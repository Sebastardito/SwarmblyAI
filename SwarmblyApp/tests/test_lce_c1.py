"""P2b: LCE C1 retrieval over raw sources, for local answers only."""

from __future__ import annotations


def _write(state, name, text):
    state.dirs.sources.mkdir(parents=True, exist_ok=True)
    (state.dirs.sources / name).write_text(text, encoding="utf-8")


def test_retrieve_ranks_paragraphs_and_reports_origin(app_state):
    _write(app_state, "notas.md", "El piquero de patas azules es un ave marina de Galápagos.\n\n"
           "La iguana marina es un reptil que se alimenta de algas.")
    _write(app_state, "otra.txt", "Receta de pan: harina, agua y sal.")
    hits = app_state.lce.retrieve("¿qué tipo de animal es el piquero de patas azules?")
    assert hits[0]["source"] == "notas.md" and "ave marina" in hits[0]["text"]
    assert hits[0]["start"] == 0 and hits[0]["score"] > 0
    assert all(h["source"] != "otra.txt" for h in hits)


def test_local_answer_gets_sources_only_with_c1(app_state, fake_chat):
    chat, fake = fake_chat
    _write(app_state, "notas.md", "El piquero de patas azules es un ave marina.")
    conv = chat.create_conversation(mode="local")
    chat.send(conv["id"], "¿El piquero de patas azules es un ave?", mode="local",
              run_async=False)
    assert all(m["role"] != "system" for m in fake.calls[-1]["messages"])   # C0: nothing
    app_state.config.update({"lce": {"enabled": True, "level": "C1"}})
    chat.send(conv["id"], "¿El piquero de patas azules es un ave?", mode="local",
              run_async=False)
    system = [m["content"] for m in fake.calls[-1]["messages"] if m["role"] == "system"]
    assert system and "Fuentes locales" in system[0] and "[1] (notas.md)" in system[0]
    final = chat.get_messages(conv["id"])[-1]
    assert final["meta"]["lce"]["sources"][0]["source"] == "notas.md"
