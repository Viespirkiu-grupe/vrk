from __future__ import annotations

from pathlib import Path
from typing import Any

# The 2004 Seimas pages one year on: the same card (one constituency
# candidacy, the campaign registration decision) and the same Seimo
# rinkimų įstatymo question set, read by the 2004 Seimas module's mapping
# and card hook with this election's id.
from scraper.elections.ep_2004.anketa_parser import (
    parse_anketa_sample as _parse_anketa_sample,
    parse_anketa_samples as _parse_anketa_samples,
)
from scraper.elections.seimo_2004.anketa_parser import (
    finish_candidacy,
    normalize_seimo_2004_anketa_rows,
)
from scraper.elections.seimo_kedainiu_2005.sitemap import ELECTION_ID

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
        candidate_id=candidate_id,
        samples_root=samples_root,
        output_root=output_root,
        results_path=results_path,
        election_id=ELECTION_ID,
        rows_normalizer=normalize_seimo_2004_anketa_rows,
        candidacy_finisher=finish_candidacy,
    )


def parse_anketa_samples(
    candidate_ids: list[str] | None,
    samples_root: Path = DEFAULT_SAMPLES_ROOT,
    output_root: Path = DEFAULT_OUTPUT_ROOT,
    results_path: Path | None = DEFAULT_RESULTS_PATH,
) -> list[dict[str, Any]]:
    return _parse_anketa_samples(
        candidate_ids=candidate_ids,
        samples_root=samples_root,
        output_root=output_root,
        results_path=results_path,
        election_id=ELECTION_ID,
        rows_normalizer=normalize_seimo_2004_anketa_rows,
        candidacy_finisher=finish_candidacy,
    )
