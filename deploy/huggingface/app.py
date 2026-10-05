"""HF Space entry point. Build a self-contained upload folder with build-space.py."""

import argparse
import atexit
import json
import os
import shutil
import sys
import tempfile
import zipfile
from pathlib import Path

# Import before torch/transformers so ZeroGPU can emulate CUDA model placement.
import spaces

ROOT = Path(__file__).resolve().parent
# Browser uploads cannot preserve a multi-directory bundle. The optional archive
# contains the same backend, production UI and reviewed corpus as the folder build.
assets = ROOT / "pramana-assets.zip"
if assets.is_file():
    unpacked = Path(tempfile.mkdtemp(prefix="pramana-assets-")).resolve()
    atexit.register(shutil.rmtree, unpacked, ignore_errors=True)
    with zipfile.ZipFile(assets) as archive:
        for member in archive.infolist():
            if not (unpacked / member.filename).resolve().is_relative_to(unpacked):
                raise ValueError("Deployment archive path escapes its directory")
        archive.extractall(unpacked)
    ROOT = unpacked
sys.path.insert(0, str(ROOT / "backend"))

parser = argparse.ArgumentParser()
parser.add_argument(
    "--local-ollama",
    action="store_true",
    help="Local transport test using real native Ollama",
)
parser.add_argument("--port", type=int, default=7860)
args = parser.parse_args() if __name__ == "__main__" else parser.parse_args([])

os.environ.update(
    {
        "INFERENCE_RUNTIME": "ollama" if args.local_ollama else "transformers",
        "STORAGE_MODE": "ephemeral",
        "QUERY_TRANSPORT": "gradio",
        "PUBLIC_DEMO_MODE": "true",
        "MOCK_MODE": "false",
        "GRADIO_SSR_MODE": "false",
        "GRADIO_ANALYTICS_ENABLED": "false",
        "TOKENIZERS_PARALLELISM": "false",
        "REQUEST_DEADLINE_S": "110",
    }
)
runtime = Path(tempfile.mkdtemp(prefix="pramana-space-"))
atexit.register(shutil.rmtree, runtime, ignore_errors=True)
os.environ["DATABASE_URL"] = f"sqlite:///{runtime / 'session.sqlite'}"
os.environ["INGEST_DATABASE_URL"] = os.environ["DATABASE_URL"]

from app.core.portable import restore_snapshot

manifest = json.loads((ROOT / "seed-manifest.json").read_text())
restore_snapshot(
    ROOT / "corpus.sqlite", runtime / "session.sqlite", manifest["seed_sha256"]
)
if not args.local_ollama:
    from app.generation.transformers_runtime import initialize

    initialize()

from app.api.space_server import create_server, query_events
from app.main import _warm_live_models, lifespan

# Gradio's startup timeout is five seconds. Warm the real verifier before launch,
# then lifespan reuses its cache. On ZeroGPU this also places it on emulated CUDA.
_warm_live_models()

gpu_query = spaces.GPU(duration=120)(query_events)
demo = create_server(ROOT / "frontend/dist", gpu_query)

if __name__ == "__main__":
    demo.launch(
        server_name="0.0.0.0",
        server_port=args.port,
        ssr_mode=False,
        show_error=True,
        run_history=False,
        app_kwargs={"lifespan": lifespan},
        blocked_paths=[str(runtime), str(ROOT / "corpus.sqlite")],
    )
