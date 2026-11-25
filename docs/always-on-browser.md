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

## 2. Install the browser (2 min)

In the LXC's console (Proxmox → the CT → Console, log in as root):
```bash
bash -c "$(curl -fsSL https://raw.githubusercontent.com/darionb85/home-dashboard/main/browser/setup.sh)"
```
It installs Docker if needed, pulls this repo, creates a random password, and starts Chromium. At the end it prints the address. Get the password with:
```bash
cat /opt/ai-usage-browser/.env
```

## 3. Log in and connect (5 min)

1. On any computer at home, open `https://<lxc-ip>:3001`. Accept the certificate warning (it's self-signed), then sign in as user `dashboard` with the password from the `.env` file. A full Chromium desktop appears in the tab.
2. In **that** Chromium, log in to **claude.ai**, **chatgpt.com** and **gemini.google.com**. Tick "stay signed in" wherever it's offered.
3. Go to `chrome://extensions`. **AI Usage Bridge** should already be listed. If it isn't: turn on **Developer mode** → **Load unpacked** → type `/bridge` in the path box → **Select**.
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
| I push a bridge update | Re-run the setup command from step 2, then in that Chromium go to `chrome://extensions` → AI Usage Bridge → ↻ reload. |
| You want to view it away from home | Install Tailscale in the LXC (`curl -fsSL https://tailscale.com/install.sh \| sh && tailscale up`) and use its Tailscale IP. |

## Security

- The browser profile in `/opt/ai-usage-browser/config` **is your logins**. It stays on your server and isn't in Git. Back up the LXC with Proxmox backups, not by copying that folder anywhere.
- Port 3001 has a password, but it's only meant for your LAN. **Never port-forward it**: the user/password setting only turns on basic HTTP auth, which linuxserver.io says is suitable only for a trusted local network.
- The bridge sends only numbers to the add-on. Your cookies and tokens never leave that browser.
- To retire it: `cd /opt/ai-usage-browser && docker compose down`, delete the CT, and sign out of the sites' "active sessions" lists if you like.

## Resources

Expect about 1 GB RAM and near-idle CPU. Chromium wakes every 15 minutes for a few seconds.
