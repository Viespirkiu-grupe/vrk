from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from bs4 import BeautifulSoup, NavigableString, Tag

from scraper.elections.seimo_2020.sitemap import ELECTION_ID
from scraper.elections.seimo_2016.anketa_parser import (
    _load_candidate_meta,
    _normalize_campaigns,
    _normalize_kita_data,
    _normalize_missing_values,
    _normalize_profile_data,
    _normalize_table_records,
    _normalize_turto_ir_pajamu_data,
    _order_dict_keys,
    _parse_kita_html,
    _parse_nested_campaign_samples,
    _parse_politines_kampanijos_html,
    _parse_turto_ir_pajamu_html,
    parse_anketa_html,
)
from scraper.shared.anomalies import build_anomaly_event
from scraper.shared.files import slugify, write_json

DEFAULT_SAMPLES_ROOT = Path("samples/html/2020-seimo")
DEFAULT_OUTPUT_ROOT = Path("data/2020-seimo")
MISSING_TEXT_VALUES = {
    "",
    "-",
    "nenurodė",
    "nenurode",
}


def normalize_space(value: str) -> str:
    return " ".join(value.split())


def _source_key(label: str) -> str:
    return slugify(normalize_space(label).rstrip(":"))


def _normalize_text_value(value: Any) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        value = str(value)

    normalized = normalize_space(value)
    if normalized.lower() in MISSING_TEXT_VALUES:
        return None
    return normalized


def _tag_text(tag: Tag | None) -> str:
    if tag is None:
        return ""
    return normalize_space(tag.get_text(" ", strip=True))


def _find_main_content_after_tabnav(soup: BeautifulSoup) -> Tag | None:
    tabnav = soup.select_one("ul#tabnav")
    if tabnav is None:
        return None

    for sibling in tabnav.next_siblings:
        if isinstance(sibling, Tag) and sibling.name == "div":
            return sibling
    return tabnav.find_next("div")


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


def _parse_nested_table(table: Tag) -> dict[str, Any]:
    headers = _extract_table_headers(table)
    rows: list[dict[str, Any]] = []

    body = table.find("tbody", recursive=False)
    if body is not None:
        tr_nodes = body.find_all("tr", recursive=False)
    else:
        tr_nodes = table.find_all("tr", recursive=False)

    for tr in tr_nodes:
        cells = tr.find_all(["td", "th"], recursive=False)
        if not cells:
            continue
        if any(cell.name == "th" for cell in cells):
            continue

        values = [_tag_text(cell) for cell in cells]
        if not any(values):
            continue

        if headers and len(values) == len(headers):
            normalized_row: dict[str, str] = {}
            for index, value in enumerate(values):
                key = _source_key(headers[index]) or f"stulpelis-{index + 1}"
                normalized_row[key] = value
            rows.append(normalized_row)
        else:
            rows.append({f"stulpelis-{index + 1}": value for index, value in enumerate(values)})

    return {
        "headers": headers,
        "rows": rows,
        "rowCount": len(rows),
    }


def _split_birth_value(value: str | None) -> tuple[str | None, str | None]:
    normalized = _normalize_text_value(value)
    if not normalized:
        return None, None

    parts = [part.strip() for part in normalized.split(",", 1)]
    if len(parts) == 2:
        return _normalize_text_value(parts[0]), _normalize_text_value(parts[1])

    return normalized, None


def _split_list_value(value: str | None) -> list[str]:
    normalized = _normalize_text_value(value)
    if not normalized:
        return []

    parts = [part.strip() for part in normalized.split(",")]
    values: list[str] = []
    for part in parts:
        item = _normalize_text_value(part)
        if item is None:
            continue
        values.append(item)
    return values


def _extract_question_number(prompt: str) -> str:
    match = re.match(r"^\s*(\d+(?:\.\d+)*)(?:\.)?\s*", prompt)
    if not match:
        return ""
    return match.group(1)


def _first_scalar_answer(answers: list[Any]) -> str | None:
    for answer in answers:
        if not isinstance(answer, str):
            continue
        normalized = _normalize_text_value(answer)
        if normalized is not None:
            return normalized
    return None


def _first_table_rows(answers: list[Any]) -> list[dict[str, Any]]:
    for answer in answers:
        if not isinstance(answer, list):
            continue

        rows = [row for row in answer if isinstance(row, dict)]
        if rows:
            return rows
    return []


def _parse_biografija_html(html: str) -> dict[str, Any]:
    soup = BeautifulSoup(html, "lxml")
    content = _find_main_content_after_tabnav(soup)
    outer_table = content.find("table") if content is not None else None

    rows: list[dict[str, Any]] = []
    pending_heading: dict[str, str] | None = None

    if outer_table is not None:
        tbody = outer_table.find("tbody", recursive=False)
        if tbody is not None:
            tr_nodes = tbody.find_all("tr", recursive=False)
        else:
            tr_nodes = outer_table.find_all("tr", recursive=False)

        for tr in tr_nodes:
            cell = tr.find("td", recursive=False)
            if cell is None:
                continue

            nested_tables = cell.find_all("table")
            prompt = _build_prompt_text(cell)
            question_number = _extract_question_number(prompt)
            answer = _extract_answer_text(cell, nested_tables)

            if nested_tables:
                if not prompt and pending_heading is not None:
                    prompt = pending_heading.get("prompt", "")
                if not question_number and pending_heading is not None:
                    question_number = pending_heading.get("questionNumber", "")

                table_rows: list[dict[str, Any]] = []
                for nested_table in nested_tables:
                    parsed_table = _parse_nested_table(nested_table)
                    for row in parsed_table.get("rows", []):
                        if isinstance(row, dict):
                            table_rows.append(row)

                rows.append(
                    {
                        "rowIndex": len(rows) + 1,
                        "questionNumber": question_number,
                        "prompt": normalize_space(prompt),
                        "answer": table_rows,
                    }
                )
                pending_heading = None
                continue

            normalized_prompt = normalize_space(prompt)
            rows.append(
                {
                    "rowIndex": len(rows) + 1,
                    "questionNumber": question_number,
                    "prompt": normalized_prompt,
                    "answer": answer,
                }
            )

            if normalized_prompt and not answer:
                pending_heading = {
                    "questionNumber": question_number,
                    "prompt": normalized_prompt.rstrip(":"),
                }
            else:
                pending_heading = None

    return {
        "rows": rows,
    }


def _normalize_biografija_data(payload: dict[str, Any]) -> dict[str, Any]:
    rows = payload.get("rows") if isinstance(payload.get("rows"), list) else []
    by_question: dict[str, list[Any]] = {}

    for row in rows:
        if not isinstance(row, dict):
            continue

        question_number = _normalize_text_value(row.get("questionNumber"))
        if not question_number:
            continue

        answer = row.get("answer")
        by_question.setdefault(question_number, []).append(answer)

    birth_date, birth_place = _split_birth_value(_first_scalar_answer(by_question.get("1", [])))
    education_rows = _normalize_table_records(_first_table_rows(by_question.get("3", [])))
    work_rows = _normalize_table_records(_first_table_rows(by_question.get("5", [])))

    result: dict[str, Any] = {
        "gimimo-data": birth_date,
        "gimimo-vieta": birth_place,
        "tautybe": _first_scalar_answer(by_question.get("2", [])),
        "issilavinimas": {
            "irasai": education_rows,
        },
        "mokslo-laipsnis": _first_scalar_answer(by_question.get("3.1", [])),
        "pedagoginis-vardas": _first_scalar_answer(by_question.get("3.2", [])),
        "uzsienio-kalbos": _split_list_value(_first_scalar_answer(by_question.get("4", []))),
        "darbo-patirtis": {
            "irasai": work_rows,
        },
        "moksline-pedagogine-visuomenine-veikla": _first_scalar_answer(by_question.get("6", [])),
        "pomegiai": _first_scalar_answer(by_question.get("7", [])),
        "seimine-padetis": _first_scalar_answer(by_question.get("8", [])),
        "sutuoktinio-vardas-pavarde": _first_scalar_answer(by_question.get("8.1", [])),
        "vaiku-vardai-pavardes": _first_scalar_answer(by_question.get("8.2", [])),
        "kita-apie-save": _first_scalar_answer(by_question.get("9", [])),
    }

    return result


def _parse_privaciu_interesu_html(html: str) -> dict[str, Any]:
    def _extract_section_title(table: Tag) -> str:
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
        cells = first_row.find_all("td", recursive=False)
        if len(cells) == 1:
            return _tag_text(cells[0]).rstrip(":")
        return ""

    def _extract_section_id(title: str) -> str:
        match = re.search(r"\b(ID\d{3}[A-Z])\b", title)
        return match.group(1).lower() if match else ""

    def _parse_section(table: Tag) -> dict[str, Any]:
        title = _extract_section_title(table)
        section_id = _extract_section_id(title)
        headers = _extract_table_headers(table)

        row_payloads: list[list[str]] = []
        for tr in table.find_all("tr"):
            cells = tr.find_all("td", recursive=False)
            if not cells:
                continue
            values = [_tag_text(cell) for cell in cells]
            if not any(values):
                continue
            row_payloads.append(values)

        section: dict[str, Any] = {"title": title, "sectionId": section_id}

        is_key_value = bool(row_payloads) and all(len(v) <= 2 for v in row_payloads)
        if is_key_value:
            items: list[dict[str, str]] = []
            for values in row_payloads:
                key = values[0].rstrip(":")
                value = values[1] if len(values) > 1 else ""
                if key == title and not value:
                    continue
                items.append({"key": key, "value": value})
            section["items"] = items
        else:
            section["columns"] = headers
            section["rows"] = row_payloads

        return section

    soup = BeautifulSoup(html, "lxml")
    content = _find_main_content_after_tabnav(soup) or soup
    sections = [_parse_section(t) for t in content.select("table.tabinc.partydata")]
    return {"sections": sections}


def _normalize_privaciu_interesu_data(payload: dict[str, Any]) -> dict[str, Any]:
    def _source_key(label: str) -> str:
        return slugify(normalize_space(label).rstrip(":"))

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
            for item in section["items"]:
                if not isinstance(item, dict):
                    continue
                item_key = _source_key(str(item.get("key", "")))
                item_value = _normalize_text_value(item.get("value"))
                if item_key:
                    item_values[item_key] = item_value
            if item_values:
                normalized_section = item_values

        normalized_columns: list[str] = []
        if isinstance(section.get("columns"), list):
            normalized_columns = [
                v for v in (_normalize_text_value(c) for c in section["columns"]) if v is not None
            ]

        if isinstance(section.get("rows"), list):
            normalized_rows: list[dict[str, Any]] = []
            for row in section["rows"]:
                if not isinstance(row, list):
                    continue
                effective = normalized_columns
                if len(normalized_columns) == len(row) + 1:
                    effective = normalized_columns[1:]
                row_obj: dict[str, Any] = {}
                for i, val in enumerate(row):
                    label = effective[i] if i < len(effective) else f"stulpelis-{i + 1}"
                    key = _source_key(label) or f"stulpelis-{i + 1}"
                    row_obj[key] = _normalize_text_value(val)
                if row_obj:
                    normalized_rows.append(row_obj)
            if normalized_rows:
                normalized_section = normalized_rows

        if isinstance(normalized_section, dict) and "deklaruojantis-asmuo" in normalized_section:
            result.update(normalized_section)
            continue

        if section_key.startswith("sekcija-"):
            continue

        result[section_key] = normalized_section

    return result


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