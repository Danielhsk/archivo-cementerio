"""Convierte los reportes Excel exportados de KNIME en una base DuckDB lista para el dashboard.

Uso:
    python etl/build_db.py                 # procesa todos los .xlsx/.csv de data/raw
    python etl/build_db.py archivo.xlsx    # procesa solo los archivos indicados
"""
from __future__ import annotations

import json
import os
import shutil
import sys
import time
import urllib.request
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = ROOT / "data" / "raw"
DB_PATH = ROOT / "data" / "cementerio.duckdb"
GITHUB_DB_URL = os.environ.get(
    "ARCHIVO_DB_URL",
    "https://media.githubusercontent.com/media/Danielhsk/archivo-cementerio/main/data/cementerio.duckdb",
)
MIN_DB_BYTES = 1_000_000
CATALOG_PATH = Path(__file__).resolve().parent / "catalogos.json"

# Cada reporte se reconoce por un conjunto de encabezados obligatorios.
DATASETS = {
    "facturas": {
        "titulo": "Facturas",
        "descripcion": "Facturación de servicios: valor, forma de pago, anulaciones y subsidios.",
        "firma": {"factura", "fecha", "valor", "forma_pago", "anulada"},
        "fecha": "fecha",
    },
    "exhumaciones": {
        "titulo": "Exhumaciones",
        "descripcion": "Exhumaciones con su inhumación de origen, reclamante y destino del traslado.",
        "firma": {"factura_ex", "fecha_exh", "fecha_inh", "traslado_a"},
        "fecha": "fecha_exh",
    },
    "cremaciones": {
        "titulo": "Cremaciones",
        "descripcion": "Certificados de cremación con destino, urna, funeraria y entrega.",
        "firma": {"factura", "fecha_cre", "certificad", "tipo_crema"},
        "fecha": "fecha_cre",
    },
    "funerarias": {
        "titulo": "Funerarias",
        "descripcion": "Maestro de NIT y nombre de funerarias para cruzar con la facturación.",
        "firma": {"nit", "nombre"},
        "fecha": None,
    },
}

# El origen (Visual FoxPro) perdió la codificación: la ñ y la ó de "-ción" llegan como U+FFFD.
CLEAN_MACROS = r"""
CREATE OR REPLACE MACRO fix_enc(x) AS
    replace(replace(replace(x, 'ci' || chr(65533) || 'n', 'ción'), 'CI' || chr(65533) || 'N', 'CIÓN'), chr(65533), 'ñ');
CREATE OR REPLACE MACRO clean(x) AS
    nullif(trim(fix_enc(regexp_replace(CAST(x AS VARCHAR), '^"(.*)"$', '\1', 's'))), '');
CREATE OR REPLACE MACRO to_date(x) AS
    CAST(try_strptime(clean(x), '%m/%d/%Y') AS DATE);
CREATE OR REPLACE MACRO to_ts(x) AS
    try_strptime(clean(x), '%m/%d/%Y %H:%M:%S');
CREATE OR REPLACE MACRO to_num(x) AS
    try_cast(replace(clean(x), ',', '') AS DOUBLE);
CREATE OR REPLACE MACRO to_bool(x) AS
    CASE upper(clean(x)) WHEN 'T' THEN true WHEN 'F' THEN false ELSE NULL END;
"""

# Columnas tipadas por reporte; el resto queda como texto limpio.
TYPED = {
    "facturas": {
        "fecha": "to_date", "fech_anul": "to_date", "fec_acc": "to_ts", "fec_exp": "to_ts",
        "valor": "to_num", "anulada": "to_bool", "cierre": "to_bool", "ok": "to_bool",
        "impreso": "to_num",
    },
    "exhumaciones": {
        "fecha_exh": "to_date", "fec_lic_ex": "to_date", "fecha_inh": "to_date",
        "fe_cal_exh": "to_date", "fec_acc": "to_ts", "fec_exp": "to_ts", "edad": "to_num",
        "reg": "to_num", "cierre": "to_bool", "bloquea": "to_bool",
    },
    "cremaciones": {
        "fecha_cre": "to_date", "entrega_ce": "to_date", "fec_ingser": "to_ts",
        "fec_acc": "to_ts", "fec_exp": "to_ts", "edad": "to_num", "urna": "to_bool",
        "cierre": "to_bool", "bloquea": "to_bool",
    },
    "funerarias": {},
}


def cloud_runtime() -> bool:
    """Streamlit Community Cloud monta el repo en /mount/src."""
    return Path("/mount/src").exists() or os.environ.get("STREAMLIT_RUNTIME_ENV") == "cloud"


def runtime_db_path() -> Path:
    """En Cloud el clone es solo lectura: la base activa vive en /tmp."""
    if cloud_runtime():
        return Path(os.environ.get("ARCHIVO_DB_PATH", "/tmp/archivo_cementerio.duckdb"))
    return DB_PATH


def db_usable(path: Path = DB_PATH) -> bool:
    if not path.is_file():
        return False
    if path.stat().st_size < MIN_DB_BYTES:
        return False
    with path.open("rb") as fh:
        head = fh.read(64)
    if head.startswith(b"version https://git-lfs.github.com/spec/v1"):
        return False
    return b"DUCK" in head[:32]


def fetch_db_from_github(url: str = GITHUB_DB_URL, dest: Path = DB_PATH) -> None:
    """Descarga la base real cuando el clone solo trajo el puntero Git LFS."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(".duckdb.download")
    if tmp.exists():
        tmp.unlink()
    req = urllib.request.Request(url, headers={"User-Agent": "archivo-cementerio-dashboard/1.0"})
    with urllib.request.urlopen(req, timeout=900) as resp, tmp.open("wb") as out:
        while True:
            chunk = resp.read(8 * 1024 * 1024)
            if not chunk:
                break
            out.write(chunk)
    if not db_usable(tmp):
        tmp.unlink(missing_ok=True)
        raise RuntimeError("La descarga de la base DuckDB no produjo un archivo válido.")
    if dest.exists():
        dest.unlink()
    tmp.replace(dest)


def ensure_db_file() -> None:
    dest = runtime_db_path()
    if db_usable(dest):
        return
    repo_db = DB_PATH
    if db_usable(repo_db):
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(repo_db, dest)
        return
    if dest.is_file():
        dest.unlink()
    fetch_db_from_github(dest=dest)


def connect(read_only: bool | None = None) -> duckdb.DuckDBPyConnection:
    if read_only is None:
        read_only = cloud_runtime()
    ensure_db_file()
    path = runtime_db_path()
    con = duckdb.connect(str(path), read_only=read_only)
    if not read_only:
        con.execute("INSTALL excel; LOAD excel;")
    return con


def read_source(con: duckdb.DuckDBPyConnection, path: Path) -> str:
    """Carga el archivo tal cual en una tabla temporal de texto y devuelve su nombre."""
    src = str(path).replace("'", "''")
    if path.suffix.lower() == ".csv":
        reader = f"read_csv('{src}', header=false, all_varchar=true)"
    else:
        reader = f"read_xlsx('{src}', header=false, all_varchar=true)"
    con.execute(
        f"CREATE OR REPLACE TEMP TABLE _raw AS SELECT row_number() OVER () AS _rn, * FROM {reader}"
    )
    return "_raw"


def header_map(row: tuple, cols: list[str]) -> dict[str, str]:
    """KNIME duplica columnas con sufijo _transformed: se usa la primera aparición de cada nombre."""
    mapping: dict[str, str] = {}
    for col, name in zip(cols, row):
        name = (name or "").strip().strip('"').strip().lower()
        if name and name not in mapping.values():
            mapping[col] = name
    return mapping


def find_header(con: duckdb.DuckDBPyConnection, table: str) -> tuple[int, dict[str, str], str | None]:
    """Busca la fila de encabezados entre las primeras filas (KNIME antepone a veces Column0, Column1...)."""
    cols = [c[0] for c in con.execute(f"DESCRIBE {table}").fetchall() if c[0] != "_rn"]
    quoted = ", ".join(f'"{c}"' for c in cols)
    rows = con.execute(f"SELECT _rn, {quoted} FROM {table} ORDER BY _rn LIMIT 5").fetchall()
    for r in rows:
        mapping = header_map(r[1:], cols)
        key = detect(set(mapping.values()))
        if key:
            return r[0], mapping, key
    return 0, header_map(rows[0][1:], cols) if rows else {}, None


def detect(names: set[str]) -> str | None:
    for key, spec in DATASETS.items():
        if spec["firma"] <= names:
            return key
    return None


def load_file(con: duckdb.DuckDBPyConnection, path: Path) -> tuple[str | None, int]:
    t = time.time()
    raw = read_source(con, path)
    header_rn, mapping, key = find_header(con, raw)
    if key is None:
        print(f"  ! {path.name}: no se reconoce el reporte (encabezados: {sorted(mapping.values())[:8]}...)")
        return None, 0

    typed = TYPED[key]
    exprs = [f'{typed.get(name, "clean")}("{col}") AS "{name}"' for col, name in mapping.items()]
    con.execute(
        f"""
        CREATE OR REPLACE TABLE {key} AS
        SELECT {', '.join(exprs)}
        FROM {raw}
        WHERE _rn > {header_rn}
        ORDER BY _rn
        """
    )
    n = con.execute(f"SELECT count(*) FROM {key}").fetchone()[0]
    con.execute(
        "INSERT OR REPLACE INTO _meta VALUES (?, ?, ?, now(), ?)",
        [key, path.name, n, round(time.time() - t, 1)],
    )
    print(f"  OK {path.name} -> {key}: {n:,} filas ({time.time() - t:.1f}s)")
    return key, n


def build_views(con: duckdb.DuckDBPyConnection) -> None:
    """Vistas analíticas con etiquetas legibles; se recrean después de cada carga."""
    tables = {r[0] for r in con.execute("SELECT table_name FROM information_schema.tables").fetchall()}

    cat = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))

    def label(field: str, expr: str) -> str:
        whens = " ".join(
            f"WHEN '{k}' THEN '{v.replace(chr(39), chr(39) * 2)}'" for k, v in cat.get(field, {}).items()
        )
        # Los códigos fuera del catálogo son errores de digitación en el origen (?, o, |...).
        return (f"CASE WHEN {expr} IS NULL THEN 'Sin dato' "
                f"ELSE CASE upper({expr}) {whens} ELSE 'Otro código' END END")

    def funeraria(alias: str) -> tuple[str, str]:
        if "funerarias" not in tables:
            return f"coalesce({alias}.funeraria, 'Sin funeraria')", ""
        return (
            f"coalesce(fu.nombre, {alias}.funeraria, 'Sin funeraria')",
            f"LEFT JOIN (SELECT nit, any_value(nombre) AS nombre FROM funerarias GROUP BY nit) fu "
            f"ON fu.nit = {alias}.funeraria",
        )

    # Solo fechas plausibles: el sistema de origen tiene registros con años 1, 1900 o 2070.
    valid = "BETWEEN DATE '2000-01-01' AND current_date"
    age = "CASE WHEN {0} >= 1 AND {0} <= 110 THEN {0} END"

    if "facturas" in tables:
        fun_name, fun_join = funeraria("f")
        con.execute(
            f"""
            CREATE OR REPLACE VIEW v_facturas AS
            SELECT f.*,
                   year(f.fecha) AS anio,
                   date_trunc('month', f.fecha) AS mes,
                   coalesce(f.anulada, false) AS es_anulada,
                   {label('forma_pago', 'f.forma_pago')} AS forma_pago_nombre,
                   {label('cementerio', 'f.cementerio')} AS cementerio_nombre,
                   {fun_name} AS funeraria_nombre
            FROM facturas f {fun_join}
            WHERE f.fecha {valid}
            """
        )
    if "exhumaciones" in tables:
        con.execute(
            f"""
            CREATE OR REPLACE VIEW v_exhumaciones AS
            SELECT e.*,
                   year(e.fecha_exh) AS anio,
                   date_trunc('month', e.fecha_exh) AS mes,
                   CASE WHEN e.fecha_inh >= DATE '1900-01-01' AND e.fecha_exh >= e.fecha_inh
                        THEN date_diff('day', e.fecha_inh, e.fecha_exh) / 365.25 END AS anios_sepultado,
                   {age.format('e.edad')} AS edad_valida,
                   {label('cementerio', 'e.cementerio')} AS cementerio_nombre,
                   {label('sexo', 'e.sexo')} AS sexo_nombre,
                   {label('causa_muer', 'e.causa_muer')} AS causa_nombre,
                   {label('tipo_usuar', 'e.tipo_usuar')} AS tipo_usuario_nombre,
                   CASE WHEN lower(e.traslado_a) LIKE 'crem%' THEN 'Cremación'
                        WHEN lower(e.traslado_a) LIKE 'entreg%' THEN 'Entregado'
                        WHEN lower(e.traslado_a) LIKE 'traslado%' THEN 'Traslado'
                        WHEN e.traslado_a IS NULL OR e.traslado_a IN ('0', '.', '-') THEN 'Sin dato'
                        ELSE upper(substr(trim(e.traslado_a), 1, 1)) || lower(substr(trim(e.traslado_a), 2))
                   END AS destino_nombre
            FROM exhumaciones e
            WHERE e.fecha_exh {valid}
            """
        )
    if "cremaciones" in tables:
        fun_name, fun_join = funeraria("c")
        con.execute(
            f"""
            CREATE OR REPLACE VIEW v_cremaciones AS
            SELECT c.*,
                   year(c.fecha_cre) AS anio,
                   date_trunc('month', c.fecha_cre) AS mes,
                   {age.format('c.edad')} AS edad_valida,
                   {label('cementerio', 'c.cementerio')} AS cementerio_nombre,
                   {label('tipo_crema', 'c.tipo_crema')} AS tipo_crema_nombre,
                   {label('sexo', 'c.sexo')} AS sexo_nombre,
                   {label('tipo_usuar', 'c.tipo_usuar')} AS tipo_usuario_nombre,
                   CASE WHEN c.destino IS NULL OR c.destino IN ('0', '.', '-') THEN 'Sin dato'
                        ELSE upper(substr(trim(c.destino), 1, 1)) || lower(substr(trim(c.destino), 2))
                   END AS destino_nombre,
                   coalesce(c.urna, false) AS con_urna,
                   {fun_name} AS funeraria_nombre
            FROM cremaciones c {fun_join}
            WHERE c.fecha_cre {valid}
            """
        )


def prepare(con: duckdb.DuckDBPyConnection) -> None:
    con.execute(CLEAN_MACROS)
    con.execute(
        """CREATE TABLE IF NOT EXISTS _meta (
               dataset VARCHAR PRIMARY KEY, archivo VARCHAR, filas BIGINT,
               cargado TIMESTAMP, segundos DOUBLE)"""
    )


def main(argv: list[str]) -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    if argv == ["--vistas"]:
        con = connect()
        prepare(con)
        build_views(con)
        con.close()
        print("Vistas recreadas con el catálogo actual.")
        return

    RAW_DIR.mkdir(parents=True, exist_ok=True)
    files = [Path(a) for a in argv] or sorted(
        p for p in RAW_DIR.iterdir() if p.suffix.lower() in {".xlsx", ".csv"}
    )
    if not files:
        sys.exit(f"No hay archivos en {RAW_DIR}. Copia ahí los reportes .xlsx de KNIME.")
    con = connect()
    prepare(con)
    print(f"Procesando {len(files)} archivo(s) -> {DB_PATH}")
    # Funerarias primero para que las vistas puedan cruzar nombres.
    files.sort(key=lambda p: 0 if "funer" in p.name.lower() else 1)
    for f in files:
        load_file(con, f)
    build_views(con)
    con.close()
    print("Listo.")


if __name__ == "__main__":
    main(sys.argv[1:])
