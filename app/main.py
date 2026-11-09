"""API del dashboard: consulta la base DuckDB generada por etl/build_db.py y sirve el frontend."""
from __future__ import annotations

import csv
import io
import json
import shutil
import sys
import threading
from pathlib import Path
from typing import Any

from fastapi import FastAPI, File, HTTPException, Query, UploadFile
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "etl"))
import build_db as etl  # noqa: E402

DATASETS: dict[str, dict[str, Any]] = {
    "facturas": {
        "vista": "v_facturas",
        "fecha": "fecha",
        "columnas": ["factura", "fecha", "recibido_d", "nit", "fallecido", "forma_pago_nombre",
                     "valor", "funeraria_nombre", "cementerio_nombre", "es_anulada"],
        "busqueda": ["factura", "recibido_d", "nit", "fallecido", "cedula"],
    },
    "cremaciones": {
        "vista": "v_cremaciones",
        "fecha": "fecha_cre",
        "columnas": ["factura", "fecha_cre", "certificad", "licencia", "nombre", "cementerio_nombre",
                     "tipo_crema_nombre", "sexo_nombre", "edad_valida", "funeraria_nombre",
                     "destino_nombre", "con_urna"],
        "busqueda": ["factura", "certificad", "licencia", "nombre", "cedula"],
    },
    "exhumaciones": {
        "vista": "v_exhumaciones",
        "fecha": "fecha_exh",
        "columnas": ["factura_ex", "fecha_exh", "fecha_inh", "nombre", "cementerio_nombre", "galeria",
                     "lugar_no", "sexo_nombre", "edad_valida", "anios_sepultado", "reclamante",
                     "destino_nombre"],
        "busqueda": ["factura_ex", "licencia_e", "nombre", "reclamante", "nombre_deu"],
    },
    "funerarias": {
        "vista": "v_funerarias",
        "fecha": None,
        "columnas": ["nit", "nombre", "facturas", "valor_facturado", "cremaciones"],
        "busqueda": ["nit", "nombre"],
    },
}

con = etl.connect()
etl.prepare(con)
write_lock = threading.Lock()


def loaded() -> set[str]:
    cur = con.cursor()
    return {r[0] for r in cur.execute("SELECT table_name FROM information_schema.tables").fetchall()}


def ensure_funerarias_view(cur) -> None:
    tables = loaded()
    if "funerarias" not in tables:
        return
    fact = (
        "LEFT JOIN (SELECT funeraria, count(*) n, sum(valor) v FROM v_facturas "
        "WHERE NOT es_anulada GROUP BY 1) f ON f.funeraria = fu.nit"
        if "v_facturas" in tables else ""
    )
    crem = (
        "LEFT JOIN (SELECT funeraria, count(*) n FROM v_cremaciones GROUP BY 1) c ON c.funeraria = fu.nit"
        if "v_cremaciones" in tables else ""
    )
    cur.execute(
        f"""
        CREATE OR REPLACE VIEW v_funerarias AS
        SELECT fu.nit, fu.nombre,
               {'coalesce(f.n, 0)' if fact else '0'} AS facturas,
               {'coalesce(f.v, 0)' if fact else '0'} AS valor_facturado,
               {'coalesce(c.n, 0)' if crem else '0'} AS cremaciones
        FROM funerarias fu {fact} {crem}
        """
    )


etl.build_views(con)
ensure_funerarias_view(con)


def q(sql: str, params: list | None = None) -> list[dict]:
    cur = con.cursor()
    res = cur.execute(sql, params or [])
    cols = [d[0] for d in res.description]
    return [dict(zip(cols, row)) for row in res.fetchall()]


def q1(sql: str, params: list | None = None) -> Any:
    return con.cursor().execute(sql, params or []).fetchone()[0]


def where(desde: int | None, hasta: int | None, cementerio: str | None, extra: str = "") -> tuple[str, list]:
    cond, params = [], []
    if desde:
        cond.append("anio >= ?")
        params.append(desde)
    if hasta:
        cond.append("anio <= ?")
        params.append(hasta)
    if cementerio:
        cond.append("cementerio = ?")
        params.append(cementerio)
    if extra:
        cond.append(extra)
    return ("WHERE " + " AND ".join(cond)) if cond else "", params


def require(view: str) -> None:
    if view not in loaded():
        raise HTTPException(404, f"El reporte '{view}' aún no está cargado. Súbelo en Archivos.")


app = FastAPI(title="Archivo · Cementerio y funeraria")


@app.get("/api/meta")
def meta():
    tables = loaded()
    info = {r["dataset"]: r for r in q("SELECT * FROM _meta")}
    datasets = []
    for key, spec in etl.DATASETS.items():
        d = {"key": key, "titulo": spec["titulo"], "descripcion": spec["descripcion"],
             "fecha": spec["fecha"], "cargado": key in tables}
        if key in info:
            d.update(filas=info[key]["filas"], archivo=info[key]["archivo"],
                     actualizado=str(info[key]["cargado"])[:19])
        view = DATASETS[key]["vista"]
        if spec["fecha"] and view in tables:
            r = q(f"SELECT min({spec['fecha']}) mn, max({spec['fecha']}) mx, count(*) n FROM {view}")[0]
            d.update(desde=str(r["mn"]), hasta=str(r["mx"]), validas=r["n"])
        datasets.append(d)

    anios, cementerios = set(), {}
    for view in ("v_facturas", "v_cremaciones", "v_exhumaciones"):
        if view in tables:
            anios |= {r["anio"] for r in q(f"SELECT DISTINCT anio FROM {view}")}
            for r in q(f"SELECT DISTINCT cementerio, cementerio_nombre FROM {view} WHERE cementerio IS NOT NULL"):
                cementerios[r["cementerio"]] = r["cementerio_nombre"]
    catalogo = json.loads(etl.CATALOG_PATH.read_text(encoding="utf-8"))
    valid_cem = set(catalogo.get("cementerio", {}))
    return {
        "datasets": datasets,
        "anios": sorted(a for a in anios if a),
        "cementerios": [{"codigo": k, "nombre": v} for k, v in sorted(cementerios.items())
                        if not valid_cem or k in valid_cem],
    }


@app.get("/api/resumen")
def resumen(desde: int | None = None, hasta: int | None = None, cementerio: str | None = None):
    tables = loaded()
    out: dict[str, Any] = {"kpis": {}, "anual": {}, "mensual": {}, "cementerios": {}, "funerarias": []}
    k = out["kpis"]

    if "v_facturas" in tables:
        w, p = where(desde, hasta, cementerio)
        r = q(f"""SELECT count(*) FILTER (WHERE NOT es_anulada) n,
                         sum(valor) FILTER (WHERE NOT es_anulada) valor,
                         count(*) FILTER (WHERE es_anulada) anuladas,
                         sum(valor) FILTER (WHERE es_anulada) valor_anulado,
                         count(*) total, count(DISTINCT nit) clientes
                  FROM v_facturas {w}""", p)[0]
        k.update(facturas=r["n"], facturado=r["valor"] or 0, anuladas=r["anuladas"],
                 valor_anulado=r["valor_anulado"] or 0, clientes=r["clientes"],
                 pct_anuladas=(r["anuladas"] / r["total"] * 100) if r["total"] else 0,
                 ticket=(r["valor"] / r["n"]) if r["n"] else 0)
        out["anual"]["facturas"] = q(f"""SELECT anio, count(*) n, sum(valor) valor FROM v_facturas {w}
                                         {'AND' if w else 'WHERE'} NOT es_anulada GROUP BY 1 ORDER BY 1""", p)
        out["mensual"]["facturas"] = q(f"""SELECT strftime(mes, '%Y-%m') mes, count(*) n, sum(valor) valor
                                           FROM v_facturas {w} {'AND' if w else 'WHERE'} NOT es_anulada
                                           GROUP BY 1 ORDER BY 1""", p)
        w2, p2 = where(desde, hasta, None, "NOT es_anulada")
        out["cementerios"]["facturado"] = q(f"""SELECT cementerio_nombre nombre, sum(valor) v FROM v_facturas {w2}
                                               GROUP BY 1 ORDER BY 2 DESC""", p2)
        out["funerarias"] = q(f"""SELECT funeraria_nombre nombre, count(*) n, sum(valor) valor FROM v_facturas {w}
                                  {'AND' if w else 'WHERE'} NOT es_anulada AND funeraria IS NOT NULL
                                  GROUP BY 1 ORDER BY 3 DESC LIMIT 10""", p)

    for key, view in (("cremaciones", "v_cremaciones"), ("exhumaciones", "v_exhumaciones")):
        if view not in tables:
            continue
        w, p = where(desde, hasta, cementerio)
        k[key] = q1(f"SELECT count(*) FROM {view} {w}", p)
        k[f"edad_{key}"] = q1(f"SELECT avg(edad_valida) FROM {view} {w}", p)
        out["anual"][key] = q(f"SELECT anio, count(*) n FROM {view} {w} GROUP BY 1 ORDER BY 1", p)
        out["mensual"][key] = q(f"SELECT strftime(mes, '%Y-%m') mes, count(*) n FROM {view} {w} GROUP BY 1 ORDER BY 1", p)
        w2, p2 = where(desde, hasta, None)
        out["cementerios"][key] = q(f"SELECT cementerio_nombre nombre, count(*) v FROM {view} {w2} GROUP BY 1 ORDER BY 2 DESC", p2)

    if "v_exhumaciones" in tables:
        w, p = where(desde, hasta, cementerio)
        k["pct_exh_cremacion"] = q1(
            f"SELECT avg(CASE WHEN destino_nombre = 'Cremación' THEN 100.0 ELSE 0 END) FROM v_exhumaciones {w}", p)
        k["anios_sepultado"] = q1(f"SELECT median(anios_sepultado) FROM v_exhumaciones {w}", p)
    return out


def dist(view: str, expr: str, w: str, p: list, limit: int | None = None, order: str = "2 DESC",
         valor: str = "count(*)") -> dict:
    rows = q(f"SELECT {expr} AS k, {valor} AS v FROM {view} {w} GROUP BY 1 ORDER BY {order}"
             + (f" LIMIT {limit}" if limit else ""), p)
    return {"labels": [str(r["k"]) for r in rows], "values": [r["v"] for r in rows]}


MESES = "['Ene','Feb','Mar','Abr','May','Jun','Jul','Ago','Sep','Oct','Nov','Dic'][month(%s)]"
DIAS = "['Dom','Lun','Mar','Mié','Jue','Vie','Sáb'][dayofweek(%s) + 1]"
EDAD = "CASE WHEN edad_valida IS NULL THEN NULL ELSE lpad(CAST(floor(edad_valida / 10) * 10 AS INT)::VARCHAR, 3, ' ') || '–' || CAST(floor(edad_valida / 10) * 10 + 9 AS INT) END"


def chart(id_: str, titulo: str, tipo: str, data: dict, formato: str = "n", nota: str = "") -> dict:
    return {"id": id_, "titulo": titulo, "tipo": tipo, "formato": formato, "nota": nota, **data}


@app.get("/api/estadisticas/{dataset}")
def estadisticas(dataset: str, desde: int | None = None, hasta: int | None = None,
                 cementerio: str | None = None):
    if dataset not in ("facturas", "cremaciones", "exhumaciones"):
        raise HTTPException(404, "Reporte sin estadísticas")
    view = DATASETS[dataset]["vista"]
    require(view)
    fecha = DATASETS[dataset]["fecha"]
    w, p = where(desde, hasta, cementerio)
    charts = []

    if dataset == "facturas":
        wv, pv = where(desde, hasta, cementerio, "NOT es_anulada")
        charts += [
            chart("pago", "Facturado por forma de pago", "doughnut",
                  dist(view, "forma_pago_nombre", wv, pv, valor="sum(valor)"), "$"),
            chart("cem", "Facturado por cementerio", "bar",
                  dist(view, "cementerio_nombre", wv, pv, valor="sum(valor)"), "$"),
            chart("rango", "Distribución del valor por factura", "bar", dist(
                view,
                "CASE WHEN valor < 100000 THEN '1 · < 100 mil' WHEN valor < 250000 THEN '2 · 100–250 mil' "
                "WHEN valor < 500000 THEN '3 · 250–500 mil' WHEN valor < 1000000 THEN '4 · 500 mil–1 M' "
                "WHEN valor < 5000000 THEN '5 · 1–5 M' ELSE '6 · ≥ 5 M' END", wv, pv, order="1"),
                  nota="Número de facturas no anuladas por rango de valor."),
            chart("mes", "Estacionalidad: facturado por mes del año", "bar",
                  dist(view, MESES % fecha, wv, pv, order=f"min(month({fecha}))", valor="sum(valor)"), "$"),
            chart("dia", "Facturas por día de la semana", "bar",
                  dist(view, DIAS % fecha, wv, pv, order=f"min(dayofweek({fecha}))")),
            chart("anul", "Facturas anuladas por año", "line",
                  dist(view, "anio", w, p, order="1", valor="count(*) FILTER (WHERE es_anulada)")),
            chart("fun", "Top 12 funerarias por valor facturado", "hbar",
                  dist(view, "funeraria_nombre", wv + " AND funeraria IS NOT NULL" if wv else
                       "WHERE funeraria IS NOT NULL", pv, 12, valor="sum(valor)"), "$"),
        ]
    elif dataset == "cremaciones":
        we, pe = where(desde, hasta, cementerio, "edad_valida IS NOT NULL")
        charts += [
            chart("tipo", "Cremaciones por tipo", "doughnut", dist(view, "tipo_crema_nombre", w, p)),
            chart("sexo", "Cremaciones por sexo", "doughnut", dist(view, "sexo_nombre", w, p)),
            chart("edad", "Distribución por edad", "bar", dist(view, EDAD, we, pe, order="1"),
                  nota="Excluye registros sin edad (edad 0 en el origen)."),
            chart("edadanio", "Edad promedio por año", "line",
                  dist(view, "anio", we, pe, order="1", valor="round(avg(edad_valida), 1)"), "d"),
            chart("cem", "Cremaciones por cementerio", "bar", dist(view, "cementerio_nombre", w, p)),
            chart("urna", "Entrega con urna", "doughnut",
                  dist(view, "CASE WHEN con_urna THEN 'Con urna' ELSE 'Sin urna' END", w, p)),
            chart("dest", "Destino de las cenizas (top 10)", "hbar", dist(view, "destino_nombre", w, p, 10)),
            chart("fun", "Top 12 funerarias por cremaciones", "hbar",
                  dist(view, "funeraria_nombre", w, p, 12)),
            chart("mes", "Estacionalidad: cremaciones por mes del año", "bar",
                  dist(view, MESES % fecha, w, p, order=f"min(month({fecha}))")),
        ]
    else:
        we, pe = where(desde, hasta, cementerio, "edad_valida IS NOT NULL")
        ws, ps = where(desde, hasta, cementerio, "anios_sepultado IS NOT NULL")
        charts += [
            chart("dest", "Destino de los restos exhumados", "hbar", dist(view, "destino_nombre", w, p, 10)),
            chart("sep", "Años transcurridos entre inhumación y exhumación", "bar", dist(
                view, "CASE WHEN anios_sepultado < 4 THEN '1 · < 4 años' WHEN anios_sepultado < 5 THEN '2 · 4–5 años' "
                      "WHEN anios_sepultado < 7 THEN '3 · 5–7 años' WHEN anios_sepultado < 10 THEN '4 · 7–10 años' "
                      "WHEN anios_sepultado < 20 THEN '5 · 10–20 años' ELSE '6 · ≥ 20 años' END", ws, ps, order="1")),
            chart("sexo", "Exhumaciones por sexo", "doughnut", dist(view, "sexo_nombre", w, p)),
            chart("causa", "Causa de muerte (código)", "doughnut", dist(view, "causa_nombre", w, p)),
            chart("edad", "Edad al fallecer", "bar", dist(view, EDAD, we, pe, order="1"),
                  nota="Excluye registros sin edad."),
            chart("cem", "Exhumaciones por cementerio", "bar", dist(view, "cementerio_nombre", w, p)),
            chart("sepanio", "Mediana de años sepultado por año de exhumación", "line",
                  dist(view, "anio", ws, ps, order="1", valor="round(median(anios_sepultado), 1)"), "d"),
            chart("mes", "Estacionalidad: exhumaciones por mes del año", "bar",
                  dist(view, MESES % fecha, w, p, order=f"min(month({fecha}))")),
        ]
    return {"dataset": dataset, "charts": charts}


CEM_OK = "cementerio_nombre NOT IN ('Sin dato', 'Otro código')"

METRICAS = {
    "facturas": {"n": "count(*)", "valor": "sum(valor)"},
    "cremaciones": {"n": "count(*)"},
    "exhumaciones": {"n": "count(*)"},
}


@app.get("/api/comparar")
def comparar(dataset: str = "facturas", metrica: str = "n", a: int = Query(...), b: int = Query(...),
             cementerio: str | None = None):
    if dataset not in METRICAS or metrica not in METRICAS[dataset]:
        raise HTTPException(400, "Métrica no válida")
    view = DATASETS[dataset]["vista"]
    require(view)
    agg = METRICAS[dataset][metrica]
    extra = "NOT es_anulada" if dataset == "facturas" else ""
    series = {}
    for anio in (a, b):
        w, p = where(anio, anio, cementerio, extra)
        rows = {r["m"]: r["v"] for r in q(f"SELECT month(mes) m, {agg} v FROM {view} {w} GROUP BY 1", p)}
        series[str(anio)] = [rows.get(m, 0) or 0 for m in range(1, 13)]
    ta, tb = sum(series[str(a)]), sum(series[str(b)])
    w, p = where(None, None, None, extra)
    por_cem = q(f"""SELECT anio, cementerio_nombre c, {agg} v FROM {view} {w}
                   {'AND' if w else 'WHERE'} anio IN (?, ?) AND {CEM_OK} GROUP BY 1, 2 ORDER BY 2""", p + [a, b])
    cems = sorted({r["c"] for r in por_cem})
    return {
        "meses": ["Ene", "Feb", "Mar", "Abr", "May", "Jun", "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"],
        "series": series,
        "totales": {str(a): ta, str(b): tb},
        "variacion": ((tb - ta) / ta * 100) if ta else None,
        "cementerios": {
            "labels": cems,
            "series": {str(y): [next((r["v"] for r in por_cem if r["anio"] == y and r["c"] == c), 0) for c in cems]
                       for y in (a, b)},
        },
    }


@app.get("/api/tendencia")
def tendencia(dataset: str = "facturas", metrica: str = "n"):
    """Serie anual por cementerio para el gráfico apilado de Comparaciones."""
    if dataset not in METRICAS or metrica not in METRICAS[dataset]:
        raise HTTPException(400, "Métrica no válida")
    view = DATASETS[dataset]["vista"]
    require(view)
    w = f"WHERE {CEM_OK}" + (" AND NOT es_anulada" if dataset == "facturas" else "")
    rows = q(f"SELECT anio, cementerio_nombre c, {METRICAS[dataset][metrica]} v FROM {view} {w} GROUP BY 1, 2")
    anios = sorted({r["anio"] for r in rows})
    cems = sorted({r["c"] for r in rows})
    idx = {(r["anio"], r["c"]): r["v"] for r in rows}
    return {"labels": anios, "series": {c: [idx.get((y, c), 0) for y in anios] for c in cems}}


def table_query(dataset: str, buscar: str | None, desde: int | None, hasta: int | None,
                cementerio: str | None, orden: str | None, dir_: str) -> tuple[str, str, list]:
    spec = DATASETS.get(dataset)
    if not spec:
        raise HTTPException(404, "Reporte desconocido")
    require(spec["vista"])
    cols = spec["columnas"]
    if spec["fecha"]:
        w, p = where(desde, hasta, cementerio)
    else:
        w, p = "", []
    if buscar:
        like = " OR ".join(f"{c} ILIKE ?" for c in spec["busqueda"])
        w = (w + " AND " if w else "WHERE ") + f"({like})"
        p += [f"%{buscar.strip()}%"] * len(spec["busqueda"])
    order_col = orden if orden in cols else (spec["fecha"] or cols[0])
    direction = "ASC" if dir_ == "asc" else "DESC"
    select = f"SELECT {', '.join(cols)} FROM {spec['vista']} {w} ORDER BY {order_col} {direction} NULLS LAST"
    count = f"SELECT count(*) FROM {spec['vista']} {w}"
    return select, count, p


@app.get("/api/tabla/{dataset}")
def tabla(dataset: str, buscar: str | None = None, desde: int | None = None, hasta: int | None = None,
          cementerio: str | None = None, orden: str | None = None, dir: str = "desc",
          pagina: int = 1, tamano: int = Query(50, le=500)):
    select, count, p = table_query(dataset, buscar, desde, hasta, cementerio, orden, dir)
    total = q1(count, p)
    rows = q(f"{select} LIMIT {tamano} OFFSET {(max(pagina, 1) - 1) * tamano}", p)
    for r in rows:
        for c, v in r.items():
            if v is not None and not isinstance(v, (int, float, str, bool)):
                r[c] = str(v)
    return {"columnas": DATASETS[dataset]["columnas"], "total": total, "pagina": pagina,
            "tamano": tamano, "filas": rows}


@app.get("/api/tabla/{dataset}/csv")
def tabla_csv(dataset: str, buscar: str | None = None, desde: int | None = None, hasta: int | None = None,
              cementerio: str | None = None, orden: str | None = None, dir: str = "desc"):
    select, _, p = table_query(dataset, buscar, desde, hasta, cementerio, orden, dir)

    def rows():
        cur = con.cursor()
        res = cur.execute(select, p)
        buf = io.StringIO()
        writer = csv.writer(buf, delimiter=";")
        # BOM para que Excel abra los acentos correctamente
        buf.write("\ufeff")
        writer.writerow([d[0] for d in res.description])
        while batch := res.fetchmany(5000):
            writer.writerows(batch)
            yield buf.getvalue()
            buf.seek(0)
            buf.truncate()
        yield buf.getvalue()

    return StreamingResponse(rows(), media_type="text/csv; charset=utf-8",
                             headers={"Content-Disposition": f'attachment; filename="{dataset}.csv"'})


@app.post("/api/cargar")
def cargar(archivos: list[UploadFile] = File(...)):
    resultados = []
    staging = etl.RAW_DIR.parent / "subidas"
    staging.mkdir(parents=True, exist_ok=True)
    cur = con.cursor()
    for up in archivos:
        nombre = Path(up.filename or "archivo.xlsx").name
        if Path(nombre).suffix.lower() not in {".xlsx", ".csv"}:
            resultados.append({"archivo": nombre, "ok": False, "mensaje": "Formato no soportado (.xlsx o .csv)."})
            continue
        temporal = staging / nombre
        with temporal.open("wb") as fh:
            shutil.copyfileobj(up.file, fh, length=4 * 1024 * 1024)
        try:
            with write_lock:
                key, n = etl.load_file(cur, temporal)
            if key:
                temporal.replace(etl.RAW_DIR / nombre)
                resultados.append({"archivo": nombre, "ok": True, "dataset": key, "filas": n,
                                   "mensaje": f"Reconocido como {etl.DATASETS[key]['titulo']}: {n:,} filas."})
            else:
                resultados.append({"archivo": nombre, "ok": False,
                                   "mensaje": "No se reconoció el reporte por sus encabezados."})
        except Exception as exc:  # el archivo puede venir corrupto o con otra estructura
            resultados.append({"archivo": nombre, "ok": False, "mensaje": f"No se pudo leer el archivo: {str(exc).splitlines()[0]}"})
        finally:
            temporal.unlink(missing_ok=True)
    with write_lock:
        etl.build_views(cur)
        ensure_funerarias_view(cur)
    return {"resultados": resultados}


app.mount("/", StaticFiles(directory=ROOT / "web", html=True), name="web")
