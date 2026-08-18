import unittest

from scraper.elections.seimo_2016.candidate_samples import _extract_campaign_root_links


class Seimo2016CandidateSamplesTests(unittest.TestCase):
    def test_campaign_root_links_use_only_direct_campaign_url(self) -> None:
        direct_url = (
            "https://www.vrk.lt/statiniai/puslapiai/politKamp/686/dalyviai/"
            "atstovaujamasis_pkdId-1123.html"
        )

        links = _extract_campaign_root_links(direct_url)

        self.assertEqual(
            links,
            [
                {
                    "label": "",
                    "url": direct_url,
                    "campaignKey": "atstovaujamasis-pkdid-1123",
                }
            ],
        )


if __name__ == "__main__":
    unittest.main()
