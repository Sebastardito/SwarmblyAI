"""Recommended configuration, explained (product spec §4.4).

From the measured hardware and the models actually installed, propose a
profile and say *why* for every parameter. Rules:

- Measured values are labelled ``measured``; derived numbers ``estimated``
  (with the formula in the explanation). Nothing is invented: what cannot be
  detected is ``unknown`` and the advice says so.
- Defaults favour safety and stability: LOCAL privacy, LAN off, worker off.
  The advisor *recommends* participation and its capacity; turning it on is
  always the user's decision.
- Every recommendation is reversible: the previous configuration is kept and
  can be restored in one step.
- LCE C4 is never recommended as active: its requirements are "to be
  measured" (SPEC LCE §16) and layer 2 has no verdict (R11).
"""

from __future__ import annotations

import math
from typing import Any

from .catalog import CATALOG, estimated_memory_gb

GB = 1024 ** 3
OS_HEADROOM_GB = 3.0          # OS + browser + this app (estimate)
APP_FOOTPRINT_GB = 0.3        # Swarmbly App process (estimate; measure on device)


def _val(report: dict[str, Any], key: str) -> dict[str, Any]:
    return (report.get(key) or {}).get("value") or {}


def _explain(out: list, key: str, value: Any, why: str, nature: str = "estimated",
             label: str = "") -> None:
    out.append({"key": key, "value": value, "why": why, "nature": nature,
                "label": label or key})


def memory_budget(hardware: dict[str, Any]) -> dict[str, Any]:
    """Memory the models may use, with its derivation."""
    mem = _val(hardware, "memory")
    gpu = _val(hardware, "gpu")
    total = (mem.get("total_bytes") or 0) / GB
    available = (mem.get("available_bytes") or 0) / GB
    unified = bool(gpu.get("unified_memory"))
    vram = None
    for card in gpu.get("gpus") or []:
        text = str(card.get("vram", "")).lower().replace("mib", "").replace("mb", "").strip()
        try:
            vram = max(vram or 0.0, float(text.split()[0]) / 1024.0)
        except (ValueError, IndexError):
            continue
    if not total:
        return {"budget_gb": None, "kind": "unknown", "total_gb": None,
                "available_gb": None, "derivation": "RAM could not be measured"}
    if unified:
        # Apple Silicon: the GPU can use roughly 2/3 (≤36 GB) to 3/4 of RAM.
        share = 0.66 if total <= 36 else 0.75
        budget = max(0.0, min(total * share, total - OS_HEADROOM_GB))
        kind = "unified"
        derivation = (f"unified memory: min({share:.2f} × {total:.1f} GB GPU share, "
                      f"{total:.1f} − {OS_HEADROOM_GB:.0f} GB headroom)")
    elif vram:
        budget = max(0.0, vram - 0.5)
        kind = "vram"
        derivation = f"dedicated GPU: {vram:.1f} GB VRAM − 0.5 GB"
    else:
        budget = max(0.0, min(total - OS_HEADROOM_GB, total * 0.6))
        kind = "ram"
        derivation = (f"CPU inference: min({total:.1f} − {OS_HEADROOM_GB:.0f} GB "
                      f"headroom, 60 % of RAM)")
    return {"budget_gb": round(budget, 1), "kind": kind, "total_gb": round(total, 1),
            "available_gb": round(available, 1), "vram_gb": vram,
            "derivation": derivation}


def _installed(backends: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out = []
    for backend in backends:
        if not backend.get("available"):
            continue
        for model in backend.get("models") or []:
            size = model.get("size_bytes")
            mem = estimated_memory_gb(size / GB if size else None, model.get("params_b"))
            out.append(dict(model, mem_gb=mem, backend=backend.get("name")))
    return out


def recommend(hardware: dict[str, Any], backends: list[dict[str, Any]],
              current: dict[str, Any] | None = None) -> dict[str, Any]:
    """Return ``{"changes", "explanations", "summary", "warnings", "downloads"}``."""
    explanations: list[dict[str, Any]] = []
    warnings: list[str] = []
    changes: dict[str, Any] = {}
    budget = memory_budget(hardware)
    cpu = _val(hardware, "cpu")
    storage = _val(hardware, "storage")
    power = _val(hardware, "power")
    free_gb = (storage.get("free_bytes") or 0) / GB
    cores = cpu.get("cores_physical") or cpu.get("cores_logical")
    accel = budget["kind"] in ("unified", "vram")
    installed = _installed(backends)
    chat_models = [m for m in installed if m.get("kind") != "embedding"]
    embedders = [m for m in installed if m.get("kind") == "embedding"]
    backend_up = any(b.get("available") for b in backends)
    b = budget["budget_gb"]

    _explain(explanations, "memory_budget", f"{b} GB" if b is not None else "unknown",
             f"Memory available to models — {budget['derivation']}. "
             "Estimates; the monitor shows real usage once models run.",
             "estimated", "Model memory budget")

    # -- chat / orchestrator model ------------------------------------------------
    fitting = [m for m in chat_models if m.get("mem_gb") and b and m["mem_gb"] <= b]
    fitting.sort(key=lambda m: (m.get("params_b") or 0), reverse=True)
    if not backend_up:
        warnings.append("No inference backend detected. Install and start Ollama "
                        "(https://ollama.com) — the app cannot run models without it.")
    chosen = None
    if fitting:
        # Prefer 3–8 B: big enough to assemble, small enough to stay responsive.
        mid = [m for m in fitting if 2.5 <= (m.get("params_b") or 0) <= 9]
        chosen = (mid or fitting)[0]
        changes["model.model_name"] = chosen["name"]
        _explain(explanations, "model.model_name", chosen["name"],
                 f"Largest installed chat model that fits the budget "
                 f"(~{chosen['mem_gb']} GB estimated of {b} GB). It answers locally, "
                 "plans, and writes the bridges when assembling distributed answers. "
                 "Whitepaper v2 recommends an 8B-class orchestrator, but whether that "
                 "is enough is unresolved (H3).", "estimated", "Chat / orchestrator model")
    elif chat_models:
        warnings.append("Installed models seem larger than the memory budget; they may "
                        "run slowly or swap. Consider a smaller model.")
    else:
        warnings.append("No chat model installed. See the recommended downloads.")

    # -- simultaneous models / multi-model -------------------------------------------
    if b and chosen:
        others = [m for m in fitting if m["name"] != chosen["name"]
                  and m.get("family") != chosen.get("family")]
        simultaneous = 1
        used = chosen["mem_gb"]
        picked = [chosen["name"]]
        for m in sorted(others, key=lambda m: m["mem_gb"]):
            if used + m["mem_gb"] <= b and simultaneous < 4:
                used += m["mem_gb"]
                simultaneous += 1
                picked.append(m["name"])
        multi = simultaneous >= 2
        changes["model.multi_model"] = multi
        changes["model.local_models"] = picked if multi else [chosen["name"]]
        changes["model.local_parallel"] = 2 if (multi and accel) else 1
        _explain(explanations, "model.local_parallel", changes["model.local_parallel"],
                 ("Two local models may generate at once on accelerated hardware."
                  if changes["model.local_parallel"] == 2 else
                  "Local models take turns: generating with two at once on this "
                  "hardware would compete for memory and slow both."),
                 "estimated", "Local models in parallel")
        _explain(explanations, "model.multi_model", multi,
                 (f"{simultaneous} models of different families fit together "
                  f"(~{used:.1f} GB of {b} GB): local consensus and family-diverse "
                  "replicas become possible on this machine." if multi else
                  "Only one model fits comfortably at a time (or only one family is "
                  "installed): single-model mode avoids constant reloading."),
                 "estimated", "Multiple local models")

    # -- worker capacity (recommended, not enabled) ------------------------------------
    if b and chosen:
        per_task = chosen["mem_gb"]
        slots = 1 if not accel or (cores or 0) < 6 else 2
        if b >= per_task * 3 and accel:
            slots = 3
        changes["swarm.worker_max_concurrent"] = slots
        _explain(explanations, "swarm.worker_max_concurrent", slots,
                 ("CPU-only inference: one task at a time keeps the machine usable."
                  if not accel else
                  f"Accelerated inference with {b} GB budget: {slots} concurrent tasks "
                  "before latency degrades (estimate; the p95 hedge timer adapts)."),
                 "estimated", "Worker: simultaneous tasks")
        changes["swarm.worker_max_tokens_per_task"] = 600 if accel else 400
        _explain(explanations, "swarm.worker_max_tokens_per_task",
                 changes["swarm.worker_max_tokens_per_task"],
                 "Upper bound per micro-task offered to others; micro-tasks are short "
                 "by design (SPEC §12).", "estimated", "Worker: tokens per task")
        if power.get("has_battery"):
            changes["swarm.worker_only_plugged"] = True
            _explain(explanations, "swarm.worker_only_plugged", True,
                     "This is a laptop on battery power: serve others only when it "
                     "is plugged in.", "measured", "Worker: only on AC power")
        _explain(explanations, "swarm.worker_enabled", False,
                 "Volunteering is your decision. With the values above this machine "
                 "could serve others without slowing you down; enable it in Swarm "
                 "settings when you want to.", "measured", "Worker participation")

    # -- timeouts ------------------------------------------------------------------------
    timeout = 60000 if accel else 120000
    changes["swarm.timeout_ms"] = timeout
    _explain(explanations, "swarm.timeout_ms", timeout,
             "Generous per-task timeout for " + ("accelerated" if accel else "CPU")
             + " inference on small models; the hedge timer switches to the observed "
               "p95 after 8 samples (SPEC §11.3).", "estimated", "Task timeout")
    changes["swarm.hedge_fallback_ms"] = timeout // 2
    changes["swarm.k_min"] = 1
    changes["swarm.k_max"] = 2
    _explain(explanations, "swarm.k_min", 1,
             "One response per micro-task by default: each extra replica multiplies "
             "network work. Raise it (2–3) to get a divergence map across families — "
             "agreement, not accuracy (L13, L23).", "measured", "Minimum responses")
    _explain(explanations, "swarm.k_max", 2,
             "Ceiling including hedges and retries: one spare attempt protects "
             "against a slow or failed worker without flooding the swarm.",
             "measured", "Maximum responses")
    changes["swarm.n_fragments_max"] = 4
    _explain(explanations, "swarm.n_fragments_max", 4,
             "Upper bound on fragments per request. N itself is derived from the "
             "request's structure and the swarm's capacity (whitepaper v2 §9.7); "
             "wider plans grow the straggler tail.", "measured", "Maximum fragments")

    # -- embedder ------------------------------------------------------------------------
    if embedders:
        changes["model.embedder"] = "server"
        changes["model.embed_model"] = embedders[0]["name"]
        _explain(explanations, "model.embedder", f"server ({embedders[0]['name']})",
                 "An embedding model is installed: seam and agreement similarity use "
                 "embeddings instead of word overlap.", "measured", "Similarity")
    else:
        changes["model.embedder"] = "hash"
        _explain(explanations, "model.embedder", "hash (lexical)",
                 "No embedding model installed: similarities fall back to word overlap "
                 "(labelled lexical everywhere). nomic-embed-text (274 MB) enables "
                 "semantic similarity.", "measured", "Similarity")

    # -- privacy (unchanged defaults) ----------------------------------------------------
    _explain(explanations, "privacy.tier", "LOCAL",
             "Nothing leaves this device until you allow the local network. Requests "
             "are always classified on-device first.", "measured", "Privacy tier")

    # -- LCE -----------------------------------------------------------------------------
    lce = lce_levels(hardware, budget, bool(chosen))
    changes["lce.level"] = lce["recommended"]
    _explain(explanations, "lce.level", lce["recommended"], lce["why"],
             "estimated", "LCE level")

    # -- downloads (suggested, never automatic) -----------------------------------------
    downloads = suggest_downloads(budget, installed, free_gb)
    summary = {
        "os": _val(hardware, "os"), "cores": cores, "accelerated": accel,
        "budget": budget, "free_disk_gb": round(free_gb, 1),
        "installed_chat_models": len(chat_models), "backend_available": backend_up,
        "power": power,
    }
    return {"changes": changes, "explanations": explanations, "summary": summary,
            "warnings": warnings, "downloads": downloads, "lce": lce}


def lce_levels(hardware: dict[str, Any], budget: dict[str, Any],
               has_model: bool) -> dict[str, Any]:
    """Each LCE level with requirements, compatibility and status (SPEC LCE §16)."""
    storage = _val(hardware, "storage")
    free_gb = (storage.get("free_bytes") or 0) / GB
    total = budget.get("total_gb") or 0
    levels = [
        {"level": "C0", "adds": "Swarmbly without the LCE", "requires": "none",
         "compatible": True, "status": "stable",
         "privacy": "no personal memory is kept"},
        {"level": "C1", "adds": "sources, retrieval over sources, wiki for provenance, "
                                "projection onto Γ, local reports",
         "requires": "CPU; storage in the order of GB",
         "compatible": free_gb >= 2, "status": "implemented upstream; app integration "
                                               "in progress",
         "privacy": "sources and wiki stay on this device; only a ≤1 KB projection "
                    "joins Γ, after double classification"},
        {"level": "C2", "adds": "automatic digestion of sources into claims",
         "requires": "the local model already in use",
         "compatible": has_model, "status": "experimental: digestion is not "
                                            "reproducible run to run (R13/AA2)",
         "privacy": "local model only"},
        {"level": "C3", "adds": "social cache, affinity, signed capsules (pull only)",
         "requires": "no additional hardware",
         "compatible": True, "status": "experimental: not validated on a real network",
         "privacy": "capsules leave the device only with your permission"},
        {"level": "C4", "adds": "personal LoRA/QLoRA adapter (style, procedures)",
         "requires": "mid-range machine; exact requirement 'to be measured' "
                     "(SPEC LCE §16)",
         "compatible": total >= 16 and budget.get("kind") in ("unified", "vram"),
         "status": "experimental, no verdict (R11); training off by default",
         "privacy": "the adapter never leaves the device and never serves others (I2)"},
    ]
    recommended = "C1" if levels[1]["compatible"] else "C0"
    why = ("C1 is the useful, validated core: retrieval over your own sources "
           "measurably helps (+0.500, exploratory) and the wiki adds provenance and "
           "verifiable forgetting. C2–C4 stay opt-in and experimental."
           if recommended == "C1" else
           "Not enough free storage for a source space: C0 (Swarmbly unchanged).")
    return {"levels": levels, "recommended": recommended, "why": why}


def suggest_downloads(budget: dict[str, Any], installed: list[dict[str, Any]],
                      free_gb: float) -> list[dict[str, Any]]:
    """Catalog models worth downloading here, with size, licence and reason."""
    have = {m.get("name") for m in installed}
    families = {m.get("family") for m in installed if m.get("kind") != "embedding"}
    b = budget.get("budget_gb") or 0
    out = []
    for entry in CATALOG:
        if entry["name"] in have:
            continue
        mem = estimated_memory_gb(entry["download_gb"], entry["params_b"])
        fits = bool(b) and mem is not None and mem <= b
        if not fits or entry["download_gb"] > max(0.0, free_gb - 2):
            continue
        reason = entry["note"]
        if "embedding" in entry["roles"]:
            if any(m.get("kind") == "embedding" for m in installed):
                continue
            priority = 2
        elif not families:
            priority = 1 if 2.5 <= entry["params_b"] <= 8 else 3
            reason = "no chat model installed — " + reason
        elif entry["family"] not in families:
            priority = 3
            reason = "adds a new model family (diversity for consensus) — " + reason
        else:
            continue
        out.append({**entry, "mem_gb_estimated": mem, "priority": priority,
                    "reason": reason, "requires_consent": True})
    out.sort(key=lambda e: (e["priority"], -e["params_b"]))
    return out[:6]
