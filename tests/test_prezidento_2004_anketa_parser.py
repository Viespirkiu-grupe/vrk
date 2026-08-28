import json
import tempfile
import unittest
from pathlib import Path

from scraper.elections.prezidento_2004.anketa_parser import (
    DEFAULT_RESULTS_PATH,
    parse_anketa_sample,
    parse_listing_card,
)
from scraper.elections.prezidento_2004.candidate_samples import (
    BASE_EXPECTED_TABS,
    UNPUBLISHED_TABS,
    expected_tabs_for_entry,
)
from scraper.elections.prezidento_2004.results import (
    ROUND_PAGES,
    RESULTS_ROOT,
    build_results,
    parse_round_page,
)
from scraper.elections.prezidento_2004.sitemap import (
    ELECTION_ID,
    build_sitemap_from_sample,
)
from scraper.shared.word_doc import WordDocError, extract_text

from local_data import require


REPO_ROOT = Path(__file__).resolve().parents[1]
SAMPLES_ROOT = REPO_ROOT / "samples" / "html" / ELECTION_ID
RESULTS_DIR = REPO_ROOT / "samples" / "results" / ELECTION_ID
SITEMAPS = REPO_ROOT / "sitemaps"

CANDIDATE_IDS = [
    "valdas-adamkus",
    "petras-austrevicius",
    "vilija-blinkeviciute",
    "ceslovas-jursenas",
    "kazimira-danute-prunskiene",
]


def _parse(candidate_id: str) -> tuple[dict, dict]:
    with tempfile.TemporaryDirectory() as tmp:
        output_path, stats = parse_anketa_sample(
            candidate_id=candidate_id,
            samples_root=SAMPLES_ROOT,
            output_root=Path(tmp),
            results_path=SITEMAPS / f"{ELECTION_ID}.results.json",
        )
        return json.loads(output_path.read_text(encoding="utf-8")), stats


class Prezidento2004SitemapTests(unittest.TestCase):
    def test_listing_yields_the_five_cards(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            _, stats = build_sitemap_from_sample(
                sample_path=SAMPLES_ROOT,
                output_path=Path(tmp) / "sitemap.json",
            )
            payload = json.loads((Path(tmp) / "sitemap.json").read_text(encoding="utf-8"))

        self.assertEqual(stats["rows"], 5)
        self.assertEqual(stats["extracted"], 5)
        # Auštrevičius published no programme; everyone else did.
        self.assertEqual(stats["withPrograma"], 4)
        self.assertEqual(stats["withWebsite"], 5)

        entries = {entry["candidateId"]: entry for entry in payload["entries"]}
        self.assertEqual(set(entries), set(CANDIDATE_IDS))

        # Both id spaces: the card anchor (= the declaration page id) and
        # the registration record id (= the trustee link, reused by the
        # results tree as rez_kand_l_<RID>_…).
        adamkus = entries["valdas-adamkus"]
        self.assertEqual(adamkus["vrkCandidateId"], "250279")
        self.assertEqual(adamkus["vrkRegistrationId"], "1759632")
        self.assertEqual(adamkus["registeredDate"], "2004-05-12")
        self.assertEqual(adamkus["decision"], "VRK sprendimu Nr. 120")
        self.assertIn("lrs.lt", adamkus["decisionUrl"])
        self.assertTrue(adamkus["biografijaUrl"].endswith("adamkus.doc"))
        self.assertTrue(adamkus["programaUrl"].endswith("prog_adamkus.doc"))
        # The health certificate is Adamkus's card only.
        self.assertTrue(adamkus["sveikatosPazymejimasUrl"].endswith("s_adamkus.gif"))
        for candidate_id in CANDIDATE_IDS[1:]:
            self.assertIsNone(entries[candidate_id]["sveikatosPazymejimasUrl"])

        austrevicius = entries["petras-austrevicius"]
        self.assertIsNone(austrevicius["programaUrl"])
        self.assertEqual(austrevicius["decision"], "VRK sprendimu Nr. 122")

        jursenas = entries["ceslovas-jursenas"]
        self.assertEqual(jursenas["registeredDate"], "2004-05-04")
        self.assertEqual(jursenas["decision"], "VRK sprendimu Nr. 90")

        for entry in entries.values():
            self.assertTrue(entry["deklaracijaUrl"].endswith(f"kand_pajam_l_{entry['vrkCandidateId']}.htm"))
            self.assertTrue(entry["patiketiniaiUrl"].endswith(f"patiketiniai_l_{entry['vrkRegistrationId']}.htm"))
            self.assertTrue(entry["photoUrl"])
            self.assertTrue(entry["nuotraukaPageUrl"])


class Prezidento2004ExpectedTabsTests(unittest.TestCase):
    def test_programa_expected_only_where_linked(self) -> None:
        self.assertEqual(
            expected_tabs_for_entry({"programaUrl": "x"}),
            BASE_EXPECTED_TABS | {"programa"},
        )
        self.assertEqual(expected_tabs_for_entry({"programaUrl": None}), BASE_EXPECTED_TABS)

    def test_trustees_are_the_unpublished_tab(self) -> None:
        # Linked on every card, a 404 for all five — recorded, not fetched.
        self.assertEqual(UNPUBLISHED_TABS, {"patiketiniai"})


class WordDocTests(unittest.TestCase):
    def test_biography_doc_extracts_document_order_text(self) -> None:
        text = extract_text((SAMPLES_ROOT / "valdas-adamkus" / "biografija.doc").read_bytes())
        self.assertTrue(text.startswith("Kandidatas į Respublikos\nPREZIDENTUS\nValdas ADAMKUS"))
        self.assertIn("gimė 1926 m. lapkričio 3 d. Kaune", text)
        # The page-header subdocument ("Kandidatas į Respublikos
        # Prezidentus") sits beyond ccpText and must not leak into the tail.
        self.assertTrue(text.endswith("garbės profesorius."))

    def test_programa_doc_extracts(self) -> None:
        text = extract_text((SAMPLES_ROOT / "valdas-adamkus" / "programa.doc").read_bytes())
        self.assertIn("Europietišką gerovę į kiekvienus namus!", text)
        self.assertTrue(text.endswith("Valdas Adamkus"))

    def test_non_ole_bytes_are_refused(self) -> None:
        with self.assertRaises(WordDocError):
            extract_text(b"<html>not a doc</html>")


class Prezidento2004CardTests(unittest.TestCase):
    def test_card_is_found_by_candidate_anchor(self) -> None:
        listing_html = (SAMPLES_ROOT / "valdas-adamkus" / "anketa.html").read_text(encoding="utf-8")
        profile = parse_listing_card(listing_html, "250279")
        self.assertEqual(profile["candidateDisplayName"], "Valdas ADAMKUS")
        fields = {field["key"]: field for field in profile["fields"]}
        self.assertEqual(
            set(fields),
            {"Registracija", "Pareiškimas", "Sveikatos pažymėjimas", "Interneto svetainė"},
        )
        self.assertIn("registruotas kandidatu", fields["Registracija"]["displayValue"])
        self.assertIn("lrs.lt", fields["Registracija"]["urls"][0])
        self.assertTrue(fields["Pareiškimas"]["urls"][0].endswith("p_adamkus.gif"))
        self.assertEqual(fields["Interneto svetainė"]["displayValue"], "http://www.adamkus.lt")
        self.assertIsNone(parse_listing_card(listing_html, "999999"))


class Prezidento2004RecordTests(unittest.TestCase):
    def test_winner_record(self) -> None:
        require(DEFAULT_RESULTS_PATH)
        record, stats = _parse("valdas-adamkus")
        candidacy = record["kandidatavimas"]
        self.assertTrue(candidacy["isrinktas"])
        self.assertEqual(candidacy["isrinktasKaip"], "prezidentas")
        self.assertEqual(candidacy["rezultatuTuras"], 2)
        # Both rounds' national votes, joined by the registration id.
        rounds = {row["turas"]: row for row in candidacy["turai"]}
        self.assertEqual(set(rounds), {1, 2})
        self.assertEqual(rounds[1]["balsai"], 387837)
        self.assertEqual(rounds[1]["balsai-apylinkese"], 329404)
        self.assertEqual(rounds[1]["balsai-pastu"], 58433)
        self.assertEqual(rounds[1]["procentai-nuo-galiojanciu"], 31.14)
        self.assertEqual(rounds[2]["balsai"], 723891)
        self.assertEqual(rounds[2]["procentai-nuo-galiojanciu"], 52.65)

        # The birth date is recovered from the biography prose and marked
        # as such — the 1990s archive family's convention.
        anketa = record["normalized"]["anketa"]
        self.assertEqual(anketa["gimimo-data"], "1926-11-03")
        self.assertEqual(anketa["gimimo-data-saltinis"], "biografijos-tekstas")

        # The full portrait replaces the card thumbnail as the photo.
        self.assertTrue(record["normalized"]["profilis"]["nuotrauka"].endswith("19_32611030033d.jpg"))
        self.assertEqual(
            record["rawData"]["nuotrauka"]["thumbnailUrl"].rsplit("/", 1)[-1],
            "19_32611030033.jpg",
        )

        self.assertIn("Rinkimų programa", record["normalized"]["programa"]["tekstas"])
        declarations = record["normalized"]["turto-ir-pajamu-deklaracijos"]
        # Adamkus filed the individual-form asset declaration, with an
        # explicit 0 Lt for registered property — the page's own number.
        self.assertEqual(declarations["privalomas-registruoti-turtas"], 0)
        self.assertEqual(declarations["pinigines-lesos"], 127749)
        self.assertEqual(declarations["gautos-pajamos"], 57408)
        self.assertEqual(stats["anomalies"], [])

    def test_runoff_loser_and_first_round_losers(self) -> None:
        require(DEFAULT_RESULTS_PATH)
        record, _ = _parse("kazimira-danute-prunskiene")
        candidacy = record["kandidatavimas"]
        self.assertFalse(candidacy["isrinktas"])
        rounds = {row["turas"]: row for row in candidacy["turai"]}
        self.assertEqual(set(rounds), {1, 2})
        self.assertEqual(rounds[2]["balsai"], 651024)
        self.assertEqual(record["normalized"]["anketa"]["gimimo-data"], "1943-02-26")

        record, _ = _parse("ceslovas-jursenas")
        candidacy = record["kandidatavimas"]
        self.assertFalse(candidacy["isrinktas"])
        self.assertEqual([row["turas"] for row in candidacy["turai"]], [1])
        self.assertEqual(candidacy["turai"][0]["balsai"], 147610)
        # The family's usual declaration page parses unchanged: the family
        # asset form with the roman-headed sections.
        declarations = record["normalized"]["turto-ir-pajamu-deklaracijos"]
        self.assertEqual(declarations["privalomas-registruoti-turtas"], 88400)
        self.assertEqual(declarations["gautos-pajamos"], 100212)
        self.assertEqual(declarations["valiuta"], "Lt")

    def test_candidate_without_programa(self) -> None:
        record, stats = _parse("petras-austrevicius")
        self.assertNotIn("programa", record["rawData"])
        self.assertNotIn("programa", record["normalized"])
        self.assertIn("biografija", record["normalized"])
        self.assertEqual(record["normalized"]["anketa"]["gimimo-data"], "1963-05-16")
        self.assertEqual(stats["anomalies"], [])

    def test_all_five_birth_dates_recovered(self) -> None:
        expected = {
            "valdas-adamkus": "1926-11-03",
            "petras-austrevicius": "1963-05-16",
            "vilija-blinkeviciute": "1960-03-03",
            "ceslovas-jursenas": "1938-05-18",
            "kazimira-danute-prunskiene": "1943-02-26",
        }
        for candidate_id, birth_date in expected.items():
            with self.subTest(candidate_id):
                record, _ = _parse(candidate_id)
                self.assertEqual(record["normalized"]["anketa"]["gimimo-data"], birth_date)


class Prezidento2004ResultsTests(unittest.TestCase):
    def _round_html(self, round_number: int) -> str:
        url = RESULTS_ROOT + ROUND_PAGES[round_number]
        path = RESULTS_DIR / url.rsplit("/", 1)[-1]
        if not path.exists():
            # fetch_page saves under a URL-derived name; find it.
            candidates = list(RESULTS_DIR.glob(f"*{ROUND_PAGES[round_number]}*"))
            self.assertTrue(candidates, f"no saved copy of {url}")
            path = candidates[0]
        return path.read_text(encoding="utf-8")

    def test_first_round_page(self) -> None:
        url = RESULTS_ROOT + ROUND_PAGES[1]
        page = parse_round_page(self._round_html(1), url)
        self.assertEqual(page["summary"]["galiojantys-biuleteniai"], 1245360)
        self.assertEqual(page["summary"]["negaliojantys-biuleteniai"], 39707)
        self.assertEqual(page["summary"]["rinkeju-skaicius"], 2655309)
        self.assertEqual(len(page["candidates"]), 5)
        self.assertEqual(sum(row["balsai"] for row in page["candidates"]), 1245360)
        bold = {row["name"] for row in page["candidates"] if row["bold"]}
        self.assertEqual(bold, {"Valdas ADAMKUS", "Kazimira Danutė PRUNSKIENĖ"})
        self.assertIsNone(page["winnerVrkCandidateId"])

    def test_runoff_page_names_the_winner_by_card_anchor(self) -> None:
        url = RESULTS_ROOT + ROUND_PAGES[2]
        page = parse_round_page(self._round_html(2), url)
        self.assertEqual(len(page["candidates"]), 2)
        self.assertEqual(page["winnerVrkCandidateId"], "250279")
        self.assertEqual(page["winnerName"], "Valdas ADAMKUS")
        self.assertEqual(page["summary"]["galiojantys-biuleteniai"], 1374915)

    def test_build_results_reconciles(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output_path, stats = build_results(
                sitemap_path=SITEMAPS / f"{ELECTION_ID}.json",
                results_dir=RESULTS_DIR,
                output_path=Path(tmp) / "results.json",
            )
            payload = json.loads(output_path.read_text(encoding="utf-8"))

        self.assertEqual(stats["candidatesRound1"], 5)
        self.assertEqual(stats["candidatesRound2"], 2)
        self.assertEqual(stats["notInSitemap"], 0)
        self.assertTrue(stats["boldRound1MatchesRound2"])
        self.assertEqual(stats["voteSumMismatches"], 0)
        self.assertEqual(stats["winnersResolved"], 1)
        self.assertEqual(list(payload["elected"]), ["250279"])
        self.assertEqual(payload["elected"]["250279"]["seat"], "prezidentas")
        self.assertEqual(payload["elected"]["250279"]["round"], 2)


if __name__ == "__main__":
    unittest.main()
