import base64
import binascii
import hashlib
import json
import re
import unicodedata
from pathlib import Path
from typing import Any


def ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def write_json(path: Path, data: Any) -> None:
    ensure_parent(path)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def slugify(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", text)
    ascii_text = normalized.encode("ascii", "ignore").decode("ascii")
    lowered = ascii_text.lower().strip()
    cleaned = re.sub(r"[^a-z0-9]+", "-", lowered)
    return cleaned.strip("-")


# Byte signatures of every photo container VRK has served (2,196 JPEG, 2 PNG
# and one ZIP a candidate uploaded as their portrait, measured 2026-08-19).
_PHOTO_SIGNATURES = [
    (b"\xff\xd8\xff", "jpg", "image/jpeg"),
    (b"\x89PNG", "png", "image/png"),
    (b"GIF8", "gif", "image/gif"),
    (b"PK\x03\x04", "zip", "application/zip"),
]


def _sniff_photo_type(raw: bytes) -> tuple[str, str]:
    # The embedded-photo eras serve extension-less "data:;base64," URIs, so
    # the container is sniffed from the decoded bytes.
    for signature, extension, mime in _PHOTO_SIGNATURES:
        if raw.startswith(signature):
            return extension, mime
    return "bin", "application/octet-stream"


def externalize_record_photo(record: Any, output_path: Path) -> None:
    """Move an embedded base64 photo into a sidecar file next to the record.

    An embedded portrait used to make a 70 KB record weigh megabytes — 362 MB
    of base64 across the 2016-2019 eras. The bytes land in
    photos/<candidateId>.<ext> beside the election's records;
    rawData.profile.photoSrc and normalized.profilis.nuotrauka both become
    that relative path, and photoMeta keeps the hash so the file is
    verifiable against what VRK served. URL-form photoSrc values (2020+) and
    undecodable payloads are left untouched.
    """
    if not isinstance(record, dict):
        return
    profile = (record.get("rawData") or {}).get("profile")
    if not isinstance(profile, dict):
        return
    source = profile.get("photoSrc")
    if not isinstance(source, str) or not source.startswith("data:"):
        return
    payload = source.partition(",")[2]
    try:
        raw = base64.b64decode(payload, validate=False)
    except (ValueError, binascii.Error):
        return
    if not raw:
        return

    extension, mime = _sniff_photo_type(raw)
    candidate_id = str(record.get("candidateId") or output_path.stem)
    relative_path = f"photos/{candidate_id}.{extension}"
    photo_path = output_path.parent / relative_path
    ensure_parent(photo_path)
    photo_path.write_bytes(raw)

    profile["photoSrc"] = relative_path
    profile["photoMeta"] = {
        "mime": mime,
        "bytes": len(raw),
        "sha256": hashlib.sha256(raw).hexdigest(),
    }
    profilis = (record.get("normalized") or {}).get("profilis")
    if isinstance(profilis, dict):
        profilis["nuotrauka"] = relative_path


def write_candidate_record(output_path: Path, record: Any) -> None:
    externalize_record_photo(record, output_path)
    write_json(output_path, record)
