import json
import tempfile
import unittest
from pathlib import Path

from scraper.elections.savivaldybiu_2007.anketa_parser import (
    normalize_municipal_2007_anketa_rows,
    parse_anketa_sample,
    split_family_members,
    split_merged_rows,
)
from scraper.elections.savivaldybiu_2007.candidate_samples import EXPECTED_TABS
from scraper.elections.savivaldybiu_2007.sitemap import ELECTION_ID
from scraper.elections.seimo_zirmunu_2015.anketa_parser import (
    _normalize_turto_ir_pajamu_data,
    _parse_interesu_html,
    parse_anketa_html,
)


REPO_ROOT = Path(__file__).resolve().parents[1]
SAMPLES_ROOT = REPO_ROOT / "samples" / "html" / "2007-vasario-25-savivaldybiu"


def _parse(candidate_id: str) -> dict:
    with tempfile.TemporaryDirectory() as tmp:
        output_path, _ = parse_anketa_sample(
            candidate_id=candidate_id, samples_root=SAMPLES_ROOT, output_root=Path(tmp)
        )
        return json.loads(output_path.read_text(encoding="utf-8"))


class Savivaldybiu2007AnketaParserTests(unittest.TestCase):
    """The 2015-era walkers on the family's oldest municipal pages: an
    unnumbered "label: <b>answer</b>" questionnaire keyed by its prompts,
    the plain-text card, the FR0462 income lines and the record-table
    interest declaration. The record shape is the 2011/2015 municipal one."""

    def setUp(self) -> None:
        self.vysniauskas = _parse("arvydas-vysniauskas-7357")
        self.zuokas = _parse("arturas-zuokas-12711")
        self.rope = _parse("bronis-rope-660")
        self.uspaskich = _parse("viktor-uspaskich-9852")
        self.pilvinis = _parse("zigfridas-herbertas-pilvinis-996")
        self.mileikiene = _parse("danute-mileikiene-3258")

    def test_records_carry_this_election_id_and_the_municipal_candidacy(self) -> None:
        self.assertEqual(ELECTION_ID, "2007-vasario-25-savivaldybiu")
        self.assertEqual(self.vysniauskas["electionId"], ELECTION_ID)
        self.assertEqual(self.vysniauskas["candidateId"], "arvydas-vysniauskas-7357")
        self.assertEqual(self.vysniauskas["candidateName"], "Arvydas Vyšniauskas")
        k = self.vysniauskas["kandidatavimas"]
        self.assertEqual(k["vrkCandidateId"], "7357")
        self.assertEqual(k["savivaldybe"], "Elektrėnų savivaldybė")
        self.assertEqual(k["roles"], ["tarybos-narys"])
        self.assertEqual(
            k["tarybosNarys"],
            {"partyList": "Lietuvos socialdemokratų partija", "listKind": "partija", "listNumber": 13, "listPosition": 1, "selfNominated": False},
        )
        # No mayor was elected directly in 2007.
        self.assertIsNone(k["meras"])
        self.assertTrue(
            self.vysniauskas["source"]["candidateSourceUrl"].endswith("/rinkimai/3/Kandidatai/Kandidatas7357/Kandidato7357Anketa.html")
        )

    def test_elected_status_comes_from_the_mandates_page(self) -> None:
        # Every winner is on VRK's "Mandatus gavę kandidatai" page of their
        # municipality, with an anketa link: an id join, no ranking arithmetic.
        k = self.zuokas["kandidatavimas"]
        self.assertIs(k["isrinktas"], True)
        self.assertEqual(k["isrinktasKaip"], "tarybos-narys")
        self.assertTrue(k["rezultatuSaltinis"].endswith("kand_mandatai_rapyg/kand_mand_rapyg6776.html"))
        self.assertNotIn("rezultatuTuras", k)
        # Uspaskich stood at position 25 of the Kėdainiai list and won on
        # preference votes; Mileikienė led a coalition that won no seat.
        self.assertIs(self.uspaskich["kandidatavimas"]["isrinktas"], True)
        self.assertEqual(self.uspaskich["kandidatavimas"]["tarybosNarys"]["listPosition"], 25)
        self.assertIs(self.mileikiene["kandidatavimas"]["isrinktas"], False)
        self.assertEqual(self.mileikiene["kandidatavimas"]["tarybosNarys"]["listKind"], "partiju-koalicija")

    def test_legacy_card_is_read_into_the_eras_fields(self) -> None:
        profile = self.vysniauskas["rawData"]["profile"]
        self.assertEqual(profile["candidateDisplayName"], "ARVYDAS VYŠNIAUSKAS")
        self.assertEqual(
            [(f["key"], f["displayValue"]) for f in profile["fields"]],
            [
                ("Apygarda", "Elektrėnų rinkimų apygarda (8 )"),
                ("Iškėlė", "Lietuvos socialdemokratų partija"),
                ("Numeris sąraše", "1"),
                ("Gimimo data", "1963-02-10"),
            ],
        )
        self.assertEqual(profile["photoSrc"], "")
        # A coalition member's card carries the position on the member
        # party's own share too.
        kita = self.rope["normalized"]["profilis"]["kita"]
        self.assertEqual(kita["iskele"]["reiksme"], "Lietuvos valstiečių liaudininkų ir krikščionių demokratų koalicija")
        self.assertEqual(kita["numeris-partijos-sarase"]["reiksme"], "1")
        self.assertEqual(kita["numeris-sarase"]["reiksme"], "1")
        self.assertNotIn("numeris-partijos-sarase", self.zuokas["normalized"]["profilis"]["kita"])

    def test_unnumbered_questions_are_keyed_by_prompt(self) -> None:
        a = self.vysniauskas["normalized"]["anketa"]
        self.assertEqual(
            list(a.keys()),
            [
                "gimimo-data", "adresas", "pareiskimai", "gimimo-vieta", "tautybe", "issilavinimas",
                "mokslo-laipsnis", "pedagoginis-vardas", "uzsienio-kalbos", "politine-organizacija",
                "anksciau-isrinktas", "pagrindine-darboviete", "visuomenine-veikla", "pomegiai",
                "seimine-padetis", "sutuoktinio-vardas-pavarde", "vaiku-vardai-pavardes", "seimos-nariai",
                "kita-apie-save",
            ],
        )
        # No Q5 on the 2007 form: the card's date lands under the anketa key.
        self.assertEqual(a["gimimo-data"], "1963-02-10")
        self.assertEqual(a["adresas"], "Elektrėnai")
        self.assertEqual(
            a["pareiskimai"],
            {
                "ar-nebaigta-teismo-paskirta-bausme": "Neturiu",
                "ar-atliekate-karo-tarnyba": "Nesu",
                "ar-eina-nesuderinamas-pareigas": "Neinu",
                "ar-kitos-valstybes-institucijos-narys": "Nesu",
                "ar-turite-kitos-valstybes-pilietybe": "Neturiu",
                "ar-pasyvioji-rinkimu-teise-neapribota": "Neapribota",
                "ar-buvote-pripazintas-kaltu": "Ne",
                "teisiniai-argumentai": None,
            },
        )
        self.assertEqual(a["gimimo-vieta"], "Radviliškis")
        self.assertEqual(a["tautybe"], "Lietuvis (-ė)")
        self.assertEqual(
            a["issilavinimas"]["irasai"],
            [{"issilavinimas": "Aukštasis", "mokymo-istaigos-pavadinimas": "Kauno politechnikos institutas", "specialybe": "inžinierius-elektrikas", "baigimo-metai": "1986"}],
        )
        self.assertEqual(a["uzsienio-kalbos"], ["Rusų", "Anglų"])
        self.assertEqual(a["politine-organizacija"], "Esu socialdemokratų partijos narys")
        self.assertEqual(
            a["anksciau-isrinktas"]["irasai"],
            [{"institucijos-pavadinimas-pareigos": "Elektrėnų savivaldybės tarybos narys", "laikotarpis": "2003 - 2007"}],
        )
        self.assertEqual(a["pagrindine-darboviete"], "Kruonio HAE, elektros cecho viršininko pavaduotojas")
        self.assertEqual(a["visuomenine-veikla"], "LSDP Elektrėnų skyriaus pirmininkas, LSDP tarybos narys")
        self.assertEqual(a["pomegiai"], "knygos, fotografija")
        self.assertEqual(a["seimine-padetis"], "Vedęs, ištekėjusi")
        self.assertIsNone(a["pedagoginis-vardas"])  # "Moksliniai vardai" printed only where there is one
        self.assertIsNone(a["kita-apie-save"])
        # The degree line is printed only where there is one.
        self.assertIsNone(a["mokslo-laipsnis"])
        self.assertEqual(self.zuokas["normalized"]["anketa"]["mokslo-laipsnis"], "Bakalauras")
        self.assertEqual(self.uspaskich["normalized"]["anketa"]["tautybe"], "Rusas (-ė)")

    def test_family_members_line_is_split_into_spouse_and_children(self) -> None:
        a = self.vysniauskas["normalized"]["anketa"]
        self.assertEqual(a["seimos-nariai"], "Sutuoktinis/sutuoktinė Vida, Vaikas Gintarė, Vaikas Ieva")
        self.assertEqual(a["sutuoktinio-vardas-pavarde"], "Vida")
        self.assertEqual(a["vaiku-vardai-pavardes"], "Gintarė, Ieva")
        self.assertEqual(
            self.uspaskich["normalized"]["anketa"]["vaiku-vardai-pavardes"], "Julija, Eduardas, Laura, Justė"
        )
        self.assertEqual(split_family_members("Sutuoktinis/sutuoktinė Laima Paksienė, Vaikas Mindaugas Paksas"), ("Laima Paksienė", "Mindaugas Paksas"))
        self.assertEqual(split_family_members("Vaikas Rokas"), (None, "Rokas"))
        self.assertEqual(split_family_members(None), (None, None))
        # A name without a role continues the role before it; a partner is
        # a spouse, a foster child a child, a grandchild neither.
        self.assertEqual(
            split_family_members("Vaikas Andrius, Tomas, Giedrius, Sutuoktinis/sutuoktinė Robertas"),
            ("Robertas", "Andrius, Tomas, Giedrius"),
        )
        self.assertEqual(
            split_family_members("Partneris/partnerė Vladas, Vaikas Simonas, Anūkas Jonas, Augintinis (-ė) Rikantė"),
            ("Vladas", "Simonas, Rikantė"),
        )

    def test_merged_prompts_are_split_on_the_forms_labels(self) -> None:
        # A question printed without its <b> joins the next label's prompt
        # and every answer after it lands one label early — the pasyvioji
        # question on 611 pages of the field. The split gives the missing
        # question a null and the answers back to their own labels.
        html = (
            '<div class="candidateInfo"><table><tr><td>X</td></tr></table></div>'
            '<div class="candidateInfo"><table><tr><td> Ar turite kitos valstybės pilietybę?: <br /> '
            'Ar pasyvioji rinkimų teisė nėra apribota valstybėje, kurios pilietis yra: <b> Neapribota </b> <br /> '
            'Ar turite ką nurodyti pagal Lietuvos Respublikos savivaldybių tarybų rinkimų įstatymo 89 straipsnio 1 dalyje išdėstytus reikalavimus: <b> Taip </b><br /> '
            '1995 m. teistas. Teistumo nebeturiu <br /> Gimimo vieta: <b>Zarasai</b> <br /> Tautybė: <b>Lietuvis (-ė)</b> </td></tr></table></div>'
        )
        parsed = parse_anketa_html(html, rows_normalizer=normalize_municipal_2007_anketa_rows)
        # rawData keeps the page's own run: the two labels in one prompt,
        # the explanation joined to "Gimimo vieta:".
        self.assertIn("Ar pasyvioji", parsed["anketa"]["rows"][0]["prompt"])
        self.assertTrue(parsed["anketa"]["rows"][2]["prompt"].endswith("Gimimo vieta:"))
        n = parsed["anketa"]["normalized"]
        self.assertIsNone(n["pareiskimai"]["ar-turite-kitos-valstybes-pilietybe"])
        self.assertEqual(n["pareiskimai"]["ar-pasyvioji-rinkimu-teise-neapribota"], "Neapribota")
        self.assertEqual(n["pareiskimai"]["ar-buvote-pripazintas-kaltu"], "Taip")
        # The bare explanation line after "Taip" is the explanation, and
        # "Gimimo vieta:" gets its own value back.
        self.assertEqual(n["pareiskimai"]["teisiniai-argumentai"], "1995 m. teistas. Teistumo nebeturiu")
        self.assertEqual(n["gimimo-vieta"], "Zarasai")
        self.assertEqual(n["tautybe"], "Lietuvis (-ė)")
        split = split_merged_rows(parsed["anketa"]["rows"])
        self.assertEqual(
            [(r["prompt"][:22], r["answer"]) for r in split],
            [("Ar turite kitos valsty", ""), ("Ar pasyvioji rinkimų t", "Neapribota"), ("Ar turite ką nurodyti ", "Taip"), ("1995 m. teistas. Teist", ""), ("Gimimo vieta:", "Zarasai"), ("Tautybė:", "Lietuvis (-ė)")],
        )
        # A "Taip" with nothing after it explains nothing.
        html_plain = html.replace("1995 m. teistas. Teistumo nebeturiu <br /> ", "")
        n2 = parse_anketa_html(html_plain, rows_normalizer=normalize_municipal_2007_anketa_rows)["anketa"]["normalized"]
        self.assertIsNone(n2["pareiskimai"]["teisiniai-argumentai"])
        self.assertEqual(n2["gimimo-vieta"], "Zarasai")

    def test_degree_and_title_lines(self) -> None:
        rows = [
            {"questionNumber": None, "prompt": "Moksliniai laipsniai:", "answer": "Daktaras", "rowIndex": 1},
            {"questionNumber": None, "prompt": "Moksliniai vardai:", "answer": "Profesorius", "rowIndex": 2},
        ]
        n = normalize_municipal_2007_anketa_rows(rows)
        self.assertEqual((n["mokslo-laipsnis"], n["pedagoginis-vardas"]), ("Daktaras", "Profesorius"))

    def test_empty_answer_closes_its_row(self) -> None:
        # Pilvinis's questionnaire stops after "Gimimo vieta: <b></b> Tautybė:
        # <b></b>": two unanswered rows, not one prompt made of both labels
        # — the shape that would credit the next value to the wrong label.
        rows = self.pilvinis["rawData"]["anketa"]["rows"]
        self.assertEqual([(r["prompt"], r["answer"]) for r in rows[-2:]], [("Gimimo vieta:", ""), ("Tautybė:", "")])
        a = self.pilvinis["normalized"]["anketa"]
        self.assertIsNone(a["gimimo-vieta"])
        self.assertIsNone(a["tautybe"])
        self.assertEqual(a["pareiskimai"]["ar-eina-nesuderinamas-pareigas"], "Einu")
        self.assertEqual(a["issilavinimas"]["irasai"], [])
        html = (
            '<div class="candidateInfo"><table><tr><td>X</td></tr></table></div>'
            '<div class="candidateInfo"><table><tr><td> Gimimo vieta: <b></b> <br /> Tautybė: <b>Lietuvis (-ė)</b> </td></tr></table></div>'
        )
        parsed = parse_anketa_html(html, rows_normalizer=normalize_municipal_2007_anketa_rows)
        self.assertIsNone(parsed["anketa"]["normalized"]["gimimo-vieta"])
        self.assertEqual(parsed["anketa"]["normalized"]["tautybe"], "Lietuvis (-ė)")

    def test_income_is_the_sum_of_the_fr0462_lines(self) -> None:
        # Five prose lines, one per form VRK knew of; the candidate filed one.
        raw = self.vysniauskas["rawData"]["turtoIrPajamuDeklaracijos"]["sections"][1]
        self.assertEqual(raw["title"], "Pajamų deklaracija")
        self.assertEqual([item["key"] for item in raw["items"]], [f"{f} Formos deklaracijos" for f in ("FR0462", "FR0462S33", "FR0462S15", "FR0462S0", "FR0462S")])
        t = self.vysniauskas["normalized"]["turto-ir-pajamu-deklaracijos"]
        self.assertEqual(t["gautos-pajamos"], 39019.3)
        self.assertEqual(t["sumoketas-pajamu-mokestis"], 11613)
        self.assertEqual(t["privalomas-registruoti-turtas"], 144000)
        self.assertEqual(t["valiuta"], "Lt")
        # Filed on the S variant: the non-zero line is not the first one.
        self.assertEqual(self.vysniauskas["normalized"]["turto-ir-pajamu-deklaracijos"]["pinigines-lesos"], 5366)
        self.assertEqual(_parse_fixture_income("vigantas-giedraitis-2544"), (60460, 18803))
        # All five at zero is a declared zero.
        self.assertEqual(self.mileikiene["normalized"]["turto-ir-pajamu-deklaracijos"]["gautos-pajamos"], 0)
        payload = {
            "sections": [{"title": "Pajamų deklaracija", "items": [
                {"key": "FR0462 Formos deklaracijos", "value": "Gauta 0 Lt , išskaičiuota pajamų mokesčio 0 Lt"},
                {"key": "FR0462S Formos deklaracijos", "value": "Gauta 100.50 Lt , išskaičiuota pajamų mokesčio 15.00 Lt"},
                {"key": "FR0462S33 Formos deklaracijos", "value": "Gauta 0.50 Lt , išskaičiuota pajamų mokesčio 0 Lt"},
            ]}],
            "note": "",
        }
        normalized = _normalize_turto_ir_pajamu_data(payload)
        self.assertEqual((normalized["gautos-pajamos"], normalized["sumoketas-pajamu-mokestis"]), (101, 15))

    def test_interest_declaration_record_tables_keep_every_row(self) -> None:
        # Column names are a row of bold cells, not <th>; two flats and two
        # employers are four rows, not two overwritten keys.
        interesai = self.vysniauskas["normalized"]["privaciu-interesu-deklaracija"]
        self.assertEqual(list(interesai.keys()), ["ii-turtas", "iii-pajamos"])
        self.assertEqual(
            interesai["ii-turtas"][:2],
            [
                {"tipas": "Butai daugiabučiuose namuose (statomi ar pastatyti)", "vienetu-skaicius": "1.0", "vietoves-pavadinimas": "Pakruojis", "isigijimo-budas": "pirkta"},
                {"tipas": "Butai daugiabučiuose namuose (statomi ar pastatyti)", "vienetu-skaicius": "1.0", "vietoves-pavadinimas": "Elektrėnai", "isigijimo-budas": "mainai"},
            ],
        )
        self.assertEqual(len(interesai["ii-turtas"]), 4)
        self.assertEqual(
            [row["pajamu-saltinio-pavadinimas"] for row in interesai["iii-pajamos"]],
            ["VšĮ Elektrėnų vaikų globos namai", "AB „Lietuvos energija“ Kruonio HAE"],
        )
        raw = self.vysniauskas["rawData"]["privaciuInteresuDeklaracija"]["sections"][0]
        self.assertEqual(raw["columns"], ["Tipas", "Vienetų skaičius", "Vietovės pavadinimas", "Įsigijimo būdas"])
        self.assertEqual(len(raw["rows"]), 4)
        # A key/value table of the same family (the 2011 declarant rows)
        # is not emphasised whole, so it still reads as items.
        html = (
            '<div class="candidateInfo"><table><tr><td>X</td></tr></table></div>'
            '<div class="candidateInfo"><table class="partydata"><tr><td>Deklaruojantis asmuo</td><td><b>JONAS JONAITIS</b></td></tr></table></div>'
        )
        parsed = _parse_interesu_html(html)
        self.assertEqual(parsed["sections"][0]["items"], [{"key": "Deklaruojantis asmuo", "value": "JONAS JONAITIS"}])
        self.assertNotIn("columns", parsed["sections"][0])

    def test_three_tabs_no_biography_no_kita_no_campaign(self) -> None:
        self.assertEqual(EXPECTED_TABS, {"anketa", "turto-ir-pajamu-deklaracijos", "interesu-deklaracija"})
        for record in (self.vysniauskas, self.zuokas, self.rope):
            self.assertEqual(
                list(record["normalized"].keys()),
                ["profilis", "anketa", "turto-ir-pajamu-deklaracijos", "privaciu-interesu-deklaracija"],
            )
            self.assertNotIn("politines-kampanijos-dalyvio-duomenys", record["normalized"])


def _parse_fixture_income(candidate_id: str) -> tuple:
    record = _parse(candidate_id)["normalized"]["turto-ir-pajamu-deklaracijos"]
    return record["gautos-pajamos"], record["sumoketas-pajamu-mokestis"]


if __name__ == "__main__":
    unittest.main()
