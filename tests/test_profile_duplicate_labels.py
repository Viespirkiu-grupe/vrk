"""A profile-card label that recurs must not overwrite its first value.

Measured over all 40,469 records on 2026-08-21: exactly one existing record
had a recurring label — Marija Puč (2015 Trakai), whose card names the
coalition that nominated her and then, in parentheses, the member party. The
overwrite kept the parenthetical and labelled it "(Iškėlė". The 2012 Seimo
cards make the same thing routine: an "Apygarda"/"Iškėlė" pair per
candidacy, single-member first, multi-member second.
"""

import json
import tempfile
import unittest
from pathlib import Path

from scraper.elections.pakartotiniai_sirvintu_traku_2015.anketa_parser import parse_anketa_sample
from scraper.shared.anketa_tabs import normalize_profile_data


REPO_ROOT = Path(__file__).resolve().parents[1]
SIRVINTOS_TRAKAI_SAMPLES = (
    REPO_ROOT / "samples" / "html" / "2015-birzelio-7-pakartotiniai-sirvintos-trakai"
)


class ProfileDuplicateLabelTests(unittest.TestCase):
    def test_first_occurrence_keeps_the_plain_key(self) -> None:
        profile = {
            "candidateDisplayName": "X",
            "electedNote": "",
            "photoSrc": "",
            "fields": [
                {"key": "Apygarda", "displayValue": "Vilkaviškio (Nr.68)", "urls": []},
                {"key": "Iškėlė", "displayValue": "A", "urls": []},
                {"key": "Apygarda", "displayValue": "Daugiamandatė", "urls": []},
                {"key": "Iškėlė", "displayValue": "B", "urls": ["https://example.test/b"]},
                {"key": "Iškėlė", "displayValue": "C", "urls": []},
            ],
        }
        kita = normalize_profile_data(profile)["kita"]
        self.assertEqual(
            list(kita.keys()), ["apygarda", "iskele", "apygarda-2", "iskele-2", "iskele-3"]
        )
        self.assertEqual(kita["apygarda"]["reiksme"], "Vilkaviškio (Nr.68)")
        self.assertEqual(kita["iskele"]["reiksme"], "A")
        self.assertEqual(kita["apygarda-2"]["reiksme"], "Daugiamandatė")
        self.assertEqual(kita["iskele-2"]["reiksme"], "B")
        self.assertEqual(kita["iskele-2"]["nuorodos"], ["https://example.test/b"])
        self.assertEqual(kita["iskele-3"]["reiksme"], "C")

    def test_marija_puc_keeps_the_coalition_as_nominator(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output_path, _ = parse_anketa_sample(
                candidate_id="marija-puc-2",
                samples_root=SIRVINTOS_TRAKAI_SAMPLES,
                output_root=Path(tmp),
            )
            record = json.loads(output_path.read_text(encoding="utf-8"))

        kita = record["normalized"]["profilis"]["kita"]
        self.assertEqual(kita["iskele"]["pavadinimas"], "Iškėlė")
        self.assertEqual(
            kita["iskele"]["reiksme"],
            "Lenkų rinkimų akcijos ir Rusų aljanso koalicija „Valdemaro Tomaševskio blokas“",
        )
        self.assertEqual(kita["iskele-2"]["pavadinimas"], "(Iškėlė")
        self.assertEqual(kita["iskele-2"]["reiksme"], "Lietuvos lenkų rinkimų akcija")
        self.assertEqual(kita["numeris-sarase"]["reiksme"], "1")
        self.assertEqual(kita["numeris-sarase-2"]["reiksme"], "1")
        # The listing-derived block already named the coalition; the two now agree.
        self.assertEqual(
            record["kandidatavimas"]["tarybosNarys"]["partyList"], kita["iskele"]["reiksme"]
        )


if __name__ == "__main__":
    unittest.main()
