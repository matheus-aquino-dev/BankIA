/* app.js — BankIQ Upload-Driven Frontend */

let KPIs    = {};
let TABELAS = {};
const agentResults = {};
let charts = {};

// ─────────────────────────────────────────────────────────────────────────────
// UPLOAD & DRAG-DROP
// ─────────────────────────────────────────────────────────────────────────────
const dropArea  = document.getElementById("drop-area");
const fileInput = document.getElementById("file-input");

dropArea.addEventListener("click",      () => fileInput.click());
dropArea.addEventListener("dragover",   e => { e.preventDefault(); dropArea.classList.add("drag-over"); });
dropArea.addEventListener("dragleave",  () => dropArea.classList.remove("drag-over"));
dropArea.addEventListener("drop", e => {
  e.preventDefault();
  dropArea.classList.remove("drag-over");
  const file = e.dataTransfer.files[0];
  if (file) handleFile(file);
});
fileInput.addEventListener("change", e => {
  if (e.target.files[0]) handleFile(e.target.files[0]);
});

// ─────────────────────────────────────────────────────────────────────────────
// STEPS DE PROCESSAMENTO (animação)
// ─────────────────────────────────────────────────────────────────────────────
const STEPS = [
  { label: "Lendo arquivo Excel",             icon: "📂" },
  { label: "Identificando abas",              icon: "🔍" },
  { label: "Tipando clientes",                icon: "👥" },
  { label: "Processando transações",          icon: "💳" },
  { label: "Analisando empréstimos",          icon: "💰" },
  { label: "Calculando inadimplência",        icon: "🚨" },
  { label: "Computando KPIs",                 icon: "📊" },
  { label: "Construindo contextos dos agentes", icon: "🤖" },
  { label: "Pronto!",                         icon: "✅" },
];

function showProgress(filename) {
  document.getElementById("prog-filename").textContent = "📄 " + filename;
  document.getElementById("prog-steps").innerHTML =
    STEPS.map((s, i) => `<div class="prog-step" id="step-${i}"><span class="step-icon">${s.icon}</span>${s.label}</div>`).join("");
  document.getElementById("prog-bar").style.width = "0%";
  document.getElementById("prog-status").textContent = "Iniciando...";
  document.getElementById("progress-overlay").style.display = "flex";
}

async function animateSteps(totalMs) {
  const stepDelay = totalMs / STEPS.length;
  for (let i = 0; i < STEPS.length; i++) {
    if (i > 0) document.getElementById(`step-${i-1}`).classList.replace("active","done");
    document.getElementById(`step-${i}`).classList.add("active");
    document.getElementById("prog-bar").style.width = `${Math.round((i+1)/STEPS.length*100)}%`;
    document.getElementById("prog-status").textContent = STEPS[i].label + "...";
    await delay(stepDelay);
  }
}

function delay(ms) { return new Promise(r => setTimeout(r, ms)); }

// ─────────────────────────────────────────────────────────────────────────────
// HANDLE FILE
// ─────────────────────────────────────────────────────────────────────────────
async function handleFile(file) {
  showProgress(file.name);

  const formData = new FormData();
  formData.append("file", file);

  // Roda animação e upload em paralelo
  const [_, response] = await Promise.all([
    animateSteps(1800),
    fetch("/api/upload", { method: "POST", body: formData }),
  ]);

  const data = await response.json();

  if (data.error) {
    document.getElementById("progress-overlay").style.display = "none";
    alert("❌ Erro: " + data.error);
    return;
  }

  // Pequena pausa no "Pronto!" antes de revelar o dashboard
  await delay(600);
  document.getElementById("progress-overlay").style.display = "none";

  KPIs    = data.kpis;
  TABELAS = data.rows;

  renderDashboard(file.name, data.abas);
}

// ─────────────────────────────────────────────────────────────────────────────
// RENDER DASHBOARD
// ─────────────────────────────────────────────────────────────────────────────
function renderDashboard(filename, abas) {
  // Troca telas
  document.getElementById("upload-screen").style.display    = "none";
  document.getElementById("dashboard-screen").style.display = "block";

  // Header info
  document.getElementById("source-filename").textContent = "📄 " + filename;
  document.getElementById("abas-pills").innerHTML =
    abas.map(a => `<span class="aba-pill">✓ ${a}</span>`).join("");

  renderKPIs();
  renderCharts();
  renderModalidadeTable();
  renderDataTables();
  renderAgentContexts();
  renderGerenteCtx();
}

function resetSystem() {
  fetch("/api/reset", { method: "POST" });
  Object.values(charts).forEach(c => c.destroy());
  charts = {};
  Object.keys(agentResults).forEach(k => delete agentResults[k]);
  document.getElementById("dashboard-screen").style.display = "none";
  document.getElementById("upload-screen").style.display    = "flex";
  fileInput.value = "";
}

// ─────────────────────────────────────────────────────────────────────────────
// TABS
// ─────────────────────────────────────────────────────────────────────────────
function showTab(name, btn) {
  document.querySelectorAll(".tab").forEach(t => t.classList.remove("active"));
  document.querySelectorAll(".nav-btn").forEach(b => b.classList.remove("active"));
  document.getElementById(`tab-${name}`).classList.add("active");
  btn.classList.add("active");
}

// ─────────────────────────────────────────────────────────────────────────────
// KPIs
// ─────────────────────────────────────────────────────────────────────────────
function br(v) {
  return "R$ " + Number(v).toLocaleString("pt-BR", { minimumFractionDigits: 2 });
}

function renderKPIs() {
  const items = [
    { label: "Total de Clientes",       value: KPIs.total_clientes,       sub: "Fonte: clientes",              cls: "kpi-neu" },
    { label: "Score Médio de Crédito",  value: KPIs.score_medio + " pts", sub: "Meta: ≥ 700",                  cls: KPIs.score_medio >= 700 ? "kpi-up" : "kpi-down" },
    { label: "Carteira Total",          value: br(KPIs.carteira_total),   sub: "saldo devedor",                cls: "kpi-neu" },
    { label: "Taxa de Inadimplência",   value: KPIs.taxa_inad_pct + "%",  sub: "Meta: ≤ 3,5%",                 cls: KPIs.taxa_inad_pct > 3.5 ? "kpi-down" : "kpi-up" },
    { label: "Fraudes Detectadas",      value: KPIs.n_fraudes,            sub: KPIs.n_revisar + " p/ revisar", cls: KPIs.n_fraudes > 0 ? "kpi-down" : "kpi-up" },
    { label: "Transações Analisadas",   value: KPIs.total_trans,          sub: br(KPIs.volume_total) + " total", cls: "kpi-neu" },
    { label: "Valor em Aberto (inad.)", value: br(KPIs.valor_inad),       sub: KPIs.total_inad + " casos",     cls: "kpi-down" },
    { label: "Taxa Média de Juros",     value: KPIs.taxa_media + "%/mês", sub: "Fonte: emprestimos",           cls: "kpi-neu" },
  ];
  document.getElementById("kpi-grid").innerHTML = items.map((item, i) => `
    <div class="kpi-card" style="animation-delay:${i*60}ms">
      <div class="kpi-label">${item.label}</div>
      <div class="kpi-value">${item.value}</div>
      <div class="kpi-sub ${item.cls}">${item.sub}</div>
    </div>`).join("");
}

// ─────────────────────────────────────────────────────────────────────────────
// CHARTS
// ─────────────────────────────────────────────────────────────────────────────
function renderCharts() {
  const mod = KPIs.por_modalidade || [];
  makeBar("chartModalidade", mod.map(m => m.modalidade), mod.map(m => m.saldo),
    ["#3b82f6","#22c55e","#f59e0b","#a78bfa"], v => "R$" + (v/1000).toFixed(0) + "k");

  const pf = KPIs.por_perfil || {};
  makeDoughnut("chartPerfil", Object.keys(pf), Object.values(pf), ["#3b82f6","#f59e0b","#ef4444"]);

  const fl = KPIs.por_flag || {};
  makeBar("chartFlags", Object.keys(fl), Object.values(fl), ["#22c55e","#f59e0b","#ef4444"]);

  const ri = KPIs.por_risco || {};
  makeDoughnut("chartRisco", Object.keys(ri), Object.values(ri), ["#ef4444","#f59e0b","#3b82f6"]);
}

function makeBar(id, labels, data, colors, tickFmt) {
  const ctx = document.getElementById(id);
  if (!ctx) return;
  if (charts[id]) charts[id].destroy();
  charts[id] = new Chart(ctx, {
    type: "bar",
    data: { labels, datasets: [{ data, backgroundColor: colors, borderRadius: 4, borderSkipped: false }] },
    options: {
      responsive: true, maintainAspectRatio: false,
      plugins: { legend: { display: false } },
      scales: {
        y: { ticks: { callback: tickFmt || (v => v), font: { size: 10 } } },
        x: { ticks: { font: { size: 10 } } },
      }
    }
  });
}

function makeDoughnut(id, labels, data, colors) {
  const ctx = document.getElementById(id);
  if (!ctx) return;
  if (charts[id]) charts[id].destroy();
  charts[id] = new Chart(ctx, {
    type: "doughnut",
    data: { labels: labels.map((l,i) => `${l} (${data[i]})`), datasets: [{ data, backgroundColor: colors, borderWidth: 0 }] },
    options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { position: "bottom", labels: { font: { size: 10 }, padding: 10 } } } }
  });
}

// ─────────────────────────────────────────────────────────────────────────────
// TABELA MODALIDADE
// ─────────────────────────────────────────────────────────────────────────────
function renderModalidadeTable() {
  document.querySelector("#tbl-modalidade tbody").innerHTML =
    (KPIs.por_modalidade || []).map(m => `
      <tr>
        <td><strong>${m.modalidade}</strong></td>
        <td>${m.qtd}</td>
        <td>${br(m.saldo)}</td>
        <td>${m.taxa_media.toFixed(2)}%/mês</td>
      </tr>`).join("");
}

// ─────────────────────────────────────────────────────────────────────────────
// TABELAS DE DADOS (geradas dinamicamente)
// ─────────────────────────────────────────────────────────────────────────────
const BADGE_MAP = {
  "Ativo":"badge-green","Inadimplente":"badge-red","Alerta":"badge-amber",
  "Em dia":"badge-green","Atraso":"badge-amber",
  "Normal":"badge-green","Fraude":"badge-red","Revisar":"badge-amber",
  "Alto":"badge-red","Médio":"badge-amber","Baixo":"badge-blue",
  "Moderado":"badge-amber","Arrojado":"badge-red","Conservador":"badge-blue",
};
const BADGE_COLS  = ["status","flag","risco","perfil"];
const MONEY_COLS  = ["valor","valor_principal","saldo_devedor","valor_em_aberto","renda_mensal","ticket_medio"];

function cellVal(col, val) {
  if (val === null || val === undefined || val === "") return "—";
  if (BADGE_COLS.includes(col) && BADGE_MAP[val])
    return `<span class="badge ${BADGE_MAP[val]}">${val}</span>`;
  if (col === "pais" && val !== "BR")
    return `<span class="badge badge-red">${val}</span>`;
  if (MONEY_COLS.includes(col) && !isNaN(val))
    return br(val);
  return val;
}

const TABLE_META = {
  clientes:      { icon:"👥", badge:"badge-green"  },
  transacoes:    { icon:"💳", badge:"badge-amber"  },
  emprestimos:   { icon:"💰", badge:"badge-purple" },
  inadimplencia: { icon:"🚨", badge:"badge-red"    },
};

function renderDataTables() {
  const grid = document.getElementById("tables-grid");
  grid.innerHTML = "";
  for (const [name, rows] of Object.entries(TABELAS)) {
    if (!rows || rows.length === 0) continue;
    const meta = TABLE_META[name] || { icon:"📋", badge:"badge-blue" };
    const cols  = Object.keys(rows[0]);
    const card  = document.createElement("div");
    card.className = "table-card";
    card.innerHTML = `
      <h3>${meta.icon} ${name} <span class="badge ${meta.badge}">${rows.length} registros</span></h3>
      <div class="tbl-scroll">
        <table>
          <thead><tr>${cols.map(c => `<th>${c}</th>`).join("")}</tr></thead>
          <tbody>${rows.map(row =>
            `<tr>${cols.map(c => `<td>${cellVal(c, row[c])}</td>`).join("")}</tr>`
          ).join("")}</tbody>
        </table>
      </div>`;
    grid.appendChild(card);
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// CONTEXTOS DOS AGENTES
// ─────────────────────────────────────────────────────────────────────────────
function renderAgentContexts() {
  const p = KPIs;
  document.getElementById("ctx-credito").textContent =
    `Fonte: emprestimos + inadimplencia\n` +
    `• ${p.total_contratos} contratos | Carteira: ${br(p.carteira_total)}\n` +
    `• Score médio: ${p.score_medio} pts (meta 700+)\n` +
    `• Inadimplência: ${p.taxa_inad_pct}% | ${p.total_inad} casos | ${br(p.valor_inad)} em aberto\n` +
    `• Alto risco: ${(p.por_risco||{}).Alto||0} casos`;

  document.getElementById("ctx-fraude").textContent =
    `Fonte: transacoes\n` +
    `• ${p.total_trans} transações | Volume: ${br(p.volume_total)}\n` +
    `• Ticket médio: ${br(p.ticket_medio)}\n` +
    `• Fraudes: ${p.n_fraudes} | Revisar: ${p.n_revisar}\n` +
    `• Transações internacionais: ${p.n_inter}`;

  document.getElementById("ctx-invest").textContent =
    `Fonte: clientes\n` +
    `• ${p.total_clientes} clientes | Renda média: ${br(p.renda_media)}/mês\n` +
    `• Conservador: ${(p.por_perfil||{}).Conservador||0}\n` +
    `• Moderado: ${(p.por_perfil||{}).Moderado||0}\n` +
    `• Arrojado: ${(p.por_perfil||{}).Arrojado||0}`;
}

function renderGerenteCtx() {
  const p = KPIs;
  document.getElementById("gerente-ctx-summary").innerHTML =
    `<strong style="color:#c8ddf8">Dados consolidados do Excel (processados em Python):</strong><br>` +
    `${p.total_clientes} clientes · Carteira ${br(p.carteira_total)} · ` +
    `Inadimplência ${p.taxa_inad_pct}% · ${p.total_inad} casos (${br(p.valor_inad)} em aberto) · ` +
    `${p.n_fraudes} fraudes + ${p.n_revisar} p/ revisar · Score médio ${p.score_medio}`;
}

// ─────────────────────────────────────────────────────────────────────────────
// AGENTES IA
// ─────────────────────────────────────────────────────────────────────────────
async function runAgent(nome) {
  const btn = document.getElementById(`btn-${nome}`);
  const out = document.getElementById(`out-${nome}`);
  btn.disabled = true;
  btn.innerHTML = `<span class="spinner"></span> Consultando IA...`;
  out.className = "agent-out loading";
  out.textContent = "Python processou o Excel. Enviando contexto à IA...";
  try {
    const res  = await fetch(`/api/agente/${nome}`, { method: "POST" });
    const data = await res.json();
    out.className = "agent-out";
    out.textContent = data.resultado || data.error;
    agentResults[nome] = data.resultado || "";
  } catch (e) {
    out.className = "agent-out";
    out.textContent = "Erro ao conectar com o servidor Flask.";
  }
  btn.disabled = false;
  btn.innerHTML = "✅ Analisado";
}

async function runGerente() {
  const btn = document.getElementById("btn-gerente");
  const out = document.getElementById("out-gerente");
  btn.disabled = true;
  btn.innerHTML = `<span class="spinner"></span> Consolidando...`;
  out.textContent = "Gerente processando relatórios dos 3 agentes...";
  try {
    const res  = await fetch("/api/agente/gerente", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        credito: agentResults.credito || "",
        fraude:  agentResults.fraude  || "",
        invest:  agentResults.invest  || "",
      }),
    });
    const data = await res.json();
    out.textContent = data.resultado || data.error;
  } catch (e) {
    out.textContent = "Erro ao conectar com o servidor Flask.";
  }
  btn.disabled = false;
  btn.innerHTML = "📑 Gerar Relatório Executivo";
}
