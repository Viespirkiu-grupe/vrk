"""`scraper/shared/anketa_cells.prompt_text` reads what the helper it replaced read.

Three election modules carried a byte-identical `_build_prompt_text` that
serialized each questionnaire cell and re-parsed it with lxml, to get a copy
it could cut the answer and the detail tables out of: 41 BeautifulSoup
constructions per record, 31 % of a 2020-seimo parse (issue #154). The
shared walk has to return the same string for every cell a parser hands it,
so the old helper is kept below as the oracle and run against every `<td>`
of every anketa page in the fixture tree.
"""

import unittest
from pathlib import Path

from bs4 import BeautifulSoup

from scraper.shared.anketa_cells import prompt_text

REPO_ROOT = Path(__file__).resolve().parents[1]


def _legacy_prompt_text(cell) -> str:
    """The helper as `seimo_2016`, `seimo_2020` and `seimo_2024` each had it."""
    clone_cell = BeautifulSoup(str(cell), "lxml").find("td")
    if clone_cell is None:
        return ""
    for nested_table in clone_cell.find_all("table"):
        nested_table.decompose()
    for bold in clone_cell.find_all("b"):
        bold.decompose()
    return " ".join(clone_cell.get_text(" ", strip=True).split())


def _cell(html: str):
    return BeautifulSoup(f"<table><tr>{html}</tr></table>", "lxml").find("td")


CASES = {
    "the answer in bold": (
        "<td>1. Gimimo data: <b>1970-01-01</b></td>",
        "1. Gimimo data:",
    ),
    "a nested detail table": (
        "<td>9.2. Ar esate pripažintas kaltu? <b>Taip</b>"
        "<table><tr><td>9.2.1. Nuosprendžio data</td><td>1995-04-15</td></tr></table></td>",
        "9.2. Ar esate pripažintas kaltu?",
    ),
    "bold inside other markup": (
        "<td><span>Partija: <b><a href='#'>X</a></b></span> (nuo 2004)</td>",
        "Partija: (nuo 2004)",
    ),
    "a comment and a no-break space": (
        "<td>\n  Pilietybė:\xa0<!-- a comment -->\n  <b>LT</b>  </td>",
        "Pilietybė:",
    ),
    "a cell that is all answer": ("<td><b>Taip</b></td>", ""),
    "a table inside the bold": (
        "<td>Q <b>A<table><tr><td>row</td></tr></table></b> tail</td>",
        "Q tail",
    ),
}


class PromptTextTests(unittest.TestCase):
    def test_the_question_is_the_cell_without_its_answer(self) -> None:
        for name, (html, expected) in CASES.items():
            with self.subTest(name):
                self.assertEqual(prompt_text(_cell(html)), expected)

    def test_each_case_reads_what_the_old_helper_read(self) -> None:
        for name, (html, _) in CASES.items():
            with self.subTest(name):
                cell = _cell(html)
                self.assertEqual(prompt_text(cell), _legacy_prompt_text(cell))

    def test_the_cell_is_not_modified(self) -> None:
        # The old helper worked on a copy because it decomposed; the walk
        # must not need one.
        cell = _cell(CASES["a nested detail table"][0])
        before = str(cell)
        prompt_text(cell)
        self.assertEqual(str(cell), before)


class FixtureEquivalenceTests(unittest.TestCase):
    """Every `<td>` of every anketa page the checkout holds, old helper against new."""

    def test_every_anketa_cell_in_the_fixtures_reads_as_it_did(self) -> None:
        pages = sorted((REPO_ROOT / "samples" / "html").glob("*/*/anketa.html"))
        if not pages:
            self.skipTest("no anketa.html fixture in this checkout")
        cells = 0
        mismatches: list[str] = []
        for page in pages:
            soup = BeautifulSoup(page.read_text(encoding="utf-8"), "lxml")
            for cell in soup.find_all("td"):
                cells += 1
                new, old = prompt_text(cell), _legacy_prompt_text(cell)
                if new != old and len(mismatches) < 5:
                    mismatches.append(f"{page.relative_to(REPO_ROOT)}: {old!r} became {new!r}")
        self.assertGreater(cells, 0)
        self.assertEqual(mismatches, [], f"{len(pages)} pages, {cells} cells")


if __name__ == "__main__":
    unittest.main()
