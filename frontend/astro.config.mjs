import { defineConfig } from 'astro/config';

// The corpus stays outside the build. Only the generated browser assets go
// into frontend/dist, never the release artifacts in the root dist directory.
const dataOrigin = `http://127.0.0.1:${process.env.VRK_DATA_PORT || '8793'}`;
export default defineConfig({
  output: 'static',
  trailingSlash: 'always',
  server: { host: '127.0.0.1', port: 4321 },
  vite: {
    // Keep even small theme/interaction scripts external for the preview CSP.
    build: { assetsInlineLimit: 0 },
    server: {
      strictPort: true,
      proxy: {
        // The page is the site root (issue #184); serve_dashboard.py answers
        // these at the same paths production does.
        '/people-version.json': dataOrigin,
        '/people-list.json': dataOrigin,
        '/people-details.json': dataOrigin,
        '/field-labels.json': dataOrigin,
        '/data/': dataOrigin,
        '/portraits/': dataOrigin,
        '/docs/concept-map.json': dataOrigin,
      },
    },
  },
});
