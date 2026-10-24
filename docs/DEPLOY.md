# Deploying vrk.viespirkiai.org

How the corpus becomes the running site, start to finish (issue #188). It
is written for someone who has not seen the repository: the server needs
none of it but two scripts and one config file.

```
corpus (data/)  ──►  scripts/build_site.py  ──►  site/  ──►  build_distribution.py --site
                     (frontend, index,           (the URL      (vrk-site-YYYY-MM-DD.tar.zst
                      portraits, records)          layout)       + MANIFEST.json, a release)
                                                                         │
production:  scripts/deploy.sh <tag>  ◄──────────────────────────────────┘
             download → sha256 → extract → smoke check → switch `current`
```

Two machines are involved. The **build machine** has the repository and
the corpus, plus Python 3.11+ and Node 22.12+. It builds the site and,
optionally, the release. The **server** has only a static web server and a
few command-line tools. It downloads a release (or receives a tarball)
and serves it. Production does not run `scripts/serve_dashboard.py`.
That script is the local preview over the repository, and it holds the
rules the server's config copies.

## What the server needs

| Need | Why |
|---|---|
| Linux with [Caddy](https://caddyserver.com/docs/install) 2.7+ (primary), or nginx | serves the files; configs in [`deploy/`](../deploy/) |
| `tar`, `zstd`, `sha256sum` (coreutils), `curl` or `gh`, `python3` 3.8+ | `scripts/deploy.sh` and `scripts/smoke_check.py`, standard library only |
| ~2.3 GB disk per release, ~7 GB with the three it keeps, plus 150 MB per download | a release unpacks to 132,508 files |
| a Cloudflare tunnel or reverse proxy to `127.0.0.1:8780` | the configs listen on loopback and Cloudflare terminates TLS |

It needs no Node, no Python packages, no corpus and no `git pull` of a
working tree. A shallow clone is only a convenient way to get the two
scripts and the config.

**Why Caddy is primary.** It serves the precompressed `.br`/`.gz` copies
with no extra module (`file_server { precompressed br gzip }`). On Debian
and Ubuntu, nginx needs `libnginx-mod-http-brotli-static` for the brotli
ones. Caddy is one static binary, and its header rules are one block
instead of a snippet each nginx `location` has to include. Both configs are
in the repository, and both are held to the page's routes and to
`serve_dashboard.py`'s headers by `tests/test_deploy_config.py`. Neither
had been run on a real Caddy or nginx when this was written; run
`caddy validate` (or `nginx -t`) on first setup and the smoke check after.

## Where every served file comes from

The site directory's layout is the public URL layout: every file in it is
served at its own path, and every other path is a 404.

| URL | In `site/` from | Produced by | Measured 2026-10-24 |
|---|---|---|---|
| `/`, `/_astro/*`, `/branding/*`, `/fonts/*` | `frontend/dist/` | `cd frontend && npm ci && npm run build` (Node ≥ 22.12, `engines`), run by `build_site.py` | 10 files, 0.25 MB |
| `/people.json` | `dashboard/people.json` | `scripts/build_person_index.py` over `data/`, ~35 s; then re-stamped by the portrait build | 30.8 MB (4.7 MB `.br`, 7.2 MB `.gz` beside it) |
| `/field-labels.json` | `dashboard/field-labels.json` | tracked in git | 26 KB |
| `/docs/concept-map.json` | `docs/concept-map.json` | tracked in git | 194 KB |
| `/data/<election>/<candidate>-<election>.json` | `data/` | the corpus: the scrapers, or a release's `vrk-corpus.sqlite.gz` via `scripts/unpack_corpus.py`; written compact and with the public profile by `build_site.py` | 113,073 files, 2,121 MB (3,411 MB as stored in `data/`) |
| `/portraits/<pid>.webp?v=<version>` | `portraits/` | `scripts/build_web_portraits.py` from `data/<election>/photos/` (#187) | 19,402 files, 75 MB |
| `/VERSION` | written by `build_site.py` | | 0.3 KB |

**Left out on purpose:** the full-size `data/<election>/photos/` sidecars
(27,493 files, 5.2 GB; the page shows the web portraits instead), each
election's `anomalies.jsonl`, the reports at the top of `data/`, the
`.staging`/manifest files of the builders, and everything else in the
repository.

**The whole site:** 132,507 files and 2,240 MB, plus `VERSION`. As a
release asset it is **147.5 MB** (`vrk-site-YYYY-MM-DD.tar.zst`, zstd -19,
1 min 39 s to pack on 8 cores; gzip -9 would be 337 MB). A full
`build_site.py` run took 3 min 34 s on the build laptop, about two of them
on the records.

**The records are written compact** (no indentation), which takes the
records from 3,411 MB to 2,121 MB on disk, −37 % per record (28.6 → 17.9 KB on
a 3,000-record sample). Over the wire, gzipped, the saving is 12 % (5.11 →
4.49 KB per record). The page parses them either way. **They are also
passed through the release's public profile** (`--profile public`, #142):
the campaign treasurer's and auditor's phone and e-mail are removed, as
they are from every release. On the build laptop's corpus that removed
90,867 values. A server whose `data/` was unpacked from a public release
was already serving them that way, but one copied from a scraping disk was
not.

**`VERSION`** is `key=value` lines. They give the commit and whether the checkout was
dirty, the corpus release tag, the build date, the profile and Node
version, and the counts, for example:

```
commit=4ebc203
dirty=false
corpus=corpus-2026-10-25
built=2026-10-25T09:12:00Z
profile=public
records=113073
people=60568
portraits=19402
portraits_version=2b7c6a62
files=132507
bytes=2239775168
```

`curl https://vrk.viespirkiai.org/VERSION` says what is live.

## Building a release (build machine)

From the repository root, with the corpus in `data/`, use the venv's
Python:

```bash
python scripts/build_site.py --out site/ --corpus-tag corpus-$(date -u +%F)
```

This builds the frontend, rebuilds `dashboard/people.json` if any record or
input is newer, runs the incremental portrait build, and writes `site/`.
The previous `site/` stays until the new one is complete. Useful flags:
`--frontend verify` (use an existing `frontend/dist`, refusing a stale one),
`--index reuse`, `--portraits reuse`, `--no-minify`, `--profile full`,
`--tarball dist/vrk-site-test.tar.zst`. `--help` lists them.

Then the release assets, with the site among them:

```bash
python scripts/build_distribution.py --site site/
```

It refuses a `site/` whose `VERSION` names another day's tag, another
profile, another record count or another portrait set, and prints the
command to rebuild it. The site asset and its sha256 and size are in
`MANIFEST.json` beside the others, and the `gh release create` line it
prints includes it. Publishing that release is the maintainer's decision;
nothing here publishes one.

**No GitHub Actions workflow builds the site.** The corpus is not in the
repository, so a workflow would have to rebuild it from the release first:
download `vrk-corpus.sqlite.gz` and `vrk-web-portraits.tar`, unpack, index,
then `build_site.py --portraits reuse`. That is possible within a runner's
disk and time limits. But it would only repeat, from the release, a build
that `build_distribution.py --site` already does from the same corpus, and
it could not be tested without publishing a release.

## First-time server setup

As a user with sudo, on Debian or Ubuntu (Caddy from
[its own apt repository](https://caddyserver.com/docs/install#debian-ubuntu-raspbian),
since distribution packages lag):

```bash
sudo apt install -y caddy zstd python3 curl git
sudo mkdir -p /srv/vrk && sudo chown "$USER": /srv/vrk
git clone --depth 1 https://github.com/Viespirkiu-grupe/vrk.git /srv/vrk/repo
sudo cp /srv/vrk/repo/deploy/Caddyfile /etc/caddy/Caddyfile
sudo caddy validate --config /etc/caddy/Caddyfile
sudo systemctl reload caddy
/srv/vrk/repo/scripts/deploy.sh corpus-YYYY-MM-DD
```

The last line downloads that release's site, checks it on port 8781,
switches to it and checks port 8780; both checks run on loopback, so this
works before any traffic arrives. Then point Cloudflare's origin at port
8780, in the tunnel's ingress (`service: http://127.0.0.1:8780`) or the
reverse proxy's upstream, where it points at `serve_dashboard.py`'s port
today. Run `scripts/smoke_check.py https://vrk.viespirkiai.org` and, once
it passes, stop the Python server.

The Caddyfile reads `VRK_ROOT` (default `/srv/vrk`), `VRK_PORT` (8780),
`VRK_PREVIEW_PORT` (8781) and `VRK_BIND` (127.0.0.1) from Caddy's
environment (`sudo systemctl edit caddy`, `Environment=VRK_ROOT=…`). The
caddy user only needs to read `/srv/vrk`; the tarball's files are 0644.

**nginx instead:** the three files in [`deploy/nginx/`](../deploy/nginx/)
go to `/etc/nginx/conf.d/` and `/etc/nginx/snippets/` as `vrk.conf`'s
header comment says; then `sudo nginx -t && sudo systemctl reload nginx`.
Uncomment `brotli_static on;` once the brotli module is installed. Set
`/srv/vrk` there by editing `root`, since nginx reads no environment.

Layout on the server after a few deploys:

```
/srv/vrk/
  repo/                         the shallow clone: scripts/ and deploy/
  releases/corpus-2026-10-25/   one extracted site per release
  releases/corpus-2026-11-02/
  current -> releases/corpus-2026-11-02   what port 8780 serves
  previous -> releases/corpus-2026-10-25  what --rollback returns to
  next -> releases/corpus-2026-11-02      what port 8781 serves (the check)
```

## Routine deploy

```bash
cd /srv/vrk/repo && git pull --ff-only     # only when scripts/ or deploy/ changed
/srv/vrk/repo/scripts/deploy.sh corpus-YYYY-MM-DD
```

`deploy.sh` downloads `MANIFEST.json` and the `vrk-site-*` asset of that
release. It uses `gh` when it is installed and logged in, and `curl`
otherwise (`VRK_DOWNLOAD=gh|curl` forces one). It then checks the sha256 and size against the manifest and
extracts into `releases/<tag>/`. It points `next` at the new release and
runs the smoke check on port 8781. If any check fails it stops there, and
`current` is untouched. Otherwise it switches `current` with a single
`rename(2)`, so no request ever sees a missing site, and checks port 8780.
If that check fails, it switches back. It keeps the newest three releases
(`--keep N`) and never deletes one a link points at.

**From a tarball instead of a release**, for example one built with
`build_site.py --tarball` and copied over with `scp`:

```bash
/srv/vrk/repo/scripts/deploy.sh /tmp/vrk-site-2026-10-25.tar.zst --sha256 <hex>
```

Without `--sha256` it uses a `MANIFEST.json` beside the tarball, or the one
`--manifest` names, and refuses a tarball with neither.

`--status` prints the three links and the live `VERSION`. `--help` lists
every option; each also has an environment variable (`VRK_ROOT`, `VRK_URL`,
`VRK_PREVIEW_URL`, `VRK_RELOAD`, `VRK_KEEP`, `VRK_REPO`). No reload is
needed by default: Caddy, and nginx without `open_file_cache`, follow the
symlink on every request. Set `--reload 'sudo systemctl reload nginx'` for
a server that caches file handles. A failing reload counts as a failed
deploy and switches back.

## Rollback

```bash
/srv/vrk/repo/scripts/deploy.sh --rollback
```

`current` goes back to `previous`, `previous` to what was current, and the
live check runs. Nothing is downloaded or deleted. Running it twice goes
forward again. To return to an older kept release, deploy its tag: a
release that is already extracted is neither downloaded nor extracted
again, only checked and switched to.

## The smoke check

```bash
python3 scripts/smoke_check.py https://vrk.viespirkiai.org
python3 scripts/smoke_check.py http://127.0.0.1:8781 --expect-version corpus-2026-10-25
```

It checks the following against any base URL, and exits non-zero if any
check fails:

- `/` is 200 HTML with the security headers, and every `/_astro/` file it
  links is 200 and `immutable`.
- `/people.json` is 200, compressed, `no-cache` and parses.
- One record and that person's portrait are 200 (the portrait as
  `image/webp`, versioned and `immutable`).
- `/asmuo/<slug>-<pid>` and `/suvestine` answer with the page.
- `/field-labels.json` and `/docs/concept-map.json` are 200.
- `/dashboard/`, `/scripts/`, `/.git/`, `/data/` and a mistyped bundle are 404.

`--record /data/…json` picks the record to probe. It works against
`serve_dashboard.py` locally too.

Against production on 2026-10-24 it failed 9 of its checks. Production
still ran a pre-#184 `serve_dashboard.py`: `/` redirected to `/dashboard/`,
`/people.json` was not there yet, and repository paths were 403 rather
than 404. That is the state this deploy replaces.

## Cloudflare

Nothing in the repository changes the zone. The operator sets the
following in the dashboard.

**Cache rule** (Caching → Cache Rules → Create rule):

- *When:* hostname equals `vrk.viespirkiai.org` **and** URI path starts
  with `/_astro/` **or** `/portraits/`.
- *Then:* Eligible for cache. Edge TTL: "Use cache-control header if
  present, bypass cache if not". Browser TTL: "Respect origin". Keep the
  default cache key: it includes the query string, which is what carries a
  portrait's `?v=` version.

That is the only rule. The origin marks only those two URL classes
`immutable` (a bare `/portraits/<pid>.webp` is `no-cache`, and the edge
honours it). Everything else (the HTML, `people.json`, the records,
`/VERSION`) is `no-cache`. Cloudflare does not cache `.json` or
extensionless paths by default, so it passes the browser's conditional
requests to the origin, and they come back as 304s. Do **not** add a
"Cache Everything" rule for `/` or `/data/`. It would serve a stale index
after a corpus update.

**If the zone uses Page Rules** rather than Cache Rules, the same thing is
one page rule per pattern: `vrk.viespirkiai.org/_astro/*` and
`vrk.viespirkiai.org/portraits/*`, each with *Cache Level: Cache
Everything* and *Edge Cache TTL* left unset, so the origin's
`Cache-Control` decides. A rule written for `/dashboard/_astro/*` before
#184 is stale and should be changed or removed.

**Also check:** Brotli on (Speed → Optimization). Leave any Auto Minify or
Rocket Loader setting off, since it would rewrite the page's hashed bundles. The
origin sends `people.json` as precompressed brotli, which Cloudflare passes
through instead of recompressing, so its `ETag` survives. Revalidation
works on `Last-Modified` alone in any case (#186).

To see what the edge does, run this twice with a bundle name from the
page's HTML. The second response shows `cf-cache-status: HIT`:

```bash
curl -s -o /dev/null -D - https://vrk.viespirkiai.org/_astro/<bundle>
```

## The lesson of #183

After the Astro migration, a deploy that was `git pull` plus a restart
served a 404 page for `/dashboard/`. `frontend/dist` is a build output that
git ignores, so pulling never produced it. The fix is structural, not a
reminder. **The frontend build is part of building the site, not of
updating a checkout.** `build_site.py` runs it, or refuses a stale one
with `--frontend verify`. The site tarball carries its output. The server
never builds anything. The smoke check asks for the page's own
`/_astro/` files, not only `/`, so a page without its bundle fails the
deploy before anyone sees it.

## Access

The GitHub repository and its releases belong to the Viespirkiu-grupe
organisation. Publishing a release needs write access. The server and the
Cloudflare zone for viespirkiai.org are held by the maintainer
([@debesyla](https://github.com/debesyla)); ask there for SSH or zone
access. The repository records no credentials, and none are needed to
download a public release.
