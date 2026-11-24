# Maptro — Delhi Metro, by timetable

Every Delhi Metro train drawn where DMRC's published timetable says it should be right now. Like [ScanPaname](https://scanpaname.com/en) for Paris, positions are **scheduled, not live**: DMRC doesn't publish live train data.

**Live page:** https://pranjalparashar1.github.io/maptro/

## Data
- DMRC static GTFS from Delhi's Open Transit Data portal (otd.delhi.gov.in): 262 stations, 36 routes, last updated Aug 2023, calendar expired 31 Dec 2025. The map ignores the expiry. Its run times and service hours are still used.
- Departure times come from DMRC's published train frequencies (delhimetrorail.com/train-frequency, as on 31 Aug 2026), in `scripts/frequency.json`, with separate weekday, Saturday and Sunday timetables. Branch trains alternate on shared track, and trains turn back where DMRC's section figures say they do (Blue at Dwarka, Green at Mundka, Yellow at Vishwavidyalaya). The first and last trains and the peak hours (08:00–12:00, 17:00–21:00) are the 2023 feed's, since DMRC's table doesn't give them. Rapid Metro and Aqua keep the feed's weekday times every day. See `scripts/headways.py`; the build prints a check of every section against DMRC's figure.
- Running times are scaled per line to Google Maps end-to-end ride times (24 Nov 2026, 11:00), from `scripts/calibration.json`. The build prints each change.
- Missing from the feed: Airport Line to Yashobhoomi Dwarka Sec 25, Magenta to Krishna Park Extension, Magenta Deepali Chowk–Majlis Park and Pink Majlis Park–Maujpur (Mar 2026). Green Line trains' stop at Punjabi Bagh West (opened Mar 2022) is added by the build.

## Rebuild
```
python3 scripts/audit.py path/to/DMRC_GTFS   # data-quality checks
python3 scripts/build.py path/to/DMRC_GTFS   # writes data.json
```
Then serve the folder (`python3 -m http.server`) and open index.html.

## Data checks
- `python3 scripts/audit_osm.py` compares every station in data.json with its OpenStreetMap station (via the Overpass API) and lists the ones more than 150 m off, plus any it can't match by name. `--fixes stop_coord_fixes.json` writes OSM's coordinates for those, for review; nothing is applied until it's copied into `STOP_FIXES` in build.py with its source. Without network access, run `--print-query` on overpass-turbo.eu and pass the exported JSON with `--osm`.
- `.github/workflows/check-gtfs.yml` runs every Monday (and by hand from the Actions tab). It downloads DMRC's GTFS from Open Transit Data and compares its contents with `scripts/gtfs_feed.json`. If DMRC has published a new feed, it audits and test-builds it, keeps the results as a run artifact and opens an issue. It also runs the OSM check and puts the report in the run summary.

## The page
- `index.html` is the whole app, with no build step. It draws the lines, stations and trains with WebGL as a MapLibre GL custom layer over an OpenStreetMap basemap (OpenFreeMap vector tiles in Maptro's own true-black style). MapLibre 4.7.1 comes from jsDelivr (unpkg as a second try). If neither loads, the same WebGL renderer runs on its own canvas with its own pan and pinch, just without the basemap.
- It opens on the Airport Express. Pick lines from the dropdown; only those lines, their stations and their trains are drawn. Station names appear by zoom level and never overlap. The choice is remembered in the browser.
- Trains glide every frame (`requestAnimationFrame`, so 120 Hz on ProMotion phones) drawn as white dots when zoomed out and as white bullets with a faint glow when zoomed in, never anything between. A zoomed-in train is laid along the track itself, so it bends through curves. Trains slide into a station's dot when they arrive and out of it when they leave. The track is a flat band in the line's full colour, two trains wide, and each direction keeps to its own (left-hand) side. With one line chosen, a direction dropdown shows both directions or just one, and a note says how many trains are active. Tap a train for its next stop and Follow it; tap a station for its next departures. When no trains run, Skip to 8 am starts a simulation, and only then can the clock run at 1×, 10× or 60×.

## Design
How it looks, moves and behaves, and the checklist for any change: [DESIGN.md](DESIGN.md).

## Tests
```
node --test tests/*.test.mjs
```
They load the `/*<core>*/` block of index.html (all the timetable and position logic) and check it against data.json.
```
python3 -m unittest discover -s tests -p 'test_*.py'
```
These cover the two data-check scripts, offline, against fixtures in `tests/fixtures/`.
