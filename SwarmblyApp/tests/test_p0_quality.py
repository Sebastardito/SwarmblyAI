"""P0 quality fixes (diagnosis 2026-10-15): admission, Γ, packets, context,
whole-replica consensus, budget and truncation.

The essay fixture reproduces the *shape* of the request that exposed the
defects — a Spanish composition with an instruction list, a numbered quality
rubric and a closing format instruction — with neutral content.
"""

from __future__ import annotations

import pytest

from swarmbly_app.engine.admission import admit, batch_shape
from swarmbly_app.engine.contract import build_contract, requested_words
from swarmbly_app.engine.followup import needs_context, standalone
from swarmbly_app.engine.packets import (UPSTREAM_INTEGRATION_SUFFIX, PacketPlan,
                                         build_message, gamma_for,
                                         localise_instruction, measure_rho)
from swarmbly_app.lang import detect_language
from swarmbly_app.p2p.worker import render_packet_prompt

ESSAY_ES = """Redacta un texto de aproximadamente 800 palabras sobre: “Ecuador y Las Islas Galapagos”.

Instrucciones:
- Escribe en español neutro, con tono divulgativo.
- Incluye un título claro y atractivo.
- Abre con una introducción que presente el tema y una idea central.
- Desarrolla al menos tres argumentos o perspectivas, respaldados con ejemplos concretos.
- Evita repeticiones, frases vacías y datos inventados.
- Cierra con una conclusión que sintetice los puntos principales.
- Extensión objetivo: entre 750 y 850 palabras.

Criterios de calidad:
1. Claridad y precisión del lenguaje.
2. Coherencia y cohesión entre ideas.
3. Profundidad del análisis.
4. Calidad de los ejemplos.
5. Corrección gramatical y ortográfica.
6. Cumplimiento de la extensión y las instrucciones.

El producto final debe ser el texto escrito como un discurso, iniciando con la presentación de la presentadora llamada Andrea. Además incluye tablas de resumen para acceso a información rápida."""

BATCH_ES = """Para cada uno de los siguientes animales, escribe una sola línea con su hábitat principal:
1. León
2. Pingüino emperador
3. Camello
4. Oso polar
5. Delfín
6. Cóndor andino
7. Tortuga gigante
8. Canguro

Usa un tono divulgativo."""

INLINE_EN = ("Extract one key fact per item from the following list of five items: "
             "apples, bridges, comets, drums, electrons. List 5 bullet points, one per "
             "item, separately.")


# -- 1. admission --------------------------------------------------------------------
class TestAdmission:
    def test_essay_with_rubric_is_not_a_batch(self):
        adm = admit(ESSAY_ES, n_max=4, n_workers=2)
        assert not adm.admitted
        assert adm.reason.startswith("not a batch")

    def test_per_item_batch_is_admitted(self):
        adm = admit(BATCH_ES, n_max=4, n_workers=2)
        assert adm.admitted and adm.path == "enumerated"
        assert len(adm.items) == 8 and adm.n_tasks >= 2

    def test_inline_english_batch_still_admitted(self):
        adm = admit(INLINE_EN, n_max=4, n_workers=2)
        assert adm.admitted and adm.normalised

    @pytest.mark.parametrize("prompt", [
        "Follow these steps:\n1. Boil water\n2. Add pasta\n3. Drain it",
        "Write an essay about rivers.\nRequirements:\n1. Clear\n2. Concise\n3. Cited",
        "Escribe un discurso de 300 palabras sobre el agua:\n1. origen\n2. usos\n3. futuro",
        "Notes\n1. alpha\n2. beta\n3. gamma",
    ])
    def test_rubrics_compositions_and_bare_lists_are_refused(self, prompt):
        assert not admit(prompt, n_max=4, n_workers=2).admitted

    def test_composition_per_item_is_a_batch(self):
        ok, _ = batch_shape("Write a short poem about each animal:\n1. cat\n2. dog\n3. owl",
                            "Write a short poem about each animal:")
        assert ok

    def test_colon_heading_is_an_operation(self):
        prompt = "Translate to French:\n1. good morning\n2. thank you\n3. see you soon"
        assert admit(prompt, n_max=4, n_workers=2).admitted


# -- 7. contract ---------------------------------------------------------------------
class TestContract:
    def test_spanish_essay_contract(self):
        rc = build_contract(ESSAY_ES)
        c = rc.contract
        assert rc.lang == "es" and rc.length_explicit
        assert rc.target_words == 800          # "aproximadamente 800 palabras"
        assert c.target_length_tokens >= 1200   # 800 words × 1.6, not the 320 default
        assert c.audience == ""                 # neutral, not "a technical reader"
        for verb in ("Redacta", "Escribe", "Incluye", "Abre", "Desarrolla",
                     "Criterios", "Instrucciones"):
            assert verb not in c.canonical_entities
        assert "in conclusion" not in c.forbidden_terms

    @pytest.mark.parametrize("text,words", [
        ("entre 750 y 850 palabras", 800), ("about 500 words", 500),
        ("un texto de 1.200 palabras", 1200), ("650 tokens", 500), ("sin longitud", None),
    ])
    def test_requested_words(self, text, words):
        assert requested_words(text) == words

    def test_english_contract_unchanged_in_lexicon(self):
        rc = build_contract(INLINE_EN)
        assert rc.lang == "en"
        assert "in conclusion" in rc.contract.forbidden_terms


# -- 2/3. packets in the request's language, user postamble kept ---------------------
def _messages(prompt: str):
    from swarmbly_v0 import planner
    adm = admit(prompt, n_max=4, n_workers=2)
    rc = build_contract(adm.prompt)
    plan = planner.plan(adm.prompt, backend=None, n_tasks=adm.n_tasks,
                        contract=rc.contract, force_sequential=False, answer_sheet=False)
    out = []
    for i, task in enumerate(plan.tasks):
        pp = PacketPlan(task.task_id, "", 0, i,
                        localise_instruction(task.instruction, rc.lang, adm.path),
                        False, (), "PUBLIC")
        gamma = gamma_for(rc.contract, "op", task.instruction, 400, rc.lang)
        out.append(build_message(pp, gamma, b"\x00" * 16, 0, {}, {}, max_tokens=400,
                                 deadline_ms=1000, tier="GLOBAL", temperature=0.2,
                                 model_family=None))
    return out


class TestPackets:
    def test_spanish_batch_packets(self):
        messages = _messages(BATCH_ES)
        assert len(messages) >= 2
        for m in messages:
            text = render_packet_prompt(m)
            assert m["contract"]["lang"] == "es"
            assert "[CONTRATO GLOBAL]" in text and "[TAREA]" in text
            assert "Responde en español." in m["task"]["instruction"]
            assert "Usa un tono divulgativo." in text      # user postamble kept
            assert "[NN]" not in text and "Close the answer" not in text
            assert "GLOBAL CONTRACT" not in text and "Respond in" not in text

    def test_english_render_unchanged(self):
        message = {"contract": {"objective": "op", "register": "formal",
                                "format": "markdown"},
                   "task": {"instruction": "Do it.", "expects": {"format": "markdown"}}}
        assert render_packet_prompt(message) == (
            "[GLOBAL CONTRACT]\nobjective: op\nregister: formal\nformat: markdown"
            "\n\n[TASK]\nDo it.\nRespond in markdown format.")

    def test_localise_instruction(self):
        text = localise_instruction("1. a\n2. b" + UPSTREAM_INTEGRATION_SUFFIX, "en",
                                    "enumerated")
        assert "Close the answer" not in text and "[NN]" not in text
        assert text.endswith("Do not repeat the item.")

    def test_max_packet_fraction_reported(self):
        messages = _messages(BATCH_ES)
        rho = measure_rho(messages, BATCH_ES)
        assert 0 < rho["max_packet_prompt_fraction"] < 1


def test_language_detection():
    assert detect_language(ESSAY_ES) == "es"
    assert detect_language(INLINE_EN) == "en"
    assert detect_language("ok") == "en"


# -- 4. conversation context ---------------------------------------------------------
class _Rewriter:
    def __init__(self, out):
        self.out, self.prompts = out, []

    def generate(self, prompt, **kw):
        self.prompts.append(prompt)
        return self.out


HISTORY = [{"role": "user", "content": "Escribe un poema sobre el mar."},
           {"role": "assistant", "content": "El mar canta..."}]


class TestFollowUp:
    def test_detection(self):
        assert needs_context("hazlo más corto", HISTORY)
        assert not needs_context("hazlo más corto", [])
        assert not needs_context(ESSAY_ES, HISTORY)

    def test_rewritten_locally(self):
        backend = _Rewriter("Solicitud: Escribe una versión más corta del poema sobre el mar.")
        text, source = standalone("hazlo más corto", HISTORY, backend)
        assert source == "local_rewrite"
        assert text == "Escribe una versión más corta del poema sobre el mar."
        assert "El mar canta" in backend.prompts[0]     # history used on-device only

    def test_no_rewriter_means_not_distributed(self):
        assert standalone("hazlo más corto", HISTORY, _Rewriter("")) == (None, "unavailable")

    def test_orchestrator_answers_follow_up_locally_without_rewriter(self, app_state):
        from swarmbly_app.engine.orchestrator import Orchestrator
        orch = Orchestrator(app_state.nodes, app_state.bus, None, app_state.config.all)
        out = orch.run("hazlo más corto", mode="lan", history=HISTORY)
        assert out["routed"] == "local"
        assert "earlier turns" in out["reason"]

    def test_chat_passes_history_to_orchestrator(self, app_state, fake_chat):
        chat, _ = fake_chat
        conv = chat.create_conversation(mode="local")
        chat.send(conv["id"], "Escribe un poema sobre el mar.", mode="local",
                  run_async=False)
        seen = {}

        class Stub:
            def run(self, text, **kw):
                seen.update(kw, text=text)
                return {"routed": "local", "reason": "stub", "metadata": {},
                        "stages": []}

        chat.orchestrator = lambda: Stub()
        chat.send(conv["id"], "hazlo más corto", mode="lan", run_async=False)
        assert seen["text"] == "hazlo más corto"
        assert [m["role"] for m in seen["history"]] == ["user", "assistant"]


# -- 5/6. whole-replica consensus, budget, truncation ---------------------------------
class TestWholeReplica:
    def _orch(self, app_state):
        from swarmbly_app.engine.orchestrator import Orchestrator
        return Orchestrator(app_state.nodes, app_state.bus, None, app_state.config.all)

    def test_selects_one_replica_in_the_request_language(self, app_state):
        from swarmbly_v0 import HashEmbedder
        from swarmbly_app.engine.scheduler import Replica
        es = ("Las islas Galápagos son un archipiélago de Ecuador. La fauna de las islas "
              "es única y su conservación es una prioridad para el país.")
        en = ("The Galapagos islands are an archipelago of Ecuador. The wildlife of the "
              "islands is unique and its conservation is a priority for the country.")
        rc = build_contract(ESSAY_ES)
        out = self._orch(app_state)._resolve(
            "t0", [Replica(en, "n1", "llama", "llama3.2:3b", 10),
                   Replica(es, "n2", "qwen2", "qwen2.5:3b", 12)],
            rc.contract, HashEmbedder(), policy="whole", lang="es", budget=2000)
        assert out["text"] == es                       # one replica, never a patchwork
        assert out["consensus"]["selection"]["chosen_family"] == "qwen2"
        assert out["consensus"]["k"] == 2              # divergence still reported

    def test_truncated_replica_loses(self, app_state):
        from swarmbly_v0 import HashEmbedder
        from swarmbly_app.engine.scheduler import Replica
        a = Replica("Texto completo sobre el mar y las islas del país.", "n1", "llama",
                    "m", 10, telemetry={"finish_reason": "length"})
        b = Replica("Texto completo sobre el mar y las islas del país.", "n2", "qwen2",
                    "m", 10, telemetry={"finish_reason": "stop"})
        out = self._orch(app_state)._resolve("t0", [a, b], build_contract(ESSAY_ES).contract,
                                             HashEmbedder(), policy="whole", lang="es")
        assert out["consensus"]["selection"]["chosen_family"] == "qwen2"
        assert out["truncated"] is False

    def test_truncation_by_token_count(self):
        from swarmbly_app.engine.orchestrator import _is_truncated
        from swarmbly_app.engine.scheduler import Replica
        assert _is_truncated(Replica("x", "n", "f", "m", 1,
                                     telemetry={"tokens_out": 400}), 400)
        assert not _is_truncated(Replica("x", "n", "f", "m", 1,
                                         telemetry={"tokens_out": 120}), 400)

    def test_budget_follows_requested_length(self):
        from swarmbly_app.engine.orchestrator import Orchestrator
        essay = build_contract(ESSAY_ES)
        whole = Orchestrator._budget({"max_tokens": 1024}, essay, 1, True)
        assert whole >= 1.5 * essay.contract.target_length_tokens
        frag = Orchestrator._budget({"max_tokens": 1024}, build_contract(BATCH_ES), 2, False)
        assert frag == 400
        assert Orchestrator._budget({"max_tokens": 1024, "max_tokens_per_fragment": 300},
                                    essay, 2, False) >= 900

    def test_local_answer_budget(self):
        from swarmbly_app.engine.contract import answer_budget
        assert answer_budget(ESSAY_ES, 1024) >= 1900       # 800 words × 1.6 × 1.5
        assert answer_budget("Hola, ¿qué tal?", 1024) == 1024


# -- item vote for enumerated batches (live smoke test 2026-10-16) ------------------
class TestItemVote:
    ITEMS = {5: "Pinzón de Darwin", 6: "Tiburón martillo", 7: "Pingüino de Galápagos",
             8: "Rana arborícola"}

    def test_parse_items_ignores_echoes_and_keeps_values(self):
        from swarmbly_app.engine.orchestrator import _parse_items
        text = ("5. Ave 6. Pez 7. Ave 8. Anfibio ```markdown 5. pez "
                "6. Pingüino de Galápagos 7. Ave")
        assert _parse_items(text, self.ITEMS) == {5: "Ave", 6: "Pez", 7: "Ave",
                                                   8: "Anfibio"}
        assert _parse_items("5. **Pinzón de Darwin**: ave\n6. Tiburón martillo – pez",
                            self.ITEMS) == {5: "ave", 6: "pez"}

    def test_majority_wins_and_output_is_one_line_per_item(self, app_state):
        from swarmbly_v0 import HashEmbedder
        from swarmbly_app.engine.orchestrator import Orchestrator
        from swarmbly_app.engine.scheduler import Replica
        orch = Orchestrator(app_state.nodes, app_state.bus, None, app_state.config.all)
        reps = [Replica("5. Ave\n6. Pez\n7. Ave\n8. Anfibio", "n1", "gemma2", "g", 5),
                Replica("5. Ave 6. Pez 7. Mamífero 8. Anfibio", "n2", "llama", "l", 6),
                Replica("5. ave\n6. Reptil\n7. Ave\n8. Anfibio", "n3", "qwen2", "q", 7)]
        out = orch._resolve("t1", reps, build_contract(BATCH_ES).contract, HashEmbedder(),
                            policy="items", lang="es", items=self.ITEMS)
        assert out["text"].splitlines() == ["5. Ave", "6. Pez", "7. Ave", "8. Anfibio"]
        sel = out["consensus"]["selection"]
        assert sel["missing_items"] == [] and sel["items"][0]["agreement"] == 1.0

    def test_unparseable_replicas_fall_back_to_whole(self, app_state):
        from swarmbly_v0 import HashEmbedder
        from swarmbly_app.engine.orchestrator import Orchestrator
        from swarmbly_app.engine.scheduler import Replica
        orch = Orchestrator(app_state.nodes, app_state.bus, None, app_state.config.all)
        reps = [Replica("Todas son aves.", "n1", "gemma2", "g", 5),
                Replica("Son animales de Galápagos.", "n2", "llama", "l", 6)]
        out = orch._resolve("t1", reps, build_contract(BATCH_ES).contract, HashEmbedder(),
                            policy="items", lang="es", items=self.ITEMS)
        assert out["text"] in {r.text for r in reps}
        assert "chosen_family" in out["consensus"]["selection"]

    def test_unlabelled_bullets_are_matched_by_item_text(self):
        from swarmbly_app.engine.orchestrator import _parse_items
        items = {7: "100 m", 8: "7000 m"}
        assert _parse_items("* 100 m = 0,1 km\n* 7000 m = 7 km.", items) == \
            {7: "0,1 km", 8: "7 km"}


class TestPersonalStaysLocal:
    """A request about the user with C1 active is answered here even in LAN mode:
    the swarm would get it without the user's passages and with personal details."""

    def _chat(self, fake_chat, hits):
        chat, _ = fake_chat
        seen = {}

        class Stub:
            def run(self, text, **kw):
                seen["text"] = text
                return {"routed": "local", "reason": "stub", "metadata": {}, "stages": []}
        chat.orchestrator = lambda: Stub()
        chat.retriever = lambda q, kw="": hits
        chat.retrieval_active = lambda: True
        return chat, seen

    def test_about_me_with_sources_stays_local(self, fake_chat):
        chat, seen = self._chat(fake_chat, [{"source": "cv.md", "start": 0, "end": 8, "text": "AcmeLabs", "score": 1.0}])
        conv = chat.create_conversation(mode="lan")
        _, msg = chat.send(conv["id"], "Resume mi carrera como investigador y mis publicaciones.",
                           mode="lan", run_async=False)
        assert "text" not in seen                     # the swarm was never asked
        stored = chat.db.get_messages(conv["id"])[-1]
        assert "on this device" in (stored["meta"].get("note") or "")

    def test_a_batch_with_bare_me_still_goes_to_the_swarm(self, fake_chat):
        chat, seen = self._chat(fake_chat, [{"source": "cv.md", "start": 0, "end": 1, "text": "x", "score": 1.0}])
        conv = chat.create_conversation(mode="lan")
        chat.send(conv["id"], "¿Me traduces al inglés estas palabras? 1. casa 2. perro 3. mesa",
                  mode="lan", run_async=False)
        assert seen.get("text", "").startswith("¿Me traduces")
        chat2, seen2 = self._chat(fake_chat, [])          # no matching sources: not personal
        conv2 = chat2.create_conversation(mode="lan")
        chat2.send(conv2["id"], "Clasifica mis 3 animales: 1. perro 2. loro 3. rana",
                   mode="lan", run_async=False)
        assert seen2.get("text", "").startswith("Clasifica")


def test_personal_topic_stays_local_even_without_sources(fake_chat):
    chat, _ = fake_chat
    seen = {}

    class Stub:
        def run(self, text, **kw):
            seen["text"] = text
            return {"routed": "local", "reason": "stub", "metadata": {}, "stages": []}
    chat.orchestrator = lambda: Stub()
    chat.retriever = None                          # C1 off or no source folder
    conv = chat.create_conversation(mode="lan")
    chat.send(conv["id"], "Resume mi carrera como investigador y mis publicaciones.",
              mode="lan", run_async=False)
    assert "text" not in seen
    chat.send(conv["id"], "Para cada uno de mis 3 animales, di si es ave: 1. perro 2. loro 3. rana",
              mode="lan", run_async=False)
    assert seen.get("text", "").startswith("Para cada")   # "mis animales" is not a personal topic
