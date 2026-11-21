# SPDX-License-Identifier: AGPL-3.0-only
"""Layer the node's TLS 1.3 session over a paired relay stream.

The App's current transport opens a TCP socket and wraps it with
``asyncio.open_connection(..., ssl=...)``.  After a relay pair there is no
socket to hand to ``open_connection``: the bytes must travel through the
relay.  This adapter uses ``ssl.MemoryBIO``, which is the smallest change to
the transport and keeps the existing frame layer untouched.

``wrap()`` returns an object with ``sendall``/``recv``/``do_handshake``; the
App can adapt it to its ``PeerSession.reader``/``writer`` pair (or, if
``loop.start_tls`` proves reliable on its transport, drop this adapter).
"""

from __future__ import annotations

import ssl

from .client import RelayStream


class TLSStream:
    def __init__(self, stream: RelayStream, context: ssl.SSLContext, *,
                 server_side: bool, server_hostname: str | None = None) -> None:
        self.stream = stream
        self._incoming = ssl.MemoryBIO()
        self._outgoing = ssl.MemoryBIO()
        self._ssl = context.wrap_bio(
            self._incoming, self._outgoing, server_side=server_side,
            server_hostname=None if server_side else server_hostname)

    def version(self) -> str | None:
        return self._ssl.version()

    def cipher(self) -> tuple[str, str, int] | None:
        return self._ssl.cipher()

    async def _flush(self) -> None:
        data = self._outgoing.read()
        if data:
            await self.stream.sendall(data)

    async def _receive(self) -> None:
        data = await self.stream.read(64 * 1024)
        if data:
            self._incoming.write(data)
        else:
            self._incoming.write_eof()

    async def do_handshake(self) -> None:
        while True:
            try:
                self._ssl.do_handshake()
                await self._flush()
                return
            except ssl.SSLWantReadError:
                await self._flush()
                await self._receive()
            except ssl.SSLWantWriteError:
                await self._flush()

    async def sendall(self, data: bytes) -> None:
        view = memoryview(data)
        while view:
            try:
                written = self._ssl.write(view)
            except ssl.SSLWantWriteError:
                await self._flush()
                continue
            except ssl.SSLWantReadError:
                await self._flush()
                await self._receive()
                continue
            view = view[written:]
            await self._flush()

    async def recv(self, size: int = 65536) -> bytes:
        while True:
            try:
                return self._ssl.read(size)
            except ssl.SSLWantReadError:
                await self._flush()
                await self._receive()
            except ssl.SSLWantWriteError:
                await self._flush()
            except ssl.SSLZeroReturnError:
                return b""

    async def close(self) -> None:
        try:
            self._ssl.unwrap()
            await self._flush()
        except (ssl.SSLError, OSError):
            pass
        self.stream.close()
