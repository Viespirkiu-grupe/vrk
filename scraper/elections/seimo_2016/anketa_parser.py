from __future__ import annotations

import json
from pathlib import Path
import re
from typing import Any

from bs4 import BeautifulSoup, Tag

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


def _extract_links(container: Tag | None) -> list[str]:
    if container is None:
        return []

    links: list[str] = []
    for anchor in container.find_all("a", href=True):
        href = normalize_space(anchor.get("href", ""))
        links.append(resolve_candidate_url(href))
    return links


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


def _parse_privaciu_interesu_html(html: str) -> dict[str, Any]:
    soup = BeautifulSoup(html, "lxml")
    content = _find_main_content_after_tabnav(soup) or soup
    sections: list[dict[str, Any]] = []
    by_section_id: dict[str, Any] = {}
    for table in content.select("table.tabinc.partydata"):
        heading = _tag_text(table.find("h4"))
        parsed = _parse_generic_table(table, title=heading)
        parsed["heading"] = heading

        section_id = _extract_section_id(heading, str(parsed.get("title", "")))
        parsed["sectionId"] = section_id

        if section_id:
            existing = by_section_id.get(section_id)
            if existing is None:
                by_section_id[section_id] = parsed
            elif isinstance(existing, list):
                existing.append(parsed)
            else:
                by_section_id[section_id] = [existing, parsed]

        sections.append(parsed)
    return {
        "sections": sections,
        "bySectionId": by_section_id,
    }


def _parse_turto_ir_pajamu_html(html: str) -> dict[str, Any]:
    soup = BeautifulSoup(html, "lxml")
    content = _find_main_content_after_tabnav(soup) or soup
    sections: list[dict[str, Any]] = []
    for table in content.select("table.tabinc"):
        sections.append(_parse_generic_table(table))
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
    soup = BeautifulSoup(html, "lxml")
    section_description = _tag_text(soup.select_one("div.sectionDescription"))
    tab_links = _parse_tabnav(soup.select_one("ul#tabnav"))

    picklists: list[dict[str, Any]] = []
    for picklist in soup.select("div.picklist"):
        picklist_title = _tag_text(picklist.find("h3"))
        picklist_texts = _extract_non_empty_text_nodes(picklist)
        tables = [_parse_generic_table(table) for table in picklist.select("table.partydata")]
        picklists.append(
            {
                "title": picklist_title,
                "texts": picklist_texts,
                "tables": tables,
            }
        )

    tables = [_parse_generic_table(table) for table in soup.select("table.partydata")]

    return {
        "sectionDescription": section_description,
        "tabLinks": tab_links,
        "picklists": picklists,
        "tables": tables,
    }


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
            raw_data[key] = data
            if key == "privaciuInteresuDeklaracija" and isinstance(data, dict):
                by_section_id = data.get("bySectionId")
                if isinstance(by_section_id, dict):
                    normalized["privaciuInteresuDeklaracija"] = {
                        "bySectionId": by_section_id,
                    }
        if isinstance(source_path, str) and source_path:
            page_samples[key] = source_path

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
