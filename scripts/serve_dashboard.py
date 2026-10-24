"""Serve the static Astro browser and its existing corpus URLs on loopback.

Build first with `cd frontend && npm ci && npm run build`, then run this script
from any directory. /dashboard/ maps to frontend/dist; the index and field-label
JSON retain their dashboard/ paths. data/, docs/ and portraits/ are the only
other public roots. No source directory or repository listing is served.

The server preserves gzip compression, an mtime-keyed LRU, ETag/Last-Modified,
loopback Host validation and response hardening from issue #160. Build assets
are separate from the root dist/ directory used by data releases.

Caching (issue #186): Astro's content-hashed `/dashboard/_astro/*` files are
`immutable` for a year, and so is a web portrait asked for with its set's
version (`/portraits/<pid>.webp?v=…`, issue #187); everything else (HTML, the index, records, the concept
map) is `no-cache`, kept but revalidated on every load. docs/DASHBOARD.md has
the rules a replacement static server and the Cloudflare zone must keep.
"""

from __future__ import annotations

import gzip
import hashlib
import os
import sys
from collections import OrderedDict
from email.utils import formatdate, parsedate_to_datetime
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

DEFAULT_PORT = 8791

#: Worth compressing. Portraits are WebP and stay as they are.
COMPRESSIBLE_SUFFIXES = {".json", ".html", ".tsv", ".csv", ".js", ".css", ".svg", ".txt", ".md"}

#: The only directories the page fetches from: itself, the records it opens
#: per person, the concept map it resolves its comparison rows against, and
#: the web portraits (issue #187) -- a top-level sibling of data/, so its URL
#: stays /portraits/ when #184 moves the page off /dashboard/.
#: Anything else under the repository root is not the dashboard's business.
SERVED_ROOTS = ("dashboard", "data", "docs", "portraits")

#: Hosts a browser reaches a loopback server by. A request naming anything
#: else is a DNS rebind: the name resolves to 127.0.0.1 while the browser
#: still treats the response as that name's origin.
ALLOWED_HOSTS = {"127.0.0.1", "localhost", "[::1]", "::1"}

#: mtime-keyed gzip cache: path -> (mtime, gzipped body). An LRU, so a long
#: browsing session over 113k record files evicts one small entry rather
#: than throwing away the 7 MB `people.json` with everything else.
_CACHE: OrderedDict[str, tuple[float, bytes]] = OrderedDict()
_CACHE_MAX_ENTRIES = 512

#: Astro bundles scripts and styles locally. The dynamic record renderers
#: still use inline styles for chart dimensions. Nothing is fetched remotely.
#: Astro names every bundled file after a hash of its content, so a changed
#: file is a new URL and the old one can be cached forever.
IMMUTABLE_PREFIX = "/dashboard/_astro/"
IMMUTABLE_CACHE_CONTROL = "public, max-age=31536000, immutable"

#: Everything else is rewritten in place: the index after every corpus update,
#: records when a parser gains a field. `no-cache` lets a browser (or edge)
#: keep the copy but never use it without asking, and the answer to that
#: question is a 304 on the unchanged mtime. Not `no-store`, which forced a
#: full 7 MB download of an unchanged index on every visit.
REVALIDATE_CACHE_CONTROL = "no-cache"

#: Web portraits are keyed by pid and rebuilt in place, so the bare URL is
#: revalidated like a record. The page always asks with `?v=<version>`, the
#: hash of the whole portrait set that people.json carries: a changed
#: portrait changes it, so that URL is never reused for other bytes.
PORTRAITS_PREFIX = "/portraits/"


def cache_control(url_path: str) -> str:
    """The Cache-Control a successful response to this URL carries."""
    path, _, query = url_path.split("#", 1)[0].partition("?")
    if path.startswith(IMMUTABLE_PREFIX):
        return IMMUTABLE_CACHE_CONTROL
    if path.startswith(PORTRAITS_PREFIX) and any(p.startswith("v=") and len(p) > 2 for p in query.split("&")):
        return IMMUTABLE_CACHE_CONTROL
    return REVALIDATE_CACHE_CONTROL


CONTENT_SECURITY_POLICY = (
    "default-src 'self'; script-src 'self'; "
    "style-src 'self' 'unsafe-inline'; img-src 'self' data:; "
    "connect-src 'self'; base-uri 'none'; form-action 'none'"
)


def _gzipped(path: Path) -> bytes:
    key = str(path)
    mtime = path.stat().st_mtime
    hit = _CACHE.get(key)
    if hit and hit[0] == mtime:
        _CACHE.move_to_end(key)
        return hit[1]
    body = gzip.compress(path.read_bytes(), compresslevel=6)
    _CACHE[key] = (mtime, body)
    _CACHE.move_to_end(key)
    while len(_CACHE) > _CACHE_MAX_ENTRIES:
        _CACHE.popitem(last=False)
    return body


def _is_served(translated: Path, root: Path) -> bool:
    """Is this path inside one of the directories the page fetches?

    Compared *lexically*, not through `Path.resolve()`, and against
    `os.getcwd()` — the base `translate_path` itself joins against. `data/`
    is a directory of symlinks on the machine that scraped the corpus and
    `dashboard/people.json` is one too, so resolving would put every record
    fetch outside the root and refuse it; and resolving only one side breaks
    wherever the cwd crosses a symlink, which on macOS is every temporary
    directory. Both were caught by driving the real dashboard and the tests
    rather than by reading the code.

    Traversal is still blocked upstream:
    `SimpleHTTPRequestHandler.translate_path` discards every `..` segment
    before this sees the path, which `test_traversal_stays_blocked` holds.
    """
    normalized = os.path.normpath(str(translated))
    base = os.path.normpath(str(root))
    if normalized == base:
        return True  # the root itself, which redirects
    prefix = base.rstrip(os.sep) + os.sep
    if not normalized.startswith(prefix):
        return False
    first = normalized[len(prefix) :].split(os.sep, 1)[0]
    return first in SERVED_ROOTS


class GzipHandler(SimpleHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def translate_path(self, path: str) -> str:
        """Map the established /dashboard/ URL to the Astro output only.

        The generated person index and field labels keep their old paths.
        Normalize with the stdlib before mapping so encoded traversals cannot
        escape the output directory. Source and build configuration are never
        reachable through /frontend/. A missing build must not fall back to
        serving the retired MVP page.
        """
        translated = Path(super().translate_path(path))
        dashboard = Path(self.directory) / "dashboard"
        try:
            relative = translated.relative_to(dashboard)
        except ValueError:
            return str(translated)
        if relative.as_posix() in {"people.json", "field-labels.json"}:
            return str(translated)
        return str(Path(self.directory) / "frontend" / "dist" / relative)

    def log_message(self, fmt: str, *args: object) -> None:
        # One line per request, without the stock double-quoting noise.
        sys.stderr.write(f"{self.address_string()} {fmt % args}\n")

    def _refuse(self, code: int, why: str) -> None:
        self.send_error(code, why)

    def _guard(self) -> bool:
        """True when the request may be served at all."""
        host = (self.headers.get("Host") or "").rsplit(":", 1)[0].strip("[]")
        if host and host not in {h.strip("[]") for h in ALLOWED_HOSTS}:
            self._refuse(403, "This server answers loopback names only")
            return False
        # The base is `os.getcwd()` because that is what `translate_path`
        # itself joins against; anything else and the two disagree the moment
        # either path crosses a symlink (macOS's /var -> /private/var, for
        # one).
        # Guard the normalized public URL, not its internal Astro destination.
        # Otherwise allowing frontend/dist would also expose it at /frontend/.
        translated = Path(super().translate_path(self.path))
        if not _is_served(translated, Path(os.getcwd())):
            self._refuse(
                403,
                "Only " + ", ".join(f"{name}/" for name in SERVED_ROOTS) + " are served",
            )
            return False
        return True

    def list_directory(self, path):  # noqa: ANN001, ANN201 - stdlib signature
        # The stock server indexes a directory with no index.html. Nothing the
        # page fetches is a directory, and a listing of `data/` names 55
        # elections and of `dashboard/` the gitignored review CSV.
        self._refuse(404, "No directory listing")
        return None

    def send_response(self, code: int, message: str | None = None) -> None:
        self._status = code
        super().send_response(code, message)

    def end_headers(self) -> None:
        # Only a 200 or a 304 is cacheable. An error under `_astro/` marked
        # immutable would pin a missing-asset 404 at the edge for a year, and
        # the redirects are cheap enough to ask for every time.
        if getattr(self, "_status", None) in (200, 304):
            self.send_header("Cache-Control", cache_control(self.path))
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Content-Security-Policy", CONTENT_SECURITY_POLICY)
        self.send_header("Referrer-Policy", "no-referrer")
        super().end_headers()

    def _redirect_directory(self, translated: Path) -> bool:
        """301 to `path/` for a directory asked for without the slash.

        The stock server does this and the gzip branch used to bypass it by
        rewriting to `index.html` in place — which served the page under a
        base URL one level too high, so its first fetch 404'd and it blamed
        the user's working directory (issue #160).
        """
        parts = self.path.split("?", 1)
        if not translated.is_dir() or parts[0].endswith("/"):
            return False
        self.send_response(301)
        self.send_header("Location", parts[0] + "/" + ("?" + parts[1] if len(parts) > 1 else ""))
        self.send_header("Content-Length", "0")
        self.end_headers()
        return True

    def do_HEAD(self) -> None:  # noqa: N802 - stdlib naming
        if self._guard():
            super().do_HEAD()

    def do_GET(self) -> None:  # noqa: N802 - stdlib naming
        if self.path.split("?", 1)[0] in ("", "/"):
            # The root is not served, and it is the one thing a person types.
            self.send_response(302)
            self.send_header("Location", "/dashboard/")
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        if not self._guard():
            return
        translated = Path(self.translate_path(self.path))
        if self._redirect_directory(translated):
            return
        path = translated / "index.html" if translated.is_dir() else translated
        if not (
            path.is_file()
            and path.suffix.lower() in COMPRESSIBLE_SUFFIXES
            and "gzip" in self.headers.get("Accept-Encoding", "")
        ):
            super().do_GET()
            return

        mtime = path.stat().st_mtime
        body = _gzipped(path)
        etag = f'W/"{hashlib.blake2s(body, digest_size=8).hexdigest()}"'
        last_modified = formatdate(mtime, usegmt=True)
        if self._not_modified(etag, mtime):
            self.send_response(304)
            self.send_header("ETag", etag)
            self.send_header("Last-Modified", last_modified)
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        self.send_response(200)
        self.send_header("Content-Type", self.guess_type(str(path)))
        self.send_header("Content-Encoding", "gzip")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("ETag", etag)
        self.send_header("Last-Modified", last_modified)
        self.end_headers()
        self.wfile.write(body)

    def _not_modified(self, etag: str, mtime: float) -> bool:
        # RFC 9110 13.2.2: an If-None-Match decides alone. Behind Cloudflare
        # the ETag often never reaches the browser (it is dropped when the edge
        # recompresses to brotli), so If-Modified-Since against the file's
        # mtime is what usually carries the revalidation; the two agree, since
        # the ETag hashes a body keyed on that same mtime.
        # The comparison is the weak one the RFC prescribes for this header, so
        # a proxy that strips the `W/` still matches.
        match = self.headers.get("If-None-Match")
        if match is not None:
            if match.strip() == "*":
                return True
            tags = {tag.strip().removeprefix("W/") for tag in match.split(",")}
            return etag.removeprefix("W/") in tags
        since = self.headers.get("If-Modified-Since")
        if not since:
            return False
        try:
            return parsedate_to_datetime(since).timestamp() >= int(mtime)
        except (TypeError, ValueError):
            return False


def main() -> int:
    # npm's working directory is frontend/; resolving relative to this script
    # makes direct invocation and npm run preview behave identically.
    os.chdir(Path(__file__).resolve().parents[1])
    if not Path("frontend/dist/index.html").is_file():
        print("Astro build not found. Run: cd frontend && npm ci && npm run build", file=sys.stderr)
    if not Path("dashboard/people.json").is_file():
        print("Person index not found. After obtaining the corpus, run: python3 scripts/build_person_index.py", file=sys.stderr)
    port = int(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_PORT
    server = ThreadingHTTPServer(("127.0.0.1", port), GzipHandler)
    print(
        f"Serving {', '.join(name + '/' for name in SERVED_ROOTS)}"
        f" at http://127.0.0.1:{port}/dashboard/ (gzip on; Ctrl-C stops)"
    )
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        return 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
