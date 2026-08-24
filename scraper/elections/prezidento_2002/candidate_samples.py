"""Candidate page-set capture for the 2002 presidential election.

As for 2004, the seventeen candidates share one listing and have no
per-candidate questionnaire page, so the fetcher is the module's own:
the shared listing is each candidate's ``anketa.html``, and the card's
links are the sub-pages —

- ``biografija.html`` — the HTML biography (this era's one per-candidate
  text page);
- ``programa.doc`` — the Word 97 programme, fetched as bytes;
- the scans, archived as bytes so the primary source survives beside
  the record that links it: ``pareiskimas.jpg``, the two-page data
  questionnaire as ``duomenu-anketa-1.jpg``/``-2.jpg``,
  ``deklaracija.jpg``, and ``sveikata-1.jpg``/``-2.jpg`` where the card
  has them. No OCR is attempted — these are 2002 paper forms
  photographed, and a guessed transcription would be worse than none;
  the record carries the URLs and the archive keeps the pixels.
- ``patiketiniai`` — the trustee index survives but every per-candidate
  page behind it is a 404 (probed 2026-08-24), so it goes to
  ``unpublishedTabs``: recorded, neither fetched nor reported missing.
- ``sveikata`` — the health-certificate scans four cards link are all
  404 on VRK's mirror too (probed 2026-08-24; the Wayback Machine holds
  four of the five files, but the corpus links VRK sources), so they
  are the second unpublished tab: the card's URLs stay on the sitemap
  entry and in the record's fields, the files are not fetched.

The index.json shape is the era fetcher's, so the parse stage and the
batch runner read this election like any other.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from scraper.elections.prezidento_2002.sitemap import ELECTION_ID
from scraper.elections.seimo_zirmunu_2015.candidate_samples import (
    _load_sitemap_entries,
    _load_sitemap_entries_by_candidate_id,
)
from scraper.shared.anomalies import build_anomaly_event
from scraper.shared.http import fetch_bytes, fetch_text

DEFAULT_SITEMAP_PATH = Path(f"sitemaps/{ELECTION_ID}.json")
DEFAULT_SAMPLES_ROOT = Path(f"samples/html/{ELECTION_ID}")

BASE_EXPECTED_TABS = {
    "anketa",
    "biografija",
    "programa",
    "pareiskimas",
    "duomenu-anketa",
    "deklaracija",
}
UNPUBLISHED_TABS = {"patiketiniai", "sveikata"}

# Šustauskas's card links a second questionnaire page that was a 404 on
# the original 2002 site already (the Wayback Machine's earliest capture
# of the URL is itself a 404) — VRK never published it. A dead link of
# the source, not a fetch failure.
UNPUBLISHED_SCAN_URLS = {
    "https://www.vrk.lt/statiniai/puslapiai/rinkimai/2002/Prezidentas/docs/Sustauskas_anketa2.jpg",
}

__all__ = [
    "BASE_EXPECTED_TABS",
    "UNPUBLISHED_TABS",
    "expected_tabs_for_entry",
    "fetch_candidates_with_tabs",
    "fetch_first_candidate_with_tabs",
]


def expected_tabs_for_entry(entry: dict[str, Any]) -> set[str]:
    return set(BASE_EXPECTED_TABS)


def _subpage_files(entry: dict[str, Any]) -> list[tuple[str, str, str, str, bool]]:
    """(slug, filename, label, url, binary) for the card's sub-pages, in
    saved order. A one-file scan group keeps the plain name; a multi-file
    group is numbered in the card's own order."""
    files: list[tuple[str, str, str, str, bool]] = []
    if entry.get("biografijaUrl"):
        files.append(("biografija", "biografija.html", "Biografija", entry["biografijaUrl"], False))
    if entry.get("programaUrl"):
        files.append(("programa", "programa.doc", "Programa", entry["programaUrl"], True))
    if entry.get("pareiskimasUrl"):
        files.append(("pareiskimas", "pareiskimas.jpg", "Pareiškimas", entry["pareiskimasUrl"], True))
    for index, url in enumerate(entry.get("anketosSkenaiUrls") or [], start=1):
        files.append(
            ("duomenu-anketa", f"duomenu-anketa-{index}.jpg", f"Duomenų anketa {index}", url, True)
        )
    if entry.get("deklaracijaUrl"):
        files.append(
            ("deklaracija", "deklaracija.jpg", entry.get("deklaracijaLabel") or "Deklaracija", entry["deklaracijaUrl"], True)
        )
    return files


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
    found_slugs = {"anketa"}

    unpublished_links = [
        {"label": "Patikėtiniai", "slug": "patiketiniai", "url": entry["patiketiniaiUrl"]}
    ] if entry.get("patiketiniaiUrl") else []
    for url in entry.get("sveikatosSkenaiUrls") or []:
        unpublished_links.append({"label": "Sveikatos pažyma", "slug": "sveikata", "url": url})

    subpages = _subpage_files(entry)
    for slug, filename, label, url, binary in subpages:
        if url in UNPUBLISHED_SCAN_URLS:
            unpublished_links.append({"label": label, "slug": slug, "url": url})
            continue
        file_path = candidate_dir / filename
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
        found_slugs.add(slug)
        saved_tabs.append({"label": label, "slug": slug, "url": url, "path": str(file_path), "fetched": True})

    missing_expected_tabs = sorted(expected_tabs_for_entry(entry) - found_slugs)
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

    index_path = candidate_dir / "index.json"
    index_payload = {
        "electionId": ELECTION_ID,
        "candidate": entry,
        "anketaPath": str(anketa_path),
        "tabCount": 1 + len(subpages),
        "tabSamples": saved_tabs,
        "missingExpectedTabs": missing_expected_tabs,
        "unpublishedTabs": unpublished_links,
        "campaignSamples": [],
        "anomalies": anomalies,
    }
    index_path.write_text(
        json.dumps(index_payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    return {
        "election_id": ELECTION_ID,
        "candidate": entry,
        "candidate_dir": candidate_dir,
        "anketa_path": anketa_path,
        "tab_count": 1 + len(subpages),
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

    # One listing fetch serves every candidate's anketa.html — the page is
    # shared, and seventeen refetches would be seventeen times the traffic
    # for the same bytes.
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
