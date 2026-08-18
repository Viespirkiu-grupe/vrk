from __future__ import annotations

from pathlib import Path
import re
from typing import Any

from scraper.shared import municipal_sitemap as municipal
from scraper.shared.municipal_sitemap import (  # re-exported: the shape is shared
    CANDIDATE_LINK_MARKER,
    LIST_LINK_MARKER,
    MUNICIPALITY_LINK_MARKER,
    VRK_STATINIAI_BASE,
    clean_candidate_name,
    extract_vrk_candidate_id,
    normalize_space,
    resolve_candidate_url,
    utc_now_iso,
)

ELECTION_ID = "2019-kovo-3-savivaldybiu-tarybu"
BASE_PATH = "/rinkimai/864/rnk1144/kandidatai"

# The same two-structure shape as 2023, four years earlier:
#
#   savKandidataiMerai.html    410 mayoral candidates, all 60 municipalities,
#                              on one page;
#   savKandidataiSarasai.html  an index of 465 party/coalition/committee lists,
#                              whose 13,635 council candidates live one page
#                              deeper.
#
# 379 people run for both and appear in both structures under the same VRK
# candidate id; 31 mayoral candidates appear on no council list at all. The
# union is 13,666, the total VRK publishes on savKandidataiSuvestine.
LISTING_URL = (
    "https://www.vrk.lt/2019-savivaldybiu-tarybu"
    f"?srcUrl={BASE_PATH}/savKandidataiMerai.html"
)
MAYORS_URL = f"{VRK_STATINIAI_BASE.rstrip('/')}{BASE_PATH}/savKandidataiMerai.html"
LISTS_INDEX_URL = f"{VRK_STATINIAI_BASE.rstrip('/')}{BASE_PATH}/savKandidataiSarasai.html"

DEFAULT_SAMPLE_PATH = Path(f"samples/html/{ELECTION_ID}/list.html")
DEFAULT_WRAPPER_SAMPLE_PATH = Path(f"samples/html/{ELECTION_ID}/page.html")
DEFAULT_LISTS_INDEX_SAMPLE_NAME = municipal.LISTS_INDEX_SAMPLE_NAME
DEFAULT_LISTS_SAMPLE_DIRNAME = municipal.LISTS_SAMPLE_DIRNAME
DEFAULT_SITEMAP_PATH = Path(f"sitemaps/{ELECTION_ID}.json")

# 2019 words the dual-candidacy flag differently from 2023: mayors were elected
# to the council as well under the rules of the time, so the listing says
# "kandidatas į savivaldybės tarybos narius - merus" where 2023 says
# "kandidatas į savivaldybės merus". The 2023 pattern matches none of these.
# The separator is written as a plain hyphen here but is matched loosely, and
# both gender inflections are published.
MAYOR_MARKER_PATTERN = re.compile(
    r"\(\s*kandidat[aė]s?\s+į\s+savivaldybės\s+tarybos\s+narius\s*[-–—]\s*merus\s*\)",
    flags=re.IGNORECASE,
)


# Thin wrappers over the shared machinery. Each reads this module's constants at
# call time, so a test can monkeypatch MAYOR_MARKER_PATTERN and see the effect.


def extract_candidate_note(raw_name: str) -> str:
    return municipal.extract_candidate_note(raw_name, MAYOR_MARKER_PATTERN)


def _is_elected(anchor: Any) -> bool:
    return municipal.is_elected(anchor)


def _parse_int(value: str | None) -> int | None:
    return municipal.parse_int(value)


def _municipality_from_cell(cell: Any) -> dict[str, Any] | None:
    return municipal.municipality_from_cell(cell)


def _select_data_table(soup: Any, table_id: str, link_marker: str) -> Any | None:
    return municipal.select_data_table(soup, table_id, link_marker)


def _table_rows(table: Any | None) -> list[Any]:
    return municipal.table_rows(table)


def _extract_list_page_links(lists_index_html: str) -> list[dict[str, Any]]:
    return municipal.extract_list_page_links(lists_index_html)


def _parse_mayor_rows(mayors_html: str) -> list[dict[str, Any]]:
    return municipal.parse_mayor_rows(mayors_html, MAYOR_MARKER_PATTERN)


def _parse_list_page(list_html: str, link: dict[str, Any]) -> list[dict[str, Any]]:
    return municipal.parse_list_page(list_html, link, MAYOR_MARKER_PATTERN)


def _build_candidate_id(candidate_name: str, vrk_candidate_id: str) -> str:
    return municipal.build_candidate_id(candidate_name, vrk_candidate_id)


def fetch_listing_sample(sample_path: Path = DEFAULT_SAMPLE_PATH) -> Path:
    return municipal.fetch_listing_sample(
        sample_path=sample_path,
        wrapper_sample_path=DEFAULT_WRAPPER_SAMPLE_PATH,
        listing_url=LISTING_URL,
        mayors_url=MAYORS_URL,
        lists_index_url=LISTS_INDEX_URL,
    )


def build_sitemap_from_sample(
    sample_path: Path | None = None,
    output_path: Path = DEFAULT_SITEMAP_PATH,
) -> tuple[Path, dict[str, int]]:
    return municipal.build_sitemap(
        sample_path=sample_path if sample_path is not None else DEFAULT_SAMPLE_PATH,
        output_path=output_path,
        election_id=ELECTION_ID,
        listing_url=LISTING_URL,
        mayor_marker=MAYOR_MARKER_PATTERN,
    )
