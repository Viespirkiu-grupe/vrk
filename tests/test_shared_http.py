"""Unit tests for the shared HTTP fetcher.

`scraper.shared.http.fetch_text` carries every request the scraper makes to
vrk.lt, so its retry, decoding, pacing and identification behaviour is pinned
here against a local stdlib HTTP server — no network, no fixtures. The retry
tests build their session with a zero backoff so exercising real urllib3
retries stays fast.

The decoding tests are issue #136's: until then the module's whole encoding
defence was `response.encoding = response.encoding or "utf-8"`, which cannot
fire (requests answers `ISO-8859-1` for a bare `text/html`), a truncated body
got one attempt where a 503 got four, there was no pacing anywhere, and
`fetch_bytes` had no test at all.
"""

from __future__ import annotations

import threading
import time
import unittest
import unittest.mock
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import requests

from scraper.shared import http as http_module
from scraper.shared.http import (
    RETRY_STATUSES,
    RETRY_TOTAL,
    USER_AGENT,
    ChallengePage,
    build_session,
    charset_candidates,
    decode_body,
    document_charset,
    fetch_bytes,
    fetch_text,
    header_charset,
)

#: Every Lithuanian diacritic the corpus holds, in one string: what latin-1
#: decoding destroys and what a correct fetch must return unchanged.
LITHUANIAN = "Ąžuolas ŠIMKŪNAS – teisėjas, „Lietuvos“ įmonė, viršininku"


class _ScriptedHandler(BaseHTTPRequestHandler):
    """Serve a scripted sequence of status codes, recording each request."""

    script: list[int] = []
    requests_seen: list[dict[str, str]] = []
    lock = threading.Lock()

    def do_GET(self):  # noqa: N802 - BaseHTTPRequestHandler API
        with self.lock:
            self.requests_seen.append(dict(self.headers))
            status = self.script.pop(0) if self.script else 200
        body = "labas".encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):  # keep test output quiet
        pass


class SharedHttpTest(unittest.TestCase):
    def setUp(self):
        _ScriptedHandler.script = []
        _ScriptedHandler.requests_seen = []
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), _ScriptedHandler)
        self.url = f"http://127.0.0.1:{self.server.server_address[1]}/page.html"
        thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(self.server.shutdown)
        self.session = build_session(backoff_seconds=0)

    def test_sends_identifying_user_agent(self):
        text = fetch_text(self.url, session=self.session)
        self.assertEqual(text, "labas")
        self.assertEqual(_ScriptedHandler.requests_seen[0].get("User-Agent"), USER_AGENT)
        self.assertIn("github.com/Viespirkiu-grupe/vrk", USER_AGENT)

    def test_retries_transient_server_errors_then_succeeds(self):
        _ScriptedHandler.script = [503, 502]
        text = fetch_text(self.url, session=self.session)
        self.assertEqual(text, "labas")
        self.assertEqual(len(_ScriptedHandler.requests_seen), 3)

    def test_persistent_server_error_raises_http_error(self):
        _ScriptedHandler.script = [503] * (RETRY_TOTAL + 1)
        with self.assertRaises(requests.HTTPError):
            fetch_text(self.url, session=self.session)
        self.assertEqual(len(_ScriptedHandler.requests_seen), RETRY_TOTAL + 1)

    def test_client_error_fails_immediately_without_retry(self):
        _ScriptedHandler.script = [404]
        with self.assertRaises(requests.HTTPError):
            fetch_text(self.url, session=self.session)
        self.assertEqual(len(_ScriptedHandler.requests_seen), 1)

    def test_retry_statuses_cover_throttling_and_upstream_failures(self):
        self.assertIn(429, RETRY_STATUSES)
        for status in (500, 502, 503, 504):
            self.assertIn(status, RETRY_STATUSES)


class _BodyHandler(BaseHTTPRequestHandler):
    """Serve a body with a chosen Content-Type, or a deliberately short one."""

    protocol_version = "HTTP/1.1"
    body: bytes = b""
    content_type: str | None = "text/html"
    truncate_to: int | None = None
    attempts: int = 0
    lock = threading.Lock()

    def do_GET(self):  # noqa: N802 - BaseHTTPRequestHandler API
        with self.lock:
            type(self).attempts += 1
            attempt = type(self).attempts
        self.send_response(200)
        if self.content_type is not None:
            self.send_header("Content-Type", self.content_type)
        self.send_header("Content-Length", str(len(self.body)))
        self.end_headers()
        if self.truncate_to is not None and attempt <= (self.truncate_to or 0):
            # Promise the whole body and deliver ten bytes, then hang up:
            # the shape of a connection dropped mid-page.
            self.wfile.write(self.body[:10])
            self.wfile.flush()
            self.close_connection = True
            return
        self.wfile.write(self.body)

    def log_message(self, *args):
        pass


class _BodyServerTest(unittest.TestCase):
    def serve(self, body: bytes, content_type: str | None = "text/html", truncate_to=None) -> str:
        _BodyHandler.body = body
        _BodyHandler.content_type = content_type
        _BodyHandler.truncate_to = truncate_to
        _BodyHandler.attempts = 0
        server = ThreadingHTTPServer(("127.0.0.1", 0), _BodyHandler)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        self.addCleanup(server.shutdown)
        http_module._reset_pacing_for_tests()
        http_module.DECODE_FINDINGS.clear()
        self.addCleanup(http_module.DECODE_FINDINGS.clear)
        # The body-read backoff is real seconds; exercising the retry does
        # not need to wait them out.
        patched = unittest.mock.patch.object(http_module, "BODY_READ_BACKOFF_SECONDS", 0.01)
        patched.start()
        self.addCleanup(patched.stop)
        self.session = build_session(backoff_seconds=0)
        return f"http://127.0.0.1:{server.server_address[1]}/page.html"

    def fetch(self, url, **kwargs):
        kwargs.setdefault("min_interval", 0)
        return fetch_text(url, session=self.session, **kwargs)


class DecodingTests(_BodyServerTest):
    """The charset is chosen, not defaulted (issue #136)."""

    def test_a_page_with_no_charset_anywhere_still_decodes(self):
        # The eleven modern-era elections: a bare fragment, no <head>, and a
        # Content-Type with no charset parameter. Decoded as latin-1 this
        # came back as 'Ä\x84Å¾uolas Å\xa0IMKÅªNAS …' with no exception.
        url = self.serve(LITHUANIAN.encode("utf-8"), "text/html")
        self.assertEqual(self.fetch(url), LITHUANIAN)
        self.assertEqual(http_module.DECODE_FINDINGS, [])

    def test_the_headers_charset_wins_when_it_is_really_there(self):
        url = self.serve(LITHUANIAN.encode("utf-8"), "text/html; charset=utf-8")
        self.assertEqual(self.fetch(url), LITHUANIAN)

    def test_a_declared_windows_1257_page_decodes_as_windows_1257(self):
        # The Baltic code page. Decoded as UTF-8 it would not decode at all;
        # as latin-1 it would decode to the wrong letters, silently.
        url = self.serve(LITHUANIAN.encode("cp1257"), "text/html; charset=windows-1257")
        self.assertEqual(self.fetch(url), LITHUANIAN)

    def test_the_documents_own_meta_charset_is_read(self):
        # What every 1996-2015 retained page carries, and the header need not
        # repeat.
        page = b'<html><head><meta charset="windows-1257"></head><body>'
        page += LITHUANIAN.encode("cp1257") + b"</body></html>"
        url = self.serve(page, "text/html")
        self.assertIn(LITHUANIAN, self.fetch(url))

    #: A page the size of a real one, valid UTF-8 with one stray
    #: windows-1257 byte in it (0xF0, `š`) — the measured shape of the 130
    #: damaged retained pages: 1 to 4 losses in about 10 KB, every other
    #: Lithuanian character on the page intact.
    MOSTLY_UTF8 = (
        ("Krikščionių demokratų sąjungos narys, Rokiškio rajonas. " * 180).encode("utf-8")
        + b"\xf0"
        + " Krikčionių".encode("utf-8")
    )

    def test_a_body_no_charset_decodes_is_a_finding_not_a_silent_edit(self):
        # The page is kept -- dropping it would cost a real candidacy -- and
        # the loss is recorded instead of edited silently into the corpus.
        url = self.serve(self.MOSTLY_UTF8, "text/html")
        text = self.fetch(url)
        self.assertIn("�", text)
        self.assertIn("Krikščionių", text, "the correct diacritics must survive")
        self.assertEqual(len(http_module.DECODE_FINDINGS), 1)
        finding = http_module.DECODE_FINDINGS[0]
        self.assertEqual(finding.replacements, 1)
        self.assertEqual(finding.url, url)
        self.assertEqual(finding.used, "utf-8")
        self.assertEqual(http_module.drain_decode_findings(), [finding])
        self.assertEqual(http_module.DECODE_FINDINGS, [])

    def test_a_mostly_utf8_page_is_not_re_read_as_a_single_byte_codec(self):
        # The trap this ordering exists for. A single-byte codec decodes any
        # byte sequence, so a detector will happily "fix" one stray byte by
        # reading the whole page as something else -- turning every correct
        # ščųėž on it into plausible garbage. U+FFFD with a finding is the
        # lesser loss, and it is honest.
        text = decode_body(self.MOSTLY_UTF8, "text/html", "x")
        self.assertEqual(text.count("Krikščionių"), 180)
        self.assertEqual(text.count("�"), 1)

    def test_a_wholly_single_byte_page_falls_to_a_detected_codec(self):
        # The other side of the rule: nothing declared, UTF-8 cannot read it
        # at all, and a guess that decodes it whole is better than a page of
        # replacement characters -- reported either way.
        body = (LITHUANIAN + " ").encode("cp1257") * 40
        text = decode_body(body, "text/html", "x")
        self.assertNotIn("�", text)
        self.assertEqual(len(http_module.DECODE_FINDINGS), 1)
        self.assertNotEqual(http_module.DECODE_FINDINGS[0].used.lower().replace("_", "-"), "utf-8")

    def test_latin_1_is_never_a_guess(self):
        # It decodes every byte sequence, which is what made the old fallback
        # silent: a charset that can never fail can never be wrong out loud.
        for content_type in ("text/html", "text/plain", None):
            with self.subTest(content_type):
                candidates = charset_candidates(LITHUANIAN.encode("utf-8"), content_type)
                lowered = [c.lower().replace("_", "-") for c in candidates]
                self.assertNotIn("iso-8859-1", lowered)
                self.assertNotIn("latin-1", lowered)
                self.assertIn("utf-8", lowered)

    def test_a_declaration_is_tried_before_utf8_and_utf8_before_any_guess(self):
        body = b'<meta charset="windows-1257">' + LITHUANIAN.encode("cp1257")
        candidates = [c.lower().replace("_", "-") for c in charset_candidates(body, "text/html")]
        self.assertEqual(candidates[0], "windows-1257")
        self.assertLessEqual(candidates.index("utf-8"), 1)

    def test_header_charset_tells_absent_from_iso_8859_1(self):
        # requests cannot: get_encoding_from_headers answers ISO-8859-1 for a
        # bare text/html, so `response.encoding or "utf-8"` never fires.
        self.assertIsNone(header_charset("text/html"))
        self.assertIsNone(header_charset(None))
        self.assertEqual(header_charset("text/html; charset=utf-8"), "utf-8")
        self.assertEqual(header_charset('text/html; charset="windows-1257"'), "windows-1257")
        self.assertEqual(header_charset("text/html;charset=UTF-8;boundary=x"), "UTF-8")

    def test_document_charset_reads_all_three_declaration_forms(self):
        self.assertEqual(document_charset(b'<meta charset="utf-8">'), "utf-8")
        self.assertEqual(
            document_charset(b'<meta http-equiv="Content-Type" content="text/html; charset=windows-1257">'),
            "windows-1257",
        )
        self.assertEqual(document_charset(b'<?xml version="1.0" encoding="ISO-8859-13"?>'), "ISO-8859-13")
        self.assertIsNone(document_charset(b"<div>a bare 2024-seimo fragment</div>"))

    def test_an_unknown_charset_name_is_skipped_not_raised(self):
        # VRK has served `charset=unicode` before now; a LookupError from a
        # typo must not take the page down.
        text = decode_body(LITHUANIAN.encode("utf-8"), "text/html; charset=utf-9", "x")
        self.assertEqual(text, LITHUANIAN)


class BodyRetryTests(_BodyServerTest):
    def test_a_truncated_body_is_retried(self):
        # urllib3's Retry is finished before the body is read, so this got
        # exactly one attempt and a ChunkedEncodingError where /always503 got
        # four attempts over 12 s.
        body = b"x" * 1000
        url = self.serve(body, "text/html; charset=utf-8", truncate_to=1)
        self.assertEqual(self.fetch(url), body.decode())
        self.assertEqual(_BodyHandler.attempts, 2)

    def test_a_body_that_never_arrives_raises_after_its_attempts(self):
        url = self.serve(b"x" * 1000, "text/html; charset=utf-8", truncate_to=99)
        with self.assertRaises(requests.exceptions.RequestException):
            self.fetch(url, body_attempts=2)
        self.assertEqual(_BodyHandler.attempts, 2)


class ChallengePageTests(_BodyServerTest):
    def test_a_bot_check_answered_200_is_refused(self):
        # 44 call sites write what fetch_text returns straight into the
        # retained tree, under the candidate's name.
        body = b"<html><head><title>Just a moment...</title></head><body>checking</body></html>"
        url = self.serve(body, "text/html; charset=utf-8")
        with self.assertRaises(ChallengePage):
            self.fetch(url)

    def test_a_real_page_that_merely_mentions_a_captcha_is_not_refused(self):
        body = "<html><body>Kandidatas rašė apie captcha technologijas</body></html>".encode()
        url = self.serve(body, "text/html; charset=utf-8")
        self.assertIn("Kandidatas", self.fetch(url))


class ForbiddenTests(unittest.TestCase):
    def test_403_is_not_retried_and_says_why(self):
        class Handler(BaseHTTPRequestHandler):
            seen = 0

            def do_GET(self):  # noqa: N802
                type(self).seen += 1
                self.send_response(403)
                self.send_header("Content-Length", "0")
                self.end_headers()

            def log_message(self, *args):
                pass

        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        self.addCleanup(server.shutdown)
        http_module._reset_pacing_for_tests()
        url = f"http://127.0.0.1:{server.server_address[1]}/page.html"
        with self.assertRaises(requests.HTTPError) as raised:
            fetch_text(url, session=build_session(backoff_seconds=0), min_interval=0)
        self.assertEqual(Handler.seen, 1)
        self.assertIn("Not retried", str(raised.exception))
        self.assertNotIn(403, RETRY_STATUSES)


class PacingTests(_BodyServerTest):
    def test_requests_are_spaced_by_the_minimum_interval(self):
        # There was no delay anywhere in this module, and none in any of the
        # 55 candidate_samples.py; the corpus's 495,337 requests went out as
        # fast as the socket allowed.
        url = self.serve(b"labas", "text/html; charset=utf-8")
        interval = 0.05
        started = time.monotonic()
        for _ in range(4):
            fetch_text(url, session=self.session, min_interval=interval)
        elapsed = time.monotonic() - started
        self.assertGreaterEqual(elapsed, interval * 3)

    def test_pacing_holds_for_fetch_bytes_too(self):
        # The documented per-candidate CLI bypasses the bash runner's one
        # `sleep 0.4`, so the floor has to live in the fetchers.
        url = self.serve(b"\xd0\xcf\x11\xe0 a .doc", "application/msword")
        interval = 0.05
        started = time.monotonic()
        for _ in range(3):
            self.assertEqual(fetch_bytes(url, session=self.session, min_interval=interval), b"\xd0\xcf\x11\xe0 a .doc")
        self.assertGreaterEqual(time.monotonic() - started, interval * 2)

    def test_a_zero_interval_does_not_sleep(self):
        url = self.serve(b"labas", "text/html; charset=utf-8")
        started = time.monotonic()
        for _ in range(5):
            fetch_text(url, session=self.session, min_interval=0)
        self.assertLess(time.monotonic() - started, 1.0)


class FetchBytesTests(_BodyServerTest):
    """The first tests `fetch_bytes` has had (issue #136)."""

    DOC = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1" + bytes(range(256))

    def test_a_word_document_comes_back_undecoded(self):
        url = self.serve(self.DOC, "application/msword")
        self.assertEqual(fetch_bytes(url, session=self.session, min_interval=0), self.DOC)

    def test_bytes_are_not_scanned_for_a_challenge_marker(self):
        # A .doc is not HTML; reading it as text to look for markers would be
        # a false positive waiting to happen.
        url = self.serve(self.DOC, "application/msword")
        self.assertEqual(len(fetch_bytes(url, session=self.session, min_interval=0)), len(self.DOC))

    def test_a_truncated_document_is_retried(self):
        url = self.serve(b"y" * 2000, "application/msword", truncate_to=1)
        self.assertEqual(fetch_bytes(url, session=self.session, min_interval=0), b"y" * 2000)
        self.assertEqual(_BodyHandler.attempts, 2)


if __name__ == "__main__":
    unittest.main()
