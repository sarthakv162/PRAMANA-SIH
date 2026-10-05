# Verification report — 4 October 2026

Later dated checks are appended below; this report's heading records the initial verification date.

The application is connected to native Ollama, PostgreSQL, real source PDFs and server citation verification. A real supported query produced verified synthesis and valid receipt proofs. **The complete plan cannot be marked finished: the rebuilt Qwen corpus fails extraction quality review and has not been promoted or approved.**

## Implemented and checked

- Native `qwen3:4b` generation, temperature 0, an 8,192-token context, JSON Schema output, and bounded retries against the same model. Native `qwen3-embedding:0.6b` produces 1,024-dimensional vectors. Remote LLM providers and text-inference keys/fallbacks have been removed. Sarvam TTS was restored by the later user request described below. Reranking stays disabled.
- Genuine source-based answers, conservative NLI/number/date/reference verification, receipt chain/Merkle proofs, immutable versioned PDFs and source provenance. Unavailable generation produces source extracts with an explicit unavailable message, without verified synthesis.
- Shared, authorized PostgreSQL conversation history and saved results; reload/resume/delete; scrubbed typed identifiers; case references; actual stored-result exports; independent 30-day expiry. New audit rows keep hashes/provenance rather than full content. Arbitrary names/prose are not guaranteed anonymized.
- Separate domain and evidence-coverage refusals. Explicitly named absent instruments cannot receive answers from unrelated statutes. Full-text search preserves ranking before trigram fallback; rule-style citation keys resolve against actual pinned rule documents.
- Four adaptive classification prompts, six outcomes, missing/unknown/conflicting inputs. Defining clauses must resolve; a generic definitions heading is insufficient. Unsupported category evidence is marked draft.
- ABS supplies a cited statutory research checklist with applicability unassessed. Missing resource facts cannot imply an exemption. Old hardcoded IP approval timing and blanket exemption conclusions were removed. Patent scores are draft rule indicators, not probabilities; claiming clinical data alone does not lower the derivative indicator.
- Weekly official-source checking, separate candidate downloads, staged ingestion, extraction/quality reports, golden retrieval evaluation, and exact-report named reviewer approval before promotion. Approval binds source files, text, vectors, locators, citation metadata and effective dates. TKDL remains a query pack and seed matching is labelled.
- Production PDF.js worker bundled and served with a JavaScript MIME type, cited physical page and highlight rendering, fixed desktop navigation/main scroll, portal-based source drawer, and corrected mobile composer/control layout.
- Exports preserve saved and source text rather than pretending to translate it. DOCX/Markdown preserve Unicode. PDF export currently supports the built-in font character set and reports an explicit error for unsupported characters; it does not deliver missing-glyph PDFs. Local speech recognition remains explicitly unavailable.
- Root [canonical plan](../PRAMANA_IMPLEMENTATION_PLAN.md); the docs plan is a pointer. Docker images rebuilt and services run in live mode.

## Measured acceptance

| Check | Observed result |
| --- | --- |
| Backend full suite | 242 passed in the isolated maintenance container |
| Frontend unit tests | 17 passed |
| Backend lint/type checks | Ruff passed; mypy passed for 122 source files |
| Frontend lint/build | Passed; production worker included in build |
| UI regressions in explicit fixture mode | 16 passed; 5 live-only cases intentionally skipped |
| Production browser tests | 5 passed against the live Docker services and actual saved answers |
| Real local synthesis | Verified claim(s), supporting evidence and receipt proofs passed |
| Real unavailable local endpoint | Extractive generation-unavailable result; actual sources and receipt; no verified synthesis |
| Routing scope benchmark | 55 cases; 100% recognition in direct/weak/indirect answerable-topic cases, in-scope/no-evidence cases and out-of-domain cases |
| Live corpus retrieval benchmark | 10 cases; 5/8 evidence cases found (reported recall 0.62); 8% precision at retrieval depth; zero jurisdiction leaks |
| Staged Qwen retrieval benchmark | 10 cases; 100% citation recall; 10% precision at retrieval depth; zero jurisdiction leaks |
| Sampled app/model memory | 8.52 GB peak against 12.00 GB budget, with both requested models loaded |

Scope recognition measures routing, **not factual answer correctness**. The retrieval golden set contains only eight evidence-bearing questions and two abstention questions. Retrieval depth/parent expansion makes retrieval precision different from final answer citation precision. Neither benchmark measures synthesized-answer faithfulness; that field remains null in the UI. The broad traditional-knowledge wording still sometimes refuses for low confidence, while the explicit cited question and its follow-up produced verified claims.

The memory run sampled 23 times over approximately 75 seconds. It included Docker container working memory, native Ollama/Docker RSS and Ollama-reported model allocations (generation context 8,192; embedding context 2,048). Shared pages may be counted twice. Sampling does not capture every transient allocation or every VM page, and is not a guarantee for all workloads. The final regression runner isolates tests from the API to avoid two verifier processes exceeding the backend's 3 GiB limit; it restores the API afterward.

## Corpus blockers

Live corpus: `2026-10-03-fed342`. Its legacy embedding space is incompatible with Qwen, so dense search is disabled and it uses keyword search. The app does not load BGE or compare incompatible vectors.

Staged corpus: `local-qwen-2026-10-04`, with 28 sources and actual Qwen embeddings. The final review reports **46 issues across 28 sources**, including:

- Twelve sources have less than 70% of extracted text indexed. Flags require inspection of operative text versus contents/schedules; they are not automatically waived. Examples: TRIPS 8.3%, New Drugs and Clinical Trials Rules 8.1%, Biological Diversity Rules 17.5%.
- 191 stored chunks lack highlight coordinates. Source offsets/text comparisons passed; missing highlights still require repair.
- Unresolved OCR/low-text-density pages, repeated or missing structural headings, unbounded/truncated tails, and extraction warnings. Some flags can concern blank/forms/notice pages; qualified review must distinguish them from missing legal content.

All source files matched their pinned hashes and authoritative provenance. Golden retrieval passed for the staged version, but that does not override extraction failures. **No reviewer identity or approval was invented, and the staged corpus was not promoted.**

Review hash: `0712fa7924946f76708cdd553dac03df0f66bfbfd78394fc307ebfc8ea547756`. Full [quality report](../eval/results/staged-quality.json). Restore/repair extraction and OCR from the official PDFs, build a fresh or correctly resumed staged version, rerun review, and obtain named reviewer approval of a passing report before promotion. Do not clear warnings merely to bypass this gate.

The final code repair accepts wrapped treaty headings, ignores wrapped inline article references, and maps each heading to its own normalized source offset. Offline parsing of the pinned PDFs now finds all 73 TRIPS articles (95.9% coverage) and all 42 CBD articles (80.9% coverage), with zero invalid offsets. Nagoya's booklet extracts pages out of reading order; it is preserved as page chunks with an explicit layout-review warning, rather than assigned to an incomplete article sequence. These [parser checks](../eval/results/parser-repair.json) measure extraction only. **The repaired parsing has not been re-ingested into the staged or live indexes**, and CBD annexes/layout/OCR, rule extraction and highlight findings still require repair and review.

The [coverage matrix](../corpus/coverage.yaml) records actual gaps, including Cosmetics Rules, designs/copyright/plant-variety legislation, WIPO GRTK, PCT, Madrid, Hague and Budapest instruments. Document availability does not certify complete extraction or current amendments.

The weekly source check recorded 26 unchanged files and two failed checks: Biological Diversity ABS Regulations 2025 and Jan Vishwas IP commencement 2024. It created no promotion candidate. Next scheduled check: `2026-10-11T11:09:34.139837+00:00`. Failures are visible in the source library; these sources have not been certified current by that check.

## Reproduce

Use the root README and configured local credentials. Do not put the workspace key into shared logs.

```sh
make test
make lint
make typecheck
make eval
npm --prefix frontend test
npm --prefix frontend run lint
npm --prefix frontend run build
npm --prefix frontend run test:e2e
python3 scripts/check_live.py
python3 scripts/run-browser-tests.py
python3 scripts/check_memory.py --seconds 75
make review-stage V=local-qwen-2026-10-04
```

`make test` temporarily stops/restores the API. Live scripts use the configured demo workspace key and actual APIs; fixture UI tests are explicitly labelled. The acceptance conversation is labelled “Live acceptance check.”

Local evidence: [live acceptance](../eval/results/live-acceptance.json), [generation unavailable](../eval/results/generation-unavailable.json), [routing](../eval/results/routing.json), [live retrieval](../eval/results/live-retrieval.json), [staged retrieval](../eval/results/staged-retrieval.json), [memory](../eval/results/memory.json), and [production screenshots](../eval/results/screenshots/). The latest-evaluation endpoint identifies the evaluated corpus version; staged evaluation is not a measurement of live retrieval.

Model/API references: [Qwen3 4B](https://ollama.com/library/qwen3:4b), [Qwen3 Embedding 0.6B](https://ollama.com/library/qwen3-embedding:0.6b), [Ollama structured outputs](https://docs.ollama.com/capabilities/structured-outputs). Download sizes do not establish peak RAM.

## Sarvam TTS restoration

The user requested restoring Sarvam for answer read-aloud. The backend now calls Sarvam Bulbul v3 using a server-only `SARVAM_API_KEY`, the current REST `language_code` field and WAV output. The frontend calls that endpoint, plays long answers in sequential chunks, supports stop/cancel/unmount cleanup and identifies the external speech provider. Local Ollama still handles answer generation, translation and embeddings. ASR is unchanged and remains unavailable.

| Restoration check | Observed result |
| --- | --- |
| Dedicated TTS backend regressions | 34 passed; transport fixtures, not real provider audio |
| Existing local inference, startup and contract regressions | 35 passed |
| Frontend unit suite | 28 passed, including audio lifecycle and API cases |
| Lint, types and production build | Passed; backend mypy checked 123 source files |
| Production browser suite after redeployment | 6 passed; Sarvam case exercised the real missing-key response |
| Actual production speech configuration | No SARVAM_API_KEY present in root .env |
| Actual provider audio verification | Not completed; requires a valid key |

The updated backend and frontend are running. The real read-aloud action reached `/v1/speech/tts`, returned HTTP 503 `sarvam_not_configured`, and displayed that error in the UI. [Speech test record](../eval/results/sarvam-tts.json) records `live_audio_verified: false`; synthetic unit WAVs are not evidence of working Sarvam speech. Add the existing key to `.env`, recreate the backend and rerun `.venv/bin/python scripts/run-browser-tests.py`; with a configured key, the speech case requires a real WAV response and advancing native playback.

## Deployment handoff — 5 October 2026

All four Compose services were running at the final handoff check. The frontend-proxied health endpoint returned live mode, the requested Qwen model names, and ready generation, embedding and NLI services. It still reported the legacy live corpus as embedding-incompatible. The root `.env` still had no Sarvam key; genuine provider playback remains unverified.

The updated 23-page Word guide was rendered and visually reviewed; its accessibility audit had zero findings and its 15 internal navigation links resolved. The root README retains the uploaded template's 25 section headings in the same order. README and deployment-guide local file links resolved, and `git diff --check` passed.

The new [deployment guide](DEPLOYMENT_GUIDE.md) recommends an always-on Mac with native Ollama and the existing Compose stack, reached through a Cloudflare Tunnel protected by Cloudflare Access. It covers the actual `127.0.0.1:8080` frontend route, shared-workspace limits, HTTPS/stream/audio verification, persistence and backups. No external tunnel, hostname, Access policy or cloud deployment was created or tested; those instructions are a deployment handoff, not a successful deployment claim.

## Simple public hosted-demo verification — 5 October 2026

The latest hosting constraint is **free only**, independent of the Mac, with no extra login gateway. No paid Railway deployment was created. Current Hugging Face Docker Spaces require a paid plan, so that option was rejected. Oracle Always Free ARM is the proposed free host; account creation, eligible capacity, networking and deployment remain pending. There is no public judging URL yet.

The root Docker image was built and tested with the real Qwen models, actual PostgreSQL/pgvector, an isolated import of the existing corpus, CPU NLI and the production frontend. The test used a two-core CPU quota and a 7 GiB app memory cap. Ollama's automatic ten-thread selection caused an initial inference timeout; the hosted image now explicitly sends `num_thread=2` for generation and embeddings. Native Mac defaults are unchanged.

The final supported query completed in **71.96 seconds**, with one verified claim and valid receipt/Merkle proofs. Shared history, results and case references survived an application restart. The real production browser test passed without a workspace key and displayed the bundled PDF worker's cited-page highlight. The screenshot was visually inspected. These are local Docker results, not measured Oracle-host performance. Raw results: `eval/results/demo-container.json`.

Additional checks passed: 71 selected backend/contract tests covering speech, generation, verification, public/private history, health and pinned-PDF integrity; 16 model/thread and deployment-configuration tests; 29 frontend unit tests; frontend lint/TypeScript/production build; backend Ruff and mypy across 123 files; Compose validation and setup-script syntax. Test groups overlap and are not added together as a total suite count. The original Mac services were restored and the backend is healthy.

The exported real-data archive is `backups/demo-seed.tar.gz` (160,120,433 bytes at this check). It includes corpus/reference/review data and pinned PDFs, with no conversations, saved results, contacts or audit payloads. Existing version status is preserved. The import does not promote the failing staged Qwen corpus.

Hash checking identified two version records for the same biodiversity PDF whose current file differs from its stored hash. No intact copy with that hash was found in the local corpus. The PDF endpoint now rejects mismatches with `409 pdf_unavailable`; matching PDFs are served normally. This source's original PDF still needs recovery or a reviewed replacement. Other previously recorded corpus quality limits and the missing real Sarvam key remain open.

## Current-date opening and corpus approval check — 5 October 2026

The user requires explicit permission before every GitHub push. This instruction is recorded in root `AGENTS.md`. At the time these checks were completed, the changes remained local and no push or remote deployment had been performed. The user subsequently explicitly authorized pushing this update to GitHub.

The running database confirms `local-qwen-2026-10-04` is staged with 46 quality issues, a null reviewer and no approval. The actual `promote()` entry point was exercised in a read-only transaction and rejected it with “Promotion requires a passing source/extraction/golden report and named reviewer approval.” Live corpus `2026-10-03-fed342` remains unchanged and uses keyword retrieval because its embedding space is incompatible with Qwen. The implemented approval gate is working; extraction repair and approved Qwen promotion remain outstanding. Machine-readable evidence: `eval/results/corpus-approval-check.json`.

The browser previously persisted `asOf`, so reopening could reuse an older query date. The frontend now stores only UI preferences, migrates old saved state and computes today's date in the browser's local time on every opening/reload. Historical selections apply during the current session. Default today mode advances after midnight on focus/visibility or the periodic check, and a page restored from the browser's back/forward cache resets to today. Clearing the date input returns to today. API reads bypass browser HTTP caching, and stale query data refreshes on window focus. Saved answer dates, source-check timestamps and corpus ingestion labels retain their original meaning; the current query date does not certify unreviewed amendments.

Validation: 35 frontend unit tests and 14 source-review backend tests passed. Frontend lint, TypeScript and production build passed. Two Playwright tests passed against the rebuilt production website at `http://127.0.0.1:8080`, including the actual classification request/response, old preference migration, reload, theme retention, midnight advancement and browser-restoration handling. The midnight and restoration events are simulated browser events for regression testing; backend classification responses are real. Only the local frontend container was rebuilt/restarted.

To repeat the date browser checks after building the local frontend:

```sh
cd frontend
PLAYWRIGHT_BASE_URL=http://127.0.0.1:8080 npx playwright test e2e/fresh-date.spec.ts --workers=1
```

Deployment instructions: `docs/DEPLOYMENT_GUIDE.md`; portable image: root `Dockerfile`; public server stack: `docker-compose.demo.yml`. The README retains all 25 second-level sections from the supplied reference format.
