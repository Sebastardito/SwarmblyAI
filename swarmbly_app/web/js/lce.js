/* Memory (LCE): optional local cognitive extension. Levels C0–C4 explained with
   requirements, compatibility with this machine, maturity and privacy; only
   what this version really runs can be activated. */
"use strict";

const Memory = (() => {
  const { h, clear, t, chip, toggle, button } = UI;
  const ACTIVATABLE = ["C0", "C1"];
  let root;
  const els = {};

  function init(el) { root = el; build(); }

  function build() {
    clear(root);
    els.top = h("div.view-actions");
    els.levels = h("div.levels", { role: "radiogroup", "aria-label": t("memory.levels") });
    els.sources = h("div");
    UI.append(root,
      h("header.view-head", h("h1.view-title", t("memory.title")), els.top),
      h("p.view-lede", t("memory.lede")),
      h("section.panel", h("h2", t("memory.what")),
        h("div.two-col",
          h("div", h("h3", t("memory.docTitle")), h("p", t("memory.docBody"))),
          h("div", h("h3", t("memory.behaviourTitle")), h("p", t("memory.behaviourBody"))))),
      h("section.panel", h("h2", t("memory.levels")), els.levels),
      h("section.panel", h("h2", t("memory.sources")), els.sources));
  }

  async function show() {
    let status = {};
    let levels = { levels: [], recommended: "C0" };
    try {
      [status, levels] = await Promise.all([Api.get("/api/lce/status"), Api.get("/api/lce/levels")]);
    } catch (e) { UI.toast(e.message, "error"); }
    renderTop(status);
    renderLevels(status, levels);
    renderSources(status);
  }

  function renderTop(status) {
    clear(els.top).appendChild(toggle(status.enabled, async (on) => {
      try {
        if (on) await Api.post("/api/lce/activate", { level: ACTIVATABLE.includes(status.level) ? status.level : "C1" });
        else await Api.post("/api/lce/deactivate", {});
        await App.reloadConfig();
      } catch (e) { UI.toast(e.message, "error"); }
      show();
    }, t("memory.enable")));
  }

  function renderLevels(status, data) {
    clear(els.levels);
    for (const lv of data.levels || []) {
      const can = ACTIVATABLE.includes(lv.level);
      const current = status.enabled && status.level === lv.level;
      const card = h(`div.level${current ? ".current" : ""}${can ? "" : ".locked"}`,
        { role: "radio", "aria-checked": String(current), tabindex: can ? 0 : -1 },
        h("div.level-head",
          h("span.level-code", lv.level),
          h("span.level-adds", lv.adds),
          lv.level === data.recommended ? chip(t("memory.recommended"), "ok") : null,
          current ? chip(t("memory.active"), "net") : null),
        h("dl.level-facts",
          h("dt", t("memory.requires")), h("dd", lv.requires),
          h("dt", t("memory.thisMachine")), h("dd", { class: lv.compatible ? "on" : "off" },
            t(lv.compatible ? "memory.compatible" : "memory.notCompatible")),
          h("dt", t("memory.maturity")), h("dd", lv.status),
          h("dt", t("memory.privacy")), h("dd", lv.privacy)),
        can ? button(t("memory.use").replace("{level}", lv.level), async () => {
          try {
            await Api.post("/api/lce/activate", { level: lv.level });
            await App.reloadConfig();
            UI.toast(t("memory.activated").replace("{level}", lv.level), "ok");
          } catch (e) { UI.toast(e.message, "error"); }
          show();
        }, current ? "ghost small" : "small", { disabled: current || !lv.compatible })
          : h("p.level-locked", t("memory.notInVersion")));
      els.levels.appendChild(card);
    }
    if (data.why) els.levels.appendChild(h("p.muted", data.why));
  }

  async function renderSources(status) {
    clear(els.sources);
    const path = status.paths?.sources;
    els.sources.appendChild(h("p", t("memory.sourcesBody")));
    if (path) els.sources.appendChild(h("p", h("code.path", path)));
    if (!status.enabled) {
      els.sources.appendChild(h("p.empty", t("memory.sourcesOff")));
      return;
    }
    // other folders read in place (lce.sources_dirs), e.g. a documents folder
    const dirs = App.state.config?.lce?.sources_dirs || [];
    const saveDirs = async (next) => {
      try { await App.saveConfig({ "lce.sources_dirs": next }); } catch (e) { UI.toast(e.message, "error"); }
      show();
    };
    const input = h("input", { type: "text", placeholder: "/Users/…/Documents", "aria-label": t("memory.addFolder") });
    els.sources.appendChild(h("h3", t("memory.otherFolders")));
    els.sources.appendChild(h("p.muted", t("memory.otherFoldersBody")));
    if (dirs.length) els.sources.appendChild(h("ul.file-list", dirs.map((d) =>
      h("li", h("code.path", d), button(t("memory.removeFolder"), () => saveDirs(dirs.filter((x) => x !== d)), "ghost small")))));
    els.sources.appendChild(h("div.inline-form", input,
      button(t("memory.addFolder"), () => { const v = input.value.trim(); if (v && !dirs.includes(v)) saveDirs([...dirs, v]); }, "small")));
    let list = [];
    try { list = await Api.get("/api/lce/sources"); } catch (_) { /* shown empty */ }
    if (!list.length) {
      els.sources.appendChild(h("p.empty", t("memory.noSources")));
    } else {
      const read = list.filter((f) => f.passages > 0 || f.glossary).length;
      els.sources.appendChild(h("p", t("memory.readCount").replace("{n}", read).replace("{total}", list.length)));
      els.sources.appendChild(h("ul.file-list", list.map((f) =>
        h("li", h("span", f.name), h("span.muted", UI.fmtBytes(f.size_bytes)),
          f.glossary ? chip(t("memory.glossary"), "net")
            : f.unreadable ? chip(t("memory.unreadable"), "warn", f.unreadable)
            : chip(t("memory.passages").replace("{n}", f.passages), f.passages ? "ok" : ""),
          f.unreadable ? h("span.muted", f.unreadable) : null))));
    }
    els.sources.appendChild(h("p.caveat", t("memory.c1Ready")));
  }

  function relabel() { build(); show(); }

  return { init, show, relabel };
})();

App.register("memory", Memory);
