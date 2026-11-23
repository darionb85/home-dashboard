"""Row schema shared by /usage.json, the PWA and the phone widgets.

Row: {service, pct_used, resets_at (ISO), updated_at (ISO), status, link}
status is one of: ok | stale | manual | error
"""
from __future__ import annotations

from datetime import datetime, timezone

ROW_KEYS = ("service", "pct_used", "resets_at", "updated_at", "status", "link")
STATUSES = ("ok", "stale", "manual", "error")

# Order here is the display order everywhere.
SERVICES = {
    "copilot": {"label": "GitHub Copilot", "link": "https://github.com/settings/copilot", "live": True},
    "claude": {"label": "Claude", "link": "https://claude.ai/settings/usage", "live": False},
    "chatgpt": {"label": "ChatGPT", "link": "https://chatgpt.com/", "live": False},
    "gemini": {"label": "Gemini", "link": "https://gemini.google.com/", "live": False},
    "grok": {"label": "Grok", "link": "https://grok.com/", "live": False},
}


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def iso(dt: datetime | None) -> str | None:
    if dt is None:
        return None
    return dt.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)
    except (ValueError, AttributeError):
        return None


def next_month_start(now: datetime | None = None) -> datetime:
    """Copilot allowances reset 00:00 UTC on the 1st of each month."""
    now = (now or utcnow()).astimezone(timezone.utc)
    if now.month == 12:
        return datetime(now.year + 1, 1, 1, tzinfo=timezone.utc)
    return datetime(now.year, now.month + 1, 1, tzinfo=timezone.utc)


def make_row(service: str, pct_used=None, resets_at=None, status="manual", updated_at=None, link=None) -> dict:
    if service not in SERVICES:
        raise ValueError(f"unknown service {service!r}")
    if status not in STATUSES:
        raise ValueError(f"bad status {status!r}")
    if pct_used is not None:
        pct_used = round(float(pct_used), 1)
        if pct_used < 0:
            raise ValueError("pct_used must be >= 0")
    if isinstance(resets_at, datetime):
        resets_at = iso(resets_at)
    elif resets_at is not None and parse_iso(resets_at) is None:
        raise ValueError("resets_at must be ISO 8601")
    return {
        "service": service,
        "pct_used": pct_used,
        "resets_at": resets_at,
        "updated_at": updated_at or iso(utcnow()),
        "status": status,
        "link": link or SERVICES[service]["link"],
    }


def default_rows() -> list[dict]:
    rows = []
    for name, meta in SERVICES.items():
        if meta["live"]:
            rows.append(make_row(name, status="stale", resets_at=next_month_start()))
        else:
            rows.append(make_row(name, status="manual"))
    return rows


def validate_row(row: dict) -> None:
    """Raise ValueError if a row doesn't match the published shape."""
    if tuple(sorted(row)) != tuple(sorted(ROW_KEYS)):
        raise ValueError(f"row keys {sorted(row)} != {sorted(ROW_KEYS)}")
    if row["service"] not in SERVICES:
        raise ValueError("unknown service")
    if row["status"] not in STATUSES:
        raise ValueError("bad status")
    if row["pct_used"] is not None and not isinstance(row["pct_used"], (int, float)):
        raise ValueError("pct_used must be number or null")
    for key in ("resets_at", "updated_at"):
        if row[key] is not None and parse_iso(row[key]) is None:
            raise ValueError(f"{key} must be ISO 8601 or null")
    if not str(row["link"]).startswith("https://"):
        raise ValueError("link must be https")


def mark_stale(rows: list[dict], max_age_minutes: int) -> list[dict]:
    """Live rows that haven't refreshed in time become stale (never manual rows)."""
    now = utcnow()
    out = []
    for row in rows:
        row = dict(row)
        if row["status"] == "ok":
            updated = parse_iso(row["updated_at"])
            if updated is None or (now - updated).total_seconds() > max_age_minutes * 60:
                row["status"] = "stale"
        out.append(row)
    return out
