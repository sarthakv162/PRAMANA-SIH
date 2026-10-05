import { expect, test } from '@playwright/test';

test('ask returns an answer and opens its cited source', async ({ page }) => {
  await page.goto('/');
  await page.getByLabel(/ask about/i).fill('Can traditional knowledge be patented in India?');
  await page.getByRole('button', { name: /ask pramana/i }).click();
  await expect(page.getByText(/illustrative mock response/i)).toBeVisible();
  await page.getByRole('button', { name: /open in source.*patents act/i }).first().click();
  await expect(page.getByRole('dialog', { name: /the patents act/i })).toBeVisible();
  await expect(page.locator('.pdf-viewer canvas')).toBeVisible();
});

test('standalone greetings are answered locally in the interface language', async ({ page }) => {
  let queryRequests = 0;
  page.on('request', (request) => {
    if (request.method() === 'POST' && new URL(request.url()).pathname.endsWith('/query')) queryRequests += 1;
  });
  await page.goto('/');
  await page.getByLabel(/answer language/i).selectOption('bn');
  await page.getByLabel(/ask about/i).fill('Hi');
  await page.getByRole('button', { name: /ask pramana/i }).click();
  await expect(page.getByRole('status')).toContainText('Hi! I can help you find source-grounded information');
  await expect(page.getByText(/out of scope/i)).toHaveCount(0);
  expect(queryRequests).toBe(0);
});

test('bottom composer stays available as a local research thread grows', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto('/');
  const composer = page.locator('.composer-dock');
  const welcome = page.locator('.research-welcome');
  await composer.scrollIntoViewIfNeeded();
  const composerBox = await composer.boundingBox();
  const welcomeBox = await welcome.boundingBox();
  expect(composerBox).not.toBeNull();
  expect(welcomeBox).not.toBeNull();
  expect(composerBox!.y).toBeGreaterThanOrEqual(welcomeBox!.y + welcomeBox!.height);
  expect(composerBox!.y + composerBox!.height).toBeLessThanOrEqual(845);

  await page.getByLabel(/ask about/i).fill('Can traditional knowledge be patented in India?');
  await page.getByRole('button', { name: /ask pramana/i }).click();
  await expect(page.locator('.conversation-turn')).toHaveCount(1);
  await expect(page.getByText(/illustrative mock response/i)).toBeVisible();
  await page.locator('.followup-chip').first().click();
  await expect(page.locator('.conversation-turn')).toHaveCount(2);
  await expect(composer).toBeVisible();
});

test('color theme switch persists and keeps both ambient corner orbs', async ({ page }) => {
  await page.goto('/');
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'light');
  await expect(page.locator('.corner-orb')).toHaveCount(2);
  await page.getByRole('button', { name: 'Dark mode' }).click();
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'dark');
  await expect(page.getByRole('button', { name: 'Dark mode' })).toHaveAttribute('aria-pressed', 'true');
  await page.reload();
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'dark');
  await page.getByRole('button', { name: 'Light mode' }).click();
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'light');
});

test('refusal can create an escalation ticket', async ({ page }) => {
  await page.goto('/');
  await page.getByLabel(/ask about/i).fill('What fees are listed in the indexed documents?');
  await page.getByRole('button', { name: /ask pramana/i }).click();
  await expect(page.getByText(/indexed documents don't cover/i)).toBeVisible();
  await page.getByRole('button', { name: /escalate to an ip facilitator/i }).click();
  await page.getByRole('button', { name: /submit/i }).click();
  await expect(page.getByText(/ticket created/i)).toBeVisible();
});

test('side by side result has independent jurisdiction sections', async ({ page }) => {
  await page.goto('/');
  await page.getByLabel(/ask about/i).fill('Can traditional knowledge be patented in India?');
  await page.getByRole('button', { name: /ask pramana/i }).click();
  await expect(page.getByRole('heading', { name: 'India' })).toBeVisible();
  await expect(page.getByRole('heading', { name: 'International' })).toBeVisible();
  await expect(page.getByText(/no cross-jurisdiction mixing/i)).toBeVisible();
});

test('classification wizard submits its server-driven answer', async ({ page }) => {
  await page.goto('/classify');
  await expect(page.getByText(/described in one of the authoritative books/i)).toBeVisible();
  await page.getByRole('radio', { name: 'Yes' }).check();
  await page.getByRole('button', { name: /submit/i }).click();
  await expect(page.getByRole('heading', { name: /classical \/ generic ayurvedic medicine/i })).toBeVisible();
  await expect(page.getByRole('heading', { name: /decision path/i })).toBeVisible();
});

test('receipt verifies and the tampered fixture reports invalidity', async ({ page }) => {
  await page.goto('/receipt/rcp_demo_01');
  await page.getByRole('button', { name: /verify receipt/i }).click();
  await expect(page.getByRole('heading', { name: /audit chain valid/i })).toBeVisible();
  await page.goto('/receipt/rcp_tampered_demo');
  await page.getByRole('button', { name: /verify receipt/i }).click();
  await expect(page.getByText('Merkle proof invalid')).toBeVisible();
});

test('ask page fits a basic mobile viewport without horizontal overflow', async ({ page }) => {
  await page.setViewportSize({ width: 360, height: 800 });
  await page.goto('/');
  const width = await page.evaluate(() => document.documentElement.scrollWidth);
  expect(width).toBeLessThanOrEqual(360);
});

test('interface language selection updates the shell and page copy', async ({ page }) => {
  await page.goto('/');
  await page.getByLabel(/interface language/i).selectOption('ta');
  await expect(page.getByRole('heading', { name: /ஆயுர்வேதத்தைப் பாதுகாக்கவும்/ })).toBeVisible();
  await expect(page.getByRole('link', { name: 'சஹாயக்கிடம் கேளுங்கள்' })).toBeVisible();
});

test('patent risk result exposes a clickable decision path citation', async ({ page }) => {
  await page.goto('/patent-risk');
  await page.getByRole('button', { name: /analyze formulation/i }).click();
  await expect(page.getByRole('heading', { name: /high rule indicator/i })).toBeVisible();
  await expect(page.getByRole('heading', { name: /decision path/i })).toBeVisible();
  await page.locator('.react-flow__node').first().click();
  await expect(page.getByRole('dialog', { name: /the patents act/i })).toBeVisible();
});

test('case file requests a marked mock dossier download', async ({ page }) => {
  await page.goto('/');
  await page.getByLabel(/ask about/i).fill('Can traditional knowledge be patented in India?');
  await page.getByRole('button', { name: /ask pramana/i }).click();
  await expect(page.getByText(/illustrative mock response/i)).toBeVisible();
  await page.getByRole('button', { name: /add to case file/i }).click();
  await expect(page.getByRole('button', { name: /added to case file/i })).toBeVisible();
  await page.evaluate(() => sessionStorage.setItem('pramana-workspace-key', 'explicit-mock-key'));
  await page.getByRole('link', { name: 'Cases' }).click();
  await expect(page.getByText(/not built from the selected case items/i)).toBeVisible();
  await page.getByLabel('Format').selectOption('md');
  const download = page.waitForEvent('download');
  await page.getByRole('button', { name: /download md/i }).click();
  expect((await download).suggestedFilename()).toBe('pramana-dossier.md');
});
