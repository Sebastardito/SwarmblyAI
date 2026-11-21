# SPDX-License-Identifier: AGPL-3.0-only
from __future__ import annotations

import asyncio
import contextlib
import logging
import struct

import pytest

from relay.client import RelayAddress, RelayClient, RelayRefused
from relay.protocol import (MAX_FRAME_BYTES, RelayError, b64url_decode, read_frame,
                            sign_register_proof, write_frame)
from relay.tests.support import (client_tls_context, make_cert, make_identity,
                                 manifest_payload, raw_connection, server_tls_context,
                                 start_relay, write_manifest)
from relay.tls import TLSStream

CIRCLE = "circle-test"


def _client(address: RelayAddress, identity) -> RelayClient:
    return RelayClient(address, CIRCLE, identity.node_id, identity.sign,
                       timeout=5.0, pair_timeout=5.0)


async def _pair(first: RelayClient, second: RelayClient):
    return await asyncio.gather(first.pair(second.node_id), second.accept_pair())


async def _read_until_eof(reader, timeout: float = 3.0) -> bytes:
    try:
        return await asyncio.wait_for(reader.read(), timeout)
    except (ConnectionError, asyncio.IncompleteReadError):
        return b""


async def _recv_exact(stream: TLSStream, size: int) -> bytes:
    chunks = bytearray()
    while len(chunks) < size:
        chunk = await asyncio.wait_for(stream.recv(size - len(chunks)), 3.0)
        if not chunk:
            break
        chunks.extend(chunk)
    return bytes(chunks)


def test_register_with_a_signed_challenge(tmp_path):
    async def run():
        owner, member = make_identity(), make_identity()
        server, address = await start_relay(tmp_path, owner, [owner, member])
        try:
            client = _client(address, member)
            await client.connect()
            assert client.registered
            await client.close()
        finally:
            await server.stop()

    asyncio.run(run())


def test_a_non_member_cannot_register(tmp_path):
    async def run():
        owner, outsider = make_identity(), make_identity()
        server, address = await start_relay(tmp_path, owner, [owner])
        try:
            with pytest.raises(RelayRefused) as exc:
                await _client(address, outsider).connect()
            assert exc.value.code == "not_a_member"
        finally:
            await server.stop()

    asyncio.run(run())


def test_a_relay_with_a_different_certificate_is_refused(tmp_path):
    async def run():
        owner = make_identity()
        server, address = await start_relay(tmp_path, owner, [owner])
        try:
            wrong = RelayAddress(address.host, address.port, "00" * 32)
            with pytest.raises(RelayError) as exc:
                await _client(wrong, owner).connect()
            assert exc.value.code == "relay_certificate_mismatch"
        finally:
            await server.stop()

    asyncio.run(run())


def test_replayed_registration_is_refused(tmp_path):
    async def run():
        owner, member = make_identity(), make_identity()
        server, address = await start_relay(tmp_path, owner, [owner, member])
        try:
            reader, writer = await raw_connection(address)
            await write_frame(writer, {"type": "register", "v": 1,
                                       "circle_id": CIRCLE, "node_id": member.node_id})
            challenge = await read_frame(reader)
            nonce = b64url_decode(challenge["nonce"])
            proof = sign_register_proof(member.sign, CIRCLE, member.node_id, nonce)
            await write_frame(writer, {"type": "register_proof", "signature": proof})
            assert (await read_frame(reader))["type"] == "registered"
            writer.close()
            with contextlib.suppress(Exception):
                await writer.wait_closed()

            # A fresh connection gets a fresh challenge; the captured proof is useless.
            reader, writer = await raw_connection(address)
            await write_frame(writer, {"type": "register", "v": 1,
                                       "circle_id": CIRCLE, "node_id": member.node_id})
            await read_frame(reader)  # new challenge, not the one that was signed
            await write_frame(writer, {"type": "register_proof", "signature": proof})
            reply = await read_frame(reader)
            assert reply["type"] == "error"
            assert reply["code"] == "bad_register_proof"
            writer.close()
            with contextlib.suppress(Exception):
                await writer.wait_closed()
        finally:
            await server.stop()

    asyncio.run(run())


def test_pair_splices_bytes_both_ways(tmp_path):
    async def run():
        owner, a, b = make_identity(), make_identity(), make_identity()
        server, address = await start_relay(tmp_path, owner, [owner, a, b])
        first, second = _client(address, a), _client(address, b)
        try:
            await first.connect()
            await second.connect()
            stream_a, stream_b = await _pair(first, second)
            assert stream_a.role == "initiator"
            assert stream_b.role == "responder"
            await stream_a.sendall(b"from-a")
            assert await asyncio.wait_for(stream_b.readexactly(6), 3.0) == b"from-a"
            await stream_b.sendall(b"from-b")
            assert await asyncio.wait_for(stream_a.readexactly(6), 3.0) == b"from-b"
            stream_a.close()
            stream_b.close()
        finally:
            await first.close()
            await second.close()
            await server.stop()

    asyncio.run(run())


def test_pair_to_a_non_member_is_refused(tmp_path):
    async def run():
        owner, member, outsider = make_identity(), make_identity(), make_identity()
        server, address = await start_relay(tmp_path, owner, [owner, member])
        client = _client(address, member)
        try:
            await client.connect()
            with pytest.raises(RelayRefused) as exc:
                await client.pair(outsider.node_id)
            assert exc.value.code == "not_a_member"
        finally:
            await client.close()
            await server.stop()

    asyncio.run(run())


def test_pair_to_an_unconnected_member_is_refused(tmp_path):
    async def run():
        owner, member, absent = make_identity(), make_identity(), make_identity()
        server, address = await start_relay(tmp_path, owner, [owner, member, absent])
        client = _client(address, member)
        try:
            await client.connect()
            with pytest.raises(RelayRefused) as exc:
                await client.pair(absent.node_id)
            assert exc.value.code == "peer_not_connected"
        finally:
            await client.close()
            await server.stop()

    asyncio.run(run())


def test_a_real_tls13_session_runs_through_the_splice(tmp_path, caplog):
    caplog.set_level(logging.DEBUG, logger="swarmbly.relay")

    async def run():
        owner, a, b = make_identity(), make_identity(), make_identity()
        server, address = await start_relay(tmp_path, owner, [owner, a, b])
        node_cert, node_key, _ = make_cert(tmp_path, "node-b")
        first, second = _client(address, a), _client(address, b)
        try:
            await first.connect()
            await second.connect()
            stream_a, stream_b = await _pair(first, second)

            tls_client = TLSStream(stream_a, client_tls_context(node_cert),
                                   server_side=False, server_hostname="node-b")
            tls_server = TLSStream(stream_b, server_tls_context(node_cert, node_key),
                                   server_side=True)
            await asyncio.gather(tls_client.do_handshake(), tls_server.do_handshake())
            assert tls_client.version() == "TLSv1.3"
            assert tls_server.version() == "TLSv1.3"

            marker = b"PLAINTEXT-MARKER-c7f5a1d9"
            await tls_client.sendall(marker)
            assert await _recv_exact(tls_server, len(marker)) == marker
            answer = b"answer-through-the-relay"
            await tls_server.sendall(answer)
            assert await _recv_exact(tls_client, len(answer)) == answer

            # The relay forwarded the inner TLS records, never the marker.
            forwarded = bytes(server.forwarded)
            assert forwarded
            assert marker not in forwarded
            assert marker.decode() not in caplog.text
            assert b"answer-through-the-relay" not in forwarded
        finally:
            with contextlib.suppress(Exception):
                await tls_client.close()
            with contextlib.suppress(Exception):
                await tls_server.close()
            await first.close()
            await second.close()
            await server.stop()

    asyncio.run(run())


def test_concurrent_splices_per_member_are_limited(tmp_path):
    async def run():
        owner, a1, b1, b2 = (make_identity() for _ in range(4))
        server, address = await start_relay(
            tmp_path, owner, [owner, a1, b1, b2],
            max_splices_per_member=1)
        # Two connections for the same member: the limit is per node, not per
        # connection, so the second splice of a1 must be refused.
        first_a = _client(address, a1)
        second_a = _client(address, a1)
        first_b = _client(address, b1)
        second_b = _client(address, b2)
        clients = [first_a, second_a, first_b, second_b]
        try:
            for client in clients:
                await client.connect()
            stream_a, stream_b = await _pair(first_a, first_b)
            assert stream_a is not None and stream_b is not None

            waiting = asyncio.create_task(second_b.accept_pair())
            with pytest.raises(RelayRefused) as exc:
                await asyncio.wait_for(second_a.pair(second_b.node_id), 5.0)
            assert exc.value.code == "limit_splices"
            waiting.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await waiting
            stream_a.close()
            stream_b.close()
        finally:
            for client in clients:
                await client.close()
            await server.stop()

    asyncio.run(run())


def test_the_daily_byte_budget_closes_the_splice(tmp_path):
    async def run():
        owner, a, b = make_identity(), make_identity(), make_identity()
        server, address = await start_relay(
            tmp_path, owner, [owner, a, b], bytes_per_day=1024)
        first, second = _client(address, a), _client(address, b)
        try:
            await first.connect()
            await second.connect()
            stream_a, stream_b = await _pair(first, second)
            with contextlib.suppress(ConnectionError, OSError):
                await stream_a.sendall(b"x" * 4096)
            forwarded = await _read_until_eof(stream_b.reader)
            assert len(forwarded) <= 4096
            assert await asyncio.wait_for(stream_b.read(1), 3.0) == b""
            assert server.limits.bytes_today(a.node_id) > 1024
        finally:
            await first.close()
            await second.close()
            await server.stop()

    asyncio.run(run())


def test_an_idle_splice_is_closed(tmp_path):
    async def run():
        owner, a, b = make_identity(), make_identity(), make_identity()
        server, address = await start_relay(
            tmp_path, owner, [owner, a, b], idle_timeout=0.2)
        first, second = _client(address, a), _client(address, b)
        try:
            await first.connect()
            await second.connect()
            stream_a, stream_b = await _pair(first, second)
            loop = asyncio.get_running_loop()
            started = loop.time()
            assert await asyncio.wait_for(stream_b.read(1), 3.0) == b""
            assert loop.time() - started < 2.0
            with contextlib.suppress(Exception):
                stream_a.close()
        finally:
            await first.close()
            await second.close()
            await server.stop()

    asyncio.run(run())


def test_an_oversized_control_frame_is_refused(tmp_path):
    async def run():
        owner = make_identity()
        server, address = await start_relay(tmp_path, owner, [owner])
        try:
            reader, writer = await raw_connection(address)
            writer.write(struct.pack(">I", MAX_FRAME_BYTES + 1))
            await writer.drain()
            reply = await asyncio.wait_for(read_frame(reader), 3.0)
            assert reply["type"] == "error"
            assert reply["code"] == "bad_frame"
            writer.close()
            with contextlib.suppress(Exception):
                await writer.wait_closed()
        finally:
            await server.stop()

    asyncio.run(run())


def test_pair_rechecks_the_current_manifest_after_revocation(tmp_path):
    async def run():
        owner, a, b = make_identity(), make_identity(), make_identity()
        server, address = await start_relay(tmp_path, owner, [owner, a, b])
        first, second = _client(address, a), _client(address, b)
        try:
            await first.connect()
            await second.connect()
            write_manifest(tmp_path / "circles" / "circle.json",
                           manifest_payload(owner, [owner, b], version=2), owner)
            with pytest.raises(RelayRefused) as exc:
                await first.pair(second.node_id)
            assert exc.value.code == "not_a_member"
        finally:
            await first.close()
            await second.close()
            await server.stop()

    asyncio.run(run())


def test_an_unanswered_pair_times_out(tmp_path):
    async def run():
        owner, a, b = make_identity(), make_identity(), make_identity()
        server, address = await start_relay(
            tmp_path, owner, [owner, a, b], pair_timeout=0.2)
        first, second = _client(address, a), _client(address, b)
        try:
            await first.connect()
            await second.connect()
            with pytest.raises(RelayRefused) as exc:
                await asyncio.wait_for(first.pair(second.node_id), 3.0)
            assert exc.value.code == "pair_timeout"
        finally:
            await first.close()
            await second.close()
            await server.stop()

    asyncio.run(run())
