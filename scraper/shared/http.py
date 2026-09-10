"""Shared HTTP fetching for every election module.

All scraper traffic to vrk.lt flows through ``fetch_text`` and ``fetch_bytes``
— 226 call sites — so politeness and byte fidelity live here: an honest
User-Agent, keep-alive connection reuse via a shared session, a minimum
interval between requests, bounded retries with backoff for failures that a
second attempt can fix, and an explicit decoding step. Only GETs are retried;
every fetch is an idempotent page read. After retries are exhausted the caller
sees the same exception types as before (HTTPError from raise_for_status,
ConnectionError from the transport), so call sites need no changes.

**Decoding is explicit** (issue #136). It used to be
``response.encoding = response.encoding or "utf-8"``, which reads like a
defence and is dead code: for a ``text/html`` response with no charset
parameter, requests sets ``encoding`` to ``ISO-8859-1`` — per RFC 2616, which
HTML5 abandoned — so the ``or`` never fires and the page is decoded as
latin-1. Measured on a stub serving ``Ąžuolas ŠIMKŪNAS – teisėjas`` as bare
``text/html``: ``Ä\\x84Å¾uolas Å\\xa0IMKÅªNAS â\\x80\\x93 teisÄ\\x97jas``, no
exception, no U+FFFD. And that is not an exotic response: the 1996–2015
retained pages all carry ``<meta charset=utf-8>``, and the eleven modern-era
elections (2016 on) carry no charset anywhere — a ``2024-seimo``
``anketa.html`` is a bare fragment with no ``<head>`` at all. Nothing but
vrk.lt's own ``Content-Type`` header stood between the corpus and mojibake,
and no test noticed: a mirror whose only real file was an ``http.py`` pinned
to ISO-8859-1 ran the whole suite green.

So the charset is chosen, and the rule is one line: **a declaration or clean
UTF-8, or the decode is reported.**

1. A charset the response *declares* — the ``charset=`` parameter of
   ``Content-Type`` (parsed here, because requests cannot tell "no charset"
   from "ISO-8859-1"), then the document's own ``<meta charset>``,
   ``<meta http-equiv="Content-Type">`` or XML declaration, which is what the
   pre-2016 pages carry and the header does not always repeat. Tried strictly,
   silent on success.
2. UTF-8, tried strictly. Silent on success: the corpus is UTF-8.
3. Anything else is a *guess*, and a guess is a finding whether or not it
   succeeds — because a guess that quietly succeeds is precisely what latin-1
   was doing to 180,305 charset-less pages.

Latin-1 is never a candidate, and no detected single-byte codec is reached
before UTF-8 has been tried, for the same reason: a codec that decodes every
byte sequence can never fail out loud. ``charset_normalizer`` will find *some*
encoding for any bytes at all — asked about a UTF-8 page with one stray byte
in it, it answers with a CJK codec that reads the whole page as garbage
without complaint. So a body UTF-8 cannot decode is split by how much of it
UTF-8 *can*: predominantly-valid UTF-8 keeps UTF-8 and takes the replacement
characters (``MOSTLY_UTF8_LOSS_RATIO``), and only a body UTF-8 cannot make
sense of at all falls to a detected codec.

**A decode that had to guess is a finding**, not a silent edit.
``response.text`` decodes with ``errors="replace"``, and 44 call sites wrote
that string straight into the retained tree: 130 retained pages (2004-seimo
109, 2000-seimo 19, 2004-ep 2) hold 192 U+FFFD, each of them valid UTF-8 —
i.e. the *re-encoded* lossy decode. On disk "vrk.lt served a broken byte" and
"our fetcher destroyed one" became indistinguishable, and
``provenance.sourceSha256`` fingerprints the re-encoding rather than the page.
Those 192 look upstream: all 130 pages decode their other Lithuanian
characters correctly, 191 of the 192 sit amid intact Lithuanian, and the
broken characters are ``š`` and the opening quote ``„`` in company names
(``„Lietuvos``, ``vir?ininku``, ``i?rinktas``) — the signature of a value
entered in windows-1257 and stored into a UTF-8 template, not of a dropped
packet. A fact worth *recording* rather than raising over, since dropping the
page would cost a real candidacy for one byte: the loss is appended to
``DECODE_FINDINGS`` and warned about on stderr, and
``drain_decode_findings()`` hands them to a caller that has an election and
candidate to file them under.

**A truncated body is retried.** urllib3's ``Retry`` covers the request and
the response *headers*; the body read happens after it is done, so a
connection dropped mid-page — the case this module's docstring has always
named — got exactly one attempt: a stub promising 1,000 bytes and delivering
10 raised ``ChunkedEncodingError`` immediately, where ``/always503`` took four
attempts over 12 s. The body read now has its own bounded retry.

**Pacing holds whichever entry point is used.** There was no delay anywhere
here, and none in any of the 55 ``candidate_samples.py`` modules; the only
throttle in the repository was a single ``sleep 0.4`` between candidates in
the bash runner, which the documented per-candidate CLI bypasses entirely.
The corpus cost 495,337 requests over 112,540 candidates (2024-seimo: 7.72
per candidate, max 12), all of them as fast as the connection allowed.
``MIN_INTERVAL_SECONDS`` is now enforced inside both fetchers, so a request
cannot leave this process sooner than that after the last one, whoever called.

**A 200 that is not the page is refused.** A bot-check interstitial answers
200 with an HTML body, and 44 call sites would write it into the retained tree
under the candidate's name. ``CHALLENGE_MARKERS`` catches the common ones and
raises, so the call site records a fetch anomaly instead. 403 is deliberately
*not* retried: the one 403 this project has seen was vrk.lt refusing a GitHub
Actions runner by address, which no number of attempts fixes — the message
says so instead of spending 12 s finding out.
"""

from __future__ import annotations

import os
import re
import sys
import threading
import time
from typing import NamedTuple

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

USER_AGENT = "vrk-scraper (+https://github.com/Viespirkiu-grupe/vrk)"

RETRY_TOTAL = 3
RETRY_BACKOFF_SECONDS = 2.0
RETRY_STATUSES = (429, 500, 502, 503, 504)

#: Attempts at reading the *body* once the headers have arrived. Separate from
#: `Retry` above, which is finished by then.
BODY_READ_ATTEMPTS = 3
BODY_READ_BACKOFF_SECONDS = 1.0

#: The floor on the interval between two requests out of this process.
#: 0.15 s is about 6.7 requests a second — the corpus's 495,337 requests in
#: 20 hours rather than as fast as the socket allows. Override with
#: `VRK_MIN_REQUEST_INTERVAL=0` for a local stub, or a larger value to be
#: kinder. Per *process*: a parallel run paces each worker, not the fleet.
MIN_INTERVAL_SECONDS = float(os.environ.get("VRK_MIN_REQUEST_INTERVAL", "0.15"))

#: Substrings that mean a 200 is a bot check rather than the page. Matched
#: against the first 4 KiB, case-insensitively.
CHALLENGE_MARKERS = (
    "cf-browser-verification",
    "__cf_chl",
    "cf_chl_opt",
    "just a moment...",
    "attention required!",
    "checking your browser before",
    "incapsula incident id",
    "_incapsula_resource",
    "please enable javascript and cookies to continue",
    "g-recaptcha",
    "h-captcha",
)

#: How much of a body to scan for a charset declaration or a challenge
#: marker. The HTML spec's own prescan limit is 1024 bytes; VRK's pre-2016
#: pages put the meta well inside 4 KiB.
SNIFF_BYTES = 4096

_META_CHARSET = re.compile(rb"""<meta[^>]+charset\s*=\s*["']?\s*([\w.:-]+)""", re.I)
_XML_ENCODING = re.compile(rb"""<\?xml[^>]+encoding\s*=\s*["']([\w.:-]+)["']""", re.I)


class ChallengePage(requests.exceptions.RequestException):
    """A 200 whose body is a bot check, not the page that was asked for."""


class DecodeFinding(NamedTuple):
    """A body no declared or detected charset could decode without loss."""

    url: str
    content_type: str | None
    tried: tuple[str, ...]
    used: str
    replacements: int
    sample: str

    def __str__(self) -> str:
        return (
            f"{self.url}: {self.replacements} byte(s) no charset could decode"
            f" (Content-Type {self.content_type!r}, tried {', '.join(self.tried)};"
            f" decoded as {self.used} with replacement). Near: {self.sample!r}"
        )


#: Decode losses this process has seen, oldest first. Appended to rather than
#: raised, because the loss is in the source and dropping the page would cost
#: a real candidacy; `drain_decode_findings` empties it.
DECODE_FINDINGS: list[DecodeFinding] = []


def drain_decode_findings() -> list[DecodeFinding]:
    """Take and clear the decode losses seen so far.

    For a caller that knows which election and candidate a fetch belonged to
    and can turn each into a `SourceDecodeLoss` anomaly. Nothing calls this
    yet from the 226 fetch sites; the warning on stderr is what a scrape sees
    today, and this is the hook that makes the finding durable.
    """
    findings = list(DECODE_FINDINGS)
    DECODE_FINDINGS.clear()
    return findings


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


# ---------------------------------------------------------------------------
# Pacing
# ---------------------------------------------------------------------------

_pace_lock = threading.Lock()
_last_request_at = 0.0


def _pace(min_interval: float) -> None:
    """Block until `min_interval` has passed since the last request."""
    global _last_request_at
    if min_interval <= 0:
        return
    with _pace_lock:
        wait = _last_request_at + min_interval - time.monotonic()
        if wait > 0:
            time.sleep(wait)
        _last_request_at = time.monotonic()


# ---------------------------------------------------------------------------
# Decoding
# ---------------------------------------------------------------------------


def header_charset(content_type: str | None) -> str | None:
    """The `charset=` parameter of a Content-Type, or None if it has none.

    Parsed here rather than through `requests.utils.get_encoding_from_headers`,
    which answers `ISO-8859-1` for a bare `text/html` — the RFC 2616 default
    HTML5 dropped — and so cannot distinguish a served charset from no
    charset at all. That conflation is the whole of this module's old
    encoding defence.
    """
    if not content_type:
        return None
    for parameter in content_type.split(";")[1:]:
        name, _, value = parameter.partition("=")
        if name.strip().lower() == "charset":
            return value.strip().strip("'\"") or None
    return None


def document_charset(body: bytes) -> str | None:
    """The charset the document declares about itself, or None.

    `<meta charset>`, `<meta http-equiv="Content-Type" content="…charset=…">`
    and an XML declaration all end in the same place, so one pattern reads
    the lot. This is what the 1996–2015 pages carry; the 2016-era fragments
    carry nothing.
    """
    head = body[:SNIFF_BYTES]
    for pattern in (_META_CHARSET, _XML_ENCODING):
        match = pattern.search(head)
        if match:
            return match.group(1).decode("ascii", "ignore") or None
    return None


def _known(charset: str | None) -> str | None:
    """`charset` if Python can decode with it, else None."""
    if not charset:
        return None
    try:
        "".encode(charset)
    except LookupError:
        return None
    return charset


#: Above this share of characters lost to replacement, a body that UTF-8
#: cannot decode is treated as genuinely *not* UTF-8 and a guessed single-byte
#: codec is preferred. Below it, the body is UTF-8 with a few stray bytes --
#: which is what the corpus's 130 damaged pages are, 1 to 4 losses in 10 KB --
#: and a single-byte codec would silently mangle every correct diacritic on
#: the page to "fix" those few. U+FFFD with a finding beats plausible garbage.
MOSTLY_UTF8_LOSS_RATIO = 0.005


def declared_charsets(body: bytes, content_type: str | None) -> list[str]:
    """The charsets the response *says* it is, best first: the Content-Type
    parameter, then the document's own declaration."""
    declared = [_known(header_charset(content_type)), _known(document_charset(body))]
    return _dedupe([c for c in declared if c])


def detected_charset(body: bytes) -> str | None:
    """`charset_normalizer`'s guess, or None. A hint, never authoritative."""
    try:
        from charset_normalizer import from_bytes

        best = from_bytes(body[: 64 * 1024]).best()
        return _known(best.encoding) if best is not None else None
    except Exception:  # noqa: BLE001 -- detection is a hint, not a dependency
        return None


def _dedupe(charsets: list[str]) -> list[str]:
    ordered: list[str] = []
    for charset in charsets:
        if charset.lower() not in {c.lower() for c in ordered}:
            ordered.append(charset)
    return ordered


def charset_candidates(body: bytes, content_type: str | None) -> list[str]:
    """Every charset this body may be decoded with, best first.

    Declarations come before guesses, UTF-8 before any guess, and latin-1 is
    never added as a guess: it decodes every byte sequence, so it can never
    fail out loud, which is exactly what made the old fallback silent. The
    same is true of any single-byte codec, so a *detected* one is only ever
    reached after UTF-8 has been tried and reported.
    """
    detected = detected_charset(body)
    return _dedupe(
        [*declared_charsets(body, content_type), "utf-8", *([detected] if detected else [])]
    )


def _record(
    body: bytes, content_type: str | None, url: str, tried: list[str], used: str, text: str
) -> None:
    index = text.find("�")
    finding = DecodeFinding(
        url=url,
        content_type=content_type,
        tried=tuple(tried),
        used=used,
        replacements=text.count("�"),
        sample=text[max(0, index - 40) : index + 41] if index >= 0 else text[:80],
    )
    DECODE_FINDINGS.append(finding)
    print(f"warning: {finding}", file=sys.stderr)


def decode_body(body: bytes, content_type: str | None, url: str) -> str:
    """`body` as text. A decode that had to guess is a finding.

    The rule, in one line: **a declaration or clean UTF-8, or it is
    reported.** Anything else is a guess, and a guess that happens to succeed
    is the failure mode this replaced — latin-1 decoded 180,305 charset-less
    pages without a murmur.

    1. A charset the response *declares*, tried strictly. Silent on success.
    2. UTF-8, tried strictly. Silent on success: the corpus is UTF-8.
    3. Otherwise a guess, and a finding either way. A body that is
       predominantly valid UTF-8 with a few stray bytes keeps UTF-8 and takes
       the replacement characters; one that UTF-8 cannot make sense of at all
       falls to a detected codec that decodes it whole.
    """
    declared = declared_charsets(body, content_type)
    for charset in declared:
        try:
            return body.decode(charset)
        except (UnicodeDecodeError, LookupError):
            continue
    try:
        return body.decode("utf-8")
    except UnicodeDecodeError:
        pass

    tried = _dedupe([*declared, "utf-8"])
    lossy = body.decode("utf-8", errors="replace")
    losses = lossy.count("�")
    if lossy and losses / len(lossy) <= MOSTLY_UTF8_LOSS_RATIO:
        # Valid UTF-8 with stray bytes in it -- the 130 damaged pages' shape.
        _record(body, content_type, url, tried, "utf-8", lossy)
        return lossy

    detected = detected_charset(body)
    if detected:
        tried.append(detected)
        try:
            text = body.decode(detected)
        except (UnicodeDecodeError, LookupError):
            text = None
        if text is not None:
            _record(body, content_type, url, tried, detected, text)
            return text
    _record(body, content_type, url, tried, "utf-8", lossy)
    return lossy


def _check_not_a_challenge(body: bytes, url: str) -> None:
    head = body[:SNIFF_BYTES].decode("utf-8", "replace").lower()
    for marker in CHALLENGE_MARKERS:
        if marker in head:
            raise ChallengePage(
                f"{url}: answered 200 with a bot-check page, not the page asked for"
                f" (matched {marker!r}). Storing it would put an interstitial in the"
                " retained tree under a candidate's name."
            )


def _raise_for_status(response: requests.Response, url: str) -> None:
    if response.status_code == 403:
        # Deliberately not in RETRY_STATUSES. The one 403 this project has
        # met was vrk.lt refusing a GitHub Actions runner by address, which
        # no number of attempts fixes; spending 12 s of backoff to learn that
        # is worse than saying it.
        raise requests.exceptions.HTTPError(
            f"403 Forbidden for {url} — vrk.lt refuses this client or this address."
            " Not retried: the 403 this project has seen was an address block, not"
            " rate limiting. Try from another network, or raise"
            " VRK_MIN_REQUEST_INTERVAL if a burst may have provoked it.",
            response=response,
        )
    response.raise_for_status()


def _read_body(
    url: str,
    timeout_seconds: int,
    session: requests.Session,
    min_interval: float,
    attempts: int,
) -> tuple[bytes, requests.Response]:
    """The response body, retrying a read that dies mid-page.

    `Retry` on the adapter covers the request and the response headers and is
    finished before the body is read, so a dropped connection used to get one
    attempt — a stub promising 1,000 bytes and delivering 10 raised
    `ChunkedEncodingError` at once, where a 503 got four attempts over 12 s.
    """
    last: Exception | None = None
    for attempt in range(attempts):
        _pace(min_interval)
        try:
            response = session.get(url, timeout=timeout_seconds)
            _raise_for_status(response, url)
            return response.content, response
        except (
            requests.exceptions.ChunkedEncodingError,
            requests.exceptions.ContentDecodingError,
            requests.exceptions.ConnectionError,
        ) as error:
            last = error
            if attempt + 1 < attempts:
                time.sleep(BODY_READ_BACKOFF_SECONDS * (2**attempt))
    raise last  # type: ignore[misc]  -- unreachable with attempts >= 1


def fetch_text(
    url: str,
    timeout_seconds: int = 45,
    session: requests.Session | None = None,
    *,
    min_interval: float | None = None,
    body_attempts: int = BODY_READ_ATTEMPTS,
) -> str:
    body, response = _read_body(
        url,
        timeout_seconds,
        session or _get_default_session(),
        MIN_INTERVAL_SECONDS if min_interval is None else min_interval,
        body_attempts,
    )
    _check_not_a_challenge(body, url)
    return decode_body(body, response.headers.get("Content-Type"), url)


def fetch_bytes(
    url: str,
    timeout_seconds: int = 45,
    session: requests.Session | None = None,
    *,
    min_interval: float | None = None,
    body_attempts: int = BODY_READ_ATTEMPTS,
) -> bytes:
    """A binary page — the 2004 presidential candidates' Word documents.

    Same session, pacing and retries as ``fetch_text``; the body is returned
    undecoded, because a ``.doc`` run through text decoding is corrupt beyond
    repair. No challenge check: a `.doc` is not HTML, and the marker scan
    would be reading a binary as text.
    """
    body, _ = _read_body(
        url,
        timeout_seconds,
        session or _get_default_session(),
        MIN_INTERVAL_SECONDS if min_interval is None else min_interval,
        body_attempts,
    )
    return body


def _reset_pacing_for_tests() -> None:
    """Forget the last request time, so a test's timings start from zero."""
    global _last_request_at
    _last_request_at = 0.0
