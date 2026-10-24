"""scripts/smoke_check.py against real servers on free ports (issue #188).

Against `scripts/serve_dashboard.py` over a synthetic repository, which must
pass, and against servers that are wrong in the ways a deploy goes wrong:
a page without its bundle (#183), a server that hands out the repository,
an index without portraits.
"""

from __future__ import annotations

import contextlib
import functools
import importlib.util
import io
import os
import shutil
import sys
import tempfile
import threading
import unittest
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import site_server  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[1]


def _load(name: str):
    spec = importlib.util.spec_from_file_location(name, REPO_ROOT / "scripts" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


smoke = _load("smoke_check")
serve = _load("serve_dashboard")


def run_quiet(base: str, **options) -> tuple[int, str]:
    out = io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(io.StringIO()):
        code = smoke.run(base, **options)
    return code, out.getvalue()


class AgainstServeDashboard(unittest.TestCase):
    """serve_dashboard.py serves the repository layout; the URLs are the same."""

    @classmethod
    def setUpClass(cls) -> None:
        cls._tmp = tempfile.TemporaryDirectory()
        cls.root = site_server.make_repo(Path(cls._tmp.name) / "repo")
        # What serve_dashboard must refuse, so the 404 checks mean something.
        for relative in ("scripts/deploy.sh", ".git/config", "dashboard/merge-review.csv"):
            path = cls.root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("private\n")
        cls._cwd = os.getcwd()
        os.chdir(cls.root)
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), serve.GzipHandler)
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()
        cls.base = f"http://127.0.0.1:{cls.server.server_address[1]}"

    @classmethod
    def tearDownClass(cls) -> None:
        cls.server.shutdown()
        cls.server.server_close()
        os.chdir(cls._cwd)
        cls._tmp.cleanup()

    def test_passes(self):
        code, out = run_quiet(self.base)
        self.assertEqual(code, 0, out)
        for line in (
            "ok    GET / -> 200 text/html",
            "ok    GET /_astro/index.abc.js -> 200",
            "ok    GET /people.json -> 200 application/json",
            "ok    GET /data/2020-seimo/vardenis-pavardenis-2020-seimo.json -> 200 application/json",
            f"ok    GET /portraits/{site_server.PID}.webp?v={site_server.PORTRAIT_VERSION} -> 200 image/webp",
            f"ok    GET /asmuo/vardenis-pavardenis-{site_server.PID} -> 200 text/html",
            "ok    GET /dashboard/ -> 404",
            "ok    GET /scripts/ -> 404",
            "ok    GET /.git/ -> 404",
        ):
            self.assertIn(line, out)

    def test_a_named_record(self):
        record = "/data/2019-prezidento/vardenis-pavardenis-2019-prezidento.json"
        code, out = run_quiet(self.base, record=record)
        self.assertEqual(code, 0, out)
        self.assertIn(f"ok    GET {record} -> 200", out)
        code, out = run_quiet(self.base, record="/data/2019-prezidento/nobody-2019-prezidento.json")
        self.assertEqual(code, 1)
        self.assertIn("is a candidacy in the index", out)

    def test_a_page_without_its_bundle_fails(self):
        # #183's failure, one level down: the HTML is there, the bundle is not.
        bundle = self.root / "frontend/dist/_astro/index.abc.js"
        moved = bundle.with_name("moved.js")
        bundle.rename(moved)
        try:
            code, out = run_quiet(self.base)
        finally:
            moved.rename(bundle)
        self.assertEqual(code, 1)
        self.assertIn("FAIL  GET /_astro/index.abc.js -> 200", out)

    def test_an_unreachable_server_fails(self):
        code, out = run_quiet("http://127.0.0.1:9")
        self.assertEqual(code, 1)
        self.assertIn("FAIL", out)


class AgainstWrongServers(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)

    def serve(self, handler) -> str:
        server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        return f"http://127.0.0.1:{server.server_address[1]}"

    def test_a_server_that_exposes_the_repository_fails(self):
        # The stock `python -m http.server` over a checkout: everything is a
        # file, nothing routes, and /scripts/ is a listing.
        repo = site_server.make_repo(self.root / "repo")
        (repo / "scripts").mkdir()
        (repo / "scripts" / "deploy.sh").write_text("#!/bin/sh\n")
        base = self.serve(functools.partial(SimpleHTTPRequestHandler, directory=str(repo)))
        code, out = run_quiet(base)
        self.assertEqual(code, 1)
        self.assertIn("FAIL  GET /scripts/ -> 404", out)
        self.assertIn("FAIL  GET / -> 200 text/html  (Cache-Control ''", out)
        self.assertIn("FAIL  security headers on /", out)

    def test_the_built_site_on_the_reference_server_passes(self):
        build_site = _load("build_site")
        site = self.root / "site"
        build_site.build_site(
            site_server.make_repo(self.root / "repo"), site,
            frontend="verify", index="reuse", portraits="reuse", jobs=1, corpus_tag="corpus-2026-10-25",
        )
        server, base = site_server.start(site)
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        code, out = run_quiet(base, expect_version="corpus-2026-10-25")
        self.assertEqual(code, 0, out)
        self.assertIn("ok    /VERSION is corpus-2026-10-25", out)
        code, out = run_quiet(base, expect_version="corpus-1999-01-01")
        self.assertEqual(code, 1)

    def test_an_index_without_portraits_fails(self):
        repo = site_server.make_repo(self.root / "repo")
        index = repo / "dashboard/people.json"
        index.write_text(index.read_text().replace('"ph":1,', ""))
        shutil.rmtree(repo / "portraits")
        cwd = os.getcwd()
        os.chdir(repo)
        self.addCleanup(os.chdir, cwd)
        code, out = run_quiet(self.serve(serve.GzipHandler))
        self.assertEqual(code, 1)
        self.assertIn("FAIL  the index flags portraits (ph)", out)


class SlugTests(unittest.TestCase):
    def test_matches_routes_js(self):
        # frontend/src/lib/routes.js nameSlug's own example.
        self.assertEqual(smoke.name_slug("Birutė VĖSAITĖ"), "birute-vesaite")
        self.assertEqual(smoke.person_path({"n": "", "pid": "p1"}), "/asmuo/p1")


if __name__ == "__main__":
    unittest.main()
