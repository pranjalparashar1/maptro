// Stand-in basemap for the dev scripts: the sandbox and CI can't (or shouldn't) reach OpenFreeMap, so tile requests
// get vector tiles built from a few hand-placed shapes (a Yamuna band, a park, ring roads, a street grid), and the
// MapLibre that index.html asks the CDN for comes from node_modules. Used by screenshots.cjs and browser-check.cjs.
// Needs: npm i maplibre-gl@4.7.1 geojson-vt@3 vt-pbf@3
const path = require('path');
const geojsonvt = require('geojson-vt'), vtpbf = require('vt-pbf');
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
// Answers a Playwright route for MapLibre's CDN files and OpenFreeMap; returns false for anything else.
function standIn(r) {
  const u = new URL(r.request().url());
  if (u.pathname.endsWith('maplibre-gl.js')) return r.fulfill({ path: ML + 'maplibre-gl.js', contentType: 'text/javascript', headers: { 'access-control-allow-origin': '*' } });
  if (u.pathname.endsWith('maplibre-gl.css')) return r.fulfill({ path: ML + 'maplibre-gl.css', contentType: 'text/css', headers: { 'access-control-allow-origin': '*' } });
  if (u.hostname === 'tiles.openfreemap.org' && u.pathname === '/planet') return r.fulfill({ json: { tilejson: '3.0.0', tiles: ['https://tiles.openfreemap.org/stand-in/{z}/{x}/{y}.pbf'], minzoom: 0, maxzoom: 14 }, headers: { 'access-control-allow-origin': '*' } });
  const m = u.pathname.match(/stand-in\/(\d+)\/(\d+)\/(\d+)/);
  if (m) return r.fulfill({ body: tile(+m[1], +m[2], +m[3]), contentType: 'application/x-protobuf', headers: { 'access-control-allow-origin': '*' } });
  return false;
}
module.exports = { standIn };
