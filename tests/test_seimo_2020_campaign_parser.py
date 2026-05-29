import json
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
CANDIDATE_PATH = REPO_ROOT / "data" / "2020-seimo" / "giedrius-drukteinis-2020-seimo.json"


class Seimo2020CampaignParserTests(unittest.TestCase):
    def setUp(self) -> None:
        self.payload = json.loads(CANDIDATE_PATH.read_text(encoding="utf-8"))

    def test_raw_campaign_structure_is_simplified(self) -> None:
        raw_campaigns = self.payload["rawData"]["politinesKampanijosDalyvioDuomenys"]["campaigns"]
        self.assertEqual(len(raw_campaigns), 1)

        campaign = raw_campaigns[0]
        self.assertNotIn("tabs", campaign)
        self.assertNotIn("availableTabs", campaign)

        self.assertIn("participant", campaign)
        self.assertIn("treasurer", campaign)
        self.assertIn("auditor", campaign)
        self.assertNotIn("auditoriausAtaskaita", campaign)

        self.assertIn("aukuIrAukotojuSarasas", campaign)
        self.assertIn("finansavimoAtaskaitos", campaign)
        self.assertIn("sutartys", campaign)
        self.assertIn("sprendimai", campaign)

        auditor_report = campaign["auditor"]["auditoriausAtaskaita"]
        self.assertIsInstance(auditor_report, list)
        self.assertEqual(len(auditor_report), 2)
        self.assertTrue(auditor_report[0]["urls"])

    def test_normalized_campaign_data_is_still_populated(self) -> None:
        normalized_campaigns = self.payload["normalized"]["politines-kampanijos-dalyvio-duomenys"]
        self.assertEqual(len(normalized_campaigns), 1)

        campaign = normalized_campaigns[0]
        self.assertEqual(campaign["statusas"], "Savarankiškas")
        self.assertIn("aukos-pagal-sekcija", campaign)
        self.assertIn("finansavimo-ataskaitos", campaign)
        self.assertIn("sutartys", campaign)


if __name__ == "__main__":
    unittest.main()
