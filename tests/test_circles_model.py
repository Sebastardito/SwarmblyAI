"""Circle data model: signed manifests, invitations, storage and defaults."""

from __future__ import annotations

import json
import time

import pytest

from swarmbly_app.config import Config
from swarmbly_app.events import EventBus
from swarmbly_app.identity import IdentityManager
from swarmbly_app.paths import DataDirs
from swarmbly_app.p2p.circles import (E_CIRCLE_VERSION_ROLLBACK,
                                      E_INVITATION_EXPIRED,
                                      E_INVITATION_USED, CircleError,
                                      CircleService, build_manifest,
                                      decode_invitation, encode_invitation,
                                      invitation_svg, validate_invitation,
                                      validate_manifest)
from swarmbly_app.p2p.messages import WIRE_VERSION


def make_service(tmp_path):
    dirs = DataDirs(tmp_path / "data")
    dirs.ensure()
    config = Config(dirs)
    bus = EventBus()
    return CircleService(IdentityManager(dirs.identity_key_path()), config,
                         dirs, bus), config, dirs, bus


class TestManifest:
    def test_owner_signature_and_roundtrip(self, tmp_path):
        svc, _, _, _ = make_service(tmp_path)
        manifest = svc.create_circle("Familia")
        assert validate_manifest(manifest, now=int(time.time())) is manifest
        assert manifest["owner"] == svc.node_id
        assert manifest["members"][0]["node_id"] == svc.node_id

    def test_tampered_manifest_rejected(self, tmp_path):
        svc, _, _, _ = make_service(tmp_path)
        manifest = svc.create_circle("Familia")
        manifest["name"] = "Otra"
        with pytest.raises(CircleError, match="signature"):
            validate_manifest(manifest)

    def test_non_owner_signature_rejected(self, tmp_path):
        svc, config, dirs, bus = make_service(tmp_path)
        other = IdentityManager(dirs.root / "other_key")
        other.load_or_create()
        now = int(time.time())
        from swarmbly_app.p2p.circles import _sign
        manifest = _sign(other, {
            "v": WIRE_VERSION, "type": "circle_manifest",
            "circle_id": "abcdefgh", "name": "Fake", "owner": svc.node_id,
            "members": [{"node_id": svc.node_id, "name": "x",
                         "endpoints": []}],
            "version": 1, "issued_at": now, "expires_at": now + 3600})
        with pytest.raises(CircleError, match="signature"):
            validate_manifest(manifest)

    def test_expired_manifest_rejected(self, tmp_path):
        svc, _, _, _ = make_service(tmp_path)
        now = int(time.time())
        manifest = build_manifest(
            identity_manager=svc.identity_manager, circle_id="expired01",
            name="Expired", owner=svc.node_id,
            members=[{"node_id": svc.node_id, "name": "x", "endpoints": []}],
            version=1, issued_at=now - 7200, expires_at=now - 3600)
        with pytest.raises(CircleError, match="expired"):
            validate_manifest(manifest, now=now)
        with pytest.raises(CircleError, match="expired"):
            svc._store_manifest(manifest, now=now)

    def test_version_rollback_refused(self, tmp_path):
        svc, _, _, _ = make_service(tmp_path)
        v1 = svc.create_circle("Familia")
        now = int(time.time())
        v2 = build_manifest(
            identity_manager=svc.identity_manager, circle_id=v1["circle_id"],
            name=v1["name"], owner=v1["owner"], members=v1["members"],
            version=2, issued_at=now, expires_at=now + 3600)
        assert svc._store_manifest(v2, now=now) is True
        assert svc._store_manifest(v2, now=now) is False   # idempotent
        with pytest.raises(CircleError) as exc:
            svc._store_manifest(v1, now=now)
        assert exc.value.code == E_CIRCLE_VERSION_ROLLBACK

    def test_same_version_different_content_refused(self, tmp_path):
        svc, _, _, _ = make_service(tmp_path)
        v1 = svc.create_circle("Familia")
        now = int(time.time())
        changed = build_manifest(
            identity_manager=svc.identity_manager, circle_id=v1["circle_id"],
            name="Renamed", owner=v1["owner"], members=v1["members"],
            version=1, issued_at=now, expires_at=now + 3600)
        with pytest.raises(CircleError, match="same version"):
            svc._store_manifest(changed, now=now)


class TestInvitation:
    def test_roundtrip_and_qr(self, tmp_path):
        svc, _, _, _ = make_service(tmp_path)
        circle = svc.create_circle("Familia")
        invite = svc.invite(circle["circle_id"],
                            endpoints=["127.0.0.1:9765"])
        decoded = decode_invitation(invite["code"])
        assert decoded["circle_id"] == circle["circle_id"]
        assert decoded["owner"] == svc.node_id
        assert decoded["endpoints"] == ["127.0.0.1:9765"]
        svg = invitation_svg(invite["code"])
        assert svg.startswith("<svg") and svg.endswith("</svg>")
        assert invite["code"] not in svg          # the QR is modules, not text

    def test_tampered_invitation_rejected(self, tmp_path):
        svc, _, _, _ = make_service(tmp_path)
        circle = svc.create_circle("Familia")
        code = svc.invite(circle["circle_id"],
                          endpoints=["127.0.0.1:9765"])["code"]
        broken = code[:-3] + ("A" if code[-3] != "A" else "B") + code[-2:]
        with pytest.raises(CircleError):
            decode_invitation(broken)

    def test_expired_invitation_rejected(self, tmp_path):
        svc, _, _, _ = make_service(tmp_path)
        circle = svc.create_circle("Familia")
        now = int(time.time())
        from swarmbly_app.p2p.circles import _sign
        invitation = _sign(svc.identity_manager, {
            "v": WIRE_VERSION, "type": "circle_invitation",
            "circle_id": circle["circle_id"], "owner": svc.node_id,
            "nonce": "expired-nonce-1", "expires_at": now - 10,
            "endpoints": ["127.0.0.1:9765"]})
        code = encode_invitation(invitation)
        assert validate_invitation(invitation) is invitation  # signature is valid
        with pytest.raises(CircleError) as exc:
            decode_invitation(code, now=now)
        assert exc.value.code == E_INVITATION_EXPIRED

    def test_invitation_is_one_time(self, tmp_path):
        svc, _, dirs, _ = make_service(tmp_path)
        circle = svc.create_circle("Familia")
        invite = svc.invite(circle["circle_id"],
                            endpoints=["127.0.0.1:9765"])
        newcomer = IdentityManager(dirs.root / "newcomer_key")
        stranger = IdentityManager(dirs.root / "stranger_key")
        token = invite["code"]

        def join_request(identity):
            from swarmbly_app.p2p.circles import _sign
            return _sign(identity, {
                "v": WIRE_VERSION, "type": "circle_join_request",
                "circle_id": circle["circle_id"],
                "node_id": identity.load_or_create().node_id,
                "name": "newcomer", "endpoints": ["127.0.0.1:9766"],
                "token": token, "issued_at": int(time.time())})

        first = join_request(newcomer)
        ack = svc._on_join_request(first["node_id"], first)
        assert ack["status"] == "pending"
        second = join_request(stranger)
        with pytest.raises(CircleError) as exc:
            svc._on_join_request(second["node_id"], second)
        assert exc.value.code == E_INVITATION_USED


class TestStorageAndDefaults:
    def test_new_install_is_circle_only(self, tmp_path):
        dirs = DataDirs(tmp_path / "fresh")
        config = Config(dirs)
        assert config.get("circle.admission_mode") == "circle"
        assert config.get("circle.notice_pending") is False

    def test_existing_install_keeps_own_devices_with_notice(self, tmp_path):
        dirs = DataDirs(tmp_path / "old")
        dirs.ensure()
        dirs.config_path().write_text(json.dumps(
            {"swarm": {"lan_enabled": True}, "setup_completed": True}),
            encoding="utf-8")
        config = Config(dirs)
        assert config.get("circle.admission_mode") == "own_devices"
        assert config.get("circle.notice_pending") is True
        reloaded = Config(dirs)
        assert reloaded.get("circle.admission_mode") == "own_devices"
        assert reloaded.get("circle.notice_pending") is True

    def test_service_survives_restart(self, tmp_path):
        svc, config, dirs, bus = make_service(tmp_path)
        circle = svc.create_circle("Familia")
        invite = svc.invite(circle["circle_id"],
                            endpoints=["127.0.0.1:9765"])
        again = CircleService(IdentityManager(dirs.identity_key_path()),
                              config, dirs, bus)
        assert circle["circle_id"] in again.manifests
        assert decode_invitation(invite["code"])["nonce"] in again.invitations


def test_invalid_circle_name_refused(tmp_path):
    svc, _, _, _ = make_service(tmp_path)
    with pytest.raises(CircleError):
        svc.create_circle("   ")


def test_forged_circle_listing_this_node_is_not_accepted(tmp_path):
    """A peer cannot make this node a member of a circle it never joined."""
    import asyncio
    victim, _, dirs, _ = make_service(tmp_path)
    attacker = IdentityManager(dirs.root / "attacker_key")
    attacker_id = attacker.load_or_create().node_id
    now = int(time.time())
    forged = build_manifest(
        identity_manager=attacker, circle_id="forgedcircle", name="Fake",
        owner=attacker_id,
        members=[{"node_id": attacker_id, "name": "a", "endpoints": []},
                 {"node_id": victim.node_id, "name": "v", "endpoints": []}],
        version=1, issued_at=now, expires_at=now + 3600)
    reply = asyncio.run(victim.handle_control(
        attacker_id, {"v": WIRE_VERSION, "type": "circle_manifest",
                           "manifest": forged}))
    assert reply is None
    assert "forgedcircle" not in victim.manifests
    assert victim.admits_local(attacker_id)[0] is (victim.mode() == "own_devices")
