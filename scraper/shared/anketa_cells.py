"""The question half of a questionnaire cell.

From 2016 on, VRK's anketa tables put a question and its answer in one
`<td>`: the question as plain text, the answer in `<b>`, and -- when the
answer has rows, a conviction or a list of memberships -- a detail table
nested inside the same cell. Reading the question is reading the cell
without its `<b>` and without its nested tables.

`seimo_2016`, `seimo_2020` and `seimo_2024` each carried a byte-identical
copy of the helper that did this, and three more modules imported the 2016
one. It serialized the cell, re-parsed the string with lxml to get a copy it
could `decompose()` those subtrees out of, and read the copy's text: 41
BeautifulSoup constructions per record, 31 % of a 2020-seimo parse (issue
#154). Walking the cell and stepping over the same subtrees reads the same
strings and builds nothing.
"""

from __future__ import annotations

from collections.abc import Iterator

from bs4 import NavigableString, Tag

#: What a question does not include: the answer, and the answer's rows.
NOT_THE_QUESTION = frozenset({"b", "table"})


def prompt_text(cell: Tag) -> str:
    """The cell's text outside every `<b>` and nested `<table>`, whitespace-normalized.

    Exactly what `get_text(" ", strip=True)` reads from the cell with those
    subtrees removed: the string types the cell counts as text (no comments,
    no script), each stripped, the empty ones dropped, one space between.
    """
    types = cell.interesting_string_types or Tag.MAIN_CONTENT_STRING_TYPES
    return " ".join(" ".join(_question_strings(cell, types)).split())


def _question_strings(tag: Tag, types) -> Iterator[str]:
    for child in tag.children:
        if isinstance(child, Tag):
            if child.name not in NOT_THE_QUESTION:
                yield from _question_strings(child, types)
        elif isinstance(child, NavigableString) and _is_text(child, types):
            stripped = child.strip()
            if stripped:
                yield stripped


def _is_text(string: NavigableString, types) -> bool:
    # bs4 accepts one type or a collection of them, and matches exactly:
    # a Comment is a NavigableString subclass and is not text.
    if isinstance(types, type):
        return type(string) is types
    return type(string) in types
