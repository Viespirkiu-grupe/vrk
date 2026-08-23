"""Text extraction from Word 97 binary documents, dependency-free.

The 2004 presidential election publishes each candidate's biography and
election programme as a ``.doc`` file (Microsoft Word 8.0, the Word 97
binary format) — the only corpus source that is a Word document rather
than a page. The corpus needs just the text, so this is a minimal reader
of that one format, not a general converter:

- The OLE compound file (the ``.doc`` container) is walked directly:
  header, DIFAT, FAT, directory, mini-FAT — enough to read the two
  streams the text lives in, ``WordDocument`` and ``0Table``/``1Table``.
- The FIB at the start of ``WordDocument`` says which table stream is
  current and where the Clx sits in it; the Clx's piece table maps the
  document's character positions to byte ranges of ``WordDocument``,
  each piece either UTF-16LE or "compressed" cp1252. Reading the piece
  table (not the bytes in FIB order) is what makes fast-saved files
  come out in document order.
- Only the main document range (the FIB's ``ccpText``) is kept: the
  pieces continue into footnotes, headers and annotation subdocuments,
  which the VRK files use for page headers.

Field codes (hyperlinks print as ``\\x13 HYPERLINK … \\x14 text \\x15``)
keep their result text and lose their instruction text; Word's control
marks (paragraph, cell, line break…) become newlines or drop. The result
is plain text with paragraph breaks as ``\\n``.
"""
from __future__ import annotations

import re
import struct

OLE_MAGIC = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"
WORD_FIB_MAGIC = 0xA5EC
# nFib 193 (0x00C1) is Word 97; 98/2000/2002/2003 keep the same layout for
# everything read here. Word 95 (nFib 101–104) stores text without a piece
# table and is refused rather than misread.
MIN_SUPPORTED_NFIB = 193

_END_OF_CHAIN = -2

# Word's in-text control marks. \x0d ends a paragraph, \x0b is a manual
# line break, \x0c a page break, \x0e a column break, \x07 a table cell or
# row mark; \x01/\x02/\x05/\x08 anchor pictures, footnotes, annotations
# and drawn objects and carry no text of their own.
_BREAK_CHARS = re.compile("[\x0b\x0c\x0d\x0e]")
_DROP_CHARS = re.compile("[\x00-\x08\x0f-\x1f]")
# A field is \x13 <instruction> [\x14 <result>] \x15; fields nest (a TOC
# field contains hyperlink fields), so instructions are stripped innermost
# first, keeping only result text.
_FIELD_WITH_RESULT = re.compile("\x13[^\x13\x14\x15]*\x14([^\x13\x15]*)\x15")
_FIELD_NO_RESULT = re.compile("\x13[^\x13\x14\x15]*\x15")


class WordDocError(ValueError):
    """The bytes are not a Word 97 document this reader understands."""


def _read_streams(data: bytes) -> dict[str, bytes]:
    """The OLE compound file's streams by name."""
    if len(data) < 512 or data[:8] != OLE_MAGIC:
        raise WordDocError("not an OLE compound file")
    sector_size = 1 << struct.unpack_from("<H", data, 30)[0]
    mini_sector_size = 1 << struct.unpack_from("<H", data, 32)[0]
    num_fat_sectors = struct.unpack_from("<I", data, 44)[0]
    dir_start = struct.unpack_from("<i", data, 48)[0]
    mini_cutoff = struct.unpack_from("<I", data, 56)[0]
    minifat_start = struct.unpack_from("<i", data, 60)[0]
    difat_start = struct.unpack_from("<i", data, 68)[0]
    num_difat_sectors = struct.unpack_from("<I", data, 72)[0]
    entries_per_sector = sector_size // 4

    difat = list(struct.unpack_from("<109i", data, 76))
    sector = difat_start
    for _ in range(num_difat_sectors):
        if sector < 0:
            break
        chunk = struct.unpack_from(f"<{entries_per_sector}i", data, 512 + sector * sector_size)
        difat.extend(chunk[:-1])
        sector = chunk[-1]

    fat: list[int] = []
    for fat_sector in [s for s in difat if s >= 0][:num_fat_sectors]:
        fat.extend(struct.unpack_from(f"<{entries_per_sector}i", data, 512 + fat_sector * sector_size))

    def read_chain(start: int) -> bytes:
        out = bytearray()
        seen: set[int] = set()
        sector = start
        while sector >= 0 and sector not in seen and sector < len(fat):
            seen.add(sector)
            offset = 512 + sector * sector_size
            out += data[offset:offset + sector_size]
            sector = fat[sector]
        return bytes(out)

    directory = read_chain(dir_start)
    entries: list[tuple[str, int, int, int]] = []
    for offset in range(0, len(directory), 128):
        raw = directory[offset:offset + 128]
        if len(raw) < 128:
            break
        name_length = struct.unpack_from("<H", raw, 64)[0]
        if not 2 <= name_length <= 64:
            continue
        name = raw[: name_length - 2].decode("utf-16-le", errors="replace")
        entries.append((name, raw[66], struct.unpack_from("<i", raw, 116)[0], struct.unpack_from("<I", raw, 120)[0]))

    root = next((entry for entry in entries if entry[1] == 5), None)
    if root is None:
        raise WordDocError("OLE file has no root storage")
    mini_stream = read_chain(root[2])[: root[3]]

    minifat: list[int] = []
    if minifat_start >= 0:
        minifat_data = read_chain(minifat_start)
        minifat = list(struct.unpack_from(f"<{len(minifat_data) // 4}i", minifat_data))

    def read_mini_chain(start: int) -> bytes:
        out = bytearray()
        seen: set[int] = set()
        sector = start
        while sector >= 0 and sector not in seen and sector < len(minifat):
            seen.add(sector)
            offset = sector * mini_sector_size
            out += mini_stream[offset:offset + mini_sector_size]
            sector = minifat[sector]
        return bytes(out)

    streams: dict[str, bytes] = {}
    for name, entry_type, start, size in entries:
        if entry_type != 2:
            continue
        raw = read_mini_chain(start) if size < mini_cutoff else read_chain(start)
        streams[name] = raw[:size]
    return streams


def _piece_table(clx: bytes) -> bytes:
    """The Pcdt's PlcPcd, skipping any Prc property blocks before it."""
    pos = 0
    while pos < len(clx):
        clxt = clx[pos]
        if clxt == 1:
            pos += 3 + struct.unpack_from("<H", clx, pos + 1)[0]
        elif clxt == 2:
            length = struct.unpack_from("<I", clx, pos + 1)[0]
            return clx[pos + 5:pos + 5 + length]
        else:
            raise WordDocError(f"unexpected Clx block type {clxt}")
    raise WordDocError("Clx holds no piece table")


def extract_text(data: bytes) -> str:
    """The main-document text of a Word 97 ``.doc``, cleaned to plain text."""
    streams = _read_streams(data)
    word = streams.get("WordDocument")
    if word is None:
        raise WordDocError("OLE file has no WordDocument stream")
    magic, n_fib = struct.unpack_from("<HH", word, 0)
    if magic != WORD_FIB_MAGIC:
        raise WordDocError("WordDocument stream has no Word FIB")
    if n_fib < MIN_SUPPORTED_NFIB:
        raise WordDocError(f"unsupported Word version (nFib {n_fib})")
    flags = struct.unpack_from("<H", word, 0x000A)[0]
    table_name = "1Table" if flags & 0x0200 else "0Table"
    table = streams.get(table_name)
    if table is None:
        raise WordDocError(f"OLE file has no {table_name} stream")
    ccp_text = struct.unpack_from("<i", word, 0x004C)[0]
    fc_clx, lcb_clx = struct.unpack_from("<II", word, 0x01A2)

    plc = _piece_table(table[fc_clx:fc_clx + lcb_clx])
    piece_count = (len(plc) - 4) // 12
    cps = struct.unpack_from(f"<{piece_count + 1}i", plc, 0)
    parts: list[str] = []
    remaining = ccp_text
    for index in range(piece_count):
        if remaining <= 0:
            break
        fc_raw = struct.unpack_from("<I", plc, 4 * (piece_count + 1) + 8 * index + 2)[0]
        length = min(cps[index + 1] - cps[index], remaining)
        remaining -= length
        if fc_raw & 0x40000000:
            offset = (fc_raw & 0x3FFFFFFF) // 2
            parts.append(word[offset:offset + length].decode("cp1252", errors="replace"))
        else:
            parts.append(word[fc_raw:fc_raw + 2 * length].decode("utf-16-le", errors="replace"))
    return _clean_text("".join(parts))


def _clean_text(text: str) -> str:
    previous = None
    while previous != text:
        previous = text
        text = _FIELD_WITH_RESULT.sub(r"\1", text)
        text = _FIELD_NO_RESULT.sub("", text)
    text = text.replace("\x07", "\n")
    text = _BREAK_CHARS.sub("\n", text)
    text = _DROP_CHARS.sub("", text)
    lines = [" ".join(line.split()) for line in text.split("\n")]
    return re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip()
