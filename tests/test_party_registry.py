"""The party registry's invariants, and the issue #82 acceptance criteria.

`scraper/parties.json` creates the party identity the corpus never had: every
one of the measured nominator surface forms is an exact alias of exactly one
entry, matching never guesses, and the registry -- not the corpus -- carries
renames and mergers. These tests run on a bare clone: the registry and
`docs/nominator-forms.tsv` are tracked files, so a new unmatched form or a
collision is a red suite before it is a corpus mystery.
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

from scraper.shared import parties
from scraper.shared.parties import ENTRY_TYPES, ancestors, entries, fold, load_registry, match

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


#: How a nominator's legal form shows in VRK's own spelling of its name. An
#: alias is a rename of one continuing organisation, so it can never cross the
#: form its entry has: the 2011 independents' coalition, the 2015-2019
#: committee and the 2023 party called Vieningas Kaunas are three entries
#: linked by `predecessors`, not one entry with three aliases.
FORM_MARKERS = (
    ("komitetas", ("visuomeninis rinkimų komitetas", "politinis komitetas")),
    ("koalicija", ("koalicija",)),
)


#: Quoted brands and parenthesised line-ups, where a comma is punctuation
#: ("Judėk, Vilniau"; "(centristai, tautininkai)") rather than a list.
_INNER = re.compile(r"[„\"“][^„“”\"]*[“”\"]|\([^)]*\)")


def form_of(name: str) -> str | None:
    # A comma between organisations outside quotes and parentheses is a joint
    # nomination line ("Darbo partija, Visuomeninis rinkimų komitetas
    # „Permainų laikas“"): a coalition whatever the parts are called. The one
    # exception is the registry's own rule for "X, išsikėlė pats", which is X.
    parts = [p for p in _INNER.sub(" ", name).split(",") if p.strip() and "išsikėl" not in p.casefold()]
    if len(parts) > 1:
        return "koalicija"
    folded = fold(name)
    for kind, markers in FORM_MARKERS:
        if any(marker in folded for marker in markers):
            return kind
    return None


class LineageTests(unittest.TestCase):
    """The issue #123 model: one entry per organisation, `predecessors` for
    what it continues, and a `reviewedDistinct` block for the pairs the
    lineage report flags that review found to be two organisations."""

    def test_predecessor_links_form_a_forest(self):
        # One successor per organisation (a merged party is continued by the
        # union, a committee by the party that grew out of it) and no loop, so
        # the dashboard's lineage groups and `ancestors()` both terminate with
        # one root per lineage.
        successors: dict[str, str] = {}
        for party_id, entry in entries().items():
            for pred in entry.get("predecessors", []):
                self.assertNotEqual(pred, party_id, f"{party_id} lists itself")
                self.assertNotIn(pred, successors, f"{pred} is listed by both {successors.get(pred)} and {party_id}")
                successors[pred] = party_id
        for party_id in entries():
            self.assertNotIn(party_id, ancestors(party_id), f"{party_id} is its own ancestor")

    def test_an_alias_never_crosses_the_legal_form_of_its_entry(self):
        for party_id, entry in entries().items():
            for name in [entry["name"], *entry.get("aliases", [])]:
                form = form_of(name)
                if form is not None:
                    self.assertEqual(form, entry["type"], f"{name!r} on {party_id} ({entry['type']})")

    def test_reviewed_distinct_pairs_name_two_unlinked_entries_with_a_reason(self):
        ids = set(entries())
        for row in load_registry().get("reviewedDistinct", []):
            self.assertEqual(set(row), {"a", "b", "why"}, row)
            self.assertIn(row["a"], ids, row)
            self.assertIn(row["b"], ids, row)
            self.assertNotEqual(row["a"], row["b"], row)
            self.assertTrue(row["why"].strip(), row)
            # A pair that got linked after being recorded is a stale review.
            self.assertNotIn(row["a"], ancestors(row["b"]), f"{row['a']} is now a predecessor of {row['b']}")
            self.assertNotIn(row["b"], ancestors(row["a"]), f"{row['b']} is now a predecessor of {row['a']}")

    def test_a_rename_of_one_organisation_is_one_entry(self):
        # The issue #123 suspect list, settled against the Ministry of Justice
        # register: the same registration under successive names.
        for form, party_id in (
            ("Pensininkų partija", "lietuvos-pensininku-partija"),
            ('Lietuvos partija "Socialdemokratija 2000"', "lietuvos-socialdemokratu-sajunga"),
            ("Nacionalinė centro partija", "lietuvos-centro-partija"),
            ("Centro partija - tautininkai", "lietuvos-centro-partija"),
            ("Kovotojų už Lietuvą sąjunga", "lietuvos-laisves-sajunga"),
            ("Politinė partija „Lietuvos žaliųjų sąjūdis“", "lietuvos-zaliuju-partija"),
            ("Nuosaikiųjų konservatorių sąjunga", "krikscioniu-partija"),
            ("Tautos vienybės sąjunga", "pilietines-demokratijos-partija"),
            ("„Šilališkių“ visuomeninis rinkimų komitetas", "komitetas-silaliskiai"),
            ("Politinis komitetas Nepartinis sąrašas „Dirbame miestui“", "komitetas-arturo-visocko-sarasas-dirbame-miestui"),
        ):
            self.assertEqual(match(form), party_id, form)

    def test_a_change_of_legal_form_or_a_takeover_is_a_link_not_an_alias(self):
        self.assertEqual(
            ancestors("vieningas-kaunas"), {"komitetas-vieningas-kaunas", "koalicija-vieningas-kaunas"}
        )
        self.assertEqual(ancestors("kartu-solidarumo-sajunga"), {"lietuvos-pensininku-partija"})
        self.assertEqual(ancestors("pilietines-demokratijos-partija"), {"lietuvos-pilieciu-aljansas"})
        self.assertEqual(
            ancestors("lietuviu-tautininku-ir-respublikonu-sajunga"),
            {"tautininku-sajunga", "respublikonu-partija"},
        )
        # The 1990 nationalists merged into the conservatives in 2008; the
        # 2011 party that claims their tradition is a re-establishment, and a
        # forest holds one successor -- so the link is the merger, the claim
        # a note.
        self.assertIn("lietuviu-tautininku-sajunga", ancestors("ts-lkd"))
        self.assertNotIn("lietuviu-tautininku-sajunga", ancestors("tautininku-sajunga"))
        self.assertIn("lietuviu-tautininku-ir-respublikonu-sajunga", ancestors("tautos-ir-teisingumo-sajunga"))
        self.assertIn("lietuvos-centro-partija", ancestors("tautos-ir-teisingumo-sajunga"))
        # Šustauskas's 1994 union and the liberals' 2014 one are two registrations.
        self.assertNotIn("lietuvos-laisves-sajunga", ancestors("laisve-ir-teisingumas"))
        self.assertIn("lietuvos-laisves-sajunga-liberalai", ancestors("laisve-ir-teisingumas"))


if __name__ == "__main__":
    unittest.main()
