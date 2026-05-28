import argparse
from pathlib import Path
from typing import Any

from scraper.elections.seimo_2016.anketa_parser import parse_anketa_samples
from scraper.elections.seimo_2016.candidate_samples import (
    fetch_candidates_with_tabs,
    fetch_first_candidate_with_tabs,
)
from scraper.elections.seimo_2016.sitemap import (
    ELECTION_ID,
    build_sitemap_from_sample,
    fetch_listing_sample,
)
from scraper.shared.anomalies import write_jsonl


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="VRK election scraper")
    subparsers = parser.add_subparsers(dest="command", required=True)

    fetch_parser = subparsers.add_parser(
        "fetch-sample",
        help="Download and save raw HTML sample for an election",
    )
    fetch_parser.add_argument("election_id", choices=[ELECTION_ID])

    sitemap_parser = subparsers.add_parser(
        "sitemap",
        help="Build sitemap JSON from a saved HTML sample",
    )
    sitemap_parser.add_argument("election_id", choices=[ELECTION_ID])
    sitemap_parser.add_argument(
        "--sample",
        type=Path,
        default=None,
        help="Path to HTML sample file. Defaults to samples/html/2016-seimo/list.html",
    )

    candidate_sample_parser = subparsers.add_parser(
        "fetch-first-candidate-samples",
        help="Download first sitemap candidate page and tab subpages as HTML samples",
    )
    candidate_sample_parser.add_argument("election_id", choices=[ELECTION_ID])
    candidate_sample_parser.add_argument(
        "--sitemap",
        type=Path,
        default=Path("sitemaps/2016-seimo.json"),
        help="Path to sitemap JSON. Defaults to sitemaps/2016-seimo.json",
    )
    candidate_sample_parser.add_argument(
        "--samples-root",
        type=Path,
        default=Path("samples/html/2016-seimo"),
        help="Path to candidate sample folders. Defaults to samples/html/2016-seimo",
    )
    candidate_sample_parser.add_argument(
        "--allow-new-samples",
        action="store_true",
        help=(
            "Allow creating new candidate directories under samples root. "
            "Disabled by default so sample fixtures stay fixed."
        ),
    )

    targeted_sample_parser = subparsers.add_parser(
        "fetch-candidate-samples",
        help="Download selected candidate page and tab subpages as HTML samples",
    )
    targeted_sample_parser.add_argument("election_id", choices=[ELECTION_ID])
    targeted_sample_parser.add_argument(
        "--candidate-id",
        action="append",
        required=True,
        help="Candidate ID from sitemap. Can be passed multiple times.",
    )
    targeted_sample_parser.add_argument(
        "--sitemap",
        type=Path,
        default=Path("sitemaps/2016-seimo.json"),
        help="Path to sitemap JSON. Defaults to sitemaps/2016-seimo.json",
    )
    targeted_sample_parser.add_argument(
        "--samples-root",
        type=Path,
        default=Path("samples/html/2016-seimo"),
        help="Path to candidate sample folders. Defaults to samples/html/2016-seimo",
    )
    targeted_sample_parser.add_argument(
        "--allow-new-samples",
        action="store_true",
        help=(
            "Allow creating new candidate directories under samples root. "
            "Disabled by default so sample fixtures stay fixed."
        ),
    )

    parse_anketa_parser = subparsers.add_parser(
        "parse-anketa-samples",
        help="Parse saved anketa HTML samples into initial structured JSON output",
    )
    parse_anketa_parser.add_argument("election_id", choices=[ELECTION_ID])
    parse_anketa_parser.add_argument(
        "--candidate-id",
        action="append",
        default=None,
        help="Candidate ID to parse. Can be passed multiple times. If omitted, parse all sampled candidates.",
    )
    parse_anketa_parser.add_argument(
        "--samples-root",
        type=Path,
        default=Path("samples/html/2016-seimo"),
        help="Path to candidate sample folders. Defaults to samples/html/2016-seimo",
    )
    parse_anketa_parser.add_argument(
        "--output-root",
        type=Path,
        default=Path("data/2016-seimo"),
        help="Path to output JSON folder. Defaults to data/2016-seimo",
    )
    parse_anketa_parser.add_argument(
        "--anomalies-path",
        type=Path,
        default=None,
        help="Path to write anomalies JSONL. Defaults to <output-root>/anomalies.jsonl",
    )

    return parser


def _summarize_anomalies(anomalies: list[dict[str, Any]]) -> tuple[dict[str, int], dict[str, int]]:
    by_type: dict[str, int] = {}
    by_severity: dict[str, int] = {}
    for event in anomalies:
        event_type = str(event.get("eventType", "unknown"))
        severity = str(event.get("severity", "unknown"))
        by_type[event_type] = by_type.get(event_type, 0) + 1
        by_severity[severity] = by_severity.get(severity, 0) + 1
    return by_type, by_severity


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    if args.command == "fetch-sample":
        sample_path = fetch_listing_sample()
        print(f"Saved HTML sample: {sample_path}")
        return 0

    if args.command == "sitemap":
        output_path, stats = build_sitemap_from_sample(sample_path=args.sample)
        print(f"Saved sitemap: {output_path}")
        print(
            "Rows: {rows}, extracted: {extracted}, skipped: {skipped}, duplicateIds: {dups}".format(
                rows=stats["rows"],
                extracted=stats["extracted"],
                skipped=stats["skipped"],
                dups=stats["duplicate_candidate_ids"],
            )
        )
        return 0

    if args.command == "fetch-first-candidate-samples":
        result = fetch_first_candidate_with_tabs(
            sitemap_path=args.sitemap,
            samples_root=args.samples_root,
            allow_new_candidate_dir=args.allow_new_samples,
        )
        candidate = result["candidate"]
        print(f"Candidate: {candidate['candidateName']} ({candidate['candidateId']})")
        print(f"Anketa sample: {result['anketa_path']}")
        print(
            "Tab samples saved: {saved} (tab links found: {found})".format(
                saved=result["tabs_saved"],
                found=result["tab_count"],
            )
        )
        missing = result["missing_expected_tabs"]
        if missing:
            print("Missing expected tabs: " + ", ".join(missing))
        else:
            print("All expected candidate tabs found")
        print(f"Index: {result['index_path']}")
        return 0

    if args.command == "fetch-candidate-samples":
        payload = fetch_candidates_with_tabs(
            candidate_ids=args.candidate_id,
            sitemap_path=args.sitemap,
            samples_root=args.samples_root,
            allow_new_candidate_dir=args.allow_new_samples,
        )
        print(f"Fetched candidates: {payload['count']}")
        for result in payload["results"]:
            candidate = result["candidate"]
            print(f"- {candidate['candidateName']} ({candidate['candidateId']})")
            print(
                "  Tab samples saved: {saved} (tab links found: {found})".format(
                    saved=result["tabs_saved"],
                    found=result["tab_count"],
                )
            )
            missing = result["missing_expected_tabs"]
            if missing:
                print("  Missing expected tabs: " + ", ".join(missing))
            else:
                print("  All expected candidate tabs found")
            anomalies = result.get("anomalies", [])
            if anomalies:
                print(f"  Anomalies: {len(anomalies)}")
            print(f"  Index: {result['index_path']}")
        return 0

    if args.command == "parse-anketa-samples":
        results = parse_anketa_samples(
            candidate_ids=args.candidate_id,
            samples_root=args.samples_root,
            output_root=args.output_root,
        )
        all_anomalies: list[dict[str, Any]] = []
        print(f"Parsed candidates: {len(results)}")
        for result in results:
            print(
                "- {name} ({cid}) -> {path}".format(
                    name=result["candidateName"] or "Unknown",
                    cid=result["candidateId"],
                    path=result["outputPath"],
                )
            )
            print(
                "  rows={rows}, answered={answered}".format(
                    rows=result["rowCount"],
                    answered=result["answeredRowCount"],
                )
            )
            anomalies = result.get("anomalies", [])
            all_anomalies.extend(anomalies)
            if anomalies:
                print(f"  anomalies={len(anomalies)}")

        anomalies_path = args.anomalies_path or (args.output_root / "anomalies.jsonl")
        write_jsonl(anomalies_path, all_anomalies)
        by_type, by_severity = _summarize_anomalies(all_anomalies)
        print(f"Anomalies saved: {anomalies_path}")
        print(f"Total anomalies: {len(all_anomalies)}")
        if by_severity:
            print(
                "By severity: "
                + ", ".join(
                    f"{name}={count}" for name, count in sorted(by_severity.items(), key=lambda item: item[0])
                )
            )
        if by_type:
            top_types = sorted(by_type.items(), key=lambda item: (-item[1], item[0]))[:10]
            print(
                "Top anomaly types: "
                + ", ".join(f"{name}={count}" for name, count in top_types)
            )
        return 0

    parser.error("Unknown command")
    return 1
