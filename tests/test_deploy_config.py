"""The production server configs agree with the page and the local server (issue #188).

Three places list the page's routes: frontend/src/lib/routes.js (the page),
scripts/serve_dashboard.py (local preview, held to the page by
tests/test_dashboard_ui.py), and deploy/Caddyfile + deploy/nginx/ (production).
A view added to the page and not to the config is a production 404 on every
reload of it, so the routes are read out of each config and checked against
the page's list, and the regexes are run against the same paths as
serve_dashboard's `is_route`. The headers are compared to the script's too.
"""

from __future__ import annotations

import importlib.util
import re
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
CADDYFILE = (REPO_ROOT / "deploy" / "Caddyfile").read_text(encoding="utf-8")
NGINX_SITE = (REPO_ROOT / "deploy" / "nginx" / "vrk-site.conf").read_text(encoding="utf-8")
NGINX_HEADERS = (REPO_ROOT / "deploy" / "nginx" / "vrk-headers.conf").read_text(encoding="utf-8")
NGINX_SERVERS = (REPO_ROOT / "deploy" / "nginx" / "vrk.conf").read_text(encoding="utf-8")
ROUTES_JS = (REPO_ROOT / "frontend" / "src" / "lib" / "routes.js").read_text(encoding="utf-8")

_spec = importlib.util.spec_from_file_location("serve_dashboard", REPO_ROOT / "scripts" / "serve_dashboard.py")
serve = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(serve)

#: The page's own list: VIEW_PATHS and the two key-carrying prefixes.
VIEW_PATHS = set(re.findall(r'^\s+\w+Btn: "(/[a-z-]+)",$', ROUTES_JS, flags=re.M))
PREFIXES = set(re.findall(r'^const \w+_PREFIX = "(/[a-z]+/)";$', ROUTES_JS, flags=re.M))

CADDY_ROUTE = re.compile(re.search(r"^\s*@route path_regexp route (\S+)$", CADDYFILE, flags=re.M).group(1))
#: nginx: every regex location that answers with the page.
NGINX_ROUTES = [
    re.compile(pattern)
    for pattern, body in re.findall(r"location ~ (\S+) \{(.*?)\}", NGINX_SITE, flags=re.S)
    if "try_files /index.html" in body
]

PATHS = [
    "/", "/index.html", "/suvestine", "/suvestine/", "/iskelejai", "/apreptis", "/pokyciai/",
    "/suvestinex", "/suvestine/x", "/partiju-keitimai", "/partiju-keitimai/", "/partiju", "/xsuvestine",
    "/asmuo/", "/asmuo/birute-vesaite-p7d185515b624", "/asmuo/p7d185515b624/", "/asmuo/a/b", "/asmuo",
    "/palyginti/p1,p2,p3", "/palyginti/p1/", "/palyginti/x/y",
    "/people.json", "/data/2019-prezidento/x.json", "/_astro/index.js", "/portraits/p1.webp",
    "/dashboard/", "/scripts/deploy.sh", "/.git/config", "/asmuo.json",
]


def nginx_is_route(path: str) -> bool:
    return any(pattern.match(path) for pattern in NGINX_ROUTES)


class RouteListTests(unittest.TestCase):
    def test_the_page_lists_what_the_tests_expect(self):
        # A sanity floor, so a routes.js reshuffle cannot make both sides empty.
        self.assertEqual(VIEW_PATHS, {"/suvestine", "/iskelejai", "/apreptis", "/pokyciai", "/partiju-keitimai"})
        self.assertEqual(PREFIXES, {"/asmuo/", "/palyginti/"})

    def test_caddy_lists_the_pages_routes(self):
        views = set(re.search(r"\(\(([a-z|-]+)\)\|", CADDY_ROUTE.pattern).group(1).split("|"))
        prefixes = set(re.search(r"\|\(([a-z|]+)\)/", CADDY_ROUTE.pattern).group(1).split("|"))
        self.assertEqual({"/" + v for v in views}, VIEW_PATHS)
        self.assertEqual({f"/{p}/" for p in prefixes}, PREFIXES)

    def test_nginx_lists_the_pages_routes(self):
        self.assertEqual(len(NGINX_ROUTES), 2)
        views = set(re.search(r"\^/\(([a-z|-]+)\)/\?\$", NGINX_ROUTES[0].pattern).group(1).split("|"))
        prefixes = set(re.search(r"\^/\(([a-z|]+)\)/\[", NGINX_ROUTES[1].pattern).group(1).split("|"))
        self.assertEqual({"/" + v for v in views}, VIEW_PATHS)
        self.assertEqual({f"/{p}/" for p in prefixes}, PREFIXES)

    def test_every_config_routes_like_serve_dashboard(self):
        for path in PATHS:
            with self.subTest(path=path):
                expected = serve.is_route(path)
                self.assertEqual(bool(CADDY_ROUTE.match(path)), expected, "Caddyfile")
                self.assertEqual(nginx_is_route(path), expected, "nginx")

    def test_dashboard_md_points_at_the_configs(self):
        # The fallback used to be written out in docs/DASHBOARD.md as well; it
        # now names the files, so there is no third copy to drift.
        text = (REPO_ROOT / "docs" / "DASHBOARD.md").read_text(encoding="utf-8")
        self.assertIn("deploy/Caddyfile", text)
        self.assertNotIn("location ~ ^/(suvestine", text)


class HeaderTests(unittest.TestCase):
    def test_csp_is_the_servers(self):
        self.assertIn(f'Content-Security-Policy "{serve.CONTENT_SECURITY_POLICY}"', CADDYFILE)
        self.assertIn(f'add_header Content-Security-Policy "{serve.CONTENT_SECURITY_POLICY}" always;', NGINX_HEADERS)

    def test_hardening_headers(self):
        self.assertRegex(CADDYFILE, r"X-Content-Type-Options nosniff")
        self.assertRegex(CADDYFILE, r"Referrer-Policy no-referrer")
        self.assertIn('add_header X-Content-Type-Options "nosniff" always;', NGINX_HEADERS)
        self.assertIn('add_header Referrer-Policy "no-referrer" always;', NGINX_HEADERS)

    def test_cache_classes_are_the_servers(self):
        immutable = serve.IMMUTABLE_CACHE_CONTROL
        self.assertIn(f'header @immutable_astro Cache-Control "{immutable}"', CADDYFILE)
        self.assertIn(f'header @immutable_portrait Cache-Control "{immutable}"', CADDYFILE)
        self.assertIn(f"header ?Cache-Control {serve.REVALIDATE_CACHE_CONTROL}", CADDYFILE)
        self.assertIn(f'add_header Cache-Control "{immutable}";', NGINX_SITE)
        self.assertIn(f'default "{immutable}";', NGINX_SERVERS)
        # Only successes are cacheable: nginx's add_header without `always`,
        # and Caddy's error handler takes it off again.
        self.assertNotRegex(NGINX_SITE, r"add_header Cache-Control [^;]+ always;")
        self.assertRegex(CADDYFILE, r"handle_errors \{\s*header -Cache-Control")
        self.assertEqual(serve.IMMUTABLE_PREFIX, "/_astro/")
        self.assertEqual(serve.PORTRAITS_PREFIX, "/portraits/")

    def test_every_nginx_location_carries_the_headers(self):
        # An add_header in a location drops the inherited ones, so each
        # location includes the hardening snippet itself.
        locations = re.findall(r"location [^{]+\{(.*?)\}", NGINX_SITE, flags=re.S)
        self.assertGreaterEqual(len(locations), 7)
        for body in locations:
            self.assertIn("include /etc/nginx/snippets/vrk-headers.conf;", body)

    def test_both_configs_serve_current_and_next(self):
        self.assertIn("import vrk_site {$VRK_ROOT:/srv/vrk}/current", CADDYFILE)
        self.assertIn("import vrk_site {$VRK_ROOT:/srv/vrk}/next", CADDYFILE)
        self.assertIn("root /srv/vrk/current;", NGINX_SERVERS)
        self.assertIn("root /srv/vrk/next;", NGINX_SERVERS)


if __name__ == "__main__":
    unittest.main()
