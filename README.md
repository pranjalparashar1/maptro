# Maptro — Delhi Metro, by timetable

Every Delhi Metro train drawn where DMRC's published timetable says it should be right now. Like [ScanPaname](https://scanpaname.com/en) for Paris, positions are **scheduled, not live**: DMRC doesn't publish live train data.

**Live page:** https://pranjalparashar1.github.io/maptro/

## Data
- DMRC static GTFS from Delhi's Open Transit Data portal (otd.delhi.gov.in): 262 stations, 36 routes, last updated Aug 2023, calendar expired 31 Dec 2025. The map ignores the expiry and runs the weekday timetable every day.
- Running times are scaled per line to Google Maps end-to-end ride times (24 Nov 2026, 11:00), from `scripts/calibration.json`. The build prints each change.
- Missing from the feed: Airport Line to Yashobhoomi Dwarka Sec 25, Magenta to Krishna Park Extension, Magenta Deepali Chowk–Majlis Park and Pink Majlis Park–Maujpur (Mar 2026). Green Line trains' stop at Punjabi Bagh West (opened Mar 2022) is added by the build.

## Rebuild
```
python3 scripts/audit.py path/to/DMRC_GTFS   # data-quality checks
python3 scripts/build.py path/to/DMRC_GTFS   # writes data.json
```
Then serve the folder (`python3 -m http.server`) and open index.html.

## The page
- `index.html` is the whole app, with no build step. It draws the lines, stations and trains with WebGL as a MapLibre GL custom layer over an OpenStreetMap basemap (OpenFreeMap vector tiles in Maptro's own true-black style). MapLibre 4.7.1 comes from jsDelivr (unpkg as a second try). If neither loads, the same WebGL renderer runs on its own canvas with its own pan and pinch, just without the basemap.
- It opens on the Airport Express. Pick lines from the dropdown; only those lines, their stations and their trains are drawn. Station names appear by zoom level and never overlap. The choice is remembered in the browser.
- Trains glide every frame (`requestAnimationFrame`, so 120 Hz on ProMotion phones) drawn as white dots when zoomed out and, zoomed in, as white bullets with a faint glow, nose first so you can see which way they're heading. The track is a flat band in the line's full colour, two trains wide, and each direction keeps to its own (left-hand) side. Stations are drawn as their platforms. Every shape comes from one unit, a train's width (see DESIGN.md). With one line chosen, a direction dropdown shows both directions or just one, and a note says how many trains are active. Tap a train for its next stop and Follow it; tap a station for its next departures. When no trains run, Skip to 8 am starts a simulation, and only then can the clock run at 1×, 10× or 60×.

## Design
How it looks, moves and behaves, and the checklist for any change: [DESIGN.md](DESIGN.md).

## Tests
```
node --test tests/*.test.mjs
```
They load the `/*<core>*/` block of index.html (all the timetable and position logic) and check it against data.json.
