"""Candidate pages of the 2004 European Parliament election.

The 2004 pages are VRK's original static site (the LRS-ITD template under
``rinkimai/2004/euro/``), not the 2015-era layout every later election of
the corpus shares, so the page readers here are this module's own; the
record they assemble keeps the corpus's sections and keys, and the
normalizers, the results join and the record writer are the shared ones.

What one candidate is:

- ``kand_anketa_l_<ID>.htm`` — the questionnaire. A profile card (photo,
  "Iškėlė:" linking the list page, "priešrinkiminis numeris sąraše:", the
  two sub-page links) followed by one ``<tr class="r1|r2">`` per question:
  ``N. Prompt: <b>answer</b>``, a list-type answer as several ``<b>``
  separated by commas (languages, hobbies, children), a record table
  (education at Q12, prior mandates at Q15) as a bordered ``table.basic``
  whose first row is the bold column names, and two unnumbered
  "label: <b>…</b>" pairs trailing their question (the degree and the
  academic title after the education table, the spouse after Q19). The
  question set is the 2009 EP one five years earlier: birth date at Q3,
  the rinkimų į Europos Parlamentą įstatymo declarations as Q8.1, 8.2 and
  8.4 (another member state's citizenship — 8.4.1/8.4.2 name it and ask
  whether the vote was withdrawn there; there is no 8.3), the lustration
  and conviction questions as Q9.1–9.3, then Q10–Q21 as every later form
  asks them. An unanswered question is printed with an empty ``<b>``.
- ``kand_biog_l_<ID>.htm`` — the free-text biography, one paragraph in a
  blockquote, usually opening with the name and nominator in capitals.
- ``kand_pajam_l_<ID>.htm`` — "Pajamų ir turto deklaracijų pagrindinių
  duomenų išrašai": two extracts, the family asset declaration (sections
  I–V with one total each) and the resident's income declaration (one
  income/tax pair per FR0462 form variant VRK knew of, five in all, "-"
  for the forms not filed), each with the issuing tax office, the receipt
  date, the filing date and the workplace.
"""
from __future__ import annotations

import errno
import json
from pathlib import Path
import re
from typing import Any

from bs4 import BeautifulSoup, NavigableString, Tag

from scraper.elections.ep_2004.candidate_samples import SUBPAGE_LINK_PATTERN
from scraper.elections.ep_2004.results import load_ranking
from scraper.elections.ep_2004.sitemap import ELECTION_ID, resolve_candidate_url
from scraper.elections.seimo_birzu_zarasu_ukmerges_2013.anketa_parser import build_candidacy
from scraper.elections.seimo_2016.anketa_parser import (
    _find_row_by_prompt_prefix,
    _find_row_by_question_number,
    _normalize_biografija_data,
    _normalize_missing_values,
    _normalize_profile_data,
    _normalize_table_records,
    _normalize_text_value,
    _order_dict_keys,
    _question_record_rows,
    _row_answer_text,
    _split_list_value,
    _tag_text,
    normalize_space,
)
from scraper.elections.seimo_zirmunu_2015.anketa_parser import (
    _apply_results,
    _normalize_answer_value,
    _parse_lt_amount,
    load_results,
)
from scraper.shared.anomalies import build_anomaly_event
from scraper.shared.deklaracijos import normalize_declaration
from scraper.shared.files import write_candidate_record
from scraper.shared.savivaldybiu_archive_1997 import normalize_birth_date

DEFAULT_SAMPLES_ROOT = Path(f"samples/html/{ELECTION_ID}")
DEFAULT_OUTPUT_ROOT = Path(f"data/{ELECTION_ID}")
# Elected status, joined in from VRK's results tree when the file exists.
DEFAULT_RESULTS_PATH = Path(f"sitemaps/{ELECTION_ID}.results.json")

QUESTION_START_PATTERN = re.compile(r"^\s*(\d{1,2}(?:\.\d{1,2})*)\.?\s+")
# Text runs that only separate one emphasised value from the next
# ("<b>Anglų</b>,&nbsp;<b>Rusų</b>").
SEPARATOR_TEXTS = {",", ".", ";"}
# "Moksliniai laipsniai: Moksliniai vardai:" — two labels, no values.
DOUBLE_LABEL_PATTERN = re.compile(r"([^:]+:)\s+([^:]+:)")

# The income extract's form lines: "1) FR0462 formos deklaracijos:".
INCOME_FORM_PATTERN = re.compile(r"^\d+\)\s*(?P<form>\S+)\s+formos\s+deklaracijos", re.IGNORECASE)
ISSUER_PATTERN = re.compile(r"Pagrindinių duomenų išrašą išdavė\s*(?P<issuer>.+?)\.\s*Gavimo data\s*(?P<date>[\d.]+)", re.DOTALL)


def _content_cell(soup: BeautifulSoup) -> Tag | None:
    return soup.find("td", class_="bigcell")


# ---------------------------------------------------------------------------
# Profile card
# ---------------------------------------------------------------------------


def _parse_profile_html(soup: BeautifulSoup) -> tuple[dict[str, Any], Tag | None]:
    profile: dict[str, Any] = {
        "candidateDisplayName": "",
        "electedNote": "",
        "photoSrc": "",
        "fields": [],
    }
    content = _content_cell(soup)
    if content is None:
        return profile, None

    # The first <h4> is the page title ("Kandidato į Europos parlamento
    # narius anketa"), the second the candidate's name.
    headings = [_tag_text(h4) for h4 in content.find_all("h4")]
    if len(headings) >= 2:
        profile["candidateDisplayName"] = headings[1]
    elif headings:
        profile["candidateDisplayName"] = headings[0]

    # The card is the cell whose own children are the "label: <b>value</b>"
    # runs. On the EP pages that is the first td.lt of the content; the
    # Seimas pages wrap the card in one more table, with the photo in a
    # sibling cell, so the cell with the emphasised values is searched for.
    card = None
    for cell in content.find_all("td", class_="lt"):
        if cell.find("b", recursive=False) is not None:
            card = cell
            break
    if card is None:
        return profile, None

    holder = card.find_parent("table")
    img = (holder or card).find("img")
    if img is not None:
        src = normalize_space(img.get("src", ""))
        if src:
            profile["photoSrc"] = resolve_candidate_url(src)

    fields: list[dict[str, Any]] = []
    pending_label = ""
    for node in card.children:
        if isinstance(node, NavigableString):
            text = normalize_space(str(node))
            if text:
                pending_label = f"{pending_label} {text}".strip() if pending_label else text
            continue
        if not isinstance(node, Tag):
            continue
        if node.name == "b":
            value = _tag_text(node)
            urls = [
                resolve_candidate_url(normalize_space(anchor["href"]))
                for anchor in node.find_all("a", href=True)
                if normalize_space(anchor["href"]) not in ("", "#")
            ]
            fields.append({"key": _card_label(pending_label), "displayValue": value, "urls": urls})
            pending_label = ""
            continue
        if node.name == "a":
            href = normalize_space(node.get("href", ""))
            if SUBPAGE_LINK_PATTERN.search(href):
                # The biography and declaration links are the page-set, saved
                # as sub-pages; they are not facts of the card.
                pending_label = ""
                continue
            label = _tag_text(node)
            urls = [resolve_candidate_url(href)] if href else []
            if pending_label and label:
                # A labelled link — the Seimas card's campaign registration
                # ("… Sprendimas - <a>Nr.316, 2004.09.20</a>", the decision
                # as a PDF): the link text is the value.
                fields.append({"key": _card_label(pending_label), "displayValue": label, "urls": urls})
            elif label or href:
                fields.append({"key": label, "displayValue": "", "urls": urls})
            pending_label = ""
    profile["fields"] = fields
    return profile, card


def _card_label(label: str) -> str:
    # "Iškėlė: <b>…</b>, priešrinkiminis numeris sąraše:" — the comma that
    # separates two labelled values on one line is not part of the label.
    return normalize_space(label).lstrip(", ").rstrip(":")


# ---------------------------------------------------------------------------
# Questionnaire rows
# ---------------------------------------------------------------------------


def _match_question_start(text: str) -> tuple[str, str] | None:
    match = QUESTION_START_PATTERN.match(text)
    if not match:
        return None
    return match.group(1), text[match.end():]


def _parse_record_table(table: Tag) -> list[dict[str, str]]:
    # A bordered table whose first row names the columns in bold and whose
    # other rows are the records.
    headers: list[str] = []
    records: list[dict[str, str]] = []
    for tr in table.find_all("tr"):
        cells = tr.find_all("td")
        if not cells:
            continue
        values = [_tag_text(cell) for cell in cells]
        if not headers:
            headers = values
            continue
        if not any(values):
            continue
        records.append(
            {
                headers[index] if index < len(headers) else f"stulpelis-{index + 1}": value
                for index, value in enumerate(values)
            }
        )
    return records


def _parse_anketa_row_cell(cell: Tag, record_table_reader: Any = None) -> list[dict[str, Any]]:
    """The rows of one ``<td class="lt">``: the numbered question, and any
    unnumbered "label: <b>…</b>" pair that trails it in the same cell.

    `record_table_reader` reads a Q12/Q15 record table; the June 2003
    election's tables print no header row, so that module supplies its own.
    """
    if record_table_reader is None:
        record_table_reader = _parse_record_table
    rows: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None

    def _flush() -> None:
        nonlocal current
        if current is None:
            return
        prompt = normalize_space(current["prompt"])
        if current["records"] is not None:
            answer: Any = current["records"]
        else:
            answer = ", ".join(current["values"])
        row: dict[str, Any] = {
            "questionNumber": current["questionNumber"],
            "prompt": prompt,
            "answer": answer,
        }
        if len(current["values"]) > 1:
            # The page prints a list-type answer as one <b> per item; the
            # joined string is the corpus's row shape, the items are kept so
            # a comma inside an item stays distinguishable from the list.
            row["answerItems"] = list(current["values"])
        if prompt or answer:
            rows.append(row)
        current = None

    def _start(question_number: str | None, prompt: str) -> None:
        nonlocal current
        _flush()
        current = {
            "questionNumber": question_number,
            "prompt": prompt,
            "values": [],
            "records": None,
            "answered": False,
        }

    for node in cell.children:
        if isinstance(node, NavigableString):
            text = normalize_space(str(node))
            if not text or text in SEPARATOR_TEXTS:
                continue
            started = _match_question_start(text)
            if started is not None:
                number, remainder = started
                _start(number, f"{number}. {normalize_space(remainder)}")
            elif DOUBLE_LABEL_PATTERN.fullmatch(text) and (current is None or current["answered"]):
                # Two labels in one text run with nothing between them: the
                # Seimas pages drop the empty <b></b> of an unanswered
                # degree or title, so "Moksliniai laipsniai: Moksliniai
                # vardai:" is two unanswered rows, not one prompt.
                first, second = DOUBLE_LABEL_PATTERN.fullmatch(text).groups()
                _start(None, first)
                current["answered"] = True
                _start(None, second)
            elif current is None or current["answered"]:
                _start(None, text)
            else:
                current["prompt"] = f"{current['prompt']} {text}".strip()
            continue
        if not isinstance(node, Tag):
            continue
        if node.name == "br":
            continue
        if node.name == "table":
            if current is None:
                _start(None, "")
            current["records"] = record_table_reader(node)
            current["answered"] = True
            continue
        if node.name == "b":
            if current is None:
                _start(None, "")
            text = _tag_text(node)
            if text:
                current["values"].append(text)
            # An empty <b> is the page's way of printing no answer; the
            # question is answered (with nothing), so a label that follows
            # starts a row of its own.
            current["answered"] = True
            continue
        text = _tag_text(node)
        if text and current is not None and not current["answered"]:
            current["prompt"] = f"{current['prompt']} {text}".strip()

    _flush()
    return rows


def _question_rows_table(content: Tag | None) -> Tag | None:
    """The table whose own rows are the questions — the r1/r2-classed rows
    under the card (the card's own row has no class)."""
    if content is None:
        return None
    for table in content.find_all("table"):
        body = table.find("tbody") or table
        if any(tr.get("class") for tr in body.find_all("tr", recursive=False)):
            return table
    return None


def _parse_anketa_rows(content: Tag | None) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    table = _question_rows_table(content)
    if table is not None:
        body = table.find("tbody") or table
        for tr in body.find_all("tr", recursive=False):
            if not tr.get("class"):
                continue
            cell = tr.find("td", recursive=False)
            if cell is None:
                continue
            rows.extend(_parse_anketa_row_cell(cell))
    for index, row in enumerate(rows, start=1):
        row["rowIndex"] = index
    answered = sum(1 for row in rows if row.get("answer"))
    return {
        "rows": rows,
        "stats": {"rowCount": len(rows), "answeredRowCount": answered},
    }


def _row_after(rows: list[dict[str, Any]], question_number: str) -> dict[str, Any] | None:
    """The unnumbered, unprompted row that directly follows a question —
    an answer the page prints without a label of its own."""
    row = _find_row_by_question_number(rows, question_number)
    if row is None:
        return None
    index = rows.index(row)
    if index + 1 >= len(rows):
        return None
    candidate = rows[index + 1]
    if candidate.get("questionNumber") or candidate.get("prompt"):
        return None
    return candidate


def normalize_ep_2004_anketa_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    def _answer(question_number: str) -> str | None:
        return _normalize_answer_value(
            _row_answer_text(_find_row_by_question_number(rows, question_number))
        )

    def _prompt_answer(prefix: str) -> str | None:
        return _normalize_answer_value(_row_answer_text(_find_row_by_prompt_prefix(rows, prefix)))

    birth_date = _answer("3")
    return {
        # "1942.01.01" on the page; the corpus's ISO form, which the
        # cross-election person index keys on.
        "gimimo-data": normalize_birth_date(birth_date) if birth_date else None,
        "adresas": _answer("6"),
        "pareiskimai": {
            "ar-nebaigta-teismo-paskirta-bausme": _answer("8.1"),
            "ar-atliekate-karo-tarnyba": _answer("8.2"),
            # Q8.4 here is the 2009 form's Q8.3 — citizenship of another EU
            # member state — with the same two sub-questions under it.
            "ar-turite-kitos-valstybes-pilietybe": _answer("8.4"),
            "kitos-valstybes-pilietybe-valstybe": _answer("8.4.1"),
            "ar-atimta-balsavimo-teise-kitoje-valstybeje": _answer("8.4.2"),
            "ar-bendradarbiavote-su-uzsienio-tarnybomis": _answer("9.1"),
            "ar-buvote-pripazintas-kaltu": _answer("9.2"),
            "ar-buvote-pripazintas-kaltu-del-sunkaus-nusikaltimo": _answer("9.3"),
            # The Q9 block's free-text explanation — the line the 2009 EP
            # and 2012 Seimo forms prompt ("Tuo atveju, jei bent į vieną 9
            # punkto klausimą atsakėte Taip …") is printed here as an
            # unlabelled emphasised row right after 9.3, on the five pages
            # that have one; the corpus key for the slot.
            "teisiniai-argumentai": _normalize_answer_value(_row_answer_text(_row_after(rows, "9.3"))),
        },
        "gimimo-vieta": _answer("10"),
        "tautybe": _answer("11"),
        "issilavinimas": {
            "aprasas": _answer("12"),
            "irasai": _normalize_table_records(_question_record_rows(rows, "12")),
        },
        "mokslo-laipsnis": _prompt_answer("moksliniai laipsniai"),
        "pedagoginis-vardas": _prompt_answer("moksliniai vardai"),
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


def parse_anketa_html(html: str, rows_normalizer: Any = None) -> dict[str, Any]:
    soup = BeautifulSoup(html, "lxml")
    profile, card = _parse_profile_html(soup)
    anketa = _parse_anketa_rows(_content_cell(soup))
    if rows_normalizer is None:
        rows_normalizer = normalize_ep_2004_anketa_rows
    anketa["normalized"] = rows_normalizer(anketa["rows"])
    return {
        "profile": profile,
        "anketa": anketa,
        "diagnostics": {
            "profileCardFound": card is not None,
            "contentDivFound": _content_cell(soup) is not None,
            "anketaTableFound": bool(anketa["rows"]),
            "anketaPlaceholder": False,
            "placeholderText": "",
        },
    }


# ---------------------------------------------------------------------------
# Sub-pages
# ---------------------------------------------------------------------------


def _parse_biografija_html(html: str) -> dict[str, Any]:
    soup = BeautifulSoup(html, "lxml")
    content = _content_cell(soup)
    body = content.find("blockquote") if content is not None else None
    if body is None:
        return {"text": "", "html": ""}
    # <br /> separates the lines; get_text's separator keeps them apart.
    return {
        "text": normalize_space(body.get_text(" ", strip=True)),
        "html": str(body),
    }


def _parse_deklaracijos_html(html: str) -> dict[str, Any]:
    """The two extracts as sections of key/value items, in page order.

    Each section keeps the issuer and dates the page prints above its table,
    and its items as the page labels them: the asset sections' roman
    headings ("I. PRIVALOMAS REGISTRUOTI TURTAS") as the keys of their
    totals, the income form lines ("1) FR0462 formos deklaracijos") as the
    keys of a two-field item.
    """
    soup = BeautifulSoup(html, "lxml")
    content = _content_cell(soup)
    sections: list[dict[str, Any]] = []
    if content is None:
        return {"sections": sections, "note": ""}

    for heading in content.find_all("h5"):
        title = _tag_text(heading)
        # The two extracts' headings stand in the page body; the roman
        # section headings inside the asset table are also <h5>, in a cell.
        if not title or (heading.parent is not None and heading.parent.name == "td"):
            continue
        section: dict[str, Any] = {"title": title, "issuer": "", "receivedDate": "", "items": []}
        holder = heading.find_next_sibling("div")
        if holder is None:
            sections.append(section)
            continue
        lead = normalize_space(" ".join(holder.find_all(string=True, recursive=False)))
        lead_bold = [_tag_text(b) for b in holder.find_all("b", recursive=False)]
        if "išrašą išdavė" in lead and len(lead_bold) >= 2:
            section["issuer"] = lead_bold[0]
            section["receivedDate"] = lead_bold[1]
        table = holder.find("table")
        items: list[dict[str, str]] = []
        pending_form: dict[str, Any] | None = None
        for tr in table.find_all("tr") if table is not None else []:
            cells = tr.find_all("td")
            if not cells:
                continue
            if len(cells) == 1:
                cell = cells[0]
                inner_heading = cell.find("h5")
                if inner_heading is not None:
                    pending_form = None
                    items.append({"key": _tag_text(inner_heading), "value": ""})
                    continue
                text = _tag_text(cell)
                form = INCOME_FORM_PATTERN.match(text)
                if form is not None:
                    pending_form = {"key": text.rstrip(":"), "form": form.group("form"), "value": ""}
                    items.append(pending_form)
                    continue
                bold = cell.find("b")
                label = normalize_space(text.replace(_tag_text(bold), "", 1)) if bold is not None else text
                items.append({"key": label.rstrip(":"), "value": _tag_text(bold) if bold is not None else ""})
                pending_form = None
                continue
            key = _tag_text(cells[0]).rstrip(":")
            value = _tag_text(cells[1])
            if pending_form is not None:
                if key.lower().startswith("gautų pajamų"):
                    pending_form["income"] = value
                    continue
                if key.lower().startswith("išskaičiuota"):
                    pending_form["tax"] = value
                    continue
            # A roman-headed asset section is one heading item followed by
            # its single total; the total fills the heading's value.
            if items and items[-1]["value"] == "" and "form" not in items[-1] and re.match(r"^[IVX]+\.", items[-1]["key"]):
                items[-1]["value"] = value
                items[-1]["label"] = key
                continue
            items.append({"key": key, "value": value})
        section["items"] = items
        sections.append(section)

    return {"sections": sections, "note": ""}


def _income_form_lines(item: dict[str, Any]) -> list[dict[str, Any]] | None:
    """One income line of the 2004 pages' per-form table.

    The page lists the five income-tax returns the tax office knew of --
    FR0462 and its S, S0, S15 and S33 variants -- with a dash against the four
    the candidate did not file. The declared income is the sum of the lines.
    """
    if "form" not in item:
        return None
    return [
        {
            "forma": item["form"],
            "gautos-pajamos": _parse_lt_amount(item.get("income")),
            "sumoketas-pajamu-mokestis": _parse_lt_amount(item.get("tax")),
        }
    ]


def _normalize_deklaracijos_data(payload: dict[str, Any]) -> dict[str, Any]:
    normalized = normalize_declaration(payload, _parse_lt_amount, form_lines=_income_form_lines)

    sections = payload.get("sections") if isinstance(payload.get("sections"), list) else []
    extracts: dict[str, Any] = {}
    for section in sections:
        if not isinstance(section, dict):
            continue
        title = normalize_space(str(section.get("title", "")))
        kind = "turto" if "TURTO" in title.upper() else "pajamu" if "PAJAM" in title.upper() else None
        if kind is None:
            continue
        meta: dict[str, Any] = {
            "pavadinimas": _normalize_text_value(title),
            "israsa-isdave": _normalize_text_value(section.get("issuer")),
            "gavimo-data": _normalize_iso_date(section.get("receivedDate")),
            "darboviete": None,
            "pildymo-data": None,
        }
        for item in section.get("items", []):
            if not isinstance(item, dict):
                continue
            key_lower = normalize_space(str(item.get("key", ""))).lower()
            if key_lower.startswith("3. darbovietė") or key_lower == "darbovietė":
                meta["darboviete"] = _normalize_text_value(item.get("value"))
            elif key_lower.startswith("pildymo data"):
                meta["pildymo-data"] = _normalize_iso_date(item.get("value"))
        extracts[kind] = meta

    normalized["valiuta"] = "Lt"
    normalized["pastaba"] = _normalize_text_value(payload.get("note"))
    # Who issued each extract, when they received it and what the candidate
    # gave as their workplace -- facts of the 2004 pages that no later era
    # prints, so they keep a block of their own rather than a shared key.
    normalized["israsai"] = {
        "turto-deklaracija": extracts.get("turto"),
        "pajamu-deklaracija": extracts.get("pajamu"),
    }
    return normalized


def _normalize_iso_date(value: Any) -> str | None:
    text = _normalize_text_value(value)
    if text is None:
        return None
    return normalize_birth_date(text)


# ---------------------------------------------------------------------------
# Record assembly
# ---------------------------------------------------------------------------

SUBPAGES: dict[str, tuple[str, Any]] = {
    "biografija": ("biografija.html", _parse_biografija_html),
    "turtoIrPajamuDeklaracijos": ("turto-ir-pajamu-deklaracijos.html", _parse_deklaracijos_html),
}


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
    ranking_lookup: dict[str, dict[str, Any]] | None = None,
    election_id: str = ELECTION_ID,
    rows_normalizer: Any = None,
    candidacy_finisher: Any = None,
) -> tuple[Path, dict[str, Any]]:
    """Parse one candidate's saved pages into the corpus record.

    The 2004 Seimas module runs this with its own election id, question
    mapping and a `candidacy_finisher(output_payload, parsed_anketa)` that
    adds what its card says beyond the listing.
    """
    if results_lookup is None:
        results_lookup = load_results(results_path)
    if ranking_lookup is None:
        ranking_lookup = load_ranking(results_path)
    candidate_dir = samples_root / candidate_id
    anketa_path = candidate_dir / "anketa.html"
    if not anketa_path.exists():
        raise FileNotFoundError(errno.ENOENT, "Missing anketa sample", str(anketa_path))

    parsed = parse_anketa_html(anketa_path.read_text(encoding="utf-8"), rows_normalizer=rows_normalizer)
    meta = _load_candidate_meta(candidate_dir)
    candidate_meta = meta.get("candidate", {}) if isinstance(meta.get("candidate"), dict) else {}
    source_url = candidate_meta.get("url")

    anomalies: list[dict[str, Any]] = []
    diagnostics = parsed["diagnostics"]
    if not diagnostics["profileCardFound"]:
        anomalies.append(
            build_anomaly_event(
                event_type="ProfileCardMissing",
                severity="error",
                stage="parse",
                election_id=election_id,
                candidate_id=candidate_id,
                source_url=source_url,
            )
        )
    if not diagnostics["anketaTableFound"]:
        anomalies.append(
            build_anomaly_event(
                event_type="AnketaTableNotFound",
                severity="critical",
                stage="parse",
                election_id=election_id,
                candidate_id=candidate_id,
                source_url=source_url,
            )
        )

    raw_data: dict[str, Any] = {
        "profile": parsed["profile"],
        "anketa": {"rows": parsed["anketa"]["rows"]},
    }
    normalized: dict[str, Any] = {
        "profilis": _normalize_profile_data(parsed["profile"]),
        "anketa": parsed["anketa"]["normalized"],
    }

    for key, (filename, parser) in SUBPAGES.items():
        path = candidate_dir / filename
        if not path.exists():
            continue
        try:
            data = parser(path.read_text(encoding="utf-8"))
        except Exception as exc:
            anomalies.append(
                build_anomaly_event(
                    event_type="SubpageParseError",
                    severity="error",
                    stage="parse",
                    election_id=election_id,
                    candidate_id=candidate_id,
                    source_url=source_url,
                    detail={"subpage": key, "sourcePath": str(path), "error": str(exc)},
                )
            )
            continue
        raw_data[key] = data
        if key == "biografija":
            normalized["biografija"] = _normalize_biografija_data(data)
        elif key == "turtoIrPajamuDeklaracijos":
            normalized["turto-ir-pajamu-deklaracijos"] = _normalize_deklaracijos_data(data)

    candidate_name = str(candidate_meta.get("candidateName", "")).strip() or parsed["profile"]["candidateDisplayName"]
    output_payload: dict[str, Any] = {
        "electionId": election_id,
        "candidateId": candidate_id,
        "candidateName": candidate_name,
        "kandidatavimas": build_candidacy(candidate_meta),
    }
    if results_lookup is not None:
        _apply_results(output_payload, candidate_meta, source_url, results_lookup)
        _apply_mandate_notes(output_payload, candidate_meta, results_lookup)
    if ranking_lookup is not None:
        _apply_ranking(output_payload, candidate_meta, ranking_lookup)
    if candidacy_finisher is not None:
        candidacy_finisher(output_payload, parsed)
    output_payload |= {
        "source": {"candidateSourceUrl": source_url},
        "rawData": _order_dict_keys(raw_data, ["profile", "anketa", "biografija", "turtoIrPajamuDeklaracijos"]),
        "normalized": _normalize_missing_values(
            _order_dict_keys(normalized, ["profilis", "anketa", "biografija", "turto-ir-pajamu-deklaracijos"])
        ),
    }

    output_path = output_root / f"{candidate_id}-{election_id}.json"
    write_candidate_record(output_path, output_payload)

    stats = {
        "candidateId": candidate_id,
        "candidateName": candidate_name,
        "outputPath": str(output_path),
        "rowCount": parsed["anketa"]["stats"]["rowCount"],
        "answeredRowCount": parsed["anketa"]["stats"]["answeredRowCount"],
        "anomalies": anomalies,
    }
    return output_path, stats


def _apply_mandate_notes(
    output_payload: dict[str, Any],
    candidate_meta: dict[str, Any],
    results_lookup: dict[str, dict[str, Any]],
) -> None:
    # The results builder records the one post-election substitution VRK's
    # page names (a mandate given up before the term and the list's next
    # member recognised in the seat); the era join carries seat, source and
    # annulment only, so the substitution facts are copied here.
    vrk_id = str(candidate_meta.get("vrkCandidateId", "") or "").strip()
    hit = results_lookup.get(vrk_id) if vrk_id else None
    if not isinstance(hit, dict):
        return
    candidacy = output_payload["kandidatavimas"]
    for source_key, target_key in (
        ("mandateTerminated", "mandatasNutrauktas"),
        ("replacementFor", "pakeiteNari"),
        ("decision", "vrkSprendimas"),
    ):
        if hit.get(source_key) is not None:
            candidacy[target_key] = hit[source_key]


def _apply_ranking(
    output_payload: dict[str, Any],
    candidate_meta: dict[str, Any],
    ranking_lookup: dict[str, dict[str, Any]],
) -> None:
    # The list's post-preference ranking page: where the candidate finished
    # after preference votes were counted, and how many they got. The
    # modern eras print the post-election position on the card
    # (porinkiminis-numeris-sarase); here it is a results-tree join.
    vrk_id = str(candidate_meta.get("vrkCandidateId", "") or "").strip()
    row = ranking_lookup.get(vrk_id) if vrk_id else None
    if not isinstance(row, dict):
        return
    candidacy = output_payload["kandidatavimas"]
    candidacy["porinkiminisNumerisSarase"] = row.get("rank")
    candidacy["pirmumoBalsai"] = row.get("preferenceVotes")
    candidacy["pirmumoBalsuSaltinis"] = row.get("sourceUrl")


def parse_anketa_samples(
    candidate_ids: list[str] | None,
    samples_root: Path = DEFAULT_SAMPLES_ROOT,
    output_root: Path = DEFAULT_OUTPUT_ROOT,
    results_path: Path | None = DEFAULT_RESULTS_PATH,
    election_id: str = ELECTION_ID,
    rows_normalizer: Any = None,
    candidacy_finisher: Any = None,
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
    stats: list[dict[str, Any]] = []
    for candidate_id in target_ids:
        _, candidate_stats = parse_anketa_sample(
            candidate_id=candidate_id,
            samples_root=samples_root,
            output_root=output_root,
            results_path=results_path,
            results_lookup=results_lookup,
            ranking_lookup=ranking_lookup,
            election_id=election_id,
            rows_normalizer=rows_normalizer,
            candidacy_finisher=candidacy_finisher,
        )
        stats.append(candidate_stats)
    return stats
