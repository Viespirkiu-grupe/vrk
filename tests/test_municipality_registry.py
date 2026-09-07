"""The municipality registry's invariants (issue #137).

`scraper/municipalities.json` creates the cross-election municipality identity
the corpus never had: every published wording of a municipality is an exact
alias of exactly one entry, matching never guesses, and the two bodies the
2000 reform dissolved stay their own entries. These tests run on a bare clone
-- the registry and `docs/municipality-forms.tsv` are tracked -- so a new
spelling upstream is a red suite before it is a doubled facet row.
"""

from __future__ import annotations

import json
import unittest
from pathlib import Path

import local_data

from scraper.shared import municipalities
from scraper.shared.kandidatura import kandidatura
from scraper.shared.municipalities import KINDS, entries, match, normalize_form, savivaldybe

REPO_ROOT = Path(__file__).resolve().parents[1]
FORMS_TABLE = REPO_ROOT / "docs" / "municipality-forms.tsv"
DATA_ROOT = REPO_ROOT / "data"
REGISTRY = REPO_ROOT / "scraper" / "elections.json"

#: Lithuania has had 60 municipalities since the 2000 reform; before it,
#: Marijampolė was a city and a district, so the corpus spans 62 bodies.
MUNICIPALITIES_SINCE_2000 = 60
BODIES_IN_THE_CORPUS = 62


def forms_table_rows() -> list[tuple[str, int, str, str]]:
    rows = []
    for line in FORMS_TABLE.read_text(encoding="utf-8").splitlines():
        if not line.strip() or line.startswith("form\t"):
            continue
        form, records, municipality_id, elections = (line.split("\t") + ["", "", "", ""])[:4]
        rows.append((form, int(records), municipality_id, elections))
    return rows


class RegistryStructureTests(unittest.TestCase):
    def test_the_registry_holds_every_body_the_corpus_spans(self):
        self.assertEqual(len(entries()), BODIES_IN_THE_CORPUS)
        current = [mid for mid, e in entries().items() if not e.get("until")]
        self.assertEqual(len(current), MUNICIPALITIES_SINCE_2000)
        self.assertEqual(
            sorted(mid for mid, e in entries().items() if e.get("until")),
            ["marijampoles-miesto", "marijampoles-rajono"],
        )

    def test_every_entry_is_well_formed(self):
        for municipality_id, entry in entries().items():
            with self.subTest(municipality_id):
                self.assertTrue(entry.get("name", "").endswith(("savivaldybė", "savivaldybė (iki 2000 m.)")), entry.get("name"))
                self.assertIn(entry.get("kind"), KINDS)
                self.assertIsInstance(entry.get("aliases"), list)
                self.assertTrue(entry["aliases"])

    def test_no_form_is_claimed_twice(self):
        seen: dict[str, str] = {}
        for municipality_id, entry in entries().items():
            for form in (entry["name"], *entry["aliases"]):
                key = normalize_form(form)
                self.assertNotIn(key, {k: v for k, v in seen.items() if v != municipality_id}, form)
                seen[key] = municipality_id

    def test_no_two_current_bodies_differ_only_by_the_suffix(self):
        # The split the issue measured: 'X rajono' and 'X rajono savivaldybė'
        # as two facet rows. Canonical names are official names, so none of
        # them is another's name plus the word.
        names = {e["name"] for e in entries().values()}
        for name in names:
            self.assertNotIn(f"{name} savivaldybė", names)
            self.assertNotIn(name.removesuffix(" savivaldybė"), names - {name})

    def test_the_city_district_pairs_stay_apart(self):
        for stem in ("Alytaus", "Kauno", "Klaipėdos", "Panevėžio", "Šiaulių", "Vilniaus"):
            self.assertNotEqual(match(f"{stem} miesto"), match(f"{stem} rajono"), stem)
            self.assertIsNotNone(match(f"{stem} miesto"))
            self.assertIsNotNone(match(f"{stem} rajono"))


class MatchingTests(unittest.TestCase):
    def test_every_eras_wording_is_one_body(self):
        self.assertEqual(match("Vilniaus miesto"), match("Vilniaus miesto savivaldybė"))
        self.assertEqual(match("Palangos savivaldybė"), match("Palangos miesto"))
        self.assertEqual(match("Birštono miesto"), match("Birštono"))
        self.assertEqual(match("Visagino miesto"), match("Visagino savivaldybė"))

    def test_the_mayoral_cards_number_suffix_is_presentation(self):
        self.assertEqual(match("Telšių rajono (Nr. 51)"), "telsiu-rajono")
        self.assertEqual(match("Jonavos rajono (10)"), "jonavos-rajono")
        self.assertEqual(match("Marijampolės (25)"), "marijampoles")

    def test_the_2019_dict_shape_matches_by_its_name(self):
        self.assertEqual(match({"id": "19972", "number": 15, "name": "Kauno miesto"}), "kauno-miesto")

    def test_matching_never_guesses(self):
        self.assertIsNone(match("Vilnius"))
        self.assertIsNone(match("vilniaus miesto"))  # case is not folded: aliases are explicit
        self.assertIsNone(match(""))
        self.assertIsNone(match(None))

    def test_the_derived_concept_keeps_the_published_form(self):
        self.assertEqual(
            savivaldybe("Telšių rajono (Nr. 51)"),
            {"savivaldybe-id": "telsiu-rajono", "savivaldybe": "Telšių rajono savivaldybė", "savivaldybe-raw": "Telšių rajono (Nr. 51)"},
        )
        self.assertEqual(
            savivaldybe("Nauja savivaldybė (7)"),
            {"savivaldybe-id": None, "savivaldybe": "Nauja savivaldybė", "savivaldybe-raw": "Nauja savivaldybė (7)"},
        )

    def test_the_two_dissolved_bodies_are_not_the_2000_municipality(self):
        self.assertEqual(match("Marijampolės miesto"), "marijampoles-miesto")
        self.assertEqual(match("Marijampolės rajono"), "marijampoles-rajono")
        self.assertEqual(match("Marijampolės"), "marijampoles")
        self.assertEqual(match("Marijampolės savivaldybė"), "marijampoles")


class FormsTableTests(unittest.TestCase):
    """docs/municipality-forms.tsv is the measured table of every published
    form: a clone can hold the corpus's spellings to the registry without the
    corpus."""

    def test_every_measured_form_resolves_to_its_entry(self):
        rows = forms_table_rows()
        self.assertGreater(len(rows), 100)
        for form, _records, municipality_id, _elections in rows:
            with self.subTest(form):
                self.assertTrue(municipality_id, f"{form!r} is unresolved in the table")
                self.assertEqual(match(form), municipality_id)

    def test_every_current_body_is_published_somewhere(self):
        used = {municipality_id for _, _, municipality_id, _ in forms_table_rows()}
        self.assertEqual(sorted(set(entries()) - used), [])

    def test_the_table_spans_the_split_the_issue_measured(self):
        # 127 distinct stripped names collapsed to 62 bodies; the raw forms
        # add the mayoral cards' numbered spellings.
        forms = {form for form, *_ in forms_table_rows()}
        self.assertGreaterEqual(len(forms), 127)
        self.assertEqual(len({match(f) for f in forms}), BODIES_IN_THE_CORPUS)


class CorpusTests(unittest.TestCase):
    """Every municipality string in the corpus resolves. Skips without data/."""

    def test_every_record_with_a_municipality_joins(self):
        local_data.require_corpus(complete=True)
        kind_of = {e["id"]: e["kind"] for e in json.loads(REGISTRY.read_text(encoding="utf-8"))["elections"]}
        unresolved: dict[str, set[str]] = {}
        seen_ids: set[str] = set()
        checked = 0
        for election_dir in sorted(p for p in DATA_ROOT.iterdir() if p.is_dir()):
            if kind_of.get(election_dir.name) not in {"savivaldybiu", "mero"}:
                continue
            for path in election_dir.glob("*.json"):
                answer = kandidatura(json.loads(path.read_text(encoding="utf-8")), kind_of[election_dir.name])
                if answer["savivaldybe-raw"] is None:
                    continue
                checked += 1
                if answer["savivaldybe-id"] is None:
                    unresolved.setdefault(election_dir.name, set()).add(answer["savivaldybe-raw"])
                else:
                    seen_ids.add(answer["savivaldybe-id"])
        self.assertGreater(checked, 90_000)
        self.assertEqual(unresolved, {})
        self.assertEqual(len(seen_ids), BODIES_IN_THE_CORPUS)


if __name__ == "__main__":
    unittest.main()
