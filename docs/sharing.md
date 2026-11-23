# Giving this to friends & family

Each household runs its **own** Home Assistant. Their devices, passwords and calendars never touch yours.

## What they need
- Any always-on box: Proxmox, a Raspberry Pi 4/5 or a mini PC. For a Pi or mini PC, use HA's official installer (<https://www.home-assistant.io/installation/>) instead of the Proxmox script.
- 1–2 hours, or you sit with them once.

## Steps for them
1. Install Home Assistant ([install.md §1](install.md#1-home-assistant-on-proxmox), or the official guide for a Pi).
2. Marketplace + Catppuccin + Tailscale ([install.md §2](install.md#2-hacs-theme-tailscale)). Tailscale is optional. Without it the dashboard works at home only.
3. Add **their** devices from [integrations.md](integrations.md), signing in with **their** accounts. Skip anything they don't own; the dashboard simply won't show it.
4. Settings → **Apps** → **App store** → ⋮ → Repositories → `https://github.com/darionb85/home-dashboard` → install **Home Dashboard** → Start → **Dashboard setup → Build dashboard**.
5. Optional: their own GitHub token for the Copilot row, or set `ai_usage=-` in *entity_overrides* to hide AI usage.

## Logins in their house
Settings → People → add each person with *Allow login*. Everyone uses their own username or email and password. Give kids non-admin accounts.

## Updates
When you push improvements here, they get an **Update** button on the add-on. Their settings stay.
