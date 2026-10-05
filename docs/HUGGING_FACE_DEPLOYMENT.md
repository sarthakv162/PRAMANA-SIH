# PRAMANA on Hugging Face ZeroGPU

The selected demo account is **RJ8307**. This deployment runs independently of the
Mac and needs neither a hosted PostgreSQL service nor a paid persistent disk.
The deployment bundle is prepared locally; it has not been uploaded or tested on
actual ZeroGPU hardware yet.

## Why there is still a small local store

RAG needs source text and a searchable index. PostgreSQL is one way to provide
them, but it is not essential. The Space packages the real live corpus as a
SQLite file with FTS5/BM25 search, then copies it into temporary storage at startup.
SQLite is an embedded library, not another server or subscription.

The existing website also uses conversations, saved results, receipt proofs and
case-file references. Keeping those in the same temporary file preserves the
current interfaces and lets GPU workers and the web process see each other's
writes. A Python in-memory dictionary would lose that connection across the
ZeroGPU worker processes. There is no requirement for paid storage for a demo.

| Item | During browser reload | After server restart |
|---|---|---|
| Packaged legal corpus, hashes and PDFs | Available | Restored from the bundle |
| Conversations and saved answers | Retained | Reset |
| Receipts and case-file references | Retained | Reset |
| Downloaded PDF/Word dossier | Kept on the judge's device | Still kept on that device |

Thirty-day expiry remains an upper bound for saved content. This profile does not
promise thirty days of durable history. The website explicitly explains the reset. Receipt URLs include a random server-session namespace so an old receipt cannot accidentally resolve to a different new answer.

## How inference stays connected

```text
Production React website
  -> @gradio/client /query queue
  -> @spaces.GPU worker
  -> existing request graph
  -> SQLite corpus retrieval and legal/as-of/jurisdiction filters
  -> Qwen3 4B schema-constrained generation
  -> server-owned citations, legal guards and mDeBERTa NLI
  -> actual answer/refusal, saved result and receipt

Other /v1 APIs -> same temporary SQLite file, PDF artifacts and deterministic tools
```

The hosted profile uses `Qwen/Qwen3-4B` and
`Qwen/Qwen3-Embedding-0.6B` with pinned model revisions. Models are loaded and placed
on emulated CUDA at module scope; actual inference happens inside the decorated
worker. This follows [ZeroGPU's model-loading requirements](https://huggingface.co/docs/hub/spaces-zerogpu).
It does not use Ollama, a paid inference endpoint, or a connection to the Mac.
The original local profile still uses Ollama.

The generation adapter disables thinking and sampling, caps total context at 8K,
constrains tokens with the original JSON Schema and validates the final output with
Pydantic. Unsupported or truncated output cannot become verified synthesis. The
model does not decide citation validity or verification status. NLI and the legal
guards inspect the server's actual retrieved text. Reranking stays disabled.

The live snapshot currently records `legacy-bge-m3` embeddings. Those vectors are
never compared with Qwen embeddings. Retrieval uses the real keyword index.
Qwen embeddings can support routing, and dense retrieval activates only for a
compatible corpus version. The rejected staged Qwen corpus is excluded from this
bundle; deployment does not bypass reviewer approval.

## 1. Confirm free-account eligibility

[Current Hugging Face rules](https://huggingface.co/docs/hub/spaces-zerogpu) allow
eligible free personal accounts to host up to two ZeroGPU Spaces. The account must
have a verified email and be older than thirty days. RJ8307's public creation date
is 3 December 2025; email verification still needs confirmation in the account.

Choose **ZeroGPU**, not a paid dedicated GPU. Anonymous visitors have a two-minute
daily GPU quota; signed-in free visitors have five minutes under the current
published rules. Queueing, cold starts and exhausted quotas can interrupt judging.
Actual latency and memory still need measurement on the deployed Space.

## 2. Build the real corpus and upload folder

Run these from the project root, with the original local Compose backend/database
running. Use a new output folder when making a replacement bundle.

```bash
PYTHONPATH=backend .venv/bin/python scripts/export-space-seed.py \
  --from-compose --output deploy/data/space-seed

.venv/bin/python scripts/build-space.py \
  --seed deploy/data/space-seed --output deploy/data/space-demo
```

The exporter reads the current live version through the running backend. It checks
each chunk's text hash, recomputes the Merkle root, and copies only PDFs matching
their pinned file hashes. It never exports conversations, saved answers, requests,
escalation contacts or audit rows. The seed manifest records actual counts and
missing artifacts. The build script compiles the real frontend in live mode and
copies only the app, corpus, matching PDFs and original measured reports.

For the Hub's browser uploader, build the equivalent four-file package:

```bash
.venv/bin/python scripts/build-space.py \
  --seed deploy/data/space-seed --output deploy/data/space-upload-20261005 \
  --archive-assets
```

Upload `app.py`, `README.md`, `requirements.txt` and `pramana-assets.zip` together
at the Space root. The entry point unpacks the archive on startup, checks its
paths, and verifies the same corpus checksum. The archive contains the actual
backend source, production UI, corpus and matching PDFs. It does not contain model
weights, credentials or user history; pinned model weights download from the Hub.

The prepared bundle contains version `2026-10-03-fed342`, 28 source documents and
3,664 chunks. One pinned Biological Diversity Act PDF does not match its stored
hash and is omitted. Its PDF viewer endpoint remains unavailable; text retrieval
does not imply that this missing original PDF has been repaired. Other matching
PDFs, including the Patents Act cited in the end-to-end check, are included.

`deploy/data` is intentionally ignored by Git. A raw GitHub-to-Space sync of the
repository root is insufficient: it would omit this real corpus and use the wrong
entry point. Sync the prepared upload folder instead.

## 3. Create the Space and upload after explicit permission

1. Sign in to RJ8307 on Hugging Face.
2. Use the Space `RJ8307/pramana-sih`, select **Gradio**, and choose **ZeroGPU**
   hardware. Confirm the displayed allocation is free.
3. Set the Space variable `GRADIO_SSR_MODE` to `false`. This allows
   `gradio.Server` to serve the original website.
4. Upload the **contents** of `deploy/data/space-demo` to the Space root.
5. Optionally add `SARVAM_API_KEY` as a **Space secret** for TTS. Hosting is free;
   Sarvam usage has separate account limits. Without a key, speech reports unavailable.

The Hugging Face CLI can upload the prepared folder. These commands create remote
commits, so execute them only after the user explicitly authorizes that upload:

```bash
hf auth login
hf upload RJ8307/pramana-sih ./deploy/data/space-demo --repo-type space
```

Enter the token only into the CLI's authentication prompt, never into chat, code or
the frontend. The deployment scripts do not upload anything automatically.
GitHub automation can later build/sync the same bundle, but enabling automatic
publication needs a separate explicit instruction. The user's Git push restriction
remains in force.

The Space address is `https://huggingface.co/spaces/RJ8307/pramana-sih`.
This is the existing deployment target. Wait for the Space
to show **Running**, then complete the checks below before submitting it.

## 4. Test the deployment

Local unit/contract tests and production frontend build:

```bash
PYTHONPATH=backend .venv/bin/pytest backend/tests/unit backend/tests/contract -q
PYTHONPATH=backend .venv/bin/ruff check backend/app
cd frontend
npm ci
npm run test
npm run lint
npm run build
```

The portable-storage tests exercise real SQLite/FTS queries, legal filters,
immutable corpus rows, concurrent receipt appends, Merkle proofs, saved-result
tamper checks and restart reset. Adapter unit tests use clearly synthetic test
doubles; they do not prove GPU model execution.

For a local Gradio transport check, install the hosted dependencies into a suitable
environment, then run the prepared entry point with `--local-ollama`. This option
uses real native Ollama for testing the transport/storage integration; it is not
the submitted hosted runtime:

```bash
.venv/bin/python deploy/data/space-demo/app.py --local-ollama
```

On the deployed Space, check these with the real website:

1. `/v1/health` reports `mock_mode=false`, `inference_runtime=transformers`,
   `storage_mode=ephemeral`, `query_transport=gradio`, real live corpus and ready
   models. `memory_budget_gb` is a configured target, not a measurement.
2. Ask “What does section 3(p) of the Patents Act say about traditional knowledge?”
   Confirm at least one claim is verified and supported by actual citations.
3. Open the citation. The production PDF worker must load, the cited page must
   render, and its highlight must match the cited passage.
4. Open the receipt and run verification. Check chain validity and each Merkle proof.
5. Reload, resume the saved conversation, add the answer to the case file, and
   download both PDF and Word dossiers. Try a follow-up using saved context.
6. Test an out-of-domain query and an in-scope question lacking corpus evidence.
   They should have distinct refusals. A quota or allocation error must be shown
   as an error, not a verified answer.
7. Exercise the six classification outcomes, missing/ambiguous fields, patent
   risk, ABS checks and TK query packs. TKDL must not claim restricted access.
8. Restart the Space. Confirm corpus/PDFs return and previous history, case files
   and receipts are gone. An old receipt link should report unavailable.
9. If configured, test Sarvam read-aloud and cancellation. Without its secret,
   confirm the clear missing-key message.
10. Repeat as a judge in a fresh browser. Inspect queue/quota messages, latency,
    server memory and mobile/desktop scrolling before submitting the live link.

The isolated local check produced a verified section 3(p) answer, two supporting
citations, a valid receipt and Merkle proofs, resumed saved result, connected case
file, matching PDF downloads, and PDF/Word dossiers in about 9.5 seconds. It used
Ollama through the Gradio queue; **actual ZeroGPU execution is still unverified**.

## Source updates and troubleshooting

The packaged corpus is a snapshot, not a claim that all law changes are indexed
today. The website opens with today's as-of date while source/report dates remain
their real dates. Run the existing weekly source-check/staged-ingestion workflow
outside this ephemeral Space. Promote only after extraction checks, golden-set
evaluation and reviewer approval, then export a replacement bundle. This demo
does not run an unapproved ingestion or promotion on startup.

For startup errors, inspect Space build/runtime logs. Model download failure,
insufficient memory, checksum mismatch, unavailable ZeroGPU eligibility and GPU
quota exhaustion are real failures to resolve. Missing or mismatched PDFs remain
unavailable until their actual pinned artifacts are restored. No mock answers,
fallback cloud model or invented successful deployment is used.
