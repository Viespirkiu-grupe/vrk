"""scripts/deploy.sh end to end, on a temporary server root (issue #188).

Two reference servers (tests/site_server.py) stand in for deploy/Caddyfile's
two sites: one serves ROOT/current, the other ROOT/next, each following its
symlink per request as Caddy does. The script is then run for real: a
deploy, a second deploy, a rollback, and the failures that must leave
`current` where it was -- a checksum that does not match, and a release
that fails its smoke check.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import site_server  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[1]
DEPLOY = REPO_ROOT / "scripts" / "deploy.sh"

_spec = importlib.util.spec_from_file_location("build_site", REPO_ROOT / "scripts" / "build_site.py")
build_site = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(build_site)


@unittest.skipUnless(shutil.which("bash") and shutil.which("python3") and shutil.which("tar"), "needs bash, python3 and tar")
class DeployTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._tmp = tempfile.TemporaryDirectory()
        tmp = Path(cls._tmp.name)
        repo = site_server.make_repo(tmp / "repo")
        cls.dist = tmp / "dist"
        cls.tarballs = {}
        for day in ("2026-10-24", "2026-10-25"):
            site = tmp / f"site-{day}"
            build_site.build_site(repo, site, frontend="verify", index="reuse", portraits="reuse", jobs=1, corpus_tag=f"corpus-{day}")
            cls.tarballs[day] = cls.dist / f"vrk-site-{day}.tar.gz"
            build_site.write_tarball(site, cls.tarballs[day])
        # A release whose page lost its bundle: it must never go live.
        broken = tmp / "site-broken"
        shutil.copytree(tmp / "site-2026-10-25", broken)
        for path in (broken / "_astro").glob("index.abc.js*"):
            path.unlink()
        cls.tarballs["broken"] = cls.dist / "vrk-site-broken.tar.gz"
        build_site.write_tarball(broken, cls.tarballs["broken"])
        artifacts = {
            path.name: {"bytes": path.stat().st_size, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
            for path in cls.tarballs.values()
        }
        (cls.dist / "MANIFEST.json").write_text(json.dumps({"artifacts": artifacts}))

    @classmethod
    def tearDownClass(cls) -> None:
        cls._tmp.cleanup()

    def setUp(self) -> None:
        self._root = tempfile.TemporaryDirectory()
        self.addCleanup(self._root.cleanup)
        self.root = Path(self._root.name)
        live, self.url = site_server.start(self.root / "current")
        preview, self.preview_url = site_server.start(self.root / "next")
        for server in (live, preview):
            self.addCleanup(server.server_close)
            self.addCleanup(server.shutdown)

    def deploy(self, *args: str, env: dict | None = None) -> subprocess.CompletedProcess:
        env = {
            **os.environ,
            "VRK_ROOT": str(self.root),
            "VRK_URL": self.url,
            "VRK_PREVIEW_URL": self.preview_url,
            "VRK_RELOAD": "",
            **(env or {}),
        }
        return subprocess.run(["bash", str(DEPLOY), *args], capture_output=True, text=True, env=env, timeout=120)

    def link(self, name: str) -> str | None:
        path = self.root / name
        return os.readlink(path) if path.is_symlink() else None

    def live_corpus(self) -> str:
        return build_site.read_version(self.root / "current")["corpus"]

    def test_deploy_redeploy_rollback(self):
        first = self.deploy(str(self.tarballs["2026-10-24"]))
        self.assertEqual(first.returncode, 0, first.stdout + first.stderr)
        self.assertIn("sha256 verified", first.stdout)
        self.assertEqual(self.link("current"), "releases/vrk-site-2026-10-24")
        self.assertEqual(self.live_corpus(), "corpus-2026-10-24")
        self.assertIn("all checks passed against " + self.preview_url, first.stdout)
        self.assertIn("all checks passed against " + self.url, first.stdout)

        second = self.deploy(str(self.tarballs["2026-10-25"]))
        self.assertEqual(second.returncode, 0, second.stdout + second.stderr)
        self.assertEqual(self.link("current"), "releases/vrk-site-2026-10-25")
        self.assertEqual(self.link("previous"), "releases/vrk-site-2026-10-24")

        back = self.deploy("--rollback")
        self.assertEqual(back.returncode, 0, back.stdout + back.stderr)
        self.assertEqual(self.live_corpus(), "corpus-2026-10-24")
        self.assertEqual(self.link("previous"), "releases/vrk-site-2026-10-25")

        # Forward again: the release is still extracted and is reused.
        again = self.deploy(str(self.tarballs["2026-10-25"]))
        self.assertEqual(again.returncode, 0, again.stdout + again.stderr)
        self.assertIn("already extracted; reusing it", again.stdout)
        self.assertEqual(self.live_corpus(), "corpus-2026-10-25")

        status = self.deploy("--status")
        self.assertIn("current   releases/vrk-site-2026-10-25", status.stdout)

    def test_a_release_tag_is_downloaded_and_checked(self):
        # The release as GitHub lays it out: <base>/<tag>/<asset>, fetched
        # with curl from a file:// URL.
        releases = self.root.parent / f"{self.root.name}-github"
        tag_dir = releases / "corpus-2026-10-25"
        tag_dir.mkdir(parents=True)
        self.addCleanup(shutil.rmtree, releases, ignore_errors=True)
        asset = self.tarballs["2026-10-25"]
        shutil.copy(asset, tag_dir / asset.name)
        manifest = json.loads((self.dist / "MANIFEST.json").read_text())
        (tag_dir / "MANIFEST.json").write_text(json.dumps({"artifacts": {asset.name: manifest["artifacts"][asset.name]}}))
        result = self.deploy("corpus-2026-10-25", env={"VRK_DOWNLOAD": "curl", "VRK_RELEASE_BASE": releases.as_uri()})
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("downloading corpus-2026-10-25", result.stdout)
        self.assertEqual(self.link("current"), "releases/corpus-2026-10-25")
        self.assertFalse(list(self.root.glob(".download.*")), "the download directory is cleaned up")
        # A corrupted asset on the server is refused.
        (tag_dir / asset.name).write_bytes(asset.read_bytes()[:-1] + b"x")
        shutil.rmtree(self.root / "releases/corpus-2026-10-25")
        (self.root / "current").unlink()
        result = self.deploy("corpus-2026-10-25", env={"VRK_DOWNLOAD": "curl", "VRK_RELEASE_BASE": releases.as_uri()})
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("the manifest says", result.stderr)

    def test_a_checksum_mismatch_changes_nothing(self):
        self.assertEqual(self.deploy(str(self.tarballs["2026-10-24"])).returncode, 0)
        result = self.deploy(str(self.tarballs["2026-10-25"]), "--sha256", "0" * 64)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("sha256", result.stderr)
        self.assertEqual(self.link("current"), "releases/vrk-site-2026-10-24")
        self.assertFalse((self.root / "releases/vrk-site-2026-10-25").exists())

    def test_a_tarball_the_manifest_does_not_list_is_refused(self):
        other = self.root / "elsewhere" / "vrk-site-2026-10-24.tar.gz"
        other.parent.mkdir()
        shutil.copy(self.tarballs["2026-10-24"], other)
        result = self.deploy(str(other))
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("no MANIFEST.json", result.stderr)

    def test_a_release_that_fails_its_smoke_check_never_goes_live(self):
        self.assertEqual(self.deploy(str(self.tarballs["2026-10-24"])).returncode, 0)
        result = self.deploy(str(self.tarballs["broken"]))
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("FAIL  GET /_astro/index.abc.js -> 200", result.stdout)
        self.assertIn("current is unchanged", result.stderr)
        self.assertEqual(self.link("current"), "releases/vrk-site-2026-10-24")
        self.assertEqual(self.live_corpus(), "corpus-2026-10-24")

    def test_a_failing_reload_switches_back(self):
        self.assertEqual(self.deploy(str(self.tarballs["2026-10-24"])).returncode, 0)
        result = self.deploy(str(self.tarballs["2026-10-25"]), "--reload", "exit 3")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("the reload command failed: exit 3", result.stderr)
        self.assertIn("switched back to releases/vrk-site-2026-10-24", result.stderr)
        self.assertEqual(self.link("current"), "releases/vrk-site-2026-10-24")
        self.assertIsNone(self.link("previous"))

    def test_old_releases_are_pruned_but_never_a_linked_one(self):
        for day in ("2026-10-24", "2026-10-25"):
            self.assertEqual(self.deploy(str(self.tarballs[day]), "--keep", "1").returncode, 0)
        self.assertEqual(sorted(p.name for p in (self.root / "releases").iterdir()), ["vrk-site-2026-10-24", "vrk-site-2026-10-25"])

    def test_rollback_without_a_previous_release(self):
        result = self.deploy("--rollback")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("no previous release", result.stderr)


if __name__ == "__main__":
    unittest.main()
