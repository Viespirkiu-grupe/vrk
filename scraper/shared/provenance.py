"""The record's provenance block: what page it came from, when, through what.

A corpus rewritten in place cannot answer "which parser wrote this?" or "has
the page changed since?" from the outside — two `people.json` builds coexisted
on one machine in 2026 disagreeing by 21,000 records with nothing inside
either file saying which corpus produced it (issue #89). So the answer now
lives inside every record, stamped by ``write_candidate_record``:

    "provenance": {
      "fetchedAt":    "2026-08-18T11:09:45+00:00",
      "parsedAt":     "2026-08-31T20:41:10+00:00",
      "parserCommit": "a5e1332",
      "sourceSha256": "…",
      "schemaVersion": 1
    }

``fetchedAt`` is the retained source file's modification time. The fetchers
write each page the moment it arrives and never touch it again, so the mtime
*is* the fetch time; measured against the sitemaps' ``generatedAt`` it agrees
for every retained tree, and it survived the corpus's one disk move. The
exception is the tracked fixture tree (``samples/html/``): git rewrites its
mtimes on every checkout, so a record parsed from a fixture — the small
elections whose fixture tree is the whole election — takes the election
sitemap's ``generatedAt`` instead, the scrape run's own timestamp. A wrong
plausible time is exactly the kind of metadata this block exists to end.

``sourceSha256`` hashes the retained file's bytes — the record's *primary*
page, the one at ``source.candidateSourceUrl`` — the same way
``photoMeta.sha256`` already fingerprints portraits. It is what lets a
re-parse gate split "the parser changed" from "the page changed"
(scripts/reparse_diff.py). It is a fingerprint of the retained *file*, not
proof of what vrk.lt served: the fetchers decode a page and write the string,
so a page whose bytes the fetcher could not decode is hashed as its
re-encoding. 130 retained pages hold 192 such characters, from before the
decode became explicit and reportable (issue #136,
``scraper/shared/http.py``).

``parserCommit`` is ``git rev-parse --short HEAD`` where the parsers live,
with ``-dirty`` appended when the working tree has uncommitted changes, and
``null`` where git is absent (a release tarball). ``parsedAt`` and
``parserCommit`` describe the parse *run*, so they differ between two honest
runs of the same code; consumers comparing records compare the other three.
"""

from __future__ import annotations

from datetime import datetime, timezone
from functools import lru_cache
import hashlib
import json
from pathlib import Path
import subprocess
from typing import Any

#: Bumped when the record envelope changes shape incompatibly.
PROVENANCE_SCHEMA_VERSION = 1

#: The provenance keys that describe the parse run rather than the data —
#: two honest runs of the same parser over the same page differ in exactly
#: these, so the re-parse gate excludes them from its diff.
VOLATILE_KEYS = frozenset({"parsedAt", "parserCommit"})


def utc_iso(timestamp: float) -> str:
    return (
        datetime.fromtimestamp(timestamp, tz=timezone.utc)
        .replace(microsecond=0)
        .isoformat()
    )


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


@lru_cache(maxsize=1)
def parser_commit() -> str | None:
    """The commit the parsers are at, read where the code lives (this file's
    directory works from any cwd, including a bare data tree), ``-dirty``
    when the checkout has uncommitted changes so a stamp cannot claim code
    it does not contain. Cached: one pair of git calls per process."""
    cwd = Path(__file__).resolve().parent
    try:
        commit = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=cwd,
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return None
    if not commit:
        return None
    try:
        dirty = bool(
            subprocess.run(
                ["git", "status", "--porcelain"],
                cwd=cwd,
                capture_output=True,
                text=True,
                check=True,
            ).stdout.strip()
        )
    except (OSError, subprocess.CalledProcessError):
        dirty = False
    return f"{commit}-dirty" if dirty else commit


@lru_cache(maxsize=128)
def _sitemap_generated_at(sitemap_path: Path) -> str | None:
    try:
        payload = json.loads(sitemap_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    generated = payload.get("generatedAt") if isinstance(payload, dict) else None
    return generated if isinstance(generated, str) and generated else None


def fetched_at_for(source_path: Path) -> str:
    """When the source page was fetched: the file's own mtime, except for a
    tracked fixture (``…/samples/html/<election>/…``), whose mtime is just
    the git checkout — there the election sitemap's ``generatedAt`` stands
    in, the timestamp of the scrape run that fetched the page."""
    resolved = source_path.resolve()
    parts = resolved.parts
    for index in range(len(parts) - 3):
        if parts[index] == "samples" and parts[index + 1] == "html":
            sitemap_path = Path(*parts[:index]) / "sitemaps" / f"{parts[index + 2]}.json"
            generated = _sitemap_generated_at(sitemap_path)
            if generated:
                return generated
            break
    return utc_iso(source_path.stat().st_mtime)


def build_provenance(source_path: Path) -> dict[str, Any]:
    """The provenance block for a record parsed from ``source_path``."""
    raw = source_path.read_bytes()
    return {
        "fetchedAt": fetched_at_for(source_path),
        "parsedAt": utc_now_iso(),
        "parserCommit": parser_commit(),
        "sourceSha256": hashlib.sha256(raw).hexdigest(),
        "schemaVersion": PROVENANCE_SCHEMA_VERSION,
    }


def comparable_provenance(provenance: Any) -> Any:
    """The block with the parse-run keys dropped — what two runs over the
    same bytes must agree on."""
    if not isinstance(provenance, dict):
        return provenance
    return {key: value for key, value in provenance.items() if key not in VOLATILE_KEYS}
