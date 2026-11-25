"""HTTP surface: auth, shape, rate limit, failure isolation, ingress lock-down."""
import pytest
from aiohttp import ClientSession

from app.ha import HAClient
from app.main import DEFAULTS, Service, make_ingress_app, make_public_app
from app.schema import validate_row
from app.store import Store


@pytest.fixture
async def svc(tmp_path):
    async with ClientSession() as session:
        yield Service(Store(tmp_path), dict(DEFAULTS), session, HAClient(session, token=""))


async def test_usage_requires_token(aiohttp_client, svc):
    c = await aiohttp_client(make_public_app(svc))
    assert (await c.get("/usage.json")).status == 401
    assert (await c.get("/usage.json?token=wrong")).status == 401


async def test_usage_shape(aiohttp_client, svc):
    c = await aiohttp_client(make_public_app(svc))
    r = await c.get("/usage.json", params={"token": svc.store.tokens["read"]})
    assert r.status == 200 and r.headers["Cache-Control"] == "no-store"
    body = await r.json()
    assert set(body) == {"generated_at", "rows"}
    assert len(body["rows"]) == 5
    for row in body["rows"]:
        validate_row(row)


async def test_refresh_rate_limited_and_failure_is_isolated(aiohttp_client, svc):
    c = await aiohttp_client(make_public_app(svc))
    hdr = {"Authorization": f"Bearer {svc.store.tokens['read']}"}
    first = await c.post("/refresh", headers=hdr)
    assert first.status == 200  # no PAT configured -> copilot row errors, service keeps running
    rows = {r["service"]: r for r in (await first.json())["rows"]}
    assert rows["copilot"]["status"] == "error"
    assert rows["copilot"]["link"] == "https://github.com/settings/copilot"
    assert rows["copilot"]["resets_at"]
    second = await c.post("/refresh", headers=hdr)
    assert second.status == 429 and "Retry-After" in second.headers


async def test_write_token_cannot_read_and_tokens_differ(aiohttp_client, svc):
    assert svc.store.tokens["read"] != svc.store.tokens["write"]


async def test_public_app_has_no_edit_routes(aiohttp_client, svc):
    c = await aiohttp_client(make_public_app(svc))
    r = await c.post("/api/rows/claude", json={"pct_used": 1}, params={"token": svc.store.tokens["read"]})
    assert r.status in (404, 405)


async def test_ingress_blocks_direct_access(aiohttp_client, svc):
    c = await aiohttp_client(make_ingress_app(svc))
    assert (await c.get("/api/state")).status == 403


async def test_ingress_manual_edit(aiohttp_client, svc):
    c = await aiohttp_client(make_ingress_app(svc, allow_any_remote=True))
    r = await c.post("/api/rows/claude", json={"pct_used": 64, "resets_at": "2026-11-24T05:00:00Z"})
    assert r.status == 200
    row = await r.json()
    validate_row(row)
    assert row["status"] == "manual" and row["pct_used"] == 64
    assert (await c.post("/api/rows/copilot", json={"pct_used": 1})).status == 400  # live row
    assert (await c.post("/api/rows/nope", json={"pct_used": 1})).status == 400
    assert (await c.post("/api/rows/claude", json={"pct_used": -5})).status == 400


async def test_ingress_yaml_export_without_ha(aiohttp_client, svc):
    c = await aiohttp_client(make_ingress_app(svc, allow_any_remote=True))
    r = await c.get("/api/dashboard.yaml")
    assert r.status == 200 and "views:" in await r.text()
    assert (await c.get("/api/dashboard.yaml?template=../etc")).status == 400


async def test_ingest_needs_write_token(aiohttp_client, svc):
    c = await aiohttp_client(make_public_app(svc))
    body = {"service": "claude", "pct_used": 64, "resets_at": "2026-11-28T09:00:00Z"}
    assert (await c.post("/ingest", json=body)).status == 401
    read = {"Authorization": f"Bearer {svc.store.tokens['read']}"}
    assert (await c.post("/ingest", json=body, headers=read)).status == 401  # read token can't write


async def test_ingest_sets_live_row_and_details(aiohttp_client, svc):
    c = await aiohttp_client(make_public_app(svc))
    hdr = {"Authorization": f"Bearer {svc.store.tokens['write']}"}
    r = await c.post("/ingest", headers=hdr, json={
        "service": "claude", "pct_used": 64, "resets_at": "2026-11-28T09:00:00Z",
        "details": {"session_pct": 12, "weekly_pct": 64, "window": "weekly",
                    "bad key!": 1, "nested": {"x": 1}, "long": "y" * 500}})
    assert r.status == 200
    row = await r.json()
    validate_row(row)
    assert row["status"] == "ok" and row["pct_used"] == 64
    d = svc.store.get_details("claude")
    assert d["session_pct"] == 12 and "bad key!" not in d and "nested" not in d and len(d["long"]) == 100
    usage = await (await c.get("/usage.json", params={"token": svc.store.tokens["read"]})).json()
    for row in usage["rows"]:
        validate_row(row)  # details never leak into the published row shape


async def test_ingest_error_keeps_last_value(aiohttp_client, svc):
    c = await aiohttp_client(make_public_app(svc))
    hdr = {"Authorization": f"Bearer {svc.store.tokens['write']}"}
    await c.post("/ingest", headers=hdr, json={"service": "chatgpt", "pct_used": 20, "resets_at": "2026-11-26T00:00:00Z"})
    svc._ingest_seen.clear()
    r = await c.post("/ingest", headers=hdr, json={"service": "chatgpt", "error": "chatgpt.com: signed out"})
    row = await r.json()
    assert row["status"] == "error" and row["pct_used"] == 20
    assert svc.store.get_details("chatgpt")["error"] == "chatgpt.com: signed out"


async def test_ingest_rejects_bad_input_and_rate_limits(aiohttp_client, svc):
    c = await aiohttp_client(make_public_app(svc))
    hdr = {"Authorization": f"Bearer {svc.store.tokens['write']}"}
    assert (await c.post("/ingest", headers=hdr, json={"service": "copilot", "pct_used": 1})).status == 400
    assert (await c.post("/ingest", headers=hdr, json={"service": "nope", "pct_used": 1})).status == 400
    assert (await c.post("/ingest", headers=hdr, json={"service": "gemini", "pct_used": -3})).status == 400
    svc._ingest_seen.clear()
    assert (await c.post("/ingest", headers=hdr, json={"service": "gemini", "pct_used": 3})).status == 200
    assert (await c.post("/ingest", headers=hdr, json={"service": "gemini", "pct_used": 4})).status == 429
