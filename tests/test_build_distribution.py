"""The distribution builder (issue #94) on a synthetic three-record corpus.

`scripts/build_distribution.py` is what a `corpus-YYYY-MM-DD` release ships;
these tests pin its contract without a corpus present: the records table
round-trips the original JSON, photos are stored once and content-verified,
the manifest's checksums match the artifacts it names, and every corruption
the builder claims to refuse — a missing sidecar, a hash mismatch, an
envelope key it does not know, a resurrected base64 portrait — actually
fails the build instead of shipping.
"""

from __future__ import annotations

import csv
import gzip
import hashlib
import importlib.util
import json
import shutil
import sqlite3
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

_spec = importlib.util.spec_from_file_location(
    "build_distribution", REPO_ROOT / "scripts" / "build_distribution.py"
)
dist_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(dist_mod)

#: Registry and resolver files the builder reads relative to --repo-root.
#: They are tracked (code, not corpus), so copying them into the temp root
#: keeps the test runnable on a checkout that has never scraped anything.
REPO_FILES = (
    "docs/concept-map.json",
    "scraper/elections.json",
    "scraper/person_overrides.json",
    "scraper/parties.json",
)

ELECTION = "2016-seimo"
JPEG = b"\xff\xd8\xff\xe0" + b"not-a-real-portrait-but-hashes-like-one"
JPEG_SHA = hashlib.sha256(JPEG).hexdigest()


def make_record(candidate_id: str, name: str) -> dict:
    return {
        "electionId": ELECTION,
        "candidateId": candidate_id,
        "candidateName": name,
        "source": {"candidateSourceUrl": f"https://www.vrk.lt/{candidate_id}"},
        "kandidatavimas": {"isrinktas": False},
        "rawData": {"profile": {"fields": {"Pavadinimas": "reikšmė"}}},
        "normalized": {"profilis": {"vardas-pavarde": name}},
    }


def write_record(data_dir: Path, record: dict) -> Path:
    path = data_dir / f"{record['candidateId']}.json"
    path.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def make_repo_root() -> Path:
    root = Path(tempfile.mkdtemp(prefix="vrk-dist-test-"))
    for rel in REPO_FILES:
        target = root / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(REPO_ROOT / rel, target)
    (root / "data" / ELECTION).mkdir(parents=True)
    return root


def empty_sqlite(path: Path) -> Path:
    sqlite3.connect(path).close()
    return path


class DistributionBuild(unittest.TestCase):
    """One subset build over three records; every artifact checked."""

    @classmethod
    def setUpClass(cls):
        cls.root = make_repo_root()
        cls.addClassCleanup(shutil.rmtree, cls.root, ignore_errors=True)
        data_dir = cls.root / "data" / ELECTION
        photos = data_dir / "photos"
        photos.mkdir()
        # The same bytes under two names: the photos table must hold ONE row.
        (photos / "ona.jpg").write_bytes(JPEG)
        (photos / "jonas.jpg").write_bytes(JPEG)

        ona = make_record("ona-a-1", "Ona A")
        ona["rawData"]["profile"]["photoSrc"] = "photos/ona.jpg"
        ona["rawData"]["profile"]["photoMeta"] = {
            "mime": "image/jpeg", "bytes": len(JPEG), "sha256": JPEG_SHA,
        }
        ona["normalized"]["profilis"]["nuotrauka"] = "photos/ona.jpg"
        ona["candidateNote"] = "Išrinkta"

        jonas = make_record("jonas-b-2", "Jonas B")
        jonas["rawData"]["profile"]["photoSrc"] = "photos/jonas.jpg"
        jonas["rawData"]["profile"]["photoMeta"] = {
            "mime": "image/jpeg", "bytes": len(JPEG), "sha256": JPEG_SHA,
        }

        petras = make_record("petras-c-3", "Petras C")
        petras["rawData"]["profile"]["photoSrc"] = "https://www.vrk.lt/petras.jpg"
        del petras["kandidatavimas"]

        cls.records = {r["candidateId"]: r for r in (ona, jonas, petras)}
        for record in cls.records.values():
            write_record(data_dir, record)
        (data_dir / "anomalies.jsonl").write_text(
            json.dumps({"stage": "parse", "type": "TestEvent", "electionId": ELECTION})
            + "\n",
            encoding="utf-8",
        )

        cls.dist = cls.root / "dist"
        cls.exit_code = dist_mod.build_distribution(cls.root, cls.dist, [ELECTION])

    def corpus_connection(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.dist / "vrk-corpus.sqlite")
        connection.row_factory = sqlite3.Row
        self.addCleanup(connection.close)
        return connection

    def test_build_succeeds_and_writes_every_artifact(self):
        self.assertEqual(self.exit_code, 0)
        for name in (
            "candidacies.csv.gz",
            "campaigns.csv.gz",
            "vrk.sqlite",
            "vrk.sqlite.gz",
            "vrk-corpus.sqlite",
            "vrk-corpus.sqlite.gz",
            "MANIFEST.json",
        ):
            self.assertTrue((self.dist / name).is_file(), name)

    def test_records_round_trip_losslessly(self):
        connection = self.corpus_connection()
        rows = connection.execute("SELECT * FROM records ORDER BY candidate_id").fetchall()
        self.assertEqual(len(rows), 3)
        for row in rows:
            self.assertEqual(
                dist_mod.reconstruct_record(row), self.records[row["candidate_id"]]
            )
            self.assertEqual(row["record_file"], f"{row['candidate_id']}.json")

    def test_photos_deduplicated_and_verified(self):
        connection = self.corpus_connection()
        photos = connection.execute("SELECT sha256, mime, bytes, data FROM photos").fetchall()
        self.assertEqual(len(photos), 1)
        self.assertEqual(photos[0]["sha256"], JPEG_SHA)
        self.assertEqual(photos[0]["mime"], "image/jpeg")
        self.assertEqual(photos[0]["bytes"], len(JPEG))
        self.assertEqual(photos[0]["data"], JPEG)
        by_candidate = dict(
            connection.execute("SELECT candidate_id, photo_sha256 FROM records")
        )
        self.assertEqual(by_candidate["ona-a-1"], JPEG_SHA)
        self.assertEqual(by_candidate["jonas-b-2"], JPEG_SHA)
        self.assertIsNone(by_candidate["petras-c-3"])  # URL-form stays a URL

    def test_the_elections_table_carries_the_term_parent(self):
        # The registry as a table (issue #122): `parent` is the general
        # election a by-election fills a seat of, NULL for a general.
        connection = self.corpus_connection()
        rows = connection.execute("SELECT id, kind, parent FROM elections").fetchall()
        self.assertEqual([(r["id"], r["kind"], r["parent"]) for r in rows], [(ELECTION, "seimo", None)])

    def test_corpus_database_carries_the_analysis_tables_too(self):
        connection = self.corpus_connection()
        tables = {
            row["name"]
            for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")
        }
        self.assertLessEqual(
            {"candidacies", "campaigns", "elections", "persons", "parties",
             "records", "photos", "anomalies"},
            tables,
        )
        self.assertEqual(
            connection.execute("SELECT COUNT(*) FROM candidacies").fetchone()[0], 3
        )
        anomalies = connection.execute("SELECT election_id, event_json FROM anomalies").fetchall()
        self.assertEqual(len(anomalies), 1)
        self.assertEqual(anomalies[0]["election_id"], ELECTION)
        self.assertEqual(json.loads(anomalies[0]["event_json"])["type"], "TestEvent")

    def test_manifest_checksums_match_the_artifacts(self):
        manifest = json.loads((self.dist / "MANIFEST.json").read_text(encoding="utf-8"))
        self.assertRegex(manifest["version"], r"^corpus-\d{4}-\d{2}-\d{2}$")
        self.assertTrue(manifest["parserCommit"])
        self.assertEqual(manifest["counts"]["records"], 3)
        self.assertEqual(manifest["counts"]["photos"], 1)
        self.assertEqual(manifest["counts"]["anomalies"], 1)
        self.assertEqual(manifest["recordsPerElection"], {ELECTION: 3})
        self.assertEqual(manifest["subset"], [ELECTION])
        self.assertEqual(
            set(manifest["artifacts"]), set(dist_mod.RELEASE_ARTIFACTS)
        )
        for name, meta in manifest["artifacts"].items():
            path = self.dist / name
            self.assertEqual(meta["bytes"], path.stat().st_size, name)
            self.assertEqual(meta["sha256"], dist_mod.sha256_file(path), name)

    def test_gzips_decompress_to_their_sources(self):
        with gzip.open(self.dist / "vrk-corpus.sqlite.gz", "rb") as handle:
            self.assertEqual(
                handle.read(), (self.dist / "vrk-corpus.sqlite").read_bytes()
            )
        with gzip.open(self.dist / "candidacies.csv.gz", "rt", encoding="utf-8") as handle:
            rows = list(csv.reader(handle))
        self.assertEqual(len(rows), 4)  # header + three candidacies
        self.assertEqual(rows[0][:2], ["person_id", "election_id"])


class RefusedCorruption(unittest.TestCase):
    """Each corruption the builder documents refusing must actually refuse."""

    def build_one(self, mutate) -> None:
        root = Path(tempfile.mkdtemp(prefix="vrk-dist-bad-"))
        self.addCleanup(shutil.rmtree, root, ignore_errors=True)
        data_dir = root / "data" / ELECTION
        data_dir.mkdir(parents=True)
        record = make_record("kazys-x-9", "Kazys X")
        mutate(record, data_dir)
        write_record(data_dir, record)
        dist_mod.write_corpus_sqlite(
            root / "corpus.sqlite",
            empty_sqlite(root / "base.sqlite"),
            root / "data",
            [ELECTION],
        )

    def test_missing_sidecar_fails(self):
        def mutate(record, data_dir):
            record["rawData"]["profile"]["photoSrc"] = "photos/gone.jpg"

        with self.assertRaisesRegex(SystemExit, "no such sidecar"):
            self.build_one(mutate)

    def test_hash_mismatch_fails(self):
        def mutate(record, data_dir):
            (data_dir / "photos").mkdir()
            (data_dir / "photos" / "kazys.jpg").write_bytes(JPEG)
            record["rawData"]["profile"]["photoSrc"] = "photos/kazys.jpg"
            record["rawData"]["profile"]["photoMeta"] = {"sha256": "0" * 64}

        with self.assertRaisesRegex(SystemExit, "photoMeta.sha256"):
            self.build_one(mutate)

    def test_inline_base64_portrait_fails(self):
        def mutate(record, data_dir):
            record["rawData"]["profile"]["photoSrc"] = "data:;base64,AAAA"

        with self.assertRaisesRegex(SystemExit, "inline base64"):
            self.build_one(mutate)

    def test_unknown_envelope_key_fails(self):
        def mutate(record, data_dir):
            record["surpriseKey"] = 1

        with self.assertRaisesRegex(SystemExit, "unknown envelope key"):
            self.build_one(mutate)

    def test_election_id_mismatch_fails(self):
        def mutate(record, data_dir):
            record["electionId"] = "2020-seimo"

        with self.assertRaisesRegex(SystemExit, "does not match its directory"):
            self.build_one(mutate)

    def test_duplicate_candidate_id_fails(self):
        def mutate(record, data_dir):
            twin = make_record("kazys-x-9", "Kazys X")
            twin_path = data_dir / "kazys-x-9-antras.json"
            twin_path.write_text(
                json.dumps(twin, ensure_ascii=False) + "\n", encoding="utf-8"
            )

        with self.assertRaisesRegex(SystemExit, "share \\(election_id, candidate_id\\)"):
            self.build_one(mutate)


if __name__ == "__main__":
    unittest.main()
