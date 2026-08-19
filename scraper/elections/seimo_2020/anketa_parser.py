from __future__ import annotations

from copy import deepcopy
import json
import re
import unicodedata
from pathlib import Path
from typing import Any

from bs4 import BeautifulSoup, NavigableString, Tag

from scraper.elections.seimo_2020.sitemap import ELECTION_ID, resolve_candidate_url
from scraper.elections.seimo_2016.anketa_parser import (
    _find_row_by_question_number,
    _load_candidate_meta,
    _normalize_campaigns,
    _normalize_kita_data,
    _normalize_missing_values,
    _normalize_profile_data,
    _normalize_table_records,
    _normalize_turto_ir_pajamu_data,
    _order_dict_keys,
    _parse_anketa_table,
    _parse_kita_html,
    _parse_nested_campaign_samples,
    _parse_politines_kampanijos_html,
    _parse_profile_table,
    _parse_tabnav,
    _parse_turto_ir_pajamu_html,
    _row_answer_text,
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

    # Mirrors seimo_2016: fold mixed unicode normalization forms to NFC so an
    # NFD "ė" string-matches its NFC form; rawData keeps the original bytes.
    normalized = normalize_space(unicodedata.normalize("NFC", value))
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


def _normalize_anketa_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    def _answer(question_number: str) -> str | None:
        return _normalize_text_value(
            _row_answer_text(_find_row_by_question_number(rows, question_number))
        )

    return {
        "adresas": _answer("6"),
        "kontaktai": {
            "telefonas": _answer("6.1"),
            "el-pastas": _answer("6.2"),
            "socialiniu-tinklu-paskyros": _answer("6.3"),
        },
        "einamos-pareigos": _answer("7"),
        # Q7.1 is answered inline ("Lietuvos valstiečių ir žaliųjų sąjungos
        # narė"), not with the membership table later elections use.
        "narystes-politinese-organizacijose": {
            "tekstas": _answer("7.1"),
        },
        "pareiskimai": {
            # Q8.x are the Seimo rinkimų įstatymo 38 str. 3 d. declarations and
            # Q9.x the 98 str. 1 ir 3 d. ones. Keys follow the 2016 module where
            # the question matches; Q8.2.1 and Q9.3-Q9.5 have no 2016
            # counterpart under the same number.
            "ar-nebaigta-teismo-paskirta-bausme": _answer("8.1"),
            "ar-atliekate-karo-tarnyba": _answer("8.2"),
            "ar-savanoriskos-karo-tarnybos-karys": _answer("8.2.1"),
            "ar-turite-kitos-valstybes-pilietybe": _answer("8.3"),
            "ar-susijes-priesaika-uzsienio-valstybei": _answer("8.4"),
            "ar-bendradarbiavote-su-uzsienio-tarnybomis": _answer("9.1"),
            "ar-buvote-pripazintas-kaltu": _answer("9.2"),
            "ar-veika-dekriminalizuota": _answer("9.3"),
            "ar-buvote-pripazintas-kaltu-uzsienyje": _answer("9.4"),
            "ar-buvote-pripazintas-kaltu-del-politinio-persekiojimo": _answer("9.5"),
        },
    }


def parse_anketa_html(html: str) -> dict[str, Any]:
    # The 2020 candidate page keeps the 2016-era layout, so the profile card is
    # read with the 2016 parser. The questionnaire, however, is numbered for the
    # 2020 Seimo rinkimų įstatymo: Q6.x contacts, Q7.x position and membership,
    # and declarations under Q8.x / Q9.x. The 2016 normalizer this module used
    # to borrow looked up 2016 numbers (9.3.1-9.3.4, 10-21), which dropped the
    # position, membership, contact and three declaration answers and emitted a
    # block of keys that can never be filled from a 2020 page.
    soup = BeautifulSoup(html, "lxml")

    tabnav = soup.select_one("ul#tabnav")
    profile_table = tabnav.find_previous("table") if tabnav is not None else soup.find("table")
    anketa_table = tabnav.find_next("table") if tabnav is not None else None

    profile = _parse_profile_table(profile_table)
    tabs = _parse_tabnav(tabnav)
    anketa = _parse_anketa_table(anketa_table)
    anketa["normalized"] = _normalize_anketa_rows(anketa["rows"])

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
                if len(values) == 1 and headers:
                    # A one-cell row in a header-bearing table is a data row
                    # of a single-column table (ID001A KITI DUOMENYS free
                    # text), not a label. Keep it unlabelled so the normalizer
                    # can collect it under "tekstas" instead of the whole
                    # sentence becoming a key.
                    items.append({"key": "", "value": values[0]})
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
            # A declaration section can be free text rather than key/value
            # pairs — ID001A KITI DUOMENYS is published as an unlabelled
            # sentence. Those rows reach here with an empty key; dropping them
            # for want of a key silently loses the whole declared text.
            free_text: list[str] = []
            for item in section["items"]:
                if not isinstance(item, dict):
                    continue
                item_key = _source_key(str(item.get("key", "")))
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


def _is_sprendimai_header_row(values: list[str]) -> bool:
    compact = [normalize_space(v).lower() for v in values if isinstance(v, str) and v.strip()]
    if not compact:
        return True

    joined = " ".join(compact)
    if "sprendimas" in joined and len(compact) <= 3:
        return True

    header_tokens = {"eil.", "nr.", "pavadinimas", "data", "numeris", "pastaba"}
    if header_tokens.intersection(compact):
        return True

    return False


def _transform_sprendimai_payload(data: Any) -> Any:
    if not isinstance(data, dict):
        return data

    blocks = data.get("blocks")
    if not isinstance(blocks, list):
        return data

    row_entries: list[list[str]] = []
    urls: list[str] = []

    for block in blocks:
        if not isinstance(block, dict):
            continue

        title = normalize_space(str(block.get("title", ""))).lower()
        if title == "links":
            raw_urls = block.get("urls")
            if isinstance(raw_urls, list):
                for url in raw_urls:
                    if not isinstance(url, str):
                        continue
                    value = normalize_space(url)
                    if value and value not in urls:
                        urls.append(value)
            continue

        rows = block.get("rows")
        if not isinstance(rows, list):
            continue

        for row in rows:
            if not isinstance(row, list):
                continue
            values = [normalize_space(str(cell)) for cell in row]
            if not any(values):
                continue
            row_entries.append(values)

    records: list[dict[str, Any]] = []
    for values in row_entries:
        if _is_sprendimai_header_row(values):
            continue

        record = {
            "rowNumber": values[0] if len(values) > 0 else "",
            "title": values[1] if len(values) > 1 else "",
            "date": values[2] if len(values) > 2 else "",
            "number": values[3] if len(values) > 3 else "",
            "note": values[4] if len(values) > 4 else "",
            "urls": [],
        }
        if not record["title"]:
            continue
        records.append(record)

    if not records and not urls:
        return {"records": []}

    for index, url in enumerate(urls):
        if index >= len(records):
            break
        records[index]["urls"] = [url]

    return {
        "records": records,
        "urls": urls,
    }


def _extract_table_links(cell: Tag) -> list[str]:
    urls: list[str] = []
    for anchor in cell.find_all("a"):
        for attr in ("data-download-href", "data-direct-href", "href"):
            href = anchor.get(attr)
            if not isinstance(href, str):
                continue
            value = normalize_space(href)
            if not value or value == "#":
                continue
            resolved = resolve_candidate_url(value)
            if resolved not in urls:
                urls.append(resolved)
    return urls


def _parse_auditoriaus_ataskaita_html(html: str) -> list[dict[str, Any]]:
    soup = BeautifulSoup(html, "lxml")

    report_table: Tag | None = None
    for table in soup.select("table.partydata"):
        title = _tag_text(table.find("h3"))
        if "Auditoriaus ataskaita" in title:
            report_table = table
            break

    if report_table is None:
        return []

    report_rows: list[dict[str, Any]] = []
    for tr in report_table.select("tr"):
        cells = tr.find_all("td", recursive=False)
        if len(cells) < 4:
            continue

        row_number = _tag_text(cells[0])
        status = _tag_text(cells[2]) if len(cells) > 2 else ""
        document_type = _tag_text(cells[3]) if len(cells) > 3 else ""
        urls = _extract_table_links(cells[4]) if len(cells) > 4 else []

        if not row_number or not status or not document_type:
            continue

        report_rows.append(
            {
                "rowNumber": row_number,
                "status": status,
                "documentType": document_type,
                "urls": urls,
            }
        )

    return report_rows


def _hydrate_auditor_reports_from_samples(
    campaigns: list[dict[str, Any]],
    candidate_dir: Path,
) -> list[dict[str, Any]]:
    hydrated: list[dict[str, Any]] = []
    for campaign in campaigns:
        if not isinstance(campaign, dict):
            continue

        campaign_payload = deepcopy(campaign)
        campaign_key = normalize_space(str(campaign_payload.get("campaignKey", "")))
        if not campaign_key:
            hydrated.append(campaign_payload)
            continue

        report_path = candidate_dir / "campaigns" / campaign_key / "auditorius.html"
        if not report_path.exists():
            hydrated.append(campaign_payload)
            continue

        reports = _parse_auditoriaus_ataskaita_html(report_path.read_text(encoding="utf-8"))
        if reports:
            auditor_payload = campaign_payload.get("auditor")
            if not isinstance(auditor_payload, dict):
                auditor_payload = {}
            auditor_payload["auditoriausAtaskaita"] = reports
            campaign_payload["auditor"] = auditor_payload

            tabs = campaign_payload.get("tabs")
            if isinstance(tabs, list):
                for tab in tabs:
                    if not isinstance(tab, dict):
                        continue
                    slug = normalize_space(str(tab.get("slug", ""))).lower()
                    if slug != "auditorius":
                        continue
                    if not tab.get("data"):
                        tab["data"] = reports

        hydrated.append(campaign_payload)

    return hydrated


def _transform_campaign_tabs_for_2020(campaigns: list[dict[str, Any]]) -> list[dict[str, Any]]:
    transformed: list[dict[str, Any]] = []
    for campaign in campaigns:
        if not isinstance(campaign, dict):
            continue

        campaign_payload = deepcopy(campaign)
        tabs = campaign_payload.get("tabs")
        if isinstance(tabs, list):
            for tab in tabs:
                if not isinstance(tab, dict):
                    continue
                slug = normalize_space(str(tab.get("slug", ""))).lower()
                if slug != "sprendimai":
                    continue
                tab["data"] = _transform_sprendimai_payload(tab.get("data"))

        transformed.append(campaign_payload)

    return transformed


def _normalize_sprendimai_records(payload: Any) -> list[dict[str, Any]]:
    if not isinstance(payload, dict):
        return []

    records = payload.get("records")
    if not isinstance(records, list):
        return []

    normalized_records: list[dict[str, Any]] = []
    for record in records:
        if not isinstance(record, dict):
            continue

        urls: list[str] = []
        raw_urls = record.get("urls")
        if isinstance(raw_urls, list):
            for url in raw_urls:
                if not isinstance(url, str):
                    continue
                value = normalize_space(url)
                if value:
                    urls.append(value)

        normalized_record = {
            "rowNumber": _normalize_text_value(record.get("rowNumber")),
            "title": _normalize_text_value(record.get("title")),
            "date": _normalize_text_value(record.get("date")),
            "number": _normalize_text_value(record.get("number")),
            "note": _normalize_text_value(record.get("note")),
            "urls": urls,
        }
        if normalized_record["title"] is None:
            continue
        normalized_records.append(normalized_record)

    return normalized_records


def _simplify_campaigns_for_raw_output(campaigns: list[dict[str, Any]]) -> list[dict[str, Any]]:
    tab_key_map = {
        "auku-ir-aukotoju-sarasas": "aukuIrAukotojuSarasas",
        "finansavimo-ataskaitos": "finansavimoAtaskaitos",
        "sutartys": "sutartys",
        "sprendimai": "sprendimai",
    }

    simplified: list[dict[str, Any]] = []
    for campaign in campaigns:
        if not isinstance(campaign, dict):
            continue

        simplified_campaign: dict[str, Any] = {
            "campaignKey": campaign.get("campaignKey", ""),
            "campaignLabel": campaign.get("campaignLabel", ""),
            "campaignUrl": campaign.get("campaignUrl", ""),
            "sectionDescription": campaign.get("sectionDescription", ""),
            "participant": campaign.get("participant"),
            "treasurer": campaign.get("treasurer"),
            "auditor": campaign.get("auditor"),
        }

        extra_sections: dict[str, Any] = {}
        tabs = campaign.get("tabs")
        if isinstance(tabs, list):
            for tab in tabs:
                if not isinstance(tab, dict):
                    continue

                slug = str(tab.get("slug", "")).strip()
                if not slug or slug == "izdininkas":
                    continue

                data = tab.get("data")
                if not isinstance(data, (dict, list)) or not data:
                    continue

                if slug == "auditorius":
                    auditor_payload = simplified_campaign.get("auditor")
                    if not isinstance(auditor_payload, dict):
                        auditor_payload = {}
                    auditor_payload["auditoriausAtaskaita"] = data
                    simplified_campaign["auditor"] = auditor_payload
                    continue

                mapped_key = tab_key_map.get(slug)
                if mapped_key is not None:
                    simplified_campaign[mapped_key] = data
                else:
                    extra_sections[slug] = data

        if extra_sections:
            simplified_campaign["kitiSkyriai"] = extra_sections

        simplified.append(simplified_campaign)

    return simplified


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

    nested_campaigns = _transform_campaign_tabs_for_2020(nested_campaigns)
    nested_campaigns = _hydrate_auditor_reports_from_samples(nested_campaigns, candidate_dir)

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

        simplified_campaigns = _simplify_campaigns_for_raw_output(nested_campaigns)

        full_campaign_payload = {
            "sectionDescription": section_description,
            "campaigns": nested_campaigns,
        }
        raw_data[campaign_key] = {
            "sectionDescription": section_description,
            "campaigns": simplified_campaigns,
        }
        normalized_campaigns = _normalize_campaigns(full_campaign_payload)
        if isinstance(normalized_campaigns, list):
            for index, campaign in enumerate(normalized_campaigns):
                if not isinstance(campaign, dict):
                    continue
                if index >= len(simplified_campaigns):
                    continue
                raw_campaign = simplified_campaigns[index]
                if not isinstance(raw_campaign, dict):
                    continue

                sprendimai_payload = raw_campaign.get("sprendimai")
                normalized_sprendimai = _normalize_sprendimai_records(sprendimai_payload)
                if normalized_sprendimai:
                    campaign["sprendimai"] = normalized_sprendimai

        normalized["politines-kampanijos-dalyvio-duomenys"] = normalized_campaigns
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