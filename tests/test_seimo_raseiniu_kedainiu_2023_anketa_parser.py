import json
import tempfile
import unittest
from pathlib import Path

from scraper.elections.seimo_raseiniu_kedainiu_2023.anketa_parser import parse_anketa_sample


REPO_ROOT = Path(__file__).resolve().parents[1]
SAMPLES_ROOT = REPO_ROOT / "samples" / "html" / "2023-rugsejo-3-seimo-raseiniai-kedainiai"


def _parse(candidate_id: str) -> dict:
    with tempfile.TemporaryDirectory() as tmp:
        output_path, _ = parse_anketa_sample(
            candidate_id=candidate_id,
            samples_root=SAMPLES_ROOT,
            output_root=Path(tmp),
        )
        return json.loads(output_path.read_text(encoding="utf-8"))


class SeimoRaseiniuKedainiu2023AnketaParserTests(unittest.TestCase):
    def setUp(self) -> None:
        self.skamarakas = _parse("matas-skamarakas")
        self.tautkus = _parse("antanas-tautkus")
        self.gricius = _parse("algirdas-gricius")
        self.sabuniene = _parse("meida-sabuniene")

    def test_top_level_fields(self) -> None:
        self.assertEqual(
            self.skamarakas["electionId"], "2023-rugsejo-3-seimo-raseiniai-kedainiai"
        )
        self.assertEqual(self.skamarakas["candidateId"], "matas-skamarakas")
        # The listing marks the winner "Matas SKAMARAKAS (V)"; the suffix is stripped.
        self.assertEqual(self.skamarakas["candidateName"], "Matas SKAMARAKAS")
        self.assertTrue(
            self.skamarakas["source"]["candidateSourceUrl"].endswith(
                "KandidatasAnketa_rkndId-2435265.html"
            )
        )

    def test_normalized_section_order(self) -> None:
        self.assertEqual(
            list(self.skamarakas["normalized"].keys()),
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

    def test_profile_constituency_fields(self) -> None:
        profilis = self.skamarakas["normalized"]["profilis"]
        self.assertEqual(profilis["vardas-pavarde"], "Matas SKAMARAKAS")
        self.assertIn("kandImg", profilis["nuotrauka"])

        kita = profilis["kita"]
        self.assertEqual(kita["vienmandate-apygarda"]["reiksme"], "Raseinių–Kėdainių( 42)")
        self.assertEqual(kita["iskele"]["reiksme"], "Lietuvos socialdemokratų partija")
        self.assertEqual(kita["turas"]["reiksme"], "II")
        self.assertEqual(self.gricius["normalized"]["profilis"]["kita"]["turas"]["reiksme"], "I")

    def test_elected_note_only_for_winner(self) -> None:
        self.assertEqual(
            self.skamarakas["normalized"]["profilis"]["pastaba"],
            "Išrinktas vienmandatėje Raseinių–Kėdainių (Nr. 42) apygardoje II ture",
        )
        self.assertIsNone(self.gricius["normalized"]["profilis"]["pastaba"])

    def test_anketa_core_fields(self) -> None:
        anketa = self.skamarakas["normalized"]["anketa"]
        self.assertEqual(anketa["adresas"], "Raseinių r.")
        self.assertEqual(anketa["einamos-pareigos"], "Raseinių rajono savivaldybės vicemeras")

    def test_anketa_membership_answer_is_inline_text(self) -> None:
        # Q8 is answered inline rather than with the 2024 membership table.
        naryste = self.skamarakas["normalized"]["anketa"]["narystes-politinese-organizacijose"]
        self.assertEqual(naryste["tekstas"], "Lietuvos socialdemokratų partija")
        self.assertEqual(naryste["irasai"], [])

    def test_anketa_pareiskimai_keys(self) -> None:
        # Q9-Q14 are the Rinkimų kodekso 76 str. declarations shared with the
        # 2024 modules; Q15-Q16 are the Seimo eligibility questions.
        pareiskimai = self.skamarakas["normalized"]["anketa"]["pareiskimai"]
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
        # Every declaration is answered, so a mis-numbered mapping would show up
        # as nulls here rather than as a parse failure.
        self.assertTrue(all(value is not None for value in pareiskimai.values()))
        self.assertEqual(pareiskimai["ar-eina-nesuderinamas-pareigas"], "Taip")
        self.assertEqual(
            self.gricius["normalized"]["anketa"]["pareiskimai"]["ar-eina-nesuderinamas-pareigas"],
            "Ne",
        )

    def test_conviction_details(self) -> None:
        # Only Tautkus answered Q13 "Taip".
        teistumas = self.tautkus["normalized"]["anketa"]["teistumo-detales"]
        self.assertEqual(teistumas["nuosprendzio-data"], "2013-03-06")
        self.assertEqual(teistumas["nuosprendzio-valstybe"], "Lietuva")
        self.assertEqual(teistumas["nuosprendzio-institucija"], "RASEINIŲ R. APYLINKĖS TEISMAS")

        irasai = teistumas["nusikalstamos-veikos"]["irasai"]
        self.assertEqual(len(irasai), 1)
        self.assertEqual(irasai[0]["kaltes-forma"], "Tyčinis")
        self.assertEqual(irasai[0]["sunkumas"], "Nesunkus")
        self.assertEqual(irasai[0]["teistumo-isnykimo-ar-panaikinimo-data"], "2016-02-22")

        self.assertIsNone(
            self.skamarakas["normalized"]["anketa"]["teistumo-detales"]["nuosprendzio-data"]
        )
        self.assertIsNone(self.skamarakas["normalized"]["anketa"]["mandato-netekimo-detales"])

    def test_biografija_uses_2023_question_numbering(self) -> None:
        # Nationality is Q2 here, shifting education (Q3) and work history (Q5)
        # by one against the 2024 modules. Empty sections would mean the tab
        # body was located with the wrong selector.
        bio = self.skamarakas["normalized"]["biografija"]
        self.assertEqual(bio["gimimo-data"], "1988-09-21")
        self.assertEqual(bio["gimimo-vieta"], "Ariogala, Raseinių rajonas")
        self.assertEqual(bio["tautybe"], "Lietuvis")
        self.assertEqual(bio["mokslo-laipsnis"], "Magistras")
        self.assertEqual(bio["uzsienio-kalbos"], ["Anglų"])
        self.assertEqual(bio["seimine-padetis"], "Vedęs")

        self.assertEqual(len(bio["issilavinimas"]["irasai"]), 2)
        self.assertEqual(
            bio["issilavinimas"]["irasai"][0]["mokymo-istaigos-pavadinimas"],
            "Kauno technologijos universitetas",
        )
        self.assertEqual(len(bio["darbo-patirtis"]["irasai"]), 4)
        self.assertEqual(bio["darbo-patirtis"]["irasai"][0]["pareigos"], "Vicemeras")

    def test_turto_ir_pajamu_normalized(self) -> None:
        turtas = self.skamarakas["normalized"]["turto-ir-pajamu-deklaracijos"]
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
        self.assertEqual(turtas["privalomas-registruoti-turtas"], 59020)
        self.assertEqual(turtas["pinigines-lesos"], 4900)
        self.assertEqual(turtas["gautos-pajamos"], 58860.23)
        self.assertEqual(turtas["sumoketas-pajamu-mokestis"], 11219.17)

    def test_privaciu_interesu_declarant_hoisted(self) -> None:
        privaciu = self.skamarakas["normalized"]["privaciu-interesu-deklaracija"]
        self.assertEqual(privaciu["deklaruojantis-asmuo"], "Matas SKAMARAKAS")
        self.assertEqual(privaciu["pateikimo-data"], "2023-06-28")
        self.assertEqual(privaciu["sutuoktinis-sugyventinis-ar-partneris"], "Eglė SKAMARAKĖ")
        self.assertEqual(len(privaciu["rysiai-su-juridiniais-asmenimis"]), 4)
        self.assertEqual(len(privaciu["rysiai-sudarius-sandorius"]), 2)

    def test_campaign_self_standing_participant(self) -> None:
        # Self-standing participants publish all five campaign tabs.
        campaigns = self.skamarakas["normalized"]["politines-kampanijos-dalyvio-duomenys"]
        self.assertEqual(len(campaigns), 1)
        campaign = campaigns[0]
        self.assertEqual(campaign["statusas"], "Savarankiškas")
        self.assertEqual(campaign["registravimo-data"], "2023-06-02")
        self.assertEqual(campaign["izdininkas"]["vardas-pavarde"], "ZOSĖ PETRAITIENĖ")
        self.assertEqual(len(campaign["finansavimo-ataskaitos"]), 2)
        self.assertEqual(len(campaign["sutartys"]), 20)

    def test_campaign_represented_participant(self) -> None:
        # Party-represented participants publish only the donations tab.
        campaign = self.gricius["normalized"]["politines-kampanijos-dalyvio-duomenys"][0]
        self.assertEqual(campaign["statusas"], "Atstovaujamasis")
        self.assertEqual(campaign["finansavimo-ataskaitos"], [])
        self.assertEqual(campaign["sutartys"], [])

    def test_campaign_donation_records(self) -> None:
        donations = self.skamarakas["normalized"]["politines-kampanijos-dalyvio-duomenys"][0][
            "aukos-pagal-sekcija"
        ]["gautos-ir-priimtos-aukos"]
        self.assertEqual(len(donations["records"]), 7)
        self.assertEqual(
            donations["records"][0],
            {
                "rowNumber": "1.",
                "donor": "LIETUVOS SOCIALDEMOKRATŲ PARTIJA",
                "municipality": None,
                "date": "2023-07-25",
                "incomeSourceCode": "PL",
                "amount": 2500.0,
                "notes": "Piniginės lėšos, Priimtas",
            },
        )
        self.assertEqual(donations["totals"]["is-viso"], 11204.81)
        self.assertEqual(
            sum(record["amount"] for record in donations["records"]),
            donations["totals"]["is-viso"],
        )

    def test_kita_tab_is_empty_for_every_candidate(self) -> None:
        for payload in (self.skamarakas, self.tautkus, self.gricius, self.sabuniene):
            self.assertEqual(payload["normalized"]["kita"], {"tekstai": [], "nuorodos": []})


if __name__ == "__main__":
    unittest.main()
