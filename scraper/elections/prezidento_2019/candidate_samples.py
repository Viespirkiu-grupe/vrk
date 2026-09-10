from __future__ import annotations

import json
from pathlib import Path
import re
import shutil
from typing import Any
from urllib.parse import urlparse

from bs4 import BeautifulSoup

from scraper.elections.prezidento_2019.sitemap import ELECTION_ID, resolve_candidate_url
from scraper.shared.anomalies import build_anomaly_event
from scraper.shared.campaign_tabs import (
    derive_subtab_links,
    is_absent_derived_tab,
    merge_campaign_tab_links,
)
from scraper.shared.files import slugify, write_json
from scraper.shared.http import fetch_text

DEFAULT_SITEMAP_PATH = Path("sitemaps/2019-prezidento.json")
DEFAULT_SAMPLES_ROOT = Path("samples/html/2019-prezidento")

# Presidential candidate tabs. The private-interest tab is singular here
# ("Interesų deklaracija") unlike the EP module, and there is an extra
# "Patikėtiniai" (trustees) tab that the other elections do not have.
EXPECTED_TABS = {
    "anketa",
    "biografija",
    "turto-ir-pajamu-deklaracijos",
    "interesu-deklaracija",
    "patiketiniai",
    "kita",
}

CAMPAIGN_TAB_SLUG = "politines-kampanijos-dalyvio-duomenys"
CAMPAIGN_LINK_PATTERN = re.compile(
    r"/(savarankiskas[^/]*|atstovaujamasis[^/]*)_pkdId-(\d+)\.html",
    flags=re.IGNORECASE,
)


def normalize_space(value: str) -> str:
    return " ".join(value.split())


def _load_sitemap_entries(sitemap_path: Path) -> list[dict[str, str]]:
    payload = json.loads(sitemap_path.read_text(encoding="utf-8"))
    entries = payload.get("entries")
    if not isinstance(entries, list) or not entries:
        raise ValueError(f"No sitemap entries found in {sitemap_path}")

    normalized_entries: list[dict[str, str]] = []
    for raw_entry in entries:
        if not isinstance(raw_entry, dict):
            continue

        candidate_name = str(raw_entry.get("candidateName", "")).strip()
        candidate_id = str(raw_entry.get("candidateId", "")).strip()
        url = str(raw_entry.get("url", "")).strip()

        if not candidate_name or not candidate_id or not url:
            continue

        normalized_entries.append(
            {
                "candidateName": candidate_name,
                "candidateId": candidate_id,
                "url": url,
            }
        )

    if not normalized_entries:
        raise ValueError(f"No valid sitemap entries found in {sitemap_path}")

    return normalized_entries


def _load_first_sitemap_entry(sitemap_path: Path) -> dict[str, str]:
    entries = _load_sitemap_entries(sitemap_path)
    return entries[0]


def _load_sitemap_entries_by_candidate_id(sitemap_path: Path) -> dict[str, dict[str, str]]:
    entries = _load_sitemap_entries(sitemap_path)
    return {entry["candidateId"]: entry for entry in entries}


def _extract_tab_links(candidate_html: str) -> list[dict[str, str]]:
    soup = BeautifulSoup(candidate_html, "lxml")
    links: list[dict[str, str]] = []

    for anchor in soup.select("ul#tabnav a[href]"):
        href = normalize_space(anchor.get("href", ""))
        if not href:
            continue
        label = normalize_space(anchor.get_text(" ", strip=True))
        links.append(
            {
                "label": label,
                "slug": slugify(label),
                "url": resolve_candidate_url(href),
            }
        )

    return links


def _dedupe_filename_slug(slug: str, seen: dict[str, int]) -> str:
    base = slug or "tab"
    seen[base] = seen.get(base, 0) + 1
    if seen[base] == 1:
        return base
    return f"{base}-{seen[base]}"


def _label_slug_from_url(url: str) -> str:
    file_name = Path(urlparse(url).path).name
    stem = Path(file_name).stem
    if "_" in stem:
        stem = stem.split("_", 1)[0]
    stem = stem.replace("preKandidatas", "")
    stem = stem.strip("-")
    return slugify(stem)


def _extract_campaign_key_from_url(url: str) -> str:
    parsed = urlparse(url)
    stem = Path(parsed.path).stem
    match = CAMPAIGN_LINK_PATTERN.search(parsed.path)
    if match:
        campaign_type = slugify(match.group(1))
        pkd_id = match.group(2)
        return f"{campaign_type}-pkdid-{pkd_id}"
    return slugify(stem)


def _extract_campaign_root_links(fallback_url: str) -> list[dict[str, str]]:
    fallback_key = _extract_campaign_key_from_url(fallback_url)
    return [
        {
            "label": "",
            "url": fallback_url,
            "campaignKey": fallback_key,
        }
    ]


def _fetch_campaign_tabs(
    candidate_dir: Path,
    campaign_link: dict[str, str],
    anomalies: list[dict[str, Any]],
    candidate_id: str,
    candidate_url: str,
) -> dict[str, Any]:
    campaign_url = campaign_link["url"]
    campaign_key = campaign_link["campaignKey"]

    campaigns_root = candidate_dir / "campaigns"
    campaigns_root.mkdir(parents=True, exist_ok=True)

    campaign_dir = campaigns_root / campaign_key
    campaign_dir.mkdir(parents=True, exist_ok=True)

    try:
        root_html = fetch_text(campaign_url)
    except Exception as exc:
        anomalies.append(
            build_anomaly_event(
                event_type="CampaignRootFetchFailed",
                severity="error",
                stage="fetch",
                election_id=ELECTION_ID,
                candidate_id=candidate_id,
                source_url=candidate_url,
                detail={
                    "campaignUrl": campaign_url,
                    "campaignKey": campaign_key,
                    "error": str(exc),
                },
            )
        )
        return {
            "campaignKey": campaign_key,
            "campaignLabel": campaign_link.get("label", ""),
            "campaignUrl": campaign_url,
            "campaignDir": str(campaign_dir),
            "tabCount": 0,
            "tabSamples": [],
            "indexPath": "",
        }

    extracted_links = _extract_tab_links(root_html)
    has_tabnav = BeautifulSoup(root_html, "lxml").select_one("ul#tabnav") is not None
    # The rendered tab list depends on the participant type — an
    # atstovaujamasis root lists one tab of five, or none — so the five
    # sub-tab URLs are derived from the pkdId and the list only adds labels
    # (issue #99). A derived URL answering 404 is VRK not publishing that
    # sub-page (the 2016-2020-era trees), recorded rather than treated as a
    # download failure.
    tab_links = merge_campaign_tab_links(extracted_links, derive_subtab_links(campaign_url))
    seen_file_slugs: dict[str, int] = {}
    saved_tabs: list[dict[str, Any]] = []
    absent_tab_slugs: list[str] = []

    if not extracted_links:
        if has_tabnav:
            anomalies.append(
                build_anomaly_event(
                    event_type="CampaignTabLinkExtractionEmpty",
                    severity="warning",
                    stage="fetch",
                    election_id=ELECTION_ID,
                    candidate_id=candidate_id,
                    source_url=candidate_url,
                    detail={
                        "campaignUrl": campaign_url,
                        "campaignKey": campaign_key,
                    },
                )
            )
        root_path = campaign_dir / "root.html"
        root_path.write_text(root_html, encoding="utf-8")
    for tab in tab_links:
        fallback_slug = _label_slug_from_url(tab["url"])
        file_slug = _dedupe_filename_slug(tab["slug"] or fallback_slug, seen_file_slugs)
        file_path = campaign_dir / f"{file_slug}.html"

        if tab["url"] == campaign_url:
            file_path.write_text(root_html, encoding="utf-8")
            fetched = False
        else:
            try:
                tab_html = fetch_text(tab["url"])
            except Exception as exc:
                if is_absent_derived_tab(tab, exc):
                    absent_tab_slugs.append(file_slug)
                    continue
                anomalies.append(
                    build_anomaly_event(
                        event_type="CampaignTabDownloadFailed",
                        severity="error",
                        stage="fetch",
                        election_id=ELECTION_ID,
                        candidate_id=candidate_id,
                        source_url=candidate_url,
                        detail={
                            "campaignUrl": campaign_url,
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

        saved_tabs.append(
            {
                "label": tab["label"],
                "slug": file_slug,
                "url": tab["url"],
                "path": str(file_path),
                "fetched": fetched,
                **({"derived": True} if tab.get("derived") else {}),
            }
        )

    index_path = campaign_dir / "index.json"
    # tabCount keeps its retained meaning — links the page itself listed — so
    # tabCount < len(tabSamples) is exactly the participant-type gap the
    # derivation closed.
    index_payload = {
        "campaignKey": campaign_key,
        "campaignLabel": campaign_link.get("label", ""),
        "campaignUrl": campaign_url,
        "tabCount": len(extracted_links),
        "tabSamples": saved_tabs,
        "campaignRootPath": str(campaign_dir / "root.html") if not extracted_links else "",
        **({"derivedTabsAbsent": absent_tab_slugs} if absent_tab_slugs else {}),
    }
    write_json(index_path, index_payload)

    return {
        "campaignKey": campaign_key,
        "campaignLabel": campaign_link.get("label", ""),
        "campaignUrl": campaign_url,
        "campaignDir": str(campaign_dir),
        "tabCount": len(extracted_links),
        "tabSamples": saved_tabs,
        "indexPath": str(index_path),
    }


def _fetch_candidate_tabs(
    entry: dict[str, str],
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
    missing_expected_tabs = sorted(EXPECTED_TABS - found_tab_slugs)
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
                detail={
                    "tabCount": len(tab_links),
                    "tabsSaved": len(saved_tabs),
                },
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
    missing_ids = [candidate_id for candidate_id in candidate_ids if candidate_id not in entries_by_id]
    if missing_ids:
        raise ValueError(
            "Candidate IDs not found in sitemap: " + ", ".join(sorted(set(missing_ids)))
        )

    results: list[dict[str, Any]] = []
    for candidate_id in candidate_ids:
        entry = entries_by_id[candidate_id]
        results.append(
            _fetch_candidate_tabs(
                entry=entry,
                samples_root=samples_root,
                allow_new_candidate_dir=allow_new_candidate_dir,
            )
        )

    return {
        "election_id": ELECTION_ID,
        "count": len(results),
        "results": results,
    }
