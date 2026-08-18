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

ELECTION_ID = "2023-kovo-5-savivaldybiu-tarybu-ir-meru"
BASE_PATH = "/rinkimai/1304/rnk1630/kandidatai"

# Two listing structures, neither a superset of the other:
#
#   savKandidataiMerai.html    433 mayoral candidates, all 60 municipalities,
#                              on one page;
#   savKandidataiSarasai.html  an index of 467 party/committee lists, whose
#                              13,769 council candidates live one page deeper.
#
# 406 people run for both and appear in both structures under the same VRK
# candidate id; 27 mayoral candidates appear on no council list at all. The
# union is 13,796, which is the total VRK publishes on savKandidataiSuvestine.
LISTING_URL = (
    "https://www.vrk.lt/kandidatai-2023-sav"
    f"?srcUrl={BASE_PATH}/savKandidataiMerai.html"
)
MAYORS_URL = f"{VRK_STATINIAI_BASE.rstrip('/')}{BASE_PATH}/savKandidataiMerai.html"
LISTS_INDEX_URL = f"{VRK_STATINIAI_BASE.rstrip('/')}{BASE_PATH}/savKandidataiSarasai.html"

DEFAULT_SAMPLE_PATH = Path(f"samples/html/{ELECTION_ID}/list.html")
DEFAULT_WRAPPER_SAMPLE_PATH = Path(f"samples/html/{ELECTION_ID}/page.html")
DEFAULT_LISTS_INDEX_SAMPLE_NAME = municipal.LISTS_INDEX_SAMPLE_NAME
DEFAULT_LISTS_SAMPLE_DIRNAME = municipal.LISTS_SAMPLE_DIRNAME
DEFAULT_SITEMAP_PATH = Path(f"sitemaps/{ELECTION_ID}.json")

# The list row appends this to the name of a candidate who is also running for
# mayor. The 'a' matters: "kandidatas" and "kandidatė" are both published, and a
# character class that omits it silently matches only the 105 feminine
# spellings rather than all 406 dual candidacies — a partial match that still
# looks plausible. The 2019 election words this differently; see that module.
MAYOR_MARKER_PATTERN = re.compile(
    r"\(\s*kandidat[aė]s?\s+į\s+savivaldybės\s+merus\s*\)",
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
