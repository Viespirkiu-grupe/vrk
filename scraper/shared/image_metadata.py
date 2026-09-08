"""Strip the metadata a portrait carries, on the way out of the archive.

The corpus retains every portrait VRK served, byte for byte, and verifies it
by sha256 (`photoMeta.sha256`). That is right for the archive and wrong for
what a release ships: of the 27,493 sidecars, 9,889 carry an Exif block,
8,247 an XMP packet and 8,957 a Photoshop/IPTC resource block, and inside
them 1,215 carry a GPS IFD -- the audit behind issue #142 counted 35 with
real coordinates, 32 of them inside Lithuania -- plus camera body serials,
`Artist` strings and `CameraOwnerName` values, three with a phone number
in them. None of it is the candidate's declaration; it is what their
camera or a photographer's software wrote into the file.

So the distribution builder passes each portrait through `strip_metadata`
after the archive's hash check has passed, and stores the stripped bytes
under the *original* sha256 (the join key `records.photo_sha256`), with the
stored bytes' own hash beside it. The archive stays what VRK served; the
release carries the picture and nothing else.

What is removed, by container:

* **JPEG** -- every APP1 segment (Exif, XMP and anything else in that
  marker), APP13 (Photoshop image resources, which is where IPTC lives),
  APP2 except an ICC colour profile (a profile changes how the picture
  renders and holds nothing personal; the other APP2 uses -- MPF, which can
  embed a second full image, and FlashPix -- go), and COM comments. The
  frame headers, quantisation and Huffman tables, the JFIF APP0 and the
  entropy-coded data are copied through untouched, so the decoded pixels
  are identical.
* **PNG** -- the `eXIf`, `tEXt`, `zTXt` and `iTXt` chunks. Everything else
  (`IHDR`, `PLTE`, `IDAT`, `IEND`, the colour chunks) is copied with its CRC.
* Anything else (BMP, GIF, TIFF, the one ZIP) is returned unchanged and said
  so: a TIFF *is* an Exif container and a GIF has nowhere to put one; the
  builder counts them rather than pretending.

A file the walker cannot parse -- a truncated JPEG, a chunk length past the
end -- is returned unchanged with `malformed=True` rather than half-rewritten:
the builder's count of those is the signal that a sidecar needs a look.
"""

from __future__ import annotations

import struct
from typing import NamedTuple

JPEG_SOI = b"\xff\xd8"
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"

#: JPEG markers whose segments carry metadata rather than the picture.
_APP1 = 0xE1
_APP2 = 0xE2
_APP13 = 0xED
_COM = 0xFE
_SOS = 0xDA
_EOI = 0xD9
_STRIPPED_MARKERS = {_APP1: "APP1", _APP2: "APP2", _APP13: "APP13", _COM: "COM"}
#: Markers that stand alone, with no length word after them.
_STANDALONE = {0xD8, 0x01, *range(0xD0, 0xD8)}

_ICC_PROFILE = b"ICC_PROFILE\x00"

#: PNG chunks that carry metadata: Exif (since PNG 1.5), the three text
#: chunk types (comments, software, author, GPS-as-text and whatever else a
#: tool wrote).
_PNG_METADATA_CHUNKS = {b"eXIf", b"tEXt", b"zTXt", b"iTXt"}


class StripResult(NamedTuple):
    """The bytes to ship, and what happened to get them."""

    data: bytes
    #: The segment / chunk names removed, in file order ("APP1", "COM", "tEXt" …).
    removed: tuple[str, ...]
    #: "jpeg", "png", or the container as `sniff_photo_type` would name it
    #: when nothing could be stripped ("other").
    container: str
    #: True when the file could not be walked and was returned unchanged.
    malformed: bool = False

    @property
    def stripped(self) -> bool:
        return bool(self.removed)


def _segment_name(marker: int, payload: bytes) -> str:
    if marker == _APP1:
        if payload.startswith(b"Exif\x00"):
            return "APP1/Exif"
        if payload.startswith(b"http://ns.adobe.com/xap/"):
            return "APP1/XMP"
        return "APP1"
    if marker == _APP13:
        return "APP13"
    if marker == _COM:
        return "COM"
    return "APP2"


def strip_jpeg(raw: bytes) -> StripResult:
    """Copy a JPEG through without its metadata segments (see the module)."""
    if not raw.startswith(JPEG_SOI):
        return StripResult(raw, (), "other")
    out = bytearray(JPEG_SOI)
    removed: list[str] = []
    i = 2
    length = len(raw)
    while True:
        if i + 2 > length or raw[i] != 0xFF:
            return StripResult(raw, (), "jpeg", malformed=True)
        marker = raw[i + 1]
        if marker == 0xFF:  # fill byte before a marker
            i += 1
            continue
        if marker in _STANDALONE:
            out += raw[i : i + 2]
            i += 2
            continue
        if marker == _EOI:
            out += raw[i:]
            return StripResult(bytes(out), tuple(removed), "jpeg")
        if i + 4 > length:
            return StripResult(raw, (), "jpeg", malformed=True)
        segment_length = struct.unpack(">H", raw[i + 2 : i + 4])[0]
        end = i + 2 + segment_length
        if segment_length < 2 or end > length:
            return StripResult(raw, (), "jpeg", malformed=True)
        if marker == _SOS:
            # Start of scan: the entropy-coded data follows the header and
            # runs to EOI, with restart markers inside it. Nothing after this
            # point is metadata a viewer honours, so it is copied verbatim.
            out += raw[i:]
            return StripResult(bytes(out), tuple(removed), "jpeg")
        payload = raw[i + 4 : end]
        if marker in _STRIPPED_MARKERS and not (marker == _APP2 and payload.startswith(_ICC_PROFILE)):
            removed.append(_segment_name(marker, payload))
        else:
            out += raw[i:end]
        i = end


def strip_png(raw: bytes) -> StripResult:
    """Copy a PNG through without its metadata chunks (see the module)."""
    if not raw.startswith(PNG_SIGNATURE):
        return StripResult(raw, (), "other")
    out = bytearray(PNG_SIGNATURE)
    removed: list[str] = []
    i = len(PNG_SIGNATURE)
    length = len(raw)
    while i < length:
        if i + 8 > length:
            return StripResult(raw, (), "png", malformed=True)
        chunk_length = struct.unpack(">I", raw[i : i + 4])[0]
        chunk_type = raw[i + 4 : i + 8]
        end = i + 12 + chunk_length
        if end > length:
            return StripResult(raw, (), "png", malformed=True)
        if chunk_type in _PNG_METADATA_CHUNKS:
            removed.append(chunk_type.decode("latin-1"))
        else:
            out += raw[i:end]
        i = end
        if chunk_type == b"IEND":
            break
    return StripResult(bytes(out), tuple(removed), "png")


def strip_metadata(raw: bytes) -> StripResult:
    """Strip whatever metadata the container can carry; other containers
    pass through unchanged and say so (`container="other"`)."""
    if raw.startswith(JPEG_SOI):
        return strip_jpeg(raw)
    if raw.startswith(PNG_SIGNATURE):
        return strip_png(raw)
    return StripResult(raw, (), "other")


def jpeg_segments(raw: bytes) -> list[tuple[int, bytes]]:
    """(marker, payload) for every length-bearing segment before the scan --
    what a test reads back to prove what is and is not left in a file."""
    segments: list[tuple[int, bytes]] = []
    i = 2
    while i + 4 <= len(raw) and raw[i] == 0xFF:
        marker = raw[i + 1]
        if marker in _STANDALONE:
            i += 2
            continue
        if marker in (_SOS, _EOI):
            break
        segment_length = struct.unpack(">H", raw[i + 2 : i + 4])[0]
        segments.append((marker, raw[i + 4 : i + 2 + segment_length]))
        i += 2 + segment_length
    return segments


def png_chunk_types(raw: bytes) -> list[str]:
    """The chunk types of a PNG in file order -- the PNG twin of `jpeg_segments`."""
    types: list[str] = []
    i = len(PNG_SIGNATURE)
    while i + 8 <= len(raw):
        chunk_length = struct.unpack(">I", raw[i : i + 4])[0]
        chunk_type = raw[i + 4 : i + 8].decode("latin-1")
        types.append(chunk_type)
        i += 12 + chunk_length
        if chunk_type == "IEND":
            break
    return types
