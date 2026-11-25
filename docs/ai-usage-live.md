# Live Claude, ChatGPT (and soon Gemini) usage

> ⚠️ **Unofficial.** None of these services offer a public "usage %" API for consumer plans. The bridge reads the same data their own usage pages load: claude.ai/settings/usage and chatgpt.com/codex/settings/usage. A site change can break a row. The row then shows **error** with the reason, and the old number stays until the next good update.

## How it works

```
Chrome on your computer (already logged in to claude.ai / chatgpt.com)
  └─ AI Usage Bridge extension, every 15 min while Chrome is open
       1. asks claude.ai / chatgpt.com for your usage, using your existing login
       2. keeps only: % used, reset time, and the other window's % (session vs weekly)
       3. POST → http://<home assistant>:8787/ingest   (write token)
Home Dashboard add-on → sensor.ai_usage_claude / _chatgpt → gauges + phone widgets
```

- Your cookies and login tokens **never leave Chrome**, and nothing logs them. The add-on only ever sees numbers.
- The headline % is your **tightest** limit (session or weekly, whichever is higher). The other one is an attribute on the sensor (`session_pct`, `weekly_pct`, plus `plan` for ChatGPT).
- If Chrome is closed for a while, the row turns **stale**. It turns **ok** again on the next run.

> **Recommended:** run the bridge in the [always-on browser](always-on-browser.md) on your Proxmox server so it works when your computer is off. The steps below are for running it in your everyday Chrome instead.

## Install in your own Chrome (5 minutes)

1. Download this repo: GitHub → **Code → Download ZIP**, and unzip it. Or use `ai-usage-bridge.zip` from the chat.
2. Chrome → `chrome://extensions` → turn on **Developer mode** (top right) → **Load unpacked** → choose the **`bridge`** folder.
3. Pin it (puzzle icon → pin), then click its icon:
   - **Add-on address:** `http://homeassistant.<tailnet>.ts.net:8787` (or `http://<vm-ip>:8787` at home)
   - **Write token:** copy it from **Dashboard setup → Phone widgets → Write token**
   - **Save.** Chrome asks for permission to reach that address. Allow it.
4. Make sure you're logged in to **claude.ai** and **chatgpt.com** in this same Chrome profile.
5. Press **Send now**. You should see something like:
   ```
   claude: 64% → sent
   chatgpt: 41% → sent
   ```
6. In Home Assistant, update the add-on to **0.2.0** (Settings → Apps → Home Dashboard → Update), then **Dashboard setup → Build dashboard**. The gauges appear. Rows with no number yet stay hidden instead of showing "Entity is non-numeric".

Use the Chrome on a computer that's on most of the day. Each computer that runs it needs the extension and the same write token.

## If something shows ✗

Copy the text from the extension popup and send it to me. It contains no secrets. Common ones:

| Message | Fix |
|---|---|
| `signed out or blocked (HTTP 401/403)` | Open that site in this Chrome profile and log in. If you're already logged in, send me the message. |
| `add-on rejected the write token` | You pasted the read token, or rotated tokens. Copy the **write** token again. |
| `add-on HTTP …` / `failed: …` | Wrong address, Tailscale off, or the add-on isn't running. |
| `no rate_limit in ChatGPT response` / `no usage windows` | The site changed its format. Do the capture below for that site. |

## What I need from you: Gemini (and any site that breaks)

Gemini's usage page loads its numbers through Google's internal `batchexecute` calls, and I can't see those without your account. Capture **one** response and send it here. It takes about 3 minutes.

1. Chrome → **gemini.google.com** → open the screen that shows your usage % / reset time.
2. Press **F12** → **Network** tab → tick **Preserve log** → type `batchexecute` in the filter box.
3. Close and reopen the usage screen, or reload the page and open it again, so new rows appear.
4. Click each `batchexecute` row → **Response** tab → press **Ctrl/Cmd+F** and search for the % number shown on screen (e.g. `37`).
5. On the row that contains it, send me **three things**:
   - **Response:** right-click the row → *Copy → Copy response* → paste into a `.txt` file.
   - **RPC id:** on the **Headers** tab, the Request URL contains `rpcids=XXXXXX`. Send only that value.
   - **Request:** on the **Payload** tab, copy only the value of **`f.req`**.
6. Also send a **screenshot** of the usage screen so I can match each number to its label.

**Never send:** anything from *Request Headers* (especially `Cookie`), the `at=` value from Payload, `f.sid`, or a `.har` export. Those can contain your login.

For ChatGPT or Claude, if a format change breaks them, the same steps work. On chatgpt.com, filter for `wham/usage`. On claude.ai, filter for `usage`. Copy the **Response** only.
