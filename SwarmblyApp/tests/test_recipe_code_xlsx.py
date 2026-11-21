"""Recipe 5 accepts spreadsheets even though C1 does not list them.

C1's ``READABLE_SUFFIXES`` excludes XLSX, so the recipe scans the project's
``sources`` folder directly for CSV/TSV/XLSX/XLSM while still keeping the C1
documents for their tables.  These tests cover the listing, the bounded
sample the model sees, containment (symlink/outside) and the size cap.
"""

from __future__ import annotations

import zipfile
from pathlib import Path
from xml.sax.saxutils import escape

import pytest

from conftest import prepare_guest_for_test

from swarmbly_app.inference.base import GenerationResult
from swarmbly_app.sandbox import available
from test_api_lce import make_client


def _status() -> dict:
    return {
        "available": True, "reason": "", "platform_guard": "rlimit+watchdog",
        "watchdog_only": False,
        "limits": {"deadline_s": 10.0, "memory_mib": 256, "output_mib": 4,
                   "max_out_mib": 256, "max_out_files": 10000},
        "max_corrections": 2,
    }


def _as_available(monkeypatch, app_state) -> None:
    monkeypatch.setattr(app_state.chat, "code_status", lambda: _status())


class FakeScript:
    name = "fake"

    def __init__(self) -> None:
        self.prompts: list[str] = []
        self.reply = "```python\nprint('ok')\n```"

    def available(self) -> bool:
        return True

    def list_models(self) -> list[str]:
        return ["fake-model:1b"]

    def stream_chat(self, messages, *, model, max_tokens=1024, temperature=0.2,
                    on_delta=None, interrupt=None, system=None, **kw):
        self.prompts.append("\n".join(str(m.get("content", "")) for m in messages))
        return GenerationResult(text=self.reply, model=model,
                                completion_tokens=2, total_ms=1)


def _col(index: int) -> str:
    return chr(ord("A") + index)


def _sheet_xml(rows: list[list[object]]) -> str:
    cells = []
    for r, row in enumerate(rows, start=1):
        parts = []
        for c, value in enumerate(row):
            ref = f"{_col(c)}{r}"
            if isinstance(value, str):
                parts.append(f'<c r="{ref}" t="inlineStr"><is><t>{escape(value)}</t></is></c>')
            else:
                parts.append(f'<c r="{ref}"><v>{value}</v></c>')
        cells.append(f'<row r="{r}">' + "".join(parts) + "</row>")
    return ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
            "<sheetData>" + "".join(cells) + "</sheetData></worksheet>")


def write_xlsx(path: Path, sheets: dict[str, list[list[object]]]) -> None:
    """A minimal multi-sheet .xlsx written with the standard library."""
    names = list(sheets)
    content_types = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
        + "".join(
            f'<Override PartName="/xl/worksheets/sheet{i}.xml" '
            'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
            for i in range(1, len(names) + 1)) +
        "</Types>")
    rels = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>'
        "</Relationships>")
    workbook = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
        "<sheets>" + "".join(
            f'<sheet name="{escape(name)}" sheetId="{i}" r:id="rId{i}"/>'
            for i, name in enumerate(names, 1)) + "</sheets></workbook>")
    workbook_rels = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        + "".join(
            f'<Relationship Id="rId{i}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet{i}.xml"/>'
            for i in range(1, len(names) + 1)) +
        "</Relationships>")
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", content_types)
        archive.writestr("_rels/.rels", rels)
        archive.writestr("xl/workbook.xml", workbook)
        archive.writestr("xl/_rels/workbook.xml.rels", workbook_rels)
        for i, name in enumerate(names, 1):
            archive.writestr(f"xl/worksheets/sheet{i}.xml", _sheet_xml(sheets[name]))


def _project(app_state, tmp_path: Path):
    project = app_state.projects.create("Spreadsheet", parent=tmp_path / "p")
    sheet1 = [["hive", "apiary", "weight"]]
    sheet2 = [["site", "ph"]]
    for i in range(1, 9):
        sheet1.append([f"H{i}", f"A{i % 2}", 100 + i])
        sheet2.append([f"S{i}", 5 + i / 10])
    # Sentinel values that must never reach the model.
    sheet1[6][2] = "SENTINEL-SHEET1-6"
    sheet1[7][2] = "SENTINEL-SHEET1-7"
    sheet2[6][1] = "SENTINEL-SHEET2-6"
    write_xlsx(project.sources / "produccion.xlsx",
               {"Sheet1": sheet1, "Sheet2": sheet2})
    (project.sources / "produccion.tsv").write_text(
        "hive\tapiary\tweight\n" + "".join(
            f"H{i}\tA{i % 2}\t{100 + i}\n" for i in range(1, 9)),
        encoding="utf-8")
    return project


def _names(client, project) -> list[str]:
    response = client.get(f"/api/recipes/code/sources?project_id={project.id}")
    assert response.status_code == 200, response.text
    return [item["rel"] for item in response.json()]


def test_listing_includes_spreadsheets_and_tsv(app_state, tmp_path):
    project = _project(app_state, tmp_path)
    client = make_client(app_state)
    names = _names(client, project)
    assert "produccion.xlsx" in names
    assert "produccion.tsv" in names


def test_xlsx_proposal_sends_only_header_and_five_rows_per_sheet(
        app_state, tmp_path, monkeypatch):
    _as_available(monkeypatch, app_state)
    project = _project(app_state, tmp_path)
    fake = FakeScript()
    app_state.backends.resolve = lambda config=None: fake  # type: ignore[method-assign]
    client = make_client(app_state)
    response = client.post("/api/recipes/code/propose", json={
        "project_id": project.id, "question": "average weight per apiary",
        "files": ["produccion.xlsx"]})
    assert response.status_code == 200, response.text
    assert response.json()["files"] == [{"name": "produccion.xlsx",
                                         "rel": "produccion.xlsx"}]
    prompt = fake.prompts[-1]
    assert "Columns: hive | apiary | weight" in prompt
    assert "Columns: site | ph" in prompt
    assert "TABLE: Sheet1" in prompt and "TABLE: Sheet2" in prompt
    for row in range(1, 6):
        assert f"ROW {row}:" in prompt
    assert "ROW 6:" not in prompt
    assert "SENTINEL-SHEET1-6" not in prompt
    assert "SENTINEL-SHEET1-7" not in prompt
    assert "SENTINEL-SHEET2-6" not in prompt


def test_tsv_proposal_uses_the_same_sample_limit(app_state, tmp_path, monkeypatch):
    _as_available(monkeypatch, app_state)
    project = _project(app_state, tmp_path)
    (project.sources / "produccion.tsv").write_text(
        "hive\tapiary\tweight\n" + "".join(
            f"H{i}\tA{i % 2}\t" + ("SENTINEL-TSV-6" if i == 6 else str(100 + i)) + "\n"
            for i in range(1, 9)), encoding="utf-8")
    fake = FakeScript()
    app_state.backends.resolve = lambda config=None: fake  # type: ignore[method-assign]
    client = make_client(app_state)
    response = client.post("/api/recipes/code/propose", json={
        "project_id": project.id, "question": "average weight",
        "files": ["produccion.tsv"]})
    assert response.status_code == 200, response.text
    prompt = fake.prompts[-1]
    assert "Columns: hive | apiary | weight" in prompt
    assert "ROW 5:" in prompt and "ROW 6:" not in prompt
    assert "SENTINEL-TSV-6" not in prompt


def test_symlinked_xlsx_is_refused(app_state, tmp_path, monkeypatch):
    _as_available(monkeypatch, app_state)
    project = _project(app_state, tmp_path)
    outside = tmp_path / "outside.xlsx"
    write_xlsx(outside, {"Sheet1": [["secret"], ["SENTINEL"]]})
    link = project.sources / "linked.xlsx"
    try:
        link.symlink_to(outside)
    except OSError:
        pytest.skip("this platform cannot create a test symlink")
    fake = FakeScript()
    app_state.backends.resolve = lambda config=None: fake  # type: ignore[method-assign]
    client = make_client(app_state)
    assert "linked.xlsx" not in _names(client, project)
    response = client.post("/api/recipes/code/propose", json={
        "project_id": project.id, "question": "q", "files": ["linked.xlsx"]})
    assert response.status_code == 400
    assert "not in this project's sources" in response.json()["detail"]
    assert fake.prompts == []


def test_xlsx_outside_sources_is_refused(app_state, tmp_path, monkeypatch):
    _as_available(monkeypatch, app_state)
    project = _project(app_state, tmp_path)
    outside = tmp_path / "outside.xlsx"
    write_xlsx(outside, {"Sheet1": [["secret"], ["SENTINEL"]]})
    fake = FakeScript()
    app_state.backends.resolve = lambda config=None: fake  # type: ignore[method-assign]
    client = make_client(app_state)
    for ref in ("../outside.xlsx", str(outside)):
        response = client.post("/api/recipes/code/propose", json={
            "project_id": project.id, "question": "q", "files": [ref]})
        assert response.status_code == 400
        assert "not in this project's sources" in response.json()["detail"]
    assert fake.prompts == []


def test_file_over_the_size_cap_is_refused(app_state, tmp_path, monkeypatch):
    _as_available(monkeypatch, app_state)
    app_state.config.update({"recipes": {"code_max_file_bytes": 100}})
    project = _project(app_state, tmp_path)
    client = make_client(app_state)
    listing = client.get(f"/api/recipes/code/sources?project_id={project.id}").json()
    xlsx = next(item for item in listing if item["rel"] == "produccion.xlsx")
    assert xlsx["too_large"] is True
    fake = FakeScript()
    app_state.backends.resolve = lambda config=None: fake  # type: ignore[method-assign]
    response = client.post("/api/recipes/code/propose", json={
        "project_id": project.id, "question": "q", "files": ["produccion.xlsx"]})
    assert response.status_code == 400
    assert "byte limit" in response.json()["detail"]
    assert fake.prompts == []


@pytest.mark.sandbox
@pytest.mark.skipif(not available()[0], reason="the [sandbox] extra is not installed")
def test_xlsx_script_runs_in_the_sandbox(app_state, tmp_path, monkeypatch):
    project = _project(app_state, tmp_path)
    fake = FakeScript()
    fake.reply = ("```python\n"
                  "import pandas as pd\n"
                  "df = pd.read_excel('/data/produccion.xlsx', sheet_name='Sheet1')\n"
                  "print(len(df))\n"
                  "```")
    app_state.backends.resolve = lambda config=None: fake  # type: ignore[method-assign]
    # R-005: prepare the real guest cache before recipe 5 is offered.
    prepare_guest_for_test(app_state)
    client = make_client(app_state)
    proposal = client.post("/api/recipes/code/propose", json={
        "project_id": project.id, "question": "how many rows",
        "files": ["produccion.xlsx"]}).json()
    try:
        approved = client.post("/api/recipes/code/approve",
                               json={"proposal_id": proposal["proposal_id"]})
        assert approved.status_code == 200, approved.text
        message = approved.json()["assistant_message"]
        assert message["meta"]["code"]["trapped"] is None
        assert "8" in message["content"]
    finally:
        if app_state.chat._code_runner is not None:
            app_state.chat._code_runner.close()
