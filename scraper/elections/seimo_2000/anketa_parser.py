"""Candidate pages of the 2000-10-08 Seimas general election.

``kandvl.htm-<ID>.htm`` is the 1996-1998 archive's candidate page grown
into one document that carries everything the 2004 static site would
split across three pages:

- The profile card — the name as ``<font size="5">``, the photo, then one
  ``<p>`` per candidacy: "Apygarda: <b>Name</b> (Nr. N)" or "Apygarda:
  <b>Daugiamandatė</b>", with ", šioje apygardoje išrinktas Seimo nariu."
  where the candidate won that seat (the one era of the corpus's static
  pages that marks a winner on the card), "Iškėlė: <b>party</b>" and, for
  a list candidacy, ", priešrinkiminis numeris sąraše: <b>N</b>" and for a
  coalition's candidate "(iškėlė <b>member party</b>, buvęs numeris
  sąraše: <b>N</b>)". A third paragraph gives "Gimimo data:",
  sometimes "Gimimo vieta:", and "Gyvenamoji vieta:".
- The Seimo rinkimų įstatymo declarations as a ``<font size="-1">`` run:
  "8.1 … : <b>Neturi</b>" through "9.3 … : <b>Nebuvo</b>" — the 38 str.
  questions (8.1–8.4) and the 98 str. ones (9.1–9.3), the same seven the
  2004–2013 pages ask as Q8.x/Q9.x. A non-default 8.3 ("Turi") or 8.4
  ("Yra"/"Nenurodė") brings a sub-question — 8.3.1 "Kurios" (the state),
  8.4.1 "Jei yra, kaip ir kada raštu … atsisakė" — whose answer the page
  sometimes prints with no ``<b>`` at all, so the next prompt runs on.
- One ``<p>`` per questionnaire field (no nationality and no party
  membership — the 2004 form's Q11 and Q14 are not asked): "Išsilavinimas:" with one <b> per
  school ("1956 - Vilniaus universitetas Medicinos fakultetas, gydytojas"),
  "Moksliniai laipsniai:", "Moksliniai vardai:", "Užsienio kalbos:" (one
  <b> per language), "Buvo išrinktas į Lietuvos Respublikos Aukščiausiąją
  Tarybą, Seimą, savivaldybių tarybas:" (one <b> per mandate),
  "Pagrindinė darbovietė:", "Visuomeninė veikla:", "Pomėgiai:" (one <b>
  each), "Šeimyninė padėtis:" and "Šeimos nariai:" ("<b>Marta</b> -
  sutuoktinis/sutuoktinė"). A field the candidate left blank is not
  printed at all.
- The income and asset declaration extract under ``<a name="pajamos">``,
  the 1996-1997 form (``scraper/shared/deklaracija_archive_1990s.py``)
  with the figures to the centas, and the section-I workplace lines
  filled in.
- The autobiography under ``<a name="autobio">``, free text.

The record keeps the 2004 Seimas keys wherever the content is the same
(``anketa.pareiskimai``, ``issilavinimas``, ``uzsienio-kalbos`` …) and the
1990s family's declaration keys for the declaration. Elected status is
the results-tree join (``results.py``), with the card's own note kept in
``profilis.pastaba`` and cross-checked against it.
"""
from __future__ import annotations

import errno
import json
from pathlib import Path
import re
from typing import Any

from bs4 import BeautifulSoup, NavigableString, Tag

from scraper.elections.ep_2004.results import load_ranking
from scraper.elections.seimo_2000.candidate_samples import CANDIDATE_PAGE_NAME, DEFAULT_SAMPLES_ROOT
from scraper.elections.seimo_2000.sitemap import ELECTION_ID, resolve_site_url
from scraper.elections.seimo_2016.anketa_parser import (
    _normalize_biografija_data,
    _normalize_missing_values,
    _normalize_profile_data,
    _normalize_text_value,
    _order_dict_keys,
    normalize_space,
)
from scraper.elections.seimo_birzu_zarasu_ukmerges_2013.anketa_parser import build_candidacy
from scraper.elections.seimo_zirmunu_2015.anketa_parser import (
    _apply_results,
    _normalize_answer_value,
    load_results,
)
from scraper.shared.anomalies import build_anomaly_event
from scraper.shared.deklaracija_archive_1990s import parse_declaration
from scraper.shared.files import write_candidate_record
from scraper.shared.savivaldybiu_archive_1997 import normalize_birth_date

DEFAULT_OUTPUT_ROOT = Path(f"data/{ELECTION_ID}")
# Elected status, joined in from VRK's results tree when the file exists.
DEFAULT_RESULTS_PATH = Path(f"sitemaps/{ELECTION_ID}.results.json")

ELECTED_NOTE_PATTERN = re.compile(r"šioje apygardoje išrinkt\w*\s+Seimo\s+nar\w*", re.IGNORECASE)
CONSTITUENCY_NUMBER_PATTERN = re.compile(r"\(Nr\.\s*(\d+)\)")
LIST_NUMBER_PATTERN = re.compile(r"priešrinkiminis numeris sąraše:\s*(\d+)", re.IGNORECASE)
MEMBER_PARTY_PATTERN = re.compile(
    r"\(\s*iškėlė\s+(?P<party>.*?)\s*,\s*buvęs numeris sąraše:\s*(?P<number>\d+)\s*\)", re.IGNORECASE
)
QUESTION_PATTERN = re.compile(r"^\s*(\d\.\d(?:\.\d)?)\s+(.*?):?\s*$", re.S)
# Where a question's answer is missing altogether (a sub-question whose
# <b></b> the page dropped), the next prompt runs straight on; split the
# pending text at every question number.
QUESTION_SPLIT_PATTERN = re.compile(r"(?=(?<![\d.])\d\.\d(?:\.\d)?\s)")
MULTI_MEMBER = "daugiamandatė"
SELF_NOMINATED_MARKER = "išsikėlė"

# The questionnaire labels the cards use, to the corpus keys the 2004
# Seimas record has for the same questions. A label not in this table is
# kept in rawData and reported, so a new one is noticed rather than lost.
FIELD_KEYS = {
    "išsilavinimas": "issilavinimas",
    "moksliniai laipsniai": "mokslo-laipsnis",
    "moksliniai vardai": "pedagoginis-vardas",
    "užsienio kalbos": "uzsienio-kalbos",
    "buvo išrinktas į lietuvos respublikos aukščiausiąją tarybą, seimą, savivaldybių tarybas": "anksciau-isrinktas",
    "pagrindinė darbovietė": "pagrindine-darboviete",
    "visuomeninė veikla": "visuomenine-veikla",
    "pomėgiai": "pomegiai",
    "šeimyninė padėtis": "seimine-padetis",
    "šeimos nariai": "seimos-nariai",
}
SPOUSE_RELATIONS = {"sutuoktinis/sutuoktinė", "sutuoktinis", "sutuoktinė"}
CHILD_RELATIONS = {"vaikas"}


def _text(tag: Tag | NavigableString | None) -> str:
    if tag is None:
        return ""
    if isinstance(tag, NavigableString):
        return normalize_space(str(tag))
    return normalize_space(tag.get_text(" ", strip=True))


def _bold_values(paragraph: Tag) -> list[dict[str, Any]]:
    """Each <b> of a field paragraph with the plain text that trails it
    up to the next <b> ("<b>Marta</b> - sutuoktinis/sutuoktinė")."""
    items: list[dict[str, Any]] = []
    for bold in paragraph.find_all("b"):
        value = _text(bold)
        if not value:
            continue
        trail: list[str] = []
        sibling = bold.next_sibling
        while sibling is not None and not (isinstance(sibling, Tag) and sibling.name == "b"):
            if isinstance(sibling, NavigableString):
                trail.append(str(sibling))
            elif isinstance(sibling, Tag) and sibling.name != "br":
                trail.append(sibling.get_text(" ", strip=True))
            sibling = sibling.next_sibling
        note = normalize_space(" ".join(trail)).strip(" -–\u00a0")
        items.append({"value": value, "note": note or None})
    return items


# ---------------------------------------------------------------------------
# Card
# ---------------------------------------------------------------------------


def _parse_candidacy_paragraph(paragraph: Tag) -> dict[str, Any]:
    plain = _text(paragraph)
    anchors = [a for a in paragraph.find_all("a", href=True)]
    before, _, after = plain.partition("Iškėlė:")
    before = before.replace("Apygarda:", "", 1).strip()
    note_match = ELECTED_NOTE_PATTERN.search(before)
    elected_note = None
    if note_match is not None:
        elected_note = normalize_space(note_match.group(0))
        before = before[: note_match.start()]
    apygarda = before.strip().rstrip(",").strip().rstrip(".").strip()
    number_match = CONSTITUENCY_NUMBER_PATTERN.search(apygarda)
    apygarda_number = int(number_match.group(1)) if number_match else None
    apygarda_name = CONSTITUENCY_NUMBER_PATTERN.sub("", apygarda).strip()

    member_match = MEMBER_PARTY_PATTERN.search(after)
    member_party = normalize_space(member_match.group("party")) if member_match else None
    member_number = int(member_match.group("number")) if member_match else None
    if member_match:
        after = after[: member_match.start()] + after[member_match.end():]
    list_match = LIST_NUMBER_PATTERN.search(after)
    list_number = int(list_match.group(1)) if list_match else None
    if list_match:
        after = after[: list_match.start()]
    nominator = after.strip().rstrip(",").strip()

    apygarda_url = None
    nominator_url = None
    member_url = None
    for anchor in anchors:
        label = _text(anchor)
        href = resolve_site_url(anchor["href"])
        if apygarda_url is None and (label == apygarda_name or label.lower() == MULTI_MEMBER):
            apygarda_url = href
        elif nominator_url is None and label == nominator:
            nominator_url = href
        elif member_party and label == member_party:
            member_url = href
    return {
        "apygardaName": apygarda_name,
        "apygardaNumber": apygarda_number,
        "apygardaUrl": apygarda_url,
        "isMultiMember": apygarda_name.lower() == MULTI_MEMBER,
        "electedNote": elected_note,
        "nominator": nominator,
        "nominatorUrl": nominator_url,
        "listNumber": list_number,
        "memberParty": member_party,
        "memberPartyUrl": member_url,
        "memberListNumber": member_number,
    }


def _card_fields(candidacies: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """The card's lines in the 2004 `profile.fields` shape — key, display
    value, links — so `profilis.kita` reads as it does for 2004."""
    fields: list[dict[str, Any]] = []
    for candidacy in candidacies:
        apygarda = candidacy["apygardaName"]
        if candidacy["apygardaNumber"] is not None:
            apygarda = f"{apygarda} (Nr. {candidacy['apygardaNumber']})"
        if candidacy["electedNote"]:
            apygarda = f"{apygarda}, {candidacy['electedNote']}."
        fields.append({"key": "Apygarda", "displayValue": apygarda, "urls": [u for u in [candidacy["apygardaUrl"]] if u]})
        fields.append({"key": "Iškėlė", "displayValue": candidacy["nominator"], "urls": [u for u in [candidacy["nominatorUrl"]] if u]})
        if candidacy["listNumber"] is not None:
            fields.append({"key": "priešrinkiminis numeris sąraše", "displayValue": str(candidacy["listNumber"]), "urls": []})
        if candidacy["memberParty"]:
            fields.append({"key": "iškėlė", "displayValue": candidacy["memberParty"], "urls": [u for u in [candidacy["memberPartyUrl"]] if u]})
            fields.append({"key": "buvęs numeris sąraše", "displayValue": str(candidacy["memberListNumber"]), "urls": []})
    return fields


def _labelled_bold(html: str, label: str) -> str | None:
    match = re.search(re.escape(label) + r":\s*<b>(.*?)</b>", html, re.S | re.IGNORECASE)
    if match is None:
        return None
    return normalize_space(re.sub(r"<[^>]+>", " ", match.group(1))) or None


def parse_candidate_html(html: str) -> dict[str, Any]:
    soup = BeautifulSoup(html, "lxml")
    result: dict[str, Any] = {
        "profile": {"candidateDisplayName": "", "electedNote": "", "photoSrc": "", "fields": []},
        "candidacies": [],
        "birthDate": None,
        "birthPlace": None,
        "residence": None,
        "links": {"biography": False, "declaration": False},
        "questions": [],
        "fields": [],
        "declaration": None,
        "biography": None,
        "diagnostics": {"cardFound": False, "questionsFound": False, "declarationFound": False, "biographyFound": False},
    }

    name_font = soup.find("font", attrs={"size": "5"})
    result["profile"]["candidateDisplayName"] = _text(name_font)

    # The card: the table whose cell holds the "Apygarda:" paragraphs.
    card: Tag | None = None
    for paragraph in soup.find_all("p"):
        if _text(paragraph).startswith("Apygarda:"):
            card = paragraph.find_parent("td")
            break
    if card is not None:
        result["diagnostics"]["cardFound"] = True
        holder = card.find_parent("table")
        img = holder.find("img") if holder is not None else None
        if img is not None and img.get("src"):
            result["profile"]["photoSrc"] = resolve_site_url(img["src"])
        for paragraph in card.find_all("p"):
            text = _text(paragraph)
            if text.startswith("Apygarda:"):
                result["candidacies"].append(_parse_candidacy_paragraph(paragraph))
            elif text.startswith("Gimimo data:") or "Gyvenamoji vieta:" in text:
                raw = str(paragraph)
                result["birthDate"] = _labelled_bold(raw, "Gimimo data")
                result["birthPlace"] = _labelled_bold(raw, "Gimimo vieta")
                result["residence"] = _labelled_bold(raw, "Gyvenamoji vieta")
            else:
                for anchor in paragraph.find_all("a", href=True):
                    label = _text(anchor).lower()
                    if "autobio" in anchor["href"] or "biografija" in label:
                        result["links"]["biography"] = True
                    if "pajamos" in anchor["href"] or "deklaracija" in label:
                        result["links"]["declaration"] = True
        notes = [c["electedNote"] for c in result["candidacies"] if c["electedNote"]]
        result["profile"]["electedNote"] = "; ".join(notes)
        result["profile"]["fields"] = _card_fields(result["candidacies"])

    # The Q8/Q9 declarations: "8.1 prompt: <b>answer</b>" runs in the small
    # font. Text between answers is the next prompt; anything after the
    # last answered question that is not a prompt is its explanation.
    blockquote = card.find_parent("blockquote") if card is not None else soup.find("blockquote")
    small = blockquote.find("font", attrs={"size": "-1"}) if blockquote is not None else None
    if small is not None:
        result["diagnostics"]["questionsFound"] = True
        pending: list[str] = []
        questions: list[dict[str, Any]] = []
        def _take(prompt_text: str, answer: str | None) -> None:
            # The pending text may hold several prompts when an answer's
            # <b> is missing (8.4.1's is, where 8.4 is "Nenurodė"): every
            # prompt but the last is a question with no answer.
            segments = [normalize_space(part) for part in QUESTION_SPLIT_PATTERN.split(prompt_text)]
            segments = [part for part in segments if part]
            if not segments:
                if answer is not None and questions:
                    questions[-1]["explanation"] = normalize_space(
                        " ".join(filter(None, [questions[-1].get("explanation"), answer]))
                    ) or None
                return
            for index, segment in enumerate(segments):
                match = QUESTION_PATTERN.match(segment)
                last = index == len(segments) - 1
                if match is not None:
                    questions.append(
                        {
                            "questionNumber": match.group(1),
                            "prompt": normalize_space(match.group(2)),
                            "answer": (answer or "") if last else "",
                        }
                    )
                elif questions:
                    # A run with no question number continues the previous
                    # answer (the explanation).
                    extra = [questions[-1].get("explanation"), segment, answer if last else None]
                    questions[-1]["explanation"] = normalize_space(" ".join(filter(None, extra))) or None

        for node in small.descendants:
            if isinstance(node, NavigableString):
                if node.find_parent("b") is None:
                    pending.append(str(node))
            elif isinstance(node, Tag) and node.name == "b":
                prompt_text = " ".join(pending)
                pending = []
                _take(prompt_text, _text(node))
        trailing = " ".join(pending)
        if normalize_space(trailing):
            _take(trailing, None)
        result["questions"] = questions

    # The labelled field paragraphs after the questions.
    if blockquote is not None:
        for paragraph in blockquote.find_all("p"):
            if paragraph.find("font", attrs={"size": "-1"}) is not None or paragraph.find_parent("td") is not None:
                continue
            text = _text(paragraph)
            if ":" not in text:
                continue
            label = text.split(":", 1)[0].strip()
            if not label or label.startswith("Apygarda"):
                continue
            result["fields"].append({"label": label, "items": _bold_values(paragraph)})

    # The declaration extract and the autobiography, by their anchors.
    declaration_start = html.find('name="pajamos"')
    biography_start = html.find('name="autobio"')
    if declaration_start >= 0:
        section_end = biography_start if biography_start > declaration_start else len(html)
        result["declaration"] = parse_declaration(html[declaration_start:section_end])
        result["diagnostics"]["declarationFound"] = True
    if biography_start >= 0:
        anchor = soup.find("a", attrs={"name": "autobio"})
        container = anchor.find_parent("blockquote") if anchor is not None else None
        text = _text(container if container is not None else anchor)
        if text:
            result["biography"] = {"text": text}
            result["diagnostics"]["biographyFound"] = True
    return result


# ---------------------------------------------------------------------------
# Normalization
# ---------------------------------------------------------------------------


def _split_school(value: str) -> dict[str, Any]:
    """"1956 - Vilniaus universitetas Medicinos fakultetas, gydytojas":
    the year, then the school, then after the last comma the
    qualification (the page joins them that way)."""
    year = None
    rest = value
    match = re.match(r"^\s*(\d{4})\s*[-–]\s*(.*)$", value)
    if match:
        year, rest = match.group(1), match.group(2)
    school, _, specialty = rest.rpartition(",")
    if not school:
        school, specialty = specialty, ""
    return {
        "mokymo-istaigos-pavadinimas": normalize_space(school) or None,
        "specialybe": normalize_space(specialty) or None,
        "baigimo-metai": year,
    }


def _place(value: str | None) -> str | None:
    # "Jusiškio k. , Anykščių raj." — the page pads its commas.
    text = _normalize_text_value(value)
    return re.sub(r"\s+,", ",", text) if text else None


def normalize_anketa(parsed: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    """The questionnaire under the 2004 Seimas keys. Returns the block and
    the card labels the key table does not know."""
    answers: dict[str, dict[str, Any]] = {}
    for question in parsed["questions"]:
        answers.setdefault(question["questionNumber"], question)

    def _answer(number: str) -> str | None:
        row = answers.get(number)
        return _normalize_answer_value(row["answer"]) if row else None

    def _answers(number: str) -> str | None:
        values = [
            value
            for q in parsed["questions"]
            if q["questionNumber"] == number and (value := _normalize_answer_value(q["answer"]))
        ]
        return ", ".join(values) if values else None

    def _explanation(number: str) -> str | None:
        row = answers.get(number)
        return _normalize_text_value(row.get("explanation")) if row else None

    def _renunciation(value: str | None) -> str | None:
        # The slot prints as "<STATE> - <answer>" per declared citizenship,
        # the state in capitals; "JAV -" alone is the empty template.
        if not value:
            return None
        text = re.sub(r"^(?:[A-ZĄČĘĖĮŠŲŪŽ][A-ZĄČĘĖĮŠŲŪŽ .]*\s+-\s*)+", "", value).strip()
        return text or None

    fields: dict[str, list[dict[str, Any]]] = {}
    unknown: list[str] = []
    for field in parsed["fields"]:
        key = FIELD_KEYS.get(field["label"].lower())
        if key is None:
            unknown.append(field["label"])
            continue
        fields.setdefault(key, []).extend(field["items"])

    def _values(key: str) -> list[str]:
        return [item["value"] for item in fields.get(key, [])]

    def _single(key: str) -> str | None:
        values = _values(key)
        return _normalize_text_value(", ".join(values)) if values else None

    family = fields.get("seimos-nariai", [])
    spouse = [m["value"] for m in family if (m["note"] or "").lower() in SPOUSE_RELATIONS]
    children = [m["value"] for m in family if (m["note"] or "").lower() in CHILD_RELATIONS]

    # The Q9 explanation slot is the emphasised run after 9.3 (often a
    # bare "Ne"); an explanation under 9.1/9.2 is the same slot mid-block.
    explanation = None
    for number in ("9.3", "9.2", "9.1"):
        if answers.get(number, {}).get("explanation"):
            explanation = answers[number]["explanation"]
            break

    birth_date = parsed["birthDate"]
    anketa = {
        "gimimo-data": normalize_birth_date(birth_date) if birth_date else None,
        "adresas": _place(parsed["residence"]),
        "pareiskimai": {
            "ar-nebaigta-teismo-paskirta-bausme": _answer("8.1"),
            "ar-atliekate-karo-tarnyba": _answer("8.2"),
            "ar-turite-kitos-valstybes-pilietybe": _answer("8.3"),
            # 8.3.1 "Kurios" (one row per citizenship) and 8.4.1 "Jei yra,
            # kaip ir kada raštu šios priesaikos ar pasižadėjimo atsisakė"
            # print under a non-default 8.3/8.4 — 8.4.1 as a labelled row
            # after "Yra"/"Nenurodė", as a bare emphasised run after "Nėra".
            # The state goes under the EP form's key for the same fact.
            "kitos-valstybes-pilietybe-valstybe": _answers("8.3.1"),
            "ar-susijes-priesaika-uzsienio-valstybei": _answer("8.4"),
            "priesaikos-uzsienio-valstybei-atsisakymas": _renunciation(_answer("8.4.1") or _explanation("8.4")),
            "ar-bendradarbiavote-su-uzsienio-tarnybomis": _answer("9.1"),
            "ar-buvote-pripazintas-kaltu": _answer("9.2"),
            "ar-buvote-pripazintas-kaltu-del-sunkaus-nusikaltimo": _answer("9.3"),
            "teisiniai-argumentai": _normalize_text_value(explanation),
        },
        "gimimo-vieta": _place(parsed["birthPlace"]),
        "issilavinimas": {
            "aprasas": None,
            "irasai": [_split_school(value) for value in _values("issilavinimas")],
        },
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
        "pomegiai": _single("pomegiai"),
        "seimine-padetis": _single("seimine-padetis"),
        "sutuoktinio-vardas-pavarde": _normalize_text_value(", ".join(spouse)) if spouse else None,
        "vaiku-vardai-pavardes": _normalize_text_value(", ".join(children)) if children else None,
        "seimos-nariai": [{"vardas": m["value"], "rysys": m["note"]} for m in family],
    }
    return anketa, unknown


# ---------------------------------------------------------------------------
# Record assembly
# ---------------------------------------------------------------------------


def _load_candidate_meta(candidate_dir: Path) -> dict[str, Any]:
    index_path = candidate_dir / "index.json"
    if not index_path.exists():
        return {}
    try:
        payload = json.loads(index_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def finish_candidacy(candidacy: dict[str, Any], parsed: dict[str, Any]) -> list[dict[str, Any]]:
    """What the card says against the listing, as the 2004 module does:
    a further nominator for the same constituency as `kitiIskelejai`, and
    a list of {eventType, detail} for a card line the sitemap contradicts
    (the constituency, the list number, the coalition member party), so
    a disagreement between VRK's two publications is recorded, not
    silently resolved either way."""
    problems: list[dict[str, Any]] = []
    single = candidacy.get("vienmandate")
    multi = candidacy.get("daugiamandate")
    card_single = [c for c in parsed["candidacies"] if not c["isMultiMember"]]
    card_multi = [c for c in parsed["candidacies"] if c["isMultiMember"]]

    if isinstance(single, dict):
        if card_single:
            first = card_single[0]
            if first["apygardaNumber"] != single.get("apygardosNumeris"):
                problems.append({"eventType": "CardConstituencyMismatch", "detail": {"card": first["apygardaName"], "cardNumber": first["apygardaNumber"], "sitemap": single.get("apygarda"), "sitemapNumber": single.get("apygardosNumeris")}})
            listed = normalize_space(str(single.get("iskele") or "")).lower()
            extra = [c["nominator"] for c in card_single if c["nominator"].lower() != listed]
            if extra:
                single["kitiIskelejai"] = extra
        else:
            problems.append({"eventType": "CardConstituencyMissing", "detail": {"sitemap": single.get("apygarda")}})
    elif card_single:
        problems.append({"eventType": "CardConstituencyNotInSitemap", "detail": {"card": card_single[0]["apygardaName"]}})

    if isinstance(multi, dict):
        if card_multi:
            first = card_multi[0]
            if first["listNumber"] != multi.get("numerisSarase"):
                problems.append({"eventType": "CardListNumberMismatch", "detail": {"card": first["listNumber"], "sitemap": multi.get("numerisSarase")}})
            if (first["memberParty"] or None) != multi.get("koalicijosPartija") or (
                first["memberParty"] and first["memberListNumber"] != multi.get("numerisPartijosSarase")
            ):
                problems.append({"eventType": "CardMemberPartyMismatch", "detail": {"card": first["memberParty"], "cardNumber": first["memberListNumber"], "sitemap": multi.get("koalicijosPartija"), "sitemapNumber": multi.get("numerisPartijosSarase")}})
        else:
            problems.append({"eventType": "CardListMissing", "detail": {"sitemap": multi.get("sarasas")}})
    elif card_multi:
        problems.append({"eventType": "CardListNotInSitemap", "detail": {"card": card_multi[0]["nominator"]}})
    return problems


def _apply_ranking(candidacy: dict[str, Any], vrk_id: str | None, ranking_lookup: dict[str, dict[str, Any]]) -> None:
    row = ranking_lookup.get(vrk_id) if vrk_id else None
    if not isinstance(row, dict):
        return
    candidacy["porinkiminisNumerisSarase"] = row.get("rank")
    candidacy["pirmumoBalsai"] = row.get("preferenceVotes")
    candidacy["partinisReitingas"] = row.get("partyRating")
    candidacy["reitingoBalai"] = row.get("ratingPoints")
    candidacy["pirmumoBalsuSaltinis"] = row.get("sourceUrl")


def _apply_constituency_votes(candidacy: dict[str, Any], vrk_id: str | None, votes_lookup: dict[str, dict[str, Any]]) -> None:
    row = votes_lookup.get(vrk_id) if vrk_id else None
    if not isinstance(row, dict):
        return
    candidacy["vienmandatesBalsai"] = {
        "balsadezese": row.get("ballotBox"),
        "pastu": row.get("postal"),
        "isViso": row.get("total"),
        "procentai": row.get("percent"),
        "vieta": row.get("rank"),
        "saltinis": row.get("sourceUrl"),
    }


def load_constituency_votes(results_path: Path | None) -> dict[str, dict[str, Any]] | None:
    if results_path is None or not results_path.exists():
        return None
    payload = json.loads(results_path.read_text(encoding="utf-8"))
    details = payload.get("details") if isinstance(payload, dict) else None
    votes = details.get("constituencyVotes") if isinstance(details, dict) else None
    return votes if isinstance(votes, dict) else None


def parse_anketa_sample(
    candidate_id: str,
    samples_root: Path = DEFAULT_SAMPLES_ROOT,
    output_root: Path = DEFAULT_OUTPUT_ROOT,
    results_path: Path | None = DEFAULT_RESULTS_PATH,
    results_lookup: dict[str, dict[str, Any]] | None = None,
    ranking_lookup: dict[str, dict[str, Any]] | None = None,
    votes_lookup: dict[str, dict[str, Any]] | None = None,
) -> tuple[Path, dict[str, Any]]:
    if results_lookup is None:
        results_lookup = load_results(results_path)
    if ranking_lookup is None:
        ranking_lookup = load_ranking(results_path)
    if votes_lookup is None:
        votes_lookup = load_constituency_votes(results_path)
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
    if not diagnostics["questionsFound"]:
        _anomaly("AnketaTableNotFound", "critical")
    elif {q["questionNumber"] for q in parsed["questions"]} - {"8.3.1", "8.4.1"} != {"8.1", "8.2", "8.3", "8.4", "9.1", "9.2", "9.3"}:
        _anomaly("QuestionCountUnexpected", "warning", {"found": [q["questionNumber"] for q in parsed["questions"]]})
    if not parsed["birthDate"]:
        _anomaly("BirthDateMissing", "warning")
    if not parsed["residence"]:
        _anomaly("ResidenceMissing", "warning")
    if parsed["links"]["declaration"] and not diagnostics["declarationFound"]:
        _anomaly("DeclarationSectionMissing", "warning")
    if parsed["links"]["biography"] and not diagnostics["biographyFound"]:
        _anomaly("BiographySectionMissing", "warning")

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
        # The card's own winner note against the members page.
        card_elected = bool(parsed["profile"]["electedNote"])
        if card_elected != bool(candidacy.get("isrinktas")):
            _anomaly("ElectedNoteMismatch", "warning", {"card": parsed["profile"]["electedNote"], "results": candidacy.get("isrinktas")})
    if ranking_lookup is not None:
        _apply_ranking(candidacy, vrk_id, ranking_lookup)
    if votes_lookup is not None:
        _apply_constituency_votes(candidacy, vrk_id, votes_lookup)
    for problem in finish_candidacy(candidacy, parsed):
        _anomaly(problem["eventType"], "warning", problem["detail"])

    raw_data: dict[str, Any] = {
        "profile": parsed["profile"],
        "candidacies": parsed["candidacies"],
        "anketa": {"rows": parsed["questions"], "fields": parsed["fields"]},
        "residence": parsed["residence"],
        "biography": parsed["biography"],
        "declaration": declaration,
    }
    normalized: dict[str, Any] = {
        "profilis": _normalize_profile_data(parsed["profile"]),
        "anketa": anketa,
        "biografija": _normalize_biografija_data(parsed["biography"]) if parsed["biography"] else None,
        **({"turto-ir-pajamu-deklaracijos": declaration} if declaration else {}),
    }
    output_payload |= {
        "source": {"candidateSourceUrl": source_url},
        "rawData": raw_data,
        "normalized": _normalize_missing_values(
            _order_dict_keys(normalized, ["profilis", "anketa", "biografija", "turto-ir-pajamu-deklaracijos"])
        ),
    }

    output_path = output_root / f"{candidate_id}-{ELECTION_ID}.json"
    write_candidate_record(output_path, output_payload)

    answered = sum(1 for q in parsed["questions"] if q["answer"]) + sum(1 for f in parsed["fields"] if f["items"])
    stats = {
        "candidateId": candidate_id,
        "candidateName": output_payload["candidateName"],
        "outputPath": str(output_path),
        "rowCount": len(parsed["questions"]) + len(parsed["fields"]),
        "answeredRowCount": answered,
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
            if child.is_dir() and (child / CANDIDATE_PAGE_NAME).exists()
        ]
    results_lookup = load_results(results_path)
    ranking_lookup = load_ranking(results_path)
    votes_lookup = load_constituency_votes(results_path)
    stats: list[dict[str, Any]] = []
    for candidate_id in target_ids:
        _, candidate_stats = parse_anketa_sample(
            candidate_id=candidate_id,
            samples_root=samples_root,
            output_root=output_root,
            results_path=results_path,
            results_lookup=results_lookup,
            ranking_lookup=ranking_lookup,
            votes_lookup=votes_lookup,
        )
        stats.append(candidate_stats)
    return stats


__all__ = [
    "FIELD_KEYS",
    "finish_candidacy",
    "normalize_anketa",
    "parse_anketa_sample",
    "parse_anketa_samples",
    "parse_candidate_html",
]
