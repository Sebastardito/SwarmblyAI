"""Triage gate (M3): mechanical predicate per returned fragment.

`does the carry that arrived answer the task that requested it?` — no judge,
no model. Checks: non-empty, token bounds, required-item coverage, schema
compliance. A failure is RETRY (isolate and re-run), then DISCARD.
"""

import json
import re

from . import units


def check(result_text, task, packet_id, expected_items=None, min_tokens=10,
          max_tokens=2000, required_fraction=1.0):
    """Mechanical predicate. Returns (PASS|RETRY|DISCARD, reason).

    `required_fraction` is the share of expected items that must be present:
    extraction demands all (1.0); summarisation demands at least half, so a
    summary that legitimately selects rows is not rejected while a carry that
    answers another packet (≈0 of the right items) still is.
    """
    if not result_text or not result_text.strip():
        return "DISCARD", "empty result"
    n = units.approx_tokens(result_text)
    if n < min_tokens:
        return "RETRY", f"too short ({n} tok < {min_tokens})"
    if n > max_tokens:
        return "DISCARD", f"too long ({n} tok > {max_tokens})"
    if expected_items:
        hits = sum(1 for it in expected_items
                   if re.search(re.escape(it), result_text, re.IGNORECASE))
        need = max(1, round(required_fraction * len(expected_items)))
        if hits < need:
            missing = [it for it in expected_items
                       if not re.search(re.escape(it), result_text, re.IGNORECASE)]
            return "RETRY", (f"covers {hits}/{len(expected_items)} items "
                             f"(need {need}); missing: {missing[:4]}")
    if task.get("schema") == "json":
        try:
            json.loads(result_text)
        except json.JSONDecodeError:
            return "RETRY", "invalid JSON schema"
    if task.get("schema") == "line-list":
        lines = [l for l in result_text.splitlines() if l.strip()]
        if len(lines) < task.get("min_lines", 1):
            return "RETRY", f"expected >= {task.get('min_lines', 1)} lines"
    return "PASS", "ok"


def triage_with_retries(generate_fn, prompt, task, packet_id, expected_items,
                        max_retries=2):
    """Run + gate, retrying on RETRY with a different instruction framing."""
    for attempt in range(max_retries + 1):
        out = generate_fn(prompt)
        verdict, reason = check(out["text"], task, packet_id, expected_items)
        out["verdict"] = verdict
        out["reason"] = reason
        out["attempt"] = attempt
        if verdict == "PASS":
            return out
    return out  # last attempt (DISCARD or exhausted RETRY)
