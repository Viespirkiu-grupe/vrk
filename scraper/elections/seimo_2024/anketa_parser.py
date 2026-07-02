from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

from bs4 import BeautifulSoup, Tag

from scraper.elections.seimo_2024.sitemap import ELECTION_ID, resolve_candidate_url
from scraper.elections.seimo_2016.anketa_parser import (
    _find_row_by_question_number,
    _load_candidate_meta,
    _normalize_campaigns,
    _normalize_kita_data,
    _normalize_missing_values,
    _normalize_profile_data,
    _normalize_table_records,
    _order_dict_keys,
    _parse_eur_amount,
    _parse_kita_html,
    _parse_nested_campaign_samples,
    _parse_nested_table,
    _parse_politines_kampanijos_html,
    _row_answer_text,
    parse_anketa_html,
    parse_question_number,
)
from scraper.shared.anomalies import build_anomaly_event
from scraper.shared.files import slugify, write_json

DEFAULT_SAMPLES_ROOT = Path("samples/html/2024-seimo")
DEFAULT_OUTPUT_ROOT = Path("data/2024-seimo")
MISSING_TEXT_VALUES = {
    "",
    "-",
    "nenurodė",
    "nenurode",
}

# The 2024 pages carry the same asset labels as the 2024 EP pages ("I.
# Privalomas registruoti turtas" ...) and the same two GPM311 income summary
# labels, so the alias table matches the 2024 EP module.
TURTO_PAJAMU_KEY_ALIASES = {
    "i-privalomas-registruoti-turtas": "privalomas-registruoti-turtas",
    "ii-vertybiniai-popieriai-meno-kuriniai-juvelyriniai-dirbiniai": "vertybiniai-popieriai-meno-kuriniai-juvelyriniai-dirbiniai",
    "iii-pinigines-lesos": "pinigines-lesos",
    "iv-suteiktos-paskolos": "suteiktos-paskolos",
    "v-gautos-paskolos": "gautos-paskolos",
    "deklaruota-apmokestinamuju-ir-neapmokestinamuju-pajamu-suma": "gautos-pajamos",
    "deklaruota-moketina-pajamu-mokescio-suma": "sumoketas-pajamu-mokestis",
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


def _record_groups_for_question(rows: list[dict[str, Any]], question_number: str) -> list[list[Any]]:
    # Record tables ("2. Išsilavinimas:", "4. Darbo patirtis:") are rendered
    # in their own <tr> right after the question row, so each table lands in
    # a separate parsed row without a question number. Collect every
    # consecutive such row; one group per table.
    row = _find_row_by_question_number(rows, question_number)
    if row is None:
        return []

    groups: list[list[Any]] = []
    answer = row.get("answer")
    if isinstance(answer, list) and answer:
        groups.append(answer)

    index = rows.index(row)
    for next_row in rows[index + 1:]:
        if next_row.get("questionNumber") or not isinstance(next_row.get("answer"), list):
            break
        groups.append(next_row["answer"])

    return groups


def _records_for_question(rows: list[dict[str, Any]], question_number: str) -> list[Any]:
    records: list[Any] = []
    for group in _record_groups_for_question(rows, question_number):
        records.extend(group)
    return records


def _parse_biografija_html(html: str) -> dict[str, Any]:
    soup = BeautifulSoup(html, "lxml")
    tabnav = soup.select_one("ul#tabnav")
    outer_table = tabnav.find_next("table") if tabnav is not None else None

    rows: list[dict[str, Any]] = []
    if outer_table is None:
        return {"rows": rows}

    body = outer_table.find("tbody", recursive=False)
    if body is not None:
        tr_nodes = body.find_all("tr", recursive=False)
    else:
        tr_nodes = outer_table.find_all("tr", recursive=False)

    for tr in tr_nodes:
        cell = tr.find("td", recursive=False)
        if cell is None:
            continue

        nested_tables = cell.find_all("table")
        prompt = _build_prompt_text(cell)
        question_number = parse_question_number(prompt)

        if nested_tables:
            table_rows: list[Any] = []
            for nested_table in nested_tables:
                parsed_table = _parse_nested_table(nested_table)
                table_rows.extend(parsed_table.get("rows", []))

            # Record tables ("2. Išsilavinimas:", "4. Darbo patirtis:") sit in
            # their own row right below the heading row; attach them to it.
            if not prompt and rows and not rows[-1]["answer"]:
                rows[-1]["answer"] = table_rows
                continue

            rows.append(
                {
                    "rowIndex": len(rows) + 1,
                    "questionNumber": question_number,
                    "prompt": prompt,
                    "answer": table_rows,
                }
            )
            continue

        answer = _extract_answer_text(cell, [])
        if not prompt and not answer:
            continue

        rows.append(
            {
                "rowIndex": len(rows) + 1,
                "questionNumber": question_number,
                "prompt": prompt,
                "answer": answer,
            }
        )

    return {"rows": rows}


def _normalize_biografija_data(payload: dict[str, Any]) -> dict[str, Any]:
    rows = payload.get("rows") if isinstance(payload.get("rows"), list) else []

    def _answer(question_number: str) -> str | None:
        return _normalize_text_value(
            _row_answer_text(_find_row_by_question_number(rows, question_number))
        )

    birth_date, birth_place = _split_birth_value(_answer("1"))

    return {
        "gimimo-data": birth_date,
        "gimimo-vieta": birth_place,
        "issilavinimas": {
            "irasai": _normalize_table_records(_records_for_question(rows, "2")),
        },
        "mokslo-laipsnis": _answer("2.1"),
        "pedagoginis-vardas": _answer("2.2"),
        "uzsienio-kalbos": _split_list_value(_answer("3")),
        "darbo-patirtis": {
            "irasai": _normalize_table_records(_records_for_question(rows, "4")),
        },
        "visuomenine-veikla": _answer("5"),
        "pomegiai": _answer("6"),
        "seimine-padetis": _answer("7"),
    }


def _parse_turto_ir_pajamu_html(html: str) -> dict[str, Any]:
    soup = BeautifulSoup(html, "lxml")
    tabnav = soup.select_one("ul#tabnav")
    if tabnav is None:
        return {"sections": []}

    sections: list[dict[str, Any]] = []
    for table in tabnav.find_next_siblings("table"):
        title = ""
        items: list[dict[str, str]] = []

        for tr in table.find_all("tr"):
            cells = tr.find_all("td", recursive=False)
            if not cells:
                continue

            prompt = normalize_space(
                " ".join(_build_prompt_text(cell) for cell in cells)
            )
            answers = [_extract_answer_text(cell, []) for cell in cells]
            answer = " | ".join(value for value in answers if value)

            if not prompt and not answer:
                continue

            # Bold-only rows are the declaration heading ("METINĖS ...
            # IŠRAŠAS (2023 m.)") and form labels ("GPM311 formos
            # deklaracijos:"); the first one names the section.
            if not prompt:
                if not title:
                    title = answer
                continue

            items.append({"key": prompt.rstrip(":").rstrip("–").strip(), "value": answer})

        sections.append({"title": title, "items": items})

    return {"sections": sections}


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
            source_key = _source_key(str(item.get("key", "")))
            target_key = TURTO_PAJAMU_KEY_ALIASES.get(source_key)
            if target_key is None:
                continue
            normalized_fields[target_key] = _parse_eur_amount(item.get("value"))

    return normalized_fields


def _parse_privaciu_record_table(table: Tag) -> dict[str, Any]:
    record_type = ""
    th = table.find("th")
    if th is not None:
        record_type = _tag_text(th)

    items: list[dict[str, str]] = []
    for tr in table.find_all("tr"):
        cells = tr.find_all("td", recursive=False)
        if not cells:
            continue

        if len(cells) >= 2:
            key = _tag_text(cells[0]).rstrip(":")
            value = _tag_text(cells[-1])
        else:
            key = _build_prompt_text(cells[0]).rstrip(":")
            value = _extract_answer_text(cells[0], [])

        if not key and not value:
            continue

        items.append({"key": key, "value": value})

    return {"recordType": record_type, "items": items}


def _parse_privaciu_interesu_html(html: str) -> dict[str, Any]:
    # 2024 layout: a leading key/value summary table (declaration date,
    # declarant, spouse), then repeated <h4 class="pid-table-title"> section
    # headings each followed by one record table per workplace/legal tie.
    soup = BeautifulSoup(html, "lxml")
    tabnav = soup.select_one("ul#tabnav")
    if tabnav is None:
        return {"sections": []}

    sections: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None

    for sibling in tabnav.next_siblings:
        if not isinstance(sibling, Tag):
            continue

        if sibling.name == "h4":
            current = {"title": _tag_text(sibling), "records": []}
            sections.append(current)
            continue

        if sibling.name == "table":
            if current is None:
                current = {"title": "", "records": []}
                sections.append(current)
            current["records"].append(_parse_privaciu_record_table(sibling))

    return {
        "sections": [section for section in sections if section["records"]],
    }


def _normalize_privaciu_interesu_data(payload: dict[str, Any]) -> dict[str, Any]:
    sections = payload.get("sections") if isinstance(payload.get("sections"), list) else []
    result: dict[str, Any] = {}

    for section in sections:
        if not isinstance(section, dict):
            continue

        section_title = str(section.get("title", "")).strip()
        records = section.get("records") if isinstance(section.get("records"), list) else []

        normalized_records: list[dict[str, Any]] = []
        for record in records:
            if not isinstance(record, dict):
                continue
            normalized_record: dict[str, Any] = {}
            for item in record.get("items", []):
                if not isinstance(item, dict):
                    continue
                item_key = _source_key(str(item.get("key", "")))
                if not item_key:
                    continue
                normalized_record[item_key] = _normalize_text_value(item.get("value"))
            if normalized_record:
                normalized_records.append(normalized_record)

        if not section_title:
            # The untitled leading table holds declaration-level key/values
            # (pateikimo-data, deklaruojantis-asmuo, sutuoktinis...).
            for record in normalized_records:
                result.update(record)
            continue

        section_key = _source_key(section_title)
        if not section_key:
            continue
        result[section_key] = normalized_records

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