"""The education level, as a comparable ordinal (issue #88).

VRK never published a level taxonomy: the corpus holds 123 distinct level
surface forms over ~114,000 mentions, four storage shapes, and a headline
share that flips direction depending on the denominator. Three facts drive
everything here, all measured over the full corpus:

* **"Aukštasis" without a qualifier is 39 % of all level tokens and is a
  property of the form, not the candidate** — every election from 1996 to
  2007-vasario offers the bare form as its *only* higher-education option.
  So the bare form is a first-class tier (`aukstasis-nedetalizuotas`)
  between `nebaigtas-aukstasis` and the qualified tiers, and a consumer who
  wants an era-comparable answer reads the `aukstasis` boolean instead.
* **The level lives in three places.** `issilavinimas.irasai[]` items
  (49 elections), `issilavinimas.aprasas` (`2000-kovo-19` and
  `2002-gruodzio-22`, 19,861 records, whose form asks the level as one
  answer), and — for 935 records with no level at all — the adjacent
  degree fields. The resolver reads them all.
* **Absence has more than one meaning.** `2019-kovo-3` literally prints
  `Išsilavinimas: Nenurodė` (a decline, retained in `rawData`);
  `2000-seimo` publishes institution/specialty/year but no level for
  anyone (its true higher-education share is ~77 %, and a naive read
  scores it 0 %); the 2015/2011/2007 pages print no education row at all
  for a candidate who left it blank. Collapsing those into one `null` is
  how a 2020-income-style artefact hides (issue #85).

Everything is derived: the stored `normalized` values are never rewritten,
and the raw surface form is always still in the record.
"""

from __future__ import annotations

import re
import unicodedata
from typing import Any

# ---------------------------------------------------------------------------
# The ordinal
# ---------------------------------------------------------------------------

#: The thirteen tiers, ascending. Every term is taken from the measured data;
#: the order follows the Lithuanian education ladder. `nebaigtas-*` tiers rank
#: below the level they did not finish. `aukstasis-nedetalizuotas` is the bare
#: "Aukštasis" that 1996–2007 forms offered as their only higher option — it is
#: deliberately *not* collapsed into either the universitetinis or the
#: neuniversitetinis tier, because the page never said which it was.
LEVELS = (
    "pradinis",
    "pagrindinis",
    "nebaigtas-vidurinis",
    "vidurinis",
    "profesinis-vidurinis",
    "aukstesnysis",
    "nebaigtas-aukstasis",
    "aukstasis-nedetalizuotas",
    "aukstasis-neuniversitetinis",
    "aukstasis-universitetinis",
    "aukstasis-bakalauras",
    "aukstasis-magistras",
    "doktorantura",
)

#: rank, 1-based; `aukstasis` (the coarse, era-comparable boolean) is rank >=
#: this one's.
RANK = {level: index + 1 for index, level in enumerate(LEVELS)}
AUKSTASIS_RANK = RANK["aukstasis-nedetalizuotas"]


def _fold(text: str) -> str:
    """Lower-cased, diacritics stripped, whitespace collapsed."""
    decomposed = unicodedata.normalize("NFD", str(text).casefold())
    stripped = "".join(ch for ch in decomposed if unicodedata.category(ch) != "Mn")
    return " ".join(stripped.split())


#: The mapping rules, first match wins, applied to the folded form. Ordering
#: is load-bearing: "Nebaigtas spec. vidurinis" must hit the nebaigtas rule
#: before the spec-vidurinis one, "Aukštesnysis neuniversitetinis" is an
#: aukštesnysis, "Magistrantūra" is a completed bachelor in master's studies
#: (not a master), and "Profesinis bakalauras" is the kolegija degree, so it
#: outranks the plain bakalauras rule. Verified against every distinct surface
#: form in the corpus by tests/test_education_taxonomy.py; the measured
#: coverage is ~99.4 % of level mentions, and the unmapped tail is dominated
#: by non-answers ("Nereglamentuojamas", "Studijuoju", "Universitetas").
_RULES: tuple[tuple[re.Pattern[str], str], ...] = tuple(
    (re.compile(pattern), level)
    for pattern, level in (
        (r"nebaigt\w*[\s.]*(special\w*|spec\.?)?\s*vidurin", "nebaigtas-vidurinis"),
        (r"\b1[01] klas", "nebaigtas-vidurinis"),
        (r"habilituot|daktar|doktorant|aspirantur|disertacij", "doktorantura"),
        (r"magistrant|magistratur", "aukstasis-bakalauras"),
        (r"magistr", "aukstasis-magistras"),
        (r"profesin\w*\s+bakalaur", "aukstasis-neuniversitetinis"),
        (r"bakalaur", "aukstasis-bakalauras"),
        (r"aukstesn", "aukstesnysis"),
        (r"(nebaigt\w*|numatom\w*)[^a-z]+aukstas|aukstas\w*[^a-z]+(nebaigt|numatom)", "nebaigtas-aukstasis"),
        (r"neuniversitetin", "aukstasis-neuniversitetinis"),
        (r"universitetin", "aukstasis-universitetinis"),
        (r"aukstas", "aukstasis-nedetalizuotas"),
        (r"(special\w*|spec\.?)\s*(vidurin|technin)", "profesinis-vidurinis"),
        (r"vidurin\w*\W+technin|technin\w*\s+vidurin", "profesinis-vidurinis"),
        (r"profesin", "profesinis-vidurinis"),
        (r"^technin", "profesinis-vidurinis"),
        (r"vidurin", "vidurinis"),
        (r"pagrindin|astuon\w* klas|devynmet|\b[89] klas", "pagrindinis"),
        (r"pradin", "pradinis"),
    )
)

_UNFINISHED = re.compile(r"nebaigt|numatom")


def level_of(text: Any) -> str | None:
    """The tier one surface form states, or None for the unmappable tail."""
    if not isinstance(text, str) or not text.strip():
        return None
    folded = _fold(text)
    for pattern, level in _RULES:
        if pattern.search(folded):
            return level
    return None


def is_unfinished(text: Any) -> bool:
    """Whether the form says the level was not completed ("Nebaigtas ...",
    "(numatoma)"). Orthogonal to the tier: "Nebaigtas aukštasis" is both the
    `nebaigtas-aukstasis` tier and unfinished."""
    return isinstance(text, str) and bool(_UNFINISHED.search(_fold(text)))


# ---------------------------------------------------------------------------
# Academic degree (mokslo laipsnis)
# ---------------------------------------------------------------------------

#: Ascending. `nera` is an *answered* "I have none" ("Neturiu", "Nėra"), which
#: is not the same as the field being empty.
DEGREES = ("nera", "bakalauras", "magistras", "daktaras", "habilituotas-daktaras")
DEGREE_RANK = {degree: index for index, degree in enumerate(DEGREES)}

_DEGREE_RULES: tuple[tuple[re.Pattern[str], str], ...] = tuple(
    (re.compile(pattern), degree)
    for pattern, degree in (
        (r"habilituot", "habilituotas-daktaras"),
        (r"daktar", "daktaras"),
        (r"magistr", "magistras"),
        (r"bakalaur", "bakalauras"),
        (r"^(neturiu|neturi|nera|-|neturime)[\s.,!]*$", "nera"),
    )
)


def degree_of(text: Any) -> str | None:
    """The academic degree one `mokslo-laipsnis`/`pedagoginis-vardas` value
    states, or None.

    The fields are free text and hold four different things at once — degrees,
    pedagogical titles (Docentas, Profesorius), school-teacher categories
    (Vyr. mokytoja) and prose. Only degree words are read; a title is not a
    degree and maps to None. In the eight elections whose page fused the two
    questions into one row ("Jei turite, nurodykite pedagoginį vardą, mokslo
    laipsnį"), the answer landed under `pedagoginis-vardas` alone — the degree
    was never published separately (verified against the retained HTML), so
    reading degree words out of that field is the only recovery there is.
    """
    if not isinstance(text, str) or not text.strip():
        return None
    folded = _fold(text)
    for pattern, degree in _DEGREE_RULES:
        if pattern.search(folded):
            return degree
    return None


# ---------------------------------------------------------------------------
# The record-level resolver
# ---------------------------------------------------------------------------

#: What the level's absence means, per record.
STATUS_STATED = "nurodyta"  # a level answer was published (lygis is null for the ~0.6 % the taxonomy does not map)
STATUS_DECLINED = "nenurode"  # the page prints the explicit decline
STATUS_NOT_PUBLISHED = "neskelbta"  # the election publishes no level for anyone
STATUS_NOT_ANSWERED = "neatsakyta"  # the form asks; this page shows no answer

#: The elections that publish no education *level* on any record, so a 0 %
#: there is an artefact of the page, not of the candidates. `2000-seimo`
#: publishes institution 100 % / specialty 93 % / year 97 % and zero levels
#: (~77 % of its candidates name a university); the two presidential
#: elections publish no questionnaire at all.
LEVEL_NOT_PUBLISHED = frozenset(
    {"2000-seimo", "2002-prezidento", "2004-prezidento"}
)

#: The one election that spells the institution key from its own column
#: heading ("Mokyklos įstaigos pavadinimas"): 360 of `2004-ep`'s 361 education
#: entries. Everywhere else it is `mokymo-istaigos-pavadinimas`.
INSTITUTION_KEYS = ("mokymo-istaigos-pavadinimas", "mokyklos-istaigos-pavadinimas")

_EDUCATION_PROMPT = re.compile(r"issilavinim")


def _education_block(record: dict[str, Any]) -> dict[str, Any] | None:
    """`issilavinimas` from whichever section this era stores it in."""
    normalized = record.get("normalized") or {}
    for section in ("anketa", "biografija"):
        data = normalized.get(section)
        if isinstance(data, dict) and isinstance(data.get("issilavinimas"), dict):
            return data["issilavinimas"]
    return None


def _degree_fields(record: dict[str, Any]) -> list[Any]:
    normalized = record.get("normalized") or {}
    values = []
    for section in ("anketa", "biografija"):
        data = normalized.get(section)
        if isinstance(data, dict):
            values.extend((data.get("mokslo-laipsnis"), data.get("pedagoginis-vardas")))
    return values


def _declined_on_page(record: dict[str, Any]) -> bool:
    """Whether the page itself printed the decline.

    The 2016-era pages keep the questionnaire as `rawData.anketa.rows` and the
    2020-era as `rawData.biografija.rows`, and both print
    `Išsilavinimas: Nenurodė` for a candidate who declined — 5,091 of 5,091
    no-level records in `2019-kovo-3` and 2,304 of 2,304 in `2023-kovo-5`.
    The earlier eras print no education row at all for a blank answer
    (measured against the retained HTML: 397–400 of 400 sampled no-level
    records per election), so this returns False there and the status stays
    `neatsakyta`.
    """
    raw = record.get("rawData") or {}
    for section in ("anketa", "biografija"):
        data = raw.get(section)
        rows = data.get("rows") if isinstance(data, dict) else None
        if not isinstance(rows, list):
            continue
        for row in rows:
            if not isinstance(row, dict):
                continue
            prompt = row.get("prompt") or row.get("label") or ""
            if not _EDUCATION_PROMPT.search(_fold(prompt)):
                continue
            answer = str(row.get("answer") or "").strip()
            if answer == "Nenurodė":
                return True
    return False


def issilavinimas(record: dict[str, Any], election_id: str | None = None) -> dict[str, Any]:
    """One education concept for one corpus record.

        {"busena":   "nurodyta" | "nenurode" | "neskelbta" | "neatsakyta",
         "lygis":    "aukstasis-universitetinis" | ... | None,
         "rangas":   10 | ... | None,
         "aukstasis": True | False | None,
         "nebaigtas": True | False | None,
         "laipsnis": "daktaras" | ... | None,
         "irasai":   [...]}

    `lygis` is the highest tier stated by any of the record's level values —
    `irasai[].issilavinimas` plus the `aprasas` the 2000/2002 municipal form
    answers with. `laipsnis` reads the degree fields independently, so a
    record with no level can still carry a doctorate (935 do). `irasai` is the
    stored entry list with the `2004-ep` institution-key spelling folded into
    the corpus-wide one.
    """
    election_id = election_id or record.get("electionId")
    block = _education_block(record) or {}

    candidates: list[str] = []
    aprasas = block.get("aprasas")
    if isinstance(aprasas, str) and aprasas.strip():
        candidates.append(aprasas)
    entries = []
    for entry in block.get("irasai") or []:
        if not isinstance(entry, dict):
            continue
        level_text = entry.get("issilavinimas")
        if isinstance(level_text, str) and level_text.strip():
            candidates.append(level_text)
        institution = next(
            (entry[key] for key in INSTITUTION_KEYS if entry.get(key)), None
        )
        entries.append(
            {
                "issilavinimas": level_text,
                "mokymo-istaigos-pavadinimas": institution,
                "specialybe": entry.get("specialybe"),
                "baigimo-metai": entry.get("baigimo-metai"),
            }
        )

    best: tuple[int, str, str] | None = None  # (rank, tier, source text)
    for text in candidates:
        tier = level_of(text)
        if tier is not None and (best is None or RANK[tier] > best[0]):
            best = (RANK[tier], tier, text)

    degree: str | None = None
    for value in _degree_fields(record):
        found = degree_of(value)
        if found is not None and (
            degree is None or DEGREE_RANK[found] > DEGREE_RANK[degree]
        ):
            degree = found

    if best is not None:
        rank, tier, source = best
        return {
            "busena": STATUS_STATED,
            "lygis": tier,
            "rangas": rank,
            "aukstasis": rank >= AUKSTASIS_RANK,
            "nebaigtas": is_unfinished(source),
            "laipsnis": degree,
            "irasai": entries,
        }

    if candidates:
        # Answered, but with a form the taxonomy does not map
        # ("Nereglamentuojamas", "Studijuoju", an institution name). The
        # answer is real; only the tier is unknown.
        return {
            "busena": STATUS_STATED,
            "lygis": None,
            "rangas": None,
            "aukstasis": None,
            "nebaigtas": None,
            "laipsnis": degree,
            "irasai": entries,
        }

    if election_id in LEVEL_NOT_PUBLISHED:
        status = STATUS_NOT_PUBLISHED
    elif _declined_on_page(record):
        status = STATUS_DECLINED
    else:
        status = STATUS_NOT_ANSWERED
    return {
        "busena": status,
        "lygis": None,
        "rangas": None,
        "aukstasis": None,
        "nebaigtas": None,
        "laipsnis": degree,
        "irasai": entries,
    }
