import json
import tempfile
import unittest
from pathlib import Path

from scraper.elections.seimo_zirmunu_2015.anketa_parser import parse_anketa_sample


REPO_ROOT = Path(__file__).resolve().parents[1]
SAMPLES_ROOT = REPO_ROOT / "samples" / "html" / "2015-kovo-1-seimo-zirmunai"


def _parse(candidate_id: str) -> dict:
    with tempfile.TemporaryDirectory() as tmp:
        output_path, _ = parse_anketa_sample(
            candidate_id=candidate_id,
            samples_root=SAMPLES_ROOT,
            output_root=Path(tmp),
        )
        return json.loads(output_path.read_text(encoding="utf-8"))


class SeimoZirmunu2015AnketaParserTests(unittest.TestCase):
    def setUp(self) -> None:
        self.morkunaite = _parse("radvile-morkunaite-mikuleniene")
        self.gustainis = _parse("sarunas-gustainis")
        self.raslanas = _parse("algirdas-raslanas")
        self.andruskevic = _parse("anzela-andruskevic")
        self.vagnorius = _parse("gediminas-vagnorius")

    def test_top_level_fields(self) -> None:
        self.assertEqual(self.gustainis["electionId"], "2015-kovo-1-seimo-zirmunai")
        self.assertEqual(self.gustainis["candidateId"], "sarunas-gustainis")
        self.assertEqual(self.gustainis["candidateName"], "Šarūnas GUSTAINIS")
        self.assertTrue(
            self.gustainis["source"]["candidateSourceUrl"].endswith(
                "Kandidatas87277/Kandidato87277Anketa.html"
            )
        )

    def test_normalized_section_order(self) -> None:
        self.assertEqual(
            list(self.morkunaite["normalized"].keys()),
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

    def test_profile_card_fields(self) -> None:
        profilis = self.morkunaite["normalized"]["profilis"]
        self.assertEqual(profilis["vardas-pavarde"], "Radvilė Morkūnaitė-Mikulėnienė")
        # No 2015 page marks the winner anywhere, so the note is always empty.
        self.assertIsNone(profilis["pastaba"])
        # The photo is an external JPG on vrk.lt, not a base64 payload, so the
        # reference stays a URL like the 2020+ eras.
        self.assertEqual(
            profilis["nuotrauka"],
            "https://www.vrk.lt/statiniai/puslapiai/rinkimai/448_lt"
            "/Kandidatai/Kandidatas87326/Kandidato87326Foto.jpg",
        )

        kita = profilis["kita"]
        self.assertEqual(kita["apygarda"]["reiksme"], "Žirmūnų (Nr.4)")
        self.assertEqual(
            kita["iskele"]["reiksme"], "Tėvynės sąjunga - Lietuvos krikščionys demokratai"
        )
        # The campaign participant link is a standalone anchor whose label
        # carries the participant type.
        self.assertIn("savarankisko-politines-kampanijos-dalyvio-duomenys", kita)
        self.assertIn(
            "atstovaujamojo-politines-kampanijos-dalyvio-duomenys",
            self.raslanas["normalized"]["profilis"]["kita"],
        )

    def test_anketa_top_level_keys(self) -> None:
        self.assertEqual(
            list(self.morkunaite["normalized"]["anketa"].keys()),
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

    def test_anketa_pareiskimai(self) -> None:
        # The 2015 Seimo set stops at Q9.2 — the 9.3.x follow-ups are a later
        # era's addition.
        pareiskimai = self.morkunaite["normalized"]["anketa"]["pareiskimai"]
        self.assertEqual(
            list(pareiskimai.keys()),
            [
                "ar-nebaigta-teismo-paskirta-bausme",
                "ar-atliekate-karo-tarnyba",
                "ar-turite-kitos-valstybes-pilietybe",
                "ar-susijes-priesaika-uzsienio-valstybei",
                "ar-bendradarbiavote-su-uzsienio-tarnybomis",
                "ar-buvote-pripazintas-kaltu",
            ],
        )
        self.assertTrue(all(value == "Ne" for value in pareiskimai.values()))

    def test_anketa_core_fields(self) -> None:
        anketa = self.morkunaite["normalized"]["anketa"]
        self.assertEqual(anketa["gimimo-data"], "1984-01-02")
        self.assertEqual(anketa["adresas"], "Vilnius")
        self.assertEqual(anketa["gimimo-vieta"], "Kaunas")
        self.assertEqual(anketa["tautybe"], "lietuvė")
        self.assertEqual(
            anketa["uzsienio-kalbos"], ["anglų", "rusų", "vokiečių", "prancūzų", "italų"]
        )
        self.assertEqual(anketa["seimine-padetis"], "ištekėjusi")
        self.assertEqual(anketa["sutuoktinio-vardas-pavarde"], "Mindaugas Mikulėnas")

    def test_inline_record_tables_are_self_labeled(self) -> None:
        # Q12/Q15 live inside nested tables whose first row is the question
        # itself, so the tables parse into their own question rows.
        anketa = self.morkunaite["normalized"]["anketa"]
        self.assertEqual(len(anketa["issilavinimas"]["irasai"]), 3)
        self.assertEqual(
            anketa["issilavinimas"]["irasai"][0],
            {
                "issilavinimas": "Magistras",
                "mokymo-istaigos-pavadinimas": "Vilniaus dailės akademija",
                "specialybe": "Kultūros vadyba ir politika",
                "baigimo-metai": "2008",
            },
        )
        self.assertEqual(
            anketa["anksciau-isrinktas"]["irasai"],
            [
                {
                    "institucijos-pavadinimas-pareigos": "Europos Parlamento narė",
                    "laikotarpis": "2009 - 2014",
                }
            ],
        )
        # A candidate who declared no prior mandates has no Q15 table at all.
        self.assertEqual(self.gustainis["normalized"]["anketa"]["anksciau-isrinktas"]["irasai"], [])
        self.assertEqual(len(self.vagnorius["normalized"]["anketa"]["anksciau-isrinktas"]["irasai"]), 4)

    def test_comma_only_workplace_is_an_artifact(self) -> None:
        # The template joins workplace and position with a comma, so an empty
        # pair renders as a bare "," that must not survive as an answer.
        self.assertIsNone(self.morkunaite["normalized"]["anketa"]["pagrindine-darboviete"])

    def test_declared_none_survives_but_nenurode_does_not(self) -> None:
        self.assertIsNone(self.raslanas["normalized"]["anketa"]["seimine-padetis"])
        self.assertEqual(self.andruskevic["normalized"]["anketa"]["vaiku-vardai-pavardes"], "Neturiu")

    def test_q21_present_only_when_answered(self) -> None:
        self.assertIsNone(self.morkunaite["normalized"]["anketa"]["kita-apie-save"])
        self.assertTrue(
            self.vagnorius["normalized"]["anketa"]["kita-apie-save"].startswith(
                "Buvau paskirtas LR Ministru Pirmininku"
            )
        )

    def test_turto_ir_pajamu_amounts_are_litas(self) -> None:
        turtas = self.morkunaite["normalized"]["turto-ir-pajamu-deklaracijos"]
        self.assertEqual(turtas["privalomas-registruoti-turtas"], 363167)
        self.assertEqual(turtas["pinigines-lesos"], 10608)
        self.assertEqual(turtas["gautos-pajamos"], 331678)
        self.assertEqual(turtas["sumoketas-pajamu-mokestis"], 0)
        self.assertEqual(turtas["valiuta"], "Lt")
        self.assertIn("nuo 2013-01-01 iki 2013-12-31", turtas["pastaba"])

    def test_privaciu_interesu_sections(self) -> None:
        privaciu = self.morkunaite["normalized"]["privaciu-interesu-deklaracija"]
        self.assertEqual(privaciu["deklaruojantis-asmuo"], "RADVILĖ MORKŪNAITĖ-MIKULĖNIENĖ")
        # Unlike the 2016-era Seimo family, the 2015 pages publish the spouse
        # block and it is retained.
        spouse = privaciu["deklaruojancio-asmens-sutuoktinis-sugyventinis-partneris"]
        self.assertEqual(spouse["vardas"], "MINDAUGAS")
        self.assertEqual(spouse["pavarde"], "MIKULĖNAS")
        self.assertEqual(
            privaciu["id001j"][0]["juridinio-asmens-pavadinimas"],
            "KOVŲ UŽ LAISVĘ ATMINIMO ASOCIACIJA NEUŽMIRŠK",
        )

    def test_kita_links_candidate_program_pdf(self) -> None:
        kita = self.morkunaite["normalized"]["kita"]
        self.assertEqual(kita["tekstai"], ["Kandidato programa"])
        self.assertEqual(len(kita["nuorodos"]), 1)
        self.assertTrue(kita["nuorodos"][0].endswith("Kandidato1000000674.pdf"))
        # A candidate without a program has the "Duomenų nėra" text and no link.
        self.assertEqual(
            self.andruskevic["normalized"]["kita"],
            {"tekstai": ["Duomenų nėra"], "nuorodos": []},
        )

    def test_biografija_is_free_text(self) -> None:
        self.assertTrue(
            self.morkunaite["normalized"]["biografija"]["tekstas"].startswith("Gimė 1984 m. Kaune")
        )

    def test_campaign_entry_has_corpus_keys(self) -> None:
        campaigns = self.gustainis["normalized"]["politines-kampanijos-dalyvio-duomenys"]
        self.assertEqual(len(campaigns), 1)
        entry = campaigns[0]
        self.assertEqual(
            list(entry.keys()),
            [
                "statusas",
                "registravimo-data",
                "sprendimo-numeris",
                "kontaktai",
                "izdininkas",
                "auditorius",
                "aukos-pagal-sekcija",
                "finansavimo-ataskaitos",
                "sutartys",
                "sprendimai",
            ],
        )
        self.assertEqual(entry["statusas"], "Savarankiškas")
        # The 2015 participant pages publish neither field.
        self.assertIsNone(entry["registravimo-data"])
        self.assertIsNone(entry["sprendimo-numeris"])
        self.assertEqual(entry["kontaktai"]["el-pastas"], "sarunas@gustainis.lt")
        self.assertEqual(entry["izdininkas"]["vardas-pavarde"], "TATJANA ILJASEVIČIŪTĖ")
        self.assertEqual(entry["auditorius"]["imones-pavadinimas"], 'UAB "LEXIN auditas"')
        # The auditor's reports are a 2015 addition inside the auditorius block.
        self.assertEqual(len(entry["auditorius"]["ataskaitos"]), 2)
        self.assertEqual(entry["auditorius"]["ataskaitos"][0]["type"], "ataskaita")

    def test_campaign_represented_participant_is_a_card(self) -> None:
        entry = self.raslanas["normalized"]["politines-kampanijos-dalyvio-duomenys"][0]
        self.assertEqual(entry["statusas"], "Atstovaujamasis")
        self.assertEqual(entry["izdininkas"], {})
        self.assertEqual(entry["finansavimo-ataskaitos"], [])
        # The card names the party whose campaign covers the candidate.
        self.assertEqual(
            entry["atstovauja"]["pavadinimas"], "LIETUVOS SOCIALDEMOKRATŲ PARTIJA (S)"
        )
        self.assertIn("Dalyvio6717", self.raslanas["rawData"]["politinesKampanijosDalyvioDuomenys"]["campaigns"][0]["campaignUrl"])

    def test_campaign_donations_split_records_from_totals(self) -> None:
        aukos = self.gustainis["normalized"]["politines-kampanijos-dalyvio-duomenys"][0][
            "aukos-pagal-sekcija"
        ]
        self.assertEqual(
            set(aukos.keys()), {"gautos-ir-priimtos-aukos", "nepriimtinos-aukos"}
        )
        accepted = aukos["gautos-ir-priimtos-aukos"]
        self.assertEqual(len(accepted["records"]), 11)
        first = accepted["records"][0]
        self.assertEqual(first["donor"], "MIKAS GUSTAINIS")
        # Dual currency: the euro conversion and the litas original.
        self.assertEqual(first["amountEur"], 2896.2)
        self.assertEqual(first["amountLt"], 10000)
        # The totals block parses into the summary, not into the records.
        totals = {row["label"]: row for row in accepted["suvestine"]}
        self.assertEqual(totals["Iš viso"]["amountEur"], 23726.9)
        rejected = aukos["nepriimtinos-aukos"]["records"]
        self.assertEqual(rejected[0]["notes"], "grąžinta aukotojui 2014-12-23")

    def test_campaign_contracts(self) -> None:
        caplikas = _parse("algis-caplikas")
        sutartys = caplikas["normalized"]["politines-kampanijos-dalyvio-duomenys"][0]["sutartys"]
        self.assertEqual(len(sutartys), 2)
        self.assertEqual(sutartys[1]["counterparty"], 'UAB "Baltijos vaizdinė reklama"')
        self.assertEqual(sutartys[1]["agreementNumber"], "12.14-479")
        self.assertEqual(
            self.gustainis["normalized"]["politines-kampanijos-dalyvio-duomenys"][0]["sutartys"],
            [],
        )

    def test_campaign_financing_reports_link_pdfs(self) -> None:
        reports = self.gustainis["normalized"]["politines-kampanijos-dalyvio-duomenys"][0][
            "finansavimo-ataskaitos"
        ]
        self.assertEqual(len(reports), 1)
        self.assertEqual(reports[0]["approvedDate"], "2015-04-16")
        self.assertEqual(len(reports[0]["reportUrls"]), 1)
        self.assertTrue(reports[0]["reportUrls"][0].endswith(".pdf"))
        self.assertEqual(len(reports[0]["advertisingAppendixUrls"]), 1)


if __name__ == "__main__":
    unittest.main()
