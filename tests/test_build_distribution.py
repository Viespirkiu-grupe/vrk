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
import unittest.mock
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


def make_record(candidate_id: str, name: str, note: str | None = ...) -> dict:
    """A record in the corpus's own key order.

    The order matters to the round trip: `reconstruct_record` rebuilds a
    record in this order so an unpacked tree is byte-comparable with a
    scraped one, and a fixture in a different order would make that
    untestable (issue #156).
    """
    record: dict = {
        "electionId": ELECTION,
        "candidateId": candidate_id,
        "candidateName": name,
    }
    if note is not ...:
        record["candidateNote"] = note
    record["kandidatavimas"] = {"isrinktas": False}
    record["source"] = {"candidateSourceUrl": f"https://www.vrk.lt/{candidate_id}"}
    record["rawData"] = {"profile": {"fields": {"Pavadinimas": "reikšmė"}}}
    record["normalized"] = {"profilis": {"vardas-pavarde": name}}
    return record


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


def jpeg(index: int, scan_bytes: int = 600) -> bytes:
    """A distinct, structurally valid JPEG: JPEG_CLEAN's headers, its own scan."""
    return JPEG_CLEAN[:-4] + bytes([0x10 + index]) * scan_bytes + b"\xff\xd9"


def load_unpack():
    spec = importlib.util.spec_from_file_location(
        "unpack_corpus", REPO_ROOT / "scripts" / "unpack_corpus.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


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

        ona = make_record("ona-a-1", "Ona A", note="Išrinkta")
        ona["rawData"]["profile"]["photoSrc"] = "photos/ona.jpg"
        ona["rawData"]["profile"]["photoMeta"] = {
            "mime": "image/jpeg", "bytes": len(JPEG), "sha256": JPEG_SHA,
        }
        ona["normalized"]["profilis"]["nuotrauka"] = "photos/ona.jpg"
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

        # `candidateNote` present *and null* — the shape 27,472 of the 27,478
        # records that carry the key have, and the one a TEXT column could
        # not tell from absent, so the round trip dropped the key on every
        # one of them while three places called it lossless (issue #156).
        rasa = make_record("rasa-d-4", "Rasa D", note=None)

        cls.records = {r["candidateId"]: r for r in (ona, jonas, petras, rasa)}
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
            "vrk-photos-1.sqlite",
            "MANIFEST.json",
        ):
            self.assertTrue((self.dist / name).is_file(), name)

    def test_records_round_trip_less_only_the_public_profile_redactions(self):
        connection = self.corpus_connection()
        rows = connection.execute("SELECT * FROM records ORDER BY candidate_id").fetchall()
        self.assertEqual(len(rows), len(self.records))
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
        photos = connection.execute("SELECT sha256, mime, bytes, stripped, stripped_sha256, part FROM photos").fetchall()
        self.assertEqual(len(photos), 1)
        # The archive's hash is the key, whatever was done to the bytes on
        # the way out; the stored bytes are the picture without its Exif,
        # and they sit in the part the row names, not in this database.
        self.assertEqual(photos[0]["sha256"], JPEG_SHA)
        self.assertEqual(photos[0]["mime"], "image/jpeg")
        self.assertEqual(photos[0]["bytes"], len(JPEG_CLEAN))
        self.assertEqual(photos[0]["stripped"], 1)
        self.assertEqual(photos[0]["stripped_sha256"], hashlib.sha256(JPEG_CLEAN).hexdigest())
        self.assertEqual(photos[0]["part"], "vrk-photos-1.sqlite")
        part = sqlite3.connect(self.dist / photos[0]["part"])
        self.addCleanup(part.close)
        self.assertEqual(
            part.execute("SELECT sha256, mime, bytes, stripped, stripped_sha256, data FROM photos").fetchall(),
            [(JPEG_SHA, "image/jpeg", len(JPEG_CLEAN), 1, hashlib.sha256(JPEG_CLEAN).hexdigest(), JPEG_CLEAN)],
        )
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
            connection.execute("SELECT COUNT(*) FROM candidacies").fetchone()[0],
            len(self.records),
        )
        anomalies = connection.execute("SELECT election_id, event_json FROM anomalies").fetchall()
        self.assertEqual(len(anomalies), 1)
        self.assertEqual(anomalies[0]["election_id"], ELECTION)
        self.assertEqual(json.loads(anomalies[0]["event_json"])["type"], "TestEvent")

    def test_manifest_checksums_match_the_artifacts(self):
        manifest = json.loads((self.dist / "MANIFEST.json").read_text(encoding="utf-8"))
        self.assertRegex(manifest["version"], r"^corpus-\d{4}-\d{2}-\d{2}$")
        # This build's own commit, dirty-aware, and the schema of what it
        # wrote — a release used to say neither (issue #156).
        self.assertTrue(manifest["buildCommit"])
        self.assertEqual(manifest["schemaVersion"], dist_mod.SCHEMA_VERSION)
        # The corpus is not from one commit, and the manifest says so: one
        # of these four records carries a parserCommit and three carry none.
        self.assertEqual(manifest["corpusParserCommits"], {"none": 3, "959f055": 1})
        self.assertEqual(manifest["counts"]["records"], len(self.records))
        self.assertEqual(manifest["counts"]["photos"], 1)
        self.assertEqual(manifest["counts"]["photoRecords"], 2)
        self.assertEqual(manifest["counts"]["anomalies"], 1)
        self.assertEqual(manifest["recordsPerElection"], {ELECTION: len(self.records)})
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
        # The portraits' part is an asset like the others (issue #130).
        self.assertEqual(manifest["counts"]["photoParts"], 1)
        self.assertEqual(
            manifest["photoParts"],
            [{"name": "vrk-photos-1.sqlite", "photos": 1, "photoBytes": len(JPEG_CLEAN), "elections": [ELECTION]}],
        )
        self.assertEqual(
            set(manifest["artifacts"]), set(dist_mod.RELEASE_ARTIFACTS) | {"vrk-photos-1.sqlite"}
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
        self.assertEqual(len(rows), len(self.records) + 1)  # header + one row each
        self.assertEqual(rows[0][:2], ["person_id", "election_id"])


class CorpusRoundTrip(unittest.TestCase):
    """`scripts/unpack_corpus.py`: the release turned back into `data/`.

    Until issue #156 nothing in the repository read a release asset — 0 of
    the 21 scripts — so the corpus the download came from could not be
    reassembled from it. `reconstruct_record` existed and was called by one
    test.

    A `full`-profile build round-trips exactly: same records, same key order,
    same bytes for every portrait, and the anomaly file back beside them.
    """

    @classmethod
    def setUpClass(cls):
        cls.root = make_repo_root()
        cls.addClassCleanup(shutil.rmtree, cls.root, ignore_errors=True)
        data_dir = cls.root / "data" / ELECTION
        (data_dir / "photos").mkdir()
        (data_dir / "photos" / "ona.jpg").write_bytes(JPEG)

        ona = make_record("ona-a-1", "Ona A", note="Išrinkta")
        ona["rawData"]["profile"]["photoSrc"] = "photos/ona.jpg"
        ona["rawData"]["profile"]["photoMeta"] = {
            "mime": "image/jpeg", "bytes": len(JPEG), "sha256": JPEG_SHA,
        }
        ona["normalized"]["profilis"]["nuotrauka"] = "photos/ona.jpg"
        # Present and null: the shape the round trip dropped on 27,472
        # records of the real corpus.
        rasa = make_record("rasa-d-4", "Rasa D", note=None)
        cls.records = {r["candidateId"]: r for r in (ona, rasa)}
        cls.paths = {cid: write_record(data_dir, r) for cid, r in cls.records.items()}
        (data_dir / "anomalies.jsonl").write_text(
            json.dumps({"stage": "parse", "type": "TestEvent", "electionId": ELECTION}) + "\n",
            encoding="utf-8",
        )
        cls.dist = cls.root / "dist"
        assert dist_mod.build_distribution(cls.root, cls.dist, [ELECTION], profile="full") == 0

        spec = importlib.util.spec_from_file_location(
            "unpack_corpus", REPO_ROOT / "scripts" / "unpack_corpus.py"
        )
        cls.unpack = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.unpack)

        cls.into = cls.root / "unpacked"
        cls.counts, cls.problems = cls.unpack.unpack(
            cls.dist / "vrk-corpus.sqlite", cls.into
        )

    def test_it_writes_every_record_with_no_problems(self):
        self.assertEqual(self.problems, [])
        self.assertEqual(self.counts["records"], len(self.records))
        self.assertEqual(self.counts["elections"], 1)
        self.assertEqual(self.counts["photos"], 1)
        self.assertEqual(self.counts["anomalies"], 1)

    def test_every_record_comes_back_key_for_key_in_order(self):
        for candidate_id, original in self.records.items():
            with self.subTest(candidate_id):
                path = self.into / ELECTION / f"{candidate_id}.json"
                self.assertTrue(path.is_file())
                rebuilt = json.loads(path.read_text(encoding="utf-8"))
                self.assertEqual(rebuilt, original)
                self.assertEqual(list(rebuilt), list(original), "key order moved")

    def test_a_present_and_null_note_survives(self):
        rebuilt = json.loads(
            (self.into / ELECTION / "rasa-d-4.json").read_text(encoding="utf-8")
        )
        self.assertIn("candidateNote", rebuilt)
        self.assertIsNone(rebuilt["candidateNote"])

    def test_the_portrait_comes_back_byte_identical(self):
        self.assertEqual((self.into / ELECTION / "photos" / "ona.jpg").read_bytes(), JPEG)

    def test_the_anomaly_file_comes_back(self):
        events = (self.into / ELECTION / "anomalies.jsonl").read_text(encoding="utf-8").splitlines()
        self.assertEqual(len(events), 1)
        self.assertEqual(json.loads(events[0])["type"], "TestEvent")

    def test_the_unpacked_tree_is_the_scraped_tree(self):
        # What a `diff -r` sees: the same files, and the same JSON in each.
        original = sorted(p.name for p in (self.root / "data" / ELECTION).rglob("*") if p.is_file())
        unpacked = sorted(p.name for p in (self.into / ELECTION).rglob("*") if p.is_file())
        self.assertEqual(original, unpacked)

    def test_it_refuses_a_database_with_no_records_table(self):
        with self.assertRaises(SystemExit):
            self.unpack.unpack(self.dist / "vrk.sqlite", self.root / "nope")

    def test_it_refuses_an_election_the_database_does_not_hold(self):
        with self.assertRaises(SystemExit):
            self.unpack.unpack(self.dist / "vrk-corpus.sqlite", self.root / "nope", ["2029-seimo"])

    def test_both_databases_say_what_they_are(self):
        for name, expected in (
            ("vrk-corpus.sqlite", {"records", "photos"}),
            ("vrk.sqlite", {"candidacies", "elections"}),
        ):
            with self.subTest(name):
                connection = sqlite3.connect(self.dist / name)
                try:
                    meta = dict(connection.execute("SELECT key, value FROM meta"))
                    version = connection.execute("PRAGMA user_version").fetchone()[0]
                finally:
                    connection.close()
                self.assertEqual(int(meta["schemaVersion"]), dist_mod.SCHEMA_VERSION)
                self.assertEqual(version, dist_mod.SCHEMA_VERSION)
                self.assertEqual(meta["profile"], "full")
                self.assertTrue(meta["buildCommit"])
                self.assertEqual(meta["dataLicense"], dist_mod.DATA_LICENSE)
                self.assertTrue(set(meta) & {"records", "candidacies"})

    def test_a_photo_part_says_which_slice_it_is(self):
        connection = sqlite3.connect(self.dist / "vrk-photos-1.sqlite")
        try:
            meta = dict(connection.execute("SELECT key, value FROM meta"))
            version = connection.execute("PRAGMA user_version").fetchone()[0]
        finally:
            connection.close()
        self.assertEqual(version, dist_mod.SCHEMA_VERSION)
        self.assertEqual(
            (meta["part"], meta["parts"], meta["photos"], meta["elections"]), ("1", "1", "1", ELECTION)
        )
        self.assertEqual(meta["profile"], "full")
        self.assertEqual(meta["attribution"], dist_mod.ATTRIBUTION)


class RealElectionRoundTrip(unittest.TestCase):
    """The same round trip over a real election, byte for byte.

    The synthetic one above pins the shapes; this one answers the question a
    downloader actually has — does the release rebuild the corpus? — against
    records the scrapers wrote. It skips without a corpus, like every other
    whole-corpus check.
    """

    ELECTION = "2019-prezidento"

    def test_a_full_build_unpacks_to_the_corpus_it_came_from(self):
        from tests import local_data

        source = REPO_ROOT / "data" / self.ELECTION
        local_data.require(source)
        with tempfile.TemporaryDirectory() as tmp:
            dist = Path(tmp) / "dist"
            self.assertEqual(
                dist_mod.build_distribution(REPO_ROOT, dist, [self.ELECTION], profile="full"), 0
            )
            spec = importlib.util.spec_from_file_location(
                "unpack_corpus", REPO_ROOT / "scripts" / "unpack_corpus.py"
            )
            unpack = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(unpack)
            into = Path(tmp) / "unpacked"
            counts, problems = unpack.unpack(dist / "vrk-corpus.sqlite", into)
            self.assertEqual(problems, [])

            originals = sorted(p for p in source.rglob("*") if p.is_file())
            self.assertEqual(counts["records"], sum(1 for p in originals if p.suffix == ".json"))
            for original in originals:
                relative = original.relative_to(source)
                with self.subTest(str(relative)):
                    rebuilt = into / self.ELECTION / relative
                    self.assertTrue(rebuilt.is_file(), f"{relative} was not written")
                    self.assertEqual(
                        rebuilt.read_bytes(), original.read_bytes(), f"{relative} differs"
                    )
            self.assertEqual(
                sorted(p.relative_to(into / self.ELECTION) for p in (into / self.ELECTION).rglob("*") if p.is_file()),
                sorted(p.relative_to(source) for p in originals),
            )


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
        self.assertEqual((photo["stripped"], photo["stripped_sha256"]), (0, JPEG_SHA))
        part = sqlite3.connect(self.dist / photo["part"])
        self.addCleanup(part.close)
        self.assertEqual(part.execute("SELECT data FROM photos").fetchone()[0], JPEG)
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


class CompletenessGate(unittest.TestCase):
    """A build that names no election claims the whole archive (issue #132).

    Measured before the gate: a `data/` holding 2 of the 55 registered
    elections, built as a *full* build, exited 0, printed "Fill gate: no
    findings", wrote all five assets and offered its `gh release create`
    line — and its MANIFEST was indistinguishable in shape from a
    113,073-record one, since a full build writes no `subset` key. Nothing
    could see it: `elections_present` is whatever is under `data/` and only
    an unregistered directory raised, the fill gate iterates cells and a
    wholly absent election has none, and the two-pass record count compares
    two passes over the same truncated list.
    """

    def _root_with(self, election_ids: list[str]) -> Path:
        root = make_repo_root()
        self.addCleanup(shutil.rmtree, root, ignore_errors=True)
        for election_id in election_ids:
            data_dir = root / "data" / election_id
            data_dir.mkdir(parents=True, exist_ok=True)
            record = make_record("kazys-x-9", "Kazys X")
            record["electionId"] = election_id
            write_record(data_dir, record)
        return root

    def test_a_full_build_over_a_partial_corpus_refuses_before_writing(self):
        root = self._root_with([ELECTION])
        dist = root / "dist"
        with self.assertRaises(SystemExit) as raised:
            dist_mod.build_distribution(root, dist, None)
        message = str(raised.exception)
        self.assertIn("of the 55 registered elections", message)
        self.assertIn("54 missing", message)
        self.assertIn("1996-spalio-20-seimo", message)
        self.assertIn("and 34 more", message)
        self.assertFalse(dist.exists(), "nothing may be written before the corpus is checked")

    def test_naming_the_elections_is_the_way_to_build_a_subset(self):
        root = self._root_with([ELECTION])
        dist = root / "dist"
        self.assertEqual(dist_mod.build_distribution(root, dist, [ELECTION]), 0)
        manifest = json.loads((dist / "MANIFEST.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["subset"], [ELECTION])
        self.assertEqual(manifest["counts"]["elections"], 1)
        self.assertEqual(manifest["counts"]["electionsRegistered"], 55)

    def test_the_manifest_says_what_a_complete_corpus_would_hold(self):
        # Without this a consumer cannot ask whether a release is the whole
        # archive: `counts.elections` alone is just a number.
        root = self._root_with([ELECTION])
        dist = root / "dist"
        dist_mod.build_distribution(root, dist, [ELECTION])
        manifest = json.loads((dist / "MANIFEST.json").read_text(encoding="utf-8"))
        registered = len(
            json.loads((REPO_ROOT / "scraper" / "elections.json").read_text(encoding="utf-8"))[
                "elections"
            ]
        )
        self.assertEqual(manifest["counts"]["electionsRegistered"], registered)


class BuildAtomicity(unittest.TestCase):
    """A build that dies partway leaves `dist/` as it was (issue #132).

    The assets were written straight into `dist/` and MANIFEST.json last, so
    a record whose envelope had moved — or a Ctrl-C, a full disk or an OOM
    during the 2.5 GB corpus write — left MANIFEST describing the *previous*
    build, candidacies.csv.gz from this one, three assets from the old,
    `gzip.decompress(vrk.sqlite.gz) != vrk.sqlite`, and `SELECT COUNT(*) FROM
    records` = 0 on a database whose `PRAGMA integrity_check` said ok. The
    error mentioned none of it.
    """

    def _root(self) -> Path:
        root = make_repo_root()
        self.addCleanup(shutil.rmtree, root, ignore_errors=True)
        data_dir = root / "data" / ELECTION
        data_dir.mkdir(parents=True, exist_ok=True)
        write_record(data_dir, make_record("kazys-x-9", "Kazys X"))
        return root

    @staticmethod
    def _snapshot(dist: Path) -> dict[str, str]:
        return {
            path.name: hashlib.sha256(path.read_bytes()).hexdigest()
            for path in sorted(dist.iterdir())
            if path.is_file()
        }

    def test_a_failed_second_build_leaves_the_first_intact(self):
        root = self._root()
        dist = root / "dist"
        self.assertEqual(dist_mod.build_distribution(root, dist, [ELECTION]), 0)
        before = self._snapshot(dist)
        self.assertIn("MANIFEST.json", before)

        # An envelope key that appeared: read only by the corpus writer, which
        # runs after both CSVs and the analysis database are written. (It used
        # to be a `candidateNote` of the wrong type, which the note's own
        # column rejected; the column holds JSON since issue #156, so a dict
        # there is legal and this is the check that still fires late.)
        record_path = next((root / "data" / ELECTION).glob("*.json"))
        record = json.loads(record_path.read_text(encoding="utf-8"))
        record["candidateWeather"] = "the envelope changed shape"
        record_path.write_text(json.dumps(record, ensure_ascii=False), encoding="utf-8")

        with self.assertRaises(SystemExit):
            dist_mod.build_distribution(root, dist, [ELECTION])

        self.assertEqual(self._snapshot(dist), before, "dist/ must be byte-identical")
        self.assertEqual(
            [p.name for p in dist.iterdir() if p.name.startswith(".staging")],
            [],
            "the staging directory must be removed on any exit",
        )

    def test_the_manifest_never_outlives_the_assets_it_checksums(self):
        # The one invariant a reader can rely on through a promotion: either
        # there is no manifest, or it matches what sits beside it.
        root = self._root()
        dist = root / "dist"
        dist_mod.build_distribution(root, dist, [ELECTION])
        manifest = json.loads((dist / "MANIFEST.json").read_text(encoding="utf-8"))
        for name, artifact in manifest["artifacts"].items():
            with self.subTest(name):
                self.assertEqual(
                    hashlib.sha256((dist / name).read_bytes()).hexdigest(), artifact["sha256"]
                )

    def test_promote_removes_the_old_manifest_before_moving_an_asset(self):
        order: list[str] = []
        root = self._root()
        dist = root / "dist"
        dist.mkdir(parents=True)
        staging = dist / ".staging-test"
        staging.mkdir()
        for name in dist_mod.BUILD_OUTPUTS + ("MANIFEST.json",):
            (staging / name).write_bytes(b"new")
            (dist / name).write_bytes(b"old")

        real_replace, real_unlink = dist_mod.os.replace, Path.unlink

        def replace(src, dst):
            order.append(f"replace {Path(dst).name}")
            real_replace(src, dst)

        def unlink(self, **kwargs):
            order.append(f"unlink {self.name}")
            real_unlink(self, **kwargs)

        with unittest.mock.patch.object(dist_mod.os, "replace", replace):
            with unittest.mock.patch.object(Path, "unlink", unlink):
                dist_mod.promote(staging, dist)

        self.assertEqual(order[0], "unlink MANIFEST.json")
        self.assertEqual(order[-1], "replace MANIFEST.json")


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


class PhotoPartsTests(unittest.TestCase):
    """The portraits ship in parts that each fit a release asset (issue #130).

    GitHub refuses an asset over 2 GiB, and the portrait archive made the
    corpus database a ~6 GB one. With the budget shrunk to two images'
    worth, five portraits over two elections have to fill three parts in
    build order -- and every record must still find, and unpack, its own.
    """

    ELECTIONS = ("2016-seimo", "2020-seimo")

    @classmethod
    def setUpClass(cls):
        cls.root = make_repo_root()
        cls.addClassCleanup(shutil.rmtree, cls.root, ignore_errors=True)
        cls.images: dict[tuple[str, str], bytes] = {}
        index = 0
        for election, how_many in zip(cls.ELECTIONS, (3, 2)):
            data_dir = cls.root / "data" / election
            (data_dir / "photos").mkdir(parents=True, exist_ok=True)
            for _ in range(how_many):
                image = jpeg(index)
                candidate_id = f"kandidatas-{index}"
                (data_dir / "photos" / f"{candidate_id}.jpg").write_bytes(image)
                record = make_record(candidate_id, f"Kandidatas {index}")
                record["electionId"] = election
                record["rawData"]["profile"]["photoSrc"] = f"photos/{candidate_id}.jpg"
                record["rawData"]["profile"]["photoMeta"] = {
                    "mime": "image/jpeg", "bytes": len(image), "sha256": hashlib.sha256(image).hexdigest(),
                }
                record["normalized"]["profilis"]["nuotrauka"] = f"photos/{candidate_id}.jpg"
                write_record(data_dir, record)
                cls.images[(election, candidate_id)] = image
                index += 1
        cls.dist = cls.root / "dist"
        with unittest.mock.patch.object(dist_mod, "PHOTO_PART_BUDGET", 2 * len(jpeg(0))):
            cls.exit_code = dist_mod.build_distribution(
                cls.root, cls.dist, list(cls.ELECTIONS), profile="full"
            )
        cls.manifest = json.loads((cls.dist / "MANIFEST.json").read_text(encoding="utf-8"))

    def test_the_images_fill_three_parts_in_build_order(self):
        self.assertEqual(self.exit_code, 0)
        self.assertEqual(
            [(part["name"], part["photos"], part["elections"]) for part in self.manifest["photoParts"]],
            [
                ("vrk-photos-1.sqlite", 2, ["2016-seimo"]),
                ("vrk-photos-2.sqlite", 2, ["2016-seimo", "2020-seimo"]),
                ("vrk-photos-3.sqlite", 1, ["2020-seimo"]),
            ],
        )
        self.assertEqual(self.manifest["counts"]["photoParts"], 3)
        for part in self.manifest["photoParts"]:
            with self.subTest(part["name"]):
                self.assertIn(part["name"], self.manifest["artifacts"])
                self.assertLessEqual(part["photoBytes"], 2 * len(jpeg(0)))

    def test_every_image_is_in_exactly_the_part_its_row_names(self):
        corpus = sqlite3.connect(self.dist / "vrk-corpus.sqlite")
        self.addCleanup(corpus.close)
        located = dict(corpus.execute("SELECT sha256, part FROM photos"))
        self.assertEqual(len(located), 5)
        held: dict[str, str] = {}
        for part in self.manifest["photoParts"]:
            connection = sqlite3.connect(self.dist / part["name"])
            self.addCleanup(connection.close)
            for (digest,) in connection.execute("SELECT sha256 FROM photos"):
                self.assertNotIn(digest, held, "an image stored in two parts")
                held[digest] = part["name"]
        self.assertEqual(held, located)

    def test_the_parts_unpack_to_every_portrait(self):
        into = self.root / "unpacked"
        counts, problems = load_unpack().unpack(self.dist / "vrk-corpus.sqlite", into)
        self.assertEqual(problems, [])
        self.assertEqual(counts["photos"], 5)
        for (election, candidate_id), image in self.images.items():
            with self.subTest(candidate_id):
                self.assertEqual((into / election / "photos" / f"{candidate_id}.jpg").read_bytes(), image)

    def test_a_missing_part_is_named_and_the_records_alone_can_still_be_had(self):
        unpack = load_unpack()
        download = self.root / "download"
        download.mkdir(exist_ok=True)
        shutil.copyfile(self.dist / "vrk-corpus.sqlite", download / "vrk-corpus.sqlite")
        shutil.copyfile(self.dist / "vrk-photos-1.sqlite", download / "vrk-photos-1.sqlite")
        with self.assertRaises(SystemExit) as raised:
            unpack.unpack(download / "vrk-corpus.sqlite", self.root / "partial")
        self.assertIn("vrk-photos-2.sqlite", str(raised.exception))
        self.assertIn("vrk-photos-3.sqlite", str(raised.exception))
        self.assertNotIn("vrk-photos-1.sqlite", str(raised.exception))

        counts, problems = unpack.unpack(
            download / "vrk-corpus.sqlite", self.root / "records-only", with_photos=False
        )
        self.assertEqual(problems, [])
        self.assertEqual((counts["records"], counts["photos"], counts["photos_skipped"]), (5, 0, 5))
        self.assertFalse((self.root / "records-only" / "2016-seimo" / "photos").exists())

        counts, problems = unpack.unpack(
            download / "vrk-corpus.sqlite", self.root / "pointed", photos_dir=self.dist
        )
        self.assertEqual((problems, counts["photos"]), ([], 5))

    def test_a_release_from_before_the_parts_still_unpacks(self):
        # corpus-2026-08-30 kept the bytes in the corpus database's own
        # photos.data column (schema 1); that shape still reads.
        old = self.root / "schema-1"
        old.mkdir(exist_ok=True)
        database = old / "vrk-corpus.sqlite"
        shutil.copyfile(self.dist / "vrk-corpus.sqlite", database)
        connection = sqlite3.connect(database)
        try:
            connection.execute("ALTER TABLE photos ADD COLUMN data BLOB")
            for part in self.manifest["photoParts"]:
                connection.execute("ATTACH DATABASE ? AS source", (str(self.dist / part["name"]),))
                connection.execute(
                    "UPDATE photos SET data = (SELECT d.data FROM source.photos AS d"
                    " WHERE d.sha256 = main.photos.sha256) WHERE part = ?",
                    (part["name"],),
                )
                connection.commit()
                connection.execute("DETACH DATABASE source")
        finally:
            connection.close()
        into = self.root / "from-schema-1"
        counts, problems = load_unpack().unpack(database, into)
        self.assertEqual((problems, counts["photos"]), ([], 5))
        for (election, candidate_id), image in self.images.items():
            with self.subTest(candidate_id):
                self.assertEqual((into / election / "photos" / f"{candidate_id}.jpg").read_bytes(), image)

    def test_an_asset_over_the_cap_is_refused_before_dist_changes(self):
        root = make_repo_root()
        self.addCleanup(shutil.rmtree, root, ignore_errors=True)
        data_dir = root / "data" / ELECTION
        write_record(data_dir, make_record("kazys-x-9", "Kazys X"))
        dist = root / "dist"
        with unittest.mock.patch.object(dist_mod, "RELEASE_ASSET_LIMIT", 100):
            with self.assertRaises(SystemExit) as raised:
                dist_mod.build_distribution(root, dist, [ELECTION])
        self.assertIn("limit GitHub puts on a release asset", str(raised.exception))
        self.assertEqual([path.name for path in dist.iterdir()], [], "nothing may reach dist/")

    def test_promote_drops_a_part_the_new_build_did_not_fill(self):
        root = make_repo_root()
        self.addCleanup(shutil.rmtree, root, ignore_errors=True)
        dist = root / "dist"
        staging = dist / ".staging-test"
        staging.mkdir(parents=True)
        for name in dist_mod.BUILD_OUTPUTS + ("MANIFEST.json", "vrk-photos-1.sqlite"):
            (staging / name).write_bytes(b"new")
        (dist / "vrk-photos-1.sqlite").write_bytes(b"old")
        (dist / "vrk-photos-2.sqlite").write_bytes(b"old")
        dist_mod.promote(staging, dist)
        self.assertEqual((dist / "vrk-photos-1.sqlite").read_bytes(), b"new")
        self.assertFalse((dist / "vrk-photos-2.sqlite").exists())


if __name__ == "__main__":
    unittest.main()
