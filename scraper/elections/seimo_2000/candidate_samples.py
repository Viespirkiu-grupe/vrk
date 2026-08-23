"""Candidate sample fetching for the 2000-10-08 Seimas general election.

One page per candidate: ``kandvl.htm-<ID>.htm`` carries the profile card,
the questionnaire, the income and asset declaration extract and the
autobiography in one document (its "Autobiografija" and "Pajamų
deklaracija" links are same-page anchors), so there are no tabs and no
sub-pages to follow. The page is saved as ``candidate.html``, as the
1996-1998 archive family saves its candidate page, with the same
``index.json`` shape so the generic CLI printing has what it expects.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from scraper.elections.seimo_2000.sitemap import DEFAULT_SITEMAP_PATH, ELECTION_ID, load_sitemap_entries
from scraper.shared.files import write_json
from scraper.shared.http import fetch_text

DEFAULT_SAMPLES_ROOT = Path(f"samples/html/{ELECTION_ID}")
CANDIDATE_PAGE_NAME = "candidate.html"

# No tabs on these pages; the generic fetch printing reads an empty set.
EXPECTED_TABS: list[str] = []

__all__ = [
    "CANDIDATE_PAGE_NAME",
    "EXPECTED_TABS",
    "fetch_candidate_sample",
    "fetch_candidates_with_tabs",
    "fetch_first_candidate_with_tabs",
]


def fetch_candidate_sample(
    entry: dict[str, Any],
    samples_root: Path,
    allow_new_candidate_dir: bool,
) -> dict[str, Any]:
    candidate_dir = samples_root / entry["candidateId"]
    if not candidate_dir.exists() and not allow_new_candidate_dir:
        raise ValueError(
            f"Refusing to create new sample candidate directory {candidate_dir}. "
            "Samples are fixture-only by default. Pass --allow-new-samples to "
            "enable one-time fixture capture."
        )
    candidate_dir.mkdir(parents=True, exist_ok=True)

    candidate_path = candidate_dir / CANDIDATE_PAGE_NAME
    candidate_path.write_text(fetch_text(entry["url"]), encoding="utf-8")

    index_path = candidate_dir / "index.json"
    write_json(
        index_path,
        {
            "candidate": entry,
            "anketaPath": str(candidate_path),
            "tabCount": 1,
            "tabsSaved": 1,
            "anomalies": [],
        },
    )
    return {
        "candidate": entry,
        "candidate_dir": candidate_dir,
        "anketa_path": candidate_path,
        "tab_count": 1,
        "tabs_saved": 1,
        "missing_expected_tabs": [],
        "anomalies": [],
        "index_path": index_path,
    }


def fetch_candidates_with_tabs(
    candidate_ids: list[str],
    sitemap_path: Path = DEFAULT_SITEMAP_PATH,
    samples_root: Path = DEFAULT_SAMPLES_ROOT,
    allow_new_candidate_dir: bool = False,
) -> dict[str, Any]:
    if not candidate_ids:
        raise ValueError("At least one candidate id must be provided")
    entries_by_id = {entry["candidateId"]: entry for entry in load_sitemap_entries(sitemap_path)}
    missing_ids = [cid for cid in candidate_ids if cid not in entries_by_id]
    if missing_ids:
        raise ValueError("Candidate IDs not found in sitemap: " + ", ".join(sorted(set(missing_ids))))
    results = [
        fetch_candidate_sample(entries_by_id[candidate_id], samples_root, allow_new_candidate_dir)
        for candidate_id in candidate_ids
    ]
    return {"count": len(results), "results": results}


def fetch_first_candidate_with_tabs(
    sitemap_path: Path = DEFAULT_SITEMAP_PATH,
    samples_root: Path = DEFAULT_SAMPLES_ROOT,
    allow_new_candidate_dir: bool = False,
) -> dict[str, Any]:
    entry = load_sitemap_entries(sitemap_path)[0]
    return fetch_candidate_sample(entry, samples_root, allow_new_candidate_dir)
