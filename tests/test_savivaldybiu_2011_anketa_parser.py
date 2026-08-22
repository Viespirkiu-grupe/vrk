import json
import tempfile
import unittest
from pathlib import Path

from scraper.elections.savivaldybiu_2011.anketa_parser import parse_anketa_sample
from scraper.elections.savivaldybiu_2011.candidate_samples import EXPECTED_TABS
from scraper.elections.savivaldybiu_2011.sitemap import ELECTION_ID
from scraper.elections.seimo_zirmunu_2015.anketa_parser import _normalize_turto_ir_pajamu_data


REPO_ROOT = Path(__file__).resolve().parents[1]
SAMPLES_ROOT = REPO_ROOT / "samples" / "html" / "2011-vasario-27-savivaldybiu"


def _parse(candidate_id: str) -> dict:
    with tempfile.TemporaryDirectory() as tmp:
        output_path, _ = parse_anketa_sample(
            candidate_id=candidate_id, samples_root=SAMPLES_ROOT, output_root=Path(tmp)
        )
        return json.loads(output_path.read_text(encoding="utf-8"))


class Savivaldybiu2011AnketaParserTests(unittest.TestCase):
    """The 2015-era walkers with the municipal question mapping, four years
    earlier: council seats only, self-nominated individuals and coalitions of
    them on the ballot, and no mayor. These tests pin what is this
    election's own; the record shape is the 2015 municipal one."""

    def setUp(self) -> None:
        self.norkus = _parse("darius-norkus-42302")
        self.zuokas = _parse("arturas-zuokas-42680")
        self.karlonas = _parse("arunas-karlonas-43800")
        self.uspaskich = _parse("viktor-uspaskich-48972")
        self.stancikas = _parse("valdemaras-stancikas-42569")

    def test_records_carry_this_election_id(self) -> None:
        self.assertEqual(ELECTION_ID, "2011-vasario-27-savivaldybiu")
        self.assertEqual(self.norkus["electionId"], ELECTION_ID)
        self.assertEqual(self.norkus["candidateId"], "darius-norkus-42302")
        self.assertEqual(self.norkus["candidateName"], "Darius Norkus")

    def test_self_nominated_individual(self) -> None:
        k = self.norkus["kandidatavimas"]
        self.assertEqual(k["vrkCandidateId"], "42302")
        self.assertEqual(k["savivaldybe"], "Vilniaus miesto savivaldybė")
        self.assertEqual(k["roles"], ["tarybos-narys"])
        self.assertEqual(
            k["tarybosNarys"],
            {"partyList": None, "listKind": None, "listNumber": 3, "listPosition": None, "selfNominated": True},
        )
        # No mayor was elected in 2011, so the mayoral block is null for
        # everyone, not just for council-only candidates.
        self.assertIsNone(k["meras"])
        # Joined from VRK's results tree: a real false, not unknown.
        self.assertIs(k["isrinktas"], False)
        # The card says so in its own words, as a valueless field.
        kita = self.norkus["normalized"]["profilis"]["kita"]
        self.assertIn("issikeles-kandidatas", kita)
        self.assertIsNone(kita["issikeles-kandidatas"]["reiksme"])
        self.assertNotIn("iskele", kita)
        self.assertNotIn("numeris-sarase", kita)

    def test_self_nominated_coalition_member_is_flagged_on_the_card(self) -> None:
        # A coalition of self-nominated candidates is a list on the listing
        # and a self-nomination on the card: both facts are kept.
        k = self.stancikas["kandidatavimas"]["tarybosNarys"]
        self.assertEqual(k["listKind"], "issikelusiu-kandidatu-koalicija")
        self.assertEqual((k["listNumber"], k["listPosition"], k["selfNominated"]), (1, 1, False))
        kita = self.stancikas["normalized"]["profilis"]["kita"]
        self.assertEqual(kita["iskele"]["reiksme"], 'Nepartinių kandidatų koalicija "Vilnius - mūsų reikalas"')
        self.assertEqual(kita["numeris-sarase"]["reiksme"], "1")
        self.assertIn("issikeles-kandidatas", kita)
        # VRK's boilerplate notice in the card is not a value of that flag.
        for field in kita.values():
            self.assertNotIn("kviečiame susipažinti", field["reiksme"] or "")

    def test_party_coalition_member_carries_the_member_party_too(self) -> None:
        kita = self.karlonas["normalized"]["profilis"]["kita"]
        self.assertTrue(kita["iskele"]["reiksme"].startswith("Pakaunės krašto koalicija"))
        self.assertEqual(kita["numeris-sarase"]["reiksme"], "1")
        # The parenthesised second nomination — the coalition's member party
        # and the position on its own share — lands under the corpus's
        # recurring-label suffix, as on the 2012 and 2014 cards.
        self.assertEqual(kita["iskele-2"]["pavadinimas"], "(Iškėlė")
        self.assertEqual(kita["iskele-2"]["reiksme"], "Naujoji sąjunga (socialliberalai)")
        self.assertEqual(kita["numeris-sarase-2"]["reiksme"], "1")
        self.assertNotIn("issikeles-kandidatas", kita)
        self.assertEqual(self.karlonas["kandidatavimas"]["tarybosNarys"]["listKind"], "partiju-koalicija")

    def test_party_list_candidate_and_elected_status(self) -> None:
        kita = self.uspaskich["normalized"]["profilis"]["kita"]
        self.assertEqual(kita["iskele"]["reiksme"], "Darbo partija")
        self.assertNotIn("iskele-2", kita)
        self.assertNotIn("issikeles-kandidatas", kita)
        self.assertEqual(self.uspaskich["kandidatavimas"]["tarybosNarys"]["listKind"], "partija")
        # Zuokas's coalition won twelve Vilnius seats; he is the first.
        k = self.zuokas["kandidatavimas"]
        self.assertIs(k["isrinktas"], True)
        self.assertEqual(k["isrinktasKaip"], "tarybos-narys")
        self.assertTrue(k["rezultatuSaltinis"].endswith("apygardos7131_partijos3994_pirmumo_balsai.html"))

    def test_municipal_question_mapping_and_era_shapes(self) -> None:
        n = self.zuokas["normalized"]
        self.assertEqual(
            list(n["anketa"]["pareiskimai"].keys()),
            [
                "ar-nebaigta-teismo-paskirta-bausme",
                "ar-atliekate-karo-tarnyba",
                "ar-eina-nesuderinamas-pareigas",
                "ar-kitos-valstybes-institucijos-narys",
                "ar-turite-kitos-valstybes-pilietybe",
                "ar-buvote-pripazintas-kaltu",
                "teisiniai-argumentai",
            ],
        )
        self.assertEqual(n["anketa"]["pareiskimai"]["ar-buvote-pripazintas-kaltu"], "Taip")
        # The unnumbered explanation row after Q9, the one the municipal
        # mapping used to drop.
        self.assertEqual(
            n["anketa"]["pareiskimai"]["teisiniai-argumentai"],
            "Teistumas buvo panaikintas Vilniaus trečiojo teismo sprendimu 2009 m. lapkričio 9 d.",
        )
        self.assertIsNone(self.norkus["normalized"]["anketa"]["pareiskimai"]["teisiniai-argumentai"])
        self.assertEqual(n["anketa"]["gimimo-data"], "1968-02-21")
        self.assertEqual(n["anketa"]["anksciau-isrinktas"]["irasai"][0]["laikotarpis"], "2000 - 2007")
        self.assertEqual(n["profilis"]["vardas-pavarde"], "ARTŪRAS ZUOKAS")
        # GPM305 income in litas, as on the 2015 municipal pages.
        self.assertEqual(n["turto-ir-pajamu-deklaracijos"]["valiuta"], "Lt")
        self.assertEqual(n["turto-ir-pajamu-deklaracijos"]["gautos-pajamos"], 154424.77)
        self.assertEqual(n["turto-ir-pajamu-deklaracijos"]["sumoketas-pajamu-mokestis"], 21624)
        self.assertEqual(self.uspaskich["normalized"]["anketa"]["mokslo-laipsnis"], "Magistro kvalifikacijos laipsnis")

    def test_income_stated_as_one_sentence_is_a_declared_zero(self) -> None:
        # Twenty 2011 pages (and ten March 2015 ones) put the GPM305 extract
        # on the form's own line as prose instead of the two labelled rows;
        # every one declares zero, which must not read as no declaration.
        payload = {
            "sections": [
                {"title": "METINĖS GYVENTOJO(ŠEIMOS) TURTO DEKLARACIJOS PAGRINDINIŲ DUOMENŲ IŠRAŠAS",
                 "items": [{"key": "I. Privalomas registruoti turtas", "value": "25100,00 Lt"}]},
                {"title": "METINĖS PAJAMŲ MOKESČIO DEKLARACIJOS GPM305 FORMOS PAGRINDINIŲ DUOMENŲ IŠRAŠAS",
                 "items": [{"key": "GPM305 formos deklaracijos", "value": "Gauta 0 Lt , išskaičiuota pajamų mokesčio 0 Lt"}]},
            ],
            "note": "",
        }
        normalized = _normalize_turto_ir_pajamu_data(payload)
        self.assertEqual(normalized["privalomas-registruoti-turtas"], 25100)
        self.assertEqual(normalized["gautos-pajamos"], 0)
        self.assertEqual(normalized["sumoketas-pajamu-mokestis"], 0)
        # The labelled rows still win when present, and a line with neither
        # shape stays null.
        payload["sections"][1]["items"] = [{"key": "GPM305 formos deklaracijos", "value": ""}]
        self.assertIsNone(_normalize_turto_ir_pajamu_data(payload)["gautos-pajamos"])

    def test_four_tabs_no_biography_no_campaign(self) -> None:
        self.assertEqual(EXPECTED_TABS, {"anketa", "turto-ir-pajamu-deklaracijos", "interesu-deklaracija", "kita"})
        for record in (self.norkus, self.zuokas, self.karlonas):
            self.assertEqual(
                list(record["normalized"].keys()),
                ["profilis", "anketa", "turto-ir-pajamu-deklaracijos", "privaciu-interesu-deklaracija", "kita"],
            )
        self.assertEqual(self.zuokas["normalized"]["kita"], {"tekstai": ["Duomenų nėra"], "nuorodos": []})
        self.assertEqual(
            self.zuokas["normalized"]["privaciu-interesu-deklaracija"]["ii-dalyvavimas-juridiniuose-asmenyse"][0]["dalyvavimo-budas"],
            "akcininkas",
        )


if __name__ == "__main__":
    unittest.main()
