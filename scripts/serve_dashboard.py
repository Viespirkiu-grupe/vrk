"""Serve the static Astro browser and its existing corpus URLs on loopback.

Build first with `cd frontend && npm ci && npm run build`, then run this script
from any directory. The site root `/` is frontend/dist (issue #184); the index
(`/people-version.json`, `/people-list.json`, `/people-details.json`) and
`/field-labels.json` are served beside the page from where the builders write
them, `dashboard/`. Besides
those, only data/, portraits/ and docs/concept-map.json are reachable. The
page's own routes (`/asmuo/<pid>`, `/suvestine`, …; see `ROUTE_PATHS`) answer
with the built index.html, which routes on the client. Every other URL
resolves inside the build, so no source directory, repository file or listing
is served.

The server sends a precompressed `.br` or `.gz` copy where the builder left
one beside the file and the client accepts it, else gzips on the fly into an
mtime-keyed LRU; it keeps ETag/Last-Modified,
loopback Host validation and response hardening from issue #160. Build assets
are separate from the root dist/ directory used by data releases.

Caching (issue #186): Astro's content-hashed `/_astro/*` files are
`immutable` for a year, and so is a web portrait asked for with its set's
version (`/portraits/<pid>.webp?v=…`, issue #187), and so is the index's list
or details file asked for with `?v=` equal to the hash of what is on disk now
(step 2 of #186); everything else (HTML, the version file, records, the
concept map, and an index file asked for with any other `v`) is `no-cache`,
kept but revalidated on every load. docs/DASHBOARD.md has the rules, and
docs/DEPLOY.md the Cloudflare cache rules production needs beside them.
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

#: Repository directories served under their own name: the records the page
#: opens per person and the web portraits (issue #187).
SERVED_ROOTS = ("data", "portraits")

#: Single repository files served at their own path. Of docs/ the page reads
#: only the concept map it resolves its comparison rows against.
SERVED_FILES = ("docs/concept-map.json",)

#: The generated person index and field labels. Every builder and release
#: script writes them to `dashboard/` (gitignored for the index), so they stay
#: there on disk and are served at the root, beside the page that fetches them
#: (issue #184).
INDEX_DIR = "dashboard"
INDEX_FILES = ("people-version.json", "people-list.json", "people-details.json", "field-labels.json")

#: The two index files the page asks for with `?v=<content hash>`, the hash
#: people-version.json names (scripts/person_index_files.py). Such a URL is
#: immutable only while `v` is the hash of the file on disk: a request that
#: lands mid-deploy, with the old version file's hash and the new file's
#: bytes, must not be pinned at the edge for a year under the old name.
VERSIONED_FILES = ("people-list.json", "people-details.json")

#: Copies a builder wrote beside a file, most preferred first, by the
#: Accept-Encoding token that admits them.
PRECOMPRESSED = (("br", ".br"), ("gzip", ".gz"))

#: The Astro output. Every URL not listed above resolves inside it, which is
#: what keeps the rest of the repository (frontend/, scripts/, .git/, …) out
#: of reach: `/scripts/x.py` asks for frontend/dist/scripts/x.py and 404s.
BUILD_DIR = os.path.join("frontend", "dist")

#: The page's client-side routes (issue #184): each view has its own URL, so
#: a shared link opens straight into it. The server answers them with the
#: page itself and the page's router picks the view. Exact paths, with or
#: without a trailing slash, and two prefixes that carry a key: a person's
#: `<slug>-<pid>` and a comparison's `<pid>,<pid>,…`. Nothing else falls
#: back, so a mistyped asset URL is still a 404 rather than an HTML page.
#: frontend/src/lib/routes.js is the other half and must list the same.
ROUTE_PATHS = ("/suvestine", "/iskelejai", "/apreptis", "/pokyciai", "/partiju-keitimai")
ROUTE_PREFIXES = ("/asmuo/", "/palyginti/")


def is_route(url_path: str) -> bool:
    """Is this URL one of the page's own routes, answered with index.html?"""
    path = url_path.split("#", 1)[0].split("?", 1)[0]
    return path.rstrip("/") in ROUTE_PATHS or any(
        path.startswith(prefix) and "/" not in path[len(prefix) :].rstrip("/")
        for prefix in ROUTE_PREFIXES
    )

#: Anything else under the repository root is not the dashboard's business.

#: Hosts a browser reaches a loopback server by. A request naming anything
#: else is a DNS rebind: the name resolves to 127.0.0.1 while the browser
#: still treats the response as that name's origin.
ALLOWED_HOSTS = {"127.0.0.1", "localhost", "[::1]", "::1"}

#: mtime-keyed gzip cache: path -> (mtime, gzipped body). An LRU, so a long
#: browsing session over 113k record files evicts one small entry rather
#: than throwing away the compressed index with everything else.
_CACHE: OrderedDict[str, tuple[float, bytes]] = OrderedDict()
_CACHE_MAX_ENTRIES = 512

#: Astro bundles scripts and styles locally. The dynamic record renderers
#: still use inline styles for chart dimensions. Nothing is fetched remotely.
#: Astro names every bundled file after a hash of its content, so a changed
#: file is a new URL and the old one can be cached forever.
IMMUTABLE_PREFIX = "/_astro/"
IMMUTABLE_CACHE_CONTROL = "public, max-age=31536000, immutable"

#: Everything else is rewritten in place: the index after every corpus update,
#: records when a parser gains a field. `no-cache` lets a browser (or edge)
#: keep the copy but never use it without asking, and the answer to that
#: question is a 304 on the unchanged mtime. Not `no-store`, which forced a
#: full 7 MB download of an unchanged index on every visit.
REVALIDATE_CACHE_CONTROL = "no-cache"

#: Web portraits are keyed by pid and rebuilt in place, so the bare URL is
#: revalidated like a record. The page always asks with `?v=<version>`, the
#: hash of the whole portrait set that the index carries: a changed
#: portrait changes it, so that URL is never reused for other bytes.
PORTRAITS_PREFIX = "/portraits/"


def _query_version(query: str) -> str:
    return next((p[2:] for p in query.split("&") if p.startswith("v=")), "")


def is_versioned(url_path: str) -> bool:
    """Is this one of the index files whose `?v=` can make it immutable?"""
    path = url_path.split("#", 1)[0].split("?", 1)[0]
    return path.lstrip("/") in VERSIONED_FILES


def cache_control(url_path: str, current: str | None = None) -> str:
    """The Cache-Control a successful response to this URL carries.

    `current` is the content hash of the file a versioned index URL names;
    without it, or with a `v` that is not it, the answer is `no-cache`.
    """
    path, _, query = url_path.split("#", 1)[0].partition("?")
    if path.startswith(IMMUTABLE_PREFIX):
        return IMMUTABLE_CACHE_CONTROL
    if path.startswith(PORTRAITS_PREFIX) and _query_version(query):
        return IMMUTABLE_CACHE_CONTROL
    if is_versioned(path) and current and _query_version(query) == current:
        return IMMUTABLE_CACHE_CONTROL
    return REVALIDATE_CACHE_CONTROL


#: path -> ((mtime_ns, size), hash): the `?v=` of each versioned file, the
#: same blake2s scripts/person_index_files.content_hash writes.
_HASHES: dict[str, tuple[tuple[int, int], str]] = {}


def content_hash(path: Path) -> str | None:
    try:
        stat = path.stat()
    except OSError:
        return None
    key = (stat.st_mtime_ns, stat.st_size)
    hit = _HASHES.get(str(path))
    if hit and hit[0] == key:
        return hit[1]
    digest = hashlib.blake2s(path.read_bytes(), digest_size=8).hexdigest()
    _HASHES[str(path)] = (key, digest)
    return digest


def accepted_encodings(header: str) -> set[str]:
    """The content codings an Accept-Encoding admits (`q=0` refuses one)."""
    accepted = set()
    for item in header.split(","):
        token, _, params = item.strip().partition(";")
        q = params.strip()
        if q.startswith("q="):
            try:
                if float(q[2:]) == 0:
                    continue
            except ValueError:
                continue
        if token.strip():
            accepted.add(token.strip().lower())
    return accepted


def precompressed(path: Path, accepted: set[str]) -> tuple[str, Path] | None:
    """The builder's copy to send for `path`, or None to compress here.

    Only a copy whose mtime is not older than the file's: the index build
    gives each the original's mtime, so an older one is from a previous
    build of a file that has since been rewritten.
    """
    try:
        mtime = path.stat().st_mtime
    except OSError:
        return None
    for coding, suffix in PRECOMPRESSED:
        if coding not in accepted:
            continue
        sibling = path.with_name(path.name + suffix)
        try:
            if sibling.is_file() and sibling.stat().st_mtime >= mtime:
                return coding, sibling
        except OSError:
            continue
    return None


CONTENT_SECURITY_POLICY = (
    "default-src 'self'; script-src 'self'; "
    "style-src 'self' 'unsafe-inline'; img-src 'self' data:; "
    "connect-src 'self'; base-uri 'none'; form-action 'none'"
)


def _gzipped(path: Path) -> bytes:
    return _cached(path, lambda: gzip.compress(path.read_bytes(), compresslevel=6))


def _read(path: Path) -> bytes:
    """A precompressed copy, held in the same LRU as what is gzipped here."""
    return _cached(path, path.read_bytes)


def _cached(path: Path, make) -> bytes:  # noqa: ANN001 - a zero-argument callable
    key = str(path)
    mtime = path.stat().st_mtime
    hit = _CACHE.get(key)
    if hit and hit[0] == mtime:
        _CACHE.move_to_end(key)
        return hit[1]
    body = make()
    _CACHE[key] = (mtime, body)
    _CACHE.move_to_end(key)
    while len(_CACHE) > _CACHE_MAX_ENTRIES:
        _CACHE.popitem(last=False)
    return body


def _is_served(translated: Path, root: Path) -> bool:
    """Is this the destination of a public URL, as `translate_path` maps them?

    A second check on what `translate_path` produced, so a mapping mistake
    there fails closed rather than handing out a repository file.

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
    prefix = base.rstrip(os.sep) + os.sep
    if not normalized.startswith(prefix):
        return False
    relative = normalized[len(prefix) :]
    build = os.path.normpath(BUILD_DIR)
    if relative == build or relative.startswith(build + os.sep):
        return True
    if relative.split(os.sep, 1)[0] in SERVED_ROOTS:
        return True
    files = {os.path.normpath(name) for name in SERVED_FILES}
    files |= {os.path.join(INDEX_DIR, name) for name in INDEX_FILES}
    return relative in files


class GzipHandler(SimpleHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def translate_path(self, path: str) -> str:
        """Map a public URL to the file it names (issue #184).

        `data/…` and `portraits/…` are their repository directories,
        `/docs/concept-map.json` its file, the index files and
        `/field-labels.json` the generated files in `dashboard/`, and a
        page route (`is_route`) the built index.html. Everything else is the
        Astro output, so `/` is the page and a source path such as
        `/frontend/src/…` or `/scripts/…` is looked up inside the build and
        is not found. The stdlib normalizes first, so encoded traversals cannot
        escape. A missing build must not fall back to serving the retired MVP
        page in `dashboard/`, and it cannot: that directory is not a root.
        """
        root = Path(self.directory)
        if is_route(path):
            return str(root / BUILD_DIR / "index.html")
        translated = Path(super().translate_path(path))
        relative = translated.relative_to(root)
        name = relative.as_posix()
        if relative.parts[:1] and relative.parts[0] in SERVED_ROOTS or name in SERVED_FILES:
            return str(translated)
        if name in INDEX_FILES:
            return str(root / INDEX_DIR / name)
        return str(root / BUILD_DIR / relative)

    def log_message(self, fmt: str, *args: object) -> None:
        # One line per request, without the stock double-quoting noise.
        sys.stderr.write(f"{self.address_string()} {fmt % args}\n")

    def _refuse(self, code: int, why: str) -> None:
        self.send_error(code, why)

    def _guard(self) -> bool:
        """True when the request may be served; otherwise it is answered."""
        host = (self.headers.get("Host") or "").rsplit(":", 1)[0].strip("[]")
        if host and host not in {h.strip("[]") for h in ALLOWED_HOSTS}:
            self._refuse(403, "This server answers loopback names only")
            return False
        # The base is `os.getcwd()` because that is what `translate_path`
        # itself joins against; anything else and the two disagree the moment
        # either path crosses a symlink (macOS's /var -> /private/var, for
        # one).
        if not _is_served(Path(self.translate_path(self.path)), Path(os.getcwd())):
            self._refuse(403, "Only the site, data/, portraits/ and the index are served")
            return False
        return True

    def list_directory(self, path):  # noqa: ANN001, ANN201 - stdlib signature
        # The stock server indexes a directory with no index.html. Nothing the
        # page fetches is a directory, and a listing of `data/` names 55
        # elections.
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
            current = content_hash(Path(self.translate_path(self.path))) if is_versioned(self.path) else None
            self.send_header("Cache-Control", cache_control(self.path, current))
            # The body depends on Accept-Encoding for everything this server
            # compresses, so a shared cache must key on it.
            served = Path(self.translate_path(self.path))
            if (served / "index.html" if served.is_dir() else served).suffix.lower() in COMPRESSIBLE_SUFFIXES:
                self.send_header("Vary", "Accept-Encoding")
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
        if not self._guard():
            return
        translated = Path(self.translate_path(self.path))
        if self._redirect_directory(translated):
            return
        path = translated / "index.html" if translated.is_dir() else translated
        accepted = accepted_encodings(self.headers.get("Accept-Encoding", ""))
        compressible = path.is_file() and path.suffix.lower() in COMPRESSIBLE_SUFFIXES
        ready = precompressed(path, accepted) if compressible else None
        if ready:
            coding, sibling = ready
            body = _read(sibling)
        elif compressible and "gzip" in accepted:
            coding, body = "gzip", _gzipped(path)
        else:
            super().do_GET()
            return

        mtime = path.stat().st_mtime
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
        self.send_header("Content-Encoding", coding)
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
    if not Path("dashboard/people-list.json").is_file():
        print("Person index not found. After obtaining the corpus, run: python3 scripts/build_person_index.py", file=sys.stderr)
    port = int(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_PORT
    server = ThreadingHTTPServer(("127.0.0.1", port), GzipHandler)
    print(
        f"Serving the site, the index and {', '.join(name + '/' for name in SERVED_ROOTS)}"
        f" at http://127.0.0.1:{port}/ (br/gzip on; Ctrl-C stops)"
    )
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        return 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
