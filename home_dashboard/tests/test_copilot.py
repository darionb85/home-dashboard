"""Copilot parser + fetcher against mocked GitHub responses."""
import pytest
from aiohttp import web, ClientSession

from app import copilot
from app.copilot import CopilotError, build_row, error_row, fetch_copilot, parse_usage
from app.schema import next_month_start, iso, validate_row

PAT = "fake-test-token-not-real"


def test_parse_ai_credit_counts_only_copilot_items(fixture):
    assert parse_usage(fixture("ai_credit_usage.json")) == 100  # ignores Actions minutes


def test_parse_premium_request(fixture):
    assert parse_usage(fixture("premium_request_usage.json")) == 150


@pytest.mark.parametrize("bad", [None, [], {}, {"usageItems": "x"}, {"usageItems": [{"grossQuantity": "7"}]}])
def test_parse_rejects_bad_shapes(bad):
    with pytest.raises(CopilotError):
        parse_usage(bad)


def test_parse_empty_month_is_zero():
    assert parse_usage({"usageItems": []}) == 0


def test_build_row_student_allowance():
    row = build_row(100, 200)
    validate_row(row)
    assert row["pct_used"] == 50.0 and row["status"] == "ok"
    assert row["resets_at"] == iso(next_month_start())
    assert row["resets_at"].endswith("-01T00:00:00Z")


def test_error_row_keeps_reset_and_link():
    row = error_row({"pct_used": 42.0})
    validate_row(row)
    assert row["status"] == "error"
    assert row["pct_used"] == 42.0
    assert row["link"] == "https://github.com/settings/copilot"
    assert row["resets_at"] == iso(next_month_start())


def mock_github(responses):
    """responses: {endpoint_kind: (status, json)}; records auth headers seen."""
    seen = []

    async def handler(request):
        kind = request.match_info["kind"]
        seen.append((kind, request.headers.get("Authorization"), dict(request.query)))
        status, body = responses.get(kind, (404, {"message": "Not Found"}))
        return web.json_response(body, status=status)

    app = web.Application()
    app.router.add_get("/users/{user}/settings/billing/{kind}/usage", handler)
    return app, seen


async def run_fetch(aiohttp_server, monkeypatch, responses, user="darionb85", pat=PAT):
    app, seen = mock_github(responses)
    server = await aiohttp_server(app)
    monkeypatch.setattr(copilot, "API", str(server.make_url("")).rstrip("/"))
    async with ClientSession() as s:
        return await fetch_copilot(s, user, pat, 200), seen


async def test_fetch_ai_credit(aiohttp_server, monkeypatch, fixture):
    row, seen = await run_fetch(aiohttp_server, monkeypatch, {"ai_credit": (200, fixture("ai_credit_usage.json"))})
    assert row["pct_used"] == 50.0 and row["status"] == "ok"
    assert seen[0][0] == "ai_credit" and seen[0][1] == f"Bearer {PAT}"
    assert {"year", "month"} <= set(seen[0][2])


async def test_fetch_falls_back_to_premium_requests(aiohttp_server, monkeypatch, fixture):
    row, seen = await run_fetch(aiohttp_server, monkeypatch,
                                {"premium_request": (200, fixture("premium_request_usage.json"))})
    assert [k for k, *_ in seen] == ["ai_credit", "premium_request"]
    assert row["pct_used"] == 75.0


async def test_fetch_bad_token_stops_and_hides_secret(aiohttp_server, monkeypatch):
    with pytest.raises(CopilotError) as exc:
        await run_fetch(aiohttp_server, monkeypatch, {"ai_credit": (401, {"message": "Bad credentials"})})
    assert "401" in str(exc.value)
    assert PAT not in str(exc.value)


async def test_fetch_without_credentials():
    async with ClientSession() as s:
        with pytest.raises(CopilotError):
            await fetch_copilot(s, "", "", 200)
