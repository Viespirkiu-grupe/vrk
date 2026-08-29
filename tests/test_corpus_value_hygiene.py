"""The value rules, checked against the corpus rather than against examples.

`tests/test_shared_values.py` pins what `scraper/shared/values.py` does.
This pins that every election actually goes through it — which is the failure
mode issue #101 was written about. Each era owns its parser, so a rule wired
into six normalizers and not the seventh is invisible: the seventh election's
records look like every other election's until you count them. That is how
`2020-seimo` shipped an election of null income (#81) and how eight copies of
the declaration row table drifted apart (#98).

So this walks `data/` and asserts the invariants hold everywhere, not on a
sample. It costs about a minute and skips entirely on a checkout with no
corpus — which is every CI run, since `data/` is gitignored.

The two counts pinned as exact numbers are the ones that cannot go to zero:
`U+FFFD` survives in values where VRK itself destroyed the character (see
`scraper/shared/values.py`), and the lowercase-uppercase junctions that look
like lost line breaks are `VšĮ`, company names and VRK's own typing. Both are
pinned so that a *rise* is a finding, and both are documented in
docs/DATA_GUIDE.md's traps.
"""

import json
import re
import unittest
from collections import Counter, defaultdict
from pathlib import Path

import local_data

REPO_ROOT = Path(__file__).resolve().parents[1]
DATA_ROOT = REPO_ROOT / "data"

TRAILING_SEPARATOR = re.compile(r"[,;]\s*$")
REPLACEMENT_CHARACTER = "�"

# A lowercase letter immediately followed by an uppercase one, outside the URL
# and file-path values where camelCase is VRK's own naming.
GLUED = re.compile(r"[a-ząčęėįšųūž][A-ZĄČĘĖĮŠŲŪŽ]")
URLISH = re.compile(r"https?://|www\.|\.html?$|\.jpe?g$|\.png$|\.pdf$|^/")

#: Row columns that hold a money figure and must never be a string again.
MONEY_COLUMNS = ("sandorio-suma", "sandorio-suma-lt", "suma-skaiciais")

#: The comma-headed columns, which are two values and must not come back as one.
PAIRED_COLUMNS = ("dovana-data", "paslauga-data")

#: Values still carrying the replacement character, measured 2026-08-29. VRK
#: serves it: fetching a 2004 page live returns U+FFFD in its own bytes. These
#: are the ones with no closing quote to prove what the character stood for --
#: 9 in 2000-seimo, 9 in 2004-seimo, 2 in 2004-ep.
REPLACEMENT_CHARACTER_VALUES = 20

#: Values with a lowercase-uppercase junction, measured 2026-08-29. 13,158 of
#: them are the legal-form abbreviation `VšĮ`; the rest are company names and
#: VRK's typing. Not a parsing defect -- see docs/DATA_GUIDE.md.
#: Issue #100 raised the pin by 59: the recovered 2008 workplace lines carry
#: 58 more `VšĮ`-style junctions and the 2000 municipal family split one
#: child's name, all of them VRK's own spelling in fields that were dropped
#: before, not new gluing.
GLUED_VALUES = 20710


def _leaves(node, path, out):
    if isinstance(node, dict):
        for key, value in node.items():
            _leaves(value, f"{path}.{key}" if path else key, out)
    elif isinstance(node, list):
        for value in node:
            _leaves(value, f"{path}[]", out)
    else:
        out.append((path, node))


class CorpusValueHygieneTests(unittest.TestCase):
    """One walk of `data/`, several invariants read off it."""

    scan = None

    @classmethod
    def setUpClass(cls):
        local_data.require(DATA_ROOT)
        if CorpusValueHygieneTests.scan is not None:
            return

        dangling = Counter()
        money_strings = Counter()
        paired = Counter()
        replacement_only = Counter()
        replacement_values = 0
        glued_values = 0
        numeric_types = defaultdict(set)

        for election_dir in sorted(p for p in DATA_ROOT.iterdir() if p.is_dir()):
            election = election_dir.name
            for record_path in election_dir.glob("*.json"):
                record = json.loads(record_path.read_text(encoding="utf-8"))
                values = []
                _leaves(record.get("normalized"), "", values)
                for path, value in values:
                    leaf = path.rsplit(".", 1)[-1]
                    if isinstance(value, bool) or value is None:
                        continue
                    if isinstance(value, (int, float)):
                        numeric_types[(election, path)].add(type(value).__name__)
                        continue
                    if not isinstance(value, str):
                        continue
                    if leaf in MONEY_COLUMNS:
                        money_strings[(election, path)] += 1
                    if leaf in PAIRED_COLUMNS:
                        paired[(election, path)] += 1
                    if TRAILING_SEPARATOR.search(value):
                        dangling[(election, path)] += 1
                    if REPLACEMENT_CHARACTER in value:
                        replacement_values += 1
                        if not value.strip(f" {REPLACEMENT_CHARACTER}"):
                            replacement_only[(election, path)] += 1
                    if not URLISH.search(value) and GLUED.search(value):
                        glued_values += 1

        CorpusValueHygieneTests.scan = {
            "dangling": dangling,
            "money_strings": money_strings,
            "paired": paired,
            "replacement_only": replacement_only,
            "replacement_values": replacement_values,
            "glued_values": glued_values,
            "mixed_numeric": {
                key: types for key, types in numeric_types.items() if len(types) > 1
            },
        }

    def test_no_value_ends_in_a_separator_that_separates_nothing(self):
        self.assertEqual(dict(self.scan["dangling"]), {})

    def test_no_money_column_is_still_a_string(self):
        self.assertEqual(dict(self.scan["money_strings"]), {})

    def test_no_column_holds_both_an_int_and_a_float(self):
        # Money is a float everywhere; a count is an int everywhere. What a
        # column may not be is both, which 225 money columns were before
        # issue #101 -- 4.2 million values sat in one.
        self.assertEqual(self.scan["mixed_numeric"], {})

    def test_the_comma_headed_columns_are_split_into_their_pairs(self):
        self.assertEqual(dict(self.scan["paired"]), {})

    def test_no_value_is_nothing_but_a_replacement_character(self):
        self.assertEqual(dict(self.scan["replacement_only"]), {})

    def test_the_surviving_replacement_characters_do_not_multiply(self):
        # VRK's own bytes carry these; the count is pinned so a rise is a
        # finding rather than a shrug.
        self.assertEqual(self.scan["replacement_values"], REPLACEMENT_CHARACTER_VALUES)

    def test_the_lowercase_uppercase_junctions_do_not_multiply(self):
        # `VšĮ`, `UAB "inChase"`, `kAUNO` -- VRK's, not ours. Pinned for the
        # same reason: a jump here would mean a parser started gluing words.
        self.assertEqual(self.scan["glued_values"], GLUED_VALUES)


if __name__ == "__main__":
    unittest.main()
