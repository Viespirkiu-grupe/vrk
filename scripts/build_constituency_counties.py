"""Which counties each single-mandate constituency name lies in, from VRK's own precinct lists.

Issue #217: the dashboard's constituency filter groups its 136 names by county
(apskritis), the way #213 groups municipalities. A name does not say where it
is -- 79 of the 136 name no municipality (Antakalnio, Dainavos, Sėlos rytinė),
and Dainavos was a Kaunas city district until 2016 and Prienai-Birštonas-Alytus
district land from 2020 -- so the county is read, not inferred. VRK publishes
one precinct list per Seimas election ("Rinkimų apygardų ir apylinkių sąrašas
ankstesniuose rinkimuose", https://www.vrk.lt/lt/rinkimu-apygardu-ir-apylinkiu-sarasas-ankstesniuose-rinkimuose):
every precinct with its district number, district name and municipality. This
script reads the eight lists of 1996-2024, joins each precinct's municipality
to its county through scraper/municipalities.json (#213: Registrų centras's
Address Register), and writes scraper/constituency_counties.json -- per name,
every county any of its maps touched and, as the evidence, the municipalities
and precinct counts per map.

A name's counties are the union over the maps it was used in, because the
facet is a name and not a boundary: a 2008 Kelmės candidate and a 2012 one
sit in the same row, and the row belongs under each county either map
reached. By-elections ran on their term's general map (the 2017 Anykščių–
Panevėžio vote on 2016's, the 2023 Raseinių–Kėdainių vote on 2020's), and
every by-election name is also a general-election name, so the eight lists
cover every name but one: Pasaulio lietuvių, the 2020+ district of voters
abroad, which has no precincts in Lithuania and no county. It is listed with
an empty county list, and the filter puts it in its own labelled group.

    python scripts/build_constituency_counties.py --source DIR           # compare with the file, exit 1 on drift
    python scripts/build_constituency_counties.py --source DIR --update  # rewrite the file

DIR holds the eight .xlsx files as VRK publishes them (SOURCES gives each
URL and the SHA-256 the file was read at); the file is checked in, so a
clone needs them only to re-derive it.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import unicodedata
import xml.etree.ElementTree as ET
import zipfile
from collections import defaultdict
from pathlib import Path
from typing import Any
from urllib.parse import quote

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scraper.shared import municipalities  # noqa: E402
from scraper.shared.apygardos import normalize_name  # noqa: E402

OUTPUT = Path("scraper/constituency_counties.json")
FORMS = Path("docs/constituency-forms.tsv")
_BASE = "https://vrk.lt/fs/prd/p/2026-03/"

#: The general election each precinct list belongs to, its published file
#: name, and the SHA-256 it was read at (2026-10-24).
SOURCES: dict[str, dict[str, str]] = {
    "1996": {"election": "1996-spalio-20-seimo", "sha256": "6361458c15c3572a648382ffc94b15096ff62e7d48820fad46573a3eea013927"},
    "2000": {"election": "2000-seimo", "sha256": "5096c27cd097023fdf6264428bdc36d3e7b1bbf440c8011356a9ef660a116a3a"},
    "2004": {"election": "2004-seimo", "sha256": "aa227fae22b59ad4fd0112110bafea69c2522d8d58d841bb22845f83c919959c"},
    "2008": {"election": "2008-seimo", "sha256": "e7cc8b72218cf09942fcc4e7946abb757a87356f217b459b5b5a16ac3d9cfb28"},
    "2012": {"election": "2012-seimo", "sha256": "f8b7649e766b0d925d3a719f64517f0e017c4905af88144f88108d7c402b5524"},
    "2016": {"election": "2016-seimo", "sha256": "0103d80baab6583a65556e40edcf5c4949c296684a2f25ebced11320219cdc22"},
    "2020": {"election": "2020-seimo", "sha256": "226e7ab4e64d0c9480fa6ab01fd018b8b0675ab757587a939dd5c59280b06692"},
    "2024": {"election": "2024-seimo", "sha256": "a54aa0aae7f5bd19f3a3d9afc70093a1c5add0f27a2d1b8d555878b09df78bac"},
}


def file_name(year: str) -> str:
    return f"{year}m. LR Seimo rinkimų apylinkių sąrašas.xlsx"


def source_url(year: str) -> str:
    return _BASE + quote(file_name(year))


#: Municipality spellings the lists use that the registry has no alias for:
#: the 1996/2000 lists' "Kupiškio rajonas" (nominative), and the 2004 list's
#: bare "Širvintų" on all 24 Širvintai precincts.
MUNICIPALITY_FORMS = {"Kupiškio rajonas": "Kupiškio rajono", "Širvintų": "Širvintų rajono"}

#: Where a list names a district differently from the corpus's cards. 1996's
#: Nr. 67 is "Prienų" on every 1996 candidate card (apgtl.htm-1+67) and
#: "Prienų–Birštono" in the list, Birštonas having become its own
#: municipality in 1995; 2012 is the first election the cards call it that.
DISTRICT_NAMES = {("1996", "Prienų–Birštono"): "Prienų"}

#: Names no list carries, and why they have no county.
NO_COUNTY = {
    "Pasaulio lietuvių": "the district of voters abroad (2020 and 2024, Nr. 72): no precinct lies in Lithuania",
}

_NS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"


def _column(ref: str) -> int:
    number = 0
    for letter in re.match(r"[A-Z]+", ref).group(0):
        number = number * 26 + ord(letter) - 64
    return number - 1


def read_xlsx(path: Path) -> list[list[str | None]]:
    """The first sheet's rows, read with the standard library (the lists are
    plain tables: shared strings and numbers, no formulas)."""
    with zipfile.ZipFile(path) as archive:
        strings = []
        if "xl/sharedStrings.xml" in archive.namelist():
            for item in ET.fromstring(archive.read("xl/sharedStrings.xml")).iter(f"{_NS}si"):
                strings.append("".join(t.text or "" for t in item.iter(f"{_NS}t")))
        rows = []
        for row in ET.fromstring(archive.read("xl/worksheets/sheet1.xml")).iter(f"{_NS}row"):
            cells: dict[int, str] = {}
            for cell in row.iter(f"{_NS}c"):
                value = cell.find(f"{_NS}v")
                if cell.get("t") == "inlineStr":
                    cells[_column(cell.get("r"))] = "".join(t.text or "" for t in cell.iter(f"{_NS}t"))
                elif value is not None:
                    text = value.text or ""
                    cells[_column(cell.get("r"))] = strings[int(text)] if cell.get("t") == "s" else text
            if cells:
                rows.append([cells.get(i) for i in range(max(cells) + 1)])
        return rows


def corpus_names(repo_root: Path) -> set[str]:
    names = set()
    for line in (repo_root / FORMS).read_text(encoding="utf-8").splitlines()[1:]:
        fields = line.split("\t")
        if len(fields) > 2 and fields[2]:
            names.add(fields[2])
    return names


def derive(repo_root: Path, source: Path) -> dict[str, Any]:
    registry = municipalities.entries()
    order = municipalities.counties()
    maps: dict[str, dict[str, dict[str, int]]] = defaultdict(lambda: defaultdict(lambda: defaultdict(int)))
    for year, meta in SOURCES.items():
        path = source / file_name(year)
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        if digest != meta["sha256"]:
            raise SystemExit(f"{path}: SHA-256 {digest}, expected {meta['sha256']} -- VRK republished it; review the change")
        rows = read_xlsx(path)
        if [unicodedata.normalize("NFC", h or "") for h in rows[0][:5]] != [
            "Apygardos nr.", "Apygardos pavadinimas", "Apylinkės nr.", "Apylinkės pavadinimas", "Savivaldybė",
        ]:
            raise SystemExit(f"{path}: unexpected header {rows[0]}")
        for row in rows[1:]:
            district, municipality = row[1], row[4]
            name = normalize_name(district)
            name = DISTRICT_NAMES.get((year, name), name)
            body = municipalities.match(MUNICIPALITY_FORMS.get(municipality, municipality))
            if not name or not body:
                raise SystemExit(f"{path}: unresolved row {row}")
            maps[name][year][registry[body]["name"]] += 1

    names = corpus_names(repo_root)
    missing = names - set(maps) - set(NO_COUNTY)
    unused = set(maps) - names
    if missing or unused:
        raise SystemExit(f"names no list covers: {sorted(missing)}; list names the corpus lacks: {sorted(unused)}")

    county_of = municipalities.county_by_name()
    entries: dict[str, Any] = {}
    for name in sorted(names):
        if name in NO_COUNTY:
            entries[name] = {"counties": [], "note": NO_COUNTY[name]}
            continue
        per_map = {year: dict(sorted(maps[name][year].items())) for year in sorted(maps[name])}
        counties = {county_of[body] for bodies in per_map.values() for body in bodies}
        entries[name] = {"counties": sorted(counties, key=order.index), "maps": per_map}
    return entries


def render(entries: dict[str, Any]) -> str:
    sources = {year: {**meta, "url": source_url(year)} for year, meta in SOURCES.items()}
    changed = [
        name for name, entry in entries.items()
        if len({tuple(sorted({municipalities.county_by_name()[b] for b in bodies})) for bodies in entry.get("maps", {}).values()}) > 1
    ]
    document = {
        "_comment": (
            "The county (apskritis) of every single-mandate constituency name (issue #217), for the dashboard's "
            "grouped filter. Derived by scripts/build_constituency_counties.py, not by reading the names: VRK's "
            "own precinct list for each Seimas election, 1996-2024 (`sources`; published at "
            "https://www.vrk.lt/lt/rinkimu-apygardu-ir-apylinkiu-sarasas-ankstesniuose-rinkimuose), gives every "
            "precinct's district and municipality, and scraper/municipalities.json (#213) gives each "
            "municipality's county. `counties` is the union over every map the name was used in, in the "
            "registry's population order -- a name is not a boundary, and a district that touched two counties "
            "is listed under both; `maps` is the evidence, the municipalities and their precinct counts per "
            "general election (by-elections ran on their term's map). Names whose counties differ between "
            "maps are listed in `changedBetweenMaps`; the sharpest is Dainavos, a Kaunas city district through "
            "2016 and the Prienai-Birštonas-Alytus district from 2020. Two precinct-list entries are read "
            "explicitly (the script's DISTRICT_NAMES and MUNICIPALITY_FORMS): 1996's Nr. 67 is 'Prienų' on the "
            "cards and 'Prienų–Birštono' in the list, and the 1996/2000 'Kupiškio rajonas' and 2004 bare "
            "'Širvintų' are Kupiškis and Širvintai district. A name with an empty `counties` list has a `note` "
            "saying why; the filter groups it apart."
        ),
        "sources": sources,
        "changedBetweenMaps": changed,
        "entries": entries,
    }
    return json.dumps(document, ensure_ascii=False, indent=2) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--source", type=Path, required=True, help="directory holding VRK's eight precinct lists")
    parser.add_argument("--update", action="store_true", help=f"rewrite {OUTPUT}")
    args = parser.parse_args()
    repo_root = Path(__file__).resolve().parents[1]
    text = render(derive(repo_root, args.source))
    target = repo_root / OUTPUT
    if args.update:
        target.write_text(text, encoding="utf-8")
        print(f"wrote {OUTPUT}")
        return 0
    if target.exists() and target.read_text(encoding="utf-8") == text:
        print(f"{OUTPUT} matches the precinct lists")
        return 0
    print(f"{OUTPUT} differs from what the precinct lists give; re-run with --update and review the diff")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
