import json
import tempfile
import unittest
from pathlib import Path

from scraper.elections.seimo_2024.anketa_parser import parse_anketa_sample


REPO_ROOT = Path(__file__).resolve().parents[1]
SAMPLES_ROOT = REPO_ROOT / "samples" / "html" / "2024-seimo"


def _parse(candidate_id: str) -> dict:
    with tempfile.TemporaryDirectory() as tmp:
        output_path, _ = parse_anketa_sample(
            candidate_id=candidate_id,
            samples_root=SAMPLES_ROOT,
            output_root=Path(tmp),
        )
        return json.loads(output_path.read_text(encoding="utf-8"))


class Seimo2024AnketaParserTests(unittest.TestCase):
    def setUp(self) -> None:
        self.algirdas = _parse("algirdas-butkevicius")
        self.vilma = _parse("vilma-aasrum")

    def test_top_level_fields(self) -> None:
        self.assertEqual(self.algirdas["electionId"], "2024-seimo")
        self.assertEqual(self.algirdas["candidateId"], "algirdas-butkevicius")
        self.assertEqual(self.algirdas["candidateName"], "Algirdas BUTKEVIČIUS")
        self.assertTrue(
            self.algirdas["source"]["candidateSourceUrl"].endswith("KandidatasAnketa_rkndId-2436053.html")
        )

    def test_normalized_section_order(self) -> None:
        self.assertEqual(
            list(self.algirdas["normalized"].keys()),
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

    def test_subpage_raw_data_not_empty(self) -> None:
        # The 2024 layout renders tab content as direct siblings of
        # ul#tabnav; a regression to the 2016-era "div after tabnav" /
        # "table.tabinc" selectors silently empties all three sections.
        raw = self.algirdas["rawData"]
        self.assertGreater(len(raw["biografija"]["rows"]), 0)
        self.assertGreater(len(raw["turtoIrPajamuDeklaracijos"]["sections"]), 0)
        self.assertGreater(len(raw["privaciuInteresuDeklaracija"]["sections"]), 0)

    def test_profile_card_fields(self) -> None:
        # The 2024 profile card is the table before the tab navigation, with the
        # photo in the outer layout table. Reading it with the 2016-era selectors
        # silently nulls the name and photo and turns the elected note into a
        # stray "kita" entry.
        profilis = self.algirdas["normalized"]["profilis"]
        self.assertEqual(profilis["vardas-pavarde"], "Algirdas BUTKEVIČIUS")
        self.assertIn("kandImg", profilis["nuotrauka"])

        kita = profilis["kita"]
        self.assertEqual(kita["vienmandate-apygarda"]["reiksme"], "Vilkaviškio Nr. 68")
        self.assertEqual(kita["iskele"]["reiksme"], "Demokratų sąjunga „Vardan Lietuvos“")
        self.assertEqual(kita["turas"]["reiksme"], "II")
        self.assertEqual(kita["numeris-sarase"]["reiksme"], "5")
        self.assertEqual(kita["porinkiminis-eiles-numeris"]["reiksme"], "3")

    def test_elected_note_variants(self) -> None:
        self.assertEqual(
            self.algirdas["normalized"]["profilis"]["pastaba"],
            "Išrinktas vienmandatėje Vilkaviškio (Nr. 68) apygardoje II ture",
        )
        self.assertEqual(
            _parse("saulius-skvernelis")["normalized"]["profilis"]["pastaba"],
            "Išrinktas pagal sąrašą",
        )
        # Non-elected candidates carry no note.
        self.assertIsNone(self.vilma["normalized"]["profilis"]["pastaba"])

    def test_anketa_core_fields(self) -> None:
        anketa = self.algirdas["normalized"]["anketa"]
        self.assertEqual(anketa["adresas"], "Vilnius")
        self.assertEqual(anketa["einamos-pareigos"], "Lietuvos Respublikos Seimo narys")

    def test_anketa_party_membership_table(self) -> None:
        irasai = self.algirdas["normalized"]["anketa"]["narystes-politinese-organizacijose"]["irasai"]
        self.assertEqual(len(irasai), 3)
        self.assertEqual(irasai[0]["politine-organizacija"], "Demokratų sąjunga „Vardan Lietuvos“")
        self.assertEqual(irasai[0]["nuo"], "2022")
        self.assertEqual(irasai[0]["iki"], "Iki dabar")
        self.assertEqual(irasai[2]["politine-organizacija"], "Tarybų Sąjungos komunistų partija")

    def test_anketa_pareiskimai_keys(self) -> None:
        # Q9-Q14 carry the Rinkimų kodekso 76 str. declarations and Q15-Q16 the
        # Seimo eligibility questions. Mapping 2016 question numbers onto these
        # pages leaves every declaration null while leaking the answers into
        # unrelated keys, so both the key list and the values are asserted.
        pareiskimai = self.algirdas["normalized"]["anketa"]["pareiskimai"]
        self.assertEqual(
            list(pareiskimai.keys()),
            [
                "ar-kitos-valstybes-institucijos-narys",
                "ar-eina-nesuderinamas-pareigas",
                "ar-bendradarbiavote-su-ssrs-tarnybomis",
                "ar-nebaigta-teismo-paskirta-bausme",
                "ar-buvote-pripazintas-kaltu",
                "ar-veika-dekriminalizuota",
                "ar-buvote-pripazintas-kaltu-uzsienyje",
                "ar-buvote-pripazintas-kaltu-del-politinio-persekiojimo",
                "ar-neteko-mandato-uz-pazeidimus",
                "ar-esate-ar-buvote-kitos-valstybes-pilietis",
                "ar-susijes-priesaika-uzsienio-valstybei",
            ],
        )
        self.assertTrue(all(value == "Ne" for value in pareiskimai.values()))
        self.assertTrue(
            all(
                value is not None
                for value in self.vilma["normalized"]["anketa"]["pareiskimai"].values()
            )
        )

    def test_anketa_conditional_blocks_absent(self) -> None:
        # No sampled candidate answered Q13/Q14 "Taip", so the conditional
        # detail blocks are null / empty but still parsed.
        anketa = self.algirdas["normalized"]["anketa"]
        # Uniform shape: no conviction block means an empty entry list.
        self.assertEqual(anketa["teistumo-detales"], {"irasai": []})
        self.assertIsNone(anketa["mandato-netekimo-detales"])

    def test_biografija_birth_and_marital(self) -> None:
        biografija = self.algirdas["normalized"]["biografija"]
        self.assertEqual(biografija["gimimo-data"], "1958-11-19")
        self.assertEqual(biografija["gimimo-vieta"], "Radviliškio rajonas")
        self.assertEqual(biografija["seimine-padetis"], "Vedęs")

    def test_biografija_education_records_attached_to_question_2(self) -> None:
        irasai = self.algirdas["normalized"]["biografija"]["issilavinimas"]["irasai"]
        self.assertEqual(len(irasai), 3)
        self.assertEqual(irasai[0]["mokymo-istaigos-pavadinimas"], "Vilniaus Gedimino technikos universitetas")
        self.assertEqual(irasai[0]["baigimo-metai"], "2008")

    def test_biografija_work_records_attached_to_question_4(self) -> None:
        irasai = self.algirdas["normalized"]["biografija"]["darbo-patirtis"]["irasai"]
        self.assertEqual(len(irasai), 6)
        self.assertEqual(irasai[0]["darboviete"], "Lietuvos Respublikos Seimas")
        self.assertEqual(irasai[0]["darbo-pradzia"], "1996")
        self.assertEqual(irasai[0]["pareigos"], "Seimo narys")

    def test_biografija_languages_split(self) -> None:
        self.assertEqual(
            self.algirdas["normalized"]["biografija"]["uzsienio-kalbos"],
            ["Anglų (Įgudęs)", "Rusų (Įgudęs)"],
        )

    def test_academic_degree_captured(self) -> None:
        # Q2.1/Q2.2 use the 2024 numbering; the 2016/2020-era mapping
        # ("3.1"/"3.2") would silently null these out.
        biografija = self.algirdas["normalized"]["biografija"]
        self.assertEqual(biografija["mokslo-laipsnis"], "Daktaras")
        self.assertEqual(biografija["pedagoginis-vardas"], "Neturiu")

    def test_biografija_activity_and_hobbies(self) -> None:
        biografija = self.vilma["normalized"]["biografija"]
        self.assertTrue(biografija["visuomenine-veikla"].startswith("Lietuvos valstiečių ir žaliųjų sąjungos"))
        self.assertEqual(biografija["pomegiai"], "Politika")

    def test_turto_amounts(self) -> None:
        turto = self.algirdas["normalized"]["turto-ir-pajamu-deklaracijos"]
        self.assertEqual(turto["privalomas-registruoti-turtas"], 85215)
        self.assertEqual(turto["vertybiniai-popieriai-meno-kuriniai-juvelyriniai-dirbiniai"], 0)
        self.assertEqual(turto["pinigines-lesos"], 76674)
        self.assertEqual(turto["suteiktos-paskolos"], 0)
        self.assertEqual(turto["gautos-paskolos"], 31800)
        self.assertEqual(turto["gautos-pajamos"], 61513.89)
        self.assertEqual(turto["sumoketas-pajamu-mokestis"], 11596.56)

    def test_privaciu_declaration_summary(self) -> None:
        privaciu = self.algirdas["normalized"]["privaciu-interesu-deklaracija"]
        self.assertEqual(privaciu["pateikimo-data"], "2024-07-22")
        self.assertEqual(privaciu["deklaruojantis-asmuo"], "Algirdas BUTKEVIČIUS")
        self.assertEqual(privaciu["sutuoktinis-sugyventinis-ar-partneris"], "Janina BUTKEVIČIENĖ")

    def test_privaciu_workplace_and_legal_tie_records(self) -> None:
        privaciu = self.algirdas["normalized"]["privaciu-interesu-deklaracija"]
        darbovietes = privaciu["deklaruojancio-darbovietes"]
        self.assertEqual(len(darbovietes), 1)
        self.assertEqual(darbovietes[0]["pavadinimas"], "Lietuvos Respublikos Seimo kanceliarija")
        self.assertEqual(darbovietes[0]["pareigos"], "Seimo narys")

        rysiai = privaciu["rysiai-su-juridiniais-asmenimis"]
        self.assertEqual(len(rysiai), 2)
        self.assertEqual(rysiai[1]["juridinio-asmens-pavadinimas"], 'Demokratų sąjunga "Vardan Lietuvos"')
        self.assertEqual(rysiai[1]["rysio-pobudis"], "Narys")

    def test_privaciu_transaction_records(self) -> None:
        sandoriai = self.algirdas["normalized"]["privaciu-interesu-deklaracija"]["rysiai-sudarius-sandorius"]
        self.assertEqual(len(sandoriai), 1)
        self.assertEqual(sandoriai[0]["sandorio-rusis"], "Lizingas")
        self.assertEqual(sandoriai[0]["sudarymo-data"], "2024-06-27")

    def test_privaciu_spouse_workplace_records(self) -> None:
        privaciu = self.vilma["normalized"]["privaciu-interesu-deklaracija"]
        sutuoktinio = privaciu["sutuoktinio-darbovietes"]
        self.assertEqual(len(sutuoktinio), 1)
        self.assertEqual(sutuoktinio[0]["pavadinimas"], "Eramet AS")
        self.assertEqual(sutuoktinio[0]["registracijos-salis"], "Užsienio valstybė")


if __name__ == "__main__":
    unittest.main()
