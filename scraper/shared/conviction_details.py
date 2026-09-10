"""The conviction-detail block, for every era that publishes one.

Since the 2016 Seimas election VRK has asked a candidate who answers "yes" to
the conviction question to itemize each conviction, and the block has carried
the same four facts throughout: the date of the judgment, the state that issued
it, the court, and the offence. What changes between eras is the question the
block hangs off and how the page renders it.

| era                                   | question | rendering |
|---|---|---|
| 2016/2017/2018/2019/2020 Seimas, 2019 EP | 9.2   | one table row per conviction, columns named after the sub-questions ("9.2.1. Apkaltinamojo nuosprendžio (sprendimo) data") |
| 2019/2021 municipal                   | 9.1      | the same table, sub-questions renumbered |
| Rinkimų kodeksas (2023 on)            | 13.4     | one "Label - value" line per field, with a nested table of offences |

Those differences are data -- a question number and, where the columns are
named after sub-questions, the four names to map them to -- so they are
arguments here rather than a private copy per module. Four such copies in three
variants existed before issue #86, each written for the election that needed
one and never copied back to its siblings, and the elections with no copy paid
for it: 2016-seimo, 2020-seimo, 2019-ep and 2019-rugsejo-8-seimo answered "yes,
convicted" for 87 candidates and published nothing about what for, while the
page's own table sat unread in `rawData.anketa.rows`.

Every era emits the same normalized shape, `anketa.teistumo-detales.irasai`:
one entry per conviction, and an empty list when the candidate declared none.
"""

from __future__ import annotations

import re
import unicodedata
from typing import Any

from scraper.shared.files import slugify
from scraper.shared.values import clean_value

# The four facts the block has carried in every era, in the order the pages
# print them. The 2019/2021 municipal and 2016-2020 Seimas tables give one
# column to each; the Rinkimų kodekso pages split the same facts between three
# flat rows and a nested offence table (see `conviction_entries`).
CONVICTION_FIELD_NAMES = (
    "nuosprendzio-data",
    "nuosprendzio-valstybe",
    "nuosprendzio-institucija",
    "nusikalstama-veika",
)

# The "not stated" tokens the election modules fold to null, kept identical to
# `normalize_text_value` in scraper/shared/anketa_tabs.py so a value normalized
# here matches the one the rest of the record went through.
MISSING_TEXT_VALUES = {
    "",
    "-",
    "nenurodė",
    "nenurode",
}

# A Rinkimų kodekso detail line ("Kaltės forma - Tyčia") separates its label
# from its value with a dash: a plain hyphen on the 2023 pages, an en dash on
# the 2024 ones. Measured over all 931 distinct such lines in the corpus, this
# pattern splits each era exactly as that era's own parser did.
DASH_FIELD_SEPARATOR = re.compile(r"\s+[-–—](?:\s+|$)")


def normalize_space(value: str) -> str:
    return " ".join(value.split())


def normalize_text_value(value: Any) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        return str(value)

    # As in every election module: fold mixed unicode normalization forms to
    # NFC so an NFD "ė" string-matches its NFC form, then apply the value
    # rules every era shares (scraper/shared/values.py). rawData keeps the
    # original bytes.
    normalized = clean_value(normalize_space(unicodedata.normalize("NFC", value)))
    if normalized is None or normalized.lower() in MISSING_TEXT_VALUES:
        return None
    return normalized


def source_key(label: str) -> str:
    return slugify(normalize_space(label).rstrip(":"))


def conviction_field_keys(question_number: str) -> dict[str, str]:
    """The detail table's four column names, keyed by the sub-question slug.

    VRK names each column after the sub-question that asks for it -- "9.2.1.
    Apkaltinamojo nuosprendžio (sprendimo) data" under Q9.2, "9.1.1 ..." under
    Q9.1 -- so the whole era difference is the question number, and the map is
    that number plus 1-4.
    """
    prefix = question_number.replace(".", "-")
    return {
        f"{prefix}-{index}": name
        for index, name in enumerate(CONVICTION_FIELD_NAMES, start=1)
    }


def _find_question_row(
    rows: list[dict[str, Any]], question_number: str
) -> tuple[int, dict[str, Any]] | None:
    for index, row in enumerate(rows):
        if row.get("questionNumber") == question_number:
            return index, row
    return None


def conviction_record_groups(
    rows: list[dict[str, Any]], question_number: str
) -> list[list[Any]]:
    """Every record table belonging to a question, one list per table.

    VRK renders the detail table sometimes inside its question's row and
    sometimes in a row of its own right after it, so both are collected. The
    2020 pages print the block's lead-in ("Jeigu buvote pripažintas kaltu,
    privalote nurodyti") as an unnumbered row of its own in between; an
    unnumbered row with no answer is that lead-in, not the end of the block,
    which is why it is stepped over rather than breaking the scan. The next
    numbered question ends it.
    """
    found = _find_question_row(rows, question_number)
    if found is None:
        return []
    index, row = found

    groups: list[list[Any]] = []
    answer = row.get("answer")
    if isinstance(answer, list) and answer:
        groups.append(answer)

    for next_row in rows[index + 1:]:
        if next_row.get("questionNumber"):
            break
        next_answer = next_row.get("answer")
        if isinstance(next_answer, list):
            groups.append(next_answer)
        elif next_answer:
            # Free text of its own under the question, not a detail table.
            break

    return groups


def _dash_field_record(values: list[Any]) -> dict[str, Any]:
    # The Rinkimų kodekso block renders one "Label - value" line per field;
    # fold the lines into a single record.
    record: dict[str, Any] = {}
    for value in values:
        if not isinstance(value, str):
            continue
        text = normalize_space(value)
        if not text:
            continue
        parts = DASH_FIELD_SEPARATOR.split(text, maxsplit=1)
        key = source_key(parts[0])
        if not key:
            continue
        record[key] = normalize_text_value(parts[1]) if len(parts) > 1 else None
    return record


def _column_record(
    row: dict[str, Any], field_keys: dict[str, str] | None
) -> dict[str, Any]:
    if field_keys is None:
        # The Rinkimų kodekso offence table names its own columns; keep them,
        # slugified, as `_normalize_table_records` does elsewhere.
        record: dict[str, Any] = {}
        for label, value in row.items():
            key = source_key(str(label))
            if not key:
                continue
            record[key] = normalize_text_value(value)
        return record

    mapped: dict[str, Any] = {}
    for label, value in row.items():
        slug = source_key(str(label))
        for prefix, name in field_keys.items():
            if slug == prefix or slug.startswith(f"{prefix}-"):
                mapped[name] = normalize_text_value(value)
                break
    if not mapped:
        return {}
    # Every entry carries all four fields in page order, so a column the
    # candidate left blank reads as null rather than as an absent key.
    return {name: mapped.get(name) for name in field_keys.values()}


def conviction_records(
    rows: list[dict[str, Any]],
    question_number: str,
    field_keys: dict[str, str] | None = None,
) -> list[dict[str, Any]]:
    """The conviction records under `question_number`, one dict per record.

    `field_keys` is `conviction_field_keys(...)` for the eras whose columns are
    named after sub-questions, and None where the table's own column names are
    kept (the Rinkimų kodekso offence table).
    """
    records: list[dict[str, Any]] = []
    for group in conviction_record_groups(rows, question_number):
        if all(isinstance(value, str) for value in group):
            record = _dash_field_record(group)
            if record:
                records.append(record)
            continue
        for row in group:
            if not isinstance(row, dict):
                continue
            record = _column_record(row, field_keys)
            if record:
                records.append(record)
    return records


def conviction_entries(
    date: str | None,
    country: str | None,
    court: str | None,
    veikos: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """The Rinkimų kodekso block as one `irasai` entry.

    Every election publishes teistumo-detales as {"irasai": [...]} with one
    entry per conviction. The Rinkimų kodekso pages carry a single conviction
    block (dates and court as flat rows, offences in a nested table), so the
    list holds one entry there -- and none when the block is empty, instead of
    a null-field skeleton. The 2016-2021 elections list one four-field record
    per conviction in the same irasai list.
    """
    if date is None and country is None and court is None and not veikos:
        return []
    return [
        {
            "nuosprendzio-data": date,
            "nuosprendzio-valstybe": country,
            "nuosprendzio-institucija": court,
            "nusikalstamos-veikos": veikos,
        }
    ]


# ---------------------------------------------------------------------------
# The derived concept
# ---------------------------------------------------------------------------

# The corpus publishes a candidate's criminal history in three shapes -- a
# structured detail table, a free-text explanation, and a bare yes/no -- over
# the 42 elections whose forms ask about it at all. `teistumas` resolves all of
# them to one answer with a typed absence, so "we never asked", "asked and
# denied", "declared, and VRK published no detail" and "declared, here it is"
# stop looking alike to a consumer counting keys.

NOT_ASKED = "neklausta"
DENIED = "ne"
DECLARED_WITHOUT_DETAIL = "deklaruota-be-detaliu"
DECLARED = "deklaruota"

DECLARATION_KEY = "ar-buvote-pripazintas-kaltu"
FREE_TEXT_KEY = "teisiniai-argumentai"
DETAILS_KEY = "teistumo-detales"

# The affirmatives of every conviction declaration, measured over all 113,073
# records. VRK words each question to suit its own paragraph and the answer
# follows the wording: the Seimas and municipal forms ask "Ar buvote
# pripažintas kaltu?" (Taip/Ne), the 2000 and 2004 static-site ones ask whether
# there is anything to declare (Yra/Nėra), the grave-crime question of that era
# asks whether there was a conviction (Buvo/Nebuvo), and the unserved-sentence
# one asks whether the candidate has one (Turiu/Neturiu/Neturi/Ne).
#
# The main question itself takes only four of these -- Taip (1,614), Yra (16),
# Ne (101,200), Nėra (2,773) -- so a consumer filtering on "Taip" alone
# under-counts its 1,630 declarers by the sixteen who answered "Yra": five in
# 2000-seimo, three in 2004-ep, eight in 2004-seimo.
AFFIRMATIVE_ANSWERS = {"taip", "yra", "buvo", "turiu"}

# The offence's name, under the two names the two eras give it: a plain string
# column in the 2016-2021 tables, a column of the nested offence record in the
# Rinkimų kodekso one.
OFFENCE_NAME_KEYS = (
    "nusikalstama-veika",
    "kesinimosi-objektas-baudziamojo-kodekso-skyriaus-ir-straipsnio-pavadinimas",
)

# The neighbouring declarations that also assert a conviction. They are not the
# same question -- the grave-crime bar of the 2000-2014 forms, the foreign
# court, the political-persecution carve-out, the unserved sentence -- so they
# do not decide `busena`, but a consumer asking "has this person declared any
# conviction" must see them. Affirmative counts corpus-wide, measured
# 2026-08-28: grave crime 25, foreign court 19, political persecution 7,
# unserved sentence 3, on 53 records in all. **20 of those answer the main
# question "Ne"**, so counting the main question alone reports 1,630 declarers
# where 1,650 records declare a conviction somewhere.
RELATED_DECLARATION_KEYS = (
    "ar-buvote-pripazintas-kaltu-del-sunkaus-nusikaltimo",
    "ar-buvote-pripazintas-kaltu-uzsienyje",
    "ar-buvote-pripazintas-kaltu-uzsienyje-del-politinio-persekiojimo",
    "ar-buvote-pripazintas-kaltu-del-politinio-persekiojimo",
    "ar-nebaigta-teismo-paskirta-bausme",
)


def _entries_of(details: Any) -> list[dict[str, Any]]:
    if not isinstance(details, dict):
        return []
    irasai = details.get("irasai")
    return [entry for entry in irasai if isinstance(entry, dict)] if isinstance(irasai, list) else []


def _offence_names(entry: dict[str, Any]) -> list[str]:
    names: list[str] = []
    for source in [entry, *(entry.get("nusikalstamos-veikos") or [])]:
        if not isinstance(source, dict):
            continue
        for key in OFFENCE_NAME_KEYS:
            value = source.get(key)
            if isinstance(value, str) and value:
                names.append(value)
    return names


def teistumas(anketa: dict[str, Any] | None) -> dict[str, Any]:
    """One conviction concept for a record's normalized `anketa`.

    Returns `busena` (one of the four constants above), the declaration
    answer verbatim, one flattened entry per conviction and the free-text
    explanation, so every era answers the same question the same way:

        {"busena": "deklaruota",
         "deklaracija": "Taip",
         "irasai": [{"data": ..., "valstybe": ..., "institucija": ...,
                     "veikos": [...], "saltinis": {...}}],
         "aprasas": None,
         "kiti-pareiskimai": {}}

    `saltinis` is the stored entry as its own era shaped it, so nothing is
    lost to the flattening. `kiti-pareiskimai` holds the neighbouring
    conviction declarations this record answered affirmatively -- a different
    question, so it does not move `busena`, but it is the difference between
    "declared no conviction" and "declared one under another paragraph".
    """
    anketa = anketa if isinstance(anketa, dict) else {}
    pareiskimai = anketa.get("pareiskimai")
    pareiskimai = pareiskimai if isinstance(pareiskimai, dict) else {}

    declaration = pareiskimai.get(DECLARATION_KEY)
    free_text = pareiskimai.get(FREE_TEXT_KEY) or None

    details = anketa.get(DETAILS_KEY)
    entries: list[dict[str, Any]] = []
    for entry in _entries_of(details):
        entries.append(
            {
                "data": entry.get("nuosprendzio-data"),
                "valstybe": entry.get("nuosprendzio-valstybe"),
                "institucija": entry.get("nuosprendzio-institucija"),
                "veikos": _offence_names(entry),
                "saltinis": entry,
            }
        )

    if not isinstance(declaration, str) or not declaration.strip():
        # The questionnaire has no conviction question at all -- the 2019
        # presidential form, the 1990s archive cards -- or left it unanswered.
        # No record in the corpus carries details without an answer; the
        # branch is here so a future one would read as declared, not as
        # never-asked.
        busena = DECLARED if entries else NOT_ASKED
    elif declaration.strip().lower() in AFFIRMATIVE_ANSWERS:
        busena = DECLARED if (entries or free_text) else DECLARED_WITHOUT_DETAIL
    else:
        busena = DENIED

    return {
        "busena": busena,
        "deklaracija": declaration if isinstance(declaration, str) else None,
        "irasai": entries,
        "aprasas": free_text,
        "kiti-pareiskimai": {
            key: pareiskimai[key]
            for key in RELATED_DECLARATION_KEYS
            if isinstance(pareiskimai.get(key), str)
            and pareiskimai[key].strip().lower() in AFFIRMATIVE_ANSWERS
        },
    }

