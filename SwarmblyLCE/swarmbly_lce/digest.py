"""Digester: proposes claims from source spans (SPEC 6.3).

The digester is the only place where a model writes into the wiki, and what
it writes are *proposals*: every proposed claim is anchored to a span by
offsets, then verified by :class:`~swarmbly_lce.anchors.AnchorVerifier`. A
claim whose anchor does not verify stays DIGESTED and can never be trained on.

The model is asked for JSON. Malformed output is not repaired creatively: the
span is skipped and counted, because a digester that invents structure is the
failure this layer exists to contain.
"""

from __future__ import annotations

import json
from pathlib import Path
import re
from dataclasses import dataclass, field

from .anchors import AnchorVerifier
from .backends import PROMPT_MARKERS, Backend
from .claims import Claim, ClaimType, Maturity, Provenance, Transmission
from .errors import InvariantViolation
from .sources import SourceSpace, Span
from .wiki import Wiki

__all__ = ["Digester", "DigestStats", "locate_quote", "reconcile_type"]

PROMPT = (
    PROMPT_MARKERS["extract"] + "\n"
    "Extract atomic claims from the passage. For each, return its exact character offsets in the passage "
    "and one type among: fact, user_claim, opinion, belief, hypothesis, experience, preference, style, procedure. "
    "Use user_claim/opinion/belief for what the author asserts or believes; style/preference/procedure for how the author "
    "writes, prefers or works. Return JSON: {{\"claims\": [{{\"text\": ..., \"type\": ..., \"start\": int, \"end\": int}}]}}.\n"
    "PASSAGE:\n{passage}\n"
)

PROMPT_QUOTE = (
    PROMPT_MARKERS["extract"] + "\n"
    "Extract atomic claims from the passage. Do NOT merge facts from different "
    "sentences into one claim: one claim per fact, at most one claim per sentence "
    "unless the sentence states two independent facts. For each, copy the exact words of the passage that support it as "
    "'quote' (a verbatim substring, unchanged), and give one type among: fact, user_claim, opinion, belief, hypothesis, "
    "experience, preference, style, procedure. Use user_claim/opinion/belief for what the author asserts or believes; "
    "style/preference/procedure for how the author writes, prefers or works. Write the claim in the passage's language. "
    "Return JSON: {{\"claims\": [{{\"text\": ..., \"type\": ..., \"quote\": ...}}]}}.\n"
    "PASSAGE:\n{passage}\n"
)

_JSON = re.compile(r"\{.*\}", re.S)
_WS = re.compile(r"\s+")

# Type reconciliation (amendment 3). The model proposes a type; when the user's
# own anchored words carry an explicit first-person cue, code decides. Applied only
# to sources the user authored, and only from an assertive type (user_claim,
# opinion, belief, fact) towards a behavioral one: never the reverse.
_PREF_CUE = re.compile(r"\b(prefiero|prefer|i prefer|i'd rather)\b", re.I)
_STYLE_CUE = re.compile(r"\b(escribo|suelo escribir|i write|i usually write|mi estilo|my style)\b", re.I)
_RECONCILABLE = frozenset({ClaimType.USER_CLAIM, ClaimType.OPINION, ClaimType.BELIEF, ClaimType.FACT})


def reconcile_type(proposed: ClaimType, span_text: str) -> ClaimType:
    if proposed not in _RECONCILABLE:
        return proposed
    if _PREF_CUE.search(span_text):
        return ClaimType.PREFERENCE
    if _STYLE_CUE.search(span_text):
        return ClaimType.STYLE
    return proposed


def locate_quote(passage: str, quote: str) -> tuple[int, int] | None:
    """Offsets of ``quote`` in ``passage``, computed by code (never by the model).

    Exact match first; then a match that tolerates differences in whitespace and
    letter case only. Anything looser (paraphrase, reordering) is not a quote.
    """
    q = quote.strip().strip("\"'«»“”")
    if len(q) < 4:
        return None
    i = passage.find(q)
    if i >= 0:
        return i, i + len(q)
    pat = r"\s+".join(re.escape(w) for w in _WS.split(q) if w)
    m = re.search(pat, passage, re.I)
    return (m.start(), m.end()) if m else None


@dataclass
class DigestStats:
    spans: int = 0
    malformed: int = 0
    proposed: int = 0
    added: int = 0
    skipped_policy: int = 0
    quote_not_found: int = 0
    type_reconciled: int = 0


@dataclass
class Digester:
    backend: Backend
    space: SourceSpace
    verifier: AnchorVerifier
    stats: DigestStats = field(default_factory=DigestStats)
    # "offsets": the model returns character offsets (v0.1). "quote": the model returns a
    # verbatim quote and the code locates it; small models count characters poorly.
    anchor_mode: str = "offsets"
    # Amendment 3: reconcile the proposed type with first-person cues in the anchored span.
    reconcile_types: bool = False
    # Amendment 11: two decodes per sub-passage, keep claims present in both.
    double_pass: bool = False

    def _parse(self, raw: str) -> list[dict]:
        m = _JSON.search(raw)
        if not m:
            raise ValueError("no JSON object in digester output")
        data: dict[str, Any]
        try:
            data = json.loads(m.group(0))
        except json.JSONDecodeError:
            # El modelo a veces emite una SECUENCIA de objetos ({..},{..},...)
            # en lugar de un solo {"claims": [...]}. Se fusionan sus claims
            # (Enmienda 10): el parser tolerante elimina la pérdida de
            # sub-pasajes enteros que rompía la reproducibilidad de AA2.
            s_out = m.group(0)
            objs: list[dict] = []
            depth = start = 0
            in_str = esc = False
            for i, ch in enumerate(s_out):
                if esc:
                    esc = False
                    continue
                if ch == "\\" and in_str:
                    esc = True
                    continue
                if ch == '"':
                    in_str = not in_str
                    continue
                if in_str:
                    continue
                if ch == "{":
                    if depth == 0:
                        start = i
                    depth += 1
                elif ch == "}":
                    depth -= 1
                    if depth == 0:
                        objs.append(json.loads(s_out[start:i + 1]))
            if not objs:
                raise ValueError("digester output not parseable")
            merged: list[dict] = []
            for o in objs:
                if "claims" in o:
                    merged.extend(o["claims"])
                else:
                    merged.append(o)
            data = {"claims": merged}
        items = data.get("claims", [])
        if not isinstance(items, list):
            raise ValueError("'claims' is not a list")
        return items

    def digest_span(self, wiki: Wiki, span: Span) -> list[Claim]:
        self.stats.spans += 1
        rule = wiki.policy.rule_for(span.source)
        if not rule.wiki:
            self.stats.skipped_policy += 1
            return []
        try:
            prompt = (PROMPT_QUOTE if self.anchor_mode == "quote" else PROMPT).format(passage=span.text)
            items = self._parse(self.backend.generate(prompt, temperature=0.0, max_tokens=1024))
            if self.double_pass:
                # Enmienda 11: dos decodificaciones por sub-pasaje y se
                # conservan solo las claims presentes en AMBAS (la decodificación
                # de Ollama no es bit-reproducible para salidas largas; la
                # intersección filtra la parte variable).
                items2 = self._parse(self.backend.generate(prompt, temperature=0.0, max_tokens=1024))
                def _k(x: dict) -> str:
                    import re as _re
                    t = str(x.get("text", "")).lower()
                    return _re.sub(r"[^a-z0-9]", "", t)
                keys2 = {_k(x) for x in items2}
                items = [x for x in items if _k(x) in keys2]
        except (ValueError, json.JSONDecodeError):
            self.stats.malformed += 1
            return []
        out: list[Claim] = []
        for it in items:
            try:
                text = str(it["text"]).strip()
                ctype = ClaimType(str(it.get("type", "fact")).strip().lower())
                if self.anchor_mode == "quote":
                    loc = locate_quote(span.text, str(it.get("quote", "")))
                    if loc is None:
                        self.stats.quote_not_found += 1
                        continue
                    s, e = loc
                else:
                    s, e = int(it["start"]), int(it["end"])
            except (KeyError, ValueError, TypeError):
                self.stats.malformed += 1
                continue
            if not text or not (0 <= s < e <= len(span.text)):
                self.stats.malformed += 1
                continue
            if self.reconcile_types and rule.authored_by_user:
                new_type = reconcile_type(ctype, span.text[s:e])
                if new_type != ctype:
                    self.stats.type_reconciled += 1
                    ctype = new_type
            self.stats.proposed += 1
            if ctype == ClaimType.EXPERIENCE and not rule.retain_episodic:
                self.stats.skipped_policy += 1
                continue
            # A style claim from text the user did not write is kept (it describes the
            # source) but can never become trainable: LearningPolicy.allows_type requires
            # authored_by_user for style (SPEC 7.2.1).
            anchor = wiki.new_anchor(span.source, span.start + s, span.start + e)
            distance = 0 if (ctype in {ClaimType.STYLE, ClaimType.PREFERENCE, ClaimType.PROCEDURE} and rule.authored_by_user) else 1
            claim = Claim(text=text, type=ctype, anchors=[anchor], maturity=Maturity.DIGESTED,
                          provenance=Provenance(epistemic_distance=distance, transmission_path=Transmission.VERTICAL))
            self.verifier.verify(claim)
            try:
                out.append(wiki.add(claim))
                self.stats.added += 1
            except InvariantViolation:
                self.stats.skipped_policy += 1
        return out

    def digest_source(self, wiki: Wiki, rel: str) -> list[Claim]:
        if Path(rel).name in getattr(self.space, "_excluded", frozenset()):
            self.stats.skipped_policy += 1
            return []
        wiki.register_source(rel, self.space.file_hash(rel))
        claims: list[Claim] = []
        for span in self.space.spans(rel):
            claims.extend(self.digest_span(wiki, span))
        return claims

    def digest_all(self, wiki: Wiki) -> list[Claim]:
        claims: list[Claim] = []
        for f in self.space.files():
            claims.extend(self.digest_source(wiki, f.rel))
        return claims
