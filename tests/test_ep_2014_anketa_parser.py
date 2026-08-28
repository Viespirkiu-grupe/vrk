import json
import tempfile
import unittest
from pathlib import Path

from scraper.elections.ep_2014.anketa_parser import (
    DEFAULT_RESULTS_PATH,
    normalize_ep_anketa_rows,
    parse_anketa_sample,
)
from scraper.elections.ep_2014.candidate_samples import EXPECTED_TABS
from scraper.elections.ep_2014.sitemap import (
    ELECTION_ID,
    LISTING_URL,
    build_sitemap_from_sample,
    extract_list_links,
)

from local_data import require


REPO_ROOT = Path(__file__).resolve().parents[1]
SAMPLES_ROOT = REPO_ROOT / "samples" / "html" / ELECTION_ID


def _parse(candidate_id: str) -> tuple[dict, dict]:
    with tempfile.TemporaryDirectory() as tmp:
        output_path, stats = parse_anketa_sample(
            candidate_id=candidate_id,
            samples_root=SAMPLES_ROOT,
            output_root=Path(tmp),
        )
        return json.loads(output_path.read_text(encoding="utf-8")), stats


class Ep2014SitemapTests(unittest.TestCase):
    def test_index_lists_ten_numbered_lists_with_declared_sizes(self) -> None:
        links = extract_list_links((SAMPLES_ROOT / "list.html").read_text(encoding="utf-8"))
        self.assertEqual([link["listNumber"] for link in links], list(range(1, 11)))
        self.assertEqual(links[0]["name"], "Lietuvos Respublikos liberalų sąjūdis")
        self.assertEqual(links[0]["listKey"], "4953")
        self.assertEqual(links[0]["declaredCount"], 22)
        self.assertEqual(sum(link["declaredCount"] for link in links), 215)
        self.assertTrue(links[0]["url"].endswith("KandidatuSarasai/RinkimuOrganizacija4953.html"))

    def test_index_rows_without_a_list_number_are_not_lists(self) -> None:
        # The 2012 Seimo index puts coalition member parties and
        # single-member-only parties in the same table with a prose first
        # cell; this parser serves that election too, so the rule is pinned.
        html = """
        <table>
          <tr><td align="center">1</td><td><a href="/x/RinkimuOrganizacija10_1.html">A</a></td><td>3</td></tr>
          <tr><td>koalicijos sąrašas Nr. 1</td><td><a href="/x/RinkimuOrganizacija11_3.html">B</a></td><td>2</td></tr>
          <tr><td>tik vienmandatėse</td><td><a href="/x/RinkimuOrganizacija12_4.html">C</a></td><td>5</td></tr>
          <tr><td>tik vienmandatėse</td><td><a href="/x/RinkimuOrganizacija_Issikele.html">D</a></td><td>6</td></tr>
        </table>
        """
        links = extract_list_links(html)
        self.assertEqual([(link["listNumber"], link["name"], link["listKey"]) for link in links], [(1, "A", "10-1")])

    def test_sitemap_reconciles_with_the_index(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            _, stats = build_sitemap_from_sample(
                sample_path=SAMPLES_ROOT,
                output_path=Path(tmp) / "sitemap.json",
            )
            payload = json.loads((Path(tmp) / "sitemap.json").read_text(encoding="utf-8"))

        self.assertEqual(
            stats,
            {
                "rows": 215,
                "extracted": 215,
                "skipped": 0,
                "duplicate_candidate_ids": 0,
                "lists": 10,
                "declared_candidates": 215,
                "list_count_mismatches": 0,
            },
        )
        self.assertEqual(payload["electionId"], "2014-ep")
        self.assertEqual(payload["sourceUrl"], LISTING_URL)
        self.assertEqual(len(payload["listUrls"]), 10)
        first = payload["entries"][0]
        self.assertEqual(first["candidateId"], "gintaras-steponavicius")
        self.assertEqual(first["vrkCandidateId"], "70598")
        self.assertEqual(first["roles"], ["daugiamandate"])
        self.assertEqual(
            first["daugiamandateCandidacy"],
            {
                "sarasas": "Lietuvos Respublikos liberalų sąjūdis",
                "sarasoNumeris": 1,
                "sarasoId": "4953",
                "numerisSarase": 1,
            },
        )
        positions = [entry["daugiamandateCandidacy"]["numerisSarase"] for entry in payload["entries"][:22]]
        self.assertEqual(positions, list(range(1, 23)))


class Ep2014AnketaParserTests(unittest.TestCase):
    def setUp(self) -> None:
        self.steponavicius, self.steponavicius_stats = _parse("gintaras-steponavicius")
        self.tomasevski, _ = _parse("valdemar-tomasevski")
        self.panka, _ = _parse("julius-panka")

    def test_expected_tabs_are_the_era_five(self) -> None:
        self.assertEqual(
            EXPECTED_TABS,
            {"anketa", "biografija", "turto-ir-pajamu-deklaracijos", "interesu-deklaracija", "kita"},
        )

    def test_top_level_fields_and_candidacy(self) -> None:
        require(DEFAULT_RESULTS_PATH)
        self.assertEqual(self.steponavicius["electionId"], "2014-ep")
        self.assertEqual(self.steponavicius["candidateName"], "Gintaras STEPONAVIČIUS")
        self.assertEqual(self.steponavicius_stats["anomalies"], [])
        self.assertEqual(
            self.steponavicius["kandidatavimas"],
            {
                "vrkCandidateId": "70598",
                "roles": ["daugiamandate"],
                "vienmandate": None,
                "daugiamandate": {
                    "sarasas": "Lietuvos Respublikos liberalų sąjūdis",
                    "sarasoNumeris": 1,
                    "sarasoId": "4953",
                    "numerisSarase": 1,
                },
                "isrinktas": False,
            },
        )
        self.assertEqual(self.panka["kandidatavimas"]["daugiamandate"]["sarasas"], "Tautininkų sąjunga")
        self.assertEqual(self.panka["kandidatavimas"]["daugiamandate"]["sarasoNumeris"], 7)

    def test_profile_card(self) -> None:
        kita = self.steponavicius["normalized"]["profilis"]["kita"]
        self.assertEqual(
            list(kita.keys()),
            ["iskele", "numeris-sarase", "savarankisko-politines-kampanijos-dalyvio-duomenys"],
        )
        self.assertEqual(kita["iskele"]["reiksme"], "Lietuvos Respublikos liberalų sąjūdis")
        self.assertEqual(kita["numeris-sarase"]["reiksme"], "1")
        # A coalition nominee's card repeats Iškėlė for the member party in
        # parentheses; the coalition stays the nominator.
        kita = self.tomasevski["normalized"]["profilis"]["kita"]
        self.assertEqual(
            kita["iskele"]["reiksme"],
            "Lenkų rinkimų akcijos ir Rusų aljanso koalicija „Valdemaro Tomaševskio blokas“",
        )
        self.assertEqual(kita["iskele-2"]["reiksme"], "Lietuvos lenkų rinkimų akcija")
        self.assertEqual(
            self.tomasevski["kandidatavimas"]["daugiamandate"]["sarasas"], kita["iskele"]["reiksme"]
        )

    def test_ep_question_mapping(self) -> None:
        anketa = self.steponavicius["normalized"]["anketa"]
        self.assertEqual(
            list(anketa.keys()),
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
            ],
        )
        # The EP form numbers the birth date Q3.
        self.assertEqual(anketa["gimimo-data"], "1967-07-23")
        self.assertEqual(anketa["adresas"], "Vilnius")
        self.assertEqual(
            anketa["pareiskimai"],
            {
                "ar-nebaigta-teismo-paskirta-bausme": "Neturiu",
                "ar-atliekate-karo-tarnyba": "Nesu",
                "ar-turite-kitos-valstybes-pilietybe": "Neturiu",
                "kitos-valstybes-pilietybe-valstybe": None,
                "ar-atimta-balsavimo-teise-kitoje-valstybeje": "Ne",
                "ar-bendradarbiavote-su-uzsienio-tarnybomis": "Ne",
                "ar-buvote-pripazintas-kaltu": "Ne",
                "ar-buvote-pripazintas-kaltu-del-sunkaus-nusikaltimo": "Ne",
            },
        )
        self.assertEqual(anketa["gimimo-vieta"], "Klaipėda")
        self.assertEqual(anketa["tautybe"], "lietuvis")
        self.assertEqual(anketa["issilavinimas"]["irasai"][0]["mokymo-istaigos-pavadinimas"], "Vilniaus universitetas")
        self.assertEqual(anketa["uzsienio-kalbos"], ["anglų", "rusų"])
        self.assertEqual(
            anketa["anksciau-isrinktas"]["irasai"],
            [
                {"institucijos-pavadinimas-pareigos": "Vilniaus miesto savivaldybės taryba", "laikotarpis": "1997 - 2000"},
                {"institucijos-pavadinimas-pareigos": "Lietuvos Respublikos Seimas", "laikotarpis": "2000 - 2016"},
            ],
        )
        self.assertEqual(anketa["seimine-padetis"], "išsiskyręs")
        self.assertIsNone(anketa["sutuoktinio-vardas-pavarde"])
        self.assertEqual(anketa["vaiku-vardai-pavardes"], "Urtė, Mykolas")

    def test_mapping_reads_q3_not_q5(self) -> None:
        rows = [
            {"questionNumber": "3", "prompt": "3. Gimimo data", "answer": "1970-01-02"},
            {"questionNumber": "5", "prompt": "5. Kažkas kita", "answer": "x"},
            {"questionNumber": "8.3.1", "prompt": "8.3.1 Jeigu turite…", "answer": "Lenkija"},
        ]
        normalized = normalize_ep_anketa_rows(rows)
        self.assertEqual(normalized["gimimo-data"], "1970-01-02")
        self.assertEqual(normalized["pareiskimai"]["kitos-valstybes-pilietybe-valstybe"], "Lenkija")
        self.assertNotIn("kita-apie-save", normalized)

    def test_declarations_and_campaign(self) -> None:
        turto = self.steponavicius["normalized"]["turto-ir-pajamu-deklaracijos"]
        self.assertEqual(turto["privalomas-registruoti-turtas"], 383000)
        self.assertEqual(turto["gautos-pajamos"], 101494.8)
        self.assertEqual(turto["sumoketas-pajamu-mokestis"], 14587)
        self.assertEqual(turto["valiuta"], "Lt")
        campaign = self.steponavicius["normalized"]["politines-kampanijos-dalyvio-duomenys"][0]
        self.assertEqual(campaign["statusas"], "Savarankiškas")
        self.assertEqual(campaign["izdininkas"]["vardas-pavarde"], "ŽIVILĖ KRISTUTIENĖ")
        self.assertEqual(len(campaign["sutartys"]), 49)


if __name__ == "__main__":
    unittest.main()
