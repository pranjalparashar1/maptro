// Phone screenshots of Maptro (iPhone 14 Pro size).
// Usage: npm i maplibre-gl@4.7.1 geojson-vt@3 vt-pbf@3, then NODE_PATH=<that folder>/node_modules:$(npm root -g) node scripts/dev/screenshots.cjs . docs/screenshots
// Serves files via page.route (local http is blocked) and, because the sandbox
// cannot reach OpenFreeMap, answers tile requests with stand-in vector tiles built from a few hand-placed shapes.
const { chromium, devices } = require('playwright');
const fs = require('fs'), path = require('path');
const geojsonvt = require('geojson-vt'), vtpbf = require('vt-pbf');
const REPO = process.argv[2], OUT = process.argv[3];
const ML = path.join(path.dirname(require.resolve('maplibre-gl/package.json')), 'dist/');
const ring = (cx, cy, r, n = 48) => { const p = []; for (let i = 0; i <= n; i++) { const a = i / n * 2 * Math.PI; p.push([cx + r * Math.cos(a) * 1.14, cy + r * Math.sin(a)]); } return p; };
const yam = [[77.235,28.75],[77.232,28.70],[77.245,28.66],[77.25,28.62],[77.265,28.58],[77.28,28.54],[77.30,28.50]];
const band = (l, w) => [...l.map(p => [p[0]-w, p[1]]), ...l.slice().reverse().map(p => [p[0]+w, p[1]]), [l[0][0]-w, l[0][1]]];
const F = (layer, type, coordinates, props) => ({ type: 'Feature', properties: { layer, ...props }, geometry: { type, coordinates } });
const feats = {
  water: [F('water', 'Polygon', [band(yam, .006)])],
  park: [F('park', 'Polygon', [[[77.14,28.57],[77.19,28.63],[77.20,28.62],[77.16,28.56],[77.14,28.57]]])],
  transportation: [
    F('t', 'LineString', ring(77.21, 28.61, .075), { class: 'trunk' }),
    F('t', 'LineString', ring(77.21, 28.61, .14), { class: 'motorway' }),
    ...[[77.21,28.61,77.05,28.45],[77.21,28.61,77.35,28.50],[77.21,28.61,77.10,28.75],[77.21,28.61,77.40,28.68],[77.21,28.61,77.02,28.62]].map(([a,b,c,d]) => F('t','LineString',[[a,b],[c,d]],{class:'primary'})),
    ...Array.from({length: 30}, (_, i) => F('t','LineString',[[77.05 + i*.012, 28.45],[77.05 + i*.012 + .02, 28.78]],{class:'minor'})),
  ],
};
const idx = Object.fromEntries(Object.entries(feats).map(([k, f]) => [k, geojsonvt({ type: 'FeatureCollection', features: f }, { maxZoom: 14, buffer: 64 })]));
function tile(z, x, y) { const layers = {}; for (const [k, i] of Object.entries(idx)) { const t = i.getTile(z, x, y); if (t) layers[k] = t; } return Buffer.from(vtpbf.fromGeojsonVt(layers, { version: 2 })); }
(async () => {
  const b = await chromium.launch({ args: ['--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader'] });
  const ctx = await b.newContext({ ...devices['iPhone 14 Pro'], colorScheme: 'dark' });
  const page = await ctx.newPage();
  page.on('pageerror', e => console.log('pageerror', e.message));
  page.on('console', m => { if (m.type() === 'error') console.log('console', m.text()); });
  const target = Date.UTC(2026, 10, 24, 3, 32); // 09:02 India time
  await page.addInitScript(t => { const off = t - Date.now(); const n = Date.now.bind(Date); Date.now = () => n() + off; try { localStorage.clear(); } catch (e) {} }, target);
  await page.route('**/*', r => {
    const u = new URL(r.request().url());
    if (u.hostname === 'maptro.test') return r.fulfill({ path: path.join(REPO, u.pathname === '/' ? 'index.html' : u.pathname) });
    if (u.pathname.endsWith('maplibre-gl.js')) return r.fulfill({ path: ML + 'maplibre-gl.js', contentType: 'text/javascript' });
    if (u.pathname.endsWith('maplibre-gl.css')) return r.fulfill({ path: ML + 'maplibre-gl.css', contentType: 'text/css' });
    if (u.hostname === 'tiles.openfreemap.org' && u.pathname === '/planet') return r.fulfill({ json: { tilejson: '3.0.0', tiles: ['https://tiles.openfreemap.org/stand-in/{z}/{x}/{y}.pbf'], minzoom: 0, maxzoom: 14 } });
    const m = u.pathname.match(/stand-in\/(\d+)\/(\d+)\/(\d+)/);
    if (m) return r.fulfill({ body: tile(+m[1], +m[2], +m[3]), contentType: 'application/x-protobuf' });
    return r.abort();
  });
  await page.goto('https://maptro.test/');
  await page.waitForFunction(() => document.documentElement.dataset.ready, null, { timeout: 30000 });
  console.log('renderer', await page.evaluate(() => document.documentElement.dataset.ready));
  await page.waitForTimeout(2500);
  const shot = async n => { await page.screenshot({ path: path.join(OUT, n + '.png') }); console.log('shot', n); };
  await shot('1-home');
  await page.click('#pickw .hx'); await page.waitForTimeout(800); await shot('2-lines');
  await page.click('#none + .hx'); await page.click('#menu .row:nth-child(1) .hx'); await page.waitForTimeout(300);
  await page.click('#pickw .hx'); await page.waitForTimeout(1200); await shot('3-red');
  await page.selectOption('#dsel', '1'); await page.waitForTimeout(700); await shot('4-to-rithala');
  await page.selectOption('#dsel', 'both'); await page.waitForTimeout(3200);
  await page.evaluate(() => window.__maptro.view(77.118, 28.713, 15)); await page.waitForTimeout(1500); await shot('5-close-up');
  await page.evaluate(() => window.__maptro.view(77.16, 28.69, 13)); await page.waitForTimeout(1200); await shot('6-mid-zoom');
  const vw = 393, vh = 852;
  const pts = (await page.evaluate(() => window.__maptro.trainsOnScreen())).filter(([x, y]) => x > 60 && x < vw - 60 && y > 170 && y < vh - 300);
  if (pts.length) { await page.mouse.click(pts[0][0], pts[0][1]); await page.waitForTimeout(700); await shot('7-train'); }
  console.log('card', await page.evaluate(() => document.getElementById('card').innerText));
  if (await page.isVisible('#card .xw .hx')) { await page.click('#card .xw .hx'); await page.waitForTimeout(500); }
  // late night: the trains are asleep, skip to 8 am, then the clock can change speed
  await page.evaluate(() => { const n = Date.now.bind(Date), off = Date.UTC(2026, 10, 24, 21, 30) - n(); Date.now = () => n() + off; });
  await page.waitForTimeout(1500); await shot('8-asleep');
  if (await page.isVisible('#ff')) { await page.click('#ff + .hx'); await page.waitForTimeout(1500); await page.click('#clockw .hx'); await page.waitForTimeout(800); await shot('9-simulation'); }
  await page.click('#disc summary'); await page.waitForTimeout(500); await shot('10-disclaimer');
  // every line, an interchange close up, and the Airport Express close up
  await page.click('#disc summary'); await page.waitForTimeout(300);
  await page.click('#pickw .hx'); await page.waitForTimeout(800); await page.click('#all + .hx'); await page.click('#pickw .hx'); await page.waitForTimeout(1500);
  await page.evaluate(() => window.__maptro.view(77.2, 28.62, 11)); await page.waitForTimeout(1500); await shot('11-all-lines');
  await page.evaluate(() => window.__maptro.view(77.228, 28.666, 14.6)); await page.waitForTimeout(1500); await shot('12-interchange');
  await page.click('#pickw .hx'); await page.waitForTimeout(800); await page.click('#none + .hx'); await page.click('#menu .row:nth-child(9) .hx'); await page.click('#pickw .hx'); await page.waitForTimeout(1500);
  await page.evaluate(() => { const ll = window.__maptro.trainLonLat(0) || [77.095, 28.556]; window.__maptro.view(ll[0], ll[1], 15); }); await page.waitForTimeout(150); await shot('13-airport-close-up');
  const bg = await page.evaluate(() => getComputedStyle(document.body).backgroundColor); console.log('body bg', bg);
  await b.close();
})();
