import json
import tempfile
import unittest
from pathlib import Path

from scraper.elections.seimo_birzu_zarasu_ukmerges_2013.anketa_parser import (
    build_candidacy,
    normalize_seimo_2012_anketa_rows,
    parse_anketa_sample,
)
from scraper.elections.seimo_birzu_zarasu_ukmerges_2013.sitemap import (
    ELECTION_ID,
    LISTING_URL,
    build_sitemap_from_sample,
    extract_district_links,
)


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


class SeimoBirzuZarasuUkmerges2013SitemapTests(unittest.TestCase):
    def test_index_lists_the_three_constituencies(self) -> None:
        links = extract_district_links((SAMPLES_ROOT / "list.html").read_text(encoding="utf-8"))
        self.assertEqual(
            [(link["number"], link["name"], link["districtId"]) for link in links],
            [
                (48, "Biržų - Kupiškio", "7433"),
                (52, "Zarasų - Visagino", "7434"),
                (61, "Ukmergės", "7435"),
            ],
        )
        self.assertTrue(links[0]["url"].endswith("Apygarda7433/KandidataiApygardos7433.html"))

    def test_sitemap_walks_every_constituency(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            _, stats = build_sitemap_from_sample(
                sample_path=SAMPLES_ROOT,
                output_path=Path(tmp) / "sitemap.json",
            )
            payload = json.loads((Path(tmp) / "sitemap.json").read_text(encoding="utf-8"))

        self.assertEqual(stats, {"rows": 37, "extracted": 37, "skipped": 0, "duplicate_candidate_ids": 0, "districts": 3})
        self.assertEqual(payload["electionId"], ELECTION_ID)
        self.assertEqual(payload["sourceUrl"], LISTING_URL)
        self.assertEqual(len(payload["districtUrls"]), 3)

        by_id = {entry["candidateId"]: entry for entry in payload["entries"]}
        self.assertEqual(len(by_id), 37)
        bitaitis = by_id["dalius-bitaitis"]
        self.assertEqual(bitaitis["candidateName"], "Dalius BITAITIS")
        self.assertEqual(bitaitis["vrkCandidateId"], "70545")
        self.assertEqual(bitaitis["roles"], ["vienmandate"])
        self.assertEqual(
            bitaitis["vienmandateCandidacy"],
            {
                "apygarda": "Biržų - Kupiškio",
                "apygardosNumeris": 48,
                "apygardosId": "7433",
                "iskele": "Tėvynės sąjunga - Lietuvos krikščionys demokratai",
            },
        )
        # The listing's "Iškėlė" column spells self-nomination out.
        self.assertEqual(by_id["rimvydas-podolskis"]["vienmandateCandidacy"]["iskele"], "Išsikėlė pats")
        self.assertEqual(by_id["rimvydas-podolskis"]["vienmandateCandidacy"]["apygardosNumeris"], 52)
        self.assertEqual(by_id["gintaras-songaila"]["vienmandateCandidacy"]["apygarda"], "Ukmergės")
        # Per-constituency counts: 11 + 12 + 14.
        counts = {}
        for entry in payload["entries"]:
            number = entry["vienmandateCandidacy"]["apygardosNumeris"]
            counts[number] = counts.get(number, 0) + 1
        self.assertEqual(counts, {48: 11, 52: 12, 61: 14})


class SeimoBirzuZarasuUkmerges2013AnketaParserTests(unittest.TestCase):
    def setUp(self) -> None:
        self.bitaitis, self.bitaitis_stats = _parse("dalius-bitaitis")
        self.podolskis, _ = _parse("rimvydas-podolskis")
        self.dumbrava, _ = _parse("algimantas-dumbrava")

    def test_top_level_fields_and_candidacy(self) -> None:
        self.assertEqual(self.bitaitis["electionId"], ELECTION_ID)
        self.assertEqual(self.bitaitis["candidateName"], "Dalius BITAITIS")
        self.assertEqual(self.bitaitis_stats["anomalies"], [])
        self.assertEqual(
            self.bitaitis["kandidatavimas"],
            {
                "vrkCandidateId": "70545",
                "roles": ["vienmandate"],
                "vienmandate": {
                    "apygarda": "Biržų - Kupiškio",
                    "apygardosNumeris": 48,
                    "apygardosId": "7433",
                    "iskele": "Tėvynės sąjunga - Lietuvos krikščionys demokratai",
                },
                "daugiamandate": None,
                "isrinktas": None,
            },
        )

    def test_candidacy_builder_carries_both_seat_types(self) -> None:
        built = build_candidacy(
            {
                "vrkCandidateId": "1",
                "roles": ["daugiamandate", "vienmandate"],
                "vienmandateCandidacy": {"apygarda": "A"},
                "daugiamandateCandidacy": {"sarasas": "B", "numerisSarase": 3},
            }
        )
        self.assertEqual(built["roles"], ["daugiamandate", "vienmandate"])
        self.assertEqual(built["vienmandate"], {"apygarda": "A"})
        self.assertEqual(built["daugiamandate"], {"sarasas": "B", "numerisSarase": 3})
        self.assertIsNone(built["isrinktas"])
        self.assertEqual(build_candidacy({})["vrkCandidateId"], None)

    def test_profile_card(self) -> None:
        profilis = self.bitaitis["normalized"]["profilis"]
        self.assertEqual(profilis["vardas-pavarde"], "DALIUS BITAITIS")
        self.assertIsNone(profilis["pastaba"])
        kita = profilis["kita"]
        self.assertEqual(kita["apygarda"]["reiksme"], "Biržų - Kupiškio (Nr.48)")
        self.assertEqual(kita["iskele"]["reiksme"], "Tėvynės sąjunga - Lietuvos krikščionys demokratai")
        # The card links the district's first-round results; no page marks
        # the winner, so that link is all the results context there is.
        self.assertEqual(
            kita["i-turas"]["nuorodos"],
            [
                "https://www.vrk.lt/statiniai/puslapiai/2013_seimo_rinkimai/output_lt"
                "/rezultatai_vienmand_apygardose/rezultatai_vienmanate_apygarda7433aktyvumasdesc1turas.html"
            ],
        )
        self.assertIn("atstovaujamojo-politines-kampanijos-dalyvio-duomenys", kita)
        self.assertIn(
            "savarankisko-politines-kampanijos-dalyvio-duomenys",
            self.podolskis["normalized"]["profilis"]["kita"],
        )

    def test_seimo_2012_mapping_adds_the_grave_crime_question(self) -> None:
        pareiskimai = self.bitaitis["normalized"]["anketa"]["pareiskimai"]
        self.assertEqual(
            list(pareiskimai.keys()),
            [
                "ar-nebaigta-teismo-paskirta-bausme",
                "ar-atliekate-karo-tarnyba",
                "ar-turite-kitos-valstybes-pilietybe",
                "ar-susijes-priesaika-uzsienio-valstybei",
                "ar-bendradarbiavote-su-uzsienio-tarnybomis",
                "ar-buvote-pripazintas-kaltu",
                "ar-buvote-pripazintas-kaltu-del-sunkaus-nusikaltimo",
            ],
        )
        self.assertEqual(pareiskimai["ar-nebaigta-teismo-paskirta-bausme"], "Neturiu")
        self.assertEqual(pareiskimai["ar-buvote-pripazintas-kaltu"], "Ne")
        # Every 2013 form carries VRK's "Nenurodė" default for Q9.3, so the
        # normalized value is None while the raw row keeps the literal.
        self.assertIsNone(pareiskimai["ar-buvote-pripazintas-kaltu-del-sunkaus-nusikaltimo"])
        raw_rows = {row["questionNumber"]: row for row in self.bitaitis["rawData"]["anketa"]["rows"]}
        self.assertEqual(raw_rows["9.3"]["answer"], "Nenurodė")

        rows = [{"questionNumber": "9.3", "prompt": "9.3 Ar buvote…", "answer": "Ne"}]
        self.assertEqual(
            normalize_seimo_2012_anketa_rows(rows)["pareiskimai"][
                "ar-buvote-pripazintas-kaltu-del-sunkaus-nusikaltimo"
            ],
            "Ne",
        )

    def test_anketa_fields(self) -> None:
        anketa = self.bitaitis["normalized"]["anketa"]
        self.assertEqual(anketa["gimimo-data"], "1964-10-01")
        self.assertEqual(anketa["gimimo-vieta"], "Tyruliai, Radviliškio raj., Šiaulių apskritis")
        self.assertEqual(anketa["tautybe"], "lietuvis")
        self.assertEqual(len(anketa["issilavinimas"]["irasai"]), 2)
        self.assertEqual(anketa["uzsienio-kalbos"], ["rusų", "lenkų", "anglų"])
        # Q16 and Q17 share one text run on these pages; the walker still
        # splits them at the question number.
        self.assertEqual(
            anketa["pagrindine-darboviete"],
            "VŠĮ Techninės priežiūros tarnyba,generalinio direktoriaus pavaduotojas",
        )
        self.assertEqual(anketa["visuomenine-veikla"], 'asociacijos "Rūpestinga globa" garbės narys')
        self.assertEqual(anketa["sutuoktinio-vardas-pavarde"], "Alina Bitaitienė")
        self.assertEqual(anketa["vaiku-vardai-pavardes"], "Domantas, Žilvinas, Laurynas")

    def test_sparse_anketa_is_null_not_wrong(self) -> None:
        # Dumbrava's form omits Q12-Q15 entirely and leaves the rest blank or
        # "Nenurodė"; a bare "," is the template's empty workplace/position.
        anketa = self.dumbrava["normalized"]["anketa"]
        self.assertEqual(anketa["gimimo-data"], "1958-06-28")
        self.assertIsNone(anketa["gimimo-vieta"])
        self.assertIsNone(anketa["tautybe"])
        self.assertEqual(anketa["issilavinimas"]["irasai"], [])
        self.assertEqual(anketa["uzsienio-kalbos"], [])
        self.assertIsNone(anketa["pagrindine-darboviete"])

    def test_declarations_and_campaign(self) -> None:
        turto = self.bitaitis["normalized"]["turto-ir-pajamu-deklaracijos"]
        self.assertEqual(turto["privalomas-registruoti-turtas"], 870000)
        self.assertEqual(turto["gautos-pajamos"], 150223.92)
        self.assertEqual(turto["valiuta"], "Lt")
        self.assertIn("nuo 2011-01-01 iki 2011-12-31", turto["pastaba"])

        campaign = self.bitaitis["normalized"]["politines-kampanijos-dalyvio-duomenys"][0]
        self.assertEqual(campaign["statusas"], "Atstovaujamasis")
        self.assertEqual(
            campaign["atstovauja"]["pavadinimas"], "TĖVYNĖS SĄJUNGA - LIETUVOS KRIKŠČIONYS DEMOKRATAI (S)"
        )
        self.assertEqual(
            self.podolskis["normalized"]["politines-kampanijos-dalyvio-duomenys"][0]["statusas"],
            "Savarankiškas",
        )


if __name__ == "__main__":
    unittest.main()
