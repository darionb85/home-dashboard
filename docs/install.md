# Install

About 30–45 minutes, plus device setup.

> **Naming:** since Home Assistant 2026.2, *add-ons* are called **Apps** (Settings → Apps → App store). Same thing; older guides still say add-ons.

## 1. Home Assistant on Proxmox

1. Open the **Proxmox host shell** (Datacenter → your node → Shell) and run the community Home Assistant OS VM script:
   ```bash
   bash -c "$(curl -fsSL https://raw.githubusercontent.com/community-scripts/ProxmoxVE/main/vm/haos-vm.sh)"
   ```
   If that URL ever 404s, get the current one from <https://community-scripts.github.io/ProxmoxVE/> (search "Home Assistant OS").
2. Choose **Advanced** and set 2 vCPU, 4 GB RAM and a 32 GB disk on the **SSD** storage, not the 18 TB HDD. Defaults are fine otherwise.
3. When it boots, find the VM's IP (VM → Summary). On the **Flint 3** admin page (192.168.8.1 → Clients), give that IP a **static/reserved address** so it never moves.
4. Browse to `http://<vm-ip>:8123` and create your owner account. Each person in the house gets their own login later (Settings → People → Add person → *Allow login*). Everyone signs in with a username or email and password of their own.

## 2. HACS, theme, Tailscale

**Turn on Advanced mode:** click your name (bottom left) → *Advanced mode* on.

**File editor:** Settings → **Apps** → **App store** → **File editor** → Install → Start → *Show in sidebar*.

**HACS** (the community store; needed for Sensi, EcoFlow, Vivosun, GL.iNet and Catppuccin). Follow <https://hacs.xyz/docs/use/download/download/>. Summary:
1. Settings → **Apps** → **App store** → ⋮ → Repositories → add `https://github.com/hacs/addons` → install **Get HACS** → Start → read its log.
2. Restart Home Assistant (Settings → System → ⏻).
3. Settings → Devices & services → **Add integration** → *HACS* → tick the boxes → approve the GitHub device code it shows.

**Themes folder.** In File editor, open `configuration.yaml` and add at the bottom:
```yaml
frontend:
  themes: !include_dir_merge_named themes
```
Save, then restart.

**Catppuccin:** HACS → search *Catppuccin* → Download. Developer tools → Actions → run `frontend.reload_themes`. The dashboard sets the theme itself. To also theme the sidebar, pick it in your profile → *Theme*.

**Tailscale** (phone access away from home, no open ports):
1. Settings → **Apps** → **App store** → **Tailscale** → Install → Start → *Open web UI* → log in to your tailnet.
2. In the Tailscale admin console, note the machine name (usually `homeassistant`). From your phone with Tailscale on:
   - Dashboard: `http://homeassistant.<tailnet>.ts.net:8123`
   - AI usage PWA: `http://homeassistant.<tailnet>.ts.net:8787/?token=<read token>`
3. In the Home Assistant phone app, set the *Internal URL* to `http://<vm-ip>:8123` and the *External URL* to the Tailscale one.

## 3. Devices

Go through [integrations.md](integrations.md). Do the easy ones first. You don't need every device before building: build now and rebuild as you add more.

## 4. Home Dashboard add-on

1. **Make the repo installable.** Home Assistant can only install add-ons from a *public* Git URL. The repo contains no secrets, so the easy path is GitHub → `darionb85/home-dashboard` → Settings → *Change visibility → Public*.
   *Want it private?* Install the **Samba share** add-on instead, copy the `home_dashboard` folder into the `addons` share, then Settings → Apps → App store → ⋮ → *Check for updates*. It appears under **Local apps**.
2. Settings → **Apps** → **App store** → ⋮ → **Repositories** → add `https://github.com/darionb85/home-dashboard` → find **Home Dashboard** → Install. The first build takes a minute or two.
3. **Configuration** tab:
   - `github_username`: `darionb85`
   - `github_pat`: your fine-grained token (see below)
   - `copilot_allowance`: `200` (Copilot Student: 200 AI credits/month)
   - leave the rest; Save.
4. **Info** tab → Start, and turn on *Start on boot*, *Watchdog* and *Show in sidebar*.
5. Open **Dashboard setup** in the sidebar → **Build dashboard**. A **Home** dashboard appears in the sidebar. To make it the default: Settings → Dashboards → Home → ⋮ → *Set as default*.

### GitHub token (2 minutes; only you enter it)

1. <https://github.com/settings/personal-access-tokens/new>
2. Name `home-dashboard copilot usage`. Pick an expiration (90 days or 1 year; you'll paste a new one when it expires).
3. **Repository access:** *Public repositories* (read-only; it can't touch your repos).
4. **Account permissions → Plan → Read-only.** Nothing else.
5. Generate, copy, and paste it into the add-on's `github_pat` field. Don't paste it anywhere else.

The Copilot row turns **ok** within a minute. If it shows **error**, open the add-on's **Log** tab. The log shows the HTTP status, never the token.

### Manual AI rows

On **Dashboard setup**, type the % used and reset time for Claude, ChatGPT, Gemini and Grok (each row links to that service's usage page) and press Save.

## Updating

When the repo changes, open Settings → Apps → App store → ⋮ → *Check for updates* → Update. Your options, tokens and AI rows are kept.
