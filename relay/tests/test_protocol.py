# SPDX-License-Identifier: AGPL-3.0-only
from __future__ import annotations

import asyncio
import json
import struct

import pytest

from relay.protocol import (MAX_FRAME_BYTES, FrameError, b64url, canonical_bytes,
                            encode_frame, frame_size, manifest_ack_frame,
                            manifest_refused_frame, read_frame,
                            sign_register_proof, verify_register_proof)
from relay.tests.support import make_identity


def test_frame_round_trip():
    async def run():
        reader = asyncio.StreamReader()
        message = {"type": "register", "circle_id": "c", "node_id": "n"}
        reader.feed_data(encode_frame(message))
        assert await read_frame(reader) == message

    asyncio.run(run())


def test_frame_size_is_bounded():
    async def run():
        reader = asyncio.StreamReader()
        reader.feed_data(struct.pack(">I", MAX_FRAME_BYTES + 1))
        with pytest.raises(FrameError):
            await read_frame(reader)

    asyncio.run(run())


def test_oversized_encode_is_refused():
    with pytest.raises(FrameError):
        encode_frame({"x": "a" * (MAX_FRAME_BYTES + 1)})


def test_canonical_bytes_are_stable_and_compact():
    first = canonical_bytes({"b": 1, "a": [True, None, "ñ"]})
    second = canonical_bytes({"a": [True, None, "ñ"], "b": 1})
    assert first == second
    assert b" " not in first
    assert "ñ".encode() in first
    assert json.loads(first) == {"a": [True, None, "ñ"], "b": 1}


def test_register_proof_verifies_only_for_the_right_key_and_challenge():
    identity = make_identity()
    other = make_identity()
    nonce = b"\x01" * 32
    proof = sign_register_proof(identity.sign, "circle", identity.node_id, nonce)
    assert verify_register_proof("circle", identity.node_id, nonce, proof)
    assert not verify_register_proof("circle", other.node_id, nonce, proof)
    assert not verify_register_proof("circle", identity.node_id, b"\x02" * 32, proof)
    assert not verify_register_proof("other", identity.node_id, nonce, proof)
    assert not verify_register_proof("circle", identity.node_id, nonce, "nope")


def test_base64url_has_no_padding():
    assert "=" not in b64url(b"abc")
    assert b64url(b"") == ""


def test_frame_size_matches_the_encoded_body():
    message = {"type": "manifest_ack", "circle_id": "c", "version": 2}
    assert frame_size(message) == len(encode_frame(message)) - 4


def test_manifest_ack_carries_metadata_not_members():
    ack = manifest_ack_frame("circle-test", 4, 7)
    assert ack == {"type": "manifest_ack", "v": 1, "circle_id": "circle-test",
                   "version": 4, "member_count": 7}
    refused = manifest_refused_frame("stale_version", "already held")
    assert refused["type"] == "manifest_refused"
    assert refused["code"] == "stale_version"
    assert refused["message"] == "already held"

