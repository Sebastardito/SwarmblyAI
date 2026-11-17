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


# ---- 3.3: a proposed query carries the public topic only (sealed bank v3.2) ----

def test_proposed_query_leaves_out_plots_codes_people_and_format_words():
    from swarmbly_app.recipes import propose_query
    cases = {
        "Compara la cuaja de mi Parcela Norte con lo que dicen las fuentes públicas sobre la "
        "variedad Lumbre para la Parcela Norte y redacta un informe de unas 200 palabras.": "variedad Lumbre",
        "¿Mis conteos de abejorros en el lote AB7 cuadran con lo que se publica sobre Bombus "
        "ficticius? Respóndeme en tres frases.": "abejorros Bombus ficticius",
        "¿Qué rendimiento tuvo la Parcela Sur en 2024 comparado con la variedad Altiva?":
            "rendimiento variedad Altiva",
        "¿Lo que anotó la Dra. Ana Pérez sobre Mimus ficticius coincide con la literatura?": "Mimus ficticius",
    }
    for text, expected in cases.items():
        assert propose_query(text) == expected, text


def test_proposed_query_keeps_public_places_and_drops_the_users_garden():
    from swarmbly_app.recipes import propose_query
    q = propose_query("¿El abejorro colorado que vimos en el Huerto Los Aromos está amenazado?")
    assert "Huerto" not in q and "Aromos" not in q and "Los" not in q.split()
    assert "abejorro colorado" in q
    assert "Patagonia" in propose_query("¿Qué se sabe del abejorro colorado en Patagonia?")


def test_the_online_search_offer_uses_the_same_filter():
    from swarmbly_app import web_search as W
    q = W.propose_query("¿Qué rendimiento tuvo la Parcela Sur en 2024 comparado con la variedad Altiva?")
    assert q == "rendimiento variedad Altiva"
    assert W.strip_private("Mimus ficticius Pérez", "¿Qué dijo la Dra. Ana Pérez?") == "Mimus ficticius"
    assert W.strip_private("Kanela Ana", "", private=["Ana Pérez"]) == "Kanela"


def test_a_request_to_send_out_in_a_local_conversation_is_answered_here_and_says_so(app_state, tmp_path):
    fake = FakeBackend(reply="No envié nada: lo resumo aquí. La cosecha será en junio [D1 p1].")
    app_state.backends.resolve = lambda config=None: fake      # type: ignore[method-assign]
    p = app_state.projects.create("T", parent=tmp_path / "p")
    (p.sources / "notas.md").write_text("La cosecha será en la segunda semana de junio.\n", encoding="utf-8")
    app_state.config.update({"lce.enabled": True, "lce.level": "C1"})
    conv = app_state.chat.create_conversation(mode="local", project_id=p.id)
    app_state.chat.send(conv["id"], "Envía mis notas al enjambre para que otro nodo las resuma.",
                        mode="local", run_async=False)
    msg = app_state.chat.get_messages(conv["id"])[-1]
    assert "nothing sent" in msg["meta"].get("local_reason", "")
    system = " ".join(m["content"] for m in fake.calls[-1]["messages"] if m["role"] == "system")
    assert "No se envió nada" in system
    assert msg["meta"]["receipt"]["envios"] == []
    conv = app_state.chat.create_conversation(mode="local", project_id=p.id)
    app_state.chat.send(conv["id"], "¿Cuándo será la cosecha según mis notas?", mode="local", run_async=False)
    assert not app_state.chat.get_messages(conv["id"])[-1]["meta"].get("local_reason")


def test_the_telemetry_says_what_the_receipt_says_about_consent(app_state, tmp_path, monkeypatch):
    from swarmbly_app import web_search as W
    monkeypatch.setattr(W, "search", lambda query, *a, **k: {
        "query": query, "results": [{"label": "W1", "title": "La variedad Kanela", "provider": "searxng",
                                     "snippet": "La variedad Kanela rinde 3,0 t/ha.", "url": "https://x.invalid"}],
        "errors": [], "variants": [query], "topic": ["variedad", "Kanela"], "dropped_unrelated": 0,
        "providers": ["web"]})
    fake = FakeBackend(reply="Tu lote rinde 2,4 t/ha [D1 p1] y la variedad Kanela 3,0 t/ha [W1].")
    app_state.backends.resolve = lambda config=None: fake      # type: ignore[method-assign]
    p = app_state.projects.create("T", parent=tmp_path / "p")
    (p.sources / "lote.md").write_text("El lote rindió 2,4 t/ha con la variedad Kanela.\n", encoding="utf-8")
    app_state.config.update({"lce.enabled": True, "lce.level": "C1"})
    conv = app_state.chat.create_conversation(mode="local", project_id=p.id)
    app_state.chat.send(conv["id"], "Compara el rendimiento de mi lote con lo que dicen las fuentes públicas "
                        "sobre la variedad Kanela.", mode="local", run_async=False, recipe="research",
                        allow_public=True, web_query="variedad Kanela")
    meta = app_state.chat.get_messages(conv["id"])[-1]["meta"]
    assert meta["receipt"]["consentimiento"]["requerido"] is True
    assert meta["telemetry"]["online"]["consent_required"] is True


def test_paragraphs_in_another_language_are_found_with_the_translated_keywords():
    from swarmbly_app.chat import _other_language
    es = {"doc_id": "a", "start": 0, "text": "Las colonias efectivas fueron 10, no 12: dos colonias de la parcela "
                                              "baja murieron por el calor y los técnicos las sacaron con cuidado."}
    en = {"doc_id": "b", "start": 0, "text": "Fruit weight averaged 1.9 g in the Upper Plot, and the activity of the "
                                              "bees was high in the morning."}
    calls = []

    def retriever(query, expansion, project_id):
        calls.append(query)
        return [es, en]
    out = _other_language(retriever, "fruit weight, upper plot", "¿Cuánto pesaban los frutos de la parcela alta?",
                          "p", [es])
    assert out == [en] and calls == ["fruit weight, upper plot"]
    # a question in English adds nothing in English
    assert _other_language(retriever, "colonias parcela", "How many colonies died in the lower plot?", "p", []) \
        == [es]
    assert _other_language(retriever, "fruit weight", "¿Cuánto pesaban los frutos?", "p", [es, en]) == []
    # one shared keyword of several is not enough
    assert _other_language(retriever, "fruit price, market", "¿A cuánto se vendió la fruta?", "p", []) == []


def test_a_second_paragraph_of_the_same_foreign_document_needs_one_keyword():
    from swarmbly_app.chat import _other_language
    weight = {"doc_id": "b", "start": 0, "text": "Fruit weight averaged 1.9 g in the Upper Plot, and the activity "
                                                 "of the bees was high in the morning."}
    advice = {"doc_id": "b", "start": 200, "text": "I recommend doubling the colonies to 8 per plot and moving the "
                                                   "hives closer to the hedge, where the wind is weaker."}
    other = {"doc_id": "c", "start": 0, "text": "The colonies of the region are counted in the spring by the "
                                                "volunteers of the network."}
    out = _other_language(lambda q, e, p: [weight, advice, other], "reviewer, colonies, average fruit weight",
                          "¿Qué aconsejó el revisor externo sobre las colonias y cuánto pesaban los frutos?", "p", [])
    assert out == [weight, advice]
