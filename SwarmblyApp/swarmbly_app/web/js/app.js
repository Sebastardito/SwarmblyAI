/* App shell: boot, navigation, shared state, event fan-out, node status card
   and the activity rail (the live strand of the current request). */
"use strict";

const App = (() => {
  const { h, clear, t } = UI;
  const state = { config: null, health: null, swarm: null, models: null, view: "chat" };
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
    for (const fn of handlers) { try { fn(event); } catch (e) { console.error(e); } }
    if (/^(node\.|swarm\.attempt|worker\.)/.test(event.type)) scheduleSwarmRefresh();
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
            reason: p.meta?.local_reason || (p.status === "failed" ? p.error : t("activity.localAnswer")),
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
           refreshSwarm, setActivity };
})();
