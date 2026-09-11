"""Candidate pages of the 2004 Seimas general election.

The same 2004 static-site pages as the EP election four months earlier
(`scraper/elections/ep_2004/anketa_parser.py` reads them), with the Seimas
question set and a richer profile card:

- The card states every candidacy: "Apygarda: <constituency> (Nr.N)" with
  "Iškėlė:" for the single-member one, "Apygarda: Daugiamandatė" with
  "Iškėlė: <list>, priešrinkiminis numeris sąraše: N" for the list one, and
  for a coalition's candidate the member party and the position on its
  own list in parentheses ("(Iškėlė: …, priešrinkiminis numeris sąraše:
  …)"). A constituency nominee who also self-nominated there has two
  constituency blocks. An independent campaign participant's card closes
  with "Kandidatas registruotas savarankišku politinės kampanijos dalyviu.
  Sprendimas - <a>Nr.316, 2004.09.20</a>", the decision as a PDF.
- The questions are the Seimo rinkimų įstatymo set the 2008–2013 pages
  ask: Q8.3 another state's citizenship and Q8.4 an oath to a foreign
  state (the EP form's Q8.4 is another *member* state's citizenship), the
  98 str. questions as Q9.1–9.3, the rest as the EP form.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from scraper.elections.ep_2004.anketa_parser import (
    _row_after,
    parse_anketa_sample as _parse_anketa_sample,
    parse_anketa_samples as _parse_anketa_samples,
)
from scraper.elections.seimo_2004.sitemap import ELECTION_ID
from scraper.elections.seimo_zirmunu_2015.anketa_parser import _normalize_answer_value
from scraper.shared.anketa_tabs import (
    find_row_by_prompt_prefix,
    find_row_by_question_number,
    normalize_space,
    normalize_table_records,
    normalize_text_value,
    question_record_rows,
    row_answer_text,
    split_list_value,
)
from scraper.shared.savivaldybiu_archive_1997 import normalize_birth_date

DEFAULT_SAMPLES_ROOT = Path(f"samples/html/{ELECTION_ID}")
DEFAULT_OUTPUT_ROOT = Path(f"data/{ELECTION_ID}")
# Elected status, joined in from VRK's results tree when the file exists.
DEFAULT_RESULTS_PATH = Path(f"sitemaps/{ELECTION_ID}.results.json")

SELF_NOMINATED_MARKER = "išsikėlė"


def normalize_seimo_2004_anketa_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    def _answer(question_number: str) -> str | None:
        return _normalize_answer_value(
            row_answer_text(find_row_by_question_number(rows, question_number))
        )

    def _prompt_answer(prefix: str) -> str | None:
        return _normalize_answer_value(row_answer_text(find_row_by_prompt_prefix(rows, prefix)))

    birth_date = _answer("3")
    return {
        "gimimo-data": normalize_birth_date(birth_date) if birth_date else None,
        "adresas": _answer("6"),
        "pareiskimai": {
            # The Seimo rinkimų įstatymo 38 str. declarations (Q8.x) and the
            # 98 str. ones (Q9.x), under the 2016 Seimo keys as the 2008–2013
            # pages of the same form are.
            "ar-nebaigta-teismo-paskirta-bausme": _answer("8.1"),
            "ar-atliekate-karo-tarnyba": _answer("8.2"),
            "ar-turite-kitos-valstybes-pilietybe": _answer("8.3"),
            "ar-susijes-priesaika-uzsienio-valstybei": _answer("8.4"),
            "ar-bendradarbiavote-su-uzsienio-tarnybomis": _answer("9.1"),
            "ar-buvote-pripazintas-kaltu": _answer("9.2"),
            "ar-buvote-pripazintas-kaltu-del-sunkaus-nusikaltimo": _answer("9.3"),
            # The Q9 explanation, printed as an unlabelled emphasised row
            # right after 9.3 (as on the EP pages).
            "teisiniai-argumentai": _normalize_answer_value(row_answer_text(_row_after(rows, "9.3"))),
        },
        "gimimo-vieta": _answer("10"),
        "tautybe": _answer("11"),
        "issilavinimas": {
            "aprasas": _answer("12"),
            "irasai": normalize_table_records(question_record_rows(rows, "12")),
        },
        "mokslo-laipsnis": _prompt_answer("moksliniai laipsniai"),
        "pedagoginis-vardas": _prompt_answer("moksliniai vardai"),
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


def finish_candidacy(output_payload: dict[str, Any], parsed: dict[str, Any]) -> None:
    """What the card says beyond the listing.

    The constituency page names one nominator per candidate; the card names
    every one, so a party nominee who also self-nominated in the same
    constituency (two in 2004, both "Išsikėlė pats" on the constituency
    page) has the party recorded here as `vienmandate.kitiIskelejai`. The
    card's campaign registration line, where present, is
    `savarankiskasKampanijosDalyvis` with the decision and its PDF.
    """
    candidacy = output_payload.get("kandidatavimas")
    if not isinstance(candidacy, dict):
        return
    fields = parsed.get("profile", {}).get("fields", [])
    single = candidacy.get("vienmandate")
    if isinstance(single, dict):
        nominators: list[str] = []
        pending_constituency = False
        for field in fields:
            key = normalize_space(str(field.get("key", ""))).lower()
            value = normalize_space(str(field.get("displayValue", "")))
            if key == "apygarda":
                pending_constituency = value.lower() != "daugiamandatė"
            elif key == "iškėlė" and pending_constituency and value:
                nominators.append(value)
        listed = normalize_space(str(single.get("iskele") or ""))
        extra = [name for name in nominators if name.lower() != listed.lower()]
        if extra:
            single["kitiIskelejai"] = extra
    for field in fields:
        key = normalize_space(str(field.get("key", ""))).lower()
        if key.startswith("kandidatas registruotas savarankišku"):
            urls = field.get("urls") or []
            candidacy["savarankiskasKampanijosDalyvis"] = {
                "sprendimas": normalize_text_value(field.get("displayValue")),
                "nuoroda": urls[0] if urls else None,
            }
            break


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
