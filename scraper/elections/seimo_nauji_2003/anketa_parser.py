"""Candidate pages of the 2003-06-15 new Seimas election.

The 2004 static site one generation early. The questionnaire is the same
document the 2004 Seimas pages print — one ``<tr class="r1|r2">`` per
question in ``N. Prompt: <b>answer</b>`` form, a list answer as several
``<b>``, record tables at Q12 and Q15, the unnumbered degree/title and
spouse pairs trailing their question — so ``ep_2004``'s row reader and
``seimo_2004``'s question mapping do the work here. Four page-level
deltas make the readers this module's own (each measured across all 27
pages, not inferred):

1. **The card is a row of the question table**, first, classed ``r2``
   like any other. On the 2004 pages it is a table of its own and its
   row is unclassed, so the era's row walk would read "Apygarda:" and
   "Iškėlė:" as two answered questions. The card row is read as the
   profile and skipped by the question walk.
2. **Birth date is Q5, not Q3** ("5. Gimimo data: <b>1957 05 04</b>").
   Everything else in ``normalize_seimo_2004_anketa_rows`` matches
   as-is, so this module overrides that one key.
3. **Q9.1-9.3 carry a footnote marker between number and prompt** —
   ``9.1<sup>*</sup> Ar ne pagal…``, footnoted at the page bottom as
   "duomenys iš kandidato į Seimo narius anketos priedo". The ``<sup>``
   splits the text run, so the question number never matches; the
   markers (81 of them, three per page) are dropped and the run
   rejoined before the row reader sees the cell.
4. **The Q12/Q15 record tables print no header row** — all 27 pages,
   every table: row one is data (level, school, specialty, year at
   Q12; institution-and-role, term at Q15). The era reader would eat
   the first record as column names and mis-key the rest, which on the
   21 single-row education tables loses the record outright, so this
   module reads them positionally under the 2004 pages' own column
   names.

The other two pages:

- ``kand_biog_l-id=<ID>.htm`` — the free-text autobiography, one
  blockquote.
- ``kand_pajam_l-id=<ID>.htm`` — the declaration extract, and **the
  2002 municipal form, not the 2004 one**: numbered summary items in
  litas, matched on wording by ``savivaldybiu_2002``'s key map. Two
  forms are printed — "Lietuvos Respublikos gyventojo turto ir pajamų
  deklaracija" on 18 pages (items 3-12, joint bank accounts as 9) and
  the family form, "šeimos turto ir pajamų deklaracija", on 9 (items
  3-11, no joint-accounts item, every prompt in the plural). Both are
  a table of ``tr.r1|r2`` item rows rather than 2002's one cell of
  ``<br>``-separated lines, and 2003 misspells two prompts
  ("negražintų", "paskolintų (nesugražintų)" — the 2002 pages spell
  both correctly, checked on 25 of them), so the reader is this
  module's and the key map is 2002's with those spellings added.

Nobody was elected: all four constituencies failed on turnout, so
``kandidatavimas.isrinktas`` is a known ``false`` on every record and
``turai`` carries the one round's votes (``results.py``).

The photo is linked, never mined. Its filename is the candidate's
asmens kodas (``…/kandidatai/ 45705040120_17.jpg`` for a candidate
whose Q5 reads ``1957 05 04`` — true on all 27), so the record's ids
and birth dates come from the ``kand_anketa_l-id=`` value and the
questionnaire, never from the URL. The ``src`` has a stray space before
the filename, which has to go or the URL 404s.
"""
from __future__ import annotations

import errno
import json
from pathlib import Path
import re
from typing import Any

from bs4 import BeautifulSoup, NavigableString, Tag

from scraper.elections.ep_2004.anketa_parser import (
    _card_label,
    _parse_anketa_row_cell,
)
from scraper.elections.savivaldybiu_2002.anketa_parser import (
    DEKLARACIJA_RANGE_ITEMS as _SAV_2002_RANGE_ITEMS,
    DEKLARACIJA_SINGLE_ITEMS as _SAV_2002_SINGLE_ITEMS,
    _parse_deklaracija_amount,
    normalize_deklaracija,
)
from scraper.elections.seimo_2004.anketa_parser import normalize_seimo_2004_anketa_rows
from scraper.elections.seimo_2016.anketa_parser import (
    _find_row_by_question_number,
    _normalize_biografija_data,
    _normalize_missing_values,
    _normalize_profile_data,
    _order_dict_keys,
    _row_answer_text,
    _tag_text,
    normalize_space,
)
from scraper.elections.seimo_birzu_zarasu_ukmerges_2013.anketa_parser import build_candidacy
from scraper.elections.seimo_nauji_2003.candidate_samples import SUBPAGE_LINK_PATTERN
from scraper.elections.seimo_nauji_2003.results import load_rounds
from scraper.elections.seimo_nauji_2003.sitemap import ELECTION_ID, resolve_candidate_url
from scraper.elections.seimo_zirmunu_2015.anketa_parser import (
    _apply_results,
    _normalize_answer_value,
    load_results,
)
from scraper.shared.anomalies import build_anomaly_event
from scraper.shared.files import write_candidate_record
from scraper.shared.savivaldybiu_archive_1997 import normalize_birth_date

DEFAULT_SAMPLES_ROOT = Path(f"samples/html/{ELECTION_ID}")
DEFAULT_OUTPUT_ROOT = Path(f"data/{ELECTION_ID}")
# Elected status and the round's votes, joined in from VRK's results tree
# when the file exists.
DEFAULT_RESULTS_PATH = Path(f"sitemaps/{ELECTION_ID}.results.json")

# The Q12 and Q15 tables print no column names; these are the names the
# 2004 pages give the same columns, in the same order.
RECORD_TABLE_COLUMNS = {
    4: ["issilavinimas", "mokyklos-istaigos-pavadinimas", "specialybe", "baigimo-metai"],
    2: ["institucijos-pavadinimas-pareigos", "laikotarpis"],
}

# 2002's key map plus the two items 2003 misspells and the family form's
# plural wording for the loans item, which drops "ir iki metų pabaigos".
DEKLARACIJA_SINGLE_ITEMS = _SAV_2002_SINGLE_ITEMS + (
    ("negražintų) paskolų", "gautos-paskolos"),
    ("paskolintų (nesugražintų) ir dovanotų", "pasiskolintos-ir-dovanotos-lesos"),
)
DEKLARACIJA_RANGE_ITEMS = _SAV_2002_RANGE_ITEMS

__all__ = [
    "normalize_seimo_2003_anketa_rows",
    "parse_anketa_html",
    "parse_anketa_sample",
    "parse_anketa_samples",
    "parse_biografija_html",
    "parse_deklaracija_html",
]


# ---------------------------------------------------------------------------
# Page furniture
# ---------------------------------------------------------------------------


def _content_div(soup: BeautifulSoup) -> Tag | None:
    """The page's own content block. Every page of this tree is a stack of
    ``div.vrk-elections-content`` — masthead, content, footer — and the
    content one is the block carrying the page's ``<h1>``."""
    for div in soup.find_all("div", class_="vrk-elections-content"):
        if div.find("h1") is not None:
            return div
    return None


def _photo_src(value: str) -> str:
    # "…/kandidatai/ 45705040120_17.jpg" — the template writes a space
    # before the filename, and the URL 404s until it is gone.
    return normalize_space(value).replace("/ ", "/")


def _question_table(content: Tag | None) -> Tag | None:
    if content is None:
        return None
    for table in content.find_all("table"):
        body = table.find("tbody") or table
        if any(tr.get("class") for tr in body.find_all("tr", recursive=False)):
            return table
    return None


def _table_rows(table: Tag | None) -> list[Tag]:
    if table is None:
        return []
    body = table.find("tbody") or table
    return list(body.find_all("tr", recursive=False))


def _card_row(table: Tag | None) -> Tag | None:
    """The card is the table's first row — the one holding the photo."""
    for tr in _table_rows(table):
        if tr.find("img") is not None:
            return tr
    return None


# ---------------------------------------------------------------------------
# Profile card
# ---------------------------------------------------------------------------


def _parse_profile_html(soup: BeautifulSoup) -> tuple[dict[str, Any], Tag | None]:
    """The card: photo, "Apygarda:" linking the constituency, "Iškėlė:"
    linking the party, then the two sub-page links."""
    profile: dict[str, Any] = {
        "candidateDisplayName": "",
        "electedNote": "",
        "photoSrc": "",
        "fields": [],
    }
    content = _content_div(soup)
    if content is None:
        return profile, None
    # The <h1> is the page title ("Kandidato į Seimo narius anketa"), the
    # <h2> the candidate's name.
    heading = content.find("h2")
    if heading is not None:
        profile["candidateDisplayName"] = _tag_text(heading)

    card = _card_row(_question_table(content))
    cell = card.find("td") if card is not None else None
    if cell is None:
        return profile, None

    img = cell.find("img")
    if img is not None:
        src = _photo_src(img.get("src", ""))
        if src:
            profile["photoSrc"] = resolve_candidate_url(src)

    fields: list[dict[str, Any]] = []
    pending_label = ""
    for node in cell.children:
        if isinstance(node, NavigableString):
            text = normalize_space(str(node))
            if text:
                pending_label = f"{pending_label} {text}".strip() if pending_label else text
            continue
        if not isinstance(node, Tag):
            continue
        if node.name == "b":
            urls = [
                resolve_candidate_url(normalize_space(anchor["href"]))
                for anchor in node.find_all("a", href=True)
                if normalize_space(anchor["href"]) not in ("", "#")
            ]
            fields.append(
                {"key": _card_label(pending_label), "displayValue": _tag_text(node), "urls": urls}
            )
            pending_label = ""
            continue
        if node.name == "a":
            # The biography and declaration links are the page-set, saved
            # as sub-pages; they are not facts of the card.
            if not SUBPAGE_LINK_PATTERN.search(normalize_space(node.get("href", ""))):
                fields.append(
                    {
                        "key": _tag_text(node),
                        "displayValue": "",
                        "urls": [resolve_candidate_url(normalize_space(node["href"]))]
                        if node.get("href")
                        else [],
                    }
                )
            pending_label = ""
    profile["fields"] = fields
    return profile, cell


# ---------------------------------------------------------------------------
# Questionnaire rows
# ---------------------------------------------------------------------------


def _strip_footnote_markers(cell: Tag) -> Tag:
    """Drop the ``<sup>*</sup>`` between a Q9.x number and its prompt and
    rejoin the text run, so the number matches as it does on every other
    page of the family."""
    for sup in cell.find_all("sup"):
        sup.extract()
    cell.smooth()
    return cell


def _parse_record_table(table: Tag) -> list[dict[str, str]]:
    """A Q12/Q15 record table, every row a record.

    The 2004 pages name the columns in a first bold row; the 2003 pages
    print none at all, so the columns are keyed positionally under the
    2004 names and anything wider falls back to ``stulpelis-N``.
    """
    records: list[dict[str, str]] = []
    for tr in table.find_all("tr"):
        cells = tr.find_all("td")
        if not cells:
            continue
        values = [_tag_text(cell) for cell in cells]
        if not any(values):
            continue
        columns = RECORD_TABLE_COLUMNS.get(len(cells), [])
        records.append(
            {
                columns[index] if index < len(columns) else f"stulpelis-{index + 1}": value
                for index, value in enumerate(values)
            }
        )
    return records


def _parse_anketa_rows(content: Tag | None) -> dict[str, Any]:
    table = _question_table(content)
    card = _card_row(table)
    rows: list[dict[str, Any]] = []
    for tr in _table_rows(table):
        if tr is card or not tr.get("class"):
            continue
        cell = tr.find("td", recursive=False)
        if cell is None:
            continue
        rows.extend(
            _parse_anketa_row_cell(
                _strip_footnote_markers(cell), record_table_reader=_parse_record_table
            )
        )
    for index, row in enumerate(rows, start=1):
        row["rowIndex"] = index
    return {
        "rows": rows,
        "stats": {
            "rowCount": len(rows),
            "answeredRowCount": sum(1 for row in rows if row.get("answer")),
        },
    }


def normalize_seimo_2003_anketa_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """The 2004 Seimas mapping — the same Seimo rinkimų įstatymo question
    set, down to the Q8.3/Q8.4 pair and the 98 str. questions at Q9.1-9.3
    — with the one number this form moves: the birth date is Q5 here and
    Q3 in 2004."""
    normalized = normalize_seimo_2004_anketa_rows(rows)
    birth_date = _normalize_answer_value(
        _row_answer_text(_find_row_by_question_number(rows, "5"))
    )
    normalized["gimimo-data"] = normalize_birth_date(birth_date) if birth_date else None
    return normalized


def parse_anketa_html(html: str) -> dict[str, Any]:
    soup = BeautifulSoup(html, "lxml")
    profile, card = _parse_profile_html(soup)
    content = _content_div(soup)
    anketa = _parse_anketa_rows(content)
    anketa["normalized"] = normalize_seimo_2003_anketa_rows(anketa["rows"])
    return {
        "profile": profile,
        "anketa": anketa,
        "diagnostics": {
            "profileCardFound": card is not None,
            "contentDivFound": content is not None,
            "anketaTableFound": bool(anketa["rows"]),
            "anketaPlaceholder": False,
            "placeholderText": "",
        },
    }


# ---------------------------------------------------------------------------
# Sub-pages
# ---------------------------------------------------------------------------


def parse_biografija_html(html: str) -> dict[str, Any]:
    soup = BeautifulSoup(html, "lxml")
    body = soup.find("blockquote")
    if body is None:
        return {"text": "", "html": ""}
    # <br /> separates the lines; get_text's separator keeps them apart.
    return {
        "text": normalize_space(body.get_text(" ", strip=True)),
        "html": str(body),
    }


def _declaration_table(soup: BeautifulSoup) -> Tag | None:
    for table in soup.find_all("table"):
        if table.find("tr", class_=["r1", "r2"]) is not None:
            return table
    return None


def parse_deklaracija_html(html: str) -> dict[str, Any]:
    """The extract's items, in page order, in ``savivaldybiu_2002``'s
    shape: a prompt, its printed figure, and for the two-figure items the
    start/end sub-lines the nested table prints as ``<li>``.

    The form and the issuing tax office are the page's own facts and are
    kept beside the items.
    """
    soup = BeautifulSoup(html, "lxml")
    heading = soup.find("h1")
    text = normalize_space(soup.get_text(" ", strip=True))
    issuer, issued = _issuer_and_date(text)
    payload: dict[str, Any] = {
        "forma": _tag_text(heading) if heading is not None else "",
        "isdave": issuer,
        "isdavimoData": issued,
        "items": [],
        "found": False,
    }
    table = _declaration_table(soup)
    if table is None:
        return payload
    payload["found"] = True
    for tr in table.find_all("tr"):
        # The two-figure items nest a table of their own; its rows are read
        # from the item's cell, not walked as items.
        if tr.find_parent("table") is not table:
            continue
        cell = tr.find("td")
        if cell is None:
            continue
        item = _declaration_item(cell)
        if item is not None:
            payload["items"].append(item)
    return payload


ISSUER_PATTERN = re.compile(
    r"Pagrindinių duomenų išrašą išdavė\s*(?P<issuer>.+?)\.\s*Išdavimo data\s*(?P<date>[\d ]+)"
)


def _issuer_and_date(text: str) -> tuple[str | None, str | None]:
    match = ISSUER_PATTERN.search(text)
    if match is None:
        return None, None
    return (
        normalize_space(match.group("issuer")) or None,
        normalize_space(match.group("date")) or None,
    )


def _declaration_item(cell: Tag) -> dict[str, Any] | None:
    """One item row: the prompt is the text before the value, the value the
    first ``<b>``, and a nested table's ``<li>`` lines the two dates."""
    prompt_parts: list[str] = []
    value: str | None = None
    periods: dict[str, str | None] = {}
    for node in cell.children:
        if isinstance(node, NavigableString):
            text = normalize_space(str(node))
            if text and value is None:
                prompt_parts.append(text)
            continue
        if not isinstance(node, Tag):
            continue
        if node.name == "b":
            if value is None:
                value = _tag_text(node)
            continue
        if node.name == "table":
            for entry in node.find_all("li"):
                label = normalize_space(entry.get_text(" ", strip=True)).lower()
                bold = entry.find("b")
                period = "pradzioje" if "pradžioje" in label else "pabaigoje" if "pabaigoje" in label else None
                if period:
                    periods[period] = _tag_text(bold) if bold is not None else None
            continue
        if value is None:
            text = _tag_text(node)
            if text:
                prompt_parts.append(text)
    prompt = normalize_space(" ".join(prompt_parts))
    if not prompt:
        return None
    item: dict[str, Any] = {"prompt": prompt, "value": value}
    if periods:
        item["periods"] = periods
    return item


def _normalize_deklaracija_data(payload: dict[str, Any]) -> dict[str, Any]:
    declaration, unknown = normalize_deklaracija(
        payload, single_items=DEKLARACIJA_SINGLE_ITEMS, range_items=DEKLARACIJA_RANGE_ITEMS
    )
    # The form the page prints and who issued the extract are facts of this
    # election's declaration, not of the 2002 key map. `israsa-isdave` is
    # the 2004 key for the issuing tax office; the date is the page's own
    # "Išdavimo data", not 2004's "Gavimo data", so it keeps its own key.
    declaration["forma"] = normalize_space(str(payload.get("forma") or "")) or None
    declaration["israsa-isdave"] = payload.get("isdave")
    declaration["isdavimo-data"] = normalize_birth_date(payload["isdavimoData"]) if payload.get(
        "isdavimoData"
    ) else None
    if unknown:
        declaration["nezinomos-eilutes"] = unknown
    return declaration


SUBPAGES: dict[str, tuple[str, Any]] = {
    "biografija": ("biografija.html", parse_biografija_html),
    "turtoIrPajamuDeklaracijos": ("turto-ir-pajamu-deklaracijos.html", parse_deklaracija_html),
}


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

    parsed = parse_anketa_html(anketa_path.read_text(encoding="utf-8"))
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
                election_id=ELECTION_ID,
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
                election_id=ELECTION_ID,
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
                    election_id=ELECTION_ID,
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
            normalized["turto-ir-pajamu-deklaracijos"] = _normalize_deklaracija_data(data)

    candidate_name = (
        str(candidate_meta.get("candidateName", "")).strip() or parsed["profile"]["candidateDisplayName"]
    )
    output_payload: dict[str, Any] = {
        "electionId": ELECTION_ID,
        "candidateId": candidate_id,
        "candidateName": candidate_name,
        "kandidatavimas": build_candidacy(candidate_meta),
    }
    if results_lookup is not None:
        _apply_results(output_payload, candidate_meta, source_url, results_lookup)
    vrk_id = str(candidate_meta.get("vrkCandidateId", "") or "").strip()
    if rounds_lookup and vrk_id in rounds_lookup:
        output_payload["kandidatavimas"]["turai"] = rounds_lookup[vrk_id]
    output_payload |= {
        "source": {"candidateSourceUrl": source_url},
        "rawData": _order_dict_keys(
            raw_data, ["profile", "anketa", "biografija", "turtoIrPajamuDeklaracijos"]
        ),
        "normalized": _normalize_missing_values(
            _order_dict_keys(
                normalized, ["profilis", "anketa", "biografija", "turto-ir-pajamu-deklaracijos"]
            )
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
