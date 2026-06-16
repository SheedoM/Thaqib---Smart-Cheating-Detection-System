import { defineConfig, devices } from '@playwright/test';

const webURL = process.env.E2E_WEB_URL ?? 'http://127.0.0.1:5173';
const apiURL = process.env.E2E_API_URL ?? 'http://127.0.0.1:8001';
const startServers = process.env.E2E_START_SERVERS === 'true';

export default defineConfig({
  testDir: './e2e/specs',
  fullyParallel: false,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  workers: process.env.CI ? 1 : undefined,
  reporter: [['html'], ['list']],
  timeout: 60_000,
  expect: { timeout: 10_000 },
  use: {
    baseURL: webURL,
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
    video: 'retain-on-failure',
  },
  webServer: startServers
    ? [
        {
          command: 'python -m uvicorn src.thaqib.main:app --host 127.0.0.1 --port 8001',
          cwd: '..',
          url: `${apiURL}/health`,
          reuseExistingServer: true,
          timeout: 120_000,
          env: {
            ...process.env,
            APP_ENV: process.env.APP_ENV ?? 'development',
            STREAM_MANAGER_ENABLED: process.env.STREAM_MANAGER_ENABLED ?? 'false',
          },
        },
        {
          command: 'npm run dev -- --host 127.0.0.1',
          url: webURL,
          reuseExistingServer: true,
          timeout: 120_000,
        },
      ]
    : undefined,
  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
    },
  ],
});
