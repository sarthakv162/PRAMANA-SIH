"""Build a reviewable Hugging Face upload folder. Does not publish or push."""

import argparse
import json
import shutil
import subprocess
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def build(seed: Path, output: Path, skip_frontend_build: bool = False, archive_assets: bool = False) -> None:
    if output.exists():
        raise ValueError(
            "Choose a new output folder to avoid overwriting a deployment bundle"
        )
    manifest = json.loads((seed / "seed-manifest.json").read_text())
    if (
        manifest["corpus_status"] != "live"
        or manifest["includes_staged_versions"]
        or manifest["includes_user_content"]
    ):
        raise ValueError(
            "Only a live corpus snapshot without user content can be bundled"
        )
    if not skip_frontend_build:
        subprocess.run(
            ["npm", "run", "build"],
            cwd=ROOT / "frontend",
            check=True,
            env=__import__("os").environ
            | {"VITE_API_MODE": "live", "VITE_API_BASE_URL": "/v1"},
        )
    output.mkdir(parents=True)
    for name in ("app.py", "README.md", "requirements.txt"):
        shutil.copyfile(ROOT / "deploy/huggingface" / name, output / name)
    shutil.copytree(
        ROOT / "backend/app",
        output / "backend/app",
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
    )
    shutil.copytree(ROOT / "frontend/dist", output / "frontend/dist")
    shutil.copytree(seed / "corpus", output / "corpus")
    for name in ("coverage.yaml", "manifest.yaml"):
        shutil.copyfile(ROOT / "corpus" / name, output / "corpus" / name)
    for name in ("corpus.sqlite", "seed-manifest.json"):
        shutil.copyfile(seed / name, output / name)
    # Measured evaluation/source-check reports keep their original dates and results.
    for relative in ("eval/results/latest.json", "corpus/raw/source-check-latest.json"):
        source = ROOT / relative
        if source.is_file():
            destination = output / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, destination)
    if archive_assets:
        # Four root files can be uploaded through the Hub's authenticated browser UI.
        roots = [path for path in output.iterdir() if path.name not in {"app.py", "README.md", "requirements.txt"}]
        with zipfile.ZipFile(output / "pramana-assets.zip", "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for root in roots:
                for path in ([root] if root.is_file() else sorted(root.rglob("*"))):
                    if path.is_file():
                        archive.write(path, path.relative_to(output))
        for root in roots:
            if root.is_dir():
                shutil.rmtree(root)
            else:
                root.unlink()
    print(
        json.dumps(
            {
                "folder": str(output),
                "corpus_version": manifest["corpus_version"],
                "bytes": sum(
                    p.stat().st_size for p in output.rglob("*") if p.is_file()
                ),
                "missing_pdfs": manifest["unavailable_artifacts"],
                "published": False,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--archive-assets",
        action="store_true",
        help="Package assets into one zip for the browser's flat file upload",
    )
    parser.add_argument(
        "--skip-frontend-build",
        action="store_true",
        help="Only for a frontend build already tested",
    )
    args = parser.parse_args()
    build(args.seed.resolve(), args.output.resolve(), args.skip_frontend_build, args.archive_assets)
