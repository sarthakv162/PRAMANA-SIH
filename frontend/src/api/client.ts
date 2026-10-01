import type {
  AbsRequest, AbsResult, ApiError, AsrResponse, ClassifyResponse, CorpusVersion, DocumentSummary,
  DossierFormat, EvalResults, EscalationItem, EscalationRequest, EscalationResponse, Formulation,
  HealthResponse, Language, PatentRisk, QueryRequest, Receipt, StageEvent, TkRadar, VerifyResult,
} from './types';
import { QUERY_STAGES } from './types';

/** backend/app/schemas/classify.py::ClassifyRequest types `answers` as `dict[str, str]` —
 * every value the server accepts is a string, even though the wizard's `multi`/`boolean`
 * input kinds produce array/boolean values in UI state. Stringify before sending so the
 * request validates against the real contract; the server-side rule tree is the authority on
 * how it expects a stringified multi-select to look (comma-joined here), which is a
 * TODO(verify) against the real rules/trees/classify.yaml once that's implemented. */
function stringifyAnswers(answers: Record<string, string | string[] | boolean>): Record<string, string> {
  return Object.fromEntries(
    Object.entries(answers).map(([key, value]) => [
      key,
      typeof value === 'string' ? value : Array.isArray(value) ? value.join(',') : String(value),
    ]),
  );
}

// Both MSW and the live reverse proxy use the same-origin API path by default.
const BASE_URL = (import.meta.env.VITE_API_BASE_URL || '/v1').replace(/\/$/, '');

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers);
  if (init.body && !(init.body instanceof FormData)) headers.set('Content-Type', 'application/json');
  const response = await fetch(`${BASE_URL}${path}`, { ...init, headers });
  if (!response.ok) {
    let body: Partial<ApiError> = {};
    try { body = await response.json() as ApiError; } catch { /* Error responses can be empty. */ }
    throw new Error(body.error?.message || `Request failed (${response.status})`);
  }
  return response.json() as Promise<T>;
}

export async function querySSE(body: QueryRequest, signal: AbortSignal, onStage: (stage: StageEvent) => void): Promise<import('./types').QueryCard> {
  const headers = new Headers({ 'Content-Type': 'application/json', Accept: 'text/event-stream' });
  const response = await fetch(`${BASE_URL}/query`, { method: 'POST', headers, body: JSON.stringify(body), signal });
  if (!response.ok || !response.body) throw new Error(`Query failed (${response.status})`);
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let pending = '';
  let eventName = '';
  let result: import('./types').QueryCard | undefined;
  while (true) {
    const { value, done } = await reader.read();
    pending += decoder.decode(value, { stream: !done });
    const blocks = pending.split(/\r?\n\r?\n/);
    pending = blocks.pop() ?? '';
    for (const block of blocks) {
      const data = block.split(/\r?\n/).filter((line) => !line.startsWith(':')).reduce((acc, line) => {
        if (line.startsWith('event:')) eventName = line.slice(6).trim();
        if (line.startsWith('data:')) acc.push(line.slice(5).trim());
        return acc;
      }, [] as string[]).join('\n');
      if (eventName === 'stage') onStage(JSON.parse(data) as StageEvent);
      if (eventName === 'result') result = JSON.parse(data) as import('./types').QueryCard;
      if (eventName === 'error') {
        const payload = JSON.parse(data) as ApiError | { code?: string; message?: string };
        const message = 'error' in payload ? payload.error.message : payload.message;
        throw new Error(message || 'The query service returned an error.');
      }
      eventName = '';
    }
    if (done) break;
  }
  if (!result) throw new Error('The query stream ended without a result.');
  return result;
}

export const api = {
  querySSE,
  health: () => request<HealthResponse>('/health'),
  classify: (body: { answers: Record<string, string | string[] | boolean>; jurisdiction: string; as_of: string; language: Language }) => request<ClassifyResponse>('/classify', { method: 'POST', body: JSON.stringify({ ...body, answers: stringifyAnswers(body.answers) }) }),
  patentRisk: (body: Formulation & { as_of: string; language: Language }) => request<PatentRisk>('/patent-risk', { method: 'POST', body: JSON.stringify(body) }),
  absCheck: (body: AbsRequest) => request<AbsResult>('/abs-check', { method: 'POST', body: JSON.stringify(body) }),
  tkRadar: (body: Formulation) => request<TkRadar>('/tk-radar', { method: 'POST', body: JSON.stringify(body) }),
  documents: (jurisdiction?: string, docType?: string) => {
    const params = new URLSearchParams();
    if (jurisdiction) params.set('jurisdiction', jurisdiction);
    if (docType) params.set('doc_type', docType);
    return request<DocumentSummary[]>(`/documents${params.size ? `?${params}` : ''}`);
  },
  versions: () => request<CorpusVersion[]>('/corpus/versions'),
  span: (id: string) => request<import('./types').EvidenceSpan>(`/spans/${encodeURIComponent(id)}`),
  pdfUrl: (id: string) => `${BASE_URL}/documents/${encodeURIComponent(id)}/pdf`,
  pdfHeaders: () => ({}),
  receipt: (id: string) => request<Receipt>(`/receipts/${encodeURIComponent(id)}`),
  verify: (id: string) => request<VerifyResult>(`/receipts/${encodeURIComponent(id)}/verify`, { method: 'POST' }),
  evalLatest: () => request<EvalResults>('/eval/latest'),
  escalate: (body: EscalationRequest) => request<EscalationResponse>('/escalations', { method: 'POST', body: JSON.stringify(body) }),
  escalations: (adminKey: string) => request<EscalationItem[]>('/escalations', { headers: { 'X-Demo-Key': adminKey } }),
  asr: (audio: Blob) => { const form = new FormData(); form.append('audio', audio, 'recording.webm'); return request<AsrResponse>('/speech/asr', { method: 'POST', body: form }); },
  tts: async (text: string, language: Language) => {
    const response = await fetch(`${BASE_URL}/speech/tts`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ text, language }) });
    if (!response.ok) throw new Error(`Speech synthesis unavailable (${response.status})`);
    return response.blob();
  },
  dossier: async (items: string[], format: DossierFormat, language: Language) => {
    const response = await fetch(`${BASE_URL}/dossier`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ items, format, language }) });
    if (!response.ok) {
      let message = `Dossier download failed (${response.status})`;
      try { const body = await response.json() as ApiError; message = body.error?.message || message; } catch { /* Non-JSON error response. */ }
      throw new Error(message);
    }
    return response.blob();
  },
  stages: QUERY_STAGES,
};
