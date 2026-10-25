"""P2e: cross-language C1 retrieval and public evidence for local answers."""

from __future__ import annotations

from swarmbly_app.lce_adapter import _paragraphs, _tokens
from swarmbly_app.local_context import (Expansion, binomials, parse_expansion,
                                        public_entities, render_public, translated_names,
                                        wants_public)
from swarmbly_app.engine.evidence import WikipediaEvidence


def _write(state, name, text):
    state.dirs.sources.mkdir(parents=True, exist_ok=True)
    (state.dirs.sources / name).write_text(text, encoding="utf-8")


def test_tokens_fold_accents_drop_function_words_and_plurals():
    assert _tokens("¿Cuántos cucuves de las islas Galápagos?") == ["cucuve", "isla", "galapago"]
    assert _tokens("I+D en la PUCE") == ["i+d", "puce"]


def test_paragraphs_index_file_name_title_and_heading_not_as_spans():
    text = "# Chapter 2: genome assembly\n\nMethods.\n\nWe used Supernova to assemble the genome."
    spans = _paragraphs("02_tesis_genoma.md", text, label="tesis/02_tesis_genoma.md")
    # the heading right above is shown with the paragraph; the document title is not
    assert [s["text"] for s in spans] == ["Methods. — We used Supernova to assemble the genome."]
    assert "tesis" in spans[0]["index"] and "Chapter 2" in spans[0]["index"] \
        and "Methods" in spans[0]["index"]


def test_stacked_headings_are_shown_and_cut_pieces_overlap_in_the_index():
    text = ("Experiencia\n\nGerente de I+D (R&D Manager) — Sep 2024\n\nAcmeLabs Inc.\n\n"
            "Lideré los programas de mejoramiento de la mosca soldado negra con un equipo de doce "
            "personas en tres sedes distintas del laboratorio.")
    spans = _paragraphs("perfil.md", text)
    assert spans[0]["text"].startswith("Experiencia · Gerente de I+D (R&D Manager) — Sep 2024 · "
                                       "AcmeLabs Inc. — Lideré")
    body = ("The two remnant populations of AB1 live on Champion and Gardner. " +
            "Filler sentence about genetic load and island size here. " * 9 +
            "These two populations, Champion (Ne ~30) and Gardner (Ne ~120), are small.")
    pieces = _paragraphs("ch3.md", body)
    assert len(pieces) > 1 and "Ne ~30" in pieces[-1]["text"]
    assert "Filler sentence" in pieces[-1]["index"].split("These two")[0]   # previous sentence
    assert _tokens("tamaño efectivo (Ne)")[-1] == "ne"                    # not a stop word


def test_cv_title_line_is_shown_with_the_duties_below():
    text = ("Entomólogo Jefe de I+D (Investigador Principal) — Fenotipado, Mejoramiento Selectivo y "
            "Genómica — Nov 2022 – Sep 2024\n\nAcmeLabs Inc.\n\nLideré iniciativas de fenotipado y "
            "mejoramiento selectivo aplicadas a insectos en el laboratorio.\n\n"
            "Ana Pérez1 | Luis Gómez2 | Sebastián Ruiz3 | Marta Díaz4 | Pedro Vela5 | Rosa Lima6 | Juan Ortiz7\n\n"
            "We studied the effects of an invasive parasite on the nestlings of island birds.")
    spans = _paragraphs("cv.md", text)
    assert spans[0]["text"].startswith("Entomólogo Jefe de I+D (Investigador Principal)")
    assert "Lideré iniciativas" in spans[0]["text"]
    assert any(s["text"].startswith("Ana Pérez1 |") for s in spans)   # an author list stays a passage


def test_long_paragraph_is_cut_at_a_sentence_end():
    body = ("Sentence one is here. " * 40).strip()
    spans = _paragraphs("a.md", body)
    assert all(len(s["text"]) <= 600 for s in spans) and spans[0]["text"].endswith(".")


def test_expansion_lets_a_spanish_question_reach_an_english_source(app_state):
    _write(app_state, "tesis_cap2.md", "A total of 139 individual Galapagos mockingbirds were "
           "sampled from six different islands.\n\nThe weather was dry in 2017.")
    _write(app_state, "notas.md", "Receta de pan: harina, agua y sal.")
    q = "¿Cuántos cucuves se muestrearon?"
    assert not app_state.lce.retrieve(q)
    hits = app_state.lce.retrieve(q, expansion="mockingbirds sampled total individuals")
    assert hits and "139" in hits[0]["text"]


def test_duplicate_paragraphs_are_returned_once(app_state):
    _write(app_state, "a.md", "The Supernova assembler built the genome.")
    _write(app_state, "b.md", "The Supernova assembler built the genome.")
    assert len(app_state.lce.retrieve("Supernova genome")) == 1


def test_parse_expansion_and_binomials():
    e = parse_expansion("Keywords: IUCN, conservation status, Mimus melanotis || "
                        "San Cristobal mockingbird; San Cristobal Island")
    assert e.keywords.startswith("IUCN") and e.entities == ["San Cristobal mockingbird",
                                                           "San Cristobal Island"]
    assert parse_expansion("only words without a bar").entities == []
    assert binomials("Según Mimus melanotis y Laterallus spilonota; Mimus species") == \
        ["Mimus melanotis", "Laterallus spilonota"]


def test_public_entities_come_from_the_question_or_species_names_in_passages():
    exp = Expansion(keywords="parasite epigenetics", entities=["Galapagos", "NRGene Canada"])
    passages = [{"text": "We studied the invasive Philornis downsi in nests of AB1 owners at "
                         "AcmeLabs. Philornis downsi larvae feed on nestlings."},
                {"text": "Guppies (Poecilia reticulata) were studied elsewhere."}]
    picked = public_entities("¿Qué parásito estudié en mi artículo de 2021?", exp, passages)
    assert [p["name"] for p in picked] == ["Philornis downsi"]   # repeated, so it is the topic
    assert picked[0]["from"].startswith("local passages")


def test_model_names_are_never_sent_glossary_names_are():
    exp = Expansion(keywords="", entities=["Galapagos rat", "Canis", "AcmeLabs"])
    glossary = [("rascón", "rail, crake, Laterallus spilonota"),
                ("cucuve", "mockingbird, Mimus"), ("lobo peletero", "fur seal, Arctocephalus")]
    q = "¿Qué se sabe hoy del rascón de Galápagos y del cucuve de la isla Floreana?"
    names = [p["name"] for p in public_entities(q, exp, [], glossary=glossary)]
    assert names == ["Galápagos rail", "Floreana mockingbird"]
    assert translated_names("Los cucuves de Española y el lobo peletero de Galápagos",
                            glossary) == ["Española mockingbird", "Galápagos fur seal"]
    assert translated_names("¿Qué logró el Proyecto Isabela?",
                            [("Proyecto Isabela", "Project Isabela, goat eradication")]) == \
        ["Project Isabela"]


def test_public_evidence_only_when_the_question_asks_for_public_or_current_facts():
    assert wants_public("¿Cuál es su estado de conservación actual?")
    assert wants_public("¿Qué dicen las fuentes públicas?")
    assert not wants_public("¿Qué programa usé en el capítulo 2 de mi tesis?")


def test_passages_keep_first_sentence_and_focus_sentences_outside_the_intro():
    article = ("The San Cristóbal mockingbird (Mimus melanotis) is a species of bird. "
               "== Distribution == It lives on San Cristóbal Island. "
               "== Status == The IUCN has assessed the San Cristóbal mockingbird as Near "
               "Threatened. Prior to 2020 it was classified as Endangered.")
    seen = []

    def fetch(url, timeout, ua):
        seen.append(url)
        return {"query": {"pages": {"1": {"title": "San Cristóbal mockingbird",
                                          "extract": article}}}}
    hit = WikipediaEvidence(lang="en", fetch=fetch).passages(
        "Mimus melanotis", ["iucn", "conservation", "status", "endangered"])
    assert hit["text"].startswith("The San Cristóbal mockingbird")
    assert "Near Threatened" in hit["text"] and "Endangered" in hit["text"]
    assert "==" not in hit["text"] and "exintro" not in seen[0]


def test_local_answer_with_public_evidence_sends_only_names(app_state, fake_chat):
    chat, fake = fake_chat
    _write(app_state, "tesis.md", "M. melanotis (IUCN: endangered), the San Cristobal "
           "mockingbird; Mimus melanotis was sequenced from sample AB1.")
    app_state.config.update({"lce": {"enabled": True, "level": "C1"},
                             "evidence": {"enabled": True}})
    fake.reply = "IUCN, endangered, Mimus melanotis, mockingbird || San Cristobal mockingbird"
    asked = []

    class Provider:
        lang = "en"

        def passages(self, entity, focus):
            asked.append(entity)
            return {"title": "San Cristóbal mockingbird", "url": "https://en.wikipedia.org/x",
                    "text": "The IUCN has assessed it as Near Threatened."}
    chat.public_provider = Provider()
    conv = chat.create_conversation(mode="local")
    q = "¿Qué categoría UICN da mi tesis a Mimus melanotis y cuál es la actual?"
    chat.send(conv["id"], q, mode="local", run_async=False)
    assert asked == ["Mimus melanotis"]            # the model's names are not sent
    assert all(q not in a for a in asked)
    system = [m["content"] for m in fake.calls[-1]["messages"] if m["role"] == "system"]
    assert not any("[1] (tesis.md)" in s for s in system)      # all in the user's turn now
    meta = chat.get_messages(conv["id"])[-1]["meta"]
    assert meta["evidence"]["queried"] == asked and meta["evidence"]["local_answer"]
    last = fake.calls[-1]["messages"][-1]["content"]
    assert "MIS DOCUMENTOS" in last and "[1] (tesis.md)" in last and "[W1]" in last
    assert meta["lce"]["expansion"]["entities"] == ["San Cristobal mockingbird"]


def test_no_public_lookup_for_a_question_about_own_documents(app_state, fake_chat):
    chat, fake = fake_chat
    app_state.config.update({"lce": {"enabled": True, "level": "C1"},
                             "evidence": {"enabled": True}})

    class Provider:
        lang = "en"

        def passages(self, entity, focus):
            raise AssertionError("must not be called")
    chat.public_provider = Provider()
    conv = chat.create_conversation(mode="local")
    chat.send(conv["id"], "¿Qué muestra de Mimus melanotis usé en mi tesis?", mode="local",
              run_async=False)
    assert "evidence" not in chat.get_messages(conv["id"])[-1]["meta"]


def test_no_public_lookup_when_evidence_is_off(app_state, fake_chat):
    chat, fake = fake_chat
    app_state.config.update({"lce": {"enabled": True, "level": "C1"}})

    class Provider:
        lang = "en"

        def passages(self, entity, focus):
            raise AssertionError("must not be called")
    chat.public_provider = Provider()
    conv = chat.create_conversation(mode="local")
    chat.send(conv["id"], "¿Qué es Mimus melanotis?", mode="local", run_async=False)
    assert "evidence" not in chat.get_messages(conv["id"])[-1]["meta"]


def test_render_public_lists_what_was_sent():
    out = render_public([{"sent": "Mimus melanotis", "title": "T", "text": "x"}], "es")
    assert "solo se enviaron estos nombres: Mimus melanotis" in out and "[W1] (T) x" in out


def test_glossary_bridges_terms_and_is_not_a_passage(app_state):
    _write(app_state, "glosario.md", "# Glosario\n\n- cucuve = mockingbird, Mimus\n"
           "- tamaño poblacional efectivo = effective population size, Ne\n")
    _write(app_state, "thesis.md", "The Champion mockingbird population has an effective "
           "population size near 30.")
    assert app_state.lce.glossary_terms("¿Qué tamaño poblacional efectivo tiene el cucuve?") == \
        "mockingbird, Mimus effective population size, Ne"
    hits = app_state.lce.retrieve("¿Qué tamaño poblacional efectivo tiene el cucuve de Champion?")
    assert hits and hits[0]["source"] == "thesis.md"
    assert all(h["source"] != "glosario.md" for h in hits)


def test_glossary_matches_spanish_gender_and_one_article_is_used_once(app_state):
    _write(app_state, "glosario.md", "- extinto = extinct, extirpated\n")
    assert app_state.lce.glossary_terms("la población extinta de Floreana") == "extinct, extirpated"
    from swarmbly_app.local_context import public_evidence

    class Provider:
        lang = "en"

        def passages(self, entity, focus):
            return {"title": "Floreana mockingbird", "url": "u", "text": "t"}
    hits, report = public_evidence([{"name": "Mimus trifasciatus", "from": "question"},
                                    {"name": "Floreana mockingbird", "from": "question (glossary)"}],
                                   Expansion(), Provider())
    assert len(hits) == 1 and report["used"] == 1


def test_abbreviated_species_names_are_indexed_in_full(app_state):
    _write(app_state, "cap1.md", "Mimus melanotis lives on one island.\n\n"
           "Its status: M. melanotis (IUCN: endangered) and others.")
    hits = app_state.lce.retrieve("Mimus melanotis IUCN endangered")
    assert hits[0]["text"].startswith("Its status: Mimus melanotis (IUCN")   # genus spelled out


def test_one_file_fills_at_most_three_slots(app_state):
    _write(app_state, "big.md", "\n\n".join(f"Supernova assembly note about {w}." for w in
                                            ("alpha", "beta", "gamma", "delta", "omega")))
    _write(app_state, "other.md", "Supernova assembly in another file.")
    hits = app_state.lce.retrieve("Supernova assembly", k=4)
    assert sum(h["source"] == "big.md" for h in hits) == 3 and any(h["source"] == "other.md" for h in hits)


def test_year_questions_bring_the_sentence_with_the_year():
    article = ("The Floreana mockingbird is a bird. It is endemic to Galápagos. Its song is loud. "
               "It was extirpated from Floreana by 1888. It now lives on two islets.")

    def fetch(url, timeout, ua):
        return {"query": {"pages": {"1": {"title": "Floreana mockingbird", "extract": article}}}}
    hit = WikipediaEvidence(lang="en", fetch=fetch).passages("Floreana mockingbird", ["__year__"])
    assert "1888" in hit["text"]
    from swarmbly_app.local_context import focus_terms
    assert focus_terms(Expansion(), "x", "", "¿En qué año desapareció?")[0] == "__year__"


def test_fusion_prompt_labels_both_kinds_and_acronyms_are_not_sent():
    from swarmbly_app.local_context import fusion_prompt
    out = fusion_prompt([{"source": "tesis.md", "text": "M. melanotis (IUCN: endangered)"}],
                        [{"sent": "Mimus melanotis", "title": "San Cristóbal mockingbird",
                          "text": "Near Threatened."}], "¿Coincide?", "es")
    assert out.index("MIS DOCUMENTOS") < out.index("[1] (tesis.md)") < out.index("FUENTES PÚBLICAS") \
        < out.index("[W1]") < out.index("PREGUNTA: ¿Coincide?") < out.index("Responde en tres partes")
    assert translated_names("¿Qué dice la UICN?", [("UICN", "IUCN")]) == []


def test_fusion_model_writes_only_fused_answers_and_expansion_uses_the_default(app_state, fake_chat):
    chat, fake = fake_chat
    _write(app_state, "tesis.md", "M. melanotis (IUCN: endangered), the San Cristobal mockingbird.")
    app_state.config.update({"lce": {"enabled": True, "level": "C1"},
                             "model": {"model_name": "small:3b"},
                             "evidence": {"enabled": True, "fusion_model": "big:27b"}})

    class Provider:
        lang = "en"

        def passages(self, entity, focus):
            return {"title": "San Cristóbal mockingbird", "url": "u", "text": "Near Threatened."}
    chat.public_provider = Provider()
    conv = chat.create_conversation(mode="local", model="big:27b")
    chat.send(conv["id"], "¿Cuál es el estado actual de Mimus melanotis?", mode="local",
              run_async=False)
    assert fake.calls[0]["model"] == "small:3b"          # expansion
    assert fake.calls[-1]["model"] == "big:27b"           # fused answer
    conv2 = chat.create_conversation(mode="local", model="small:3b")
    chat.send(conv2["id"], "¿Qué muestra de Mimus melanotis usé en mi tesis?", mode="local",
              run_async=False)
    assert fake.calls[-1]["model"] == "small:3b"          # not fused: no public question


def test_reasoning_output_is_stripped_from_the_expansion():
    e = parse_expansion("<think>let me see</think>mockingbird, sample || San Cristobal mockingbird")
    assert e.keywords.startswith("mockingbird") and e.entities == ["San Cristobal mockingbird"]


def test_hybrid_retrieval_brings_a_semantically_close_long_paragraph(app_state):
    filler = " ".join(f"word{i}" for i in range(80))
    _write(app_state, "a.md", f"Champion and Gardner came from a larger population. {filler}\n\n"
           "Champion Gardner Champion Gardner Champion Gardner, notes listed here today.\n\n"
           "Champion islet notes about weather and plants written by the field team.\n\n"
           "Gardner islet notes about weather and rocks written by the field team.")
    calls = []

    def embed(texts, kind):
        calls.append(kind)
        # toy embedding: 1 on axis 0 if the text speaks of an ancestral/larger population
        return [[1.0, 0.0] if ("larger population" in t or "ancestral" in t) else [0.0, 1.0]
                for t in texts]
    hits = app_state.lce.retrieve("Champion Gardner ancestral", k=2, embed=embed)
    assert any(h["text"].startswith("Champion and Gardner came from") for h in hits)
    assert "query" in calls
    plain = app_state.lce.retrieve("Champion Gardner ancestral", k=2)
    assert not any(h["text"].startswith("Champion and Gardner came from") for h in plain)


def test_hybrid_falls_back_to_bm25_when_embedding_fails(app_state):
    _write(app_state, "a.md", "The Supernova assembler built the reference genome of the species.")

    def embed(texts, kind):
        raise OSError("no model")
    assert app_state.lce.retrieve("Supernova genome", embed=embed)[0]["source"] == "a.md"


def test_empty_fused_answer_falls_back_to_the_conversation_model(app_state, fake_chat):
    chat, fake = fake_chat
    _write(app_state, "tesis.md", "M. melanotis (IUCN: endangered), the San Cristobal mockingbird.")
    app_state.config.update({"lce": {"enabled": True, "level": "C1", "dense_retrieval": False},
                             "model": {"model_name": "small:3b"},
                             "evidence": {"enabled": True, "fusion_model": "big:27b"}})

    class Provider:
        lang = "en"

        def passages(self, entity, focus):
            return {"title": "San Cristóbal mockingbird", "url": "u", "text": "Near Threatened."}
    chat.public_provider = Provider()
    real = fake.stream_chat

    def stream(messages, *, model, **kw):
        out = real(messages, model=model, **kw)
        if model == "big:27b":
            out.text = ""
        return out
    fake.stream_chat = stream
    conv = chat.create_conversation(mode="local", model="small:3b")
    chat.send(conv["id"], "¿Cuál es el estado actual de Mimus melanotis?", mode="local",
              run_async=False)
    final = chat.get_messages(conv["id"])[-1]
    assert final["content"] and final["meta"]["fusion_fallback"].startswith("big:27b")
    assert [c["model"] for c in fake.calls][-2:] == ["big:27b", "small:3b"]
