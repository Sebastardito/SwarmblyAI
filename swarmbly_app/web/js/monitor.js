/* Swarm view: real network state only. Announced ≠ verified: a node counts as
   authenticated after the channel-bound handshake; its capacity counts as
   verified only once it has completed a task. */
"use strict";

const Monitor = (() => {
  const { h, clear, t, readout, chip, button, toggle } = UI;
  let root;
  const els = {};
  let monitor = null;
  let circles = null;
  let creditsData = null;
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
    els.roles = h("div.readouts");
    els.graph = h("div.graph-box");
    els.peers = h("div.table-wrap");
    els.cache = h("div.table-wrap");
    els.contribution = h("div.readouts");
    els.circles = h("div");
    els.credits = h("div");
    UI.append(root,
      h("header.view-head", h("h1.view-title", t("monitor.title")), els.controls),
      h("p.view-lede", t("monitor.lede")),
      h("section.panel", h("h2", t("monitor.health")), els.health),
      h("section.panel", h("h2", t("monitor.nodeRoles")),
        h("p.muted", t("monitor.nodeRolesNote")), els.roles),
      h("section.panel.graph-panel", h("h2", t("monitor.graph")), els.graph),
      h("section.panel", h("h2", t("monitor.peers")), els.peers),
      h("section.panel", h("h2", t("circle.title")), h("p.muted", t("circle.lede")),
        els.circles),
      h("section.panel", h("h2", t("credits.title")), h("p.muted", t("credits.lede")),
        els.credits),
      h("section.panel", h("h2", t("monitor.discovery")), h("p.muted", t("monitor.discoveryNote")), els.cache),
      h("section.panel", h("h2", t("monitor.contribution")), h("p.muted", t("monitor.contributionNote")),
        els.contribution));
    SwarmGraph.mount(els.graph);
  }

  function show() { refresh(); }

  async function refresh() {
    try { monitor = await Api.get("/api/monitor"); } catch (_) { monitor = null; }
    try { circles = await Api.get("/api/circles"); } catch (_) { circles = null; }
    try { creditsData = await Api.get("/api/credits"); } catch (_) { creditsData = null; }
    render();
  }

  function onEvent(event) {
    if (event.type === "app.swarm" || event.type.startsWith("circle.")
        || event.type.startsWith("credit.")) {
      scheduleRefresh();
      return;
    }
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
    renderRoles(sw, cfg);
    const selfModels = cfg.model?.multi_model ? (cfg.model.local_models || [])
      : [cfg.model?.model_name].filter(Boolean);
    SwarmGraph.draw({ self: { models: selfModels }, peers: sw.peers || [], discovered: sw.discovered || [] });
    renderPeers(sw.peers || []);
    renderCache(sw.discovered || []);
    renderContribution();
    renderCircles();
    renderCredits();
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

  function roleLabel(role) {
    if (!role || typeof role !== "object") return "";
    if (role.role === "large_model") {
      return `large_model · ${role.model || "?"}${role.params_b ? ` (${role.params_b}B)` : ""}`;
    }
    if (role.role === "reasoner") return `reasoner · ${role.model || "?"} (think)`;
    if (role.role === "search") return `search · ${(role.engines || []).join(", ") || "?"}`;
    if (role.role === "corpus") return `corpus · ${role.name || "?"} (${role.size || "?"})`;
    return String(role.role || "");
  }

  function roleChips(roles) {
    const list = (roles || []).map(roleLabel).filter(Boolean);
    return list.length ? list.map((label) => chip(label)) : h("span.muted", t("monitor.noRoles"));
  }

  function renderRoles(sw, cfg) {
    clear(els.roles);
    const own = sw.roles || [];
    const settings = sw.node_roles || {};
    const marked = settings.reasoner_models || [];
    UI.append(els.roles,
      readout(t("monitor.ownRoles"),
        own.length ? own.map(roleLabel).join(" · ") : t("monitor.noRoles"), "measured"),
      readout(t("monitor.largeModelMin"),
        `${settings.large_model_min_b ?? "—"} B`, "measured"),
      readout(t("monitor.reasonerModels"),
        marked.length ? marked.join(", ") : t("monitor.noneMarked"), "measured"));
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
      h("thead", h("tr", ["node", "address", "link", "state", "role", "roles", "models", "rtt", "inflight", "seen"]
        .map((k) => h("th", { scope: "col" }, t(`monitor.col.${k}`))))),
      h("tbody", peers.map((p) => h("tr",
        h("td", h("code", { title: peerTitle(p) }, p.short_id || UI.shortId(p.node_id))),
        h("td", `${p.address}:${p.port}`),
        h("td", p.transport === "relayed"
          ? chip(t("monitor.relayed"), "", p.relay?.host || "")
          : t("monitor.direct")),
        h("td", h(`span.status-word.${p.connected ? "completed" : "failed"}`,
          t(p.connected ? (p.admitted === false ? "monitor.bootstrap"
            : p.authenticated ? "monitor.authenticatedShort" : "monitor.connectedShort")
            : "monitor.lost"))),
        h("td", t(p.worker ? "monitor.roleWorker" : "monitor.roleClient")),
        h("td", h("div.chips", roleChips(p.roles))),
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

  // ---- trusted circles (3.5, D-015) -----------------------------------------
  function renderCircles() {
    clear(els.circles);
    const data = circles || {};
    els.circles.appendChild(h("div.form-actions",
      button(t("circle.create"), createCircleDialog, "small"),
      button(t("circle.accept"), acceptInvitationDialog, "ghost small")));
    if (data.own_devices_notice) {
      els.circles.appendChild(h("div.warnings", { role: "status" },
        h("strong", t("circle.noticeTitle")),
        h("p", t("circle.noticeBody")),
        h("div.form-actions",
          button(t("circle.noticeSwitch"), switchToCircles, "primary small"),
          button(t("circle.noticeKeep"), acknowledgeNotice, "ghost small"))));
    }
    if (data.admission_mode === "own_devices") {
      const ownBox = h("input", { type: "checkbox" });
      ownBox.checked = !!data.own_devices_passages;
      ownBox.addEventListener("change", () => setOwnDevicesPassages(ownBox.checked));
      els.circles.appendChild(h("div.passages-setting",
        h("label.check", ownBox, h("span", t("circle.ownPassages"))),
        h("p.muted", t("circle.ownPassagesHelp"))));
    }
    const items = data.circles || [];
    if (!items.length) {
      els.circles.appendChild(h("p.empty", t("circle.none")));
    }
    for (const circle of items) els.circles.appendChild(circleCard(circle, data));
    const outgoing = data.outgoing_joins || [];
    if (outgoing.length) {
      els.circles.appendChild(h("h4", t("circle.outgoing")));
      els.circles.appendChild(h("table.data",
        h("thead", h("tr", ["circle", "status"].map((k) =>
          h("th", { scope: "col" }, t(`circle.col.${k}`))))),
        h("tbody", outgoing.map((item) => h("tr",
          h("td", h("code", { title: item.circle_id }, UI.shortId(item.circle_id))),
          h("td", item.status))))));
    }
  }

  function circleCard(circle, data) {
    const members = circle.members || [];
    const rows = members.map((member) => h("tr",
      h("td", member.name,
        member.node_id === data.node_id ? h("span.chip", t("circle.you")) : null),
      h("td", h("code", { title: member.node_id }, UI.shortId(member.node_id))),
      h("td", (member.endpoints || []).join(", ") || "—"),
      h("td", member.node_id === circle.owner ? t("circle.owner") : t("circle.member")),
      h("td", circle.is_owner && member.node_id !== circle.owner
          && member.node_id !== data.node_id
        ? button(t("circle.revoke"), () => revokeMember(circle, member), "danger small")
        : null)));
    const card = h("div.circle-item",
      h("div.circle-head",
        h("h3", circle.name),
        chip(t("circle.version").replace("{v}", circle.version)),
        circle.is_owner ? chip(t("circle.owner")) : null),
      relaySummary(circle),
      h("p.muted", t("circle.expires").replace("{when}",
        new Date(circle.expires_at * 1000).toLocaleDateString())),
      h("h4", t("circle.members")),
      h("table.data",
        h("thead", h("tr", ["name", "node", "endpoints", "role", ""]
          .map((k) => h("th", { scope: "col" }, k ? t(`circle.col.${k}`) : "")))),
        h("tbody", rows)));
    const passagesBox = h("input", { type: "checkbox" });
    passagesBox.checked = !!circle.circle_passages;
    passagesBox.addEventListener("change", () =>
      setCirclePassages(circle, passagesBox.checked));
    card.appendChild(h("div.passages-setting",
      h("label.check", passagesBox, h("span", t("circle.passages"))),
      h("p.muted", t("circle.passagesHelp"))));
    // 3.5, D-018 WP4b: the corpus executor shares ONE local project, and each
    // circle decides whether it may retrieve from it. Only the display name
    // and a size bucket are advertised; every admitted peer sees them.
    const corpus = App.state.swarm?.node_roles?.corpus || {};
    const corpusIds = corpus.circle_ids || [];
    const corpusBox = h("input", { type: "checkbox",
      disabled: !corpus.project_id });
    corpusBox.checked = corpus.project_id && corpusIds.includes(circle.circle_id);
    corpusBox.addEventListener("change", async () => {
      const next = corpusBox.checked
        ? [...new Set([...corpusIds, circle.circle_id])]
        : corpusIds.filter((id) => id !== circle.circle_id);
      await App.saveConfig({ node_roles: { corpus: { circle_ids: next } } },
        { quiet: true });
      await App.refreshSwarm();
    });
    card.appendChild(h("div.passages-setting",
      h("label.check", corpusBox, h("span", t("circle.corpusShare"))),
      h("p.muted", t(corpus.project_id
        ? "circle.corpusShareHelp" : "circle.corpusPickFirst"))));
    if (circle.is_owner) {
      const requests = circle.pending_joins || [];
      card.appendChild(h("h4", t("circle.requests")));
      card.appendChild(requests.length
        ? h("table.data",
          h("thead", h("tr", ["name", "node", "endpoints", ""]
            .map((k) => h("th", { scope: "col" }, k ? t(`circle.col.${k}`) : "")))),
          h("tbody", requests.map((request) => h("tr",
            h("td", request.name),
            h("td", h("code", { title: request.node_id },
              UI.shortId(request.node_id))),
            h("td", (request.endpoints || []).join(", ") || "—"),
            h("td", h("div.form-actions",
              button(t("circle.approve"), () => approveJoin(circle, request),
                "primary small"),
              button(t("circle.reject"), () => rejectJoin(circle, request),
                "ghost small")))))))
        : h("p.empty", t("circle.noRequests")));
    }
    if (circle.is_owner) {
      card.appendChild(h("div.form-actions",
        button(circle.relay ? t("circle.relayChange") : t("circle.relaySet"),
          () => relayDialog(circle), "ghost small"),
        circle.relay
          ? button(t("circle.relayRemove"), () => removeRelay(circle), "ghost small")
          : null,
        button(t("circle.renew"), () => renewCircle(circle), "ghost small")));
    }
    card.appendChild(h("div.form-actions",
      circle.is_owner
        ? button(t("circle.invite"), () => inviteDialog(circle), "small")
        : null,
      button(circle.is_owner ? t("circle.delete") : t("circle.leave"),
        () => leaveCircle(circle), "danger small")));
    return card;
  }

  // ---- reciprocity credits (3.5, D-020) ------------------------------------
  // Local wallet only: no transfer, no export, no market. A receipt belongs
  // to the worker it names, in that circle, and expires. The issuer also
  // shows receipts reported spent twice (detection, not prevention).
  function renderCredits() {
    clear(els.credits);
    const data = creditsData || {};
    const items = data.circles || [];
    UI.append(els.credits,
      readout(t("credits.issued"), data.issued_count ?? 0, "measured"),
      readout(t("credits.unit"), t("credits.unitReceipts"), "measured"),
      readout(t("credits.ttl"), `${data.ttl_days ?? 90} d`, "measured"));
    if (!items.length) {
      els.credits.appendChild(h("p.empty", t("credits.empty")));
    } else {
      els.credits.appendChild(h("table.data",
        h("thead", h("tr", ["name", "balance", "earned", "spent", "expiring"]
          .map((k) => h("th", { scope: "col" }, t(`credits.col.${k}`))))),
        h("tbody", items.map((item) => h("tr",
          h("td", item.name || UI.shortId(item.circle_id)),
          h("td", String(item.balance ?? 0)),
          h("td", String(item.earned ?? 0)),
          h("td", String(item.spent ?? 0)),
          h("td", String(item.expiring_soon ?? 0),
            h("span.muted", ` · ${t("credits.withinDays").replace("{days}",
              data.expiring_soon_days ?? 7)}`)))))));
    }
    els.credits.appendChild(h("h4", t("credits.flagged")));
    els.credits.appendChild(h("p.muted", t("credits.flaggedHelp")));
    const flagged = data.flagged || [];
    els.credits.appendChild(flagged.length
      ? h("table.data",
        h("thead", h("tr", ["receipt", "circle", "worker", "reports", "reason"]
          .map((k) => h("th", { scope: "col" }, t(`credits.col.${k}`))))),
        h("tbody", flagged.map((item) => h("tr",
          h("td", h("code", { title: item.receipt_id },
            UI.shortId(item.receipt_id))),
          h("td", h("code", { title: item.circle_id },
            UI.shortId(item.circle_id))),
          h("td", h("code", { title: item.worker }, item.worker_short)),
          h("td", String(item.reports ?? 0)),
          h("td", item.reason || "—"))))))
      : h("p.empty", t("credits.noFlagged")));
  }

  function relaySummary(circle) {
    const relay = circle.relay;
    const status = circle.relay_status || {};
    if (!relay) {
      return h("p.muted", t(circle.is_owner ? "circle.relayNoneOwner"
        : "circle.relayNone"));
    }
    const target = `${relay.host}:${relay.port}`;
    const state = status.security_warning
      ? t("circle.relaySecurity")
      : status.status === "connected" ? t("circle.relayConnected")
      : status.status === "down" ? t("circle.relayDown")
      : status.status === "refused" ? t("circle.relayRefused")
      : status.status === "limited" ? t("circle.relayLimited")
      : t("circle.relayOff");
    const extra = status.last_error
      ? h("span.muted", ` — ${status.last_error}`) : null;
    const push = (status.push || {}).current;
    let pushText = t("circle.relayPushNone");
    let pushHint = "";
    if (push) {
      const acked = Number(push.acknowledged_version || 0);
      const pending = Number(push.pending_version || 0);
      pushText = acked
        ? t("circle.relayPushAck").replace("{v}", String(acked))
        : t("circle.relayPushNone");
      if (pending > acked) {
        pushText += ` · ${t("circle.relayPushPending").replace("{v}",
          String(pending))}`;
      }
      if (push.last_refusal) {
        pushText += ` · ${t("circle.relayPushRefused").replace("{code}",
          push.last_refusal)}`;
        pushHint = pushRefusalHint(push.last_refusal);
      } else if (push.status === "unreachable") {
        pushText += ` · ${t("circle.relayPushUnreachable")}`;
      }
    }
    return h("div.relay-summary",
      h("p.muted", { class: status.security_warning ? "warn" : "" },
        `${t("circle.relay")}: ${target} · ${state}`, extra,
        h("br"), h("span.muted", t("circle.relayPin").replace("{pin}",
          `${String(relay.tls_cert_sha256 || "").slice(0, 16)}…`))),
      h("p.muted", t("circle.relayPush") + ": " + pushText,
        pushHint ? h("span.muted", ` — ${pushHint}`) : null),
      h("p.muted.small", t("circle.relayPushSource")));
  }

  async function relayDialog(circle) {
    const relay = circle.relay || {};
    const host = h("input", { type: "text", value: relay.host || "",
      placeholder: "relay.example.org" });
    const port = h("input", { type: "number", min: "1", max: "65535",
      value: String(relay.port || 8765) });
    const pin = h("input", { type: "text", value: relay.tls_cert_sha256 || "",
      placeholder: "64 hex characters", spellcheck: "false" });
    const ok = await UI.modal(t(circle.relay ? "circle.relayChangeTitle"
      : "circle.relaySetTitle"),
      h("div.form",
        h("label.field", h("span", t("circle.relayHost")), host),
        h("label.field", h("span", t("circle.relayPort")), port),
        h("label.field", h("span", t("circle.relayPinLabel")), pin),
        h("p.muted", t("circle.relayHelp"))),
      [{ label: t("common.cancel"), value: false, kind: "ghost" },
       { label: t("common.save"), value: true, kind: "primary" }]);
    if (!ok) return;
    if (!host.value.trim() || !pin.value.trim()) {
      UI.toast(t("circle.relayPinRequired"), "error");
      return;
    }
    try {
      await Api.post(`/api/circles/${encodeURIComponent(circle.circle_id)}/relay`,
        { host: host.value.trim(), port: Number(port.value),
          tls_cert_sha256: pin.value.trim() });
      await refresh();
    } catch (e) { UI.toast(e.message, "error"); }
  }

  function pushRefusalHint(code) {
    if (code === "unknown_circle") return t("circle.relayPushUnknownCircle");
    if (code === "rate_limited") return t("circle.relayPushRateLimited");
    if (code === "stale_version") return t("circle.relayPushStale");
    if (code === "not_owner") return t("circle.relayPushNotOwner");
    return t("circle.relayPushOther");
  }

  async function renewCircle(circle) {
    try {
      await Api.post(`/api/circles/${encodeURIComponent(circle.circle_id)}/renew`, {});
      await refresh();
    } catch (e) { UI.toast(e.message, "error"); }
  }

  async function removeRelay(circle) {
    try {
      await Api.post(`/api/circles/${encodeURIComponent(circle.circle_id)}/relay`,
        { relay: null });
      await refresh();
    } catch (e) { UI.toast(e.message, "error"); }
  }

  async function setCirclePassages(circle, enabled) {
    try {
      await Api.post(`/api/circles/${encodeURIComponent(circle.circle_id)}/passages`,
        { enabled });
      await refresh();
    } catch (e) { UI.toast(e.message, "error"); await refresh(); }
  }

  async function setOwnDevicesPassages(enabled) {
    try {
      await Api.post("/api/circles/own-devices/passages", { enabled });
      await refresh();
    } catch (e) { UI.toast(e.message, "error"); await refresh(); }
  }

  async function createCircleDialog() {
    const name = h("input", { type: "text", maxlength: 64 });
    const ok = await UI.modal(t("circle.createTitle"),
      h("div.form",
        h("label.field", h("span", t("circle.name")), name)),
      [{ label: t("common.cancel"), value: false, kind: "ghost" },
       { label: t("circle.create"), value: true, kind: "primary" }]);
    if (!ok) return;
    if (!name.value.trim()) { UI.toast(t("circle.name"), "error"); return; }
    try {
      await Api.post("/api/circles", { name: name.value.trim() });
      UI.toast(t("settings.saved"), "ok");
      await refresh();
    } catch (e) { UI.toast(e.message, "error"); }
  }

  async function acceptInvitationDialog() {
    const code = h("textarea", { rows: 6, placeholder: t("circle.codePlaceholder") });
    const name = h("input", { type: "text", maxlength: 64 });
    const ok = await UI.modal(t("circle.acceptTitle"),
      h("div.form",
        h("p.muted", t("circle.codeHelp")),
        h("label.field", h("span", t("circle.code")), code),
        h("label.field", h("span", t("circle.name")), name)),
      [{ label: t("common.cancel"), value: false, kind: "ghost" },
       { label: t("circle.accept"), value: true, kind: "primary" }]);
    if (!ok || !code.value.trim()) return;
    try {
      const result = await Api.post("/api/circles/accept", {
        code: code.value.trim(), name: name.value.trim() || undefined,
      });
      UI.toast(result.status === "already_member" ? t("circle.member")
        : result.status === "sent" ? t("circle.accepted") : t("circle.pending"), "ok");
      await refresh();
    } catch (e) { UI.toast(e.message, "error"); }
  }

  async function inviteDialog(circle) {
    try {
      const result = await Api.post(
        `/api/circles/${encodeURIComponent(circle.circle_id)}/invite`, {});
      const code = h("textarea", { rows: 6, readonly: true });
      code.value = result.code;
      const copy = button(t("circle.copy"), async () => {
        try {
          await navigator.clipboard.writeText(result.code);
          UI.toast(t("circle.copied"), "ok");
        } catch (_) { code.select(); }
      }, "ghost small");
      const qr = h("img.circle-qr", {
        alt: t("circle.qr"),
        src: "data:image/svg+xml;charset=utf-8," + encodeURIComponent(result.qr_svg),
      });
      await UI.modal(t("circle.inviteTitle"),
        h("div.form",
          h("p.muted", t("circle.qr")),
          qr,
          h("label.field", h("span", t("circle.code")), code),
          copy,
          h("p.muted", t("circle.expires").replace("{when}",
            new Date(result.expires_at * 1000).toLocaleString()))),
        [{ label: t("common.close"), value: true, kind: "primary" }]);
    } catch (e) { UI.toast(e.message, "error"); }
  }

  async function approveJoin(circle, request) {
    try {
      await Api.post(`/api/circles/${encodeURIComponent(circle.circle_id)}`
        + `/requests/${encodeURIComponent(request.node_id)}/approve`, {});
      await refresh();
    } catch (e) { UI.toast(e.message, "error"); }
  }

  async function rejectJoin(circle, request) {
    try {
      await Api.post(`/api/circles/${encodeURIComponent(circle.circle_id)}`
        + `/requests/${encodeURIComponent(request.node_id)}/reject`, {});
      await refresh();
    } catch (e) { UI.toast(e.message, "error"); }
  }

  async function revokeMember(circle, member) {
    try {
      await Api.post(`/api/circles/${encodeURIComponent(circle.circle_id)}`
        + `/members/${encodeURIComponent(member.node_id)}/revoke`, {});
      await refresh();
    } catch (e) { UI.toast(e.message, "error"); }
  }

  async function leaveCircle(circle) {
    const owner = !!circle.is_owner;
    const ok = await UI.modal(
      owner ? t("circle.delete") : t("circle.leave"),
      h("p", owner ? t("circle.deleteConfirm") : t("circle.leaveConfirm")),
      [{ label: t("common.cancel"), value: false, kind: "ghost" },
       { label: owner ? t("circle.delete") : t("circle.leave"),
         value: true, kind: "danger" }]);
    if (!ok) return;
    try {
      await Api.post(`/api/circles/${encodeURIComponent(circle.circle_id)}/leave`, {});
      await refresh();
    } catch (e) { UI.toast(e.message, "error"); }
  }

  async function acknowledgeNotice() {
    try {
      await Api.post("/api/circles/notice/ack", {});
      await refresh();
    } catch (e) { UI.toast(e.message, "error"); }
  }

  async function switchToCircles() {
    try {
      await App.saveConfig({ circle: { admission_mode: "circle" } }, { quiet: true });
      await Api.post("/api/circles/notice/ack", {});
      await refresh();
    } catch (e) { UI.toast(e.message, "error"); }
  }

  function relabel() { build(); render(); }

  return { init, show, relabel };
})();

App.register("swarm", Monitor);
