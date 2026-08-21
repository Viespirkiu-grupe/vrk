from __future__ import annotations

from pathlib import Path
from typing import Any

from scraper.elections.prezidento_2014.sitemap import ELECTION_ID
# The pre-2016 layout family's page walkers, with the presidential question
# set: Q8.1-8.7 are the Respublikos Prezidento rinkimų įstatymo 2 str.
# eligibility questions (citizenship by origin, three years' residence,
# eligibility for the Seimas, then the four the Seimo variant asks), so
# birthplace, nationality and education shift to Q9-Q11, an unnumbered
# academic-title line follows the education table, and there is no Q15
# elected-history table. Keys follow prezidento_2019 where the question
# matches and the Seimo 2015 variant elsewhere, so the concept lines up
# across eras.
from scraper.elections.seimo_zirmunu_2015.anketa_parser import (
    load_results,
    _normalize_answer_value,
    parse_anketa_sample as _parse_anketa_sample,
    parse_anketa_samples as _parse_anketa_samples,
)
from scraper.elections.seimo_2016.anketa_parser import (
    _find_row_by_prompt_prefix,
    _find_row_by_question_number,
    _normalize_table_records,
    _question_record_rows,
    _row_answer_text,
    _split_list_value,
)

DEFAULT_SAMPLES_ROOT = Path(f"samples/html/{ELECTION_ID}")
DEFAULT_OUTPUT_ROOT = Path(f"data/{ELECTION_ID}")
# Elected status, joined in from VRK's results tree when the file exists.
DEFAULT_RESULTS_PATH = Path(f"sitemaps/{ELECTION_ID}.results.json")


def normalize_presidential_anketa_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    def _answer(question_number: str) -> str | None:
        return _normalize_answer_value(
            _row_answer_text(_find_row_by_question_number(rows, question_number))
        )

    def _prompt_answer(prefix: str) -> str | None:
        return _normalize_answer_value(_row_answer_text(_find_row_by_prompt_prefix(rows, prefix)))

    return {
        "gimimo-data": _answer("5"),
        "adresas": _answer("6"),
        "pareiskimai": {
            "ar-esate-pilietis-pagal-kilme": _answer("8.1"),
            "ar-gyvenate-lietuvoje-trejus-metus": _answer("8.2"),
            "ar-galite-buti-renkamas-seimo-nariu": _answer("8.3"),
            "ar-nebaigta-teismo-paskirta-bausme": _answer("8.4"),
            "ar-atliekate-karo-tarnyba": _answer("8.5"),
            "ar-turite-kitos-valstybes-pilietybe": _answer("8.6"),
            "ar-susijes-priesaika-uzsienio-valstybei": _answer("8.7"),
        },
        "gimimo-vieta": _answer("9"),
        "tautybe": _answer("10"),
        "issilavinimas": {
            "aprasas": _answer("11"),
            "irasai": _normalize_table_records(_question_record_rows(rows, "11")),
        },
        # One combined line, as on the 2016 Seimo pages, which also keep it
        # under this key.
        "pedagoginis-vardas": _prompt_answer("jei turite, nurodykite pedagogin"),
        "uzsienio-kalbos": _split_list_value(
            _row_answer_text(_find_row_by_question_number(rows, "13"))
        ),
        "politine-organizacija": _answer("14"),
        "pagrindine-darboviete": _answer("16"),
        "visuomenine-veikla": _answer("17"),
        "pomegiai": _answer("18"),
        "seimine-padetis": _answer("19"),
        "sutuoktinio-vardas-pavarde": _prompt_answer("vyro arba žmonos vardas"),
        "vaiku-vardai-pavardes": _answer("20"),
        "kita-apie-save": _answer("21"),
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
        rows_normalizer=normalize_presidential_anketa_rows,
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
        rows_normalizer=normalize_presidential_anketa_rows,
    )
