"""Serve the repo root for the dashboard, gzip-compressing what compresses.

`python3 -m http.server` works, but it sends `dashboard/people.json` — 28 MB
of JSON that gzips 4.7× — uncompressed on every load, and the page fetches it
`no-store` on purpose (a stale cached index quietly disagrees with the corpus
on disk). This is the same stdlib server with one addition: a text response
is gzipped when the client accepts it, cached in memory keyed on the file's
mtime so a reload after a corpus rebuild re-compresses and one during a
session does not.

Run from the repo root:

    python3 scripts/serve_dashboard.py [port]

and open http://127.0.0.1:8791/dashboard/. Everything the page needs —
dashboard/, data/, docs/concept-map.json — is under the served root, which is
why the server must run from the repo root; it refuses to start anywhere else
rather than serve a dashboard whose every record fetch would 404.
"""

from __future__ import annotations

import gzip
import sys
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

DEFAULT_PORT = 8791

#: Worth compressing. Photos are JPEGs and stay as they are.
COMPRESSIBLE_SUFFIXES = {".json", ".html", ".tsv", ".csv", ".js", ".css", ".svg", ".txt", ".md"}

#: mtime-keyed gzip cache: path -> (mtime, gzipped body). Bounded so a long
#: browsing session over 113k record files cannot grow it without limit.
_CACHE: dict[str, tuple[float, bytes]] = {}
_CACHE_MAX_ENTRIES = 512


def _gzipped(path: Path) -> bytes:
    key = str(path)
    mtime = path.stat().st_mtime
    hit = _CACHE.get(key)
    if hit and hit[0] == mtime:
        return hit[1]
    body = gzip.compress(path.read_bytes(), compresslevel=6)
    if len(_CACHE) >= _CACHE_MAX_ENTRIES:
        _CACHE.clear()
    _CACHE[key] = (mtime, body)
    return body


class GzipHandler(SimpleHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def do_GET(self) -> None:  # noqa: N802 - stdlib naming
        path = Path(self.translate_path(self.path))
        if path.is_dir():
            path = path / "index.html"
        if (
            path.is_file()
            and path.suffix.lower() in COMPRESSIBLE_SUFFIXES
            and "gzip" in self.headers.get("Accept-Encoding", "")
        ):
            body = _gzipped(path)
            self.send_response(200)
            self.send_header("Content-Type", self.guess_type(str(path)))
            self.send_header("Content-Encoding", "gzip")
            self.send_header("Content-Length", str(len(body)))
            # The page's own fetches say no-store; saying it here too keeps
            # any other client honest about the rewritten-in-place corpus.
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)
            return
        super().do_GET()


def main() -> int:
    if not Path("dashboard").is_dir() or not Path("data").is_dir():
        print(
            "No dashboard/ and data/ here — run from the repo root:\n"
            "    python3 scripts/serve_dashboard.py",
            file=sys.stderr,
        )
        return 1
    port = int(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_PORT
    server = ThreadingHTTPServer(("127.0.0.1", port), GzipHandler)
    print(f"Serving the repo root at http://127.0.0.1:{port}/dashboard/ (gzip on; Ctrl-C stops)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        return 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
