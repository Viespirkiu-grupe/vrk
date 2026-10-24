"""scripts/build_site.py on a synthetic corpus (issue #188).

The site directory is what production serves file for file, so what is
asserted is its layout: what is in it, what is not (source HTML, anomalies,
full-size photos, anything of the repository), what the records look like
after the public profile, and what VERSION says.
"""

from __future__ import annotations

import importlib.util
import json
import os
import stat
import subprocess
import sys
import tarfile
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import site_server  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts"))
_spec = importlib.util.spec_from_file_location("build_site", REPO_ROOT / "scripts" / "build_site.py")
build_site = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(build_site)


def build(repo: Path, out: Path, **options) -> dict:
    options = {"frontend": "verify", "index": "reuse", "portraits": "reuse", "jobs": 1, **options}
    return build_site.build_site(repo, out, **options)


class LayoutTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._tmp = tempfile.TemporaryDirectory()
        cls.repo = site_server.make_repo(Path(cls._tmp.name) / "repo")
        cls.site = Path(cls._tmp.name) / "site"
        cls.fields = build(cls.repo, cls.site, corpus_tag="corpus-2026-10-25")
        cls.files = sorted(p.relative_to(cls.site).as_posix() for p in cls.site.rglob("*") if p.is_file())

    @classmethod
    def tearDownClass(cls) -> None:
        cls._tmp.cleanup()

    def test_the_layout_is_the_url_layout(self):
        # Every file is served at its own path: the build at the root, the
        # index beside it, the records, portraits and concept map at theirs.
        for name in (
            "index.html",
            "_astro/index.abc.js",
            "_astro/index.abc.css",
            "branding/icon.svg",
            "people.json",
            "field-labels.json",
            "docs/concept-map.json",
            "data/2019-prezidento/vardenis-pavardenis-2019-prezidento.json",
            "data/2020-seimo/vardenis-pavardenis-2020-seimo.json",
            f"portraits/{site_server.PID}.webp",
            "VERSION",
        ):
            self.assertIn(name, self.files)

    def test_nothing_but_the_records_comes_from_data(self):
        data = [name for name in self.files if name.startswith("data/")]
        self.assertEqual(len(data), 2)
        self.assertTrue(all(name.endswith(".json") for name in data))
        for absent in ("anomalies.jsonl", "photos/", "notes.txt"):
            self.assertFalse([name for name in self.files if absent in name], absent)
        self.assertFalse([name for name in data if name.endswith(".html")])

    def test_nothing_of_the_repository_comes_along(self):
        for prefix in ("dashboard/", "frontend/", "scripts/", "scraper/", "portraits/manifest.json", "docs/DASHBOARD"):
            self.assertFalse([name for name in self.files if name.startswith(prefix)], prefix)
        self.assertFalse([name for name in self.files if name.split("/")[-1].startswith(".")])

    def test_records_are_compact_and_redacted(self):
        path = self.site / "data/2019-prezidento/vardenis-pavardenis-2019-prezidento.json"
        body = path.read_text(encoding="utf-8")
        self.assertNotIn("\n", body)
        self.assertNotIn(site_server.TREASURER_PHONE, body)
        self.assertNotIn("izd@example.lt", body)
        record = json.loads(body)
        treasurer = record["rawData"]["politinesKampanijosDalyvioDuomenys"]["campaigns"][0]["treasurer"]
        self.assertEqual(treasurer, {"name": "Iždininkė"})
        # Non-ASCII stays as it is: smaller, and what the source files hold.
        self.assertIn("Iždininkė", body)

    def test_outputs_keep_their_sources_mtime(self):
        # Last-Modified is the file's mtime, so an unchanged record must keep
        # answering 304 after a redeploy.
        source = self.repo / "data/2019-prezidento/vardenis-pavardenis-2019-prezidento.json"
        target = self.site / "data/2019-prezidento/vardenis-pavardenis-2019-prezidento.json"
        self.assertEqual(int(source.stat().st_mtime), int(target.stat().st_mtime))
        index = self.site / "people.json"
        self.assertEqual(int((self.repo / "dashboard/people.json").stat().st_mtime), int(index.stat().st_mtime))

    def test_precompressed_copies_beside_the_always_fetched_files(self):
        for name in ("index.html", "people.json", "_astro/index.abc.js", "_astro/index.abc.css"):
            self.assertIn(name + ".gz", self.files)
            self.assertEqual(int((self.site / name).stat().st_mtime), int((self.site / (name + ".gz")).stat().st_mtime))
        # Records are compressed by the server, and tiny files not at all.
        self.assertFalse([name for name in self.files if name.startswith("data/") and name.endswith(".gz")])
        self.assertNotIn("docs/concept-map.json.gz", self.files)

    def test_version_says_what_this_is(self):
        fields = build_site.read_version(self.site)
        for key in ("commit", "dirty", "corpus", "built", "profile", "records", "people", "portraits", "portraits_version", "files", "bytes"):
            self.assertIn(key, fields)
        self.assertEqual(fields["corpus"], "corpus-2026-10-25")
        self.assertIn(fields["dirty"], ("true", "false"))
        self.assertRegex(fields["built"], r"^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ$")
        self.assertEqual(fields["profile"], "public")
        self.assertEqual(fields["records"], "2")
        self.assertEqual(fields["portraits_version"], site_server.PORTRAIT_VERSION)
        self.assertEqual(fields["redacted_values"], "4")
        self.assertEqual(int(fields["files"]), len(self.files) - 1)


class OptionTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)
        self.repo = site_server.make_repo(self.root / "repo")

    def test_full_profile_and_no_minify_keep_the_record(self):
        build(self.repo, self.root / "site", profile="full", minify=False, compress=False)
        source = self.repo / "data/2020-seimo/vardenis-pavardenis-2020-seimo.json"
        target = self.root / "site/data/2020-seimo/vardenis-pavardenis-2020-seimo.json"
        self.assertEqual(source.read_bytes(), target.read_bytes())
        self.assertFalse(list((self.root / "site").rglob("*.gz")))

    def test_a_failed_build_leaves_the_previous_site(self):
        build(self.repo, self.root / "site")
        before = (self.root / "site/VERSION").read_text()
        (self.repo / "data/2020-seimo/broken.json").write_text("{not json")
        with self.assertRaises(SystemExit) as caught:
            build(self.repo, self.root / "site")
        self.assertIn("broken.json", str(caught.exception))
        self.assertEqual((self.root / "site/VERSION").read_text(), before)
        self.assertFalse([p for p in self.root.iterdir() if p.name.startswith(".site.")])

    def test_a_json_file_that_is_not_a_record_is_refused(self):
        (self.repo / "data/2020-seimo/summary.json").write_text('{"total": 1}')
        with self.assertRaises(SystemExit) as caught:
            build(self.repo, self.root / "site")
        self.assertIn("not a candidate record", str(caught.exception))

    def test_portrait_version_must_match_the_index(self):
        manifest = self.repo / "portraits/manifest.json"
        manifest.write_text(json.dumps({**json.loads(manifest.read_text()), "version": "other"}))
        with self.assertRaises(SystemExit) as caught:
            build(self.repo, self.root / "site")
        self.assertIn("build_web_portraits.py after the index", str(caught.exception))

    def test_a_missing_or_stale_frontend_build_is_refused(self):
        # #183: the page is a build output; a site without it is a 404 site.
        os.utime(self.repo / "frontend/src/pages/index.astro")
        with self.assertRaises(SystemExit) as caught:
            build(self.repo, self.root / "site")
        self.assertIn("older than frontend/src/pages/index.astro", str(caught.exception))
        (self.repo / "frontend/dist/index.html").unlink()
        with self.assertRaises(SystemExit) as caught:
            build(self.repo, self.root / "site")
        self.assertIn("#183", str(caught.exception))

    def test_node_below_engines_is_refused_before_npm_runs(self):
        fake = self.root / "node"
        fake.write_text("#!/bin/sh\necho v20.11.0\n")
        fake.chmod(fake.stat().st_mode | stat.S_IEXEC)
        with self.assertRaises(SystemExit) as caught:
            build_site.check_node(self.repo / "frontend", str(fake))
        self.assertIn("older than the frontend needs (>= 22.12.0", str(caught.exception))
        fake.write_text("#!/bin/sh\necho v22.12.0\n")
        self.assertEqual(build_site.check_node(self.repo / "frontend", str(fake)), "v22.12.0")

    def test_the_stale_index_is_detected(self):
        records = build_site.record_paths(self.repo / "data")
        self.assertIsNone(build_site.index_is_stale(self.repo, records))
        os.utime(records[0])
        self.assertIn("is newer than it", build_site.index_is_stale(self.repo, records))

    def test_out_may_not_be_a_source_directory(self):
        with self.assertRaises(SystemExit):
            build(self.repo, self.repo / "data")


class TarballTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._tmp = tempfile.TemporaryDirectory()
        root = Path(cls._tmp.name)
        cls.site = root / "site"
        build(site_server.make_repo(root / "repo"), cls.site)
        cls.root = root

    @classmethod
    def tearDownClass(cls) -> None:
        cls._tmp.cleanup()

    def check(self, tarball: Path, mode: str) -> None:
        packed = build_site.write_tarball(self.site, tarball)
        self.assertEqual(packed["bytes"], tarball.stat().st_size)
        self.assertEqual(len(packed["sha256"]), 64)
        if mode == "zst":
            raw = subprocess.run(["zstd", "-dc", str(tarball)], capture_output=True, check=True).stdout
            tar = tarfile.open(fileobj=__import__("io").BytesIO(raw))
        else:
            tar = tarfile.open(tarball)
        with tar:
            members = {m.name: m for m in tar.getmembers()}
        # Entries are the URL paths themselves: extracted into a release
        # directory, it is the site.
        self.assertIn("index.html", members)
        self.assertIn("VERSION", members)
        self.assertFalse([name for name in members if name.startswith(("/", "./", "site/"))])
        expected = sorted(p.relative_to(self.site).as_posix() for p in self.site.rglob("*") if p.is_file())
        self.assertEqual(sorted(members), expected)
        member = members["data/2020-seimo/vardenis-pavardenis-2020-seimo.json"]
        self.assertEqual((member.uid, member.gid, member.mode), (0, 0, 0o644))
        self.assertEqual(member.mtime, int((self.site / member.name).stat().st_mtime))

    def test_tar_gz(self):
        self.check(self.root / "out" / "vrk-site-2026-10-25.tar.gz", "gz")

    @unittest.skipUnless(build_site.shutil.which("zstd"), "zstd is not installed")
    def test_tar_zst(self):
        self.check(self.root / "out" / "vrk-site-2026-10-25.tar.zst", "zst")

    def test_other_suffixes_are_refused(self):
        with self.assertRaises(SystemExit):
            build_site.write_tarball(self.site, self.root / "out" / "site.zip")


if __name__ == "__main__":
    unittest.main()
