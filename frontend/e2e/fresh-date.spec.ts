import { expect, test } from '@playwright/test';

test('opening ignores a saved date and sends today to the connected classification API', async ({ page }) => {
  await page.goto('/');
  const dates = await page.evaluate(() => {
    const format = (date: Date) => `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')}`;
    const now = new Date();
    const past = new Date(now); past.setDate(now.getDate() - 3);
    return { today: format(now), past: format(past) };
  });
  await expect(page.getByLabel('As of', { exact: true })).toHaveValue(dates.today);
  // Simulate a browser returning with the old persisted preference format.
  await page.evaluate((past) => localStorage.setItem('pramana-ui-state', JSON.stringify({
    version: 1, state: { asOf: past, theme: 'dark', jurisdiction: 'IN' },
  })), dates.past);
  await page.reload();
  await expect(page.getByLabel('As of', { exact: true })).toHaveValue(dates.today);
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'dark');
  await expect(page.locator('.asof-banner')).toHaveCount(0);

  await page.getByLabel('As of', { exact: true }).fill(dates.past);
  const historical = page.waitForRequest((request) => request.method() === 'POST' && new URL(request.url()).pathname.endsWith('/classify'));
  await page.getByRole('link', { name: 'Classify', exact: true }).click();
  expect((await historical).postDataJSON().as_of).toBe(dates.past);
  await expect(page.locator('.wizard-panel')).toBeVisible();

  const current = page.waitForRequest((request) => request.method() === 'POST' && new URL(request.url()).pathname.endsWith('/classify'));
  await page.reload();
  expect((await current).postDataJSON().as_of).toBe(dates.today);
  await expect(page.getByLabel('As of', { exact: true })).toHaveValue(dates.today);
  await expect(page.locator('.wizard-panel')).toBeVisible();
  expect(await page.evaluate(() => JSON.parse(localStorage.getItem('pramana-ui-state')!).state.asOf)).toBeUndefined();
});

test('returning after midnight advances today and restoring a cached page clears a historical date', async ({ page }) => {
  await page.goto('/');
  await expect(page.getByLabel('As of', { exact: true })).toBeVisible();
  const now = await page.evaluate(() => Date.now());
  const tomorrow = new Date(now); tomorrow.setDate(tomorrow.getDate() + 1);
  await page.clock.setSystemTime(tomorrow);
  const nextDate = await page.evaluate(() => {
    const date = new Date();
    return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')}`;
  });
  await page.evaluate(() => window.dispatchEvent(new Event('focus')));
  await expect(page.getByLabel('As of', { exact: true })).toHaveValue(nextDate);
  await page.getByLabel('As of', { exact: true }).fill('2020-01-01');
  await page.evaluate(() => window.dispatchEvent(new Event('focus')));
  await expect(page.getByLabel('As of', { exact: true })).toHaveValue('2020-01-01');
  await page.evaluate(() => window.dispatchEvent(new PageTransitionEvent('pageshow', { persisted: true })));
  await expect(page.getByLabel('As of', { exact: true })).toHaveValue(nextDate);
});
