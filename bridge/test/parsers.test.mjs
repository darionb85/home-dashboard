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
  assert.equal(r.details.fields, "five_hour,seven_day,seven_day_opus");
  delete r.details.fields;
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

import { parseGeminiText, parseResetPhrase } from "../parsers.js";
const NOW = new Date("2026-11-25T15:00:00Z");

test("gemini: reads current + weekly with relative and dated resets", () => {
  const text = `Usage limits\nCurrent usage\n37% used\nResets in 2 hr 10 min\nWeekly limit\n12% used\nResets Nov 28, 9:00 AM\nUpgrade`;
  const r = parseGeminiText(text, NOW);
  assert.equal(r.pct_used, 37);
  assert.equal(r.details.window, "session");
  assert.equal(r.details.session_pct, 37);
  assert.equal(r.details.weekly_pct, 12);
  assert.equal(r.details.session_resets_at, "2026-11-25T17:10:00.000Z");
  assert.ok(r.details.weekly_resets_at.startsWith("2026-11-2"));
});

test("gemini: 'left' is converted to used; weekly can be the headline", () => {
  const r = parseGeminiText("Current usage 90% left Resets in 4 hours  Weekly limit 61% used Resets Friday at 9:00 AM", NOW);
  assert.equal(r.details.session_pct, 10);
  assert.equal(r.pct_used, 61);
  assert.equal(r.details.window, "weekly");
});

test("gemini: signed-out or unrecognised page is an error", () => {
  assert.throws(() => parseGeminiText("Sign in to continue to Gemini", NOW), ParseError);
  assert.throws(() => parseGeminiText("Hello there", NOW), ParseError);
});

test("reset phrases", () => {
  assert.equal(parseResetPhrase("in 45 min", NOW), "2026-11-25T15:45:00.000Z");
  assert.equal(parseResetPhrase("in 3 days", NOW), "2026-11-28T15:00:00.000Z");
  assert.equal(new Date(parseResetPhrase("Friday at 9:00 AM", NOW)).getDay(), 5);
  assert.equal(parseResetPhrase("whenever", NOW), null);
});

import { parseGrokUsageText } from "../parsers.js";

test("grok: weekly pool at 100% with extra credits (the reported case)", () => {
  const text = `Settings\nAccount\nUsage\nBilling\nUsage limits\nWeekly usage\n100% used\nResets Thursday at 9:00 AM\nChat\n71%\nImagine\n22%\nVoice\n7%\nExtra Usage Credits\n$4.20\nBuy credits`;
  const r = parseGrokUsageText(text, NOW); // NOW = Wed 2026-11-25
  assert.equal(r.pct_used, 100);
  assert.equal(r.details.weekly_pct, 100);
  assert.equal(new Date(r.resets_at).getDay(), 4); // Thursday
  assert.equal(r.details.credits, "$4.20");
});

test("grok: product lines before the total are skipped; 'left' wording; dated reset", () => {
  const r = parseGrokUsageText("Usage\nChat 40%\nImagine 10%\nWeekly limit: 35% left\nResets on Nov 27, 9:00 AM", NOW);
  assert.equal(r.pct_used, 65);
  assert.ok(r.resets_at.startsWith("2026-11-27"));
  assert.equal(r.details.credits, undefined);
});

test("grok: inline phrasing and credits after the number", () => {
  const r = parseGrokUsageText("Usage limits You've used 62% of your weekly limit. Resets in 2 days. $12.50 in extra usage credits", NOW);
  assert.equal(r.pct_used, 62);
  assert.equal(r.resets_at, "2026-11-27T15:00:00.000Z");
  assert.equal(r.details.credits, "$12.50");
});

test("grok: signed out / unrecognised", () => {
  assert.throws(() => parseGrokUsageText("Sign in to Grok", NOW), ParseError);
  assert.throws(() => parseGrokUsageText("Usage\nnothing here", NOW), ParseError);
});
