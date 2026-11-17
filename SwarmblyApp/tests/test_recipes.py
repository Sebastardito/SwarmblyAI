"""3.3: the "¿Qué quieres hacer?" entry and what each recipe turns on."""

from __future__ import annotations

from conftest import FakeBackend
from swarmbly_app import recipes as R
from test_api_lce import make_client


def test_recipes_are_listed_and_only_known_ones_run():
    assert [r["id"] for r in R.listing()] == ["documents", "table", "research", "list"]
    assert {r["id"]: r["available"] for r in R.listing()}["list"] is False
    assert R.valid("Table") == "table" and R.valid("list") == "" and R.valid("whatever") == ""


def test_the_research_query_is_proposed_before_anything_leaves(app_state, monkeypatch):
    from swarmbly_app import web_search as W
    sent = []
    monkeypatch.setattr(W, "_get", lambda *a, **k: sent.append(a) or {})
    client = make_client(app_state)
    assert [r["id"] for r in client.get("/api/recipes").json()][:3] == ["documents", "table", "research"]
    resp = client.post("/api/recipes/query", json={
        "text": "Compara el rendimiento de mi lote con lo que dicen las fuentes públicas sobre la variedad Kanela."})
    assert resp.status_code == 200
    query = resp.json()["query"]
    assert "Kanela" in query and "mi" not in query.split()
    assert sent == []                                       # a proposal, not a search
    lot = client.post("/api/recipes/query", json={"text": "Compara el rendimiento medio del lote AB2 con lo que dicen "
                                                          "las fuentes públicas sobre la variedad Altiva."}).json()
    assert lot["query"] == "variedad Altiva"                # the lot code stays home
    assert client.post("/api/recipes/query", json={"text": " "}).status_code == 400


class _Table(FakeBackend):
    """Header, then nothing for the rows (the source table is read by code), then the text."""

    def stream_chat(self, messages, *, model, max_tokens=1024, **kw):
        prompt = messages[-1]["content"]
        self.calls.append({"messages": messages, "model": model})
        from swarmbly_app.inference.base import GenerationResult
        if "fila de encabezado" in prompt:
            text = "| Sitio | pH |"
        elif "Párrafos:" in prompt[:12]:
            text = "SÍ"
        else:
            text = "El pH más alto está en la Parcela Sur [D1 p1]."
        return GenerationResult(text=text, model=model, completion_tokens=5, total_ms=1)


def test_the_table_recipe_builds_a_table_without_the_word_tabla(app_state, tmp_path):
    fake = _Table()
    app_state.backends.resolve = lambda config=None: fake      # type: ignore[method-assign]
    p = app_state.projects.create("T", parent=tmp_path / "p")
    (p.sources / "suelo.md").write_text(
        "| Sitio | pH |\n|---|---|\n| Parcela Norte | 6,8 |\n| Parcela Sur | 7,9 |\n", encoding="utf-8")
    app_state.config.update({"lce.enabled": True, "lce.level": "C1", "compose.table_by_code": False})
    question = "Compara el pH de la Parcela Norte y la Parcela Sur."
    conv = app_state.chat.create_conversation(mode="local", project_id=p.id)
    app_state.chat.send(conv["id"], question, mode="local", run_async=False)
    plain = app_state.chat.get_messages(conv["id"])[-1]
    assert "table" not in plain["meta"] and "recipe" not in plain["meta"]
    conv = app_state.chat.create_conversation(mode="local", project_id=p.id)
    app_state.chat.send(conv["id"], question, mode="local", run_async=False, recipe="table")
    msg = app_state.chat.get_messages(conv["id"])[-1]
    assert msg["meta"]["recipe"] == "table" and msg["meta"]["table"]["rows"] == 2
    assert "| Parcela Sur | 7,9 |" in msg["content"]
    # a retry keeps the recipe
    user_text = app_state.chat.get_messages(conv["id"])[-2]["content"]
    assert user_text == question
    app_state.chat.retry(conv["id"], msg["id"])
    import time
    for _ in range(100):                                    # retry answers in the background
        last = app_state.chat.get_messages(conv["id"])[-1]
        if last["meta"].get("status") not in (None, "running"):
            break
        time.sleep(0.05)
    assert last["meta"]["recipe"] == "table"


def test_the_documents_recipe_offers_no_public_lookup(app_state, tmp_path):
    fake = FakeBackend(reply="Según tus notas, la cosecha será en junio [D1 p1].")
    app_state.backends.resolve = lambda config=None: fake      # type: ignore[method-assign]
    p = app_state.projects.create("T", parent=tmp_path / "p")
    (p.sources / "notas.md").write_text("La cosecha será en la segunda semana de junio.\n", encoding="utf-8")
    app_state.config.update({"lce.enabled": True, "lce.level": "C1"})
    q = "¿Cuándo será la cosecha según mis notas? Busca referencias en línea también."
    conv = app_state.chat.create_conversation(mode="local", project_id=p.id)
    app_state.chat.send(conv["id"], q, mode="local", run_async=False)
    assert "web_offer" in app_state.chat.get_messages(conv["id"])[-1]["meta"]
    conv = app_state.chat.create_conversation(mode="local", project_id=p.id)
    app_state.chat.send(conv["id"], q, mode="local", run_async=False, recipe="documents",
                        allow_public=True, web_query="cosecha junio")
    meta = app_state.chat.get_messages(conv["id"])[-1]["meta"]
    assert meta["recipe"] == "documents" and "web_offer" not in meta and "web_search" not in meta
