import { afterEach, describe, expect, it, vi } from 'vitest';
import { api, setPublicDemo, setWorkspaceKey, workspaceConnected } from './client';

describe('public demo workspace', () => {
  afterEach(() => { setPublicDemo(false); setWorkspaceKey(''); });

  it('connects without putting a fake workspace key in storage', () => {
    setWorkspaceKey('');
    expect(workspaceConnected()).toBe(false);
    setPublicDemo(true);
    expect(workspaceConnected()).toBe(true);
    expect(sessionStorage.getItem('pramana-workspace-key')).toBeNull();
    setPublicDemo(false);
    expect(workspaceConnected()).toBe(false);
  });
});

describe('classification API contract', () => {
  afterEach(() => vi.unstubAllGlobals());

  it('serializes boolean answers using the rule tree yes/no values', async () => {
    const requests: RequestInit[] = [];
    vi.stubGlobal('fetch', vi.fn(async (_input: RequestInfo | URL, init?: RequestInit) => {
      requests.push(init ?? {});
      return new Response('{}', { status: 200 });
    }));

    await api.classify({
      answers: { q_first_schedule: true, q_clinical_data: false },
      jurisdiction: 'IN',
      as_of: '2026-10-03',
      language: 'en',
    });

    expect(JSON.parse(String(requests[0]?.body)).answers).toEqual({
      q_first_schedule: 'yes',
      q_clinical_data: 'no',
    });
  });
});

describe('speech API contract', () => {
  afterEach(() => vi.unstubAllGlobals());

  it('requests WAV audio through the backend with cancellation', async () => {
    const fetchMock = vi.fn(async () => new Response('audio fixture', { headers: { 'Content-Type': 'audio/wav' } }));
    vi.stubGlobal('fetch', fetchMock);
    const controller = new AbortController();
    const blob = await api.tts('Claim text', 'hi', controller.signal);
    expect(blob.type).toBe('audio/wav');
    expect(fetchMock).toHaveBeenCalledWith('/v1/speech/tts', expect.objectContaining({
      signal: controller.signal, body: JSON.stringify({ text: 'Claim text', language: 'hi' }),
    }));
  });

  it('preserves the backend error message', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => new Response(JSON.stringify({ error: { message: 'Configure SARVAM_API_KEY.' } }), { status: 503 })));
    await expect(api.tts('Claim', 'en')).rejects.toThrow('Configure SARVAM_API_KEY.');
  });

  it('rejects a successful response containing HTML or empty audio', async () => {
    for (const response of [new Response('<html>error</html>', { headers: { 'Content-Type': 'text/html' } }), new Response('', { headers: { 'Content-Type': 'audio/wav' } })]) {
      vi.stubGlobal('fetch', vi.fn(async () => response));
      await expect(api.tts('Claim', 'en')).rejects.toThrow('invalid audio');
    }
  });
});
