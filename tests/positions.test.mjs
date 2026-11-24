// Run: node --test tests/*.test.mjs
// Tests the timetable/geometry block of index.html (between /*<core>*/ and /*</core>*/).
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

const html = readFileSync(new URL('../index.html', import.meta.url), 'utf8');
const src = html.split('/*<core>*/')[1].split('/*</core>*/')[0];
const load = () => new Function(src + '\nreturn {DAY,nowIST,dayKey,useDay,merc,unmerc,prepare,stateAt,runAt,profile,ACCEL,DECEL,posAt,headingAt,directions,trainsAt,trailPoints,departures,lowerBound,clockSkew,SKEW_MIN,provenance,serviceOn,plainService,firstDeparture,skipTarget,Buf,polyline,ribbon};')();
const core = load();
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

test('trains are where the timetable says at every stop, and on the same stretch as before in between', () => {
  // the pre-kinematics algorithm (straight-line in time), kept as the reference for which stop a train is at or after
  const ref = (r, e) => { const p = r.pat; let i = 0; while (i < p.length - 1 && p[i + 1][1] <= e) i++;
    return { i, dwell: e <= p[i][2] || i === p.length - 1 }; };
  for (const r of R) {
    for (let e = 0; e < r.dur; e += 13) {
      const s = core.stateAt(r, e), q = ref(r, e);
      assert.equal(s.i, q.i, r.id); assert.equal(s.dwell, q.dwell, `${r.id} e=${e}`);
      assert.ok(s.d >= r.pat[s.i][3] - 1e-6 && s.d <= (r.pat[s.i + 1] || r.pat[s.i])[3] + 1e-6, `${r.id} left its stretch at e=${e}`);
    }
    for (const q of r.pat) { assert.equal(core.stateAt(r, q[1]).d, q[3]); assert.equal(core.stateAt(r, q[2]).d, q[3]); }
  }
});

// Speed (m/s) t seconds into run k, by a central difference.
const speed = (r, k, t, h = .05) => (core.runAt(r, k, t + h) - core.runAt(r, k, t - h)) / (2 * h);
const VMAX = Number(html.match(/const VMAX = ([\d.]+)/)[1]);
const TOP = line => (line === 'ORANGE/AIRPORT' ? 120 : 80) / 3.6; // build.py LINE_VMAX

test('trains pull away and brake: still at each stop, never over the rates or the line\'s top speed', () => {
  let peak = 0;
  for (const r of R) for (let k = 0; k < r.pat.length - 1; k++) {
    const L = r.pat[k + 1][3] - r.pat[k][3], T = r.pat[k + 1][1] - r.pat[k][2];
    if (!(L > 0)) continue;
    assert.equal(r.ka[k], core.ACCEL, `${r.id} run ${k} is too short for the rates (${L} m in ${T} s)`);
    assert.ok(r.kv[k] <= TOP(r.line) + .01, `${r.id} run ${k} peaks at ${(r.kv[k] * 3.6).toFixed(1)} km/h`);
    peak = Math.max(peak, r.kv[k]);
    assert.ok(speed(r, k, .05) < .1 && speed(r, k, T - .05) < .1, `${r.id} run ${k} doesn't start and end at rest`);
    let v0 = 0;
    for (let t = .5; t < T; t += .5) {
      const v = speed(r, k, t, .25);
      assert.ok(v >= -1e-6 && v <= r.kv[k] + 1e-6, `${r.id} run ${k} speed ${v} at ${t}`);
      assert.ok((v - v0) / .5 <= core.ACCEL + .02 && (v0 - v) / .5 <= core.DECEL + .02, `${r.id} run ${k} jerks at ${t}`);
      v0 = v;
    }
  }
  assert.ok(peak <= VMAX, `fastest train ${peak.toFixed(1)} m/s, over the frame loop's VMAX ${VMAX}`);
});

test('a run too short for the rates still arrives on time, without going backwards', () => {
  const r = { pat: [[0, 0, 20, 0], [1, 40, 60, 1000]] }; core.profile(r); // 1 km in 20 s
  assert.ok(r.ka[0] > core.ACCEL);
  let prev = 0;
  for (let t = 0; t <= 20; t += .25) { const s = core.runAt(r, 0, t); assert.ok(s >= prev - 1e-9); prev = s; }
  assert.equal(core.runAt(r, 0, 20), 1000); assert.ok(Math.abs(core.runAt(r, 0, 20 - 1e-9) - 1000) < 1e-3);
});

test('rides still match the Google Maps times they were calibrated to', () => {
  const cal = JSON.parse(readFileSync(new URL('../scripts/calibration.json', import.meta.url), 'utf8'));
  for (const c of cal.lines) {
    if (c.hold) continue;
    for (const [a, b] of [[c.from, c.to], [c.to, c.from]]) {
      let best = null;
      for (const r of R) {
        if (r.line !== c.line) continue;
        const ids = r.pat.map(p => p[0]), i = ids.indexOf(a), j = ids.indexOf(b);
        if (i >= 0 && j > i && (!best || j - i > best.n)) best = { n: j - i, t: r.pat[j][1] - r.pat[i][2] };
      }
      assert.ok(best, c.label);
      assert.ok(Math.abs(best.t - c.minutes * 60) <= 3, `${c.label}: ${(best.t / 60).toFixed(2)} min, Google ${c.minutes}`);
    }
  }
});

test('trains wait longer at interchanges than at other stops', () => {
  const dw = n => { const out = new Set(); for (const r of R) for (const p of r.pat.slice(1, -1)) if (D.stops[p[0]][0] === n) out.add(p[2] - p[1]); return [...out]; };
  assert.deepEqual(dw('Rajiv Chowk'), [35]);
  assert.deepEqual(dw('Kashmere Gate'), [35]);
  assert.deepEqual(dw('Patel Chowk'), [20]);
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

test('every line splits into two directions with named ends', () => {
  const dirs = core.directions(D);
  const name = id => D.stops[id][0];
  assert.deepEqual(dirs.RED, { a: 'Rithala', b: 'Shaheed Sthal (New Bus Adda)' });
  assert.deepEqual(dirs['ORANGE/AIRPORT'], { a: 'Yashobhoomi Dwarka Sector 25', b: 'New Delhi' });
  for (const r of R) {
    assert.ok(r.dir === 0 || r.dir === 1, r.id);
    if (r.line === 'RED') assert.equal(r.dir, name(r.pat[0][0]) === 'Rithala' ? 0 : 1, r.id);
    if (r.line === 'ORANGE/AIRPORT') assert.equal(r.dir, name(r.pat.at(-1)[0]) === 'New Delhi' || name(r.pat[0][0]) === 'Yashobhoomi Dwarka Sector 25' ? 0 : 1, r.id);
  }
  // both directions together are every train, and neither is empty by day
  const red = R.filter(r => r.line === 'RED'), t = H(9);
  const n0 = core.trainsAt(red.filter(r => r.dir === 0), t, null).length, n1 = core.trainsAt(red.filter(r => r.dir === 1), t, null).length;
  assert.ok(n0 > 3 && n1 > 3);
  assert.equal(n0 + n1, core.trainsAt(R, t, new Set(['RED'])).length);
});

test('heading is a unit vector pointing the way the train moves', () => {
  for (const o of core.trainsAt(R, H(10), null)) {
    const [hx, hy] = core.headingAt(o.r, o.d);
    assert.ok(Math.abs(Math.hypot(hx, hy) - 1) < 1e-6, o.r.id);
    const end = o.r.md[o.r.md.length - 1];
    if (o.d > 200 && o.d < end - 200) { const a = core.posAt(o.r, o.d - 100), b = core.posAt(o.r, o.d + 100);
      assert.ok(hx * (b[0] - a[0]) + hy * (b[1] - a[1]) > 0, `${o.r.id} heading backwards`); }
  }
});

test('the timetable follows the India service day, turning over at 3 am', () => {
  assert.equal(core.dayKey(Date.UTC(2026, 10, 24, 6, 0)), 'wkd'); // Tue 11:30 IST
  assert.equal(core.dayKey(Date.UTC(2026, 10, 28, 6, 0)), 'sat');
  assert.equal(core.dayKey(Date.UTC(2026, 10, 29, 6, 0)), 'sun');
  assert.equal(core.dayKey(Date.UTC(2026, 10, 29, 20, 0)), 'sun'); // Mon 01:30 IST is still Sunday's service
  assert.equal(core.dayKey(Date.UTC(2026, 10, 29, 22, 0)), 'wkd'); // Mon 03:30 IST
});

test('Sundays run fewer trains than weekdays, and switching back restores the weekday', () => {
  const wkd = core.trainsAt(R, H(9.5), null).length;
  core.useDay(D, 'sun'); const sun = core.trainsAt(R, H(9.5), null).length;
  core.useDay(D, 'wkd');
  assert.ok(sun < wkd * 0.8, `${sun} vs ${wkd}`);
  assert.equal(core.trainsAt(R, H(9.5), null).length, wkd);
});

test('branch trains alternate on shared track instead of doubling up', () => {
  // DMRC, 31 Aug 2026: Dwarka-Yamuna Bank every 2:51 at weekday peak; Ashok Park-Mundka every 4:10
  for (const [line, stop, want] of [['BLUE', 'Rajiv Chowk', 171], ['GREEN', 'Punjabi Bagh', 250]]) {
    const ids = new Set(Object.entries(D.stops).filter(([, s]) => s[0] === stop).map(([k]) => +k));
    for (const dir of [0, 1]) {
      const ts = [];
      for (const r of R) if (r.line === line && r.dir === dir) for (const p of r.pat) if (ids.has(p[0]))
        for (const s of r.starts) { const x = s + p[2]; if (x >= H(9.5) && x < H(11.5)) ts.push(x); }
      ts.sort((a, b) => a - b);
      const gaps = ts.slice(1).map((x, i) => x - ts[i]);
      assert.ok(gaps.length > 20 && Math.min(...gaps) > 60, `${line} ${dir}: min gap ${Math.min(...gaps)}`);
      assert.ok(Math.abs(gaps.reduce((a, b) => a + b) / gaps.length - want) < 5, `${line} ${dir} mean gap`);
    }
  }
});

// ---- 1.6: honest clock, 32-bit index buffers ----

test('all lines and every peak train fit the index buffers, with nothing dropped', t => {
  const ids = new Set(R.map(r => r.id)), V = new core.Buf(Float32Array), I = new core.Buf(Uint32Array);
  let want = 0;
  for (const r of R) { // the whole network's track, as buildStatic draws it with every line chosen
    if (r.id.endsWith('_R') && ids.has(r.id.slice(0, -2))) continue;
    const pts = []; for (let i = 0; i < r.mx.length; i++) pts.push([r.mx[i], r.my[i]]);
    core.polyline(V, I, pts, [1, 1, 1, 1]); want += 6 * (pts.length - 1);
  }
  assert.equal(I.n, want, 'every track segment drawn');
  assert.ok(Math.max(...I.view()) < V.n / 11, 'indices point at real vertices');
  t.diagnostic(`track: ${V.n / 11} vertices`);
  for (const at of [H(9), H(18.5)]) { // every train at peak, as long ribbons with generous padding
    const tV = new core.Buf(Float32Array), tI = new core.Buf(Uint32Array), ts = core.trainsAt(R, at, null);
    let drawn = 0;
    for (const o of ts) { const n0 = tI.n; core.ribbon(tV, tI, o.r, o.d - 150, o.d + 150, 1, 40); if (tI.n > n0) drawn++; }
    assert.equal(drawn, ts.length, 'a ribbon for every train');
    assert.ok(Math.max(...tI.view()) < tV.n / 9);
    t.diagnostic(`${ts.length} trains at ${at / 3600}h: ${tV.n / 9} vertices`);
  }
});

test('16-bit index buffers stop at the cap and warn, instead of wrapping round', () => {
  const c = load(), V = new c.Buf(Float32Array), I = new c.Buf(Uint16Array), warn = console.warn, said = [];
  console.warn = m => said.push(m);
  try {
    V.n = 65530 * 11; V.need(0); // 65,530 vertices already in
    c.polyline(V, I, [[0, 0], [1, 0], [2, 0]], [1, 1, 1, 1]); // would need vertices 65,530 to 65,535: fits
    assert.equal(I.n, 12);
    c.polyline(V, I, [[0, 0], [1, 0]], [1, 1, 1, 1]); // would need 65,536 and up: skipped
    assert.equal(I.n, 12);
    assert.equal(said.length, 1);
  } finally { console.warn = warn; }
});

test('clock skew: ignored within 2 minutes, measured beyond it', () => {
  const t0 = Date.UTC(2026, 10, 24, 6, 0, 0), at = ms => new Date(ms).toUTCString();
  assert.equal(core.clockSkew(t0, t0 + 200, at(t0 + 100)), 0);           // in step
  assert.equal(core.clockSkew(t0, t0 + 200, at(t0 + 90000)), 0);         // 1.5 min out: left alone
  const slow = core.clockSkew(t0, t0 + 200, at(t0 + 7 * 60000));         // phone 7 min behind
  assert.ok(Math.abs(slow - 7 * 60000) <= 1000, String(slow));
  const fast = core.clockSkew(t0, t0 + 200, at(t0 - 3 * 3600000));       // phone 3 h ahead
  assert.ok(Math.abs(fast + 3 * 3600000) <= 1000, String(fast));
  assert.equal(core.clockSkew(t0, t0 + 200, null), 0);                    // no Date header
  assert.equal(core.clockSkew(t0, t0 + 200, 'not a date'), 0);
  assert.equal(core.clockSkew(t0, t0 + 20000, at(t0 + 3600000)), 0);     // answer too slow to trust
});

test('a corrected clock picks the right India time and service day', () => {
  const phone = Date.UTC(2026, 10, 27, 21, 28, 0); // Sat 28 Nov, 02:58 in India by a phone 3 min slow
  const off = core.clockSkew(phone, phone, new Date(phone + 180000).toUTCString());
  assert.equal(core.dayKey(phone), 'wkd');       // still Friday's service day by the phone
  assert.equal(core.dayKey(phone + off), 'sat'); // past 03:00: Saturday's
  assert.ok(Math.abs(core.nowIST(phone + off) - (3 * 3600 + 60 + 0.5)) < 1); // really 03:01
});

test('the Disclaimer names the timetable and the day it runs', () => {
  const p = core.provenance(D.meta, 'wkd');
  assert.match(p, /31 Aug 2026/);
  assert.match(p, /Aug 2023/);
  assert.match(p, /weekday timetable/);
  assert.match(core.provenance(D.meta, 'sat'), /Saturday timetable/);
  assert.match(core.provenance(D.meta, 'sun'), /Sunday timetable/);
  assert.doesNotMatch(p, /live/i);
});

test('the clock says Now, and nothing on screen says Live', () => {
  const body = html.split('<body>')[1].split('<script>')[0].replace(/<[^>]+>/g, ' ');
  assert.doesNotMatch(body, /\bLive\b/);
  assert.match(html, /id="spd">Now</);
  assert.match(html, /sim \? speed \+ '×' : 'Now'/);
});

// Times in India (IST) as UTC ms: ist(2026, 11, 29, 6, 30) is 06:30 on Sun 29 Nov 2026 in Delhi.
const ist = (y, mo, d, h, mi = 0) => Date.UTC(y, mo - 1, d, h, mi) - 19800000;
const atMs = ms => { core.useDay(D, core.serviceOn(D.meta, ms)); return core.trainsAt(R, core.nowIST(ms), null); };
const lineSet = ts => new Set(ts.map(o => o.r.line));

test('Sunday trains start later: none on Pink, Magenta or Grey at 06:30, as on a weekday', () => {
  const sun = lineSet(atMs(ist(2026, 11, 29, 6, 30))), wkd = lineSet(atMs(ist(2026, 11, 30, 6, 30)));
  for (const l of ['PINK', 'MAGENTA', 'GRAY']) { assert.ok(!sun.has(l), `${l} on Sunday`); assert.ok(wkd.has(l), `${l} on Monday`); }
  assert.ok(sun.has('YELLOW') && sun.has('BLUE'));
  core.useDay(D, core.serviceOn(D.meta, ist(2026, 11, 29, 6, 30)));
  for (const r of R) if (D.meta.service.sun_first[r.line]) assert.ok(r.starts.every(s => s >= D.meta.service.sun_first[r.line]), r.id);
  core.useDay(D, 'wkd');
});

test('a train out before midnight on Saturday finishes on Saturday\'s timetable', () => {
  const sat = ist(2026, 11, 28, 23, 55), sun = ist(2026, 11, 29, 0, 10);
  assert.equal(core.serviceOn(D.meta, sun).tt, 'sat');
  const before = atMs(sat).filter(o => o.e + 15 * 60 < o.r.dur), after = atMs(sun);
  assert.ok(before.length > 0);
  for (const o of before) assert.ok(after.some(a => a.r === o.r && a.s0 === o.s0), `${o.r.id} ${o.s0} vanished at midnight`);
  assert.equal(core.serviceOn(D.meta, ist(2026, 11, 29, 3, 1)).tt, 'sun');
  core.useDay(D, 'wkd');
});

test('special days: Holi starts at 14:30 on the weekday timetable, Diwali is a Sunday that ends early', () => {
  const holi = core.serviceOn(D.meta, ist(2026, 3, 4, 10));
  assert.equal(holi.name, 'Holi'); assert.equal(holi.tt, 'wkd');
  assert.equal(atMs(ist(2026, 3, 4, 10)).length, 0);
  assert.ok(atMs(ist(2026, 3, 4, 15)).length > 100);
  assert.equal(core.serviceOn(D.meta, ist(2026, 3, 5, 1)).name, 'Holi'); // 01:00 next morning is still Holi's service
  const dw = core.serviceOn(D.meta, ist(2026, 11, 8, 12));
  assert.equal(dw.tt, 'sun'); assert.equal(dw.last, 22 * 3600);
  assert.ok(lineSet(atMs(ist(2026, 11, 8, 6, 30))).has('PINK'), 'Pink starts at 06:00 on Diwali');
  for (const r of R) assert.ok(r.starts.every(s => s <= 22 * 3600), r.id);
  assert.equal(core.serviceOn(D.meta, ist(2026, 11, 15, 12)).name, null); // the next Sunday is a plain one
  core.useDay(D, 'wkd');
});

test('a public holiday listed as a Sunday runs the Sunday timetable on a weekday', () => {
  const meta = { ...D.meta, service: { ...D.meta.service, days: { '2027-01-26': { name: 'Republic Day', tt: 'sun' } } } };
  const sv = core.serviceOn(meta, ist(2027, 1, 26, 9));
  assert.equal(sv.tt, 'sun'); assert.equal(sv.first.PINK, 7 * 3600);
  assert.equal(core.serviceOn(meta, ist(2027, 1, 27, 9)).tt, 'wkd');
  core.useDay(D, sv); const hol = core.trainsAt(R, H(9.5), null).length;
  core.useDay(D, 'wkd'); assert.ok(hol < core.trainsAt(R, H(9.5), null).length * 0.8);
});

test('Skip goes to the next 8 am, or to the first train on a day that starts later', () => {
  const skip = (ms, l) => core.skipTarget(D, ms, l ? new Set(l) : null);
  assert.equal(skip(ist(2026, 11, 29, 1)), ist(2026, 11, 29, 8));   // Sun 01:00 (Saturday's service): Sunday 08:00
  assert.equal(skip(ist(2026, 11, 28, 23, 50)), ist(2026, 11, 29, 8));
  const near = (a, b) => assert.ok(a >= b && a - b < 60000, `${new Date(a).toISOString()} vs ${new Date(b).toISOString()}`);
  near(skip(ist(2026, 3, 4, 10)), ist(2026, 3, 4, 14, 30)); // Holi morning: the first train, later the same day
  near(skip(ist(2026, 3, 4, 1)), ist(2026, 3, 4, 14, 30));
});

test('the Disclaimer names special days and simulated days', () => {
  assert.match(core.provenance(D.meta, core.serviceOn(D.meta, ist(2026, 3, 4, 15))), /Today runs the weekday timetable, with DMRC's Holi timings/);
  assert.match(core.provenance(D.meta, 'sun', true), /The simulated day runs the Sunday timetable/);
});

test('data.json says where every special day comes from, and stays small', () => {
  const svc = JSON.parse(readFileSync(new URL('../scripts/service_days.json', import.meta.url), 'utf8'));
  for (const [k, d] of Object.entries(svc.special_days)) if (!k.startsWith('_')) assert.ok(d.source && d.name && d.timetable, k);
  assert.ok(readFileSync(new URL('../data.json', import.meta.url)).length < 250000);
});
