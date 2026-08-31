import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from bs4 import BeautifulSoup

from scraper.elections.seimo_dzukijos_2007.anketa_parser import (
    DEFAULT_RESULTS_PATH,
    parse_anketa_sample,
)
from scraper.elections.seimo_dzukijos_2007.candidate_samples import EXPECTED_TABS
from scraper.elections.seimo_dzukijos_2007.results import RESULTS_TREE
from scraper.elections.seimo_dzukijos_2007.sitemap import (
    ELECTION_ID,
    LISTING_URL,
    build_sitemap_from_sample,
    given_first_name,
)
from scraper.elections.seimo_zirmunu_2015.anketa_parser import parse_anketa_html
from scraper.elections.seimo_zirmunu_2015.sitemap import resolve_candidate_url
from scraper.shared.election_results import (
    page_path,
    parse_seimo_district_page,
    seimo_district_pages,
    tree_root,
)

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


class SeimoDzukijos2007SitemapTests(unittest.TestCase):
    def test_listing_is_the_district_page_and_names_are_given_first(self) -> None:
        self.assertTrue(LISTING_URL.endswith("rinkimai/396/Apygardos/Apygarda6838/KandidataiApygardos6838.html"))
        with tempfile.TemporaryDirectory() as tmp:
            _, stats = build_sitemap_from_sample(
                sample_path=SAMPLES_ROOT / "list.html",
                output_path=Path(tmp) / "sitemap.json",
            )
            payload = json.loads((Path(tmp) / "sitemap.json").read_text(encoding="utf-8"))
        # Eleven rows: the <th> header and ten candidates.
        self.assertEqual(stats, {"rows": 11, "extracted": 10, "skipped": 1, "duplicate_candidate_ids": 0})
        by_id = {entry["candidateId"]: entry for entry in payload["entries"]}
        self.assertEqual(len(by_id), 10)
        # The listing prints "KĘSTUTIS ČILINSKAS"; the corpus form is given
        # names in title case, surname in capitals.
        self.assertEqual(
            by_id["kestutis-cilinskas"],
            {
                "candidateName": "Kęstutis ČILINSKAS",
                "candidateId": "kestutis-cilinskas",
                "url": "https://www.vrk.lt/statiniai/puslapiai/rinkimai/396/Kandidatai/Kandidatas19310/Kandidato19310Anketa.html",
                "vrkCandidateId": "19310",
                "roles": ["vienmandate"],
                "vienmandateCandidacy": {
                    "apygarda": "Dzūkijos",
                    "apygardosNumeris": 69,
                    "apygardosId": "6838",
                    "iskele": "Tėvynės sąjunga (konservatoriai, politiniai kaliniai ir tremtiniai, krikščioniškieji demokratai)",
                },
            },
        )
        self.assertEqual(by_id["vytautas-jurgis-kadzys"]["candidateName"], "Vytautas Jurgis KADŽYS")
        self.assertEqual(given_first_name("ONA BALEVIČIŪTĖ"), "Ona BALEVIČIŪTĖ")
        self.assertEqual(given_first_name("USPASKICH"), "USPASKICH")

    def test_campaign_link_climbs_one_level_too_many(self) -> None:
        # The 2007 template's five "../" land in /statiniai/rinkimai/…, which
        # does not exist; the resolver puts the link where the page is.
        href = "/statiniai/puslapiai/rinkimai/396/Kandidatai/Kandidatas19310/../../../../../rinkimai/396/PolitiniuKampanijuFinansavimas/Dalyvis3145/Dalyvio3145Izdininkas.html"
        self.assertEqual(
            resolve_candidate_url(href),
            "https://www.vrk.lt/statiniai/puslapiai/rinkimai/396/PolitiniuKampanijuFinansavimas/Dalyvis3145/Dalyvio3145Izdininkas.html",
        )
        self.assertEqual(
            resolve_candidate_url("/statiniai/puslapiai/rinkimai/448_lt/Apygardos/Apygarda7822/../../Kandidatai/Kandidatas1/Kandidato1Anketa.html"),
            "https://www.vrk.lt/statiniai/puslapiai/rinkimai/448_lt/Kandidatai/Kandidatas1/Kandidato1Anketa.html",
        )


class SeimoDzukijos2007ResultsTests(unittest.TestCase):
    def test_tree_without_output_lt(self) -> None:
        self.assertEqual(RESULTS_TREE, "2007_seimo_rinkimai/")
        self.assertEqual(tree_root("2007_seimo_rinkimai/"), "https://www.vrk.lt/statiniai/puslapiai/2007_seimo_rinkimai")
        self.assertEqual(tree_root("2013_seimo_rinkimai"), "https://www.vrk.lt/statiniai/puslapiai/2013_seimo_rinkimai/output_lt")
        # Cached file names keep the folder so the two rounds' pages, which
        # share one folder here, do not collide with the index.
        self.assertEqual(
            page_path(Path("/r"), "https://www.vrk.lt/statiniai/puslapiai/2007_seimo_rinkimai/rezultatai_vienmand_apygardose/rezultatai_vienmanate_apygarda6840aktyvumasdesc2turas.html").name,
            "rezultatai_vienmand_apygardose__rezultatai_vienmanate_apygarda6840aktyvumasdesc2turas.html",
        )

    def test_round_two_index_falls_back_to_the_round_one_folder(self) -> None:
        index = '<a href="rezultatai_vienmanate_apygarda6840aktyvumasdesc2turas.html">69. Dzūkijos</a>'
        calls: list[str] = []

        def fake_fetch(url: str) -> str:
            calls.append(url)
            if "/rezultatai_vienmand_apygardose2/" in url:
                raise RuntimeError("404")
            return index

        with tempfile.TemporaryDirectory() as tmp, mock.patch("scraper.shared.election_results.fetch_text", side_effect=fake_fetch):
            pages = seimo_district_pages(Path(tmp), "2007_seimo_rinkimai/", 2)
        self.assertEqual([page["resultDistrictId"] for page in pages], ["6840"])
        self.assertTrue(calls[0].endswith("/rezultatai_vienmand_apygardose2/rezultatai_vienmand_apygardose2turas.html"))
        self.assertTrue(calls[1].endswith("/rezultatai_vienmand_apygardose/rezultatai_vienmand_apygardose2turas.html"))

    def test_rows_linked_to_the_anketa_pages(self) -> None:
        html = """<table><tr><th>Kandidatas</th><th>a</th><th>p</th><th>iš viso</th><th>%</th><th>%</th></tr>
        <tr><td><a href="../../rinkimai/396/Kandidatai/Kandidatas19310/Kandidato19310Anketa.html">Kęstutis ČILINSKAS</a></td><td>5377</td><td>1219</td><td>6596</td><td>56,42%</td><td>55,33%</td></tr>
        <tr><td><a href="../../rinkimai/396/Kandidatai/Kandidatas19297/Kandidato19297Anketa.html">Viktor USPASKICH</a></td><td>3991</td><td>1103</td><td>5094</td><td>43,58%</td><td>42,73%</td></tr></table>"""
        parsed = parse_seimo_district_page(html)
        self.assertIsNone(parsed["verdictName"])
        self.assertEqual([(r["name"], r["votes"]) for r in parsed["rows"]], [("Kęstutis ČILINSKAS", 6596), ("Viktor USPASKICH", 5094)])

    def test_built_results(self) -> None:
        payload = json.loads((SITEMAPS / f"{ELECTION_ID}.results.json").read_text(encoding="utf-8"))
        self.assertEqual(
            payload["stats"],
            {"constituencies": 1, "winnersResolved": 1, "unresolved": 0, "decidedInRoundTwo": 1, "byRunoffPlurality": 1, "candidatesWithVotes": 10, "voteRowsUnresolved": 0},
        )
        self.assertEqual(list(payload["elected"]), ["19310"])
        self.assertEqual(payload["details"]["constituencies"][0]["field"][:2], ["Kęstutis ČILINSKAS", "Viktor USPASKICH"])


LEGACY_CARD = """
<html><body>
<div class="picklist tabinc"><h3></h3><table class="partydata"><tbody><tr>
<td><strong>Dzūkijos rinkimų<br /> apygarda (Nr. 69)</strong></td><td><strong>Partija X</strong></td></tr></tbody></table></div>
<div class="candidateInfo"><table class="partydata"><tbody><tr>
<td> <img src="/statiniai/puslapiai/rinkimai/396/Kandidatai/Kandidatas1/Kandidato1Foto.jpg" /> </td>
<td valign="top"> VARDAS &nbsp;&nbsp; PAVARDĖ<br /> Gimimo data: 1950-02-03 <br /><br /> Kandidatas nėra savarankiškas politinės kampanijos dalyvis <br /><br /> Balsavimo rezultatai: <a href="/statiniai/puslapiai/2007_seimo_rinkimai/rezultatai_vienmand_apygardose/r1.html">I turas</a>, <a href="/statiniai/puslapiai/2007_seimo_rinkimai/rezultatai_vienmand_apygardose/r2.html">II turas</a>. </td>
</tr></tbody></table></div>
<ul id="tabnav"><li><a href="x">Anketa</a></li></ul>
<div class="candidateInfo"><table class="partydata"><tbody><tr><td> 6. Nuolatinės gyvenamosios vietos adresas <b>Alytus</b><br /> 10. Gimimo vieta <b>Alytus</b><br /> </td></tr></tbody></table></div>
</body></html>
"""


class LegacyProfileCardTests(unittest.TestCase):
    def test_plain_text_card_and_header_table(self) -> None:
        parsed = parse_anketa_html(LEGACY_CARD)
        profile = parsed["profile"]
        self.assertEqual(profile["candidateDisplayName"], "VARDAS PAVARDĖ")
        self.assertTrue(profile["photoSrc"].endswith("Kandidato1Foto.jpg"))
        self.assertEqual(
            [(field["key"], field["displayValue"], len(field["urls"])) for field in profile["fields"]],
            [
                ("Apygarda", "Dzūkijos rinkimų apygarda (Nr. 69)", 0),
                ("Iškėlė", "Partija X", 0),
                ("Gimimo data", "1950-02-03", 0),
                ("I turas", "", 1),
                ("II turas", "", 1),
            ],
        )
        # No Q5 on the form: the card's birth date is the anketa's.
        self.assertEqual(parsed["anketa"]["normalized"]["gimimo-data"], "1950-02-03")
        self.assertEqual(parsed["anketa"]["normalized"]["adresas"], "Alytus")


class SeimoDzukijos2007AnketaParserTests(unittest.TestCase):
    def setUp(self) -> None:
        self.cilinskas, self.cilinskas_stats = _parse("kestutis-cilinskas")
        self.baleviciute, _ = _parse("ona-baleviciute")
        self.uspaskich, _ = _parse("viktor-uspaskich")

    def test_expected_tabs_lack_kita(self) -> None:
        self.assertEqual(EXPECTED_TABS, {"anketa", "biografija", "turto-ir-pajamu-deklaracijos", "interesu-deklaracija"})
        index = json.loads((SAMPLES_ROOT / "kestutis-cilinskas" / "index.json").read_text(encoding="utf-8"))
        self.assertEqual(index["tabCount"], 4)
        self.assertEqual(index["anomalies"], [])
        self.assertEqual(index["campaignSamples"][0]["tabCount"], 5)

    def test_top_level_fields_and_candidacy(self) -> None:
        require(DEFAULT_RESULTS_PATH)
        self.assertEqual(self.cilinskas["electionId"], "2007-spalio-7-seimo-dzukija")
        self.assertEqual(self.cilinskas["candidateName"], "Kęstutis ČILINSKAS")
        self.assertEqual(self.cilinskas_stats["anomalies"], [])
        self.assertEqual(
            self.cilinskas["kandidatavimas"],
            {
                "vrkCandidateId": "19310",
                "roles": ["vienmandate"],
                "vienmandate": {
                    "apygarda": "Dzūkijos",
                    "apygardosNumeris": 69,
                    "apygardosId": "6838",
                    "iskele": "Tėvynės sąjunga (konservatoriai, politiniai kaliniai ir tremtiniai, krikščioniškieji demokratai)",
                },
                "daugiamandate": None,
                "isrinktas": True,
                "isrinktasKaip": "vienmandate",
                "rezultatuSaltinis": "https://www.vrk.lt/statiniai/puslapiai/2007_seimo_rinkimai/rezultatai_vienmand_apygardose/rezultatai_vienmanate_apygarda6840aktyvumasdesc2turas.html",
                "rezultatuTuras": 2,
                "vienmandatesBalsai": {
                    "balsadezese": 2636,
                    "pastu": 503,
                    "isViso": 3139,
                    "procentai": 30.76,
                    "vieta": 1,
                    "saltinis": "https://www.vrk.lt/statiniai/puslapiai/2007_seimo_rinkimai/rezultatai_vienmand_apygardose/rezultatai_vienmanate_apygarda6838aktyvumasdesc1turas.html",
                },
                "vienmandatesBalsai2": {
                    "balsadezese": 5377,
                    "pastu": 1219,
                    "isViso": 6596,
                    "procentai": 56.42,
                    "vieta": 1,
                    "saltinis": "https://www.vrk.lt/statiniai/puslapiai/2007_seimo_rinkimai/rezultatai_vienmand_apygardose/rezultatai_vienmanate_apygarda6840aktyvumasdesc2turas.html",
                },
            },
        )
        self.assertIs(self.uspaskich["kandidatavimas"]["isrinktas"], False)
        self.assertEqual(
            list(self.cilinskas["normalized"].keys()),
            ["profilis", "anketa", "biografija", "turto-ir-pajamu-deklaracijos", "privaciu-interesu-deklaracija", "politines-kampanijos-dalyvio-duomenys"],
        )
        # A represented candidate: the card says so in words and links no
        # campaign, so there is no campaign section.
        self.assertNotIn("politines-kampanijos-dalyvio-duomenys", self.baleviciute["normalized"])

    def test_profile_card(self) -> None:
        kita = self.cilinskas["normalized"]["profilis"]["kita"]
        self.assertEqual(self.cilinskas["normalized"]["profilis"]["vardas-pavarde"], "KĘSTUTIS ČILINSKAS")
        self.assertEqual(
            list(kita.keys()),
            ["apygarda", "iskele", "gimimo-data", "politines-kampanijos-dalyvio-duomenys", "i-turas", "ii-turas"],
        )
        self.assertEqual(kita["apygarda"]["reiksme"], "Dzūkijos rinkimų apygarda (Nr. 69)")
        self.assertEqual(kita["gimimo-data"]["reiksme"], "1946-01-08")
        self.assertTrue(kita["politines-kampanijos-dalyvio-duomenys"]["nuorodos"][0].startswith("https://www.vrk.lt/statiniai/puslapiai/rinkimai/396/PolitiniuKampanijuFinansavimas/"))
        self.assertEqual(
            list(self.baleviciute["normalized"]["profilis"]["kita"].keys()),
            ["apygarda", "iskele", "gimimo-data", "kandidatas-nera-savarankiskas-politines-kampanijos-dalyvis", "i-turas", "ii-turas"],
        )

    def test_anketa(self) -> None:
        anketa = self.cilinskas["normalized"]["anketa"]
        # The form asks no Q5; the birth date comes from the card.
        self.assertEqual(anketa["gimimo-data"], "1946-01-08")
        self.assertNotIn("5", {row.get("questionNumber") for row in self.cilinskas["rawData"]["anketa"]["rows"]})
        self.assertEqual(anketa["adresas"], "Vilnius")
        self.assertEqual(anketa["gimimo-vieta"], "Šiaulių m.")
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
        self.assertEqual(anketa["uzsienio-kalbos"], ["Anglų", "Rusų"])
        self.assertEqual(anketa["issilavinimas"]["irasai"][0]["specialybe"], "Teisė")
        self.assertEqual(anketa["sutuoktinio-vardas-pavarde"], "Irta Emilija Čilinskienė")
        self.assertEqual(self.uspaskich["normalized"]["anketa"]["gimimo-data"], "1959-07-24")

    def test_declarations_use_the_gpm302_form(self) -> None:
        turto = self.cilinskas["normalized"]["turto-ir-pajamu-deklaracijos"]
        self.assertEqual(turto["privalomas-registruoti-turtas"], 400000)
        self.assertEqual(turto["gautos-pajamos"], 95834)
        self.assertEqual(turto["sumoketas-pajamu-mokestis"], 13601)
        self.assertEqual(turto["valiuta"], "Lt")
        self.assertEqual(self.uspaskich["normalized"]["turto-ir-pajamu-deklaracijos"]["privalomas-registruoti-turtas"], 2427187)
        self.assertIn("ii-turtas", self.cilinskas["normalized"]["privaciu-interesu-deklaracija"])

    def test_campaign(self) -> None:
        campaign = self.cilinskas["normalized"]["politines-kampanijos-dalyvio-duomenys"][0]
        self.assertEqual(campaign["statusas"], "Savarankiškas")
        self.assertEqual(campaign["izdininkas"]["vardas-pavarde"], "EDELA RAKŠTELIENĖ")
        aukos = campaign["aukos-pagal-sekcija"]["aukotoju-sarasas"]
        self.assertEqual(len(aukos["records"]), 6)
        self.assertEqual(aukos["records"][0]["donor"], "Tėvynės Sąjunga")
        self.assertEqual(aukos["suvestine"], [{"label": "Iš viso", "amountEur": None, "amountLt": 79008.33, "note": None}])
        self.assertEqual(len(campaign["finansavimo-ataskaitos"]), 5)


if __name__ == "__main__":
    unittest.main()
