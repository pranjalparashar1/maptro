"""python3 -m unittest discover -s tests -p 'test_*.py'"""
import contextlib, io, json, os, sys, tempfile, unittest
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "scripts"))
import audit_osm as A

def _read(p):
    with open(p, encoding="utf-8") as f:
        return f.read()


FIX = os.path.join(HERE, "fixtures")
STOPS = A.load(os.path.join(FIX, "osm_stops.json"))["stops"]
DOC = A.load(os.path.join(FIX, "overpass_sample.json"))


class Names(unittest.TestCase):
    def test_norm(self):
        self.assertEqual(A.norm("Noida Sec -18"), "noida sector 18")
        self.assertEqual(A.norm("Adarsh Nagar Metro Station"), "adarsh nagar")
        self.assertEqual(A.norm("Dwarka Sector - 21"), "dwarka sector 21")

    def test_aliases_drop_generic_brackets(self):
        self.assertEqual(A.aliases("Paschim Vihar (East)"), {"paschim vihar east", "paschim vihar"})
        self.assertIn("sihi", A.aliases("Sant Surdas (Sihi)"))
        self.assertNotIn("rapid", A.aliases("Sikanderpur (Rapid Metro)"))

    def test_score(self):
        self.assertEqual(A.score({"rajiv chowk"}, {"rajivchowk"}), 1.0)
        self.assertGreaterEqual(A.score({"kashmere gate"}, {"kashmere gate isbt"}), 0.9)
        self.assertEqual(A.score({"noida sector 18"}, {"noida sector 81"}), 0.0)
        self.assertEqual(A.score(A.aliases("Phase-I (Rapid Metro)"), {"phase 3"}), 0.0)  # seen on the first live run
        self.assertEqual(A.norm("Mayur Vihar-I"), "mayur vihar 1")
        self.assertLess(A.score({"jhilmil"}, {"dilshad garden"}), A.MIN_SCORE)


class Matching(unittest.TestCase):
    def setUp(self):
        self.osm = A.osm_stations(DOC)
        self.res = {r["id"]: r for r in A.match(STOPS, self.osm)}

    def test_unnamed_osm_station_dropped(self):
        self.assertEqual(len(self.osm), 9)

    def test_interchange_uses_nearest_same_name(self):
        r = self.res["10"]
        self.assertEqual(r["osm"]["id"], "node/1")
        self.assertLess(r["dist"], 20)

    def test_way_centre_and_far_stop(self):
        r = self.res["40"]
        self.assertEqual(r["osm"]["id"], "way/3")
        self.assertGreater(r["dist"], 300)

    def test_name_en_and_brackets(self):
        self.assertEqual(self.res["21"]["osm"]["id"], "node/4")
        self.assertEqual(self.res["60"]["osm"]["id"], "node/6")
        self.assertEqual(self.res["61"]["osm"]["id"], "node/5")
        self.assertEqual(self.res["70"]["osm"]["id"], "node/7")
        self.assertEqual(self.res["80"]["osm"]["id"], "node/8")

    def test_unmatched_gives_nearest(self):
        r = self.res["99"]
        self.assertEqual(r["status"], "unmatched")
        self.assertEqual(r["nearest"]["name"], "Central Secretariat")

    def test_report_and_fixes(self):
        text, far = A.report(list(self.res.values()), 150, "fixture")
        self.assertEqual([r["id"] for r in far], ["40"])
        self.assertIn("| 40 | Adarsh Nagar |", text)
        self.assertIn("| 99 | Nowhere Halt | Central Secretariat", text)
        fx = A.fixes(far, "fixture")
        self.assertEqual(fx["40"]["lat"], 28.7142)
        self.assertIn("way/3", fx["40"]["source"])


class Cli(unittest.TestCase):
    def test_main_offline(self):
        with tempfile.TemporaryDirectory() as d:
            out, fx = os.path.join(d, "r.md"), os.path.join(d, "f.json")
            with contextlib.redirect_stdout(io.StringIO()):
                rc = A.main(["--data", os.path.join(FIX, "osm_stops.json"), "--osm", os.path.join(FIX, "overpass_sample.json"),
                             "--out", out, "--fixes", fx, "--strict"])
            self.assertEqual(rc, 1)
            self.assertIn("OSM data as of 2026-11-20", _read(out))
            self.assertEqual(list(A.load(fx)), ["40"])

    def test_bbox_covers_every_stop(self):
        stops = A.load(os.path.join(HERE, "..", "data.json"))["stops"]
        s, w, n, e = A.bbox(stops)
        self.assertTrue(all(s < v[2] < n and w < v[1] < e for v in stops.values()))
        self.assertLess(s, 28.34)  # Raja Nahar Singh, Ballabhgarh

    def test_every_real_stop_matches_itself(self):
        """Each data.json stop, offered as an OSM station 100 m away, matches itself and not a neighbour."""
        stops = A.load(os.path.join(HERE, "..", "data.json"))["stops"]
        doc = {"elements": [{"type": "node", "id": int(k), "lat": v[2] + 0.0009, "lon": v[1],
                             "tags": {"railway": "station", "station": "subway", "name": v[0]}} for k, v in stops.items()]}
        res = A.match(stops, A.osm_stations(doc))
        wrong = [(r["id"], r.get("osm", {}).get("id")) for r in res if r.get("osm", {}).get("id") != f"node/{r['id']}"]
        self.assertEqual(wrong, [])


if __name__ == "__main__":
    unittest.main()
