"""Candidate page-set capture for the 2004 presidential election.

The five candidates share one listing page and have no per-candidate
questionnaire, so the fetcher here is the module's own rather than the
2015-era one: the shared listing is each candidate's ``anketa.html`` (the
profile card lives there), and the card's links are the sub-pages —

- ``turto-ir-pajamu-deklaracijos.html`` — the ``kand_pajam_l_<ID>.htm``
  declaration extracts, the corpus's usual name for the tab;
- ``biografija.doc`` and ``programa.doc`` — the Word documents, fetched
  as bytes and saved with their own extension (a ``.doc`` decoded as
  text is corrupt beyond repair); Auštrevičius published no programme,
  so ``programa`` is expected only where the card links it;
- ``nuotrauka.html`` — the full-portrait page behind the card's
  thumbnail (the page holds the only link to the full-size photo);
- ``patiketiniai`` — linked on every card and a 404 for all five
  (probed 2026-08-24), so it goes to ``unpublishedTabs``: recorded as a
  fact of the source, neither fetched nor reported missing, as the 2009
  presidential trustees tab established.

The scanned GIFs (the statement, Adamkus's health certificate) and the
campaign site stay URLs on the sitemap entry; they are images and an
external site, not VRK page content.

The index.json shape is the era fetcher's, so the parse stage and the
batch runner read this election like any other.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from scraper.elections.prezidento_2004.sitemap import ELECTION_ID
from scraper.shared.files import write_json
from scraper.elections.seimo_zirmunu_2015.candidate_samples import (
    _load_sitemap_entries,
    _load_sitemap_entries_by_candidate_id,
)
from scraper.shared.anomalies import build_anomaly_event
from scraper.shared.http import fetch_bytes, fetch_text

DEFAULT_SITEMAP_PATH = Path(f"sitemaps/{ELECTION_ID}.json")
DEFAULT_SAMPLES_ROOT = Path(f"samples/html/{ELECTION_ID}")

BASE_EXPECTED_TABS = {"anketa", "turto-ir-pajamu-deklaracijos", "biografija", "nuotrauka"}
UNPUBLISHED_TABS = {"patiketiniai"}

# (slug, label, sitemap key, binary) — the page-set in saved order after
# the anketa. A candidate without the sitemap URL simply lacks the tab.
SUBPAGES: list[tuple[str, str, str, bool]] = [
    ("turto-ir-pajamu-deklaracijos", "Deklaracija", "deklaracijaUrl", False),
    ("biografija", "Biografija", "biografijaUrl", True),
    ("programa", "Programa", "programaUrl", True),
    ("nuotrauka", "Nuotrauka", "nuotraukaPageUrl", False),
]

__all__ = [
    "BASE_EXPECTED_TABS",
    "UNPUBLISHED_TABS",
    "expected_tabs_for_entry",
    "fetch_candidates_with_tabs",
    "fetch_first_candidate_with_tabs",
]


def expected_tabs_for_entry(entry: dict[str, Any]) -> set[str]:
    expected = set(BASE_EXPECTED_TABS)
    if entry.get("programaUrl"):
        expected.add("programa")
    return expected


def _fetch_candidate(
    entry: dict[str, Any],
    samples_root: Path,
    allow_new_candidate_dir: bool,
    listing_html: str | None = None,
) -> dict[str, Any]:
    candidate_dir = samples_root / entry["candidateId"]
    if not candidate_dir.exists() and not allow_new_candidate_dir:
        raise ValueError(
            "Refusing to create new sample candidate directory "
            f"{candidate_dir}. Samples are fixture-only by default. "
            "Pass --allow-new-samples to enable one-time fixture capture."
        )
    candidate_dir.mkdir(parents=True, exist_ok=True)

    anomalies: list[dict[str, Any]] = []
    if listing_html is None:
        listing_html = fetch_text(entry["url"])
    anketa_path = candidate_dir / "anketa.html"
    anketa_path.write_text(listing_html, encoding="utf-8")
    saved_tabs: list[dict[str, Any]] = [
        {"label": "Anketa", "slug": "anketa", "url": entry["url"], "path": str(anketa_path), "fetched": False},
    ]

    tab_count = 1
    for slug, label, url_key, binary in SUBPAGES:
        url = entry.get(url_key)
        if not url:
            continue
        tab_count += 1
        file_path = candidate_dir / (f"{slug}.doc" if binary else f"{slug}.html")
        try:
            if binary:
                file_path.write_bytes(fetch_bytes(url))
            else:
                file_path.write_text(fetch_text(url), encoding="utf-8")
        except Exception as exc:
            anomalies.append(
                build_anomaly_event(
                    event_type="TabDownloadFailed",
                    severity="error",
                    stage="fetch",
                    election_id=ELECTION_ID,
                    candidate_id=entry["candidateId"],
                    source_url=entry["url"],
                    detail={"tabLabel": label, "tabSlug": slug, "tabUrl": url, "error": str(exc)},
                )
            )
            continue
        saved_tabs.append({"label": label, "slug": slug, "url": url, "path": str(file_path), "fetched": True})

    found_tab_slugs = {tab["slug"] for tab in saved_tabs}
    missing_expected_tabs = sorted(expected_tabs_for_entry(entry) - found_tab_slugs)
    if missing_expected_tabs:
        anomalies.append(
            build_anomaly_event(
                event_type="MissingExpectedTab",
                severity="warning",
                stage="fetch",
                election_id=ELECTION_ID,
                candidate_id=entry["candidateId"],
                source_url=entry["url"],
                detail={"missingTabs": missing_expected_tabs},
            )
        )

    unpublished_links = [
        {"label": "Patikėtiniai", "slug": "patiketiniai", "url": entry["patiketiniaiUrl"]}
    ] if entry.get("patiketiniaiUrl") else []

    index_path = candidate_dir / "index.json"
    index_payload = {
        "electionId": ELECTION_ID,
        "candidate": entry,
        "anketaPath": str(anketa_path),
        "tabCount": tab_count,
        "tabSamples": saved_tabs,
        "missingExpectedTabs": missing_expected_tabs,
        "unpublishedTabs": unpublished_links,
        "campaignSamples": [],
        "anomalies": anomalies,
    }
    write_json(index_path, index_payload)

    return {
        "election_id": ELECTION_ID,
        "candidate": entry,
        "candidate_dir": candidate_dir,
        "anketa_path": anketa_path,
        "tab_count": tab_count,
        "tabs_saved": len(saved_tabs),
        "missing_expected_tabs": missing_expected_tabs,
        "unpublished_tabs": unpublished_links,
        "campaign_samples": [],
        "anomalies": anomalies,
        "index_path": index_path,
    }


def fetch_first_candidate_with_tabs(
    sitemap_path: Path = DEFAULT_SITEMAP_PATH,
    samples_root: Path = DEFAULT_SAMPLES_ROOT,
    allow_new_candidate_dir: bool = False,
) -> dict[str, Any]:
    entry = _load_sitemap_entries(sitemap_path)[0]
    return _fetch_candidate(
        entry=entry,
        samples_root=samples_root,
        allow_new_candidate_dir=allow_new_candidate_dir,
    )


def fetch_candidates_with_tabs(
    candidate_ids: list[str],
    sitemap_path: Path = DEFAULT_SITEMAP_PATH,
    samples_root: Path = DEFAULT_SAMPLES_ROOT,
    allow_new_candidate_dir: bool = False,
) -> dict[str, Any]:
    if not candidate_ids:
        raise ValueError("At least one candidate id must be provided")

    entries_by_id = _load_sitemap_entries_by_candidate_id(sitemap_path)
    missing_ids = [candidate_id for candidate_id in candidate_ids if candidate_id not in entries_by_id]
    if missing_ids:
        raise ValueError(
            "Candidate IDs not found in sitemap: " + ", ".join(sorted(set(missing_ids)))
        )

    # One listing fetch serves every candidate's anketa.html: the page is
    # shared, and refetching it five times is five times the traffic for
    # the same bytes.
    listing_html: dict[str, str] = {}
    results: list[dict[str, Any]] = []
    for candidate_id in candidate_ids:
        entry = entries_by_id[candidate_id]
        if entry["url"] not in listing_html:
            listing_html[entry["url"]] = fetch_text(entry["url"])
        results.append(
            _fetch_candidate(
                entry=entry,
                samples_root=samples_root,
                allow_new_candidate_dir=allow_new_candidate_dir,
                listing_html=listing_html[entry["url"]],
            )
        )

    return {
        "election_id": ELECTION_ID,
        "count": len(results),
        "results": results,
    }
