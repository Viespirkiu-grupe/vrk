"""The five campaign-finance sub-tabs, derived from the campaign URL itself.

A campaign participant's page family has five sub-pages — treasurer, auditor,
donations, funding reports, contracts — but the tab list VRK renders on the
campaign root depends on the *participant type*: an atstovaujamasis
(represented) participant's root shows one tab (2023-2024), or none at all
(2012-2020), while the sub-pages themselves exist and even carry the full
five-tab navigation. The walkers trusted the rendered list, which is how
2,189 represented campaigns ended up with donations but no funding reports
(issue #99). The URLs never needed the list — they follow the participant id:

- **Modern family** (politKamp trees, 2016 on):
  ``…/politKamp/<tree>/dalyviai/<type>_pkdId-<id>.html`` →
  ``…/savarankiskas{Izdininkas,Auditorius,Aukotojai,Finansavimas,Sutartys}_pkdId-<id>.html``.
  The ``savarankiskas`` stem serves both participant types — the retained
  atstovaujamasis pages' own tab lists point at it (measured on 2023-2024).
- **Older family** (per-election rinkimai trees, 2003-2015):
  ``…/Dalyvis<id>/Dalyvio<id><Tab>.html`` with the stems
  ``Izdininkas, Auditorius, AukotojuSarasas, FinansavimoAtaskaitos, Sutartys``.

Derivation is a claim about the URL scheme, not about VRK having published
the page: the 2016, 2020 and 2019-03 trees answer 404 for every derived
atstovaujamasis sub-page (spot-checked 2026-08-31), and that absence is
recorded rather than treated as a fetch failure — ``is_absent_derived_tab``
is how a walker tells "VRK never published this" from a real error.
"""

from __future__ import annotations

import re
from typing import Any
from urllib.parse import urlparse, urlunparse

import requests

#: label, file slug (what the parsers dispatch on), modern URL stem, older URL stem.
CAMPAIGN_TABS: tuple[tuple[str, str, str, str], ...] = (
    ("Iždininkas", "izdininkas", "Izdininkas", "Izdininkas"),
    ("Auditorius", "auditorius", "Auditorius", "Auditorius"),
    ("Aukų ir aukotojų sąrašas", "auku-ir-aukotoju-sarasas", "Aukotojai", "AukotojuSarasas"),
    ("Finansavimo ataskaitos", "finansavimo-ataskaitos", "Finansavimas", "FinansavimoAtaskaitos"),
    ("Sutartys", "sutartys", "Sutartys", "Sutartys"),
)

#: The modern campaign page: any participant-type page under a politKamp
#: dalyviai tree — the root (`savarankiskas_`/`atstovaujamasis_`) and the
#: sub-tabs (`savarankiskasAukotojai_`, …) all match, so a derivation from
#: any of them lands on the same five URLs.
MODERN_CAMPAIGN_PATTERN = re.compile(
    r"^(?P<prefix>.*/)(?:savarankiskas|atstovaujamasis)[^/_]*_pkdId-(?P<id>\d+)(?:_[^/]*)?\.html$",
    re.IGNORECASE,
)

#: The older campaign page: `Dalyvis<id>/Dalyvio<id><Tab>.html`.
OLDER_CAMPAIGN_PATTERN = re.compile(
    r"^(?P<prefix>.*/Dalyvis(?P<id>\d+)/)Dalyvio(?P=id)[A-Za-z]*\.html$"
)


def derive_subtab_links(campaign_url: str) -> list[dict[str, Any]]:
    """The five sub-tab links a campaign URL implies: ``[{label, slug, url,
    derived}]`` in the page's own tab order, or ``[]`` for a URL matching
    neither family (nothing is guessed for an unknown scheme)."""
    parsed = urlparse(campaign_url)
    modern = MODERN_CAMPAIGN_PATTERN.match(parsed.path)
    older = OLDER_CAMPAIGN_PATTERN.match(parsed.path)
    links: list[dict[str, Any]] = []
    for label, slug, modern_stem, older_stem in CAMPAIGN_TABS:
        if modern:
            path = f"{modern.group('prefix')}savarankiskas{modern_stem}_pkdId-{modern.group('id')}.html"
        elif older:
            path = f"{older.group('prefix')}Dalyvio{older.group('id')}{older_stem}.html"
        else:
            return []
        links.append(
            {
                "label": label,
                "slug": slug,
                "url": urlunparse(parsed._replace(path=path)),
                "derived": True,
            }
        )
    return links


def merge_campaign_tab_links(
    extracted: list[dict[str, Any]],
    derived: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """The page's own tab list first — its labels and URLs are what VRK
    rendered — then every derived tab the list omitted, matched by slug or
    URL so a listed tab is never fetched twice under a second name."""
    seen_slugs = {tab.get("slug") for tab in extracted if tab.get("slug")}
    seen_urls = {tab.get("url") for tab in extracted}
    merged = list(extracted)
    for tab in derived:
        if tab["slug"] in seen_slugs or tab["url"] in seen_urls:
            continue
        merged.append(tab)
    return merged


def is_absent_derived_tab(tab: dict[str, Any], exc: Exception) -> bool:
    """A derived URL answering 404 means VRK never published that sub-page —
    the 2016-2020-era trees do this for every atstovaujamasis sub-tab — so
    the walker records the absence instead of a download-failure anomaly.
    A 404 on a tab the page itself listed stays an anomaly."""
    if not tab.get("derived"):
        return False
    if not isinstance(exc, requests.HTTPError):
        return False
    response = getattr(exc, "response", None)
    return response is not None and response.status_code == 404
