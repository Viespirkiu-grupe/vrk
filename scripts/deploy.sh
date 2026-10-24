#!/usr/bin/env bash
# Install a built site on the server and switch to it (issue #188).
#
#   scripts/deploy.sh corpus-2026-10-25                  # a release tag
#   scripts/deploy.sh /tmp/vrk-site-2026-10-25.tar.zst   # a local tarball
#   scripts/deploy.sh --rollback                         # back to the previous one
#   scripts/deploy.sh --status
#
# A deploy:
#   1. downloads the release's vrk-site-*.tar.zst and MANIFEST.json (gh, or
#      curl when gh is not installed); a local tarball uses the
#      MANIFEST.json beside it, or --manifest, or --sha256;
#   2. checks the tarball's sha256 and size against the manifest;
#   3. extracts it into $VRK_ROOT/releases/<name>/;
#   4. points $VRK_ROOT/next at it and runs scripts/smoke_check.py against
#      the preview server, which serves `next` (deploy/Caddyfile, port 8781);
#      a failure stops here, with `current` untouched;
#   5. switches $VRK_ROOT/current to it with one rename, keeping the old
#      target as $VRK_ROOT/previous;
#   6. runs the reload command, if one is set, then the smoke check against
#      the live server; if either fails, switches back and exits non-zero;
#   7. deletes all but the newest --keep releases (never current or previous).
#
# Rollback points `current` at `previous` (and `previous` at what was
# current), reloads, and checks. Nothing is downloaded or deleted.
#
# Needs bash, tar, zstd (for .tar.zst), sha256sum or shasum, python3 (3.8+,
# for the smoke check and the atomic rename), and gh or curl. docs/DEPLOY.md
# has the server setup.

set -euo pipefail

ROOT="${VRK_ROOT:-/srv/vrk}"
REPO="${VRK_REPO:-Viespirkiu-grupe/vrk}"
URL="${VRK_URL:-http://127.0.0.1:8780}"
PREVIEW_URL="${VRK_PREVIEW_URL:-http://127.0.0.1:8781}"
# Caddy and nginx (without open_file_cache) resolve the `current` symlink on
# every request, so a switch needs no reload; set one for a server that
# caches file handles, e.g. --reload 'sudo systemctl reload nginx'.
RELOAD="${VRK_RELOAD-}"
KEEP="${VRK_KEEP:-3}"
# How a tag is fetched: auto (gh when logged in, else curl), gh or curl; and
# where curl finds the assets (a file:// URL works, which the tests use).
DOWNLOAD="${VRK_DOWNLOAD:-auto}"
RELEASE_BASE="${VRK_RELEASE_BASE:-https://github.com/$REPO/releases/download}"
SMOKE="${VRK_SMOKE:-$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/smoke_check.py}"
MANIFEST=""
SHA256=""
MODE=deploy
TARGET=""

usage() { sed -n '2,/^$/s/^# \{0,1\}//p' "$0"; cat <<EOF
Options (environment variable in brackets):
  --root DIR          where releases/, current, next, previous live [VRK_ROOT, $ROOT]
  --repo OWNER/NAME   the GitHub repository a tag is downloaded from [VRK_REPO, $REPO]
                      (VRK_DOWNLOAD=auto|gh|curl picks the tool; VRK_RELEASE_BASE the curl URL)
  --url URL           the live server, checked after the switch [VRK_URL, $URL]
  --preview-url URL   the server that serves ROOT/next [VRK_PREVIEW_URL, $PREVIEW_URL]
  --reload CMD        run after a switch; '' for none [VRK_RELOAD, $RELOAD]
  --keep N            releases to keep [VRK_KEEP, $KEEP]
  --manifest FILE     MANIFEST.json for a local tarball
  --sha256 HEX        the checksum of a local tarball, instead of a manifest
  --rollback          switch back to the previous release
  --status            print what current, previous and next point at
EOF
}

die() { echo "deploy: $*" >&2; exit 1; }
say() { echo "deploy: $*"; }

while [ $# -gt 0 ]; do
  case "$1" in
    --root) ROOT="$2"; shift 2 ;;
    --repo) REPO="$2"; shift 2 ;;
    --url) URL="$2"; shift 2 ;;
    --preview-url) PREVIEW_URL="$2"; shift 2 ;;
    --reload) RELOAD="$2"; shift 2 ;;
    --keep) KEEP="$2"; shift 2 ;;
    --manifest) MANIFEST="$2"; shift 2 ;;
    --sha256) SHA256="$2"; shift 2 ;;
    --rollback) MODE=rollback; shift ;;
    --status) MODE=status; shift ;;
    -h|--help) usage; exit 0 ;;
    -*) die "unknown option $1 (--help lists them)" ;;
    *) [ -z "$TARGET" ] || die "one release at a time"; TARGET="$1"; shift ;;
  esac
done

command -v python3 >/dev/null || die "python3 is required (smoke check, atomic switch)"
[ -f "$SMOKE" ] || die "smoke check not found at $SMOKE (set VRK_SMOKE)"

# Point a symlink somewhere with one rename(2): a reader sees the old target
# or the new one, never a missing link. (`ln -sfn` unlinks first.)
relink() {
  local link="$1" dest="$2"
  python3 - "$link" "$dest" <<'PY'
import os, sys
link, dest = sys.argv[1], sys.argv[2]
tmp = f"{link}.tmp-{os.getpid()}"
os.symlink(dest, tmp)
os.replace(tmp, link)
PY
}

target_of() { [ -L "$1" ] && readlink "$1" || true; }

sha256_of() {
  if command -v sha256sum >/dev/null; then sha256sum "$1" | cut -d' ' -f1
  else shasum -a 256 "$1" | cut -d' ' -f1; fi
}

reload() {
  [ -n "$RELOAD" ] || return 0
  say "reload: $RELOAD"
  sh -c "$RELOAD" || { echo "deploy: the reload command failed: $RELOAD" >&2; return 1; }
}

smoke() {
  local base="$1"; shift
  python3 "$SMOKE" "$base" "$@"
}

mkdir -p "$ROOT/releases"

if [ "$MODE" = status ]; then
  for link in current previous next; do
    printf '%-9s %s\n' "$link" "$(target_of "$ROOT/$link")"
  done
  [ -f "$ROOT/current/VERSION" ] && sed 's/^/  /' "$ROOT/current/VERSION"
  exit 0
fi

if [ "$MODE" = rollback ]; then
  [ -z "$TARGET" ] || die "--rollback takes no release"
  prev="$(target_of "$ROOT/previous")"
  cur="$(target_of "$ROOT/current")"
  [ -n "$prev" ] || die "no previous release recorded at $ROOT/previous"
  [ -d "$ROOT/$prev" ] || [ -d "$prev" ] || die "previous release $prev is gone"
  relink "$ROOT/current" "$prev"
  [ -n "$cur" ] && relink "$ROOT/previous" "$cur"
  say "current -> $prev (was $cur)"
  reload || die "rolled back to $prev, but the reload failed"
  smoke "$URL" || die "rolled back to $prev, but the live smoke check fails"
  exit 0
fi

[ -n "$TARGET" ] || { usage; exit 2; }

# A release already extracted was checked when it was first deployed: a
# redeploy (forward again after a rollback) neither downloads nor extracts.
if [ -f "$TARGET" ]; then name="$(basename "$TARGET")"; name="${name%.tar.*}"; else name="$TARGET"; fi
release="releases/$name"

install_release() {
  work="$(mktemp -d "$ROOT/.download.XXXXXX")"
  trap 'rm -rf "$work"' EXIT

  # 1. The tarball and what it should hash to.
  if [ -f "$TARGET" ]; then
    tarball="$TARGET"
    asset="$(basename "$tarball")"
    [ -n "$MANIFEST" ] || [ -n "$SHA256" ] || MANIFEST="$(dirname "$tarball")/MANIFEST.json"
  else
    tag="$TARGET"
    if [ "$DOWNLOAD" = gh ] || { [ "$DOWNLOAD" = auto ] && command -v gh >/dev/null && gh auth status >/dev/null 2>&1; }; then
      say "downloading $tag from $REPO (gh)"
      gh release download "$tag" -R "$REPO" -D "$work" -p MANIFEST.json -p 'vrk-site-*'
    else
      command -v curl >/dev/null || die "neither gh nor curl is installed"
      say "downloading $tag from $REPO (curl)"
      base="$RELEASE_BASE/$tag"
      curl -fsSL -o "$work/MANIFEST.json" "$base/MANIFEST.json" || die "$tag has no MANIFEST.json"
      asset="$(python3 -c 'import json,sys; print(next(k for k in json.load(open(sys.argv[1]))["artifacts"] if k.startswith("vrk-site-")))' "$work/MANIFEST.json" 2>/dev/null)" \
        || die "$tag's MANIFEST.json lists no vrk-site-* asset"
      curl -fL --progress-bar -o "$work/$asset" "$base/$asset" || die "could not download $asset"
    fi
    MANIFEST="$work/MANIFEST.json"
    tarball="$(ls "$work"/vrk-site-*.tar.* 2>/dev/null | head -1)"
    [ -n "$tarball" ] || die "$tag has no vrk-site-* asset; was the release built with build_distribution.py --site?"
    asset="$(basename "$tarball")"
  fi

  # 2. The checksum.
  if [ -n "$SHA256" ]; then
    want_sha="$SHA256"; want_bytes=""
  else
    [ -f "$MANIFEST" ] || die "no MANIFEST.json for $asset (pass --manifest FILE or --sha256 HEX)"
    read -r want_sha want_bytes < <(python3 -c '
import json, sys
entry = json.load(open(sys.argv[1]))["artifacts"].get(sys.argv[2])
print(entry["sha256"], entry["bytes"]) if entry else sys.exit(1)' "$MANIFEST" "$asset") \
      || die "$MANIFEST does not list $asset"
  fi
  got_sha="$(sha256_of "$tarball")"
  [ "$got_sha" = "$want_sha" ] || die "$asset: sha256 $got_sha, the manifest says $want_sha"
  if [ -n "$want_bytes" ]; then
    got_bytes="$(wc -c < "$tarball" | tr -d ' ')"
    [ "$got_bytes" = "$want_bytes" ] || die "$asset: $got_bytes bytes, the manifest says $want_bytes"
  fi
  say "$asset: sha256 verified"

  # 3. Extract.
  partial="$ROOT/$release.partial"
  rm -rf "$partial"; mkdir -p "$partial"
  say "extracting into $release"
  case "$asset" in
    *.tar.zst) command -v zstd >/dev/null || die "zstd is not installed (apt install zstd)"
               zstd -dc "$tarball" | tar -x --no-same-owner -C "$partial" ;;
    *.tar.gz)  tar -xz --no-same-owner -f "$tarball" -C "$partial" ;;
    *) die "$asset: expected .tar.zst or .tar.gz" ;;
  esac
  [ -f "$partial/VERSION" ] && [ -f "$partial/index.html" ] || die "$asset is not a built site (no VERSION or index.html)"
  rm -rf "${ROOT:?}/$release"
  mv "$partial" "$ROOT/$release"
}

if [ -f "$ROOT/$release/VERSION" ]; then
  say "$release is already extracted; reusing it"
else
  install_release
fi
sed 's/^/  /' "$ROOT/$release/VERSION"

# 4. Check it before anyone sees it.
relink "$ROOT/next" "$release"
say "smoke check of $release on the preview server"
smoke "$PREVIEW_URL" || die "the smoke check failed on $release; current is unchanged ($(target_of "$ROOT/current"))"

# 5-6. Switch, reload, check again.
old="$(target_of "$ROOT/current")"
old_previous="$(target_of "$ROOT/previous")"
if [ "$old" = "$release" ]; then
  say "current already points at $release"
else
  relink "$ROOT/current" "$release"
  [ -n "$old" ] && relink "$ROOT/previous" "$old"
  say "current -> $release${old:+ (previous -> $old)}"
fi
if ! { reload && smoke "$URL"; }; then
  if [ -n "$old" ] && [ "$old" != "$release" ]; then
    relink "$ROOT/current" "$old"
    if [ -n "$old_previous" ]; then relink "$ROOT/previous" "$old_previous"; else rm -f "$ROOT/previous"; fi
    reload || true
    die "the live check failed after the switch; switched back to $old"
  fi
  die "the live check failed after the switch"
fi

# 7. Prune, oldest first, never what a link points at.
keep_links=" $(target_of "$ROOT/current") $(target_of "$ROOT/previous") $(target_of "$ROOT/next") "
count=0
for dir in $(ls -1t "$ROOT/releases"); do
  [ -d "$ROOT/releases/$dir" ] || continue
  count=$((count + 1))
  [ "$count" -gt "$KEEP" ] || continue
  case "$keep_links" in *" releases/$dir "*) continue ;; esac
  say "pruning releases/$dir"
  rm -rf "${ROOT:?}/releases/$dir"
done
say "deployed $release"
