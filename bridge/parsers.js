// Pure parsers: response JSON -> {pct_used, resets_at, details}. No network, no tokens.
// Each picks the tightest window (highest %) as the headline number and keeps
// the others as details (shown as attributes on the Home Assistant sensor).

export class ParseError extends Error {}

const num = (v) => (typeof v === "number" && Number.isFinite(v) ? v : null);
const isoFromUnix = (s) => (num(s) != null ? new Date(s * 1000).toISOString() : null);

// names of the fields a site returned (no values), shown on the setup page to debug format changes
function fieldNames(obj) {
  return Object.keys(obj || {}).filter((k) => obj[k] !== null).join(",").slice(0, 100);
}

function headline(windows) {
  const usable = windows.filter((w) => w.pct != null);
  if (!usable.length) throw new ParseError("no usage windows in response");
  return usable.reduce((a, b) => (b.pct > a.pct ? b : a));
}

// ---------- Claude (claude.ai/settings/usage) ----------
// GET https://claude.ai/api/organizations  -> [{uuid, capabilities: [...]}, ...]
export function pickClaudeOrg(orgs) {
  if (!Array.isArray(orgs) || !orgs.length) throw new ParseError("no Claude organizations (signed in?)");
  const chat = orgs.find((o) => Array.isArray(o.capabilities) && o.capabilities.includes("chat"));
  const org = chat || orgs[0];
  if (!org.uuid) throw new ParseError("organization has no uuid");
  return org.uuid;
}

// GET https://claude.ai/api/organizations/{uuid}/usage
// -> {five_hour: {utilization, resets_at}, seven_day: {...}, seven_day_opus: {...}, ...}
export function parseClaudeUsage(data) {
  if (!data || typeof data !== "object") throw new ParseError("unexpected Claude response");
  const w = (key, label) => ({
    label,
    pct: num(data[key]?.utilization),
    resets_at: data[key]?.resets_at || null,
  });
  const windows = [w("five_hour", "session"), w("seven_day", "weekly")];
  const top = headline(windows);
  const details = { window: top.label, fields: fieldNames(data) };
  for (const x of windows) {
    if (x.pct != null) {
      details[`${x.label}_pct`] = x.pct;
      details[`${x.label}_resets_at`] = x.resets_at;
    }
  }
  for (const [key, label] of [["seven_day_opus", "weekly_opus_pct"], ["seven_day_sonnet", "weekly_sonnet_pct"]]) {
    const p = num(data[key]?.utilization);
    if (p != null) details[label] = p;
  }
  return { pct_used: top.pct, resets_at: top.resets_at, details };
}

// ---------- ChatGPT / Codex (chatgpt.com/codex/settings/usage) ----------
// GET https://chatgpt.com/api/auth/session -> {accessToken, account: {id}}
export function parseChatgptSession(data) {
  const token = data && data.accessToken;
  if (!token) throw new ParseError("not signed in to chatgpt.com");
  return { accessToken: token, accountId: data.account?.id || null };
}

// GET https://chatgpt.com/backend-api/wham/usage
// -> {plan_type, rate_limit: {primary_window: {used_percent, reset_at, reset_after_seconds, limit_window_seconds}, secondary_window: {...}}}
export function parseChatgptUsage(data, nowMs = Date.now()) {
  const rl = data && data.rate_limit;
  if (!rl || typeof rl !== "object") throw new ParseError("no rate_limit in ChatGPT response");
  const w = (win, fallback) => {
    if (!win) return { label: fallback, pct: null, resets_at: null };
    const secs = num(win.limit_window_seconds);
    const label = secs == null ? fallback : secs <= 6 * 3600 ? "session" : "weekly";
    let resets = isoFromUnix(win.reset_at);
    if (!resets && num(win.reset_after_seconds) != null) resets = new Date(nowMs + win.reset_after_seconds * 1000).toISOString();
    return { label, pct: num(win.used_percent), resets_at: resets };
  };
  const windows = [w(rl.primary_window, "session"), w(rl.secondary_window, "weekly")];
  const top = headline(windows);
  const details = { window: top.label, fields: fieldNames(rl) };
  if (data.plan_type) details.plan = String(data.plan_type);
  if (typeof rl.limit_reached === "boolean") details.limit_reached = rl.limit_reached;
  for (const x of windows) {
    if (x.pct != null) {
      details[`${x.label}_pct`] = x.pct;
      details[`${x.label}_resets_at`] = x.resets_at;
    }
  }
  return { pct_used: top.pct, resets_at: top.resets_at, details };
}

// ---------- Gemini (gemini.google.com/usage) ----------
// No public JSON; we read the page's visible text, e.g.
//   "Current usage  37% used  Resets in 2 hr 10 min   Weekly limit  12% used  Resets Fri, Nov 28, 9:00 AM"
const UNIT_MS = { d: 864e5, day: 864e5, days: 864e5, h: 36e5, hr: 36e5, hrs: 36e5, hour: 36e5, hours: 36e5,
                  m: 6e4, min: 6e4, mins: 6e4, minute: 6e4, minutes: 6e4 };
const WEEKDAYS = ["sun", "mon", "tue", "wed", "thu", "fri", "sat"];

export function parseResetPhrase(phrase, now = new Date()) {
  if (!phrase) return null;
  const p = phrase.trim().replace(/[.,;]+$/, "");
  // "in 2 hr 10 min" / "in 3 days" / "2h 10m"
  const parts = [...p.matchAll(/(\d+(?:\.\d+)?)\s*(days?|d|hours?|hrs?|h|minutes?|mins?|m)\b/gi)];
  if (parts.length && /^(in\s+)?\d/i.test(p)) {
    const ms = parts.reduce((t, [, n, u]) => t + parseFloat(n) * (UNIT_MS[u.toLowerCase()] || 0), 0);
    if (ms > 0) return new Date(now.getTime() + ms).toISOString();
  }
  if (/^tomorrow/i.test(p)) {
    const t = p.match(/(\d{1,2})(?::(\d{2}))?\s*(am|pm)/i);
    const d = new Date(now); d.setDate(d.getDate() + 1);
    if (t) d.setHours((+t[1] % 12) + (/pm/i.test(t[3]) ? 12 : 0), +(t[2] || 0), 0, 0);
    return d.toISOString();
  }
  // "Friday at 9:00 AM" / "Fri 9 AM"
  const wd = p.match(/^(on\s+)?(sun|mon|tue|wed|thu|fri|sat)[a-z]*\b(?![,\s]+[a-z]{3}\s+\d)/i);
  if (wd) {
    const target = WEEKDAYS.indexOf(wd[2].toLowerCase());
    const d = new Date(now);
    let add = (target - d.getDay() + 7) % 7;
    const t = p.match(/(\d{1,2})(?::(\d{2}))?\s*(am|pm)/i);
    d.setDate(d.getDate() + add);
    if (t) d.setHours((+t[1] % 12) + (/pm/i.test(t[3]) ? 12 : 0), +(t[2] || 0), 0, 0);
    if (d <= now) d.setDate(d.getDate() + 7);
    return d.toISOString();
  }
  // "Nov 28, 9:00 AM" / "Fri, Nov 28 at 9:00 AM" / "November 28"
  const cleaned = p.replace(/^(on|at)\s+/i, "").replace(/^(sun|mon|tue|wed|thu|fri|sat)[a-z]*,?\s+/i, "").replace(/\s+at\s+/i, " ");
  const m = cleaned.match(/^([A-Za-z]{3,9})\s+(\d{1,2})(?:,?\s+(\d{4}))?(?:,?\s+(\d{1,2}(?::\d{2})?\s*(?:am|pm)))?/i);
  if (m) {
    const year = m[3] || now.getFullYear();
    let d = new Date(`${m[1]} ${m[2]} ${year} ${m[4] || "12:00 AM"}`);
    if (!isNaN(d)) {
      if (!m[3] && d < now - 864e5) d = new Date(`${m[1]} ${m[2]} ${+year + 1} ${m[4] || "12:00 AM"}`);
      return d.toISOString();
    }
  }
  return null;
}

function geminiWindow(section, now) {
  if (!section) return { pct: null, resets_at: null, reset_text: null };
  const pm = section.match(/(\d{1,3}(?:\.\d+)?)\s*%\s*(used|left|remaining|available)?/i);
  let pct = pm ? parseFloat(pm[1]) : null;
  if (pct != null && pm[2] && /left|remaining|available/i.test(pm[2])) pct = Math.max(0, 100 - pct);
  const rm = section.match(/(?:resets?|refreshes?|renews?)\s+(?:on\s+|at\s+)?([^\n%]{2,60}?)(?=\s{2,}|\n|$|\s+(?:weekly|current)\b)/i);
  const reset_text = rm ? rm[1].trim() : null;
  return { pct, resets_at: parseResetPhrase(reset_text, now), reset_text };
}

export function parseGeminiText(text, now = new Date()) {
  if (!text || typeof text !== "string") throw new ParseError("empty Gemini page");
  if (/sign in|choose an account/i.test(text) && !/%/.test(text)) throw new ParseError("not signed in to gemini.google.com");
  const t = text.replace(/\r/g, "");
  const cur = t.search(/current\s+usage|5[- ]hour|five[- ]hour/i);
  const wk = t.search(/weekly\s+(limit|usage)/i);
  const slice = (start, other) => (start < 0 ? null : t.slice(start, other > start ? other : start + 400));
  const session = geminiWindow(slice(cur, wk), now);
  const weekly = geminiWindow(slice(wk, cur), now);
  const windows = [{ label: "session", ...session }, { label: "weekly", ...weekly }];
  const top = headline(windows);
  const details = { window: top.label };
  for (const w of windows) {
    if (w.pct != null) {
      details[`${w.label}_pct`] = w.pct;
      details[`${w.label}_resets_at`] = w.resets_at;
      if (!w.resets_at && w.reset_text) details[`${w.label}_reset_text`] = w.reset_text;
    }
  }
  return { pct_used: top.pct, resets_at: top.resets_at, details };
}

// ---------- Grok (grok.com Settings -> Usage) ----------
// Since mid-2026 paid Grok has one weekly pool (% used, weekly reset, optional
// Extra Usage Credits). There's no JSON we can call, so we read the Usage tab's text, e.g.
//   "Usage limits  Weekly usage  100% used  Resets Thursday at 9:00 AM ... Extra Usage Credits $4.20"
const GROK_PRODUCTS = /^(api|build|chat|imagine|voice|video|image|grok bot)\b/i;

export function parseGrokUsageText(text, now = new Date()) {
  if (!text || typeof text !== "string") throw new ParseError("empty Grok page");
  const t = text.replace(/\r/g, "");
  if (/(sign in|log in|create account)/i.test(t) && !/%/.test(t)) throw new ParseError("grok.com: signed out. Open it once and log in.");
  // the overall pool % is the first % after the weekly/usage heading that isn't a per-product line
  const start = Math.max(0, t.search(/weekly|usage limits?|usage/i));
  const lines = t.slice(start).split("\n").map((l) => l.trim()).filter(Boolean);
  let pct = null;
  for (let i = 0; i < lines.length && pct === null; i++) {
    const m = lines[i].match(/(\d{1,3}(?:\.\d+)?)\s*%\s*(used|left|remaining|available)?/i);
    if (!m) continue;
    const label = (lines[i].slice(0, m.index) || lines[i - 1] || "").trim();
    if (GROK_PRODUCTS.test(label)) continue;
    pct = parseFloat(m[1]);
    if (m[2] && /left|remaining|available/i.test(m[2])) pct = Math.max(0, 100 - pct);
  }
  if (pct === null) throw new ParseError("Grok usage page text not recognized (no weekly %)");
  const rm = t.match(/(?:resets?|renews?|refreshes)\s+(?:on\s+|at\s+)?([^\n%]{2,60})/i);
  const reset_text = rm ? rm[1].trim() : null;
  const resets_at = parseResetPhrase(reset_text, now);
  const details = { window: "weekly", weekly_pct: pct, weekly_resets_at: resets_at };
  if (!resets_at && reset_text) details.weekly_reset_text = reset_text;
  const cm = t.match(/(?:extra usage credits?|usage credits?|additional usage credits?|credits? balance)[^\n$]{0,40}?\n?\s*\$\s?(\d+(?:,\d{3})*(?:\.\d{1,2})?)/i)
        || t.match(/\$\s?(\d+(?:,\d{3})*(?:\.\d{1,2})?)\s*(?:in\s+)?(?:extra\s+)?(?:usage\s+)?credits?/i);
  if (cm) details.credits = `$${cm[1]}`;
  return { pct_used: pct, resets_at, details };
}
