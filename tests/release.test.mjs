// Run: node --test tests/*.test.mjs
// The app's version, its offline worker and its install manifest agree (1.11).
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync, existsSync } from 'node:fs';

const read = f => readFileSync(new URL('../' + f, import.meta.url), 'utf8');
const html = read('index.html'), sw = read('sw.js'), log = read('CHANGELOG.md');

test('index.html, sw.js and CHANGELOG.md name the same version', () => {
  const app = html.match(/const VERSION = '([\d.]+)'/)[1];
  assert.equal(sw.match(/const VERSION = '([\d.]+)'/)[1], app, 'sw.js VERSION');
  assert.equal(log.match(/^## ([\d.]+),/m)[1], app, "CHANGELOG.md's newest entry");
});

test('the manifest is installable: standalone, true black, icons that exist', () => {
  const m = JSON.parse(read('manifest.webmanifest'));
  assert.equal(m.display, 'standalone');
  assert.equal(m.background_color, '#000000'); assert.equal(m.theme_color, '#000000');
  for (const s of ['192x192', '512x512']) assert.ok(m.icons.some(i => i.sizes === s && i.purpose.includes('any')), s);
  assert.ok(m.icons.some(i => i.purpose.includes('maskable')));
  for (const i of m.icons) assert.ok(existsSync(new URL('../' + i.src, import.meta.url)), i.src);
  assert.match(html, /<link rel="manifest" href="manifest.webmanifest">/);
});

test('sw.js saves files that exist, and the MapLibre that index.html loads first', () => {
  const shell = JSON.parse(sw.match(/const SHELL = (\[.*?\]);/)[1].replace(/'/g, '"'));
  for (const f of shell) if (f !== './') assert.ok(existsSync(new URL('../' + f, import.meta.url)), f);
  const cdn = html.match(/const CDN = \['([^']+)'/)[1];
  assert.ok(sw.includes(`'${cdn}'`), 'sw.js LIB_URLS has ' + cdn);
  assert.ok(sw.includes(`'${cdn.replace(/\.js$/, '.css')}'`), 'and its stylesheet');
  new Function(sw);
});

test('every line in the picker has a short code', () => {
  const order = eval(html.match(/const ORDER = (\[.*?\]);/)[1]), codes = eval('(' + html.match(/const CODES = (\{.*?\});/)[1] + ')');
  for (const l of order) assert.ok(codes[l], l);
  assert.equal(new Set(Object.values(codes)).size, Object.values(codes).length, 'codes are unique');
});
