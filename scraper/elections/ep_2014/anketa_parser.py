from __future__ import annotations

from pathlib import Path
from typing import Any

from scraper.elections.ep_2014.sitemap import ELECTION_ID
# The pre-2016 layout family's page walkers with the European Parliament
# question set: the birth date is numbered Q3 (the only such numbering in
# the corpus), Q8.1-8.3 are the rinkimų į Europos Parlamentą įstatymo 37
# str. questions with 8.3.1/8.3.2 on another member state's citizenship, and
# Q9.1-9.3 the 93 str. ones. Q10-Q20 match the Seimo variant, including the
# degree/title line after the education table; there is no Q21. Keys follow
# ep_2019 where the question matches.
from scraper.elections.seimo_birzu_zarasu_ukmerges_2013.anketa_parser import (
    build_candidacy,
)
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


def normalize_ep_anketa_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    def _answer(question_number: str) -> str | None:
        return _normalize_answer_value(
            row_answer_text(find_row_by_question_number(rows, question_number))
        )

    def _prompt_answer(prefix: str) -> str | None:
        return _normalize_answer_value(row_answer_text(find_row_by_prompt_prefix(rows, prefix)))

    return {
        "gimimo-data": _answer("3"),
        "adresas": _answer("6"),
        "pareiskimai": {
            "ar-nebaigta-teismo-paskirta-bausme": _answer("8.1"),
            "ar-atliekate-karo-tarnyba": _answer("8.2"),
            "ar-turite-kitos-valstybes-pilietybe": _answer("8.3"),
            "kitos-valstybes-pilietybe-valstybe": _answer("8.3.1"),
            "ar-atimta-balsavimo-teise-kitoje-valstybeje": _answer("8.3.2"),
            "ar-bendradarbiavote-su-uzsienio-tarnybomis": _answer("9.1"),
            "ar-buvote-pripazintas-kaltu": _answer("9.2"),
            "ar-buvote-pripazintas-kaltu-del-sunkaus-nusikaltimo": _answer("9.3"),
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
        rows_normalizer=normalize_ep_anketa_rows,
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
        rows_normalizer=normalize_ep_anketa_rows,
        candidacy_builder=build_candidacy,
    )
