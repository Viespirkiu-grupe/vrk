"""The asset-and-income declaration block, for every era that publishes one.

VRK has published a candidate's declarations as titled sections since 2004, and
every era of pages says the same four things about them: *whose* declaration it
is, *which* income-tax form the extract is taken from, *what year* it covers,
and *which figures* it states. Before issue #98 the normalized layer kept only
the last of those, and only seven of the figures.

Three losses, all of them recoverable from `rawData` alone:

* **the figures**. The GPM308/GPM311 extract prints six or seven lines; the
  normalizers matched a fixed pair and dropped the rest, so 18,251 non-zero
  declared amounts on 10,063 records had nowhere to go -- self-employment
  income and its allowable deductions, income from selling non-business assets
  and what that asset had cost. Every published line has a key here.
* **the year and the form**. A declaration filed for 2023 and one filed for
  2015 were indistinguishable. Both are in the section heading where the page
  prints them ("... IŠRAŠAS (2023 m.)", "... GPM311 FORMOS ..."), and the
  Seimas-era pages state the period in their closing note instead.
* **the scope**. 2004 and 2007 published *separate* declarations for the
  candidate, the family and the spouse, and the normalizer flattened them into
  one unlabelled set of numbers by letting the last section win. On 243 records
  of `2007-vasario-25-savivaldybiu` that last section was the *spouse's*, so
  the corpus reported a spouse's assets as the candidate's.

Two more surfaced while checking that nothing published is dropped: a section
the page prints twice was summed twice (thirteen 2007 candidates' income read
double what their page states), and the 2007 income sentence was refused whole
when its tax figure was missing, which lost 522 records' declared income along
with it.

The eras and what they publish:

| era | asset heading | income heading | scope |
|---|---|---|---|
| 2004-2005 (`ep_2004` family) | METINĖ GYVENTOJO / ŠEIMOS TURTO DEKLARACIJA | METINĖ GYVENTOJO PAJAMŲ DEKLARACIJA, five FR0462 lines | own or family, one of the two |
| 2007 municipal | Gyventojo / Šeimos / Sutuoktinio turto deklaracija | Pajamų deklaracija, five FR0462 lines | up to two asset declarations, one of which can be the spouse's |
| 2007-2015 (`seimo_zirmunu_2015` family) | METINĖS GYVENTOJO(ŠEIMOS) TURTO ... | ... GPM302/GPM305/GPM308 FORMOS ... | combined, litas |
| 2016-2025 (`seimo_2016` family) | METINĖS GYVENTOJO (ŠEIMOS) TURTO ... (YYYY m.) | ... GPM308/GPM311 FORMOS ... (YYYY m.) | combined, euro |

`normalize_declaration` is the one implementation of all of that. What differs
between eras is the amount parser (litas or euro) and whether the income
section prints per-form prose lines, so both are arguments rather than a
private copy per module -- eight near-identical copies existed before this,
and the elections whose copy was never updated paid for it (issue #81's
`2020-seimo`, whose income read null on all 1,753 records).
"""

from __future__ import annotations

import json
import re
import unicodedata
from typing import Any, Callable, Iterable

from scraper.shared.files import slugify
from scraper.shared.values import as_money

# --------------------------------------------------------------------------
# Value labels
# --------------------------------------------------------------------------

#: The five asset rows. Their Roman-numeral labels have not changed since 2004
#: (only their capitalisation, which the slug folds), so they match whole.
ASSET_KEY_ALIASES = {
    "i-privalomas-registruoti-turtas": "privalomas-registruoti-turtas",
    "ii-vertybiniai-popieriai-meno-kuriniai-juvelyriniai-dirbiniai": (
        "vertybiniai-popieriai-meno-kuriniai-juvelyriniai-dirbiniai"
    ),
    "iii-pinigines-lesos": "pinigines-lesos",
    "iv-suteiktos-paskolos": "suteiktos-paskolos",
    "v-gautos-paskolos": "gautos-paskolos",
}

#: The money rows, matched on their opening words. Their labels do not hold
#: still: VRK restates them with every revision of the income-tax form, quoting
#: the form number and the fields it sums ("Gautų pajamų suma (GPM308 formos
#: 12, 13, 13a, 14, 20 laukelių ...)"), so a key made from the whole sentence
#: silently loses any election filed on a newer form. That is issue #81.
#:
#: Measured over the declaration rows of all 113,073 records: sixteen distinct
#: spellings across the nine concepts, these prefixes match all sixteen, and no
#: other declaration row in any election begins with one of them. The only
#: labels they leave unmatched are the form-name rows ("GPM305 formos
#: deklaracijos", "FR0462S15 Formos deklaracijos") -- which carry a form, not a
#: figure, and are read by `section_form` and the `form_lines` hook -- and the
#: 2004 pages' two profile rows ("3. Darbovietė", "Pildymo data").
MONEY_KEY_PREFIXES: tuple[tuple[str, str], ...] = (
    # "Gautų pajamų suma (GPM302/GPM305/GPM308 ...)" up to 2017, then the prose
    # wording the 2018-and-later pages use.
    ("gautu-pajamu-suma", "gautos-pajamos"),
    ("deklaruota-apmokestinamuju-ir-neapmokestinamuju-pajamu-suma", "gautos-pajamos"),
    # "Išskaičiuota (sumokėta) pajamų mokesčio suma (GPM308 formos 26
    # laukelis)" up to 2017 -- "Išskaičiuota mokesčio suma (36 laukelio suma)"
    # on the 2007 Dzūkija by-election's GPM302 extract -- then the prose one.
    ("isskaiciuota-sumoketa-pajamu-mokescio-suma", "sumoketas-pajamu-mokestis"),
    ("isskaiciuota-mokescio-suma", "sumoketas-pajamu-mokestis"),
    ("deklaruota-moketina-pajamu-mokescio-suma", "sumoketas-pajamu-mokestis"),
    # The four lines the 2018-and-later GPM308/GPM311 extract adds, and which
    # nothing normalized before issue #98.
    ("deklaruota-individualios-veiklos-pajamu-suma", "individualios-veiklos-pajamos"),
    ("su-individualios-veiklos-pajamu-gavimu", "individualios-veiklos-atskaitymai"),
    ("deklaruota-ne-individualios-veiklos-turto-pardavimo", "turto-pardavimo-pajamos"),
    # The acquisition cost of what was sold, whose label VRK writes two ways
    # ("Deklaruoto turto įsigijimo kaina ...", "To turto įsigijimo kaina ...").
    ("deklaruoto-turto-isigijimo-kaina", "turto-isigijimo-kaina"),
    ("to-turto-isigijimo-kaina", "turto-isigijimo-kaina"),
)

#: The value keys of the block, in the order they are written. The first seven
#: are the corpus's long-standing set; the last four are the GPM lines issue
#: #98 recovered.
DECLARATION_VALUE_KEYS = (
    "privalomas-registruoti-turtas",
    "vertybiniai-popieriai-meno-kuriniai-juvelyriniai-dirbiniai",
    "pinigines-lesos",
    "suteiktos-paskolos",
    "gautos-paskolos",
    "gautos-pajamos",
    "sumoketas-pajamu-mokestis",
    "individualios-veiklos-pajamos",
    "individualios-veiklos-atskaitymai",
    "turto-pardavimo-pajamos",
    "turto-isigijimo-kaina",
)

#: The five asset keys, which are the ones a scope applies to.
ASSET_VALUE_KEYS = tuple(ASSET_KEY_ALIASES.values())

#: Every key of the block, in the order it is written. An era that publishes
#: litas amounts, per-form income lines or a spouse declaration appends its own
#: keys after these (`valiuta`, `pastaba`, `pajamos-pagal-forma`,
#: `sutuoktinio`, `israsai`) -- see `normalize_declaration`.
DECLARATION_BLOCK_KEYS = (
    *DECLARATION_VALUE_KEYS,
    "deklaracijos-metai",
    "deklaracijos-forma",
    "deklaracijos-apimtis",
    "deklaracijos",
)

# --------------------------------------------------------------------------
# What the section heading says
# --------------------------------------------------------------------------

#: Whose declaration it is. `gyventojo-seimos` is the combined heading every
#: page from 2008 on prints ("METINĖS GYVENTOJO(ŠEIMOS) TURTO DEKLARACIJOS
#: ..."), which does not distinguish the two -- unlike 2004 and 2007, which
#: published one heading per scope.
SCOPE_OWN = "gyventojo"
SCOPE_FAMILY = "seimos"
SCOPE_SPOUSE = "sutuoktinio"
SCOPE_OWN_OR_FAMILY = "gyventojo-seimos"

#: Which scope the candidate's own figures are taken from, best first. A
#: spouse's declaration is never one of them.
SCOPE_PREFERENCE = (SCOPE_OWN, SCOPE_OWN_OR_FAMILY, SCOPE_FAMILY)

_YEAR_IN_TITLE = re.compile(r"\((\d{4})\s*m\.\)")
#: "GPM311", and the FR0462 family the 2004 and 2007 pages list one line per.
_FORM_NAME = re.compile(r"\b(GPM\d{3}[A-Z]?|FR\d{4}[A-Z0-9]*)\b")
#: The Seimas-era closing note: "... deklaracijos pateikiamos už laikotarpį nuo
#: 2011-01-01 iki 2011-12-31". The two dates always name one calendar year.
_PERIOD_IN_NOTE = re.compile(r"nuo\s+(\d{4})-01-01\s+iki\s+\1-12-31")


def normalize_space(value: str) -> str:
    return " ".join(str(value).split())


def source_key(label: Any) -> str:
    """A declaration row's label as a slug, the way every era module makes it."""
    return slugify(normalize_space(label).rstrip(":"))


def _fold(text: str) -> str:
    """Upper-cased and stripped of diacritics, for matching heading words.

    The headings are printed in mixed case across eras ("Šeimos turto
    deklaracija" in 2007, "METINĖ ŠEIMOS TURTO DEKLARACIJA" in 2004) and the
    2016-era pages are not consistent about the space in "GYVENTOJO (ŠEIMOS)".
    """
    decomposed = unicodedata.normalize("NFD", normalize_space(text).upper())
    return "".join(ch for ch in decomposed if unicodedata.category(ch) != "Mn")


def value_key(label: Any) -> str | None:
    """The block key a declaration row's label states, or None if it states none."""
    key = source_key(label)
    alias = ASSET_KEY_ALIASES.get(key)
    if alias is not None:
        return alias
    for prefix, target in MONEY_KEY_PREFIXES:
        if key.startswith(prefix):
            return target
    return None


def section_scope(title: Any) -> str | None:
    """Whose declaration a section's heading says it is."""
    folded = _fold(title)
    if "SUTUOKTINIO" in folded:
        return SCOPE_SPOUSE
    has_own = "GYVENTOJO" in folded or "GYVENTOJU" in folded
    has_family = "SEIMOS" in folded
    if has_own and has_family:
        return SCOPE_OWN_OR_FAMILY
    if has_family:
        return SCOPE_FAMILY
    if has_own:
        return SCOPE_OWN
    return None


def section_kind(title: Any) -> str | None:
    """`turto` for an asset extract, `pajamu` for an income one.

    Every asset heading names TURTO and no income heading does, so the asset
    test comes first: the 2004 income heading is "METINĖ GYVENTOJO PAJAMŲ
    DEKLARACIJA" and the modern one "METINĖS PAJAMŲ MOKESČIO DEKLARACIJOS ...",
    both of which name PAJAM and neither TURTO.
    """
    folded = _fold(title)
    if "TURTO" in folded:
        return "turto"
    if "PAJAM" in folded:
        return "pajamu"
    return None


def section_year(title: Any) -> int | None:
    """The tax year a section's heading states, as in "... IŠRAŠAS (2023 m.)"."""
    match = _YEAR_IN_TITLE.search(normalize_space(title))
    return int(match.group(1)) if match else None


def period_year(note: Any) -> int | None:
    """The tax year the page's closing note states, where the heading does not.

    The Seimas pages of 2008-2015 print no year in the heading and name the
    period in the note instead ("2012 m. ... rinkimuose deklaracijos
    pateikiamos už laikotarpį nuo 2011-01-01 iki 2011-12-31"). Only a note
    naming one whole calendar year is read; anything else is left as no year.
    """
    match = _PERIOD_IN_NOTE.search(normalize_space(note))
    return int(match.group(1)) if match else None


def section_form(title: Any, labels: Iterable[Any] = ()) -> str | None:
    """The income-tax form a section is an extract of.

    The 2008-and-later headings name it ("... GPM311 FORMOS ..."). The 2004 and
    2007 pages do not: they head the section "Pajamų deklaracija" and print one
    line per form the tax office knew of, so the form is read from the first of
    those lines instead -- FR0462 for both (the other four lines are its S, S0,
    S15 and S33 variants), GPM302 for the 2007 Dzūkija by-election, whose
    heading says only that the return was an interim one. Which variant the
    candidate actually filed is in `pajamos-pagal-forma`, one entry per line.
    """
    match = _FORM_NAME.search(normalize_space(title))
    if match:
        return match.group(1)
    for label in labels:
        match = _FORM_NAME.search(normalize_space(label))
        if match:
            return match.group(1)
    return None


# --------------------------------------------------------------------------
# The block
# --------------------------------------------------------------------------


def _sum_amounts(current: Any, amount: Any) -> Any:
    if amount is None:
        return current
    if current is None:
        return amount
    return as_money(round(current + amount, 2))


def normalize_declaration(
    payload: dict[str, Any] | None,
    parse_amount: Callable[[Any], int | float | None],
    *,
    form_lines: Callable[[dict[str, Any]], list[dict[str, Any]] | None] | None = None,
) -> dict[str, Any]:
    """The declaration block for one record's `rawData.turtoIrPajamuDeklaracijos`.

    `parse_amount` reads a printed figure -- litas before 2016, euro after --
    and `form_lines`, where an era's income section states its figures as one
    prose line per form rather than as two labelled rows, turns one such item
    into `{"forma", "gautos-pajamos", "sumoketas-pajamu-mokestis"}` entries.
    Passing it also switches on the `pajamos-pagal-forma` key, so an era either
    always publishes that list or never does.

    The block is:

    * the eleven value keys, from the candidate's own declaration -- their own
      where the page publishes one, the family's where it publishes that
      instead, and never the spouse's;
    * `deklaracijos-metai`, `-forma` and `-apimtis`: what the extract is;
    * `deklaracijos`: every published section in page order, each with its own
      heading, scope, year, form and figures, so nothing the page printed is
      collapsed away;
    * `sutuoktinio`, the spouse's asset figures -- present only on the records
      whose page publishes a spouse declaration.
    """
    payload = payload if isinstance(payload, dict) else {}
    sections_raw = payload.get("sections")
    sections_raw = sections_raw if isinstance(sections_raw, list) else []

    note_year = period_year(payload.get("note") or "")
    sections: list[dict[str, Any]] = []
    all_form_lines: list[dict[str, Any]] = []
    seen: set[str] = set()

    for section in sections_raw:
        if not isinstance(section, dict):
            continue
        items = [item for item in (section.get("items") or []) if isinstance(item, dict)]
        title = normalize_space(section.get("title") or "")

        # A section the page prints twice over is one extract rendered twice,
        # not two declarations. Nineteen records in four elections have such a
        # repeat and fifteen of them are byte-identical; summing them counted
        # thirteen candidates' 2007 income twice over (34,197.32 Lt against a
        # declaration of 17,098.66). The repeat that *differs* -- Sadeckas in
        # 2008, two asset extracts under one heading; Diškevičius in 2007, an
        # income extract and an empty second one -- is a second declaration and
        # is kept.
        fingerprint = json.dumps([title, items], ensure_ascii=False, sort_keys=True)
        if fingerprint in seen:
            continue
        seen.add(fingerprint)

        values: dict[str, Any] = {}
        for item in items:
            lines = form_lines(item) if form_lines is not None else None
            if lines:
                # The 2004 and 2007 pages print one income line per form, all
                # but the one the candidate filed at zero; the declared income
                # is the sum of the lines, not the last of them.
                all_form_lines.extend(lines)
                for line in lines:
                    for key in ("gautos-pajamos", "sumoketas-pajamu-mokestis"):
                        values[key] = _sum_amounts(values.get(key), line.get(key))
                continue
            key = value_key(item.get("key", ""))
            if key is None:
                continue
            values[key] = parse_amount(item.get("value"))

        section_year_in_title = section_year(title)
        sections.append(
            {
                "pavadinimas": title or None,
                "rusis": section_kind(title),
                "apimtis": section_scope(title),
                "metai": section_year_in_title if section_year_in_title is not None else note_year,
                "forma": section_form(title, (item.get("key", "") for item in items)),
                "reiksmes": values,
            }
        )

    block: dict[str, Any] = dict.fromkeys(DECLARATION_VALUE_KEYS)
    own_scope: str | None = None

    asset_sections = [s for s in sections if s["reiksmes"].keys() & set(ASSET_VALUE_KEYS)]
    own_asset = _preferred_asset_section(asset_sections)
    if own_asset is not None:
        own_scope = own_asset["apimtis"]
        for key in ASSET_VALUE_KEYS:
            if key in own_asset["reiksmes"]:
                block[key] = own_asset["reiksmes"][key]

    # The money rows carry no scope of their own -- 2007 heads its income
    # extract "Pajamų deklaracija" with no owner and every other era publishes
    # one income section -- so they are read from every section but the
    # spouse's, and what several of them state is summed, as the per-form lines
    # within one section are.
    for section in sections:
        if section["apimtis"] == SCOPE_SPOUSE:
            continue
        for key, value in section["reiksmes"].items():
            if key not in ASSET_VALUE_KEYS:
                block[key] = _sum_amounts(block[key], value)

    block["deklaracijos-metai"] = next(
        (s["metai"] for s in sections if s["metai"] is not None), None
    )
    block["deklaracijos-forma"] = next(
        (s["forma"] for s in sections if s["rusis"] == "pajamu" and s["forma"]),
        next((s["forma"] for s in sections if s["forma"]), None),
    )
    block["deklaracijos-apimtis"] = own_scope
    block["deklaracijos"] = sections
    if form_lines is not None:
        block["pajamos-pagal-forma"] = all_form_lines

    spouse = next((s for s in asset_sections if s["apimtis"] == SCOPE_SPOUSE), None)
    if spouse is not None:
        block["sutuoktinio"] = {
            key: spouse["reiksmes"].get(key) for key in ASSET_VALUE_KEYS
        }

    return block


def _preferred_asset_section(sections: list[dict[str, Any]]) -> dict[str, Any] | None:
    """The asset declaration the candidate's own figures come from.

    Their own before the family's, and a spouse's never: on 243 records of
    `2007-vasario-25-savivaldybiu` the spouse's declaration was the last
    section on the page, and letting the last section win reported a spouse's
    assets as the candidate's (issue #98).
    """
    for scope in SCOPE_PREFERENCE:
        matching = [section for section in sections if section["apimtis"] == scope]
        if matching:
            # Among declarations of the same scope the last one on the page
            # wins, which is what every era did before there was a preference
            # at all -- one 2008 record publishes two asset extracts under the
            # same combined heading, and this leaves its stored figures alone.
            return matching[-1]
    return next(
        (section for section in reversed(sections) if section["apimtis"] != SCOPE_SPOUSE),
        None,
    )


# --------------------------------------------------------------------------
# Derived: the income figure to read
# --------------------------------------------------------------------------

INCOME_TOTAL = "deklaruota-suma"
INCOME_EMPLOYMENT = "darbo-santykiu"
INCOME_NONE = "nera"

#: The irrevocable LTL/EUR conversion rate fixed for the 2015-01-01 changeover.
#: Every pre-2016 election declares in litas (`valiuta` is `"Lt"` on all
#: 79,071 records that carry the section, 1996 through 2015, with no
#: exceptions); every 2016-and-later one declares in euro and says nothing.
LITAS_PER_EURO = 3.4528

CURRENCY_LITAS = "Lt"
CURRENCY_EURO = "EUR"


def deklaracijos_valiuta(declaration: dict[str, Any] | None) -> str | None:
    """The currency one declaration block's figures are published in.

    `"Lt"` where the record states it, `"EUR"` for a block that states
    nothing — no record anywhere says `"EUR"`, so in the stored corpus the
    euro is marked by *absence*, which is too load-bearing to hand a
    consumer (issue #97). Measured over all 113,073 records: `valiuta` is
    `"Lt"` on every 1996–2015 record with the section and absent from
    `2016-seimo` on. None when there is no declaration block at all.
    """
    if not isinstance(declaration, dict):
        return None
    return CURRENCY_LITAS if declaration.get("valiuta") == CURRENCY_LITAS else CURRENCY_EURO


# --------------------------------------------------------------------------
# Derived: total declared assets, with the measure named
# --------------------------------------------------------------------------

#: What a total-assets figure is a sum *of*, per era of the declaration form.
TURTAS_SPLIT = "skaidytas"  # property + securities + cash, summed from split rows (2004 on)
TURTAS_PLUS_CASH = "turtas-plius-lesos"  # the 1996-2000 combined "Turtas ir piniginės lėšos" row
TURTAS_PLUS_SECURITIES = "turtas-plius-vp"  # 2002's "Turtas ir vertybiniai popieriai" row, plus its cash row

#: The split rows the modern total sums. Loans given are an asset too, but the
#: archive-era combined rows exclude them, so keeping them out of every era's
#: total is what makes the figure comparable; they stay available as their own
#: keys.
_SPLIT_TOTAL_KEYS = (
    "privalomas-registruoti-turtas",
    "vertybiniai-popieriai-meno-kuriniai-juvelyriniai-dirbiniai",
    "pinigines-lesos",
)

#: The era-marker keys. Present-with-null still marks the era: the archive
#: elections carry the modern keys as always-null placeholders, so key
#: *presence* of the era's own row is what decides, never value.
_ARCHIVE_COMBINED_KEY = "turtas-ir-pinigines-lesos-metu-pabaigoje"
_2002_COMBINED_KEY = "turtas-ir-vertybiniai-popieriai-laikotarpio-pabaigoje"


def _non_null_sum(values: Iterable[Any]) -> int | float | None:
    total: int | float | None = None
    for value in values:
        if isinstance(value, (int, float)):
            total = value if total is None else as_money(round(total + value, 2))
    return total


def deklaruotas_turtas(declaration: dict[str, Any] | None) -> dict[str, Any]:
    """One total-declared-assets concept: `{"suma", "matas"}`.

    The documented seven-key contract reaches 73.9 % of records; the two
    archive families hold their wealth under other names while leaving the
    modern keys as always-null placeholders (issue #97). This resolves the
    era's own figure and *names the measure*, because the three are not the
    same sum:

    * `skaidytas` — property + securities + cash, summed from the split rows
      every sectioned form (2004 on) publishes;
    * `turtas-plius-lesos` — the 1996–2000 form's single combined row, which
      already includes the cash;
    * `turtas-plius-vp` — the 2002 form's property-and-securities row plus
      its separate cash row.

    Loans given/received are in none of the three. `suma` is in the block's
    published currency (`deklaracijos_valiuta`), never converted here.
    """
    declaration = declaration if isinstance(declaration, dict) else {}
    if _ARCHIVE_COMBINED_KEY in declaration:
        value = declaration.get(_ARCHIVE_COMBINED_KEY)
        value = value if isinstance(value, (int, float)) else None
        return {"suma": value, "matas": TURTAS_PLUS_CASH if value is not None else None}
    if _2002_COMBINED_KEY in declaration:
        total = _non_null_sum(
            (declaration.get(_2002_COMBINED_KEY), declaration.get("pinigines-lesos"))
        )
        return {"suma": total, "matas": TURTAS_PLUS_SECURITIES if total is not None else None}
    if any(key in declaration for key in _SPLIT_TOTAL_KEYS):
        total = _non_null_sum(declaration.get(key) for key in _SPLIT_TOTAL_KEYS)
        return {"suma": total, "matas": TURTAS_SPLIT if total is not None else None}
    return {"suma": None, "matas": None}


# --------------------------------------------------------------------------
# Derived: which measure the income and tax rows state
# --------------------------------------------------------------------------

#: `gautos-pajamos` is not one measure (issue #97). The 1996–2002 forms state
#: income *net of tax* ("Gauta pajamų (be mokesčių) suma" — provable from the
#: numbers: the modal tax/income ratio there is 0.40–0.52, above the era's
#: 33 % statutory rate, which a gross base cannot produce); everything from
#: 2004 on is gross. All of it normalizes to the same key.
PAJAMOS_NET_ARCHIVE = "neto-archyvas"
PAJAMOS_FR0462 = "fr0462"
PAJAMOS_GROSS_GPM = "gpm-bruto"
PAJAMOS_GROSS_DECLARED = "deklaruota-apmokestinamos"

#: And the tax row switches from tax *paid* ("Išskaičiuota (sumokėta) ...")
#: to tax *payable* ("Deklaruota mokėtina ...") with the 2018 rewording.
MOKESTIS_PAID = "sumoketas"
MOKESTIS_PAYABLE = "moketinas"

#: Label-prefix → measure, matched against the raw declaration rows the same
#: way `MONEY_KEY_PREFIXES` reads the values. Measured: the wording flips
#: cleanly at 2018 — every 2007–2017 election prints the "Gautų pajamų suma" /
#: "Išskaičiuota (sumokėta)" pair, every 2018-and-later one the "Deklaruota
#: apmokestinamųjų..." / "Deklaruota mokėtina..." pair, and no election mixes
#: them.
_INCOME_LABEL_MEASURES = (
    ("deklaruota-apmokestinamuju-ir-neapmokestinamuju-pajamu-suma", PAJAMOS_GROSS_DECLARED),
    ("gautu-pajamu-suma", PAJAMOS_GROSS_GPM),
)
_TAX_LABEL_MEASURES = (
    ("deklaruota-moketina-pajamu-mokescio-suma", MOKESTIS_PAYABLE),
    ("isskaiciuota-sumoketa-pajamu-mokescio-suma", MOKESTIS_PAID),
    ("isskaiciuota-mokescio-suma", MOKESTIS_PAID),
)


def _row_label_slugs(raw_declaration: dict[str, Any] | None) -> list[str]:
    if not isinstance(raw_declaration, dict):
        return []
    slugs = []
    for section in raw_declaration.get("sections") or []:
        if not isinstance(section, dict):
            continue
        for item in section.get("items") or []:
            if isinstance(item, dict):
                slugs.append(source_key(item.get("key", "")))
    return slugs


def _is_archive_form(declaration: dict[str, Any]) -> bool:
    """The 1996–2002 un-sectioned forms, whose income is net of tax."""
    return (
        "gautos-pajamos-darbo-santykiu" in declaration
        or _ARCHIVE_COMBINED_KEY in declaration
        or _2002_COMBINED_KEY in declaration
    )


def pajamu_matas(
    declaration: dict[str, Any] | None,
    raw_declaration: dict[str, Any] | None = None,
) -> str | None:
    """Which measure this declaration's income figure states.

    Decided from the record itself: the archive form's own keys mark the net
    era, `pajamos-pagal-forma` marks the FR0462 per-form pages, and for the
    GPM eras the row label retained in `rawData` says which wording the page
    printed. Falls back to the stated form name where no labels are
    available. None when there is no declaration block.
    """
    if not isinstance(declaration, dict):
        return None
    if _is_archive_form(declaration):
        return PAJAMOS_NET_ARCHIVE
    # The label the page printed decides first: `pajamos-pagal-forma` exists
    # on every 2004-2015 declaration (issue #98 normalizes the per-form lines
    # for the whole span), so it cannot distinguish the FR0462 pages from the
    # GPM ones -- but only the FR0462 pages print *no* income-total label.
    for slug in _row_label_slugs(raw_declaration):
        for prefix, measure in _INCOME_LABEL_MEASURES:
            if slug.startswith(prefix):
                return measure
    form = declaration.get("deklaracijos-forma")
    if isinstance(form, str):
        if form.startswith("FR"):
            return PAJAMOS_FR0462
        if form.startswith("GPM"):
            return PAJAMOS_GROSS_GPM
    if "pajamos-pagal-forma" in declaration:
        return PAJAMOS_FR0462
    return None


def mokescio_matas(
    declaration: dict[str, Any] | None,
    raw_declaration: dict[str, Any] | None = None,
) -> str | None:
    """Which measure this declaration's income-tax figure states."""
    if not isinstance(declaration, dict):
        return None
    if _is_archive_form(declaration):
        return MOKESTIS_PAID
    for slug in _row_label_slugs(raw_declaration):
        for prefix, measure in _TAX_LABEL_MEASURES:
            if slug.startswith(prefix):
                return measure
    form = declaration.get("deklaracijos-forma")
    if isinstance(form, str) and (form.startswith("FR") or form.startswith("GPM")):
        return MOKESTIS_PAID
    if "pajamos-pagal-forma" in declaration:
        return MOKESTIS_PAID
    return None


def deklaruotos_pajamos_bruto(
    declaration: dict[str, Any] | None,
    matas: str | None = None,
) -> int | float | None:
    """The gross-equivalent income, so one series is comparable across 2002→2004.

    The gross eras return the declared figure as is. The net era re-grosses
    exactly as issue #97 proves out: `gautos-pajamos +
    sumoketas-pajamu-mokestis` (the two rows of the same form), or the
    employment rows' pair where the income is the row-1 floor. Net income
    whose tax row is unpublished has no recoverable gross and returns None —
    the net figure itself is still in `gautos-pajamos`.
    """
    declaration = declaration if isinstance(declaration, dict) else {}
    income = deklaruotos_pajamos(declaration)
    if income["suma"] is None:
        return None
    if matas is None:
        matas = pajamu_matas(declaration)
    if matas != PAJAMOS_NET_ARCHIVE:
        return income["suma"]
    tax_key = (
        "sumoketas-pajamu-mokestis-darbo-santykiu"
        if income["saltinis"] == INCOME_EMPLOYMENT
        else "sumoketas-pajamu-mokestis"
    )
    tax = declaration.get(tax_key)
    if isinstance(tax, (int, float)):
        return as_money(round(income["suma"] + tax, 2))
    return None


def deklaruotos_pajamos(declaration: dict[str, Any] | None) -> dict[str, Any]:
    """One income concept for a record's `turto-ir-pajamu-deklaracijos`.

    Returns `{"suma", "saltinis", "valiuta"}`, where `saltinis` says which
    figure `suma` is:

    * `deklaruota-suma` -- the declared total, which is what every era from
      2004 on publishes and what `gautos-pajamos` holds;
    * `darbo-santykiu` -- row 1 of the 1990s form, employment income alone.
      The archive pages print rows 1 and 20 only, and row 20 is not always
      trustworthy: it fails by rendering 0 against a non-zero row 1, so
      `scraper/shared/deklaracija_archive_1990s.py` refuses it and leaves
      `gautos-pajamos` null. On 4,463 of `1997-kovo-23-savivaldybiu-tarybu`'s
      6,276 records -- and 147 of `2000-kovo-19`, 9 of `1996-spalio-20-seimo`,
      8 of `2000-seimo` and 1 of the 1997 Švenčionys repeat, 4,628 in all --
      row 1 is nonetheless there and is the only income figure the page has.
      This is how to read it *as* row 1: employment income only, so it is a
      floor on what was declared and not the total;
    * `nera` -- neither figure, and `suma` is None.

    The parser is deliberately not changed to substitute one for the other:
    a total the page contradicts stays refused, and a consumer that wants the
    floor asks for it here and is told what it got.
    """
    # Through `deklaracijos_valiuta`, not `declaration.get("valiuta")` — that
    # is the raw key, which is absent on every euro-era record, and the
    # resolver exists precisely because "in the stored corpus the euro is
    # marked by absence, which is too load-bearing to hand a consumer"
    # (issue #97). Reading it raw here made the two disagree on 33,120 of the
    # 112,218 records with a declaration: None where the sibling says EUR
    # (issue #161). Latent, because both builders take the currency from the
    # sibling — but a consumer reading this function's own `valiuta` got the
    # absence back.
    #
    # Resolved before the coercion below, so *no declaration* stays None:
    # an empty block would otherwise read as the euro era, which is the same
    # absence-as-meaning mistake one level up.
    currency = deklaracijos_valiuta(declaration)
    declaration = declaration if isinstance(declaration, dict) else {}

    total = declaration.get("gautos-pajamos")
    if total is not None:
        return {"suma": total, "saltinis": INCOME_TOTAL, "valiuta": currency}

    employment = declaration.get("gautos-pajamos-darbo-santykiu")
    if employment is not None:
        return {"suma": employment, "saltinis": INCOME_EMPLOYMENT, "valiuta": currency}

    return {"suma": None, "saltinis": INCOME_NONE, "valiuta": currency}
