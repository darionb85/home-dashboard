// Pure parsers: response JSON -> {pct_used, resets_at, details}. No network, no tokens.
// Each picks the tightest window (highest %) as the headline number and keeps
// the others as details (shown as attributes on the Home Assistant sensor).

export class ParseError extends Error {}

const num = (v) => (typeof v === "number" && Number.isFinite(v) ? v : null);
const isoFromUnix = (s) => (num(s) != null ? new Date(s * 1000).toISOString() : null);

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
  const details = { window: top.label };
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
  const details = { window: top.label };
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
