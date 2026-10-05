"""Run live browser checks without putting the workspace key into command output."""
import os
import subprocess
from pathlib import Path

root = Path(__file__).resolve().parents[1]
env = os.environ.copy()
values = dict(line.split('=', 1) for line in (root / '.env').read_text().splitlines() if '=' in line and not line.startswith('#'))
env.update(
    RUN_BACKEND_E2E='1', E2E_DEMO_KEY=values['DEMO_KEY'], PLAYWRIGHT_BASE_URL='http://127.0.0.1:8080',
    E2E_SARVAM_CONFIGURED='1' if values.get('SARVAM_API_KEY', '').strip().strip('\"\'') else '0',
)
(root / 'eval/results/screenshots').mkdir(parents=True, exist_ok=True)
raise SystemExit(subprocess.call(['npx', 'playwright', 'test', 'e2e/live-backend.spec.ts', '--workers=1'], cwd=root / 'frontend', env=env))
