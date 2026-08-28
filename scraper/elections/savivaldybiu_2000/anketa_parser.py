"""Candidate pages of the 2000-03-19 municipal council general election.

``kandvl.htm-<ID>.htm`` is the document the October 2000 Seimas election
publishes seven months later (``scraper/elections/seimo_2000/anketa_parser.py``
reads that one), for the municipal form:

- The card: the name as ``<font size="5">``, "Apygarda: <b>Vilniaus
  miesto</b> (Nr. 57)" linking the municipality page, "Sąrašas:
  <b>Krikščionių demokratų sąjungos</b>, priešrinkiminis numeris sąraše:
  <b>N</b>" — the list's name in the genitive, linking its ``pkal`` page
  — then "Gimimo data:", sometimes "Gimimo vieta:", "Gyvenamoji vieta:".
  No photo, no winner note.
- The savivaldybių tarybų rinkimų įstatymo declarations as a small-font
  run of **unnumbered** "prompt: <b>answer</b>" lines: the unserved
  sentence, the armed/security service, another state's citizenship,
  collaboration with foreign services, a conviction since 1990 — five of
  the Seimas form's seven (no 8.4 oath, no 9.3 grave crime), with the
  2000 Seimas page's sub-question habit where the citizenship is "Turi".
- The questionnaire fields as "Label: <b>value</b>…" paragraphs (the
  Seimas page's table, read by its reader), education as a level
  ("Aukštasis") rather than the Seimas page's school lines.
- The 1996–1997 income and asset form inline, to the centas, with the
  section-I workplace lines.
- No autobiography.

Keys follow the 2000 Seimas record where the content is the same and the
2007 municipal general (`savivaldybiu_2007`) for the candidacy block;
elected status is the results-tree join (``results.py``).
"""
from __future__ import annotations

import errno
import json
from pathlib import Path
import re
from typing import Any

from bs4 import BeautifulSoup, NavigableString, Tag

from scraper.elections.ep_2004.results import load_ranking
from scraper.elections.savivaldybiu_2000.sitemap import ELECTION_ID, resolve_site_url
from scraper.elections.seimo_2000.anketa_parser import (
    MEMBER_PARTY_PATTERN,
    _bold_values,
    _labelled_bold,
    _load_candidate_meta,
    _place,
    _text,
)
from scraper.elections.seimo_2000.candidate_samples import CANDIDATE_PAGE_NAME
from scraper.elections.seimo_2016.anketa_parser import (
    _normalize_missing_values,
    _normalize_profile_data,
    _normalize_text_value,
    _order_dict_keys,
    normalize_space,
)
from scraper.elections.seimo_zirmunu_2015.anketa_parser import (
    _apply_results,
    _normalize_answer_value,
    load_results,
)
from scraper.shared.anomalies import build_anomaly_event
from scraper.shared.deklaracija_archive_1990s import parse_declaration
from scraper.shared.files import write_candidate_record
from scraper.shared.savivaldybiu_archive_1997 import normalize_birth_date

DEFAULT_SAMPLES_ROOT = Path(f"samples/html/{ELECTION_ID}")
DEFAULT_OUTPUT_ROOT = Path(f"data/{ELECTION_ID}")
# Elected status, joined in from VRK's results tree when the file exists.
DEFAULT_RESULTS_PATH = Path(f"sitemaps/{ELECTION_ID}.results.json")

MUNICIPALITY_NUMBER_PATTERN = re.compile(r"\(Nr\.\s*(\d+)\)")
LIST_NUMBER_PATTERN = re.compile(r"priešrinkiminis numeris sąraše:\s*(\d+)", re.IGNORECASE)

# The questionnaire labels the municipal cards use (no family members,
# hobbies or birthplace — the Seimas form's — on any of the pages read
# while building), to the 2000 Seimas keys. A label outside the table is
# kept in rawData and reported.
FIELD_KEYS = {
    "išsilavinimas": "issilavinimas",
    "moksliniai laipsniai": "mokslo-laipsnis",
    "moksliniai vardai": "pedagoginis-vardas",
    "užsienio kalbos": "uzsienio-kalbos",
    "buvo išrinktas į lietuvos respublikos aukščiausiąją tarybą, seimą, savivaldybių tarybas": "anksciau-isrinktas",
    "pagrindinė darbovietė": "pagrindine-darboviete",
    "visuomeninė veikla": "visuomenine-veikla",
    "šeimyninė padėtis": "seimine-padetis",
    "ką dar norėtų parašyti apie save": "kita-apie-save",
}

# The unnumbered declaration prompts, by their opening words, to the
# corpus keys (the 2016 Seimo names, as every other municipal general).
QUESTION_KEYS = (
    ("ar turi nebaigtą atlikti teismo", "ar-nebaigta-teismo-paskirta-bausme"),
    ("ar yra asmuo, atliekantis", "ar-atliekate-karo-tarnyba"),
    ("ar turi kitos valstybės pilietybę", "ar-turite-kitos-valstybes-pilietybe"),
    # The citizenship sub-questions, under a "Turi": this form says
    # "Kokios" where the Seimas form says "Kurios", and words the oath
    # renunciation as its own line.
    ("kokios", "kitos-valstybes-pilietybe-valstybe"),
    ("kurios", "kitos-valstybes-pilietybe-valstybe"),
    ("jei yra davęs kitos valstybės piliečio priesaiką", "priesaikos-uzsienio-valstybei-atsisakymas"),
    ("ar ne pagal lietuvos respublikos užduotis", "ar-bendradarbiavote-su-uzsienio-tarnybomis"),
    ("ar po 1990 m. kovo 11 d.", "ar-buvote-pripazintas-kaltu"),
)


def _question_key(prompt: str) -> str | None:
    lowered = prompt.lower()
    for prefix, key in QUESTION_KEYS:
        if lowered.startswith(prefix):
            return key
    return None


# ---------------------------------------------------------------------------
# Page
# ---------------------------------------------------------------------------


def _parse_card(paragraph: Tag) -> dict[str, Any]:
    plain = _text(paragraph)
    before, _, after = plain.partition("Sąrašas:")
    municipality = before.replace("Apygarda:", "", 1).strip().rstrip(",").strip()
    number_match = MUNICIPALITY_NUMBER_PATTERN.search(municipality)
    # A coalition's candidate: "(iškėlė <member party>, buvęs numeris
    # sąraše: N)" after the list number, as on the Seimas card.
    member_match = MEMBER_PARTY_PATTERN.search(after)
    if member_match:
        after = after[: member_match.start()]
    list_match = LIST_NUMBER_PATTERN.search(after)
    list_name = after[: list_match.start()] if list_match else after
    anchors = paragraph.find_all("a", href=True)
    return {
        "municipalityName": MUNICIPALITY_NUMBER_PATTERN.sub("", municipality).strip(),
        "municipalityNumber": int(number_match.group(1)) if number_match else None,
        "municipalityUrl": resolve_site_url(anchors[0]["href"]) if anchors else None,
        "listName": list_name.strip().rstrip(",").strip() or None,
        "listUrl": resolve_site_url(anchors[1]["href"]) if len(anchors) > 1 else None,
        "listPosition": int(list_match.group(1)) if list_match else None,
        "memberParty": normalize_space(member_match.group("party")) if member_match else None,
        "memberListNumber": int(member_match.group("number")) if member_match else None,
    }


def parse_candidate_html(html: str) -> dict[str, Any]:
    soup = BeautifulSoup(html, "lxml")
    result: dict[str, Any] = {
        "profile": {"candidateDisplayName": "", "electedNote": "", "photoSrc": "", "fields": []},
        "candidacy": None,
        "birthDate": None,
        "birthPlace": None,
        "residence": None,
        "questions": [],
        "fields": [],
        "declaration": None,
        "diagnostics": {"cardFound": False, "questionsFound": False, "declarationFound": False},
    }
    name_font = soup.find("font", attrs={"size": "5"})
    result["profile"]["candidateDisplayName"] = _text(name_font)

    blockquote = soup.find("blockquote")
    if blockquote is None:
        return result
    for paragraph in blockquote.find_all("p"):
        text = _text(paragraph)
        if text.startswith("Apygarda:"):
            result["diagnostics"]["cardFound"] = True
            card = _parse_card(paragraph)
            result["candidacy"] = card
            fields = [
                {"key": "Apygarda", "displayValue": f"{card['municipalityName']} (Nr. {card['municipalityNumber']})" if card["municipalityNumber"] else card["municipalityName"], "urls": [u for u in [card["municipalityUrl"]] if u]},
                {"key": "Sąrašas", "displayValue": card["listName"] or "", "urls": [u for u in [card["listUrl"]] if u]},
            ]
            if card["listPosition"] is not None:
                fields.append({"key": "priešrinkiminis numeris sąraše", "displayValue": str(card["listPosition"]), "urls": []})
            if card["memberParty"]:
                fields.append({"key": "iškėlė", "displayValue": card["memberParty"], "urls": []})
                fields.append({"key": "buvęs numeris sąraše", "displayValue": str(card["memberListNumber"]), "urls": []})
            result["profile"]["fields"] = fields
        elif text.startswith("Gimimo data:") or "Gyvenamoji vieta:" in text:
            raw = str(paragraph)
            result["birthDate"] = _labelled_bold(raw, "Gimimo data")
            result["birthPlace"] = _labelled_bold(raw, "Gimimo vieta")
            result["residence"] = _labelled_bold(raw, "Gyvenamoji vieta")
        elif paragraph.find("font", attrs={"size": "-1"}) is not None:
            result["diagnostics"]["questionsFound"] = True
            pending: list[str] = []
            questions: list[dict[str, Any]] = []
            for node in paragraph.find("font", attrs={"size": "-1"}).descendants:
                if isinstance(node, NavigableString):
                    if node.find_parent("b") is None:
                        pending.append(str(node))
                elif isinstance(node, Tag) and node.name == "b":
                    prompt = normalize_space(" ".join(pending)).rstrip(":").strip()
                    pending = []
                    if prompt:
                        questions.append({"prompt": prompt, "key": _question_key(prompt), "answer": _text(node)})
                    elif questions:
                        questions[-1]["explanation"] = normalize_space(" ".join(filter(None, [questions[-1].get("explanation"), _text(node)]))) or None
            result["questions"] = questions
        elif ":" in text:
            label = text.split(":", 1)[0].strip()
            if label:
                result["fields"].append({"label": label, "items": _bold_values(paragraph)})

    declaration_start = html.find("pagrindinių duomenų išrašas")
    if declaration_start >= 0:
        result["declaration"] = parse_declaration(html[declaration_start:])
        result["diagnostics"]["declarationFound"] = True
    return result


# ---------------------------------------------------------------------------
# Normalization
# ---------------------------------------------------------------------------


def normalize_anketa(parsed: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    """The questionnaire under the 2000 Seimas / 2007 municipal keys.
    Returns the block and the labels the key table does not know."""
    answers: dict[str, list[dict[str, Any]]] = {}
    for question in parsed["questions"]:
        if question["key"]:
            answers.setdefault(question["key"], []).append(question)

    def _answer(key: str) -> str | None:
        rows = answers.get(key)
        return _normalize_answer_value(rows[0]["answer"]) if rows else None

    def _answers(key: str) -> str | None:
        values = [v for row in answers.get(key, []) if (v := _normalize_answer_value(row["answer"]))]
        return ", ".join(values) if values else None

    fields: dict[str, list[dict[str, Any]]] = {}
    unknown: list[str] = []
    for field in parsed["fields"]:
        key = FIELD_KEYS.get(field["label"].lower())
        if key is None:
            unknown.append(field["label"])
            continue
        fields.setdefault(key, []).extend(field["items"])
    unknown.extend(q["prompt"] for q in parsed["questions"] if q["key"] is None)

    def _values(key: str) -> list[str]:
        return [item["value"] for item in fields.get(key, [])]

    def _single(key: str) -> str | None:
        values = _values(key)
        return _normalize_text_value(", ".join(values)) if values else None

    explanation = None
    for key in ("ar-buvote-pripazintas-kaltu", "ar-bendradarbiavote-su-uzsienio-tarnybomis"):
        for row in answers.get(key, []):
            if row.get("explanation"):
                explanation = row["explanation"]
                break
        if explanation:
            break

    birth_date = parsed["birthDate"]
    anketa = {
        "gimimo-data": normalize_birth_date(birth_date) if birth_date else None,
        "adresas": _place(parsed["residence"]),
        "pareiskimai": {
            "ar-nebaigta-teismo-paskirta-bausme": _answer("ar-nebaigta-teismo-paskirta-bausme"),
            "ar-atliekate-karo-tarnyba": _answer("ar-atliekate-karo-tarnyba"),
            "ar-turite-kitos-valstybes-pilietybe": _answer("ar-turite-kitos-valstybes-pilietybe"),
            "kitos-valstybes-pilietybe-valstybe": _answers("kitos-valstybes-pilietybe-valstybe"),
            "priesaikos-uzsienio-valstybei-atsisakymas": _answer("priesaikos-uzsienio-valstybei-atsisakymas"),
            "ar-bendradarbiavote-su-uzsienio-tarnybomis": _answer("ar-bendradarbiavote-su-uzsienio-tarnybomis"),
            "ar-buvote-pripazintas-kaltu": _answer("ar-buvote-pripazintas-kaltu"),
            "teisiniai-argumentai": _normalize_text_value(explanation),
        },
        # "Gimimo vieta" is on the card template; no page read so far
        # prints it. Kept so a page that does is not silently dropped.
        "gimimo-vieta": _place(parsed["birthPlace"]),
        # The municipal form asks the level ("Aukštasis"), as 1997 did,
        # not the Seimas form's school lines.
        "issilavinimas": {"aprasas": _single("issilavinimas"), "irasai": []},
        "mokslo-laipsnis": _single("mokslo-laipsnis"),
        "pedagoginis-vardas": _single("pedagoginis-vardas"),
        "uzsienio-kalbos": _values("uzsienio-kalbos"),
        "anksciau-isrinktas": {
            "aprasas": None,
            "irasai": [
                {"institucijos-pavadinimas-pareigos": value, "laikotarpis": None}
                for value in _values("anksciau-isrinktas")
            ],
        },
        "pagrindine-darboviete": _single("pagrindine-darboviete"),
        "visuomenine-veikla": _single("visuomenine-veikla"),
        "seimine-padetis": _single("seimine-padetis"),
        "kita-apie-save": _single("kita-apie-save"),
    }
    return anketa, unknown


# ---------------------------------------------------------------------------
# Record assembly
# ---------------------------------------------------------------------------


def build_candidacy(candidate_meta: dict[str, Any]) -> dict[str, Any]:
    """The listing's facts in the 2007 municipal general's shape: the
    municipality, the one role (council candidate — no mayoral vote in
    2000), the list with its kind, number, position and registration
    decision, the coalition's member parties where the list is one."""
    municipality = candidate_meta.get("municipality") or {}
    party_list = candidate_meta.get("list") or {}
    council: dict[str, Any] = {
        "partyList": party_list.get("pavadinimas"),
        "listKind": party_list.get("rusis"),
        "listNumber": party_list.get("numeris"),
        "sarasoId": party_list.get("sarasoId"),
        "listPosition": candidate_meta.get("listPosition"),
        "vrkSprendimas": party_list.get("vrkSprendimas"),
    }
    if party_list.get("koalicijosPartijos"):
        council["koalicijosPartijos"] = list(party_list["koalicijosPartijos"])
    return {
        "vrkCandidateId": str(candidate_meta.get("vrkCandidateId", "") or "").strip() or None,
        "savivaldybe": municipality.get("pavadinimas"),
        "savivaldybesNumeris": municipality.get("numeris"),
        "savivaldybesId": municipality.get("savivaldybesId"),
        "roles": ["tarybos-narys"],
        "tarybosNarys": council,
        "isrinktas": None,
    }


def finish_candidacy(candidacy: dict[str, Any], parsed: dict[str, Any]) -> list[dict[str, Any]]:
    """The card against the listing: the municipality number and the
    list position must agree (the card names the list in the genitive,
    so the name is not compared)."""
    card = parsed.get("candidacy")
    if not card:
        return [{"eventType": "CardCandidacyMissing", "detail": {}}]
    problems: list[dict[str, Any]] = []
    council = candidacy["tarybosNarys"]
    if card.get("memberParty"):
        # Only the card says which member party nominated a coalition's
        # candidate and where on that party's own list.
        council["koalicijosPartija"] = card["memberParty"]
        council["numerisPartijosSarase"] = card["memberListNumber"]
        if council.get("listKind") != "koalicija" or card["memberParty"] not in (council.get("koalicijosPartijos") or []):
            problems.append({"eventType": "CardMemberPartyMismatch", "detail": {"card": card["memberParty"], "sitemap": council.get("koalicijosPartijos")}})
    elif council.get("listKind") == "koalicija":
        problems.append({"eventType": "CardMemberPartyMissing", "detail": {"sitemap": council.get("koalicijosPartijos")}})
    if card["municipalityNumber"] != candidacy.get("savivaldybesNumeris"):
        problems.append({"eventType": "CardMunicipalityMismatch", "detail": {"card": card["municipalityNumber"], "sitemap": candidacy.get("savivaldybesNumeris")}})
    if card["listPosition"] != candidacy["tarybosNarys"].get("listPosition"):
        problems.append({"eventType": "CardListPositionMismatch", "detail": {"card": card["listPosition"], "sitemap": candidacy["tarybosNarys"].get("listPosition")}})
    return problems


def load_results_details(results_path: Path | None) -> dict[str, Any] | None:
    """The results file's per-list figures and the municipalities VRK's
    archive holds no per-candidate results for."""
    if results_path is None or not results_path.exists():
        return None
    payload = json.loads(results_path.read_text(encoding="utf-8"))
    details = payload.get("details") if isinstance(payload, dict) else None
    if not isinstance(details, dict):
        return None
    return {
        "listResults": details.get("listResults") or {},
        "unavailable": {row["municipalityId"]: row for row in details.get("resultsUnavailable") or []},
    }


def _apply_list_results(candidacy: dict[str, Any], details: dict[str, Any]) -> None:
    """The list's own result beside the candidate's: votes and mandates in
    the municipality. Where the archive has no per-candidate results,
    `isrinktas` goes back to unknown — the seats went to the list's top
    candidates after preference votes, which the archive does not say."""
    municipality_id = candidacy.get("savivaldybesId")
    council = candidacy.get("tarybosNarys") or {}
    list_id = (council or {}).get("sarasoId")
    row = (details["listResults"].get(municipality_id or "") or {}).get(list_id or "")
    if row:
        council["sarasoBalsai"] = row.get("total")
        council["sarasoMandatai"] = row.get("mandates") or 0
        council["sarasoRezultatuSaltinis"] = row.get("sourceUrl")
    unavailable = details["unavailable"].get(municipality_id or "")
    if unavailable:
        candidacy["isrinktas"] = None
        candidacy["rezultataiNeskelbiami"] = {
            "priezastis": "VRK archyvas saugo tik sąrašų balsus ir mandatus; išrinktų narių ir pirmumo balsų puslapiai neužfiksuoti",
            "nariuPuslapis": unavailable.get("membersUrl"),
        }


def _apply_ranking(candidacy: dict[str, Any], vrk_id: str | None, ranking_lookup: dict[str, dict[str, Any]]) -> None:
    row = ranking_lookup.get(vrk_id) if vrk_id else None
    if not isinstance(row, dict):
        return
    candidacy["porinkiminisNumerisSarase"] = row.get("rank")
    candidacy["pirmumoBalsai"] = row.get("preferenceVotes")
    candidacy["pirmumoBalsuSaltinis"] = row.get("sourceUrl")


def parse_anketa_sample(
    candidate_id: str,
    samples_root: Path = DEFAULT_SAMPLES_ROOT,
    output_root: Path = DEFAULT_OUTPUT_ROOT,
    results_path: Path | None = DEFAULT_RESULTS_PATH,
    results_lookup: dict[str, dict[str, Any]] | None = None,
    ranking_lookup: dict[str, dict[str, Any]] | None = None,
    results_details: dict[str, Any] | None = None,
) -> tuple[Path, dict[str, Any]]:
    if results_lookup is None:
        results_lookup = load_results(results_path)
    if ranking_lookup is None:
        ranking_lookup = load_ranking(results_path)
    if results_details is None:
        results_details = load_results_details(results_path)
    candidate_dir = samples_root / candidate_id
    page_path = candidate_dir / CANDIDATE_PAGE_NAME
    if not page_path.exists():
        raise FileNotFoundError(errno.ENOENT, "Missing candidate sample", str(page_path))

    parsed = parse_candidate_html(page_path.read_text(encoding="utf-8"))
    meta = _load_candidate_meta(candidate_dir)
    candidate_meta = meta.get("candidate", {}) if isinstance(meta.get("candidate"), dict) else {}
    source_url = candidate_meta.get("url")
    vrk_id = str(candidate_meta.get("vrkCandidateId", "") or "").strip() or None

    anomalies: list[dict[str, Any]] = []

    def _anomaly(event_type: str, severity: str, detail: dict[str, Any] | None = None) -> None:
        anomalies.append(
            build_anomaly_event(
                event_type=event_type,
                severity=severity,
                stage="parse",
                election_id=ELECTION_ID,
                candidate_id=candidate_id,
                source_url=source_url,
                detail=detail,
            )
        )

    diagnostics = parsed["diagnostics"]
    if not diagnostics["cardFound"]:
        _anomaly("ProfileCardMissing", "error")
    # The form omits a question the candidate left unanswered (seven
    # pages print just one), so a missing question is the page's blank;
    # an unknown prompt still surfaces as UnmappedCardLabel.
    if not diagnostics["questionsFound"]:
        _anomaly("AnketaTableNotFound", "critical")
    if not parsed["birthDate"]:
        _anomaly("BirthDateMissing", "warning")
    if not parsed["residence"]:
        _anomaly("ResidenceMissing", "warning")
    if not diagnostics["declarationFound"]:
        _anomaly("DeclarationSectionMissing", "warning")

    anketa, unknown_labels = normalize_anketa(parsed)
    if unknown_labels:
        _anomaly("UnmappedCardLabel", "warning", {"labels": unknown_labels})

    declaration = None
    if parsed["declaration"] is not None:
        declaration = parsed["declaration"]["declaration"]
        for event in parsed["declaration"]["anomalies"]:
            _anomaly(event["eventType"], event["severity"], event["detail"])

    candidacy = build_candidacy(candidate_meta)
    output_payload: dict[str, Any] = {
        "electionId": ELECTION_ID,
        "candidateId": candidate_id,
        "candidateName": parsed["profile"]["candidateDisplayName"] or str(candidate_meta.get("candidateName", "")).strip(),
        "kandidatavimas": candidacy,
    }
    if results_lookup is not None:
        _apply_results(output_payload, candidate_meta, source_url, results_lookup)
    if ranking_lookup is not None:
        _apply_ranking(candidacy, vrk_id, ranking_lookup)
    if results_details is not None:
        _apply_list_results(candidacy, results_details)
    for problem in finish_candidacy(candidacy, parsed):
        _anomaly(problem["eventType"], "warning", problem["detail"])

    raw_data: dict[str, Any] = {
        "profile": parsed["profile"],
        "candidacy": parsed["candidacy"],
        "anketa": {"rows": parsed["questions"], "fields": parsed["fields"]},
        "residence": parsed["residence"],
        "declaration": declaration,
    }
    normalized: dict[str, Any] = {
        "profilis": _normalize_profile_data(parsed["profile"]),
        "anketa": anketa,
        **({"turto-ir-pajamu-deklaracijos": declaration} if declaration else {}),
    }
    output_payload |= {
        "source": {"candidateSourceUrl": source_url},
        "rawData": raw_data,
        "normalized": _normalize_missing_values(
            _order_dict_keys(normalized, ["profilis", "anketa", "turto-ir-pajamu-deklaracijos"])
        ),
    }

    output_path = output_root / f"{candidate_id}-{ELECTION_ID}.json"
    write_candidate_record(output_path, output_payload)

    answered = sum(1 for q in parsed["questions"] if q["answer"]) + sum(1 for f in parsed["fields"] if f["items"])
    return output_path, {
        "candidateId": candidate_id,
        "candidateName": output_payload["candidateName"],
        "outputPath": str(output_path),
        "rowCount": len(parsed["questions"]) + len(parsed["fields"]),
        "answeredRowCount": answered,
        "anomalies": anomalies,
    }


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
            if child.is_dir() and (child / CANDIDATE_PAGE_NAME).exists()
        ]
    results_lookup = load_results(results_path)
    ranking_lookup = load_ranking(results_path)
    results_details = load_results_details(results_path)
    stats: list[dict[str, Any]] = []
    for candidate_id in target_ids:
        _, candidate_stats = parse_anketa_sample(
            candidate_id=candidate_id,
            samples_root=samples_root,
            output_root=output_root,
            results_path=results_path,
            results_lookup=results_lookup,
            ranking_lookup=ranking_lookup,
            results_details=results_details,
        )
        stats.append(candidate_stats)
    return stats


__all__ = [
    "QUESTION_KEYS",
    "build_candidacy",
    "finish_candidacy",
    "normalize_anketa",
    "parse_anketa_sample",
    "parse_anketa_samples",
    "parse_candidate_html",
]
