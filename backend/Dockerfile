FROM python:3.12-slim

WORKDIR /workspace/backend

# psycopg[binary] avoids needing libpq-dev; kept minimal for the prototype.
COPY backend/pyproject.toml ./pyproject.toml
COPY backend/app ./app
COPY backend/tests ./tests
COPY backend/alembic ./alembic
COPY backend/alembic.ini ./alembic.ini
COPY corpus /workspace/corpus
COPY eval /workspace/eval
COPY contracts /workspace/contracts

# This image runs all transformer models on CPU. Install the official CPU wheel first so
# sentence-transformers doesn't pull PyPI's CUDA runtime bundles into the prototype image.
RUN pip install --no-cache-dir \
    --index-url https://pypi.org/simple \
    --extra-index-url https://download.pytorch.org/whl/cpu \
    "torch==2.13.0+cpu"
RUN pip install --no-cache-dir -e ".[dev]"

EXPOSE 8000

CMD ["sh", "-c", "python -m app.core.bootstrap_db && exec uvicorn app.main:app --host 0.0.0.0 --port 8000"]
