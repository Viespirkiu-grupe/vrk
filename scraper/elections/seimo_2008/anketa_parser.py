from __future__ import annotations

from pathlib import Path
from typing import Any

from scraper.elections.seimo_2008.sitemap import ELECTION_ID
# The pre-2016 layout family's page walkers with the Seimo question
# mapping and candidacy block owned by the March 2013 repeat-election
# module: the 2008 form is the 2012 form verbatim — Q8.1-8.4, Q9.1-9.3
# with the free-text explanation line, Q10-Q21 — one term earlier, and the
# profile card carries the same Apygarda/Iškėlė pair per candidacy. What
# the 2008 pages lack is the Kita tab and any campaign participant link.
from scraper.elections.seimo_birzu_zarasu_ukmerges_2013.anketa_parser import (
    build_candidacy,
    normalize_seimo_2012_anketa_rows,
)
from scraper.elections.seimo_zirmunu_2015.anketa_parser import (
    load_results,
    parse_anketa_sample as _parse_anketa_sample,
    parse_anketa_samples as _parse_anketa_samples,
)

DEFAULT_SAMPLES_ROOT = Path(f"samples/html/{ELECTION_ID}")
DEFAULT_OUTPUT_ROOT = Path(f"data/{ELECTION_ID}")
# Elected status, joined in from VRK's results tree when the file exists.
DEFAULT_RESULTS_PATH = Path(f"sitemaps/{ELECTION_ID}.results.json")


def parse_anketa_sample(
    candidate_id: str,
    samples_root: Path = DEFAULT_SAMPLES_ROOT,
    output_root: Path = DEFAULT_OUTPUT_ROOT,
    results_path: Path | None = DEFAULT_RESULTS_PATH,
) -> tuple[Path, dict[str, Any]]:
    return _parse_anketa_sample(
        results_lookup=load_results(results_path),
        candidate_id=candidate_id,
        samples_root=samples_root,
        output_root=output_root,
        election_id=ELECTION_ID,
        rows_normalizer=normalize_seimo_2012_anketa_rows,
        candidacy_builder=build_candidacy,
    )


def parse_anketa_samples(
    candidate_ids: list[str] | None,
    samples_root: Path = DEFAULT_SAMPLES_ROOT,
    output_root: Path = DEFAULT_OUTPUT_ROOT,
    results_path: Path | None = DEFAULT_RESULTS_PATH,
) -> list[dict[str, Any]]:
    return _parse_anketa_samples(
        results_lookup=load_results(results_path),
        candidate_ids=candidate_ids,
        samples_root=samples_root,
        output_root=output_root,
        election_id=ELECTION_ID,
        rows_normalizer=normalize_seimo_2012_anketa_rows,
        candidacy_builder=build_candidacy,
    )
