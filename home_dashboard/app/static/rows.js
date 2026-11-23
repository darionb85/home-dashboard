// Shared row renderer for the PWA and the admin page. Uses textContent only.
const LABELS = {copilot: "GitHub Copilot", claude: "Claude", chatgpt: "ChatGPT", gemini: "Gemini", grok: "Grok"};

function fmtReset(iso) {
  if (!iso) return "reset unknown";
  const d = new Date(iso);
  const ms = d - new Date();
  if (ms <= 0) return "reset due";
  const h = Math.floor(ms / 3.6e6);
  const when = h < 48 ? `${h}h` : `${Math.round(h / 24)}d`;
  return `resets in ${when} · ${d.toLocaleDateString(undefined, {month: "short", day: "numeric"})}`;
}

function el(tag, cls, text) {
  const n = document.createElement(tag);
  if (cls) n.className = cls;
  if (text !== undefined) n.textContent = text;
  return n;
}

function renderRows(container, rows, onEdit) {
  container.replaceChildren();
  for (const r of rows) {
    const card = el("div", `row s-${r.status}`);
    const head = el("div", "head");
    const name = el("a", "name", LABELS[r.service] || r.service);
    name.href = r.link; name.target = "_blank"; name.rel = "noopener noreferrer";
    head.append(name, el("span", "badge", r.status));
    const pct = r.pct_used;
    const bar = el("div", "bar");
    const fill = el("div", "fill");
    fill.style.width = pct == null ? "0%" : `${Math.min(100, pct)}%`;
    fill.className = "fill " + (pct == null ? "" : pct >= 85 ? "hi" : pct >= 60 ? "mid" : "lo");
    bar.append(fill);
    const meta = el("div", "meta");
    meta.append(el("span", "pct", pct == null ? "—" : `${pct}%`), el("span", "", fmtReset(r.resets_at)));
    card.append(head, bar, meta);
    if (onEdit && r.service !== "copilot") card.append(onEdit(r));
    container.append(card);
  }
}
