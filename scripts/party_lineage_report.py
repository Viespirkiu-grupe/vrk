"""Flag nominator pairs whose candidates carried over, and check the registry explains each.

Issue #123: scraper/parties.json holds one entry per organisation, and an
organisation another one continues -- by a merger under a new name, a change
of legal form (komitetas -> partija), a takeover of its registration, or a
re-brand -- is listed under the successor's `predecessors`. Names alone cannot
find those pairs: the 2019 „Su Sinkevičiumi ir Osausku“ and the 2023 „Mūsų
Jonava“ share no word, and 16 of 28 candidates. Candidates can. This script
reads the person index the dashboard is built from (dashboard/people.json --
pids, candidacies, nominator ids) and lists every ordered pair A -> B of
nominators where A's last election precedes B's first and at least a third
of the smaller side's persons, three or more, stood for both. Each pair is
one of:

* linked     -- A is among B's predecessors, directly or through the chain;
* reviewed   -- the registry's `reviewedDistinct` block names the pair and
                says why two organisations share candidates without one
                continuing the other (a coalition whose core party outlived
                it; a split);
* succeeded  -- the earlier one already has a successor in the registry;
* unreviewed -- a finding: link the pair in the registry, or record it as
                reviewed with the reason.

Two pairs are not findings. A local list -- one that only ever stood in
municipal elections -- is never proposed as the predecessor of a national
party or coalition: a committee's people joining a new Seimas party is a
career move, not a continuation, and every such pair would otherwise
resurface at each election. And an organisation the registry already
continues elsewhere (`succeeded`: the Naujoji sąjunga branch that formed a
committee after the party merged into Darbo partija) has its successor;
the forest allows one. The threshold and the floor are the ones the
2026-09-02 audit was decided on; a pair below them is not a finding, only
evidence for a reviewer who is already looking.

Run from the repo root after `python scripts/build_person_index.py`:

    python scripts/party_lineage_report.py            # findings, exit 1 on any
    python scripts/party_lineage_report.py --all      # every pair, linked ones too
    python scripts/party_lineage_report.py --index other/people.json

Writes the full pair table to data/party-lineage-report.tsv either way.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scraper.shared.parties import ancestors, entries, load_registry  # noqa: E402

INDEX = Path("dashboard/people.json")
REPORT = Path("data/party-lineage-report.tsv")

#: The share of the smaller side's persons that must stand for both, and the
#: least number of them, for a pair to count as continuity.
THRESHOLD = 1 / 3
MINIMUM = 3
#: The election kinds a national organisation stands in; a nominator seen
#: only in the others is a local list.
NATIONAL_KINDS = {"seimo", "ep", "prezidento"}

COLUMNS = ("from", "to", "from_years", "to_years", "shared", "share", "status", "why")


def fold_municipality(name: str) -> str:
    """The 2011-2015 index spells `X savivaldybė`, the 2019-2023 one `X`."""
    return name.replace(" savivaldybė", "").strip()


def measure(index: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Per nominator id: its persons, municipalities, election span and scope."""
    dates = {e["id"]: e["date"] for e in index["elections"]}
    kinds = {e["id"]: e.get("kind") for e in index["elections"]}
    municipalities = index.get("municipalities", [])
    stats: dict[str, dict[str, Any]] = {}
    for person in index["people"]:
        for candidacy in person["e"]:
            party_id = candidacy.get("p")
            if not party_id:
                continue
            stat = stats.setdefault(
                party_id,
                {"persons": set(), "municipalities": set(), "first": "9999", "last": "0000", "n": 0, "national": False},
            )
            stat["persons"].add(person["pid"])
            if "sv" in candidacy:
                stat["municipalities"].add(fold_municipality(municipalities[candidacy["sv"]]))
            date = dates.get(candidacy["id"], "")
            stat["first"] = min(stat["first"], date)
            stat["last"] = max(stat["last"], date)
            stat["n"] += 1
            stat["national"] = stat["national"] or kinds.get(candidacy["id"]) in NATIONAL_KINDS
    return stats


def continuity_pairs(stats: dict[str, dict[str, Any]]) -> list[tuple[str, str, int, float]]:
    """Ordered pairs (earlier, later, shared persons, share of the smaller side)."""
    pairs = []
    ids = sorted(stats)
    for a in ids:
        for b in ids:
            if a == b:
                continue
            sa, sb = stats[a], stats[b]
            if not sa["last"] < sb["first"]:
                continue
            if sb["national"] and not sa["national"]:
                continue
            shared = len(sa["persons"] & sb["persons"])
            smaller = min(len(sa["persons"]), len(sb["persons"]))
            if shared < MINIMUM or shared < THRESHOLD * smaller:
                continue
            pairs.append((a, b, shared, shared / smaller))
    return pairs


def reviewed_distinct() -> dict[tuple[str, str], str]:
    return {(row["a"], row["b"]): row["why"] for row in load_registry().get("reviewedDistinct", [])}


def successors() -> dict[str, str]:
    """Who continues whom, inverted from the registry's `predecessors`."""
    return {pred: party_id for party_id, data in entries().items() for pred in data.get("predecessors", [])}


def classify(pair: tuple[str, str, int, float], reviewed: dict[tuple[str, str], str]) -> tuple[str, str]:
    a, b, _, _ = pair
    if a in ancestors(b):
        return "linked", ""
    if (a, b) in reviewed:
        return "reviewed", reviewed[(a, b)]
    if a in successors():
        return "succeeded", f"continued by {successors()[a]}"
    return "unreviewed", ""


def years(stat: dict[str, Any]) -> str:
    first, last = stat["first"][:4], stat["last"][:4]
    return first if first == last else f"{first}-{last}"


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--index", type=Path, default=INDEX, help="The person index to read.")
    parser.add_argument("--all", action="store_true", help="Print every pair, linked and reviewed ones too.")
    parser.add_argument("--repo-root", type=Path, default=Path("."), help="Checkout holding data/. Defaults to the cwd.")
    args = parser.parse_args()

    index = json.loads(args.index.read_text(encoding="utf-8"))
    stats = measure(index)
    unknown = sorted(set(stats) - set(entries()))
    if unknown:
        parser.error(f"index names nominator ids the registry lacks (rebuild it): {unknown[:5]}")
    reviewed = reviewed_distinct()
    rows = []
    for pair in continuity_pairs(stats):
        status, why = classify(pair, reviewed)
        rows.append((*pair, status, why))

    report_path = args.repo_root / REPORT
    report_path.parent.mkdir(parents=True, exist_ok=True)
    lines = ["\t".join(COLUMNS)]
    for a, b, shared, share, status, why in rows:
        lines.append("\t".join([a, b, years(stats[a]), years(stats[b]), str(shared), f"{share:.0%}", status, why]))
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    counts = {s: sum(1 for r in rows if r[4] == s) for s in ("linked", "reviewed", "succeeded", "unreviewed")}
    print(f"{len(stats)} nominators, {len(rows)} continuity pairs -> {report_path}")
    print("linked {linked}, reviewed {reviewed}, succeeded {succeeded}, unreviewed {unreviewed}".format(**counts))
    shown = rows if args.all else [r for r in rows if r[4] == "unreviewed"]
    for a, b, shared, share, status, why in shown:
        print(f"    {status:10} {a} ({years(stats[a])}) -> {b} ({years(stats[b])}): {shared} shared, {share:.0%}" + (f" -- {why}" if why else ""))
    if counts["unreviewed"]:
        print(
            f"\n{counts['unreviewed']} unreviewed pair(s): add the earlier id to the later entry's"
            " `predecessors` in scraper/parties.json, or record the pair under `reviewedDistinct`"
            " with the reason.",
            file=sys.stderr,
        )
        return 1
    print("No findings.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
