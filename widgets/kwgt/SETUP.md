# AI usage widget for Android (KWGT)

KWGT reads the same `/usage.json` with its `wg()` web-get function.

**You need:** KWGT (and KWGT Pro for importing/saving presets), the Tailscale app connected on the phone (or be on home Wi-Fi), and your **read token** from the add-on's *Dashboard setup* page.

## 1. Build the URL once

```
http://homeassistant.<your-tailnet>.ts.net:8787/usage.json?token=<READ_TOKEN>
```

Open it in Chrome on the phone first. You should see JSON. If you don't, fix that before touching KWGT.

> KWGT can't send headers, so the token rides in the URL. That's fine on your tailnet. Don't paste this URL anywhere public. If it leaks, press **Rotate tokens** on the setup page.

## 2. Create the widget

1. Long-press the home screen → Widgets → **KWGT** (4×2 works well). Tap it to open the editor.
2. Root → **Globals** → **+** → *Text* → name it `url` → paste the URL from step 1.
3. Add a **Stack Layout** (vertical). Inside it add one **Overlap Group** per AI service (5 total).
4. In each group, add:

| Item | Setting | Formula (row 0 = Copilot; use 1–4 for Claude, ChatGPT, Gemini, Grok) |
|---|---|---|
| Text (name) | Text | `$wg(gv(url), json, ".rows[0].service")$` |
| Text (percent) | Text | `$mu(round, wg(gv(url), json, ".rows[0].pct_used"))$%` |
| Text (reset) | Text | `↻ $tf(wg(gv(url), json, ".rows[0].resets_at"), "MMM d")$` (if this shows an odd date on your KWGT version, drop the `tf(…)` wrapper to show the raw ISO date) |
| Progress (Shape → *Progress*) | Level | `$wg(gv(url), json, ".rows[0].pct_used")$` with max `100` |
| Text (status, optional) | Text | `$wg(gv(url), json, ".rows[0].status")$` |

5. Progress color: Color → formula
   `$if(wg(gv(url), json, ".rows[0].pct_used") >= 85, #f38ba8, wg(gv(url), json, ".rows[0].pct_used") >= 60, #f9e2af, #a6e3a1)$`
   (These are Catppuccin Mocha's red, yellow and green.)
6. Row order is fixed: `copilot, claude, chatgpt, gemini, grok`.

## 3. Refresh

KWGT re-fetches web content on its own schedule. To control it: KWGT app → Settings → **Advanced → Update interval** (15 min is plenty; the server refreshes Copilot every 30 min). To force a refresh, add a Touch action → *Kustom Action → Refresh*. To refresh Copilot on the server too, open the PWA (`http://…:8787/?token=…`) and tap **Refresh**.

## Troubleshooting

- `$wg…$` shows nothing → Tailscale is off, or the token is wrong (open the URL in Chrome).
- Percent shows blank for Claude/ChatGPT/Gemini/Grok → you haven't set them yet; set them on the setup page (they're manual for now).
