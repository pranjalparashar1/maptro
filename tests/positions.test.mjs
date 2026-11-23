// Run: node --test tests/*.test.mjs
// Tests the timetable/geometry block of index.html (between /*<core>*/ and /*</core>*/).
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

const html = readFileSync(new URL('../index.html', import.meta.url), 'utf8');
const src = html.split('/*<core>*/')[1].split('/*</core>*/')[0];
const core = new Function(src + '\nreturn {DAY,nowIST,merc,unmerc,prepare,stateAt,posAt,trainsAt,trailPoints,departures,lowerBound};')();
const D = core.prepare(JSON.parse(readFileSync(new URL('../data.json', import.meta.url), 'utf8')));
const R = D.routes;
const H = h => h * 3600;

test('every inline script parses', () => {
  for (const m of html.matchAll(/<script>([\s\S]*?)<\/script>/g)) new Function(m[1]);
});

test('IST clock is UTC+05:30', () => {
  assert.equal(core.nowIST(Date.UTC(2026, 10, 23, 0, 0, 0)), 19800);
  assert.equal(core.nowIST(Date.UTC(2026, 10, 23, 20, 0, 0)), 5400); // 01:30 next day
});

test('mercator round-trips', () => {
  const [x, y] = core.merc(77.2, 28.6), [lon, lat] = core.unmerc(x, y);
  assert.ok(Math.abs(lon - 77.2) < 1e-9 && Math.abs(lat - 28.6) < 1e-9);
});

test('trainsAt matches a brute-force scan over all trips', () => {
  for (const t of [H(5.5), H(9), H(13.25), H(18.5), H(23.4), H(0.2)]) {
    let brute = 0;
    for (const r of R) for (const tt of [t, t + core.DAY]) for (const s of r.starts) { const e = tt - s; if (e >= 0 && e <= r.dur) brute++; }
    assert.equal(core.trainsAt(R, t, null).length, brute, `count at ${t}`);
  }
});

test('plenty of trains by day, none at 3 am', () => {
  assert.ok(core.trainsAt(R, H(9), null).length > 150);
  assert.equal(core.trainsAt(R, H(3), null).length, 0);
});

test('line filter only returns chosen lines', () => {
  const ts = core.trainsAt(R, H(9), new Set(['YELLOW']));
  assert.ok(ts.length > 10 && ts.every(o => o.r.line === 'YELLOW'));
});

test('positions stay in Delhi NCR and on the route shape', () => {
  const [x0, y0] = core.merc(76.8, 28.9), [x1, y1] = core.merc(77.7, 28.3);
  for (const t of [H(7), H(12), H(20)]) for (const o of core.trainsAt(R, t, null)) {
    const [x, y, tx, ty] = o.pos;
    assert.ok(x > x0 && x < x1 && y > y0 && y < y1, `${o.r.id} out of bounds`);
    assert.ok(Math.abs(Math.hypot(tx, ty) - 1) < 1e-6, 'unit tangent');
  }
});

test('distance never goes backwards along a trip, and dwells sit at stops', () => {
  for (const r of R) {
    let prev = -1;
    for (let e = 0; e <= r.dur; e += 7) {
      const s = core.stateAt(r, e);
      assert.ok(s.d >= prev - 1e-6, `${r.id} reversed at e=${e}`); prev = s.d;
      if (s.dwell) assert.equal(s.d, r.pat[s.i][3]);
    }
    assert.equal(core.stateAt(r, r.dur).d, r.pat[r.pat.length - 1][3]);
  }
});

test('interpolation matches the original linear scan', () => {
  // the pre-redesign index.html algorithm, kept as the reference
  const ref = (r, e) => { const p = r.pat; let i = 0; while (i < p.length - 1 && p[i + 1][1] <= e) i++;
    if (e <= p[i][2]) return p[i][3]; const a = p[i], b = p[i + 1]; return a[3] + (b[3] - a[3]) * ((e - a[2]) / ((b[1] - a[2]) || 1)); };
  for (const r of R) for (let e = 0; e < r.dur; e += 13) assert.ok(Math.abs(core.stateAt(r, e).d - ref(r, e)) < 1e-6, r.id);
});

test('posAt hits shape endpoints and is continuous', () => {
  for (const r of R) {
    const n = r.md.length, a = core.posAt(r, r.md[0]), b = core.posAt(r, r.md[n - 1]);
    assert.ok(Math.abs(a[0] - r.mx[0]) < 1e-12 && Math.abs(b[1] - r.my[n - 1]) < 1e-12);
    let last = core.posAt(r, 0);
    for (let d = 0; d <= r.md[n - 1]; d += 50) { const p = core.posAt(r, d);
      assert.ok(Math.hypot(p[0] - last[0], p[1] - last[1]) < 60 / 4e7 * 1.5 * 2, `${r.id} jump at ${d}`); last = p; }
  }
});

test('trails run oldest to newest and end at the train', () => {
  for (const o of core.trainsAt(R, H(10), null).slice(0, 80)) {
    const pts = core.trailPoints(o.r, o.e, 50);
    if (!pts.length) continue;
    for (let i = 1; i < pts.length; i++) assert.ok(pts[i][2] >= pts[i - 1][2]);
    const h = pts[pts.length - 1];
    assert.ok(Math.abs(h[0] - o.pos[0]) < 1e-12 && Math.abs(h[1] - o.pos[1]) < 1e-12);
  }
});

test('departures are upcoming and sorted', () => {
  const rc = new Set(Object.entries(D.stops).filter(([, s]) => s[0] === 'Rajiv Chowk').map(([k]) => +k));
  const t = H(9), ds = core.departures(R, rc, t, null, 4);
  assert.equal(ds.length, 4);
  for (let i = 0; i < ds.length; i++) { assert.ok(ds[i].time >= t && ds[i].time < t + 600); if (i) assert.ok(ds[i].time >= ds[i - 1].time); }
});

test('estimated Phase 4 trains appear', () => {
  assert.ok(core.trainsAt(R, H(9), null).some(o => o.r.est));
});
