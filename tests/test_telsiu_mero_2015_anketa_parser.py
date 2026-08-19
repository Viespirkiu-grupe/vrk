import json
import tempfile
import unittest
from pathlib import Path

from scraper.elections.telsiu_mero_2015.anketa_parser import parse_anketa_sample
from scraper.elections.telsiu_mero_2015.sitemap import ELECTION_ID, LISTING_URL


REPO_ROOT = Path(__file__).resolve().parents[1]
SAMPLES_ROOT = REPO_ROOT / "samples" / "html" / "2015-lapkricio-8-telsiu-mero"


def _parse(candidate_id: str) -> dict:
    with tempfile.TemporaryDirectory() as tmp:
        output_path, _ = parse_anketa_sample(
            candidate_id=candidate_id,
            samples_root=SAMPLES_ROOT,
            output_root=Path(tmp),
        )
        return json.loads(output_path.read_text(encoding="utf-8"))


class TelsiuMero2015AnketaParserTests(unittest.TestCase):
    """First municipal-variant election of the 2015 era: the page walkers are
    the Žirmūnai set, the question mapping is the savivaldybių one."""

    def setUp(self) -> None:
        self.kuizinas = _parse("petras-kuizinas")
        self.urbonas = _parse("saulius-urbonas")
        self.bacevicius = _parse("algirdas-bacevicius")

    def test_module_constants(self) -> None:
        self.assertEqual(ELECTION_ID, "2015-lapkricio-8-telsiu-mero")
        # This election's static pages live under a nonstandard base.
        self.assertIn("2015_4_savivaldybiu_tarybu_rinkimai/469_lt", LISTING_URL)

    def test_municipal_pareiskimai(self) -> None:
        # The savivaldybių tarybų rinkimų įstatymo set: Q8.1–8.5 plus the Q9
        # "anything to declare" conviction question, with the era's verbose
        # first-person answers.
        pareiskimai = self.kuizinas["normalized"]["anketa"]["pareiskimai"]
        self.assertEqual(
            list(pareiskimai.keys()),
            [
                "ar-nebaigta-teismo-paskirta-bausme",
                "ar-atliekate-karo-tarnyba",
                "ar-eina-nesuderinamas-pareigas",
                "ar-kitos-valstybes-institucijos-narys",
                "ar-turite-kitos-valstybes-pilietybe",
                "ar-buvote-pripazintas-kaltu",
            ],
        )
        self.assertEqual(pareiskimai["ar-nebaigta-teismo-paskirta-bausme"], "Neturiu")
        self.assertEqual(pareiskimai["ar-eina-nesuderinamas-pareigas"], "Neinu")
        self.assertEqual(pareiskimai["ar-buvote-pripazintas-kaltu"], "Ne")
        # One candidate answers the incompatible-duties question "Einu".
        self.assertEqual(
            self.urbonas["normalized"]["anketa"]["pareiskimai"]["ar-eina-nesuderinamas-pareigas"],
            "Einu",
        )

    def test_municipal_profile_card_fields(self) -> None:
        kita = self.kuizinas["normalized"]["profilis"]["kita"]
        self.assertEqual(kita["savivaldybe"]["reiksme"], "Telšių rajono (Nr. 51)")
        self.assertEqual(kita["iskele"]["reiksme"], "Darbo partija")
        self.assertIn("numeris-sarase", kita)
        # The self-nominated candidate's card carries no list fields but names
        # him "Išsikėlęs kandidatas".
        bacevicius_kita = self.bacevicius["normalized"]["profilis"]["kita"]
        self.assertIn("issikeles-kandidatas", bacevicius_kita)
        self.assertNotIn("numeris-sarase", bacevicius_kita)

    def test_era_shapes_hold(self) -> None:
        n = self.kuizinas["normalized"]
        self.assertEqual(n["turto-ir-pajamu-deklaracijos"]["valiuta"], "Lt")
        self.assertEqual(n["turto-ir-pajamu-deklaracijos"]["privalomas-registruoti-turtas"], 60300)
        self.assertIsNone(n["profilis"]["pastaba"])
        self.assertEqual(len(n["anketa"]["anksciau-isrinktas"]["irasai"]), 4)
        self.assertEqual(
            n["politines-kampanijos-dalyvio-duomenys"][0]["statusas"], "Savarankiškas"
        )
        # No Telšiai candidate published a program.
        self.assertEqual(n["kita"], {"tekstai": ["Duomenų nėra"], "nuorodos": []})


if __name__ == "__main__":
    unittest.main()
