"""Fetch the campaign sub-tabs the walkers never followed (issue #99).

The campaign walkers trusted the tab list the campaign root rendered, and
that list depends on the participant type: an *atstovaujamasis* (represented)
participant's root shows one of the five finance sub-tabs (2023-2024), or
none (2012-2020) — so 2,189 represented campaigns hold donations but no
funding reports, treasurer, auditor or contracts. The walkers now derive the
five sub-tab URLs from the participant id (`scraper/shared/campaign_tabs.py`);
this script replays that derivation over the campaigns already retained under
``samples-full/``, fetches what is missing, and updates both places the parse
stage reads: the candidate's ``index.json`` (its ``campaignSamples`` is what
the parsers iterate) and the campaign directory's own ``index.json``.

What a fresh walk would do, this does from the retained bytes where possible:
a sub-tab whose URL *is* the campaign root (the older family's Iždininkas)
is written from the retained ``root.html`` without a network request.

Not every tree publishes the sub-pages: the 2016, 2020 and 2019-03 trees
answer 404 for every derived atstovaujamasis sub-tab (spot-checked
2026-08-31). A 404 on a derived URL is recorded as ``derivedTabsAbsent`` in
the campaign's index — a known absence, not a failure — and once the first
``--probe`` campaigns of an election come back all-404, the election is
declared unpublished and its remaining campaigns are left untouched rather
than hammering VRK with thousands of guaranteed 404s. The report then says
how many campaigns that verdict covers.

    python scripts/refetch_campaign_subtabs.py                    # all elections
    python scripts/refetch_campaign_subtabs.py 2024-seimo         # one election
    python scripts/refetch_campaign_subtabs.py --dry-run          # count only

After a run, re-parse the affected elections so the records gain the data:
``python scripts/reparse_diff.py --full --jobs 8 --apply <election-id> …``
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any

import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scraper.shared.campaign_tabs import derive_subtab_links  # noqa: E402
from scraper.shared.files import write_json  # noqa: E402
from scraper.shared.http import fetch_text  # noqa: E402

DEFAULT_PAUSE_SECONDS = 0.25
DEFAULT_PROBE_CAMPAIGNS = 8


class ElectionStats:
    def __init__(self) -> None:
        self.campaigns = 0
        self.complete = 0
        self.updated = 0
        self.fetched = 0
        self.reused = 0
        self.absent = 0
        # Campaigns holding `root.html` and nothing else, with no
        # `derivedTabsAbsent` marker: the 2026-09-01 run decided those tabs
        # were unpublished and recorded the verdict in DATASET.md's prose
        # rather than in the campaigns' own index.json, so this cannot tell
        # them from a campaign nobody has tried (issue #159). Counted apart
        # from `updated` so a dry run says which population it is looking at.
        self.root_only_unmarked = 0
        self.skipped_after_probe = 0
        self.errors: list[str] = []
        # The probe verdict: campaigns whose every attempted derived fetch
        # came back 404, before anything resolved.
        self.probed_all_absent = 0
        self.any_published = False


def _is_404(exc: Exception) -> bool:
    response = getattr(exc, "response", None)
    return (
        isinstance(exc, requests.HTTPError)
        and response is not None
        and response.status_code == 404
    )


def known_absent_slugs(campaign_dir: Path) -> set[str]:
    """The sub-tabs this campaign's own index.json records as unpublished.

    Written by a previous run of this script (a 404 on a derived URL is the
    source saying the tab does not exist), and read here so the same URL is
    not requested again.
    """
    index_path = campaign_dir / "index.json"
    if not index_path.is_file():
        return set()
    try:
        payload = json.loads(index_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return set()
    absent = payload.get("derivedTabsAbsent")
    return {str(slug) for slug in absent} if isinstance(absent, list) else set()


def refetch_campaign(
    campaign: dict[str, Any],
    candidate_dir: Path,
    stats: ElectionStats,
    pause: float,
    dry_run: bool,
) -> bool:
    """Fetch one campaign's missing sub-tabs; returns True when the
    candidate-level entry was changed."""
    campaign_url = str(campaign.get("campaignUrl", ""))
    campaign_key = str(campaign.get("campaignKey", ""))
    derived = derive_subtab_links(campaign_url)
    if not derived or not campaign_key:
        return False

    campaign_dir = (candidate_dir / "campaigns" / campaign_key).resolve()
    if not campaign_dir.is_dir():
        return False

    stats.campaigns += 1
    tab_samples = campaign.get("tabSamples")
    if not isinstance(tab_samples, list):
        tab_samples = []
        campaign["tabSamples"] = tab_samples
    existing_slugs = {tab.get("slug") for tab in tab_samples if isinstance(tab, dict)}
    existing_urls = {tab.get("url") for tab in tab_samples if isinstance(tab, dict)}
    # A tab VRK does not publish is recorded as `derivedTabsAbsent` in the
    # campaign's own index.json, and this used to compute its work from
    # `tabSamples` alone and never read that back: `--dry-run` reported 1,218
    # campaigns and 6,089 sub-pages pending across six elections — precisely
    # the ones DATASET.md records as settled by the source's own absence —
    # and a real run re-requested about 40 known-404 URLs per election
    # (issue #159). The marker is part of the work set now.
    absent_marker = known_absent_slugs(campaign_dir)
    existing_slugs |= absent_marker
    missing = [
        tab
        for tab in derived
        if tab["slug"] not in existing_slugs and tab["url"] not in existing_urls
    ]
    if not missing:
        stats.complete += 1
        return False
    if dry_run:
        root_only = not absent_marker and not any(
            path.name != "root.html" for path in campaign_dir.glob("*.html")
        )
        if root_only:
            stats.root_only_unmarked += 1
        else:
            stats.updated += 1
            stats.fetched += sum(1 for tab in missing if tab["url"] != campaign_url)
            stats.reused += sum(1 for tab in missing if tab["url"] == campaign_url)
        return False

    new_entries: list[dict[str, Any]] = []
    absent_slugs: list[str] = []
    attempted = resolved = 0
    for tab in missing:
        file_path = campaign_dir / f"{tab['slug']}.html"
        if tab["url"] == campaign_url and (campaign_dir / "root.html").is_file():
            file_path.write_bytes((campaign_dir / "root.html").read_bytes())
            fetched = False
            stats.reused += 1
        else:
            attempted += 1
            try:
                html = fetch_text(tab["url"])
            except Exception as exc:  # noqa: BLE001 - each tab fails alone
                if _is_404(exc):
                    absent_slugs.append(tab["slug"])
                    stats.absent += 1
                else:
                    stats.errors.append(f"{campaign_key}/{tab['slug']}: {exc}")
                time.sleep(pause)
                continue
            time.sleep(pause)
            file_path.write_text(html, encoding="utf-8")
            fetched = True
            resolved += 1
            stats.fetched += 1
        new_entries.append(
            {
                "label": tab["label"],
                "slug": tab["slug"],
                "url": tab["url"],
                "path": str(file_path),
                "fetched": fetched,
                "derived": True,
            }
        )

    if attempted and resolved == 0 and not new_entries:
        stats.probed_all_absent += 1
    if resolved:
        stats.any_published = True

    changed = bool(new_entries)
    if changed:
        tab_samples.extend(new_entries)
        stats.updated += 1

    # The campaign directory's own index mirrors the candidate-level entry
    # and additionally records the measured absences.
    index_path = campaign_dir / "index.json"
    campaign_index: dict[str, Any] = {}
    if index_path.is_file():
        try:
            campaign_index = json.loads(index_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            campaign_index = {}
    if changed or absent_slugs:
        index_tabs = campaign_index.get("tabSamples")
        if not isinstance(index_tabs, list):
            index_tabs = []
        index_slugs = {tab.get("slug") for tab in index_tabs if isinstance(tab, dict)}
        index_tabs.extend(tab for tab in new_entries if tab["slug"] not in index_slugs)
        campaign_index["tabSamples"] = index_tabs
        if absent_slugs:
            known_absent = campaign_index.get("derivedTabsAbsent")
            known_absent = known_absent if isinstance(known_absent, list) else []
            campaign_index["derivedTabsAbsent"] = sorted(set(known_absent) | set(absent_slugs))
        write_json(index_path, campaign_index)
    return changed


def refetch_election(
    election_dir: Path,
    pause: float,
    probe_limit: int,
    dry_run: bool,
) -> ElectionStats:
    stats = ElectionStats()
    for candidate_dir in sorted(p for p in election_dir.iterdir() if p.is_dir()):
        if not (candidate_dir / "campaigns").is_dir():
            continue
        index_path = candidate_dir / "index.json"
        if not index_path.is_file():
            continue
        # The unpublished-tree verdict: the first `probe_limit` incomplete
        # campaigns all answered 404 on every derived URL, so the rest of the
        # election would too. Their indexes are left untouched.
        if (
            not dry_run
            and not stats.any_published
            and stats.probed_all_absent >= probe_limit
        ):
            stats.skipped_after_probe += 1
            continue
        meta = json.loads(index_path.read_text(encoding="utf-8"))
        campaigns = meta.get("campaignSamples")
        if not isinstance(campaigns, list):
            continue
        changed = False
        for campaign in campaigns:
            if isinstance(campaign, dict):
                changed |= refetch_campaign(campaign, candidate_dir, stats, pause, dry_run)
        if changed:
            write_json(index_path, meta)
    return stats


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "election_id", nargs="*", help="Elections to refetch. Defaults to every samples-full tree."
    )
    parser.add_argument("--dry-run", action="store_true", help="Count what would be fetched.")
    parser.add_argument(
        "--pause", type=float, default=DEFAULT_PAUSE_SECONDS, help="Seconds between requests."
    )
    parser.add_argument(
        "--probe",
        type=int,
        default=DEFAULT_PROBE_CAMPAIGNS,
        help=(
            "Incomplete campaigns to try before declaring an election's sub-pages "
            "unpublished when every derived URL has answered 404."
        ),
    )
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=Path("."),
        help="Checkout holding samples-full/. Defaults to the cwd.",
    )
    args = parser.parse_args()

    samples_root = args.repo_root / "samples-full"
    if not samples_root.is_dir():
        print(f"No {samples_root}/ here — run from the repo root.", file=sys.stderr)
        return 2

    election_ids = args.election_id or sorted(
        child.name for child in samples_root.iterdir() if child.is_dir()
    )

    exit_code = 0
    for election_id in election_ids:
        election_dir = samples_root / election_id
        if not election_dir.is_dir():
            print(f"{election_id}: no samples-full/ tree, skipped", file=sys.stderr)
            exit_code = 2
            continue
        stats = refetch_election(election_dir, args.pause, args.probe, args.dry_run)
        if not stats.campaigns and not stats.skipped_after_probe:
            continue
        note = (
            f"{election_id}: {stats.campaigns} campaign(s), {stats.complete} complete, "
            f"{stats.updated} updated ({stats.fetched} fetched, {stats.reused} from root.html)"
        )
        if stats.absent:
            note += f", {stats.absent} sub-page(s) unpublished"
        if stats.root_only_unmarked:
            note += (
                f"; {stats.root_only_unmarked} campaign(s) hold root.html alone with no"
                " `derivedTabsAbsent` marker — a run would attempt those URLs once"
                " and then record the verdict"
            )
        if stats.skipped_after_probe:
            note += (
                f"; declared unpublished after {stats.probed_all_absent} all-404 probe(s), "
                f"{stats.skipped_after_probe} candidate(s) left untouched"
            )
        if args.dry_run:
            note += " [dry run]"
        print(note)
        for error in stats.errors:
            print(f"    ERROR {error}", file=sys.stderr)
            exit_code = 1
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
