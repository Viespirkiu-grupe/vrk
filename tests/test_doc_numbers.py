"""The measured figures the documents print, re-measured against the corpus.

Issue #84 fixed one generation of headline counts and asked for the step that
would stop the next one rotting; it was never built, and issue #150 found
about thirty figures across seven documents that no longer reproduce — JSON
storage documented at 0.66 GB against a measured 3.41, an anomaly total 78
events low, the hygiene pins quoted at two different wrong values, and
`docs/FIELD_COVERAGE.md`'s own worked example printing numbers the gate it
documents does not.

So each figure is read out of the prose here and compared against a fresh
measurement. One walk of `data/` serves all of them; the module skips without
a corpus, like every other whole-corpus pin. A figure that moves fails here,
naming the document, instead of going quietly stale for two corpora.

What is deliberately *not* pinned: figures a document records as a dated
one-off measurement ("measured once on 2026-08-26 over the 906 records the
family then held"), and the suite's own pass/skip counts, which no test can
measure without measuring itself.
"""

from __future__ import annotations

import json
import re
import sys
import unittest
from collections import Counter
from pathlib import Path

from tests import local_data

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "tests"))

DOCS = {
    name: (REPO_ROOT / "docs" / f"{name}.md").read_text(encoding="utf-8")
    for name in (
        "DATASET",
        "DATA_GUIDE",
        "OUTPUT_SCHEMA",
        "CANDIDACIES",
        "CLI_REFERENCE",
        "ANOMALY_DETECTION",
        "FIELD_COVERAGE",
        "DASHBOARD",
    )
}

#: The six elections of the 1996-1999 Seimas archive family, whose appendix in
#: OUTPUT_SCHEMA.md measured three of them and said six.
ARCHIVE_FAMILY = (
    "1996-spalio-20-seimo",
    "1997-kovo-23-seimo-pakartotiniai",
    "1997-gruodzio-21-seimo-pakartotiniai",
    "1998-kovo-22-seimo-pakartotiniai",
    "1998-lapkricio-15-seimo-pakartotiniai",
    "1999-kovo-21-seimo-pakartotiniai",
)

ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
YEAR = re.compile(r"^\d{4}$")


def thousands(value: int) -> str:
    return f"{value:,}"


class Census:
    """One walk of the corpus, holding every figure the documents state."""

    def __init__(self, data_root: Path) -> None:
        from test_corpus_value_hygiene import GLUED, URLISH, _leaves

        self.records = 0
        self.record_bytes = 0
        self.photo_files = 0
        self.photo_bytes = 0
        self.litas = 0
        self.with_declaration = 0
        self.says_eur = 0
        self.vrk_id_records = 0
        self.vrk_id_elections: set[str] = set()
        self.positional_records = 0
        self.positional_elections: set[str] = set()
        self.glued = 0
        self.glued_with_vsi = 0
        self.date_shapes: dict[str, Counter[str]] = {
            "nuosprendzio-data": Counter(),
            "isipareigojimo-data": Counter(),
        }
        self.archive_records = 0
        self.archive_birth = Counter()

        for election in sorted(child for child in data_root.iterdir() if child.is_dir()):
            paths = sorted(election.glob("*.json"))
            slugs = set()
            rows = []
            for path in paths:
                if path.name == "index.json":
                    continue
                try:
                    record = json.loads(path.read_text(encoding="utf-8"))
                except (json.JSONDecodeError, UnicodeDecodeError):
                    continue
                if not isinstance(record, dict) or "normalized" not in record:
                    continue
                self.records += 1
                self.record_bytes += path.stat().st_size
                candidate_id = str(record.get("candidateId") or "")
                slugs.add(candidate_id)
                rows.append(candidate_id)

                declaration = (record.get("normalized") or {}).get("turto-ir-pajamu-deklaracijos")
                if declaration:
                    self.with_declaration += 1
                    currency = declaration.get("valiuta") if isinstance(declaration, dict) else None
                    if currency == "Lt":
                        self.litas += 1
                    elif currency == "EUR":
                        self.says_eur += 1

                values: list[tuple[str, object]] = []
                _leaves(record.get("normalized"), "", values)
                for path_text, value in values:
                    if not isinstance(value, str) or not value:
                        continue
                    leaf = path_text.rsplit(".", 1)[-1]
                    if leaf in self.date_shapes:
                        shape = (
                            "iso"
                            if ISO_DATE.match(value)
                            else "year"
                            if YEAR.match(value)
                            else "other"
                        )
                        self.date_shapes[leaf][shape] += 1
                    if URLISH.search(value) or not GLUED.search(value):
                        continue
                    self.glued += 1
                    if "VšĮ" in value:
                        self.glued_with_vsi += 1

                if election.name in ARCHIVE_FAMILY:
                    self.archive_records += 1
                    anketa = (record.get("normalized") or {}).get("anketa") or {}
                    if anketa.get("gimimo-data"):
                        self.archive_birth["full"] += 1
                    elif anketa.get("gimimo-metai"):
                        self.archive_birth["year"] += 1
                    else:
                        self.archive_birth["neither"] += 1

            for candidate_id in rows:
                tail = candidate_id.rsplit("-", 1)[-1]
                if tail.isdigit() and len(tail) >= 3:
                    self.vrk_id_records += 1
                    self.vrk_id_elections.add(election.name)
                elif tail.isdigit() and candidate_id.rsplit("-", 1)[0] in slugs:
                    self.positional_records += 1
                    self.positional_elections.add(election.name)

            photos = election / "photos"
            if photos.is_dir():
                for photo in photos.iterdir():
                    if photo.is_file():
                        self.photo_files += 1
                        self.photo_bytes += photo.stat().st_size


class DocumentNumberTests(unittest.TestCase):
    census: Census

    @classmethod
    def setUpClass(cls) -> None:
        local_data.require_corpus(complete=True)
        cls.census = Census(REPO_ROOT / "data")

    # -- storage ------------------------------------------------------------

    def test_the_storage_figures_are_the_corpus_on_disk(self):
        # DATASET.md said "~0.66 GB of JSON", 5.2x under the measured size,
        # while a paragraph on the same page said 3,447.6 MB.
        records_gb = self.census.record_bytes / 1e9
        photos_gb = self.census.photo_bytes / 1e9
        self.assertIn(f"{records_gb:.2f} GB of JSON over the {thousands(self.census.records)}", DOCS["DATASET"])
        self.assertIn(f"{photos_gb:.2f} GB of photo sidecars", DOCS["DATASET"])
        self.assertIn(f"{thousands(self.census.photo_files)} portraits", DOCS["DATASET"])

    # -- value hygiene ------------------------------------------------------

    def test_the_hygiene_counts_are_the_test_that_owns_them(self):
        from test_corpus_value_hygiene import GLUED_VALUES, REPLACEMENT_CHARACTER_VALUES

        self.assertEqual(self.census.glued, GLUED_VALUES)
        for document in ("DATASET", "DATA_GUIDE"):
            with self.subTest(document):
                self.assertIn(thousands(GLUED_VALUES), DOCS[document])
                self.assertIn(thousands(self.census.glued_with_vsi), DOCS[document])
        self.assertIn(f"{REPLACEMENT_CHARACTER_VALUES} surviving", DOCS["DATASET"])

    # -- money --------------------------------------------------------------

    def test_the_litas_count_is_the_same_number_everywhere_it_appears(self):
        # Three documents said 79,071 — the count before
        # 2003-birzelio-15-seimo-nauji landed — and DASHBOARD.md said
        # "36,362 of 76,776", which corresponded to nothing.
        self.assertEqual(self.census.says_eur, 0)
        for document in ("DATA_GUIDE", "DASHBOARD"):
            with self.subTest(document):
                self.assertIn(thousands(self.census.litas), DOCS[document])
        self.assertIn(
            f"{thousands(self.census.litas)} of {thousands(self.census.with_declaration)}",
            DOCS["DASHBOARD"],
        )

    # -- ids ----------------------------------------------------------------

    def test_the_candidate_id_shapes_are_the_measured_ones(self):
        # "positional -2/-3 suffixes (18 elections) vs name-slug-plus-VRK-id
        # in the two municipal generals" — really 7 elections and 92,357
        # records for the VRK-id form, and 64 records over 9 for the suffix.
        self.assertIn(
            f"{thousands(self.census.vrk_id_records)} records of"
            f" {'seven' if len(self.census.vrk_id_elections) == 7 else len(self.census.vrk_id_elections)}"
            " elections",
            DOCS["DATA_GUIDE"],
        )
        self.assertIn(f"{thousands(self.census.positional_records)} records over nine", DOCS["DATA_GUIDE"])
        self.assertEqual(len(self.census.positional_elections), 9)

    # -- dates --------------------------------------------------------------

    def test_the_two_date_shapes_are_documented_as_measured(self):
        conviction = self.census.date_shapes["nuosprendzio-data"]
        obligation = self.census.date_shapes["isipareigojimo-data"]
        values = scraper_values_source()
        self.assertIn(f"year-only on {conviction['year']} of its", values)
        self.assertIn(f"ISO on {conviction['iso']}", values)
        self.assertIn(f"year-only on {thousands(obligation['year'])} of {thousands(sum(obligation.values()))}", values)

    # -- the archive appendix ----------------------------------------------

    def test_the_archive_appendix_covers_its_whole_family(self):
        self.assertEqual(self.census.archive_records, 950)
        self.assertIn(f"family's {self.census.archive_records} records", DOCS["OUTPUT_SCHEMA"])
        births = self.census.archive_birth
        self.assertIn(
            f"{births['full']} full dates (76 %), {births['year']}\n    year-only, {births['neither']} neither",
            DOCS["OUTPUT_SCHEMA"],
        )
        self.assertEqual(sum(births.values()), self.census.archive_records)


def scraper_values_source() -> str:
    return (REPO_ROOT / "scraper" / "shared" / "values.py").read_text(encoding="utf-8")


class AnomalyNumberTests(unittest.TestCase):
    """The anomaly totals, which three documents quote and one contradicts."""

    @classmethod
    def setUpClass(cls) -> None:
        local_data.require_corpus(complete=True)
        from scraper.shared.anomaly_report import read_events

        cls.events = list(read_events(REPO_ROOT / "data"))
        cls.severity = Counter(str(event.get("severity")) for event in cls.events)
        cls.stage = Counter(str(event.get("stage")) for event in cls.events)
        cls.types = Counter(str(event.get("eventType")) for event in cls.events)

    def test_the_total_is_the_same_in_every_document_that_states_it(self):
        total = thousands(len(self.events))
        for document in ("DATASET", "CLI_REFERENCE", "ANOMALY_DETECTION"):
            with self.subTest(document):
                self.assertIn(total, DOCS[document])

    def test_the_severity_table_is_the_corpus(self):
        table = DOCS["ANOMALY_DETECTION"]
        self.assertIn(f"| `error` | a page was lost — unreadable, or never fetched | {self.severity['error']} |", table)
        self.assertIn(f"missing a field | {self.severity['warning']} |", table)
        self.assertIn(f"its own fault | {thousands(self.severity['info'])} |", table)
        self.assertEqual(self.severity["critical"], 0)

    def test_the_per_type_table_sums_to_the_corpus_and_names_every_type(self):
        rows = re.findall(r"^\| ([\d,]+) \| `([A-Za-z]+)`", DOCS["ANOMALY_DETECTION"], re.M)
        self.assertEqual(sum(int(count.replace(",", "")) for count, _ in rows), len(self.events))
        self.assertEqual({name for _, name in rows}, set(self.types))
        # And the heading says how many types that is.
        self.assertIn(f"## The {number_word(len(self.types))} types that fire", DOCS["ANOMALY_DETECTION"])

    def test_the_fetch_stage_share_is_stated_not_denied(self):
        # CLI_REFERENCE said "not one of them says stage: fetch", which was
        # true when the flag existed and nothing passed it.
        self.assertGreater(self.stage["fetch"], 0)
        self.assertIn(
            f"{thousands(self.stage['parse'])} of the corpus's {thousands(len(self.events))}",
            DOCS["CLI_REFERENCE"],
        )
        self.assertIn(f"The {self.stage['fetch']} that say", DOCS["CLI_REFERENCE"])


def number_word(value: int) -> str:
    words = {
        8: "eight",
        9: "nine",
        10: "ten",
        11: "eleven",
        12: "twelve",
        13: "thirteen",
    }
    return words.get(value, str(value))


class CoverageExampleTests(unittest.TestCase):
    """FIELD_COVERAGE.md's worked example, against the gate's own output."""

    def test_the_example_rows_are_what_the_gate_prints(self):
        coverage = REPO_ROOT / "data" / "coverage.tsv"
        local_data.require(coverage)
        rows = {
            (parts[0], parts[1]): parts
            for parts in (line.split("\t") for line in coverage.read_text(encoding="utf-8").splitlines())
            if len(parts) > 5
        }
        row = rows.get(("gautos-pajamos", "2020-seimo"))
        self.assertIsNotNone(row, "the example's cell is gone from data/coverage.tsv")
        records, key_present, non_null, pct = row[2], row[3], row[4], row[5]
        self.assertIn(
            f"gautos-pajamos   2020-seimo                    {records}        {key_present}     {non_null}  {pct}  ok",
            DOCS["FIELD_COVERAGE"],
        )


class CandidacyTableNumberTests(unittest.TestCase):
    """docs/CANDIDACIES.md's figures, against the built table.

    Six of them were stale: 23,141 net records for 27,795, `nera` 855 for
    838, the €0-when-summed count, and the education shares by a tenth of a
    point each way.
    """

    rows: list[dict[str, str]] = []

    @classmethod
    def setUpClass(cls) -> None:
        import csv
        import gzip
        import io

        table = REPO_ROOT / "dist" / "candidacies.csv.gz"
        local_data.require(table)
        with gzip.open(table) as handle:
            cls.rows = list(csv.DictReader(io.TextIOWrapper(handle, encoding="utf-8")))

    @staticmethod
    def _number(value: str | None) -> float | None:
        try:
            return float(value)  # type: ignore[arg-type]
        except (TypeError, ValueError):
            return None

    def test_the_declaration_status_counts(self):
        status = Counter(row["declaration_status"] for row in self.rows)
        self.assertIn(f"`yra` ({thousands(status['yra'])} records)", DOCS["CANDIDACIES"])
        self.assertIn(f"`nera` ({thousands(status['nera'])})", DOCS["CANDIDACIES"])
        self.assertIn(f"`archyvo-skenai` ({status['archyvo-skenai']} —", DOCS["CANDIDACIES"])

    def test_the_net_income_count(self):
        typed = sum(1 for row in self.rows if row["income_measure"] == "neto-archyvas")
        with_figure = sum(
            1
            for row in self.rows
            if row["income_measure"] == "neto-archyvas" and row.get("income_eur")
        )
        self.assertIn(
            f"{thousands(with_figure)} records carry a net figure"
            f" ({thousands(typed)} rows are typed `neto-archyvas`)",
            DOCS["CANDIDACIES"],
        )

    def test_the_zero_when_summed_count(self):
        keys = (
            "assets_registered_eur",
            "securities_eur",
            "cash_eur",
            "loans_given_eur",
            "loans_received_eur",
        )
        count = sum(
            1
            for row in self.rows
            if (self._number(row.get("assets_total_eur")) or 0) > 0
            and not any((self._number(row.get(key)) or 0) for key in keys)
        )
        self.assertIn(f"reads €0 for {thousands(count)} declarations", DOCS["CANDIDACIES"])

    def test_the_education_shares(self):
        higher = sum(1 for row in self.rows if row.get("education_higher") in ("1", "true", "True"))
        levelled = sum(1 for row in self.rows if row.get("education_level_rank"))
        self.assertIn(f"{levelled / len(self.rows) * 100:.1f} % of all records carry a mapped level", DOCS["CANDIDACIES"])
        self.assertIn(f"{higher / len(self.rows) * 100:.1f} % of all records are", DOCS["CANDIDACIES"])
        self.assertIn(f"{higher / levelled * 100:.1f} % on the answered-only", DOCS["CANDIDACIES"])

    def test_the_donation_inflation_ceiling(self):
        """The worst naive-vs-per-campaign ratio, which four places state.

        DATASET.md's table reproduces exactly; `build_candidacy_table.py`'s
        own docstring said 1,189x.
        """
        import sqlite3

        database = REPO_ROOT / "dist" / "vrk.sqlite"
        local_data.require(database)
        connection = sqlite3.connect(database)
        try:
            campaigns = {
                key: (election, candidacies, total)
                for key, election, candidacies, total in connection.execute(
                    "SELECT campaign_key, election_id, candidacies, donations_total_eur FROM campaigns"
                )
            }
        finally:
            connection.close()
        naive: Counter[str] = Counter()
        true: Counter[str] = Counter()
        for row in self.rows:
            entry = campaigns.get(row.get("campaign_key") or "")
            if entry and entry[2]:
                naive[row["election_id"]] += float(entry[2])
        for election, _, total in campaigns.values():
            if total:
                true[election] += float(total)
        worst = max(
            (naive[election] / true[election], election) for election in naive if true[election]
        )
        self.assertIn(f"**{worst[0]:,.0f}×**", DOCS["DATASET"])
        builder = (REPO_ROOT / "scripts" / "build_candidacy_table.py").read_text(encoding="utf-8")
        self.assertIn(f"{worst[0]:,.0f}×", builder)


class NominatorFormTests(unittest.TestCase):
    """The number of distinct nominator surface forms, which four files state.

    `scripts/nominator_report.py` measures it on every run and printed 393
    while three docstrings said 427.
    """

    def test_every_file_states_the_same_count(self):
        sources = {
            "scraper/shared/parties.py": None,
            "scripts/nominator_report.py": None,
            "docs/DATA_GUIDE.md": None,
        }
        counts = set()
        for name in sources:
            text = (REPO_ROOT / name).read_text(encoding="utf-8")
            found = re.findall(r"(\d{3}) (?:measured surface forms|distinct nominator|surface)", text)
            found += re.findall(r"every one of the (\d{3}) measured nominator surface forms", text)
            self.assertTrue(found, f"{name} states no surface-form count")
            counts |= set(found)
        self.assertEqual(len(counts), 1, f"the surface-form count disagrees: {sorted(counts)}")

    def test_the_count_is_the_checked_in_table_of_forms(self):
        """`docs/nominator-forms.tsv` is the measured table, one row per form.

        It is written by `--update` and gated on every run, so it is the
        number the docstrings should be quoting.
        """
        import importlib.util

        spec = importlib.util.spec_from_file_location(
            "nominator_report", REPO_ROOT / "scripts" / "nominator_report.py"
        )
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        forms = module.read_forms_table(REPO_ROOT / module.FORMS_TABLE)
        self.assertTrue(forms, "docs/nominator-forms.tsv is missing or empty")
        stated = re.search(
            r"(\d{3}) measured surface forms",
            (REPO_ROOT / "scraper" / "shared" / "parties.py").read_text(encoding="utf-8"),
        )
        self.assertIsNotNone(stated)
        self.assertEqual(int(stated.group(1)), len(forms))


if __name__ == "__main__":
    unittest.main()
