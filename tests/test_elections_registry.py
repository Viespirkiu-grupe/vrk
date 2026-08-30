"""The one registry of elections: scraper/elections.json.

Before it, an election's name and chronology lived in three hand-maintained
lists across two files -- ELECTION_ORDER in scripts/build_person_index.py plus
ELECTION_LABELS and SHORT_LABELS in dashboard/index.html. Adding an election
meant editing all three, and the last additions edited none: the 2011
municipal general (16,400 records) was invisible to the dashboard and six more
elections rendered as raw slugs. These tests pin the registry's shape and,
when a local corpus is present, that every election in it has an entry --
which is the check that was missing. See GitHub issue #63.
"""

from __future__ import annotations

import datetime as dt
import importlib.util
import json
import re
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
REGISTRY_PATH = REPO_ROOT / "scraper" / "elections.json"
DASHBOARD_PATH = REPO_ROOT / "dashboard" / "index.html"

_spec = importlib.util.spec_from_file_location(
    "build_person_index", REPO_ROOT / "scripts" / "build_person_index.py"
)
build_person_index = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(build_person_index)

REGISTRY = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))["elections"]

# The chronology as it stood when the three hand-maintained lists were folded
# into the registry, kept here as a one-time oracle: the registry now derives
# order from its `date` fields, and reproducing this list exactly is what
# showed those dates were right. The 2011 municipal general is the single
# addition -- it was missing from the old list, which is the bug.
ORDER_BEFORE_THE_REGISTRY = [
    "1996-spalio-20-seimo",
    "1997-kovo-23-savivaldybiu-tarybu",
    "1997-kovo-23-seimo-pakartotiniai",
    "1997-birzelio-29-svenciniu-tarybos-pakartotiniai",
    "1997-gruodzio-21-seimo-pakartotiniai",
    "2007-spalio-7-seimo-dzukija",
    "2008-seimo",
    "2009-prezidento",
    "2009-ep",
    "2009-lapkricio-15-seimo-silale-silute-vilnius-salcininkai",
    "2011-vasario-13-seimo-marijampole",
    "2012-seimo",
    "2013-kovo-3-seimo-birzai-zarasai-ukmerge",
    "2014-prezidento",
    "2014-ep",
    "2015-kovo-1-savivaldybiu",
    "2015-kovo-1-seimo-zirmunai",
    "2015-birzelio-7-seimo-varena-eisiskes",
    "2015-birzelio-7-pakartotiniai-sirvintos-trakai",
    "2015-birzelio-21-pakartotiniai-silutes",
    "2015-lapkricio-8-telsiu-mero",
    "2016-seimo",
    "2017-balandzio-23-meru",
    "2017-balandzio-23-seimo-anyksciai-panevezys",
    "2017-rugsejo-10-marijampoles-mero",
    "2018-rugsejo-16-seimo-zanavykai",
    "2019-kovo-3-savivaldybiu-tarybu",
    "2019-prezidento",
    "2019-ep",
    "2019-rugsejo-8-seimo",
    "2020-seimo",
    "2021-balandzio-11-radviliskio-mero",
    "2021-spalio-10-meru",
    "2023-kovo-5-savivaldybiu-tarybu-ir-meru",
    "2023-geguzes-7-visagino-mero",
    "2023-rugsejo-3-seimo-raseiniai-kedainiai",
    "2023-spalio-8-kupiskio-mero",
    "2024-prezidento",
    "2024-ep",
    "2024-seimo",
    "2025-kovo-16-meru",
]


#: What each election elects. `savivaldybiu` covers the council generals
#: (2023's combined council-and-mayor ballot included); `mero` the purely
#: mayoral races. The candidacy table's election_kind column and
#: scraper/shared/kandidatura.py's office resolution both read this field.
KINDS = {"seimo", "savivaldybiu", "prezidento", "ep", "mero"}


class RegistryShapeTests(unittest.TestCase):
    def test_every_entry_has_the_five_required_fields(self):
        for entry in REGISTRY:
            with self.subTest(entry.get("id")):
                self.assertEqual(
                    set(entry), {"id", "date", "kind", "name", "shortName"}, entry.get("id")
                )
                for field in ("id", "date", "kind", "name", "shortName"):
                    self.assertTrue(str(entry[field]).strip(), field)

    def test_kind_is_one_of_the_five(self):
        for entry in REGISTRY:
            with self.subTest(entry["id"]):
                self.assertIn(entry["kind"], KINDS)

    def test_kind_agrees_with_the_id(self):
        # The id encodes what was elected; a kind that contradicts it is a
        # typo. The two 2015 municipal repeats carry no marker in their id
        # and are pinned explicitly.
        for entry in REGISTRY:
            eid, kind = entry["id"], entry["kind"]
            with self.subTest(eid):
                if eid in {
                    "2015-birzelio-7-pakartotiniai-sirvintos-trakai",
                    "2015-birzelio-21-pakartotiniai-silutes",
                }:
                    self.assertEqual(kind, "savivaldybiu")
                elif "prezidento" in eid:
                    self.assertEqual(kind, "prezidento")
                elif eid.endswith("-ep"):
                    self.assertEqual(kind, "ep")
                elif "savivaldybiu" in eid or "tarybos" in eid:
                    self.assertEqual(kind, "savivaldybiu")
                elif "meru" in eid or "mero" in eid:
                    self.assertEqual(kind, "mero")
                else:
                    self.assertIn("seimo", eid)
                    self.assertEqual(kind, "seimo")

    def test_ids_are_unique(self):
        ids = [e["id"] for e in REGISTRY]
        self.assertEqual(len(ids), len(set(ids)))

    def test_dates_are_iso_and_the_id_starts_with_the_same_year(self):
        for entry in REGISTRY:
            with self.subTest(entry["id"]):
                date = dt.date.fromisoformat(entry["date"])  # raises if malformed
                self.assertTrue(entry["id"].startswith(f"{date.year}-"))

    def test_names_are_lithuanian_not_english_descriptions(self):
        # The labels this registry replaced read "1997 municipal councils".
        for entry in REGISTRY:
            with self.subTest(entry["id"]):
                self.assertRegex(entry["name"], r"rinkimai|balsavimas")

    def test_short_names_stay_short_enough_for_a_chart_axis(self):
        for entry in REGISTRY:
            with self.subTest(entry["id"]):
                self.assertLessEqual(len(entry["shortName"]), 24)

    def test_file_is_stored_in_chronological_order(self):
        # load_registry() re-sorts, so this only pins the file itself readable.
        self.assertEqual(
            [e["id"] for e in REGISTRY],
            [e["id"] for e in build_person_index.load_registry(REGISTRY_PATH)],
        )

    def test_order_still_matches_the_hand_curated_chronology(self):
        ordered = [e["id"] for e in build_person_index.load_registry(REGISTRY_PATH)]
        self.assertEqual(
            [eid for eid in ordered if eid in set(ORDER_BEFORE_THE_REGISTRY)],
            ORDER_BEFORE_THE_REGISTRY,
        )


class DashboardCarriesNoElectionListTests(unittest.TestCase):
    """The point of the registry is that index.html stops duplicating it."""

    def test_no_hardcoded_label_maps_remain(self):
        source = DASHBOARD_PATH.read_text(encoding="utf-8")
        for name in ("ELECTION_LABELS", "SHORT_LABELS", "ELECTION_ORDER"):
            self.assertNotIn(name, source)

    def test_no_election_id_is_hardcoded_in_the_dashboard(self):
        source = DASHBOARD_PATH.read_text(encoding="utf-8")
        found = sorted(set(re.findall(r"\b(?:19|20)\d{2}-[a-z0-9-]{3,}\b", source)))
        # Comments may name an id as an example; code may not key off one.
        offenders = [
            eid for eid in found if f'"{eid}"' in source or f"'{eid}'" in source
        ]
        self.assertEqual(offenders, [])


class CorpusCoverageTests(unittest.TestCase):
    """The check that was missing: a scraped election with no registry entry."""

    def test_every_election_directory_has_a_registry_entry(self):
        data_root = REPO_ROOT / "data"
        if not data_root.is_dir():
            self.skipTest("no local corpus — data/ is gitignored")
        known = {e["id"] for e in REGISTRY}
        on_disk = {p.name for p in data_root.iterdir() if p.is_dir() or p.is_symlink()}
        self.assertEqual(
            sorted(on_disk - known),
            [],
            "scraped election(s) with no scraper/elections.json entry — "
            "they would render as raw slugs in the dashboard",
        )


if __name__ == "__main__":
    unittest.main()
