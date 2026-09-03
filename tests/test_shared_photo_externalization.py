"""Pins for the photo sidecar externalization (tier-2 phase B, 2026-08-19).

Embedded base64 portraits (2,196 JPEG, 2 PNG and one ZIP a candidate uploaded
as their photo — 362 MB decoded) move out of the records into
photos/<candidateId>.<ext> beside them. Both photo fields become the relative
path; photoMeta keeps size and sha256 so the file stays verifiable against
what VRK served. Undecodable payloads pass through untouched.

URL-form values (issue #118) take the same road when the portrait was
retained beside the record's primary page — `portrait.json` naming the URL
and a `portrait.<ext>` holding the bytes, as scripts/backfill_url_portraits.py
writes them. A URL with no retained portrait, or one retained for a different
URL, stays a URL; a retained *failure* stays a URL too, but stamps photoMeta
with how the fetch failed so the two cases never read alike.
"""

from __future__ import annotations

import base64
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from scraper.shared.files import (
    IMAGE_EXTENSIONS,
    externalize_record_photo,
    sniff_photo_type,
    write_candidate_record,
)

JPEG_BYTES = b"\xff\xd8\xff\xe0test-jpeg-payload"
DATA_URI = "data:;base64," + base64.b64encode(JPEG_BYTES).decode()


def _record(photo_src):
    return {
        "candidateId": "jonas-jonaitis",
        "rawData": {"profile": {"photoSrc": photo_src}},
        "normalized": {"profilis": {"nuotrauka": None}},
    }


class ExternalizeRecordPhotoTests(unittest.TestCase):
    def test_data_uri_becomes_a_sidecar_file(self) -> None:
        record = _record(DATA_URI)
        with tempfile.TemporaryDirectory() as tmp:
            output_path = Path(tmp) / "jonas-jonaitis-2016-seimo.json"
            externalize_record_photo(record, output_path)

            photo_path = Path(tmp) / "photos" / "jonas-jonaitis.jpg"
            self.assertTrue(photo_path.exists())
            self.assertEqual(photo_path.read_bytes(), JPEG_BYTES)

        profile = record["rawData"]["profile"]
        self.assertEqual(profile["photoSrc"], "photos/jonas-jonaitis.jpg")
        self.assertEqual(profile["photoMeta"]["bytes"], len(JPEG_BYTES))
        self.assertEqual(
            profile["photoMeta"]["sha256"], hashlib.sha256(JPEG_BYTES).hexdigest()
        )
        self.assertEqual(profile["photoMeta"]["mime"], "image/jpeg")
        self.assertEqual(
            record["normalized"]["profilis"]["nuotrauka"], "photos/jonas-jonaitis.jpg"
        )

    def test_zip_payload_is_sniffed_and_kept_faithfully(self) -> None:
        raw = b"PK\x03\x04rest-of-a-zip"
        record = _record("data:;base64," + base64.b64encode(raw).decode())
        with tempfile.TemporaryDirectory() as tmp:
            externalize_record_photo(record, Path(tmp) / "x.json")
            self.assertTrue((Path(tmp) / "photos" / "jonas-jonaitis.zip").exists())
        self.assertEqual(record["rawData"]["profile"]["photoMeta"]["mime"], "application/zip")

    def test_url_value_is_untouched(self) -> None:
        url = "https://www.vrk.lt/statiniai/kandImg/123.jpg"
        record = _record(url)
        with tempfile.TemporaryDirectory() as tmp:
            externalize_record_photo(record, Path(tmp) / "x.json")
            self.assertEqual(list(Path(tmp).iterdir()), [])
        self.assertEqual(record["rawData"]["profile"]["photoSrc"], url)
        self.assertNotIn("photoMeta", record["rawData"]["profile"])

    def test_undecodable_payload_is_left_verbatim(self) -> None:
        bad = "data:;base64,%%%not-base64%%%"
        record = _record(bad)
        with tempfile.TemporaryDirectory() as tmp:
            externalize_record_photo(record, Path(tmp) / "x.json")
        self.assertEqual(record["rawData"]["profile"]["photoSrc"], bad)

    def test_write_candidate_record_externalizes_then_writes(self) -> None:
        record = _record(DATA_URI)
        with tempfile.TemporaryDirectory() as tmp:
            output_path = Path(tmp) / "jonas-jonaitis-2016-seimo.json"
            write_candidate_record(output_path, record)
            self.assertTrue(output_path.exists())
            self.assertTrue((Path(tmp) / "photos" / "jonas-jonaitis.jpg").exists())
            self.assertIn('"photos/jonas-jonaitis.jpg"', output_path.read_text())


class SniffTests(unittest.TestCase):
    def test_every_container_vrk_has_served_is_recognised(self) -> None:
        # The 2012 Seimas tree serves BMP and TIFF portraits as image/jpeg
        # under .jpg names; the container comes from the bytes, never the URL.
        self.assertEqual(sniff_photo_type(b"BM\x18\x1f\x01\x00rest"), ("bmp", "image/bmp"))
        self.assertEqual(sniff_photo_type(b"II*\x00\x08\x00\x00\x00"), ("tif", "image/tiff"))
        self.assertEqual(sniff_photo_type(b"MM\x00*\x00\x00\x00\x08"), ("tif", "image/tiff"))
        self.assertEqual(sniff_photo_type(b"\x89PNG\r\n"), ("png", "image/png"))
        self.assertEqual(sniff_photo_type(b"GIF89a"), ("gif", "image/gif"))
        self.assertEqual(sniff_photo_type(JPEG_BYTES), ("jpg", "image/jpeg"))
        self.assertEqual(sniff_photo_type(b"<!DOCTYPE html>"), ("bin", "application/octet-stream"))
        self.assertEqual(IMAGE_EXTENSIONS, {"jpg", "png", "gif", "bmp", "tif"})


URL = "https://www.vrk.lt/statiniai/puslapiai/rinkimai/1104/rnk1424/kandidatai/kandImg/photo_1.jpeg"


def _retain(candidate_dir: Path, url: str, raw: bytes | None = None, error: str | None = None) -> None:
    """What scripts/backfill_url_portraits.py leaves beside a candidate's pages."""
    candidate_dir.mkdir(parents=True, exist_ok=True)
    (candidate_dir / "anketa.html").write_text("<html></html>", encoding="utf-8")
    meta: dict = {"url": url, "fetchedAt": "2026-09-02T20:00:00+00:00"}
    if raw is not None:
        (candidate_dir / "portrait.jpg").write_bytes(raw)
        meta.update(
            {
                "file": "portrait.jpg",
                "mime": "image/jpeg",
                "bytes": len(raw),
                "sha256": hashlib.sha256(raw).hexdigest(),
            }
        )
    else:
        meta["error"] = error
    (candidate_dir / "portrait.json").write_text(json.dumps(meta), encoding="utf-8")


class RetainedPortraitTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        root = Path(self._tmp.name)
        self.candidate_dir = root / "samples-full" / "2020-seimo" / "jonas-jonaitis"
        self.page = self.candidate_dir / "anketa.html"
        self.output_path = root / "data" / "2020-seimo" / "jonas-jonaitis-2020-seimo.json"
        self.output_path.parent.mkdir(parents=True)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_url_with_a_retained_portrait_becomes_a_sidecar(self) -> None:
        _retain(self.candidate_dir, URL, raw=JPEG_BYTES)
        record = _record(URL)
        externalize_record_photo(record, self.output_path, self.page)

        sidecar = self.output_path.parent / "photos" / "jonas-jonaitis.jpg"
        self.assertEqual(sidecar.read_bytes(), JPEG_BYTES)
        profile = record["rawData"]["profile"]
        self.assertEqual(profile["photoSrc"], "photos/jonas-jonaitis.jpg")
        self.assertEqual(
            profile["photoMeta"],
            {
                "mime": "image/jpeg",
                "bytes": len(JPEG_BYTES),
                "sha256": hashlib.sha256(JPEG_BYTES).hexdigest(),
                "url": URL,
                "fetchedAt": "2026-09-02T20:00:00+00:00",
            },
        )
        self.assertEqual(record["normalized"]["profilis"]["nuotrauka"], "photos/jonas-jonaitis.jpg")

    def test_the_archive_family_photo_url_key_is_rewritten_too(self) -> None:
        # The 1996-1999 Seimas archive family's profile has no photoSrc; its
        # reference is `photoUrl`, and that is the key the path replaces.
        _retain(self.candidate_dir, URL, raw=JPEG_BYTES)
        record = {
            "candidateId": "jonas-jonaitis",
            "rawData": {"profile": {"candidateDisplayName": "Jonas", "photoUrl": URL}},
            "normalized": {"profilis": {"nuotrauka": URL}},
        }
        externalize_record_photo(record, self.output_path, self.page)
        profile = record["rawData"]["profile"]
        self.assertEqual(profile["photoUrl"], "photos/jonas-jonaitis.jpg")
        self.assertNotIn("photoSrc", profile)
        self.assertEqual(profile["photoMeta"]["url"], URL)
        self.assertEqual(record["normalized"]["profilis"]["nuotrauka"], "photos/jonas-jonaitis.jpg")

    def test_a_recorded_failure_stamps_photo_meta_and_keeps_the_url(self) -> None:
        _retain(self.candidate_dir, URL, error="HTTP 404")
        record = _record(URL)
        externalize_record_photo(record, self.output_path, self.page)

        profile = record["rawData"]["profile"]
        self.assertEqual(profile["photoSrc"], URL)
        self.assertEqual(
            profile["photoMeta"],
            {"url": URL, "fetchedAt": "2026-09-02T20:00:00+00:00", "error": "HTTP 404"},
        )
        self.assertIsNone(record["normalized"]["profilis"]["nuotrauka"])
        self.assertFalse((self.output_path.parent / "photos").exists())

    def test_a_retained_portrait_for_another_url_is_ignored(self) -> None:
        # The page moved its portrait since the fetch: the retained bytes are
        # not this URL's, so the record keeps the URL and no photoMeta.
        _retain(self.candidate_dir, URL.replace("photo_1", "photo_2"), raw=JPEG_BYTES)
        record = _record(URL)
        externalize_record_photo(record, self.output_path, self.page)
        self.assertEqual(record["rawData"]["profile"]["photoSrc"], URL)
        self.assertNotIn("photoMeta", record["rawData"]["profile"])

    def test_no_retained_portrait_leaves_the_url(self) -> None:
        self.candidate_dir.mkdir(parents=True)
        self.page.write_text("<html></html>", encoding="utf-8")
        record = _record(URL)
        externalize_record_photo(record, self.output_path, self.page)
        self.assertEqual(record["rawData"]["profile"]["photoSrc"], URL)
        self.assertNotIn("photoMeta", record["rawData"]["profile"])

    def test_retained_bytes_that_do_not_match_their_record_raise(self) -> None:
        _retain(self.candidate_dir, URL, raw=JPEG_BYTES)
        (self.candidate_dir / "portrait.jpg").write_bytes(b"\xff\xd8\xffsomething-else")
        with self.assertRaisesRegex(ValueError, "not what was fetched"):
            externalize_record_photo(_record(URL), self.output_path, self.page)

    def test_write_candidate_record_reads_the_portrait_beside_the_page(self) -> None:
        _retain(self.candidate_dir, URL, raw=JPEG_BYTES)
        record = _record(URL)
        write_candidate_record(self.output_path, record, source_path=self.page)
        self.assertTrue((self.output_path.parent / "photos" / "jonas-jonaitis.jpg").exists())
        stored = json.loads(self.output_path.read_text(encoding="utf-8"))
        self.assertEqual(stored["rawData"]["profile"]["photoSrc"], "photos/jonas-jonaitis.jpg")
        self.assertEqual(stored["rawData"]["profile"]["photoMeta"]["url"], URL)
        self.assertIn("provenance", stored)


if __name__ == "__main__":
    unittest.main()
