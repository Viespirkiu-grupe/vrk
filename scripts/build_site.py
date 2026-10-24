"""Build the site: one directory whose layout is the public URL layout (issue #188).

vrk.viespirkiai.org serves files from four places, each produced
differently (docs/DEPLOY.md has the table): the Astro build, the generated
index beside it, the records under `data/`, and the web portraits. Until
this script a deploy had to know all four, and the one that did not know the
first served 404s for a day (#183). This writes them into one directory:

    site/
      index.html, _astro/, branding/, fonts/   frontend/dist (built here)
      people.json, field-labels.json           dashboard/ (index built here)
      docs/concept-map.json                    docs/
      data/<election>/<file>.json              data/, record JSON only
      portraits/<pid>.webp                     portraits/ (built here)
      VERSION                                  what this is, see below

Every file in it is served at its own path, so any static server can serve
it (deploy/Caddyfile, deploy/nginx.conf) and production needs neither
Python, Node nor the corpus. `scripts/serve_dashboard.py` stays the local
preview over the repository itself; this is what replaces it in production.

What it does, in order:

1. **The frontend.** `npm ci && npm run build` in `frontend/`, refusing a
   Node older than `package.json`'s `engines` before anything runs.
   `--frontend verify` instead checks that `frontend/dist` exists and is
   newer than every source it is built from.
2. **The index, then the portraits.** `build_person_index.py` (about 35 s)
   when `dashboard/people.json` is older than a record or an input it reads
   (`--index auto`, the default), then `build_web_portraits.py`, which is
   incremental (under a second with nothing to do) and re-stamps the index's
   `ph` flags and portrait version. That order is the one the portrait
   script documents; a second index pass is not needed, since the portrait
   script runs the same stamping pass the index does. The version in the
   index must then equal the portrait manifest's, or the build stops: the
   page would ask for portrait URLs the set does not have.
3. **The records, and only the records.** `data/` also holds the full-size
   `photos/` sidecars (5.2 GB) and each election's `anomalies.jsonl`; the
   page fetches neither. Each record is parsed, passed through the release's
   public profile (`build_distribution.redact_record`, issue #142: the
   campaign treasurer's and auditor's phone and e-mail) and written compact.
   The public profile is the default because it is what production serves
   today: its `data/` was unpacked from a public release. `--profile full`
   ships the records verbatim.
4. **Precompressed copies** (`.gz`, and `.br` when the `brotli` command is
   installed) of the files a visitor always downloads: the page, its
   bundles, the index, the labels and the concept map. A static server sends
   them as they are (`precompressed` in Caddy, `gzip_static` in nginx); the
   per-candidate records are compressed on the fly, since a few KB each is
   cheap to compress and 113,073 more files are not cheap to ship.
5. **`VERSION`**, `key=value` lines: the commit and whether the checkout was
   dirty, the corpus release tag when known (`--corpus-tag`), the build date,
   the profile, and the counts. It is served at `/VERSION`, so an operator
   can ask the live site what it is.

Every output keeps its source's mtime, and the precompressed copies their
original's. A static server's `Last-Modified` and `ETag` are the file's
mtime (and size), so an unchanged record keeps answering 304 across a
redeploy instead of every browser downloading everything again.

The build writes into a staging directory beside `--out` and swaps it in at
the end, so a failed build leaves the previous site as it was.

Run from the repo root:

    python scripts/build_site.py --out site/
    python scripts/build_site.py --out site/ --corpus-tag corpus-2026-10-25
    python scripts/build_site.py --out site/ --tarball dist/vrk-site-2026-10-25.tar.zst

`build_distribution.py --site site/` packs a built site into the release
(`vrk-site-YYYY-MM-DD.tar.zst`, checksummed in MANIFEST.json);
`scripts/deploy.sh` installs one on a server. docs/DEPLOY.md is the whole
path.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tarfile
from concurrent.futures import ProcessPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from scraper.shared import provenance  # noqa: E402

FRONTEND_DIR = Path("frontend")
BUILD_DIR = FRONTEND_DIR / "dist"
INDEX_DIR = Path("dashboard")
INDEX_FILES = ("people.json", "field-labels.json")
DATA_ROOT = Path("data")
PORTRAITS_DIR = Path("portraits")
PORTRAITS_MANIFEST = "manifest.json"
CONCEPT_MAP = Path("docs/concept-map.json")

#: What build_person_index.py reads besides the records. A newer one of these
#: means the index on disk is stale (`--index auto`).
INDEX_INPUTS = (
    Path("scripts/build_person_index.py"),
    Path("scraper/elections.json"),
    Path("scraper/parties.json"),
    Path("scraper/person_overrides.json"),
    CONCEPT_MAP,
)

#: What frontend/dist is built from (`--frontend verify`).
FRONTEND_INPUTS = ("src", "public", "astro.config.mjs", "package.json", "package-lock.json")

#: Precompressed beside themselves: the files every visit downloads. Matched
#: against the path inside the site.
PRECOMPRESS = re.compile(r"^(index\.html|people\.json|field-labels\.json|docs/concept-map\.json|(_astro|branding)/.+\.(js|css|svg))$")

#: Under this, compression is not worth a file (nginx's own gzip_min_length
#: default is 20 bytes; Cloudflare's is 48).
PRECOMPRESS_MIN_BYTES = 256

VERSION_FILE = "VERSION"
PROFILES = ("public", "full")

#: zstd level for the site tarball. 19 compresses the 2 GB of compact JSON to
#: about a tenth in a few minutes on all cores; decompression speed is the
#: same at every level.
ZSTD_LEVEL = 19


class BuildError(SystemExit):
    """A build that cannot go on, with what to do about it."""

    def __init__(self, message: str) -> None:
        super().__init__(f"build_site: {message}")


# --- 1. the frontend -------------------------------------------------------


def _version_tuple(text: str) -> tuple[int, ...]:
    return tuple(int(part) for part in re.findall(r"\d+", text)[:3])


def required_node(frontend: Path) -> tuple[int, ...]:
    """The minimum Node from `engines.node` (only the `>=x.y.z` form is used)."""
    package = json.loads((frontend / "package.json").read_text(encoding="utf-8"))
    spec = (package.get("engines") or {}).get("node", "")
    match = re.fullmatch(r"\s*>=\s*(\d+(?:\.\d+){0,2})\s*", spec)
    if not match:
        raise BuildError(f"frontend/package.json engines.node is {spec!r}; expected a '>=x.y.z' floor")
    return _version_tuple(match.group(1))


def check_node(frontend: Path, node: str = "node") -> str:
    """Refuse a Node below `engines` before npm gets the chance to fail later."""
    need = required_node(frontend)
    try:
        found = subprocess.run([node, "--version"], capture_output=True, text=True, check=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        raise BuildError(
            f"Node.js not found; the frontend build needs Node >= {'.'.join(map(str, need))}"
            " (frontend/package.json engines)."
        ) from None
    if _version_tuple(found) < need:
        raise BuildError(
            f"Node {found} is older than the frontend needs (>= {'.'.join(map(str, need))},"
            " frontend/package.json engines). Install a newer Node, e.g. Node 22 LTS."
        )
    return found


def _newest_mtime(paths: Iterable[Path]) -> tuple[float, Path | None]:
    newest, which = 0.0, None
    for root in paths:
        if not root.exists():
            continue
        files = [root] if root.is_file() else (p for p in root.rglob("*") if p.is_file())
        for path in files:
            mtime = path.stat().st_mtime
            if mtime > newest:
                newest, which = mtime, path
    return newest, which


def build_frontend(repo: Path, mode: str) -> str:
    """`build`: npm ci + npm run build. `verify`: the existing build is current."""
    frontend = repo / FRONTEND_DIR
    index_html = repo / BUILD_DIR / "index.html"
    if mode == "build":
        node = check_node(frontend)
        for command in (["npm", "ci", "--no-audit", "--no-fund"], ["npm", "run", "build"]):
            print(f"$ (cd frontend && {' '.join(command)})", flush=True)
            if subprocess.run(command, cwd=frontend).returncode != 0:
                raise BuildError(f"`{' '.join(command)}` failed in frontend/")
        if not index_html.is_file():
            raise BuildError("npm run build finished but frontend/dist/index.html is missing")
        return node
    if not index_html.is_file():
        raise BuildError(
            "frontend/dist/index.html is missing: the page is a build output, not a"
            " tracked file (#183). Run without --frontend verify, or:"
            " cd frontend && npm ci && npm run build"
        )
    newest, which = _newest_mtime(frontend / name for name in FRONTEND_INPUTS)
    if newest > index_html.stat().st_mtime:
        raise BuildError(
            f"frontend/dist is older than {which.relative_to(repo)}: rebuild it"
            " (cd frontend && npm run build) or run without --frontend verify"
        )
    return "verified"


# --- 2. the index and the portraits ----------------------------------------


def record_paths(data_root: Path) -> list[Path]:
    """Every record: `data/<election>/<file>.json`, one level down, sorted.

    `anomalies.jsonl` and the `photos/` directories are what is left out; so
    is anything else that is not a `.json` file directly in an election's
    directory.
    """
    return sorted(
        path
        for election in data_root.iterdir()
        if election.is_dir() and not election.name.startswith(".")
        for path in election.glob("*.json")
        if path.is_file()
    )


def index_is_stale(repo: Path, records: list[Path]) -> str | None:
    """Why dashboard/people.json needs rebuilding, or None when it is current."""
    index = repo / INDEX_DIR / "people.json"
    if not index.is_file():
        return "dashboard/people.json does not exist"
    built = index.stat().st_mtime
    for path in [repo / p for p in INDEX_INPUTS] + records:
        if path.is_file() and path.stat().st_mtime > built:
            return f"{path.relative_to(repo) if path.is_relative_to(repo) else path} is newer than it"
    return None


def _run_script(repo: Path, script: str, *args: str) -> None:
    command = [sys.executable, str(repo / "scripts" / script), *args]
    print(f"$ python scripts/{script} {' '.join(args)}".rstrip(), flush=True)
    if subprocess.run(command, cwd=repo).returncode != 0:
        raise BuildError(f"scripts/{script} failed; nothing was written to the site")


def build_index_and_portraits(repo: Path, records: list[Path], index_mode: str, portraits_mode: str) -> dict[str, Any]:
    stale = index_is_stale(repo, records)
    if index_mode == "build" or (index_mode == "auto" and stale):
        if stale and index_mode == "auto":
            print(f"index: rebuilding, {stale}")
        _run_script(repo, "build_person_index.py")
    elif stale:
        print(f"index: reusing although {stale} (--index reuse)")
    else:
        print("index: dashboard/people.json is current")
    if portraits_mode == "build":
        _run_script(repo, "build_web_portraits.py")

    for name in INDEX_FILES:
        if not (repo / INDEX_DIR / name).is_file():
            raise BuildError(f"{INDEX_DIR / name} is missing")
    index = json.loads((repo / INDEX_DIR / "people.json").read_text(encoding="utf-8"))
    manifest_path = repo / PORTRAITS_DIR / PORTRAITS_MANIFEST
    if not manifest_path.is_file():
        raise BuildError("portraits/manifest.json is missing: run scripts/build_web_portraits.py")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    stamped = (index.get("portraits") or {}).get("v")
    if stamped != manifest.get("version"):
        raise BuildError(
            f"dashboard/people.json carries portrait version {stamped!r}, portraits/ is"
            f" {manifest.get('version')!r}: the page would ask for URLs the set does not"
            " have. Run scripts/build_web_portraits.py after the index."
        )
    flagged = sum(1 for person in index.get("people", []) if person.get("ph"))
    listed = manifest.get("portraits") or {}
    if flagged != len(listed):
        raise BuildError(f"the index flags {flagged} portrait(s), portraits/manifest.json lists {len(listed)}")
    return {"people": len(index.get("people", [])), "portraits": len(listed), "portraitsVersion": manifest["version"]}


# --- 3. the records --------------------------------------------------------


def _copy_mtime(source: Path, target: Path) -> None:
    stat = source.stat()
    os.utime(target, ns=(stat.st_atime_ns, stat.st_mtime_ns))


def _write_records(job: tuple[list[str], str, str, bool]) -> tuple[int, int, int, list[str]]:
    """One election's records into the site. Runs in a worker process."""
    sources, out_dir, profile, minify = job
    import build_distribution  # noqa: PLC0415 - heavy, and only workers need it

    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    read = written = removed = 0
    problems: list[str] = []
    for name in sources:
        source = Path(name)
        raw = source.read_bytes()
        read += len(raw)
        try:
            record = json.loads(raw)
        except json.JSONDecodeError as error:
            problems.append(f"{source}: not JSON ({error})")
            continue
        if not isinstance(record, dict) or "candidateId" not in record or "electionId" not in record:
            problems.append(f"{source}: not a candidate record (no electionId/candidateId)")
            continue
        if profile == "public":
            removed += build_distribution.redact_record(record)
        if minify:
            body = json.dumps(record, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        elif profile == "public":
            body = (json.dumps(record, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
        else:
            body = raw
        target = out / source.name
        target.write_bytes(body)
        _copy_mtime(source, target)
        written += len(body)
    return read, written, removed, problems


def copy_records(records: list[Path], data_root: Path, site_data: Path, profile: str, minify: bool, jobs: int | None) -> dict[str, Any]:
    by_election: dict[str, list[str]] = {}
    for path in records:
        by_election.setdefault(path.parent.name, []).append(str(path))
    work = [
        (sources, str(site_data / election), profile, minify)
        for election, sources in sorted(by_election.items())
    ]
    totals = {"records": len(records), "elections": len(by_election), "sourceBytes": 0, "bytes": 0, "valuesRemoved": 0}
    problems: list[str] = []
    # One process per election; `jobs=1` stays in this one (the tests, which
    # load this file by path, cannot hand a worker the function).
    if jobs == 1:
        results = map(_write_records, work)
    else:
        pool = ProcessPoolExecutor(max_workers=jobs)
        results = pool.map(_write_records, work)
    try:
        for read, written, removed, found in results:
            totals["sourceBytes"] += read
            totals["bytes"] += written
            totals["valuesRemoved"] += removed
            problems += found
    finally:
        if jobs != 1:
            pool.shutdown()
    if problems:
        shown = "\n".join(f"    {line}" for line in problems[:20])
        more = f"\n    ... and {len(problems) - 20} more" if len(problems) > 20 else ""
        raise BuildError(f"{len(problems)} file(s) under {data_root}/ are not records:\n{shown}{more}")
    return totals


# --- 4. precompression ------------------------------------------------------


def precompress(site: Path) -> dict[str, int]:
    """`.gz` (and `.br` when the brotli command exists) beside each always-fetched file."""
    brotli = shutil.which("brotli")
    counts = {"gzip": 0, "brotli": 0}
    for path in sorted(site.rglob("*")):
        relative = path.relative_to(site).as_posix()
        if not path.is_file() or not PRECOMPRESS.match(relative) or path.stat().st_size < PRECOMPRESS_MIN_BYTES:
            continue
        gz = path.with_name(path.name + ".gz")
        with open(path, "rb") as raw, open(gz, "wb") as out:
            with gzip.GzipFile(fileobj=out, mode="wb", mtime=0, compresslevel=9, filename="") as handle:
                shutil.copyfileobj(raw, handle)
        _copy_mtime(path, gz)
        counts["gzip"] += 1
        if brotli:
            br = path.with_name(path.name + ".br")
            subprocess.run([brotli, "-q", "11", "-f", "-o", str(br), str(path)], check=True)
            _copy_mtime(path, br)
            counts["brotli"] += 1
    return counts


# --- 5. VERSION, and the whole build ----------------------------------------


def write_version(site: Path, fields: dict[str, Any]) -> None:
    lines = [f"{key}={value}" for key, value in fields.items()]
    (site / VERSION_FILE).write_text("\n".join(lines) + "\n", encoding="utf-8")


def read_version(site: Path) -> dict[str, str]:
    """VERSION as a dict; the inverse of `write_version`."""
    fields: dict[str, str] = {}
    for line in (site / VERSION_FILE).read_text(encoding="utf-8").splitlines():
        key, sep, value = line.partition("=")
        if sep:
            fields[key] = value
    return fields


def site_size(site: Path) -> tuple[int, int]:
    files = [path for path in site.rglob("*") if path.is_file()]
    return len(files), sum(path.stat().st_size for path in files)


def build_site(
    repo: Path,
    out: Path,
    *,
    corpus_tag: str | None = None,
    frontend: str = "build",
    index: str = "auto",
    portraits: str = "build",
    profile: str = "public",
    minify: bool = True,
    compress: bool = True,
    jobs: int | None = None,
) -> dict[str, Any]:
    """Build the site into `out`. Returns what VERSION says, with sizes."""
    repo = repo.resolve()
    out = out if out.is_absolute() else Path.cwd() / out
    if profile not in PROFILES:
        raise BuildError(f"unknown profile {profile!r}; one of {PROFILES}")
    for protected in (repo, repo / DATA_ROOT, repo / FRONTEND_DIR, repo / "scripts", repo / "docs"):
        if out.resolve() == protected.resolve():
            raise BuildError(f"--out {out} would replace {protected}")
    data_root = repo / DATA_ROOT
    if not data_root.is_dir():
        raise BuildError(f"no {data_root}/: get the corpus first (README, 'Getting the data')")

    node = build_frontend(repo, frontend)
    records = record_paths(data_root)
    if not records:
        raise BuildError(f"no records under {data_root}/")
    people = build_index_and_portraits(repo, records, index, portraits)

    staging = out.parent / f".{out.name}.staging-{os.getpid()}"
    shutil.rmtree(staging, ignore_errors=True)
    staging.mkdir(parents=True)
    try:
        # The page and its assets; nothing of frontend/ but the build.
        shutil.copytree(repo / BUILD_DIR, staging, dirs_exist_ok=True)
        for name in INDEX_FILES:
            shutil.copy2(repo / INDEX_DIR / name, staging / name)
        (staging / CONCEPT_MAP.parent).mkdir(parents=True, exist_ok=True)
        shutil.copy2(repo / CONCEPT_MAP, staging / CONCEPT_MAP)
        (staging / "portraits").mkdir()
        manifest = json.loads((repo / PORTRAITS_DIR / PORTRAITS_MANIFEST).read_text(encoding="utf-8"))
        for pid in sorted(manifest["portraits"]):
            shutil.copy2(repo / PORTRAITS_DIR / f"{pid}.webp", staging / "portraits" / f"{pid}.webp")
        print(f"records: {len(records):,} file(s), profile {profile}{', minified' if minify else ''} ...", flush=True)
        totals = copy_records(records, data_root, staging / "data", profile, minify, jobs)
        compressed = precompress(staging) if compress else {"gzip": 0, "brotli": 0}

        commit = provenance.parser_commit() or "unknown"
        files, size = site_size(staging)
        fields = {
            "commit": commit.removesuffix("-dirty"),
            "dirty": "true" if commit.endswith("-dirty") else "false",
            "corpus": corpus_tag or "unknown",
            "built": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "profile": profile,
            "node": node,
            "records": totals["records"],
            "elections": totals["elections"],
            "people": people["people"],
            "portraits": people["portraits"],
            "portraits_version": people["portraitsVersion"],
            "redacted_values": totals["valuesRemoved"],
            "minified": "true" if minify else "false",
            "precompressed": "+".join(k for k in ("brotli", "gzip") if compressed[k]) or "none",
            # Counted before VERSION exists, so they describe everything else.
            "files": files,
            "bytes": size,
        }
        write_version(staging, fields)

        old = out.parent / f".{out.name}.old-{os.getpid()}"
        if out.exists():
            os.replace(out, old)
        os.replace(staging, out)
        shutil.rmtree(old, ignore_errors=True)
    finally:
        shutil.rmtree(staging, ignore_errors=True)

    print(
        f"records:     {totals['records']:,} in {totals['elections']} election(s),"
        f" {totals['sourceBytes'] / 1e6:,.1f} MB in data/ -> {totals['bytes'] / 1e6:,.1f} MB"
        + (f"; {totals['valuesRemoved']} value(s) redacted" if profile == "public" else "")
    )
    print(f"index:       {people['people']:,} people, {people['portraits']:,} portraits (version {people['portraitsVersion']})")
    print(f"precompressed: {compressed['gzip']} .gz, {compressed['brotli']} .br")
    print(f"wrote {out}/: {fields['files']:,} files, {fields['bytes'] / 1e6:,.1f} MB (commit {commit}, corpus {fields['corpus']})")
    return {**fields, "sourceBytes": totals["sourceBytes"]}


# --- the tarball ------------------------------------------------------------


def write_tarball(site: Path, target: Path, level: int = ZSTD_LEVEL) -> dict[str, Any]:
    """Tar `site/` as its URL layout, entries without a leading directory.

    `.tar.zst` through the `zstd` command (Python 3.11 has no zstd module);
    `.tar.gz` in-process for a machine without it. Entries are sorted, owner
    and mode normalised, and mtimes kept: they are what Last-Modified says
    on the server.
    """
    if not (site / VERSION_FILE).is_file():
        raise BuildError(f"{site} has no VERSION: not a built site")
    target.parent.mkdir(parents=True, exist_ok=True)
    partial = target.with_name(target.name + ".partial")
    names = sorted(path.relative_to(site).as_posix() for path in site.rglob("*") if path.is_file())

    def add_all(tar: tarfile.TarFile) -> None:
        for name in names:
            path = site / name
            info = tar.gettarinfo(str(path), arcname=name)
            info.uid = info.gid = 0
            info.uname = info.gname = ""
            info.mode = 0o644
            info.mtime = int(info.mtime)
            with open(path, "rb") as handle:
                tar.addfile(info, handle)

    if target.name.endswith(".tar.zst"):
        zstd = shutil.which("zstd")
        if not zstd:
            raise BuildError("the zstd command is not installed; install it or name a .tar.gz target")
        with open(partial, "wb") as out:
            process = subprocess.Popen([zstd, "-q", "-T0", f"-{level}", "-c"], stdin=subprocess.PIPE, stdout=out)
            assert process.stdin is not None
            with tarfile.open(fileobj=process.stdin, mode="w|", format=tarfile.PAX_FORMAT) as tar:
                add_all(tar)
            process.stdin.close()
            if process.wait() != 0:
                raise BuildError("zstd failed")
    elif target.name.endswith(".tar.gz"):
        with open(partial, "wb") as out, gzip.GzipFile(fileobj=out, mode="wb", mtime=0, compresslevel=9, filename="") as gz:
            with tarfile.open(fileobj=gz, mode="w|", format=tarfile.PAX_FORMAT) as tar:
                add_all(tar)
    else:
        partial.unlink(missing_ok=True)
        raise BuildError(f"{target.name}: the tarball must end in .tar.zst or .tar.gz")
    os.replace(partial, target)
    digest = hashlib.sha256()
    with open(target, "rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
    return {"bytes": target.stat().st_size, "sha256": digest.hexdigest(), "files": len(names)}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--out", type=Path, default=Path("site"), help="output directory (default site/)")
    parser.add_argument("--repo-root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--corpus-tag", help="the corpus release this is, e.g. corpus-2026-10-25 (VERSION's corpus=)")
    parser.add_argument("--frontend", choices=("build", "verify"), default="build", help="build frontend/dist (default) or check the existing one is current")
    parser.add_argument("--index", choices=("auto", "build", "reuse"), default="auto", help="rebuild dashboard/people.json when stale (default), always, or never")
    parser.add_argument("--portraits", choices=("build", "reuse"), default="build", help="run the incremental portrait build (default) or use portraits/ as it is")
    parser.add_argument("--profile", choices=PROFILES, default="public", help="public (default): the release's redaction; full: records verbatim")
    parser.add_argument("--no-minify", dest="minify", action="store_false", help="keep the records' two-space indent")
    parser.add_argument("--no-precompress", dest="compress", action="store_false")
    parser.add_argument("--jobs", type=int, default=None, help="worker processes for the records (default: all cores)")
    parser.add_argument("--tarball", type=Path, help="also write the site as this .tar.zst or .tar.gz")
    args = parser.parse_args(argv)
    build_site(
        args.repo_root,
        args.out,
        corpus_tag=args.corpus_tag,
        frontend=args.frontend,
        index=args.index,
        portraits=args.portraits,
        profile=args.profile,
        minify=args.minify,
        compress=args.compress,
        jobs=args.jobs,
    )
    if args.tarball:
        packed = write_tarball(args.out, args.tarball)
        print(f"wrote {args.tarball}: {packed['bytes'] / 1e6:,.1f} MB, sha256 {packed['sha256']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
