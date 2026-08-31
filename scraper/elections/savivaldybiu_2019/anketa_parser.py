from __future__ import annotations

import errno
from pathlib import Path
from typing import Any

from scraper.elections.savivaldybiu_2019.sitemap import ELECTION_ID
# The candidate pages are the same vintage as the April 2017 mayoral election —
# same savivaldybių tarybų rinkimų įstatymas question set (Q5–Q21 with the
# biography questions inside the anketa), the same dotless sub-question
# numbering, base64 photos, GPM308 income labels and ID001x private-interest
# sections — so the parsing rules are reused rather than restated here.
from scraper.elections.meru_2017.anketa_parser import (
    _parse_optional_subpages,
    parse_anketa_html as _parse_anketa_html_2017,
)
from scraper.elections.ep_2019.anketa_parser import _normalize_privaciu_interesu_data
from scraper.elections.seimo_2016.anketa_parser import (
    _find_row_by_question_number,
    _load_candidate_meta,
    _normalize_biografija_data,
    _normalize_campaigns,
    _normalize_kita_data,
    _normalize_missing_values,
    _normalize_profile_data,
    _normalize_text_value,
    _order_dict_keys,
    _parse_eur_amount,
    _parse_nested_campaign_samples,
    _row_answer_text,
)
from scraper.shared.anomalies import build_anomaly_event
from scraper.shared.conviction_details import conviction_field_keys, conviction_records
from scraper.shared.deklaracijos import normalize_declaration
from scraper.shared.files import write_candidate_record, write_json

DEFAULT_SAMPLES_ROOT = Path(f"samples/html/{ELECTION_ID}")
DEFAULT_OUTPUT_ROOT = Path(f"data/{ELECTION_ID}")

# The declaration rows, and the four things a section heading says about an
# extract — its scope, its year, its form and its figures — are one shared
# reading for every era; see scraper/shared/deklaracijos.py.

# The 2019 pages ask for the conviction details under Q9.1, as the 2021 mayoral
# ones do: same statute, same question, one table row per conviction.
CONVICTION_QUESTION = "9.1"


def parse_anketa_html(html: str) -> dict[str, Any]:
    """The 2017 anketa parse plus the questions 2019 asks and 2017 did not.

    The April 2017 pages number their declarations 8.2–8.5 with no 8.1, carry
    no 9.2–9.4 at all, and write Q21 with its number in brackets at the end so
    the 2017 module matches that question on its prompt text. 2019 asks four
    more declarations and numbers Q21 at the front, so inheriting the 2017
    mapping unchanged drops all five answers into rawData and never normalizes
    them — losing conviction-related declarations, and free text, for the whole
    election. Keys match the 2021 mayoral module, which asks the same
    questions under the same statute.
    """
    parsed = _parse_anketa_html_2017(html)

    anketa = parsed.get("anketa")
    if not isinstance(anketa, dict):
        return parsed
    rows = anketa.get("rows") or []
    normalized = anketa.get("normalized")
    if not isinstance(normalized, dict):
        return parsed

    def _answer(question_number: str) -> Any:
        return _normalize_text_value(
            _row_answer_text(_find_row_by_question_number(rows, question_number))
        )

    pareiskimai = normalized.get("pareiskimai")
    if isinstance(pareiskimai, dict):
        normalized["pareiskimai"] = {
            "ar-nebaigta-teismo-paskirta-bausme": _answer("8.1"),
            **pareiskimai,
            "ar-veika-dekriminalizuota": _answer("9.2"),
            "ar-buvote-pripazintas-kaltu-uzsienyje": _answer("9.3"),
            "ar-buvote-pripazintas-kaltu-del-politinio-persekiojimo": _answer("9.4"),
        }

    # Q9.1 is a record table listing each conviction — date, country, court
    # and offence — present only when Q9 is answered "Taip". The shared parse
    # captures it as a records row; fold it into the meru_2021 shape.
    normalized["teistumo-detales"] = {
        "irasai": conviction_records(
            rows, CONVICTION_QUESTION, conviction_field_keys(CONVICTION_QUESTION)
        ),
    }

    # Q21 is "21. Be jau išvardintų atsakymų, ką dar norėtumėte parašyti apie
    # save?". 2017 renders the number at the end of the prompt, so that module
    # matches on the text; here the prompt starts with "21. " and the prefix
    # match never fires, discarding whatever the candidate wrote.
    normalized["kita-apie-save"] = _answer("21")
    return parsed


def _normalize_turto_ir_pajamu_data(payload: dict[str, Any]) -> dict[str, Any]:
    return normalize_declaration(payload, _parse_eur_amount)


def _build_candidacy(candidate_meta: dict[str, Any]) -> dict[str, Any]:
    """The listing-only context for one candidate.

    Which municipality a candidate stood in, on whose list, at which position
    and whether they won is published on the listing pages and nowhere on the
    candidate page, so it is carried in from the sitemap. `roles` is the pair
    this election shape needs: 379 people ran for both a council seat and the
    mayoralty in 2019.
    """
    roles = candidate_meta.get("roles")
    council = candidate_meta.get("councilCandidacy")
    mayoral = candidate_meta.get("mayoralCandidacy")

    candidacy: dict[str, Any] = {
        "vrkCandidateId": str(candidate_meta.get("vrkCandidateId", "")).strip() or None,
        "savivaldybe": candidate_meta.get("municipality") or None,
        "roles": list(roles) if isinstance(roles, list) else [],
        "tarybosNarys": council if isinstance(council, dict) else None,
        "meras": mayoral if isinstance(mayoral, dict) else None,
    }
    candidacy["isrinktas"] = bool(
        (isinstance(council, dict) and council.get("elected"))
        or (isinstance(mayoral, dict) and mayoral.get("elected"))
    )
    return candidacy


def parse_anketa_sample(
    candidate_id: str,
    samples_root: Path = DEFAULT_SAMPLES_ROOT,
    output_root: Path = DEFAULT_OUTPUT_ROOT,
) -> tuple[Path, dict[str, Any]]:
    candidate_dir = samples_root / candidate_id
    anketa_path = candidate_dir / "anketa.html"
    if not anketa_path.exists():
        raise FileNotFoundError(errno.ENOENT, "Missing anketa sample", str(anketa_path))

    parsed = parse_anketa_html(anketa_path.read_text(encoding="utf-8"))
    meta = _load_candidate_meta(candidate_dir)
    candidate_meta = meta.get("candidate", {}) if isinstance(meta, dict) else {}
    candidate_source_url = candidate_meta.get("url") if isinstance(candidate_meta, dict) else None

    anomalies: list[dict[str, Any]] = []
    diagnostics = parsed.get("diagnostics", {})
    for flag, event_type, severity in (
        ("tabnavFound", "TabnavSelectorNotFound", "critical"),
        ("profileTableFound", "ProfileTableMissing", "error"),
        ("anketaTableFound", "AnketaTableNotFound", "critical"),
    ):
        if not diagnostics.get(flag, False):
            anomalies.append(
                build_anomaly_event(
                    event_type=event_type,
                    severity=severity,
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
    candidate_note = ""
    if isinstance(candidate_meta, dict):
        candidate_name = str(candidate_meta.get("candidateName", "")).strip()
        candidate_note = str(candidate_meta.get("candidateNote", "")).strip()
    if not candidate_name:
        candidate_name = parsed["profile"].get("candidateDisplayName", "")

    raw_data: dict[str, Any] = {
        "profile": parsed["profile"],
        "anketa": {"rows": parsed["anketa"]["rows"]},
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

    campaign_key = "politinesKampanijosDalyvioDuomenys"
    if nested_campaigns:
        section_description = ""
        if isinstance(root_campaign_data, dict):
            section_description = str(root_campaign_data.get("sectionDescription", ""))
        raw_data[campaign_key] = {
            "sectionDescription": section_description,
            "campaigns": nested_campaigns,
        }
        normalized["politines-kampanijos-dalyvio-duomenys"] = _normalize_campaigns(
            raw_data[campaign_key]
        )
    elif isinstance(root_campaign_data, dict):
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
        "candidateNote": candidate_note or None,
        "kandidatavimas": _build_candidacy(
            candidate_meta if isinstance(candidate_meta, dict) else {}
        ),
        "source": {"candidateSourceUrl": candidate_source_url},
        "rawData": raw_data,
        "normalized": _normalize_missing_values(normalized),
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
