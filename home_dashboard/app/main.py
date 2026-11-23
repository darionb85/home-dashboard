"""Home Dashboard add-on.

Two web servers:
  * public  :8787  /usage.json, PWA, POST /refresh   (read token required)
  * ingress :8099  admin page inside Home Assistant (HA login), edit rows,
                   build dashboard, show/rotate tokens
"""
from __future__ import annotations

import asyncio
import hmac
import json
import logging
import os
import time
from pathlib import Path

import aiohttp
import yaml
from aiohttp import web

from . import builder
from .copilot import CopilotError, error_row, fetch_copilot
from .ha import HAClient, HAError
from .schema import SERVICES, iso, mark_stale, utcnow
from .store import Store

log = logging.getLogger("home_dashboard")
STATIC = Path(__file__).parent / "static"
INGRESS_PROXY = "172.30.32.2"
DEFAULTS = {
    "github_username": "",
    "github_pat": "",
    "copilot_allowance": 200,
    "refresh_minutes": 30,
    "template": "catppuccin",
    "auto_build": True,
    "entity_overrides": [],
}

KEY_OPTIONS = web.AppKey("options", dict)
KEY_SVC = web.AppKey("service", object)


def load_options(path: str) -> dict:
    opts = dict(DEFAULTS)
    try:
        opts.update(json.loads(Path(path).read_text()))
    except (FileNotFoundError, json.JSONDecodeError):
        log.warning("no options file; using defaults")
    return opts


class Service:
    """Shared state + work for both servers."""

    def __init__(self, store: Store, options: dict, session: aiohttp.ClientSession, ha: HAClient):
        self.store = store
        self.options = options
        self.session = session
        self.ha = ha
        self.refresh_lock = asyncio.Lock()
        self.last_refresh = 0.0
        self.last_build: dict = {}
        self.extra_template_dirs = [Path(os.environ.get("USER_TEMPLATES", "/share/home_dashboard/templates"))]

    # -- usage -------------------------------------------------------------
    def usage_payload(self) -> dict:
        stale_after = int(self.options["refresh_minutes"]) * 2 + 5
        return {"generated_at": iso(utcnow()), "rows": mark_stale(self.store.rows, stale_after)}

    async def refresh(self, force: bool = False) -> tuple[bool, int]:
        """Returns (ran, retry_after_seconds). Rate-limited to once per minute."""
        wait = int(60 - (time.monotonic() - self.last_refresh))
        if not force and self.last_refresh and wait > 0:
            return False, wait
        async with self.refresh_lock:
            self.last_refresh = time.monotonic()
            await self._refresh_copilot()
            await self.push_sensors()
        return True, 0

    async def _refresh_copilot(self) -> None:
        o = self.options
        try:
            row = await fetch_copilot(self.session, o["github_username"], o["github_pat"], int(o["copilot_allowance"]))
            log.info("copilot refreshed: %.1f%% used", row["pct_used"])
        except CopilotError as exc:
            log.warning("copilot refresh failed: %s", exc)
            row = error_row(self.store.get_row("copilot"))
        except Exception as exc:  # never let one row take the service down
            log.exception("copilot refresh crashed: %s", type(exc).__name__)
            row = error_row(self.store.get_row("copilot"))
        self.store.put_row(row)

    async def push_sensors(self) -> None:
        if not self.ha.available:
            return
        for row in self.usage_payload()["rows"]:
            meta = SERVICES[row["service"]]
            attrs = {
                "friendly_name": f"{meta['label']} usage",
                "unit_of_measurement": "%",
                "icon": "mdi:robot",
                "state_class": "measurement",
                "resets_at": row["resets_at"],
                "status": row["status"],
                "link": row["link"],
                "updated_at": row["updated_at"],
            }
            state = row["pct_used"] if row["pct_used"] is not None else "unknown"
            try:
                await self.ha.set_state(f"sensor.ai_usage_{row['service']}", state, attrs)
            except (HAError, aiohttp.ClientError, asyncio.TimeoutError) as exc:
                log.warning("could not update HA sensor for %s: %s", row["service"], exc)

    async def scheduler(self) -> None:
        while True:
            try:
                await self.refresh(force=True)
            except Exception:
                log.exception("scheduled refresh failed")
            await asyncio.sleep(max(5, int(self.options["refresh_minutes"])) * 60)

    # -- dashboard -----------------------------------------------------------
    async def build_dashboard(self, template: str | None = None, push: bool = True) -> dict:
        template = template or self.options["template"]
        states = await self.ha.get_states() if self.ha.available else []
        registry = []
        extras = {}
        if self.ha.available:
            try:
                registry = await self.ha.entity_registry()
            except (HAError, aiohttp.ClientError, asyncio.TimeoutError) as exc:
                log.warning("entity registry unavailable, using name hints: %s", exc)
            try:
                info = await self.ha.addon_info()
                if info.get("slug"):
                    extras["addon_ingress"] = f"/hassio/ingress/{info['slug']}"
            except (HAError, aiohttp.ClientError, asyncio.TimeoutError):
                pass
        overrides = builder.parse_overrides(self.options.get("entity_overrides"))
        config, found = builder.build(states, registry, template, overrides, extras, self.extra_template_dirs)
        pushed = False
        if push and self.ha.available:
            await self.ha.save_dashboard("home-dashboard", config.get("title", "Home"), config)
            pushed = True
        self.last_build = {"at": iso(utcnow()), "template": template, "found": found, "pushed": pushed, "config": config}
        log.info("dashboard built with template %s (%d keys found, pushed=%s)", template, len(found), pushed)
        return self.last_build

    async def auto_build(self) -> None:
        await asyncio.sleep(45)  # let HA settle after a reboot
        try:
            await self.build_dashboard()
        except Exception as exc:
            log.warning("auto build failed (open the add-on page to retry): %s", exc)


# ------------------------------------------------------------------------
# helpers
# ------------------------------------------------------------------------
def _token_ok(request: web.Request, expected: str) -> bool:
    given = request.query.get("token", "")
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        given = auth[7:]
    return bool(given) and hmac.compare_digest(given.encode(), expected.encode())


def _json(data, status=200, **headers):
    return web.json_response(data, status=status, headers={"Cache-Control": "no-store", **headers})


def _static(name: str, content_type: str | None = None):
    async def handler(_request):
        return web.FileResponse(STATIC / name, headers={"Cache-Control": "no-cache"} if content_type is None else {
            "Cache-Control": "no-cache", "Content-Type": content_type})
    return handler


SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "no-referrer",
    "X-Frame-Options": "SAMEORIGIN",
}


@web.middleware
async def security_headers(request, handler):
    resp = await handler(request)
    for k, v in SECURITY_HEADERS.items():
        resp.headers.setdefault(k, v)
    return resp


# ------------------------------------------------------------------------
# public app (:8787) – phone widgets + read-only PWA
# ------------------------------------------------------------------------
def make_public_app(svc: Service) -> web.Application:
    app = web.Application(middlewares=[security_headers])
    app[KEY_SVC] = svc

    async def usage(request):
        if not _token_ok(request, svc.store.tokens["read"]):
            return _json({"error": "unauthorized"}, 401)
        return _json(svc.usage_payload())

    async def refresh(request):
        if not _token_ok(request, svc.store.tokens["read"]):
            return _json({"error": "unauthorized"}, 401)
        ran, wait = await svc.refresh()
        if not ran:
            return _json({"error": "rate_limited", "retry_after": wait}, 429, **{"Retry-After": str(wait)})
        return _json(svc.usage_payload())

    app.router.add_get("/", _static("index.html"))
    app.router.add_get("/usage.json", usage)
    app.router.add_post("/refresh", refresh)
    app.router.add_get("/manifest.webmanifest", _static("manifest.webmanifest", "application/manifest+json"))
    app.router.add_get("/sw.js", _static("sw.js", "application/javascript"))
    app.router.add_get("/icon.svg", _static("icon.svg", "image/svg+xml"))
    add_shared_assets(app)
    return app


def add_shared_assets(app: web.Application) -> None:
    app.router.add_get("/rows.js", _static("rows.js", "application/javascript"))
    app.router.add_get("/theme.css", _static("theme.css", "text/css"))


# ------------------------------------------------------------------------
# ingress app (:8099) – admin, only reachable through HA's authenticated proxy
# ------------------------------------------------------------------------
def make_ingress_app(svc: Service, allow_any_remote: bool = False) -> web.Application:
    @web.middleware
    async def only_ingress(request, handler):
        if not allow_any_remote and request.remote != INGRESS_PROXY:
            return _json({"error": "forbidden"}, 403)
        return await handler(request)

    app = web.Application(middlewares=[only_ingress, security_headers])
    app[KEY_SVC] = svc

    async def state(_request):
        b = svc.last_build
        return _json({
            "rows": svc.usage_payload()["rows"],
            "tokens": svc.store.tokens,
            "templates": builder.list_templates(svc.extra_template_dirs),
            "template": svc.options["template"],
            "copilot_configured": bool(svc.options["github_username"] and svc.options["github_pat"]),
            "last_build": {k: b.get(k) for k in ("at", "template", "found", "pushed")} if b else None,
        })

    async def set_row(request):
        service = request.match_info["service"]
        try:
            body = await request.json()
            row = svc.store.set_manual(service, body.get("pct_used"), body.get("resets_at"))
        except (ValueError, json.JSONDecodeError) as exc:
            return _json({"error": str(exc)}, 400)
        await svc.push_sensors()
        return _json(row)

    async def refresh(_request):
        ran, wait = await svc.refresh()
        if not ran:
            return _json({"error": "rate_limited", "retry_after": wait}, 429)
        return _json(svc.usage_payload())

    async def build(request):
        try:
            body = await request.json() if request.can_read_body else {}
        except json.JSONDecodeError:
            body = {}
        try:
            result = await svc.build_dashboard(body.get("template"))
        except (FileNotFoundError, ValueError) as exc:
            return _json({"error": str(exc)}, 400)
        except (HAError, aiohttp.ClientError, asyncio.TimeoutError) as exc:
            return _json({"error": f"Home Assistant refused: {exc}"}, 502)
        return _json({k: result[k] for k in ("at", "template", "found", "pushed")})

    async def dashboard_yaml(request):
        template = request.query.get("template")
        try:
            result = await svc.build_dashboard(template, push=False)
        except (FileNotFoundError, ValueError) as exc:
            return _json({"error": str(exc)}, 400)
        text = yaml.safe_dump(result["config"], sort_keys=False, allow_unicode=True)
        return web.Response(text=text, content_type="text/yaml",
                            headers={"Content-Disposition": "attachment; filename=home-dashboard.yaml"})

    async def rotate(_request):
        svc.store.rotate_tokens()
        return _json({"tokens": svc.store.tokens})

    app.router.add_get("/", _static("admin.html"))
    app.router.add_get("/api/state", state)
    app.router.add_post("/api/rows/{service}", set_row)
    app.router.add_post("/api/refresh", refresh)
    app.router.add_post("/api/build", build)
    app.router.add_get("/api/dashboard.yaml", dashboard_yaml)
    app.router.add_post("/api/tokens/rotate", rotate)
    add_shared_assets(app)
    return app


# ------------------------------------------------------------------------
async def run() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    options = load_options(os.environ.get("OPTIONS_PATH", "/data/options.json"))
    store = Store(os.environ.get("DATA_DIR", "/data"))
    async with aiohttp.ClientSession() as session:
        svc = Service(store, options, session, HAClient(session))
        dev = os.environ.get("DEV_ALLOW_ANY_REMOTE") == "1"
        runners = []
        for app, port in ((make_public_app(svc), int(os.environ.get("PUBLIC_PORT", 8787))),
                          (make_ingress_app(svc, dev), int(os.environ.get("INGRESS_PORT", 8099)))):
            runner = web.AppRunner(app, access_log=None)  # access log would contain ?token=
            await runner.setup()
            await web.TCPSite(runner, "0.0.0.0", port).start()
            runners.append(runner)
        log.info("listening: public :8787, ingress :8099")
        tasks = [asyncio.create_task(svc.scheduler())]
        if options.get("auto_build") and svc.ha.available:
            tasks.append(asyncio.create_task(svc.auto_build()))
        try:
            await asyncio.Event().wait()
        finally:
            for t in tasks:
                t.cancel()
            for r in runners:
                await r.cleanup()


def main() -> None:
    asyncio.run(run())


if __name__ == "__main__":
    main()
