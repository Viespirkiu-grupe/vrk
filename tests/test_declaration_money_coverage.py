"""A guard on the shape of defect that issue #81 was.

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
