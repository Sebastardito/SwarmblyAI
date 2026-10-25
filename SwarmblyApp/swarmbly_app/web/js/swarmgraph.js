/* Swarm graph: this node as the central hive cell, every known peer as a cell
   on a ring, linked by axons. Only real state is drawn: authenticated
   sessions, discovered-but-unconnected announcements and the local model
   pool. A pulse travels along a link only when a micro-task is actually
   dispatched to that node (and never with reduced motion). */
"use strict";

const SwarmGraph = (() => {
  const { svg } = UI;
  const W = 640;
  const H = 360;
  const CX = W / 2;
  const CY = H / 2;
  let root = null;
  let linkIndex = {};

  function hexPath(cx, cy, r) {
    const pts = [];
    for (let i = 0; i < 6; i++) {
      const a = Math.PI / 6 + (i * Math.PI) / 3;
      pts.push(`${(cx + r * Math.cos(a)).toFixed(1)} ${(cy + r * Math.sin(a)).toFixed(1)}`);
    }
    return `M${pts.join("L")}Z`;
  }

  function mount(container) {
    root = svg("svg", { viewBox: `0 0 ${W} ${H}`, class: "swarm-graph", role: "img",
      "aria-label": I18n.t("monitor.graphLabel") });
    container.appendChild(root);
    return root;
  }

  /* data: {self:{id, models[]}, peers:[...], discovered:[...]} */
  function draw(data) {
    if (!root) return;
    UI.clear(root);
    linkIndex = {};
    const peers = (data.peers || []).slice().sort((a, b) => a.node_id.localeCompare(b.node_id));
    const known = new Set(peers.map((p) => p.node_id.slice(0, 16)));
    const pending = (data.discovered || []).filter((d) => !d.verified && !known.has(d.node_hint));
    const cells = [...peers.map((p) => ({ kind: "peer", p })),
      ...pending.map((d) => ({ kind: "announce", d }))].slice(0, 24);
    const n = cells.length;
    const rx = Math.min(260, 190 + n * 4);
    const ry = Math.min(135, 118 + n * 2);

    const links = svg("g", { class: "links" });
    const nodes = svg("g", { class: "nodes" });
    root.appendChild(links);
    root.appendChild(nodes);

    cells.forEach((cell, i) => {
      // Start off the vertical axis so one or two peers never sit on the labels.
      const angle = -Math.PI / 2 + Math.PI / Math.max(n, 2) + (2 * Math.PI * i) / Math.max(n, 1);
      const x = CX + rx * Math.cos(angle);
      const y = CY + ry * Math.sin(angle);
      let state = "announce";
      let id = "";
      let label = "";
      let sub = "";
      if (cell.kind === "peer") {
        const p = cell.p;
        id = p.node_id;
        state = !p.connected ? "lost" : p.worker ? "worker" : "client";
        label = p.short_id || p.node_id.slice(0, 10);
        sub = (p.models || []).map((m) => m.family).filter(Boolean).join(" ")
          || I18n.t("monitor.noModels");
      } else {
        id = cell.d.node_hint || cell.d.address;
        label = (cell.d.node_hint || "").slice(0, 10) || cell.d.address;
        sub = I18n.t("monitor.announced");
      }
      const mx = (CX + x) / 2 + (y - CY) * 0.18;
      const my = (CY + y) / 2 - (x - CX) * 0.18;
      const pathId = `axon-${i}`;
      links.appendChild(svg("path", { id: pathId, class: `axon ${state}`,
        d: `M${CX} ${CY} Q${mx.toFixed(1)} ${my.toFixed(1)} ${x.toFixed(1)} ${y.toFixed(1)}` }));
      linkIndex[String(id).slice(0, 12)] = pathId;
      const g = svg("g", { class: `cell ${state}` });
      g.appendChild(svg("path", { d: hexPath(x, y, 17), class: "cell-body" }));
      if (cell.kind === "peer" && cell.p.tasks_inflight > 0) {
        g.appendChild(svg("path", { d: hexPath(x, y, 8), class: "cell-core" }));
      }
      const tl = svg("text", { x: x.toFixed(1), y: (y + 32).toFixed(1), class: "cell-label" });
      tl.textContent = label;
      const ts = svg("text", { x: x.toFixed(1), y: (y + 45).toFixed(1), class: "cell-sub" });
      ts.textContent = sub;
      g.appendChild(tl);
      g.appendChild(ts);
      if (cell.kind === "peer" && cell.p.rtt_ms !== null && cell.p.rtt_ms !== undefined) {
        const tr = svg("text", { x: ((CX + x) / 2).toFixed(1), y: ((CY + y) / 2 - 4).toFixed(1),
          class: "rtt" });
        tr.textContent = `${Math.round(cell.p.rtt_ms)} ms`;
        links.appendChild(tr);
      }
      nodes.appendChild(g);
    });

    // this node + its local model pool
    const self = svg("g", { class: "cell self" });
    self.appendChild(svg("path", { d: hexPath(CX, CY, 30), class: "cell-body" }));
    self.appendChild(svg("path", { d: `M${CX - 9} ${CY - 15}c18 7 0 22 18 30M${CX + 9} ${CY - 15}c-18 7 0 22 -18 30`,
      class: "self-helix" }));
    const models = data.self?.models || [];
    models.slice(0, 6).forEach((m, i) => {
      const a = Math.PI / 2 + (i - (models.length - 1) / 2) * 0.55;
      const x = CX + 46 * Math.cos(a);
      const y = CY + 46 * Math.sin(a);
      const mg = svg("g", { class: "cell local" });
      mg.appendChild(svg("path", { d: hexPath(x, y, 9), class: "cell-body" }));
      const title = svg("title");
      title.textContent = m;
      mg.appendChild(title);
      self.appendChild(mg);
    });
    const label = svg("text", { x: CX, y: CY + (models.length ? 70 : 48), class: "cell-label self-label" });
    label.textContent = I18n.t("monitor.thisNode");
    self.appendChild(label);
    nodes.appendChild(self);

    if (!n) {
      const empty = svg("text", { x: CX, y: H - 26, class: "graph-empty" });
      empty.textContent = I18n.t("monitor.graphEmpty");
      root.appendChild(empty);
    }
  }

  /* A real dispatch to node `shortId` → one pulse along its axon. */
  function pulse(shortId, kind = "out") {
    if (!root || UI.reducedMotion()) return;
    const pathId = linkIndex[String(shortId).slice(0, 12)];
    if (!pathId) return;
    const dot = svg("circle", { r: 3.5, class: `pulse ${kind}` });
    const motion = svg("animateMotion", { dur: "0.9s", repeatCount: "1", fill: "freeze",
      keyPoints: kind === "out" ? "0;1" : "1;0", keyTimes: "0;1", calcMode: "linear" });
    motion.appendChild(svg("mpath", { href: `#${pathId}` }));
    dot.appendChild(motion);
    root.appendChild(dot);
    motion.beginElement?.();
    setTimeout(() => dot.remove(), 1000);
  }

  return { mount, draw, pulse };
})();
