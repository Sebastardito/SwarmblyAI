/* Request pipeline drawn as a DNA strand: two backbones cross between stages,
   each stage is a rung whose base dot carries the status. Statuses are the
   orchestrator's own: pending, running, completed, partial, skipped, failed —
   a stage that did not apply is drawn skipped, never completed. */
"use strict";

const Helix = (() => {
  const { h, svg } = UI;
  const ORDER = ["REQUEST RECEIVED", "PRIVACY CLASSIFICATION", "ROUTING / DECOMPOSABILITY",
    "TASK PLANNING", "PACKET GENERATION", "NODE SELECTION", "DISPATCHING",
    "MODEL EXECUTION", "RESULT RECEPTION", "VERIFICATION", "CONSENSUS / ALIGNMENT",
    "ASSEMBLY", "COHERENCE REPORT", "FINAL RESPONSE"];

  // Fields worth showing per stage (in this order); everything else stays in reports.
  const FIELDS = ["tier", "lane", "decomposable", "path", "n_tasks", "n_levels",
    "n_packets", "rho_achieved", "privacy_check", "workers", "families", "k_min", "k_max",
    "attempts", "hedges", "retries", "accepted", "failed", "timeouts",
    "signatures_checked", "signature_failures", "layer1_commitment",
    "mean_agreement", "tasks", "n_seams", "bridges", "seam_policy",
    "entity_grid", "mean_seam_similarity", "total_ms"];

  function stageKey(name) {
    return "stage." + String(name).toLowerCase().replace(/[^a-z]+/g, "_").replace(/^_|_$/g, "");
  }

  function fmtValue(v) {
    if (Array.isArray(v)) return v.join(", ");
    if (typeof v === "boolean") return I18n.t(v ? "common.yes" : "common.no");
    if (typeof v === "number") return Number.isInteger(v) ? String(v) : v.toFixed(3);
    if (v && typeof v === "object") return Object.keys(v).length ? JSON.stringify(v) : "";
    return String(v ?? "");
  }

  function strandSegment(index) {
    const seg = svg("svg", { class: "strand", viewBox: "0 0 44 100", preserveAspectRatio: "none",
      "aria-hidden": "true" });
    const a = index % 2 === 0;
    seg.appendChild(svg("path", { class: "backbone b1", "vector-effect": "non-scaling-stroke",
      d: a ? "M8 0 C8 50 36 50 36 100" : "M36 0 C36 50 8 50 8 100" }));
    seg.appendChild(svg("path", { class: "backbone b2", "vector-effect": "non-scaling-stroke",
      d: a ? "M36 0 C36 50 8 50 8 100" : "M8 0 C8 50 36 50 36 100" }));
    return seg;
  }

  /* stages: list of {stage, status, ...detail}. Returns an element. */
  function render(stages, { compact = false } = {}) {
    const byName = Object.fromEntries((stages || []).map((s) => [s.stage, s]));
    const extra = (stages || []).filter((s) => !ORDER.includes(s.stage));
    const list = h("ol.helix", { class: compact ? "compact" : "" });
    [...ORDER, ...extra.map((s) => s.stage)].forEach((name, i) => {
      const s = byName[name] || { stage: name, status: "pending" };
      const status = s.status || "pending";
      const fields = compact ? [] : FIELDS.filter((k) => k in s && fmtValue(s[k]) !== "")
        .map((k) => h("span.kv", h("span.kv-k", I18n.t(`field.${k}`, k)),
          h("span.kv-v", fmtValue(s[k]))));
      const reason = s.reason || s.detail || "";
      list.appendChild(h(`li.rung.${status}`, { title: name },
        strandSegment(i),
        h("span.base", { "aria-hidden": "true" }),
        h("div.rung-body",
          h("div.rung-head",
            h("span.rung-name", I18n.t(stageKey(name), name)),
            h(`span.status-word.${status}`, I18n.t(`status.${status}`, status)),
            s.elapsed_ms !== undefined && s.elapsed_ms !== null
              ? h("span.rung-time", UI.fmtMs(s.elapsed_ms)) : null),
          reason && !compact ? h("div.rung-reason", String(reason)) : null,
          fields.length ? h("div.rung-fields", fields) : null)));
    });
    return list;
  }

  return { render, ORDER, stageKey };
})();
