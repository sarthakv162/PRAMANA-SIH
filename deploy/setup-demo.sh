#!/usr/bin/env bash
# Run once on the server. Generated credentials stay outside Git and Docker builds.
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p deploy/data
if [[ ! -f .env.deploy ]]; then
  umask 077
  python3 - <<'PY'
import secrets
from pathlib import Path
Path('.env.deploy').write_text('POSTGRES_PASSWORD=' + secrets.token_hex(32) + '\nSARVAM_API_KEY=\n')
PY
fi
if [[ -f backups/demo-seed.tar.gz && ! -f deploy/data/demo-seed.tar.gz ]]; then
  cp backups/demo-seed.tar.gz deploy/data/demo-seed.tar.gz
fi
printf 'Demo environment prepared. Start with:\n'
printf 'docker compose --env-file .env.deploy -p pramana-demo -f docker-compose.demo.yml up -d --build\n'
