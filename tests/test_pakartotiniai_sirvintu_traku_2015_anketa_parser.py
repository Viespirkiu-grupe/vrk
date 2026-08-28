import json
import tempfile
import unittest
from pathlib import Path

from scraper.elections.pakartotiniai_sirvintu_traku_2015.anketa_parser import (
    DEFAULT_RESULTS_PATH,
    parse_anketa_sample,
)
from scraper.elections.pakartotiniai_sirvintu_traku_2015.candidate_samples import (
    expected_tabs_for_entry,
)
from scraper.elections.pakartotiniai_sirvintu_traku_2015.sitemap import ELECTION_ID

from local_data import require


REPO_ROOT = Path(__file__).resolve().parents[1]
SAMPLES_ROOT = REPO_ROOT / "samples" / "html" / "2015-birzelio-7-pakartotiniai-sirvintos-trakai"


def _parse(candidate_id: str) -> tuple[dict, dict]:
    with tempfile.TemporaryDirectory() as tmp:
        output_path, stats = parse_anketa_sample(
            candidate_id=candidate_id,
            samples_root=SAMPLES_ROOT,
            output_root=Path(tmp),
        )
        return json.loads(output_path.read_text(encoding="utf-8")), stats


class PakartotiniaiSirvintuTraku2015AnketaParserTests(unittest.TestCase):
    """The 2015-era walkers with the municipal question mapping, as in the
    Telšiai module; these tests pin what is specific to this election."""

    def setUp(self) -> None:
        self.pinskuviene, _ = _parse("zivile-pinskuviene")
        self.vilkauskas, _ = _parse("kestutis-vilkauskas")
        self.puc_council, self.puc_council_stats = _parse("marija-puc-2")

    def test_records_carry_this_election_id(self) -> None:
        self.assertEqual(self.pinskuviene["electionId"], ELECTION_ID)
        self.assertEqual(ELECTION_ID, "2015-birzelio-7-pakartotiniai-sirvintos-trakai")

    def test_municipal_question_mapping_applies(self) -> None:
        pareiskimai = self.pinskuviene["normalized"]["anketa"]["pareiskimai"]
        self.assertEqual(
            list(pareiskimai.keys()),
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
        self.assertEqual(pareiskimai["ar-nebaigta-teismo-paskirta-bausme"], "Neturiu")
        self.assertEqual(
            self.vilkauskas["normalized"]["anketa"]["pareiskimai"][
                "ar-eina-nesuderinamas-pareigas"
            ],
            "Einu",
        )

    def test_era_shapes_hold(self) -> None:
        n = self.pinskuviene["normalized"]
        self.assertEqual(n["turto-ir-pajamu-deklaracijos"]["valiuta"], "Lt")
        self.assertEqual(n["turto-ir-pajamu-deklaracijos"]["privalomas-registruoti-turtas"], 1032500)
        self.assertIsNone(n["profilis"]["pastaba"])
        self.assertEqual(n["profilis"]["vardas-pavarde"], "Živilė Pinskuvienė")
        self.assertEqual(n["profilis"]["kita"]["savivaldybe"]["reiksme"], "Širvintų rajono (Nr. 48)")
        self.assertEqual(
            n["politines-kampanijos-dalyvio-duomenys"][0]["statusas"], "Savarankiškas"
        )

    def test_biografija_is_a_mayoral_only_tab(self) -> None:
        # Council-only candidates publish four tabs, mayoral candidates five,
        # so the expected set is computed from the candidate's role.
        self.assertIn("biografija", self.pinskuviene["normalized"])
        self.assertNotIn("biografija", self.vilkauskas["normalized"])
        self.assertEqual(
            expected_tabs_for_entry({"roles": ["tarybos-narys"]}),
            {"anketa", "turto-ir-pajamu-deklaracijos", "interesu-deklaracija", "kita"},
        )
        self.assertIn("biografija", expected_tabs_for_entry({"roles": ["meras"]}))
        self.assertIn("biografija", expected_tabs_for_entry({"roles": ["meras", "tarybos-narys"]}))

    def test_kandidatavimas_carries_the_listing_only_facts(self) -> None:
        require(DEFAULT_RESULTS_PATH)
        # The two structures' facts — municipality, roles, list and seat
        # order — exist on the listing pages and nowhere on the candidate
        # page, so they are carried into the record.
        mayoral = self.pinskuviene["kandidatavimas"]
        self.assertEqual(mayoral["savivaldybe"], "Širvintų rajono savivaldybė")
        self.assertEqual(mayoral["roles"], ["meras"])
        self.assertIsNone(mayoral["tarybosNarys"])
        # No 2015 page marks a winner; the results join says she won the
        # mayoralty outright in round one.
        self.assertIs(mayoral["isrinktas"], True)
        self.assertEqual(mayoral["isrinktasKaip"], "meras")
        self.assertEqual(mayoral["rezultatuTuras"], 1)
        self.assertIn("2015_2_savivaldybiu_tarybu_rinkimai/output_lt/", mayoral["rezultatuSaltinis"])

        council = self.vilkauskas["kandidatavimas"]
        self.assertEqual(council["roles"], ["tarybos-narys"])
        self.assertIs(council["isrinktas"], True)
        self.assertEqual(council["isrinktasKaip"], "tarybos-narys")
        self.assertEqual(council["tarybosNarys"]["partyList"], "Lietuvos socialdemokratų partija")
        self.assertEqual(council["tarybosNarys"]["listPosition"], 2)
        self.assertIsNone(council["meras"])

    def test_unpublished_anketa_is_reported_as_data_not_breakage(self) -> None:
        # VRK published this candidacy's page with the single word "Rengiama"
        # and no questionnaire at all. That is an upstream gap: it earns one
        # warning naming the placeholder, not the critical/error pair that a
        # parser failure would raise.
        events = [(a["eventType"], a["severity"]) for a in self.puc_council_stats["anomalies"]]
        self.assertEqual(events, [("AnketaNotPublished", "warning")])
        self.assertEqual(
            self.puc_council_stats["anomalies"][0]["detail"]["placeholderText"], "Rengiama"
        )
        self.assertEqual(self.puc_council_stats["rowCount"], 0)
        # The profile card is still published, so the record keeps who she is
        # and which list she stood on.
        profilis = self.puc_council["normalized"]["profilis"]
        self.assertEqual(profilis["vardas-pavarde"], "Marija Puč")
        self.assertEqual(profilis["kita"]["numeris-sarase"]["reiksme"], "1")
        self.assertEqual(self.puc_council["kandidatavimas"]["vrkCandidateId"], "87694")
        self.assertIsNone(self.puc_council["normalized"]["anketa"]["gimimo-data"])


if __name__ == "__main__":
    unittest.main()
