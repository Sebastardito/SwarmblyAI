"""Handshake tests: happy path, replay, signature attacks, channel binding."""

from __future__ import annotations

import base64

import pytest

from swarmbly_app.identity import IdentityManager
from swarmbly_app.p2p.handshake import (Handshake, sign_advertisement_update,
                                        validate_advertisement,
                                        verify_advertisement_update)
from swarmbly_app.p2p.messages import WireError, canonical_bytes

FP_B = "b" * 64            # fingerprint of the responder's real TLS certificate
FP_MITM = "e" * 64         # certificate presented by an interceptor


@pytest.fixture()
def pair(tmp_path):
    a = IdentityManager(tmp_path / "a" / "node_key")
    b = IdentityManager(tmp_path / "b" / "node_key")
    adv_a = {"node_id": a.load_or_create().node_id,
             "models": [{"family": "llama", "version": "llama3.2:3b"}],
             "policy": {"kinds": ["generate"]}, "resources": {}, "capabilities": {}}
    adv_b = {"node_id": b.load_or_create().node_id,
             "models": [{"family": "qwen2", "version": "qwen2.5:3b"}],
             "policy": {"kinds": ["generate"]}, "resources": {}, "capabilities": {}}
    return (Handshake(a, adv_a, tls_fingerprint="a" * 64),
            Handshake(b, adv_b, tls_fingerprint=FP_B), a, b, adv_a, adv_b)


def _complete(pair, observed=FP_B):
    initiator, responder, ida, idb, adv_a, adv_b = pair
    hello, nonce = initiator.build_hello()
    ack_message, own_nonce = responder.build_hello_ack(hello)
    result = initiator.verify_ack(ack_message, nonce, observed)
    final = initiator.build_final_ack(_nonce(ack_message["nonce"]), observed, adv_a)
    confirmed = responder.verify_final_ack(final, ida.load_or_create().node_id,
                                           own_nonce)
    return result, confirmed


class TestHandshake:
    def test_full_exchange(self, pair):
        _, _, ida, idb, adv_a, adv_b = pair
        result, confirmed = _complete(pair)
        assert result.node_id == idb.load_or_create().node_id
        assert result.advertisement == adv_b
        assert confirmed.node_id == ida.load_or_create().node_id
        # The initiator's advertisement is now authenticated (signed in the ack).
        assert confirmed.advertisement == adv_a

    def test_mitm_certificate_rejected(self, pair):
        """An interceptor terminating TLS shows its own certificate: the
        initiator aborts before signing anything."""
        with pytest.raises(WireError, match="man in the middle"):
            _complete(pair, observed=FP_MITM)

    def test_final_ack_bound_to_other_channel_rejected(self, pair):
        initiator, responder, ida, idb, adv_a, _ = pair
        hello, nonce = initiator.build_hello()
        ack_message, own_nonce = responder.build_hello_ack(hello)
        final = initiator.build_final_ack(_nonce(ack_message["nonce"]), FP_MITM, adv_a)
        with pytest.raises(WireError):
            responder.verify_final_ack(final, ida.load_or_create().node_id, own_nonce)

    def test_unbound_legacy_hello_rejected(self, pair):
        initiator, responder, *_ = pair
        hello, _ = initiator.build_hello()
        hello.pop("hs")
        with pytest.raises(WireError, match="upgrade"):
            responder.build_hello_ack(hello)

    def test_replay_old_ack_rejected(self, pair):
        initiator, responder, *_ = pair
        hello, nonce = initiator.build_hello()
        ack_message, _ = responder.build_hello_ack(hello)
        _, nonce2 = initiator.build_hello()
        with pytest.raises(WireError):
            initiator.verify_ack(ack_message, nonce2, FP_B)

    def test_tampered_ack_rejected(self, pair):
        initiator, responder, *_ = pair
        hello, nonce = initiator.build_hello()
        ack_message, _ = responder.build_hello_ack(hello)
        ack_message["advertisement"] = {"node_id": "attacker"}
        with pytest.raises(WireError):
            initiator.verify_ack(ack_message, nonce, FP_B)

    def test_tampered_initiator_advertisement_rejected(self, pair):
        initiator, responder, ida, idb, adv_a, _ = pair
        hello, nonce = initiator.build_hello()
        ack_message, own_nonce = responder.build_hello_ack(hello)
        final = initiator.build_final_ack(_nonce(ack_message["nonce"]), FP_B, adv_a)
        final["advertisement"] = dict(adv_a, policy={"kinds": ["judge"]})
        with pytest.raises(WireError):
            responder.verify_final_ack(final, ida.load_or_create().node_id, own_nonce)

    def test_forged_signature_rejected(self, pair):
        initiator, responder, ida, *_ = pair
        hello, nonce = initiator.build_hello()
        ack_message, _ = responder.build_hello_ack(hello)
        unsigned = {k: v for k, v in ack_message.items() if k != "sig"}
        ack_message["sig"] = _b64(ida.sign(canonical_bytes(unsigned)))
        with pytest.raises(WireError):
            initiator.verify_ack(ack_message, nonce, FP_B)

    def test_short_nonce_rejected(self, pair):
        initiator, responder, *_ = pair
        hello, _ = initiator.build_hello()
        hello["nonce"] = _b64(b"short")
        with pytest.raises(WireError):
            responder.build_hello_ack(hello)


class TestAdvertisementUpdate:
    def test_signed_update_roundtrip(self, pair):
        _, _, ida, _, adv_a, _ = pair
        node_id = ida.load_or_create().node_id
        msg = sign_advertisement_update(ida, adv_a, seq=3)
        assert verify_advertisement_update(node_id, msg)
        msg["advertisement"] = dict(adv_a, models=[])
        assert not verify_advertisement_update(node_id, msg)


class TestAdvertisement:
    def test_valid(self, pair):
        adv_a = pair[4]
        assert validate_advertisement(adv_a, adv_a["node_id"]) == []

    def test_missing_node_id(self):
        problems = validate_advertisement({"models": []})
        assert any("node_id" in p for p in problems)

    def test_node_id_must_match_authenticated(self, pair):
        adv_a = pair[4]
        problems = validate_advertisement(adv_a, expected_node_id="someone-else")
        assert any("differs" in p for p in problems)

    def test_model_without_family(self):
        problems = validate_advertisement({"node_id": "x", "models": [{"version": "1"}]})
        assert any("family" in p for p in problems)

    def test_markup_in_family_rejected(self):
        """Advertisements are untrusted: markup never reaches the UI."""
        problems = validate_advertisement(
            {"node_id": "x", "models": [{"family": "<img src=x onerror=alert(1)>"}]})
        assert any("disallowed" in p for p in problems)

    def test_unknown_kind_rejected(self):
        problems = validate_advertisement(
            {"node_id": "x", "models": [], "policy": {"kinds": ["rm -rf"]}})
        assert any("kinds" in p for p in problems)


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _nonce(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))
