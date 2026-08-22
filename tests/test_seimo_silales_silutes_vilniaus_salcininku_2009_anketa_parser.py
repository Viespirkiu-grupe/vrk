import json
import tempfile
import unittest
from pathlib import Path

from scraper.elections.seimo_silales_silutes_vilniaus_salcininku_2009.anketa_parser import parse_anketa_sample
from scraper.elections.seimo_silales_silutes_vilniaus_salcininku_2009.candidate_samples import EXPECTED_TABS
from scraper.elections.seimo_silales_silutes_vilniaus_salcininku_2009.results import RESULTS_TREE
from scraper.elections.seimo_silales_silutes_vilniaus_salcininku_2009.sitemap import (
    ELECTION_ID,
    LISTING_URL,
    build_sitemap_from_sample,
)
from scraper.elections.seimo_birzu_zarasu_ukmerges_2013.sitemap import extract_district_links


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


class SeimoSilalesSilutesVilniausSalcininku2009SitemapTests(unittest.TestCase):
    def test_index_lists_the_constituencies(self) -> None:
        links = extract_district_links((SAMPLES_ROOT / "list.html").read_text(encoding="utf-8"))
        self.assertEqual([(link["number"], link["name"], link["districtId"]) for link in links], [(33, 'Šilalės - Šilutės', '7126'), (56, 'Vilniaus - Šalčininkų', '7125')])
        self.assertEqual(LISTING_URL, "https://www.vrk.lt/statiniai/puslapiai/rinkimai/406_lt/Kandidatai/index.html")

    def test_sitemap_walks_every_constituency(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            _, stats = build_sitemap_from_sample(
                sample_path=SAMPLES_ROOT,
                output_path=Path(tmp) / "sitemap.json",
            )
            payload = json.loads((Path(tmp) / "sitemap.json").read_text(encoding="utf-8"))
        self.assertEqual(stats, {"rows": 17, "extracted": 17, "skipped": 0, "duplicate_candidate_ids": 0, "districts": 2})
        self.assertEqual(payload["electionId"], "2009-lapkricio-15-seimo-silale-silute-vilnius-salcininkai")
        self.assertEqual(payload["sourceUrl"], LISTING_URL)
        by_id = {entry["candidateId"]: entry for entry in payload["entries"]}
        self.assertEqual(sorted(by_id), ['algimantas-matulevicius', 'alina-gorevaja', 'ceslava-stanul', 'daiva-vaitkeviciute-rekasiene', 'darius-kasperaitis', 'darius-skusevicius', 'janina-simkuviene', 'jonas-gudauskas', 'jonas-purlys', 'laima-zemeckiene', 'leonard-talmont', 'lilijana-astra', 'osvaldas-sarmavicius', 'raimundas-vaitiekus', 'remigijus-zemaitaitis', 'renatas-saladzius', 'vidmantas-zilius'])
        self.assertEqual(
            by_id["remigijus-zemaitaitis"]["vienmandateCandidacy"],
            {"apygarda": "Šilalės - Šilutės", "apygardosNumeris": 33, "apygardosId": "7126", "iskele": "Partija Tvarka ir teisingumas"},
        )
        self.assertEqual(by_id["remigijus-zemaitaitis"]["vrkCandidateId"], "26249")


class SeimoSilalesSilutesVilniausSalcininku2009ResultsTests(unittest.TestCase):
    def test_winners_resolve_from_the_constituency_pages(self) -> None:
        self.assertEqual(RESULTS_TREE, "2009_seimo_rinkimai")
        payload = json.loads((SITEMAPS / f"{ELECTION_ID}.results.json").read_text(encoding="utf-8"))
        self.assertEqual(payload["stats"], {'constituencies': 2, 'winnersResolved': 2, 'unresolved': 0, 'decidedInRoundTwo': 1, 'byRunoffPlurality': 1})
        self.assertEqual(payload["elected"]["26249"]["method"], "runoff-plurality")
        self.assertEqual(payload["elected"]["26249"]["round"], 2)
        # The other constituency was decided outright in round one: no verdict
        # sentence on its page and no round-two page — the tree's first-round
        # elected-members page names the winner.
        self.assertEqual(payload["elected"]["26261"]["method"], "first-round-list")
        self.assertEqual(payload["elected"]["26261"]["round"], 1)


class SeimoSilalesSilutesVilniausSalcininku2009AnketaParserTests(unittest.TestCase):
    def setUp(self) -> None:
        self.winner, self.winner_stats = _parse("remigijus-zemaitaitis")
        self.other, _ = _parse("leonard-talmont")

    def test_expected_tabs_are_the_era_five(self) -> None:
        self.assertEqual(
            EXPECTED_TABS,
            {"anketa", "biografija", "turto-ir-pajamu-deklaracijos", "interesu-deklaracija", "kita"},
        )

    def test_top_level_fields_and_candidacy(self) -> None:
        self.assertEqual(self.winner["electionId"], "2009-lapkricio-15-seimo-silale-silute-vilnius-salcininkai")
        self.assertEqual(self.winner_stats["anomalies"], [])
        self.assertEqual(
            self.winner["kandidatavimas"],
            {
                "vrkCandidateId": "26249",
                "roles": ["vienmandate"],
                "vienmandate": {"apygarda": "Šilalės - Šilutės", "apygardosNumeris": 33, "apygardosId": "7126", "iskele": "Partija Tvarka ir teisingumas"},
                "daugiamandate": None,
                "isrinktas": True,
                "isrinktasKaip": "vienmandate",
                "rezultatuSaltinis": "https://www.vrk.lt/statiniai/puslapiai/2009_seimo_rinkimai/output_lt/rezultatai_vienmand_apygardose2/rezultatai_vienmanate_apygarda{}aktyvumasdesc2turas.html".format(self.winner["kandidatavimas"]["rezultatuSaltinis"].split("apygarda")[-1].split("aktyvumas")[0]),
                "rezultatuTuras": 2,
            },
        )
        self.assertIs(self.other["kandidatavimas"]["isrinktas"], True)
        self.assertEqual(
            list(self.winner["normalized"].keys()),
            ["profilis", "anketa", "biografija", "turto-ir-pajamu-deklaracijos", "privaciu-interesu-deklaracija", "politines-kampanijos-dalyvio-duomenys", "kita"],
        )

    def test_profile_card_and_anketa(self) -> None:
        kita = self.winner["normalized"]["profilis"]["kita"]
        # Apygarda, Iškėlė and the campaign link; unlike the 2013 cards, no
        # results links.
        self.assertEqual(kita["apygarda"]["reiksme"].startswith("Šilalės - Šilutės"), True)
        self.assertEqual(kita["iskele"]["reiksme"], "Partija Tvarka ir teisingumas")
        self.assertNotIn("i-turas", kita)
        anketa = self.winner["normalized"]["anketa"]
        self.assertEqual(anketa["gimimo-data"], "1982-05-30")
        self.assertEqual(anketa["gimimo-vieta"], "Šilutės rajono savivaldybė")
        self.assertEqual(anketa["tautybe"], "lietuvis")
        self.assertEqual(
            list(anketa["pareiskimai"].keys()),
            [
                "ar-nebaigta-teismo-paskirta-bausme",
                "ar-atliekate-karo-tarnyba",
                "ar-turite-kitos-valstybes-pilietybe",
                "ar-susijes-priesaika-uzsienio-valstybei",
                "ar-bendradarbiavote-su-uzsienio-tarnybomis",
                "ar-buvote-pripazintas-kaltu",
                "ar-buvote-pripazintas-kaltu-del-sunkaus-nusikaltimo",
                "teisiniai-argumentai",
            ],
        )
        self.assertIn("mokslo-laipsnis", anketa)
        self.assertIn("pedagoginis-vardas", anketa)
        self.assertEqual(self.winner["normalized"]["kita"], {"tekstai": ["Duomenų nėra"], "nuorodos": []})

    def test_declarations_and_campaign(self) -> None:
        turto = self.winner["normalized"]["turto-ir-pajamu-deklaracijos"]
        self.assertEqual(turto["privalomas-registruoti-turtas"], 734000)
        self.assertEqual(turto["gautos-pajamos"], 58013.64)
        self.assertEqual(turto["sumoketas-pajamu-mokestis"], 13002)
        self.assertEqual(turto["valiuta"], "Lt")
        campaign = self.winner["normalized"]["politines-kampanijos-dalyvio-duomenys"][0]
        # A represented participant: the card points at the nominating
        # party's own campaign page and carries no tabs of its own.
        self.assertEqual(campaign["statusas"], "Atstovaujamasis")
        self.assertEqual(campaign["atstovauja"]["pavadinimas"], "PARTIJA TVARKA IR TEISINGUMAS")
        self.assertEqual(campaign["aukos-pagal-sekcija"], {})


if __name__ == "__main__":
    unittest.main()
