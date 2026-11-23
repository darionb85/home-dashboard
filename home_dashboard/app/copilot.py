"""GitHub Copilot usage (official REST API, fine-grained PAT with Plan: read-only).

Primary:  GET /users/{username}/settings/billing/ai_credit/usage        (AI credits)
Fallback: GET /users/{username}/settings/billing/premium_request/usage  (legacy premium requests)
"""
from __future__ import annotations

import logging

from .schema import make_row, next_month_start, utcnow

log = logging.getLogger(__name__)

API = "https://api.github.com"
ENDPOINTS = (
    ("ai_credit", "2026-03-10"),
    ("premium_request", "2022-11-28"),
)


class CopilotError(Exception):
    """Raised with a short, secret-free reason."""


def parse_usage(payload: dict) -> float:
    """Total units used this period (credits or premium requests).

    Sums grossQuantity across usageItems. If any item names Copilot in its
    product, only Copilot items are counted.
    """
    if not isinstance(payload, dict):
        raise CopilotError("unexpected response shape")
    items = payload.get("usageItems")
    if not isinstance(items, list):
        raise CopilotError("response has no usageItems")
    copilot_items = [i for i in items if "copilot" in str(i.get("product", "")).lower()]
    chosen = copilot_items or items
    total = 0.0
    for item in chosen:
        qty = item.get("grossQuantity", 0)
        if not isinstance(qty, (int, float)):
            raise CopilotError("non-numeric grossQuantity")
        total += qty
    return total


def build_row(used: float, allowance: int) -> dict:
    if allowance <= 0:
        raise CopilotError("allowance must be > 0")
    pct = used / allowance * 100
    return make_row("copilot", pct_used=pct, resets_at=next_month_start(), status="ok")


def error_row(previous: dict | None = None) -> dict:
    """On failure keep the last known pct but always show the reset date + settings link."""
    pct = previous.get("pct_used") if previous else None
    return make_row("copilot", pct_used=pct, resets_at=next_month_start(), status="error")


async def fetch_copilot(session, username: str, pat: str, allowance: int) -> dict:
    """Return an 'ok' row, or raise CopilotError. Never logs the token."""
    if not username or not pat:
        raise CopilotError("github_username / github_pat not set")
    now = utcnow()
    last_reason = "no endpoint answered"
    for kind, version in ENDPOINTS:
        url = f"{API}/users/{username}/settings/billing/{kind}/usage"
        headers = {
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {pat}",
            "X-GitHub-Api-Version": version,
            "User-Agent": "home-dashboard-addon",
        }
        params = {"year": now.year, "month": now.month}
        try:
            async with session.get(url, headers=headers, params=params, timeout=20) as resp:
                if resp.status == 200:
                    used = parse_usage(await resp.json(content_type=None))
                    return build_row(used, allowance)
                last_reason = f"{kind}: HTTP {resp.status}"
                if resp.status in (401, 403):
                    break  # bad/insufficient token: fallback won't help
        except CopilotError as exc:
            last_reason = f"{kind}: {exc}"
        except Exception as exc:  # network, timeout, JSON
            last_reason = f"{kind}: {type(exc).__name__}"
    raise CopilotError(last_reason)
