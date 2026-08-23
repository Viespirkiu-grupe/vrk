import json
import tempfile
import unittest
from pathlib import Path

from scraper.elections.ep_2004.anketa_parser import (
    _parse_deklaracijos_html,
    normalize_ep_2004_anketa_rows,
    parse_anketa_html,
    parse_anketa_sample,
)
from scraper.elections.ep_2004.candidate_samples import EXPECTED_TABS, extract_tab_links
from scraper.elections.ep_2004.results import (
    MEMBERS_PAGE,
    RESULTS_ROOT,
    SEATS,
    parse_members_page,
    parse_preference_page,
    parse_results_page,
)
from scraper.elections.ep_2004.sitemap import (
    ELECTION_ID,
    LISTING_URL,
    build_sitemap_from_sample,
)


REPO_ROOT = Path(__file__).resolve().parents[1]
SAMPLES_ROOT = REPO_ROOT / "samples" / "html" / ELECTION_ID
RESULTS_ROOT_DIR = REPO_ROOT / "samples" / "results" / ELECTION_ID
SITEMAPS = REPO_ROOT / "sitemaps"
CANDIDATES = "https://www.vrk.lt/statiniai/puslapiai/rinkimai/2004/euro/kandidatai/"
REZULTATAI = "https://www.vrk.lt/statiniai/puslapiai/rinkimai/2004/euro/rezultatai/"


def _parse(candidate_id: str) -> tuple[dict, dict]:
    with tempfile.TemporaryDirectory() as tmp:
        output_path, stats = parse_anketa_sample(
            candidate_id=candidate_id,
            samples_root=SAMPLES_ROOT,
            output_root=Path(tmp),
        )
        return json.loads(output_path.read_text(encoding="utf-8")), stats


class Ep2004SitemapTests(unittest.TestCase):
    def test_index_and_lists_reconcile(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            _, stats = build_sitemap_from_sample(
                sample_path=SAMPLES_ROOT,
                output_path=Path(tmp) / "sitemap.json",
            )
            payload = json.loads((Path(tmp) / "sitemap.json").read_text(encoding="utf-8"))

        # The 2004 pages lay everything out in nested tables, so an outer
        # layout row contains every candidate anchor: read naively the walk
        # counted 277 rows for 241 candidates and lost every list position.
        self.assertEqual(stats["lists"], 12)
        self.assertEqual(stats["declared_candidates"], 241)
        self.assertEqual(stats["rows"], 241)
        self.assertEqual(stats["extracted"], 241)
        self.assertEqual(stats["list_count_mismatches"], 0)
        self.assertEqual(stats["skipped"], 0)
        self.assertEqual(stats["duplicate_candidate_ids"], 0)
        self.assertEqual(payload["electionId"], "2004-ep")
        self.assertEqual(payload["sourceUrl"], LISTING_URL)
        self.assertEqual(len(payload["listUrls"]), 12)
        by_id = {entry["candidateId"]: entry for entry in payload["entries"]}
        self.assertEqual(
            by_id["justas-vincas-paleckis"],
            {
                "candidateName": "Justas Vincas PALECKIS",
                "candidateId": "justas-vincas-paleckis",
                "url": CANDIDATES + "kand_anketa_l_260848.htm",
                "vrkCandidateId": "260848",
                "roles": ["daugiamandate"],
                "daugiamandateCandidacy": {
                    "sarasas": "Lietuvos socialdemokratų partija",
                    "sarasoNumeris": 2,
                    "sarasoId": "1698",
                    "numerisSarase": 1,
                },
            },
        )
        self.assertTrue(all(entry["daugiamandateCandidacy"]["numerisSarase"] for entry in payload["entries"]))
        leaders = [entry for entry in payload["entries"] if entry["daugiamandateCandidacy"]["numerisSarase"] == 1]
        self.assertEqual(len(leaders), 12)


class Ep2004FetcherTests(unittest.TestCase):
    def test_expected_tabs_are_the_three_pages(self) -> None:
        self.assertEqual(EXPECTED_TABS, {"anketa", "biografija", "turto-ir-pajamu-deklaracijos"})

    def test_tab_links_come_from_the_card(self) -> None:
        html = (SAMPLES_ROOT / "justas-vincas-paleckis" / "anketa.html").read_text(encoding="utf-8")
        links = extract_tab_links(html, CANDIDATES + "kand_anketa_l_260848.htm")
        self.assertEqual(
            links,
            [
                {"label": "Anketa", "slug": "anketa", "url": CANDIDATES + "kand_anketa_l_260848.htm"},
                {"label": "Biografija", "slug": "biografija", "url": CANDIDATES + "kand_biog_l_260848.htm"},
                {
                    "label": "Pajamų ir turto deklaracijų pagrindinių duomenų išrašai",
                    "slug": "turto-ir-pajamu-deklaracijos",
                    "url": CANDIDATES + "kand_pajam_l_260848.htm",
                },
            ],
        )
        index = json.loads((SAMPLES_ROOT / "justas-vincas-paleckis" / "index.json").read_text(encoding="utf-8"))
        self.assertEqual([tab["slug"] for tab in index["tabSamples"]], ["anketa", "biografija", "turto-ir-pajamu-deklaracijos"])
        self.assertEqual(index["missingExpectedTabs"], [])
        self.assertEqual(index["campaignSamples"], [])


class Ep2004ResultsTests(unittest.TestCase):
    def test_results_file_reconciles(self) -> None:
        self.assertEqual(MEMBERS_PAGE, "rez_isrinkti_l_18_1.htm")
        self.assertEqual(SEATS, 13)
        payload = json.loads((SITEMAPS / f"{ELECTION_ID}.results.json").read_text(encoding="utf-8"))
        self.assertEqual(
            payload["stats"],
            {
                "seats": 13,
                "membersListed": 13,
                "membersInSitemap": 13,
                "membersNotInSitemap": 0,
                "substitutions": 1,
                "elected": 14,
                "mandatesDeclared": 13,
                "listMandateMismatches": 0,
                "rankingPages": 12,
                "candidatesRanked": 241,
                "rankedNotInSitemap": 0,
                "sitemapNotRanked": 0,
                "boldNotMembers": 0,
                "membersNotBold": 0,
                "listPositionMismatches": 0,
            },
        )
        self.assertEqual(payload["elected"]["260811"]["party"], "Tėvynės sąjunga (konservatoriai, politiniai kaliniai ir tremtiniai, krikščioniškieji demokratai)")
        self.assertEqual(payload["elected"]["260811"]["method"], "members-list")
        self.assertEqual(payload["details"]["ranking"]["260811"], {
            "rank": 1,
            "listPosition": 1,
            "preferenceVotes": 100701,
            "listId": "1739",
            "sourceUrl": REZULTATAI + "rez_pirm_l_1739.htm",
        })

    def test_members_page_names_the_substitution(self) -> None:
        html = (RESULTS_ROOT_DIR / "rezultatai__rez_isrinkti_l_18_1.htm").read_text(encoding="utf-8")
        page = parse_members_page(html, RESULTS_ROOT + MEMBERS_PAGE)
        self.assertEqual(len(page["members"]), 13)
        self.assertEqual([member["name"] for member in page["members"] if member["marked"]], ["Kazimira Danutė PRUNSKIENĖ"])
        self.assertEqual(page["replacements"], [{
            "vrkCandidateId": "260979",
            "name": "Gintaras DIDŽIOKAS",
            "anketaUrl": CANDIDATES + "kand_anketa_l_260979.htm",
        }])
        self.assertEqual(
            [decision["label"] for decision in page["decisions"]],
            ["VRK 2004 m. birželio 21 d. sprendimu Nr. 180", "VRK 2004 m. birželio 21 d. sprendimu Nr. 181"],
        )
        self.assertIn("įgaliojimai pripažinti nutrūkusiais", page["note"])
        self.assertNotIn(" ,", page["note"])

    def test_results_and_preference_pages(self) -> None:
        rows = parse_results_page((RESULTS_ROOT_DIR / "rezultatai__rez_l_18.htm").read_text(encoding="utf-8"))
        self.assertEqual(len(rows), 12)
        self.assertEqual(sum(row["mandates"] for row in rows), 13)
        self.assertEqual(rows[0], {"listNumber": 11, "name": "Darbo partija", "votes": 363996, "mandates": 5})
        ranking = parse_preference_page((RESULTS_ROOT_DIR / "rezultatai__rez_pirm_l_1730.htm").read_text(encoding="utf-8"))
        self.assertEqual(len(ranking), 26)
        self.assertEqual(ranking[0]["vrkCandidateId"], "260978")
        self.assertTrue(ranking[0]["mandate"])
        self.assertEqual(ranking[1], {
            "vrkCandidateId": "260979",
            "name": "Gintaras DIDŽIOKAS",
            "rank": 2,
            "listPosition": 2,
            "preferenceVotes": 26767,
            "mandate": False,
        })


class Ep2004AnketaParserTests(unittest.TestCase):
    def setUp(self) -> None:
        self.paleckis, self.paleckis_stats = _parse("justas-vincas-paleckis")
        self.landsbergis, _ = _parse("vytautas-landsbergis")
        self.prunskiene, _ = _parse("kazimira-danute-prunskiene")
        self.didziokas, _ = _parse("gintaras-didziokas")
        self.backis, _ = _parse("vytautas-ricardas-backis")
        self.salkovskis, _ = _parse("nikolajus-salkovskis")
        self.kundrotas, self.kundrotas_stats = _parse("marius-kundrotas")

    def test_top_level_fields_and_candidacy(self) -> None:
        self.assertEqual(self.paleckis["electionId"], "2004-ep")
        self.assertEqual(self.paleckis["candidateName"], "Justas Vincas PALECKIS")
        self.assertEqual(
            self.paleckis["kandidatavimas"],
            {
                "vrkCandidateId": "260848",
                "roles": ["daugiamandate"],
                "vienmandate": None,
                "daugiamandate": {
                    "sarasas": "Lietuvos socialdemokratų partija",
                    "sarasoNumeris": 2,
                    "sarasoId": "1698",
                    "numerisSarase": 1,
                },
                "isrinktas": True,
                "isrinktasKaip": "daugiamandate",
                "rezultatuSaltinis": REZULTATAI + "rez_isrinkti_l_18_1.htm",
                "porinkiminisNumerisSarase": 1,
                "pirmumoBalsai": 101882,
                "pirmumoBalsuSaltinis": REZULTATAI + "rez_pirm_l_1698.htm",
            },
        )
        self.assertEqual(self.paleckis_stats["anomalies"], [])
        self.assertEqual(self.paleckis_stats["rowCount"], 23)
        self.assertEqual(
            list(self.paleckis["normalized"].keys()),
            ["profilis", "anketa", "biografija", "turto-ir-pajamu-deklaracijos"],
        )
        self.assertEqual(
            list(self.paleckis["rawData"].keys()),
            ["profile", "anketa", "biografija", "turtoIrPajamuDeklaracijos"],
        )
        self.assertEqual(self.paleckis["source"]["candidateSourceUrl"], CANDIDATES + "kand_anketa_l_260848.htm")

    def test_the_substitution_is_on_both_records(self) -> None:
        # VRK's members page lists Prunskienė with a footnote: at her request
        # her mandate was declared terminated (decision Nr. 180) and the
        # list's next member recognised as elected (Nr. 181). Both records
        # carry isrinktas and the decision that links them.
        prunskiene = self.prunskiene["kandidatavimas"]
        self.assertTrue(prunskiene["isrinktas"])
        self.assertEqual(prunskiene["mandatasNutrauktas"]["replacedBy"], "260979")
        self.assertEqual(prunskiene["mandatasNutrauktas"]["decision"]["label"], "VRK 2004 m. birželio 21 d. sprendimu Nr. 180")
        self.assertTrue(prunskiene["mandatasNutrauktas"]["decision"]["url"].startswith("http://www3.lrs.lt/"))
        self.assertEqual(prunskiene["porinkiminisNumerisSarase"], 1)
        didziokas = self.didziokas["kandidatavimas"]
        self.assertTrue(didziokas["isrinktas"])
        self.assertEqual(didziokas["pakeiteNari"], "260978")
        self.assertEqual(didziokas["vrkSprendimas"]["label"], "VRK 2004 m. birželio 21 d. sprendimu Nr. 181")
        self.assertEqual(didziokas["porinkiminisNumerisSarase"], 2)
        self.assertNotIn("mandatasNutrauktas", didziokas)
        self.assertNotIn("pakeiteNari", prunskiene)
        self.assertFalse(self.kundrotas["kandidatavimas"]["isrinktas"])
        self.assertEqual(self.kundrotas["kandidatavimas"]["pirmumoBalsai"], 1667)

    def test_profile_card(self) -> None:
        profilis = self.paleckis["normalized"]["profilis"]
        self.assertEqual(profilis["vardas-pavarde"], "Justas Vincas PALECKIS")
        self.assertIsNone(profilis["pastaba"])
        self.assertEqual(profilis["nuotrauka"], "https://www.vrk.lt/statiniai/puslapiai/rinkimai/2004/euro/nuotraukos/1698_34201010105.jpg")
        self.assertEqual(
            profilis["kita"],
            {
                "iskele": {
                    "pavadinimas": "Iškėlė",
                    "reiksme": "Lietuvos socialdemokratų partija",
                    "nuorodos": [CANDIDATES + "kand_part_l_1698.htm"],
                },
                "priesrinkiminis-numeris-sarase": {
                    "pavadinimas": "priešrinkiminis numeris sąraše",
                    "reiksme": "1",
                    "nuorodos": [],
                },
            },
        )
        # The Biografija / Pajamų links are the page-set, not card fields.
        self.assertEqual([field["key"] for field in self.paleckis["rawData"]["profile"]["fields"]], ["Iškėlė", "priešrinkiminis numeris sąraše"])

    def test_ep_2004_question_mapping(self) -> None:
        anketa = self.paleckis["normalized"]["anketa"]
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
        # Q3 on this form, printed "1942.01.01"; the corpus's ISO form.
        self.assertEqual(anketa["gimimo-data"], "1942-01-01")
        self.assertEqual(self.paleckis["rawData"]["anketa"]["rows"][0]["answer"], "1942.01.01")
        self.assertEqual(anketa["adresas"], "Vilnius")
        self.assertEqual(
            anketa["pareiskimai"],
            {
                "ar-nebaigta-teismo-paskirta-bausme": "Neturi",
                "ar-atliekate-karo-tarnyba": "Nėra",
                "ar-turite-kitos-valstybes-pilietybe": "Neturi",
                "kitos-valstybes-pilietybe-valstybe": None,
                "ar-atimta-balsavimo-teise-kitoje-valstybeje": None,
                "ar-bendradarbiavote-su-uzsienio-tarnybomis": "Nėra",
                "ar-buvote-pripazintas-kaltu": "Nėra",
                "ar-buvote-pripazintas-kaltu-del-sunkaus-nusikaltimo": "Nebuvo",
                "teisiniai-argumentai": None,
            },
        )
        self.assertEqual(anketa["gimimo-vieta"], "RUSIJA, Samara")
        self.assertEqual(anketa["tautybe"], "Lietuvis (-ė)")
        self.assertEqual(
            anketa["issilavinimas"]["irasai"],
            [
                {
                    "issilavinimas": "Aukštasis",
                    "mokyklos-istaigos-pavadinimas": "Diplomatinė akademija (Maskva)",
                    "specialybe": "diplomatas",
                    "baigimo-metai": "1969",
                },
                {
                    "issilavinimas": "Aukštasis",
                    "mokyklos-istaigos-pavadinimas": "Vilniaus valstybinis universitetas",
                    "specialybe": "žurnalistas",
                    "baigimo-metai": "1964",
                },
            ],
        )
        self.assertIsNone(anketa["mokslo-laipsnis"])
        # A list-type answer is one <b> per item, comma-separated on the page.
        self.assertEqual(anketa["uzsienio-kalbos"], ["Anglų", "Vokiečių", "Rusų", "Lenkų"])
        self.assertEqual(anketa["pomegiai"], "Gamta, Skaitymas, Sportas")
        self.assertEqual(anketa["vaiku-vardai-pavardes"], "Rimvydas Paleckis, Algirdas Paleckis, Justina Paleckytė")
        row_20 = next(row for row in self.paleckis["rawData"]["anketa"]["rows"] if row["questionNumber"] == "20")
        self.assertEqual(row_20["answerItems"], ["Rimvydas Paleckis", "Algirdas Paleckis", "Justina Paleckytė"])
        self.assertEqual(
            anketa["anksciau-isrinktas"]["irasai"],
            [{"institucijos-pavadinimas-pareigos": "LR Aukščiausioji Taryba", "laikotarpis": "1990 - 1992"}],
        )
        self.assertEqual(anketa["pagrindine-darboviete"], "LR Užsienio reikalų ministerija, viceministras")
        self.assertIsNone(anketa["visuomenine-veikla"])
        self.assertEqual(anketa["seimine-padetis"], "Vedęs")
        self.assertEqual(anketa["sutuoktinio-vardas-pavarde"], "Laima Paleckienė (Škarnulytė)")
        self.assertIsNone(anketa["kita-apie-save"])

    def test_degree_and_title_trail_the_education_table(self) -> None:
        anketa = self.landsbergis["normalized"]["anketa"]
        self.assertEqual(anketa["mokslo-laipsnis"], "Habilituotas daktaras")
        self.assertEqual(anketa["pedagoginis-vardas"], "Profesorius")
        self.assertEqual(anketa["kita-apie-save"], "Turiu 10 anūkų ir 2 proanūkius")
        rows = self.landsbergis["rawData"]["anketa"]["rows"]
        prompts = [row["prompt"] for row in rows]
        index = prompts.index("12. Išsilavinimas:")
        self.assertEqual(prompts[index + 1 : index + 3], ["Moksliniai laipsniai:", "Moksliniai vardai:"])
        self.assertIsInstance(rows[index]["answer"], list)

    def test_another_member_states_citizenship(self) -> None:
        pareiskimai = self.backis["normalized"]["anketa"]["pareiskimai"]
        self.assertEqual(pareiskimai["ar-turite-kitos-valstybes-pilietybe"], "Turi")
        self.assertEqual(pareiskimai["kitos-valstybes-pilietybe-valstybe"], "PRANCŪZIJA")
        self.assertEqual(pareiskimai["ar-atimta-balsavimo-teise-kitoje-valstybeje"], "Ne")

    def test_conviction_explanation_is_the_unlabelled_row_after_q9(self) -> None:
        pareiskimai = self.salkovskis["normalized"]["anketa"]["pareiskimai"]
        self.assertEqual(pareiskimai["ar-buvote-pripazintas-kaltu"], "Yra")
        self.assertTrue(pareiskimai["teisiniai-argumentai"].startswith("Pripažintas kaltu pagal LR BK 246 str. 1 d."))
        rows = self.salkovskis["rawData"]["anketa"]["rows"]
        index = next(i for i, row in enumerate(rows) if row["questionNumber"] == "9.3")
        self.assertEqual(rows[index + 1]["prompt"], "")
        self.assertIsNone(rows[index + 1]["questionNumber"])

    def test_empty_answers_are_null_not_missing_rows(self) -> None:
        # The sparsest questionnaire of the field prints every question with
        # an empty <b>; the rows are there, the answers are null.
        anketa = self.kundrotas["normalized"]["anketa"]
        self.assertEqual(self.kundrotas_stats["rowCount"], 23)
        self.assertIsNone(anketa["gimimo-vieta"])
        self.assertIsNone(anketa["tautybe"])
        self.assertEqual(anketa["issilavinimas"]["irasai"], [])
        self.assertEqual(anketa["uzsienio-kalbos"], [])
        self.assertIsNone(anketa["seimine-padetis"])
        self.assertEqual(anketa["gimimo-data"], "1978-04-04")
        self.assertEqual(self.kundrotas_stats["anomalies"], [])

    def test_omitted_questions_stay_null(self) -> None:
        record, stats = _parse("evalda-siskauskiene")
        anketa = record["normalized"]["anketa"]
        self.assertEqual(stats["rowCount"], 20)
        self.assertIsNone(anketa["seimine-padetis"])
        self.assertIsNone(anketa["sutuoktinio-vardas-pavarde"])
        self.assertIsNone(anketa["vaiku-vardai-pavardes"])
        self.assertTrue(anketa["kita-apie-save"].startswith("Lengvai bendrauju"))

    def test_mapping_reads_q3_and_the_2004_sub_questions(self) -> None:
        rows = [
            {"questionNumber": "3", "prompt": "3. Gimimo data:", "answer": "1960.01.02"},
            {"questionNumber": "5", "prompt": "5. Kažkas kita", "answer": "x"},
            {"questionNumber": "8.4", "prompt": "8.4. Ar turi kitos Europos Sąjungos valstybės narės pilietybę:", "answer": "Turi"},
            {"questionNumber": "8.4.1", "prompt": "8.4.1. Kurios:", "answer": "LENKIJA"},
            {"questionNumber": "8.4.2", "prompt": "8.4.2. Ar nėra atimta balsavimo teisė:", "answer": "Ne"},
            {"questionNumber": "9.3", "prompt": "9.3. Ar įsiteisėjusiu teismo nuosprendžiu", "answer": "Buvo"},
            {"questionNumber": None, "prompt": "", "answer": "Paaiškinimas"},
            {"questionNumber": "12", "prompt": "12. Išsilavinimas:", "answer": [{"Išsilavinimas": "Aukštasis", "Baigimo metai": "1980"}]},
            {"questionNumber": None, "prompt": "Moksliniai laipsniai:", "answer": "Daktaras"},
            {"questionNumber": None, "prompt": "Moksliniai vardai:", "answer": "Docentas"},
            {"questionNumber": "19", "prompt": "19. Šeimyninė padėtis:", "answer": "Vedęs"},
            {"questionNumber": None, "prompt": "vyro arba žmonos vardas (pavardė):", "answer": "Ona"},
        ]
        normalized = normalize_ep_2004_anketa_rows(rows)
        self.assertEqual(normalized["gimimo-data"], "1960-01-02")
        self.assertEqual(normalized["pareiskimai"]["ar-turite-kitos-valstybes-pilietybe"], "Turi")
        self.assertEqual(normalized["pareiskimai"]["kitos-valstybes-pilietybe-valstybe"], "LENKIJA")
        self.assertEqual(normalized["pareiskimai"]["ar-atimta-balsavimo-teise-kitoje-valstybeje"], "Ne")
        self.assertEqual(normalized["pareiskimai"]["ar-buvote-pripazintas-kaltu-del-sunkaus-nusikaltimo"], "Buvo")
        self.assertEqual(normalized["pareiskimai"]["teisiniai-argumentai"], "Paaiškinimas")
        self.assertEqual(normalized["issilavinimas"]["irasai"], [{"issilavinimas": "Aukštasis", "baigimo-metai": "1980"}])
        self.assertEqual(normalized["mokslo-laipsnis"], "Daktaras")
        self.assertEqual(normalized["pedagoginis-vardas"], "Docentas")
        self.assertEqual(normalized["seimine-padetis"], "Vedęs")
        self.assertEqual(normalized["sutuoktinio-vardas-pavarde"], "Ona")
        # Only an unlabelled row directly after 9.3 is the explanation.
        without = normalize_ep_2004_anketa_rows(rows[:6] + rows[7:])
        self.assertIsNone(without["pareiskimai"]["teisiniai-argumentai"])

    def test_row_splitter_on_a_synthetic_cell(self) -> None:
        html = """
        <td class="bigcell"><h4>Anketa</h4><h4>Ona TESTIENĖ</h4>
        <table><tbody>
        <tr><td class="lt"><img src="/x.jpg" />Iškėlė: <b><a href="/statiniai/puslapiai/rinkimai/2004/euro/kandidatai/kand_part_l_1.htm">P</a></b><br />priešrinkiminis numeris sąraše: <b>3</b>
            <a href="/statiniai/puslapiai/rinkimai/2004/euro/kandidatai/kand_biog_l_9.htm">Biografija</a></td></tr>
        <tr><td>&nbsp;</td></tr>
        <tr class="r1"><td class="lt"> 13. Kokias kalbas moka: <b>Anglų</b>,&nbsp;<b>Rusų</b></td></tr>
        <tr class="r2"><td class="lt"> 18. Pomėgiai: <b></b></td></tr>
        <tr class="r1"><td class="lt"> 19. Šeimyninė padėtis: <b></b>&nbsp;vyro arba žmonos vardas (pavardė): <b>Jonas</b></td></tr>
        </tbody></table></td>
        """
        parsed = parse_anketa_html(html)
        self.assertEqual(parsed["profile"]["candidateDisplayName"], "Ona TESTIENĖ")
        self.assertEqual([field["key"] for field in parsed["profile"]["fields"]], ["Iškėlė", "priešrinkiminis numeris sąraše"])
        rows = parsed["anketa"]["rows"]
        self.assertEqual(
            [(row["questionNumber"], row["prompt"], row["answer"]) for row in rows],
            [
                ("13", "13. Kokias kalbas moka:", "Anglų, Rusų"),
                ("18", "18. Pomėgiai:", ""),
                ("19", "19. Šeimyninė padėtis:", ""),
                (None, "vyro arba žmonos vardas (pavardė):", "Jonas"),
            ],
        )
        # An empty <b> closes its row, so the spouse label does not join the
        # Q19 prompt and take the spouse's name as Q19's answer.
        self.assertEqual(parsed["anketa"]["normalized"]["sutuoktinio-vardas-pavarde"], "Jonas")
        self.assertIsNone(parsed["anketa"]["normalized"]["seimine-padetis"])

    def test_biography(self) -> None:
        biografija = self.paleckis["normalized"]["biografija"]["tekstas"]
        self.assertTrue(biografija.startswith("JUSTAS VINCAS PALECKIS KANDIDATAS Į EUROPOS PARLAMENTĄ, IŠKELTAS LIETUVOS SOCIALDEMOKRATŲ PARTIJOS Justas Vincas Paleckis gimė 1942 m. sausio 1 d."))
        self.assertTrue(self.paleckis["rawData"]["biografija"]["html"].startswith("<blockquote>"))

    def test_declarations(self) -> None:
        turto = self.paleckis["normalized"]["turto-ir-pajamu-deklaracijos"]
        self.assertEqual(
            turto,
            {
                "privalomas-registruoti-turtas": 170000,
                "vertybiniai-popieriai-meno-kuriniai-juvelyriniai-dirbiniai": 34881,
                "pinigines-lesos": 68829,
                "suteiktos-paskolos": None,
                "gautos-paskolos": None,
                "gautos-pajamos": 98270,
                "sumoketas-pajamu-mokestis": 29568,
                "valiuta": "Lt",
                "pastaba": None,
                "pajamos-pagal-forma": [
                    {"forma": "FR0462", "gautos-pajamos": None, "sumoketas-pajamu-mokestis": None},
                    {"forma": "FR0462S33", "gautos-pajamos": None, "sumoketas-pajamu-mokestis": None},
                    {"forma": "FR0462S15", "gautos-pajamos": None, "sumoketas-pajamu-mokestis": None},
                    {"forma": "FR0462S0", "gautos-pajamos": None, "sumoketas-pajamu-mokestis": None},
                    {"forma": "FR0462S", "gautos-pajamos": 98270, "sumoketas-pajamu-mokestis": 29568},
                ],
                "israsai": {
                    "turto-deklaracija": {
                        "pavadinimas": "METINĖ ŠEIMOS TURTO DEKLARACIJA",
                        "israsa-isdave": "Vilniaus apskrities VMI Vilniaus skyrius",
                        "gavimo-data": "2004-05-06",
                        "darboviete": "Lietuvos Respublikos Užsienio reikalų ministerija",
                        "pildymo-data": "2004-05-06",
                    },
                    "pajamu-deklaracija": {
                        "pavadinimas": "METINĖ GYVENTOJO PAJAMŲ DEKLARACIJA",
                        "israsa-isdave": "Vilniaus apskrities VMI Vilniaus skyrius",
                        "gavimo-data": "2004-04-28",
                        "darboviete": "Lietuvos Respublikos Užsienio reikalų ministerija",
                        "pildymo-data": "2004-05-06",
                    },
                },
            },
        )
        raw = self.paleckis["rawData"]["turtoIrPajamuDeklaracijos"]["sections"]
        self.assertEqual([section["title"] for section in raw], ["METINĖ ŠEIMOS TURTO DEKLARACIJA", "METINĖ GYVENTOJO PAJAMŲ DEKLARACIJA"])
        self.assertEqual(raw[0]["items"][1], {"key": "I. PRIVALOMAS REGISTRUOTI TURTAS", "value": "170000 Lt.", "label": "Visa šeimos turto vertė"})
        self.assertEqual(raw[1]["items"][1], {"key": "1) FR0462 formos deklaracijos", "form": "FR0462", "value": "", "income": "-", "tax": "-"})

    def test_declaration_variants(self) -> None:
        # The individual form, and income filed on two form variants.
        individual = self.prunskiene["normalized"]["turto-ir-pajamu-deklaracijos"]
        self.assertEqual(individual["israsai"]["turto-deklaracija"]["pavadinimas"], "METINĖ GYVENTOJO TURTO DEKLARACIJA")
        self.assertEqual(individual["pinigines-lesos"], 261943)
        platelis, _ = _parse("kornelijus-platelis")
        turto = platelis["normalized"]["turto-ir-pajamu-deklaracijos"]
        filed = [form for form in turto["pajamos-pagal-forma"] if form["gautos-pajamos"] is not None]
        self.assertEqual([form["forma"] for form in filed], ["FR0462", "FR0462S33", "FR0462S15"])
        self.assertEqual(turto["gautos-pajamos"], sum(form["gautos-pajamos"] for form in filed))
        self.assertEqual(turto["sumoketas-pajamu-mokestis"], sum(form["sumoketas-pajamu-mokestis"] for form in filed))
        # Nothing filed on any form: null, not zero.
        nothing = self.kundrotas["normalized"]["turto-ir-pajamu-deklaracijos"]
        self.assertIsNone(nothing["gautos-pajamos"])
        self.assertIsNone(nothing["sumoketas-pajamu-mokestis"])
        self.assertIsNone(nothing["israsai"]["pajamu-deklaracija"]["darboviete"])

    def test_declaration_parser_reads_a_synthetic_page(self) -> None:
        html = """
        <td class="bigcell"><h4>X</h4><div align="center">
        <h5><a name="d1"></a>METINĖ GYVENTOJO <u>TURTO</u> DEKLARACIJA</h5>
        <div>Pagrindinių duomenų išrašą išdavė <b>Kauno VMI</b>. Gavimo data <b>2004.05.01</b>.<br />
        <table><tbody>
        <tr><td class="lt" colspan="2">3. Darbovietė: <b>UAB Testas</b></td></tr>
        <tr><td class="ct" colspan="2"><h5>I. PRIVALOMAS REGISTRUOTI TURTAS</h5></td></tr>
        <tr><td class="lt">Visa gyventojo turto vertė</td><td class="rt"><b>12000 Lt.</b></td></tr>
        <tr><td class="lt" colspan="2">Pildymo data: <b>2004.05.02</b></td></tr>
        </tbody></table></div>
        <h5><a name="d2"></a>METINĖ GYVENTOJO <u>PAJAMŲ</u> DEKLARACIJA</h5>
        <div>Pagrindinių duomenų išrašą išdavė <b>Kauno VMI</b>. Gavimo data <b>2004.05.03</b>.<br />
        <table><tbody>
        <tr><td class="lt" colspan="2"><b>1) FR0462 formos</b> deklaracijos:</td></tr>
        <tr><td class="lt">Gautų pajamų suma</td><td class="rt"><b>1000 Lt.</b></td></tr>
        <tr><td class="lt">Išskaičiuota (sumokėta) mokesčio suma</td><td class="rt"><b>-</b></td></tr>
        </tbody></table></div></div></td>
        """
        parsed = _parse_deklaracijos_html(html)
        self.assertEqual([section["title"] for section in parsed["sections"]], ["METINĖ GYVENTOJO TURTO DEKLARACIJA", "METINĖ GYVENTOJO PAJAMŲ DEKLARACIJA"])
        self.assertEqual(parsed["sections"][0]["issuer"], "Kauno VMI")
        self.assertEqual(parsed["sections"][0]["receivedDate"], "2004.05.01")
        self.assertEqual(parsed["sections"][0]["items"][1]["value"], "12000 Lt.")
        self.assertEqual(parsed["sections"][1]["items"][0]["income"], "1000 Lt.")
        self.assertEqual(parsed["sections"][1]["items"][0]["tax"], "-")


if __name__ == "__main__":
    unittest.main()
