/* i18n: loads en.json/es.json; UI defaults to English, switchable and persisted. */
"use strict";

const I18n = (() => {
  let lang = "en";
  const dicts = {};

  async function load(language) {
    if (!dicts[language]) {
      const resp = await fetch(`/i18n/${language}.json`);
      dicts[language] = await resp.json();
    }
    lang = language;
    document.documentElement.lang = language;
    applyAll();
  }

  function t(key, fallback = key) {
    let node = dicts[lang] || dicts.en || {};
    for (const part of key.split(".")) {
      if (node && typeof node === "object" && part in node) node = node[part];
      else return fallback;
    }
    return node;
  }

  function applyAll(root = document) {
    root.querySelectorAll("[data-i18n]").forEach((el) => {
      el.textContent = t(el.dataset.i18n);
    });
    root.querySelectorAll("[data-i18n-ph]").forEach((el) => {
      el.placeholder = t(el.dataset.i18nPh);
    });
    root.querySelectorAll("[data-i18n-title]").forEach((el) => {
      el.title = t(el.dataset.i18nTitle);
    });
  }

  function current() { return lang; }

  /* Pipeline notes come from the engine in English ("the router judged the
     request not decomposable"); known ones are shown in the UI language. */
  function reason(text) {
    const s = String(text || "");
    const table = (dicts[lang] || {}).stageReasons || {};
    if (table[s]) return table[s];
    for (const [k, v] of Object.entries(table)) {
      if (k.endsWith("*") && s.startsWith(k.slice(0, -1))) return v + s.slice(k.length - 1);
    }
    return s;
  }

  return { load, t, applyAll, current, reason };
})();
