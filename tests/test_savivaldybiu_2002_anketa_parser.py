import json
import tempfile
import unittest
from pathlib import Path

from scraper.elections.savivaldybiu_2002.anketa_parser import (
    DEFAULT_RESULTS_PATH,
    build_candidacy,
    normalize_deklaracija,
    normalize_savivaldybiu_2002_anketa_rows,
    parse_anketa_html,
    parse_anketa_sample,
    parse_deklaracija_html,
)
from scraper.elections.savivaldybiu_2002.candidate_samples import EXPECTED_TABS, extract_tab_links
from scraper.elections.savivaldybiu_2002.results import (
    build_results,
    parse_council_page,
    parse_mandate_summary,
    parse_members_page,
    parse_municipality_results_page,
    parse_preference_page,
)
from scraper.elections.savivaldybiu_2002.sitemap import (
    ELECTION_ID,
    LISTING_URL,
    PARTIES_URL,
    SITE_ROOT,
    build_sitemap_from_sample,
    extract_municipality_links,
    extract_party_links,
    parse_apygarda_page,
)

from local_data import require


REPO_ROOT = Path(__file__).resolve().parents[1]
SAMPLES_ROOT = REPO_ROOT / "samples" / "html" / ELECTION_ID
RESULTS_DIR = REPO_ROOT / "samples" / "results" / ELECTION_ID
SITEMAPS = REPO_ROOT / "sitemaps"


def _parse(candidate_id: str) -> tuple[dict, dict]:
    with tempfile.TemporaryDirectory() as tmp:
        output_path, stats = parse_anketa_sample(
            candidate_id=candidate_id,
            samples_root=SAMPLES_ROOT,
            output_root=Path(tmp),
        )
        return json.loads(output_path.read_text(encoding="utf-8")), stats


class Savivaldybiu2002SitemapTests(unittest.TestCase):
    def test_indexes(self) -> None:
        municipalities = extract_municipality_links((SAMPLES_ROOT / "list.html").read_text(encoding="utf-8"))
        self.assertEqual(len(municipalities), 60)
        self.assertEqual(
            municipalities[0],
            {
                "apygardosId": "1354",
                "number": 1,
                "name": "Akmenės rajono",
                "url": SITE_ROOT + "kandidatai/kandidatai_apygardoje_jsp_ri_id_15_apyg_id_1354.htm",
            },
        )
        self.assertEqual(
            (municipalities[56]["number"], municipalities[56]["apygardosId"], municipalities[56]["name"]),
            (57, "1410", "Vilniaus miesto"),
        )
        parties = extract_party_links((SAMPLES_ROOT / "parties.html").read_text(encoding="utf-8"))
        self.assertEqual(len(parties), 25)
        self.assertEqual(
            parties[0],
            {
                "orgId": "945",
                "number": 1,
                "name": "Valstiečių ir Naujosios demokratijos partijų sąjunga",
                "url": PARTIES_URL + "kandidatai_apygardose_jsp_ri_id_15_org_ri_id_945.htm",
            },
        )
        # The party numbering has a gap (no 7): the last of the 25 is 26.
        self.assertEqual((parties[-1]["number"], parties[-1]["name"]), (26, "Lietuvos liberalų sąjunga"))

    def test_page_readers(self) -> None:
        page = parse_apygarda_page((SAMPLES_ROOT / "municipalities" / "municipality-1354.html").read_text(encoding="utf-8"))
        self.assertEqual((page["municipalityName"], len(page["lists"])), ("Akmenės rajono", 8))
        first = page["lists"][0]
        self.assertEqual((first["listNumber"], first["name"], len(first["candidates"])), (1, "Valstiečių ir Naujosios demokratijos partijų sąjunga", 11))
        # The list's #1 withdrew: the printed positions start at 2.
        self.assertEqual(
            first["candidates"][0],
            {
                "listPosition": 2,
                "candidateName": "Stasys Beržinis",
                "vrkCandidateId": "132939",
                "url": SITE_ROOT + "kandidatai/1354/kandidatai_anketa_jsp_ri_id_15_asm_kod_132939.htm",
                "deklaracijaUrl": SITE_ROOT + "kandidatai/1354/kandidatai_deklaracija_jsp_ri_id_15_asm_kod_132939.htm",
            },
        )
        self.assertEqual(sum(len(entry["candidates"]) for entry in page["lists"]), 146)
        # A party's per-municipality page is the same document narrowed
        # to its own candidates — the coalition heading unchanged.
        page = parse_apygarda_page((SAMPLES_ROOT / "party-lists" / "list-1410-936.html").read_text(encoding="utf-8"))
        self.assertEqual((page["municipalityName"], len(page["lists"])), ("Vilniaus miesto", 1))
        self.assertEqual(page["lists"][0]["listNumber"], 26)
        self.assertEqual(len(page["lists"][0]["candidates"]), 11)

    def test_two_structures_reconcile_with_the_party_pages(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            _, stats = build_sitemap_from_sample(sample_path=SAMPLES_ROOT, output_path=Path(tmp) / "sitemap.json")
            payload = json.loads((Path(tmp) / "sitemap.json").read_text(encoding="utf-8"))
        self.assertEqual(
            payload["stats"],
            {
                "municipalities": 60,
                "partyLists": 521,
                "coalitionLists": 15,
                "parties": 25,
                "candidatesClaimedByParties": 10139,
                "unclaimedCandidates": 0,
                "doubleNominations": 0,
                "partyPositionMismatches": 0,
                "headingNameMismatches": 0,
                "duplicateVrkIds": 0,
                "missingDeklaracijaLinks": 0,
            },
        )
        self.assertEqual(
            (stats["rows"], stats["extracted"], stats["skipped"], stats["duplicate_candidate_ids"]),
            (521, 10139, 0, 0),
        )
        self.assertEqual(payload["sourceUrl"], LISTING_URL)
        self.assertEqual(payload["partiesUrl"], PARTIES_URL)
        self.assertEqual(len(payload["municipalities"]), 60)
        by_id = {entry["candidateId"]: entry for entry in payload["entries"]}
        self.assertEqual(
            by_id["stasys-berzinis-132939"],
            {
                "candidateName": "Stasys Beržinis",
                "candidateId": "stasys-berzinis-132939",
                "url": SITE_ROOT + "kandidatai/1354/kandidatai_anketa_jsp_ri_id_15_asm_kod_132939.htm",
                "deklaracijaUrl": SITE_ROOT + "kandidatai/1354/kandidatai_deklaracija_jsp_ri_id_15_asm_kod_132939.htm",
                "vrkCandidateId": "132939",
                "municipality": {"pavadinimas": "Akmenės rajono", "numeris": 1, "apygardosId": "1354"},
                "list": {"pavadinimas": "Valstiečių ir Naujosios demokratijos partijų sąjunga", "rusis": "partija", "numeris": 1},
                "listPosition": 2,
            },
        )
        # A coalition list: the heading is no party of the index (it
        # stands under the Liberals' ballot number), the member parties
        # and each candidate's nominator come from the party pages.
        zuokas = by_id["arturas-zuokas-154491"]
        self.assertEqual(
            zuokas["list"],
            {
                "pavadinimas": 'A.Zuoko koalicija "Už Vilnių, kuriame gera visiems" Liberalai ir modernieji krikščionys demokratai',
                "rusis": "koalicija",
                "numeris": 26,
                "koalicijosPartijos": ["Moderniųjų krikščionių demokratų sąjunga", "Lietuvos liberalų sąjunga"],
            },
        )
        self.assertEqual(zuokas["koalicijosPartija"], "Lietuvos liberalų sąjunga")
        self.assertEqual(by_id["vytautas-bogusis-22"]["koalicijosPartija"], "Moderniųjų krikščionių demokratų sąjunga")


class Savivaldybiu2002CandidateSamplesTests(unittest.TestCase):
    def test_expected_tabs(self) -> None:
        self.assertEqual(EXPECTED_TABS, {"anketa", "turto-ir-pajamu-deklaracijos"})

    def test_tab_links(self) -> None:
        candidate_url = SITE_ROOT + "kandidatai/1354/kandidatai_anketa_jsp_ri_id_15_asm_kod_132939.htm"
        html = (SAMPLES_ROOT / "stasys-berzinis-132939" / "anketa.html").read_text(encoding="utf-8")
        links = extract_tab_links(html, candidate_url)
        self.assertEqual(
            links,
            [
                {"label": "Anketa", "slug": "anketa", "url": candidate_url},
                {
                    "label": "Pajamų deklaracija",
                    "slug": "turto-ir-pajamu-deklaracijos",
                    "url": SITE_ROOT + "kandidatai/1354/kandidatai_deklaracija_jsp_ri_id_15_asm_kod_132939.htm",
                },
            ],
        )


class Savivaldybiu2002AnketaParserTests(unittest.TestCase):
    def test_question_rows(self) -> None:
        parsed = parse_anketa_html((SAMPLES_ROOT / "stasys-berzinis-132939" / "anketa.html").read_text(encoding="utf-8"))
        self.assertEqual(parsed["profile"]["candidateDisplayName"], "Stasys Beržinis")
        self.assertTrue(all(parsed["diagnostics"].values()))
        rows = parsed["anketa"]["rows"]
        self.assertEqual(
            [row.get("questionNumber") for row in rows],
            ["5", "6", "8.1", "8.2", "8.3", "9", "10", "11", "12", "13", "15", "16", "17", "19", None],
        )
        by_number = {row.get("questionNumber"): row for row in rows}
        self.assertEqual(by_number["5"]["answer"], "1944-08-28")
        self.assertEqual(by_number["9"]["answer"], "Ne")
        # The 88 str. legal excerpt under Q9 is boilerplate, not a row.
        self.assertTrue(any(text.startswith("88 str.") for text in parsed["anketa"]["boilerplate"]))
        # Q15's indented mandate line, one record per prior mandate.
        self.assertEqual(
            by_number["15"]["records"],
            [{"nuo": "1997", "iki": "2000", "institucija": "Akmenės rajono savivaldybės taryba"}],
        )
        # The children's names trail Q19 as an unnumbered row.
        self.assertEqual((rows[-1]["prompt"], rows[-1]["answer"]), ("Vaikų vardai:", "Sonata, Stasys"))

    def test_conviction_explanation(self) -> None:
        # A "Taip" on the 88 str. question is followed by the
        # conviction's circumstances in a blockquote of its own.
        parsed = parse_anketa_html(
            (SAMPLES_ROOT / "rimvydas-vytautas-kliucius-135195" / "anketa.html").read_text(encoding="utf-8")
        )
        q9 = next(row for row in parsed["anketa"]["rows"] if row.get("questionNumber") == "9")
        self.assertEqual(q9["answer"], "Taip")
        self.assertTrue(q9["explanation"].startswith("Transporto priemonės vairavimas"))
        anketa = normalize_savivaldybiu_2002_anketa_rows(parsed["anketa"]["rows"])
        self.assertEqual(anketa["pareiskimai"]["ar-buvote-pripazintas-kaltu"], "Taip")
        self.assertEqual(anketa["pareiskimai"]["teisiniai-argumentai"], q9["explanation"])

    def test_sparse_page(self) -> None:
        # A page that answers almost nothing: the blanks are empty
        # bolds, Q19 is omitted entirely, Q15 is an inline "Nebuvo".
        parsed = parse_anketa_html((SAMPLES_ROOT / "veronika-staneikiene-202013" / "anketa.html").read_text(encoding="utf-8"))
        rows = parsed["anketa"]["rows"]
        self.assertEqual(
            [row.get("questionNumber") for row in rows],
            ["5", "6", "8.1", "8.2", "8.3", "9", "10", "11", "12", "13", "15", "16", "17"],
        )
        by_number = {row.get("questionNumber"): row for row in rows}
        self.assertEqual(by_number["15"]["answer"], "Nebuvo")
        self.assertEqual(by_number["10"]["answer"], "")
        self.assertEqual(parsed["anketa"]["stats"], {"rowCount": 13, "answeredRowCount": 7})

    def test_normalized_keys(self) -> None:
        parsed = parse_anketa_html((SAMPLES_ROOT / "arturas-zuokas-154491" / "anketa.html").read_text(encoding="utf-8"))
        anketa = normalize_savivaldybiu_2002_anketa_rows(parsed["anketa"]["rows"])
        self.assertEqual(
            list(anketa.keys()),
            [
                "gimimo-data",
                "adresas",
                "pareiskimai",
                "gimimo-vieta",
                "tautybe",
                "issilavinimas",
                "uzsienio-kalbos",
                "anksciau-isrinktas",
                "pagrindine-darboviete",
                "visuomenine-veikla",
                "pomegiai",
                "seimine-padetis",
                "sutuoktinio-vardas-pavarde",
                "vaiku-vardai-pavardes",
            ],
        )
        self.assertEqual(
            list(anketa["pareiskimai"].keys()),
            [
                "ar-nebaigta-teismo-paskirta-bausme",
                "ar-atliekate-karo-tarnyba",
                "ar-turite-kitos-valstybes-pilietybe",
                "ar-buvote-pripazintas-kaltu",
                "teisiniai-argumentai",
            ],
        )
        self.assertEqual(anketa["gimimo-data"], "1968-02-21")
        self.assertEqual(anketa["uzsienio-kalbos"], ["Anglų", "Vokiečių", "Rusų"])
        # The page prints his council mandate three times; parsed as printed.
        self.assertEqual(len(anketa["anksciau-isrinktas"]["irasai"]), 3)
        self.assertEqual(
            anketa["anksciau-isrinktas"]["irasai"][0],
            {"institucijos-pavadinimas-pareigos": "Vilniaus miesto savivaldybės taryba", "laikotarpis": "2000–2000"},
        )
        self.assertEqual(anketa["sutuoktinio-vardas-pavarde"], "Agnė")
        self.assertEqual(anketa["vaiku-vardai-pavardes"], "Gabrielė, Domantas")


class Savivaldybiu2002DeklaracijaTests(unittest.TestCase):
    def test_eleven_item_variant(self) -> None:
        raw = parse_deklaracija_html(
            (SAMPLES_ROOT / "stasys-berzinis-132939" / "turto-ir-pajamu-deklaracijos.html").read_text(encoding="utf-8")
        )
        declaration, unknown = normalize_deklaracija(raw)
        self.assertEqual(unknown, [])
        self.assertEqual(declaration["gautos-pajamos"], 25565)
        self.assertEqual(declaration["sumoketas-pajamu-mokestis"], 8088)
        # The form sums registrable assets with securities (III S1 + IV
        # S1): the modern split is unrecoverable, the combined figures
        # keep era keys.
        self.assertIsNone(declaration["privalomas-registruoti-turtas"])
        self.assertIsNone(declaration["vertybiniai-popieriai-meno-kuriniai-juvelyriniai-dirbiniai"])
        self.assertEqual(declaration["turtas-ir-vertybiniai-popieriai-laikotarpio-pradzioje"], 151659)
        self.assertEqual(declaration["turtas-ir-vertybiniai-popieriai-laikotarpio-pabaigoje"], 151659)
        # Item 8's end-of-period figure fills the modern key.
        self.assertEqual(declaration["pinigines-lesos"], 99833)
        self.assertEqual(declaration["pinigines-lesos-laikotarpio-pradzioje"], 92387)
        self.assertIsNone(declaration["bendros-pinigines-lesos-banke-laikotarpio-pabaigoje"])
        self.assertEqual(declaration["darboviete"], 'Uždaroji akcinė bendrovė "Akmenės vandenys"')
        self.assertEqual(declaration["valiuta"], "Lt")

    def test_twelve_item_variant(self) -> None:
        # The variant that inserts the joint bank-accounts item as 9 and
        # renumbers the rest — items are matched on wording, not number.
        raw = parse_deklaracija_html(
            (SAMPLES_ROOT / "vytautas-juozapavicius-132963" / "turto-ir-pajamu-deklaracijos.html").read_text(encoding="utf-8")
        )
        declaration, unknown = normalize_deklaracija(raw)
        self.assertEqual(unknown, [])
        self.assertIsNotNone(declaration["bendros-pinigines-lesos-banke-laikotarpio-pradzioje"])
        self.assertEqual(declaration["gautos-paskolos"], 0)
        self.assertEqual(declaration["grazintos-paskolos"], 0)
        self.assertEqual(declaration["pasiskolintos-ir-dovanotos-lesos"], 0)

    def test_empty_workplace(self) -> None:
        raw = parse_deklaracija_html(
            (SAMPLES_ROOT / "algimantas-rasimas-121894" / "turto-ir-pajamu-deklaracijos.html").read_text(encoding="utf-8")
        )
        declaration, unknown = normalize_deklaracija(raw)
        self.assertEqual(unknown, [])
        self.assertIsNone(declaration["darboviete"])
        self.assertEqual(declaration["gautos-pajamos"], 3668)
        self.assertEqual(declaration["sumoketas-pajamu-mokestis"], 0)


class Savivaldybiu2002ResultsTests(unittest.TestCase):
    def test_page_readers(self) -> None:
        page = parse_municipality_results_page((RESULTS_DIR / "rezultatai__rapgpl_1354.htm").read_text(encoding="utf-8"))
        self.assertEqual(
            (page["voters"], page["turnout"], page["turnoutPercent"], page["validBallots"], page["invalidBallots"], page["quota"], len(page["lists"])),
            (23675, 13299, 56.17, 12375, 924, 476, 8),
        )
        self.assertEqual(
            page["lists"][0],
            {
                "listNumber": 15,
                "name": "Lietuvių tautininkų sąjunga",
                "apygardosId": "1354",
                "listSeq": "22",
                "preferenceUrl": SITE_ROOT + "rezultatai/rpbapgl_1354_22.htm",
                "ballotBox": 3293,
                "postal": 239,
                "total": 3532,
                "mandates": 8,
            },
        )
        # A list below the threshold prints "-" in the mandates column.
        self.assertIsNone(page["lists"][-1]["mandates"])
        self.assertEqual(page["total"], {"ballotBox": 11680, "postal": 695, "total": 12375, "mandates": 25})
        members = parse_members_page((RESULTS_DIR / "rezultatai__rikl_1354.htm").read_text(encoding="utf-8"))
        self.assertEqual((members["seats"], len(members["members"])), (25, 25))
        self.assertEqual(
            members["members"][0],
            {"vrkCandidateId": "132972", "name": "Lupeika Anicetas", "listName": "Lietuvių tautininkų sąjunga", "listSeq": "22", "rank": 1},
        )
        preference = parse_preference_page((RESULTS_DIR / "rezultatai__rpbapgl_1354_22.htm").read_text(encoding="utf-8"))
        self.assertEqual(preference["listVotes"], 3532)
        self.assertEqual(
            preference["rows"][0],
            {"rank": 1, "vrkCandidateId": "132972", "name": "Lupeika Anicetas", "preferenceVotes": 2086, "listPosition": 1, "mandate": True},
        )
        self.assertEqual(sum(1 for row in preference["rows"] if row["mandate"]), 8)
        council = parse_council_page((RESULTS_DIR / "savtaryb__sav_apg_l_1354_1.htm").read_text(encoding="utf-8"))
        self.assertEqual((council["seats"], len(council["members"])), (25, 25))
        by_id = {member["vrkCandidateId"]: member for member in council["members"]}
        self.assertEqual(by_id["132972"]["nuo"], "2002-12-22")
        # A substitute's row replaces the departed member's, dated by
        # its own entry into the council.
        self.assertEqual(by_id["204265"]["nuo"], "2004-03-17")
        summary = parse_mandate_summary((RESULTS_DIR / "mandatai__mlt_15_1.html").read_text(encoding="utf-8"))
        self.assertEqual(len(summary["parties"]), 23)
        self.assertEqual(summary["parties"][0], {"name": "Lietuvos socialdemokratų partija", "mandates": 332})
        self.assertEqual(summary["total"], 1560)

    def test_members_lists_and_rankings_reconcile(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            _, stats = build_results(
                sitemap_path=SITEMAPS / f"{ELECTION_ID}.json",
                results_dir=RESULTS_DIR,
                output_path=Path(tmp) / "results.json",
            )
            payload = json.loads((Path(tmp) / "results.json").read_text(encoding="utf-8"))
        self.assertEqual(
            stats,
            {
                "municipalities": 60,
                "councilMembers": 1560,
                "membersOnPages": 1560,
                "councilNotInSitemap": 0,
                "municipalityMismatches": 0,
                "listMismatches": 0,
                "seatCountMismatches": 0,
                "rankMismatches": 0,
                "boldNotMembers": 0,
                "listTopRanksNotMembers": 0,
                "listVoteMismatches": 0,
                "candidatesRanked": 10139,
                "rankedNotInSitemap": 0,
                "sitemapNotRanked": 0,
                "listPositionMismatches": 0,
                "councilRows": 1560,
                "councilDayRowsNotMembers": 0,
                "councilSizeMismatches": 0,
                "replacedMembers": 562,
                "substitutes": 562,
                "substitutesNotInSitemap": 0,
                "mandateSummaryTotal": 1560,
                "seats": {"tarybos-narys": 1560},
            },
        )
        self.assertEqual(
            payload["elected"]["132972"],
            {
                "seat": "tarybos-narys",
                "sourceUrl": SITE_ROOT + "rezultatai/rikl_1354.htm",
                "municipality": "Akmenės rajono",
                "apygardosId": "1354",
                "listName": "Lietuvių tautininkų sąjunga",
                "listNumber": 15,
                "rank": 1,
            },
        )
        self.assertEqual(payload["details"]["listResults"]["1354"]["15"]["mandates"], 8)
        self.assertEqual(len(payload["details"]["listResults"]), 60)


class Savivaldybiu2002RecordTests(unittest.TestCase):
    def test_elected_record(self) -> None:
        require(DEFAULT_RESULTS_PATH)
        record, stats = _parse("anicetas-lupeika-132972")
        self.assertEqual(stats["anomalies"], [])
        candidacy = record["kandidatavimas"]
        self.assertTrue(candidacy["isrinktas"])
        self.assertEqual(candidacy["isrinktasKaip"], "tarybos-narys")
        self.assertEqual(candidacy["savivaldybe"], "Akmenės rajono")
        self.assertEqual(candidacy["roles"], ["tarybos-narys"])
        self.assertEqual(candidacy["porinkiminisNumerisSarase"], 1)
        self.assertEqual(candidacy["pirmumoBalsai"], 2086)
        self.assertEqual(candidacy["tarybosNarysNuo"], "2002-12-22")
        self.assertEqual(candidacy["tarybosNarys"]["sarasoBalsai"], 3532)
        self.assertEqual(candidacy["tarybosNarys"]["sarasoMandatai"], 8)

    def test_substitute_record(self) -> None:
        require(DEFAULT_RESULTS_PATH)
        # Elected no — but on the council from 2004-03-17, when a member
        # left and the list's next candidate took the seat.
        record, stats = _parse("jadvyga-daukantaite-204265")
        self.assertEqual(stats["anomalies"], [])
        candidacy = record["kandidatavimas"]
        self.assertFalse(candidacy["isrinktas"])
        self.assertNotIn("isrinktasKaip", candidacy)
        self.assertEqual(candidacy["tarybosNarysNuo"], "2004-03-17")
        self.assertEqual(candidacy["porinkiminisNumerisSarase"], 17)

    def test_coalition_record(self) -> None:
        require(DEFAULT_RESULTS_PATH)
        record, stats = _parse("arturas-zuokas-154491")
        self.assertEqual(stats["anomalies"], [])
        council = record["kandidatavimas"]["tarybosNarys"]
        self.assertEqual(council["listKind"], "koalicija")
        self.assertEqual(
            council["koalicijosPartijos"],
            ["Moderniųjų krikščionių demokratų sąjunga", "Lietuvos liberalų sąjunga"],
        )
        self.assertEqual(council["koalicijosPartija"], "Lietuvos liberalų sąjunga")
        self.assertEqual(record["kandidatavimas"]["pirmumoBalsai"], 42797)
        self.assertEqual(
            record["normalized"]["turto-ir-pajamu-deklaracijos"]["pinigines-lesos"], 812164
        )

    def test_sparse_record(self) -> None:
        require(DEFAULT_RESULTS_PATH)
        record, stats = _parse("veronika-staneikiene-202013")
        self.assertEqual(stats["anomalies"], [])
        self.assertEqual((stats["rowCount"], stats["answeredRowCount"]), (13, 7))
        candidacy = record["kandidatavimas"]
        self.assertFalse(candidacy["isrinktas"])
        self.assertNotIn("tarybosNarysNuo", candidacy)
        self.assertEqual(candidacy["tarybosNarys"]["sarasoMandatai"], 0)
        anketa = record["normalized"]["anketa"]
        self.assertIsNone(anketa["seimine-padetis"])
        self.assertIsNone(anketa["gimimo-vieta"])
        self.assertEqual(anketa["anksciau-isrinktas"], {"aprasas": "Nebuvo", "irasai": []})

    def test_candidacy_builder(self) -> None:
        candidacy = build_candidacy(
            {
                "vrkCandidateId": "1",
                "municipality": {"pavadinimas": "X", "numeris": 2, "apygardosId": "9"},
                "list": {"pavadinimas": "L", "rusis": "koalicija", "numeris": 3, "koalicijosPartijos": ["A", "B"]},
                "listPosition": 4,
                "koalicijosPartija": "A",
            }
        )
        self.assertEqual(
            candidacy,
            {
                "vrkCandidateId": "1",
                "savivaldybe": "X",
                "savivaldybesNumeris": 2,
                "apygardosId": "9",
                "roles": ["tarybos-narys"],
                "tarybosNarys": {
                    "partyList": "L",
                    "listKind": "koalicija",
                    "listNumber": 3,
                    "listPosition": 4,
                    "koalicijosPartijos": ["A", "B"],
                    "koalicijosPartija": "A",
                },
                "isrinktas": None,
            },
        )


if __name__ == "__main__":
    unittest.main()
