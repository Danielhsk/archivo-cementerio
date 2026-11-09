"use strict";

/* ================= Utilidades ================= */

const ICONS = {
  grid: '<path d="M3 3h7v7H3zM14 3h7v7h-7zM3 14h7v7H3zM14 14h7v7h-7z"/>',
  upload: '<path d="M12 15V3M7 8l5-5 5 5M4 15v4a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-4"/>',
  layers: '<path d="m12 2 10 5-10 5L2 7zM2 17l10 5 10-5M2 12l10 5 10-5"/>',
  flame: '<path d="M8.5 14.5A2.5 2.5 0 0 0 11 12c0-1.38-.5-2-1-3-1.07-2.14-.22-4.05 2-6 .5 2.5 2 4.9 4 6.5 2 1.6 3 3.5 3 5.5a7 7 0 1 1-14 0c0-1.15.43-2.29 1-3a2.5 2.5 0 0 0 2.5 2.5z"/>',
  file: '<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8zM14 2v6h6M16 13H8M16 17H8M10 9H8"/>',
  users: '<path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2M9 11a4 4 0 1 0 0-8 4 4 0 0 0 0 8zM22 21v-2a4 4 0 0 0-3-3.87M16 3.13a4 4 0 0 1 0 7.75"/>',
  chart: '<path d="M3 3v18h18M7 16v-5M12 16V8M17 16v-8"/>',
  compare: '<path d="M16 3h5v5M8 21H3v-5M21 3l-7 7M3 21l7-7"/>',
  doc: '<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8zM14 2v6h6M12 18v-6M9 15l3-3 3 3"/>',
  alert: '<circle cx="12" cy="12" r="10"/><path d="M12 8v4M12 16h.01"/>',
  check: '<circle cx="12" cy="12" r="10"/><path d="m8 12 3 3 5-6"/>',
  download: '<path d="M12 3v12M7 10l5 5 5-5M4 17v2a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-2"/>',
};

const icon = (name) =>
  `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round">${ICONS[name]}</svg>`;

const $ = (sel, root = document) => root.querySelector(sel);
const $$ = (sel, root = document) => [...root.querySelectorAll(sel)];
const esc = (s) => String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));

const nf = new Intl.NumberFormat("es-CO");
const nf1 = new Intl.NumberFormat("es-CO", { maximumFractionDigits: 1 });
const money = new Intl.NumberFormat("es-CO", { style: "currency", currency: "COP", maximumFractionDigits: 0 });

function compactMoney(v) {
  if (v == null) return "—";
  const a = Math.abs(v);
  if (a >= 1e12) return "$" + nf1.format(v / 1e12) + " B";
  if (a >= 1e9) return "$" + nf1.format(v / 1e9) + " mil M";
  if (a >= 1e6) return "$" + nf1.format(v / 1e6) + " M";
  return money.format(v);
}

const fmt = {
  n: (v) => (v == null ? "—" : nf.format(Math.round(v))),
  d: (v) => (v == null ? "—" : nf1.format(v)),
  $: (v) => compactMoney(v),
  pct: (v) => (v == null ? "—" : nf1.format(v) + " %"),
};

async function api(path, params = {}) {
  const qs = new URLSearchParams(Object.entries(params).filter(([, v]) => v !== "" && v != null));
  const res = await fetch(`/api/${path}${qs.toString() ? "?" + qs : ""}`);
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail || `Error ${res.status}`);
  }
  return res.json();
}

/* ================= Gráficos ================= */

const PALETTE = ["#2f4a3f", "#b0894f", "#8c5a44", "#7d9a8a", "#4f5d75", "#c9b38a", "#a3a08d", "#d08c60", "#5c7a6a", "#9b7b5b"];

Chart.defaults.locale = "es-CO";
Chart.defaults.font.family = '"Inter", "Segoe UI", system-ui, sans-serif';
Chart.defaults.font.size = 11.5;
Chart.defaults.color = "#6d6a62";
Chart.defaults.borderColor = "#ebe6dc";
Chart.defaults.plugins.legend.labels.boxWidth = 10;
Chart.defaults.plugins.legend.labels.boxHeight = 10;
Chart.defaults.plugins.tooltip.backgroundColor = "#141d19";
Chart.defaults.plugins.tooltip.padding = 10;
Chart.defaults.plugins.tooltip.cornerRadius = 8;
Chart.defaults.maintainAspectRatio = false;

let charts = [];
function destroyCharts() {
  charts.forEach((c) => c.destroy());
  charts = [];
}

function makeChart(canvas, cfg) {
  const c = new Chart(canvas, cfg);
  charts.push(c);
  return c;
}

function axisFormatter(format) {
  return (v) => (format === "$" ? compactMoney(v) : fmt[format] ? fmt[format](v) : v);
}

/** Renderiza un gráfico simple a partir de {tipo, labels, values, formato}. */
function renderSimple(canvas, spec) {
  const f = spec.formato || "n";
  const labels = spec.labels.map((l) => l.replace(/^\d · /, "").trim());
  const tooltip = { callbacks: { label: (ctx) => ` ${f === "$" ? money.format(ctx.raw) : fmt[f](ctx.raw)}` } };
  if (spec.tipo === "doughnut") {
    return makeChart(canvas, {
      type: "doughnut",
      data: { labels, datasets: [{ data: spec.values, backgroundColor: PALETTE, borderColor: "#fcfbf8", borderWidth: 2 }] },
      options: {
        cutout: "62%",
        plugins: {
          legend: { position: "right" },
          tooltip: {
            callbacks: {
              label: (ctx) => {
                const total = ctx.dataset.data.reduce((a, b) => a + (b || 0), 0);
                const val = f === "$" ? money.format(ctx.raw) : fmt[f](ctx.raw);
                return ` ${ctx.label}: ${val} (${nf1.format((ctx.raw / total) * 100)} %)`;
              },
            },
          },
        },
      },
    });
  }
  const horizontal = spec.tipo === "hbar";
  const isLine = spec.tipo === "line";
  return makeChart(canvas, {
    type: isLine ? "line" : "bar",
    data: {
      labels,
      datasets: [{
        data: spec.values,
        backgroundColor: isLine ? "rgba(47,74,63,.08)" : PALETTE[0],
        borderColor: PALETTE[0],
        borderWidth: isLine ? 2 : 0,
        borderRadius: 4,
        fill: isLine,
        tension: 0.3,
        pointRadius: isLine ? 2 : 0,
        maxBarThickness: 38,
      }],
    },
    options: {
      indexAxis: horizontal ? "y" : "x",
      plugins: { legend: { display: false }, tooltip },
      scales: {
        [horizontal ? "x" : "y"]: { beginAtZero: !isLine, ticks: { callback: axisFormatter(f) }, grid: { color: "#efebe2" } },
        [horizontal ? "y" : "x"]: { grid: { display: false }, ticks: { autoSkip: !horizontal } },
      },
    },
  });
}

/* ================= Estado y filtros ================= */

const state = {
  meta: null,
  filtros: { desde: "", hasta: "", cementerio: "" },
  estDataset: "facturas",
  comp: { dataset: "facturas", metrica: "valor", a: "", b: "", cementerio: "" },
};

async function loadMeta() {
  state.meta = await api("meta");
  const loaded = state.meta.datasets.filter((d) => d.cargado);
  const total = loaded.reduce((a, d) => a + (d.filas || 0), 0);
  $("#foot-status").innerHTML = loaded.length
    ? `${loaded.length} de ${state.meta.datasets.length} reportes · ${nf.format(total)} filas<br>DuckDB local`
    : "Sin datos cargados";
  return state.meta;
}

function yearOptions(selected, placeholder) {
  const years = state.meta?.anios || [];
  return `<option value="">${placeholder}</option>` +
    years.map((y) => `<option value="${y}" ${String(y) === String(selected) ? "selected" : ""}>${y}</option>`).join("");
}

function cemOptions(selected) {
  return `<option value="">Todos los cementerios</option>` +
    (state.meta?.cementerios || []).map((c) =>
      `<option value="${esc(c.codigo)}" ${c.codigo === selected ? "selected" : ""}>${esc(c.nombre)}</option>`).join("");
}

function filtersHTML() {
  const f = state.filtros;
  return `
    <div class="filters">
      <label class="field"><span class="label">Desde</span><select data-f="desde">${yearOptions(f.desde, "Inicio")}</select></label>
      <label class="field"><span class="label">Hasta</span><select data-f="hasta">${yearOptions(f.hasta, "Fin")}</select></label>
      <label class="field"><span class="label">Cementerio</span><select data-f="cementerio">${cemOptions(f.cementerio)}</select></label>
    </div>`;
}

function bindFilters(root, onChange) {
  $$("[data-f]", root).forEach((el) =>
    el.addEventListener("change", () => {
      state.filtros[el.dataset.f] = el.value;
      onChange();
    }));
}

function pageHead(eyebrow, title, lead, right = "") {
  return `
    <div class="page-head">
      <div>
        <div class="eyebrow">${eyebrow}</div>
        <h1>${title}</h1>
        <p class="lead">${lead}</p>
      </div>
      ${right}
    </div>`;
}

function emptyState(msg) {
  return `<div class="card empty">${msg}<br><br><a class="btn" href="#/archivos">Ir a Archivos</a></div>`;
}

const hasData = (key) => state.meta?.datasets.some((d) => d.key === key && d.cargado);

/* ================= Vista: Resumen ================= */

function kpi(label, value, hint = "", small = false) {
  return `<div class="card kpi ${small ? "small" : ""}"><div class="label">${label}</div>
          <div class="value">${value}</div>${hint ? `<div class="hint">${hint}</div>` : ""}</div>`;
}

async function viewResumen(root) {
  root.innerHTML = `<div class="page">
    ${pageHead("Resumen", "Panorama general", "Indicadores clave de facturación, cremaciones y exhumaciones. Los filtros aplican a todas las cifras de esta página.", filtersHTML())}
    <div id="body"></div></div>`;
  bindFilters(root, () => renderResumen($("#body", root)));
  await renderResumen($("#body", root));
}

async function renderResumen(body) {
  if (!state.meta.datasets.some((d) => d.cargado)) {
    body.innerHTML = emptyState("Todavía no hay reportes cargados.");
    return;
  }
  body.classList.add("loading");
  const d = await api("resumen", state.filtros);
  body.classList.remove("loading");
  destroyCharts();
  const k = d.kpis;
  body.innerHTML = `
    <div class="kpis">
      ${kpi("Facturado neto", fmt.$(k.facturado), `${money.format(k.facturado || 0)}`)}
      ${kpi("Facturas emitidas", fmt.n(k.facturas), `Ticket promedio ${fmt.$(k.ticket)}`)}
      ${kpi("Cremaciones", fmt.n(k.cremaciones), `Edad promedio ${fmt.d(k.edad_cremaciones)} años`)}
      ${kpi("Exhumaciones", fmt.n(k.exhumaciones), `${fmt.pct(k.pct_exh_cremacion)} pasan a cremación`)}
    </div>
    <div class="kpis" style="margin-top:16px">
      ${kpi("Facturas anuladas", fmt.n(k.anuladas), `${fmt.pct(k.pct_anuladas)} del total · ${fmt.$(k.valor_anulado)}`, true)}
      ${kpi("Clientes únicos (NIT)", fmt.n(k.clientes), "Pagadores distintos en facturación", true)}
      ${kpi("Años sepultado", fmt.d(k.anios_sepultado), "Mediana entre inhumación y exhumación", true)}
      ${kpi("Edad promedio exhumados", fmt.d(k.edad_exhumaciones), "Al momento del fallecimiento", true)}
    </div>

    <div class="grid grid-2" style="margin-top:16px">
      <div class="card chart-card span-2">
        <header><h3>Actividad mensual</h3><span class="label">Número de registros por mes</span></header>
        <div class="chart-box tall"><canvas id="c-mensual"></canvas></div>
      </div>
      <div class="card chart-card">
        <header><h3>Facturación anual</h3><span class="label">Valor neto y número de facturas</span></header>
        <div class="chart-box"><canvas id="c-anual"></canvas></div>
      </div>
      <div class="card chart-card">
        <header><h3>Servicios por año</h3><span class="label">Cremaciones y exhumaciones</span></header>
        <div class="chart-box"><canvas id="c-servicios"></canvas></div>
      </div>
      <div class="card chart-card">
        <header><h3>Por cementerio</h3><span class="label">Participación de cada sede</span></header>
        <div class="chart-box"><canvas id="c-cem"></canvas></div>
      </div>
      <div class="card chart-card">
        <header><h3>Top 10 funerarias</h3><span class="label">Valor facturado</span></header>
        <div class="chart-box"><canvas id="c-fun"></canvas></div>
      </div>
    </div>`;

  // Actividad mensual: unión de meses de las tres fuentes
  const m = d.mensual;
  const meses = [...new Set(Object.values(m).flat().map((r) => r.mes))].sort();
  const serie = (rows) => {
    const idx = Object.fromEntries((rows || []).map((r) => [r.mes, r.n]));
    return meses.map((x) => idx[x] ?? 0);
  };
  const lineDs = (label, data, color) => ({ label, data, borderColor: color, backgroundColor: color, borderWidth: 1.6, pointRadius: 0, tension: 0.25 });
  makeChart($("#c-mensual"), {
    type: "line",
    data: {
      labels: meses,
      datasets: [
        m.facturas && lineDs("Facturas", serie(m.facturas), PALETTE[0]),
        m.cremaciones && lineDs("Cremaciones", serie(m.cremaciones), PALETTE[1]),
        m.exhumaciones && lineDs("Exhumaciones", serie(m.exhumaciones), PALETTE[2]),
      ].filter(Boolean),
    },
    options: {
      interaction: { mode: "index", intersect: false },
      plugins: { legend: { position: "top", align: "end" } },
      scales: { x: { grid: { display: false }, ticks: { maxTicksLimit: 18 } }, y: { beginAtZero: true, grid: { color: "#efebe2" } } },
    },
  });

  const fa = d.anual.facturas || [];
  makeChart($("#c-anual"), {
    data: {
      labels: fa.map((r) => r.anio),
      datasets: [
        { type: "bar", label: "Valor neto", data: fa.map((r) => r.valor), backgroundColor: PALETTE[0], borderRadius: 4, yAxisID: "y" },
        { type: "line", label: "Facturas", data: fa.map((r) => r.n), borderColor: PALETTE[1], backgroundColor: PALETTE[1], pointRadius: 2, tension: 0.3, yAxisID: "y1" },
      ],
    },
    options: {
      interaction: { mode: "index", intersect: false },
      plugins: {
        legend: { position: "top", align: "end" },
        tooltip: { callbacks: { label: (c) => ` ${c.dataset.label}: ${c.dataset.yAxisID === "y" ? money.format(c.raw) : fmt.n(c.raw)}` } },
      },
      scales: {
        x: { grid: { display: false } },
        y: { beginAtZero: true, ticks: { callback: compactMoney }, grid: { color: "#efebe2" } },
        y1: { beginAtZero: true, position: "right", grid: { display: false }, ticks: { callback: fmt.n } },
      },
    },
  });

  const years = [...new Set([...(d.anual.cremaciones || []), ...(d.anual.exhumaciones || [])].map((r) => r.anio))].sort();
  const byYear = (rows) => years.map((y) => (rows || []).find((r) => r.anio === y)?.n ?? 0);
  makeChart($("#c-servicios"), {
    type: "bar",
    data: {
      labels: years,
      datasets: [
        { label: "Cremaciones", data: byYear(d.anual.cremaciones), backgroundColor: PALETTE[1], borderRadius: 3 },
        { label: "Exhumaciones", data: byYear(d.anual.exhumaciones), backgroundColor: PALETTE[2], borderRadius: 3 },
      ],
    },
    options: {
      interaction: { mode: "index", intersect: false },
      plugins: { legend: { position: "top", align: "end" } },
      scales: { x: { grid: { display: false } }, y: { grid: { color: "#efebe2" }, ticks: { callback: fmt.n } } },
    },
  });

  const c = d.cementerios;
  const cems = [...new Set(Object.values(c).flat().map((r) => r.nombre))]
    .filter((n) => n !== "Sin dato" && n !== "Otro código").sort();
  const share = (rows) => {
    const total = (rows || []).filter((r) => cems.includes(r.nombre)).reduce((a, r) => a + (r.v || 0), 0) || 1;
    return cems.map((n) => (((rows || []).find((r) => r.nombre === n)?.v || 0) / total) * 100);
  };
  makeChart($("#c-cem"), {
    type: "bar",
    data: {
      labels: ["Facturado", "Cremaciones", "Exhumaciones"],
      datasets: cems.map((n, i) => ({
        label: n,
        data: [share(c.facturado)[i], share(c.cremaciones)[i], share(c.exhumaciones)[i]],
        backgroundColor: PALETTE[i % PALETTE.length],
      })),
    },
    options: {
      indexAxis: "y",
      plugins: { legend: { position: "top", align: "end" }, tooltip: { callbacks: { label: (x) => ` ${x.dataset.label}: ${nf1.format(x.raw)} %` } } },
      scales: { x: { stacked: true, max: 100, ticks: { callback: (v) => v + " %" }, grid: { color: "#efebe2" } }, y: { stacked: true, grid: { display: false } } },
    },
  });

  renderSimple($("#c-fun"), {
    tipo: "hbar", formato: "$",
    labels: d.funerarias.map((r) => r.nombre), values: d.funerarias.map((r) => r.valor),
  });
}

/* ================= Vista: Archivos ================= */

async function viewArchivos(root) {
  root.innerHTML = `<div class="page">
    ${pageHead("Archivos", "Carga de datos", "Sube la hoja de Excel (.xlsx) de cada reporte exportado de KNIME. El panel reconoce el tipo de archivo por sus encabezados, lo procesa en el servidor local y lo deja listo para consultar, filtrar y comparar.")}
    <div class="card dropzone" id="drop">
      <div class="icon">${icon("doc")}</div>
      <h2>Arrastra tus hojas de Excel aquí</h2>
      <p>.xlsx o .csv. Puedes soltar varios a la vez. Los archivos se procesan en este equipo con DuckDB; los reportes grandes (más de 100 MB) pueden tardar alrededor de un minuto.</p>
      <label class="btn">Elegir archivos<input type="file" id="file" accept=".xlsx,.csv" multiple hidden /></label>
    </div>
    <div id="results"></div>
    <div class="label section-title">Reportes que reconoce el panel</div>
    <div class="grid grid-3" id="reports"></div>
  </div>`;
  renderReports();

  const drop = $("#drop");
  ["dragenter", "dragover"].forEach((e) => drop.addEventListener(e, (ev) => { ev.preventDefault(); drop.classList.add("over"); }));
  ["dragleave", "drop"].forEach((e) => drop.addEventListener(e, (ev) => { ev.preventDefault(); drop.classList.remove("over"); }));
  drop.addEventListener("drop", (ev) => upload([...ev.dataTransfer.files]));
  $("#file").addEventListener("change", (ev) => upload([...ev.target.files]));
}

function renderReports() {
  $("#reports").innerHTML = state.meta.datasets.map((d) => `
    <div class="card report">
      <div style="display:flex;justify-content:space-between;align-items:center">
        <span class="label">${esc(d.titulo)}</span>
        ${d.cargado ? '<span class="pill good">Cargado</span>' : '<span class="pill bad">Pendiente</span>'}
      </div>
      <p>${esc(d.descripcion)}</p>
      <div class="meta">
        ${d.fecha ? `Fecha: ${esc(d.fecha)}` : "Sin campo de fecha"}<br>
        ${d.cargado ? `${nf.format(d.filas || 0)} filas · ${esc(d.archivo || "")}<br>` : ""}
        ${d.desde ? `Rango válido: ${d.desde} → ${d.hasta}<br>` : ""}
        ${d.actualizado ? `Actualizado: ${esc(d.actualizado)}` : ""}
      </div>
    </div>`).join("");
}

async function upload(files) {
  if (!files.length) return;
  const results = $("#results");
  results.innerHTML = files.map((f) => `
    <div class="card result"><div class="spinner"></div>
      <div><strong>${esc(f.name)}</strong><div class="msg">Subiendo y procesando ${nf1.format(f.size / 1048576)} MB…</div></div>
      <span class="status">Procesando</span></div>`).join("");
  const form = new FormData();
  files.forEach((f) => form.append("archivos", f));
  try {
    const res = await fetch("/api/cargar", { method: "POST", body: form });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || res.statusText);
    results.innerHTML = data.resultados.map((r) => `
      <div class="card result ${r.ok ? "ok" : "err"}">
        <span style="width:18px;color:${r.ok ? "var(--ok)" : "var(--danger)"}">${icon(r.ok ? "check" : "alert")}</span>
        <div><strong>${esc(r.archivo)}</strong><div class="msg">${esc(r.mensaje)}</div></div>
        <span class="status">${r.ok ? "Reconocido" : "No reconocido"}</span>
      </div>`).join("");
  } catch (err) {
    results.innerHTML = `<div class="card result err"><div><strong>Error</strong><div class="msg">${esc(err.message)}</div></div></div>`;
  }
  await loadMeta();
  renderReports();
}

/* ================= Vista: Tablas ================= */

const TABLE_INFO = {
  facturas: ["Tablas", "Facturas", "Detalle de la facturación. Busca por número de factura, pagador, NIT, fallecido o cédula."],
  cremaciones: ["Tablas", "Cremaciones", "Certificados de cremación. Busca por factura, certificado, licencia, nombre o cédula."],
  exhumaciones: ["Tablas", "Exhumaciones", "Exhumaciones con su inhumación de origen. Busca por factura, licencia, nombre, reclamante o deudor."],
  funerarias: ["Tablas", "Funerarias", "Maestro de funerarias cruzado con la facturación neta y las cremaciones atendidas."],
};

const COL_LABELS = {
  recibido_d: "Recibido de", forma_pago_nombre: "Forma de pago", funeraria_nombre: "Funeraria", cementerio_nombre: "Cementerio",
  es_anulada: "Estado", fecha_cre: "Fecha cremación", certificad: "Certificado", tipo_crema_nombre: "Tipo", sexo_nombre: "Sexo",
  edad_valida: "Edad", destino_nombre: "Destino", con_urna: "Urna", factura_ex: "Factura", fecha_exh: "Fecha exhumación",
  fecha_inh: "Fecha inhumación", lugar_no: "Lugar", anios_sepultado: "Años sepultado", valor_facturado: "Valor facturado",
};

const NUMERIC = new Set(["valor", "edad_valida", "anios_sepultado", "facturas", "valor_facturado", "cremaciones"]);

function cell(col, v) {
  if (v == null || v === "") return '<span style="color:var(--faint)">—</span>';
  if (col === "es_anulada") return v ? '<span class="pill bad">Anulada</span>' : '<span class="pill good">Vigente</span>';
  if (col === "con_urna") return v ? "Sí" : "No";
  if (col === "valor" || col === "valor_facturado") return money.format(v);
  if (col === "anios_sepultado" || col === "edad_valida") return nf1.format(v);
  if (typeof v === "number") return nf.format(v);
  return esc(v);
}

async function viewTabla(root, dataset) {
  const [eyebrow, title, lead] = TABLE_INFO[dataset];
  const t = { buscar: "", orden: "", dir: "desc", pagina: 1, tamano: 50 };
  const withDates = dataset !== "funerarias";
  root.innerHTML = `<div class="page">
    ${pageHead(eyebrow, title, lead)}
    ${hasData(dataset) ? `
    <div class="filters" style="margin-bottom:16px">
      <label class="field"><span class="label">Buscar</span><input type="search" id="q" placeholder="Escribe y presiona Enter…" /></label>
      ${withDates ? filtersHTML().replace('<div class="filters">', "").replace(/<\/div>\s*$/, "") : ""}
      <a class="btn" id="csv" style="margin-left:auto">${icon("download").replace("<svg", '<svg width="15" height="15"')}Exportar CSV</a>
    </div>
    <div class="card"><div class="table-wrap" id="tbl"></div><div class="table-foot" id="foot"></div></div>` : emptyState("Este reporte aún no está cargado.")}
  </div>`;
  if (!hasData(dataset)) return;

  const load = async () => {
    const params = { ...t, ...(withDates ? state.filtros : {}) };
    $("#tbl").classList.add("loading");
    let d;
    try {
      d = await api(`tabla/${dataset}`, params);
    } catch (e) {
      $("#tbl").innerHTML = `<div class="empty">${esc(e.message)}</div>`;
      return;
    }
    $("#tbl").classList.remove("loading");
    const qs = new URLSearchParams(Object.entries(params).filter(([k, v]) => v !== "" && !["pagina", "tamano"].includes(k)));
    $("#csv").href = `/api/tabla/${dataset}/csv?${qs}`;
    $("#tbl").innerHTML = `<table><thead><tr>${d.columnas.map((c) => `
        <th data-col="${c}" class="${NUMERIC.has(c) ? "num" : ""} ${t.orden === c ? "sorted" : ""}">
          ${esc(COL_LABELS[c] || c.replace(/_/g, " "))}${t.orden === c ? (t.dir === "asc" ? " ↑" : " ↓") : ""}</th>`).join("")}
      </tr></thead><tbody>${d.filas.map((r) => `<tr>${d.columnas.map((c) =>
        `<td class="${NUMERIC.has(c) ? "num" : ""}">${cell(c, r[c])}</td>`).join("")}</tr>`).join("") ||
        `<tr><td colspan="${d.columnas.length}" class="empty">Sin resultados</td></tr>`}</tbody></table>`;
    const pages = Math.max(1, Math.ceil(d.total / t.tamano));
    $("#foot").innerHTML = `<span>${nf.format(d.total)} registros</span>
      <div class="pager"><button class="btn" id="prev" ${t.pagina <= 1 ? "disabled" : ""}>Anterior</button>
      <span>Página ${nf.format(t.pagina)} de ${nf.format(pages)}</span>
      <button class="btn" id="next" ${t.pagina >= pages ? "disabled" : ""}>Siguiente</button></div>`;
    $$("th[data-col]").forEach((th) => th.addEventListener("click", () => {
      const col = th.dataset.col;
      t.dir = t.orden === col && t.dir === "desc" ? "asc" : "desc";
      t.orden = col;
      t.pagina = 1;
      load();
    }));
    $("#prev").onclick = () => { t.pagina--; load(); };
    $("#next").onclick = () => { t.pagina++; load(); };
  };

  $("#q").addEventListener("keydown", (e) => {
    if (e.key === "Enter") { t.buscar = e.target.value; t.pagina = 1; load(); }
  });
  $("#q").addEventListener("search", (e) => { t.buscar = e.target.value; t.pagina = 1; load(); });
  bindFilters(root, () => { t.pagina = 1; load(); });
  await load();
}

/* ================= Vista: Estadísticas ================= */

const DS_LABEL = { facturas: "Facturas", cremaciones: "Cremaciones", exhumaciones: "Exhumaciones" };

async function viewEstadisticas(root) {
  const tabs = Object.keys(DS_LABEL).filter(hasData);
  if (!tabs.includes(state.estDataset)) state.estDataset = tabs[0];
  root.innerHTML = `<div class="page">
    ${pageHead("Análisis", "Estadísticas", "Distribuciones y patrones de cada reporte: composición, perfiles de edad y sexo, estacionalidad y principales funerarias.", filtersHTML())}
    ${tabs.length ? `<div class="tabs" id="tabs">${tabs.map((k) =>
      `<button data-k="${k}" class="${k === state.estDataset ? "active" : ""}">${DS_LABEL[k]}</button>`).join("")}</div>
    <div class="grid grid-2" id="charts" style="margin-top:18px"></div>` : emptyState("No hay reportes cargados.")}
  </div>`;
  if (!tabs.length) return;

  const render = async () => {
    const box = $("#charts");
    box.classList.add("loading");
    const d = await api(`estadisticas/${state.estDataset}`, state.filtros);
    box.classList.remove("loading");
    destroyCharts();
    box.innerHTML = d.charts.map((c) => `
      <div class="card chart-card">
        <header><h3>${esc(c.titulo)}</h3></header>
        <div class="chart-box"><canvas id="st-${c.id}"></canvas></div>
        ${c.nota ? `<p class="note">${esc(c.nota)}</p>` : ""}
      </div>`).join("");
    d.charts.forEach((c) => renderSimple($(`#st-${c.id}`), c));
  };

  $$("#tabs button").forEach((b) => b.addEventListener("click", () => {
    state.estDataset = b.dataset.k;
    $$("#tabs button").forEach((x) => x.classList.toggle("active", x === b));
    render();
  }));
  bindFilters(root, render);
  await render();
}

/* ================= Vista: Comparaciones ================= */

const METRICAS = {
  facturas: { valor: "Valor facturado", n: "Número de facturas" },
  cremaciones: { n: "Número de cremaciones" },
  exhumaciones: { n: "Número de exhumaciones" },
};

async function viewComparaciones(root) {
  const c = state.comp;
  const years = state.meta.anios;
  const datasets = Object.keys(METRICAS).filter(hasData);
  if (!datasets.includes(c.dataset)) c.dataset = datasets[0];
  if (!c.b) c.b = years[years.length - 2] ?? years[years.length - 1];
  if (!c.a) c.a = years[years.length - 3] ?? years[0];

  root.innerHTML = `<div class="page">
    ${pageHead("Análisis", "Comparaciones", "Contrasta dos años mes a mes, mira cómo cambia la participación de cada cementerio y sigue la tendencia histórica.")}
    ${datasets.length ? `
    <div class="filters" id="cf" style="margin-bottom:20px">
      <label class="field"><span class="label">Reporte</span><select data-c="dataset">${datasets.map((k) =>
        `<option value="${k}" ${k === c.dataset ? "selected" : ""}>${DS_LABEL[k]}</option>`).join("")}</select></label>
      <label class="field"><span class="label">Métrica</span><select data-c="metrica"></select></label>
      <label class="field"><span class="label">Año base</span><select data-c="a">${yearOptions(c.a, "Año")}</select></label>
      <label class="field"><span class="label">Año a comparar</span><select data-c="b">${yearOptions(c.b, "Año")}</select></label>
      <label class="field"><span class="label">Cementerio</span><select data-c="cementerio">${cemOptions(c.cementerio)}</select></label>
    </div>
    <div class="kpis" id="ck" style="grid-template-columns:repeat(3,minmax(0,1fr))"></div>
    <div class="grid grid-2" style="margin-top:16px">
      <div class="card chart-card span-2"><header><h3>Mes a mes</h3><span class="label" id="cm-label"></span></header>
        <div class="chart-box tall"><canvas id="cm"></canvas></div></div>
      <div class="card chart-card"><header><h3>Por cementerio</h3><span class="label">Ambos años</span></header>
        <div class="chart-box"><canvas id="cc"></canvas></div></div>
      <div class="card chart-card"><header><h3>Tendencia histórica</h3><span class="label">Apilado por cementerio</span></header>
        <div class="chart-box"><canvas id="ct"></canvas></div></div>
    </div>` : emptyState("No hay reportes cargados.")}
  </div>`;
  if (!datasets.length) return;

  const syncMetric = () => {
    const opts = METRICAS[c.dataset];
    if (!opts[c.metrica]) c.metrica = Object.keys(opts)[0];
    $('[data-c="metrica"]').innerHTML = Object.entries(opts).map(([k, v]) =>
      `<option value="${k}" ${k === c.metrica ? "selected" : ""}>${v}</option>`).join("");
  };
  syncMetric();

  const render = async () => {
    if (!c.a || !c.b) return;
    const f = c.metrica === "valor" ? "$" : "n";
    const [d, t] = await Promise.all([api("comparar", c), api("tendencia", { dataset: c.dataset, metrica: c.metrica })]);
    destroyCharts();
    const v = d.variacion;
    $("#ck").innerHTML =
      kpi(`Total ${c.a}`, fmt[f](d.totales[c.a]), METRICAS[c.dataset][c.metrica]) +
      kpi(`Total ${c.b}`, fmt[f](d.totales[c.b]), METRICAS[c.dataset][c.metrica]) +
      kpi("Variación", v == null ? "—" : `<span class="${v >= 0 ? "delta-up" : "delta-down"}">${v >= 0 ? "+" : ""}${nf1.format(v)} %</span>`,
        `${c.b} frente a ${c.a}`);
    $("#cm-label").textContent = METRICAS[c.dataset][c.metrica];
    const tip = { callbacks: { label: (x) => ` ${x.dataset.label}: ${f === "$" ? money.format(x.raw) : fmt.n(x.raw)}` } };
    makeChart($("#cm"), {
      type: "line",
      data: {
        labels: d.meses,
        datasets: [String(c.a), String(c.b)].map((y, i) => ({
          label: y, data: d.series[y], borderColor: PALETTE[i ? 1 : 0], backgroundColor: PALETTE[i ? 1 : 0],
          borderWidth: 2, tension: 0.3, pointRadius: 3,
        })),
      },
      options: {
        interaction: { mode: "index", intersect: false },
        plugins: { legend: { position: "top", align: "end" }, tooltip: tip },
        scales: { x: { grid: { display: false } }, y: { beginAtZero: true, ticks: { callback: axisFormatter(f) }, grid: { color: "#efebe2" } } },
      },
    });
    makeChart($("#cc"), {
      type: "bar",
      data: {
        labels: d.cementerios.labels,
        datasets: [String(c.a), String(c.b)].map((y, i) => ({
          label: y, data: d.cementerios.series[y], backgroundColor: PALETTE[i ? 1 : 0], borderRadius: 4, maxBarThickness: 34,
        })),
      },
      options: {
        plugins: { legend: { position: "top", align: "end" }, tooltip: tip },
        scales: { x: { grid: { display: false } }, y: { ticks: { callback: axisFormatter(f) }, grid: { color: "#efebe2" } } },
      },
    });
    makeChart($("#ct"), {
      type: "bar",
      data: {
        labels: t.labels,
        datasets: Object.entries(t.series).map(([name, data], i) => ({ label: name, data, backgroundColor: PALETTE[i % PALETTE.length] })),
      },
      options: {
        interaction: { mode: "index", intersect: false },
        plugins: { legend: { position: "top", align: "end" }, tooltip: tip },
        scales: { x: { stacked: true, grid: { display: false } }, y: { stacked: true, ticks: { callback: axisFormatter(f) }, grid: { color: "#efebe2" } } },
      },
    });
  };

  $$("[data-c]").forEach((el) => el.addEventListener("change", () => {
    c[el.dataset.c] = el.value;
    if (el.dataset.c === "dataset") syncMetric();
    render();
  }));
  await render();
}

/* ================= Router ================= */

async function route() {
  const hash = location.hash.replace(/^#\/?/, "") || "resumen";
  $$("nav a").forEach((a) => a.classList.toggle("active", a.dataset.route === hash));
  destroyCharts();
  const root = $("#view");
  try {
    if (!state.meta) await loadMeta();
    if (hash === "resumen") await viewResumen(root);
    else if (hash === "archivos") await viewArchivos(root);
    else if (hash.startsWith("tabla/") && TABLE_INFO[hash.slice(6)]) await viewTabla(root, hash.slice(6));
    else if (hash === "estadisticas") await viewEstadisticas(root);
    else if (hash === "comparaciones") await viewComparaciones(root);
    else location.hash = "#/resumen";
  } catch (err) {
    root.innerHTML = `<div class="page"><div class="card empty">No se pudo cargar la vista: ${esc(err.message)}</div></div>`;
  }
}

$$("[data-icon]").forEach((el) => (el.innerHTML = icon(el.dataset.icon)));
window.addEventListener("hashchange", route);
route();
