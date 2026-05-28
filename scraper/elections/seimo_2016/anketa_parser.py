from __future__ import annotations

import json
from pathlib import Path
import re
from typing import Any

from bs4 import BeautifulSoup, NavigableString, Tag

from scraper.elections.seimo_2016.sitemap import ELECTION_ID, resolve_candidate_url
from scraper.shared.files import slugify, write_json

DEFAULT_SAMPLES_ROOT = Path("samples/html/2016-seimo")
DEFAULT_OUTPUT_ROOT = Path("data/2016-seimo")


def normalize_space(value: str) -> str:
    return " ".join(value.split())


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
    if not value:
        return []
    parts = [normalize_space(item) for item in value.split(",")]
    return [item for item in parts if item]


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


def _normalize_anketa_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    q5 = _find_row_by_question_number(rows, "5")
    q6 = _find_row_by_question_number(rows, "6")
    q8_1 = _find_row_by_question_number(rows, "8.1")
    q8_2 = _find_row_by_question_number(rows, "8.2")
    q8_3 = _find_row_by_question_number(rows, "8.3")
    q8_4 = _find_row_by_question_number(rows, "8.4")
    q9_1 = _find_row_by_question_number(rows, "9.1")
    q9_2 = _find_row_by_question_number(rows, "9.2")
    q9_2_followup = _find_row_by_prompt_prefix(rows, "tai nurodoma šioje anketoje")
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
        "birthDate": _row_answer_text(q5),
        "residenceAddress": _row_answer_text(q6),
        "declarations": {
            "unfinishedSentence": _row_answer_text(q8_1),
            "activeServiceOfficer": _row_answer_text(q8_2),
            "otherCitizenship": _row_answer_text(q8_3),
            "foreignOath": _row_answer_text(q8_4),
            "cooperationWithForeignServices": _row_answer_text(q9_1),
            "convictionQuestion": _row_answer_text(q9_2),
            "convictionAnswer": _row_answer_text(q9_2_followup),
            "decriminalizedOffense": _row_answer_text(q9_3_1),
            "foreignCourtNonCriminal": _row_answer_text(q9_3_2),
            "politicalPersecution": _row_answer_text(q9_3_3),
            "legalArguments": _row_answer_text(q9_3_4),
        },
        "birthPlace": _row_answer_text(q10),
        "nationality": _row_answer_text(q11),
        "education": {
            "summary": _row_answer_text(q12),
            "records": _first_nested_table_rows(q12),
        },
        "pedagogicalTitleOrDegree": _row_answer_text(pedagogical),
        "foreignLanguages": _split_list_value(_row_answer_text(q13)),
        "partyMembership": _row_answer_text(q14),
        "previousElectedPositions": {
            "summary": _row_answer_text(q15),
            "records": _first_nested_table_rows(q15),
        },
        "primaryWorkplace": _row_answer_text(q16),
        "socialActivities": _row_answer_text(q17),
        "hobbies": _row_answer_text(q18),
        "maritalStatus": _row_answer_text(q19),
        "spouseName": _row_answer_text(spouse),
        "children": _row_answer_text(q20),
        "aboutSelf": _row_answer_text(q21),
    }


def _parse_anketa_table(table: Tag | None) -> dict[str, Any]:
    if table is None:
        return {
            "rows": [],
            "stats": {
                "rowCount": 0,
                "answeredRowCount": 0,
                "rowsWithNestedTables": 0,
            },
        }

    parsed_rows: list[dict[str, Any]] = []
    answered_count = 0

    body = table.find("tbody")
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

    normalized = _normalize_anketa_rows(parsed_rows)

    return {
        "rows": parsed_rows,
        "normalized": normalized,
        "stats": {
            "rowCount": len(parsed_rows),
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

    registration = _parse_registration_details(notices[0] if notices else "")
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


def _parse_donations_table(table: Tag) -> dict[str, Any]:
    records: list[dict[str, Any]] = []
    summary: list[dict[str, Any]] = []

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
        if re.match(r"^\d+\.$", first_value) and len(values) >= 7:
            amount_text = values[5]
            records.append(
                {
                    "rowNumber": first_value,
                    "donor": values[1],
                    "municipality": values[2],
                    "date": values[3],
                    "incomeSourceCode": values[4],
                    "amountText": amount_text,
                    "amount": _parse_decimal_value(amount_text),
                    "notes": values[6],
                }
            )
            continue

        if len(values) >= 2:
            summary.append(
                {
                    "label": first_value.rstrip(":"),
                    "amountText": values[1],
                    "amount": _parse_decimal_value(values[1]),
                    "note": values[2] if len(values) > 2 else "",
                }
            )

    totals: dict[str, Any] = {}
    for item in summary:
        key = _build_campaign_title_key(str(item.get("label", "")))
        if key:
            totals[key] = item.get("amount")

    return {
        "records": records,
        "summary": summary,
        "totals": totals,
    }


def _parse_campaign_donations_html(html: str) -> dict[str, Any]:
    soup = BeautifulSoup(html, "lxml")
    content = _extract_content_picklist(soup)
    if content is None:
        return {"sections": []}

    sections: list[dict[str, Any]] = []
    current_title = ""

    for child in content.children:
        if isinstance(child, NavigableString):
            text = normalize_space(str(child))
            if not text or not current_title:
                continue
            sections.append({"title": current_title, "status": "noData", "message": text})
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
            current_title = _tag_text(child).rstrip(":")
            continue

        if child.name == "table" and current_title:
            parsed_table = _parse_donations_table(child)
            sections.append({"title": current_title, **parsed_table})
            current_title = ""
            continue

        text = _tag_text(child)
        if text and current_title:
            sections.append({"title": current_title, "status": "noData", "message": text})
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


def _normalize_campaigns(raw_campaign_data: dict[str, Any]) -> dict[str, Any]:
    campaigns = raw_campaign_data.get("campaigns")
    if not isinstance(campaigns, list):
        return {"campaigns": []}

    normalized_campaigns: list[dict[str, Any]] = []
    for campaign in campaigns:
        if not isinstance(campaign, dict):
            continue

        tabs = campaign.get("tabs", [])
        donations: dict[str, Any] = {}
        financing_reports: list[dict[str, Any]] = []
        contracts: list[dict[str, Any]] = []
        tab_slugs: list[str] = []

        if isinstance(tabs, list):
            for tab in tabs:
                if not isinstance(tab, dict):
                    continue
                slug = str(tab.get("slug", ""))
                if slug:
                    tab_slugs.append(slug)
                data = tab.get("data")
                if not isinstance(data, dict):
                    continue
                if slug == "auku-ir-aukotoju-sarasas":
                    for section in data.get("sections", []):
                        if not isinstance(section, dict):
                            continue
                        section_key = _build_campaign_title_key(str(section.get("title", "")))
                        if section_key:
                            donations[section_key] = section
                elif slug == "finansavimo-ataskaitos":
                    financing_reports = data.get("reports", []) if isinstance(data.get("reports"), list) else []
                elif slug == "sutartys":
                    contracts = data.get("contracts", []) if isinstance(data.get("contracts"), list) else []

        participant = campaign.get("participant") if isinstance(campaign.get("participant"), dict) else {}
        normalized_campaigns.append(
            {
                "campaignKey": campaign.get("campaignKey", ""),
                "campaignLabel": campaign.get("campaignLabel", ""),
                "campaignUrl": campaign.get("campaignUrl", ""),
                "status": participant.get("status", ""),
                "participantType": participant.get("participantType", ""),
                "registeredDate": participant.get("registeredDate", ""),
                "decisionNumber": participant.get("decisionNumber", ""),
                "contact": {
                    "inquiryPhone": participant.get("inquiryPhone", ""),
                    "email": participant.get("email", ""),
                },
                "treasurer": campaign.get("treasurer", {}),
                "auditor": campaign.get("auditor", {}),
                "tabSlugs": tab_slugs,
                "donations": donations,
                "financingReports": financing_reports,
                "contracts": contracts,
            }
        )

    return {"campaigns": normalized_campaigns}


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
        "sourcePath": path,
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
                    "sourcePath": tab.get("sourcePath", ""),
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
                "campaignDir": campaign.get("campaignDir", ""),
                "sectionDescription": section_description,
                "availableTabs": available_tabs,
                "participant": participant,
                "treasurer": treasurer,
                "auditor": auditor,
                "tabs": raw_tabs,
            }
        )

    return parsed_campaigns


def _parse_optional_subpages(candidate_dir: Path) -> dict[str, Any]:
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
        pages[key] = {
            "sourcePath": str(path),
            "data": parser(html),
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
    subpages = _parse_optional_subpages(candidate_dir)
    meta = _load_candidate_meta(candidate_dir)
    candidate_meta = meta.get("candidate", {}) if isinstance(meta, dict) else {}
    root_campaign_data = subpages.get("politinesKampanijosDalyvioDuomenys", {}).get("data")
    nested_campaigns = _parse_nested_campaign_samples(
        meta if isinstance(meta, dict) else None,
        root_campaign_data if isinstance(root_campaign_data, dict) else None,
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
        "anketa": parsed["anketa"]["normalized"],
    }

    page_samples: dict[str, str] = {"anketa": str(anketa_path)}
    for key, payload in subpages.items():
        if not isinstance(payload, dict):
            continue
        data = payload.get("data")
        source_path = payload.get("sourcePath")
        if data is not None:
            if key != "politinesKampanijosDalyvioDuomenys":
                raw_data[key] = data
            if key == "privaciuInteresuDeklaracija" and isinstance(data, dict):
                sections = data.get("sections")
                if isinstance(sections, list):
                    by_section_id = _index_sections_by_id(sections)
                    normalized["privaciuInteresuDeklaracija"] = {
                        "bySectionId": by_section_id,
                    }
        if isinstance(source_path, str) and source_path:
            page_samples[key] = source_path

    if nested_campaigns:
        campaign_key = "politinesKampanijosDalyvioDuomenys"
        section_description = ""
        if isinstance(root_campaign_data, dict):
            section_description = str(root_campaign_data.get("sectionDescription", ""))

        raw_data[campaign_key] = {
            "sectionDescription": section_description,
            "campaigns": nested_campaigns,
        }
        normalized[campaign_key] = _normalize_campaigns(raw_data[campaign_key])

        for campaign in nested_campaigns:
            campaign_dir = campaign.get("campaignDir")
            campaign_key_value = campaign.get("campaignKey", "")
            if isinstance(campaign_dir, str) and campaign_dir and campaign_key_value:
                page_samples[f"campaign::{campaign_key_value}"] = campaign_dir
    elif isinstance(root_campaign_data, dict):
        campaign_key = "politinesKampanijosDalyvioDuomenys"
        raw_data[campaign_key] = root_campaign_data

    output_payload = {
        "electionId": ELECTION_ID,
        "candidateId": candidate_id,
        "candidateName": candidate_name,
        "source": {
            "samplePath": str(anketa_path),
            "candidateSourceUrl": candidate_meta.get("url") if isinstance(candidate_meta, dict) else None,
            "pageSamples": page_samples,
        },
        "rawData": raw_data,
        "normalized": normalized,
    }

    output_path = output_root / f"{candidate_id}-{ELECTION_ID}.json"
    write_json(output_path, output_payload)

    anketa_stats = parsed["anketa"]["stats"]
    stats = {
        "candidateId": candidate_id,
        "candidateName": candidate_name,
        "outputPath": str(output_path),
        "rowCount": anketa_stats["rowCount"],
        "answeredRowCount": anketa_stats["answeredRowCount"],
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
