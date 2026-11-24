// Maptro's service worker (1.11): once Maptro has been opened, it opens again and the trains run with no signal.
//
// - The page and the timetable (index.html, data.json): network first, so a new timetable shows as soon as it is
//   published. Only when the network fails, or takes over 3 seconds, does the saved copy load, and the network's
//   answer still updates it for next time. (Stale-while-revalidate would open one visit behind every change.)
// - MapLibre from the CDN: saved once. The URLs name an exact version, so they never change under a saved copy.
// - Basemap tiles: kept as they are seen, up to MAX_TILES, oldest dropped first. Their URLs name the tile set's
//   version too. With no saved tiles the map is black and the trains still run, as when the tiles fail anyway.
// - Nothing else is touched: the clock check (a HEAD request) always goes to the network.
const VERSION = '1.11'; // the same as index.html's VERSION; a new one replaces the saved app on the next visit
const APP = 'maptro-app-' + VERSION, TILES = 'maptro-tiles', MAX_TILES = 600, WAIT = 3000;
const SHELL = ['./', 'data.json', 'manifest.webmanifest', 'icons/icon.svg', 'icons/icon-192.png', 'icons/apple-touch-icon.png'];
// index.html's first choice of MapLibre, saved at install too: the first visit loads it before this worker runs
const LIB_URLS = ['https://cdn.jsdelivr.net/npm/maplibre-gl@4.7.1/dist/maplibre-gl.js', 'https://cdn.jsdelivr.net/npm/maplibre-gl@4.7.1/dist/maplibre-gl.css'];
const LIB = /^https:\/\/(cdn\.jsdelivr\.net\/npm|unpkg\.com)\/maplibre-gl@\d+\.\d+\.\d+\//;
const TILE_HOST = 'tiles.openfreemap.org';

self.addEventListener('install', e => {
  e.waitUntil(caches.open(APP).then(c => Promise.all([
    c.addAll(SHELL.map(u => new Request(u, { cache: 'reload' }))),
    ...LIB_URLS.map(u => c.add(new Request(u, { mode: 'cors' })).catch(() => {})), // a CDN that's down mustn't stop the install
  ])).then(() => self.skipWaiting()));
});
self.addEventListener('activate', e => {
  e.waitUntil(caches.keys().then(ks => Promise.all(ks.filter(k => k.startsWith('maptro-app-') && k !== APP).map(k => caches.delete(k))))
    .then(() => self.clients.claim()));
});

self.addEventListener('fetch', e => {
  const req = e.request;
  if (req.method !== 'GET') return;
  const u = new URL(req.url);
  if (u.origin === location.origin) {
    // every visit to the page, whatever its query, is saved as one copy of the page
    const key = req.mode === 'navigate' ? new URL('./', location.href).href : u.origin + u.pathname;
    return e.respondWith(networkFirst(e, req, key));
  }
  if (LIB.test(req.url)) return e.respondWith(cacheFirst(APP, req));
  if (u.hostname === TILE_HOST) return e.respondWith(/\.(pbf|mvt)$/.test(u.pathname) ? cacheFirst(TILES, req, true) : networkFirst(e, req, req.url, TILES));
});

async function networkFirst(e, req, key, name = APP) {
  const cache = await caches.open(name);
  const net = fetch(req).then(r => { if (r.ok) cache.put(key, r.clone()); return r; });
  e.waitUntil(net.then(() => {}, () => {}));
  const saved = await cache.match(key);
  if (!saved) return net;
  return Promise.race([net.then(r => r.ok ? r : saved, () => saved), new Promise(res => setTimeout(() => res(saved), WAIT))]);
}

let puts = 0;
async function cacheFirst(name, req, trim = false) {
  const cache = await caches.open(name), saved = await cache.match(req);
  if (saved) return saved;
  const r = await fetch(req);
  if (r.ok) {
    await cache.put(req, r.clone());
    if (trim && ++puts % 50 === 0) { const ks = await cache.keys(); for (const k of ks.slice(0, Math.max(0, ks.length - MAX_TILES))) await cache.delete(k); }
  }
  return r;
}
