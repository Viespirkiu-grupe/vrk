"""What personal data the corpus carries, path by path, and about whom (issue #142).

The corpus is a register of people: 113,073 candidacies of about 60,700
named persons, with birth dates, birth places, declared wealth and income,
declared convictions, campaign finances and portraits. It also carries
people who never stood for election -- children's names on 67,141 records,
a spouse's on 59,590, the treasurer and auditor of every campaign with
their phone and e-mail -- and nothing in the repository said so, or said
which of it a release ships. This script is the inventory.

One pass over `data/` collects every leaf path a record holds (list indices
collapsed to `[]`, so the corpus is a finite list: 1,169 paths across the
`normalized`, `rawData` and envelope layers on 2026-09-08) with the number of
records and elections carrying it, and classifies each through the RULES
table below: **who** the value is about (the candidate, their family, a
third party, or nobody -- an id, a URL, a vote count) and **how sensitive**
it is. The result is checked in twice -- `docs/personal-data.tsv`, the
table, and `docs/PERSONAL_DATA.md`, the reading of it -- and
tests/test_pii_inventory.py fails when a record holds a path the table
does not, so a parser that starts emitting a new field has to say whose
data it is before the field ships.

The classification decides one thing in code: `PUBLIC_PROFILE_DROPS` is the
list of paths `scripts/build_distribution.py --profile public` (the default)
removes from every record before it writes `vrk-corpus.sqlite` -- the
treasurer's and auditor's phone and e-mail, in both layers, plus the
campaign's own contact line where it repeats one of those values. None of
them reaches the candidacy table, the coverage gate or the dashboard's
comparison rows, so dropping them costs nothing a consumer can see.

    python scripts/pii_inventory.py            # measure the corpus, write both docs
    python scripts/pii_inventory.py --check    # measure, compare with the table, exit 1 on a path it lacks
    python scripts/pii_inventory.py --sample 200   # a sample of each election (what the suite runs)
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterator, NamedTuple

TABLE = Path("docs/personal-data.tsv")
DOCUMENT = Path("docs/PERSONAL_DATA.md")
TABLE_COLUMNS = ("path", "records", "elections", "subject", "sensitivity", "public", "note")

SUBJECTS = {
    "candidate": "the candidate: what they declared about themselves",
    "family": "the candidate's spouse, partner, children or other family members",
    "third-party": "someone else named on the candidate's pages: a treasurer, an auditor, a donor, a counterparty, a trustee",
    "none": "not about a person: an election fact, an organisation, an identifier, a URL, a hash",
}
SENSITIVITIES = {
    "identifying": "a name, a birth date or place, a portrait, a residence",
    "contact": "a phone number, an e-mail address, a website",
    "financial": "declared wealth, income, loans, transactions, donations, gifts",
    "criminal": "a conviction declaration and its detail",
    "eligibility": "the statutory declarations: citizenship, oaths, service, collaboration with foreign services",
    "ethnic": "declared nationality (tautybė)",
    "political": "party membership, the nominating organisation, the programme",
    "family": "marital status, family composition and counts",
    "biographical": "education, work, activity, languages, hobbies, free text about oneself",
    "public-record": "the candidacy itself: office, constituency, list, votes, outcome, registration",
    "organisation": "a legal person: its name, code, form",
    "technical": "an identifier, a URL, a hash, a date of fetch or filing, a selector",
    "mixed": "a raw page block whose rows carry several of the above; the normalized twin says which",
}
PUBLIC = {"ship", "drop", "conditional"}

#: The paths the public profile removes from every record, both layers
#: (issue #142): the campaign treasurer's and auditor's phone and e-mail --
#: 790 people, 259 of them on personal free-mail accounts, 355 on mobiles,
#: who never stood for anything. `conditional` paths are the campaign's own
#: contact line, dropped where its value is one of those.
PUBLIC_PROFILE_DROPS = (
    "normalized.politines-kampanijos-dalyvio-duomenys[].izdininkas.telefonas",
    "normalized.politines-kampanijos-dalyvio-duomenys[].izdininkas.el-pastas",
    "normalized.politines-kampanijos-dalyvio-duomenys[].auditorius.telefonas",
    "normalized.politines-kampanijos-dalyvio-duomenys[].auditorius.el-pastas",
    "rawData.politinesKampanijosDalyvioDuomenys.campaigns[].treasurer.phone",
    "rawData.politinesKampanijosDalyvioDuomenys.campaigns[].treasurer.email",
    "rawData.politinesKampanijosDalyvioDuomenys.campaigns[].auditor.phone",
    "rawData.politinesKampanijosDalyvioDuomenys.campaigns[].auditor.email",
)
PUBLIC_PROFILE_CONDITIONAL = (
    "normalized.politines-kampanijos-dalyvio-duomenys[].kontaktai.telefonas-pasiteirauti",
    "normalized.politines-kampanijos-dalyvio-duomenys[].kontaktai.el-pastas",
    "rawData.politinesKampanijosDalyvioDuomenys.campaigns[].participant.inquiryPhone",
    "rawData.politinesKampanijosDalyvioDuomenys.campaigns[].participant.email",
)


class Rule(NamedTuple):
    pattern: str
    subject: str
    sensitivity: str
    note: str = ""


# Ordered: the first pattern that matches the whole path wins. Specific
# paths come before the section-wide catch-alls, and the raw layer's rows
# -- page text keyed by a prompt, not by a field -- are classified at the
# block level with a pointer at the normalized twin that names each field.
_C = "candidate"
_F = "family"
_T = "third-party"
_N = "none"
RULES: tuple[Rule, ...] = (
    # --- envelope ---------------------------------------------------------
    Rule(r"candidateName", _C, "identifying"),
    Rule(r"candidateId|electionId", _N, "technical"),
    Rule(r"candidateNote", _C, "public-record", "the elected note VRK prints under the name"),
    Rule(r"source\..*", _N, "technical"),
    Rule(r"provenance\..*", _N, "technical"),
    # --- the candidacy block: at the root (2000-2015 results joins) and
    # --- inside normalized (the 1996-1999 archive list, the 1997 municipal dict)
    Rule(r"(normalized\.)?kandidatavimas(\[\])?\..*(-saltinis|\.saltinis|Saltinis|-nuoroda|Nuoroda|Url|Id|\.url|\.label|nariuPuslapis)$", _N, "technical"),
    Rule(r"(normalized\.)?kandidatavimas(\[\])?\..*(iskele|koalicijosPartij[a-z]*|partyList.*|sarasas|listKind|selfNominated|nominatedBy|kitiIskelejai\[\])$", _C, "political", "who nominated the candidate and on which list"),
    Rule(r"(normalized\.)?kandidatavimas(\[\])?\..*", _C, "public-record", "the candidacy: office, constituency, list position, votes, outcome"),
    # --- empty sections: the key exists and holds nothing ------------------------
    Rule(r"normalized\.(biografija|privaciu-interesu-deklaracija|profilis\.kita|anketa|kita)", _N, "technical", "an empty section: the key exists and holds nothing on this record"),
    Rule(r"rawData\.(biography|declaration|anketa|biografija|kita|programa|program|residence|personal|patiketiniai|candidacies|candidacy|deklaracija|skenai|privaciuInteresuDeklaracija|turtoIrPajamuDeklaracijos|politinesKampanijosDalyvioDuomenys)", _N, "technical", "an empty section: the key exists and holds nothing on this record"),
    # --- profile --------------------------------------------------------------
    Rule(r"normalized\.profilis\.vardas-pavarde", _C, "identifying"),
    Rule(r"normalized\.profilis\.nuotrauka", _C, "identifying", "the portrait's sidecar path; the bytes are the photos table, metadata-stripped in the public profile"),
    Rule(r"normalized\.profilis\.(pastaba|kandidatuoja-i)", _C, "public-record"),
    Rule(r"normalized\.profilis\.(biografijos-nuoroda|pajamu-deklaracijos-nuoroda|dokumentu-pateikimo-data)", _N, "technical"),
    Rule(r"normalized\.profilis\.kita\.[^.]+\.(pavadinimas|nuorodos\[\])", _N, "technical", "the card row's own label and links"),
    Rule(r"normalized\.profilis\.kita\.gimimo-data\.reiksme", _C, "identifying"),
    Rule(r"normalized\.profilis\.kita\.(interneto-svetaine|tinklalapis|www-[a-z0-9-]+)\.reiksme", _C, "contact", "the candidate's own website"),
    Rule(r"normalized\.profilis\.kita\.(iskele[a-z0-9-]*|issikeles-kandidatas|kandidata-iskele|sarasas)\.reiksme", _C, "political", "the nominating organisation and list"),
    Rule(r"normalized\.profilis\.kita\.(sveikatos-pazym[a-z]*|gyventojo-turto-pajamu-deklaracija|seimos-turto-pajamu-deklaracija|duomenu-anketa|registracija|pareiskimas)\.reiksme", _N, "technical", "the label of a linked document"),
    Rule(r"normalized\.profilis\.kita\.[^.]+\.reiksme", _C, "public-record", "a card row about the candidacy: constituency, municipality, list numbers, round, campaign registration"),
    # --- questionnaire ---------------------------------------------------------
    Rule(r"normalized\.(anketa|biografija)\.(gimimo-data|gimimo-metai|gimimo-vieta)$", _C, "identifying"),
    Rule(r"normalized\.anketa\.(gimimo-data-saltinis|gimimo-vietos-saltinis)", _N, "technical", "where a recovered value came from"),
    Rule(r"normalized\.anketa\.(adresas|gyvenamoji-vieta)|normalized\.gyvenamoji-vieta", _C, "contact", "the residence as published: a municipality or locality on all but four of 89,949 values (issue #142)"),
    Rule(r"normalized\.anketa\.kontaktai\..*", _C, "contact", "the candidate's own contact line (2019-2021 forms; `Neskelbiamas` on most)"),
    Rule(r"normalized\.(anketa|biografija)\.tautybe", _C, "ethnic"),
    Rule(r"normalized\.(anketa|biografija)\.seimine-padetis", _C, "family"),
    Rule(r"normalized\.(anketa|biografija)\.(sutuoktinio-vardas-pavarde|vaiku-vardai-pavardes)", _F, "identifying", "a spouse's or the children's names, published on the 1996-2020 questionnaires"),
    Rule(r"normalized\.anketa\.seimos-nariai.*", _F, "identifying", "family members by name and relation; 9,581 records declare members under 18"),
    Rule(r"normalized\.anketa\.pareiskimai\.(ar-buvote-pripazintas-kaltu.*|teisiniai-argumentai|ar-nebaigta-teismo-paskirta-bausme|ar-veika-dekriminalizuota|ar-neteko-mandato-uz-pazeidimus)", _C, "criminal"),
    Rule(r"normalized\.anketa\.teistumo-detales.*", _C, "criminal"),
    Rule(r"normalized\.anketa\.mandato-netekimo-detales", _C, "criminal", "the detail behind a mandate lost for a breach"),
    Rule(r"normalized\.anketa\.pareiskimai\..*", _C, "eligibility"),
    Rule(r"normalized\.anketa\.(politine-organizacija|narystes-politinese-organizacijose.*)", _C, "political"),
    Rule(r"normalized\.(anketa|biografija)\..*", _C, "biographical", "education, work, activity, languages, hobbies, free text"),
    Rule(r"normalized\.(kita\..*|programa\.tekstas)", _C, "biographical"),
    Rule(r"normalized\.patiketiniai.*", _T, "identifying", "the candidate's trustees (patikėtiniai), by name"),
    # --- asset and income declaration ---------------------------------------------
    Rule(r"normalized\.turto-ir-pajamu-deklaracijos\.(seimos-nariu-skaicius|seimos-nariu-iki-18-metu|islaikytiniu-skaicius)", _F, "family", "counts of family members and dependants"),
    Rule(r"normalized\.turto-ir-pajamu-deklaracijos\.sutuoktinio\..*", _F, "financial", "the spouse's own declared figures (352 records)"),
    Rule(r"normalized\.turto-ir-pajamu-deklaracijos\.(darboviete|pareigos|nepagrindines-darbovietes|pareigos-nepagrindinese-darbovietese)", _C, "biographical"),
    Rule(r"normalized\.turto-ir-pajamu-deklaracijos\.(israso-data|israsa-isdave|isdavimo-data|valiuta|deklaracijos-apimtis|deklaracijos-forma|deklaracijos-metai|forma|pastaba|deklaracijos\[\]\.(apimtis|forma|metai|pavadinimas|rusis)|israsai\..*)", _N, "technical"),
    Rule(r"normalized\.turto-ir-pajamu-deklaracijos\..*", _C, "financial"),
    # --- private-interest declaration ---------------------------------------------
    Rule(r"normalized\.privaciu-interesu-deklaracija\.(deklaruojantis-asmuo|deklaruojantysis-asmuo)", _C, "identifying", "the declarant's name"),
    Rule(r"normalized\.privaciu-interesu-deklaracija\.(pateikimo-data|id001a\.tekstas)", _N, "technical"),
    Rule(r"normalized\.privaciu-interesu-deklaracija\.[^.]*sutuoktin[^.]*\.(vardas|pavarde)", _F, "identifying", "the spouse's or partner's name"),
    Rule(r"normalized\.privaciu-interesu-deklaracija\.[^.]*sutuoktin[^.]*(\..*)?", _F, "biographical", "the spouse's or partner's employer and position"),
    Rule(r"normalized\.privaciu-interesu-deklaracija\.[^.]+\[\]\.(asmuo-kurio-[a-z-]+|sandori-sudares-asmuo|kieno-rysys|kieno-sandoris|tipas|rysio-pobudis|dalyvavimo-budas|pareigu-pobudis|sandorio-forma|sandoris|isigijimo-budas)", _N, "technical", "a selector or category: whose entry it is, what kind"),
    Rule(r"normalized\.privaciu-interesu-deklaracija\.[^.]+\[\]\.(juridinio-asmens-[a-z-]+|registracijos-salis|valstybe|pavadinimas|darbdavys|darboviete|pajamu-saltinio-pavadinimas|kitos-sandorio-salies-pavadinimas|kita-sandorio-salis|sandorio-salies-kodas|dovanojusiojo-asmens-pavadinimas|vietoves-pavadinimas)", _T, "organisation", "the legal person or place named in the entry (a counterparty can also be a natural person)"),
    Rule(r"normalized\.privaciu-interesu-deklaracija\.[^.]+\[\]\.(vardas-pavarde|vardas-ir-pavarde|fizinio-asmens-vardas-pavarde[a-z-]*|fizinio-ar-juridinio-asmens-sandorio-salies-iu-vardas-pavarde-ar-pavadinimas|dovanojusio-fizinio-asmens-vardas-pavarde[a-z-]*|kas-suteike-paslauga|paslauga-suteikusio-ar-apmokejusio-islaidas-fiz[a-z-]*|rysiais-susieto-asmens-pilietybe)", _T, "identifying", "a natural person named in the declaration: a relative, a counterparty, a gift giver, a source of a possible conflict"),
    Rule(r"normalized\.privaciu-interesu-deklaracija\.(deklaruojancio-darbovietes|darboviete-ir-pareigos-valstybineje-tarnyboje|visos-darbovietes[a-z-]*|kitos-darbovietes-pareigos|iii-individuali-veikla|id001i|iv-naryste[a-z-]*|ix-naryste[a-z-]*|vi-individualios-imones[a-z-]*|ii-dalyvavimas[a-z-]*)(\[\])?(\..*)?", _C, "biographical", "the declarant's employers, positions, memberships and activities"),
    Rule(r"normalized\.privaciu-interesu-deklaracija\..*", _C, "financial", "assets, income sources, securities, obligations, transactions, gifts and possible conflicts of interest"),
    # --- campaign finance -----------------------------------------------------------
    Rule(r"normalized\.politines-kampanijos-dalyvio-duomenys\[\]\.(izdininkas|auditorius)\.(telefonas|el-pastas)", _T, "contact", "the treasurer's / auditor's phone and e-mail; DROPPED by the public profile"),
    Rule(r"normalized\.politines-kampanijos-dalyvio-duomenys\[\]\.(izdininkas|auditorius)\.vardas-pavarde", _T, "identifying", "the treasurer / auditor by name (790 people)"),
    Rule(r"normalized\.politines-kampanijos-dalyvio-duomenys\[\]\.(izdininkas|auditorius)\.imones-[a-z-]+", _T, "organisation"),
    Rule(r"normalized\.politines-kampanijos-dalyvio-duomenys\[\]\.auditorius\.ataskaitos.*", _N, "public-record", "the audit reports filed"),
    Rule(r"normalized\.politines-kampanijos-dalyvio-duomenys\[\]\.kontaktai\..*", _T, "contact", "the campaign's contact line; the treasurer's own phone and e-mail on 93 of 105 sampled 2016 records, so dropped by the public profile where it repeats one"),
    Rule(r"normalized\.politines-kampanijos-dalyvio-duomenys\[\]\.aukos-pagal-sekcija\.[^.]+\.records\[\]\.(donor|municipality)", _T, "identifying", "a donor's name and municipality, as VRK publishes them (the law requires disclosure above the small-donation threshold)"),
    Rule(r"normalized\.politines-kampanijos-dalyvio-duomenys\[\]\.aukos-pagal-sekcija\.[^.]+\.records\[\]\..*", _T, "financial", "a donation: amount, date, source code, notes"),
    Rule(r"normalized\.politines-kampanijos-dalyvio-duomenys\[\]\.aukos-pagal-sekcija\..*", _C, "financial", "the campaign's donation totals and section headings"),
    Rule(r"normalized\.politines-kampanijos-dalyvio-duomenys\[\]\.sutartys\[\]\.counterparty", _T, "organisation", "the contract counterparty (an agency, a printer, a broadcaster)"),
    Rule(r"normalized\.politines-kampanijos-dalyvio-duomenys\[\]\.(sutartys|finansavimo-ataskaitos|sprendimai)(\[\])?(\..*)?", _N, "public-record", "contracts, funding reports and VRK decisions as filed"),
    Rule(r"normalized\.politines-kampanijos-dalyvio-duomenys\[\]\.atstovauja\..*", _C, "political", "the party or list the represented participant runs under"),
    Rule(r"normalized\.politines-kampanijos-dalyvio-duomenys\[\]\..*", _C, "public-record", "the campaign registration: status, dates, decision numbers"),
    # --- the raw layer ------------------------------------------------------------------
    Rule(r"rawData\.profile\.photoMeta\..*", _N, "technical"),
    Rule(r"rawData\.profile\.(photoSrc|photoUrl)", _C, "identifying", "the portrait reference (sidecar path or URL)"),
    Rule(r"rawData\.profile\.candidateDisplayName", _C, "identifying"),
    Rule(r"rawData\.profile\..*", _C, "mixed", "the candidate card as published: nomination, constituency, list, elected note, document links; see normalized.profilis"),
    Rule(r"rawData\.personal\.(birthDate|birthPlace)", _C, "identifying"),
    Rule(r"rawData\.personal\.residence", _C, "contact"),
    Rule(r"rawData\.personal\.nationality", _C, "ethnic"),
    Rule(r"rawData\.personal\.familyStatus", _C, "family"),
    Rule(r"rawData\.personal\.familyMembers.*", _F, "identifying", "family members by name and relation (the 1997 municipal card)"),
    Rule(r"rawData\.personal\..*", _C, "biographical"),
    Rule(r"rawData\.residence(\..*)?", _C, "contact"),
    Rule(r"rawData\.(anketa|biografija|biography)\..*", _C, "mixed", "the questionnaire / biography rows as published, prompt by prompt; normalized.anketa and normalized.biografija classify each field"),
    Rule(r"rawData\.(turtoIrPajamuDeklaracijos|declaration)\..*", _C, "mixed", "the declaration extract as published, family counts included; see normalized.turto-ir-pajamu-deklaracijos"),
    Rule(r"rawData\.privaciuInteresuDeklaracija\..*", _C, "mixed", "the private-interest declaration as published, spouse and third parties included; see normalized.privaciu-interesu-deklaracija"),
    Rule(r"rawData\.politinesKampanijosDalyvioDuomenys\.campaigns\[\]\.(treasurer|auditor)\.(phone|email)", _T, "contact", "the treasurer's / auditor's phone and e-mail; DROPPED by the public profile"),
    Rule(r"rawData\.politinesKampanijosDalyvioDuomenys\.campaigns\[\]\.(treasurer|auditor)\.name", _T, "identifying"),
    Rule(r"rawData\.politinesKampanijosDalyvioDuomenys\.campaigns\[\]\.(treasurer|auditor)\..*", _T, "organisation"),
    Rule(r"rawData\.politinesKampanijosDalyvioDuomenys\.campaigns\[\]\.participant\.(inquiryPhone|email)", _T, "contact", "the campaign's contact line; dropped by the public profile where it repeats the treasurer's or auditor's"),
    Rule(r"rawData\.politinesKampanijosDalyvioDuomenys\..*", _C, "mixed", "the campaign pages as published: donors, reports, contracts; see normalized.politines-kampanijos-dalyvio-duomenys"),
    Rule(r"rawData\.candidacies.*", _C, "public-record", "the archive card's candidacies and results"),
    Rule(r"rawData\.candidacy\.(listName|nominator|memberParty)", _C, "political", "the 1997 municipal card's list and nominator"),
    Rule(r"rawData\.candidacy\..*", _C, "public-record", "the 1997 municipal card's municipality and list numbers"),
    Rule(r"rawData\.deklaracija\..*", _C, "mixed", "the 2003/2004 declaration form as published, prompt by prompt; see normalized.turto-ir-pajamu-deklaracijos"),
    Rule(r"rawData\.skenai\..*", _C, "technical", "the URLs of VRK's scanned documents on the 2002/2004 presidential pages (declaration, questionnaire, health certificate, statement); the corpus holds the links, not the scans"),
    Rule(r"rawData\.(kita|programa|program)(\..*)?", _C, "biographical"),
    Rule(r"rawData\.patiketiniai.*", _T, "identifying"),
    Rule(r"rawData\..*(Url|url|urls\[\]|Id|sha256|fetchedAt)$", _N, "technical"),
)
_COMPILED = [(re.compile(rule.pattern), rule) for rule in RULES]


class Classification(NamedTuple):
    subject: str
    sensitivity: str
    public: str
    note: str


def classify(path: str) -> Classification | None:
    """The first rule whose pattern matches the whole path, or None."""
    for pattern, rule in _COMPILED:
        if pattern.fullmatch(path):
            public = "drop" if path in PUBLIC_PROFILE_DROPS else "conditional" if path in PUBLIC_PROFILE_CONDITIONAL else "ship"
            return Classification(rule.subject, rule.sensitivity, public, rule.note)
    return None


# ---------------------------------------------------------------------------
# Measuring
# ---------------------------------------------------------------------------

ENVELOPE_ORDER = ("electionId", "candidateId", "candidateName", "candidateNote", "source", "kandidatavimas", "normalized", "rawData", "provenance")


def leaf_paths(record: dict[str, Any]) -> set[str]:
    """Every leaf path in a record, list indices collapsed to `[]`. An empty
    list or dict is a leaf of its own (the key exists, holds nothing)."""
    found: set[str] = set()

    def walk(value: Any, path: str) -> None:
        if isinstance(value, dict):
            if not value:
                found.add(path)
                return
            for key, child in value.items():
                walk(child, f"{path}.{key}" if path else key)
        elif isinstance(value, list):
            if not value:
                found.add(path + "[]")
                return
            for child in value:
                walk(child, path + "[]")
        else:
            found.add(path)

    for key in ENVELOPE_ORDER:
        if key in record:
            walk(record[key], key)
    for key in record:
        if key not in ENVELOPE_ORDER:
            walk(record[key], key)
    return found


def election_records(data_root: Path, election_id: str, sample: int | None = None) -> Iterator[dict[str, Any]]:
    paths = sorted(p for p in (data_root / election_id).glob("*.json") if p.name != "anomalies.jsonl")
    if sample is not None and len(paths) > sample:
        step = max(1, len(paths) // sample)
        paths = paths[::step][:sample]
    for path in paths:
        yield json.loads(path.read_text(encoding="utf-8"))


class PathCount(NamedTuple):
    path: str
    records: int
    elections: int


def measure(data_root: Path, election_ids: list[str], sample: int | None = None) -> list[PathCount]:
    records: Counter[str] = Counter()
    elections: dict[str, set[str]] = defaultdict(set)
    for election_id in election_ids:
        for record in election_records(data_root, election_id, sample):
            for path in leaf_paths(record):
                records[path] += 1
                elections[path].add(election_id)
    return sorted(PathCount(path, count, len(elections[path])) for path, count in records.items())


def corpus_elections(data_root: Path) -> list[str]:
    return sorted(
        child.name
        for child in data_root.iterdir()
        if child.is_dir() and any(p.name != "anomalies.jsonl" for p in child.glob("*.json"))
    )


# ---------------------------------------------------------------------------
# The two documents
# ---------------------------------------------------------------------------


class Row(NamedTuple):
    path: str
    records: int
    elections: int
    subject: str
    sensitivity: str
    public: str
    note: str


def rows_for(counts: list[PathCount]) -> tuple[list[Row], list[str]]:
    """Classify every measured path; the second value lists the paths no rule
    claims, which the caller treats as an error."""
    rows: list[Row] = []
    unclassified: list[str] = []
    for count in counts:
        classification = classify(count.path)
        if classification is None:
            unclassified.append(count.path)
            continue
        rows.append(Row(count.path, count.records, count.elections, *classification))
    return rows, unclassified


def write_table(path: Path, rows: list[Row]) -> None:
    lines = ["\t".join(TABLE_COLUMNS)]
    for row in rows:
        lines.append("\t".join([row.path, str(row.records), str(row.elections), row.subject, row.sensitivity, row.public, row.note]))
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def read_table(path: Path) -> list[Row]:
    rows: list[Row] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip() or line.startswith(TABLE_COLUMNS[0] + "\t"):
            continue
        fields = (line.split("\t") + [""] * 7)[:7]
        rows.append(Row(fields[0], int(fields[1]), int(fields[2]), fields[3], fields[4], fields[5], fields[6]))
    return rows


def _fmt(n: int) -> str:
    return f"{n:,}"


def render_document(rows: list[Row], total_records: int, measured_on: str) -> str:
    by_subject: Counter[str] = Counter()
    by_pair: dict[tuple[str, str], list[Row]] = defaultdict(list)
    for row in rows:
        by_subject[row.subject] += 1
        by_pair[(row.subject, row.sensitivity)].append(row)

    def reach(group: list[Row]) -> int:
        return max((r.records for r in group), default=0)

    out: list[str] = []
    out.append("# Personal data in the corpus\n")
    out.append(
        "Who each field is about, how sensitive it is, and which fields the public\n"
        "release drops (issue #142). Generated by `scripts/pii_inventory.py` from\n"
        f"`docs/personal-data.tsv`, measured over {_fmt(total_records)} records on {measured_on};\n"
        "`tests/test_pii_inventory.py` fails when a record holds a path the table\n"
        "does not. The terms under which any of it may be reused, and whom to write\n"
        "to about a person's record, are in [DATA_TERMS.md](../DATA_TERMS.md).\n"
    )
    out.append("## The four subjects\n")
    out.append("| subject | paths | who |\n|---|---:|---|")
    for subject, meaning in SUBJECTS.items():
        out.append(f"| `{subject}` | {_fmt(by_subject[subject])} | {meaning} |")
    out.append("")
    out.append(
        "`records` below is the widest reach of any path in the group -- how many\n"
        "records carry at least that field -- not a sum over paths.\n"
    )
    for subject in SUBJECTS:
        out.append(f"### {subject}\n")
        out.append("| sensitivity | paths | records | what |\n|---|---:|---:|---|")
        for sensitivity, meaning in SENSITIVITIES.items():
            group = by_pair.get((subject, sensitivity))
            if not group:
                continue
            out.append(f"| `{sensitivity}` | {_fmt(len(group))} | {_fmt(reach(group))} | {meaning} |")
        out.append("")

    third = [r for r in rows if r.subject == "third-party" and r.sensitivity in ("identifying", "contact")]
    out.append("## People who never stood for election\n")
    out.append(
        "The fields that name or reach someone other than the candidate -- family\n"
        "members and the third parties on a campaign or a declaration -- sorted by\n"
        "how many records carry them. Family fields are the questionnaire's own\n"
        "questions (a spouse's name, the children's names, asked until 2020) and the\n"
        "declarations' spouse sections; third-party fields are the people a campaign\n"
        "or a declaration has to name by law: treasurer, auditor, donors, counterparties.\n"
    )
    out.append("| path | records | elections | subject | sensitivity | public |\n|---|---:|---:|---|---|---|")
    family_and_third = sorted(
        (r for r in rows if r.subject in ("family", "third-party") and r.sensitivity in ("identifying", "contact", "financial", "biographical")),
        key=lambda r: (-r.records, r.path),
    )
    for row in family_and_third:
        out.append(f"| `{row.path}` | {_fmt(row.records)} | {row.elections} | {row.subject} | {row.sensitivity} | {row.public} |")
    out.append("")

    dropped = [r for r in rows if r.public == "drop"]
    conditional = [r for r in rows if r.public == "conditional"]
    out.append("## What the public release drops\n")
    out.append(
        "`scripts/build_distribution.py --profile public` (the default) removes\n"
        "these values from every record before it writes `vrk-corpus.sqlite`; the\n"
        "`records` table and `reconstruct_record` then reproduce the record *without*\n"
        "them. `--profile full` ships everything, for a mirror of the archive. None\n"
        "of the dropped paths reaches `candidacies.csv.gz`, the coverage gate or the\n"
        "dashboard's comparison rows, so the public profile costs nothing a consumer\n"
        "of those can see. `MANIFEST.json` records the profile and how many values\n"
        "were removed.\n"
    )
    out.append("| path | records | why |\n|---|---:|---|")
    for row in dropped:
        out.append(f"| `{row.path}` | {_fmt(row.records)} | {row.note} |")
    for row in conditional:
        out.append(f"| `{row.path}` (where it repeats a dropped value) | {_fmt(row.records)} | {row.note} |")
    out.append("")
    out.append("## What the derived layers surface\n")
    out.append(
        "The release carries every record whole; what the candidacy table, the person\n"
        "index and the dashboard lift *out* of the records is a narrower, deliberate\n"
        "set (issue #162). Declared nationality (`ethnic` above, a special category\n"
        "of personal data) is the candidacy table's `nationality` and the dashboard's\n"
        "nationality facet, comparison row and summary section, folded from 117\n"
        "spellings into 45 census groups by `scraper/shared/tautybe.py` -- the\n"
        "corpus's one minority-representation series, 89,154 answers over 30 years.\n"
        "The statutory declarations (`eligibility`: another citizenship, an oath to a\n"
        "foreign state, military service, collaboration with foreign or Soviet\n"
        "special services, a lost mandate) are concepts in `docs/concept-map.json`,\n"
        "the table's `declarations_status` and `declarations_flagged`, and one\n"
        "dashboard row that lists only the answers departing from the usual one.\n"
        "Deliberately *not* surfaced: the spouse's and children's names are measured\n"
        "by the fill gate and read by no column, row or index field, and the home\n"
        "address is mapped nowhere -- VRK prints them for the voter reading one page,\n"
        "not for a register.\n"
    )
    out.append("## Portraits\n")
    out.append(
        "Every portrait is stored once in the `photos` table under the sha256 of the\n"
        "bytes VRK served, which is what the record's `photoMeta.sha256` names. In the\n"
        "public profile the stored bytes are passed through\n"
        "`scraper/shared/image_metadata.py` first: the Exif block (GPS position,\n"
        "camera serial, `Artist`, `CameraOwnerName` -- 9,889 of the 27,493 sidecars\n"
        "carry one, 1,215 with a GPS IFD), the XMP packet, the Photoshop/IPTC block\n"
        "and JPEG comments are removed and the picture is copied through unchanged;\n"
        "PNG text and Exif chunks likewise. `photos.stripped` says whether anything\n"
        "was removed and `photos.stripped_sha256` hashes what is stored, so the\n"
        "archive stays verifiable against the original hash and the release carries\n"
        "the face and nothing else. The archive under `data/` is not touched.\n"
    )
    out.append("## Regenerating\n")
    out.append(
        "```bash\n"
        "python scripts/pii_inventory.py          # measure data/, rewrite the table and this file\n"
        "python scripts/pii_inventory.py --check  # exit 1 on a path the table lacks\n"
        "```\n\n"
        "A new path means a parser started emitting a field; add a rule to `RULES`\n"
        "in the script -- whose data it is, how sensitive -- and regenerate. A path\n"
        "that should not ship goes into `PUBLIC_PROFILE_DROPS` there, which is the\n"
        "list the distribution builder reads.\n"
    )
    return "\n".join(out)


# ---------------------------------------------------------------------------


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--repo-root", type=Path, default=Path("."))
    parser.add_argument("--sample", type=int, default=None, help="Records read per election (default: all).")
    parser.add_argument("--check", action="store_true", help="Compare the measured paths with the checked-in table; exit 1 on one it lacks.")
    args = parser.parse_args()

    data_root = args.repo_root / "data"
    election_ids = corpus_elections(data_root) if data_root.is_dir() else []
    if not election_ids:
        print(f"No election under {data_root}: the corpus is scraped, not cloned.", file=sys.stderr)
        return 2
    counts = measure(data_root, election_ids, args.sample)
    total = sum(1 for eid in election_ids for _ in election_records(data_root, eid, args.sample))
    rows, unclassified = rows_for(counts)
    if unclassified:
        print(f"{len(unclassified)} path(s) no rule classifies -- add rules to RULES:", file=sys.stderr)
        for path in unclassified:
            print(f"    {path}", file=sys.stderr)
        return 1

    table_path = args.repo_root / TABLE
    if args.check:
        known = {row.path for row in read_table(table_path)} if table_path.exists() else set()
        missing = [row.path for row in rows if row.path not in known]
        print(f"{len(rows)} path(s) across {len(election_ids)} election(s); {len(known)} in {table_path}")
        if missing:
            print(f"{len(missing)} path(s) the table lacks -- run scripts/pii_inventory.py to regenerate it:", file=sys.stderr)
            for path in missing:
                print(f"    {path}", file=sys.stderr)
            return 1
        print("No findings.")
        return 0

    from datetime import date

    write_table(table_path, rows)
    (args.repo_root / DOCUMENT).write_text(render_document(rows, total, date.today().isoformat()), encoding="utf-8")
    by_subject = Counter(row.subject for row in rows)
    print(f"{len(rows)} path(s) across {len(election_ids)} election(s), {total} records -> {table_path}, {args.repo_root / DOCUMENT}")
    for subject in SUBJECTS:
        print(f"  {subject:12s} {by_subject[subject]:5d} path(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
