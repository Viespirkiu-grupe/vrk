from __future__ import annotations

import json
from pathlib import Path
import re
import shutil
from typing import Any

from bs4 import BeautifulSoup

from scraper.elections.seimo_zirmunu_2015.sitemap import ELECTION_ID, resolve_candidate_url
from scraper.shared.anomalies import build_anomaly_event
from scraper.shared.campaign_tabs import (
    derive_subtab_links,
    is_absent_derived_tab,
    merge_campaign_tab_links,
)
from scraper.shared.files import slugify
from scraper.shared.http import fetch_text

DEFAULT_SITEMAP_PATH = Path("sitemaps/2015-kovo-1-seimo-zirmunai.json")
DEFAULT_SAMPLES_ROOT = Path("samples/html/2015-kovo-1-seimo-zirmunai")

# The 2015-era candidate "tabs" are separate static files per candidate, and
# their links are bare <li> siblings in the page body — there is no ul#tabnav
# on candidate pages (district pages have one, candidate pages do not), so the
# links are recognized by their file stems instead of a nav container.
# Patiketiniai is the presidential elections' sixth tab (the candidate's
# trustees); the 2014 presidential module is its only user, and the stem is
# simply absent from every other election's pages.
CANDIDATE_TAB_LINK_PATTERN = re.compile(
    r"Kandidato\d+(?:Anketa|Biografija|Deklaracijos|InteresuDeklaracija|Patiketiniai|Kita)\.html$"
)

EXPECTED_TABS = {
    "anketa",
    "biografija",
    "turto-ir-pajamu-deklaracijos",
    "interesu-deklaracija",
    "kita",
}

# The campaign participant link sits in the profile card, not among the tabs:
# "Savarankiško/Atstovaujamojo politinės kampanijos dalyvio duomenys" pointing
# into PolitiniuKampanijuFinansavimas/Dalyvis<ID>/. The participant pages share
# the "Dalyvio<ID><Tab>.html" stem; the campaign root's tabnav also links the
# district-wide participants index, which is not participant data and is
# excluded by requiring that stem.
CAMPAIGN_LINK_PATTERN = re.compile(r"/Dalyvis(\d+)/Dalyvio\1[A-Za-z]+\.html$")
CAMPAIGN_TAB_LINK_PATTERN = re.compile(r"Dalyvio\d+[A-Za-z]+\.html$")

# A represented participant's page is a card without sub-tabs: the campaign
# belongs to the nominating party, whose own participant page the card links.
# That shape is data, not an extraction failure.
REPRESENTED_PARTICIPANT_MARKER = "Atstovaujamasis politinės kampanijos dalyvis"


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
        candidate_id = str(raw_entry.get("candidateId", "")).strip()
        url = str(raw_entry.get("url", "")).strip()
        if not candidate_id or not url:
            continue
        # Everything the sitemap recorded is carried through: the listing-only
        # facts (municipality, list, seat order, roles, VRK's own candidate id)
        # exist nowhere on the candidate page, and both the fetch stage (which
        # tabs to expect) and the parse stage (the kandidatavimas block) need
        # them.
        entry = dict(raw_entry)
        entry["candidateId"] = candidate_id
        entry["candidateName"] = str(raw_entry.get("candidateName", "")).strip()
        entry["url"] = url
        normalized_entries.append(entry)

    if not normalized_entries:
        raise ValueError(f"No usable sitemap entries found in {sitemap_path}")
    return normalized_entries


def _load_first_sitemap_entry(sitemap_path: Path) -> dict[str, str]:
    return _load_sitemap_entries(sitemap_path)[0]


def _load_sitemap_entries_by_candidate_id(sitemap_path: Path) -> dict[str, dict[str, str]]:
    return {entry["candidateId"]: entry for entry in _load_sitemap_entries(sitemap_path)}


def _extract_tab_links(candidate_html: str) -> list[dict[str, str]]:
    soup = BeautifulSoup(candidate_html, "lxml")
    links: list[dict[str, str]] = []

    for anchor in soup.select("li a[href]"):
        href = normalize_space(anchor.get("href", ""))
        if not href or not CANDIDATE_TAB_LINK_PATTERN.search(href):
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


def _extract_campaign_link(candidate_html: str) -> dict[str, str] | None:
    soup = BeautifulSoup(candidate_html, "lxml")
    for anchor in soup.find_all("a", href=True):
        href = normalize_space(anchor["href"])
        match = CAMPAIGN_LINK_PATTERN.search(href)
        if not match:
            continue
        return {
            "label": normalize_space(anchor.get_text(" ", strip=True)),
            "url": resolve_candidate_url(href),
            "campaignKey": f"dalyvis-{match.group(1)}",
        }
    return None


def _extract_campaign_tab_links(campaign_html: str) -> list[dict[str, str]]:
    soup = BeautifulSoup(campaign_html, "lxml")
    links: list[dict[str, str]] = []

    for anchor in soup.select("ul#tabnav a[href]"):
        href = normalize_space(anchor.get("href", ""))
        if not href or not CAMPAIGN_TAB_LINK_PATTERN.search(href):
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


def _fetch_campaign_tabs(
    candidate_dir: Path,
    campaign_link: dict[str, str],
    anomalies: list[dict[str, Any]],
    candidate_id: str,
    candidate_url: str,
    election_id: str,
) -> dict[str, Any]:
    campaign_url = campaign_link["url"]
    campaign_key = campaign_link["campaignKey"]

    campaign_dir = candidate_dir / "campaigns" / campaign_key
    campaign_dir.mkdir(parents=True, exist_ok=True)

    try:
        root_html = fetch_text(campaign_url)
    except Exception as exc:
        anomalies.append(
            build_anomaly_event(
                event_type="CampaignRootFetchFailed",
                severity="error",
                stage="fetch",
                election_id=election_id,
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

    extracted_links = _extract_campaign_tab_links(root_html)
    if not extracted_links and REPRESENTED_PARTICIPANT_MARKER not in root_html:
        anomalies.append(
            build_anomaly_event(
                event_type="CampaignTabLinkExtractionEmpty",
                severity="warning",
                stage="fetch",
                election_id=election_id,
                candidate_id=candidate_id,
                source_url=candidate_url,
                detail={
                    "campaignUrl": campaign_url,
                    "campaignKey": campaign_key,
                },
            )
        )

    # An atstovaujamasis participant's root renders no tab list at all in this
    # family, while its five Dalyvio<id>* sub-pages exist (measured 2026-08-31)
    # — so the sub-tab URLs are derived from the participant id and the
    # rendered list only supplies labels (issue #99). A derived URL answering
    # 404 is VRK not publishing that sub-page, recorded rather than treated as
    # a download failure.
    tab_links = merge_campaign_tab_links(extracted_links, derive_subtab_links(campaign_url))

    seen_file_slugs: dict[str, int] = {}
    saved_tabs: list[dict[str, Any]] = []
    absent_tab_slugs: list[str] = []

    for tab in tab_links:
        file_slug = _dedupe_filename_slug(tab["slug"], seen_file_slugs)
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
                        election_id=election_id,
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

    if not extracted_links:
        root_path = campaign_dir / "root.html"
        root_path.write_text(root_html, encoding="utf-8")

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
    index_path.write_text(
        json.dumps(index_payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

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
    election_id: str,
    expected_tabs: set[str] | Any,
    unpublished_tabs: set[str] | None = None,
    tab_links_extractor: Any = None,
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

    # The 2004 EP pages (VRK's original static site) link their sub-pages
    # from the profile card under other file stems; that module supplies
    # its own extractor, with the same (label, slug, url) result.
    if tab_links_extractor is None:
        tab_links = _extract_tab_links(anketa_html)
    else:
        tab_links = tab_links_extractor(anketa_html, entry["url"])
    # Tabs the election's pages link but VRK never published (every such
    # URL is a 404 for every candidate): recorded as a fact of the source,
    # not fetched, and not counted against the expected set — see the
    # module that names them for the probe that established it.
    unpublished_links = [
        tab for tab in tab_links if unpublished_tabs and tab["slug"] in unpublished_tabs
    ]
    if unpublished_links:
        tab_links = [tab for tab in tab_links if tab not in unpublished_links]
    anomalies: list[dict[str, Any]] = []
    if not tab_links:
        anomalies.append(
            build_anomaly_event(
                event_type="TabLinkExtractionEmpty",
                severity="error",
                stage="fetch",
                election_id=election_id,
                candidate_id=entry["candidateId"],
                source_url=entry["url"],
            )
        )

    found_tab_slugs = {tab["slug"] for tab in tab_links if tab["slug"]}
    required_tabs = expected_tabs(entry) if callable(expected_tabs) else expected_tabs
    missing_expected_tabs = sorted(required_tabs - found_tab_slugs - set(unpublished_tabs or ()))
    if missing_expected_tabs:
        anomalies.append(
            build_anomaly_event(
                event_type="MissingExpectedTab",
                severity="warning",
                stage="fetch",
                election_id=election_id,
                candidate_id=entry["candidateId"],
                source_url=entry["url"],
                detail={"missingTabs": missing_expected_tabs},
            )
        )

    seen_file_slugs: dict[str, int] = {}
    saved_tabs: list[dict[str, Any]] = []

    for tab in tab_links:
        file_slug = _dedupe_filename_slug(tab["slug"], seen_file_slugs)
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
                        election_id=election_id,
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
    campaign_link = _extract_campaign_link(anketa_html)
    if campaign_link is not None:
        campaigns_root = candidate_dir / "campaigns"
        if campaigns_root.exists():
            shutil.rmtree(campaigns_root)

        campaign_samples.append(
            _fetch_campaign_tabs(
                candidate_dir,
                campaign_link,
                anomalies,
                candidate_id=entry["candidateId"],
                candidate_url=entry["url"],
                election_id=election_id,
            )
        )

    if len(saved_tabs) < len(tab_links):
        anomalies.append(
            build_anomaly_event(
                event_type="TabDownloadPartial",
                severity="error",
                stage="fetch",
                election_id=election_id,
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
        "electionId": election_id,
        "candidate": entry,
        "anketaPath": str(anketa_path),
        "tabCount": len(tab_links),
        "tabSamples": saved_tabs,
        "missingExpectedTabs": missing_expected_tabs,
        "unpublishedTabs": unpublished_links,
        "campaignSamples": campaign_samples,
        "anomalies": anomalies,
    }
    index_path.write_text(
        json.dumps(index_payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    return {
        "election_id": election_id,
        "candidate": entry,
        "candidate_dir": candidate_dir,
        "anketa_path": anketa_path,
        "tab_count": len(tab_links),
        "tabs_saved": len(saved_tabs),
        "missing_expected_tabs": missing_expected_tabs,
        "unpublished_tabs": unpublished_links,
        "campaign_samples": campaign_samples,
        "anomalies": anomalies,
        "index_path": index_path,
    }


def fetch_first_candidate_with_tabs(
    sitemap_path: Path = DEFAULT_SITEMAP_PATH,
    samples_root: Path = DEFAULT_SAMPLES_ROOT,
    allow_new_candidate_dir: bool = False,
    election_id: str = ELECTION_ID,
    expected_tabs: set[str] | Any | None = None,
    unpublished_tabs: set[str] | None = None,
    tab_links_extractor: Any = None,
) -> dict[str, Any]:
    entry = _load_first_sitemap_entry(sitemap_path)
    return _fetch_candidate_tabs(
        entry=entry,
        samples_root=samples_root,
        allow_new_candidate_dir=allow_new_candidate_dir,
        election_id=election_id,
        expected_tabs=expected_tabs if expected_tabs is not None else EXPECTED_TABS,
        unpublished_tabs=unpublished_tabs,
        tab_links_extractor=tab_links_extractor,
    )


def fetch_candidates_with_tabs(
    candidate_ids: list[str],
    sitemap_path: Path = DEFAULT_SITEMAP_PATH,
    samples_root: Path = DEFAULT_SAMPLES_ROOT,
    allow_new_candidate_dir: bool = False,
    election_id: str = ELECTION_ID,
    expected_tabs: set[str] | Any | None = None,
    unpublished_tabs: set[str] | None = None,
    tab_links_extractor: Any = None,
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
                election_id=election_id,
                expected_tabs=expected_tabs if expected_tabs is not None else EXPECTED_TABS,
                unpublished_tabs=unpublished_tabs,
                tab_links_extractor=tab_links_extractor,
            )
        )

    return {
        "election_id": election_id,
        "count": len(results),
        "results": results,
    }
