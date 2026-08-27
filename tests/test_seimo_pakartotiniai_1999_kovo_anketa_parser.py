"""The 1999-03-21 re-run — one election, three constituencies, 22 candidates.

The last election of the 1996-1998 Seimas archive family, and the only one
whose directory is outside `seim96`/`seimpk`: `19990321`, the date-named
convention `savivaldybiu_2000` and `seimo_2000` also use. The pages are still
this family's layout, so the directory name says nothing about the page era —
`test_a_date_named_directory_is_still_this_layout_family` is what pins that,
because getting it backwards would send a future election to the wrong parsers.
"""

import json
import tempfile
import unittest
from collections import Counter
from pathlib import Path

from scraper.elections.seimo_pakartotiniai_1999_kovo.anketa_parser import parse_anketa_samples
from scraper.elections.seimo_pakartotiniai_1999_kovo.sitemap import (
    CONSTITUENCIES,
    DIRECTORY,
    PHASE,
)

ELECTION_ID = "1999-kovo-21-seimo-pakartotiniai"
NAUJOSIOS_VILNIOS = (
    "antanaitis-audrys", "balcevic-zbignev", "melianas-arturas", "petkevicius-juozapas",
    "sablinskas-eduardas", "sarkus-juozas", "zacharevic-miroslav",
)
NEVEZIO = (
    "braziene-valerija", "daukas-virginijus", "davydovas-sergiejus", "liepa-rimantas",
    "malukas-edmundas-zenonas", "satkevicius-vitalijus", "sedzius-laimutis",
    "terleckas-antanas",
)
VILNIAUS_TRAKU = (
    "garbovskaja-marija", "ivanoviene-bronislava", "jankovski-henrik", "komiciene-vida",
    "pilikauskas-stasys", "purvaneckiene-giedre", "tryk-zdislav",
)
CANDIDATE_IDS = NAUJOSIOS_VILNIOS + NEVEZIO + VILNIAUS_TRAKU


class SeimoPakartotiniai1999KovoAnketaParserTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.purvaneckiene = self._parse("purvaneckiene-giedre")

    def _parse(self, candidate_id: str) -> dict:
        results = parse_anketa_samples(
            candidate_ids=[candidate_id], output_root=Path(self._tmp.name)
        )
        self.assertEqual(results[0]["anomalies"], [], candidate_id)
        return json.loads(Path(results[0]["outputPath"]).read_text(encoding="utf-8"))

    def test_a_date_named_directory_is_still_this_layout_family(self) -> None:
        # `19990321` looks like `20000319`/`20001008`, which are the *2000*
        # layout. This election is the counter-example: same date-named
        # convention, 1996-1998 pages. The shared module takes the directory
        # as a parameter precisely so the two are independent.
        self.assertEqual(DIRECTORY, "19990321")
        self.assertEqual(PHASE, "11")
        self.assertTrue(
            self.purvaneckiene["source"]["candidateSourceUrl"].endswith(".htm"),
        )
        self.assertIn("/19990321/", self.purvaneckiene["source"]["candidateSourceUrl"])

    def test_top_level_fields(self) -> None:
        self.assertEqual(self.purvaneckiene["electionId"], ELECTION_ID)
        self.assertEqual(self.purvaneckiene["candidateName"], "Giedrė Purvaneckienė")

    def test_the_election_spans_all_three_constituencies(self) -> None:
        self.assertEqual(CONSTITUENCIES, [10, 26, 57])
        seen = Counter()
        for candidate_id in CANDIDATE_IDS:
            with self.subTest(candidate_id):
                candidacies = self._parse(candidate_id)["rawData"]["candidacies"]
                self.assertEqual(len(candidacies), 1)
                seen[candidacies[0]["apygardaNumber"]] += 1
        self.assertEqual(seen, Counter({10: 7, 26: 8, 57: 7}))

    def test_the_card_questionnaire_is_read(self) -> None:
        anketa = self.purvaneckiene["normalized"]["anketa"]
        self.assertEqual(anketa["tautybe"], "Lietuvis (-ė)")
        # The only candidate of the 22 with both an academic degree and title.
        self.assertTrue(anketa["mokslo-laipsnis"])
        self.assertTrue(anketa["pedagoginis-vardas"])

    def test_the_prose_birthplace_fallback_covers_six_of_the_twenty_two(self) -> None:
        # 10 cards print "Gimimo vieta"; the biography reaches 6 more, and only
        # those 6 carry the source marker.
        anketa = self._parse("antanaitis-audrys")["normalized"]["anketa"]
        self.assertEqual(anketa["gimimo-vieta"], "Palanga")
        self.assertEqual(anketa["gimimo-vietos-saltinis"], "biografijos-tekstas")

    def test_the_complete_field_parses_and_its_coverage_is_pinned(self) -> None:
        counts = Counter()
        for candidate_id in CANDIDATE_IDS:
            record = self._parse(candidate_id)
            # The most complete of the four by-elections of this era: every
            # card links both sub-pages, unlike March 1998's 2-of-11.
            self.assertIsNotNone(record["normalized"]["biografija"], candidate_id)
            self.assertIsNotNone(
                record["normalized"]["turto-ir-pajamu-deklaracijos"], candidate_id
            )
            self.assertIsNotNone(record["normalized"]["gyvenamoji-vieta"], candidate_id)
            for key, value in (record["normalized"].get("anketa") or {}).items():
                if value not in (None, "", [], {}):
                    counts[key] += 1
        self.assertEqual(
            {key: counts[key] for key in sorted(counts)},
            {
                "anksciau-isrinktas": 7,
                "gimimo-data": 15,
                "gimimo-data-saltinis": 15,
                "gimimo-metai": 21,
                "gimimo-vieta": 16,
                "gimimo-vietos-saltinis": 6,
                "issilavinimas": 21,
                "mokslo-laipsnis": 2,
                "pagrindine-darboviete": 20,
                "pedagoginis-vardas": 1,
                "seimine-padetis": 12,
                "seimos-nariai": 20,
                "sutuoktinio-vardas-pavarde": 16,
                "tautybe": 20,
                "uzsienio-kalbos": 21,
                "vaiku-vardai-pavardes": 19,
                "visuomenine-veikla": 16,
            },
        )
        # No card prints the free-text self-description (0 of 22 on the raw
        # HTML), so no record carries the key.
        self.assertNotIn("kita-apie-save", counts)

    def test_the_failed_election_makes_isrinktas_a_known_false(self) -> None:
        sablinskas = self._parse("sablinskas-eduardas")["normalized"]["kandidatavimas"][0]
        self.assertIs(sablinskas["isrinktas"], False)
        self.assertEqual(sablinskas["turai"][0]["balsai"], 2735)
        self.assertEqual(sablinskas["turai"][0]["apygardos-numeris"], 10)


if __name__ == "__main__":
    unittest.main()
