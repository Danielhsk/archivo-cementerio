"""Dashboard de cementerio y funeraria. Ejecutar con: streamlit run streamlit_app.py"""
from pathlib import Path

import streamlit as st

from dashboard import data, pages, ui

st.set_page_config(page_title="Archivo · Cementerio y funeraria", page_icon="🕯️", layout="wide")
ui.inject_css()
st.logo(str(Path(__file__).parent / "dashboard" / "assets" / "logo.svg"), size="large")

# Filtros compartidos entre páginas: reasignarlos evita que Streamlit los borre al cambiar de página.
for key, todos in (("f_desde", 0), ("f_hasta", 0), ("f_cem", "")):
    st.session_state[key] = st.session_state.get(key, todos)

nav = st.navigation({
    "": [
        st.Page(pages.resumen, title="Resumen", icon=":material/grid_view:", default=True),
        st.Page(pages.archivos, title="Archivos", icon=":material/upload:", url_path="archivos"),
    ],
    "Tablas": [
        st.Page(lambda: pages.tabla("exhumaciones"), title="Exhumaciones", icon=":material/layers:", url_path="exhumaciones"),
        st.Page(lambda: pages.tabla("cremaciones"), title="Cremaciones", icon=":material/local_fire_department:", url_path="cremaciones"),
        st.Page(lambda: pages.tabla("facturas"), title="Facturas", icon=":material/receipt_long:", url_path="facturas"),
        st.Page(lambda: pages.tabla("funerarias"), title="Funerarias", icon=":material/groups:", url_path="funerarias"),
    ],
    "Análisis": [
        st.Page(pages.estadisticas, title="Estadísticas", icon=":material/bar_chart:", url_path="estadisticas"),
        st.Page(pages.comparaciones, title="Comparaciones", icon=":material/compare_arrows:", url_path="comparaciones"),
    ],
})

m = data.meta()
total = sum(d.get("filas", 0) or 0 for d in m["datasets"] if d["cargado"])
st.sidebar.markdown(
    f'<div class="side-foot"><b>Fuente de datos</b><span>{len(m["cargados"])} de {len(m["datasets"])} reportes · '
    f'{ui.n(total)} filas<br>DuckDB local</span></div>', unsafe_allow_html=True)

nav.run()
