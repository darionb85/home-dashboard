/* AI Usage card: one card per AI with up to two gauges (current/session + weekly)
 * and their reset times. Installed automatically by the Home Dashboard add-on.
 *
 *   type: custom:ai-usage-card
 *   entity: sensor.ai_usage_claude
 *   name: Claude            # optional
 *
 * Reads the sensor's attributes: session_pct, session_resets_at, weekly_pct,
 * weekly_resets_at, status. With no session/weekly attributes it shows the
 * sensor state as a single gauge (e.g. Copilot's monthly credits).
 */
const CARD_VERSION = "0.3.2";
const HAS_WEEKLY = ["claude", "chatgpt", "gemini"];

const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const num = (v) => (v === null || v === undefined || v === "" || isNaN(Number(v)) ? null : Number(v));

function severity(p) {
  if (p >= 85) return "var(--error-color, #db4437)";
  if (p >= 60) return "var(--warning-color, #ffa600)";
  return "var(--success-color, #43a047)";
}

function fmtReset(iso, text) {
  if (!iso) return text ? `resets ${text}` : "";
  const d = new Date(iso);
  if (isNaN(d)) return "";
  const ms = d - new Date();
  if (ms <= 0) return "resetting\u2026";
  const mins = Math.round(ms / 60000);
  if (mins < 60) return `resets in ${mins}m`;
  if (mins < 24 * 60) return `resets in ${Math.floor(mins / 60)}h ${mins % 60}m`;
  if (ms < 7 * 864e5) return `resets ${d.toLocaleString(undefined, { weekday: "short", hour: "numeric", minute: "2-digit" })}`;
  return `resets ${d.toLocaleDateString(undefined, { month: "short", day: "numeric" })}`;
}

// Semicircle like the built-in gauge card: track + value arc.
function arc(pct) {
  const p = Math.max(0, Math.min(100, pct ?? 0)) / 100;
  const a = Math.PI * (1 - p);
  const x = 50 + 40 * Math.cos(a), y = 50 - 40 * Math.sin(a);
  const track = "M 10 50 A 40 40 0 0 1 90 50";
  const value = p <= 0 ? "" : `M 10 50 A 40 40 0 0 1 ${x.toFixed(2)} ${y.toFixed(2)}`;
  return { track, value };
}

class AiUsageCard extends HTMLElement {
  setConfig(config) {
    if (!config || !config.entity) throw new Error("ai-usage-card: 'entity' is required");
    this._config = config;
    if (!this.shadowRoot) this.attachShadow({ mode: "open" });
  }

  set hass(hass) {
    this._hass = hass;
    this._render();
  }

  getCardSize() { return 3; }
  getGridOptions() { return { columns: 6, rows: "auto", min_columns: 6 }; }
  static getStubConfig(hass) {
    const e = Object.keys(hass.states).find((k) => k.startsWith("sensor.ai_usage_"));
    return { entity: e || "sensor.ai_usage_claude" };
  }

  _gauges(st) {
    const a = st.attributes || {};
    const out = [];
    const s = num(a.session_pct), w = num(a.weekly_pct);
    if (s !== null) out.push({ label: "Current", pct: s, reset: fmtReset(a.session_resets_at, a.session_reset_text) });
    const credits = a.credits ? ` \u00b7 ${a.credits} credits` : "";
    if (w !== null) out.push({ label: "Weekly", pct: w, reset: fmtReset(a.weekly_resets_at, a.weekly_reset_text) + credits });
    else if (s !== null && HAS_WEEKLY.some((k) => this._config.entity.endsWith(`_${k}`)))
      out.push({ label: "Weekly", pct: null, reset: "no weekly number received" });
    if (!out.length) {
      const v = num(st.state);
      const isCopilot = this._config.entity.endsWith("_copilot");
      out.push({ label: isCopilot ? "This month" : "Usage", pct: v, reset: fmtReset(a.resets_at) });
    }
    return out;
  }

  _render() {
    if (!this._config || !this._hass || !this.shadowRoot) return;
    const st = this._hass.states[this._config.entity];
    const name = this._config.name || (st && st.attributes.friendly_name || this._config.entity).replace(/ usage$/i, "");
    let body;
    if (!st) {
      body = `<div class="empty">Entity not found: ${esc(this._config.entity)}</div>`;
    } else {
      const gauges = this._gauges(st);
      body = `<div class="gauges">${gauges.map((g) => {
        const { track, value } = arc(g.pct);
        const color = g.pct === null ? "transparent" : severity(g.pct);
        const shown = g.pct === null ? "\u2014" : `${Math.round(g.pct * 10) / 10}%`;
        return `<div class="gauge">
          <svg viewBox="0 0 100 58" role="img" aria-label="${esc(g.label)} ${esc(shown)}">
            <path d="${track}" class="track"/>
            ${value ? `<path d="${value}" class="value" style="stroke:${color}"/>` : ""}
            <text x="50" y="49" class="pct">${esc(shown)}</text>
          </svg>
          <div class="label">${esc(g.label)}</div>
          <div class="reset">${esc(g.reset)}</div>
        </div>`;
      }).join("")}</div>`;
    }
    const status = st && st.attributes.status;
    const chip = status === "error" || status === "stale"
      ? `<span class="chip ${status}" title="${esc(st.attributes.error || "")}">${esc(status)}</span>` : "";
    this.shadowRoot.innerHTML = `
      <style>
        ha-card { padding: 12px 16px 14px; cursor: pointer; height: 100%; box-sizing: border-box; }
        .head { display: flex; justify-content: space-between; align-items: center; margin-bottom: 4px; }
        .name { font-size: 16px; font-weight: 500; color: var(--primary-text-color); }
        .chip { font-size: 11px; text-transform: uppercase; letter-spacing: .04em; padding: 2px 8px; border-radius: 10px; }
        .chip.error { color: var(--error-color, #db4437); border: 1px solid currentColor; }
        .chip.stale { color: var(--warning-color, #ffa600); border: 1px solid currentColor; }
        .gauges { display: flex; gap: 8px; justify-content: space-around; }
        .gauge { flex: 1 1 0; min-width: 0; max-width: 220px; text-align: center; }
        svg { width: 100%; display: block; }
        .track { fill: none; stroke: var(--primary-background-color, #111); stroke-width: 10; }
        .value { fill: none; stroke-width: 10; transition: d .4s ease; }
        .pct { font-size: 15px; text-anchor: middle; fill: var(--primary-text-color); font-family: inherit; }
        .label { font-size: 14px; color: var(--primary-text-color); margin-top: 2px; }
        .reset { font-size: 12px; color: var(--secondary-text-color); min-height: 16px; }
        .empty { color: var(--secondary-text-color); padding: 12px 0; }
      </style>
      <ha-card>
        <div class="head"><span class="name">${esc(name)}</span>${chip}</div>
        ${body}
      </ha-card>`;
    this.shadowRoot.querySelector("ha-card").onclick = () => {
      this.dispatchEvent(new CustomEvent("hass-more-info", { bubbles: true, composed: true, detail: { entityId: this._config.entity } }));
    };
  }
}

if (!customElements.get("ai-usage-card")) {
  customElements.define("ai-usage-card", AiUsageCard);
  window.customCards = window.customCards || [];
  window.customCards.push({ type: "ai-usage-card", name: "AI Usage", description: "Current + weekly AI usage in one card" });
  console.info(`%c AI-USAGE-CARD %c ${CARD_VERSION} `, "background:#cba6f7;color:#1e1e2e", "");
}
