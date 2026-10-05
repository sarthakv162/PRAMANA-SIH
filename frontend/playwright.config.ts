import { defineConfig, devices } from '@playwright/test';

export default defineConfig({
  testDir: './e2e', fullyParallel: true, workers: 1, reporter: 'list', timeout: 30_000,
  use: { baseURL: process.env.PLAYWRIGHT_BASE_URL ?? 'http://127.0.0.1:4173', trace: 'retain-on-failure', ...devices['Desktop Chrome'] },
  webServer: process.env.PLAYWRIGHT_BASE_URL ? undefined : { command: 'VITE_API_MODE=mock npm run dev -- --host 127.0.0.1 --port 4173', url: 'http://127.0.0.1:4173', reuseExistingServer: !process.env.CI, timeout: 60_000 },
});
