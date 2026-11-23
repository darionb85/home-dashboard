# Devices: easiest first

All of these are added under **Settings → Devices & services → Add integration**, except community ones, which you download from **Settings → Marketplace** first and then restart HA (Marketplace is the built-in version of HACS since 2026.11). After each one, open **Dashboard setup → Build dashboard**.

> "Unofficial" means the integration reverse-engineered the vendor's app. It works today, but a vendor app update can break it until the maintainer catches up. Updates come through the Marketplace.

## 1. Weather: already there
Met.no is set up from your home location during onboarding. Nothing to do.

## 2. Tesla Wall Connector: local, ~2 min
*Add integration → Tesla Wall Connector* → enter the charger's IP. Find it on the Flint 3's **Clients** list (name like `TeslaWallConnector_xxxx`) and reserve that IP. Requires the Wi-Fi Gen 3 connector. Solar and car data come with [Tesla Fleet](tesla-fleet.md).

## 3. Tapo / Kasa plugs + Tapo cameras: ~10 min
Plugs (P125M, EP10) and cameras (C211, C110, C101) all use **TP-Link Smart Home** (built in). Most get auto-discovered.

1. **For each camera first:** Tapo app → camera → ⚙ → *Advanced settings* → **Camera account** → set a username and password. This enables the camera's local video stream.
2. *Add integration → TP-Link Smart Home* → it asks for your TP-Link cloud email/password once (used to authenticate locally), then the camera account for cameras.
3. Tick **Live view** when asked for cameras.
4. Reserve each device's IP on the Flint 3.

If a camera's live view is unreliable, switch that camera to **Tapo: Cameras Control** (Marketplace → search *Tapo: Cameras Control*). It needs the same camera account plus LAN ports 443/554 open between HA and the camera (they are by default). The builder picks up either.

> P125M is also a Matter plug. If you'd rather add it via Matter, that works too; the builder looks at both.

## 4. Ring Video Doorbell 2: ~3 min
*Add integration → Ring* → Ring email + password + the 2-factor code Ring sends. You get a **live_view** camera. Recordings need a Ring Protect subscription, and the builder skips them.

## 5. Blink: ~3 min
*Add integration → Blink* → Blink email + password, then the PIN Blink emails/texts you. **Limit:** Home Assistant gets snapshots and motion clips, not a live stream (Blink doesn't expose one). The widget shows the latest snapshot. Tap it for detail.

## 6. GL.iNet Flint 3 (BE9300, fw 4.9): ~5 min, local
Marketplace → search **GL.iNet Router** (`vithurshanselvarajah/ha-glinet-router`) → Download → restart → *Add integration → GL.iNet Router* → URL `http://192.168.8.1`, user `root`, your router admin password. It gives WAN status, up/down speed, connected clients and device trackers.

## 7. Google Calendar: ~10 min, one time
*Add integration → Google Calendar*. HA walks you through creating your own Google OAuth credentials (a free Google Cloud project; HA's page has the exact clicks: <https://www.home-assistant.io/integrations/google/>). Then sign in with your Google account. Each calendar becomes a `calendar.*` entity. Holiday/birthday calendars are hidden by default; override in the add-on if you want them.

## 8. Sensi thermostat (1F86U-42WF): ~10 min, unofficial
Marketplace → search **Sensi** (`iprak/sensi`) → Download → restart.

Sensi's login uses a captcha, so the integration needs a **refresh token** you copy once from your browser:
1. Desktop Chrome/Edge → go to `manager.sensicomfort.com` → press **F12** → **Network** tab.
2. Log in normally.
3. In the Network list, click the request starting with `token?device=` (if two, the one with a Response) → **Response** → copy the `refresh_token` value.
4. *Add integration → Sensi* → paste it.

Repeat only if you change your Sensi password. Treat the token like a password.

## 9. Vivosun GrowHub E42A: ~5 min, unofficial
Marketplace → search **Vivosun GrowHub** (`lientry/homeassistant-vivosun-growhub`; the E42A is on its verified list) → Download → restart → *Add integration → Vivosun GrowHub* → your Vivosun app email/password. Uses Vivosun's cloud. You get tent temperature, humidity, VPD, light and fans, plus GrowCam if you have one. Needs Home Assistant 2026.11 or newer, which a fresh install already is.

## 10. EcoFlow Delta 3 Ultra Plus: best effort
**Try first: EcoFlow Cloud** (Marketplace → search *EcoFlow Cloud*, `tolwi/hassio-ecoflow-cloud`).
- Best: **public API** mode with a free developer key. Sign up at <https://developer.ecoflow.com/>, wait for approval, then create an Access Key and Secret Key.
- Or **private API** mode with your EcoFlow app email/password (works immediately, less official).
- In the device list, look for *Delta 3 Ultra Plus*. If it isn't listed yet, don't pick a different model. Use the backup below.

**Backup: Bluetooth** (Marketplace → search *EcoFlow BLE*, `ha-ef-ble`; its device list includes the Delta 3 Ultra Plus). Your Proxmox box needs Bluetooth within range of the battery, either way:
- a USB Bluetooth dongle passed through to the HA VM (VM → Hardware → Add → USB device), or
- a ~$10 ESP32 board flashed as an **ESPHome Bluetooth proxy** (<https://esphome.io/projects/>) placed near the battery.

The builder looks for the battery %, input watts, output watts and time remaining from either integration.

---

## When the builder picks the wrong thing

Dashboard setup → *What was found* shows every match. To fix one, add a line in the add-on's **Configuration → entity_overrides**:

```
thermostat=climate.hallway
cameras=camera.front_door_live_view, camera.garage_hd_stream
plugs=-                       # "-" hides that widget
```

The keys are listed in `home_dashboard/app/dashboard/discovery.yaml`. Save, then **Build dashboard** again.
