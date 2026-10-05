import { useCallback, useRef, useState } from 'react';
import { api } from '../api/client';
import type { QueryCard, QueryRequest, StageEvent } from '../api/types';

export function useQuerySSE() {
  const controller = useRef<AbortController | null>(null);
  const [result, setResult] = useState<QueryCard | null>(null);
  const [stages, setStages] = useState<Record<string, StageEvent['status']>>({});
  const [error, setError] = useState('');
  const [isLoading, setIsLoading] = useState(false);

  const run = useCallback(async (body: QueryRequest) => {
    controller.current?.abort();
    const nextController = new AbortController(); controller.current = nextController;
    setResult(null); setError(''); setStages({}); setIsLoading(true);
    try {
      const response = await api.querySSE(body, nextController.signal, (event) => setStages((previous) => ({ ...previous, [event.name]: event.status })));
      setResult(response); return response;
    } catch (cause) {
      if (!(cause instanceof DOMException && cause.name === 'AbortError')) setError(cause instanceof Error ? cause.message : 'Unable to complete the query.');
      return null;
    } finally { if (controller.current === nextController) setIsLoading(false); }
  }, []);

  const cancel = useCallback(() => { controller.current?.abort(); setIsLoading(false); }, []);
  const clearStatus = useCallback(() => { setError(''); setStages({}); }, []);
  return { result, stages, error, isLoading, run, cancel, clearStatus };
}
