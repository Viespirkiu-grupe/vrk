from __future__ import annotations

from pathlib import Path
from typing import Any

from scraper.elections.telsiu_mero_2015.sitemap import ELECTION_ID
# Same pre-2016 layout family as the 2015 Seimo by-elections, but the anketa
# asks the savivaldybių tarybų rinkimų įstatymo questions: Q8.1–8.5 (36 str.
# 11 d.) instead of the Seimo set, and Q9 is the single "anything to declare"
# conviction question (36 str. 12 d.). Only the question-to-key mapping is
# restated here; the page walkers are the era's. Keys follow meru_2017 where
# the municipal question matches, so the concept lines up across eras.
from scraper.elections.seimo_zirmunu_2015.anketa_parser import (
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
from scraper.elections.seimo_zirmunu_2015.anketa_parser import (
    _normalize_answer_value,
)

DEFAULT_SAMPLES_ROOT = Path(f"samples/html/{ELECTION_ID}")
DEFAULT_OUTPUT_ROOT = Path(f"data/{ELECTION_ID}")


def normalize_municipal_anketa_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
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
            "ar-nebaigta-teismo-paskirta-bausme": _answer("8.1"),
            "ar-atliekate-karo-tarnyba": _answer("8.2"),
            "ar-eina-nesuderinamas-pareigas": _answer("8.3"),
            "ar-kitos-valstybes-institucijos-narys": _answer("8.4"),
            "ar-turite-kitos-valstybes-pilietybe": _answer("8.5"),
            "ar-buvote-pripazintas-kaltu": _answer("9"),
        },
        "gimimo-vieta": _answer("10"),
        "tautybe": _answer("11"),
        "issilavinimas": {
            "aprasas": _answer("12"),
            "irasai": _normalize_table_records(_question_record_rows(rows, "12")),
        },
        "uzsienio-kalbos": _split_list_value(
            _row_answer_text(_find_row_by_question_number(rows, "13"))
        ),
        "politine-organizacija": _answer("14"),
        "anksciau-isrinktas": {
            "aprasas": _answer("15"),
            "irasai": _normalize_table_records(_question_record_rows(rows, "15")),
        },
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
) -> tuple[Path, dict[str, Any]]:
    return _parse_anketa_sample(
        candidate_id=candidate_id,
        samples_root=samples_root,
        output_root=output_root,
        election_id=ELECTION_ID,
        rows_normalizer=normalize_municipal_anketa_rows,
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
    )
