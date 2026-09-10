"""The value rules every era's normalizer applies to a parsed string or figure.

Each election owns its own parser, and that is deliberate — VRK's HTML differs
by election. What a *value* means does not: a trailing comma is noise in 2000
and noise in 2023, and a money column that is `int` on one record and `float`
on the next is unusable in either. Issue #101 scanned all 113,073 records for
value-shaped defects; the rules that survived that scan live here, so an era
picks them up by calling one function rather than by growing its own copy.

The four rules, and what each was measured against on 2026-08-29:

* **A trailing separator is noise** — 3,856 values across 30 elections ended in
  a stray `,` or `;` (`"Jonas, Rasa, Živilė, Jovita,"`). VRK publishes them
  that way — 1,908 of 1,909 sampled were verbatim in the retained HTML — but a
  separator with nothing after it says nothing, and it breaks any consumer that
  splits the value on it. `strip_trailing_separator`.

* **Money is a float** — `_parse_eur_amount` and its siblings used to hand back
  an `int` when the figure happened to be integral, so 225 money columns held
  both types and 4.2 million values sat in one. Whether a column is decimal is
  a property of the column, not of whether this candidate's cents were zero.
  `as_money`.

* **A figure printed with its currency is two values** —
  `privaciu-interesu-deklaracija.id001s[].sandorio-suma` was the corpus's only
  money field left as a string, 8,658 of them across ten elections, and the
  currency is load-bearing: 8,111 are euro and 547 are litas in the same
  column. `parse_money` splits them.

* **A value that is only a replacement character is missing** — 30 records
  (28 in 2008-seimo) carried a biography whose entire text was `U+FFFD`. It is
  a NUL byte in VRK's own page, which the HTML parser renders as a replacement
  character; there is no biography behind it. `is_missing_marker`.

And one repair. 173 further values held an embedded `U+FFFD` where
punctuation belongs — `AB �Lietuvos geležinkeliai"`, 152 of them in
`2004-seimo`. The character itself is **not** ours to re-decode: fetching the
page live on 2026-08-29 returns it in VRK's own bytes, so the original was
destroyed upstream and no encoding recovers it. What *can* be recovered is
the character the surviving half of a pair proves, and
`repair_lost_punctuation` does four such repairs (issue #164 measured the
survivors and found the old "no closing quote to prove what it stood for"
account false for all 20 of them):

* an **opening** quote before a phrase a closing one ends — 153 of the 173;
* a **closing** quote after a phrase an opening one begins — 15 more, whose
  surviving glyph decides whether `“` or `"` is written back;
* an opening quote VRK followed with a space — 2, skipped by the old rule's
  `\\S` lookahead;
* an opening **bracket** whose closing one is a few characters away — 1.

That leaves **6 values holding 9 characters**, and not one of them is a
recoverable quote. Five are a destroyed *letter*, `š` or `Š` inside a
Lithuanian word (`i�rinktas`, `Roki�kio`, `vir�ininku`), on 2000-seimo pages
where the same words appear correctly elsewhere — a rule that turned an
in-word replacement into `š` would be right on all five and wrong the first
time the lost byte was a `ž`. The sixth is one 2004-seimo biography whose
four closing quotes lost their *opening* partner too, to a hyphen
(`-Termoizoliacija�`, `-Lietuvos rytas�`): nothing survives to pair against,
and "a hyphen opens a quotation" is not a rule this corpus can afford.
`rawData` keeps the replacement character either way.

`clean_value` composes the string rules in the order a normalizer wants them,
and is what the era `_normalize_text_value` functions call. Two rules sit
*outside* it on purpose — `is_refusal` and `candidate_status_note` — because
`clean_value`'s output also lands in `rawData`, which the docs promise keeps
the text VRK published; a refusal is a word and a status marker is a name's
suffix, and both are filtered where a normalizer decides meaning.
"""

from __future__ import annotations

import re
import unicodedata
from typing import Any

#: Separators a value may end with and mean nothing by.
TRAILING_SEPARATORS = ",;"

REPLACEMENT_CHARACTER = "�"

#: A value made only of these says "nothing here" — the empty string, the
#: dash or dashes VRK prints for an unanswered field, the full stop or comma a
#: candidate typed instead of an answer, and the replacement character a NUL
#: byte in the page decodes to.
#:
#: The set was `" \t\r\n-�"`, which is why `"-"` nulled out and `"-,-"`
#: did not: 207 punctuation-only values survived in 194 records across 14
#: elections and 39 (election, key) pairs — `"."` 89, `"-,-"` 73, `"-, -"` 28,
#: `"–"` 7, plus `".."`, `"..."`, `"...."`, `",-"`, `"., ."`, `". ."`. Dash one
#: half of question 16 and you got null; dash both and the template joined
#: them with a comma and you got the string (issue #164,
#: `jurij-avdejev-2012-seimo`). `is_missing_marker` only asks whether a value
#: is *entirely* marks, so `"Vilnius, LT"` is untouched.
_EMPTY_MARKS = f" \t\r\n-,.;–—{REPLACEMENT_CHARACTER}"

#: VRK's own refusal token, byte-identical on 185,939 occurrences across 43
#: elections. Every era's normalizer folds it to null except the 1996 Seimas
#: archive card, whose 20 survivors reached `normalized` — 18 as a marital
#: status and, worse, 2 as an entry of `anksciau-isrinktas`, so the corpus
#: asserted a prior mandate for two candidates who declined to answer
#: (issue #164). Not in `_EMPTY_MARKS`, deliberately: `clean_value`'s job is
#: whitespace and punctuation, and a refusal is a *word* — the distinction
#: is what keeps `rawData` holding the published text.
REFUSAL_TOKENS = frozenset({"nenurode", "nenurodė", "nenurodyta", "nenurodo"})

# The replacement character stands in for an opening quote only when it opens
# something: a closing quote comes later in the value, and at most one space
# separates the two. `AB <FFFD>Lietuvos geležinkeliai"` matches, and so does
# `AB <FFFD> Vakarų skirstomieji tinklai"` — VRK left a space after the quote
# on two 2004-seimo values and the `\S` this used to require skipped both
# (issue #164). A lone `<FFFD>` does not match, nor one with nothing quoted
# after it.
_LOST_OPEN_QUOTE = re.compile(rf"{REPLACEMENT_CHARACTER}(?= ?\S[^\"“”]*[\"“”])")

# And the mirror: the replacement character *closes* a quotation whose
# opening glyph is earlier in the same value. `"La-Nika Baltic Ltd<FFFD>`,
# `„Vilniaus pirmoji autotransporto įmonė<FFFD>` — 15 of the corpus's 30
# broken characters, every one of them the closing half of a pair the value
# itself proves (issue #164). The opening glyph decides which closing one to
# write, so the two forms are matched separately.
_LOST_CLOSE_AFTER_LOW = re.compile(rf"(?<=„)([^„“\"]+){REPLACEMENT_CHARACTER}")
_LOST_CLOSE_AFTER_STRAIGHT = re.compile(rf"(?<=\")([^\"„“]+){REPLACEMENT_CHARACTER}")

# `Tėvynės liaudies partija <FFFD>TLP)` — an opening bracket whose closing
# one is right there. One value in the corpus.
_LOST_OPEN_BRACKET = re.compile(rf"{REPLACEMENT_CHARACTER}(?=[^()]{{1,40}}\))")

#: Lithuanian opens a quotation low and closes it high. Where VRK's surviving
#: partner is a plain `"` the pair is written straight, and where it is `„`
#: the Lithuanian pair is completed — in both directions the *published*
#: glyph is kept and only the destroyed one is supplied.
OPENING_QUOTE = "„"
CLOSING_QUOTE = "“"
STRAIGHT_QUOTE = '"'

# A printed amount, with the currency where the value carries one: "22000
# EUR", "75000 Eur", "15000 Ltl", and the bare "13000" of the columns that
# name their currency in the header instead. All but a handful of the 17,894
# such values in the corpus are whole numbers, but the fractional form is
# accepted so a page that starts printing centai does not parse to None.
_MONEY = re.compile(
    r"^(?P<amount>-?\d[\d\s ]*(?:[.,]\d+)?)"
    r"\s*(?P<currency>EUR|Eur|eur|€|LTL|Ltl|LT|Lt|lt)?$"
)

#: What each printed currency token is stored as. `Lt` matches
#: `turto-ir-pajamu-deklaracijos.valiuta`, which every 2004-2015 record
#: already carries.
CURRENCIES = {
    "eur": "EUR",
    "€": "EUR",
    "ltl": "Lt",
    "lt": "Lt",
}

#: A date as these columns print it: ISO, or a bare year. The year is not the
#: exception the old comment here called it ("the only form these columns
#: print" was ISO): measured over the corpus, `nuosprendzio-data` is
#: year-only on 325 of its 1,016 values and ISO on 690 (one is a year and
#: month), and `isipareigojimo-data` is year-only on 2,292 of 7,287 — 31.5 %
#: (issue #150).
_DATE = re.compile(r"\d{4}-\d{2}-\d{2}|\d{4}")

# "Kaimo sodyba su žeme, 2006-11-01" — the object and its date in the one cell
# VRK heads "Dovana, data". The date is last, after the final comma.
_OBJECT_AND_DATE = re.compile(r"^(?P<object>.*?),\s*(?P<date>\d{4}(?:-\d{2}-\d{2})?)$")


def strip_trailing_separator(value: str) -> str:
    """Drop separators a value ends with and nothing follows.

    `"Jonas, Rasa, Živilė, Jovita,"` loses its last comma and keeps the three
    that separate something. Repeated and space-padded separators go too;
    a full stop stays, because a sentence is allowed to end.
    """
    stripped = value.rstrip()
    while stripped and stripped[-1] in TRAILING_SEPARATORS:
        stripped = stripped[:-1].rstrip()
    return stripped


def repair_lost_punctuation(value: str) -> str:
    """Restore the punctuation VRK's own encoding lost, where the value proves
    what it was.

    Four shapes, all of them a replacement character whose partner survives in
    the same value, so nothing is guessed:

    * an **opening** quote before a phrase a closing quote ends —
      `AB <FFFD>Lietuvos geležinkeliai"`, 153 of the corpus's original 173;
    * a **closing** quote after a phrase an opening one begins —
      `"La-Nika Baltic Ltd<FFFD>`, whose opening glyph decides whether the
      Lithuanian `“` or the straight `"` is written back;
    * an opening quote VRK followed with a **space**, which the old
      `\\S` lookahead skipped;
    * an opening **bracket** whose closing one is a few characters away.

    What is left after this is the destroyed *letter* class — 12 characters on
    nine 2000-seimo biographies, every one of them `š` or `Š` on the evidence
    of the word it sits inside (`i<FFFD>rinktas`, `Roki<FFFD>kio`,
    `vir<FFFD>ininku`). Those are not repaired: a rule that turned an in-word
    replacement into `š` would be right on all twelve and wrong the first time
    the lost byte was a `ž`. They are described for what they are instead —
    the four places that used to call every survivor an unrecoverable *quote*
    were wrong about all 20 (issue #164).
    """
    if REPLACEMENT_CHARACTER not in value:
        return value
    value = _LOST_OPEN_QUOTE.sub(OPENING_QUOTE, value)
    value = _LOST_CLOSE_AFTER_LOW.sub(rf"\1{CLOSING_QUOTE}", value)
    value = _LOST_CLOSE_AFTER_STRAIGHT.sub(rf"\1{STRAIGHT_QUOTE}", value)
    return _LOST_OPEN_BRACKET.sub("(", value)


#: The name this repair had when it only did the opening quote.
repair_lost_open_quote = repair_lost_punctuation


def is_missing_marker(value: str) -> bool:
    """Is this value nothing but the marks a page leaves where a value isn't?"""
    return not value.strip(_EMPTY_MARKS)


#: What a trailing parenthetical on a *listing* name means, when it means
#: something about the candidate rather than about the ballot.
#:
#: Measured across every retained listing page of all 55 elections
#: (issue #164): 25 distinct trailing parentheticals, and exactly six
#: occurrences are candidate status markers — "išbrauktas - Seimo nutarimu"
#: ×2, "išbraukta - Seimo nutarimu" ×2, "panaikinta kandidato registracija",
#: "mirė". The other 24 forms are about the ballot, not the person: the
#: 2016 constituency flags `(D)` and `(V)`, party and coalition names
#: ("liberalai", "socialliberalai"), the mayoral role marker
#: ("kandidatas į savivaldybės merus"), list numbers ("Nr.6") and page
#: furniture. A broad "keep any trailing parenthetical" rule reads 143 notes
#: out of the 2016 listing where there are two.
CANDIDATE_STATUS_MARKERS = (
    "isbrauktas",
    "isbraukta",
    "panaikinta kandidato registracija",
    "mire",
)

_TRAILING_PARENTHETICAL = re.compile(r"\(([^()]{1,64})\)\s*$")


def candidate_status_note(raw_name: str) -> str:
    """The status a listing name's trailing parenthetical states, or "".

    The candidate page leaves this line blank on every election that prints
    it, so the listing is the only place it exists — and the name cleaners
    strip it. Two 2016-seimo candidates lost theirs entirely: the corpus said
    a candidate who died before polling day and one whose registration was
    revoked were ordinary losing candidates (issue #164).
    """
    match = _TRAILING_PARENTHETICAL.search(" ".join(str(raw_name).split()))
    if match is None:
        return ""
    note = match.group(1).strip()
    folded = _fold_marker(note)
    return note if any(folded.startswith(m) for m in CANDIDATE_STATUS_MARKERS) else ""


def _fold_marker(text: str) -> str:
    """Lower-cased and diacritic-free, for matching a marker as a phrase."""
    return "".join(
        c
        for c in unicodedata.normalize("NFD", text.lower())
        if not unicodedata.combining(c)
    )


def is_refusal(value: Any) -> bool:
    """Is this value VRK's own "I decline to answer" token?

    Applied at the normalizer boundary, not inside `clean_value`: a refusal is
    a word rather than punctuation, and `clean_value`'s output is also what
    lands in `rawData`, which the docs promise keeps the text VRK published.
    """
    return isinstance(value, str) and value.strip().lower() in REFUSAL_TOKENS


def clean_value(value: str) -> str | None:
    """The string rules, in the order a normalizer wants them.

    The quote repair runs first so a repaired value is judged on its repaired
    text, and `None` comes back for a value that turns out to hold nothing —
    which is what the era normalizers already return for VRK's "nenurodė".
    """
    repaired = strip_trailing_separator(repair_lost_open_quote(value))
    return None if is_missing_marker(repaired) else repaired


def as_money(amount: float | int | None) -> float | None:
    """Money is a float, whether or not this particular figure has cents."""
    return None if amount is None else float(amount)


def parse_money(value: Any) -> tuple[float | None, str | None]:
    """Split a printed amount into its figure and its currency.

    `"22000 EUR"` becomes `(22000.0, "EUR")` and `"15000 Ltl"` becomes
    `(15000.0, "Lt")`. A figure printed without a currency -- the columns that
    name it in their own header -- becomes `(13000.0, None)`. A value that is
    not a printed amount comes back as `(None, None)`, leaving the caller to
    keep whatever it had.
    """
    if not isinstance(value, str):
        return None, None
    match = _MONEY.match(value.strip())
    if match is None:
        return None, None
    digits = re.sub(r"[\s ]", "", match.group("amount")).replace(",", ".")
    try:
        amount = float(digits)
    except ValueError:  # pragma: no cover - the pattern already proved the shape
        return None, None
    currency = match.group("currency")
    return amount, CURRENCIES[currency.lower()] if currency else None


def split_object_and_date(value: Any) -> tuple[str | None, str | None]:
    """Split a "<thing>, <date>" cell into the thing and the date.

    VRK heads two columns of the 2007-2008 private-interest form `Dovana,
    data` and `Paslauga, data` — a comma-joined *pair* of column names, not a
    date field — and prints both values in one cell. Slugified, the header
    reads `dovana-data`, which is indistinguishable from every other date key
    in the corpus until you look at the value.

    A cell that is only a date returns `(None, date)`; one this cannot read
    returns `(value, None)`, so the text is never dropped.
    """
    if not isinstance(value, str):
        return None, None
    text = value.strip()
    if not text:
        return None, None
    if _DATE.fullmatch(text):
        return None, text
    match = _OBJECT_AND_DATE.match(text)
    if match is None:
        return text, None
    return match.group("object").strip() or None, match.group("date")


#: Private-interest row columns that print a money figure. VRK names each
#: after what it holds, so the column key is the rule: `sandorio-suma` carries
#: its currency in the value (EUR from 2016, Ltl on the 2016-era pages that
#: still declared litas), `sandorio-suma-lt` and `suma-skaiciais` state it in
#: the header instead. Measured on 2026-08-29: 8,658 / 7,047 / 2,189 values,
#: every one of them a parseable figure and every one of them a string.
#:
#: `*-vertes-litais-kodas` is deliberately absent. It looks numeric ("001",
#: "002") but it is VRK's value-band code, and parsing it would eat the
#: leading zeros that distinguish the bands.
MONEY_COLUMNS = frozenset({"sandorio-suma", "sandorio-suma-lt", "suma-skaiciais"})

#: The currency key a money column gets when the value carries the currency
#: rather than the header. Named after the column so a row can hold two.
MONEY_CURRENCY_SUFFIX = "-valiuta"

#: Columns VRK heads with a comma-joined *pair* of names, both values in the
#: one cell — see `split_object_and_date`. The map is column key to the pair
#: of keys it becomes.
PAIRED_COLUMNS = {
    "dovana-data": ("dovana", "data"),
    "paslauga-data": ("paslauga", "data"),
}


def interest_row_columns(key: str, value: Any) -> dict[str, Any]:
    """What one private-interest row column contributes to its row.

    Most columns contribute themselves. The three money columns contribute a
    float (plus the currency, where the value carried it rather than the
    header), the two comma-headed columns contribute the pair of values VRK
    printed in one cell, and a date column contributes a date VRK printed
    twice only once.

    A value the rule cannot read is passed through unchanged, so a page that
    starts printing something new is a finding in the corpus rather than a
    silent null.
    """
    if key in PAIRED_COLUMNS:
        object_key, date_key = PAIRED_COLUMNS[key]
        thing, date = split_object_and_date(value)
        return {object_key: thing, date_key: date}

    if key in MONEY_COLUMNS:
        amount, currency = parse_money(value)
        if amount is None:
            return {key: value}
        if currency is None or key.endswith("-lt"):
            return {key: amount}
        return {key: amount, f"{key}{MONEY_CURRENCY_SUFFIX}": currency}

    if key.endswith("-data"):
        return {key: collapse_repeated_date(value)}

    return {key: value}


def collapse_repeated_date(value: Any) -> Any:
    """Fold a date VRK printed twice in one cell back to one.

    Ten cells across the 2011 Marijampolė by-election read `"2009-12-14
    2009-12-14"`, in the page's own source. Only an exact repetition is
    folded; two different dates in a cell are a finding, not a duplicate.
    """
    if not isinstance(value, str):
        return value
    parts = value.split()
    if len(parts) == 2 and parts[0] == parts[1] and _DATE.fullmatch(parts[0]):
        return parts[0]
    return value
