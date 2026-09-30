# PRAMANA — IP-SAKTI Sahayak (SIH26045)

Proof-carrying, multilingual assistant for Ayurvedic IP, ABS and drug-regulatory questions.

Source of truth: [`docs/IMPLEMENTATION_PLAN.md`](docs/IMPLEMENTATION_PLAN.md). If code and that doc
disagree, fix the doc in the same PR.

## Quick start

```bash
cp .env.example .env
make up          # docker compose up: db + backend (MOCK_MODE=1)
make contracts   # export contracts/openapi.yaml
make test        # backend unit + invariant + contract tests
```

Backend health check: `curl localhost:8000/v1/health`.

## Layout

- `backend/` — FastAPI app, ingestion, orchestrator, rules engine (owned by backend).
- `contracts/` — OpenAPI export + fixtures, the frozen contract between frontend and backend.
- `corpus/` — source manifest + raw documents (gitignored PDFs).
- `eval/` — golden set + evaluation harness.
- `frontend/` — React PWA (owned by frontend, see `frontend/README.md`).

## Ownership

See `CODEOWNERS`. Contract changes (`contracts/`) need both owners' approval.
