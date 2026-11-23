# Home Dashboard

Builds your **Home** dashboard from the devices you've added, and serves AI-usage data for phone widgets.

## Use
1. Configuration tab → set `github_username` and `github_pat` (fine-grained token, **Plan: Read-only** only). Save → Start.
2. Sidebar → **Dashboard setup** → **Build dashboard**.
3. Phone widgets: copy the **read token** from Dashboard setup.

## Options
| Option | Meaning |
|---|---|
| `github_username` / `github_pat` | Copilot usage (official GitHub API). Never logged. |
| `copilot_allowance` | Monthly AI credits for your plan (Student: 200). |
| `refresh_minutes` | How often Copilot refreshes (default 30). |
| `template` | Layout used on start-up builds (`catppuccin`, `minimal`, or yours in `/share/home_dashboard/templates`). |
| `auto_build` | Rebuild the dashboard each time the add-on starts. |
| `entity_overrides` | `key=entity_id` lines to fix or hide (`key=-`) a widget. |

## Ports
- `8787`: `/usage.json` and the AI-usage PWA. Needs the read token. Reach it on your LAN or over Tailscale only; don't forward it on your router.

Full docs: <https://github.com/darionb85/home-dashboard>
