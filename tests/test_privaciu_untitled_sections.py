"""Regression tests for issue #100's private-interest section drops.

`normalize_privaciu_interesu_data` (scraper/shared/anketa_tabs.py, the copy
every 2007-2019-era module normalizes through; seimo_2016's until issue #90)
drops any section it cannot key — the sekcija-N fallback. Two real blocks used
to fall into it:

- the 2016-era spouse block: the page prints "Deklaruojančio asmens
  sutuoktinis, sugyventinis, partneris" as the table's first *row*, not a
  heading, so the section arrived untitled (1,415 records in 2016 Seimo,
  27 in 2019-09 Seimo, 11 in 2017 Anykščiai-Panevėžys, 6 in 2018 Zanavykai
  lost the spouse's name and workplace). The same section titles itself on
  the 2020-era pages and normalized there all along.
- the 2008 declarant block: the 2008 form says "Deklaruojantysis asmuo"
  where every later year says "Deklaruojantis asmuo", so the hoist that
  keys on the latter missed it and 1,602 records lost the two workplace
  lines beside the name.
"""

import json
import tempfile
import unittest
from pathlib import Path

from scraper.elections.seimo_2008.anketa_parser import (
    parse_anketa_sample as parse_seimo_2008_sample,
)
from scraper.shared.anketa_tabs import (
    normalize_privaciu_interesu_data as normalize_privaciu,
    parse_privaciu_interesu_html as parse_privaciu_html,
)

REPO_ROOT = Path(__file__).resolve().parents[1]

SPOUSE_KEY = "deklaruojancio-asmens-sutuoktinis-sugyventinis-partneris"


class UntitledSpouseSectionTests(unittest.TestCase):
    def test_untitled_spouse_block_is_titled_from_its_heading_row(self) -> None:
        payload = {
            "sections": [
                {
                    "title": "",
                    "sectionId": "",
                    "items": [
                        {"key": "Deklaruojančio asmens sutuoktinis, sugyventinis, partneris", "value": ""},
                        {"key": "Vardas", "value": "VYTAUTAS"},
                        {"key": "Pavardė", "value": "RUPŠYS"},
                        {
                            "key": "Sutuoktinio, sugyventinio, partnerio darbovietė (kitos darbovietės nurodomos ID001J priede)",
                            "value": "VALSTYBINĖ ĮMONĖ KURŠĖNŲ MIŠKŲ URĖDIJA",
                        },
                    ],
                }
            ]
        }
        normalized = normalize_privaciu(payload)
        self.assertEqual(
            normalized,
            {
                SPOUSE_KEY: {
                    "vardas": "VYTAUTAS",
                    "pavarde": "RUPŠYS",
                    "sutuoktinio-sugyventinio-partnerio-darboviete-kitos-darbovietes-nurodomos-id001j-priede": "VALSTYBINĖ ĮMONĖ KURŠĖNŲ MIŠKŲ URĖDIJA",
                }
            },
        )

    def test_other_untitled_sections_are_still_dropped(self) -> None:
        payload = {
            "sections": [
                {"title": "", "sectionId": "", "items": []},
                {"title": "", "sectionId": "", "items": [{"key": "Kažkas kita", "value": "reikšmė"}]},
            ]
        }
        self.assertEqual(normalize_privaciu(payload), {})

    def test_fixture_page_spouse_block_normalizes(self) -> None:
        html = (
            REPO_ROOT / "samples" / "html" / "2016-seimo" / "algirdas-butkevicius" / "privaciu-interesu-deklaracija.html"
        ).read_text(encoding="utf-8")
        normalized = normalize_privaciu(parse_privaciu_html(html))
        self.assertEqual(
            normalized[SPOUSE_KEY],
            {
                "vardas": "JANINA",
                "pavarde": "BUTKEVIČIENĖ",
                "sutuoktinio-sugyventinio-partnerio-darboviete-kitos-darbovietes-nurodomos-id001j-priede": "VĮ ENERGETIKOS AGENTŪRA",
            },
        )


class Seimo2008DeclarantHoistTests(unittest.TestCase):
    def test_declarantysis_block_hoists_with_its_workplace_lines(self) -> None:
        payload = {
            "sections": [
                {
                    "title": "",
                    "sectionId": "",
                    "items": [
                        {"key": "Deklaruojantysis asmuo", "value": "Juozas JARUŠEVIČIUS"},
                        {"key": "Darbovietė ir pareigos valstybinėje tarnyboje", "value": "LR Seimas, Seimo narys"},
                        {"key": "Kitos darbovietės, pareigos", "value": "Informacija nepateikta"},
                    ],
                }
            ]
        }
        self.assertEqual(
            normalize_privaciu(payload),
            {
                "deklaruojantysis-asmuo": "Juozas JARUŠEVIČIUS",
                "darboviete-ir-pareigos-valstybineje-tarnyboje": "LR Seimas, Seimo narys",
                "kitos-darbovietes-pareigos": "Informacija nepateikta",
            },
        )

    def test_fixture_record_keeps_workplace_lines(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output_path, stats = parse_seimo_2008_sample("andrius-kubilius", output_root=Path(tmp))
            record = json.loads(output_path.read_text(encoding="utf-8"))
        declaration = record["normalized"]["privaciu-interesu-deklaracija"]
        self.assertEqual(declaration["deklaruojantysis-asmuo"], "Andrius KUBILIUS")
        self.assertEqual(
            declaration["darboviete-ir-pareigos-valstybineje-tarnyboje"],
            "Lietuvos Respublikos Seimas, Seimo narys",
        )
        self.assertEqual(declaration["kitos-darbovietes-pareigos"], "Informacija nepateikta")


if __name__ == "__main__":
    unittest.main()
