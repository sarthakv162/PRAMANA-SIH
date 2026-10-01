# Frontend implementation audit

Scope is limited to the frontend. No API server, authentication server, database, business rules, legal decision engine, ingestion system, or deployment infrastructure was added.

## Plan-to-frontend checklist

| Plan requirement | Frontend implementation | Status | Backend dependency / handoff |
|---|---|---|---|
| Persistent jurisdiction, as-of, answer language, persona, corpus version controls | Shared top bar, persisted Zustand UI state, version popover, historical-date banner | Implemented | `/corpus/versions`; control enums and response fields follow the plan |
| Ask page and POST `/query` SSE flow | Query box, examples, voice entry, cancellable `useQuerySSE`, all ten stage states | Implemented in mock/live client | Live FastAPI SSE stream at `/v1/query` |
| Answer card, claim badges, citations, verbatim text, glossary, confidence, gaps, follow-ups, receipt and TTS | Reusable answer view, per-jurisdiction sections, source drawer, native gloss details, speech fallbacks, case and receipt actions | Implemented | `AnswerCard`, `EvidenceSpan`, `/speech/tts`, receipt link |
| Side-by-side jurisdiction mode | Separate India and International result columns, independent span counts, no-mixing note; stacks on narrow screens | Implemented | Depends on backend preserving jurisdiction-pure sections and evidence IDs |
| Source drawer and PDF highlight | Lazy pdf.js viewer, page rendering, top-left highlight rectangles, citation metadata, text-only fallback, citation navigation | Implemented; mock uses provisional PDF only for Patents Act fixture | `/documents/{doc_id}/pdf` Range support and authoritative source PDFs |
| Refusal and escalation | Refusal explanation, nearest-source slots, escalation form, ticket confirmation | Implemented | `/escalations`; no real human routing exists in the planned backend |
| Classification wizard and posture card | Server-driven input kinds, progress, why-asked disclosure, re-send answers/back action, posture matrix and React Flow path | Implemented | `/classify`; provisional question wording/value is clearly fixture-only |
| Patent risk triage | Shared formulation form, ingredient repeater, evidence toggles, gauge, 3(p)/3(e)/3(d) cards, citations and clickable decision graph | Implemented | `/patent-risk`; risk indicator is explicitly not a probability |
| ABS obligations checker | Applicant/activity/resource form, required/exempt checklist, authority/timing/citations and print stylesheet | Implemented | `/abs-check` |
| TK radar | Debounced shared formulation draft, Recharts radar, matches, overlap/missing/extra, normalized names, TKDL pack copy and seeded watchlist links | Implemented | `/tk-radar`; dataset content comes from backend response |
| Case file and dossier | Persisted request IDs and summaries, reorder/remove, format/language choices and binary download | Implemented | `/dossier`; mock downloads are valid, clearly marked sample files, not case-generated dossiers |
| Receipt and verification | Receipt metadata, hash display, chain and per-span/Merkle state, valid and tampered fixture paths | Implemented | `GET /receipts/{id}`, `POST /receipts/{id}/verify` |
| Corpus browser | Search, jurisdiction/type filters, document list, effective dates and version history | Implemented | `/documents`, `/corpus/versions` |
| Evaluation results | Metrics table and risk–coverage chart rendered only from endpoint data; empty state when no run data exists | Implemented | `/eval/latest`; mock fixture intentionally contains no measured numbers |
| Hidden admin escalation list | `/admin/escalations` route is available but not in primary navigation | Implemented | `GET /escalations`; `X-Demo-Key` sent when configured |
| Five UI languages and multilingual fonts | i18next resources for English, Hindi, Tamil, Bengali, Marathi; Noto Sans script subsets bundled locally | Implemented | Response language remains independent and backend-controlled |
| PWA/offline/mobile/accessibility | Installable manifest/icons, service worker shell, offline notice, local case summaries, responsive tables, 360px layout, semantic labels and visible focus | Implemented | Full offline result replay is limited to content already in the active view; no sensitive query text is persisted |
| Shared mock and live API modes | Central typed client; MSW fixture handlers in mock mode; environment-based live base URL and optional demo key | Implemented | Replace provisional types/fixtures after backend contract freeze |

## Provisional contract and fixture notes

`../contracts/fixtures/provisional.json` plus the adjacent provisional PDF, MD, and DOCX files are frontend-only examples assembled from the plan. They are not canonical API fixtures, authoritative source documents, real legal results, or measured evaluation data. Their purpose is to exercise UI states in `VITE_API_MODE=mock`.

`src/api/types.ts` is the one local provisional type boundary. `src/api/client.ts` is the only application API client. After the backend adds its Pydantic schemas and `../contracts/openapi.yaml`, generate OpenAPI types with `npm run types:generate`, reconcile the provisional boundary and fixtures, and keep presentation components unchanged where possible.

The plan does not fully specify some endpoint details. Confirm these during contract freeze:

- The exact `DocumentSummary` response fields, currently based on the documented `documents` data model and corpus-browser needs.
- The `GET /escalations` list item identifier and shape; the mock uses `ticket_id`, `request_id`, `status`, and `created_at`.
- The multipart field name expected by `/speech/asr`; the provisional client currently sends the audio as `audio`.
- Exact Pydantic shapes for the classification IP-posture row values, health model map, and dossier download headers/MIME behavior.
- Exact metric field names for latency in `EvalResults`; the provisional type uses `latency_p50_ms` and `latency_p95_ms`, as described in the evaluation metrics section.

