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


class Resp(io.BytesIO):
    def __init__(self, body, ctype):
        super().__init__(body); self.headers = {"Content-Type": ctype, "Content-Disposition": "attachment"}
    def __enter__(self): return self
    def __exit__(self, *a): self.close()


PAGE = b"""<html><body>
<form method="post" action="/data/broken/"><input type="hidden" name="csrfmiddlewaretoken" value="tok123"></form>
<form method="POST" action="/data/staticDMRC/download/">
 <input type="hidden" name="csrfmiddlewaretoken" value="tok123">
 <select name="usage_type"><option value="">--</option><option value="Commercial">Commercial</option>
  <option value="Non-Commercial">Non-Commercial</option></select>
 <select name="purpose"><option value="Business">Business</option><option value="Academia R&amp;D">Academia R&amp;D</option></select>
 <button type="submit">Submit</button>
</form></body></html>"""


def opener(zipbytes, calls):
    class Opener:
        addheaders = []
        def open(self, req, timeout=None):
            calls.append(req)
            if isinstance(req, str):
                return Resp(PAGE, "text/html")
            if req.full_url.endswith("/broken/"):
                raise G.urllib.error.HTTPError(req.full_url, 404, "NOT FOUND", {}, None)
            return Resp(zipbytes, "application/zip")
    return lambda *a: Opener()


class Download(unittest.TestCase):
    def test_form_fields_and_fallback(self):
        buf = io.BytesIO(); write_zip(buf, FEED); calls = []
        with tempfile.TemporaryDirectory() as d, mock.patch.object(G.urllib.request, "build_opener", opener(buf.getvalue(), calls)):
            p = os.path.join(d, "f.zip")
            h = G.download(p)
            self.assertEqual(G.fingerprint(G.read_feed(p)), G.fingerprint(FEED))
        self.assertEqual(calls[1].full_url, "https://otd.delhi.gov.in/data/broken/")
        post = calls[2]
        self.assertEqual(post.full_url, "https://otd.delhi.gov.in/data/staticDMRC/download/")
        self.assertEqual(dict(G.urllib.parse.parse_qsl(post.data.decode())),
                         {"csrfmiddlewaretoken": "tok123", "usage_type": "Non-Commercial", "purpose": "Academia R&D"})
        self.assertEqual(post.get_header("Cookie"), "csrftoken=tok123")
        self.assertIn("Content-Disposition", h)

    def test_no_zip_saves_page(self):
        calls = []
        with tempfile.TemporaryDirectory() as d, mock.patch.object(G.urllib.request, "build_opener", opener(b"<html>", calls)):
            cwd = os.getcwd(); os.chdir(d)
            try:
                with self.assertRaises(SystemExit) as e:
                    G.download(os.path.join(d, "f.zip"))
                self.assertTrue(os.path.exists("otd-page.html"))
            finally:
                os.chdir(cwd)
        self.assertIn("HTTP 404", str(e.exception.code))
        self.assertIn("not a zip", str(e.exception.code))


if __name__ == "__main__":
    unittest.main()
