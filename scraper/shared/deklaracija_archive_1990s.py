"""Parse the 1996-1997 archive's income and asset declaration page (`kpdl.htm`).

Both 1990s archive families link one of these per candidate --
`scraper/shared/seimo_archive_1990s.py` and
`scraper/shared/savivaldybiu_archive_1997.py` -- and both used to capture the
link and stop there, which left all 7,292 of their records with no declared
figures at all while every other election in the corpus has them. This module
reads the page so those records land in the same
`turto-ir-pajamu-deklaracijos` keys as the rest of the corpus.

The page is a fixed extract of the "Lietuvos Respublikos gyventojų turto ir
pajamų deklaracijos pagrindinių duomenų išrašas" form, in five sections:

    I.   Bendrieji duomenys       -- name, workplace, family member counts
    II.  Turtas ir piniginės lėšos metų pradžioje    -- one combined total
    III. Gautos pajamos / sumokėti mokesčiai         -- rows 1 and 20 only
    IV.  Kalendoriniais metais įsigytas turtas       -- one combined total
    V.   Turtas ir piniginės lėšos metų pabaigoje    -- one combined total

Sections II, IV and V are the mismatch with the modern schema, and the reason
this module adds keys rather than reusing `privalomas-registruoti-turtas` and
`pinigines-lesos`: the 1990s form publishes turtas and piniginės lėšos as a
single summed figure ("Bendra suma pagal šios deklaracijos dalies 1, 2, 3 ir 4
punktus"), and the split the modern pages make is not recoverable from it.
Both modern keys are therefore emitted as null, and the combined figures get
their own `turtas-ir-pinigines-lesos-*` keys.

Section III prints only rows 1 (employment income) and 20 (the total), and
row 20 is not always trustworthy. It fails by rendering **0** against a
non-zero row 1 -- a sub-query that failed leaving its default behind, the
same failure these archives show elsewhere. Measured over all 6,469
declarations after the backfill:

    election                                     income totals refused
    1997-kovo-23-savivaldybiu-tarybu             4,463 of 5,477   (99% are 0)
    1996-spalio-20-seimo                             9 of   879   (89% are 0)
    1997-birzelio-29-svenciniu-tarybos-pakart.       1 of   108
    the other two                                    0

So the failure is not confined to one election, only overwhelmingly
concentrated in the largest. Note it is *not* a rounding artefact: across the
whole corpus exactly two refused totals fall short of row 1 by 1-2 Lt, and the
median shortfall is 946 Lt in the municipal general and 1,852 Lt in 1996.

VRK's own "Klaida užklausoje." banner is not the signal -- it marks the
municipal family as a whole, and Švenčionys carries it on 27 of 27 sampled
pages whose totals are fine.

So `gautos-pajamos` takes row 20 only when row 20 >= row 1, which is the
weakest check that catches a total contradicted by its own detail line;
otherwise the key is null and an anomaly is recorded, carrying the refused
figure so nothing is lost from the audit trail. Row 1 is always published as
it stands, under its own key, because it is a printed figure either way, and
for most of the municipal general it is the only income figure there is.
Guessing a total from it would be inventing one, which this repository does
not do with a field it cannot trust.

Two 1996 pages carry no declaration at all: VRK's archive froze an Oracle
error into them ("ORA-02391: exceeded simultaneous SESSIONS_PER_USER limit"),
which is still what the URL serves today. They raise
`DeclarationPageUnreadable` and are permanently unrecoverable.

Figures are integer litas on the 1996-1997 pages. The October 2000 Seimas
election (`scraper/elections/seimo_2000`) prints the same form inline on the
candidate page with the figures to the centas ("9546.02 Lt"); those parse to
a float where the centai are non-zero and an integer otherwise, the way the
2015-era `_parse_lt_amount` reads a modern page. `valiuta` is set to "Lt" so
the corpus-wide litas->euro conversion applies to these records like any
other pre-2015 declaration.

The 2000 form also fills section I's workplace lines ("Pagrindinė
darbovietė", "Pareigos", "Nepagrindinės darbovietės", "Pareigos
nepagrindinėse darbovietėse"); the 1996-1997 pages print the labels with
nothing after them. They are read as `darboviete`, `pareigos`,
`nepagrindines-darbovietes` and `pareigos-nepagrindinese-darbovietese`,
present only when the page gives a value, so the older families' records
are unchanged.
"""

from __future__ import annotations

import html as html_module
import re
from typing import Any

# A printed figure: digits (thousands sometimes spaced), on the 2000 pages
# with two decimals.
AMOUNT = r"([\d\s]+?(?:[.,]\d{1,2})?)"

# Sections II, IV and V each end in the same "Bendra suma ... punktus:" line,
# so each is anchored on the words unique to its own heading.
SECTION_TOTALS = {
    "turtas-ir-pinigines-lesos-metu-pradzioje": r"atitinkam\w*\s+met\w*\s+pradžioje",
    "kalendoriniais-metais-isigytas-turtas": r"Kalendoriniais\s+metais\s+įsigytas\s+turtas",
    "turtas-ir-pinigines-lesos-metu-pabaigoje": r"met\w*\s+pabaigoje",
}
SECTION_TOTAL_TAIL = r".*?punktus:\s*" + AMOUNT + r"\s*Lt"

# Section III. The two figures on a row are the income and the tax columns;
# "Lt" follows each on the municipal and 2000 pages and neither on the 1996
# Seimas ones.
ROW_EMPLOYMENT = re.compile(
    r"1\.\s*Susijusios\s+su\s+darbo\s+santykiais\s+pajamos"
    r"[^\d]*?" + AMOUNT + r"(?:\s*Lt)?\s+" + AMOUNT + r"(?:\s*Lt)?\s+20\.",
    re.S,
)
ROW_TOTAL = re.compile(
    r"20\.\s*Iš\s+viso:\s*" + AMOUNT + r"(?:\s*Lt)?\s+" + AMOUNT + r"(?:\s*Lt)?"
    r"\s+(?:IV\.|Kalendoriniais)",
    re.S,
)

TAX_ARREARS = re.compile(r"Mokesčių\s+nepriemoka[^:]*:\s*" + AMOUNT + r"\s*Lt", re.S)
TAX_PAYABLE = re.compile(r"Privaloma\s+sumokėti[^:]*:\s*" + AMOUNT + r"\s*Lt", re.S)

# Section I's workplace lines, between the name and the family counts. Each
# value runs to the next label; the 1996-1997 labels are "Nepagrindinė(-ės)
# darbovietė(-ės):" and a second bare "Pareigos:", the 2000 ones
# "Nepagrindinės darbovietės:" and "Pareigos nepagrindinėse darbovietėse:".
WORKPLACE = re.compile(
    r"Pagrindinė\s+darbovietė:\s*(.*?)\s*Pareigos:\s*(.*?)\s*Nepagrindin[^:]*:\s*(.*?)"
    r"\s*Pareigos[^:]*:\s*(.*?)\s*Šeimos\s+narių",
    re.S,
)
FAMILY_COUNTS = re.compile(
    r"Šeimos\s+narių\s+skaičius:\s*(\d+)\s*,\s*tarp\s+jų\s+išlaikytinių:\s*(\d+)"
    r"\s*,\s*iš\s+jų\s+iki\s+18\s+metų:\s*(\d+)",
    re.S,
)
# 1997: "Išrašą 1997 02 10 išdavė <inspekcija>". The 1996 family prints the
# same line with its Baltic characters mojibaked -- the source is CP1257 but
# the entities were emitted for Latin-1, so "Išrašą išdavė" arrives as
# "Iðraðà iðdavë" and this pattern simply does not match there. Nothing is
# lost: across 49 sampled 1996 pages that line carries a date and never an
# issuer, so the family has no issuer to read. (Re-encoding latin-1 -> cp1257
# does recover the wording, which is how that was checked.)
ISSUE_DATE = re.compile(r"(\d{4})\s+(\d{2})\s+(\d{2})")
ISSUER = re.compile(r"išdavė\s+(.+?)\s*(?:I\.|Bendrieji|$)", re.S)

QUERY_ERROR_BANNER = "Klaida užklausoje"


def clean_page_text(html: str) -> str:
    """Tags to spaces, entities resolved, whitespace collapsed.

    Deliberately text-based rather than DOM-based: the two families wrap the
    same wording in different tables -- the Seimas pages split a heading's
    numeral and its text across cells, the municipal pages keep them together
    -- but the reading order of the text is identical, so one set of patterns
    serves both. The 1996 pages also carry mojibake and a stray comment
    terminator, which a parser would have to survive anyway.
    """
    text = re.sub(r"<[^>]+>", " ", html)
    text = html_module.unescape(text)
    return re.sub(r"[\s ]+", " ", text).strip()


def _int(value: str | None) -> int | float | None:
    """A printed litas figure: an int, or a float when it carries non-zero
    centai (the 2000 pages; the 1996-1997 figures are whole litas)."""
    if not value:
        return None
    compact = re.sub(r"\s", "", value).replace(",", ".")
    if not re.fullmatch(r"\d+(?:\.\d+)?", compact):
        digits = re.sub(r"[^\d]", "", compact)
        return int(digits) if digits else None
    amount = float(compact)
    return int(amount) if amount.is_integer() else amount


def _section_total(text: str, pattern: str) -> int | None:
    match = re.search(pattern + SECTION_TOTAL_TAIL, text, re.S)
    return _int(match.group(1)) if match else None


def extract_issue_date(text: str) -> str | None:
    """The `YYYY MM DD` the extract was issued on, as ISO.

    The 1996 pages render this line's Lithuanian characters as Latin-1
    entities ("I&eth;ra&eth;&agrave; i&eth;dav&euml;") and leave an HTML
    comment terminator in the output, so the surrounding words are unreliable
    on that family and the date is matched on its own shape instead. It is the
    first such triple on the page either way.
    """
    match = ISSUE_DATE.search(text)
    if not match:
        return None
    year, month, day = match.groups()
    if not (1990 <= int(year) <= 2000 and 1 <= int(month) <= 12 and 1 <= int(day) <= 31):
        return None
    return f"{year}-{month}-{day}"


def parse_declaration(html: str) -> dict[str, Any]:
    """Read one `kpdl.htm` page into the corpus's declaration keys.

    Returns the `turto-ir-pajamu-deklaracijos` block plus an `anomalies` list
    of dicts describing anything the page contradicted about itself; callers
    turn those into anomaly events with their own election and candidate ids.
    """
    text = clean_page_text(html)
    anomalies: list[dict[str, Any]] = []

    employment = ROW_EMPLOYMENT.search(text)
    total = ROW_TOTAL.search(text)
    employment_income = _int(employment.group(1)) if employment else None
    employment_tax = _int(employment.group(2)) if employment else None
    total_income = _int(total.group(1)) if total else None
    total_tax = _int(total.group(2)) if total else None

    query_error_banner = QUERY_ERROR_BANNER in text

    def trusted(total_value, row_value, column: str):
        """A total the page's own row 1 contradicts is not a total.

        The 2000 pages print the figures to the centas but row 20 with
        the centai dropped ("10042.00 Lt" against a row 1 of
        "10042.32 Lt"), so a shortfall under one litas is the page's own
        truncation, not a contradiction, and the total stands.

        A page carrying VRK's own "Klaida užklausoje" banner reports the
        contradiction at `info`, not `warning`: the source has said in so
        many words that its query failed, so the figures below it are its
        problem and not a parse loss. That distinction is what makes
        STOP_ON_ANOMALY usable on the archive elections -- issue #85 found
        8,598 of the corpus's 8,949 anomaly events to be this one banner,
        drowning the other 24 completely.
        """
        if total_value is None or row_value is None:
            return total_value
        if row_value - total_value < 1:
            return total_value
        anomalies.append(
            {
                "eventType": "DeclarationTotalBelowItsOwnRow",
                "severity": "info" if query_error_banner else "warning",
                "detail": {
                    "column": column,
                    "row20Total": total_value,
                    "row1Employment": row_value,
                    "queryErrorBanner": query_error_banner,
                },
            }
        )
        return None

    declaration: dict[str, Any] = {
        # The 1990s form publishes turtas and piniginės lėšos summed, so the
        # modern split cannot be recovered; the combined figures are below.
        "privalomas-registruoti-turtas": None,
        "pinigines-lesos": None,
        "gautos-pajamos": trusted(total_income, employment_income, "gautos-pajamos"),
        "sumoketas-pajamu-mokestis": trusted(
            total_tax, employment_tax, "sumoketas-pajamu-mokestis"
        ),
        "gautos-pajamos-darbo-santykiu": employment_income,
        "sumoketas-pajamu-mokestis-darbo-santykiu": employment_tax,
        "mokesciu-nepriemoka": _int(m.group(1)) if (m := TAX_ARREARS.search(text)) else None,
        "privaloma-sumoketi-mokesciu-ir-sankciju": (
            _int(m.group(1)) if (m := TAX_PAYABLE.search(text)) else None
        ),
        "valiuta": "Lt",
        "israso-data": extract_issue_date(text),
    }
    for key, pattern in SECTION_TOTALS.items():
        declaration[key] = _section_total(text, pattern)

    family = FAMILY_COUNTS.search(text)
    if family:
        declaration["seimos-nariu-skaicius"] = int(family.group(1))
        declaration["islaikytiniu-skaicius"] = int(family.group(2))
        declaration["seimos-nariu-iki-18-metu"] = int(family.group(3))

    issuer = ISSUER.search(text)
    if issuer:
        declaration["israsa-isdave"] = issuer.group(1).strip() or None

    workplace = WORKPLACE.search(text)
    if workplace:
        for key, value in zip(
            (
                "darboviete",
                "pareigos",
                "nepagrindines-darbovietes",
                "pareigos-nepagrindinese-darbovietese",
            ),
            workplace.groups(),
        ):
            value = value.strip().rstrip(".").strip()
            if value:
                declaration[key] = value

    if not any(
        declaration[k] is not None
        for k in ("gautos-pajamos", "gautos-pajamos-darbo-santykiu", *SECTION_TOTALS)
    ):
        anomalies.append(
            {
                "eventType": "DeclarationPageUnreadable",
                "severity": "error",
                "detail": {"length": len(text)},
            }
        )

    return {"declaration": declaration, "anomalies": anomalies}
