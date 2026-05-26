import argparse
from pathlib import Path

from scraper.elections.seimo_2016.sitemap import (
    ELECTION_ID,
    build_sitemap_from_sample,
    fetch_listing_sample,
)


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

    return parser


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

    parser.error("Unknown command")
    return 1
