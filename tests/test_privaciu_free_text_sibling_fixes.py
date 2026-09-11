"""Regression tests for the sibling copies of the privačių interesų free-text
recovery first shipped for ep_2024 (the "tekstas" fix).

The 2023-03-05 municipal fix rescued declaration items published with an empty
label. Auditing the sibling parsers against the full-run rawData corpora showed
the same free text is more often published the other way round: as a one-cell
row in a header-bearing table, which the raw parsers read as a *label*, so the
normalizers turned the whole declared sentence into an ASCII slug key with a
null value (62 records in 2016 Seimo, 97 in 2020 Seimo, 146 in 2024 Seimo,
29 in 2024 EP across the full runs).

The fix has two halves, mirrored into each affected copy:

  - raw parsers (seimo_2016's, now anketa_tabs.parse_privaciu_interesu_html
    since issue #90, seimo_2020._parse_privaciu_interesu_html,
    seimo_2024/ep_2024._parse_privaciu_record_table) treat a one-cell row in a
    table that carries column headers as an unlabelled data row of a
    single-column table, not a label;
  - normalizers (seimo_2016's, now anketa_tabs.normalize_privaciu_interesu_data,
    and seimo_2020's and seimo_2024's _normalize_privaciu_interesu_data)
    collect unlabelled values under "tekstas", exactly like the fixed ep_2024
    copy.

One-cell rows in header-less tables (spouse/workplace group labels such as
"Darbovietė") must keep their label semantics — the 2021-2023 mayoral pages
publish thousands of those.
"""

import json
import tempfile
import unittest
from pathlib import Path

from scraper.elections.ep_2024.anketa_parser import (
    _parse_privaciu_interesu_html as parse_ep_2024_privaciu_html,
)
from scraper.elections.kupiskio_mero_2023.anketa_parser import (
    parse_anketa_sample as parse_kupiskio_2023_sample,
)
from scraper.elections.meru_2025.anketa_parser import (
    parse_anketa_sample as parse_meru_2025_sample,
)
from scraper.elections.prezidento_2024.anketa_parser import (
    parse_anketa_sample as parse_prezidento_2024_sample,
)
from scraper.elections.seimo_2019.anketa_parser import (
    parse_anketa_sample as parse_seimo_2019_sample,
)
from scraper.elections.seimo_2020.anketa_parser import (
    _normalize_privaciu_interesu_data as normalize_seimo_2020_privaciu,
    _parse_privaciu_interesu_html as parse_seimo_2020_privaciu_html,
)
from scraper.elections.seimo_2024.anketa_parser import (
    _normalize_privaciu_interesu_data as normalize_seimo_2024_privaciu,
    _parse_privaciu_interesu_html as parse_seimo_2024_privaciu_html,
)
from scraper.elections.seimo_zanavyku_2018.anketa_parser import (
    parse_anketa_sample as parse_zanavykai_2018_sample,
)
from scraper.shared.anketa_tabs import (
    normalize_privaciu_interesu_data as normalize_seimo_2016_privaciu,
    parse_privaciu_interesu_html as parse_seimo_2016_privaciu_html,
)


REPO_ROOT = Path(__file__).resolve().parents[1]
SAMPLES_ROOT = REPO_ROOT / "samples" / "html"


def _parse(parse_fn, election_id: str, candidate_id: str) -> dict:
    with tempfile.TemporaryDirectory() as tmp:
        output_path, _ = parse_fn(
            candidate_id=candidate_id,
            samples_root=SAMPLES_ROOT / election_id,
            output_root=Path(tmp),
        )
        return json.loads(output_path.read_text(encoding="utf-8"))


# The 2016-era markup: the ID001A free text is a lone <td> row in a table
# whose real column labels live in <thead>.
SEIMO_2016_KITI_HTML = """
<div>
<table class="tabinc partydata" border="1">
<h4 align="left" class="h4apgKom">ID001A KITI DUOMENYS</h4>
<thead>
<tr><th>Kiti duomenys, dėl kurių gali kilti interesų konfliktas</th></tr>
</thead>
<tr><td>TURIU ŠIŲ ĮMONIŲ AKCIJŲ: AB „APRANGA“, AB „LITGRID“.</td></tr>
</table>
</div>
"""

# The spouse block is also published as one-cell rows, but its table carries
# no column headers — those rows are group labels, not free text.
SEIMO_2016_LABEL_HTML = """
<div>
<table class="tabinc partydata" border="1">
<tr><td>Deklaruojančio asmens sutuoktinis, sugyventinis, partneris:</td></tr>
<tr><td>PAPILDOMA PASTABA</td></tr>
<tr><td>Vardas:</td><td>HENRIKAS</td></tr>
</table>
</div>
"""

# The 2024-era markup: an h4 section heading, then a table whose single
# column is headed by a <th> and whose one body row is the unlabelled text.
SEIMO_2024_KITI_HTML = """
<div>
<ul id="tabnav"></ul>
<h4 class="h4apgKom pid-table-title">Kiti duomenys</h4>
<table class="partydata defaultSize tableKand">
<thead><tr><th class="tableKandTitle">Kiti duomenys ar aplinkybės</th></tr></thead>
<tr><td>Sesuo dirba ministerijos audito skyriuje.</td></tr>
</table>
</div>
"""

# The 2021-2023 mayoral markup publishes workplace records as one-cell group
# labels ("Darbovietė") in tables without any <th> — they must stay labels.
EP_2024_LABEL_HTML = """
<div>
<ul id="tabnav"></ul>
<h4 class="h4apgKom pid-table-title">Deklaruojančio darbovietės</h4>
<table class="partydata">
<tr><td>Darbovietė</td></tr>
<tr><td>Pavadinimas</td><td><b>UAB Bandymas</b></td></tr>
</table>
</div>
"""

# In the same mayoral family the Kiti duomenys text is wrapped in <b> inside a
# header-less table; it must keep flowing to the empty-key path.
EP_2024_BOLD_KITI_HTML = """
<div>
<ul id="tabnav"></ul>
<h4 class="h4apgKom pid-table-title">Kiti duomenys</h4>
<table class="partydata">
<tr><td><b>Šaulių sąjungos narė</b></td></tr>
</table>
</div>
"""


class Seimo2016PrivaciuFreeTextTests(unittest.TestCase):
    FREE_TEXT = "TURIU ŠIŲ ĮMONIŲ AKCIJŲ: AB „APRANGA“, AB „LITGRID“."

    def test_one_cell_row_in_header_table_is_unlabelled(self) -> None:
        payload = parse_seimo_2016_privaciu_html(SEIMO_2016_KITI_HTML)

        (section,) = payload["sections"]
        self.assertEqual(section["sectionId"], "id001a")
        self.assertEqual(section["items"], [{"key": "", "value": self.FREE_TEXT}])

    def test_one_cell_row_without_headers_stays_a_label(self) -> None:
        payload = parse_seimo_2016_privaciu_html(SEIMO_2016_LABEL_HTML)

        (section,) = payload["sections"]
        self.assertIn({"key": "PAPILDOMA PASTABA", "value": ""}, section["items"])
        self.assertIn({"key": "Vardas", "value": "HENRIKAS"}, section["items"])

    def test_unlabelled_item_survives_as_tekstas(self) -> None:
        payload = parse_seimo_2016_privaciu_html(SEIMO_2016_KITI_HTML)

        normalized = normalize_seimo_2016_privaciu(payload)

        self.assertEqual(normalized, {"id001a": {"tekstas": self.FREE_TEXT}})

    def test_tekstas_label_collision_keeps_both(self) -> None:
        payload = {
            "sections": [
                {
                    "title": "ID001A KITI DUOMENYS",
                    "sectionId": "id001a",
                    "items": [
                        {"key": "Tekstas", "value": "Pažymėta reikšmė"},
                        {"key": "", "value": "Laisvas tekstas"},
                    ],
                }
            ]
        }

        normalized = normalize_seimo_2016_privaciu(payload)

        self.assertEqual(
            normalized,
            {"id001a": {"tekstas": "Pažymėta reikšmė Laisvas tekstas"}},
        )


class Seimo2020PrivaciuFreeTextTests(unittest.TestCase):
    FREE_TEXT = "TURIU ŠIŲ ĮMONIŲ AKCIJŲ: AB „APRANGA“, AB „LITGRID“."

    def test_one_cell_row_in_header_table_is_unlabelled(self) -> None:
        payload = parse_seimo_2020_privaciu_html(SEIMO_2016_KITI_HTML)

        (section,) = payload["sections"]
        self.assertEqual(section["sectionId"], "id001a")
        self.assertEqual(section["items"], [{"key": "", "value": self.FREE_TEXT}])

    def test_unlabelled_item_survives_as_tekstas(self) -> None:
        payload = parse_seimo_2020_privaciu_html(SEIMO_2016_KITI_HTML)

        normalized = normalize_seimo_2020_privaciu(payload)

        self.assertEqual(normalized, {"id001a": {"tekstas": self.FREE_TEXT}})

    def test_tekstas_label_collision_keeps_both(self) -> None:
        payload = {
            "sections": [
                {
                    "title": "ID001A KITI DUOMENYS",
                    "sectionId": "id001a",
                    "items": [
                        {"key": "Tekstas", "value": "Pažymėta reikšmė"},
                        {"key": "", "value": "Laisvas tekstas"},
                    ],
                }
            ]
        }

        normalized = normalize_seimo_2020_privaciu(payload)

        self.assertEqual(
            normalized,
            {"id001a": {"tekstas": "Pažymėta reikšmė Laisvas tekstas"}},
        )


class Seimo2024PrivaciuFreeTextTests(unittest.TestCase):
    FREE_TEXT = "Sesuo dirba ministerijos audito skyriuje."

    def test_one_cell_row_in_header_table_is_unlabelled(self) -> None:
        payload = parse_seimo_2024_privaciu_html(SEIMO_2024_KITI_HTML)

        (section,) = payload["sections"]
        self.assertEqual(section["title"], "Kiti duomenys")
        (record,) = section["records"]
        self.assertEqual(record["recordType"], "Kiti duomenys ar aplinkybės")
        self.assertEqual(record["items"], [{"key": "", "value": self.FREE_TEXT}])

    def test_unlabelled_item_survives_as_tekstas(self) -> None:
        payload = parse_seimo_2024_privaciu_html(SEIMO_2024_KITI_HTML)

        normalized = normalize_seimo_2024_privaciu(payload)

        self.assertEqual(normalized, {"kiti-duomenys": [{"tekstas": self.FREE_TEXT}]})

    def test_tekstas_label_collision_keeps_both(self) -> None:
        payload = {
            "sections": [
                {
                    "title": "Kiti duomenys",
                    "records": [
                        {
                            "items": [
                                {"key": "Tekstas", "value": "Pažymėta reikšmė"},
                                {"key": "", "value": "Laisvas tekstas"},
                            ],
                        }
                    ],
                }
            ]
        }

        normalized = normalize_seimo_2024_privaciu(payload)

        self.assertEqual(
            normalized,
            {"kiti-duomenys": [{"tekstas": "Pažymėta reikšmė Laisvas tekstas"}]},
        )


class Ep2024PrivaciuRecordTableTests(unittest.TestCase):
    def test_one_cell_row_in_header_table_is_unlabelled(self) -> None:
        payload = parse_ep_2024_privaciu_html(SEIMO_2024_KITI_HTML)

        (section,) = payload["sections"]
        (record,) = section["records"]
        self.assertEqual(
            record["items"],
            [{"key": "", "value": "Sesuo dirba ministerijos audito skyriuje."}],
        )

    def test_one_cell_group_label_without_headers_stays_a_label(self) -> None:
        payload = parse_ep_2024_privaciu_html(EP_2024_LABEL_HTML)

        (section,) = payload["sections"]
        (record,) = section["records"]
        self.assertEqual(
            record["items"],
            [
                {"key": "Darbovietė", "value": ""},
                {"key": "Pavadinimas", "value": "UAB Bandymas"},
            ],
        )

    def test_bold_free_text_without_headers_keeps_empty_key(self) -> None:
        payload = parse_ep_2024_privaciu_html(EP_2024_BOLD_KITI_HTML)

        (section,) = payload["sections"]
        (record,) = section["records"]
        self.assertEqual(record["items"], [{"key": "", "value": "Šaulių sąjungos narė"}])


class FixtureFreeTextRecoveryTests(unittest.TestCase):
    """End to end over the retained fixture corpora, one per parser path."""

    def test_zanavykai_2018_id001a_free_text(self) -> None:
        record = _parse(
            parse_zanavykai_2018_sample, "2018-rugsejo-16-seimo-zanavykai", "giedrius-surplys"
        )

        declaration = record["normalized"]["privaciu-interesu-deklaracija"]
        self.assertEqual(
            declaration["id001a"],
            {
                "tekstas": (
                    "ĮMONĖ, KURIOJE DIRBA MANO ŽMONA LINA BANYTĖ-SURPLIENĖ, "
                    "2017-08-11 D. YRA SUDARIUSI SUTARTĮ NR. 8P-17-134 SU ŽŪM."
                )
            },
        )

    def test_seimo_2019_id001a_free_text(self) -> None:
        record = _parse(parse_seimo_2019_sample, "2019-rugsejo-8-seimo", "saulius-gegieckas")

        declaration = record["normalized"]["privaciu-interesu-deklaracija"]
        self.assertEqual(
            declaration["id001a"],
            {"tekstas": "TRENERIO VEIKLA (NUMERIS 85.51) VYKDOMA VERSLO LIUDIJIMO PAGRINDU."},
        )

    def test_prezidento_2024_kiti_duomenys_free_text(self) -> None:
        record = _parse(parse_prezidento_2024_sample, "2024-prezidento", "gitanas-nauseda")

        declaration = record["normalized"]["privaciu-interesu-deklaracija"]
        self.assertEqual(
            declaration["kiti-duomenys"],
            [
                {
                    "tekstas": (
                        "SESUO DIRBA EKONOMIKOS IR INOVACIJŲ MINISTERIJOS "
                        "CENTRALIZUOTO VIDAUS AUDITO SKYRIAUS VYRESNIĄJA PATARĖJA"
                    )
                }
            ],
        )

    def test_meru_2025_kiti_duomenys_free_text(self) -> None:
        record = _parse(parse_meru_2025_sample, "2025-kovo-16-meru", "gediminas-cepulis")

        declaration = record["normalized"]["privaciu-interesu-deklaracija"]
        self.assertEqual(
            declaration["kiti-duomenys"], [{"tekstas": "Dukra Justina Vinickienė"}]
        )

    def test_kupiskio_2023_workplace_group_labels_survive(self) -> None:
        # Negative control: the mayoral pages publish "Darbovietė" as a
        # one-cell group label in a header-less table; the free-text recovery
        # must not swallow it.
        record = _parse(
            parse_kupiskio_2023_sample, "2023-spalio-8-kupiskio-mero", "algirdas-raslanas"
        )

        declaration = record["normalized"]["privaciu-interesu-deklaracija"]
        workplaces = declaration["deklaruojancio-darbovietes"]
        self.assertTrue(workplaces)
        for workplace in workplaces:
            self.assertIn("darboviete", workplace)
            self.assertNotIn("tekstas", workplace)


if __name__ == "__main__":
    unittest.main()
