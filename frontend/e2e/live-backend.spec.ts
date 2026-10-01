import { expect, test } from '@playwright/test';

test('reverse proxy connects answer, source, dossier, receipt, escalation, and admin flows', async ({ page }) => {
  test.skip(process.env.RUN_BACKEND_E2E !== '1', 'Run with RUN_BACKEND_E2E=1 against the Docker Compose app.');
  test.skip(!process.env.E2E_DEMO_KEY, 'E2E_DEMO_KEY must match the local backend DEMO_KEY.');

  await page.goto('/');
  await expect(page.getByText('Mock data')).toBeVisible();
  await page.getByRole('button', { name: 'India', exact: true }).click();
  await page.getByLabel(/Ask about Ayurvedic IP/i).fill('Can traditional knowledge be patented in India?');
  await page.getByRole('button', { name: 'Ask PRAMANA' }).click();
  await expect(page.getByText(/A claimed invention that is in effect traditional knowledge/)).toBeVisible();

  await page.getByRole('button', { name: /Open in source: Patents Act, 1970/ }).click();
  await expect(page.getByRole('dialog')).toContainText('The Patents Act, 1970');
  await page.getByRole('button', { name: 'Close' }).click();
  await page.getByRole('button', { name: 'Add to case file' }).click();
  await page.getByRole('link', { name: 'Cases' }).click();
  await page.getByLabel('Format').selectOption('pdf');
  const pdfDownload = page.waitForEvent('download');
  await page.getByRole('button', { name: /Download PDF/ }).click();
  expect((await pdfDownload).suggestedFilename()).toBe('pramana-dossier.pdf');

  await page.getByRole('link', { name: /rcp_/ }).click();
  await page.getByRole('button', { name: /Verify receipt/ }).click();
  await expect(page.getByText('Audit chain valid')).toBeVisible();
  await page.getByRole('link', { name: /Open tampered mock receipt/ }).click();
  await page.getByRole('button', { name: /Verify receipt/ }).click();
  await expect(page.getByText('Merkle proof invalid')).toBeVisible();

  await page.goto('/');
  await page.getByLabel(/Ask about Ayurvedic IP/i).fill('What fees are listed in the indexed documents?');
  await page.getByRole('button', { name: 'Ask PRAMANA' }).click();
  await expect(page.getByText(/The indexed documents don.t cover this/)).toBeVisible();
  await page.getByRole('button', { name: 'Escalate to an IP facilitator' }).click();
  await page.getByRole('button', { name: 'Submit' }).click();
  await expect(page.getByText('Ticket created')).toBeVisible();
  const ticketId = (await page.locator('.success-card code').textContent()) ?? '';
  expect(ticketId).toMatch(/^tkt_/);

  await page.goto('/admin/escalations');
  await page.getByLabel('Admin access key').fill(process.env.E2E_DEMO_KEY!);
  await page.getByRole('button', { name: 'Submit' }).click();
  await expect(page.locator('table tbody tr').filter({ hasText: ticketId })).toHaveCount(1);
});

test('backend serves the classification and patent risk APIs', async ({ page }) => {
  test.skip(process.env.RUN_BACKEND_E2E !== '1', 'Run with RUN_BACKEND_E2E=1 against the Docker Compose app.');
  await page.goto('/classify');
  await expect(page.getByText(/described in one of the authoritative books/i)).toBeVisible();
  await page.getByRole('radio', { name: 'Yes' }).check();
  await page.getByRole('button', { name: 'Submit' }).click();
  await expect(page.getByRole('heading', { name: /classical \/ generic ayurvedic medicine/i })).toBeVisible();
  await page.goto('/patent-risk');
  await page.getByLabel('Classical sources cited').fill('Charaka Samhita');
  await page.getByRole('button', { name: /Analyze formulation/i }).click();
  await expect(page.getByRole('heading', { name: /high risk/i })).toBeVisible();
});
