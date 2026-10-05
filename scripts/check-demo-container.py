"""Exercise the hosted Docker image with real models/data in an isolated local database."""

from __future__ import annotations

import json
import os
import secrets
import shutil
import subprocess
import tempfile
import time
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
MODEL_ROOT = Path.home() / ".ollama/models"


def docker(*args: str, env: dict[str, str] | None = None) -> str:
    result = subprocess.run(["docker", *args], cwd=ROOT, env=env, check=True, capture_output=True, text=True)
    return (result.stdout + (result.stderr if args[0] == "logs" else "")).strip()


def copy_models(destination: Path) -> None:
    for model, tag in (("qwen3", "4b"), ("qwen3-embedding", "0.6b")):
        relative = Path("manifests/registry.ollama.ai/library") / model / tag
        manifest = MODEL_ROOT / relative
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(manifest, target)
        definition = json.loads(manifest.read_text())
        for layer in [definition["config"], *definition["layers"]]:
            name = layer["digest"].replace(":", "-")
            blob = destination / "blobs" / name
            blob.parent.mkdir(parents=True, exist_ok=True)
            if not blob.exists():
                shutil.copy2(MODEL_ROOT / "blobs" / name, blob)


def main() -> None:
    suffix = secrets.token_hex(4)
    network, db, web = (f"pramana-demo-{suffix}-{name}" for name in ("network", "db", "web"))
    password = secrets.token_urlsafe(24)
    stopped = False
    started: list[str] = []
    with tempfile.TemporaryDirectory(prefix="pramana-demo-data-") as temporary:
        data = Path(temporary)
        shutil.copy2(ROOT / "backups/demo-seed.tar.gz", data / "demo-seed.tar.gz")
        copy_models(data / "ollama")
        try:
            docker("network", "create", network)
            environment = {**os.environ, "POSTGRES_PASSWORD": password}
            docker("run", "-d", "--name", db, "--network", network, "--network-alias", "postgres",
                   "-e", "POSTGRES_PASSWORD", "-e", "POSTGRES_DB=pramana", "--memory", "768m",
                   "pgvector/pgvector:pg16", env=environment)
            started.append(db)
            for _attempt in range(40):
                probe = subprocess.run(["docker", "exec", db, "pg_isready", "-U", "postgres"], check=False, capture_output=True)
                if probe.returncode == 0:
                    break
                time.sleep(1)
            else:
                raise RuntimeError("The isolated test database did not start.")
            docker("compose", "stop", "backend")
            stopped = True
            environment = {**os.environ, "DATABASE_URL": f"postgresql://postgres:{password}@postgres:5432/pramana"}
            docker("run", "-d", "--name", web, "--network", network,
                   "-p", "127.0.0.1:18080:8080", "-e", "DATABASE_URL", "--memory", "7g", "--cpus", "2",
                   "--mount", f"type=bind,src={data},dst=/data",
                   "--mount", "type=volume,src=parmanacomplete_huggingface_cache,dst=/data/huggingface",
                   "pramana-demo:local", env=environment)
            started.append(web)
            with httpx.Client(base_url="http://127.0.0.1:18080", timeout=240) as client:
                deadline = time.monotonic() + 600
                while True:
                    if docker("inspect", "--format", "{{.State.Running}}", web) != "true":
                        raise RuntimeError("Hosted image exited during startup. " + docker("logs", "--tail", "35", web))
                    try:
                        health = client.get("/v1/health", timeout=3)
                        if health.status_code == 200:
                            break
                    except httpx.RequestError:
                        pass
                    if time.monotonic() > deadline:
                        raise RuntimeError("Hosted image failed to become ready. " + docker("logs", "--tail", "35", web))
                    time.sleep(2)
                status = health.json()
                assert status["mock_mode"] is False and status["public_demo_mode"] is True
                assert status["models"]["llm_ready"] and status["models"]["embed_ready"] and status["models"]["nli_ready"]
                assert status["corpus_version"] not in {"none", "unknown"}
                assert client.get("/").status_code == 200
                assert client.get("/classify").status_code == 200
                assert client.get("/v1/conversations").json() == []
                created = client.post("/v1/conversations", json={"title": "Hosted container acceptance"})
                created.raise_for_status()
                cid = created.json()["id"]
                start = time.monotonic()
                response = client.post("/v1/query", json={"query": "Summarize section 3(p) of the Patents Act and its introductory section.",
                                                          "jurisdiction": "IN", "language": "en", "conversation_id": cid})
                response.raise_for_status()
                events = response.text.split("\n\n")
                result = next(json.loads(event.split("data: ", 1)[1]) for event in events if event.startswith("event: result\n"))
                claims = [claim for section in result.get("sections", []) for claim in section["claims"]]
                if result["type"] != "answer" or not any(claim["status"] == "verified" for claim in claims):
                    (ROOT / "eval/results/demo-container-failure.json").write_text(json.dumps(result, indent=2))
                    print(docker("logs", "--tail", "70", web), flush=True)
                    raise RuntimeError(f"Real query did not produce verified synthesis: {result.get('reason', 'unverified')}")
                verification = client.post(f'/v1/receipts/{result["receipt_id"]}/verify').json()
                assert verification["chain_valid"] and all(span["merkle_proof_valid"] for span in verification["spans"])
                evidence = next(iter(result["evidence"].values()))
                pdf = client.get(evidence["pdf_url"])
                assert pdf.status_code == 200 and pdf.content.startswith(b"%PDF-")
                elapsed = round(time.monotonic() - start, 2)
                assert client.get(f"/v1/conversations/{cid}").json()["messages"][-1]["result"] == result
                client.post(f'/v1/case-file/{result["request_id"]}').raise_for_status()
                saved = client.get("/v1/case-file").json()
                docker("restart", web)
                deadline = time.monotonic() + 180
                while True:
                    try:
                        response = client.get("/v1/case-file", timeout=3)
                        if response.status_code == 200:
                            break
                    except httpx.RequestError:
                        pass
                    if time.monotonic() > deadline:
                        raise RuntimeError("Hosted image did not return after restarting.")
                    time.sleep(2)
                assert response.json() == saved
                assert client.get(f"/v1/conversations/{cid}").status_code == 200
                report = {"checked_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "health": status,
                          "query_seconds": elapsed, "result": result, "receipt_verification": verification,
                          "conversation_id": cid, "restart_persistence": True,
                          "tested_url": "http://127.0.0.1:18080", "external_deployment": False}
                (ROOT / "eval/results/demo-container.json").write_text(json.dumps(report, ensure_ascii=False, indent=2))
                print(json.dumps({"status": "passed", "corpus": status["corpus_version"], "query_seconds": elapsed,
                                  "verified_claims": sum(claim["status"] == "verified" for claim in claims),
                                  "history_and_case_survive_restart": True}))
                # The caller may run production browser checks during this short interval.
                if os.environ.get("DEMO_BROWSER_CHECK") == "1":
                    env = {**os.environ, "PLAYWRIGHT_BASE_URL": "http://127.0.0.1:18080", "RUN_PUBLIC_DEMO_E2E": "1"}
                    subprocess.run(["npx", "playwright", "test", "e2e/public-demo.spec.ts", "--workers=1"],
                                   cwd=ROOT / "frontend", env=env, check=True)
        finally:
            for name in reversed(started):
                subprocess.run(["docker", "rm", "-f", "-v", name], check=False, capture_output=True)
            subprocess.run(["docker", "network", "rm", network], check=False, capture_output=True)
            if stopped:
                docker("compose", "up", "-d", "backend")


if __name__ == "__main__":
    main()
