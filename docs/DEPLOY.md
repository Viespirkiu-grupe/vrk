# Deploying vrk.viespirkiai.org

Production runs `scripts/serve_dashboard.py` over a checkout of this
repository, behind Cloudflare. The same server you run locally serves the
public site. It serves the Astro build at `/`, the index beside it,
`data/`, `portraits/` and `docs/concept-map.json`, and nothing else
([DASHBOARD.md](DASHBOARD.md#url-layout) has the URL layout).

## What the server needs

- A checkout of this repository, for the compose sample and the data
  directories, and Docker with Compose. The image carries the frontend build
  and the Python that builds the index.
- **`data/`**, the records, from the latest public
  [release](https://github.com/Viespirkiu-grupe/vrk/releases). The server
  needs no full-size photos:

  ```bash
  gh release download corpus-YYYY-MM-DD --pattern 'vrk-corpus.sqlite.gz' --pattern 'vrk-web-portraits.tar'
  gunzip vrk-corpus.sqlite.gz
  python scripts/unpack_corpus.py vrk-corpus.sqlite --no-photos   # writes ./data
  tar -xf vrk-web-portraits.tar                                    # writes ./portraits/*.webp
  ```

  Or copy `data/` and `portraits/` from a machine that scraped and built them
  (`scripts/build_web_portraits.py`). A public release has the third-party
  contacts already removed ([PERSONAL_DATA.md](PERSONAL_DATA.md)). A scraping
  disk still has them.
- **The index**, `dashboard/people-{list,details,version}.json`, built from
  `data/` (about 35 s; see below). It also stamps which people have a
  portrait in `portraits/`.

## Docker

The image is `ghcr.io/viespirkiu-grupe/vrk`, built from the
[Dockerfile](../Dockerfile) by `build-image.yml` on every push to main. It is
tagged with the full and short commit SHA, and with `latest` on main.
[compose.sample.yml](../compose.sample.yml) runs it as one service,
`vrk-app`. The service publishes no port. It joins the external network
`$VRK_NETWORK` (default `proxy`), and the front proxy on that network
(cloudflared, or a shared Caddy) sends `vrk.viespirkiai.org` to
**`http://vrk-app:8080`**. A commented `network_mode: host` is there for a
host-network setup like viespirkiai's. `data/` and `portraits/` are mounted
read-only and `dashboard/` read-write. The container runs as
`$VRK_UID:$VRK_GID`, which must be able to read the corpus and write
`dashboard/`.

The server answers only `localhost` and the names in `VRK_ALLOW_HOSTS`, so
the proxy must pass the original `Host` header. cloudflared and Caddy's
`reverse_proxy` both do by default. The proxy must also leave
`Cache-Control` alone. Caddy's `encode` leaves a response that is already
`Content-Encoding: br` as it is.

First setup, in the checkout, after `data/` and `portraits/` are in place:

```bash
cp compose.sample.yml compose.yml && cp .env.sample .env   # both gitignored; edit .env
docker network create proxy        # once per host, if it does not exist yet
docker compose run --rm vrk-app python scripts/build_person_index.py
docker compose up -d
```

A new GHCR package is private. Make it public in the package settings, or
`docker login ghcr.io` on the server. Without the registry,
`docker compose up -d --build` builds the same image from the checkout.

## Updating

```bash
git pull --ff-only                 # the sample and the docs; diff compose.yml against the sample
docker compose pull
docker compose run --rm vrk-app python scripts/build_person_index.py   # only after new data/ or portraits/
docker compose up -d
python3 scripts/smoke_check.py https://vrk.viespirkiai.org
```

A new corpus means unpacking the new release into `data/` and `portraits/`
first, as above. The index files are read from the mount on every request,
so a rebuilt index is live without a restart. To roll back, set `image:` in
compose.yml to an older SHA tag (`ghcr.io/viespirkiu-grupe/vrk:sha-<short>`)
and run `docker compose up -d`.

## Cloudflare

Nothing in the repository changes the zone. `/_astro/*` (CSS, JS) and
`/portraits/*.webp` need no rule. Their extensions are on Cloudflare's
default cacheable list, so the origin's `public, max-age=31536000,
immutable` already keeps them at the edge. The default cache key includes
the query string, which carries a portrait's `?v=` version.

JSON is not on that list, so the person index needs one cache rule
(Caching → Cache Rules):

- *When:* hostname is `vrk.viespirkiai.org` and the URI path equals
  `/people-list.json` or `/people-details.json`.
- *Then:* Eligible for cache. Edge TTL: "Use cache-control header if
  present". Browser TTL: "Respect origin". Default cache key: `?v=` is the
  file's content hash. The origin answers `immutable` only when `v` is the
  hash of the file it holds, and `no-cache` otherwise, so the edge never
  keeps a mid-deploy answer ([DASHBOARD.md](DASHBOARD.md#caching)).

After a deploy, check it with the `list` hash from the version file. The
second request should say `cf-cache-status: HIT`:

```bash
v=$(curl -s https://vrk.viespirkiai.org/people-version.json | python3 -c 'import json,sys; print(json.load(sys.stdin)["list"])')
curl -sI -H 'Accept-Encoding: br' "https://vrk.viespirkiai.org/people-list.json?v=$v" | grep -iE 'cf-cache-status|cache-control|content-encoding'
```

Everything else is `no-cache`, and Cloudflare passes revalidations through,
so they come back as 304s. Do not add a "Cache Everything" rule for `/` or
`/data/`, because the edge would then serve a stale index after an update.
Leave Auto Minify and Rocket Loader off, since they would rewrite the hashed
bundles. A rule left over for `/dashboard/_astro/*` from before #184 is
stale, and so is one for `/_astro/` or `/portraits/`, though it does no harm.

## Checking

```bash
python3 scripts/smoke_check.py https://vrk.viespirkiai.org
python3 scripts/smoke_check.py http://127.0.0.1:8791          # a local serve_dashboard.py
```

It exits non-zero if any check fails, and prints one line per check:

- `/` and the `/_astro/` files it links (immutable).
- The index (compressed, `no-cache`).
- One record, and that person's portrait and page.
- `/suvestine`.
- The repository paths that must 404.

`--record /data/…json` picks the record to probe.

## Access

The repository and its releases belong to the Viespirkiu-grupe
organisation. The server and the Cloudflare zone are held by the maintainer
([@debesyla](https://github.com/debesyla)). Ask there for access.
