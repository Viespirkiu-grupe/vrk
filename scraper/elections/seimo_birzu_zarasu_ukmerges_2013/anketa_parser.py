from __future__ import annotations

from pathlib import Path
from typing import Any

from scraper.elections.seimo_birzu_zarasu_ukmerges_2013.sitemap import ELECTION_ID
# The pre-2016 layout family's page walkers with the Seimo question set as
# the 2012-2013 pages ask it. It is the 2015 Seimo variant plus one question:
# Q9.3, whether the candidate was ever convicted of a grave or very grave
# crime (98 str.), which the 2015 pages no longer carry. Only the mapping is
# restated; everything else is the era's.
from scraper.elections.seimo_zirmunu_2015.anketa_parser import (
    load_results,
    _normalize_anketa_rows as _normalize_seimo_2015_anketa_rows,
    _normalize_answer_value,
    parse_anketa_sample as _parse_anketa_sample,
    parse_anketa_samples as _parse_anketa_samples,
)
from scraper.elections.seimo_2016.anketa_parser import (
    _find_row_by_prompt_prefix,
    _find_row_by_question_number,
    _row_answer_text,
)

DEFAULT_SAMPLES_ROOT = Path(f"samples/html/{ELECTION_ID}")
DEFAULT_OUTPUT_ROOT = Path(f"data/{ELECTION_ID}")
# Elected status, joined in from VRK's results tree when the file exists.
DEFAULT_RESULTS_PATH = Path(f"sitemaps/{ELECTION_ID}.results.json")


def normalize_seimo_2012_anketa_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    normalized = _normalize_seimo_2015_anketa_rows(rows)
    pareiskimai = dict(normalized["pareiskimai"])
    pareiskimai["ar-buvote-pripazintas-kaltu-del-sunkaus-nusikaltimo"] = _normalize_answer_value(
        _row_answer_text(_find_row_by_question_number(rows, "9.3"))
    )
    # The Q9 block's free-text line for anyone who answered "Taip" ("Tuo
    # atveju, jei bent į vieną 9 punkto klausimą atsakėte Taip … paaiškinimą
    # įrašykite čia"), on the 2012 and 2009 EP pages but no longer asked
    # from 2013 on; the 2016 Seimo key for the same slot.
    pareiskimai["teisiniai-argumentai"] = _normalize_answer_value(
        _row_answer_text(_find_row_by_prompt_prefix(rows, "tuo atveju, jei bent į vieną 9 punkto"))
    )
    normalized["pareiskimai"] = pareiskimai
    return normalized


def build_candidacy(candidate_meta: dict[str, Any]) -> dict[str, Any]:
    """The listing-only context for one Seimo candidate.

    Which constituency someone stood in and who nominated them is on the
    listing (and repeated on the profile card); which party list and at what
    position exists for the general election only. Both candidacies are
    carried in from the sitemap under one block so a record reads the same
    whether the person held one or both.

    `isrinktas` is None rather than False: these pages publish no elected
    markers, so electedness is unknown, and a False would assert something
    the source never said.
    """
    roles = candidate_meta.get("roles")
    single = candidate_meta.get("vienmandateCandidacy")
    multi = candidate_meta.get("daugiamandateCandidacy")
    return {
        "vrkCandidateId": str(candidate_meta.get("vrkCandidateId", "")).strip() or None,
        "roles": list(roles) if isinstance(roles, list) else [],
        "vienmandate": single if isinstance(single, dict) else None,
        "daugiamandate": multi if isinstance(multi, dict) else None,
        "isrinktas": None,
    }


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
