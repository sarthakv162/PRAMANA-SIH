.PHONY: up down ingest promote test eval contracts types lint typecheck

BACKEND := backend
VENV_ACTIVATE := source .venv/bin/activate

up:
	docker compose up --build

down:
	docker compose down

# Ingestion CLI lands in M1; this target is the documented entrypoint ahead of that.
ingest:
	cd $(BACKEND) && $(VENV_ACTIVATE) && python -m app.ingest.cli

# Promotes a staged corpus_version to live after running the eval smoke test (§6.2 step 8).
promote:
	cd $(BACKEND) && $(VENV_ACTIVATE) && python -m app.ingest.versions promote --label "$(V)"

test:
	cd $(BACKEND) && $(VENV_ACTIVATE) && pytest

# Golden-set evaluation harness lands in M5; placeholder entrypoint per §9.
eval:
	cd $(BACKEND) && $(VENV_ACTIVATE) && python ../eval/run_eval.py

# Exports contracts/openapi.yaml straight from the Pydantic/FastAPI schemas — the
# generated file, not a hand-maintained one, is the thing CI diffs against (invariant I7).
contracts:
	cd $(BACKEND) && $(VENV_ACTIVATE) && python -c "\
import yaml; \
from app.main import app; \
yaml.safe_dump(app.openapi(), open('../contracts/openapi.yaml', 'w'), sort_keys=False)"

# Frontend isn't scaffolded yet (M0 frontend work is Ritwik's); once it is, this runs
# openapi-typescript against contracts/openapi.yaml to produce frontend/src/api/types.gen.ts.
types:
	@echo "frontend not scaffolded yet — will run: cd frontend && npx openapi-typescript ../contracts/openapi.yaml -o src/api/types.gen.ts"

lint:
	cd $(BACKEND) && $(VENV_ACTIVATE) && ruff check app

typecheck:
	cd $(BACKEND) && $(VENV_ACTIVATE) && mypy app
