"""Anchor verification (SPEC 6.3).

Verification has two parts. The **deterministic** part is code: the cited
span must exist in the source with the recorded file hash. The **support**
part judges whether the span supports the atomic claim, in the sense of
FActScore [20]. The default support checker is lexical and conservative; a
model-based checker can be plugged in, and SHOULD be a different model from
the digester, because models do not cite reliably [21].

Verification never trusts the digester: an unverified claim stays DIGESTED.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Protocol

from .claims import Anchor, Claim, replace_verified
from .sources import SourceSpace

__all__ = ["SupportChecker", "LexicalSupport", "ModelSupport", "AnchorVerifier", "VerificationStats"]

_WORD = re.compile(r"[\wáéíóúñü]+", re.IGNORECASE)
_STOP = frozenset(
    "the a an of and or to in on for is are was were be by with as at from that this it its "
    "el la los las un una unos unas de del y o en por para con como es son fue al que se su sus lo".split()
)


def _content(text: str) -> set[str]:
    return {w.lower() for w in _WORD.findall(text) if w.lower() not in _STOP and len(w) > 2}


class SupportChecker(Protocol):
    def supports(self, span_text: str, claim_text: str) -> bool:  # pragma: no cover - protocol
        ...


@dataclass
class LexicalSupport:
    """Content-word recall of the claim within the span.

    Deliberately strict: a paraphrase with new content words fails. It is a
    floor, not a judge — its job is to reject inventions cheaply.
    """

    min_recall: float = 0.6

    def supports(self, span_text: str, claim_text: str) -> bool:
        cw = _content(claim_text)
        if not cw:
            return False
        sw = _content(span_text)
        return len(cw & sw) / len(cw) >= self.min_recall


@dataclass
class ModelSupport:
    """Model-based support check through any backend with ``generate``."""

    backend: object
    prompt_template: str = (
        "You verify citations. Answer only YES or NO.\n"
        "SOURCE PASSAGE:\n{span}\n\nCLAIM:\n{claim}\n\n"
        "Is the claim fully supported by the source passage alone?"
    )

    def supports(self, span_text: str, claim_text: str) -> bool:
        out = self.backend.generate(self.prompt_template.format(span=span_text, claim=claim_text), temperature=0.0, max_tokens=4)
        return out.strip().upper().startswith("YES")


@dataclass
class VerificationStats:
    proposed: int = 0
    verified: int = 0
    rejected_missing: int = 0
    rejected_hash: int = 0
    rejected_support: int = 0

    @property
    def rejection_rate(self) -> float:
        return 0.0 if self.proposed == 0 else 1.0 - self.verified / self.proposed


@dataclass
class AnchorVerifier:
    space: SourceSpace
    support: SupportChecker = field(default_factory=LexicalSupport)
    stats: VerificationStats = field(default_factory=VerificationStats)

    def verify_anchor(self, anchor: Anchor, claim_text: str) -> Anchor:
        self.stats.proposed += 1
        try:
            text = self.space.read(anchor.source)
            current_hash = self.space.file_hash(anchor.source)
        except (FileNotFoundError, PermissionError):
            self.stats.rejected_missing += 1
            return replace_verified(anchor, False)
        if current_hash != anchor.source_hash:
            self.stats.rejected_hash += 1
            return replace_verified(anchor, False)
        if anchor.end > len(text):
            self.stats.rejected_missing += 1
            return replace_verified(anchor, False)
        if not self.support.supports(text[anchor.start:anchor.end], claim_text):
            self.stats.rejected_support += 1
            return replace_verified(anchor, False)
        self.stats.verified += 1
        return replace_verified(anchor, True)

    def verify(self, claim: Claim) -> bool:
        claim.anchors = [self.verify_anchor(a, claim.text) for a in claim.anchors]
        return claim.anchored
