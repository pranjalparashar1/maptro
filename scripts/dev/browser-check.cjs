// Browser check (1.11), run in CI by .github/workflows/test.yml: opens Maptro in a phone-sized Chromium at a fixed
// moment (09:02 India time, Tuesday 24 Nov 2026) over a real local server, and fails if it breaks.
//   - it renders with MapLibre, with no page errors, and trains are running
//   - pixels: the Airport Express track is drawn in its colour, and the trains are drawn white
//   - a station card shows line codes; the Tab key reaches the text view first, and it lists stations and times
//   - the Disclaimer shows the version
//   - offline: after one visit, with the network off, it opens again and the trains run
// Pixel snapshots compared with saved pictures were left out on purpose: WebGL and system fonts differ between
// machines, so they fail for reasons that aren't bugs, and Maptro's looks are judged on a phone (DESIGN.md, 10).
// The screenshots it takes are kept as a CI artifact to look at.
// Usage: npm i playwright maplibre-gl@4.7.1 geojson-vt@3 vt-pbf@3, then
//   NODE_PATH=<that folder>/node_modules node scripts/dev/browser-check.cjs . out
const { chromium, devices } = require('playwright');
const fs = require('fs'), path = require('path'), http = require('http');
const { standIn } = require('./standin.cjs');
const REPO = path.resolve(process.argv[2] || '.'), OUT = process.argv[3] || 'browser-check';
const TYPES = { '.html': 'text/html', '.json': 'application/json', '.js': 'text/javascript', '.webmanifest': 'application/manifest+json', '.png': 'image/png', '.svg': 'image/svg+xml', '.md': 'text/markdown' };
const AE = [0xff, 0x8a, 0x12], INK = [0xf4, 0xf4, 0xf4];
let failed = 0;
const check = (ok, what) => { console.log(`${ok ? 'ok  ' : 'FAIL'} ${what}`); if (!ok) failed++; };
const near = (p, c, tol) => p && Math.max(...c.map((v, i) => Math.abs(v - p[i]))) <= tol;

const server = http.createServer((req, res) => {
  const u = new URL(req.url, 'http://x'), f = path.join(REPO, u.pathname.endsWith('/') ? u.pathname + 'index.html' : u.pathname);
  if (!f.startsWith(REPO) || !fs.existsSync(f)) { res.writeHead(404); return res.end(); }
  res.sendDate = false; // no Date header, so Maptro's clock check leaves the faked time alone
  res.writeHead(200, { 'content-type': TYPES[path.extname(f)] || 'application/octet-stream' });
  res.end(req.method === 'HEAD' ? undefined : fs.readFileSync(f));
});

(async () => {
  await new Promise(r => server.listen(0, '127.0.0.1', r));
  const URL0 = `http://localhost:${server.address().port}/`;
  fs.mkdirSync(OUT, { recursive: true });
  const b = await chromium.launch({ args: ['--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader'] });
  const ctx = await b.newContext({ ...devices['iPhone 14 Pro'], colorScheme: 'dark', serviceWorkers: 'allow' });
  await ctx.route(/^https:/, r => standIn(r) || r.abort());
  const target = Date.UTC(2026, 10, 24, 3, 32);
  await ctx.addInitScript(t => { const off = t - Date.now(); const n = Date.now.bind(Date); Date.now = () => n() + off; }, target);
  const page = await ctx.newPage(), errors = [];
  page.on('pageerror', e => errors.push(e.message));
  // the PNG of a screenshot, decoded in the page, so a pixel can be read without a PNG library
  const pixels = async () => { const png = (await page.screenshot()).toString('base64');
    return page.evaluate(async src => { const i = new Image(); i.src = 'data:image/png;base64,' + src; await i.decode();
      const c = document.createElement('canvas'); c.width = i.width; c.height = i.height; const x = c.getContext('2d'); x.drawImage(i, 0, 0);
      window.__px = { w: i.width, d: x.getImageData(0, 0, i.width, i.height).data, s: i.width / innerWidth }; }, png); };
  const px = (x, y) => page.evaluate(([x, y]) => { const p = window.__px, X = Math.round(x * p.s), Y = Math.round(y * p.s), k = (Y * p.w + X) * 4; return [p.d[k], p.d[k + 1], p.d[k + 2]]; }, [x, y]);
  const ready = () => page.waitForFunction(() => document.documentElement.dataset.ready && window.__maptro, null, { timeout: 30000 });
  const shot = n => page.screenshot({ path: path.join(OUT, n + '.png') });

  await page.goto(URL0); await ready(); await page.waitForTimeout(2500);
  check(await page.evaluate(() => document.documentElement.dataset.ready) === 'maplibre', 'renders with MapLibre');
  const n = (await page.evaluate(() => window.__maptro.trainsOnScreen())).length;
  check(n > 0, `trains running at 09:02 (${n})`);
  await shot('1-home');

  await page.keyboard.press('Tab');
  check(await page.evaluate(() => document.activeElement.id) === 'tvl', 'the first Tab reaches "Text view"');
  await page.waitForTimeout(400); await shot('3-text-view-link');
  await page.keyboard.press('Enter'); await page.waitForTimeout(300);
  check(await page.evaluate(() => document.getElementById('tv').open), 'Enter opens the text view');
  const tv = await page.$eval('#tvb', e => e.innerText);
  check(/Airport Express Line/.test(tv) && /\d+ trains? running/.test(tv), 'it names the line and its trains running');
  check(/New Delhi\s+to .+ (in \d+ min|now)/.test(tv), 'and each station\'s next train');
  await shot('4-text-view');
  await page.keyboard.press('Escape');
  check(!(await page.evaluate(() => document.getElementById('tv').open)), 'Escape closes it');



  await pixels();
  let track = 0; for (const f of [.2, .3, .4, .6, .7]) { const [x, y] = await page.evaluate(f => window.__maptro.trackXY('ORANGE/AIRPORT', f), f); if (near(await px(x, y), AE, 40)) track++; }
  check(track >= 3, `Airport Express track drawn in its colour (${track} of 5 points)`);
  const tr = await page.evaluate(() => window.__maptro.trainsOnScreen()); let white = 0;
  for (const [x, y] of tr) if (near(await px(x, y), INK, 40)) white++;
  check(white > 0, `trains drawn white (${white} of ${tr.length})`);

  const nd = await page.evaluate(() => window.__maptro.stationXY('New Delhi'));
  await page.mouse.click(nd[0], nd[1]); await page.waitForTimeout(600);
  const codes = await page.$$eval('#card .su .lc', e => e.map(x => x.textContent));
  check(codes.includes('AE') && codes.includes('Y'), `New Delhi's card shows line codes (${codes.join(' ')})`);
  check(/Airport Express Line/.test(await page.$eval('#card .su', e => e.textContent)), 'and names the lines for screen readers');
  await shot('2-station-card');
  await page.click('#card .xw .hx'); await page.waitForTimeout(400);

  await page.click('#disc summary'); await page.waitForTimeout(400);
  const ver = await page.$eval('#ver', e => e.textContent), app = fs.readFileSync(path.join(REPO, 'index.html'), 'utf8').match(/const VERSION = '([\d.]+)'/)[1];
  check(ver === app, `the Disclaimer shows Maptro ${ver}`);
  await shot('5-disclaimer');

  const sw = await page.evaluate(async () => { const r = await navigator.serviceWorker.ready; return !!r.active; });
  check(sw, 'the offline worker is installed');
  await page.reload(); await ready(); await page.waitForTimeout(1500);
  check(await page.evaluate(() => !!navigator.serviceWorker.controller), 'and controls the page');
  await ctx.setOffline(true); await ctx.unrouteAll({ behavior: 'ignoreErrors' }); await ctx.route(/^https:/, r => r.abort());
  errors.length = 0;
  await page.reload(); await ready(); await page.waitForTimeout(2000);
  check(await page.evaluate(() => document.documentElement.dataset.ready) === 'maplibre', 'offline: opens, with MapLibre from the saved copy');
  check((await page.evaluate(() => window.__maptro.trainsOnScreen())).length > 0, 'offline: trains running');
  await shot('6-offline');
  check(!errors.length, `no page errors${errors.length ? ': ' + errors.join('; ') : ''}`);

  await b.close(); server.close();
  console.log(failed ? `${failed} check(s) failed` : 'all checks passed');
  process.exit(failed ? 1 : 0);
})().catch(e => { console.error(e); process.exit(1); });
