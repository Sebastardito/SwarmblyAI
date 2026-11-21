"""Minimal QR Code Model 2 encoder (byte mode, error correction level M).

Why this exists: an invitation must be scannable from the screen, and the App
has no QR dependency. Pulling a new package (and its transitive wheels) for
one small image is not justified, so this module implements the part of
ISO/IEC 18004 the invitation needs: versions 1–40, byte mode, level M (about
15 % recovery), automatic version and mask selection, and an SVG output.

The tables are the standard ones; the algorithm follows the public QR
specification (Reed–Solomon over GF(2^8 / 0x11D), the eight mask patterns and
the format/version BCH codes). It is deliberately small and has no I/O beyond
the returned string.

The payload is a short ASCII invitation token. Non-ASCII text is encoded as
UTF-8 bytes, which is what scanners return; the invitation decoder treats the
text as ASCII base64url.
"""

from __future__ import annotations

MIN_VERSION = 1
MAX_VERSION = 40
ECC_LEVEL_M = 1

# Error-correction codewords per block, level M (index = version, 0 unused).
_ECC_PER_BLOCK_M = (
    -1, 10, 16, 26, 18, 24, 16, 18, 22, 22, 26, 30, 22, 22, 24, 24, 28, 28,
    26, 26, 26, 26, 28, 28, 28, 28, 28, 28, 28, 28, 28, 28, 28, 28, 28, 28,
    28, 28, 28, 28, 28)

# Number of Reed-Solomon blocks, level M (index = version, 0 unused).
_BLOCKS_M = (
    -1, 1, 1, 1, 2, 2, 4, 4, 4, 5, 5, 5, 8, 9, 9, 10, 10, 11, 13, 14, 16, 17,
    17, 18, 20, 21, 23, 25, 26, 28, 29, 31, 33, 35, 37, 38, 40, 43, 45, 47,
    49)

_MASKS = (
    lambda x, y: (x + y) % 2,
    lambda x, y: y % 2,
    lambda x, y: x % 3,
    lambda x, y: (x + y) % 3,
    lambda x, y: (x // 3 + y // 2) % 2,
    lambda x, y: x * y % 2 + x * y % 3,
    lambda x, y: (x * y % 2 + x * y % 3) % 2,
    lambda x, y: ((x + y) % 2 + x * y % 3) % 2,
)


class QrError(ValueError):
    """The payload does not fit a QR code or the input is invalid."""


def _raw_data_modules(version: int) -> int:
    result = (16 * version + 128) * version + 64
    if version >= 2:
        numalign = version // 7 + 2
        result -= (25 * numalign - 10) * numalign - 55
        if version >= 7:
            result -= 36
    return result


def _data_codewords(version: int) -> int:
    return _raw_data_modules(version) // 8 - _ECC_PER_BLOCK_M[version] * _BLOCKS_M[version]


def _alignment_positions(version: int) -> list[int]:
    if version == 1:
        return []
    size = version * 4 + 17
    numalign = version // 7 + 2
    step = (version * 8 + numalign * 3 + 5) // (numalign * 4 - 4) * 2
    return list(reversed([size - 7 - i * step for i in range(numalign - 1)] + [6]))


def _rs_divisor(degree: int) -> bytes:
    result = bytearray([0] * (degree - 1) + [1])
    root = 1
    for _ in range(degree):
        for j in range(degree):
            result[j] = _rs_multiply(result[j], root)
            if j + 1 < degree:
                result[j] ^= result[j + 1]
        root = _rs_multiply(root, 0x02)
    return bytes(result)


def _rs_multiply(x: int, y: int) -> int:
    z = 0
    for i in reversed(range(8)):
        z = (z << 1) ^ ((z >> 7) * 0x11D)
        z ^= ((y >> i) & 1) * x
    return z


def _rs_remainder(data: bytes, divisor: bytes) -> bytes:
    result = bytearray(len(divisor))
    for byte in data:
        factor = byte ^ result.pop(0)
        result.append(0)
        for i, coef in enumerate(divisor):
            result[i] ^= _rs_multiply(coef, factor)
    return bytes(result)


def _bits(value: int, length: int) -> list[int]:
    return [(value >> i) & 1 for i in reversed(range(length))]


def _pick_version(nbytes: int) -> int:
    for version in range(MIN_VERSION, MAX_VERSION + 1):
        header = 4 + (8 if version <= 9 else 16)
        if header + 8 * nbytes <= _data_codewords(version) * 8:
            return version
    raise QrError(f"payload too large for a QR code: {nbytes} bytes")


def _data_codewords_for(data: bytes, version: int) -> bytes:
    bits = _bits(0b0100, 4)                     # byte mode
    bits += _bits(len(data), 8 if version <= 9 else 16)
    for byte in data:
        bits += _bits(byte, 8)
    capacity = _data_codewords(version) * 8
    bits += [0] * min(4, capacity - len(bits))  # terminator
    bits += [0] * (-len(bits) % 8)              # byte boundary
    pad = (0xEC, 0x11)
    i = 0
    while len(bits) < capacity:
        bits += _bits(pad[i % 2], 8)
        i += 1
    out = bytearray(len(bits) // 8)
    for i, bit in enumerate(bits):
        out[i >> 3] |= bit << (7 - (i & 7))
    return bytes(out)


def _add_ecc_and_interleave(data: bytes, version: int) -> bytes:
    numblocks = _BLOCKS_M[version]
    ecclen = _ECC_PER_BLOCK_M[version]
    rawcodewords = _raw_data_modules(version) // 8
    numshort = numblocks - rawcodewords % numblocks
    shortlen = rawcodewords // numblocks
    divisor = _rs_divisor(ecclen)
    blocks: list[bytes] = []
    offset = 0
    for i in range(numblocks):
        length = shortlen - ecclen + (0 if i < numshort else 1)
        chunk = bytearray(data[offset:offset + length])
        offset += length
        ecc = _rs_remainder(bytes(chunk), divisor)
        if i < numshort:
            chunk.append(0)                     # padding byte in short blocks
        blocks.append(bytes(chunk) + ecc)
    out = bytearray()
    for i in range(len(blocks[0])):
        for j, block in enumerate(blocks):
            if i != shortlen - ecclen or j >= numshort:
                out.append(block[i])
    if offset != len(data) or len(out) != rawcodewords:
        raise QrError("internal QR block error")
    return bytes(out)


class _Matrix:
    def __init__(self, version: int):
        self.version = version
        self.size = version * 4 + 17
        self.modules = [[False] * self.size for _ in range(self.size)]
        self.function = [[False] * self.size for _ in range(self.size)]

    def set_function(self, x: int, y: int, dark: bool) -> None:
        if 0 <= x < self.size and 0 <= y < self.size:
            self.modules[y][x] = dark
            self.function[y][x] = True

    def draw_function_patterns(self) -> None:
        for i in range(self.size):
            self.set_function(6, i, i % 2 == 0)
            self.set_function(i, 6, i % 2 == 0)
        self._finder(3, 3)
        self._finder(self.size - 4, 3)
        self._finder(3, self.size - 4)
        positions = _alignment_positions(self.version)
        corners = {(0, 0), (0, len(positions) - 1), (len(positions) - 1, 0)}
        for i, x in enumerate(positions):
            for j, y in enumerate(positions):
                if (i, j) not in corners:
                    self._alignment(x, y)
        self.draw_format_bits(0)
        self.draw_version()

    def _finder(self, cx: int, cy: int) -> None:
        for dy in range(-4, 5):
            for dx in range(-4, 5):
                self.set_function(cx + dx, cy + dy,
                                  max(abs(dx), abs(dy)) not in (2, 4))

    def _alignment(self, cx: int, cy: int) -> None:
        for dy in range(-2, 3):
            for dx in range(-2, 3):
                self.set_function(cx + dx, cy + dy,
                                  max(abs(dx), abs(dy)) != 1)

    def draw_format_bits(self, mask: int) -> None:
        data = (0b00 << 3) | mask                # level M = 0b00
        rem = data
        for _ in range(10):
            rem = (rem << 1) ^ ((rem >> 9) * 0x537)
        bits = (data << 10 | rem) ^ 0x5412
        for i in range(6):
            self.set_function(8, i, _get_bit(bits, i))
        self.set_function(8, 7, _get_bit(bits, 6))
        self.set_function(8, 8, _get_bit(bits, 7))
        self.set_function(7, 8, _get_bit(bits, 8))
        for i in range(9, 15):
            self.set_function(14 - i, 8, _get_bit(bits, i))
        for i in range(8):
            self.set_function(self.size - 1 - i, 8, _get_bit(bits, i))
        for i in range(8, 15):
            self.set_function(8, self.size - 15 + i, _get_bit(bits, i))
        self.set_function(8, self.size - 8, True)

    def draw_version(self) -> None:
        if self.version < 7:
            return
        rem = self.version
        for _ in range(12):
            rem = (rem << 1) ^ ((rem >> 11) * 0x1F25)
        bits = self.version << 12 | rem
        for i in range(18):
            dark = _get_bit(bits, i)
            a = self.size - 11 + i % 3
            b = i // 3
            self.set_function(a, b, dark)
            self.set_function(b, a, dark)

    def draw_codewords(self, codewords: bytes) -> None:
        i = 0
        for right in range(self.size - 1, 0, -2):
            if right <= 6:
                right -= 1
            for vert in range(self.size):
                for j in range(2):
                    x = right - j
                    upward = (right + 1) & 2 == 0
                    y = (self.size - 1 - vert) if upward else vert
                    if not self.function[y][x] and i < len(codewords) * 8:
                        self.modules[y][x] = _get_bit(codewords[i >> 3],
                                                      7 - (i & 7))
                        i += 1
        if i != len(codewords) * 8:
            raise QrError("internal QR placement error")

    def apply_mask(self, mask: int) -> None:
        fn = _MASKS[mask]
        for y in range(self.size):
            for x in range(self.size):
                if not self.function[y][x] and fn(x, y) == 0:
                    self.modules[y][x] = not self.modules[y][x]

    def penalty(self) -> int:
        size = self.size
        score = 0
        # N1: runs of five or more same-coloured modules.
        for y in range(size):
            run, colour = 1, self.modules[y][0]
            for x in range(1, size):
                if self.modules[y][x] == colour:
                    run += 1
                else:
                    if run >= 5:
                        score += 3 + (run - 5)
                    run, colour = 1, self.modules[y][x]
            if run >= 5:
                score += 3 + (run - 5)
        for x in range(size):
            run, colour = 1, self.modules[0][x]
            for y in range(1, size):
                if self.modules[y][x] == colour:
                    run += 1
                else:
                    if run >= 5:
                        score += 3 + (run - 5)
                    run, colour = 1, self.modules[y][x]
            if run >= 5:
                score += 3 + (run - 5)
        # N2: 2x2 blocks of one colour.
        for y in range(size - 1):
            for x in range(size - 1):
                c = self.modules[y][x]
                if c == self.modules[y][x + 1] == self.modules[y + 1][x] \
                        == self.modules[y + 1][x + 1]:
                    score += 3
        # N3: finder-like 1:1:3:1:1 patterns with four light modules.
        patterns = ("00001011101", "10111010000")
        for y in range(size):
            row = "".join("1" if m else "0" for m in self.modules[y])
            for pattern in patterns:
                start = row.find(pattern)
                while start != -1:
                    score += 40
                    start = row.find(pattern, start + 1)
        for x in range(size):
            col = "".join("1" if self.modules[y][x] else "0" for y in range(size))
            for pattern in patterns:
                start = col.find(pattern)
                while start != -1:
                    score += 40
                    start = col.find(pattern, start + 1)
        # N4: dark/light balance.
        dark = sum(sum(1 for cell in row if cell) for row in self.modules)
        total = size * size
        score += (abs(dark * 20 - total * 10) // total) * 10
        return score


def _get_bit(value: int, index: int) -> bool:
    return bool((value >> index) & 1)


def _build(data: bytes, mask: int = -1) -> _Matrix:
    version = _pick_version(len(data))
    matrix = _Matrix(version)
    matrix.draw_function_patterns()
    codewords = _add_ecc_and_interleave(
        _data_codewords_for(data, version), version)
    matrix.draw_codewords(codewords)
    if mask >= 0:
        matrix.apply_mask(mask)
        matrix.draw_format_bits(mask)
        return matrix
    best_mask, best_penalty = 0, None
    for mask in range(8):
        matrix.apply_mask(mask)
        matrix.draw_format_bits(mask)
        penalty = matrix.penalty()
        if best_penalty is None or penalty < best_penalty:
            best_mask, best_penalty = mask, penalty
        matrix.apply_mask(mask)                 # undo
    matrix.apply_mask(best_mask)
    matrix.draw_format_bits(best_mask)
    return matrix


def encode_svg(text: str, *, border: int = 4, scale: int = 4) -> str:
    """Return a self-contained SVG with a quiet zone of ``border`` modules."""
    if not isinstance(text, str) or not text:
        raise QrError("QR payload must be a non-empty string")
    if border < 0:
        raise QrError("border must not be negative")
    matrix = _build(text.encode("utf-8"))
    size = matrix.size
    dim = (size + 2 * border) * scale
    path: list[str] = []
    for y in range(size):
        x = 0
        while x < size:
            if not matrix.modules[y][x]:
                x += 1
                continue
            start = x
            while x < size and matrix.modules[y][x]:
                x += 1
            path.append(f"M{(start + border) * scale} {(y + border) * scale}"
                        f"h{(x - start) * scale}v{scale}h-{(x - start) * scale}z")
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" '
        f'width="{dim}" height="{dim}" viewBox="0 0 {dim} {dim}" '
        'shape-rendering="crispEdges" role="img" aria-label="QR">'
        f'<rect width="{dim}" height="{dim}" fill="#ffffff"/>'
        f'<path d="{"".join(path)}" fill="#000000"/>'
        "</svg>")


def encode_matrix(text: str) -> list[list[bool]]:
    """The raw modules (dark = True), for tests and non-SVG renderers."""
    return _build(text.encode("utf-8")).modules
