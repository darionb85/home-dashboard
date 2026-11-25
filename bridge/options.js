const $ = (id) => document.getElementById(id);

function show(last) {
  if (!last) return;
  if (last.error) { $("out").textContent = last.error; return; }
  const lines = [`Last run: ${new Date(last.at || Date.now()).toLocaleString()}`];
  for (const [name, r] of Object.entries(last.results || {})) {
    lines.push(r.error ? `${name}: ✗ ${r.error} (${r.delivery})` : `${name}: ${r.pct_used}% → ${r.delivery}`);
  }
  $("out").textContent = lines.join("\n");
}

async function load() {
  const c = await chrome.storage.local.get(["server", "token", "services", "last"]);
  $("server").value = c.server || "";
  $("token").value = c.token || "";
  const s = c.services || { claude: true, chatgpt: true, gemini: true };
  $("svc-claude").checked = !!s.claude;
  $("svc-chatgpt").checked = !!s.chatgpt;
  $("svc-gemini").checked = s.gemini !== false;
  show(c.last);
}

$("save").onclick = async () => {
  let server = $("server").value.trim().replace(/\/+$/, "");
  try { new URL(server); } catch { $("out").textContent = "Address must look like http://host:8787"; return; }
  const origin = new URL(server).origin + "/*";
  const granted = await chrome.permissions.request({ origins: [origin] });
  if (!granted) { $("out").textContent = "Chrome needs permission to reach your add-on."; return; }
  await chrome.storage.local.set({
    server,
    token: $("token").value.trim(),
    services: { claude: $("svc-claude").checked, chatgpt: $("svc-chatgpt").checked, gemini: $("svc-gemini").checked },
  });
  $("out").textContent = "Saved. Press “Send now” to test.";
};

$("run").onclick = async () => {
  $("out").textContent = "Sending…";
  const res = await chrome.runtime.sendMessage({ type: "run" });
  show(res.error ? res : { at: new Date().toISOString(), results: res.results });
};

$("gemtext").onclick = async () => {
  $("out").textContent = "Opening gemini.google.com/usage…";
  const res = await chrome.runtime.sendMessage({ type: "gemini-text" });
  if (res.error) { $("out").textContent = res.error; return; }
  try { await navigator.clipboard.writeText(res.text); $("out").textContent = "Copied. Paste it to Claude."; }
  catch { $("out").textContent = res.text; }
};

load();
