# PRAMANA — IP-SAKTI Sahayak

Proof-carrying, multilingual assistant prototype for Ayurvedic IP, access-and-benefit-sharing, and regulatory research. The implementation plan is [`docs/IMPLEMENTATION_PLAN.md`](docs/IMPLEMENTATION_PLAN.md); repository guidance is in [`CLAUDE.md`](CLAUDE.md).

## Run the local demo

Prerequisites: Docker Desktop (or Docker Engine) with the Compose plugin, 6 GB or more free disk space, and ports `5432`, `8000`, and `8080` available. No host Python or Node install is needed for the Docker demo.

```bash
cp .env.example .env
# Recommended before sharing the machine: replace the four example secrets in .env.
openssl rand -hex 32
make up
```

`make up` starts PostgreSQL with pgvector, the FastAPI service, and the React app. Backend startup provisions the runtime and ingestion database roles from `.env`, then applies Alembic migrations. The default `MOCK_MODE=1` runs fixture-backed demo responses and is visibly labeled **Mock data** in the app; fixture text and scores are illustrative, not legal content or measured system results.

- App: <http://localhost:8080>
- API docs: <http://localhost:8000/docs>
- Health and mode: <http://localhost:8000/v1/health>
- Readiness check: `curl --fail http://localhost:8000/v1/health`
- Backend tests: `make test`

`make down` stops containers and preserves the local database volume. `make logs` tails service logs.

## Demo walkthrough

1. Ask “Can traditional knowledge be patented in India?” and inspect the fixture-backed answer card. Open its evidence drawer to see the quoted span and source metadata. Mock mode does not ship the source PDF, so the UI uses the documented text-only fallback.
2. Set jurisdiction to **Side by side** and ask again to see separate India and international fixture sections.
3. Ask “What fees are listed in the indexed documents?” to get the no-evidence refusal. Submit the escalation form; the local demo stores its ticket in process memory.
4. Add an answer to the case file. Select Markdown and download the dossier. The backend demo also produces valid PDF and DOCX files from the answer fixture; the standalone MSW frontend mock supports Markdown only.
5. Open the answer receipt and choose **Verify receipt**. In fixture mode the result is explicitly mock data; use **Open tampered mock receipt** to inspect the failure-state UI.
6. Open Classification, Patent risk, ABS, TK radar, Corpus, and Evaluation from the sidebar to exercise their fixture-backed screens. Evaluation starts with zero measured questions and shows an empty-state message.

## Use the live backend pipeline

The live pipeline requires a Groq API key, network access to fetch the manifest-listed source PDFs and model weights, and sufficient RAM for local BGE-M3 embeddings plus multilingual NLI on CPU. No API key or production corpus is included. Groq is the default provider and uses `openai/gpt-oss-120b` for strict structured output; change `LLM_MODEL` to select another compatible Groq model.

1. Set `MOCK_MODE=0` and set `GROQ_API_KEY` in `.env`. Keep the database password variables and their local-development DSNs consistent if using those DSNs outside Compose.
2. Start or restart the stack with `make up`.
3. Ingest only sources listed in [`corpus/manifest.yaml`](corpus/manifest.yaml): `make ingest`. The source download and embedding steps need outbound network access and may take several minutes.
4. Review the printed report or run `make ingest-report`, then promote the staged version with `make promote V=staged-version-label` (replace the example label with the CLI label printed by `make ingest`). Promotion runs the golden retrieval smoke test and refuses promotion if the set is empty or a jurisdiction leak is observed.
5. Run retrieval evaluation with `make eval`. The current harness measures the retrieval-stage metrics in its output; it leaves faithfulness unmeasured and does not report the four-condition ablation or risk–coverage curve.

The current manifest contains two Indian Acts, not the six Tier-A documents and curated historical amendment set in the plan. A live run therefore does **not** verify international retrieval, amendment time-travel, production-quality legal coverage, or statutory correctness. Review source provenance and rule outputs with a qualified reviewer before relying on them.

## Configuration

Compose reads `.env` (copy from `.env.example`).

| Variable | Purpose |
|---|---|
| `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB` | Local database owner used for role provisioning and migrations. |
| `APP_DB_PASSWORD`, `INGEST_DB_PASSWORD` | Separate API and corpus-ingestion logins. Use unique URL-safe values. |
| `DATABASE_URL`, `DATABASE_URL_ADMIN`, `INGEST_DATABASE_URL` | SQLAlchemy DSNs for local/direct backend work; Compose supplies container-host DSNs using the password variables above. |
| `MOCK_MODE` | `1` serves clearly labeled fixtures; `0` uses the live corpus and processing pipeline. |
| `DEMO_KEY` | Required to list escalation tickets at `GET /v1/escalations`; the key is entered in the admin screen and is not embedded in frontend assets. |
| `RATE_LIMIT_REQUESTS`, `RATE_LIMIT_WINDOW_S` | Per-process, in-memory request limit per client address. |
| `REQUEST_DEADLINE_S` | Request processing budget in seconds. |
| `LLM_PROVIDER`, `LLM_MODEL` | Live text generation and non-English translation. Defaults to Groq with `openai/gpt-oss-120b`; the model must support strict JSON-schema output. Anthropic remains available with `LLM_PROVIDER=anthropic`. |
| `GROQ_API_KEY` | Preferred key variable when `LLM_PROVIDER=groq`; for compatibility, Groq also accepts `LLM_API_KEY`. |
| `LLM_API_KEY` | Legacy Groq key fallback; use it for Anthropic only when `LLM_PROVIDER=anthropic`. |
| `EMBEDDER`, `EMBED_MODEL` | Local sentence-transformer embeddings used for ingestion and retrieval. |
| `NLI_MODEL`, `NLI_TAU_HIGH`, `NLI_TAU_LOW` | Claim verification model and thresholds. |
| `BHASHINI_USER_ID`, `BHASHINI_API_KEY`, `BHASHINI_PIPELINE_ID` | Reserved for the not-yet-wired Bhashini adapter; speech endpoints return `503` and the browser uses speech APIs. |
| `VITE_API_MODE` | Frontend build mode: `live` calls the same-origin API proxy; `mock` starts MSW fixtures for frontend-only development. The app's displayed mode comes from backend health. |

## Development and verification commands

Backend commands run in the Compose service unless noted. Run `make up` first.

```bash
make test             # pytest; database-backed invariants skip without a live corpus
make lint             # Ruff
make typecheck        # mypy
make eval             # retrieval-stage evaluation, requires an ingested live corpus
make ingest-report    # print the latest manifest ingestion report
make contracts        # regenerate contracts/openapi.yaml
make types            # regenerate frontend/src/api/types.gen.ts
```

Frontend local development requires Node 22 or newer:

```bash
cd frontend
npm ci
npm run dev           # mock mode by default; VITE_API_MODE=live proxies to localhost:8000
npm run lint
npm test
npm run test:e2e
npm run build
```

The default browser suite exercises the frontend's clearly labeled MSW fixtures. To additionally verify the built UI through Nginx, FastAPI, and the local dossier/receipt endpoints, start the Compose stack and run the backend-backed Playwright flow (it reads the configured demo key without printing it):

```bash
cd frontend
set -a
. ../.env
set +a
RUN_BACKEND_E2E=1 E2E_DEMO_KEY="$DEMO_KEY" PLAYWRIGHT_BASE_URL=http://127.0.0.1:8080 npx playwright test e2e/live-backend.spec.ts
```

For the optional host backend environment, install Python 3.12 or newer, then run `make install`. The Docker workflow is the reproducible setup path.

## Prototype boundaries

- The source manifest currently covers only two Indian statutes; no real PDF files are committed. Mock fixture text is labeled illustrative.
- Bhashini ASR/TTS, IndicTrans2, OpenAI/Gemini/Ollama LLM adapters, reranking, Presidio NER, and a public human-escalation integration are not wired. Browser speech fallback and regex/checksum PII scrubbing are available.
- The current rule engine and seed datasets are prototype-sized. Review its outputs and citations; do not treat them as legal advice.
- The audit chain and corpus Merkle root are implemented in live mode. Mock receipts are demonstrations, not cryptographic verification of a live database.
- The evaluation harness does not yet measure generated-claim faithfulness, latency percentiles, risk–coverage, or ablation baselines. No placeholder scores are shown as measurements.
