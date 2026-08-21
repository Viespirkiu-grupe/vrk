import argparse
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
from scraper.elections.seimo_2012.results import build_results as build_seimo_2012_results
from scraper.elections.seimo_birzu_zarasu_ukmerges_2013.results import build_results as build_seimo_birzu_zarasu_ukmerges_2013_results
from scraper.elections.prezidento_2009.results import build_results as build_prezidento_2009_results
from scraper.elections.prezidento_2014.results import build_results as build_prezidento_2014_results
from scraper.elections.ep_2014.results import build_results as build_ep_2014_results
from scraper.elections.seimo_zirmunu_2015.results import build_results as build_seimo_zirmunu_2015_results
from scraper.elections.seimo_varenos_eisiskiu_2015.results import build_results as build_seimo_varenos_eisiskiu_2015_results
from scraper.elections.telsiu_mero_2015.results import build_results as build_telsiu_mero_2015_results
from scraper.elections.pakartotiniai_sirvintu_traku_2015.results import build_results as build_pakartotiniai_sirvintu_traku_2015_results
from scraper.elections.pakartotiniai_silutes_2015.results import build_results as build_pakartotiniai_silutes_2015_results
from scraper.elections.savivaldybiu_2015.results import build_results as build_savivaldybiu_2015_results
from scraper.shared.anomalies import write_jsonl

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
    SEIMO_1996_ELECTION_ID,
    SEIMO_PAKARTOTINIAI_1997_KOVO_ELECTION_ID,
    SEIMO_AUKSTAITIJOS_1997_GRUODZIO_ELECTION_ID,
    SAVIVALDYBIU_1997_ELECTION_ID,
    SVENCIONIU_TARYBOS_1997_ELECTION_ID,
    PREZIDENTO_2014_ELECTION_ID,
    SEIMO_BIRZU_ZARASU_UKMERGES_2013_ELECTION_ID,
    EP_2014_ELECTION_ID,
    SEIMO_2012_ELECTION_ID,
    PREZIDENTO_2009_ELECTION_ID,
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
    SEIMO_1996_ELECTION_ID,
    SEIMO_PAKARTOTINIAI_1997_KOVO_ELECTION_ID,
    SEIMO_AUKSTAITIJOS_1997_GRUODZIO_ELECTION_ID,
    SAVIVALDYBIU_1997_ELECTION_ID,
    SVENCIONIU_TARYBOS_1997_ELECTION_ID,
    PREZIDENTO_2014_ELECTION_ID,
    SEIMO_BIRZU_ZARASU_UKMERGES_2013_ELECTION_ID,
    EP_2014_ELECTION_ID,
    SEIMO_2012_ELECTION_ID,
    PREZIDENTO_2009_ELECTION_ID,
]

# Elections whose pages mark no winner and whose elected status is joined in
# from VRK's results tree (scraper/shared/election_results.py).
RESULTS_ELECTION_IDS = [
    PREZIDENTO_2009_ELECTION_ID,
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
]

_RESULTS_BUILDERS = {
    PREZIDENTO_2009_ELECTION_ID: build_prezidento_2009_results,
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
}


def _build_results_for_election(election_id: str) -> tuple[Path, dict[str, Any]]:
    builder = _RESULTS_BUILDERS.get(election_id)
    if builder is None:
        raise ValueError(f"No results builder for election id: {election_id}")
    return builder()


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
    if election_id == SEIMO_1996_ELECTION_ID:
        return fetch_seimo_1996_listing_sample()
    if election_id == SEIMO_PAKARTOTINIAI_1997_KOVO_ELECTION_ID:
        return fetch_seimo_pakartotiniai_1997_kovo_listing_sample()
    if election_id == SEIMO_AUKSTAITIJOS_1997_GRUODZIO_ELECTION_ID:
        return fetch_seimo_aukstaitijos_1997_gruodzio_listing_sample()
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
    if election_id == EP_2014_ELECTION_ID:
        return fetch_ep_2014_listing_sample()
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
    if election_id == SEIMO_1996_ELECTION_ID:
        return build_seimo_1996_sitemap_from_sample(sample_path=sample_path)
    if election_id == SEIMO_PAKARTOTINIAI_1997_KOVO_ELECTION_ID:
        return build_seimo_pakartotiniai_1997_kovo_sitemap_from_sample(sample_path=sample_path)
    if election_id == SEIMO_AUKSTAITIJOS_1997_GRUODZIO_ELECTION_ID:
        return build_seimo_aukstaitijos_1997_gruodzio_sitemap_from_sample(sample_path=sample_path)
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
    if election_id == EP_2014_ELECTION_ID:
        return build_ep_2014_sitemap_from_sample(sample_path=sample_path)
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
    if election_id == EP_2014_ELECTION_ID:
        return fetch_ep_2014_first_candidate_with_tabs(
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
    if election_id == EP_2014_ELECTION_ID:
        return fetch_ep_2014_candidates_with_tabs(
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
    if election_id == EP_2014_ELECTION_ID:
        return parse_ep_2014_anketa_samples(
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

    results_parser = subparsers.add_parser(
        "build-results",
        help=(
            "Fetch VRK's results pages for an election whose candidate pages mark no "
            "winner (2012-2015) and write sitemaps/<election-id>.results.json; "
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


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    if args.command == "fetch-sample":
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
        output_path, stats = _build_results_for_election(args.election_id)
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
            if anomalies:
                print(f"  Anomalies: {len(anomalies)}")
            print(f"  Index: {result['index_path']}")
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

        anomalies_path = args.anomalies_path or (output_root / "anomalies.jsonl")
        write_jsonl(anomalies_path, all_anomalies)
        by_type, by_severity = _summarize_anomalies(all_anomalies)
        print(f"Anomalies saved: {anomalies_path}")
        print(f"Total anomalies: {len(all_anomalies)}")
        if by_severity:
            print(
                "By severity: "
                + ", ".join(
                    f"{name}={count}" for name, count in sorted(by_severity.items(), key=lambda item: item[0])
                )
            )
        if by_type:
            top_types = sorted(by_type.items(), key=lambda item: (-item[1], item[0]))[:10]
            print(
                "Top anomaly types: "
                + ", ".join(f"{name}={count}" for name, count in top_types)
            )
        return 0

    parser.error("Unknown command")
    return 1
