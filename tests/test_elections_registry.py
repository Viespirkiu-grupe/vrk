"""The one registry of elections: scraper/elections.json.

Before it, an election's name and chronology lived in three hand-maintained
lists across two files -- ELECTION_ORDER in scripts/build_person_index.py plus
ELECTION_LABELS and SHORT_LABELS in dashboard/index.html. Adding an election
meant editing all three, and the last additions edited none: the 2011
municipal general (16,400 records) was invisible to the dashboard and six more
elections rendered as raw slugs. These tests pin the registry's shape and,
when a local corpus is present, that every election in it has an entry --
which is the check that was missing. See GitHub issue #63.

The display fields then drifted in their own way: 55 entries written one
module at a time, with `shortName` mixing nominative and genitive, month and
no month, institution and place, and `name` sometimes carrying the day and
sometimes not (issue #121). NamingConventionTests pins one rule per field, so
a new entry either follows the convention or fails here.

The by-elections then had no home (issue #122): 28 of the 55 entries fill a
seat of some general election's term, and the dashboard treated all 55 as
peers, so selecting "2016 Seimas" silently left out the 2017-2019 seat-fills
for that same Seimas. TermGroupingTests pins the `parent` field that groups
them -- one mechanical rule, checked against the marker VRK itself puts in
the name.
"""

from __future__ import annotations

import collections
import datetime as dt
import importlib.util
import json
import re
import unittest
from pathlib import Path

from tests.dashboard_source import script_source

REPO_ROOT = Path(__file__).resolve().parents[1]
REGISTRY_PATH = REPO_ROOT / "scraper" / "elections.json"

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
        # `parent` is the one optional field; TermGroupingTests says exactly
        # which entries carry it.
        for entry in REGISTRY:
            with self.subTest(entry.get("id")):
                self.assertEqual(
                    set(entry) - {"parent"}, {"id", "date", "kind", "name", "shortName"}, entry.get("id")
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


#: The Lithuanian month names in the genitive, as a date reads in a heading
#: ("2019 m. kovo 3 d."), and their ASCII forms as an id spells them.
MONTHS_LT = (
    "sausio", "vasario", "kovo", "balandžio", "gegužės", "birželio",
    "liepos", "rugpjūčio", "rugsėjo", "spalio", "lapkričio", "gruodžio",
)
MONTHS_ASCII = (
    "sausio", "vasario", "kovo", "balandzio", "geguzes", "birzelio",
    "liepos", "rugpjucio", "rugsejo", "spalio", "lapkricio", "gruodzio",
)

#: The institution word of a shortName: one capitalised nominative per kind.
INSTITUTION = {
    "seimo": "Seimas",
    "savivaldybiu": "Savivaldybės",
    "prezidento": "Prezidentas",
    "ep": "EP",
    "mero": "Merai",
}

#: What follows the date in a `name`, per kind. A general election is the
#: bare body phrase; anything else opens with VRK's own marker -- `nauji`
#: (new) or `pakartotiniai` (repeat), `pakartotinis balsavimas` for the one
#: re-vote -- and a Seimas by-election closes with its constituencies.
#: One constituency ("Naujosios Vilnios apygardoje Nr. 10") or several
#: ("Žirmūnų Nr. 4, Gargždų Nr. 31 ir Žiemgalos Nr. 46 apygardose").
CONSTITUENCY = r"[^,]+? Nr\. \d+"
CONSTITUENCIES = (
    r"(?:[^,]+? apygardoje Nr\. \d+"
    r"|(?:" + CONSTITUENCY + r", )*" + CONSTITUENCY + r" ir " + CONSTITUENCY + r" apygardose)"
)
NAME_BODY = {
    "seimo": re.compile(
        r"^(?:Lietuvos Respublikos Seimo rinkimai"
        r"|(?:nauji|pakartotiniai) Lietuvos Respublikos Seimo rinkimai " + CONSTITUENCIES
        + r"(?: ir nauji rinkimai " + CONSTITUENCIES + r")?)$"
    ),
    "savivaldybiu": re.compile(
        r"^(?:savivaldybių tarybų(?: ir merų)? rinkimai"
        r"|pakartotiniai \S+ rajono savivaldybės tarybos(?: nario–mero)?"
        r"(?: ir \S+ rajono savivaldybės tarybos)? rinkimai)$"
    ),
    "prezidento": re.compile(r"^Respublikos Prezidento rinkimai$"),
    "ep": re.compile(r"^Europos Parlamento rinkimai$"),
    "mero": re.compile(
        r"^(?:nauji .+ savivaldyb(?:ės tarybos nario–mero|ių tarybų narių–merų|ės mero|ių merų) rinkimai"
        r"|\S+ savivaldybės mero rinkimų pakartotinis balsavimas)$"
    ),
}

#: Ids are frozen as of the newest election in the registry when issue #121
#: settled the conventions: an id names data/<id>/, the sitemaps, the module
#: constants, the release assets and the join key of every export, so the old
#: ones keep the slug shapes they were born with. Elections after this date
#: follow one pattern: `YYYY-<kind>` for a general election, and
#: `YYYY-<menuo>-<D>-<kind>[-<vieta>...]` for anything else.
ID_FREEZE_DATE = "2025-03-16"
GENERAL_ID = re.compile(r"^\d{4}-(?:seimo|savivaldybiu|prezidento|ep)$")
OTHER_ID = re.compile(
    r"^\d{4}-(?:" + "|".join(MONTHS_ASCII) + r")-[1-9]\d?-(?:seimo|savivaldybiu|prezidento|ep|mero)(?:-[a-z0-9]+)*$"
)


def date_in_words(iso: str) -> str:
    date = dt.date.fromisoformat(iso)
    return f"{date.year} m. {MONTHS_LT[date.month - 1]} {date.day} d."


def name_body(entry: dict) -> str:
    """The part of `name` after the date -- the date prefix is checked apart."""
    prefix = date_in_words(entry["date"]) + " "
    return entry["name"][len(prefix):] if entry["name"].startswith(prefix) else entry["name"]


def has_vrk_marker(entry: dict) -> bool:
    # VRK names every election that is not a general one as `nauji` (new),
    # `pakartotiniai` (repeat) or `pakartotinis balsavimas` (re-vote), and the
    # registry keeps that word in `name`.
    return re.search(r"\b(?:nauji|pakartotin\w*)\b", name_body(entry)) is not None


def is_general(entry: dict) -> bool:
    # A general election is one with no `parent` (issue #122). The name
    # marker was the test before the field existed; TermGroupingTests keeps
    # the two agreeing, so neither can drift from the other.
    return "parent" not in entry


def expected_short_name(entry: dict, registry: list[dict]) -> str:
    date = dt.date.fromisoformat(entry["date"])
    word = INSTITUTION[entry["kind"]]
    if is_general(entry):
        return f"{date.year} {word}"
    same_month = [
        other
        for other in registry
        if not is_general(other)
        and INSTITUTION[other["kind"]] == word
        and other["date"][:7] == entry["date"][:7]
    ]
    return f"{entry['date'] if len(same_month) > 1 else entry['date'][:7]} {word}"


class NamingConventionTests(unittest.TestCase):
    """One rule per display field, so the dropdown stops reading as a style
    lottery: `2016 Seimas` beside `2002 prezidento` beside `1997-12 Aukštaitija`
    beside `2003 Seimas (nauji)` was the state before issue #121."""

    def test_name_opens_with_the_registry_date_in_words(self):
        for entry in REGISTRY:
            with self.subTest(entry["id"]):
                self.assertTrue(
                    entry["name"].startswith(date_in_words(entry["date"]) + " "),
                    f"{entry['name']!r} should open with {date_in_words(entry['date'])!r}",
                )

    def test_name_body_follows_the_kind_template(self):
        for entry in REGISTRY:
            with self.subTest(entry["id"]):
                self.assertRegex(name_body(entry), NAME_BODY[entry["kind"]])

    def test_a_seimas_by_election_names_its_constituencies_and_a_general_does_not(self):
        for entry in REGISTRY:
            if entry["kind"] != "seimo":
                continue
            with self.subTest(entry["id"]):
                self.assertEqual("apygard" in entry["name"], not is_general(entry))

    def test_short_name_is_the_year_or_year_month_plus_the_institution(self):
        for entry in REGISTRY:
            with self.subTest(entry["id"]):
                self.assertEqual(entry["shortName"], expected_short_name(entry, REGISTRY))

    def test_short_names_are_unique(self):
        labels = [e["shortName"] for e in REGISTRY]
        self.assertEqual(sorted(set(labels)), sorted(labels))

    def test_the_day_reaches_a_short_name_only_where_the_month_collides(self):
        # The two June 2015 municipal repeats are the one collision; nothing
        # else should ever need the day, and generals never carry a month.
        dated = sorted(e["id"] for e in REGISTRY if re.match(r"^\d{4}-\d{2}-\d{2} ", e["shortName"]))
        self.assertEqual(
            dated,
            ["2015-birzelio-21-pakartotiniai-silutes", "2015-birzelio-7-pakartotiniai-sirvintos-trakai"],
        )
        for entry in REGISTRY:
            with self.subTest(entry["id"]):
                self.assertEqual(re.match(r"^\d{4} ", entry["shortName"]) is not None, is_general(entry))

    def test_the_generals_are_the_expected_twenty_seven(self):
        # Eight Seimas, eight municipal, six presidential and five EP general
        # elections; everything else is a by-election, a repeat or a re-vote.
        generals = collections.Counter(e["kind"] for e in REGISTRY if is_general(e))
        self.assertEqual(generals, {"seimo": 8, "savivaldybiu": 8, "prezidento": 6, "ep": 5})

    def test_ids_added_after_the_freeze_follow_the_slug_convention(self):
        for entry in REGISTRY:
            if entry["date"] <= ID_FREEZE_DATE:
                continue
            with self.subTest(entry["id"]):
                date = dt.date.fromisoformat(entry["date"])
                if is_general(entry):
                    self.assertRegex(entry["id"], GENERAL_ID)
                else:
                    self.assertRegex(entry["id"], OTHER_ID)
                    self.assertTrue(
                        entry["id"].startswith(f"{date.year}-{MONTHS_ASCII[date.month - 1]}-{date.day}-"),
                        entry["id"],
                    )

    def test_the_slug_convention_itself(self):
        # No election is newer than the freeze yet, so the rule above has
        # nothing to bite; this pins the patterns it will bite with.
        for good in ("2028-seimo", "2027-savivaldybiu", "2029-prezidento", "2029-ep"):
            self.assertRegex(good, GENERAL_ID)
        for good in ("2026-kovo-15-seimo-zirmunai", "2026-birzelio-7-mero-trakai", "2026-spalio-4-seimo"):
            self.assertRegex(good, OTHER_ID)
        for bad in ("2027-savivaldybiu-tarybu", "2026-03-15-seimo", "2026-kovo-05-seimo", "2026-kovo-15-meru"):
            self.assertIsNone(GENERAL_ID.match(bad) or OTHER_ID.match(bad), bad)


#: Which general election a seat-fill belongs to: the latest general of the
#: same family before it. There is no mayoral general -- the 2023
#: council-and-mayor ballot is `savivaldybiu` -- so a mayoral by-election
#: belongs to the municipal council term, and `mero` folds into it.
FAMILY = {"mero": "savivaldybiu"}


def family(entry: dict) -> str:
    return FAMILY.get(entry["kind"], entry["kind"])


def expected_parent(entry: dict, registry: list[dict]) -> str:
    earlier = [
        other
        for other in registry
        if is_general(other) and family(other) == family(entry) and other["date"] < entry["date"]
    ]
    return max(earlier, key=lambda other: other["date"])["id"]


class TermGroupingTests(unittest.TestCase):
    """`parent` groups the 28 by-elections, repeats and re-votes under the
    general election whose term they fill (issue #122): the dashboard lists
    the generals, folds the children under them, and selecting a general
    includes its seat-fills. One rule derives every parent, so a new entry
    cannot point at the wrong term."""

    def test_the_parent_and_the_vrk_name_marker_agree(self):
        # "No parent" is what makes an entry a general election; VRK's own
        # nauji / pakartotiniai marker in the name must say the same.
        for entry in REGISTRY:
            with self.subTest(entry["id"]):
                self.assertEqual("parent" in entry, has_vrk_marker(entry))

    def test_a_parent_is_a_registered_general_election(self):
        by_id = {e["id"]: e for e in REGISTRY}
        for entry in REGISTRY:
            if "parent" not in entry:
                continue
            with self.subTest(entry["id"]):
                self.assertIn(entry["parent"], by_id)
                self.assertTrue(is_general(by_id[entry["parent"]]), "a parent has no parent of its own")
                self.assertLess(by_id[entry["parent"]]["date"], entry["date"])

    def test_a_parent_is_the_latest_earlier_general_of_the_same_family(self):
        for entry in REGISTRY:
            if "parent" not in entry:
                continue
            with self.subTest(entry["id"]):
                self.assertEqual(entry["parent"], expected_parent(entry, REGISTRY))

    def test_grouping_is_by_term_not_by_kind(self):
        # Every mayoral by-election and re-vote belongs to a municipal
        # council term.
        by_id = {e["id"]: e for e in REGISTRY}
        mayoral = [e for e in REGISTRY if e["kind"] == "mero"]
        self.assertEqual(len(mayoral), 8)
        for entry in mayoral:
            with self.subTest(entry["id"]):
                self.assertEqual(by_id[entry["parent"]]["kind"], "savivaldybiu")

    def test_the_cases_the_issue_names(self):
        by_id = {e["id"]: e for e in REGISTRY}
        for child, parent in (
            ("2017-balandzio-23-seimo-anyksciai-panevezys", "2016-seimo"),
            ("2018-rugsejo-16-seimo-zanavykai", "2016-seimo"),
            # "pakartotiniai ir nauji" in one event: still one parent.
            ("2013-kovo-3-seimo-birzai-zarasai-ukmerge", "2012-seimo"),
            ("1997-birzelio-29-svenciniu-tarybos-pakartotiniai", "1997-kovo-23-savivaldybiu-tarybu"),
            ("2015-lapkricio-8-telsiu-mero", "2015-kovo-1-savivaldybiu"),
            # The Visaginas re-vote: the strongest case for never being a
            # top-level row.
            ("2023-geguzes-7-visagino-mero", "2023-kovo-5-savivaldybiu-tarybu-ir-meru"),
        ):
            with self.subTest(child):
                self.assertEqual(by_id[child]["parent"], parent)

    def test_the_children_are_the_expected_twenty_eight(self):
        # Seventeen Seimas seat-fills, three municipal repeats, eight mayoral
        # by-elections and re-votes; the presidency and the EP have none.
        children = collections.Counter(e["kind"] for e in REGISTRY if "parent" in e)
        self.assertEqual(children, {"seimo": 17, "savivaldybiu": 3, "mero": 8})
        self.assertEqual(len(REGISTRY), 27 + 28)


class DashboardCarriesNoElectionListTests(unittest.TestCase):
    """The point of the registry is that index.html stops duplicating it."""

    def test_no_hardcoded_label_maps_remain(self):
        source = script_source()
        for name in ("ELECTION_LABELS", "SHORT_LABELS", "ELECTION_ORDER"):
            self.assertNotIn(name, source)

    def test_no_election_id_is_hardcoded_in_the_dashboard(self):
        source = script_source()
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
