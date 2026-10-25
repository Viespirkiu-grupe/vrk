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
        # The split index (issue #186), with the stale whole file an old
        # checkout still holds: it is no longer served.
        (cls.root / "dashboard" / "people-list.json").write_text(
            json.dumps({"build": "b1", "people": [{"n": "Vardenė PAVARDENĖ"}] * 200}), encoding="utf-8"
        )
        (cls.root / "dashboard" / "people-details.json").write_text(
            json.dumps({"build": "b1", "people": [[{"wp": "Vilniaus universitetas"}]] * 200}), encoding="utf-8"
        )
        (cls.root / "dashboard" / "people-version.json").write_text('{"build": "b1"}', encoding="utf-8")
        (cls.root / "dashboard" / "people.json").write_text('{"people": []}', encoding="utf-8")
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
        for path in ("/people-list.json", "/people-details.json"):
            with self.subTest(path):
                status, _, body = self.get(path)
                self.assertEqual(status, 200)
                self.assertEqual(len(json.loads(body)["people"]), 200)
        status, _, body = self.get("/people-version.json")
        self.assertEqual(json.loads(body), {"build": "b1"})
        # The whole index is not written any more; a stale copy stays dark.
        self.assertEqual(self.get("/people.json")[0], 404)

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

    def test_the_index_is_gzipped(self):
        status, headers, body = self.get("/people-list.json", self.GZIP)
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
        status, headers, body = self.get("/people-list.json")
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
            ("dashboard/people-list.json", True),
            ("dashboard/people-details.json", True),
            ("dashboard/people-version.json", True),
            ("dashboard/people.json", False),
            ("dashboard/people-list.json.br", False),
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
        for path in ("/people-list.json", "/asmuo/x"):
            with self.subTest(path):
                status, _, _ = self.get(path, {**self.GZIP, "Host": "evil.example.com"})
                self.assertEqual(status, 403)
        for host in ("127.0.0.1", f"127.0.0.1:{self.port}", "localhost", f"localhost:{self.port}"):
            with self.subTest(host):
                self.assertEqual(self.get("/", {**self.GZIP, "Host": host})[0], 200)

    # -- listening in a container (issue #186) -------------------------------

    def serve(self, *args, **kwargs):
        """Start `make_server(...)` on a free port; returns its port."""
        server = serve.make_server(*args, **kwargs)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        return server, server.server_address[1]

    def get_from(self, port, path, host):
        connection = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
        try:
            connection.request("GET", path, headers={**self.GZIP, "Host": host})
            response = connection.getresponse()
            response.read()
            return response.status, dict(response.getheaders())
        finally:
            connection.close()

    def test_the_default_server_answers_loopback_names_only(self):
        server, port = self.serve(port=0)
        self.assertEqual(server.server_address[0], "127.0.0.1")
        self.assertEqual(self.get_from(port, "/", "vrk.viespirkiai.org")[0], 403)
        self.assertEqual(self.get_from(port, "/", "localhost")[0], 200)

    def test_an_allowed_host_is_served_beside_the_loopback_names(self):
        _, port = self.serve(port=0, allow_hosts=["VRK.viespirkiai.org"])
        for host in ("vrk.viespirkiai.org", "vrk.viespirkiai.org:443", "Vrk.Viespirkiai.org", "localhost", "127.0.0.1"):
            with self.subTest(host):
                status, headers = self.get_from(port, "/people-list.json", host)
                self.assertEqual(status, 200)
                self.assertEqual(headers["Content-Encoding"], "gzip")
        self.assertEqual(self.get_from(port, "/", "evil.example.com")[0], 403)
        # The widening is per server: the stock handler is untouched.
        self.assertNotIn("vrk.viespirkiai.org", serve.GzipHandler.allowed_hosts)

    def test_a_bind_of_all_interfaces_is_honoured(self):
        server, port = self.serve("0.0.0.0", 0, ["vrk.viespirkiai.org"])
        self.assertEqual(server.server_address[0], "0.0.0.0")
        self.assertEqual(self.get_from(port, "/", "vrk.viespirkiai.org")[0], 200)

    def test_listen_options_from_flags_and_env(self):
        args = serve.parse_args([], environ={})
        self.assertEqual((args.bind, args.port, args.allow_hosts), ("127.0.0.1", 8791, []))
        env = {"VRK_BIND": "0.0.0.0", "VRK_PORT": "8080", "VRK_ALLOW_HOSTS": "vrk.viespirkiai.org, b.example ,"}
        args = serve.parse_args([], environ=env)
        self.assertEqual((args.bind, args.port, args.allow_hosts), ("0.0.0.0", 8080, ["b.example", "vrk.viespirkiai.org"]))
        args = serve.parse_args(["9000", "--bind", "10.0.0.2", "--allow-host", "a.example", "--allow-host", "c,d"], environ=env)
        self.assertEqual((args.bind, args.port, args.allow_hosts), ("10.0.0.2", 9000, ["a.example", "c", "d"]))

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
        self.assertEqual(self.get("/people-list.json", self.GZIP, method="HEAD")[0], 200)

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
            ("/people-list.json", False),
        ):
            with self.subTest(path):
                self.assertIs(serve.is_route(path), expected)

    # -- caching and headers -----------------------------------------------

    def test_a_conditional_request_gets_a_304(self):
        _, headers, body = self.get("/people-list.json", self.GZIP)
        etag, modified = headers["ETag"], headers["Last-Modified"]
        self.assertTrue(etag and modified)
        status, _, empty = self.get(
            "/people-list.json", {**self.GZIP, "If-None-Match": etag}
        )
        self.assertEqual(status, 304)
        self.assertEqual(empty, b"")
        status, _, _ = self.get(
            "/people-list.json", {**self.GZIP, "If-Modified-Since": modified}
        )
        self.assertEqual(status, 304)
        # A different ETag still gets the body.
        status, _, again = self.get(
            "/people-list.json", {**self.GZIP, "If-None-Match": 'W/"0000000000000000"'}
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
            "/people-version.json": "no-cache",
            "/people-list.json": "no-cache",
            "/people-details.json?v=0000000000000000": "no-cache",
            "/people-list.json?v=": "no-cache",
            "/field-labels.json": "no-cache",
            "/field-labels.json?v=x": "no-cache",
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
        # Not from the host's mime table: python:3.11-slim has none that knows
        # `.webp`, and the container sent application/octet-stream.
        with unittest.mock.patch("http.server.mimetypes.guess_type", return_value=(None, None)):
            _, headers, _ = self.get("/portraits/p0123456789ab.webp?v=1")
        self.assertEqual(headers["Content-type"], "image/webp")
        status, headers, _ = self.get("/portraits/pmissing.webp?v=1")
        self.assertEqual(status, 404)
        self.assertNotIn("Cache-Control", headers)
        status, _, _ = self.get("/portraits/")
        self.assertEqual(status, 404)

    def test_a_304_repeats_the_cache_control(self):
        for path in ("/people-list.json", "/_astro/app.js"):
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
        for path in ("/people-list.json", "/data/2016-seimo/x-2016-seimo.json"):
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
        _, headers, _ = self.get("/people-list.json", self.GZIP)
        etag, modified = headers["ETag"], headers["Last-Modified"]
        # A mismatched tag wins over a date that alone would be a 304.
        status, _, _ = self.get(
            "/people-list.json",
            {**self.GZIP, "If-None-Match": 'W/"0000000000000000"', "If-Modified-Since": modified},
        )
        self.assertEqual(status, 200)
        # A list, and a tag a proxy stripped of its W/ prefix, both match.
        for match in (f'"aaaa", {etag}', etag.removeprefix("W/")):
            with self.subTest(match):
                status, _, _ = self.get(
                    "/people-list.json", {**self.GZIP, "If-None-Match": match}
                )
                self.assertEqual(status, 304)

    def test_every_response_carries_the_hardening_headers(self):
        for path in ("/", "/people-list.json", "/conftest.py", "/asmuo/x"):
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


class VersionedIndexTests(unittest.TestCase):
    """Step 2 of issue #186: the split index's two big files are cached at the
    edge for good when asked for by their content hash, and leave the server
    as the brotli or gzip copy the index build wrote beside them."""

    LIST = b'{"build":"b1","people":[' + b",".join([b'{"n":"Vardene PAVARDENE"}'] * 300) + b"]}"
    BR = b"precompressed-brotli-stand-in"

    def setUp(self) -> None:
        serve._CACHE.clear()
        serve._HASHES.clear()
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)
        (self.root / "dashboard").mkdir()
        self.list = self.root / "dashboard" / "people-list.json"
        self.list.write_bytes(self.LIST)
        (self.root / "dashboard" / "people-list.json.gz").write_bytes(__import__("gzip").compress(self.LIST, 9))
        (self.root / "dashboard" / "people-list.json.br").write_bytes(self.BR)
        self.age_siblings(0)
        self.version = __import__("hashlib").blake2s(self.LIST, digest_size=8).hexdigest()
        cwd = os.getcwd()
        os.chdir(self.root)
        self.addCleanup(os.chdir, cwd)
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), serve.GzipHandler)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.server.shutdown)

    def age_siblings(self, seconds: int) -> None:
        """Give the .br/.gz copies the list's mtime, minus `seconds`."""
        mtime = self.list.stat().st_mtime
        for suffix in (".gz", ".br"):
            os.utime(self.list.with_name(self.list.name + suffix), (mtime - seconds, mtime - seconds))

    def get(self, path, headers=None):
        connection = http.client.HTTPConnection("127.0.0.1", self.server.server_address[1], timeout=10)
        try:
            connection.request("GET", path, headers=headers or {})
            response = connection.getresponse()
            return response.status, {k.lower(): v for k, v in response.getheaders()}, response.read()
        finally:
            connection.close()

    def test_the_build_writes_the_hash_the_server_checks(self):
        spec = importlib.util.spec_from_file_location("person_index_files", REPO_ROOT / "scripts" / "person_index_files.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        self.assertEqual(module.content_hash(self.LIST), self.version)
        self.assertEqual(serve.content_hash(self.list), self.version)

    def test_the_current_version_is_immutable(self):
        status, headers, _ = self.get(f"/people-list.json?v={self.version}", {"Accept-Encoding": "gzip"})
        self.assertEqual(status, 200)
        self.assertEqual(headers["cache-control"], serve.IMMUTABLE_CACHE_CONTROL)
        status, headers, _ = self.get(f"/people-list.json?v={self.version}", {"If-Modified-Since": headers["last-modified"]})
        self.assertEqual(status, 304)
        self.assertEqual(headers["cache-control"], serve.IMMUTABLE_CACHE_CONTROL)

    def test_any_other_version_is_revalidated(self):
        # A request that lands mid-deploy: the old version file's hash, the
        # new file on disk. Pinned for a year, the edge would serve these
        # bytes under the old name to every later visit.
        for query in ("", "?v=", "?v=0000000000000000", f"?v={self.version}x", f"?x=1&v={self.version[:-1]}"):
            with self.subTest(query):
                _, headers, _ = self.get(f"/people-list.json{query}")
                self.assertEqual(headers["cache-control"], "no-cache")
        self.list.write_bytes(self.LIST.replace(b"b1", b"b2"))
        _, headers, _ = self.get(f"/people-list.json?v={self.version}")
        self.assertEqual(headers["cache-control"], "no-cache")

    def test_brotli_is_preferred_then_gzip(self):
        status, headers, body = self.get("/people-list.json", {"Accept-Encoding": "gzip, deflate, br"})
        self.assertEqual((status, headers["content-encoding"], body), (200, "br", self.BR))
        self.assertEqual(headers["vary"], "Accept-Encoding")
        self.assertEqual(headers["content-length"], str(len(self.BR)))
        status, headers, body = self.get("/people-list.json", {"Accept-Encoding": "gzip"})
        self.assertEqual(headers["content-encoding"], "gzip")
        self.assertEqual(__import__("gzip").decompress(body), self.LIST)
        self.assertEqual(body, (self.root / "dashboard" / "people-list.json.gz").read_bytes())
        status, headers, body = self.get("/people-list.json", {"Accept-Encoding": "br;q=0, gzip"})
        self.assertEqual(headers["content-encoding"], "gzip")
        status, headers, body = self.get("/people-list.json")
        self.assertNotIn("content-encoding", headers)
        self.assertEqual(body, self.LIST)

    def test_an_older_copy_is_not_sent(self):
        # The list was rewritten after its copies: they are a previous build.
        self.age_siblings(5)
        status, headers, body = self.get("/people-list.json", {"Accept-Encoding": "br, gzip"})
        self.assertEqual(status, 200)
        self.assertEqual(headers["content-encoding"], "gzip")
        self.assertEqual(__import__("gzip").decompress(body), self.LIST)
        status, headers, body = self.get("/people-list.json", {"Accept-Encoding": "br"})
        self.assertNotIn("content-encoding", headers)
        self.assertEqual(body, self.LIST)

    def test_a_precompressed_copy_revalidates_by_date(self):
        _, headers, _ = self.get("/people-list.json", {"Accept-Encoding": "br"})
        status, again, body = self.get(
            "/people-list.json", {"Accept-Encoding": "br", "If-Modified-Since": headers["last-modified"]}
        )
        self.assertEqual((status, body), (304, b""))
        status, _, _ = self.get("/people-list.json", {"Accept-Encoding": "br", "If-None-Match": headers["etag"]})
        self.assertEqual(status, 304)

    def test_the_copies_are_not_urls(self):
        for path in ("/people-list.json.br", "/people-list.json.gz", "/dashboard/people-list.json.br"):
            with self.subTest(path):
                self.assertEqual(self.get(path)[0], 404)

    def test_accept_encoding_parsing(self):
        for header, expected in (
            ("", set()),
            ("gzip, deflate, br, zstd", {"gzip", "deflate", "br", "zstd"}),
            ("br;q=0, gzip;q=0.5", {"gzip"}),
            ("BR", {"br"}),
            ("gzip;q=x", set()),
        ):
            with self.subTest(header):
                self.assertEqual(serve.accepted_encodings(header), expected)


class CacheTests(unittest.TestCase):
    """The cache used to `clear()` at 512 entries, so every ~275 person views
    threw away the compressed 7 MB index with everything else."""

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
