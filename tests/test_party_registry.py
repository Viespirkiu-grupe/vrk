"""The party registry's invariants, and the issue #82 acceptance criteria.

`scraper/parties.json` creates the party identity the corpus never had: every
one of the measured nominator surface forms is an exact alias of exactly one
entry, matching never guesses, and the registry -- not the corpus -- carries
renames and mergers. These tests run on a bare clone: the registry and
`docs/nominator-forms.tsv` are tracked files, so a new unmatched form or a
collision is a red suite before it is a corpus mystery.
"""

from __future__ import annotations

import unittest
from pathlib import Path

from scraper.shared import parties
from scraper.shared.parties import ENTRY_TYPES, entries, fold, load_registry, match

REPO_ROOT = Path(__file__).resolve().parents[1]
FORMS_TABLE = REPO_ROOT / "docs" / "nominator-forms.tsv"


def forms_table_rows() -> list[tuple[str, int, str, str]]:
    rows = []
    for line in FORMS_TABLE.read_text(encoding="utf-8").splitlines():
        if not line.strip() or line.startswith("form\t"):
            continue
        form, records, party_id, kind = (line.split("\t") + ["", "", "", ""])[:4]
        rows.append((form, int(records), party_id, kind))
    return rows


class RegistryStructureTests(unittest.TestCase):
    def test_unmatched_block_is_empty(self):
        # The issue #82 acceptance: every measured surface form maps to an
        # entry. scripts/nominator_report.py writes any form nothing claims
        # into this block; classifying it (an alias on an existing entry, or
        # a new entry) is what turns this test green again.
        self.assertEqual(load_registry()["unmatched"], [])

    def test_every_entry_is_well_formed(self):
        for party_id, entry in entries().items():
            self.assertTrue(entry.get("name"), party_id)
            self.assertIn(entry.get("type"), ENTRY_TYPES, party_id)
            self.assertIsInstance(entry.get("aliases", []), list, party_id)

    def test_no_alias_is_claimed_twice_even_folded(self):
        # Matching must be deterministic: one string, one entry. Checked on
        # the folded key, which the exact key cannot collide without.
        seen: dict[str, str] = {}
        for party_id, entry in entries().items():
            keys = [entry["name"], *entry.get("aliases", [])]
            if entry.get("shortName"):
                keys.append(entry["shortName"])
            for key in keys:
                folded = fold(key)
                self.assertNotIn(
                    folded, {k: v for k, v in seen.items() if v != party_id},
                    f"{key!r} of {party_id} folds onto an alias of {seen.get(folded)}",
                )
                seen[folded] = party_id

    def test_every_reference_resolves(self):
        ids = set(entries())
        for party_id, entry in entries().items():
            for ref in entry.get("predecessors", []):
                self.assertIn(ref, ids, f"{party_id} predecessor {ref}")
            for ref in entry.get("nariai", []):
                self.assertIn(ref, ids, f"{party_id} narys {ref}")

    def test_nariai_appear_only_on_coalitions_and_never_empty(self):
        # An absent `nariai` means "membership not recovered"; an empty list
        # would silently claim "no members", which no coalition has.
        for party_id, entry in entries().items():
            if "nariai" in entry:
                self.assertEqual(entry["type"], "koalicija", party_id)
                self.assertTrue(entry["nariai"], party_id)


class FormsTableTests(unittest.TestCase):
    def test_every_measured_form_matches_an_entry(self):
        for form, _, _, _ in forms_table_rows():
            self.assertIsNotNone(match(form), f"no registry entry claims {form!r}")

    def test_the_written_join_agrees_with_the_matcher(self):
        # The table's partija-id column is written for human review; if the
        # registry moves an alias, the stale column has to move with it.
        for form, _, party_id, kind in forms_table_rows():
            self.assertEqual(match(form), party_id, form)
            self.assertEqual(entries()[party_id]["type"], kind, form)

    def test_the_table_covers_the_measured_corpus(self):
        rows = forms_table_rows()
        self.assertGreaterEqual(len(rows), 390)
        self.assertGreaterEqual(sum(records for _, records, _, _ in rows), 113_000)


class MatchingTests(unittest.TestCase):
    def test_exact_alias(self):
        self.assertEqual(match("Lietuvos socialdemokratų partija"), "lsdp")
        self.assertEqual(match("Lietuvos socialdemokratų partijos"), "lsdp")

    def test_fold_unifies_the_glyph_noise_vrk_varies_on(self):
        # An em dash and uppercase: no measured form, but the same name.
        self.assertEqual(match("TĖVYNĖS SĄJUNGA — LIETUVOS KRIKŠČIONYS DEMOKRATAI"), "ts-lkd")
        # Straight quotes for curly ones.
        self.assertEqual(match('Demokratų sąjunga "Vardan Lietuvos"'), "vardan-lietuvos")

    def test_fold_never_de_inflects(self):
        # The genitive is an explicit alias where measured, never a rule: a
        # generic de-genitiver cannot tell an inflection from another name.
        self.assertNotEqual(fold("Lietuvos centro sąjungos"), fold("Lietuvos centro sąjunga"))

    def test_an_unknown_form_is_unmatched_not_guessed(self):
        self.assertIsNone(match("Nebūtų nebūtėlių partija"))
        self.assertIsNone(match(None))
        self.assertIsNone(match("  "))

    def test_the_self_nomination_label_maps_to_the_self_entry(self):
        self.assertEqual(match("Išsikėlęs kandidatas"), "issikele-pats")
        self.assertEqual(match("išsikėlė pati"), "issikele-pats")

    def test_a_line_naming_a_party_plus_self_nomination_is_the_party(self):
        self.assertEqual(match("Partija Tvarka ir teisingumas, išsikėlė pats"),
                         "tvarka-ir-teisingumas")


class AcceptanceTests(unittest.TestCase):
    """The issue #82 acceptance criteria, verbatim."""

    #: TS-LKD's six surface forms: three dash glyphs, the genitive, and the
    #: party's two pre-2008 official names.
    TSLKD_FORMS = (
        "Tėvynės sąjunga - Lietuvos krikščionys demokratai",
        "Tėvynės sąjunga – Lietuvos krikščionys demokratai",
        "Tėvynės sąjunga-Lietuvos krikščionys demokratai",
        "Tėvynės sąjunga (Lietuvos konservatoriai)",
        "Tėvynės sąjungos (Lietuvos konservatorių)",
        "Tėvynės sąjunga (konservatoriai, politiniai kaliniai ir tremtiniai,"
        " krikščioniškieji demokratai)",
    )

    def test_ts_lkd_groups_as_one_party_with_the_pre_2008_name_a_predecessor(self):
        family = {"ts-lkd", *entries()["ts-lkd"]["predecessors"]}
        for form in self.TSLKD_FORMS:
            self.assertIn(match(form), family, form)
        # The three dash variants are the party itself; the pre-2008 names are
        # the predecessor entry, not aliases of the merged party.
        for form in self.TSLKD_FORMS[:3]:
            self.assertEqual(match(form), "ts-lkd", form)
        for form in self.TSLKD_FORMS[3:]:
            self.assertEqual(match(form), "tevynes-sajunga", form)
        self.assertIn("tevynes-sajunga", entries()["ts-lkd"]["predecessors"])

    def test_the_derived_concept_returns_id_raw_and_kind(self):
        record = {
            "electionId": "2016-seimo",
            "normalized": {
                "profilis": {
                    "kita": {"iskele": {"reiksme": "Tėvynės sąjunga-Lietuvos krikščionys demokratai"}}
                }
            },
        }
        self.assertEqual(
            parties.partija(record),
            {
                "partija-id": "ts-lkd",
                "partija-vardas-raw": "Tėvynės sąjunga-Lietuvos krikščionys demokratai",
                "tipas": "partija",
            },
        )

    def test_the_derived_concept_on_an_election_with_no_nominator(self):
        record = {"electionId": "2019-prezidento", "normalized": {}}
        self.assertEqual(
            parties.partija(record),
            {"partija-id": None, "partija-vardas-raw": None, "tipas": None},
        )


if __name__ == "__main__":
    unittest.main()
