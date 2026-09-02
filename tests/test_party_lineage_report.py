"""scripts/party_lineage_report.py: the continuity rule on a synthetic index,
and the real run whenever the index has been built.

The registry's `predecessors` (issue #123) say which organisation another
continues; the report finds the pairs a name cannot -- two committees that
share no word and sixteen candidates -- and holds the registry to explaining
each one. The rule is pinned here on a hand-made people.json: a third of the
smaller side, three persons at least, the earlier list wholly before the
later, and never a local list as a national organisation's predecessor.
"""

from __future__ import annotations

import importlib.util
import json
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
INDEX_PATH = REPO_ROOT / "dashboard" / "people.json"

_spec = importlib.util.spec_from_file_location(
    "party_lineage_report", REPO_ROOT / "scripts" / "party_lineage_report.py"
)
report = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(report)


def _index(lists: dict[str, tuple[str, list[str]]], elections: list[dict]) -> dict:
    """A people.json with one candidacy per (person, list). `lists` maps a
    nominator id to (election id, person ids)."""
    people: dict[str, dict] = {}
    for party_id, (election_id, pids) in lists.items():
        for pid in pids:
            person = people.setdefault(pid, {"pid": pid, "n": pid, "k": f"{pid}|1970-01-01", "e": []})
            person["e"].append({"id": election_id, "c": pid, "p": party_id, "sv": 0})
    return {"elections": elections, "municipalities": ["Jonavos rajono"], "people": list(people.values())}


ELECTIONS = [
    {"id": "2015-kovo-1-savivaldybiu", "date": "2015-03-01", "kind": "savivaldybiu"},
    {"id": "2019-kovo-3-savivaldybiu-tarybu", "date": "2019-03-03", "kind": "savivaldybiu"},
    {"id": "2020-seimo", "date": "2020-10-11", "kind": "seimo"},
    {"id": "2023-kovo-5-savivaldybiu-tarybu-ir-meru", "date": "2023-03-05", "kind": "savivaldybiu"},
]
PEOPLE = [f"p{i}" for i in range(12)]


class ContinuityRuleTests(unittest.TestCase):
    def _pairs(self, lists):
        stats = report.measure(_index(lists, ELECTIONS))
        return [(a, b, shared) for a, b, shared, _ in report.continuity_pairs(stats)]

    def test_a_third_of_the_smaller_list_carried_over_is_a_pair(self):
        # 2019: p0-p8 (9 persons); 2023: p6-p11 (6 persons); shared p6-p8 = 3 = 50 % of 6.
        self.assertEqual(
            self._pairs({
                "komitetas-su-sinkeviciumi-ir-osausku": ("2019-kovo-3-savivaldybiu-tarybu", PEOPLE[:9]),
                "komitetas-musu-jonava": ("2023-kovo-5-savivaldybiu-tarybu-ir-meru", PEOPLE[6:12]),
            }),
            [("komitetas-su-sinkeviciumi-ir-osausku", "komitetas-musu-jonava", 3)],
        )

    def test_fewer_than_three_shared_persons_or_under_a_third_is_not(self):
        # Two shared of a six-person list is a third, but under the floor.
        self.assertEqual(
            self._pairs({
                "a": ("2019-kovo-3-savivaldybiu-tarybu", PEOPLE[:8]),
                "b": ("2023-kovo-5-savivaldybiu-tarybu-ir-meru", PEOPLE[6:12]),
            }),
            [],
        )
        # Three shared of a twelve-person later list is a quarter.
        self.assertEqual(
            self._pairs({
                "a": ("2019-kovo-3-savivaldybiu-tarybu", PEOPLE[:12]),
                "b": ("2023-kovo-5-savivaldybiu-tarybu-ir-meru", PEOPLE[9:12] + ["q1", "q2", "q3", "q4", "q5", "q6", "q7", "q8", "q9"]),
            }),
            [],
        )

    def test_the_earlier_list_must_end_before_the_later_one_starts(self):
        # The same persons, but the "earlier" list also stood in 2023.
        self.assertEqual(
            self._pairs({
                "a": ("2019-kovo-3-savivaldybiu-tarybu", PEOPLE[:6]),
                "a-again": ("2023-kovo-5-savivaldybiu-tarybu-ir-meru", PEOPLE[:6]),
            }),
            [("a", "a-again", 6)],
        )
        stats = report.measure(_index({
            "a": ("2019-kovo-3-savivaldybiu-tarybu", PEOPLE[:6]),
            "b": ("2023-kovo-5-savivaldybiu-tarybu-ir-meru", PEOPLE[:6]),
        }, ELECTIONS))
        stats["a"]["last"] = "2023-03-05"  # a stood again alongside b
        self.assertEqual(report.continuity_pairs(stats), [])

    def test_a_local_list_is_never_a_national_organisations_predecessor(self):
        # A 2019 committee whose people ran for a Seimas party in 2020 is a
        # career move; a national committee (an EP list) before the same
        # party is a candidate pair.
        self.assertEqual(
            self._pairs({
                "komitetas-x": ("2019-kovo-3-savivaldybiu-tarybu", PEOPLE[:6]),
                "partija-y": ("2020-seimo", PEOPLE[:6]),
            }),
            [],
        )
        national = ELECTIONS + [{"id": "2019-ep", "date": "2019-05-26", "kind": "ep"}]
        stats = report.measure(_index({
            "komitetas-x": ("2019-ep", PEOPLE[:6]),
            "partija-y": ("2020-seimo", PEOPLE[:6]),
        }, national))
        self.assertEqual([(a, b) for a, b, _, _ in report.continuity_pairs(stats)], [("komitetas-x", "partija-y")])


class ClassificationTests(unittest.TestCase):
    """Against the real registry: linked through the chain, reviewed by the
    block, succeeded by another entry, or a finding."""

    def test_linked_reviewed_succeeded_and_unreviewed(self):
        reviewed = report.reviewed_distinct()
        self.assertTrue(reviewed)
        some_reviewed = next(iter(reviewed))
        self.assertEqual(report.classify(("koalicija-vieningas-kaunas", "vieningas-kaunas", 9, 0.47), reviewed)[0], "linked")
        self.assertEqual(report.classify((*some_reviewed, 5, 0.5), reviewed)[0], "reviewed")
        self.assertEqual(
            report.classify(("naujoji-sajunga", "komitetas-kartu-pakruojo-labui", 18, 0.5), reviewed),
            ("succeeded", "continued by darbo-partija"),
        )
        self.assertEqual(report.classify(("lsdp", "komitetas-musu-jonava", 3, 0.4), reviewed)[0], "unreviewed")


@unittest.skipUnless(INDEX_PATH.exists(), "dashboard/people.json not built -- python scripts/build_person_index.py")
class BuiltIndexTests(unittest.TestCase):
    def test_every_continuity_pair_of_the_built_index_is_explained(self):
        index = json.loads(INDEX_PATH.read_text(encoding="utf-8"))
        stats = report.measure(index)
        self.assertEqual(sorted(set(stats) - set(report.entries())), [], "index ids the registry lacks: rebuild it")
        reviewed = report.reviewed_distinct()
        findings = [
            (a, b, shared) for a, b, shared, _ in report.continuity_pairs(stats)
            if report.classify((a, b, shared, 0.0), reviewed)[0] == "unreviewed"
        ]
        self.assertEqual(findings, [], "link these in scraper/parties.json or record them under reviewedDistinct")


if __name__ == "__main__":
    unittest.main()
