"""The dashboard's local server, which had no tests at all (issue #160).

Every assertion here was a probe against the running server first: it handed
out the whole repository root with listings, answered `/dashboard` with 200
instead of 301 (so the page loaded under a base URL one level too high and
then blamed the user's working directory), checked no `Host`, sent no
`Last-Modified` or `ETag` on the gzip branch, and cleared its whole cache at
512 entries.

The server is started for real on an ephemeral port over a temporary root, so
what is asserted is what a browser gets.
"""

from __future__ import annotations

import http.client
import importlib.util
import json
import os
import tempfile
import threading
import unittest
import unittest.mock
from http.server import ThreadingHTTPServer
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

_spec = importlib.util.spec_from_file_location(
    "serve_dashboard", REPO_ROOT / "scripts" / "serve_dashboard.py"
)
serve = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(serve)


class ServerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._tmp = tempfile.TemporaryDirectory()
        cls.root = Path(cls._tmp.name)
        (cls.root / "dashboard").mkdir()
        build = cls.root / "frontend" / "dist"
        (build / "_astro").mkdir(parents=True)
        (build / "index.html").write_text(
            '<html><body>Astro dashboard<script type="module" src="/_astro/app.js"></script></body></html>',
            encoding="utf-8",
        )
        (build / "_astro" / "app.js").write_text('console.log("Astro bundle");', encoding="utf-8")
        (build / "_astro" / "app.css").write_text('body { color: #1b313f; }', encoding="utf-8")
        # A forgotten MVP file must never shadow the maintained build.
        (cls.root / "dashboard" / "index.html").write_text("retired MVP", encoding="utf-8")
        (cls.root / "frontend" / "src").mkdir()
        (cls.root / "frontend" / "src" / "private.js").write_text("source only", encoding="utf-8")
        (cls.root / "dashboard" / "people.json").write_text(
            json.dumps({"people": [{"n": "Vardenė PAVARDENĖ"}] * 200}), encoding="utf-8"
        )
        (cls.root / "data" / "2016-seimo").mkdir(parents=True)
        (cls.root / "data" / "2016-seimo" / "x-2016-seimo.json").write_text("{}", encoding="utf-8")
        (cls.root / "docs").mkdir()
        (cls.root / "docs" / "concept-map.json").write_text("{}", encoding="utf-8")
        (cls.root / "docs" / "DASHBOARD.md").write_text("# not for the page\n", encoding="utf-8")
        (cls.root / "dashboard" / "field-labels.json").write_text('{"turtas": "Turtas"}', encoding="utf-8")
        (cls.root / "dashboard" / "merge-review.csv").write_text("pid,pid\n", encoding="utf-8")
        (cls.root / "portraits").mkdir()
        (cls.root / "portraits" / "p0123456789ab.webp").write_bytes(b"RIFF\x04\x00\x00\x00WEBP")
        # What the server must not serve.
        (cls.root / ".git").mkdir()
        (cls.root / ".git" / "config").write_text("[core]\n", encoding="utf-8")
        (cls.root / "conftest.py").write_text("# secret\n", encoding="utf-8")
        (cls.root / "scraper").mkdir()
        (cls.root / "scraper" / "person_overrides.json").write_text("{}", encoding="utf-8")
        (cls.root / "scripts").mkdir()
        (cls.root / "scripts" / "serve_dashboard.py").write_text("# source\n", encoding="utf-8")
        (cls.root / "frontend" / "astro.config.mjs").write_text("// config\n", encoding="utf-8")

        cls._cwd = os.getcwd()
        os.chdir(cls.root)

        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), serve.GzipHandler)
        cls.port = cls.server.server_address[1]
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.server.shutdown()
        os.chdir(cls._cwd)
        cls._tmp.cleanup()

    def get(self, path, headers=None, method="GET"):
        connection = http.client.HTTPConnection("127.0.0.1", self.port, timeout=10)
        try:
            connection.request(method, path, headers=headers or {})
            response = connection.getresponse()
            body = response.read()
            return response.status, dict(response.getheaders()), body
        finally:
            connection.close()

    GZIP = {"Accept-Encoding": "gzip"}

    # -- what is served -----------------------------------------------------

    def test_the_site_root_is_the_page(self):
        # Issue #184: `/` used to 302 to `/dashboard/`.
        status, _, body = self.get("/", self.GZIP)
        self.assertEqual(status, 200)
        self.assertIn(b"Astro dashboard", __import__("gzip").decompress(body))
        for path in ("/index.html", "/?view=review"):
            with self.subTest(path):
                status, _, body = self.get(path)
                self.assertEqual(status, 200)
                self.assertIn(b"Astro dashboard", body)

    def test_the_index_and_labels_are_served_beside_the_page(self):
        # They stay in dashboard/ on disk, where every builder writes them.
        status, _, body = self.get("/field-labels.json")
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body), {"turtas": "Turtas"})
        status, _, body = self.get("/people.json")
        self.assertEqual(status, 200)
        self.assertEqual(len(json.loads(body)["people"]), 200)

    def test_bundled_javascript_and_css_use_the_dashboard_asset_urls(self):
        for filename, marker, mime in (
            ("app.js", b"Astro bundle", "javascript"),
            ("app.css", b"#1b313f", "text/css"),
        ):
            with self.subTest(filename):
                path = f"/_astro/{filename}"
                status, headers, compressed = self.get(path, self.GZIP)
                self.assertEqual(status, 200)
                self.assertIn(mime, headers["Content-Type"])
                self.assertIn(marker, __import__("gzip").decompress(compressed))
                status, _, body = self.get(path, method="HEAD")
                self.assertEqual(status, 200)
                self.assertEqual(body, b"")
                status, headers, raw = self.get(path)
                self.assertEqual(status, 200)
                self.assertNotIn("Content-Encoding", headers)
                self.assertIn(marker, raw)

    def test_retired_html_does_not_shadow_the_astro_build(self):
        for path in ("/index.html", "/dashboard/index.html", "/asmuo/x"):
            with self.subTest(path):
                _, _, body = self.get(path)
                self.assertNotIn(b"retired MVP", body)
        status, _, body = self.get("/index.html")
        self.assertIn(b"Astro dashboard", body)

    def test_frontend_source_and_build_paths_are_not_public_urls(self):
        # The build is the root now, so these resolve inside it and miss.
        for path in (
            "/frontend/src/private.js",
            "/frontend/dist/index.html",
            "/frontend/astro.config.mjs",
            "/frontend/../frontend/src/private.js",
        ):
            with self.subTest(path):
                status, _, body = self.get(path)
                self.assertEqual(status, 404)
                self.assertNotIn(b"source only", body)
                self.assertNotIn(b"Astro dashboard", body)

    def test_people_json_is_gzipped(self):
        status, headers, body = self.get("/people.json", self.GZIP)
        self.assertEqual(status, 200)
        self.assertEqual(headers["Content-Encoding"], "gzip")
        decoded = __import__("gzip").decompress(body)
        self.assertEqual(len(json.loads(decoded)["people"]), 200)
        self.assertLess(len(body), len(decoded), "gzip must actually compress it")

    def test_a_record_and_the_concept_map(self):
        for path in ("/data/2016-seimo/x-2016-seimo.json", "/docs/concept-map.json"):
            with self.subTest(path):
                self.assertEqual(self.get(path, self.GZIP)[0], 200)

    def test_an_uncompressed_client_still_gets_the_file(self):
        status, headers, body = self.get("/people.json")
        self.assertEqual(status, 200)
        self.assertNotIn("Content-Encoding", headers)
        self.assertEqual(len(json.loads(body)["people"]), 200)

    # -- what is not --------------------------------------------------------

    def test_no_repository_path_outside_the_served_set(self):
        # The server used to answer all of these 200. With the build at the
        # root (issue #184) every one resolves inside frontend/dist and 404s,
        # the retired /dashboard/ URLs included: the page was never published
        # there, so they are not redirected.
        for path in (
            "/.git/config",
            "/conftest.py",
            "/scraper/person_overrides.json",
            "/scripts/serve_dashboard.py",
            "/docs/DASHBOARD.md",
            "/merge-review.csv",
            "/dashboard/merge-review.csv",
            "/dashboard/people.json",
            "/dashboard/index.html",
            "/dashboard/",
        ):
            for method in ("GET", "HEAD"):
                with self.subTest(path=path, method=method):
                    status, _, body = self.get(path, self.GZIP, method=method)
                    self.assertEqual(status, 404)
                    for secret in (b"[core]", b"secret", b"source", b"pid,pid", b"not for the page"):
                        self.assertNotIn(secret, body)

    def test_the_guard_refuses_what_translate_path_would_not_produce(self):
        # Defence in depth: the guard re-checks each destination, so a
        # mapping mistake fails closed.
        root = Path("/srv/vrk")
        for path, served in (
            ("frontend/dist/index.html", True),
            ("frontend/dist/_astro/app.js", True),
            ("data/2016-seimo/x.json", True),
            ("portraits/p0123456789ab.webp", True),
            ("docs/concept-map.json", True),
            ("dashboard/people.json", True),
            ("dashboard/field-labels.json", True),
            ("dashboard/merge-review.csv", False),
            ("dashboard/index.html", False),
            ("docs/DASHBOARD.md", False),
            ("frontend/src/private.js", False),
            ("frontend/distx/index.html", False),
            ("scripts/serve_dashboard.py", False),
            (".git/config", False),
            ("", False),
        ):
            with self.subTest(path):
                self.assertEqual(serve._is_served(root / path, root), served)
        self.assertFalse(serve._is_served(Path("/etc/passwd"), root))

    def test_a_directory_gets_no_listing(self):
        # `/` listed `.claude/`, `.git`, `.run-state/`, `samples-full/`, …
        self.assertEqual(self.get("/data/", self.GZIP)[0], 404)
        self.assertEqual(self.get("/data/2016-seimo/", self.GZIP)[0], 404)

    def test_a_foreign_host_is_refused(self):
        # Nothing checked `Host`, so a page the user visits in the same
        # browser could read the served root as same-origin after a DNS
        # rebind.
        for path in ("/people.json", "/asmuo/x"):
            with self.subTest(path):
                status, _, _ = self.get(path, {**self.GZIP, "Host": "evil.example.com"})
                self.assertEqual(status, 403)
        for host in ("127.0.0.1", f"127.0.0.1:{self.port}", "localhost", f"localhost:{self.port}"):
            with self.subTest(host):
                self.assertEqual(self.get("/", {**self.GZIP, "Host": host})[0], 200)

    def test_traversal_stays_blocked(self):
        for path in (
            "/dashboard/../conftest.py",
            "/../conftest.py",
            "/dashboard/%2e%2e/conftest.py",
            "/%2e%2e/conftest.py",
            "/data/../conftest.py",
            "/portraits/%2e%2e/conftest.py",
            "/docs/../conftest.py",
            "/_astro/../../../conftest.py",
        ):
            with self.subTest(path):
                status, _, body = self.get(path, self.GZIP)
                self.assertNotEqual(status, 200)
                self.assertNotIn(b"secret", body)

    def test_head_is_guarded_too(self):
        self.assertEqual(self.get("/conftest.py", self.GZIP, method="HEAD")[0], 404)
        self.assertEqual(self.get("/", self.GZIP, method="HEAD")[0], 200)
        self.assertEqual(self.get("/people.json", self.GZIP, method="HEAD")[0], 200)

    # -- redirects and page routes -------------------------------------------

    def test_a_directory_without_its_slash_redirects(self):
        # It answered 200 with the page, whose base URL is then one level too
        # high, so its first fetch 404'd and `bootFailed` told the user their
        # working directory was wrong.
        for path, location in (("/_astro", "/_astro/"), ("/data?x=1", "/data/?x=1")):
            with self.subTest(path):
                status, headers, _ = self.get(path, self.GZIP)
                self.assertEqual(status, 301)
                self.assertEqual(headers["Location"], location)

    # Issue #184: every view has its own path, answered with the page itself;
    # the page's router picks the view. Only those paths fall back -- a
    # mistyped asset is still a 404, and no repository root becomes reachable.

    ROUTES = (
        "/asmuo/birute-vesaite-p7d185515b624",
        "/asmuo/p7d185515b624",
        "/asmuo/nobody/",
        "/palyginti/p7d185515b624,p0123456789ab",
        "/suvestine",
        "/suvestine/",
        "/iskelejai",
        "/apreptis",
        "/pokyciai?x=1",
    )

    def test_every_route_is_answered_with_the_page(self):
        for path in self.ROUTES:
            for headers, method in ((self.GZIP, "GET"), ({}, "GET"), ({}, "HEAD")):
                with self.subTest(path=path, headers=headers, method=method):
                    status, got, body = self.get(path, headers, method)
                    got = {name.lower(): value for name, value in got.items()}
                    self.assertEqual(status, 200)
                    self.assertIn("text/html", got["content-type"])
                    self.assertEqual(got["cache-control"], "no-cache")
                    if method == "GET":
                        if headers:
                            body = __import__("gzip").decompress(body)
                        self.assertIn(b"Astro dashboard", body)

    def test_only_the_route_paths_fall_back(self):
        for path in (
            "/asmuo",
            "/asmuo/x/y",
            "/asmuo/../conftest.py",
            "/palyginti/a/b",
            "/suvestine/x",
            "/suvestines",
            "/statistika",
            "/dashboard/",
            "/dashboard",
            "/dashboard/people.json",
            "/_astro/missing.js",
            "/data/2016-seimo/missing.json",
            "/portraits/pmissing.webp",
        ):
            with self.subTest(path):
                status, headers, body = self.get(path, self.GZIP)
                self.assertEqual(status, 404)
                self.assertNotIn("Location", headers)
                self.assertNotIn(b"Astro dashboard", body)
                self.assertNotIn(b"secret", body)

    def test_route_matching(self):
        for path, expected in (
            ("/asmuo/x", True),
            ("/asmuo/x/", True),
            ("/asmuo/", True),
            ("/palyginti/a,b?x=1", True),
            ("/apreptis/", True),
            ("/asmuo", False),
            ("/asmuo/x/y", False),
            ("/apreptis/x", False),
            ("/", False),
            ("/people.json", False),
        ):
            with self.subTest(path):
                self.assertIs(serve.is_route(path), expected)

    # -- caching and headers -----------------------------------------------

    def test_a_conditional_request_gets_a_304(self):
        _, headers, body = self.get("/people.json", self.GZIP)
        etag, modified = headers["ETag"], headers["Last-Modified"]
        self.assertTrue(etag and modified)
        status, _, empty = self.get(
            "/people.json", {**self.GZIP, "If-None-Match": etag}
        )
        self.assertEqual(status, 304)
        self.assertEqual(empty, b"")
        status, _, _ = self.get(
            "/people.json", {**self.GZIP, "If-Modified-Since": modified}
        )
        self.assertEqual(status, 304)
        # A different ETag still gets the body.
        status, _, again = self.get(
            "/people.json", {**self.GZIP, "If-None-Match": 'W/"0000000000000000"'}
        )
        self.assertEqual(status, 200)
        self.assertEqual(again, body)

    # Issue #186: every visit re-downloaded the 7 MB index, because the page
    # said no-store and so did the server. Hashed build assets are now cached
    # for good; everything rewritten in place is kept but revalidated.

    def test_cache_control_per_path_class(self):
        cases = {
            "/_astro/app.js": serve.IMMUTABLE_CACHE_CONTROL,
            "/_astro/app.css": serve.IMMUTABLE_CACHE_CONTROL,
            "/": "no-cache",
            "/?q=x": "no-cache",
            "/index.html": "no-cache",
            "/people.json": "no-cache",
            "/field-labels.json": "no-cache",
            "/data/2016-seimo/x-2016-seimo.json": "no-cache",
            "/docs/concept-map.json": "no-cache",
            # Issue #187: versioned portraits are a new URL per change.
            "/portraits/p0123456789ab.webp?v=2b7c6a62": serve.IMMUTABLE_CACHE_CONTROL,
            "/portraits/p0123456789ab.webp": "no-cache",
            "/portraits/p0123456789ab.webp?v=": "no-cache",
        }
        self.assertEqual(serve.IMMUTABLE_CACHE_CONTROL, "public, max-age=31536000, immutable")
        for path, expected in cases.items():
            # Both branches: the gzip one and the stdlib one an identity
            # client (or a HEAD) falls through to.
            for headers, method in ((self.GZIP, "GET"), ({}, "GET"), (self.GZIP, "HEAD")):
                with self.subTest(path=path, headers=headers, method=method):
                    status, got, _ = self.get(path, headers, method)
                    self.assertEqual(status, 200)
                    self.assertEqual(got.get("Cache-Control"), expected)

    def test_web_portraits_are_served_as_webp(self):
        # Issue #187: the one image root the page fetches from, uncompressed.
        status, headers, body = self.get("/portraits/p0123456789ab.webp?v=1", self.GZIP)
        headers = {name.lower(): value for name, value in headers.items()}
        self.assertEqual(status, 200)
        self.assertEqual(headers["content-type"], "image/webp")
        self.assertNotIn("content-encoding", headers)
        self.assertTrue(body.startswith(b"RIFF"))
        status, headers, _ = self.get("/portraits/pmissing.webp?v=1")
        self.assertEqual(status, 404)
        self.assertNotIn("Cache-Control", headers)
        status, _, _ = self.get("/portraits/")
        self.assertEqual(status, 404)

    def test_a_304_repeats_the_cache_control(self):
        for path in ("/people.json", "/_astro/app.js"):
            with self.subTest(path):
                _, headers, _ = self.get(path, self.GZIP)
                status, again, _ = self.get(
                    path, {**self.GZIP, "If-Modified-Since": headers["Last-Modified"]}
                )
                self.assertEqual(status, 304)
                self.assertEqual(again["Cache-Control"], headers["Cache-Control"])

    def test_errors_and_redirects_are_not_marked_cacheable(self):
        # An immutable 404 under _astro/ would pin a missing asset at the
        # edge for a year.
        for path in ("/_astro/missing.js", "/conftest.py", "/dashboard/", "/dashboard/_astro/app.js", "/_astro"):
            with self.subTest(path):
                status, headers, _ = self.get(path, self.GZIP)
                self.assertIn(status, (301, 302, 403, 404))
                self.assertNotIn("Cache-Control", headers)

    def test_if_modified_since_alone_revalidates(self):
        # What a browser sends from behind Cloudflare, which drops the origin
        # ETag when it recompresses: no If-None-Match, only the date.
        for path in ("/people.json", "/data/2016-seimo/x-2016-seimo.json"):
            for encoding in (self.GZIP, {}):
                with self.subTest(path=path, encoding=encoding):
                    _, headers, _ = self.get(path, encoding)
                    status, _, empty = self.get(
                        path, {**encoding, "If-Modified-Since": headers["Last-Modified"]}
                    )
                    self.assertEqual(status, 304)
                    self.assertEqual(empty, b"")

    def test_a_rewritten_record_is_never_answered_304(self):
        # The guarantee no-store used to buy: a record backfilled in place
        # must reach a browser holding the old copy on its next load.
        record = self.root / "data" / "2016-seimo" / "rewritten-2016-seimo.json"
        record.write_text('{"turtas": null}', encoding="utf-8")
        old = record.stat().st_mtime - 60
        os.utime(record, (old, old))
        url = "/data/2016-seimo/rewritten-2016-seimo.json"
        for encoding in (self.GZIP, {}):
            with self.subTest(encoding=encoding):
                record.write_text('{"turtas": null}', encoding="utf-8")
                os.utime(record, (old, old))
                _, headers, _ = self.get(url, encoding)
                record.write_text('{"turtas": 1200}', encoding="utf-8")
                status, _, body = self.get(
                    url, {**encoding, "If-Modified-Since": headers["Last-Modified"]}
                )
                self.assertEqual(status, 200)
                if encoding:
                    body = __import__("gzip").decompress(body)
                self.assertEqual(json.loads(body), {"turtas": 1200})

    def test_if_none_match_takes_precedence_and_compares_weakly(self):
        _, headers, _ = self.get("/people.json", self.GZIP)
        etag, modified = headers["ETag"], headers["Last-Modified"]
        # A mismatched tag wins over a date that alone would be a 304.
        status, _, _ = self.get(
            "/people.json",
            {**self.GZIP, "If-None-Match": 'W/"0000000000000000"', "If-Modified-Since": modified},
        )
        self.assertEqual(status, 200)
        # A list, and a tag a proxy stripped of its W/ prefix, both match.
        for match in (f'"aaaa", {etag}', etag.removeprefix("W/")):
            with self.subTest(match):
                status, _, _ = self.get(
                    "/people.json", {**self.GZIP, "If-None-Match": match}
                )
                self.assertEqual(status, 304)

    def test_every_response_carries_the_hardening_headers(self):
        for path in ("/", "/people.json", "/conftest.py", "/asmuo/x"):
            with self.subTest(path):
                _, headers, _ = self.get(path, self.GZIP)
                self.assertEqual(headers["X-Content-Type-Options"], "nosniff")
                self.assertIn("default-src 'self'", headers["Content-Security-Policy"])
                self.assertEqual(headers["Referrer-Policy"], "no-referrer")
                script_policy = next(
                    rule.strip() for rule in headers["Content-Security-Policy"].split(";")
                    if rule.strip().startswith("script-src ")
                )
                self.assertNotIn("unsafe-inline", script_policy)


class CacheTests(unittest.TestCase):
    """The cache used to `clear()` at 512 entries, so every ~275 person views
    threw away the compressed 7 MB `people.json` with everything else."""

    def setUp(self) -> None:
        serve._CACHE.clear()
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)
        self.addCleanup(serve._CACHE.clear)

    def _file(self, name: str, text: str) -> Path:
        path = self.root / name
        path.write_text(text, encoding="utf-8")
        return path

    def test_a_hit_returns_the_cached_body(self):
        path = self._file("a.json", '{"a": 1}')
        first = serve._gzipped(path)
        self.assertIs(serve._gzipped(path), first)

    def test_a_changed_mtime_recompresses(self):
        path = self._file("a.json", '{"a": 1}')
        first = serve._gzipped(path)
        os.utime(path, (0, 0))
        path.write_text('{"a": 2}', encoding="utf-8")
        os.utime(path, (1, 1))
        self.assertNotEqual(serve._gzipped(path), first)

    def test_it_evicts_one_entry_rather_than_clearing(self):
        with unittest.mock.patch.object(serve, "_CACHE_MAX_ENTRIES", 3):
            paths = [self._file(f"f{i}.json", f'{{"i": {i}}}') for i in range(4)]
            for path in paths:
                serve._gzipped(path)
            self.assertEqual(len(serve._CACHE), 3)
            # The first is the least recently used and the only one gone.
            self.assertNotIn(str(paths[0]), serve._CACHE)
            for path in paths[1:]:
                self.assertIn(str(path), serve._CACHE)

    def test_a_re_read_entry_survives_eviction(self):
        with unittest.mock.patch.object(serve, "_CACHE_MAX_ENTRIES", 2):
            a, b, c = (self._file(f"{n}.json", '{"x": 1}') for n in "abc")
            serve._gzipped(a)
            serve._gzipped(b)
            serve._gzipped(a)  # a is now the most recently used
            serve._gzipped(c)
            self.assertIn(str(a), serve._CACHE)
            self.assertNotIn(str(b), serve._CACHE)


if __name__ == "__main__":
    unittest.main()
