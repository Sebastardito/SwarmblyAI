/* App shell: boot, navigation, shared state, event fan-out, node status card
   and the activity rail (the live strand of the current request). */
"use strict";

const App = (() => {
  const { h, clear, t } = UI;
  const state = { config: null, health: null, swarm: null, models: null,
                  sandbox: null, view: "chat" };
  const handlers = [];
  const views = {};
  const live = { requestId: null, stages: {}, mode: "" };
  let swarmTimer = null;

  function onEvent(fn) { handlers.push(fn); }
  function register(name, view) { views[name] = view; }

  async function boot() {
    try {
      state.config = await Api.get("/api/config");
      state.health = await Api.get("/api/health");
    } catch (err) {
      document.body.appendChild(h("p.boot-error", String(err)));
      return;
    }
    if (state.health?.test_mode?.active) {
      const banner = UI.$("#test-mode-banner");
      if (banner) banner.hidden = false;
    }
    await I18n.load(state.config.language || "en");
    applyTheme();
    UI.append(clear(UI.$("#brand")), UI.mark(30), h("span.brand-name", "Swarmbly"));
    document.querySelectorAll(".nav-btn").forEach((b) =>
      b.addEventListener("click", () => navigate(b.dataset.view)));
    UI.$("#activity-close").addEventListener("click", () => setActivity(false));
    UI.$("#activity-open").addEventListener("click", () => setActivity(true));
    for (const [name, view] of Object.entries(views)) {
      try { view.init(UI.$(`#view-${name}`)); } catch (e) { console.error(name, e); }
    }
    Api.subscribe(dispatch);
    await refreshSandbox();
    navigate(location.hash.replace("#", "") || "chat");
    // Back/forward and typed #links switch views too.
    window.addEventListener("hashchange", () => {
      const name = location.hash.replace("#", "");
      if (name && name !== state.view) navigate(name);
    });
    await refreshSwarm();
    renderActivity();
    if (!state.config.setup_completed) Wizard.show();
  }

  function dispatch(event) {
    handleLive(event);
    if (event.type === "sandbox.prepare") {
      const state = event.payload?.status;
      if (state === "ready") UI.toast(t("sandbox.readyToast"), "ok");
      else if (state === "failed") UI.toast(t("sandbox.failedToast"), "error");
      refreshSandbox();
    }
    for (const fn of handlers) { try { fn(event); } catch (e) { console.error(e); } }
    if (/^(node\.|swarm\.attempt|worker\.)/.test(event.type)) scheduleSwarmRefresh();
  }

  async function refreshSandbox() {
    try { state.sandbox = await Api.get("/api/sandbox"); } catch (_) { return; }
    renderSandboxNotice();
    for (const fn of handlers) { try { fn({ type: "app.sandbox", payload: state.sandbox }); } catch (_) {} }
  }

  function renderSandboxNotice() {
    const slot = UI.$("#sandbox-notice");
    if (!slot) return;
    clear(slot);
    const s = state.sandbox;
    if (!s || (!s.notice && s.status !== "preparing")) {
      slot.hidden = true;
      return;
    }
    slot.hidden = false;
    slot.appendChild(SandboxNotice.view(s, refreshSandbox, { compact: true }));
  }

  function scheduleSwarmRefresh() {
    clearTimeout(swarmTimer);
    swarmTimer = setTimeout(refreshSwarm, 400);
  }

  async function refreshSwarm() {
    try { state.swarm = await Api.get("/api/swarm"); } catch (_) { return; }
    renderNodeCard();
    for (const fn of handlers) { try { fn({ type: "app.swarm", payload: state.swarm }); } catch (_) {} }
  }

  function navigate(name) {
    if (!views[name]) name = "chat";
    state.view = name;
    history.replaceState(null, "", `#${name}`);
    document.querySelectorAll(".nav-btn").forEach((b) => {
      const on = b.dataset.view === name;
      b.classList.toggle("active", on);
      b.setAttribute("aria-current", on ? "page" : "false");
    });
    document.querySelectorAll(".view").forEach((v) =>
      v.classList.toggle("active", v.id === `view-${name}`));
    views[name]?.show?.();
  }

  // ---- node card (sidebar) --------------------------------------------------
  function renderNodeCard() {
    const card = clear(UI.$("#node-card"));
    const cfg = state.config || {};
    const sw = state.swarm || {};
    const peers = sw.peers || [];
    const workers = peers.filter((p) => p.connected && p.worker).length;
    const mode = cfg.swarm?.mode || "local";
    const lanOn = !!sw.discovery?.enabled;
    card.appendChild(h("div.node-id", { title: state.health?.node_id },
      h("span.node-id-k", t("node.id")), h("code", state.health?.node_id || "—")));
    card.appendChild(h("dl.node-facts",
      h("dt", t("node.mode")), h("dd", t(`mode.${mode}`)),
      h("dt", t("node.privacy")), h("dd", cfg.privacy?.tier || "LOCAL"),
      h("dt", t("node.lan")), h("dd", { class: lanOn ? "on" : "off" },
        t(lanOn ? "common.on" : "common.off")),
      h("dt", t("node.peers")), h("dd", t("node.peersValue").replace("{c}", sw.connected_count || 0).replace("{w}", workers)),
      h("dt", t("node.worker")), h("dd", { class: cfg.swarm?.worker_enabled ? "on" : "off" },
        t(cfg.swarm?.worker_enabled ? (cfg.swarm?.worker_paused ? "node.paused" : "common.on")
          : "common.off"))));
  }

  // ---- activity rail ----------------------------------------------------------
  function handleLive(event) {
    const p = event.payload || {};
    if (event.type === "request.started") {
      live.requestId = p.request_id;
      live.mode = p.mode;
      live.stages = { "REQUEST RECEIVED": { stage: "REQUEST RECEIVED", status: "completed" } };
      live.started = Date.now();
      renderActivity();
    } else if (event.type === "request.stage" && p.request_id === live.requestId) {
      live.stages[p.stage] = { ...(live.stages[p.stage] || {}), ...p };
      renderActivity();
    } else if (event.type === "chat.done" && p.request_id === live.requestId) {
      if (p.meta?.executed === "local" || !p.meta?.swarm) {
        const fin = live.stages["FINAL RESPONSE"];
        if (!fin || fin.status === "pending" || fin.status === "skipped") {
          live.stages["FINAL RESPONSE"] = { stage: "FINAL RESPONSE",
            status: p.status === "failed" ? "failed" : "completed",
            reason: p.meta?.local_reason ? I18n.reason(p.meta.local_reason) : (p.status === "failed" ? p.error : t("activity.localAnswer")),
            total_ms: p.meta?.total_ms };
        }
      }
      live.done = p.status;
      renderActivity();
    }
  }

  function renderActivity() {
    const box = clear(UI.$("#activity-helix"));
    const sub = UI.$("#activity-sub");
    if (!live.requestId) {
      sub.textContent = t("activity.empty");
      return;
    }
    sub.textContent = `${t(`mode.${live.mode}`, live.mode)} (${live.requestId.slice(0, 8)})`;
    box.appendChild(Helix.render(Object.values(live.stages)));
  }

  function setActivity(open) {
    UI.$("#shell").classList.toggle("activity-hidden", !open);
    document.body.classList.toggle("activity-open", open);
  }

  // ---- config ---------------------------------------------------------------------
  async function saveConfig(changes, { quiet = false } = {}) {
    try {
      state.config = await Api.put("/api/config", changes);
      applyTheme();
      renderNodeCard();
      if (!quiet) UI.toast(t("settings.saved"), "ok");
      scheduleSwarmRefresh();
      return state.config;
    } catch (err) {
      UI.toast(err.message, "error");
      throw err;
    }
  }

  async function reloadConfig() {
    state.config = await Api.get("/api/config");
    applyTheme();
    renderNodeCard();
    return state.config;
  }

  function applyTheme() {
    const cfg = state.config || {};
    document.body.classList.toggle("light", cfg.theme === "light");
    document.body.classList.toggle("reduce-motion", !!cfg.reduce_motion);
  }

  async function setLanguage(lang) {
    await saveConfig({ language: lang }, { quiet: true });
    await I18n.load(lang);
    for (const view of Object.values(views)) { try { view.relabel?.(); } catch (_) {} }
    renderNodeCard();
    renderActivity();
  }

  document.addEventListener("DOMContentLoaded", boot);

  return { state, onEvent, register, navigate, saveConfig, reloadConfig, setLanguage,
           refreshSwarm, refreshSandbox, setActivity };
})();

/* First-launch sandbox notice (R-005). Shared by the banner, the setup
   assistant and Settings: one status line, the expected time/memory and the
   Prepare now / Later actions. It never starts the compile without a click. */
const SandboxNotice = (() => {
  const { h, t, button, readout } = UI;

  function statusLine(s) {
    const state = s?.status || "missing";
    if (state === "preparing") {
      return t("sandbox.preparing").replace("{stage}", s.stage || "compiling");
    }
    if (state === "ready") {
      const m = s.measurement || {};
      const line = t("sandbox.ready")
        .replace("{time}", m.elapsed_s ?? "—")
        .replace("{peak}", m.peak_rss_mib ?? "—");
      return s.forced ? line + t("sandbox.forcedNote") : line;
    }
    if (state === "failed") {
      return t("sandbox.failed").replace("{reason}", s.last_error || t("sandbox.state.failed"));
    }
    if (state === "refused") {
      return t("sandbox.refused").replace("{reason}", s.last_error || t("sandbox.state.refused"));
    }
    if (state === "not_installed") return t("sandbox.notInstalled");
    return t("sandbox.noticeBody")
      .replace("{time}", s.expected_seconds ?? "—")
      .replace("{memory}", s.expected_memory_gb ?? "—");
  }

  async function prepare(onChange, force = false) {
    try {
      await Api.post("/api/sandbox/prepare", { consent: true, force: !!force });
      UI.toast(force ? t("sandbox.forcingToast") : t("sandbox.preparingToast"),
        force ? "" : "ok");
    } catch (err) {
      UI.toast(err.message, "error");
    }
    try { await onChange?.(); } catch (_) { /* the event will refresh it */ }
  }

  async function later(onChange) {
    try { await Api.post("/api/sandbox/defer", {}); }
    catch (err) { UI.toast(err.message, "error"); }
    try { await onChange?.(); } catch (_) { /* ignore */ }
  }

  function view(s, onChange, { compact = false } = {}) {
    const box = h("div.sandbox-panel");
    box.appendChild(h("div.sandbox-head",
      h("strong", t("sandbox.noticeTitle")),
      h("span.chip", t(`sandbox.state.${s.status}`, s.status))));
    box.appendChild(h("p.sandbox-line", statusLine(s)));
    if (s.installed && ["missing", "stale", "failed", "refused"].includes(s.status)) {
      box.appendChild(h("p.muted", t("sandbox.expected")
        .replace("{time}", s.expected_seconds ?? "—")
        .replace("{memory}", s.expected_memory_gb ?? "—")
        .replace("{free}", s.free_memory_gb ?? "—")
        .replace("{min}", s.minimum_free_memory_gb ?? "—")));
    }
    if (s.installed && s.enough_memory === false) {
      box.appendChild(h("p.error", t("sandbox.free").replace("{free}", s.free_memory_gb ?? "—")
        .replace("{min}", s.minimum_free_memory_gb ?? "—")));
      if (s.status !== "ready" && s.status !== "preparing") {
        box.appendChild(h("p.sandbox-warning", t("sandbox.forceWarning")));
      }
    }
    if (!compact && s.status === "ready") {
      const m = s.measurement || {};
      box.appendChild(h("div.readouts",
        readout(t("sandbox.compile"), m.elapsed_s == null ? null : `${m.elapsed_s} s`, "measured"),
        readout(t("sandbox.peak"), m.peak_rss_mib == null ? null : `${m.peak_rss_mib} MiB`, "measured"),
        readout(t("sandbox.expected"), `${s.expected_seconds} s · ${s.expected_memory_gb} GB`, "estimated")));
    }
    const actions = h("div.sandbox-actions");
    if (s.installed && s.status !== "ready" && s.status !== "preparing") {
      // The plain action always keeps the floor; below it the API refuses and
      // the explicit second button is the informed override.
      actions.appendChild(button(s.status === "failed" ? t("sandbox.retry") : t("sandbox.prepareNow"),
        () => prepare(onChange, false), "primary small"));
    }
    if (s.can_force && s.status !== "preparing") {
      actions.appendChild(button(t("sandbox.prepareAnyway"),
        () => prepare(onChange, true), "danger small"));
    }
    if (s.installed && s.status !== "ready" && s.status !== "preparing") {
      actions.appendChild(button(t("sandbox.later"), () => later(onChange), "ghost small"));
    }
    if (actions.childNodes.length) box.appendChild(actions);
    return box;
  }

  return { view, statusLine };
})();
