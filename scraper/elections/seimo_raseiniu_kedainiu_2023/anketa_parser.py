from __future__ import annotations

import errno
from pathlib import Path
from typing import Any

from bs4 import BeautifulSoup

from scraper.elections.seimo_raseiniu_kedainiu_2023.sitemap import ELECTION_ID
from scraper.elections.ep_2019.anketa_parser import (
    _parse_profile_table,
    _select_profile_table,
)
from scraper.elections.ep_2024.anketa_parser import (
    _find_photo_src,
    _normalize_privaciu_interesu_data,
    _normalize_turto_ir_pajamu_data,
    _parse_biografija_html,
    _parse_kita_html,
    _parse_privaciu_interesu_html,
    _parse_turto_ir_pajamu_html,
    _records_for_question,
)
# Tab bodies follow the tab navigation as siblings (the 2024 layout), so the
# 2024 EP page parsers apply, but the biography questionnaire is numbered as on
# the 2023 mayoral pages (nationality is Q2), so that module's normalization is
# reused verbatim.
from scraper.elections.kupiskio_mero_2023.anketa_parser import _normalize_biografija_data
from scraper.elections.seimo_2016.anketa_parser import (
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
    _parse_nested_campaign_samples,
    _parse_politines_kampanijos_html,
    _parse_tabnav,
    _row_answer_text,
)
from scraper.shared.anomalies import build_anomaly_event
from scraper.shared.conviction_details import conviction_entries, conviction_records
from scraper.shared.files import write_candidate_record, write_json

DEFAULT_SAMPLES_ROOT = Path("samples/html/2023-rugsejo-3-seimo-raseiniai-kedainiai")
DEFAULT_OUTPUT_ROOT = Path("data/2023-rugsejo-3-seimo-raseiniai-kedainiai")


# ---------------------------------------------------------------------------
# Anketa
# ---------------------------------------------------------------------------


def _normalize_anketa_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    def _answer(question_number: str) -> str | None:
        return _normalize_text_value(
            _row_answer_text(_find_row_by_question_number(rows, question_number))
        )

    return {
        "adresas": _answer("6"),
        "einamos-pareigos": _answer("7"),
        # Q8 asks for a single membership ("Narystė politinėje partijoje,
        # politiniame komitete, asociacijose") and is answered inline rather
        # than with the membership table the 2024 elections use, so the text is
        # kept alongside the record list the shared shape expects.
        "narystes-politinese-organizacijose": {
            "tekstas": _answer("8"),
            "irasai": _normalize_table_records(_records_for_question(rows, "8")),
        },
        "pareiskimai": {
            # Q9-Q14 follow Rinkimų kodekso 76 str. and share their keys with
            # the 2024 modules. Q15-Q16 are the Seimo eligibility questions and
            # repeat the presidential wording, so those keys are shared too.
            "ar-kitos-valstybes-institucijos-narys": _answer("9"),
            "ar-eina-nesuderinamas-pareigas": _answer("10"),
            "ar-bendradarbiavote-su-ssrs-tarnybomis": _answer("11"),
            "ar-nebaigta-teismo-paskirta-bausme": _answer("12"),
            "ar-buvote-pripazintas-kaltu": _answer("13"),
            "ar-veika-dekriminalizuota": _answer("13.5"),
            "ar-buvote-pripazintas-kaltu-uzsienyje": _answer("13.6"),
            "ar-buvote-pripazintas-kaltu-del-politinio-persekiojimo": _answer("13.7"),
            "ar-neteko-mandato-uz-pazeidimus": _answer("14"),
            "ar-esate-ar-buvote-kitos-valstybes-pilietis": _answer("15"),
            "ar-susijes-priesaika-uzsienio-valstybei": _answer("16"),
        },
        # 13.1-13.4 appear only when Q13 is answered "Taip".
        "teistumo-detales": {
            # One entry per conviction; empty list when Q13 has no block. The
            # always-null 13.4 free-text aprasas (the table carries the data)
            # is retired with the old null-field skeleton.
            "irasai": conviction_entries(
                _answer("13.1"),
                _answer("13.2"),
                _answer("13.3"),
                conviction_records(rows, "13.4"),
            ),
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
