"""A candidacy's campaign-finance participant, and the money its campaign declared.

Two consumers read this and must read it one way: the candidacy table
(`campaign_key`, the campaigns table, the de-duplicated donation total) and
the person index the dashboard renders (issue #162). It lived in
scripts/build_candidacy_table.py until the index needed it too, and the
index is imported by that script, so the shared reading moved here.

The one rule worth repeating wherever this money is shown: a campaign is not
a candidate. `campaignKey` groups the candidacies that share one participant
-- one per independent candidate, one for a party's whole list -- and its
donations are VRK's single total for that participant. Summing it per
candidacy counts a party's money once per candidate on its list: over the
corpus that reads €2.68 bn where the de-duplicated total is €25.7 M, 104.1x
(issue #97). So a figure from here always travels with the campaign's
candidacy count.
"""

from __future__ import annotations

import unicodedata
from typing import Any

from scraper.shared.deklaracijos import LITAS_PER_EURO


def fold_token(text: Any) -> str | None:
    """A status word, case- and accent-folded: "Savarankiškas" -> "savarankiskas"."""
    if not isinstance(text, str) or not text.strip():
        return None
    decomposed = unicodedata.normalize("NFD", text.strip().casefold())
    return "".join(ch for ch in decomposed if unicodedata.category(ch) != "Mn")


def campaign_entry(record: dict[str, Any]) -> tuple[str | None, str | None, str | None, dict | None]:
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
        status = fold_token(entry.get("statusas"))
    return key, status, label, entry


def donation_total_eur(entry: dict[str, Any] | None) -> float | None:
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
