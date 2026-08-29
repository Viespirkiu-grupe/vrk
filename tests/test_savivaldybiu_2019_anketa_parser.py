import json
import re
import tempfile
import unittest
from pathlib import Path

from scraper.elections.savivaldybiu_2019.anketa_parser import parse_anketa_sample
from scraper.elections.savivaldybiu_2019.candidate_samples import expected_tabs_for


REPO_ROOT = Path(__file__).resolve().parents[1]
SAMPLES_ROOT = REPO_ROOT / "samples" / "html" / "2019-kovo-3-savivaldybiu-tarybu"

ELECTION_ID = "2019-kovo-3-savivaldybiu-tarybu"

# Council-only candidates publish five tabs; the campaign tab appears only for
# the people who also stand for mayor (see the candidate_samples tests below).
BASE_SECTIONS = [
    "profilis",
    "anketa",
    "biografija",
    "turto-ir-pajamu-deklaracijos",
    "privaciu-interesu-deklaracija",
    "kita",
]
MAYORAL_SECTIONS = [
    "profilis",
    "anketa",
    "biografija",
    "turto-ir-pajamu-deklaracijos",
    "privaciu-interesu-deklaracija",
    "politines-kampanijos-dalyvio-duomenys",
    "kita",
]

# The anketa is the 2016/2017 vintage: the biography questions (Q10-Q21) live
# inside it, so there is no separate biography question block and biografija is
# a free-text tab.
ANKETA_KEYS = [
    "gimimo-data",
    "adresas",
    "pareiskimai",
    "gimimo-vieta",
    "tautybe",
    "issilavinimas",
    "pedagoginis-vardas",
    "uzsienio-kalbos",
    "politine-organizacija",
    "anksciau-isrinktas",
    "pagrindine-darboviete",
    "visuomenine-veikla",
    "pomegiai",
    "seimine-padetis",
    "sutuoktinio-vardas-pavarde",
    "vaiku-vardai-pavardes",
    "kita-apie-save",
    "teistumo-detales",
]

TURTO_PAJAMU_KEYS = [
    "privalomas-registruoti-turtas",
    "vertybiniai-popieriai-meno-kuriniai-juvelyriniai-dirbiniai",
    "pinigines-lesos",
    "suteiktos-paskolos",
    "gautos-paskolos",
    "gautos-pajamos",
    "sumoketas-pajamu-mokestis",
]

# The labels VRK actually prints on the 2019 "Turto ir pajamų deklaracijos"
# tab, transcribed from the fixture HTML rather than from the module. The asset
# rows (I-V) are worded as in 2017; the two income rows were rewritten between
# the elections — 2017 names GPM308 field numbers ("Gautų pajamų suma (GPM308
# formos 12, 13, 14 ... laukelių suma)"), 2019 states them in prose. Keeping
# this table local means the assertions below fail if the module ever falls
# back on another election's aliases, which is exactly how the two income keys
# came to be null for the whole election before they were fixed.
PUBLISHED_AMOUNT_LABELS = {
    "I. Privalomas registruoti turtas": "privalomas-registruoti-turtas",
    "II. Vertybiniai popieriai, meno kūriniai, juvelyriniai dirbiniai": (
        "vertybiniai-popieriai-meno-kuriniai-juvelyriniai-dirbiniai"
    ),
    "III. Piniginės lėšos": "pinigines-lesos",
    "IV. Suteiktos paskolos": "suteiktos-paskolos",
    "V. Gautos paskolos": "gautos-paskolos",
    "Deklaruota apmokestinamųjų ir neapmokestinamųjų pajamų suma": "gautos-pajamos",
    "Deklaruota mokėtina pajamų mokesčio suma": "sumoketas-pajamu-mokestis",
}


def _parse(candidate_id: str) -> dict:
    with tempfile.TemporaryDirectory() as tmp:
        output_path, _ = parse_anketa_sample(
            candidate_id=candidate_id,
            samples_root=SAMPLES_ROOT,
            output_root=Path(tmp),
        )
        return json.loads(output_path.read_text(encoding="utf-8"))


def _published_amount(value: str) -> int | float | None:
    """Read "246338 EUR" / "242774,5 EUR" the way a reader of the page would."""
    match = re.search(r"-?\d[\d\s ]*(?:[.,]\d+)?", value or "")
    if match is None:
        return None
    number = match.group(0).replace(" ", "").replace("\xa0", "").replace(",", ".")
    return float(number) if "." in number else int(number)


def _published_amounts(payload: dict) -> dict[str, int | float]:
    """The seven canonical amounts, read straight out of rawData by label."""
    amounts: dict[str, int | float] = {}
    for section in payload["rawData"]["turtoIrPajamuDeklaracijos"]["sections"]:
        for item in section["items"]:
            label = " ".join(str(item.get("key", "")).split())
            target = PUBLISHED_AMOUNT_LABELS.get(label)
            if target is None:
                continue
            amounts[target] = _published_amount(str(item.get("value", "")))
    return amounts


class Savivaldybiu2019ExpectedTabsTests(unittest.TestCase):
    def test_campaign_tab_is_expected_only_of_mayoral_candidates(self) -> None:
        # As in 2023: a council candidate's campaign is run by the party list,
        # so only the people who also stand for mayor register a participant of
        # their own. A fixed six-tab expectation would warn on all 13,256
        # council-only candidates of this election.
        for roles, campaign_expected in (
            (["tarybos-narys"], False),
            (["meras"], True),
            (["tarybos-narys", "meras"], True),
        ):
            with self.subTest(roles=roles):
                tabs = expected_tabs_for({"roles": roles})
                self.assertEqual(
                    "politines-kampanijos-dalyvio-duomenys" in tabs, campaign_expected
                )
                self.assertTrue(
                    {
                        "anketa",
                        "biografija",
                        "turto-ir-pajamu-deklaracijos",
                        "privaciu-interesu-deklaracijos",
                        "kita",
                    }.issubset(tabs)
                )


class Savivaldybiu2019AnketaParserTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.aleksejevaite = _parse("agne-aleksejevaite-2409490")
        cls.dauksys = _parse("gediminas-dauksys-2408494")
        cls.ziliene = _parse("judita-ziliene-2409466")
        cls.armonas = _parse("kestutis-armonas-2404237")
        cls.cesiulis = _parse("nerijus-cesiulis-2406286")
        cls.juska = _parse("ricardas-juska-2413847")
        cls.mockevicius = _parse("skirmantas-mockevicius-2400117")
        cls.mitrofanovas = _parse("vitalijus-mitrofanovas-2406746")
        cls.jareckas = _parse("vytas-jareckas-2404239")
        # The only fixture that answers the conviction question "Taip"; VRK
        # nests the conviction-detail table inside the anketa for these pages.
        cls.orda = _parse("gintas-orda-2400958")

    @property
    def by_id(self) -> dict[str, dict]:
        return {payload["candidateId"]: payload for payload in self.everyone}

    @property
    def council_only(self) -> tuple[dict, ...]:
        return (self.aleksejevaite, self.ziliene, self.armonas, self.orda)

    @property
    def mayoral(self) -> tuple[dict, ...]:
        return (
            self.dauksys,
            self.cesiulis,
            self.juska,
            self.mockevicius,
            self.mitrofanovas,
            self.jareckas,
        )

    @property
    def everyone(self) -> tuple[dict, ...]:
        return self.council_only + self.mayoral

    # ------------------------------------------------------------------
    # Top-level record
    # ------------------------------------------------------------------

    def test_top_level_fields(self) -> None:
        self.assertEqual(
            list(self.dauksys.keys()),
            [
                "electionId",
                "candidateId",
                "candidateName",
                "candidateNote",
                "kandidatavimas",
                "source",
                "rawData",
                "normalized",
            ],
        )
        self.assertEqual(self.dauksys["electionId"], ELECTION_ID)
        self.assertEqual(self.dauksys["candidateId"], "gediminas-dauksys-2408494")
        self.assertEqual(self.dauksys["candidateName"], "Gediminas DAUKŠYS")
        self.assertEqual(self.ziliene["candidateName"], "Judita ŽILIENĖ")
        for payload in self.everyone:
            with self.subTest(candidate=payload["candidateId"]):
                self.assertEqual(payload["electionId"], ELECTION_ID)
                self.assertIsNone(payload["candidateNote"])

    def test_candidate_id_carries_the_vrk_candidate_id(self) -> None:
        # Name slugs collide across 13,666 candidates and the batch runner
        # resumes off data/<candidateId>-<electionId>.json, so the id has to be
        # stable rather than order-dependent. Unlike 2023 the page stem has no
        # year in it: savKandidatasAnketa_rkndId-N.html.
        for payload in self.everyone:
            with self.subTest(candidate=payload["candidateId"]):
                vrk_id = payload["kandidatavimas"]["vrkCandidateId"]
                self.assertTrue(payload["candidateId"].endswith(f"-{vrk_id}"))
                self.assertTrue(
                    payload["source"]["candidateSourceUrl"].endswith(
                        f"savKandidatasAnketa_rkndId-{vrk_id}.html"
                    ),
                    payload["source"]["candidateSourceUrl"],
                )

    # ------------------------------------------------------------------
    # kandidatavimas: the listing-only candidacy context
    # ------------------------------------------------------------------

    def test_kandidatavimas_block_shape(self) -> None:
        for payload in self.everyone:
            with self.subTest(candidate=payload["candidateId"]):
                self.assertEqual(
                    list(payload["kandidatavimas"].keys()),
                    [
                        "vrkCandidateId",
                        "savivaldybe",
                        "roles",
                        "tarybosNarys",
                        "meras",
                        "isrinktas",
                    ],
                )
                self.assertEqual(
                    list(payload["kandidatavimas"]["savivaldybe"].keys()),
                    ["id", "number", "name"],
                )

    def test_kandidatavimas_council_only(self) -> None:
        kandidatavimas = self.aleksejevaite["kandidatavimas"]
        self.assertEqual(kandidatavimas["vrkCandidateId"], "2409490")
        self.assertEqual(
            kandidatavimas["savivaldybe"],
            {"id": "19982", "number": 1, "name": "Akmenės rajono"},
        )
        self.assertEqual(kandidatavimas["roles"], ["tarybos-narys"])
        self.assertIsNone(kandidatavimas["meras"])
        self.assertFalse(kandidatavimas["isrinktas"])
        self.assertEqual(
            kandidatavimas["tarybosNarys"],
            {
                "partyList": {
                    "id": "28698",
                    "number": 2,
                    "name": "Lietuvos valstiečių ir žaliųjų sąjunga",
                },
                "listPosition": 8,
                "postElectionPosition": 6,
                "elected": False,
            },
        )

        # Same list, elected: the post-election position moved her up to 2.
        self.assertEqual(
            self.ziliene["kandidatavimas"]["tarybosNarys"],
            {
                "partyList": {
                    "id": "28698",
                    "number": 2,
                    "name": "Lietuvos valstiečių ir žaliųjų sąjunga",
                },
                "listPosition": 4,
                "postElectionPosition": 2,
                "elected": True,
            },
        )
        self.assertTrue(self.ziliene["kandidatavimas"]["isrinktas"])

        # 2019 has no politiniai komitetai, but coalitions are carried verbatim.
        self.assertEqual(
            self.armonas["kandidatavimas"]["tarybosNarys"]["partyList"]["name"],
            "VYTO JARECKO koalicija „VIENINGI BIRŽAI“ (Lietuvos valstiečių ir "
            "žaliųjų sąjunga, Lietuvos Respublikos liberalų sąjūdis)",
        )
        self.assertTrue(self.armonas["kandidatavimas"]["isrinktas"])

    def test_kandidatavimas_mayor_only(self) -> None:
        # 31 people stood only for mayor. They hold no list seat at all.
        for payload in (self.juska, self.mockevicius):
            with self.subTest(candidate=payload["candidateId"]):
                self.assertEqual(payload["kandidatavimas"]["roles"], ["meras"])
                self.assertIsNone(payload["kandidatavimas"]["tarybosNarys"])

        self.assertEqual(
            self.mockevicius["kandidatavimas"]["meras"],
            {"round": "II", "nominatedBy": "išsikėlė pats", "elected": True},
        )
        self.assertTrue(self.mockevicius["kandidatavimas"]["isrinktas"])

        # Same municipality, same round, party-nominated, beaten.
        self.assertEqual(
            self.juska["kandidatavimas"]["meras"],
            {
                "round": "II",
                "nominatedBy": "Lietuvos Respublikos liberalų sąjūdis",
                "elected": False,
            },
        )
        self.assertFalse(self.juska["kandidatavimas"]["isrinktas"])

    def test_kandidatavimas_dual_candidates_carry_both_roles(self) -> None:
        # 379 people stood for both a council seat and the mayoralty under one
        # VRK candidate id; the two candidacies are decided independently.
        for payload in (self.dauksys, self.cesiulis, self.mitrofanovas, self.jareckas):
            with self.subTest(candidate=payload["candidateId"]):
                self.assertEqual(
                    payload["kandidatavimas"]["roles"], ["tarybos-narys", "meras"]
                )
                self.assertIsInstance(payload["kandidatavimas"]["tarybosNarys"], dict)
                self.assertIsInstance(payload["kandidatavimas"]["meras"], dict)

        # Elected mayor in round II; the list seat went to the runner-up rules.
        self.assertEqual(
            self.cesiulis["kandidatavimas"]["meras"],
            {
                "round": "II",
                "nominatedBy": "Lietuvos socialdemokratų partija",
                "elected": True,
            },
        )
        self.assertFalse(self.cesiulis["kandidatavimas"]["tarybosNarys"]["elected"])
        self.assertTrue(self.cesiulis["kandidatavimas"]["isrinktas"])

        # Elected mayor in round I.
        self.assertEqual(
            self.mitrofanovas["kandidatavimas"]["meras"],
            {
                "round": "I",
                "nominatedBy": "Lietuvos socialdemokratų partija",
                "elected": True,
            },
        )
        self.assertFalse(self.mitrofanovas["kandidatavimas"]["tarybosNarys"]["elected"])

        # Jareckas is nominated for mayor by one of the coalition's two parties
        # while standing on the coalition's list — the two nominations differ.
        self.assertEqual(
            self.jareckas["kandidatavimas"]["meras"],
            {
                "round": "I",
                "nominatedBy": "Lietuvos valstiečių ir žaliųjų sąjunga",
                "elected": True,
            },
        )
        self.assertEqual(
            self.jareckas["kandidatavimas"]["tarybosNarys"]["partyList"]["name"],
            "VYTO JARECKO koalicija „VIENINGI BIRŽAI“ (Lietuvos valstiečių ir "
            "žaliųjų sąjunga, Lietuvos Respublikos liberalų sąjūdis)",
        )

    def test_dauksys_won_the_council_seat_and_lost_the_mayoralty(self) -> None:
        # The asymmetry that a single "elected" boolean would destroy: Daukšys
        # took his committee list's first seat and was beaten in the mayoral
        # run-off. isrinktas is the OR of the two candidacies, so it is true
        # even though meras.elected is false — and his profile note is the
        # list-seat one, not the mayoral one (see test_profilis_pastaba_forms).
        kandidatavimas = self.dauksys["kandidatavimas"]
        self.assertEqual(kandidatavimas["roles"], ["tarybos-narys", "meras"])
        self.assertEqual(
            kandidatavimas["tarybosNarys"],
            {
                "partyList": {
                    "id": "27808",
                    "number": 3,
                    "name": "Visuomeninis rinkimų komitetas „Už Alytų“",
                },
                "listPosition": 1,
                "postElectionPosition": 1,
                "elected": True,
            },
        )
        self.assertEqual(
            kandidatavimas["meras"],
            {
                "round": "II",
                "nominatedBy": "Visuomeninis rinkimų komitetas „Už Alytų“",
                "elected": False,
            },
        )
        self.assertTrue(kandidatavimas["isrinktas"])
        # The man who beat him in the same municipality and round.
        self.assertTrue(self.cesiulis["kandidatavimas"]["meras"]["elected"])
        self.assertEqual(
            self.cesiulis["kandidatavimas"]["savivaldybe"],
            kandidatavimas["savivaldybe"],
        )

    # ------------------------------------------------------------------
    # Section presence
    # ------------------------------------------------------------------

    def test_normalized_section_order_for_mayoral_candidates(self) -> None:
        for payload in self.mayoral:
            with self.subTest(candidate=payload["candidateId"]):
                self.assertEqual(list(payload["normalized"].keys()), MAYORAL_SECTIONS)

    def test_council_only_candidates_have_no_campaign_section(self) -> None:
        # Not a gap in the scrape: a council candidate registers no political
        # campaign of their own — the party list does — so VRK publishes five
        # tabs for them and never a campaign one. The absence is expected, and
        # the candidate_samples expectation above is what keeps it from being
        # reported as a MissingExpectedTab anomaly.
        for payload in self.council_only:
            with self.subTest(candidate=payload["candidateId"]):
                self.assertEqual(list(payload["normalized"].keys()), BASE_SECTIONS)
                self.assertNotIn(
                    "politinesKampanijosDalyvioDuomenys", payload["rawData"]
                )
                self.assertEqual(payload["kandidatavimas"]["roles"], ["tarybos-narys"])
                self.assertNotIn(
                    "politines-kampanijos-dalyvio-duomenys",
                    expected_tabs_for(payload["kandidatavimas"]),
                )

    def test_raw_data_section_order(self) -> None:
        self.assertEqual(
            list(self.dauksys["rawData"].keys()),
            [
                "profile",
                "anketa",
                "biografija",
                "turtoIrPajamuDeklaracijos",
                "privaciuInteresuDeklaracija",
                "politinesKampanijosDalyvioDuomenys",
                "kita",
            ],
        )
        self.assertEqual(
            list(self.ziliene["rawData"].keys()),
            [
                "profile",
                "anketa",
                "biografija",
                "turtoIrPajamuDeklaracijos",
                "privaciuInteresuDeklaracija",
                "kita",
            ],
        )

    # ------------------------------------------------------------------
    # profilis
    # ------------------------------------------------------------------

    def test_profilis_shape_and_photo(self) -> None:
        for payload in self.everyone:
            with self.subTest(candidate=payload["candidateId"]):
                profilis = payload["normalized"]["profilis"]
                self.assertEqual(
                    list(profilis.keys()),
                    ["vardas-pavarde", "pastaba", "nuotrauka", "kita", "kandidatuoja-i", "dokumentu-pateikimo-data"],
                )
        self.assertEqual(self.dauksys["normalized"]["profilis"]["vardas-pavarde"], "GEDIMINAS DAUKŠYS")

        # This vintage embeds the portrait; it is externalized to a sidecar
        # file and both photo fields carry the relative path.
        for payload in self.mayoral:
            with self.subTest(candidate=payload["candidateId"]):
                expected = f"photos/{payload['candidateId']}.jpg"
                self.assertEqual(payload["normalized"]["profilis"]["nuotrauka"], expected)
                self.assertEqual(payload["rawData"]["profile"]["photoSrc"], expected)
                self.assertGreater(payload["rawData"]["profile"]["photoMeta"]["bytes"], 0)

        # The three council-only fixtures publish no portrait at all — their
        # pages carry no image element, not an image the parser missed.
        for payload in self.council_only:
            with self.subTest(candidate=payload["candidateId"]):
                self.assertIsNone(payload["normalized"]["profilis"]["nuotrauka"])
                self.assertEqual(
                    payload["rawData"]["profile"].get("candidatePhoto"), None
                )

    def test_profilis_kita_keys_vary_by_role(self) -> None:
        # Council-only pages carry no nomination line and no round.
        for payload in self.council_only:
            with self.subTest(candidate=payload["candidateId"]):
                kita = payload["normalized"]["profilis"]["kita"]
                self.assertEqual(
                    list(kita.keys()),
                    [
                        "savivaldybe",
                        "sarasas",
                        "numeris-sarase",
                        "porinkiminis-numeris-sarase",
                    ],
                )
                self.assertNotIn("turas", kita)

        # Every mayoral candidate — dual or mayor-only — is nominated under the
        # single 2019 label. Note there is no "ir": 2019 says "Iškėlė į tarybos
        # narius - merus", where 2023 says "Iškėlė į tarybos narius ir merus"
        # for dual candidates and "Iškėlė į savivaldybės merus" for mayor-only
        # ones. Keying off the 2023 wording finds nothing here.
        for payload in self.mayoral:
            with self.subTest(candidate=payload["candidateId"]):
                kita = payload["normalized"]["profilis"]["kita"]
                self.assertEqual(
                    list(kita.keys()),
                    [
                        "savivaldybe",
                        "iskele-i-tarybos-narius-merus",
                        "turas",
                        "sarasas",
                        "numeris-sarase",
                        "porinkiminis-numeris-sarase",
                    ],
                )
                self.assertEqual(
                    kita["iskele-i-tarybos-narius-merus"]["pavadinimas"],
                    "Iškėlė į tarybos narius - merus",
                )
                self.assertEqual(
                    kita["turas"]["reiksme"],
                    payload["kandidatavimas"]["meras"]["round"],
                )
                self.assertEqual(
                    kita["iskele-i-tarybos-narius-merus"]["reiksme"],
                    payload["kandidatavimas"]["meras"]["nominatedBy"],
                )

    def test_profilis_kita_values(self) -> None:
        kita = self.armonas["normalized"]["profilis"]["kita"]
        self.assertEqual(kita["savivaldybe"]["pavadinimas"], "Savivaldybė")
        self.assertEqual(kita["savivaldybe"]["reiksme"], "Biržų rajono (6)")
        self.assertTrue(
            kita["savivaldybe"]["nuorodos"][0].endswith(
                "savKandidataiApygardoje_rpgId-19962.html"
            )
        )
        self.assertEqual(kita["numeris-sarase"]["reiksme"], "1")
        self.assertEqual(kita["porinkiminis-numeris-sarase"]["reiksme"], "2")
        self.assertEqual(
            kita["sarasas"]["reiksme"],
            self.armonas["kandidatavimas"]["tarybosNarys"]["partyList"]["name"],
        )

        # Mayor-only candidates stand on no list, so the three list rows are
        # published empty rather than dropped.
        for payload in (self.juska, self.mockevicius):
            with self.subTest(candidate=payload["candidateId"]):
                mayor_kita = payload["normalized"]["profilis"]["kita"]
                self.assertIsNone(mayor_kita["sarasas"]["reiksme"])
                self.assertIsNone(mayor_kita["numeris-sarase"]["reiksme"])
                self.assertIsNone(mayor_kita["porinkiminis-numeris-sarase"]["reiksme"])
                self.assertIsNone(payload["kandidatavimas"]["tarybosNarys"])

        # Self-nomination is written in the nomination row itself.
        self.assertEqual(
            self.mockevicius["normalized"]["profilis"]["kita"][
                "iskele-i-tarybos-narius-merus"
            ]["reiksme"],
            "išsikėlė pats",
        )

    def test_profilis_pastaba_forms(self) -> None:
        # Three shapes appear on the 2019 pages, all gendered.
        #
        # 1. The list-seat note, naming the list in the genitive.
        self.assertEqual(
            self.ziliene["normalized"]["profilis"]["pastaba"],
            "Išrinkta pagal Lietuvos valstiečių ir žaliųjų sąjungos sąrašą",
        )
        self.assertEqual(
            self.armonas["normalized"]["profilis"]["pastaba"],
            "Išrinktas pagal VYTO JARECKO koalicijos „VIENINGI BIRŽAI“ (Lietuvos "
            "valstiečių ir žaliųjų sąjungos, Lietuvos Respublikos liberalų "
            "sąjūdžio) sąrašą",
        )
        # A dual candidate who won the seat but lost the mayoralty gets the
        # list note, not the mayoral one.
        self.assertEqual(
            self.dauksys["normalized"]["profilis"]["pastaba"],
            "Išrinktas pagal Visuomeninio rinkimų komiteto „Už Alytų“ sąrašą",
        )

        # 2. The mayoral note, naming the municipality and the round.
        self.assertEqual(
            self.mitrofanovas["normalized"]["profilis"]["pastaba"],
            "Išrinktas Akmenės rajono (Nr.1) savivaldybėje I ture",
        )
        self.assertEqual(
            self.jareckas["normalized"]["profilis"]["pastaba"],
            "Išrinktas Biržų rajono (Nr.6) savivaldybėje I ture",
        )
        self.assertEqual(
            self.cesiulis["normalized"]["profilis"]["pastaba"],
            "Išrinktas Alytaus miesto (Nr.2) savivaldybėje II ture",
        )
        self.assertEqual(
            self.mockevicius["normalized"]["profilis"]["pastaba"],
            "Išrinktas Jurbarko rajono (Nr.12) savivaldybėje II ture",
        )

        # 3. Nothing at all, for everyone who won neither contest.
        for payload in (self.aleksejevaite, self.juska):
            with self.subTest(candidate=payload["candidateId"]):
                self.assertIsNone(payload["normalized"]["profilis"]["pastaba"])
                self.assertFalse(payload["kandidatavimas"]["isrinktas"])

        # The note and the sitemap's elected flags never disagree.
        for payload in self.everyone:
            with self.subTest(candidate=payload["candidateId"]):
                self.assertEqual(
                    payload["normalized"]["profilis"]["pastaba"] is not None,
                    payload["kandidatavimas"]["isrinktas"],
                )

    # ------------------------------------------------------------------
    # anketa
    # ------------------------------------------------------------------

    def test_anketa_key_set_is_the_2016_era_one(self) -> None:
        # Q5-Q21 with the biography questions inside the anketa — no separate
        # biography question block, no membership table, no conviction detail
        # sub-object. This is the meru_2017 shape, not the 2023 one.
        for payload in self.everyone:
            with self.subTest(candidate=payload["candidateId"]):
                self.assertEqual(
                    list(payload["normalized"]["anketa"].keys()), ANKETA_KEYS
                )

    def test_anketa_core_fields(self) -> None:
        anketa = self.dauksys["normalized"]["anketa"]
        self.assertEqual(anketa["gimimo-data"], "1963-04-29")
        self.assertEqual(anketa["gimimo-vieta"], "Alytus")
        self.assertEqual(anketa["tautybe"], "Lietuvis")
        self.assertEqual(anketa["uzsienio-kalbos"], ["Anglų", "Rusų", "Lenkų"])
        self.assertEqual(anketa["pagrindine-darboviete"], "UAB Vėtrija, Direktorius")
        self.assertEqual(anketa["pomegiai"], "Futbolas, žvejyba, kalnų slidinėjimas")
        self.assertEqual(anketa["seimine-padetis"], "Vedęs")
        self.assertEqual(anketa["sutuoktinio-vardas-pavarde"], "Inga")
        self.assertEqual(anketa["vaiku-vardai-pavardes"], "Laurynas, Eglė ir Martynas")

        # Q6 is answered "Neskelbiamas" throughout this election — the address
        # is withheld on the page, not missing from the parse.
        for payload in self.everyone:
            with self.subTest(candidate=payload["candidateId"]):
                self.assertEqual(
                    payload["normalized"]["anketa"]["adresas"], "Neskelbiamas"
                )

        # Feminine forms occur.
        self.assertEqual(
            self.aleksejevaite["normalized"]["anketa"]["tautybe"], "Lietuvė"
        )
        self.assertEqual(
            self.aleksejevaite["normalized"]["anketa"]["politine-organizacija"],
            "Jokiai politinei partinei nepriklausau ir nesu priklausiusi.",
        )
        # "Nenurodė" normalizes to null rather than being carried through.
        self.assertIsNone(self.dauksys["normalized"]["anketa"]["politine-organizacija"])
        self.assertIsNone(self.dauksys["normalized"]["anketa"]["kita-apie-save"])

    def test_anketa_of_a_candidate_who_answered_nothing(self) -> None:
        # Juška filled in Q5, Q6 and the declarations and answered "Nenurodė"
        # to every one of Q10-Q21. All of these nulls are on the page.
        anketa = self.juska["normalized"]["anketa"]
        self.assertEqual(anketa["gimimo-data"], "1960-05-11")
        for key in (
            "gimimo-vieta",
            "tautybe",
            "pedagoginis-vardas",
            "politine-organizacija",
            "pagrindine-darboviete",
            "visuomenine-veikla",
            "pomegiai",
            "seimine-padetis",
            "sutuoktinio-vardas-pavarde",
            "vaiku-vardai-pavardes",
            "kita-apie-save",
        ):
            with self.subTest(key=key):
                self.assertIsNone(anketa[key])
        self.assertEqual(anketa["uzsienio-kalbos"], [])
        self.assertEqual(anketa["issilavinimas"], {"aprasas": None, "irasai": []})
        self.assertEqual(anketa["anksciau-isrinktas"], {"aprasas": None, "irasai": []})

    def test_record_tables_attached_to_their_questions(self) -> None:
        anketa = self.aleksejevaite["normalized"]["anketa"]
        issilavinimas = anketa["issilavinimas"]["irasai"]
        self.assertEqual(len(issilavinimas), 3)
        self.assertEqual(
            issilavinimas[0],
            {
                "issilavinimas": "Aukštasis universitetinis",
                "mokymo-istaigos-pavadinimas": "Mykolo Romerio universitetas",
                "specialybe": "Civilinė teisė",
                "baigimo-metai": "2016",
            },
        )
        # Q12 and Q15 render as record tables with no free-text description in
        # this era, so `aprasas` is legitimately null wherever records exist.
        self.assertIsNone(anketa["issilavinimas"]["aprasas"])
        # Never elected before: the table is absent, the list empty.
        self.assertEqual(anketa["anksciau-isrinktas"]["irasai"], [])

        mandates = self.dauksys["normalized"]["anketa"]["anksciau-isrinktas"]
        self.assertIsNone(mandates["aprasas"])
        self.assertEqual(
            mandates["irasai"],
            [
                {
                    "institucijos-pavadinimas-pareigos": (
                        "Alytaus miesto savivaldybės taryba, Tarybos narys"
                    ),
                    "laikotarpis": "2000 - 2015",
                }
            ],
        )

    def test_unnumbered_rows_matched_by_prompt(self) -> None:
        # Two rows carry no question number. The first asks for the pedagogic
        # title *and* the academic degree in one prompt ("Jei turite,
        # nurodykite pedagoginį vardą, mokslo laipsnį"), which is why a degree
        # lands under `pedagoginis-vardas` — one published row, one field.
        self.assertEqual(
            self.dauksys["normalized"]["anketa"]["pedagoginis-vardas"], "Magistras"
        )
        self.assertEqual(
            self.aleksejevaite["normalized"]["anketa"]["pedagoginis-vardas"],
            "Magistras",
        )
        self.assertEqual(
            self.dauksys["normalized"]["anketa"]["sutuoktinio-vardas-pavarde"], "Inga"
        )

    def test_pareiskimai_are_the_savivaldybiu_tarybu_istatymas_declarations(
        self,
    ) -> None:
        # This election is run under the savivaldybių tarybų rinkimų įstatymas
        # (36 str. 11-12 d.), not the Rinkimų kodeksas. The sub-question numbers
        # are written without a dot ("8.2 Ar nesate ..."), which a strict
        # question-number pattern reads as question 8 and collapses onto the
        # section heading.
        #
        # Every answer is compared against what the page publishes rather than
        # against a hardcoded "Ne". An earlier version asserted "Ne" for the
        # conviction question across the whole fixture set, which certified as
        # working the one path that was broken — a candidate who answers "Taip"
        # used to lose the entire questionnaire.
        for payload in self.everyone:
            with self.subTest(candidate=payload["candidateId"]):
                pareiskimai = payload["normalized"]["anketa"]["pareiskimai"]
                published = {
                    str(row.get("questionNumber")): row.get("answer")
                    for row in payload["rawData"]["anketa"]["rows"]
                }
                self.assertEqual(
                    pareiskimai["ar-atliekate-karo-tarnyba"], published["8.2"]
                )
                self.assertEqual(
                    pareiskimai["ar-turite-kitos-valstybes-pilietybe"], published["8.5"]
                )
                self.assertEqual(
                    pareiskimai["ar-buvote-pripazintas-kaltu"], published["9"]
                )

        # Both answers occur in the fixture set, so the assertion above is not
        # vacuous in either direction.
        answers = {
            payload["normalized"]["anketa"]["pareiskimai"]["ar-buvote-pripazintas-kaltu"]
            for payload in self.everyone
        }
        self.assertEqual(answers, {"Ne", "Taip"})

        # Two declarations in the fixture set carry a non-default answer, and
        # both are on the page — a parser that always returned the negative
        # form would still look right on eight of the nine fixtures.
        #
        # Q8.3: Jareckas was the sitting Biržų mayor, so he declared "Einu" —
        # he does hold office incompatible with a council seat.
        self.assertEqual(
            self.jareckas["normalized"]["anketa"]["pareiskimai"][
                "ar-eina-nesuderinamas-pareigas"
            ],
            "Einu",
        )
        # Q8.4: Aleksejevaitė declared "Esu" — a member of another state's
        # elected authority.
        self.assertEqual(
            self.aleksejevaite["normalized"]["anketa"]["pareiskimai"][
                "ar-kitos-valstybes-institucijos-narys"
            ],
            "Esu",
        )
        for payload in self.everyone:
            with self.subTest(candidate=payload["candidateId"]):
                pareiskimai = payload["normalized"]["anketa"]["pareiskimai"]
                self.assertEqual(
                    pareiskimai["ar-eina-nesuderinamas-pareigas"],
                    "Einu" if payload is self.jareckas else "Neinu",
                )
                self.assertEqual(
                    pareiskimai["ar-kitos-valstybes-institucijos-narys"],
                    "Esu" if payload is self.aleksejevaite else "Nesu",
                )

    def test_every_published_declaration_is_normalized(self) -> None:
        # 2019 asks four declarations the April 2017 pages do not: Q8.1 (their
        # sub-questions start at 8.2) and Q9.2-9.4 (absent entirely). Inheriting
        # the 2017 mapping unchanged parsed all four into rawData and dropped
        # them from normalized — conviction-related answers lost for the whole
        # election. Keys follow meru_2021, which asks the same set under the
        # same statute.
        #
        # The list is exact on purpose: the earlier version of this test
        # prescribed only six keys, which would have locked in the loss of
        # 9.2-9.4 the moment it went green.
        for payload in self.everyone:
            with self.subTest(candidate=payload["candidateId"]):
                rows = payload["rawData"]["anketa"]["rows"]
                published = {
                    str(row.get("questionNumber")): row.get("answer") for row in rows
                }
                for number in ("8.1", "8.2", "8.3", "8.4", "8.5", "9", "9.2", "9.3", "9.4"):
                    self.assertIn(number, published, f"page does not publish Q{number}")

                pareiskimai = payload["normalized"]["anketa"]["pareiskimai"]
                self.assertEqual(
                    list(pareiskimai.keys()),
                    [
                        "ar-nebaigta-teismo-paskirta-bausme",
                        "ar-atliekate-karo-tarnyba",
                        "ar-eina-nesuderinamas-pareigas",
                        "ar-kitos-valstybes-institucijos-narys",
                        "ar-turite-kitos-valstybes-pilietybe",
                        "ar-buvote-pripazintas-kaltu",
                        "ar-veika-dekriminalizuota",
                        "ar-buvote-pripazintas-kaltu-uzsienyje",
                        "ar-buvote-pripazintas-kaltu-del-politinio-persekiojimo",
                    ],
                )
                # Every declaration the page answers must reach normalized.
                self.assertEqual(
                    pareiskimai["ar-nebaigta-teismo-paskirta-bausme"], published["8.1"]
                )
                self.assertEqual(pareiskimai["ar-veika-dekriminalizuota"], published["9.2"])
                self.assertEqual(
                    pareiskimai["ar-buvote-pripazintas-kaltu-uzsienyje"], published["9.3"]
                )

    def test_a_declared_conviction_keeps_the_whole_questionnaire(self) -> None:
        # VRK nests the conviction-detail table inside the anketa table for any
        # candidate who answers Q9 "Taip". A recursive <th> lookup used to
        # classify the whole anketa as a records table, so these candidates lost
        # every question from birth date to nationality along with all nine
        # declarations — silently, with no anomaly raised. This fixture is the
        # only one in the set that answers "Taip".
        payload = self.by_id["gintas-orda-2400958"]
        anketa = payload["normalized"]["anketa"]

        self.assertEqual(anketa["pareiskimai"]["ar-buvote-pripazintas-kaltu"], "Taip")
        self.assertEqual(anketa["gimimo-data"], "1966-07-26")
        self.assertEqual(anketa["gimimo-vieta"], "Kuršėnų m., Šiaulių raj.")
        self.assertEqual(anketa["tautybe"], "Lietuvis")
        self.assertEqual(anketa["adresas"], "Neskelbiamas")
        # The block used to collapse to 13 rows; a full questionnaire has 27,
        # plus the captured Q9.1 conviction-detail records row.
        self.assertEqual(len(payload["rawData"]["anketa"]["rows"]), 28)
        for value in anketa["pareiskimai"].values():
            self.assertIsNotNone(value)

    def test_conviction_details_are_normalized(self) -> None:
        # Q9.1 lists each conviction — date, country, court and offence — in a
        # table VRK nests inside a row of its own. The shared 2019-era parse
        # used to drop that row before anything could read it, so the details
        # reached neither rawData nor normalized. The keys and the shape match
        # meru_2021, which asks the same questions under the same statute.
        payload = self.by_id["gintas-orda-2400958"]
        self.assertEqual(
            payload["normalized"]["anketa"]["teistumo-detales"],
            {
                "irasai": [
                    {
                        "nuosprendzio-data": "1988",
                        "nuosprendzio-valstybe": "LTSR",
                        "nuosprendzio-institucija": "LTSR Aukščiausiasis Teismas",
                        "nusikalstama-veika": "Chuliganizmas",
                    }
                ]
            },
        )
        # Every candidate carries the key; without a "Taip" answer it is empty.
        for candidate in self.everyone:
            with self.subTest(candidate=candidate["candidateId"]):
                anketa = candidate["normalized"]["anketa"]
                self.assertIn("teistumo-detales", anketa)
                if anketa["pareiskimai"]["ar-buvote-pripazintas-kaltu"] != "Taip":
                    self.assertEqual(anketa["teistumo-detales"], {"irasai": []})

    # ------------------------------------------------------------------
    # biografija
    # ------------------------------------------------------------------

    def test_biografija_is_free_text(self) -> None:
        # 2016-era pages publish the biography as one prose block, not the
        # question-keyed object of the 2023+ modules.
        for payload in self.everyone:
            with self.subTest(candidate=payload["candidateId"]):
                self.assertEqual(
                    list(payload["normalized"]["biografija"].keys()), ["tekstas"]
                )

        self.assertTrue(
            self.dauksys["normalized"]["biografija"]["tekstas"].startswith(
                "Gimė 1963 m. balandžio 29 d. Alytuje."
            )
        )
        self.assertIn(
            "Vilniaus universiteto",
            self.dauksys["normalized"]["biografija"]["tekstas"],
        )
        self.assertTrue(
            self.mockevicius["normalized"]["biografija"]["tekstas"].startswith(
                "Gimė 1965 m. gruodžio 18 d. Jurbarke."
            )
        )

        # The three council-only fixtures have an empty biography tab: VRK
        # wrote no biography for them, so null is the page's own answer.
        for payload in self.council_only:
            with self.subTest(candidate=payload["candidateId"]):
                self.assertIsNone(payload["normalized"]["biografija"]["tekstas"])

    # ------------------------------------------------------------------
    # turto ir pajamu deklaracijos
    # ------------------------------------------------------------------

    def test_turto_ir_pajamu_key_order(self) -> None:
        for payload in self.everyone:
            with self.subTest(candidate=payload["candidateId"]):
                self.assertEqual(
                    list(payload["normalized"]["turto-ir-pajamu-deklaracijos"].keys()),
                    TURTO_PAJAMU_KEYS,
                )

    def test_every_published_amount_reaches_the_normalized_record(self) -> None:
        # The regression this whole block exists for: with the 2017 income
        # aliases, `gautos-pajamos` and `sumoketas-pajamu-mokestis` came out
        # null for 9 of 9 fixtures — and for the whole election — while the
        # figures sat untouched in rawData. Nothing may be null when the page
        # prints a number.
        for payload in self.everyone:
            with self.subTest(candidate=payload["candidateId"]):
                normalized = payload["normalized"]["turto-ir-pajamu-deklaracijos"]
                published = _published_amounts(payload)
                # All seven rows are printed on every 2019 declaration page.
                self.assertEqual(sorted(published), sorted(TURTO_PAJAMU_KEYS))
                for key in TURTO_PAJAMU_KEYS:
                    self.assertIsNotNone(
                        normalized[key],
                        f"{key} is null although the page publishes "
                        f"{published[key]}",
                    )
                    self.assertEqual(normalized[key], published[key], key)

    def test_turto_ir_pajamu_amounts(self) -> None:
        # Whole euros stay ints; the comma decimal separator parses to a float.
        self.assertEqual(
            self.dauksys["normalized"]["turto-ir-pajamu-deklaracijos"],
            {
                "privalomas-registruoti-turtas": 29223,
                "vertybiniai-popieriai-meno-kuriniai-juvelyriniai-dirbiniai": 91805,
                "pinigines-lesos": 76824,
                "suteiktos-paskolos": 0,
                "gautos-paskolos": 0,
                "gautos-pajamos": 12023.63,
                "sumoketas-pajamu-mokestis": 1345,
            },
        )
        self.assertEqual(
            self.ziliene["normalized"]["turto-ir-pajamu-deklaracijos"],
            {
                "privalomas-registruoti-turtas": 246338,
                "vertybiniai-popieriai-meno-kuriniai-juvelyriniai-dirbiniai": 0,
                "pinigines-lesos": 24674,
                "suteiktos-paskolos": 0,
                "gautos-paskolos": 0,
                "gautos-pajamos": 242774.5,
                "sumoketas-pajamu-mokestis": 4855,
            },
        )
        self.assertEqual(
            self.armonas["normalized"]["turto-ir-pajamu-deklaracijos"],
            {
                "privalomas-registruoti-turtas": 481880,
                "vertybiniai-popieriai-meno-kuriniai-juvelyriniai-dirbiniai": 0,
                "pinigines-lesos": 13241,
                "suteiktos-paskolos": 0,
                "gautos-paskolos": 142671,
                "gautos-pajamos": 395658.6,
                "sumoketas-pajamu-mokestis": 6785,
            },
        )
        self.assertEqual(
            self.mockevicius["normalized"]["turto-ir-pajamu-deklaracijos"],
            {
                "privalomas-registruoti-turtas": 9413,
                "vertybiniai-popieriai-meno-kuriniai-juvelyriniai-dirbiniai": 29,
                "pinigines-lesos": 3173,
                "suteiktos-paskolos": 0,
                "gautos-paskolos": 0,
                "gautos-pajamos": 34241.13,
                "sumoketas-pajamu-mokestis": 5136,
            },
        )
        # A declaration whose asset half is all zeros — the rows are published
        # as "0 EUR", so zero and "not declared" stay distinguishable.
        self.assertEqual(
            self.aleksejevaite["normalized"]["turto-ir-pajamu-deklaracijos"],
            {
                "privalomas-registruoti-turtas": 0,
                "vertybiniai-popieriai-meno-kuriniai-juvelyriniai-dirbiniai": 0,
                "pinigines-lesos": 0,
                "suteiktos-paskolos": 0,
                "gautos-paskolos": 0,
                "gautos-pajamos": 11599.07,
                "sumoketas-pajamu-mokestis": 1710,
            },
        )
        self.assertEqual(
            self.cesiulis["normalized"]["turto-ir-pajamu-deklaracijos"][
                "suteiktos-paskolos"
            ],
            29049,
        )

    def test_gpm308_breakdown_stays_in_raw_data_only(self) -> None:
        # 2019 also publishes individual-activity income, its deductions, and
        # asset-sale income with its acquisition cost. Those are not part of
        # the seven canonical keys and must not be folded into them.
        armonas_raw = self.armonas["rawData"]["turtoIrPajamuDeklaracijos"]
        labels = {
            " ".join(str(item["key"]).split())
            for section in armonas_raw["sections"]
            for item in section["items"]
        }
        self.assertIn("Deklaruota individualios veiklos pajamų suma", labels)
        normalized = self.armonas["normalized"]["turto-ir-pajamu-deklaracijos"]
        # 347357 EUR of individual-activity income is part of the 395658.6
        # total, not a value of its own in the record.
        self.assertNotIn(347357, normalized.values())

    # ------------------------------------------------------------------
    # privaciu interesu deklaracija
    # ------------------------------------------------------------------

    def test_privaciu_interesu_sections_keyed_by_id(self) -> None:
        # The 2016-era private-interest pages use ID001x section anchors rather
        # than the named sections of the 2023 modules.
        privaciu = self.dauksys["normalized"]["privaciu-interesu-deklaracija"]
        self.assertEqual(privaciu["deklaruojantis-asmuo"], "GEDIMINAS DAUKŠYS")
        sutuoktinis = privaciu[
            "deklaruojancio-asmens-sutuoktinis-sugyventinis-partneris"
        ]
        self.assertEqual(sutuoktinis["vardas"], "INGA")
        self.assertEqual(sutuoktinis["pavarde"], "DAUKŠIENĖ")
        self.assertEqual(len(privaciu["id001j"]), 3)
        self.assertEqual(
            privaciu["id001j"][0]["juridinio-asmens-pavadinimas"],
            "ALYTAUS APSKRITIES FUTBOLO FEDERACIJA",
        )
        self.assertEqual(privaciu["id001j"][0]["rysio-pradzios-data"], "2012-04-27")
        self.assertIsNone(privaciu["id001j"][0]["rysio-pabaigos-data"])

        # Sections appear only when the declaration carries them, and the set
        # differs per declarant — id001s/id001a/id001f/id001i all occur.
        self.assertEqual(
            list(self.cesiulis["normalized"]["privaciu-interesu-deklaracija"].keys()),
            [
                "deklaruojantis-asmuo",
                "deklaruojancio-asmens-sutuoktinis-sugyventinis-partneris",
                "id001j",
                "id001s",
                "id001i",
            ],
        )
        self.assertEqual(
            list(self.mitrofanovas["normalized"]["privaciu-interesu-deklaracija"].keys()),
            [
                "deklaruojantis-asmuo",
                "deklaruojancio-asmens-sutuoktinis-sugyventinis-partneris",
                "id001j",
                "id001s",
                "id001f",
            ],
        )

        # An unmarried declarant still gets the spouse block, with null fields
        # rather than the block being dropped.
        aleksejevaite = self.aleksejevaite["normalized"][
            "privaciu-interesu-deklaracija"
        ]
        self.assertEqual(
            list(aleksejevaite.keys()),
            [
                "deklaruojantis-asmuo",
                "deklaruojancio-asmens-sutuoktinis-sugyventinis-partneris",
            ],
        )
        self.assertEqual(
            aleksejevaite["deklaruojancio-asmens-sutuoktinis-sugyventinis-partneris"],
            {
                "vardas": None,
                "pavarde": None,
                "sutuoktinio-sugyventinio-partnerio-darboviete-kitos-darbovietes-"
                "nurodomos-id001j-priede": None,
            },
        )

    # ------------------------------------------------------------------
    # politines kampanijos dalyvio duomenys
    # ------------------------------------------------------------------

    def test_campaign_shape(self) -> None:
        for payload in self.mayoral:
            with self.subTest(candidate=payload["candidateId"]):
                campaigns = payload["normalized"][
                    "politines-kampanijos-dalyvio-duomenys"
                ]
                self.assertEqual(len(campaigns), 1)
                self.assertEqual(
                    list(campaigns[0].keys()),
                    [
                        "statusas",
                        "registravimo-data",
                        "sprendimo-numeris",
                        "kontaktai",
                        "izdininkas",
                        "auditorius",
                        "aukos-pagal-sekcija",
                        "finansavimo-ataskaitos",
                        "sutartys",
                        "sprendimai",
                    ],
                )

    def test_represented_participants_publish_only_a_status(self) -> None:
        # Five of the six mayoral fixtures are "Atstovaujamasis" — represented
        # by their party's or committee's candidate list, which holds the
        # money. Their participant page carries a status and two contact rows
        # and literally nothing else: no registration date, no treasurer, no
        # donations table. The empties are the page, not a failed fetch.
        for payload in (
            self.dauksys,
            self.cesiulis,
            self.juska,
            self.mitrofanovas,
            self.jareckas,
        ):
            with self.subTest(candidate=payload["candidateId"]):
                campaign = payload["normalized"][
                    "politines-kampanijos-dalyvio-duomenys"
                ][0]
                self.assertEqual(campaign["statusas"], "Atstovaujamasis")
                self.assertEqual(
                    list(campaign["kontaktai"].keys()),
                    ["telefonas-pasiteirauti", "el-pastas"],
                )
                self.assertEqual(campaign["kontaktai"]["el-pastas"], "neskelbtina")
                self.assertIsNone(campaign["registravimo-data"])
                self.assertIsNone(campaign["sprendimo-numeris"])
                self.assertEqual(campaign["izdininkas"], {})
                self.assertEqual(campaign["auditorius"], {})
                self.assertEqual(campaign["aukos-pagal-sekcija"], {})
                self.assertEqual(campaign["finansavimo-ataskaitos"], [])
                self.assertEqual(campaign["sutartys"], [])
                self.assertEqual(campaign["sprendimai"], [])

                raw = payload["rawData"]["politinesKampanijosDalyvioDuomenys"][
                    "campaigns"
                ][0]
                self.assertEqual(raw["availableTabs"], [])
                self.assertEqual(
                    raw["participant"]["participantType"],
                    "Atstovaujamasis politinės kampanijos dalyvis",
                )
                self.assertIn("atstovaujamasis_pkdId-", raw["campaignUrl"])

        # The contact rows are the participant's own, not a constant: Jareckas
        # published a phone number where the other four withheld theirs.
        self.assertEqual(
            self.jareckas["normalized"]["politines-kampanijos-dalyvio-duomenys"][0][
                "kontaktai"
            ],
            {"telefonas-pasiteirauti": "68575567", "el-pastas": "neskelbtina"},
        )
        for payload in (self.dauksys, self.cesiulis, self.juska, self.mitrofanovas):
            with self.subTest(candidate=payload["candidateId"]):
                self.assertEqual(
                    payload["normalized"]["politines-kampanijos-dalyvio-duomenys"][0][
                        "kontaktai"
                    ]["telefonas-pasiteirauti"],
                    "neskelbtina",
                )

    def test_self_financed_participant_carries_the_full_campaign(self) -> None:
        campaign = self.mockevicius["normalized"][
            "politines-kampanijos-dalyvio-duomenys"
        ][0]
        self.assertEqual(campaign["statusas"], "Savarankiškas")
        self.assertEqual(campaign["registravimo-data"], "2018-11-30")
        self.assertEqual(campaign["sprendimo-numeris"], "PK1-2018STR-S160")
        self.assertEqual(campaign["izdininkas"]["vardas-pavarde"], "RAMUTĖ MOCKEVIČIENĖ")
        self.assertEqual(campaign["auditorius"]["vardas-pavarde"], "ARTŪRAS VITKAUSKAS")
        self.assertEqual(campaign["auditorius"]["imones-kodas"], "120612714")
        self.assertEqual(len(campaign["finansavimo-ataskaitos"]), 1)
        self.assertEqual(
            campaign["finansavimo-ataskaitos"][0]["approvedDate"], "2019-04-03"
        )
        self.assertEqual(len(campaign["sutartys"]), 2)
        self.assertEqual(
            campaign["sutartys"][0]["counterparty"],
            'Uždaroji akcinė bendrovė "BALTICUM TV"',
        )
        self.assertEqual(campaign["sutartys"][1]["agreementNumber"], "F4-9")

        donations = campaign["aukos-pagal-sekcija"]["gautos-ir-priimtos-aukos"]
        self.assertEqual(list(donations.keys()), ["title", "records", "totals"])
        self.assertEqual(len(donations["records"]), 7)
        self.assertEqual(
            donations["records"][0],
            {
                "rowNumber": "1.",
                "donor": "SKIRMANTAS MOCKEVIČIUS",
                "municipality": None,
                "date": "2018-12-29",
                "incomeSourceCode": "KL",
                "amount": 1000.0,
                "notes": "Piniginės lėšos, Priimtas",
            },
        )
        # He financed the campaign entirely himself, so the rows sum to both
        # the grand total and the candidate's-own-funds total.
        self.assertEqual(donations["totals"]["is-viso"], 3436.35)
        self.assertEqual(donations["totals"]["kandidato-nuosavos-lesos"], 3436.35)
        self.assertEqual(donations["totals"]["fiziniu-asmenu"], 0.0)
        self.assertEqual(
            round(sum(record["amount"] for record in donations["records"]), 2),
            donations["totals"]["is-viso"],
        )

    # ------------------------------------------------------------------
    # kita
    # ------------------------------------------------------------------

    def test_kita_tab_carries_the_published_attachments(self) -> None:
        # Daukšys is the only fixture whose "Kita" tab has anything on it: the
        # signed pledge not to bribe voters, with its download link.
        self.assertEqual(
            self.dauksys["normalized"]["kita"],
            {
                "tekstai": ["Pasižadėjimas laikytis draudimo papirkti rinkėjus.pdf"],
                "nuorodos": [
                    "https://www.vrk.lt/statiniai/puslapiai/rinkimai/864/rnk1144/"
                    "kandidatai/kpdFileDownload/17736/"
                    "G_DAUKSYS_PASIZADEJIMAS_NEPAPIRKTI.pdf"
                ],
            },
        )

        for payload in self.everyone:
            if payload is self.dauksys:
                continue
            with self.subTest(candidate=payload["candidateId"]):
                self.assertEqual(
                    payload["normalized"]["kita"], {"tekstai": [], "nuorodos": []}
                )


if __name__ == "__main__":
    unittest.main()
