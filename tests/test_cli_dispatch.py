"""Every election-id branch of every `scraper/cli.py` dispatcher, exercised.

Issue #157: five dispatchers in `scraper/cli.py` are 55-branch `if
election_id == ...` chains — 275 bindings from an election id to the one
function of the one module that belongs to it — and a full suite run
executed 3 of them. `_parse_anketa_samples_for_election` reached three
election ids and the other four dispatchers reached none, because every
test that parses a fixture calls its module's parser directly. `cli.py`
was 42 % covered, the largest gap in the repository, with four dispatchers
at exactly one executed statement each.

The classic copy-paste error in such a chain — `EP_2019_ELECTION_ID`
returning `parse_ep_2024_anketa_samples` — left the suite at 1,826 passed,
zero failures, while the mutated dispatcher wrote six records named
`<candidate>-2024-ep.json` carrying `electionId: "2024-ep"` and differing
in content from every stored 2019-ep record.

So: no fixture, no network, no parse. Each alias `cli.py` imported from an
election module is replaced by a stub returning its own name, the
dispatcher is called with one election id, and the name that comes back has
to belong to *that* election's module. The two maps the assertion needs are
each read from a source that is not the dispatcher:

* alias → module, from the AST of `cli.py`'s own `from
  scraper.elections.<module>.… import … as <alias>` statements. The alias
  names do not follow the module names (`seimo_2016`'s parser is imported
  as `parse_2016_anketa_samples`), so the import is the only honest source.
* election id → module, from each `scraper/elections/<module>/sitemap.py`'s
  `ELECTION_ID`, which is what the records themselves carry.

`_build_results_for_election` is not tested here: it is already a dict
(`_RESULTS_BUILDERS`), where a wrong wiring is a wrong key rather than a
wrong branch. `test_results_builders_are_wired_to_their_own_modules` pins
that mapping the same way.
"""

from __future__ import annotations

import ast
import importlib
import sys
import unittest
from pathlib import Path
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scraper import cli  # noqa: E402

#: alias in cli.py -> the election module it was imported from.
ALIAS_MODULE: dict[str, str] = {}
for _node in ast.walk(ast.parse((REPO_ROOT / "scraper" / "cli.py").read_text(encoding="utf-8"))):
    if isinstance(_node, ast.ImportFrom) and (_node.module or "").startswith("scraper.elections."):
        _module = _node.module.split(".")[2]
        for _alias in _node.names:
            ALIAS_MODULE[_alias.asname or _alias.name] = _module

#: election id -> the module that owns it, from the module's own sitemap.
ID_MODULE: dict[str, str] = {}
for _package in sorted((REPO_ROOT / "scraper" / "elections").iterdir()):
    if not _package.is_dir() or _package.name.startswith("_"):
        continue
    ID_MODULE[importlib.import_module(f"scraper.elections.{_package.name}.sitemap").ELECTION_ID] = (
        _package.name
    )

#: The five if-chains, with the id list each is reachable with from argparse.
DISPATCHERS = (
    ("_fetch_listing_sample_for_election", cli.FETCHABLE_ELECTION_IDS),
    ("_build_sitemap_from_sample_for_election", cli.FETCHABLE_ELECTION_IDS),
    ("_fetch_first_candidate_with_tabs_for_election", cli.FETCHABLE_ELECTION_IDS),
    ("_fetch_candidates_with_tabs_for_election", cli.FETCHABLE_ELECTION_IDS),
    ("_parse_anketa_samples_for_election", cli.PARSABLE_ELECTION_IDS),
)


#: The aliases that are functions. `cli.py` imports each module's
#: `ELECTION_ID` by the same mechanism, and those are what the branches
#: *compare against* — stub one and its whole chain falls through.
STUBBABLE = tuple(
    alias
    for alias in sorted(ALIAS_MODULE)
    if callable(getattr(cli, alias, None)) and not isinstance(getattr(cli, alias), str)
)


def _stubbed() -> list[mock._patch]:
    """Every election-module function replaced by a stub returning its name."""
    return [
        mock.patch.object(cli, alias, (lambda name: lambda *a, **k: name)(alias))
        for alias in STUBBABLE
    ]


class DispatchBindings(unittest.TestCase):
    #: What each dispatcher takes beyond the election id. Nothing here is
    #: read: every branch passes them straight to the stub.
    EXTRA_ARGS = {
        "_build_sitemap_from_sample_for_election": {"sample_path": None},
        "_fetch_first_candidate_with_tabs_for_election": {
            "sitemap_path": Path("sitemaps/x.json"),
            "samples_root": Path("samples"),
            "allow_new_samples": False,
        },
        "_fetch_candidates_with_tabs_for_election": {
            "candidate_ids": [],
            "sitemap_path": Path("sitemaps/x.json"),
            "samples_root": Path("samples"),
            "allow_new_samples": False,
        },
        "_parse_anketa_samples_for_election": {
            "candidate_ids": None,
            "samples_root": Path("samples"),
            "output_root": Path("data"),
        },
    }

    def _called_alias(self, dispatcher: str, election_id: str) -> str:
        patches = _stubbed()
        for patch in patches:
            patch.start()
        try:
            # Every branch of all five chains is `return <alias>(...)`, so
            # whatever comes back is the stub's own name.
            return getattr(cli, dispatcher)(
                election_id, **self.EXTRA_ARGS.get(dispatcher, {})
            )
        finally:
            for patch in patches:
                patch.stop()

    def test_every_branch_calls_its_own_modules_function(self) -> None:
        checked = 0
        for dispatcher, ids in DISPATCHERS:
            for election_id in ids:
                with self.subTest(dispatcher=dispatcher, election=election_id):
                    called = self._called_alias(dispatcher, election_id)
                    self.assertIsInstance(
                        called, str, f"{dispatcher} did not return a stubbed alias for {election_id}"
                    )
                    self.assertEqual(
                        ALIAS_MODULE[called],
                        ID_MODULE[election_id],
                        f"{dispatcher}({election_id!r}) calls {called}, which belongs to"
                        f" scraper.elections.{ALIAS_MODULE[called]}, not to"
                        f" scraper.elections.{ID_MODULE[election_id]}",
                    )
                checked += 1
        self.assertEqual(checked, 275, "every id of every dispatcher, or the chains have changed")

    def test_an_unknown_id_is_refused_not_dispatched(self) -> None:
        # An id argparse's `choices` does not gate — a caller inside the
        # process, or a list that has gained an entry the chain has not.
        for dispatcher, _ in DISPATCHERS:
            with self.subTest(dispatcher):
                with self.assertRaises(ValueError):
                    self._called_alias(dispatcher, "2099-neverendum")
        with self.assertRaises(ValueError):
            cli._build_results_for_election("2099-neverendum")

    def test_the_stubs_leave_the_id_constants_alone(self) -> None:
        # `cli.py` imports each module's ELECTION_ID the same way it imports
        # its functions, and the branches compare against those constants:
        # stub one and its whole chain falls through to the ValueError. The
        # first draft of this test did exactly that, on all 275 branches.
        self.assertTrue(STUBBABLE)
        for election_id in cli.PARSABLE_ELECTION_IDS:
            self.assertNotIn(election_id, STUBBABLE)
        patches = _stubbed()
        for patch in patches:
            patch.start()
        try:
            self.assertEqual(cli.SEIMO_2016_ELECTION_ID, "2016-seimo")
        finally:
            for patch in patches:
                patch.stop()

    def test_the_two_maps_cover_the_dispatched_ids(self) -> None:
        # The assertion above is vacuous for an id missing from either map.
        for dispatcher, ids in DISPATCHERS:
            for election_id in ids:
                with self.subTest(dispatcher=dispatcher, election=election_id):
                    self.assertIn(election_id, ID_MODULE)

    def test_results_builders_are_wired_to_their_own_modules(self) -> None:
        # The dict form of the same fact. `_RESULTS_BUILDERS`' values are the
        # imported aliases themselves, so the alias map answers directly.
        by_function = {getattr(cli, alias): alias for alias in ALIAS_MODULE if hasattr(cli, alias)}
        for election_id, builder in cli._RESULTS_BUILDERS.items():
            with self.subTest(election_id):
                self.assertEqual(ALIAS_MODULE[by_function[builder]], ID_MODULE[election_id])
        self.assertEqual(
            sorted(cli._RESULTS_BUILDERS), sorted(cli.RESULTS_ELECTION_IDS), "the list and the dict disagree"
        )


class ElectionIdLists(unittest.TestCase):
    """The three id lists, pinned to what they are lists *of* (issue #157).

    Only `FETCHABLE_ELECTION_IDS` was pinned to the registry. A missing
    `PARSABLE` entry makes `reparse_diff.py` skip that election forever —
    silently, because the script iterates the list; a missing `RESULTS`
    entry makes the runner skip build-results, and 79,952 records (70.7 %)
    take their elected status from that join.
    """

    REGISTRY_IDS = set(ID_MODULE)

    def test_every_registered_election_is_parsable(self) -> None:
        self.assertEqual(self.REGISTRY_IDS, set(cli.PARSABLE_ELECTION_IDS))
        self.assertEqual(
            len(cli.PARSABLE_ELECTION_IDS), len(set(cli.PARSABLE_ELECTION_IDS)), "duplicate id"
        )

    def test_every_module_with_a_results_builder_is_in_the_results_list(self) -> None:
        with_results = {
            election_id: module
            for election_id, module in ID_MODULE.items()
            if (REPO_ROOT / "scraper" / "elections" / module / "results.py").exists()
        }
        self.assertEqual(set(with_results), set(cli.RESULTS_ELECTION_IDS))
        self.assertEqual(
            len(cli.RESULTS_ELECTION_IDS), len(set(cli.RESULTS_ELECTION_IDS)), "duplicate id"
        )


if __name__ == "__main__":
    unittest.main()
