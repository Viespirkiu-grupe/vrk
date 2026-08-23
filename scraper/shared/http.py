"""Shared HTTP fetching for every election module.

All scraper traffic to vrk.lt flows through ``fetch_text``, so politeness and
robustness live here: an honest User-Agent, keep-alive connection reuse via a
shared session, and bounded retries with backoff for failures that a second
attempt can fix — dropped connections and 429/5xx responses. Only GETs are
retried; every fetch is an idempotent page read. A 4xx other than 429 still
fails immediately, and after retries are exhausted the caller sees the same
exception types as before (HTTPError from raise_for_status, ConnectionError
from the transport), so call sites need no changes.
"""

from __future__ import annotations

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

USER_AGENT = "vrk-scraper (+https://github.com/Viespirkiu-grupe/vrk)"

RETRY_TOTAL = 3
RETRY_BACKOFF_SECONDS = 2.0
RETRY_STATUSES = (429, 500, 502, 503, 504)


def build_session(
    retry_total: int = RETRY_TOTAL,
    backoff_seconds: float = RETRY_BACKOFF_SECONDS,
) -> requests.Session:
    session = requests.Session()
    session.headers["User-Agent"] = USER_AGENT
    retry = Retry(
        total=retry_total,
        backoff_factor=backoff_seconds,
        status_forcelist=RETRY_STATUSES,
        allowed_methods=frozenset({"GET"}),
        # Hand the final failing response back so raise_for_status raises the
        # HTTPError callers already expect, instead of urllib3's RetryError.
        raise_on_status=False,
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    return session


_default_session: requests.Session | None = None


def _get_default_session() -> requests.Session:
    global _default_session
    if _default_session is None:
        _default_session = build_session()
    return _default_session


def fetch_text(
    url: str,
    timeout_seconds: int = 45,
    session: requests.Session | None = None,
) -> str:
    response = (session or _get_default_session()).get(url, timeout=timeout_seconds)
    response.raise_for_status()
    response.encoding = response.encoding or "utf-8"
    return response.text


def fetch_bytes(
    url: str,
    timeout_seconds: int = 45,
    session: requests.Session | None = None,
) -> bytes:
    """A binary page — the 2004 presidential candidates' Word documents.

    Same session, politeness and retries as ``fetch_text``; the body is
    returned undecoded, because a ``.doc`` run through text decoding is
    corrupt beyond repair.
    """
    response = (session or _get_default_session()).get(url, timeout=timeout_seconds)
    response.raise_for_status()
    return response.content
