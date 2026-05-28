import json
import tempfile
import unittest
from pathlib import Path

from scraper.elections.seimo_2016.anketa_parser import parse_anketa_sample


REPO_ROOT = Path(__file__).resolve().parents[1]
SAMPLES_ROOT = REPO_ROOT / "samples" / "html" / "2016-seimo"


class Seimo2016CampaignParserTests(unittest.TestCase):
    def _parse_candidate(self, candidate_id: str) -> dict:
        with tempfile.TemporaryDirectory() as tmp_dir:
            output_root = Path(tmp_dir)
            output_path, _ = parse_anketa_sample(
                candidate_id=candidate_id,
                samples_root=SAMPLES_ROOT,
                output_root=output_root,
            )
            return json.loads(output_path.read_text(encoding="utf-8"))

    def test_gabrielius_campaign_data_is_reshaped_and_normalized(self) -> None:
        payload = self._parse_candidate("gabrielius-landsbergis")

        raw_campaigns = payload["rawData"]["politinesKampanijosDalyvioDuomenys"]["campaigns"]
        self.assertEqual(len(raw_campaigns), 1)

        campaign = raw_campaigns[0]
        self.assertEqual(campaign["participant"]["registeredDate"], "2016-05-06")
        self.assertEqual(campaign["participant"]["decisionNumber"], "PK2-2016LRS-S160")
        self.assertEqual(campaign["treasurer"]["name"], "ROLANDAS ŠEGŽDA")
        self.assertEqual(campaign["auditor"]["companyCode"], "125515863")
        self.assertEqual(
            [tab["slug"] for tab in campaign["tabs"]],
            [
                "izdininkas",
                "auditorius",
                "auku-ir-aukotoju-sarasas",
                "finansavimo-ataskaitos",
                "sutartys",
            ],
        )

        donations_data = next(tab for tab in campaign["tabs"] if tab["slug"] == "auku-ir-aukotoju-sarasas")["data"]
        received_section = next(
            section for section in donations_data["sections"] if section["title"] == "Gautos ir priimtos aukos"
        )
        self.assertEqual(len(received_section["records"]), 8)
        self.assertEqual(received_section["records"][0]["incomeSourceCode"], "PL")
        self.assertEqual(received_section["totals"]["is-viso"], 20052.31)
        self.assertEqual(received_section["totals"]["kandidato-nuosavos-lesos"], 5987.0)

        financing_data = next(tab for tab in campaign["tabs"] if tab["slug"] == "finansavimo-ataskaitos")["data"]
        self.assertEqual(len(financing_data["reports"]), 2)
        self.assertEqual(len(financing_data["reports"][0]["reportUrls"]), 1)
        self.assertEqual(len(financing_data["publisherInfoUrls"]), 1)

        contracts_data = next(tab for tab in campaign["tabs"] if tab["slug"] == "sutartys")["data"]
        self.assertEqual(len(contracts_data["contracts"]), 4)

        normalized_campaign = payload["normalized"]["politinesKampanijosDalyvioDuomenys"]["campaigns"][0]
        self.assertEqual(normalized_campaign["status"], "Savarankiškas")
        self.assertEqual(normalized_campaign["contact"]["email"], "neskelbtina")
        self.assertEqual(normalized_campaign["donations"]["gautos-ir-priimtos-aukos"]["totals"]["is-viso"], 20052.31)
        self.assertEqual(len(normalized_campaign["contracts"]), 4)

    def test_regina_has_no_campaign_section(self) -> None:
        payload = self._parse_candidate("regina-ablom")

        self.assertNotIn("politinesKampanijosDalyvioDuomenys", payload["rawData"])
        self.assertNotIn("politinesKampanijosDalyvioDuomenys", payload["normalized"])


if __name__ == "__main__":
    unittest.main()