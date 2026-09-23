import { defineConfig } from 'astro/config';

// The corpus stays outside the build. Only the generated browser assets go
// into frontend/dist, never the release artifacts in the root dist directory.
const dataOrigin = `http://127.0.0.1:${process.env.VRK_DATA_PORT || '8793'}`;
export default defineConfig({
  output: 'static',
  base: '/dashboard',
  trailingSlash: 'always',
  server: { host: '127.0.0.1', port: 4321 },
  vite: {
    // Keep even small theme/interaction scripts external for the preview CSP.
    build: { assetsInlineLimit: 0 },
    server: {
      strictPort: true,
      proxy: {
        // Astro removes the configured base before Vite's proxy middleware.
        '/people.json': { target: dataOrigin, rewrite: path => `/dashboard${path}` },
        '/field-labels.json': { target: dataOrigin, rewrite: path => `/dashboard${path}` },
        '/data/': dataOrigin,
        '/docs/concept-map.json': dataOrigin,
      },
    },
  },
});
