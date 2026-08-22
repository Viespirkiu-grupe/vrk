from __future__ import annotations

from pathlib import Path
import re
from typing import Any

from scraper.elections.savivaldybiu_2007.sitemap import ELECTION_ID
# The pre-2016 layout family's page walkers — the 2007 pages are the
# family's oldest shape, the one the Dzūkija by-election of the same year
# has: a plain-text profile card (name, "Numeris sąraše", "Gimimo data";
# district and nominating party in a header table above it, read by the
# era's legacy-card branch), and an anketa of "label: <b>answer</b>" lines
# with the education and prior-mandate record tables in between. The
# municipal form of that year numbers nothing, so the rows are keyed by
# their prompts here; the keys are the 2011/2015 municipal ones where the
# question is the same, so the concept lines up across the family.
from scraper.elections.pakartotiniai_sirvintu_traku_2015.anketa_parser import (
    build_candidacy,
)
from scraper.elections.seimo_2016.anketa_parser import (
    _find_row_by_prompt_prefix,
    _normalize_table_records,
    _row_answer_text,
    _split_list_value,
)
from scraper.elections.seimo_zirmunu_2015.anketa_parser import (
    _normalize_answer_value,
    load_results,
    parse_anketa_sample as _parse_anketa_sample,
    parse_anketa_samples as _parse_anketa_samples,
)

DEFAULT_SAMPLES_ROOT = Path(f"samples/html/{ELECTION_ID}")
DEFAULT_OUTPUT_ROOT = Path(f"data/{ELECTION_ID}")
# Elected status, joined in from VRK's results tree when the file exists.
DEFAULT_RESULTS_PATH = Path(f"sitemaps/{ELECTION_ID}.results.json")

# "Šeimos nariai: Sutuoktinis/sutuoktinė Vida, Vaikas Gintarė, Vaikas Ieva"
# — one line of role-prefixed names where the later forms ask for the
# spouse (Q19's second line) and the children (Q20) separately.
FAMILY_SPOUSE_PREFIX = re.compile(r"^sutuoktin(?:is|ė)(?:\s*/\s*sutuoktin(?:is|ė))?\s+", re.IGNORECASE)
FAMILY_CHILD_PREFIX = re.compile(r"^vaikas\s+", re.IGNORECASE)


def _prompt_record_rows(rows: list[dict[str, Any]], prompt_prefix: str) -> list[Any]:
    """The records of the inline table whose label starts with the prefix
    (the unnumbered equivalent of the era's `_question_record_rows`)."""
    row = _find_row_by_prompt_prefix(rows, prompt_prefix)
    if row is None or not isinstance(row.get("answer"), list):
        return []
    return list(row["answer"])


def split_family_members(value: str | None) -> tuple[str | None, str | None]:
    """(spouse names, children names) from the family-members line; a part
    with neither prefix goes with the children, which is where the form's
    "Vaikas" entries are the only other thing it lists."""
    if not value:
        return None, None
    spouses: list[str] = []
    children: list[str] = []
    for part in (p.strip() for p in value.split(",")):
        if not part:
            continue
        if FAMILY_SPOUSE_PREFIX.match(part):
            spouses.append(FAMILY_SPOUSE_PREFIX.sub("", part).strip())
        elif FAMILY_CHILD_PREFIX.match(part):
            children.append(FAMILY_CHILD_PREFIX.sub("", part).strip())
        else:
            children.append(part)
    return (", ".join(s for s in spouses if s) or None, ", ".join(c for c in children if c) or None)


def normalize_municipal_2007_anketa_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    def _prompt_answer(prefix: str) -> str | None:
        return _normalize_answer_value(_row_answer_text(_find_row_by_prompt_prefix(rows, prefix)))

    family = _prompt_answer("šeimos nariai")
    spouse, children = split_family_members(family)

    return {
        # The 2007 form does not ask the birth date; the era parser folds the
        # card's "Gimimo data" line in here.
        "gimimo-data": None,
        "adresas": _prompt_answer("nuolatinė gyvenamoji vieta"),
        "pareiskimai": {
            # The savivaldybių tarybų rinkimų įstatymo declarations as the
            # 2007 form words them, each a question of its own.
            "ar-nebaigta-teismo-paskirta-bausme": _prompt_answer("ar neturite nebaigtos atlikti teismo"),
            "ar-atliekate-karo-tarnyba": _prompt_answer("ar nesate asmuo, atliekantis"),
            "ar-eina-nesuderinamas-pareigas": _prompt_answer("ar einate pareigas, nesuderinamas"),
            "ar-kitos-valstybes-institucijos-narys": _prompt_answer("ar esate kitos valstybės renkamos"),
            "ar-turite-kitos-valstybes-pilietybe": _prompt_answer("ar turite kitos valstybės pilietybę"),
            # Asked of every candidate in 2007 and of no later one: whether
            # the right to stand is restricted in the other state of
            # citizenship ("Neapribota" for the Lithuanian-only field too).
            "ar-pasyvioji-rinkimu-teise-neapribota": _prompt_answer("ar pasyvioji rinkimų teisė"),
            # The conviction question, under the same 89 str. 1 d. the 2011
            # and 2015 forms cite as Q9.
            "ar-buvote-pripazintas-kaltu": _prompt_answer("ar turite ką nurodyti pagal"),
        },
        "gimimo-vieta": _prompt_answer("gimimo vieta"),
        "tautybe": _prompt_answer("tautybė"),
        "issilavinimas": {
            "aprasas": None,
            "irasai": _normalize_table_records(_prompt_record_rows(rows, "išsilavinimas")),
        },
        # "Moksliniai laipsniai:" — printed only on the pages that have one.
        "mokslo-laipsnis": _prompt_answer("moksliniai laipsniai"),
        # Not asked in 2007.
        "pedagoginis-vardas": None,
        "uzsienio-kalbos": _split_list_value(
            _row_answer_text(_find_row_by_prompt_prefix(rows, "kokias kalbas moka"))
        ),
        "politine-organizacija": _prompt_answer("kokios partijos, politinės organizacijos"),
        "anksciau-isrinktas": {
            "aprasas": None,
            "irasai": _normalize_table_records(_prompt_record_rows(rows, "buvo išrinktas į")),
        },
        "pagrindine-darboviete": _prompt_answer("pagrindinė darbovietė"),
        "visuomenine-veikla": _prompt_answer("visuomeninė veikla"),
        "pomegiai": _prompt_answer("pomėgiai"),
        "seimine-padetis": _prompt_answer("šeiminė padėtis"),
        "sutuoktinio-vardas-pavarde": spouse,
        "vaiku-vardai-pavardes": children,
        # The line the two above are read from, kept whole.
        "seimos-nariai": family,
        "kita-apie-save": None,
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
        rows_normalizer=normalize_municipal_2007_anketa_rows,
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
        rows_normalizer=normalize_municipal_2007_anketa_rows,
        candidacy_builder=build_candidacy,
    )
