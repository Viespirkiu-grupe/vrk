"""Pins for the photo sidecar externalization (tier-2 phase B, 2026-08-19).

Embedded base64 portraits (2,196 JPEG, 2 PNG and one ZIP a candidate uploaded
as their photo — 362 MB decoded) move out of the records into
photos/<candidateId>.<ext> beside them. Both photo fields become the relative
path; photoMeta keeps size and sha256 so the file stays verifiable against
what VRK served. URL-form values and undecodable payloads pass through
untouched.
"""

from __future__ import annotations

import base64
import hashlib
import tempfile
import unittest
from pathlib import Path

from scraper.shared.files import externalize_record_photo, write_candidate_record

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


if __name__ == "__main__":
    unittest.main()
