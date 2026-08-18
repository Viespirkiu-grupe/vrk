from __future__ import annotations

from pathlib import Path
import re
from typing import Any

from bs4 import BeautifulSoup, Tag

from scraper.elections.ep_2024.sitemap import ELECTION_ID
from scraper.elections.ep_2019.anketa_parser import (
    _parse_profile_table,
    _select_profile_table,
)
from scraper.elections.seimo_2016.anketa_parser import (
    _build_prompt_text,
    _extract_answer_text,
    _extract_links,
    _find_row_by_question_number,
    _load_candidate_meta,
    _normalize_campaigns,
    _normalize_kita_data,
    _normalize_missing_values,
    _normalize_profile_data,
    _normalize_table_records,
    _normalize_text_value,
    _order_dict_keys,
    _parse_anketa_table,
    _parse_eur_amount,
    _parse_nested_campaign_samples,
    _parse_nested_table,
    _parse_politines_kampanijos_html,
    _parse_tabnav,
    _row_answer_text,
    _source_key,
    _tag_text,
    normalize_space,
    parse_question_number,
)
from scraper.shared.anomalies import build_anomaly_event
from scraper.shared.files import write_json

DEFAULT_SAMPLES_ROOT = Path("samples/html/2024-ep")
DEFAULT_OUTPUT_ROOT = Path("data/2024-ep")

# The 2024 pages carry the same asset labels as 2019 ("I. Privalomas
# registruoti turtas" ...) and the same two GPM311 income summary labels,
# so the alias table matches the 2019 EP module.
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

PHOTO_SRC_PATTERN = re.compile(r"kandImg", flags=re.IGNORECASE)


# ---------------------------------------------------------------------------
# Anketa
# ---------------------------------------------------------------------------


def _find_photo_src(soup: BeautifulSoup) -> str:
    # In 2024 the photo sits in the page-level layout table next to the
    # profile table, so it is not captured by the profile-table parser.
    img = soup.find("img", src=PHOTO_SRC_PATTERN)
    if img is None:
        return ""
    return normalize_space(img.get("src", ""))


def _record_groups_for_question(rows: list[dict[str, Any]], question_number: str) -> list[list[Any]]:
    # Standalone record tables (e.g. Q8 party memberships) are rendered in
    # their own <tr> right after the question row, so each table lands in a
    # separate parsed row without a question number. Collect every
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


def _structure_dash_fields(values: list[Any]) -> dict[str, Any]:
    # Detail tables such as the Q13.4 conviction block render one
    # "Label – value" line per field; fold them into a single record.
    record: dict[str, Any] = {}
    for value in values:
        if not isinstance(value, str):
            continue
        text = normalize_space(value)
        if not text:
            continue
        label, _, field_value = text.partition("–")
        key = _source_key(label)
        if not key:
            continue
        record[key] = _normalize_text_value(field_value)
    return record


def _conviction_records(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for group in _record_groups_for_question(rows, "13.4"):
        if all(isinstance(value, str) for value in group):
            record = _structure_dash_fields(group)
            if record:
                records.append(record)
            continue
        for normalized in _normalize_table_records(group):
            if isinstance(normalized, dict):
                records.append(normalized)
    return records


def _normalize_anketa_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    def _answer(question_number: str) -> str | None:
        return _normalize_text_value(
            _row_answer_text(_find_row_by_question_number(rows, question_number))
        )

    return {
        "adresas": _answer("6"),
        "einamos-pareigos": _answer("7"),
        "narystes-politinese-organizacijose": {
            "irasai": _normalize_table_records(_records_for_question(rows, "8")),
        },
        "pareiskimai": {
            "ar-kitos-valstybes-institucijos-narys": _answer("9"),
            "ar-eina-nesuderinamas-pareigas": _answer("10"),
            "ar-bendradarbiavote-su-ssrs-tarnybomis": _answer("11"),
            "ar-nebaigta-teismo-paskirta-bausme": _answer("12"),
            "ar-buvote-pripazintas-kaltu": _answer("13"),
            "ar-veika-dekriminalizuota": _answer("13.5"),
            "ar-buvote-pripazintas-kaltu-uzsienyje": _answer("13.6"),
            "ar-buvote-pripazintas-kaltu-del-politinio-persekiojimo": _answer("13.7"),
            "ar-neteko-mandato-uz-pazeidimus": _answer("14"),
            "ar-kitos-es-valstybes-pilietis": _answer("15"),
            "ar-rinkimu-teise-apribota-kitoje-es-valstybeje": _answer("16"),
        },
        # 13.1-13.4 appear only when Q13 is answered "Taip".
        "teistumo-detales": {
            "nuosprendzio-data": _answer("13.1"),
            "nuosprendzio-valstybe": _answer("13.2"),
            "nuosprendzio-institucija": _answer("13.3"),
            "nusikalstamos-veikos": {
                "aprasas": _answer("13.4"),
                "irasai": _conviction_records(rows),
            },
        },
        # 14.1 appears only when Q14 is answered "Taip".
        "mandato-netekimo-detales": _answer("14.1"),
    }


def parse_anketa_html(html: str) -> dict[str, Any]:
    soup = BeautifulSoup(html, "lxml")

    tabnav = soup.select_one("ul#tabnav")
    profile_table = _select_profile_table(soup, tabnav)
    anketa_table = tabnav.find_next("table") if tabnav is not None else None

    profile = _parse_profile_table(profile_table)
    if not profile.get("photoSrc"):
        profile["photoSrc"] = _find_photo_src(soup)
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


# ---------------------------------------------------------------------------
# Biografija (structured questionnaire, unlike the 2019 free-text bio)
# ---------------------------------------------------------------------------


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


def _split_birth_value(value: str | None) -> tuple[str | None, str | None]:
    normalized = _normalize_text_value(value)
    if not normalized:
        return None, None

    parts = [part.strip() for part in normalized.split(",", 1)]
    if len(parts) == 2:
        return _normalize_text_value(parts[0]), _normalize_text_value(parts[1])

    return normalized, None


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


# ---------------------------------------------------------------------------
# Turto ir pajamų deklaracijos (asset/income)
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# Privačių interesų deklaracijos (private interests)
# ---------------------------------------------------------------------------


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
            if th is not None and key and not value:
                # A one-cell row in a header-bearing table is a data row of a
                # single-column table ("Kiti duomenys ar aplinkybės" free
                # text), not a label. Keep it unlabelled so the normalizer
                # can collect it under "tekstas" instead of the whole
                # sentence becoming a key.
                key, value = "", _tag_text(cells[0])

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
            # A declaration section can be free text rather than key/value
            # pairs — "Kiti duomenys" is filled in as a sentence with no label.
            # Those rows reach here with an empty key; dropping them for want
            # of a key silently loses the whole declared text.
            free_text: list[str] = []
            for item in record.get("items", []):
                if not isinstance(item, dict):
                    continue
                item_value = _normalize_text_value(item.get("value"))
                item_key = _source_key(str(item.get("key", "")))
                if not item_key:
                    if item_value:
                        free_text.append(str(item_value))
                    continue
                normalized_record[item_key] = item_value
            if free_text:
                joined = " ".join(free_text)
                existing = normalized_record.get("tekstas")
                # A labelled field can itself slugify to "tekstas". Appending
                # rather than deferring keeps both, instead of re-introducing
                # the silent loss this branch exists to fix.
                normalized_record["tekstas"] = (
                    f"{existing} {joined}".strip() if isinstance(existing, str) and existing else joined
                )
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


# ---------------------------------------------------------------------------
# Kita
# ---------------------------------------------------------------------------


def _parse_kita_html(html: str) -> dict[str, Any]:
    soup = BeautifulSoup(html, "lxml")
    tabnav = soup.select_one("ul#tabnav")

    texts: list[str] = []
    links: list[str] = []
    if tabnav is not None:
        for sibling in tabnav.next_siblings:
            if isinstance(sibling, Tag):
                for text in sibling.stripped_strings:
                    normalized = normalize_space(text)
                    if normalized:
                        texts.append(normalized)
                links.extend(_extract_links(sibling))
            else:
                normalized = normalize_space(str(sibling))
                if normalized:
                    texts.append(normalized)

    return {
        "texts": texts,
        "links": links,
    }


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
