import { expect, test } from '@playwright/test';
import { readFileSync, writeFileSync } from 'node:fs';

const live = process.env.RUN_BACKEND_E2E === '1';
const demoKey = process.env.E2E_DEMO_KEY ?? '';
const sarvamConfigured = process.env.E2E_SARVAM_CONFIGURED === '1';
test.beforeEach(async ({ page }) => {
  test.skip(!live, 'Runs against the production Docker application.');
  test.skip(!demoKey, 'Requires the configured shared demo workspace key.');
  await page.addInitScript((key) => sessionStorage.setItem('pramana-workspace-key', key), demoKey);
});

test('production saved answer reloads and loads bundled PDF worker with cited-page highlight', async ({ page }) => {
  test.setTimeout(120_000);
  const acceptance = JSON.parse(readFileSync('../eval/results/live-acceptance.json', 'utf8'));
  await page.addInitScript((id) => sessionStorage.setItem('pramana-conversation-id', id), acceptance.conversation_id);
  await page.goto('/');
  await expect(page.locator('.mode-chip')).toHaveText('Live API');
  await expect(page.locator('.claim-card .claim-text').first()).toContainText(/traditional knowledge/i);
  await page.reload();
  await expect(page.locator('.claim-card .claim-text').first()).toBeVisible();
  const workerRequests: string[] = [];
  page.on('request', (request) => { if (request.url().includes('pdf.worker')) workerRequests.push(request.url()); });
  await page.getByRole('button', { name: /Open in source: The Patents Act, 1970/ }).first().click();
  const drawer = page.locator('.source-drawer');
  await expect(page.getByRole('heading', { name: 'The Patents Act, 1970', exact: true })).toBeVisible();
  expect((await drawer.boundingBox())?.y).toBe(0);
  const canvas = page.locator('.pdf-viewer canvas');
  await expect(canvas).toBeVisible();
  await expect.poll(() => canvas.evaluate((node) => (node as HTMLCanvasElement).width)).toBeGreaterThan(0);
  await expect.poll(() => canvas.evaluate((node) => {
    const c = node as HTMLCanvasElement;
    const data = c.getContext('2d')?.getImageData(0, 0, c.width, c.height).data;
    if (!data) return 0;
    let highlighted = 0;
    for (let i = 0; i < data.length; i += 4) if (data[i] - data[i + 1] > 8 && data[i + 1] - data[i + 2] > 15) highlighted++;
    return highlighted;
  })).toBeGreaterThan(100);
  expect(workerRequests.some((url) => new URL(url).pathname.startsWith('/assets/'))).toBeTruthy();
  await page.screenshot({ path: '../eval/results/screenshots/production-cited-pdf.png', fullPage: true, animations: 'disabled' });
  await page.getByRole('button', { name: 'Close' }).click();
  const sidebar = await page.locator('.sidebar').boundingBox();
  await page.locator('.main-content').evaluate((main) => { main.scrollTop = main.scrollHeight; });
  expect((await page.locator('.sidebar').boundingBox())?.y).toBe(sidebar?.y);
  await page.screenshot({ path: '../eval/results/screenshots/production-desktop.png', animations: 'disabled' });
});

test('shared history and case references survive reload, resume, export and delete', async ({ page }) => {
  test.setTimeout(120_000);
  const acceptance = JSON.parse(readFileSync('../eval/results/live-acceptance.json', 'utf8'));
  await page.goto('/case');
  await expect(page.locator('.case-summary').filter({ hasText: acceptance.result.request_id })).toBeVisible();
  await page.reload();
  await expect(page.locator('.case-summary').filter({ hasText: acceptance.result.request_id })).toBeVisible();
  await page.getByLabel('Format').selectOption('pdf');
  const download = page.waitForEvent('download');
  await page.getByRole('button', { name: /Download PDF/ }).click();
  expect((await download).suggestedFilename()).toBe('pramana-dossier.pdf');
  await page.goto(`/receipt/${acceptance.result.receipt_id}`);
  await page.getByRole('button', { name: /Verify receipt/ }).click();
  await expect(page.getByText('Audit chain valid')).toBeVisible();
  await expect(page.getByText(/Merkle proof valid/).first()).toBeVisible();
  const created = await page.request.post('/v1/conversations', { headers: { 'X-Demo-Key': demoKey }, data: { title: 'Browser deletion acceptance' } });
  const conversation = await created.json();
  await page.goto('/');
  await page.locator('.history-panel summary').click();
  await expect(page.getByRole('button', { name: 'Browser deletion acceptance', exact: true })).toBeVisible();
  await page.getByRole('button', { name: 'Browser deletion acceptance', exact: true }).click();
  await page.getByRole('button', { name: 'Delete conversation: Browser deletion acceptance' }).click();
  await expect(page.getByRole('button', { name: 'Browser deletion acceptance', exact: true })).toHaveCount(0);
  expect((await page.request.get(`/v1/conversations/${conversation.id}`, { headers: { 'X-Demo-Key': demoKey } })).status()).toBe(404);
});

test('four-prompt classification is connected to real source-backed results', async ({ page }) => {
  await page.goto('/classify');
  const values = [
    { 'Intended use': 'medicine', 'Diagnosis, prevention, mitigation or treatment claims?': 'yes', 'Describe the intended use and the proposed label claims': 'Traditional medicinal use for the documented indication' },
    { 'Route': 'oral', 'Dosage form, quantity, frequency and intended population': 'Classical decoction; dosage per the cited book for adults' },
    { 'Formulation, process, dosage and indication match': 'exact', "Book, passage and deviations (write 'none' if there is no source match)": 'Charaka Samhita, exact cited preparation; no deviations declared' },
    { 'All ingredients, plant parts, amounts and extraction / preparation process': 'Triphala fruits, classical equal-part preparation', 'Are all medicinal ingredients documented in authoritative classical sources?': 'yes', 'Novel indication, ingredient, process, dosage or isolated substance?': 'no', "Describe any novelty and supporting data (write 'none' if absent)": 'none', 'Purified, standardised medicinal plant extract fraction?': 'no', 'At least four bioactive / phytochemical compounds assessed qualitatively AND quantitatively?': 'no' },
  ];
  for (const fields of values) {
    for (const [label, value] of Object.entries(fields)) {
      const field = page.getByLabel(label, { exact: true });
      await expect(field).toBeVisible();
      if (await field.evaluate((node) => node.tagName === 'SELECT')) await field.selectOption(value); else await field.fill(value);
    }
    await page.getByRole('button', { name: /Submit/ }).click();
  }
  await expect(page.getByRole('heading', { name: 'Classical / generic Ayurvedic medicine', exact: true })).toBeVisible();
  await expect(page.locator('.classify-citation-chip').first()).toBeVisible();
});

test('mobile production layout has no horizontal overflow', async ({ page }) => {
  await page.setViewportSize({ width: 360, height: 800 });
  await page.goto('/');
  await expect(page.locator('.research-welcome')).toBeVisible();
  await expect(page.locator('.mode-chip')).toHaveText('Live API');
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBeTruthy();
  const hero = await page.locator('.research-welcome').boundingBox();
  const composer = await page.locator('.composer-dock').boundingBox();
  expect(composer!.y).toBeGreaterThanOrEqual(hero!.y + hero!.height);
  const dateControl = await page.getByLabel('As of', { exact: true }).boundingBox();
  if (dateControl) expect(dateControl.x + dateControl.width).toBeLessThanOrEqual(360);
  await page.screenshot({ path: '../eval/results/screenshots/production-mobile.png', fullPage: true, animations: 'disabled' });
});

test('real ABS, patent, TK, corpus and evaluation routes expose grounded results and limitations', async ({ page }) => {
  await page.goto('/abs');
  await page.getByLabel('research', { exact: true }).check();
  await page.getByLabel('Species', { exact: true }).fill('Curcuma longa');
  await page.getByRole('button', { name: /Submit/ }).click();
  await expect(page.getByText('ABS applicability has not been determined.', { exact: false })).toBeVisible();
  await expect(page.getByText('Unassessed', { exact: true })).toBeVisible();
  await expect(page.locator('.checklist-item .citation-chip').first()).toBeVisible();
  const formulation = { name: 'Live workflow validation', intended_use: 'Research', product_form: 'decoction', ingredients: [{ name: 'Curcuma longa' }], classical_sources_cited: ['Declared source for testing'], is_derivative_of_known_substance: true };
  for (const endpoint of ['patent-risk', 'tk-radar']) {
    const response = await page.request.post(`/v1/${endpoint}`, { data: formulation });
    expect(response.ok()).toBeTruthy();
    const result = await response.json();
    expect(result.receipt_id).toMatch(/^rcp_/);
    if (endpoint === 'patent-risk') {
      expect(result.assessment_status).toBe('draft');
      expect(Object.keys(result.evidence).length).toBeGreaterThan(0);
    } else {
      expect(result.tkdl_query.note).toMatch(/TKDL/i);
      expect(result.normalized_ingredients[0].canonical_latin).toMatch(/Curcuma/i);
    }
    const verification = await page.request.post(`/v1/receipts/${result.receipt_id}/verify`);
    expect((await verification.json()).chain_valid).toBeTruthy();
  }
  const invalid = await page.request.post('/v1/abs-check', { data: { applicant_type: 'indian_company', activity: ['research'], as_of: 'invalid-date' } });
  expect(invalid.status()).toBe(422);
  await page.goto('/corpus');
  await expect(page.getByText('Patent Cooperation Treaty', { exact: true })).toBeVisible();
  const coverage = await page.request.get('/v1/corpus/coverage');
  expect((await coverage.json()).topics.find((topic: { id: string }) => topic.id === 'pct').status).toBe('not_indexed');
  const evaluation = await page.request.get('/v1/eval/latest');
  expect(evaluation.ok()).toBeTruthy();
  expect((await evaluation.json()).conditions[0].faithfulness).toBeNull();
});

test('Sarvam read-aloud calls the real backend and reports speech availability honestly', async ({ page }) => {
  test.setTimeout(120_000);
  const acceptance = JSON.parse(readFileSync('../eval/results/live-acceptance.json', 'utf8'));
  await page.addInitScript((id) => sessionStorage.setItem('pramana-conversation-id', id), acceptance.conversation_id);
  // Observe native media playback without replacing it or inventing provider audio.
  await page.addInitScript(() => {
    const play = HTMLMediaElement.prototype.play;
    HTMLMediaElement.prototype.play = function () {
      (window as Window & { pramanaTtsAudio?: HTMLMediaElement }).pramanaTtsAudio = this;
      return play.call(this);
    };
  });
  await page.goto('/');
  await expect(page.locator('.claim-card .claim-text').first()).toBeVisible();
  await expect(page.getByText('Read-aloud sends the displayed answer text to Sarvam.').first()).toBeVisible();
  const button = page.getByRole('button', { name: /Listen.*Sarvam/ }).first();
  const responsePromise = page.waitForResponse((response) => response.url().endsWith('/v1/speech/tts'));
  await button.click();
  const response = await responsePromise;
  const speechResult = {
    checked_at: new Date().toISOString(), configured: sarvamConfigured,
    http_status: response.status(), provider: response.headers()['x-speech-provider'] ?? null,
    live_audio_verified: false, test_mode: 'real production UI and backend',
  };
  const saveResult = () => writeFileSync('../eval/results/sarvam-tts.json', JSON.stringify(speechResult, null, 2));
  saveResult();
  if (!sarvamConfigured) {
    expect(response.status()).toBe(503);
    expect((await response.json()).error.code).toBe('sarvam_not_configured');
    await expect(page.getByRole('alert').filter({ hasText: 'Configure SARVAM_API_KEY' }).first()).toBeVisible();
  } else {
    expect(response.status()).toBe(200);
    expect(response.headers()['content-type']).toBe('audio/wav');
    expect(response.headers()['x-speech-provider']).toBe('sarvam');
    expect((await response.body()).subarray(0, 4).toString('ascii')).toBe('RIFF');
    await expect.poll(() => page.evaluate(() => (
      (window as Window & { pramanaTtsAudio?: HTMLMediaElement }).pramanaTtsAudio?.currentTime ?? 0
    ))).toBeGreaterThan(0);
    speechResult.live_audio_verified = true;
    saveResult();
    await page.getByRole('button', { name: /Stop listening/ }).first().click();
  }
  await expect(page.getByRole('button', { name: /Listen.*Sarvam/ }).first()).toBeVisible();
});
