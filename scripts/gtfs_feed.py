"""Watch Delhi Open Transit Data for a new DMRC GTFS feed.

Usage:
  python3 scripts/gtfs_feed.py check --download feed.zip      # fetch from OTD and compare
  python3 scripts/gtfs_feed.py check --feed path/to/DMRC_GTFS # compare a zip or folder you already have
  python3 scripts/gtfs_feed.py record path/to/DMRC_GTFS       # make this feed the known one

The known feed is scripts/gtfs_feed.json. A feed counts as new when the contents of its .txt files
differ, not when the zip does: OTD builds the zip on request, so its bytes, dates and headers can
change while the timetable doesn't. `check` prints a Markdown summary (old and new counts side by
side) and, inside GitHub Actions, sets the step outputs `changed` and `fingerprint`.

OTD serves the DMRC feed from a form: GET the page, then submit its form (CSRF token, usage type,
purpose) back. Transitous fetches it the same way (github.com/public-transport/transitous feeds/in-dl.json).
If no form returns a zip, the page is saved as otd-page.html so the change can be seen.
Only the standard library is needed.
"""
import argparse, datetime, hashlib, html.parser, http.cookiejar, io, json, os, re, sys, urllib.error, urllib.parse, urllib.request, zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
KNOWN = os.path.join(HERE, "gtfs_feed.json")
URL = "https://otd.delhi.gov.in/data/staticDMRC/"
UA = "Mozilla/5.0 (compatible; gtfs-feed-watch/1.0)"


def read_feed(path):
    """{file name: bytes} for the .txt files of a GTFS zip or folder (subfolders in a zip are flattened)."""
    out = {}
    if os.path.isdir(path):
        for n in sorted(os.listdir(path)):
            if n.endswith(".txt"):
                with open(os.path.join(path, n), "rb") as f:
                    out[n] = f.read()
    else:
        with zipfile.ZipFile(path) as z:
            for n in z.namelist():
                if n.endswith(".txt") and not n.startswith("__MACOSX"):
                    out[os.path.basename(n)] = z.read(n)
    if "stops.txt" not in out or "stop_times.txt" not in out:
        raise SystemExit(f"{path}: not a GTFS feed (no stops.txt or stop_times.txt)")
    return out


def _clean(b):
    return b.lstrip(b"\xef\xbb\xbf").replace(b"\r\n", b"\n").rstrip(b"\n")


def fingerprint(files):
    h = hashlib.sha256()
    for n in sorted(files):
        h.update(n.encode() + b"\0" + hashlib.sha256(_clean(files[n])).digest())
    return h.hexdigest()


def _rows(b):
    t = _clean(b).decode("utf-8", "replace")
    lines = t.split("\n")
    head = lines[0].split(",") if lines and lines[0] else []
    return head, [l for l in lines[1:] if l.strip()]


def summary(files):
    s = dict(files=sorted(files))
    for n in ("agency", "stops", "routes", "trips", "stop_times", "shapes"):
        if f"{n}.txt" in files:
            s[n] = len(_rows(files[f"{n}.txt"])[1])
    for n, cols in (("calendar", ("start_date", "end_date")), ("feed_info", ("feed_start_date", "feed_end_date"))):
        if f"{n}.txt" in files:
            head, rows = _rows(files[f"{n}.txt"])
            for c in cols:
                if c in head:
                    i = head.index(c)
                    v = sorted(r.split(",")[i] for r in rows if len(r.split(",")) > i and r.split(",")[i])
                    if v:
                        s[c] = v[0] if c.endswith("start_date") else v[-1]
    if "feed_info.txt" in files:
        head, rows = _rows(files["feed_info.txt"])
        if "feed_version" in head and rows:
            s["feed_version"] = rows[0].split(",")[head.index("feed_version")]
    return s


class _Forms(html.parser.HTMLParser):
    """Collects every <form>: its action, method and fields. A <select> gets the option matching PREFER, else its first."""
    def __init__(self):
        super().__init__(); self.forms, self._sel = [], None

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "form":
            self.forms.append(dict(action=a.get("action") or "", method=(a.get("method") or "get").lower(), fields={}))
        elif not self.forms:
            return
        elif tag == "input" and a.get("name") and a.get("type", "text").lower() in ("radio", "checkbox"):
            f, v = self.forms[-1]["fields"], a.get("value") or "on"
            if f.get(a["name"]) is None or any(x in v.lower() for x in PREFER):
                f[a["name"]] = v
        elif tag == "input" and a.get("name") and a.get("type", "text").lower() not in ("submit", "button"):
            self.forms[-1]["fields"][a["name"]] = a.get("value") or ""
        elif tag == "select" and a.get("name"):
            self._sel = a["name"]; self.forms[-1]["fields"].setdefault(self._sel, None)
        elif tag == "option" and self._sel:
            v = a.get("value", ""); f = self.forms[-1]["fields"]
            if v and (f[self._sel] is None or any(x in v.lower() for x in PREFER)):
                f[self._sel] = v

    def handle_endtag(self, tag):
        if tag == "select":
            self._sel = None


PREFER = ("non-commercial", "non_commercial", "noncommercial", "academ")
# OTD's form asks for a name and an e-mail. Set OTD_NAME / OTD_EMAIL (repository variables in the workflow)
# if it starts insisting on real ones.
DEFAULTS = {"name": "GTFS feed watcher", "email": ""}


def download(out, url=URL, timeout=120):
    """Fetch the DMRC GTFS zip from OTD into `out`.

    The page (Nov 2026) has one Django form per download button, each posting back to the page with a CSRF
    token, `dataDownloaded`, a usage-type radio, purpose checkboxes, name and e-mail. Every form carrying the
    token is tried in order (the first is "Download Data", the whole zip) until one returns a zip.
    """
    jar = http.cookiejar.CookieJar()
    op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
    op.addheaders = [("User-Agent", UA)]
    try:
        with op.open(url, timeout=timeout) as f:
            page = f.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        raise SystemExit(f"GET {url} failed: HTTP {e.code} {e.reason}")
    fp = _Forms(); fp.feed(page)
    forms = [f for f in fp.forms if "csrfmiddlewaretoken" in f["fields"]]
    if not forms:
        _keep(page)
        raise SystemExit(f"{url}: no form with a csrfmiddlewaretoken on the page; OTD's download page has changed (saved as otd-page.html)")
    tried = []
    for form in forms:
        target = urllib.parse.urljoin(url, form["action"]) if form["action"] else url
        fields = {k: v or "" for k, v in form["fields"].items()}
        for k, env in (("name", "OTD_NAME"), ("email", "OTD_EMAIL")):
            if k in fields and not fields[k]:
                fields[k] = os.environ.get(env) or DEFAULTS[k]
        data = urllib.parse.urlencode(fields).encode()
        headers = {"Content-Type": "application/x-www-form-urlencoded", "Referer": url}
        if not any(c.name == "csrftoken" for c in jar):
            headers["Cookie"] = f"csrftoken={fields['csrfmiddlewaretoken']}"
        req = urllib.request.Request(target, data=data, headers=headers) if form["method"] == "post" else \
            urllib.request.Request(target + ("&" if "?" in target else "?") + data.decode(), headers=headers)
        try:
            with op.open(req, timeout=timeout) as f:
                body, h = f.read(), dict(f.headers)
        except urllib.error.HTTPError as e:
            tried.append(f"{form['method'].upper()} {target} with {sorted(fields)}: HTTP {e.code}"); continue
        if body.startswith(b"PK"):
            with open(out, "wb") as f:
                f.write(body)
            return {k: h[k] for k in ("Last-Modified", "ETag", "Content-Disposition", "Content-Length") if k in h}
        tried.append(f"{form['method'].upper()} {target} with {sorted(fields)}: {h.get('Content-Type')}, {len(body)} bytes, not a zip")
    _keep(page)
    raise SystemExit("no form on the page returned a zip (page saved as otd-page.html):\n  " + "\n  ".join(tried))


def _keep(page):
    with open("otd-page.html", "w", encoding="utf-8") as f:
        f.write(page)


def compare(known, files, fp, headers=None):
    new = summary(files)
    changed = fp != known.get("fingerprint")
    keys = [k for k in ("stops", "routes", "trips", "stop_times", "shapes", "start_date", "end_date",
                        "feed_start_date", "feed_end_date", "feed_version") if k in new or k in known.get("summary", {})]
    L = ["## DMRC GTFS on Open Transit Data", "",
         ("**A new feed.** Its contents differ from the one Maptro is built from." if changed else
          "No change: the feed is the one Maptro is built from."), "",
         f"Checked {datetime.datetime.now(datetime.timezone.utc):%Y-%m-%d %H:%M} UTC. "
         f"Fingerprint `{fp[:12]}` (known: `{known.get('fingerprint', '')[:12]}`, {known.get('source', '')}).", "",
         "| | Known feed | This feed |", "|---|---:|---:|"]
    for k in keys:
        a, b = known.get("summary", {}).get(k, ""), new.get(k, "")
        L.append(f"| {k} | {a} | {'**' + str(b) + '**' if a != b else b} |")
    added = sorted(set(new["files"]) - set(known.get("summary", {}).get("files", [])))
    gone = sorted(set(known.get("summary", {}).get("files", [])) - set(new["files"]))
    if added or gone:
        L += ["", f"Files added: {', '.join(added) or 'none'}. Files gone: {', '.join(gone) or 'none'}."]
    if headers:
        L += ["", "Download headers: " + ", ".join(f"{k}: {v}" for k, v in headers.items())]
    return changed, "\n".join(L) + "\n"


def gh_output(**kv):
    p = os.environ.get("GITHUB_OUTPUT")
    if p:
        with open(p, "a") as f:
            for k, v in kv.items():
                f.write(f"{k}={v}\n")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("check")
    g = c.add_mutually_exclusive_group(required=True)
    g.add_argument("--download", metavar="ZIP", help="fetch the feed from OTD into this file")
    g.add_argument("--feed", help="a GTFS zip or folder already on disk")
    c.add_argument("--url", default=URL)
    c.add_argument("--known", default=KNOWN)
    c.add_argument("--report", help="also write the Markdown summary here")
    r = sub.add_parser("record")
    r.add_argument("feed")
    r.add_argument("--source", required=True, help="where this feed came from, with a date")
    r.add_argument("--known", default=KNOWN)
    a = ap.parse_args(argv)

    if a.cmd == "record":
        files = read_feed(a.feed)
        doc = dict(fingerprint=fingerprint(files), source=a.source, summary=summary(files))
        with open(a.known, "w") as f:
            f.write(json.dumps(doc, indent=1) + "\n")
        print(json.dumps(doc, indent=1))
        return 0

    headers = None
    if a.download:
        try:
            headers = download(a.download, a.url)
        except OSError as e:  # URLError, timeouts, refused connections
            raise SystemExit(f"could not download the feed from {a.url}: {e}")
    path = a.download or a.feed
    files = read_feed(path)
    fp = fingerprint(files)
    with open(a.known) as f:
        known = json.load(f)
    changed, text = compare(known, files, fp, headers)
    print(text)
    if a.report:
        with open(a.report, "w") as f:
            f.write(text)
    gh_output(changed=str(changed).lower(), fingerprint=fp)
    return 0


if __name__ == "__main__":
    sys.exit(main())
