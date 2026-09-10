from __future__ import annotations

import errno
from pathlib import Path
import re
from typing import Any

from bs4 import BeautifulSoup, Tag

from scraper.elections.ep_2019.sitemap import ELECTION_ID
from scraper.elections.seimo_2016.anketa_parser import (
    _extract_answer_text,
    _extract_links,
    _extract_table_headers,
    _find_main_content_after_tabnav,
    _find_row_by_question_number,
    _question_record_rows,
    _load_candidate_meta,
    _normalize_biografija_data,
    _normalize_campaigns,
    _normalize_kita_data,
    _normalize_missing_values,
    _normalize_privaciu_interesu_data,
    _normalize_profile_data,
    _normalize_table_records,
    _normalize_text_value,
    _order_dict_keys,
    _parse_biografija_html,
    _parse_eur_amount,
    _parse_kita_html,
    _parse_nested_campaign_samples,
    _parse_politines_kampanijos_html,
    _parse_tabnav,
    _parse_turto_ir_pajamu_html,
    _row_answer_text,
    _source_key,
    _tag_text,
    normalize_space,
)
from scraper.shared.anketa_cells import prompt_text as _build_prompt_text
from scraper.shared.anomalies import build_anomaly_event
from scraper.shared.election_results import candidacy_from_elected_note
from scraper.shared.conviction_details import conviction_field_keys, conviction_records
from scraper.shared.deklaracijos import normalize_declaration
from scraper.shared.files import write_candidate_record, write_json

DEFAULT_SAMPLES_ROOT = Path("samples/html/2019-ep")
DEFAULT_OUTPUT_ROOT = Path("data/2019-ep")

# Q9.2 is the conviction question here too, and its detail table is the one the
# 2019-era row loop used to drop entirely (see `_parse_anketa_content`). These
# pages slugify the column headings before printing them
# ("9-2-1-apkaltinamojo-nuosprendzio-sprendimo-data"), which the sub-question
# prefix match handles as it does the spelled-out headings elsewhere.
CONVICTION_QUESTION = "9.2"

# The declaration rows, and the four things a section heading says about an
# extract — its scope, its year, its form and its figures — are one shared
# reading for every era; see scraper/shared/deklaracijos.py.


# ---------------------------------------------------------------------------
# Profile
# ---------------------------------------------------------------------------


def _parse_profile_table(table: Tag | None) -> dict[str, Any]:
    if table is None:
        return {
            "candidateDisplayName": "",
            "electedNote": "",
            "photoSrc": "",
            "fields": [],
        }

    rows = table.find_all("tr")
    candidate_display_name = ""
    elected_note = ""
    photo_src = ""
    fields: list[dict[str, Any]] = []

    if rows:
        first_cells = rows[0].find_all("td", recursive=False)
        for cell in first_cells:
            img = cell.find("img")
            if img is not None and not photo_src:
                photo_src = normalize_space(img.get("src", ""))
        # The candidate name lives in the last cell of the first row, usually
        # wrapped in <strong>.
        if first_cells:
            name_cell = first_cells[-1]
            if name_cell.find("img") is None:
                candidate_display_name = _tag_text(name_cell)

    for row in rows[1:]:
        cells = row.find_all("td", recursive=False)
        if not cells:
            continue

        # A single-cell row spanning the table width is either the "elected"
        # note (only present for elected MEPs) or a stray spacer row.
        if len(cells) == 1:
            text = _tag_text(cells[0])
            if text and "išrink" in text.lower() and not elected_note:
                elected_note = text
            continue

        key_cell = cells[0]
        value_cell = cells[-1]

        key_text = _tag_text(key_cell).rstrip(":")
        value_text = _tag_text(value_cell)
        if not key_text and not value_text:
            continue

        # An extra nominator is rendered as a row with an empty label cell; it
        # belongs to the field above it (see the 2016 profile parser).
        if not key_text and fields:
            previous = fields[-1]
            previous["displayValue"] = "; ".join(
                part for part in (previous["displayValue"], value_text) if part
            )
            previous["urls"] = previous["urls"] + [
                url for url in _extract_links(value_cell) if url not in previous["urls"]
            ]
            continue

        fields.append(
            {
                "key": key_text,
                "displayValue": value_text,
                "urls": _extract_links(value_cell),
            }
        )

    return {
        "candidateDisplayName": candidate_display_name,
        "electedNote": elected_note,
        "photoSrc": photo_src,
        "fields": fields,
    }


def parse_office_heading(soup: BeautifulSoup) -> str:
    """The office line above the profile card — "Kandidatas į Seimo narius
    (dokumentai pateikti 2024-07-16)", "Kandidatė į savivaldybės tarybos
    narius ir merus" — printed as the page's only <h4 class="h4apgKom">
    on the 2017-2025 layouts (the 2016 and 2020 Seimo pages have none).
    It is the one place the page says which office the candidate seeks
    and, on the 2024 Seimo pages, when the documents were submitted."""
    heading = soup.find("h4", class_="h4apgKom")
    return _tag_text(heading) if heading is not None else ""


def _select_profile_table(soup: BeautifulSoup, tabnav: Tag | None) -> Tag | None:
    if tabnav is None:
        return soup.find("table")

    # The candidate profile is the first table on the page; the tab navigation
    # is wrapped in a layout table (id="meniuTable") which must be skipped.
    return tabnav.find_previous(
        lambda node: isinstance(node, Tag)
        and node.name == "table"
        and node.get("id") != "meniuTable"
    )


# ---------------------------------------------------------------------------
# Anketa body (split across sibling tables)
# ---------------------------------------------------------------------------


def _parse_question_number(text: str) -> str | None:
    # EP prompts number top-level and 8.x questions with a trailing dot
    # ("5. ", "8.1. ") but write 9.x / 12.x sub-questions without one
    # ("9.1 ", "12.2 "). Accept both so sub-question answers are not lost.
    match = re.match(r"^\s*(\d+(?:\.\d+)*)\.?(?=\s|$)", text)
    if not match:
        return None
    return match.group(1)


def _is_records_table(table: Tag) -> bool:
    classes = table.get("class") or []
    if "tableKand" in classes:
        return True
    # find() searches descendants, so a header belonging to a *nested* table
    # used to count. VRK renders the conviction-detail table inside the anketa
    # table for anyone who answers the conviction question "Taip", which made
    # the whole anketa look like a records table: every question from birth
    # date to nationality, and every declaration, was dropped without an
    # anomaly. Only headers owned by this table decide.
    return any(th.find_parent("table") is table for th in table.find_all("th"))


def _parse_records_table(table: Tag) -> list[dict[str, Any]]:
    headers = _extract_table_headers(table)
    records: list[dict[str, Any]] = []

    body = table.find("tbody", recursive=False)
    tr_nodes = body.find_all("tr", recursive=False) if body is not None else table.find_all("tr")

    for tr in tr_nodes:
        cells = tr.find_all("td", recursive=False)
        if not cells:
            continue
        values = [_tag_text(cell) for cell in cells]
        if not any(values):
            continue

        if headers and len(values) == len(headers):
            record: dict[str, Any] = {}
            for index, value in enumerate(values):
                key = _source_key(headers[index]) or f"stulpelis-{index + 1}"
                record[key] = value
            records.append(record)
        else:
            records.append({f"stulpelis-{index + 1}": value for index, value in enumerate(values)})

    return records


def _parse_anketa_content(content: Tag | None) -> dict[str, Any]:
    parsed_rows: list[dict[str, Any]] = []

    if content is None:
        return {
            "rows": parsed_rows,
            "normalized": _normalize_anketa_rows(parsed_rows),
            "stats": {"rowCount": 0, "answeredRowCount": 0},
        }

    for table in content.find_all("table", recursive=False):
        if _is_records_table(table):
            records = _parse_records_table(table)
            if parsed_rows and not parsed_rows[-1]["answer"]:
                # Attach the standalone records table to the heading row that
                # immediately precedes it (e.g. "12. Išsilavinimas:").
                parsed_rows[-1]["answer"] = records
            else:
                parsed_rows.append(
                    {
                        "rowIndex": len(parsed_rows) + 1,
                        "questionNumber": "",
                        "prompt": "",
                        "answer": records,
                    }
                )
            continue

        body = table.find("tbody", recursive=False)
        tr_nodes = body.find_all("tr", recursive=False) if body is not None else table.find_all("tr", recursive=False)
        for tr in tr_nodes:
            cell = tr.find("td", recursive=False)
            if cell is None:
                continue
            nested_tables = cell.find_all("table")
            prompt = _build_prompt_text(cell)
            if nested_tables:
                # VRK renders the conviction-detail table in a row of its own,
                # nested inside that row's cell. Its cells carry no <b> text,
                # so the bold-only extraction read nothing and the empty-row
                # skip below dropped the row — the conviction details never
                # reached rawData.
                answer: Any = _parse_records_table(nested_tables[0])
            else:
                answer = _extract_answer_text(cell, nested_tables)
            if not prompt and not answer:
                continue
            parsed_rows.append(
                {
                    "rowIndex": len(parsed_rows) + 1,
                    "questionNumber": _parse_question_number(prompt),
                    "prompt": prompt,
                    "answer": answer,
                }
            )

    answered_count = sum(1 for row in parsed_rows if row.get("answer"))
    return {
        "rows": parsed_rows,
        "normalized": _normalize_anketa_rows(parsed_rows),
        "stats": {
            "rowCount": len(parsed_rows),
            "answeredRowCount": answered_count,
        },
    }


def _split_marital_and_spouse(answer: str | None) -> tuple[str | None, str | None]:
    if not isinstance(answer, str):
        return None, None
    parts = [part.strip() for part in answer.split("|")]
    parts = [part for part in parts if part]
    marital = parts[0] if parts else None
    spouse = parts[1] if len(parts) > 1 else None
    return _normalize_text_value(marital), _normalize_text_value(spouse)


def _normalize_anketa_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    q5 = _find_row_by_question_number(rows, "5")
    q6 = _find_row_by_question_number(rows, "6")
    q8_1 = _find_row_by_question_number(rows, "8.1")
    q8_2 = _find_row_by_question_number(rows, "8.2")
    q8_3 = _find_row_by_question_number(rows, "8.3")
    q9_1 = _find_row_by_question_number(rows, "9.1")
    q9_2 = _find_row_by_question_number(rows, "9.2")
    q9_3 = _find_row_by_question_number(rows, "9.3")
    q9_4 = _find_row_by_question_number(rows, "9.4")
    q9_5 = _find_row_by_question_number(rows, "9.5")
    q10 = _find_row_by_question_number(rows, "10")
    q11 = _find_row_by_question_number(rows, "11")
    q12 = _find_row_by_question_number(rows, "12")
    q12_1 = _find_row_by_question_number(rows, "12.1")
    q12_2 = _find_row_by_question_number(rows, "12.2")
    q13 = _find_row_by_question_number(rows, "13")
    q14 = _find_row_by_question_number(rows, "14")
    q15 = _find_row_by_question_number(rows, "15")
    q16 = _find_row_by_question_number(rows, "16")
    q17 = _find_row_by_question_number(rows, "17")
    q18 = _find_row_by_question_number(rows, "18")
    q19 = _find_row_by_question_number(rows, "19")
    q20 = _find_row_by_question_number(rows, "20")
    q21 = _find_row_by_question_number(rows, "21")

    marital_status, spouse_name = _split_marital_and_spouse(_row_answer_text(q19))

    return {
        "gimimo-data": _normalize_text_value(_row_answer_text(q5)),
        "adresas": _normalize_text_value(_row_answer_text(q6)),
        "pareiskimai": {
            "ar-nebaigta-teismo-paskirta-bausme": _normalize_text_value(_row_answer_text(q8_1)),
            "ar-atliekate-karo-tarnyba": _normalize_text_value(_row_answer_text(q8_2)),
            "ar-turite-kitos-valstybes-pilietybe": _normalize_text_value(_row_answer_text(q8_3)),
            "ar-bendradarbiavote-su-uzsienio-tarnybomis": _normalize_text_value(_row_answer_text(q9_1)),
            "ar-buvote-pripazintas-kaltu": _normalize_text_value(_row_answer_text(q9_2)),
            "ar-veika-dekriminalizuota": _normalize_text_value(_row_answer_text(q9_3)),
            "ar-buvote-pripazintas-kaltu-uzsienyje": _normalize_text_value(_row_answer_text(q9_4)),
            "ar-buvote-pripazintas-kaltu-del-politinio-persekiojimo": _normalize_text_value(
                _row_answer_text(q9_5)
            ),
        },
        # One entry per conviction, in the shape every other era publishes;
        # empty when Q9.2 is "Ne" or the block is absent.
        "teistumo-detales": {
            "irasai": conviction_records(
                rows, CONVICTION_QUESTION, conviction_field_keys(CONVICTION_QUESTION)
            ),
        },
        "gimimo-vieta": _normalize_text_value(_row_answer_text(q10)),
        "tautybe": _normalize_text_value(_row_answer_text(q11)),
        "issilavinimas": {
            "aprasas": _normalize_text_value(_row_answer_text(q12)),
            "irasai": _normalize_table_records(_question_record_rows(rows, "12")),
        },
        "mokslo-laipsnis": _normalize_text_value(_row_answer_text(q12_1)),
        "pedagoginis-vardas": _normalize_text_value(_row_answer_text(q12_2)),
        "uzsienio-kalbos": _split_list_value(_row_answer_text(q13)),
        "politine-organizacija": _normalize_text_value(_row_answer_text(q14)),
        "anksciau-isrinktas": {
            "aprasas": _normalize_text_value(_row_answer_text(q15)),
            "irasai": _normalize_table_records(_question_record_rows(rows, "15")),
        },
        "pagrindine-darboviete": _normalize_text_value(_row_answer_text(q16)),
        "visuomenine-veikla": _normalize_text_value(_row_answer_text(q17)),
        "pomegiai": _normalize_text_value(_row_answer_text(q18)),
        "seimine-padetis": marital_status,
        "sutuoktinio-vardas-pavarde": spouse_name,
        "vaiku-vardai-pavardes": _normalize_text_value(_row_answer_text(q20)),
        "kita-apie-save": _normalize_text_value(_row_answer_text(q21)),
    }


def _split_list_value(value: Any) -> list[str]:
    normalized_value = _normalize_text_value(value)
    if normalized_value is None:
        return []
    parts = [normalize_space(item) for item in normalized_value.split(",")]
    normalized_parts: list[str] = []
    for item in parts:
        candidate = _normalize_text_value(item)
        if candidate is None:
            continue
        normalized_parts.append(candidate)
    return normalized_parts


def parse_anketa_html(html: str) -> dict[str, Any]:
    soup = BeautifulSoup(html, "lxml")

    tabnav = soup.select_one("ul#tabnav")
    profile_table = _select_profile_table(soup, tabnav)
    content = _find_main_content_after_tabnav(soup)

    profile = _parse_profile_table(profile_table)
    profile["officeHeading"] = parse_office_heading(soup)
    tabs = _parse_tabnav(tabnav)
    anketa = _parse_anketa_content(content)

    return {
        "profile": profile,
        "tabs": tabs,
        "anketa": anketa,
        "diagnostics": {
            "tabnavFound": tabnav is not None,
            "profileTableFound": profile_table is not None,
            "anketaTableFound": content is not None and anketa["stats"]["rowCount"] > 0,
        },
    }


# ---------------------------------------------------------------------------
# Turto ir pajamų deklaracijos (asset/income)
# ---------------------------------------------------------------------------


def _normalize_turto_ir_pajamu_data(payload: dict[str, Any]) -> dict[str, Any]:
    return normalize_declaration(payload, _parse_eur_amount)


# ---------------------------------------------------------------------------
# Privačių interesų deklaracijos (private interests)
# ---------------------------------------------------------------------------


def _parse_privaciu_interesu_html(html: str) -> dict[str, Any]:
    soup = BeautifulSoup(html, "lxml")
    content = _find_main_content_after_tabnav(soup) or soup

    sections: list[dict[str, Any]] = []
    pending_title = ""
    pending_section_id = ""

    for table in content.find_all("table", recursive=False):
        classes = table.get("class") or []
        is_data_table = "partydata" in classes and table.find("th") is not None

        if is_data_table:
            headers = _extract_table_headers(table)
            rows: list[list[str]] = []
            for tr in table.find_all("tr"):
                cells = tr.find_all("td", recursive=False)
                if not cells:
                    continue
                values = [_tag_text(cell) for cell in cells]
                if not any(values):
                    continue
                rows.append(values)

            sections.append(
                {
                    "title": pending_title,
                    "sectionId": pending_section_id,
                    "columns": headers,
                    "rows": rows,
                }
            )
            pending_title = ""
            pending_section_id = ""
            continue

        # Key/value block. Each row is a single cell where the label sits in
        # plain text and the value is wrapped in <b> (e.g. "Vardas: VIRGINIJUS").
        items: list[dict[str, str]] = []
        block_section_id = ""
        block_title = ""
        for tr in table.find_all("tr"):
            cell = tr.find("td", recursive=False)
            if cell is None:
                continue
            label = _build_prompt_text(cell)
            value = _extract_answer_text(cell, [])

            if not label:
                # Bold-only row: section heading or descriptive note.
                heading_id = _section_id_from_text(value)
                if heading_id:
                    block_section_id = heading_id
                    block_title = value
                elif not block_title:
                    block_title = value
                continue

            clean_label = label.rstrip(":")
            # A leading label with no value that introduces the block (e.g.
            # "Deklaruojančio asmens sutuoktinis, sugyventinis, partneris:") is
            # the block heading, not a field. Naming it keeps the block in the
            # normalized output instead of being dropped as an unnamed section.
            if not value and not items and not block_title:
                block_title = clean_label
                continue

            items.append({"key": clean_label, "value": value})

        if block_section_id and not items:
            # Pure heading table preceding a data table.
            pending_title = block_title
            pending_section_id = block_section_id
            continue

        sections.append(
            {
                "title": block_title,
                "sectionId": block_section_id,
                "items": items,
            }
        )

    return {"sections": sections}


def _section_id_from_text(text: str) -> str:
    match = re.search(r"\b(ID\d{3}[A-Z])\b", text or "")
    return match.group(1).lower() if match else ""


# ---------------------------------------------------------------------------
# Optional subpages
# ---------------------------------------------------------------------------


def _parse_optional_subpages(
    candidate_dir: Path,
    candidate_id: str,
    candidate_source_url: str | None,
    anomalies: list[dict[str, Any]],
) -> dict[str, Any]:
    pages: dict[str, Any] = {}
    parser_map: dict[str, Any] = {
        "biografija": ("biografija.html", _parse_biografija_html),
        "privaciuInteresuDeklaracija": ("privaciu-interesu-deklaracijos.html", _parse_privaciu_interesu_html),
        "turtoIrPajamuDeklaracijos": ("turto-ir-pajamu-deklaracijos.html", _parse_turto_ir_pajamu_html),
        "kita": ("kita.html", _parse_kita_html),
        "politinesKampanijosDalyvioDuomenys": (
            "politines-kampanijos-dalyvio-duomenys.html",
            _parse_politines_kampanijos_html,
        ),
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
                    election_id=ELECTION_ID,
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


# ---------------------------------------------------------------------------
# Top-level parse
# ---------------------------------------------------------------------------


def parse_anketa_sample(
    candidate_id: str,
    samples_root: Path = DEFAULT_SAMPLES_ROOT,
    output_root: Path = DEFAULT_OUTPUT_ROOT,
) -> tuple[Path, dict[str, Any]]:
    candidate_dir = samples_root / candidate_id
    anketa_path = candidate_dir / "anketa.html"
    if not anketa_path.exists():
        raise FileNotFoundError(errno.ENOENT, "Missing anketa sample", str(anketa_path))

    html = anketa_path.read_text(encoding="utf-8")
    parsed = parse_anketa_html(html)
    meta = _load_candidate_meta(candidate_dir)
    candidate_meta = meta.get("candidate", {}) if isinstance(meta, dict) else {}
    candidate_source_url = candidate_meta.get("url") if isinstance(candidate_meta, dict) else None

    anomalies: list[dict[str, Any]] = []
    diagnostics = parsed.get("diagnostics", {})
    if not diagnostics.get("tabnavFound", False):
        anomalies.append(
            build_anomaly_event(
                event_type="TabnavSelectorNotFound",
                severity="critical",
                stage="parse",
                election_id=ELECTION_ID,
                candidate_id=candidate_id,
                source_url=candidate_source_url,
            )
        )
    if not diagnostics.get("profileTableFound", False):
        anomalies.append(
            build_anomaly_event(
                event_type="ProfileTableMissing",
                severity="error",
                stage="parse",
                election_id=ELECTION_ID,
                candidate_id=candidate_id,
                source_url=candidate_source_url,
            )
        )
    if not diagnostics.get("anketaTableFound", False):
        anomalies.append(
            build_anomaly_event(
                event_type="AnketaTableNotFound",
                severity="critical",
                stage="parse",
                election_id=ELECTION_ID,
                candidate_id=candidate_id,
                source_url=candidate_source_url,
            )
        )

    anketa_stats = parsed["anketa"]["stats"]
    if anketa_stats["rowCount"] == 0:
        anomalies.append(
            build_anomaly_event(
                event_type="AnketaTableEmpty",
                severity="error",
                stage="parse",
                election_id=ELECTION_ID,
                candidate_id=candidate_id,
                source_url=candidate_source_url,
            )
        )

    subpages = _parse_optional_subpages(
        candidate_dir=candidate_dir,
        candidate_id=candidate_id,
        candidate_source_url=candidate_source_url,
        anomalies=anomalies,
    )
    root_campaign_data = subpages.get("politinesKampanijosDalyvioDuomenys", {}).get("data")
    try:
        nested_campaigns = _parse_nested_campaign_samples(
            meta if isinstance(meta, dict) else None,
            root_campaign_data if isinstance(root_campaign_data, dict) else None,
            candidate_dir=candidate_dir,
            election_id=ELECTION_ID,
            candidate_id=candidate_id,
            source_url=candidate_source_url,
            anomalies=anomalies,
        )
    except Exception as exc:
        anomalies.append(
            build_anomaly_event(
                event_type="CampaignDataStructureDrift",
                severity="error",
                stage="parse",
                election_id=ELECTION_ID,
                candidate_id=candidate_id,
                source_url=candidate_source_url,
                detail={"error": str(exc)},
            )
        )
        nested_campaigns = []

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
        if key != "politinesKampanijosDalyvioDuomenys":
            raw_data[key] = data
        if key == "biografija" and isinstance(data, dict):
            normalized["biografija"] = _normalize_biografija_data(data)
        if key == "privaciuInteresuDeklaracija" and isinstance(data, dict):
            normalized["privaciu-interesu-deklaracija"] = _normalize_privaciu_interesu_data(data)
        if key == "turtoIrPajamuDeklaracijos" and isinstance(data, dict):
            normalized["turto-ir-pajamu-deklaracijos"] = _normalize_turto_ir_pajamu_data(data)
        if key == "kita" and isinstance(data, dict):
            normalized["kita"] = _normalize_kita_data(data)

    if nested_campaigns:
        campaign_key = "politinesKampanijosDalyvioDuomenys"
        section_description = ""
        if isinstance(root_campaign_data, dict):
            section_description = str(root_campaign_data.get("sectionDescription", ""))

        raw_data[campaign_key] = {
            "sectionDescription": section_description,
            "campaigns": nested_campaigns,
        }
        normalized["politines-kampanijos-dalyvio-duomenys"] = _normalize_campaigns(raw_data[campaign_key])
    elif isinstance(root_campaign_data, dict):
        campaign_key = "politinesKampanijosDalyvioDuomenys"
        raw_data[campaign_key] = root_campaign_data

    raw_data = _order_dict_keys(
        raw_data,
        [
            "profile",
            "anketa",
            "biografija",
            "turtoIrPajamuDeklaracijos",
            "privaciuInteresuDeklaracija",
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
            "politines-kampanijos-dalyvio-duomenys",
            "kita",
        ],
    )

    output_payload = {
        "electionId": ELECTION_ID,
        "candidateId": candidate_id,
        "candidateName": candidate_name,
        # Elected status exists on these pages only as the profile's prose
        # note; the derived flag pair keeps it queryable (issue #100).
        "kandidatavimas": candidacy_from_elected_note(normalized["profilis"].get("pastaba")),
        "source": {
            "candidateSourceUrl": candidate_source_url,
        },
        "rawData": raw_data,
        "normalized": _normalize_missing_values(normalized),
    }

    output_path = output_root / f"{candidate_id}-{ELECTION_ID}.json"
    write_candidate_record(output_path, output_payload, source_path=anketa_path)

    stats = {
        "candidateId": candidate_id,
        "candidateName": candidate_name,
        "outputPath": str(output_path),
        "rowCount": anketa_stats["rowCount"],
        "answeredRowCount": anketa_stats["answeredRowCount"],
        "anomalies": anomalies,
    }
    return output_path, stats


def parse_anketa_samples(
    candidate_ids: list[str] | None,
    samples_root: Path = DEFAULT_SAMPLES_ROOT,
    output_root: Path = DEFAULT_OUTPUT_ROOT,
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
        )
        results.append(stats)

    return results
