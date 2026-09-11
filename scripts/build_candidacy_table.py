"""Build the one canonical candidacy table the 54-schema corpus never had.

Issue #93, measured: the full path × election matrix of the corpus holds 965
distinct dotted paths, 8 of which appear in every election — and once the
structural containers are dropped, exactly ONE substantive field is universal
(`profilis.vardas-pavarde`). Two large elections agree on about a quarter of
their schema (mean pairwise Jaccard 0.262). That was the right call for the
*scrapers* — VRK's pages really are 55 different pages — and the wrong shape
for the *output*, because everything the project set out to do ("compare
candidates across elections") reads off one row per (person, election).

This is the projector. One pass over `data/` writes:

    dist/candidacies.csv.gz   one row per candidacy, every column defined below
    dist/campaigns.csv.gz     one row per campaign-finance participant
    dist/vrk.sqlite           the same, plus elections / persons / parties /
                              party_predecessors / municipalities tables

Three rules make it trustworthy (all three are #93's):

1. **Path resolution is data or a named resolver, never ad-hoc walking.**
   Concepts that move between page eras resolve through
   `docs/concept-map.json` (same semantics as `scripts/field_coverage.py`,
   list paths fan out, first filled alternative wins); the uniform
   declaration block resolves through `scraper/shared/deklaracijos.py`; the
   five `kandidatavimas` shapes through `scraper/shared/kandidatura.py`; the
   education ordinal through `scraper/shared/education.py`; identity through
   `scripts/build_person_index.py` (pids, override merges); parties through
   `scraper/shared/parties.py`.
2. **Absence is typed.** `declaration_status` says whether a missing money
   section is "never published" or "published as archive scans";
   `education_status` distinguishes a printed decline (`Nenurodė`) from a
   blank from an election that publishes no level for anyone. A `null` alone
   never has to mean four different things again.
3. **Tested against the population.** Per-column, per-election fill rates
   are checked in (`docs/candidacy-baseline.tsv`) and this build is a gate
   against them: a new zero-fill cell, or a rate that fell more than
   `--max-drop` points, fails the run — the 2020-income shape (issue #85)
   cannot ship silently through this table.

Money columns are EUR-converted at the irrevocable changeover rate wherever
the declaration says `Lt` (`currency_rate` records the divisor), and carry
the *measure* alongside the figure — `income_measure` distinguishes the
1996–2002 net-of-tax figures from the gross eras (issue #97), and
`income_gross_eur` is the re-grossed comparable series. `campaign_key` is
the one correct donation-grouping key (`campaignKey`, present on every
campaign entry; grouping donation lists any other way double-counts by up to
1,182× — the 2015 municipal general, whose largest campaign is shared by
2,414 candidacies).

The `normalized` layer is not touched: this adds a derived layer and
rewrites nothing.

Run from the repo root:

    python scripts/build_candidacy_table.py                    # build + gate
    python scripts/build_candidacy_table.py --update-baseline  # after a deliberate change
    python scripts/build_candidacy_table.py 2024-seimo         # a subset, no gate
"""

from __future__ import annotations

import argparse
import csv
import gzip
import io
import json
import sqlite3
import sys
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable, Iterator

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from scraper.shared import education  # noqa: E402
from scraper.shared.conviction_details import teistumas  # noqa: E402
from scraper.shared.deklaracijos import (  # noqa: E402
    CURRENCY_LITAS,
    INCOME_EMPLOYMENT,
    LITAS_PER_EURO,
    deklaracijos_valiuta,
    deklaruotas_turtas,
    deklaruotos_pajamos,
    deklaruotos_pajamos_bruto,
    mokescio_matas,
    pajamu_matas,
)
from scraper.shared.kandidatura import kandidatura  # noqa: E402
from scraper.shared.municipalities import entries as municipality_entries  # noqa: E402
from scraper.shared.parties import partija  # noqa: E402

import build_person_index as identity  # noqa: E402
import field_coverage  # noqa: E402

CONCEPT_MAP = Path("docs/concept-map.json")
BASELINE = Path("docs/candidacy-baseline.tsv")

#: The one election whose declarations exist only as archived page scans,
#: never as parseable text — a typed absence, not a gap (issue #97).
SCANNED_DECLARATIONS = frozenset({"2002-prezidento"})

#: VRK's own verified data-entry errors: the stored value is byte-faithful to
#: the page, and the page itself is wrong — each entry here was re-traced to
#: the retained HTML in `samples-full/` and fails an internal consistency
#: check of its own declaration. They would dominate any ranking, so the row
#: is flagged (`quality_flags: saltinio-klaida`), never filtered (issue #97).
#: An outlier that is merely large (Karbauskis's 16.4M, Romanov's 52M) is
#: not here: big and consistent is data.
SOURCE_ERRORS: dict[tuple[str, str], str] = {
    ("2000-kovo-19-savivaldybiu-tarybu", "budrys-kazimieras-algirdas-89555"): (
        "the page prints income 334,017,647.47 Lt against 11,283.19 Lt employment"
        " income and 66,034.57 Lt year-end wealth on the same form"
    ),
    ("2000-kovo-19-savivaldybiu-tarybu", "pilipaviciene-stefa-93146"): (
        "the page prints income 172,087,745.59 Lt against 13,896.77 Lt employment"
        " income and 19,900 Lt wealth at both ends of the year"
    ),
    ("1997-kovo-23-savivaldybiu-tarybu", "korotajeva-nina"): (
        "the page prints year-end wealth 355,397,021 Lt against 3,553 Lt at the"
        " start of the year and zero declared income"
    ),
}

COLUMNS = (
    "person_id",
    "election_id",
    "election_date",
    "election_kind",
    # The name and the term, in the flat file itself: `candidacies.csv.gz` is
    # the "Start here" asset and carried the slug alone, with no elections
    # table beside it, so the `COALESCE(parent, id)` grouping the docs
    # prescribe was unavailable to a CSV reader for the 1,119 rows across 28
    # elections that need it (issue #156).
    "election_name",
    "election_parent",
    "candidate_id",
    "candidate_name",
    "source_url",
    "birth_date",
    "birth_place",
    "role",
    "constituency",
    "municipality",
    "municipality_id",
    "list_name",
    "list_position",
    "post_election_position",
    "list_movement",
    "party_id",
    "party_name_raw",
    "nomination_kind",
    "elected",
    "elected_council",
    "elected_mayor",
    "preference_votes",
    "preference_votes_measure",
    "list_votes",
    "constituency_number",
    "constituency_votes",
    "constituency_round",
    "constituency_place",
    "constituency_votes_pct",
    "votes_source",
    "education_status",
    "education_level",
    "education_level_rank",
    "education_higher",
    "education_unfinished",
    "education_degree",
    "education_entries",
    "declaration_status",
    "declared_currency",
    "currency_rate",
    "declaration_year",
    "assets_registered_eur",
    "securities_eur",
    "cash_eur",
    "loans_given_eur",
    "loans_received_eur",
    "income_eur",
    "income_tax_eur",
    "self_employment_income_eur",
    "self_employment_deductions_eur",
    "asset_sale_income_eur",
    "asset_acquisition_cost_eur",
    "assets_total_eur",
    "assets_measure",
    "income_measure",
    "income_gross_eur",
    "tax_measure",
    "income_floor_only",
    "quality_flags",
    "campaign_key",
    "campaign_status",
    "conviction_status",
    "conviction_details",
)

#: Not gated: columns that are empty by design on nearly every row, so a
#: zero on a small election means nothing. `conviction_details` fills on
#: ~1.4 % of the corpus (the declarers); its recovery is pinned by the
#: `teistumas` tests and the conviction_status column instead.
UNGATED_COLUMNS = frozenset({"quality_flags", "conviction_details"})

#: The 26 elections whose records carry a vote or rating figure (issue
#: #133, measured 2026-09-08): the 2000-2004 static sites print them on the
#: candidate's own pages, the 2007-2015 trees were joined by issue #99, the
#: 1996-1999 archive family carries them in its candidacy list. Every other
#: election publishes its results on pages the corpus does not read, so its
#: vote columns are a parser gap, not an upstream absence.
VOTES_JOINED = frozenset(
    {
        "1996-spalio-20-seimo",
        "1997-kovo-23-seimo-pakartotiniai",
        "1997-gruodzio-21-seimo-pakartotiniai",
        "1998-kovo-22-seimo-pakartotiniai",
        "1998-lapkricio-15-seimo-pakartotiniai",
        "1999-kovo-21-seimo-pakartotiniai",
        "2000-kovo-19-savivaldybiu-tarybu",
        "2000-seimo",
        "2002-gruodzio-22-savivaldybiu-tarybu",
        "2002-prezidento",
        "2003-birzelio-15-seimo-nauji",
        "2004-ep",
        "2004-prezidento",
        "2004-seimo",
        "2007-spalio-7-seimo-dzukija",
        "2008-seimo",
        "2009-lapkricio-15-seimo-silale-silute-vilnius-salcininkai",
        "2011-vasario-13-seimo-marijampole",
        "2011-vasario-27-savivaldybiu",
        "2012-seimo",
        "2013-kovo-3-seimo-birzai-zarasai-ukmerge",
        "2015-birzelio-7-pakartotiniai-sirvintos-trakai",
        "2015-birzelio-21-pakartotiniai-silutes",
        "2015-birzelio-7-seimo-varena-eisiskes",
        "2015-kovo-1-savivaldybiu",
        "2015-kovo-1-seimo-zirmunai",
    }
)

#: Of those, the two whose results tree carries the list's own total beside
#: the candidate's preference votes.
LIST_VOTES_JOINED = frozenset({"2000-kovo-19-savivaldybiu-tarybu", "2002-gruodzio-22-savivaldybiu-tarybu"})

#: A general whose constituency round-one pages were not joined (the 2004
#: tree rows candidates under ids the candidate pages do not carry --
#: OUTPUT_SCHEMA); the preference votes are.
CONSTITUENCY_VOTES_NOT_JOINED = frozenset({"2004-seimo"})

#: The Seimas by-elections whose 2016-era cards name the constituency
#: without its number ("Anykščių-Panevėžio", "Zanavykų", "Žirmūnų").
CONSTITUENCY_NUMBER_NOT_PRINTED = frozenset(
    {
        "2017-balandzio-23-seimo-anyksciai-panevezys",
        "2018-rugsejo-16-seimo-zanavykai",
        "2019-rugsejo-8-seimo",
    }
)

VOTE_COLUMNS = (
    "preference_votes",
    "preference_votes_measure",
    "list_votes",
    "constituency_votes",
    "constituency_round",
    "constituency_place",
    "constituency_votes_pct",
    "votes_source",
)

#: The eight Seimas *generals* — every other seimo-kind election is a
#: single-mandate by-election with no party list on the ballot. Derived from
#: the registry rather than listed, because a hand copy is only right until
#: the next election is added: `_known_zero_note` reads a seimo-kind election
#: that is not in this set as a by-election, so a well-formed 2027-seimo
#: would have been told it had no party list on the ballot — the note under
#: which `list_name`, `list_position` and `post_election_position` are
#: legitimately zero, three columns filled on 1,721 of 2024-seimo's 1,740
#: rows (issue #165). `parent` is the general whose term a by-election,
#: repeat or re-vote fills (issue #122), so the generals are the ones without
#: one; the derivation is a no-op on today's registry.
def _seimas_generals(registry: Iterable[dict[str, Any]]) -> frozenset[str]:
    return frozenset(e["id"] for e in registry if e["kind"] == "seimo" and not e.get("parent"))


SEIMAS_GENERALS = _seimas_generals(
    identity.load_registry(Path(__file__).resolve().parents[1] / "scraper" / "elections.json")
)

#: The presidential elections whose cards print a "Kandidatą iškėlė" row.
#: 2024's does and no earlier one does — verified in the retained anketa
#: pages — so the blanket rule that presidential candidates self-nominate and
#: the pages name no nominator was a false excuse standing over three columns
#: filled on all 8 of 2024's rows (four parties, four genuine
#: self-nominations). Found by the invariant issue #165 added, not by the
#: issue itself.
PRESIDENTIAL_NOMINATOR_PUBLISHED = frozenset({"2024-prezidento"})

#: Elections whose candidates have no campaign-participant section at all —
#: VRK ran the era's campaign finance through the parties (2008, 2011) or
#: publishes no participant pages for the election (the 2023/2024 ones).
NO_CAMPAIGN_PAGES = frozenset(
    {
        "2008-seimo",
        "2011-vasario-27-savivaldybiu",
        "2023-geguzes-7-visagino-mero",
        "2024-ep",
        "2024-prezidento",
    }
)

#: Elections measured to publish no post-election list ranking anywhere —
#: no root porinkiminisNumerisSarase, no profile porinkiminis key, no
#: postElectionPosition. Seimas by-elections and the mayoral races are
#: covered by their own rules; these are the generals and EP elections that
#: simply never printed one.
#:
#: This list was written against the corpus as it stood for issue #93 and
#: went stale under it: issue #99's results join landed afterwards and
#: recovered the ranking for six of the eleven — 35,507 values whose baseline
#: rows had gone on saying VRK published none (issue #165). The six are gone
#: from the set, so the excuse no longer stands ready to cover their loss;
#: `ClassificationsAgreeWithTheBaseline` in the tests now measures every id
#: here against the checked-in fill rates, so the next join cannot rot it in
#: silence.
POST_RANKING_ABSENT = frozenset(
    {
        "1997-kovo-23-savivaldybiu-tarybu",
        "1997-birzelio-29-svenciniu-tarybos-pakartotiniai",
        "2007-vasario-25-savivaldybiu",
        "2009-ep",
        "2014-ep",
    }
)

#: Elections measured to state no declaration year anywhere: no "(YYYY m.)"
#: in any section heading and no period sentence in the closing note.
DECLARATION_YEAR_ABSENT = frozenset(
    {
        "2004-ep",
        "2004-prezidento",
        "2004-seimo",
        "2005-lapkricio-20-seimo-kedainiai",
        "2007-spalio-7-seimo-dzukija",
        "2007-vasario-25-savivaldybiu",
        "2009-ep",
        "2009-lapkricio-15-seimo-silale-silute-vilnius-salcininkai",
        "2009-prezidento",
        "2011-vasario-13-seimo-marijampole",
        "2011-vasario-27-savivaldybiu",
        "2014-ep",
        "2014-prezidento",
        "2015-birzelio-21-pakartotiniai-silutes",
        "2015-birzelio-7-pakartotiniai-sirvintos-trakai",
        "2015-kovo-1-savivaldybiu",
        "2015-lapkricio-8-telsiu-mero",
        "2016-seimo",
        "2017-balandzio-23-seimo-anyksciai-panevezys",
        "2018-rugsejo-16-seimo-zanavykai",
        "2019-rugsejo-8-seimo",
        "2020-seimo",
    }
)

CAMPAIGN_COLUMNS = (
    "campaign_key",
    "election_id",
    "label",
    "status",
    "candidacies",
    "donations_total_eur",
)

DECLARATION_TO_COLUMN = (
    ("privalomas-registruoti-turtas", "assets_registered_eur"),
    ("vertybiniai-popieriai-meno-kuriniai-juvelyriniai-dirbiniai", "securities_eur"),
    ("pinigines-lesos", "cash_eur"),
    ("suteiktos-paskolos", "loans_given_eur"),
    ("gautos-paskolos", "loans_received_eur"),
    ("individualios-veiklos-pajamos", "self_employment_income_eur"),
    ("individualios-veiklos-atskaitymai", "self_employment_deductions_eur"),
    ("turto-pardavimo-pajamos", "asset_sale_income_eur"),
    ("turto-isigijimo-kaina", "asset_acquisition_cost_eur"),
)


# The concept-map value resolver lives in field_coverage (`concept_value`),
# beside the (present, filled) resolver whose semantics it shares.
concept_value = field_coverage.concept_value


# ---------------------------------------------------------------------------
# Per-record projection
# ---------------------------------------------------------------------------


def _fold_token(text: Any) -> str | None:
    if not isinstance(text, str) or not text.strip():
        return None
    decomposed = unicodedata.normalize("NFD", text.strip().casefold())
    return "".join(ch for ch in decomposed if unicodedata.category(ch) != "Mn")


def _source_url(record: dict[str, Any]) -> str | None:
    source = record.get("source")
    if isinstance(source, str):
        return source
    if isinstance(source, list):
        return next((s for s in source if isinstance(s, str)), None)
    if isinstance(source, dict):
        return next((s for s in source.values() if isinstance(s, str)), None)
    return None


def _eur(value: Any, rate: float | None) -> float | None:
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        return None
    return round(float(value) / (rate or 1.0), 2)


def _campaign_entry(record: dict[str, Any]) -> tuple[str | None, str | None, str | None, dict | None]:
    """(campaign_key, status, label, normalized entry) for the record's own
    campaign participant. Every record with the section carries exactly one
    campaign entry, and `campaignKey` is present on all of them (measured:
    20,199 of 20,199)."""
    raw = (record.get("rawData") or {}).get("politinesKampanijosDalyvioDuomenys")
    campaigns = raw.get("campaigns") if isinstance(raw, dict) else None
    key = label = None
    if isinstance(campaigns, list) and campaigns and isinstance(campaigns[0], dict):
        key = campaigns[0].get("campaignKey")
        label = campaigns[0].get("campaignLabel")
    normalized = (record.get("normalized") or {}).get(
        "politines-kampanijos-dalyvio-duomenys"
    )
    status = entry = None
    if isinstance(normalized, list) and normalized and isinstance(normalized[0], dict):
        entry = normalized[0]
        status = _fold_token(entry.get("statusas"))
    return key, status, label, entry


def campaign_donation_total_eur(entry: dict[str, Any] | None) -> float | None:
    """The campaign's accepted-donations total ("Iš viso" of the accepted
    section — `gautos-ir-priimtos-aukos` from 2012 on, the 2009–2011 era's
    one `aukotoju-sarasas`), EUR-converted. VRK's own sum, read from
    whichever of the era shapes the block has; None where the campaign
    publishes no donation data (the Atstovaujamasis participants — financed
    through the party's campaign, not "no money")."""
    if not isinstance(entry, dict):
        return None
    sections = entry.get("aukos-pagal-sekcija")
    sections = sections if isinstance(sections, dict) else {}
    section = next(
        (
            sections[key]
            for key in ("gautos-ir-priimtos-aukos", "aukotoju-sarasas")
            if isinstance(sections.get(key), dict)
        ),
        None,
    )
    if section is None:
        return None
    totals = section.get("totals")
    if isinstance(totals, dict) and isinstance(totals.get("is-viso"), (int, float)):
        return round(float(totals["is-viso"]), 2)
    for row in section.get("suvestine") or []:
        if isinstance(row, dict) and row.get("label") == "Iš viso":
            if isinstance(row.get("amountEur"), (int, float)):
                return round(float(row["amountEur"]), 2)
            if isinstance(row.get("amountLt"), (int, float)):
                return round(float(row["amountLt"]) / LITAS_PER_EURO, 2)
    return None


def project_record(
    record: dict[str, Any],
    election: dict[str, Any],
    paths_by_concept: dict[str, dict[str, str | list[str]]],
) -> dict[str, Any]:
    """One candidacy row (COLUMNS minus person_id, which needs the corpus)."""
    election_id = election["id"]

    def concept(name: str) -> Any:
        path = paths_by_concept.get(name, {}).get(election_id)
        return concept_value(record, path) if path is not None else None

    row: dict[str, Any] = dict.fromkeys(COLUMNS)
    row["election_id"] = election_id
    row["election_date"] = election["date"]
    row["election_kind"] = election["kind"]
    row["election_name"] = election.get("name") or election.get("shortName")
    # The general election whose term this one fills, or the election itself:
    # `election_parent` is never null, so grouping by it needs no COALESCE.
    row["election_parent"] = election.get("parent") or election_id
    row["candidate_id"] = record.get("candidateId")
    row["candidate_name"] = record.get("candidateName")
    row["source_url"] = _source_url(record)
    row["birth_date"] = concept("gimimo-data")
    row["birth_place"] = concept("gimimo-vieta")

    candidacy = kandidatura(record, election["kind"])
    row["role"] = candidacy["vaidmuo"]
    # One name per district across the four label eras, the number beside
    # it (scraper/shared/apygardos.py, issue #133); the label as published
    # stays in the record file.
    row["constituency"] = candidacy["apygarda"]
    row["constituency_number"] = candidacy["apygardos-numeris"]
    # The official name and the registry id (scraper/municipalities.json,
    # issue #137): the eras' own wordings -- "Vilniaus miesto" on five
    # elections, "Vilniaus miesto savivaldybė" on three -- used to ship as
    # two municipalities. The published form stays in the record file.
    row["municipality"] = candidacy["savivaldybe"]
    row["municipality_id"] = candidacy["savivaldybe-id"]
    row["list_name"] = candidacy["sarasas"]
    row["list_position"] = candidacy["numeris-sarase"]
    row["post_election_position"] = candidacy["porinkiminis-numeris"]
    # Positive = the preference votes moved the candidate up the list. For
    # the 2016-2025 elections, which publish no vote counts, this pair is
    # the only preference signal there is (issue #133).
    if row["list_position"] is not None and row["post_election_position"] is not None:
        row["list_movement"] = row["list_position"] - row["post_election_position"]
    # `elected` is any office on the ballot; the two per-office columns are
    # what a council-and-mayor candidacy needs (issue #140: 448 council
    # winners who lost the mayoralty shipped as role=meras, elected=1).
    row["elected"] = candidacy["isrinktas"]
    row["elected_council"] = candidacy["isrinktas-tarybos-nariu"]
    row["elected_mayor"] = candidacy["isrinktas-meru"]

    # The electoral result (issue #133): the candidate's preference votes on
    # the list, the list's own total where the tree carries it, and the
    # single-winner race's last round contested -- a Seimas constituency, or
    # the country for a presidential candidate.
    row["preference_votes"] = candidacy["pirmumo-balsai"]
    row["preference_votes_measure"] = candidacy["pirmumo-balsu-matas"]
    row["list_votes"] = candidacy["sarasas-balsai"]
    row["constituency_votes"] = candidacy["apygardos-balsai"]
    row["constituency_round"] = candidacy["apygardos-turas"]
    row["constituency_place"] = candidacy["apygardos-vieta"]
    row["constituency_votes_pct"] = candidacy["apygardos-procentai"]
    row["votes_source"] = candidacy["balsu-saltinis"]

    party = partija(record, election_id)
    row["party_id"] = party["partija-id"]
    row["party_name_raw"] = party["partija-vardas-raw"]
    row["nomination_kind"] = party["tipas"]

    edu = education.issilavinimas(record, election_id)
    row["education_status"] = edu["busena"]
    row["education_level"] = edu["lygis"]
    row["education_level_rank"] = edu["rangas"]
    row["education_higher"] = edu["aukstasis"]
    row["education_unfinished"] = edu["nebaigtas"]
    row["education_degree"] = edu["laipsnis"]
    row["education_entries"] = edu["irasai"] or None

    declaration = (record.get("normalized") or {}).get("turto-ir-pajamu-deklaracijos")
    raw_declaration = (record.get("rawData") or {}).get("turtoIrPajamuDeklaracijos")
    if isinstance(declaration, dict):
        row["declaration_status"] = "yra"
        currency = deklaracijos_valiuta(declaration)
        rate = LITAS_PER_EURO if currency == CURRENCY_LITAS else 1.0
        row["declared_currency"] = currency
        row["currency_rate"] = rate
        row["declaration_year"] = declaration.get("deklaracijos-metai")
        for key, column in DECLARATION_TO_COLUMN:
            row[column] = _eur(declaration.get(key), rate)
        income = deklaruotos_pajamos(declaration)
        row["income_eur"] = _eur(income["suma"], rate)
        row["income_floor_only"] = income["saltinis"] == INCOME_EMPLOYMENT
        tax_key = (
            "sumoketas-pajamu-mokestis-darbo-santykiu"
            if row["income_floor_only"]
            else "sumoketas-pajamu-mokestis"
        )
        row["income_tax_eur"] = _eur(declaration.get(tax_key), rate)
        turtas = deklaruotas_turtas(declaration)
        row["assets_total_eur"] = _eur(turtas["suma"], rate)
        row["assets_measure"] = turtas["matas"]
        row["income_measure"] = pajamu_matas(declaration, raw_declaration)
        row["tax_measure"] = mokescio_matas(declaration, raw_declaration)
        row["income_gross_eur"] = _eur(
            deklaruotos_pajamos_bruto(declaration, row["income_measure"]), rate
        )
    else:
        row["declaration_status"] = (
            "archyvo-skenai" if election_id in SCANNED_DECLARATIONS else "nera"
        )

    flags = []
    error = SOURCE_ERRORS.get((election_id, record.get("candidateId")))
    if error is not None:
        flags.append("saltinio-klaida")
    row["quality_flags"] = ";".join(flags) or None

    key, status, _, _ = _campaign_entry(record)
    row["campaign_key"] = key
    row["campaign_status"] = status

    conviction = teistumas((record.get("normalized") or {}).get("anketa"))
    row["conviction_status"] = conviction["busena"]
    if conviction["irasai"] or conviction["aprasas"]:
        row["conviction_details"] = {
            "irasai": conviction["irasai"],
            "aprasas": conviction["aprasas"],
        }
    return row


# ---------------------------------------------------------------------------
# The corpus pass
# ---------------------------------------------------------------------------


def election_records(data_root: Path, election_id: str) -> Iterator[dict[str, Any]]:
    for path in sorted((data_root / election_id).glob("*.json")):
        if path.name == "anomalies.jsonl":
            continue
        yield json.loads(path.read_text(encoding="utf-8"))


def build(
    repo_root: Path, election_ids: list[str] | None = None
) -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    """Returns (rows, campaigns, elections-present, stats)."""
    data_root = repo_root / "data"
    concept_map = json.loads((repo_root / CONCEPT_MAP).read_text(encoding="utf-8"))
    paths_by_concept = field_coverage.concept_paths(concept_map)
    registry = identity.load_registry(repo_root / "scraper" / "elections.json")
    registry_by_id = {entry["id"]: entry for entry in registry}
    overrides = identity.load_overrides(repo_root / "scraper" / "person_overrides.json")

    present = sorted(
        child.name
        for child in data_root.iterdir()
        if child.is_dir() and (election_ids is None or child.name in election_ids)
    )
    unregistered = [eid for eid in present if eid not in registry_by_id]
    if unregistered:
        raise SystemExit(
            "election(s) missing from scraper/elections.json: " + ", ".join(unregistered)
        )

    rows: list[dict[str, Any]] = []
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    campaigns: dict[str, dict[str, Any]] = {}
    donation_naive = Counter()
    donation_campaigns: dict[str, float] = {}

    for eid in present:
        election = registry_by_id[eid]
        for record in election_records(data_root, eid):
            row = project_record(record, election, paths_by_concept)
            index = len(rows)
            rows.append(row)
            name = identity.normalize_name(record.get("candidateName"))
            birth = identity.birth_key_of(record)
            grouped[identity.person_key(name, birth)].append(
                {"election": eid, "row": index, "birthKey": birth}
            )

            key, status, label, entry = _campaign_entry(record)
            if key is not None:
                campaign = campaigns.setdefault(
                    key,
                    {
                        "campaign_key": key,
                        "election_id": eid,
                        "label": label,
                        "status": status,
                        "candidacies": 0,
                        "donations_total_eur": None,
                    },
                )
                campaign["candidacies"] += 1
                total = campaign_donation_total_eur(entry)
                if total is not None:
                    donation_naive[eid] += total
                    campaign["donations_total_eur"] = total
                    donation_campaigns[key] = total

    order = {entry["id"]: i for i, entry in enumerate(registry)}
    former, unmatched = identity.apply_merges(grouped, overrides, order)
    if unmatched and election_ids is None:
        print(
            f"warning: {len(unmatched)} override key(s) match no person on this corpus",
            file=sys.stderr,
        )

    pid_of_key: dict[str, str] = {}
    persons: list[dict[str, Any]] = []
    for key, fragments in grouped.items():
        pid = identity.person_pid(key)
        if pid in pid_of_key:
            raise ValueError(f"pid collision: {key!r} and {pid_of_key[pid]!r}")
        pid_of_key[pid] = key
        fragments.sort(key=lambda f: order.get(f["election"], len(order)))
        for fragment in fragments:
            rows[fragment["row"]]["person_id"] = pid
        last_row = rows[fragments[-1]["row"]]
        birth = next(
            (f["birthKey"] for f in reversed(fragments) if f["birthKey"] and not f["birthKey"].startswith("~")),
            next((f["birthKey"] for f in reversed(fragments) if f["birthKey"]), None),
        )
        persons.append(
            {
                "person_id": pid,
                "name": last_row["candidate_name"],
                "birth_key": birth,
                "candidacies": len(fragments),
                "elections": len({f["election"] for f in fragments}),
                "merged_keys": len(former.get(key, [])) or None,
            }
        )

    stats = {
        "records": len(rows),
        "elections": len(present),
        "persons": len(persons),
        "campaigns": len(campaigns),
        "donations_naive_eur": {e: round(v, 2) for e, v in donation_naive.items()},
        "donations_deduplicated_eur": round(sum(donation_campaigns.values()), 2),
        "elections_present": present,
    }
    elections_table = [
        {**registry_by_id[eid], "records": sum(1 for r in rows if r["election_id"] == eid)}
        for eid in present
    ]
    return rows, campaigns, elections_table, stats | {"persons_rows": persons}


# ---------------------------------------------------------------------------
# Outputs
# ---------------------------------------------------------------------------


def _cell(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "1" if value else "0"
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    return str(value)


def write_csv_gz(path: Path, columns: tuple[str, ...], rows: list[dict[str, Any]]) -> None:
    """Write `rows` as a gzipped CSV, streamed into the compressor.

    The table used to be built whole in a StringIO, then `getvalue()`, then
    `encode()` -- three copies of an 80 MB CSV, 572 MB of this script's
    1,056 MB peak, and the same spike in every release build, which calls
    this while `rows` is still live (issue #154). Row order, the encoding
    and the header's mtime are unchanged, so the output is too.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "wb") as raw:
        # mtime=0 keeps the archive byte-reproducible across rebuilds.
        with gzip.GzipFile(fileobj=raw, mode="wb", mtime=0) as compressed:
            with io.TextIOWrapper(compressed, encoding="utf-8", newline="") as text:
                writer = csv.writer(text, lineterminator="\n")
                writer.writerow(columns)
                for row in rows:
                    writer.writerow([_cell(row.get(column)) for column in columns])


def _sqlite_type(column: str) -> str:
    if column.endswith(("_eur", "_rate", "_pct")):
        return "REAL"
    if column.endswith(("_rank", "_position", "_year", "_votes", "_round", "_place", "_number", "_movement")) or column in {
        "elected",
        "elected_council",
        "elected_mayor",
        "education_higher",
        "education_unfinished",
        "income_floor_only",
        "candidacies",
        "elections",
        "records",
        "merged_keys",
    }:
        return "INTEGER"
    return "TEXT"


def _sqlite_value(value: Any) -> Any:
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    return value


def write_sqlite(
    path: Path,
    rows: list[dict[str, Any]],
    campaigns: dict[str, dict[str, Any]],
    elections_table: list[dict[str, Any]],
    persons: list[dict[str, Any]],
    parties_path: Path,
    meta: dict[str, str] | None = None,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.unlink(missing_ok=True)
    connection = sqlite3.connect(path)
    try:

        def create(table: str, columns: tuple[str, ...], data: list[dict[str, Any]]) -> None:
            spec = ", ".join(f'"{c}" {_sqlite_type(c)}' for c in columns)
            connection.execute(f'CREATE TABLE "{table}" ({spec})')
            connection.executemany(
                f'INSERT INTO "{table}" VALUES ({", ".join("?" * len(columns))})',
                ([_sqlite_value(row.get(c)) for c in columns] for row in data),
            )

        create("candidacies", COLUMNS, rows)
        create("campaigns", CAMPAIGN_COLUMNS, sorted(campaigns.values(), key=lambda c: (c["election_id"], c["campaign_key"])))
        # The registry as a table. `parent` is the general election whose
        # term a by-election, repeat or re-vote fills (NULL for a general),
        # so COALESCE(parent, id) is the term key (issue #122).
        create(
            "elections",
            ("id", "date", "kind", "parent", "name", "shortName", "records"),
            elections_table,
        )
        create(
            "persons",
            ("person_id", "name", "birth_key", "candidacies", "elections", "merged_keys"),
            persons,
        )
        # The municipality registry as a table (issue #137): one row per
        # body, `until` set on the two the 2000 reform dissolved, so
        # candidacies.municipality_id joins to an official name and a kind.
        create(
            "municipalities",
            ("municipality_id", "name", "kind", "until"),
            [
                {"municipality_id": municipality_id, "name": data["name"], "kind": data["kind"], "until": data.get("until")}
                for municipality_id, data in sorted(municipality_entries().items())
            ],
        )
        registry = json.loads(parties_path.read_text(encoding="utf-8"))["entries"]
        create(
            "parties",
            ("party_id", "name", "short_name", "type"),
            [
                {
                    "party_id": party_id,
                    "name": data["name"],
                    "short_name": data.get("shortName"),
                    "type": data["type"],
                }
                for party_id, data in sorted(registry.items())
            ],
        )
        # The lineage the registry records (issue #123): one row per
        # (successor, predecessor) link -- the merged parties behind TS-LKD,
        # the committee behind the Vieningas Kaunas party -- so a query can
        # roll a nominator up with what it continues (a recursive CTE over
        # this table). The links form a forest: one successor per party_id
        # on the right-hand side.
        create(
            "party_predecessors",
            ("party_id", "predecessor_id"),
            [
                {"party_id": party_id, "predecessor_id": predecessor}
                for party_id, data in sorted(registry.items())
                for predecessor in data.get("predecessors", [])
            ],
        )
        for index in (
            "candidacies(person_id)",
            "candidacies(election_id)",
            "candidacies(party_id)",
            "candidacies(campaign_key)",
            "campaigns(campaign_key)",
        ):
            connection.execute(f"CREATE INDEX idx_{index.replace('(', '_').replace(')', '')} ON {index}")
        if meta:
            # What this file is, readable without the repository (issue #156).
            connection.execute("CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT)")
            connection.executemany("INSERT INTO meta VALUES (?, ?)", sorted(meta.items()))
            version = meta.get("schemaVersion")
            if version and version.isdigit():
                connection.execute(f"PRAGMA user_version = {int(version)}")
        connection.commit()
    finally:
        connection.close()


# ---------------------------------------------------------------------------
# The fill gate (rule 3)
# ---------------------------------------------------------------------------


def measure_cells(rows: list[dict[str, Any]]) -> list[field_coverage.Cell]:
    per_election: dict[str, int] = Counter()
    filled: dict[tuple[str, str], int] = Counter()
    for row in rows:
        eid = row["election_id"]
        per_election[eid] += 1
        for column in COLUMNS:
            if column in UNGATED_COLUMNS:
                continue
            if field_coverage.is_filled(row.get(column)):
                filled[(column, eid)] += 1
    # Every row carries every column, so `key_present` is the row count: an
    # empty cell is a value the projection could not derive, never a key the
    # writer forgot.
    return sorted(
        (
            field_coverage.Cell(
                column, eid, per_election[eid], per_election[eid], filled[(column, eid)]
            )
            for eid in per_election
            for column in COLUMNS
            if column not in UNGATED_COLUMNS
        ),
        key=lambda cell: (cell.concept, cell.election),
    )


#: Why a cell is legitimately empty, applied when --update-baseline meets a
#: new zero: (column, predicate over the registry entry, note). Anything not
#: covered here stays `unexplained` and the gate demands a human answer.
#: Every rule is an upstream absence except the vote columns' parser gaps,
#: which say so (issue #133: the results exist on vrk.lt and are not read).
def _known_zero_note(column: str, election: dict[str, Any]) -> field_coverage.Baseline | None:
    eid, kind, date = election["id"], election["kind"], election["date"]
    campaign_era = date >= "2007-10"  # campaign-finance pages exist from the 2007 Dzūkija by-election on
    seimas_by_election = kind == "seimo" and eid not in SEIMAS_GENERALS
    no_list = kind in {"prezidento", "mero"} or seimas_by_election
    single_winner_race = kind in {"seimo", "prezidento"}
    if column == "list_movement":
        # Empty exactly where the post-election ranking is.
        return _known_zero_note("post_election_position", election)
    if column in VOTE_COLUMNS and eid not in VOTES_JOINED:
        return field_coverage.Baseline(
            0.0,
            "parser-gap",
            "no vote figures are joined for this election: VRK publishes its results on"
            " pages the corpus does not read (issue #133; VOTES_JOINED lists the 26 that carry them)",
        )
    rules: list[tuple[bool, str]] = [
        (column in {"preference_votes", "preference_votes_measure"} and no_list, "no list on the ballot, so no preference votes"),
        (column == "list_votes" and no_list, "no list on the ballot"),
        (column == "list_votes" and eid not in LIST_VOTES_JOINED, "PARSER-GAP: the list's own total is on the results pages and was not joined; only the 2000 and 2002 municipal trees carry it beside the candidate's preference votes"),
        (column in {"constituency_votes", "constituency_round", "constituency_place", "constituency_votes_pct"} and not single_winner_race, "no single-winner race on this ballot"),
        (column in {"constituency_votes", "constituency_round", "constituency_place", "constituency_votes_pct"} and eid in CONSTITUENCY_VOTES_NOT_JOINED, "PARSER-GAP: the constituency round pages of this tree row candidates under ids the candidate pages do not carry, and were not joined (OUTPUT_SCHEMA)"),
        (column == "constituency_votes_pct" and date < "2000", "the archive's round pages print votes and place, never a share"),
        (column == "constituency_place" and kind == "prezidento", "the presidential results pages print votes and shares, never a place"),
        (column == "constituency_number" and eid in CONSTITUENCY_NUMBER_NOT_PRINTED, "the 2017-2019 by-election cards print the constituency's name without its number"),
        (column in {"constituency", "constituency_number"} and kind != "seimo", "not a Seimas election; no single-mandate constituency"),
        (column in {"municipality", "municipality_id"} and kind not in {"savivaldybiu", "mero"}, "not a municipal or mayoral election"),
        (column == "elected_council" and kind != "savivaldybiu", "no council seat on this ballot"),
        (column == "elected_mayor" and kind not in {"savivaldybiu", "mero"}, "no mayoral seat on this ballot"),
        (column == "elected_mayor" and kind == "savivaldybiu" and date < "2015", "no directly elected mayor before the 2015 municipal general; the council alone was on the ballot"),
        (column in {"list_name", "list_position", "post_election_position"} and kind == "prezidento", "presidential candidates stand on no list"),
        (column in {"list_name", "list_position", "post_election_position"} and seimas_by_election, "a single-mandate Seimas by-election; no party list on the ballot"),
        (column in {"list_name", "list_position"} and kind == "mero", "the mayoral card prints its Sąrašas row empty (verified upstream)"),
        (column == "post_election_position" and (kind == "mero" or eid in POST_RANKING_ABSENT), "VRK publishes no post-election list ranking for this election"),
        (column in {"party_id", "party_name_raw", "nomination_kind"} and kind == "prezidento" and eid not in PRESIDENTIAL_NOMINATOR_PUBLISHED, "the presidential cards of this era name no nominator"),
        (column in {"campaign_key", "campaign_status"} and not campaign_era, "no campaign-finance pages before the 2007-10 Dzūkija by-election"),
        (column in {"campaign_key", "campaign_status"} and eid in NO_CAMPAIGN_PAGES, "VRK publishes no campaign-participant section for this election's candidates"),
        (column in {"education_level", "education_level_rank", "education_higher", "education_unfinished"} and eid in education.LEVEL_NOT_PUBLISHED, "the election publishes no education level for anyone (education_status: neskelbta)"),
        (column in {"education_degree", "education_entries"} and eid in {"2002-prezidento", "2004-prezidento"}, "no questionnaire published at all"),
        (column == "education_entries" and eid in {"2000-kovo-19-savivaldybiu-tarybu", "2002-gruodzio-22-savivaldybiu-tarybu"}, "the form asks the level as one answer (issilavinimas.aprasas); the entry list is structurally empty"),
        (column == "education_degree" and eid in {"1998-kovo-22-seimo-pakartotiniai", "2002-gruodzio-22-savivaldybiu-tarybu"}, "the card asks no degree question"),
        (
            column == "education_degree"
            and eid
            in {
                "1997-birzelio-29-svenciniu-tarybos-pakartotiniai",
                "2015-lapkricio-8-telsiu-mero",
                "2023-geguzes-7-visagino-mero",
            },
            "asked; no candidate of this small election states a degree",
        ),
        (column.endswith("_eur") and eid == "2002-prezidento", "declarations published only as archive scans (declaration_status: archyvo-skenai)"),
        (column in {"declared_currency", "currency_rate", "declaration_year", "assets_measure", "income_measure", "tax_measure", "income_floor_only"} and eid == "2002-prezidento", "declarations published only as archive scans"),
        (column == "declaration_year" and eid in DECLARATION_YEAR_ABSENT, "the page's declaration headings state no (YYYY m.) year and its closing note no period"),
        (column == "declaration_year" and date < "2004", "the archive forms state an extract date, never a tax year"),
        (column in {"assets_registered_eur", "cash_eur"} and date < "2002", "the 1996-2000 form holds wealth in one combined row (assets_total_eur, measure turtas-plius-lesos); this key is a null placeholder there"),
        (column in {"assets_registered_eur", "securities_eur"} and eid == "2002-gruodzio-22-savivaldybiu-tarybu", "the 2002 form prints property and securities as one combined row (assets_total_eur, measure turtas-plius-vp)"),
        (column in {"assets_registered_eur", "securities_eur", "loans_received_eur"} and eid == "2003-birzelio-15-seimo-nauji", "the row is printed and holds „-“ on all 27 records"),
        (column in {"self_employment_income_eur", "self_employment_deductions_eur", "asset_sale_income_eur", "asset_acquisition_cost_eur"} and date < "2018", "rows added by the 2018 GPM308/GPM311 rewording; earlier forms never print them"),
        (column in {"securities_eur", "loans_given_eur", "loans_received_eur"} and date < "2002", "the 1996-2000 form folds these into its combined rows"),
        # There is no rule here for `income_floor_only` reading zero on the
        # sectioned era. There was one, saying the flag is false everywhere
        # from 2004 on, and it could never fire: the column is a bool, and
        # `is_filled` counts False as an answer (a declared "no" is data),
        # so the cell reads 100 % wherever the declaration block is parsed
        # at all and 0 % only where it is absent — which the archive-scans
        # rule above already answers for the one such election. It was the
        # only one of the rules whose text appeared on no baseline row
        # (issue #165).
        (column == "birth_place" and eid == "2000-kovo-19-savivaldybiu-tarybu", "the card prints no birth place"),
        (column == "birth_place" and eid == "2004-prezidento", "the five birthplace phrases are the prose helper's documented misses (concept map)"),
    ]
    for matches, note in rules:
        if matches:
            if note.startswith("PARSER-GAP: "):
                return field_coverage.Baseline(0.0, "parser-gap", note.removeprefix("PARSER-GAP: "))
            return field_coverage.Baseline(0.0, "upstream-absent", note)
    return None


#: Which concept of docs/concept-map.json a gated column projects, for the
#: below-peers rule (issue #135): a column filled far under its peers is the
#: same fact as its concept's cell in docs/coverage-baseline.tsv, classified
#: there against the retained pages, so the candidacy baseline inherits that
#: classification rather than asking a human twice. The declaration-wide
#: columns (currency, measures, the derived totals) follow `gautos-pajamos`,
#: which every declaration block carries.
COLUMN_CONCEPTS = {
    "birth_date": "gimimo-data",
    "birth_place": "gimimo-vieta",
    "education_level": "issilavinimas",
    "education_level_rank": "issilavinimas",
    "education_higher": "issilavinimas",
    "education_unfinished": "issilavinimas",
    "education_entries": "issilavinimas",
    "assets_registered_eur": "privalomas-registruoti-turtas",
    "securities_eur": "vertybiniai-popieriai-meno-kuriniai-juvelyriniai-dirbiniai",
    "cash_eur": "pinigines-lesos",
    "loans_given_eur": "suteiktos-paskolos",
    "loans_received_eur": "gautos-paskolos",
    "income_eur": "gautos-pajamos",
    "income_tax_eur": "sumoketas-pajamu-mokestis",
    "income_gross_eur": "gautos-pajamos",
    "income_measure": "gautos-pajamos",
    "income_floor_only": "gautos-pajamos",
    "tax_measure": "gautos-pajamos",
    "assets_total_eur": "gautos-pajamos",
    "assets_measure": "gautos-pajamos",
    "declared_currency": "gautos-pajamos",
    "currency_rate": "gautos-pajamos",
    "declaration_year": "deklaracijos-metai",
    "self_employment_income_eur": "individualios-veiklos-pajamos",
    "self_employment_deductions_eur": "individualios-veiklos-atskaitymai",
    "asset_sale_income_eur": "turto-pardavimo-pajamos",
    "asset_acquisition_cost_eur": "turto-isigijimo-kaina",
    "preference_votes": "pirmumo-balsai",
    "preference_votes_measure": "pirmumo-balsai",
    "list_votes": "sarasas-balsai",
    "constituency_votes": "apygardos-balsai",
    "constituency_round": "apygardos-balsai",
    "constituency_place": "apygardos-balsai",
    "constituency_votes_pct": "apygardos-balsai",
}


def _known_low_note(
    column: str,
    election_id: str,
    coverage_baseline: dict[tuple[str, str], field_coverage.Baseline],
) -> field_coverage.Baseline | None:
    """The classification a below-peers column cell inherits from its concept's
    row in docs/coverage-baseline.tsv, or a structural reason of the table's
    own, or None -- then the gate demands a human answer."""
    # A Seimas general's constituency columns: on the candidates who stood in
    # one, and empty for those who stood on the list alone (issue #133 stopped
    # the 2000-2012 cards' "Daugiamandatė" row shipping as a district). The
    # by-elections, every candidate a constituency one, set the peer median.
    if column in {"constituency", "constituency_number"} and election_id in SEIMAS_GENERALS:
        return field_coverage.Baseline(
            0.0,
            "partly-published",
            "the constituency is on the candidates who stood in one; the rest of a"
            " general's field stood on the list alone (the cards' Daugiamandatė row is not a district)",
        )
    concept = COLUMN_CONCEPTS.get(column)
    if concept is None:
        return None
    prior = coverage_baseline.get((concept, election_id))
    if prior is None or prior.status not in field_coverage.LOW_STATUSES:
        return None
    return field_coverage.Baseline(0.0, prior.status, f"as the {concept} concept: {prior.note}")


def gate(
    cells: list[field_coverage.Cell],
    baseline_path: Path,
    registry_by_id: dict[str, dict[str, Any]],
    update: bool,
    max_drop: float,
    *,
    force: bool = False,
    coverage_baseline_path: Path | None = None,
) -> int:
    baseline = field_coverage.read_baseline(baseline_path)
    if update:
        # Auto-classify what the builder can explain structurally -- a zero
        # with a `_known_zero_note`, a below-peers cell whose concept the
        # coverage baseline already classifies -- and leave the rest
        # `unexplained` for a human, which exits 1 (issue #135 made
        # field_coverage's update do the same, and refuse over a standing
        # finding on a row already checked in).
        coverage = field_coverage.read_baseline(
            coverage_baseline_path
            if coverage_baseline_path is not None
            else baseline_path.parent / field_coverage.BASELINE.name
        )
        medians = field_coverage.peer_medians(cells)
        enriched = dict(baseline)
        for cell in cells:
            key = (cell.concept, cell.election)
            prior = enriched.get(key)
            if cell.records and cell.non_null == 0 and (
                prior is None or prior.status not in field_coverage.ZERO_STATUSES
            ):
                known = _known_zero_note(cell.concept, registry_by_id[cell.election])
                if known is not None:
                    enriched[key] = known
            elif field_coverage.below_peers(cell, medians[key]) and (
                prior is None or prior.status not in field_coverage.LOW_STATUSES
            ):
                inherited = _known_low_note(cell.concept, cell.election, coverage)
                if inherited is not None:
                    enriched[key] = inherited
        # What the builder could not explain is what blocks the rewrite: a
        # regression on a classified row, a zero or a low cell with no
        # structural reason on a row already checked in.
        return field_coverage.update_baseline(
            baseline_path,
            cells,
            enriched,
            field_coverage.check(cells, enriched, max_drop),
            force=force,
            max_drop=max_drop,
        )

    findings = field_coverage.check(cells, baseline, max_drop)

    if not findings:
        print("Fill gate: no findings.")
        return 0
    print(f"\nFill gate: {len(findings)} finding(s):", file=sys.stderr)
    for finding in findings[:40]:
        print(f"    {finding}", file=sys.stderr)
    if len(findings) > 40:
        print(f"    ... and {len(findings) - 40} more", file=sys.stderr)
    return 1


# ---------------------------------------------------------------------------


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("election_id", nargs="*", help="Subset to build; skips the gate and writes no baseline.")
    parser.add_argument("--repo-root", type=Path, default=Path("."))
    parser.add_argument("--dist", type=Path, default=None, help="Output directory (default <repo-root>/dist).")
    parser.add_argument("--max-drop", type=float, default=5.0)
    parser.add_argument("--update-baseline", action="store_true")
    parser.add_argument(
        "--force",
        action="store_true",
        help="With --update-baseline: rewrite even over a standing finding on a row already checked in.",
    )
    args = parser.parse_args()

    repo_root = args.repo_root
    dist = args.dist or (repo_root / "dist")
    subset = args.election_id or None
    if subset and args.update_baseline:
        parser.error("--update-baseline needs the full corpus, not a subset")

    rows, campaigns, elections_table, stats = build(repo_root, subset)
    persons = stats.pop("persons_rows")

    write_csv_gz(dist / "candidacies.csv.gz", COLUMNS, rows)
    write_csv_gz(
        dist / "campaigns.csv.gz",
        CAMPAIGN_COLUMNS,
        sorted(campaigns.values(), key=lambda c: (c["election_id"], c["campaign_key"])),
    )
    write_sqlite(
        dist / "vrk.sqlite",
        rows,
        campaigns,
        elections_table,
        persons,
        repo_root / "scraper" / "parties.json",
    )

    naive = sum(stats["donations_naive_eur"].values())
    print(f"candidacies:  {stats['records']} rows / {stats['elections']} elections")
    print(f"persons:      {stats['persons']}")
    print(f"campaigns:    {stats['campaigns']}")
    print(
        f"donations:    €{stats['donations_deduplicated_eur']:,.2f} de-duplicated by campaign_key"
        f" (naive per-candidate summing would say €{naive:,.2f}, "
        f"{naive / stats['donations_deduplicated_eur']:.1f}x)"
        if stats["donations_deduplicated_eur"]
        else "donations:    none in this subset"
    )
    for name in ("candidacies.csv.gz", "campaigns.csv.gz", "vrk.sqlite"):
        size = (dist / name).stat().st_size
        print(f"wrote {dist / name} ({size / 1024 / 1024:.1f} MB)")

    if subset:
        print("(subset build: fill gate skipped)")
        return 0
    registry_by_id = {e["id"]: e for e in identity.load_registry(repo_root / "scraper" / "elections.json")}
    cells = measure_cells(rows)
    return gate(
        cells,
        repo_root / BASELINE,
        registry_by_id,
        args.update_baseline,
        args.max_drop,
        force=args.force,
        coverage_baseline_path=repo_root / field_coverage.BASELINE,
    )


if __name__ == "__main__":
    raise SystemExit(main())
