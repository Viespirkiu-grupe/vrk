"""Archive the portraits the corpus still points at on vrk.lt (issue #118).

Portraits reached the corpus two ways. The 2016-2019 pages embed them as
base64, and ``scraper/shared/files.py`` has externalized those into
``photos/<candidateId>.<ext>`` sidecars beside the records since 2026-08-17:
2,199 files, hashed, shipped deduplicated in the corpus database. Every other
era links a URL on vrk.lt instead, and for 25,332 records that URL was all
the corpus held — the portrait existed for as long as VRK kept serving it,
which the 2004-era URL rot in the sitemap reconciliations shows it does not.

This fetches those URLs into the retained trees — beside the candidate's
pages, as ``portrait.<ext>`` plus a ``portrait.json`` naming the URL, the
fetch time and the hash — and nothing else. It does not touch ``data/``.
The record rewrite is the parsers' job: ``write_candidate_record`` reads the
retained portrait beside the page it parses and externalizes it exactly as
it does a base64 payload, so the corpus is regenerated with the usual

    python scripts/reparse_diff.py --full --jobs 8 --apply <election-id> ...

and the re-parse gate stays what it is: a record re-parsed from its retained
pages reproduces its sidecar, because the portrait is part of what was
retained. That is the whole design. The alternative — a script writing
sidecars into ``data/`` that no parse could reproduce — would have had the
gate and the backfill rewriting each other's work forever.

Both trees are written when a candidate is in both: ``samples-full/`` is
what ``--full`` re-parses, ``samples/html/`` what the fixture sweep and the
test suite parse. A URL is fetched once per run however many directories
want it, and a directory that lacks the portrait another directory already
holds gets a copy, not a request. A candidate whose ``portrait.json`` already
names the record's URL is done, so a re-run costs nothing; ``--retry-failed``
tries the failures again.

A URL that cannot be fetched is not left looking untried. Its
``portrait.json`` records the error, the parsers stamp the record's
``photoMeta`` with it, and a ``PortraitFetchFailed`` event (stage ``fetch``)
lands in the election's ``anomalies.jsonl`` — one per candidate, replaced on
every run, so a retry that succeeds clears it and one that fails again does
not double it. ``anomalies-report`` reads them back like any other event.

    python scripts/backfill_url_portraits.py                  # every election
    python scripts/backfill_url_portraits.py 2020-seimo       # named elections
    python scripts/backfill_url_portraits.py --dry-run        # count, no network
    python scripts/backfill_url_portraits.py --only-fixtures  # the fixture trees first
    python scripts/backfill_url_portraits.py --retry-failed 2000-seimo

Measured on the first run (2026-09-02/03): 25,332 URL-form records across
41 elections — 24,408 under ``photoSrc``, 924 under the 1996-1999 archive
family's ``photoUrl`` — every URL unique, every record with a retained
directory. 25,294 were archived in three hours at 0.2 s between requests:
5.2 GB, the 2020+ ``kandImg`` era's 17,667 portraits averaging 285 KB and
the older eras 8-20 KB; 24,375 JPEG, 911 PNG, six BMP, one GIF and one TIFF,
sniffed from the bytes because the 2012 tree serves BMP and TIFF as
``image/jpeg`` under ``.jpg`` names. 38 stay URLs: the 32 (2000 Seimas) and
5 (2005 Kėdainiai) hosted on lrs.lt, which answers 520 or 503 to any client,
and one 2020 Seimas image vrk.lt itself answers 404 for. Cloudflare 520/522
on vrk.lt are transient — ``--retry-failed`` cleared five of them.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scraper.shared.anomalies import build_anomaly_event, utc_now_iso  # noqa: E402
from scraper.shared.files import (  # noqa: E402
    IMAGE_EXTENSIONS,
    PORTRAIT_KEYS,
    PORTRAIT_META_NAME,
    read_retained_portrait,
    sniff_photo_type,
    write_json,
)
from scraper.shared.http import build_session  # noqa: E402

ANOMALIES_NAME = "anomalies.jsonl"
EVENT_TYPE = "PortraitFetchFailed"
SCRIPT_NAME = "backfill_url_portraits.py"
DEFAULT_PAUSE_SECONDS = 0.2
FETCH_TIMEOUT_SECONDS = 45
PROGRESS_EVERY = 500


@dataclass
class Target:
    """One URL-form record and the retained directories that can hold its portrait."""

    election_id: str
    candidate_id: str
    url: str
    retained_dir: Path | None
    fixture_dir: Path | None

    @property
    def dirs(self) -> list[Path]:
        return [path for path in (self.retained_dir, self.fixture_dir) if path is not None]


@dataclass
class ElectionStats:
    records: int = 0  # URL-form records in data/
    without_dir: int = 0  # retained nowhere: nothing can hold the portrait
    skipped: int = 0  # --only-fixtures, and the candidate has no fixture directory
    retained: int = 0  # already archived at this URL before the run
    failed_before: int = 0  # a recorded failure, left alone (no --retry-failed)
    copied: int = 0  # one tree had it, the other got a copy
    fetched: int = 0
    failed: int = 0
    bytes: int = 0
    #: candidateId -> the failure the anomaly file should carry after this run.
    failures: dict[str, dict[str, Any]] = field(default_factory=dict)
    #: The candidates whose `PortraitFetchFailed` rows this run is
    #: authoritative for.
    processed: set[str] = field(default_factory=set)


def portrait_url(record: dict[str, Any]) -> str | None:
    """The record's portrait URL, or None for a sidecar, an empty value or no photo."""
    profile = (record.get("rawData") or {}).get("profile")
    if not isinstance(profile, dict):
        return None
    key = next((name for name in PORTRAIT_KEYS if name in profile), None)
    value = profile.get(key) if key else None
    if isinstance(value, str) and value.startswith(("http://", "https://")):
        return value
    return None


def election_targets(repo_root: Path, election_id: str) -> list[Target]:
    targets: list[Target] = []
    for record_path in sorted((repo_root / "data" / election_id).glob("*.json")):
        record = json.loads(record_path.read_text(encoding="utf-8"))
        url = portrait_url(record)
        if url is None:
            continue
        candidate_id = str(record.get("candidateId") or "")
        retained_dir = repo_root / "samples-full" / election_id / candidate_id
        fixture_dir = repo_root / "samples" / "html" / election_id / candidate_id
        targets.append(
            Target(
                election_id,
                candidate_id,
                url,
                retained_dir if candidate_id and retained_dir.is_dir() else None,
                fixture_dir if candidate_id and fixture_dir.is_dir() else None,
            )
        )
    return targets


def retained_state(candidate_dir: Path, url: str) -> str | None:
    """`"ok"`, `"failed"`, or None when the directory holds no attempt at this URL."""
    retained = read_retained_portrait(candidate_dir)
    if retained is None or retained["url"] != url:
        return None
    name = retained.get("file")
    if isinstance(name, str) and (candidate_dir / name).is_file():
        return "ok"
    return "failed"


def fetch_portrait(session: requests.Session, url: str) -> tuple[bytes | None, str | None]:
    """(bytes, None) for an image, (None, why) for anything else.

    A status other than 200 is a failure, and so is a 200 whose body is not
    an image — a site that answers a retired path with an HTML page would
    otherwise be archived as a portrait.
    """
    try:
        response = session.get(url, timeout=FETCH_TIMEOUT_SECONDS)
    except requests.RequestException as exc:
        return None, f"{type(exc).__name__}: {exc}"[:300]
    if response.status_code != 200:
        return None, f"HTTP {response.status_code}"
    raw = response.content
    extension, _ = sniff_photo_type(raw)
    if extension not in IMAGE_EXTENSIONS:
        content_type = response.headers.get("Content-Type", "no content type")
        return None, f"not an image: {content_type}, {len(raw)} bytes"
    return raw, None


def _clear_portrait_files(candidate_dir: Path) -> None:
    # A URL that once resolved and now fails must not leave the old bytes
    # beside a portrait.json saying the fetch failed.
    for stale in candidate_dir.glob("portrait.*"):
        if stale.name != PORTRAIT_META_NAME:
            stale.unlink()


def write_retained_portrait(
    candidate_dir: Path,
    url: str,
    fetched_at: str,
    raw: bytes | None,
    error: str | None,
) -> dict[str, Any]:
    """Land a fetch result beside the candidate's pages; portrait.json is the commit."""
    _clear_portrait_files(candidate_dir)
    meta: dict[str, Any] = {"url": url, "fetchedAt": fetched_at}
    if raw is not None:
        extension, mime = sniff_photo_type(raw)
        name = f"portrait.{extension}"
        (candidate_dir / name).write_bytes(raw)
        meta.update(
            {
                "file": name,
                "mime": mime,
                "bytes": len(raw),
                "sha256": hashlib.sha256(raw).hexdigest(),
            }
        )
    else:
        meta["error"] = error
    write_json(candidate_dir / PORTRAIT_META_NAME, meta)
    return meta


def copy_retained_portrait(source_dir: Path, target_dir: Path) -> dict[str, Any]:
    """Replicate one directory's attempt — bytes and record — into another."""
    _clear_portrait_files(target_dir)
    retained = read_retained_portrait(source_dir)
    assert retained is not None
    name = retained.get("file")
    if isinstance(name, str):
        shutil.copy2(source_dir / name, target_dir / name)
    write_json(target_dir / PORTRAIT_META_NAME, retained)
    return retained


def failure_event(election_id: str, candidate_id: str, failure: dict[str, Any]) -> dict[str, Any]:
    event = build_anomaly_event(
        event_type=EVENT_TYPE,
        severity="warning",
        stage="fetch",
        election_id=election_id,
        candidate_id=candidate_id,
        source_url=failure.get("url"),
        detail={
            "url": failure.get("url"),
            "error": failure.get("error"),
            "fetchedAt": failure.get("fetchedAt"),
            "recordedBy": SCRIPT_NAME,
            "retry": f"python scripts/{SCRIPT_NAME} --retry-failed {election_id}",
        },
    )
    # The event is the fetch attempt, so it carries the attempt's time — a
    # rewrite on a later run must not make an old failure look fresh.
    if isinstance(failure.get("fetchedAt"), str):
        event["timestamp"] = failure["fetchedAt"]
    return event


def rewrite_failure_events(
    path: Path,
    election_id: str,
    processed: set[str],
    failures: dict[str, dict[str, Any]],
) -> tuple[int, int]:
    """Make the election's `PortraitFetchFailed` rows say what the retained tree says.

    Only the processed candidates' rows are this run's to replace; every
    other line — parse-stage events, the runner's fetch failures, rows for
    candidates a partial run did not reach — is kept verbatim. Returns
    (removed, written).
    """
    lines = path.read_text(encoding="utf-8").splitlines() if path.is_file() else []
    kept: list[str] = []
    removed = 0
    for line in lines:
        if not line.strip():
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            kept.append(line)
            continue
        if (
            isinstance(event, dict)
            and event.get("eventType") == EVENT_TYPE
            and event.get("candidateId") in processed
        ):
            removed += 1
            continue
        kept.append(line)
    fresh = [
        json.dumps(failure_event(election_id, candidate_id, failure), ensure_ascii=False)
        for candidate_id, failure in sorted(failures.items())
    ]
    if not removed and not fresh:
        return 0, 0
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(line + "\n" for line in kept + fresh), encoding="utf-8")
    return removed, len(fresh)


def backfill_election(
    repo_root: Path,
    election_id: str,
    session: requests.Session | None,
    *,
    pause: float = DEFAULT_PAUSE_SECONDS,
    dry_run: bool = False,
    retry_failed: bool = False,
    only_fixtures: bool = False,
    progress: bool = False,
) -> ElectionStats:
    stats = ElectionStats()
    #: url -> the attempt this run already made, so siblings sharing a URL
    #: (none in the corpus today, but the fetch is keyed on the URL anyway)
    #: cost one request.
    attempts: dict[str, tuple[bytes | None, str | None, str]] = {}
    targets = election_targets(repo_root, election_id)
    for index, target in enumerate(targets, 1):
        stats.records += 1
        if progress and not dry_run and index % PROGRESS_EVERY == 0:
            print(f"    {election_id}: {index}/{len(targets)} …", flush=True)
        if not target.dirs:
            stats.without_dir += 1
            continue
        if only_fixtures and target.fixture_dir is None:
            stats.skipped += 1
            continue

        states = {path: retained_state(path, target.url) for path in target.dirs}
        settled = [path for path, state in states.items() if state is not None]
        pending = [path for path, state in states.items() if state is None]
        if settled and not (retry_failed and states[settled[0]] == "failed"):
            # An attempt exists somewhere: the other directory gets a copy of
            # it, and the network is not asked again.
            if pending and not dry_run:
                for path in pending:
                    copy_retained_portrait(settled[0], path)
                stats.copied += 1
            retained = read_retained_portrait(settled[0])
            assert retained is not None
            if states[settled[0]] == "ok":
                stats.retained += 1
            else:
                stats.failed_before += 1
                stats.failures[target.candidate_id] = retained
            stats.processed.add(target.candidate_id)
            continue

        if dry_run:
            stats.fetched += 1
            continue
        if target.url in attempts:
            raw, error, fetched_at = attempts[target.url]
        else:
            assert session is not None
            raw, error = fetch_portrait(session, target.url)
            fetched_at = utc_now_iso()
            attempts[target.url] = (raw, error, fetched_at)
            time.sleep(pause)
        for path in target.dirs:
            meta = write_retained_portrait(path, target.url, fetched_at, raw, error)
        stats.processed.add(target.candidate_id)
        if raw is None:
            stats.failed += 1
            stats.failures[target.candidate_id] = meta
        else:
            stats.fetched += 1
            stats.bytes += len(raw)
    return stats


def describe(election_id: str, stats: ElectionStats, dry_run: bool) -> str:
    note = f"{election_id}: {stats.records} URL portrait(s)"
    if stats.retained:
        note += f", {stats.retained} retained"
    if stats.copied:
        note += f" ({stats.copied} copied across trees)"
    if stats.fetched:
        verb = "to fetch" if dry_run else "fetched"
        note += f", {stats.fetched} {verb}"
        if not dry_run:
            note += f" ({stats.bytes / 1e6:.1f} MB)"
    if stats.failed:
        note += f", {stats.failed} failed"
    if stats.failed_before:
        note += f", {stats.failed_before} failed earlier (left; --retry-failed)"
    if stats.skipped:
        note += f", {stats.skipped} without a fixture directory skipped"
    if stats.without_dir:
        note += f", {stats.without_dir} retained nowhere"
    if dry_run:
        note += " [dry run]"
    return note


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "election_id", nargs="*", help="Elections to archive. Defaults to every data/ directory."
    )
    parser.add_argument("--dry-run", action="store_true", help="Count what would be fetched; no network, no writes.")
    parser.add_argument(
        "--retry-failed",
        action="store_true",
        help="Fetch again the URLs whose last attempt failed.",
    )
    parser.add_argument(
        "--only-fixtures",
        action="store_true",
        help="Only candidates with a fixture directory (samples/html/) — the test suite's set.",
    )
    parser.add_argument(
        "--pause", type=float, default=DEFAULT_PAUSE_SECONDS, help="Seconds between requests."
    )
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=Path("."),
        help="Checkout holding data/ and the sample trees. Defaults to the cwd.",
    )
    args = parser.parse_args()

    data_root = args.repo_root / "data"
    if not data_root.is_dir():
        print(f"No {data_root}/ here — run from the repo root.", file=sys.stderr)
        return 2
    election_ids = args.election_id or sorted(
        child.name for child in data_root.iterdir() if child.is_dir()
    )

    session = None if args.dry_run else build_session()
    totals = ElectionStats()
    changed: list[str] = []
    exit_code = 0
    for election_id in election_ids:
        if not (data_root / election_id).is_dir():
            print(f"{election_id}: no data/ directory, skipped", file=sys.stderr)
            exit_code = 2
            continue
        stats = backfill_election(
            args.repo_root,
            election_id,
            session,
            pause=args.pause,
            dry_run=args.dry_run,
            retry_failed=args.retry_failed,
            only_fixtures=args.only_fixtures,
            progress=True,
        )
        if not stats.records:
            continue
        print(describe(election_id, stats, args.dry_run), flush=True)
        if not args.dry_run:
            removed, written = rewrite_failure_events(
                data_root / election_id / ANOMALIES_NAME,
                election_id,
                stats.processed,
                stats.failures,
            )
            if removed or written:
                print(f"    {ANOMALIES_NAME}: {EVENT_TYPE} rows {removed} → {written}")
            for candidate_id, failure in sorted(stats.failures.items()):
                print(f"    FAILED {candidate_id}: {failure.get('error')} — {failure.get('url')}")
        for name in ("records", "without_dir", "skipped", "retained", "failed_before", "copied", "fetched", "failed", "bytes"):
            setattr(totals, name, getattr(totals, name) + getattr(stats, name))
        if stats.fetched or stats.copied or stats.failed:
            changed.append(election_id)
        if stats.failed:
            exit_code = max(exit_code, 1)

    if len(election_ids) > 1:
        print("\n" + describe(f"{len(election_ids)} election(s)", totals, args.dry_run))
    if changed and not args.dry_run:
        print(
            "\nNow regenerate the records from the retained trees:\n"
            "  python scripts/reparse_diff.py --full --jobs 8 --apply "
            + " ".join(changed)
        )
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
