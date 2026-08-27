"""The 1998-03-22 re-run — one election, two constituencies, 11 candidates.

VRK's `seimpk` index names Naujosios Vilnios (No. 10) and Vilniaus Trakų
(No. 57) as one election, so this is one module over both, the way
`seimo_pakartotiniai_1997_kovo` covers its four. GitHub carried them as two
tickets (#21, #22); #22 was closed as a duplicate on that reading, and the
split-by-constituency test below is what would catch a regression back to it.

Two things about this election look like scrape failures and are not: only 2
of the 11 cards link a declaration, and none prints an academic degree, an
academic title, public activity or the free-text self-description. Both are
pinned here so a future parser change cannot quietly turn a real absence into
a silent one.
"""

import json
import tempfile
import unittest
from collections import Counter
from pathlib import Path

from scraper.elections.seimo_pakartotiniai_1998_kovo.anketa_parser import parse_anketa_samples

ELECTION_ID = "1998-kovo-22-seimo-pakartotiniai"
NAUJOSIOS_VILNIOS = (
    "antanaitis-audrys",
    "filipovic-tadeus",
    "jocius-kazimieras-jonas",
    "paulauskas-arturas",
    "petniunas-vytautas",
)
VILNIAUS_TRAKU = (
    "bologoviene-regina",
    "maldaikiene-birute",
    "mickevicius-antanas",
    "suboc-danute",
    "subotinas-jurijus",
    "tomasevski-valdemar",
)
CANDIDATE_IDS = NAUJOSIOS_VILNIOS + VILNIAUS_TRAKU


class SeimoPakartotiniai1998KovoAnketaParserTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.paulauskas = self._parse("paulauskas-arturas")

    def _parse(self, candidate_id: str) -> dict:
        results = parse_anketa_samples(
            candidate_ids=[candidate_id], output_root=Path(self._tmp.name)
        )
        self.assertEqual(results[0]["anomalies"], [], candidate_id)
        return json.loads(Path(results[0]["outputPath"]).read_text(encoding="utf-8"))

    def test_top_level_fields(self) -> None:
        self.assertEqual(self.paulauskas["electionId"], ELECTION_ID)
        self.assertEqual(self.paulauskas["candidateName"], "Artūras Paulauskas")
        self.assertEqual(
            self.paulauskas["rawData"]["candidacies"][0]["nominator"], "Išsikėlė pats"
        )

    def test_the_election_spans_both_constituencies(self) -> None:
        # The regression this guards is splitting 1998-03-22 back into two
        # elections: one polling day, one election id, 5 + 6 candidates.
        seen = Counter()
        for candidate_id in CANDIDATE_IDS:
            with self.subTest(candidate_id):
                candidacies = self._parse(candidate_id)["rawData"]["candidacies"]
                self.assertEqual(len(candidacies), 1)
                seen[(candidacies[0]["apygardaName"], candidacies[0]["apygardaNumber"])] += 1
        self.assertEqual(seen, Counter({("Naujosios Vilnios", 10): 5, ("Vilniaus Trakų", 57): 6}))

    def test_the_prose_birthplace_fallback_earns_its_keep_here(self) -> None:
        # 6 of the 11 cards print "Gimimo vieta"; the biography's opening
        # sentence reaches 3 more, and only those 3 carry the source marker.
        # This is the first election of the family where the fallback adds
        # anything at all -- in the November 1998 re-run it adds none.
        anketa = self.paulauskas["normalized"]["anketa"]
        self.assertEqual(anketa["gimimo-vieta"], "Vilnius")
        self.assertEqual(anketa["gimimo-vietos-saltinis"], "biografijos-tekstas")

        from_card = self._parse("filipovic-tadeus")["normalized"]["anketa"]
        self.assertTrue(from_card["gimimo-vieta"])
        self.assertNotIn("gimimo-vietos-saltinis", from_card)

    def test_only_two_of_eleven_cards_link_a_declaration(self) -> None:
        # Unique to this election in its era -- 1998-11-15 is 11/11. A mostly
        # empty declaration column here is the source, not a scrape failure.
        with_declaration = {
            candidate_id
            for candidate_id in CANDIDATE_IDS
            if self._parse(candidate_id)["normalized"].get("turto-ir-pajamu-deklaracijos")
        }
        self.assertEqual(with_declaration, {"filipovic-tadeus", "tomasevski-valdemar"})

    def test_the_complete_field_parses_and_its_coverage_is_pinned(self) -> None:
        counts = Counter()
        for candidate_id in CANDIDATE_IDS:
            record = self._parse(candidate_id)
            # Every card links a biography, even where it links no declaration.
            self.assertIsNotNone(record["normalized"]["biografija"], candidate_id)
            self.assertIsNotNone(record["normalized"]["gyvenamoji-vieta"], candidate_id)
            for key, value in (record["normalized"].get("anketa") or {}).items():
                if value not in (None, "", [], {}):
                    counts[key] += 1
        self.assertEqual(
            {key: counts[key] for key in sorted(counts)},
            {
                "anksciau-isrinktas": 1,
                "gimimo-data": 9,
                "gimimo-data-saltinis": 9,
                "gimimo-metai": 10,
                "gimimo-vieta": 9,
                "gimimo-vietos-saltinis": 3,
                "issilavinimas": 8,
                "pagrindine-darboviete": 8,
                "seimine-padetis": 6,
                "seimos-nariai": 6,
                "sutuoktinio-vardas-pavarde": 6,
                "tautybe": 5,
                "uzsienio-kalbos": 7,
                "vaiku-vardai-pavardes": 5,
            },
        )
        # Four labels no card of this election prints, so no record has the
        # key at all. Verified against the raw cards, not inferred.
        for absent in (
            "mokslo-laipsnis",
            "pedagoginis-vardas",
            "visuomenine-veikla",
            "kita-apie-save",
        ):
            with self.subTest(absent):
                self.assertNotIn(absent, counts)

    def test_the_failed_election_makes_isrinktas_a_known_false(self) -> None:
        # Both constituencies closed "Rinkimai apygardoje neįvyko", so every
        # candidacy is false rather than null. These two pages are also the
        # family's only results capture with no candidate ids on its rows, so
        # the votes below arrived through the name join.
        paulauskas = self._parse("paulauskas-arturas")["normalized"]["kandidatavimas"][0]
        self.assertIs(paulauskas["isrinktas"], False)
        self.assertNotIn("isrinktas-kaip", paulauskas)
        self.assertEqual(paulauskas["turai"][0]["balsai"], 12851)
        self.assertEqual(paulauskas["turai"][0]["vieta"], 1)


if __name__ == "__main__":
    unittest.main()
