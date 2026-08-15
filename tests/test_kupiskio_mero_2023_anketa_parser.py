import json
import tempfile
import unittest
from pathlib import Path

from scraper.elections.kupiskio_mero_2023.anketa_parser import parse_anketa_sample


REPO_ROOT = Path(__file__).resolve().parents[1]
SAMPLES_ROOT = REPO_ROOT / "samples" / "html" / "2023-spalio-8-kupiskio-mero"


def _parse(candidate_id: str) -> dict:
    with tempfile.TemporaryDirectory() as tmp:
        output_path, _ = parse_anketa_sample(
            candidate_id=candidate_id,
            samples_root=SAMPLES_ROOT,
            output_root=Path(tmp),
        )
        return json.loads(output_path.read_text(encoding="utf-8"))


class KupiskioMero2023AnketaParserTests(unittest.TestCase):
    def setUp(self) -> None:
        self.aukstikalnis = _parse("zilvinas-aukstikalnis")
        self.raslanas = _parse("algirdas-raslanas")
        self.blazeviciene = _parse("egle-blazeviciene")
        self.jonutis = _parse("edmundas-jonutis")

    def test_top_level_fields(self) -> None:
        self.assertEqual(self.aukstikalnis["electionId"], "2023-spalio-8-kupiskio-mero")
        self.assertEqual(self.aukstikalnis["candidateId"], "zilvinas-aukstikalnis")
        self.assertEqual(self.aukstikalnis["candidateName"], "Žilvinas AUKŠTIKALNIS")
        self.assertTrue(
            self.aukstikalnis["source"]["candidateSourceUrl"].endswith(
                "savKandidatasAnketa_2023_rkndId-2435289.html"
            )
        )

    def test_normalized_section_order(self) -> None:
        # Candidate pages carry a campaign tab, unlike the 2024 presidential
        # pages, so the campaign section sits between declarations and "kita".
        self.assertEqual(
            list(self.aukstikalnis["normalized"].keys()),
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

    def test_profile_municipal_fields(self) -> None:
        kita = self.aukstikalnis["normalized"]["profilis"]["kita"]
        self.assertEqual(kita["savivaldybe"]["reiksme"], "Kupiškio rajono (23)")
        self.assertEqual(kita["iskele-i-savivaldybes-merus"]["reiksme"], "Liberalų sąjūdis")
        self.assertEqual(kita["turas"]["reiksme"], "I")
        self.assertEqual(
            self.raslanas["normalized"]["profilis"]["kita"]["turas"]["reiksme"], "II"
        )

    def test_elected_note_only_for_winner(self) -> None:
        self.assertEqual(
            self.raslanas["normalized"]["profilis"]["pastaba"],
            "Išrinktas Kupiškio rajono (Nr.23) savivaldybėje II ture",
        )
        self.assertIsNone(self.aukstikalnis["normalized"]["profilis"]["pastaba"])

    def test_photo_src_is_url(self) -> None:
        photo = self.aukstikalnis["normalized"]["profilis"]["nuotrauka"]
        self.assertIn("kandImg", photo)
        self.assertTrue(photo.startswith("https://"))

    def test_anketa_core_fields(self) -> None:
        anketa = self.aukstikalnis["normalized"]["anketa"]
        self.assertEqual(anketa["adresas"], "Kupiškio r. sav.")
        self.assertEqual(anketa["einamos-pareigos"], "Projektų vadovas")

    def test_anketa_membership_answer_is_inline_text(self) -> None:
        # Q8 asks for a single membership and is answered inline, so the text is
        # kept next to the (empty) record list the shared shape expects.
        naryste = self.aukstikalnis["normalized"]["anketa"]["narystes-politinese-organizacijose"]
        self.assertEqual(naryste["tekstas"], "Kupiškio Rotary klubas")
        self.assertEqual(naryste["irasai"], [])
        self.assertEqual(
            self.raslanas["normalized"]["anketa"]["narystes-politinese-organizacijose"]["tekstas"],
            "Lietuvos socialdemokratų partija",
        )

    def test_anketa_pareiskimai_keys(self) -> None:
        pareiskimai = self.aukstikalnis["normalized"]["anketa"]["pareiskimai"]
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
            ],
        )

    def test_spaced_question_numbers_are_answered(self) -> None:
        # Q10-Q12 are numbered "10 ." on these pages; without the tolerant
        # question-number repair their answers are dropped silently.
        pareiskimai = self.aukstikalnis["normalized"]["anketa"]["pareiskimai"]
        self.assertEqual(pareiskimai["ar-eina-nesuderinamas-pareigas"], "Taip")
        self.assertEqual(pareiskimai["ar-bendradarbiavote-su-ssrs-tarnybomis"], "Ne")
        self.assertEqual(pareiskimai["ar-nebaigta-teismo-paskirta-bausme"], "Ne")
        self.assertEqual(
            self.jonutis["normalized"]["anketa"]["pareiskimai"]["ar-eina-nesuderinamas-pareigas"],
            "Ne",
        )

    def test_conviction_details_split_on_hyphen(self) -> None:
        # Only Aukštikalnis answered Q13 "Taip"; the 13.4 detail table separates
        # label from value with a plain hyphen, not the 2024 en dash.
        teistumas = self.aukstikalnis["normalized"]["anketa"]["teistumo-detales"]
        self.assertEqual(teistumas["nuosprendzio-data"], "1992-06-19")
        self.assertEqual(teistumas["nuosprendzio-valstybe"], "Lietuva")
        self.assertEqual(teistumas["nuosprendzio-institucija"], "KUPIŠKIO R. APYLINKĖS TEISMAS")

        irasai = teistumas["nusikalstamos-veikos"]["irasai"]
        self.assertEqual(len(irasai), 1)
        self.assertEqual(
            irasai[0]["kesinimosi-objektas-baudziamojo-kodekso-skyriaus-ir-straipsnio-pavadinimas"],
            "90 str. 1 d.(senas (iki 2003-05-01));",
        )
        self.assertEqual(irasai[0]["teistumo-isnykimo-ar-panaikinimo-data"], "1993-12-04")

        self.assertIsNone(
            self.raslanas["normalized"]["anketa"]["teistumo-detales"]["nuosprendzio-data"]
        )
        self.assertEqual(
            self.raslanas["normalized"]["anketa"]["teistumo-detales"]["nusikalstamos-veikos"]["irasai"],
            [],
        )

    def test_mandate_loss_details_absent(self) -> None:
        # No candidate answered Q14 "Taip".
        self.assertIsNone(self.aukstikalnis["normalized"]["anketa"]["mandato-netekimo-detales"])

    def test_biografija_uses_2020_question_numbering(self) -> None:
        # Nationality is Q2 here, so education (Q3) and work history (Q5) are
        # shifted by one against the 2024 modules.
        bio = self.raslanas["normalized"]["biografija"]
        self.assertEqual(bio["gimimo-data"], "1956-09-09")
        self.assertEqual(bio["gimimo-vieta"], "Zarasų r.sa. Dusetos")
        self.assertEqual(bio["tautybe"], "Lietuvis")
        self.assertEqual(bio["mokslo-laipsnis"], "Habilituotas mokslų daktaras")
        self.assertEqual(bio["pedagoginis-vardas"], "Profesorius")
        self.assertEqual(bio["uzsienio-kalbos"], ["Anglų", "Lenkų", "Prancūzų"])
        self.assertEqual(bio["pomegiai"], "Aktyvus poilsis, sodininkystė.")
        self.assertEqual(bio["seimine-padetis"], "Vedęs")

    def test_biografija_record_tables(self) -> None:
        bio = self.blazeviciene["normalized"]["biografija"]
        self.assertEqual(len(bio["issilavinimas"]["irasai"]), 3)
        self.assertEqual(
            bio["issilavinimas"]["irasai"][0]["mokymo-istaigos-pavadinimas"],
            "Kauno technologijos universitetas",
        )
        self.assertEqual(len(bio["darbo-patirtis"]["irasai"]), 11)
        self.assertEqual(bio["darbo-patirtis"]["irasai"][0]["pareigos"], "Tarybos narė")

    def test_turto_ir_pajamu_normalized(self) -> None:
        # Guards the tab-body shim: these tables sit inside a <div> instead of
        # being siblings of the tab navigation.
        turtas = self.aukstikalnis["normalized"]["turto-ir-pajamu-deklaracijos"]
        self.assertEqual(
            list(turtas.keys()),
            [
                "privalomas-registruoti-turtas",
                "vertybiniai-popieriai-meno-kuriniai-juvelyriniai-dirbiniai",
                "pinigines-lesos",
                "suteiktos-paskolos",
                "gautos-paskolos",
                "gautos-pajamos",
                "sumoketas-pajamu-mokestis",
            ],
        )
        self.assertEqual(turtas["privalomas-registruoti-turtas"], 57780)
        self.assertEqual(turtas["pinigines-lesos"], 11000)
        self.assertEqual(turtas["suteiktos-paskolos"], 1500)
        # Comma-decimal amounts parse to floats.
        self.assertEqual(turtas["gautos-pajamos"], 12847.96)
        self.assertEqual(turtas["sumoketas-pajamu-mokestis"], 1376.78)

    def test_privaciu_interesu_declarant_hoisted(self) -> None:
        privaciu = self.aukstikalnis["normalized"]["privaciu-interesu-deklaracija"]
        self.assertEqual(privaciu["deklaruojantis-asmuo"], "Žilvinas AUKŠTIKALNIS")
        self.assertEqual(privaciu["pateikimo-data"], "2023-07-28")
        self.assertEqual(privaciu["sutuoktinis-sugyventinis-ar-partneris"], "Rima AUKŠTIKALNIENĖ")
        self.assertEqual(len(privaciu["deklaruojancio-darbovietes"]), 2)
        self.assertEqual(
            privaciu["deklaruojancio-darbovietes"][0]["pavadinimas"],
            "Kupiškio rajono savivaldybės taryba",
        )
        # Extra sections are keyed by their slugified title.
        self.assertEqual(len(privaciu["rysiai-su-juridiniais-asmenimis"]), 3)
        self.assertEqual(len(self.jonutis["normalized"]["privaciu-interesu-deklaracija"]["rysiai-sudarius-sandorius"]), 1)

    def test_campaign_participant_and_donation_totals(self) -> None:
        campaigns = self.aukstikalnis["normalized"]["politines-kampanijos-dalyvio-duomenys"]
        self.assertEqual(len(campaigns), 1)
        campaign = campaigns[0]
        self.assertEqual(campaign["statusas"], "Atstovaujamasis")
        self.assertEqual(campaign["registravimo-data"], "2023-08-24")
        totals = campaign["aukos-pagal-sekcija"]["gautos-ir-priimtos-aukos"]["totals"]
        self.assertEqual(totals["is-viso"], 3804.96)
        self.assertEqual(totals["kandidato-nuosavos-lesos"], 1000.0)

    def test_kita_tab_is_empty_for_every_candidate(self) -> None:
        # No candidate published programme documents on the "Kita" tab.
        for payload in (self.aukstikalnis, self.raslanas, self.blazeviciene, self.jonutis):
            self.assertEqual(payload["normalized"]["kita"], {"tekstai": [], "nuorodos": []})


if __name__ == "__main__":
    unittest.main()
