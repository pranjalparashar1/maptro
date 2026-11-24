"""Departure times from DMRC's published train frequencies (frequency.json), for weekdays, Saturdays and Sundays.

Called by build.py after the feed and estimated routes are built and calibrated. Run times (route "pat") are
kept: they come from the feed and are calibrated to Google Maps. Only the departure times ("starts") change.

How the times are made:
 - A corridor is a stretch of track shared by several services, e.g. Blue Line Dwarka to Yamuna Bank. Trains on
   it are "slots" at one stop, spaced by DMRC's headway for that stretch (peak or off-peak, by day). The slots are
   dealt to the corridor's services in a fixed cycle, so branch trains alternate instead of leaving together
   (the 2023 feed starts both Blue branches, and both Green branches, at the same second all day).
 - Branch and turn-back frequencies follow from the cycle. Each cycle below reproduces DMRC's figure for every
   section it covers (e.g. Blue: 2:51 trunk, 5:42 each branch, 4:16 to Dwarka Sector 21); build.py prints a check.
 - Where DMRC's numbers imply trains that turn back short of the end (Blue at Dwarka, Green at Mundka, Yellow at
   Vishwavidyalaya, the Pink spur), the service is a trimmed copy of a feed route, with the feed's run times.
 - Service hours (first and last train) and the peak bands are the 2023 feed's: DMRC's table gives neither.
 - Routes the table doesn't cover (Rapid Metro, Aqua) keep the feed's weekday times every day.
"""
import json, os
DAY = 86400
DAYS = ("wkd", "sat", "sun")
HERE = os.path.dirname(os.path.abspath(__file__))


def mmss(s):
    m, x = s.split(":"); return int(m) * 60 + int(x)


def fmt(sec):
    return f"{int(sec // 60)}:{int(round(sec % 60)):02d}"


class Table:
    def __init__(self, cfg):
        self.cfg = cfg; self.bands = [(a * 3600, b * 3600) for a, b in cfg["peak_bands"]]

    def hw(self, key, di, t):
        s = self.cfg["sections"][key]
        peak = any(a <= t % DAY < b for a, b in self.bands)
        return mmss(s["peak" if peak else "off"][di])


def slots(first, last, h):
    out, t = [], first
    while t <= last:
        out.append(t); t += h(t)
    return out


def at(r, stop):
    """Seconds after the route's start at which it leaves `stop`."""
    for p in r["pat"]:
        if p[0] == stop: return p[2]
    raise KeyError(f"{r['id']} doesn't call at stop {stop}")


def trim(r, new_id, start=None, end=None):
    """Copy of route r running only from stop `start` to stop `end` (its own ends if None), same run times."""
    ids = [p[0] for p in r["pat"]]
    i = ids.index(start) if start is not None else 0
    j = ids.index(end) if end is not None else len(ids) - 1
    t0 = r["pat"][i][1]
    pat = [[p[0], p[1] - t0, p[2] - t0, p[3]] for p in r["pat"][i:j + 1]]
    d0, d1 = pat[0][3], pat[-1][3]
    def point(d):
        for a, b in zip(r["shape"], r["shape"][1:]):
            if a[2] <= d <= b[2]:
                u = (d - a[2]) / ((b[2] - a[2]) or 1)
                return [round(a[0] + (b[0] - a[0]) * u, 5), round(a[1] + (b[1] - a[1]) * u, 5), d]
        return list(r["shape"][-1])
    shape = [point(d0)] + [list(p) for p in r["shape"] if d0 < p[2] < d1] + [point(d1)]
    out = {k: v for k, v in r.items() if k not in ("pat", "shape", "starts")}
    out.update(id=new_id, pat=pat, shape=shape, starts=[])
    first, last = pat[0][0], pat[-1][0]
    return out, first, last


# Corridors: (slot stop, section key giving the slot headway, cycle of route ids, feed routes whose times at the
# slot stop set the first and last slot). Ids with a lower-case tag are trimmed copies made in apply().
CORRIDORS = [
    # Red: Rithala-Dilshad Garden every 3:30, every second train on to Shaheed Sthal (7:00).
    (21, "red_trunk", ["R_RS", "R_RD"], ["R_RS", "R_RD"]),
    (1, "red_trunk", ["R_RS_R", "R_RD_R"], ["R_RS_R", "R_RD_R"]),
    # Yellow: Gurugram-Vishwavidyalaya every 2:54, every second train on to Samaypur Badli (5:48).
    (71, "yellow_trunk", ["Y_HS", "Y_HSv"], ["Y_HS", "Y_HQ"]),
    (44, "yellow_trunk", ["Y_HS_R", "Y_HSv_R"], ["Y_HS_R", "Y_QV_R"]),
    # Blue: Dwarka-Yamuna Bank every 2:51, alternating Noida and Vaishali (5:42 each); 2 in 3 to Dwarka Sec 21 (4:16).
    (113, "blue_trunk", ["B_DN", "B_DV", "B_DNd", "B_DV", "B_DN", "B_DVd"], ["B_DN", "B_DV"]),
    (89, "blue_trunk", ["B_DN_R", "B_DV_R", "B_DNd_R", "B_DV_R", "B_DN_R", "B_DVd_R"], ["B_DN_R", "B_DV_R"]),
    # Green: Ashok Park-Mundka every 4:10, alternating Inderlok and Kirti Nagar (8:20 each); 2 in 3 on to
    # Brig. Hoshiyar Singh (6:15).
    (34, "green_trunk", ["G_IB", "G_KB", "G_IBm", "G_KB", "G_IB", "G_KBm"], ["G_IB", "G_KB"]),
    (34, "green_trunk", ["G_IB_R", "G_KB_R", "G_IBm_R", "G_KB_R", "G_IB_R", "G_KBm_R"], ["G_IB_R", "G_KB_R"]),
    # Violet: Kashmere Gate-Badarpur every 3:24, every second train on to Raja Nahar Singh (6:48).
    (8, "violet_trunk", ["V_KR", "V_KB"], ["V_KR", "V_KB"]),
    (138, "violet_trunk", ["V_KR_R", "V_KB_R"], ["V_KR_R", "V_KB_R"]),
    # One service each.
    (None, "magenta_main", ["M_JB"], ["M_JB"]),
    (None, "magenta_main", ["M_JB_R"], ["M_JB_R"]),
    (None, "magenta_north", ["E_magenta_north"], ["E_magenta_north"]),
    (None, "magenta_north", ["E_magenta_north_R"], ["E_magenta_north_R"]),
    (None, "grey", ["G_DD"], ["G_DD"]),
    (None, "grey", ["G_DD_R"], ["G_DD_R"]),
    (None, "airport", ["O_DN"], ["O_DN"]),
    (None, "airport", ["O_DN_R"], ["O_DN_R"]),
    # Pink: the ring both ways from Majlis Park, and Maujpur-Shiv Vihar as its own service (8:10).
    # "+ circular" is taken to be Majlis Park via Rajouri Garden and Welcome (the feed's P_MS direction).
    (173, "pink_plus", ["P_MSp"], ["P_MS"]),
    (173, "pink_minus", ["E_pink_ring"], ["P_MS"]),
    (215, "pink_spur", ["P_MSs"], ["P_MS_R"]),
    (218, "pink_spur", ["P_MSs_R"], ["P_MS_R"]),
]
# Trimmed copies: new id -> (feed route, start stop, end stop).
TRIMS = {
    "Y_HSv": ("Y_HS", None, 44), "Y_HSv_R": ("Y_HS_R", 44, None),
    "B_DNd": ("B_DN", 113, None), "B_DVd": ("B_DV", 113, None),
    "B_DNd_R": ("B_DN_R", None, 113), "B_DVd_R": ("B_DV_R", None, 113),
    "G_IBm": ("G_IB", None, 22), "G_KBm": ("G_KB", None, 22),
    "G_IBm_R": ("G_IB_R", 22, None), "G_KBm_R": ("G_KB_R", 22, None),
    "P_MSp": ("P_MS", None, 215), "P_MSm_R": ("P_MS_R", 215, None),
    "P_MSs": ("P_MS", 215, None), "P_MSs_R": ("P_MS_R", None, 215),
}
# Feed routes replaced by the services above (short turns the table has no place for, and the Pink through route).
DROP = {"Y_QV", "Y_QV_R", "Y_HQ", "Y_HQ_R", "P_MS", "P_MS_R"}
# Services timed off another: id -> (leader, section). Each starts when a leader train arrives at the leader's last
# stop, so a ring train carries on round. Before the first such train, trains start here on their own at the
# section's headway from the leader's first departure, so the far side of the ring isn't empty early in the morning.
CHAINS = {"E_pink_ring_R": ("P_MSp", "pink_plus"), "P_MSm_R": ("E_pink_ring", "pink_minus")}
# Estimated extensions keep their phase4.json rule (every train, or every second), re-run on the new times.
PHASE4_RULES = ("airport", "magenta_kpe")
# Checks printed by the build (a 2-in-3 pattern averages within ~4% of its figure over a window): (section, stop, route ids that carry it there, in one direction).
CHECKS = [
    ("red_trunk", 10, ["R_RS", "R_RD"]), ("red_branch", 225, ["R_RS_R"]),
    ("yellow_trunk", 62, ["Y_HS", "Y_HSv"]), ("yellow_north", 36, ["Y_HS_R"]),
    ("blue_dwarka21", 121, ["B_DN", "B_DV"]), ("blue_trunk", 50, ["B_DN", "B_DV", "B_DNd", "B_DVd"]),
    ("blue_noida", 238, ["B_DN_R", "B_DNd_R"]), ("blue_vaishali", 72, ["B_DV_R", "B_DVd_R"]),
    ("green_trunk", 28, ["G_IB", "G_KB", "G_IBm", "G_KBm"]), ("green_branch", 100, ["G_KB", "G_KBm"]),
    ("green_branch", 13, ["G_IB_R", "G_IBm_R"]), ("green_west", 202, ["G_IB_R", "G_KB_R"]),
    ("violet_trunk", 138, ["V_KB_R", "V_KR_R"]), ("violet_south", 220, ["V_KR_R"]),
    ("pink_plus", 173, ["P_MSp"]), ("pink_minus", 173, ["E_pink_ring"]), ("pink_spur", 218, ["P_MSs_R"]),
    ("magenta_main", 108, ["M_JB"]), ("magenta_kpe", 9002, ["E_magenta_kpe_R"]),
    ("magenta_north", 173, ["E_magenta_north"]), ("grey", None, ["G_DD"]), ("airport", 9001, ["E_airport_R"]),
]


def apply(routes, stops, cfg, p4cfg, phase4, log=print):
    tab = Table(cfg); by = {r["id"]: r for r in routes}
    feed_times = {r["id"]: list(r["starts"]) for r in routes}
    for nid, (src, a, b) in TRIMS.items():
        by[nid], first, last = trim(by[src], nid, a, b)
        by[nid]["name"] = f"{stops[first][0]} to {stops[last][0]}"
    times = {d: {} for d in DAYS}
    for di, day in enumerate(DAYS):
        for stop, key, cycle, hours in CORRIDORS:
            at_stop = lambda rid: at(by[rid], stop) if stop is not None else 0
            t = [s + at_stop(h) for h in hours for s in feed_times[h]]
            ss = slots(min(t), max(t), lambda x: tab.hw(key, di, x))
            for k, s in enumerate(ss):
                rid = cycle[k % len(cycle)]
                times[day].setdefault(rid, []).append(s - at_stop(rid))
        for rid, (lead, key) in CHAINS.items():
            ts = [s + by[lead]["pat"][-1][1] for s in times[day][lead]]
            first = min(times[day][lead])
            while ts[0] - tab.hw(key, di, ts[0]) >= first:
                ts.insert(0, ts[0] - tab.hw(key, di, ts[0]))
            times[day][rid] = ts
        for sec in p4cfg["sections"]:
            if sec["key"] not in PHASE4_RULES: continue
            fake = {k: dict(by[k], starts=times[day].get(k, feed_times.get(k, []))) for k in by}
            for suffix, rule in (("", sec["timing"]), ("_R", sec["reverse_timing"])):
                rid = f"E_{sec['key']}{suffix}"
                times[day][rid] = phase4._starts(rule, by[rid]["pat"], fake)
    out = []
    for rid, r in by.items():
        if rid in DROP: continue
        if rid not in times["wkd"]:
            out.append(r); continue  # not on DMRC's table: feed times every day
        r["starts"] = sorted(round(x) for x in times["wkd"][rid])
        for day in ("sat", "sun"):
            r[day] = sorted(round(x) for x in times[day].get(rid, []))
        r["svc"] = ["dmrc_frequency"]
        out.append(r)
    for di, day in enumerate(DAYS):
        for key, stop, rids in CHECKS:
            got = {b: gap(by, rids, stop, day, a, b) for a, b in ((9.5 * 3600, 11.5 * 3600), (13 * 3600, 16 * 3600))}
            sec = cfg["sections"][key]; want = sec["peak"][di], sec["off"][di]
            vals = list(got.values())
            ok = all(v is not None and abs(v - mmss(w)) <= max(2, 0.04 * mmss(w)) for v, w in zip(vals, want))
            if day == "wkd" or not ok:
                log(f"headway {day} {sec['label']}: peak {fmt(vals[0]) if vals[0] else '-'} (DMRC {want[0]}), "
                    f"off-peak {fmt(vals[1]) if vals[1] else '-'} (DMRC {want[1]}){'' if ok else '  MISMATCH'}")
    return out


def gap(by, rids, stop, day, a, b):
    """Average gap between departures from `stop` on routes rids within [a, b)."""
    ts = []
    for rid in rids:
        r = by[rid]; st = r["starts"] if day == "wkd" else r.get(day, r["starts"])
        off = 0 if stop is None else at(r, stop)
        ts += [s + off for s in st if a <= s + off < b]
    ts.sort()
    return (ts[-1] - ts[0]) / (len(ts) - 1) if len(ts) > 1 else None
