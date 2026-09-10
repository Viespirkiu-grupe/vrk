"""Candidate records of the 2004 presidential election.

There is no questionnaire in this tree — VRK asked the five candidates
for none. What one candidate is, and where each record section comes
from:

- the profile card on the shared listing (saved as ``anketa.html``):
  name, registration sentence with the linked VRK decision, the scanned
  statement (and Adamkus's health certificate) as GIF URLs, the campaign
  site. The card is found by the candidate's own ``<a name>`` anchor,
  through the sitemap module's card reader.
- ``nuotrauka.html`` — the full-portrait page; its image is the
  record's photo, the card's thumbnail the fallback.
- ``biografija.doc`` / ``programa.doc`` — Word 97 documents, read by
  ``scraper/shared/word_doc.py``. The corpus's only prose-recovered
  birth facts outside the 1990s archive come from the biography's
  opening sentence, under the same ``-saltinis`` markers that family
  established (all five biographies state the full date).
- ``turto-ir-pajamu-deklaracijos.html`` — the family's declaration
  extracts page, parsed by ``ep_2004``'s readers unchanged.
- ``kandidatavimas`` — the results join: ``isrinktas`` from the runoff
  verdict, and both rounds' national votes as ``turai`` (the corpus's
  only per-round presidential vote counts; later presidential trees
  publish them too but those modules join the verdict only).
"""
from __future__ import annotations

import errno
import json
from pathlib import Path
from typing import Any

from bs4 import BeautifulSoup

from scraper.elections.ep_2004.anketa_parser import (
    _normalize_deklaracijos_data,
    _parse_deklaracijos_html,
)
from scraper.elections.prezidento_2004.results import DEFAULT_RESULTS_PATH as _RESULTS_PATH, load_rounds
from scraper.elections.prezidento_2004.sitemap import (
    ELECTION_ID,
    extract_listing_entries,
    resolve_candidate_url,
)
from scraper.elections.seimo_zirmunu_2015.anketa_parser import _apply_results, load_results
from scraper.shared.anketa_tabs import (
    normalize_biografija_data,
    normalize_missing_values,
    normalize_profile_data,
    normalize_space,
    normalize_text_value,
    order_dict_keys,
)
from scraper.shared.anomalies import build_anomaly_event
from scraper.shared.files import load_candidate_index, write_candidate_record
from scraper.shared.seimo_archive_1990s import (
    extract_biography_birth_date,
    extract_biography_birth_place,
)
from scraper.shared.word_doc import extract_text

DEFAULT_SAMPLES_ROOT = Path(f"samples/html/{ELECTION_ID}")
DEFAULT_OUTPUT_ROOT = Path(f"data/{ELECTION_ID}")
# Elected status and both rounds' votes, joined in from VRK's results tree
# when the file exists.
DEFAULT_RESULTS_PATH = _RESULTS_PATH

__all__ = ["parse_anketa_sample", "parse_anketa_samples", "parse_listing_card"]


def parse_listing_card(listing_html: str, vrk_candidate_id: str) -> dict[str, Any] | None:
    """The candidate's card from the shared listing, as the profile."""
    card = None
    for entry in extract_listing_entries(listing_html):
        if entry["vrkCandidateId"] == vrk_candidate_id:
            card = entry
            break
    if card is None:
        return None
    fields: list[dict[str, Any]] = [
        {
            "key": "Registracija",
            "displayValue": card["registration"],
            "urls": [card["decisionUrl"]] if card["decisionUrl"] else [],
        },
        {"key": "Pareiškimas", "displayValue": "", "urls": [card["pareiskimasUrl"]] if card["pareiskimasUrl"] else []},
    ]
    if card["sveikatosPazymejimasUrl"]:
        fields.append({"key": "Sveikatos pažymėjimas", "displayValue": "", "urls": [card["sveikatosPazymejimasUrl"]]})
    if card["websiteUrl"]:
        fields.append({"key": "Interneto svetainė", "displayValue": card["websiteUrl"], "urls": [card["websiteUrl"]]})
    return {
        "candidateDisplayName": card["candidateName"],
        "electedNote": "",
        "photoSrc": card["photoUrl"] or "",
        "fields": fields,
    }


def _parse_nuotrauka_html(html: str) -> dict[str, Any]:
    soup = BeautifulSoup(html, "lxml")
    for image in soup.find_all("img", src=True):
        src = normalize_space(image["src"])
        if "/nuotraukos/" in src:
            return {"photoUrl": resolve_candidate_url(src)}
    return {"photoUrl": ""}


def _biography_anketa(text: str) -> dict[str, Any]:
    """Birth facts recovered from the biography prose, marked as such —
    the 1990s archive family's convention, same keys, same caveats."""
    anketa: dict[str, Any] = {}
    birth_date, birth_year = extract_biography_birth_date(text)
    if birth_date:
        anketa["gimimo-data"] = birth_date
        anketa["gimimo-data-saltinis"] = "biografijos-tekstas"
    if birth_year:
        anketa["gimimo-metai"] = birth_year
    birth_place = extract_biography_birth_place(text)
    if birth_place:
        anketa["gimimo-vieta"] = birth_place
        anketa["gimimo-vietos-saltinis"] = "biografijos-tekstas"
    return anketa


_load_candidate_meta = load_candidate_index


def parse_anketa_sample(
    candidate_id: str,
    samples_root: Path = DEFAULT_SAMPLES_ROOT,
    output_root: Path = DEFAULT_OUTPUT_ROOT,
    results_path: Path | None = DEFAULT_RESULTS_PATH,
    results_lookup: dict[str, dict[str, Any]] | None = None,
    rounds_lookup: dict[str, list[dict[str, Any]]] | None = None,
) -> tuple[Path, dict[str, Any]]:
    if results_lookup is None:
        results_lookup = load_results(results_path)
    if rounds_lookup is None:
        rounds_lookup = load_rounds(results_path)
    candidate_dir = samples_root / candidate_id
    anketa_path = candidate_dir / "anketa.html"
    if not anketa_path.exists():
        raise FileNotFoundError(errno.ENOENT, "Missing anketa sample", str(anketa_path))

    meta = _load_candidate_meta(candidate_dir)
    candidate_meta = meta.get("candidate", {}) if isinstance(meta.get("candidate"), dict) else {}
    source_url = candidate_meta.get("url")
    vrk_id = str(candidate_meta.get("vrkCandidateId", "") or "").strip()
    registration_id = str(candidate_meta.get("vrkRegistrationId", "") or "").strip()

    anomalies: list[dict[str, Any]] = []
    profile = parse_listing_card(anketa_path.read_text(encoding="utf-8"), vrk_id)
    if profile is None:
        anomalies.append(
            build_anomaly_event(
                event_type="ProfileCardMissing",
                severity="error",
                stage="parse",
                election_id=ELECTION_ID,
                candidate_id=candidate_id,
                source_url=source_url,
            )
        )
        profile = {"candidateDisplayName": "", "electedNote": "", "photoSrc": "", "fields": []}

    raw_data: dict[str, Any] = {"profile": profile}
    normalized: dict[str, Any] = {"profilis": normalize_profile_data(profile)}

    def _subpage_failed(key: str, path: Path, error: Exception) -> None:
        anomalies.append(
            build_anomaly_event(
                event_type="SubpageParseError",
                severity="error",
                stage="parse",
                election_id=ELECTION_ID,
                candidate_id=candidate_id,
                source_url=source_url,
                detail={"subpage": key, "sourcePath": str(path), "error": str(error)},
            )
        )

    nuotrauka_path = candidate_dir / "nuotrauka.html"
    if nuotrauka_path.exists():
        try:
            portrait = _parse_nuotrauka_html(nuotrauka_path.read_text(encoding="utf-8"))
        except Exception as exc:
            _subpage_failed("nuotrauka", nuotrauka_path, exc)
        else:
            raw_data["nuotrauka"] = {
                "pageUrl": candidate_meta.get("nuotraukaPageUrl"),
                "photoUrl": portrait["photoUrl"],
                "thumbnailUrl": candidate_meta.get("photoUrl"),
            }
            # The full portrait is the record's photo; the card's thumbnail
            # already sits in photoSrc as the fallback.
            if portrait["photoUrl"]:
                profile["photoSrc"] = portrait["photoUrl"]
                normalized["profilis"] = normalize_profile_data(profile)

    for key, normalized_key, url_key in (
        ("biografija", "biografija", "biografijaUrl"),
        ("programa", "programa", "programaUrl"),
    ):
        doc_path = candidate_dir / f"{key}.doc"
        if not doc_path.exists():
            continue
        try:
            text = extract_text(doc_path.read_bytes())
        except Exception as exc:
            _subpage_failed(key, doc_path, exc)
            continue
        raw_data[key] = {"text": text, "sourceUrl": candidate_meta.get(url_key)}
        normalized[normalized_key] = normalize_biografija_data({"text": text})
        if key == "biografija":
            anketa = _biography_anketa(text)
            if anketa:
                normalized["anketa"] = anketa

    deklaracija_path = candidate_dir / "turto-ir-pajamu-deklaracijos.html"
    if deklaracija_path.exists():
        try:
            data = _parse_deklaracijos_html(deklaracija_path.read_text(encoding="utf-8"))
        except Exception as exc:
            _subpage_failed("turtoIrPajamuDeklaracijos", deklaracija_path, exc)
        else:
            raw_data["turtoIrPajamuDeklaracijos"] = data
            normalized["turto-ir-pajamu-deklaracijos"] = _normalize_deklaracijos_data(data)

    candidate_name = str(candidate_meta.get("candidateName", "")).strip() or profile["candidateDisplayName"]
    output_payload: dict[str, Any] = {
        "electionId": ELECTION_ID,
        "candidateId": candidate_id,
        "candidateName": candidate_name,
        "kandidatavimas": {
            "vrkCandidateId": vrk_id or None,
            "vrkRegistrationId": registration_id or None,
            "isrinktas": None,
        },
    }
    if results_lookup is not None:
        _apply_results(output_payload, candidate_meta, source_url, results_lookup)
    if rounds_lookup is not None and registration_id in rounds_lookup:
        output_payload["kandidatavimas"]["turai"] = rounds_lookup[registration_id]
    output_payload |= {
        "source": {"candidateSourceUrl": source_url},
        "rawData": order_dict_keys(
            raw_data, ["profile", "nuotrauka", "biografija", "programa", "turtoIrPajamuDeklaracijos"]
        ),
        "normalized": normalize_missing_values(
            order_dict_keys(
                normalized,
                ["profilis", "anketa", "biografija", "programa", "turto-ir-pajamu-deklaracijos"],
            )
        ),
    }

    output_path = output_root / f"{candidate_id}-{ELECTION_ID}.json"
    write_candidate_record(output_path, output_payload, source_path=anketa_path)

    # No questionnaire exists in this tree, so "rows" are the record's
    # scalar sources — the card fields and the three sub-page texts — and
    # cli.py's row-count line still measures something real.
    scalar_values = [
        normalize_text_value(field.get("displayValue")) or (field.get("urls") or [None])[0]
        for field in profile["fields"]
    ] + [
        (raw_data.get(key) or {}).get("text")
        for key in ("biografija", "programa")
    ] + [raw_data.get("turtoIrPajamuDeklaracijos") and "deklaracijos"]
    stats = {
        "candidateId": candidate_id,
        "candidateName": candidate_name,
        "outputPath": str(output_path),
        "rowCount": len(scalar_values),
        "answeredRowCount": sum(1 for value in scalar_values if value),
        "anomalies": anomalies,
    }
    return output_path, stats


def parse_anketa_samples(
    candidate_ids: list[str] | None,
    samples_root: Path = DEFAULT_SAMPLES_ROOT,
    output_root: Path = DEFAULT_OUTPUT_ROOT,
    results_path: Path | None = DEFAULT_RESULTS_PATH,
) -> list[dict[str, Any]]:
    if candidate_ids:
        target_ids = list(candidate_ids)
    else:
        target_ids = [
            child.name
            for child in sorted(samples_root.iterdir())
            if child.is_dir() and (child / "anketa.html").exists()
        ]
    results_lookup = load_results(results_path)
    rounds_lookup = load_rounds(results_path)
    stats: list[dict[str, Any]] = []
    for candidate_id in target_ids:
        _, candidate_stats = parse_anketa_sample(
            candidate_id=candidate_id,
            samples_root=samples_root,
            output_root=output_root,
            results_path=results_path,
            results_lookup=results_lookup,
            rounds_lookup=rounds_lookup,
        )
        stats.append(candidate_stats)
    return stats
