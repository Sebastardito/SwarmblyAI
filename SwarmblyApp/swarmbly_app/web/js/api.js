/* Thin API client: REST helpers + a WebSocket event subscription. */
"use strict";

const Api = (() => {
  /* Per-launch session token injected by the server into this page. */
  const tokenMeta = document.querySelector('meta[name="swarmbly-token"]');
  const TOKEN = tokenMeta ? tokenMeta.getAttribute("content") : "";

  /* Escape any value before it goes into innerHTML. Remote peers control
     some strings (model families, error details): never trust them. */
  function esc(value) {
    return String(value === undefined || value === null ? "" : value)
      .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;").replace(/'/g, "&#39;");
  }

  async function request(method, path, body) {
    const opts = { method, headers: { "X-Swarmbly-Token": TOKEN } };
    if (body !== undefined) {
      opts.headers["Content-Type"] = "application/json";
      opts.body = JSON.stringify(body);
    }
    const resp = await fetch(path, opts);
    if (!resp.ok) {
      let detail = resp.statusText;
      try { detail = (await resp.json()).detail || detail; } catch (_) {}
      throw new Error(`${resp.status} ${detail}`);
    }
    const text = await resp.text();
    return text ? JSON.parse(text) : null;
  }

  const get = (p) => request("GET", p);
  const post = (p, b) => request("POST", p, b);
  const put = (p, b) => request("PUT", p, b);
  const del = (p) => request("DELETE", p);

  /* WebSocket: one connection, many typed handlers. */
  function subscribe(onEvent) {
    const proto = location.protocol === "https:" ? "wss" : "ws";
    const ws = new WebSocket(`${proto}://${location.host}/ws?token=${encodeURIComponent(TOKEN)}`);
    ws.onmessage = (msg) => {
      try { onEvent(JSON.parse(msg.data)); } catch (_) {}
    };
    ws.onopen = () => {
      retryDelay = 2000;
      // after a reconnection, views re-read what may have finished meanwhile
      try { onEvent({ type: "ws.open", payload: {} }); } catch (_) {}
    };
    ws.onclose = () => setTimeout(() => reconnect(onEvent), retryDelay);
    return ws;
  }

  /* The session token changes at every launch: a tab opened before a restart
     holds a stale one and every reconnection is refused. Instead of retrying
     forever (it flooded the terminal), check the token once the server
     answers; if it is stale, reload the page to get the new one (at most once
     per 30 s, so a misconfigured server cannot cause a reload loop). While
     the server is down, retry with exponential back-off up to 30 s. */
  let retryDelay = 2000;
  async function reconnect(onEvent) {
    let status = 0;
    try {
      status = (await fetch("/api/config", { headers: { "X-Swarmbly-Token": TOKEN } })).status;
    } catch (_) { status = 0; }
    if (status === 401 || status === 403) {
      let last = 0;
      try { last = Number(sessionStorage.getItem("swarmbly-reload") || 0); } catch (_) {}
      if (Date.now() - last > 30000) {
        try { sessionStorage.setItem("swarmbly-reload", String(Date.now())); } catch (_) {}
        location.reload();
        return;
      }
      return;   // stale token and a recent reload: stop; the user can reload by hand
    }
    if (status === 0) {
      retryDelay = Math.min(retryDelay * 2, 30000);
      setTimeout(() => reconnect(onEvent), retryDelay);
      return;
    }
    subscribe(onEvent);
  }

  /* Authenticated download (export/report links cannot carry the header). */
  async function download(path, filename) {
    const resp = await fetch(path, { headers: { "X-Swarmbly-Token": TOKEN } });
    if (!resp.ok) throw new Error(`${resp.status}`);
    const blob = await resp.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url; a.download = filename;
    document.body.appendChild(a); a.click(); a.remove();
    setTimeout(() => URL.revokeObjectURL(url), 2000);
  }

  return { request, get, post, put, del, subscribe, download, esc, TOKEN };
})();
