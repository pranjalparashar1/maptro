"""Check every station in data.json against OpenStreetMap and list the ones that are off.

Usage:
  python3 scripts/audit_osm.py                       # asks the Overpass API (needs network)
  python3 scripts/audit_osm.py --osm saved.json      # uses a saved Overpass JSON answer instead
  python3 scripts/audit_osm.py --save-osm osm.json --fixes stop_coord_fixes.json
  python3 scripts/audit_osm.py --print-query         # the query, to run by hand on overpass-turbo.eu

It prints a Markdown report: stations whose point in data.json is more than --threshold metres
(default 150) from the matching OSM station, and stations it could not match at all. With --fixes it
also writes the OSM coordinates of the far ones as JSON, for review. Nothing is applied: a fix only
reaches the map once it is copied into STOP_FIXES in build.py with its source.

Matching: an OSM station matches a stop when its name (or name:en, alt_name, old_name, ...) is close
to the stop's name and it lies within --radius metres (default 5000; the worst feed error found so
far was 4.4 km). Interchanges are often mapped as one OSM station per line, so the nearest of the
equally good name matches is used. Only the standard library is needed.
"""
import argparse, datetime, difflib, json, math, os, re, sys, urllib.parse, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
MARGIN = 0.05  # degrees (~5 km) added round the stops' own extent for the Overpass bounding box
OVERPASS = "https://overpass-api.de/api/interpreter"
# Delhi Metro stations are tagged inconsistently (station=subway, station=light_rail, subway=yes, or
# only network/operator), so several filters are combined. Indian Railways and Namo Bharat stations
# carry none of these and stay out.
QUERY = """[out:json][timeout:180];
(
  nwr["railway"="station"]["station"~"^(subway|light_rail|monorail)$"]({b});
  nwr["railway"="station"]["subway"="yes"]({b});
  nwr["public_transport"="station"]["subway"="yes"]({b});
  nwr["railway"="station"]["network"~"Delhi Metro|Rapid Metro|Noida Metro|Aqua",i]({b});
  nwr["railway"="station"]["operator"~"DMRC|Delhi Metro|NMRC|Noida Metro|Rapid Metro",i]({b});
);
out center tags;"""
NAME_KEYS = ("name:en", "name", "official_name", "alt_name", "old_name", "short_name", "int_name")
MIN_SCORE = 0.8
GENERIC = {"east", "west", "north", "south", "rapid", "m i a"}
# Our name (normalised) -> the name OSM uses, for stations it names differently. Checked by hand, 24 Nov 2026.
ALIASES = {
    "barakhamba": "barakhambha road",
    "rk ashram marg": "ramakrishna ashram marg",
    "badarpur border": "badarpur",
    "iit": "iit delhi",
    "mayur vihar pocket 1": "shree ram mandir mayur vihar",  # renamed; OSM uses the new name
    "udyog bhawan": "seva teerth",  # renamed 14 Feb 2026 (Wikipedia)
}


def hv(lat1, lon1, lat2, lon2):
    """Metres between two points."""
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * 6371008.8 * math.asin(math.sqrt(a))


def norm(name):
    s = name.lower().replace("&", " and ")
    s = re.sub(r"\bsec(tor)?\b\.?", "sector", s)
    s = re.sub(r"\b(metro station|metro|station|rly|railway)\b", " ", s)
    s = re.sub(r"[^a-z0-9]+", " ", s)
    s = " ".join({"i": "1", "ii": "2", "iii": "3", "iv": "4"}.get(w, w) for w in s.split())  # Phase-I, Mayur Vihar-II
    return s


def aliases(name):
    """'Sant Surdas (Sihi)' -> {'sant surdas sihi', 'sant surdas', 'sihi'}"""
    out = {norm(name)}
    inner = re.findall(r"\(([^)]*)\)", name)
    if inner:
        out.add(norm(re.sub(r"\([^)]*\)", " ", name)))
        # '(Sihi)' or '(New Bus Adda)' are other names for the station; '(East)' or '(Rapid Metro)' are not
        out.update(n for n in map(norm, inner) if n not in GENERIC)
    out |= {ALIASES[a] for a in out if a in ALIASES}
    return {a for a in out if a}


def score(a, b):
    """Name similarity, 0..1. Names with different numbers never match. A whole-word subset ('kashmere gate' in 'kashmere gate isbt') counts as 0.9."""
    best = 0.0
    for x in a:
        for y in b:
            nx, ny = set(re.findall(r"\d+", x)), set(re.findall(r"\d+", y))
            if nx and ny and nx != ny:
                continue  # 'phase 1' is not 'phase 3', 'sector 18' is not 'sector 81'
            r = difflib.SequenceMatcher(None, x, y).ratio()
            tx, ty = set(x.split()), set(y.split())
            if tx and ty and (tx <= ty or ty <= tx) and min(len(tx), len(ty)) >= 2:
                r = max(r, 0.9)
            if x.replace(" ", "") == y.replace(" ", ""):
                r = 1.0
            best = max(best, r)
    return best


def osm_stations(doc):
    """Overpass JSON -> [{id, lat, lon, name, names}] (ways and relations use their centre)."""
    out = []
    for el in doc.get("elements", []):
        tags = el.get("tags", {})
        lat = el.get("lat", el.get("center", {}).get("lat"))
        lon = el.get("lon", el.get("center", {}).get("lon"))
        if lat is None or lon is None:
            continue
        names = set()
        for k in NAME_KEYS:
            for v in tags.get(k, "").split(";"):
                names |= aliases(v) if v.strip() else set()
        if not names:
            continue
        out.append(dict(id=f"{el['type']}/{el['id']}", lat=lat, lon=lon,
                        name=tags.get("name:en") or tags.get("name"), names=names))
    return out


def match(stops, osm, radius=5000.0):
    """stops: {id: [name, lon, lat]} as in data.json. Returns one result per stop."""
    res = []
    for sid, (name, lon, lat) in stops.items():
        mine = aliases(name)
        near = [(hv(lat, lon, o["lat"], o["lon"]), o) for o in osm]
        near = [(d, o) for d, o in near if d <= radius]
        scored = [(score(mine, o["names"]), d, o) for d, o in near]
        good = [x for x in scored if x[0] >= MIN_SCORE]
        r = dict(id=sid, name=name, lat=lat, lon=lon)
        if good:
            top = max(s for s, _, _ in good)
            s, d, o = min((x for x in good if x[0] >= top - 0.05), key=lambda x: x[1])
            r.update(status="matched", score=round(s, 2), dist=d, osm=o)
        else:
            r["status"] = "unmatched"
            if near:
                d, o = min(near, key=lambda x: x[0])
                r.update(nearest=o, dist=d)
        res.append(r)
    return res


def report(res, threshold, src):
    far = sorted((r for r in res if r["status"] == "matched" and r["dist"] > threshold), key=lambda r: -r["dist"])
    un = [r for r in res if r["status"] == "unmatched"]
    ok = sum(1 for r in res if r["status"] == "matched" and r["dist"] <= threshold)
    L = [f"# Station coordinates vs OpenStreetMap", "",
         f"Source: {src}", "",
         f"{len(res)} stops checked: {ok} within {threshold:g} m of their OSM station, "
         f"{len(far)} further off, {len(un)} not matched by name.", ""]
    if far:
        L += [f"## More than {threshold:g} m from OSM", "",
              "| Stop | Name | Off by | data.json (lat, lon) | OSM | OSM name | OSM (lat, lon) |",
              "|---|---|---:|---|---|---|---|"]
        for r in far:
            o = r["osm"]
            L.append(f"| {r['id']} | {r['name']} | {r['dist']:.0f} m | {r['lat']:.6f}, {r['lon']:.6f} | "
                     f"[{o['id']}](https://www.openstreetmap.org/{o['id']}) | {o['name']} | {o['lat']:.6f}, {o['lon']:.6f} |")
        L.append("")
    if un:
        L += ["## Not matched", "",
              "No OSM station with a similar name nearby. Either OSM names it differently or the stop is far off.", "",
              "| Stop | Name | Nearest OSM station |", "|---|---|---|"]
        for r in un:
            n = r.get("nearest")
            L.append(f"| {r['id']} | {r['name']} | " + (f"{n['name']} ({r['dist']:.0f} m)" if n else "none in range") + " |")
        L.append("")
    return "\n".join(L), far


def fixes(far, src):
    return {r["id"]: dict(name=r["name"], lat=round(r["osm"]["lat"], 7), lon=round(r["osm"]["lon"], 7),
                          moved_m=round(r["dist"]), source=f"OpenStreetMap {r['osm']['id']} ({src})")
            for r in far}


def bbox(stops, margin=MARGIN):
    """south, west, north, east round all stops. A fixed Delhi NCR box (28.35-28.90 N) would miss
    Raja Nahar Singh in Ballabhgarh, at 28.34 N."""
    lats = [v[2] for v in stops.values()]; lons = [v[1] for v in stops.values()]
    return (round(min(lats) - margin, 2), round(min(lons) - margin, 2), round(max(lats) + margin, 2), round(max(lons) + margin, 2))


def load(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def save(path, text):
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)


def fetch(url, bbox):
    q = QUERY.format(b=",".join(f"{x:g}" for x in bbox))
    req = urllib.request.Request(url, data=urllib.parse.urlencode({"data": q}).encode(),
                                 headers={"User-Agent": "station-coord-audit/1.0 (python-urllib)"})
    with urllib.request.urlopen(req, timeout=240) as f:
        return json.load(f)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--data", default=os.path.join(HERE, "..", "data.json"))
    ap.add_argument("--osm", help="saved Overpass JSON to use instead of asking the API")
    ap.add_argument("--save-osm", help="also save the Overpass answer here")
    ap.add_argument("--overpass", default=OVERPASS)
    ap.add_argument("--threshold", type=float, default=150, help="metres (default 150)")
    ap.add_argument("--radius", type=float, default=5000, help="search radius in metres (default 5000)")
    ap.add_argument("--fixes", help="write OSM coordinates of the far stops here, as JSON")
    ap.add_argument("--out", help="write the report here as well as printing it")
    ap.add_argument("--print-query", action="store_true",
                    help="print the Overpass query and stop (paste it into overpass-turbo.eu, export the JSON, pass it as --osm)")
    ap.add_argument("--strict", action="store_true", help="exit 1 if any stop is far off or unmatched")
    a = ap.parse_args(argv)
    stops = load(a.data)["stops"]
    if a.print_query:
        print(QUERY.format(b=",".join(f"{x:g}" for x in bbox(stops))))
        return 0
    if a.osm:
        doc = load(a.osm); src = f"saved Overpass answer {os.path.basename(a.osm)}"
        if doc.get("osm3s", {}).get("timestamp_osm_base"):
            src += f", OSM data as of {doc['osm3s']['timestamp_osm_base']}"
    else:
        try:
            doc = fetch(a.overpass, bbox(stops))
        except OSError as e:
            raise SystemExit(f"could not reach Overpass at {a.overpass}: {e}. Save an answer elsewhere and pass --osm.")
        src = f"Overpass API, {datetime.date.today().isoformat()}"
        if doc.get("osm3s", {}).get("timestamp_osm_base"):
            src += f", OSM data as of {doc['osm3s']['timestamp_osm_base']}"
    if a.save_osm:
        save(a.save_osm, json.dumps(doc))
    osm = osm_stations(doc)
    if not osm:
        sys.exit("no metro stations in the OSM answer; check the query or the saved file")
    text, far = report(match(stops, osm, a.radius), a.threshold, f"{src}; {len(osm)} OSM stations")
    print(text)
    if a.out:
        save(a.out, text + "\n")
    if a.fixes:
        save(a.fixes, json.dumps(fixes(far, src), indent=1, ensure_ascii=False) + "\n")
    if a.strict and (far or "## Not matched" in text):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
