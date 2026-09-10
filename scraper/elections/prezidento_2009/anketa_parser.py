from __future__ import annotations

from pathlib import Path
from typing import Any

from scraper.elections.prezidento_2009.sitemap import ELECTION_ID
# The pre-2016 layout family's page walkers, with the 2009 presidential
# question set. It is the 2014 form one revision earlier: Q8 asks only the
# four Respublikos Prezidento rinkimų įstatymo 2 str. questions (unserved
# sentence, armed service, other citizenship, foreign oath) — the
# citizenship-by-origin, residence and Seimas-eligibility questions that open
# 2014's Q8 were not asked yet — and a separate Q9 asks the 3 str. lustration
# question (service in, schooling by, or collaboration with the NKVD/NKGB/
# MGB/KGB and equivalent foreign services), which goes under the corpus's
# `ar-bendradarbiavote-su-uzsienio-tarnybomis` alongside the Seimo and EP
# laws' narrower "knowingly collaborated with other states' special services"
# wording. Birthplace, nationality and education therefore sit at Q10–Q12
# (2014: Q9–Q11); the unnumbered line after the education table asks for the
# academic degree only ("mokslo laipsnį", no pedagogical title); and unlike
# 2014 the Q15 elected-history table is asked, under the Seimo 2015 key.
# The page omits a question it has no answer for — Q7 everywhere, Q15 for
# two candidates, Q20 and the spouse line for the unmarried — so a null is
# an absent row, not an empty one. Keys follow prezidento_2014 where the
# question matches so the concept lines up across eras.
from scraper.elections.seimo_zirmunu_2015.anketa_parser import (
    load_results,
    _normalize_answer_value,
    parse_anketa_sample as _parse_anketa_sample,
    parse_anketa_samples as _parse_anketa_samples,
)
from scraper.shared.anketa_tabs import (
    find_row_by_prompt_prefix,
    find_row_by_question_number,
    normalize_table_records,
    question_record_rows,
    row_answer_text,
    split_list_value,
)

DEFAULT_SAMPLES_ROOT = Path(f"samples/html/{ELECTION_ID}")
DEFAULT_OUTPUT_ROOT = Path(f"data/{ELECTION_ID}")
# Elected status, joined in from VRK's results tree when the file exists.
DEFAULT_RESULTS_PATH = Path(f"sitemaps/{ELECTION_ID}.results.json")


def normalize_presidential_anketa_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    def _answer(question_number: str) -> str | None:
        return _normalize_answer_value(
            row_answer_text(find_row_by_question_number(rows, question_number))
        )

    def _prompt_answer(prefix: str) -> str | None:
        return _normalize_answer_value(row_answer_text(find_row_by_prompt_prefix(rows, prefix)))

    return {
        "gimimo-data": _answer("5"),
        "adresas": _answer("6"),
        "pareiskimai": {
            "ar-nebaigta-teismo-paskirta-bausme": _answer("8.1"),
            "ar-atliekate-karo-tarnyba": _answer("8.2"),
            "ar-turite-kitos-valstybes-pilietybe": _answer("8.3"),
            "ar-susijes-priesaika-uzsienio-valstybei": _answer("8.4"),
            "ar-bendradarbiavote-su-uzsienio-tarnybomis": _answer("9"),
        },
        "gimimo-vieta": _answer("10"),
        "tautybe": _answer("11"),
        "issilavinimas": {
            "aprasas": _answer("12"),
            "irasai": normalize_table_records(question_record_rows(rows, "12")),
        },
        "mokslo-laipsnis": _prompt_answer("jei turite, nurodykite mokslo laipsn"),
        "pedagoginis-vardas": _prompt_answer(", vard") or _prompt_answer("jei turite, nurodykite mokslo vard"),
        "uzsienio-kalbos": split_list_value(
            row_answer_text(find_row_by_question_number(rows, "13"))
        ),
        "politine-organizacija": _answer("14"),
        "anksciau-isrinktas": {
            "aprasas": _answer("15"),
            "irasai": normalize_table_records(question_record_rows(rows, "15")),
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
