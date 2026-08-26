"""The card grammar both 1996-1998 archive families read.

The municipal fixture set in `samples/html/` predates issue #69 and carries
none of the four labels that fix added, so the paragraphs below are lifted
verbatim from real pages under `samples-full/` -- `adamonis-donatas` of the
1997 municipal general election for the municipal card (the candidate whose
"Moksliniai laipsniai: Technikos mokslų daktaras" and "Moksliniai vardai:
Docentas" appeared nowhere in his stored record), and `alesionka-leonas` of
the 1996 Seimas general election for the Seimas one.
"""

import unittest

from bs4 import BeautifulSoup

from scraper.shared.archive_1990s_card import (
    FIELD_LABELS,
    bold_values,
    education_record,
    family_concepts,
    family_members,
    field_value,
    previously_elected_record,
)
from scraper.shared.savivaldybiu_archive_1997 import parse_candidate_detail as parse_municipal
from scraper.shared.seimo_archive_1990s import parse_candidate_detail as parse_seimas

# adamonis-donatas, 1997-kovo-23-savivaldybiu-tarybu.
MUNICIPAL_CARD = """
<blockquote>
 <p>Apygarda: <b><a href="apgtl.htm-3+5.htm">Kauno miesto</a> (Nr. 5)</b><br />
    Iškėlė: <b><a href="pkal.htm-148+6.htm">Lietuvos politinių kalinių ir tremtinių sąjunga</a></b>
    <br />Numeris sąraše: <b>5</b></p>
 <p>Gimimo data: <b>1939 11 07</b> <br />Gyvenamoji vieta: <b>Kaunas </b>
    <br />Tautybė: <b>Lietuvis (-ė)</b> <font size="-1"> </font></p>
 <p><font size="-1">Nurodo, vykdydamas Lietuvos Respublikos Seimo rinkimų įstatymo 97
    straipsnio 1 dalyje išdėstytą nuostatą: <b>ne</b></font> </p>
 <p>Išsilavinimas: <b>Aukštasis</b> </p>
 <p>Moksliniai laipsniai: &nbsp;&nbsp;<b>Technikos mokslų daktaras</b> </p>
 <p>Moksliniai vardai: &nbsp;&nbsp;<b>Docentas</b> </p>
 <p>Užsienio kalbos: &nbsp;&nbsp;<b>Anglų</b> &nbsp;&nbsp;<b>Rusų</b> </p>
 <p>Pagrindinė darbovietė: <b>Lietuvos žemės ūkio universitetas</b> </p>
 <p>Visuomeninė veikla: <b>Ž.Ū. inžinerijos fakulteto tarybos pirmininkas</b> </p>
 <p>Šeimyninė padėtis: <b>Vedęs</b> </p>
 <p>Šeimos nariai: <br /> <b>Rima</b> - Sutuoktinis/sutuoktinė<br />
    <b>Gintaras</b> - Vaikas<br /> <b>Linas</b> - Vaikas<br /> </p>
 <p><a href="kpdl.htm-15776.htm">Pajamų deklaracija</a> </p>
</blockquote>
"""

# alesionka-leonas, 1996-spalio-20-seimo. The `<!--sql format>` marker opens a
# comment that only the stray `-->` far below closes, so everything between
# them -- birthplace, residence, nationality and the boilerplate eligibility
# Q&A -- is invisible to a DOM parser.
SEIMAS_CARD = """
<blockquote>
 <p><br /> Apygarda: <b><a href="apgtl.htm-1+57.htm">Vilniaus Trakų</a> (Nr. 57)</b><br />
    Iškėlė: <a href="partr2l.htm-3.htm"><b>Lietuvos demokratinė darbo partija</b></a> </p>
 <p>
  <!--sql format>
Klaida užklausoje.<br>
<br>Gimimo vieta: <b>Melagėnų k. , Švenčionių raj.</b>
<br>Gyvenamoji vieta: <b>Anykščiai , Anykščių raj.</b>
<br>Tautybė: <b>Lietuvis (-ė)</b>
<!--
<p>Ar neturi nebaigtos atlikti teismo nuosprendžiu paskirtos bausmės: <b>Neturi</b>
--> </p>
 <p>Išsilavinimas: <b>Aukštasis</b> </p>
 <p>Užsienio kalbos: &nbsp;&nbsp;<b>Anglų</b> &nbsp;&nbsp;<b>Rusų</b> </p>
 <p>Buvo išrinktas į Lietuvos Respublikos Aukščiausiąją Tarybą, Seimą, savivaldybių tarybas:
    <br /><b>Lietuvos Respublikos Seimas</b> </p>
 <p>Visuomeninė veikla: <b>Tarptautinė medikų parlamentarų organizacija,narys</b> </p>
 <p>Šeimyninė padėtis: <b>Nevedęs</b> </p>
 <p>Ką dar norėtų parašyti apie save: <b>noriu tęsti sveikatos sistemos reformą</b> </p>
 <p><a href="kpdl.htm-3567.htm">Pajamų deklaracija</a> </p>
</blockquote>
"""


def paragraph(html: str, starts_with: str):
    soup = BeautifulSoup(html, "lxml")
    for para in soup.find_all("p"):
        if " ".join(para.get_text(" ", strip=True).split()).startswith(starts_with):
            return para
    raise AssertionError(f"no paragraph starting {starts_with!r}")


class FieldValueTests(unittest.TestCase):
    """The stop-list reader for the municipal card, whose birth-date paragraph
    packs four labels into one."""

    PACKED = "Gimimo data: 1945 04 17 Gyvenamoji vieta: Kaunas Tautybė: Lietuvis (-ė)"

    def test_a_value_stops_at_whichever_label_comes_next(self) -> None:
        # The bug this guards: stopping only at the caller's expected
        # successor ran to the end of the paragraph whenever that label was
        # absent, which put the whole tail into 91% of birth-date values.
        self.assertEqual(field_value(self.PACKED, "Gimimo data"), "1945 04 17")
        self.assertEqual(field_value(self.PACKED, "Gyvenamoji vieta"), "Kaunas")

    def test_the_last_value_runs_to_the_end(self) -> None:
        self.assertEqual(field_value(self.PACKED, "Tautybė"), "Lietuvis (-ė)")

    def test_an_absent_label_yields_nothing(self) -> None:
        self.assertEqual(field_value(self.PACKED, "Išsilavinimas"), "")

    def test_the_label_list_is_the_union_of_both_cards(self) -> None:
        # Named outright rather than derived, because the tests below iterate
        # FIELD_LABELS: without this, dropping a label would silently drop its
        # own coverage with it. The last four are the Seimas card's, and their
        # absence here is what cost the municipal family 156 academic degrees
        # and 112 titles in the 1997 general election.
        self.assertEqual(
            set(FIELD_LABELS),
            {
                "Gimimo data", "Gimimo vieta", "Gyvenamoji vieta", "Tautybė",
                "Išsilavinimas", "Užsienio kalbos", "Pagrindinė darbovietė",
                "Visuomeninė veikla", "Šeimyninė padėtis", "Šeimos nariai",
                "Apygarda", "Iškėlė", "Numeris sąraše",
                "Moksliniai laipsniai", "Moksliniai vardai",
                "Buvo išrinktas", "Ką dar norėtų parašyti apie save",
            },
        )

    def test_every_label_is_a_stop_label(self) -> None:
        # A label missing from FIELD_LABELS is not merely unread -- it gets
        # swallowed into the value before it. So each one has to stop the
        # scan, including the sentence-length "Buvo išrinktas ..." whose
        # colon is 60 characters after the prefix.
        for label in FIELD_LABELS:
            if label == "Išsilavinimas":
                continue
            # Only this one prints a sentence between its prefix and its colon.
            tail = (
                " į Lietuvos Respublikos Aukščiausiąją Tarybą, Seimą, savivaldybių tarybas"
                if label == "Buvo išrinktas"
                else ""
            )
            with self.subTest(label):
                text = f"Išsilavinimas: Aukštasis {label}{tail}: liktų"
                self.assertEqual(field_value(text, "Išsilavinimas"), "Aukštasis")


class BoldValueTests(unittest.TestCase):
    def test_one_entry_per_bold_run(self) -> None:
        self.assertEqual(
            [item["value"] for item in bold_values(paragraph(MUNICIPAL_CARD, "Užsienio kalbos"))],
            ["Anglų", "Rusų"],
        )

    def test_the_trailing_text_becomes_the_note(self) -> None:
        self.assertEqual(
            bold_values(paragraph(MUNICIPAL_CARD, "Šeimos nariai"))[0],
            {"value": "Rima", "note": "Sutuoktinis/sutuoktinė"},
        )

    def test_an_empty_bold_is_not_a_value(self) -> None:
        # One 1996 card prints "Užsienio kalbos: <b></b>" and one prints an
        # empty "Moksliniai laipsniai" -- a label with no answer, which must
        # not become an empty-string value.
        soup = BeautifulSoup("<p>Užsienio kalbos: <b></b> </p>", "lxml")
        self.assertEqual(bold_values(soup.find("p")), [])


class FamilyTests(unittest.TestCase):
    def test_members_carry_name_and_relation(self) -> None:
        self.assertEqual(
            family_members(paragraph(MUNICIPAL_CARD, "Šeimos nariai")),
            [
                {"name": "Rima", "relation": "Sutuoktinis/sutuoktinė"},
                {"name": "Gintaras", "relation": "Vaikas"},
                {"name": "Linas", "relation": "Vaikas"},
            ],
        )

    def test_the_two_keyed_roles_are_split_out(self) -> None:
        spouse, children = family_concepts(
            family_members(paragraph(MUNICIPAL_CARD, "Šeimos nariai"))
        )
        self.assertEqual(spouse, "Rima")
        self.assertEqual(children, "Gintaras, Linas")

    def test_other_relations_belong_to_neither_concept(self) -> None:
        # "Augintinis (ė)" and "Anūkas (ė)" appear twice each across the whole
        # archive era and are neither a spouse nor a child.
        spouse, children = family_concepts([{"name": "Ona", "relation": "Anūkas (ė)"}])
        self.assertIsNone(spouse)
        self.assertIsNone(children)


class ShapeHelperTests(unittest.TestCase):
    def test_the_education_level_fills_the_modern_entry_field(self) -> None:
        self.assertEqual(
            education_record("Aukštasis"),
            {
                "aprasas": None,
                "irasai": [
                    {
                        "issilavinimas": "Aukštasis",
                        "mokymo-istaigos-pavadinimas": None,
                        "specialybe": None,
                        "baigimo-metai": None,
                    }
                ],
            },
        )

    def test_no_level_stays_null_rather_than_an_empty_object(self) -> None:
        self.assertIsNone(education_record(""))
        self.assertIsNone(previously_elected_record([]))

    def test_each_named_body_becomes_one_entry_without_a_term(self) -> None:
        self.assertEqual(
            previously_elected_record(["Lietuvos Respublikos Seimas", "Kauno miesto taryba"]),
            {
                "aprasas": None,
                "irasai": [
                    {"institucijos-pavadinimas-pareigos": "Lietuvos Respublikos Seimas",
                     "laikotarpis": None},
                    {"institucijos-pavadinimas-pareigos": "Kauno miesto taryba",
                     "laikotarpis": None},
                ],
            },
        )


class MunicipalCardTests(unittest.TestCase):
    def setUp(self) -> None:
        self.personal = parse_municipal(MUNICIPAL_CARD, "https://example.invalid/kandvl.htm")[
            "personal"
        ]

    def test_the_two_labels_the_parser_used_to_drop(self) -> None:
        # 156 degrees and 112 titles in the 1997 general election were on the
        # page and in no record until issue #69.
        self.assertEqual(self.personal["academicDegree"], "Technikos mokslų daktaras")
        self.assertEqual(self.personal["academicTitle"], "Docentas")

    def test_the_fields_it_already_read_are_unchanged(self) -> None:
        self.assertEqual(self.personal["birthDate"], "1939-11-07")
        self.assertEqual(self.personal["residence"], "Kaunas")
        self.assertEqual(self.personal["nationality"], "Lietuvis (-ė)")
        self.assertEqual(self.personal["education"], "Aukštasis")
        self.assertEqual(self.personal["foreignLanguages"], ["Anglų", "Rusų"])
        self.assertEqual(self.personal["mainWorkplace"], "Lietuvos žemės ūkio universitetas")

    def test_the_eligibility_paragraph_is_not_a_field(self) -> None:
        # "Nurodo, vykdydamas ... nuostatą: ne" is boilerplate, matches no
        # label, and must not land anywhere.
        self.assertNotIn("Nurodo", str(self.personal))
        self.assertEqual(self.personal["aboutSelf"], "")
        self.assertEqual(self.personal["previouslyElected"], [])


class SeimasCardTests(unittest.TestCase):
    def setUp(self) -> None:
        self.detail = parse_seimas(SEIMAS_CARD, "https://example.invalid/kandvl.htm")
        self.personal = self.detail["personal"]

    def test_the_three_commented_fields_are_recovered_by_regex(self) -> None:
        # A DOM parser sees none of these: they sit inside the comment the
        # broken "<!--sql format>" marker opens.
        self.assertEqual(self.detail["residence"], "Anykščiai , Anykščių raj.")
        self.assertEqual(self.personal["birthPlace"], "Melagėnų k. , Švenčionių raj.")
        self.assertEqual(self.personal["nationality"], "Lietuvis (-ė)")

    def test_the_commented_eligibility_boilerplate_stays_out(self) -> None:
        # It is the failed query's default rendering, identical on every page,
        # not an answer -- so it is discarded rather than stored.
        self.assertNotIn("Neturi", str(self.personal))

    def test_the_paragraph_labels_are_read(self) -> None:
        self.assertEqual(self.personal["education"], "Aukštasis")
        self.assertEqual(self.personal["foreignLanguages"], ["Anglų", "Rusų"])
        self.assertEqual(self.personal["familyStatus"], "Nevedęs")
        self.assertEqual(self.personal["aboutSelf"], "noriu tęsti sveikatos sistemos reformą")

    def test_the_sentence_length_previously_elected_label_is_matched(self) -> None:
        self.assertEqual(self.personal["previouslyElected"], ["Lietuvos Respublikos Seimas"])

    def test_a_label_the_card_omits_reads_as_blank(self) -> None:
        self.assertEqual(self.personal["academicDegree"], "")
        self.assertEqual(self.personal["mainWorkplace"], "")
        self.assertEqual(self.personal["familyMembers"], [])


if __name__ == "__main__":
    unittest.main()
