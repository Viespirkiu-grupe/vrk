# Deploying vrk.viespirkiai.org

The site is one Docker container, with a Cloudflare tunnel in front.

## First time

On the server, with Docker, `gh` and `python3`:

1. **Get the code.**

   ```bash
   git clone https://github.com/Viespirkiu-grupe/vrk && cd vrk
   ```

2. **Get the data** from the latest
   [release](https://github.com/Viespirkiu-grupe/vrk/releases). This writes
   `data/` and `portraits/`.

   ```bash
   gh release download corpus-YYYY-MM-DD --pattern 'vrk-corpus.sqlite.gz' --pattern 'vrk-web-portraits.tar'
   gunzip vrk-corpus.sqlite.gz
   python3 scripts/unpack_corpus.py vrk-corpus.sqlite --no-photos
   tar -xf vrk-web-portraits.tar
   ```

3. **Copy the settings.** Then check `.env`: the user ID in it must be able
   to read `data/` and `portraits/` and write `dashboard/`.

   ```bash
   cp compose.sample.yml compose.yml && cp .env.sample .env
   ```

4. **Create the Docker network** the tunnel and the site share. Skip this if
   it already exists.

   ```bash
   docker network create proxy
   ```

5. **Build the person index** from `data/` into `dashboard/`.

   ```bash
   docker compose run --rm vrk-app python scripts/build_person_index.py
   ```

6. **Start the site.**

   ```bash
   docker compose up -d
   ```

   The image is pulled from `ghcr.io/viespirkiu-grupe/vrk`. If the pull is
   refused, the package is still private: make it public in its GitHub
   settings, or run `docker login ghcr.io`.

7. **Point the Cloudflare tunnel** at `http://vrk-app:8080`.

## Updating

```bash
git pull --ff-only
docker compose pull
docker compose up -d
python3 scripts/smoke_check.py https://vrk.viespirkiai.org
```

The last command checks the live site and prints what failed, if anything.

For a new corpus, repeat steps 2 and 5 first.

## Rolling back

Every push to main builds an image tagged with its commit. In
`compose.yml`, set `image:` to an older one, e.g.
`ghcr.io/viespirkiu-grupe/vrk:sha-1a2b3c4`, then run `docker compose up -d`.

## Cloudflare

Add one cache rule (Caching → Cache Rules):

- **When:** the path is `/people-list.json` or `/people-details.json`.
- **Then:** Eligible for cache, Edge TTL "use cache-control header", Browser
  TTL "respect origin".

CSS, JS and portraits are cached without a rule. JSON is not, so these two
files need it. Old data is never served, because the page asks for them by
content hash (`?v=…`).

To check the rule, run this twice. The second run should print
`cf-cache-status: HIT`.

```bash
v=$(curl -s https://vrk.viespirkiai.org/people-version.json | python3 -c 'import json,sys; print(json.load(sys.stdin)["list"])')
curl -sI "https://vrk.viespirkiai.org/people-list.json?v=$v" | grep -i cf-cache-status
```

Don't add a "Cache Everything" rule. It would serve old pages after an
update.

## Access

Code and releases: [Viespirkiu-grupe](https://github.com/Viespirkiu-grupe).
Server and Cloudflare: [Viespirkiai](https://github.com/Viespirkiai).
