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


def _segment(marker: int, payload: bytes) -> bytes:
    return bytes([0xFF, marker]) + (len(payload) + 2).to_bytes(2, "big") + payload


#: A structurally valid JPEG with an Exif block (what 9,889 sidecars carry):
#: the public profile ships it without the block, under the original hash.
EXIF = _segment(0xE1, b"Exif\x00\x00MM\x00*\x00\x00\x00\x08\x00\x00")
JPEG_CLEAN = (
    b"\xff\xd8"
    + _segment(0xE0, b"JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00")
    + _segment(0xDA, b"\x01\x01\x00\x00\x3f\x00")
    + b"\x12\x34\xff\xd9"
)
JPEG = JPEG_CLEAN[:2] + EXIF + JPEG_CLEAN[2:]
JPEG_SHA = hashlib.sha256(JPEG).hexdigest()

#: A campaign block with the treasurer's contact in both layers, and the
#: campaign contact line repeating the treasurer's phone -- what the public
#: profile removes (issue #142).
TREASURER_PHONE = "+370 600 00000"
TREASURER_EMAIL = "izdininke@example.lt"


def campaign_block() -> tuple[dict, dict]:
    normalized = [
        {
            "statusas": "Savarankiškas",
            "kontaktai": {"telefonas-pasiteirauti": TREASURER_PHONE, "el-pastas": "stabas@example.lt"},
            "izdininkas": {"vardas-pavarde": "Ona Iždininkė", "telefonas": TREASURER_PHONE, "el-pastas": TREASURER_EMAIL, "imones-pavadinimas": None, "imones-kodas": None},
            "auditorius": {"vardas-pavarde": "UAB Auditas", "telefonas": "+370 5 000000", "el-pastas": "info@auditas.example", "imones-pavadinimas": "UAB Auditas", "imones-kodas": "123"},
        }
    ]
    raw = {
        "campaigns": [
            {
                "campaignKey": "dalyvis-1",
                "participant": {"inquiryPhone": TREASURER_PHONE, "email": "stabas@example.lt"},
                "treasurer": {"name": "Ona Iždininkė", "phone": TREASURER_PHONE, "email": TREASURER_EMAIL},
                "auditor": {"name": "UAB Auditas", "phone": "+370 5 000000", "email": "info@auditas.example"},
            }
        ]
    }
    return normalized, raw


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
        normalized_campaign, raw_campaign = campaign_block()
        ona["normalized"]["politines-kampanijos-dalyvio-duomenys"] = normalized_campaign
        ona["rawData"]["politinesKampanijosDalyvioDuomenys"] = raw_campaign

        jonas = make_record("jonas-b-2", "Jonas B")
        jonas["rawData"]["profile"]["photoSrc"] = "photos/jonas.jpg"
        jonas["rawData"]["profile"]["photoMeta"] = {
            "mime": "image/jpeg", "bytes": len(JPEG), "sha256": JPEG_SHA,
        }
        # The envelope's third optional key (issue #89): on every record with
        # a retained page, and the reason no build could run from 2026-09-01
        # until the builder learned it.
        jonas["provenance"] = {
            "fetchedAt": "2026-08-18T10:40:58+00:00",
            "parsedAt": "2026-09-03T09:51:58+00:00",
            "parserCommit": "959f055",
            "sourceSha256": "0" * 64,
            "schemaVersion": 1,
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

    def test_records_round_trip_less_only_the_public_profile_redactions(self):
        connection = self.corpus_connection()
        rows = connection.execute("SELECT * FROM records ORDER BY candidate_id").fetchall()
        self.assertEqual(len(rows), 3)
        for row in rows:
            self.assertEqual(row["record_file"], f"{row['candidate_id']}.json")
            rebuilt = dist_mod.reconstruct_record(row)
            if row["candidate_id"] != "ona-a-1":
                self.assertEqual(rebuilt, self.records[row["candidate_id"]])
                continue
            # Ona's campaign block: the treasurer's and auditor's phone and
            # e-mail are gone in both layers, the contact line kept only
            # where it was not the treasurer's own number, everything else
            # -- names, company, status -- as it was.
            campaign = rebuilt["normalized"]["politines-kampanijos-dalyvio-duomenys"][0]
            self.assertEqual(campaign["izdininkas"], {"vardas-pavarde": "Ona Iždininkė", "imones-pavadinimas": None, "imones-kodas": None})
            self.assertEqual(campaign["auditorius"], {"vardas-pavarde": "UAB Auditas", "imones-pavadinimas": "UAB Auditas", "imones-kodas": "123"})
            self.assertEqual(campaign["kontaktai"], {"el-pastas": "stabas@example.lt"})
            raw = rebuilt["rawData"]["politinesKampanijosDalyvioDuomenys"]["campaigns"][0]
            self.assertEqual(raw["treasurer"], {"name": "Ona Iždininkė"})
            self.assertEqual(raw["auditor"], {"name": "UAB Auditas"})
            self.assertEqual(raw["participant"], {"email": "stabas@example.lt"})
            self.assertNotIn(TREASURER_PHONE, json.dumps(rebuilt))
            self.assertNotIn(TREASURER_EMAIL, json.dumps(rebuilt))
            # And nothing else moved.
            expected = json.loads(json.dumps(self.records["ona-a-1"]))
            dist_mod.redact_record(expected)
            self.assertEqual(rebuilt, expected)

    def test_photos_deduplicated_verified_and_stripped(self):
        connection = self.corpus_connection()
        photos = connection.execute("SELECT sha256, mime, bytes, stripped, stripped_sha256, data FROM photos").fetchall()
        self.assertEqual(len(photos), 1)
        # The archive's hash is the key, whatever was done to the bytes on
        # the way out; the stored bytes are the picture without its Exif.
        self.assertEqual(photos[0]["sha256"], JPEG_SHA)
        self.assertEqual(photos[0]["mime"], "image/jpeg")
        self.assertEqual(photos[0]["data"], JPEG_CLEAN)
        self.assertEqual(photos[0]["bytes"], len(JPEG_CLEAN))
        self.assertEqual(photos[0]["stripped"], 1)
        self.assertEqual(photos[0]["stripped_sha256"], hashlib.sha256(JPEG_CLEAN).hexdigest())
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
             "party_predecessors", "records", "photos", "anomalies"},
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
        # The profile and what it did (issue #142).
        self.assertEqual(manifest["profile"], "public")
        self.assertEqual(manifest["redaction"]["paths"], list(dist_mod.PUBLIC_PROFILE_DROPS))
        self.assertEqual(manifest["redaction"]["conditionalPaths"], list(dist_mod.PUBLIC_PROFILE_CONDITIONAL))
        # 4 treasurer/auditor values per layer, plus the contact phone that
        # repeated the treasurer's, per layer.
        self.assertEqual(manifest["redaction"]["valuesRemoved"], 10)
        self.assertEqual(manifest["counts"]["photosStripped"], 1)
        self.assertEqual(manifest["counts"]["photosMetadataUntouched"], 0)
        self.assertEqual(manifest["counts"]["photosMalformed"], 0)
        self.assertEqual(manifest["counts"]["photoBytes"], len(JPEG_CLEAN))
        self.assertEqual(
            set(manifest["artifacts"]), set(dist_mod.RELEASE_ARTIFACTS)
        )

    def test_manifest_carries_the_terms(self):
        # Issue #138: the licence, the attribution and the terms URL ride
        # with the assets, so a downloaded directory says what may be done
        # with it without the repository at hand.
        manifest = json.loads((self.dist / "MANIFEST.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["license"], dist_mod.CODE_LICENSE)
        self.assertEqual(manifest["dataLicense"], dist_mod.DATA_LICENSE)
        self.assertEqual(manifest["attribution"], dist_mod.ATTRIBUTION)
        self.assertEqual(manifest["terms"], dist_mod.TERMS_URL)
        self.assertEqual(manifest["source"], dist_mod.SOURCE_URL)
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


class FullProfileBuild(unittest.TestCase):
    """`--profile full` is the archive verbatim: no redaction, no stripping."""

    @classmethod
    def setUpClass(cls):
        cls.root = make_repo_root()
        cls.addClassCleanup(shutil.rmtree, cls.root, ignore_errors=True)
        data_dir = cls.root / "data" / ELECTION
        (data_dir / "photos").mkdir()
        (data_dir / "photos" / "ona.jpg").write_bytes(JPEG)
        ona = make_record("ona-a-1", "Ona A")
        ona["rawData"]["profile"]["photoSrc"] = "photos/ona.jpg"
        ona["rawData"]["profile"]["photoMeta"] = {"mime": "image/jpeg", "bytes": len(JPEG), "sha256": JPEG_SHA}
        normalized_campaign, raw_campaign = campaign_block()
        ona["normalized"]["politines-kampanijos-dalyvio-duomenys"] = normalized_campaign
        ona["rawData"]["politinesKampanijosDalyvioDuomenys"] = raw_campaign
        cls.record = ona
        write_record(data_dir, ona)
        cls.dist = cls.root / "dist"
        cls.exit_code = dist_mod.build_distribution(cls.root, cls.dist, [ELECTION], profile="full")

    def test_the_record_and_the_portrait_are_verbatim(self):
        self.assertEqual(self.exit_code, 0)
        connection = sqlite3.connect(self.dist / "vrk-corpus.sqlite")
        connection.row_factory = sqlite3.Row
        self.addCleanup(connection.close)
        row = connection.execute("SELECT * FROM records").fetchone()
        self.assertEqual(dist_mod.reconstruct_record(row), self.record)
        photo = connection.execute("SELECT * FROM photos").fetchone()
        self.assertEqual((photo["data"], photo["stripped"], photo["stripped_sha256"]), (JPEG, 0, JPEG_SHA))
        manifest = json.loads((self.dist / "MANIFEST.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["profile"], "full")
        self.assertEqual(manifest["redaction"], {"paths": [], "conditionalPaths": [], "valuesRemoved": 0})
        self.assertEqual(manifest["counts"]["photosStripped"], 0)

    def test_an_unknown_profile_is_refused(self):
        with self.assertRaises(ValueError):
            dist_mod.write_corpus_sqlite(self.root / "x.sqlite", empty_sqlite(self.root / "e.sqlite"), self.root / "data", [ELECTION], profile="anonymous")


class RedactionTests(unittest.TestCase):
    """`redact_record` on the shapes the corpus has."""

    def test_nothing_to_redact_is_zero_and_leaves_the_record_alone(self):
        record = make_record("a", "A")
        before = json.loads(json.dumps(record))
        self.assertEqual(dist_mod.redact_record(record), 0)
        self.assertEqual(record, before)

    def test_the_contact_line_is_kept_where_it_is_not_a_third_partys(self):
        record = make_record("a", "A")
        normalized, raw = campaign_block()
        normalized[0]["kontaktai"] = {"telefonas-pasiteirauti": "+370 5 111111", "el-pastas": "kandidatas@example.lt"}
        raw["campaigns"][0]["participant"] = {"inquiryPhone": "+370 5 111111", "email": "kandidatas@example.lt"}
        record["normalized"]["politines-kampanijos-dalyvio-duomenys"] = normalized
        record["rawData"]["politinesKampanijosDalyvioDuomenys"] = raw
        self.assertEqual(dist_mod.redact_record(record), 8)
        self.assertEqual(record["normalized"]["politines-kampanijos-dalyvio-duomenys"][0]["kontaktai"], {"telefonas-pasiteirauti": "+370 5 111111", "el-pastas": "kandidatas@example.lt"})
        self.assertEqual(record["rawData"]["politinesKampanijosDalyvioDuomenys"]["campaigns"][0]["participant"], {"inquiryPhone": "+370 5 111111", "email": "kandidatas@example.lt"})

    def test_every_campaign_entry_is_redacted_not_just_the_first(self):
        record = make_record("a", "A")
        normalized, raw = campaign_block()
        record["normalized"]["politines-kampanijos-dalyvio-duomenys"] = normalized + json.loads(json.dumps(normalized))
        record["rawData"]["politinesKampanijosDalyvioDuomenys"] = raw
        dist_mod.redact_record(record)
        for entry in record["normalized"]["politines-kampanijos-dalyvio-duomenys"]:
            self.assertNotIn("telefonas", entry["izdininkas"])
            self.assertNotIn("el-pastas", entry["auditorius"])


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



class PortraitKeyTests(unittest.TestCase):
    """`record_photo` reads whichever key the family writes the reference under."""

    def _root(self) -> Path:
        root = Path(tempfile.mkdtemp(prefix="vrk-dist-photo-"))
        self.addCleanup(shutil.rmtree, root, ignore_errors=True)
        (root / "photos").mkdir()
        (root / "photos" / "alvydas.jpg").write_bytes(JPEG)
        return root

    def test_the_archive_family_photo_url_sidecar_is_stored(self) -> None:
        # The 1996-1999 Seimas archive profile has `photoUrl`, not `photoSrc`;
        # once archived (issue #118) it points at the sidecar like the rest.
        root = self._root()
        record = make_record("alvydas", "Alvydas")
        record["rawData"]["profile"] = {
            "candidateDisplayName": "Alvydas",
            "photoUrl": "photos/alvydas.jpg",
            "photoMeta": {"mime": "image/jpeg", "bytes": len(JPEG), "sha256": JPEG_SHA},
        }
        digest, mime, raw = dist_mod.record_photo(record, root / "alvydas.json")
        self.assertEqual((digest, mime, raw), (JPEG_SHA, "image/jpeg", JPEG))

    def test_a_tried_and_failed_url_stays_a_url_with_nothing_to_store(self) -> None:
        root = self._root()
        record = make_record("alvydas", "Alvydas")
        record["rawData"]["profile"] = {
            "photoUrl": "https://www.vrk.lt/gone.jpg",
            "photoMeta": {"url": "https://www.vrk.lt/gone.jpg", "error": "HTTP 404"},
        }
        self.assertIsNone(dist_mod.record_photo(record, root / "alvydas.json"))

if __name__ == "__main__":
    unittest.main()
