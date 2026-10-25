"""SPEC v0.2 wire codec tests."""

from __future__ import annotations

import json

import pytest

from swarmbly_app.identity import IdentityManager
from swarmbly_app.p2p.messages import (
    WIRE_VERSION, attempt_id_for, canonical_bytes, decode_frame, encode_frame,
    error, new_session_id, packet, result, task_id_for, verify_signed,
    VersionMismatch, WireError)


class TestFrames:
    def test_roundtrip(self):
        message = {"v": WIRE_VERSION, "type": "hello", "node_id": "abc"}
        decoded = decode_frame(encode_frame(message))
        assert decoded == message

    def test_missing_version_rejected(self):
        with pytest.raises(WireError):
            decode_frame(encode_frame({"type": "hello"}))

    def test_major_version_mismatch(self):
        with pytest.raises(VersionMismatch):
            decode_frame(encode_frame({"v": "1.0", "type": "hello"}))

    def test_minor_version_tolerated(self):
        decoded = decode_frame(encode_frame({"v": "0.9", "type": "hello",
                                             "unknown_field": True}))
        assert decoded["type"] == "hello"  # unknown fields are ignored

    def test_oversized_frame_rejected(self):
        with pytest.raises(WireError):
            encode_frame({"v": WIRE_VERSION, "payload": "x" * (5 * 1024 * 1024)})


class TestTaskIds:
    def test_derivation_is_stable_and_one_way(self):
        session = new_session_id()
        assert len(session) == 16
        a = task_id_for(session, 0, 1)
        b = task_id_for(session, 0, 1)
        c = task_id_for(session, 1, 1)
        assert a == b and a != c
        assert len(a) == 32  # 16-byte hex digest
        assert attempt_id_for(a, 0) == f"{a}:0"

    def test_session_id_never_serialized(self):
        """SPEC §4: session_id is never transmitted to a worker."""
        session = new_session_id()
        task_id = task_id_for(session, 0, 0)
        wire = packet(attempt_id_for(task_id, 0), {}, [], {"instruction": "x"})
        text = json.dumps(wire)
        assert "session_id" not in text
        assert session.hex() not in text


class TestSignatures:
    def test_result_signature_verifies(self, tmp_path):
        manager = IdentityManager(tmp_path / "id" / "node_key")
        ident = manager.load_or_create()
        reply = result("task:0", "text", {"model_family": "x"},
                       {"gen_ms": 1}, b"")
        unsigned = {k: v for k, v in reply.items() if k != "sig"}
        sig = manager.sign(canonical_bytes(unsigned))
        import base64
        reply["sig"] = base64.urlsafe_b64encode(sig).rstrip(b"=").decode()
        assert verify_signed(ident.node_id, reply)
        reply["text"] = "tampered"
        assert not verify_signed(ident.node_id, reply)


class TestCanonical:
    def test_stable_serialization(self):
        a = canonical_bytes({"b": 1, "a": [1, 2], "c": None})
        b = canonical_bytes({"a": [1, 2], "c": None, "b": 1})
        assert a == b
        assert json.loads(a.decode()) == {"a": [1, 2], "b": 1, "c": None}
