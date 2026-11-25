"""Installs the AI usage card into Home Assistant: copies the JS into config/www
and registers it as a dashboard resource. Fails soft; the builder then falls
back to plain gauges."""
from __future__ import annotations

import logging
import os
import shutil
from pathlib import Path

log = logging.getLogger(__name__)

CARD_SRC = Path(__file__).parent / "static" / "ai-usage-card.js"
CARD_VERSION = "0.3.0"
URL_PATH = "/local/home-dashboard/ai-usage-card.js"
CONFIG_ROOTS = ("/homeassistant", "/config")


def config_root() -> Path | None:
    override = os.environ.get("HA_CONFIG_DIR")
    for p in ([override] if override else []) + list(CONFIG_ROOTS):
        if p and Path(p, "configuration.yaml").exists():
            return Path(p)
    return None


def copy_card(root: Path) -> bool:
    """Returns True if config/www had to be created (HA must restart once to serve /local)."""
    www = root / "www"
    created = not www.exists()
    dest = www / "home-dashboard"
    dest.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(CARD_SRC, dest / "ai-usage-card.js")
    return created


CORE_URLS = ("http://homeassistant:8123", "https://homeassistant:8123")


async def served(session) -> bool:
    """True if Home Assistant is already serving the card at /local (no restart needed)."""
    for base in CORE_URLS:
        try:
            async with session.get(f"{base}{URL_PATH}", timeout=5, ssl=False) as r:
                if r.status == 200:
                    return True
        except Exception:
            continue
    return False


async def register_resource(ha) -> None:
    url = f"{URL_PATH}?v={CARD_VERSION}"
    (resources,) = await ha.ws_commands([{"type": "lovelace/resources"}])
    mine = [r for r in resources or [] if str(r.get("url", "")).split("?")[0] == URL_PATH]
    if mine and mine[0].get("url") == url:
        return
    if mine:
        await ha.ws_commands([{"type": "lovelace/resources/update", "resource_id": mine[0]["id"],
                               "res_type": "module", "url": url}])
    else:
        await ha.ws_commands([{"type": "lovelace/resources/create", "res_type": "module", "url": url}])


async def install(ha) -> dict:
    """{'ok': bool, 'needs_restart': bool, 'reason': str|None}"""
    root = config_root()
    if root is None:
        return {"ok": False, "needs_restart": False, "reason": "Home Assistant config folder not mapped"}
    try:
        created = copy_card(root)
        await register_resource(ha)
    except Exception as exc:  # never break the build over the card
        log.warning("AI usage card install failed: %s", exc)
        return {"ok": False, "needs_restart": False, "reason": str(exc)[:120]}
    return {"ok": True, "needs_restart": created, "reason": None}
