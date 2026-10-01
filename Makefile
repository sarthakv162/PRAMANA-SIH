.PHONY: up down logs install test eval ingest ingest-report promote contracts types frontend-install frontend-lint frontend-test frontend-e2e frontend-build lint typecheck

SHELL := /bin/bash
.ONESHELL:
PYTHON ?= python3.12

up:
	docker compose up --build

down:
	docker compose down

logs:
	docker compose logs -f --tail=200

# Optional host development environment. The Docker workflow needs no host Python dependencies.
install:
	$(PYTHON) -m venv .venv
	.venv/bin/python -m pip install --upgrade pip
	.venv/bin/python -m pip install -e 'backend[dev]'

test:
	docker compose exec -T -e MOCK_MODE=1 backend pytest -p no:cacheprovider

eval:
	docker compose exec -T backend python /workspace/eval/run_eval.py

ingest:
	docker compose exec -T backend python -m app.ingest.cli

ingest-report:
	docker compose exec -T backend cat /workspace/corpus/raw/ingest_report.md

promote:
	@if [[ -z "$(V)" ]]; then echo 'Usage: make promote V=<staged-version-label>'; exit 2; fi
	docker compose exec -T backend python -m app.ingest.versions promote --label '$(V)'

contracts:
	docker compose exec -T backend python -c 'import yaml; from app.main import app; yaml.safe_dump(app.openapi(), open("/workspace/contracts/openapi.yaml", "w"), sort_keys=False)'

types: contracts
	npm --prefix frontend run types:generate

frontend-install:
	npm --prefix frontend ci

frontend-lint:
	npm --prefix frontend run lint

frontend-test:
	npm --prefix frontend test -- --reporter=dot

frontend-e2e:
	npm --prefix frontend run test:e2e

frontend-build:
	npm --prefix frontend run build

lint:
	docker compose exec -T backend ruff check app tests

typecheck:
	docker compose exec -T backend mypy app
