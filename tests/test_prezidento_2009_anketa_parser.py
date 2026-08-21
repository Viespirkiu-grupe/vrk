import json
import tempfile
import unittest
from pathlib import Path

from scraper.elections.prezidento_2009.anketa_parser import (
    normalize_presidential_anketa_rows,
    parse_anketa_sample,
)
from scraper.elections.prezidento_2009.candidate_samples import EXPECTED_TABS, UNPUBLISHED_TABS
from scraper.elections.prezidento_2009.results import RESULTS_PAGE, RESULTS_TREE
from scraper.elections.prezidento_2009.sitemap import (
    ELECTION_ID,
    LISTING_URL,
    build_sitemap_from_sample,
)


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


class Prezidento2009SitemapTests(unittest.TestCase):
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
        self.assertEqual(payload["electionId"], "2009-prezidento")
        self.assertEqual(payload["sourceUrl"], LISTING_URL)
        by_id = {entry["candidateId"]: entry for entry in payload["entries"]}
        self.assertEqual(
            set(by_id),
            {
                "algirdas-butkevicius",
                "loreta-grauziniene",
                "dalia-grybauskaite",
                "ceslovas-jezerskas",
                "valentinas-mazuronis",
                "kazimira-danute-prunskiene",
                "valdemar-tomasevski",
            },
        )
        self.assertEqual(by_id["kazimira-danute-prunskiene"]["candidateName"], "Kazimira Danutė PRUNSKIENĖ")
        self.assertTrue(
            by_id["dalia-grybauskaite"]["url"].endswith("403_lt/Kandidatai/Kandidatas24900/Kandidato24900Anketa.html")
        )


class Prezidento2009ResultsTests(unittest.TestCase):
    def test_results_come_from_the_first_round_vote_table(self) -> None:
        # Decided in the first round, so the walked page is the nationwide
        # vote table, not 2014's second-round page.
        self.assertEqual(RESULTS_TREE, "2009_prezidento_rinkimai")
        self.assertEqual(RESULTS_PAGE, "rezultatai_vienmand_apygardose/rezultatai_vienmand_apygardose1turas.html")
        payload = json.loads((SITEMAPS / f"{ELECTION_ID}.results.json").read_text(encoding="utf-8"))
        self.assertEqual(
            payload["stats"], {"winnerName": "Dalia GRYBAUSKAITĖ", "winnersResolved": 1, "unresolved": 0}
        )
        self.assertEqual(list(payload["elected"]), ["24900"])
        self.assertEqual(payload["elected"]["24900"]["round"], 1)


class Prezidento2009AnketaParserTests(unittest.TestCase):
    def setUp(self) -> None:
        self.grybauskaite, self.grybauskaite_stats = _parse("dalia-grybauskaite")
        self.butkevicius, _ = _parse("algirdas-butkevicius")
        self.jezerskas, _ = _parse("ceslovas-jezerskas")

    def test_trustees_tab_is_linked_but_unpublished(self) -> None:
        # The tab link is on every page; the file behind it is a 404 for all
        # seven candidates, so it is neither expected nor fetched.
        self.assertEqual(
            EXPECTED_TABS,
            {"anketa", "biografija", "turto-ir-pajamu-deklaracijos", "interesu-deklaracija", "kita"},
        )
        self.assertEqual(UNPUBLISHED_TABS, {"patiketiniai"})
        index = json.loads((SAMPLES_ROOT / "dalia-grybauskaite" / "index.json").read_text(encoding="utf-8"))
        self.assertEqual(index["missingExpectedTabs"], [])
        self.assertEqual(index["anomalies"], [])
        self.assertEqual(
            index["unpublishedTabs"],
            [
                {
                    "label": "Patikėtiniai",
                    "slug": "patiketiniai",
                    "url": "https://www.vrk.lt/statiniai/puslapiai/rinkimai/403_lt"
                    "/Kandidatai/Kandidatas24900/Kandidato24900Patiketiniai.html",
                }
            ],
        )
        self.assertNotIn("patiketiniai", self.grybauskaite["normalized"])
        self.assertNotIn("patiketiniai", self.grybauskaite["rawData"])

    def test_top_level_fields_and_elected_join(self) -> None:
        self.assertEqual(self.grybauskaite["electionId"], "2009-prezidento")
        self.assertEqual(self.grybauskaite["candidateId"], "dalia-grybauskaite")
        self.assertEqual(self.grybauskaite["candidateName"], "Dalia GRYBAUSKAITĖ")
        self.assertEqual(
            self.grybauskaite["kandidatavimas"],
            {
                "vrkCandidateId": "24900",
                "isrinktas": True,
                "isrinktasKaip": "prezidentas",
                "rezultatuSaltinis": "https://www.vrk.lt/statiniai/puslapiai/2009_prezidento_rinkimai"
                "/output_lt/rezultatai_vienmand_apygardose/rezultatai_vienmand_apygardose1turas.html",
                "rezultatuTuras": 1,
            },
        )
        self.assertEqual(self.butkevicius["kandidatavimas"], {"vrkCandidateId": "24890", "isrinktas": False})
        self.assertEqual(self.grybauskaite_stats["anomalies"], [])

    def test_normalized_section_order_has_no_trustees(self) -> None:
        self.assertEqual(
            list(self.grybauskaite["normalized"].keys()),
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

    def test_profile_card_carries_the_campaign_website(self) -> None:
        profilis = self.grybauskaite["normalized"]["profilis"]
        self.assertEqual(profilis["vardas-pavarde"], "DALIA GRYBAUSKAITĖ")
        self.assertEqual(
            profilis["nuotrauka"],
            "https://www.vrk.lt/statiniai/puslapiai/rinkimai/403_lt"
            "/Kandidatai/Kandidatas24900/Kandidato24900Foto.jpg",
        )
        # Self-nominated, so no Apygarda/Iškėlė; the card links the campaign
        # participant page (under the same election id here, unlike 2014)
        # and — new to this election — the candidate's own campaign site,
        # keyed by the link text since the card gives it no label.
        self.assertEqual(
            list(profilis["kita"].keys()),
            ["savarankisko-politines-kampanijos-dalyvio-duomenys", "www-grybauskaite2009-lt"],
        )
        self.assertEqual(
            profilis["kita"]["savarankisko-politines-kampanijos-dalyvio-duomenys"]["nuorodos"],
            [
                "https://www.vrk.lt/statiniai/puslapiai/rinkimai/403_lt"
                "/PolitiniuKampanijuFinansavimas/Dalyvis3984/Dalyvio3984Izdininkas.html"
            ],
        )
        self.assertEqual(
            profilis["kita"]["www-grybauskaite2009-lt"],
            {"pavadinimas": "www.grybauskaite2009.lt", "reiksme": None, "nuorodos": ["http://www.grybauskaite2009.lt"]},
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
        self.assertEqual(anketa["gimimo-data"], "1956-03-01")
        self.assertEqual(anketa["adresas"], "Vilnius")
        # Four 2 str. questions, then the 3 str. lustration question as Q9
        # under the corpus-wide key for it.
        self.assertEqual(
            anketa["pareiskimai"],
            {
                "ar-nebaigta-teismo-paskirta-bausme": "Neturiu",
                "ar-atliekate-karo-tarnyba": "Nesu",
                "ar-turite-kitos-valstybes-pilietybe": "Neturiu",
                "ar-susijes-priesaika-uzsienio-valstybei": "Nesu",
                "ar-bendradarbiavote-su-uzsienio-tarnybomis": "Ne",
            },
        )
        # Birthplace, nationality and education at Q10-Q12.
        self.assertEqual(anketa["gimimo-vieta"], "Vilnius")
        self.assertEqual(anketa["tautybe"], "lietuvė")
        self.assertEqual(
            anketa["issilavinimas"]["irasai"],
            [
                {
                    "issilavinimas": "Aukštasis",
                    "mokymo-istaigos-pavadinimas": "Džordžtauno universitetas JAV, spec. programa vadovams",
                    "specialybe": None,
                    "baigimo-metai": "1991",
                },
                {
                    "issilavinimas": "Aukštasis",
                    "mokymo-istaigos-pavadinimas": "Leningrado universitetas",
                    "specialybe": "Ekonomistė, politinės ekonomijos dėstytoja",
                    "baigimo-metai": "1983",
                },
            ],
        )
        # The degree line asks for "mokslo laipsnį" only, and is on the
        # page only when answered.
        self.assertEqual(anketa["mokslo-laipsnis"], "socialinių mokslų daktarės vardas, 1988 m.")
        self.assertIsNone(anketa["pedagoginis-vardas"])
        self.assertIsNone(self.butkevicius["normalized"]["anketa"]["mokslo-laipsnis"])
        self.assertEqual(anketa["uzsienio-kalbos"], ["anglų", "lenkų", "rusų", "prancūzų"])
        self.assertEqual(anketa["politine-organizacija"], "1979-1988 KP narė, nuo 1990 - nepartinė")
        self.assertEqual(anketa["pagrindine-darboviete"], "Europos Komisija, EK narė, atsakinga už ES Biudžetą")
        # "Nenurodė"/"nenurodė" are the page's own blanks; Q20 and the
        # spouse line are absent from her page altogether.
        self.assertIsNone(anketa["visuomenine-veikla"])
        self.assertIsNone(anketa["seimine-padetis"])
        self.assertIsNone(anketa["sutuoktinio-vardas-pavarde"])
        self.assertIsNone(anketa["vaiku-vardai-pavardes"])
        self.assertEqual(self.butkevicius["normalized"]["anketa"]["sutuoktinio-vardas-pavarde"], "Janina")
        self.assertEqual(self.butkevicius["normalized"]["anketa"]["vaiku-vardai-pavardes"], "Indrė")

    def test_prior_mandates_table_is_asked_here(self) -> None:
        # Unlike the 2014 presidential form, Q15 is on the page — for the
        # five candidates with something to list.
        self.assertEqual(
            self.butkevicius["normalized"]["anketa"]["anksciau-isrinktas"]["irasai"][-1],
            {"institucijos-pavadinimas-pareigos": "Lietuvos Respublikos Seimas, Seimo narys", "laikotarpis": "2008 -"},
        )
        self.assertEqual(len(self.butkevicius["normalized"]["anketa"]["anksciau-isrinktas"]["irasai"]), 6)
        self.assertEqual(self.grybauskaite["normalized"]["anketa"]["anksciau-isrinktas"]["irasai"], [])
        self.assertEqual(self.jezerskas["normalized"]["anketa"]["anksciau-isrinktas"]["irasai"], [])
        # A page-level blank birthplace ("nenurodė") stays null.
        self.assertIsNone(self.jezerskas["normalized"]["anketa"]["gimimo-vieta"])
        self.assertEqual(self.jezerskas["normalized"]["anketa"]["seimine-padetis"], "našlys")

    def test_mapping_does_not_read_the_2014_question_numbers(self) -> None:
        # On a 2009 page Q8.1 is the unserved sentence, Q9 the lustration
        # question, Q10 the birthplace; the 2014 normalizer would put the
        # birthplace into the nationality. Guard on synthetic rows.
        rows = [
            {"questionNumber": "8.1", "prompt": "8.1 Ar turite nebaigtą bausmę?", "answer": "Neturiu"},
            {"questionNumber": "9", "prompt": "9. Ar dirbote SSRS ... KGB?", "answer": "Ne"},
            {"questionNumber": "10", "prompt": "10. Gimimo vieta", "answer": "Kaunas"},
            {"questionNumber": "11", "prompt": "11. Tautybė", "answer": "lietuvis"},
            {"questionNumber": "12", "prompt": "12. Išsilavinimas:", "answer": []},
        ]
        normalized = normalize_presidential_anketa_rows(rows)
        self.assertEqual(normalized["pareiskimai"]["ar-nebaigta-teismo-paskirta-bausme"], "Neturiu")
        self.assertEqual(normalized["pareiskimai"]["ar-bendradarbiavote-su-uzsienio-tarnybomis"], "Ne")
        self.assertNotIn("ar-esate-pilietis-pagal-kilme", normalized["pareiskimai"])
        self.assertEqual(normalized["gimimo-vieta"], "Kaunas")
        self.assertEqual(normalized["tautybe"], "lietuvis")
        self.assertIn("anksciau-isrinktas", normalized)
        # The title half of the degree line is mapped but on no 2009
        # presidential page.
        self.assertIsNone(normalized["pedagoginis-vardas"])

    def test_declarations_use_the_gpm305_form(self) -> None:
        turto = self.grybauskaite["normalized"]["turto-ir-pajamu-deklaracijos"]
        self.assertEqual(turto["privalomas-registruoti-turtas"], 428792)
        self.assertEqual(turto["pinigines-lesos"], 925360)
        self.assertEqual(turto["gautos-pajamos"], 694248)
        # "0,00 Lt" is a declared zero, not a blank.
        self.assertEqual(turto["sumoketas-pajamu-mokestis"], 0)
        self.assertEqual(turto["valiuta"], "Lt")
        self.assertEqual(self.butkevicius["normalized"]["turto-ir-pajamu-deklaracijos"]["gautos-pajamos"], 264869)

    def test_interest_declaration_is_the_roman_numbered_form(self) -> None:
        # Pre-ID001x: sections II, IV and VII, and a value-band code where
        # the later form has sums.
        interesai = self.grybauskaite["normalized"]["privaciu-interesu-deklaracija"]
        self.assertEqual(
            list(interesai.keys()),
            [
                "deklaruojantis-asmuo",
                "darboviete-ir-pareigos-valstybineje-tarnyboje",
                "visos-darbovietes-ir-pareigos",
                "deklaruojancio-asmens-sutuoktinis-partneris",
                "vii-sandoriai",
            ],
        )
        self.assertEqual(len(interesai["vii-sandoriai"]), 7)
        self.assertEqual(
            interesai["vii-sandoriai"][4],
            {
                "tipas": "Kiti sandoriai",
                "sandorio-objektas-ai": "INDĖLIS",
                "sandorio-sudarymo-data": "2008-07-01",
                "asmens-atliktas-veiksmas-pirkimas-pardavimas-paskolos-gavimas-ar-kt": "INDĖLIO PADĖJIMAS",
                "fizinio-ar-juridinio-asmens-sandorio-salies-iu-vardas-pavarde-ar-pavadinimas": "AB SEB BANKAS",
                "sandorio-vertes-litais-kodas": "012",
                "suma-skaiciais": None,
                "suma-zodziais": None,
            },
        )
        self.assertEqual(len(self.butkevicius["normalized"]["privaciu-interesu-deklaracija"]["vii-sandoriai"]), 22)
        self.assertIn(
            "iv-naryste-pareigos-imonese-istaigose-asociacijose-ar-fonduose",
            self.butkevicius["normalized"]["privaciu-interesu-deklaracija"],
        )

    def test_campaign_participant(self) -> None:
        campaigns = self.grybauskaite["normalized"]["politines-kampanijos-dalyvio-duomenys"]
        self.assertEqual(len(campaigns), 1)
        campaign = campaigns[0]
        self.assertEqual(campaign["statusas"], "Savarankiškas")
        self.assertEqual(campaign["kontaktai"], {"telefonas-pasiteirauti": "+370 5 2619442", "el-pastas": "info@grybauskaite2009.lt"})
        self.assertEqual(campaign["izdininkas"]["vardas-pavarde"], "JOLANTA ŽUTAUTIENĖ")
        # A company auditor, labelled "Pavadinimas"/"Kodas" on these pages.
        self.assertEqual(
            campaign["auditorius"],
            {
                "vardas-pavarde": None,
                "telefonas": "852762030",
                "el-pastas": "info@ekonauda.lt",
                "imones-pavadinimas": 'Uždaroji akcinė bendrovė "EKONOMINĖ NAUDA"',
                "imones-kodas": "125515863",
            },
        )
        # The 2009 donor list: one "Aukotojų sąrašas" table headed by
        # <td><strong> cells, litas amounts, a full-width totals row.
        self.assertEqual(list(campaign["aukos-pagal-sekcija"]), ["aukotoju-sarasas"])
        aukos = campaign["aukos-pagal-sekcija"]["aukotoju-sarasas"]
        self.assertEqual(aukos["title"], "Aukotojų sąrašas")
        self.assertEqual(len(aukos["records"]), 141)
        self.assertEqual(
            aukos["records"][0],
            {"rowNumber": "1", "donor": "DALIA GRYBAUSKAITĖ", "municipality": "Vilniaus miesto", "amountLt": 11600, "date": "2009-02-26"},
        )
        self.assertEqual(aukos["suvestine"], [{"label": "Iš viso", "amountEur": None, "amountLt": 507341.16, "note": None}])
        self.assertAlmostEqual(sum(record["amountLt"] for record in aukos["records"]), 507341.16, places=1)
        # An unacceptable donation is flagged inline after the donor's name;
        # the flag becomes the notes column the later eras have.
        flagged = [record for record in aukos["records"] if record.get("notes")]
        self.assertEqual(len(flagged), 8)
        self.assertEqual(flagged[0]["donor"], "RAJINDER KUMAR CHAUDHARY")
        self.assertEqual(flagged[0]["notes"], "nepriimtina auka")
        self.assertEqual({record["notes"] for record in flagged}, {"nepriimtina auka", "nepriintina auka", "auka nepriimtina"})
        # Four reports with a kind instead of a status; no contracts tab content.
        self.assertEqual(len(campaign["finansavimo-ataskaitos"]), 4)
        self.assertEqual(campaign["finansavimo-ataskaitos"][0]["reportType"], "Pradinė")
        self.assertEqual(campaign["finansavimo-ataskaitos"][1]["reportType"], "Galutinė")
        self.assertIsNone(campaign["finansavimo-ataskaitos"][0]["status"])
        self.assertEqual(len(campaign["finansavimo-ataskaitos"][0]["reportUrls"]), 1)
        self.assertEqual(campaign["sutartys"], [])
        # A candidate without an auditor: the page has no auditor table.
        self.assertEqual(
            self.jezerskas["normalized"]["politines-kampanijos-dalyvio-duomenys"][0]["auditorius"],
            {"vardas-pavarde": None, "telefonas": None, "el-pastas": None, "imones-pavadinimas": None, "imones-kodas": None},
        )
        self.assertEqual(
            len(self.jezerskas["normalized"]["politines-kampanijos-dalyvio-duomenys"][0]["aukos-pagal-sekcija"]["aukotoju-sarasas"]["records"]),
            3,
        )

    def test_kita_tab_carries_the_filed_pdfs(self) -> None:
        kita = self.grybauskaite["normalized"]["kita"]
        self.assertEqual(kita["tekstai"], ["Duomenų anketa apie ryšius su užsienio specialiosiomis tarnybomis (struktūromis)"])
        self.assertEqual(len(kita["nuorodos"]), 1)
        self.assertTrue(kita["nuorodos"][0].endswith(".pdf"))
        self.assertEqual(
            self.butkevicius["normalized"]["kita"]["tekstai"],
            [
                "Duomenų anketa apie ryšius su užsienio specialiosiomis tarnybomis (struktūromis)",
                "Kandidato sveikatos pažyma",
                "Partijos sprendimas dėl kandidato į Lietuvos Respublikos Prezidentus iškėlimo",
            ],
        )


if __name__ == "__main__":
    unittest.main()
