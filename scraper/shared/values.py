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

And one repair. 173 further values held an embedded `U+FFFD` where a
Lithuanian opening quote belongs — `AB �Lietuvos geležinkeliai"`, 152 of them
in `2004-seimo`. That one is **not** ours to re-decode: fetching the page
live on 2026-08-29 returns the replacement character in VRK's own bytes, so
the original was destroyed upstream and no encoding recovers it. Where the
character opens a phrase that a `"` closes, the pair is unambiguous and
`repair_lost_open_quote` restores the opening `„` — 153 of the 173. The other
20 have no closing quote to prove what they were and are left exactly as VRK
published them; `rawData` keeps the replacement character either way.

`clean_value` composes the string rules in the order a normalizer wants them,
and is what the era `_normalize_text_value` functions call.
"""

from __future__ import annotations

import re
from typing import Any

#: Separators a value may end with and mean nothing by.
TRAILING_SEPARATORS = ",;"

REPLACEMENT_CHARACTER = "�"

#: A value made only of these says "nothing here" — the empty string, the
#: dash VRK prints for an unanswered field, and the replacement character a
#: NUL byte in the page decodes to.
_EMPTY_MARKS = f" \t\r\n-{REPLACEMENT_CHARACTER}"

# The replacement character stands in for an opening quote only when it opens
# something: a non-space follows it, and a closing quote comes later in the
# value. `AB <FFFD>Lietuvos geležinkeliai"` matches; a lone `<FFFD>` does not,
# and neither does one with nothing quoted after it.
_LOST_OPEN_QUOTE = re.compile(rf"{REPLACEMENT_CHARACTER}(?=\S[^\"“”]*[\"“”])")

#: Lithuanian opens a quotation low and closes it high. VRK's surviving
#: closing character is a plain `"`, which is what it published; only the
#: destroyed opening one is restored.
OPENING_QUOTE = "„"

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

#: An ISO date, which is the only form these columns print.
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


def repair_lost_open_quote(value: str) -> str:
    """Restore the opening quote VRK's own encoding lost.

    Only where the replacement character opens a phrase that a closing quote
    ends — see this module's docstring for why the rest are left alone.
    """
    if REPLACEMENT_CHARACTER not in value:
        return value
    return _LOST_OPEN_QUOTE.sub(OPENING_QUOTE, value)


def is_missing_marker(value: str) -> bool:
    """Is this value nothing but the marks a page leaves where a value isn't?"""
    return not value.strip(_EMPTY_MARKS)


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
