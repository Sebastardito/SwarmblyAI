/* Settings: data-driven fields, each with a one-line explanation. Changes are
   saved immediately and validated by the server. Three profiles: Automatic
   (the recommended configuration, applied and explained), Custom (the
   everyday fields), Advanced (every parameter). */
"use strict";

const Settings = (() => {
  const { h, clear, t, chip, button, toggle, select, readout } = UI;
  const TABS = ["recommended", "general", "models", "swarm", "privacy", "tools", "results", "permissions", "system"];
  let root;
  let tab = "recommended";
  const els = {};
  let installed = [];          // installed models (from /api/models)
  const pulls = {};            // name -> progress element
  const toolProposals = new Map();   // server id -> live manifest shown for approval

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
      { key: "model.backend", type: "select", options: [["auto", "backend.auto"], ["ollama", "Ollama"], ["openai_compat", "backend.openai"], ["anthropic", "backend.anthropic"]] },
      { key: "model.backend_url", type: "text", placeholder: "http://127.0.0.1:11434" },
      { key: "model.api_key", type: "password", advanced: true },
      // 3.2: shown for every backend: an Ollama on this computer forwards its cloud models
      { key: "privacy.third_party_models", type: "list" },
      { key: "privacy.third_party_passages", type: "bool" },
      { key: "model.model_name", type: "model" },
      // 3.3: models by role. Empty = the conversation's model.
      { key: "roles.writer.model", type: "model", allowEmpty: true, group: "roles",
        textIf: (c) => !!c.roles?.writer?.backend },
      { key: "roles.writer.think", type: "tri", group: "roles" },
      { key: "roles.search_terms.model", type: "model", allowEmpty: true, group: "roles" },
      { key: "roles.fusion.model", type: "model", allowEmpty: true, group: "roles" },
      // 3.4: embeddings for retrieval. Empty keeps the app's previous embedder.
      { key: "roles.embeddings.model", type: "embedding", allowEmpty: true, group: "roles",
        textIf: (c) => c.roles?.embeddings?.backend === "openai_compat" },
      { key: "roles.embeddings.backend", type: "select", group: "roles", advanced: true,
        options: [["", "settings.defaultEmbedder"], ["ollama", "Ollama"], ["openai_compat", "backend.openai"]] },
      { key: "roles.embeddings.backend_url", type: "text", group: "roles", advanced: true,
        showIf: (c) => !!c.roles?.embeddings?.backend },
      { key: "roles.embeddings.api_key", type: "password", group: "roles", advanced: true,
        showIf: (c) => c.roles?.embeddings?.backend === "openai_compat" },
      { key: "roles.writer.backend", type: "select", group: "roles", advanced: true,
        options: [["", "settings.sameServer"], ["ollama", "Ollama"], ["openai_compat", "backend.openai"], ["anthropic", "backend.anthropic"]] },
      { key: "roles.writer.backend_url", type: "text", group: "roles", advanced: true,
        showIf: (c) => !!c.roles?.writer?.backend },
      { key: "roles.writer.api_key", type: "password", group: "roles", advanced: true,
        showIf: (c) => ["openai_compat", "anthropic"].includes(c.roles?.writer?.backend) },
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
    if (tab === "tools") return renderTools();
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
        if (["model.multi_model", "profile", "roles.writer.backend",
             "roles.embeddings.backend"].includes(f.key)) renderTab();
      }).catch(() => renderTab());
    };
    let control;
    if (f.type === "bool") {
      control = toggle(!!value, save, null, { "aria-label": label });
    } else if (f.type === "tri") {
      // yes / no / leave the model's default (null)
      const opts = [["", "settings.modelDefault"], ["true", "common.yes"], ["false", "common.no"]];
      control = select(opts.map(([v, l]) => ({ value: v, label: t(l, l) })),
        value === true ? "true" : value === false ? "false" : "",
        (v) => save(v === "" ? null : v === "true"), { "aria-label": label });
    } else if ((f.type === "model" || f.type === "embedding") && f.textIf && f.textIf(App.state.config || {})) {
      // a model on another server: its name is typed, this computer cannot list it
      control = h("input", { type: "text", "aria-label": label, autocomplete: "off" });
      control.value = value ?? "";
      control.addEventListener("change", () => save(control.value.trim()));
    } else if (f.type === "select") {
      control = select(f.options.map(([v, l]) => ({ value: v, label: t(l, l) })), value, save,
        { "aria-label": label });
    } else if (f.type === "number") {
      control = h("input", { type: "number", min: f.min, max: f.max, step: f.step || 1,
        value: value ?? "", "aria-label": label });
      control.addEventListener("change", () => save(Number(control.value)));
    } else if (f.type === "model") {
      const chat = installed.filter((m) => m.kind !== "embedding").map((m) => ({ value: m.name,
        label: m.remote ? `${m.name} (${t("settings.cloudModel").replace("{host}", m.remote)})` : m.name }));
      if (value && !chat.some((o) => o.value === value)) chat.unshift({ value, label: `${value} (${t("settings.notInstalled")})` });
      if (f.allowEmpty) chat.unshift({ value: "", label: t("settings.sameModel") });
      control = select(chat.length ? chat : [{ value: "", label: t("chat.noModel") }], value, save,
        { "aria-label": label });
    } else if (f.type === "embedding") {
      // embedding models only; an empty value keeps model.embed_model
      const emb = installed.filter((m) => m.kind === "embedding").map((m) => ({ value: m.name,
        label: m.remote ? `${m.name} (${t("settings.cloudModel").replace("{host}", m.remote)})` : m.name }));
      if (value && !emb.some((o) => o.value === value)) emb.unshift({ value, label: `${value} (${t("settings.notInstalled")})` });
      if (f.allowEmpty) emb.unshift({ value: "", label: t("settings.sameEmbedder") });
      control = select(emb.length ? emb : [{ value: "", label: t("settings.sameEmbedder") }], value, save,
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
          return h("label.check", box, h("span", m.name), m.family ? chip(m.family) : null,
            m.remote ? chip(t("settings.cloudModel").replace("{host}", m.remote)) : null);
        }) : h("span.muted", t("chat.noModel")));
    } else if (f.type === "list") {
      control = h("textarea", { rows: 2, "aria-label": label });
      control.value = (value || []).join("\n");
      control.addEventListener("change", () =>
        save(control.value.split(/\n|,/).map((s) => s.trim()).filter(Boolean)));
    } else {
      const stored = f.type === "password" && (App.state.config?._secrets || {})[f.key];
      control = h("input", { type: f.type === "password" ? "password" : "text",
        placeholder: stored ? t(`settings.secretStored.${stored}`) : (f.placeholder || ""),
        "aria-label": label, autocomplete: "off" });
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

  // ---- tools: MCP servers and author search (3.4) -----------------------------------
  function toolField(label, control, help) {
    return h("div.field-row",
      h("div.field-text", h("span.field-label", label),
        help ? h("span.field-help", help) : null),
      h("div.field-control", control));
  }

  function lines(value) {
    return String(value || "").split(/\n/).map((s) => s.trim()).filter(Boolean);
  }

  function names(value) {
    return String(value || "").split(/\n|,/).map((s) => s.trim()).filter(Boolean);
  }

  async function renderTools() {
    clear(els.body);
    els.body.appendChild(h("p.muted", t("tools.loading")));
    let listing;
    let projects;
    let standing = [];
    try {
      projects = await Api.get("/api/projects");
      listing = await Api.get(`/api/mcp/servers?project=${encodeURIComponent(projects.active || "")}`);
      const data = await Api.get(`/api/tools/standing?project=${encodeURIComponent(projects.active || "")}`);
      standing = data.standing || [];
    } catch (e) {
      if (tab === "tools") clear(els.body).appendChild(h("p.error", e.message));
      return;
    }
    if (tab !== "tools") return;
    clear(els.body);
    const project = (projects.items || []).find((p) => p.id === projects.active);
    const projectName = project ? project.name : t("tools.personal");
    const projectId = listing.project_id || "";

    els.body.appendChild(h("section.subpanel",
      h("h3", t("tools.title")),
      h("p.muted", t("tools.lede").replace("{project}", projectName)),
      h("p.muted", t("tools.authorNote"))));

    // Author search: off by default; it sends one exact name per call.
    const authorOn = !!(App.state.config?.tools?.author?.enabled);
    const author = h("div.field-row",
      h("div.field-text", h("span.field-label", t("tools.author")),
        h("span.field-help", t("tools.authorBody"))),
      h("div.field-control", toggle(authorOn, async (on) => {
        try {
          await App.saveConfig({ "tools.author.enabled": on }, { quiet: true });
          UI.toast(t("tools.saved"), "ok");
          renderTools();
        } catch (_) { renderTools(); }
      }, null, { "aria-label": t("tools.author") })));
    els.body.appendChild(h("div.fields", author));

    // 3.4, D-011: the agent loop's hard budget. The server enforces the same
    // upper bounds; these fields only lower them.
    const agentCfg = App.state.config?.tools?.agent || {};
    const budgetInput = (key, label, min, max) => {
      const value = agentCfg[key] ?? { max_steps: 8, max_tool_calls: 8,
        max_observation_chars: 4000 }[key];
      const input = h("input", { type: "number", min: String(min), max: String(max),
        value: String(value), "aria-label": label });
      input.addEventListener("change", async () => {
        try {
          await App.saveConfig({ [`tools.agent.${key}`]: Number(input.value) }, { quiet: true });
          UI.toast(t("tools.saved"), "ok");
        } catch (_) { renderTools(); }
      });
      return toolField(label, input, t(`tools.agent.${key}Hint`));
    };
    els.body.appendChild(h("section.subpanel",
      h("h3", t("tools.agentTitle")),
      h("p.muted", t("tools.agentBody")),
      h("div.fields",
        budgetInput("max_steps", t("tools.agentMaxSteps"), 1, 8),
        budgetInput("max_tool_calls", t("tools.agentMaxToolCalls"), 1, 8),
        budgetInput("max_observation_chars", t("tools.agentMaxObservation"), 500, 8000))));

    // 3.4, D-011: "don't ask again in this project" is only for local MCP
    // tools. Revoking it here makes the next call ask again.
    const standingBox = h("div");
    if (!standing.length) {
      standingBox.appendChild(h("p.empty", t("tools.standingNone")));
    } else {
      standingBox.appendChild(h("ul.plain", standing.map((record) => h("li",
        h("code", record.spec_id), " ",
        h("span.muted", record.granted_at || ""), " ",
        button(t("tools.standingRevoke"), async () => {
          try {
            await Api.post("/api/tools/standing",
              { project_id: projectId, spec_id: record.spec_id, standing: false });
            UI.toast(t("tools.standingRevoked"), "ok");
            renderTools();
          } catch (e) { UI.toast(e.message, "error"); }
        }, "ghost small")))));
    }
    els.body.appendChild(h("section.subpanel",
      h("h3", t("tools.standingTitle")),
      h("p.muted", t("tools.standingBody")),
      standingBox));

    // Add form. Nothing here starts a process; Start is an explicit button.
    const id = h("input", { type: "text", autocomplete: "off", placeholder: "weather",
      "aria-label": t("tools.id") });
    const kind = select([
      { value: "local_stdio", label: t("tools.kind.local_stdio") },
      { value: "remote_http", label: t("tools.kind.remote_http") },
    ], "local_stdio", (value) => {
      localBox.hidden = value !== "local_stdio";
      remoteBox.hidden = value !== "remote_http";
    }, { "aria-label": t("tools.kind") });
    const command = h("input", { type: "text", autocomplete: "off",
      placeholder: "/usr/bin/python3", "aria-label": t("tools.command") });
    const args = h("textarea", { rows: 2, "aria-label": t("tools.args"),
      placeholder: "-m\nmy_server" });
    const cwd = h("input", { type: "text", autocomplete: "off",
      placeholder: App.state.health?.data_dir || "",
      "aria-label": t("tools.cwd") });
    const env = h("textarea", { rows: 2, "aria-label": t("tools.env"),
      placeholder: "HOME\nMCP_TOKEN" });
    const url = h("input", { type: "text", autocomplete: "off",
      placeholder: "https://example.test/mcp", "aria-label": t("tools.url") });
    const localBox = h("div",
      toolField(t("tools.command"), command, t("tools.commandHint")),
      toolField(t("tools.args"), args, t("tools.argsHint")),
      toolField(t("tools.cwd"), cwd, t("tools.cwdHint")),
      toolField(t("tools.env"), env, t("tools.envHint")));
    const remoteBox = h("div",
      toolField(t("tools.url"), url, t("tools.urlHint")));
    remoteBox.hidden = true;
    const add = button(t("tools.add"), async () => {
      const body = {
        project_id: projectId,
        id: id.value.trim(),
        kind: kind.value,
      };
      if (kind.value === "local_stdio") {
        body.command = command.value.trim();
        body.args = lines(args.value);
        body.cwd = cwd.value.trim();
        body.env_allowlist = names(env.value);
      } else {
        body.url = url.value.trim();
      }
      try {
        await Api.post("/api/mcp/servers", body);
        UI.toast(t("tools.added"), "ok");
        renderTools();
      } catch (e) { UI.toast(e.message, "error"); }
    }, "primary");
    els.body.appendChild(h("section.subpanel",
      h("h3", t("tools.addTitle")),
      h("p.muted", t("tools.addBody")),
      h("div.fields",
        toolField(t("tools.id"), id, t("tools.idHint")),
        toolField(t("tools.kind"), kind),
        localBox, remoteBox),
      h("div.form-actions", add)));

    if (!(listing.servers || []).length) {
      els.body.appendChild(h("p.empty", t("tools.none")));
      return;
    }
    for (const server of listing.servers) els.body.appendChild(toolCard(server, projectId));
  }

  function toolCard(server, projectId) {
    const box = h("section.subpanel.mcp-server");
    const running = !!server.running;
    box.appendChild(h("div.inline-form",
      h("h3", server.id),
      chip(t(`tools.kind.${server.kind}`, server.kind)),
      server.kind === "remote_http" ? chip(t("tools.thirdParty"), "warn") : null,
      chip(t(`tools.status.${server.status}`, server.status),
        server.status === "approved" ? "ok" : server.status === "suspended" ? "danger" : ""),
      chip(running ? t("tools.running") : t("tools.stopped"), running ? "ok" : "")));

    if (server.kind === "local_stdio") {
      box.appendChild(h("p.caveat", t("tools.localNotice")));
      box.appendChild(h("dl.facts",
        h("dt", t("tools.command")), h("dd", h("code.path", server.command_line || "—")),
        h("dt", t("tools.cwd")), h("dd", h("code.path", server.cwd || "—"))));
    } else {
      box.appendChild(h("p.caveat", t("tools.remoteNotice")));
      box.appendChild(h("p", h("span.muted", t("tools.host") + " "),
        h("code", server.host || "—")));
      const hosts = new Set(App.state.config?.privacy?.tool_hosts || []);
      const host = h("input", { type: "checkbox" });
      host.checked = !!server.host_authorised;
      host.addEventListener("change", async () => {
        if (host.checked) hosts.add(server.host); else hosts.delete(server.host);
        try {
          await App.saveConfig({ "privacy.tool_hosts": [...hosts] }, { quiet: true });
          UI.toast(t("tools.saved"), "ok");
        } catch (_) { /* config error toast shown by saveConfig */ }
        renderTools();
      });
      box.appendChild(h("label.check", host, h("span", t("tools.hostAuth"))));
      box.appendChild(h("div.field-row",
        h("div.field-text", h("span.field-label", t("tools.passagesAuth")),
          h("span.field-help", t("tools.passagesHelp"))),
        h("div.field-control", toggle(!!server.passages_authorised, async (on) => {
          try {
            await App.saveConfig({ "privacy.third_party_passages": on }, { quiet: true });
            UI.toast(t("tools.saved"), "ok");
            renderTools();
          } catch (_) { renderTools(); }
        }, null, { "aria-label": t("tools.passagesAuth") }))));
    }

    if (server.env_allowlist?.length) {
      box.appendChild(h("p", h("strong", t("tools.envTitle"))));
      box.appendChild(h("ul.plain", server.env_allowlist.map((name) => h("li",
        h("code", name), " ",
        chip(server.env?.[name] ? t("tools.envSet") : t("tools.envNotSet"),
          server.env?.[name] ? "ok" : "")))));
    } else {
      box.appendChild(h("p.muted", t("tools.envNone")));
    }

    if (server.status === "suspended") {
      box.appendChild(h("p.caveat", t("tools.suspended")
        .replace("{reason}", server.suspension_reason || "")));
      box.appendChild(h("p.muted", t("tools.reapproveHint")));
    }
    if (server.approved_tools?.length) {
      box.appendChild(h("p.muted", `${t("tools.approved")}: ${server.approved_tools.join(", ")}`));
    }

    const actions = h("div.inline-form");
    actions.appendChild(button(running ? t("tools.stop") : t("tools.start"), async () => {
      try {
        await Api.post(`/api/mcp/servers/${encodeURIComponent(server.id)}/${running ? "stop" : "start"}`,
          { project_id: projectId });
        toolProposals.delete(server.id);
        renderTools();
      } catch (e) { UI.toast(e.message, "error"); }
    }, running ? "ghost" : "primary"));
    if (running) {
      actions.appendChild(button(t("tools.propose"), async () => {
        try {
          const manifest = await Api.post(
            `/api/mcp/servers/${encodeURIComponent(server.id)}/propose`,
            { project_id: projectId });
          const live = new Set((manifest.tools || []).map((tool) => tool.name));
          const selected = new Set((server.approved_tools || []).filter((name) => live.has(name)));
          toolProposals.set(server.id, { manifest, selected });
          renderTools();
        } catch (e) { UI.toast(e.message, "error"); }
      }, "small"));
    }
    actions.appendChild(button(t("tools.remove"), () => removeServer(server, projectId), "ghost small"));
    box.appendChild(actions);

    const proposal = toolProposals.get(server.id);
    if (proposal) {
      box.appendChild(h("h4", t("tools.toolsTitle")));
      box.appendChild(h("p.caveat", t("tools.toolsHint")));
      if (!(proposal.manifest.tools || []).length) {
        box.appendChild(h("p.empty", t("tools.noTools")));
      } else {
        const checks = h("div.checks");
        for (const tool of proposal.manifest.tools) {
          const check = h("input", { type: "checkbox" });
          check.checked = proposal.selected.has(tool.name);
          check.addEventListener("change", () => {
            if (check.checked) proposal.selected.add(tool.name);
            else proposal.selected.delete(tool.name);
          });
          // h() appends a text node (textContent): a description is quoted
          // data, never HTML or a Markdown link.
          checks.appendChild(h("label.check", check,
            h("div", h("strong", tool.name),
              h("blockquote.tool-desc", tool.description))));
        }
        box.appendChild(checks);
        box.appendChild(button(t("tools.approve"), async () => {
          try {
            await Api.post(`/api/mcp/servers/${encodeURIComponent(server.id)}/approve`,
              { project_id: projectId, tools: [...proposal.selected].sort() });
            toolProposals.delete(server.id);
            UI.toast(t("tools.approvedOk"), "ok");
            renderTools();
          } catch (e) { UI.toast(e.message, "error"); }
        }, "primary", { disabled: !proposal.selected.size }));
      }
    }
    return box;
  }

  async function removeServer(server, projectId) {
    const ok = await UI.modal(t("tools.removeTitle"),
      h("p", t("tools.removeBody").replace("{id}", server.id)),
      [{ label: t("common.cancel"), value: false, kind: "ghost" },
       { label: t("tools.remove"), value: true, kind: "primary" }]);
    if (!ok) return;
    try {
      await Api.del(`/api/mcp/servers/${encodeURIComponent(server.id)}?project=${encodeURIComponent(projectId)}`);
      toolProposals.delete(server.id);
      UI.toast(t("tools.removed"), "ok");
      renderTools();
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
    els.body.appendChild(h("section.subpanel",
      h("h3", t("support.title")),
      h("p.muted", t("support.body")),
      h("p", h("a", { href: "https://buymeacoffee.com/swarmbly", target: "_blank",
        rel: "noopener noreferrer" }, t("support.link")))));
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
