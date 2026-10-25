"""Fixes from the P3d round on the five-machine network (22 October 2026)."""

from __future__ import annotations

from swarmbly_app.engine import composer
from swarmbly_app.engine.contract import build_contract
from swarmbly_app.engine.orchestrator import _normalise_items, _parse_items, _vote_items

REPORT_ES = ("Escribe un informe de unas 500 palabras sobre las ventajas y riesgos de la "
             "energía solar en zonas rurales de Ecuador, en registro profesional, con una "
             "introducción, tres secciones y una conclusión.")
CAPITALS_ES = ("Para cada uno de los siguientes países, indica solo el nombre de su "
               "capital:\n1. Ecuador\n2. Perú\n3. Chile\n4. Argentina\n5. Colombia\n"
               "6. Uruguay\n7. Paraguay\n8. Venezuela")


# -- item answers -----------------------------------------------------------------
def test_renumbered_echo_with_its_own_label_is_not_an_answer():
    """'1. 7. libro' is item 7 echoed, not a translation (accepted in P3d.1)."""
    items = {7: "libro", 8: "árbol"}
    assert _parse_items("1. 7. libro\n2. 8. tree", items) == {8: "tree"}


def test_label_followed_by_markdown_star():
    """'7.* Asunción' was shown as '7. 7.* Asunción'."""
    items = {7: "Paraguay", 8: "Venezuela"}
    assert _parse_items("7.* Asunción\n8.** Caracas", items) == {7: "Asunción",
                                                                 8: "Caracas"}


def test_decimals_are_not_taken_for_labels():
    items = {1: "1500 m", 2: "250 m"}
    assert _parse_items("1. 1.5 km\n2. 0.25 km", items) == {1: "1.5 km", 2: "0.25 km"}


def test_positional_reading_needs_unlabelled_lines():
    """A labelled echo plus a stray line must not become 'item 20 = the stray line'."""
    items = {19: "grande", 20: "pequeño"}
    assert _parse_items("19. grande - grande\n\nEn formato markdown, esto se vería así:",
                        items) == {}


def test_rejected_replica_text_is_not_shown():
    items = {19: "grande", 20: "pequeño"}
    junk = "19. grande - grande\n\nEn formato markdown, esto se vería así:\n```"
    out = _normalise_items(junk, items, "es", rejected=True)
    assert out.splitlines() == ["19. grande — (sin respuesta verificada)",
                                "20. pequeño — (sin respuesta verificada)"]
    assert _normalise_items("Todas son aves.", items, "es") == "Todas son aves."


def test_vote_marks_items_nobody_answered():
    from swarmbly_app.engine.scheduler import Replica
    items = {1: "Ecuador", 2: "Perú", 3: "Chile"}
    reps = [Replica("1. Quito\n2. Lima", "n1", "a", "a", 1),
            Replica("1. Quito\n2. Lima", "n2", "b", "b", 1)]
    text, report = _vote_items(reps, items, [0, 1], "es")
    assert text.splitlines()[-1] == "3. Chile — (sin respuesta verificada)"
    assert report["missing_items"] == [3]


# -- whole-replica selection by length ---------------------------------------------
def test_replica_near_the_section_target_wins(app_state):
    from swarmbly_v0 import HashEmbedder
    from swarmbly_app.engine.orchestrator import Orchestrator
    from swarmbly_app.engine.scheduler import Replica
    short = "Las islas Galápagos son únicas. " * 6          # 30 words
    right = "Las islas Galápagos son únicas y frágiles. " * 17   # ~119 words
    orch = Orchestrator(app_state.nodes, app_state.bus, None, app_state.config.all)
    out = orch._resolve("t1", [Replica(short, "n1", "gemma2", "g", 5),
                               Replica(right, "n2", "llama", "l", 6)],
                        build_contract(REPORT_ES).contract, HashEmbedder(),
                        policy="whole", lang="es", target_words=120)
    assert out["text"] == right
    sel = out["consensus"]["selection"]
    assert sel["target_words"] == 120 and [c["length_fits"] for c in sel["candidates"]] == [False, True]


# -- section count ------------------------------------------------------------------
def test_requested_sections():
    assert composer.requested_sections(REPORT_ES) == 5
    assert composer.requested_sections("Redacta un ensayo en tres secciones: introducción, "
                                       "desarrollo y conclusión.") == 3
    assert composer.requested_sections("Write a report in 4 sections.") == 4
    assert composer.requested_sections("Redacta un artículo de 600 palabras.") is None
    assert "Exactly 5 sections" in composer.outline_prompt(REPORT_ES, "es", 500, 6, 5)


def _outline(*specs):
    return composer.Outline("T", "energía solar", "",
                            [composer.Section(h, "x", w, kind=k) for h, w, k in specs],
                            "local_model")


def test_missing_section_is_added_before_the_closing():
    o = _outline(("Introducción", 107, "prose"), ("Ventajas", 143, "prose"),
                 ("Riesgos", 143, "prose"), ("Conclusión", 107, "prose"))
    composer._ensure_section_count(o, 5, "es", 500)
    heads = [s.heading for s in o.sections]
    assert len(heads) == 5 and heads[0] == "Introducción" and heads[-1] == "Conclusión"
    assert heads[1:3] == ["Ventajas", "Riesgos"]
    assert abs(sum(s.words for s in o.sections) - 500) <= 10
    assert o.adjustments and "5" in o.adjustments[-1]


def test_extra_sections_are_folded_and_tables_not_counted():
    o = _outline(("A", 100, "prose"), ("B", 100, "prose"), ("C", 50, "prose"),
                 ("Tabla", 120, "table"), ("D", 100, "prose"), ("E", 100, "prose"))
    composer._ensure_section_count(o, 4, "es", 500)
    assert [s.heading for s in o.sections] == ["A", "B", "Tabla", "D", "E"]
    assert "C" in o.sections[1].key_points            # folded, not lost


class _Backend:
    def __init__(self, raw):
        self.raw = raw

    def generate(self, prompt, max_tokens, temperature):
        return self.raw


def test_make_outline_honours_the_requested_count():
    import json
    raw = json.dumps({"title": "Energía solar rural", "topic": "energía solar",
                      "style": "profesional", "sections": [
                          {"heading": "Introducción", "purpose": "abre", "words": 100},
                          {"heading": "Ventajas", "purpose": "v", "words": 150},
                          {"heading": "Riesgos", "purpose": "r", "words": 150},
                          {"heading": "Conclusión", "purpose": "cierra", "words": 100}]})
    o = composer.make_outline(REPORT_ES, build_contract(REPORT_ES).contract, "es", 500,
                              _Backend(raw), 6)
    assert len(o.sections) == 5 and o.source == "local_model"


# -- local rescue without the contract header ---------------------------------------
def test_local_rescue_retries_the_bare_task(tmp_path):
    """P3d.1: the 3B model echoed a fragment wrapped in the contract and
    answered the same fragment without it."""
    from test_p2p_two_nodes import connect, make_node
    answers = ("1. Quito\n2. Lima\n3. Santiago\n4. Buenos Aires\n5. Bogotá\n"
               "6. Montevideo\n7. Asunción\n8. Caracas")
    echo = "\n".join(f"{n}. {c}" for n, c in enumerate(
        ["Ecuador", "Perú", "Chile", "Argentina", "Colombia", "Uruguay", "Paraguay",
         "Venezuela"], 1))
    worker, _ = make_node(tmp_path, "W", worker=True, reply="No lo sé.")
    client, fake = make_node(tmp_path, "C", reply=answers,
                             extra={"swarm": {"k_min": 1, "k_max": 1}})
    original = fake.stream_chat
    seen = []

    def stream_chat(messages, **kw):
        prompt = " ".join(str(m.get("content", "")) for m in messages)
        seen.append("[CONTRATO GLOBAL]" in prompt)
        fake.reply = echo if "[CONTRATO GLOBAL]" in prompt else answers
        return original(messages, **kw)

    fake.stream_chat = stream_chat
    try:
        connect(client, worker)
        conv = client.chat.create_conversation(mode="lan")
        client.chat.send(conv["id"], CAPITALS_ES, mode="lan", run_async=False)
        final = client.chat.get_messages(conv["id"])[-1]
        assert final["meta"]["status"] == "done", final["meta"]
        assert final["meta"]["swarm"]["local_fallback_tasks"]
        assert "Quito" in final["content"] and "No lo sé" not in final["content"]
        assert True in seen and False in seen         # packet first, then bare task
    finally:
        worker.stop()
        client.stop()


def test_item_texts_drop_the_upstream_suffix():
    from swarmbly_app.engine.orchestrator import _item_texts
    text = ("Convierte:\n\n7. 100 m\n8. 7000 m Close the answer; do not repeat "
            "earlier parts.")
    assert _item_texts(text) == {7: "100 m", 8: "7000 m"}


def test_unrequested_table_is_removed_and_count_kept():
    """P3e.2: the report asked for no table and got one."""
    import json
    raw = json.dumps({"title": "Energía solar rural", "topic": "energía solar",
                      "style": "profesional", "sections": [
                          {"heading": "Introducción", "purpose": "abre", "words": 60},
                          {"heading": "Ventajas", "purpose": "v", "words": 90},
                          {"heading": "Riesgos", "purpose": "r", "words": 80},
                          {"heading": "Tabla de costos", "purpose": "t", "words": 120,
                           "kind": "table", "key_points": ["costos"]},
                          {"heading": "Conclusión", "purpose": "cierra", "words": 60}]})
    o = composer.make_outline(REPORT_ES, build_contract(REPORT_ES).contract, "es", 500,
                              _Backend(raw), 6)
    assert [s.kind for s in o.sections] == ["prose"] * 5
    assert "costos" in o.sections[2].key_points
    assert any("table section removed" in a for a in o.adjustments)


def test_outside_the_band_the_closest_length_wins(app_state):
    """P3f.2: 195 and 83 words for a 144-word section; the 83 was chosen."""
    from swarmbly_v0 import HashEmbedder
    from swarmbly_app.engine.orchestrator import Orchestrator
    from swarmbly_app.engine.scheduler import Replica
    long_ = "El agua de los páramos andinos alimenta ríos y ciudades. " * 19   # ~190
    short = "El agua de los páramos andinos alimenta ríos. " * 10              # ~80
    orch = Orchestrator(app_state.nodes, app_state.bus, None, app_state.config.all)
    out = orch._resolve("t0", [Replica(short, "n1", "qwen2", "q", 5),
                               Replica(long_, "n2", "phi3", "p", 6)],
                        build_contract(REPORT_ES).contract, HashEmbedder(),
                        policy="whole", lang="es", target_words=144)
    assert out["text"] == long_


def test_item_check_explains_a_rejection():
    from swarmbly_app.engine.orchestrator import _ItemCheck
    check = _ItemCheck({19: "grande", 20: "pequeño"})
    assert not check("19. grande - grande\n20. pequeño - pequeño")
    assert check.explain("19. grande - grande\n20. small") == "items 19-20: read [20], need 1"
    assert "raw" in check.explain("19. grande - grande")
    assert check("19. large")


def test_split_items_finds_disagreements():
    from swarmbly_app.engine.orchestrator import _split_items
    from swarmbly_app.engine.scheduler import Replica
    items = {13: "coche", 14: "pan", 15: "leche"}
    a = Replica("13. car\n14. bread\n15. milk", "n1", "llama", "l", 1)
    b = Replica("13. carro\n14. Bread.\n15. leite", "n2", "phi3", "p", 1)
    assert _split_items([a, b], items) == [13, 15]


def test_run_task_continues_with_excluded_pairs(monkeypatch):
    import asyncio
    from types import SimpleNamespace
    import swarmbly_app.engine.scheduler as sched
    monkeypatch.setattr(sched, "verify_result", lambda *x: "")

    def peer(node_id, family, version):
        return SimpleNamespace(node_id=node_id, tasks_inflight=0, rtt_ms=1.0,
                               advertisement={"models": [{"family": family,
                                                          "version": version}],
                                              "policy": {"max_concurrent": 1}})

    class Nodes:
        def __init__(self, peers):
            self.peers = {p.node_id: p for p in peers}
            self.sent = []

        def available_workers(self, kind="generate"):
            return list(self.peers.values())

        async def dispatch_async(self, node_id, message, timeout_s):
            self.sent.append((node_id, message["attempt_id"]))
            return {"type": "result", "attempt_id": message["attempt_id"],
                    "text": node_id, "profile": {}, "telemetry": {}}

    class Bus:
        def publish(self, *a, **k):
            pass

    nodes = Nodes([peer("a", "llama", "llama3.1:8b"), peer("b", "phi3", "phi3.5:3.8b"),
                   peer("c", "gemma2", "gemma2:2b")])
    s = sched.Scheduler(nodes, Bus(), "r", k_min=2, k_max=4, max_concurrency=4,
                        timeout_s=5, hedge_fallback_s=5, latency=sched.LatencyStats())
    out = asyncio.run(s.run_task("t0", lambda n, f, m=None: {"attempt_id": f"x{n}"}, 100,
                                 k_min=1, k_max=1, start_number=2,
                                 exclude={("a", "llama"), ("b", "phi3")}))
    assert [r.text for r in out] == ["c"] and nodes.sent == [("c", "x2")]


def test_disagreeing_replicas_get_a_third(tmp_path):
    from test_p2p_two_nodes import connect, make_node
    w1, _ = make_node(tmp_path, "W1", worker=True, model="llama3.2:3b",
                      reply="1. Quito\n2. Lima\n3. Santiago\n4. Buenos Aires")
    w2, _ = make_node(tmp_path, "W2", worker=True, model="phi3.5:3.8b",
                      reply="1. Quito\n2. Lima\n3. Valparaíso\n4. Buenos Aires")
    w3, _ = make_node(tmp_path, "W3", worker=True, model="gemma2:2b",
                      reply="1. Quito\n2. Lima\n3. Santiago\n4. Buenos Aires")
    client, _ = make_node(tmp_path, "C", extra={"swarm": {"k_min": 2, "k_max": 4,
                                                          "min_items_per_fragment": 4}})
    try:
        for w in (w1, w2, w3):
            connect(client, w)
        conv = client.chat.create_conversation(mode="lan")
        client.chat.send(conv["id"], "Para cada uno de los siguientes países, indica solo "
                         "el nombre de su capital:\n1. Ecuador\n2. Perú\n3. Chile\n"
                         "4. Argentina\n5. Colombia\n6. Uruguay\n7. Paraguay\n8. Venezuela",
                         mode="lan", run_async=False)
        final = client.chat.get_messages(conv["id"])[-1]
        swarm = final["meta"]["swarm"]
        assert final["meta"]["status"] == "done", final["meta"]
        assert any(3 in tb["items"] for tb in swarm["tie_breaks"]) or not any(
            "Valparaíso" in line for line in final["content"].splitlines())
        assert "3. Santiago" in final["content"]
    finally:
        for st in (w1, w2, w3, client):
            st.stop()


def test_length_beats_extra_requirement_words_but_not_names(app_state):
    """P3g.2: a 164-word replica beat a 73-word one for a 99-word section
    because it repeated more of the brief's words."""
    from swarmbly_v0 import HashEmbedder
    from swarmbly_app.engine.orchestrator import Orchestrator
    from swarmbly_app.engine.scheduler import Replica
    orch = Orchestrator(app_state.nodes, app_state.bus, None, app_state.config.all)
    long_ = "Las estrategias para maximizar ventajas y reducir riesgos rurales. " * 18
    fit = "El sol abastece a las comunidades aisladas del país. " * 11       # ~99
    out = orch._resolve("t3", [Replica(long_, "n1", "llama", "l", 5),
                               Replica(fit, "n2", "phi3", "p", 6)],
                        build_contract(REPORT_ES).contract, HashEmbedder(),
                        policy="whole", lang="es", target_words=99,
                        required=["estrategias", "maximizar", "riesgos"])
    assert out["text"] == fit
    named = "Soy Sebastian y presento las Galápagos. " * 26                  # ~182
    out = orch._resolve("t0", [Replica(named, "n1", "llama", "l", 5),
                               Replica(fit, "n2", "phi3", "p", 6)],
                        build_contract(REPORT_ES).contract, HashEmbedder(),
                        policy="whole", lang="es", target_words=99,
                        required=["sebastian"], critical=["sebastian"])
    assert out["text"] == named


def test_short_sections_ask_for_fewer_words():
    assert composer.asked_words(composer.Section("x", "x", 100), 0.8) == 60
    assert composer.asked_words(composer.Section("x", "x", 250), 0.8) == 200


def test_numbered_answers_win_ties_over_positional_ones():
    """P3g.1: unnumbered answers in another order were mapped to the wrong items."""
    from swarmbly_app.engine.scheduler import Replica
    items = {4: "Iguana marina", 5: "Pinzón de Darwin", 6: "Tiburón martillo"}
    positional = Replica("pez\nave\nreptil", "n1", "qwen2", "q", 1)
    numbered = Replica("4. Reptil\n5. Ave\n6. Pez", "n2", "llama", "l", 1)
    text, _ = _vote_items([positional, numbered], items, [0, 1], "es")
    assert text.splitlines() == ["4. Reptil", "5. Ave", "6. Pez"]


def test_style_loses_format_words_the_request_did_not_ask_for():
    """P3g.2: 'formatting rules: … bullet points, numbered lists, tables' in
    the style line gave every section its own table (31 rows)."""
    o = composer.Outline("T", "agua", "register: formal; tone: informative; formatting "
                         "rules: headings, subheadings, bullet points, numbered lists, tables",
                         [composer.Section("Intro", "x", 100),
                          composer.Section("Tabla", "x", 120, kind="table"),
                          composer.Section("Cierre", "x", 100)], "local_model")
    composer._clean_style(o, "Redacta un artículo con una tabla de ecosistemas.")
    assert o.style == "register: formal; tone: informative" and not o.lists_ok
    brief = composer.section_instruction(o, 0, "es")
    assert "sin tablas ni listas" in brief and "tables" not in brief
    assert "sin tablas" not in composer.section_instruction(o, 1, "es")


def test_requested_lists_are_kept():
    o = composer.Outline("T", "t", "tono cercano, con viñetas", [
        composer.Section("A", "x", 100), composer.Section("B", "x", 100),
        composer.Section("C", "x", 100)], "local_model")
    composer._clean_style(o, "Escribe una guía con viñetas.")
    assert o.style == "tono cercano, con viñetas" and o.lists_ok
    assert "sin tablas." in composer.section_instruction(o, 1, "es")


def test_no_respond_in_spanish_when_the_answer_language_is_named():
    """P3h.1: 'traducción al inglés … Responde en español.' made qwen2.5:3b
    echo the Spanish words; without the last line it translated them."""
    from swarmbly_app.engine.packets import answer_language_named, localise_instruction
    d = localise_instruction("Para cada una de las siguientes palabras en español, da solo "
                             "su traducción al inglés:\n\n7. libro", "es", "enumerated")
    assert "Responde en español" not in d and d.rstrip().endswith("No repitas el elemento.")
    b = localise_instruction("Para cada uno de los siguientes países, indica solo el "
                             "nombre de su capital:\n\n1. Ecuador", "es", "enumerated")
    assert b.rstrip().endswith("Responde en español.")
    assert answer_language_named("Traduce al francés") and answer_language_named(
        "translate into German") and not answer_language_named("la capital de Inglaterra")


def test_vote_key_ignores_units_and_plurals():
    from swarmbly_app.engine.orchestrator import _vote_key
    assert _vote_key("1.5") == _vote_key("1.5 km") == _vote_key("1,5 km")
    assert _vote_key("250/1000 = 0.25 km") == _vote_key("0.25")
    assert _vote_key("Aves") == _vote_key("ave") and _vote_key("Reptiles") == _vote_key("reptil")
    assert _vote_key("Mamíferos") == _vote_key("mamífero")
    assert _vote_key("car") != _vote_key("carro") and _vote_key("0.1 km") != _vote_key("70 m")


def test_answer_on_the_line_after_the_repeated_item():
    items = {4: "Iguana marina", 5: "Pinzón de Darwin", 6: "Tiburón martillo"}
    text = "4. Iguana marina\n- reptil\n\n5. Pinzón de Darwin\n- ave\n\n6. Tiburón martillo\n- pez"
    assert _parse_items(text, items) == {4: "reptil", 5: "ave", 6: "pez"}
    assert _parse_items("4. Iguana marina\n5. Pinzón de Darwin", items) == {}


def test_lowercase_upstream_entities_are_not_names():
    """P3i.1: 'usa exactamente estos nombres: para, cada, una' in every packet."""
    assert build_contract("Para cada una de las siguientes palabras en español, da solo "
                          "su traducción al inglés:\n1. perro\n2. gato"
                          ).contract.canonical_entities == ()
    assert "Darwin" in build_contract("Indica:\n1. Tortuga\n2. Pinzón de Darwin"
                                      ).contract.canonical_entities


def test_copied_style_placeholder_is_dropped():
    o = composer.Outline("T", "t", "One line: register, tone, voice and formatting rules "
                         "from the request", [composer.Section("A", "x", 100)] * 3,
                         "local_model")
    composer._clean_style(o, "Redacta un artículo.")
    assert o.style == ""


def test_advertisement_says_version_system_and_memory(app_state):
    from swarmbly_app import __version__
    from swarmbly_app.state import _build_advertisement
    res = _build_advertisement(app_state)["resources"]
    assert res["app_version"] == __version__ and res["os"] and res["ram_available_mb"] > 0
    assert "app_build" in res


def test_batch_directive_has_no_example_line():
    """P3j: an example ("1. respuesta") was copied or made workers renumber."""
    from swarmbly_app.engine.packets import localise_instruction
    text = localise_instruction("Indica la clase:\n\n7. Pingüino\n8. Rana", "es", "enumerated")
    assert "respuesta»" not in text and "respuesta. No repitas el elemento." in text


def test_renumbered_answer_repeated_in_a_fence_is_read():
    """P3j.1: '1. Ave 2. Anfibio ```markdown 1. Ave 2. Anfibio```' for items 7–8."""
    items = {7: "Pingüino de Galápagos", 8: "Rana arborícola"}
    text = "1. Ave\n2. Anfibio\n\n```markdown\n1. Ave\n2. Anfibio\n```"
    assert _parse_items(text, items) == {7: "Ave", 8: "Anfibio"}
    assert _parse_items("1. Ave\n2. Anfibio\n3. Pez", items) == {}


def test_bold_markers_inside_an_answer_are_removed():
    assert _parse_items("4. **12.5** km\n5. __0.8__ km", {4: "12500 m", 5: "800 m"}) == {
        4: "12.5 km", 5: "0.8 km"}


def test_table_section_needs_a_table():
    from swarmbly_app.engine.orchestrator import Orchestrator
    o = composer.Outline("T", "agua", "", [composer.Section("Intro", "x", 100),
                                           composer.Section("Tabla", "x", 120, kind="table"),
                                           composer.Section("Cierre", "x", 100)], "local_model")
    checks = Orchestrator._validators(None, "composition", o)
    assert not checks["t1"]("Los ecosistemas andinos cumplen papeles distintos. " * 10)
    assert checks["t1"]("Resumen:\n| Ecosistema | Papel |\n|---|---|\n| Páramo | esponja |\n")


def test_answers_in_a_markdown_table_are_read():
    items = {7: "Pingüino de Galápagos", 8: "Rana arborícola"}
    text = ("| Número | Animal | Tipo |\n|--------|--------|------|\n"
            "| 7 | Pingüino de Galápagos | Ave |\n| 8 | Rana arborícola | Anfibio |")
    assert _parse_items(text, items) == {7: "Ave", 8: "Anfibio"}
