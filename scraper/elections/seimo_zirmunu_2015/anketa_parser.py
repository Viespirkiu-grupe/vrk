from __future__ import annotations

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
from scraper.shared.files import write_candidate_record

DEFAULT_SAMPLES_ROOT = Path("samples/html/2015-kovo-1-seimo-zirmunai")
DEFAULT_OUTPUT_ROOT = Path("data/2015-kovo-1-seimo-zirmunai")

# Question numbers start a text node ("5. Gimimo data", "8.1 Ar turite" — the
# sub-question form carries no trailing dot). The bound keeps statute citations
# that begin a line in the municipal variant ("91 str. 1 d. ...") from reading
# as questions.
QUESTION_START_PATTERN = re.compile(r"^\s*(\d{1,2}(?:\.\d{1,2})*)\.?\s+")
MAX_QUESTION_NUMBER = 30

# The 2015 pages publish declared amounts in litas; the GPM308 row wording is
# also this era's own (the 2016 pages cite fields "…14, 20", these cite
# "…14, 22" plus the V13 field in the singular), so the aliases are restated.
TURTO_PAJAMU_KEY_ALIASES = {
    "i-privalomas-registruoti-turtas": "privalomas-registruoti-turtas",
    "ii-vertybiniai-popieriai-meno-kuriniai-juvelyriniai-dirbiniai": "vertybiniai-popieriai-meno-kuriniai-juvelyriniai-dirbiniai",
    "iii-pinigines-lesos": "pinigines-lesos",
    "iv-suteiktos-paskolos": "suteiktos-paskolos",
    "v-gautos-paskolos": "gautos-paskolos",
    "gautu-pajamu-suma-gpm308-formos-12-13-13a-14-22-laukeliu-ir-gpm308-formos-v-priedo-v13-laukelio-suma": "gautos-pajamos",
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
        return profile

    fields: list[dict[str, Any]] = []
    pending_label = ""

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


def parse_anketa_html(html: str) -> dict[str, Any]:
    soup = BeautifulSoup(html, "lxml")

    profile = _parse_profile_html(soup)

    content = _content_div(soup)
    anketa_cell = None
    if content is not None:
        anketa_table = content.find("table")
        if anketa_table is not None:
            anketa_cell = anketa_table.find("td")

    anketa = _parse_anketa_cell(anketa_cell)
    anketa["normalized"] = _normalize_anketa_rows(anketa["rows"])

    return {
        "profile": profile,
        "anketa": anketa,
        "diagnostics": {
            "profileCardFound": _profile_div(soup) is not None,
            "contentDivFound": content is not None,
            "anketaTableFound": anketa_cell is not None,
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


def _parse_lt_amount(value: Any) -> int | float | None:
    normalized_value = _normalize_text_value(value)
    if normalized_value is None:
        return None

    compact = normalized_value.replace(" ", " ")
    compact = re.sub(r"\blt\b\.?", "", compact, flags=re.IGNORECASE)
    compact = compact.replace(" ", "").replace(",", ".")

    if not compact or not re.fullmatch(r"-?\d+(?:\.\d+)?", compact):
        return None

    amount = float(compact)
    if amount.is_integer():
        return int(amount)
    return amount


def _normalize_turto_ir_pajamu_data(payload: dict[str, Any]) -> dict[str, Any]:
    sections = payload.get("sections") if isinstance(payload.get("sections"), list) else []
    normalized_fields: dict[str, Any] = {key: None for key in TURTO_PAJAMU_OUTPUT_ORDER}

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
            normalized_fields[target_key] = _parse_lt_amount(item.get("value"))

    # Unlike every later era the amounts are litas, and the page names the
    # declaration period in its closing note; both carried explicitly so a
    # cross-era consumer cannot silently read Lt as Eur.
    normalized_fields["valiuta"] = "Lt"
    normalized_fields["pastaba"] = _normalize_text_value(payload.get("note"))
    return normalized_fields


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


def _extract_interesu_section_id(title: str) -> str:
    match = re.search(r"\b(ID\d{3}[A-Z])\b", title)
    if match:
        return match.group(1).lower()
    return ""


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


def _parse_optional_subpages(
    candidate_dir: Path,
    candidate_id: str,
    candidate_source_url: str | None,
    anomalies: list[dict[str, Any]],
) -> dict[str, Any]:
    pages: dict[str, Any] = {}
    parser_map: dict[str, Any] = {
        "biografija": ("biografija.html", _parse_biografija_html),
        "turtoIrPajamuDeklaracijos": ("turto-ir-pajamu-deklaracijos.html", _parse_deklaracijos_html),
        # The 2015 tab is titled just "Interesų deklaracija"; the record keeps
        # the corpus-wide "privačių interesų" name because the content is the
        # same ID001x form.
        "privaciuInteresuDeklaracija": ("interesu-deklaracija.html", _parse_interesu_html),
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
    if not diagnostics.get("profileCardFound", False):
        anomalies.append(
            build_anomaly_event(
                event_type="ProfileCardMissing",
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
        if key == "kita" and isinstance(data, dict):
            normalized["kita"] = _normalize_kita_data(data)

    raw_data = _order_dict_keys(
        raw_data,
        [
            "profile",
            "anketa",
            "biografija",
            "turtoIrPajamuDeklaracijos",
            "privaciuInteresuDeklaracija",
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
