# SPDX-License-Identifier: AGPL-3.0-only
"""Owner push of signed manifest versions (D-023)."""

from __future__ import annotations

import asyncio
import json
import logging

import pytest

from relay.client import RelayAddress, RelayClient, RelayRefused
from relay.manifest import parse_manifest
from relay.protocol import read_frame
from relay.server import RelayConfig, RelayServer
from relay.tests.support import (make_identity, manifest_payload, sign_manifest,
                                 start_relay)

CIRCLE = "circle-test"


def _client(address: RelayAddress, identity) -> RelayClient:
    return RelayClient(address, CIRCLE, identity.node_id, identity.sign,
                       timeout=5.0, pair_timeout=5.0)


async def _pair(first: RelayClient, second: RelayClient):
    return await asyncio.gather(first.pair(second.node_id), second.accept_pair())


async def _reader_closed(reader, timeout: float = 3.0) -> bool:
    try:
        return await asyncio.wait_for(reader.read(1), timeout) == b""
    except (ConnectionError, OSError, asyncio.IncompleteReadError):
        return True


def test_owner_push_is_accepted_persisted_and_survives_restart(tmp_path):
    async def run():
        owner, member = make_identity(), make_identity()
        server, address = await start_relay(tmp_path, owner, [owner, member])
        client = _client(address, owner)
        try:
            await client.connect()
            document = sign_manifest(
                manifest_payload(owner, [owner], version=2), owner)
            ack = await client.push_manifest(document)
            assert ack["type"] == "manifest_ack"
            assert ack["version"] == 2
            assert ack["member_count"] == 1
            held = server.store.get(CIRCLE)
            assert held.version == 2
            assert not held.contains(member.node_id)
            path = server.config.manifests[0]
            on_disk = parse_manifest(json.loads(path.read_text(encoding="utf-8")))
            assert on_disk.version == 2
            assert not on_disk.contains(member.node_id)
        finally:
            await client.close()
            config = server.config
            await server.stop()

        restarted = RelayServer(RelayConfig(
            manifests=config.manifests, certfile=config.certfile,
            keyfile=config.keyfile, host="127.0.0.1", port=0))
        await restarted.start()
        try:
            held = restarted.store.get(CIRCLE)
            assert held.version == 2
            assert not held.contains(member.node_id)
            new_address = RelayAddress("127.0.0.1", restarted.port,
                                       address.tls_fingerprint)
            with pytest.raises(RelayRefused) as exc:
                await _client(new_address, member).connect()
            assert exc.value.code == "not_a_member"
        finally:
            await restarted.stop()

    asyncio.run(run())


def test_equal_and_lower_versions_are_refused_and_the_connection_stays(tmp_path):
    async def run():
        owner = make_identity()
        server, address = await start_relay(tmp_path, owner, [owner])
        client = _client(address, owner)
        try:
            await client.connect()
            for version in (1, 0):
                with pytest.raises(RelayRefused) as exc:
                    await client.push_manifest(sign_manifest(
                        manifest_payload(owner, [owner], version=version), owner))
                assert exc.value.code == "stale_version"
            ack = await client.push_manifest(sign_manifest(
                manifest_payload(owner, [owner], version=2), owner))
            assert ack["version"] == 2
            assert server.store.get(CIRCLE).version == 2
        finally:
            await client.close()
            await server.stop()

    asyncio.run(run())


def test_a_member_who_claims_to_be_owner_is_refused(tmp_path):
    async def run():
        owner, member = make_identity(), make_identity()
        server, address = await start_relay(tmp_path, owner, [owner, member])
        client = _client(address, member)
        try:
            await client.connect()
            # The document verifies under the member's key and names the
            # member as owner; authority still comes from the held manifest.
            payload = manifest_payload(member, [owner, member], version=2)
            with pytest.raises(RelayRefused) as exc:
                await client.push_manifest(sign_manifest(payload, member))
            assert exc.value.code == "not_owner"
            assert server.store.get(CIRCLE).version == 1
            assert server.store.get(CIRCLE).owner_node_id == owner.node_id
        finally:
            await client.close()
            await server.stop()

    asyncio.run(run())


def test_a_forged_signature_is_refused(tmp_path):
    async def run():
        owner, other = make_identity(), make_identity()
        server, address = await start_relay(tmp_path, owner, [owner, other])
        client = _client(address, owner)
        try:
            await client.connect()
            payload = manifest_payload(owner, [owner], version=2)
            with pytest.raises(RelayRefused) as exc:
                await client.push_manifest(sign_manifest(payload, other))
            assert exc.value.code == "bad_signature"
            assert server.store.get(CIRCLE).version == 1
        finally:
            await client.close()
            await server.stop()

    asyncio.run(run())


def test_an_owner_change_is_refused(tmp_path):
    async def run():
        owner, new_owner = make_identity(), make_identity()
        server, address = await start_relay(tmp_path, owner, [owner])
        client = _client(address, owner)
        try:
            await client.connect()
            payload = manifest_payload(owner, [owner, new_owner], version=2)
            payload["owner"] = new_owner.node_id
            document = sign_manifest(payload, new_owner)
            with pytest.raises(RelayRefused) as exc:
                await client.push_manifest(document)
            assert exc.value.code == "owner_change_refused"
            held = server.store.get(CIRCLE)
            assert held.version == 1
            assert held.owner_node_id == owner.node_id
        finally:
            await client.close()
            await server.stop()

    asyncio.run(run())


def test_a_push_for_an_unserved_circle_is_unknown(tmp_path):
    async def run():
        owner = make_identity()
        server, address = await start_relay(tmp_path, owner, [owner])
        client = _client(address, owner)
        try:
            await client.connect()
            document = sign_manifest(
                manifest_payload(owner, [owner], circle_id="circle-elsewhere",
                                 version=2), owner)
            with pytest.raises(RelayRefused) as exc:
                await client.push_manifest(document)
            assert exc.value.code == "unknown_circle"
        finally:
            await client.close()
            await server.stop()

    asyncio.run(run())


def test_an_expired_manifest_is_refused(tmp_path):
    async def run():
        owner = make_identity()
        server, address = await start_relay(tmp_path, owner, [owner])
        client = _client(address, owner)
        try:
            await client.connect()
            document = sign_manifest(
                manifest_payload(owner, [owner], version=2,
                                 expires_in_days=-1), owner)
            with pytest.raises(RelayRefused) as exc:
                await client.push_manifest(document)
            assert exc.value.code == "expired"
            assert server.store.get(CIRCLE).version == 1
        finally:
            await client.close()
            await server.stop()

    asyncio.run(run())


def test_an_oversized_manifest_is_refused(tmp_path):
    async def run():
        owner = make_identity()
        server, address = await start_relay(
            tmp_path, owner, [owner], max_manifest_bytes=1024)
        client = _client(address, owner)
        try:
            await client.connect()
            payload = manifest_payload(owner, [owner], version=2)
            payload["padding"] = "x" * 4096
            with pytest.raises(RelayRefused) as exc:
                await client.push_manifest(sign_manifest(payload, owner))
            assert exc.value.code == "too_large"
            assert server.store.get(CIRCLE).version == 1
        finally:
            await client.close()
            await server.stop()

    asyncio.run(run())


def test_revocation_closes_registrations_and_splices_and_blocks_reentry(tmp_path):
    async def run():
        owner, a, c, d = (make_identity() for _ in range(4))
        server, address = await start_relay(tmp_path, owner, [owner, a, c, d])
        owner_client = _client(address, owner)
        c_idle = _client(address, c)
        c_splice = _client(address, c)
        a_client = _client(address, a)
        try:
            await owner_client.connect()
            await c_idle.connect()
            await c_splice.connect()
            await a_client.connect()
            stream_c, stream_a = await _pair(c_splice, a_client)

            document = sign_manifest(
                manifest_payload(owner, [owner, a, d], version=2), owner)
            ack = await owner_client.push_manifest(document)
            assert ack["version"] == 2

            # The idle registration gets a revocation error, then EOF.
            notice = await read_frame(c_idle.reader, timeout=3.0)
            assert notice["type"] == "error"
            assert notice["code"] == "revoked"
            assert await _reader_closed(c_idle.reader)
            # The open splice is cut at once; the peer's side ends too.
            assert await _reader_closed(stream_c.reader)
            assert await _reader_closed(stream_a.reader)

            # A revoked node cannot register again.
            with pytest.raises(RelayRefused) as exc:
                await _client(address, c).connect()
            assert exc.value.code == "not_a_member"

            # A current member cannot pair with it either.
            a_again = _client(address, a)
            try:
                await a_again.connect()
                with pytest.raises(RelayRefused) as exc:
                    await a_again.pair(c.node_id)
                assert exc.value.code == "not_a_member"
            finally:
                await a_again.close()
        finally:
            for client in (owner_client, c_idle, c_splice, a_client):
                await client.close()
            await server.stop()

    asyncio.run(run())


def test_pushes_are_rate_limited_per_owner(tmp_path):
    async def run():
        owner = make_identity()
        server, address = await start_relay(
            tmp_path, owner, [owner], manifest_pushes_per_hour=2)
        client = _client(address, owner)
        try:
            await client.connect()
            for version in (2, 3):
                ack = await client.push_manifest(sign_manifest(
                    manifest_payload(owner, [owner], version=version), owner))
                assert ack["version"] == version
            with pytest.raises(RelayRefused) as exc:
                await client.push_manifest(sign_manifest(
                    manifest_payload(owner, [owner], version=4), owner))
            assert exc.value.code == "rate_limited"
            assert server.store.get(CIRCLE).version == 3
        finally:
            await client.close()
            await server.stop()

    asyncio.run(run())


def test_push_metadata_log_has_no_member_list(tmp_path, caplog):
    caplog.set_level(logging.INFO, logger="swarmbly.relay")

    async def run():
        owner, member = make_identity(), make_identity()
        server, address = await start_relay(tmp_path, owner, [owner, member])
        client = _client(address, owner)
        try:
            await client.connect()
            await client.push_manifest(sign_manifest(
                manifest_payload(owner, [owner], version=2), owner))
        finally:
            await client.close()
            await server.stop()
        return member

    member = asyncio.run(run())
    text = caplog.text
    assert "manifest push accepted" in text
    assert "version=2" in text
    assert "members=1" in text
    # The owner's short node prefix is metadata; the removed member's id is not.
    assert member.node_id not in text
    assert member.node_id[:12] not in text
    assert "members: [" not in text
