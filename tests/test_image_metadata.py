"""The portrait metadata stripper (issue #142): what a release ships is the
picture, not the camera's notes about where and by whom it was taken.

Synthetic files first -- a JPEG with an Exif block holding a GPS IFD, an XMP
packet, an IPTC block, a comment and an ICC profile; a PNG with `eXIf` and
text chunks -- so the contract is pinned byte by byte. Then the tracked
fixture portraits, hundreds of real files VRK served: every one strips to a
file with no metadata segment left, or is reported as a container the
stripper does not touch.
"""

from __future__ import annotations

import struct
import unittest
import zlib
from pathlib import Path

from scraper.shared.image_metadata import (
    StripResult,
    jpeg_segments,
    png_chunk_types,
    strip_jpeg,
    strip_metadata,
    strip_png,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURES_ROOT = REPO_ROOT / "samples" / "html"


def _segment(marker: int, payload: bytes) -> bytes:
    return bytes([0xFF, marker]) + struct.pack(">H", len(payload) + 2) + payload


def _exif_with_gps() -> bytes:
    # A minimal big-endian TIFF: IFD0 with one entry, the GPSInfo pointer
    # (0x8825) to a GPS IFD holding GPSLatitude (0x0002).
    tiff = b"MM\x00*" + struct.pack(">I", 8)
    ifd0 = struct.pack(">H", 1) + struct.pack(">HHII", 0x8825, 4, 1, 26) + struct.pack(">I", 0)
    gps = struct.pack(">H", 1) + struct.pack(">HHII", 0x0002, 5, 3, 44) + struct.pack(">I", 0)
    rationals = struct.pack(">IIIIII", 54, 1, 26, 1, 5940, 100)  # 54° 26' 59.40"
    return b"Exif\x00\x00" + tiff + ifd0 + gps + rationals


APP0 = _segment(0xE0, b"JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00")
EXIF = _segment(0xE1, _exif_with_gps())
XMP = _segment(0xE1, b"http://ns.adobe.com/xap/1.0/\x00<x:xmpmeta>gps here</x:xmpmeta>")
IPTC = _segment(0xED, b"Photoshop 3.0\x008BIM\x04\x04\x00\x00\x00\x00\x00\x06Artist")
ICC = _segment(0xE2, b"ICC_PROFILE\x00\x01\x01" + b"\x00" * 20)
MPF = _segment(0xE2, b"MPF\x00" + b"\x00" * 8)
COMMENT = _segment(0xFE, b"File written by Adobe Photoshop")
DQT = _segment(0xDB, b"\x00" + bytes(range(64)))
SOF = _segment(0xC0, b"\x08\x00\x10\x00\x10\x01\x01\x11\x00")
DHT = _segment(0xC4, b"\x00" + b"\x01" + b"\x00" * 15 + b"\x00")
SOS_AND_SCAN = _segment(0xDA, b"\x01\x01\x00\x00\x3f\x00") + b"\x12\x34\xff\x00\x56\xff\xd0\x78" + b"\xff\xd9"


def synthetic_jpeg(*extra: bytes) -> bytes:
    return b"\xff\xd8" + APP0 + b"".join(extra) + DQT + SOF + DHT + SOS_AND_SCAN


def _chunk(chunk_type: bytes, payload: bytes) -> bytes:
    return struct.pack(">I", len(payload)) + chunk_type + payload + struct.pack(">I", zlib.crc32(chunk_type + payload) & 0xFFFFFFFF)


def synthetic_png(*extra: bytes) -> bytes:
    ihdr = _chunk(b"IHDR", struct.pack(">IIBBBBB", 1, 1, 8, 0, 0, 0, 0))
    idat = _chunk(b"IDAT", zlib.compress(b"\x00\x00"))
    return b"\x89PNG\r\n\x1a\n" + ihdr + b"".join(extra) + idat + _chunk(b"IEND", b"")


class JpegTests(unittest.TestCase):
    def test_every_metadata_segment_goes_and_the_picture_stays(self) -> None:
        raw = synthetic_jpeg(EXIF, XMP, IPTC, COMMENT, MPF)
        result = strip_jpeg(raw)
        self.assertEqual(result.container, "jpeg")
        self.assertFalse(result.malformed)
        self.assertEqual(result.removed, ("APP1/Exif", "APP1/XMP", "APP13", "COM", "APP2"))
        self.assertEqual(result.data, synthetic_jpeg())
        self.assertNotIn(b"Exif", result.data)
        self.assertNotIn(b"xmpmeta", result.data)
        self.assertNotIn(b"Photoshop", result.data)
        self.assertEqual([marker for marker, _ in jpeg_segments(result.data)], [0xE0, 0xDB, 0xC0, 0xC4])
        # The scan data, restart marker included, is byte-identical.
        self.assertTrue(result.data.endswith(SOS_AND_SCAN))

    def test_the_icc_profile_is_kept(self) -> None:
        # A colour profile changes how the picture renders and holds nothing
        # personal; the other APP2 uses (MPF, FlashPix) go.
        result = strip_jpeg(synthetic_jpeg(ICC, MPF))
        self.assertEqual(result.removed, ("APP2",))
        self.assertEqual(result.data, synthetic_jpeg(ICC))

    def test_a_clean_file_is_returned_unchanged_and_says_so(self) -> None:
        raw = synthetic_jpeg()
        result = strip_jpeg(raw)
        self.assertEqual(result, StripResult(raw, (), "jpeg"))
        self.assertFalse(result.stripped)

    def test_a_truncated_file_is_returned_whole_and_flagged(self) -> None:
        raw = synthetic_jpeg(EXIF)[:40]
        result = strip_jpeg(raw)
        self.assertEqual(result.data, raw)
        self.assertTrue(result.malformed)
        self.assertEqual(result.removed, ())

    def test_a_segment_length_past_the_end_is_malformed_not_half_written(self) -> None:
        raw = b"\xff\xd8" + bytes([0xFF, 0xE1]) + struct.pack(">H", 5000) + b"Exif\x00\x00"
        result = strip_jpeg(raw)
        self.assertEqual((result.data, result.malformed), (raw, True))


class PngTests(unittest.TestCase):
    def test_exif_and_text_chunks_go_and_the_image_chunks_stay_with_their_crcs(self) -> None:
        exif = _chunk(b"eXIf", _exif_with_gps()[6:])
        text = _chunk(b"tEXt", b"Author\x00Some Photographer")
        itxt = _chunk(b"iTXt", b"XML:com.adobe.xmp\x00\x00\x00\x00\x00<x:xmpmeta/>")
        ztxt = _chunk(b"zTXt", b"Comment\x00\x00" + zlib.compress(b"lat 54.45"))
        result = strip_png(synthetic_png(exif, text, itxt, ztxt))
        self.assertEqual(result.container, "png")
        self.assertEqual(result.removed, ("eXIf", "tEXt", "iTXt", "zTXt"))
        self.assertEqual(result.data, synthetic_png())
        self.assertEqual(png_chunk_types(result.data), ["IHDR", "IDAT", "IEND"])

    def test_a_clean_png_is_unchanged(self) -> None:
        raw = synthetic_png()
        self.assertEqual(strip_png(raw), StripResult(raw, (), "png"))

    def test_a_chunk_past_the_end_is_malformed(self) -> None:
        raw = b"\x89PNG\r\n\x1a\n" + struct.pack(">I", 999) + b"tEXt" + b"abc"
        result = strip_png(raw)
        self.assertEqual((result.data, result.malformed), (raw, True))


class DispatchTests(unittest.TestCase):
    def test_the_container_picks_the_walker(self) -> None:
        self.assertEqual(strip_metadata(synthetic_jpeg(COMMENT)).removed, ("COM",))
        self.assertEqual(strip_metadata(synthetic_png(_chunk(b"tEXt", b"a\x00b"))).removed, ("tEXt",))

    def test_other_containers_pass_through_and_say_so(self) -> None:
        # A TIFF is an Exif container in its own right and a GIF has nowhere
        # to put one; the builder counts these rather than pretending.
        for raw in (b"BM" + b"\x00" * 30, b"GIF89a" + b"\x00" * 10, b"II*\x00" + b"\x00" * 10, b"PK\x03\x04zip"):
            with self.subTest(raw[:4]):
                self.assertEqual(strip_metadata(raw), StripResult(raw, (), "other"))


class TrackedPortraitTests(unittest.TestCase):
    """Every retained portrait in the fixture trees -- hundreds of real files
    VRK served, 254 of them carrying metadata on 2026-09-08 -- strips clean,
    or is a container the stripper leaves alone."""

    def _portraits(self) -> list[Path]:
        if not FIXTURES_ROOT.is_dir():
            return []
        return sorted(p for p in FIXTURES_ROOT.glob("*/*/portrait.*") if p.suffix != ".json")

    def test_there_are_portraits_to_strip(self) -> None:
        self.assertGreater(len(self._portraits()), 100)

    def test_every_portrait_strips_clean(self) -> None:
        stripped = 0
        for path in self._portraits():
            raw = path.read_bytes()
            with self.subTest(f"{path.parent.parent.name}/{path.parent.name}"):
                result = strip_metadata(raw)
                self.assertFalse(result.malformed, "a retained portrait the walker cannot parse")
                if result.container == "jpeg":
                    self.assertEqual(result.data[:2], b"\xff\xd8")
                    for marker, payload in jpeg_segments(result.data):
                        self.assertNotIn(marker, (0xE1, 0xED, 0xFE), hex(marker))
                        if marker == 0xE2:
                            self.assertTrue(payload.startswith(b"ICC_PROFILE\x00"))
                    self.assertTrue(result.data.endswith(raw[-2:]), "the scan data is copied through whole")
                elif result.container == "png":
                    self.assertTrue({"eXIf", "tEXt", "zTXt", "iTXt"}.isdisjoint(png_chunk_types(result.data)))
                    self.assertIn("IEND", png_chunk_types(result.data))
                else:
                    self.assertEqual(result.data, raw)
                stripped += result.stripped
        self.assertGreater(stripped, 0, "the fixtures carry metadata to strip; none stripped means the walker skipped them")


if __name__ == "__main__":
    unittest.main()
