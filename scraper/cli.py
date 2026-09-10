import argparse
import sys

import requests
from pathlib import Path
from typing import Any

from scraper.elections.seimo_2016.anketa_parser import parse_anketa_samples as parse_2016_anketa_samples
from scraper.elections.seimo_2016.candidate_samples import (
    fetch_candidates_with_tabs as fetch_2016_candidates_with_tabs,
    fetch_first_candidate_with_tabs as fetch_2016_first_candidate_with_tabs,
)
from scraper.elections.seimo_2016.sitemap import (
    ELECTION_ID as SEIMO_2016_ELECTION_ID,
    build_sitemap_from_sample as build_2016_sitemap_from_sample,
    fetch_listing_sample as fetch_2016_listing_sample,
)
from scraper.elections.seimo_2020.candidate_samples import (
    fetch_candidates_with_tabs as fetch_2020_candidates_with_tabs,
    fetch_first_candidate_with_tabs as fetch_2020_first_candidate_with_tabs,
)
from scraper.elections.seimo_2020.anketa_parser import parse_anketa_samples as parse_2020_anketa_samples
from scraper.elections.seimo_2020.sitemap import (
    ELECTION_ID as SEIMO_2020_ELECTION_ID,
    build_sitemap_from_sample as build_2020_sitemap_from_sample,
    fetch_listing_sample as fetch_2020_listing_sample,
)
from scraper.elections.seimo_2024.anketa_parser import parse_anketa_samples as parse_2024_anketa_samples
from scraper.elections.seimo_2024.candidate_samples import (
    fetch_candidates_with_tabs as fetch_2024_candidates_with_tabs,
    fetch_first_candidate_with_tabs as fetch_2024_first_candidate_with_tabs,
)
from scraper.elections.seimo_2024.sitemap import (
    ELECTION_ID as SEIMO_2024_ELECTION_ID,
    build_sitemap_from_sample as build_2024_sitemap_from_sample,
    fetch_listing_sample as fetch_2024_listing_sample,
)
from scraper.elections.ep_2019.anketa_parser import parse_anketa_samples as parse_ep_2019_anketa_samples
from scraper.elections.ep_2019.candidate_samples import (
    fetch_candidates_with_tabs as fetch_ep_2019_candidates_with_tabs,
    fetch_first_candidate_with_tabs as fetch_ep_2019_first_candidate_with_tabs,
)
from scraper.elections.ep_2019.sitemap import (
    ELECTION_ID as EP_2019_ELECTION_ID,
    build_sitemap_from_sample as build_ep_2019_sitemap_from_sample,
    fetch_listing_sample as fetch_ep_2019_listing_sample,
)
from scraper.elections.ep_2024.anketa_parser import parse_anketa_samples as parse_ep_2024_anketa_samples
from scraper.elections.ep_2024.candidate_samples import (
    fetch_candidates_with_tabs as fetch_ep_2024_candidates_with_tabs,
    fetch_first_candidate_with_tabs as fetch_ep_2024_first_candidate_with_tabs,
)
from scraper.elections.ep_2024.sitemap import (
    ELECTION_ID as EP_2024_ELECTION_ID,
    build_sitemap_from_sample as build_ep_2024_sitemap_from_sample,
    fetch_listing_sample as fetch_ep_2024_listing_sample,
)
from scraper.elections.prezidento_2019.anketa_parser import (
    parse_anketa_samples as parse_prezidento_2019_anketa_samples,
)
from scraper.elections.prezidento_2019.candidate_samples import (
    fetch_candidates_with_tabs as fetch_prezidento_2019_candidates_with_tabs,
    fetch_first_candidate_with_tabs as fetch_prezidento_2019_first_candidate_with_tabs,
)
from scraper.elections.prezidento_2019.sitemap import (
    ELECTION_ID as PREZIDENTO_2019_ELECTION_ID,
    build_sitemap_from_sample as build_prezidento_2019_sitemap_from_sample,
    fetch_listing_sample as fetch_prezidento_2019_listing_sample,
)
from scraper.elections.prezidento_2024.anketa_parser import (
    parse_anketa_samples as parse_prezidento_2024_anketa_samples,
)
from scraper.elections.prezidento_2024.candidate_samples import (
    fetch_candidates_with_tabs as fetch_prezidento_2024_candidates_with_tabs,
    fetch_first_candidate_with_tabs as fetch_prezidento_2024_first_candidate_with_tabs,
)
from scraper.elections.prezidento_2024.sitemap import (
    ELECTION_ID as PREZIDENTO_2024_ELECTION_ID,
    build_sitemap_from_sample as build_prezidento_2024_sitemap_from_sample,
    fetch_listing_sample as fetch_prezidento_2024_listing_sample,
)
from scraper.elections.kupiskio_mero_2023.anketa_parser import (
    parse_anketa_samples as parse_kupiskio_mero_2023_anketa_samples,
)
from scraper.elections.kupiskio_mero_2023.candidate_samples import (
    fetch_candidates_with_tabs as fetch_kupiskio_mero_2023_candidates_with_tabs,
    fetch_first_candidate_with_tabs as fetch_kupiskio_mero_2023_first_candidate_with_tabs,
)
from scraper.elections.kupiskio_mero_2023.sitemap import (
    ELECTION_ID as KUPISKIO_MERO_2023_ELECTION_ID,
    build_sitemap_from_sample as build_kupiskio_mero_2023_sitemap_from_sample,
    fetch_listing_sample as fetch_kupiskio_mero_2023_listing_sample,
)
from scraper.elections.visagino_mero_2023.anketa_parser import (
    parse_anketa_samples as parse_visagino_mero_2023_anketa_samples,
)
from scraper.elections.visagino_mero_2023.candidate_samples import (
    fetch_candidates_with_tabs as fetch_visagino_mero_2023_candidates_with_tabs,
    fetch_first_candidate_with_tabs as fetch_visagino_mero_2023_first_candidate_with_tabs,
)
from scraper.elections.visagino_mero_2023.sitemap import (
    ELECTION_ID as VISAGINO_MERO_2023_ELECTION_ID,
    build_sitemap_from_sample as build_visagino_mero_2023_sitemap_from_sample,
    fetch_listing_sample as fetch_visagino_mero_2023_listing_sample,
)
from scraper.elections.seimo_raseiniu_kedainiu_2023.anketa_parser import (
    parse_anketa_samples as parse_seimo_raseiniu_kedainiu_2023_anketa_samples,
)
from scraper.elections.seimo_raseiniu_kedainiu_2023.candidate_samples import (
    fetch_candidates_with_tabs as fetch_seimo_raseiniu_kedainiu_2023_candidates_with_tabs,
    fetch_first_candidate_with_tabs as fetch_seimo_raseiniu_kedainiu_2023_first_candidate_with_tabs,
)
from scraper.elections.seimo_raseiniu_kedainiu_2023.sitemap import (
    ELECTION_ID as SEIMO_RASEINIU_KEDAINIU_2023_ELECTION_ID,
    build_sitemap_from_sample as build_seimo_raseiniu_kedainiu_2023_sitemap_from_sample,
    fetch_listing_sample as fetch_seimo_raseiniu_kedainiu_2023_listing_sample,
)
from scraper.elections.meru_2025.anketa_parser import (
    parse_anketa_samples as parse_meru_2025_anketa_samples,
)
from scraper.elections.meru_2025.candidate_samples import (
    fetch_candidates_with_tabs as fetch_meru_2025_candidates_with_tabs,
    fetch_first_candidate_with_tabs as fetch_meru_2025_first_candidate_with_tabs,
)
from scraper.elections.meru_2025.sitemap import (
    ELECTION_ID as MERU_2025_ELECTION_ID,
    build_sitemap_from_sample as build_meru_2025_sitemap_from_sample,
    fetch_listing_sample as fetch_meru_2025_listing_sample,
)
from scraper.elections.meru_2017.anketa_parser import (
    parse_anketa_samples as parse_meru_2017_anketa_samples,
)
from scraper.elections.meru_2017.candidate_samples import (
    fetch_candidates_with_tabs as fetch_meru_2017_candidates_with_tabs,
    fetch_first_candidate_with_tabs as fetch_meru_2017_first_candidate_with_tabs,
)
from scraper.elections.meru_2017.sitemap import (
    ELECTION_ID as MERU_2017_ELECTION_ID,
    build_sitemap_from_sample as build_meru_2017_sitemap_from_sample,
    fetch_listing_sample as fetch_meru_2017_listing_sample,
)
from scraper.elections.marijampoles_mero_2017.anketa_parser import (
    parse_anketa_samples as parse_marijampoles_mero_2017_anketa_samples,
)
from scraper.elections.marijampoles_mero_2017.candidate_samples import (
    fetch_candidates_with_tabs as fetch_marijampoles_mero_2017_candidates_with_tabs,
    fetch_first_candidate_with_tabs as fetch_marijampoles_mero_2017_first_candidate_with_tabs,
)
from scraper.elections.marijampoles_mero_2017.sitemap import (
    ELECTION_ID as MARIJAMPOLES_MERO_2017_ELECTION_ID,
    build_sitemap_from_sample as build_marijampoles_mero_2017_sitemap_from_sample,
    fetch_listing_sample as fetch_marijampoles_mero_2017_listing_sample,
)
from scraper.elections.meru_2021.anketa_parser import (
    parse_anketa_samples as parse_meru_2021_anketa_samples,
)
from scraper.elections.meru_2021.candidate_samples import (
    fetch_candidates_with_tabs as fetch_meru_2021_candidates_with_tabs,
    fetch_first_candidate_with_tabs as fetch_meru_2021_first_candidate_with_tabs,
)
from scraper.elections.meru_2021.sitemap import (
    ELECTION_ID as MERU_2021_ELECTION_ID,
    build_sitemap_from_sample as build_meru_2021_sitemap_from_sample,
    fetch_listing_sample as fetch_meru_2021_listing_sample,
)
from scraper.elections.radviliskio_mero_2021.anketa_parser import (
    parse_anketa_samples as parse_radviliskio_mero_2021_anketa_samples,
)
from scraper.elections.radviliskio_mero_2021.candidate_samples import (
    fetch_candidates_with_tabs as fetch_radviliskio_mero_2021_candidates_with_tabs,
    fetch_first_candidate_with_tabs as fetch_radviliskio_mero_2021_first_candidate_with_tabs,
)
from scraper.elections.radviliskio_mero_2021.sitemap import (
    ELECTION_ID as RADVILISKIO_MERO_2021_ELECTION_ID,
    build_sitemap_from_sample as build_radviliskio_mero_2021_sitemap_from_sample,
    fetch_listing_sample as fetch_radviliskio_mero_2021_listing_sample,
)
from scraper.elections.seimo_anyksciu_panevezio_2017.anketa_parser import (
    parse_anketa_samples as parse_seimo_anyksciu_panevezio_2017_anketa_samples,
)
from scraper.elections.seimo_anyksciu_panevezio_2017.candidate_samples import (
    fetch_candidates_with_tabs as fetch_seimo_anyksciu_panevezio_2017_candidates_with_tabs,
    fetch_first_candidate_with_tabs as fetch_seimo_anyksciu_panevezio_2017_first_candidate_with_tabs,
)
from scraper.elections.seimo_anyksciu_panevezio_2017.sitemap import (
    ELECTION_ID as SEIMO_ANYKSCIU_PANEVEZIO_2017_ELECTION_ID,
    build_sitemap_from_sample as build_seimo_anyksciu_panevezio_2017_sitemap_from_sample,
    fetch_listing_sample as fetch_seimo_anyksciu_panevezio_2017_listing_sample,
)
from scraper.elections.seimo_zanavyku_2018.anketa_parser import (
    parse_anketa_samples as parse_seimo_zanavyku_2018_anketa_samples,
)
from scraper.elections.seimo_zanavyku_2018.candidate_samples import (
    fetch_candidates_with_tabs as fetch_seimo_zanavyku_2018_candidates_with_tabs,
    fetch_first_candidate_with_tabs as fetch_seimo_zanavyku_2018_first_candidate_with_tabs,
)
from scraper.elections.seimo_zanavyku_2018.sitemap import (
    ELECTION_ID as SEIMO_ZANAVYKU_2018_ELECTION_ID,
    build_sitemap_from_sample as build_seimo_zanavyku_2018_sitemap_from_sample,
    fetch_listing_sample as fetch_seimo_zanavyku_2018_listing_sample,
)
from scraper.elections.seimo_2019.anketa_parser import (
    parse_anketa_samples as parse_seimo_2019_anketa_samples,
)
from scraper.elections.seimo_2019.candidate_samples import (
    fetch_candidates_with_tabs as fetch_seimo_2019_candidates_with_tabs,
    fetch_first_candidate_with_tabs as fetch_seimo_2019_first_candidate_with_tabs,
)
from scraper.elections.seimo_2019.sitemap import (
    ELECTION_ID as SEIMO_2019_ELECTION_ID,
    build_sitemap_from_sample as build_seimo_2019_sitemap_from_sample,
    fetch_listing_sample as fetch_seimo_2019_listing_sample,
)
from scraper.elections.savivaldybiu_2023.anketa_parser import (
    parse_anketa_samples as parse_savivaldybiu_2023_anketa_samples,
)
from scraper.elections.savivaldybiu_2023.candidate_samples import (
    fetch_candidates_with_tabs as fetch_savivaldybiu_2023_candidates_with_tabs,
    fetch_first_candidate_with_tabs as fetch_savivaldybiu_2023_first_candidate_with_tabs,
)
from scraper.elections.savivaldybiu_2023.sitemap import (
    ELECTION_ID as SAVIVALDYBIU_2023_ELECTION_ID,
    build_sitemap_from_sample as build_savivaldybiu_2023_sitemap_from_sample,
    fetch_listing_sample as fetch_savivaldybiu_2023_listing_sample,
)
from scraper.elections.savivaldybiu_2019.anketa_parser import (
    parse_anketa_samples as parse_savivaldybiu_2019_anketa_samples,
)
from scraper.elections.savivaldybiu_2019.candidate_samples import (
    fetch_candidates_with_tabs as fetch_savivaldybiu_2019_candidates_with_tabs,
    fetch_first_candidate_with_tabs as fetch_savivaldybiu_2019_first_candidate_with_tabs,
)
from scraper.elections.savivaldybiu_2019.sitemap import (
    ELECTION_ID as SAVIVALDYBIU_2019_ELECTION_ID,
    build_sitemap_from_sample as build_savivaldybiu_2019_sitemap_from_sample,
    fetch_listing_sample as fetch_savivaldybiu_2019_listing_sample,
)
from scraper.elections.seimo_zirmunu_2015.anketa_parser import (
    parse_anketa_samples as parse_seimo_zirmunu_2015_anketa_samples,
)
from scraper.elections.seimo_zirmunu_2015.candidate_samples import (
    fetch_candidates_with_tabs as fetch_seimo_zirmunu_2015_candidates_with_tabs,
    fetch_first_candidate_with_tabs as fetch_seimo_zirmunu_2015_first_candidate_with_tabs,
)
from scraper.elections.seimo_zirmunu_2015.sitemap import (
    ELECTION_ID as SEIMO_ZIRMUNU_2015_ELECTION_ID,
    build_sitemap_from_sample as build_seimo_zirmunu_2015_sitemap_from_sample,
    fetch_listing_sample as fetch_seimo_zirmunu_2015_listing_sample,
)
from scraper.elections.seimo_varenos_eisiskiu_2015.anketa_parser import (
    parse_anketa_samples as parse_seimo_varenos_eisiskiu_2015_anketa_samples,
)
from scraper.elections.seimo_varenos_eisiskiu_2015.candidate_samples import (
    fetch_candidates_with_tabs as fetch_seimo_varenos_eisiskiu_2015_candidates_with_tabs,
    fetch_first_candidate_with_tabs as fetch_seimo_varenos_eisiskiu_2015_first_candidate_with_tabs,
)
from scraper.elections.seimo_varenos_eisiskiu_2015.sitemap import (
    ELECTION_ID as SEIMO_VARENOS_EISISKIU_2015_ELECTION_ID,
    build_sitemap_from_sample as build_seimo_varenos_eisiskiu_2015_sitemap_from_sample,
    fetch_listing_sample as fetch_seimo_varenos_eisiskiu_2015_listing_sample,
)
from scraper.elections.telsiu_mero_2015.anketa_parser import (
    parse_anketa_samples as parse_telsiu_mero_2015_anketa_samples,
)
from scraper.elections.telsiu_mero_2015.candidate_samples import (
    fetch_candidates_with_tabs as fetch_telsiu_mero_2015_candidates_with_tabs,
    fetch_first_candidate_with_tabs as fetch_telsiu_mero_2015_first_candidate_with_tabs,
)
from scraper.elections.telsiu_mero_2015.sitemap import (
    ELECTION_ID as TELSIU_MERO_2015_ELECTION_ID,
    build_sitemap_from_sample as build_telsiu_mero_2015_sitemap_from_sample,
    fetch_listing_sample as fetch_telsiu_mero_2015_listing_sample,
)
from scraper.elections.pakartotiniai_sirvintu_traku_2015.anketa_parser import (
    parse_anketa_samples as parse_pakartotiniai_sirvintu_traku_2015_anketa_samples,
)
from scraper.elections.pakartotiniai_sirvintu_traku_2015.candidate_samples import (
    fetch_candidates_with_tabs as fetch_pakartotiniai_sirvintu_traku_2015_candidates_with_tabs,
    fetch_first_candidate_with_tabs as fetch_pakartotiniai_sirvintu_traku_2015_first_candidate_with_tabs,
)
from scraper.elections.pakartotiniai_sirvintu_traku_2015.sitemap import (
    ELECTION_ID as PAKARTOTINIAI_SIRVINTU_TRAKU_2015_ELECTION_ID,
    build_sitemap_from_sample as build_pakartotiniai_sirvintu_traku_2015_sitemap_from_sample,
    fetch_listing_sample as fetch_pakartotiniai_sirvintu_traku_2015_listing_sample,
)
from scraper.elections.pakartotiniai_silutes_2015.anketa_parser import (
    parse_anketa_samples as parse_pakartotiniai_silutes_2015_anketa_samples,
)
from scraper.elections.pakartotiniai_silutes_2015.candidate_samples import (
    fetch_candidates_with_tabs as fetch_pakartotiniai_silutes_2015_candidates_with_tabs,
    fetch_first_candidate_with_tabs as fetch_pakartotiniai_silutes_2015_first_candidate_with_tabs,
)
from scraper.elections.pakartotiniai_silutes_2015.sitemap import (
    ELECTION_ID as PAKARTOTINIAI_SILUTES_2015_ELECTION_ID,
    build_sitemap_from_sample as build_pakartotiniai_silutes_2015_sitemap_from_sample,
    fetch_listing_sample as fetch_pakartotiniai_silutes_2015_listing_sample,
)
from scraper.elections.savivaldybiu_2007.anketa_parser import (
    parse_anketa_samples as parse_savivaldybiu_2007_anketa_samples,
)
from scraper.elections.savivaldybiu_2007.candidate_samples import (
    fetch_candidates_with_tabs as fetch_savivaldybiu_2007_candidates_with_tabs,
    fetch_first_candidate_with_tabs as fetch_savivaldybiu_2007_first_candidate_with_tabs,
)
from scraper.elections.savivaldybiu_2007.sitemap import (
    ELECTION_ID as SAVIVALDYBIU_2007_ELECTION_ID,
    build_sitemap_from_sample as build_savivaldybiu_2007_sitemap_from_sample,
    fetch_listing_sample as fetch_savivaldybiu_2007_listing_sample,
)
from scraper.elections.savivaldybiu_2011.anketa_parser import (
    parse_anketa_samples as parse_savivaldybiu_2011_anketa_samples,
)
from scraper.elections.savivaldybiu_2011.candidate_samples import (
    fetch_candidates_with_tabs as fetch_savivaldybiu_2011_candidates_with_tabs,
    fetch_first_candidate_with_tabs as fetch_savivaldybiu_2011_first_candidate_with_tabs,
)
from scraper.elections.savivaldybiu_2011.sitemap import (
    ELECTION_ID as SAVIVALDYBIU_2011_ELECTION_ID,
    build_sitemap_from_sample as build_savivaldybiu_2011_sitemap_from_sample,
    fetch_listing_sample as fetch_savivaldybiu_2011_listing_sample,
)
from scraper.elections.savivaldybiu_2015.anketa_parser import (
    parse_anketa_samples as parse_savivaldybiu_2015_anketa_samples,
)
from scraper.elections.savivaldybiu_2015.candidate_samples import (
    fetch_candidates_with_tabs as fetch_savivaldybiu_2015_candidates_with_tabs,
    fetch_first_candidate_with_tabs as fetch_savivaldybiu_2015_first_candidate_with_tabs,
)
from scraper.elections.savivaldybiu_2015.sitemap import (
    ELECTION_ID as SAVIVALDYBIU_2015_ELECTION_ID,
    build_sitemap_from_sample as build_savivaldybiu_2015_sitemap_from_sample,
    fetch_listing_sample as fetch_savivaldybiu_2015_listing_sample,
)
from scraper.elections.seimo_1996.anketa_parser import (
    parse_anketa_samples as parse_seimo_1996_anketa_samples,
)
from scraper.elections.seimo_1996.candidate_samples import (
    fetch_candidates_with_tabs as fetch_seimo_1996_candidates_with_tabs,
    fetch_first_candidate_with_tabs as fetch_seimo_1996_first_candidate_with_tabs,
)
from scraper.elections.seimo_1996.sitemap import (
    ELECTION_ID as SEIMO_1996_ELECTION_ID,
    build_sitemap_from_sample as build_seimo_1996_sitemap_from_sample,
    fetch_listing_sample as fetch_seimo_1996_listing_sample,
)
from scraper.elections.seimo_pakartotiniai_1997_kovo.anketa_parser import (
    parse_anketa_samples as parse_seimo_pakartotiniai_1997_kovo_anketa_samples,
)
from scraper.elections.seimo_pakartotiniai_1997_kovo.candidate_samples import (
    fetch_candidates_with_tabs as fetch_seimo_pakartotiniai_1997_kovo_candidates_with_tabs,
    fetch_first_candidate_with_tabs as fetch_seimo_pakartotiniai_1997_kovo_first_candidate_with_tabs,
)
from scraper.elections.seimo_pakartotiniai_1997_kovo.sitemap import (
    ELECTION_ID as SEIMO_PAKARTOTINIAI_1997_KOVO_ELECTION_ID,
    build_sitemap_from_sample as build_seimo_pakartotiniai_1997_kovo_sitemap_from_sample,
    fetch_listing_sample as fetch_seimo_pakartotiniai_1997_kovo_listing_sample,
)
from scraper.elections.seimo_aukstaitijos_1997_gruodzio.anketa_parser import (
    parse_anketa_samples as parse_seimo_aukstaitijos_1997_gruodzio_anketa_samples,
)
from scraper.elections.seimo_aukstaitijos_1997_gruodzio.candidate_samples import (
    fetch_candidates_with_tabs as fetch_seimo_aukstaitijos_1997_gruodzio_candidates_with_tabs,
    fetch_first_candidate_with_tabs as fetch_seimo_aukstaitijos_1997_gruodzio_first_candidate_with_tabs,
)
from scraper.elections.seimo_aukstaitijos_1997_gruodzio.sitemap import (
    ELECTION_ID as SEIMO_AUKSTAITIJOS_1997_GRUODZIO_ELECTION_ID,
    build_sitemap_from_sample as build_seimo_aukstaitijos_1997_gruodzio_sitemap_from_sample,
    fetch_listing_sample as fetch_seimo_aukstaitijos_1997_gruodzio_listing_sample,
)
from scraper.elections.seimo_nevezio_1998_lapkricio.anketa_parser import (
    parse_anketa_samples as parse_seimo_nevezio_1998_lapkricio_anketa_samples,
)
from scraper.elections.seimo_nevezio_1998_lapkricio.candidate_samples import (
    fetch_candidates_with_tabs as fetch_seimo_nevezio_1998_lapkricio_candidates_with_tabs,
    fetch_first_candidate_with_tabs as fetch_seimo_nevezio_1998_lapkricio_first_candidate_with_tabs,
)
from scraper.elections.seimo_nevezio_1998_lapkricio.sitemap import (
    ELECTION_ID as SEIMO_NEVEZIO_1998_LAPKRICIO_ELECTION_ID,
    build_sitemap_from_sample as build_seimo_nevezio_1998_lapkricio_sitemap_from_sample,
    fetch_listing_sample as fetch_seimo_nevezio_1998_lapkricio_listing_sample,
)
from scraper.elections.seimo_pakartotiniai_1998_kovo.anketa_parser import (
    parse_anketa_samples as parse_seimo_pakartotiniai_1998_kovo_anketa_samples,
)
from scraper.elections.seimo_pakartotiniai_1999_kovo.anketa_parser import (
    parse_anketa_samples as parse_seimo_pakartotiniai_1999_kovo_anketa_samples,
)
from scraper.elections.seimo_pakartotiniai_1998_kovo.candidate_samples import (
    fetch_candidates_with_tabs as fetch_seimo_pakartotiniai_1998_kovo_candidates_with_tabs,
    fetch_first_candidate_with_tabs as fetch_seimo_pakartotiniai_1998_kovo_first_candidate_with_tabs,
)
from scraper.elections.seimo_pakartotiniai_1999_kovo.candidate_samples import (
    fetch_candidates_with_tabs as fetch_seimo_pakartotiniai_1999_kovo_candidates_with_tabs,
    fetch_first_candidate_with_tabs as fetch_seimo_pakartotiniai_1999_kovo_first_candidate_with_tabs,
)
from scraper.elections.seimo_pakartotiniai_1998_kovo.sitemap import (
    ELECTION_ID as SEIMO_PAKARTOTINIAI_1998_KOVO_ELECTION_ID,
    build_sitemap_from_sample as build_seimo_pakartotiniai_1998_kovo_sitemap_from_sample,
    fetch_listing_sample as fetch_seimo_pakartotiniai_1998_kovo_listing_sample,
)
from scraper.elections.seimo_pakartotiniai_1999_kovo.sitemap import (
    ELECTION_ID as SEIMO_PAKARTOTINIAI_1999_KOVO_ELECTION_ID,
    build_sitemap_from_sample as build_seimo_pakartotiniai_1999_kovo_sitemap_from_sample,
    fetch_listing_sample as fetch_seimo_pakartotiniai_1999_kovo_listing_sample,
)
from scraper.elections.savivaldybiu_1997.anketa_parser import (
    parse_anketa_samples as parse_savivaldybiu_1997_anketa_samples,
)
from scraper.elections.savivaldybiu_1997.candidate_samples import (
    fetch_candidates_with_tabs as fetch_savivaldybiu_1997_candidates_with_tabs,
    fetch_first_candidate_with_tabs as fetch_savivaldybiu_1997_first_candidate_with_tabs,
)
from scraper.elections.savivaldybiu_1997.sitemap import (
    ELECTION_ID as SAVIVALDYBIU_1997_ELECTION_ID,
    build_sitemap_from_sample as build_savivaldybiu_1997_sitemap_from_sample,
    fetch_listing_sample as fetch_savivaldybiu_1997_listing_sample,
)
from scraper.elections.svencioniu_tarybos_1997.anketa_parser import (
    parse_anketa_samples as parse_svencioniu_tarybos_1997_anketa_samples,
)
from scraper.elections.svencioniu_tarybos_1997.candidate_samples import (
    fetch_candidates_with_tabs as fetch_svencioniu_tarybos_1997_candidates_with_tabs,
    fetch_first_candidate_with_tabs as fetch_svencioniu_tarybos_1997_first_candidate_with_tabs,
)
from scraper.elections.svencioniu_tarybos_1997.sitemap import (
    ELECTION_ID as SVENCIONIU_TARYBOS_1997_ELECTION_ID,
    build_sitemap_from_sample as build_svencioniu_tarybos_1997_sitemap_from_sample,
    fetch_listing_sample as fetch_svencioniu_tarybos_1997_listing_sample,
)
from scraper.elections.prezidento_2009.anketa_parser import (
    parse_anketa_samples as parse_prezidento_2009_anketa_samples,
)
from scraper.elections.prezidento_2009.candidate_samples import (
    fetch_candidates_with_tabs as fetch_prezidento_2009_candidates_with_tabs,
    fetch_first_candidate_with_tabs as fetch_prezidento_2009_first_candidate_with_tabs,
)
from scraper.elections.prezidento_2009.sitemap import (
    ELECTION_ID as PREZIDENTO_2009_ELECTION_ID,
    build_sitemap_from_sample as build_prezidento_2009_sitemap_from_sample,
    fetch_listing_sample as fetch_prezidento_2009_listing_sample,
)
from scraper.elections.prezidento_2014.anketa_parser import (
    parse_anketa_samples as parse_prezidento_2014_anketa_samples,
)
from scraper.elections.prezidento_2014.candidate_samples import (
    fetch_candidates_with_tabs as fetch_prezidento_2014_candidates_with_tabs,
    fetch_first_candidate_with_tabs as fetch_prezidento_2014_first_candidate_with_tabs,
)
from scraper.elections.prezidento_2014.sitemap import (
    ELECTION_ID as PREZIDENTO_2014_ELECTION_ID,
    build_sitemap_from_sample as build_prezidento_2014_sitemap_from_sample,
    fetch_listing_sample as fetch_prezidento_2014_listing_sample,
)
from scraper.elections.seimo_birzu_zarasu_ukmerges_2013.anketa_parser import (
    parse_anketa_samples as parse_seimo_birzu_zarasu_ukmerges_2013_anketa_samples,
)
from scraper.elections.seimo_birzu_zarasu_ukmerges_2013.candidate_samples import (
    fetch_candidates_with_tabs as fetch_seimo_birzu_zarasu_ukmerges_2013_candidates_with_tabs,
    fetch_first_candidate_with_tabs as fetch_seimo_birzu_zarasu_ukmerges_2013_first_candidate_with_tabs,
)
from scraper.elections.seimo_birzu_zarasu_ukmerges_2013.sitemap import (
    ELECTION_ID as SEIMO_BIRZU_ZARASU_UKMERGES_2013_ELECTION_ID,
    build_sitemap_from_sample as build_seimo_birzu_zarasu_ukmerges_2013_sitemap_from_sample,
    fetch_listing_sample as fetch_seimo_birzu_zarasu_ukmerges_2013_listing_sample,
)
from scraper.elections.ep_2009.anketa_parser import (
    parse_anketa_samples as parse_ep_2009_anketa_samples,
)
from scraper.elections.ep_2009.candidate_samples import (
    fetch_candidates_with_tabs as fetch_ep_2009_candidates_with_tabs,
    fetch_first_candidate_with_tabs as fetch_ep_2009_first_candidate_with_tabs,
)
from scraper.elections.ep_2009.sitemap import (
    ELECTION_ID as EP_2009_ELECTION_ID,
    build_sitemap_from_sample as build_ep_2009_sitemap_from_sample,
    fetch_listing_sample as fetch_ep_2009_listing_sample,
)
from scraper.elections.ep_2014.anketa_parser import (
    parse_anketa_samples as parse_ep_2014_anketa_samples,
)
from scraper.elections.ep_2014.candidate_samples import (
    fetch_candidates_with_tabs as fetch_ep_2014_candidates_with_tabs,
    fetch_first_candidate_with_tabs as fetch_ep_2014_first_candidate_with_tabs,
)
from scraper.elections.ep_2014.sitemap import (
    ELECTION_ID as EP_2014_ELECTION_ID,
    build_sitemap_from_sample as build_ep_2014_sitemap_from_sample,
    fetch_listing_sample as fetch_ep_2014_listing_sample,
)
from scraper.elections.seimo_dzukijos_2007.anketa_parser import (
    parse_anketa_samples as parse_seimo_dzukijos_2007_anketa_samples,
)
from scraper.elections.seimo_dzukijos_2007.candidate_samples import (
    fetch_candidates_with_tabs as fetch_seimo_dzukijos_2007_candidates_with_tabs,
    fetch_first_candidate_with_tabs as fetch_seimo_dzukijos_2007_first_candidate_with_tabs,
)
from scraper.elections.seimo_dzukijos_2007.sitemap import (
    ELECTION_ID as SEIMO_DZUKIJOS_2007_ELECTION_ID,
    build_sitemap_from_sample as build_seimo_dzukijos_2007_sitemap_from_sample,
    fetch_listing_sample as fetch_seimo_dzukijos_2007_listing_sample,
)
from scraper.elections.ep_2004.anketa_parser import (
    parse_anketa_samples as parse_ep_2004_anketa_samples,
)
from scraper.elections.ep_2004.candidate_samples import (
    fetch_candidates_with_tabs as fetch_ep_2004_candidates_with_tabs,
    fetch_first_candidate_with_tabs as fetch_ep_2004_first_candidate_with_tabs,
)
from scraper.elections.ep_2004.sitemap import (
    ELECTION_ID as EP_2004_ELECTION_ID,
    build_sitemap_from_sample as build_ep_2004_sitemap_from_sample,
    fetch_listing_sample as fetch_ep_2004_listing_sample,
)
from scraper.elections.prezidento_2004.anketa_parser import (
    parse_anketa_samples as parse_prezidento_2004_anketa_samples,
)
from scraper.elections.prezidento_2004.candidate_samples import (
    fetch_candidates_with_tabs as fetch_prezidento_2004_candidates_with_tabs,
    fetch_first_candidate_with_tabs as fetch_prezidento_2004_first_candidate_with_tabs,
)
from scraper.elections.prezidento_2004.sitemap import (
    ELECTION_ID as PREZIDENTO_2004_ELECTION_ID,
    build_sitemap_from_sample as build_prezidento_2004_sitemap_from_sample,
    fetch_listing_sample as fetch_prezidento_2004_listing_sample,
)
from scraper.elections.prezidento_2002.anketa_parser import (
    parse_anketa_samples as parse_prezidento_2002_anketa_samples,
)
from scraper.elections.prezidento_2002.candidate_samples import (
    fetch_candidates_with_tabs as fetch_prezidento_2002_candidates_with_tabs,
    fetch_first_candidate_with_tabs as fetch_prezidento_2002_first_candidate_with_tabs,
)
from scraper.elections.prezidento_2002.sitemap import (
    ELECTION_ID as PREZIDENTO_2002_ELECTION_ID,
    build_sitemap_from_sample as build_prezidento_2002_sitemap_from_sample,
    fetch_listing_sample as fetch_prezidento_2002_listing_sample,
)
from scraper.elections.seimo_2004.anketa_parser import (
    parse_anketa_samples as parse_seimo_2004_anketa_samples,
)
from scraper.elections.seimo_2004.candidate_samples import (
    fetch_candidates_with_tabs as fetch_seimo_2004_candidates_with_tabs,
    fetch_first_candidate_with_tabs as fetch_seimo_2004_first_candidate_with_tabs,
)
from scraper.elections.seimo_2004.sitemap import (
    ELECTION_ID as SEIMO_2004_ELECTION_ID,
    build_sitemap_from_sample as build_seimo_2004_sitemap_from_sample,
    fetch_listing_sample as fetch_seimo_2004_listing_sample,
)
from scraper.elections.seimo_nauji_2003.anketa_parser import (
    parse_anketa_samples as parse_seimo_nauji_2003_anketa_samples,
)
from scraper.elections.seimo_nauji_2003.candidate_samples import (
    fetch_candidates_with_tabs as fetch_seimo_nauji_2003_candidates_with_tabs,
    fetch_first_candidate_with_tabs as fetch_seimo_nauji_2003_first_candidate_with_tabs,
)
from scraper.elections.seimo_nauji_2003.sitemap import (
    ELECTION_ID as SEIMO_NAUJI_2003_ELECTION_ID,
    build_sitemap_from_sample as build_seimo_nauji_2003_sitemap_from_sample,
    fetch_listing_sample as fetch_seimo_nauji_2003_listing_sample,
)
from scraper.elections.seimo_kedainiu_2005.anketa_parser import (
    parse_anketa_samples as parse_seimo_kedainiu_2005_anketa_samples,
)
from scraper.elections.seimo_kedainiu_2005.candidate_samples import (
    fetch_candidates_with_tabs as fetch_seimo_kedainiu_2005_candidates_with_tabs,
    fetch_first_candidate_with_tabs as fetch_seimo_kedainiu_2005_first_candidate_with_tabs,
)
from scraper.elections.seimo_kedainiu_2005.sitemap import (
    ELECTION_ID as SEIMO_KEDAINIU_2005_ELECTION_ID,
    build_sitemap_from_sample as build_seimo_kedainiu_2005_sitemap_from_sample,
    fetch_listing_sample as fetch_seimo_kedainiu_2005_listing_sample,
)
from scraper.elections.seimo_2000.anketa_parser import (
    parse_anketa_samples as parse_seimo_2000_anketa_samples,
)
from scraper.elections.seimo_2000.candidate_samples import (
    fetch_candidates_with_tabs as fetch_seimo_2000_candidates_with_tabs,
    fetch_first_candidate_with_tabs as fetch_seimo_2000_first_candidate_with_tabs,
)
from scraper.elections.seimo_2000.sitemap import (
    ELECTION_ID as SEIMO_2000_ELECTION_ID,
    build_sitemap_from_sample as build_seimo_2000_sitemap_from_sample,
    fetch_listing_sample as fetch_seimo_2000_listing_sample,
)
from scraper.elections.savivaldybiu_2000.anketa_parser import (
    parse_anketa_samples as parse_savivaldybiu_2000_anketa_samples,
)
from scraper.elections.savivaldybiu_2000.candidate_samples import (
    fetch_candidates_with_tabs as fetch_savivaldybiu_2000_candidates_with_tabs,
    fetch_first_candidate_with_tabs as fetch_savivaldybiu_2000_first_candidate_with_tabs,
)
from scraper.elections.savivaldybiu_2000.sitemap import (
    ELECTION_ID as SAVIVALDYBIU_2000_ELECTION_ID,
    build_sitemap_from_sample as build_savivaldybiu_2000_sitemap_from_sample,
    fetch_listing_sample as fetch_savivaldybiu_2000_listing_sample,
)
from scraper.elections.savivaldybiu_2002.anketa_parser import (
    parse_anketa_samples as parse_savivaldybiu_2002_anketa_samples,
)
from scraper.elections.savivaldybiu_2002.candidate_samples import (
    fetch_candidates_with_tabs as fetch_savivaldybiu_2002_candidates_with_tabs,
    fetch_first_candidate_with_tabs as fetch_savivaldybiu_2002_first_candidate_with_tabs,
)
from scraper.elections.savivaldybiu_2002.sitemap import (
    ELECTION_ID as SAVIVALDYBIU_2002_ELECTION_ID,
    build_sitemap_from_sample as build_savivaldybiu_2002_sitemap_from_sample,
    fetch_listing_sample as fetch_savivaldybiu_2002_listing_sample,
)
from scraper.elections.seimo_silales_silutes_vilniaus_salcininku_2009.anketa_parser import (
    parse_anketa_samples as parse_seimo_silales_silutes_vilniaus_salcininku_2009_anketa_samples,
)
from scraper.elections.seimo_silales_silutes_vilniaus_salcininku_2009.candidate_samples import (
    fetch_candidates_with_tabs as fetch_seimo_silales_silutes_vilniaus_salcininku_2009_candidates_with_tabs,
    fetch_first_candidate_with_tabs as fetch_seimo_silales_silutes_vilniaus_salcininku_2009_first_candidate_with_tabs,
)
from scraper.elections.seimo_silales_silutes_vilniaus_salcininku_2009.sitemap import (
    ELECTION_ID as SEIMO_SILALES_SILUTES_VILNIAUS_SALCININKU_2009_ELECTION_ID,
    build_sitemap_from_sample as build_seimo_silales_silutes_vilniaus_salcininku_2009_sitemap_from_sample,
    fetch_listing_sample as fetch_seimo_silales_silutes_vilniaus_salcininku_2009_listing_sample,
)
from scraper.elections.seimo_marijampoles_2011.anketa_parser import (
    parse_anketa_samples as parse_seimo_marijampoles_2011_anketa_samples,
)
from scraper.elections.seimo_marijampoles_2011.candidate_samples import (
    fetch_candidates_with_tabs as fetch_seimo_marijampoles_2011_candidates_with_tabs,
    fetch_first_candidate_with_tabs as fetch_seimo_marijampoles_2011_first_candidate_with_tabs,
)
from scraper.elections.seimo_marijampoles_2011.sitemap import (
    ELECTION_ID as SEIMO_MARIJAMPOLES_2011_ELECTION_ID,
    build_sitemap_from_sample as build_seimo_marijampoles_2011_sitemap_from_sample,
    fetch_listing_sample as fetch_seimo_marijampoles_2011_listing_sample,
)
from scraper.elections.seimo_2008.anketa_parser import (
    parse_anketa_samples as parse_seimo_2008_anketa_samples,
)
from scraper.elections.seimo_2008.candidate_samples import (
    fetch_candidates_with_tabs as fetch_seimo_2008_candidates_with_tabs,
    fetch_first_candidate_with_tabs as fetch_seimo_2008_first_candidate_with_tabs,
)
from scraper.elections.seimo_2008.sitemap import (
    ELECTION_ID as SEIMO_2008_ELECTION_ID,
    build_sitemap_from_sample as build_seimo_2008_sitemap_from_sample,
    fetch_listing_sample as fetch_seimo_2008_listing_sample,
)
from scraper.elections.seimo_2012.anketa_parser import (
    parse_anketa_samples as parse_seimo_2012_anketa_samples,
)
from scraper.elections.seimo_2012.candidate_samples import (
    fetch_candidates_with_tabs as fetch_seimo_2012_candidates_with_tabs,
    fetch_first_candidate_with_tabs as fetch_seimo_2012_first_candidate_with_tabs,
)
from scraper.elections.seimo_2012.sitemap import (
    ELECTION_ID as SEIMO_2012_ELECTION_ID,
    build_sitemap_from_sample as build_seimo_2012_sitemap_from_sample,
    fetch_listing_sample as fetch_seimo_2012_listing_sample,
)
from scraper.elections.seimo_dzukijos_2007.results import build_results as build_seimo_dzukijos_2007_results
from scraper.elections.seimo_silales_silutes_vilniaus_salcininku_2009.results import build_results as build_seimo_silales_silutes_vilniaus_salcininku_2009_results
from scraper.elections.seimo_marijampoles_2011.results import build_results as build_seimo_marijampoles_2011_results
from scraper.elections.seimo_2008.results import build_results as build_seimo_2008_results
from scraper.elections.seimo_2012.results import build_results as build_seimo_2012_results
from scraper.elections.seimo_birzu_zarasu_ukmerges_2013.results import build_results as build_seimo_birzu_zarasu_ukmerges_2013_results
from scraper.elections.prezidento_2009.results import build_results as build_prezidento_2009_results
from scraper.elections.prezidento_2014.results import build_results as build_prezidento_2014_results
from scraper.elections.ep_2009.results import build_results as build_ep_2009_results
from scraper.elections.ep_2004.results import build_results as build_ep_2004_results
from scraper.elections.prezidento_2004.results import build_results as build_prezidento_2004_results
from scraper.elections.prezidento_2002.results import build_results as build_prezidento_2002_results
from scraper.elections.seimo_2004.results import build_results as build_seimo_2004_results
from scraper.elections.seimo_nauji_2003.results import build_results as build_seimo_nauji_2003_results
from scraper.elections.seimo_kedainiu_2005.results import build_results as build_seimo_kedainiu_2005_results
from scraper.elections.seimo_2000.results import build_results as build_seimo_2000_results
from scraper.elections.savivaldybiu_2000.results import build_results as build_savivaldybiu_2000_results
from scraper.elections.savivaldybiu_2002.results import build_results as build_savivaldybiu_2002_results
from scraper.elections.ep_2014.results import build_results as build_ep_2014_results
from scraper.elections.seimo_zirmunu_2015.results import build_results as build_seimo_zirmunu_2015_results
from scraper.elections.seimo_varenos_eisiskiu_2015.results import build_results as build_seimo_varenos_eisiskiu_2015_results
from scraper.elections.telsiu_mero_2015.results import build_results as build_telsiu_mero_2015_results
from scraper.elections.pakartotiniai_sirvintu_traku_2015.results import build_results as build_pakartotiniai_sirvintu_traku_2015_results
from scraper.elections.pakartotiniai_silutes_2015.results import build_results as build_pakartotiniai_silutes_2015_results
from scraper.elections.savivaldybiu_2015.results import build_results as build_savivaldybiu_2015_results
from scraper.elections.savivaldybiu_2011.results import build_results as build_savivaldybiu_2011_results
from scraper.elections.savivaldybiu_2007.results import build_results as build_savivaldybiu_2007_results
from scraper.elections.seimo_1996.results import build_results as build_seimo_1996_results
from scraper.elections.seimo_pakartotiniai_1997_kovo.results import build_results as build_seimo_pakartotiniai_1997_kovo_results
from scraper.elections.seimo_aukstaitijos_1997_gruodzio.results import build_results as build_seimo_aukstaitijos_1997_gruodzio_results
from scraper.elections.seimo_pakartotiniai_1998_kovo.results import build_results as build_seimo_pakartotiniai_1998_kovo_results
from scraper.elections.seimo_nevezio_1998_lapkricio.results import build_results as build_seimo_nevezio_1998_lapkricio_results
from scraper.elections.seimo_pakartotiniai_1999_kovo.results import build_results as build_seimo_pakartotiniai_1999_kovo_results
from scraper.elections.savivaldybiu_1997.results import build_results as build_savivaldybiu_1997_results
from scraper.elections.svencioniu_tarybos_1997.results import build_results as build_svencioniu_tarybos_1997_results
from scraper.shared import anomaly_report
from scraper.shared.anomalies import write_jsonl, write_run_events

ANOMALY_BASELINE = anomaly_report.BASELINE

FETCHABLE_ELECTION_IDS = [
    SEIMO_2016_ELECTION_ID,
    SEIMO_2020_ELECTION_ID,
    SEIMO_2024_ELECTION_ID,
    EP_2019_ELECTION_ID,
    EP_2024_ELECTION_ID,
    PREZIDENTO_2019_ELECTION_ID,
    PREZIDENTO_2024_ELECTION_ID,
    KUPISKIO_MERO_2023_ELECTION_ID,
    VISAGINO_MERO_2023_ELECTION_ID,
    SEIMO_RASEINIU_KEDAINIU_2023_ELECTION_ID,
    MERU_2025_ELECTION_ID,
    MERU_2017_ELECTION_ID,
    MARIJAMPOLES_MERO_2017_ELECTION_ID,
    MERU_2021_ELECTION_ID,
    RADVILISKIO_MERO_2021_ELECTION_ID,
    SEIMO_ANYKSCIU_PANEVEZIO_2017_ELECTION_ID,
    SEIMO_ZANAVYKU_2018_ELECTION_ID,
    SEIMO_2019_ELECTION_ID,
    SAVIVALDYBIU_2023_ELECTION_ID,
    SAVIVALDYBIU_2019_ELECTION_ID,
    SEIMO_ZIRMUNU_2015_ELECTION_ID,
    SEIMO_VARENOS_EISISKIU_2015_ELECTION_ID,
    TELSIU_MERO_2015_ELECTION_ID,
    PAKARTOTINIAI_SIRVINTU_TRAKU_2015_ELECTION_ID,
    PAKARTOTINIAI_SILUTES_2015_ELECTION_ID,
    SAVIVALDYBIU_2015_ELECTION_ID,
    SAVIVALDYBIU_2011_ELECTION_ID,
    SAVIVALDYBIU_2007_ELECTION_ID,
    SEIMO_1996_ELECTION_ID,
    SEIMO_PAKARTOTINIAI_1997_KOVO_ELECTION_ID,
    SEIMO_AUKSTAITIJOS_1997_GRUODZIO_ELECTION_ID,
    SEIMO_NEVEZIO_1998_LAPKRICIO_ELECTION_ID,
    SEIMO_PAKARTOTINIAI_1998_KOVO_ELECTION_ID,
    SEIMO_PAKARTOTINIAI_1999_KOVO_ELECTION_ID,
    SAVIVALDYBIU_1997_ELECTION_ID,
    SVENCIONIU_TARYBOS_1997_ELECTION_ID,
    PREZIDENTO_2014_ELECTION_ID,
    SEIMO_BIRZU_ZARASU_UKMERGES_2013_ELECTION_ID,
    EP_2014_ELECTION_ID,
    SEIMO_2012_ELECTION_ID,
    PREZIDENTO_2009_ELECTION_ID,
    EP_2009_ELECTION_ID,
    SEIMO_2008_ELECTION_ID,
    SEIMO_SILALES_SILUTES_VILNIAUS_SALCININKU_2009_ELECTION_ID,
    SEIMO_MARIJAMPOLES_2011_ELECTION_ID,
    SEIMO_DZUKIJOS_2007_ELECTION_ID,
    EP_2004_ELECTION_ID,
    PREZIDENTO_2004_ELECTION_ID,
    PREZIDENTO_2002_ELECTION_ID,
    SEIMO_2004_ELECTION_ID,
    SEIMO_NAUJI_2003_ELECTION_ID,
    SEIMO_KEDAINIU_2005_ELECTION_ID,
    SEIMO_2000_ELECTION_ID,
    SAVIVALDYBIU_2000_ELECTION_ID,
    SAVIVALDYBIU_2002_ELECTION_ID,
]
PARSABLE_ELECTION_IDS = [
    SEIMO_2016_ELECTION_ID,
    SEIMO_2020_ELECTION_ID,
    SEIMO_2024_ELECTION_ID,
    EP_2019_ELECTION_ID,
    EP_2024_ELECTION_ID,
    PREZIDENTO_2019_ELECTION_ID,
    PREZIDENTO_2024_ELECTION_ID,
    KUPISKIO_MERO_2023_ELECTION_ID,
    VISAGINO_MERO_2023_ELECTION_ID,
    SEIMO_RASEINIU_KEDAINIU_2023_ELECTION_ID,
    MERU_2025_ELECTION_ID,
    MERU_2017_ELECTION_ID,
    MARIJAMPOLES_MERO_2017_ELECTION_ID,
    MERU_2021_ELECTION_ID,
    RADVILISKIO_MERO_2021_ELECTION_ID,
    SEIMO_ANYKSCIU_PANEVEZIO_2017_ELECTION_ID,
    SEIMO_ZANAVYKU_2018_ELECTION_ID,
    SEIMO_2019_ELECTION_ID,
    SAVIVALDYBIU_2023_ELECTION_ID,
    SAVIVALDYBIU_2019_ELECTION_ID,
    SEIMO_ZIRMUNU_2015_ELECTION_ID,
    SEIMO_VARENOS_EISISKIU_2015_ELECTION_ID,
    TELSIU_MERO_2015_ELECTION_ID,
    PAKARTOTINIAI_SIRVINTU_TRAKU_2015_ELECTION_ID,
    PAKARTOTINIAI_SILUTES_2015_ELECTION_ID,
    SAVIVALDYBIU_2015_ELECTION_ID,
    SAVIVALDYBIU_2011_ELECTION_ID,
    SAVIVALDYBIU_2007_ELECTION_ID,
    SEIMO_1996_ELECTION_ID,
    SEIMO_PAKARTOTINIAI_1997_KOVO_ELECTION_ID,
    SEIMO_AUKSTAITIJOS_1997_GRUODZIO_ELECTION_ID,
    SEIMO_NEVEZIO_1998_LAPKRICIO_ELECTION_ID,
    SEIMO_PAKARTOTINIAI_1998_KOVO_ELECTION_ID,
    SEIMO_PAKARTOTINIAI_1999_KOVO_ELECTION_ID,
    SAVIVALDYBIU_1997_ELECTION_ID,
    SVENCIONIU_TARYBOS_1997_ELECTION_ID,
    PREZIDENTO_2014_ELECTION_ID,
    SEIMO_BIRZU_ZARASU_UKMERGES_2013_ELECTION_ID,
    EP_2014_ELECTION_ID,
    SEIMO_2012_ELECTION_ID,
    PREZIDENTO_2009_ELECTION_ID,
    EP_2009_ELECTION_ID,
    SEIMO_2008_ELECTION_ID,
    SEIMO_SILALES_SILUTES_VILNIAUS_SALCININKU_2009_ELECTION_ID,
    SEIMO_MARIJAMPOLES_2011_ELECTION_ID,
    SEIMO_DZUKIJOS_2007_ELECTION_ID,
    EP_2004_ELECTION_ID,
    PREZIDENTO_2004_ELECTION_ID,
    PREZIDENTO_2002_ELECTION_ID,
    SEIMO_2004_ELECTION_ID,
    SEIMO_NAUJI_2003_ELECTION_ID,
    SEIMO_KEDAINIU_2005_ELECTION_ID,
    SEIMO_2000_ELECTION_ID,
    SAVIVALDYBIU_2000_ELECTION_ID,
    SAVIVALDYBIU_2002_ELECTION_ID,
]

# Elections whose pages mark no winner and whose elected status is joined in
# from VRK's results tree (scraper/shared/election_results.py).
RESULTS_ELECTION_IDS = [
    SEIMO_DZUKIJOS_2007_ELECTION_ID,
    SEIMO_2008_ELECTION_ID,
    SEIMO_SILALES_SILUTES_VILNIAUS_SALCININKU_2009_ELECTION_ID,
    SEIMO_MARIJAMPOLES_2011_ELECTION_ID,
    PREZIDENTO_2009_ELECTION_ID,
    EP_2009_ELECTION_ID,
    SEIMO_2012_ELECTION_ID,
    SEIMO_BIRZU_ZARASU_UKMERGES_2013_ELECTION_ID,
    PREZIDENTO_2014_ELECTION_ID,
    EP_2014_ELECTION_ID,
    SEIMO_ZIRMUNU_2015_ELECTION_ID,
    SEIMO_VARENOS_EISISKIU_2015_ELECTION_ID,
    TELSIU_MERO_2015_ELECTION_ID,
    PAKARTOTINIAI_SIRVINTU_TRAKU_2015_ELECTION_ID,
    PAKARTOTINIAI_SILUTES_2015_ELECTION_ID,
    SAVIVALDYBIU_2015_ELECTION_ID,
    SAVIVALDYBIU_2011_ELECTION_ID,
    SAVIVALDYBIU_2007_ELECTION_ID,
    EP_2004_ELECTION_ID,
    PREZIDENTO_2004_ELECTION_ID,
    PREZIDENTO_2002_ELECTION_ID,
    SEIMO_2004_ELECTION_ID,
    SEIMO_NAUJI_2003_ELECTION_ID,
    SEIMO_KEDAINIU_2005_ELECTION_ID,
    SEIMO_2000_ELECTION_ID,
    SAVIVALDYBIU_2000_ELECTION_ID,
    SAVIVALDYBIU_2002_ELECTION_ID,
    SEIMO_1996_ELECTION_ID,
    SEIMO_PAKARTOTINIAI_1997_KOVO_ELECTION_ID,
    SEIMO_AUKSTAITIJOS_1997_GRUODZIO_ELECTION_ID,
    SEIMO_PAKARTOTINIAI_1998_KOVO_ELECTION_ID,
    SEIMO_NEVEZIO_1998_LAPKRICIO_ELECTION_ID,
    SEIMO_PAKARTOTINIAI_1999_KOVO_ELECTION_ID,
    SAVIVALDYBIU_1997_ELECTION_ID,
    SVENCIONIU_TARYBOS_1997_ELECTION_ID,
]

_RESULTS_BUILDERS = {
    SEIMO_DZUKIJOS_2007_ELECTION_ID: build_seimo_dzukijos_2007_results,
    SEIMO_2008_ELECTION_ID: build_seimo_2008_results,
    SEIMO_SILALES_SILUTES_VILNIAUS_SALCININKU_2009_ELECTION_ID: build_seimo_silales_silutes_vilniaus_salcininku_2009_results,
    SEIMO_MARIJAMPOLES_2011_ELECTION_ID: build_seimo_marijampoles_2011_results,
    PREZIDENTO_2009_ELECTION_ID: build_prezidento_2009_results,
    EP_2009_ELECTION_ID: build_ep_2009_results,
    EP_2004_ELECTION_ID: build_ep_2004_results,
    PREZIDENTO_2004_ELECTION_ID: build_prezidento_2004_results,
    PREZIDENTO_2002_ELECTION_ID: build_prezidento_2002_results,
    SEIMO_2004_ELECTION_ID: build_seimo_2004_results,
    SEIMO_NAUJI_2003_ELECTION_ID: build_seimo_nauji_2003_results,
    SEIMO_KEDAINIU_2005_ELECTION_ID: build_seimo_kedainiu_2005_results,
    SEIMO_2000_ELECTION_ID: build_seimo_2000_results,
    SAVIVALDYBIU_2000_ELECTION_ID: build_savivaldybiu_2000_results,
    SAVIVALDYBIU_2002_ELECTION_ID: build_savivaldybiu_2002_results,
    SEIMO_2012_ELECTION_ID: build_seimo_2012_results,
    SEIMO_BIRZU_ZARASU_UKMERGES_2013_ELECTION_ID: build_seimo_birzu_zarasu_ukmerges_2013_results,
    PREZIDENTO_2014_ELECTION_ID: build_prezidento_2014_results,
    EP_2014_ELECTION_ID: build_ep_2014_results,
    SEIMO_ZIRMUNU_2015_ELECTION_ID: build_seimo_zirmunu_2015_results,
    SEIMO_VARENOS_EISISKIU_2015_ELECTION_ID: build_seimo_varenos_eisiskiu_2015_results,
    TELSIU_MERO_2015_ELECTION_ID: build_telsiu_mero_2015_results,
    PAKARTOTINIAI_SIRVINTU_TRAKU_2015_ELECTION_ID: build_pakartotiniai_sirvintu_traku_2015_results,
    PAKARTOTINIAI_SILUTES_2015_ELECTION_ID: build_pakartotiniai_silutes_2015_results,
    SAVIVALDYBIU_2015_ELECTION_ID: build_savivaldybiu_2015_results,
    SAVIVALDYBIU_2011_ELECTION_ID: build_savivaldybiu_2011_results,
    SAVIVALDYBIU_2007_ELECTION_ID: build_savivaldybiu_2007_results,
    SEIMO_1996_ELECTION_ID: build_seimo_1996_results,
    SEIMO_PAKARTOTINIAI_1997_KOVO_ELECTION_ID: build_seimo_pakartotiniai_1997_kovo_results,
    SEIMO_AUKSTAITIJOS_1997_GRUODZIO_ELECTION_ID: build_seimo_aukstaitijos_1997_gruodzio_results,
    SEIMO_PAKARTOTINIAI_1998_KOVO_ELECTION_ID: build_seimo_pakartotiniai_1998_kovo_results,
    SEIMO_NEVEZIO_1998_LAPKRICIO_ELECTION_ID: build_seimo_nevezio_1998_lapkricio_results,
    SEIMO_PAKARTOTINIAI_1999_KOVO_ELECTION_ID: build_seimo_pakartotiniai_1999_kovo_results,
    SAVIVALDYBIU_1997_ELECTION_ID: build_savivaldybiu_1997_results,
    SVENCIONIU_TARYBOS_1997_ELECTION_ID: build_svencioniu_tarybos_1997_results,
}


def _build_results_for_election(election_id: str) -> tuple[Path, dict[str, Any]]:
    builder = _RESULTS_BUILDERS.get(election_id)
    if builder is None:
        raise ValueError(f"No results builder for election id: {election_id}")
    return builder()


def listing_fixture_refusal(election_id: str, allow_fixture_overwrite: bool) -> str | None:
    """Why fetch-sample must not run, or None when it may.

    The listing fetchers write into ``samples/html/<election-id>/`` — the
    tracked fixture tree the suite pins — and used to do so silently
    (issue #95). An election that already has that directory is either fully
    fixtured or a fresh clone still missing its untracked listing pages;
    both are deliberate re-captures, so both take an explicit flag.
    """
    fixture_root = Path(f"samples/html/{election_id}")
    if allow_fixture_overwrite or not fixture_root.exists():
        return None
    return (
        f"{fixture_root}/ already exists — fetch-sample writes the tracked "
        "listing fixtures and would overwrite them. If the sitemap is what "
        f"you need, `python -m scraper sitemap {election_id}` rebuilds it "
        "offline from the fixtures already on disk; pass "
        "--allow-fixture-overwrite to re-capture the listing pages "
        "deliberately (fetchers resume past files already saved)."
    )


def _fetch_listing_sample_for_election(election_id: str) -> Path:
    if election_id == SEIMO_2016_ELECTION_ID:
        return fetch_2016_listing_sample()
    if election_id == SEIMO_2020_ELECTION_ID:
        return fetch_2020_listing_sample()
    if election_id == SEIMO_2024_ELECTION_ID:
        return fetch_2024_listing_sample()
    if election_id == EP_2019_ELECTION_ID:
        return fetch_ep_2019_listing_sample()
    if election_id == EP_2024_ELECTION_ID:
        return fetch_ep_2024_listing_sample()
    if election_id == PREZIDENTO_2019_ELECTION_ID:
        return fetch_prezidento_2019_listing_sample()
    if election_id == PREZIDENTO_2024_ELECTION_ID:
        return fetch_prezidento_2024_listing_sample()
    if election_id == KUPISKIO_MERO_2023_ELECTION_ID:
        return fetch_kupiskio_mero_2023_listing_sample()
    if election_id == VISAGINO_MERO_2023_ELECTION_ID:
        return fetch_visagino_mero_2023_listing_sample()
    if election_id == SEIMO_RASEINIU_KEDAINIU_2023_ELECTION_ID:
        return fetch_seimo_raseiniu_kedainiu_2023_listing_sample()
    if election_id == MERU_2025_ELECTION_ID:
        return fetch_meru_2025_listing_sample()
    if election_id == MERU_2017_ELECTION_ID:
        return fetch_meru_2017_listing_sample()
    if election_id == MARIJAMPOLES_MERO_2017_ELECTION_ID:
        return fetch_marijampoles_mero_2017_listing_sample()
    if election_id == MERU_2021_ELECTION_ID:
        return fetch_meru_2021_listing_sample()
    if election_id == RADVILISKIO_MERO_2021_ELECTION_ID:
        return fetch_radviliskio_mero_2021_listing_sample()
    if election_id == SEIMO_ANYKSCIU_PANEVEZIO_2017_ELECTION_ID:
        return fetch_seimo_anyksciu_panevezio_2017_listing_sample()
    if election_id == SEIMO_ZANAVYKU_2018_ELECTION_ID:
        return fetch_seimo_zanavyku_2018_listing_sample()
    if election_id == SEIMO_2019_ELECTION_ID:
        return fetch_seimo_2019_listing_sample()
    if election_id == SAVIVALDYBIU_2023_ELECTION_ID:
        return fetch_savivaldybiu_2023_listing_sample()
    if election_id == SAVIVALDYBIU_2019_ELECTION_ID:
        return fetch_savivaldybiu_2019_listing_sample()
    if election_id == SEIMO_ZIRMUNU_2015_ELECTION_ID:
        return fetch_seimo_zirmunu_2015_listing_sample()
    if election_id == SEIMO_VARENOS_EISISKIU_2015_ELECTION_ID:
        return fetch_seimo_varenos_eisiskiu_2015_listing_sample()
    if election_id == TELSIU_MERO_2015_ELECTION_ID:
        return fetch_telsiu_mero_2015_listing_sample()
    if election_id == PAKARTOTINIAI_SIRVINTU_TRAKU_2015_ELECTION_ID:
        return fetch_pakartotiniai_sirvintu_traku_2015_listing_sample()
    if election_id == PAKARTOTINIAI_SILUTES_2015_ELECTION_ID:
        return fetch_pakartotiniai_silutes_2015_listing_sample()
    if election_id == SAVIVALDYBIU_2015_ELECTION_ID:
        return fetch_savivaldybiu_2015_listing_sample()
    if election_id == SAVIVALDYBIU_2011_ELECTION_ID:
        return fetch_savivaldybiu_2011_listing_sample()
    if election_id == SAVIVALDYBIU_2007_ELECTION_ID:
        return fetch_savivaldybiu_2007_listing_sample()
    if election_id == SEIMO_1996_ELECTION_ID:
        return fetch_seimo_1996_listing_sample()
    if election_id == SEIMO_PAKARTOTINIAI_1997_KOVO_ELECTION_ID:
        return fetch_seimo_pakartotiniai_1997_kovo_listing_sample()
    if election_id == SEIMO_AUKSTAITIJOS_1997_GRUODZIO_ELECTION_ID:
        return fetch_seimo_aukstaitijos_1997_gruodzio_listing_sample()
    if election_id == SEIMO_NEVEZIO_1998_LAPKRICIO_ELECTION_ID:
        return fetch_seimo_nevezio_1998_lapkricio_listing_sample()
    if election_id == SEIMO_PAKARTOTINIAI_1998_KOVO_ELECTION_ID:
        return fetch_seimo_pakartotiniai_1998_kovo_listing_sample()
    if election_id == SEIMO_PAKARTOTINIAI_1999_KOVO_ELECTION_ID:
        return fetch_seimo_pakartotiniai_1999_kovo_listing_sample()
    if election_id == SAVIVALDYBIU_1997_ELECTION_ID:
        return fetch_savivaldybiu_1997_listing_sample()
    if election_id == SVENCIONIU_TARYBOS_1997_ELECTION_ID:
        return fetch_svencioniu_tarybos_1997_listing_sample()
    if election_id == PREZIDENTO_2009_ELECTION_ID:
        return fetch_prezidento_2009_listing_sample()
    if election_id == PREZIDENTO_2014_ELECTION_ID:
        return fetch_prezidento_2014_listing_sample()
    if election_id == SEIMO_BIRZU_ZARASU_UKMERGES_2013_ELECTION_ID:
        return fetch_seimo_birzu_zarasu_ukmerges_2013_listing_sample()
    if election_id == EP_2009_ELECTION_ID:
        return fetch_ep_2009_listing_sample()
    if election_id == EP_2014_ELECTION_ID:
        return fetch_ep_2014_listing_sample()
    if election_id == SEIMO_SILALES_SILUTES_VILNIAUS_SALCININKU_2009_ELECTION_ID:
        return fetch_seimo_silales_silutes_vilniaus_salcininku_2009_listing_sample()
    if election_id == SEIMO_MARIJAMPOLES_2011_ELECTION_ID:
        return fetch_seimo_marijampoles_2011_listing_sample()
    if election_id == SEIMO_DZUKIJOS_2007_ELECTION_ID:
        return fetch_seimo_dzukijos_2007_listing_sample()
    if election_id == EP_2004_ELECTION_ID:
        return fetch_ep_2004_listing_sample()
    if election_id == PREZIDENTO_2004_ELECTION_ID:
        return fetch_prezidento_2004_listing_sample()
    if election_id == PREZIDENTO_2002_ELECTION_ID:
        return fetch_prezidento_2002_listing_sample()
    if election_id == SEIMO_2004_ELECTION_ID:
        return fetch_seimo_2004_listing_sample()
    if election_id == SEIMO_NAUJI_2003_ELECTION_ID:
        return fetch_seimo_nauji_2003_listing_sample()
    if election_id == SEIMO_KEDAINIU_2005_ELECTION_ID:
        return fetch_seimo_kedainiu_2005_listing_sample()
    if election_id == SEIMO_2000_ELECTION_ID:
        return fetch_seimo_2000_listing_sample()
    if election_id == SAVIVALDYBIU_2000_ELECTION_ID:
        return fetch_savivaldybiu_2000_listing_sample()
    if election_id == SAVIVALDYBIU_2002_ELECTION_ID:
        return fetch_savivaldybiu_2002_listing_sample()
    if election_id == SEIMO_2008_ELECTION_ID:
        return fetch_seimo_2008_listing_sample()
    if election_id == SEIMO_2012_ELECTION_ID:
        return fetch_seimo_2012_listing_sample()
    raise ValueError(f"Unsupported election id: {election_id}")


def _build_sitemap_from_sample_for_election(election_id: str, sample_path: Path | None) -> tuple[Path, dict[str, int]]:
    if election_id == SEIMO_2016_ELECTION_ID:
        return build_2016_sitemap_from_sample(sample_path=sample_path)
    if election_id == SEIMO_2020_ELECTION_ID:
        return build_2020_sitemap_from_sample(sample_path=sample_path)
    if election_id == SEIMO_2024_ELECTION_ID:
        return build_2024_sitemap_from_sample(sample_path=sample_path)
    if election_id == EP_2019_ELECTION_ID:
        return build_ep_2019_sitemap_from_sample(sample_path=sample_path)
    if election_id == EP_2024_ELECTION_ID:
        return build_ep_2024_sitemap_from_sample(sample_path=sample_path)
    if election_id == PREZIDENTO_2019_ELECTION_ID:
        return build_prezidento_2019_sitemap_from_sample(sample_path=sample_path)
    if election_id == PREZIDENTO_2024_ELECTION_ID:
        return build_prezidento_2024_sitemap_from_sample(sample_path=sample_path)
    if election_id == KUPISKIO_MERO_2023_ELECTION_ID:
        return build_kupiskio_mero_2023_sitemap_from_sample(sample_path=sample_path)
    if election_id == VISAGINO_MERO_2023_ELECTION_ID:
        return build_visagino_mero_2023_sitemap_from_sample(sample_path=sample_path)
    if election_id == SEIMO_RASEINIU_KEDAINIU_2023_ELECTION_ID:
        return build_seimo_raseiniu_kedainiu_2023_sitemap_from_sample(sample_path=sample_path)
    if election_id == MERU_2025_ELECTION_ID:
        return build_meru_2025_sitemap_from_sample(sample_path=sample_path)
    if election_id == MERU_2017_ELECTION_ID:
        return build_meru_2017_sitemap_from_sample(sample_path=sample_path)
    if election_id == MARIJAMPOLES_MERO_2017_ELECTION_ID:
        return build_marijampoles_mero_2017_sitemap_from_sample(sample_path=sample_path)
    if election_id == MERU_2021_ELECTION_ID:
        return build_meru_2021_sitemap_from_sample(sample_path=sample_path)
    if election_id == RADVILISKIO_MERO_2021_ELECTION_ID:
        return build_radviliskio_mero_2021_sitemap_from_sample(sample_path=sample_path)
    if election_id == SEIMO_ANYKSCIU_PANEVEZIO_2017_ELECTION_ID:
        return build_seimo_anyksciu_panevezio_2017_sitemap_from_sample(sample_path=sample_path)
    if election_id == SEIMO_ZANAVYKU_2018_ELECTION_ID:
        return build_seimo_zanavyku_2018_sitemap_from_sample(sample_path=sample_path)
    if election_id == SEIMO_2019_ELECTION_ID:
        return build_seimo_2019_sitemap_from_sample(sample_path=sample_path)
    if election_id == SAVIVALDYBIU_2023_ELECTION_ID:
        return build_savivaldybiu_2023_sitemap_from_sample(sample_path=sample_path)
    if election_id == SAVIVALDYBIU_2019_ELECTION_ID:
        return build_savivaldybiu_2019_sitemap_from_sample(sample_path=sample_path)
    if election_id == SEIMO_ZIRMUNU_2015_ELECTION_ID:
        return build_seimo_zirmunu_2015_sitemap_from_sample(sample_path=sample_path)
    if election_id == SEIMO_VARENOS_EISISKIU_2015_ELECTION_ID:
        return build_seimo_varenos_eisiskiu_2015_sitemap_from_sample(sample_path=sample_path)
    if election_id == TELSIU_MERO_2015_ELECTION_ID:
        return build_telsiu_mero_2015_sitemap_from_sample(sample_path=sample_path)
    if election_id == PAKARTOTINIAI_SIRVINTU_TRAKU_2015_ELECTION_ID:
        return build_pakartotiniai_sirvintu_traku_2015_sitemap_from_sample(sample_path=sample_path)
    if election_id == PAKARTOTINIAI_SILUTES_2015_ELECTION_ID:
        return build_pakartotiniai_silutes_2015_sitemap_from_sample(sample_path=sample_path)
    if election_id == SAVIVALDYBIU_2015_ELECTION_ID:
        return build_savivaldybiu_2015_sitemap_from_sample(sample_path=sample_path)
    if election_id == SAVIVALDYBIU_2011_ELECTION_ID:
        return build_savivaldybiu_2011_sitemap_from_sample(sample_path=sample_path)
    if election_id == SAVIVALDYBIU_2007_ELECTION_ID:
        return build_savivaldybiu_2007_sitemap_from_sample(sample_path=sample_path)
    if election_id == SEIMO_1996_ELECTION_ID:
        return build_seimo_1996_sitemap_from_sample(sample_path=sample_path)
    if election_id == SEIMO_PAKARTOTINIAI_1997_KOVO_ELECTION_ID:
        return build_seimo_pakartotiniai_1997_kovo_sitemap_from_sample(sample_path=sample_path)
    if election_id == SEIMO_AUKSTAITIJOS_1997_GRUODZIO_ELECTION_ID:
        return build_seimo_aukstaitijos_1997_gruodzio_sitemap_from_sample(sample_path=sample_path)
    if election_id == SEIMO_NEVEZIO_1998_LAPKRICIO_ELECTION_ID:
        return build_seimo_nevezio_1998_lapkricio_sitemap_from_sample(sample_path=sample_path)
    if election_id == SEIMO_PAKARTOTINIAI_1998_KOVO_ELECTION_ID:
        return build_seimo_pakartotiniai_1998_kovo_sitemap_from_sample(sample_path=sample_path)
    if election_id == SEIMO_PAKARTOTINIAI_1999_KOVO_ELECTION_ID:
        return build_seimo_pakartotiniai_1999_kovo_sitemap_from_sample(sample_path=sample_path)
    if election_id == SAVIVALDYBIU_1997_ELECTION_ID:
        return build_savivaldybiu_1997_sitemap_from_sample(sample_path=sample_path)
    if election_id == SVENCIONIU_TARYBOS_1997_ELECTION_ID:
        return build_svencioniu_tarybos_1997_sitemap_from_sample(sample_path=sample_path)
    if election_id == PREZIDENTO_2009_ELECTION_ID:
        return build_prezidento_2009_sitemap_from_sample(sample_path=sample_path)
    if election_id == PREZIDENTO_2014_ELECTION_ID:
        return build_prezidento_2014_sitemap_from_sample(sample_path=sample_path)
    if election_id == SEIMO_BIRZU_ZARASU_UKMERGES_2013_ELECTION_ID:
        return build_seimo_birzu_zarasu_ukmerges_2013_sitemap_from_sample(sample_path=sample_path)
    if election_id == EP_2009_ELECTION_ID:
        return build_ep_2009_sitemap_from_sample(sample_path=sample_path)
    if election_id == EP_2014_ELECTION_ID:
        return build_ep_2014_sitemap_from_sample(sample_path=sample_path)
    if election_id == SEIMO_SILALES_SILUTES_VILNIAUS_SALCININKU_2009_ELECTION_ID:
        return build_seimo_silales_silutes_vilniaus_salcininku_2009_sitemap_from_sample(sample_path=sample_path)
    if election_id == SEIMO_MARIJAMPOLES_2011_ELECTION_ID:
        return build_seimo_marijampoles_2011_sitemap_from_sample(sample_path=sample_path)
    if election_id == SEIMO_DZUKIJOS_2007_ELECTION_ID:
        return build_seimo_dzukijos_2007_sitemap_from_sample(sample_path=sample_path)
    if election_id == EP_2004_ELECTION_ID:
        return build_ep_2004_sitemap_from_sample(sample_path=sample_path)
    if election_id == PREZIDENTO_2004_ELECTION_ID:
        return build_prezidento_2004_sitemap_from_sample(sample_path=sample_path)
    if election_id == PREZIDENTO_2002_ELECTION_ID:
        return build_prezidento_2002_sitemap_from_sample(sample_path=sample_path)
    if election_id == SEIMO_2004_ELECTION_ID:
        return build_seimo_2004_sitemap_from_sample(sample_path=sample_path)
    if election_id == SEIMO_NAUJI_2003_ELECTION_ID:
        return build_seimo_nauji_2003_sitemap_from_sample(sample_path=sample_path)
    if election_id == SEIMO_KEDAINIU_2005_ELECTION_ID:
        return build_seimo_kedainiu_2005_sitemap_from_sample(sample_path=sample_path)
    if election_id == SEIMO_2000_ELECTION_ID:
        return build_seimo_2000_sitemap_from_sample(sample_path=sample_path)
    if election_id == SAVIVALDYBIU_2000_ELECTION_ID:
        return build_savivaldybiu_2000_sitemap_from_sample(sample_path=sample_path)
    if election_id == SAVIVALDYBIU_2002_ELECTION_ID:
        return build_savivaldybiu_2002_sitemap_from_sample(sample_path=sample_path)
    if election_id == SEIMO_2008_ELECTION_ID:
        return build_seimo_2008_sitemap_from_sample(sample_path=sample_path)
    if election_id == SEIMO_2012_ELECTION_ID:
        return build_seimo_2012_sitemap_from_sample(sample_path=sample_path)
    raise ValueError(f"Unsupported election id: {election_id}")


def _fetch_first_candidate_with_tabs_for_election(
    election_id: str,
    sitemap_path: Path,
    samples_root: Path,
    allow_new_samples: bool,
) -> dict[str, Any]:
    if election_id == SEIMO_2016_ELECTION_ID:
        return fetch_2016_first_candidate_with_tabs(
            sitemap_path=sitemap_path,
            samples_root=samples_root,
            allow_new_candidate_dir=allow_new_samples,
        )
    if election_id == SEIMO_2020_ELECTION_ID:
        return fetch_2020_first_candidate_with_tabs(
            sitemap_path=sitemap_path,
            samples_root=samples_root,
            allow_new_candidate_dir=allow_new_samples,
        )
    if election_id == SEIMO_2024_ELECTION_ID:
        return fetch_2024_first_candidate_with_tabs(
            sitemap_path=sitemap_path,
            samples_root=samples_root,
            allow_new_candidate_dir=allow_new_samples,
        )
    if election_id == EP_2019_ELECTION_ID:
        return fetch_ep_2019_first_candidate_with_tabs(
            sitemap_path=sitemap_path,
            samples_root=samples_root,
            allow_new_candidate_dir=allow_new_samples,
        )
    if election_id == EP_2024_ELECTION_ID:
        return fetch_ep_2024_first_candidate_with_tabs(
            sitemap_path=sitemap_path,
            samples_root=samples_root,
            allow_new_candidate_dir=allow_new_samples,
        )
    if election_id == PREZIDENTO_2019_ELECTION_ID:
        return fetch_prezidento_2019_first_candidate_with_tabs(
            sitemap_path=sitemap_path,
            samples_root=samples_root,
            allow_new_candidate_dir=allow_new_samples,
        )
    if election_id == PREZIDENTO_2024_ELECTION_ID:
        return fetch_prezidento_2024_first_candidate_with_tabs(
            sitemap_path=sitemap_path,
            samples_root=samples_root,
            allow_new_candidate_dir=allow_new_samples,
        )
    if election_id == KUPISKIO_MERO_2023_ELECTION_ID:
        return fetch_kupiskio_mero_2023_first_candidate_with_tabs(
            sitemap_path=sitemap_path,
            samples_root=samples_root,
            allow_new_candidate_dir=allow_new_samples,
        )
    if election_id == VISAGINO_MERO_2023_ELECTION_ID:
        return fetch_visagino_mero_2023_first_candidate_with_tabs(
            sitemap_path=sitemap_path,
            samples_root=samples_root,
            allow_new_candidate_dir=allow_new_samples,
        )
    if election_id == SEIMO_RASEINIU_KEDAINIU_2023_ELECTION_ID:
        return fetch_seimo_raseiniu_kedainiu_2023_first_candidate_with_tabs(
            sitemap_path=sitemap_path,
            samples_root=samples_root,
            allow_new_candidate_dir=allow_new_samples,
        )
    if election_id == MERU_2025_ELECTION_ID:
        return fetch_meru_2025_first_candidate_with_tabs(
            sitemap_path=sitemap_path,
            samples_root=samples_root,
            allow_new_candidate_dir=allow_new_samples,
        )
    if election_id == MERU_2017_ELECTION_ID:
        return fetch_meru_2017_first_candidate_with_tabs(
            sitemap_path=sitemap_path,
            samples_root=samples_root,
            allow_new_candidate_dir=allow_new_samples,
        )
    if election_id == MARIJAMPOLES_MERO_2017_ELECTION_ID:
        return fetch_marijampoles_mero_2017_first_candidate_with_tabs(
            sitemap_path=sitemap_path,
            samples_root=samples_root,
            allow_new_candidate_dir=allow_new_samples,
        )
    if election_id == MERU_2021_ELECTION_ID:
        return fetch_meru_2021_first_candidate_with_tabs(
            sitemap_path=sitemap_path,
            samples_root=samples_root,
            allow_new_candidate_dir=allow_new_samples,
        )
    if election_id == RADVILISKIO_MERO_2021_ELECTION_ID:
        return fetch_radviliskio_mero_2021_first_candidate_with_tabs(
            sitemap_path=sitemap_path,
            samples_root=samples_root,
            allow_new_candidate_dir=allow_new_samples,
        )
    if election_id == SEIMO_ANYKSCIU_PANEVEZIO_2017_ELECTION_ID:
        return fetch_seimo_anyksciu_panevezio_2017_first_candidate_with_tabs(
            sitemap_path=sitemap_path,
            samples_root=samples_root,
            allow_new_candidate_dir=allow_new_samples,
        )
    if election_id == SEIMO_ZANAVYKU_2018_ELECTION_ID:
        return fetch_seimo_zanavyku_2018_first_candidate_with_tabs(
            sitemap_path=sitemap_path,
            samples_root=samples_root,
            allow_new_candidate_dir=allow_new_samples,
        )
    if election_id == SEIMO_2019_ELECTION_ID:
        return fetch_seimo_2019_first_candidate_with_tabs(
            sitemap_path=sitemap_path,
            samples_root=samples_root,
            allow_new_candidate_dir=allow_new_samples,
        )
    if election_id == SAVIVALDYBIU_2023_ELECTION_ID:
        return fetch_savivaldybiu_2023_first_candidate_with_tabs(
            sitemap_path=sitemap_path,
            samples_root=samples_root,
            allow_new_candidate_dir=allow_new_samples,
        )
    if election_id == SAVIVALDYBIU_2019_ELECTION_ID:
        return fetch_savivaldybiu_2019_first_candidate_with_tabs(
            sitemap_path=sitemap_path,
            samples_root=samples_root,
            allow_new_candidate_dir=allow_new_samples,
        )
    if election_id == SEIMO_ZIRMUNU_2015_ELECTION_ID:
        return fetch_seimo_zirmunu_2015_first_candidate_with_tabs(
            sitemap_path=sitemap_path,
            samples_root=samples_root,
            allow_new_candidate_dir=allow_new_samples,
        )
    if election_id == SEIMO_VARENOS_EISISKIU_2015_ELECTION_ID:
        return fetch_seimo_varenos_eisiskiu_2015_first_candidate_with_tabs(
            sitemap_path=sitemap_path,
            samples_root=samples_root,
            allow_new_candidate_dir=allow_new_samples,
        )
    if election_id == TELSIU_MERO_2015_ELECTION_ID:
        return fetch_telsiu_mero_2015_first_candidate_with_tabs(
            sitemap_path=sitemap_path,
            samples_root=samples_root,
            allow_new_candidate_dir=allow_new_samples,
        )
    if election_id == PAKARTOTINIAI_SIRVINTU_TRAKU_2015_ELECTION_ID:
        return fetch_pakartotiniai_sirvintu_traku_2015_first_candidate_with_tabs(
            sitemap_path=sitemap_path,
            samples_root=samples_root,
            allow_new_candidate_dir=allow_new_samples,
        )
    if election_id == PAKARTOTINIAI_SILUTES_2015_ELECTION_ID:
        return fetch_pakartotiniai_silutes_2015_first_candidate_with_tabs(
            sitemap_path=sitemap_path,
            samples_root=samples_root,
            allow_new_candidate_dir=allow_new_samples,
        )
    if election_id == SAVIVALDYBIU_2015_ELECTION_ID:
        return fetch_savivaldybiu_2015_first_candidate_with_tabs(
            sitemap_path=sitemap_path,
            samples_root=samples_root,
            allow_new_candidate_dir=allow_new_samples,
        )
    if election_id == SAVIVALDYBIU_2011_ELECTION_ID:
        return fetch_savivaldybiu_2011_first_candidate_with_tabs(
            sitemap_path=sitemap_path,
            samples_root=samples_root,
            allow_new_candidate_dir=allow_new_samples,
        )
    if election_id == SAVIVALDYBIU_2007_ELECTION_ID:
        return fetch_savivaldybiu_2007_first_candidate_with_tabs(
            sitemap_path=sitemap_path,
            samples_root=samples_root,
            allow_new_candidate_dir=allow_new_samples,
        )
    if election_id == SEIMO_1996_ELECTION_ID:
        return fetch_seimo_1996_first_candidate_with_tabs(
            sitemap_path=sitemap_path,
            samples_root=samples_root,
            allow_new_candidate_dir=allow_new_samples,
        )
    if election_id == SEIMO_PAKARTOTINIAI_1997_KOVO_ELECTION_ID:
        return fetch_seimo_pakartotiniai_1997_kovo_first_candidate_with_tabs(
            sitemap_path=sitemap_path,
            samples_root=samples_root,
            allow_new_candidate_dir=allow_new_samples,
        )
    if election_id == SEIMO_AUKSTAITIJOS_1997_GRUODZIO_ELECTION_ID:
        return fetch_seimo_aukstaitijos_1997_gruodzio_first_candidate_with_tabs(
            sitemap_path=sitemap_path,
            samples_root=samples_root,
            allow_new_candidate_dir=allow_new_samples,
        )
    if election_id == SEIMO_NEVEZIO_1998_LAPKRICIO_ELECTION_ID:
        return fetch_seimo_nevezio_1998_lapkricio_first_candidate_with_tabs(
            sitemap_path=sitemap_path,
            samples_root=samples_root,
            allow_new_candidate_dir=allow_new_samples,
        )
    if election_id == SEIMO_PAKARTOTINIAI_1998_KOVO_ELECTION_ID:
        return fetch_seimo_pakartotiniai_1998_kovo_first_candidate_with_tabs(
            sitemap_path=sitemap_path,
            samples_root=samples_root,
            allow_new_candidate_dir=allow_new_samples,
        )
    if election_id == SEIMO_PAKARTOTINIAI_1999_KOVO_ELECTION_ID:
        return fetch_seimo_pakartotiniai_1999_kovo_first_candidate_with_tabs(
            sitemap_path=sitemap_path,
            samples_root=samples_root,
            allow_new_candidate_dir=allow_new_samples,
        )
    if election_id == SAVIVALDYBIU_1997_ELECTION_ID:
        return fetch_savivaldybiu_1997_first_candidate_with_tabs(
            sitemap_path=sitemap_path,
            samples_root=samples_root,
            allow_new_candidate_dir=allow_new_samples,
        )
    if election_id == SVENCIONIU_TARYBOS_1997_ELECTION_ID:
        return fetch_svencioniu_tarybos_1997_first_candidate_with_tabs(
            sitemap_path=sitemap_path,
            samples_root=samples_root,
            allow_new_candidate_dir=allow_new_samples,
        )
    if election_id == PREZIDENTO_2009_ELECTION_ID:
        return fetch_prezidento_2009_first_candidate_with_tabs(
            sitemap_path=sitemap_path,
            samples_root=samples_root,
            allow_new_candidate_dir=allow_new_samples,
        )
    if election_id == PREZIDENTO_2014_ELECTION_ID:
        return fetch_prezidento_2014_first_candidate_with_tabs(
            sitemap_path=sitemap_path,
            samples_root=samples_root,
            allow_new_candidate_dir=allow_new_samples,
        )
    if election_id == SEIMO_BIRZU_ZARASU_UKMERGES_2013_ELECTION_ID:
        return fetch_seimo_birzu_zarasu_ukmerges_2013_first_candidate_with_tabs(
            sitemap_path=sitemap_path,
            samples_root=samples_root,
            allow_new_candidate_dir=allow_new_samples,
        )
    if election_id == EP_2009_ELECTION_ID:
        return fetch_ep_2009_first_candidate_with_tabs(
            sitemap_path=sitemap_path,
            samples_root=samples_root,
            allow_new_candidate_dir=allow_new_samples,
        )
    if election_id == EP_2014_ELECTION_ID:
        return fetch_ep_2014_first_candidate_with_tabs(
            sitemap_path=sitemap_path,
            samples_root=samples_root,
            allow_new_candidate_dir=allow_new_samples,
        )
    if election_id == SEIMO_SILALES_SILUTES_VILNIAUS_SALCININKU_2009_ELECTION_ID:
        return fetch_seimo_silales_silutes_vilniaus_salcininku_2009_first_candidate_with_tabs(
            sitemap_path=sitemap_path,
            samples_root=samples_root,
            allow_new_candidate_dir=allow_new_samples,
        )
    if election_id == SEIMO_MARIJAMPOLES_2011_ELECTION_ID:
        return fetch_seimo_marijampoles_2011_first_candidate_with_tabs(
            sitemap_path=sitemap_path,
            samples_root=samples_root,
            allow_new_candidate_dir=allow_new_samples,
        )
    if election_id == SEIMO_DZUKIJOS_2007_ELECTION_ID:
        return fetch_seimo_dzukijos_2007_first_candidate_with_tabs(
            sitemap_path=sitemap_path,
            samples_root=samples_root,
            allow_new_candidate_dir=allow_new_samples,
        )
    if election_id == EP_2004_ELECTION_ID:
        return fetch_ep_2004_first_candidate_with_tabs(
            sitemap_path=sitemap_path,
            samples_root=samples_root,
            allow_new_candidate_dir=allow_new_samples,
        )
    if election_id == PREZIDENTO_2004_ELECTION_ID:
        return fetch_prezidento_2004_first_candidate_with_tabs(
            sitemap_path=sitemap_path,
            samples_root=samples_root,
            allow_new_candidate_dir=allow_new_samples,
        )
    if election_id == PREZIDENTO_2002_ELECTION_ID:
        return fetch_prezidento_2002_first_candidate_with_tabs(
            sitemap_path=sitemap_path,
            samples_root=samples_root,
            allow_new_candidate_dir=allow_new_samples,
        )
    if election_id == SEIMO_2004_ELECTION_ID:
        return fetch_seimo_2004_first_candidate_with_tabs(
            sitemap_path=sitemap_path,
            samples_root=samples_root,
            allow_new_candidate_dir=allow_new_samples,
        )
    if election_id == SEIMO_NAUJI_2003_ELECTION_ID:
        return fetch_seimo_nauji_2003_first_candidate_with_tabs(
            sitemap_path=sitemap_path,
            samples_root=samples_root,
            allow_new_candidate_dir=allow_new_samples,
        )
    if election_id == SEIMO_KEDAINIU_2005_ELECTION_ID:
        return fetch_seimo_kedainiu_2005_first_candidate_with_tabs(
            sitemap_path=sitemap_path,
            samples_root=samples_root,
            allow_new_candidate_dir=allow_new_samples,
        )
    if election_id == SEIMO_2000_ELECTION_ID:
        return fetch_seimo_2000_first_candidate_with_tabs(
            sitemap_path=sitemap_path,
            samples_root=samples_root,
            allow_new_candidate_dir=allow_new_samples,
        )
    if election_id == SAVIVALDYBIU_2000_ELECTION_ID:
        return fetch_savivaldybiu_2000_first_candidate_with_tabs(
            sitemap_path=sitemap_path,
            samples_root=samples_root,
            allow_new_candidate_dir=allow_new_samples,
        )
    if election_id == SAVIVALDYBIU_2002_ELECTION_ID:
        return fetch_savivaldybiu_2002_first_candidate_with_tabs(
            sitemap_path=sitemap_path,
            samples_root=samples_root,
            allow_new_candidate_dir=allow_new_samples,
        )
    if election_id == SEIMO_2008_ELECTION_ID:
        return fetch_seimo_2008_first_candidate_with_tabs(
            sitemap_path=sitemap_path,
            samples_root=samples_root,
            allow_new_candidate_dir=allow_new_samples,
        )
    if election_id == SEIMO_2012_ELECTION_ID:
        return fetch_seimo_2012_first_candidate_with_tabs(
            sitemap_path=sitemap_path,
            samples_root=samples_root,
            allow_new_candidate_dir=allow_new_samples,
        )
    raise ValueError(f"Unsupported election id: {election_id}")


def _fetch_candidates_with_tabs_for_election(
    election_id: str,
    candidate_ids: list[str],
    sitemap_path: Path,
    samples_root: Path,
    allow_new_samples: bool,
) -> dict[str, Any]:
    if election_id == SEIMO_2016_ELECTION_ID:
        return fetch_2016_candidates_with_tabs(
            candidate_ids=candidate_ids,
            sitemap_path=sitemap_path,
            samples_root=samples_root,
            allow_new_candidate_dir=allow_new_samples,
        )
    if election_id == SEIMO_2020_ELECTION_ID:
        return fetch_2020_candidates_with_tabs(
            candidate_ids=candidate_ids,
            sitemap_path=sitemap_path,
            samples_root=samples_root,
            allow_new_candidate_dir=allow_new_samples,
        )
    if election_id == SEIMO_2024_ELECTION_ID:
        return fetch_2024_candidates_with_tabs(
            candidate_ids=candidate_ids,
            sitemap_path=sitemap_path,
            samples_root=samples_root,
            allow_new_candidate_dir=allow_new_samples,
        )
    if election_id == EP_2019_ELECTION_ID:
        return fetch_ep_2019_candidates_with_tabs(
            candidate_ids=candidate_ids,
            sitemap_path=sitemap_path,
            samples_root=samples_root,
            allow_new_candidate_dir=allow_new_samples,
        )
    if election_id == EP_2024_ELECTION_ID:
        return fetch_ep_2024_candidates_with_tabs(
            candidate_ids=candidate_ids,
            sitemap_path=sitemap_path,
            samples_root=samples_root,
            allow_new_candidate_dir=allow_new_samples,
        )
    if election_id == PREZIDENTO_2019_ELECTION_ID:
        return fetch_prezidento_2019_candidates_with_tabs(
            candidate_ids=candidate_ids,
            sitemap_path=sitemap_path,
            samples_root=samples_root,
            allow_new_candidate_dir=allow_new_samples,
        )
    if election_id == PREZIDENTO_2024_ELECTION_ID:
        return fetch_prezidento_2024_candidates_with_tabs(
            candidate_ids=candidate_ids,
            sitemap_path=sitemap_path,
            samples_root=samples_root,
            allow_new_candidate_dir=allow_new_samples,
        )
    if election_id == KUPISKIO_MERO_2023_ELECTION_ID:
        return fetch_kupiskio_mero_2023_candidates_with_tabs(
            candidate_ids=candidate_ids,
            sitemap_path=sitemap_path,
            samples_root=samples_root,
            allow_new_candidate_dir=allow_new_samples,
        )
    if election_id == VISAGINO_MERO_2023_ELECTION_ID:
        return fetch_visagino_mero_2023_candidates_with_tabs(
            candidate_ids=candidate_ids,
            sitemap_path=sitemap_path,
            samples_root=samples_root,
            allow_new_candidate_dir=allow_new_samples,
        )
    if election_id == SEIMO_RASEINIU_KEDAINIU_2023_ELECTION_ID:
        return fetch_seimo_raseiniu_kedainiu_2023_candidates_with_tabs(
            candidate_ids=candidate_ids,
            sitemap_path=sitemap_path,
            samples_root=samples_root,
            allow_new_candidate_dir=allow_new_samples,
        )
    if election_id == MERU_2025_ELECTION_ID:
        return fetch_meru_2025_candidates_with_tabs(
            candidate_ids=candidate_ids,
            sitemap_path=sitemap_path,
            samples_root=samples_root,
            allow_new_candidate_dir=allow_new_samples,
        )
    if election_id == MERU_2017_ELECTION_ID:
        return fetch_meru_2017_candidates_with_tabs(
            candidate_ids=candidate_ids,
            sitemap_path=sitemap_path,
            samples_root=samples_root,
            allow_new_candidate_dir=allow_new_samples,
        )
    if election_id == MARIJAMPOLES_MERO_2017_ELECTION_ID:
        return fetch_marijampoles_mero_2017_candidates_with_tabs(
            candidate_ids=candidate_ids,
            sitemap_path=sitemap_path,
            samples_root=samples_root,
            allow_new_candidate_dir=allow_new_samples,
        )
    if election_id == MERU_2021_ELECTION_ID:
        return fetch_meru_2021_candidates_with_tabs(
            candidate_ids=candidate_ids,
            sitemap_path=sitemap_path,
            samples_root=samples_root,
            allow_new_candidate_dir=allow_new_samples,
        )
    if election_id == RADVILISKIO_MERO_2021_ELECTION_ID:
        return fetch_radviliskio_mero_2021_candidates_with_tabs(
            candidate_ids=candidate_ids,
            sitemap_path=sitemap_path,
            samples_root=samples_root,
            allow_new_candidate_dir=allow_new_samples,
        )
    if election_id == SEIMO_ANYKSCIU_PANEVEZIO_2017_ELECTION_ID:
        return fetch_seimo_anyksciu_panevezio_2017_candidates_with_tabs(
            candidate_ids=candidate_ids,
            sitemap_path=sitemap_path,
            samples_root=samples_root,
            allow_new_candidate_dir=allow_new_samples,
        )
    if election_id == SEIMO_ZANAVYKU_2018_ELECTION_ID:
        return fetch_seimo_zanavyku_2018_candidates_with_tabs(
            candidate_ids=candidate_ids,
            sitemap_path=sitemap_path,
            samples_root=samples_root,
            allow_new_candidate_dir=allow_new_samples,
        )
    if election_id == SEIMO_2019_ELECTION_ID:
        return fetch_seimo_2019_candidates_with_tabs(
            candidate_ids=candidate_ids,
            sitemap_path=sitemap_path,
            samples_root=samples_root,
            allow_new_candidate_dir=allow_new_samples,
        )
    if election_id == SAVIVALDYBIU_2023_ELECTION_ID:
        return fetch_savivaldybiu_2023_candidates_with_tabs(
            candidate_ids=candidate_ids,
            sitemap_path=sitemap_path,
            samples_root=samples_root,
            allow_new_candidate_dir=allow_new_samples,
        )
    if election_id == SAVIVALDYBIU_2019_ELECTION_ID:
        return fetch_savivaldybiu_2019_candidates_with_tabs(
            candidate_ids=candidate_ids,
            sitemap_path=sitemap_path,
            samples_root=samples_root,
            allow_new_candidate_dir=allow_new_samples,
        )
    if election_id == SEIMO_ZIRMUNU_2015_ELECTION_ID:
        return fetch_seimo_zirmunu_2015_candidates_with_tabs(
            candidate_ids=candidate_ids,
            sitemap_path=sitemap_path,
            samples_root=samples_root,
            allow_new_candidate_dir=allow_new_samples,
        )
    if election_id == SEIMO_VARENOS_EISISKIU_2015_ELECTION_ID:
        return fetch_seimo_varenos_eisiskiu_2015_candidates_with_tabs(
            candidate_ids=candidate_ids,
            sitemap_path=sitemap_path,
            samples_root=samples_root,
            allow_new_candidate_dir=allow_new_samples,
        )
    if election_id == TELSIU_MERO_2015_ELECTION_ID:
        return fetch_telsiu_mero_2015_candidates_with_tabs(
            candidate_ids=candidate_ids,
            sitemap_path=sitemap_path,
            samples_root=samples_root,
            allow_new_candidate_dir=allow_new_samples,
        )
    if election_id == PAKARTOTINIAI_SIRVINTU_TRAKU_2015_ELECTION_ID:
        return fetch_pakartotiniai_sirvintu_traku_2015_candidates_with_tabs(
            candidate_ids=candidate_ids,
            sitemap_path=sitemap_path,
            samples_root=samples_root,
            allow_new_candidate_dir=allow_new_samples,
        )
    if election_id == PAKARTOTINIAI_SILUTES_2015_ELECTION_ID:
        return fetch_pakartotiniai_silutes_2015_candidates_with_tabs(
            candidate_ids=candidate_ids,
            sitemap_path=sitemap_path,
            samples_root=samples_root,
            allow_new_candidate_dir=allow_new_samples,
        )
    if election_id == SAVIVALDYBIU_2015_ELECTION_ID:
        return fetch_savivaldybiu_2015_candidates_with_tabs(
            candidate_ids=candidate_ids,
            sitemap_path=sitemap_path,
            samples_root=samples_root,
            allow_new_candidate_dir=allow_new_samples,
        )
    if election_id == SAVIVALDYBIU_2011_ELECTION_ID:
        return fetch_savivaldybiu_2011_candidates_with_tabs(
            candidate_ids=candidate_ids,
            sitemap_path=sitemap_path,
            samples_root=samples_root,
            allow_new_candidate_dir=allow_new_samples,
        )
    if election_id == SAVIVALDYBIU_2007_ELECTION_ID:
        return fetch_savivaldybiu_2007_candidates_with_tabs(
            candidate_ids=candidate_ids,
            sitemap_path=sitemap_path,
            samples_root=samples_root,
            allow_new_candidate_dir=allow_new_samples,
        )
    if election_id == SEIMO_1996_ELECTION_ID:
        return fetch_seimo_1996_candidates_with_tabs(
            candidate_ids=candidate_ids,
            sitemap_path=sitemap_path,
            samples_root=samples_root,
            allow_new_candidate_dir=allow_new_samples,
        )
    if election_id == SEIMO_PAKARTOTINIAI_1997_KOVO_ELECTION_ID:
        return fetch_seimo_pakartotiniai_1997_kovo_candidates_with_tabs(
            candidate_ids=candidate_ids,
            sitemap_path=sitemap_path,
            samples_root=samples_root,
            allow_new_candidate_dir=allow_new_samples,
        )
    if election_id == SEIMO_AUKSTAITIJOS_1997_GRUODZIO_ELECTION_ID:
        return fetch_seimo_aukstaitijos_1997_gruodzio_candidates_with_tabs(
            candidate_ids=candidate_ids,
            sitemap_path=sitemap_path,
            samples_root=samples_root,
            allow_new_candidate_dir=allow_new_samples,
        )
    if election_id == SEIMO_NEVEZIO_1998_LAPKRICIO_ELECTION_ID:
        return fetch_seimo_nevezio_1998_lapkricio_candidates_with_tabs(
            candidate_ids=candidate_ids,
            sitemap_path=sitemap_path,
            samples_root=samples_root,
            allow_new_candidate_dir=allow_new_samples,
        )
    if election_id == SEIMO_PAKARTOTINIAI_1998_KOVO_ELECTION_ID:
        return fetch_seimo_pakartotiniai_1998_kovo_candidates_with_tabs(
            candidate_ids=candidate_ids,
            sitemap_path=sitemap_path,
            samples_root=samples_root,
            allow_new_candidate_dir=allow_new_samples,
        )
    if election_id == SEIMO_PAKARTOTINIAI_1999_KOVO_ELECTION_ID:
        return fetch_seimo_pakartotiniai_1999_kovo_candidates_with_tabs(
            candidate_ids=candidate_ids,
            sitemap_path=sitemap_path,
            samples_root=samples_root,
            allow_new_candidate_dir=allow_new_samples,
        )
    if election_id == SAVIVALDYBIU_1997_ELECTION_ID:
        return fetch_savivaldybiu_1997_candidates_with_tabs(
            candidate_ids=candidate_ids,
            sitemap_path=sitemap_path,
            samples_root=samples_root,
            allow_new_candidate_dir=allow_new_samples,
        )
    if election_id == SVENCIONIU_TARYBOS_1997_ELECTION_ID:
        return fetch_svencioniu_tarybos_1997_candidates_with_tabs(
            candidate_ids=candidate_ids,
            sitemap_path=sitemap_path,
            samples_root=samples_root,
            allow_new_candidate_dir=allow_new_samples,
        )
    if election_id == PREZIDENTO_2009_ELECTION_ID:
        return fetch_prezidento_2009_candidates_with_tabs(
            candidate_ids=candidate_ids,
            sitemap_path=sitemap_path,
            samples_root=samples_root,
            allow_new_candidate_dir=allow_new_samples,
        )
    if election_id == PREZIDENTO_2014_ELECTION_ID:
        return fetch_prezidento_2014_candidates_with_tabs(
            candidate_ids=candidate_ids,
            sitemap_path=sitemap_path,
            samples_root=samples_root,
            allow_new_candidate_dir=allow_new_samples,
        )
    if election_id == SEIMO_BIRZU_ZARASU_UKMERGES_2013_ELECTION_ID:
        return fetch_seimo_birzu_zarasu_ukmerges_2013_candidates_with_tabs(
            candidate_ids=candidate_ids,
            sitemap_path=sitemap_path,
            samples_root=samples_root,
            allow_new_candidate_dir=allow_new_samples,
        )
    if election_id == EP_2009_ELECTION_ID:
        return fetch_ep_2009_candidates_with_tabs(
            candidate_ids=candidate_ids,
            sitemap_path=sitemap_path,
            samples_root=samples_root,
            allow_new_candidate_dir=allow_new_samples,
        )
    if election_id == EP_2014_ELECTION_ID:
        return fetch_ep_2014_candidates_with_tabs(
            candidate_ids=candidate_ids,
            sitemap_path=sitemap_path,
            samples_root=samples_root,
            allow_new_candidate_dir=allow_new_samples,
        )
    if election_id == SEIMO_SILALES_SILUTES_VILNIAUS_SALCININKU_2009_ELECTION_ID:
        return fetch_seimo_silales_silutes_vilniaus_salcininku_2009_candidates_with_tabs(
            candidate_ids=candidate_ids,
            sitemap_path=sitemap_path,
            samples_root=samples_root,
            allow_new_candidate_dir=allow_new_samples,
        )
    if election_id == SEIMO_MARIJAMPOLES_2011_ELECTION_ID:
        return fetch_seimo_marijampoles_2011_candidates_with_tabs(
            candidate_ids=candidate_ids,
            sitemap_path=sitemap_path,
            samples_root=samples_root,
            allow_new_candidate_dir=allow_new_samples,
        )
    if election_id == SEIMO_DZUKIJOS_2007_ELECTION_ID:
        return fetch_seimo_dzukijos_2007_candidates_with_tabs(
            candidate_ids=candidate_ids,
            sitemap_path=sitemap_path,
            samples_root=samples_root,
            allow_new_candidate_dir=allow_new_samples,
        )
    if election_id == EP_2004_ELECTION_ID:
        return fetch_ep_2004_candidates_with_tabs(
            candidate_ids=candidate_ids,
            sitemap_path=sitemap_path,
            samples_root=samples_root,
            allow_new_candidate_dir=allow_new_samples,
        )
    if election_id == PREZIDENTO_2004_ELECTION_ID:
        return fetch_prezidento_2004_candidates_with_tabs(
            candidate_ids=candidate_ids,
            sitemap_path=sitemap_path,
            samples_root=samples_root,
            allow_new_candidate_dir=allow_new_samples,
        )
    if election_id == PREZIDENTO_2002_ELECTION_ID:
        return fetch_prezidento_2002_candidates_with_tabs(
            candidate_ids=candidate_ids,
            sitemap_path=sitemap_path,
            samples_root=samples_root,
            allow_new_candidate_dir=allow_new_samples,
        )
    if election_id == SEIMO_2004_ELECTION_ID:
        return fetch_seimo_2004_candidates_with_tabs(
            candidate_ids=candidate_ids,
            sitemap_path=sitemap_path,
            samples_root=samples_root,
            allow_new_candidate_dir=allow_new_samples,
        )
    if election_id == SEIMO_NAUJI_2003_ELECTION_ID:
        return fetch_seimo_nauji_2003_candidates_with_tabs(
            candidate_ids=candidate_ids,
            sitemap_path=sitemap_path,
            samples_root=samples_root,
            allow_new_candidate_dir=allow_new_samples,
        )
    if election_id == SEIMO_KEDAINIU_2005_ELECTION_ID:
        return fetch_seimo_kedainiu_2005_candidates_with_tabs(
            candidate_ids=candidate_ids,
            sitemap_path=sitemap_path,
            samples_root=samples_root,
            allow_new_candidate_dir=allow_new_samples,
        )
    if election_id == SEIMO_2000_ELECTION_ID:
        return fetch_seimo_2000_candidates_with_tabs(
            candidate_ids=candidate_ids,
            sitemap_path=sitemap_path,
            samples_root=samples_root,
            allow_new_candidate_dir=allow_new_samples,
        )
    if election_id == SAVIVALDYBIU_2000_ELECTION_ID:
        return fetch_savivaldybiu_2000_candidates_with_tabs(
            candidate_ids=candidate_ids,
            sitemap_path=sitemap_path,
            samples_root=samples_root,
            allow_new_candidate_dir=allow_new_samples,
        )
    if election_id == SAVIVALDYBIU_2002_ELECTION_ID:
        return fetch_savivaldybiu_2002_candidates_with_tabs(
            candidate_ids=candidate_ids,
            sitemap_path=sitemap_path,
            samples_root=samples_root,
            allow_new_candidate_dir=allow_new_samples,
        )
    if election_id == SEIMO_2008_ELECTION_ID:
        return fetch_seimo_2008_candidates_with_tabs(
            candidate_ids=candidate_ids,
            sitemap_path=sitemap_path,
            samples_root=samples_root,
            allow_new_candidate_dir=allow_new_samples,
        )
    if election_id == SEIMO_2012_ELECTION_ID:
        return fetch_seimo_2012_candidates_with_tabs(
            candidate_ids=candidate_ids,
            sitemap_path=sitemap_path,
            samples_root=samples_root,
            allow_new_candidate_dir=allow_new_samples,
        )
    raise ValueError(f"Unsupported election id: {election_id}")


def _parse_anketa_samples_for_election(
    election_id: str,
    candidate_ids: list[str] | None,
    samples_root: Path,
    output_root: Path,
) -> list[dict[str, Any]]:
    if election_id == SEIMO_2016_ELECTION_ID:
        return parse_2016_anketa_samples(
            candidate_ids=candidate_ids,
            samples_root=samples_root,
            output_root=output_root,
        )
    if election_id == SEIMO_2020_ELECTION_ID:
        return parse_2020_anketa_samples(
            candidate_ids=candidate_ids,
            samples_root=samples_root,
            output_root=output_root,
        )
    if election_id == SEIMO_2024_ELECTION_ID:
        return parse_2024_anketa_samples(
            candidate_ids=candidate_ids,
            samples_root=samples_root,
            output_root=output_root,
        )
    if election_id == EP_2019_ELECTION_ID:
        return parse_ep_2019_anketa_samples(
            candidate_ids=candidate_ids,
            samples_root=samples_root,
            output_root=output_root,
        )
    if election_id == EP_2024_ELECTION_ID:
        return parse_ep_2024_anketa_samples(
            candidate_ids=candidate_ids,
            samples_root=samples_root,
            output_root=output_root,
        )
    if election_id == PREZIDENTO_2019_ELECTION_ID:
        return parse_prezidento_2019_anketa_samples(
            candidate_ids=candidate_ids,
            samples_root=samples_root,
            output_root=output_root,
        )
    if election_id == PREZIDENTO_2024_ELECTION_ID:
        return parse_prezidento_2024_anketa_samples(
            candidate_ids=candidate_ids,
            samples_root=samples_root,
            output_root=output_root,
        )
    if election_id == KUPISKIO_MERO_2023_ELECTION_ID:
        return parse_kupiskio_mero_2023_anketa_samples(
            candidate_ids=candidate_ids,
            samples_root=samples_root,
            output_root=output_root,
        )
    if election_id == VISAGINO_MERO_2023_ELECTION_ID:
        return parse_visagino_mero_2023_anketa_samples(
            candidate_ids=candidate_ids,
            samples_root=samples_root,
            output_root=output_root,
        )
    if election_id == SEIMO_RASEINIU_KEDAINIU_2023_ELECTION_ID:
        return parse_seimo_raseiniu_kedainiu_2023_anketa_samples(
            candidate_ids=candidate_ids,
            samples_root=samples_root,
            output_root=output_root,
        )
    if election_id == MERU_2025_ELECTION_ID:
        return parse_meru_2025_anketa_samples(
            candidate_ids=candidate_ids,
            samples_root=samples_root,
            output_root=output_root,
        )
    if election_id == MERU_2017_ELECTION_ID:
        return parse_meru_2017_anketa_samples(
            candidate_ids=candidate_ids,
            samples_root=samples_root,
            output_root=output_root,
        )
    if election_id == MARIJAMPOLES_MERO_2017_ELECTION_ID:
        return parse_marijampoles_mero_2017_anketa_samples(
            candidate_ids=candidate_ids,
            samples_root=samples_root,
            output_root=output_root,
        )
    if election_id == MERU_2021_ELECTION_ID:
        return parse_meru_2021_anketa_samples(
            candidate_ids=candidate_ids,
            samples_root=samples_root,
            output_root=output_root,
        )
    if election_id == RADVILISKIO_MERO_2021_ELECTION_ID:
        return parse_radviliskio_mero_2021_anketa_samples(
            candidate_ids=candidate_ids,
            samples_root=samples_root,
            output_root=output_root,
        )
    if election_id == SEIMO_ANYKSCIU_PANEVEZIO_2017_ELECTION_ID:
        return parse_seimo_anyksciu_panevezio_2017_anketa_samples(
            candidate_ids=candidate_ids,
            samples_root=samples_root,
            output_root=output_root,
        )
    if election_id == SEIMO_ZANAVYKU_2018_ELECTION_ID:
        return parse_seimo_zanavyku_2018_anketa_samples(
            candidate_ids=candidate_ids,
            samples_root=samples_root,
            output_root=output_root,
        )
    if election_id == SEIMO_2019_ELECTION_ID:
        return parse_seimo_2019_anketa_samples(
            candidate_ids=candidate_ids,
            samples_root=samples_root,
            output_root=output_root,
        )
    if election_id == SAVIVALDYBIU_2023_ELECTION_ID:
        return parse_savivaldybiu_2023_anketa_samples(
            candidate_ids=candidate_ids,
            samples_root=samples_root,
            output_root=output_root,
        )
    if election_id == SAVIVALDYBIU_2019_ELECTION_ID:
        return parse_savivaldybiu_2019_anketa_samples(
            candidate_ids=candidate_ids,
            samples_root=samples_root,
            output_root=output_root,
        )
    if election_id == SEIMO_ZIRMUNU_2015_ELECTION_ID:
        return parse_seimo_zirmunu_2015_anketa_samples(
            candidate_ids=candidate_ids,
            samples_root=samples_root,
            output_root=output_root,
        )
    if election_id == SEIMO_VARENOS_EISISKIU_2015_ELECTION_ID:
        return parse_seimo_varenos_eisiskiu_2015_anketa_samples(
            candidate_ids=candidate_ids,
            samples_root=samples_root,
            output_root=output_root,
        )
    if election_id == TELSIU_MERO_2015_ELECTION_ID:
        return parse_telsiu_mero_2015_anketa_samples(
            candidate_ids=candidate_ids,
            samples_root=samples_root,
            output_root=output_root,
        )
    if election_id == PAKARTOTINIAI_SIRVINTU_TRAKU_2015_ELECTION_ID:
        return parse_pakartotiniai_sirvintu_traku_2015_anketa_samples(
            candidate_ids=candidate_ids,
            samples_root=samples_root,
            output_root=output_root,
        )
    if election_id == PAKARTOTINIAI_SILUTES_2015_ELECTION_ID:
        return parse_pakartotiniai_silutes_2015_anketa_samples(
            candidate_ids=candidate_ids,
            samples_root=samples_root,
            output_root=output_root,
        )
    if election_id == SAVIVALDYBIU_2015_ELECTION_ID:
        return parse_savivaldybiu_2015_anketa_samples(
            candidate_ids=candidate_ids,
            samples_root=samples_root,
            output_root=output_root,
        )
    if election_id == SAVIVALDYBIU_2011_ELECTION_ID:
        return parse_savivaldybiu_2011_anketa_samples(
            candidate_ids=candidate_ids,
            samples_root=samples_root,
            output_root=output_root,
        )
    if election_id == SAVIVALDYBIU_2007_ELECTION_ID:
        return parse_savivaldybiu_2007_anketa_samples(
            candidate_ids=candidate_ids,
            samples_root=samples_root,
            output_root=output_root,
        )
    if election_id == SEIMO_1996_ELECTION_ID:
        return parse_seimo_1996_anketa_samples(
            candidate_ids=candidate_ids,
            samples_root=samples_root,
            output_root=output_root,
        )
    if election_id == SEIMO_PAKARTOTINIAI_1997_KOVO_ELECTION_ID:
        return parse_seimo_pakartotiniai_1997_kovo_anketa_samples(
            candidate_ids=candidate_ids,
            samples_root=samples_root,
            output_root=output_root,
        )
    if election_id == SEIMO_AUKSTAITIJOS_1997_GRUODZIO_ELECTION_ID:
        return parse_seimo_aukstaitijos_1997_gruodzio_anketa_samples(
            candidate_ids=candidate_ids,
            samples_root=samples_root,
            output_root=output_root,
        )
    if election_id == SEIMO_NEVEZIO_1998_LAPKRICIO_ELECTION_ID:
        return parse_seimo_nevezio_1998_lapkricio_anketa_samples(
            candidate_ids=candidate_ids,
            samples_root=samples_root,
            output_root=output_root,
        )
    if election_id == SEIMO_PAKARTOTINIAI_1998_KOVO_ELECTION_ID:
        return parse_seimo_pakartotiniai_1998_kovo_anketa_samples(
            candidate_ids=candidate_ids,
            samples_root=samples_root,
            output_root=output_root,
        )
    if election_id == SEIMO_PAKARTOTINIAI_1999_KOVO_ELECTION_ID:
        return parse_seimo_pakartotiniai_1999_kovo_anketa_samples(
            candidate_ids=candidate_ids,
            samples_root=samples_root,
            output_root=output_root,
        )
    if election_id == SAVIVALDYBIU_1997_ELECTION_ID:
        return parse_savivaldybiu_1997_anketa_samples(
            candidate_ids=candidate_ids,
            samples_root=samples_root,
            output_root=output_root,
        )
    if election_id == SVENCIONIU_TARYBOS_1997_ELECTION_ID:
        return parse_svencioniu_tarybos_1997_anketa_samples(
            candidate_ids=candidate_ids,
            samples_root=samples_root,
            output_root=output_root,
        )
    if election_id == PREZIDENTO_2009_ELECTION_ID:
        return parse_prezidento_2009_anketa_samples(
            candidate_ids=candidate_ids,
            samples_root=samples_root,
            output_root=output_root,
        )
    if election_id == PREZIDENTO_2014_ELECTION_ID:
        return parse_prezidento_2014_anketa_samples(
            candidate_ids=candidate_ids,
            samples_root=samples_root,
            output_root=output_root,
        )
    if election_id == SEIMO_BIRZU_ZARASU_UKMERGES_2013_ELECTION_ID:
        return parse_seimo_birzu_zarasu_ukmerges_2013_anketa_samples(
            candidate_ids=candidate_ids,
            samples_root=samples_root,
            output_root=output_root,
        )
    if election_id == EP_2009_ELECTION_ID:
        return parse_ep_2009_anketa_samples(
            candidate_ids=candidate_ids,
            samples_root=samples_root,
            output_root=output_root,
        )
    if election_id == EP_2014_ELECTION_ID:
        return parse_ep_2014_anketa_samples(
            candidate_ids=candidate_ids,
            samples_root=samples_root,
            output_root=output_root,
        )
    if election_id == SEIMO_SILALES_SILUTES_VILNIAUS_SALCININKU_2009_ELECTION_ID:
        return parse_seimo_silales_silutes_vilniaus_salcininku_2009_anketa_samples(
            candidate_ids=candidate_ids,
            samples_root=samples_root,
            output_root=output_root,
        )
    if election_id == SEIMO_MARIJAMPOLES_2011_ELECTION_ID:
        return parse_seimo_marijampoles_2011_anketa_samples(
            candidate_ids=candidate_ids,
            samples_root=samples_root,
            output_root=output_root,
        )
    if election_id == SEIMO_DZUKIJOS_2007_ELECTION_ID:
        return parse_seimo_dzukijos_2007_anketa_samples(
            candidate_ids=candidate_ids,
            samples_root=samples_root,
            output_root=output_root,
        )
    if election_id == EP_2004_ELECTION_ID:
        return parse_ep_2004_anketa_samples(
            candidate_ids=candidate_ids,
            samples_root=samples_root,
            output_root=output_root,
        )
    if election_id == PREZIDENTO_2004_ELECTION_ID:
        return parse_prezidento_2004_anketa_samples(
            candidate_ids=candidate_ids,
            samples_root=samples_root,
            output_root=output_root,
        )
    if election_id == PREZIDENTO_2002_ELECTION_ID:
        return parse_prezidento_2002_anketa_samples(
            candidate_ids=candidate_ids,
            samples_root=samples_root,
            output_root=output_root,
        )
    if election_id == SEIMO_2004_ELECTION_ID:
        return parse_seimo_2004_anketa_samples(
            candidate_ids=candidate_ids,
            samples_root=samples_root,
            output_root=output_root,
        )
    if election_id == SEIMO_NAUJI_2003_ELECTION_ID:
        return parse_seimo_nauji_2003_anketa_samples(
            candidate_ids=candidate_ids,
            samples_root=samples_root,
            output_root=output_root,
        )
    if election_id == SEIMO_KEDAINIU_2005_ELECTION_ID:
        return parse_seimo_kedainiu_2005_anketa_samples(
            candidate_ids=candidate_ids,
            samples_root=samples_root,
            output_root=output_root,
        )
    if election_id == SEIMO_2000_ELECTION_ID:
        return parse_seimo_2000_anketa_samples(
            candidate_ids=candidate_ids,
            samples_root=samples_root,
            output_root=output_root,
        )
    if election_id == SAVIVALDYBIU_2000_ELECTION_ID:
        return parse_savivaldybiu_2000_anketa_samples(
            candidate_ids=candidate_ids,
            samples_root=samples_root,
            output_root=output_root,
        )
    if election_id == SAVIVALDYBIU_2002_ELECTION_ID:
        return parse_savivaldybiu_2002_anketa_samples(
            candidate_ids=candidate_ids,
            samples_root=samples_root,
            output_root=output_root,
        )
    if election_id == SEIMO_2008_ELECTION_ID:
        return parse_seimo_2008_anketa_samples(
            candidate_ids=candidate_ids,
            samples_root=samples_root,
            output_root=output_root,
        )
    if election_id == SEIMO_2012_ELECTION_ID:
        return parse_seimo_2012_anketa_samples(
            candidate_ids=candidate_ids,
            samples_root=samples_root,
            output_root=output_root,
        )
    raise ValueError(f"Unsupported election id: {election_id}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="VRK election scraper")
    subparsers = parser.add_subparsers(dest="command", required=True)

    fetch_parser = subparsers.add_parser(
        "fetch-sample",
        help="Download and save raw HTML sample for an election",
    )
    fetch_parser.add_argument("election_id", choices=FETCHABLE_ELECTION_IDS)
    fetch_parser.add_argument(
        "--allow-fixture-overwrite",
        action="store_true",
        help=(
            "Fetch even though samples/html/<election-id>/ already exists. The "
            "listing samples are tracked test fixtures, so re-capturing them is "
            "a deliberate act — refused by default (issue #95)."
        ),
    )

    sitemap_parser = subparsers.add_parser(
        "sitemap",
        help="Build sitemap JSON from a saved HTML sample",
    )
    sitemap_parser.add_argument("election_id", choices=FETCHABLE_ELECTION_IDS)
    sitemap_parser.add_argument(
        "--sample",
        type=Path,
        default=None,
        help="Path to HTML sample file. Defaults to samples/html/2016-seimo/list.html",
    )

    candidate_sample_parser = subparsers.add_parser(
        "fetch-first-candidate-samples",
        help="Download first sitemap candidate page and tab subpages as HTML samples",
    )
    candidate_sample_parser.add_argument("election_id", choices=FETCHABLE_ELECTION_IDS)
    candidate_sample_parser.add_argument(
        "--sitemap",
        type=Path,
        default=None,
        help="Path to sitemap JSON. Defaults to sitemaps/<election-id>.json",
    )
    candidate_sample_parser.add_argument(
        "--samples-root",
        type=Path,
        default=None,
        help="Path to candidate sample folders. Defaults to samples/html/<election-id>",
    )
    candidate_sample_parser.add_argument(
        "--allow-new-samples",
        action="store_true",
        help=(
            "Allow creating new candidate directories under samples root. "
            "Disabled by default so sample fixtures stay fixed."
        ),
    )

    targeted_sample_parser = subparsers.add_parser(
        "fetch-candidate-samples",
        help="Download selected candidate page and tab subpages as HTML samples",
    )
    targeted_sample_parser.add_argument("election_id", choices=FETCHABLE_ELECTION_IDS)
    targeted_sample_parser.add_argument(
        "--candidate-id",
        action="append",
        required=True,
        help="Candidate ID from sitemap. Can be passed multiple times.",
    )
    targeted_sample_parser.add_argument(
        "--sitemap",
        type=Path,
        default=None,
        help="Path to sitemap JSON. Defaults to sitemaps/<election-id>.json",
    )
    targeted_sample_parser.add_argument(
        "--samples-root",
        type=Path,
        default=None,
        help="Path to candidate sample folders. Defaults to samples/html/<election-id>",
    )
    targeted_sample_parser.add_argument(
        "--allow-new-samples",
        action="store_true",
        help=(
            "Allow creating new candidate directories under samples root. "
            "Disabled by default so sample fixtures stay fixed."
        ),
    )
    targeted_sample_parser.add_argument(
        "--anomalies-path",
        type=Path,
        default=None,
        help=(
            "Path to write fetch-stage anomalies JSONL. Without it the events are "
            "counted and thrown away, which is how a failed tab download became invisible."
        ),
    )

    results_parser = subparsers.add_parser(
        "build-results",
        help=(
            "Fetch VRK's results pages for an election whose candidate pages mark no "
            "winner (1996-2015) and write sitemaps/<election-id>.results.json; "
            "parse-anketa-samples joins it into kandidatavimas.isrinktas"
        ),
    )
    results_parser.add_argument("election_id", choices=RESULTS_ELECTION_IDS)

    parse_anketa_parser = subparsers.add_parser(
        "parse-anketa-samples",
        help="Parse saved anketa HTML samples into initial structured JSON output",
    )
    parse_anketa_parser.add_argument("election_id", choices=PARSABLE_ELECTION_IDS)
    parse_anketa_parser.add_argument(
        "--candidate-id",
        action="append",
        default=None,
        help="Candidate ID to parse. Can be passed multiple times. If omitted, parse all sampled candidates.",
    )
    parse_anketa_parser.add_argument(
        "--samples-root",
        type=Path,
        default=None,
        help="Path to candidate sample folders. Defaults to samples/html/<election-id>",
    )
    parse_anketa_parser.add_argument(
        "--output-root",
        type=Path,
        default=None,
        help="Path to output JSON folder. Defaults to data/<election-id>",
    )
    parse_anketa_parser.add_argument(
        "--anomalies-path",
        type=Path,
        default=None,
        help="Path to write anomalies JSONL. Defaults to <output-root>/anomalies.jsonl",
    )

    anomalies_report_parser = subparsers.add_parser(
        "anomalies-report",
        help=(
            "Read the corpus's anomalies.jsonl files: counts per event type per "
            "election, and a diff against docs/anomaly-baseline.tsv so a new "
            "failure stands out against the known ones"
        ),
    )
    anomalies_report_parser.add_argument(
        "election_id",
        nargs="*",
        help="Elections to report on. Defaults to every election under the data root.",
    )
    anomalies_report_parser.add_argument(
        "--data-root",
        type=Path,
        default=Path("data"),
        help="Corpus root holding <election-id>/anomalies.jsonl. Defaults to data/.",
    )
    anomalies_report_parser.add_argument(
        "--errors-only",
        action="store_true",
        help="Report only severity=error events -- a page lost, not a page doubted.",
    )
    anomalies_report_parser.add_argument(
        "--baseline",
        type=Path,
        default=None,
        help=f"Baseline TSV to diff against. Defaults to {ANOMALY_BASELINE}.",
    )
    anomalies_report_parser.add_argument(
        "--update-baseline",
        action="store_true",
        help="Rewrite the baseline from this run. Requires a run over every election.",
    )

    return parser


def _summarize_anomalies(anomalies: list[dict[str, Any]]) -> tuple[dict[str, int], dict[str, int]]:
    by_type: dict[str, int] = {}
    by_severity: dict[str, int] = {}
    for event in anomalies:
        event_type = str(event.get("eventType", "unknown"))
        severity = str(event.get("severity", "unknown"))
        by_type[event_type] = by_type.get(event_type, 0) + 1
        by_severity[severity] = by_severity.get(severity, 0) + 1
    return by_type, by_severity


def _write_and_report_anomalies(
    path: Path,
    anomalies: list[dict[str, Any]],
    *,
    stage: str | None = None,
    candidate_ids: list[str] | None = None,
) -> None:
    """Persist a run's anomaly events and print what they were.

    Both the fetch and the parse command end here. Until issue #85 only parse
    did: `fetch-candidate-samples` counted its events and dropped them, so the
    corpus held 8,949 anomalies of which not one was a `fetch` event, against
    the 147 fetch-stage call sites that can raise them.

    With `stage` given, the run owns only that stage's events for
    `candidate_ids` and the rest of the file is kept (issue #139: the parse
    command's default path is the election's own `anomalies.jsonl`, and
    writing it whole from a one-candidate run emptied it). Without it the
    file is the run's alone and is written whole -- the fetch command, whose
    path has no default and which the batch runner points at a fresh
    per-candidate file.
    """
    if stage is None:
        write_jsonl(path, anomalies)
        kept = 0
    else:
        kept, _ = write_run_events(path, anomalies, stage=stage, candidate_ids=candidate_ids)
    by_type, by_severity = _summarize_anomalies(anomalies)
    print(f"Anomalies saved: {path}")
    print(f"Total anomalies: {len(anomalies)}" + (f" (this run; {kept} kept from other runs and stages)" if kept else ""))
    if by_severity:
        print(
            "By severity: "
            + ", ".join(
                f"{name}={count}" for name, count in sorted(by_severity.items(), key=lambda item: item[0])
            )
        )
    if by_type:
        top_types = sorted(by_type.items(), key=lambda item: (-item[1], item[0]))[:10]
        print("Top anomaly types: " + ", ".join(f"{name}={count}" for name, count in top_types))


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    if args.command == "fetch-sample":
        refusal = listing_fixture_refusal(args.election_id, args.allow_fixture_overwrite)
        if refusal:
            print(refusal, file=sys.stderr)
            return 1
        sample_path = _fetch_listing_sample_for_election(args.election_id)
        print(f"Saved HTML sample: {sample_path}")
        return 0

    if args.command == "sitemap":
        output_path, stats = _build_sitemap_from_sample_for_election(
            args.election_id,
            sample_path=args.sample,
        )
        print(f"Saved sitemap: {output_path}")
        print(
            "Rows: {rows}, extracted: {extracted}, skipped: {skipped}, duplicateIds: {dups}".format(
                rows=stats["rows"],
                extracted=stats["extracted"],
                skipped=stats["skipped"],
                dups=stats["duplicate_candidate_ids"],
            )
        )
        return 0

    if args.command == "build-results":
        # A page that could not be fetched, or a build that resolved no winner
        # without the pages saying nobody was elected, is a failed build: no
        # file is written and the exit status says so, which is what
        # scripts/run_election_batches.sh tests before it parses (issue #134).
        try:
            output_path, stats = _build_results_for_election(args.election_id)
        except (requests.RequestException, ValueError) as exc:
            print(f"build-results failed for {args.election_id}: {exc}", file=sys.stderr)
            return 1
        print(f"Saved results: {output_path}")
        for key, value in stats.items():
            print(f"  {key}: {value}")
        return 0

    if args.command == "fetch-first-candidate-samples":
        result = _fetch_first_candidate_with_tabs_for_election(
            election_id=args.election_id,
            sitemap_path=args.sitemap or Path(f"sitemaps/{args.election_id}.json"),
            samples_root=args.samples_root or Path(f"samples/html/{args.election_id}"),
            allow_new_samples=args.allow_new_samples,
        )
        candidate = result["candidate"]
        print(f"Candidate: {candidate['candidateName']} ({candidate['candidateId']})")
        print(f"Anketa sample: {result['anketa_path']}")
        print(
            "Tab samples saved: {saved} (tab links found: {found})".format(
                saved=result["tabs_saved"],
                found=result["tab_count"],
            )
        )
        missing = result["missing_expected_tabs"]
        if missing:
            print("Missing expected tabs: " + ", ".join(missing))
        else:
            print("All expected candidate tabs found")
        print(f"Index: {result['index_path']}")
        return 0

    if args.command == "fetch-candidate-samples":
        payload = _fetch_candidates_with_tabs_for_election(
            election_id=args.election_id,
            candidate_ids=args.candidate_id,
            sitemap_path=args.sitemap or Path(f"sitemaps/{args.election_id}.json"),
            samples_root=args.samples_root or Path(f"samples/html/{args.election_id}"),
            allow_new_samples=args.allow_new_samples,
        )
        print(f"Fetched candidates: {payload['count']}")
        all_anomalies: list[dict[str, Any]] = []
        for result in payload["results"]:
            candidate = result["candidate"]
            print(f"- {candidate['candidateName']} ({candidate['candidateId']})")
            print(
                "  Tab samples saved: {saved} (tab links found: {found})".format(
                    saved=result["tabs_saved"],
                    found=result["tab_count"],
                )
            )
            missing = result["missing_expected_tabs"]
            if missing:
                print("  Missing expected tabs: " + ", ".join(missing))
            else:
                print("  All expected candidate tabs found")
            anomalies = result.get("anomalies", [])
            all_anomalies.extend(anomalies)
            if anomalies:
                print(f"  Anomalies: {len(anomalies)}")
            print(f"  Index: {result['index_path']}")
        if args.anomalies_path is not None:
            _write_and_report_anomalies(args.anomalies_path, all_anomalies)
        elif all_anomalies:
            # No default path: this command writes the file it is given whole
            # (a portrait backfill's fetch events for the same candidate are
            # not this command's to replace), so a default of the election's
            # own anomalies.jsonl would truncate it. The batch runner passes a
            # per-candidate path and appends.
            by_type, _ = _summarize_anomalies(all_anomalies)
            print(
                f"Fetch anomalies: {len(all_anomalies)} "
                + ", ".join(f"{name}={count}" for name, count in sorted(by_type.items()))
                + " (pass --anomalies-path to keep them)"
            )
        # A fetch that recorded an error did not get the candidate, and the
        # exit status has to say so (issue #158). It returned 0 whatever
        # happened: driving this branch with every tab answering 503 produced
        # six TabDownloadFailed plus one TabDownloadPartial, all
        # severity=error, and still exited 0 — so
        # `scripts/run_election_batches.sh`'s `if ! fetch_candidate` never
        # fired, the id was appended to `done_ids.txt`, and the run reported
        # "complete". What a transient outage should mean is that the
        # candidate stays pending.
        errors = [a for a in all_anomalies if a.get("severity") == "error"]
        if errors:
            print(
                f"{len(errors)} fetch error(s): this candidate was not fetched."
                " Exiting non-zero so the runner keeps it pending.",
                file=sys.stderr,
            )
            return 1
        return 0

    if args.command == "parse-anketa-samples":
        samples_root = args.samples_root or Path(f"samples/html/{args.election_id}")
        output_root = args.output_root or Path(f"data/{args.election_id}")
        results = _parse_anketa_samples_for_election(
            election_id=args.election_id,
            candidate_ids=args.candidate_id,
            samples_root=samples_root,
            output_root=output_root,
        )
        all_anomalies: list[dict[str, Any]] = []
        print(f"Parsed candidates: {len(results)}")
        for result in results:
            print(
                "- {name} ({cid}) -> {path}".format(
                    name=result["candidateName"] or "Unknown",
                    cid=result["candidateId"],
                    path=result["outputPath"],
                )
            )
            print(
                "  rows={rows}, answered={answered}".format(
                    rows=result["rowCount"],
                    answered=result["answeredRowCount"],
                )
            )
            anomalies = result.get("anomalies", [])
            all_anomalies.extend(anomalies)
            if anomalies:
                print(f"  anomalies={len(anomalies)}")

        # The default path is the election's own file, shared with the batch
        # runner's appends and the portrait backfill's fetch events: this run
        # replaces only its own parse-stage events for the candidates it
        # parsed and keeps every other line (issue #139).
        anomalies_path = args.anomalies_path or (output_root / "anomalies.jsonl")
        _write_and_report_anomalies(
            anomalies_path,
            all_anomalies,
            stage="parse",
            candidate_ids=[str(result["candidateId"]) for result in results],
        )
        return 0

    if args.command == "anomalies-report":
        return _anomalies_report(
            data_root=args.data_root,
            election_ids=args.election_id or None,
            errors_only=args.errors_only,
            baseline_path=args.baseline or ANOMALY_BASELINE,
            update_baseline=args.update_baseline,
        )

    parser.error("Unknown command")
    return 1


def _anomalies_report(
    *,
    data_root: Path,
    election_ids: list[str] | None,
    errors_only: bool,
    baseline_path: Path,
    update_baseline: bool,
) -> int:
    """Print the corpus's anomalies and diff them against the baseline.

    Exit 1 when the run holds an event type the baseline does not name, or
    more of one than it records. Fewer is progress: it is printed and does not
    fail, so that a parser fix does not have to touch the baseline in the same
    commit as the fix -- up to a point. An election whose total fell to less
    than half of what the baseline records also exits 1: a wiped
    `anomalies.jsonl` looks exactly like that (issue #139 measured 8,636 -> 8
    passing as "progress"), and a parser fix that large is a deliberate change
    that updates the baseline in the same commit.
    """
    if not data_root.is_dir():
        print(f"No such data root: {data_root}", file=sys.stderr)
        return 2

    absent = [eid for eid in election_ids or [] if not (data_root / eid).is_dir()]
    if absent:
        print(f"Not under {data_root}: " + ", ".join(absent), file=sys.stderr)
        return 2

    events = list(anomaly_report.read_events(data_root, election_ids))
    if errors_only:
        events = [event for event in events if event.get("severity") == "error"]
    counts = anomaly_report.tally(events)

    for election_id, rows in anomaly_report.by_election(counts).items():
        total = sum(count for _, count in rows)
        print(f"{election_id}  ({total} event{'' if total == 1 else 's'})")
        for key, count in rows:
            print(f"    {count:>6}  {key.event_type:<38} {key.severity}")

    totals = anomaly_report.severity_totals(counts)
    print(
        f"\n{len(events)} event(s) across {len({key.election for key in counts})} election(s)"
        + (": " + ", ".join(f"{name}={count}" for name, count in totals.items()) if totals else "")
    )

    # What the corpus does *not* hold, which no gate asked about (issue
    # #158): a candidate VRK's sitemap lists and `data/` has no record for.
    # `final_report` in the batch runner diffs the two, but only during a
    # scrape and into a gitignored `.run-state/` directory that died with the
    # worktrees those scrapes ran in. A gap with a CandidateFetchFailed event
    # against it is recorded and explained; a gap with none is a finding.
    gaps = anomaly_report.sitemap_gaps(data_root.parent, election_ids)
    unrecorded = anomaly_report.unrecorded_gaps(gaps, events)
    if gaps:
        held = sum(len(v) for v in gaps.values())
        print(
            f"{held} sitemap candidate(s) across {len(gaps)} election(s) have no record"
            f"; {held - sum(len(v) for v in unrecorded.values())} recorded as"
            f" {anomaly_report.FETCH_FAILED}"
        )

    if update_baseline:
        if election_ids or errors_only:
            print(
                "--update-baseline rewrites the whole file, so it cannot be narrowed"
                " to some elections or to one severity",
                file=sys.stderr,
            )
            return 2
        anomaly_report.write_baseline(baseline_path, counts)
        print(f"Baseline rewritten: {baseline_path} ({len(counts)} row(s))")
        return 0

    if unrecorded:
        print(
            f"\n{sum(len(v) for v in unrecorded.values())} sitemap candidate(s) have no"
            f" record and no {anomaly_report.FETCH_FAILED} event saying why:",
            file=sys.stderr,
        )
        for election_id, candidates in sorted(unrecorded.items()):
            for candidate_id in candidates[:20]:
                print(f"    {election_id}  {candidate_id}", file=sys.stderr)
            if len(candidates) > 20:
                print(f"    ... and {len(candidates) - 20} more in {election_id}", file=sys.stderr)
        print(
            "    Fetch them, or record why they cannot be fetched:"
            " `python -m scraper fetch-candidate-samples <election> --candidate-id <id>`",
            file=sys.stderr,
        )

    baseline = anomaly_report.read_baseline(baseline_path)
    if not baseline:
        print(
            f"\nNo baseline at {baseline_path}; nothing to compare against."
            " Write one with --update-baseline.",
            file=sys.stderr,
        )
        # A gap is a finding whether or not there is a baseline: it is about
        # what the corpus does not hold, not about what changed.
        return 1 if unrecorded else 0

    # A narrowed run only ever sees part of the baseline, so it compares
    # against that part rather than reporting every unvisited row as resolved.
    if election_ids:
        baseline = {key: count for key, count in baseline.items() if key.election in election_ids}
    if errors_only:
        baseline = {key: count for key, count in baseline.items() if key.severity == "error"}

    new, regressed, improved = anomaly_report.diff(counts, baseline)
    collapsed = anomaly_report.collapsed(counts, baseline)

    if improved:
        print(f"\n{len(improved)} row(s) below the baseline:")
        for key, count, was in improved:
            print(f"    {key.election}  {key.event_type} [{key.severity}]  {was} -> {count}")

    if collapsed:
        print(
            f"\n{len(collapsed)} election(s) lost more than half their events since the"
            " baseline -- a wiped anomalies.jsonl looks exactly like this. If the drop"
            " is a parser fix, rerun with --update-baseline:",
            file=sys.stderr,
        )
        for election, count, was in collapsed:
            print(f"    {election}  {was} -> {count}", file=sys.stderr)

    if not new and not regressed and not collapsed and not unrecorded:
        print("\nNothing new against the baseline.")
        return 0

    if new:
        print(f"\n{len(new)} event type(s) the baseline does not name:", file=sys.stderr)
        for key, count in new:
            print(
                f"    {key.election}  {key.event_type} [{key.severity}]  {count}",
                file=sys.stderr,
            )
    if regressed:
        print(f"\n{len(regressed)} row(s) above the baseline:", file=sys.stderr)
        for key, count, was in regressed:
            print(
                f"    {key.election}  {key.event_type} [{key.severity}]"
                f"  {was} -> {count} (+{count - was})",
                file=sys.stderr,
            )
    return 1
