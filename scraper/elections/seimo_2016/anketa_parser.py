from __future__ import annotations

import json
from pathlib import Path
import re
from typing import Any

from bs4 import BeautifulSoup, NavigableString, Tag

from scraper.elections.seimo_2016.sitemap import ELECTION_ID, resolve_candidate_url
from scraper.shared.anomalies import build_anomaly_event
from scraper.shared.files import slugify, write_json

DEFAULT_SAMPLES_ROOT = Path("samples/html/2016-seimo")
DEFAULT_OUTPUT_ROOT = Path("data/2016-seimo")
MISSING_TEXT_VALUES = {
    "",
    "nenurodė",
    "nenurode",
    "-",
}

TURTO_PAJAMU_KEY_ALIASES = {
    "i-privalomas-registruoti-turtas": "privalomas-registruoti-turtas",
    "ii-vertybiniai-popieriai-meno-kuriniai-juvelyriniai-dirbiniai": "vertybiniai-popieriai-meno-kuriniai-juvelyriniai-dirbiniai",
    "iii-pinigines-lesos": "pinigines-lesos",
    "iv-suteiktos-paskolos": "suteiktos-paskolos",
    "v-gautos-paskolos": "gautos-paskolos",
    "gautu-pajamu-suma-gpm308-formos-12-13-13a-14-20-laukeliu-ir-gpm308-formos-v-priedo-v13-laukeliu-suma": "gautos-pajamos",
    "isskaiciuota-sumoketa-pajamu-mokescio-suma-gpm308-formos-26-laukelis": "sumoketas-pajamu-mokestis",
}

TURTO_PAJAMU_OUTPUT_ORDER = [
    "privalomas-registruoti-turtas",
    "vertybiniai-popieriai-meno-kuriniai-juvelyriniai-dirbiniai",
    "pinigines-lesos",
    "suteiktos-paskolos",
    "gautos-paskolos",
    "gautos-pajamos",
    "sumoketas-pajamu-mokestis",
]


def normalize_space(value: str) -> str:
    return " ".join(value.split())


def _normalize_text_value(value: Any) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        return str(value)

    normalized = normalize_space(value)
    if normalized.lower() in MISSING_TEXT_VALUES:
        return None
    return normalized


def _source_key(label: str) -> str:
    return slugify(normalize_space(label).rstrip(":"))


def _normalize_links(values: Any) -> list[str]:
    if not isinstance(values, list):
        return []
    links: list[str] = []
    for item in values:
        if not isinstance(item, str):
            continue
        value = normalize_space(item)
        if not value or value in links:
            continue
        links.append(value)
    return links


def _order_dict_keys(payload: dict[str, Any], ordered_keys: list[str]) -> dict[str, Any]:
    ordered: dict[str, Any] = {}
    for key in ordered_keys:
        if key in payload:
            ordered[key] = payload[key]

    for key, value in payload.items():
        if key in ordered:
            continue
        ordered[key] = value

    return ordered


def parse_question_number(text: str) -> str | None:
    match = re.match(r"^\s*(\d+(?:\.\d+)*)\.\s*", text)
    if not match:
        return None
    return match.group(1)


def _tag_text(tag: Tag | None) -> str:
    if tag is None:
        return ""
    return normalize_space(tag.get_text(" ", strip=True))


def _extract_link_target(anchor: Tag) -> str:
    href = normalize_space(anchor.get("href", ""))
    if href and href != "#":
        return href

    for attr_name in ("data-download-href", "data-direct-href"):
        attr_value = normalize_space(anchor.get(attr_name, ""))
        if attr_value:
            return attr_value

    return ""


def _extract_links(container: Tag | None) -> list[str]:
    if container is None:
        return []

    links: list[str] = []
    if container.name == "a":
        href = _extract_link_target(container)
        if href:
            links.append(resolve_candidate_url(href))

    for anchor in container.find_all("a"):
        href = _extract_link_target(anchor)
        if href:
            links.append(resolve_candidate_url(href))

    deduped_links: list[str] = []
    for link in links:
        if link not in deduped_links:
            deduped_links.append(link)
    return deduped_links


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
        if first_cells:
            img = first_cells[0].find("img")
            if img is not None:
                photo_src = normalize_space(img.get("src", ""))

        if len(first_cells) >= 2:
            title_cell = first_cells[1]
            elected_node = title_cell.find("b")
            elected_note = _tag_text(elected_node)

            title_clone_soup = BeautifulSoup(str(title_cell), "lxml")
            title_clone = title_clone_soup.find("td")
            if title_clone is not None:
                for node in title_clone.find_all("b"):
                    node.decompose()
                candidate_display_name = _tag_text(title_clone)

    for row in rows[1:]:
        cells = row.find_all("td", recursive=False)
        if not cells:
            continue

        key_cell = cells[0]
        value_cell = cells[1] if len(cells) > 1 else None

        key_text = _tag_text(key_cell).rstrip(":")
        value_text = _tag_text(value_cell)

        # A candidate nominated by more than one nominator gets a row per extra
        # nominator, with an empty label cell. Those rows belong to the field
        # above them; kept separate they would normalize away, because a field
        # without a key has nowhere to go.
        if not key_text and value_text and fields:
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


def _parse_tabnav(tabnav: Tag | None) -> list[dict[str, Any]]:
    if tabnav is None:
        return []

    tabs: list[dict[str, Any]] = []
    for anchor in tabnav.find_all("a", href=True):
        href = normalize_space(anchor.get("href", ""))
        label = _tag_text(anchor)
        classes = anchor.get("class", [])
        tabs.append(
            {
                "label": label,
                "slug": slugify(label),
                "url": resolve_candidate_url(href),
                "active": "active" in classes,
            }
        )
    return tabs


def _parse_nested_table(table: Tag) -> dict[str, Any]:
    headers: list[str] = []
    rows: list[Any] = []

    for th in table.find_all("th"):
        header = _tag_text(th)
        if header:
            headers.append(header)

    for tr in table.find_all("tr"):
        cells = tr.find_all("td")
        if not cells:
            continue

        values = [_tag_text(cell) for cell in cells]
        values = [value for value in values if value]
        if not values:
            continue

        if headers and len(values) == len(headers):
            rows.append({headers[i]: values[i] for i in range(len(headers))})
        elif len(values) == 1:
            rows.append(values[0])
        else:
            rows.append(values)

    return {
        "headers": headers,
        "rows": rows,
        "rowCount": len(rows),
    }


def _build_prompt_text(cell: Tag) -> str:
    clone_soup = BeautifulSoup(str(cell), "lxml")
    clone_cell = clone_soup.find("td")
    if clone_cell is None:
        return ""

    for nested_table in clone_cell.find_all("table"):
        nested_table.decompose()
    for bold in clone_cell.find_all("b"):
        bold.decompose()

    return _tag_text(clone_cell)


def _extract_answer_text(cell: Tag, nested_tables: list[Tag]) -> str:
    answers: list[str] = []
    for bold in cell.find_all("b"):
        in_nested = any(parent in nested_tables for parent in bold.parents)
        if in_nested:
            continue
        value = _tag_text(bold)
        if value:
            answers.append(value)

    if not answers:
        return ""
    return " | ".join(answers)


def _split_list_value(value: str) -> list[str]:
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


def _normalize_table_records(records: list[Any]) -> list[Any]:
    normalized_records: list[Any] = []
    for row in records:
        if isinstance(row, dict):
            normalized_row: dict[str, Any] = {}
            for key, value in row.items():
                source_key = _source_key(str(key))
                if not source_key:
                    continue
                normalized_row[source_key] = _normalize_text_value(value)
            normalized_records.append(normalized_row)
        else:
            normalized_records.append(row)
    return normalized_records


def _row_answer_text(row: dict[str, Any] | None) -> str:
    if not row:
        return ""
    answer = row.get("answer", "")
    if isinstance(answer, str):
        return answer
    return ""


def _find_row_by_question_number(rows: list[dict[str, Any]], question_number: str) -> dict[str, Any] | None:
    for row in rows:
        if row.get("questionNumber") == question_number:
            return row
    return None


def _find_row_by_prompt_prefix(rows: list[dict[str, Any]], prompt_prefix: str) -> dict[str, Any] | None:
    prefix = prompt_prefix.lower()
    for row in rows:
        prompt = str(row.get("prompt", "")).lower()
        if prompt.startswith(prefix):
            return row
    return None


def _first_nested_table_rows(row: dict[str, Any] | None) -> list[Any]:
    if not row:
        return []
    answer = row.get("answer")
    if not isinstance(answer, list):
        return []
    return answer


def _question_record_rows(rows: list[dict[str, Any]], question_number: str) -> list[Any]:
    # A record table (education for Q12, prior mandates for Q15) is sometimes
    # rendered inside its question's row and sometimes in a row of its own right
    # after it. Collect both, so the records are not lost in the second case.
    row = _find_row_by_question_number(rows, question_number)
    if row is None:
        return []

    records: list[Any] = list(_first_nested_table_rows(row))

    index = rows.index(row)
    for next_row in rows[index + 1:]:
        if next_row.get("questionNumber") or not isinstance(next_row.get("answer"), list):
            break
        records.extend(next_row["answer"])

    return records


def _merge_split_anketa_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    merged_rows: list[dict[str, Any]] = []
    index = 0

    while index < len(rows):
        row = rows[index]

        if index + 1 < len(rows):
            next_row = rows[index + 1]
            row_answer = row.get("answer")
            next_answer = next_row.get("answer")
            row_prompt = normalize_space(str(row.get("prompt", "")))
            next_prompt = normalize_space(str(next_row.get("prompt", "")))

            should_merge_q9_2 = (
                row.get("questionNumber") == "9.2"
                and isinstance(row_answer, str)
                and row_answer == ""
                and next_row.get("questionNumber") is None
                and isinstance(next_answer, str)
                and next_answer != ""
                and next_prompt.lower().startswith("tai nurodoma šioje anketoje")
            )

            if should_merge_q9_2:
                merged_rows.append(
                    {
                        "rowIndex": row.get("rowIndex"),
                        "questionNumber": row.get("questionNumber"),
                        "prompt": normalize_space(f"{row_prompt} {next_prompt}"),
                        "answer": next_answer,
                    }
                )
                index += 2
                continue

        merged_rows.append(row)
        index += 1

    return merged_rows


def _normalize_anketa_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    q5 = _find_row_by_question_number(rows, "5")
    q6 = _find_row_by_question_number(rows, "6")
    q8_1 = _find_row_by_question_number(rows, "8.1")
    q8_2 = _find_row_by_question_number(rows, "8.2")
    q8_3 = _find_row_by_question_number(rows, "8.3")
    q8_4 = _find_row_by_question_number(rows, "8.4")
    q9_1 = _find_row_by_question_number(rows, "9.1")
    q9_2 = _find_row_by_question_number(rows, "9.2")
    q9_3_1 = _find_row_by_question_number(rows, "9.3.1")
    q9_3_2 = _find_row_by_question_number(rows, "9.3.2")
    q9_3_3 = _find_row_by_question_number(rows, "9.3.3")
    q9_3_4 = _find_row_by_question_number(rows, "9.3.4")
    q10 = _find_row_by_question_number(rows, "10")
    q11 = _find_row_by_question_number(rows, "11")
    q12 = _find_row_by_question_number(rows, "12")
    pedagogical = _find_row_by_prompt_prefix(rows, "jei turite, nurodykite pedagogin")
    q13 = _find_row_by_question_number(rows, "13")
    q14 = _find_row_by_question_number(rows, "14")
    q15 = _find_row_by_question_number(rows, "15")
    q16 = _find_row_by_question_number(rows, "16")
    q17 = _find_row_by_question_number(rows, "17")
    q18 = _find_row_by_question_number(rows, "18")
    q19 = _find_row_by_question_number(rows, "19")
    spouse = _find_row_by_prompt_prefix(rows, "vyro arba žmonos vardas")
    q20 = _find_row_by_question_number(rows, "20")
    q21 = _find_row_by_question_number(rows, "21")

    return {
        "gimimo-data": _normalize_text_value(_row_answer_text(q5)),
        "adresas": _normalize_text_value(_row_answer_text(q6)),
        "pareiskimai": {
            "ar-nebaigta-teismo-paskirta-bausme": _normalize_text_value(
                _row_answer_text(q8_1)
            ),
            "ar-atliekate-karo-tarnyba": _normalize_text_value(
                _row_answer_text(q8_2)
            ),
            "ar-turite-kitos-valstybes-pilietybe": _normalize_text_value(_row_answer_text(q8_3)),
            "ar-susijes-priesaika-uzsienio-valstybei": _normalize_text_value(
                _row_answer_text(q8_4)
            ),
            "ar-bendradarbiavote-su-uzsienio-tarnybomis": _normalize_text_value(
                _row_answer_text(q9_1)
            ),
            "ar-buvote-pripazintas-kaltu": _normalize_text_value(_row_answer_text(q9_2)),
            "ar-veika-dekriminalizuota": _normalize_text_value(_row_answer_text(q9_3_1)),
            "ar-buvote-pripazintas-kaltu-uzsienyje": _normalize_text_value(
                _row_answer_text(q9_3_2)
            ),
            "ar-buvote-pripazintas-kaltu-uzsienyje-del-politinio-persekiojimo": _normalize_text_value(_row_answer_text(q9_3_3)),
            "teisiniai-argumentai": _normalize_text_value(_row_answer_text(q9_3_4)),
        },
        "gimimo-vieta": _normalize_text_value(_row_answer_text(q10)),
        "tautybe": _normalize_text_value(_row_answer_text(q11)),
        "issilavinimas": {
            "aprasas": _normalize_text_value(_row_answer_text(q12)),
            "irasai": _normalize_table_records(_question_record_rows(rows, "12")),
        },
        "pedagoginis-vardas": _normalize_text_value(_row_answer_text(pedagogical)),
        "uzsienio-kalbos": _split_list_value(_row_answer_text(q13)),
        "politine-organizacija": _normalize_text_value(_row_answer_text(q14)),
        "anksciau-isrinktas": {
            "aprasas": _normalize_text_value(_row_answer_text(q15)),
            "irasai": _normalize_table_records(_question_record_rows(rows, "15")),
        },
        "pagrindine-darboviete": _normalize_text_value(_row_answer_text(q16)),
        "visuomenine-veikla": _normalize_text_value(_row_answer_text(q17)),
        "pomegiai": _normalize_text_value(_row_answer_text(q18)),
        "seimine-padetis": _normalize_text_value(_row_answer_text(q19)),
        "sutuoktinio-vardas-pavarde": _normalize_text_value(_row_answer_text(spouse)),
        "vaiku-vardai-pavardes": _normalize_text_value(_row_answer_text(q20)),
        "kita-apie-save": _normalize_text_value(_row_answer_text(q21)),
    }


def _parse_anketa_table(table: Tag | None) -> dict[str, Any]:
    if table is None:
        return {
            "rows": [],
            "normalized": _normalize_anketa_rows([]),
            "stats": {
                "rowCount": 0,
                "answeredRowCount": 0,
                "rowsWithNestedTables": 0,
            },
        }

    parsed_rows: list[dict[str, Any]] = []
    answered_count = 0

    # Only the table's own body counts. A recursive lookup would find the
    # <tbody> of a nested detail table (a conviction block, say) whenever the
    # outer table has none of its own, and the whole anketa would collapse to
    # that nested table's rows.
    body = table.find("tbody", recursive=False)
    if body is not None:
        tr_nodes = body.find_all("tr", recursive=False)
    else:
        tr_nodes = table.find_all("tr", recursive=False)

    for row_index, tr in enumerate(tr_nodes, start=1):
        cell = tr.find("td")
        if cell is None:
            continue

        nested_tables = cell.find_all("table")
        nested_payload = [_parse_nested_table(nested_table) for nested_table in nested_tables]

        prompt = _build_prompt_text(cell)
        if nested_payload:
            first_rows = nested_payload[0].get("rows", [])
            answer: Any = first_rows if isinstance(first_rows, list) else []
        else:
            answer = _extract_answer_text(cell, nested_tables)
        question_number = parse_question_number(prompt)

        if answer:
            answered_count += 1

        parsed_rows.append(
            {
                "rowIndex": row_index,
                "questionNumber": question_number,
                "prompt": prompt,
                "answer": answer,
            }
        )

    merged_rows = _merge_split_anketa_rows(parsed_rows)
    answered_count = sum(1 for row in merged_rows if row.get("answer"))
    normalized = _normalize_anketa_rows(merged_rows)

    return {
        "rows": merged_rows,
        "normalized": normalized,
        "stats": {
            "rowCount": len(merged_rows),
            "answeredRowCount": answered_count,
        },
    }


def parse_anketa_html(html: str) -> dict[str, Any]:
    soup = BeautifulSoup(html, "lxml")

    tabnav = soup.select_one("ul#tabnav")
    profile_table = tabnav.find_previous("table") if tabnav is not None else soup.find("table")
    anketa_table = tabnav.find_next("table") if tabnav is not None else None

    profile = _parse_profile_table(profile_table)
    tabs = _parse_tabnav(tabnav)
    anketa = _parse_anketa_table(anketa_table)

    return {
        "profile": profile,
        "tabs": tabs,
        "anketa": anketa,
        "diagnostics": {
            "tabnavFound": tabnav is not None,
            "profileTableFound": profile_table is not None,
            "anketaTableFound": anketa_table is not None,
        },
    }


def _find_main_content_after_tabnav(soup: BeautifulSoup) -> Tag | None:
    tabnav = soup.select_one("ul#tabnav")
    if tabnav is None:
        return None

    for sibling in tabnav.next_siblings:
        if isinstance(sibling, Tag) and sibling.name == "div":
            return sibling
    return tabnav.find_next("div")


def _extract_non_empty_text_nodes(container: Tag | None) -> list[str]:
    if container is None:
        return []
    values: list[str] = []
    for text in container.stripped_strings:
        normalized = normalize_space(text)
        if normalized:
            values.append(normalized)
    return values


def _extract_table_headers(table: Tag) -> list[str]:
    headers: list[str] = []
    thead = table.find("thead")
    if thead is not None:
        for th in thead.find_all("th"):
            value = _tag_text(th)
            if value:
                headers.append(value)
        if headers:
            return headers

    for th in table.find_all("th", recursive=False):
        value = _tag_text(th)
        if value:
            headers.append(value)
    return headers


def _extract_table_title(table: Tag) -> str:
    heading = _tag_text(table.find("h4"))
    if heading:
        return heading

    first_row = table.find("tr")
    if first_row is None:
        return ""

    bold = first_row.find("b")
    if bold is not None:
        return _tag_text(bold)

    th = first_row.find("th")
    if th is not None:
        return _tag_text(th)

    return ""


def _parse_generic_table(table: Tag, title: str = "") -> dict[str, Any]:
    headers = _extract_table_headers(table)
    rows: list[dict[str, Any]] = []
    key_values: list[dict[str, Any]] = []

    for tr in table.find_all("tr"):
        cells = tr.find_all("td", recursive=False)
        if not cells:
            continue

        values = [_tag_text(cell) for cell in cells]
        if not any(values):
            continue

        row_links = [_extract_links(cell) for cell in cells]
        mapped: dict[str, str] = {}
        if headers and len(values) == len(headers):
            mapped = {headers[i]: values[i] for i in range(len(headers))}

        rows.append(
            {
                "values": values,
                "mapped": mapped,
                "links": row_links,
            }
        )

        if len(values) == 2:
            key_values.append(
                {
                    "key": values[0].rstrip(":"),
                    "value": values[1],
                    "links": row_links[1] if len(row_links) > 1 else [],
                }
            )

    return {
        "title": title or _extract_table_title(table),
        "headers": headers,
        "rows": rows,
        "keyValues": key_values,
        "rowCount": len(rows),
    }


def _parse_decimal_value(value: str) -> float | None:
    cleaned = normalize_space(value).replace("Eur", "").replace(" ", "")
    cleaned = cleaned.replace("\xa0", "").replace(",", ".")
    cleaned = cleaned.strip(".")
    if not cleaned:
        return None

    try:
        return float(cleaned)
    except ValueError:
        return None


def _build_campaign_title_key(value: str) -> str:
    return slugify(value).replace("-nr", "")


def _parse_registration_details(text: str) -> dict[str, str]:
    normalized = normalize_space(text)
    details = {
        "registrationNote": normalized,
        "registeredDate": "",
        "decisionNumber": "",
    }

    if not normalized:
        return details

    date_match = re.search(r"(\d{4}-\d{2}-\d{2})", normalized)
    if date_match:
        details["registeredDate"] = date_match.group(1)

    decision_match = re.search(r"Nr\.\s*([^\s]+)", normalized)
    if decision_match:
        details["decisionNumber"] = decision_match.group(1)

    return details


def _extract_picklist_free_text(picklist: Tag) -> list[str]:
    values: list[str] = []
    for child in picklist.children:
        if isinstance(child, NavigableString):
            text = normalize_space(str(child))
            if text:
                values.append(text)
            continue

        if not isinstance(child, Tag):
            continue

        if child.name in {"h3", "table", "br", "a"}:
            continue

        text = _tag_text(child)
        if text:
            values.append(text)

    return values


def _extract_campaign_contacts(table: Tag | None) -> tuple[dict[str, str], list[str]]:
    fields: dict[str, str] = {}
    notices: list[str] = []
    if table is None:
        return fields, notices

    for tr in table.find_all("tr"):
        cells = tr.find_all("td", recursive=False)
        if not cells:
            continue

        values = [_tag_text(cell) for cell in cells]
        values = [value for value in values if value]
        if not values:
            continue

        if len(values) == 1:
            notices.append(values[0])
            continue

        fields[values[0].rstrip(":")] = values[1]

    return fields, notices


def _parse_campaign_participant_picklist(picklist: Tag | None) -> dict[str, Any] | None:
    if picklist is None:
        return None

    table = picklist.find("table")
    fields, notices = _extract_campaign_contacts(table)
    participant_type = ""
    for value in _extract_picklist_free_text(picklist):
        if value:
            participant_type = value
            break

    registration_source = ""
    for notice in notices:
        if re.search(r"registruot", notice, flags=re.IGNORECASE):
            registration_source = notice
            break
    if not registration_source:
        for notice in notices:
            if re.search(r"\d{4}-\d{2}-\d{2}", notice):
                registration_source = notice
                break
    if not registration_source and notices:
        registration_source = notices[0]

    registration = _parse_registration_details(registration_source)
    return {
        "title": _tag_text(picklist.find("h3")),
        "participantType": participant_type,
        "status": fields.get("Statusas", ""),
        "inquiryPhone": fields.get("Telefonas pasiteirauti", ""),
        "email": fields.get("Elektroninio pašto adresas", ""),
        **registration,
    }


def _parse_campaign_person_picklist(picklist: Tag | None) -> dict[str, Any] | None:
    if picklist is None:
        return None

    title = _tag_text(picklist.find("h3"))
    table = picklist.find("table")
    fields, _ = _extract_campaign_contacts(table)
    if not title and not fields:
        return None

    return {
        "title": title,
        "name": fields.get("Vardas, pavardė", ""),
        "phone": fields.get("Telefonas", ""),
        "email": fields.get("El. paštas", ""),
        "companyName": fields.get("Įmonės pavadinimas", ""),
        "companyCode": fields.get("Įmonės kodas", ""),
    }


def _parse_campaign_header(html: str) -> dict[str, Any]:
    soup = BeautifulSoup(html, "lxml")
    picklists = soup.select("div.picklist.tabinc")
    overview_picklist = picklists[0] if picklists else None
    secondary_picklist = picklists[1] if len(picklists) > 1 else None

    treasurer = _parse_campaign_person_picklist(secondary_picklist)
    auditor = None
    if treasurer and "auditor" in _build_campaign_title_key(treasurer.get("title", "")):
        auditor = treasurer
        treasurer = None

    return {
        "sectionDescription": _tag_text(soup.select_one("div.sectionDescription")),
        "availableTabs": _parse_tabnav(soup.select_one("ul#tabnav")),
        "participant": _parse_campaign_participant_picklist(overview_picklist),
        "treasurer": treasurer,
        "auditor": auditor,
    }


def _extract_content_picklist(soup: BeautifulSoup) -> Tag | None:
    picklists = soup.select("div.picklist.tabinc")
    if len(picklists) >= 2:
        return picklists[1]
    if picklists:
        return picklists[0]
    return None


def _extract_heading_text(tag: Tag | NavigableString | None) -> str:
    if isinstance(tag, NavigableString):
        return normalize_space(str(tag))
    if isinstance(tag, Tag):
        return _tag_text(tag)
    return ""


DONATION_RECORD_KEYS = [
    "rowNumber",
    "donor",
    "municipality",
    "date",
    "incomeSourceCode",
    "amount",
    "notes",
]


def _donation_column_key(header: str) -> str:
    # Donation tables come in several widths: the 2016 layout carries all seven
    # columns, while later pages drop the municipality column, the income source
    # column, or both, and rename "Pastabos" to "VRK sprendimas, pastabos".
    # Columns are therefore matched by heading, not by position.
    key = _source_key(header)
    if not key:
        return ""
    if key.startswith("eil-nr"):
        return "rowNumber"
    if key.startswith("aukotojas"):
        return "donor"
    if key.startswith("savivaldybe"):
        return "municipality"
    if key.startswith("data"):
        return "date"
    if key.startswith("pajamu-saltinis"):
        return "incomeSourceCode"
    if key.startswith("aukos-suma"):
        return "amount"
    if "pastab" in key:
        return "notes"
    return ""


def _donation_column_keys(table: Tag) -> list[str]:
    return [_donation_column_key(_tag_text(th)) for th in table.find_all("th")]


def _build_donation_record(values: list[str], column_keys: list[str]) -> dict[str, Any]:
    # Absent columns stay in the record as empty values so every election keeps
    # the same record shape.
    record: dict[str, Any] = {key: "" for key in DONATION_RECORD_KEYS}
    record["amount"] = None

    for index, value in enumerate(values):
        key = column_keys[index] if index < len(column_keys) else ""
        if not key:
            continue
        record[key] = _parse_decimal_value(value) if key == "amount" else value

    return record


def _parse_donations_table(table: Tag) -> dict[str, Any]:
    records: list[dict[str, Any]] = []
    column_keys = _donation_column_keys(table)

    for tr in table.find_all("tr"):
        cells = tr.find_all(["td", "th"], recursive=False)
        if not cells:
            continue

        if any(cell.name == "th" for cell in cells):
            continue

        values = [_tag_text(cell) for cell in cells]
        if not any(values):
            continue

        first_value = values[0]
        if not re.match(r"^\d+\.$", first_value):
            continue

        if column_keys and len(values) == len(column_keys):
            records.append(_build_donation_record(values, column_keys))
            continue

        # Fall back to the 2016 column order when the table has no usable
        # headings (or a row does not line up with them).
        if len(values) >= 7:
            records.append(
                {
                    "rowNumber": first_value,
                    "donor": values[1],
                    "municipality": values[2],
                    "date": values[3],
                    "incomeSourceCode": values[4],
                    "amount": _parse_decimal_value(values[5]),
                    "notes": values[6],
                }
            )
            continue

    totals: dict[str, Any] = {}
    for tr in table.find_all("tr"):
        cells = tr.find_all(["td", "th"], recursive=False)
        if not cells or any(cell.name == "th" for cell in cells):
            continue

        values = [_tag_text(cell) for cell in cells]
        if not any(values) or len(values) < 2:
            continue

        first_value = values[0]
        if re.match(r"^\d+\.$", first_value):
            continue

        key = _build_campaign_title_key(first_value.rstrip(":"))
        if key:
            totals[key] = _parse_decimal_value(values[1])

    return {
        "records": records,
        "totals": totals,
    }


NO_DATA_HEADING_PATTERN = re.compile(r"Duomen[ųu]\s+n[ėe]ra\s*$", flags=re.IGNORECASE)


def _parse_campaign_donations_html(html: str) -> dict[str, Any]:
    soup = BeautifulSoup(html, "lxml")
    content = _extract_content_picklist(soup)
    if content is None:
        return {"sections": []}

    sections: list[dict[str, Any]] = []
    current_title = ""

    def _make_no_data_section(title: str, text: str) -> dict[str, Any]:
        if _source_key(title) in {"nepriimtos-aukos", "vrk-sprendimais-pripazintos-ir-papildytos-dalyvio-politines-kampanijos-pajamos"}:
            return {
                "status": "noData",
                "message": text,
            }
        return {
            "title": title,
            "status": "noData",
            "message": text,
        }

    for child in content.children:
        if isinstance(child, NavigableString):
            text = normalize_space(str(child))
            if not text or not current_title:
                continue
            sections.append(_make_no_data_section(current_title, text))
            current_title = ""
            continue

        if not isinstance(child, Tag):
            continue

        if child.name == "a":
            sections.append(
                {
                    "title": "Spausdinimui",
                    "urls": _extract_links(child),
                    "label": _tag_text(child),
                }
            )
            continue

        if child.name == "h3":
            heading = _tag_text(child)
            # A campaign with nothing to report folds the empty-state marker
            # into the heading itself ("Gautos ir priimtos aukos: Duomenų
            # nėra") rather than emitting it as the text node that follows a
            # bare heading. Left unsplit, no table or text node follows, so the
            # next h3 overwrites current_title and the whole section vanishes —
            # silently turning "this candidate received no donations" into
            # "this section was never published".
            no_data = NO_DATA_HEADING_PATTERN.search(heading)
            if no_data:
                title = heading[: no_data.start()].strip().rstrip(":").strip()
                if title:
                    sections.append(_make_no_data_section(title, no_data.group(0).strip()))
                    current_title = ""
                    continue
            current_title = heading.rstrip(":")
            continue

        if child.name == "table" and current_title:
            parsed_table = _parse_donations_table(child)
            sections.append({"title": current_title, **parsed_table})
            current_title = ""
            continue

        text = _tag_text(child)
        if text and current_title:
            sections.append(_make_no_data_section(current_title, text))
            current_title = ""

    return {"sections": sections}


def _parse_campaign_financing_html(html: str) -> dict[str, Any]:
    soup = BeautifulSoup(html, "lxml")
    content = _extract_content_picklist(soup)
    if content is None:
        return {"reports": [], "publisherInfoUrls": []}

    reports: list[dict[str, Any]] = []
    table = content.find("table")
    if table is not None:
        for tr in table.find_all("tr"):
            cells = tr.find_all("td", recursive=False)
            if len(cells) < 5:
                continue

            report_url_values = _extract_links(cells[3])
            appendix_url_values = _extract_links(cells[4])
            reports.append(
                {
                    "rowNumber": _tag_text(cells[0]),
                    "approvedDate": _tag_text(cells[1]),
                    "status": _tag_text(cells[2]),
                    "reportUrls": report_url_values,
                    "advertisingAppendixUrls": appendix_url_values,
                }
            )

    publisher_links: list[str] = []
    for anchor in content.find_all("a"):
        label = _tag_text(anchor)
        if "Viešosios informacijos rengėjų ir skleidėjų duomenys" in label:
            publisher_links.extend(_extract_links(anchor))

    return {
        "reports": reports,
        "publisherInfoUrls": publisher_links,
    }


def _parse_campaign_contracts_html(html: str) -> dict[str, Any]:
    soup = BeautifulSoup(html, "lxml")
    content = _extract_content_picklist(soup)
    if content is None:
        return {"contracts": []}

    contracts: list[dict[str, Any]] = []
    table = content.find("table")
    if table is None:
        return {"contracts": contracts}

    for tr in table.find_all("tr"):
        cells = tr.find_all("td", recursive=False)
        if len(cells) < 6:
            continue

        contracts.append(
            {
                "rowNumber": _tag_text(cells[0]),
                "counterparty": _tag_text(cells[1]),
                "agreementDate": _tag_text(cells[2]),
                "agreementNumber": _tag_text(cells[3]),
                "subject": _tag_text(cells[4]),
                "textAccessNote": _tag_text(cells[5]),
                "textUrls": _extract_links(cells[5]),
            }
        )

    return {"contracts": contracts}


def _parse_campaign_generic_html(html: str) -> dict[str, Any]:
    soup = BeautifulSoup(html, "lxml")
    blocks: list[dict[str, Any]] = []
    content = _extract_content_picklist(soup)
    if content is None:
        return {"blocks": blocks}

    for table in content.find_all("table", recursive=False):
        payload = _parse_generic_table(table)
        blocks.append(
            {
                "title": payload.get("title", ""),
                "columns": payload.get("headers", []),
                "rows": [row.get("values", []) for row in payload.get("rows", [])],
            }
        )

    texts = _extract_non_empty_text_nodes(content)
    if texts:
        blocks.append({"title": "texts", "values": texts})

    links = _extract_links(content)
    if links:
        blocks.append({"title": "links", "urls": links})

    return {"blocks": blocks}


def _parse_campaign_tab_data(slug: str, html: str) -> dict[str, Any]:
    if slug == "izdininkas":
        return {}
    if slug == "auditorius":
        return {}
    if slug == "auku-ir-aukotoju-sarasas":
        return _parse_campaign_donations_html(html)
    if slug == "finansavimo-ataskaitos":
        return _parse_campaign_financing_html(html)
    if slug == "sutartys":
        return _parse_campaign_contracts_html(html)
    return _parse_campaign_generic_html(html)


_SPRENDIMAI_HEADER_TOKENS = {"eil.", "nr.", "pavadinimas", "data", "numeris", "pastaba"}


def _is_sprendimai_header_row(values: list[str]) -> bool:
    compact = [normalize_space(v).lower() for v in values if isinstance(v, str) and v.strip()]
    if not compact:
        return True
    if "sprendimas" in " ".join(compact) and len(compact) <= 3:
        return True
    return bool(_SPRENDIMAI_HEADER_TOKENS.intersection(compact))


def _normalize_sprendimai_tab(data: Any) -> list[dict[str, Any]]:
    """VRK decisions published on a campaign's "Sprendimai" tab.

    The tab is fetched and kept in rawData but was never normalized, so every
    decision VRK took about a campaign — unlawful political advertising,
    accounting breaches — was dropped from the analysis-ready output. The
    payload is the same block/row shape the 2024 Seimo module already handles.
    """
    if not isinstance(data, dict):
        return []
    blocks = data.get("blocks")
    if not isinstance(blocks, list):
        return []

    urls: list[str] = []
    rows: list[list[str]] = []
    for block in blocks:
        if not isinstance(block, dict):
            continue
        if normalize_space(str(block.get("title", ""))).lower() == "links":
            for url in block.get("urls", []) or []:
                value = normalize_space(str(url))
                if value and value not in urls:
                    urls.append(value)
            continue
        for row in block.get("rows", []) or []:
            if not isinstance(row, list):
                continue
            values = [normalize_space(str(cell)) for cell in row]
            if any(values):
                rows.append(values)

    records: list[dict[str, Any]] = []
    for values in rows:
        # Rows are swept from every non-links block, and on a page whose
        # decisions table is missing the content selector falls back to the
        # participant profile table. Its rows are one or two cells wide;
        # every decision VRK publishes is five, so width separates them
        # cleanly and keeps "Statusas: Savarankiškas" out of the output.
        if len(values) < 4:
            continue
        if _is_sprendimai_header_row(values):
            continue
        padded = list(values) + [""] * max(0, 5 - len(values))
        title = _normalize_text_value(padded[1])
        if title is None:
            continue
        record: dict[str, Any] = {
            "rowNumber": _normalize_text_value(padded[0]),
            "title": title,
            "date": _normalize_text_value(padded[2]),
            "number": _normalize_text_value(padded[3]),
            "note": _normalize_text_value(padded[4]),
            "urls": [],
        }
        # A wider table than VRK has ever published would otherwise lose its
        # extra columns silently.
        if len(values) > 5:
            record["extraColumns"] = [
                value for value in values[5:] if _normalize_text_value(value) is not None
            ]
        records.append(record)

    # Each decision row carries its own document link, and the links block
    # lists them in row order. Copying the whole list onto every record — as
    # this first did — cross-links each decision to the others' documents.
    for index, url in enumerate(urls):
        if index < len(records):
            records[index]["urls"] = [url]

    return records


def _normalize_campaigns(raw_campaign_data: dict[str, Any]) -> list[dict[str, Any]]:
    campaigns = raw_campaign_data.get("campaigns")
    if not isinstance(campaigns, list):
        return []

    normalized_campaigns: list[dict[str, Any]] = []
    for campaign in campaigns:
        if not isinstance(campaign, dict):
            continue

        tabs = campaign.get("tabs", [])
        donations: dict[str, Any] = {}
        financing_reports: list[dict[str, Any]] = []
        contracts: list[dict[str, Any]] = []
        decisions: list[dict[str, Any]] = []

        if isinstance(tabs, list):
            for tab in tabs:
                if not isinstance(tab, dict):
                    continue
                slug = str(tab.get("slug", ""))
                data = tab.get("data")
                if not isinstance(data, dict):
                    continue
                if slug == "auku-ir-aukotoju-sarasas":
                    for section in data.get("sections", []):
                        if not isinstance(section, dict):
                            continue
                        section_title = str(section.get("title", ""))
                        if _source_key(section_title) == "spausdinimui":
                            continue
                        section_key = _build_campaign_title_key(section_title)
                        if section_key:
                            donations[section_key] = section
                elif slug == "finansavimo-ataskaitos":
                    financing_reports = data.get("reports", []) if isinstance(data.get("reports"), list) else []
                elif slug == "sutartys":
                    contracts = data.get("contracts", []) if isinstance(data.get("contracts"), list) else []
                elif slug == "sprendimai":
                    decisions = _normalize_sprendimai_tab(data)

        participant = campaign.get("participant") if isinstance(campaign.get("participant"), dict) else {}
        treasurer = campaign.get("treasurer") if isinstance(campaign.get("treasurer"), dict) else {}
        auditor = campaign.get("auditor") if isinstance(campaign.get("auditor"), dict) else {}

        normalized_donations: dict[str, Any] = {}
        for donation_key, donation_payload in donations.items():
            if not donation_key:
                continue
            normalized_donations[_source_key(donation_key)] = donation_payload

        normalized_campaigns.append(
            {
                "statusas": _normalize_text_value(participant.get("status")),
                "registravimo-data": _normalize_text_value(participant.get("registeredDate")),
                "sprendimo-numeris": _normalize_text_value(participant.get("decisionNumber")),
                "kontaktai": {
                    "telefonas-pasiteirauti": _normalize_text_value(participant.get("inquiryPhone")),
                    "el-pastas": _normalize_text_value(participant.get("email")),
                },
                "izdininkas": {
                    "vardas-pavarde": _normalize_text_value(treasurer.get("name")),
                    "telefonas": _normalize_text_value(treasurer.get("phone")),
                    "el-pastas": _normalize_text_value(treasurer.get("email")),
                    "imones-pavadinimas": _normalize_text_value(treasurer.get("companyName")),
                    "imones-kodas": _normalize_text_value(treasurer.get("companyCode")),
                }
                if treasurer
                else {},
                "auditorius": {
                    "vardas-pavarde": _normalize_text_value(auditor.get("name")),
                    "telefonas": _normalize_text_value(auditor.get("phone")),
                    "el-pastas": _normalize_text_value(auditor.get("email")),
                    "imones-pavadinimas": _normalize_text_value(auditor.get("companyName")),
                    "imones-kodas": _normalize_text_value(auditor.get("companyCode")),
                }
                if auditor
                else {},
                "aukos-pagal-sekcija": normalized_donations,
                "finansavimo-ataskaitos": financing_reports,
                "sutartys": contracts,
                "sprendimai": decisions,
            }
        )

    return normalized_campaigns


def _parse_biografija_html(html: str) -> dict[str, Any]:
    soup = BeautifulSoup(html, "lxml")
    content = _find_main_content_after_tabnav(soup)
    return {
        "text": _tag_text(content),
        "html": str(content) if content is not None else "",
    }


def _extract_section_id(*candidates: str) -> str:
    for candidate in candidates:
        if not candidate:
            continue
        match = re.search(r"\b(ID\d{3}[A-Z])\b", candidate)
        if match:
            return match.group(1).lower()
    return ""


def _index_sections_by_id(sections: list[dict[str, Any]]) -> dict[str, Any]:
    by_section_id: dict[str, Any] = {}
    for section in sections:
        if not isinstance(section, dict):
            continue
        section_id = section.get("sectionId")
        if not isinstance(section_id, str) or not section_id:
            continue

        existing = by_section_id.get(section_id)
        if existing is None:
            by_section_id[section_id] = section
        elif isinstance(existing, list):
            existing.append(section)
        else:
            by_section_id[section_id] = [existing, section]

    return by_section_id


def _normalize_profile_data(profile: dict[str, Any]) -> dict[str, Any]:
    normalized_fields: dict[str, Any] = {}
    fields = profile.get("fields") if isinstance(profile.get("fields"), list) else []
    for field in fields:
        if not isinstance(field, dict):
            continue
        key_text = str(field.get("key", ""))
        key = _source_key(key_text)
        if not key:
            continue
        normalized_fields[key] = {
            "pavadinimas": _normalize_text_value(key_text),
            "reiksme": _normalize_text_value(field.get("displayValue")),
            "nuorodos": _normalize_links(field.get("urls")),
        }

    return {
        "vardas-pavarde": _normalize_text_value(profile.get("candidateDisplayName")),
        "pastaba": _normalize_text_value(profile.get("electedNote")),
        "nuotrauka": _normalize_text_value(profile.get("photoSrc")),
        "kita": normalized_fields,
    }


def _normalize_biografija_data(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "tekstas": _normalize_text_value(payload.get("text")),
    }


def _normalize_privaciu_interesu_data(payload: dict[str, Any]) -> dict[str, Any]:
    sections = payload.get("sections") if isinstance(payload.get("sections"), list) else []
    result: dict[str, Any] = {}
    for index, section in enumerate(sections, start=1):
        if not isinstance(section, dict):
            continue
        section_title = str(section.get("title", "")).strip()
        section_id = str(section.get("sectionId", "")).strip()
        section_key = _source_key(section_id or section_title) or f"sekcija-{index}"

        normalized_section: dict[str, Any] = {}

        if isinstance(section.get("items"), list):
            item_values: dict[str, Any] = {}
            # A declaration section can be free text rather than key/value
            # pairs — ID001A KITI DUOMENYS is published as an unlabelled
            # sentence. Those rows reach here with an empty key; dropping them
            # for want of a key silently loses the whole declared text.
            free_text: list[str] = []
            for item in section["items"]:
                if not isinstance(item, dict):
                    continue
                item_label = str(item.get("key", ""))
                item_key = _source_key(item_label)
                item_value = _normalize_text_value(item.get("value"))
                if not item_key:
                    if item_value:
                        free_text.append(str(item_value))
                    continue
                item_values[item_key] = item_value
            if free_text:
                joined = " ".join(free_text)
                existing = item_values.get("tekstas")
                # A labelled field can itself slugify to "tekstas". Appending
                # rather than deferring keeps both, instead of re-introducing
                # the silent loss this branch exists to fix.
                item_values["tekstas"] = (
                    f"{existing} {joined}".strip() if isinstance(existing, str) and existing else joined
                )
            if item_values:
                normalized_section = item_values

        if isinstance(section.get("columns"), list):
            normalized_columns = [
                _normalize_text_value(column) for column in section["columns"] if _normalize_text_value(column) is not None
            ]
        else:
            normalized_columns = []

        if isinstance(section.get("rows"), list):
            normalized_rows: list[dict[str, Any]] = []
            for row in section.get("rows", []):
                if not isinstance(row, list):
                    continue

                effective_columns = normalized_columns
                if len(normalized_columns) == len(row) + 1:
                    effective_columns = normalized_columns[1:]

                row_object: dict[str, Any] = {}
                for column_index, value in enumerate(row):
                    label = (
                        effective_columns[column_index]
                        if column_index < len(effective_columns)
                        else f"stulpelis-{column_index + 1}"
                    )
                    key = _source_key(label) or f"stulpelis-{column_index + 1}"
                    row_object[key] = _normalize_text_value(value)

                if row_object:
                    normalized_rows.append(row_object)

            if normalized_rows:
                normalized_section = normalized_rows

        # Hoist declarant fields (deklaruojantis-asmuo) to the top level
        if isinstance(normalized_section, dict) and "deklaruojantis-asmuo" in normalized_section:
            result.update(normalized_section)
            continue

        # Drop sections with no id/title (spouse/secondary blocks with fallback keys)
        if section_key.startswith("sekcija-"):
            continue

        result[section_key] = normalized_section

    return result


def _parse_eur_amount(value: Any) -> int | float | None:
    normalized_value = _normalize_text_value(value)
    if normalized_value is None:
        return None

    compact = normalized_value.replace("\u00a0", " ")
    compact = re.sub(r"\beur\b", "", compact, flags=re.IGNORECASE)
    compact = compact.replace(" ", "").replace(",", ".")

    if not compact or not re.fullmatch(r"-?\d+(?:\.\d+)?", compact):
        return None

    amount = float(compact)
    if amount.is_integer():
        return int(amount)
    return amount


def _normalize_turto_ir_pajamu_data(payload: dict[str, Any]) -> dict[str, Any]:
    sections = payload.get("sections") if isinstance(payload.get("sections"), list) else []
    normalized_fields: dict[str, int | float | None] = {
        key: None for key in TURTO_PAJAMU_OUTPUT_ORDER
    }

    for section in sections:
        if not isinstance(section, dict):
            continue

        for item in section.get("items", []):
            if not isinstance(item, dict):
                continue

            item_label = str(item.get("key", ""))
            source_key = _source_key(item_label)
            target_key = TURTO_PAJAMU_KEY_ALIASES.get(source_key)
            if target_key is None:
                continue

            normalized_fields[target_key] = _parse_eur_amount(item.get("value"))

    return normalized_fields


def _normalize_kita_data(payload: dict[str, Any]) -> dict[str, Any]:
    texts = payload.get("texts") if isinstance(payload.get("texts"), list) else []
    normalized_texts = [
        value
        for value in (_normalize_text_value(text) for text in texts)
        if value is not None
    ]

    return {
        "tekstai": normalized_texts,
        "nuorodos": _normalize_links(payload.get("links")),
    }


def _normalize_missing_values(value: Any) -> Any:
    if isinstance(value, str):
        return _normalize_text_value(value)
    if isinstance(value, list):
        return [_normalize_missing_values(item) for item in value]
    if isinstance(value, dict):
        return {key: _normalize_missing_values(item) for key, item in value.items()}
    return value


def _parse_privaciu_interesu_html(html: str) -> dict[str, Any]:
    def _parse_privaciu_section(table: Tag) -> dict[str, Any]:
        heading = _tag_text(table.find("h4"))
        title = heading or _extract_table_title(table)
        section_id = _extract_section_id(heading, title)
        headers = _extract_table_headers(table)

        row_payloads: list[dict[str, Any]] = []
        for tr in table.find_all("tr"):
            cells = tr.find_all("td", recursive=False)
            if not cells:
                continue

            values = [_tag_text(cell) for cell in cells]
            if not any(values):
                continue

            row_payloads.append({"values": values})

        section: dict[str, Any] = {
            "title": title,
            "sectionId": section_id,
        }

        is_key_value = bool(row_payloads) and all(len(row["values"]) <= 2 for row in row_payloads)
        if is_key_value:
            items: list[dict[str, str]] = []
            for row in row_payloads:
                values = row["values"]
                key = values[0].rstrip(":")
                value = values[1] if len(values) > 1 else ""
                if key == title and not value:
                    continue
                if len(values) == 1 and headers:
                    # A one-cell row in a header-bearing table is a data row
                    # of a single-column table (ID001A KITI DUOMENYS free
                    # text), not a label. Keep it unlabelled so the normalizer
                    # can collect it under "tekstas" instead of the whole
                    # sentence becoming a key.
                    items.append({"key": "", "value": values[0]})
                    continue
                items.append(
                    {
                        "key": key,
                        "value": value,
                    }
                )
            section["items"] = items
        else:
            section["columns"] = headers
            section["rows"] = [row["values"] for row in row_payloads]

        return section

    soup = BeautifulSoup(html, "lxml")
    content = _find_main_content_after_tabnav(soup) or soup
    sections: list[dict[str, Any]] = []
    for table in content.select("table.tabinc.partydata"):
        sections.append(_parse_privaciu_section(table))

    return {
        "sections": sections,
    }


def _parse_turto_ir_pajamu_html(html: str) -> dict[str, Any]:
    def _parse_turto_section(table: Tag) -> dict[str, Any]:
        title = _extract_table_title(table)
        items: list[dict[str, Any]] = []

        for tr in table.find_all("tr"):
            cells = tr.find_all("td", recursive=False)
            if not cells:
                continue

            values = [_tag_text(cell) for cell in cells]
            if not any(values):
                continue

            row_links = [_extract_links(cell) for cell in cells]

            if len(values) == 1:
                key = values[0].rstrip(":")
                value = ""
                urls = row_links[0] if row_links else []
            else:
                key = values[0].rstrip(":")
                value = values[1]
                urls = row_links[1] if len(row_links) > 1 else []

            # Some tables repeat the section title as a one-cell row.
            if key == title and not value:
                continue

            items.append(
                {
                    "key": key,
                    "value": value,
                    "urls": urls,
                }
            )

        return {
            "title": title,
            "items": items,
        }

    soup = BeautifulSoup(html, "lxml")
    content = _find_main_content_after_tabnav(soup) or soup
    sections: list[dict[str, Any]] = []
    for table in content.select("table.tabinc"):
        sections.append(_parse_turto_section(table))
    return {
        "sections": sections,
    }


def _parse_kita_html(html: str) -> dict[str, Any]:
    soup = BeautifulSoup(html, "lxml")
    content = _find_main_content_after_tabnav(soup)
    return {
        "texts": _extract_non_empty_text_nodes(content),
        "links": _extract_links(content),
    }


def _parse_politines_kampanijos_html(html: str) -> dict[str, Any]:
    def _append_campaign_item(items: list[dict[str, Any]], key: str, value: str, urls: list[str]) -> None:
        key = normalize_space(key).rstrip(":")
        value = normalize_space(value)

        if not key and not value and not urls:
            return

        if items:
            last_item = items[-1]
            if not last_item.get("key") and not last_item.get("value") and not last_item.get("urls"):
                items[-1] = {"key": key, "value": value, "urls": urls}
                return

        items.append(
            {
                "key": key,
                "value": value,
                "urls": urls,
            }
        )

    def _parse_campaign_block(picklist: Tag) -> dict[str, Any]:
        title = _tag_text(picklist.find("h3"))
        items: list[dict[str, Any]] = []
        tables: list[dict[str, Any]] = []

        for child in picklist.children:
            if isinstance(child, NavigableString):
                text = normalize_space(str(child))
                if text:
                    _append_campaign_item(items, "", text, [])
                continue

            if not isinstance(child, Tag):
                continue

            if child.name == "h3":
                continue

            if child.name == "br":
                continue

            if child.name == "a":
                value = _tag_text(child)
                urls = _extract_links(child)
                if items and not items[-1].get("key") and items[-1].get("value"):
                    previous_value = str(items[-1].get("value", "")).rstrip(":")
                    items[-1] = {
                        "key": previous_value,
                        "value": value,
                        "urls": urls,
                    }
                else:
                    _append_campaign_item(items, "", value, urls)
                continue

            if child.name == "table":
                table_payload = _parse_generic_table(child)
                if table_payload.get("rowCount", 0):
                    tables.append(
                        {
                            "title": table_payload.get("title", ""),
                            "columns": table_payload.get("headers", []),
                            "rows": [row.get("values", []) for row in table_payload.get("rows", [])],
                        }
                    )

                for tr in child.find_all("tr"):
                    cells = tr.find_all("td", recursive=False)
                    if not cells:
                        continue

                    values = [_tag_text(cell) for cell in cells]
                    urls_by_cell = [_extract_links(cell) for cell in cells]
                    if not any(values) and not any(urls_by_cell):
                        continue

                    if len(cells) == 1:
                        notice_value = values[0]
                        if notice_value == title:
                            continue
                        _append_campaign_item(items, "", notice_value, urls_by_cell[0] if urls_by_cell else [])
                        continue

                    key = values[0]
                    value = values[1] if len(values) > 1 else ""
                    if key == title and not value:
                        continue
                    urls = urls_by_cell[1] if len(urls_by_cell) > 1 else []
                    _append_campaign_item(items, key, value, urls)
                continue

            text = _tag_text(child)
            if text:
                _append_campaign_item(items, "", text, _extract_links(child))

        return {
            "title": title,
            "items": items,
            "tables": tables,
        }

    header = _parse_campaign_header(html)
    return {
        "sectionDescription": header.get("sectionDescription", ""),
        "availableTabs": header.get("availableTabs", []),
        "participant": header.get("participant"),
        "treasurer": header.get("treasurer"),
        "auditor": header.get("auditor"),
    }


def _parse_campaign_sample_entry(entry: dict[str, Any]) -> dict[str, Any] | None:
    path = entry.get("path")
    if not isinstance(path, str) or not path:
        return None

    file_path = Path(path)
    if not file_path.exists():
        return None

    html = file_path.read_text(encoding="utf-8")
    header = _parse_campaign_header(html)
    parsed = _parse_campaign_tab_data(str(entry.get("slug", "")), html)
    return {
        "label": entry.get("label", ""),
        "slug": entry.get("slug", ""),
        "url": entry.get("url", ""),
        "data": parsed,
        "sectionDescription": header.get("sectionDescription", ""),
        "availableTabs": header.get("availableTabs", []),
        "participant": header.get("participant"),
        "treasurer": header.get("treasurer"),
        "auditor": header.get("auditor"),
    }


def _parse_nested_campaign_samples(
    candidate_meta: dict[str, Any] | None,
    root_campaign_data: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    if not isinstance(candidate_meta, dict):
        return []

    campaign_samples = candidate_meta.get("campaignSamples")
    if not isinstance(campaign_samples, list):
        return []

    parsed_campaigns: list[dict[str, Any]] = []
    for campaign in campaign_samples:
        if not isinstance(campaign, dict):
            continue

        tab_samples = campaign.get("tabSamples")
        nested_tabs: list[dict[str, Any]] = []

        if isinstance(tab_samples, list) and tab_samples:
            for tab in tab_samples:
                if not isinstance(tab, dict):
                    continue
                parsed_tab = _parse_campaign_sample_entry(tab)
                if parsed_tab is not None:
                    nested_tabs.append(parsed_tab)
        else:
            root_path = campaign.get("campaignRootPath")
            if isinstance(root_path, str) and root_path:
                parsed_root = _parse_campaign_sample_entry(
                    {
                        "label": "",
                        "slug": "root",
                        "url": campaign.get("campaignUrl", ""),
                        "path": root_path,
                    }
                )
                if parsed_root is not None:
                    nested_tabs.append(parsed_root)

        section_description = ""
        available_tabs: list[dict[str, Any]] = []
        participant = None
        treasurer = None
        auditor = None
        raw_tabs: list[dict[str, Any]] = []

        for tab in nested_tabs:
            if not section_description:
                section_description = str(tab.get("sectionDescription", ""))
            if not available_tabs and isinstance(tab.get("availableTabs"), list):
                available_tabs = tab.get("availableTabs", [])
            if participant is None and isinstance(tab.get("participant"), dict):
                participant = tab.get("participant")
            if treasurer is None and isinstance(tab.get("treasurer"), dict):
                treasurer = tab.get("treasurer")
            if auditor is None and isinstance(tab.get("auditor"), dict):
                auditor = tab.get("auditor")

            raw_tabs.append(
                {
                    "label": tab.get("label", ""),
                    "slug": tab.get("slug", ""),
                    "url": tab.get("url", ""),
                    "data": tab.get("data", {}),
                }
            )

        if isinstance(root_campaign_data, dict):
            if not section_description:
                section_description = str(root_campaign_data.get("sectionDescription", ""))
            if not available_tabs and isinstance(root_campaign_data.get("availableTabs"), list):
                available_tabs = root_campaign_data.get("availableTabs", [])
            if participant is None and isinstance(root_campaign_data.get("participant"), dict):
                participant = root_campaign_data.get("participant")
            if treasurer is None and isinstance(root_campaign_data.get("treasurer"), dict):
                treasurer = root_campaign_data.get("treasurer")
            if auditor is None and isinstance(root_campaign_data.get("auditor"), dict):
                auditor = root_campaign_data.get("auditor")

        parsed_campaigns.append(
            {
                "campaignKey": campaign.get("campaignKey", ""),
                "campaignLabel": campaign.get("campaignLabel", ""),
                "campaignUrl": campaign.get("campaignUrl", ""),
                "sectionDescription": section_description,
                "availableTabs": available_tabs,
                "participant": participant,
                "treasurer": treasurer,
                "auditor": auditor,
                "tabs": raw_tabs,
            }
        )

    return parsed_campaigns


def _parse_optional_subpages(
    candidate_dir: Path,
    candidate_id: str,
    candidate_source_url: str | None,
    anomalies: list[dict[str, Any]],
) -> dict[str, Any]:
    pages: dict[str, Any] = {}
    parser_map: dict[str, Any] = {
        "biografija": ("biografija.html", _parse_biografija_html),
        "privaciuInteresuDeklaracija": ("privaciu-interesu-deklaracija.html", _parse_privaciu_interesu_html),
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

        pages[key] = {
            "data": parsed_data,
        }

    return pages


def _load_candidate_meta(candidate_dir: Path) -> dict[str, Any]:
    index_path = candidate_dir / "index.json"
    if not index_path.exists():
        return {}

    try:
        payload = json.loads(index_path.read_text(encoding="utf-8"))
    except Exception:
        return {}

    if not isinstance(payload, dict):
        return {}
    return payload


def parse_anketa_sample(
    candidate_id: str,
    samples_root: Path = DEFAULT_SAMPLES_ROOT,
    output_root: Path = DEFAULT_OUTPUT_ROOT,
) -> tuple[Path, dict[str, Any]]:
    candidate_dir = samples_root / candidate_id
    anketa_path = candidate_dir / "anketa.html"
    if not anketa_path.exists():
        raise FileNotFoundError(f"Missing anketa sample: {anketa_path}")

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
        if data is not None:
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
        "source": {
            "candidateSourceUrl": candidate_source_url,
        },
        "rawData": raw_data,
        "normalized": _normalize_missing_values(normalized),
    }

    output_path = output_root / f"{candidate_id}-{ELECTION_ID}.json"
    write_json(output_path, output_payload)

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
