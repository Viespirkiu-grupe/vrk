"""Unit tests for the shared HTTP fetcher.

`scraper.shared.http.fetch_text` carries every request the scraper makes to
vrk.lt, so its retry and identification behaviour is pinned here against a
local stdlib HTTP server — no network, no fixtures. The retry tests build
their session with a zero backoff so exercising real urllib3 retries stays
fast.
"""

from __future__ import annotations

import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import requests

from scraper.shared.http import (
    RETRY_STATUSES,
    RETRY_TOTAL,
    USER_AGENT,
    build_session,
    fetch_text,
)


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


if __name__ == "__main__":
    unittest.main()
