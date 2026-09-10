"""The write and read paths every record passes through (issue #153).

Two rules, and both were broken in the same way: a half-finished write left a
file that counted as done, and a half-finished file read as an empty one.

`write_json` has landed the corpus atomically since issue #95 — serialize,
then `os.replace` — because the runners resume on a record's existence. But
`index.json`, the one file in the *fetch* path, was written with a plain
`write_text` as the last step in 23 modules, and 47 JSON writes across the
scrapers and `scripts/` bypassed the atomic writer altogether.

And the parse stage answered `{}` for an `index.json` that was absent or
would not parse, in eight copies of one function, so a truncated fetch
produced a record that looks complete and is not.
"""

from __future__ import annotations

import ast
import errno
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from scraper.shared.files import load_candidate_index, write_json

REPO_ROOT = Path(__file__).resolve().parents[1]


class WriteJsonTests(unittest.TestCase):
    def test_it_writes_and_leaves_no_temporary(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "nested" / "a.json"
            write_json(path, {"a": 1})
            self.assertEqual(json.loads(path.read_text(encoding="utf-8")), {"a": 1})
            self.assertEqual([p.name for p in path.parent.iterdir()], ["a.json"])

    def test_a_failed_write_leaves_the_previous_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "a.json"
            write_json(path, {"a": 1})
            with mock.patch.object(os, "replace", side_effect=OSError("disk full")):
                with self.assertRaises(OSError):
                    write_json(path, {"a": 2})
            self.assertEqual(json.loads(path.read_text(encoding="utf-8")), {"a": 1})

    def test_the_indent_is_a_parameter_so_a_one_space_file_stays_one_space(self):
        # `scraper/shared/vietovardziai.json` and `scraper/parties.json` are
        # checked in at one space. The point of routing them here is the
        # atomicity, not the layout (issue #153).
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "a.json"
            write_json(path, {"a": [1]}, indent=1)
            self.assertEqual(path.read_text(encoding="utf-8"), '{\n "a": [\n  1\n ]\n}\n')
            write_json(path, {"a": [1]})
            self.assertEqual(path.read_text(encoding="utf-8"), '{\n  "a": [\n    1\n  ]\n}\n')


class LoadCandidateIndexTests(unittest.TestCase):
    """A truncated `index.json` used to read as an empty one.

    Measured on the tracked 2023 fixture `mykolas-majauskas-2420485` with its
    5,666-byte index truncated to 4,000: the parse wrote a record, reported
    zero anomalies, and lost `kandidatavimas`, the whole 29,894-character
    campaign section and `source.candidateSourceUrl`, while `candidateName`
    fell back to the page's shouted heading. 28 modules read this file,
    covering 54,711 of the corpus's 113,073 records.
    """

    def test_a_good_index_comes_back(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            payload = {"candidate": {"candidateId": "x", "url": "https://www.vrk.lt/x"}}
            (directory / "index.json").write_text(json.dumps(payload), encoding="utf-8")
            self.assertEqual(load_candidate_index(directory), payload)

    def test_an_absent_index_raises_the_error_the_runner_records(self):
        # `FileNotFoundError` is what `anketa.html`'s absence already raises,
        # and what the runner turns into a recorded CandidateParseFailed.
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(FileNotFoundError) as raised:
                load_candidate_index(Path(tmp))
            self.assertEqual(raised.exception.errno, errno.ENOENT)
            self.assertIn("index.json", str(raised.exception.filename))

    def test_a_truncated_index_raises_instead_of_reading_as_empty(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            whole = json.dumps({"candidate": {"candidateId": "x"}, "tabSamples": [1, 2, 3]})
            (directory / "index.json").write_text(whole[: len(whole) * 2 // 3], encoding="utf-8")
            with self.assertRaises(json.JSONDecodeError):
                load_candidate_index(directory)

    def test_a_json_document_that_is_not_an_object_raises(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            (directory / "index.json").write_text("[1, 2, 3]", encoding="utf-8")
            with self.assertRaises(ValueError):
                load_candidate_index(directory)

    def test_the_eight_copies_are_one_function_now(self):
        # Eight modules defined this, all eight answering `{}` either way.
        defining = [
            path
            for path in sorted(REPO_ROOT.glob("scraper/**/*.py"))
            if "def _load_candidate_meta" in path.read_text(encoding="utf-8")
        ]
        self.assertEqual(defining, [])


class NoUnguardedJsonWriteTests(unittest.TestCase):
    """`write_text(json.dumps(...))` is the shape that broke, so nothing
    writes JSON that way any more (issue #153).

    Static, because the point is the next backfill: two scripts
    (`backfill_archive_birthplaces.py`, `reshape_1997_education.py`, 950 and
    6,386 records) had grown their own non-atomic record write while every
    other one used `write_json`, and the fetch path's `index.json` write did
    the same in 23 modules.
    """

    #: Where a non-atomic JSON write would matter: the scrapers and the
    #: scripts that rewrite records. Tests and docs are not gated.
    ROOTS = ("scraper", "scripts")

    def _offenders(self) -> list[str]:
        offenders = []
        for root in self.ROOTS:
            for path in sorted((REPO_ROOT / root).rglob("*.py")):
                tree = ast.parse(path.read_text(encoding="utf-8"))
                for node in ast.walk(tree):
                    if not (
                        isinstance(node, ast.Call)
                        and isinstance(node.func, ast.Attribute)
                        and node.func.attr == "write_text"
                    ):
                        continue
                    # `write_text(json.dumps(...) + "\n")` — the argument is
                    # a BinOp whose left side is the dumps call, or the call
                    # itself.
                    argument = node.args[0] if node.args else None
                    if isinstance(argument, ast.BinOp):
                        argument = argument.left
                    if (
                        isinstance(argument, ast.Call)
                        and isinstance(argument.func, ast.Attribute)
                        and argument.func.attr == "dumps"
                    ):
                        offenders.append(
                            f"{path.relative_to(REPO_ROOT)}:{node.lineno}"
                        )
        return offenders

    def test_nothing_writes_json_through_write_text(self):
        self.assertEqual(
            self._offenders(),
            [],
            "use scraper.shared.files.write_json: a write that dies halfway must"
            " leave the previous file or nothing, never a truncated one that"
            " counts as done",
        )

    def test_no_module_carries_an_invalid_escape_sequence(self):
        # Free, given the parse above, and it found one: a `\\S` in a plain
        # docstring, which Python already deprecates and will make an error.
        import warnings

        offenders = []
        for root in (*self.ROOTS, "tests"):
            for path in sorted((REPO_ROOT / root).rglob("*.py")):
                with warnings.catch_warnings(record=True) as caught:
                    warnings.simplefilter("always")
                    ast.parse(path.read_text(encoding="utf-8"))
                offenders += [
                    f"{path.relative_to(REPO_ROOT)}: {w.message}"
                    for w in caught
                    if issubclass(w.category, (DeprecationWarning, SyntaxWarning))
                ]
        self.assertEqual(offenders, [])


if __name__ == "__main__":
    unittest.main()
