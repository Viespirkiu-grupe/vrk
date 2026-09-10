from __future__ import annotations

import json
from pathlib import Path
import shutil
from typing import Any

# The candidate pages are the 2016/2017 vintage, so the campaign-page handling
# comes from the April 2017 mayoral module: that era publishes some participant
# pages without a tab navigation and needs the treasurer-URL variants.
from scraper.elections.meru_2017.candidate_samples import (
    _dedupe_filename_slug,
    _extract_campaign_root_links,
    _extract_tab_links,
    _fetch_campaign_tabs,
    _label_slug_from_url,
)
from scraper.elections.savivaldybiu_2019.sitemap import ELECTION_ID
from scraper.shared.anomalies import build_anomaly_event
from scraper.shared.http import fetch_text
from scraper.shared.files import write_json

DEFAULT_SITEMAP_PATH = Path(f"sitemaps/{ELECTION_ID}.json")
DEFAULT_SAMPLES_ROOT = Path(f"samples/html/{ELECTION_ID}")

CAMPAIGN_TAB_SLUG = "politines-kampanijos-dalyvio-duomenys"

# The five tabs every candidate publishes.
BASE_EXPECTED_TABS = {
    "anketa",
    "biografija",
    "turto-ir-pajamu-deklaracijos",
    "privaciu-interesu-deklaracijos",
    "kita",
}

# As in 2023, the campaign tab varies by role rather than by election: a council
# candidate's campaign is run by the party list, so only candidates who also
# stand for mayor register as a campaign participant of their own. Expecting it
# unconditionally would raise a MissingExpectedTab warning for each of the
# 13,256 council-only candidates.
EXPECTED_TABS = BASE_EXPECTED_TABS | {CAMPAIGN_TAB_SLUG}
COUNCIL_EXPECTED_TABS = set(BASE_EXPECTED_TABS)

# Sitemap fields carried through to the candidate record. The municipal context
# — which municipality, which list, which seat order, whether the person was
# elected — exists only on the listing pages, never on the candidate page.
CARRIED_ENTRY_FIELDS = (
    "candidateNote",
    "vrkCandidateId",
    "municipality",
    "roles",
    "councilCandidacy",
    "mayoralCandidacy",
)


def expected_tabs_for(entry: dict[str, Any]) -> set[str]:
    roles = entry.get("roles")
    if isinstance(roles, list) and "meras" in roles:
        return set(EXPECTED_TABS)
    return set(COUNCIL_EXPECTED_TABS)


def normalize_space(value: str) -> str:
    return " ".join(value.split())


def _load_sitemap_entries(sitemap_path: Path) -> list[dict[str, Any]]:
    payload = json.loads(sitemap_path.read_text(encoding="utf-8"))
    entries = payload.get("entries")
    if not isinstance(entries, list) or not entries:
        raise ValueError(f"No sitemap entries found in {sitemap_path}")

    normalized_entries: list[dict[str, Any]] = []
    for raw_entry in entries:
        if not isinstance(raw_entry, dict):
            continue

        candidate_name = str(raw_entry.get("candidateName", "")).strip()
        candidate_id = str(raw_entry.get("candidateId", "")).strip()
        url = str(raw_entry.get("url", "")).strip()

        if not candidate_name or not candidate_id or not url:
            continue

        entry: dict[str, Any] = {
            "candidateName": candidate_name,
            "candidateId": candidate_id,
            "url": url,
        }
        for field in CARRIED_ENTRY_FIELDS:
            if field in raw_entry:
                entry[field] = raw_entry[field]
        normalized_entries.append(entry)

    if not normalized_entries:
        raise ValueError(f"No valid sitemap entries found in {sitemap_path}")

    return normalized_entries


def _load_first_sitemap_entry(sitemap_path: Path) -> dict[str, Any]:
    return _load_sitemap_entries(sitemap_path)[0]


def _load_sitemap_entries_by_candidate_id(sitemap_path: Path) -> dict[str, dict[str, Any]]:
    return {entry["candidateId"]: entry for entry in _load_sitemap_entries(sitemap_path)}


def _fetch_candidate_tabs(
    entry: dict[str, Any],
    samples_root: Path,
    allow_new_candidate_dir: bool,
) -> dict[str, Any]:
    candidate_dir = samples_root / entry["candidateId"]
    if not candidate_dir.exists() and not allow_new_candidate_dir:
        raise ValueError(
            "Refusing to create new sample candidate directory "
            f"{candidate_dir}. Samples are fixture-only by default. "
            "Pass --allow-new-samples to enable one-time fixture capture."
        )
    candidate_dir.mkdir(parents=True, exist_ok=True)

    anketa_html = fetch_text(entry["url"])
    anketa_path = candidate_dir / "anketa.html"
    anketa_path.write_text(anketa_html, encoding="utf-8")

    tab_links = _extract_tab_links(anketa_html)
    anomalies: list[dict[str, Any]] = []
    if not tab_links:
        anomalies.append(
            build_anomaly_event(
                event_type="TabLinkExtractionEmpty",
                severity="error",
                stage="fetch",
                election_id=ELECTION_ID,
                candidate_id=entry["candidateId"],
                source_url=entry["url"],
            )
        )

    found_tab_slugs = {tab["slug"] for tab in tab_links if tab["slug"]}
    missing_expected_tabs = sorted(expected_tabs_for(entry) - found_tab_slugs)
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

    seen_file_slugs: dict[str, int] = {}
    saved_tabs: list[dict[str, Any]] = []
    campaign_tab_url = ""

    for tab in tab_links:
        fallback_slug = _label_slug_from_url(tab["url"])
        file_slug = _dedupe_filename_slug(tab["slug"] or fallback_slug, seen_file_slugs)
        file_path = candidate_dir / f"{file_slug}.html"

        if tab["url"] == entry["url"]:
            file_path.write_text(anketa_html, encoding="utf-8")
            fetched = False
        else:
            try:
                tab_html = fetch_text(tab["url"])
            except Exception as exc:
                anomalies.append(
                    build_anomaly_event(
                        event_type="TabDownloadFailed",
                        severity="error",
                        stage="fetch",
                        election_id=ELECTION_ID,
                        candidate_id=entry["candidateId"],
                        source_url=entry["url"],
                        detail={
                            "tabLabel": tab["label"],
                            "tabSlug": tab["slug"],
                            "tabUrl": tab["url"],
                            "error": str(exc),
                        },
                    )
                )
                continue
            file_path.write_text(tab_html, encoding="utf-8")
            fetched = True

        if tab["slug"] == CAMPAIGN_TAB_SLUG:
            campaign_tab_url = tab["url"]

        saved_tabs.append(
            {
                "label": tab["label"],
                "slug": file_slug,
                "url": tab["url"],
                "path": str(file_path),
                "fetched": fetched,
            }
        )

    campaign_samples: list[dict[str, Any]] = []
    if campaign_tab_url:
        campaigns_root = candidate_dir / "campaigns"
        if campaigns_root.exists():
            shutil.rmtree(campaigns_root)

        campaign_links = _extract_campaign_root_links(campaign_tab_url)
        seen_campaign_keys: dict[str, int] = {}
        for link in campaign_links:
            base_key = link["campaignKey"] or "campaign"
            campaign_key = _dedupe_filename_slug(base_key, seen_campaign_keys)
            campaign_link = {
                "label": link.get("label", ""),
                "url": link["url"],
                "campaignKey": campaign_key,
            }
            campaign_samples.append(
                _fetch_campaign_tabs(
                    candidate_dir,
                    campaign_link,
                    anomalies,
                    candidate_id=entry["candidateId"],
                    candidate_url=entry["url"],
                )
            )

    if len(saved_tabs) < len(tab_links):
        anomalies.append(
            build_anomaly_event(
                event_type="TabDownloadPartial",
                severity="error",
                stage="fetch",
                election_id=ELECTION_ID,
                candidate_id=entry["candidateId"],
                source_url=entry["url"],
                detail={"tabCount": len(tab_links), "tabsSaved": len(saved_tabs)},
            )
        )

    index_path = candidate_dir / "index.json"
    index_payload = {
        "electionId": ELECTION_ID,
        "candidate": entry,
        "anketaPath": str(anketa_path),
        "tabCount": len(tab_links),
        "tabSamples": saved_tabs,
        "missingExpectedTabs": missing_expected_tabs,
        "campaignSamples": campaign_samples,
        "anomalies": anomalies,
    }
    write_json(index_path, index_payload)

    return {
        "election_id": ELECTION_ID,
        "candidate": entry,
        "candidate_dir": candidate_dir,
        "anketa_path": anketa_path,
        "tab_count": len(tab_links),
        "tabs_saved": len(saved_tabs),
        "missing_expected_tabs": missing_expected_tabs,
        "campaign_samples": campaign_samples,
        "anomalies": anomalies,
        "index_path": index_path,
    }


def fetch_first_candidate_with_tabs(
    sitemap_path: Path = DEFAULT_SITEMAP_PATH,
    samples_root: Path = DEFAULT_SAMPLES_ROOT,
    allow_new_candidate_dir: bool = False,
) -> dict[str, Any]:
    entry = _load_first_sitemap_entry(sitemap_path)
    return _fetch_candidate_tabs(
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
    missing_ids = [cid for cid in candidate_ids if cid not in entries_by_id]
    if missing_ids:
        raise ValueError(
            "Candidate IDs not found in sitemap: " + ", ".join(sorted(set(missing_ids)))
        )

    results: list[dict[str, Any]] = []
    for candidate_id in candidate_ids:
        results.append(
            _fetch_candidate_tabs(
                entry=entries_by_id[candidate_id],
                samples_root=samples_root,
                allow_new_candidate_dir=allow_new_candidate_dir,
            )
        )

    return {"election_id": ELECTION_ID, "count": len(results), "results": results}
