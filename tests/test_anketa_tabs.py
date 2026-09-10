"""The 2016-on page family's helpers live in `scraper/shared/anketa_tabs.py`.

Until issue #90 they lived in `scraper/elections/seimo_2016/anketa_parser.py`,
and 35 other election modules imported 37 of its names -- 35 of them private,
`_normalize_missing_values`, `_normalize_profile_data` and `_order_dict_keys`
in 27 modules each -- and three more modules reached one of them through
`ep_2019`. A fix to any of them changed every election that read it, from a
file named for one election. The move was a pure one: the re-parse gate and
the fixture hash manifest found no record changed.

These tests keep it that way. Nothing imports the helpers from the 2016 module
again, nothing reaches them through another election module, no shared module
imports an election module, and the most-shared helpers keep doing what they
did the day they moved -- pinned on synthetic inputs, so that changing one is
a decision about 27 elections and not an accident in one.
"""

from __future__ import annotations

import ast
import importlib
import re
import unicodedata
import unittest
from pathlib import Path

from scraper.shared import anketa_tabs
from scraper.shared.anketa_tabs import (
    find_row_by_question_number,
    normalize_missing_values,
    normalize_text_value,
    order_dict_keys,
    parse_nested_campaign_samples,
    resolve_candidate_url,
)
from scraper.shared.files import load_candidate_index

REPO_ROOT = Path(__file__).resolve().parents[1]
ELECTIONS = REPO_ROOT / "scraper" / "elections"
SHARED = REPO_ROOT / "scraper" / "shared"
SEIMO_2016_PARSER = "scraper.elections.seimo_2016.anketa_parser"

#: The 35 private names other election modules imported from the 2016 module
#: when issue #90 moved them, under the public names they have now.
PROMOTED = (
    "extract_answer_text",
    "extract_links",
    "extract_non_empty_text_nodes",
    "extract_table_headers",
    "find_main_content_after_tabnav",
    "find_row_by_prompt_prefix",
    "find_row_by_question_number",
    "load_candidate_meta",
    "normalize_biografija_data",
    "normalize_campaigns",
    "normalize_kita_data",
    "normalize_links",
    "normalize_missing_values",
    "normalize_privaciu_interesu_data",
    "normalize_profile_data",
    "normalize_table_records",
    "normalize_text_value",
    "normalize_turto_ir_pajamu_data",
    "order_dict_keys",
    "parse_anketa_table",
    "parse_biografija_html",
    "parse_eur_amount",
    "parse_kita_html",
    "parse_nested_campaign_samples",
    "parse_nested_table",
    "parse_politines_kampanijos_html",
    "parse_privaciu_interesu_html",
    "parse_profile_table",
    "parse_tabnav",
    "parse_turto_ir_pajamu_html",
    "question_record_rows",
    "row_answer_text",
    "source_key",
    "split_list_value",
    "tag_text",
)
#: The two that were public already and kept their names.
KEPT = ("normalize_space", "parse_question_number")


def _election_modules() -> list[Path]:
    return sorted(ELECTIONS.rglob("*.py"))


def _package(module: str) -> str:
    return ".".join(module.split(".")[:3])


def _shared_constants() -> dict[int, str]:
    """The container constants anketa_tabs itself defines, by identity.

    Functions are told by `__module__` instead. Identity only means something
    for an object the module creates: a short string or a number can be the
    same object in two modules by accident, `re.compile` hands two modules
    the same cached pattern, and `load_candidate_meta` is
    `scraper.shared.files.load_candidate_index`, which other modules alias
    under names of their own.
    """
    tree = ast.parse((SHARED / "anketa_tabs.py").read_text(encoding="utf-8"))
    names: list[str] = []
    for node in tree.body:
        if isinstance(node, ast.Assign):
            names.extend(t.id for t in node.targets if isinstance(t, ast.Name))
    return {
        id(value): name
        for name in names
        if isinstance(value := getattr(anketa_tabs, name), (dict, list, set))
    }


class WhereTheHelpersLive(unittest.TestCase):
    def test_no_election_module_imports_the_2016_parser(self) -> None:
        offenders = []
        for path in _election_modules():
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom) and node.module == SEIMO_2016_PARSER:
                    offenders.append(f"{path.relative_to(REPO_ROOT)}:{node.lineno}")
                elif isinstance(node, ast.Import) and any(a.name == SEIMO_2016_PARSER for a in node.names):
                    offenders.append(f"{path.relative_to(REPO_ROOT)}:{node.lineno}")
        self.assertEqual(offenders, [])

    def test_the_promoted_names_are_importable_from_the_shared_module(self) -> None:
        self.assertEqual(len(PROMOTED), 35)
        for name in PROMOTED + KEPT:
            with self.subTest(name):
                self.assertTrue(callable(getattr(anketa_tabs, name, None)), name)
                self.assertFalse(hasattr(anketa_tabs, f"_{name}"), f"_{name} is back")
        self.assertIs(anketa_tabs.load_candidate_meta, load_candidate_index)

    def test_the_2016_parser_keeps_none_of_them(self) -> None:
        parser = importlib.import_module(SEIMO_2016_PARSER)
        for name in PROMOTED:
            with self.subTest(name):
                self.assertFalse(hasattr(parser, f"_{name}"), f"_{name} is defined in seimo_2016 again")
                value = getattr(parser, name, None)
                if value is not None:
                    self.assertIs(value, getattr(anketa_tabs, name))

    def test_no_election_module_reaches_a_shared_helper_through_another(self) -> None:
        # Within one election's package it is the same module family talking
        # to itself: `seimo_2016.candidate_samples` takes the URL resolver
        # from its own sitemap, which takes it from here.
        constants = _shared_constants()
        offenders = []
        for path in _election_modules():
            own = _package(".".join(path.relative_to(REPO_ROOT).with_suffix("").parts))
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in tree.body:
                if not (isinstance(node, ast.ImportFrom) and (node.module or "").startswith("scraper.elections.")):
                    continue
                if _package(node.module) == own:
                    continue
                source = importlib.import_module(node.module)
                for alias in node.names:
                    value = getattr(source, alias.name)
                    defined_there = callable(value) and getattr(value, "__module__", None) == anketa_tabs.__name__
                    if defined_there or id(value) in constants or alias.name == "load_candidate_meta":
                        offenders.append(f"{path.relative_to(REPO_ROOT)}: {alias.name} from {node.module}")
        self.assertEqual(offenders, [])

    def test_no_shared_module_imports_an_election_module(self) -> None:
        offenders = []
        for path in sorted(SHARED.glob("*.py")):
            for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
                modules = []
                if isinstance(node, ast.ImportFrom):
                    modules = [node.module or ""]
                elif isinstance(node, ast.Import):
                    modules = [a.name for a in node.names]
                for module in modules:
                    if module == "scraper.elections" or module.startswith("scraper.elections."):
                        offenders.append(f"{path.name}:{node.lineno} {module}")
        self.assertEqual(offenders, [])

    def test_the_2016_sitemap_resolves_urls_with_the_shared_rule(self) -> None:
        sitemap = importlib.import_module("scraper.elections.seimo_2016.sitemap")
        self.assertIs(sitemap.resolve_candidate_url, resolve_candidate_url)
        self.assertEqual(sitemap.VRK_STATINIAI_BASE, "https://www.vrk.lt/statiniai/puslapiai/")


class NormalizeTextValue(unittest.TestCase):
    """What every normalized string in 27 elections goes through."""

    def test_the_not_stated_placeholders_read_as_missing(self) -> None:
        for value in (None, "", "   ", "-", "nenurodė", "Nenurodė", "NENURODE", " nenurode "):
            with self.subTest(value=value):
                self.assertIsNone(normalize_text_value(value))

    def test_a_value_that_is_only_a_replacement_character_is_missing(self) -> None:
        self.assertIsNone(normalize_text_value("\ufffd"))

    def test_whitespace_collapses_and_a_trailing_separator_goes(self) -> None:
        self.assertEqual(normalize_text_value("  Jonas \n  Jonaitis  "), "Jonas Jonaitis")
        self.assertEqual(normalize_text_value("Jonas, Rasa,"), "Jonas, Rasa")

    def test_text_is_folded_to_nfc(self) -> None:
        decomposed = "Ke\u0307dainiai"
        self.assertFalse(unicodedata.is_normalized("NFC", decomposed))
        self.assertEqual(normalize_text_value(decomposed), "K\u0117dainiai")

    def test_a_non_string_is_stringified_not_judged(self) -> None:
        self.assertEqual(normalize_text_value(12), "12")
        self.assertEqual(normalize_text_value(1.5), "1.5")
        self.assertEqual(normalize_text_value(0), "0")


class OrderDictKeys(unittest.TestCase):
    def test_named_keys_first_then_the_rest_in_their_own_order(self) -> None:
        payload = {"c": 3, "a": 1, "d": 4, "b": 2}
        ordered = order_dict_keys(payload, ["a", "b", "not-there"])
        self.assertEqual(list(ordered), ["a", "b", "c", "d"])
        self.assertEqual(ordered, payload)

    def test_the_payload_is_left_alone(self) -> None:
        payload = {"c": 3, "a": 1}
        ordered = order_dict_keys(payload, ["a"])
        self.assertIsNot(ordered, payload)
        self.assertEqual(list(payload), ["c", "a"])

    def test_no_named_keys_keeps_the_payload_order(self) -> None:
        self.assertEqual(list(order_dict_keys({"b": 1, "a": 2}, [])), ["b", "a"])


class FindRowByQuestionNumber(unittest.TestCase):
    ROWS = [
        {"questionNumber": "9", "answer": "Ne"},
        {"questionNumber": "9.2", "answer": ""},
        {"questionNumber": "9.2", "answer": "Taip"},
        {"questionNumber": None, "answer": "tęsinys"},
        {"prompt": "no number at all"},
    ]

    def test_the_first_row_with_exactly_that_number(self) -> None:
        self.assertIs(find_row_by_question_number(self.ROWS, "9.2"), self.ROWS[1])
        self.assertIs(find_row_by_question_number(self.ROWS, "9"), self.ROWS[0])

    def test_no_prefix_match_and_no_row_is_none(self) -> None:
        self.assertIsNone(find_row_by_question_number(self.ROWS, "9.3"))
        self.assertIsNone(find_row_by_question_number(self.ROWS, "2"))
        self.assertIsNone(find_row_by_question_number([], "9"))


class NormalizeMissingValues(unittest.TestCase):
    def test_every_string_at_any_depth_goes_through_normalize_text_value(self) -> None:
        payload = {
            "a": " nenurodė ",
            "b": ["  x  y ", "-", 3, None, True],
            "c": {"d": "Ke\u0307dainiai", "e": {"f": ""}},
            "g": 2.5,
        }
        self.assertEqual(
            normalize_missing_values(payload),
            {
                "a": None,
                "b": ["x y", None, 3, None, True],
                "c": {"d": "K\u0117dainiai", "e": {"f": None}},
                "g": 2.5,
            },
        )

    def test_keys_and_non_list_containers_are_not_touched(self) -> None:
        self.assertEqual(normalize_missing_values({"nenurodė": "x"}), {"nenurodė": "x"})
        self.assertEqual(normalize_missing_values(("-",)), ("-",))
        self.assertIsNone(normalize_missing_values("-"))


class ResolveCandidateUrl(unittest.TestCase):
    BASE = "https://www.vrk.lt/statiniai/puslapiai/"

    def test_an_absolute_url_is_kept(self) -> None:
        for url in ("https://www.vrk.lt/2016-seimo/kandidatai", "http://example.test/a.html"):
            with self.subTest(url):
                self.assertEqual(resolve_candidate_url(url), url)

    def test_src_url_and_relative_links_resolve_against_the_static_root(self) -> None:
        self.assertEqual(
            resolve_candidate_url("?srcUrl=/rinkimai/102/rnk426/kandidatai/x.html"),
            f"{self.BASE}rinkimai/102/rnk426/kandidatai/x.html",
        )
        self.assertEqual(resolve_candidate_url("/rinkimai/102/x.html"), f"{self.BASE}rinkimai/102/x.html")
        self.assertEqual(resolve_candidate_url("rinkimai/102/x.html"), f"{self.BASE}rinkimai/102/x.html")


class CampaignSamplesTakeTheElection(unittest.TestCase):
    def test_the_election_id_is_required(self) -> None:
        # It used to default to "2016-seimo", the label every anomaly event
        # the campaign readers raise carries (issue #90).
        with self.assertRaises(TypeError):
            parse_nested_campaign_samples({}, None)  # type: ignore[call-arg]
        self.assertEqual(parse_nested_campaign_samples(None, election_id="x"), [])


if __name__ == "__main__":
    unittest.main()
