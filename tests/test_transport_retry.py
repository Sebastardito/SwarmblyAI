"""A five-hour sweep must not die on one dropped socket.

The first attempt to exercise the full v0 grid aborted because the endpoint
blinked once. On a laptop swapping three models in and out of memory that is an
ordinary event, and the cost of not handling it is the whole run.

Retries are bounded and counted. An unlimited retry would hide a genuinely dead
endpoint; an uncounted one would let a run held together by retries look
identical to a clean one in the metadata.
"""

from __future__ import annotations

import pytest

from swarmbly_v0.backends import BackendUnavailable, OpenAICompatBackend


class _Flaky(OpenAICompatBackend):
    """Fails `fail_times` times, then succeeds."""

    def __init__(self, fail_times: int, **kw):
        super().__init__(retry_backoff_s=0.0, **kw)
        object.__setattr__(self, "_left", fail_times)
        object.__setattr__(self, "calls", 0)

    def _post_once(self, path, payload):
        self.calls += 1
        if self._left > 0:
            self._left -= 1
            raise BackendUnavailable("connection refused")
        return {"choices": [{"message": {"content": "ok"}}]}


def test_a_single_blip_is_survived_and_counted():
    b = _Flaky(1)
    assert b._post("/chat/completions", {})["choices"][0]["message"]["content"] == "ok"
    assert b.calls == 2
    assert b.retries == 1
    assert b.retry_events and "connection refused" in b.retry_events[0]


def test_a_clean_call_costs_no_retries():
    b = _Flaky(0)
    b._post("/chat/completions", {})
    assert b.calls == 1 and b.retries == 0 and b.retry_events == []


def test_a_dead_endpoint_still_fails_rather_than_looping():
    b = _Flaky(99)
    with pytest.raises(BackendUnavailable, match="gave up after 3 attempts"):
        b._post("/chat/completions", {})
    assert b.calls == 3, "bounded: first attempt plus max_retries"


def test_retry_can_be_switched_off():
    b = _Flaky(1, max_retries=0)
    with pytest.raises(BackendUnavailable):
        b._post("/chat/completions", {})
    assert b.calls == 1


def test_the_run_metadata_reports_the_retries():
    from swarmbly_v0.experiment import SweepConfig, load_prompts, run_sweep
    from swarmbly_v0.backends import HashEmbedder

    class _OneBlip(OpenAICompatBackend):
        def __init__(self, **kw):
            super().__init__(retry_backoff_s=0.0, prefer_sdk=False, **kw)
            object.__setattr__(self, "_blipped", False)

        def _post_once(self, path, payload):
            if not self._blipped:
                object.__setattr__(self, "_blipped", True)
                raise BackendUnavailable("connection refused")
            if path == "/embeddings":
                n = len(payload["input"])
                return {"data": [{"embedding": [1.0, 0.0, 0.0]} for _ in range(n)]}
            return {"choices": [{"message": {"content": "Alpha beta. Gamma delta."}}]}

    engine = _OneBlip()
    _, meta = run_sweep(
        load_prompts()[:2],
        SweepConfig(rhos=(1.0,), ns=(2,), ks=(1,), backend_name="openai"),
        engine,
        HashEmbedder(),
    )
    assert meta["transport_retries"] >= 1


# --------------------------------------------------------------------------- #
# the SDK path, which had no retry at all
# --------------------------------------------------------------------------- #

class _SdkClient:
    """The shape of openai.OpenAI, blipping once like the HTTP fake above.

    The reason this class exists: the whole suite passed on a machine with no
    openai package, where `_client` is None and every call takes the HTTP path.
    On a machine that has the SDK -- which is every machine that actually runs
    these sweeps against Ollama -- the SDK branch returned before ever reaching
    the retry, so the bounded retry documented on `_post` did not apply. The
    branch was marked `pragma: no cover` and was never exercised end to end.
    """

    def __init__(self, blips: int = 1, reply: str = "Alpha beta. Gamma delta.") -> None:
        self.blips = blips
        self.reply = reply
        self.calls = 0
        self.chat = self
        self.completions = self

    def create(self, **kwargs):
        self.calls += 1
        if self.calls <= self.blips:
            raise ConnectionError("connection refused")

        class _Message:
            content = self.reply

        class _Choice:
            message = _Message()

        class _Completion:
            choices = [_Choice()]

        return _Completion()


def _sdk_backend(client, **kw):
    backend = OpenAICompatBackend(retry_backoff_s=0.0, **kw)
    object.__setattr__(backend, "_client", client)
    return backend


def test_the_sdk_path_retries_a_dropped_socket_like_the_http_path_does():
    client = _SdkClient(blips=1)
    backend = _sdk_backend(client)

    assert backend.generate("hello") == "Alpha beta. Gamma delta."
    assert client.calls == 2, "the SDK call was not retried"
    assert backend.retries == 1
    assert backend.retry_events and "/chat/completions" in backend.retry_events[0]


def test_the_sdk_path_still_gives_up_after_the_bounded_number_of_attempts():
    """Bounded, not unlimited. A server that is really down must fail the run."""
    client = _SdkClient(blips=99)
    backend = _sdk_backend(client, max_retries=2)

    with pytest.raises(BackendUnavailable) as caught:
        backend.generate("hello")
    assert client.calls == 3, "max_retries=2 means three attempts, no more"
    assert "gave up after 3 attempts" in str(caught.value)


def test_both_transports_report_the_same_retry_counter():
    """The counter is what run metadata publishes, so a run held together by
    retries reads as different from a clean one -- on either transport."""
    from swarmbly_v0.experiment import SweepConfig, load_prompts, run_sweep
    from swarmbly_v0.backends import HashEmbedder

    client = _SdkClient(blips=1)
    engine = _sdk_backend(client)
    _, meta = run_sweep(
        load_prompts()[:2],
        SweepConfig(rhos=(1.0,), ns=(2,), ks=(1,), backend_name="openai"),
        engine,
        HashEmbedder(),
    )
    assert meta["transport_retries"] >= 1


def test_the_run_metadata_names_the_transport_that_actually_ran():
    """Which code path executed must not be something a reader has to infer from
    what happens to be installed.

    The suite passed on a machine with no openai package and failed on one with
    it, on a test asserting that the retry had fired -- because on the SDK path
    the retry did not exist. Nothing in the output said which path a run took.
    """
    from swarmbly_v0.experiment import SweepConfig, load_prompts, run_sweep
    from swarmbly_v0.backends import HashEmbedder

    engine = _sdk_backend(_SdkClient(blips=0))
    _, meta = run_sweep(
        load_prompts()[:2],
        SweepConfig(rhos=(1.0,), ns=(2,), ks=(1,), backend_name="openai"),
        engine,
        HashEmbedder(),
    )
    assert meta["transport"], "the run must name its transport"
    assert meta["transport_retries"] == 0, "a clean run must report zero retries"


def test_forcing_the_http_transport_is_deterministic_either_way():
    """prefer_sdk=False must take the HTTP path whether or not the SDK exists."""
    backend = OpenAICompatBackend(base_url="http://localhost:11434/v1", model="m",
                                  prefer_sdk=False)
    assert backend._client is None
    assert backend.transport != "openai-sdk"
