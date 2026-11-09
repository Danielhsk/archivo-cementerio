"""Páginas del dashboard."""
from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from dashboard import data, ui
from dashboard.ui import PALETTE

TITULOS = {"facturas": "Facturas", "cremaciones": "Cremaciones", "exhumaciones": "Exhumaciones"}


def filtros(con_cementerio: bool = True) -> tuple:
    """Filtros globales (año desde, hasta, cementerio). Se conservan entre páginas vía session_state."""
    m = data.meta()
    anios = [0] + m["anios"]
    cols = st.columns([1, 1, 1.6, 3] if con_cementerio else [1, 1, 4.6])
    cols[0].selectbox("Desde", anios, key="f_desde", format_func=lambda x: str(x) if x else "Inicio")
    cols[1].selectbox("Hasta", anios, key="f_hasta", format_func=lambda x: str(x) if x else "Fin")
    if con_cementerio:
        cems = [""] + list(m["cementerios"])
        cols[2].selectbox("Cementerio", cems, key="f_cem",
                          format_func=lambda x: m["cementerios"][x] if x else "Todos los cementerios")
    return st.session_state.f_desde, st.session_state.f_hasta, st.session_state.f_cem if con_cementerio else None


def sin_datos(msg: str = "Todavía no hay reportes cargados.") -> None:
    st.info(msg + " Súbelos en la página **Archivos**.")


# ================================================================ Resumen

def resumen() -> None:
    ui.page_header("Resumen", "Panorama general",
                   "Indicadores clave de facturación, cremaciones y exhumaciones. Los filtros aplican a todas las cifras de esta página.")
    if not data.meta()["cargados"]:
        ui.rule()
        return sin_datos()
    desde, hasta, cem = filtros()
    ui.rule()
    with st.spinner("Calculando…"):
        r = data.resumen(desde, hasta, cem)
    k = r["kpis"]
    ui.kpi_row([
        ui.kpi("Facturado neto", ui.money(k.get("facturado")), "$" + ui.n(k.get("facturado"))),
        ui.kpi("Facturas emitidas", ui.n(k.get("facturas")), f"Ticket promedio {ui.money(k.get('ticket'))}"),
        ui.kpi("Cremaciones", ui.n(k.get("cremaciones")), f"Edad promedio {ui.d(k.get('edad_cremaciones'))} años"),
        ui.kpi("Exhumaciones", ui.n(k.get("exhumaciones")), f"{ui.pct(k.get('pct_exh_cremacion'))} pasan a cremación"),
    ])
    st.write("")
    ui.kpi_row([
        ui.kpi("Facturas anuladas", ui.n(k.get("anuladas")),
               f"{ui.pct(k.get('pct_anuladas'))} del total · {ui.money(k.get('valor_anulado'))}", True),
        ui.kpi("Clientes únicos (NIT)", ui.n(k.get("clientes")), "Pagadores distintos en facturación", True),
        ui.kpi("Años sepultado", ui.d(k.get("anios_sepultado")), "Mediana entre inhumación y exhumación", True),
        ui.kpi("Edad promedio exhumados", ui.d(k.get("edad_exhumaciones")), "Al momento del fallecimiento", True),
    ])
    st.write("")

    fig = go.Figure()
    for i, (nombre, dfm) in enumerate(r["mensual"].items()):
        fig.add_scatter(x=dfm["mes"], y=dfm["n"], name=nombre, mode="lines", line=dict(width=1.6, color=PALETTE[i]),
                        hovertemplate="%{y:,.0f}")
    ui.style(fig, 340).update_layout(hovermode="x unified")
    ui.chart_card("Actividad mensual", fig, "Registros por mes")

    c1, c2 = st.columns(2)
    with c1:
        fa = r["anual"].get("facturas", pd.DataFrame(columns=["anio", "n", "valor"]))
        div, suf = ui.money_scale(fa["valor"])
        fig = go.Figure()
        fig.add_bar(x=fa["anio"], y=fa["valor"] / div, name="Valor neto", marker=dict(color=PALETTE[0], cornerradius=4),
                    hovertemplate=f"$%{{y:,.1f}}{suf}")
        fig.add_scatter(x=fa["anio"], y=fa["n"], name="Facturas", yaxis="y2", mode="lines+markers",
                        line=dict(color=PALETTE[1], width=2, shape="spline"), marker=dict(size=4), hovertemplate="%{y:,.0f}")
        ui.style(fig, 300).update_layout(
            hovermode="x unified",
            yaxis=dict(tickprefix="$", ticksuffix=suf, rangemode="tozero"),
            yaxis2=dict(overlaying="y", side="right", showgrid=False, rangemode="tozero"))
        ui.chart_card("Facturación anual", fig, "Valor neto y facturas")
    with c2:
        fig = go.Figure()
        for i, key in enumerate(["cremaciones", "exhumaciones"]):
            if key in r["anual"]:
                a = r["anual"][key]
                fig.add_bar(x=a["anio"], y=a["n"], name=key.capitalize(), marker=dict(color=PALETTE[i + 1], cornerradius=3),
                            hovertemplate="%{y:,.0f}")
        ui.style(fig, 300).update_layout(barmode="group", hovermode="x unified")
        ui.chart_card("Servicios por año", fig, "Cremaciones y exhumaciones")

    c1, c2 = st.columns(2)
    with c1:
        fig = go.Figure()
        cem = r["cementerios"]
        nombres = sorted({x for dfc in cem.values() for x in dfc["nombre"]})
        for i, nombre in enumerate(nombres):
            vals = []
            for dfc in cem.values():
                total = dfc["v"].sum() or 1
                vals.append(float(dfc.loc[dfc["nombre"] == nombre, "v"].sum()) / total * 100)
            fig.add_bar(y=list(cem.keys()), x=vals, name=nombre, orientation="h", marker_color=PALETTE[i % len(PALETTE)],
                        hovertemplate="%{x:.1f} %")
        ui.style(fig, 300).update_layout(barmode="stack")
        fig.update_xaxes(ticksuffix=" %", range=[0, 100], showgrid=True, gridcolor="#efebe2")
        fig.update_yaxes(autorange="reversed")
        ui.chart_card("Por cementerio", fig, "Participación de cada sede")
    with c2:
        f = r["funerarias"].rename(columns={"nombre": "k", "valor": "v"})
        ui.chart_card("Top 10 funerarias", ui.simple_chart("hbarra", f, "$"), "Valor facturado")


# ================================================================ Archivos

def archivos() -> None:
    ui.page_header("Archivos", "Carga de datos",
                   "Sube la hoja de Excel (.xlsx) de cada reporte exportado de KNIME. El panel reconoce el tipo de archivo "
                   "por sus encabezados, lo procesa con DuckDB y lo deja listo para consultar, filtrar y comparar.")
    ui.rule()
    host = st.context.headers.get("Host", "localhost").split(":")[0]
    if host not in ("localhost", "127.0.0.1"):
        st.info("La carga de archivos solo está habilitada en el equipo donde corre el dashboard. "
                "Este enlace público es de solo lectura.")
        subidos = None
    else:
        subidos = st.file_uploader("Arrastra tus hojas de Excel aquí", type=["xlsx", "csv"], accept_multiple_files=True,
                                   help="Los reportes grandes (más de 100 MB) pueden tardar alrededor de un minuto.")
    if subidos and st.button("Procesar archivos", type="primary"):
        for f in subidos:
            with st.spinner(f"Procesando {f.name}…"):
                res = data.cargar(f.name, f.getvalue())
            (st.success if res["ok"] else st.error)(f"**{f.name}** — {res['mensaje']}")

    st.markdown('<div class="lbl" style="margin:28px 0 12px">Reportes que reconoce el panel</div>', unsafe_allow_html=True)
    ds = data.meta()["datasets"]
    for fila in range(0, len(ds), 3):
        cols = st.columns(3)
        for col, dset in zip(cols, ds[fila:fila + 3]):
            pill = '<span class="pill good">Cargado</span>' if dset["cargado"] else '<span class="pill bad">Pendiente</span>'
            meta = [f"Fecha: {dset['fecha']}" if dset["fecha"] else "Sin campo de fecha"]
            if dset["cargado"]:
                meta.append(f"{ui.n(dset.get('filas'))} filas · {ui.esc(dset.get('archivo'))}")
            if dset.get("desde"):
                meta.append(f"Rango válido: {dset['desde']} → {dset['hasta']}")
            if dset.get("actualizado"):
                meta.append(f"Actualizado: {dset['actualizado']}")
            col.markdown(f'<div class="report">{pill}<span class="lbl">{dset["titulo"]}</span>'
                         f'<p>{ui.esc(dset["descripcion"])}</p><div class="meta">{"<br>".join(meta)}</div></div>',
                         unsafe_allow_html=True)
        st.write("")


# ================================================================ Tablas

TABLAS = {
    "facturas": ("Facturas", "Detalle de la facturación. Busca por número de factura, pagador, NIT, fallecido o cédula."),
    "cremaciones": ("Cremaciones", "Certificados de cremación. Busca por factura, certificado, licencia, nombre o cédula."),
    "exhumaciones": ("Exhumaciones", "Exhumaciones con su inhumación de origen. Busca por factura, licencia, nombre, reclamante o deudor."),
    "funerarias": ("Funerarias", "Maestro de funerarias cruzado con la facturación neta y las cremaciones atendidas."),
}

ETIQUETAS = {
    "factura": "Factura", "fecha": "Fecha", "recibido_d": "Recibido de", "nit": "NIT", "fallecido": "Fallecido",
    "forma_pago_nombre": "Forma de pago", "valor": "Valor", "funeraria_nombre": "Funeraria",
    "cementerio_nombre": "Cementerio", "es_anulada": "Anulada", "fecha_cre": "Fecha cremación",
    "certificad": "Certificado", "licencia": "Licencia", "nombre": "Nombre", "tipo_crema_nombre": "Tipo",
    "sexo_nombre": "Sexo", "edad_valida": "Edad", "destino_nombre": "Destino", "con_urna": "Urna",
    "factura_ex": "Factura", "fecha_exh": "Fecha exhumación", "fecha_inh": "Fecha inhumación", "galeria": "Galería",
    "lugar_no": "Lugar", "anios_sepultado": "Años sepultado", "reclamante": "Reclamante", "facturas": "Facturas",
    "valor_facturado": "Valor facturado", "cremaciones": "Cremaciones",
}


def tabla(dataset: str) -> None:
    titulo, lead = TABLAS[dataset]
    ui.page_header("Tablas", titulo, lead)
    ui.rule()
    if dataset not in data.meta()["cargados"]:
        return sin_datos("Este reporte aún no está cargado.")

    cols = st.columns([2.2, 1, 1, 1.5, 1.4, .8])
    buscar = cols[0].text_input("Buscar", key=f"q_{dataset}", placeholder="Escribe y presiona Enter…")
    desde = hasta = cem = None
    m = data.meta()
    if data.FECHAS[dataset]:
        anios = [0] + m["anios"]
        desde = cols[1].selectbox("Desde", anios, key="f_desde", format_func=lambda x: str(x) if x else "Inicio")
        hasta = cols[2].selectbox("Hasta", anios, key="f_hasta", format_func=lambda x: str(x) if x else "Fin")
        cem = cols[3].selectbox("Cementerio", [""] + list(m["cementerios"]), key="f_cem",
                                format_func=lambda x: m["cementerios"][x] if x else "Todos")
    columnas = data.COLUMNAS[dataset]
    defecto = data.FECHAS[dataset] or columnas[0]
    orden = cols[4].selectbox("Ordenar por", columnas, index=columnas.index(defecto), key=f"o_{dataset}",
                              format_func=lambda c: ETIQUETAS.get(c, c))
    asc = cols[5].selectbox("Sentido", [False, True], key=f"a_{dataset}", format_func=lambda x: "↑ Asc" if x else "↓ Desc")

    tamano = 50
    filtros_actuales = (buscar, desde, hasta, cem, orden, asc)
    if st.session_state.get(f"prev_{dataset}") != filtros_actuales:
        st.session_state[f"p_{dataset}"] = 1
        st.session_state[f"prev_{dataset}"] = filtros_actuales
    pagina = st.session_state.get(f"p_{dataset}", 1)

    filas, total = data.tabla(dataset, buscar, desde, hasta, cem, orden, asc, pagina, tamano)
    paginas = max(1, -(-total // tamano))
    config = {c: st.column_config.Column(ETIQUETAS.get(c, c)) for c in columnas}
    for c in ("valor", "valor_facturado"):
        if c in columnas:
            config[c] = st.column_config.NumberColumn(ETIQUETAS[c], format="$ %,.0f")
    for c in ("edad_valida", "anios_sepultado"):
        if c in columnas:
            config[c] = st.column_config.NumberColumn(ETIQUETAS[c], format="%.1f")
    for c in ("fecha", "fecha_cre", "fecha_exh", "fecha_inh"):
        if c in columnas:
            config[c] = st.column_config.DateColumn(ETIQUETAS[c], format="YYYY-MM-DD")
    st.dataframe(filas, column_config=config, hide_index=True, width="stretch", height=min(38 + 35 * len(filas), 640))

    f1, f2, f3, f4 = st.columns([3, 1, 1, 1.4])
    f1.markdown(f'<div class="lbl" style="margin-top:10px">{ui.n(total)} registros · página {ui.n(pagina)} de {ui.n(paginas)}</div>',
                unsafe_allow_html=True)
    if f2.button("Anterior", disabled=pagina <= 1, width="stretch", key=f"prev_btn_{dataset}"):
        st.session_state[f"p_{dataset}"] = pagina - 1
        st.rerun()
    if f3.button("Siguiente", disabled=pagina >= paginas, width="stretch", key=f"next_btn_{dataset}"):
        st.session_state[f"p_{dataset}"] = pagina + 1
        st.rerun()
    if total <= 200_000:
        f4.download_button("Exportar CSV", data.tabla_csv(dataset, buscar, desde, hasta, cem, orden, asc),
                           file_name=f"{dataset}.csv", mime="text/csv", width="stretch")
    else:
        f4.button("Exportar CSV", disabled=True, width="stretch",
                  help="Filtra a 200.000 registros o menos para exportar.", key=f"csv_off_{dataset}")


# ================================================================ Estadísticas

def estadisticas() -> None:
    ui.page_header("Análisis", "Estadísticas",
                   "Distribuciones y patrones de cada reporte: composición, perfiles de edad y sexo, estacionalidad y principales funerarias.")
    disponibles = [k for k in TITULOS if k in data.meta()["cargados"]]
    if not disponibles:
        ui.rule()
        return sin_datos()
    desde, hasta, cem = filtros()
    ui.rule()
    dataset = st.segmented_control("Reporte", disponibles, default=disponibles[0], key="est_ds",
                                   format_func=TITULOS.get, label_visibility="collapsed") or disponibles[0]
    with st.spinner("Calculando…"):
        graficos = data.estadisticas(dataset, desde, hasta, cem)
    for i in range(0, len(graficos), 2):
        cols = st.columns(2)
        for col, g in zip(cols, graficos[i:i + 2]):
            with col:
                ui.chart_card(g["titulo"], ui.simple_chart(g["tipo"], g["datos"], g["formato"]), nota=g["nota"])


# ================================================================ Comparaciones

def comparaciones() -> None:
    ui.page_header("Análisis", "Comparaciones",
                   "Contrasta dos años mes a mes, mira cómo cambia la participación de cada cementerio y sigue la tendencia histórica.")
    m = data.meta()
    disponibles = [k for k in data.METRICAS if k in m["cargados"]]
    if not disponibles:
        ui.rule()
        return sin_datos()
    anios = m["anios"]
    cols = st.columns([1.2, 1.4, 1, 1, 1.6])
    dataset = cols[0].selectbox("Reporte", disponibles, format_func=TITULOS.get, key="c_ds")
    metricas = data.METRICAS[dataset]
    metrica = cols[1].selectbox("Métrica", list(metricas), format_func=lambda x: metricas[x][0], key=f"c_m_{dataset}")
    a = cols[2].selectbox("Año base", anios, index=max(0, len(anios) - 3), key="c_a")
    b = cols[3].selectbox("Año a comparar", anios, index=max(0, len(anios) - 2), key="c_b")
    cem = cols[4].selectbox("Cementerio", [""] + list(m["cementerios"]), key="c_cem",
                            format_func=lambda x: m["cementerios"][x] if x else "Todos los cementerios")
    ui.rule()

    r = data.comparar(dataset, metrica, a, b, cem)
    es_dinero = metrica == "valor"
    fmt = ui.money if es_dinero else ui.n
    escala, suf = ui.money_scale(r["tendencia"]["v"]) if es_dinero else (1, "")
    hover = f"$%{{y:,.1f}}{suf}" if es_dinero else "%{y:,.0f}"
    var = r["variacion"]
    var_txt = "—" if var is None else f'<span class="{"up" if var >= 0 else "down"}">{"+" if var >= 0 else ""}{ui.d(var)} %</span>'
    nombre = metricas[metrica][0]
    ui.kpi_row([ui.kpi(f"Total {a}", fmt(r["totales"][0]), nombre),
                ui.kpi(f"Total {b}", fmt(r["totales"][1]), nombre),
                ui.kpi("Variación", var_txt, f"{b} frente a {a}")])
    st.write("")

    fig = go.Figure()
    for i, (anio, serie) in enumerate(r["mensual"].items()):
        fig.add_scatter(x=data.MESES, y=[v / escala for v in serie], name=anio, mode="lines+markers",
                        line=dict(color=PALETTE[i], width=2, shape="spline"), marker=dict(size=6), hovertemplate=hover)
    ui.style(fig, 340).update_layout(hovermode="x unified")
    fig.update_yaxes(rangemode="tozero")
    if es_dinero:
        fig.update_yaxes(tickprefix="$", ticksuffix=suf)
    ui.chart_card("Mes a mes", fig, nombre)

    c1, c2 = st.columns(2)
    with c1:
        pc = r["por_cem"]
        fig = go.Figure()
        for i, anio in enumerate([str(a), str(b)]):
            s = pc[pc["anio"] == anio]
            fig.add_bar(x=s["c"], y=s["v"] / escala, name=anio, marker=dict(color=PALETTE[i], cornerradius=4), hovertemplate=hover)
        ui.style(fig, 320).update_layout(barmode="group", hovermode="x unified")
        if es_dinero:
            fig.update_yaxes(tickprefix="$", ticksuffix=suf)
        ui.chart_card("Por cementerio", fig, "Ambos años")
    with c2:
        t = r["tendencia"]
        fig = go.Figure()
        for i, c in enumerate(sorted(t["c"].unique())):
            s = t[t["c"] == c]
            fig.add_bar(x=s["anio"], y=s["v"] / escala, name=c, marker_color=PALETTE[i % len(PALETTE)], hovertemplate=hover)
        ui.style(fig, 320).update_layout(barmode="stack", hovermode="x unified")
        if es_dinero:
            fig.update_yaxes(tickprefix="$", ticksuffix=suf)
        ui.chart_card("Tendencia histórica", fig, "Apilado por cementerio")
