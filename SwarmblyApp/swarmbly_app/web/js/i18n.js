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

  return { load, t, applyAll, current };
})();
