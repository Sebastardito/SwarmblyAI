"""T10.17: the conversation language reaches every recipe and the final text."""

from __future__ import annotations

from swarmbly_app import recipes
from swarmbly_app.inference.base import GenerationResult


class Replier:
    name = "fake"

    def __init__(self, replies: list[str]):
        self.replies = list(replies)
        self.calls: list[list[dict]] = []

    def available(self) -> bool:
        return True

    def list_models(self) -> list[str]:
        return ["fake-model:1b"]

    def stream_chat(self, messages, *, model, max_tokens=1024, temperature=0.2,
                    on_delta=None, interrupt=None, system=None, **kw):
        self.calls.append([dict(message) for message in messages])
        text = self.replies[min(len(self.calls) - 1, len(self.replies) - 1)]
        if on_delta:
            on_delta(text)
        return GenerationResult(text=text, model=model, completion_tokens=8,
                                total_ms=1)


def test_list_and_code_prompts_take_the_conversation_language():
    assert recipes.list_language("Estado", "es") == "es"
    prompt = recipes.build_list_prompt("Estado", ["ficha uno"], lang="es")
    assert "Elementos:" in prompt
    assert "número. respuesta" in prompt

    code = recipes.build_code_prompt("q", [{"name": "datos.csv"}], [], lang="es")
    assert "Pregunta: q" in code
    assert "Responde solo con el script" in code
    assert "Escribe en español" in code


def test_an_english_answer_to_a_spanish_question_is_regenerated_once(app_state):
    app_state.config.update({"language": "es", "evidence.enabled": False,
                             "compose.verify": False,
                             "lce": {"query_expansion": False}})
    fake = Replier([
        "The document says the fruit weighed two kilos and the field was dry.",
        "El documento dice que la fruta pesó dos kilos y el campo estaba seco.",
    ])
    app_state.backends.resolve = lambda config=None: fake
    conv = app_state.chat.create_conversation(mode="local")
    app_state.chat.send(conv["id"], "¿Qué dice el documento sobre la fruta?",
                        run_async=False)
    message = app_state.chat.get_messages(conv["id"])[-1]
    assert len(fake.calls) == 2
    assert message["content"].startswith("El documento")
    assert message["meta"]["language_retry"]["kept"] is True
    assert message["meta"]["language_retry"]["detected"] == "en"


def test_a_short_numeric_answer_is_not_retried_as_a_language_drift(app_state):
    app_state.config.update({"language": "es", "evidence.enabled": False,
                             "compose.verify": False,
                             "lce": {"query_expansion": False}})
    fake = Replier(["42"])
    app_state.backends.resolve = lambda config=None: fake
    conv = app_state.chat.create_conversation(mode="local")
    app_state.chat.send(conv["id"], "¿Cuánto es seis por siete?", run_async=False)
    assert len(fake.calls) == 1
    message = app_state.chat.get_messages(conv["id"])[-1]
    assert "language_retry" not in message["meta"]


def test_list_status_cells_follow_a_spanish_conversation(app_state, monkeypatch):
    from swarmbly_app.recipes import normalise_list_job
    app_state.config.update({"language": "es", "evidence.enabled": False,
                             "compose.verify": False})
    job = normalise_list_job({"items": ["ficha uno", "ficha dos"],
                              "operation": "Estado", "where": "local"},
                             max_items=200)
    monkeypatch.setattr(
        app_state.chat, "_list_local_wave",
        lambda *args, **kw: ({1: {"answer": "listo", "status": "answered",
                                  "agreement": 1.0},
                              2: {"answer": "", "status": "missing",
                                  "agreement": 0.0}}, "fake", False))
    conv = app_state.chat.create_conversation(mode="local")
    app_state.chat.send(conv["id"], "Estado", recipe="list",
                        list_job=job.to_dict(), run_async=False)
    message = app_state.chat.get_messages(conv["id"])[-1]
    assert "Elemento" in message["content"] and "Estado" in message["content"]
    assert "respondido" in message["content"]
    assert "sin respuesta" in message["content"]
    assert "missing" not in message["content"]
