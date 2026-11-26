// Runs INSIDE a grok.com tab (via chrome.scripting.executeScript). Opens Settings -> Usage
// if needed and returns the page's visible text. Kept dependency-free so it can be injected.
export async function grokUsagePageText() {
  const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
  const text = () => (document.body ? document.body.innerText : "");
  const onUsage = () => /%/.test(text()) && /(weekly|usage limits?)/i.test(text()) && /resets?|renews?/i.test(text());
  const visible = (e) => !!(e.offsetWidth || e.offsetHeight || e.getClientRects().length);
  const click = (re) => {
    const els = [...document.querySelectorAll("button, a, [role=tab], [role=menuitem], [role=button], [role=link], [tabindex]")];
    const el = els.find((e) => visible(e) && re.test(`${e.getAttribute("aria-label") || ""} ${(e.innerText || "").trim()}`.trim()));
    if (el) el.click();
    return !!el;
  };
  const waitFor = async (cond, ms) => { for (let t = 0; t < ms; t += 500) { if (cond()) return true; await sleep(500); } return cond(); };

  await waitFor(() => text().length > 50, 15000);        // app shell rendered
  if (await waitFor(onUsage, 2000)) return text();         // already on the Usage tab

  // Settings may be a direct button, or inside the profile/avatar menu
  if (!click(/^settings$/i)) {
    click(/(profile|account|avatar|user menu|open menu)/i);
    await sleep(800);
    click(/^settings$/i);
  }
  await waitFor(() => /usage/i.test(text()), 5000);
  click(/^usage( (&|and) billing)?$/i);
  await waitFor(onUsage, 10000);
  return text();
}
