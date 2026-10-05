"""Measure a conservative total of container memory, native Ollama RSS and Docker host RSS.

Run while issuing representative queries. Shared mappings may be counted more than once;
this measures sampled working memory, not allocations between samples or every VM page.
"""
import argparse
import json
import re
import subprocess
import time
import urllib.request
from datetime import UTC, datetime
from pathlib import Path


def memory_bytes(text):
    match = re.match(r'([\d.]+)\s*([KMGTP]?i?B)', text.strip())
    if not match:
        raise ValueError(text)
    amount, unit = match.groups()
    powers = {'B': 0, 'KB': 1, 'MB': 2, 'GB': 3, 'TB': 4, 'KiB': 1, 'MiB': 2, 'GiB': 3, 'TiB': 4}
    return float(amount) * (1024 if 'i' in unit else 1000) ** powers[unit]


def sample():
    containers = subprocess.check_output(['docker', 'compose', 'ps', '-q'], text=True).split()
    stats = subprocess.check_output(['docker', 'stats', '--no-stream', '--format', '{{json .}}', *containers], text=True)
    services = [json.loads(line) for line in stats.splitlines() if line.strip()]
    container_bytes = sum(memory_bytes(item['MemUsage'].split('/')[0]) for item in services)
    processes = subprocess.check_output(['ps', '-axo', 'pid,rss,comm'], text=True)
    native = []
    docker_host = []
    for line in processes.splitlines()[1:]:
        fields = line.strip().split(None, 2)
        if len(fields) < 3:
            continue
        pid, rss, command = fields
        name = Path(command).name.lower()
        entry = {'pid': int(pid), 'rss_bytes': int(rss) * 1024, 'command': command}
        if 'ollama' in name:
            native.append(entry)
        elif name.startswith('com.docker.') or name in {'docker desktop', 'virtualization.framework'}:
            docker_host.append(entry)
    with urllib.request.urlopen('http://127.0.0.1:11434/api/ps', timeout=5) as response:
        models = json.load(response).get('models', [])
    model_allocations = sum(model['size'] for model in models)
    # Apple Metal allocations need not be fully represented by process RSS. Include the
    # reported loaded model allocations as well, conservatively double-counting shared pages.
    total = container_bytes + model_allocations + sum(p['rss_bytes'] for p in native + docker_host)
    return {'at': datetime.now(UTC).isoformat(), 'services': services, 'ollama': native,
            'docker_host': docker_host, 'loaded_models': models, 'sampled_total_bytes': total}


parser = argparse.ArgumentParser()
parser.add_argument('--seconds', type=int, default=60)
parser.add_argument('--output', default='eval/results/memory.json')
args = parser.parse_args()
samples = []
end = time.monotonic() + args.seconds
while time.monotonic() < end:
    samples.append(sample())
    time.sleep(1)
peak = max(s['sampled_total_bytes'] for s in samples)
report = {'budget_gb': 12, 'budget_bytes': 12_000_000_000,
          'sampled_peak_gb': round(peak / 1000**3, 3), 'sampled_peak_gib': round(peak / 1024**3, 3),
          'within_budget': peak <= 12_000_000_000,
          'limitations': 'Sampled container working memory plus Ollama reported model allocations and native Ollama/Docker RSS; shared mappings may be double-counted, transient peaks and all VM pages are not captured.', 'samples': samples}
Path(args.output).parent.mkdir(parents=True, exist_ok=True)
Path(args.output).write_text(json.dumps(report, indent=2))
print(json.dumps({k: v for k, v in report.items() if k != 'samples'}))
raise SystemExit(0 if report['within_budget'] else 1)
