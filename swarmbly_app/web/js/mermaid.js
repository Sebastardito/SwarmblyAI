/* Lazy Mermaid loader for ```mermaid blocks.
   The library is vendored locally (no CDN, works offline); it is only loaded
   the first time a flowchart actually appears, and falls back to the raw
   diagram text if rendering fails. */
"use strict";

const MermaidRender = (() => {
  let loaded = false;
  let loading = null;

  function load() {
    if (loaded) return Promise.resolve();
    if (loading) return loading;
    loading = new Promise((resolve, reject) => {
      const s = document.createElement("script");
      s.src = "/js/vendor/mermaid.min.js";
      s.onload = () => { loaded = true; resolve(); };
      s.onerror = reject;
      document.head.appendChild(s);
    });
    return loading;
  }

  async function process(root) {
    const nodes = root.querySelectorAll("pre.mermaid:not([data-rendered])");
    if (!nodes.length) return;
    try {
      await load();
      if (!window.mermaid) return;
      window.mermaid.initialize({
        startOnLoad: false,
        theme: document.body.classList.contains("light") ? "neutral" : "dark",
        securityLevel: "strict",
        fontFamily: "inherit",
      });
      for (const node of nodes) {
        try {
          const id = "m-" + Math.random().toString(36).slice(2, 10);
          const { svg } = await window.mermaid.render(id, node.textContent);
          node.innerHTML = svg;
          node.dataset.rendered = "1";
        } catch (_) {
          node.dataset.rendered = "error";  // keep the raw source visible
        }
      }
    } catch (_) { /* keep raw code as fallback */ }
  }

  return { process };
})();
