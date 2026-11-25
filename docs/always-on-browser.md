# Always-on browser for live AI usage (no computer needed)

A Chromium browser runs 24/7 in a small container on your Proxmox server. You log in to Claude, ChatGPT and Gemini there once. The **AI Usage Bridge** extension runs inside it and sends usage numbers to Home Assistant every 15 minutes, whether your computer is on or not.

```
Proxmox
 ├─ VM  Home Assistant OS ── Home Dashboard add-on (:8787 /ingest)
 └─ LXC ai-usage-browser ── Docker ── Chromium (logged in) + AI Usage Bridge ──┘
           you view/log in at https://<lxc-ip>:3001
```

## 1. Create the LXC (5 min)

**Size:** 2 vCPU · 2 GB RAM · 512 MB swap · 12 GB disk on the **SSD** (local-lvm) · Debian 12 · unprivileged.

**Easiest:** in the Proxmox host shell, run the community Docker LXC script and pick **Advanced** to set the size above:
```bash
bash -c "$(curl -fsSL https://raw.githubusercontent.com/community-scripts/ProxmoxVE/main/ct/docker.sh)"
```
(If the URL 404s, find "Docker" at <https://community-scripts.github.io/ProxmoxVE/>.)

**Or by hand:** Create CT → Debian 12 template, the size above → when it's created, *Options → Features* → tick **nesting** and **keyctl** → start it.

Then on the Flint 3, reserve the LXC's IP like you did for the HA VM.

## 2. Install the browser in Portainer (3 min, no console needed)

The Docker LXC script also installs **Portainer**, at `https://<lxc-ip>:9443`. Do everything there.

> Don't use the **portainer** container's console (Containers → portainer → `>_`). That image has no shell, so **Connect** never works there, and you don't need it.

1. Portainer → **local** environment → **Stacks** → **+ Add stack**.
2. Name: `ai-usage-browser`. Build method: **Web editor**.
3. Paste the contents of [`browser/docker-compose.yml`](https://raw.githubusercontent.com/darionb85/home-dashboard/main/browser/docker-compose.yml) (open the link, select all, copy).
4. In the editor, find the line `- PASSWORD=CHANGE-ME` and replace **CHANGE-ME** with your own password (letters, numbers, `- _ . ! @` only). Leave the **Environment variables** section empty.
5. **Deploy the stack.** The first pull is about 1 GB, so allow a couple of minutes.
6. Check **Containers**: `ai-usage-browser` and `…bridge-sync…` should both be **running**. bridge-sync keeps the extension up to date by checking GitHub hourly.

Something wrong? Click the container → **Logs**, and paste the last lines to me.

## 3. Log in and connect (5 min)

1. On any computer at home, open `https://<lxc-ip>:3001`. Accept the certificate warning (it's self-signed), then sign in as `dashboard` with the password you put in the stack file. A full Chromium desktop appears in the tab.
2. In **that** Chromium, log in to **claude.ai**, **chatgpt.com** and **gemini.google.com**. Tick "stay signed in" wherever it's offered.
3. The browser opens on `chrome://extensions`. **AI Usage Bridge** should be listed. If it isn't: turn on **Developer mode** → **Load unpacked** → in the file picker press **Ctrl+L**, type `/bridge`, Enter → **Select**.
4. Click the puzzle icon → pin **AI Usage Bridge** → click it:
   - **Add-on address:** `http://<home-assistant-vm-ip>:8787`. Use the plain LAN IP, since Tailscale isn't needed inside your network.
   - **Write token:** from **Dashboard setup → Phone widgets → Write token**
   - **Save** → allow the permission prompt → **Send now**. You should see `claude: …% → sent` and `chatgpt: …% → sent`.
5. Close the browser **tab** on your computer. The browser keeps running on the server. Don't close the Chromium window *inside* the desktop. If you do by accident, restart the CT.

If you turn off your own computer, nothing changes. If the Proxmox host reboots, the container starts again with you still logged in.

## Upkeep

| When | Do |
|---|---|
| A row shows **error: signed out** | Open `https://<lxc-ip>:3001` and log in to that site again. Google is the one most likely to ask now and then. |
| I push a bridge update | Nothing. bridge-sync downloads it within an hour, and the extension reloads itself on its next run. To get it immediately: Portainer → Containers → `…bridge-sync…` → **Restart**, then ↻ on the extension in `chrome://extensions`. |
| You want to view it away from home | Not needed for it to work. If you want it, install Tailscale on the LXC from the Proxmox CT console (Proxmox → the CT → **Console**, not Portainer). |

## Security

- The browser profile (Docker volume `chromium-config`) **is your logins**. It stays on your server and isn't in Git. Back up the LXC with Proxmox backups, not by copying that folder anywhere.
- Port 3001 has a password, but it's only meant for your LAN. **Never port-forward it**: the user/password setting only turns on basic HTTP auth, which linuxserver.io says is suitable only for a trusted local network.
- The bridge sends only numbers to the add-on. Your cookies and tokens never leave that browser.
- To retire it: Portainer → Stacks → ai-usage-browser → **Delete** (and remove its volumes), delete the CT, and sign out of the sites' "active sessions" lists if you like.

## Resources

Expect about 1 GB RAM and near-idle CPU. Chromium wakes every 15 minutes for a few seconds.
