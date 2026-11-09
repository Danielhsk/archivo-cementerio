"""Publica el dashboard en Hugging Face Spaces (Streamlit).

Requisito: token con permiso de escritura.
  Windows: set HF_TOKEN=hf_...
  O: hf auth login

Uso:
  python scripts/deploy_hf.py
  python scripts/deploy_hf.py --repo-id USUARIO/archivo-cementerio --public
"""
from __future__ import annotations

import argparse
import shutil
import sys
import tempfile
from pathlib import Path

from huggingface_hub import HfApi, login, whoami
from huggingface_hub.utils import HfHubHTTPError

ROOT = Path(__file__).resolve().parent.parent
SPACE_README = """---
title: Archivo · Cementerio y funeraria
emoji: 🕯️
colorFrom: green
colorTo: gray
sdk: streamlit
sdk_version: 1.46.0
app_file: streamlit_app.py
pinned: false
---

Dashboard interactivo (facturas, cremaciones, exhumaciones y funerarias).
Los datos están precargados en `data/cementerio.duckdb`; la carga de archivos solo funciona en localhost.
"""

COPY_DIRS = ("dashboard", "etl", ".streamlit")
COPY_FILES = ("streamlit_app.py", "requirements.txt")


def stage(target: Path) -> None:
    for name in COPY_FILES:
        shutil.copy2(ROOT / name, target / name)
    for d in COPY_DIRS:
        shutil.copytree(ROOT / d, target / d, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    db = ROOT / "data" / "cementerio.duckdb"
    if not db.exists():
        sys.exit("Falta data/cementerio.duckdb. Ejecuta: python etl/build_db.py")
    (target / "data").mkdir()
    shutil.copy2(db, target / "data" / "cementerio.duckdb")
    (target / "README.md").write_text(SPACE_README, encoding="utf-8")


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--repo-id", help="usuario/nombre-del-space (por defecto: tu usuario/archivo-cementerio)")
    p.add_argument("--public", action="store_true", help="Space público (por defecto: privado)")
    args = p.parse_args()

    import os
    if tok := os.environ.get("HF_TOKEN"):
        login(token=tok, add_to_git_credential=False)
    else:
        login()
    user = whoami()["name"]
    repo_id = args.repo_id or f"{user}/archivo-cementerio"
    private = not args.public

    api = HfApi()
    try:
        api.create_repo(repo_id=repo_id, repo_type="space", space_sdk="streamlit", private=private, exist_ok=True)
        print(f"Space listo: {repo_id} ({'privado' if private else 'público'})")
    except HfHubHTTPError as e:
        sys.exit(f"No se pudo crear el Space: {e}")

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        stage(root)
        print("Subiendo archivos (la base DuckDB ~110 MB puede tardar varios minutos)...")
        api.upload_folder(
            folder_path=str(root),
            repo_id=repo_id,
            repo_type="space",
            commit_message="Deploy dashboard Streamlit",
        )

    url = f"https://huggingface.co/spaces/{repo_id}"
    print(f"\nListo. URL fija del Space:\n  {url}")
    print("El build puede tardar 2–5 minutos la primera vez. Si está dormido, la primera visita puede tardar ~1 min.")


if __name__ == "__main__":
    main()
