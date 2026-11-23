// AI Usage — Scriptable widget (iOS)
// Reads /usage.json from the Home Dashboard add-on.
// First run inside the Scriptable app asks for the server URL and read token
// and stores them in the iOS Keychain (nothing secret lives in this file).
//
// Widget parameter (optional): "small" shows only the top 3 rows.

const KEY_URL = "ai_usage_url";
const KEY_TOKEN = "ai_usage_token";

async function ask(title, message, placeholder, current) {
  const a = new Alert();
  a.title = title;
  a.message = message;
  a.addTextField(placeholder, current || "");
  a.addAction("Save");
  a.addCancelAction("Cancel");
  if ((await a.present()) === -1) return null;
  return a.textFieldValue(0).trim();
}

async function setup() {
  const url = await ask("Server", "e.g. http://homeassistant.tailnet-name.ts.net:8787", "http://…:8787",
    Keychain.contains(KEY_URL) ? Keychain.get(KEY_URL) : "");
  if (!url) return false;
  const token = await ask("Read token", "From the add-on's Dashboard setup page", "read token", "");
  if (!token) return false;
  Keychain.set(KEY_URL, url.replace(/\/+$/, ""));
  Keychain.set(KEY_TOKEN, token);
  return true;
}

async function fetchUsage() {
  const req = new Request(`${Keychain.get(KEY_URL)}/usage.json`);
  req.headers = { Authorization: `Bearer ${Keychain.get(KEY_TOKEN)}` };
  req.timeoutInterval = 15;
  return await req.loadJSON();
}

const LABELS = { copilot: "Copilot", claude: "Claude", chatgpt: "ChatGPT", gemini: "Gemini", grok: "Grok" };
const C = {
  bg: Color.dynamic(new Color("#eff1f5"), new Color("#1e1e2e")),
  track: Color.dynamic(new Color("#ccd0da"), new Color("#45475a")),
  text: Color.dynamic(new Color("#4c4f69"), new Color("#cdd6f4")),
  sub: Color.dynamic(new Color("#6c6f85"), new Color("#a6adc8")),
  lo: Color.dynamic(new Color("#40a02b"), new Color("#a6e3a1")),
  mid: Color.dynamic(new Color("#df8e1d"), new Color("#f9e2af")),
  hi: Color.dynamic(new Color("#d20f39"), new Color("#f38ba8")),
};

function resetText(iso) {
  if (!iso) return "";
  const h = Math.max(0, Math.round((new Date(iso) - new Date()) / 3.6e6));
  return h < 48 ? `${h}h` : `${Math.round(h / 24)}d`;
}

function bar(pct, width) {
  const ctx = new DrawContext();
  ctx.size = new Size(width, 6);
  ctx.opaque = false;
  ctx.respectScreenScale = true;
  const track = new Path();
  track.addRoundedRect(new Rect(0, 0, width, 6), 3, 3);
  ctx.addPath(track); ctx.setFillColor(C.track); ctx.fillPath();
  if (pct != null) {
    const w = Math.max(6, Math.min(1, pct / 100) * width);
    const fill = new Path();
    fill.addRoundedRect(new Rect(0, 0, w, 6), 3, 3);
    ctx.addPath(fill);
    ctx.setFillColor(pct >= 85 ? C.hi : pct >= 60 ? C.mid : C.lo);
    ctx.fillPath();
  }
  return ctx.getImage();
}

function build(data, error) {
  const w = new ListWidget();
  w.backgroundColor = C.bg;
  w.setPadding(12, 14, 12, 14);
  w.refreshAfterDate = new Date(Date.now() + 15 * 60 * 1000);
  const title = w.addText("AI usage");
  title.font = Font.boldSystemFont(13); title.textColor = C.text;
  w.addSpacer(6);
  if (error) {
    const t = w.addText(error); t.font = Font.systemFont(11); t.textColor = C.hi;
    return w;
  }
  const small = config.widgetFamily === "small" || args.widgetParameter === "small";
  const rows = small ? data.rows.slice(0, 3) : data.rows;
  const width = small ? 120 : 290;
  for (const r of rows) {
    const line = w.addStack();
    line.centerAlignContent();
    const name = line.addText(LABELS[r.service] || r.service);
    name.font = Font.mediumSystemFont(11); name.textColor = C.text;
    line.addSpacer();
    const pct = line.addText(r.pct_used == null ? "—" : `${Math.round(r.pct_used)}%`);
    pct.font = Font.boldSystemFont(11);
    pct.textColor = r.status === "error" ? C.hi : r.status === "stale" ? C.mid : C.text;
    const rt = resetText(r.resets_at);
    if (rt && !small) { line.addSpacer(6); const s = line.addText(`↻ ${rt}`); s.font = Font.systemFont(10); s.textColor = C.sub; }
    w.addSpacer(2);
    w.addImage(bar(r.pct_used, width)).imageSize = new Size(width, 6);
    w.addSpacer(5);
  }
  return w;
}

let widget;
if (!Keychain.contains(KEY_URL) || !Keychain.contains(KEY_TOKEN)) {
  if (config.runsInApp && (await setup())) {
    widget = build(await fetchUsage());
  } else {
    widget = build(null, "Open in Scriptable to set up.");
  }
} else {
  try {
    widget = build(await fetchUsage());
  } catch (e) {
    widget = build(null, "Can't reach server (Tailscale on?)");
  }
}

if (config.runsInWidget) {
  Script.setWidget(widget);
} else if (config.runsInApp) {
  const menu = new Alert();
  menu.title = "AI usage";
  menu.addAction("Preview widget");
  menu.addAction("Change server / token");
  menu.addCancelAction("Done");
  const choice = await menu.present();
  if (choice === 0) await widget.presentMedium();
  if (choice === 1) await setup();
}
Script.complete();
