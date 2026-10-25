/* Safe Markdown renderer with a rich, self-contained subset:
   - GFM tables, task lists, strikethrough, images (http/https only)
   - fenced code blocks with a language label
   - admonition/callout boxes ([!NOTE] / [!TIP] / [!WARNING] / [!CAUTION])
   - ASCII trees / box-drawing figures (auto-detected, monospace)
   - Mermaid ```mermaid blocks (rendered by the vendored mermaid.js when present)
   All HTML is escaped first; no raw HTML survives. */
"use strict";

const Markdown = (() => {
  const TREE_RE = /[│├└┌┬┴┼║═╔╗╚╝╠╣╦╩╬─━]/;
  const CALLOUT_TYPES = ["NOTE", "TIP", "WARNING", "CAUTION", "IMPORTANT", "INFO"];

  function escapeHtml(text) {
    return text
      .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function inline(text) {
    text = escapeHtml(text);
    // Remote images are never auto-loaded (a worker could use them as a
    // tracking beacon); they render as an explicit link instead.
    text = text.replace(/!\[([^\]]*)\]\((https?:\/\/[^)\s]+)\)/g,
      '<a href="$2" target="_blank" rel="noopener noreferrer">[image: $1]</a>');
    text = text.replace(/`([^`\n]+)`/g, (_, c) => `<code>${c}</code>`);
    text = text.replace(/\*\*([^*\n]+)\*\*/g, "<strong>$1</strong>");
    text = text.replace(/(^|[^*])\*([^*\n]+)\*/g, "$1<em>$2</em>");
    text = text.replace(/~~([^~\n]+)~~/g, "<del>$1</del>");
    text = text.replace(/\[([^\]]+)\]\((https?:\/\/[^)\s]+)\)/g,
      '<a href="$2" target="_blank" rel="noopener noreferrer">$1</a>');
    return text;
  }

  function parseTableRow(line) {
    const trimmed = line.trim();
    if (!trimmed.startsWith("|")) return null;
    const inner = trimmed.replace(/^\|/, "").replace(/\|$/, "");
    return inner.split("|").map((c) => c.trim());
  }

  function isSeparatorRow(cells) {
    return cells.length > 0 && cells.every((c) => /^:?-{1,}:?$/.test(c));
  }

  function renderTable(rows) {
    if (rows.length < 2) return "";
    const header = rows[0];
    let body = rows.slice(1);
    if (body.length && isSeparatorRow(body[0])) body = body.slice(1);
    const cell = (c, tag) => `<${tag}>${inline(c)}</${tag}>`;
    const thead = `<thead><tr>${header.map((c) => cell(c, "th")).join("")}</tr></thead>`;
    const tbody = body.map((r) =>
      `<tr>${r.map((c) => cell(c, "td")).join("")}</tr>`).join("");
    return `<table>${thead}<tbody>${tbody}</tbody></table>`;
  }

  function renderList(items, ordered) {
    const tag = ordered ? "ol" : "ul";
    const lis = items.map((item) => {
      let inner = item;
      let task = "";
      const m = item.match(/^\[([ xX])\]\s+(.*)$/);
      if (m) {
        task = `<input type="checkbox" disabled${m[1].trim() ? " checked" : ""}>`;
        inner = m[2];
      }
      return `<li>${task}${inline(inner)}</li>`;
    }).join("");
    return `<${tag}>${lis}</${tag}>`;
  }

  function render(src) {
    if (!src) return "";
    const lines = String(src).split("\n");
    const out = [];
    let i = 0;

    while (i < lines.length) {
      const line = lines[i];
      const trimmed = line.trim();

      // fenced code blocks (incl. mermaid)
      if (trimmed.startsWith("```")) {
        const lang = trimmed.slice(3).trim().toLowerCase();
        const buf = [];
        i += 1;
        while (i < lines.length && !lines[i].trim().startsWith("```")) {
          buf.push(lines[i]); i += 1;
        }
        i += 1; // skip closing fence
        const code = escapeHtml(buf.join("\n"));
        if (lang === "mermaid") {
          out.push(`<div class="mermaid-wrap"><pre class="mermaid">${code}</pre></div>`);
        } else {
          const label = lang ? `<div class="code-label">${escapeHtml(lang)}</div>` : "";
          out.push(`<div class="code-block">${label}<pre><code>${code}</code></pre></div>`);
        }
        continue;
      }

      // GFM table
      if (trimmed.startsWith("|")) {
        const rows = [];
        while (i < lines.length && lines[i].trim().startsWith("|")) {
          const cells = parseTableRow(lines[i]);
          if (cells) rows.push(cells);
          i += 1;
        }
        out.push(renderTable(rows));
        continue;
      }

      // callout / blockquote
      if (trimmed.startsWith("> ")) {
        const first = trimmed.slice(2).trim();
        const m = first.match(/^\[!([A-Za-z]+)\](.*)$/);
        if (m && CALLOUT_TYPES.includes(m[1].toUpperCase())) {
          const type = m[1].toUpperCase();
          const title = m[2].trim();
          const body = [];
          i += 1;
          while (i < lines.length && lines[i].trim().startsWith("> ")) {
            body.push(lines[i].trim().slice(2)); i += 1;
          }
          const t = title || type.charAt(0) + type.slice(1).toLowerCase();
          out.push(`<div class="callout ${type.toLowerCase()}"><div class="callout-title">${escapeHtml(t)}</div>${body.map((b) => `<p>${inline(b)}</p>`).join("")}</div>`);
          continue;
        }
        const quotes = [];
        while (i < lines.length && lines[i].trim().startsWith("> ")) {
          quotes.push(lines[i].trim().slice(2)); i += 1;
        }
        out.push(`<blockquote>${quotes.map((q) => `<p>${inline(q)}</p>`).join("")}</blockquote>`);
        continue;
      }

      // ASCII tree / box-drawing figure
      if (TREE_RE.test(line)) {
        const buf = [];
        while (i < lines.length && TREE_RE.test(lines[i])) {
          buf.push(lines[i]); i += 1;
        }
        out.push(`<pre class="ascii">${escapeHtml(buf.join("\n"))}</pre>`);
        continue;
      }

      if (trimmed === "") { i += 1; continue; }

      const heading = trimmed.match(/^(#{1,6})\s+(.*)$/);
      if (heading) {
        const level = Math.min(heading[1].length, 6);
        out.push(`<h${level}>${inline(heading[2])}</h${level}>`);
        i += 1; continue;
      }
      if (/^(-{3,}|\*{3,})$/.test(trimmed)) { out.push("<hr>"); i += 1; continue; }

      // list (collect consecutive items of the same kind)
      const listKind = trimmed.startsWith("- ") || trimmed.startsWith("* ") || trimmed.startsWith("+ ")
        ? "ul" : /^\d+[.)]\s/.test(trimmed) ? "ol" : null;
      if (listKind) {
        const items = [];
        while (i < lines.length) {
          const t = lines[i].trim();
          const ul = t.match(/^[-*+]\s+(.*)$/);
          const ol = t.match(/^\d+[.)]\s+(.*)$/);
          if (listKind === "ul" && ul) { items.push(ul[1]); i += 1; continue; }
          if (listKind === "ol" && ol) { items.push(ol[1]); i += 1; continue; }
          break;
        }
        out.push(renderList(items, listKind === "ol"));
        continue;
      }

      out.push(`<p>${inline(trimmed)}</p>`);
      i += 1;
    }
    return out.join("");
  }

  return { render, escapeHtml };
})();
