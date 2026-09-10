"""The offline backfills, on a temporary corpus of one record each (issue #163).

`coverage run --source=scraper,scripts -m pytest` over the whole local suite
reported six scripts at 0 % — 358 statements, none executed. Two of the six
got their first tests earlier in this batch (`serve_dashboard.py` with issue
#160, `build_place_vocabulary.py` with #157); these are the rest of the
offline passes, each exercised end to end over a `data/` tree built here.

Every one of them rewrites records in place, so the two claims worth pinning
are the same for all: it changes what it says it changes, and a second run is
a no-op. A backfill that is not idempotent cannot be re-run over a corpus
that was partly done, which is exactly how these get used.
"""

from __future__ import annotations

import contextlib
import importlib.util
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def load(name: str):
    """A script as a module, without importing the package it lives beside."""
    spec = importlib.util.spec_from_file_location(name, REPO_ROOT / "scripts" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@contextlib.contextmanager
def working_directory(path: Path):
    previous = os.getcwd()
    os.chdir(path)
    try:
        yield
    finally:
        os.chdir(previous)


def write_record(directory: Path, candidate_id: str, election_id: str, record: dict) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{candidate_id}-{election_id}.json"
    path.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


class ArchiveBirthplaceTests(unittest.TestCase):
    """`backfill_archive_birthplaces.py`: the biography's opening sentence.

    The card publishes the field on most of the family (it hides inside a
    malformed `<!--sql format>` comment, which issue #69 taught the parser to
    read); this recovers it from prose for the records where it does not, and
    marks the weaker source.
    """

    ELECTION = "1996-spalio-20-seimo"

    def _run(self, record: dict, *, dry_run: bool = False) -> dict:
        module = load("backfill_archive_birthplaces")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path = write_record(root / "data" / self.ELECTION, "kandidatas", self.ELECTION, record)
            with working_directory(root):
                module.DATA_ROOT = Path("data")
                sys.argv = ["backfill_archive_birthplaces"] + (["--dry-run"] if dry_run else [])
                self.assertEqual(module.main(), 0)
            return json.loads(path.read_text(encoding="utf-8"))

    RECORD = {
        "electionId": ELECTION,
        "candidateId": "kandidatas",
        "candidateName": "Vardenis Pavardenis",
        "normalized": {
            "profilis": {"vardas-pavarde": "Vardenis Pavardenis"},
            "anketa": {},
            "biografija": {"tekstas": "Gimė 1950 m. sausio 1 d. Kaune. Dirbo mokytoju."},
        },
    }

    def test_the_place_and_its_source_marker_land_together(self):
        anketa = self._run(json.loads(json.dumps(self.RECORD)))["normalized"]["anketa"]
        self.assertEqual(anketa.get("gimimo-vieta"), "Kaunas")
        self.assertEqual(anketa.get("gimimo-vietos-saltinis"), "biografijos-tekstas")

    def test_a_dry_run_writes_nothing(self):
        record = json.loads(json.dumps(self.RECORD))
        self.assertEqual(self._run(record, dry_run=True)["normalized"]["anketa"], {})

    def test_a_place_the_card_published_is_left_alone(self):
        record = json.loads(json.dumps(self.RECORD))
        record["normalized"]["anketa"]["gimimo-vieta"] = "Vilnius"
        anketa = self._run(record)["normalized"]["anketa"]
        self.assertEqual(anketa["gimimo-vieta"], "Vilnius")
        self.assertNotIn("gimimo-vietos-saltinis", anketa)

    def test_a_second_run_is_a_no_op(self):
        once = self._run(json.loads(json.dumps(self.RECORD)))
        twice = self._run(once)
        self.assertEqual(once, twice)


class EducationReshapeTests(unittest.TestCase):
    """`reshape_1997_education.py`: the bare string becomes the corpus shape.

    `issilavinimas` is `{"aprasas", "irasai"}` everywhere else, and the two
    1997 municipal elections published one level as a bare string — the only
    concept in the corpus with two shapes.
    """

    ELECTION = "1997-kovo-23-savivaldybiu-tarybu"

    def _run(self, record: dict, *, dry_run: bool = False) -> dict:
        module = load("reshape_1997_education")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path = write_record(root / "data" / self.ELECTION, "kandidatas", self.ELECTION, record)
            with working_directory(root):
                module.DATA_ROOT = Path("data")
                sys.argv = ["reshape_1997_education"] + (["--dry-run"] if dry_run else [])
                self.assertEqual(module.main(), 0)
            return json.loads(path.read_text(encoding="utf-8"))

    def _record(self, education) -> dict:
        return {
            "electionId": self.ELECTION,
            "candidateId": "kandidatas",
            "candidateName": "Vardenis Pavardenis",
            "normalized": {"anketa": {"issilavinimas": education}},
        }

    def test_a_bare_string_becomes_an_entry_not_a_description(self):
        # The level is a controlled-list answer, so it lands in `irasai` as
        # the entry's `issilavinimas`; `aprasas` is the free-text description
        # these cards do not have, and stays null rather than repeating it.
        after = self._run(self._record("Aukštasis"))
        self.assertEqual(
            after["normalized"]["anketa"]["issilavinimas"],
            {
                "aprasas": None,
                "irasai": [
                    {
                        "issilavinimas": "Aukštasis",
                        "mokymo-istaigos-pavadinimas": None,
                        "specialybe": None,
                        "baigimo-metai": None,
                    }
                ],
            },
        )

    def test_the_corpus_shape_is_left_alone(self):
        shaped = {"aprasas": "Aukštasis", "irasai": [{"pavadinimas": "VU"}]}
        after = self._run(self._record(shaped))
        self.assertEqual(after["normalized"]["anketa"]["issilavinimas"], shaped)

    def test_a_dry_run_writes_nothing(self):
        after = self._run(self._record("Aukštasis"), dry_run=True)
        self.assertEqual(after["normalized"]["anketa"]["issilavinimas"], "Aukštasis")

    def test_a_second_run_is_a_no_op(self):
        once = self._run(self._record("Aukštasis"))
        self.assertEqual(once, self._run(once))


class CardFieldBackfillTests(unittest.TestCase):
    """`backfill_1997_card_fields.py`, whose input is a retained page.

    It replaces `rawData.personal` and `normalized.anketa` from the retained
    `candidate.html` and leaves the declaration alone — which is the whole
    point, since that election's retained tree has no `declaration.html` and
    a full re-parse would drop 5,471 records' income. What is pinned here is
    the path resolution and the guards; the parse itself is the shared
    archive-card parser's own tests.
    """

    def test_it_refuses_a_checkout_with_no_corpus(self):
        module = load("backfill_1997_card_fields")
        with tempfile.TemporaryDirectory() as tmp:
            sys.argv = ["backfill_1997_card_fields", "--repo-root", tmp]
            self.assertEqual(module.main(), 1)

    def test_an_election_with_no_data_directory_is_skipped_not_failed(self):
        module = load("backfill_1997_card_fields")
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "data").mkdir()
            sys.argv = ["backfill_1997_card_fields", "--repo-root", tmp, "--dry-run"]
            self.assertEqual(module.main(), 0)

    def test_the_retained_page_is_looked_for_in_both_trees(self):
        module = load("backfill_1997_card_fields")
        election = next(iter(module.SAMPLE_ROOTS))
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.assertIsNone(module.candidate_html_path(root, election, "kandidatas"))
            fixture = root / "samples" / "html" / election / "kandidatas"
            fixture.mkdir(parents=True)
            (fixture / "candidate.html").write_text("<html></html>", encoding="utf-8")
            self.assertEqual(
                module.candidate_html_path(root, election, "kandidatas"),
                fixture / "candidate.html",
            )
            full = root / "samples-full" / election / "kandidatas"
            full.mkdir(parents=True)
            (full / "candidate.html").write_text("<html></html>", encoding="utf-8")
            # The full tree wins where both exist: it is the whole field, and
            # the fixture tree is a subset of it.
            self.assertEqual(
                module.candidate_html_path(root, election, "kandidatas"),
                full / "candidate.html",
            )


class NominatorFormsTableTests(unittest.TestCase):
    """`nominator_report.py`'s checked-in table of measured surface forms."""

    def test_the_table_round_trips(self):
        module = load("nominator_report")
        from collections import Counter

        counts = Counter({"Tėvynės sąjunga": 3, "Išsikėlė pats": 1})
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "forms.tsv"
            module.write_forms_table(path, counts)
            self.assertEqual(module.read_forms_table(path), set(counts))
            # The header is not a form, and a comment line is not either.
            text = path.read_text(encoding="utf-8")
            self.assertTrue(text.startswith("#") or text.startswith("form\t"))

    def test_an_absent_table_reads_as_empty_rather_than_raising(self):
        module = load("nominator_report")
        self.assertEqual(module.read_forms_table(Path("/nonexistent/forms.tsv")), set())

    def test_the_checked_in_table_is_the_one_the_docstrings_count(self):
        module = load("nominator_report")
        forms = module.read_forms_table(REPO_ROOT / module.FORMS_TABLE)
        self.assertEqual(len(forms), 393)


if __name__ == "__main__":
    unittest.main()
