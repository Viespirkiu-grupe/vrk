"""Candidate pages of the 2002-12-22 municipal council general election.

Two pages per candidate on the 2002 LRS-ITD template, each one table
cell of ``<br>``-separated ``N. Prompt: <b>answer</b>`` lines under the
page's ``<h1>`` and the candidate's name as ``<h2>``:

- the anketa (saved as ``anketa.html``): the savivaldybių tarybų
  rinkimų įstatymo questions as Q5–Q19 with gaps — birth date (already
  ISO), residence, the 8.1–8.3 declarations, the 88 str. conviction
  question at Q9 followed by the article's text as an ``<i>``
  boilerplate block, birth place, nationality, education as a level,
  languages in one ``<b>`` with commas, prior mandates at Q15 either
  inline ("Nebuvo") or as indented "nuo: <b>1997</b> iki: <b>2000</b>
  <b>institution</b>" lines, workplace, public activity, marital
  status at Q19 with unnumbered "Sutuoktinio vardas:" and "Vaikų
  vardai:" lines trailing it. An unanswered question is printed with
  an empty ``<b>``; Q19 is omitted entirely on some pages.
- the declaration extract (``turto-ir-pajamu-deklaracijos.html``,
  "Lietuvos Respublikos gyventojo turto ir pajamų deklaracija"):
  numbered summary lines in litas — workplace, income and taxes, then
  start/end-of-period figures. Two variants exist: most pages print
  items 3–11, some insert a joint-bank-accounts item as 9 and run to
  12, so items are matched on wording, never on number. The form sums
  registrable assets with securities/art/jewellery into one figure
  (III S1 + IV S1), so the modern split is not recoverable — both
  modern keys are null and the combined start/end figures get their
  own keys, the ``deklaracija_archive_1990s`` convention. Item 8
  ("piniginių lėšų ne banke, banko sąskaitose ir indėlių bendra
  suma") is the modern ``pinigines-lesos`` fact at two dates: the
  end-of-period figure fills the modern key, both figures keep era
  keys.

The pages carry no candidacy facts at all — municipality, list and
position come from the sitemap (``kandidatavimas`` in the 2000/2007
municipal shape) and elected status, preference votes, the list's
result and the council-term join from the results tree
(``results.py``).
"""
from __future__ import annotations

import errno
import json
from pathlib import Path
import re
from typing import Any

from bs4 import BeautifulSoup, NavigableString, Tag

from scraper.elections.ep_2004.results import load_ranking
from scraper.elections.savivaldybiu_2002.sitemap import ELECTION_ID
from scraper.elections.seimo_2016.anketa_parser import (
    _find_row_by_question_number,
    _normalize_missing_values,
    _normalize_profile_data,
    _normalize_text_value,
    _order_dict_keys,
    _split_list_value,
    _tag_text,
    normalize_space,
)
from scraper.elections.seimo_zirmunu_2015.anketa_parser import (
    _apply_results,
    _normalize_answer_value,
    load_results,
)
from scraper.shared.anomalies import build_anomaly_event
from scraper.shared.deklaracijos import SCOPE_FAMILY, SCOPE_OWN
from scraper.shared.files import load_candidate_index, write_candidate_record
from scraper.shared.savivaldybiu_archive_1997 import normalize_birth_date
from scraper.shared.values import as_money

DEFAULT_SAMPLES_ROOT = Path(f"samples/html/{ELECTION_ID}")
DEFAULT_OUTPUT_ROOT = Path(f"data/{ELECTION_ID}")
# Elected status, joined in from VRK's results tree when the file exists.
DEFAULT_RESULTS_PATH = Path(f"sitemaps/{ELECTION_ID}.results.json")

DEKLARACIJA_FILE_NAME = "turto-ir-pajamu-deklaracijos.html"

QUESTION_START_PATTERN = re.compile(r"^\s*(\d{1,2}(?:\.\d{1,2})*)\.\s+")

# The known question numbers; anything else the pages print is reported.
# The form omits a question the candidate left unanswered: Q18
# (Pomėgiai) survives on one page of the 10,139, Q19 on most.
KNOWN_QUESTION_NUMBERS = {"5", "6", "8.1", "8.2", "8.3", "9", "10", "11", "12", "13", "15", "16", "17", "18", "19"}

# The declaration's summary lines, matched on their wording — the item
# numbers shift between the 11- and 12-item variants. Single-figure
# items map straight to a key; the two-figure items (start/end of the
# reporting period) are handled by the sub-line reader.
DEKLARACIJA_SINGLE_ITEMS = (
    ("gautų pajamų", "gautos-pajamos"),
    ("sumokėtų mokesčių", "sumoketas-pajamu-mokestis"),
    ("suteiktų paskolų", "suteiktos-paskolos"),
    ("gautų (ir iki metų pabaigos negrąžintų) paskolų", "gautos-paskolos"),
    ("kitų asmenų grąžintų paskolų", "grazintos-paskolos"),
    ("pasiskolintų (nesugrąžintų) ir dovanotų", "pasiskolintos-ir-dovanotos-lesos"),
)
DEKLARACIJA_RANGE_ITEMS = (
    ("privalomo registruoti turto", "turtas-ir-vertybiniai-popieriai"),
    ("piniginių lėšų ne banke", "pinigines-lesos"),
    ("bendros piniginės lėšos banko", "bendros-pinigines-lesos-banke"),
)

# The order the normalized declaration block's keys are emitted in;
# the corpus-wide keys first, the era's own after them.
DEKLARACIJA_OUTPUT_ORDER = [
    "privalomas-registruoti-turtas",
    "vertybiniai-popieriai-meno-kuriniai-juvelyriniai-dirbiniai",
    "pinigines-lesos",
    "suteiktos-paskolos",
    "gautos-paskolos",
    "gautos-pajamos",
    "sumoketas-pajamu-mokestis",
    "turtas-ir-vertybiniai-popieriai-laikotarpio-pradzioje",
    "turtas-ir-vertybiniai-popieriai-laikotarpio-pabaigoje",
    "pinigines-lesos-laikotarpio-pradzioje",
    "pinigines-lesos-laikotarpio-pabaigoje",
    "bendros-pinigines-lesos-banke-laikotarpio-pradzioje",
    "bendros-pinigines-lesos-banke-laikotarpio-pabaigoje",
    "grazintos-paskolos",
    "pasiskolintos-ir-dovanotos-lesos",
    "darboviete",
    "valiuta",
    "deklaracijos-apimtis",
]

# Whose declaration it is. The 2002 and 2003 pages print one of two forms --
# "Lietuvos Respublikos gyventojo turto ir pajamų deklaracija" and its šeimos
# variant -- and every numbered item follows suit, the individual form asking
# after "Deklaruotojo (įskaitant vaikų)" and the family one after
# "Deklaruotojų". So the scope is in the items whether or not the heading
# reached rawData: it did for 2003 (`forma`), and not for 2002.
#
# Measured over both elections: 10,135 of 2002's 10,138 records are individual
# declarations and three publish no item at all; 2003 splits 18 individual to
# 9 family. Neither election has a spouse declaration -- that is the 2007
# municipal form (see scraper/shared/deklaracijos.py).
DEKLARACIJA_SCOPE_MARKERS = (
    ("deklaruotojų", SCOPE_FAMILY),
    ("deklaruotojams", SCOPE_FAMILY),
    ("deklaruotojo", SCOPE_OWN),
    ("deklaruotojui", SCOPE_OWN),
)

__all__ = [
    "build_candidacy",
    "normalize_savivaldybiu_2002_anketa_rows",
    "parse_anketa_html",
    "parse_anketa_sample",
    "parse_anketa_samples",
    "parse_deklaracija_html",
]


# ---------------------------------------------------------------------------
# Page reading
# ---------------------------------------------------------------------------


def _content_cell(soup: BeautifulSoup) -> Tag | None:
    for h1 in soup.find_all("h1"):
        cell = h1.find_parent("td")
        if cell is not None:
            return cell
    return None


def _cell_lines(cell: Tag) -> list[list[Any]]:
    """The cell's children segmented at ``<br>`` into lines."""
    lines: list[list[Any]] = [[]]
    for node in cell.children:
        if isinstance(node, Tag) and node.name == "br":
            lines.append([])
            continue
        lines[-1].append(node)
    return [line for line in lines if any(_node_text(node) or isinstance(node, Tag) for node in line)]


def _node_text(node: Any) -> str:
    if isinstance(node, NavigableString):
        return normalize_space(str(node))
    if isinstance(node, Tag):
        return normalize_space(node.get_text(" ", strip=True))
    return ""


def _line_parts(line: list[Any]) -> list[tuple[str, str]]:
    """The line as ("text"|"bold", value) runs, header tags dropped."""
    parts: list[tuple[str, str]] = []
    for node in line:
        if isinstance(node, NavigableString):
            text = normalize_space(str(node))
            if text:
                parts.append(("text", text))
        elif isinstance(node, Tag):
            if node.name in ("h1", "h2", "center", "img", "span"):
                continue
            if node.name == "b":
                parts.append(("bold", _tag_text(node)))
            elif node.name == "i":
                parts.append(("italic", _tag_text(node)))
            else:
                bolds = node.find_all("b")
                if bolds:
                    for bold in bolds:
                        parts.append(("bold", _tag_text(bold)))
                else:
                    text = _tag_text(node)
                    if text:
                        parts.append(("text", text))
    return parts


def _parse_mandate_line(parts: list[tuple[str, str]]) -> dict[str, Any]:
    """One "nuo: <b>1997</b> iki: <b>2000</b> <b>institution</b>" line."""
    record: dict[str, Any] = {"nuo": None, "iki": None, "institucija": None}
    expecting: str | None = None
    institution: list[str] = []
    for kind, value in parts:
        if kind == "text":
            lowered = value.lower()
            if "nuo" in lowered:
                expecting = "nuo"
            elif "iki" in lowered:
                expecting = "iki"
        elif kind == "bold":
            if not value:
                expecting = None
                continue
            if expecting:
                record[expecting] = value
                expecting = None
            else:
                institution.append(value)
    if institution:
        record["institucija"] = normalize_space(" ".join(institution))
    return record


def parse_anketa_html(html: str) -> dict[str, Any]:
    soup = BeautifulSoup(html, "lxml")
    cell = _content_cell(soup)
    name = ""
    if cell is not None:
        h2 = cell.find("h2")
        if h2 is not None:
            name = normalize_space(h2.get_text(" ", strip=True))

    rows: list[dict[str, Any]] = []
    boilerplate: list[str] = []
    if cell is not None:
        for line in _cell_lines(cell):
            parts = _line_parts(line)
            if not parts:
                continue
            if any(kind == "italic" for kind, _ in parts):
                # The 88 str. legal excerpt printed under Q9 on every
                # page — the law's text, not the candidate's answer.
                boilerplate.append(
                    normalize_space(" ".join(value for _, value in parts))
                )
                continue
            first_kind, first_value = parts[0]
            if first_kind != "text":
                # A bold-only line is the explanation a "Taip" on Q9 is
                # followed by — the conviction's circumstances in a
                # blockquote of its own (27 pages of the 10,139).
                text = normalize_space(" ".join(value for kind, value in parts if kind == "bold"))
                if text and rows:
                    target = rows[-1]
                    target["explanation"] = normalize_space(
                        " ".join(filter(None, [target.get("explanation"), text]))
                    )
                continue
            lowered = first_value.lower()
            started = QUESTION_START_PATTERN.match(first_value)
            if lowered.startswith("nuo") and rows:
                # An indented mandate line under Q15 ("nuo: 1997 iki:
                # 2000 institution"), one per prior mandate.
                target = _find_row_by_question_number(rows, "15") or rows[-1]
                if target.get("records") is None:
                    target["records"] = []
                target["records"].append(_parse_mandate_line(parts))
                continue
            if started is None and ":" not in first_value:
                # The declaration link's label, a stray text run.
                continue
            prompt_parts: list[str] = []
            values: list[str] = []
            answered = False
            for kind, value in parts:
                if kind == "text" and not answered:
                    prompt_parts.append(value)
                elif kind == "bold":
                    answered = True
                    if value:
                        values.append(value)
            row: dict[str, Any] = {
                "questionNumber": started.group(1) if started else None,
                "prompt": normalize_space(" ".join(prompt_parts)),
                "answer": ", ".join(values),
            }
            if len(values) > 1:
                row["answerItems"] = values
            rows.append(row)

    for index, row in enumerate(rows, start=1):
        row["rowIndex"] = index
    answered_count = sum(1 for row in rows if row.get("answer") or row.get("records"))
    return {
        "profile": {
            "candidateDisplayName": name,
            "electedNote": "",
            "photoSrc": "",
            "fields": [],
        },
        "anketa": {
            "rows": rows,
            "boilerplate": boilerplate,
            "stats": {"rowCount": len(rows), "answeredRowCount": answered_count},
        },
        "diagnostics": {
            "contentCellFound": cell is not None,
            "nameFound": bool(name),
            "anketaRowsFound": bool(rows),
        },
    }


def normalize_savivaldybiu_2002_anketa_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    def _answer(question_number: str) -> str | None:
        row = _find_row_by_question_number(rows, question_number)
        return _normalize_answer_value(row.get("answer") if row else None)

    def _prompt_answer(prefix: str) -> str | None:
        for row in rows:
            if row.get("questionNumber") is None and row.get("prompt", "").lower().startswith(prefix):
                return _normalize_answer_value(row.get("answer"))
        return None

    mandates = []
    q15 = _find_row_by_question_number(rows, "15")
    for record in (q15 or {}).get("records") or []:
        laikotarpis = None
        if record.get("nuo") or record.get("iki"):
            laikotarpis = f"{record.get('nuo') or ''}–{record.get('iki') or ''}".strip("–")
        mandates.append(
            {
                "institucijos-pavadinimas-pareigos": record.get("institucija"),
                "laikotarpis": laikotarpis,
            }
        )

    birth_date = _answer("5")
    return {
        "gimimo-data": normalize_birth_date(birth_date) if birth_date else None,
        "adresas": _answer("6"),
        "pareiskimai": {
            "ar-nebaigta-teismo-paskirta-bausme": _answer("8.1"),
            "ar-atliekate-karo-tarnyba": _answer("8.2"),
            "ar-turite-kitos-valstybes-pilietybe": _answer("8.3"),
            # The conviction question, under the same 88 str. 1 d. the
            # later municipal forms cite (savivaldybiu_2007 maps the same
            # wording to this key), and the explanation a "Taip" is
            # followed by — a blockquote of its own on the page, the key
            # the rest of the family uses for it.
            "ar-buvote-pripazintas-kaltu": _answer("9"),
            "teisiniai-argumentai": _normalize_answer_value(
                (_find_row_by_question_number(rows, "9") or {}).get("explanation")
            ),
        },
        "gimimo-vieta": _answer("10"),
        "tautybe": _answer("11"),
        # The municipal form asks the level ("Aukštasis"), not school lines.
        "issilavinimas": {"aprasas": _answer("12"), "irasai": []},
        "uzsienio-kalbos": _split_list_value(
            (_find_row_by_question_number(rows, "13") or {}).get("answer")
        ),
        "anksciau-isrinktas": {"aprasas": _answer("15"), "irasai": mandates},
        "pagrindine-darboviete": _answer("16"),
        "visuomenine-veikla": _answer("17"),
        "pomegiai": _answer("18"),
        "seimine-padetis": _answer("19"),
        "sutuoktinio-vardas-pavarde": _prompt_answer("sutuoktinio vardas"),
        "vaiku-vardai-pavardes": _prompt_answer("vaikų vardai"),
    }


# ---------------------------------------------------------------------------
# Declaration page
# ---------------------------------------------------------------------------


def _parse_deklaracija_amount(value: Any) -> float | None:
    """A printed litas figure. The page glues the unit to the income
    figures ("25565Lt") and spaces it elsewhere ("151659 Lt."), which
    the 2015-era ``_parse_lt_amount``'s word-boundary strip cannot
    reach, so the unit is taken off the tail here."""
    text = _normalize_text_value(value)
    if text is None:
        return None
    compact = re.sub(r"lt\.?\s*$", "", text.replace("\xa0", " ").strip(), flags=re.IGNORECASE)
    compact = compact.replace(" ", "").replace(",", ".")
    if not compact or not re.fullmatch(r"-?\d+(?:\.\d+)?", compact):
        return None
    return as_money(float(compact))


def parse_deklaracija_html(html: str) -> dict[str, Any]:
    """The declaration's summary lines, in page order — each a prompt
    with its printed figure (or text for the workplace), the start/end
    sub-lines attached to the two-figure items."""
    soup = BeautifulSoup(html, "lxml")
    cell = _content_cell(soup)
    items: list[dict[str, Any]] = []
    if cell is None:
        return {"items": items, "found": False}
    for line in _cell_lines(cell):
        parts = _line_parts(line)
        if not parts:
            continue
        first_kind, first_value = parts[0]
        if first_kind != "text":
            continue
        values = [value for kind, value in parts if kind == "bold" and value]
        prompt = normalize_space(" ".join(value for kind, value in parts if kind == "text"))
        if not prompt or ":" not in first_value and not QUESTION_START_PATTERN.match(first_value):
            continue
        lowered = prompt.lower()
        if lowered.startswith("ataskaitinio laikotarpio"):
            period = "pradzioje" if "pradžioje" in lowered else "pabaigoje"
            if items:
                items[-1].setdefault("periods", {})[period] = values[0] if values else None
            continue
        items.append(
            {
                "prompt": prompt,
                "value": values[0] if values else None,
            }
        )
    return {"items": items, "found": True}


def normalize_deklaracija(
    payload: dict[str, Any],
    single_items: tuple[tuple[str, str], ...] = DEKLARACIJA_SINGLE_ITEMS,
    range_items: tuple[tuple[str, str], ...] = DEKLARACIJA_RANGE_ITEMS,
) -> tuple[dict[str, Any], list[str]]:
    """The corpus's ``turto-ir-pajamu-deklaracijos`` keys, plus the
    prompts the tables above do not know.

    The item tables are arguments because the same form is printed with
    other wordings elsewhere: the June 2003 Seimas election's pages carry
    two of the items misspelled and its family variant in the plural, so
    that module passes these tables extended with its own spellings.
    """
    declaration: dict[str, Any] = {key: None for key in DEKLARACIJA_OUTPUT_ORDER}
    # The form sums registrable assets with securities (III S1 + IV S1),
    # so the modern split is unrecoverable; both keys stay null and the
    # combined figures live under the era keys below.
    unknown: list[str] = []
    for item in payload.get("items", []):
        prompt = normalize_space(str(item.get("prompt", "")))
        lowered = prompt.lower()
        if lowered.startswith("3. darbovietė") or lowered.startswith("darbovietė"):
            declaration["darboviete"] = _normalize_text_value(item.get("value"))
            continue
        matched = False
        for marker, key in single_items:
            if marker in lowered:
                declaration[key] = _parse_deklaracija_amount(item.get("value"))
                matched = True
                break
        if matched:
            continue
        for marker, key_stem in range_items:
            if marker in lowered:
                periods = item.get("periods") or {}
                declaration[f"{key_stem}-laikotarpio-pradzioje"] = _parse_deklaracija_amount(
                    periods.get("pradzioje")
                )
                declaration[f"{key_stem}-laikotarpio-pabaigoje"] = _parse_deklaracija_amount(
                    periods.get("pabaigoje")
                )
                matched = True
                break
        if not matched:
            unknown.append(prompt)
    # Item 8's end-of-period figure is the modern key's fact: the money
    # held outside banks, in accounts and deposits.
    declaration["pinigines-lesos"] = declaration["pinigines-lesos-laikotarpio-pabaigoje"]
    declaration["valiuta"] = "Lt"
    declaration["deklaracijos-apimtis"] = _deklaracija_scope(payload)
    return declaration, unknown


def _deklaracija_scope(payload: dict[str, Any]) -> str | None:
    """`gyventojo` or `seimos`, from whichever of the two forms the page prints.

    The heading names it where the page's parser keeps one (`forma`, the 2003
    pages); otherwise the numbered items do, each addressed to "Deklaruotojo"
    on the individual form and "Deklaruotojų" on the family one. A page with
    neither -- three of 2002's records publish no item at all -- has no scope.
    """
    heading = normalize_space(str(payload.get("forma") or "")).lower()
    for marker, scope in (("šeimos", SCOPE_FAMILY), ("gyventojo", SCOPE_OWN)):
        if marker in heading:
            return scope
    for item in payload.get("items", []):
        if not isinstance(item, dict):
            continue
        lowered = normalize_space(str(item.get("prompt", ""))).lower()
        for marker, scope in DEKLARACIJA_SCOPE_MARKERS:
            if marker in lowered:
                return scope
    return None


# ---------------------------------------------------------------------------
# Record assembly
# ---------------------------------------------------------------------------


def build_candidacy(candidate_meta: dict[str, Any]) -> dict[str, Any]:
    """The listing's facts in the 2000/2007 municipal shape: the
    municipality, the one role (council candidate — mayors were not
    directly elected in 2002), the list with its kind, ballot number
    and position, the coalition's member parties and the member party
    that nominated the candidate where the list is one."""
    municipality = candidate_meta.get("municipality") or {}
    party_list = candidate_meta.get("list") or {}
    council: dict[str, Any] = {
        "partyList": party_list.get("pavadinimas"),
        "listKind": party_list.get("rusis"),
        "listNumber": party_list.get("numeris"),
        "listPosition": candidate_meta.get("listPosition"),
    }
    if party_list.get("koalicijosPartijos"):
        council["koalicijosPartijos"] = list(party_list["koalicijosPartijos"])
    if candidate_meta.get("koalicijosPartija"):
        council["koalicijosPartija"] = candidate_meta["koalicijosPartija"]
    return {
        "vrkCandidateId": str(candidate_meta.get("vrkCandidateId", "") or "").strip() or None,
        "savivaldybe": municipality.get("pavadinimas"),
        "savivaldybesNumeris": municipality.get("numeris"),
        "apygardosId": municipality.get("apygardosId"),
        "roles": ["tarybos-narys"],
        "tarybosNarys": council,
        "isrinktas": None,
    }


def load_results_details(results_path: Path | None) -> dict[str, Any] | None:
    """The results file's per-list figures and the council-term join."""
    if results_path is None or not results_path.exists():
        return None
    payload = json.loads(results_path.read_text(encoding="utf-8"))
    details = payload.get("details") if isinstance(payload, dict) else None
    if not isinstance(details, dict):
        return None
    return {
        "listResults": details.get("listResults") or {},
        "council": details.get("council") or {},
    }


def _apply_list_results(candidacy: dict[str, Any], details: dict[str, Any]) -> None:
    """The list's own result beside the candidate's: votes and mandates
    in the municipality, joined on (apygarda, ballot number)."""
    apygarda_id = candidacy.get("apygardosId")
    council = candidacy.get("tarybosNarys") or {}
    list_number = council.get("listNumber")
    if apygarda_id is None or list_number is None:
        return
    row = (details["listResults"].get(str(apygarda_id)) or {}).get(str(list_number))
    if row:
        council["sarasoBalsai"] = row.get("total")
        council["sarasoMandatai"] = row.get("mandates") or 0
        council["sarasoRezultatuSaltinis"] = row.get("sourceUrl")


def _apply_council(candidacy: dict[str, Any], vrk_id: str | None, details: dict[str, Any]) -> None:
    """The council-composition join: when this candidate held a seat
    during the term, from when — election day for those elected, later
    for the substitutes who came in when a member left."""
    row = details["council"].get(vrk_id) if vrk_id else None
    if not isinstance(row, dict):
        return
    candidacy["tarybosNarysNuo"] = row.get("nuo")
    candidacy["tarybosSudetiesSaltinis"] = row.get("sourceUrl")


def _apply_ranking(candidacy: dict[str, Any], vrk_id: str | None, ranking_lookup: dict[str, dict[str, Any]]) -> None:
    row = ranking_lookup.get(vrk_id) if vrk_id else None
    if not isinstance(row, dict):
        return
    candidacy["porinkiminisNumerisSarase"] = row.get("rank")
    candidacy["pirmumoBalsai"] = row.get("preferenceVotes")
    candidacy["pirmumoBalsuSaltinis"] = row.get("sourceUrl")


_load_candidate_meta = load_candidate_index


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
    anketa_path = candidate_dir / "anketa.html"
    if not anketa_path.exists():
        raise FileNotFoundError(errno.ENOENT, "Missing anketa sample", str(anketa_path))

    parsed = parse_anketa_html(anketa_path.read_text(encoding="utf-8"))
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
    if not diagnostics["nameFound"]:
        _anomaly("ProfileCardMissing", "error")
    if not diagnostics["anketaRowsFound"]:
        _anomaly("AnketaTableNotFound", "critical")

    rows = parsed["anketa"]["rows"]
    unknown_questions = sorted(
        {
            row["questionNumber"]
            for row in rows
            if row.get("questionNumber") and row["questionNumber"] not in KNOWN_QUESTION_NUMBERS
        }
    )
    if unknown_questions:
        _anomaly("UnmappedCardLabel", "warning", {"questionNumbers": unknown_questions})

    anketa = normalize_savivaldybiu_2002_anketa_rows(rows)
    if diagnostics["anketaRowsFound"] and not anketa["gimimo-data"]:
        _anomaly("BirthDateMissing", "warning")

    declaration = None
    deklaracija_raw = None
    deklaracija_path = candidate_dir / DEKLARACIJA_FILE_NAME
    if deklaracija_path.exists():
        try:
            deklaracija_raw = parse_deklaracija_html(deklaracija_path.read_text(encoding="utf-8"))
        except Exception as exc:
            _anomaly(
                "SubpageParseError",
                "error",
                {"subpage": "turto-ir-pajamu-deklaracijos", "sourcePath": str(deklaracija_path), "error": str(exc)},
            )
        else:
            if not deklaracija_raw["found"] or not deklaracija_raw["items"]:
                # VRK published the page with an empty table cell (three
                # of the 10,139): nothing to normalize, the anomaly is
                # the record of it.
                _anomaly("DeclarationSectionMissing", "warning")
            else:
                declaration, unknown_prompts = normalize_deklaracija(deklaracija_raw)
                if unknown_prompts:
                    _anomaly("UnmappedCardLabel", "warning", {"deklaracijaPrompts": unknown_prompts})
    else:
        _anomaly("DeclarationSectionMissing", "warning")

    candidacy = build_candidacy(candidate_meta)
    candidate_name = parsed["profile"]["candidateDisplayName"] or str(
        candidate_meta.get("candidateName", "")
    ).strip()
    output_payload: dict[str, Any] = {
        "electionId": ELECTION_ID,
        "candidateId": candidate_id,
        "candidateName": candidate_name,
        "kandidatavimas": candidacy,
    }
    if results_lookup is not None:
        _apply_results(output_payload, candidate_meta, source_url, results_lookup)
    if ranking_lookup is not None:
        _apply_ranking(candidacy, vrk_id, ranking_lookup)
    if results_details is not None:
        _apply_list_results(candidacy, results_details)
        _apply_council(candidacy, vrk_id, results_details)

    raw_data: dict[str, Any] = {
        "profile": parsed["profile"],
        "anketa": {"rows": rows},
        **({"deklaracija": deklaracija_raw} if deklaracija_raw is not None else {}),
    }
    normalized: dict[str, Any] = {
        "profilis": _normalize_profile_data(parsed["profile"]),
        "anketa": anketa,
        **(
            {"turto-ir-pajamu-deklaracijos": _order_dict_keys(declaration, DEKLARACIJA_OUTPUT_ORDER)}
            if declaration is not None
            else {}
        ),
    }
    output_payload |= {
        "source": {"candidateSourceUrl": source_url},
        "rawData": raw_data,
        "normalized": _normalize_missing_values(
            _order_dict_keys(normalized, ["profilis", "anketa", "turto-ir-pajamu-deklaracijos"])
        ),
    }

    output_path = output_root / f"{candidate_id}-{ELECTION_ID}.json"
    write_candidate_record(output_path, output_payload, source_path=anketa_path)

    stats = {
        "candidateId": candidate_id,
        "candidateName": candidate_name,
        "outputPath": str(output_path),
        "rowCount": parsed["anketa"]["stats"]["rowCount"],
        "answeredRowCount": parsed["anketa"]["stats"]["answeredRowCount"],
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
