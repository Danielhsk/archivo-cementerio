# Archivo · Dashboard de cementerio y funeraria

Dashboard interactivo en [Streamlit](https://streamlit.io) para analizar los reportes exportados desde KNIME (facturas, cremaciones, exhumaciones y funerarias). Los Excel se convierten a una base analítica local [DuckDB](https://duckdb.org) y se consultan desde la interfaz con métricas, tablas filtrables, estadísticas y comparaciones.

## Requisitos

- Python 3.10 o superior
- Conexión a internet la primera vez (para instalar dependencias y la extensión de Excel de DuckDB)

## Ejecutar

1. Copia los reportes `.xlsx` en `data/raw/` (por ejemplo `KnimeFactura.xlsx`, `KnimeCremados1.xlsx`, `KnimeExhumados.xlsx`, `KnimeFuneraria.xlsx`). Los nombres no importan: cada reporte se reconoce por sus encabezados.
2. Ejecuta:
   - **Windows**: doble clic en `iniciar.bat`
   - **Mac / Linux**: `sh iniciar.sh`
   - **Manual**:
     ```bash
     pip install -r requirements.txt
     python run.py            # o: streamlit run streamlit_app.py
     ```
3. Se abre el navegador en <http://localhost:8501>.

La primera ejecución procesa los Excel (unos 40 segundos para ~840 mil filas). También puedes arrancar sin datos y subir los archivos desde la página **Archivos**.

## Compartir con un enlace público

Con el dashboard corriendo, en otra terminal:

```bash
cloudflared tunnel --url http://localhost:8501
```

`cloudflared` imprime una URL `https://<algo>.trycloudflare.com` que cualquiera puede abrir mientras tu equipo y el túnel sigan encendidos. Desde ese enlace la carga de archivos está deshabilitada: solo se puede subir datos desde `localhost`.

Ten en cuenta que los reportes contienen datos personales (nombres, cédulas, direcciones de deudos): comparte el enlace solo con quien deba verlos.

## Secciones

| Sección | Contenido |
| --- | --- |
| Resumen | KPIs (facturado neto, facturas, ticket promedio, cremaciones, exhumaciones, anulaciones), actividad mensual, facturación anual, participación por cementerio y top de funerarias |
| Archivos | Carga de Excel/CSV con detección automática del tipo de reporte y estado de cada fuente |
| Tablas | Exhumaciones, Cremaciones, Facturas y Funerarias con búsqueda, filtros, orden, paginación y exportación a CSV |
| Estadísticas | Distribuciones por reporte: forma de pago, rangos de valor, estacionalidad, edad, sexo, tipo, destino, años sepultado |
| Comparaciones | Año contra año mes a mes, comparación por cementerio y tendencia histórica apilada |

## Estructura

```
streamlit_app.py       Punto de entrada: navegación y barra lateral
dashboard/data.py      Consultas a DuckDB (con caché de Streamlit)
dashboard/pages.py     Páginas del dashboard
dashboard/ui.py        Estilo visual, tarjetas y tema de los gráficos Plotly
etl/build_db.py        Lee los Excel, limpia y crea data/cementerio.duckdb con tablas y vistas analíticas
etl/catalogos.json     Etiquetas de los códigos (cementerio, forma de pago, tipo de cremación...)
.streamlit/config.toml Tema y límites (carga hasta 500 MB)
```

## Limpieza de datos aplicada

- KNIME exporta una fila de nombres genéricos (`Column0`, `Column1`…) antes de los encabezados reales y duplica cada columna con sufijo `_transformed`. El ETL detecta la fila de encabezados y usa solo la primera copia de cada columna.
- Se quitan las comillas que envuelven los textos y las fechas vacías de FoxPro (`/  /`).
- El sistema de origen perdió la codificación de la ñ y de la terminación "-ción"; se restauran (por ejemplo `Mu�oz` pasa a `Muñoz`).
- Se consideran solo fechas entre el año 2000 y hoy (hay registros con años 1, 1900 o 2070).
- La edad 0 se trata como "sin dato" (más de 120 mil cremaciones la tienen).
- Los códigos que no están en el catálogo (errores de digitación como `?` o `|`) se agrupan como "Otro código".

## Personalizar etiquetas

Los reportes traen códigos sin descripción (`cementerio` 01–04, `forma_pago` 1–7, `tipo_crema` 1–2, etc.). Edita `etl/catalogos.json` con los nombres reales y reinicia el dashboard: las vistas se recrean al arrancar.

## Notas

- `data/raw/` y la base `.duckdb` están excluidas de git porque pesan cientos de MB y contienen datos personales.
- Para volver a procesar todo desde cero: `python etl/build_db.py` (con el dashboard detenido, porque DuckDB bloquea el archivo mientras está abierto).
