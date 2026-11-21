"""Pure-Python QR encoder used for circle invitations (no third-party dep)."""

from __future__ import annotations

import pytest

from swarmbly_app import qr


def test_svg_is_self_contained_and_does_not_embed_text():
    payload = "SWC1.example-token-" + "a" * 200
    svg = qr.encode_svg(payload)
    assert svg.startswith("<svg") and svg.endswith("</svg>")
    assert 'xmlns="http://www.w3.org/2000/svg"' in svg
    assert payload not in svg
    assert "<path" in svg


def test_matrix_is_square_model2_and_has_finder_patterns():
    modules = qr.encode_matrix("swarmbly")
    size = len(modules)
    assert size == len(modules[0])
    assert size >= 21 and (size - 17) % 4 == 0
    for ox, oy in ((0, 0), (size - 7, 0), (0, size - 7)):
        for y in range(7):
            for x in range(7):
                ring = max(abs(x - 3), abs(y - 3))
                assert modules[oy + y][ox + x] is (ring != 2)


def test_different_payloads_differ():
    a = qr.encode_matrix("swc1_alpha")
    b = qr.encode_matrix("swc1_beta")
    assert a != b


def test_large_payload_uses_a_larger_version():
    small = qr.encode_matrix("x")
    large = qr.encode_matrix("x" * 400)
    assert len(large) > len(small)


def test_payload_too_large_is_refused():
    with pytest.raises(qr.QrError):
        qr.encode_svg("x" * 4000)


def test_invitation_sized_payload_fits():
    payload = "SWC1." + "A" * 350
    modules = qr.encode_matrix(payload)
    assert 21 <= len(modules) <= 177
