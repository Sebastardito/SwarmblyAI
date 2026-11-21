"""Recipe 4: process a list on the swarm (3.4)."""

from __future__ import annotations

import re
import time

import pytest
from fastapi.testclient import TestClient

from swarmbly_app import egress
from swarmbly_app import recipes
from swarmbly_app.config import ConfigError, validate_changes
from swarmbly_app.inference.base import GenerationResult
from swarmbly_app.recipes import (ListJobError, MAX_ITEM_CHARS, build_list_prompt,
                                   duplicate_rows, item_match_terms, list_wave_size,
                                   normalise_list_job, passage_matches_item, preview_list,
                                   read_csv_column, relevant_list_passages)
from tests.conftest import FakeBackend
from tests.test_p2p_two_nodes import connect, make_node


def _job(items, operation="Give the status of this item", where="local", source=None):
    return normalise_list_job({"items": items, "operation": operation, "where": where,
                               "source": source or {"kind": "pasted"}}, max_items=200)


# --- validation and CSV ---------------------------------------------------------------

def test_validation_limits_and_empty_items():
    with pytest.raises(ListJobError, match="no items"):
        normalise_list_job({"items": "\n\n", "operation": "x"})
    with pytest.raises(ListJobError, match="maximum"):
        normalise_list_job({"items": ["a", "b", "c"], "operation": "x"}, max_items=2)
    with pytest.raises(ListJobError, match="longer than"):
        normalise_list_job({"items": "x" * (MAX_ITEM_CHARS + 1), "operation": "x"})
    with pytest.raises(ListJobError, match="operation is empty"):
        normalise_list_job({"items": ["a"], "operation": " "})
    with pytest.raises(ListJobError, match="where"):
        normalise_list_job({"items": ["a"], "operation": "x", "where": "somewhere"})


def test_duplicates_are_kept_and_marked():
    items = ["Lontra felina", "Puma concolor", "lontra FELINA"]
    assert duplicate_rows(items) == [{"n": 3, "of": 1}]
    job = _job(items)
    assert job.items == items
    preview = preview_list(job, cfg={"privacy": {"tier": "GLOBAL"}, "swarm": {}},
                           nodes_available=0)
    assert preview["count"] == 3 and preview["duplicates"] == 1


def test_csv_multiline_quoted_fields_and_missing_column(tmp_path):
    path = tmp_path / "species.csv"
    path.write_text('name,status\n"Lontra\nfelina",NT\n"Puma concolor",LC\n',
                    encoding="utf-8")
    assert read_csv_column(path, "name", 200) == ["Lontra felina", "Puma concolor"]
    with pytest.raises(ListJobError, match="no column"):
        read_csv_column(path, "missing", 200)
    with pytest.raises(ListJobError, match="more than 1"):
        read_csv_column(path, "name", 1)


def test_csv_is_resolved_inside_project_sources(app_state, tmp_path):
    project = app_state.projects.create("CSV project", parent=tmp_path / "projects")
    (project.sources / "species.csv").write_text(
        "name,status\nLontra felina,NT\nPuma concolor,LC\n", encoding="utf-8")
    job = normalise_list_job({
        "items": "", "operation": "Give the IUCN status", "where": "local",
        "source": {"kind": "csv", "file": "species.csv", "column": "name"}},
        max_items=200, roots=[project.sources])
    assert job.items == ["Lontra felina", "Puma concolor"]
    with pytest.raises(ListJobError, match="not in the project's sources"):
        normalise_list_job({
            "items": "", "operation": "Give the IUCN status", "where": "local",
            "source": {"kind": "csv", "file": "../outside.csv", "column": "name"}},
            max_items=200, roots=[project.sources])


def test_config_validates_list_max_items():
    assert validate_changes({"recipes": {"list_max_items": 5}})["recipes.list_max_items"] == 5
    with pytest.raises(ConfigError):
        validate_changes({"recipes": {"list_max_items": 0}})
    with pytest.raises(ConfigError):
        validate_changes({"recipes": {"list_max_items": 5000}})


# --- preview ---------------------------------------------------------------------------

def test_preview_sends_nothing_and_shows_what_leaves():
    job = _job(["Lontra felina", "Puma concolor"], where="swarm")
    with egress.request_ledger("preview") as ledger:
        preview = preview_list(job, cfg={"privacy": {"tier": "GLOBAL"}, "swarm": {}},
                               nodes_available=2, nodes=[{"node": "abc"}])
    assert ledger.events == []
    assert preview["count"] == 2 and preview["what_leaves"]["count"] == 2
    assert preview["what_leaves"]["operation"] == "Give the status of this item"
    assert preview["what_leaves"]["items"] == job.items
    assert "Lontra felina" in preview["what_leaves"]["prompt"]
    assert preview["nodes_available"] == 2 and preview["default_where"] == "swarm"
    assert list_wave_size({"swarm": {"n_fragments_max": 4,
                                     "min_items_per_fragment": 3}}) == 12


def test_personal_items_default_to_local_even_with_nodes():
    job = _job(["my salary", "my diagnosis"], where="swarm")
    preview = preview_list(job, cfg={"privacy": {"tier": "GLOBAL"}, "swarm": {}},
                           nodes_available=2)
    assert preview["privacy"]["sensitive"] is True
    assert preview["default_where"] == "local"
    assert preview["local_only_reason"]
    assert preview["privacy"]["items_flagged"]


def test_list_prompt_is_an_enumerated_batch():
    prompt = build_list_prompt("Give the IUCN status of this species", ["a", "b", "c"])
    assert "1. a" in prompt and "3. c" in prompt
    assert "Items:" in prompt


def test_api_preview_returns_what_leaves_without_egress(app_state, monkeypatch):
    from swarmbly_app.api import create_app

    def forbidden(*args, **kwargs):
        raise AssertionError("preview must not call egress")

    monkeypatch.setattr(egress, "check_call", forbidden)
    app = create_app(app_state)
    c = TestClient(app, base_url="http://127.0.0.1:8765")
    c.headers["X-Swarmbly-Token"] = app.state.guard.token
    out = c.post("/api/recipes/list/preview", json={
        "items": "alpha\nbeta\nalpha", "operation": "Give the IUCN status",
        "where": "local", "source": {"kind": "pasted"}})
    assert out.status_code == 200, out.text
    body = out.json()
    assert body["count"] == 3 and body["duplicates"] == 1
    assert body["what_leaves"]["items"] == ["alpha", "beta", "alpha"]


def test_api_send_accepts_a_list_job(app_state):
    from swarmbly_app.api import create_app

    app_state.backends.resolve = lambda cfg=None: FakeBackend(reply="1. A")
    app = create_app(app_state)
    c = TestClient(app, base_url="http://127.0.0.1:8765")
    c.headers["X-Swarmbly-Token"] = app.state.guard.token
    conv = app_state.chat.create_conversation(mode="local")
    out = c.post(f"/api/conversations/{conv['id']}/messages", json={
        "text": "Give the status of this item", "mode": "local", "recipe": "list",
        "list_job": {"items": ["alpha"], "operation": "Give the status of this item",
                     "where": "local", "source": {"kind": "pasted"}}})
    assert out.status_code == 202, out.text
    message = None
    for _ in range(50):
        message = app_state.chat.get_messages(conv["id"])[-1]
        if message["meta"].get("status") != "running":
            break
        time.sleep(0.05)
    assert message["meta"]["status"] == "done", message["meta"]
    assert message["meta"]["table"]["rows_data"][0]["status"] == "answered"


# --- local execution -------------------------------------------------------------------

def _send_list(app_state, job, reply, items_text="list"):
    fake = FakeBackend(reply=reply)
    app_state.backends.resolve = lambda cfg=None: fake
    conv = app_state.chat.create_conversation(mode="local")
    app_state.chat.send(conv["id"], job.operation, recipe="list",
                        list_job=job.to_dict(), run_async=False)
    return app_state.chat.get_messages(conv["id"])[-1], fake


def _multi_nodes(nodes):
    return {"swarm": {"k_min": 2, "k_max": 2, "n_fragments_max": 4,
                      "min_items_per_fragment": 3, "timeout_ms": 8000,
                      "hedge_fallback_ms": 3000},
            "privacy": {"tier": "GLOBAL"}}


def test_local_run_builds_the_table_in_order_with_missing_and_duplicate(app_state):
    job = _job(["alpha", "alpha", "beta", "gamma"])
    msg, _ = _send_list(app_state, job, "1. A\n2. A\n3. B")
    table = msg["meta"]["table"]
    assert table["by_code"] is True
    assert msg["meta"]["list"]["count"] == 4
    assert msg["meta"]["list"]["answered"] == 3
    assert msg["meta"]["list"]["missing"] == 1
    assert [r["status"] for r in table["rows_data"]] == [
        "answered", "answered", "answered", "missing"]
    assert "duplicate of #1" in table["rows_data"][1]["item_cell"]
    assert table["rows_data"][3]["answer"] == "—"
    assert msg["content"].index("| 1 |") < msg["content"].index("| 2 |") < \
        msg["content"].index("| 3 |") < msg["content"].index("| 4 |")
    assert msg["meta"]["receipt"]["recipe"] == "list"
    assert msg["meta"]["receipt"]["recipe_where"] == "local"


def test_local_long_list_is_processed_in_waves(app_state):
    items = [f"item {i}" for i in range(1, 26)]
    reply = "\n".join(f"{i}. answer {i}" for i in range(1, 13))
    msg, fake = _send_list(app_state, _job(items), reply)
    assert msg["meta"]["list"]["waves"] == 3
    assert msg["meta"]["list"]["answered"] == 25
    assert len(msg["meta"]["table"]["rows_data"]) == 25
    assert msg["meta"]["table"]["rows_data"][-1]["n"] == 25
    assert len(fake.calls) == 3


# --- swarm execution -------------------------------------------------------------------

def test_swarm_run_reports_agreement_and_disagreement(tmp_path):
    worker1, _ = make_node(tmp_path, "W1", worker=True, model="llama3.2:3b",
                           reply="1. A\n2. A\n3. A")
    worker2, _ = make_node(tmp_path, "W2", worker=True, model="qwen2.5:3b",
                           reply="1. A\n2. B\n3. A")
    client, _ = make_node(tmp_path, "C", model="fake-model:1b",
                          extra=_multi_nodes(None))
    connect(client, worker1)
    connect(client, worker2)
    items = [f"item {i}" for i in range(1, 7)]
    job = _job(items, where="swarm")
    client.chat.send(client.chat.create_conversation(mode="lan")["id"],
                     job.operation, recipe="list", list_job=job.to_dict(),
                     run_async=False)
    msg = client.chat.get_messages(client.chat.list_conversations()[0]["id"])[-1]
    assert msg["meta"]["status"] == "done", msg["meta"]
    assert msg["meta"]["list"]["executed"] == "distributed", msg["meta"]["list"]
    assert msg["meta"]["list"]["where"] == "swarm"
    assert msg["meta"]["list"]["answered"] == 4
    assert msg["meta"]["list"]["disagreement"] == 2
    statuses = [r["status"] for r in msg["meta"]["table"]["rows_data"]]
    assert statuses.count("disagreement") == 2
    assert msg["meta"]["receipt"]["recipe"] == "list"
    assert msg["meta"]["receipt"]["recipe_where"] == "swarm"
    assert msg["meta"]["receipt"]["envios"], "distributed fragments must be in the receipt"
    client.stop(); worker1.stop(); worker2.stop()


# --- degenerated local waves (MX-01) ------------------------------------------

OP_ADD_SEVEN = "Suma 7 al número de cada ficha. Responde solo con el resultado."


class ItemTextBackend:
    """A fake model that answers from the item text.

    It also reproduces what qwen2.5:7b did with a whole 12-item wave: it
    answers the first item and repeats that value for every line. A prompt
    with at most six items (the per-item retry) is answered correctly; the
    single-item table prompt keeps the item's own number in the first cell.
    """

    name = "fake"

    def __init__(self):
        self.calls: list[str] = []

    def available(self) -> bool:
        return True

    def list_models(self) -> list[str]:
        return ["fake-model:1b"]

    @staticmethod
    def _answer(item: str) -> str:
        found = re.search(r"Ficha\s+(\d+)", item)
        return str(int(found.group(1)) + 7) if found else ""

    def stream_chat(self, messages, *, model, max_tokens=1024,
                    temperature=0.2, **kw):
        prompt = messages[-1]["content"]
        self.calls.append(prompt)
        items = re.findall(r"^\s*(\d+)\.\s+(.+?)\s*$", prompt, re.M)
        if not items:
            return GenerationResult(text="", model=model)
        if "tabla Markdown" in prompt or "Markdown table" in prompt:
            # the per-item retry: a table row with the item's own number
            ficha = re.search(r"Ficha\s+(\d+)", items[0][1])
            numero = ficha.group(1) if ficha else items[0][0]
            return GenerationResult(text=f"| {numero} | {self._answer(items[0][1])} |",
                                    model=model)
        if len(items) > 6:
            first = self._answer(items[0][1])
            text = "\n".join(f"{n}. {first}" for n, _ in items)
        else:
            text = "\n".join(f"{n}. {self._answer(item)}" for n, item in items)
        return GenerationResult(text=text, model=model)


def _send_list_with(app_state, job, fake):
    app_state.config.update({"model": {"model_name": "fake-model:1b"},
                             "swarm": {"n_fragments_max": 4,
                                       "min_items_per_fragment": 3}})
    app_state.backends.resolve = lambda config=None: fake
    conv = app_state.chat.create_conversation(mode="local")
    app_state.chat.send(conv["id"], job.operation, recipe="list",
                        list_job=job.to_dict(), run_async=False)
    return app_state.chat.get_messages(conv["id"])[-1], fake


def _cells(message):
    return {row["n"]: row["answer"] for row in message["meta"]["table"]["rows_data"]}


def test_a_12_item_wave_that_repeats_the_first_answer_is_retried(app_state):
    items = [f"Ficha {n}: parcela Norte." for n in range(1, 13)]
    message, fake = _send_list_with(app_state, _job(items, operation=OP_ADD_SEVEN),
                                    ItemTextBackend())
    assert message["meta"]["status"] == "done", message["meta"]
    assert _cells(message) == {n: str(n + 7) for n in range(1, 13)}
    assert message["meta"]["list"]["waves"] == 1
    assert message["meta"]["list"]["retries"] == 1
    # the first prompt carries items 1 and 2 in the same 12-item wave
    assert "1. Ficha 1: parcela Norte." in fake.calls[0]
    assert "2. Ficha 2: parcela Norte." in fake.calls[0]
    # the retry is one item per prompt, as a single-row table
    assert "tabla Markdown" in fake.calls[1]
    assert "Elemento:\n1. Ficha 1: parcela Norte." in fake.calls[1]
    assert "Elemento:\n1. Ficha 2: parcela Norte." in fake.calls[2]
    assert len(fake.calls) == 13


def test_a_13_item_list_retries_only_the_12_item_wave(app_state):
    items = [f"Ficha {n}: parcela Norte." for n in range(1, 14)]
    message, fake = _send_list_with(app_state, _job(items, operation=OP_ADD_SEVEN),
                                    ItemTextBackend())
    assert _cells(message) == {n: str(n + 7) for n in range(1, 14)}
    assert message["meta"]["list"]["waves"] == 2
    assert message["meta"]["list"]["retries"] == 1
    # 12-item wave + 12 single-item retries + 1-item second wave
    assert len(fake.calls) == 14


def test_a_single_short_wave_is_not_retried(app_state):
    items = [f"Ficha {n}: parcela Norte." for n in range(1, 5)]
    message, fake = _send_list_with(app_state, _job(items, operation=OP_ADD_SEVEN),
                                    ItemTextBackend())
    assert _cells(message) == {n: str(n + 7) for n in range(1, 5)}
    assert message["meta"]["list"]["waves"] == 1
    assert (message["meta"]["list"].get("retries") or 0) == 0
    assert len(fake.calls) == 1


def test_a_table_header_or_separator_is_not_an_item_answer():
    from swarmbly_app.engine.orchestrator import _parse_items, _parse_single_item

    header = "| # | Elemento | Respuesta |\n|---|---|---|"
    assert _parse_items(header, {1: "Ficha uno", 2: "Ficha dos"}) == {}
    assert _parse_single_item(header, "Ficha uno") == ""
    numbered = "| 1 | Item | Answer |\n|---|---|---|"
    assert _parse_items(numbered, {1: "Ficha uno"}) == {}
    assert _parse_single_item(numbered, "Ficha uno") == ""
    separator = "|---|---|---|"
    assert _parse_items(separator, {1: "Ficha uno", 2: "Ficha dos"}) == {}
    assert _parse_single_item(separator, "Ficha uno") == ""
    # A real data row still parses.
    assert _parse_items("| 1 | 9 |\n| 2 | 8 |",
                        {1: "Ficha uno", 2: "Ficha dos"}) == {1: "9", 2: "8"}


def test_item_text_echoed_with_its_own_number_is_parsed():
    from swarmbly_app.engine.orchestrator import _parse_items, _parse_single_item

    item = "Ficha 2: parcela Norte."
    assert _parse_items("1. Ficha 2: parcela Norte. 9", {1: item}) == {1: "9"}
    assert _parse_single_item("1. Ficha 9: parcela Norte.", item) == "9"
    assert _parse_single_item("| 2 | 9 |", item) == "9"


# ---- T9.12: list items read the project documents ---------------------------

def _docs_retriever(query, expansion="", project_id=""):
    """One passage per item, so the test can see which item got which fact."""
    return [{"doc_id": "d1", "source": "notas.md", "rel": "notas.md",
             "anchor": f"p{query.split()[-1]}", "text": f"SENTINEL-PASSAGE for {query}",
             "score": 0.9}]


def test_a_local_list_reads_the_documents_for_each_item(app_state, tmp_path):
    project = app_state.projects.create("List docs", parent=tmp_path / "p")
    app_state.chat.retriever = _docs_retriever          # type: ignore[assignment]
    app_state.chat.retrieval_active = lambda project_id="": True  # type: ignore[assignment]
    fake = FakeBackend(reply="1. 42\n2. 43")
    app_state.backends.resolve = lambda cfg=None: fake  # type: ignore[method-assign]
    job = _job(["Ficha 1", "Ficha 2"], operation="Di el dato de cada ficha")
    conv = app_state.chat.create_conversation(mode="local", project_id=project.id)
    app_state.chat.send(conv["id"], job.operation, recipe="list",
                        list_job=job.to_dict(), run_async=False)
    msg = app_state.chat.get_messages(conv["id"])[-1]
    prompt = fake.calls[-1]["messages"][-1]["content"]
    assert "SENTINEL-PASSAGE for Ficha 1" in prompt
    assert "SENTINEL-PASSAGE for Ficha 2" in prompt
    assert prompt.index("SENTINEL-PASSAGE for Ficha 1") < prompt.index("2. Ficha 2")
    assert msg["meta"]["list"]["documents_used"] is True
    assert msg["meta"]["list"]["documents_withheld"] is False
    assert [row["answer"] for row in msg["meta"]["table"]["rows_data"]] == ["42", "43"]


class _CapturingSwarm:
    def __init__(self):
        self.prompts: list[str] = []

    def run(self, prompt, *, mode="lan", request_id=None, cancel=None,
            history=None, passage_texts=None, passage_peer_ids=None):
        self.prompts.append(str(prompt))
        items = re.findall(r"^\s*(\d+)\.\s+(.+)$", prompt, re.M)
        text = "\n".join(f"{n}. answer {n}" for n, _ in items)
        passages = sum(1 for text in (passage_texts or []) if text in str(prompt))
        return {"routed": "distributed", "text": text,
                "metadata": {"n_tasks": 1,
                             "attempts": [{"node": "W1", "task": "t0",
                                           "bytes_out": len(prompt),
                                           "passages": passages}]},
                "stages": []}


def _send_swarm_list(app_state, tmp_path, monkeypatch, passages: bool):
    project = app_state.projects.create("Swarm docs", parent=tmp_path / "p")
    app_state.chat.retriever = _docs_retriever          # type: ignore[assignment]
    app_state.chat.retrieval_active = lambda project_id="": True  # type: ignore[assignment]
    swarm = _CapturingSwarm()
    app_state.chat.orchestrator = lambda: swarm          # type: ignore[assignment]
    # D-017: recipe 4 in my-own-devices mode uses its own switch; the old
    # privacy.third_party_passages (model services) is left off on purpose.
    app_state.config.update({"circle": {"admission_mode": "own_devices",
                                         "own_devices_passages": passages},
                             "privacy": {"third_party_passages": False}})
    job = _job(["alpha", "beta"], operation="Give the status of this item",
               where="swarm")
    conv = app_state.chat.create_conversation(mode="lan", project_id=project.id)
    app_state.chat.send(conv["id"], job.operation, recipe="list",
                        list_job=job.to_dict(), run_async=False)
    msg = app_state.chat.get_messages(conv["id"])[-1]
    return swarm, msg


def test_the_swarm_list_without_permission_does_not_send_the_documents(
        app_state, tmp_path, monkeypatch):
    swarm, msg = _send_swarm_list(app_state, tmp_path, monkeypatch, passages=False)
    assert swarm.prompts and "SENTINEL-PASSAGE" not in swarm.prompts[0]
    assert msg["meta"]["list"]["documents_used"] is False
    assert msg["meta"]["list"]["documents_withheld"] is True
    assert "not used" in msg["content"].lower()
    assert "SENTINEL-PASSAGE" not in msg["content"]


def test_the_swarm_list_with_permission_sends_the_documents(
        app_state, tmp_path, monkeypatch):
    swarm, msg = _send_swarm_list(app_state, tmp_path, monkeypatch, passages=True)
    assert "SENTINEL-PASSAGE for alpha" in swarm.prompts[0]
    assert "SENTINEL-PASSAGE for beta" in swarm.prompts[0]
    assert msg["meta"]["list"]["documents_used"] is True
    assert msg["meta"]["list"]["documents_withheld"] is False
    # the receipt lists the passages per destination, not only a total
    sends = msg["meta"]["receipt"]["envios"]
    assert sends and sends[0].get("pasajes") == 2
    assert msg["meta"]["receipt"]["pasajes_enviados"] == 2


def test_third_party_passages_does_not_enable_the_swarm_switches(
        app_state, tmp_path, monkeypatch):
    project = app_state.projects.create("Old flag", parent=tmp_path / "p")
    app_state.chat.retriever = _docs_retriever          # type: ignore[assignment]
    app_state.chat.retrieval_active = lambda project_id="": True  # type: ignore[assignment]
    swarm = _CapturingSwarm()
    app_state.chat.orchestrator = lambda: swarm          # type: ignore[assignment]
    # Migration: an existing third_party_passages=true must not silently turn
    # on passages to peers (neither circle nor my-own-devices).
    app_state.config.update({"circle": {"admission_mode": "own_devices",
                                         "own_devices_passages": False},
                             "privacy": {"third_party_passages": True}})
    job = _job(["alpha", "beta"], operation="Give the status of this item",
               where="swarm")
    conv = app_state.chat.create_conversation(mode="lan", project_id=project.id)
    app_state.chat.send(conv["id"], job.operation, recipe="list",
                        list_job=job.to_dict(), run_async=False)
    msg = app_state.chat.get_messages(conv["id"])[-1]
    assert swarm.prompts and "SENTINEL-PASSAGE" not in swarm.prompts[0]
    assert msg["meta"]["list"]["documents_used"] is False
    assert msg["meta"]["list"]["documents_withheld"] is True

# ---- T9.15: a passage belongs to an item only when the item points at it ----

def test_a_row_of_lotes_csv_is_not_about_a_plot_record():
    row = {"text": "| lote | region | cantidad |\n|---|---|---|\n"
                   "| Aliso | Norte | 3 |"}
    # "Norte" and "parcela" are ordinary place words, not the item's identity
    assert not passage_matches_item(
        "Ficha de la parcela Norte; código: PN-204; responsable: equipo de campo.", row)
    assert not passage_matches_item("Ficha 14: muestra de suelo.", row)
    # a long record does not match a table by one incidental lot name
    assert not passage_matches_item(
        "Ficha 31; código: LN-410; lote: Aliso.", row)
    # its key does
    assert passage_matches_item("Aliso", row)


def test_short_codes_are_matched_exactly_and_word_bounded():
    glossary = {"text": "**QA** = Quilén Alto. Estación aguas arriba.\n"
                        "**QM** = Quilén Medio."}
    assert passage_matches_item("QA", glossary)
    assert not passage_matches_item("QB", glossary)
    # a prefix of a longer sensor code is a different token
    assert not passage_matches_item("QA", {"text": "Registro 1: sensor QA-01, caudal."})
    assert item_match_terms("QA") == (["qa"], [])
    assert item_match_terms("Lote Arrayán") == ([], ["arrayan"])


def test_prose_wins_over_a_table_row_and_the_cap_is_small():
    table = {"doc_id": "csv", "anchor": "p1", "score": 9.0,
             "text": "| lote | region |\n|---|---|\n| Aliso | Norte |"}
    prose = {"doc_id": "md", "anchor": "p1", "score": 0.0,
             "text": "Aliso fue el primer lote plantado."}
    other = {"doc_id": "md", "anchor": "p2", "score": 0.0,
             "text": "El lote Aliso se cosechó en marzo."}
    found = relevant_list_passages("Aliso", [table, prose, other])
    assert found == [prose, other]                    # no table, at most two
    assert relevant_list_passages("Lote Boldo", [table, prose]) == []


def test_the_whole_station_name_beats_a_shared_river_name():
    alto = {"doc_id": "report", "anchor": "p1",
            "text": "## Quilén Alto (QA)\nLa estación QA se ubica aguas arriba."}
    medio = {"doc_id": "report", "anchor": "p2",
             "text": "## Quilén Medio (QM)\nLa estación QM está en la junta."}
    csv = {"doc_id": "csv", "anchor": "p1",
           "text": "| estacion | caudal |\n|---|---|\n| Quilén Alto | 4,2 |"}
    assert relevant_list_passages("Quilén Alto", [medio, csv, alto]) == [alto]


def test_the_glossary_is_read_for_a_short_code(app_state, tmp_path):
    project = app_state.projects.create("Codes", parent=tmp_path / "p")
    (project.sources / "glosario.md").write_text(
        "**QA** = Quilén Alto. Estación aguas arriba.\n"
        "**QM** = Quilén Medio. Estación en la junta.\n"
        "**QB** = Quilén Bajo. Estación de cierre.\n", encoding="utf-8")
    app_state.chat.retriever = lambda query, expansion="", project_id="": []  # type: ignore[assignment]
    app_state.chat.retrieval_active = lambda project_id="": True  # type: ignore[assignment]
    fake = FakeBackend(reply="1. Quilén Alto\n2. Quilén Medio\n3. Quilén Bajo")
    app_state.backends.resolve = lambda cfg=None: fake  # type: ignore[method-assign]
    job = _job(["QA", "QM", "QB"], operation="Para cada código, dime el nombre completo "
                                             "de la estación según el glosario.")
    conv = app_state.chat.create_conversation(mode="local", project_id=project.id)
    app_state.chat.send(conv["id"], job.operation, recipe="list",
                        list_job=job.to_dict(), run_async=False)
    msg = app_state.chat.get_messages(conv["id"])[-1]
    prompt = fake.calls[-1]["messages"][-1]["content"]
    assert "QA = Quilén Alto" in prompt and "QB = Quilén Bajo" in prompt
    assert msg["meta"]["list"]["documents_used"] is True
    assert msg["meta"]["list"]["documents_available"] is True


def test_a_csv_column_does_not_get_its_own_row_back(app_state, tmp_path):
    project = app_state.projects.create("Own rows", parent=tmp_path / "p")
    csv = project.sources / "lotes.csv"
    csv.write_text("lote,region,cantidad\nAliso,Norte,3\nLingue,Este,2\n",
                   encoding="utf-8")
    row = {"doc_id": "csv", "source": "lotes.csv", "rel": "lotes.csv", "anchor": "p1",
           "score": 9.0, "text": "| lote | region | cantidad |\n|---|---|---|\n"
                                  "| Aliso | Norte | 3 |"}
    app_state.chat.retriever = lambda query, expansion="", project_id="": [row]  # type: ignore[assignment]
    app_state.chat.retrieval_active = lambda project_id="": True  # type: ignore[assignment]
    fake = FakeBackend(reply="1. 5\n2. 6")
    app_state.backends.resolve = lambda cfg=None: fake  # type: ignore[method-assign]
    operation = "Escribe el número de letras de cada nombre de lote."
    job = normalise_list_job({
        "items": "", "operation": operation, "where": "local",
        "source": {"kind": "csv", "file": "lotes.csv", "column": "lote"}},
        max_items=200, roots=[project.sources])
    conv = app_state.chat.create_conversation(mode="local", project_id=project.id)
    app_state.chat.send(conv["id"], operation, recipe="list",
                        list_job=job.to_dict(), run_async=False)
    msg = app_state.chat.get_messages(conv["id"])[-1]
    prompt = fake.calls[-1]["messages"][-1]["content"]
    assert prompt == build_list_prompt(operation, job.items)
    assert msg["meta"]["list"]["documents_used"] is False
    # an operation that asks for the table keeps it
    assert app_state.chat._list_redundant(row, job.source, "cuenta las filas del CSV") is False


def test_an_item_without_a_relevant_passage_gets_the_old_prompt(app_state, tmp_path):
    project = app_state.projects.create("Rows", parent=tmp_path / "p")
    (project.sources / "lotes.csv").write_text(
        "lote,region,cantidad\nAliso,Norte,3\nCanelo,Sur,5\n", encoding="utf-8")
    row = {"doc_id": "csv", "source": "lotes.csv", "rel": "lotes.csv", "anchor": "p1",
           "score": 9.0, "text": "| lote | region | cantidad |\n|---|---|---|\n"
                                  "| Aliso | Norte | 3 |"}
    app_state.chat.retriever = lambda query, expansion="", project_id="": [row]  # type: ignore[assignment]
    app_state.chat.retrieval_active = lambda project_id="": True  # type: ignore[assignment]
    fake = FakeBackend(reply="1. LN-410")
    app_state.backends.resolve = lambda cfg=None: fake  # type: ignore[method-assign]
    item = "Ficha 31; código: LN-410; lote: Aliso."
    job = _job([item], operation="Extrae solo el código que sigue a «código:».")
    conv = app_state.chat.create_conversation(mode="local", project_id=project.id)
    app_state.chat.send(conv["id"], job.operation, recipe="list",
                        list_job=job.to_dict(), run_async=False)
    msg = app_state.chat.get_messages(conv["id"])[-1]
    prompt = fake.calls[-1]["messages"][-1]["content"]
    assert prompt == build_list_prompt(job.operation, [item], lang="es")
    assert "lotes.csv" not in prompt and "| lote |" not in prompt
    assert msg["meta"]["list"]["documents_used"] is False
    assert msg["meta"]["list"]["documents_available"] is False
