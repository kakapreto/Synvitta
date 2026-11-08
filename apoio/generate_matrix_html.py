"""
Generates updated matriz_sensibilidade_synvitta2.html including:
1. Parity point highlight (Margens Iguais Matriz = Subsidiaria no Cenario 1).
2. Minimum viable point for the partner (Margem da operacao Brasil >= 20% em funcao dos riscos).
3. Optimal point for the Matriz (Venda EUA + Remessa Brasil 75% = R$ 5.210.394 em FOB $1.346,65).
"""

import json
import re

with open('simulador_synvitta/synvitta2_report.htm', 'r', encoding='utf-8') as f:
    report_content = f.read()

m = re.search(r'id="initial-values"[^>]*>(.*?)</script>', report_content)
initial_params = json.loads(m.group(1))

html_content = """<!doctype html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Synvitta2 · Matriz de Sensibilidade, Paridade de Margens & Ponto Ótimo da Matriz</title>
<meta name="description" content="Análise econométrica de sensibilidade FOB vs margem de lucro com ponto de equilíbrio (paridade de margens), ponto mínimo viável para o sócio (20%) e ponto ótimo da Matriz.">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@300;400;500;600;700;800&family=JetBrains+Mono:wght@400;500;600;700&display=swap" rel="stylesheet">
<style>
:root {
  --bg-main: #070a13;
  --bg-card: rgba(13, 19, 34, 0.78);
  --bg-card-hover: rgba(18, 26, 46, 0.92);
  --border: rgba(255, 255, 255, 0.08);
  --border-focus: rgba(0, 210, 255, 0.45);
  --text-primary: #f1f5f9;
  --text-secondary: #94a3b8;
  --text-muted: #64748b;
  --cyan: #00d2ff;
  --cyan-glow: rgba(0, 210, 255, 0.25);
  --emerald: #10b981;
  --emerald-glow: rgba(16, 185, 129, 0.25);
  --amber: #f59e0b;
  --amber-glow: rgba(245, 158, 11, 0.25);
  --rose: #f43f5e;
  --rose-glow: rgba(244, 63, 94, 0.25);
  --indigo: #6366f1;
  --purple: #a855f7;
  --gold: #fbbf24;
  --gold-glow: rgba(251, 191, 36, 0.3);
  --font-sans: 'Plus Jakarta Sans', system-ui, -apple-system, sans-serif;
  --font-mono: 'JetBrains Mono', monospace;
  --radius-sm: 8px;
  --radius-md: 14px;
  --radius-lg: 20px;
  --shadow: 0 12px 36px rgba(0, 0, 0, 0.4);
}

[data-theme="light"] {
  --bg-main: #f8fafc;
  --bg-card: rgba(255, 255, 255, 0.88);
  --bg-card-hover: rgba(255, 255, 255, 0.98);
  --border: rgba(0, 0, 0, 0.08);
  --border-focus: rgba(0, 150, 200, 0.5);
  --text-primary: #0f172a;
  --text-secondary: #475569;
  --text-muted: #64748b;
  --cyan: #0284c7;
  --cyan-glow: rgba(2, 132, 199, 0.15);
  --emerald: #059669;
  --emerald-glow: rgba(5, 150, 105, 0.15);
  --amber: #d97706;
  --amber-glow: rgba(217, 119, 6, 0.15);
  --rose: #e11d48;
  --rose-glow: rgba(225, 29, 72, 0.15);
  --indigo: #4f46e5;
  --purple: #9333ea;
  --gold: #b45309;
  --gold-glow: rgba(180, 83, 9, 0.2);
  --shadow: 0 12px 30px rgba(0, 0, 0, 0.06);
}

* { box-sizing: border-box; margin: 0; padding: 0; }

body {
  background-color: var(--bg-main);
  color: var(--text-primary);
  font-family: var(--font-sans);
  line-height: 1.6;
  min-height: 100vh;
  padding-bottom: 60px;
  transition: background-color 0.3s ease, color 0.3s ease;
  overflow-x: hidden;
}

.ambient-glow {
  position: fixed;
  width: 600px;
  height: 600px;
  border-radius: 50%;
  filter: blur(140px);
  opacity: 0.18;
  pointer-events: none;
  z-index: 0;
}
.glow-1 { top: -100px; left: -100px; background: var(--cyan); }
.glow-2 { top: 30%; right: -150px; background: var(--indigo); }
.glow-3 { bottom: 100px; left: 20%; background: var(--gold); }

.container {
  max-width: 1440px;
  margin: 0 auto;
  padding: 24px 28px;
  position: relative;
  z-index: 1;
}

header {
  background: var(--bg-card);
  backdrop-filter: blur(16px);
  -webkit-backdrop-filter: blur(16px);
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  padding: 24px 32px;
  margin-bottom: 24px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-wrap: wrap;
  gap: 20px;
  box-shadow: var(--shadow);
}

.brand-badge {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 4px 12px;
  background: rgba(0, 210, 255, 0.1);
  border: 1px solid rgba(0, 210, 255, 0.3);
  border-radius: 999px;
  color: var(--cyan);
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  margin-bottom: 8px;
}

h1 {
  font-size: clamp(22px, 2.5vw, 32px);
  font-weight: 800;
  letter-spacing: -0.02em;
  line-height: 1.2;
  background: linear-gradient(135deg, var(--text-primary) 40%, var(--cyan) 100%);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
}

header p {
  color: var(--text-secondary);
  font-size: 14px;
  margin-top: 4px;
}

.header-controls {
  display: flex;
  align-items: center;
  gap: 12px;
}

.btn-pill {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 9px 18px;
  border-radius: 999px;
  border: 1px solid var(--border);
  background: var(--bg-card);
  color: var(--text-primary);
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s ease;
}

.btn-pill:hover {
  border-color: var(--cyan);
  box-shadow: 0 0 16px var(--cyan-glow);
  transform: translateY(-1px);
}

.btn-pill.primary {
  background: linear-gradient(135deg, var(--cyan), var(--indigo));
  color: #fff;
  border: none;
}

/* Strategic Highlights Grid (Dual Callouts) */
.dual-callout-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 18px;
  margin-bottom: 24px;
}

.callout-box {
  background: var(--bg-card);
  backdrop-filter: blur(14px);
  border-radius: var(--radius-md);
  padding: 22px 24px;
  position: relative;
  overflow: hidden;
  box-shadow: var(--shadow);
  border: 1px solid var(--border);
}

.callout-box.parity {
  border-color: rgba(0, 210, 255, 0.4);
  background: linear-gradient(135deg, rgba(0, 210, 255, 0.08), rgba(99, 102, 241, 0.05));
}

.callout-box.security {
  border-color: rgba(245, 158, 11, 0.4);
  background: linear-gradient(135deg, rgba(245, 158, 11, 0.08), rgba(244, 63, 94, 0.05));
}

.callout-badge {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 11px;
  font-weight: 800;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  padding: 3px 10px;
  border-radius: 6px;
  margin-bottom: 10px;
}

.callout-box.parity .callout-badge { background: var(--cyan); color: #070a13; }
.callout-box.security .callout-badge { background: var(--amber); color: #070a13; }

.callout-title {
  font-size: 17px;
  font-weight: 800;
  color: var(--text-primary);
  margin-bottom: 6px;
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.callout-target-val {
  font-family: var(--font-mono);
  font-size: 20px;
  font-weight: 800;
}
.callout-box.parity .callout-target-val { color: var(--cyan); }
.callout-box.security .callout-target-val { color: var(--amber); }

.callout-desc {
  font-size: 13px;
  color: var(--text-secondary);
  line-height: 1.5;
  margin-bottom: 12px;
}

.callout-stats-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 10px;
  padding-top: 12px;
  border-top: 1px solid var(--border);
}

.c-stat span { display: block; font-size: 11px; color: var(--text-muted); }
.c-stat strong { display: block; font-family: var(--font-mono); font-size: 13px; color: var(--text-primary); margin-top: 2px; }

/* Big Decision Banner */
.winner-banner {
  background: linear-gradient(135deg, rgba(16, 185, 129, 0.16), rgba(0, 210, 255, 0.1));
  border: 1px solid rgba(16, 185, 129, 0.45);
  border-radius: var(--radius-lg);
  padding: 22px 28px;
  margin-bottom: 24px;
  display: grid;
  grid-template-columns: auto 1fr auto;
  align-items: center;
  gap: 24px;
  box-shadow: 0 10px 30px var(--emerald-glow);
}

.winner-icon {
  width: 58px;
  height: 58px;
  border-radius: 50%;
  background: linear-gradient(135deg, var(--gold), var(--emerald));
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 28px;
  box-shadow: 0 0 24px var(--gold-glow);
  flex-shrink: 0;
}

.winner-content h2 {
  font-size: 19px;
  font-weight: 800;
  color: var(--emerald);
  margin-bottom: 4px;
  display: flex;
  align-items: center;
  gap: 10px;
}

.winner-content p {
  color: var(--text-secondary);
  font-size: 14px;
  line-height: 1.5;
}

.winner-stat {
  text-align: right;
  border-left: 1px solid rgba(255, 255, 255, 0.12);
  padding-left: 24px;
}
.winner-stat-val {
  font-size: 28px;
  font-weight: 800;
  color: var(--gold);
  font-family: var(--font-mono);
}
.winner-stat-lbl {
  font-size: 11px;
  text-transform: uppercase;
  color: var(--text-muted);
  letter-spacing: 0.05em;
}

/* Key Metrics Cards Grid */
.kpi-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 18px;
  margin-bottom: 24px;
}

.kpi-card {
  background: var(--bg-card);
  backdrop-filter: blur(14px);
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  padding: 20px;
  position: relative;
  transition: all 0.25s ease;
  overflow: hidden;
}

.kpi-card::before {
  content: "";
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  height: 4px;
  background: var(--card-accent, var(--cyan));
}

.kpi-card.optimum-highlight {
  border-color: rgba(251, 191, 36, 0.6);
  box-shadow: 0 0 25px var(--gold-glow);
}

.kpi-card:hover {
  transform: translateY(-3px);
  border-color: var(--border-focus);
  box-shadow: var(--shadow);
}

.kpi-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 10px;
}

.kpi-tag {
  font-size: 11px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  color: var(--text-muted);
}

.kpi-badge {
  font-size: 10px;
  font-weight: 800;
  padding: 3px 8px;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.08);
  color: var(--card-accent, var(--cyan));
}

.kpi-value {
  font-size: clamp(20px, 1.8vw, 25px);
  font-weight: 800;
  font-family: var(--font-mono);
  color: var(--text-primary);
  margin-bottom: 6px;
  letter-spacing: -0.02em;
}

.kpi-desc {
  font-size: 12px;
  color: var(--text-secondary);
  line-height: 1.45;
}

.kpi-breakdown {
  margin-top: 12px;
  padding-top: 10px;
  border-top: 1px solid var(--border);
  display: flex;
  flex-direction: column;
  gap: 4px;
  font-size: 11px;
  font-family: var(--font-mono);
}

.breakdown-row {
  display: flex;
  justify-content: space-between;
  color: var(--text-muted);
}

.breakdown-row strong {
  color: var(--text-primary);
}

/* Section styling */
.section {
  background: var(--bg-card);
  backdrop-filter: blur(14px);
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  padding: 28px;
  margin-bottom: 24px;
  box-shadow: var(--shadow);
}

.section-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 20px;
  flex-wrap: wrap;
  gap: 16px;
}

.section-title {
  font-size: 20px;
  font-weight: 700;
  color: var(--text-primary);
  display: flex;
  align-items: center;
  gap: 10px;
}

.section-desc {
  font-size: 13px;
  color: var(--text-secondary);
  margin-top: 4px;
  max-width: 850px;
}

/* Tabs & Switchers */
.tab-group {
  display: inline-flex;
  background: rgba(0, 0, 0, 0.3);
  border: 1px solid var(--border);
  border-radius: 999px;
  padding: 4px;
  gap: 4px;
}

.tab-btn {
  padding: 7px 16px;
  border-radius: 999px;
  border: none;
  background: transparent;
  color: var(--text-muted);
  font-size: 12px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s ease;
}

.tab-btn:hover { color: var(--text-primary); }

.tab-btn.active {
  background: var(--cyan);
  color: #070a13;
  font-weight: 800;
}

/* 2D Heatmap Matrix Table */
.matrix-container {
  overflow-x: auto;
  border-radius: var(--radius-md);
  border: 1px solid var(--border);
  margin-top: 14px;
}

table.matrix-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 12px;
  min-width: 880px;
}

table.matrix-table th, table.matrix-table td {
  padding: 10px 14px;
  text-align: right;
  border: 1px solid var(--border);
  white-space: nowrap;
}

table.matrix-table th {
  background: rgba(0, 0, 0, 0.4);
  color: var(--text-secondary);
  font-weight: 700;
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 0.04em;
}

table.matrix-table th.col-corner {
  text-align: left;
  background: rgba(0, 0, 0, 0.55);
  color: var(--cyan);
}

table.matrix-table th.col-header { text-align: right; }

table.matrix-table td.row-header {
  text-align: left;
  font-weight: 700;
  font-family: var(--font-mono);
  background: rgba(0, 0, 0, 0.28);
  color: var(--text-primary);
}

.cell-val {
  font-family: var(--font-mono);
  font-size: 12px;
  font-weight: 700;
  display: block;
}

.cell-sub {
  font-size: 10px;
  opacity: 0.8;
  display: block;
  margin-top: 2px;
}

.cell-optimum {
  position: relative;
  outline: 2px solid var(--gold);
  outline-offset: -2px;
  background: rgba(251, 191, 36, 0.22) !important;
}

.cell-parity {
  position: relative;
  outline: 2px solid var(--cyan);
  outline-offset: -2px;
  background: rgba(0, 210, 255, 0.22) !important;
}

.badge-optimum {
  display: inline-block;
  background: var(--gold);
  color: #070a13;
  font-size: 9px;
  font-weight: 800;
  padding: 1px 6px;
  border-radius: 4px;
  margin-left: 5px;
  text-transform: uppercase;
  vertical-align: middle;
}

.badge-parity {
  display: inline-block;
  background: var(--cyan);
  color: #070a13;
  font-size: 9px;
  font-weight: 800;
  padding: 1px 6px;
  border-radius: 4px;
  margin-left: 5px;
  text-transform: uppercase;
  vertical-align: middle;
}

.badge-security {
  display: inline-block;
  background: var(--amber);
  color: #070a13;
  font-size: 9px;
  font-weight: 800;
  padding: 1px 6px;
  border-radius: 4px;
  margin-left: 5px;
  text-transform: uppercase;
  vertical-align: middle;
}

/* Charts Section */
.charts-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 20px;
  margin-top: 14px;
}

.chart-card {
  background: rgba(0, 0, 0, 0.25);
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  padding: 18px;
}

.chart-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
  flex-wrap: wrap;
  gap: 8px;
}

.chart-title {
  font-size: 14px;
  font-weight: 700;
  color: var(--text-primary);
}

.chart-legend {
  display: flex;
  gap: 14px;
  font-size: 11px;
  color: var(--text-muted);
}

.legend-item {
  display: flex;
  align-items: center;
  gap: 6px;
}

.legend-color {
  width: 12px;
  height: 4px;
  border-radius: 2px;
}

.svg-chart {
  width: 100%;
  height: 320px;
  overflow: visible;
}

/* Interactive Simulator */
.sim-panel {
  display: grid;
  grid-template-columns: 320px 1fr;
  gap: 24px;
  background: rgba(0, 0, 0, 0.25);
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  padding: 20px;
  margin-top: 14px;
}

.controls-col {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.control-item {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.control-label {
  display: flex;
  justify-content: space-between;
  font-size: 12px;
  font-weight: 600;
  color: var(--text-secondary);
}

.control-value {
  font-family: var(--font-mono);
  color: var(--cyan);
  font-weight: 700;
}

input[type="range"] {
  -webkit-appearance: none;
  width: 100%;
  height: 6px;
  border-radius: 3px;
  background: rgba(255, 255, 255, 0.12);
  outline: none;
}
input[type="range"]::-webkit-slider-thumb {
  -webkit-appearance: none;
  width: 18px;
  height: 18px;
  border-radius: 50%;
  background: var(--cyan);
  cursor: pointer;
  box-shadow: 0 0 10px var(--cyan-glow);
  transition: transform 0.15s ease;
}
input[type="range"]::-webkit-slider-thumb:hover { transform: scale(1.2); }

.results-col {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
}

.sim-result-box {
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  padding: 16px;
}

.sim-result-box.winner {
  border-color: var(--gold);
  box-shadow: 0 0 24px rgba(251, 191, 36, 0.2);
}

.sim-box-title {
  font-size: 13px;
  font-weight: 700;
  color: var(--text-primary);
  margin-bottom: 12px;
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.sim-row {
  display: flex;
  justify-content: space-between;
  font-size: 12px;
  padding: 5px 0;
  border-bottom: 1px dashed rgba(255, 255, 255, 0.06);
}

.sim-row span:first-child { color: var(--text-muted); }
.sim-row span:last-child { font-family: var(--font-mono); font-weight: 600; color: var(--text-primary); }

.sim-row.total {
  border-bottom: none;
  margin-top: 8px;
  padding-top: 8px;
  border-top: 1px solid var(--border);
}
.sim-row.total span:first-child { font-weight: 800; color: var(--gold); }
.sim-row.total span:last-child { font-size: 16px; color: var(--gold); font-weight: 800; }

/* Advisory Cards */
.advisory-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 18px;
  margin-top: 16px;
}

.advisory-card {
  background: rgba(0, 0, 0, 0.25);
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  padding: 22px;
  position: relative;
}

.advisory-card h3 {
  font-size: 15px;
  font-weight: 700;
  color: var(--text-primary);
  margin-bottom: 12px;
  display: flex;
  align-items: center;
  gap: 8px;
}

.advisory-card p {
  font-size: 13px;
  color: var(--text-secondary);
  line-height: 1.6;
  margin-bottom: 12px;
}

.advisory-card ul {
  list-style: none;
  font-size: 12px;
  color: var(--text-secondary);
  display: flex;
  flex-direction: column;
  gap: 9px;
}

.advisory-card ul li {
  display: flex;
  align-items: flex-start;
  gap: 8px;
}

.advisory-card ul li::before {
  content: "✦";
  color: var(--cyan);
}

/* Detailed Comparison Table */
.data-table-container {
  overflow-x: auto;
  border-radius: var(--radius-md);
  border: 1px solid var(--border);
  margin-top: 14px;
}

table.data-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 12px;
}

table.data-table th, table.data-table td {
  padding: 10px 12px;
  text-align: right;
  border-bottom: 1px solid var(--border);
  white-space: nowrap;
}

table.data-table th {
  background: rgba(0, 0, 0, 0.45);
  color: var(--text-secondary);
  font-weight: 700;
  font-size: 11px;
}

table.data-table th:first-child, table.data-table td:first-child { text-align: left; }

table.data-table tr:hover { background: rgba(255, 255, 255, 0.04); }

table.data-table tr.row-optimum {
  background: rgba(251, 191, 36, 0.12) !important;
  font-weight: 700;
}
table.data-table tr.row-parity {
  background: rgba(0, 210, 255, 0.12) !important;
}
table.data-table tr.row-security {
  background: rgba(245, 158, 11, 0.12) !important;
}

footer {
  text-align: center;
  color: var(--text-muted);
  font-size: 12px;
  margin-top: 40px;
  padding-top: 20px;
  border-top: 1px solid var(--border);
}

@media (max-width: 1100px) {
  .dual-callout-grid { grid-template-columns: 1fr; }
  .kpi-grid { grid-template-columns: repeat(2, 1fr); }
  .charts-grid { grid-template-columns: 1fr; }
  .winner-banner { grid-template-columns: 1fr; }
  .winner-stat { text-align: left; border-left: none; padding-left: 0; border-top: 1px solid rgba(255,255,255,0.1); padding-top: 14px; }
  .advisory-grid { grid-template-columns: 1fr; }
  .sim-panel { grid-template-columns: 1fr; }
}

@media (max-width: 650px) {
  .container { padding: 16px; }
  .kpi-grid { grid-template-columns: 1fr; }
  header { flex-direction: column; align-items: flex-start; }
}
</style>
</head>
<body>

<div class="ambient-glow glow-1"></div>
<div class="ambient-glow glow-2"></div>
<div class="ambient-glow glow-3"></div>

<div class="container">

  <!-- Header -->
  <header>
    <div>
      <div class="brand-badge">Synvitta2 · Análise de Sensibilidade & Otimização da Matriz</div>
      <h1>Ponto Ótimo, Paridade de Margens & Viabilidade do Sócio</h1>
      <p>Simulação econométrica baseada no relatório <code>Synvitta2_report</code> (1.000 kits · Lucro Presumido · Matriz Flórida EUA · Câmbio R$ 5,60)</p>
    </div>
    <div class="header-controls">
      <button class="btn-pill" id="theme-toggle" onclick="toggleTheme()">
        <span id="theme-icon">🌙</span> <span id="theme-text">Modo Claro</span>
      </button>
      <button class="btn-pill primary" onclick="window.print()">
        <span>🖨️</span> Imprimir Relatório
      </button>
    </div>
  </header>

  <!-- Dual Strategic Callouts: Parity & Minimum Viable Partner Point -->
  <div class="dual-callout-grid">
    <!-- Parity Callout -->
    <div class="callout-box parity">
      <div class="callout-badge">⚖️ Ponto de Paridade e Equilíbrio (Margens Iguais)</div>
      <div class="callout-title">
        <span>Equilíbrio Perfeito Matriz & Subsidiária</span>
        <span class="callout-target-val">FOB US$ 487,56</span>
      </div>
      <p class="callout-desc">
        Neste ponto exato, a <strong>Margem da Matriz</strong> e a <strong>Margem Líquida da Subsidiária no Brasil</strong> são <strong>rigorosamente iguais a 50,84%</strong>. Ambas as entidades geram exatamente <strong>R$ 4.879.607,22</strong> cada, estabelecendo justiça contratual e simetria de rentabilidade.
      </p>
      <div class="callout-stats-grid">
        <div class="c-stat"><span>Lucro Total Matriz:</span><strong>R$ 4.879.607 (50,84%)</strong></div>
        <div class="c-stat"><span>Lucro Líq. Subsidiária:</span><strong>R$ 4.879.607 (50,84%)</strong></div>
        <div class="c-stat"><span>Sócio Local (25%):</span><strong>R$ 1.219.902 (R$ 1.220/kit)</strong></div>
      </div>
    </div>

    <!-- Partner Security 20% Callout -->
    <div class="callout-box security">
      <div class="callout-badge">🛡️ Ponto Mínimo Viável para o Sócio (Margem ≥ 20%)</div>
      <div class="callout-title">
        <span>Teto de FOB p/ Absorção de Riscos</span>
        <span class="callout-target-val">FOB US$ 1.008,68</span>
      </div>
      <p class="callout-desc">
        Em função dos <strong>severos riscos assumidos pelo sócio local no Brasil</strong> (responsabilidade técnica perante a ANVISA, risco trabalhista CLT, passivos tributários e risco de crédito/inadimplência hospitalar), o FOB máximo suportado sem comprometer a viabilidade de 20% de margem no Brasil é <strong>US$ 1.008,68</strong> (ou ~US$ 1.000).
      </p>
      <div class="callout-stats-grid">
        <div class="c-stat"><span>Margem Operação BR:</span><strong style="color:var(--amber);">20,00% (R$ 1,92 mi)</strong></div>
        <div class="c-stat"><span>Lucro Total Matriz:</span><strong>R$ 5.080.260 (52,93%)</strong></div>
        <div class="c-stat"><span>Retido Sócio Local:</span><strong>R$ 479.920 livres</strong></div>
      </div>
    </div>
  </div>

  <!-- Big Decision Banner -->
  <div class="winner-banner">
    <div class="winner-icon">🏆</div>
    <div class="winner-content">
      <h2>Veredito Executivo: Cenário 1 (Subsidiária 75%) é a Melhor Opção de Todas</h2>
      <p>
        No Cenário 1, a Matriz captura as duas pontas da cadeia: o <strong>lucro da venda nos EUA</strong> e <strong>75% do lucro líquido gerado no Brasil</strong>. O Ponto Ótimo de Máximo Lucro da Matriz ocorre em <strong>FOB = US$ 1.346,65 / kit</strong> (atingindo <strong>R$ 5.210.394</strong>). Mesmo no FOB base de US$ 200, a Matriz já lucra <strong>R$ 4.768.883</strong> (49,68%), contra míseros <strong>R$ 416.605</strong> (4,34%) no Cenário 2 via distribuidor!
      </p>
    </div>
    <div class="winner-stat">
      <div class="winner-stat-val">R$ 5.210.394</div>
      <div class="winner-stat-lbl">Ponto Ótimo de Lucro Máximo da Matriz (FOB $1.346,65)</div>
    </div>
  </div>

  <!-- Key Metrics / KPI Cards -->
  <div class="kpi-grid">
    <div class="kpi-card optimum-highlight" style="--card-accent: var(--gold);">
      <div class="kpi-header">
        <span class="kpi-tag">Ponto Ótimo Absoluto · C1</span>
        <span class="kpi-badge" style="background: var(--gold); color: #070a13;">MÁXIMO DA MATRIZ</span>
      </div>
      <div class="kpi-value" style="color: var(--gold);">R$ 5.210.394</div>
      <div class="kpi-desc">Alcançado no <strong>FOB = US$ 1.346,65 / kit</strong>. Margem de <strong>54,28%</strong> sobre a receita bruta.</div>
      <div class="kpi-breakdown">
        <div class="breakdown-row"><span>Exportação EUA:</span><strong>R$ 5.210.381,48</strong></div>
        <div class="breakdown-row"><span>Remessa Brasil (75%):</span><strong>R$ 12,16 (equilibra BR)</strong></div>
      </div>
    </div>

    <div class="kpi-card" style="--card-accent: var(--cyan);">
      <div class="kpi-header">
        <span class="kpi-tag">Ponto de Paridade (50,84%)</span>
        <span class="kpi-badge">EQUILÍBRIO BILATERAL</span>
      </div>
      <div class="kpi-value" style="color: var(--cyan);">FOB US$ 487,56</div>
      <div class="kpi-desc">Matriz e Subsidiária geram exatamente <strong>R$ 4,88 mi cada</strong> (margens iguais de 50,84%).</div>
      <div class="kpi-breakdown">
        <div class="breakdown-row"><span>Lucro Matriz:</span><strong style="color: var(--cyan);">R$ 4.879.607</strong></div>
        <div class="c-stat-row breakdown-row"><span>Sócio Local (25%):</span><strong>R$ 1.219.902 livres</strong></div>
      </div>
    </div>

    <div class="kpi-card" style="--card-accent: var(--amber);">
      <div class="kpi-header">
        <span class="kpi-tag">Mínimo Viável Sócio (20%)</span>
        <span class="kpi-badge">TETO DE RISCO</span>
      </div>
      <div class="kpi-value" style="color: var(--amber);">FOB US$ 1.008,68</div>
      <div class="kpi-desc">Garante margem de <strong>20,00%</strong> para a operação do sócio suportar passivos e riscos regulatórios.</div>
      <div class="kpi-breakdown">
        <div class="breakdown-row"><span>Lucro Operação BR:</span><strong>R$ 1.919.680 (20%)</strong></div>
        <div class="breakdown-row"><span>Lucro Matriz:</span><strong style="color: var(--gold);">R$ 5.080.260 (52,93%)</strong></div>
      </div>
    </div>

    <div class="kpi-card" style="--card-accent: var(--rose);">
      <div class="kpi-header">
        <span class="kpi-tag">Cenário 2 · Base US$ 200</span>
        <span class="kpi-badge">Distribuidor 0%</span>
      </div>
      <div class="kpi-value" style="color: var(--rose);">R$ 416.605</div>
      <div class="kpi-desc">A Matriz só ganha a exportação básica. O distribuidor retém <strong>R$ 6.512.949</strong> (67,85% de margem!).</div>
      <div class="kpi-breakdown">
        <div class="breakdown-row"><span>Margem Matriz:</span><strong style="color: var(--rose);">Apenas 4,34%</strong></div>
        <div class="breakdown-row"><span>Vantagem C1:</span><strong style="color: var(--emerald);">+R$ 4.352.278 (+1.045%)</strong></div>
      </div>
    </div>
  </div>

  <!-- Interactive 2D Sensitivity Heatmap Matrix -->
  <div class="section">
    <div class="section-header">
      <div>
        <h2 class="section-title">📊 Matriz Bidimensional de Sensibilidade: FOB × Preço de Venda no Brasil</h2>
        <p class="section-desc">
          Avalie o <strong>Lucro Total da Matriz (Exportação EUA + Remessa de 75% do Brasil)</strong> para diferentes combinações de Preço FOB e Preço de Venda praticado no Brasil.
        </p>
      </div>
      <div class="tab-group" id="matrix-mode-selector">
        <button class="tab-btn active" onclick="setMatrixMode('c1_parent')">Lucro Total Matriz (C1)</button>
        <button class="tab-btn" onclick="setMatrixMode('c2_parent')">Lucro Total Matriz (C2)</button>
        <button class="tab-btn" onclick="setMatrixMode('advantage')">Vantagem C1 s/ C2 (Δ R$)</button>
        <button class="tab-btn" onclick="setMatrixMode('c1_margin')">Margem Matriz C1 (%)</button>
      </div>
    </div>

    <div class="matrix-container">
      <table class="matrix-table" id="heatmap-table">
        <!-- Rendered dynamically via JavaScript -->
      </table>
    </div>
  </div>

  <!-- Interactive Sensitivity Curves -->
  <div class="section">
    <div class="section-header">
      <div>
        <h2 class="section-title">📈 Curvas de Sensibilidade, Paridade e Limite de Segurança</h2>
        <p class="section-desc">
          Visualize a convergência: o cruzamento de paridade em <strong>FOB = US$ 487,56</strong> (50,84%), o piso de <strong>20% de margem</strong> em <strong>FOB = US$ 1.008,68</strong> e o ponto ótimo absoluto da Matriz em <strong>FOB = US$ 1.346,65</strong>.
        </p>
      </div>
      <div class="tab-group">
        <span style="font-size: 12px; color: var(--text-muted); align-self: center; margin-right: 8px;">Preço base Brasil: R$ 9.598,40</span>
      </div>
    </div>

    <div class="charts-grid">
      <!-- Chart 1: Lucro Total da Matriz (R$) -->
      <div class="chart-card">
        <div class="chart-header">
          <span class="chart-title">Lucro Total da Matriz (EUA + Remessa 75%)</span>
          <div class="chart-legend">
            <div class="legend-item"><div class="legend-color" style="background: var(--cyan);"></div> Cenário 1 (Total Matriz)</div>
            <div class="legend-item"><div class="legend-color" style="background: var(--gold);"></div> Parcela EUA C1</div>
            <div class="legend-item"><div class="legend-color" style="background: var(--emerald);"></div> Parcela Remessa C1</div>
            <div class="legend-item"><div class="legend-color" style="background: var(--rose);"></div> Cenário 2 (Total Matriz)</div>
          </div>
        </div>
        <div id="chart-profit-container">
          <svg class="svg-chart" id="chart-profit" viewBox="0 0 540 280"></svg>
        </div>
      </div>

      <!-- Chart 2: Margens de Lucro (%) -->
      <div class="chart-card">
        <div class="chart-header">
          <span class="chart-title">Margens sobre Receita Bruta (%)</span>
          <div class="chart-legend">
            <div class="legend-item"><div class="legend-color" style="background: var(--cyan);"></div> Margem Matriz C1</div>
            <div class="legend-item"><div class="legend-color" style="background: var(--emerald);"></div> Margem Subsidiária C1</div>
            <div class="legend-item"><div class="legend-color" style="background: var(--amber);"></div> Margem Distribuidor C2</div>
          </div>
        </div>
        <div id="chart-margin-container">
          <svg class="svg-chart" id="chart-margin" viewBox="0 0 540 280"></svg>
        </div>
      </div>
    </div>
  </div>

  <!-- Live Simulation Sandbox -->
  <div class="section">
    <div class="section-header">
      <div>
        <h2 class="section-title">🎛️ Simulador Interativo de Sensibilidade em Tempo Real</h2>
        <p class="section-desc">
          Mova os controles deslizantes para recalcular instantaneamente o Lucro da Venda dos EUA, a Remessa de Lucro do Brasil (75%), a margem do sócio e o Ponto Ótimo.
        </p>
      </div>
      <div style="display:flex; gap:8px;">
        <button class="btn-pill" onclick="setFobQuick(487.56)">⚖️ FOB Paridade ($487,56)</button>
        <button class="btn-pill" onclick="setFobQuick(1008.68)">🛡️ FOB Sócio 20% ($1.008,68)</button>
        <button class="btn-pill" onclick="setFobQuick(1346.65)">👑 FOB Máximo Matriz ($1.346,65)</button>
        <button class="btn-pill" onclick="resetSimParams()">↺ Base ($200)</button>
      </div>
    </div>

    <div class="sim-panel">
      <div class="controls-col">
        <div class="control-item">
          <div class="control-label">
            <span>Preço FOB (USD/kit)</span>
            <span class="control-value" id="val-fob">US$ 200,00</span>
          </div>
          <input type="range" id="slider-fob" min="100" max="1400" step="5" value="200" oninput="updateSim()">
        </div>

        <div class="control-item">
          <div class="control-label">
            <span>Preço de Venda Brasil (R$/kit)</span>
            <span class="control-value" id="val-price">R$ 9.598,40</span>
          </div>
          <input type="range" id="slider-price" min="6000" max="14000" step="200" value="9598.40" oninput="updateSim()">
        </div>

        <div class="control-item">
          <div class="control-label">
            <span>Taxa de Câmbio (USD/BRL)</span>
            <span class="control-value" id="val-exchange">R$ 5,60</span>
          </div>
          <input type="range" id="slider-exchange" min="4.50" max="7.00" step="0.10" value="5.60" oninput="updateSim()">
        </div>

        <div class="control-item">
          <div class="control-label">
            <span>Participação da Matriz no Brasil</span>
            <span class="control-value" id="val-share">75%</span>
          </div>
          <input type="range" id="slider-share" min="50" max="100" step="5" value="75" oninput="updateSim()">
        </div>
      </div>

      <div class="results-col">
        <div class="sim-result-box winner">
          <div class="sim-box-title">
            <span>Cenário 1: Subsidiária (75%)</span>
            <span class="badge-optimum" style="background: var(--gold); color: #000;">MELHOR OPÇÃO</span>
          </div>
          <div class="sim-row"><span>FOB Total:</span><span id="sim-c1-fob-total">US$ 200.000,00</span></div>
          <div class="sim-row"><span>Lucro Líquido Brasil (Sub):</span><span id="sim-c1-net-br">R$ 6.512.949,49</span></div>
          <div class="sim-row"><span>Margem Operação Brasil:</span><span id="sim-c1-sub-margin" style="color: var(--amber);">67,85%</span></div>
          <div class="sim-row"><span>Retido Sócio Local (25%):</span><span id="sim-c1-partner-retained" style="color: var(--emerald);">R$ 1.628.237,37</span></div>
          <div class="sim-row"><span>(1) Lucro Venda EUA (Net Export):</span><span id="sim-c1-net-exp" style="color: var(--cyan);">R$ 416.604,76</span></div>
          <div class="sim-row"><span>(2) Remessa Lucro Brasil (75%):</span><span id="sim-c1-remit" style="color: var(--emerald);">R$ 4.352.278,49</span></div>
          <div class="sim-row total"><span>Lucro Total Matriz (1 + 2):</span><span id="sim-c1-total" style="color: var(--gold);">R$ 4.768.883,26</span></div>
          <div class="sim-row" style="border: none;"><span>Margem Matriz s/ Faturamento:</span><span id="sim-c1-margin" style="color: var(--cyan);">49,68%</span></div>
        </div>

        <div class="sim-result-box">
          <div class="sim-box-title">
            <span>Cenário 2: Distribuidor (0%)</span>
            <span class="badge-optimum" style="background: var(--text-muted); color: #fff;">INDEPENDENTE</span>
          </div>
          <div class="sim-row"><span>FOB Total:</span><span id="sim-c2-fob-total">US$ 200.000,00</span></div>
          <div class="sim-row"><span>Lucro Líquido Distribuidor:</span><span id="sim-c2-net-dist">R$ 6.512.949,49</span></div>
          <div class="sim-row"><span>Margem do Distribuidor:</span><span id="sim-c2-dist-margin">67,85%</span></div>
          <div class="sim-row"><span>(1) Lucro Venda EUA (Net Export):</span><span id="sim-c2-net-exp">R$ 416.604,76</span></div>
          <div class="sim-row"><span>(2) Remessa Lucro Brasil (0%):</span><span style="color: var(--rose);">R$ 0,00 (0%)</span></div>
          <div class="sim-row total"><span>Lucro Total Matriz (1 + 2):</span><span id="sim-c2-total" style="color: var(--rose);">R$ 416.604,76</span></div>
          <div class="sim-row" style="border: none;"><span>Margem Matriz s/ Venda:</span><span id="sim-c2-margin" style="color: var(--rose);">4,34%</span></div>
        </div>
      </div>
    </div>
  </div>

  <!-- Detailed Step-by-Step Table -->
  <div class="section">
    <div class="section-header">
      <div>
        <h2 class="section-title">📋 Tabela Analítica: Sensibilidade, Paridade e Riscos do Sócio</h2>
        <p class="section-desc">
          Discriminação completa de receitas, remessas de dividendos, retenção do sócio local e verificação de piso de 20% de margem.
        </p>
      </div>
    </div>

    <div class="data-table-container">
      <table class="data-table" id="detailed-data-table">
        <thead>
          <tr>
            <th>FOB (USD/kit)</th>
            <th>(1) Lucro Venda EUA</th>
            <th>(2) Remessa Brasil (75%)</th>
            <th>Total Matriz C1 (1 + 2)</th>
            <th>Margem Matriz C1</th>
            <th>Lucro Líq. Brasil</th>
            <th>Margem Brasil</th>
            <th>Sócio Local (25%)</th>
            <th>Total Matriz C2</th>
            <th>Margem Distribuidor</th>
            <th>Vantagem C1 (Δ R$)</th>
          </tr>
        </thead>
        <tbody>
          <!-- Populated by JS -->
        </tbody>
      </table>
    </div>
  </div>

  <!-- Deep Strategic Advisory Section -->
  <div class="section">
    <div class="section-header">
      <div>
        <h2 class="section-title">🎯 Parecer Técnico: Governança, Paridade e Riscos Assumidos pelo Sócio</h2>
        <p class="section-desc">
          Fundamentação estratégica e societária para tomada de decisão e equilíbrio de longo prazo.
        </p>
      </div>
    </div>

    <div class="advisory-grid">
      <div class="advisory-card">
        <h3>1. Ponto de Paridade e Equilíbrio (FOB US$ 487,56)</h3>
        <p>
          Em <strong>FOB = US$ 487,56 / kit</strong>, alcança-se a simetria perfeita:
        </p>
        <ul>
          <li><strong>Margens Rigorosamente Iguais:</strong> A Matriz lucra <strong>50,84%</strong> e a Subsidiária Brasileira lucra <strong>50,84%</strong>.</li>
          <li><strong>Volume Financeiro Idêntico:</strong> A Matriz embolsa <strong>R$ 4.879.607,22</strong> e a subsidiária gera <strong>R$ 4.879.607,22</strong>.</li>
          <li><strong>Sócio Local Remunerado com Justiça:</strong> O sócio local (25%) retém <strong>R$ 1.219.901,80 livres</strong> (R$ 1.220 por kit), criando total alinhamento de incentivos.</li>
        </ul>
      </div>

      <div class="advisory-card">
        <h3>2. O Piso Mínimo de 20% do Sócio pelos Riscos</h3>
        <p>
          O sócio local brasileiro assume o ônus operacional e jurídico da operação:
        </p>
        <ul>
          <li><strong>Riscos Regulatórios ANVISA:</strong> Responsabilidade técnica e legal pelas Boas Práticas e conformidade dos testes.</li>
          <li><strong>Passivo Fiscal e Aduaneiro:</strong> Solidariedade dos sócios em fiscalizações de ICMS, PIS/COFINS e aduana.</li>
          <li><strong>Risco Trabalhista e Crédito:</strong> Contratos CLT e fluxo de recebimento de hospitais (prazos de 60-120 dias).</li>
          <li><strong>FOB Teto de Segurança (US$ 1.008,68):</strong> Garante que a margem da operação brasileira não fique abaixo de <strong>20,00%</strong> (R$ 1,92 mi), deixando R$ 480 mil livres para o sócio.</li>
        </ul>
      </div>

      <div class="advisory-card">
        <h3>3. Comparativo Final: C1 vs C2</h3>
        <p>
          O Cenário 1 protege todos os flancos em qualquer ponto da curva:
        </p>
        <ul>
          <li><strong>FOB Base US$ 200:</strong> Matriz ganha <strong>R$ 4,77 mi</strong> no C1 vs míseros <strong>R$ 416 mil</strong> no C2 (+R$ 4,35 mi para a Matriz).</li>
          <li><strong>FOB Paridade US$ 487,56:</strong> Matriz ganha <strong>R$ 4,88 mi</strong> e filial tem R$ 4,88 mi de lucro equilibrado.</li>
          <li><strong>FOB Ótimo Matriz US$ 1.346,65:</strong> Matriz atinge seu teto de <strong>R$ 5,21 mi</strong>.</li>
          <li><strong>No Cenário 2:</strong> O distribuidor independente fica com o controle do registro sanitário e 67,8% do lucro, deixando a Matriz vulnerável.</li>
        </ul>
      </div>
    </div>
  </div>

  <footer>
    <p>Synvitta2 · Análise de Sensibilidade, Paridade e Governança do Sócio · Gerado com base no Synvitta2_report · 2026</p>
  </footer>

</div>

<script>
const INITIAL_P = """ + json.dumps(initial_params) + """;

let currentSim = {
  fob: 200.0,
  price: 9598.40,
  exchange: 5.60,
  share: 75.0,
  quantity: 1000.0
};

let currentMatrixMode = 'c1_parent';

function calculateScenario(fob, price, exchange, share, scenarioNum) {
  const p = INITIAL_P;
  const quantity = currentSim.quantity;
  const period = Number(p.meses_operacao || 3);
  const freightUsd = Number(p.frete_usd || 6400);
  const freightBrl = freightUsd * exchange;
  const fobUsd = fob * quantity;
  const insurance = (fobUsd + freightUsd) * exchange * (Number(p.seguro_pct || 0.25) / 100);
  const customsVal = fobUsd * exchange + freightBrl + insurance + Number(p.ajustes_aduaneiros_brl || 0);

  const pisImport = customsVal * (Number(p.aliq_pis || 0.21) / 100);
  const cofinsImport = customsVal * (Number(p.aliq_cofins || 0.965) / 100);
  const importTaxes = pisImport + cofinsImport;

  const dispatch = Number(p.custo_armazenagem || 11299.62) + Number(p.custo_capatazia || 2500) +
                   Number(p.custo_despachante || 4500) + Number(p.taxa_siscomex || 136.53) +
                   Number(p.taxas_terminal || 600) + Number(p.honorarios_agente_carga || 1100) +
                   Number(p.licencas_inspecao || 1637.70) + Number(p.outras_despesas_importacao || 1500);

  const inventoryCost = customsVal + importTaxes + dispatch;
  const cogs = (inventoryCost / quantity) * quantity;

  const grossRevenue = price * quantity;
  const salesTaxRate = (Number(p.aliq_icms_venda || 4) + Number(p.aliq_pis_venda || 0.65) + Number(p.aliq_cofins_venda || 3)) / 100;
  const salesTaxes = grossRevenue * salesTaxRate;
  const netRevenue = grossRevenue - salesTaxes;

  const monthlyOpex = Number(p.opex_pessoal || 90000) + Number(p.opex_aluguel || 25000) + Number(p.opex_utilidades || 10000) +
                      Number(p.opex_servicos_profissionais || 15000) + Number(p.opex_comercial_marketing || 30000) +
                      Number(p.opex_sistemas || 5000) + Number(p.opex_seguros || 5000) + Number(p.opex_depreciacao || 10000) +
                      Number(p.opex_administrativo || 5000) + Number(p.opex_outros || 5000);
  const opexFactor = scenarioNum === 1 ? 1.0 : Number(p.fator_opex_c2 || 1.0);
  const totalOpex = monthlyOpex * period * opexFactor;
  const varOperator = netRevenue * (Number(p.operador_pct || 3) / 100);

  const operatingProfit = netRevenue - cogs - varOperator - totalOpex;

  // Lucro Presumido
  const irpj = grossRevenue * (Number(p.aliq_irpj_faturamento || 1.2) / 100);
  const addIrpj = Math.max(grossRevenue * (Number(p.base_presumida_irpj || 8) / 100) - Number(p.limite_adicional_irpj_mensal || 20000) * period, 0) * (Number(p.aliq_adicional_irpj || 10) / 100);
  const csll = grossRevenue * (Number(p.aliq_csll_faturamento || 1.08) / 100);
  const brazilTax = irpj + addIrpj + csll;
  const netBrazil = operatingProfit - brazilTax;

  // Parcela 1: Lucro de Exportação EUA (Net Export)
  const mfgCost = Number(p.custo_fabricacao_usd || 100) * quantity * exchange;
  const exportBeforeTax = fobUsd * exchange - mfgCost - Number(p.opex_matriz_usd || 350) * exchange;
  const flTax = Math.max(exportBeforeTax, 0) * (Number(p.rateio_fl || 100) / 100) * (Number(p.aliq_fl || 5.5) / 100);
  const fedTax = Math.max(exportBeforeTax - flTax, 0) * (Number(p.aliq_federal_eua || 21) / 100);
  const netExport = exportBeforeTax - flTax - fedTax;

  // Parcela 2: Remessa de Lucro do Brasil (75%)
  const parentShareRate = scenarioNum === 1 ? (share / 100) : (Number(p.participacao_matriz_c2 || 0) / 100);
  const parentBrazil = Math.max(netBrazil, 0) * parentShareRate;
  const divWht = parentBrazil * (Number(p.retencao_dividendos || 10) / 100);
  const remitAfterTax = parentBrazil - divWht;
  const remitCost = remitAfterTax * (Number(p.custo_remessa || 1) / 100);
  const netRemittance = remitAfterTax - remitCost;

  const branchRetained = netBrazil - parentBrazil; // 25% para o sócio local
  
  // Total Matriz = (1) Lucro Venda EUA + (2) Remessa Lucro Brasil 75%
  const totalParent = netExport + netRemittance;
  const globalProfit = netExport + branchRetained + netRemittance;

  return {
    fob, price, exchange, fobUsd, customsVal, inventoryCost, cogs,
    grossRevenue, netRevenue, operatingProfit, brazilTax, netBrazil,
    netExport, parentBrazil, netRemittance, branchRetained, totalParent,
    globalProfit,
    parentGrossMargin: grossRevenue > 0 ? (totalParent / grossRevenue) * 100 : 0,
    brazilGrossMargin: grossRevenue > 0 ? (netBrazil / grossRevenue) * 100 : 0,
    partnerRetainedMargin: grossRevenue > 0 ? (branchRetained / grossRevenue) * 100 : 0,
    distributorGrossMargin: grossRevenue > 0 ? (netBrazil / grossRevenue) * 100 : 0
  };
}

function fmtMoney(v) {
  return 'R$ ' + Number(v || 0).toLocaleString('pt-BR', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

function fmtMoneyCompact(v) {
  if (Math.abs(v) >= 1000000) return 'R$ ' + (v / 1000000).toLocaleString('pt-BR', { minimumFractionDigits: 2, maximumFractionDigits: 2 }) + ' mi';
  if (Math.abs(v) >= 10000) return 'R$ ' + (v / 1000).toLocaleString('pt-BR', { minimumFractionDigits: 1, maximumFractionDigits: 1 }) + ' mil';
  return fmtMoney(v);
}

function fmtUsd(v) {
  return 'US$ ' + Number(v || 0).toLocaleString('pt-BR', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

function fmtPct(v) {
  return Number(v || 0).toLocaleString('pt-BR', { minimumFractionDigits: 2, maximumFractionDigits: 2 }) + '%';
}

const matrixFobs = [100, 150, 200, 300, 400, 487.56, 600, 800, 1000, 1008.68, 1200, 1346.65];
const matrixPrices = [7000, 8000, 9598.40, 11000, 12500];

function renderHeatmap() {
  const table = document.getElementById('heatmap-table');
  let html = '<thead><tr><th class="col-corner">FOB (USD) \\ Venda (R$)</th>';
  for (let pr of matrixPrices) {
    const isBase = Math.abs(pr - 9598.40) < 1;
    html += `<th class="col-header">${fmtMoney(pr)}${isBase ? ' <span class="badge-optimum" style="background:var(--cyan);color:#000;">BASE</span>' : ''}</th>`;
  }
  html += '</tr></thead><tbody>';

  let values = [];
  for (let fob of matrixFobs) {
    for (let pr of matrixPrices) {
      let r1 = calculateScenario(fob, pr, currentSim.exchange, currentSim.share, 1);
      let r2 = calculateScenario(fob, pr, currentSim.exchange, currentSim.share, 2);
      if (currentMatrixMode === 'c1_parent') values.push(r1.totalParent);
      else if (currentMatrixMode === 'c2_parent') values.push(r2.totalParent);
      else if (currentMatrixMode === 'advantage') values.push(r1.totalParent - r2.totalParent);
      else if (currentMatrixMode === 'c1_margin') values.push(r1.parentGrossMargin);
    }
  }
  const minVal = Math.min(...values);
  const maxVal = Math.max(...values);

  for (let fob of matrixFobs) {
    const isOptimumAbsolute = Math.abs(fob - 1346.65) < 0.1;
    const isParity = Math.abs(fob - 487.56) < 0.1;
    const isSecurity = Math.abs(fob - 1008.68) < 0.1;
    const isBaseFob = fob === 200;

    let badgeText = '';
    if (isOptimumAbsolute) badgeText = ' <span class="badge-optimum">👑 ÓTIMO</span>';
    else if (isParity) badgeText = ' <span class="badge-parity">⚖️ PARIDADE</span>';
    else if (isSecurity) badgeText = ' <span class="badge-security">🛡️ SÓCIO 20%</span>';
    else if (isBaseFob) badgeText = ' <span class="badge-optimum" style="background:var(--cyan);color:#000;">BASE</span>';

    html += `<tr><td class="row-header">${fmtUsd(fob)}${badgeText}</td>`;

    for (let pr of matrixPrices) {
      let r1 = calculateScenario(fob, pr, currentSim.exchange, currentSim.share, 1);
      let r2 = calculateScenario(fob, pr, currentSim.exchange, currentSim.share, 2);
      let val, subText, displayVal;

      if (currentMatrixMode === 'c1_parent') {
        val = r1.totalParent;
        displayVal = fmtMoneyCompact(val);
        subText = fmtPct(r1.parentGrossMargin);
      } else if (currentMatrixMode === 'c2_parent') {
        val = r2.totalParent;
        displayVal = fmtMoneyCompact(val);
        subText = fmtPct(r2.parentGrossMargin);
      } else if (currentMatrixMode === 'advantage') {
        val = r1.totalParent - r2.totalParent;
        displayVal = '+' + fmtMoneyCompact(val);
        subText = '+' + (val > 0 && r2.totalParent > 0 ? (val / r2.totalParent * 100).toFixed(0) + '%' : 'N/A');
      } else if (currentMatrixMode === 'c1_margin') {
        val = r1.parentGrossMargin;
        displayVal = fmtPct(val);
        subText = fmtMoneyCompact(r1.totalParent);
      }

      const norm = maxVal > minVal ? (val - minVal) / (maxVal - minVal) : 0.5;
      let bgStyle;
      if (currentMatrixMode === 'advantage') {
        bgStyle = `background: rgba(16, 185, 129, ${0.1 + norm * 0.35}); color: #10b981;`;
      } else if (val < 0) {
        bgStyle = 'background: rgba(244, 63, 94, 0.25); color: #f43f5e;';
      } else {
        bgStyle = `background: rgba(0, 210, 255, ${0.08 + norm * 0.35}); color: var(--text-primary);`;
      }

      let specialClass = '';
      if (isOptimumAbsolute && Math.abs(pr - 9598.40) < 1) specialClass = 'cell-optimum';
      else if (isParity && Math.abs(pr - 9598.40) < 1) specialClass = 'cell-parity';

      html += `<td style="${bgStyle}" class="${specialClass}">
        <span class="cell-val">${displayVal}</span>
        <span class="cell-sub">${subText}</span>
      </td>`;
    }
    html += '</tr>';
  }
  html += '</tbody>';
  table.innerHTML = html;
}

function setMatrixMode(mode) {
  currentMatrixMode = mode;
  document.querySelectorAll('#matrix-mode-selector .tab-btn').forEach(btn => btn.classList.remove('active'));
  event.target.classList.add('active');
  renderHeatmap();
}

function renderDetailedTable() {
  const tbody = document.querySelector('#detailed-data-table tbody');
  let html = '';
  for (let fob of matrixFobs) {
    let r1 = calculateScenario(fob, currentSim.price, currentSim.exchange, currentSim.share, 1);
    let r2 = calculateScenario(fob, currentSim.price, currentSim.exchange, currentSim.share, 2);
    let adv = r1.totalParent - r2.totalParent;
    let isOptimumAbsolute = Math.abs(fob - 1346.65) < 0.1;
    let isParity = Math.abs(fob - 487.56) < 0.1;
    let isSecurity = Math.abs(fob - 1008.68) < 0.1;
    let isBaseFob = fob === 200;

    let rowClass = '';
    let badgeText = '';
    if (isOptimumAbsolute) { rowClass = 'row-optimum'; badgeText = ' <span class="badge-optimum">👑 MÁXIMO MATRIZ</span>'; }
    else if (isParity) { rowClass = 'row-parity'; badgeText = ' <span class="badge-parity">⚖️ PARIDADE (50,84%)</span>'; }
    else if (isSecurity) { rowClass = 'row-security'; badgeText = ' <span class="badge-security">🛡️ SÓCIO 20%</span>'; }
    else if (isBaseFob) { badgeText = ' <span class="badge-optimum" style="background:var(--cyan);color:#000;">BASE</span>'; }

    html += `<tr class="${rowClass}">
      <td><strong>${fmtUsd(fob)}</strong>${badgeText}</td>
      <td style="color:var(--cyan);">${fmtMoney(r1.netExport)}</td>
      <td style="color:var(--emerald);">${fmtMoney(r1.netRemittance)}</td>
      <td style="color:${isOptimumAbsolute ? 'var(--gold)' : 'var(--text-primary)'};font-weight:800;font-size:13px;">${fmtMoney(r1.totalParent)}</td>
      <td><strong>${fmtPct(r1.parentGrossMargin)}</strong></td>
      <td>${fmtMoney(r1.netBrazil)}</td>
      <td style="color:${isSecurity ? 'var(--amber)' : (isParity ? 'var(--cyan)' : 'inherit')};font-weight:700;">${fmtPct(r1.brazilGrossMargin)}</td>
      <td style="color:var(--emerald);font-weight:600;">${fmtMoney(r1.branchRetained)}</td>
      <td style="color:var(--rose);">${fmtMoney(r2.totalParent)}</td>
      <td>${fmtPct(r2.distributorGrossMargin)}</td>
      <td style="color:var(--emerald);font-weight:700;">+${fmtMoney(adv)}</td>
    </tr>`;
  }
  tbody.innerHTML = html;
}

function renderCharts() {
  const width = 540, height = 280;
  const padL = 65, padR = 25, padT = 30, padB = 45;
  const pW = width - padL - padR;
  const pH = height - padT - padB;

  const fobs = [];
  for (let f = 100; f <= 1350; f += 25) fobs.push(f);
  fobs.push(487.56);
  fobs.push(1008.68);
  fobs.push(1346.65);
  fobs.sort((a,b)=>a-b);

  const ptsTotal1 = [], ptsExp1 = [], ptsRemit1 = [], ptsTotal2 = [];
  let maxP = 5500000;

  for (let f of fobs) {
    let r1 = calculateScenario(f, currentSim.price, currentSim.exchange, currentSim.share, 1);
    let r2 = calculateScenario(f, currentSim.price, currentSim.exchange, currentSim.share, 2);
    ptsTotal1.push({ x: f, y: r1.totalParent });
    ptsExp1.push({ x: f, y: r1.netExport });
    ptsRemit1.push({ x: f, y: r1.netRemittance });
    ptsTotal2.push({ x: f, y: r2.totalParent });
  }

  function xMap(f) { return padL + ((f - 100) / (1350 - 100)) * pW; }
  function yMap(p) { return padT + pH - (Math.max(0, p) / maxP) * pH; }

  let dTotal1 = '', dExp1 = '', dRemit1 = '', dTotal2 = '';
  ptsTotal1.forEach((pt, i) => { dTotal1 += (i===0?'M':'L') + `${xMap(pt.x).toFixed(1)},${yMap(pt.y).toFixed(1)} `; });
  ptsExp1.forEach((pt, i) => { dExp1 += (i===0?'M':'L') + `${xMap(pt.x).toFixed(1)},${yMap(pt.y).toFixed(1)} `; });
  ptsRemit1.forEach((pt, i) => { dRemit1 += (i===0?'M':'L') + `${xMap(pt.x).toFixed(1)},${yMap(pt.y).toFixed(1)} `; });
  ptsTotal2.forEach((pt, i) => { dTotal2 += (i===0?'M':'L') + `${xMap(pt.x).toFixed(1)},${yMap(pt.y).toFixed(1)} `; });

  let svgProfit = `
    <line x1="${padL}" y1="${padT+pH}" x2="${width-padR}" y2="${padT+pH}" stroke="rgba(255,255,255,0.1)" stroke-width="1"/>
    <line x1="${padL}" y1="${padT}" x2="${padL}" y2="${padT+pH}" stroke="rgba(255,255,255,0.1)" stroke-width="1"/>
  `;
  for (let pStep = 0; pStep <= maxP; pStep += 1000000) {
    let y = yMap(pStep);
    svgProfit += `<line x1="${padL}" y1="${y}" x2="${width-padR}" y2="${y}" stroke="rgba(255,255,255,0.06)" stroke-dasharray="3,3"/>
                  <text x="${padL-8}" y="${y+4}" fill="#94a3b8" font-size="10" text-anchor="end" font-family="var(--font-mono)">R$ ${(pStep/1e6).toFixed(1)}M</text>`;
  }
  for (let fStep = 200; fStep <= 1300; fStep += 300) {
    let x = xMap(fStep);
    svgProfit += `<line x1="${x}" y1="${padT}" x2="${x}" y2="${padT+pH}" stroke="rgba(255,255,255,0.06)" stroke-dasharray="3,3"/>
                  <text x="${x}" y="${padT+pH+18}" fill="#94a3b8" font-size="10" text-anchor="middle" font-family="var(--font-mono)">$${fStep}</text>`;
  }

  // Paths
  svgProfit += `<path d="${dExp1}" fill="none" stroke="var(--gold)" stroke-width="2" stroke-dasharray="4,4"/>`;
  svgProfit += `<path d="${dRemit1}" fill="none" stroke="var(--emerald)" stroke-width="2" stroke-dasharray="4,4"/>`;
  svgProfit += `<path d="${dTotal2}" fill="none" stroke="var(--rose)" stroke-width="2.5"/>`;
  svgProfit += `<path d="${dTotal1}" fill="none" stroke="var(--cyan)" stroke-width="3.5" stroke-linecap="round"/>`;

  // Highlight Optimum Point C1
  let opt = calculateScenario(1346.65, currentSim.price, currentSim.exchange, currentSim.share, 1);
  let optX = xMap(1346.65);
  let optY = yMap(opt.totalParent);

  svgProfit += `<circle cx="${optX}" cy="${optY}" r="7" fill="var(--gold)" stroke="#fff" stroke-width="2.5"/>`;
  svgProfit += `<text x="${optX-10}" y="${optY-12}" fill="var(--gold)" font-size="11" font-weight="800" text-anchor="end">PONTO ÓTIMO: R$ 5,21M (FOB $1.346)</text>`;

  // Parity Marker
  let par = calculateScenario(487.56, currentSim.price, currentSim.exchange, currentSim.share, 1);
  svgProfit += `<circle cx="${xMap(487.56)}" cy="${yMap(par.totalParent)}" r="5.5" fill="var(--cyan)" stroke="#fff" stroke-width="2"/>`;
  svgProfit += `<text x="${xMap(487.56)}" y="${yMap(par.totalParent)-10}" fill="var(--cyan)" font-size="10" font-weight="700" text-anchor="middle">Paridade: $487,56 (R$ 4,88M)</text>`;

  // Security Marker
  let sec = calculateScenario(1008.68, currentSim.price, currentSim.exchange, currentSim.share, 1);
  svgProfit += `<circle cx="${xMap(1008.68)}" cy="${yMap(sec.totalParent)}" r="5.5" fill="var(--amber)" stroke="#fff" stroke-width="2"/>`;
  svgProfit += `<text x="${xMap(1008.68)}" y="${yMap(sec.totalParent)-10}" fill="var(--amber)" font-size="10" font-weight="700" text-anchor="middle">Sócio 20%: $1.008,68</text>`;

  document.getElementById('chart-profit').innerHTML = svgProfit;

  // Margin Chart
  let svgMargin = `
    <line x1="${padL}" y1="${padT+pH}" x2="${width-padR}" y2="${padT+pH}" stroke="rgba(255,255,255,0.1)" stroke-width="1"/>
    <line x1="${padL}" y1="${padT}" x2="${padL}" y2="${padT+pH}" stroke="rgba(255,255,255,0.1)" stroke-width="1"/>
  `;
  for (let mStep = 0; mStep <= 80; mStep += 20) {
    let y = padT + pH - (mStep / 80) * pH;
    svgMargin += `<line x1="${padL}" y1="${y}" x2="${width-padR}" y2="${y}" stroke="rgba(255,255,255,0.06)" stroke-dasharray="3,3"/>
                  <text x="${padL-8}" y="${y+4}" fill="#94a3b8" font-size="10" text-anchor="end" font-family="var(--font-mono)">${mStep}%</text>`;
  }
  for (let fStep = 200; fStep <= 1300; fStep += 300) {
    let x = xMap(fStep);
    svgMargin += `<text x="${x}" y="${padT+pH+18}" fill="#94a3b8" font-size="10" text-anchor="middle" font-family="var(--font-mono)">$${fStep}</text>`;
  }

  // 20% Security Threshold Line
  let y20 = padT + pH - (20 / 80) * pH;
  svgMargin += `<line x1="${padL}" y1="${y20}" x2="${width-padR}" y2="${y20}" stroke="var(--amber)" stroke-dasharray="5,3" stroke-width="1.5"/>
                <text x="${width-padR}" y="${y20-5}" fill="var(--amber)" font-size="10" font-weight="800" text-anchor="end">PISO MÍNIMO DO SÓCIO (20%)</text>`;

  let m1Pts = [], mSubPts = [], mDistPts = [];
  for (let f of fobs) {
    let r1 = calculateScenario(f, currentSim.price, currentSim.exchange, currentSim.share, 1);
    let r2 = calculateScenario(f, currentSim.price, currentSim.exchange, currentSim.share, 2);
    m1Pts.push({ x: f, y: r1.parentGrossMargin });
    mSubPts.push({ x: f, y: r1.brazilGrossMargin });
    mDistPts.push({ x: f, y: r2.distributorGrossMargin });
  }

  function yMargin(m) { return padT + pH - (Math.max(0, m) / 80) * pH; }
  let dm1 = '', dmSub = '', dmDist = '';
  m1Pts.forEach((pt, i) => { dm1 += (i===0?'M':'L') + `${xMap(pt.x).toFixed(1)},${yMargin(pt.y).toFixed(1)} `; });
  mSubPts.forEach((pt, i) => { dmSub += (i===0?'M':'L') + `${xMap(pt.x).toFixed(1)},${yMargin(pt.y).toFixed(1)} `; });
  mDistPts.forEach((pt, i) => { dmDist += (i===0?'M':'L') + `${xMap(pt.x).toFixed(1)},${yMargin(pt.y).toFixed(1)} `; });

  svgMargin += `<path d="${dm1}" fill="none" stroke="var(--cyan)" stroke-width="3.5" stroke-linecap="round"/>`;
  svgMargin += `<path d="${dmSub}" fill="none" stroke="var(--emerald)" stroke-width="3" stroke-linecap="round"/>`;
  svgMargin += `<path d="${dmDist}" fill="none" stroke="var(--rose)" stroke-width="2" stroke-dasharray="4,4"/>`;

  // Parity Crossover Point (where m1 == mSub at 50.84%)
  svgMargin += `<circle cx="${xMap(487.56)}" cy="${yMargin(50.84)}" r="6" fill="var(--cyan)" stroke="#fff" stroke-width="2.5"/>`;
  svgMargin += `<text x="${xMap(487.56)}" y="${yMargin(50.84)-10}" fill="var(--cyan)" font-size="10" font-weight="800" text-anchor="middle">Paridade de Margens: 50,84% ($487,56)</text>`;

  // 20% partner crossing point
  svgMargin += `<circle cx="${xMap(1008.68)}" cy="${yMargin(20.0)}" r="6" fill="var(--amber)" stroke="#fff" stroke-width="2.5"/>`;
  svgMargin += `<text x="${xMap(1008.68)}" y="${yMargin(20.0)+16}" fill="var(--amber)" font-size="10" font-weight="800" text-anchor="middle">Limite 20% do Sócio ($1.008,68)</text>`;

  document.getElementById('chart-margin').innerHTML = svgMargin;
}

function updateSim() {
  currentSim.fob = Number(document.getElementById('slider-fob').value);
  currentSim.price = Number(document.getElementById('slider-price').value);
  currentSim.exchange = Number(document.getElementById('slider-exchange').value);
  currentSim.share = Number(document.getElementById('slider-share').value);

  document.getElementById('val-fob').textContent = fmtUsd(currentSim.fob);
  document.getElementById('val-price').textContent = fmtMoney(currentSim.price);
  document.getElementById('val-exchange').textContent = fmtMoney(currentSim.exchange).replace('R$ ', 'R$ ');
  document.getElementById('val-share').textContent = currentSim.share + '%';

  const r1 = calculateScenario(currentSim.fob, currentSim.price, currentSim.exchange, currentSim.share, 1);
  const r2 = calculateScenario(currentSim.fob, currentSim.price, currentSim.exchange, currentSim.share, 2);

  document.getElementById('sim-c1-fob-total').textContent = fmtUsd(r1.fobUsd);
  document.getElementById('sim-c1-net-br').textContent = fmtMoney(r1.netBrazil);
  document.getElementById('sim-c1-sub-margin').textContent = fmtPct(r1.brazilGrossMargin);
  document.getElementById('sim-c1-partner-retained').textContent = fmtMoney(r1.branchRetained);
  document.getElementById('sim-c1-net-exp').textContent = fmtMoney(r1.netExport);
  document.getElementById('sim-c1-remit').textContent = fmtMoney(r1.netRemittance);
  document.getElementById('sim-c1-total').textContent = fmtMoney(r1.totalParent);
  document.getElementById('sim-c1-margin').textContent = fmtPct(r1.parentGrossMargin);

  document.getElementById('sim-c2-fob-total').textContent = fmtUsd(r2.fobUsd);
  document.getElementById('sim-c2-net-dist').textContent = fmtMoney(r2.netBrazil);
  document.getElementById('sim-c2-dist-margin').textContent = fmtPct(r2.distributorGrossMargin);
  document.getElementById('sim-c2-net-exp').textContent = fmtMoney(r2.netExport);
  document.getElementById('sim-c2-total').textContent = fmtMoney(r2.totalParent);
  document.getElementById('sim-c2-margin').textContent = fmtPct(r2.parentGrossMargin);

  renderHeatmap();
  renderDetailedTable();
  renderCharts();
}

function setFobQuick(val) {
  document.getElementById('slider-fob').value = val;
  updateSim();
}

function resetSimParams() {
  document.getElementById('slider-fob').value = 200;
  document.getElementById('slider-price').value = 9598.40;
  document.getElementById('slider-exchange').value = 5.60;
  document.getElementById('slider-share').value = 75;
  updateSim();
}

function toggleTheme() {
  const current = document.body.getAttribute('data-theme');
  const target = current === 'light' ? 'dark' : 'light';
  if (target === 'light') {
    document.body.setAttribute('data-theme', 'light');
    document.getElementById('theme-icon').textContent = '☀️';
    document.getElementById('theme-text').textContent = 'Modo Escuro';
  } else {
    document.body.removeAttribute('data-theme');
    document.getElementById('theme-icon').textContent = '🌙';
    document.getElementById('theme-text').textContent = 'Modo Claro';
  }
}

window.addEventListener('DOMContentLoaded', () => {
  renderHeatmap();
  renderDetailedTable();
  renderCharts();
  updateSim();
});
</script>
</body>
</html>
"""

with open('simulador_synvitta/matriz_sensibilidade_synvitta2.html', 'w', encoding='utf-8') as f:
    f.write(html_content)

print("Updated simulador_synvitta/matriz_sensibilidade_synvitta2.html with parity point and 20% partner minimum viable threshold successfully!")
