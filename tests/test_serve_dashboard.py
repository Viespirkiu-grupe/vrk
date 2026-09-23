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
            '<html><body>Astro dashboard<script type="module" src="/dashboard/_astro/app.js"></script></body></html>',
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
        # What the server must not serve.
        (cls.root / ".git").mkdir()
        (cls.root / ".git" / "config").write_text("[core]\n", encoding="utf-8")
        (cls.root / "conftest.py").write_text("# secret\n", encoding="utf-8")
        (cls.root / "scraper").mkdir()
        (cls.root / "scraper" / "person_overrides.json").write_text("{}", encoding="utf-8")

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

    def test_the_dashboard_and_its_index(self):
        status, _, body = self.get("/dashboard/", self.GZIP)
        self.assertEqual(status, 200)
        self.assertIn(b"dashboard", __import__("gzip").decompress(body))

    def test_a_trailing_slash_with_query_does_not_redirect_again(self):
        status, _, body = self.get("/dashboard/?view=review")
        self.assertEqual(status, 200)
        self.assertIn(b"Astro dashboard", body)

    def test_bundled_javascript_and_css_use_the_dashboard_asset_urls(self):
        for filename, marker, mime in (
            ("app.js", b"Astro bundle", "javascript"),
            ("app.css", b"#1b313f", "text/css"),
        ):
            with self.subTest(filename):
                path = f"/dashboard/_astro/{filename}"
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
        status, _, body = self.get("/dashboard/index.html")
        self.assertEqual(status, 200)
        self.assertIn(b"Astro dashboard", body)
        self.assertNotIn(b"retired MVP", body)

    def test_frontend_source_and_build_paths_are_not_public_urls(self):
        for path in ("/frontend/src/private.js", "/frontend/dist/index.html", "/dashboard/../frontend/src/private.js"):
            with self.subTest(path):
                self.assertEqual(self.get(path)[0], 403)

    def test_people_json_is_gzipped(self):
        status, headers, body = self.get("/dashboard/people.json", self.GZIP)
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
        status, headers, body = self.get("/dashboard/people.json")
        self.assertEqual(status, 200)
        self.assertNotIn("Content-Encoding", headers)
        self.assertEqual(len(json.loads(body)["people"]), 200)

    # -- what is not --------------------------------------------------------

    def test_nothing_outside_the_three_directories(self):
        # The server used to answer all of these 200.
        for path in ("/.git/config", "/conftest.py", "/scraper/person_overrides.json"):
            with self.subTest(path):
                self.assertEqual(self.get(path, self.GZIP)[0], 403)

    def test_a_directory_gets_no_listing(self):
        # `/` listed `.claude/`, `.git`, `.run-state/`, `samples-full/`, …
        self.assertEqual(self.get("/data/", self.GZIP)[0], 404)
        self.assertEqual(self.get("/data/2016-seimo/", self.GZIP)[0], 404)

    def test_a_foreign_host_is_refused(self):
        # Nothing checked `Host`, so a page the user visits in the same
        # browser could read the served root as same-origin after a DNS
        # rebind.
        status, _, _ = self.get("/dashboard/people.json", {**self.GZIP, "Host": "evil.example.com"})
        self.assertEqual(status, 403)
        for host in ("127.0.0.1", f"127.0.0.1:{self.port}", "localhost", f"localhost:{self.port}"):
            with self.subTest(host):
                self.assertEqual(self.get("/dashboard/", {**self.GZIP, "Host": host})[0], 200)

    def test_traversal_stays_blocked(self):
        for path in ("/dashboard/../conftest.py", "/../conftest.py", "/dashboard/%2e%2e/conftest.py"):
            with self.subTest(path):
                self.assertNotEqual(self.get(path, self.GZIP)[0], 200)

    def test_head_is_guarded_too(self):
        self.assertEqual(self.get("/conftest.py", self.GZIP, method="HEAD")[0], 403)
        self.assertEqual(self.get("/dashboard/index.html", self.GZIP, method="HEAD")[0], 200)

    # -- the redirects ------------------------------------------------------

    def test_a_directory_without_its_slash_redirects(self):
        # It answered 200 with the page, whose base URL is then one level too
        # high, so its first fetch 404'd and `bootFailed` told the user their
        # working directory was wrong.
        status, headers, _ = self.get("/dashboard", self.GZIP)
        self.assertEqual(status, 301)
        self.assertEqual(headers["Location"], "/dashboard/")

    def test_a_dashboard_query_keeps_its_parameters_in_the_slash_redirect(self):
        status, headers, _ = self.get("/dashboard?view=review", self.GZIP)
        self.assertEqual(status, 301)
        self.assertEqual(headers["Location"], "/dashboard/?view=review")

    def test_the_root_points_at_the_dashboard(self):
        status, headers, _ = self.get("/", self.GZIP)
        self.assertEqual(status, 302)
        self.assertEqual(headers["Location"], "/dashboard/")

    # -- caching and headers -----------------------------------------------

    def test_a_conditional_request_gets_a_304(self):
        _, headers, body = self.get("/dashboard/people.json", self.GZIP)
        etag, modified = headers["ETag"], headers["Last-Modified"]
        self.assertTrue(etag and modified)
        status, _, empty = self.get(
            "/dashboard/people.json", {**self.GZIP, "If-None-Match": etag}
        )
        self.assertEqual(status, 304)
        self.assertEqual(empty, b"")
        status, _, _ = self.get(
            "/dashboard/people.json", {**self.GZIP, "If-Modified-Since": modified}
        )
        self.assertEqual(status, 304)
        # A different ETag still gets the body.
        status, _, again = self.get(
            "/dashboard/people.json", {**self.GZIP, "If-None-Match": 'W/"0000000000000000"'}
        )
        self.assertEqual(status, 200)
        self.assertEqual(again, body)

    def test_every_response_carries_the_hardening_headers(self):
        for path in ("/dashboard/", "/dashboard/people.json", "/conftest.py"):
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
