"""Arranque en un paso: genera la base si no existe y abre el dashboard de Streamlit."""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DB = ROOT / "data" / "cementerio.duckdb"
RAW = ROOT / "data" / "raw"

if not DB.exists() and RAW.exists() and any(p.suffix.lower() in {".xlsx", ".csv"} for p in RAW.iterdir()):
    print("Primera ejecucion: procesando los Excel de data/raw (puede tardar ~1 minuto)...")
    subprocess.run([sys.executable, str(ROOT / "etl" / "build_db.py")], check=True)

args = [sys.executable, "-m", "streamlit", "run", str(ROOT / "streamlit_app.py"), "--server.port", "8501"]
if "--no-browser" in sys.argv:
    args += ["--server.headless", "true"]
else:
    args += ["--server.headless", "false"]
subprocess.run(args, cwd=ROOT)
