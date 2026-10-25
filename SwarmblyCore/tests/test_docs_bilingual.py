"""Every public document exists in both languages, and the pair says the same.

The rule the user set is simple -- anything public is readable in Spanish and
in English -- but a rule about documentation that only a person enforces is a
rule that decays the first busy week. So it is a test.

The second half is the one that earns its place. A translation that drifts is
worse than no translation, because two documents then claim different numbers
with equal authority and nothing says which is right. So the pair is compared
on the things a translation must never change: the figures, and the identifiers
that name a run, a digest, a file or a field.

Each language keeps its own number typography -- Spanish writes 0,585 and
English 0.585 -- and the comparison ignores the separator entirely rather than
trying to work out which one each language meant. Imposing a format would make
the Spanish read as a translation rather than as Spanish, and guessing the
format, as an earlier version of this file did, fails on correct work. The job
here is to catch a figure that drifted, not to police a glyph.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"

sys.path.insert(0, str(ROOT / "scripts"))
from make_status import front_matter  # noqa: E402

DOCUMENTS = sorted(p for p in DOCS.glob("*.md") if p.name != "STATUS.md")

# A figure keeps whatever separators it was written with; _canonical removes
# them. Both have to be inside the match, or "0,01" reads as 0 and then 01.
_NUMBER = re.compile(r"(?<![\w.,])-?\d+(?:[.,]\d+)*%?")
_CODE = re.compile(r"`([^`\n]+)`")
# An identifier is a name, not prose: a path, a field, a digest, a run id.
_IDENTIFIER = re.compile(r"^[\w][\w./:\-]*$")


def pair_of(path: Path) -> Path | None:
    """The file that must hold the other language, or None if bilingual.

    Two shapes coexist, and both are correct. Some families were written in
    both languages from the start and carry a suffix on each side
    (``SPEC_EN.md`` / ``SPEC_ES.md``). Others were written in one language,
    are cited by that name from code and from other documents, and gained
    their translation afterwards (``RESULTS_V4.md`` / ``RESULTS_V4_ES.md``).
    Renaming the second kind to match the first would break every citation to
    buy symmetry, so the rule accepts both: the suffixed sibling if it exists,
    otherwise the bare name.
    """
    fields = front_matter(path)
    lang = fields.get("lang", "")
    if lang == "es+en":
        return None
    other = "ES" if lang == "en" else "EN"
    stem = path.stem
    if stem.endswith(("_EN", "_ES")):
        base = stem[:-3]
        suffixed = DOCS / f"{base}_{other}.md"
        bare = DOCS / f"{base}.md"
        if suffixed.exists():
            return suffixed
        if bare.exists():
            return bare
        return suffixed
    return DOCS / f"{stem}_{other}.md"


def _body(path: Path) -> str:
    text = path.read_text(encoding="utf-8")
    return text[4:].partition("\n---\n")[2] if text.startswith("---\n") else text


_SEPARATOR = re.compile(r"(?<=\d)[.,](?=\d)")


def _canonical(token: str) -> str:
    """One number, written so that 0,844 and 0.844 are the same figure.

    The first version of this compared numbers after guessing which separator
    each language meant -- point for decimals in English, comma in Spanish,
    the other one for grouping thousands. The guess is not decidable: Spanish
    "1.000" is a thousand written with a grouping point and also a score of one
    written to three places, and only the sentence around it says which. The
    rule read three digits after a point in a Spanish file as grouping, so a
    perfectly correct "0,844" translated as "0.844" was reported as drift, and
    a translator following the failure message would write a decimal comma
    into an English research record to make the test go quiet. One did.

    So the separators are simply removed and the digits compared. What this
    can no longer distinguish is a genuine 1000 from a genuine 1.000 -- a
    narrow blind spot, and a much smaller one than a check that fails on
    correct work, because a test that cries wolf gets satisfied rather than
    believed.
    """
    return _SEPARATOR.sub("", token)


def _figures(path: Path) -> set[str]:
    """The distinct figures a document states.

    A set rather than a multiset: Spanish writes "31 %" where English writes
    "31%", and a figure repeated once more in one language is a difference in
    how a sentence was built, not in what was measured. What this has to catch
    is a figure that appears in one version and not the other.
    """
    return {_canonical(token.rstrip("%")) for token in _NUMBER.findall(_body(path))}


_LANG_SUFFIX = re.compile(r"_(EN|ES)(?=\.|$)")


def _identifiers(path: Path) -> list[str]:
    # A document cites its own language's siblings: ONEPAGER_EN.md points at
    # WHITEPAPER_EN.md and ONEPAGER_ES.md at WHITEPAPER_ES.md. That is the
    # pair working, not drifting, so the suffix is normalised away.
    return sorted(
        _LANG_SUFFIX.sub("_LANG", span)
        for span in _CODE.findall(_body(path))
        if _IDENTIFIER.match(span)
    )


@pytest.mark.parametrize("path", DOCUMENTS, ids=lambda p: p.name)
def test_every_document_declares_its_language(path: Path) -> None:
    lang = front_matter(path).get("lang")
    assert lang in ("es", "en", "es+en"), (
        f"{path.name} declares lang={lang!r}. Use es, en, or es+en for a "
        "document that carries both languages in one file."
    )


@pytest.mark.parametrize("path", DOCUMENTS, ids=lambda p: p.name)
def test_every_document_has_its_other_language(path: Path) -> None:
    pair = pair_of(path)
    if pair is None:
        return
    assert pair.exists(), (
        f"{path.name} is {front_matter(path).get('lang')}-only. Its pair "
        f"{pair.name} does not exist. Every public document is readable in "
        "both languages -- write the pair, or carry both languages in one file "
        "and declare lang: es+en."
    )


@pytest.mark.parametrize("path", DOCUMENTS, ids=lambda p: p.name)
def test_a_pair_agrees_on_every_figure(path: Path) -> None:
    pair = pair_of(path)
    if pair is None or not pair.exists():
        pytest.skip("no pair yet")
    mine, theirs = _figures(path), _figures(pair)
    if mine == theirs:
        return
    only_here = sorted(mine - theirs)
    only_there = sorted(theirs - mine)
    pytest.fail(
        f"{path.name} and {pair.name} disagree on their figures. A translation "
        "may change every word and no number.\n"
        f"  only in {path.name}: {only_here}\n"
        f"  only in {pair.name}: {only_there}\n"
        "  (separators are ignored, so 0,844 and 0.844 are the same figure "
        "here -- a difference reported above is a real one. Write each "
        "language's own typography and fix the digits, never the glyph.)"
    )


@pytest.mark.parametrize("path", DOCUMENTS, ids=lambda p: p.name)
def test_a_pair_agrees_on_every_identifier(path: Path) -> None:
    pair = pair_of(path)
    if pair is None or not pair.exists():
        pytest.skip("no pair yet")
    mine, theirs = _identifiers(path), _identifiers(pair)
    if mine == theirs:
        return
    pytest.fail(
        f"{path.name} and {pair.name} disagree on the names they cite. Field "
        "names, file names, run ids and digests are not translated.\n"
        f"  only in {path.name}: {sorted(set(mine) - set(theirs))}\n"
        f"  only in {pair.name}: {sorted(set(theirs) - set(mine))}"
    )


@pytest.mark.parametrize("path", DOCUMENTS, ids=lambda p: p.name)
def test_a_pair_agrees_on_its_status(path: Path) -> None:
    pair = pair_of(path)
    if pair is None or not pair.exists():
        pytest.skip("no pair yet")
    mine, theirs = front_matter(path), front_matter(pair)
    assert mine.get("status") == theirs.get("status"), (
        f"{path.name} is {mine.get('status')} but {pair.name} is "
        f"{theirs.get('status')}. One language would tell a reader the figure "
        "stands and the other that it does not."
    )
