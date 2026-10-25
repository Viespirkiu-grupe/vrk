# Deploying vrk.viespirkiai.org

The site is one Docker container running `scripts/serve_dashboard.py`.
Cloudflare sits in front of it.

## Quick start

First time, on the server:

1. `git clone https://github.com/Viespirkiu-grupe/vrk && cd vrk`
2. Get the data (see [Data](#data)).
3. `cp compose.sample.yml compose.yml && cp .env.sample .env`, then edit `.env`.
4. `docker compose run --rm vrk-app python scripts/build_person_index.py`
5. `docker compose up -d`
6. Point the Cloudflare tunnel or proxy at `http://vrk-app:8080`.

Every update after that:

```bash
git pull --ff-only
docker compose pull
docker compose up -d
python3 scripts/smoke_check.py https://vrk.viespirkiai.org
```

For new data, unpack it first and rerun step 4. You don't need a restart.

## Data

The container needs three folders next to `compose.yml`:

| Folder | What | Where from |
|---|---|---|
| `data/` | the records | the latest [release](https://github.com/Viespirkiu-grupe/vrk/releases) |
| `portraits/` | small portrait images | the same release |
| `dashboard/` | the person index | step 4 builds it from `data/` (about 35 s) |

```bash
gh release download corpus-YYYY-MM-DD --pattern 'vrk-corpus.sqlite.gz' --pattern 'vrk-web-portraits.tar'
gunzip vrk-corpus.sqlite.gz
python scripts/unpack_corpus.py vrk-corpus.sqlite --no-photos   # writes data/
tar -xf vrk-web-portraits.tar                                    # writes portraits/
```

Releases have third-party contact details removed
([PERSONAL_DATA.md](PERSONAL_DATA.md)). A scraping machine's `data/` does
not, so don't copy that one to the server.

## Docker

- **Image:** `ghcr.io/viespirkiu-grupe/vrk`. GitHub builds it on every push
  to main and tags it `latest` plus the commit SHA.
- **First push:** the package starts private. Make it public in the package
  settings, or run `docker login ghcr.io` on the server. Until then,
  `docker compose up -d --build` builds the image on the server.
- **Network:** the container publishes no port. It joins the Docker network
  named in `.env` (`VRK_NETWORK`, default `proxy`; create it once with
  `docker network create proxy`). For host networking, as on viespirkiai,
  see the comment in `compose.sample.yml`.
- **Host names:** the server answers only the names in `VRK_ALLOW_HOSTS`, so
  the proxy must pass the original `Host` header. cloudflared and Caddy do
  that by default.
- **Permissions:** the container runs as `VRK_UID:VRK_GID`. That user must be
  able to read `data/` and `portraits/` and write `dashboard/`.
- **Roll back:** in `compose.yml`, set `image:` to an older tag
  (`ghcr.io/viespirkiu-grupe/vrk:sha-<short>`), then run
  `docker compose up -d`.

## Cloudflare

CSS, JS and portraits are cached automatically, because the server marks
them `public, immutable`.

JSON isn't cached by default, so add one cache rule (Caching → Cache Rules):

- **When:** the path is `/people-list.json` or `/people-details.json`.
- **Then:** Eligible for cache, Edge TTL "use cache-control header", Browser
  TTL "respect origin", and the default cache key.

This is safe. The page asks for these files as `?v=<hash>`, and a new index
gets a new hash, so visitors never see old data.

To check it, run this twice. The second run should show
`cf-cache-status: HIT`:

```bash
v=$(curl -s https://vrk.viespirkiai.org/people-version.json | python3 -c 'import json,sys; print(json.load(sys.stdin)["list"])')
curl -sI "https://vrk.viespirkiai.org/people-list.json?v=$v" | grep -i cf-cache-status
```

Don't add a "Cache Everything" rule, and leave Auto Minify and Rocket Loader
off.

## Checking

```bash
python3 scripts/smoke_check.py https://vrk.viespirkiai.org
```

It checks the page, the index, one record with its portrait, and that
private paths return 404. A failure prints the reason and exits non-zero.

## Access

The code and releases are in the
[Viespirkiu-grupe](https://github.com/Viespirkiu-grupe) organisation. The
server and Cloudflare are run by [Viespirkiai](https://github.com/Viespirkiai).
