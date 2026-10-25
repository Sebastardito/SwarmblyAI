/* First-run assistant: checks the system, explains the recommended
   configuration, offers model downloads (with consent), asks the network
   permissions explicitly and lets the person choose the memory level.
   Every step can be skipped; every choice can be changed later in Settings. */
"use strict";

const Wizard = (() => {
  const { h, clear, t, button, chip } = UI;
  const STEPS = ["welcome", "system", "profile", "models", "permissions", "memory", "done"];
  let index = 0;
  let overlay;
  let body;
  let nav;
  let stepAction = null;   // a step's own primary button, placed last in the nav
  const answers = { lan: null, downloads: null, level: null };

  function show() {
    if (UI.$("#wizard")) return;
    index = 0;
    body = h("div.wizard-body");
    nav = h("div.wizard-nav");
    overlay = h("div#wizard.wizard", { role: "dialog", "aria-modal": "true", "aria-label": t("wizard.title") },
      h("div.wizard-card",
        h("div.wizard-brand", UI.mark(40), h("span.brand-name", "Swarmbly")),
        h("ol.wizard-steps", { "aria-hidden": "true" }), body, nav));
    document.body.appendChild(overlay);
    render();
  }

  function render() {
    const steps = overlay.querySelector(".wizard-steps");
    clear(steps);
    STEPS.forEach((s, i) => steps.appendChild(h(`li${i === index ? ".current" : i < index ? ".done" : ""}`,
      t(`wizard.step.${s}`))));
    clear(body);
    clear(nav);
    stepAction = null;
    const step = STEPS[index];
    ({ welcome, system, profile, models, permissions, memory, done })[step]();
    if (index > 0 && step !== "done") nav.appendChild(button(t("wizard.back"), () => go(-1), "ghost"));
    nav.appendChild(h("span.spacer"));
    if (step !== "done") nav.appendChild(button(t("wizard.skipAll"), finish, "ghost"));
    nav.appendChild(stepAction || button(t("wizard.next"), () => go(1), "primary"));
    body.querySelector("h1, h2")?.setAttribute("tabindex", "-1");
    body.querySelector("h1, h2")?.focus();
  }

  function go(delta) { index = Math.max(0, Math.min(STEPS.length - 1, index + delta)); render(); }

  function welcome() {
    UI.append(body,
      h("h1", t("wizard.welcomeTitle")),
      h("p.lead", t("wizard.welcomeBody")),
      h("p", t("wizard.welcomePrivacy")),
      h("div.lang-choice", ["en", "es"].map((l) => button(l === "en" ? "English" : "Español", async () => {
        await App.setLanguage(l);
        render();
      }, I18n.current() === l ? "primary small" : "ghost small"))));
  }

  async function system() {
    body.appendChild(h("h2", t("wizard.systemTitle")));
    body.appendChild(h("p", t("wizard.systemBody")));
    const slot = h("div", h("p.muted", t("settings.analyzing")));
    body.appendChild(slot);
    try {
      const d = await Api.get("/api/doctor");
      clear(slot).appendChild(Doctor.view(d, () => render()));
    } catch (e) { clear(slot).appendChild(h("p.error", e.message)); }
  }

  async function profile() {
    body.appendChild(h("h2", t("wizard.profileTitle")));
    body.appendChild(h("p", t("wizard.profileBody")));
    const slot = h("div", h("p.muted", t("settings.analyzing")));
    body.appendChild(slot);
    try {
      const rec = await Api.get("/api/setup/recommendation");
      clear(slot).appendChild(Recommendation.view(rec, { onApplied: () => go(1) }));
    } catch (e) { clear(slot).appendChild(h("p.error", e.message)); }
  }

  async function models() {
    body.appendChild(h("h2", t("wizard.modelsTitle")));
    body.appendChild(h("p", t("wizard.modelsBody")));
    const slot = h("div", h("p.muted", t("settings.analyzing")));
    body.appendChild(slot);
    let rec;
    let data;
    try {
      [rec, data] = await Promise.all([Api.get("/api/setup/recommendation"), Api.get("/api/models")]);
    } catch (e) { clear(slot).appendChild(h("p.error", e.message)); return; }
    clear(slot);
    const have = (data.backends || []).flatMap((b) => b.models || []);
    slot.appendChild(h("h3", t("models.installed")));
    slot.appendChild(have.length ? h("ul.model-list", have.map((m) => h("li", h("span.model-name", m.name),
      m.family ? chip(m.family) : null, m.parameter_size ? chip(m.parameter_size) : null)))
      : h("p.empty", t("models.none")));
    if (rec.downloads?.length) {
      slot.appendChild(h("h3", t("wizard.suggested")));
      slot.appendChild(h("ul.download-list", rec.downloads.map((d) => h("li.download-row",
        h("div", h("strong", d.name), h("span.muted", ` ${d.reason}`)),
        h("div.chips", chip(`${d.download_gb} GB`), chip(d.license, d.license.includes("non-commercial") ? "warn" : "")),
        button(t("models.downloadBtn"), () => Downloads.ask(d.name), "small")))));
      slot.appendChild(h("p.muted", t("wizard.downloadLater")));
    }
  }

  function permissions() {
    body.appendChild(h("h2", t("wizard.permTitle")));
    body.appendChild(h("p", t("wizard.permBody")));
    const choice = (key, label, help) => {
      const yes = button(t("wizard.allow"), () => { answers[key] = true; paint(); }, "small");
      const no = button(t("wizard.deny"), () => { answers[key] = false; paint(); }, "small");
      const row = h("div.perm-row", h("div", h("strong", label), h("p.muted", help)), h("div.perm-buttons", yes, no));
      const paint = () => {
        yes.className = `btn small${answers[key] === true ? " primary" : " ghost"}`;
        no.className = `btn small${answers[key] === false ? " danger" : " ghost"}`;
        next.disabled = answers.lan === null || answers.downloads === null;
        next.title = next.disabled ? t("wizard.answerBoth") : "";
      };
      row.paint = paint;
      return row;
    };
    const next = button(t("wizard.next"), async () => {
      try {
        await Api.post("/api/permissions", { lan_discovery: answers.lan, model_downloads: answers.downloads });
        if (answers.lan) await App.saveConfig({ swarm: { lan_enabled: true } }, { quiet: true });
        await App.reloadConfig();
        App.refreshSwarm();
      } catch (e) { UI.toast(e.message, "error"); return; }
      go(1);
    }, "primary", { disabled: true });
    const rows = [choice("lan", t("perm.lan_discovery.label"), t("perm.lan_discovery.help")),
      choice("downloads", t("perm.model_downloads.label"), t("perm.model_downloads.help"))];
    rows.forEach((r) => { body.appendChild(r); r.paint(); });
    body.appendChild(h("div.perm-row.disabled", h("div", h("strong", t("perm.internet.label")),
      h("p.muted", t("perm.internet.help"))), chip(t("wizard.notYet"))));
    body.appendChild(h("p.muted", t("wizard.permLater")));
    stepAction = next;
  }

  async function memory() {
    body.appendChild(h("h2", t("wizard.memoryTitle")));
    body.appendChild(h("p", t("wizard.memoryBody")));
    let levels = { levels: [], recommended: "C0" };
    try { levels = await Api.get("/api/lce/levels"); } catch (_) { /* default */ }
    answers.level = answers.level || levels.recommended;
    const list = h("div.levels.compact");
    const paint = () => {
      clear(list);
      for (const lv of levels.levels.filter((l) => ["C0", "C1"].includes(l.level))) {
        list.appendChild(h(`button.level.choice${answers.level === lv.level ? ".current" : ""}`,
          { type: "button", "aria-pressed": String(answers.level === lv.level), disabled: !lv.compatible,
            onclick: () => { answers.level = lv.level; paint(); } },
          h("span.level-code", lv.level), h("span.level-adds", lv.adds),
          lv.level === levels.recommended ? chip(t("memory.recommended"), "ok") : null,
          h("span.muted", lv.privacy)));
      }
    };
    paint();
    body.appendChild(list);
    body.appendChild(h("p.muted", t("wizard.memoryLater")));
  }

  function done() {
    body.appendChild(h("h2", t("wizard.doneTitle")));
    body.appendChild(h("p", t("wizard.doneBody")));
    stepAction = button(t("wizard.start"), finish, "primary");
  }

  async function finish() {
    try {
      if (answers.level === "C1") await Api.post("/api/lce/activate", { level: "C1" });
      await App.saveConfig({ setup_completed: true }, { quiet: true });
    } catch (e) { UI.toast(e.message, "error"); }
    overlay?.remove();
    await App.reloadConfig();
    App.navigate("chat");
  }

  return { show };
})();
