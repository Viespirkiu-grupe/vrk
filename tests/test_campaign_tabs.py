"""Sub-tab derivation from campaign URLs (issue #99): both URL families, the
merge with the rendered tab list, the 404-means-unpublished classification,
and the refetch script that replays it over retained campaigns."""

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import requests

from scraper.shared.campaign_tabs import (
    CAMPAIGN_TABS,
    derive_subtab_links,
    is_absent_derived_tab,
    merge_campaign_tab_links,
)

MODERN_ROOT = "https://www.vrk.lt/statiniai/puslapiai/politKamp/1726/dalyviai/atstovaujamasis_pkdId-19700.html"
OLDER_ROOT = (
    "https://www.vrk.lt/statiniai/puslapiai/rinkimai/416_lt/"
    "PolitiniuKampanijuFinansavimas/Dalyvis6396/Dalyvio6396Izdininkas.html"
)


class DeriveSubtabLinksTests(unittest.TestCase):
    def test_modern_family_from_the_atstovaujamasis_root(self) -> None:
        links = derive_subtab_links(MODERN_ROOT)
        self.assertEqual(len(links), 5)
        self.assertEqual([tab["slug"] for tab in links], [t[1] for t in CAMPAIGN_TABS])
        # Even a represented participant's sub-pages live under the
        # `savarankiskas` stem — the retained pages' own tab lists say so.
        self.assertEqual(
            links[2]["url"],
            "https://www.vrk.lt/statiniai/puslapiai/politKamp/1726/dalyviai/"
            "savarankiskasAukotojai_pkdId-19700.html",
        )
        self.assertEqual(
            links[3]["url"],
            "https://www.vrk.lt/statiniai/puslapiai/politKamp/1726/dalyviai/"
            "savarankiskasFinansavimas_pkdId-19700.html",
        )
        self.assertTrue(all(tab["derived"] for tab in links))

    def test_modern_family_from_a_sub_tab_url_lands_on_the_same_five(self) -> None:
        donation_url = (
            "https://www.vrk.lt/statiniai/puslapiai/politKamp/1726/dalyviai/"
            "savarankiskasAukotojai_pkdId-19700.html"
        )
        self.assertEqual(derive_subtab_links(donation_url), derive_subtab_links(MODERN_ROOT))

    def test_older_family_uses_its_own_stems(self) -> None:
        links = derive_subtab_links(OLDER_ROOT)
        self.assertEqual(len(links), 5)
        by_slug = {tab["slug"]: tab["url"] for tab in links}
        prefix = (
            "https://www.vrk.lt/statiniai/puslapiai/rinkimai/416_lt/"
            "PolitiniuKampanijuFinansavimas/Dalyvis6396/Dalyvio6396"
        )
        self.assertEqual(by_slug["izdininkas"], f"{prefix}Izdininkas.html")
        # AukotojuSarasas and FinansavimoAtaskaitos, not the modern
        # Aukotojai/Finansavimas stems.
        self.assertEqual(by_slug["auku-ir-aukotoju-sarasas"], f"{prefix}AukotojuSarasas.html")
        self.assertEqual(by_slug["finansavimo-ataskaitos"], f"{prefix}FinansavimoAtaskaitos.html")
        self.assertEqual(by_slug["sutartys"], f"{prefix}Sutartys.html")

    def test_unknown_url_derives_nothing(self) -> None:
        self.assertEqual(
            derive_subtab_links("https://www.vrk.lt/statiniai/puslapiai/rinkimai/1104/kazkas.html"),
            [],
        )
        self.assertEqual(derive_subtab_links(""), [])


class MergeCampaignTabLinksTests(unittest.TestCase):
    def test_rendered_tabs_win_and_derived_fill_the_gaps(self) -> None:
        extracted = [
            {
                "label": "Aukų ir aukotojų sąrašas",
                "slug": "auku-ir-aukotoju-sarasas",
                "url": (
                    "https://www.vrk.lt/statiniai/puslapiai/politKamp/1726/dalyviai/"
                    "savarankiskasAukotojai_pkdId-19700.html"
                ),
            }
        ]
        merged = merge_campaign_tab_links(extracted, derive_subtab_links(MODERN_ROOT))
        self.assertEqual(len(merged), 5)
        self.assertIs(merged[0], extracted[0])
        self.assertNotIn("derived", merged[0])
        self.assertEqual(
            [tab["slug"] for tab in merged[1:]],
            ["izdininkas", "auditorius", "finansavimo-ataskaitos", "sutartys"],
        )

    def test_a_full_rendered_list_gains_nothing(self) -> None:
        derived = derive_subtab_links(MODERN_ROOT)
        extracted = [dict(tab, derived=False) for tab in derived]
        self.assertEqual(merge_campaign_tab_links(extracted, derived), extracted)


class AbsentDerivedTabTests(unittest.TestCase):
    @staticmethod
    def _http_error(status: int) -> requests.HTTPError:
        response = requests.Response()
        response.status_code = status
        return requests.HTTPError(response=response)

    def test_404_on_a_derived_tab_is_an_absence(self) -> None:
        self.assertTrue(is_absent_derived_tab({"derived": True}, self._http_error(404)))

    def test_404_on_a_rendered_tab_stays_an_error(self) -> None:
        self.assertFalse(is_absent_derived_tab({"slug": "sutartys"}, self._http_error(404)))

    def test_other_failures_stay_errors(self) -> None:
        self.assertFalse(is_absent_derived_tab({"derived": True}, self._http_error(500)))
        self.assertFalse(is_absent_derived_tab({"derived": True}, ConnectionError("boom")))


class RefetchScriptTests(unittest.TestCase):
    @staticmethod
    def _load_script():
        spec = importlib.util.spec_from_file_location(
            "refetch_campaign_subtabs",
            Path(__file__).resolve().parents[1] / "scripts" / "refetch_campaign_subtabs.py",
        )
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def _candidate(self, tmp: str) -> Path:
        candidate_dir = Path(tmp) / "cand"
        campaign_dir = candidate_dir / "campaigns" / "dalyvis-6396"
        campaign_dir.mkdir(parents=True)
        (campaign_dir / "root.html").write_text("<html>card</html>", encoding="utf-8")
        (campaign_dir / "index.json").write_text(
            json.dumps(
                {
                    "campaignKey": "dalyvis-6396",
                    "campaignUrl": OLDER_ROOT,
                    "tabCount": 0,
                    "tabSamples": [],
                    "campaignRootPath": str(campaign_dir / "root.html"),
                }
            ),
            encoding="utf-8",
        )
        (candidate_dir / "index.json").write_text(
            json.dumps(
                {
                    "campaignSamples": [
                        {
                            "campaignKey": "dalyvis-6396",
                            "campaignUrl": OLDER_ROOT,
                            "tabCount": 0,
                            "tabSamples": [],
                        }
                    ]
                }
            ),
            encoding="utf-8",
        )
        return candidate_dir

    def test_root_only_campaign_gains_its_five_tabs(self) -> None:
        module = self._load_script()
        with tempfile.TemporaryDirectory() as tmp:
            candidate_dir = self._candidate(tmp)
            meta = json.loads((candidate_dir / "index.json").read_text(encoding="utf-8"))
            campaign = meta["campaignSamples"][0]
            stats = module.ElectionStats()
            with mock.patch.object(module, "fetch_text", return_value="<html>tab</html>"), \
                 mock.patch.object(module.time, "sleep"):
                changed = module.refetch_campaign(
                    campaign, candidate_dir, stats, pause=0, dry_run=False
                )

            self.assertTrue(changed)
            # Iždininkas is the root itself: written from retained bytes, not fetched.
            self.assertEqual((stats.fetched, stats.reused), (4, 1))
            slugs = [tab["slug"] for tab in campaign["tabSamples"]]
            self.assertEqual(slugs, [t[1] for t in CAMPAIGN_TABS])
            campaign_dir = candidate_dir / "campaigns" / "dalyvis-6396"
            self.assertEqual(
                (campaign_dir / "izdininkas.html").read_text(encoding="utf-8"),
                "<html>card</html>",
            )
            self.assertTrue((campaign_dir / "finansavimo-ataskaitos.html").is_file())
            index = json.loads((campaign_dir / "index.json").read_text(encoding="utf-8"))
            self.assertEqual(len(index["tabSamples"]), 5)
            self.assertTrue(all(tab["derived"] for tab in index["tabSamples"]))

    def test_unpublished_sub_pages_are_recorded_not_fetched_as_tabs(self) -> None:
        module = self._load_script()
        response = requests.Response()
        response.status_code = 404
        with tempfile.TemporaryDirectory() as tmp:
            candidate_dir = self._candidate(tmp)
            meta = json.loads((candidate_dir / "index.json").read_text(encoding="utf-8"))
            campaign = meta["campaignSamples"][0]
            stats = module.ElectionStats()
            with mock.patch.object(
                module, "fetch_text", side_effect=requests.HTTPError(response=response)
            ), mock.patch.object(module.time, "sleep"):
                module.refetch_campaign(campaign, candidate_dir, stats, pause=0, dry_run=False)

            # The root-reuse still lands; the four network tabs are absences.
            self.assertEqual((stats.reused, stats.absent, stats.fetched), (1, 4, 0))
            index = json.loads(
                (candidate_dir / "campaigns" / "dalyvis-6396" / "index.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertEqual(
                index["derivedTabsAbsent"],
                sorted(["auditorius", "auku-ir-aukotoju-sarasas", "finansavimo-ataskaitos", "sutartys"]),
            )

    def test_complete_campaigns_are_left_alone(self) -> None:
        module = self._load_script()
        with tempfile.TemporaryDirectory() as tmp:
            candidate_dir = self._candidate(tmp)
            meta = json.loads((candidate_dir / "index.json").read_text(encoding="utf-8"))
            campaign = meta["campaignSamples"][0]
            campaign["tabSamples"] = [
                {"slug": tab["slug"], "url": tab["url"]}
                for tab in derive_subtab_links(OLDER_ROOT)
            ]
            stats = module.ElectionStats()
            with mock.patch.object(module, "fetch_text") as fetch:
                changed = module.refetch_campaign(
                    campaign, candidate_dir, stats, pause=0, dry_run=False
                )
            self.assertFalse(changed)
            self.assertEqual(stats.complete, 1)
            fetch.assert_not_called()


if __name__ == "__main__":
    unittest.main()
