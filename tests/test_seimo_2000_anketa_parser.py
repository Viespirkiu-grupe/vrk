import json
import tempfile
import unittest
from pathlib import Path

from scraper.elections.seimo_2000.anketa_parser import (
    DEFAULT_RESULTS_PATH,
    FIELD_KEYS,
    finish_candidacy,
    normalize_anketa,
    parse_anketa_sample,
    parse_candidate_html,
)
from scraper.elections.seimo_2000.candidate_samples import EXPECTED_TABS
from scraper.elections.seimo_2000.results import (
    MEMBERS_PAGE,
    build_results,
    parse_constituency_page,
    parse_list_results_page,
    parse_members_page,
    parse_preference_page,
)
from scraper.elections.seimo_2000.sitemap import (
    DISTRICTS_URL,
    ELECTION_ID,
    LISTING_URL,
    SITE_ROOT,
    build_sitemap_from_sample,
    district_records,
    extract_district_links,
    extract_party_links,
    party_page_coalition,
    party_page_records,
    resolve_party_kinds,
)
from scraper.shared.deklaracija_archive_1990s import parse_declaration

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


def _party_links() -> list[dict]:
    links = extract_party_links((SAMPLES_ROOT / "list.html").read_text(encoding="utf-8"))
    facts = {
        link["listKey"]: party_page_coalition((SAMPLES_ROOT / "lists" / f"list-{link['listKey']}.html").read_text(encoding="utf-8"))
        for link in links
    }
    resolve_party_kinds(links, facts)
    return links


class Seimo2000SitemapTests(unittest.TestCase):
    def test_index_kinds_are_settled_from_the_pages(self) -> None:
        raw = extract_party_links((SAMPLES_ROOT / "list.html").read_text(encoding="utf-8"))
        self.assertEqual(len(raw), 28)
        self.assertEqual([link["kind"] for link in raw].count("sarasas"), 15)
        self.assertEqual([link["kind"] for link in raw].count("nenumeruota"), 13)
        self.assertTrue(all(link["declaredCount"] is None for link in raw))
        links = _party_links()
        kinds = [link["kind"] for link in links]
        self.assertEqual((kinds.count("sarasas"), kinds.count("koalicijos-nare"), kinds.count("tik-vienmandatese")), (15, 4, 9))
        member = next(link for link in links if link["listKey"] == "646")
        self.assertEqual(member, {
            "listKey": "646",
            "kind": "koalicijos-nare",
            "listNumber": None,
            "coalitionListNumber": 9,
            "name": "Lietuvos socialdemokratų partija",
            "declaredCount": None,
            "url": SITE_ROOT + "kandpartl.htm-646.htm",
        })
        coalition = next(link for link in links if link["listKey"] == "698")
        self.assertEqual((coalition["kind"], coalition["listNumber"], coalition["name"]), ("sarasas", 9, "A.Brazausko socialdemokratinė koalicija"))
        self.assertEqual(
            party_page_coalition((SAMPLES_ROOT / "lists" / "list-698.html").read_text(encoding="utf-8")),
            {"memberKeys": ["644", "671", "646", "649"], "coalitionKeys": []},
        )
        districts = extract_district_links((SAMPLES_ROOT / "districts.html").read_text(encoding="utf-8"))
        self.assertEqual(len(districts), 71)
        self.assertEqual(districts[0], {"districtId": "757", "number": 1, "name": "Naujamiesčio", "url": SITE_ROOT + "kandapgl.htm-13+1+757.htm"})
        self.assertEqual((districts[70]["number"], districts[70]["districtId"]), (71, "827"))

    def test_party_page_shapes(self) -> None:
        index = {link["listKey"]: link for link in _party_links()}
        # A plain list: numbered rows with the constituency column, then
        # the party's constituency-only nominees as unnumbered rows.
        rows = party_page_records((SAMPLES_ROOT / "lists" / "list-643.html").read_text(encoding="utf-8"), index["643"])
        self.assertEqual(len(rows), 98)
        self.assertEqual(rows[0]["candidateName"], "Ozolas Romualdas")
        self.assertEqual((rows[0]["position"], rows[0]["hasDistrictColumn"]), (1, True))
        self.assertEqual(sum(1 for row in rows if row["position"] is None), 9)
        # The coalition's page: coalition position, member party, member
        # position, no constituency column.
        rows = party_page_records((SAMPLES_ROOT / "lists" / "list-698.html").read_text(encoding="utf-8"), index["698"])
        self.assertEqual(len(rows), 140)
        self.assertEqual(
            (rows[0]["candidateName"], rows[0]["position"], rows[0]["memberParty"], rows[0]["memberPartyKey"], rows[0]["memberPosition"], rows[0]["hasDistrictColumn"]),
            ("Andriukaitis Vytenis Povilas", 1, "Lietuvos socialdemokratų partija", "646", 1, False),
        )
        # A member party's page: its own numbering, the coalition position,
        # the constituency column.
        rows = party_page_records((SAMPLES_ROOT / "lists" / "list-644.html").read_text(encoding="utf-8"), index["644"])
        self.assertEqual((rows[0]["candidateName"], rows[0]["position"], rows[0]["coalitionPosition"], rows[0]["districtId"]), ("Juršėnas Česlovas", 1, 2, "809"))
        # A constituency-only party: every row unnumbered.
        rows = party_page_records((SAMPLES_ROOT / "lists" / "list-674.html").read_text(encoding="utf-8"), index["674"])
        self.assertEqual(len(rows), 9)
        self.assertTrue(all(row["position"] is None for row in rows))
        # A constituency page: nominator a party or "Išsikėlė pati".
        districts = {d["districtId"]: d for d in extract_district_links((SAMPLES_ROOT / "districts.html").read_text(encoding="utf-8"))}
        rows = district_records((SAMPLES_ROOT / "districts" / "district-757.html").read_text(encoding="utf-8"), districts["757"])
        self.assertEqual(len(rows), 10)
        self.assertEqual((rows[0]["candidateName"], rows[0]["vrkCandidateId"], rows[0]["nominatedBy"], rows[0]["nominatedByKey"]), ("Čobotas Medardas", "154491", "Krikščionių demokratų sąjunga", "642"))
        self.assertEqual((rows[7]["candidateName"], rows[7]["nominatedBy"], rows[7]["nominatedByKey"]), ("Oželytė Nijolė", "Išsikėlė pati", None))
        self.assertEqual(rows[0]["district"], {"pavadinimas": "Naujamiesčio", "numeris": 1, "apygardosId": "757", "antraste": "Naujamiesčio (Nr. 1) apygarda"})

    def test_two_structures_reconcile(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            _, stats = build_sitemap_from_sample(sample_path=SAMPLES_ROOT, output_path=Path(tmp) / "sitemap.json")
            payload = json.loads((Path(tmp) / "sitemap.json").read_text(encoding="utf-8"))
        self.assertEqual(
            payload["stats"],
            {
                "rows": 2088,
                "extracted": 1271,
                "duplicateCandidateIds": 3,
                "lists": 15,
                "sidePages": 13,
                "districts": 71,
                "dual": 582,
                "listOnly": 569,
                "districtOnly": 120,
                "declaredCountMismatches": 0,
                "unnumberedRowsOnLists": 19,
                "unnumberedRowsNotInAnyConstituency": 0,
                "memberPositionMismatches": 0,
                "listColumnConstituencyWrong": 0,
                "constituencyByAnotherNominator": 29,
                "duplicateDistrictRows": 0,
                "selfNominated": 56,
                # One: Virginijus Šmigelskas, the LCS nominee on the Širvintų
                # - Vilniaus page whom the LCS party page omits.
                "districtOnlyReconciled": False,
                "districtOnlyUnaccounted": 1,
                "coalitionLinksUnreciprocated": 0,
                "coalitionMembersNotInIndex": 0,
            },
        )
        self.assertEqual(stats["skipped"], 0)
        self.assertEqual(payload["sourceUrl"], LISTING_URL)
        self.assertEqual(payload["districtsUrl"], DISTRICTS_URL)
        self.assertEqual(len(payload["listUrls"]), 15)
        self.assertEqual(len(payload["sidePageUrls"]), 13)
        by_id = {entry["candidateId"]: entry for entry in payload["entries"]}
        # A coalition candidate carries the member party and its position.
        self.assertEqual(
            by_id["andriukaitis-vytenis-povilas"],
            {
                "candidateName": "Andriukaitis Vytenis Povilas",
                "candidateId": "andriukaitis-vytenis-povilas",
                "url": SITE_ROOT + "kandvl.htm-154044.htm",
                "vrkCandidateId": "154044",
                "roles": ["daugiamandate", "vienmandate"],
                "daugiamandateCandidacy": {
                    "sarasas": "A.Brazausko socialdemokratinė koalicija",
                    "sarasoNumeris": 9,
                    "sarasoId": "698",
                    "numerisSarase": 1,
                    "koalicijosPartija": "Lietuvos socialdemokratų partija",
                    "numerisPartijosSarase": 1,
                },
                "vienmandateCandidacy": {"apygarda": "Žirmūnų", "apygardosNumeris": 4, "apygardosId": "760", "iskele": "Lietuvos socialdemokratų partija"},
            },
        )
        # A cross-party pair: the LTS list, a Lietuvos laisvės lyga
        # constituency nomination (the constituency page is the authority).
        self.assertEqual(by_id["terleckas-antanas"]["daugiamandateCandidacy"]["sarasas"], "Lietuvių tautininkų sąjunga")
        self.assertEqual(by_id["terleckas-antanas"]["vienmandateCandidacy"]["iskele"], "Lietuvos laisvės lyga")
        # The VRK gap is in the sitemap from the constituency page alone.
        self.assertEqual(by_id["smigelskas-virginijus"]["roles"], ["vienmandate"])
        # Namesakes get positional ids: different VRK ids, different lists.
        self.assertEqual((by_id["sedzius-alvydas"]["vrkCandidateId"], by_id["sedzius-alvydas-2"]["vrkCandidateId"]), ("151858", "152007"))
        self.assertEqual(by_id["sedzius-alvydas-2"]["daugiamandateCandidacy"]["koalicijosPartija"], "Lietuvos demokratinė darbo partija")


class Seimo2000ResultsTests(unittest.TestCase):
    def test_page_readers(self) -> None:
        members = parse_members_page((RESULTS_DIR / ("20001008__" + MEMBERS_PAGE)).read_text(encoding="utf-8"), SITE_ROOT + MEMBERS_PAGE)
        self.assertEqual(len(members), 141)
        self.assertEqual(sum(1 for m in members if m["seat"] == "daugiamandate"), 70)
        self.assertEqual(members[0], {
            "vrkCandidateId": "152839",
            "name": "Kvietkauskas Vytautas",
            "party": "Naujoji sąjunga (socialliberalai)",
            "candidateUrl": SITE_ROOT + "kandvl.htm-152839.htm",
            "seat": "vienmandate",
            "districtId": "757",
            "districtNumber": 1,
            "districtName": "Naujamiesčio",
        })
        lists = parse_list_results_page((RESULTS_DIR / "20001008__rdl.htm-13.htm").read_text(encoding="utf-8"))
        self.assertEqual(len(lists), 15)
        self.assertEqual(lists[0], {"listNumber": 9, "name": "A.Brazausko socialdemokratinė koalicija", "listId": "698", "votes": 457294, "percent": 31.08, "mandates": 28})
        self.assertEqual(sum(row["mandates"] for row in lists), 70)
        ranking = parse_preference_page((RESULTS_DIR / "20001008__rdpbl.htm-642.htm").read_text(encoding="utf-8"))
        self.assertEqual(len(ranking), 43)
        self.assertEqual(ranking[0], {"rank": 1, "vrkCandidateId": "154482", "name": "Bobelis Kazys", "listPosition": 1, "preferenceVotes": 38958, "partyRating": 840, "ratingPoints": 32724720})
        page = parse_constituency_page((RESULTS_DIR / "20001008__rvapgl.htm-757.htm").read_text(encoding="utf-8"))
        self.assertEqual((page["heading"], page["voters"], page["turnout"], page["turnoutPercent"]), ("Naujamiesčio (Nr. 1) vienmandatė apygarda", 48280, 28906, 59.87))
        self.assertEqual(page["status"], "Rinkimai apygardoje įvyko. Seimo nariu išrinktas kandidatas, už kurį paduota daugiausia balsų.")
        self.assertEqual(len(page["candidates"]), 10)
        self.assertEqual(page["candidates"][0], {"vrkCandidateId": "152839", "name": "Vytautas Kvietkauskas", "ballotBox": 5680, "postal": 649, "total": 6329, "percent": 23.03})

    def test_members_lists_and_constituencies_reconcile(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            _, stats = build_results(sitemap_path=SITEMAPS / f"{ELECTION_ID}.json", results_dir=RESULTS_DIR, output_path=Path(tmp) / "results.json")
            payload = json.loads((Path(tmp) / "results.json").read_text(encoding="utf-8"))
        self.assertEqual(
            stats,
            {
                "seats": 141,
                "membersListed": 141,
                "membersInSitemap": 141,
                "membersNotInSitemap": 0,
                "listSeats": 70,
                "constituencySeats": 71,
                "roleMismatches": 0,
                "districtMismatches": 0,
                "mandatesDeclared": 70,
                "listMandateMismatches": 0,
                "rankingPages": 15,
                "candidatesRanked": 1151,
                "rankedNotInSitemap": 0,
                "listCandidatesNotRanked": 0,
                "listPositionMismatches": 0,
                "rankSeatMismatches": 0,
                "constituencyPages": 71,
                "constituencyCandidatesWithVotes": 702,
                "constituencyVotesNotInSitemap": 0,
                "constituencyCandidatesWithoutVotes": 0,
                "constituencyVotesDistrictWrong": 0,
                "constituencyWinnerMismatches": 0,
                "constituencyStatuses": {"Rinkimai apygardoje įvyko. Seimo nariu išrinktas kandidatas, už kurį paduota daugiausia balsų.": 71},
            },
        )
        self.assertEqual(payload["elected"]["154044"], {
            "seat": "vienmandate",
            "method": "members-list",
            "sourceUrl": SITE_ROOT + MEMBERS_PAGE,
            "party": "Lietuvos socialdemokratų partija",
            "districtId": "760",
            "districtNumber": 4,
            "districtName": "Žirmūnų",
        })
        self.assertEqual(payload["elected"]["133893"]["seat"], "daugiamandate")
        self.assertEqual(payload["details"]["constituencyVotes"]["133960"]["total"], 16057)
        self.assertEqual(payload["details"]["ranking"]["133893"]["rank"], 4)


class Seimo2000CardParserTests(unittest.TestCase):
    def test_expected_tabs_is_empty(self) -> None:
        self.assertEqual(EXPECTED_TABS, [])

    def test_card_with_elected_note_and_coalition_member(self) -> None:
        parsed = parse_candidate_html((SAMPLES_ROOT / "sakalas-aloyzas" / "candidate.html").read_text(encoding="utf-8"))
        self.assertEqual(parsed["profile"]["candidateDisplayName"], "Aloyzas SAKALAS")
        self.assertEqual(parsed["profile"]["electedNote"], "šioje apygardoje išrinktas Seimo nariu")
        self.assertEqual(parsed["profile"]["photoSrc"], SITE_ROOT + "lm455344.jpg")
        multi, single = parsed["candidacies"]
        self.assertEqual(
            multi,
            {
                "apygardaName": "Daugiamandatė",
                "apygardaNumber": None,
                "apygardaUrl": SITE_ROOT + "rdpbl.htm-698.htm",
                "isMultiMember": True,
                "electedNote": "šioje apygardoje išrinktas Seimo nariu",
                "nominator": "A.Brazausko socialdemokratinė koalicija",
                "nominatorUrl": SITE_ROOT + "kandpartl.htm-698.htm",
                "listNumber": 5,
                "memberParty": "Lietuvos socialdemokratų partija",
                "memberPartyUrl": SITE_ROOT + "kandpartl.htm-646.htm",
                "memberListNumber": 2,
            },
        )
        self.assertEqual((single["apygardaName"], single["apygardaNumber"], single["electedNote"], single["nominator"], single["listNumber"]), ("Antakalnio", 3, None, "Lietuvos socialdemokratų partija", None))
        self.assertEqual((parsed["birthDate"], parsed["birthPlace"], parsed["residence"]), ("1931 07 06", "Jusiškio k. , Anykščių raj.", "Vilnius"))
        self.assertEqual([q["questionNumber"] for q in parsed["questions"]], ["8.1", "8.2", "8.3", "8.4", "9.1", "9.2", "9.3"])
        self.assertEqual(parsed["questions"][0]["prompt"], "Ar turi nebaigtą atlikti teismo nuosprendžiu paskirtą bausmę")
        self.assertEqual([f["label"] for f in parsed["fields"]], [
            "Išsilavinimas", "Moksliniai laipsniai", "Moksliniai vardai", "Užsienio kalbos",
            "Buvo išrinktas į Lietuvos Respublikos Aukščiausiąją Tarybą, Seimą, savivaldybių tarybas",
            "Pagrindinė darbovietė", "Visuomeninė veikla", "Pomėgiai", "Šeimyninė padėtis", "Šeimos nariai",
        ])
        self.assertEqual(parsed["fields"][-1]["items"][0], {"value": "Rita", "note": "sutuoktinis/sutuoktinė"})
        self.assertTrue(parsed["diagnostics"]["declarationFound"] and parsed["diagnostics"]["biographyFound"])
        self.assertTrue(parsed["biography"]["text"].startswith("Aloyzas SAKALAS Lietuvos socialdemokratų partijos kandidatas"))

    def test_every_card_label_is_mapped(self) -> None:
        for candidate_dir in sorted(SAMPLES_ROOT.iterdir()):
            if not (candidate_dir / "candidate.html").exists():
                continue
            with self.subTest(candidate_dir.name):
                parsed = parse_candidate_html((candidate_dir / "candidate.html").read_text(encoding="utf-8"))
                _, unknown = normalize_anketa(parsed)
                self.assertEqual(unknown, [])
                self.assertTrue(all(field["label"].lower() in FIELD_KEYS for field in parsed["fields"]))

    def test_feminine_elected_note_and_self_nomination_beside_the_party(self) -> None:
        parsed = parse_candidate_html((SAMPLES_ROOT / "jukneviciene-rasa" / "candidate.html").read_text(encoding="utf-8"))
        self.assertEqual(parsed["profile"]["electedNote"], "šioje apygardoje išrinkta Seimo nare")
        self.assertEqual([(c["apygardaName"], c["nominator"]) for c in parsed["candidacies"]], [
            ("Daugiamandatė", "Tėvynės sąjunga (Lietuvos konservatoriai)"),
            ("Lazdynų", "Išsikėlė pati"),
            ("Lazdynų", "Tėvynės sąjunga (Lietuvos konservatoriai)"),
        ])
        candidacy = {"vienmandate": {"apygarda": "Lazdynų", "apygardosNumeris": 9, "iskele": "Išsikėlė pati"}, "daugiamandate": {"numerisSarase": 3}}
        self.assertEqual(finish_candidacy(candidacy, parsed), [])
        self.assertEqual(candidacy["vienmandate"]["kitiIskelejai"], ["Tėvynės sąjunga (Lietuvos konservatoriai)"])

    def test_citizenship_and_oath_sub_questions(self) -> None:
        parsed = parse_candidate_html((SAMPLES_ROOT / "vaitas-vilimantas-stanislovas" / "candidate.html").read_text(encoding="utf-8"))
        self.assertEqual(
            [(q["questionNumber"], q["answer"]) for q in parsed["questions"]],
            [("8.1", "Neturi"), ("8.2", "Nėra"), ("8.3", "Turi"), ("8.3.1", "JAV"), ("8.4", "Yra"), ("8.4.1", "JAV - paleistas į pensiją 1982 m."), ("9.1", "Nėra"), ("9.2", "Nėra"), ("9.3", "Nebuvo")],
        )
        anketa, _ = normalize_anketa(parsed)
        self.assertEqual(anketa["pareiskimai"]["ar-turite-kitos-valstybes-pilietybe"], "Turi")
        self.assertEqual(anketa["pareiskimai"]["kitos-valstybes-pilietybe-valstybe"], "JAV")
        self.assertEqual(anketa["pareiskimai"]["ar-susijes-priesaika-uzsienio-valstybei"], "Yra")
        self.assertEqual(anketa["pareiskimai"]["priesaikos-uzsienio-valstybei-atsisakymas"], "paleistas į pensiją 1982 m.")
        # Two citizenships: 8.3.1 twice; after a "Nėra" on 8.4 the page
        # prints the 8.4.1 template with nothing in it.
        parsed = parse_candidate_html((SAMPLES_ROOT / "laugalis-victor-vitold-vytautas" / "candidate.html").read_text(encoding="utf-8"))
        self.assertEqual([q["answer"] for q in parsed["questions"] if q["questionNumber"] == "8.3.1"], ["KANADA", "LENKIJA"])
        self.assertEqual(next(q for q in parsed["questions"] if q["questionNumber"] == "8.4")["explanation"], "KANADA - LENKIJA -")
        anketa, _ = normalize_anketa(parsed)
        self.assertEqual(anketa["pareiskimai"]["kitos-valstybes-pilietybe-valstybe"], "KANADA, LENKIJA")
        self.assertIsNone(anketa["pareiskimai"]["priesaikos-uzsienio-valstybei-atsisakymas"])
        self.assertEqual([q["questionNumber"] for q in parsed["questions"] if q["questionNumber"].count(".") == 1], ["8.1", "8.2", "8.3", "8.4", "9.1", "9.2", "9.3"])

    def test_pre_results_vintage_page_keeps_no_note(self) -> None:
        require(DEFAULT_RESULTS_PATH)
        # 32 of the 1,271 pages are VRK's pre-results capture: the card
        # links the live CGI and carries no winner note even for a winner.
        record, stats = _parse("zukauskas-henrikas")
        self.assertEqual([a["eventType"] for a in stats["anomalies"]], ["ElectedNoteMismatch"])
        self.assertIsNone(record["normalized"]["profilis"]["pastaba"])
        self.assertEqual((record["kandidatavimas"]["isrinktas"], record["kandidatavimas"]["isrinktasKaip"], record["kandidatavimas"]["vienmandatesBalsai"]["vieta"]), (True, "vienmandate", 1))
        self.assertIn("cgi-bin/ora7dbcgi", record["normalized"]["profilis"]["kita"]["apygarda-2"]["nuorodos"][0])

    def test_card_contradictions_are_named(self) -> None:
        parsed = parse_candidate_html((SAMPLES_ROOT / "sakalas-aloyzas" / "candidate.html").read_text(encoding="utf-8"))
        candidacy = {
            "vienmandate": {"apygarda": "Senamiesčio", "apygardosNumeris": 2, "iskele": "Lietuvos socialdemokratų partija"},
            "daugiamandate": {"numerisSarase": 6, "koalicijosPartija": "Lietuvos socialdemokratų partija", "numerisPartijosSarase": 2},
        }
        self.assertEqual([p["eventType"] for p in finish_candidacy(candidacy, parsed)], ["CardConstituencyMismatch", "CardListNumberMismatch"])

    def test_declaration_reads_decimal_litas_and_workplace(self) -> None:
        html = (SAMPLES_ROOT / "cobotas-medardas" / "candidate.html").read_text(encoding="utf-8")
        start, end = html.index('name="pajamos"'), html.index('name="autobio"')
        parsed = parse_declaration(html[start:end])
        self.assertEqual(parsed["anomalies"], [])
        self.assertEqual(
            parsed["declaration"],
            {
                "privalomas-registruoti-turtas": None,
                "pinigines-lesos": None,
                "gautos-pajamos": 18520.68,
                "sumoketas-pajamu-mokestis": 4487.13,
                "gautos-pajamos-darbo-santykiu": 9546.02,
                "sumoketas-pajamu-mokestis-darbo-santykiu": 4487.13,
                "mokesciu-nepriemoka": 0,
                "privaloma-sumoketi-mokesciu-ir-sankciju": 0,
                "valiuta": "Lt",
                "israso-data": "2000-08-21",
                "turtas-ir-pinigines-lesos-metu-pradzioje": 254065,
                "kalendoriniais-metais-isigytas-turtas": 0,
                "turtas-ir-pinigines-lesos-metu-pabaigoje": 266611,
                "seimos-nariu-skaicius": 2,
                "islaikytiniu-skaicius": 0,
                "seimos-nariu-iki-18-metu": 0,
                "israsa-isdave": "Vilniaus apskrities VMI Vilniaus skyrius",
                "darboviete": "Ekaperimentinės ir klinikinės medicinos institutas",
                "pareigos": "vyr. mokslinis bendradarbis",
            },
        )


class Seimo2000RecordTests(unittest.TestCase):
    def test_constituency_winner_on_a_coalition_list(self) -> None:
        require(DEFAULT_RESULTS_PATH)
        record, stats = _parse("andriukaitis-vytenis-povilas")
        self.assertEqual(stats["anomalies"], [])
        self.assertEqual(record["candidateName"], "Vytenis Povilas ANDRIUKAITIS")
        self.assertEqual(
            record["kandidatavimas"],
            {
                "vrkCandidateId": "154044",
                "roles": ["daugiamandate", "vienmandate"],
                "vienmandate": {"apygarda": "Žirmūnų", "apygardosNumeris": 4, "apygardosId": "760", "iskele": "Lietuvos socialdemokratų partija"},
                "daugiamandate": {
                    "sarasas": "A.Brazausko socialdemokratinė koalicija",
                    "sarasoNumeris": 9,
                    "sarasoId": "698",
                    "numerisSarase": 1,
                    "koalicijosPartija": "Lietuvos socialdemokratų partija",
                    "numerisPartijosSarase": 1,
                },
                "isrinktas": True,
                "isrinktasKaip": "vienmandate",
                "rezultatuSaltinis": SITE_ROOT + MEMBERS_PAGE,
                "porinkiminisNumerisSarase": 1,
                "pirmumoBalsai": 239647,
                "partinisReitingas": 2780,
                "reitingoBalai": 666218660,
                "pirmumoBalsuSaltinis": SITE_ROOT + "rdpbl.htm-698.htm",
                "vienmandatesBalsai": {
                    "balsadezese": 8938,
                    "pastu": 252,
                    "isViso": 9190,
                    "procentai": 39.87,
                    "vieta": 1,
                    "saltinis": SITE_ROOT + "rvapgl.htm-760.htm",
                },
            },
        )
        normalized = record["normalized"]
        self.assertEqual(list(normalized.keys()), ["profilis", "anketa", "biografija", "turto-ir-pajamu-deklaracijos"])
        self.assertEqual(normalized["profilis"]["pastaba"], "šioje apygardoje išrinktas Seimo nariu")
        self.assertEqual(list(normalized["profilis"]["kita"].keys()), ["apygarda", "iskele", "apygarda-2", "iskele-2", "priesrinkiminis-numeris-sarase", "iskele-3", "buves-numeris-sarase"])
        self.assertEqual(normalized["profilis"]["kita"]["apygarda"]["reiksme"], "Žirmūnų (Nr. 4), šioje apygardoje išrinktas Seimo nariu.")
        anketa = normalized["anketa"]
        self.assertEqual(
            list(anketa.keys()),
            [
                "gimimo-data", "adresas", "pareiskimai", "gimimo-vieta", "issilavinimas", "mokslo-laipsnis",
                "pedagoginis-vardas", "uzsienio-kalbos", "anksciau-isrinktas", "pagrindine-darboviete",
                "visuomenine-veikla", "pomegiai", "seimine-padetis", "sutuoktinio-vardas-pavarde",
                "vaiku-vardai-pavardes", "seimos-nariai",
            ],
        )
        self.assertEqual((anketa["gimimo-data"], anketa["adresas"], anketa["gimimo-vieta"]), ("1951-08-09", "Vilnius", None))
        self.assertEqual(
            anketa["pareiskimai"],
            {
                "ar-nebaigta-teismo-paskirta-bausme": "Neturi",
                "ar-atliekate-karo-tarnyba": "Nėra",
                "ar-turite-kitos-valstybes-pilietybe": "Neturi",
                "kitos-valstybes-pilietybe-valstybe": None,
                "ar-susijes-priesaika-uzsienio-valstybei": "Nėra",
                "priesaikos-uzsienio-valstybei-atsisakymas": None,
                "ar-bendradarbiavote-su-uzsienio-tarnybomis": "Nėra",
                "ar-buvote-pripazintas-kaltu": "Nėra",
                "ar-buvote-pripazintas-kaltu-del-sunkaus-nusikaltimo": "Nebuvo",
                "teisiniai-argumentai": None,
            },
        )
        self.assertEqual(
            anketa["issilavinimas"]["irasai"],
            [
                {"mokymo-istaigos-pavadinimas": "Vilniaus universitetas", "specialybe": "istorija", "baigimo-metai": "1984"},
                {"mokymo-istaigos-pavadinimas": "Kauno medicinos institutas", "specialybe": "chirurgija", "baigimo-metai": "1975"},
            ],
        )
        self.assertEqual(anketa["uzsienio-kalbos"], ["Anglų", "Vokiečių", "Lenkų", "Rusų"])
        self.assertEqual([r["institucijos-pavadinimas-pareigos"] for r in anketa["anksciau-isrinktas"]["irasai"]], ["Lietuvos Respublikos Aukščiausioji Taryba", "Lietuvos Respublikos Seimas", "Vilniaus miesto savivaldybės taryba"])
        self.assertEqual((anketa["pagrindine-darboviete"], anketa["visuomenine-veikla"], anketa["seimine-padetis"]), ("Lietuvos Respublikos Seimas, Seimo narys", "LSDP pirmininkas", "Vedęs"))
        self.assertEqual(anketa["pomegiai"], "Etnografija, Filosofija, Medicina, Muzika, Poezija, Sportas")
        self.assertEqual((anketa["sutuoktinio-vardas-pavarde"], anketa["vaiku-vardai-pavardes"]), ("Irena", "Šarūnas, Gediminas, Rūta"))
        self.assertEqual(anketa["seimos-nariai"][0], {"vardas": "Irena", "rysys": "sutuoktinis/sutuoktinė"})
        declaration = normalized["turto-ir-pajamu-deklaracijos"]
        self.assertEqual((declaration["gautos-pajamos"], declaration["turtas-ir-pinigines-lesos-metu-pradzioje"], declaration["darboviete"], declaration["pareigos"]), (19268.76, 241371, "LR Seimas", "Seimo narys"))
        self.assertTrue(normalized["biografija"]["tekstas"].startswith("Vytenis Povilas ANDRIUKAITIS"))
        self.assertEqual(record["source"]["candidateSourceUrl"], SITE_ROOT + "kandvl.htm-154044.htm")
        self.assertEqual(list(record["rawData"].keys()), ["profile", "candidacies", "anketa", "residence", "biography", "declaration"])

    def test_self_nominated_constituency_winner(self) -> None:
        require(DEFAULT_RESULTS_PATH)
        record, stats = _parse("uspaskich-viktor")
        self.assertEqual(stats["anomalies"], [])
        candidacy = record["kandidatavimas"]
        self.assertEqual((candidacy["roles"], candidacy["daugiamandate"], candidacy["isrinktas"], candidacy["isrinktasKaip"]), (["vienmandate"], None, True, "vienmandate"))
        self.assertEqual(candidacy["vienmandate"]["iskele"], "Išsikėlė pats")
        self.assertNotIn("porinkiminisNumerisSarase", candidacy)
        self.assertEqual(candidacy["vienmandatesBalsai"]["isViso"], 16057)
        self.assertEqual(candidacy["vienmandatesBalsai"]["vieta"], 1)
        self.assertEqual(record["normalized"]["anketa"]["adresas"], "Kėdainiai, Kėdainių raj.")
        declaration = record["normalized"]["turto-ir-pajamu-deklaracijos"]
        self.assertEqual(declaration["turtas-ir-pinigines-lesos-metu-pradzioje"], 60571532)
        self.assertEqual((declaration["nepagrindines-darbovietes"], declaration["pareigos-nepagrindinese-darbovietese"]), ('UAB "Songailai"', "Komercijos direktorius"))

    def test_list_seat_without_photo_or_biography(self) -> None:
        require(DEFAULT_RESULTS_PATH)
        record, stats = _parse("maldeikis-eugenijus")
        self.assertEqual(stats["anomalies"], [])
        candidacy = record["kandidatavimas"]
        self.assertEqual((candidacy["roles"], candidacy["vienmandate"], candidacy["isrinktas"], candidacy["isrinktasKaip"], candidacy["porinkiminisNumerisSarase"]), (["daugiamandate"], None, True, "daugiamandate", 2))
        self.assertNotIn("vienmandatesBalsai", candidacy)
        self.assertIsNone(record["normalized"]["profilis"]["nuotrauka"])
        self.assertIsNone(record["normalized"]["biografija"])
        self.assertEqual(
            record["normalized"]["anketa"]["issilavinimas"]["irasai"][1],
            {"mokymo-istaigos-pavadinimas": "Maskvos valstybinis universitetas, Ekonomikos fakultetas", "specialybe": "Ekonomistas", "baigimo-metai": "1978"},
        )

    def test_losers_and_the_gap(self) -> None:
        require(DEFAULT_RESULTS_PATH)
        record, stats = _parse("petkus-viktoras")
        self.assertEqual(stats["anomalies"], [])
        self.assertEqual((record["kandidatavimas"]["isrinktas"], record["kandidatavimas"]["porinkiminisNumerisSarase"], record["kandidatavimas"]["pirmumoBalsai"]), (False, 3, 19111))
        self.assertEqual(record["normalized"]["profilis"]["pastaba"], None)
        self.assertEqual(record["normalized"]["anketa"]["seimos-nariai"], [])
        self.assertEqual(record["normalized"]["anketa"]["issilavinimas"]["irasai"], [{"mokymo-istaigos-pavadinimas": "Raseinių D.J.vidurinė m-kla", "specialybe": None, "baigimo-metai": "1954"}])
        record, stats = _parse("smigelskas-virginijus")
        self.assertEqual(stats["anomalies"], [])
        self.assertEqual(record["kandidatavimas"]["vienmandate"]["iskele"], "Lietuvos centro sąjunga")
        self.assertEqual(record["kandidatavimas"]["vienmandatesBalsai"]["vieta"], 7)
        record, stats = _parse("terleckas-antanas")
        self.assertEqual(stats["anomalies"], [])
        self.assertEqual((record["kandidatavimas"]["vienmandate"]["iskele"], record["kandidatavimas"]["daugiamandate"]["sarasas"]), ("Lietuvos laisvės lyga", "Lietuvių tautininkų sąjunga"))
        self.assertNotIn("kitiIskelejai", record["kandidatavimas"]["vienmandate"])


if __name__ == "__main__":
    unittest.main()
