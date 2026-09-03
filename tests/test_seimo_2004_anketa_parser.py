import json
import tempfile
import unittest
from pathlib import Path

from scraper.elections.ep_2004.anketa_parser import parse_anketa_html
from scraper.elections.seimo_2004.anketa_parser import (
    DEFAULT_RESULTS_PATH,
    finish_candidacy,
    normalize_seimo_2004_anketa_rows,
    parse_anketa_sample,
)
from scraper.elections.seimo_2004.candidate_samples import EXPECTED_TABS
from scraper.elections.seimo_2004.results import MEMBERS_PAGE, RESULTS_ROOT, build_results, parse_members_page
from scraper.elections.seimo_2004.sitemap import (
    DISTRICTS_URL,
    ELECTION_ID,
    LISTING_URL,
    build_sitemap_from_sample,
    extract_district_links,
    extract_party_links,
    party_page_records,
)

from local_data import require


REPO_ROOT = Path(__file__).resolve().parents[1]
SAMPLES_ROOT = REPO_ROOT / "samples" / "html" / ELECTION_ID
RESULTS_DIR = REPO_ROOT / "samples" / "results" / ELECTION_ID
SITEMAPS = REPO_ROOT / "sitemaps"
CANDIDATES = "https://www.vrk.lt/statiniai/puslapiai/rinkimai/2004/seimas/kandidatai/"
REZULTATAI = "https://www.vrk.lt/statiniai/puslapiai/rinkimai/2004/seimas/rezultatai/"


def _parse(candidate_id: str) -> tuple[dict, dict]:
    with tempfile.TemporaryDirectory() as tmp:
        output_path, stats = parse_anketa_sample(
            candidate_id=candidate_id,
            samples_root=SAMPLES_ROOT,
            output_root=Path(tmp),
        )
        return json.loads(output_path.read_text(encoding="utf-8")), stats


class Seimo2004SitemapTests(unittest.TestCase):
    def test_index_kinds(self) -> None:
        links = extract_party_links((SAMPLES_ROOT / "list.html").read_text(encoding="utf-8"))
        self.assertEqual(len(links), 22)
        kinds = [link["kind"] for link in links]
        self.assertEqual(kinds.count("sarasas"), 15)
        self.assertEqual(kinds.count("tik-vienmandatese"), 3)
        self.assertEqual(kinds.count("koalicijos-nare"), 4)
        member = next(link for link in links if link["listKey"] == "1829")
        self.assertEqual(member, {
            "listKey": "1829",
            "kind": "koalicijos-nare",
            "listNumber": None,
            "coalitionListNumber": 6,
            "name": "Lietuvos socialdemokratų partija",
            "declaredCount": 99,
            "url": CANDIDATES + "kand_part_l_1829.htm",
        })
        districts = extract_district_links((SAMPLES_ROOT / "districts.html").read_text(encoding="utf-8"))
        self.assertEqual(len(districts), 71)
        self.assertEqual(districts[0], {"districtId": "1603", "number": 1, "name": "Naujamiesčio", "url": CANDIDATES + "apg_kand_l_1603.htm"})
        self.assertEqual(districts[70]["number"], 71)

    def test_party_page_shapes(self) -> None:
        index = {link["listKey"]: link for link in extract_party_links((SAMPLES_ROOT / "list.html").read_text(encoding="utf-8"))}
        # A plain list: numbered rows with the constituency column; the
        # unnumbered rows below are the party's constituency-only nominees.
        rows = party_page_records((SAMPLES_ROOT / "lists" / "list-1836.html").read_text(encoding="utf-8"), index["1836"])
        self.assertEqual(len(rows), 31)
        self.assertEqual(rows[0]["candidateName"], "Vytautas ŠUSTAUSKAS")
        self.assertEqual((rows[0]["position"], rows[0]["districtId"], rows[0]["hasDistrictColumn"]), (1, "1623", True))
        self.assertEqual([row["position"] for row in rows[-2:]], [None, None])
        # A coalition's page: the coalition position, the member party and
        # the member position, no constituency column.
        rows = party_page_records((SAMPLES_ROOT / "lists" / "list-1874.html").read_text(encoding="utf-8"), index["1874"])
        self.assertEqual(len(rows), 137)
        self.assertEqual((rows[0]["candidateName"], rows[0]["position"], rows[0]["memberParty"], rows[0]["memberPartyKey"], rows[0]["memberPosition"], rows[0]["hasDistrictColumn"]),
                         ("Valentinas MAZURONIS", 1, "Liberalų demokratų partija", "1866", 1, False))
        # A member party's page: its own numbering with the coalition
        # position alongside.
        rows = party_page_records((SAMPLES_ROOT / "lists" / "list-1829.html").read_text(encoding="utf-8"), index["1829"])
        self.assertEqual((rows[1]["candidateName"], rows[1]["position"], rows[1]["coalitionPosition"], rows[1]["districtId"]), ("Algirdas BUTKEVIČIUS", 2, 4, "1670"))

    def test_two_structures_reconcile(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            _, stats = build_sitemap_from_sample(sample_path=SAMPLES_ROOT, output_path=Path(tmp) / "sitemap.json")
            payload = json.loads((Path(tmp) / "sitemap.json").read_text(encoding="utf-8"))
        self.assertEqual(
            payload["stats"],
            {
                "rows": 2100,
                "extracted": 1251,
                "duplicateCandidateIds": 0,
                "lists": 15,
                "sidePages": 7,
                "districts": 71,
                "dual": 534,
                "listOnly": 649,
                "districtOnly": 68,
                "declaredCountMismatches": 0,
                "unnumberedRowsOnLists": 9,
                "unnumberedRowsNotInAnyConstituency": 0,
                "memberPositionMismatches": 0,
                "listColumnConstituencyWrong": 0,
                "constituencyByAnotherNominator": 17,
                "duplicateDistrictRows": 0,
                "selfNominated": 49,
                "districtOnlyReconciled": True,
                "districtOnlyUnaccounted": 0,
            },
        )
        self.assertEqual(stats["skipped"], 0)
        self.assertEqual(payload["sourceUrl"], LISTING_URL)
        self.assertEqual(payload["districtsUrl"], DISTRICTS_URL)
        by_id = {entry["candidateId"]: entry for entry in payload["entries"]}
        self.assertEqual(
            by_id["vytautas-sustauskas"],
            {
                "candidateName": "Vytautas ŠUSTAUSKAS",
                "candidateId": "vytautas-sustauskas",
                "url": CANDIDATES + "kand_anketa_l_294403.htm",
                "vrkCandidateId": "294403",
                "roles": ["daugiamandate", "vienmandate"],
                "daugiamandateCandidacy": {"sarasas": "Lietuvos laisvės sąjunga", "sarasoNumeris": 1, "sarasoId": "1836", "numerisSarase": 1},
                "vienmandateCandidacy": {"apygarda": "Marių", "apygardosNumeris": 21, "apygardosId": "1623", "iskele": "Lietuvos laisvės sąjunga"},
            },
        )
        # A coalition candidate carries the member party and the position on
        # its list; a constituency-only nominee of a numbered-list party has
        # no list candidacy; a cross-party constituency nominee keeps the
        # constituency page's nominator.
        self.assertEqual(
            by_id["valentinas-mazuronis"]["daugiamandateCandidacy"],
            {"sarasas": 'Rolando Pakso koalicija "Už tvarką ir teisingumą"', "sarasoNumeris": 8, "sarasoId": "1874", "numerisSarase": 1,
             "koalicijosPartija": "Liberalų demokratų partija", "numerisPartijosSarase": 1},
        )
        self.assertEqual(by_id["vytautas-ricardas-backis"]["roles"], ["vienmandate"])
        self.assertEqual(by_id["vytautas-ricardas-backis"]["vienmandateCandidacy"]["iskele"], "Tėvynės sąjunga (konservatoriai, politiniai kaliniai ir tremtiniai, krikščioniškieji demokratai)")
        self.assertEqual(by_id["nikolajus-salkovskis"]["daugiamandateCandidacy"]["sarasas"], "Lietuvos lenkų rinkimų akcija")
        self.assertEqual(by_id["nikolajus-salkovskis"]["vienmandateCandidacy"]["iskele"], "Lietuvos rusų sąjunga")
        self.assertEqual(by_id["saulius-gintautas"]["vienmandateCandidacy"]["iskele"], "Išsikėlė pats")


class Seimo2004ResultsTests(unittest.TestCase):
    def test_results_file_reconciles(self) -> None:
        self.assertEqual(MEMBERS_PAGE, "rez_isrinkti_l_20_1.htm")
        payload = json.loads((SITEMAPS / f"{ELECTION_ID}.results.json").read_text(encoding="utf-8"))
        self.assertEqual(
            payload["stats"],
            {
                "seats": 141,
                "membersListed": 141,
                "membersInSitemap": 141,
                "membersNotInSitemap": 0,
                "listSeats": 70,
                "constituencySeats": 71,
                "constituencySeatsFirstRound": 5,
                "constituencySeatsRunoff": 66,
                "roleMismatches": 0,
                "districtMismatches": 0,
                "roundMarkerMismatches": 0,
                "listWinnersPageDiff": 0,
                "constituencyWinnersPageDiff": 0,
                "mandatesDeclared": 70,
                "listMandateMismatches": 0,
                "rankingPages": 15,
                "candidatesRanked": 1183,
                "rankedNotInSitemap": 0,
                "listCandidatesNotRanked": 0,
                "boldNotListSeats": 0,
                "listSeatsNotBold": 0,
                "listPositionMismatches": 0,
                "unrankedLists": 1,
                "candidatesOnUnrankedLists": 128,
            },
        )
        self.assertEqual(payload["details"]["unrankedLists"], ["1832"])
        self.assertEqual(payload["elected"]["294653"], {
            "seat": "vienmandate", "method": "members-list", "sourceUrl": REZULTATAI + MEMBERS_PAGE,
            "party": "Tėvynės sąjunga (konservatoriai, politiniai kaliniai ir tremtiniai, krikščioniškieji demokratai)",
            "round": 2, "districtId": "1603", "districtNumber": 1, "districtName": "Naujamiesčio",
        })
        self.assertEqual(payload["elected"]["295030"]["round"], 1)
        self.assertEqual(payload["elected"]["294429"]["seat"], "daugiamandate")

    def test_builder_rebuilds_the_file_from_the_cached_pages(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output_path, stats = build_results(
                sitemap_path=SITEMAPS / f"{ELECTION_ID}.json",
                results_dir=RESULTS_DIR,
                output_path=Path(tmp) / "results.json",
            )
            payload = json.loads(output_path.read_text(encoding="utf-8"))
        committed = json.loads((SITEMAPS / f"{ELECTION_ID}.results.json").read_text(encoding="utf-8"))
        self.assertEqual(stats, committed["stats"])
        self.assertEqual(payload["elected"], committed["elected"])
        self.assertEqual(payload["elected"]["295030"]["round"], 1)
        self.assertEqual(payload["elected"]["294653"]["round"], 2)
        self.assertEqual(payload["details"]["ranking"]["295380"], {"rank": 1, "listPosition": None, "preferenceVotes": None, "ranked": False, "listId": "1832", "sourceUrl": REZULTATAI + "rez_pirm_l_1832.htm"})

    def test_members_page_rows(self) -> None:
        html = (RESULTS_DIR / "rezultatai__rez_isrinkti_l_20_1.htm").read_text(encoding="utf-8")
        members = parse_members_page(html, RESULTS_ROOT + MEMBERS_PAGE)
        self.assertEqual(len(members), 141)
        balcytis = next(m for m in members if m["vrkCandidateId"] == "295030")
        self.assertTrue(balcytis["firstRoundMarker"])
        self.assertEqual((balcytis["seat"], balcytis["round"], balcytis["districtNumber"], balcytis["districtName"]), ("vienmandate", 1, 33, "Šilalės - Šilutės"))
        self.assertEqual(sum(1 for m in members if m["firstRoundMarker"]), 5)


class Seimo2004AnketaParserTests(unittest.TestCase):
    def setUp(self) -> None:
        self.mazuronis, self.mazuronis_stats = _parse("valentinas-mazuronis")
        self.degutiene, _ = _parse("irena-degutiene")
        self.balcytis, _ = _parse("zigmantas-balcytis")
        self.tomasevski, _ = _parse("valdemar-tomasevski")
        self.gintautas, _ = _parse("saulius-gintautas")
        self.ziobakiene, self.ziobakiene_stats = _parse("genovaite-ziobakiene")

    def test_expected_tabs_are_the_2004_pages(self) -> None:
        self.assertEqual(EXPECTED_TABS, {"anketa", "biografija", "turto-ir-pajamu-deklaracijos"})

    def test_top_level_fields_and_candidacy(self) -> None:
        require(DEFAULT_RESULTS_PATH)
        self.assertEqual(self.mazuronis["electionId"], "2004-seimo")
        self.assertEqual(self.mazuronis["candidateName"], "Valentinas MAZURONIS")
        self.assertEqual(
            self.mazuronis["kandidatavimas"],
            {
                "vrkCandidateId": "294409",
                "roles": ["daugiamandate", "vienmandate"],
                "vienmandate": {"apygarda": "Dainų", "apygardosNumeris": 25, "apygardosId": "1627", "iskele": "Liberalų demokratų partija"},
                "daugiamandate": {
                    "sarasas": 'Rolando Pakso koalicija "Už tvarką ir teisingumą"',
                    "sarasoNumeris": 8,
                    "sarasoId": "1874",
                    "numerisSarase": 1,
                    "koalicijosPartija": "Liberalų demokratų partija",
                    "numerisPartijosSarase": 1,
                },
                "isrinktas": True,
                "isrinktasKaip": "daugiamandate",
                "rezultatuSaltinis": REZULTATAI + "rez_isrinkti_l_20_1.htm",
                "porinkiminisNumerisSarase": 3,
                "pirmumoBalsai": 52095,
                "pirmumoBalsuSaltinis": REZULTATAI + "rez_pirm_l_1874.htm",
                "savarankiskasKampanijosDalyvis": {
                    "sprendimas": "Nr.194, 2004.09.16",
                    "nuoroda": CANDIDATES + "pazym_l_318.pdf",
                },
            },
        )
        self.assertEqual(self.mazuronis_stats["anomalies"], [])
        self.assertEqual(list(self.mazuronis["normalized"].keys()), ["profilis", "anketa", "biografija", "turto-ir-pajamu-deklaracijos"])

    def test_constituency_seats_carry_the_round(self) -> None:
        require(DEFAULT_RESULTS_PATH)
        degutiene = self.degutiene["kandidatavimas"]
        self.assertEqual((degutiene["isrinktas"], degutiene["isrinktasKaip"], degutiene["rezultatuTuras"]), (True, "vienmandate", 2))
        balcytis = self.balcytis["kandidatavimas"]
        self.assertEqual((balcytis["isrinktasKaip"], balcytis["rezultatuTuras"]), ("vienmandate", 1))
        self.assertEqual(balcytis["daugiamandate"]["koalicijosPartija"], "Lietuvos socialdemokratų partija")
        self.assertEqual(balcytis["daugiamandate"]["numerisPartijosSarase"], 7)
        self.assertNotIn("rezultatuTuras", self.mazuronis["kandidatavimas"])

    def test_unranked_list_has_rank_but_no_votes(self) -> None:
        require(DEFAULT_RESULTS_PATH)
        tomasevski = self.tomasevski["kandidatavimas"]
        self.assertEqual(tomasevski["daugiamandate"]["sarasas"], "Lietuvos lenkų rinkimų akcija")
        self.assertEqual(tomasevski["porinkiminisNumerisSarase"], 1)
        self.assertIsNone(tomasevski["pirmumoBalsai"])
        self.assertEqual((tomasevski["isrinktasKaip"], tomasevski["rezultatuTuras"]), ("vienmandate", 1))
        self.assertNotIn("savarankiskasKampanijosDalyvis", tomasevski)

    def test_card_names_the_second_nominator(self) -> None:
        single = self.gintautas["kandidatavimas"]["vienmandate"]
        self.assertEqual(single["iskele"], "Išsikėlė pats")
        self.assertEqual(single["kitiIskelejai"], ["Liberalų demokratų partija"])
        kita = self.gintautas["normalized"]["profilis"]["kita"]
        self.assertEqual(
            [(key, value["reiksme"]) for key, value in kita.items()][:6],
            [
                ("apygarda", "Rokiškio (Nr.50)"),
                ("iskele", "Liberalų demokratų partija"),
                ("apygarda-2", "Rokiškio (Nr.50)"),
                ("iskele-2", "Išsikėlė pats"),
                ("apygarda-3", "Daugiamandatė"),
                ("iskele-3", 'Rolando Pakso koalicija "Už tvarką ir teisingumą"'),
            ],
        )
        self.assertNotIn("kitiIskelejai", self.degutiene["kandidatavimas"]["vienmandate"])

    def test_profile_card(self) -> None:
        profilis = self.mazuronis["normalized"]["profilis"]
        self.assertEqual(profilis["vardas-pavarde"], "Valentinas MAZURONIS")
        self.assertIsNone(profilis["pastaba"])
        # The page links the portrait on vrk.lt; the record carries the archived
        # sidecar and photoMeta remembers the URL it came from (issue #118).
        self.assertEqual(profilis["nuotrauka"], f"photos/{self.mazuronis['candidateId']}.jpg")
        self.assertEqual(
            self.mazuronis["rawData"]["profile"]["photoMeta"]["url"],
            "https://www.vrk.lt/statiniai/puslapiai/rinkimai/2004/seimas/nuotraukos/294409.jpg",
        )
        kita = profilis["kita"]
        self.assertEqual(
            list(kita.keys()),
            ["apygarda", "iskele", "apygarda-2", "iskele-2", "priesrinkiminis-numeris-sarase", "iskele-3", "priesrinkiminis-numeris-sarase-2",
             "kandidatas-registruotas-savarankisku-politines-kampanijos-dalyviu-sprendimas"],
        )
        self.assertEqual(kita["apygarda"], {"pavadinimas": "Apygarda", "reiksme": "Dainų (Nr.25)", "nuorodos": [CANDIDATES + "apg_kand_l_1627.htm"]})
        self.assertEqual(kita["apygarda-2"]["reiksme"], "Daugiamandatė")
        self.assertEqual(kita["iskele-2"]["reiksme"], 'Rolando Pakso koalicija "Už tvarką ir teisingumą"')
        self.assertEqual(kita["priesrinkiminis-numeris-sarase"]["reiksme"], "1")
        self.assertEqual(kita["iskele-3"], {"pavadinimas": "(Iškėlė", "reiksme": "Liberalų demokratų partija", "nuorodos": [CANDIDATES + "kand_part_l_1866.htm"]})
        self.assertEqual(kita["priesrinkiminis-numeris-sarase-2"]["reiksme"], "1")
        registration = kita["kandidatas-registruotas-savarankisku-politines-kampanijos-dalyviu-sprendimas"]
        self.assertEqual(registration["pavadinimas"], "Kandidatas registruotas savarankišku politinės kampanijos dalyviu. Sprendimas -")
        self.assertEqual(registration["reiksme"], "Nr.194, 2004.09.16")
        self.assertEqual(registration["nuorodos"], [CANDIDATES + "pazym_l_318.pdf"])
        # A list-only card without a campaign line has the three keys only.
        self.assertEqual(list(self.ziobakiene["normalized"]["profilis"]["kita"].keys()), ["apygarda", "iskele", "priesrinkiminis-numeris-sarase"])

    def test_seimo_question_mapping(self) -> None:
        anketa = self.mazuronis["normalized"]["anketa"]
        self.assertEqual(anketa["gimimo-data"], "1953-11-18")
        self.assertEqual(
            anketa["pareiskimai"],
            {
                "ar-nebaigta-teismo-paskirta-bausme": "Neturi",
                "ar-atliekate-karo-tarnyba": "Nėra",
                "ar-turite-kitos-valstybes-pilietybe": "Neturi",
                "ar-susijes-priesaika-uzsienio-valstybei": "Nėra",
                "ar-bendradarbiavote-su-uzsienio-tarnybomis": "Nėra",
                "ar-buvote-pripazintas-kaltu": "Nėra",
                "ar-buvote-pripazintas-kaltu-del-sunkaus-nusikaltimo": "Nebuvo",
                "teisiniai-argumentai": None,
            },
        )
        self.assertEqual(anketa["adresas"], "Šiauliai")
        self.assertEqual(anketa["anksciau-isrinktas"]["irasai"], [{"institucijos-pavadinimas-pareigos": "Šiaulių miesto taryba", "laikotarpis": "1991 - 2002"}])
        self.assertEqual(anketa["vaiku-vardai-pavardes"], "Rokas Mazuronis, Andrius Mazuronis")
        ramonas, _ = _parse("jonas-ramonas")
        pareiskimai = ramonas["normalized"]["anketa"]["pareiskimai"]
        self.assertEqual(pareiskimai["ar-buvote-pripazintas-kaltu"], "Yra")
        self.assertTrue(pareiskimai["teisiniai-argumentai"].startswith("1994 m. balandžio 7 d. nuteistas"))
        self.assertEqual(ramonas["normalized"]["anketa"]["mokslo-laipsnis"], "Mokslinis agronomas")
        dumcius, _ = _parse("arimantas-dumcius")
        self.assertEqual((dumcius["normalized"]["anketa"]["mokslo-laipsnis"], dumcius["normalized"]["anketa"]["pedagoginis-vardas"]), ("Habilituotas mokslų daktaras", "Profesorius"))

    def test_absent_degree_labels_are_two_empty_rows(self) -> None:
        # The Seimas pages drop the empty <b></b> of an unanswered degree and
        # title, so the two labels follow each other with nothing between.
        rows = self.mazuronis["rawData"]["anketa"]["rows"]
        prompts = [row["prompt"] for row in rows]
        index = prompts.index("12. Išsilavinimas:")
        self.assertEqual(prompts[index + 1 : index + 3], ["Moksliniai laipsniai:", "Moksliniai vardai:"])
        self.assertEqual([rows[index + 1]["answer"], rows[index + 2]["answer"]], ["", ""])
        self.assertIsNone(self.mazuronis["normalized"]["anketa"]["mokslo-laipsnis"])

    def test_mapping_reads_the_seimo_eight_block(self) -> None:
        rows = [
            {"questionNumber": "3", "prompt": "3. Gimimo data:", "answer": "1960.01.02"},
            {"questionNumber": "8.3", "prompt": "8.3 Ar turi kitos valstybės pilietybę:", "answer": "Turi"},
            {"questionNumber": "8.4", "prompt": "8.4 Ar yra susijęs priesaika ar pasižadėjimu užsienio valstybei:", "answer": "Yra"},
            {"questionNumber": "9.3", "prompt": "9.3 …", "answer": "Buvo"},
            {"questionNumber": None, "prompt": "", "answer": "Paaiškinimas"},
            {"questionNumber": None, "prompt": "Moksliniai laipsniai:", "answer": ""},
            {"questionNumber": None, "prompt": "Moksliniai vardai:", "answer": "Docentas"},
        ]
        normalized = normalize_seimo_2004_anketa_rows(rows)
        self.assertEqual(normalized["gimimo-data"], "1960-01-02")
        self.assertEqual(normalized["pareiskimai"]["ar-turite-kitos-valstybes-pilietybe"], "Turi")
        self.assertEqual(normalized["pareiskimai"]["ar-susijes-priesaika-uzsienio-valstybei"], "Yra")
        self.assertNotIn("kitos-valstybes-pilietybe-valstybe", normalized["pareiskimai"])
        self.assertEqual(normalized["pareiskimai"]["teisiniai-argumentai"], "Paaiškinimas")
        self.assertIsNone(normalized["mokslo-laipsnis"])
        self.assertEqual(normalized["pedagoginis-vardas"], "Docentas")

    def test_finish_candidacy_on_a_synthetic_card(self) -> None:
        html = """
        <td class="bigcell"><h4>Kandidato anketa</h4><h4>Ona TESTIENĖ</h4>
        <table><tbody><tr><td class="lt"><table><tbody><tr>
        <td><img src="/statiniai/puslapiai/rinkimai/2004/seimas/nuotraukos/1.jpg" /></td>
        <td class="lt"> Apygarda: <b><a href="/statiniai/puslapiai/rinkimai/2004/seimas/kandidatai/apg_kand_l_1603.htm">Naujamiesčio</a> (Nr.1)</b><br />
        Iškėlė: <b><a href="/statiniai/puslapiai/rinkimai/2004/seimas/kandidatai/kand_part_l_1836.htm">Partija</a></b><br /><br />
        Apygarda: <b><a href="/statiniai/puslapiai/rinkimai/2004/seimas/kandidatai/apg_kand_l_1603.htm">Naujamiesčio</a> (Nr.1)</b><br />
        Iškėlė: <b>Išsikėlė pati</b><br /><br />
        <a href="/statiniai/puslapiai/rinkimai/2004/seimas/kandidatai/kand_biog_l_1.htm">Biografija</a>
        Kandidatas registruotas savarankišku politinės kampanijos dalyviu. Sprendimas -
        <a href="/statiniai/puslapiai/rinkimai/2004/seimas/kandidatai/pazym_l_9.pdf">Nr.1, 2004.09.01</a>.</td>
        </tr></tbody></table></td></tr>
        <tr class="r1"><td class="lt"> 3. Gimimo data: <b>1970.01.01</b></td></tr>
        </tbody></table></td>
        """
        parsed = parse_anketa_html(html, rows_normalizer=normalize_seimo_2004_anketa_rows)
        self.assertEqual(parsed["profile"]["candidateDisplayName"], "Ona TESTIENĖ")
        self.assertTrue(parsed["profile"]["photoSrc"].endswith("nuotraukos/1.jpg"))
        self.assertEqual([(f["key"], f["displayValue"]) for f in parsed["profile"]["fields"]], [
            ("Apygarda", "Naujamiesčio (Nr.1)"), ("Iškėlė", "Partija"), ("Apygarda", "Naujamiesčio (Nr.1)"), ("Iškėlė", "Išsikėlė pati"),
            ("Kandidatas registruotas savarankišku politinės kampanijos dalyviu. Sprendimas -", "Nr.1, 2004.09.01"),
        ])
        self.assertEqual(parsed["anketa"]["normalized"]["gimimo-data"], "1970-01-01")
        payload = {"kandidatavimas": {"vienmandate": {"iskele": "Išsikėlė pati"}}}
        finish_candidacy(payload, parsed)
        self.assertEqual(payload["kandidatavimas"]["vienmandate"]["kitiIskelejai"], ["Partija"])
        self.assertEqual(payload["kandidatavimas"]["savarankiskasKampanijosDalyvis"]["sprendimas"], "Nr.1, 2004.09.01")
        self.assertTrue(payload["kandidatavimas"]["savarankiskasKampanijosDalyvis"]["nuoroda"].endswith("pazym_l_9.pdf"))

    def test_missing_declarations_page(self) -> None:
        # Žiobakienė's card links no declarations page and the URL is a 404:
        # the fetch recorded the gap, the record has no section, no anomaly.
        index = json.loads((SAMPLES_ROOT / "genovaite-ziobakiene" / "index.json").read_text(encoding="utf-8"))
        self.assertEqual(index["missingExpectedTabs"], ["turto-ir-pajamu-deklaracijos"])
        self.assertEqual([event["eventType"] for event in index["anomalies"]], ["MissingExpectedTab"])
        self.assertNotIn("turto-ir-pajamu-deklaracijos", self.ziobakiene["normalized"])
        self.assertEqual(list(self.ziobakiene["normalized"].keys()), ["profilis", "anketa", "biografija"])
        self.assertEqual(self.ziobakiene_stats["anomalies"], [])
        # Matkevičius's page prints the income extract only.
        matkevicius, _ = _parse("visvaldas-matkevicius")
        turto = matkevicius["normalized"]["turto-ir-pajamu-deklaracijos"]
        self.assertIsNone(turto["israsai"]["turto-deklaracija"])
        self.assertEqual(turto["gautos-pajamos"], 73384)
        self.assertIsNone(turto["privalomas-registruoti-turtas"])

    def test_declarations_and_biography(self) -> None:
        turto = self.balcytis["normalized"]["turto-ir-pajamu-deklaracijos"]
        self.assertEqual(turto["israsai"]["turto-deklaracija"]["pavadinimas"], "METINĖ GYVENTOJO TURTO DEKLARACIJA")
        self.assertEqual((turto["privalomas-registruoti-turtas"], turto["gautos-pajamos"], turto["sumoketas-pajamu-mokestis"], turto["valiuta"]), (732773, 108571, 17520, "Lt"))
        self.assertTrue(self.balcytis["normalized"]["biografija"]["tekstas"].startswith("ZIGMANTAS BALČYTIS LIETUVOS SOCIALDEMOKRATŲ PARTIJOS KANDIDATAS"))


if __name__ == "__main__":
    unittest.main()
