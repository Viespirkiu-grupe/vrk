"""scripts/person_index_files.py: the split index is the old index, losslessly.

The page fetches the person index as a list file and a details file (issue
#186, step 2). Python reads the two joined, and "the index equals what the
code produces" is only checkable through the split if joining gives back
exactly what build_person_index.build_index() returned -- same values, same
key order, same bytes. Every test here holds that from a different side: a
hand-made index carrying every key, an index the builder itself produced from
records, and, when it has been built, the real one in dashboard/.
"""

from __future__ import annotations

import gzip
import importlib.util
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parents[1]


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


files = _load("person_index_files", REPO_ROOT / "scripts" / "person_index_files.py")
index_tests = _load("test_person_index", REPO_ROOT / "tests" / "test_person_index.py")


def compact(value) -> bytes:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def hand_made() -> dict:
    """Every person and candidacy key, in the order the builder writes them."""
    return {
        "elections": [{"id": "2016-seimo", "date": "2016-10-09"}, {"id": "2019-prezidento", "date": "2019-05-12"}],
        "unregisteredElections": [],
        "parties": {"lsdp": {"n": "LSDP", "t": "partija"}, "ts-lkd": {"n": "TS-LKD", "t": "partija"}},
        "municipalities": ["Vilniaus m."],
        "constituencies": ["Naujamiesčio"],
        "campaigns": [{"k": "lsdp-2016", "d": 1200.5, "n": 71}],
        "nationalities": [{"id": "lietuviai", "label": "lietuviai"}],
        "stats": {"persons": 3},
        "people": [
            {
                "k": "JONAS JONAITIS|1970-01-01", "pid": "p1", "ak": ["JONAS JONAITIS|?"],
                "n": "Jonas JONAITIS", "b": "1970-01-01",
                "e": [
                    {
                        "id": "2016-seimo", "c": "jonas-1", "w": True, "m": [1000, None, 25000.5, 1000],
                        "lt": True, "ds": True, "p": "ts-lkd", "sv": 0, "r": "tm", "wt": True, "wm": False,
                        "wp": "Vilniaus universitetas", "ed": 9, "v": 1234, "cv": 4321, "ap": 0, "ck": 0, "tb": 0,
                    },
                    {"id": "2019-prezidento", "c": "jonas-2", "w": False},
                ],
                "ph": 1,
            },
            # Keyed by an older spelling, so the key travels as `kn`.
            {"k": "ONA PETRAITYTĖ|1980-02-02", "pid": "p2", "n": "Ona PETRAITIENĖ", "b": "1980-02-02",
             "e": [{"id": "2016-seimo", "c": "ona-1", "p": "lsdp"}]},
            # No birth date: the key ends in `?`, the shown birth is null.
            {"k": "PETRAS PETRAITIS|?", "pid": "p3", "n": "Petras PETRAITIS", "b": None,
             "e": [{"id": "2019-prezidento", "c": "petras-1"}]},
        ],
        "portraits": {"v": "abc", "n": 1},
    }


class SplitTests(unittest.TestCase):
    def test_join_inverts_split_to_the_byte(self):
        index = hand_made()
        listing, details = files.split_index(index)
        self.assertEqual(compact(files.join_index(listing, details)), compact(index))

    def test_the_list_carries_only_what_the_list_needs(self):
        listing, details = files.split_index(hand_made())
        self.assertNotIn("campaigns", listing)
        self.assertEqual(details["campaigns"], hand_made()["campaigns"])
        self.assertEqual(listing["partyIds"], ["lsdp", "ts-lkd"])
        jonas, ona, petras = listing["people"]
        self.assertEqual(set(jonas), {"pid", "n", "b", "ph", "ak", "e"})
        self.assertEqual(jonas["e"][0], {"ei": 0, "pi": 1, "w": True, "sv": 0, "ap": 0, "tb": 0, "wm": False, "wt": True, "r": "tm"})
        self.assertEqual(jonas["e"][1], {"ei": 1, "w": False})
        self.assertEqual(ona["kn"], "ONA PETRAITYTĖ|1980-02-02")
        self.assertEqual(petras["kn"], "PETRAS PETRAITIS|?")
        self.assertNotIn("kn", jonas)
        self.assertEqual(details["people"][0][0], {
            "wp": "Vilniaus universitetas", "m": [1000, None, 25000.5, 1000], "c": "jonas-1",
            "lt": True, "ed": 9, "v": 1234, "cv": 4321, "ck": 0, "ds": True,
        })
        self.assertEqual(details["people"][2], [{"c": "petras-1"}])
        self.assertEqual(listing["build"], details["build"])

    def test_an_unknown_key_fails_the_split(self):
        # A key the split does not place would silently vanish from both.
        index = hand_made()
        index["people"][0]["e"][0]["zz"] = 1
        with self.assertRaisesRegex(ValueError, "zz"):
            files.split_index(index)

    def test_files_from_two_builds_do_not_join(self):
        listing, _ = files.split_index(hand_made())
        other = hand_made()
        other["stats"]["persons"] = 4
        _, details = files.split_index(other)
        with self.assertRaisesRegex(ValueError, "build"):
            files.join_index(listing, details)

    def test_the_index_the_builder_produces_round_trips(self):
        # Built from records by build_person_index itself, so the key order
        # tested is the builder's and not this file's idea of it.
        build = index_tests.build_person_index
        record = index_tests._record
        year_only = record("Jonas JONAITIS")
        year_only["normalized"]["anketa"] = {"gimimo-metai": 1936}
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for eid, cid, rec in (
                ("2016-seimo", "a", record("Jonas JONAITIS", "1970-01-01")),
                ("2020-seimo", "a", record("Jonas JONAITIS", "1970-01-01")),
                ("2020-seimo", "b", record("Ona ONAITĖ")),
                ("1996-spalio-20-seimo", "c", year_only),
            ):
                (root / eid).mkdir(exist_ok=True)
                (root / eid / f"{cid}-{eid}.json").write_text(json.dumps(dict(rec, candidateId=cid), ensure_ascii=False), encoding="utf-8")
            index = build.build_index(root, overrides={"decisions": []})
        listing, details = files.split_index(index)
        self.assertEqual(compact(files.join_index(listing, details)), compact(index))


class WriteTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.out = Path(self._tmp.name)

    def test_the_files_their_copies_and_the_version(self):
        written = files.write_index(hand_made(), self.out)
        version = json.loads((self.out / files.VERSION_NAME).read_text(encoding="utf-8"))
        self.assertEqual({k: written[k] for k in ("build", "list", "details")}, version)
        for key, name in (("list", files.LIST_NAME), ("details", files.DETAILS_NAME)):
            with self.subTest(name):
                path = self.out / name
                body = path.read_bytes()
                self.assertEqual(version[key], files.content_hash(body))
                gz = path.with_name(name + ".gz")
                self.assertEqual(gzip.decompress(gz.read_bytes()), body)
                # The server sends a copy only when it is not older.
                self.assertEqual(gz.stat().st_mtime_ns, path.stat().st_mtime_ns)
                br = path.with_name(name + ".br")
                if br.exists():
                    self.assertEqual(br.stat().st_mtime_ns, path.stat().st_mtime_ns)
        self.assertEqual(compact(files.load_index(self.out)), compact(hand_made()))

    def test_without_brotli_gzip_alone(self):
        with mock.patch.object(files, "_brotli", return_value=None):
            written = files.write_index(hand_made(), self.out)
        self.assertNotIn("br", written["sizes"]["list"])
        self.assertTrue((self.out / (files.LIST_NAME + ".gz")).is_file())
        self.assertFalse((self.out / (files.LIST_NAME + ".br")).exists())

    def test_an_unchanged_rebuild_keeps_the_mtimes(self):
        # Last-Modified is the mtime: an unchanged file must keep answering 304.
        files.write_index(hand_made(), self.out)
        paths = [self.out / n for n in (files.LIST_NAME, files.DETAILS_NAME, files.VERSION_NAME)]
        for path in paths:
            os.utime(path, ns=(1_000_000_000, 1_000_000_000))
        files.write_index(hand_made(), self.out)
        self.assertEqual([p.stat().st_mtime_ns for p in paths], [1_000_000_000] * 3)

    def test_a_changed_details_file_leaves_the_list_alone(self):
        # The build id changes with any change, so both files are rewritten;
        # the version file then names both new hashes.
        first = files.write_index(hand_made(), self.out)
        changed = hand_made()
        changed["people"][0]["e"][0]["wp"] = "Kauno technologijos universitetas"
        second = files.write_index(changed, self.out)
        self.assertNotEqual(first["details"], second["details"])
        self.assertNotEqual(first["build"], second["build"])
        self.assertEqual(compact(files.load_index(self.out)), compact(changed))


BUILT = REPO_ROOT / "dashboard"


@unittest.skipUnless(files.index_exists(BUILT), "dashboard/people-list.json not built -- python scripts/build_person_index.py")
class BuiltIndexTests(unittest.TestCase):
    def test_the_built_files_are_the_split_of_their_join(self):
        listing = (BUILT / files.LIST_NAME).read_bytes()
        details = (BUILT / files.DETAILS_NAME).read_bytes()
        again = files.split_index(files.join_index(json.loads(listing), json.loads(details)))
        self.assertEqual(compact(again[0]), listing)
        self.assertEqual(compact(again[1]), details)
        version = json.loads((BUILT / files.VERSION_NAME).read_text(encoding="utf-8"))
        self.assertEqual(version["list"], files.content_hash(listing))
        self.assertEqual(version["details"], files.content_hash(details))


if __name__ == "__main__":
    unittest.main()
