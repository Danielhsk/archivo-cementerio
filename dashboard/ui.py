"""Estilo visual (boceto "Archivo"), componentes HTML y tema de gráficos Plotly."""
from __future__ import annotations

import html

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

PALETTE = ["#2f4a3f", "#b0894f", "#8c5a44", "#7d9a8a", "#4f5d75", "#c9b38a", "#a3a08d", "#d08c60", "#5c7a6a", "#9b7b5b"]

CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Newsreader:opsz,wght@6..72,400;6..72,500&family=Inter:wght@400;500;600&family=JetBrains+Mono:wght@400;500&display=swap');

:root {
  --surface: #fcfbf8; --line: #e6e1d6; --ink: #1d2420; --muted: #6d6a62; --faint: #9a958a;
  --side: #141d19; --side-2: #1f2a25; --gold: #c4a46a; --ok: #3f6b52; --danger: #a5463a;
  --serif: "Newsreader", Georgia, serif; --mono: "JetBrains Mono", Consolas, monospace;
}

html, body, .stApp, .stMarkdown, p, label, input, button { font-family: "Inter", "Segoe UI", sans-serif; }
[data-testid="stIconMaterial"] { font-family: "Material Symbols Rounded" !important; }
.block-container { padding-top: 2.6rem; padding-bottom: 4rem; max-width: 1280px; }
header[data-testid="stHeader"] { background: transparent; }

/* Sidebar */
[data-testid="stSidebar"] { background: var(--side); }
[data-testid="stSidebar"] span, [data-testid="stSidebar"] p { color: #d9ddd6; }
[data-testid="stSidebarNavLink"] { border-radius: 8px; }
[data-testid="stSidebarNavLink"][aria-current="page"] { background: var(--side-2); }
[data-testid="stSidebarNavLink"][aria-current="page"] span { color: #fff !important; }
[data-testid="stSidebarNavLink"]:hover { background: rgba(255,255,255,.05); }
[data-testid="stNavSectionHeader"], [data-testid="stNavSectionHeader"] * {
  font-family: var(--mono) !important; font-size: 10px !important; letter-spacing: .18em;
  text-transform: uppercase; color: #7f8a83 !important;
}
[data-testid="stSidebarNavLink"] [data-testid="stIconMaterial"] { color: #7f8a83 !important; }
[data-testid="stSidebarNavLink"][aria-current="page"] [data-testid="stIconMaterial"] { color: var(--gold) !important; }
.side-foot { margin-top: 18px; padding: 14px; border: 1px solid #26312c; border-radius: 12px; font-size: 12.5px; }
.side-foot b { display: block; color: #f1efe9; font-weight: 500; margin-bottom: 4px; }
.side-foot span { font-family: var(--mono); font-size: 10.5px; color: #7f8a83 !important; line-height: 1.6; }

/* Encabezados */
.eyebrow, .lbl { font-family: var(--mono); font-size: 10.5px; letter-spacing: .18em; text-transform: uppercase; color: var(--faint); }
h1.page-title { font-family: var(--serif) !important; font-weight: 400 !important; font-size: 42px !important;
  letter-spacing: -.01em; margin: 6px 0 6px !important; padding: 0 !important; color: var(--ink); }
.lead { color: var(--muted); max-width: 680px; line-height: 1.55; margin: 0 0 6px; }
hr.rule { border: 0; border-top: 1px solid var(--line); margin: 18px 0 22px; }
h3.card-title { font-family: var(--serif) !important; font-weight: 400 !important; font-size: 19px !important;
  padding: 0 !important; margin: 0 0 2px !important; color: var(--ink); }
.note { font-size: 12px; color: var(--faint); margin-top: -6px; }

/* Tarjetas */
[data-testid="stVerticalBlockBorderWrapper"], div[data-testid="stVerticalBlock"][class*="border"] {
  background: var(--surface); border-color: var(--line) !important; border-radius: 14px !important;
}
.kpi { background: var(--surface); border: 1px solid var(--line); border-radius: 14px; padding: 16px 20px 18px; height: 100%; }
.kpi .value { font-family: var(--serif); font-size: 32px; line-height: 1.05; margin-top: 10px; color: var(--ink); }
.kpi.small .value { font-size: 25px; }
.kpi .hint { margin-top: 8px; font-size: 12.5px; color: var(--muted); }
.up { color: var(--ok); } .down { color: var(--danger); }
.report { background: var(--surface); border: 1px solid var(--line); border-radius: 14px; padding: 16px 18px; height: 100%; }
.report p { margin: 10px 0 12px; font-size: 13.5px; line-height: 1.5; color: var(--ink); }
.report .meta { font-family: var(--mono); font-size: 10.5px; color: var(--faint); line-height: 1.7; }
.pill { float: right; padding: 2px 9px; border-radius: 999px; font-family: var(--mono); font-size: 10px; letter-spacing: .08em; text-transform: uppercase; }
.pill.good { background: #e3eee6; color: var(--ok); } .pill.bad { background: #f5e3df; color: var(--danger); }

/* Controles */
[data-testid="stWidgetLabel"] p { font-family: var(--mono); font-size: 10px !important; letter-spacing: .16em; text-transform: uppercase; color: var(--faint); }
[data-baseweb="select"] > div, [data-testid="stTextInput"] input { background: var(--surface); border-radius: 9px; }
.stButton button, .stDownloadButton button { border-radius: 999px; }
[data-testid="stFileUploaderDropzone"] { background: var(--surface); border: 1px dashed #d6cfc0; border-radius: 14px; padding: 42px 24px; }
</style>
"""


def inject_css() -> None:
    st.markdown(CSS, unsafe_allow_html=True)


def page_header(eyebrow: str, title: str, lead: str) -> None:
    st.markdown(f'<div class="eyebrow">{eyebrow}</div><h1 class="page-title">{title}</h1>'
                f'<p class="lead">{lead}</p>', unsafe_allow_html=True)


def rule() -> None:
    st.markdown('<hr class="rule">', unsafe_allow_html=True)


# ---------------------------------------------------------------- formatos

def n(v) -> str:
    return "—" if v is None or pd.isna(v) else f"{v:,.0f}".replace(",", ".")


def d(v) -> str:
    return "—" if v is None or pd.isna(v) else f"{v:,.1f}".replace(",", "X").replace(".", ",").replace("X", ".")


def pct(v) -> str:
    return "—" if v is None or pd.isna(v) else d(v) + " %"


def money(v) -> str:
    if v is None or pd.isna(v):
        return "—"
    a = abs(v)
    if a >= 1e9:
        return "$" + d(v / 1e9) + " mil M"
    if a >= 1e6:
        return "$" + d(v / 1e6) + " M"
    return "$" + n(v)


def kpi(label: str, value: str, hint: str = "", small: bool = False) -> str:
    return (f'<div class="kpi {"small" if small else ""}"><div class="lbl">{label}</div>'
            f'<div class="value">{value}</div><div class="hint">{hint}</div></div>')


def kpi_row(cards: list[str]) -> None:
    for col, card in zip(st.columns(len(cards)), cards):
        col.markdown(card, unsafe_allow_html=True)


def esc(s) -> str:
    return html.escape(str(s or ""))


# ---------------------------------------------------------------- gráficos

def style(fig: go.Figure, height: int = 300, legend: bool = True) -> go.Figure:
    fig.update_layout(
        height=height, margin=dict(l=8, r=8, t=28 if legend else 8, b=8),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family="Inter, Segoe UI, sans-serif", size=12, color="#6d6a62"),
        colorway=PALETTE, separators=",.", showlegend=legend,
        legend=dict(orientation="h", yanchor="bottom", y=1.0, xanchor="right", x=1, title=None),
        hoverlabel=dict(bgcolor="#141d19", font_color="#fff", bordercolor="#141d19"),
        bargap=0.25,
    )
    fig.update_xaxes(showgrid=False, linecolor="#e6e1d6", title=None, automargin=True)
    fig.update_yaxes(gridcolor="#efebe2", zeroline=False, title=None, tickformat=",~f", automargin=True)
    return fig


def money_scale(values) -> tuple[float, str]:
    """Divisor y sufijo para mostrar montos en millones o miles de millones."""
    top = max((abs(float(x)) for x in values if pd.notna(x)), default=0)
    return (1e9, " mil M") if top >= 1e9 else (1e6, " M")


def chart_card(titulo: str, fig: go.Figure, subtitulo: str = "", nota: str = "") -> None:
    with st.container(border=True):
        sub = f'<span class="lbl" style="float:right;margin-top:6px">{subtitulo}</span>' if subtitulo else ""
        st.markdown(f'{sub}<h3 class="card-title">{titulo}</h3>', unsafe_allow_html=True)
        st.plotly_chart(fig, width="stretch", theme=None, config={"displayModeBar": False, "locale": "es"})
        if nota:
            st.markdown(f'<p class="note">{nota}</p>', unsafe_allow_html=True)


def simple_chart(tipo: str, data: pd.DataFrame, formato: str = "n", height: int = 300) -> go.Figure:
    """data con columnas k (etiqueta) y v (valor)."""
    k, v = data["k"].astype(str), data["v"].astype(float)
    if formato == "$":
        div, suf = money_scale(v)
        v = v / div
        hover = f"%{{label}}: $%{{value:,.1f}}{suf}<extra></extra>"
        ticks = dict(ticksuffix=suf, tickprefix="$", tickformat=",~f")
    elif formato == "d":
        hover, ticks = "%{label}: %{value:,.1f}<extra></extra>", {}
    else:
        hover, ticks = "%{label}: %{value:,.0f}<extra></extra>", {}

    if tipo == "dona":
        fig = go.Figure(go.Pie(labels=k, values=v, hole=.62, sort=False, marker=dict(colors=PALETTE, line=dict(color="#fcfbf8", width=2)),
                               textinfo="percent", textposition="inside", hovertemplate=hover))
        fig = style(fig, height)
        fig.update_layout(uniformtext_minsize=10, uniformtext_mode="hide", legend=dict(orientation="v", x=1.02, y=.5, xanchor="left", yanchor="middle"))
        return fig
    if tipo == "linea":
        fig = go.Figure(go.Scatter(x=k, y=v, mode="lines+markers", line=dict(color=PALETTE[0], width=2, shape="spline"),
                                   marker=dict(size=5), fill="tozeroy", fillcolor="rgba(47,74,63,.07)",
                                   hovertemplate=hover.replace("%{label}", "%{x}").replace("%{value", "%{y")))
        fig = style(fig, height, legend=False)
        fig.update_yaxes(**ticks)
        return fig
    horizontal = tipo == "hbarra"
    fig = go.Figure(go.Bar(
        x=v if horizontal else k, y=k if horizontal else v, orientation="h" if horizontal else "v",
        marker=dict(color=PALETTE[0], cornerradius=4),
        hovertemplate=hover.replace("%{label}", "%{y}" if horizontal else "%{x}").replace("%{value", "%{x" if horizontal else "%{y"),
    ))
    fig = style(fig, height, legend=False)
    if horizontal:
        fig.update_yaxes(autorange="reversed", gridcolor="rgba(0,0,0,0)")
        fig.update_xaxes(showgrid=True, gridcolor="#efebe2", **({"tickformat": ",~f"} | ticks))
    else:
        fig.update_xaxes(type="category")
        fig.update_yaxes(**ticks)
    return fig
