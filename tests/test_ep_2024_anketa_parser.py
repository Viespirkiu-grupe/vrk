import json
import tempfile
import unittest
from pathlib import Path

from scraper.elections.ep_2024.anketa_parser import parse_anketa_sample


REPO_ROOT = Path(__file__).resolve().parents[1]
SAMPLES_ROOT = REPO_ROOT / "samples" / "html" / "2024-ep"


def _parse(candidate_id: str) -> dict:
    with tempfile.TemporaryDirectory() as tmp:
        output_path, _ = parse_anketa_sample(
            candidate_id=candidate_id,
            samples_root=SAMPLES_ROOT,
            output_root=Path(tmp),
        )
        return json.loads(output_path.read_text(encoding="utf-8"))


class Ep2024AnketaParserTests(unittest.TestCase):
    def setUp(self) -> None:
        self.vitalijus = _parse("vitalijus-mitrofanovas")
        self.vilija = _parse("vilija-blinkeviciute")
        self.petras = _parse("petras-grazulis")
        self.tomas = _parse("tomas-baranauskas")

    def test_top_level_fields(self) -> None:
        self.assertEqual(self.vitalijus["electionId"], "2024-ep")
        self.assertEqual(self.vitalijus["candidateId"], "vitalijus-mitrofanovas")
        self.assertEqual(self.vitalijus["candidateName"], "Vitalijus MITROFANOVAS")
        self.assertTrue(
            self.vitalijus["source"]["candidateSourceUrl"].endswith("KandidatasAnketa_rkndId-2435638.html")
        )

    def test_normalized_section_order(self) -> None:
        # 2024 EP candidate pages carry no campaign tab (campaigns were run
        # by the party lists), so no campaign section is expected.
        self.assertEqual(
            list(self.vitalijus["normalized"].keys()),
            [
                "profilis",
                "anketa",
                "biografija",
                "turto-ir-pajamu-deklaracijos",
                "privaciu-interesu-deklaracija",
                "kita",
            ],
        )

    def test_profile_fields(self) -> None:
        profilis = self.vitalijus["normalized"]["profilis"]
        self.assertEqual(profilis["vardas-pavarde"], "Vitalijus MITROFANOVAS")
        self.assertIsNone(profilis["pastaba"])
        # The page links the portrait on vrk.lt; the record carries the archived
        # sidecar and photoMeta remembers the URL it came from (issue #118).
        self.assertEqual(profilis["nuotrauka"], f"photos/{self.vitalijus['candidateId']}.jpg")
        self.assertTrue(
            self.vitalijus["rawData"]["profile"]["photoMeta"]["url"].endswith("kandImg/photo_2435638.jpeg")
        )
        self.assertEqual(profilis["kita"]["sarasas"]["reiksme"], "Lietuvos socialdemokratų partija")
        self.assertEqual(profilis["kita"]["numeris-sarase"]["reiksme"], "8")
        self.assertEqual(profilis["kita"]["porinkiminis-numeris-sarase"]["reiksme"], "12")

    def test_elected_note_present_for_elected_mep(self) -> None:
        self.assertTrue(
            self.vilija["normalized"]["profilis"]["pastaba"].startswith("Išrinkta")
        )

    def test_anketa_core_answers(self) -> None:
        anketa = self.vitalijus["normalized"]["anketa"]
        self.assertEqual(anketa["adresas"], "Akmenės r. sav.")
        self.assertEqual(anketa["einamos-pareigos"], "Akmenės rajono savivaldybės meras")

    def test_anketa_pareiskimai_keys(self) -> None:
        pareiskimai = self.vitalijus["normalized"]["anketa"]["pareiskimai"]
        self.assertEqual(
            set(pareiskimai.keys()),
            {
                "ar-kitos-valstybes-institucijos-narys",
                "ar-eina-nesuderinamas-pareigas",
                "ar-bendradarbiavote-su-ssrs-tarnybomis",
                "ar-nebaigta-teismo-paskirta-bausme",
                "ar-buvote-pripazintas-kaltu",
                "ar-veika-dekriminalizuota",
                "ar-buvote-pripazintas-kaltu-uzsienyje",
                "ar-buvote-pripazintas-kaltu-del-politinio-persekiojimo",
                "ar-neteko-mandato-uz-pazeidimus",
                "ar-kitos-es-valstybes-pilietis",
                "ar-rinkimu-teise-apribota-kitoje-es-valstybeje",
            },
        )
        self.assertEqual(pareiskimai["ar-eina-nesuderinamas-pareigas"], "Taip")
        self.assertEqual(pareiskimai["ar-kitos-es-valstybes-pilietis"], "Ne")

    def test_party_membership_records_attached_to_question_8(self) -> None:
        # The membership table is rendered in its own <tr> after the Q8
        # heading row; a regression here silently empties the records.
        irasai = self.vitalijus["normalized"]["anketa"]["narystes-politinese-organizacijose"]["irasai"]
        self.assertEqual(len(irasai), 1)
        self.assertEqual(irasai[0]["politine-organizacija"], "Lietuvos socialdemokratų partija")
        self.assertEqual(irasai[0]["nuo"], "2000")
        self.assertEqual(irasai[0]["iki"], "Iki dabar")

    def test_conviction_details_captured_when_q13_is_taip(self) -> None:
        anketa = self.petras["normalized"]["anketa"]
        self.assertEqual(anketa["pareiskimai"]["ar-buvote-pripazintas-kaltu"], "Taip")
        # Uniform shape: one entry per conviction under irasai.
        irasai = anketa["teistumo-detales"]["irasai"]
        self.assertEqual(len(irasai), 1)
        detales = irasai[0]
        self.assertEqual(detales["nuosprendzio-data"], "2022-06-30")
        self.assertEqual(detales["nuosprendzio-valstybe"], "Lietuva")
        self.assertEqual(detales["nuosprendzio-institucija"], "VILNIAUS APYGARDOS TEISMAS")
        veikos = detales["nusikalstamos-veikos"]
        self.assertEqual(len(veikos), 1)
        self.assertEqual(
            veikos[0]["nusikalstamos-veikos-rusis-nusikaltimas-ar-baudziamasis-isakymas"],
            "Nusikaltimas",
        )
        self.assertEqual(veikos[0]["kaltes-forma"], "Tyčinis")

    def test_mandate_loss_details_captured_when_q14_is_taip(self) -> None:
        anketa = self.petras["normalized"]["anketa"]
        self.assertEqual(anketa["pareiskimai"]["ar-neteko-mandato-uz-pazeidimus"], "Taip")
        self.assertEqual(anketa["mandato-netekimo-detales"], "LR Seimas 2023-12-18")

    def test_conviction_details_empty_when_q13_is_ne(self) -> None:
        # No conviction block: the uniform shape is an empty list, not a
        # skeleton of null fields.
        self.assertEqual(
            self.vitalijus["normalized"]["anketa"]["teistumo-detales"],
            {"irasai": []},
        )

    def test_biografija_birth_and_marital(self) -> None:
        biografija = self.vitalijus["normalized"]["biografija"]
        self.assertEqual(biografija["gimimo-data"], "1971-05-01")
        self.assertEqual(biografija["gimimo-vieta"], "Akmenės raj. Ramučių km")
        self.assertEqual(biografija["seimine-padetis"], "Vedęs")

    def test_biografija_education_records_attached_to_question_2(self) -> None:
        irasai = self.vitalijus["normalized"]["biografija"]["issilavinimas"]["irasai"]
        self.assertEqual(len(irasai), 2)
        self.assertEqual(irasai[0]["mokymo-istaigos-pavadinimas"], "Vilniaus universitetas")
        self.assertEqual(irasai[0]["baigimo-metai"], "2006")

    def test_biografija_work_records_attached_to_question_4(self) -> None:
        irasai = self.vitalijus["normalized"]["biografija"]["darbo-patirtis"]["irasai"]
        self.assertEqual(len(irasai), 4)
        self.assertEqual(irasai[0]["darbo-pradzia"], "2008")
        self.assertEqual(irasai[0]["pareigos"], "meras")

    def test_biografija_languages_split(self) -> None:
        self.assertEqual(
            self.vitalijus["normalized"]["biografija"]["uzsienio-kalbos"],
            ["Anglų (Pradedantis)", "Latvių (Pradedantis)", "Rusų (Pažengęs)"],
        )

    def test_academic_degree_captured(self) -> None:
        # Q2.1/Q2.2 use the 2024 numbering; the 2016/2020-era mapping
        # ("3.1"/"3.2") would silently null these out.
        biografija = self.tomas["normalized"]["biografija"]
        self.assertEqual(biografija["mokslo-laipsnis"], "Daktaras")
        self.assertEqual(biografija["pedagoginis-vardas"], "Neturiu")

    def test_turto_amounts(self) -> None:
        turto = self.vitalijus["normalized"]["turto-ir-pajamu-deklaracijos"]
        self.assertEqual(turto["privalomas-registruoti-turtas"], 85729)
        self.assertEqual(turto["pinigines-lesos"], 76599)
        self.assertEqual(turto["gautos-paskolos"], 10832)
        self.assertEqual(turto["gautos-pajamos"], 68559.33)
        self.assertEqual(turto["sumoketas-pajamu-mokestis"], 12006.83)

    def test_privaciu_declaration_summary(self) -> None:
        privaciu = self.vitalijus["normalized"]["privaciu-interesu-deklaracija"]
        self.assertEqual(privaciu["pateikimo-data"], "2023-06-20")
        self.assertEqual(privaciu["deklaruojantis-asmuo"], "Vitalijus MITROFANOVAS")
        self.assertEqual(privaciu["sutuoktinis-sugyventinis-ar-partneris"], "Ingrida MITROFANOVIENĖ")

    def test_privaciu_workplace_and_legal_tie_records(self) -> None:
        privaciu = self.vitalijus["normalized"]["privaciu-interesu-deklaracija"]
        darbovietes = privaciu["deklaruojancio-darbovietes"]
        self.assertEqual(len(darbovietes), 1)
        self.assertEqual(darbovietes[0]["pavadinimas"], "Akmenės rajono savivaldybės administracija")
        self.assertEqual(darbovietes[0]["pareigos"], "Meras")

        rysiai = privaciu["rysiai-su-juridiniais-asmenimis"]
        self.assertEqual(len(rysiai), 5)
        self.assertEqual(rysiai[1]["juridinio-asmens-pavadinimas"], "LIETUVOS SOCIALDEMOKRATŲ PARTIJA")
        self.assertEqual(rysiai[1]["rysio-pobudis"], "Kolegialaus valdymo organo narys")

    def test_privaciu_has_no_sekcija_fallback_keys(self) -> None:
        privaciu = self.vitalijus["normalized"]["privaciu-interesu-deklaracija"]
        for key in privaciu:
            self.assertFalse(key.startswith("sekcija-"), f"Unexpected fallback key: {key!r}")

    def test_kita_is_empty_for_fixture_candidates(self) -> None:
        self.assertEqual(
            self.vitalijus["normalized"]["kita"],
            {"tekstai": [], "nuorodos": []},
        )


if __name__ == "__main__":
    unittest.main()
