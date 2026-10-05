# Single web image for the hosted demo. The Mac Compose workflow keeps its own images.
FROM node:22-alpine AS frontend
WORKDIR /app
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
COPY contracts/ /contracts/
ENV VITE_API_MODE=live
RUN npm run build

# Official Ollama release, pinned to the downloaded multi-platform image digest.
FROM ollama/ollama:latest@sha256:292ee7945dfc3d5840a181f3ab86fedb1e66703e02c8af98b50f4da56b7e278c AS ollama
# This simple hosted demo uses CPU inference; omit the unused CUDA runner directories.
RUN find /usr/lib/ollama -mindepth 1 -maxdepth 1 -type d -exec rm -rf {} +

FROM ubuntu:24.04
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3 python3-venv nginx postgresql-client-16 ca-certificates \
    libopenblas0 libgomp1 libvulkan1 \
    && rm -rf /var/lib/apt/lists/* /etc/nginx/sites-enabled/default
RUN python3 -m venv /opt/venv
ENV PATH="/opt/venv/bin:${PATH}" \
    PYTHONUNBUFFERED=1 \
    HF_HOME=/data/huggingface \
    OLLAMA_MODELS=/data/ollama \
    OLLAMA_HOST=127.0.0.1:11434 \
    OLLAMA_BASE_URL=http://127.0.0.1:11434 \
    OLLAMA_NUM_PARALLEL=1 \
    OLLAMA_MAX_LOADED_MODELS=1 \
    OLLAMA_NUM_THREADS=2 \
    OMP_NUM_THREADS=2 \
    TOKENIZERS_PARALLELISM=false \
    PUBLIC_DEMO_MODE=1 \
    MOCK_MODE=0 \
    PORT=8080
COPY --from=ollama /usr/bin/ollama /usr/bin/ollama
COPY --from=ollama /usr/lib/ollama /usr/lib/ollama
COPY --from=frontend /app/dist /usr/share/nginx/html
WORKDIR /workspace/backend
COPY backend/pyproject.toml ./
RUN pip install --no-cache-dir \
    --index-url https://pypi.org/simple \
    --extra-index-url https://download.pytorch.org/whl/cpu "torch==2.13.0+cpu"
COPY backend/app ./app
COPY backend/alembic ./alembic
COPY backend/alembic.ini ./
RUN pip install --no-cache-dir -e .
COPY contracts /workspace/contracts
COPY corpus/manifest.yaml corpus/coverage.yaml /workspace/corpus-seed/
COPY eval/golden /workspace/eval/golden
COPY deploy /workspace/deploy
EXPOSE 8080
CMD ["python", "/workspace/deploy/start.py"]
