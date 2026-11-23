// Caches only the app shell. Usage data is never cached.
const SHELL = "ai-usage-shell-v1";
const FILES = ["./", "manifest.webmanifest", "icon.svg"];
self.addEventListener("install", (e) => e.waitUntil(caches.open(SHELL).then((c) => c.addAll(FILES))));
self.addEventListener("activate", (e) => e.waitUntil(
  caches.keys().then((ks) => Promise.all(ks.filter((k) => k !== SHELL).map((k) => caches.delete(k))))));
self.addEventListener("fetch", (e) => {
  const url = new URL(e.request.url);
  if (e.request.method !== "GET" || url.pathname.endsWith("/usage.json")) return;
  e.respondWith(fetch(e.request).catch(() => caches.match(e.request, {ignoreSearch: true})));
});
