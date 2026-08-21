from __future__ import annotations

from pathlib import Path
from typing import Any

from scraper.elections.seimo_2012.sitemap import ELECTION_ID
# The pre-2016 layout family's page walkers with the Seimo 2012-2013
# question mapping and the Seimo candidacy block, both owned by the March
# 2013 repeat-election module — the same pages, one election earlier. A
# candidate's profile card here carries one Apygarda/Iškėlė pair per
# candidacy (the single-member one first, then "Daugiamandatė" with the list
# link and position); the recurring labels land as apygarda/iskele and
# apygarda-2/iskele-2, while the kandidatavimas block is the structured
# reading of the same facts from the listings.
from scraper.elections.seimo_birzu_zarasu_ukmerges_2013.anketa_parser import (
    build_candidacy,
    normalize_seimo_2012_anketa_rows,
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
        rows_normalizer=normalize_seimo_2012_anketa_rows,
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
        rows_normalizer=normalize_seimo_2012_anketa_rows,
        candidacy_builder=build_candidacy,
    )
