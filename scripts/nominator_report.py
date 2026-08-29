"""Resolve every record's nominator, join it to the party registry, and gate both.

Issue #82: party affiliation was spread over eleven paths and 427 surface
forms with no canonical id. The resolver (`scraper/shared/nominator.py`) and
the registry (`scraper/parties.json`, matched by `scraper/shared/parties.py`)
fixed that for the corpus as it is -- this script keeps it fixed as the corpus
moves. One pass over `data/` resolves the nominator of every record, matches
it, and checks three things:

* **resolution** -- every record of every mapped election resolves a
  non-null nominator. The mapped elections are the 51 non-presidential ones
  plus 2024-prezidento; the other five presidential elections publish no
  nominator and map no paths, which is self-nomination by law, not a gap.
* **match** -- every resolved string is claimed by exactly one registry
  entry. A form nothing claims is a finding here and lands in the registry's
  `unmatched` block on `--update`, where tests/test_party_registry.py asserts
  the block is empty -- so a new surface form upstream is a red test until a
  registry entry claims it.
* **drift** -- every resolved form is listed in `docs/nominator-forms.tsv`,
  the checked-in table of measured forms. A form the table does not know is
  new upstream data, reported rather than silently absorbed.

Run from the repo root:

    python scripts/nominator_report.py                  # measure and check
    python scripts/nominator_report.py 2024-seimo       # one election
    python scripts/nominator_report.py --update         # rewrite the forms
                                                        # table and the
                                                        # registry's unmatched
                                                        # block after a
                                                        # deliberate change

Writes the full per-election table to data/nominator-report.tsv either way.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scraper.shared.nominator import nominator_paths, resolve_nominator  # noqa: E402
from scraper.shared.parties import REGISTRY_PATH, entry, load_registry, match  # noqa: E402

FORMS_TABLE = Path("docs/nominator-forms.tsv")
REPORT = Path("data/nominator-report.tsv")

FORMS_COLUMNS = ("form", "records", "partija-id", "tipas")
REPORT_COLUMNS = ("election", "records", "resolved", "matched", "pct")


def read_forms_table(path: Path) -> set[str]:
    if not path.exists():
        return set()
    forms: set[str] = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip() or line.startswith("#") or line.startswith("form\t"):
            continue
        forms.add(line.split("\t")[0])
    return forms


def write_forms_table(path: Path, counts: Counter[str]) -> None:
    """One row per surface form the resolver returned, most frequent first.

    The registry id and kind are written alongside so the table reads as the
    measured answer to "which strings exist and what does each join to";
    tests/test_party_registry.py re-derives the join and would catch a stale
    column, so the table cannot quietly disagree with the registry.
    """
    lines = ["\t".join(FORMS_COLUMNS)]
    for form, count in sorted(counts.items(), key=lambda item: (-item[1], item[0])):
        party_id = match(form)
        kind = entry(party_id)["type"] if party_id else ""
        lines.append("\t".join([form, str(count), party_id or "", kind]))
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_unmatched(unmatched: list[str]) -> None:
    registry = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
    registry["unmatched"] = unmatched
    REGISTRY_PATH.write_text(
        json.dumps(registry, ensure_ascii=False, indent=1) + "\n", encoding="utf-8"
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "election_id",
        nargs="*",
        help="Elections to measure. Defaults to every directory under data/.",
    )
    parser.add_argument(
        "--update",
        action="store_true",
        help="Rewrite docs/nominator-forms.tsv and the registry's unmatched block.",
    )
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=Path("."),
        help="Checkout holding data/ and docs/. Defaults to the cwd.",
    )
    args = parser.parse_args()

    data_root = args.repo_root / "data"
    election_ids = args.election_id or sorted(
        child.name for child in data_root.iterdir() if child.is_dir()
    )
    mapped = nominator_paths()

    form_counts: Counter[str] = Counter()
    type_counts: Counter[str] = Counter()
    rows: list[tuple[str, int, int, int]] = []
    unresolved: list[str] = []
    unmatched: Counter[str] = Counter()

    for election_id in election_ids:
        records = resolved = matched = 0
        for record_path in sorted((data_root / election_id).glob("*.json")):
            if record_path.name == "anomalies.jsonl":
                continue
            record = json.loads(record_path.read_text(encoding="utf-8"))
            records += 1
            raw = resolve_nominator(record, election_id)
            if raw is None:
                if election_id in mapped and len(unresolved) < 20:
                    unresolved.append(f"{election_id}/{record_path.name}")
                type_counts["neiskelta"] += 1
                continue
            resolved += 1
            form_counts[raw] += 1
            party_id = match(raw)
            if party_id is None:
                unmatched[raw] += 1
                type_counts["nezinoma"] += 1
            else:
                matched += 1
                type_counts[entry(party_id)["type"]] += 1
        rows.append((election_id, records, resolved, matched))

    report_path = args.repo_root / REPORT
    report_path.parent.mkdir(parents=True, exist_ok=True)
    lines = ["\t".join(REPORT_COLUMNS)]
    for election_id, records, resolved, matched in rows:
        pct = 100.0 * resolved / records if records else 0.0
        note = "" if election_id in mapped else "\tno nominator published"
        lines.append(f"{election_id}\t{records}\t{resolved}\t{matched}\t{pct:.1f}{note}")
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    total = sum(row[1] for row in rows if row[0] in mapped)
    resolved_total = sum(row[2] for row in rows if row[0] in mapped)
    print(f"{len(rows)} election(s) -> {report_path}")
    print(f"mapped elections: {resolved_total}/{total} records resolve a nominator")
    print(f"distinct surface forms: {len(form_counts)}")
    print("by kind: " + ", ".join(f"{kind} {count}" for kind, count in type_counts.most_common()))

    findings: list[str] = []
    for name in unresolved:
        findings.append(f"unresolved nominator on a mapped election: {name}")
    for form, count in unmatched.most_common():
        findings.append(f"no registry entry claims {form!r} ({count} records)")
    known_forms = read_forms_table(args.repo_root / FORMS_TABLE)
    new_forms = sorted(set(form_counts) - known_forms)
    if not args.election_id:
        for form in new_forms:
            findings.append(f"form not in {FORMS_TABLE}: {form!r} ({form_counts[form]} records)")

    if args.update:
        if args.election_id:
            parser.error("--update rewrites the whole table, so it cannot take election ids")
        write_forms_table(args.repo_root / FORMS_TABLE, form_counts)
        print(f"Forms table rewritten: {FORMS_TABLE} ({len(form_counts)} forms)")
        stale = load_registry().get("unmatched", []) != sorted(unmatched)
        if stale:
            write_unmatched(sorted(unmatched))
            print(f"Registry unmatched block rewritten: {len(unmatched)} form(s)")
        if unmatched:
            print(
                "Unmatched forms remain; add each to a registry entry (or a new one)"
                " until tests/test_party_registry.py is green.",
                file=sys.stderr,
            )
        return 0

    if not findings:
        print("No findings.")
        return 0
    print(f"\n{len(findings)} finding(s):", file=sys.stderr)
    for finding in findings[:40]:
        print(f"    {finding}", file=sys.stderr)
    if len(findings) > 40:
        print(f"    ... and {len(findings) - 40} more", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
