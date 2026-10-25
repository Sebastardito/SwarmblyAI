"""Processing reports (product spec §11): JSON / Markdown / HTML.

A report covers one request: identifier, timing, models and participating
nodes, privacy classification, router and admission decision, micro-task
plan, distribution metrics, verification, assembly, coherence, failures and
retries, and the final response. Every value carries its nature (measured,
estimated, placeholder, not available).

Detail levels (``results.report_detail``):

- ``minimal``  — diagnostics only: **no request text, no response text**
  (safe to share when reporting a problem);
- ``standard`` — adds the final response and per-stage details;
- ``full``     — adds every dispatch attempt and the per-task consensus units.

Reports are generated on demand and never stored unless exported.
"""

from __future__ import annotations

import html as _html
import json
import time
from typing import Any

DETAIL_LEVELS = ("minimal", "standard", "full")


def _find_assistant(db, req: dict[str, Any]) -> dict[str, Any] | None:
    """The assistant message produced by this request (follows its user message)."""
    if not req.get("conversation_id"):
        return None
    messages = db.get_messages(req["conversation_id"])
    for i, message in enumerate(messages):
        if message["id"] == req.get("message_id"):
            for nxt in messages[i + 1:]:
                if nxt["role"] == "assistant":
                    return nxt
            return None
        if message["id"] == (req.get("meta") or {}).get("assistant_message_id"):
            return message
    return None


def build_report(db, request_id: str, detail: str = "standard") -> dict[str, Any]:
    req = db.get_request(request_id)
    if req is None:
        raise KeyError(f"unknown request {request_id}")
    detail = detail if detail in DETAIL_LEVELS else "standard"
    assistant = _find_assistant(db, req) or {}
    meta = assistant.get("meta") or {}
    stages = assistant.get("stages") or []
    swarm = meta.get("swarm") or {}
    routing = swarm.get("routing") or {}
    router = swarm.get("router") or {}
    attempts = swarm.get("attempts") or []
    report: dict[str, Any] = {
        "request_id": request_id,
        "generated_at": _iso(time.time()),
        "started_at": _iso(req.get("started_at")),
        "finished_at": _iso(req.get("finished_at")),
        "duration_ms": (int((req["finished_at"] - req["started_at"]) * 1000)
                        if req.get("finished_at") else None),
        "status": req.get("status"),
        "mode_requested": req.get("mode"),
        "executed": meta.get("executed") or ("local" if not swarm else "distributed"),
        "local_reason": meta.get("local_reason") or "",
        "models": {"local": req.get("model"),
                   "workers": sorted({n.get("version") or n.get("family", "")
                                      for n in swarm.get("nodes", [])})},
        "nodes": swarm.get("nodes", []),
        "privacy": {"tier": routing.get("tier"), "lane": routing.get("lane"),
                    "classifier": routing.get("classifier"),
                    "note": "automatic triage raises a tier; it never certifies "
                            "the absence of sensitive content"},
        "router": router,
        "plan": {"n_tasks": swarm.get("n_tasks"), "n_levels": swarm.get("n_levels"),
                 "rho_achieved": swarm.get("rho_achieved"),
                 "rho_floor": swarm.get("rho_floor"),
                 "rho_target": swarm.get("rho_target"),
                 "rho_policy": swarm.get("rho_policy")},
        "distribution": {"attempts": len(attempts),
                         "accepted": sum(1 for a in attempts if a.get("status") == "accepted"),
                         "failed": sum(1 for a in attempts if a.get("status") == "failed"),
                         "cancelled_slow": sum(1 for a in attempts
                                               if a.get("status") == "cancelled_slow"),
                         "hedges": swarm.get("hedges"), "retries": swarm.get("retries"),
                         "timeouts": swarm.get("timeouts"),
                         "bytes": swarm.get("bytes"),
                         "coverage": swarm.get("coverage"),
                         "stage_ms": swarm.get("stage_ms")},
        "verification": swarm.get("verification"),
        "consensus": _consensus_summary(swarm, detail),
        "consensus_waived_reason": swarm.get("consensus_waived_reason"),
        "assembly": {"seams": swarm.get("seams", []), "tau_sem": swarm.get("tau_sem"),
                     "tau_source": swarm.get("tau_source"),
                     "embedder": swarm.get("embedder")},
        "coherence": swarm.get("coherence"),
        "error": meta.get("error"),
        "stages": [{"stage": s.get("stage"), "status": s.get("status"),
                    "elapsed_ms": s.get("elapsed_ms"),
                    "reason": s.get("reason") or s.get("detail")}
                   for s in stages] if detail == "minimal" else stages,
        "detail": detail,
        "notes": [
            "Layer-1 verification commitments are not available (SPEC §21.1); "
            "result signatures were verified.",
            "Agreement between replicas is convergence, not correctness; errors "
            "are correlated across families (SwarmblyAI L13, L23).",
            "τ_sem and α thresholds are documented placeholders until calibrated.",
        ],
    }
    if detail != "minimal":
        report["final_response"] = assistant.get("content") or ""
    if detail == "full":
        report["attempts"] = attempts
    return report


def _consensus_summary(swarm: dict[str, Any], detail: str) -> dict[str, Any] | None:
    consensus = swarm.get("consensus")
    if not consensus:
        return None
    out = {k: v for k, v in consensus.items() if k != "per_task"}
    per_task = consensus.get("per_task") or {}
    out["tasks"] = len(per_task)
    if detail == "full":
        out["per_task"] = per_task
    else:
        out["low_confidence_units"] = sum(
            1 for block in per_task.values()
            for unit in block.get("units", []) if unit.get("label") == "LOW")
    return out


def render_report(db, request_id: str, fmt: str = "markdown",
                  detail: str = "standard") -> str:
    data = build_report(db, request_id, detail)
    if fmt == "json":
        return json.dumps(data, indent=2, ensure_ascii=False)
    if fmt == "html":
        return _html_report(data)
    return _markdown(data)


def _iso(ts: float | None) -> str:
    if not ts:
        return ""
    return time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(ts))


def _stages_text(stages: list[dict[str, Any]]) -> str:
    lines = []
    for stage in stages:
        extra = stage.get("elapsed_ms")
        reason = stage.get("reason") or stage.get("detail") or ""
        lines.append(f"{str(stage.get('stage')):26} {str(stage.get('status')):10} "
                     f"{'' if extra is None else str(extra) + ' ms':>9}  {reason}"[:160])
    return "\n".join(lines)


def _kv(value: Any) -> str:
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False)
    return "—" if value in (None, "") else str(value)


def _markdown(d: dict[str, Any]) -> str:
    p, dist = d["plan"], d["distribution"]
    lines = [
        f"# Swarmbly processing report — `{d['request_id']}`", "",
        f"- **Status:** {d['status']} · **Executed:** {d['executed']}"
        + (f" ({d['local_reason']})" if d["local_reason"] else ""),
        f"- **Started:** {d['started_at']} · **Duration:** {_kv(d['duration_ms'])} ms",
        f"- **Local model:** {_kv(d['models']['local'])} · **Worker models:** "
        f"{', '.join(d['models']['workers']) or '—'}", "",
        "## Privacy",
        f"- Tier `{_kv(d['privacy']['tier'])}` · lane `{_kv(d['privacy']['lane'])}` · "
        f"classifier {_kv(d['privacy']['classifier'])}", "",
        "## Router and plan",
        f"- Router: {_kv(d['router'])}",
        f"- Tasks {_kv(p['n_tasks'])} in {_kv(p['n_levels'])} level(s) · ρ achieved "
        f"{_kv(p['rho_achieved'])} (floor {_kv(p['rho_floor'])}) — {_kv(p['rho_policy'])}", "",
        "## Distribution (measured)",
        f"- Attempts {dist['attempts']}: accepted {dist['accepted']}, failed "
        f"{dist['failed']}, cancelled as slow {dist['cancelled_slow']}",
        f"- Hedges {_kv(dist['hedges'])} · retries {_kv(dist['retries'])} · "
        f"timeouts {_kv(dist['timeouts'])} · bytes {_kv(dist['bytes'])}",
        f"- Coverage (estimate): {_kv(dist['coverage'])}", "",
        "## Verification",
        f"- {_kv(d['verification'])}", "",
        "## Consensus",
        f"- {_kv(d['consensus'])}" if d["consensus"]
        else f"- not computed: {_kv(d['consensus_waived_reason'])}", "",
        "## Assembly and coherence",
        f"- Seams {len(d['assembly']['seams'])} · τ_sem {_kv(d['assembly']['tau_sem'])} "
        f"({_kv(d['assembly']['tau_source'])}) · embedder {_kv(d['assembly']['embedder'])}",
        f"- Coherence: {_kv(d['coherence'])}", "",
        "## Nodes",
        "\n".join(f"- `{n.get('node')}` {n.get('family')} {n.get('version')} "
                  f"({n.get('tasks')} task(s))" for n in d["nodes"]) or "- none", "",
        "## Pipeline", "```", _stages_text(d["stages"]), "```",
    ]
    if d.get("error"):
        lines += ["", f"**Error:** {d['error']}"]
    if "final_response" in d:
        lines += ["", "## Final response", "", d["final_response"]]
    lines += ["", "> " + " ".join(d["notes"])]
    return "\n".join(lines)


def _html_report(d: dict[str, Any]) -> str:
    esc = _html.escape
    sections = []
    for key in ("status", "executed", "local_reason", "started_at", "duration_ms",
                "models", "nodes", "privacy", "router", "plan", "distribution",
                "verification", "consensus", "consensus_waived_reason", "assembly",
                "coherence", "error"):
        sections.append(f"<tr><th>{esc(key)}</th><td><code>{esc(_kv(d.get(key)))}"
                        "</code></td></tr>")
    body = (f"<h1>Swarmbly processing report — {esc(d['request_id'])}</h1>"
            f"<table>{''.join(sections)}</table>"
            f"<h2>Pipeline</h2><pre>{esc(_stages_text(d['stages']))}</pre>")
    if "final_response" in d:
        body += f"<h2>Final response</h2><pre>{esc(d['final_response'])}</pre>"
    body += f"<p><em>{esc(' '.join(d['notes']))}</em></p>"
    style = ("body{font-family:system-ui,sans-serif;max-width:960px;margin:2rem auto;"
             "padding:0 1rem;background:#0b0f0d;color:#d7e3dc}th{text-align:left;"
             "vertical-align:top;padding:.4rem 1rem .4rem 0;color:#5ff2a1}"
             "td code{white-space:pre-wrap;word-break:break-word}pre{background:#111915;"
             "padding:1rem;overflow:auto}")
    return ("<!doctype html><html><head><meta charset='utf-8'>"
            f"<title>Swarmbly report {esc(d['request_id'])}</title>"
            f"<style>{style}</style></head><body>{body}</body></html>")
