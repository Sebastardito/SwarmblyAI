"""T10.17: one short passage must be found even with few shared words.

The open set in ``tests/fixtures/retrieval`` uses neutral field notes. The
App controls only the query it hands to LCE: glossary equivalents and regular
inflections are added there, without changing LCE's ranking.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

from swarmbly_app.inference.base import GenerationResult

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "retrieval"


class Capture:
    name = "fake"

    def __init__(self):
        self.calls: list[list[dict]] = []

    def available(self) -> bool:
        return True

    def list_models(self) -> list[str]:
        return ["fake-model:1b"]

    def stream_chat(self, messages, *, model, max_tokens=1024, temperature=0.2,
                    on_delta=None, interrupt=None, system=None, **kw):
        self.calls.append([dict(message) for message in messages])
        return GenerationResult(text="Según el registro, el dato está en el pasaje.",
                                model=model, completion_tokens=8, total_ms=1)


def _cases() -> list[dict]:
    return json.loads((FIXTURES / "cases.json").read_text(encoding="utf-8"))


def test_retrieval_terms_include_glossary_and_inflections():
    from swarmbly_app.local_context import retrieval_terms

    terms = retrieval_terms("¿Cuánto pesaron los frutos?", "", [])
    assert "peso" in terms and "fruta" in terms

    terms = retrieval_terms("¿Cuánto se recolectó en el terreno elevado?", "",
                            [("terreno", "finca, plot"), ("elevado", "alta")])
    assert "finca" in terms and "alta" in terms


def test_each_open_case_reaches_the_model_with_its_passage(app_state, tmp_path):
    project = app_state.projects.create("Retrieval open set", parent=tmp_path / "p")
    for source in FIXTURES.glob("*.md"):
        shutil.copyfile(source, project.sources / source.name)
    app_state.config.update({
        "evidence.enabled": False, "compose.verify": False,
        "lce": {"enabled": True, "level": "C1", "dense_retrieval": False,
                "query_expansion": False},
    })
    app_state.chat.retriever = lambda query, expansion="", project_id="": (
        app_state.lce.retrieve(query, k=6, expansion=expansion,
                               roots=app_state.c1_roots(project_id)))
    app_state.chat.retrieval_active = lambda project_id="": True
    fake = Capture()
    app_state.backends.resolve = lambda config=None: fake

    for case in _cases():
        glob = [tuple(pair) for pair in case["glossary"]]
        app_state.chat.glossary_entries = lambda project_id="", pairs=glob: list(pairs)
        conv = app_state.chat.create_conversation(mode="local", project_id=project.id)
        app_state.chat.send(conv["id"], case["question"], run_async=False)
        prompt = "\n".join(str(m.get("content", "")) for m in fake.calls[-1])
        assert case["expected"] in prompt, (case["id"], prompt[:1200])
        message = app_state.chat.get_messages(conv["id"])[-1]
        assert message["meta"]["status"] == "done"
        assert message["meta"]["lce"]["sources"], case["id"]
