/* Swarm view: real network state only. Announced ≠ verified: a node counts as
   authenticated after the channel-bound handshake; its capacity counts as
   verified only once it has completed a task. */
"use strict";

const Monitor = (() => {
  const { h, clear, t, readout, chip, button, toggle } = UI;
  let root;
  const els = {};
  let monitor = null;
  let refreshTimer = null;

  function init(el) {
    root = el;
    build();
    App.onEvent(onEvent);
  }

  function build() {
    clear(root);
    els.controls = h("div.view-actions");
    els.health = h("div.readouts.wide");
    els.graph = h("div.graph-box");
    els.peers = h("div.table-wrap");
    els.cache = h("div.table-wrap");
    els.contribution = h("div.readouts");
    UI.append(root,
      h("header.view-head", h("h1.view-title", t("monitor.title")), els.controls),
      h("p.view-lede", t("monitor.lede")),
      h("section.panel", h("h2", t("monitor.health")), els.health),
      h("section.panel.graph-panel", h("h2", t("monitor.graph")), els.graph),
      h("section.panel", h("h2", t("monitor.peers")), els.peers),
      h("section.panel", h("h2", t("monitor.discovery")), h("p.muted", t("monitor.discoveryNote")), els.cache),
      h("section.panel", h("h2", t("monitor.contribution")), h("p.muted", t("monitor.contributionNote")),
        els.contribution));
    SwarmGraph.mount(els.graph);
  }

  function show() { refresh(); }

  async function refresh() {
    try { monitor = await Api.get("/api/monitor"); } catch (_) { monitor = null; }
    render();
  }

  function onEvent(event) {
    if (event.type === "app.swarm") { scheduleRefresh(); return; }
    if (event.type === "swarm.attempt") {
      const p = event.payload || {};
      if (p.event === "dispatched") SwarmGraph.pulse(p.node, "out");
      if (p.event === "accepted") SwarmGraph.pulse(p.node, "in");
    }
  }

  function scheduleRefresh() {
    if (App.state.view !== "swarm") { render(); return; }
    clearTimeout(refreshTimer);
    refreshTimer = setTimeout(refresh, 300);
  }

  function render() {
    const sw = App.state.swarm || {};
    const cfg = App.state.config || {};
    renderControls(sw, cfg);
    renderHealth(sw);
    const selfModels = cfg.model?.multi_model ? (cfg.model.local_models || [])
      : [cfg.model?.model_name].filter(Boolean);
    SwarmGraph.draw({ self: { models: selfModels }, peers: sw.peers || [], discovered: sw.discovered || [] });
    renderPeers(sw.peers || []);
    renderCache(sw.discovered || []);
    renderContribution();
  }

  function renderControls(sw, cfg) {
    clear(els.controls);
    const refused = cfg.permissions?.lan_discovery === false;
    els.controls.appendChild(toggle(cfg.swarm?.lan_enabled && !refused, async (on) => {
      if (on && refused) {
        UI.toast(t("monitor.lanRefused"), "error");
        return render();
      }
      await App.saveConfig({ swarm: { lan_enabled: on } }, { quiet: true });
      await App.refreshSwarm();
    }, t("monitor.lan"), { disabled: refused }));
    els.controls.appendChild(toggle(cfg.swarm?.worker_enabled, async (on) => {
      try { await Api.post("/api/swarm/worker", { enabled: on }); } catch (e) { UI.toast(e.message, "error"); }
      await App.reloadConfig();
      await App.refreshSwarm();
    }, t("monitor.workerToggle")));
    if (cfg.swarm?.worker_enabled) {
      els.controls.appendChild(button(t(cfg.swarm.worker_paused ? "monitor.resume" : "monitor.pause"), async () => {
        await App.saveConfig({ swarm: { worker_paused: !cfg.swarm.worker_paused } }, { quiet: true });
        render();
      }, "ghost small"));
    }
    els.controls.appendChild(button(t("monitor.search"), async () => {
      try {
        const r = await Api.post("/api/swarm/rescan", {});
        UI.toast(r.discovery === "off" ? t("monitor.searchOff")
          : t("monitor.searchDone").replace("{n}", r.answered), r.discovery === "off" ? "error" : "ok");
      } catch (e) { UI.toast(e.message, "error"); }
      App.refreshSwarm();
    }, "small", { disabled: !sw.discovery?.enabled }));
    els.controls.appendChild(button(t("monitor.connect"), connectDialog, "ghost small"));
  }

  async function connectDialog() {
    const host = h("input", { type: "text", placeholder: "192.168.1.20", "aria-label": t("monitor.host") });
    const port = h("input", { type: "number", value: 9765, min: 1, max: 65535, "aria-label": t("monitor.port") });
    const ok = await UI.modal(t("monitor.connectTitle"),
      h("div.form", h("p.muted", t("monitor.connectBody")),
        h("label.field", h("span", t("monitor.host")), host),
        h("label.field", h("span", t("monitor.port")), port)),
      [{ label: t("common.cancel"), value: false, kind: "ghost" },
       { label: t("monitor.connect"), value: true, kind: "primary" }]);
    if (!ok || !host.value.trim()) return;
    try {
      await Api.post("/api/swarm/connect", { host: host.value.trim(), port: Number(port.value) });
      UI.toast(t("monitor.connecting"), "ok");
    } catch (e) { UI.toast(e.message, "error"); }
  }

  function renderHealth(sw) {
    clear(els.health);
    const peers = sw.peers || [];
    const connected = peers.filter((p) => p.connected);
    const workers = connected.filter((p) => p.worker);
    const busy = workers.filter((p) => p.tasks_inflight > 0);
    const families = new Set(workers.flatMap((p) => (p.models || []).map((m) => m.family)));
    const health = monitor?.health || {};
    const tasks = monitor?.tasks || {};
    UI.append(els.health,
      readout(t("monitor.discovered"), (sw.discovered || []).length, "measured"),
      readout(t("monitor.connected"), connected.length, "measured"),
      readout(t("monitor.authenticated"), sw.authenticated_count ?? 0, "measured"),
      readout(t("monitor.workersAvailable"), workers.length - busy.length, "measured"),
      readout(t("monitor.workersBusy"), busy.length, "measured"),
      readout(t("monitor.unreachable"), sw.unreachable_count ?? 0, "measured"),
      readout(t("monitor.families"), families.size ? [...families].join(", ") : 0, "measured"),
      readout(t("monitor.latency"), health.latency?.median_rtt_ms !== undefined
        ? `${health.latency.median_rtt_ms} ms` : null, health.latency?.median_rtt_ms !== undefined ? "measured" : "unknown"),
      readout(t("monitor.uptime"), monitor?.swarm ? UI.fmtMs(monitor.swarm.uptime_s * 1000) : null, "measured"),
      readout(t("monitor.distributedRequests"), tasks.distributed_requests ?? 0, "measured"),
      readout(t("monitor.dispatched"), tasks.dispatched ?? 0, "measured"),
      readout(t("monitor.dispatchFailed"), tasks.dispatch_failed ?? 0, "measured"),
      readout(t("monitor.listening"), sw.listening ? `TCP ${sw.port}` : (sw.listen_error || t("common.no")),
        "measured"));
    if (families.size) els.health.appendChild(h("p.caveat", t("monitor.diversityCaveat")));
  }

  // Node id plus what the node says about itself (older nodes say nothing).
  function peerTitle(p) {
    const r = p.resources || {};
    const parts = [p.node_id];
    if (r.os) parts.push(`${r.os}${r.machine ? " · " + r.machine : ""}`);
    if (r.app_version) parts.push(`Swarmbly ${r.app_version}${r.app_build ? " (" + r.app_build + ")" : ""}`);
    if (r.ram_mb) parts.push(`RAM ${Math.round(r.ram_mb / 1024)} GB` +
      (r.ram_available_mb ? ` (${Math.round(r.ram_available_mb / 1024)} GB free)` : ""));
    return parts.join("\n");
  }

  function renderPeers(peers) {
    clear(els.peers);
    if (!peers.length) {
      els.peers.appendChild(h("p.empty", t("monitor.noPeers")));
      return;
    }
    els.peers.appendChild(h("table.data",
      h("thead", h("tr", ["node", "address", "state", "role", "models", "rtt", "inflight", "seen"]
        .map((k) => h("th", { scope: "col" }, t(`monitor.col.${k}`))))),
      h("tbody", peers.map((p) => h("tr",
        h("td", h("code", { title: peerTitle(p) }, p.short_id || UI.shortId(p.node_id))),
        h("td", `${p.address}:${p.port}`),
        h("td", h(`span.status-word.${p.connected ? "completed" : "failed"}`,
          t(p.connected ? (p.authenticated ? "monitor.authenticatedShort" : "monitor.connectedShort")
            : "monitor.lost"))),
        h("td", t(p.worker ? "monitor.roleWorker" : "monitor.roleClient")),
        h("td", (p.models || []).map((m) => chip(m.version || m.family))),
        h("td", p.rtt_ms !== null && p.rtt_ms !== undefined ? `${Math.round(p.rtt_ms)} ms` : "—"),
        h("td", String(p.tasks_inflight || 0)),
        h("td", UI.fmtAgo(p.last_seen)))))));
  }

  function renderCache(entries) {
    clear(els.cache);
    if (!entries.length) {
      els.cache.appendChild(h("p.empty", t(App.state.swarm?.discovery?.enabled
        ? "monitor.cacheEmpty" : "monitor.discoveryOff")));
      return;
    }
    els.cache.appendChild(h("table.data",
      h("thead", h("tr", ["hint", "addresses", "source", "first", "verified", "expires", "auth"]
        .map((k) => h("th", { scope: "col" }, t(`monitor.cache.${k}`))))),
      h("tbody", entries.map((d) => h("tr",
        h("td", h("code", d.node_hint || "—")),
        h("td", (d.addresses || [d.address]).join(", ") + `:${d.port}`),
        h("td", d.source),
        h("td", UI.fmtAgo(d.discovered_at)),
        h("td", UI.fmtAgo(d.last_seen)),
        h("td", new Date(d.expires_at * 1000).toLocaleTimeString()),
        h("td", t(d.verified ? "common.yes" : "common.no")))))));
  }

  function renderContribution() {
    clear(els.contribution);
    const c = monitor?.contribution;
    if (!c) return;
    UI.append(els.contribution,
      readout(t("monitor.served"), c.tasks_served, "measured"),
      readout(t("monitor.servedTime"), UI.fmtMs(c.processing_time_ms), "measured"),
      readout(t("monitor.servedTokens"), c.tokens_generated, "measured"),
      readout(t("monitor.bytesIn"), UI.fmtBytes(c.bytes_transferred?.in), "measured"),
      readout(t("monitor.bytesOut"), UI.fmtBytes(c.bytes_transferred?.out), "measured"),
      readout(t("monitor.sharedModels"), (App.state.swarm?.worker?.shared_models || []).join(", "), "measured"),
      readout(t("monitor.availability"), null, "unknown"));
  }

  function relabel() { build(); render(); }

  return { init, show, relabel };
})();

App.register("swarm", Monitor);
