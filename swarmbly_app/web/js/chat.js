/* Chat: conversations, streaming answers, modes, text attachments, stop/retry,
   export, and "Explore processing" — the full record of how an answer was made. */
"use strict";

const Chat = (() => {
  const { h, clear, t, chip, button, select } = UI;
  const ATTACH_TYPES = ".txt,.md,.markdown,.csv,.tsv,.json,.yaml,.yml,.xml,.html,.py,.js,.ts,.r,.sql,.tex,.log";
  const ATTACH_MAX = 200 * 1024;
  let root;
  let active = null;
  let conversations = [];
  let attachments = [];
  const pending = {};           // message_id -> {el, partial}
  const early = {};             // message_id -> events that arrived before the element
  const requestOf = {};         // message_id -> request_id
  const els = {};

  function init(el) {
    root = el;
    build();
    App.onEvent(onEvent);
    loadConversations();
  }

  function build() {
    clear(root);
    els.list = h("ul.conv-list", { "aria-label": t("chat.conversations") });
    els.side = h("div.conv-side",
      h("div.conv-side-head", button(t("chat.new"), newConversation, "primary small")),
      els.list);
    els.title = h("h1.view-title.chat-title");
    // Narrow screens hide the side list; this picker takes its place.
    els.picker = h("select.conv-picker", { "aria-label": t("chat.conversations") });
    els.picker.addEventListener("change", () => {
      if (els.picker.value === "__new") newConversation();
      else if (els.picker.value) open(els.picker.value);
    });
    els.actions = h("div.chat-actions",
      button(t("chat.export"), exportConversation, "ghost small"),
      button(t("chat.delete"), deleteConversation, "ghost small danger"));
    els.thread = h("div.thread", { role: "log", "aria-live": "polite" });
    els.input = h("textarea.composer-input", { rows: 2, placeholder: t("chat.placeholder"),
      "aria-label": t("chat.placeholder") });
    els.input.addEventListener("keydown", (e) => {
      if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); send(); }
    });
    els.file = h("input", { type: "file", accept: ATTACH_TYPES, multiple: true, hidden: true });
    els.file.addEventListener("change", addFiles);
    els.attachList = h("div.attach-list");
    els.mode = select(modeOptions(), App.state.config?.swarm?.mode || "local", null,
      { "aria-label": t("chat.mode") });
    els.model = h("select", { "aria-label": t("chat.model") });
    els.send = button(t("chat.send"), send, "primary");
    els.stop = button(t("chat.stop"), stop, "danger", { disabled: true });
    els.hint = h("p.composer-hint");
    els.mode.addEventListener("change", updateHint);
    const composer = h("div.composer",
      els.attachList,
      els.input,
      h("div.composer-bar",
        button(t("chat.attach"), () => els.file.click(), "ghost small", { title: t("chat.attachHint") }),
        els.file,
        h("label.inline", h("span", t("chat.mode")), els.mode),
        h("label.inline", h("span", t("chat.model")), els.model),
        h("span.spacer"), els.stop, els.send),
      els.hint);
    UI.append(root, h("div.chat-layout", els.side,
      h("div.chat-main", h("header.chat-head", els.title, els.picker, els.actions), els.thread, composer)));
    refreshModels();
    updateHint();
  }

  function modeOptions() {
    return ["local", "lan", "auto", "internet"].map((m) => ({
      value: m, label: t(`mode.${m}`), disabled: m === "internet" }));
  }

  function updateHint() {
    const mode = els.mode.value;
    const cfg = App.state.config || {};
    let key = `chat.hint.${mode}`;
    if (mode === "local" && cfg.model?.multi_model) key = "chat.hint.localMulti";
    if (mode !== "local" && (cfg.privacy?.tier || "LOCAL") === "LOCAL") key = "chat.hint.tierLocal";
    els.hint.textContent = t(key);
  }

  async function refreshModels() {
    let data;
    try { data = await Api.get("/api/models"); } catch (_) { data = { backends: [] }; }
    const names = [];
    for (const b of data.backends || []) {
      for (const m of b.models || []) if (m.kind !== "embedding") names.push(m.name);
    }
    const current = App.state.config?.model?.model_name || names[0] || "";
    clear(els.model);
    if (!names.length) els.model.appendChild(h("option", { value: "" }, t("chat.noModel")));
    for (const n of names) {
      const o = h("option", { value: n }, n);
      if (n === current) o.selected = true;
      els.model.appendChild(o);
    }
  }

  // ---- conversations ---------------------------------------------------------
  async function loadConversations(openId) {
    try { conversations = await Api.get("/api/conversations"); } catch (_) { conversations = []; }
    renderList();
    const target = openId || active || conversations[0]?.id;
    if (target && conversations.some((c) => c.id === target)) await open(target);
    else renderEmpty();
  }

  function renderList() {
    clear(els.list);
    clear(els.picker);
    if (!active) els.picker.appendChild(h("option", { value: "" }, t("chat.welcomeTitle")));
    for (const c of conversations) {
      const o = h("option", { value: c.id }, c.title || t("chat.untitled"));
      if (c.id === active) o.selected = true;
      els.picker.appendChild(o);
    }
    els.picker.appendChild(h("option", { value: "__new" }, "+ " + t("chat.new")));
    if (!conversations.length) els.list.appendChild(h("li.conv-empty", t("chat.noConversations")));
    for (const c of conversations) {
      els.list.appendChild(h("li", h("button.conv", {
        type: "button", class: c.id === active ? "active" : "",
        onclick: () => open(c.id), title: c.title },
      h("span.conv-title", c.title || t("chat.untitled")),
      h("span.conv-mode", t(`mode.${c.mode}`, c.mode)))));
    }
  }

  function renderEmpty() {
    active = null;
    els.title.textContent = t("chat.welcomeTitle");
    clear(els.thread).appendChild(h("div.empty-state",
      h("p", t("chat.welcome")), h("p.muted", t("chat.welcomeHint"))));
  }

  async function open(id) {
    active = id;
    renderList();
    const conv = conversations.find((c) => c.id === id);
    els.title.textContent = conv?.title || t("chat.untitled");
    if (conv?.mode && conv.mode !== "internet") els.mode.value = conv.mode;
    updateHint();
    const messages = await Api.get(`/api/conversations/${encodeURIComponent(id)}/messages`);
    clear(els.thread);
    for (const m of messages) els.thread.appendChild(messageEl(m));
    if (!messages.length) els.thread.appendChild(h("div.empty-state", h("p.muted", t("chat.welcomeHint"))));
    scroll();
  }

  async function newConversation() {
    const conv = await Api.post("/api/conversations", { mode: els.mode.value, model: els.model.value });
    await loadConversations(conv.id);
    els.input.focus();
  }

  async function deleteConversation() {
    if (!active) return;
    const ok = await UI.modal(t("chat.deleteTitle"), h("p", t("chat.deleteBody")),
      [{ label: t("common.cancel"), value: false, kind: "ghost" },
       { label: t("chat.delete"), value: true, kind: "danger" }]);
    if (!ok) return;
    await Api.del(`/api/conversations/${encodeURIComponent(active)}`);
    active = null;
    await loadConversations();
  }

  async function exportConversation() {
    if (!active) return;
    const fmt = await UI.modal(t("chat.exportTitle"), h("p", t("chat.exportBody")), [
      { label: "Markdown", value: "markdown", kind: "primary" },
      { label: "JSON", value: "json" }, { label: "HTML", value: "html" },
      { label: t("common.cancel"), value: null, kind: "ghost" }]);
    if (!fmt) return;
    const ext = { markdown: "md", json: "json", html: "html" }[fmt];
    Api.download(`/api/conversations/${encodeURIComponent(active)}/export?format=${fmt}`,
      `swarmbly-${active}.${ext}`).catch((e) => UI.toast(e.message, "error"));
  }

  // ---- attachments (text files, read locally) -----------------------------------
  async function addFiles() {
    for (const file of els.file.files) {
      if (file.size > ATTACH_MAX) {
        UI.toast(t("chat.attachTooBig").replace("{name}", file.name), "error");
        continue;
      }
      attachments.push({ name: file.name, text: await file.text() });
    }
    els.file.value = "";
    renderAttachments();
  }

  function renderAttachments() {
    clear(els.attachList);
    attachments.forEach((a, i) => els.attachList.appendChild(h("span.chip.attach", a.name,
      h("button.chip-x", { type: "button", "aria-label": t("chat.removeAttachment"),
        onclick: () => { attachments.splice(i, 1); renderAttachments(); } }, "×"))));
  }

  function composeText() {
    const question = els.input.value.trim();
    if (!attachments.length) return question;
    const blocks = attachments.map((a) => `Attached file \`${a.name}\`:\n\n\`\`\`\n${a.text}\n\`\`\``);
    return `${blocks.join("\n\n")}\n\n${question}`;
  }

  // ---- sending -------------------------------------------------------------------
  async function send() {
    const text = composeText();
    if (!text) return;
    if (!active) {
      const conv = await Api.post("/api/conversations", { mode: els.mode.value, model: els.model.value });
      active = conv.id;
    }
    els.input.value = "";
    attachments = [];
    renderAttachments();
    let res;
    try {
      res = await Api.post(`/api/conversations/${encodeURIComponent(active)}/messages`,
        { text, mode: els.mode.value, model: els.model.value });
    } catch (err) {
      UI.toast(err.message, "error");
      return;
    }
    els.thread.querySelector(".empty-state")?.remove();
    track(res);
    conversations = await Api.get("/api/conversations");
    renderList();
    els.title.textContent = conversations.find((c) => c.id === active)?.title || "";
  }

  function track(res) {
    els.thread.appendChild(messageEl(res.user_message));
    const el = messageEl(res.assistant_message, true);
    els.thread.appendChild(el);
    pending[res.assistant_message.id] = { el, partial: "", conv: active, last: Date.now() };
    els.stop.disabled = false;
    const queued = early[res.assistant_message.id];
    delete early[res.assistant_message.id];
    (queued || []).forEach(onEvent);
    scroll();
  }

  async function stop() {
    const ids = Object.keys(pending);
    for (const mid of ids) {
      const rid = requestOf[mid];
      if (rid) await Api.post(`/api/requests/${encodeURIComponent(rid)}/stop`, {});
    }
    if (!ids.some((mid) => requestOf[mid])) await Api.post("/api/requests/_stop_last", {});
  }

  function onEvent(event) {
    const p = event.payload || {};
    if (event.type === "request.started" && p.message_id) requestOf[p.message_id] = p.request_id;
    if (!["chat.delta", "chat.done", "chat.notice"].includes(event.type)) return;
    if (event.type === "ws.open") { checkPending(true); return; }
    const entry = pending[p.message_id];
    if (entry) entry.last = Date.now();
    if (!entry) {
      (early[p.message_id] = early[p.message_id] || []).push(event);
      return;
    }
    if (event.type === "chat.delta") {
      entry.partial += p.delta;
      entry.el.querySelector(".md").textContent = entry.partial;
      scroll();
    } else if (event.type === "chat.notice") {
      setNote(entry.el, p.note);
    } else {
      delete pending[p.message_id];
      els.stop.disabled = Object.keys(pending).length === 0;
      refreshMessage(p.message_id, entry.el, p);
    }
  }

  /* A swarm request can run for minutes with few events; if the WebSocket
     dropped meanwhile (sleep, network change, a server-side ping timeout),
     the final event is lost and the answer only showed after a reload. Every
     few seconds, a message with no recent event is read from the database
     and shown once it is finished; after a reconnection, at once. */
  async function checkPending(force = false) {
    const now = Date.now();
    for (const [mid, entry] of Object.entries(pending)) {
      if (!force && now - entry.last < 8000) continue;
      entry.last = now;
      let m = null;
      try {
        const messages = await Api.get(`/api/conversations/${encodeURIComponent(entry.conv)}/messages`);
        m = messages.find((x) => x.id === mid);
      } catch (_) { continue; }
      const status = m?.meta?.status;
      if (m && status && status !== "running" && pending[mid]) {
        delete pending[mid];
        els.stop.disabled = Object.keys(pending).length === 0;
        if (entry.el.isConnected && entry.conv === active) entry.el.replaceWith(messageEl(m));
        scroll();
      }
    }
  }
  setInterval(() => { if (Object.keys(pending).length) checkPending(); }, 5000);

  /* Re-read the finished message from the DB (it now holds the stage log). */
  async function refreshMessage(mid, el, payload) {
    let m = null;
    try {
      const messages = await Api.get(`/api/conversations/${encodeURIComponent(active)}/messages`);
      m = messages.find((x) => x.id === mid);
    } catch (_) { /* fall back to the event payload */ }
    if (!m) {
      m = { id: mid, role: "assistant",
        content: payload.status === "failed" ? `[Error] ${payload.error || ""}` : payload.content,
        meta: { ...(payload.meta || {}), request_id: payload.request_id, status: payload.status } };
    }
    if (el.isConnected) el.replaceWith(messageEl(m));
    scroll();
  }

  function scroll() { els.thread.scrollTop = els.thread.scrollHeight; }

  // ---- rendering -------------------------------------------------------------------
  function messageEl(m, streaming = false) {
    if (m.role === "user") return h("article.msg.user", h("div.msg-body", m.content));
    const meta = m.meta || {};
    const body = h("div.md");
    if (streaming) body.appendChild(h("span.cursor", { "aria-hidden": "true" }));
    else {
      body.innerHTML = Markdown.render(m.content || "");  // Markdown escapes before formatting
      if (window.MermaidRender) MermaidRender.process(body);
    }
    const article = h(`article.msg.assistant${meta.status === "failed" ? ".failed" : ""}`,
      h("div.msg-gutter", { "aria-hidden": "true" }), body);
    if (meta.local_reason) setNote(article, meta.local_reason);
    if (!streaming) article.appendChild(footer(m));
    return article;
  }

  function setNote(article, note) {
    if (!note) return;
    let n = article.querySelector(".msg-note");
    if (!n) { n = h("p.msg-note"); article.insertBefore(n, article.querySelector(".md")); }
    n.textContent = note;
  }

  function footer(m) {
    const meta = m.meta || {};
    const sw = meta.swarm || {};
    const chips = [];
    if (meta.status === "stopped") chips.push(chip(t("chat.stopped"), "warn"));
    if (meta.executed === "distributed") {
      const localOnly = (sw.nodes || []).length && (sw.nodes || []).every((n) => n.role === "local model");
      chips.push(chip(t(localOnly ? "chat.execLocalPool" : "chat.execDistributed"), "net"));
      if (sw.router?.whole_request_replicas) {
        chips.push(chip(t("chat.replicas").replace("{n}", (sw.attempts || []).filter((a) => a.status === "accepted").length)));
      } else if (sw.n_tasks) chips.push(chip(t("chat.fragments").replace("{n}", sw.n_tasks)));
      if (sw.consensus) chips.push(chip(t("chat.agreement").replace("{v}", sw.consensus.mean_agreement),
        "warn", t("chat.agreementTitle")));
    } else if (meta.status && meta.status !== "failed") {
      chips.push(chip(t("chat.execLocal")));
    }
    if (sw.evidence?.used) chips.push(chip(t("chat.evidenceChip").replace("{n}", sw.evidence.used),
      "", t("chat.evidenceTitle").replace("{n}", sw.evidence.used)));
    if (meta.lce?.sources?.length) chips.push(chip(t("chat.lceChip").replace("{n}", meta.lce.sources.length),
      "", t("chat.lceTitle")));
    if (meta.model) chips.push(chip(meta.model));
    const ms = sw.total_ms ?? meta.total_ms;
    if (ms) chips.push(chip(UI.fmtMs(ms)));
    if (meta.completion_tokens) chips.push(chip(t("chat.tokens").replace("{n}", meta.completion_tokens)));
    const actions = [];
    if ((m.stages && m.stages.length) || meta.swarm || meta.lce) {
      actions.push(button(t("chat.explore"), () => Explore.open(m), "ghost small"));
    }
    if (meta.status === "failed" || meta.status === "stopped") {
      actions.push(button(t("chat.retry"), () => retry(m.id), "ghost small"));
    }
    return h("footer.msg-foot", h("div.chips", chips), h("div.msg-actions", actions));
  }

  async function retry(messageId) {
    if (!active) return;
    try {
      track(await Api.post(`/api/conversations/${encodeURIComponent(active)}/messages/${encodeURIComponent(messageId)}/retry`, {}));
    } catch (err) { UI.toast(err.message, "error"); }
  }

  function relabel() { build(); loadConversations(active); }
  function show() { refreshModels(); updateHint(); }

  return { init, show, relabel };
})();

/* "Explore processing": everything recorded about one answer. */
const Explore = (() => {
  const { h, t, readout, chip, button } = UI;

  // Where the answer's outside information came from: public evidence sent
  // with the fragments (Wikipedia, attributed) and local LCE passages.
  function sourcesView(evidence, lce) {
    const parts = [];
    if (evidence && evidence.sources?.length) {
      parts.push(h("p.muted", t("explore.evidenceNote")),
        h("ul.sources", evidence.sources.map((s) => h("li",
          h("span", `${s.item}: `),
          h("a", { href: s.url, target: "_blank", rel: "noopener noreferrer" }, s.title)))));
      if (evidence.errors?.length) parts.push(h("p.note", `${t("explore.evidenceErrors")} ${evidence.errors.join(", ")}`));
    } else if (evidence && evidence.skipped) {
      parts.push(h("p.muted", `${t("explore.evidenceSkipped")} ${evidence.skipped}`));
    }
    if (lce && lce.sources?.length) {
      parts.push(h("p.muted", t("explore.lceNote")),
        h("ul.sources", lce.sources.map((s) => h("li", `[${s.n}] ${s.source}`))));
    }
    return parts.length ? h("div", parts) : null;
  }

  function open(m) {
    const meta = m.meta || {};
    const sw = meta.swarm || {};
    const routing = sw.routing || {};
    const sections = [h("div.readouts",
      readout(t("explore.executed"), t(`explore.exec.${meta.executed || "local"}`, meta.executed), "measured"),
      readout(t("explore.tier"), routing.tier, "measured"),
      readout(t("explore.lane"), routing.lane, "measured"),
      readout(t("explore.tasks"), sw.n_tasks, "measured"),
      readout(t("explore.rho"), sw.rho_achieved, "measured"),
      readout(t("explore.total"), UI.fmtMs(sw.total_ms ?? meta.total_ms), "measured"),
      readout(t("explore.coverage"), sw.coverage ? sw.coverage.c_eff : null, "estimated"),
      readout(t("explore.embedder"), sw.embedder, null))];
    if (meta.local_reason) sections.push(h("p.note", meta.local_reason));
    sections.push(h("h3", t("explore.pipeline")), Helix.render(m.stages || []));
    const sources = sourcesView(sw.evidence, meta.lce);
    if (sources) sections.push(h("h3", t("explore.sources")), sources);
    if (sw.attempts?.length) sections.push(h("h3", t("explore.attempts")), attemptsTable(sw.attempts));
    if (sw.consensus) sections.push(h("h3", t("explore.consensus")), consensusView(sw.consensus));
    if (sw.seams?.length) {
      sections.push(h("h3", t("explore.seams")), h("p.muted", sw.seam_policy || ""),
        h("ul.seams", sw.seams.map((s) => h("li", chip(`${s.left} | ${s.right}`),
          chip(`${t("explore.similarity")} ${s.similarity}`),
          chip(t(`explore.path.${s.path}`, s.path), s.path === "bridge" ? "warn" : "")))));
    }
    sections.push(h("h3", t("explore.caveats")), h("ul.caveats",
      h("li", t("explore.caveat.verification")), h("li", t("explore.caveat.agreement")),
      h("li", t("explore.caveat.thresholds"))));
    const rid = meta.request_id;
    if (rid) {
      sections.push(h("div.report-actions",
        ["markdown", "json", "html"].map((fmt) => button(t(`explore.download.${fmt}`), () =>
          Api.download(`/api/requests/${encodeURIComponent(rid)}/report?format=${fmt}`,
            `swarmbly-report-${rid}.${{ markdown: "md", json: "json", html: "html" }[fmt]}`)
            .catch((e) => UI.toast(e.message, "error")), "ghost small")),
        button(t("explore.save"), async () => {
          try {
            const r = await fetch(`/api/requests/${encodeURIComponent(rid)}/report?format=markdown&save=true`,
              { headers: { "X-Swarmbly-Token": Api.TOKEN } });
            if (!r.ok) throw new Error(String(r.status));
            UI.toast(t("explore.saved").replace("{path}", r.headers.get("X-Saved-To") || ""), "ok");
          } catch (e) { UI.toast(e.message, "error"); }
        }, "small")));
    }
    UI.modal(t("explore.title"), h("div.explore", sections),
      [{ label: t("common.close"), value: null, kind: "primary" }]);
  }

  function attemptsTable(attempts) {
    return h("div.table-wrap", h("table.data",
      h("thead", h("tr", ["task", "attempt", "reason", "node", "family", "status", "time", "code"]
        .map((k) => h("th", { scope: "col" }, t(`explore.col.${k}`))))),
      h("tbody", attempts.map((a) => h("tr",
        h("td", a.task), h("td", String(a.attempt)), h("td", t(`explore.reason.${a.reason}`, a.reason)),
        h("td", h("code", a.node)), h("td", a.family),
        h("td", h(`span.status-word.${a.status === "accepted" ? "completed" : a.status === "failed" ? "failed" : "skipped"}`,
          t(`explore.attempt.${a.status}`, a.status))),
        h("td", UI.fmtMs(a.elapsed_ms)), h("td", a.code || ""))))));
  }

  function consensusView(c) {
    const blocks = Object.entries(c.per_task || {}).map(([task, b]) => h("div.consensus-task",
      h("div.consensus-head", h("strong", task), chip((b.families || []).join(" + ")),
        chip(`${t("explore.meanAgreement")} ${b.mean_agreement}`)),
      h("ol.units", (b.units || []).map((u) => h(`li.unit.${String(u.label).toLowerCase()}`,
        h("span.unit-label", t(`explore.label.${u.label}`, u.label)),
        h("span.unit-score", String(u.agreement)), h("span.unit-text", u.text))))));
    return h("div.consensus", h("p.muted", t("explore.agreementNote")), blocks);
  }

  return { open };
})();

App.register("chat", Chat);
