import { expect, test } from '@playwright/test';

test('asks, inspects evidence, saves a case item, exports Markdown, and verifies a receipt', async ({ page }) => {
  await page.goto('/');
  await expect(page.getByText('Mock data')).toBeVisible();
  await page.getByRole('button', { name: 'India', exact: true }).click();
  await page.getByLabel(/Ask about Ayurvedic IP/).fill('Can traditional knowledge be patented in India?');
  await page.getByRole('button', { name: 'Ask PRAMANA' }).click();
  await expect(page.getByText(/A claimed invention that is in effect traditional knowledge/)).toBeVisible();

  await page.getByRole('button', { name: /Open in source: Patents Act, 1970/ }).click();
  await expect(page.getByRole('dialog')).toContainText('The Patents Act, 1970');
  await page.getByRole('button', { name: 'Close' }).click();

  await page.getByRole('button', { name: 'Add to case file' }).click();
  await expect(page.getByRole('button', { name: 'Added to case file' })).toBeVisible();
  await page.evaluate(() => sessionStorage.setItem('pramana-workspace-key', 'explicit-mock-key'));
  await page.getByRole('link', { name: 'Cases' }).click();
  await expect(page.locator('.case-summary').first()).toContainText(/traditional knowledge/i);
  await page.getByLabel('Format').selectOption('md');
  const downloadPromise = page.waitForEvent('download');
  await page.getByRole('button', { name: /Download MD/ }).click();
  const download = await downloadPromise;
  expect(download.suggestedFilename()).toBe('pramana-dossier.md');

  await page.goto('/receipt/rcp_demo_01');
  await page.getByRole('button', { name: /Verify receipt/ }).click();
  await expect(page.getByText('Audit chain valid')).toBeVisible();
  await page.getByRole('link', { name: /Open tampered mock receipt/ }).click();
  await page.getByRole('button', { name: /Verify receipt/ }).click();
  await expect(page.getByText('Merkle proof invalid')).toBeVisible();
});

test('refuses unsupported questions and accepts an escalation', async ({ page }) => {
  await page.goto('/');
  await page.getByLabel(/Ask about Ayurvedic IP/).fill('What fees are listed in the indexed documents?');
  await page.getByRole('button', { name: 'Ask PRAMANA' }).click();
  await expect(page.getByText('The indexed documents don\'t cover this. I can\'t answer without a source.')).toBeVisible();
  await page.getByRole('button', { name: 'Escalate to an IP facilitator' }).click();
  await page.getByLabel('Contact (optional)').fill('demo@example.test');
  await page.getByRole('button', { name: 'Submit' }).click();
  await expect(page.getByText('Ticket created')).toBeVisible();
});

test('runs the classification wizard and patent risk form', async ({ page }) => {
  await page.goto('/classify');
  await expect(page.getByText(/described in one of the authoritative books/)).toBeVisible();
  await page.getByRole('radio', { name: 'Yes' }).click();
  await page.getByRole('button', { name: 'Submit' }).click();
  await expect(page.getByText('Classical / generic Ayurvedic medicine', { exact: true })).toBeVisible();

  await page.goto('/patent-risk');
  await page.getByLabel('Classical sources cited').fill('Charaka Samhita');
  await page.getByRole('button', { name: /Analyze formulation/ }).click();
  await expect(page.getByText('High rule indicator', { exact: true })).toBeVisible();
});

test('loads the corpus and reports that mock evaluation has no measurements', async ({ page }) => {
  await page.goto('/corpus');
  await expect(page.getByText('The Patents Act, 1970')).toBeVisible();
  await page.goto('/eval');
  await expect(page.getByText('No measured results are available for this run.')).toBeVisible();
});
