import { test } from "node:test";
import assert from "node:assert/strict";
import { pickClaudeOrg, parseClaudeUsage, parseChatgptSession, parseChatgptUsage, ParseError } from "../parsers.js";

test("claude: picks the chat org", () => {
  const orgs = [{ uuid: "api-org", capabilities: ["api"] }, { uuid: "chat-org", capabilities: ["chat", "claude_max"] }];
  assert.equal(pickClaudeOrg(orgs), "chat-org");
  assert.throws(() => pickClaudeOrg([]), ParseError);
});

test("claude: headline is the tighter window, both kept as details", () => {
  const r = parseClaudeUsage({
    five_hour: { utilization: 12.0, resets_at: "2026-11-25T18:00:00Z" },
    seven_day: { utilization: 64.0, resets_at: "2026-11-28T09:00:00Z" },
    seven_day_opus: { utilization: 3.0 },
    extra_usage: null,
  });
  assert.equal(r.pct_used, 64);
  assert.equal(r.resets_at, "2026-11-28T09:00:00Z");
  assert.deepEqual(r.details, {
    window: "weekly", session_pct: 12, session_resets_at: "2026-11-25T18:00:00Z",
    weekly_pct: 64, weekly_resets_at: "2026-11-28T09:00:00Z", weekly_opus_pct: 3,
  });
});

test("claude: null windows are skipped; empty is an error", () => {
  assert.equal(parseClaudeUsage({ five_hour: { utilization: 5, resets_at: "x" }, seven_day: null }).pct_used, 5);
  assert.throws(() => parseClaudeUsage({ five_hour: null, seven_day: null }), ParseError);
});

test("chatgpt: session must have a token", () => {
  assert.deepEqual(parseChatgptSession({ accessToken: "t", account: { id: "a" } }), { accessToken: "t", accountId: "a" });
  assert.throws(() => parseChatgptSession({}), ParseError);
});

test("chatgpt: windows labelled by length, unix reset converted", () => {
  const r = parseChatgptUsage({
    plan_type: "plus",
    rate_limit: {
      allowed: true, limit_reached: false,
      primary_window: { used_percent: 20, limit_window_seconds: 18000, reset_at: 1795000000 },
      secondary_window: { used_percent: 41, limit_window_seconds: 604800, reset_after_seconds: 3600 },
    },
  }, Date.parse("2026-11-25T12:00:00Z"));
  assert.equal(r.pct_used, 41);
  assert.equal(r.resets_at, "2026-11-25T13:00:00.000Z");
  assert.equal(r.details.plan, "plus");
  assert.equal(r.details.session_pct, 20);
  assert.equal(r.details.session_resets_at, new Date(1795000000 * 1000).toISOString());
  assert.equal(r.details.limit_reached, false);
});

test("chatgpt: missing rate_limit is an error", () => {
  assert.throws(() => parseChatgptUsage({ plan_type: "free" }), ParseError);
});
