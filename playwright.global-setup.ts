import { chromium, type FullConfig } from '@playwright/test';

// Before the tests: open the app once and wait for its first page load, which fetches and opens the knowledge base.
// On a fresh app without store/ that means the 150 MB demo store download first, about a minute; later page loads
// take a few seconds. A page that stops at an error (no OPENROUTER_API_KEY, a knowledge base problem) also ends the
// wait, and the tests then fail on what the page shows.
export default async function globalSetup(config: FullConfig): Promise<void> {
  const browser = await chromium.launch();
  try {
    const page = await browser.newPage();
    await page.goto(config.projects[0].use.baseURL!);
    const loaded = page.getByRole('heading', { name: 'CargoLint' }).or(page.getByRole('alert'));
    await loaded.first().waitFor({ timeout: 300_000 });
  } finally {
    await browser.close();
  }
}
