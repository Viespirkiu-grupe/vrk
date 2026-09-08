"""Every published constituency label, what it resolves to, and the table that pins it.

Issue #133: the single-mandate constituency reached the candidacy table as
315 raw labels for what is a few dozen districts per era, and the dashboard
could not offer it as a facet. `scraper/shared/apygardos.py` now folds the
label eras to one name per district; this script measures every label the
corpus publishes and writes `docs/constituency-forms.tsv` -- form, records,
the name and number it resolves to, the elections carrying it -- so a clone
can hold the corpus's spellings to the rule (tests/test_apygardos.py) and a
new spelling upstream is a red test before it is a doubled facet row.

    python scripts/constituency_report.py           # measure, compare with the table, exit 1 on drift
    python scripts/constituency_report.py --update  # rewrite the table
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scraper.shared.apygardos import normalize_name, number_of  # noqa: E402
from scraper.shared.kandidatura import kandidatura  # noqa: E402

TABLE = Path("docs/constituency-forms.tsv")
COLUMNS = ("form", "records", "name", "number", "elections")


def measure(repo_root: Path) -> tuple[Counter[str], dict[str, set[str]]]:
    registry = json.loads((repo_root / "scraper" / "elections.json").read_text(encoding="utf-8"))["elections"]
    counts: Counter[str] = Counter()
    elections: dict[str, set[str]] = defaultdict(set)
    for entry in registry:
        directory = repo_root / "data" / entry["id"]
        if not directory.is_dir():
            continue
        for path in sorted(directory.glob("*.json")):
            if path.name == "anomalies.jsonl":
                continue
            record = json.loads(path.read_text(encoding="utf-8"))
            raw = kandidatura(record, entry["kind"])["apygarda-raw"]
            if raw:
                counts[raw] += 1
                elections[raw].add(entry["id"])
    return counts, elections


def read_table(path: Path) -> dict[str, tuple[str, str]]:
    rows: dict[str, tuple[str, str]] = {}
    if not path.exists():
        return rows
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip() or line.startswith(COLUMNS[0] + "\t"):
            continue
        form, _records, name, number, _elections = (line.split("\t") + [""] * 5)[:5]
        rows[form] = (name, number)
    return rows


def write_table(path: Path, counts: Counter[str], elections: dict[str, set[str]]) -> None:
    lines = ["\t".join(COLUMNS)]
    for form in sorted(counts, key=lambda f: (normalize_name(f) or "", f)):
        lines.append(
            "\t".join(
                [
                    form,
                    str(counts[form]),
                    normalize_name(form) or "",
                    str(number_of(form) or ""),
                    ",".join(sorted(elections[form])),
                ]
            )
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--repo-root", type=Path, default=Path("."))
    parser.add_argument("--update", action="store_true", help="Rewrite docs/constituency-forms.tsv from this run.")
    args = parser.parse_args()

    counts, elections = measure(args.repo_root)
    if not counts:
        print("No constituency label found under data/: the corpus is scraped, not cloned.", file=sys.stderr)
        return 2
    names = {normalize_name(form) for form in counts} - {None}
    print(f"{len(counts)} published form(s) over {sum(counts.values())} candidacies resolve to {len(names)} district name(s)")
    table_path = args.repo_root / TABLE
    if args.update:
        write_table(table_path, counts, elections)
        print(f"wrote {table_path}")
        return 0
    known = read_table(table_path)
    missing = sorted(form for form in counts if form not in known)
    if missing:
        print(f"{len(missing)} form(s) the table lacks -- run with --update:", file=sys.stderr)
        for form in missing:
            print(f"    {form!r} -> {normalize_name(form)!r}", file=sys.stderr)
        return 1
    print("No findings.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
