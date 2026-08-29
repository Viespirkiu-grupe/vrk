"""The office line above the profile card (issue #100 item 5).

Every 2017-2025 page opens with one <h4 class="h4apgKom"> naming the office
sought — "Kandidatas į savivaldybės tarybos narius ir merus" — and on the
2024 Seimo pages each candidate's own document-submission date. Neither used
to reach the record, not even rawData.
"""

import json
import tempfile
import unittest
from pathlib import Path

from scraper.elections.savivaldybiu_2023.anketa_parser import (
    parse_anketa_sample as parse_savivaldybiu_2023_sample,
)
from scraper.elections.seimo_2016.anketa_parser import (
    parse_anketa_sample as parse_seimo_2016_sample,
)
from scraper.elections.seimo_2024.anketa_parser import (
    parse_anketa_sample as parse_seimo_2024_sample,
)


def _parse(parse, candidate_id: str) -> dict:
    with tempfile.TemporaryDirectory() as tmp:
        output_path, _ = parse(candidate_id, output_root=Path(tmp))
        return json.loads(output_path.read_text(encoding="utf-8"))


class OfficeHeadingTests(unittest.TestCase):
    def test_2024_seimo_office_and_submission_date(self) -> None:
        record = _parse(parse_seimo_2024_sample, "algirdas-butkevicius")
        self.assertEqual(
            record["rawData"]["profile"]["officeHeading"],
            "Kandidatas į Seimo narius (dokumentai pateikti 2024-07-16)",
        )
        profilis = record["normalized"]["profilis"]
        self.assertEqual(profilis["kandidatuoja-i"], "Kandidatas į Seimo narius")
        self.assertEqual(profilis["dokumentu-pateikimo-data"], "2024-07-16")

    def test_2023_municipal_office_distinguishes_the_roles(self) -> None:
        record = _parse(parse_savivaldybiu_2023_sample, "algirdas-zebrauskas-2424292")
        profilis = record["normalized"]["profilis"]
        self.assertEqual(profilis["kandidatuoja-i"], "Kandidatas į savivaldybės tarybos narius ir merus")
        self.assertIsNone(profilis["dokumentu-pateikimo-data"])

    def test_2016_page_has_no_heading_and_no_new_keys(self) -> None:
        record = _parse(parse_seimo_2016_sample, "algirdas-butkevicius")
        self.assertNotIn("officeHeading", record["rawData"]["profile"])
        self.assertNotIn("kandidatuoja-i", record["normalized"]["profilis"])
        self.assertNotIn("dokumentu-pateikimo-data", record["normalized"]["profilis"])


if __name__ == "__main__":
    unittest.main()
