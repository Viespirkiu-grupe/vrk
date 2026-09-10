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
from scraper.elections.seimo_zirmunu_2015.anketa_parser import (
    _normalize_answer_value,
    load_results,
    parse_anketa_sample as _parse_anketa_sample,
    parse_anketa_samples as _parse_anketa_samples,
)
from scraper.shared.anketa_tabs import (
    find_row_by_prompt_prefix,
    normalize_table_records,
    row_answer_text,
    split_list_value,
)

DEFAULT_SAMPLES_ROOT = Path(f"samples/html/{ELECTION_ID}")
DEFAULT_OUTPUT_ROOT = Path(f"data/{ELECTION_ID}")
# Elected status, joined in from VRK's results tree when the file exists.
DEFAULT_RESULTS_PATH = Path(f"sitemaps/{ELECTION_ID}.results.json")

# "Šeimos nariai: Sutuoktinis/sutuoktinė Vida, Vaikas Gintarė, Vaikas Ieva"
# — one line of role-prefixed names where the later forms ask for the
# spouse (Q19's second line) and the children (Q20) separately. The form's
# roles, measured over the whole field: Sutuoktinis/sutuoktinė and
# Partneris/partnerė (a spouse), Vaikas and Augintinis (-ė) (a child),
# Anūkas (neither); a name with no role continues the previous role's
# list ("Vaikas Andrius, Tomas, Giedrius").
FAMILY_ROLE_PREFIXES = [
    (re.compile(r"^(?:sutuoktin(?:is|ė)|partner(?:is|ė))(?:\s*/\s*(?:sutuoktin(?:is|ė)|partner(?:is|ė)))?\s+", re.IGNORECASE), "spouse"),
    (re.compile(r"^(?:vaikas|augintin(?:is|ė)(?:\s*\(-ė\))?)\s+", re.IGNORECASE), "child"),
    (re.compile(r"^(?:anūk(?:as|ė)(?:\s*\(-ė\))?)\s+", re.IGNORECASE), "other"),
]

# The 2007 form's labels. The questionnaire is one run of "label: <b>answer</b>"
# lines, and the era's row splitter starts a row at a text node only when
# the row before it has an answer. Two things on these pages break that:
# a question printed without its <b> at all (its label then joins the next
# label's prompt, and every answer after it lands one label early — the
# pasyvioji rinkimų teisė question on 611 pages, the citizenship one on a
# handful), and the conviction explanation, a bare text line after
# "<b>Taip</b>" that joins the "Gimimo vieta:" prompt. Both are undone by
# splitting a prompt wherever one of the form's labels begins inside it.
LABEL_STARTS = [
    "Nuolatinė gyvenamoji vieta",
    "Ar neturite nebaigtos atlikti teismo",
    "Ar nesate asmuo, atliekantis",
    "Ar einate pareigas, nesuderinamas",
    "Ar esate kitos valstybės renkamos",
    "Ar turite kitos valstybės pilietybę",
    "Ar pasyvioji rinkimų teisė",
    "Ar turite ką nurodyti pagal",
    "Gimimo vieta",
    "Tautybė",
    "Moksliniai laipsniai",
    "Moksliniai vardai",
    "Kokias kalbas moka",
    "Kokios partijos, politinės organizacijos",
    "Pagrindinė darbovietė",
    "Visuomeninė veikla",
    "Pomėgiai",
    "Šeiminė padėtis",
    "Šeimos nariai",
]
LABEL_START_PATTERN = re.compile("|".join(re.escape(label) for label in LABEL_STARTS))
CONVICTION_LABEL = "Ar turite ką nurodyti pagal"


def split_merged_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """The era's rows with every prompt that holds more than one of the
    form's labels — or free text before one — split into a row per label.
    A label the page printed without an answer keeps an empty one; the
    row's answer stays with the last label; free text becomes a row of its
    own with no answer (after the conviction question, the explanation)."""
    result: list[dict[str, Any]] = []
    for row in rows:
        prompt = str(row.get("prompt", ""))
        if not isinstance(row.get("answer"), str):
            result.append(row)
            continue
        starts = [m.start() for m in LABEL_START_PATTERN.finditer(prompt)]
        if not starts:
            result.append(row)
            continue
        segments: list[tuple[str, bool]] = []
        if starts[0] > 0:
            segments.append((prompt[: starts[0]].strip(), False))
        for index, start in enumerate(starts):
            end = starts[index + 1] if index + 1 < len(starts) else len(prompt)
            segment = prompt[start:end].strip()
            # A label ends at its colon; anything after it on the same text
            # run (the conviction explanation when the <b>Taip</b> is
            # missing) is free text.
            colon = segment.find(":")
            if 0 < colon < len(segment) - 1:
                segments.append((segment[: colon + 1].strip(), True))
                segments.append((segment[colon + 1 :].strip(), False))
            else:
                segments.append((segment, True))
        segments = [(text, is_label) for text, is_label in segments if text]
        if len(segments) <= 1:
            result.append(row)
            continue
        # The answer belongs to the last label; a trailing free-text
        # segment would have come after that label's <b>, which the splitter
        # would have made a row of its own, so the last segment is a label.
        last_label = max(i for i, (_, is_label) in enumerate(segments) if is_label)
        for index, (text, _) in enumerate(segments):
            result.append(
                {
                    "questionNumber": None,
                    "prompt": text,
                    "answer": row["answer"] if index == last_label else "",
                }
            )
    for index, row in enumerate(result, start=1):
        row["rowIndex"] = index
    return result


def conviction_explanation(rows: list[dict[str, Any]]) -> str | None:
    """The free-text line after the conviction question: a row of its own,
    prompted by the text and unanswered, that is not one of the labels."""
    for index, row in enumerate(rows):
        if not str(row.get("prompt", "")).startswith(CONVICTION_LABEL):
            continue
        for candidate in rows[index + 1 : index + 2]:
            prompt = str(candidate.get("prompt", "")).strip()
            if prompt and not LABEL_START_PATTERN.match(prompt) and not isinstance(candidate.get("answer"), list):
                return prompt
        return None
    return None


def _prompt_record_rows(rows: list[dict[str, Any]], prompt_prefix: str) -> list[Any]:
    """The records of the inline table whose label starts with the prefix
    (the unnumbered equivalent of the era's `question_record_rows`)."""
    row = find_row_by_prompt_prefix(rows, prompt_prefix)
    if row is None or not isinstance(row.get("answer"), list):
        return []
    return list(row["answer"])


def split_family_members(value: str | None) -> tuple[str | None, str | None]:
    """(spouse names, children names) from the family-members line; a part
    with no role of its own continues the role before it."""
    if not value:
        return None, None
    names: dict[str, list[str]] = {"spouse": [], "child": [], "other": []}
    role = "child"
    for part in (p.strip() for p in value.split(",")):
        if not part:
            continue
        for pattern, prefixed_role in FAMILY_ROLE_PREFIXES:
            if pattern.match(part):
                role = prefixed_role
                part = pattern.sub("", part).strip()
                break
        if part:
            names[role].append(part)
    return (", ".join(names["spouse"]) or None, ", ".join(names["child"]) or None)


def normalize_municipal_2007_anketa_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    rows = split_merged_rows(rows)

    def _prompt_answer(prefix: str) -> str | None:
        return _normalize_answer_value(row_answer_text(find_row_by_prompt_prefix(rows, prefix)))

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
            # The explanation a "Taip" is followed by — a bare text line on
            # this form, where the 2011/2015 forms have a prompted row; the
            # key the rest of the family uses for it.
            "teisiniai-argumentai": _normalize_answer_value(conviction_explanation(rows) or ""),
        },
        "gimimo-vieta": _prompt_answer("gimimo vieta"),
        "tautybe": _prompt_answer("tautybė"),
        "issilavinimas": {
            "aprasas": None,
            "irasai": normalize_table_records(_prompt_record_rows(rows, "išsilavinimas")),
        },
        # "Moksliniai laipsniai:" and "Moksliniai vardai:" — each printed
        # only on the pages that have one.
        "mokslo-laipsnis": _prompt_answer("moksliniai laipsniai"),
        "pedagoginis-vardas": _prompt_answer("moksliniai vardai"),
        "uzsienio-kalbos": split_list_value(
            row_answer_text(find_row_by_prompt_prefix(rows, "kokias kalbas moka"))
        ),
        "politine-organizacija": _prompt_answer("kokios partijos, politinės organizacijos"),
        "anksciau-isrinktas": {
            "aprasas": None,
            "irasai": normalize_table_records(_prompt_record_rows(rows, "buvo išrinktas į")),
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
