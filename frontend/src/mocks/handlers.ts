import { http, HttpResponse } from 'msw';
import answerCardIn from '../../../contracts/fixtures/answer_card_in.json';
import answerCardBothHi from '../../../contracts/fixtures/answer_card_both_hi.json';
import refusalNoEvidence from '../../../contracts/fixtures/refusal_no_evidence.json';
import refusalLegalAdvice from '../../../contracts/fixtures/refusal_legal_advice.json';
import classifyQuestion from '../../../contracts/fixtures/classify_question.json';
import classifyResultClassical from '../../../contracts/fixtures/classify_result_classical.json';
import classifyResultNewDrug from '../../../contracts/fixtures/classify_result_new_drug.json';
import patentRiskHigh from '../../../contracts/fixtures/patent_risk_high.json';
import absResult from '../../../contracts/fixtures/abs_result.json';
import tkRadar from '../../../contracts/fixtures/tk_radar.json';
import receipt from '../../../contracts/fixtures/receipt.json';
import verifyOk from '../../../contracts/fixtures/verify_ok.json';
import verifyTampered from '../../../contracts/fixtures/verify_tampered.json';
import evalResults from '../../../contracts/fixtures/eval_results.json';
import type { CorpusVersion, DocumentSummary, EscalationItem, HealthResponse, QueryRequest } from '../api/types';

const apiMode = import.meta.env.VITE_API_MODE ?? 'live';
const base = apiMode === 'mock' ? '/v1' : (import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/v1').replace(/\/$/, '');

function sse(events: { event: string; data: unknown }[]) {
  let index = 0;
  const encoder = new TextEncoder();
  const stream = new ReadableStream<Uint8Array>({
    async pull(controller) {
      if (index >= events.length) { controller.close(); return; }
      const item = events[index++];
      await new Promise((resolve) => window.setTimeout(resolve, 70));
      controller.enqueue(encoder.encode(`event: ${item.event}\ndata: ${JSON.stringify(item.data)}\n\n`));
    },
  });
  return new HttpResponse(stream, { headers: { 'Content-Type': 'text/event-stream', 'Cache-Control': 'no-cache' } });
}

// §5.6 of the plan only lists fixtures for request/response bodies that go through the
// orchestrator or rule engine. GET /health, /documents, /corpus/versions and /escalations
// aren't on that list, so there's no contracts/fixtures/*.json for them — this mock data is
// built directly from the real schemas (backend/app/schemas/health.py, documents.py) and the
// doc_ids/corpus_version that already appear inside the real fixtures above, so it stays
// consistent with everything else mock mode serves.
const health: HealthResponse = {
  status: 'ok',
  mock_mode: true,
  corpus_version: '2026.09.28-a',
  models: { llm: 'qwen3:4b', embed: 'qwen3-embedding:0.6b', nli: 'mdeberta-v3-xnli' },
};

const documents: DocumentSummary[] = [
  { id: 'patents_act_1970', short_key: 'patents_act_1970', title: 'The Patents Act, 1970', doc_type: 'statute', jurisdiction: 'IN', issuer: 'Government of India', source_url: 'https://www.indiacode.nic.in/', language: 'en', in_force_from: '1970-04-20', in_force_to: null },
  { id: 'drugs_cosmetics_act_1940', short_key: 'drugs_cosmetics_act_1940', title: 'The Drugs and Cosmetics Act, 1940 & Rules, 1945', doc_type: 'statute', jurisdiction: 'IN', issuer: 'Government of India', source_url: 'https://www.indiacode.nic.in/', language: 'en', in_force_from: '1945-08-21', in_force_to: null },
  { id: 'biological_diversity_act_2002', short_key: 'biological_diversity_act_2002', title: 'The Biological Diversity Act, 2002', doc_type: 'statute', jurisdiction: 'IN', issuer: 'Government of India', source_url: 'https://www.indiacode.nic.in/', language: 'en', in_force_from: '2003-10-01', in_force_to: null },
  { id: 'trips_1994', short_key: 'trips_1994', title: 'TRIPS Agreement', doc_type: 'treaty', jurisdiction: 'INTL', issuer: 'World Trade Organization', source_url: 'https://www.wto.org/', language: 'en', in_force_from: '1995-01-01', in_force_to: null },
];

const versions: CorpusVersion[] = [
  { label: '2026.09.28-a', status: 'live', created_at: '2026-09-28T06:00:00Z' },
  { label: '2026.09.14-a', status: 'retired', created_at: '2026-09-14T06:00:00Z' },
];

const mockEscalations: EscalationItem[] = [
  { ticket_id: 'tkt_demo000001', request_id: refusalNoEvidence.request_id, contact: 'vaidya@example.in', note: 'Please confirm export duty figures.', status: 'open', created_at: '2026-09-30T10:20:00Z' },
];

// In-memory fixture references exist only in the explicitly selected MSW mode.
let mockCaseRefs: { request_id: string; summary: string; receipt_id: string }[] = [];

export const handlers = [
  http.get(`${base}/case-file`, () => HttpResponse.json(mockCaseRefs)),
  http.post(`${base}/case-file/:id`, ({ params }) => {
    const cards = [answerCardIn, answerCardBothHi, refusalNoEvidence, refusalLegalAdvice];
    const card = cards.find((item) => item.request_id === params.id);
    if (!card) return HttpResponse.json({ error: { message: 'Fixture result not found.' } }, { status: 404 });
    if (!mockCaseRefs.some((ref) => ref.request_id === card.request_id)) {
      const summary = 'sections' in card ? card.sections.flatMap((section) => section.claims)[0]?.text : card.message;
      mockCaseRefs.push({ request_id: card.request_id, receipt_id: card.receipt_id, summary: summary ?? 'Fixture result' });
    }
    return HttpResponse.json(mockCaseRefs);
  }),
  http.delete(`${base}/case-file/:id`, ({ params }) => {
    mockCaseRefs = mockCaseRefs.filter((ref) => ref.request_id !== params.id);
    return HttpResponse.json(mockCaseRefs);
  }),
  http.get(`${base}/health`, () => HttpResponse.json(health)),
  http.post(`${base}/query`, async ({ request }) => {
    const body = await request.json() as QueryRequest;
    const legalAdvice = /should i file|will i win|is this legal for me/i.test(body.query);
    const refusal = /fees|unindexed|unknown topic/i.test(body.query);
    const result = legalAdvice ? refusalLegalAdvice : refusal ? refusalNoEvidence : body.jurisdiction === 'IN' ? answerCardIn : answerCardBothHi;
    const stages = ['intake', 'frame', 'cache', 'route', 'retrieve', 'resolve', 'generate', 'verify', 'render', 'audit'];
    return sse([
      ...stages.map((name) => ({ event: 'stage', data: { name, status: 'done', ms: 12 } })),
      { event: 'result', data: result }, { event: 'done', data: {} },
    ]);
  }),
  // Explicit fixture mode exercises a short wizard path, independently of the real four-prompt classifier.
  // /classify is stateless (§6.8): the client resends all answers each call and the server
  // replays the rule tree from the root. For this isolated fixture test, this
  // mock takes the simplest correct-looking path: no answers yet -> the one seeded question
  // fixture; any answer given -> a result (classical unless the wizard's first answer is "no",
  // in which case it returns the new-drug fixture, giving both ClassifyResult fixtures a way
  // to be reached from the UI).
  http.post(`${base}/classify`, async ({ request }) => {
    const body = await request.json() as { answers: Record<string, string> };
    if (!Object.keys(body.answers).length) return HttpResponse.json(classifyQuestion);
    const firstAnswer = Object.values(body.answers)[0];
    return HttpResponse.json(firstAnswer === 'no' ? classifyResultNewDrug : classifyResultClassical);
  }),
  http.post(`${base}/patent-risk`, () => HttpResponse.json(patentRiskHigh)),
  http.post(`${base}/abs-check`, () => HttpResponse.json(absResult)),
  http.post(`${base}/tk-radar`, () => HttpResponse.json(tkRadar)),
  http.get(`${base}/documents`, ({ request }) => {
    const params = new URL(request.url).searchParams;
    const jurisdiction = params.get('jurisdiction');
    const docType = params.get('doc_type');
    const filtered = documents.filter((document) => (!jurisdiction || document.jurisdiction === jurisdiction) && (!docType || document.doc_type === docType));
    return HttpResponse.json(filtered);
  }),
  http.get(`${base}/corpus/versions`, () => HttpResponse.json(versions)),
  http.get(`${base}/spans/:id`, ({ params }) => {
    const pools: Record<string, unknown>[] = [answerCardBothHi.evidence, answerCardIn.evidence, patentRiskHigh.evidence, absResult.evidence, classifyResultClassical.evidence];
    const span = pools.map((pool) => pool[String(params.id)]).find(Boolean);
    return span ? HttpResponse.json(span) : new HttpResponse(null, { status: 404 });
  }),
  // No real fixture PDFs ship with the contract (only the plan-era provisional PDF did, which
  // this reconciliation removed). The Source Drawer already has a documented text-only
  // fallback for when highlight rects/PDF bytes aren't available, so mock mode always 503s
  // here and relies on that fallback rather than shipping a fake PDF binary.
  http.get(`${base}/documents/:id/pdf`, () => new HttpResponse(null, { status: 503 })),
  http.get(`${base}/receipts/:id`, () => HttpResponse.json(receipt)),
  http.post(`${base}/receipts/:id/verify`, ({ params }) => HttpResponse.json(String(params.id).includes('tampered') ? verifyTampered : verifyOk)),
  http.get(`${base}/eval/latest`, () => HttpResponse.json(evalResults)),
  http.post(`${base}/escalations`, async ({ request }) => {
    const body = await request.json() as { request_id: string; contact?: string; note?: string };
    const ticket: EscalationItem = { ticket_id: `tkt_demo${String(mockEscalations.length + 1).padStart(6, '0')}`, request_id: body.request_id, contact: body.contact ?? null, note: body.note ?? null, status: 'open', created_at: new Date().toISOString() };
    mockEscalations.push(ticket);
    return HttpResponse.json({ ticket_id: ticket.ticket_id, status: ticket.status });
  }),
  http.get(`${base}/escalations`, ({ request }) => request.headers.get('X-Demo-Key')
    ? HttpResponse.json(mockEscalations)
    : HttpResponse.json({ error: { code: 'unauthorized', message: 'A demo key is required.', request_id: 'req_mock' } }, { status: 401 })),
  http.post(`${base}/speech/asr`, () => HttpResponse.json({ text: 'क्या पारंपरिक ज्ञान पर पेटेंट मिल सकता है?', language: 'hi' })),
  // Fixture mode does not pretend to generate Sarvam audio.
  http.post(`${base}/speech/tts`, () => HttpResponse.json({ error: { code: 'mock_audio_unavailable', message: 'Sarvam read-aloud requires live mode and a configured backend key.', request_id: 'req_mock' } }, { status: 503 })),
  // MSW can return a real text/markdown demo document. Binary PDF/DOCX exports run through
  // the backend's fixture-backed renderers; avoid returning fake bytes with those media types.
  http.post(`${base}/dossier`, async ({ request }) => {
    const body = await request.json() as { items: string[]; format: 'pdf' | 'docx' | 'md' };
    if (body.format !== 'md') {
      return HttpResponse.json({ error: { code: 'mock_export_unavailable', message: 'Select Markdown here, or use the Docker backend demo for PDF and DOCX exports.', request_id: 'req_mock' } }, { status: 501 });
    }
    const items = body.items.map((id) => id === answerCardIn.request_id
      ? `## Answer\n\n${answerCardIn.sections.flatMap((section) => section.claims.map((claim) => claim.text)).join('\n\n')}\n\n${Object.values(answerCardIn.evidence).map((span) => `> ${span.citation_label}\n> ${span.text}`).join('\n\n')}\n\nReceipt: ${answerCardIn.receipt_id}`
      : `## Item not found\n\nNo stored fixture result for request ${id}.`).join('\n\n---\n\n');
    const markdown = `# PRAMANA compliance dossier (mock fixture)\n\n${items}\n\nInformational, not legal advice.\n`;
    return new HttpResponse(markdown, { headers: { 'Content-Type': 'text/markdown; charset=utf-8' } });
  }),
];
