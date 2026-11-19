import { test, expect } from '@playwright/test';

// The main page loads with its knowledge base: the header, the TARIC snapshot date in the Origin box and the two
// input tabs. Nothing is checked, so no model is called.
test('the main page loads', async ({ page }) => {
  await page.goto('/');
  await expect(page.getByRole('heading', { name: 'CargoLint' })).toBeVisible();
  await expect(page.getByText('Check invoice and packing-list lines before customs declaration')).toBeVisible();
  await expect(page.getByText(/^TARIC snapshot \d{4}-\d{2}-\d{2}/)).toBeVisible();
  await expect(page.getByRole('tab', { name: 'Upload file' })).toBeVisible();
  await expect(page.getByRole('tab', { name: 'Check a single line' })).toBeVisible();
  await expect(page.getByRole('button', { name: 'Load sample invoice' })).toBeVisible();
});
