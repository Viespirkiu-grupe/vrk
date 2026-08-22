from __future__ import annotations

from pathlib import Path
from typing import Any

from scraper.elections.savivaldybiu_2011.sitemap import ELECTION_ID
# The pre-2016 static layout with the savivaldybių tarybų rinkimų įstatymo
# question set — the same numbering the 2015 municipal pages use (Q8.1–8.5
# under 35 str. 12 d. here, 36 str. 11 d. there; Q9 under 89 str. 1 d.) —
# and the candidacy block the 2015 municipal modules write from their
# sitemaps. Nothing here is this election's own: its differences are all
# in the listing (scraper/elections/savivaldybiu_2011/sitemap.py).
from scraper.elections.telsiu_mero_2015.anketa_parser import (
    normalize_municipal_anketa_rows,
)
from scraper.elections.pakartotiniai_sirvintu_traku_2015.anketa_parser import (
    build_candidacy,
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
        rows_normalizer=normalize_municipal_anketa_rows,
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
        rows_normalizer=normalize_municipal_anketa_rows,
        candidacy_builder=build_candidacy,
    )
