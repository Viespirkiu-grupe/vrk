"""Guards on the two shapes of declaration loss this corpus has had.

Issue #81 was a whole election's income arriving as `null`; issue #98 was a
published figure with nowhere in `normalized` to go. Both were invisible: the
keys were present, the values were plausible, and `rawData` held everything.

`2020-seimo` shipped with income `null` on all 1,753 of its declaration
records, an empty `anomalies.jsonl` and a green suite: the keys were all
present, the values were all `null`, and every fixture still passed. What made
it visible was comparing the election against its neighbours -- 0 % fill on a
key that is at 97.8-100 % everywhere else in the corpus.

So that comparison is the test. It is deliberately narrow: only the two mapped
money keys, and only the 0 %-against-a-healthy-corpus case. The full
field-coverage report over every mapped concept, with a checked-in baseline and
a drift threshold, is issue #85.

The corpus is gitignored, so this skips when `data/` is absent.
"""

import json
import re
import statistics
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
DATA_ROOT = REPO_ROOT / "data"

DECLARATION_KEY = "turto-ir-pajamu-deklaracijos"
MONEY_KEYS = ("gautos-pajamos", "sumoketas-pajamu-mokestis")

# Records per election, by sorted filename. The rule below only asks whether an
# election is at zero while the corpus is healthy, and an election that
# normalizes nothing normalizes nothing in any sample of it, so the whole
# 113,046-record corpus does not have to be read to answer that.
SAMPLE_SIZE = 250

# Below this many sampled declarations an election is too small to read a rate
# off; the smallest in the corpus today holds a single record.
MIN_DECLARATIONS = 5

HEALTHY_NEIGHBOUR_RATE = 90.0


def _fill_rates() -> dict[str, tuple[int, dict[str, float]]]:
    rates: dict[str, tuple[int, dict[str, float]]] = {}

    for election_dir in sorted(p for p in DATA_ROOT.iterdir() if p.is_dir()):
        declarations = 0
        non_null = dict.fromkeys(MONEY_KEYS, 0)

        for record_path in sorted(election_dir.glob("*.json"))[:SAMPLE_SIZE]:
            record = json.loads(record_path.read_text(encoding="utf-8"))
            declaration = record.get("normalized", {}).get(DECLARATION_KEY)
            if not isinstance(declaration, dict):
                continue
            declarations += 1
            for key in MONEY_KEYS:
                if declaration.get(key) is not None:
                    non_null[key] += 1

        if declarations >= MIN_DECLARATIONS:
            rates[election_dir.name] = (
                declarations,
                {key: 100.0 * non_null[key] / declarations for key in MONEY_KEYS},
            )

    return rates


class DeclarationMoneyCoverageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        if not DATA_ROOT.is_dir():
            raise unittest.SkipTest("no local corpus — data/ is gitignored")
        cls.rates = _fill_rates()
        if not cls.rates:
            raise unittest.SkipTest("no scraped election holds declaration records")

    def test_no_election_is_alone_at_zero_fill(self) -> None:
        for key in MONEY_KEYS:
            with self.subTest(key=key):
                for election_id, (declarations, election_rates) in self.rates.items():
                    if election_rates[key] > 0:
                        continue

                    neighbours = [
                        rates[key]
                        for other_id, (_, rates) in self.rates.items()
                        if other_id != election_id
                    ]
                    neighbour_rate = statistics.median(neighbours) if neighbours else 0.0
                    self.assertLessEqual(
                        neighbour_rate,
                        HEALTHY_NEIGHBOUR_RATE,
                        f"{election_id}: {key} is null on all {declarations} sampled "
                        f"declarations while the corpus median is {neighbour_rate:.1f} % — "
                        "the values are most likely in rawData and dropped in normalization",
                    )


if __name__ == "__main__":
    unittest.main()


# A printed amount: digits with the era's separators, then the currency. VRK
# drops the leading zero of a sub-euro figure ("<b>,53 Eur</b>" in the page
# source), so the pattern allows one and the reader restores it — the parsers
# do the same, and 102 declaration values corpus-wide are written that way.
PRINTED_AMOUNT = re.compile(
    r"(-?(?:\d[\d\s\u00a0]*)?(?:[.,]\d{1,2})?)\s*(?:Lt|Eur)\b\.?", re.IGNORECASE
)

# Where a declaration item states a figure. `value` everywhere; `income` and
# `tax` on the 2004 pages, whose income table gives each form a row of its own.
AMOUNT_FIELDS = ("value", "income", "tax")


def _printed_amounts(text: object) -> list[float]:
    amounts = []
    for printed in PRINTED_AMOUNT.findall(str(text or "")):
        compact = re.sub(r"[\s\u00a0]", "", printed).replace(",", ".")
        compact = re.sub(r"^(-?)\.", r"\g<1>0.", compact)
        try:
            amounts.append(float(compact))
        except ValueError:
            pass
    return amounts


def _stored_numbers(value: object) -> list[float]:
    if isinstance(value, bool):
        return []
    if isinstance(value, (int, float)):
        return [float(value)]
    if isinstance(value, dict):
        return [n for item in value.values() for n in _stored_numbers(item)]
    if isinstance(value, list):
        return [n for item in value for n in _stored_numbers(item)]
    return []


class NothingPublishedIsDroppedTests(unittest.TestCase):
    """Issue #98's acceptance criterion, as a test.

    No non-zero figure a declarations page prints may be absent from the
    record's normalized block — under a value key, in a `deklaracijos` entry,
    in `pajamos-pagal-forma` or under `sutuoktinio`. Four losses used to fail
    it: the four GPM lines nothing mapped, the spouse declaration that
    displaced the candidate's own, the section printed twice and summed, and
    the 2007 income sentence whose tax figure is missing and which was
    therefore refused whole.

    Sampled per election for speed; the full 84,402-record sweep was clean when
    this landed.
    """

    @classmethod
    def setUpClass(cls) -> None:
        if not DATA_ROOT.is_dir():
            raise unittest.SkipTest("no local corpus — data/ is gitignored")

    def test_no_published_figure_is_missing_from_normalized(self) -> None:
        checked = 0
        dropped: list[str] = []
        for election_dir in sorted(p for p in DATA_ROOT.iterdir() if p.is_dir()):
            for record_path in sorted(election_dir.glob("*.json"))[:SAMPLE_SIZE]:
                record = json.loads(record_path.read_text(encoding="utf-8"))
                raw = (record.get("rawData") or {}).get("turtoIrPajamuDeklaracijos")
                stored = (record.get("normalized") or {}).get(DECLARATION_KEY)
                # Only the eras that publish the declaration as titled sections:
                # the 1996-2003 parsers write their reading straight into
                # rawData, so there is nothing to compare it against.
                if not isinstance(raw, dict) or not isinstance(stored, dict):
                    continue
                if not isinstance(raw.get("sections"), list):
                    continue
                checked += 1

                printed = [
                    amount
                    for section in raw["sections"]
                    if isinstance(section, dict)
                    for item in (section.get("items") or [])
                    if isinstance(item, dict)
                    for field in AMOUNT_FIELDS
                    for amount in _printed_amounts(item.get(field))
                ]
                normalized = set(_stored_numbers(stored))
                dropped.extend(
                    f"{record_path.name}: the page states {amount:g} and the "
                    "normalized declaration does not"
                    for amount in printed
                    if amount and amount not in normalized
                )

        self.assertGreater(checked, 0, "no sectioned declaration record was reached")
        self.assertEqual(dropped[:10], [], f"{len(dropped)} published figure(s) dropped")
