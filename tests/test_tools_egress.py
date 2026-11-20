"""Tool egress: tool hosts, author allowlist/consent, receipts and no bypass."""

from __future__ import annotations

import httpx
import pytest

from swarmbly_app import egress
from swarmbly_app.config import ConfigError, validate_changes
from swarmbly_app.tools import ToolCall, ToolDenied, ToolSpec
import swarmbly_app.tools.broker as broker_module
from swarmbly_app.tools import ToolBroker


def _policy(monkeypatch, tool_hosts=()):
    cfg = {"privacy": {"tool_hosts": list(tool_hosts)}}
    monkeypatch.setattr(egress, "_config_getter", lambda: cfg)
    return cfg


def _mock_http(monkeypatch):
    seen: list[httpx.Request] = []
    real = httpx.Client

    def client(*args, **kwargs):
        kwargs["transport"] = httpx.MockTransport(
            lambda request: (seen.append(request) or httpx.Response(200, text="ok")))
        return real(*args, **kwargs)

    monkeypatch.setattr(broker_module.httpx, "Client", client)
    return seen


def _remote_spec(host="api.example.com"):
    return ToolSpec("mcp_remote/weather", "mcp_remote", f"https://{host}/tool",
                    {"type": "object", "properties": {"q": {"type": "string"}},
                     "required": ["q"]},
                    "Weather")


def _author_spec():
    return ToolSpec("author/orcid", "author",
                    "https://pub.orcid.org/v3.0/expanded-search/",
                    {"type": "object", "properties": {"name": {"type": "string"}},
                     "required": ["name"]},
                    "ORCID author search")


def _handler():
    def run(call, ctx):
        return ctx.http_get(ctx.spec.destination, params={"q": call.arguments.get("q", "")}).text
    return run


def test_tool_remote_policy_requires_tool_hosts_for_any_non_local_destination(monkeypatch):
    _policy(monkeypatch)
    strict = egress.policy()
    assert strict.allows(egress.THIRD_PARTY, "api.example.com", egress.TOOL_REMOTE)[0] is False
    assert strict.allows(egress.OWN_NETWORK, "nas.local", egress.TOOL_REMOTE)[0] is False
    assert strict.allows(egress.LOCAL, "127.0.0.1", egress.TOOL_REMOTE)[0] is True

    _policy(monkeypatch, ["api.example.com", "nas.local"])
    allowed = egress.policy()
    assert allowed.allows(egress.THIRD_PARTY, "api.example.com", egress.TOOL_REMOTE)[0] is True
    assert allowed.allows(egress.OWN_NETWORK, "nas.local", egress.TOOL_REMOTE)[0] is True
    assert allowed.allows(egress.THIRD_PARTY, "other.example", egress.TOOL_REMOTE)[0] is False


def test_author_query_needs_allowlist_and_per_call_consent(monkeypatch):
    _policy(monkeypatch)
    with pytest.raises(egress.EgressDenied, match="not one of the approved author sources"):
        egress.check_call("https://evil.example/v1", 1, "author", kind=egress.AUTHOR_QUERY)
    with pytest.raises(egress.EgressDenied, match="no per-call consent"):
        egress.check_call("https://pub.orcid.org/v3.0/expanded-search/", 1,
                          "author", kind=egress.AUTHOR_QUERY)
    with egress.author_consent():
        egress.check_call("https://pub.orcid.org/v3.0/expanded-search/", 1,
                          "author", kind=egress.AUTHOR_QUERY)
    with pytest.raises(egress.EgressDenied, match="no per-call consent"):
        egress.check_call("https://api.openalex.org/authors", 1,
                          "author", kind=egress.AUTHOR_QUERY)


def test_local_tool_call_is_recorded_even_though_check_call_skips_local(monkeypatch):
    _policy(monkeypatch)
    with egress.request_ledger("r") as ledger:
        egress.check_call("http://127.0.0.1:9/tool", 5, "local", kind=egress.TOOL_LOCAL)
    assert ledger.events == [{
        "t": ledger.events[0]["t"], "destino": "local", "clase": egress.LOCAL,
        "tipo": egress.TOOL_LOCAL, "bytes": 0, "motivo": "local"}]


def test_remote_tool_without_tool_hosts_sends_nothing(monkeypatch, tmp_path):
    _policy(monkeypatch)
    seen = _mock_http(monkeypatch)
    broker = ToolBroker(tmp_path)
    spec = _remote_spec()
    broker.register(spec, _handler())
    broker.approve(spec.id)
    with egress.request_ledger("r") as ledger:
        with pytest.raises(ToolDenied, match="not an authorised tool host"):
            broker.invoke(ToolCall(spec.id, {"q": "Lontra"}, "r"))
    assert seen == []
    receipt = egress.build_receipt(ledger, lane="local", route="local",
                                   answer="", consent={})
    assert receipt["envios"] == [] and receipt["bloqueados"]
    assert receipt["tools"][0]["allowed"] is False
    assert receipt["tools"][0]["spec_id"] == spec.id


def test_remote_handler_cannot_swallow_a_policy_denial(monkeypatch, tmp_path):
    _policy(monkeypatch)
    seen = _mock_http(monkeypatch)
    broker = ToolBroker(tmp_path)
    spec = _remote_spec()

    def swallow(call, ctx):
        try:
            ctx.http_get(ctx.spec.destination, params={"q": "x"})
        except egress.EgressDenied:
            return "pretend it worked"
        return "unexpected"

    broker.register(spec, swallow)
    broker.approve(spec.id)
    with pytest.raises(ToolDenied, match="not an authorised tool host"):
        broker.invoke(ToolCall(spec.id, {"q": "x"}, "r"))
    assert seen == []


def test_remote_tool_with_tool_hosts_sends_and_counts_twice(monkeypatch, tmp_path):
    _policy(monkeypatch, ["api.example.com"])
    seen = _mock_http(monkeypatch)
    broker = ToolBroker(tmp_path)
    spec = _remote_spec()
    broker.register(spec, _handler())
    broker.approve(spec.id)
    with egress.request_ledger("r") as ledger:
        result = broker.invoke(ToolCall(spec.id, {"q": "Lontra"}, "r"))
    assert result.ok and result.content == "ok"
    assert len(seen) == 1 and "api.example.com" in str(seen[0].url)
    receipt = egress.build_receipt(ledger, lane="local", route="local",
                                   answer="", consent={})
    assert [s["tipo"] for s in receipt["envios"]] == [egress.TOOL_REMOTE]
    assert receipt["bytes_salientes"] > 0
    assert receipt["tools"][0]["allowed"] is True
    assert receipt["tools"][0]["bytes"] == receipt["bytes_salientes"]
    assert receipt["tools"][0]["approved_by"] == "approval"


def test_author_tool_sets_consent_only_for_the_call(monkeypatch, tmp_path):
    _policy(monkeypatch)
    seen = _mock_http(monkeypatch)
    broker = ToolBroker(tmp_path)
    spec = _author_spec()
    broker.register(spec, _handler())
    broker.approve(spec.id)
    with pytest.raises(ToolDenied, match="one-time approval token"):
        broker.invoke(ToolCall(spec.id, {"name": "Ada Lovelace"}, "r"))
    assert seen == []

    token = broker.issue_token(ToolCall(spec.id, {"name": "Ada Lovelace"}, "r"))
    with egress.request_ledger("r") as ledger:
        result = broker.invoke(ToolCall(spec.id, {"name": "Ada Lovelace"}, "r", token=token))
    assert result.ok and len(seen) == 1
    assert egress.author_consent_granted() is False
    with pytest.raises(egress.EgressDenied, match="no per-call consent"):
        egress.check_call("https://pub.orcid.org/v3.0/expanded-search/", 1,
                          "author", kind=egress.AUTHOR_QUERY)
    receipt = egress.build_receipt(ledger, lane="local", route="local",
                                   answer="", consent={})
    assert receipt["tools"][0]["tipo"] == egress.AUTHOR_QUERY
    assert receipt["tools"][0]["approved_by"] == "token"


def test_author_allowlist_is_fixed():
    assert egress.AUTHOR_HOSTS == ("pub.orcid.org", "api.openalex.org",
                                   "eutils.ncbi.nlm.nih.gov")


def test_carry_keeps_tool_consent_and_ledger_in_a_thread(monkeypatch):
    from concurrent.futures import ThreadPoolExecutor

    _policy(monkeypatch)

    def lookup():
        egress.check_call("https://pub.orcid.org/v3.0/expanded-search/", 7,
                          "author", kind=egress.AUTHOR_QUERY)

    with egress.request_ledger("r") as ledger, egress.author_consent():
        with ThreadPoolExecutor(max_workers=1) as pool:
            pool.submit(egress.carry(lookup)).result()
    assert [e["tipo"] for e in ledger.events] == [egress.AUTHOR_QUERY]
    assert ledger.events[0]["bytes"] == 7


def test_tool_hosts_config_is_normalised_and_validated():
    from swarmbly_app.config import DEFAULTS

    assert DEFAULTS["privacy"]["tool_hosts"] == []
    flat = validate_changes({"privacy": {"tool_hosts": [
        "https://API.Example.com/v1", "api.example.com", "192.168.1.5"]}})
    assert flat["privacy.tool_hosts"] == ["192.168.1.5", "api.example.com"]
    with pytest.raises(ConfigError, match="valid host"):
        validate_changes({"privacy": {"tool_hosts": ["bad host"]}})
    with pytest.raises(ConfigError, match="non-empty host"):
        validate_changes({"privacy": {"tool_hosts": [""]}})
