// AI Usage Bridge: every 15 min (while Chrome is open) read usage with your existing
// logins and POST only {service, pct_used, resets_at, details} to the add-on.
// Session cookies and tokens never leave the browser and are never logged or stored.
import { pickClaudeOrg, parseClaudeUsage, parseChatgptSession, parseChatgptUsage } from "./parsers.js";

const PERIOD_MIN = 15;
const TIMEOUT_MS = 20000;

async function getJSON(url, init = {}) {
  const r = await fetch(url, { credentials: "include", cache: "no-store", signal: AbortSignal.timeout(TIMEOUT_MS), ...init });
  if (r.status === 401 || r.status === 403) throw new Error(`${new URL(url).host}: signed out or blocked (HTTP ${r.status}). Open the site once and log in.`);
  if (!r.ok) throw new Error(`${new URL(url).host}: HTTP ${r.status}`);
  return r.json();
}

const FETCHERS = {
  async claude() {
    const org = pickClaudeOrg(await getJSON("https://claude.ai/api/organizations"));
    return parseClaudeUsage(await getJSON(`https://claude.ai/api/organizations/${org}/usage`));
  },
  async chatgpt() {
    const s = parseChatgptSession(await getJSON("https://chatgpt.com/api/auth/session"));
    const headers = { Authorization: `Bearer ${s.accessToken}` };
    if (s.accountId) headers["ChatGPT-Account-Id"] = s.accountId;
    return parseChatgptUsage(await getJSON("https://chatgpt.com/backend-api/wham/usage", { headers }));
  },
  // gemini: added once its usage response has been captured (see docs/ai-usage-live.md)
};

async function post(server, token, payload) {
  const r = await fetch(`${server}/ingest`, {
    method: "POST",
    headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
    body: JSON.stringify(payload),
    signal: AbortSignal.timeout(TIMEOUT_MS),
  });
  if (r.status === 401) throw new Error("add-on rejected the write token");
  if (r.status === 429) return "rate limited (fine)";
  if (!r.ok) throw new Error(`add-on HTTP ${r.status}`);
  return "sent";
}

export async function runAll() {
  const cfg = await chrome.storage.local.get(["server", "token", "services"]);
  const results = {};
  if (!cfg.server || !cfg.token) return { error: "Set the server URL and write token first." };
  const services = cfg.services || { claude: true, chatgpt: true };
  for (const [name, fetcher] of Object.entries(FETCHERS)) {
    if (!services[name]) continue;
    let payload;
    try {
      payload = { service: name, ...(await fetcher()) };
    } catch (e) {
      payload = { service: name, error: String(e.message || e).slice(0, 120) };
    }
    try {
      results[name] = { ...(payload.error ? { error: payload.error } : { pct_used: payload.pct_used, resets_at: payload.resets_at }),
                        delivery: await post(cfg.server, cfg.token, payload) };
    } catch (e) {
      results[name] = { error: payload.error || null, delivery: `failed: ${e.message}` };
    }
  }
  await chrome.storage.local.set({ last: { at: new Date().toISOString(), results } });
  return { results };
}

function schedule() {
  chrome.alarms.create("ai-usage", { periodInMinutes: PERIOD_MIN, delayInMinutes: 1 });
}
chrome.runtime.onInstalled.addListener(schedule);
chrome.runtime.onStartup.addListener(schedule);
chrome.alarms.onAlarm.addListener((a) => { if (a.name === "ai-usage") runAll(); });
chrome.runtime.onMessage.addListener((msg, _sender, reply) => {
  if (msg && msg.type === "run") { runAll().then(reply); return true; }
});
