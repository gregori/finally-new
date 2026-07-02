import { defineConfig } from '@playwright/test';

export default defineConfig({
  testDir: './e2e',
  timeout: 45000,
  retries: 1,
  use: {
    baseURL: 'http://localhost:8001',
    screenshot: 'only-on-failure',
    trace: 'on-first-retry',
  },
});
