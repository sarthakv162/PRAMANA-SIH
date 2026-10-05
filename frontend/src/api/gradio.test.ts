import { afterEach, describe, expect, it, vi } from 'vitest';
import { Client } from '@gradio/client';
import { queryQueued } from './gradio';
import type { QueryRequest } from './types';

vi.mock('@gradio/client', () => ({ Client: { connect: vi.fn() } }));
const request: QueryRequest = { query: 'Unit test query', jurisdiction: 'IN', language: 'en', persona: 'researcher', mode: 'text', as_of: '2026-10-05', conversation_id: null, formulation: null };

function connect(events: unknown[]) {
  const cancel = vi.fn(async () => undefined);
  const close_stream = vi.fn();
  const submit = vi.fn(() => ({ cancel, close_stream, async *[Symbol.asyncIterator]() { yield* events; } }));
  vi.mocked(Client.connect).mockResolvedValue({ submit, close: vi.fn() } as unknown as Client);
  return { submit, cancel, close_stream };
}

describe('ZeroGPU transport contract', () => {
  afterEach(() => vi.clearAllMocks());

  it('uses the queue and delivers stage events and the real result envelope', async () => {
    const result = { type: 'refusal', message: 'Unit test result' };
    const { submit, close_stream } = connect([
      { type: 'data', data: [{ event: 'stage', data: { name: 'generate', status: 'running' } }] },
      { type: 'data', data: [{ event: 'result', data: result }] },
      { type: 'data', data: [{ event: 'done', data: {} }] },
    ]);
    const stage = vi.fn();
    expect(await queryQueued(request, new AbortController().signal, stage)).toEqual(result);
    expect(submit).toHaveBeenCalledWith('/query', { request_json: JSON.stringify(request) });
    expect(stage).toHaveBeenCalledWith({ name: 'generate', status: 'running' });
    expect(close_stream).toHaveBeenCalled();
  });

  it('surfaces quota/allocation failures without inventing an answer', async () => {
    connect([{ type: 'status', stage: 'error', message: 'GPU quota exceeded' }]);
    await expect(queryQueued(request, new AbortController().signal, vi.fn())).rejects.toThrow('GPU quota exceeded');
  });

  it('keeps the audited card when the queue coalesces result and done updates', async () => {
    const result = { type: 'refusal', message: 'Unit test result' };
    connect([{ type: 'data', data: [{ event: 'done', data: {}, result }] }]);
    expect(await queryQueued(request, new AbortController().signal, vi.fn())).toEqual(result);
  });

  it('rejects incomplete streams', async () => {
    connect([{ type: 'data', data: [{ event: 'done', data: {} }] }]);
    await expect(queryQueued(request, new AbortController().signal, vi.fn())).rejects.toThrow('without a result');
  });

  it('closes the connection when submission fails before streaming', async () => {
    const close = vi.fn();
    vi.mocked(Client.connect).mockResolvedValue({
      submit: () => { throw new Error('Submission failed'); }, close,
    } as unknown as Client);
    await expect(queryQueued(request, new AbortController().signal, vi.fn())).rejects.toThrow('Submission failed');
    expect(close).toHaveBeenCalled();
  });

  it('rejects an already cancelled request before contacting Gradio', async () => {
    const abort = new AbortController();
    abort.abort();
    await expect(queryQueued(request, abort.signal, vi.fn())).rejects.toThrow();
    expect(Client.connect).not.toHaveBeenCalled();
  });
});
