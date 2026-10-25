"""Build the web portraits: one small WebP per person (issue #187).

The corpus keeps every portrait VRK ever published, full size and in its
original container -- 27,493 files and 5.2 GB under
`data/<election-id>/photos/<candidateId>.<ext>`, released as three
`vrk-photos-N.sqlite` parts. That is the archive. The browser shows one
portrait per person in a 96x128 box, and shipping the archive to a server to
fill that box is what kept production without photos (#185). This script
builds the web asset instead: `portraits/<pid>.webp`, 192x256 (2x the
desktop box, which also covers a 2x phone), keyed by the person id the page
already routes by.

Per person, from the person index in `dashboard/`:

- **Source.** The newest candidacy whose portrait file exists -- people age,
  and the recent photo is the one a reader recognises. A file that does not
  decode (VRK published one Word document as a photo) falls back to the next
  older candidacy's.
- **Decode by content.** Pillow sniffs the container, so the BMP, TIFF and
  PNG files VRK served under `.jpg` (#118) decode as what they are.
- **Shape.** EXIF orientation applied, transparency flattened onto white, an
  embedded colour profile converted to sRGB, then cropped to 3:4 anchored at
  the top -- the page's `object-position: center top` -- and resized to
  192x256.
- **No metadata.** The WebP is written from a fresh image, so no EXIF, XMP
  or ICC chunk survives (#142's privacy rule). The file is a bare `VP8 `
  bitstream in a RIFF container, which the tests check chunk by chunk.

`portraits/manifest.json` makes the run incremental. Per person it records
the source path, its size, mtime and sha256, the settings hash and the
output's sha256; a person whose source and settings are unchanged is
skipped without decoding, a source that changed on disk is re-hashed before
anything is re-encoded, and an output is only rewritten when its bytes
differ, so its mtime (what the server's Last-Modified answers with) stays
put. Sources that failed to decode are recorded too, so a re-run does not
retry them. A re-run with nothing changed writes nothing.

The manifest's `version` is a short hash of every pid and output hash. The
person index carries it, and the page puts it on each portrait URL, so the
server can mark portraits immutable and a changed portrait is a new URL.

Finally the person index (`dashboard/people-list.json`) is re-stamped: `ph: 1` on exactly the people
whose `portraits/<pid>.webp` exists, and the version beside them. That is
the same pass `scripts/build_person_index.py` runs on every build, so the
order after a corpus change is: index, then portraits.

Run from the repo root:

    python scripts/build_web_portraits.py

Measured on the full corpus (2026-10-24): see docs/DASHBOARD.md.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import re
import struct
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

sys.path.insert(0, str(Path(__file__).resolve().parent))

from scraper.shared.files import write_json  # noqa: E402
from person_index_files import index_exists, load_index  # noqa: E402
from person_index_files import write_index as write_split  # noqa: E402

DATA_ROOT = Path("data")
#: The person index's directory (scripts/person_index_files.py, issue #186).
INDEX_PATH = Path("dashboard")
PORTRAITS_DIR = Path("portraits")
MANIFEST_NAME = "manifest.json"

WIDTH = 192
HEIGHT = 256
#: Chosen from a contact sheet of 24 portraits from 12 elections (2009-2023)
#: at q65, q75 and q85, averaging 3.2, 3.6 and 5.6 KB: q65 visibly softens
#: hair and skin at 2x zoom, and q85 costs half as much again for a
#: difference that does not survive the 96x128 box.
QUALITY = 75
#: libwebp's slowest, smallest method. At 192x256 it costs milliseconds.
METHOD = 6
#: Bumped by hand when the pipeline changes in a way the numbers above do not
#: show (the crop rule, the colour handling), so every portrait is rebuilt.
PIPELINE = 1

SETTINGS = {
    "format": "webp",
    "width": WIDTH,
    "height": HEIGHT,
    "quality": QUALITY,
    "method": METHOD,
    "pipeline": PIPELINE,
}


def settings_hash(settings: dict = SETTINGS) -> str:
    raw = json.dumps(settings, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.blake2s(raw, digest_size=6).hexdigest()


# --- selection --------------------------------------------------------------


def photo_files(data_root: Path) -> dict[tuple[str, str], Path]:
    """(election id, candidateId) -> the portrait sidecar on disk.

    Every sidecar is `photos/<candidateId>.<ext>`, one per candidate -- the
    file every record's `photoSrc` names (measured: 27,493 of 27,493) -- so
    a directory listing finds them without opening a record.
    """
    found: dict[tuple[str, str], Path] = {}
    for election_dir in sorted(p for p in data_root.iterdir() if p.is_dir()):
        photos = election_dir / "photos"
        if not photos.is_dir():
            continue
        for path in sorted(photos.iterdir()):
            if path.is_file() and not path.name.startswith("."):
                found[(election_dir.name, path.stem)] = path
    return found


def candidate_sources(person: dict, photos: dict[tuple[str, str], Path]) -> list[Path]:
    """The person's portrait files, newest candidacy first.

    `e` in people.json is chronological (the registry's order), so the last
    candidacy is the newest. Candidacies without a file are skipped.
    """
    sources = []
    for candidacy in reversed(person["e"]):
        path = photos.get((candidacy["id"], candidacy["c"]))
        if path is not None:
            sources.append(path)
    return sources


# --- one image --------------------------------------------------------------


def crop_box(width: int, height: int) -> tuple[int, int, int, int]:
    """The 3:4 box to cut: centred across, anchored at the top."""
    if width * HEIGHT > height * WIDTH:  # wider than 3:4
        cut = round(height * WIDTH / HEIGHT)
        left = (width - cut) // 2
        return (left, 0, left + cut, height)
    return (0, 0, width, min(height, round(width * HEIGHT / WIDTH)))


def render(raw: bytes, quality: int = QUALITY) -> bytes:
    """Source bytes in any container Pillow reads -> the web portrait.

    Raises on anything that does not decode as an image.
    """
    from PIL import Image, ImageCms, ImageOps

    with Image.open(io.BytesIO(raw)) as opened:
        # JPEG decodes at a reduced DCT scale when the result is still at
        # least twice the target: a 600x900 original costs a quarter of the
        # work, and the resize below does the rest.
        opened.draft("RGB", (WIDTH * 2, HEIGHT * 2))
        icc = opened.info.get("icc_profile")
        image = ImageOps.exif_transpose(opened)
        image.load()
    if image.mode in ("RGBA", "LA", "PA") or (image.mode == "P" and "transparency" in image.info):
        image = image.convert("RGBA")
        flat = Image.new("RGB", image.size, "white")
        flat.paste(image, mask=image.getchannel("A"))
        image = flat
    elif image.mode != "RGB":
        image = image.convert("RGB")
    if icc:
        # Stripping the profile without converting would shift an Adobe RGB
        # or camera-profile photo's colours; a broken profile is ignored.
        try:
            source = ImageCms.ImageCmsProfile(io.BytesIO(icc))
            image = ImageCms.profileToProfile(image, source, ImageCms.createProfile("sRGB"), outputMode="RGB")
        except (ImageCms.PyCMSError, OSError, ValueError):
            pass
    image = image.crop(crop_box(*image.size)).resize((WIDTH, HEIGHT), Image.Resampling.LANCZOS)
    # A fresh image carries no `info`, so nothing the source said about
    # itself -- EXIF, XMP, ICC -- can ride into the encoder.
    clean = Image.new("RGB", (WIDTH, HEIGHT))
    clean.paste(image)
    out = io.BytesIO()
    clean.save(out, "WEBP", quality=quality, method=METHOD)
    return out.getvalue()


def webp_chunk_types(raw: bytes) -> list[str]:
    """The RIFF chunk FourCCs of a WebP file, in order."""
    if raw[:4] != b"RIFF" or raw[8:12] != b"WEBP":
        raise ValueError("not a WebP file")
    chunks, offset = [], 12
    while offset + 8 <= len(raw):
        fourcc = raw[offset : offset + 4].decode("ascii", "replace")
        (size,) = struct.unpack("<I", raw[offset + 4 : offset + 8])
        chunks.append(fourcc)
        offset += 8 + size + (size & 1)
    return chunks


def _render_job(job: tuple[str, str, int]) -> tuple[str, str, str, bytes | None, str | None]:
    """One source in a worker: its sha256, and the portrait or why not."""
    pid, source, quality = job
    raw = Path(source).read_bytes()
    sha = hashlib.sha256(raw).hexdigest()
    try:
        return pid, source, sha, render(raw, quality), None
    except Exception as exc:  # noqa: BLE001 - every decode failure is the same outcome
        # Without the object addresses Pillow puts in some messages, so the
        # manifest is the same bytes on every run.
        reason = re.sub(r" at 0x[0-9a-f]+", "", f"{type(exc).__name__}: {exc}")
        return pid, source, sha, None, reason[:200]


# --- the run ----------------------------------------------------------------


def _fingerprint(path: Path) -> dict:
    stat = path.stat()
    return {"bytes": stat.st_size, "mtime_ns": stat.st_mtime_ns}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for block in iter(lambda: fh.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def _rel(path: Path, root: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return path.as_posix()


def load_manifest(portraits_dir: Path) -> dict:
    path = portraits_dir / MANIFEST_NAME
    if not path.is_file():
        return {"portraits": {}, "failed": {}}
    manifest = json.loads(path.read_text(encoding="utf-8"))
    manifest.setdefault("portraits", {})
    manifest.setdefault("failed", {})
    return manifest


def manifest_version(portraits: dict) -> str | None:
    """A short hash of every (pid, output) pair: the portraits' cache key."""
    if not portraits:
        return None
    digest = hashlib.blake2s(digest_size=4)
    for pid in sorted(portraits):
        digest.update(f"{pid}:{portraits[pid]['out']}\n".encode())
    return digest.hexdigest()


def build(
    people: list[dict],
    data_root: Path = DATA_ROOT,
    portraits_dir: Path = PORTRAITS_DIR,
    jobs: int | None = None,
    quality: int = QUALITY,
    log=print,
) -> dict:
    """Bring `portraits_dir` in line with `people`; return the run's counts."""
    settings = settings_hash({**SETTINGS, "quality": quality})
    photos = photo_files(data_root)
    old = load_manifest(portraits_dir)
    known_sha: dict[str, tuple[dict, str]] = {}
    for entry in old["portraits"].values():
        known_sha[entry["src"]] = ({"bytes": entry["bytes"], "mtime_ns": entry["mtime_ns"]}, entry["sha256"])
    for src, entry in old["failed"].items():
        known_sha[src] = ({"bytes": entry["bytes"], "mtime_ns": entry["mtime_ns"]}, entry["sha256"])

    def source_sha(path: Path, fingerprint: dict) -> str:
        cached = known_sha.get(_rel(path, data_root.parent))
        if cached and cached[0] == fingerprint:
            return cached[1]
        return _sha256(path)

    portraits: dict[str, dict] = {}
    failed: dict[str, dict] = {}
    # People still to render, each with their remaining sources newest-first.
    pending: dict[str, list[Path]] = {}
    counts = {"people": len(people), "with_source": 0, "unchanged": 0, "rendered": 0, "written": 0, "fallbacks": 0}

    for person in people:
        pid = person["pid"]
        sources = candidate_sources(person, photos)
        if not sources:
            continue
        counts["with_source"] += 1
        previous = old["portraits"].get(pid)
        remaining = []
        for path in sources:
            rel = _rel(path, data_root.parent)
            fingerprint = _fingerprint(path)
            prior_failure = old["failed"].get(rel)
            if prior_failure and prior_failure["settings"] == settings:
                if {"bytes": prior_failure["bytes"], "mtime_ns": prior_failure["mtime_ns"]} == fingerprint or (
                    prior_failure["sha256"] == source_sha(path, fingerprint)
                ):
                    failed[rel] = {**prior_failure, **fingerprint}
                    continue
            if (
                not remaining
                and previous
                and previous["src"] == rel
                and previous["settings"] == settings
                and (portraits_dir / f"{pid}.webp").is_file()
                and previous["sha256"] == source_sha(path, fingerprint)
            ):
                portraits[pid] = {**previous, **fingerprint}
                counts["unchanged"] += 1
                break
            remaining.append(path)
        else:
            if remaining:
                pending[pid] = remaining

    portraits_dir.mkdir(parents=True, exist_ok=True)
    # Round by round: every pending person's best remaining source, in
    # parallel; a failure moves that person to their next one.
    workers = jobs or os.cpu_count() or 1
    pool = ProcessPoolExecutor(max_workers=workers) if workers > 1 and pending else None
    try:
        attempt = 0
        while pending:
            queue = [(pid, str(paths[0]), quality) for pid, paths in pending.items()]
            log(f"rendering {len(queue)} portrait(s){' (fallback round)' if attempt else ''} on {workers} worker(s)")
            results = pool.map(_render_job, queue, chunksize=32) if pool else map(_render_job, queue)
            for pid, source, sha, body, error in results:
                path = Path(source)
                rel = _rel(path, data_root.parent)
                fingerprint = _fingerprint(path)
                if body is None:
                    failed[rel] = {**fingerprint, "sha256": sha, "settings": settings, "error": error}
                    pending[pid].pop(0)
                    if not pending[pid]:
                        del pending[pid]
                    continue
                counts["rendered"] += 1
                counts["fallbacks"] += attempt > 0
                out_sha = hashlib.sha256(body).hexdigest()
                target = portraits_dir / f"{pid}.webp"
                if not (target.is_file() and hashlib.sha256(target.read_bytes()).hexdigest() == out_sha):
                    tmp = target.with_name(target.name + ".tmp")
                    tmp.write_bytes(body)
                    os.replace(tmp, target)
                    counts["written"] += 1
                portraits[pid] = {
                    "src": rel,
                    **fingerprint,
                    "sha256": sha,
                    "settings": settings,
                    "out": out_sha,
                    "outBytes": len(body),
                }
                del pending[pid]
            attempt += 1
    finally:
        if pool:
            pool.shutdown()

    # A person who no longer exists, or no longer has a decodable source,
    # keeps no portrait: the page would show a face the corpus does not.
    removed = 0
    for path in portraits_dir.glob("*.webp"):
        if path.stem not in portraits:
            path.unlink()
            removed += 1
    counts["removed"] = removed

    manifest = {
        "settings": {**SETTINGS, "quality": quality},
        "settingsHash": settings,
        "version": manifest_version(portraits),
        "count": len(portraits),
        "bytes": sum(e["outBytes"] for e in portraits.values()),
        "portraits": dict(sorted(portraits.items())),
        "failed": dict(sorted(failed.items())),
    }
    manifest_path = portraits_dir / MANIFEST_NAME
    previous_body = manifest_path.read_text(encoding="utf-8") if manifest_path.is_file() else None
    if previous_body is None or json.loads(previous_body) != manifest:
        write_json(manifest_path, manifest, indent=1)
        counts["manifest_written"] = True
    else:
        counts["manifest_written"] = False
    counts.update(
        portraits=manifest["count"],
        bytes=manifest["bytes"],
        failed=len(failed),
        version=manifest["version"],
        no_portrait=counts["with_source"] - manifest["count"],
    )
    return counts


# --- the index flag ---------------------------------------------------------


def apply_portrait_flags(index: dict, portraits_dir: Path = PORTRAITS_DIR) -> bool:
    """Stamp `ph: 1` on the people with a web portrait; True if anything changed.

    The flag follows the file, not the manifest: a deployment that has
    people.json but not the portraits must request none (#185), and the
    file is what the server would answer with. The manifest's version rides
    beside as `portraits.v`, the query string that busts caches.
    """
    present = (
        {name[:-5] for name in os.listdir(portraits_dir) if name.endswith(".webp")}
        if portraits_dir.is_dir()
        else set()
    )
    changed = False
    for person in index["people"]:
        want = person["pid"] in present
        if want and person.get("ph") != 1:
            person["ph"] = 1
            changed = True
        elif not want and "ph" in person:
            del person["ph"]
            changed = True
    shown = sum(1 for person in index["people"] if person.get("ph"))
    summary = {"v": load_manifest(portraits_dir).get("version"), "n": shown} if shown else None
    if index.get("portraits") != summary:
        changed = True
        if summary is None:
            index.pop("portraits", None)
        else:
            index["portraits"] = summary
    return changed


def write_index(index: dict, path: Path = INDEX_PATH) -> None:
    # The same split files build_person_index.py writes.
    write_split(index, path)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--index", type=Path, default=INDEX_PATH, help="person index directory to read and re-stamp")
    parser.add_argument("--data-root", type=Path, default=DATA_ROOT)
    parser.add_argument("--out", type=Path, default=PORTRAITS_DIR, help="output directory")
    parser.add_argument("--jobs", type=int, default=None, help="worker processes (default: all cores)")
    args = parser.parse_args(argv)

    if not index_exists(args.index):
        print(f"No person index in {args.index}/ -- run scripts/build_person_index.py first.", file=sys.stderr)
        return 1
    if not args.data_root.is_dir():
        print(f"No {args.data_root}/ here -- run from the repo root.", file=sys.stderr)
        return 1
    started = time.monotonic()
    index = load_index(args.index)
    counts = build(index["people"], args.data_root, args.out, args.jobs)
    restamped = apply_portrait_flags(index, args.out)
    if restamped:
        write_index(index, args.index)
    elapsed = time.monotonic() - started
    print(f"people:              {counts['people']}")
    print(f"with a source file:  {counts['with_source']}")
    print(
        f"portraits:           {counts['portraits']} ({counts['bytes'] / 1e6:.1f} MB,"
        f" avg {counts['bytes'] / max(counts['portraits'], 1) / 1024:.1f} KB)"
    )
    print(f"  unchanged:         {counts['unchanged']}")
    print(f"  rendered:          {counts['rendered']} ({counts['written']} written, {counts['fallbacks']} from an older candidacy)")
    print(f"  removed:           {counts['removed']}")
    print(f"undecodable sources: {counts['failed']} ({counts['no_portrait']} people left without a portrait)")
    print(f"version:             {counts['version']}")
    print(f"index:               {args.index} {'re-stamped' if restamped else 'unchanged'}")
    print(f"took:                {elapsed:.1f} s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
