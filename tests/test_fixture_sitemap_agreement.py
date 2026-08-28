"""A fixture's `index.json` must say what the sitemap says.

`fetch-candidate-samples` copies the sitemap entry into the candidate's
`index.json` verbatim, and the municipal parsers read the party list, roles
and municipality back out of it — so a fixture captured against an older
sitemap parses to a record the corpus does not contain, and the re-parse gate
(`scripts/reparse_diff.py`) reports drift that is in the fixture rather than
in `data/`.

That is not hypothetical: two 2023 municipal fixtures carried the Akmenė
group-header list number 25 against the sitemap's 5, and the gate blamed the
corpus for it (issue #91).

Only the fixture tree is checked here. `samples-full/` is covered by
`reparse_diff --full`, which parses every retained candidate.
"""

import json
import unittest
from pathlib import Path

from local_data import require


REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURES_ROOT = REPO_ROOT / "samples" / "html"
SITEMAPS_ROOT = REPO_ROOT / "sitemaps"


class FixtureSitemapAgreementTests(unittest.TestCase):
    def test_every_fixture_index_matches_its_sitemap_entry(self) -> None:
        require(SITEMAPS_ROOT)
        checked = 0
        mismatches: list[str] = []
        missing: list[str] = []

        for election_dir in sorted(p for p in FIXTURES_ROOT.iterdir() if p.is_dir()):
            sitemap_path = SITEMAPS_ROOT / f"{election_dir.name}.json"
            if not sitemap_path.exists():
                continue
            entries = {
                entry["candidateId"]: entry
                for entry in json.loads(sitemap_path.read_text(encoding="utf-8"))["entries"]
            }
            for index_path in sorted(election_dir.glob("*/index.json")):
                candidate = json.loads(index_path.read_text(encoding="utf-8")).get("candidate")
                if not isinstance(candidate, dict):
                    continue
                checked += 1
                entry = entries.get(candidate.get("candidateId"))
                if entry is None:
                    missing.append(f"{election_dir.name}/{index_path.parent.name}")
                elif entry != candidate:
                    differing = sorted(
                        key
                        for key in set(entry) | set(candidate)
                        if entry.get(key) != candidate.get(key)
                    )
                    mismatches.append(
                        f"{election_dir.name}/{index_path.parent.name}: {', '.join(differing)}"
                    )

        self.assertGreater(checked, 0, "no fixture index.json found — is samples/ present?")
        self.assertEqual(
            missing, [], "fixture candidate(s) absent from the sitemap; rebuild the sitemap"
        )
        self.assertEqual(
            mismatches,
            [],
            "fixture index.json disagrees with the sitemap; re-fetch the candidate "
            "(python -m scraper fetch-candidate-samples <id> --candidate-id <cid>)",
        )


if __name__ == "__main__":
    unittest.main()
