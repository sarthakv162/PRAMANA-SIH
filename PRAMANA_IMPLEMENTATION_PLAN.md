# PRAMANA Final Implementation Plan

Canonical plan for SIH26045 / IP-SAKTI Sahayak. `docs/IMPLEMENTATION_PLAN.md` points here. Contracts live in `backend/app/schemas/`, generated `contracts/openapi.yaml`, and `frontend/src/api/types.gen.ts`.

## Product and model stack

Build a citation-grounded Ayurveda IP and regulatory assistant for a 16 GB MacBook. Retrieved authoritative legal evidence and server-verified citations are the basis of substantive answers.

- Native Mac Ollama runs **qwen3:4b** for answers and translation, and **qwen3-embedding:0.6b** for multilingual retrieval. Listed download sizes are [2.5 GB](https://ollama.com/library/qwen3:4b) and [639 MB](https://ollama.com/library/qwen3-embedding:0.6b); download size is not peak RAM.
- Generation uses Ollama's [JSON Schema format](https://docs.ollama.com/capabilities/structured-outputs), the existing claim schema, temperature 0, thinking disabled, and at most 8,192 context tokens. Invalid output is retried once against the same local model and then rejected.
- No cloud LLM providers, model fallback selectors, or text-inference API keys. Sarvam speech credentials are an explicit user-requested TTS exception. Loopback, `host.docker.internal`, and the same-server Docker service `ollama:11434` are allowed. Database passwords and the demo workspace key are application credentials, not provider keys.
- The containerized backend reaches native Ollama through `http://host.docker.internal:11434`. Unavailable generation produces an extractive card with server-sourced excerpts and a clear message; it never emits verified synthesis.
- Dense embeddings are 1,024 dimensions and produced by the requested Qwen embedding model. Corpus versions record the embedding model. A legacy index uses keyword search until a Qwen index passes review; incompatible vector spaces are never compared.
- mDeBERTa NLI remains a local CPU verifier. Number, date, section-reference, negation, modality and jurisdiction checks operate on server-owned evidence. Quotes never come from model output. Optional reranking stays disabled.
- Only one query/inference runs at a time. Container limits: database 1 GiB, backend 3 GiB, frontend 256 MiB, source checker 256 MiB. **12 GB (12,000,000,000 bytes) is the total peak app-services-plus-models acceptance budget**, measured during representative queries; container limits alone do not prove it. Ollama loads the two selected models with 8K context, one parallel request and limited keep-alive. macOS and browser headroom must remain available.
- Text inference, translation and embeddings remain local. Per the user's request, answer read-aloud uses Sarvam Bulbul v3 via `POST /v1/speech/tts`, with `SARVAM_API_KEY` kept on the backend. Only an explicit read-aloud action sends displayed answer text to Sarvam. Long answers are split into at most 2,500-character requests and played in order, with cancellation and audio cleanup. Missing credentials or provider failures are reported explicitly; browser speech is not silently substituted. ASR remains unavailable until separately implemented.

## Hosted demo deployment

The selected judging host is **Hugging Face ZeroGPU**, under `RJ8307`, with no managed database or paid persistent disk. Free hosting requires a verified personal account older than 30 days, and visitors have GPU quotas and queues. Account age is publicly confirmed; email verification and actual ZeroGPU allocation still need confirmation. No public deployment has been completed.

The Space runs the same React website and FastAPI routes through `gradio.Server`. Generation requests use the Gradio client and queue, then `@spaces.GPU`; a direct `/v1/query` call is rejected in this profile. The original graph performs retrieval, schema validation, citation checks, NLI verification, rendering and audit. Qwen3 4B and Qwen3 Embedding 0.6B use pinned Hugging Face weights in PyTorch; the NLI verifier also runs within the GPU allocation. JSON Schema token constraints plus Pydantic validation replace Ollama's structured-output transport. Greedy decoding, disabled thinking, the 8K context cap, disabled reranking and no remote text-inference API remain in force. The Mac profile still uses native Ollama and PostgreSQL by default.

`scripts/export-space-seed.py` exports only the actual live corpus into a checked SQLite snapshot, retaining source/version IDs, text hashes, artifact hashes and the Merkle root. It excludes staged versions and all user/audit content. The shipped legacy embedding index remains incompatible with Qwen: actual FTS5/BM25 retrieval runs until an appropriate index passes the existing review/promotion process. No failed staged corpus is promoted for deployment.

On each server start the checksum-verified snapshot is copied into a temporary SQLite file shared by the web process and ZeroGPU workers. Conversations, results, case references and receipts survive browser reloads during that server session, but reset on restart. The original 30-day expiry remains an upper bound; durable 30-day retention is deliberately waived for this demo. Judges can download dossiers to keep results. There is no hosted PostgreSQL service or paid disk.

`scripts/build-space.py` builds an upload folder containing real app code, the production website, live corpus and matching PDFs. It never publishes or pushes. Invalid PDFs are omitted and reported rather than represented as pinned originals. Sarvam uses an optional Space secret; speech usage is separate from free hosting. See `docs/HUGGING_FACE_DEPLOYMENT.md` for setup, reasoning and exact checks. The existing root Dockerfile/Compose server option remains available, but is no longer the selected judging deployment.

## Shared saved history

The local default authorizes shared history with `X-Demo-Key`; the public hosted demo opens it through `PUBLIC_DEMO_MODE=1`. Everyone uses the configured `shared-demo` workspace. History is stored in PostgreSQL locally, or temporary SQLite in the ZeroGPU demo, never fabricated or treated as evidence.

- `POST /v1/conversations`, `GET /v1/conversations`, `GET /v1/conversations/{id}`, `DELETE /v1/conversations/{id}`.
- `GET /v1/requests/{request_id}` returns saved answer results and receipt references.
- `POST /v1/query` accepts `conversation_id`, validates workspace access, saves scrubbed messages and results, and uses a bounded set of recent saved turns to resolve follow-ups. Past answers are untrusted context; all claims still cite the current, pinned corpus.
- Case-file references use `GET /v1/case-file`, `POST /v1/case-file/{request_id}`, `DELETE /v1/case-file/{request_id}`, and `PUT /v1/case-file` for order. Dossiers read actual saved results.
- Email, phone, Aadhaar, PAN and GSTIN identifiers are scrubbed before saving. This is a structured-identifier scrubber, not a guarantee that arbitrary personal names or prose are anonymized. Users see the shared-workspace and retention notice.
- Messages and result payloads expire independently after 30 days. Conversations expire after 30 days of inactivity. Delete cascades remove their messages, results and dependent case references. Expired content is filtered on reads and physically purged by maintenance.
- New audit entries retain hashes/provenance rather than full conversation/result payloads; saved content is stored separately so expiry can operate without changing the append-only receipt chain. Existing pre-migration audit entries remain historical records and are not rewritten silently.
- Workspace credentials live in browser session storage. UI preferences may remain in local storage; shared history, case results and formulation drafts are not persisted there. The query's “As of” date defaults to the browser's current local date on every opening/reload and is not saved as a preference. Historical dates apply only to the current session; saved answers retain their original dates and corpus versions.

## Routing and corpus coverage

Routing distinguishes unsupported subject matter from relevant questions for which the indexed corpus has no evidence. Routing uses deterministic domain/citation rules and local embedding exemplars; it never calls a generative model. Regulatory tool intents remain in scope for Q&A.

Explicitly named instruments constrain retrieval to their real indexed documents. An absent instrument returns no evidence rather than an answer drawn from a related law.

`corpus/coverage.yaml` maps national and international topics to official sources and explicit gaps. `GET /v1/corpus/coverage` calculates indexed/partial/not-indexed status from the actual live corpus. Coverage is document availability, not a certification that every amendment is current.

Weekly source checking compares pinned hashes with fresh official-source downloads. Changed bytes are written to a separate candidate snapshot, never into the active corpus. Required flow:

1. Source check and complete candidate snapshot.
2. Staged ingestion with immutable, version-specific PDF artifacts.
3. Authoritative HTTPS provenance, source/chunk hashes, extraction/OCR/proviso checks.
4. Golden-set retrieval evaluation with zero jurisdiction leaks, recall >= 0.80. Precision at the configured retrieval depth is reported for reviewer assessment; it is not final-answer citation precision. Report the measured values and set size; these are not synthesis-faithfulness measurements.
5. Named reviewer approval of the exact quality report hash.
6. Promotion rejects missing/stale approval, unresolved issues or changed corpus/golden-set contents.

TKDL remains a query pack unless authorized database access is supplied. Neither seed classical matches nor watchlist summaries are represented as a live TKDL search.

## Classification and UI

At most four distinct, adaptive prompts collect:

1. Intended use, therapeutic claims and proposed label claims.
2. Administration route, dosage/form and intended population.
3. Classical book/passage match and deviations.
4. Ingredients, preparation/extract, authoritative ingredient basis, novelty and marker-standardisation details.

Route to classical/generic, patent-or-proprietary, new/investigational medicinal workflow, phytopharmaceutical, Aahara/nutraceutical food workflow, or cosmetic. Missing/unknown/conflicting facts keep the relevant prompt open. Clinical-data availability alone never determines a category. Product pathways are provisional; the app's `new_drug` grouping and combined food grouping are workflows and do not assert a standalone statutory definition. Missing corpus support must be marked draft.

The category's defining clause must resolve; a generic definitions heading is insufficient. The ABS checker provides cited statutory provisions with applicability unassessed, rather than inferring an obligation, exemption or timing from incomplete facts. Patent scores are draft, unreviewed rule indicators, not probabilities; declaring clinical data alone cannot reduce the derivative rule score.

Bundle the PDF.js worker as a production asset and precache it. Source viewers fetch the PDF for the cited corpus version, render the cited physical page, and scale the server's highlight rectangles. Keep desktop navigation fixed while the main pane scrolls. Mobile navigation remains responsive and dismissible.

## Milestones and acceptance

M1 may deliver extractive source cards. M2 delivers synthesis only when an answerable question produces schema-valid, server-verified claims and resolvable supporting citations end to end.

- Representative local queries stay within the 12 GB total app/model peak budget on a 16 GB MacBook. Keep the measured report and measurement limitations.
- Real Qwen output validates against the claim schema. Unavailable or invalid generation never appears as verified synthesis.
- At least 95% of answerable in-scope routing cases are recognized across direct, weak and indirect phrasings. Separately test out-of-domain and in-scope/no-evidence cases; report corpus/golden limitations.
- Promotion requires authoritative provenance, extraction checks, golden evaluation and reviewer approval.
- Test all six classification outcomes, missing fields, ambiguity and conflicting inputs.
- Test shared access, workspace isolation, reload/resume/delete, scrubbed persistence, saved-result lookup and 30-day expiry.
- Verify the production viewer's bundled worker, cited page and highlight with the live backend, and inspect desktop/mobile layouts.

Never fabricate answers, citations, source coverage, reviewer approval, memory figures or evaluation results. Mock fixtures are allowed only in explicit test/demo mode and must remain labelled.
