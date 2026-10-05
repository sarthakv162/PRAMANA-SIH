# PRAMANA — Claude Code guide
Read PRAMANA_IMPLEMENTATION_PLAN.md first (canonical source of truth). Contract: contracts/ + backend/app/schemas.

## Rules
- Contract-first: change Pydantic schemas + fixtures + CHANGELOG together; run `make contracts`.
- The LLM never writes quotes. Evidence text is materialised by the server from the DB.
- Only retrieval/repo.py may query the chunks table. Always filter by corpus_version, jurisdiction, as_of.
- The router must not call a model.
- Never log raw user text; log sha256 of the PII-scrubbed query only.
- Every rule-tree node cites a section_key. Don't invent legal content: if the corpus doesn't contain it, mark status: draft and leave a TODO(verify).
- Python 3.12, FastAPI, SQLAlchemy 2, Pydantic v2, Alembic, pytest, ruff, mypy. Type everything.
- Write tests with the code (see §11 invariants). Small commits, conventional messages.
- Scope of my work: backend/, corpus/, eval/, contracts/ (with Ritwik's approval). Do not edit frontend/.

## Commands
make up | make ingest | make promote V=... | make test | make eval | make contracts
