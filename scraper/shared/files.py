import base64
import binascii
import hashlib
import errno
import json
import os
import re
import unicodedata
from pathlib import Path
from typing import Any

from scraper.shared.provenance import build_provenance


def ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def write_json(
    path: Path,
    data: Any,
    indent: int | None = 2,
    separators: tuple[str, str] | None = None,
    newline: bool = True,
) -> None:
    """Every JSON file this project writes, landed atomically.

    Serialized first and landed with `os.replace`: the runners resume on file
    existence, so a write that dies halfway must leave either the previous
    file or nothing — never a truncated file that counts as done (issue #95).

    The layout parameters exist so that the files whose format is not the
    corpus's two-space indent can be written through here anyway — the point
    is the atomicity, not the layout (issue #153):

    * `indent=1` for the two registries checked in at one space
      (`scraper/shared/vietovardziai.json`, `scraper/parties.json`);
    * `indent=None, separators=(",", ":"), newline=False` for
      `dashboard/people.json`, 29 MB of compact JSON the page fetches whole,
      and the file with the most to lose from a half-write.
    """
    payload = json.dumps(data, ensure_ascii=False, indent=indent, separators=separators)
    if newline:
        payload += "\n"
    ensure_parent(path)
    tmp_path = path.with_name(path.name + ".tmp")
    tmp_path.write_text(payload, encoding="utf-8")
    os.replace(tmp_path, path)


def load_candidate_index(candidate_dir: Path) -> dict[str, Any]:
    """A retained candidate's `index.json`, or a raise.

    The fetch stage writes this file last and the parse stage reads its
    `candidate` block for the candidacy, the source URL, the display name and
    the campaign sample list. Eight modules had a copy of this function and
    all eight answered `{}` for a file that was absent *or* would not parse —
    so a half-written `index.json` produced a record that looks complete and
    is not.

    Measured on the tracked 2023 fixture `mykolas-majauskas-2420485` with its
    5,666-byte index truncated to 4,000: the parse wrote a record, reported
    zero anomalies, and lost `kandidatavimas` (vrkCandidateId, savivaldybė,
    roles, meras all null), the whole 29,894-character campaign section, and
    `source.candidateSourceUrl`; `candidateName` fell back to the page's
    shouted heading and `normalized` went from 37,034 characters to 7,097.
    28 modules read it, covering 54,711 of the corpus's 113,073 records
    (issue #153).

    So it raises, both ways. `FileNotFoundError` is what `anketa.html`'s
    absence already raises and what the runner turns into a recorded
    `CandidateParseFailed`; a `JSONDecodeError` means the fetch did not
    finish, and the answer to that is to fetch the candidate again, which a
    recorded failure says and a quietly degraded record does not.
    """
    index_path = candidate_dir / "index.json"
    if not index_path.exists():
        raise FileNotFoundError(errno.ENOENT, "Missing candidate index", str(index_path))
    payload = json.loads(index_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{index_path}: expected a JSON object, got {type(payload).__name__}")
    return payload


def slugify(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", text)
    ascii_text = normalized.encode("ascii", "ignore").decode("ascii")
    lowered = ascii_text.lower().strip()
    cleaned = re.sub(r"[^a-z0-9]+", "-", lowered)
    return cleaned.strip("-")


# Byte signatures of every photo container VRK has served: 2,196 JPEG, 2 PNG
# and one ZIP a candidate uploaded as their portrait in the embedded eras
# (measured 2026-08-19), and among the linked portraits fetched for issue
# #118 (2026-09-02) 24,375 JPEG, 911 PNG, six BMP, one GIF and one TIFF —
# the 2012 Seimas tree serves the BMPs and the TIFF as `image/jpeg` under a
# `.jpg` name, which is why the container is sniffed from the bytes and never
# taken from the URL.
_PHOTO_SIGNATURES = [
    (b"\xff\xd8\xff", "jpg", "image/jpeg"),
    (b"\x89PNG", "png", "image/png"),
    (b"GIF8", "gif", "image/gif"),
    (b"BM", "bmp", "image/bmp"),
    (b"II*\x00", "tif", "image/tiff"),
    (b"MM\x00*", "tif", "image/tiff"),
    (b"PK\x03\x04", "zip", "application/zip"),
]

#: The containers a fetched portrait is accepted in. A URL that answers with
#: anything else — an HTML error page served with a 200, an empty body — is a
#: failed fetch, not a portrait (scripts/backfill_url_portraits.py).
IMAGE_EXTENSIONS = frozenset({"jpg", "png", "gif", "bmp", "tif"})

#: The raw profile keys that carry the portrait reference. Every family
#: writes `photoSrc`; the 1996-1999 Seimas archive family alone writes
#: `photoUrl` (scraper/shared/seimo_archive_1990s.py). A profile has one of
#: the two, and whichever it has is what the sidecar path replaces.
PORTRAIT_KEYS = ("photoSrc", "photoUrl")

#: The retained portrait beside a candidate's pages. `portrait.json` names
#: the URL the bytes were fetched from, when, and the `portrait.<ext>` file
#: holding them — or, for a URL that could not be fetched, the error it met.
#: `scripts/backfill_url_portraits.py` writes both; this module reads them.
PORTRAIT_META_NAME = "portrait.json"


def sniff_photo_type(raw: bytes) -> tuple[str, str]:
    """(extension, mime) of a photo payload, from its leading bytes.

    The embedded-photo eras serve extension-less "data:;base64," URIs and a
    URL's extension is only a claim, so the container is sniffed from the
    bytes themselves: `("bin", "application/octet-stream")` when no known
    signature matches.
    """
    for signature, extension, mime in _PHOTO_SIGNATURES:
        if raw.startswith(signature):
            return extension, mime
    return "bin", "application/octet-stream"


def _decode_data_uri(source: str) -> bytes | None:
    payload = source.partition(",")[2]
    try:
        raw = base64.b64decode(payload, validate=False)
    except (ValueError, binascii.Error):
        return None
    return raw or None


def read_retained_portrait(candidate_dir: Path) -> dict[str, Any] | None:
    """The `portrait.json` beside a candidate's retained pages, or None.

    A malformed file raises rather than reading as "no portrait": the
    retained tree is the corpus's source, and a corrupt entry in it is a
    finding, not an absence.
    """
    path = candidate_dir / PORTRAIT_META_NAME
    if not path.is_file():
        return None
    meta = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(meta, dict) or not isinstance(meta.get("url"), str):
        raise ValueError(f"{path}: not a retained portrait record (no url)")
    return meta


def _retained_portrait_bytes(candidate_dir: Path, retained: dict[str, Any]) -> bytes:
    name = retained.get("file")
    if not isinstance(name, str) or Path(name).name != name:
        raise ValueError(f"{candidate_dir / PORTRAIT_META_NAME}: file {name!r} is not a plain name")
    raw = (candidate_dir / name).read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    if retained.get("sha256") not in (None, digest):
        raise ValueError(
            f"{candidate_dir / name}: hashes to {digest}, but {PORTRAIT_META_NAME}"
            f" says {retained['sha256']} — the retained portrait is not what was fetched"
        )
    return raw


def externalize_record_photo(
    record: Any,
    output_path: Path,
    source_path: Path | None = None,
) -> None:
    """Move a record's portrait into a sidecar file next to the record.

    Two page eras, one storage form. The 2016-2019 pages embed the portrait
    as a base64 data URI — 362 MB of it, making a 70 KB record weigh
    megabytes — and every other era links a URL on vrk.lt that the corpus
    used to trust VRK to keep serving (issue #118). Either way the bytes
    land in photos/<candidateId>.<ext> beside the election's records; the
    profile's portrait key (`photoSrc`, or the archive family's `photoUrl`)
    and normalized.profilis.nuotrauka both become that relative path, and
    photoMeta keeps the hash so the file is verifiable against what VRK
    served — plus, for a fetched portrait, the URL it came from and when.

    The URL era's bytes are not on the page, so they are read from the
    retained tree: the `portrait.json` beside the record's primary page
    (`source_path`), written by scripts/backfill_url_portraits.py. That is
    what keeps the re-parse gate honest — a record re-parsed from its
    retained pages reproduces the sidecar form, because the portrait is part
    of what was retained. A URL whose `portrait.json` records a failed fetch
    keeps the URL and gains a photoMeta saying it was tried and how it
    failed, so "still a URL" is never mistaken for "never tried". A URL with
    no retained portrait, a `portrait.json` for a different URL, and an
    undecodable data URI are left untouched.
    """
    if not isinstance(record, dict):
        return
    profile = (record.get("rawData") or {}).get("profile")
    if not isinstance(profile, dict):
        return
    key = next((name for name in PORTRAIT_KEYS if name in profile), None)
    if key is None:
        return
    source = profile.get(key)
    if not isinstance(source, str):
        return

    origin: dict[str, Any] = {}
    if source.startswith("data:"):
        raw = _decode_data_uri(source)
        if raw is None:
            return
    elif source.startswith(("http://", "https://")) and source_path is not None:
        retained = read_retained_portrait(source_path.parent)
        if retained is None or retained["url"] != source:
            return
        if retained.get("file") is None:
            profile["photoMeta"] = {
                "url": source,
                "fetchedAt": retained.get("fetchedAt"),
                "error": retained.get("error"),
            }
            return
        raw = _retained_portrait_bytes(source_path.parent, retained)
        origin = {"url": source, "fetchedAt": retained.get("fetchedAt")}
    else:
        return

    extension, mime = sniff_photo_type(raw)
    candidate_id = str(record.get("candidateId") or output_path.stem)
    relative_path = f"photos/{candidate_id}.{extension}"
    photo_path = output_path.parent / relative_path
    ensure_parent(photo_path)
    photo_path.write_bytes(raw)

    profile[key] = relative_path
    profile["photoMeta"] = {
        "mime": mime,
        "bytes": len(raw),
        "sha256": hashlib.sha256(raw).hexdigest(),
        **origin,
    }
    profilis = (record.get("normalized") or {}).get("profilis")
    if isinstance(profilis, dict):
        profilis["nuotrauka"] = relative_path


def write_candidate_record(
    output_path: Path,
    record: Any,
    source_path: Path | None = None,
) -> None:
    # `source_path` is the record's primary page as retained on disk — the one
    # at source.candidateSourceUrl — and stamps the `provenance` block from it
    # (scraper/shared/provenance.py, issue #89). Every parser passes it; the
    # parameter stays optional so a caller without a retained page (none today)
    # writes an honest record with no block rather than a fabricated one. The
    # retained portrait, when there is one, sits beside that page too.
    if isinstance(record, dict) and source_path is not None and source_path.is_file():
        record["provenance"] = build_provenance(source_path)
    # The photo sidecar is written first on purpose: resume is keyed on the
    # record file's existence, so the record has to be the last thing to land —
    # a crash in between leaves an orphan photo a re-run overwrites, never a
    # record pointing at a photo that was never written.
    externalize_record_photo(record, output_path, source_path)
    write_json(output_path, record)
