"""One-off: pull OpenStreetMap geometry and station points for the Phase 4 sections
that the 2023 DMRC feed lacks, and write scripts/phase4_geometry.json.

Neither OSM's API nor Overpass was reachable from the build machine, so this
reads an OSM extract already converted to GTFS in github.com/Cubestormer-IV/MetroMapper
(commit a5ab3e3, 27 Oct 2026). That project's scripts say its new-section shapes
and station points come from OSM (delhi_metro_lines.geojson / delhi_metro_stations.geojson).
Data (c) OpenStreetMap contributors, ODbL.

Usage: python3 scripts/phase4_extract.py path/to/MetroMapper/app/src/main/assets/data/gtfs/metro
"""
import csv, json, os, sys

SRC = sys.argv[1]
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "phase4_geometry.json")
SHAPES = {"airport": "shp_osm_AEx", "magenta_kpe": "shp_osm_8", "magenta_north": "shp_magenta_ext", "pink_ring": "shp_pink_ring"}
STOPS = {  # our key -> MetroMapper stop_id
    "yashobhoomi": "121_orange_ext", "krishna_park_ext": "108_magenta_ext",
    "bhalaswa": "529", "haiderpur_village": "531", "uttari_pitampura": "532", "madhuban_chowk": "533", "deepali_chowk": "534",
    "burari": "528", "jharoda_majra": "527", "jagatpur_wazirabad": "526", "soorghat": "524", "nanaksar_sonia_vihar": "525",
    "khajuri_khas": "523", "bhajanpura": "522", "yamuna_vihar": "521",
}
pts = {}
with open(f"{SRC}/shapes.txt") as f:
    for r in csv.DictReader(f):
        if r["shape_id"] in SHAPES.values():
            pts.setdefault(r["shape_id"], []).append((int(r["shape_pt_sequence"]), round(float(r["shape_pt_lon"]), 6), round(float(r["shape_pt_lat"]), 6)))
stops = {}
with open(f"{SRC}/stops.txt") as f:
    for r in csv.DictReader(f):
        for k, v in STOPS.items():
            if r["stop_id"] == v: stops[k] = [round(float(r["stop_lon"]), 6), round(float(r["stop_lat"]), 6)]
missing = set(STOPS) - set(stops)
if missing: sys.exit(f"missing stops: {missing}")
out = dict(source="OpenStreetMap (c) OpenStreetMap contributors, ODbL; via github.com/Cubestormer-IV/MetroMapper @a5ab3e3 (27 Oct 2026)",
           shapes={k: [[x, y] for _, x, y in sorted(pts[v])] for k, v in SHAPES.items()}, stops=stops)
json.dump(out, open(OUT, "w"), separators=(",", ":"))
print(OUT, {k: len(v) for k, v in out["shapes"].items()})
