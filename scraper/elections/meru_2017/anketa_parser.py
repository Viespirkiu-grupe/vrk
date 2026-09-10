from __future__ import annotations

import errno
from pathlib import Path
from typing import Any

from bs4 import BeautifulSoup

from scraper.elections.meru_2017.sitemap import ELECTION_ID
# These pages predate the 2024 layout: the anketa is split across sibling
# tables, standalone record tables sit between them, sub-questions are numbered
# without a trailing dot ("8.2 Ar nesate ..."), photos are base64 data URIs and
# the private-interest declaration uses the ID001x section blocks. That is the
# 2019 EP shape, so its profile and anketa parsers apply here.
from scraper.elections.ep_2019.anketa_parser import (
    parse_office_heading,
    _parse_anketa_content,
    _parse_privaciu_interesu_html,
    _parse_profile_table,
    _select_profile_table,
)
from scraper.shared.anketa_tabs import (
    find_main_content_after_tabnav,
    find_row_by_prompt_prefix,
    find_row_by_question_number,
    load_candidate_meta,
    normalize_biografija_data,
    normalize_campaigns,
    normalize_kita_data,
    normalize_missing_values,
    normalize_privaciu_interesu_data,
    normalize_profile_data,
    normalize_table_records,
    normalize_text_value,
    order_dict_keys,
    parse_biografija_html,
    parse_eur_amount,
    parse_kita_html,
    parse_nested_campaign_samples,
    parse_politines_kampanijos_html,
    parse_tabnav,
    parse_turto_ir_pajamu_html,
    question_record_rows,
    row_answer_text,
    split_list_value,
)
from scraper.shared.anomalies import build_anomaly_event
from scraper.shared.election_results import candidacy_from_elected_note
from scraper.shared.deklaracijos import normalize_declaration
from scraper.shared.files import write_candidate_record, write_json

DEFAULT_SAMPLES_ROOT = Path("samples/html/2017-balandzio-23-meru")
DEFAULT_OUTPUT_ROOT = Path("data/2017-balandzio-23-meru")

# The declaration rows, and the four things a section heading says about an
# extract — its scope, its year, its form and its figures — are one shared
# reading for every era; see scraper/shared/deklaracijos.py.


# Q9 quotes the statute it refers to in a row of its own, and the answer is
# rendered on that continuation row rather than on the question row.
Q9_CONTINUATION_PREFIX = "36 str."


# ---------------------------------------------------------------------------
# Anketa
# ---------------------------------------------------------------------------


def _q9_answer(rows: list[dict[str, Any]]) -> str | None:
    row = find_row_by_question_number(rows, "9")
    answer = normalize_text_value(row_answer_text(row))
    if answer is not None:
        return answer

    continuation = find_row_by_prompt_prefix(rows, Q9_CONTINUATION_PREFIX)
    return normalize_text_value(row_answer_text(continuation))


def _normalize_anketa_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    def _answer(question_number: str) -> str | None:
        return normalize_text_value(
            row_answer_text(find_row_by_question_number(rows, question_number))
        )

    def _prompt_answer(prefix: str) -> str | None:
        return normalize_text_value(row_answer_text(find_row_by_prompt_prefix(rows, prefix)))


    return {
        "gimimo-data": _answer("5"),
        "adresas": _answer("6"),
        "pareiskimai": {
            # Q8.x are the savivaldybių tarybų rinkimų įstatymo 36 str. 11 d.
            # declarations; there is no 8.1 on these pages. Keys follow the
            # other modules where the question matches.
            "ar-atliekate-karo-tarnyba": _answer("8.2"),
            "ar-eina-nesuderinamas-pareigas": _answer("8.3"),
            "ar-kitos-valstybes-institucijos-narys": _answer("8.4"),
            "ar-turite-kitos-valstybes-pilietybe": _answer("8.5"),
            # Q9 asks whether the candidate has anything to declare under the
            # conviction paragraph (36 str. 12 d.), so it fills the same slot as
            # the explicit conviction question of the later elections.
            "ar-buvote-pripazintas-kaltu": _q9_answer(rows),
        },
        "gimimo-vieta": _answer("10"),
        "tautybe": _answer("11"),
        "issilavinimas": {
            "aprasas": _answer("12"),
            "irasai": normalize_table_records(question_record_rows(rows, "12")),
        },
        "pedagoginis-vardas": _prompt_answer("jei turite, nurodykite pedagogin"),
        "uzsienio-kalbos": split_list_value(row_answer_text(find_row_by_question_number(rows, "13"))),
        "politine-organizacija": _answer("14"),
        "anksciau-isrinktas": {
            "aprasas": _answer("15"),
            "irasai": normalize_table_records(question_record_rows(rows, "15")),
        },
        "pagrindine-darboviete": _answer("16"),
        "visuomenine-veikla": _answer("17"),
        "pomegiai": _answer("18"),
        "seimine-padetis": _answer("19"),
        "sutuoktinio-vardas-pavarde": _prompt_answer("vyro arba žmonos vardas"),
        "vaiku-vardai-pavardes": _answer("20"),
        # Q21 is written with the number in brackets at the end of the prompt,
        # so it is matched on its text instead.
        "kita-apie-save": _prompt_answer("be jau išvardintų atsakymų"),
    }


def parse_anketa_html(html: str) -> dict[str, Any]:
    soup = BeautifulSoup(html, "lxml")

    tabnav = soup.select_one("ul#tabnav")
    profile_table = _select_profile_table(soup, tabnav)
    content = find_main_content_after_tabnav(soup)

    profile = _parse_profile_table(profile_table)
    profile["officeHeading"] = parse_office_heading(soup)
    tabs = parse_tabnav(tabnav)
    anketa = _parse_anketa_content(content)
    anketa["normalized"] = _normalize_anketa_rows(anketa["rows"])

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
# Turto ir pajamų deklaracijos
# ---------------------------------------------------------------------------


def _normalize_turto_ir_pajamu_data(payload: dict[str, Any]) -> dict[str, Any]:
    return normalize_declaration(payload, parse_eur_amount)


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
        "biografija": ("biografija.html", parse_biografija_html),
        "privaciuInteresuDeklaracija": ("privaciu-interesu-deklaracijos.html", _parse_privaciu_interesu_html),
        "turtoIrPajamuDeklaracijos": ("turto-ir-pajamu-deklaracijos.html", parse_turto_ir_pajamu_html),
        "kita": ("kita.html", parse_kita_html),
        "politinesKampanijosDalyvioDuomenys": (
            "politines-kampanijos-dalyvio-duomenys.html",
            parse_politines_kampanijos_html,
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
    meta = load_candidate_meta(candidate_dir)
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
        nested_campaigns = parse_nested_campaign_samples(
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
        "profilis": normalize_profile_data(parsed["profile"]),
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
            normalized["biografija"] = normalize_biografija_data(data)
        if key == "privaciuInteresuDeklaracija" and isinstance(data, dict):
            normalized["privaciu-interesu-deklaracija"] = normalize_privaciu_interesu_data(data)
        if key == "turtoIrPajamuDeklaracijos" and isinstance(data, dict):
            normalized["turto-ir-pajamu-deklaracijos"] = _normalize_turto_ir_pajamu_data(data)
        if key == "kita" and isinstance(data, dict):
            normalized["kita"] = normalize_kita_data(data)

    if nested_campaigns:
        campaign_key = "politinesKampanijosDalyvioDuomenys"
        section_description = ""
        if isinstance(root_campaign_data, dict):
            section_description = str(root_campaign_data.get("sectionDescription", ""))

        raw_data[campaign_key] = {
            "sectionDescription": section_description,
            "campaigns": nested_campaigns,
        }
        normalized["politines-kampanijos-dalyvio-duomenys"] = normalize_campaigns(raw_data[campaign_key])
    elif isinstance(root_campaign_data, dict):
        campaign_key = "politinesKampanijosDalyvioDuomenys"
        raw_data[campaign_key] = root_campaign_data

    raw_data = order_dict_keys(
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
    normalized = order_dict_keys(
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
        "normalized": normalize_missing_values(normalized),
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
