/* Small DOM toolkit. Everything is built with textContent, never innerHTML,
   so remote strings (peer advertisements, model output metadata) are inert. */
"use strict";

const UI = (() => {
  const SVG_NS = "http://www.w3.org/2000/svg";

  /* h("div.card#id", {onclick, title, dataset:{}}, child, "text", [children]) */
  function h(spec, attrs, ...children) {
    const [tagPart, ...rest] = spec.split(/(?=[.#])/);
    const el = document.createElement(tagPart || "div");
    for (const token of rest) {
      if (token.startsWith(".")) el.classList.add(token.slice(1));
      else if (token.startsWith("#")) el.id = token.slice(1);
    }
    if (attrs && (typeof attrs !== "object" || attrs instanceof Node || Array.isArray(attrs))) {
      children.unshift(attrs);
      attrs = null;
    }
    for (const [key, value] of Object.entries(attrs || {})) {
      if (value === undefined || value === null || value === false) continue;
      if (key.startsWith("on") && typeof value === "function") {
        el.addEventListener(key.slice(2), value);
      } else if (key === "dataset") {
        Object.assign(el.dataset, value);
      } else if (key === "class") {
        String(value).split(/\s+/).filter(Boolean).forEach((c) => el.classList.add(c));
      } else if (key === "text") {
        el.textContent = String(value);
      } else if (value === true) {
        el.setAttribute(key, "");
      } else {
        el.setAttribute(key, String(value));
      }
    }
    append(el, ...children);
    return el;
  }

  function append(el, ...children) {
    for (const child of children.flat(Infinity)) {
      if (child === null || child === undefined || child === false) continue;
      el.appendChild(child instanceof Node ? child : document.createTextNode(String(child)));
    }
    return el;
  }

  function svg(tag, attrs = {}, ...children) {
    const el = document.createElementNS(SVG_NS, tag);
    for (const [k, v] of Object.entries(attrs)) {
      if (v !== undefined && v !== null) el.setAttribute(k, String(v));
    }
    for (const c of children.flat()) if (c) el.appendChild(c);
    return el;
  }

  function clear(el) { while (el && el.firstChild) el.removeChild(el.firstChild); return el; }
  function $(sel, root = document) { return root.querySelector(sel); }
  const t = (key, fallback) => I18n.t(key, fallback);

  /* A labelled value with its nature: measured / estimated / unknown. */
  function readout(label, value, nature) {
    return h("div.readout",
      h("span.readout-label", label),
      h("span.readout-value", value === null || value === undefined || value === "" ? "—" : String(value)),
      nature ? h(`span.nature.${nature}`, { title: t(`nature.${nature}`) }, t(`nature.${nature}`)) : null);
  }

  function chip(text, kind = "", title) {
    return h("span.chip", { title, class: kind }, text);
  }

  function button(label, onclick, kind = "", attrs = {}) {
    const extra = attrs.class ? ` ${attrs.class}` : "";
    return h("button.btn", { type: "button", onclick, ...attrs, class: `${kind}${extra}` }, label);
  }

  function toggle(checked, onchange, label, attrs = {}) {
    const input = h("input", { type: "checkbox", role: "switch", ...attrs });
    input.checked = !!checked;
    input.addEventListener("change", () => onchange(input.checked));
    return h("label.switch", input, h("span.switch-track"), label ? h("span.switch-label", label) : null);
  }

  function select(options, value, onchange, attrs = {}) {
    const el = h("select", attrs);
    for (const opt of options) {
      const o = h("option", { value: opt.value, disabled: opt.disabled }, opt.label);
      if (String(opt.value) === String(value)) o.selected = true;
      el.appendChild(o);
    }
    if (onchange) el.addEventListener("change", () => onchange(el.value));
    return el;
  }

  /* Modal dialog. Resolves with the value of the pressed action (or null). */
  function modal(title, body, actions) {
    return new Promise((resolve) => {
      const close = (value) => { overlay.remove(); document.removeEventListener("keydown", onKey); resolve(value); };
      const onKey = (e) => { if (e.key === "Escape") close(null); };
      const card = h("div.modal", { role: "dialog", "aria-modal": "true", "aria-label": title },
        h("h2.modal-title", title),
        h("div.modal-body", body),
        h("div.modal-actions", actions.map((a) =>
          button(a.label, () => close(a.value), a.kind || "", a.attrs || {}))));
      const overlay = h("div.overlay", { onclick: (e) => { if (e.target === overlay) close(null); } }, card);
      document.body.appendChild(overlay);
      document.addEventListener("keydown", onKey);
      const focusable = card.querySelector("button.primary") || card.querySelector("button");
      if (focusable) focusable.focus();
    });
  }

  let toastTimer = null;
  function toast(text, kind = "") {
    let el = $("#toast");
    if (!el) { el = h("div#toast", { role: "status", "aria-live": "polite" }); document.body.appendChild(el); }
    el.className = `show ${kind}`;
    el.textContent = text;
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => { el.className = ""; }, 4200);
  }

  function fmtBytes(n) {
    if (n === null || n === undefined) return "—";
    const units = ["B", "KB", "MB", "GB", "TB"];
    let i = 0; let v = Number(n);
    while (v >= 1024 && i < units.length - 1) { v /= 1024; i++; }
    return `${v.toFixed(v < 10 && i ? 1 : 0)} ${units[i]}`;
  }
  function fmtMs(ms) {
    if (ms === null || ms === undefined) return "—";
    return ms < 1000 ? `${Math.round(ms)} ms` : `${(ms / 1000).toFixed(ms < 10000 ? 1 : 0)} s`;
  }
  function fmtAgo(ts) {
    if (!ts) return "—";
    const s = Math.max(0, Date.now() / 1000 - ts);
    if (s < 60) return t("time.seconds").replace("{n}", Math.round(s));
    if (s < 3600) return t("time.minutes").replace("{n}", Math.round(s / 60));
    return t("time.hours").replace("{n}", Math.round(s / 3600));
  }
  function shortId(id) { return id ? String(id).slice(0, 10) : "—"; }

  /* Brand mark: a hive cell holding a double helix. */
  function mark(size = 28) {
    const s = svg("svg", { viewBox: "0 0 32 32", width: size, height: size, class: "mark", "aria-hidden": "true" });
    s.appendChild(svg("path", { d: "M16 2 28 9v14L16 30 4 23V9Z", class: "mark-cell" }));
    s.appendChild(svg("path", { d: "M11 8c10 4 0 12 10 16M21 8c-10 4 0 12-10 16", class: "mark-helix" }));
    for (const y of [11, 16, 21]) s.appendChild(svg("line", { x1: 12.5, x2: 19.5, y1: y, y2: y, class: "mark-rung" }));
    return s;
  }

  const reducedMotion = () => document.body.classList.contains("reduce-motion") ||
    window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  return { h, svg, append, clear, $, t, readout, chip, button, toggle, select, modal, toast,
           fmtBytes, fmtMs, fmtAgo, shortId, mark, reducedMotion };
})();
