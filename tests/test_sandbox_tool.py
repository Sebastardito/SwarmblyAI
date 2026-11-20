"""Broker-level checks for ``sandbox/python`` (T7.1).

Light tests run without the optional extra: availability, the spec contract,
token enforcement and project-folder containment happen before a worker is
started.  The one end-to-end run is skipped when ``wasi-python`` is absent and
also verifies that a local tool produces a ``TOOL_LOCAL`` receipt entry and no
outbound traffic.
"""

from __future__ import annotations

import importlib
from pathlib import Path

import pytest

from swarmbly_app import egress
from swarmbly_app.sandbox import (Limits, SandboxRunner, available, input_schema,
                                  tool_spec)
from swarmbly_app.tools import (ToolBroker, ToolCall, ToolDenied, ToolResult,
                                register_sandbox)

pytestmark = pytest.mark.sandbox


def _project(tmp_path: Path) -> tuple[Path, Path]:
    project = tmp_path / "project"
    (project / "sources").mkdir(parents=True)
    (project / "sources" / "input.csv").write_text("region,amount\nnorth,10\n")
    outside = tmp_path / "outside.csv"
    outside.write_text("secret\n1\n")
    return project, outside


def _broker(tmp_path: Path, project: Path, runner=None):
    broker = ToolBroker(tmp_path / "data",
                        project_path=lambda pid: project if pid == "p1" else None)
    spec = register_sandbox(broker, project_path=lambda pid: project if pid == "p1" else None,
                            runner=runner if runner is not None else SandboxRunner(
                                tmp_path / "sandbox-root"))
    broker.approve(spec.id, "p1")
    return broker, spec


def test_tool_spec_contract() -> None:
    spec = tool_spec()
    assert spec.id == "sandbox/python"
    assert spec.provider == "sandbox" and spec.kind == "sandbox"
    assert spec.destination == "local"
    assert spec.requires_token is True and spec.is_remote is False
    schema = spec.input_schema
    assert schema["required"] == ["script"]
    assert schema["properties"]["script"]["type"] == "string"
    assert schema["properties"]["script"]["maxLength"] == 20_000
    assert schema["properties"]["inputs"]["type"] == "array"
    assert schema["properties"]["inputs"]["items"]["type"] == "string"
    assert schema["properties"]["inputs"]["maxItems"] == 20
    assert input_schema() == schema


def test_default_limits() -> None:
    limits = Limits()
    assert limits.deadline_s == 10.0
    assert limits.memory_bytes == 256 * 1024 * 1024
    assert limits.output_bytes == 4 * 1024 * 1024
    assert limits.fuel is None
    assert limits.max_out_bytes == 256 * 1024 * 1024
    assert limits.max_out_files == 10_000
    assert limits.max_file_bytes == 384 * 1024 * 1024


def test_registration_through_tools_helper(tmp_path: Path) -> None:
    project, _ = _project(tmp_path)
    broker, spec = _broker(tmp_path, project)
    assert broker.spec("sandbox/python") is not None
    assert broker.spec("sandbox/python").approval_hash == spec.approval_hash


def test_missing_or_changed_token_is_refused(tmp_path: Path) -> None:
    project, _ = _project(tmp_path)

    class NeverRunner:
        def run(self, *args, **kwargs):  # pragma: no cover - must not be reached
            raise AssertionError("the broker must reject before the handler runs")

    broker, spec = _broker(tmp_path, project, NeverRunner())
    arguments = {"script": "print('one')", "inputs": []}

    with pytest.raises(ToolDenied, match="needs a one-time"):
        broker.invoke(ToolCall(spec.id, arguments, "r1", project_id="p1"))

    token = broker.issue_token(ToolCall(spec.id, arguments, "r1"))
    with pytest.raises(ToolDenied, match="different arguments"):
        broker.invoke(ToolCall(spec.id, {"script": "print('two')", "inputs": []},
                               "r1", token=token, project_id="p1"))


def test_script_change_after_approval_does_not_reuse_a_token(tmp_path: Path) -> None:
    project, _ = _project(tmp_path)
    broker, spec = _broker(tmp_path, project, NeverRunner())
    approved_script = "print('approved')"
    token = broker.issue_token(ToolCall(
        spec.id, {"script": approved_script, "inputs": []}, "req"))
    with pytest.raises(ToolDenied, match="different arguments"):
        broker.invoke(ToolCall(
            spec.id, {"script": "print('tampered')", "inputs": []}, "req",
            token=token, project_id="p1"))


class NeverRunner:
    def run(self, *args, **kwargs):  # pragma: no cover - refusal is under test
        raise AssertionError("the sandbox must not run for an invalid input")


def _invoke_input(broker: ToolBroker, spec, inputs: list[str]) -> ToolResult:
    arguments = {"script": "print('should not run')", "inputs": inputs}
    token = broker.issue_token(ToolCall(spec.id, arguments, "r"))
    return broker.invoke(ToolCall(spec.id, arguments, "r", token=token,
                                  project_id="p1"))


@pytest.mark.parametrize("bad", ["../outside.csv", "/etc/passwd", "sources/../../outside.csv"])
def test_inputs_outside_the_project_are_refused(tmp_path: Path, bad: str) -> None:
    project, _ = _project(tmp_path)
    broker, spec = _broker(tmp_path, project, NeverRunner())
    result = _invoke_input(broker, spec, [bad])
    assert result.ok is False
    assert "project" in result.error.lower() or "clean" in result.error.lower()


def test_symlink_escaping_the_project_is_refused(tmp_path: Path) -> None:
    project, outside = _project(tmp_path)
    link = project / "sources" / "escape.csv"
    try:
        link.symlink_to(outside)
    except OSError as exc:
        pytest.skip(f"this platform cannot create a test symlink: {exc}")
    broker, spec = _broker(tmp_path, project, NeverRunner())
    result = _invoke_input(broker, spec, ["sources/escape.csv"])
    assert result.ok is False
    assert "outside the project" in result.error


def test_empty_approval_is_refused_before_a_worker_starts(tmp_path: Path) -> None:
    runner = SandboxRunner(tmp_path / "root")
    with pytest.raises(ValueError, match="approval"):
        runner.run("print(1)", [], approval="")
    runner.close()


def test_available_false_when_the_package_import_fails(monkeypatch) -> None:
    real = importlib.import_module

    def fake(name, *args, **kwargs):
        if name == "wasi_python":
            raise ImportError("simulated missing wasi-python")
        return real(name, *args, **kwargs)

    monkeypatch.setattr(importlib, "import_module", fake)
    ok, reason = available()
    assert ok is False
    assert "wasi_python" in reason and "not installed" in reason


@pytest.mark.skipif(not available()[0], reason="the [sandbox] extra is not installed")
def test_valid_run_is_local_and_records_tool_local(tmp_path: Path) -> None:
    project, _ = _project(tmp_path)
    runner = SandboxRunner(tmp_path / "sandbox-root")
    broker, spec = _broker(tmp_path, project, runner)
    arguments = {
        "script": ("import pandas as pd\n"
                   "df = pd.read_csv('/data/input.csv')\n"
                   "open('/out/answer.txt', 'w').write(str(int(df['amount'].sum())))\n"),
        "inputs": ["sources/input.csv"],
    }
    token = broker.issue_token(ToolCall(spec.id, arguments, "req-1"))
    try:
        with egress.request_ledger("req-1") as ledger:
            result = broker.invoke(ToolCall(spec.id, arguments, "req-1",
                                            token=token, project_id="p1"))
    finally:
        runner.close()

    assert result.ok is True, result.error
    payload = result.data
    assert payload["ok"] is True and payload["approval"] == "token"
    assert payload["script_sha256"]
    assert payload["inputs"] == ["input.csv"]
    assert payload["files"][0]["name"] == "answer.txt"
    assert payload["platform_guard"] in ("rlimit+watchdog", "watchdog")

    receipt = egress.build_receipt(ledger, lane="local", route="local",
                                   answer="", consent={})
    assert receipt["envios"] == [] and receipt["bytes_salientes"] == 0
    tools = receipt["tools"]
    assert len(tools) == 1
    assert tools[0]["spec_id"] == "sandbox/python"
    assert tools[0]["tipo"] == egress.TOOL_LOCAL
    assert tools[0]["clase"] == "local"
    assert tools[0]["approved_by"] == "token"
    assert tools[0]["bytes"] == 0
