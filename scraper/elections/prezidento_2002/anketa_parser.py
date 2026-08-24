"""Candidate records of the 2002 presidential election.

There is no questionnaire page in this tree — the questionnaire exists
only as a two-page scan of the paper form, alongside the scanned
statement, declaration and health certificate. The record's rule:
**text that survives as text is parsed; scans are archived and linked,
never OCR'd** — a guessed transcription of a 2002 form photograph would
be worse than none. What one candidate is:

- the profile card on the shared listing (saved as ``anketa.html``):
  name, VRK's candidate id, photo, the registration sentence with the
  linked VRK decision, the campaign site(s), and the scan links — the
  statement, the two questionnaire pages, the declaration (whose link
  label names the form: "Šeimos" or "Gyventojo turto pajamų
  deklaracija") and, on four cards, the health certificate. The scan
  URLs live in the profile's fields and in ``rawData.skenai``; the
  fetched JPGs sit beside the record in the sample set — except the
  health certificates, whose files are 404 on VRK's mirror (linked,
  never mirrored), so their URLs are the card's fact and nothing more.
- ``biografija.html`` — the era's one per-candidate text page: header
  headings, then the prose as sibling blocks. The birth facts are
  recovered from its opening sentence under the 1990s archive family's
  keys and caveats, exactly as ``prezidento_2004`` does from its Word
  biographies.
- ``programa.doc`` — Word 97, read by ``scraper/shared/word_doc.py``.
- ``kandidatavimas`` — the results join: ``isrinktas`` from the final
  protocol's verdict, and both rounds' national votes as ``turai``.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from bs4 import BeautifulSoup, NavigableString

from scraper.elections.prezidento_2002.results import DEFAULT_RESULTS_PATH as _RESULTS_PATH
from scraper.elections.prezidento_2002.sitemap import ELECTION_ID, extract_listing_entries
from scraper.elections.prezidento_2004.results import load_rounds
from scraper.elections.seimo_2016.anketa_parser import (
    _normalize_biografija_data,
    _normalize_missing_values,
    _normalize_profile_data,
    _normalize_text_value,
    _order_dict_keys,
    normalize_space,
)
from scraper.elections.seimo_zirmunu_2015.anketa_parser import _apply_results, load_results
from scraper.shared.anomalies import build_anomaly_event
from scraper.shared.files import write_candidate_record
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

__all__ = ["parse_anketa_sample", "parse_anketa_samples", "parse_biografija_html", "parse_listing_card"]


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
        {"key": "Duomenų anketa", "displayValue": "", "urls": list(card["anketosSkenaiUrls"])},
        {
            "key": card["deklaracijaLabel"] or "Deklaracija",
            "displayValue": "",
            "urls": [card["deklaracijaUrl"]] if card["deklaracijaUrl"] else [],
        },
    ]
    if card["sveikatosSkenaiUrls"]:
        fields.append({"key": "Sveikatos pažyma", "displayValue": "", "urls": list(card["sveikatosSkenaiUrls"])})
    if card["websiteUrls"]:
        fields.append(
            {"key": "Tinklalapis", "displayValue": card["websiteUrls"][0], "urls": list(card["websiteUrls"])}
        )
    return {
        "candidateDisplayName": card["candidateName"],
        "electedNote": "",
        "photoSrc": card["photoUrl"] or "",
        "fields": fields,
    }


def parse_biografija_html(html: str) -> dict[str, Any]:
    """The prose after the header headings, one line per block.

    The header is the page title plus two ``<h1>`` ("KANDIDATAS Į
    RESPUBLIKOS PREZIDENTUS", the name); everything after the last
    heading is the biography, printed as sibling text blocks separated
    by spacer divs.
    """
    soup = BeautifulSoup(html, "lxml")
    for tag in soup.find_all(["script", "style"]):
        tag.decompose()
    headings = soup.find_all("h1")
    if not headings:
        return {"text": "", "headingName": ""}
    lines: list[str] = []
    for node in headings[-1].next_elements:
        # next_elements starts inside the heading; its own text is the
        # name, not the first line of the prose.
        if isinstance(node, NavigableString) and headings[-1] not in node.parents:
            text = normalize_space(str(node))
            if text:
                lines.append(text)
    return {
        "text": "\n".join(lines),
        "headingName": normalize_space(headings[-1].get_text(" ", strip=True)),
    }


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


def _load_candidate_meta(candidate_dir: Path) -> dict[str, Any]:
    index_path = candidate_dir / "index.json"
    if not index_path.exists():
        return {}
    try:
        payload = json.loads(index_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


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
        raise FileNotFoundError(f"Missing anketa sample: {anketa_path}")

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

    raw_data: dict[str, Any] = {
        "profile": profile,
        # The scan inventory in one machine-readable block: what VRK
        # published only as photographs, archived in the sample set and
        # linked here — never OCR'd into data.
        "skenai": {
            "pareiskimas": candidate_meta.get("pareiskimasUrl"),
            "duomenu-anketa": list(candidate_meta.get("anketosSkenaiUrls") or []),
            "deklaracija": {
                "url": candidate_meta.get("deklaracijaUrl"),
                "forma": candidate_meta.get("deklaracijaLabel"),
            },
            "sveikatos-pazyma": list(candidate_meta.get("sveikatosSkenaiUrls") or []),
        },
    }
    normalized: dict[str, Any] = {"profilis": _normalize_profile_data(profile)}

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

    biografija_path = candidate_dir / "biografija.html"
    if biografija_path.exists():
        try:
            biografija = parse_biografija_html(biografija_path.read_text(encoding="utf-8"))
        except Exception as exc:
            _subpage_failed("biografija", biografija_path, exc)
        else:
            raw_data["biografija"] = {
                "text": biografija["text"],
                "headingName": biografija["headingName"],
                "sourceUrl": candidate_meta.get("biografijaUrl"),
            }
            normalized["biografija"] = _normalize_biografija_data(biografija)
            anketa = _biography_anketa(biografija["text"])
            if anketa:
                normalized["anketa"] = anketa

    programa_path = candidate_dir / "programa.doc"
    if programa_path.exists():
        try:
            text = extract_text(programa_path.read_bytes())
        except Exception as exc:
            _subpage_failed("programa", programa_path, exc)
        else:
            raw_data["programa"] = {"text": text, "sourceUrl": candidate_meta.get("programaUrl")}
            normalized["programa"] = _normalize_biografija_data({"text": text})

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
        "rawData": _order_dict_keys(raw_data, ["profile", "skenai", "biografija", "programa"]),
        "normalized": _normalize_missing_values(
            _order_dict_keys(normalized, ["profilis", "anketa", "biografija", "programa"])
        ),
    }

    output_path = output_root / f"{candidate_id}-{ELECTION_ID}.json"
    write_candidate_record(output_path, output_payload)

    # No questionnaire text exists in this tree, so "rows" are the record's
    # scalar sources — the card fields and the two parsed texts — and
    # cli.py's row-count line still measures something real.
    scalar_values = [
        _normalize_text_value(field.get("displayValue")) or (field.get("urls") or [None])[0]
        for field in profile["fields"]
    ] + [
        (raw_data.get(key) or {}).get("text")
        for key in ("biografija", "programa")
    ]
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
