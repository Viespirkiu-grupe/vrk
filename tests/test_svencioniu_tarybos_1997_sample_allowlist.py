import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SAMPLES_ROOT = REPO_ROOT / "samples" / "html" / "1997-birzelio-29-svenciniu-tarybos-pakartotiniai"
# All 110 candidates across the nine party lists fielded in the Švenčionys
# repeat -- the complete field, since the whole (one-municipality) election
# is this small.
ALLOWED_CANDIDATE_DIRS = {
    "achranovic-agrikina",
    "ankenas-romualdas",
    "babusis-algis-stepanas",
    "bagdonas-juozas",
    "belanova-janina",
    "beperscius-kazimiras",
    "bliudzius-alvydas",
    "borovskij-aleksandr",
    "borovskis-vitoldas",
    "brazauskiene-audra",
    "braziene-vida-emile",
    "buceliene-veronika",
    "bulka-vytautas",
    "burakiene-jelena",
    "cenkus-vytautas",
    "ceponis-rimantas",
    "cepuliene-danute",
    "cesliak-leokadija",
    "cuvalov-vitold",
    "daugirdiene-marija",
    "davidonis-audrius",
    "deveikiene-aldona",
    "driomina-ceslava",
    "dubauskiene-joleta-veronika",
    "dubicki-veslav",
    "gadliauskas-romualdas",
    "gailiusiene-regina",
    "gegiene-irena",
    "grigiene-alfreda",
    "guobys-juozas",
    "iljina-larisa",
    "jakstas-juozas",
    "jankauskiene-irena",
    "jasiulioniene-daiva",
    "jedinskij-vladislav",
    "jedinskij-zbignev",
    "jurkeniene-regina",
    "jurkevic-ana",
    "jurkevicius-algirdas",
    "jurkovlianecas-tadeusas",
    "jursenas-ceslovas",
    "kaminskas-alvidas",
    "karaliunas-vladas",
    "karvelis-petras",
    "karvelis-pranas",
    "kasinskas-jonas",
    "kazimierenaite-jurate",
    "kindurys-vidmantas",
    "kirdeika-ricardas",
    "klipcius-rimas",
    "kliseviciene-rita",
    "kliseviciene-stase",
    "kliukaite-elena",
    "kliukas-bronislovas-valerijus",
    "kulda-janina",
    "lapeniene-viktorija",
    "laurinciukas-darius",
    "lauzadis-sarunas",
    "macijauskas-juozapas",
    "maldauskiene-irena",
    "maminskas-algimantas-mykolas",
    "markauskiene-laima",
    "martinkenas-vidmantas",
    "medart-jacevic",
    "menkovas-vasilijus",
    "meskela-ceslavas",
    "mikelionis-valdas",
    "navickas-valierius",
    "novickij-ceslav",
    "papinigis-vaclovas",
    "perveneckiene-edita",
    "petrauskiene-genovaite",
    "pirstelis-arunas",
    "pivoriunas-kestutis",
    "podvoiskij-stanislav",
    "politiene-irena",
    "posiunas-alfonsas",
    "prunskus-vaidotas",
    "rastenis-antanas",
    "rastenis-vytautas",
    "riaukiene-regina",
    "rokickis-mecislovas",
    "sanseviciene-teresa",
    "sapronavicius-tadas",
    "semasko-jurij",
    "semenas-vidas",
    "serenas-algimantas-antanas",
    "sivickiene-irena",
    "slabadiene-grazina",
    "stankunas-rimantas",
    "staras-kestutis",
    "stasiulevicius-sarunas",
    "striuzas-valdas",
    "sukov-nikolaj",
    "trusovas-genadijus",
    "tunevic-lucija",
    "umbraziuniene-giedra",
    "usov-fiodor",
    "uziala-juzefas",
    "vainickas-kazys",
    "vainoriene-nijole",
    "vaitkevicius-vytautas",
    "valatka-ramunas",
    "velicka-petras",
    "verikas-juozas",
    "vigelis-vytautas",
    "visimirskij-sergej",
    "zenkeviciene-viktorija",
    "zenkevicius-zenonas",
    "zukovska-henryka",
}
ALLOWED_NON_CANDIDATE_TOP_LEVEL_ENTRIES = {
    "list.html",
    "municipalities",
    "lists",
}


class SvencioniuTarybos1997SampleAllowlistTests(unittest.TestCase):
    def test_candidate_directory_contains_only_allowlisted_candidates(self) -> None:
        actual_dirs = {
            child.name
            for child in SAMPLES_ROOT.iterdir()
            if child.is_dir() and child.name not in ALLOWED_NON_CANDIDATE_TOP_LEVEL_ENTRIES
        }
        self.assertEqual(actual_dirs, ALLOWED_CANDIDATE_DIRS)
        self.assertEqual(len(ALLOWED_CANDIDATE_DIRS), 110)


if __name__ == "__main__":
    unittest.main()
