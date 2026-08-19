import json
import tempfile
import unittest
from pathlib import Path

from scraper.elections.prezidento_2024.anketa_parser import parse_anketa_sample


REPO_ROOT = Path(__file__).resolve().parents[1]
SAMPLES_ROOT = REPO_ROOT / "samples" / "html" / "2024-prezidento"


def _parse(candidate_id: str) -> dict:
    with tempfile.TemporaryDirectory() as tmp:
        output_path, _ = parse_anketa_sample(
            candidate_id=candidate_id,
            samples_root=SAMPLES_ROOT,
            output_root=Path(tmp),
        )
        return json.loads(output_path.read_text(encoding="utf-8"))


class Prezidento2024AnketaParserTests(unittest.TestCase):
    def setUp(self) -> None:
        self.nauseda = _parse("gitanas-nauseda")
        self.simonyte = _parse("ingrida-simonyte")
        self.vaitkus = _parse("eduardas-vaitkus")
        self.zalimas = _parse("dainius-zalimas")
        self.zemaitaitis = _parse("remigijus-zemaitaitis")
        self.jeglinskas = _parse("giedrimas-jeglinskas")

    def test_top_level_fields(self) -> None:
        self.assertEqual(self.nauseda["electionId"], "2024-prezidento")
        self.assertEqual(self.nauseda["candidateId"], "gitanas-nauseda")
        self.assertEqual(self.nauseda["candidateName"], "Gitanas NAUSĖDA")
        self.assertTrue(
            self.nauseda["source"]["candidateSourceUrl"].endswith(
                "KandidatasAnketa_rkndId-2435326.html"
            )
        )

    def test_normalized_section_order(self) -> None:
        # No trustees / campaign tabs on 2024 presidential candidate pages, so
        # the section order matches the 2024 EP module.
        self.assertEqual(
            list(self.nauseda["normalized"].keys()),
            [
                "profilis",
                "anketa",
                "biografija",
                "turto-ir-pajamu-deklaracijos",
                "privaciu-interesu-deklaracija",
                "kita",
            ],
        )

    def test_status_note_captured_for_all_candidates(self) -> None:
        # The run-off / elected status line is captured for every candidate,
        # not only the winner.
        self.assertEqual(self.nauseda["normalized"]["profilis"]["pastaba"], "Išrinktas II ture")
        self.assertEqual(self.simonyte["normalized"]["profilis"]["pastaba"], "Dalyvavo II ture")
        self.assertEqual(self.vaitkus["normalized"]["profilis"]["pastaba"], "Dalyvavo I ture")

    def test_photo_src_is_url(self) -> None:
        photo = self.nauseda["normalized"]["profilis"]["nuotrauka"]
        self.assertIn("kandImg", photo)
        self.assertTrue(photo.startswith("https://"))

    def test_nomination_captured(self) -> None:
        # Self-nominated vs party-nominated is captured under profilis.kita.
        self.assertEqual(
            self.nauseda["normalized"]["profilis"]["kita"]["kandidata-iskele"]["reiksme"],
            "išsikėlė pats",
        )
        self.assertEqual(
            self.simonyte["normalized"]["profilis"]["kita"]["kandidata-iskele"]["reiksme"],
            "Tėvynės sąjunga-Lietuvos krikščionys demokratai",
        )

    def test_anketa_core_fields(self) -> None:
        anketa = self.nauseda["normalized"]["anketa"]
        self.assertEqual(anketa["adresas"], "Vilnius")
        self.assertEqual(anketa["einamos-pareigos"], "Lietuvos Respublikos Prezidentas")

    def test_anketa_party_membership_table(self) -> None:
        irasai = self.nauseda["normalized"]["anketa"]["narystes-politinese-organizacijose"]["irasai"]
        self.assertEqual(len(irasai), 2)
        self.assertEqual(irasai[0]["politine-organizacija"], "Lietuvos komunistų partija")
        self.assertEqual(irasai[0]["nuo"], "1989")
        self.assertEqual(irasai[0]["iki"], "1990")

    def test_anketa_membership_inline_text_yields_no_records(self) -> None:
        # Jeglinskas answers Q8 with inline text ("Nebuvau ir nesu...") rather
        # than a membership table, so there are no structured records.
        anketa = self.jeglinskas["normalized"]["anketa"]
        self.assertEqual(anketa["narystes-politinese-organizacijose"]["irasai"], [])

    def test_anketa_pareiskimai_keys(self) -> None:
        pareiskimai = self.nauseda["normalized"]["anketa"]["pareiskimai"]
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
                "ar-esate-pilietis-pagal-kilme",
                "ar-gyvenate-lietuvoje-trejus-metus",
            ],
        )

    def test_presidential_eligibility_answers(self) -> None:
        # Q17 (citizen by origin) and Q18 (3-year residency) are the
        # presidential-only eligibility questions.
        pareiskimai = self.nauseda["normalized"]["anketa"]["pareiskimai"]
        self.assertEqual(pareiskimai["ar-esate-pilietis-pagal-kilme"], "Taip")
        self.assertEqual(pareiskimai["ar-gyvenate-lietuvoje-trejus-metus"], "Taip")
        # Incompatible-office answer differs between candidates.
        self.assertEqual(
            self.simonyte["normalized"]["anketa"]["pareiskimai"]["ar-eina-nesuderinamas-pareigas"],
            "Taip",
        )
        self.assertEqual(pareiskimai["ar-eina-nesuderinamas-pareigas"], "Ne")

    def test_conviction_and_mandate_details_absent(self) -> None:
        # No 2024 presidential candidate answered Q13/Q14 "Taip", so the
        # conditional detail blocks are all null / empty.
        anketa = self.nauseda["normalized"]["anketa"]
        # Uniform shape: no conviction block means an empty entry list.
        self.assertEqual(anketa["teistumo-detales"], {"irasai": []})
        self.assertIsNone(anketa["mandato-netekimo-detales"])

    def test_biografija_structured_questionnaire(self) -> None:
        bio = self.nauseda["normalized"]["biografija"]
        self.assertEqual(bio["gimimo-data"], "1964-05-19")
        self.assertEqual(bio["gimimo-vieta"], "Klaipėda, Lietuva")
        self.assertEqual(bio["mokslo-laipsnis"], "Daktaras")
        self.assertEqual(bio["seimine-padetis"], "Vedęs")
        self.assertTrue(len(bio["darbo-patirtis"]["irasai"]) >= 5)
        # Academic degree / pedagogic title guard the 2.1 / 2.2 numbering.
        self.assertEqual(self.zalimas["normalized"]["biografija"]["pedagoginis-vardas"], "Profesorius")

    def test_turto_ir_pajamu_normalized(self) -> None:
        turtas = self.nauseda["normalized"]["turto-ir-pajamu-deklaracijos"]
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
        self.assertEqual(turtas["privalomas-registruoti-turtas"], 359450)
        self.assertEqual(turtas["gautos-pajamos"], 122760)
        # Comma-decimal amounts parse to floats.
        self.assertEqual(
            self.zalimas["normalized"]["turto-ir-pajamu-deklaracijos"]["sumoketas-pajamu-mokestis"],
            28039.73,
        )

    def test_privaciu_interesu_declarant_hoisted(self) -> None:
        privaciu = self.nauseda["normalized"]["privaciu-interesu-deklaracija"]
        self.assertEqual(privaciu["deklaruojantis-asmuo"], "Gitanas NAUSĖDA")
        self.assertEqual(privaciu["pateikimo-data"], "2024-02-13")
        # An extra section (legal-entity ties) is keyed by its slugified title.
        rysiai = self.zemaitaitis["normalized"]["privaciu-interesu-deklaracija"][
            "rysiai-su-juridiniais-asmenimis"
        ]
        self.assertEqual(len(rysiai), 6)

    def test_kita_program_links(self) -> None:
        kita = self.nauseda["normalized"]["kita"]
        self.assertTrue(any(url.endswith(".pdf") for url in kita["nuorodos"]))


if __name__ == "__main__":
    unittest.main()
