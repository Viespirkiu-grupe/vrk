"""The site tarball in the release (issue #188): build_distribution.py --site.

A full distribution build needs all 55 registered elections, so the pieces
`--site` adds are tested one by one: the check that the site was built for
this release, the asset list the manifest checksums, promotion's stale-file
rule, and the refusal of a subset build.
"""

from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import site_server  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

_spec = importlib.util.spec_from_file_location("build_distribution", REPO_ROOT / "scripts" / "build_distribution.py")
dist_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(dist_mod)


class SiteReleaseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._tmp = tempfile.TemporaryDirectory()
        tmp = Path(cls._tmp.name)
        cls.site = tmp / "site"
        dist_mod.build_site.build_site(
            site_server.make_repo(tmp / "repo"), cls.site,
            frontend="verify", index="reuse", portraits="reuse", jobs=1, corpus_tag="corpus-2026-10-25",
        )
        cls.tmp = tmp

    @classmethod
    def tearDownClass(cls) -> None:
        cls._tmp.cleanup()

    def check(self, **overrides):
        arguments = {"version": "corpus-2026-10-25", "profile": "public", "records": 2, "portraits_version": site_server.PORTRAIT_VERSION, **overrides}
        return dist_mod.check_site(self.site, **arguments)

    def test_a_site_built_for_this_release_passes(self):
        self.assertEqual(self.check()["corpus"], "corpus-2026-10-25")

    def test_a_site_built_for_anything_else_is_refused(self):
        for overrides, named in (
            ({"version": "corpus-2026-10-26"}, "corpus"),
            ({"profile": "full"}, "profile"),
            ({"records": 113073}, "records"),
            ({"portraits_version": "ffffffff"}, "portraits_version"),
        ):
            with self.subTest(named), self.assertRaises(SystemExit) as caught:
                self.check(**overrides)
            self.assertIn(f"    {named}: the site says", str(caught.exception))
            self.assertIn("python scripts/build_site.py --out", str(caught.exception))

    def test_a_directory_without_version_is_refused(self):
        with self.assertRaises(SystemExit) as caught:
            dist_mod.check_site(self.tmp, "corpus-2026-10-25", "public", 2, "x")
        self.assertIn("has no VERSION", str(caught.exception))

    def test_the_asset_is_listed_for_the_manifest(self):
        counts = {"photo_parts": [], "web_portraits": {"count": 1}, "site": {"asset": "vrk-site-2026-10-25.tar.zst"}}
        assets = dist_mod.release_assets(counts)
        self.assertEqual(assets[-2:], ("vrk-web-portraits.tar", "vrk-site-2026-10-25.tar.zst"))
        self.assertNotIn("vrk-site-2026-10-25.tar.zst", dist_mod.release_assets({"photo_parts": []}))
        self.assertEqual(dist_mod.SITE_ASSET.format(date="2026-10-25"), "vrk-site-2026-10-25.tar.zst")

    def test_promote_drops_a_site_tarball_from_another_build(self):
        staging = self.tmp / "staging"
        dist = self.tmp / "dist"
        for directory in (staging, dist):
            directory.mkdir(exist_ok=True)
        for name in dist_mod.BUILD_OUTPUTS + ("MANIFEST.json", "vrk-site-2026-10-25.tar.zst"):
            (staging / name).write_text(name)
        (dist / "vrk-site-2026-10-24.tar.zst").write_text("yesterday")
        dist_mod.promote(staging, dist)
        self.assertTrue((dist / "vrk-site-2026-10-25.tar.zst").is_file())
        self.assertFalse((dist / "vrk-site-2026-10-24.tar.zst").exists())

    def test_a_subset_build_cannot_ship_a_site(self):
        with self.assertRaises(SystemExit) as caught:
            dist_mod.build_distribution(self.tmp, self.tmp / "dist", ["2019-prezidento"], site=self.site)
        self.assertIn("a subset build does not describe", str(caught.exception))


if __name__ == "__main__":
    unittest.main()
