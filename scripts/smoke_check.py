"""Check that a running vrk site answers like one (issue #188).

    python3 scripts/smoke_check.py https://vrk.viespirkiai.org
    python3 scripts/smoke_check.py http://127.0.0.1:8791

Usable against any base URL: production, or `scripts/serve_dashboard.py`
locally. It needs Python 3.8+ and nothing else, so it runs on the server as
it is.

What it asks, each a pass or a failure:

- `/` is 200 HTML with the security headers, and the `/_astro/` files it
  links are 200 and `immutable` -- the page without its bundle is #183's
  failure, which a status check on `/` alone does not see.
- `/people-version.json` is 200 `no-cache` JSON naming the index's build and
  the hash of each half; `/people-list.json?v=<hash>` and
  `/people-details.json?v=<hash>` are 200, compressed when asked, `immutable`
  (the server checks `v` against the file it holds, so a mismatch here means
  the version file and the files disagree), parse, and carry that build.
- One record from the index (the first person with a portrait, their newest
  candidacy) is 200 and parses; `--record` names another.
- That person's portrait, `/portraits/<pid>.webp?v=<version>`, is 200
  `image/webp` and `immutable`.
- Their page, `/asmuo/<slug>-<pid>`, and `/suvestine` answer with the page.
- `/field-labels.json` and `/docs/concept-map.json` are 200 JSON.
- `/dashboard/`, `/scripts/`, `/.git/` and a mistyped asset are 404.

Exit 0 when every check passes, 1 otherwise; each check prints one line.
"""

from __future__ import annotations

import argparse
import gzip
import json
import re
import sys
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from typing import Dict, List, Optional, Tuple

IMMUTABLE = "immutable"
NO_CACHE = "no-cache"
SECURITY_HEADERS = ("content-security-policy", "x-content-type-options", "referrer-policy")
MUST_404 = ("/dashboard/", "/scripts/", "/.git/", "/.git/config", "/_astro/no-such-asset.js", "/data/")


class Response:
    def __init__(self, status: int, headers: Dict[str, str], body: bytes) -> None:
        self.status = status
        self.headers = headers
        self.body = body

    def header(self, name: str) -> str:
        return self.headers.get(name.lower(), "")

    def text(self) -> str:
        return self.decoded().decode("utf-8", "replace")

    def decoded(self) -> bytes:
        encoding = self.header("content-encoding")
        if encoding == "gzip":
            return gzip.decompress(self.body)
        if encoding in ("", "identity"):
            return self.body
        raise ValueError(f"cannot decode Content-Encoding {encoding!r}")


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):  # noqa: ANN002, ANN003, ANN201
        return None


_OPENER = urllib.request.build_opener(_NoRedirect)


def fetch(base: str, path: str, gzip_ok: bool = False, timeout: float = 30.0) -> Response:
    request = urllib.request.Request(base.rstrip("/") + path, headers={"User-Agent": "vrk-smoke-check/1"})
    request.add_header("Accept-Encoding", "gzip" if gzip_ok else "identity")
    try:
        with _OPENER.open(request, timeout=timeout) as response:
            return Response(response.status, {k.lower(): v for k, v in response.headers.items()}, response.read())
    except urllib.error.HTTPError as error:
        return Response(error.code, {k.lower(): v for k, v in error.headers.items()}, error.read() or b"")


def name_slug(name: str) -> str:
    """routes.js `nameSlug`: "Birutė VĖSAITĖ" -> "birute-vesaite"."""
    text = unicodedata.normalize("NFD", name or "")
    text = "".join(ch for ch in text if not ("̀" <= ch <= "ͯ")).lower()
    return re.sub(r"[^a-z0-9]+", "-", text).strip("-")


def person_path(person: dict) -> str:
    slug = name_slug(person.get("n", ""))
    return "/asmuo/" + (slug + "-" if slug else "") + urllib.parse.quote(person["pid"], safe="")


def record_path(candidacy: dict) -> str:
    """records.js `recordFile`."""
    return f"/data/{candidacy['id']}/{candidacy['c']}-{candidacy['id']}.json"


class Checker:
    def __init__(self, base: str) -> None:
        self.base = base
        self.failures: List[str] = []

    def check(self, label: str, ok: bool, detail: str = "") -> bool:
        print(f"{'ok  ' if ok else 'FAIL'}  {label}" + (f"  ({detail})" if detail else ""), flush=True)
        if not ok:
            self.failures.append(label)
        return ok

    def get(self, path: str, gzip_ok: bool = False) -> Optional[Response]:
        try:
            return fetch(self.base, path, gzip_ok)
        except (urllib.error.URLError, OSError, ValueError) as error:
            self.check(f"GET {path}", False, str(error))
            return None

    def expect(self, path: str, status: int = 200, content_type: str = "", cache: str = "", gzip_ok: bool = False) -> Optional[Response]:
        response = self.get(path, gzip_ok)
        if response is None:
            return None
        problems = []
        if response.status != status:
            problems.append(f"status {response.status}, expected {status}")
        if status == 200 and content_type and not response.header("content-type").startswith(content_type):
            problems.append(f"Content-Type {response.header('content-type')!r}, expected {content_type}")
        if status == 200 and cache and cache not in response.header("cache-control"):
            problems.append(f"Cache-Control {response.header('cache-control')!r}, expected {cache}")
        self.check(f"GET {path} -> {status}" + (f" {content_type}" if content_type else ""), not problems, "; ".join(problems))
        # A wrong header is reported, and the body is still checked.
        return response if response.status == status else None

    def json(self, path: str, response: Optional[Response]) -> Optional[object]:
        if response is None:
            return None
        try:
            value = json.loads(response.decoded())
        except (ValueError, OSError) as error:
            self.check(f"{path} parses as JSON", False, str(error))
            return None
        return value


def join_people(listing: dict, details: dict) -> dict:
    """Enough of person_index_files.join_index to pick a record: `id` and `c`.

    Not an import of it: this script runs on the server with Python and
    nothing else.
    """
    elections = listing.get("elections") or []
    people = []
    for entry, rows in zip(listing.get("people") or [], details.get("people") or []):
        e = [dict(row, id=elections[c["ei"]]["id"]) for c, row in zip(entry.get("e") or [], rows)]
        people.append(dict(entry, e=e))
    return {"portraits": listing.get("portraits"), "people": people}


def pick_person(index: dict, record: Optional[str]) -> Tuple[Optional[dict], Optional[dict]]:
    """The person and candidacy to probe: `--record`'s, or the first with a portrait."""
    people = index.get("people") or []
    for person in people:
        for candidacy in person.get("e") or []:
            if record and record_path(candidacy) == record:
                return person, candidacy
    if record:
        return None, None
    with_portrait = [person for person in people if person.get("ph") and person.get("e")]
    person = (with_portrait or [p for p in people if p.get("e")] or [None])[0]
    return person, (person["e"][-1] if person else None)


def run(base: str, record: Optional[str] = None) -> int:
    c = Checker(base)
    print(f"smoke check: {base}")

    page = c.expect("/", 200, "text/html", NO_CACHE)
    if page is not None:
        missing = [h for h in SECURITY_HEADERS if not page.header(h)]
        c.check("security headers on /", not missing, "missing " + ", ".join(missing) if missing else "")
        assets = sorted(set(re.findall(r'(?:src|href)="(/_astro/[^"]+)"', page.text())))
        c.check("/ links its /_astro/ bundle", bool(assets), "" if assets else "no /_astro/ script or stylesheet in the HTML")
        for asset in assets:
            c.expect(asset, 200, cache=IMMUTABLE)

    version = c.json("/people-version.json", c.expect("/people-version.json", 200, "application/json", NO_CACHE, gzip_ok=True))
    halves: Dict[str, dict] = {}
    if isinstance(version, dict):
        for half in ("list", "details"):
            path = f"/people-{half}.json?v={urllib.parse.quote(str(version.get(half, '')))}"
            response = c.expect(path, 200, "application/json", IMMUTABLE, gzip_ok=True)
            if response is not None:
                c.check(f"{path} is compressed when asked", response.header("content-encoding") in ("gzip", "br", "zstd"), response.header("content-encoding") or "sent uncompressed")
            value = c.json(path, response)
            if isinstance(value, dict):
                halves[half] = value
                c.check(f"{path} is build {version.get('build')}", value.get("build") == version.get("build"), f"it says {value.get('build')!r}")
    index = None
    if len(halves) == 2:
        index = join_people(halves["list"], halves["details"])
        people = index["people"]
        c.check("the index lists people", bool(people), f"{len(people)} people")
        c.check(
            "list and details align",
            len(halves["list"].get("people") or []) == len(halves["details"].get("people") or []),
        )
    for path in ("/field-labels.json", "/docs/concept-map.json"):
        c.json(path, c.expect(path, 200, "application/json", NO_CACHE, gzip_ok=True))

    person, candidacy = pick_person(index, record) if isinstance(index, dict) else (None, None)
    if record and candidacy is None:
        c.check(f"{record} is a candidacy in the index", False)
    if candidacy is not None:
        path = record_path(candidacy)
        value = c.json(path, c.expect(path, 200, "application/json", NO_CACHE, gzip_ok=True))
        if value is not None:
            c.check(f"{path} is the record it names", isinstance(value, dict) and value.get("electionId") == candidacy["id"])
    if person is not None and person.get("ph"):
        version = (index.get("portraits") or {}).get("v", "")
        path = f"/portraits/{urllib.parse.quote(person['pid'], safe='')}.webp" + (f"?v={urllib.parse.quote(version)}" if version else "")
        portrait = c.expect(path, 200, "image/webp", IMMUTABLE if version else NO_CACHE)
        if portrait is not None:
            c.check(f"{path} is a WebP", portrait.body[:4] == b"RIFF" and portrait.body[8:12] == b"WEBP")
    elif person is not None:
        c.check("the index flags portraits (ph)", False, "no person has ph: 1; were the portraits built?")
    if person is not None:
        for path in (person_path(person), "/suvestine"):
            routed = c.expect(path, 200, "text/html", NO_CACHE)
            if routed is not None and page is not None:
                c.check(f"{path} answers with the page", routed.text() == page.text())

    for path in MUST_404:
        c.expect(path, 404)

    if c.failures:
        print(f"\n{len(c.failures)} check(s) failed against {base}", file=sys.stderr)
        return 1
    print(f"\nall checks passed against {base}")
    return 0


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("base_url", help="e.g. https://vrk.viespirkiai.org or http://127.0.0.1:8791")
    parser.add_argument("--record", help="record URL path to probe, e.g. /data/2019-prezidento/gitanas-nauseda-2019-prezidento.json")
    args = parser.parse_args(argv)
    return run(args.base_url, args.record)


if __name__ == "__main__":
    raise SystemExit(main())
