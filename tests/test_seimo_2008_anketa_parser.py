import json
import tempfile
import unittest
from pathlib import Path

from bs4 import BeautifulSoup

from scraper.elections.seimo_2008.anketa_parser import (
    DEFAULT_RESULTS_PATH,
    parse_anketa_sample,
)
from scraper.elections.seimo_2008.candidate_samples import EXPECTED_TABS
from scraper.elections.seimo_2008.results import RESULTS_TREE
from scraper.elections.seimo_2008.sitemap import (
    DISTRICTS_URL,
    ELECTION_ID,
    LISTING_URL,
    build_sitemap_from_sample,
)
from scraper.elections.seimo_2012.sitemap import _coalition_member_from_row, extract_side_links

from local_data import require


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


class Seimo2008SitemapTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            _, cls.stats = build_sitemap_from_sample(
                sample_path=SAMPLES_ROOT,
                output_path=Path(tmp) / "sitemap.json",
            )
            cls.payload = json.loads((Path(tmp) / "sitemap.json").read_text(encoding="utf-8"))
        cls.by_vrk_id = {entry["vrkCandidateId"]: entry for entry in cls.payload["entries"]}

    def test_index_side_rows(self) -> None:
        side = extract_side_links((SAMPLES_ROOT / "list.html").read_text(encoding="utf-8"))
        kinds = {}
        for link in side:
            kinds.setdefault(link["kind"], []).append(link)
        # The coalition's two member parties, linked by their plain list pages
        # (no "_3" suffix here), and two single-member-only parties. There is
        # no self-nominated page in this index.
        self.assertEqual([link["name"] for link in kinds["koalicijos-nare"]], ["Darbo partija", "Leiboristų partija"])
        self.assertEqual([link["listKey"] for link in kinds["koalicijos-nare"]], ["3434", "3484"])
        self.assertEqual({link["coalitionListNumber"] for link in kinds["koalicijos-nare"]}, {10})
        self.assertEqual([link["declaredCount"] for link in kinds["koalicijos-nare"]], [32, 37])
        self.assertEqual([link["declaredCount"] for link in kinds["tik-vienmandatese"]], [3, 2])
        self.assertNotIn("issikele", [link["listKey"] for link in side])
        self.assertEqual(self.stats["lists"], 16)

    def test_two_structures_merge_on_the_vrk_candidate_id(self) -> None:
        stats = self.stats
        self.assertEqual(stats["districts"], 71)
        self.assertEqual(stats["list_candidacies"], 1583)
        self.assertEqual(stats["declared_list_candidates"], 1583)
        self.assertEqual(stats["list_count_mismatches"], 0)
        self.assertEqual(stats["district_candidacies"], 790)
        self.assertEqual(stats["extracted"], 1603)
        self.assertEqual(stats["dual_candidates"], 770)
        self.assertEqual(stats["list_only_candidates"], 813)
        self.assertEqual(stats["district_only_candidates"], 20)
        self.assertEqual(stats["duplicate_list_rows"], 0)
        self.assertEqual(stats["duplicate_district_rows"], 0)
        self.assertEqual(stats["skipped"], 0)
        self.assertEqual(self.payload["electionId"], "2008-seimo")
        self.assertEqual(self.payload["sourceUrl"], LISTING_URL)
        self.assertEqual(self.payload["districtsUrl"], DISTRICTS_URL)

    def test_cross_checks_reconcile(self) -> None:
        stats = self.stats
        # Only the coalition list page lacks a constituency column (130
        # rows); every other list row agrees with the constituency pages.
        self.assertEqual(stats["list_rows_without_district_column"], 130)
        self.assertEqual(stats["list_district_join_mismatch"], 0)
        # The two "tik vienmandatėse" pages list 5 people; the other 15
        # district-only candidates are the self-nominated, who have no page
        # of their own in 2008 and are counted from the constituency rows.
        self.assertEqual(stats["side_page_district_only_ids"], 5)
        self.assertEqual(stats["side_page_ids_also_on_lists"], 0)
        self.assertEqual(stats["side_page_ids_not_on_district_pages"], 0)
        self.assertEqual(stats["self_nominated_not_on_side_pages"], 15)
        self.assertEqual(stats["district_only_reconciled"], 1)

    def test_coalition_members_come_from_the_member_rows(self) -> None:
        # The coalition page's Iškėlė column links the member's plain list
        # page; the declared member counts (32, 37) are the members who also
        # stood in a constituency for that party, not the list shares (67, 63).
        members = {}
        for entry in self.payload["entries"]:
            member = (entry.get("daugiamandateCandidacy") or {}).get("koalicijosPartija")
            if member:
                members.setdefault(member, []).append(entry)
        self.assertEqual({name: len(entries) for name, entries in members.items()}, {"Darbo partija": 67, "Leiboristų partija": 63})
        self.assertEqual(
            sum(1 for entry in members["Darbo partija"] if (entry.get("vienmandateCandidacy") or {}).get("iskele") == "Darbo partija"),
            32,
        )
        self.assertEqual(
            sum(1 for entry in members["Leiboristų partija"] if (entry.get("vienmandateCandidacy") or {}).get("iskele") == "Leiboristų partija"),
            37,
        )
        grauziniene = self.by_vrk_id["21260"]
        self.assertEqual(
            grauziniene["daugiamandateCandidacy"],
            {"sarasas": "Koalicija Darbo partija + jaunimas", "sarasoNumeris": 10, "sarasoId": "3487", "numerisSarase": 2, "koalicijosPartija": "Leiboristų partija"},
        )
        # Without the member keys a plain list link is not a member link —
        # the 2012 pages' "_3" suffix still is.
        row = BeautifulSoup(
            '<tr><td>2</td><td><a href="/x/Kandidatas1/Kandidato1Anketa.html">A</a></td>'
            '<td><a href="/x/KandidatuSarasai/RinkimuOrganizacija3484.html">Leiboristų partija</a></td></tr>',
            "lxml",
        ).find("tr")
        self.assertIsNone(_coalition_member_from_row(row))
        self.assertEqual(_coalition_member_from_row(row, {"3484"}), "Leiboristų partija")
        row_2012 = BeautifulSoup(
            '<tr><td><a href="/x/KandidatuSarasai/RinkimuOrganizacija4146_3.html">Lietuvos centro partija</a></td></tr>', "lxml"
        ).find("tr")
        self.assertEqual(_coalition_member_from_row(row_2012), "Lietuvos centro partija")

    def test_entry_shapes_and_name_collisions(self) -> None:
        kubilius = self.by_vrk_id["19520"]
        self.assertEqual(kubilius["candidateId"], "andrius-kubilius")
        self.assertEqual(kubilius["roles"], ["daugiamandate", "vienmandate"])
        self.assertEqual(
            kubilius["vienmandateCandidacy"],
            {"apygarda": "Antakalnio", "apygardosNumeris": 3, "apygardosId": "6875", "iskele": "Tėvynės sąjunga - Lietuvos krikščionys demokratai"},
        )
        self.assertEqual(self.by_vrk_id["22403"]["roles"], ["daugiamandate"])  # Kirkilas, list-only
        self.assertEqual(self.stats["duplicate_candidate_ids"], 2)
        # Two Algis KAŠĖTAs stood in the same constituency for different
        # parties (born 1962 and 1971); two Arūnas RIMKUSes on different lists.
        kasetos = [entry for entry in self.payload["entries"] if entry["candidateName"] == "Algis KAŠĖTA"]
        self.assertEqual([entry["candidateId"] for entry in kasetos], ["algis-kaseta", "algis-kaseta-2"])
        self.assertEqual({entry["vienmandateCandidacy"]["apygardosNumeris"] for entry in kasetos}, {70})
        self.assertEqual(self.by_vrk_id["20790"]["vienmandateCandidacy"]["iskele"], "Lietuvos laisvės sąjunga")


class Seimo2008ResultsTests(unittest.TestCase):
    def test_members_page_resolves_all_141(self) -> None:
        self.assertEqual(RESULTS_TREE, "2008_seimo_rinkimai")
        payload = json.loads((SITEMAPS / f"{ELECTION_ID}.results.json").read_text(encoding="utf-8"))
        stats = payload["stats"]
        self.assertEqual(stats["membersListed"], 141)
        self.assertEqual(stats["membersInSitemap"], 141)
        self.assertEqual(stats["membersNotInSitemap"], 0)
        self.assertEqual(stats["seats"], {"daugiamandate": 70, "vienmandate": 71})
        self.assertEqual(stats["constituencyPages"], 71)
        self.assertEqual(stats["constituencyWinnersAgree"], 70)
        self.assertEqual(stats["constituencyWinnersDisagree"], 0)
        # The one unresolved cross-check is the Kašėta namesake pair: name
        # resolution refuses an ambiguous name; the member page's id
        # settles it (22043, the LRLS one).
        self.assertEqual(stats["constituencyWinnersUnresolved"], 1)
        self.assertEqual(payload["details"]["disagreements"], [{"constituency": "70. Varėnos - Eišiškių", "winnerName": "Algis KAŠĖTA", "reason": "name-not-resolved"}])
        self.assertEqual(payload["elected"]["22043"]["seat"], "vienmandate")
        self.assertNotIn("20790", payload["elected"])


class Seimo2008AnketaParserTests(unittest.TestCase):
    def setUp(self) -> None:
        self.kubilius, self.kubilius_stats = _parse("andrius-kubilius")
        self.grauziniene, _ = _parse("loreta-grauziniene")
        self.kirkilas, _ = _parse("gediminas-kirkilas")
        self.puodziunas, _ = _parse("valdemaras-puodziunas")
        self.dumcius, _ = _parse("arimantas-dumcius")
        self.bankauskas, self.bankauskas_stats = _parse("sigitas-bankauskas")

    def test_expected_tabs_lack_kita(self) -> None:
        self.assertEqual(
            EXPECTED_TABS,
            {"anketa", "biografija", "turto-ir-pajamu-deklaracijos", "interesu-deklaracija"},
        )
        index = json.loads((SAMPLES_ROOT / "andrius-kubilius" / "index.json").read_text(encoding="utf-8"))
        self.assertEqual(index["tabCount"], 4)
        self.assertEqual(index["missingExpectedTabs"], [])
        self.assertEqual(index["campaignSamples"], [])
        self.assertEqual(index["anomalies"], [])

    def test_top_level_fields_and_candidacy(self) -> None:
        require(DEFAULT_RESULTS_PATH)
        self.assertEqual(self.kubilius["electionId"], "2008-seimo")
        self.assertEqual(self.kubilius["candidateName"], "Andrius KUBILIUS")
        self.assertEqual(self.kubilius_stats["anomalies"], [])
        self.assertEqual(
            self.kubilius["kandidatavimas"],
            {
                "vrkCandidateId": "19520",
                "roles": ["daugiamandate", "vienmandate"],
                "vienmandate": {
                    "apygarda": "Antakalnio",
                    "apygardosNumeris": 3,
                    "apygardosId": "6875",
                    "iskele": "Tėvynės sąjunga - Lietuvos krikščionys demokratai",
                },
                "daugiamandate": {
                    "sarasas": "Tėvynės sąjunga - Lietuvos krikščionys demokratai",
                    "sarasoNumeris": 5,
                    "sarasoId": "3433",
                    "numerisSarase": 1,
                },
                "isrinktas": True,
                "isrinktasKaip": "vienmandate",
                "rezultatuSaltinis": "https://www.vrk.lt/statiniai/puslapiai/2008_seimo_rinkimai/output_lt/rinkimu_diena/isrinkti_seimo_nariai_kadencijaik.html",
            },
        )
        self.assertEqual(self.grauziniene["kandidatavimas"]["isrinktasKaip"], "daugiamandate")
        self.assertEqual(self.grauziniene["kandidatavimas"]["daugiamandate"]["koalicijosPartija"], "Leiboristų partija")
        self.assertEqual(self.kirkilas["kandidatavimas"]["roles"], ["daugiamandate"])
        self.assertIsNone(self.kirkilas["kandidatavimas"]["vienmandate"])
        self.assertEqual(self.puodziunas["kandidatavimas"]["roles"], ["vienmandate"])
        self.assertIs(self.puodziunas["kandidatavimas"]["isrinktas"], False)
        # No Kita tab and no campaign link: neither section exists.
        self.assertEqual(
            list(self.kubilius["normalized"].keys()),
            ["profilis", "anketa", "biografija", "turto-ir-pajamu-deklaracijos", "privaciu-interesu-deklaracija"],
        )

    def test_profile_card_has_no_campaign_link(self) -> None:
        kita = self.kubilius["normalized"]["profilis"]["kita"]
        self.assertEqual(
            list(kita.keys()),
            ["apygarda", "iskele", "apygarda-2", "iskele-2", "numeris-sarase", "daugiamandateje-apygardoje", "i-turas", "ii-turas"],
        )
        self.assertEqual(kita["apygarda"]["reiksme"], "Antakalnio (Nr.3)")
        self.assertEqual(kita["apygarda-2"]["reiksme"], "Daugiamandatė")
        self.assertTrue(kita["daugiamandateje-apygardoje"]["nuorodos"][0].endswith("partijos_pirmumo_balsai3433.html"))
        # The coalition nominee's card repeats Iškėlė for the member party.
        kita = self.grauziniene["normalized"]["profilis"]["kita"]
        self.assertEqual(kita["iskele-3"]["pavadinimas"], "(Iškėlė")
        self.assertEqual(kita["iskele-3"]["reiksme"], "Leiboristų partija")
        self.assertTrue(kita["iskele-3"]["nuorodos"][0].endswith("RinkimuOrganizacija3484.html"))
        kita = self.puodziunas["normalized"]["profilis"]["kita"]
        self.assertEqual(list(kita.keys()), ["apygarda", "iskele", "i-turas"])
        self.assertEqual(kita["iskele"]["reiksme"], "Išsikėlė pats")

    def test_anketa_uses_the_seimo_2012_mapping(self) -> None:
        anketa = self.kubilius["normalized"]["anketa"]
        self.assertEqual(anketa["gimimo-data"], "1956-12-08")
        self.assertEqual(
            anketa["pareiskimai"],
            {
                "ar-nebaigta-teismo-paskirta-bausme": "Neturiu",
                "ar-atliekate-karo-tarnyba": "Nesu",
                "ar-turite-kitos-valstybes-pilietybe": "Neturiu",
                "ar-susijes-priesaika-uzsienio-valstybei": "Nesu",
                "ar-bendradarbiavote-su-uzsienio-tarnybomis": "Ne",
                "ar-buvote-pripazintas-kaltu": "Ne",
                "ar-buvote-pripazintas-kaltu-del-sunkaus-nusikaltimo": "Ne",
                "teisiniai-argumentai": None,
            },
        )
        self.assertEqual(anketa["tautybe"], "Lietuvis (-ė)")
        self.assertEqual(anketa["uzsienio-kalbos"], ["Anglų", "Rusų"])
        self.assertEqual(anketa["anksciau-isrinktas"]["irasai"][0], {"institucijos-pavadinimas-pareigos": "LR Seimas", "laikotarpis": "1992 - 1996"})
        self.assertEqual(anketa["sutuoktinio-vardas-pavarde"], "Rasa Kubilienė")
        self.assertIsNone(anketa["mokslo-laipsnis"])
        self.assertIsNone(anketa["pedagoginis-vardas"])

    def test_degree_and_title_line(self) -> None:
        # "Jei turite, nurodykite mokslo laipsnį <b>…</b>, vardą <b>…</b>" —
        # one line, two answers, which the era normalizer had never mapped
        # (264 and 68 of them in this election alone).
        anketa = self.dumcius["normalized"]["anketa"]
        self.assertEqual(anketa["mokslo-laipsnis"], "Habilituotas daktaras")
        self.assertEqual(anketa["pedagoginis-vardas"], "Profesorius")
        self.assertEqual(
            [row["prompt"] for row in self.dumcius["rawData"]["anketa"]["rows"] if row.get("questionNumber") is None][:2],
            ["Jei turite, nurodykite mokslo laipsnį", ", vardą"],
        )

    def test_empty_anketa_div_is_unpublished_not_broken(self) -> None:
        # Bankauskas's anketa page has an empty content div — no "Rengiama"
        # placeholder, no table. The source says nothing; the record is a
        # card plus nulls and the anomaly is the warning, not a critical.
        self.assertEqual([event["eventType"] for event in self.bankauskas_stats["anomalies"]], ["AnketaNotPublished"])
        self.assertEqual(self.bankauskas_stats["anomalies"][0]["severity"], "warning")
        self.assertEqual(self.bankauskas["kandidatavimas"]["daugiamandate"]["numerisSarase"], 98)
        self.assertIsNone(self.bankauskas["normalized"]["anketa"]["gimimo-data"])
        self.assertEqual(self.bankauskas["normalized"]["profilis"]["kita"]["iskele-2"]["reiksme"], "Darbo partija")

    def test_declarations(self) -> None:
        # GPM305 here too, for the 2007 tax year.
        turto = self.kubilius["normalized"]["turto-ir-pajamu-deklaracijos"]
        self.assertEqual(turto["privalomas-registruoti-turtas"], 351344)
        self.assertEqual(turto["gautos-pajamos"], 79873.94)
        self.assertEqual(turto["sumoketas-pajamu-mokestis"], 20458)
        self.assertEqual(turto["valiuta"], "Lt")
        self.assertIn("nuo 2007-01-01 iki 2007-12-31", turto["pastaba"])
        # The 2008 interest form: roman-numbered sections of its own.
        interesai = self.kubilius["normalized"]["privaciu-interesu-deklaracija"]
        self.assertIn("ii-turtas", interesai)
        self.assertIn("iii-pajamos", interesai)


if __name__ == "__main__":
    unittest.main()
