import { defineConfig } from '@playwright/test';

export default defineConfig({
  testDir: './tests',
  fullyParallel: false,
  forbidOnly: Boolean(process.env.CI),
  retries: process.env.CI ? 1 : 0,
  workers: 1,
  reporter: [['list'], ['html', { open: 'never' }]],
  use: {
    baseURL: 'http://127.0.0.1:8792',
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
  },
  projects: [
    { name: 'desktop', use: { browserName: 'chromium', viewport: { width: 1440, height: 1000 } } },
    { name: 'tablet', use: { browserName: 'chromium', viewport: { width: 768, height: 1024 } } },
    { name: 'phone', use: { browserName: 'chromium', viewport: { width: 375, height: 812 } } },
  ],
  webServer: {
    command: 'python3 scripts/serve_dashboard.py 8792',
    cwd: '..',
    url: 'http://127.0.0.1:8792/dashboard/',
    reuseExistingServer: !process.env.CI,
    timeout: 30_000,
  },
});
