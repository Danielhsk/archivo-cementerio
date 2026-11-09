"""Consultas a la base DuckDB generada por etl/build_db.py."""
from __future__ import annotations

import sys
import threading
from pathlib import Path

import duckdb
import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "etl"))
import build_db as etl  # noqa: E402

VISTAS = {"facturas": "v_facturas", "cremaciones": "v_cremaciones",
          "exhumaciones": "v_exhumaciones", "funerarias": "v_funerarias"}
FECHAS = {"facturas": "fecha", "cremaciones": "fecha_cre", "exhumaciones": "fecha_exh", "funerarias": None}
CEM_OK = "cementerio_nombre NOT IN ('Sin dato', 'Otro código')"
MESES = ["Ene", "Feb", "Mar", "Abr", "May", "Jun", "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"]

write_lock = threading.Lock()


def _tables(cur) -> set[str]:
    return {r[0] for r in cur.execute("SELECT table_name FROM information_schema.tables").fetchall()}


def _refresh_views(cur) -> None:
    etl.build_views(cur)
    tables = _tables(cur)
    if "funerarias" not in tables:
        return
    fact = ("LEFT JOIN (SELECT funeraria, count(*) n, sum(valor) v FROM v_facturas WHERE NOT es_anulada "
            "GROUP BY 1) f ON f.funeraria = fu.nit") if "v_facturas" in tables else ""
    crem = ("LEFT JOIN (SELECT funeraria, count(*) n FROM v_cremaciones GROUP BY 1) c "
            "ON c.funeraria = fu.nit") if "v_cremaciones" in tables else ""
    cur.execute(f"""
        CREATE OR REPLACE VIEW v_funerarias AS
        SELECT fu.nit, fu.nombre,
               {'coalesce(f.n, 0)' if fact else '0'} AS facturas,
               {'coalesce(f.v, 0)' if fact else '0'} AS valor_facturado,
               {'coalesce(c.n, 0)' if crem else '0'} AS cremaciones
        FROM funerarias fu {fact} {crem}""")


@st.cache_resource
def connection() -> duckdb.DuckDBPyConnection:
    etl.DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    con = etl.connect()
    etl.prepare(con)
    _refresh_views(con)
    return con


def df(sql: str, params: list | None = None) -> pd.DataFrame:
    return connection().cursor().execute(sql, params or []).df()


def scalar(sql: str, params: list | None = None):
    return connection().cursor().execute(sql, params or []).fetchone()[0]


def where(desde=None, hasta=None, cementerio=None, extra: str = "") -> tuple[str, list]:
    cond, params = [], []
    if desde:
        cond.append("anio >= ?")
        params.append(int(desde))
    if hasta:
        cond.append("anio <= ?")
        params.append(int(hasta))
    if cementerio:
        cond.append("cementerio = ?")
        params.append(cementerio)
    if extra:
        cond.append(extra)
    return ("WHERE " + " AND ".join(cond)) if cond else "", params


def and_(w: str, cond: str) -> str:
    return f"{w} AND {cond}" if w else f"WHERE {cond}"


# ---------------------------------------------------------------- meta

@st.cache_data(show_spinner=False)
def meta() -> dict:
    cur = connection().cursor()
    tables = _tables(cur)
    info = {r[0]: r for r in cur.execute("SELECT dataset, archivo, filas, cargado FROM _meta").fetchall()}
    datasets = []
    for key, spec in etl.DATASETS.items():
        d = {"key": key, "titulo": spec["titulo"], "descripcion": spec["descripcion"],
             "fecha": spec["fecha"], "cargado": key in tables}
        if key in info:
            d.update(archivo=info[key][1], filas=info[key][2], actualizado=str(info[key][3])[:16])
        if spec["fecha"] and VISTAS[key] in tables:
            mn, mx = cur.execute(f"SELECT min({spec['fecha']}), max({spec['fecha']}) FROM {VISTAS[key]}").fetchone()
            d.update(desde=str(mn), hasta=str(mx))
        datasets.append(d)
    anios, cems = set(), {}
    for view in ("v_facturas", "v_cremaciones", "v_exhumaciones"):
        if view in tables:
            anios |= {r[0] for r in cur.execute(f"SELECT DISTINCT anio FROM {view}").fetchall()}
            for c, n in cur.execute(f"SELECT DISTINCT cementerio, cementerio_nombre FROM {view} WHERE {CEM_OK}").fetchall():
                cems[c] = n
    return {"datasets": datasets, "cargados": {d["key"] for d in datasets if d["cargado"]},
            "anios": sorted(a for a in anios if a), "cementerios": dict(sorted(cems.items()))}


# ---------------------------------------------------------------- resumen

@st.cache_data(show_spinner=False)
def resumen(desde, hasta, cementerio) -> dict:
    cargados = meta()["cargados"]
    out: dict = {"kpis": {}, "anual": {}, "mensual": {}, "cementerios": {}, "funerarias": pd.DataFrame()}
    k = out["kpis"]
    w, p = where(desde, hasta, cementerio)
    if "facturas" in cargados:
        r = df(f"""SELECT count(*) FILTER (WHERE NOT es_anulada) n,
                          sum(valor) FILTER (WHERE NOT es_anulada) valor,
                          count(*) FILTER (WHERE es_anulada) anuladas,
                          sum(valor) FILTER (WHERE es_anulada) valor_anulado,
                          count(*) total, count(DISTINCT nit) clientes
                   FROM v_facturas {w}""", p).iloc[0]
        k.update(facturas=r.n, facturado=r.valor or 0, anuladas=r.anuladas, valor_anulado=r.valor_anulado or 0,
                 clientes=r.clientes, pct_anuladas=(r.anuladas / r.total * 100) if r.total else 0,
                 ticket=(r.valor / r.n) if r.n else 0)
        wn = and_(w, "NOT es_anulada")
        out["anual"]["facturas"] = df(f"SELECT anio, count(*) n, sum(valor) valor FROM v_facturas {wn} GROUP BY 1 ORDER BY 1", p)
        out["mensual"]["Facturas"] = df(f"SELECT mes, count(*) n FROM v_facturas {wn} GROUP BY 1 ORDER BY 1", p)
        w2, p2 = where(desde, hasta, None, f"NOT es_anulada AND {CEM_OK}")
        out["cementerios"]["Facturado"] = df(f"SELECT cementerio_nombre nombre, sum(valor) v FROM v_facturas {w2} GROUP BY 1", p2)
        out["funerarias"] = df(f"""SELECT funeraria_nombre nombre, count(*) n, sum(valor) valor FROM v_facturas
                                   {and_(wn, 'funeraria IS NOT NULL')} GROUP BY 1 ORDER BY 3 DESC LIMIT 10""", p)
    for key, view in (("cremaciones", "v_cremaciones"), ("exhumaciones", "v_exhumaciones")):
        if key not in cargados:
            continue
        k[key] = scalar(f"SELECT count(*) FROM {view} {w}", p)
        k[f"edad_{key}"] = scalar(f"SELECT avg(edad_valida) FROM {view} {w}", p)
        out["anual"][key] = df(f"SELECT anio, count(*) n FROM {view} {w} GROUP BY 1 ORDER BY 1", p)
        out["mensual"][key.capitalize()] = df(f"SELECT mes, count(*) n FROM {view} {w} GROUP BY 1 ORDER BY 1", p)
        w2, p2 = where(desde, hasta, None, CEM_OK)
        out["cementerios"][key.capitalize()] = df(f"SELECT cementerio_nombre nombre, count(*) v FROM {view} {w2} GROUP BY 1", p2)
    if "exhumaciones" in cargados:
        k["pct_exh_cremacion"] = scalar(
            f"SELECT avg(CASE WHEN destino_nombre = 'Cremación' THEN 100.0 ELSE 0 END) FROM v_exhumaciones {w}", p)
        k["anios_sepultado"] = scalar(f"SELECT median(anios_sepultado) FROM v_exhumaciones {w}", p)
    return out


# ---------------------------------------------------------------- estadísticas

EDAD = ("CASE WHEN edad_valida IS NULL THEN NULL ELSE lpad(CAST(floor(edad_valida / 10) * 10 AS INT)::VARCHAR, 3, '0') "
        "|| '–' || CAST(floor(edad_valida / 10) * 10 + 9 AS INT) END")
MES_SQL = "['Ene','Feb','Mar','Abr','May','Jun','Jul','Ago','Sep','Oct','Nov','Dic'][month({0})]"
DIA_SQL = "['Dom','Lun','Mar','Mié','Jue','Vie','Sáb'][dayofweek({0}) + 1]"


def _dist(view, expr, w, p, limit=None, order="2 DESC", valor="count(*)") -> pd.DataFrame:
    sql = f"SELECT {expr} AS k, {valor} AS v FROM {view} {w} GROUP BY 1 ORDER BY {order}"
    return df(sql + (f" LIMIT {limit}" if limit else ""), p)


@st.cache_data(show_spinner=False)
def estadisticas(dataset, desde, hasta, cementerio) -> list[dict]:
    """Lista de gráficos: {titulo, tipo (dona|barra|hbarra|linea), datos (k, v), formato, nota}."""
    view, fecha = VISTAS[dataset], FECHAS[dataset]
    w, p = where(desde, hasta, cementerio)
    mes, dia = MES_SQL.format(fecha), DIA_SQL.format(fecha)
    out = []

    def add(titulo, tipo, datos, formato="n", nota=""):
        out.append({"titulo": titulo, "tipo": tipo, "datos": datos, "formato": formato, "nota": nota})

    if dataset == "facturas":
        wv, pv = where(desde, hasta, cementerio, "NOT es_anulada")
        add("Facturado por forma de pago", "dona", _dist(view, "forma_pago_nombre", wv, pv, valor="sum(valor)"), "$")
        add("Facturado por cementerio", "barra", _dist(view, "cementerio_nombre", wv, pv, valor="sum(valor)"), "$")
        add("Distribución del valor por factura", "barra", _dist(
            view, "CASE WHEN valor < 100000 THEN '1|< 100 mil' WHEN valor < 250000 THEN '2|100–250 mil' "
                  "WHEN valor < 500000 THEN '3|250–500 mil' WHEN valor < 1000000 THEN '4|500 mil–1 M' "
                  "WHEN valor < 5000000 THEN '5|1–5 M' ELSE '6|≥ 5 M' END", wv, pv, order="1"),
            nota="Número de facturas no anuladas por rango de valor.")
        add("Estacionalidad: facturado por mes del año", "barra",
            _dist(view, mes, wv, pv, order=f"min(month({fecha}))", valor="sum(valor)"), "$")
        add("Facturas por día de la semana", "barra", _dist(view, dia, wv, pv, order=f"min(dayofweek({fecha}))"))
        add("Facturas anuladas por año", "linea",
            _dist(view, "anio", w, p, order="1", valor="count(*) FILTER (WHERE es_anulada)"))
        add("Top 12 funerarias por valor facturado", "hbarra",
            _dist(view, "funeraria_nombre", and_(wv, "funeraria IS NOT NULL"), pv, 12, valor="sum(valor)"), "$")
    elif dataset == "cremaciones":
        we, pe = where(desde, hasta, cementerio, "edad_valida IS NOT NULL")
        add("Cremaciones por tipo", "dona", _dist(view, "tipo_crema_nombre", w, p))
        add("Cremaciones por sexo", "dona", _dist(view, "sexo_nombre", w, p))
        add("Distribución por edad", "barra", _dist(view, EDAD, we, pe, order="1"),
            nota="Excluye registros sin edad (edad 0 en el origen).")
        add("Edad promedio por año", "linea", _dist(view, "anio", we, pe, order="1", valor="round(avg(edad_valida), 1)"), "d")
        add("Cremaciones por cementerio", "barra", _dist(view, "cementerio_nombre", w, p))
        add("Entrega con urna", "dona", _dist(view, "CASE WHEN con_urna THEN 'Con urna' ELSE 'Sin urna' END", w, p))
        add("Destino de las cenizas (top 10)", "hbarra", _dist(view, "destino_nombre", w, p, 10))
        add("Top 12 funerarias por cremaciones", "hbarra", _dist(view, "funeraria_nombre", w, p, 12))
        add("Estacionalidad: cremaciones por mes del año", "barra",
            _dist(view, mes, w, p, order=f"min(month({fecha}))"))
    else:
        we, pe = where(desde, hasta, cementerio, "edad_valida IS NOT NULL")
        ws, ps = where(desde, hasta, cementerio, "anios_sepultado IS NOT NULL")
        add("Destino de los restos exhumados", "hbarra", _dist(view, "destino_nombre", w, p, 10))
        add("Años entre inhumación y exhumación", "barra", _dist(
            view, "CASE WHEN anios_sepultado < 4 THEN '1|< 4 años' WHEN anios_sepultado < 5 THEN '2|4–5 años' "
                  "WHEN anios_sepultado < 7 THEN '3|5–7 años' WHEN anios_sepultado < 10 THEN '4|7–10 años' "
                  "WHEN anios_sepultado < 20 THEN '5|10–20 años' ELSE '6|≥ 20 años' END", ws, ps, order="1"))
        add("Exhumaciones por sexo", "dona", _dist(view, "sexo_nombre", w, p))
        add("Causa de muerte (código)", "dona", _dist(view, "causa_nombre", w, p))
        add("Edad al fallecer", "barra", _dist(view, EDAD, we, pe, order="1"), nota="Excluye registros sin edad.")
        add("Exhumaciones por cementerio", "barra", _dist(view, "cementerio_nombre", w, p))
        add("Mediana de años sepultado por año de exhumación", "linea",
            _dist(view, "anio", ws, ps, order="1", valor="round(median(anios_sepultado), 1)"), "d")
        add("Estacionalidad: exhumaciones por mes del año", "barra",
            _dist(view, mes, w, p, order=f"min(month({fecha}))"))
    for c in out:
        c["datos"]["k"] = c["datos"]["k"].astype(str).str.replace(r"^\d\|", "", regex=True)
        if "por cementerio" in c["titulo"]:
            c["datos"] = c["datos"][~c["datos"]["k"].isin(["Sin dato", "Otro código"])]
    return out


# ---------------------------------------------------------------- comparaciones

METRICAS = {
    "facturas": {"valor": ("Valor facturado", "sum(valor)"), "n": ("Número de facturas", "count(*)")},
    "cremaciones": {"n": ("Número de cremaciones", "count(*)")},
    "exhumaciones": {"n": ("Número de exhumaciones", "count(*)")},
}


@st.cache_data(show_spinner=False)
def comparar(dataset, metrica, a, b, cementerio) -> dict:
    view, agg = VISTAS[dataset], METRICAS[dataset][metrica][1]
    extra = "NOT es_anulada" if dataset == "facturas" else ""
    mensual = {}
    for anio in (a, b):
        w, p = where(anio, anio, cementerio, extra)
        r = df(f"SELECT month(mes) m, {agg} v FROM {view} {w} GROUP BY 1", p).set_index("m")["v"]
        mensual[str(anio)] = [float(r.get(m, 0) or 0) for m in range(1, 13)]
    w, p = where(None, None, None, f"{CEM_OK}" + (f" AND {extra}" if extra else ""))
    por_cem = df(f"SELECT CAST(anio AS VARCHAR) anio, cementerio_nombre c, {agg} v FROM {view} "
                 f"{and_(w, 'anio IN (?, ?)')} GROUP BY 1, 2 ORDER BY 2", p + [int(a), int(b)])
    tendencia = df(f"SELECT anio, cementerio_nombre c, {agg} v FROM {view} {w} GROUP BY 1, 2 ORDER BY 1, 2", p)
    ta, tb = sum(mensual[str(a)]), sum(mensual[str(b)])
    return {"mensual": mensual, "totales": (ta, tb), "variacion": ((tb - ta) / ta * 100) if ta else None,
            "por_cem": por_cem, "tendencia": tendencia}


# ---------------------------------------------------------------- tablas

COLUMNAS = {
    "facturas": ["factura", "fecha", "recibido_d", "nit", "fallecido", "forma_pago_nombre", "valor",
                 "funeraria_nombre", "cementerio_nombre", "es_anulada"],
    "cremaciones": ["factura", "fecha_cre", "certificad", "licencia", "nombre", "cementerio_nombre",
                    "tipo_crema_nombre", "sexo_nombre", "edad_valida", "funeraria_nombre", "destino_nombre", "con_urna"],
    "exhumaciones": ["factura_ex", "fecha_exh", "fecha_inh", "nombre", "cementerio_nombre", "galeria", "lugar_no",
                     "sexo_nombre", "edad_valida", "anios_sepultado", "reclamante", "destino_nombre"],
    "funerarias": ["nit", "nombre", "facturas", "valor_facturado", "cremaciones"],
}
BUSQUEDA = {
    "facturas": ["factura", "recibido_d", "nit", "fallecido", "cedula"],
    "cremaciones": ["factura", "certificad", "licencia", "nombre", "cedula"],
    "exhumaciones": ["factura_ex", "licencia_e", "nombre", "reclamante", "nombre_deu"],
    "funerarias": ["nit", "nombre"],
}


def _tabla_sql(dataset, buscar, desde, hasta, cementerio, orden, asc) -> tuple[str, str, list]:
    view, cols = VISTAS[dataset], COLUMNAS[dataset]
    w, p = where(desde, hasta, cementerio) if FECHAS[dataset] else ("", [])
    if buscar:
        like = " OR ".join(f"{c} ILIKE ?" for c in BUSQUEDA[dataset])
        w = and_(w, f"({like})")
        p = p + [f"%{buscar.strip()}%"] * len(BUSQUEDA[dataset])
    orden = orden if orden in cols else (FECHAS[dataset] or cols[0])
    select = (f"SELECT {', '.join(cols)} FROM {view} {w} "
              f"ORDER BY {orden} {'ASC' if asc else 'DESC'} NULLS LAST")
    return select, f"SELECT count(*) FROM {view} {w}", p


@st.cache_data(show_spinner=False)
def tabla(dataset, buscar, desde, hasta, cementerio, orden, asc, pagina, tamano) -> tuple[pd.DataFrame, int]:
    select, count, p = _tabla_sql(dataset, buscar, desde, hasta, cementerio, orden, asc)
    return df(f"{select} LIMIT {tamano} OFFSET {(pagina - 1) * tamano}", p), scalar(count, p)


@st.cache_data(show_spinner=False)
def tabla_csv(dataset, buscar, desde, hasta, cementerio, orden, asc) -> bytes:
    select, _, p = _tabla_sql(dataset, buscar, desde, hasta, cementerio, orden, asc)
    return df(select, p).to_csv(index=False, sep=";").encode("utf-8-sig")


# ---------------------------------------------------------------- carga

def cargar(nombre: str, contenido: bytes) -> dict:
    nombre = Path(nombre).name
    staging = etl.RAW_DIR.parent / "subidas"
    staging.mkdir(parents=True, exist_ok=True)
    temporal = staging / nombre
    temporal.write_bytes(contenido)
    try:
        cur = connection().cursor()
        with write_lock:
            key, n = etl.load_file(cur, temporal)
            if key:
                etl.RAW_DIR.mkdir(parents=True, exist_ok=True)
                temporal.replace(etl.RAW_DIR / nombre)
                _refresh_views(cur)
        if key:
            return {"ok": True, "mensaje": f"Reconocido como {etl.DATASETS[key]['titulo']}: {n:,} filas.".replace(",", ".")}
        return {"ok": False, "mensaje": "No se reconoció el reporte por sus encabezados."}
    except Exception as exc:  # archivo corrupto o con otra estructura
        return {"ok": False, "mensaje": f"No se pudo leer el archivo: {str(exc).splitlines()[0]}"}
    finally:
        temporal.unlink(missing_ok=True)
        st.cache_data.clear()
