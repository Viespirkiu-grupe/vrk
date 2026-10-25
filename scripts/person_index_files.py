"""The person index on disk: a list file, a details file and a version file.

The page used to fetch one `people.json`, 30.8 MB of JSON and 7.35 MB of
gzip on a first visit, before it could show a single name (issue #186). It
now fetches what the list, the filters and the search need first and the
rest behind it:

- `people-list.json`: every top-level table except `campaigns`, plus per
  person `pid`, `n`, `b`, `ph`, `ak`, and per candidacy `ei` (an index into
  `elections`), `pi` (an index into `partyIds`, the sorted keys of
  `parties`), `w`, `sv`, `ap`, `tb`, `wm`, `wt` and `r`. The natural key `k`
  is left out, because the page rebuilds it as `NAME|birth` from `n` and
  `b`; `kn` carries it whole on the people where that would be wrong (a
  merged person keyed by an older spelling, or by a `~year` / `?` birth the
  shown date has since replaced).
- `people-details.json`: `campaigns`, and per person an array of per-
  candidacy `{wp, m, c, lt, ed, v, cv, ck, ds}`, aligned by position with
  the list's people and their `e`.
- `people-version.json`: the content hash of each, which the page puts on
  the two URLs (`?v=`) so the server may mark them immutable (see
  scripts/serve_dashboard.py), and the build id both files carry, so a page
  that caught one file from each of two builds can tell.

`join_index(split_index(x))` is `x`, key order included -- that is what
tests/test_person_index_files.py holds on the real index, and what keeps "the
index equals what the code produces" checkable through the split. Python
consumers read the joined form through `load_index()`; nothing writes or
reads a whole `people.json` any more.

Beside the list and details files the writer drops `.br` (Python's `brotli`
module, else the `brotli` command, quality 11) and `.gz` (gzip -9) copies
with the original's mtime, which the server sends as they are to a client
that accepts them.
"""

from __future__ import annotations

import gzip
import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scraper.shared.files import write_json  # noqa: E402

INDEX_DIR = Path("dashboard")
LIST_NAME = "people-list.json"
DETAILS_NAME = "people-details.json"
VERSION_NAME = "people-version.json"

#: The candidacy keys in the order build_person_index.py writes them. The
#: list keeps the facet keys, the details file everything the list does not
#: need until a record, a sum or a workplace search is asked for.
CANDIDACY_KEYS = ("id", "c", "w", "m", "lt", "ds", "p", "sv", "r", "wt", "wm", "wp", "ed", "v", "cv", "ap", "ck", "tb")
LIST_CANDIDACY_KEYS = ("w", "sv", "ap", "tb", "wm", "wt", "r")
DETAIL_CANDIDACY_KEYS = ("wp", "m", "c", "lt", "ed", "v", "cv", "ck", "ds")
#: The person keys in build order; `ph` is appended by the portrait pass.
PERSON_KEYS = ("k", "pid", "ak", "n", "b", "e", "ph")
LIST_PERSON_KEYS = ("pid", "n", "b", "ph", "ak")
#: The top-level tables that travel in the details file, not the list.
DETAIL_TABLES = ("campaigns",)

assert set(LIST_CANDIDACY_KEYS) | set(DETAIL_CANDIDACY_KEYS) | {"id", "p"} == set(CANDIDACY_KEYS)
assert not set(LIST_CANDIDACY_KEYS) & set(DETAIL_CANDIDACY_KEYS)


def default_key(person: dict) -> str:
    """The natural key the page derives from the list (`NAME|birth`)."""
    return f"{(person.get('n') or '').upper()}|{person.get('b') or ''}"


def build_id(index: dict) -> str:
    """What both files carry: a hash of the whole index they split from."""
    body = json.dumps(index, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return hashlib.blake2s(body, digest_size=6).hexdigest()


def content_hash(body: bytes) -> str:
    """The `?v=` of a file: the server computes the same over what it serves."""
    return hashlib.blake2s(body, digest_size=8).hexdigest()


def split_index(index: dict) -> tuple[dict, dict]:
    """The index as (list, details); `join_index` is the inverse."""
    build = build_id(index)
    election_index = {e["id"]: i for i, e in enumerate(index["elections"])}
    party_ids = sorted(index["parties"])
    party_index = {pid: i for i, pid in enumerate(party_ids)}
    unknown_keys = set()
    people = []
    details = []
    for person in index["people"]:
        unknown_keys |= set(person) - set(PERSON_KEYS)
        entry = {key: person[key] for key in LIST_PERSON_KEYS if key in person}
        if person["k"] != default_key(person):
            entry["kn"] = person["k"]
        rows = []
        detail_rows = []
        for e in person["e"]:
            unknown_keys |= set(e) - set(CANDIDACY_KEYS)
            row = {"ei": election_index[e["id"]]}
            if "p" in e:
                row["pi"] = party_index[e["p"]]
            row.update({key: e[key] for key in LIST_CANDIDACY_KEYS if key in e})
            rows.append(row)
            detail_rows.append({key: e[key] for key in DETAIL_CANDIDACY_KEYS if key in e})
        entry["e"] = rows
        people.append(entry)
        details.append(detail_rows)
    if unknown_keys:
        # A key the split does not know would be dropped from both files
        # without a word; name it here so it gets a side.
        raise ValueError(f"split_index: unknown index keys {sorted(unknown_keys)}")

    listing: dict[str, Any] = {"build": build}
    for key, value in index.items():
        if key in DETAIL_TABLES:
            continue
        if key == "people":
            listing["partyIds"] = party_ids
            listing["people"] = people
        else:
            listing[key] = value
    detail_doc: dict[str, Any] = {"build": build}
    for key in DETAIL_TABLES:
        if key in index:
            detail_doc[key] = index[key]
    detail_doc["people"] = details
    return listing, detail_doc


def join_index(listing: dict, details: dict) -> dict:
    """The one index again, in the key order build_person_index.py wrote."""
    if listing.get("build") != details.get("build"):
        raise ValueError(f"list build {listing.get('build')!r} is not details build {details.get('build')!r}")
    if len(listing["people"]) != len(details["people"]):
        raise ValueError("list and details disagree on the number of people")
    elections = listing["elections"]
    party_ids = listing["partyIds"]
    people = []
    for entry, detail_rows in zip(listing["people"], details["people"]):
        if len(entry["e"]) != len(detail_rows):
            raise ValueError(f"{entry['pid']}: list and details disagree on the candidacies")
        candidacies = []
        for row, detail in zip(entry["e"], detail_rows):
            merged = {**row, **detail, "id": elections[row["ei"]]["id"]}
            if "pi" in row:
                merged["p"] = party_ids[row["pi"]]
            candidacies.append({key: merged[key] for key in CANDIDACY_KEYS if key in merged})
        whole = {**entry, "k": entry.get("kn") or default_key(entry), "e": candidacies}
        people.append({key: whole[key] for key in PERSON_KEYS if key in whole})

    index: dict[str, Any] = {}
    for key, value in listing.items():
        if key in ("build", "partyIds"):
            continue
        if key == "nationalities" or (key == "people" and "campaigns" not in index):
            # campaigns sat just before nationalities in the build.
            for table in DETAIL_TABLES:
                if table in details and table not in index:
                    index[table] = details[table]
        index[key] = people if key == "people" else value
    return index


def _brotli(body: bytes) -> bytes | None:
    try:
        import brotli  # type: ignore[import-not-found]
    except ImportError:
        command = shutil.which("brotli")
        if not command:
            return None
        return subprocess.run([command, "-c", "-q", "11"], input=body, capture_output=True, check=True).stdout
    return brotli.compress(body, quality=11)


def _write_bytes(path: Path, body: bytes) -> None:
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_bytes(body)
    os.replace(tmp, path)


def _precompress(path: Path) -> dict[str, int]:
    """`.gz` and, when brotli is available, `.br` beside `path`, same mtime.

    A copy that could not be made this time is removed rather than left
    behind: the server sends a sibling only when it is not older than the
    file, and an older one from a previous build would then just be skipped,
    but there is no reason to keep it.
    """
    body = path.read_bytes()
    sizes = {"raw": len(body)}
    stat = path.stat()
    for suffix, compressed in ((".gz", gzip.compress(body, compresslevel=9, mtime=0)), (".br", _brotli(body))):
        target = path.with_name(path.name + suffix)
        if compressed is None:
            target.unlink(missing_ok=True)
            continue
        _write_bytes(target, compressed)
        os.utime(target, ns=(stat.st_atime_ns, stat.st_mtime_ns))
        sizes[suffix[1:]] = len(compressed)
    return sizes


def _write_if_changed(path: Path, data: Any) -> bool:
    """Write compact JSON unless the file already holds those bytes.

    An unchanged file keeps its mtime, which is what the server's
    Last-Modified answers with, so a rebuild with nothing new costs a
    visitor nothing.
    """
    body = json.dumps(data, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    if path.is_file() and path.read_bytes() == body:
        return False
    write_json(path, data, indent=None, separators=(",", ":"), newline=False)
    return True


def write_index(index: dict, out_dir: Path = INDEX_DIR) -> dict[str, Any]:
    """Write the list, the details, their compressed copies and the version.

    The version file goes last, so until it lands a page keeps asking for
    the previous hashes, which the server then answers `no-cache` rather
    than immutable. Returns the version document with the sizes beside it.
    """
    listing, details = split_index(index)
    out_dir.mkdir(parents=True, exist_ok=True)
    version: dict[str, Any] = {"build": listing["build"]}
    sizes = {}
    for key, name, doc in (("list", LIST_NAME, listing), ("details", DETAILS_NAME, details)):
        path = out_dir / name
        changed = _write_if_changed(path, doc)
        stat = path.stat()
        siblings_current = all(
            (path.with_name(path.name + s)).is_file() and path.with_name(path.name + s).stat().st_mtime >= stat.st_mtime
            for s in (".gz", ".br")
        )
        if changed or not siblings_current:
            sizes[key] = _precompress(path)
        else:
            sizes[key] = {"raw": stat.st_size, **{
                s: path.with_name(f"{path.name}.{s}").stat().st_size
                for s in ("gz", "br")
                if path.with_name(f"{path.name}.{s}").is_file()
            }}
        version[key] = content_hash(path.read_bytes())
    _write_if_changed(out_dir / VERSION_NAME, version)
    return {**version, "sizes": sizes}


def index_exists(index_dir: Path = INDEX_DIR) -> bool:
    return all((index_dir / name).is_file() for name in (LIST_NAME, DETAILS_NAME))


def load_index(index_dir: Path = INDEX_DIR) -> dict:
    """The whole index, joined from the list and details files."""
    listing = json.loads((index_dir / LIST_NAME).read_text(encoding="utf-8"))
    details = json.loads((index_dir / DETAILS_NAME).read_text(encoding="utf-8"))
    return join_index(listing, details)
