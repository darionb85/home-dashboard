"""JSON shape published at /usage.json."""
from datetime import timedelta

import pytest

from app.schema import (ROW_KEYS, SERVICES, default_rows, iso, make_row, mark_stale,
                        next_month_start, utcnow, validate_row)
from datetime import datetime, timezone


def test_default_rows_cover_every_service_in_order():
    rows = default_rows()
    assert [r["service"] for r in rows] == list(SERVICES)
    for r in rows:
        validate_row(r)
        assert tuple(sorted(r)) == tuple(sorted(ROW_KEYS))
    assert rows[0]["service"] == "copilot" and rows[0]["status"] == "stale"
    assert all(r["status"] == "manual" for r in rows[1:])


def test_make_row_rounds_and_formats():
    r = make_row("claude", pct_used=33.333, resets_at="2026-11-24T05:00:00Z")
    assert r["pct_used"] == 33.3 and r["resets_at"] == "2026-11-24T05:00:00Z"


@pytest.mark.parametrize("kwargs", [
    {"service": "nope"},
    {"service": "claude", "status": "great"},
    {"service": "claude", "pct_used": -1},
    {"service": "claude", "resets_at": "tomorrow"},
])
def test_make_row_rejects(kwargs):
    with pytest.raises(ValueError):
        make_row(**kwargs)


def test_validate_rejects_extra_keys():
    r = make_row("claude")
    r["secret"] = "x"
    with pytest.raises(ValueError):
        validate_row(r)


def test_next_month_start_rolls_year():
    assert next_month_start(datetime(2026, 12, 15, tzinfo=timezone.utc)) == datetime(2027, 1, 1, tzinfo=timezone.utc)


def test_mark_stale_only_touches_old_ok_rows():
    old = iso(utcnow() - timedelta(hours=3))
    rows = [make_row("copilot", 10, status="ok", updated_at=old), make_row("claude", status="manual", updated_at=old)]
    out = mark_stale(rows, 65)
    assert out[0]["status"] == "stale" and out[1]["status"] == "manual"
