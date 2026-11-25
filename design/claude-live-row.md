> **Superseded (v0.2.0):** Claude is now live through the Chrome [AI Usage Bridge](../docs/ai-usage-live.md), which needs no Mac job and covers ChatGPT too. This launchd design stays as an option for a Mac that's always on without Chrome open.

# Step 2: live Claude row (DESIGN ONLY, not built)

> ⚠️ **Unofficial.** `GET https://api.anthropic.com/api/oauth/usage` is an undocumented endpoint used by Claude Code. Anthropic can change or remove it without notice. If it breaks, the Claude row falls back to **stale**, then back to manual entry. It only reads *your own* usage with *your own* sign-in, on *your own* Mac.

## Flow

```
Mac (launchd, every 15 min)
  1. read Claude Code's sign-in from the macOS Keychain
       security find-generic-password -s "Claude Code-credentials" -w   → JSON
       → .claudeAiOauth.accessToken      (kept in memory only)
  2. GET https://api.anthropic.com/api/oauth/usage
       Authorization: Bearer <access token>
       anthropic-beta: oauth-2025-04-20
     → { five_hour: {utilization, resets_at}, seven_day: {utilization, resets_at}, … }
  3. pick the tighter window (five_hour unless seven_day is higher)
  4. POST http://homeassistant.<tailnet>.ts.net:8787/ingest/claude
       Authorization: Bearer <WRITE token>
       {pct_used, resets_at}
add-on
  5. validate → store row {service: claude, status: ok, …} → push sensor
  6. if no ingest for 45 min → status "stale"
```

## Pieces to build when approved
- **Add-on:** `POST /ingest/{service}` (write-token only, constant-time compare, schema-validated, 1 req/10 s) and a `live_ingest` flag per row so the scheduler marks it stale instead of manual.
- **Mac:** `claude-usage-push.sh` (bash + `curl` + `/usr/bin/python3` for JSON; no extra installs), installed to `~/Library/Application Support/home-dashboard/`. The write token goes in the **Keychain** (`security add-generic-password -s home-dashboard-write`), never in the plist or the script.
- `~/Library/LaunchAgents/com.darionb85.claude-usage.plist`: `StartInterval` 900, `RunAtLoad` true, logs to `~/Library/Logs/claude-usage.log` (status codes only, never tokens).
- Token expiry: if the API returns 401, the job skips this run. Claude Code refreshes the token the next time you use it. The job never refreshes tokens itself.

## Commands (one each)

Install (prompts for the server URL and write token, stores the token in Keychain, loads the agent):
```bash
curl -fsSL https://raw.githubusercontent.com/darionb85/home-dashboard/main/mac/install.sh | bash
```

Uninstall (unloads the agent, deletes the script, the plist, the log and the Keychain item):
```bash
curl -fsSL https://raw.githubusercontent.com/darionb85/home-dashboard/main/mac/uninstall.sh | bash
```

(Requires the repo to be public. If it stays private, the same two scripts run from a local clone: `./mac/install.sh` and `./mac/uninstall.sh`.)

## Risks
- Endpoint or response shape changes → the parser rejects it, logs the HTTP status, and the row goes stale.
- The Keychain prompt appears the first time launchd reads the Claude Code item. Click **Always Allow**.
- The Mac must be awake with Tailscale connected. Otherwise the row goes stale, which is expected.
