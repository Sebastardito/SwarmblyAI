# SPDX-License-Identifier: AGPL-3.0-only
from __future__ import annotations

import copy
import json

import pytest

from relay.manifest import (ManifestError, ManifestStore, document_circle_id,
                            parse_manifest)
from relay.protocol import b64url, canonical_bytes
from relay.tests.support import (make_identity, manifest_payload, sign_manifest,
                                 write_manifest)


def test_signed_manifest_is_read_tolerantly():
    owner = make_identity()
    member = make_identity()
    payload = manifest_payload(owner, [member])
    payload["members"] = [{"node_id": member.node_id, "name": "Seb"}]
    manifest = parse_manifest(sign_manifest(payload, owner))
    assert manifest.circle_id == "circle-test"
    assert manifest.owner_node_id == owner.node_id
    assert manifest.contains(member.node_id)
    assert manifest.version == 1
    assert manifest.expires_at is not None


def test_manifest_envelope_and_top_level_signature_are_both_accepted():
    owner = make_identity()
    member = make_identity()
    payload = manifest_payload(owner, [member])
    envelope = sign_manifest(payload, owner)
    top_level = dict(payload)
    top_level["sig"] = b64url(owner.sign(canonical_bytes(payload)))
    assert parse_manifest(envelope).members == parse_manifest(top_level).members


def test_tampered_manifest_is_refused():
    owner = make_identity()
    member = make_identity()
    document = sign_manifest(manifest_payload(owner, [member]), owner)
    document["manifest"]["members"].append(make_identity().node_id)
    with pytest.raises(ManifestError) as exc:
        parse_manifest(document)
    assert exc.value.code == "bad_manifest_signature"


def test_signature_from_another_owner_is_refused():
    owner = make_identity()
    other = make_identity()
    payload = manifest_payload(owner, [owner])
    document = sign_manifest(payload, other)
    with pytest.raises(ManifestError) as exc:
        parse_manifest(document)
    assert exc.value.code == "bad_manifest_signature"


def test_expired_manifest_is_refused():
    owner = make_identity()
    payload = manifest_payload(owner, [owner], expires_in_days=-1)
    with pytest.raises(ManifestError) as exc:
        parse_manifest(sign_manifest(payload, owner))
    assert exc.value.code == "manifest_expired"


def test_relay_endpoint_and_pin_are_extracted():
    from relay.client import RelayAddress

    owner = make_identity()
    address = RelayAddress("relay.example", 8765, "ab" * 32)
    manifest = parse_manifest(
        sign_manifest(manifest_payload(owner, [owner], relay=address), owner))
    assert manifest.relay is not None
    assert manifest.relay.host == "relay.example"
    assert manifest.relay.port == 8765
    assert manifest.relay.tls_fingerprint == "ab" * 32


def test_manifest_without_signature_is_refused():
    owner = make_identity()
    with pytest.raises(ManifestError) as exc:
        parse_manifest({"circle_id": "c", "owner": owner.node_id, "members": []})
    assert exc.value.code == "unsigned_manifest"


def test_store_reloads_a_higher_version_and_drops_a_revoked_member(tmp_path):
    owner = make_identity()
    member = make_identity()
    path = tmp_path / "circle.json"
    write_manifest(path, manifest_payload(owner, [owner, member]), owner)
    store = ManifestStore([path])
    assert store.reload(force=True)
    assert store.get("circle-test").contains(member.node_id)

    write_manifest(path, manifest_payload(owner, [owner], version=2), owner)
    assert store.reload(force=True)
    manifest = store.get("circle-test")
    assert manifest.version == 2
    assert not manifest.contains(member.node_id)


def test_a_bad_edit_does_not_replace_a_valid_manifest(tmp_path):
    owner = make_identity()
    path = tmp_path / "circle.json"
    write_manifest(path, manifest_payload(owner, [owner]), owner)
    store = ManifestStore([path])
    store.reload(force=True)

    path.write_text("{not json", encoding="utf-8")
    assert not store.reload(force=True)
    assert store.get("circle-test") is not None


def test_directory_input_loads_each_circle(tmp_path):
    owner = make_identity()
    write_manifest(tmp_path / "a.json",
                   manifest_payload(owner, [owner], circle_id="a"), owner)
    write_manifest(tmp_path / "b.json",
                   manifest_payload(owner, [owner], circle_id="b"), owner)
    store = ManifestStore([tmp_path])
    assert store.reload(force=True)
    assert {m.circle_id for m in store.all()} == {"a", "b"}


def test_manifest_parser_ignores_unknown_fields():
    owner = make_identity()
    payload = manifest_payload(owner, [owner])
    payload["future_field"] = {"anything": [1, 2, 3]}
    document = sign_manifest(payload, owner)
    assert parse_manifest(document).members == {owner.node_id}


def test_manifest_json_round_trip(tmp_path):
    owner = make_identity()
    payload = manifest_payload(owner, [owner])
    path = tmp_path / "m.json"
    path.write_text(json.dumps(sign_manifest(copy.deepcopy(payload), owner)))
    assert parse_manifest(json.loads(path.read_text())).owner_node_id == owner.node_id


def test_a_malformed_expiry_is_not_treated_as_never_expiring():
    owner = make_identity()
    payload = manifest_payload(owner, [owner])
    payload["expires_at"] = "not-a-date"
    with pytest.raises(ManifestError) as exc:
        parse_manifest(sign_manifest(payload, owner))
    assert exc.value.code == "invalid_manifest"


def test_document_circle_id_reads_envelopes_without_verifying():
    owner = make_identity()
    payload = manifest_payload(owner, [owner])
    document = sign_manifest(payload, owner)
    assert document_circle_id(document) == "circle-test"
    assert document_circle_id(payload) == "circle-test"
    assert document_circle_id({"manifest": {"circle": "c2"}, "sig": "x"}) == "c2"
    assert document_circle_id({"manifest": {"id": "c3"}, "sig": "x"}) == "c3"
    assert document_circle_id({"manifest": {}, "sig": "x"}) is None
    assert document_circle_id({"sig": "x"}) is None


def test_commit_persists_a_pushed_version_and_a_restart_reads_it(tmp_path):
    owner = make_identity()
    member = make_identity()
    path = tmp_path / "circle.json"
    write_manifest(path, manifest_payload(owner, [owner, member]), owner)
    store = ManifestStore([path])
    store.reload(force=True)

    payload = manifest_payload(owner, [owner], version=2)
    document = sign_manifest(payload, owner)
    parsed = parse_manifest(document)
    target = store.commit(parsed, document)

    assert target == path
    assert store.get("circle-test").version == 2
    assert not store.get("circle-test").contains(member.node_id)
    assert parse_manifest(json.loads(path.read_text())).version == 2

    restarted = ManifestStore([path])
    restarted.reload(force=True)
    assert restarted.get("circle-test").version == 2
    assert not restarted.get("circle-test").contains(member.node_id)


def test_a_directory_store_writes_an_in_memory_manifest_by_circle_id(tmp_path):
    owner = make_identity()
    store = ManifestStore([tmp_path])
    payload = manifest_payload(owner, [owner], circle_id="circle/a")
    document = sign_manifest(payload, owner)
    target = store.commit(parse_manifest(document), document)
    assert target.parent == tmp_path
    assert target.name == "circle_a.json"
    assert target.exists()

