"""The terms a release ships under are stated once and agree everywhere (issue #138).

A published dataset of 60,725 named people had no LICENSE, no data terms, no
attribution requirement and no takedown contact — nothing in the repository
or the release notes said what a downstream user may do or whom to write to.
Now four facts (the code licence, the compilation licence, the attribution
string, the terms URL) live as constants in scripts/build_distribution.py,
ride inside every MANIFEST.json and close every release's notes, and
DATA_TERMS.md / LICENSE / README.md say the same thing in prose. These tests
hold the prose to the constants, so the repository cannot drift into saying
one thing while the assets say another.
"""

from __future__ import annotations

import importlib.util
import re
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

_spec = importlib.util.spec_from_file_location(
    "build_distribution", REPO_ROOT / "scripts" / "build_distribution.py"
)
dist_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(dist_mod)

LICENSE = (REPO_ROOT / "LICENSE").read_text(encoding="utf-8")
DATA_TERMS = (REPO_ROOT / "DATA_TERMS.md").read_text(encoding="utf-8")
README = (REPO_ROOT / "README.md").read_text(encoding="utf-8")


class CodeLicenseTests(unittest.TestCase):
    def test_the_code_is_mit_licensed(self):
        self.assertEqual(dist_mod.CODE_LICENSE, "MIT")
        self.assertTrue(LICENSE.startswith("MIT License"))
        self.assertIn("Permission is hereby granted, free of charge", LICENSE)

    def test_the_licence_file_points_at_the_data_terms(self):
        # The code licence does not cover the corpus; a reader of LICENSE
        # alone must be sent to the file that does.
        self.assertIn("DATA_TERMS.md", LICENSE)


class DataTermsTests(unittest.TestCase):
    def test_the_compilation_licence_is_named_in_prose_and_in_the_manifest_constant(self):
        self.assertEqual(dist_mod.DATA_LICENSE, "CC-BY-4.0")
        self.assertIn(dist_mod.DATA_LICENSE_NAME, DATA_TERMS)
        self.assertIn("creativecommons.org/licenses/by/4.0", DATA_TERMS)

    def test_the_attribution_string_in_the_terms_is_the_one_the_manifest_carries(self):
        # Quoted as a blockquote, wrapped over lines; compare with the
        # whitespace folded.
        quoted = re.search(r"^> (.*?)\n\n", DATA_TERMS, re.S | re.M).group(1)
        folded = " ".join(quoted.replace("\n> ", " ").split())
        self.assertEqual(folded, dist_mod.ATTRIBUTION)

    def test_the_terms_name_the_source_and_claim_nothing_over_it(self):
        self.assertIn("vrk.lt", DATA_TERMS)
        self.assertIn("claims no rights over VRK's content", DATA_TERMS)

    def test_the_terms_give_a_removal_contact(self):
        self.assertIn("https://github.com/Viespirkiu-grupe/vrk/issues", DATA_TERMS)
        self.assertRegex(DATA_TERMS, r"<[\w.+-]+@[\w.-]+>")
        self.assertIn("removed or corrected", DATA_TERMS)

    def test_the_terms_url_resolves_to_this_file(self):
        self.assertTrue(dist_mod.TERMS_URL.endswith("/DATA_TERMS.md"))

    def test_the_terms_point_at_the_personal_data_inventory(self):
        self.assertIn("docs/PERSONAL_DATA.md", DATA_TERMS)


class ReadmeTests(unittest.TestCase):
    def test_the_readme_links_both_files(self):
        self.assertIn("[LICENSE](LICENSE)", README)
        self.assertIn("[DATA_TERMS.md](DATA_TERMS.md)", README)
        self.assertIn(dist_mod.DATA_LICENSE_NAME, README)


class ReleaseNotesFooterTests(unittest.TestCase):
    def test_the_footer_carries_all_four_facts_and_the_release(self):
        footer = dist_mod.release_notes_footer("corpus-2026-09-08")
        for fact in (
            dist_mod.SOURCE_URL,
            dist_mod.CODE_LICENSE,
            dist_mod.DATA_LICENSE_NAME,
            dist_mod.TERMS_URL,
            dist_mod.ATTRIBUTION,
            "corpus-2026-09-08",
        ):
            with self.subTest(fact):
                self.assertIn(fact, footer)
        self.assertIn("removed or corrected", footer)


if __name__ == "__main__":
    unittest.main()
