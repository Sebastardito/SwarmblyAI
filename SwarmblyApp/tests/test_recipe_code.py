"""Recipe 5: data with code (3.4).

The model only sees headers and at most five rows; nothing runs until the user
approves the script; approval is the only endpoint that issues the broker's
one-time token.  Tests that execute the real WebAssembly guest are marked
``sandbox`` and skip cleanly when the optional extra is absent.
"""

from __future__ import annotations

import json
import zipfile
from pathlib import Path
from urllib.parse import quote

import pytest

from conftest import FakeBackend, prepare_guest_for_test
from swarmbly_app import egress
from swarmbly_app.inference.base import GenerationResult
from swarmbly_app.recipes import (CodeRecipeError, build_code_prompt,
                                  markdown_tables, parse_code_script, sample_csv,
                                  sample_xlsx)
from swarmbly_app.sandbox import available
from swarmbly_app.tools import ToolCall, ToolDenied
from test_api_lce import make_client

SANDBOX = pytest.mark.skipif(not available()[0],
                             reason="the [sandbox] extra is not installed")


class ScriptBackend(FakeBackend):
    """A fake writer: returns a script and keeps every prompt it received."""

    def __init__(self, reply: str):
        super().__init__(reply=reply)
        self.prompts: list[str] = []

    def stream_chat(self, messages, *, model, max_tokens=1024, temperature=0.2,
                    on_delta=None, interrupt=None, system=None, **kw):
        self.calls.append({"messages": messages, "model": model})
        self.prompts.append(str(messages[-1]["content"]))
        return GenerationResult(text=self.reply, model=model, completion_tokens=2,
                                total_ms=1)


@pytest.fixture()
def sandbox_cleanup(app_state):
    """Close the chat-owned runner after a test that executed the guest."""
    yield
    runner = getattr(app_state.chat, "_code_runner", None)
    if runner is not None:
        runner.close()


def _status() -> dict:
    return {
        "available": True, "reason": "", "platform_guard": "rlimit+watchdog",
        "watchdog_only": False,
        "limits": {"deadline_s": 10.0, "memory_mib": 256, "output_mib": 4,
                   "max_out_mib": 256, "max_out_files": 10000},
        "max_corrections": 2,
    }


def _as_available(monkeypatch, app_state) -> None:
    """Proposal tests do not need to compile wasm: they only write a script."""
    monkeypatch.setattr(app_state.chat, "code_status", lambda: _status())


def _project(app_state, tmp_path: Path, rows: int = 8):
    project = app_state.projects.create("Recipe5", parent=tmp_path / "p")
    lines = ["hive,apiary,weight"]
    for i in range(1, rows + 1):
        if i == 7:
            lines.append(f"hive-{i},SENTINEL-APIARY,{i}")
        else:
            lines.append(f"hive-{i},apiary-{i % 3},{100 + i}")
    csv_path = project.sources / "hive.csv"
    csv_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return project, csv_path


def _write_xlsx(path: Path, rows: list[list[object]]) -> None:
    def col(index: int) -> str:
        return chr(ord("A") + index)

    cells = []
    for r, row in enumerate(rows, start=1):
        parts = []
        for c, value in enumerate(row):
            ref = f"{col(c)}{r}"
            if isinstance(value, str):
                parts.append(f'<c r="{ref}" t="inlineStr"><is><t>{value}</t></is></c>')
            else:
                parts.append(f'<c r="{ref}"><v>{value}</v></c>')
        cells.append(f'<row r="{r}">' + "".join(parts) + "</row>")
    sheet = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
             '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
             "<sheetData>" + "".join(cells) + "</sheetData></worksheet>")
    content_types = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                     '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
                     '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
                     '<Default Extension="xml" ContentType="application/xml"/>'
                     '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
                     '<Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
                     "</Types>")
    rels = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>'
            "</Relationships>")
    workbook = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
                'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
                '<sheets><sheet name="Sheet1" sheetId="1" r:id="rId1"/></sheets></workbook>')
    workbook_rels = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                     '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                     '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>'
                     "</Relationships>")
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", content_types)
        archive.writestr("_rels/.rels", rels)
        archive.writestr("xl/workbook.xml", workbook)
        archive.writestr("xl/_rels/workbook.xml.rels", workbook_rels)
        archive.writestr("xl/worksheets/sheet1.xml", sheet)


# --------------------------------------------------------------------------- parsing and sampling


def test_script_parsing_is_defensive_and_capped():
    assert parse_code_script("```python\nprint(1)\n```") == "print(1)"
    assert parse_code_script("Here:\n```py\nprint(2)\n```\nThanks") == "print(2)"
    assert parse_code_script("print(3)") == "print(3)"
    with pytest.raises(CodeRecipeError):
        parse_code_script("I cannot write that script.")
    with pytest.raises(CodeRecipeError):
        parse_code_script("```python\n\x00\n```")
    with pytest.raises(CodeRecipeError, match="longer"):
        parse_code_script("```python\n" + "x" * 120 + "\n```", max_chars=50)


def test_csv_and_xlsx_samples_have_headers_and_at_most_five_rows(tmp_path: Path):
    csv_path = tmp_path / "table.csv"
    csv_path.write_text("hive,apiary,weight\n" + "".join(
        f"h{i},a{i},SENTINEL-{i}\n" for i in range(1, 9)), encoding="utf-8")
    table = sample_csv(csv_path)
    assert table["headers"] == ["hive", "apiary", "weight"]
    assert len(table["rows"]) == 5
    assert "SENTINEL-8" not in json.dumps(table)

    xlsx_path = tmp_path / "table.xlsx"
    _write_xlsx(xlsx_path, [["hive", "apiary", "weight"],
                            *[[f"h{i}", f"a{i}", f"SENTINEL-{i}"] for i in range(1, 9)]])
    xlsx = sample_xlsx(xlsx_path)
    assert xlsx["headers"] == ["hive", "apiary", "weight"]
    assert len(xlsx["rows"]) == 5
    assert "SENTINEL-8" not in json.dumps(xlsx)

    markdown = "# Table\n\n| hive | apiary | weight |\n|---|---|---|\n" + "".join(
        f"| h{i} | a{i} | SENTINEL-{i} |\n" for i in range(1, 9))
    tables = markdown_tables(markdown)
    assert len(tables) == 1 and len(tables[0]["rows"]) == 5
    assert "SENTINEL-8" not in json.dumps(tables)


def test_prompt_carries_only_the_sample_and_never_the_sentinel(tmp_path: Path):
    csv_path = tmp_path / "table.csv"
    csv_path.write_text("hive,apiary,weight\n" + "".join(
        f"h{i},a{i},ROW-{i}\n" for i in range(1, 9)), encoding="utf-8")
    sample = sample_csv(csv_path)
    prompt = build_code_prompt("average weight per apiary", [{"name": "table.csv"}],
                               [sample])
    assert "hive | apiary | weight" in prompt
    assert "ROW-5" in prompt and "ROW-6" not in prompt
    assert prompt.count("ROW-") == 5


# --------------------------------------------------------------------------- proposal / approval


def test_proposal_uses_a_fake_model_and_never_runs(app_state, tmp_path, monkeypatch):
    _as_available(monkeypatch, app_state)
    project, _ = _project(app_state, tmp_path)
    fake = ScriptBackend("```python\nprint('not run')\n```")
    app_state.backends.resolve = lambda config=None: fake  # type: ignore[method-assign]
    called: list[object] = []
    monkeypatch.setattr(app_state.tools, "invoke", lambda call: called.append(call))
    monkeypatch.setattr(app_state.tools, "issue_token", lambda call: called.append(call))
    client = make_client(app_state)

    response = client.post("/api/recipes/code/propose", json={
        "project_id": project.id, "question": "average weight per apiary",
        "files": ["hive.csv"]})
    assert response.status_code == 200, response.text
    proposal = response.json()
    assert proposal["script"] == "print('not run')"
    assert proposal["script_sha256"]
    assert proposal["files"] == [{"name": "hive.csv", "rel": "hive.csv"}]
    assert proposal["limits"]["deadline_s"] == 10.0
    assert proposal["corrections"] == 0 and proposal["corrections_left"] == 2
    assert called == [], "propose must not invoke the broker or issue a token"
    prompt = fake.prompts[-1]
    assert "hive | apiary | weight" in prompt
    assert "SENTINEL-APIARY" not in prompt
    assert "hive-5" in prompt and "hive-6" not in prompt
    messages = client.get(f"/api/conversations/{proposal['conversation_id']}/messages").json()
    assert messages == []


def test_cancel_runs_nothing(app_state, tmp_path, monkeypatch):
    _as_available(monkeypatch, app_state)
    project, _ = _project(app_state, tmp_path)
    fake = ScriptBackend("```python\nprint('cancelled')\n```")
    app_state.backends.resolve = lambda config=None: fake  # type: ignore[method-assign]
    called: list[object] = []
    monkeypatch.setattr(app_state.tools, "invoke", lambda call: called.append(call))
    client = make_client(app_state)
    proposal = client.post("/api/recipes/code/propose", json={
        "project_id": project.id, "question": "q", "files": ["hive.csv"]}).json()
    cancelled = client.post("/api/recipes/code/cancel",
                            json={"proposal_id": proposal["proposal_id"]})
    assert cancelled.status_code == 200
    refused = client.post("/api/recipes/code/approve",
                          json={"proposal_id": proposal["proposal_id"]})
    assert refused.status_code == 400
    assert "cancel" in refused.json()["detail"].lower()
    assert called == []
    messages = client.get(f"/api/conversations/{proposal['conversation_id']}/messages").json()
    assert messages == []


def test_missing_extra_is_reported_and_offers_nothing(app_state, tmp_path, monkeypatch):
    import swarmbly_app.sandbox as sandbox
    monkeypatch.setattr(sandbox, "available",
                        lambda: (False, "wasi-python is not installed"))
    project, _ = _project(app_state, tmp_path)
    client = make_client(app_state)
    status = client.get("/api/recipes/code/status").json()
    assert status["available"] is False and "not installed" in status["reason"]
    response = client.post("/api/recipes/code/propose", json={
        "project_id": project.id, "question": "q", "files": ["hive.csv"]})
    assert response.status_code == 503
    assert "not installed" in response.json()["detail"]
    assert "proposal_id" not in response.text


def test_windows_watchdog_flag_is_plain(monkeypatch):
    import swarmbly_app.chat as chat
    import swarmbly_app.sandbox as sandbox
    monkeypatch.setattr(sandbox, "available", lambda: (True, ""))
    monkeypatch.setattr(chat.sys, "platform", "win32")
    # code_status only needs config/limits on this path; use a tiny object.
    class Dummy:
        tools = None
        def config(self):
            return {}
        _code_cfg = chat.ChatService._code_cfg
        _code_limits_payload = chat.ChatService._code_limits_payload
        _code_platform_guard = staticmethod(chat.ChatService._code_platform_guard)
    dummy = Dummy()
    status = chat.ChatService.code_status(dummy)
    assert status["platform_guard"] == "watchdog" and status["watchdog_only"] is True


@SANDBOX
@pytest.mark.sandbox
def test_token_is_required_single_use_and_bound_to_the_script(app_state, tmp_path, monkeypatch, sandbox_cleanup):
    _as_available(monkeypatch, app_state)
    project, _ = _project(app_state, tmp_path)
    fake = ScriptBackend("```python\nprint('token')\n```")
    app_state.backends.resolve = lambda config=None: fake  # type: ignore[method-assign]
    client = make_client(app_state)
    proposal = client.post("/api/recipes/code/propose", json={
        "project_id": project.id, "question": "q", "files": ["hive.csv"]}).json()
    approved = client.post("/api/recipes/code/approve",
                           json={"proposal_id": proposal["proposal_id"]})
    assert approved.status_code == 200, approved.text
    proforma = app_state.chat._code_proposals[proposal["proposal_id"]]
    args = {"script": proforma["script"], "inputs": proforma["inputs"]}

    with pytest.raises(ToolDenied, match="needs a one-time"):
        app_state.tools.invoke(ToolCall("sandbox/python", args, "r", project_id=project.id))
    first = app_state.tools.issue_token(ToolCall("sandbox/python", args, "r"))
    assert app_state.tools.invoke(ToolCall("sandbox/python", args, "r", token=first,
                                          project_id=project.id)).ok
    with pytest.raises(ToolDenied, match="already used"):
        app_state.tools.invoke(ToolCall("sandbox/python", args, "r", token=first,
                                        project_id=project.id))
    changed = app_state.tools.issue_token(ToolCall("sandbox/python", args, "r2"))
    with pytest.raises(ToolDenied, match="different arguments"):
        app_state.tools.invoke(ToolCall("sandbox/python",
                                        {"script": "print('tampered')", "inputs": args["inputs"]},
                                        "r2", token=changed, project_id=project.id))


@SANDBOX
@pytest.mark.sandbox
def test_trap_plain_reason_and_a_correction_needs_another_approval(app_state, tmp_path, monkeypatch, sandbox_cleanup):
    _as_available(monkeypatch, app_state)
    project, _ = _project(app_state, tmp_path)
    fake = ScriptBackend("```python\nprint('x'*(5*1024*1024))\n```")
    app_state.backends.resolve = lambda config=None: fake  # type: ignore[method-assign]
    client = make_client(app_state)
    proposal = client.post("/api/recipes/code/propose", json={
        "project_id": project.id, "question": "q", "files": ["hive.csv"]}).json()
    trapped = client.post("/api/recipes/code/approve",
                          json={"proposal_id": proposal["proposal_id"]})
    assert trapped.status_code == 200, trapped.text
    message = trapped.json()["assistant_message"]
    assert message["meta"]["code"]["trapped"] == "output"
    assert "printed more output" in message["content"]
    before = len(client.get(f"/api/conversations/{proposal['conversation_id']}/messages").json())

    fake.reply = "```python\nprint('fixed')\n```"
    corrected = client.post("/api/recipes/code/propose",
                            json={"correction_of": proposal["proposal_id"]})
    assert corrected.status_code == 200, corrected.text
    assert corrected.json()["corrections"] == 1
    assert len(client.get(f"/api/conversations/{proposal['conversation_id']}/messages").json()) == before
    ran = client.post("/api/recipes/code/approve",
                      json={"proposal_id": corrected.json()["proposal_id"]})
    assert ran.status_code == 200
    assert ran.json()["assistant_message"]["meta"]["code"]["corrections"] == 1
    assert ran.json()["assistant_message"]["meta"]["code"]["trapped"] is None

    fake.reply = "```python\nprint('fixed again')\n```"
    second = client.post("/api/recipes/code/propose",
                         json={"correction_of": corrected.json()["proposal_id"]})
    assert second.status_code == 200 and second.json()["corrections"] == 2
    third = client.post("/api/recipes/code/propose",
                        json={"correction_of": second.json()["proposal_id"]})
    assert third.status_code == 400
    assert "correction" in third.json()["detail"].lower()


@SANDBOX
@pytest.mark.sandbox
def test_successful_run_meta_receipt_and_safe_download(app_state, tmp_path, monkeypatch, sandbox_cleanup):
    _as_available(monkeypatch, app_state)
    project, _ = _project(app_state, tmp_path)
    fake = ScriptBackend(
        "```python\n"
        "import pandas as pd\n"
        "df=pd.read_csv('/data/hive.csv')\n"
        "print(df.groupby('apiary')['weight'].mean().to_string())\n"
        "open('/out/result.txt','w').write('ok')\n"
        "```")
    app_state.backends.resolve = lambda config=None: fake  # type: ignore[method-assign]
    client = make_client(app_state)
    with egress.request_ledger("proposal") as ledger:
        proposal = client.post("/api/recipes/code/propose", json={
            "project_id": project.id, "question": "average weight per apiary",
            "files": ["hive.csv"]}).json()
    assert ledger.events == [] or all(e.get("clase") == "local" for e in ledger.events)
    approved = client.post("/api/recipes/code/approve",
                           json={"proposal_id": proposal["proposal_id"]})
    assert approved.status_code == 200, approved.text
    message = approved.json()["assistant_message"]
    code = message["meta"]["code"]
    assert set(code) == {"script_sha256", "files_in", "trapped", "elapsed_s",
                         "approved_by", "corrections", "model", "backend"}
    assert code["approved_by"] == "user" and code["trapped"] is None
    assert code["model"] == "fake-model:1b"
    assert code["backend"]
    assert code["files_in"] == ["hive.csv"]
    assert code["elapsed_s"] >= 0
    run = message["meta"]["code_run"]
    assert run["platform_guard"] in ("rlimit+watchdog", "watchdog")
    assert run["files"] and run["files"][0]["name"] == "result.txt"
    assert len(run["files"][0]["sha256"]) == 64
    receipt = message["meta"]["receipt"]
    assert receipt["envios"] == []
    assert [tool["spec_id"] for tool in receipt["tools"]] == ["sandbox/python"]
    assert receipt["tools"][0]["clase"] == "local"
    assert receipt["recipe"] == "code"

    url = run["files"][0]["url"]
    downloaded = client.get(url)
    assert downloaded.status_code == 200 and downloaded.content == b"ok"

    out = app_state.chat._code_runner.output_dir_for(run["run_id"])
    assert out is not None
    (out.parent / "secret.txt").write_text("secret")
    traversal = client.get(f"/api/recipes/code/runs/{run['run_id']}/files/"
                           + quote("../secret.txt", safe=""))
    assert traversal.status_code == 404
    link = out / "link.txt"
    link.symlink_to(out.parent / "secret.txt")
    linked = client.get(f"/api/recipes/code/runs/{run['run_id']}/files/link.txt")
    assert linked.status_code == 404
    assert client.get("/api/recipes/code/runs/not-a-run/files/x.txt").status_code == 404


# ---- T9.11: recipe 5 also hands the script the text documents ---------------

def test_listing_includes_markdown_and_plain_text(app_state, tmp_path):
    project, _ = _project(app_state, tmp_path)
    (project.sources / "notas.md").write_text("# Notas\nEl total es 42.\n",
                                              encoding="utf-8")
    (project.sources / "datos.txt").write_text("clave,valor\nuno,1\n",
                                               encoding="utf-8")
    client = make_client(app_state)
    listing = client.get(f"/api/recipes/code/sources?project_id={project.id}").json()
    by_rel = {item["rel"]: item for item in listing}
    assert by_rel["notas.md"]["kind"] == "text"
    assert by_rel["datos.txt"]["kind"] == "text"
    assert by_rel["hive.csv"]["kind"] == "table"


def test_text_proposal_lists_only_the_first_lines_and_the_size(
        app_state, tmp_path, monkeypatch):
    _as_available(monkeypatch, app_state)
    project, _ = _project(app_state, tmp_path)
    lines = ["El total es 42."] + [f"SENTINEL-LINE-{n}" for n in range(2, 10)]
    (project.sources / "notas.md").write_text("\n".join(lines) + "\n",
                                              encoding="utf-8")
    fake = ScriptBackend("```python\nprint('ok')\n```")
    app_state.backends.resolve = lambda config=None: fake   # type: ignore[method-assign]
    client = make_client(app_state)
    response = client.post("/api/recipes/code/propose", json={
        "project_id": project.id, "question": "combine the note with the table",
        "files": ["hive.csv", "notas.md"]})
    assert response.status_code == 200, response.text
    assert [f["name"] for f in response.json()["files"]] == ["hive.csv", "notas.md"]
    prompt = fake.prompts[-1]
    assert "- FILE: notas.md (" in prompt and "bytes)" in prompt
    assert "TEXT: first lines" in prompt and "El total es 42." in prompt
    assert "SENTINEL-LINE-6" not in prompt and "SENTINEL-LINE-7" not in prompt


def test_symlinked_text_is_refused_and_an_escape_is_refused(
        app_state, tmp_path, monkeypatch):
    _as_available(monkeypatch, app_state)
    project, _ = _project(app_state, tmp_path)
    outside = tmp_path / "outside.md"
    outside.write_text("SENTINEL-OUTSIDE\n", encoding="utf-8")
    link = project.sources / "linked.md"
    try:
        link.symlink_to(outside)
    except OSError:
        pytest.skip("this platform cannot create a test symlink")
    fake = ScriptBackend("```python\nprint('ok')\n```")
    app_state.backends.resolve = lambda config=None: fake    # type: ignore[method-assign]
    client = make_client(app_state)
    names = [item["rel"] for item in
             client.get(f"/api/recipes/code/sources?project_id={project.id}").json()]
    assert "linked.md" not in names
    for ref in ("linked.md", "../outside.md", str(outside)):
        response = client.post("/api/recipes/code/propose", json={
            "project_id": project.id, "question": "q", "files": [ref]})
        assert response.status_code == 400, ref
        assert "not in this project's sources" in response.json()["detail"]
    assert fake.prompts == []


def test_text_file_over_the_size_cap_is_refused(app_state, tmp_path, monkeypatch):
    _as_available(monkeypatch, app_state)
    app_state.config.update({"recipes": {"code_max_file_bytes": 80}})
    project, _ = _project(app_state, tmp_path)
    (project.sources / "notas.md").write_text("x" * 200, encoding="utf-8")
    fake = ScriptBackend("```python\nprint('ok')\n```")
    app_state.backends.resolve = lambda config=None: fake    # type: ignore[method-assign]
    client = make_client(app_state)
    listing = client.get(f"/api/recipes/code/sources?project_id={project.id}").json()
    note = next(item for item in listing if item["rel"] == "notas.md")
    assert note["too_large"] is True
    response = client.post("/api/recipes/code/propose", json={
        "project_id": project.id, "question": "q", "files": ["notas.md"]})
    assert response.status_code == 400
    assert "byte limit" in response.json()["detail"]
    assert fake.prompts == []


@pytest.mark.sandbox
@pytest.mark.skipif(not available()[0], reason="the [sandbox] extra is not installed")
def test_recipe5_script_reads_the_text_and_the_spreadsheet(
        app_state, tmp_path, monkeypatch):
    project, _ = _project(app_state, tmp_path)
    (project.sources / "notas.md").write_text("El total de agujas es 42.\n",
                                              encoding="utf-8")
    fake = ScriptBackend(
        "```python\n"
        "import csv\n"
        "nota = open('/data/notas.md', encoding='utf-8').read()\n"
        "with open('/data/hive.csv', encoding='utf-8') as fh:\n"
        "    rows = list(csv.DictReader(fh))\n"
        "print(nota.strip(), len(rows))\n"
        "```")
    app_state.backends.resolve = lambda config=None: fake    # type: ignore[method-assign]
    # R-005: recipe 5 refuses an unprepared cache instead of compiling inside
    # the request; this test runs the real guest.
    prepare_guest_for_test(app_state)
    client = make_client(app_state)
    proposal = client.post("/api/recipes/code/propose", json={
        "project_id": project.id, "question": "combine the note and the table",
        "files": ["hive.csv", "notas.md"]}).json()
    try:
        approved = client.post("/api/recipes/code/approve",
                               json={"proposal_id": proposal["proposal_id"]})
        assert approved.status_code == 200, approved.text
        message = approved.json()["assistant_message"]
        assert message["meta"]["code"]["trapped"] is None
        assert "42" in message["content"] and "8" in message["content"]
    finally:
        if app_state.chat._code_runner is not None:
            app_state.chat._code_runner.close()


# ---- T10.17: the script writer is the configured chat model -----------------

def test_code_uses_the_writer_role_and_falls_back_to_the_conversation_model(
        app_state, tmp_path, monkeypatch):
    """Recipe 5 writes the script with the ``writer`` role (3.4 design); with
    no writer configured it uses the conversation's model. Either way the
    proposal records the model that really wrote it."""
    _as_available(monkeypatch, app_state)
    project, _ = _project(app_state, tmp_path)

    class TwoModels(ScriptBackend):
        def list_models(self):
            return ["configured:7b", "big:27b"]

    fake = TwoModels("```python\nprint('ok')\n```")
    app_state.backends.resolve = lambda config=None: fake
    app_state.config.update({"model": {"model_name": "configured:7b"}})
    conv = app_state.chat.create_conversation(mode="local", model="configured:7b",
                                              project_id=project.id)
    proposal = app_state.chat.propose_code(
        conversation_id=conv["id"], question="sum the weights",
        files=["hive.csv"])
    assert fake.calls[-1]["model"] == "configured:7b"
    assert proposal["model"] == "configured:7b"

    app_state.config.update({"roles": {"writer": {"model": "big:27b"}}})
    proposal = app_state.chat.propose_code(
        conversation_id=conv["id"], question="sum the weights",
        files=["hive.csv"])
    assert fake.calls[-1]["model"] == "big:27b"
    assert proposal["model"] == "big:27b"
    assert proposal["backend"] == "fake"


def test_code_records_the_model_and_backend_in_meta_and_receipt(
        app_state, tmp_path, monkeypatch, sandbox_cleanup):
    _as_available(monkeypatch, app_state)
    project, _ = _project(app_state, tmp_path)
    fake = ScriptBackend("```python\nprint('42')\n```")
    app_state.backends.resolve = lambda config=None: fake  # type: ignore[method-assign]
    conv = app_state.chat.create_conversation(mode="local", model="configured:7b",
                                              project_id=project.id)
    proposal = app_state.chat.propose_code(
        conversation_id=conv["id"], project_id=project.id,
        question="print the answer", files=["hive.csv"])
    assert proposal["model"] == "configured:7b"
    result = app_state.chat.approve_code(proposal["proposal_id"])
    message = result["assistant_message"]
    assert message["meta"]["model"] == "configured:7b"
    assert message["meta"]["code"]["model"] == "configured:7b"
    assert message["meta"]["code"]["backend"] == "fake"
    assert message["meta"]["receipt"]["code"]["model"] == "configured:7b"
    assert message["meta"]["receipt"]["code"]["backend"] == "fake"
