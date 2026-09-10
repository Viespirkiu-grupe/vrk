"""`dashboard/field-labels.json`: the labels, and the proof of each (issue #149).

`labelFor` resolved a record key against three tables and then de-slugged it,
which lower-cases an ASCII-folded slug and cannot put a diacritic back.
Measured over all 113,073 records: 480 distinct keys reach a label, 398 fell
through to `deslug`, and of those 125 came out provably mis-spelled
("Darboviete", "Pavarde", "Numeris sarase", "Seimos nariu skaicius") while 47
came out in English -- "Row number", on 4,020,284 cells.

The labels file answers that, and every entry in it says where its label comes
from. The four claims below are what the `proof` field means, and each one is
mechanical:

* `printed` -- the label is the string VRK prints, so `slugify(label) == key`:
  slugifying the printed label is *how the parser made the key*. Nothing here
  needs the corpus, and no wording is mine.
* `header` -- the label is the column heading VRK prints above the value, for
  the campaign-finance tables whose columns the parsers named in English
  (`donor`, `amountEur`). Checked against the archived pages under `samples/`.
* `restored` -- the key's own words with their diacritics and case restored,
  so folding the label reproduces the key word for word. Punctuation may be
  added, since a slug drops it.
* `structural` -- a key the parsers invented that no VRK page labels
  (`records`, `label`, `listKind`). No external proof exists, so these are
  held to the small explicit list at the end of this file: adding one is a
  deliberate act, not a slip.

And whatever the proof, an entry has to be live: its key still occurs in the
corpus, and its label differs from what `deslug` already produces.
"""

from __future__ import annotations

import json
import re
import unittest
from pathlib import Path

from tests import local_data

REPO_ROOT = Path(__file__).resolve().parents[1]
LABELS_PATH = REPO_ROOT / "dashboard" / "field-labels.json"
DASHBOARD_PATH = REPO_ROOT / "dashboard" / "index.html"
PAYLOAD = json.loads(LABELS_PATH.read_text(encoding="utf-8"))
LABELS: dict[str, dict[str, str]] = PAYLOAD["labels"]
SOURCE = DASHBOARD_PATH.read_text(encoding="utf-8")

PROOFS = ("printed", "header", "restored", "structural")

#: Every `structural` key there is. These are the parsers' own names for
#: things no VRK page labels, so the Lithuanian is editorial and the list is
#: enumerated here rather than pattern-matched.
STRUCTURAL_KEYS = frozenset(
    {
        "amount",
        "elected",
        "label",
        "listKind",
        "nominatedBy",
        "records",
        "relation",
        "replacedBy",
        "selfNominated",
        "statementUrl",
        "textUrls",
        "urls",
        "decision",
        "message",
        "round",
        "totals",
        "url",
        "vienmandatesBalsai",
        "vienmandatesBalsai2",
        "vrkRegistrationId",
    }
)

_FOLD = str.maketrans("ąčęėįšųūžĄČĘĖĮŠŲŪŽ", "aceeisuuzACEEISUUZ")
_LOWER, _UPPER = "a-ząčęėįšųūž", "A-ZĄČĘĖĮŠŲŪŽ"


def fold(text: str) -> str:
    return text.translate(_FOLD)


def deslug(key: str) -> str:
    """`deslug` out of dashboard/index.html, which this file exists to beat."""
    words = re.sub(f"([{_LOWER}])([{_UPPER}])", r"\1 \2", key).replace("-", " ").lower()
    return words[:1].upper() + words[1:]


def words(text: str) -> list[str]:
    """The letter-and-digit runs of a label, folded and lower-cased."""
    return re.findall(r"[a-z0-9]+", fold(text).lower())


class FileTests(unittest.TestCase):
    def test_it_is_a_documented_object_of_labels(self):
        self.assertIn("description", PAYLOAD)
        self.assertIn("verified", PAYLOAD)
        self.assertGreater(len(LABELS), 200)

    def test_every_entry_has_a_label_and_a_known_proof(self):
        for key, entry in LABELS.items():
            with self.subTest(key):
                self.assertTrue(entry.get("lt"), "empty label")
                self.assertEqual(entry["lt"], entry["lt"].strip())
                self.assertIn(entry.get("proof"), PROOFS)

    def test_no_entry_repeats_what_deslug_already_says(self):
        # A dead entry is worse than none: it looks like a decision and is
        # not, and the next reader has to re-derive that it changes nothing.
        dead = {k: v["lt"] for k, v in LABELS.items() if v["lt"] == deslug(k)}
        self.assertEqual(dead, {})

    def test_no_entry_shadows_a_section_label(self):
        # SECTION_LABELS wins in labelFor, so an entry for one of its keys
        # would never be read.
        block = re.search(r"const SECTION_LABELS = \{(.*?)\n\};", SOURCE, re.S).group(1)
        section_keys = set(re.findall(r'^\s*"?([A-Za-z-]+)"?:', block, re.M))
        self.assertTrue(section_keys)
        self.assertEqual(sorted(section_keys & set(LABELS)), [])

    def test_the_page_reads_the_file_and_survives_without_it(self):
        self.assertIn('fetch("field-labels.json", { cache: "no-store" })', SOURCE)
        self.assertIn("(FIELD_LABELS[key] || {}).lt || deslug(key)", SOURCE)
        # Not fatal: the labels are an improvement on deslug, not a
        # precondition for the page.
        self.assertIn(".catch(() => null)", SOURCE)
        self.assertNotIn("field-labels.json: HTTP", SOURCE)

    def test_the_labels_resolve_after_the_concept_map_and_before_deslug(self):
        resolution = re.search(r"function labelFor\(key\) \{(.*?)\n\}", SOURCE, re.S).group(1)
        order = [
            m.group(1)
            for m in re.finditer(r"(SECTION_LABELS|CONCEPT_LABELS|SEGMENT_LABELS|FIELD_LABELS|deslug)", resolution)
        ]
        self.assertEqual(
            order,
            ["SECTION_LABELS", "CONCEPT_LABELS", "SEGMENT_LABELS", "FIELD_LABELS", "deslug"],
        )


class ProofTests(unittest.TestCase):
    """Each `proof` value is a claim this class holds the file to."""

    def test_a_printed_label_slugifies_back_to_its_key(self):
        # Which is how the parser made the key in the first place: the label
        # is VRK's own string, not a translation.
        from scraper.shared.files import slugify

        for key, entry in LABELS.items():
            if entry["proof"] != "printed":
                continue
            with self.subTest(key):
                self.assertEqual(slugify(entry["lt"]), key)

    def test_a_restored_label_is_its_key_word_for_word(self):
        # Diacritics, case and punctuation only. Folding the label has to
        # reproduce what `deslug` makes of the key -- the same words in the
        # same order, camelCase split the same way -- so no entry can quietly
        # reword a field.
        for key, entry in LABELS.items():
            if entry["proof"] != "restored":
                continue
            with self.subTest(key):
                self.assertEqual(words(entry["lt"]), words(deslug(key)))

    def test_a_restored_label_actually_restores_something(self):
        for key, entry in LABELS.items():
            if entry["proof"] != "restored":
                continue
            with self.subTest(key):
                self.assertNotEqual(entry["lt"], deslug(key), "nothing restored")

    def test_the_structural_keys_are_the_enumerated_ones(self):
        declared = {k for k, v in LABELS.items() if v["proof"] == "structural"}
        self.assertEqual(declared, set(STRUCTURAL_KEYS))

    def test_a_header_label_is_quoted_from_an_archived_page(self):
        """Every `header` label is a table heading VRK prints.

        The campaign-finance tables are the ones whose columns the parsers
        named in English, so the proof is the heading itself, read out of the
        retained HTML. `samples/` carries at least one campaign tree per
        election that has one; a clone without them skips.
        """
        pages = sorted((REPO_ROOT / "samples" / "html").glob("*/*/campaigns/*/*.html"))
        local_data.require(REPO_ROOT / "samples" / "html")
        if not pages:
            self.skipTest("no campaign fixtures — run the scraper for one election")
        cells: set[str] = set()
        for page in pages:
            text = page.read_text(encoding="utf-8", errors="replace")
            for cell in re.findall(r"<t[hd][^>]*>(.*?)</t[hd]>", text, re.S | re.I):
                stripped = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", cell)).strip()
                if stripped:
                    cells.add(_unescape(stripped))
        self.assertGreater(len(cells), 100, "campaign fixtures parsed to nothing")
        for key, entry in LABELS.items():
            if entry["proof"] != "header":
                continue
            with self.subTest(key):
                self.assertIn(entry["lt"], cells)


def _unescape(text: str) -> str:
    import html

    return html.unescape(text)


class CorpusTests(unittest.TestCase):
    """Whatever proves a label, the key it labels has to still be in the data."""

    KEYS: set[str] = set()

    @classmethod
    def setUpClass(cls) -> None:
        local_data.require_corpus()
        cls.KEYS = _corpus_keys(REPO_ROOT / "data")

    def test_every_labelled_key_occurs_in_the_corpus(self):
        missing = sorted(set(LABELS) - self.KEYS)
        self.assertEqual(missing, [], "labels for keys no record holds")

    def test_what_is_left_to_deslug_is_pinned(self):
        """253 of the 442 keys are labelled here; the residue is pinned.

        The 189 that still de-slug were read one by one: `adresas`, `data`,
        `forma`, `metai`, `pareigos`, `turas`, `koalicijosPartija` and the
        rest carry no diacritic, so de-slugging them is right and a label
        would be dead weight -- which is what
        `test_no_entry_repeats_what_deslug_already_says` refuses. A new
        election that adds a key of its own moves this count, which is the
        signal to look at its labels.
        """
        self.assertEqual(len(self.KEYS), 442)
        self.assertEqual(len(set(LABELS) & self.KEYS), len(LABELS))
        for key in ("darboviete", "pavarde", "numeris-sarase", "seimos-nariu-skaicius", "rowNumber"):
            self.assertIn(key, LABELS, f"{key} is the issue's own example")


def _corpus_keys(data_root: Path) -> set[str]:
    """Every key the person page can put a label on, over the whole corpus.

    The same walk `labelFor`'s callers do: the sections of `normalized` plus
    the root `kandidatavimas` block, the keys of every object below them, and
    the union of keys across a list of objects — skipping the
    `{pavadinimas, reiksme}` shape, which prints its own label.
    """
    keys: set[str] = set()

    def prints_its_own_label(value: object) -> bool:
        # `profilis.kita`'s entries are {pavadinimas, reiksme, nuorodos} and
        # renderValue uses the `pavadinimas` as the label, so their key
        # (`iskele-2`, `numeris-sarase-2`) never reaches labelFor.
        return (
            isinstance(value, dict)
            and isinstance(value.get("pavadinimas"), str)
            and "reiksme" in value
        )

    def walk(value: object) -> None:
        if isinstance(value, dict):
            if prints_its_own_label(value):
                walk(value.get("reiksme"))
                return
            for key, child in value.items():
                if key == "nuotrauka":
                    continue
                if not prints_its_own_label(child):
                    keys.add(key)
                walk(child)
        elif isinstance(value, list):
            for item in value:
                walk(item)

    for election in sorted(child for child in data_root.iterdir() if child.is_dir()):
        for path in sorted(election.glob("*.json")):
            if path.name == "index.json":
                continue
            try:
                record = json.loads(path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, UnicodeDecodeError):
                continue
            if not isinstance(record, dict) or "normalized" not in record:
                continue
            sections = dict(record.get("normalized") or {})
            if isinstance(record.get("kandidatavimas"), dict) and "kandidatavimas" not in sections:
                sections["kandidatavimas"] = record["kandidatavimas"]
            for section, value in sections.items():
                keys.add(section)
                walk(value)
    return keys


if __name__ == "__main__":
    unittest.main()
