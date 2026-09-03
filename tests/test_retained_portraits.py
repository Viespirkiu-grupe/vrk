"""Every retained portrait in the fixture trees is what its record says it is.

`scripts/backfill_url_portraits.py` leaves a `portrait.json` beside a
candidate's pages and, when the fetch succeeded, the `portrait.<ext>` it
names; `scraper/shared/files.py` reads the pair when it writes the record
(issue #118). The allowlists deliberately look past these files
(`local_data.page_names`), so this is where they are held to their contract:
a URL, a fetch time, and either bytes that hash to the recorded sha256 in the
container the record claims, or a recorded error and no bytes at all. On a
clone the tracked fixture subset carries the portraits of every unit under
the limit, so this runs on CI over hundreds of them.
"""

from __future__ import annotations

import hashlib
import json
import unittest
from pathlib import Path

from scraper.shared.files import IMAGE_EXTENSIONS, sniff_photo_type

REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURES_ROOT = REPO_ROOT / "samples" / "html"


def retained_portraits() -> list[Path]:
    if not FIXTURES_ROOT.is_dir():
        return []
    return sorted(FIXTURES_ROOT.glob("*/*/portrait.json"))


class RetainedPortraitTests(unittest.TestCase):
    def test_there_are_retained_portraits_to_check(self) -> None:
        # The tracked subset holds every URL-era fixture candidate's portrait;
        # zero here means the trees this test guards are absent, not clean.
        self.assertGreater(len(retained_portraits()), 100)

    def test_every_retained_portrait_matches_its_record(self) -> None:
        for meta_path in retained_portraits():
            candidate_dir = meta_path.parent
            with self.subTest(f"{candidate_dir.parent.name}/{candidate_dir.name}"):
                meta = json.loads(meta_path.read_text(encoding="utf-8"))
                self.assertTrue(meta["url"].startswith(("http://", "https://")), meta["url"])
                self.assertRegex(meta["fetchedAt"], r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\+00:00$")
                bytes_files = sorted(
                    p.name for p in candidate_dir.glob("portrait.*") if p.name != "portrait.json"
                )
                if "file" in meta:
                    self.assertEqual(bytes_files, [meta["file"]])
                    raw = (candidate_dir / meta["file"]).read_bytes()
                    self.assertEqual(hashlib.sha256(raw).hexdigest(), meta["sha256"])
                    self.assertEqual(len(raw), meta["bytes"])
                    extension, mime = sniff_photo_type(raw)
                    self.assertIn(extension, IMAGE_EXTENSIONS)
                    self.assertEqual((meta["file"], meta["mime"]), (f"portrait.{extension}", mime))
                else:
                    self.assertTrue(meta.get("error"), "a failed fetch records why")
                    self.assertEqual(bytes_files, [], "a failed fetch leaves no bytes behind")


if __name__ == "__main__":
    unittest.main()
