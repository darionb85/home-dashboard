# Home Dashboard

A clean, local-only home dashboard built on **Home Assistant**. It covers calendar, weather, thermostat, battery, Tesla, cameras, grow tent, router, smart plugs and AI usage. A small add-on builds the dashboard for you by finding your devices. Friends and family install the same thing and sign in with their own accounts.

```
Proxmox ──► Home Assistant OS (VM)
              ├─ integrations: Google Calendar, Sensi, EcoFlow, Tesla, TP-Link/Tapo,
              │                Ring, Blink, Vivosun, GL.iNet
              ├─ Catppuccin theme (Marketplace)
              ├─ Tailscale add-on  ─► reach it from your phone anywhere
              └─ Home Dashboard add-on (this repo)
                   ├─ "Dashboard setup" page: finds devices → builds the Home dashboard
                   └─ :8787 /usage.json + PWA ─► Scriptable (iOS) / KWGT (Android)
```

## Today's setup, in order (about 1–2 hours)

| # | Step | Guide |
|---|---|---|
| 1 | Create the Home Assistant VM on Proxmox | [docs/install.md](docs/install.md#1-home-assistant-on-proxmox) |
| 2 | Open the Marketplace (built-in HACS), install the Catppuccin theme and Tailscale | [docs/install.md](docs/install.md#2-marketplace-theme-tailscale) |
| 3 | Add your devices, easiest first | [docs/integrations.md](docs/integrations.md) |
| 4 | Install this add-on, paste your GitHub token, press **Build dashboard** | [docs/install.md](docs/install.md#4-home-dashboard-add-on) |
| 5 | Phone widgets | [Scriptable](widgets/scriptable/ai-usage.js) · [KWGT](widgets/kwgt/SETUP.md) |

Adding a device later? Open **Dashboard setup** → **Build dashboard** again and its widget appears.

## Status per widget

| Widget | Source | State |
|---|---|---|
| Calendar, weather | Google Calendar, Met.no (built in) | ✅ today |
| Thermostat (Sensi 1F86U-42WF) | `iprak/sensi` (Marketplace, unofficial) | ✅ today |
| Network (GL.iNet Flint 3 / BE9300) | `glinet_router` (Marketplace, local) | ✅ today |
| Cameras: Tapo C211/C110/C101, Ring Doorbell 2 | TP-Link (built in) / Tapo Control, Ring (built in) | ✅ live |
| Cameras: Blink | Blink (built in) | ✅ snapshots only (no live view in HA) |
| Smart plugs: Tapo P125M, Kasa EP10 | TP-Link (built in) | ✅ today |
| Tesla Wall Connector | Tesla Wall Connector (built in, local) | ✅ today |
| EcoFlow Delta 3 Ultra Plus | EcoFlow Cloud (Marketplace), Bluetooth as backup | ⚠️ best effort |
| Vivosun GrowHub E42A | `vivosun_growhub` (Marketplace, unofficial) | ✅ today |
| AI usage | Copilot live (add-on); Claude + ChatGPT live via the [AI Usage Bridge](docs/ai-usage-live.md) in an [always-on browser](docs/always-on-browser.md); Grok by hand | ✅ |
| AI usage: Gemini | Bridge, once one capture is sent ([how](docs/ai-usage-live.md#what-i-need-from-you-gemini-and-any-site-that-breaks)) | 🕒 waiting on capture |
| Tesla solar + car | Tesla Fleet | 🕒 next build: [docs/tesla-fleet.md](docs/tesla-fleet.md) |
| iCloud Reminders/Notes | iOS Shortcut → HA | 🕒 later: [docs/icloud-shortcut.md](docs/icloud-shortcut.md) |

## Change the look

Widgets and layout are separate: a **template** only says which widgets go in which section, plus the theme. Pick another one in **Dashboard setup**, or drop your own YAML in `/share/home_dashboard/templates/`. See [docs/templates.md](docs/templates.md).

## Share with friends & family

Each household runs its own copy and signs in with its own accounts. Nothing of yours is in this repo. See [docs/sharing.md](docs/sharing.md).

## Security

- Everything runs on your network. Off-site access goes only through Tailscale, and no ports are opened on your router.
- Device passwords and tokens live inside Home Assistant (encrypted storage on the VM), never in this repo.
- The GitHub token is a fine-grained PAT with **Plan: read-only** and no repo access. It's stored as an add-on secret, used server-side only, and never logged.
- `/usage.json` needs a random read token. Editing rows happens only on the setup page, behind your Home Assistant login. Tokens can be rotated with one button.

## Repo layout

```
repository.yaml              Home Assistant add-on repository manifest
home_dashboard/              the add-on
  config.yaml, Dockerfile
  app/                       Python service (aiohttp)
    main.py                  servers, scheduler, routes
    copilot.py               GitHub AI-credit / premium-request usage
    builder.py               device discovery + template rendering
    dashboard/discovery.yaml how each device's entities are found
    dashboard/widgets/       one file per widget (never changes per look)
    dashboard/templates/     layouts + theme (swap freely)
    static/                  PWA + setup page
  tests/                     pytest: JSON shape, Copilot parser (mocked), builder, API
widgets/                     Scriptable (iOS) + KWGT (Android)
bridge/                      Chrome extension: live Claude/ChatGPT usage → add-on /ingest
browser/                     always-on Chromium (Proxmox LXC + Docker) that runs the bridge 24/7
docs/                        install, integrations, templates, Tesla, iCloud, sharing
design/                      Step 2 Claude live row (design only)
```

Run the tests: `cd home_dashboard && pip install -r requirements.txt pytest pytest-aiohttp && pytest` and `node --test bridge/test/parsers.test.mjs`
