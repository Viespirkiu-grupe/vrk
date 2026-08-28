import json
import tempfile
import unittest
from pathlib import Path

from scraper.elections.prezidento_2002.anketa_parser import (
    DEFAULT_RESULTS_PATH,
    parse_anketa_sample,
    parse_biografija_html,
    parse_listing_card,
)
from scraper.elections.prezidento_2002.candidate_samples import (
    BASE_EXPECTED_TABS,
    UNPUBLISHED_TABS,
)
from scraper.elections.prezidento_2002.results import (
    PROTOCOL_PAGE,
    ROUND_PAGES,
    build_results,
    parse_protocol_winner,
    parse_round_page,
    resolve_verdict_name,
)
from scraper.elections.prezidento_2002.sitemap import (
    ELECTION_ID,
    SITE_ROOT,
    build_sitemap_from_sample,
    extract_registration_ids,
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
            results_path=SITEMAPS / f"{ELECTION_ID}.results.json",
        )
        return json.loads(output_path.read_text(encoding="utf-8")), stats


def _saved_results_page(page_name: str) -> str:
    stem = page_name.replace("/", "__")
    candidates = list(RESULTS_DIR.glob(f"*{stem.rsplit('__', 1)[-1]}*"))
    assert candidates, f"no saved copy of {page_name}"
    return candidates[0].read_text(encoding="utf-8")


class Prezidento2002SitemapTests(unittest.TestCase):
    def test_listing_yields_the_seventeen_cards(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            _, stats = build_sitemap_from_sample(
                sample_path=SAMPLES_ROOT,
                output_path=Path(tmp) / "sitemap.json",
            )
            payload = json.loads((Path(tmp) / "sitemap.json").read_text(encoding="utf-8"))

        self.assertEqual(stats["rows"], 17)
        self.assertEqual(stats["extracted"], 17)
        # Four cards link a health certificate; nine link a campaign site.
        self.assertEqual(stats["withSveikata"], 4)
        self.assertEqual(stats["withWebsite"], 9)

        entries = {entry["candidateId"]: entry for entry in payload["entries"]}
        self.assertEqual(len(entries), 17)

        # Both id spaces: the card's own anchor and the registration
        # record id from the trustee index, which the results tree keys on.
        paksas = entries["rolandas-paksas"]
        self.assertEqual(paksas["vrkCandidateId"], "168284")
        self.assertEqual(paksas["vrkRegistrationId"], "948551")
        self.assertEqual(paksas["registeredDate"], "2002-11-12")
        self.assertEqual(paksas["decision"], "VRK sprendimu Nr. 130")
        self.assertTrue(paksas["biografijaUrl"].endswith("Pakso_biografija.htm"))
        self.assertTrue(paksas["programaUrl"].endswith("Pakso_programa.doc"))
        self.assertEqual(len(paksas["anketosSkenaiUrls"]), 2)
        self.assertEqual(paksas["deklaracijaLabel"], "Šeimos turto pajamų deklaracija")
        self.assertEqual(len(paksas["sveikatosSkenaiUrls"]), 1)

        adamkus = entries["valdas-adamkus"]
        self.assertEqual(adamkus["vrkCandidateId"], "168296")
        self.assertEqual(adamkus["vrkRegistrationId"], "948562")
        self.assertEqual(adamkus["registeredDate"], "2002-10-29")
        self.assertEqual(adamkus["decision"], "VRK sprendimu Nr. 91")

        # The declaration link label states which form was filed.
        gentvilas = entries["eugenijus-gentvilas"]
        self.assertEqual(gentvilas["deklaracijaLabel"], "Gyventojo turto pajamų deklaracija")

        # Šerėnas's health certificate is two pages; V. A. Matulevičius's
        # card links two campaign sites.
        self.assertEqual(len(entries["vytautas-serenas"]["sveikatosSkenaiUrls"]), 2)
        self.assertEqual(len(entries["vytautas-antanas-matulevicius"]["websiteUrls"]), 2)

        for entry in entries.values():
            self.assertTrue(entry["photoUrl"].endswith("_nuotrauka.jpg"))
            self.assertTrue(entry["pareiskimasUrl"].endswith("_pareiskimas.jpg"))
            self.assertTrue(entry["deklaracijaUrl"].endswith("_deklaracija.jpg"))

    def test_trustee_index_maps_names_to_registration_ids(self) -> None:
        html = (SAMPLES_ROOT / "patiketiniai-index.html").read_text(encoding="utf-8")
        ids = extract_registration_ids(html)
        self.assertEqual(len(ids), 17)
        self.assertEqual(ids["Valdas Adamkus"], "948562")
        self.assertEqual(ids["Rolandas Paksas"], "948551")


class Prezidento2002ExpectedTabsTests(unittest.TestCase):
    def test_scans_are_expected_health_certificates_are_not(self) -> None:
        self.assertEqual(
            BASE_EXPECTED_TABS,
            {"anketa", "biografija", "programa", "pareiskimas", "duomenu-anketa", "deklaracija"},
        )
        # The trustee pages and the health-certificate scans are linked
        # but 404 on VRK's mirror — recorded, not fetched.
        self.assertEqual(UNPUBLISHED_TABS, {"patiketiniai", "sveikata"})


class Prezidento2002CardTests(unittest.TestCase):
    def test_card_is_found_by_candidate_anchor(self) -> None:
        listing_html = (SAMPLES_ROOT / "rolandas-paksas" / "anketa.html").read_text(encoding="utf-8")
        profile = parse_listing_card(listing_html, "168284")
        self.assertEqual(profile["candidateDisplayName"], "Rolandas Paksas")
        self.assertTrue(profile["photoSrc"].endswith("Paksas_nuotrauka.jpg"))
        fields = {field["key"]: field for field in profile["fields"]}
        self.assertIn("Registracija", fields)
        self.assertIn("registruotas kandidatu", fields["Registracija"]["displayValue"])
        self.assertIn("lrs.lt", fields["Registracija"]["urls"][0])
        self.assertEqual(len(fields["Duomenų anketa"]["urls"]), 2)
        self.assertIn("Šeimos turto pajamų deklaracija", fields)
        self.assertEqual(len(fields["Sveikatos pažyma"]["urls"]), 1)
        self.assertIsNone(parse_listing_card(listing_html, "999999"))


class Prezidento2002BiografijaTests(unittest.TestCase):
    def test_prose_follows_the_headings(self) -> None:
        html = (SAMPLES_ROOT / "rolandas-paksas" / "biografija.html").read_text(encoding="utf-8")
        parsed = parse_biografija_html(html)
        self.assertEqual(parsed["headingName"], "ROLANDAS PAKSAS")
        self.assertTrue(parsed["text"].startswith("Gimė 1956 m. birželio 10 d. Telšiuose."))
        self.assertIn("Liberalų demokratų partijos pirmininkas", parsed["text"])


class Prezidento2002RecordTests(unittest.TestCase):
    def test_winner_record(self) -> None:
        require(DEFAULT_RESULTS_PATH)
        record, stats = _parse("rolandas-paksas")
        candidacy = record["kandidatavimas"]
        self.assertTrue(candidacy["isrinktas"])
        self.assertEqual(candidacy["isrinktasKaip"], "prezidentas")
        self.assertEqual(candidacy["rezultatuTuras"], 2)
        rounds = {row["turas"]: row for row in candidacy["turai"]}
        self.assertEqual(set(rounds), {1, 2})
        self.assertEqual(rounds[1]["balsai"], 284559)
        self.assertEqual(rounds[2]["balsai"], 777769)
        self.assertEqual(rounds[2]["procentai-nuo-galiojanciu"], 54.71)

        anketa = record["normalized"]["anketa"]
        self.assertEqual(anketa["gimimo-data"], "1956-06-10")
        self.assertEqual(anketa["gimimo-data-saltinis"], "biografijos-tekstas")
        self.assertEqual(anketa["gimimo-vieta"], "Telšiai")

        self.assertIn("RINKIMŲ PROGRAMA", record["normalized"]["programa"]["tekstas"])
        # The scans are URLs, never parsed data: no declaration section
        # exists, and the inventory names what VRK published as images.
        self.assertNotIn("turto-ir-pajamu-deklaracijos", record["normalized"])
        skenai = record["rawData"]["skenai"]
        self.assertTrue(skenai["deklaracija"]["url"].endswith("Paksas_deklaracija.jpg"))
        self.assertEqual(skenai["deklaracija"]["forma"], "Šeimos turto pajamų deklaracija")
        self.assertEqual(len(skenai["duomenu-anketa"]), 2)
        self.assertEqual(stats["anomalies"], [])

    def test_runoff_loser_and_first_round_loser(self) -> None:
        require(DEFAULT_RESULTS_PATH)
        record, _ = _parse("valdas-adamkus")
        candidacy = record["kandidatavimas"]
        self.assertFalse(candidacy["isrinktas"])
        rounds = {row["turas"]: row for row in candidacy["turai"]}
        self.assertEqual(set(rounds), {1, 2})
        self.assertEqual(rounds[1]["balsai"], 514154)
        self.assertEqual(rounds[2]["balsai"], 643870)
        self.assertEqual(record["normalized"]["anketa"]["gimimo-data"], "1926-11-03")

        record, _ = _parse("vytautas-serenas")
        candidacy = record["kandidatavimas"]
        self.assertFalse(candidacy["isrinktas"])
        self.assertEqual([row["turas"] for row in candidacy["turai"]], [1])
        self.assertEqual(candidacy["turai"][0]["balsai"], 112215)
        # His programme document is one line: the campaign aired on LNK.
        self.assertIn("LNK", record["normalized"]["programa"]["tekstas"])

    def test_year_only_birth_date_stays_a_year(self) -> None:
        # Bernatonis's biography opens "Gimė 1940 metais" — the spelled-out
        # year the widened shared pattern reads; a year alone is never
        # promoted to a birth date.
        record, _ = _parse("vytautas-bernatonis")
        anketa = record["normalized"]["anketa"]
        self.assertNotIn("gimimo-data", anketa)
        self.assertEqual(anketa["gimimo-metai"], 1940)

    def test_all_other_birth_dates_recovered(self) -> None:
        expected = {
            "valdas-adamkus": "1926-11-03",
            "eugenijus-gentvilas": "1960-03-14",
            "algimantas-matulevicius": "1948-01-19",
            "vytenis-povilas-andriukaitis": "1951-08-09",
            "arturas-paulauskas": "1953-08-23",
            "kazys-bobelis": "1923-03-04",
            "kestutis-glaveckas": "1949-04-30",
            "vytautas-serenas": "1959-10-10",
            "rolandas-paksas": "1956-06-10",
            "vytautas-sustauskas": "1945-03-19",
            "rimantas-jonas-dagys": "1957-07-16",
            "vytautas-antanas-matulevicius": "1952-07-31",
            "kazimira-danute-prunskiene": "1943-02-26",
            "juozas-edvardas-petraitis": "1957-10-16",
            "algirdas-pilvelis": "1944-03-04",
            "julius-veselka": "1943-02-08",
        }
        for candidate_id, birth_date in expected.items():
            with self.subTest(candidate_id):
                record, _ = _parse(candidate_id)
                self.assertEqual(record["normalized"]["anketa"]["gimimo-data"], birth_date)


class Prezidento2002ResultsTests(unittest.TestCase):
    def test_first_round_page(self) -> None:
        url = SITE_ROOT + ROUND_PAGES[1]
        page = parse_round_page(_saved_results_page(ROUND_PAGES[1]), url)
        self.assertEqual(page["summary"]["apylinkes"], 2015)
        self.assertEqual(page["summary"]["rinkeju-skaicius"], 2719608)
        self.assertEqual(page["summary"]["negaliojantys-biuleteniai"], 19419)
        self.assertEqual(page["summary"]["galiojantys-biuleteniai"], 1447117)
        self.assertEqual(len(page["candidates"]), 17)
        self.assertEqual(sum(row["balsai"] for row in page["candidates"]), 1447117)
        top = page["candidates"][0]
        self.assertEqual(top["name"], "Valdas Adamkus")
        self.assertEqual(top["vrkRegistrationId"], "948562")
        self.assertEqual(top["balsai"], 514154)

    def test_runoff_page(self) -> None:
        url = SITE_ROOT + ROUND_PAGES[2]
        page = parse_round_page(_saved_results_page(ROUND_PAGES[2]), url)
        self.assertEqual(len(page["candidates"]), 2)
        self.assertEqual(page["summary"]["galiojantys-biuleteniai"], 1421639)
        winner = max(page["candidates"], key=lambda row: row["balsai"])
        self.assertEqual(winner["name"], "Rolandas Paksas")
        self.assertEqual(winner["balsai"], 777769)

    def test_protocol_verdict_resolves_the_accusative_name(self) -> None:
        verdict = parse_protocol_winner(_saved_results_page(PROTOCOL_PAGE))
        self.assertEqual(verdict, "Rolandą Paksą")
        candidates = [
            {"name": "Rolandas Paksas", "vrkRegistrationId": "948551"},
            {"name": "Valdas Adamkus", "vrkRegistrationId": "948562"},
        ]
        hit = resolve_verdict_name(verdict, candidates)
        self.assertEqual(hit["vrkRegistrationId"], "948551")
        self.assertIsNone(resolve_verdict_name("Kažkas Kitas", candidates))

    def test_build_results_reconciles(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output_path, stats = build_results(
                sitemap_path=SITEMAPS / f"{ELECTION_ID}.json",
                results_dir=RESULTS_DIR,
                output_path=Path(tmp) / "results.json",
            )
            payload = json.loads(output_path.read_text(encoding="utf-8"))

        self.assertEqual(stats["candidatesRound1"], 17)
        self.assertEqual(stats["candidatesRound2"], 2)
        self.assertEqual(stats["notInSitemap"], 0)
        self.assertTrue(stats["runoffIsRound1TopTwo"])
        self.assertEqual(stats["voteSumMismatches"], 0)
        self.assertTrue(stats["verdictMatchesVoteLeader"])
        self.assertEqual(stats["winnersResolved"], 1)
        self.assertEqual(list(payload["elected"]), ["168284"])
        self.assertEqual(payload["elected"]["168284"]["seat"], "prezidentas")
        self.assertEqual(payload["elected"]["168284"]["round"], 2)


if __name__ == "__main__":
    unittest.main()
