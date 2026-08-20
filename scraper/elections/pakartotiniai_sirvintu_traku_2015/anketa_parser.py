from __future__ import annotations

from pathlib import Path
from typing import Any

from scraper.elections.pakartotiniai_sirvintu_traku_2015.sitemap import ELECTION_ID
# The 2015-era page walkers with the municipal question mapping, the same
# combination the Telšiai module uses — this election asks the identical
# savivaldybių tarybų rinkimų įstatymo questions.
from scraper.elections.telsiu_mero_2015.anketa_parser import (
    normalize_municipal_anketa_rows,
)
from scraper.elections.seimo_zirmunu_2015.anketa_parser import (
    parse_anketa_sample as _parse_anketa_sample,
    parse_anketa_samples as _parse_anketa_samples,
)

DEFAULT_SAMPLES_ROOT = Path(f"samples/html/{ELECTION_ID}")
DEFAULT_OUTPUT_ROOT = Path(f"data/{ELECTION_ID}")


def build_candidacy(candidate_meta: dict[str, Any]) -> dict[str, Any]:
    """The listing-only context for one candidate.

    Which municipality someone stood in, on whose list, at which position and
    in which roles is published on the listing pages and nowhere on the
    candidate page, so it is carried in from the sitemap — the same block the
    municipal general elections write.

    `isrinktas` is None rather than False: the 2015 pages publish no elected
    markers at all, so electedness is unknown here, and a False would assert
    something the source never said.
    """
    roles = candidate_meta.get("roles")
    council = candidate_meta.get("councilCandidacy")
    mayoral = candidate_meta.get("mayoralCandidacy")

    return {
        "vrkCandidateId": str(candidate_meta.get("vrkCandidateId", "")).strip() or None,
        "savivaldybe": candidate_meta.get("municipality") or None,
        "roles": list(roles) if isinstance(roles, list) else [],
        "tarybosNarys": council if isinstance(council, dict) else None,
        "meras": mayoral if isinstance(mayoral, dict) else None,
        "isrinktas": None,
    }


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
