"""Synthesise ESTIMATED trips for sections the 2023 DMRC feed lacks (see phase4.json).

Called by build.py after the feed routes are built. Nothing here is a timetable:
 - Track and new station points: OpenStreetMap (phase4_geometry.json).
 - Running times: each segment takes distance / the line's average running speed in
   the feed, but never less than a train could manage (build.tmin), plus the feed's 20 s dwell.
 - Trip times come from the section's "timing" rule:
     continues: R    trains of feed route R carry on past R's last stop (every Nth train)
     feeds: R        trains arrive in time to become feed route R's trips (every Nth)
     departs: R, at  a train starts here each time a route-R train leaves stop `at`
     headway_like: R trips start at the same times as feed route R's trips
Every route made here has est=1, which the page draws dashed and labels "estimated".
"""
import json, os
B = None  # build.py's module, for its geometry helpers; set by build()

HERE = os.path.dirname(os.path.abspath(__file__))
DWELL = 20


def _line_speed(routes, line):
    d = t = 0
    for r in routes:
        if r["line"] != line: continue
        p = r["pat"]
        d += p[-1][3] - p[0][3]
        t += sum(b[1] - a[2] for a, b in zip(p, p[1:]))
    return d / t  # m/s


def _cut(poly, a, b):
    """Polyline from the point nearest a to the point nearest b, with distances."""
    poly, _ = B.clean_shape([tuple(p) for p in poly])
    full = B.with_dist(poly)
    da, _ = B.project(full, a, 0)
    db, _ = B.project(full, b, 0)
    if db < da:
        full = B.with_dist(poly[::-1]); da, _ = B.project(full, a, 0); db, _ = B.project(full, b, da)
    def at(d):
        for p, q in zip(full, full[1:]):
            if p[2] <= d <= q[2]:
                u = (d - p[2]) / ((q[2] - p[2]) or 1)
                return (p[0] + (q[0] - p[0]) * u, p[1] + (q[1] - p[1]) * u)
        return full[-1][:2]
    mid = [p[:2] for p in full if da < p[2] < db]
    return B.with_dist(B.clean_shape([at(da)] + mid + [at(db)])[0])


def _starts(rule, pat, feed):
    dur = pat[-1][1]
    if "continues" in rule:
        r = feed[rule["continues"]]; off = r["pat"][-1][1]
        return [s + off for s in r["starts"][::rule.get("every", 1)]]
    if "feeds" in rule:
        r = feed[rule["feeds"]]
        return [s - dur for s in r["starts"][::rule.get("every", 1)]]
    if "departs" in rule:
        r = feed[rule["departs"]]; q = next(x for x in r["pat"] if x[0] == rule["at"])
        return [s + q[2] - DWELL for s in r["starts"][::rule.get("every", 1)]]
    if "headway_like" in rule:
        return list(feed[rule["headway_like"]]["starts"])
    raise ValueError(rule)


def build(cfg, stops, routes_feed, helpers):
    global B
    B = helpers
    geo = json.load(open(os.path.join(HERE, "phase4_geometry.json")))
    feed = {r["id"]: r for r in routes_feed}
    sid = {k: v[0] for k, v in cfg["stations"].items()}
    new_stops = {v[0]: [v[1], round(geo["stops"][k][0], 5), round(geo["stops"][k][1], 5)] for k, v in cfg["stations"].items()}
    allstops = {**{int(k): v for k, v in stops.items()}, **new_stops}
    out, meta = [], []
    for sec in cfg["sections"]:
        ids = [x if isinstance(x, int) else sid[x] for x in sec["stops"]]
        vavg = _line_speed(routes_feed, sec["line"])
        vmax = B.LINE_VMAX.get(sec["line"], B.VMAX_DEFAULT)
        for direction, rule in (("", sec["timing"]), ("_R", sec["reverse_timing"])):
            seq = ids if not direction else ids[::-1]
            ll = [tuple(allstops[i][1:]) for i in seq]
            shape = _cut(geo["shapes"][sec["shape"]], ll[0], ll[-1])
            pat, dmin, t = [], 0, 0
            for k, (i, p) in enumerate(zip(seq, ll)):
                d, err = B.project(shape, p, dmin)
                if err > 300: print(f"warning: {sec['key']}{direction} {allstops[i][0]} is {err:.0f} m from the OSM track")
                if k:
                    run = (d - pat[-1][3])
                    t = pat[-1][2] + max(round(run / vavg), round(B.tmin(run, vmax) + 0.5))
                pat.append([i, t, t + DWELL, round(d)]); dmin = d
            cal = sec.get("calibrate")
            if cal:  # scale running times so a published ride time between two stations is matched
                a_id, b_id = [x if isinstance(x, int) else sid[x] for x in (cal["from"], cal["to"])]
                ia, ib = sorted((seq.index(a_id), seq.index(b_id)))
                run_ab = sum(pat[k + 1][1] - pat[k][2] for k in range(ia, ib))
                f = (cal["minutes"] * 60 - (pat[ib][1] - pat[ia][2] - run_ab)) / run_ab
                out_t, prev = [], None
                for k, q in enumerate(pat):
                    if k:
                        run = q[3] - pat[k - 1][3]
                        tt = prev[2] + max(round((q[1] - pat[k - 1][2]) * f), round(B.tmin(run, vmax) + 0.5))
                    else:
                        tt = 0
                    prev = [q[0], tt, tt + DWELL, q[3]]; out_t.append(prev)
                pat = out_t
                print(f"calibrated {sec['key']}{direction}: running times x{f:.3f} to match {cal['minutes']} min")
            starts = sorted(_starts(rule, pat, feed))
            first, last = allstops[seq[0]][0], allstops[seq[-1]][0]
            out.append(dict(id=f"E_{sec['key']}{direction}", line=sec["line"], name=f"{first} to {last}", pat=pat, starts=starts,
                            shape=[list(p) for p in B.rdp([(round(x, 5), round(y, 5), round(dd)) for x, y, dd in shape], 0.00004)],
                            svc=["estimated"], est=1, sec=len(meta)))
            ok = f", official {sec['official_km']} km" if "official_km" in sec else ""
            print(f"estimated: {first} to {last}: {len(starts)} trips, {pat[-1][1] / 60:.1f} min, {pat[-1][3] / 1000:.1f} km on OSM track{ok}")
        meta.append(dict(label=sec["label"], opened=sec["opened"], basis=sec["basis"], sources=sec["sources"]))
    meta_out = dict(geometry=geo["source"], sections=meta)
    return out, {k: v for k, v in new_stops.items()}, meta_out
