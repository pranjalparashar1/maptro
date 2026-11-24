"""python3 -m unittest discover -s tests -p 'test_*.py'"""
import contextlib, io, json, os, sys, tempfile, unittest, zipfile
from unittest import mock
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "scripts"))
import gtfs_feed as G

FEED = {
    "stops.txt": b"stop_id,stop_name,stop_lat,stop_lon\n1,A,28.6,77.2\n2,B,28.61,77.21\n",
    "stop_times.txt": b"trip_id,arrival_time,departure_time,stop_id,stop_sequence\nt1,05:00:00,05:00:00,1,1\nt1,05:02:00,05:02:00,2,2\n",
    "trips.txt": b"route_id,service_id,trip_id\nr1,weekday,t1\n",
    "routes.txt": b"route_id,route_short_name\nr1,R\n",
    "calendar.txt": b"service_id,monday,tuesday,wednesday,thursday,friday,saturday,sunday,start_date,end_date\n"
                    b"weekday,1,1,1,1,1,0,0,20190101,20251231\n",
}


def write_dir(d, files):
    for n, b in files.items():
        with open(os.path.join(d, n), "wb") as f:
            f.write(b)


def write_zip(p, files, prefix=""):
    with zipfile.ZipFile(p, "w") as z:
        for n, b in files.items():
            z.writestr(prefix + n, b)


class Fingerprint(unittest.TestCase):
    def test_same_contents_same_fingerprint(self):
        with tempfile.TemporaryDirectory() as d:
            write_dir(d, FEED)
            write_zip(os.path.join(d, "a.zip"), FEED, prefix="DMRC_GTFS/")
            crlf = {n: b.replace(b"\n", b"\r\n") for n, b in FEED.items()}
            crlf["stops.txt"] = b"\xef\xbb\xbf" + crlf["stops.txt"]
            write_zip(os.path.join(d, "b.zip"), crlf)
            fps = {G.fingerprint(G.read_feed(p)) for p in (d, os.path.join(d, "a.zip"), os.path.join(d, "b.zip"))}
            self.assertEqual(len(fps), 1)

    def test_timetable_change_changes_fingerprint(self):
        new = dict(FEED, **{"stop_times.txt": FEED["stop_times.txt"].replace(b"05:02:00", b"05:03:00")})
        self.assertNotEqual(G.fingerprint(FEED), G.fingerprint(new))

    def test_not_gtfs(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(SystemExit):
                G.read_feed(d)

    def test_summary(self):
        s = G.summary(FEED)
        self.assertEqual((s["stops"], s["trips"], s["stop_times"], s["end_date"]), (2, 1, 2, "20251231"))


class Check(unittest.TestCase):
    def run_check(self, files, known_files):
        with tempfile.TemporaryDirectory() as d:
            feed, known, out = os.path.join(d, "f.zip"), os.path.join(d, "known.json"), os.path.join(d, "gh_out")
            write_zip(feed, known_files)
            with contextlib.redirect_stdout(io.StringIO()):
                G.main(["record", feed, "--source", "test", "--known", known])
            write_zip(feed, files)
            with mock.patch.dict(os.environ, {"GITHUB_OUTPUT": out}), contextlib.redirect_stdout(io.StringIO()) as so:
                G.main(["check", "--feed", feed, "--known", known])
            with open(out) as f:
                return dict(l.strip().split("=", 1) for l in f), so.getvalue()

    def test_unchanged(self):
        o, text = self.run_check(FEED, FEED)
        self.assertEqual(o["changed"], "false")
        self.assertIn("No change", text)

    def test_changed(self):
        new = dict(FEED, **{"calendar.txt": FEED["calendar.txt"].replace(b"20251231", b"20271231")})
        o, text = self.run_check(new, FEED)
        self.assertEqual(o["changed"], "true")
        self.assertIn("| end_date | 20251231 | **20271231** |", text)

    def test_known_file_matches_committed_feed_summary(self):
        with open(G.KNOWN) as f:
            k = json.load(f)
        self.assertEqual((k["summary"]["stops"], k["summary"]["routes"], k["summary"]["trips"]), (262, 36, 5438))


class Download(unittest.TestCase):
    def test_csrf_form(self):
        page = b'<form method="post"><input type="hidden" name="csrfmiddlewaretoken" value="tok123"></form>'
        buf = io.BytesIO()
        write_zip(buf, FEED)
        calls = []

        class Resp(io.BytesIO):
            headers = {"Content-Type": "application/zip", "Content-Disposition": "attachment; filename=DMRC_GTFS.zip"}
            def __enter__(self): return self
            def __exit__(self, *a): pass

        class Opener:
            addheaders = []
            def open(self, req, timeout=None):
                calls.append(req)
                return Resp(page if isinstance(req, str) else buf.getvalue())

        with tempfile.TemporaryDirectory() as d, mock.patch.object(G.urllib.request, "build_opener", lambda *a: Opener()):
            p = os.path.join(d, "f.zip")
            h = G.download(p)
            self.assertEqual(G.fingerprint(G.read_feed(p)), G.fingerprint(FEED))
        self.assertEqual(calls[1].data, b"csrfmiddlewaretoken=tok123")
        self.assertEqual(calls[1].get_header("Cookie"), "csrftoken=tok123")
        self.assertIn("Content-Disposition", h)

    def test_html_instead_of_zip(self):
        class Resp(io.BytesIO):
            headers = {"Content-Type": "text/html"}
            def __enter__(self): return self
            def __exit__(self, *a): pass

        class Opener:
            addheaders = []
            def open(self, req, timeout=None):
                return Resp(b'<input name="csrfmiddlewaretoken" value="x">')

        with tempfile.TemporaryDirectory() as d, mock.patch.object(G.urllib.request, "build_opener", lambda *a: Opener()):
            with self.assertRaises(SystemExit):
                G.download(os.path.join(d, "f.zip"))


if __name__ == "__main__":
    unittest.main()
