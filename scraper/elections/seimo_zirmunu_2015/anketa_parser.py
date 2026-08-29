from __future__ import annotations

import errno
import json
from pathlib import Path
import re
from typing import Any

from bs4 import BeautifulSoup, NavigableString, Tag

from scraper.elections.seimo_zirmunu_2015.sitemap import ELECTION_ID, resolve_candidate_url
# The 2015-era pages predate every parsed layout, so the page walkers below are
# written against them; only the format-agnostic helpers — text/missing-value
# normalization, row lookups, record and section normalizers — come from the
# 2016 module.
from scraper.elections.seimo_2016.anketa_parser import (
    _find_row_by_prompt_prefix,
    _find_row_by_question_number,
    _normalize_biografija_data,
    _normalize_kita_data,
    _normalize_links,
    _normalize_missing_values,
    _normalize_privaciu_interesu_data,
    _normalize_profile_data,
    _normalize_table_records,
    _normalize_text_value,
    _order_dict_keys,
    _question_record_rows,
    _row_answer_text,
    _source_key,
    _split_list_value,
    _tag_text,
    normalize_space,
)
from scraper.shared.anomalies import build_anomaly_event
from scraper.shared.deklaracijos import normalize_declaration, section_form
from scraper.shared.election_results import ANKETA_ID_PATTERN, load_results_lookup
from scraper.shared.files import write_candidate_record
from scraper.shared.values import as_money

DEFAULT_SAMPLES_ROOT = Path("samples/html/2015-kovo-1-seimo-zirmunai")
DEFAULT_OUTPUT_ROOT = Path("data/2015-kovo-1-seimo-zirmunai")
# This election's own results file; sibling modules pass their own lookup.
DEFAULT_RESULTS_PATH = Path("sitemaps/2015-kovo-1-seimo-zirmunai.results.json")

# Question numbers start a text node ("5. Gimimo data", "8.1 Ar turite" — the
# sub-question form carries no trailing dot). The bound keeps statute citations
# that begin a line in the municipal variant ("91 str. 1 d. ...") from reading
# as questions.
QUESTION_START_PATTERN = re.compile(r"^\s*(\d{1,2}(?:\.\d{1,2})*)\.?\s+")
MAX_QUESTION_NUMBER = 30

# VRK publishes a candidate whose anketa it never received as a page whose
# content is the single word "Rengiama" — the questionnaire is genuinely
# absent upstream, not missed by the parser.
ANKETA_PLACEHOLDER_TEXTS = {"rengiama"}

# The municipal profile cards close with a standing notice to parties and
# candidates. It is page furniture, not a field, and it is emphasised like a
# value, so it is recognised and dropped rather than attached to whatever
# label happens to precede it. Its opening words differ by year — the 2015
# pages address "Politinių partijų, visuomeninių rinkimų komitetų ir
# kandidatų atstovus", the 2011 ones, before election committees existed,
# "Politinių partijų ir kandidatų atstovus" — so it is recognised by the
# invitation that follows, the same on both.
PROFILE_NOTICE_MARKER = "kviečiame susipažinti su skelbiamais duomenimis"


# The income extract stated as one sentence on the form's own line —
# "GPM305 formos deklaracijos: Gauta 0 Lt, išskaičiuota pajamų mokesčio
# 0 Lt" — instead of the two labelled rows. Thirty pages across the 2011 and
# March 2015 municipal generals do this, every one of them a declared zero,
# which is a statement and not a missing declaration; the 2007 municipal pages
# state every income form this way.
#
# Either figure can be missing from the sentence, and the sentence is printed
# anyway: "Gauta 4200.00 Lt , išskaičiuota pajamų mokesčio Lt" is the shape of
# 531 lines on 529 records of `2007-vasario-25-savivaldybiu`. Requiring both
# figures refused the whole line and lost the income with the tax, so both are
# optional and the absent one normalizes to null (issue #98).
TURTO_PAJAMU_PROSE_PATTERN = re.compile(
    r"^\s*Gauta\s+(?:(?P<income>-?[\d\s.,]+?)\s*)?Lt\b\s*,"
    r"\s*išskaičiuota pajamų mokesčio\s+(?:(?P<tax>-?[\d\s.,]+?)\s*)?Lt\b",
    re.IGNORECASE,
)


def _extract_links(container: Tag | None) -> list[str]:
    if container is None:
        return []

    anchors: list[Tag] = []
    if container.name == "a":
        anchors.append(container)
    anchors.extend(container.find_all("a"))

    links: list[str] = []
    for anchor in anchors:
        href = normalize_space(anchor.get("href", ""))
        if not href or href == "#":
            continue
        resolved = resolve_candidate_url(href)
        if resolved not in links:
            links.append(resolved)
    return links


def _candidate_info_divs(soup: BeautifulSoup) -> list[Tag]:
    return soup.select("div.candidateInfo")


def _profile_div(soup: BeautifulSoup) -> Tag | None:
    divs = _candidate_info_divs(soup)
    return divs[0] if divs else None


def _content_div(soup: BeautifulSoup) -> Tag | None:
    # Every candidate page carries the profile card as the first
    # div.candidateInfo and the tab's own content as the second.
    divs = _candidate_info_divs(soup)
    if len(divs) < 2:
        return None
    return divs[-1]


# ---------------------------------------------------------------------------
# Profile card
# ---------------------------------------------------------------------------


def _parse_profile_html(soup: BeautifulSoup) -> dict[str, Any]:
    profile: dict[str, Any] = {
        "candidateDisplayName": "",
        "electedNote": "",
        "photoSrc": "",
        "fields": [],
    }

    card = _profile_div(soup)
    if card is None:
        return profile

    img = card.find("img")
    if img is not None:
        src = normalize_space(img.get("src", ""))
        if src:
            profile["photoSrc"] = resolve_candidate_url(src)

    cells = card.find_all("td")
    detail_cell = None
    for cell in cells:
        if cell.find("b") is not None:
            detail_cell = cell
            break
    if detail_cell is None:
        return _parse_legacy_profile_card(soup, card, profile)

    fields: list[dict[str, Any]] = []
    pending_label = ""

    # The municipal pages wrap the name in <p texttransform="uppercase">, so it
    # is not a direct child of the cell. Reading it here first also keeps the
    # unlabelled <b> further down — VRK's "kviečiame susipažinti su skelbiamais
    # duomenimis" notice — from being promoted to the name instead.
    name_paragraph = detail_cell.find("p")
    if name_paragraph is not None:
        name_node = name_paragraph.find("b")
        if name_node is not None:
            profile["candidateDisplayName"] = _tag_text(name_node)

    for node in detail_cell.children:
        if isinstance(node, NavigableString):
            text = normalize_space(str(node))
            if text:
                pending_label = f"{pending_label} {text}".strip() if pending_label else text
            continue
        if not isinstance(node, Tag):
            continue
        if node.name == "br":
            continue
        if node.name == "b":
            value_text = _tag_text(node)
            if PROFILE_NOTICE_MARKER in value_text.lower():
                # A label still pending here has no value of its own — the
                # self-nomination flag ("Išsikėlęs kandidatas") is written
                # that way — so it is kept as a valueless field rather than
                # taking the notice as its value or vanishing with it.
                if pending_label:
                    fields.append(
                        {
                            "key": pending_label.rstrip(":"),
                            "displayValue": "",
                            "urls": [],
                        }
                    )
                pending_label = ""
                continue
            if not profile["candidateDisplayName"] and not pending_label:
                profile["candidateDisplayName"] = value_text
                continue
            fields.append(
                {
                    "key": pending_label.rstrip(":"),
                    "displayValue": value_text,
                    "urls": _extract_links(node),
                }
            )
            pending_label = ""
            continue
        if node.name == "a":
            # The campaign participant link (and, on the municipal pages, the
            # program PDF) stands on its own rather than following a label.
            label = _tag_text(node)
            urls = _extract_links(node)
            if label or urls:
                fields.append(
                    {
                        "key": label,
                        "displayValue": "",
                        "urls": urls,
                    }
                )
            pending_label = ""

    profile["fields"] = fields
    return profile


def _parse_legacy_profile_card(soup: BeautifulSoup, card: Tag, profile: dict[str, Any]) -> dict[str, Any]:
    # The 2007 by-election card (the oldest page of the family) emphasises
    # nothing: the name and "Gimimo data: 1946-01-08" are plain text runs,
    # the campaign and results links stand alone, and the constituency and
    # the nominating party sit in a two-cell header table above the card,
    # in <strong>. They are read into the same fields the later cards
    # label Apygarda / Iškėlė, so the record keeps the era's keys.
    cells = card.find_all("td")
    detail_cell = None
    for cell in cells:
        if cell.find("img") is None and _tag_text(cell):
            detail_cell = cell
            break
    if detail_cell is None:
        return profile

    fields: list[dict[str, Any]] = []
    header = card.find_previous("table")
    if header is not None:
        strongs = [_tag_text(node) for node in header.find_all("strong")]
        if len(strongs) == 2:
            fields.append({"key": "Apygarda", "displayValue": strongs[0], "urls": []})
            fields.append({"key": "Iškėlė", "displayValue": strongs[1], "urls": []})

    pending_label = ""
    for node in detail_cell.children:
        if isinstance(node, NavigableString):
            text = normalize_space(str(node))
            if not text or text in (",", "."):
                continue
            if ":" in text:
                label, _, value = text.partition(":")
                if value.strip():
                    fields.append({"key": label.strip(), "displayValue": value.strip(), "urls": []})
                    pending_label = ""
                else:
                    pending_label = label.strip()
                continue
            if not profile["candidateDisplayName"]:
                profile["candidateDisplayName"] = text
            continue
        if isinstance(node, Tag) and node.name == "a":
            label = _tag_text(node)
            urls = _extract_links(node)
            if label or urls:
                fields.append({"key": label, "displayValue": "", "urls": urls})
    profile["fields"] = fields
    return profile


# ---------------------------------------------------------------------------
# Anketa
# ---------------------------------------------------------------------------


def _match_question_start(text: str) -> tuple[str, str] | None:
    match = QUESTION_START_PATTERN.match(text)
    if not match:
        return None
    number = match.group(1)
    if int(number.split(".", 1)[0]) > MAX_QUESTION_NUMBER:
        return None
    return number, text[match.end():]


def _parse_inline_record_table(table: Tag) -> dict[str, Any]:
    # Q12/Q15 record tables label themselves: the first row is the question
    # ("12. Išsilavinimas:"), the second the column names, the rest records.
    label = ""
    headers: list[str] = []
    records: list[dict[str, str]] = []

    for tr in table.find_all("tr"):
        cells = tr.find_all("td")
        if not cells:
            continue
        values = [_tag_text(cell) for cell in cells]
        if len(cells) == 1 and not headers:
            label = f"{label} {values[0]}".strip() if label else values[0]
            continue
        if not headers:
            headers = values
            continue
        record = {
            headers[index] if index < len(headers) else f"stulpelis-{index + 1}": value
            for index, value in enumerate(values)
        }
        records.append(record)

    question_number = None
    started = _match_question_start(label)
    if started is not None:
        question_number = started[0]

    return {
        "questionNumber": question_number,
        "prompt": label,
        "answer": records,
    }


def _parse_anketa_cell(cell: Tag | None) -> dict[str, Any]:
    if cell is None:
        return {
            "rows": [],
            "stats": {"rowCount": 0, "answeredRowCount": 0},
        }

    rows: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None

    def _flush() -> None:
        nonlocal current
        if current is None:
            return
        current["prompt"] = normalize_space(current["prompt"])
        current["answer"] = (
            current["answer"]
            if isinstance(current["answer"], list)
            else normalize_space(current["answer"])
        )
        if current["prompt"] or current["answer"]:
            rows.append(current)
        current = None

    def _start(question_number: str | None, prompt: str) -> None:
        nonlocal current
        _flush()
        current = {
            "questionNumber": question_number,
            "prompt": prompt,
            "answer": "",
        }

    for node in cell.children:
        if isinstance(node, NavigableString):
            text = normalize_space(str(node))
            if not text:
                continue
            started = _match_question_start(str(node))
            if started is not None:
                number, remainder = started
                _start(number, f"{number}. {normalize_space(remainder)}")
            elif current is None or current["answer"]:
                # Unnumbered prompt after an answered question — the spouse
                # name line under Q19 is the recurring case.
                _start(None, text)
            else:
                current["prompt"] = f"{current['prompt']} {text}".strip()
            continue

        if not isinstance(node, Tag):
            continue
        if node.name == "br":
            continue
        if node.name == "table":
            _flush()
            table_row = _parse_inline_record_table(node)
            if table_row["prompt"] or table_row["answer"]:
                rows.append(table_row)
            continue
        if node.name == "b":
            text = _tag_text(node)
            if not text:
                # An empty emphasised answer still answers its prompt: the
                # row closes, so the next label starts a row of its own
                # rather than joining this prompt and taking the next value.
                # Only the unnumbered 2007 municipal form can be misread
                # that way — in the numbered forms an empty answer is always
                # followed by a table or a numbered question.
                if current is not None and not current["answer"]:
                    _flush()
                continue
            if current is None:
                _start(None, "")
            if isinstance(current["answer"], str):
                current["answer"] = f"{current['answer']} {text}".strip()
            continue

        # Any other inline tag contributes to the prompt.
        text = _tag_text(node)
        if text and current is not None and not current["answer"]:
            current["prompt"] = f"{current['prompt']} {text}".strip()

    _flush()

    for row_index, row in enumerate(rows, start=1):
        row["rowIndex"] = row_index

    answered_count = sum(1 for row in rows if row.get("answer"))
    return {
        "rows": rows,
        "stats": {"rowCount": len(rows), "answeredRowCount": answered_count},
    }


def _normalize_answer_value(value: str) -> str | None:
    # The page template joins workplace and position with a comma, so an
    # empty pair renders as a bare "," — an artifact, not an answer.
    if isinstance(value, str) and not value.strip(" ,"):
        return None
    return _normalize_text_value(value)


def _normalize_anketa_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
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
            # The Seimo rinkimų įstatymo 38 str. 4 d. declarations (Q8.x) and
            # the 98 str. 1 ir 3 d. ones (Q9.x), under the 2016 Seimo keys.
            "ar-nebaigta-teismo-paskirta-bausme": _answer("8.1"),
            "ar-atliekate-karo-tarnyba": _answer("8.2"),
            "ar-turite-kitos-valstybes-pilietybe": _answer("8.3"),
            "ar-susijes-priesaika-uzsienio-valstybei": _answer("8.4"),
            "ar-bendradarbiavote-su-uzsienio-tarnybomis": _answer("9.1"),
            "ar-buvote-pripazintas-kaltu": _answer("9.2"),
        },
        "gimimo-vieta": _answer("10"),
        "tautybe": _answer("11"),
        "issilavinimas": {
            "aprasas": _answer("12"),
            "irasai": _normalize_table_records(_question_record_rows(rows, "12")),
        },
        # The unnumbered line after the education table: "Jei turite,
        # nurodykite mokslo laipsnį <b>…</b>, vardą <b>…</b>" — degree and
        # pedagogical title on one line, which the row splitter reads as
        # two rows, the second prompted ", vardą"; a page with a title but
        # no degree prints "Jei turite, nurodykite mokslo vardą" alone. The
        # keys the 2019+ eras use for the same two facts.
        "mokslo-laipsnis": _prompt_answer("jei turite, nurodykite mokslo laipsn"),
        "pedagoginis-vardas": _prompt_answer(", vard") or _prompt_answer("jei turite, nurodykite mokslo vard"),
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


def parse_anketa_html(
    html: str,
    rows_normalizer: Any = None,
) -> dict[str, Any]:
    if rows_normalizer is None:
        rows_normalizer = _normalize_anketa_rows

    soup = BeautifulSoup(html, "lxml")

    profile = _parse_profile_html(soup)

    content = _content_div(soup)
    anketa_cell = None
    if content is not None:
        anketa_table = content.find("table")
        if anketa_table is not None:
            anketa_cell = anketa_table.find("td")

    anketa = _parse_anketa_cell(anketa_cell)
    anketa["normalized"] = rows_normalizer(anketa["rows"])
    # The 2007 form does not ask Q5; the birth date is the card's
    # "Gimimo data" line instead, and it belongs under the anketa key every
    # other era publishes it under.
    if anketa["normalized"].get("gimimo-data") is None:
        for field in profile.get("fields", []):
            if _source_key(str(field.get("key", ""))) == "gimimo-data" and field.get("displayValue"):
                anketa["normalized"]["gimimo-data"] = _normalize_text_value(field["displayValue"])
                break

    # An unpublished questionnaire is either VRK's "Rengiama" placeholder or
    # (one 2008 Seimo candidate) a content div with nothing in it at all —
    # no text, no table. Both are the source saying nothing, not a parse
    # failure.
    placeholder = (
        anketa_cell is None
        and content is not None
        and _tag_text(content).strip().lower() in ANKETA_PLACEHOLDER_TEXTS | {""}
    )

    return {
        "profile": profile,
        "anketa": anketa,
        "diagnostics": {
            "profileCardFound": _profile_div(soup) is not None,
            "contentDivFound": content is not None,
            "anketaTableFound": anketa_cell is not None,
            "anketaPlaceholder": placeholder,
            "placeholderText": _tag_text(content) if placeholder else "",
        },
    }


# ---------------------------------------------------------------------------
# Subpages
# ---------------------------------------------------------------------------


def _parse_biografija_html(html: str) -> dict[str, Any]:
    soup = BeautifulSoup(html, "lxml")
    content = _content_div(soup)
    return {
        "text": _tag_text(content),
        "html": str(content) if content is not None else "",
    }


def _parse_deklaracijos_html(html: str) -> dict[str, Any]:
    soup = BeautifulSoup(html, "lxml")
    content = _content_div(soup)

    sections: list[dict[str, Any]] = []
    if content is not None:
        # The two declaration extracts are partydata tables nested inside the
        # outer partydata wrapper's single cell.
        inner_tables = content.select("table.partydata table.partydata")
        for table in inner_tables:
            title = ""
            items: list[dict[str, str]] = []
            for tr in table.find_all("tr"):
                cells = tr.find_all("td")
                if not cells:
                    continue
                values = [_tag_text(cell) for cell in cells]
                if len(cells) == 1 or (len(values) > 1 and not any(values[1:])):
                    if not title:
                        title = values[0]
                    elif values[0]:
                        items.append({"key": values[0].rstrip(":"), "value": ""})
                    continue
                items.append(
                    {
                        "key": values[0].rstrip(":"),
                        "value": values[1] if len(values) > 1 else "",
                    }
                )
            sections.append({"title": title, "items": items})

    note = ""
    if content is not None:
        note_tag = content.find("p")
        if note_tag is not None:
            note = _tag_text(note_tag)

    return {
        "sections": sections,
        "note": note,
    }


def _parse_lt_amount(value: Any) -> float | None:
    normalized_value = _normalize_text_value(value)
    if normalized_value is None:
        return None

    compact = normalized_value.replace(" ", " ")
    compact = re.sub(r"\blt\b\.?", "", compact, flags=re.IGNORECASE)
    compact = compact.replace(" ", "").replace(",", ".")

    if not compact or not re.fullmatch(r"-?\d+(?:\.\d+)?", compact):
        return None

    return as_money(float(compact))


def _sum_amounts(current: float | None, amount: float | None) -> float | None:
    if amount is None:
        return current
    if current is None:
        return amount
    return as_money(round(current + amount, 2))


def _income_form_lines(item: dict[str, Any]) -> list[dict[str, Any]] | None:
    """The income lines a page states as prose rather than as labelled rows.

    "FR0462S15 Formos deklaracijos: Gauta 6900.00 Lt , išskaičiuota pajamų
    mokesčio 1035.00 Lt". The 2007 municipal pages print one such line per
    income form the tax office knew of (FR0462 and its S, S0, S15 and S33
    variants), all but the one the candidate filed at zero; thirty pages across
    the 2011 and March 2015 municipal generals print a single line the same
    way, every one of them a declared zero, which is a statement and not a
    missing declaration. Either way the declared income is the sum of the
    lines, and which form each figure came from is kept in
    `pajamos-pagal-forma`.
    """
    prose = TURTO_PAJAMU_PROSE_PATTERN.match(normalize_space(str(item.get("value") or "")))
    if prose is None:
        return None

    def figure(name: str) -> int | float | None:
        printed = prose.group(name)
        return _parse_lt_amount(f"{printed} Lt") if printed else None

    return [
        {
            "forma": section_form(item.get("key", "")),
            "gautos-pajamos": figure("income"),
            "sumoketas-pajamu-mokestis": figure("tax"),
        }
    ]


def _normalize_turto_ir_pajamu_data(payload: dict[str, Any]) -> dict[str, Any]:
    block = normalize_declaration(payload, _parse_lt_amount, form_lines=_income_form_lines)
    # Unlike every later era the amounts are litas, and the page names the
    # declaration period in its closing note; both carried explicitly so a
    # cross-era consumer cannot silently read Lt as Eur.
    block["valiuta"] = "Lt"
    block["pastaba"] = _normalize_text_value(payload.get("note"))
    return block


def _parse_interesu_html(html: str) -> dict[str, Any]:
    soup = BeautifulSoup(html, "lxml")
    content = _content_div(soup)

    sections: list[dict[str, Any]] = []
    if content is None:
        return {"sections": sections}

    for table in content.select("table.partydata"):
        title = ""
        description = ""
        headers = [_tag_text(th) for th in table.find_all("th")]
        items: list[dict[str, str]] = []
        data_rows: list[list[str]] = []

        for tr in table.find_all("tr"):
            cells = tr.find_all("td")
            if not cells:
                continue
            values = [_tag_text(cell) for cell in cells]
            if len(cells) == 1:
                # Single-cell leading rows are the section title and the form's
                # own description, in that order.
                if not title:
                    title = values[0]
                elif not description and not items and not data_rows:
                    description = values[0]
                else:
                    items.append({"key": "", "value": values[0]})
                continue
            if not headers and not items and not data_rows and _is_bold_header_row(cells):
                # The 2007 and 2008 pages publish the declaration as record
                # tables — "Tipas | Vienetų skaičius | Vietovės pavadinimas |
                # Įsigijimo būdas" under "II. Turtas" — whose column names are
                # a row of bold cells rather than <th>. Read as key/value
                # pairs, a table of two flats became one "1.0" and two
                # employers the last one; as columns and rows every record
                # keeps its cells, in the shape the 2016-era sections use.
                headers = values
                continue
            if headers:
                data_rows.append(values)
            else:
                items.append(
                    {
                        "key": values[0].rstrip(":"),
                        "value": values[1] if len(values) > 1 else "",
                    }
                )

        section: dict[str, Any] = {
            "title": title,
            "sectionId": _extract_interesu_section_id(title),
        }
        if description:
            section["description"] = description
        if headers:
            section["columns"] = headers
            section["rows"] = data_rows
        else:
            section["items"] = items
        sections.append(section)

    return {"sections": sections}


def _is_bold_header_row(cells: list[Tag]) -> bool:
    """Every cell's text is the text of a <b> inside it — the column-name
    row of the 2007/2008 record tables; no key/value row of the family is
    emphasised whole."""
    for cell in cells:
        bold = cell.find("b")
        if bold is None:
            return False
        if _tag_text(bold) != _tag_text(cell):
            return False
    return True


def _extract_interesu_section_id(title: str) -> str:
    match = re.search(r"\b(ID\d{3}[A-Z])\b", title)
    if match:
        return match.group(1).lower()
    return ""


def _parse_patiketiniai_html(html: str) -> dict[str, Any]:
    # The presidential elections publish the candidate's trustees as a
    # numbered two-column table (Numeris, Vardas, pavardė) — names only, no
    # links, no further detail.
    soup = BeautifulSoup(html, "lxml")
    content = _content_div(soup)
    records: list[dict[str, Any]] = []
    if content is None:
        return {"records": records}

    for table in content.find_all("table"):
        for tr in table.find_all("tr"):
            cells = tr.find_all("td")
            if len(cells) < 2:
                continue
            values = [_tag_text(cell) for cell in cells]
            if not values[1]:
                continue
            records.append({"number": values[0], "name": values[1]})

    return {"records": records}


def _normalize_patiketiniai_data(payload: dict[str, Any]) -> list[dict[str, Any]]:
    records = payload.get("records") if isinstance(payload.get("records"), list) else []
    normalized: list[dict[str, Any]] = []
    for record in records:
        if not isinstance(record, dict):
            continue
        number = _normalize_text_value(record.get("number"))
        normalized.append(
            {
                "numeris": int(number) if number is not None and number.isdigit() else number,
                "vardas-pavarde": _normalize_text_value(record.get("name")),
            }
        )
    return normalized


def _parse_kita_html(html: str) -> dict[str, Any]:
    soup = BeautifulSoup(html, "lxml")
    content = _content_div(soup)
    texts: list[str] = []
    if content is not None:
        for text in content.stripped_strings:
            normalized = normalize_space(text)
            if normalized:
                texts.append(normalized)
    return {
        "texts": texts,
        "links": _extract_links(content),
    }


# ---------------------------------------------------------------------------
# Campaign participant pages
# ---------------------------------------------------------------------------

CAMPAIGN_STATUS_VALUES = {
    "savarankiškas": "Savarankiškas",
    "atstovaujamas": "Atstovaujamasis",
}

CAMPAIGN_CONTACT_KEY_ALIASES = {
    "telefonas-pasiteirauti": "telefonas-pasiteirauti",
    "elektroninio-pasto-adresas": "el-pastas",
}

CAMPAIGN_PERSON_KEY_ALIASES = {
    "vardas-pavarde": "vardas-pavarde",
    "telefonas": "telefonas",
    "el-pastas": "el-pastas",
    "imones-pavadinimas": "imones-pavadinimas",
    "imones-kodas": "imones-kodas",
    # The 2009 presidential pages label a company auditor's card
    # "Pavadinimas" / "Kodas" without the "Įmonės" qualifier.
    "pavadinimas": "imones-pavadinimas",
    "kodas": "imones-kodas",
}

AUKOS_COLUMN_KEYS = {
    "eil-nr": "rowNumber",
    "aukotojas-fizinio-asmens-vardas-ir-pavarde-juridinio-asmens-pavadinimas": "donor",
    "savivaldybes-pavadinimas": "municipality",
    "data": "date",
    "aukos-suma-eur": "amountEur",
    "aukos-suma-lt": "amountLt",
    "pastabos-nepinigine-auka-auka-grynais-kita": "notes",
    # The 2009 presidential pages' shorter headings for the same columns.
    "aukotojas": "donor",
    "savivaldybe": "municipality",
    "aukos-data": "date",
}
AUKOS_AMOUNT_KEYS = ("amountEur", "amountLt")

# The 2009 donor list has no notes column and no separate "Nepriimtinos
# aukos" section: an unacceptable donation is flagged inline after the
# donor's name (", nepriimtina auka", once ", auka nepriimtina", once with
# VRK's own typo "nepriintina"). The flag is the later eras' notes column.
AUKOS_DONOR_FLAG_PATTERN = re.compile(
    r",\s*((?:nepri\w+\s+auka)|(?:auka\s+nepri\w+))\s*$", re.IGNORECASE
)

FINANSAVIMO_ATASKAITOS_COLUMN_KEYS = {
    "eil-nr": "rowNumber",
    "patvirtinimo-data": "approvedDate",
    "statusas": "status",
    "ataskaita": "reportUrls",
    "priedas-del-politines-reklamos": "advertisingAppendixUrls",
    # 2009 only: the report's kind ("Pradinė" / "Galutinė") where the later
    # pages carry the verification status.
    "ataskaitos-tipas": "reportType",
}


def _table_header_cells(table: Tag) -> tuple[list[str], Tag | None]:
    """The column headings of a listing table and the row they sit in.

    The 2012-2015 pages mark headings with <th>; the 2009 presidential pages
    write them as a first row of <td><strong> cells, so that row is returned
    too and callers skip it when walking the data rows.
    """
    headers = [_tag_text(th) for th in table.find_all("th")]
    if headers:
        return headers, None
    for tr in table.find_all("tr"):
        cells = tr.find_all("td")
        if len(cells) < 2:
            continue
        if all(cell.find("strong") is not None for cell in cells):
            return [_tag_text(cell) for cell in cells], tr
        return [], None
    return [], None


def _kv_rows_from_table(table: Tag) -> list[tuple[str, str, Tag]]:
    rows: list[tuple[str, str, Tag]] = []
    for tr in table.find_all("tr"):
        cells = tr.find_all("td")
        if len(cells) < 2:
            continue
        rows.append((_tag_text(cells[0]).rstrip(":"), _tag_text(cells[1]), cells[1]))
    return rows


def _parse_campaign_card(html: str) -> dict[str, Any]:
    # Every participant page repeats the header card: an h3 naming the
    # participant, a Statusas/Telefonas/El. paštas table, and — on represented
    # participants — a "Dalyvį atstovauja" line linking the party's own
    # participant page.
    soup = BeautifulSoup(html, "lxml")
    card: dict[str, Any] = {
        "title": "",
        "statusas": "",
        "kontaktai": {},
        "atstovauja": None,
    }

    picklist = soup.select_one("div.picklist")
    if picklist is None:
        return card

    card["title"] = _tag_text(picklist.find("h3"))

    table = picklist.find("table")
    if table is not None:
        for key_text, value_text, _ in _kv_rows_from_table(table):
            key = _source_key(key_text)
            if key == "statusas":
                raw_status = str(_normalize_text_value(value_text) or "")
                card["statusas"] = CAMPAIGN_STATUS_VALUES.get(
                    raw_status.lower(), raw_status.capitalize() if raw_status else ""
                )
                continue
            alias = CAMPAIGN_CONTACT_KEY_ALIASES.get(key)
            if alias is not None:
                card["kontaktai"][alias] = _normalize_text_value(value_text)

    picklist_text = _tag_text(picklist)
    if "Dalyvį atstovauja" in picklist_text:
        for anchor in picklist.find_all("a", href=True):
            if "Dalyvi" in anchor["href"]:
                card["atstovauja"] = {
                    "pavadinimas": _tag_text(anchor),
                    "nuoroda": resolve_candidate_url(normalize_space(anchor["href"])),
                }
                break

    return card


def _parse_campaign_person_html(html: str) -> dict[str, Any]:
    # The iždininkas and auditorius tabs share one shape: a partydata table
    # whose first row is the section heading and the rest key/value pairs.
    # The auditorius page adds a second table listing the auditor's reports.
    soup = BeautifulSoup(html, "lxml")
    person: dict[str, Any] = {key: None for key in CAMPAIGN_PERSON_KEY_ALIASES.values()}
    reports: list[dict[str, Any]] = []

    tabnav = soup.select_one("ul#tabnav")
    if tabnav is None:
        return {"person": person, "reports": reports}

    for table in tabnav.find_all_next("table"):
        kv_rows = _kv_rows_from_table(table)
        has_report_rows = any(
            len(tr.find_all("td")) >= 4 for tr in table.find_all("tr")
        )
        if has_report_rows:
            for tr in table.find_all("tr"):
                cells = tr.find_all("td")
                if len(cells) < 4:
                    continue
                values = [_tag_text(cell) for cell in cells]
                urls: list[str] = []
                for cell in cells:
                    urls.extend(_extract_links(cell))
                reports.append(
                    {
                        "rowNumber": _normalize_text_value(values[0]),
                        "date": _normalize_text_value(values[1]),
                        "status": _normalize_text_value(values[2]),
                        "type": _normalize_text_value(values[3]),
                        "urls": urls,
                    }
                )
            continue
        for key_text, value_text, _ in _kv_rows_from_table(table):
            alias = CAMPAIGN_PERSON_KEY_ALIASES.get(_source_key(key_text))
            if alias is not None:
                person[alias] = _normalize_text_value(value_text)
        if kv_rows:
            continue

    return {"person": person, "reports": reports}


def _parse_aukos_html(html: str) -> dict[str, Any]:
    # Donation sections are h3 headings followed by a headed table, all
    # inside the picklist div after the tab navigation.
    soup = BeautifulSoup(html, "lxml")
    sections: list[dict[str, Any]] = []

    tabnav = soup.select_one("ul#tabnav")
    if tabnav is None:
        return {"sections": sections}

    for table in tabnav.find_all_next("table"):
        headers, header_row = _table_header_cells(table)
        if not headers:
            continue
        heading = table.find_previous("h3")
        title = _tag_text(heading).rstrip(":")

        header_keys: list[str] = []
        for index, header in enumerate(headers):
            header_key = _source_key(header)
            # The notes column's parenthetical varies per section
            # ("Nepiniginė auka…" vs "grąžinta aukotojui…"); either way it
            # is the notes column.
            if header_key.startswith("pastabos"):
                header_key = "pastabos-nepinigine-auka-auka-grynais-kita"
            header_keys.append(AUKOS_COLUMN_KEYS.get(header_key) or header_key or f"stulpelis-{index + 1}")
        # The totals block names one amount per amount column, in the
        # header's order — Lt only (2009-2014), Eur and Lt (March 2015) or
        # Eur only (the later 2015 elections) — so the sums are keyed by the
        # header, not by position.
        amount_keys = [key for key in header_keys if key in AUKOS_AMOUNT_KEYS]
        has_notes_column = "notes" in header_keys

        records: list[dict[str, Any]] = []
        summary: list[dict[str, Any]] = []
        for tr in table.find_all("tr"):
            if tr is header_row:
                continue
            cells = tr.find_all("td")
            if not cells:
                continue
            values = [_tag_text(cell) for cell in cells]
            # The 2009 totals row keeps the full cell count, with the label
            # in an inner cell and no row number.
            full_width_total = (
                len(cells) == len(headers)
                and not values[0].strip()
                and any(value.rstrip().endswith(":") for value in values)
            )
            if len(cells) < len(headers) or full_width_total:
                # The totals block under the donations: a colspan label, the
                # sums, and an occasional note ("juridinių asmenų aukos — Nuo
                # 2012-01-01 draudžiamos").
                if full_width_total:
                    label_index = next(
                        index for index, value in enumerate(values) if value.rstrip().endswith(":")
                    )
                    values = [values[label_index]] + [
                        value for value in values[label_index + 1 :] if value.strip()
                    ]
                entry: dict[str, Any] = {
                    "label": _normalize_text_value(values[0].rstrip(":")) if values else None,
                    "amountEur": None,
                    "amountLt": None,
                    "note": None,
                }
                for offset, key in enumerate(amount_keys, start=1):
                    if offset < len(values):
                        entry[key] = _parse_lt_amount(values[offset])
                note_index = 1 + len(amount_keys)
                if note_index < len(values):
                    entry["note"] = _normalize_text_value(values[note_index])
                if entry["label"] is not None:
                    summary.append(entry)
                continue
            record: dict[str, Any] = {}
            for index, cell in enumerate(cells):
                key = header_keys[index] if index < len(header_keys) else f"stulpelis-{index + 1}"
                value = _normalize_text_value(_tag_text(cell))
                if key in AUKOS_AMOUNT_KEYS:
                    record[key] = _parse_lt_amount(value)
                else:
                    record[key] = value
            if not has_notes_column and record.get("donor"):
                flag = AUKOS_DONOR_FLAG_PATTERN.search(record["donor"])
                if flag is not None:
                    record["donor"] = record["donor"][: flag.start()].strip()
                    record["notes"] = flag.group(1)
            if any(value is not None for value in record.values()):
                records.append(record)

        sections.append({"title": title, "records": records, "summary": summary})

    return {"sections": sections}


def _parse_finansavimo_ataskaitos_html(html: str) -> list[dict[str, Any]]:
    soup = BeautifulSoup(html, "lxml")
    entries: list[dict[str, Any]] = []

    tabnav = soup.select_one("ul#tabnav")
    if tabnav is None:
        return entries

    for table in tabnav.find_all_next("table"):
        headers, header_row = _table_header_cells(table)
        if not headers:
            continue
        column_keys = [
            FINANSAVIMO_ATASKAITOS_COLUMN_KEYS.get(_source_key(header), "") for header in headers
        ]
        for tr in table.find_all("tr"):
            if tr is header_row:
                continue
            cells = tr.find_all("td")
            if len(cells) < 4:
                continue
            values = [_tag_text(cell) for cell in cells]
            entry: dict[str, Any] = {
                "rowNumber": None,
                "approvedDate": None,
                "status": None,
                "reportUrls": [],
                "advertisingAppendixUrls": [],
            }
            for index, cell in enumerate(cells):
                key = column_keys[index] if index < len(column_keys) else ""
                if key in ("reportUrls", "advertisingAppendixUrls"):
                    entry[key] = _extract_links(cell)
                elif key:
                    entry[key] = _normalize_text_value(values[index])
            entries.append(entry)

    return entries


def _parse_sutartys_html(html: str) -> list[dict[str, Any]]:
    soup = BeautifulSoup(html, "lxml")
    entries: list[dict[str, Any]] = []

    tabnav = soup.select_one("ul#tabnav")
    if tabnav is None:
        return entries

    for table in tabnav.find_all_next("table"):
        if not table.find_all("th"):
            continue
        for tr in table.find_all("tr"):
            cells = tr.find_all("td")
            if len(cells) < 5:
                continue
            values = [_tag_text(cell) for cell in cells]
            entries.append(
                {
                    "rowNumber": _normalize_text_value(values[0]),
                    "counterparty": _normalize_text_value(values[1]),
                    "agreementDate": _normalize_text_value(values[2]),
                    "agreementNumber": _normalize_text_value(values[3]),
                    "subject": _normalize_text_value(values[4]),
                    "textAccessNote": _normalize_text_value(values[5]) if len(values) > 5 else None,
                    "textUrls": _extract_links(cells[5]) if len(cells) > 5 else [],
                }
            )

    return entries


def _parse_campaign_sample(
    campaign_meta: dict[str, Any],
    candidate_dir: Path,
) -> dict[str, Any] | None:
    campaign_key = str(campaign_meta.get("campaignKey", ""))
    campaign_dir = candidate_dir / "campaigns" / campaign_key
    if not campaign_dir.exists():
        return None

    tab_files = {
        str(tab.get("slug", "")): campaign_dir / f"{tab.get('slug', '')}.html"
        for tab in campaign_meta.get("tabSamples", [])
        if isinstance(tab, dict) and tab.get("slug")
    }

    # Independent participants carry the header card on every tab; represented
    # participants have only the card, saved as root.html.
    card_path = tab_files.get("izdininkas", campaign_dir / "root.html")
    if not card_path.exists():
        card_path = campaign_dir / "root.html"
    if not card_path.exists():
        return None

    card = _parse_campaign_card(card_path.read_text(encoding="utf-8"))

    raw: dict[str, Any] = {
        "campaignKey": campaign_key,
        "campaignLabel": str(campaign_meta.get("campaignLabel", "")),
        "campaignUrl": str(campaign_meta.get("campaignUrl", "")),
        "card": card,
    }

    entry: dict[str, Any] = {
        "statusas": _normalize_text_value(card.get("statusas")),
        # The 2015 participant pages publish neither a registration date nor a
        # decision number.
        "registravimo-data": None,
        "sprendimo-numeris": None,
        "kontaktai": card.get("kontaktai", {}),
        "izdininkas": {},
        "auditorius": {},
        "aukos-pagal-sekcija": {},
        "finansavimo-ataskaitos": [],
        "sutartys": [],
        "sprendimai": [],
    }
    if card.get("atstovauja"):
        entry["atstovauja"] = card["atstovauja"]

    izdininkas_path = tab_files.get("izdininkas")
    if izdininkas_path is not None and izdininkas_path.exists():
        parsed = _parse_campaign_person_html(izdininkas_path.read_text(encoding="utf-8"))
        raw["izdininkas"] = parsed
        entry["izdininkas"] = parsed["person"]

    auditorius_path = tab_files.get("auditorius")
    if auditorius_path is not None and auditorius_path.exists():
        parsed = _parse_campaign_person_html(auditorius_path.read_text(encoding="utf-8"))
        raw["auditorius"] = parsed
        entry["auditorius"] = dict(parsed["person"])
        if parsed["reports"]:
            entry["auditorius"]["ataskaitos"] = parsed["reports"]

    # "Aukų ir aukotojų sąrašas" from 2012 on; the 2009 tab is titled just
    # "Aukotojų sąrašas".
    aukos_path = tab_files.get("auku-ir-aukotoju-sarasas") or tab_files.get("aukotoju-sarasas")
    if aukos_path is not None and aukos_path.exists():
        parsed = _parse_aukos_html(aukos_path.read_text(encoding="utf-8"))
        raw["aukos"] = parsed
        by_section: dict[str, Any] = {}
        for section in parsed["sections"]:
            section_key = _source_key(str(section.get("title", "")))
            if not section_key:
                section_key = f"sekcija-{len(by_section) + 1}"
            by_section[section_key] = {
                "title": _normalize_text_value(section.get("title")),
                "records": section.get("records", []),
                "suvestine": section.get("summary", []),
            }
        entry["aukos-pagal-sekcija"] = by_section

    ataskaitos_path = tab_files.get("finansavimo-ataskaitos")
    if ataskaitos_path is not None and ataskaitos_path.exists():
        parsed_reports = _parse_finansavimo_ataskaitos_html(
            ataskaitos_path.read_text(encoding="utf-8")
        )
        raw["finansavimoAtaskaitos"] = parsed_reports
        entry["finansavimo-ataskaitos"] = parsed_reports

    sutartys_path = tab_files.get("sutartys")
    if sutartys_path is not None and sutartys_path.exists():
        parsed_contracts = _parse_sutartys_html(sutartys_path.read_text(encoding="utf-8"))
        raw["sutartys"] = parsed_contracts
        entry["sutartys"] = parsed_contracts

    return {"raw": raw, "entry": entry}


def _parse_campaign_samples(
    meta: dict[str, Any],
    candidate_dir: Path,
    candidate_id: str,
    source_url: str | None,
    anomalies: list[dict[str, Any]],
    election_id: str,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    raw_campaigns: list[dict[str, Any]] = []
    entries: list[dict[str, Any]] = []

    campaign_samples = meta.get("campaignSamples")
    if not isinstance(campaign_samples, list):
        return raw_campaigns, entries

    for campaign_meta in campaign_samples:
        if not isinstance(campaign_meta, dict):
            continue
        try:
            parsed = _parse_campaign_sample(campaign_meta, candidate_dir)
        except Exception as exc:
            anomalies.append(
                build_anomaly_event(
                    event_type="CampaignParseError",
                    severity="error",
                    stage="parse",
                    election_id=election_id,
                    candidate_id=candidate_id,
                    source_url=source_url,
                    detail={
                        "campaignKey": str(campaign_meta.get("campaignKey", "")),
                        "error": str(exc),
                    },
                )
            )
            continue
        if parsed is None:
            # The candidate page linked a campaign whose root page never
            # fetched (the fetch stage recorded a CampaignRootFetchFailed in
            # index.json — a dead link on VRK's side, such as the 2009 EP
            # candidate pages that link a presidential campaign's participant
            # id under the EP path). Without this the campaign would vanish
            # from the record and from anomalies.jsonl alike.
            anomalies.append(
                build_anomaly_event(
                    event_type="CampaignRootMissing",
                    severity="warning",
                    stage="parse",
                    election_id=election_id,
                    candidate_id=candidate_id,
                    source_url=source_url,
                    detail={
                        "campaignKey": str(campaign_meta.get("campaignKey", "")),
                        "campaignUrl": str(campaign_meta.get("campaignUrl", "")),
                    },
                )
            )
            continue
        raw_campaigns.append(parsed["raw"])
        entries.append(parsed["entry"])

    return raw_campaigns, entries


def _parse_optional_subpages(
    candidate_dir: Path,
    candidate_id: str,
    candidate_source_url: str | None,
    anomalies: list[dict[str, Any]],
    election_id: str,
) -> dict[str, Any]:
    pages: dict[str, Any] = {}
    parser_map: dict[str, Any] = {
        "biografija": ("biografija.html", _parse_biografija_html),
        "turtoIrPajamuDeklaracijos": ("turto-ir-pajamu-deklaracijos.html", _parse_deklaracijos_html),
        # The 2015 tab is titled just "Interesų deklaracija"; the record keeps
        # the corpus-wide "privačių interesų" name because the content is the
        # same ID001x form.
        "privaciuInteresuDeklaracija": ("interesu-deklaracija.html", _parse_interesu_html),
        # Presidential elections only; the file does not exist for any other
        # election's candidates, so the key is simply absent there.
        "patiketiniai": ("patiketiniai.html", _parse_patiketiniai_html),
        "kita": ("kita.html", _parse_kita_html),
    }

    for key, (filename, parser) in parser_map.items():
        path = candidate_dir / filename
        if not path.exists():
            continue
        html = path.read_text(encoding="utf-8")
        try:
            parsed_data = parser(html)
        except Exception as exc:
            anomalies.append(
                build_anomaly_event(
                    event_type="SubpageParseError",
                    severity="error",
                    stage="parse",
                    election_id=election_id,
                    candidate_id=candidate_id,
                    source_url=candidate_source_url,
                    detail={
                        "subpage": key,
                        "sourcePath": str(path),
                        "error": str(exc),
                    },
                )
            )
            continue

        pages[key] = {"data": parsed_data}

    return pages


def _load_candidate_meta(candidate_dir: Path) -> dict[str, Any]:
    index_path = candidate_dir / "index.json"
    if not index_path.exists():
        return {}
    try:
        payload = json.loads(index_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


# ---------------------------------------------------------------------------
# Top-level parse
# ---------------------------------------------------------------------------


def parse_anketa_sample(
    candidate_id: str,
    samples_root: Path = DEFAULT_SAMPLES_ROOT,
    output_root: Path = DEFAULT_OUTPUT_ROOT,
    election_id: str = ELECTION_ID,
    rows_normalizer: Any = None,
    candidacy_builder: Any = None,
    results_lookup: dict[str, dict[str, Any]] | None = None,
) -> tuple[Path, dict[str, Any]]:
    if results_lookup is None and election_id == ELECTION_ID:
        results_lookup = load_results_lookup(DEFAULT_RESULTS_PATH)
    candidate_dir = samples_root / candidate_id
    anketa_path = candidate_dir / "anketa.html"
    if not anketa_path.exists():
        raise FileNotFoundError(errno.ENOENT, "Missing anketa sample", str(anketa_path))

    html = anketa_path.read_text(encoding="utf-8")
    parsed = parse_anketa_html(html, rows_normalizer=rows_normalizer)
    meta = _load_candidate_meta(candidate_dir)
    candidate_meta = meta.get("candidate", {}) if isinstance(meta, dict) else {}
    candidate_source_url = candidate_meta.get("url") if isinstance(candidate_meta, dict) else None

    anomalies: list[dict[str, Any]] = []
    diagnostics = parsed.get("diagnostics", {})
    if not diagnostics.get("profileCardFound", False):
        anomalies.append(
            build_anomaly_event(
                event_type="ProfileCardMissing",
                severity="error",
                stage="parse",
                election_id=election_id,
                candidate_id=candidate_id,
                source_url=candidate_source_url,
            )
        )
    anketa_placeholder = bool(diagnostics.get("anketaPlaceholder", False))
    if anketa_placeholder:
        # An unpublished questionnaire is upstream data, not a parse failure;
        # recording it as one would hide it among real breakage.
        anomalies.append(
            build_anomaly_event(
                event_type="AnketaNotPublished",
                severity="warning",
                stage="parse",
                election_id=election_id,
                candidate_id=candidate_id,
                source_url=candidate_source_url,
                detail={"placeholderText": diagnostics.get("placeholderText", "")},
            )
        )
    elif not diagnostics.get("anketaTableFound", False):
        anomalies.append(
            build_anomaly_event(
                event_type="AnketaTableNotFound",
                severity="critical",
                stage="parse",
                election_id=election_id,
                candidate_id=candidate_id,
                source_url=candidate_source_url,
            )
        )

    anketa_stats = parsed["anketa"]["stats"]
    if anketa_stats["rowCount"] == 0 and not anketa_placeholder:
        anomalies.append(
            build_anomaly_event(
                event_type="AnketaTableEmpty",
                severity="error",
                stage="parse",
                election_id=election_id,
                candidate_id=candidate_id,
                source_url=candidate_source_url,
            )
        )

    subpages = _parse_optional_subpages(
        candidate_dir=candidate_dir,
        candidate_id=candidate_id,
        candidate_source_url=candidate_source_url,
        anomalies=anomalies,
        election_id=election_id,
    )

    raw_campaigns, campaign_entries = _parse_campaign_samples(
        meta=meta if isinstance(meta, dict) else {},
        candidate_dir=candidate_dir,
        candidate_id=candidate_id,
        source_url=candidate_source_url,
        anomalies=anomalies,
        election_id=election_id,
    )

    candidate_name = ""
    if isinstance(candidate_meta, dict):
        candidate_name = str(candidate_meta.get("candidateName", "")).strip()
    if not candidate_name:
        candidate_name = parsed["profile"].get("candidateDisplayName", "")

    raw_data: dict[str, Any] = {
        "profile": parsed["profile"],
        "anketa": {
            "rows": parsed["anketa"]["rows"],
        },
    }

    normalized: dict[str, Any] = {
        "profilis": _normalize_profile_data(parsed["profile"]),
        "anketa": parsed["anketa"]["normalized"],
    }

    for key, payload in subpages.items():
        if not isinstance(payload, dict):
            continue
        data = payload.get("data")
        if data is None:
            continue
        raw_data[key] = data
        if key == "biografija" and isinstance(data, dict):
            normalized["biografija"] = _normalize_biografija_data(data)
        if key == "turtoIrPajamuDeklaracijos" and isinstance(data, dict):
            normalized["turto-ir-pajamu-deklaracijos"] = _normalize_turto_ir_pajamu_data(data)
        if key == "privaciuInteresuDeklaracija" and isinstance(data, dict):
            normalized["privaciu-interesu-deklaracija"] = _normalize_privaciu_interesu_data(data)
        if key == "patiketiniai" and isinstance(data, dict):
            normalized["patiketiniai"] = _normalize_patiketiniai_data(data)
        if key == "kita" and isinstance(data, dict):
            normalized["kita"] = _normalize_kita_data(data)

    if raw_campaigns:
        raw_data["politinesKampanijosDalyvioDuomenys"] = {"campaigns": raw_campaigns}
    if campaign_entries:
        normalized["politines-kampanijos-dalyvio-duomenys"] = campaign_entries

    raw_data = _order_dict_keys(
        raw_data,
        [
            "profile",
            "anketa",
            "biografija",
            "turtoIrPajamuDeklaracijos",
            "privaciuInteresuDeklaracija",
            "patiketiniai",
            "politinesKampanijosDalyvioDuomenys",
            "kita",
        ],
    )
    normalized = _order_dict_keys(
        normalized,
        [
            "profilis",
            "anketa",
            "biografija",
            "turto-ir-pajamu-deklaracijos",
            "privaciu-interesu-deklaracija",
            "patiketiniai",
            "politines-kampanijos-dalyvio-duomenys",
            "kita",
        ],
    )

    output_payload: dict[str, Any] = {
        "electionId": election_id,
        "candidateId": candidate_id,
        "candidateName": candidate_name,
    }
    if candidacy_builder is not None:
        # Elections published through two listing structures carry facts that
        # appear on no candidate page — which municipality, which list, which
        # seat order, which roles.
        output_payload["kandidatavimas"] = candidacy_builder(
            candidate_meta if isinstance(candidate_meta, dict) else {}
        )
    if results_lookup is not None:
        # No page of this family marks a winner; electedness is joined in from
        # VRK's results tree (scraper/shared/election_results.py) on the VRK
        # candidate id. With a results file the flag is a real true/false;
        # without one it stays null, as unknown.
        _apply_results(output_payload, candidate_meta if isinstance(candidate_meta, dict) else {}, candidate_source_url, results_lookup)
    output_payload |= {
        "source": {
            "candidateSourceUrl": candidate_source_url,
        },
        "rawData": raw_data,
        "normalized": _normalize_missing_values(normalized),
    }

    output_path = output_root / f"{candidate_id}-{election_id}.json"
    write_candidate_record(output_path, output_payload)

    stats = {
        "candidateId": candidate_id,
        "candidateName": candidate_name,
        "outputPath": str(output_path),
        "rowCount": anketa_stats["rowCount"],
        "answeredRowCount": anketa_stats["answeredRowCount"],
        "anomalies": anomalies,
    }
    return output_path, stats


def _vrk_candidate_id(candidate_meta: dict[str, Any], candidate_source_url: str | None) -> str | None:
    vrk_id = str(candidate_meta.get("vrkCandidateId", "") or "").strip()
    if vrk_id:
        return vrk_id
    match = ANKETA_ID_PATTERN.search(candidate_source_url or "")
    return match.group(1) if match else None


def _apply_results(
    output_payload: dict[str, Any],
    candidate_meta: dict[str, Any],
    candidate_source_url: str | None,
    results_lookup: dict[str, dict[str, Any]],
) -> None:
    vrk_id = _vrk_candidate_id(candidate_meta, candidate_source_url)
    candidacy = output_payload.get("kandidatavimas")
    if not isinstance(candidacy, dict):
        candidacy = {"vrkCandidateId": vrk_id}
        output_payload["kandidatavimas"] = candidacy
    hit = results_lookup.get(vrk_id) if vrk_id else None
    if hit is None:
        candidacy["isrinktas"] = False
        return
    annulled = hit.get("annulled")
    candidacy["isrinktas"] = not annulled
    candidacy["isrinktasKaip"] = hit.get("seat")
    candidacy["rezultatuSaltinis"] = hit.get("sourceUrl")
    if hit.get("round"):
        candidacy["rezultatuTuras"] = hit["round"]
    if annulled:
        # The results page named this candidate; VRK then declared those
        # results void. Recorded so the record says both things.
        candidacy["rezultataiPanaikinti"] = annulled


def load_results(results_path: Path | None) -> dict[str, dict[str, Any]] | None:
    return load_results_lookup(results_path)


def parse_anketa_samples(
    candidate_ids: list[str] | None,
    samples_root: Path = DEFAULT_SAMPLES_ROOT,
    output_root: Path = DEFAULT_OUTPUT_ROOT,
    election_id: str = ELECTION_ID,
    rows_normalizer: Any = None,
    candidacy_builder: Any = None,
    results_lookup: dict[str, dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    if candidate_ids:
        target_ids = candidate_ids
    else:
        target_ids = []
        for child in sorted(samples_root.iterdir()):
            if not child.is_dir():
                continue
            if (child / "anketa.html").exists():
                target_ids.append(child.name)

    results: list[dict[str, Any]] = []
    for candidate_id in target_ids:
        _, stats = parse_anketa_sample(
            candidate_id=candidate_id,
            samples_root=samples_root,
            output_root=output_root,
            election_id=election_id,
            rows_normalizer=rows_normalizer,
            candidacy_builder=candidacy_builder,
            results_lookup=results_lookup,
        )
        results.append(stats)

    return results
