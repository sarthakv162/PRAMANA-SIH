import { Client } from '@gradio/client';
import type { ApiError, QueryCard, QueryRequest, StageEvent } from './types';

export async function queryQueued(body: QueryRequest, signal: AbortSignal, onStage: (stage: StageEvent) => void): Promise<QueryCard> {
  signal.throwIfAborted();
  const client = await Client.connect(window.location.origin, { events: ['data', 'status'], record_history: false });
  if (signal.aborted) { client.close(); signal.throwIfAborted(); }
  let job: ReturnType<Client['submit']> | undefined;
  const abort = () => { void job?.cancel().catch(() => undefined); };
  let result: QueryCard | undefined;
  try {
    job = client.submit('/query', { request_json: JSON.stringify(body) });
    signal.addEventListener('abort', abort, { once: true });
    if (signal.aborted) { abort(); signal.throwIfAborted(); }
    for await (const event of job) {
      signal.throwIfAborted();
      if (event.type === 'status' && event.stage === 'error') {
        throw new Error(typeof event.message === 'string' ? event.message : 'The ZeroGPU queue is unavailable. Please retry later.');
      }
      if (event.type !== 'data') continue;
      const item = event.data[0] as { event: string; data: unknown; result?: QueryCard } | undefined;
      if (!item) continue;
      if (item.result) result = item.result;
      if (item.event === 'stage') onStage(item.data as StageEvent);
      if (item.event === 'result') result = item.data as QueryCard;
      if (item.event === 'error') {
        const error = item.data as ApiError | { message?: string };
        throw new Error(('error' in error ? error.error.message : error.message) || 'Query failed.');
      }
    }
    signal.throwIfAborted();
    if (!result) throw new Error('The ZeroGPU query ended without a result.');
    return result;
  } finally {
    signal.removeEventListener('abort', abort);
    job?.close_stream();
    client.close();
  }
}
