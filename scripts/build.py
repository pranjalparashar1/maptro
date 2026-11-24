"""DMRC GTFS -> data.json, with documented fixes for known feed bugs.

Usage: python3 scripts/build.py path/to/DMRC_GTFS [path/to/phase4.json]

Fixes applied (each is printed when the build runs):
  1. Service: the feed's only "saturday" trips (R_RS_R, 59 Red Line trips) are
     treated as daily. There is no Sunday service and no other route uses
     "saturday", so these look like mislabelled weekday trips.
  2. Station coordinates: six stops in the feed sit 0.9-4.4 km from the real
     station, and the feed's shapes were routed through those wrong points, so
     trains drove out to them and back. STOP_FIXES below has the corrected
     coordinates and their sources. Shape vertices at a wrong point move with it.
  3. Shape spurs: out-and-back hairpins left in the shapes (mostly caused by 2)
     are removed, and shape distances and stop positions are recomputed for
     any route that changed.
  4. Impossible speeds: a segment whose run time is shorter than a train
     could manage (top speed LINE_VMAX, ACCEL away and DECEL braking) is lengthened to
     that minimum, and the time is taken from slack in the trip's other
     segments, so trip start and end times stay as published.
  5. Run times: the feed's running times are scaled line by line so end-to-end
     rides match published ride times (calibration.json, from Google Maps).
     See calibrate() below.
  6. New stops: stations that opened after the feed, on lines it already has, are inserted
     from STOP_INSERTS (Punjabi Bagh West on Green), before calibration.
  7. Dwells: the feed stops every train for 20 s everywhere. Interchanges get DWELL_INTERCHANGE
     instead, and the extra time comes out of the two runs either side, so every other stop keeps
     its time and calibrated rides are unchanged. See tier_dwells() below.
Estimated sections (Phase 4 openings not in the feed) come from phase4.json,
see scripts/phase4.py. They take their speeds from the uncalibrated feed.
"""
import pandas as pd, json, math, os, sys, copy
D = sys.argv[1] if len(sys.argv) > 1 else "DMRC_GTFS"
HERE = os.path.dirname(os.path.abspath(__file__))
P4 = sys.argv[2] if len(sys.argv) > 2 else os.path.join(HERE, "phase4.json")
CAL = os.path.join(HERE, "calibration.json")
OUT = "data.json"

SERVICE_AS_DAILY = {"R_RS_R"}
# stop_id: (lat, lon, source). Stops the feed places more than ~800 m from the real station, which
# makes trains double back or reach impossible speeds. Fixed only where English Wikipedia's station
# article gives a precise coordinate (read 23 Nov 2026) and the DMRC app backend's station catalogue
# (backend.delhimetrorail.com, as captured in github.com/tashifkhan/delhi-metro @faf5ced, 20 Nov 2026)
# also puts the feed's point far off.
W = "en.wikipedia.org/wiki/{}_metro_station (read 23 Nov 2026)"
STOP_FIXES = {
    36: (28.7450431, 77.1376725, W.format("Samaypur_Badli")),
    38: (28.729923, 77.14913, W.format("Haiderpur_Badli_Mor")),
    40: (28.716535, 77.170452, W.format("Adarsh_Nagar")),          # feed had it beside GTB Nagar
    97: (28.6422, 77.1783, W.format("Rajendra_Place")),            # feed had it east of Karol Bagh
    196: (28.6834099, 77.0173627, W.format("Mundka_Industrial_Area")),  # feed had it west of Ghevra
    205: (28.5758068, 77.1985707, W.format("Sarojini_Nagar")),
}
# Top operating speed in km/h. DMRC metro lines run at up to 80 km/h; the Airport Line at 120 km/h
# since 17 Sep 2023 (DMRC, reported by India TV and india.com that day).
LINE_VMAX = {"ORANGE/AIRPORT": 120}
VMAX_DEFAULT = 80
# m/s^2, average acceleration from a stand to line speed and average service braking. Assumptions for DMRC stock
# (rated about 1.0 at the start of a run, falling off with speed). index.html moves trains with the same two rates
# (ACCEL and DECEL in its core block), so a run time this build allows is one the page can draw at or under LINE_VMAX.
ACCEL, DECEL = 0.85, 0.9
HAIRPIN_DEG = 30
# Stations opened after the feed was made, on routes the feed already has. (line, after, before, stop_id,
# dwell s, source): every route of `line` that runs after->before, or before->after, gets the stop
# between them. The run time is split by distance, the dwell is added, and later times shift by it.
# Calibration then rescales the line, so the added dwell doesn't change calibrated ride times.
STOP_INSERTS = [
    ("GREEN", 33, 32, 176, 20, "Green Line platforms at Punjabi Bagh West, between Punjabi Bagh and Shivaji Park, "
     "opened 29 Mar 2022 (PTI in The Tribune that day); Google Maps lists the stop on Green trains (24 Nov 2026)"),
]

r = pd.read_csv(f"{D}/routes.txt"); s = pd.read_csv(f"{D}/stops.txt"); t = pd.read_csv(f"{D}/trips.txt")
st = pd.read_csv(f"{D}/stop_times.txt"); sh = pd.read_csv(f"{D}/shapes.txt")
f = lambda x: sum(int(a) * b for a, b in zip(x.split(':'), (3600, 60, 1)))
st['a'] = st.arrival_time.map(f); st['d'] = st.departure_time.map(f)
st = st.sort_values(['trip_id', 'stop_sequence'])
col = {'RED': '#e2231a', 'YELLOW': '#f5c400', 'BLUE': '#1663be', 'GREEN': '#2f9e44', 'VIOLET': '#7d3c98', 'PINK': '#ee5ca4', 'MAGENTA': '#b0127e', 'GRAY': '#8d939a', 'AQUA': '#18b7c9', 'ORANGE/AIRPORT': '#f08519', 'RAPID': '#3d7fd1'}
notes = []
def note(msg):
    notes.append(msg); print("fix:", msg)

def hv(a, b):  # metres between (lon, lat) points
    R = 6371008.8; p1, p2 = math.radians(a[1]), math.radians(b[1]); dl = math.radians(b[0] - a[0]); dp = p2 - p1
    return 2 * R * math.asin(math.sqrt(math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2))
KX = math.cos(math.radians(28.62))
def angle(a, b, c):
    v1 = ((a[0] - b[0]) * KX, a[1] - b[1]); v2 = ((c[0] - b[0]) * KX, c[1] - b[1])
    n = math.hypot(*v1) * math.hypot(*v2)
    return 180.0 if n == 0 else math.degrees(math.acos(max(-1, min(1, (v1[0] * v2[0] + v1[1] * v2[1]) / n))))

def clean_shape(pts):
    """Drop repeated points and out-and-back hairpins. pts: [(lon, lat)]. Returns (pts, removed)."""
    out = [pts[0]]
    for p in pts[1:]:
        if hv(out[-1], p) >= 1: out.append(p)
    removed = 0; changed = True
    while changed:
        changed = False
        for i in range(1, len(out) - 1):
            if angle(out[i - 1], out[i], out[i + 1]) < HAIRPIN_DEG:
                del out[i]; removed += 1; changed = True
                if hv(out[i - 1], out[i]) < 1: del out[i]
                break
    return out, removed

def with_dist(pts):
    d = 0.0; res = [(pts[0][0], pts[0][1], 0.0)]
    for a, b in zip(pts, pts[1:]):
        d += hv(a, b); res.append((b[0], b[1], d))
    return res

def project(shape, pt, dmin):
    """Shape distance of the point on `shape` nearest to pt, not before dmin."""
    best = (1e18, dmin)
    for a, b in zip(shape, shape[1:]):
        if b[2] < dmin - 1: continue
        ax, ay, bx, by, px_, py_ = a[0] * KX, a[1], b[0] * KX, b[1], pt[0] * KX, pt[1]
        dx, dy = bx - ax, by - ay; L2 = dx * dx + dy * dy
        u = 0 if L2 == 0 else max(0, min(1, ((px_ - ax) * dx + (py_ - ay) * dy) / L2))
        q = (a[0] + (b[0] - a[0]) * u, a[1] + (b[1] - a[1]) * u)
        e = hv(q, pt); dd = a[2] + (b[2] - a[2]) * u
        if dd >= dmin - 1 and e < best[0]: best = (e, dd)
    return best[1], best[0]

def tmin(dist, vmax_kmh):
    """Shortest run over dist metres: accelerate at ACCEL, cruise at vmax (if there is room), brake at DECEL."""
    v = vmax_kmh / 3.6; k = 1 / ACCEL + 1 / DECEL
    return dist / v + v * k / 2 if dist >= v * v * k / 2 else math.sqrt(2 * dist * k)

def clamp_speeds(pat, vmax, rid, S):
    """pat rows [stop, arr, dep, dist]. Lengthen too-fast segments, borrow from slack elsewhere."""
    n = len(pat) - 1
    run = [pat[i + 1][1] - pat[i][2] for i in range(n)]
    need = [tmin(pat[i + 1][3] - pat[i][3], vmax) for i in range(n)]
    short = [i for i in range(n) if run[i] < need[i] - 0.5]
    if not short: return pat
    for i in short:
        d = pat[i + 1][3] - pat[i][3]
        note(f"{rid}: {S[pat[i][0]]} to {S[pat[i + 1][0]]} was {d / run[i] * 3.6:.0f} km/h ({d} m in {run[i]} s), "
             f"lengthened to {math.ceil(need[i])} s")
    deficit = sum(math.ceil(need[i]) - run[i] for i in short)
    slack = {j: run[j] - math.ceil(need[j] * 1.15) for j in range(n) if j not in short}
    slack = {j: v for j, v in slack.items() if v > 0}
    tot = sum(slack.values())
    new = list(run)
    for i in short: new[i] = math.ceil(need[i])
    take = min(deficit, tot); left = take
    for k, j in enumerate(sorted(slack)):
        x = round(take * slack[j] / tot) if k < len(slack) - 1 else left
        x = min(x, slack[j], left); new[j] -= x; left -= x
    if deficit > take: note(f"{rid}: not enough slack, trip runs {deficit - take} s longer")
    out = [list(pat[0])]; tcur = pat[0][2]
    for i in range(n):
        arr = tcur + new[i]; dwell = pat[i + 1][2] - pat[i + 1][1]
        out.append([pat[i + 1][0], arr, arr + dwell, pat[i + 1][3]]); tcur = arr + dwell
    return out

def insert_stop(pat, pts, a, b, sid, dwell, rid, S):
    """Add stop sid between consecutive stops a and b (either order). pts: shape [(lon, lat, dist)]."""
    for i in range(len(pat) - 1):
        p, q = pat[i], pat[i + 1]
        if {p[0], q[0]} != {a, b}: continue
        d, err = project(pts, coords[sid], p[3])
        if not p[3] < d < q[3]: raise ValueError(f"{rid}: {S[sid]} doesn't fall between {S[p[0]]} and {S[q[0]]}")
        arr = p[2] + round((q[1] - p[2]) * (d - p[3]) / (q[3] - p[3]))
        new = [sid, arr, arr + dwell, round(d)]
        rest = [[x[0], x[1] + dwell, x[2] + dwell, x[3]] for x in pat[i + 1:]]
        note(f"{rid}: added {S[sid]} between {S[p[0]]} and {S[q[0]]} ({err:.0f} m from the track, +{dwell} s dwell)")
        return pat[:i + 1] + [new] + rest
    return pat

def retime(pat, factors, vmax):
    """Scale the running time of each segment (a, b) in factors; dwells are kept, no segment beats tmin."""
    out = [list(pat[0])]
    for p, q in zip(pat, pat[1:]):
        run = q[1] - p[2]; f = factors.get((p[0], q[0]))
        if f is not None: run = max(round(run * f), math.ceil(tmin(q[3] - p[3], vmax)))
        arr = out[-1][2] + run
        out.append([q[0], arr, arr + q[2] - q[1], q[3]])
    return out

def calibrate(routes, cfg, S):
    """Scale running times between two stops to a published ride time, per line and direction.
    The factor is solved on the longest route that runs from `from` to `to` (or back), then
    applied to those segments on every route of the line. Returns before/after rows."""
    rows = []
    for c in cfg["lines"]:
        if "hold" in c:
            print(f"calibration held: {c['label']}: {c['hold']}"); continue
        vmax = LINE_VMAX.get(c["line"], VMAX_DEFAULT); line = [r for r in routes if r["line"] == c["line"]]
        for a, b in ((c["from"], c["to"]), (c["to"], c["from"])):
            def span(r):
                ids = [p[0] for p in r["pat"]]
                return (ids.index(a), ids.index(b)) if a in ids and b in ids and ids.index(a) < ids.index(b) else None
            ref = max((r for r in line if span(r)), key=lambda r: len(r["pat"]), default=None)
            if ref is None: raise ValueError(f"calibration: no {c['line']} route runs {S[a]} to {S[b]}")
            i, j = span(ref); seg = [(ref["pat"][k][0], ref["pat"][k + 1][0]) for k in range(i, j)]
            if j - i != c["stops"]:
                note(f"calibration: {c['label']}: source counts {c['stops']} stops, the map has {j - i}")
            ride = lambda pat: pat[j][1] - pat[i][2]
            before = ride(ref["pat"]); target = c["minutes"] * 60
            lo, hi = 0.3, 3.0  # bisect on the factor; tmin floors make the ride time piecewise linear in it
            for _ in range(60):
                f = (lo + hi) / 2
                if ride(retime(ref["pat"], {k: f for k in seg}, vmax)) < target: lo = f
                else: hi = f
            fac = {k: f for k in seg}; n = 0
            for r in line:
                if any(k in fac for k in zip([p[0] for p in r["pat"]], [p[0] for p in r["pat"]][1:])):
                    r["pat"] = retime(r["pat"], fac, vmax); n += 1
            after = ride(ref["pat"])
            note(f"{ref['id']}: {S[a]} to {S[b]} {before / 60:.1f} -> {after / 60:.1f} min "
                 f"(running times x{f:.3f}, {n} route(s); {cfg['source']}: {c['minutes']} min)")
            rows.append((c["label"], ref["id"], j - i, c["stops"], before, after, c["minutes"]))
    return rows

# Dwell at an interchange, in seconds, against the feed's 20 s everywhere (assumption: more people change trains
# there). Terminals keep the feed's times: a trip starts 20 s before it leaves and ends as it arrives, and a real
# turnaround is minutes, which the map doesn't draw. An interchange is a station served by two or more lines, by
# name, plus the pairs below that are joined on foot under different names.
DWELL_INTERCHANGE = 35
INTERCHANGE_PAIRS = [("Noida Sec-52", "Noida Sector 51")]  # Blue and Aqua, joined by a walkway

def interchanges(routes, stops):
    lines = {}
    for r in routes:
        for p in r["pat"]: lines.setdefault(stops[p[0]][0], set()).add(r["line"])
    for a, b in INTERCHANGE_PAIRS:
        both = lines.get(a, set()) | lines.get(b, set()); lines[a] = lines[b] = both
    return {sid for sid, s_ in stops.items() if len(lines.get(s_[0], ())) > 1}

def tier_dwells(routes, stops):
    """Lengthen intermediate interchange dwells to DWELL_INTERCHANGE. The extra time is taken from the runs
    just before and after, split by how much each can spare above tmin, so the times at every other stop stay as
    they were: end-to-end rides, calibrated spans and the starts headways.py lays out don't move."""
    ic = interchanges(routes, stops); short = 0
    for r in routes:
        p = r["pat"]; vmax = LINE_VMAX.get(r["line"], VMAX_DEFAULT)
        for j in range(1, len(p) - 1):
            extra = DWELL_INTERCHANGE - (p[j][2] - p[j][1])
            if p[j][0] not in ic or extra <= 0: continue
            spare = [max(0, (b[1] - a[2]) - math.ceil(tmin(b[3] - a[3], vmax))) for a, b in ((p[j - 1], p[j]), (p[j], p[j + 1]))]
            give = min(extra, sum(spare))
            if give < extra: short += 1
            if give <= 0: continue
            x = min(spare[0], round(give * spare[0] / sum(spare))); y = min(spare[1], give - x); x = give - y
            p[j][1] -= x; p[j][2] += y
    note(f"dwells: {DWELL_INTERCHANGE} s at {len(ic)} interchange stops, 20 s elsewhere; time taken from the runs either side"
         + (f" ({short} stop(s) had too little to spare and got less)" if short else ""))

def rdp(pts, eps):
    if len(pts) < 3: return pts
    (x1, y1, _), (x2, y2, _) = pts[0], pts[-1]; dx, dy = x2 - x1, y2 - y1; L = math.hypot(dx, dy) or 1e-12
    dmax, idx = 0, 0
    for i in range(1, len(pts) - 1):
        x, y, _ = pts[i]; dd = abs(dy * x - dx * y + x2 * y1 - y2 * x1) / L
        if dd > dmax: dmax, idx = dd, i
    if dmax > eps: return rdp(pts[:idx + 1], eps)[:-1] + rdp(pts[idx:], eps)
    return [pts[0], pts[-1]]

# stops, with coordinate fixes
coords = {int(x.stop_id): (x.stop_lon, x.stop_lat) for x in s.itertuples()}
names = {int(x.stop_id): x.stop_name.strip() for x in s.itertuples()}
orig = dict(coords)
for sid, (lat, lon, src) in STOP_FIXES.items():
    old = coords[sid]; coords[sid] = (lon, lat)
    note(f"stop {names[sid]} moved {hv(old, (lon, lat)) / 1000:.1f} km to {lat}, {lon} ({src})")

routes = []
for _, ro in r.iterrows():
    tr = t[t.route_id == ro.route_id]
    if tr.empty: continue
    rid = ro.route_short_name
    line, name = ro.route_long_name.split('_', 1)
    first = st[st.trip_id == tr.trip_id.iloc[0]]
    a0 = first.a.min()
    pat = [[int(x.stop_id), int(x.a - a0), int(x.d - a0), round(float(x.shape_dist_traveled))] for x in first.itertuples()]
    starts = sorted(st[st.trip_id.isin(tr.trip_id)].groupby('trip_id').a.min().astype(int).tolist())
    shp = sh[sh.shape_id == tr.shape_id.iloc[0]].sort_values('shape_pt_sequence')
    raw = list(zip(shp.shape_pt_lon, shp.shape_pt_lat))
    moved = False
    for sid in {p[0] for p in pat} & STOP_FIXES.keys():
        for i, q in enumerate(raw):
            if hv(q, orig[sid]) < 30: raw[i] = coords[sid]; moved = True
        moved = True
    cleaned, removed = clean_shape(raw)
    if removed or moved:
        full = with_dist(cleaned)
        if removed: note(f"{rid}: removed {removed} hairpin point(s) from the shape, "
                         f"length {shp.shape_dist_traveled.max() / 1000:.1f} -> {full[-1][2] / 1000:.1f} km")
        dmin = 0
        for p in pat:
            dd, err = project(full, coords[p[0]], dmin); p[3] = round(dd); dmin = dd
            if err > 300: print(f"warning: {rid} stop {names[p[0]]} is {err:.0f} m from the cleaned shape")
        pts = [(round(x, 5), round(y, 5), round(d)) for x, y, d in full]
    else:
        pts = [(round(x.shape_pt_lon, 5), round(x.shape_pt_lat, 5), round(x.shape_dist_traveled)) for x in shp.itertuples()]
    for ln, a, b, sid, dwell, src in STOP_INSERTS:
        if ln == line: pat = insert_stop(pat, pts, a, b, sid, dwell, rid, names)
    pat = clamp_speeds(pat, LINE_VMAX.get(line, VMAX_DEFAULT), rid, names)
    pts = rdp(pts, 0.00004)
    svc = sorted(tr.service_id.unique().tolist())
    if rid in SERVICE_AS_DAILY:
        note(f"{rid}: {len(tr)} trips labelled {'/'.join(svc)} treated as daily"); svc = ["daily"]
    routes.append(dict(id=rid, line=line, name=name.strip().replace('  ', ' '), pat=pat, starts=starts,
                       shape=[list(p) for p in pts], svc=svc))

stops = {k: [names[k], round(coords[k][0], 5), round(coords[k][1], 5)] for k in coords}
ROUTES_UNCALIBRATED = copy.deepcopy(routes)  # phase4 takes line speeds from these
if os.path.exists(CAL):
    calibrate(routes, json.load(open(CAL)), names)

# feed_date: when the GTFS was published. No build date: the same inputs must give a byte-identical data.json.
meta = dict(feed="DMRC GTFS, Delhi Open Transit Data, updated 10 Aug 2023", feed_date="2023-08-10", fixes=notes)
if os.path.exists(P4):
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import phase4
    est_routes, est_stops, est_meta = phase4.build(json.load(open(P4)), stops, routes, sys.modules[__name__])
    routes += est_routes; stops.update(est_stops); meta["estimated"] = est_meta
tier_dwells(routes, stops)
FREQ = os.path.join(HERE, "frequency.json")
if os.path.exists(FREQ) and os.path.exists(P4):
    import headways
    fcfg = json.load(open(FREQ))
    routes = headways.apply(routes, stops, fcfg, json.load(open(P4)), phase4)
    meta["frequency"] = dict(source=fcfg["source"], as_of=fcfg["as_of"], peak_bands=fcfg["peak_bands"], peak_bands_source=fcfg["peak_bands_source"])
SVC = os.path.join(HERE, "service_days.json")
if os.path.exists(SVC):
    import headways
    meta["service"] = headways.service_meta(json.load(open(SVC)), routes)

json.dump(dict(colors=col, routes=routes, stops=stops, meta=meta), open(OUT, 'w'), separators=(',', ':'), ensure_ascii=False)
print(os.path.getsize(OUT), len(routes), sum(len(x['shape']) for x in routes))
