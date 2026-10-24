"""A stand-in for deploy/Caddyfile in the tests: serves a built site directory.

The deploy tests need a static server over `site/`'s layout (not the
repository's, which is what scripts/serve_dashboard.py maps), with the
production rules: the route fallback, the two Cache-Control classes on
successes only, the security headers on everything, a precompressed `.gz`
when one sits beside the file, and 404 for directories and dotfiles. The
route regex is read out of deploy/Caddyfile itself, so this cannot route
differently from the real config.

Not a production server; Caddy is (docs/DEPLOY.md).
"""

from __future__ import annotations

import functools
import os
import re
import threading
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
CADDYFILE = REPO_ROOT / "deploy" / "Caddyfile"

CSP = re.search(r'Content-Security-Policy "([^"]+)"', CADDYFILE.read_text(encoding="utf-8")).group(1)
ROUTE = re.compile(re.search(r"@route path_regexp route (\S+)", CADDYFILE.read_text(encoding="utf-8")).group(1))
IMMUTABLE = "public, max-age=31536000, immutable"


class SiteHandler(SimpleHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt: str, *args: object) -> None:
        pass

    def _path(self) -> str:
        return self.path.split("?", 1)[0].split("#", 1)[0]

    def translate_path(self, path: str) -> str:
        if ROUTE.match(self._path()):
            return os.path.join(self.directory, "index.html")
        return super().translate_path(path)

    def list_directory(self, path):  # noqa: ANN001, ANN201
        self.send_error(404)
        return None

    def send_response(self, code: int, message: str | None = None) -> None:
        self._status = code
        super().send_response(code, message)

    def end_headers(self) -> None:
        if getattr(self, "_status", None) in (200, 304):
            path, _, query = self.path.partition("?")
            immutable = path.startswith("/_astro/") or (path.startswith("/portraits/") and re.search(r"(^|&)v=[^&]", query))
            self.send_header("Cache-Control", IMMUTABLE if immutable else "no-cache")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Content-Security-Policy", CSP)
        self.send_header("Referrer-Policy", "no-referrer")
        super().end_headers()

    def guess_type(self, path: str) -> str:
        if os.path.basename(path) == "VERSION":
            return "text/plain; charset=utf-8"
        if path.endswith(".webp"):
            return "image/webp"
        return super().guess_type(path)

    def do_GET(self) -> None:  # noqa: N802
        if any(part.startswith(".") for part in self._path().split("/")):
            self.send_error(404)
            return
        translated = self.translate_path(self.path)
        if os.path.isdir(translated) and self._path() != "/":
            self.send_error(404)
            return
        if os.path.isdir(translated):
            translated = os.path.join(translated, "index.html")
        gz = translated + ".gz"
        if "gzip" in self.headers.get("Accept-Encoding", "") and os.path.isfile(gz):
            body = Path(gz).read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", self.guess_type(translated))
            self.send_header("Content-Encoding", "gzip")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        super().do_GET()


def start(directory: Path) -> tuple[ThreadingHTTPServer, str]:
    """Serve `directory` (a symlink is followed per request) on a free port."""
    server = ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(SiteHandler, directory=str(directory)))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server, f"http://127.0.0.1:{server.server_address[1]}"


# --- a tiny synthetic repository, for build_site.py and everything after ---

PID = "p0123456789ab"
PORTRAIT_VERSION = "abcd1234"
#: The smallest file that passes for a WebP: RIFF, size, WEBP.
WEBP = b"RIFF\x0c\x00\x00\x00WEBPVP8 \x00\x00\x00\x00"
TREASURER_PHONE = "+370 600 00000"


def record(election: str, candidate: str, name: str) -> dict:
    return {
        "electionId": election,
        "candidateId": candidate,
        "candidateName": name,
        "source": {"url": f"https://www.vrk.lt/{candidate}"},
        "rawData": {
            "profile": {"photo": f"photos/{candidate}.jpg"},
            "politinesKampanijosDalyvioDuomenys": {
                "campaigns": [{"treasurer": {"name": "Iždininkė", "phone": TREASURER_PHONE, "email": "izd@example.lt"}}]
            },
        },
        "normalized": {"vardas": name},
    }


def make_repo(root: Path) -> Path:
    """A repository with a built frontend, an index, portraits and two records.

    Inputs are dated in the past and outputs now, so `--frontend verify` and
    `--index auto` find them current.
    """
    import json

    def write(relative: str, content: str | bytes) -> Path:
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        (path.write_bytes if isinstance(content, bytes) else path.write_text)(content)
        return path

    old = 1_700_000_000
    for relative, body in {
        "frontend/package.json": json.dumps({"engines": {"node": ">=22.12.0"}}),
        "frontend/src/pages/index.astro": "---\n---\n",
        "data/2019-prezidento/vardenis-pavardenis-2019-prezidento.json": json.dumps(record("2019-prezidento", "vardenis-pavardenis-2019-prezidento", "Vardenis PAVARDENIS"), indent=2),
        "data/2020-seimo/vardenis-pavardenis-2020-seimo.json": json.dumps(record("2020-seimo", "vardenis-pavardenis-2020-seimo", "Vardenis PAVARDENIS"), indent=2),
        "data/2019-prezidento/anomalies.jsonl": '{"event": "x"}\n',
        "data/2019-prezidento/photos/vardenis-pavardenis-2019-prezidento.jpg": b"\xff\xd8\xff full size",
        "data/2019-prezidento/notes.txt": "not served",
        "docs/concept-map.json": '{"concepts": []}',
    }.items():
        os.utime(write(relative, body), (old, old))
    index = {
        "elections": [{"id": "2019-prezidento"}, {"id": "2020-seimo"}],
        "portraits": {"v": PORTRAIT_VERSION, "n": 1},
        "people": [
            {
                "pid": PID,
                "n": "Vardenis PAVARDENIS",
                "b": "1970-01-01",
                "ph": 1,
                "e": [
                    {"id": "2019-prezidento", "c": "vardenis-pavardenis"},
                    {"id": "2020-seimo", "c": "vardenis-pavardenis"},
                ],
            }
        ],
    }
    write("dashboard/people.json", json.dumps(index, separators=(",", ":")))
    write("dashboard/field-labels.json", json.dumps({"turtas": "Turtas"}))
    write(f"portraits/{PID}.webp", WEBP)
    write("portraits/manifest.json", json.dumps({"version": PORTRAIT_VERSION, "portraits": {PID: {"out": "x", "outBytes": len(WEBP)}}}))
    write(
        "frontend/dist/index.html",
        '<!doctype html><html><head><link rel="stylesheet" href="/_astro/index.abc.css">'
        '<script type="module" src="/_astro/index.abc.js"></script></head><body>'
        + "<p>Kandidatai</p>" * 40 + "</body></html>",
    )
    write("frontend/dist/_astro/index.abc.js", "console.log('page');\n" * 40)
    write("frontend/dist/_astro/index.abc.css", "body { color: #1b313f; }\n" * 40)
    write("frontend/dist/branding/icon.svg", "<svg xmlns='http://www.w3.org/2000/svg'/>")
    return root
