# Tesla solar + car (Tesla Fleet): next build

**Why:** Fleet is Tesla's official API. It covers solar, home usage, grid, the car and the Wall Connector. Energy (solar) calls are free. Car data fits in Tesla's $10/month personal credit because Home Assistant polls the car only every 10 minutes while it's awake. Unofficial routes keep breaking; this one doesn't.

**Effort:** 30–60 minutes once. The fiddly part is hosting a small public key file on a web domain with HTTPS.

## What you need
- Tesla account with verified email and MFA.
- A domain for the public key. Pick one:
  - **Easiest:** a hosted key service such as **FleetKey.net** or **MyTeslamate.com** (supported by HA's docs; no domain needed).
  - **Own domain:** any domain you control, using the HA **NGINX SSL proxy** add-on, or a free Cloudflare Pages site serving one file. Avoid `ddns.net` hostnames; Tesla rejects them silently.

## Steps
1. <https://developer.tesla.com/request> → create an app:
   - OAuth grant types: *Authorization Code* + *Machine-to-Machine*
   - Allowed origin: your key domain
   - Redirect URI: `https://my.home-assistant.io/redirect/oauth`
   - Scopes: Vehicle Information, **Energy Product Information**, Vehicle Location (optional), Vehicle Commands (optional), Energy Product Settings (optional)
   - Save the **Client ID** and **Client Secret**.
2. Host the public key at `https://<domain>/.well-known/appspecific/com.tesla.3p.public-key.pem`. HA generates the key pair during setup, or the key service does it for you.
3. HA → *Add integration → Tesla Fleet* → enter Client ID/Secret → sign in to Tesla → approve scopes → enter your domain.
4. For car commands only: open `https://tesla.com/_ak/<your-domain>` on your phone and approve the virtual key in the Tesla app. Read-only data doesn't need this.
5. **Dashboard setup → Build dashboard**. Solar, home usage, car battery and range appear in the Energy section.

Usage and cost show in the Tesla Developer Dashboard. Add billing details only if you ever exceed the credit.

**Paid shortcut:** Teslemetry (built-in HA integration, subscription) skips the developer app and domain steps. The builder supports it too.
