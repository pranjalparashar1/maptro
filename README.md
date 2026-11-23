# Maptro — Delhi Metro, by timetable

Every Delhi Metro train drawn where DMRC's published timetable says it should be right now. Like [ScanPaname](https://scanpaname.com/en) for Paris, positions are **scheduled, not live**: DMRC doesn't publish live train data.

**Live page:** https://pranjalparashar1.github.io/maptro/

## Data
- DMRC static GTFS from Delhi's Open Transit Data portal (otd.delhi.gov.in): 262 stations, 36 routes, last updated Aug 2023, calendar expired 31 Dec 2025. The map ignores the expiry and runs the weekday timetable every day.
- Running times are scaled per line to Google Maps end-to-end ride times (24 Nov 2026, 11:00), from `scripts/calibration.json`. The build prints each change.
- Missing from the feed: Airport Line to Yashobhoomi Dwarka Sec 25, Magenta to Krishna Park Extension, Magenta Deepali Chowk–Majlis Park and Pink Majlis Park–Maujpur (Mar 2026).

## Rebuild
```
python3 scripts/audit.py path/to/DMRC_GTFS   # data-quality checks
python3 scripts/build.py path/to/DMRC_GTFS   # writes data.json
```
Then serve the folder (`python3 -m http.server`) and open index.html.

## Checking it
The page has a "Train arrived now" logger: stand on a platform, tap when each train stops, and it reports the gap to the nearest scheduled arrival plus the observed headway.
