"""Talks to Home Assistant through the Supervisor proxy (SUPERVISOR_TOKEN).

Only available when running as an add-on; every call fails soft.
"""
from __future__ import annotations

import logging
import os

import aiohttp

log = logging.getLogger(__name__)

SUPERVISOR = "http://supervisor"
CORE_API = f"{SUPERVISOR}/core/api"
CORE_WS = "ws://supervisor/core/websocket"


class HAError(Exception):
    pass


class HAClient:
    def __init__(self, session: aiohttp.ClientSession, token: str | None = None):
        self.session = session
        self.token = token if token is not None else os.environ.get("SUPERVISOR_TOKEN", "")

    @property
    def available(self) -> bool:
        return bool(self.token)

    def _headers(self) -> dict:
        return {"Authorization": f"Bearer {self.token}", "Content-Type": "application/json"}

    async def get_states(self) -> list[dict]:
        async with self.session.get(f"{CORE_API}/states", headers=self._headers(), timeout=20) as r:
            if r.status != 200:
                raise HAError(f"states HTTP {r.status}")
            return await r.json()

    async def set_state(self, entity_id: str, state, attributes: dict) -> None:
        body = {"state": state, "attributes": attributes}
        async with self.session.post(
            f"{CORE_API}/states/{entity_id}", headers=self._headers(), json=body, timeout=20
        ) as r:
            if r.status not in (200, 201):
                raise HAError(f"set_state HTTP {r.status}")

    async def call_service(self, domain: str, service: str, data: dict | None = None) -> None:
        async with self.session.post(f"{CORE_API}/services/{domain}/{service}", headers=self._headers(),
                                     json=data or {}, timeout=20) as r:
            if r.status not in (200, 201):
                raise HAError(f"service HTTP {r.status}")

    async def addon_info(self) -> dict:
        async with self.session.get(f"{SUPERVISOR}/addons/self/info", headers=self._headers(), timeout=20) as r:
            if r.status != 200:
                raise HAError(f"addon info HTTP {r.status}")
            return (await r.json()).get("data", {})

    async def ws_commands(self, commands: list[dict]) -> list:
        """Open one websocket, auth, run commands in order, return their results."""
        results = []
        async with self.session.ws_connect(CORE_WS, timeout=20) as ws:
            hello = await ws.receive_json()
            if hello.get("type") != "auth_required":
                raise HAError("unexpected websocket greeting")
            await ws.send_json({"type": "auth", "access_token": self.token})
            auth = await ws.receive_json()
            if auth.get("type") != "auth_ok":
                raise HAError("websocket auth failed")
            for i, cmd in enumerate(commands, start=1):
                await ws.send_json({"id": i, **cmd})
                while True:
                    msg = await ws.receive_json()
                    if msg.get("id") == i and msg.get("type") == "result":
                        break
                if not msg.get("success"):
                    err = msg.get("error", {})
                    raise HAError(f"{cmd['type']}: {err.get('code')} {err.get('message')}")
                results.append(msg.get("result"))
        return results

    async def entity_registry(self) -> list[dict]:
        (result,) = await self.ws_commands([{"type": "config/entity_registry/list"}])
        return result or []

    async def save_dashboard(self, url_path: str, title: str, config: dict) -> None:
        (dashboards,) = await self.ws_commands([{"type": "lovelace/dashboards/list"}])
        cmds = []
        if not any(d.get("url_path") == url_path for d in dashboards or []):
            cmds.append({
                "type": "lovelace/dashboards/create",
                "url_path": url_path,
                "title": title,
                "icon": "mdi:view-dashboard",
                "show_in_sidebar": True,
                "require_admin": False,
                "mode": "storage",
            })
        cmds.append({"type": "lovelace/config/save", "url_path": url_path, "config": config})
        await self.ws_commands(cmds)
