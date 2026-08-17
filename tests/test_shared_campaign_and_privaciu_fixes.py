"""Regression tests for two shared-parser defects found while building the
2023-03-05 municipal module.

Both bugs were silent: the source data was fetched and kept in rawData, but the
normalizer dropped it, so nothing downstream ever noticed. Neither shared code
path had a test, which is what let the defects survive across 17 election
modules. These tests pin the recovered fields at the unit level and end to end.

  A. ep_2024._normalize_privaciu_interesu_data dropped declaration items with an
     empty key. Free-text sections such as "Kiti duomenys" are published as an
     unlabelled sentence, so the whole declared text vanished.
  B. seimo_2016._normalize_campaigns ignored the "Sprendimai" campaign tab, so
     VRK decisions about a campaign (unlawful political advertising, accounting
     breaches) were never normalized.
  C. seimo_2016._parse_campaign_donations_html lost a donations section whose
     heading carried the empty-state marker inline ("Gautos ir priimtos aukos:
     Duomenų nėra"). No table or text node follows such a heading, so the next
     heading overwrote the pending title and the section disappeared —
     collapsing "declared no donations" into "section never published".
"""

import json
import tempfile
import unittest
from pathlib import Path

from scraper.elections.ep_2024.anketa_parser import _normalize_privaciu_interesu_data
from scraper.elections.prezidento_2019.anketa_parser import (
    parse_anketa_sample as parse_prezidento_2019_sample,
)
from scraper.elections.savivaldybiu_2023.anketa_parser import (
    parse_anketa_sample as parse_savivaldybiu_2023_sample,
)
from scraper.elections.seimo_2016.anketa_parser import (
    _normalize_sprendimai_tab,
    _parse_campaign_donations_html,
)


REPO_ROOT = Path(__file__).resolve().parents[1]
SAMPLES_ROOT = REPO_ROOT / "samples" / "html"
DATA_ROOT = REPO_ROOT / "data"

SAVIVALDYBIU_ELECTION_ID = "2023-kovo-5-savivaldybiu-tarybu-ir-meru"
# The one fixture that exercises both recovered fields at once.
ZEBRAUSKAS = "algirdas-zebrauskas-2424292"
# A registered campaign participant that declared no donations at all.
MITROFANOVAS = "vitalijus-mitrofanovas-2425352"


def _parse(parse_fn, election_id: str, candidate_id: str) -> dict:
    with tempfile.TemporaryDirectory() as tmp:
        output_path, _ = parse_fn(
            candidate_id=candidate_id,
            samples_root=SAMPLES_ROOT / election_id,
            output_root=Path(tmp),
        )
        return json.loads(output_path.read_text(encoding="utf-8"))


def _all_decisions(record: dict) -> list[dict]:
    campaigns = record["normalized"]["politines-kampanijos-dalyvio-duomenys"]
    decisions: list[dict] = []
    for campaign in campaigns:
        decisions.extend(campaign.get("sprendimai") or [])
    return decisions


class SprendimaiTabNormalizationTests(unittest.TestCase):
    """Fix B — seimo_2016._normalize_sprendimai_tab."""

    # Verbatim rawData payload of the "sprendimai" tab from
    # data/2023-kovo-5-savivaldybiu-tarybu-ir-meru/algirdas-zebrauskas-2424292-*.json
    DECISION_TITLE = (
        "Dėl Telšių rajono rinkimų apygardoje Nr. 51 išsikėlusio kandidato "
        "Algirdo Žebrausko neatlygintinai skleistos išorinės politinės reklamos "
        "ant juridiniams asmenims nuosavybės teise priklausančių objekt"
    )
    DECISION_URL = (
        "https://e-seimas.lrs.lt/portal/legalAct/lt/TAD/"
        "63cdc540643811eea182def3ac5c11d6?positionInSearchResults=1"
        "&searchModelUUID=a65ba314-0cd9-4e2e-ade8-3d4be4d8ac7d"
    )

    def _payload(self) -> dict:
        return {
            "blocks": [
                {
                    "title": "",
                    "columns": [],
                    "rows": [
                        ["Sprendimas"],
                        [
                            "1.",
                            self.DECISION_TITLE,
                            "2023-10-06",
                            "Sp-242",
                            "",
                        ],
                    ],
                },
                {
                    "title": "texts",
                    "values": [
                        "Sprendimas",
                        "Eil.",
                        "nr.",
                        "Pavadinimas",
                        "Data",
                        "Numeris",
                        "Pastaba",
                        "1.",
                        self.DECISION_TITLE,
                        "2023-10-06",
                        "Sp-242",
                    ],
                },
                {"title": "links", "urls": [self.DECISION_URL]},
            ]
        }

    def test_decision_row_is_normalized(self) -> None:
        records = _normalize_sprendimai_tab(self._payload())

        self.assertEqual(
            records,
            [
                {
                    "rowNumber": "1.",
                    "title": self.DECISION_TITLE,
                    "date": "2023-10-06",
                    "number": "Sp-242",
                    "note": None,
                    "urls": [self.DECISION_URL],
                }
            ],
        )

    def test_header_rows_are_skipped(self) -> None:
        payload = self._payload()
        # VRK renders the column headings as their own row on some pages.
        payload["blocks"][0]["rows"].insert(
            1, ["Eil. nr.", "Pavadinimas", "Data", "Numeris", "Pastaba"]
        )

        records = _normalize_sprendimai_tab(payload)

        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["number"], "Sp-242")

    def test_links_block_is_not_treated_as_a_decision(self) -> None:
        # The links block carries no rows of its own; its urls belong to the
        # decision rows, in row order.
        records = _normalize_sprendimai_tab(self._payload())

        self.assertEqual([record["urls"] for record in records], [[self.DECISION_URL]])

    def test_each_decision_keeps_only_its_own_document(self) -> None:
        # Every decision row carries its own e-seimas link. Copying the whole
        # links block onto every record cross-links each decision to the
        # others' documents, which is what the first version of this handler
        # did: 6 of 27 decision records in the fixture corpus were affected.
        payload = self._payload()
        payload["blocks"][0]["rows"].append(
            ["2.", "Dėl politinės kampanijos finansavimo ataskaitos", "2023-11-02", "Sp-301", ""]
        )
        second_url = "https://e-seimas.lrs.lt/portal/legalAct/lt/TAD/second-decision"
        payload["blocks"][2]["urls"].append(second_url)

        records = _normalize_sprendimai_tab(payload)

        self.assertEqual(len(records), 2)
        self.assertEqual(records[0]["urls"], [self.DECISION_URL])
        self.assertEqual(records[1]["urls"], [second_url])

    def test_decision_without_a_document_gets_an_empty_list(self) -> None:
        payload = self._payload()
        payload["blocks"][0]["rows"].append(
            ["2.", "Dėl politinės kampanijos finansavimo ataskaitos", "2023-11-02", "Sp-301", ""]
        )

        records = _normalize_sprendimai_tab(payload)

        self.assertEqual(records[0]["urls"], [self.DECISION_URL])
        self.assertEqual(records[1]["urls"], [])

    def test_columns_beyond_the_fifth_are_kept(self) -> None:
        # A wider table than VRK currently publishes must not lose data.
        payload = self._payload()
        payload["blocks"][0]["rows"][1].append("Papildomas stulpelis")

        records = _normalize_sprendimai_tab(payload)

        self.assertEqual(records[0]["extraColumns"], ["Papildomas stulpelis"])

    def test_malformed_payloads_are_ignored(self) -> None:
        self.assertEqual(_normalize_sprendimai_tab(None), [])
        self.assertEqual(_normalize_sprendimai_tab({}), [])
        self.assertEqual(_normalize_sprendimai_tab({"blocks": "nope"}), [])
        self.assertEqual(_normalize_sprendimai_tab({"blocks": [{"rows": [[]]}]}), [])

    def test_savivaldybiu_2023_fixture_carries_decisions(self) -> None:
        record = _parse(
            parse_savivaldybiu_2023_sample, SAVIVALDYBIU_ELECTION_ID, ZEBRAUSKAS
        )

        decisions = _all_decisions(record)

        self.assertEqual(len(decisions), 1)
        self.assertEqual(decisions[0]["number"], "Sp-242")
        self.assertEqual(decisions[0]["date"], "2023-10-06")

    def test_pre_existing_election_gains_decisions(self) -> None:
        # 2019-prezidento is one of the 9 elections whose parsed output changed
        # when the shared handler landed; it reaches the same seimo_2016
        # _normalize_campaigns through its own module.
        record = _parse(parse_prezidento_2019_sample, "2019-prezidento", "ingrida-simonyte")

        decisions = _all_decisions(record)

        self.assertEqual([decision["number"] for decision in decisions], ["Sp-411", "Sp-392"])
        for decision in decisions:
            self.assertTrue(decision["title"])
            self.assertTrue(decision["urls"])

    def test_committed_output_matches_reparse(self) -> None:
        committed = json.loads(
            (
                DATA_ROOT / "2019-prezidento" / "ingrida-simonyte-2019-prezidento.json"
            ).read_text(encoding="utf-8")
        )

        self.assertEqual(
            [decision["number"] for decision in _all_decisions(committed)],
            ["Sp-411", "Sp-392"],
        )


class PrivaciuInteresuFreeTextTests(unittest.TestCase):
    """Fix A — ep_2024._normalize_privaciu_interesu_data."""

    FREE_TEXT = (
        "Dukra Šarūnė Žebrauskaitė-Lekavičienė yra Telšių rajono apygardos "
        "Nr. 51 rinkimų komisijos narė, dirba Telšių rajono savivaldybės "
        "administracijoje. Patalpų nuoma Turgaus a. 14, Telšiai."
    )

    def test_unlabelled_item_survives_as_tekstas(self) -> None:
        payload = {
            "sections": [
                {
                    "title": "Kiti duomenys",
                    "records": [
                        {
                            "recordType": "",
                            "items": [{"key": "", "value": self.FREE_TEXT}],
                        }
                    ],
                }
            ]
        }

        normalized = _normalize_privaciu_interesu_data(payload)

        self.assertEqual(normalized, {"kiti-duomenys": [{"tekstas": self.FREE_TEXT}]})

    def test_labelled_items_are_unaffected_by_free_text_recovery(self) -> None:
        payload = {
            "sections": [
                {
                    "title": "Kiti duomenys",
                    "records": [
                        {
                            "items": [
                                {"key": "Pastaba", "value": "Reikšmė"},
                                {"key": "", "value": "Laisvas tekstas"},
                            ]
                        }
                    ],
                }
            ]
        }

        normalized = _normalize_privaciu_interesu_data(payload)

        self.assertEqual(
            normalized,
            {"kiti-duomenys": [{"pastaba": "Reikšmė", "tekstas": "Laisvas tekstas"}]},
        )

    def test_labelled_tekstas_key_does_not_swallow_recovered_free_text(self) -> None:
        # A labelled field can itself slugify to "tekstas". Deferring to it
        # would drop the unlabelled text and re-introduce exactly the silent
        # loss this whole branch exists to fix, so both are kept.
        payload = {
            "sections": [
                {
                    "title": "Kiti duomenys",
                    "records": [
                        {
                            "items": [
                                {"key": "Tekstas", "value": "Pažymėta reikšmė"},
                                {"key": "", "value": "Laisvas tekstas"},
                            ]
                        }
                    ],
                }
            ]
        }

        normalized = _normalize_privaciu_interesu_data(payload)

        self.assertEqual(
            normalized,
            {"kiti-duomenys": [{"tekstas": "Pažymėta reikšmė Laisvas tekstas"}]},
        )

    def test_multiple_unlabelled_items_are_joined(self) -> None:
        payload = {
            "sections": [
                {
                    "title": "Kiti duomenys",
                    "records": [
                        {
                            "items": [
                                {"key": "", "value": "Pirmas sakinys."},
                                {"key": "", "value": "Antras sakinys."},
                            ]
                        }
                    ],
                }
            ]
        }

        normalized = _normalize_privaciu_interesu_data(payload)

        self.assertEqual(
            normalized,
            {"kiti-duomenys": [{"tekstas": "Pirmas sakinys. Antras sakinys."}]},
        )

    def test_empty_unlabelled_items_still_produce_no_record(self) -> None:
        payload = {
            "sections": [
                {
                    "title": "Kiti duomenys",
                    "records": [{"items": [{"key": "", "value": "   "}]}],
                }
            ]
        }

        normalized = _normalize_privaciu_interesu_data(payload)

        self.assertEqual(normalized, {"kiti-duomenys": []})

    def test_savivaldybiu_2023_fixture_carries_free_text(self) -> None:
        record = _parse(
            parse_savivaldybiu_2023_sample, SAVIVALDYBIU_ELECTION_ID, ZEBRAUSKAS
        )

        declaration = record["normalized"]["privaciu-interesu-deklaracija"]

        self.assertEqual(declaration["kiti-duomenys"], [{"tekstas": self.FREE_TEXT}])


class EmptyDonationsSectionTests(unittest.TestCase):
    """Fix C: an inline "Duomenų nėra" heading must still yield a section."""

    INLINE_EMPTY = (
        '<div class="picklist tabinc">'
        "<h3>Gautos ir priimtos aukos: Duomenų nėra</h3>"
        "<h3>Nepriimtos aukos:</h3>Duomenų nėra"
        "</div>"
    )
    SEPARATE_EMPTY = (
        '<div class="picklist tabinc">'
        "<h3>Gautos ir priimtos aukos:</h3>Duomenų nėra"
        "</div>"
    )

    def test_inline_marker_still_produces_a_titled_section(self) -> None:
        sections = _parse_campaign_donations_html(self.INLINE_EMPTY)["sections"]

        titled = [s for s in sections if s.get("title") == "Gautos ir priimtos aukos"]
        self.assertEqual(len(titled), 1)
        self.assertEqual(titled[0]["status"], "noData")
        self.assertEqual(titled[0]["message"], "Duomenų nėra")

    def test_following_section_is_not_swallowed(self) -> None:
        # The bug dropped the first section because the second heading
        # overwrote the pending title; both must survive.
        sections = _parse_campaign_donations_html(self.INLINE_EMPTY)["sections"]

        self.assertEqual(len(sections), 2)

    def test_separately_rendered_marker_is_unchanged(self) -> None:
        # The pre-existing shape must keep parsing exactly as before.
        sections = _parse_campaign_donations_html(self.SEPARATE_EMPTY)["sections"]

        self.assertEqual(
            sections,
            [
                {
                    "title": "Gautos ir priimtos aukos",
                    "status": "noData",
                    "message": "Duomenų nėra",
                }
            ],
        )

    def test_savivaldybiu_2023_fixture_reports_its_empty_donations(self) -> None:
        record = _parse(
            parse_savivaldybiu_2023_sample, SAVIVALDYBIU_ELECTION_ID, MITROFANOVAS
        )

        sections = record["normalized"]["politines-kampanijos-dalyvio-duomenys"][0][
            "aukos-pagal-sekcija"
        ]

        self.assertEqual(
            sections,
            {
                "gautos-ir-priimtos-aukos": {
                    "title": "Gautos ir priimtos aukos",
                    "status": "noData",
                    "message": "Duomenų nėra",
                }
            },
        )


if __name__ == "__main__":
    unittest.main()
