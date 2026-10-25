"""Core unit tests: paths, config, db, identity, events."""

from __future__ import annotations

import json
import time

from swarmbly_app.config import DEFAULTS, Config
from swarmbly_app.db import Database
from swarmbly_app.events import EventBus
from swarmbly_app.identity import (IdentityManager, b64url, b64url_decode,
                                   verify_signature)
from swarmbly_app.paths import DataDirs


class TestPaths:
    def test_layout_created(self, tmp_path):
        dirs = DataDirs(tmp_path / "data")
        dirs.ensure()
        assert dirs.sources.exists()
        assert dirs.wiki.exists()
        assert dirs.exports.exists()
        assert dirs.reports.exists()
        assert dirs.identity.exists()

    def test_output_is_logical_default(self, tmp_path):
        dirs = DataDirs(tmp_path / "data")
        assert str(dirs.output) == str(tmp_path / "data" / "output")

    def test_env_override(self, monkeypatch, tmp_path):
        monkeypatch.setenv("SWARMBLY_DATA_DIR", str(tmp_path / "custom"))
        assert DataDirs().root == tmp_path / "custom"


class TestConfig:
    def test_defaults(self, tmp_path):
        config = Config(DataDirs(tmp_path / "data"))
        assert config.get("language") == "en"
        assert config.get("swarm.mode") == "local"
        assert config.get("privacy.tier") == "LOCAL"
        assert config.get("lce.level") == "C0"
        assert config.get("lce.learning_enabled") is False

    def test_update_and_persist(self, tmp_path):
        dirs = DataDirs(tmp_path / "data")
        config = Config(dirs)
        config.update({"language": "es", "swarm": {"mode": "lan"}})
        assert config.get("language") == "es"
        assert config.get("swarm.mode") == "lan"
        # reload from disk
        again = Config(dirs)
        assert again.get("language") == "es"
        assert again.get("swarm.mode") == "lan"

    def test_dot_keys(self, tmp_path):
        config = Config(DataDirs(tmp_path / "data"))
        config.update({"model.model_name": "llama3.2:3b"})
        assert config.get("model.model_name") == "llama3.2:3b"

    def test_corrupt_file_recovers(self, tmp_path):
        dirs = DataDirs(tmp_path / "data")
        dirs.ensure()
        dirs.config_path().write_text("{not json", encoding="utf-8")
        config = Config(dirs)  # must not raise
        assert config.get("language") == "en"

    def test_reset(self, tmp_path):
        config = Config(DataDirs(tmp_path / "data"))
        config.update({"language": "es"})
        config.reset()
        assert config.get("language") == "en"

    def test_defaults_are_safe(self):
        # Safety-first defaults are part of the contract
        assert DEFAULTS["privacy"]["tier"] == "LOCAL"
        assert DEFAULTS["swarm"]["lan_enabled"] is False
        assert DEFAULTS["swarm"]["internet_enabled"] is False
        assert DEFAULTS["swarm"]["worker_enabled"] is False
        assert DEFAULTS["lce"]["learning_enabled"] is False


class TestDb:
    def test_conversation_crud(self, tmp_path):
        db = Database(tmp_path / "app.db")
        conv = db.create_conversation(title="Hello", mode="local", model="m:1b")
        assert db.get_conversation(conv["id"])["title"] == "Hello"
        assert db.list_conversations()
        db.delete_conversation(conv["id"])
        assert db.get_conversation(conv["id"]) is None
        db.close()

    def test_messages_roundtrip(self, tmp_path):
        db = Database(tmp_path / "app.db")
        conv = db.create_conversation()
        user = db.add_message(conv["id"], "user", "hi")
        assistant = db.add_message(conv["id"], "assistant", "hello",
                                   meta={"mode": "local"}, stages=[{"stage": "x"}])
        rows = db.get_messages(conv["id"])
        assert [r["role"] for r in rows] == ["user", "assistant"]
        db.update_message(assistant["id"], content="hello!")
        assert db.get_messages(conv["id"])[1]["content"] == "hello!"
        assert db.get_messages(conv["id"])[1]["meta"]["mode"] == "local"
        db.close()

    def test_node_cache_and_stats(self, tmp_path):
        db = Database(tmp_path / "app.db")
        db.upsert_node("nodeA", "10.0.0.2", 9000, verified=True,
                       profile={"models": []})
        assert db.list_nodes()[0]["node_id"] == "nodeA"
        db.add_stats("2026-10-11", tasks_served=1, tokens_out=12)
        db.add_stats("2026-10-11", tasks_served=1, tokens_out=8)
        stats = db.get_stats()
        assert stats[0]["tasks_served"] == 2
        assert stats[0]["tokens_out"] == 20
        db.close()


class TestIdentity:
    def test_roundtrip(self, tmp_path):
        mgr = IdentityManager(tmp_path / "identity" / "node_key")
        ident = mgr.load_or_create()
        assert len(ident.node_id) == 43  # 32 bytes base64url unpadded
        again = mgr.load_or_create()
        assert again.node_id == ident.node_id  # persistent

    def test_sign_verify(self, tmp_path):
        mgr = IdentityManager(tmp_path / "identity" / "node_key")
        ident = mgr.load_or_create()
        message = b"handshake transcript"
        sig = mgr.sign(message)
        assert verify_signature(ident.node_id, message, sig)
        assert not verify_signature(ident.node_id, b"other", sig)

    def test_b64url(self):
        assert b64url_decode(b64url(b"\x00\xff")) == b"\x00\xff"

    def test_permissions_0600(self, tmp_path):
        import stat
        mgr = IdentityManager(tmp_path / "identity" / "node_key")
        mgr.load_or_create()
        mode = stat.S_IMODE((tmp_path / "identity" / "node_key").stat().st_mode)
        assert mode == 0o600


class TestEvents:
    def test_publish_subscribe(self):
        bus = EventBus()
        seen: list[dict] = []
        bus.subscribe(seen.append)
        event = bus.publish("test.ping", value=1)
        assert seen == [event]
        assert event["type"] == "test.ping"
        assert event["payload"]["value"] == 1

    def test_history(self):
        bus = EventBus(history=2)
        bus.publish("a")
        bus.publish("b")
        bus.publish("c")
        assert [e["type"] for e in bus.recent()] == ["b", "c"]

    def test_broken_subscriber_isolated(self):
        bus = EventBus()

        def broken(event):
            raise RuntimeError("boom")

        seen: list[dict] = []
        bus.subscribe(broken)
        bus.subscribe(seen.append)
        bus.publish("x")  # must not raise
        assert len(seen) == 1

    def test_async_subscriber_from_background_thread(self):
        """Regression: chat/P2P publish from a non-asyncio thread; the async
        subscriber (WebSocket bridge) must still receive the event."""
        import asyncio
        import threading
        bus = EventBus()
        loop = asyncio.new_event_loop()
        bus.set_loop(loop)
        received: list[dict] = []

        async def handler(event):
            received.append(event)

        bus.subscribe_async(handler)

        def publish():
            bus.publish("thread.event", value=42)

        thread = threading.Thread(target=publish)
        thread.start()
        thread.join()
        # let the scheduled coroutine run on the captured loop
        loop.run_until_complete(asyncio.sleep(0.05))
        loop.close()
        assert len(received) == 1
        assert received[0]["payload"]["value"] == 42
