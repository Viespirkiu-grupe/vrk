import json
import tempfile
import unittest
from pathlib import Path

from scraper.elections.savivaldybiu_2000.anketa_parser import (
    FIELD_KEYS,
    build_candidacy,
    finish_candidacy,
    normalize_anketa,
    parse_anketa_sample,
    parse_candidate_html,
)
from scraper.elections.savivaldybiu_2000.candidate_samples import EXPECTED_TABS
from scraper.elections.savivaldybiu_2000.results import (
    build_results,
    parse_members_page,
    parse_municipality_results_page,
    parse_preference_page,
)
from scraper.elections.savivaldybiu_2000.sitemap import (
    ELECTION_ID,
    LISTING_URL,
    MUNICIPALITIES_URL,
    SITE_ROOT,
    build_sitemap_from_sample,
    extract_municipality_links,
    extract_party_links,
    parse_list_page,
    parse_municipality_page,
    parse_party_page,
)


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


class Savivaldybiu2000SitemapTests(unittest.TestCase):
    def test_indexes(self) -> None:
        municipalities = extract_municipality_links((SAMPLES_ROOT / "municipalities.html").read_text(encoding="utf-8"))
        self.assertEqual(len(municipalities), 60)
        self.assertEqual(municipalities[0], {
            "municipalityId": "563",
            "number": 1,
            "name": "Akmenės rajono",
            "resultsUrl": SITE_ROOT + "rapgpl.htm-563.htm",
            "url": SITE_ROOT + "apgl.htm-12+1.htm",
        })
        self.assertEqual((municipalities[56]["number"], municipalities[56]["municipalityId"], municipalities[56]["name"]), (57, "551", "Vilniaus miesto"))
        parties = extract_party_links((SAMPLES_ROOT / "list.html").read_text(encoding="utf-8"))
        self.assertEqual(len(parties), 28)
        self.assertEqual(parties[0], {"partyId": "433", "number": 1, "name": "Lietuvos valstiečių partija", "url": SITE_ROOT + "papgsarl.htm-433.htm"})

    def test_page_readers(self) -> None:
        page = parse_municipality_page((SAMPLES_ROOT / "municipalities" / "municipality-57.html").read_text(encoding="utf-8"))
        self.assertEqual((page["name"], page["number"], page["municipalityId"], page["voters"], page["seats"], len(page["lists"])), ("Vilniaus miesto", 57, "551", 422722, 51, 21))
        kds = next(entry for entry in page["lists"] if entry["listId"] == "38")
        self.assertEqual(kds, {"listNumber": 21, "name": "Krikščionių demokratų sąjunga", "listId": "38", "municipalityId": "551", "url": SITE_ROOT + "pkal.htm-551+38.htm", "vrkDecision": "2000 02 08, Nr.36"})
        coalition = next(entry for entry in page["lists"] if entry["listId"] == "2799")
        self.assertIsNone(coalition["vrkDecision"])
        rows = parse_party_page((SAMPLES_ROOT / "parties" / "party-407.html").read_text(encoding="utf-8"))
        self.assertEqual(len(rows), 24)
        self.assertEqual(sum(1 for row in rows if row["ownList"]), 6)
        self.assertEqual(rows[0], {"municipalityId": "564", "listId": "2791", "municipalityName": "Alytaus rajono", "ownList": False, "url": SITE_ROOT + "pkal.htm-564+2791.htm"})
        page = parse_list_page((SAMPLES_ROOT / "lists" / "list-551-38.html").read_text(encoding="utf-8"))
        self.assertEqual((page["name"], page["representatives"], len(page["candidates"])), ("Krikščionių demokratų sąjunga", "Cicilionis Nerijus", 9))
        self.assertEqual(page["candidates"][0], {"listNumber": 1, "candidateName": "Petkus Viktoras", "url": SITE_ROOT + "kandvl.htm-89850.htm"})

    def test_three_hops_reconcile_with_the_party_pages(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            _, stats = build_sitemap_from_sample(sample_path=SAMPLES_ROOT, output_path=Path(tmp) / "sitemap.json")
            payload = json.loads((Path(tmp) / "sitemap.json").read_text(encoding="utf-8"))
        self.assertEqual(
            payload["stats"],
            {
                "municipalities": 60,
                "partyLists": 651,
                "coalitionLists": 26,
                "missingPartyListSamples": 0,
                "parties": 28,
                "listsClaimedByParties": 651,
                "claimedNotWalked": 0,
                "walkedNotClaimed": 0,
                "ownClaimNameMismatches": 0,
                "municipalityIdMismatches": 0,
                "duplicateVrkIds": 0,
                "duplicateCandidateIds": 0,
                "seatsDeclared": 1562,
            },
        )
        self.assertEqual((stats["rows"], stats["extracted"], stats["skipped"], stats["duplicate_candidate_ids"]), (651, 9881, 0, 0))
        self.assertEqual(payload["sourceUrl"], LISTING_URL)
        self.assertEqual(payload["municipalitiesUrl"], MUNICIPALITIES_URL)
        self.assertEqual(len(payload["municipalities"]), 60)
        by_id = {entry["candidateId"]: entry for entry in payload["entries"]}
        self.assertEqual(
            by_id["paksas-rolandas-84817"],
            {
                "candidateName": "Paksas Rolandas",
                "candidateId": "paksas-rolandas-84817",
                "url": SITE_ROOT + "kandvl.htm-84817.htm",
                "vrkCandidateId": "84817",
                "municipality": {"pavadinimas": "Vilniaus miesto", "numeris": 57, "savivaldybesId": "551", "mandatai": 51},
                "list": {"pavadinimas": "Lietuvos liberalų sąjunga", "rusis": "partija", "numeris": 17, "sarasoId": "28", "vrkSprendimas": "2000 01 21, Nr.13"},
                "listPosition": 1,
            },
        )
        # A coalition list: no VRK decision on the municipality page, the
        # member parties from the party pages.
        self.assertEqual(
            by_id["jusas-albertas-94748"]["list"],
            {
                "pavadinimas": "Lietuvos valstiečių partijos ir Krikščionių demokratų sąjungos koalicija",
                "rusis": "koalicija",
                "numeris": 1,
                "sarasoId": "2791",
                "vrkSprendimas": None,
                "koalicijosPartijos": ["Lietuvos valstiečių partija", "Krikščionių demokratų sąjunga"],
            },
        )


class Savivaldybiu2000ResultsTests(unittest.TestCase):
    def test_page_readers(self) -> None:
        page = parse_municipality_results_page((RESULTS_DIR / "20000319__rapgpl.htm-551.htm").read_text(encoding="utf-8"))
        self.assertEqual((page["voters"], page["turnout"], page["turnoutPercent"], page["quota"], len(page["lists"])), (398023, 211671, 53.18, 3283, 21))
        self.assertEqual(page["lists"][0], {"listNumber": 17, "name": "Lietuvos liberalų sąjunga", "municipalityId": "551", "listId": "28", "preferenceUrl": SITE_ROOT + "rpbapgl.htm-551+28.htm", "ballotBox": 56970, "postal": 1371, "total": 58341, "mandates": 18})
        self.assertIsNone(page["lists"][-1]["mandates"])
        self.assertEqual(page["total"], {"ballotBox": 199647, "postal": 5035, "total": 204682, "mandates": 51})
        # One of the five municipalities captured without links: the rows
        # are there, unlinked.
        page = parse_municipality_results_page((RESULTS_DIR / "20000319__rapgpl.htm-570.htm").read_text(encoding="utf-8"))
        self.assertEqual((len(page["lists"]), page["lists"][0]["listId"], page["lists"][0]["name"], page["lists"][0]["mandates"], page["total"]), (9, None, "Lietuvos valstiečių partija", 9, {"ballotBox": 12354, "postal": 1909, "total": 14263, "mandates": 25}))
        members = parse_members_page((RESULTS_DIR / "20000319__rikl.htm-551.htm").read_text(encoding="utf-8"))
        self.assertEqual((members["seats"], len(members["members"])), (51, 51))
        self.assertEqual(members["members"][0], {"vrkCandidateId": "84817", "name": "Paksas Rolandas", "listName": "Lietuvos liberalų sąjunga", "listId": "28", "rank": 1})
        rows = parse_preference_page((RESULTS_DIR / "20000319__rpbapgl.htm-551+28.htm").read_text(encoding="utf-8"))
        self.assertEqual(len(rows), 50)
        self.assertEqual(rows[0], {"rank": 1, "vrkCandidateId": "84817", "name": "Paksas Rolandas", "preferenceVotes": 47349, "listPosition": 1, "mandate": True})
        self.assertEqual(sum(1 for row in rows if row["mandate"]), 18)

    def test_members_lists_and_rankings_reconcile(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            _, stats = build_results(sitemap_path=SITEMAPS / f"{ELECTION_ID}.json", results_dir=RESULTS_DIR, output_path=Path(tmp) / "results.json")
            payload = json.loads((Path(tmp) / "results.json").read_text(encoding="utf-8"))
        self.assertEqual(
            stats,
            {
                "municipalities": 60,
                "municipalitiesWithResults": 55,
                "resultsUnavailable": 5,
                "candidatesWithoutResults": 806,
                "seatsWithoutMembers": 129,
                "membersPagesMissing": 0,
                "unresolvedListRows": 0,
                "councilMembers": 1433,
                "membersOnPages": 1433,
                "councilNotInSitemap": 0,
                "municipalityMismatches": 0,
                "listMismatches": 0,
                "seatCountMismatches": 0,
                "rankMismatches": 0,
                "boldNotMembers": 0,
                "listTopRanksNotMembers": 0,
                "candidatesRanked": 9075,
                "rankedNotInSitemap": 0,
                "sitemapNotRanked": 0,
                "listPositionMismatches": 0,
                "seats": {"tarybos-narys": 1433},
            },
        )
        self.assertEqual([row["name"] for row in payload["details"]["resultsUnavailable"]], ["Jurbarko rajono", "Kelmės rajono", "Radviliškio rajono", "Raseinių rajono", "Vilkaviškio rajono"])
        self.assertEqual(payload["elected"]["84817"], {
            "seat": "tarybos-narys",
            "method": "mandates-page",
            "sourceUrl": SITE_ROOT + "rikl.htm-551.htm",
            "municipality": "Vilniaus miesto",
            "municipalityId": "551",
            "listName": "Lietuvos liberalų sąjunga",
            "listId": "28",
            "rank": 1,
        })
        self.assertEqual(payload["details"]["listResults"]["570"]["25"]["mandates"], 9)
        self.assertEqual(len(payload["details"]["listResults"]), 60)


class Savivaldybiu2000CardParserTests(unittest.TestCase):
    def test_expected_tabs_is_empty(self) -> None:
        self.assertEqual(EXPECTED_TABS, [])

    def test_card_questions_fields_and_declaration(self) -> None:
        parsed = parse_candidate_html((SAMPLES_ROOT / "petkus-viktoras-89850" / "candidate.html").read_text(encoding="utf-8"))
        self.assertEqual(parsed["profile"]["candidateDisplayName"], "Viktoras PETKUS")
        self.assertEqual(
            parsed["candidacy"],
            {
                "municipalityName": "Vilniaus miesto",
                "municipalityNumber": 57,
                "municipalityUrl": SITE_ROOT + "apgl.htm-12+57.htm",
                "listName": "Krikščionių demokratų sąjungos",
                "listUrl": SITE_ROOT + "pkal.htm-551+38.htm",
                "listPosition": 1,
                "memberParty": None,
                "memberListNumber": None,
            },
        )
        self.assertEqual((parsed["birthDate"], parsed["birthPlace"], parsed["residence"]), ("1930 10 22", None, "Vilnius"))
        self.assertEqual(
            [(q["key"], q["answer"]) for q in parsed["questions"]],
            [
                ("ar-nebaigta-teismo-paskirta-bausme", "Neturi"),
                ("ar-atliekate-karo-tarnyba", "Nėra"),
                ("ar-turite-kitos-valstybes-pilietybe", "Neturi"),
                ("ar-bendradarbiavote-su-uzsienio-tarnybomis", "Ne"),
                ("ar-buvote-pripazintas-kaltu", "Ne"),
            ],
        )
        self.assertEqual([f["label"] for f in parsed["fields"]], ["Išsilavinimas", "Pagrindinė darbovietė", "Šeimyninė padėtis"])
        self.assertTrue(parsed["diagnostics"]["declarationFound"])
        self.assertEqual(parsed["declaration"]["declaration"]["turtas-ir-pinigines-lesos-metu-pradzioje"], 115000)
        self.assertEqual(parsed["declaration"]["declaration"]["pareigos"], "Pensininkas")
        self.assertNotIn("darboviete", parsed["declaration"]["declaration"])

    def test_every_card_label_is_mapped(self) -> None:
        for candidate_dir in sorted(SAMPLES_ROOT.iterdir()):
            if not (candidate_dir / "candidate.html").exists():
                continue
            with self.subTest(candidate_dir.name):
                parsed = parse_candidate_html((candidate_dir / "candidate.html").read_text(encoding="utf-8"))
                _, unknown = normalize_anketa(parsed)
                self.assertEqual(unknown, [])
                self.assertTrue(all(field["label"].lower() in FIELD_KEYS for field in parsed["fields"]))

    def test_coalition_card_names_the_member_party(self) -> None:
        parsed = parse_candidate_html((SAMPLES_ROOT / "jusas-albertas-94748" / "candidate.html").read_text(encoding="utf-8"))
        self.assertEqual((parsed["candidacy"]["listName"], parsed["candidacy"]["listPosition"], parsed["candidacy"]["memberParty"], parsed["candidacy"]["memberListNumber"]),
                         ("Lietuvos valstiečių partijos ir Krikščionių demokratų sąjungos koalicijos", 1, "Krikščionių demokratų sąjunga", 1))
        self.assertEqual([f["key"] for f in parsed["profile"]["fields"]], ["Apygarda", "Sąrašas", "priešrinkiminis numeris sąraše", "iškėlė", "buvęs numeris sąraše"])
        candidacy = build_candidacy({"municipality": {"numeris": 3}, "list": {"rusis": "koalicija", "koalicijosPartijos": ["Lietuvos valstiečių partija", "Krikščionių demokratų sąjunga"]}, "listPosition": 1})
        self.assertEqual(finish_candidacy(candidacy, parsed), [])
        self.assertEqual((candidacy["tarybosNarys"]["koalicijosPartija"], candidacy["tarybosNarys"]["numerisPartijosSarase"]), ("Krikščionių demokratų sąjunga", 1))
        wrong = build_candidacy({"municipality": {"numeris": 4}, "list": {"rusis": "partija"}, "listPosition": 2})
        self.assertEqual([p["eventType"] for p in finish_candidacy(wrong, parsed)], ["CardMemberPartyMismatch", "CardMunicipalityMismatch", "CardListPositionMismatch"])


class Savivaldybiu2000RecordTests(unittest.TestCase):
    def test_list_leader_elected(self) -> None:
        record, stats = _parse("paksas-rolandas-84817")
        self.assertEqual(stats["anomalies"], [])
        self.assertEqual(record["candidateName"], "Rolandas PAKSAS")
        self.assertEqual(
            record["kandidatavimas"],
            {
                "vrkCandidateId": "84817",
                "savivaldybe": "Vilniaus miesto",
                "savivaldybesNumeris": 57,
                "savivaldybesId": "551",
                "roles": ["tarybos-narys"],
                "tarybosNarys": {
                    "partyList": "Lietuvos liberalų sąjunga",
                    "listKind": "partija",
                    "listNumber": 17,
                    "sarasoId": "28",
                    "listPosition": 1,
                    "vrkSprendimas": "2000 01 21, Nr.13",
                    "sarasoBalsai": 58341,
                    "sarasoMandatai": 18,
                    "sarasoRezultatuSaltinis": SITE_ROOT + "rapgpl.htm-551.htm",
                },
                "isrinktas": True,
                "isrinktasKaip": "tarybos-narys",
                "rezultatuSaltinis": SITE_ROOT + "rikl.htm-551.htm",
                "porinkiminisNumerisSarase": 1,
                "pirmumoBalsai": 47349,
                "pirmumoBalsuSaltinis": SITE_ROOT + "rpbapgl.htm-551+28.htm",
            },
        )
        normalized = record["normalized"]
        self.assertEqual(list(normalized.keys()), ["profilis", "anketa", "turto-ir-pajamu-deklaracijos"])
        self.assertEqual(list(normalized["profilis"]["kita"].keys()), ["apygarda", "sarasas", "priesrinkiminis-numeris-sarase"])
        self.assertEqual(normalized["profilis"]["kita"]["sarasas"]["reiksme"], "Lietuvos liberalų sąjungos")
        self.assertIsNone(normalized["profilis"]["nuotrauka"])
        self.assertEqual(
            list(normalized["anketa"].keys()),
            ["gimimo-data", "adresas", "pareiskimai", "gimimo-vieta", "issilavinimas", "mokslo-laipsnis", "pedagoginis-vardas", "uzsienio-kalbos", "anksciau-isrinktas", "pagrindine-darboviete", "visuomenine-veikla", "seimine-padetis", "kita-apie-save"],
        )
        self.assertEqual(
            normalized["anketa"]["pareiskimai"],
            {
                "ar-nebaigta-teismo-paskirta-bausme": "Neturi",
                "ar-atliekate-karo-tarnyba": "Nėra",
                "ar-turite-kitos-valstybes-pilietybe": "Neturi",
                "kitos-valstybes-pilietybe-valstybe": None,
                "priesaikos-uzsienio-valstybei-atsisakymas": None,
                "ar-bendradarbiavote-su-uzsienio-tarnybomis": "Ne",
                "ar-buvote-pripazintas-kaltu": "Ne",
                "teisiniai-argumentai": None,
            },
        )
        self.assertEqual(normalized["anketa"]["issilavinimas"], {"aprasas": "Aukštasis", "irasai": []})
        self.assertEqual(normalized["anketa"]["uzsienio-kalbos"], ["Anglų", "Rusų"])
        self.assertEqual(normalized["turto-ir-pajamu-deklaracijos"]["darboviete"], "LR Prezidentūra")
        self.assertEqual(list(record["rawData"].keys()), ["profile", "candidacy", "anketa", "residence", "declaration"])

    def test_climber_coalition_member_and_loser(self) -> None:
        record, stats = _parse("cekuolis-jonas-85130")
        self.assertEqual(stats["anomalies"], [])
        self.assertEqual((record["kandidatavimas"]["tarybosNarys"]["listPosition"], record["kandidatavimas"]["porinkiminisNumerisSarase"], record["kandidatavimas"]["isrinktas"]), (52, 6, True))
        record, stats = _parse("zekas-algis-94742")
        self.assertEqual(stats["anomalies"], [])
        council = record["kandidatavimas"]["tarybosNarys"]
        self.assertEqual((council["listKind"], council["koalicijosPartija"], council["numerisPartijosSarase"], council["vrkSprendimas"], council["sarasoMandatai"]), ("koalicija", "Lietuvos valstiečių partija", 4, None, 4))
        self.assertEqual(record["kandidatavimas"]["isrinktasKaip"], "tarybos-narys")
        record, stats = _parse("lizdenis-antanas-85463")
        self.assertEqual(stats["anomalies"], [])
        self.assertEqual((record["kandidatavimas"]["isrinktas"], record["kandidatavimas"]["tarybosNarys"]["sarasoMandatai"], record["kandidatavimas"]["porinkiminisNumerisSarase"], record["kandidatavimas"]["pirmumoBalsai"]), (False, 0, 1, 234))

    def test_results_unavailable_municipality_keeps_elected_unknown(self) -> None:
        record, stats = _parse("zairys-aloyzas-86350")
        self.assertEqual(stats["anomalies"], [])
        candidacy = record["kandidatavimas"]
        self.assertIsNone(candidacy["isrinktas"])
        self.assertNotIn("porinkiminisNumerisSarase", candidacy)
        self.assertEqual((candidacy["tarybosNarys"]["sarasoBalsai"], candidacy["tarybosNarys"]["sarasoMandatai"]), (5177, 9))
        self.assertEqual(candidacy["rezultataiNeskelbiami"]["nariuPuslapis"], SITE_ROOT + "rikl.htm-570.htm")


if __name__ == "__main__":
    unittest.main()
