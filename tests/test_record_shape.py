"""The record shape the two reference documents promise, against `data/`.

`docs/DATA_GUIDE.md` said "Seven top-level fields on every record" and scoped
`kandidatavimas` to "the two municipal generals only"; `docs/OUTPUT_SCHEMA.md`
listed the same seven and never named either extra field, although its own
appendices document them. A full-corpus census says `kandidatavimas` is a root
field on 105,737 of 113,073 records across 47 of the 55 elections, and
`candidateNote` on 27,478 across four (issue #144). Both documents drifted the
day issues #79, #92 and #95 landed, and nothing noticed, because the promise
was prose and the corpus is 113,073 files.

So the promise is a list this file reads out of the prose and compares against
the corpus: the three root key-sets that exist, the provenance block every
record carries, the fixed section order, and the sections a record loses.
Everything here is measured, and a new election that changes any of it fails
here rather than in a reader's parser.
"""

from __future__ import annotations

import json
import re
import unittest
from collections import Counter
from pathlib import Path

from tests import local_data

REPO_ROOT = Path(__file__).resolve().parents[1]
DATA_ROOT = REPO_ROOT / "data"
DATA_GUIDE = (REPO_ROOT / "docs" / "DATA_GUIDE.md").read_text(encoding="utf-8")
OUTPUT_SCHEMA = (REPO_ROOT / "docs" / "OUTPUT_SCHEMA.md").read_text(encoding="utf-8")

#: The seven both documents list, in the order they list them.
REQUIRED_FIELDS = (
    "electionId",
    "candidateId",
    "candidateName",
    "source",
    "rawData",
    "normalized",
    "provenance",
)

#: And the two that are not on every record.
OPTIONAL_FIELDS = ("kandidatavimas", "candidateNote")

#: `docs/OUTPUT_SCHEMA.md`'s normalized section order: eleven names in one
#: order, of which each record carries a subset. Nineteen distinct sequences
#: exist in the corpus and every one of them is this list with names left out.
#: Four of the eleven were missing from the document until issue #144 --
#: `kandidatavimas` (the 1996-1999 family, inside `normalized`),
#: `gyvenamoji-vieta` (the six 1996-1999 Seimas elections), `programa` (the
#: 2002 and 2004 presidential elections) and `patiketiniai` (2014 and 2019).
SECTION_ORDER = (
    "profilis",
    "anketa",
    "kandidatavimas",
    "gyvenamoji-vieta",
    "biografija",
    "programa",
    "turto-ir-pajamu-deklaracijos",
    "privaciu-interesu-deklaracija",
    "patiketiniai",
    "politines-kampanijos-dalyvio-duomenys",
    "kita",
)

#: The sections only one election family publishes, and how many records each
#: reaches -- measured, and named in the document beside the order.
SCOPED_SECTIONS = {
    "kandidatavimas": 7_336,
    "gyvenamoji-vieta": 950,
    "programa": 21,
    "patiketiniai": 16,
}

PROVENANCE_KEYS = ("fetchedAt", "parsedAt", "parserCommit", "schemaVersion", "sourceSha256")

#: The rule for reading "a record loses a section": a section absent from most
#: of an election's records is that era's form, not a gap in the corpus.
UNIVERSAL_THRESHOLD = 0.99


class Census:
    """One pass over the corpus, shared by every test below."""

    def __init__(self, data_root: Path) -> None:
        self.records = 0
        self.key_sets: Counter[tuple[str, ...]] = Counter()
        self.key_set_elections: dict[tuple[str, ...], set[str]] = {}
        self.provenance_key_sets: Counter[tuple[str, ...]] = Counter()
        self.without_provenance = 0
        self.without_parser_commit = 0
        self.section_sequences: Counter[tuple[str, ...]] = Counter()
        self.totals: Counter[str] = Counter()
        self.section_counts: dict[str, Counter[str]] = {}
        self.lost_sections: list[tuple[str, str, str]] = []
        self._sections_by_record: list[tuple[str, str, set[str]]] = []

        for election in sorted(child for child in data_root.iterdir() if child.is_dir()):
            for path in sorted(election.glob("*.json")):
                if path.name == "index.json":
                    continue
                try:
                    record = json.loads(path.read_text(encoding="utf-8"))
                except (json.JSONDecodeError, UnicodeDecodeError):
                    continue
                if not isinstance(record, dict) or "normalized" not in record:
                    continue
                self.records += 1
                self.totals[election.name] += 1
                key_set = tuple(sorted(record))
                self.key_sets[key_set] += 1
                self.key_set_elections.setdefault(key_set, set()).add(election.name)
                provenance = record.get("provenance")
                if isinstance(provenance, dict):
                    self.provenance_key_sets[tuple(sorted(provenance))] += 1
                    if not provenance.get("parserCommit"):
                        self.without_parser_commit += 1
                else:
                    self.without_provenance += 1
                sections = tuple(record.get("normalized") or {})
                self.section_sequences[sections] += 1
                counts = self.section_counts.setdefault(election.name, Counter())
                for section in sections:
                    counts[section] += 1
                self._sections_by_record.append((election.name, path.stem, set(sections)))

        for section in SECTION_ORDER:
            for election, total in self.totals.items():
                published = self.section_counts.get(election, Counter()).get(section, 0)
                if not total or published / total <= UNIVERSAL_THRESHOLD or published == total:
                    continue
                for name, stem, sections in self._sections_by_record:
                    if name == election and section not in sections:
                        self.lost_sections.append((section, election, stem))

    def root_field(self, field: str) -> tuple[int, int]:
        """(records, elections) carrying `field` at the root."""
        records = sum(count for keys, count in self.key_sets.items() if field in keys)
        elections = set()
        for keys, names in self.key_set_elections.items():
            if field in keys:
                elections |= names
        return records, len(elections)


class RecordShapeTests(unittest.TestCase):
    census: Census

    @classmethod
    def setUpClass(cls) -> None:
        local_data.require_corpus(complete=True)
        cls.census = Census(DATA_ROOT)

    # -- the root fields ----------------------------------------------------

    def test_exactly_three_root_key_sets_exist(self):
        expected = {
            tuple(sorted(REQUIRED_FIELDS)),
            tuple(sorted(REQUIRED_FIELDS + ("kandidatavimas",))),
            tuple(sorted(REQUIRED_FIELDS + OPTIONAL_FIELDS)),
        }
        self.assertEqual(set(self.census.key_sets), expected)

    def test_the_seven_are_on_every_record(self):
        for keys in self.census.key_sets:
            with self.subTest(keys=keys):
                self.assertEqual(set(REQUIRED_FIELDS) - set(keys), set())

    def test_the_documented_scope_of_the_two_optional_fields_is_the_measured_one(self):
        # The numbers the documents print. A new election moves them, which is
        # the point: the prose said "the two municipal generals only" for
        # 105,737 records across 47 elections.
        records, elections = self.census.root_field("kandidatavimas")
        self.assertEqual((records, elections), (105_737, 47))
        self.assertIn("105,737 records across 47 of the 55 elections", DATA_GUIDE)
        self.assertIn("105,737 records across 47 of the 55 elections", OUTPUT_SCHEMA)

        records, elections = self.census.root_field("candidateNote")
        self.assertEqual((records, elections), (27_478, 4))
        for document in (DATA_GUIDE, OUTPUT_SCHEMA):
            self.assertIn("27,478 records", document)

    def test_the_documents_name_both_optional_fields(self):
        for field in OPTIONAL_FIELDS:
            for name, document in (("DATA_GUIDE", DATA_GUIDE), ("OUTPUT_SCHEMA", OUTPUT_SCHEMA)):
                with self.subTest(field=field, document=name):
                    self.assertIn(f"`{field}`", document)

    def test_the_archive_family_keeps_its_candidacy_block_inside_normalized(self):
        # Which is the exception worth a sentence: a consumer that walks the
        # root for it finds nothing there for 7,336 records.
        bare = tuple(sorted(REQUIRED_FIELDS))
        self.assertEqual(self.census.key_sets[bare], 7_336)
        self.assertEqual(len(self.census.key_set_elections[bare]), 8)
        for election in self.census.key_set_elections[bare]:
            with self.subTest(election):
                self.assertRegex(election, r"^199[6-9]-")

    # -- provenance ---------------------------------------------------------

    def test_every_record_carries_one_provenance_shape(self):
        self.assertEqual(self.census.without_provenance, 0)
        self.assertEqual(list(self.census.provenance_key_sets), [tuple(sorted(PROVENANCE_KEYS))])

    def test_the_documents_state_the_measured_parser_commit_gap(self):
        # The documented "~0.4 % carry no provenance block" was a case that no
        # longer occurs, while the field that *is* routinely null carried no
        # number at all.
        share = self.census.without_parser_commit / self.census.records * 100
        self.assertAlmostEqual(share, 43.9, delta=0.1)
        for document in (DATA_GUIDE, OUTPUT_SCHEMA):
            self.assertIn("49,586 records", document)
        self.assertNotIn("About 0.4 % of records have no retained primary page", OUTPUT_SCHEMA)

    # -- sections -----------------------------------------------------------

    def test_the_section_order_is_fixed(self):
        # One order, 19 sequences, each of them this list with names left out.
        documented = {section: index for index, section in enumerate(SECTION_ORDER)}
        for sections, count in self.census.section_sequences.items():
            with self.subTest(sections=sections, records=count):
                positions = [documented[s] for s in sections if s in documented]
                self.assertEqual(positions, sorted(positions))

    def test_no_section_is_unknown_to_the_documents(self):
        seen = {section for sections in self.census.section_sequences for section in sections}
        self.assertEqual(seen - set(SECTION_ORDER), set())
        # And the order is written down where a reader looks for it.
        for section in SECTION_ORDER:
            with self.subTest(section):
                self.assertIn(f"`{section}`", OUTPUT_SCHEMA)

    def test_the_scoped_sections_reach_the_records_the_document_says(self):
        counts = Counter()
        for sections, records in self.census.section_sequences.items():
            for section in sections:
                counts[section] += records
        for section, expected in SCOPED_SECTIONS.items():
            with self.subTest(section):
                self.assertEqual(counts[section], expected)

    def test_the_records_that_lose_a_section_are_the_documented_ones(self):
        expected = {
            ("biografija", "gintaras-binkauskas-2012-seimo"),
            ("biografija", "gintaras-binkauskas-2016-seimo"),
            ("biografija", "jonas-korsakas-2020-seimo"),
            ("turto-ir-pajamu-deklaracijos", "stasys-stankus-205466-2002-gruodzio-22-savivaldybiu-tarybu"),
            ("turto-ir-pajamu-deklaracijos", "saulius-jancys-205870-2002-gruodzio-22-savivaldybiu-tarybu"),
            ("turto-ir-pajamu-deklaracijos", "mindaugas-kucinskas-205871-2002-gruodzio-22-savivaldybiu-tarybu"),
            ("turto-ir-pajamu-deklaracijos", "genovaite-ziobakiene-2004-seimo"),
            ("turto-ir-pajamu-deklaracijos", "darius-juodeska-72579-2015-kovo-1-savivaldybiu"),
            ("turto-ir-pajamu-deklaracijos", "jonas-korsakas-2020-seimo"),
            ("politines-kampanijos-dalyvio-duomenys", "algimantas-matulevicius-2009-ep"),
            ("politines-kampanijos-dalyvio-duomenys", "valdemar-tomasevski-2009-ep"),
        }
        measured = {(section, stem) for section, _, stem in self.census.lost_sections}
        self.assertEqual(measured, expected)
        # And both documents name every one of them, so a reader meets the
        # list before their parser does.
        for _, stem in sorted(expected):
            with self.subTest(stem):
                short = re.sub(r"-(19|20)\d\d-.*$", "", stem)
                self.assertTrue(
                    short in DATA_GUIDE or stem in DATA_GUIDE, f"{stem} unnamed in DATA_GUIDE.md"
                )
                self.assertTrue(
                    short in OUTPUT_SCHEMA or stem in OUTPUT_SCHEMA,
                    f"{stem} unnamed in OUTPUT_SCHEMA.md",
                )


if __name__ == "__main__":
    unittest.main()
