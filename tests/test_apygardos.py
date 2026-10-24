"""The constituency normaliser (issue #133): four label eras, one name per district.

315 raw labels over 9,309 candidacies -- "Akmenės - Joniškio", "Akmenės
Joniškio", "Aukštaitijos (Nr. 28)", "Aukštaitijos Nr. 33", "33. Aukštaitijos"
-- and 2,980 rows that said "Daugiamandatė" where the candidate stood on the
list alone. `docs/constituency-forms.tsv` is the measured table of every
published form; on a clone it holds the corpus's spellings to the rule.
"""

from __future__ import annotations

import unittest
from pathlib import Path

import local_data

from scraper.shared import municipalities
from scraper.shared.apygardos import (
    DASHLESS_ARCHIVE,
    apygarda,
    counties_of,
    entry_of,
    group_order,
    groups_of,
    is_multi_mandate,
    load_counties,
    normalize_name,
    number_of,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
FORMS_TABLE = REPO_ROOT / "docs" / "constituency-forms.tsv"


def forms_table_rows() -> list[tuple[str, int, str, str, str]]:
    rows = []
    for line in FORMS_TABLE.read_text(encoding="utf-8").splitlines():
        if not line.strip() or line.startswith("form\t"):
            continue
        form, records, name, number, elections = (line.split("\t") + [""] * 5)[:5]
        rows.append((form, int(records), name, number, elections))
    return rows


class NameTests(unittest.TestCase):
    def test_every_era_of_one_district_is_one_name(self):
        for label in ("Aukštaitijos", "Aukštaitijos (Nr. 28)", "Aukštaitijos Nr. 33", "33. Aukštaitijos", "Aukštaitijos apygarda"):
            with self.subTest(label):
                self.assertEqual(normalize_name(label), "Aukštaitijos")

    def test_every_dash_form_is_the_en_dash(self):
        for label in ("Akmenės - Joniškio", "Akmenės-Joniškio", "Akmenės–Joniškio", "Akmenės — Joniškio", "Akmenės Joniškio"):
            with self.subTest(label):
                self.assertEqual(normalize_name(label), "Akmenės–Joniškio")

    def test_a_two_word_district_is_not_joined(self):
        self.assertEqual(normalize_name("Šiaulių kaimiškoji"), "Šiaulių kaimiškoji")
        self.assertEqual(normalize_name("Naujosios Vilnios (Nr. 10)"), "Naujosios Vilnios")
        self.assertEqual(normalize_name("27. Panevėžio vakarinė"), "Panevėžio vakarinė")

    def test_vrks_own_typos_resolve(self):
        self.assertEqual(normalize_name("Raseinių–Kėdainių( 42)"), "Raseinių–Kėdainių")
        self.assertEqual(normalize_name("Varėnos - Eišiškių (Nr.70)"), "Varėnos–Eišiškių")
        self.assertEqual(normalize_name("Žirmūnų (Nr.4)"), "Žirmūnų")

    def test_the_multi_mandate_marker_is_not_a_district(self):
        for label in ("Daugiamandatė", "Daugiamandatė, šioje apygardoje išrinktas Seimo nariu."):
            with self.subTest(label):
                self.assertTrue(is_multi_mandate(label))
                self.assertIsNone(normalize_name(label))
        self.assertFalse(is_multi_mandate("Dainavos"))

    def test_nothing_is_none(self):
        for value in (None, "", "   ", 42):
            self.assertIsNone(normalize_name(value))

    def test_the_dashless_aliases_map_to_themselves_dashed(self):
        for dashless, dashed in DASHLESS_ARCHIVE.items():
            with self.subTest(dashless):
                self.assertEqual(normalize_name(dashed), dashed)
                self.assertEqual(normalize_name(dashless), dashed)
                self.assertIn("–", dashed)


class NumberTests(unittest.TestCase):
    def test_the_number_is_read_from_any_position(self):
        self.assertEqual(number_of("4. Žirmūnų"), 4)
        self.assertEqual(number_of("Žirmūnų (Nr. 4)"), 4)
        self.assertEqual(number_of("Žirmūnų Nr. 4"), 4)
        self.assertEqual(number_of("Raseinių–Kėdainių( 42)"), 42)
        self.assertIsNone(number_of("Žirmūnų"))
        self.assertIsNone(number_of(None))


class DerivedTests(unittest.TestCase):
    def test_the_records_own_number_wins_over_the_label(self):
        self.assertEqual(
            apygarda("Šiaulių kaimiškoji", 45),
            {"apygarda": "Šiaulių kaimiškoji", "apygardos-numeris": 45, "apygarda-raw": "Šiaulių kaimiškoji"},
        )
        self.assertEqual(apygarda("Dzūkijos (Nr. 69)"), {"apygarda": "Dzūkijos", "apygardos-numeris": 69, "apygarda-raw": "Dzūkijos (Nr. 69)"})
        self.assertEqual(apygarda("Dzūkijos (Nr. 69)", "70")["apygardos-numeris"], 70)

    def test_a_list_only_row_has_no_constituency_and_no_number(self):
        self.assertEqual(apygarda("Daugiamandatė", 3), {"apygarda": None, "apygardos-numeris": None, "apygarda-raw": "Daugiamandatė"})
        self.assertEqual(apygarda(None), {"apygarda": None, "apygardos-numeris": None, "apygarda-raw": None})


class FormsTableTests(unittest.TestCase):
    def test_every_measured_form_resolves_as_the_table_says(self):
        rows = forms_table_rows()
        self.assertGreater(len(rows), 200)
        for form, _records, name, number, _elections in rows:
            with self.subTest(form):
                self.assertEqual(normalize_name(form) or "", name)
                self.assertEqual(str(number_of(form) or ""), number)

    def test_the_entries_column_names_the_era_split_forms(self):
        # Issue #219: a form whose name is split into eras lists the entries
        # its candidacies land in; every other form leaves it empty.
        noted = {}
        for line in FORMS_TABLE.read_text(encoding="utf-8").splitlines()[1:]:
            form, _records, name, _number, elections, entries = line.split("\t")
            if entries:
                noted[form] = entries
                self.assertEqual(entries, ",".join(sorted({entry_of(name, e) for e in elections.split(",")})))
        self.assertEqual(noted, {
            "67. Dainavos": "Dainavos (nuo 2020)", "Dainavos": "Dainavos (iki 2016)",
            "Dainavos (Nr. 16)": "Dainavos (iki 2016)", "Dainavos Nr. 67": "Dainavos (nuo 2020)",
        })

    def test_the_multi_mandate_forms_resolve_to_no_district(self):
        rows = forms_table_rows()
        self.assertTrue(any(form.startswith("Daugiamandat") and name == "" for form, _, name, _, _ in rows))

    def test_every_dashless_alias_is_a_published_form(self):
        forms = {form for form, *_ in forms_table_rows()}
        self.assertEqual(sorted(set(DASHLESS_ARCHIVE) - forms), [])

    def test_the_corpus_holds_no_form_the_table_lacks(self):
        # A sample of every Seimas election's records against the table.
        local_data.require_corpus()
        import json

        from scraper.shared.kandidatura import kandidatura

        forms = {form for form, *_ in forms_table_rows()}
        registry = {e["id"]: e for e in json.loads((REPO_ROOT / "scraper" / "elections.json").read_text(encoding="utf-8"))["elections"]}
        unknown = set()
        for eid, entry in registry.items():
            if entry["kind"] != "seimo" or not (REPO_ROOT / "data" / eid).is_dir():
                continue
            paths = sorted(p for p in (REPO_ROOT / "data" / eid).glob("*.json") if p.name != "anomalies.jsonl")
            for path in paths[:: max(1, len(paths) // 60)]:
                raw = kandidatura(json.loads(path.read_text(encoding="utf-8")), "seimo")["apygarda-raw"]
                if raw and raw not in forms:
                    unknown.add(raw)
        self.assertEqual(sorted(unknown), [], "run scripts/constituency_report.py --update")


class CountyTests(unittest.TestCase):
    """Every district name lies in at least one of the 10 counties (issue
    #217), read from VRK's precinct lists rather than from the name."""

    def setUp(self):
        self.registry = load_counties()
        self.names = {name for _form, _records, name, _number, _elections in forms_table_rows() if name}

    def test_the_file_covers_every_name_the_corpus_publishes(self):
        # 136 names, 137 entries: Dainavos is two eras (issue #219).
        self.assertEqual(len(self.names), 136)
        self.assertEqual(len(self.registry["entries"]), 137)
        self.assertEqual({entry.get("name", label) for label, entry in self.registry["entries"].items()}, self.names)

    def test_every_name_has_a_county_and_every_county_is_one_of_the_10(self):
        for name in sorted(self.registry["entries"]):
            with self.subTest(name):
                entry = self.registry["entries"][name]
                if name == "Pasaulio lietuvių":
                    # The district abroad: no precinct in Lithuania, so no county.
                    self.assertEqual(entry["counties"], [])
                    self.assertTrue(entry["note"])
                    continue
                self.assertGreaterEqual(len(entry["counties"]), 1)
                self.assertTrue(set(entry["counties"]) <= set(municipalities.counties()))
                self.assertEqual(entry["counties"], sorted(entry["counties"], key=municipalities.counties().index))

    def test_the_counties_are_the_union_of_the_evidence(self):
        county_of = municipalities.county_by_name()
        for name, entry in self.registry["entries"].items():
            with self.subTest(name):
                evidence = {county_of[body] for bodies in entry.get("maps", {}).values() for body in bodies}
                self.assertEqual(set(entry["counties"]), evidence)

    def test_the_names_a_heuristic_would_get_wrong(self):
        for name, counties in {
            # City districts and regional names that name no municipality.
            "Antakalnio": ["Vilniaus"], "Centro": ["Kauno"], "Baltijos": ["Klaipėdos"], "Aušros": ["Šiaulių"],
            "Aukštaitijos": ["Panevėžio"], "Sėlos rytinė": ["Panevėžio", "Utenos"], "Karšuvos": ["Tauragės"],
            "Jotvingių": ["Alytaus"], "Deltuvos šiaurinė": ["Vilniaus", "Panevėžio", "Utenos"],
            # A city district through 2016, Prienai-Birštonas-Alytus land from
            # 2020: two entries (issue #219), and the bare name is neither.
            "Dainavos (iki 2016)": ["Kauno"], "Dainavos (nuo 2020)": ["Kauno", "Alytaus"], "Dainavos": [],
            # Districts across a county line.
            "Anykščių–Panevėžio": ["Panevėžio", "Utenos"], "Kelmės–Šilalės": ["Šiaulių", "Tauragės"],
            "Varėnos–Eišiškių": ["Vilniaus", "Alytaus"], "Pietų Žemaitijos": ["Klaipėdos", "Telšių", "Tauragės"],
            # Ukmergė and Elektrėnai are Vilnius county; Birštonas is Kaunas county.
            "Ukmergės": ["Vilniaus"], "Trakų–Elektrėnų": ["Vilniaus"], "Prienų–Birštono": ["Kauno", "Alytaus"],
        }.items():
            self.assertEqual(counties_of(name), counties, name)
        self.assertEqual(counties_of("Nėra tokios"), [])
        self.assertEqual(counties_of(None), [])

    def test_the_changed_names_are_the_ones_whose_maps_disagree(self):
        self.assertEqual(
            self.registry["changedBetweenMaps"],
            ["Deltuvos pietinė", "Deltuvos šiaurinė", "Kelmės", "Prienų", "Prienų–Birštono"],
        )

    def test_the_groups_are_the_per_map_placement_over_the_evidence(self):
        # Issue #217: each map places the name -- in a big city's group when
        # that city municipality holds a strict majority of the map's
        # precincts, else under every county the map touches -- and the name
        # is listed under the union. Recomputed here for all 136 names.
        cities = self.registry["cities"]
        self.assertEqual(list(cities), ["Vilniaus", "Kauno", "Klaipėdos", "Šiaulių", "Panevėžio"])
        order = self.registry["groupOrder"]
        self.assertEqual(order[:4], ["Vilniaus miestas", "Vilniaus apskritis", "Kauno miestas", "Kauno apskritis"])
        self.assertEqual(len(order), 15)
        self.assertEqual(group_order(), order)
        county_of = municipalities.county_by_name()
        for name, entry in self.registry["entries"].items():
            with self.subTest(name):
                placed = {}
                for year, bodies in entry.get("maps", {}).items():
                    total = sum(bodies.values())
                    city = [c for c, body in cities.items() if 2 * bodies.get(body, 0) > total]
                    placed[year] = (
                        [f"{city[0]} miestas"] if city
                        else sorted({f"{county_of[b]} apskritis" for b in bodies}, key=order.index)
                    )
                self.assertEqual(entry.get("placedBy", {}), placed)
                union = sorted({g for groups in placed.values() for g in groups}, key=order.index)
                self.assertEqual(entry["groups"], union)
                self.assertEqual(groups_of(name), union)
                if name != "Pasaulio lietuvių":
                    self.assertTrue(union)

    def test_the_city_groups_hold_the_expected_districts(self):
        by_group = {}
        for name, entry in self.registry["entries"].items():
            for group in entry["groups"]:
                by_group.setdefault(group, []).append(name)
        self.assertEqual({g: len(n) for g, n in by_group.items() if g.endswith("miestas")},
                         {"Vilniaus miestas": 22, "Kauno miestas": 12, "Klaipėdos miestas": 4,
                          "Šiaulių miestas": 3, "Panevėžio miestas": 3})
        for name, groups in {
            # A strict city majority on every map: the city group alone.
            "Vilniaus pietinė": ["Vilniaus miestas"], "Savanorių": ["Kauno miestas"], "Dainų": ["Šiaulių miestas"],
            "Danės": ["Klaipėdos miestas"],
            # A city minority on every map: the county groups alone.
            "Garliavos": ["Kauno apskritis"], "Aukštaitijos": ["Panevėžio apskritis"], "Kuršėnų–Dainų": ["Šiaulių apskritis"],
            # Maps that disagree: a Klaipėda city majority in 1996 and from
            # 2016, a minority in 2000-2012.
            "Pajūrio": ["Klaipėdos miestas", "Klaipėdos apskritis"],
            # A name reused for a different place, one entry per era (#219):
            # a Kaunas city district through 2016, Prienai-Birštonas-Alytus
            # land from 2020.
            "Dainavos (iki 2016)": ["Kauno miestas"],
            "Dainavos (nuo 2020)": ["Kauno apskritis", "Alytaus apskritis"],
        }.items():
            self.assertEqual(groups_of(name), groups, name)
        both = sorted(n for n, e in self.registry["entries"].items()
                      if any(g.endswith("miestas") for g in e["groups"]) and any(g.endswith("apskritis") for g in e["groups"]))
        self.assertEqual(both, ["Pajūrio"])
        self.assertEqual(groups_of("Nėra tokios"), [])

    def test_every_source_is_a_general_election_of_the_registry(self):
        import json

        ids = {e["id"] for e in json.loads((REPO_ROOT / "scraper" / "elections.json").read_text(encoding="utf-8"))["elections"]}
        for year, source in self.registry["sources"].items():
            self.assertIn(source["election"], ids)
            self.assertRegex(source["sha256"], r"^[0-9a-f]{64}$")
            self.assertTrue(source["url"].startswith("https://vrk.lt/"))


def _build_script():
    import importlib.util

    spec = importlib.util.spec_from_file_location("build_constituency_counties", REPO_ROOT / "scripts" / "build_constituency_counties.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class EraTests(unittest.TestCase):
    """A name reused for a different place is split into eras (issue #219):
    wherever two consecutive maps the name was used in share no municipality,
    a pre-2000 body counting as the bodies the 2000 reform made of it."""

    def setUp(self):
        self.registry = load_counties()
        # Every name's maps, the eras merged back.
        self.maps: dict[str, dict[str, dict[str, int]]] = {}
        for label, entry in self.registry["entries"].items():
            self.maps.setdefault(entry.get("name", label), {}).update(entry.get("maps", {}))

    def test_the_rule_over_the_evidence_splits_dainavos_alone(self):
        successors = {
            entry["name"]: {entries_by_id["name"] for entries_by_id in (municipalities.entries()[s] for s in entry.get("successors", []))}
            for entry in municipalities.entries().values()
        }

        def territory(bodies):
            return set(bodies).union(*(successors[b] for b in bodies))

        split = {}
        for name, per_map in self.maps.items():
            years = sorted(per_map)
            cuts = [(a, b) for a, b in zip(years, years[1:]) if not territory(per_map[a]) & territory(per_map[b])]
            if cuts:
                split[name] = cuts
        self.assertEqual(split, {"Dainavos": [("2016", "2020")]})
        self.assertEqual(self.registry["eras"], {"Dainavos": ["Dainavos (iki 2016)", "Dainavos (nuo 2020)"]})
        self.assertEqual(sorted(self.registry["entries"]["Dainavos (iki 2016)"]["maps"]), ["1996", "2000", "2004", "2008", "2012", "2016"])
        self.assertEqual(sorted(self.registry["entries"]["Dainavos (nuo 2020)"]["maps"]), ["2020", "2024"])

    def test_boundary_changes_that_keep_territory_do_not_split(self):
        for name in ("Deltuvos pietinė", "Deltuvos šiaurinė", "Kelmės", "Prienų", "Prienų–Birštono", "Pajūrio"):
            with self.subTest(name):
                self.assertIn(name, self.registry["entries"])
                self.assertNotIn(name, self.registry["eras"])
                self.assertGreater(len(self.registry["entries"][name]["maps"]), 1)

    def test_the_2000_merger_is_not_a_new_place(self):
        # Marijampolės and Suvalkijos: 1996 in the pre-2000 city and district
        # bodies, from 2000 in the municipalities the reform made of them.
        # Read literally, the rule would split both.
        for name in ("Marijampolės", "Suvalkijos"):
            with self.subTest(name):
                self.assertNotIn(name, self.registry["eras"])
                self.assertIn("1996", self.registry["entries"][name]["maps"])
                self.assertIn("2000", self.registry["entries"][name]["maps"])

    def test_the_script_rule_on_synthetic_maps(self):
        script = _build_script()
        self.assertEqual(script.eras({"2016": {"A": 1}, "2020": {"B": 1}, "2024": {"B": 1, "C": 1}}), [["2016"], ["2020", "2024"]])
        self.assertEqual(script.eras({"2012": {"A": 1, "B": 1}, "2016": {"B": 1}}), [["2012", "2016"]])
        self.assertEqual(script.eras({"2000": {"A": 1}, "2008": {"B": 1}, "2016": {"C": 1}}), [["2000"], ["2008"], ["2016"]])
        self.assertEqual(
            [script.era_label("X", era, i, 3) for i, era in enumerate([["2000"], ["2008", "2012"], ["2016"]])],
            ["X (iki 2000)", "X (2008–2012)", "X (nuo 2016)"],
        )
        self.assertEqual(script.era_label("X", ["2000", "2004"], 0, 1), "X")

    def test_entry_of_follows_the_map_the_election_ran_on(self):
        self.assertEqual(entry_of("Dainavos", "1996-spalio-20-seimo"), "Dainavos (iki 2016)")
        self.assertEqual(entry_of("Dainavos", "2016-seimo"), "Dainavos (iki 2016)")
        # A by-election runs on its term's general map, whatever its year.
        self.assertEqual(entry_of("Dainavos", "2019-rugsejo-8-seimo"), "Dainavos (iki 2016)")
        self.assertEqual(entry_of("Dainavos", "2020-seimo"), "Dainavos (nuo 2020)")
        self.assertEqual(entry_of("Dainavos", "2024-seimo"), "Dainavos (nuo 2020)")
        self.assertEqual(entry_of("Kelmės", "2024-seimo"), "Kelmės")
        self.assertEqual(entry_of("Kelmės", None), "Kelmės")
        self.assertIsNone(entry_of(None, "2024-seimo"))
        with self.assertRaises(ValueError):
            entry_of("Dainavos", "2099-seimo")

    def test_every_seimas_candidacy_maps_to_exactly_one_entry(self):
        local_data.require_corpus()
        import json

        from scraper.shared.kandidatura import kandidatura

        registry = json.loads((REPO_ROOT / "scraper" / "elections.json").read_text(encoding="utf-8"))["elections"]
        map_year = {source["election"]: year for year, source in self.registry["sources"].items()}
        dainavos: dict[str, set[str]] = {}
        resolved = 0
        for election in registry:
            directory = REPO_ROOT / "data" / election["id"]
            if election["kind"] != "seimo" or not directory.is_dir():
                continue
            for path in sorted(directory.glob("*.json")):
                name = kandidatura(json.loads(path.read_text(encoding="utf-8")), "seimo")["apygarda"]
                if not name:
                    continue
                entry = entry_of(name, election["id"])
                self.assertIn(entry, self.registry["entries"], (path.name, name))
                self.assertEqual(self.registry["entries"][entry].get("name", entry), name)
                # The entry holds the map this election ran on (the district
                # abroad has no precinct list, so no maps at all).
                year = map_year[election.get("parent") or election["id"]]
                self.assertIn(year, self.registry["entries"][entry].get("maps", {year: None}), (path.name, entry))
                resolved += 1
                if name == "Dainavos":
                    dainavos.setdefault(election["id"], set()).add(entry)
        self.assertGreater(resolved, 5000)
        self.assertEqual(dainavos["2016-seimo"], {"Dainavos (iki 2016)"})
        self.assertEqual(dainavos["2020-seimo"], {"Dainavos (nuo 2020)"})


if __name__ == "__main__":
    unittest.main()
