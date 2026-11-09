"""Arranque en un paso: genera la base si no existe y abre el dashboard en el navegador."""
import subprocess
import sys
import threading
import webbrowser
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DB = ROOT / "data" / "cementerio.duckdb"
RAW = ROOT / "data" / "raw"
PORT = 8000

if not DB.exists() and RAW.exists() and any(p.suffix.lower() in {".xlsx", ".csv"} for p in RAW.iterdir()):
    print("Primera ejecución: procesando los Excel de data/raw (puede tardar ~1 minuto)…")
    subprocess.run([sys.executable, str(ROOT / "etl" / "build_db.py")], check=True)

if "--no-browser" not in sys.argv:
    threading.Timer(1.5, lambda: webbrowser.open(f"http://localhost:{PORT}")).start()

import uvicorn  # noqa: E402

sys.path.insert(0, str(ROOT))
uvicorn.run("app.main:app", host="127.0.0.1", port=PORT)
