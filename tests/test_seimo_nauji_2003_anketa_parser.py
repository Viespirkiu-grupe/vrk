"""The 2003-06-15 new Seimas election (GitHub issue #29).

The four page-level deltas from the 2004 static site each get a test that
fails if the reader regresses to the era's own: the card row is not a
question, the birth date is Q5, the Q9.x footnote marker does not hide the
question number, and the record tables have no header row.
"""

import json
import tempfile
import unittest
from pathlib import Path

from bs4 import BeautifulSoup

from scraper.elections.ep_2004.anketa_parser import _parse_record_table as ep_2004_record_table
from scraper.elections.savivaldybiu_2002.anketa_parser import normalize_deklaracija
from scraper.elections.seimo_nauji_2003.anketa_parser import (
    DEKLARACIJA_RANGE_ITEMS,
    DEKLARACIJA_SINGLE_ITEMS,
    _parse_record_table,
    normalize_seimo_2003_anketa_rows,
    parse_anketa_html,
    parse_anketa_sample,
    parse_deklaracija_html,
)
from scraper.elections.seimo_nauji_2003.candidate_samples import EXPECTED_TABS
from scraper.elections.seimo_nauji_2003.results import (
    DISTRICT_PAGES,
    INDEX_PAGE,
    RESULTS_ROOT,
    build_results,
    parse_district_page,
)
from scraper.elections.seimo_nauji_2003.sitemap import (
    DISTRICTS_URL,
    ELECTION_ID,
    PARTIES_URL,
    build_sitemap_from_sample,
)
from scraper.shared.election_results import page_path

REPO_ROOT = Path(__file__).resolve().parents[1]
SAMPLES_ROOT = REPO_ROOT / "samples" / "html" / ELECTION_ID
RESULTS_DIR = REPO_ROOT / "samples" / "results" / ELECTION_ID
SITEMAPS = REPO_ROOT / "sitemaps"
CANDIDATES = "https://www.vrk.lt/statiniai/puslapiai/rinkimai/2003/seimas/kandidatai/"


def _parse(candidate_id: str) -> tuple[dict, dict]:
    with tempfile.TemporaryDirectory() as tmp:
        output_path, stats = parse_anketa_sample(
            candidate_id=candidate_id, samples_root=SAMPLES_ROOT, output_root=Path(tmp)
        )
        return json.loads(output_path.read_text(encoding="utf-8")), stats


def _anketa_html(candidate_id: str) -> str:
    return (SAMPLES_ROOT / candidate_id / "anketa.html").read_text(encoding="utf-8")


class SeimoNauji2003SitemapTests(unittest.TestCase):
    def test_four_constituencies_twenty_seven_candidates(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            _, stats = build_sitemap_from_sample(
                sample_path=SAMPLES_ROOT, output_path=Path(tmp) / "sitemap.json"
            )
            payload = json.loads((Path(tmp) / "sitemap.json").read_text(encoding="utf-8"))
        self.assertEqual(
            payload["stats"],
            {
                "rows": 27,
                "extracted": 27,
                "duplicateCandidateIds": 0,
                "districts": 4,
                "parties": 12,
                "partyPageRows": 27,
                # The two listing structures agree candidate for candidate.
                "partyPageDiff": 0,
                # Every 2003 candidate was nominated by a party.
                "selfNominated": 0,
            },
        )
        self.assertEqual(stats["skipped"], 0)
        self.assertEqual(payload["sourceUrl"], DISTRICTS_URL)
        self.assertEqual(payload["partiesUrl"], PARTIES_URL)
        self.assertEqual(
            payload["districtUrls"],
            [CANDIDATES + f"w3_smn_kand.apg_kand_vien_l-id={i}.htm" for i in (1476, 1477, 1478, 1479)],
        )
        by_id = {entry["candidateId"]: entry for entry in payload["entries"]}
        self.assertEqual(
            by_id["vilija-aleknaite-abramikiene"],
            {
                "candidateName": "Vilija Aleknaitė Abramikienė",
                "candidateId": "vilija-aleknaite-abramikiene",
                "url": CANDIDATES + "w3_smn_kand.kand_anketa_l-id=241265.htm",
                "vrkCandidateId": "241265",
                "roles": ["vienmandate"],
                "vienmandateCandidacy": {
                    "apygarda": "Senamiesčio",
                    "apygardosNumeris": 2,
                    "apygardosId": "1476",
                    "iskele": "Tėvynės sąjunga (Lietuvos konservatoriai)",
                },
            },
        )

    def test_the_four_constituency_numbers_are_read_off_the_index(self) -> None:
        # The index writes "2&nbsp;<a>Senamiesčio</a>" with no trailing dot,
        # unlike 2004's "N."; a number lost here would land as null in every
        # record's kandidatavimas.
        payload = json.loads((SITEMAPS / f"{ELECTION_ID}.json").read_text(encoding="utf-8"))
        seats = {
            (e["vienmandateCandidacy"]["apygardosNumeris"], e["vienmandateCandidacy"]["apygarda"])
            for e in payload["entries"]
        }
        self.assertEqual(
            seats, {(2, "Senamiesčio"), (3, "Antakalnio"), (6, "Šeškinės"), (26, "Nevėžio")}
        )


class SeimoNauji2003ResultsTests(unittest.TestCase):
    def test_nobody_was_elected_and_every_constituency_says_so(self) -> None:
        payload = json.loads((SITEMAPS / f"{ELECTION_ID}.results.json").read_text(encoding="utf-8"))
        self.assertEqual(payload["elected"], {})
        self.assertEqual(
            payload["stats"],
            {
                "seats": 4,
                "constituencies": 4,
                "constituenciesNotHeld": 4,
                "indexNotHeldNote": True,
                "candidates": 27,
                "candidatesWithVotes": 27,
                "candidatesWithoutVotes": 0,
                "rowsNotInSitemap": 0,
                # Each page's rows add up to the valid ballots it declares.
                "voteTotalMismatches": 0,
                "elected": 0,
            },
        )
        with tempfile.TemporaryDirectory() as tmp:
            _, stats = build_results(
                sitemap_path=SITEMAPS / f"{ELECTION_ID}.json",
                results_dir=RESULTS_DIR,
                output_path=Path(tmp) / "r.json",
            )
        self.assertEqual(stats, payload["stats"])

    def test_senamiescio_turnout_is_the_lowest_of_the_four(self) -> None:
        url = RESULTS_ROOT + DISTRICT_PAGES["1476"]
        page = parse_district_page(page_path(RESULTS_DIR, url).read_text(encoding="utf-8"), url)
        self.assertFalse(page["held"])
        self.assertEqual(page["constituencyName"], "Senamiesčio")
        self.assertEqual(page["constituencyNumber"], 2)
        self.assertEqual(
            page["summary"],
            {
                "rinkeju-skaicius": 37523,
                "dalyvavo": 3476,
                "aktyvumas-procentais": 9.26,
                "negaliojantys-biuleteniai": 107,
                # Read past "negaliojančių biuletenių", which the page prints
                # first and which the same pattern would otherwise match.
                "galiojantys-biuleteniai": 3369,
            },
        )
        self.assertEqual(len(page["candidates"]), 7)
        self.assertEqual(
            page["candidates"][0],
            {
                "vrkCandidateId": "241265",
                "name": "Vilija Aleknaitė Abramikienė",
                "vieta": 1,
                "balsai-apylinkese": 1019,
                "balsai-pastu": 197,
                "balsai": 1216,
                "procentai-nuo-galiojanciu": 36.09,
            },
        )

    def test_the_index_page_carries_the_not_held_footnote(self) -> None:
        self.assertEqual(INDEX_PAGE, "rez_v_apg_sar_l_17_1_1.htm")
        payload = json.loads((SITEMAPS / f"{ELECTION_ID}.results.json").read_text(encoding="utf-8"))
        self.assertEqual(len(payload["sources"]), 5)
        self.assertTrue(payload["sources"][0].endswith(INDEX_PAGE))


class SeimoNauji2003AnketaParserTests(unittest.TestCase):
    def test_expected_tabs(self) -> None:
        self.assertEqual(EXPECTED_TABS, {"anketa", "biografija", "turto-ir-pajamu-deklaracijos"})

    def test_the_card_row_is_the_profile_and_not_two_questions(self) -> None:
        # The card is the question table's first row and classed r2 like any
        # other, so the era's row walk reads "Apygarda:"/"Iškėlė:" as answers.
        parsed = parse_anketa_html(_anketa_html("vilija-aleknaite-abramikiene"))
        self.assertEqual(parsed["anketa"]["stats"], {"rowCount": 24, "answeredRowCount": 24})
        self.assertNotIn("Apygarda:", [row["prompt"] for row in parsed["anketa"]["rows"]])
        self.assertEqual(
            [(field["key"], field["displayValue"]) for field in parsed["profile"]["fields"]],
            [
                ("Apygarda", "Senamiesčio (Nr.2)"),
                ("Iškėlė", "Tėvynės sąjunga (Lietuvos konservatoriai)"),
            ],
        )
        # The photo's src carries a stray space before the filename.
        self.assertEqual(
            parsed["profile"]["photoSrc"], CANDIDATES + "45705040120_17.jpg"
        )

    def test_birth_date_is_question_five(self) -> None:
        parsed = parse_anketa_html(_anketa_html("vilija-aleknaite-abramikiene"))
        self.assertEqual(parsed["anketa"]["normalized"]["gimimo-data"], "1957-05-04")
        # The 2004 mapping's Q3 does not exist on this form.
        rows = parsed["anketa"]["rows"]
        self.assertNotIn("3", [row["questionNumber"] for row in rows])

    def test_the_q9_footnote_marker_does_not_hide_the_question_number(self) -> None:
        # "9.1<sup>*</sup> Ar ne pagal…" — the marker splits the text run.
        self.assertIn("9.1<sup>*</sup>", _anketa_html("vilija-aleknaite-abramikiene"))
        rows = parse_anketa_html(_anketa_html("vilija-aleknaite-abramikiene"))["anketa"]["rows"]
        numbered = {row["questionNumber"] for row in rows}
        self.assertTrue({"9.1", "9.2", "9.3"} <= numbered)
        declarations = parse_anketa_html(_anketa_html("vilija-aleknaite-abramikiene"))["anketa"][
            "normalized"
        ]["pareiskimai"]
        self.assertEqual(declarations["ar-bendradarbiavote-su-uzsienio-tarnybomis"], "Nėra")
        self.assertEqual(declarations["ar-buvote-pripazintas-kaltu"], "Nėra")
        self.assertEqual(declarations["ar-buvote-pripazintas-kaltu-del-sunkaus-nusikaltimo"], "Nebuvo")

    def test_record_tables_have_no_header_row(self) -> None:
        # The one candidate whose Q12 table has two rows shows the damage the
        # era's reader does: it takes row one for column names.
        table = BeautifulSoup(
            """<table><tr><td><b>Aukštasis</b></td><td><b>&nbsp;</b></td><td><b>&nbsp;</b></td>
            <td><b>&nbsp;</b></td></tr><tr><td><b>Aukštasis</b></td>
            <td><b>Lietuvos konservatorija</b></td><td><b>koncertinis atlikėjas</b></td>
            <td><b>1980</b></td></tr></table>""",
            "lxml",
        ).find("table")
        self.assertEqual(
            _parse_record_table(table),
            [
                {
                    "issilavinimas": "Aukštasis",
                    "mokyklos-istaigos-pavadinimas": "",
                    "specialybe": "",
                    "baigimo-metai": "",
                },
                {
                    "issilavinimas": "Aukštasis",
                    "mokyklos-istaigos-pavadinimas": "Lietuvos konservatorija",
                    "specialybe": "koncertinis atlikėjas",
                    "baigimo-metai": "1980",
                },
            ],
        )
        self.assertEqual(ep_2004_record_table(table), [{"Aukštasis": "Aukštasis", "": "1980"}])

    def test_every_candidate_has_an_education_record(self) -> None:
        # 21 of the 27 print exactly one education row, which the era's
        # reader would have swallowed whole as column names.
        counts = []
        for directory in sorted(SAMPLES_ROOT.iterdir()):
            if not (directory / "anketa.html").exists():
                continue
            normalized = parse_anketa_html(
                (directory / "anketa.html").read_text(encoding="utf-8")
            )["anketa"]["normalized"]
            counts.append(len(normalized["issilavinimas"]["irasai"]))
        self.assertEqual(len(counts), 27)
        self.assertEqual(counts.count(0), 0)
        self.assertEqual(counts.count(1), 21)

    def test_record(self) -> None:
        record, stats = _parse("vilija-aleknaite-abramikiene")
        self.assertEqual(record["electionId"], ELECTION_ID)
        self.assertEqual(stats["anomalies"], [])
        self.assertEqual(
            record["kandidatavimas"],
            {
                "vrkCandidateId": "241265",
                "roles": ["vienmandate"],
                "vienmandate": {
                    "apygarda": "Senamiesčio",
                    "apygardosNumeris": 2,
                    "apygardosId": "1476",
                    "iskele": "Tėvynės sąjunga (Lietuvos konservatoriai)",
                },
                "daugiamandate": None,
                # Known false: the constituency page states the vote failed.
                "isrinktas": False,
                "turai": [
                    {
                        "turas": 1,
                        "apygardos-numeris": 2,
                        "balsai-apylinkese": 1019,
                        "balsai-pastu": 197,
                        "balsai": 1216,
                        "procentai-nuo-galiojanciu": 36.09,
                        "vieta": 1,
                        "saltinis": RESULTS_ROOT + DISTRICT_PAGES["1476"],
                    }
                ],
            },
        )
        anketa = record["normalized"]["anketa"]
        self.assertEqual(anketa["adresas"], "Vilnius")
        self.assertEqual(anketa["uzsienio-kalbos"], ["Rusų", "Vokiečių", "Lenkų", "Anglų"])
        self.assertEqual(anketa["sutuoktinio-vardas-pavarde"], "Kęstutis")
        self.assertEqual(
            anketa["anksciau-isrinktas"]["irasai"],
            [
                {"institucijos-pavadinimas-pareigos": "Lietuvos Respublikos Seimas, narė", "laikotarpis": "1996 - 2000"},
                {"institucijos-pavadinimas-pareigos": "Lietuvos Respublikos Seimas, narė", "laikotarpis": "1992 - 1996"},
            ],
        )
        # "Nenurodė" is the corpus's missing-value marker.
        self.assertIsNone(anketa["mokslo-laipsnis"])
        self.assertIsNone(anketa["visuomenine-veikla"])
        self.assertEqual(list(record["normalized"]["profilis"]["kita"]), ["apygarda", "iskele"])
        self.assertTrue(
            record["normalized"]["biografija"]["tekstas"].startswith("Vilija ALEKNAITĖ-ABRAMIKIENĖ")
        )

    def test_the_one_q9_explanation_the_field_carries(self) -> None:
        # The page prints it as an unlabelled emphasised row right after 9.3,
        # exactly as the 2004 pages do; one of the 27 has one.
        record, _ = _parse("viktor-balakin")
        self.assertEqual(
            record["normalized"]["anketa"]["pareiskimai"]["teisiniai-argumentai"],
            "1973 - 1991 - LTSR valst. saugumo k - to vyr. inžinierius, majoras",
        )
        others, _ = _parse("algirdas-paleckis")
        self.assertIsNone(others["normalized"]["anketa"]["pareiskimai"]["teisiniai-argumentai"])


class SeimoNauji2003DeklaracijaTests(unittest.TestCase):
    def _declaration(self, candidate_id: str) -> dict:
        return parse_deklaracija_html(
            (SAMPLES_ROOT / candidate_id / "turto-ir-pajamu-deklaracijos.html").read_text(
                encoding="utf-8"
            )
        )

    def test_the_resident_form(self) -> None:
        record, _ = _parse("vilija-aleknaite-abramikiene")
        declaration = record["normalized"]["turto-ir-pajamu-deklaracijos"]
        self.assertEqual(declaration["forma"], "Lietuvos Respublikos gyventojo turto ir pajamų deklaracija")
        self.assertEqual(declaration["israsa-isdave"], "Vilniaus apskrities VMI Vilniaus skyrius")
        self.assertEqual(declaration["isdavimo-data"], "2003-05-08")
        self.assertEqual(declaration["gautos-pajamos"], 39777)
        self.assertEqual(declaration["sumoketas-pajamu-mokestis"], 7889)
        self.assertEqual(declaration["suteiktos-paskolos"], 34080)
        self.assertEqual(declaration["turtas-ir-vertybiniai-popieriai-laikotarpio-pabaigoje"], 627668)
        self.assertEqual(declaration["pinigines-lesos"], 44829)
        self.assertEqual(declaration["valiuta"], "Lt")
        # The 2002 form sums registrable assets with securities, so the
        # modern split is unrecoverable here too.
        self.assertIsNone(declaration["privalomas-registruoti-turtas"])
        self.assertNotIn("nezinomos-eilutes", declaration)

    def test_both_forms_are_printed_and_every_line_is_recognised(self) -> None:
        forms: dict[str, int] = {}
        unknown: list[str] = []
        for directory in sorted(SAMPLES_ROOT.iterdir()):
            path = directory / "turto-ir-pajamu-deklaracijos.html"
            if not path.exists():
                continue
            record, _ = _parse(directory.name)
            declaration = record["normalized"]["turto-ir-pajamu-deklaracijos"]
            forms[declaration["forma"]] = forms.get(declaration["forma"], 0) + 1
            unknown.extend(declaration.get("nezinomos-eilutes") or [])
        self.assertEqual(
            forms,
            {
                "Lietuvos Respublikos gyventojo turto ir pajamų deklaracija": 18,
                "Lietuvos Respublikos šeimos turto ir pajamų deklaracija": 9,
            },
        )
        # The two 2003 misspellings ("negražintų", "paskolintų
        # (nesugražintų)") and the family form's plural wording are in the
        # key map; anything else would show up here.
        self.assertEqual(unknown, [])

    def test_the_family_form_drops_the_joint_accounts_item(self) -> None:
        family = self._declaration("algirdas-paleckis")
        self.assertEqual(family["forma"], "Lietuvos Respublikos šeimos turto ir pajamų deklaracija")
        prompts = [item["prompt"] for item in family["items"]]
        self.assertEqual(len(prompts), 9)
        self.assertTrue(all("bendros piniginės lėšos banko" not in p.lower() for p in prompts))
        resident = self._declaration("vilija-aleknaite-abramikiene")
        self.assertEqual(len(resident["items"]), 10)
        self.assertTrue(
            any("bendros piniginės lėšos banko" in p["prompt"].lower() for p in resident["items"])
        )

    def test_the_one_repaid_loan_in_the_field(self) -> None:
        # 26 of the 27 declare "-" for every loan item, which is why the
        # misspelled prompts cost no figure — only the unknown-line signal.
        filled = {}
        for directory in sorted(SAMPLES_ROOT.iterdir()):
            if not (directory / "turto-ir-pajamu-deklaracijos.html").exists():
                continue
            record, _ = _parse(directory.name)
            value = record["normalized"]["turto-ir-pajamu-deklaracijos"]["grazintos-paskolos"]
            if value is not None:
                filled[directory.name] = value
        self.assertEqual(filled, {"zigfrid-rackovskis": 16000})

    def test_the_2002_key_map_alone_leaves_the_misspelled_items_unknown(self) -> None:
        # Without the 2003 spellings the two loan items go unrecognised on
        # every page — 2 x 27 unknown lines, silently.
        raw = self._declaration("vilija-aleknaite-abramikiene")
        _, unknown = normalize_deklaracija(raw)
        self.assertEqual(
            [prompt.split(" ", 1)[0] for prompt in unknown], ["10.", "12."]
        )
        _, none_unknown = normalize_deklaracija(
            raw, single_items=DEKLARACIJA_SINGLE_ITEMS, range_items=DEKLARACIJA_RANGE_ITEMS
        )
        self.assertEqual(none_unknown, [])


class SeimoNauji2003RowsNormalizerTests(unittest.TestCase):
    def test_the_normalizer_reads_question_five_not_three(self) -> None:
        rows = [
            {"questionNumber": "3", "prompt": "3. Gimimo data:", "answer": "1900 01 01"},
            {"questionNumber": "5", "prompt": "5. Gimimo data:", "answer": "1957 05 04"},
        ]
        self.assertEqual(normalize_seimo_2003_anketa_rows(rows)["gimimo-data"], "1957-05-04")


if __name__ == "__main__":
    unittest.main()
