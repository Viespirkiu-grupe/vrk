# Astro and Viešpirkiai design migration (#177)

Work branch: `codex/177-astro-design-migration`. This branch is for local
review before a merge; it does not deploy or change the public site.

## Plan

1. [#178 — Foundation](https://github.com/Viespirkiu-grupe/vrk/issues/178):
   introduce a static Astro build, extract browser code from the MVP HTML,
   and serve the build at the established `/dashboard/` URL.
2. [#179 — Shared design](https://github.com/Viespirkiu-grupe/vrk/issues/179):
   adopt the main site's typography, brand, neutral palette, controls,
   header/footer and reusable Astro components.
3. [#180 — Views and interaction](https://github.com/Viespirkiu-grupe/vrk/issues/180):
   carry all existing views into the new layout, including responsive,
   keyboard, loading, empty and error behavior.
4. [#181 — Verification and preview](https://github.com/Viespirkiu-grupe/vrk/issues/181):
   adapt the regression suite, exercise the built application, document
   development and preview, and push the reviewed implementation branch.

## Architecture

`frontend/` is an independent npm project. Astro generates static HTML,
locally hosted assets and bundled JavaScript into `frontend/dist/`; it never
copies or packages the corpus. There is no React runtime or database server.
The Python scraper, its data model and the release-building commands remain
independent of the frontend build. The repository's root `dist/` still holds
data release artifacts and is never an Astro output directory.

The browser still loads `dashboard/people.json` and
`dashboard/field-labels.json`, `docs/concept-map.json`, and the selected
candidate records/portraits under `data/`. Person IDs and legacy name/birth
hashes keep the same URL contract. Searches and facets remain local to the
index; records are fetched only when required by a detail/comparison view.

`scripts/serve_dashboard.py` maps `/dashboard/` to the Astro build and serves
the existing data URLs with gzip and conditional requests. It binds only to
loopback, checks the Host, denies repository/source paths and directory
listings, and keeps its response headers. The old source HTML is retired;
a missing build produces an explicit setup diagnostic rather than silently
running a second implementation.

## Design reference

The reference is [viespirkiai.org](https://viespirkiai.org/) and
[`Viespirkiu-grupe/viespirkiai` at d445130](https://github.com/Viespirkiu-grupe/viespirkiai/tree/d445130107984313e67e317edae58301596bce5f).
The main site's `src/design-system/foundation` and shared header/footer,
search, result and table components establish the visual language: Ubuntu,
stone neutrals, sky links, fine borders, small radii and restrained controls.
VRK's own Astro components implement that language without importing the
procurement application's backend or unrelated scripts. Copied brand/font
assets retain their separate notices in `frontend/public/`.

## Review gates

- A clean checkout installs, checks and builds without `data/` or a person index.
- The existing Python/Node data-formatting regressions still execute the
  maintained source; there is no stale HTML fallback in tests.
- Browser tests load the real build with small synthetic data fixtures and
  cover search, filters, links/history, comparison, CSV, all aggregate views,
  errors, and desktop/tablet/phone layouts.
- Real local corpus checks cover populated records, all main views, and
  responsive layout in the running preview.
- Data interpretation remains unchanged: typed absence, campaign-level
  denominators, litas conversion, differing financial measures, election
  terms and party lineages retain their established semantics.
- The feature branch is committed and pushed. Issue #177 stays open for the
  user's design review and eventual merge decision.

See [DASHBOARD.md](DASHBOARD.md) for commands and the full data/interaction
contract. The related open questions #175 and #176 are not resolved by
changing how nationality is interpreted during a visual migration.

## Verification record

The completed implementation passes Astro diagnostics and the production
build, 183 dashboard/domain regression tests (1,420 subtests), 22 serving
tests (20 subtests), and 33 browser checks across desktop, tablet and phone.
Three browser cases are intentionally skipped outside their target viewport.
The browser suite uses one worker and synthetic records against the actual
production build; CI also runs the full Python suite from a clean checkout.

The local preview was reviewed with the full index of 60,568 people and
113,073 candidacies across 55 elections, including person history, records,
financial charts and every aggregate view in light and dark themes. Narrow
320-pixel layouts keep wide tables inside their own scroll containers.
The development server's data proxy and shutdown were also checked with
the real index and candidate records.
