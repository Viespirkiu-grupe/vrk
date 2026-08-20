from __future__ import annotations

from pathlib import Path
from typing import Any

from scraper.elections.pakartotiniai_silutes_2015.sitemap import ELECTION_ID
# The 2015-era page walkers with the municipal question mapping, the same
# combination the Telšiai and June 7th repeat modules use.
from scraper.elections.telsiu_mero_2015.anketa_parser import (
    normalize_municipal_anketa_rows,
)
from scraper.elections.pakartotiniai_sirvintu_traku_2015.anketa_parser import (
    build_candidacy,
)
from scraper.elections.seimo_zirmunu_2015.anketa_parser import (
    parse_anketa_sample as _parse_anketa_sample,
    parse_anketa_samples as _parse_anketa_samples,
)

DEFAULT_SAMPLES_ROOT = Path(f"samples/html/{ELECTION_ID}")
DEFAULT_OUTPUT_ROOT = Path(f"data/{ELECTION_ID}")


def parse_anketa_sample(
    candidate_id: str,
    samples_root: Path = DEFAULT_SAMPLES_ROOT,
    output_root: Path = DEFAULT_OUTPUT_ROOT,
) -> tuple[Path, dict[str, Any]]:
    return _parse_anketa_sample(
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
) -> list[dict[str, Any]]:
    return _parse_anketa_samples(
        candidate_ids=candidate_ids,
        samples_root=samples_root,
        output_root=output_root,
        election_id=ELECTION_ID,
        rows_normalizer=normalize_municipal_anketa_rows,
        candidacy_builder=build_candidacy,
    )
