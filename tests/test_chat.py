"""Chat engine tests (fake backend, real DB and event flow)."""

from __future__ import annotations

from swarmbly_app.inference.base import Interrupted


class TestChat:
    def test_send_local_records_history(self, app_state, fake_chat):
        chat, fake = fake_chat
        conv = chat.create_conversation(title="T", mode="local", model="fake-model:1b")
        events: list[dict] = []
        app_state.bus.subscribe(events.append)
        user, assistant = chat.send(conv["id"], "Hello there", run_async=False)
        assert user["role"] == "user"
        rows = chat.get_messages(conv["id"])
        assert rows[-1]["content"] == fake.reply
        assert rows[-1]["meta"]["status"] == "done"
        assert rows[-1]["meta"]["mode"] == "local"
        assert rows[-1]["meta"]["model"] == "fake-model:1b"
        assert rows[-1]["meta"]["completion_tokens"] > 0
        assert any(e["type"] == "chat.delta" for e in events)
        assert any(e["type"] == "chat.done" for e in events)
        assert any(e["type"] == "request.started" for e in events)

    def test_default_mode_is_local(self, app_state, fake_chat):
        chat, _ = fake_chat
        assert chat.config()["swarm"]["mode"] == "local"
        conv = chat.create_conversation()
        assert conv["mode"] == "local"

    def test_interrupt_stops_generation(self, app_state, fake_chat):
        chat, fake = fake_chat
        conv = chat.create_conversation()

        def never_stops():  # interrupt fires after the first delta
            return True

        fake.stream_chat = fake.stream_chat  # keep original signature
        original = fake.stream_chat

        def interrupting(messages, **kw):
            kw["interrupt"] = never_stops
            return original(messages, **kw)

        fake.stream_chat = interrupting
        user, assistant = chat.send(conv["id"], "hi", run_async=False)
        rows = chat.get_messages(conv["id"])
        assert rows[-1]["meta"]["status"] == "stopped"

    def test_retry(self, app_state, fake_chat):
        chat, _ = fake_chat
        conv = chat.create_conversation()
        user, assistant = chat.send(conv["id"], "retry me", run_async=False)
        result = chat.retry(conv["id"], assistant["id"])
        assert result is not None
        rows = chat.get_messages(conv["id"])
        # user, assistant, user, assistant
        assert [m["role"] for m in rows] == ["user", "assistant", "user", "assistant"]

    def test_export_markdown_json_html(self, app_state, fake_chat, tmp_path):
        chat, _ = fake_chat
        conv = chat.create_conversation(title="Export me")
        chat.send(conv["id"], "hi", run_async=False)
        md = chat.export(conv["id"], fmt="markdown")
        assert "Export me" in md and "hi" in md
        js = chat.export(conv["id"], fmt="json")
        assert '"role"' in js
        html = chat.export(conv["id"], fmt="html")
        assert "<h1>Export me</h1>" in html
        path = chat.export(conv["id"], fmt="markdown", out_dir=tmp_path / "out")
        assert (tmp_path / "out" / f"conversation-{conv['id']}.md").exists()

    def test_unknown_conversation_raises(self, app_state, fake_chat):
        chat, _ = fake_chat
        try:
            chat.send("missing", "hi", run_async=False)
            raise AssertionError("expected KeyError")
        except KeyError:
            pass
