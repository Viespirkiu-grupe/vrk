import json
import tempfile
import unittest
from pathlib import Path

from scraper.elections.ep_2009.anketa_parser import (
    DEFAULT_RESULTS_PATH,
    normalize_ep_anketa_rows,
    parse_anketa_sample,
)
from scraper.elections.ep_2009.candidate_samples import EXPECTED_TABS
from scraper.elections.ep_2009.results import MEMBERS_PAGE, RESULTS_TREE
from scraper.elections.ep_2009.sitemap import (
    ELECTION_ID,
    LISTING_URL,
    build_sitemap_from_sample,
)
from scraper.elections.seimo_birzu_zarasu_ukmerges_2013.anketa_parser import (
    normalize_seimo_2012_anketa_rows,
)

from local_data import require


REPO_ROOT = Path(__file__).resolve().parents[1]
SAMPLES_ROOT = REPO_ROOT / "samples" / "html" / ELECTION_ID
SITEMAPS = REPO_ROOT / "sitemaps"


def _parse(candidate_id: str) -> tuple[dict, dict]:
    with tempfile.TemporaryDirectory() as tmp:
        output_path, stats = parse_anketa_sample(
            candidate_id=candidate_id,
            samples_root=SAMPLES_ROOT,
            output_root=Path(tmp),
        )
        return json.loads(output_path.read_text(encoding="utf-8")), stats


class Ep2009SitemapTests(unittest.TestCase):
    def test_index_and_lists_reconcile(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            _, stats = build_sitemap_from_sample(
                sample_path=SAMPLES_ROOT,
                output_path=Path(tmp) / "sitemap.json",
            )
            payload = json.loads((Path(tmp) / "sitemap.json").read_text(encoding="utf-8"))

        self.assertEqual(stats["lists"], 15)
        self.assertEqual(stats["declared_candidates"], 262)
        self.assertEqual(stats["extracted"], 262)
        self.assertEqual(stats["list_count_mismatches"], 0)
        self.assertEqual(stats["skipped"], 0)
        self.assertEqual(stats["duplicate_candidate_ids"], 0)
        self.assertEqual(payload["electionId"], "2009-ep")
        self.assertEqual(payload["sourceUrl"], LISTING_URL)
        self.assertEqual(len(payload["listUrls"]), 15)
        by_id = {entry["candidateId"]: entry for entry in payload["entries"]}
        self.assertEqual(
            by_id["vytautas-landsbergis"],
            {
                "candidateName": "Vytautas LANDSBERGIS",
                "candidateId": "vytautas-landsbergis",
                "url": "https://www.vrk.lt/statiniai/puslapiai/rinkimai/404_lt"
                "/Kandidatai/Kandidatas25370/Kandidato25370Anketa.html",
                "vrkCandidateId": "25370",
                "roles": ["daugiamandate"],
                "daugiamandateCandidacy": {
                    "sarasas": "Tėvynės sąjunga - Lietuvos krikščionys demokratai",
                    "sarasoNumeris": 11,
                    "sarasoId": "3565",
                    "numerisSarase": 1,
                },
            },
        )
        leaders = [entry for entry in payload["entries"] if entry["daugiamandateCandidacy"]["numerisSarase"] == 1]
        self.assertEqual(len(leaders), 15)


class Ep2009ResultsTests(unittest.TestCase):
    def test_members_page_resolves_all_twelve(self) -> None:
        # The 2009 tree files the elected-members page as rezultatai/index.html.
        self.assertEqual(RESULTS_TREE, "2009_ep_rinkimai")
        self.assertEqual(MEMBERS_PAGE, "rezultatai/index.html")
        payload = json.loads((SITEMAPS / f"{ELECTION_ID}.results.json").read_text(encoding="utf-8"))
        self.assertEqual(payload["stats"], {"membersListed": 12, "membersInSitemap": 12, "membersNotInSitemap": 0})
        self.assertEqual(payload["elected"]["25370"]["party"], "Tėvynės sąjunga - Lietuvos krikščionys demokratai")


class Ep2009AnketaParserTests(unittest.TestCase):
    def setUp(self) -> None:
        self.landsbergis, self.landsbergis_stats = _parse("vytautas-landsbergis")
        self.zuokas, _ = _parse("arturas-zuokas")
        self.tomasevski, self.tomasevski_stats = _parse("valdemar-tomasevski")

    def test_expected_tabs_are_the_eras_five(self) -> None:
        self.assertEqual(
            EXPECTED_TABS,
            {"anketa", "biografija", "turto-ir-pajamu-deklaracijos", "interesu-deklaracija", "kita"},
        )

    def test_top_level_fields_and_candidacy(self) -> None:
        require(DEFAULT_RESULTS_PATH)
        self.assertEqual(self.landsbergis["electionId"], "2009-ep")
        self.assertEqual(self.landsbergis["candidateName"], "Vytautas LANDSBERGIS")
        self.assertEqual(
            self.landsbergis["kandidatavimas"],
            {
                "vrkCandidateId": "25370",
                "roles": ["daugiamandate"],
                "vienmandate": None,
                "daugiamandate": {
                    "sarasas": "Tėvynės sąjunga - Lietuvos krikščionys demokratai",
                    "sarasoNumeris": 11,
                    "sarasoId": "3565",
                    "numerisSarase": 1,
                },
                "isrinktas": True,
                "isrinktasKaip": "daugiamandate",
                "rezultatuSaltinis": "https://www.vrk.lt/statiniai/puslapiai/2009_ep_rinkimai/output_lt/rezultatai/index.html",
            },
        )
        self.assertFalse(self.zuokas["kandidatavimas"]["isrinktas"])
        self.assertEqual(self.landsbergis_stats["anomalies"], [])
        self.assertEqual(
            list(self.landsbergis["normalized"].keys()),
            [
                "profilis",
                "anketa",
                "biografija",
                "turto-ir-pajamu-deklaracijos",
                "privaciu-interesu-deklaracija",
                "politines-kampanijos-dalyvio-duomenys",
                "kita",
            ],
        )

    def test_profile_card(self) -> None:
        profilis = self.landsbergis["normalized"]["profilis"]
        self.assertEqual(profilis["vardas-pavarde"], "VYTAUTAS LANDSBERGIS")
        self.assertIsNone(profilis["pastaba"])
        # The page links the portrait on vrk.lt; the record carries the archived
        # sidecar and photoMeta remembers the URL it came from (issue #118).
        self.assertEqual(profilis["nuotrauka"], f"photos/{self.landsbergis['candidateId']}.jpg")
        self.assertTrue(
            self.landsbergis["rawData"]["profile"]["photoMeta"]["url"].endswith(
                "Kandidatas25370/Kandidato25370Foto.jpg"
            )
        )
        self.assertEqual(
            list(profilis["kita"].keys()),
            ["iskele", "numeris-sarase", "savarankisko-politines-kampanijos-dalyvio-duomenys"],
        )
        self.assertEqual(profilis["kita"]["iskele"]["reiksme"], "Tėvynės sąjunga - Lietuvos krikščionys demokratai")
        self.assertEqual(profilis["kita"]["numeris-sarase"]["reiksme"], "1")

    def test_ep_question_mapping(self) -> None:
        anketa = self.landsbergis["normalized"]["anketa"]
        self.assertEqual(
            list(anketa.keys()),
            [
                "gimimo-data",
                "adresas",
                "pareiskimai",
                "gimimo-vieta",
                "tautybe",
                "issilavinimas",
                "mokslo-laipsnis",
                "pedagoginis-vardas",
                "uzsienio-kalbos",
                "politine-organizacija",
                "anksciau-isrinktas",
                "pagrindine-darboviete",
                "visuomenine-veikla",
                "pomegiai",
                "seimine-padetis",
                "sutuoktinio-vardas-pavarde",
                "vaiku-vardai-pavardes",
                "kita-apie-save",
            ],
        )
        # The birth date is Q5 here; 2014 renumbered it Q3.
        self.assertEqual(anketa["gimimo-data"], "1932-10-18")
        self.assertEqual(anketa["adresas"], "Vilnius")
        self.assertEqual(
            anketa["pareiskimai"],
            {
                "ar-nebaigta-teismo-paskirta-bausme": "Neturiu",
                "ar-atliekate-karo-tarnyba": "Nesu",
                "ar-turite-kitos-valstybes-pilietybe": "Neturiu",
                "kitos-valstybes-pilietybe-valstybe": None,
                "ar-atimta-balsavimo-teise-kitoje-valstybeje": None,
                "ar-bendradarbiavote-su-uzsienio-tarnybomis": "Ne",
                "ar-buvote-pripazintas-kaltu": "Ne",
                "ar-buvote-pripazintas-kaltu-del-sunkaus-nusikaltimo": "Ne",
                "teisiniai-argumentai": None,
            },
        )
        self.assertEqual(anketa["gimimo-vieta"], "Kaunas")
        self.assertEqual(anketa["tautybe"], "lietuvis")
        self.assertEqual(
            anketa["issilavinimas"]["irasai"],
            [
                {
                    "issilavinimas": "Aukštasis",
                    "mokymo-istaigos-pavadinimas": "Valstybinė konservatorija (Muzikos akademija)",
                    "specialybe": "fortepijonas",
                    "baigimo-metai": "1955",
                }
            ],
        )
        # One line carries both: "…mokslo laipsnį <b>…</b>, vardą <b>…</b>".
        self.assertEqual(anketa["mokslo-laipsnis"], "Habilituotas daktaras")
        self.assertEqual(anketa["pedagoginis-vardas"], "Profesorius")
        self.assertEqual(anketa["uzsienio-kalbos"], ["anglų", "rusų", "lenkų"])
        self.assertEqual(anketa["anksciau-isrinktas"]["irasai"][0]["laikotarpis"], "1990 - 1992")
        self.assertEqual(anketa["pagrindine-darboviete"], "Europos Parlamentas, narys")
        self.assertEqual(anketa["seimine-padetis"], "vedęs")
        self.assertEqual(anketa["sutuoktinio-vardas-pavarde"], "Gražina")
        # Q21 is asked on this form (2014 EP dropped it).
        self.assertEqual(anketa["kita-apie-save"], "darbingas")

    def test_conviction_explanation_lands_under_the_2016_key(self) -> None:
        # Zuokas answered Q9.2 "Taip" and wrote into the Q9 block's free-text
        # line, which is the same slot as 2016's Q9.3.4.
        pareiskimai = self.zuokas["normalized"]["anketa"]["pareiskimai"]
        self.assertEqual(pareiskimai["ar-buvote-pripazintas-kaltu"], "Taip")
        self.assertTrue(pareiskimai["teisiniai-argumentai"].startswith("Vilniaus apygardos teismas skyrė 12500Lt. baudą"))

    def test_mapping_does_not_read_the_2014_birth_date_number(self) -> None:
        rows = [
            {"questionNumber": "3", "prompt": "3. Kažkas kita", "answer": "x"},
            {"questionNumber": "5", "prompt": "5. Gimimo data", "answer": "1960-01-02"},
            {"questionNumber": None, "prompt": "Jei turite, nurodykite mokslo laipsnį", "answer": "Daktaras"},
            {"questionNumber": None, "prompt": ", vardą", "answer": "Docentas"},
            {"questionNumber": None, "prompt": "Jei turite, nurodykite mokslo vardą", "answer": "Profesorius"},
            {"questionNumber": None, "prompt": "Tuo atveju, jei bent į vieną 9 punkto klausimą atsakėte „Taip“…", "answer": "Paaiškinimas"},
            {"questionNumber": "21", "prompt": "21. Be jau išvardytų atsakymų", "answer": "Tekstas"},
        ]
        normalized = normalize_ep_anketa_rows(rows)
        self.assertEqual(normalized["gimimo-data"], "1960-01-02")
        self.assertEqual(normalized["mokslo-laipsnis"], "Daktaras")
        self.assertEqual(normalized["pedagoginis-vardas"], "Docentas")
        # The title-only wording is read when the two-answer line is absent.
        title_only = normalize_ep_anketa_rows([rows[0], rows[1], rows[4]])
        self.assertIsNone(title_only["mokslo-laipsnis"])
        self.assertEqual(title_only["pedagoginis-vardas"], "Profesorius")
        self.assertEqual(normalized["pareiskimai"]["teisiniai-argumentai"], "Paaiškinimas")
        self.assertEqual(normalized["kita-apie-save"], "Tekstas")
        # The 2012 Seimo form carries the same free-text line.
        seimo = normalize_seimo_2012_anketa_rows(rows)
        self.assertEqual(seimo["pareiskimai"]["teisiniai-argumentai"], "Paaiškinimas")

    def test_declarations_and_interests(self) -> None:
        turto = self.landsbergis["normalized"]["turto-ir-pajamu-deklaracijos"]
        self.assertEqual(turto["valiuta"], "Lt")
        self.assertIsNotNone(turto["gautos-pajamos"])
        self.assertIsNotNone(turto["privalomas-registruoti-turtas"])
        interesai = self.landsbergis["normalized"]["privaciu-interesu-deklaracija"]
        self.assertEqual(interesai["deklaruojantis-asmuo"], "VYTAUTAS LANDSBERGIS")
        self.assertIn("deklaruojancio-asmens-sutuoktinis-partneris", interesai)

    def test_campaign_is_the_party_participant(self) -> None:
        campaigns = self.landsbergis["normalized"]["politines-kampanijos-dalyvio-duomenys"]
        self.assertEqual(len(campaigns), 1)
        campaign = campaigns[0]
        self.assertEqual(campaign["statusas"], "Savarankiškas")
        self.assertEqual(campaign["izdininkas"]["vardas-pavarde"], "EDELA RAKŠTELIENĖ")
        self.assertEqual(campaign["auditorius"]["imones-pavadinimas"], "E. Čiupailienės konsultacinė įmonė")
        aukos = campaign["aukos-pagal-sekcija"]["aukotoju-sarasas"]
        self.assertEqual(len(aukos["records"]), 33)
        self.assertEqual(aukos["suvestine"], [{"label": "Iš viso", "amountEur": None, "amountLt": 815509.63, "note": None}])
        self.assertEqual(len(campaign["finansavimo-ataskaitos"]), 13)
        self.assertEqual(campaign["finansavimo-ataskaitos"][0]["reportType"], "Pradinė")
        # Tomaševski's page links his presidential campaign's participant id
        # under the EP path, where it does not exist: no campaign data, one
        # fetch anomaly in his fixture index, and a CampaignRootMissing
        # warning at parse time so the gap reaches anomalies.jsonl.
        self.assertNotIn("politines-kampanijos-dalyvio-duomenys", self.tomasevski["normalized"])
        self.assertEqual([event["eventType"] for event in self.tomasevski_stats["anomalies"]], ["CampaignRootMissing"])
        self.assertEqual(self.tomasevski_stats["anomalies"][0]["detail"]["campaignKey"], "dalyvis-4000")
        index = json.loads((SAMPLES_ROOT / "valdemar-tomasevski" / "index.json").read_text(encoding="utf-8"))
        self.assertEqual([event["eventType"] for event in index["anomalies"]], ["CampaignRootFetchFailed"])
        self.assertTrue(index["campaignSamples"][0]["campaignUrl"].endswith("Dalyvis4000/Dalyvio4000Izdininkas.html"))


if __name__ == "__main__":
    unittest.main()
