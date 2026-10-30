// The engine's files (engine/<version>/...: Pyodide, the packs, the plan) never change under their versioned path:
// they are served from the Cache API once fetched, for the page and its workers (a second build downloads nothing).
// Everything else goes to the network as usual.
const CACHE = 'horizon-engine';

self.addEventListener('install', () => self.skipWaiting());
self.addEventListener('activate', (e) => e.waitUntil(self.clients.claim()));

self.addEventListener('fetch', (e) => {
  const url = new URL(e.request.url);
  if (e.request.method !== 'GET' || url.origin !== self.location.origin || !/\/engine\/[0-9a-f]{12}\//.test(url.pathname)) return;
  e.respondWith((async () => {
    const c = await caches.open(CACHE);
    const hit = await c.match(e.request, { ignoreVary: true });
    if (hit) return hit;
    const r = await fetch(e.request);
    if (r.ok) { try { await c.put(e.request, r.clone()); } catch { /* quota */ } }
    return r;
  })());
});
