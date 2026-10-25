/* Settings: data-driven fields, each with a one-line explanation. Changes are
   saved immediately and validated by the server. Three profiles: Automatic
   (the recommended configuration, applied and explained), Custom (the
   everyday fields), Advanced (every parameter). */
"use strict";

const Settings = (() => {
  const { h, clear, t, chip, button, toggle, select, readout } = UI;
  const TABS = ["recommended", "general", "models", "swarm", "privacy", "results", "permissions", "system"];
  let root;
  let tab = "recommended";
  const els = {};
  let installed = [];          // installed models (from /api/models)
  const pulls = {};            // name -> progress element

  // key, type, options/range, advanced, tab
  const FIELDS = {
    general: [
      { key: "language", type: "select", options: [["en", "English"], ["es", "Español"]] },
      { key: "theme", type: "select", options: [["dark", "theme.dark"], ["light", "theme.light"]] },
      { key: "reduce_motion", type: "bool" },
      { key: "output_dir", type: "text", placeholder: "<data>/output" },
      { key: "log_retention_days", type: "number", min: 1, max: 3650, advanced: true },
    ],
    models: [
      { key: "model.backend", type: "select", options: [["auto", "backend.auto"], ["ollama", "Ollama"], ["openai_compat", "backend.openai"]] },
      { key: "model.backend_url", type: "text", placeholder: "http://127.0.0.1:11434" },
      { key: "model.api_key", type: "password", advanced: true },
      { key: "model.model_name", type: "model" },
      { key: "model.multi_model", type: "bool" },
      { key: "model.local_models", type: "models", showIf: (c) => c.model?.multi_model },
      { key: "model.local_parallel", type: "number", min: 1, max: 4, showIf: (c) => c.model?.multi_model },
      { key: "model.max_tokens", type: "number", min: 16, max: 32768 },
      { key: "model.temperature", type: "number", min: 0, max: 2, step: 0.1 },
      { key: "model.max_tokens_per_fragment", type: "number", min: 16, max: 8192, advanced: true },
      { key: "model.embedder", type: "select", options: [["hash", "embedder.hash"], ["server", "embedder.server"]] },
      { key: "model.embed_model", type: "text", advanced: true },
    ],
    swarm: [
      { key: "swarm.mode", type: "select", options: [["local", "mode.local"], ["lan", "mode.lan"], ["auto", "mode.auto"]] },
      { key: "swarm.lan_enabled", type: "bool" },
      { key: "swarm.k_min", type: "number", min: 1, max: 8 },
      { key: "swarm.k_max", type: "number", min: 1, max: 8 },
      { key: "swarm.n_fragments_max", type: "number", min: 2, max: 16 },
      { key: "swarm.max_concurrency", type: "number", min: 1, max: 64 },
      { key: "swarm.timeout_ms", type: "number", min: 1000, max: 600000, step: 1000 },
      { key: "swarm.worker_enabled", type: "bool", group: "worker" },
      { key: "swarm.worker_paused", type: "bool", group: "worker" },
      { key: "swarm.worker_models", type: "models", group: "worker" },
      { key: "swarm.worker_max_concurrent", type: "number", min: 1, max: 16, group: "worker" },
      { key: "swarm.worker_max_tokens_per_task", type: "number", min: 16, max: 8192, group: "worker" },
      { key: "swarm.worker_only_idle", type: "bool", group: "worker" },
      { key: "swarm.worker_only_plugged", type: "bool", group: "worker" },
      { key: "swarm.worker_max_task_seconds", type: "number", min: 5, max: 3600, group: "worker", advanced: true },
      { key: "swarm.hedge_fallback_ms", type: "number", min: 200, max: 600000, step: 500, advanced: true },
      { key: "swarm.tau_sem", type: "number", min: 0, max: 1, step: 0.05, advanced: true },
      { key: "swarm.discovery_ttl_s", type: "number", min: 30, max: 86400, advanced: true },
      { key: "swarm.p2p_port", type: "number", min: 1024, max: 65535, advanced: true },
    ],
    privacy: [
      { key: "privacy.tier", type: "select", options: [["LOCAL", "tier.LOCAL"], ["GLOBAL", "tier.GLOBAL"], ["TRUSTED", "tier.TRUSTED"]] },
      { key: "privacy.trusted_networks", type: "list", advanced: true },
      { key: "evidence.enabled", type: "bool", group: "evidence" },
      { key: "evidence.timeout_s", type: "number", min: 0.5, max: 30, step: 0.5, group: "evidence", advanced: true },
      { key: "evidence.max_chars", type: "number", min: 60, max: 1000, step: 10, group: "evidence", advanced: true },
      { key: "evidence.max_items", type: "number", min: 1, max: 100, group: "evidence", advanced: true },
      { key: "evidence.local_answers", type: "bool", group: "evidence" },
      { key: "evidence.local_max_entities", type: "number", min: 1, max: 6, group: "evidence", advanced: true },
      { key: "evidence.fusion_model", type: "model", allowEmpty: true, group: "evidence", advanced: true },
      { key: "evidence.providers", type: "list", group: "evidence", advanced: true },
      { key: "evidence.searxng_url", type: "text", group: "evidence", advanced: true },
      { key: "evidence.google_cse_key", type: "password", group: "evidence", advanced: true },
      { key: "evidence.google_cse_cx", type: "text", group: "evidence", advanced: true },
    ],
    results: [
      { key: "results.export_format", type: "select", options: [["markdown", "Markdown"], ["json", "JSON"], ["html", "HTML"]] },
      { key: "results.report_detail", type: "select", options: [["minimal", "detail.minimal"], ["standard", "detail.standard"], ["full", "detail.full"]] },
      { key: "results.auto_report", type: "bool" },
      { key: "results.export_dir", type: "text", placeholder: "<data>/output" },
      { key: "results.keep_stats", type: "bool" },
    ],
  };

  function init(el) {
    root = el;
    build();
    App.onEvent(onEvent);
  }

  function build() {
    clear(root);
    els.tabs = h("div.tabs", { role: "tablist", "aria-label": t("settings.title") },
      TABS.map((name) => h("button.tab", { type: "button", role: "tab", dataset: { tab: name },
        "aria-selected": String(name === tab), onclick: () => { tab = name; renderTab(); } },
      t(`settings.tab.${name}`))));
    els.profile = select(["automatic", "custom", "advanced"].map((p) => ({ value: p, label: t(`profile.${p}`) })),
      App.state.config?.profile || "custom", async (v) => {
        await App.saveConfig({ profile: v }, { quiet: true });
        renderTab();
      }, { "aria-label": t("settings.profile") });
    els.body = h("div.settings-body", { role: "tabpanel" });
    UI.append(root,
      h("header.view-head", h("h1.view-title", t("settings.title")),
        h("label.inline", h("span", t("settings.profile")), els.profile)),
      h("p.view-lede", t("settings.lede")),
      els.tabs, els.body);
  }

  async function show() {
    try {
      const data = await Api.get("/api/models");
      installed = (data.backends || []).flatMap((b) => (b.models || []).map((m) => ({ ...m, backend: b.name })));
    } catch (_) { installed = []; }
    renderTab();
  }

  function renderTab() {
    els.tabs.querySelectorAll(".tab").forEach((b) => b.setAttribute("aria-selected", String(b.dataset.tab === tab)));
    clear(els.body);
    const fn = { recommended: renderRecommended, permissions: renderPermissions, system: renderSystem }[tab];
    if (fn) return fn();
    renderFields(FIELDS[tab] || []);
    if (tab === "models") renderModelsExtra();
    if (tab === "privacy") { renderWebSearch(); renderIdentity(); }
  }

  // ---- generic fields ------------------------------------------------------------
  function get(cfg, key) { return key.split(".").reduce((n, k) => (n ? n[k] : undefined), cfg); }

  function renderFields(fields) {
    const cfg = App.state.config || {};
    const advanced = (cfg.profile || "custom") === "advanced";
    let group = null;
    const list = h("div.fields");
    for (const f of fields) {
      if (f.advanced && !advanced) continue;
      if (f.showIf && !f.showIf(cfg)) continue;
      if (f.group && f.group !== group) {
        group = f.group;
        list.appendChild(h("h3.field-group", t(`field.group.${group}`)));
      }
      list.appendChild(fieldRow(f, get(cfg, f.key)));
    }
    if (!advanced) list.appendChild(h("p.muted", t("settings.moreInAdvanced")));
    els.body.appendChild(list);
  }

  function fieldRow(f, value) {
    const id = f.key.replace(/\./g, "__");
    const label = t(`setting.${id}.label`, f.key);
    const help = t(`setting.${id}.help`, "");
    const save = (v) => {
      if (f.key === "language") return App.setLanguage(v);
      return App.saveConfig(nested(f.key, v)).then(() => {
        if (["model.multi_model", "profile"].includes(f.key)) renderTab();
      }).catch(() => renderTab());
    };
    let control;
    if (f.type === "bool") {
      control = toggle(!!value, save, null, { "aria-label": label });
    } else if (f.type === "select") {
      control = select(f.options.map(([v, l]) => ({ value: v, label: t(l, l) })), value, save,
        { "aria-label": label });
    } else if (f.type === "number") {
      control = h("input", { type: "number", min: f.min, max: f.max, step: f.step || 1,
        value: value ?? "", "aria-label": label });
      control.addEventListener("change", () => save(Number(control.value)));
    } else if (f.type === "model") {
      const chat = installed.filter((m) => m.kind !== "embedding").map((m) => ({ value: m.name, label: m.name }));
      if (value && !chat.some((o) => o.value === value)) chat.unshift({ value, label: `${value} (${t("settings.notInstalled")})` });
      if (f.allowEmpty) chat.unshift({ value: "", label: t("settings.sameModel") });
      control = select(chat.length ? chat : [{ value: "", label: t("chat.noModel") }], value, save,
        { "aria-label": label });
    } else if (f.type === "models") {
      const chosen = new Set(value || []);
      const chat = installed.filter((m) => m.kind !== "embedding");
      control = h("div.checks", { role: "group", "aria-label": label },
        chat.length ? chat.map((m) => {
          const box = h("input", { type: "checkbox" });
          box.checked = chosen.has(m.name);
          box.addEventListener("change", () => {
            if (box.checked) chosen.add(m.name); else chosen.delete(m.name);
            save([...chosen]);
          });
          return h("label.check", box, h("span", m.name), m.family ? chip(m.family) : null);
        }) : h("span.muted", t("chat.noModel")));
    } else if (f.type === "list") {
      control = h("textarea", { rows: 2, "aria-label": label });
      control.value = (value || []).join("\n");
      control.addEventListener("change", () =>
        save(control.value.split(/\n|,/).map((s) => s.trim()).filter(Boolean)));
    } else {
      control = h("input", { type: f.type === "password" ? "password" : "text",
        placeholder: f.placeholder || "", "aria-label": label, autocomplete: "off" });
      control.value = value ?? "";
      control.addEventListener("change", () => save(control.value.trim() || null));
    }
    return h("div.field-row", h("div.field-text", h("span.field-label", label),
      help ? h("span.field-help", help) : null), h("div.field-control", control));
  }

  function nested(key, value) {
    const parts = key.split(".");
    if (parts.length === 1) return { [key]: value };
    return { [parts[0]]: { [parts.slice(1).join(".")]: value } };
  }

  // ---- recommended profile ----------------------------------------------------------
  async function renderRecommended() {
    els.body.appendChild(h("p.muted", t("settings.analyzing")));
    let rec;
    try { rec = await Api.get("/api/setup/recommendation"); } catch (e) {
      clear(els.body).appendChild(h("p.error", e.message));
      return;
    }
    clear(els.body);
    els.body.appendChild(Recommendation.view(rec, { onApplied: () => { show(); } }));
  }

  // ---- models: installed list, downloads -------------------------------------------
  async function renderModelsExtra() {
    const box = h("section.subpanel", h("h3", t("models.installed")));
    if (!installed.length) box.appendChild(h("p.empty", t("models.none")));
    else {
      box.appendChild(h("ul.model-list", installed.map((m) => h("li",
        h("span.model-name", m.name),
        m.family ? chip(m.family) : null,
        m.parameter_size ? chip(m.parameter_size) : null,
        m.quantization ? chip(m.quantization) : null,
        m.size_bytes ? chip(UI.fmtBytes(m.size_bytes)) : null,
        m.kind === "embedding" ? chip(t("models.embedding"), "net") : null,
        button(t("models.licence"), () => showLicence(m.name), "ghost small")))));
    }
    els.body.appendChild(box);
    const downloads = h("section.subpanel", h("h3", t("models.download")),
      h("p.muted", t("models.downloadNote")));
    let rec = null;
    try { rec = await Api.get("/api/setup/recommendation"); } catch (_) { /* offline */ }
    for (const d of rec?.downloads || []) downloads.appendChild(downloadRow(d));
    const custom = h("input", { type: "text", placeholder: "mistral:7b", "aria-label": t("models.customName") });
    downloads.appendChild(h("div.inline-form", custom,
      button(t("models.downloadOther"), () => custom.value.trim() && Downloads.ask(custom.value.trim()), "small")));
    els.body.appendChild(downloads);
  }

  function downloadRow(d) {
    const progress = h("span.pull-progress");
    pulls[d.name] = progress;
    return h("div.download-row",
      h("div", h("strong", d.name), h("span.muted", ` ${d.reason}`)),
      h("div.chips", chip(`${d.download_gb} GB`), chip(d.license, d.license.includes("non-commercial") ? "warn" : ""),
        chip(t("models.memEstimate").replace("{gb}", d.mem_gb_estimated), "", t("nature.estimated"))),
      progress,
      button(t("models.downloadBtn"), () => Downloads.ask(d.name), "small"));
  }

  async function showLicence(name) {
    let info;
    try { info = await Api.get(`/api/models/info?name=${encodeURIComponent(name)}`); }
    catch (e) { UI.toast(e.message, "error"); return; }
    UI.modal(t("models.licenceTitle").replace("{name}", name),
      h("pre.licence", info.license || t("models.noLicence")),
      [{ label: t("common.close"), value: null, kind: "primary" }]);
  }

  function onEvent(event) {
    if (event.type === "searxng.install") {
      const p = event.payload || {};
      if (p.status === "done") { UI.toast(t("websearch.ready"), "ok"); show(); }
      else if (p.status === "failed") { UI.toast(t("websearch.failed"), "error"); refreshWebSearch(); }
      else if (tab === "privacy") refreshWebSearch();
      return;
    }
    if (event.type !== "models.pull") return;
    const p = event.payload || {};
    const el = pulls[p.name];
    if (el) el.textContent = p.status === "running"
      ? `${p.percent ?? 0}% ${p.detail || ""}` : t(`models.pull.${p.status}`, p.status);
    if (p.status === "done") {
      UI.toast(t("models.pulled").replace("{name}", p.name), "ok");
      if (tab === "models") show();
    } else if (p.status === "failed") {
      UI.toast(`${p.name}: ${p.detail}`, "error");
    }
  }

  // ---- privacy: optional web search (local SearXNG, Google) -----------------------------
  let searxBox = null;
  async function renderWebSearch() {
    searxBox = h("section.subpanel");
    els.body.appendChild(searxBox);
    await refreshWebSearch();
  }

  async function refreshWebSearch() {
    if (!searxBox) return;
    let s;
    try { s = await Api.get("/api/evidence/searxng"); } catch (e) { s = null; }
    clear(searxBox);
    searxBox.appendChild(h("h3", t("websearch.title")));
    searxBox.appendChild(h("p.muted", t("websearch.body")));
    if (!s) return;
    const job = s.job;
    let state;
    if (job && job.status === "running") state = t("websearch.installing").replace("{step}", t(`websearch.step.${job.step}`, job.step));
    else if (s.managed && s.running) state = t("websearch.running").replace("{url}", s.url).replace("{method}", s.managed);
    else if (s.managed) state = t("websearch.stopped").replace("{url}", s.url);
    else if (s.url) state = t("websearch.external").replace("{url}", s.url);
    else state = t("websearch.none");
    searxBox.appendChild(h("p", chip(state, s.running ? "ok" : (job && job.status === "running" ? "net" : ""))));
    if (job && job.status === "failed") searxBox.appendChild(h("p.error", (job.log || []).slice(-1)[0] || ""));
    if (s.url && !s.web_enabled) searxBox.appendChild(h("p.caveat", t("websearch.webOff")));
    const row = h("div.inline-form");
    if (!s.managed && !(job && job.status === "running"))
      row.appendChild(button(t("websearch.install"), askInstall, "small"));
    if (s.managed && !(job && job.status === "running"))
      row.appendChild(button(t("websearch.reinstall"), askInstall, "ghost small"));
    row.appendChild(button(t("websearch.test"), testWeb, "ghost small"));
    if (s.managed) row.appendChild(button(t("websearch.uninstall"), async () => {
      try { await Api.post("/api/evidence/searxng/uninstall"); UI.toast(t("websearch.removed"), "ok"); }
      catch (e) { UI.toast(e.message, "error"); }
      show();
    }, "ghost small"));
    searxBox.appendChild(row);
    searxBox.appendChild(h("p.caveat", t("websearch.google")));
  }

  async function askInstall() {
    if (App.state.config?.permissions?.internet === false) { UI.toast(t("websearch.noInternet"), "error"); return; }
    const s = await Api.get("/api/evidence/searxng").catch(() => ({}));
    const how = s.docker ? t("websearch.howDocker") : (s.python ? t("websearch.howNative") : t("websearch.howNone"));
    const body = h("div.form",
      h("p", t("websearch.consentBody")),
      h("p.muted", how),
      h("p.muted", t("websearch.consentPrivacy")));
    const ok = await UI.modal(t("websearch.consentTitle"), body, [
      { label: t("common.cancel"), value: false, kind: "ghost" },
      { label: t("websearch.consentAccept"), value: true, kind: "primary", attrs: { disabled: !s.docker && !s.python } }]);
    if (!ok) return;
    try {
      await Api.post("/api/evidence/searxng/install", { consent: true, method: "auto" });
      UI.toast(t("websearch.started"), "ok");
    } catch (e) { UI.toast(e.message, "error"); }
    refreshWebSearch();
  }

  async function testWeb() {
    try {
      const r = await Api.post("/api/evidence/web/test");
      if (r.ok) UI.toast(t("websearch.testOk").replace("{n}", r.results).replace("{engines}", (r.engines || []).join(", ")), "ok");
      else UI.toast(t("websearch.testFail").replace("{why}", r.error || (r.unresponsive || []).join(", ") || "0"), "error");
    } catch (e) { UI.toast(e.message, "error"); }
  }

  // ---- privacy: identity --------------------------------------------------------------
  function renderIdentity() {
    els.body.appendChild(h("section.subpanel",
      h("h3", t("privacy.identity")),
      h("p.muted", t("privacy.identityBody")),
      h("code.path", App.state.health?.node_id || "—"),
      h("p.caveat", t("privacy.lanNotTrust"))));
  }

  // ---- permissions -------------------------------------------------------------------
  function renderPermissions() {
    const perms = App.state.config?.permissions || {};
    const rows = ["lan_discovery", "model_downloads", "internet"].map((key) => {
      const value = perms[key];
      const state = value === true ? "granted" : value === false ? "refused" : "unasked";
      return h("div.field-row",
        h("div.field-text", h("span.field-label", t(`perm.${key}.label`)),
          h("span.field-help", t(`perm.${key}.help`))),
        h("div.field-control",
          chip(t(`perm.state.${state}`), state === "granted" ? "ok" : state === "refused" ? "danger" : ""),
          toggle(value === true, async (on) => {
            try {
              await Api.post("/api/permissions", { [key]: on });
              await App.reloadConfig();
              await App.refreshSwarm();
            } catch (e) { UI.toast(e.message, "error"); }
            renderTab();
          }, null, { "aria-label": t(`perm.${key}.label`), disabled: key === "internet" })));
    });
    els.body.appendChild(h("div.fields", rows));
  }

  // ---- system (dependency doctor) ---------------------------------------------------
  async function renderSystem() {
    els.body.appendChild(h("p.muted", t("settings.analyzing")));
    let d;
    try { d = await Api.get("/api/doctor"); } catch (e) {
      clear(els.body).appendChild(h("p.error", e.message));
      return;
    }
    clear(els.body);
    els.body.appendChild(Doctor.view(d, () => renderTab()));
  }

  function relabel() { build(); renderTab(); }

  return { init, show, relabel };
})();

/* Recommended configuration with its reasons (shared with the setup assistant). */
const Recommendation = (() => {
  const { h, t, chip, button } = UI;

  function view(rec, { onApplied, compact = false } = {}) {
    const box = h("div.recommendation");
    if (rec.warnings?.length) box.appendChild(h("ul.warnings", rec.warnings.map((w) => h("li", w))));
    const b = rec.summary?.budget || {};
    box.appendChild(h("div.readouts",
      UI.readout(t("rec.ram"), b.total_gb ? `${b.total_gb} GB` : null, "measured"),
      UI.readout(t("rec.memoryKind"), t(`rec.kind.${b.kind}`, b.kind), "measured"),
      UI.readout(t("rec.budget"), b.budget_gb ? `${b.budget_gb} GB` : null, "estimated"),
      UI.readout(t("rec.cores"), rec.summary?.cores, "measured"),
      UI.readout(t("rec.disk"), rec.summary?.free_disk_gb ? `${rec.summary.free_disk_gb} GB` : null, "measured"),
      UI.readout(t("rec.backend"), t(rec.summary?.backend_available ? "common.yes" : "common.no"), "measured")));
    box.appendChild(h("ol.reasons", rec.explanations.map((e) => h("li.reason",
      h("div.reason-head", h("span.reason-label", e.label), h("span.reason-value", fmt(e.value)),
        h(`span.nature.${e.nature}`, t(`nature.${e.nature}`))),
      compact ? null : h("p.reason-why", e.why)))));
    const actions = h("div.form-actions",
      button(t("rec.apply"), async () => {
        try {
          await Api.post("/api/setup/apply", {});
          await App.reloadConfig();
          UI.toast(t("rec.applied"), "ok");
          onApplied?.();
        } catch (err) { UI.toast(err.message, "error"); }
      }, "primary"),
      button(t("rec.revert"), async () => {
        try {
          await Api.post("/api/setup/revert", {});
          await App.reloadConfig();
          UI.toast(t("rec.reverted"), "ok");
          onApplied?.();
        } catch (err) { UI.toast(err.message, "error"); }
      }, "ghost"));
    box.appendChild(actions);
    box.appendChild(h("p.muted", t("rec.reversible")));
    return box;
  }

  function fmt(v) {
    if (typeof v === "boolean") return t(v ? "common.yes" : "common.no");
    if (Array.isArray(v)) return v.join(", ");
    return String(v);
  }

  return { view };
})();

/* Consented downloads through Ollama. */
const Downloads = (() => {
  const { h, t, chip } = UI;

  async function ask(name) {
    if (App.state.config?.permissions?.model_downloads === false) {
      UI.toast(t("models.downloadsRefused"), "error");
      return false;
    }
    let p;
    try { p = await Api.get(`/api/models/preview?name=${encodeURIComponent(name)}`); }
    catch (e) { UI.toast(e.message, "error"); return false; }
    const body = h("div.form",
      h("p", t("models.consentBody")),
      h("dl.facts",
        h("dt", t("models.size")), h("dd", p.download_gb ? `${p.download_gb} GB` : t("models.sizeUnknown")),
        h("dt", t("models.licenceLabel")), h("dd", p.license),
        h("dt", t("models.origin")), h("dd", p.origin),
        h("dt", t("models.page")), h("dd", h("a", { href: p.page, target: "_blank", rel: "noopener noreferrer" }, p.page)),
        h("dt", t("models.freeDisk")), h("dd", `${p.free_disk_gb} GB`)),
      p.enough_space ? null : h("p.error", t("models.noSpace")),
      p.checked_on ? h("p.muted", t("models.checkedOn").replace("{date}", p.checked_on)) : null,
      String(p.license).includes("non-commercial") ? chip(t("models.nonCommercial"), "warn") : null);
    const ok = await UI.modal(t("models.consentTitle").replace("{name}", name), body, [
      { label: t("common.cancel"), value: false, kind: "ghost" },
      { label: t("models.consentAccept"), value: true, kind: "primary", attrs: { disabled: !p.enough_space } }]);
    if (!ok) return false;
    try {
      await Api.post("/api/models/pull", { name, consent: true });
      UI.toast(t("models.pulling").replace("{name}", name), "ok");
      return true;
    } catch (e) { UI.toast(e.message, "error"); return false; }
  }

  return { ask };
})();

/* Dependency checks with consented installation. */
const Doctor = (() => {
  const { h, t, chip, button } = UI;

  function view(d, onChange) {
    const box = h("div.doctor");
    const ok = (s) => (s === "ok" ? "ok" : s === "missing" || s === "too_old" ? "danger" : "warn");
    box.appendChild(h("div.readouts",
      UI.readout("Python", `${d.python.version}`, "measured"),
      UI.readout(t("doctor.venv"), t(d.python.virtualenv ? "common.yes" : "common.no"), "measured"),
      UI.readout(t("doctor.ready"), t(d.ready ? "common.yes" : "common.no"), "measured"),
      UI.readout(t("doctor.inference"), t(d.inference_ready ? "common.yes" : "common.no"), "measured")));
    const o = d.ollama;
    box.appendChild(h("section.subpanel", h("h3", "Ollama"),
      h("p", chip(t(`doctor.state.${o.status}`, o.status), ok(o.status)), " ",
        o.version ? chip(`v${o.version}`) : null, " ", h("span.muted", t("doctor.ollamaPurpose"))),
      o.fix ? h("p.note", o.fix) : null));
    box.appendChild(h("section.subpanel", h("h3", t("doctor.packages")),
      h("div.table-wrap", h("table.data",
        h("thead", h("tr", ["package", "purpose", "version", "status"].map((k) => h("th", { scope: "col" }, t(`doctor.col.${k}`))))),
        h("tbody", d.packages.map((p) => h("tr",
          h("td", h("code", p.name)), h("td", p.purpose),
          h("td", `${p.version || "—"}${p.installed_commit ? ` @${p.installed_commit}` : ""}`),
          h("td", chip(t(`doctor.state.${p.status}`, p.status).replace("{pin}", p.pinned_commit || ""), ok(p.status))))))))));
    if (d.installable?.length) {
      box.appendChild(button(t("doctor.install").replace("{n}", d.installable.length), async () => {
        const yes = await UI.modal(t("doctor.installTitle"), h("div",
          h("p", t("doctor.installBody")), h("ul", d.installable.map((p) => h("li", h("code", p))))),
        [{ label: t("common.cancel"), value: false, kind: "ghost" },
         { label: t("doctor.installAccept"), value: true, kind: "primary" }]);
        if (!yes) return;
        try {
          await Api.post("/api/doctor/install", { packages: d.installable, consent: true });
          UI.toast(t("doctor.installing"), "ok");
        } catch (e) { UI.toast(e.message, "error"); }
      }, "primary"));
    } else if (d.manual_command) {
      box.appendChild(h("p.note", t("doctor.manual")), h("code.path", d.manual_command));
    }
    box.appendChild(h("section.subpanel", h("h3", t("doctor.network")),
      h("ul.plain", d.ports.map((p) => h("li", h("code", `${p.name} ${p.port}`), " ",
        chip(t(`doctor.port.${p.status}`, p.status)), " ", h("span.muted", p.purpose)))),
      h("p.muted", t("doctor.firewall"))));
    box.appendChild(h("p.muted", `${t("doctor.dataDir")} `, h("code", d.data_dir.path)));
    box.appendChild(button(t("doctor.recheck"), onChange, "ghost small"));
    return box;
  }

  return { view };
})();

App.register("settings", Settings);
