import { defineConfig, devices } from '@playwright/test';

// Browser tests for the agentic QA platform (docs/qa-platform.md). Its workflows start the app themselves and export
// its address as BASE_URL and APP_URL; locally the webServer below starts the app when nothing answers there yet.
const baseURL = process.env.BASE_URL || process.env.APP_URL || 'http://localhost:8501';

export default defineConfig({
  testDir: 'tests/e2e-browser',
  globalSetup: './playwright.global-setup.ts', // waits for the app's first page load: the knowledge base
  // results/junit.xml is the report the platform reads (frameworks/playwright.json: report_glob results/*.xml)
  reporter: [['list'], ['junit', { outputFile: 'results/junit.xml' }]],
  use: { baseURL },
  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'] } }],
  webServer: {
    command: `streamlit run app.py --server.headless true --server.port ${new URL(baseURL).port || '8501'}`,
    url: baseURL,
    reuseExistingServer: true, // the agentic-qa workflows start the app themselves
  },
});
