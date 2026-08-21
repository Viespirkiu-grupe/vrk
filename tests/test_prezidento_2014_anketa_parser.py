import json
import tempfile
import unittest
from pathlib import Path

from scraper.elections.prezidento_2014.anketa_parser import (
    normalize_presidential_anketa_rows,
    parse_anketa_sample,
)
from scraper.elections.prezidento_2014.candidate_samples import EXPECTED_TABS
from scraper.elections.prezidento_2014.sitemap import (
    ELECTION_ID,
    LISTING_URL,
    build_sitemap_from_sample,
)


REPO_ROOT = Path(__file__).resolve().parents[1]
SAMPLES_ROOT = REPO_ROOT / "samples" / "html" / ELECTION_ID


def _parse(candidate_id: str) -> tuple[dict, dict]:
    with tempfile.TemporaryDirectory() as tmp:
        output_path, stats = parse_anketa_sample(
            candidate_id=candidate_id,
            samples_root=SAMPLES_ROOT,
            output_root=Path(tmp),
        )
        return json.loads(output_path.read_text(encoding="utf-8")), stats


class Prezidento2014SitemapTests(unittest.TestCase):
    def test_listing_yields_the_seven_candidates_once_each(self) -> None:
        # Every listing row links the anketa twice — from the name and from a
        # "Plačiau" link — and must still produce one entry.
        with tempfile.TemporaryDirectory() as tmp:
            _, stats = build_sitemap_from_sample(
                sample_path=SAMPLES_ROOT / "list.html",
                output_path=Path(tmp) / "sitemap.json",
            )
            payload = json.loads((Path(tmp) / "sitemap.json").read_text(encoding="utf-8"))

        self.assertEqual(stats["extracted"], 7)
        self.assertEqual(stats["duplicate_candidate_ids"], 0)
        self.assertEqual(payload["electionId"], "2014-prezidento")
        self.assertEqual(payload["sourceUrl"], LISTING_URL)
        by_id = {entry["candidateId"]: entry for entry in payload["entries"]}
        self.assertEqual(
            set(by_id),
            {
                "zigmantas-balcytis",
                "dalia-grybauskaite",
                "arturas-paulauskas",
                "naglis-puteikis",
                "bronis-rope",
                "valdemar-tomasevski",
                "arturas-zuokas",
            },
        )
        # The name cell joins given name and surname with two non-breaking
        # spaces; they collapse to one plain space.
        self.assertEqual(by_id["dalia-grybauskaite"]["candidateName"], "Dalia GRYBAUSKAITĖ")
        self.assertTrue(
            by_id["dalia-grybauskaite"]["url"].endswith("Kandidatas70873/Kandidato70873Anketa.html")
        )


class Prezidento2014AnketaParserTests(unittest.TestCase):
    def setUp(self) -> None:
        self.grybauskaite, self.grybauskaite_stats = _parse("dalia-grybauskaite")
        self.balcytis, _ = _parse("zigmantas-balcytis")
        self.paulauskas, _ = _parse("arturas-paulauskas")

    def test_expected_tabs_add_the_trustees_tab(self) -> None:
        self.assertEqual(
            EXPECTED_TABS,
            {
                "anketa",
                "biografija",
                "turto-ir-pajamu-deklaracijos",
                "interesu-deklaracija",
                "patiketiniai",
                "kita",
            },
        )

    def test_top_level_fields(self) -> None:
        self.assertEqual(self.grybauskaite["electionId"], "2014-prezidento")
        self.assertEqual(self.grybauskaite["candidateId"], "dalia-grybauskaite")
        self.assertEqual(self.grybauskaite["candidateName"], "Dalia GRYBAUSKAITĖ")
        # No listing-only facts, but the results join adds the block: the
        # final-results page names her elected in the second round.
        self.assertEqual(
            self.grybauskaite["kandidatavimas"],
            {
                "vrkCandidateId": "70873",
                "isrinktas": True,
                "isrinktasKaip": "prezidentas",
                "rezultatuSaltinis": "https://www.vrk.lt/statiniai/puslapiai/2014_prezidento_rinkimai/output_lt/rinkimu_diena/rezultatai_isankstiniai2.html",
                "rezultatuTuras": 2,
            },
        )
        self.assertEqual(self.balcytis["kandidatavimas"], {"vrkCandidateId": "70874", "isrinktas": False})
        self.assertEqual(self.grybauskaite_stats["anomalies"], [])

    def test_normalized_section_order_includes_trustees(self) -> None:
        self.assertEqual(
            list(self.grybauskaite["normalized"].keys()),
            [
                "profilis",
                "anketa",
                "biografija",
                "turto-ir-pajamu-deklaracijos",
                "privaciu-interesu-deklaracija",
                "patiketiniai",
                "politines-kampanijos-dalyvio-duomenys",
                "kita",
            ],
        )

    def test_profile_card(self) -> None:
        profilis = self.grybauskaite["normalized"]["profilis"]
        self.assertEqual(profilis["vardas-pavarde"], "DALIA GRYBAUSKAITĖ")
        self.assertIsNone(profilis["pastaba"])
        self.assertEqual(
            profilis["nuotrauka"],
            "https://www.vrk.lt/statiniai/puslapiai/rinkimai/424_lt"
            "/Kandidatai/Kandidatas70873/Kandidato70873Foto.jpg",
        )
        # Presidential candidates are self-nominated: no Apygarda, no Iškėlė,
        # only the campaign participant link — which VRK published under the
        # campaign's own election id (423), not the candidate pages' 424.
        self.assertEqual(
            list(profilis["kita"].keys()),
            ["savarankisko-politines-kampanijos-dalyvio-duomenys"],
        )
        self.assertEqual(
            profilis["kita"]["savarankisko-politines-kampanijos-dalyvio-duomenys"]["nuorodos"],
            [
                "https://www.vrk.lt/statiniai/puslapiai/rinkimai/423_lt"
                "/PolitiniuKampanijuFinansavimas/Dalyvis6489/Dalyvio6489Izdininkas.html"
            ],
        )

    def test_presidential_question_mapping(self) -> None:
        anketa = self.grybauskaite["normalized"]["anketa"]
        self.assertEqual(
            list(anketa.keys()),
            [
                "gimimo-data",
                "adresas",
                "pareiskimai",
                "gimimo-vieta",
                "tautybe",
                "issilavinimas",
                "pedagoginis-vardas",
                "uzsienio-kalbos",
                "politine-organizacija",
                "pagrindine-darboviete",
                "visuomenine-veikla",
                "pomegiai",
                "seimine-padetis",
                "sutuoktinio-vardas-pavarde",
                "vaiku-vardai-pavardes",
                "kita-apie-save",
            ],
        )
        self.assertEqual(anketa["gimimo-data"], "1956-03-01")
        self.assertEqual(anketa["adresas"], "Vilnius")
        self.assertEqual(
            anketa["pareiskimai"],
            {
                "ar-esate-pilietis-pagal-kilme": "Taip",
                "ar-gyvenate-lietuvoje-trejus-metus": "Taip",
                "ar-galite-buti-renkamas-seimo-nariu": "Taip",
                "ar-nebaigta-teismo-paskirta-bausme": "Neturiu",
                "ar-atliekate-karo-tarnyba": "Nesu",
                "ar-turite-kitos-valstybes-pilietybe": "Neturiu",
                "ar-susijes-priesaika-uzsienio-valstybei": "Nesu",
            },
        )
        # Birthplace, nationality and education shift down to Q9-Q11 after
        # the seven eligibility questions.
        self.assertEqual(anketa["gimimo-vieta"], "Vilnius")
        self.assertEqual(anketa["tautybe"], "lietuvė")
        self.assertEqual(
            anketa["issilavinimas"]["irasai"],
            [
                {
                    "issilavinimas": "Speciali programa vadovams",
                    "mokymo-istaigos-pavadinimas": "Džordžtauno universitetas JAV",
                    "specialybe": "Speciali programa vadovams",
                    "baigimo-metai": "1992",
                },
                {
                    "issilavinimas": "Aukštasis",
                    "mokymo-istaigos-pavadinimas": "Leningrado universitetas",
                    "specialybe": "Ekonomistė",
                    "baigimo-metai": "1983",
                },
            ],
        )
        self.assertEqual(anketa["pedagoginis-vardas"], "Daktarė, socialinių mokslų (ekonomika)")
        self.assertEqual(anketa["uzsienio-kalbos"], ["anglų", "rusų", "lenkų", "prancūzų"])
        self.assertEqual(anketa["pagrindine-darboviete"], "LR Prezidento kanceliarija, LR Prezidentė")
        # "Nenurodė"/"nenurodė"/"-" are the page's own blanks.
        self.assertIsNone(anketa["visuomenine-veikla"])
        self.assertIsNone(anketa["seimine-padetis"])
        self.assertIsNone(anketa["sutuoktinio-vardas-pavarde"])
        self.assertIsNone(anketa["vaiku-vardai-pavardes"])

        self.assertEqual(self.paulauskas["normalized"]["anketa"]["pedagoginis-vardas"], "MRU garbės daktaras")
        self.assertEqual(self.paulauskas["normalized"]["anketa"]["sutuoktinio-vardas-pavarde"], "Jolanta")

    def test_mapping_does_not_read_the_seimo_question_numbers(self) -> None:
        # On a presidential page Q8.1 is citizenship by origin, Q9 is the
        # birthplace and Q10 the nationality; a Seimo-numbered normalizer
        # would put "lietuvė" into the birthplace. Guard the mapping on
        # synthetic rows so a mutation back to the Seimo numbers fails.
        rows = [
            {"questionNumber": "8.1", "prompt": "8.1 Ar esate pilietis pagal kilmę?", "answer": "Taip"},
            {"questionNumber": "8.4", "prompt": "8.4 Ar turite nebaigtą bausmę?", "answer": "Neturiu"},
            {"questionNumber": "9", "prompt": "9. Gimimo vieta", "answer": "Kaunas"},
            {"questionNumber": "10", "prompt": "10. Tautybė", "answer": "lietuvis"},
            {"questionNumber": "11", "prompt": "11. Išsilavinimas:", "answer": []},
        ]
        normalized = normalize_presidential_anketa_rows(rows)
        self.assertEqual(normalized["pareiskimai"]["ar-esate-pilietis-pagal-kilme"], "Taip")
        self.assertEqual(normalized["pareiskimai"]["ar-nebaigta-teismo-paskirta-bausme"], "Neturiu")
        self.assertEqual(normalized["gimimo-vieta"], "Kaunas")
        self.assertEqual(normalized["tautybe"], "lietuvis")
        self.assertNotIn("anksciau-isrinktas", normalized)

    def test_declarations_use_the_2014_gpm308_wording(self) -> None:
        turto = self.grybauskaite["normalized"]["turto-ir-pajamu-deklaracijos"]
        # The income row cites "…14, 20 laukelių … V13 laukelių suma" here,
        # where the 2015 pages cite "…14, 22 … V13 laukelio"; both resolve.
        self.assertEqual(turto["gautos-pajamos"], 388195.16)
        self.assertEqual(turto["sumoketas-pajamu-mokestis"], 44550)
        self.assertEqual(turto["privalomas-registruoti-turtas"], 428792)
        self.assertEqual(turto["valiuta"], "Lt")
        # "0,00 Lt" is a declared zero, not a blank.
        self.assertEqual(
            self.balcytis["normalized"]["turto-ir-pajamu-deklaracijos"]["sumoketas-pajamu-mokestis"], 0
        )

    def test_trustees_tab(self) -> None:
        trustees = self.grybauskaite["normalized"]["patiketiniai"]
        self.assertEqual(len(trustees), 7)
        self.assertEqual(trustees[0], {"numeris": 1, "vardas-pavarde": "GAJA BARTUSEVIČIŪTĖ"})
        self.assertEqual(trustees[-1], {"numeris": 7, "vardas-pavarde": "JOLANTA ŽUTAUTIENĖ"})
        self.assertEqual(len(self.paulauskas["normalized"]["patiketiniai"]), 90)
        # A "Duomenų nėra" trustees page is an empty list, not a missing key.
        self.assertEqual(self.balcytis["normalized"]["patiketiniai"], [])
        self.assertIn("patiketiniai", self.balcytis["rawData"])

    def test_campaign_participant(self) -> None:
        campaigns = self.grybauskaite["normalized"]["politines-kampanijos-dalyvio-duomenys"]
        self.assertEqual(len(campaigns), 1)
        campaign = campaigns[0]
        self.assertEqual(campaign["statusas"], "Savarankiškas")
        self.assertEqual(campaign["izdininkas"]["vardas-pavarde"], "JOLANTA ŽUTAUTIENĖ")
        self.assertEqual(
            set(campaign["aukos-pagal-sekcija"]), {"gautos-ir-priimtos-aukos", "nepriimtinos-aukos"}
        )
        self.assertEqual(len(campaign["sutartys"]), 23)
        self.assertEqual(len(campaign["finansavimo-ataskaitos"]), 1)

    def test_kita_tab_carries_the_program_pdf_when_published(self) -> None:
        self.assertEqual(self.grybauskaite["normalized"]["kita"], {"tekstai": ["Duomenų nėra"], "nuorodos": []})
        kita = self.balcytis["normalized"]["kita"]
        self.assertEqual(kita["tekstai"], ["Kandidato programa"])
        self.assertEqual(len(kita["nuorodos"]), 1)
        self.assertTrue(kita["nuorodos"][0].endswith(".pdf"))


if __name__ == "__main__":
    unittest.main()
