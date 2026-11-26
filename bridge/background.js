// AI Usage Bridge: every 15 min (while Chrome is open) read usage with your existing
// logins and POST only {service, pct_used, resets_at, details} to the add-on.
// Session cookies and tokens never leave the browser and are never logged or stored.
import { pickClaudeOrg, parseClaudeUsage, parseChatgptSession, parseChatgptUsage, parseGeminiText, parseGrokUsageText } from "./parsers.js";
import { grokUsagePageText } from "./grok-page.js";

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
  async gemini() {
    return parseGeminiText(await readGeminiUsagePage());
  },
  async grok() {
    return parseGrokUsageText(await readGrokUsagePage());
  },
};

// Grok's weekly pool lives in Settings -> Usage (a window inside grok.com), so open grok.com
// in a background tab, let grok-page.js click through to Usage, read the text, close the tab.
export async function readGrokUsagePage() {
  const tab = await chrome.tabs.create({ url: "https://grok.com/", active: false });
  try {
    for (let i = 0; i < 20; i++) {
      await sleep(1000);
      const t = await chrome.tabs.get(tab.id);
      if (t.url && /(accounts\.x\.ai|x\.com\/i\/flow\/login|\/sign-?in)/.test(t.url)) throw new Error("grok.com: signed out. Open it once and log in.");
      if (t.status === "complete") break;
    }
    const [res] = await chrome.scripting.executeScript({ target: { tabId: tab.id }, func: grokUsagePageText });
    const text = (res && res.result) || "";
    if (!text) throw new Error("grok.com didn't load");
    return text;
  } finally {
    chrome.tabs.remove(tab.id).catch(() => {});
  }
}

// Unpacked extensions don't reload themselves when their files change on disk.
// The always-on browser's sync container refreshes the files hourly; this picks them up.
async function selfUpdate() {
  try {
    const r = await fetch(chrome.runtime.getURL("manifest.json"), { cache: "no-store" });
    const disk = (await r.json()).version;
    if (disk && disk !== chrome.runtime.getManifest().version) chrome.runtime.reload();
  } catch (_) {}
}

// Gemini has no JSON endpoint we can call, so open its usage page in a background
// tab, wait for it to render, read the visible text, and close the tab.
const GEMINI_USAGE_URL = "https://gemini.google.com/usage";
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

export async function readGeminiUsagePage() {
  const tab = await chrome.tabs.create({ url: GEMINI_USAGE_URL, active: false });
  try {
    let text = "";
    for (let i = 0; i < 20; i++) {           // up to ~30 s
      await sleep(1500);
      const t = await chrome.tabs.get(tab.id);
      if (t.url && /accounts\.google\.com/.test(t.url)) throw new Error("gemini.google.com: signed out. Open it once and log in.");
      if (t.status !== "complete") continue;
      try {
        const [res] = await chrome.scripting.executeScript({ target: { tabId: tab.id }, func: () => document.body ? document.body.innerText : "" });
        text = (res && res.result) || "";
      } catch (_) { continue; }
      if (/%/.test(text) && /(current\s+usage|weekly)/i.test(text)) break;
    }
    if (!text) throw new Error("gemini.google.com/usage didn't load");
    return text;
  } finally {
    chrome.tabs.remove(tab.id).catch(() => {});
  }
}

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
  const services = { claude: true, chatgpt: true, gemini: true, grok: true, ...(cfg.services || {}) };
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
chrome.alarms.onAlarm.addListener(async (a) => {
  if (a.name !== "ai-usage") return;
  await runAll();
  await selfUpdate();
});
chrome.runtime.onMessage.addListener((msg, _sender, reply) => {
  if (msg && msg.type === "run") { runAll().then(reply); return true; }
  if (msg && msg.type === "grok-text") {
    readGrokUsagePage().then((text) => reply({ text }), (e) => reply({ error: String(e.message || e) }));
    return true;
  }
  if (msg && msg.type === "gemini-text") {
    readGeminiUsagePage().then((text) => reply({ text }), (e) => reply({ error: String(e.message || e) }));
    return true;
  }
});
