from __future__ import annotations

import json
import hashlib
from html import escape
from typing import Any


UI_TEXT = {
    "pt": {
        "tagline": "Calculadora local. Os cálculos acontecem neste navegador; nenhum dado é enviado.",
        "inputs": "Premissas editáveis",
        "results": "Resultados atualizados",
        "download_inputs": "Exportar premissas",
        "upload_inputs": "Importar premissas",
        "print_pdf": "Imprimir / Salvar em PDF",
        "export_excel": "Exportar para Excel (.xml)",
        "print_hint": "Na janela de impressão, selecione Salvar como PDF.",
        "reset": "Restaurar valores iniciais",
        "saved": "Premissas salvas neste navegador",
        "saved_error": "Este navegador não permite salvar localmente. Exporte as premissas para transferi-las.",
        "assumptions": "As alterações são locais neste dispositivo. Use Exportar/Importar premissas para transferi-las.",
        "chart": "Comparação de resultados",
        "scenario": "Cenário",
        "import_error": "Arquivo de premissas inválido ou de outro simulador.",
        "import_ok": "Premissas importadas.",
        "export_name": "premissas",
    },
    "en": {
        "tagline": "Local calculator. Calculations run in this browser; no data is uploaded.",
        "inputs": "Editable assumptions",
        "results": "Updated results",
        "download_inputs": "Export assumptions",
        "upload_inputs": "Import assumptions",
        "print_pdf": "Print / Save as PDF",
        "export_excel": "Export to Excel (.xml)",
        "print_hint": "In the print dialog, choose Save as PDF.",
        "reset": "Restore initial values",
        "saved": "Assumptions saved in this browser",
        "saved_error": "This browser cannot save locally. Export assumptions to transfer them.",
        "assumptions": "Changes stay on this device. Use Export/Import assumptions to transfer them.",
        "chart": "Results comparison",
        "scenario": "Scenario",
        "import_error": "Invalid assumptions file or file from another calculator.",
        "import_ok": "Assumptions imported.",
        "export_name": "assumptions",
    },
}


def field(
    key: str,
    label_pt: str,
    label_en: str,
    value: Any,
    group_pt: str,
    group_en: str,
    *,
    kind: str = "number",
    scale: float = 1,
    step: str | float = "any",
    minimum: float | None = None,
    maximum: float | None = None,
    options: list[tuple[str, str, str]] | None = None,
) -> dict[str, Any]:
    return {
        "key": key,
        "label": {"pt": label_pt, "en": label_en},
        "value": value,
        "group": {"pt": group_pt, "en": group_en},
        "kind": kind,
        "scale": scale,
        "step": step,
        "min": minimum,
        "max": maximum,
        "options": options or [],
    }


def _control(field_data: dict[str, Any], language: str) -> str:
    key = escape(field_data["key"], quote=True)
    label = escape(field_data["label"][language])
    kind = field_data["kind"]
    if kind == "select":
        options = []
        for value, label_pt, label_en in field_data["options"]:
            selected = " selected" if str(value) == str(field_data["value"]) else ""
            options.append(
                f'<option value="{escape(str(value), quote=True)}"{selected}>'
                f'{escape(label_pt if language == "pt" else label_en)}</option>'
            )
        class_attr = ' class="mode-choice"' if key in {
            "modo_custos_importacao", "modo_tributos_venda", "modo_opex"
        } else ""
        control = f'<select id="f-{key}" data-key="{key}"{class_attr}>{"".join(options)}</select>'
    elif kind == "checkbox":
        checked = " checked" if field_data["value"] else ""
        control = f'<input id="f-{key}" data-key="{key}" type="checkbox"{checked}>'
        return f'<label class="check-field" for="f-{key}">{control}<span>{label}</span></label>'
    elif kind == "text":
        control = (
            f'<input id="f-{key}" data-key="{key}" type="text" '
            f'value="{escape(str(field_data["value"] or ""), quote=True)}">'
        )
    else:
        scale = float(field_data.get("scale", 1) or 1)
        value = float(field_data["value"] or 0) * scale
        attrs = [
            f'id="f-{key}"', f'data-key="{key}"',
            f'data-scale="{scale}"', 'type="number"',
            f'value="{value:.8f}"', f'step="{escape(str(field_data.get("step", "any")), quote=True)}"',
        ]
        if field_data.get("min") is not None:
            attrs.append(f'min="{field_data["min"]}"')
        if field_data.get("max") is not None:
            attrs.append(f'max="{field_data["max"]}"')
        control = f'<input {" ".join(attrs)}>'
    wrapper_class = "field mode-field" if kind == "select" and field_data["key"] in {
        "modo_custos_importacao", "modo_tributos_venda", "modo_opex"
    } else "field"
    return f'<label class="{wrapper_class}" for="f-{key}"><span>{label}</span>{control}</label>'


def build_calculator_html(
    *,
    model_id: str,
    language: str,
    title: str,
    fields: list[dict[str, Any]],
    calculation_js: str,
) -> str:
    language = "en" if language == "en" else "pt"
    text = UI_TEXT[language]
    groups: dict[str, list[dict[str, Any]]] = {}
    group_names: dict[str, str] = {}
    for item in fields:
        group_key = item["group"][language]
        groups.setdefault(group_key, []).append(item)
        group_names[group_key] = group_key
    sections = []
    for index, (group, items) in enumerate(groups.items()):
        controls = "".join(_control(item, language) for item in items)
        opened = " open" if index == 0 else ""
        sections.append(
            f'<details class="input-group"{opened}><summary>{escape(group)}</summary>'
            f'<div class="field-grid">{controls}</div></details>'
        )
    defaults = {item["key"]: item["value"] for item in fields}
    defaults_json = json.dumps(defaults, ensure_ascii=False, separators=(",", ":"))
    defaults_json = defaults_json.replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")
    save_key = f"synvitta-standalone:{model_id}:{hashlib.sha256(defaults_json.encode('utf-8')).hexdigest()[:12]}"
    visibility_rules: dict[str, tuple[str, str]] = {}
    if model_id == "synvitta2":
        detailed_import_fields = [
            "aliq_ii", "aliq_ipi", "aliq_pis", "aliq_cofins", "aliq_cbs", "aliq_ibs",
            "multiplo_base_cbs_ibs", "aliq_icms", "aliq_afrmm", "antidumping_brl",
            "despesas_na_base_icms", "custo_armazenagem", "custo_capatazia", "custo_despachante",
            "taxa_siscomex", "taxas_terminal", "honorarios_agente_carga", "licencas_inspecao",
            "outras_despesas_importacao", "credita_ipi", "credita_pis", "credita_cofins",
            "credita_cbs_ibs", "credita_icms",
        ]
        for key in detailed_import_fields:
            visibility_rules[key] = ("modo_custos_importacao", "Detalhado")
        visibility_rules["custo_importacao_consolidado_brl"] = ("modo_custos_importacao", "Consolidado")
        for key in ("aliq_icms_venda", "aliq_pis_venda", "aliq_cofins_venda", "aliq_outros_venda"):
            visibility_rules[key] = ("modo_tributos_venda", "Detalhado")
        visibility_rules["aliq_venda_consolidada"] = ("modo_tributos_venda", "Consolidado")
        detailed_opex_fields = [
            "opex_pessoal", "opex_aluguel", "opex_utilidades", "opex_servicos_profissionais",
            "opex_comercial_marketing", "opex_sistemas", "opex_seguros", "opex_depreciacao",
            "opex_administrativo", "opex_outros",
        ]
        for key in detailed_opex_fields:
            visibility_rules[key] = ("modo_opex", "Detalhado")
        visibility_rules["opex_consolidado_mensal"] = ("modo_opex", "Consolidado")
    visibility_rules_json = json.dumps(visibility_rules, ensure_ascii=False, separators=(",", ":"))
    safe_model = escape(model_id, quote=True)
    safe_title = escape(title)
    return f'''<!doctype html>
<html lang="{"en" if language == "en" else "pt-BR"}">
<head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="application-name" content="{safe_model}"><title>{safe_title}</title>
<style>
:root{{--ink:#18364a;--text:#203040;--muted:#52606d;--line:#d9e1e8;--paper:#fff;--canvas:#f3f6f7;--blue:#2878a0;--green:#4e9a72;--orange:#d78a36}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--canvas);color:var(--text);font:15px/1.45 "Segoe UI",Arial,sans-serif}}
header{{background:var(--ink);color:white;padding:20px max(20px,calc((100vw - 1500px)/2));display:flex;align-items:center;justify-content:space-between;gap:18px}}
header h1{{font-size:22px;line-height:1.2;margin:0}}header p{{font-size:12px;color:#d5e1e7;margin:5px 0 0}}#save-status{{font-size:12px;white-space:nowrap}}
.layout{{max-width:1540px;padding:20px;margin:auto;display:grid;grid-template-columns:minmax(300px,380px) minmax(0,1fr);gap:20px;align-items:start}}
aside,.results{{min-width:0}}.panel-title{{font-size:17px;color:var(--ink);margin:0 0 12px}}
.input-group,.output-section{{background:var(--paper);border:1px solid var(--line);border-radius:6px;margin-bottom:10px}}
.input-group summary{{cursor:pointer;padding:12px 14px;color:var(--ink);font-weight:700}}.field-grid{{display:grid;grid-template-columns:1fr 1fr;gap:10px;padding:0 12px 13px}}
.field{{display:grid;gap:4px;font-size:12px;color:var(--muted);min-width:0}}.field[hidden],.check-field[hidden]{{display:none!important}}.field input,.field select{{width:100%;min-width:0;border:1px solid #bac7cf;border-radius:4px;padding:8px;background:white;color:var(--text);font:inherit;font-size:14px}}
.field.mode-field{{grid-column:1/-1;padding:10px;border:2px solid var(--blue);border-radius:5px;background:#edf5f8;color:var(--ink);font-weight:700}}.mode-field select{{border:2px solid var(--blue);font-weight:700;color:var(--ink)}}
.field.locked,.check-field.locked{{opacity:.48;filter:grayscale(.75);cursor:not-allowed}}.field.locked input,.field.locked select{{background:#e7ecef;color:#59656b;cursor:not-allowed}}.check-field.locked input{{cursor:not-allowed}}
.check-field{{grid-column:span 2;display:flex;align-items:center;gap:8px;color:var(--text);font-size:13px}}.check-field input{{width:17px;height:17px;accent-color:var(--blue)}}
.actions{{display:grid;grid-template-columns:1fr 1fr;gap:8px;margin:12px 0}}button,.file-label{{border:1px solid var(--blue);background:var(--blue);color:#fff;padding:9px 10px;border-radius:4px;font:inherit;font-size:13px;font-weight:700;text-align:center;cursor:pointer}}button.secondary,.file-label.secondary{{background:#fff;color:var(--blue)}}button:hover,.file-label:hover{{filter:brightness(.94)}}#import-file{{display:none}}.note{{color:var(--muted);font-size:12px;margin:8px 2px}}
.output-section{{padding:14px;overflow:hidden}}.output-section h2{{font-size:17px;color:var(--ink);margin:0 0 12px}}.kpis{{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:10px}}
.kpi{{border-bottom:2px solid var(--blue);padding:8px 5px;min-width:0}}.kpi span{{display:block;font-size:11px;color:var(--muted)}}.kpi strong{{display:block;color:var(--ink);font-size:15px;margin-top:4px;overflow-wrap:anywhere}}
.table-wrap{{overflow-x:auto}}table{{border-collapse:collapse;width:100%;min-width:680px;font-size:12px}}th{{background:var(--ink);color:#fff;text-align:left}}th,td{{padding:8px;border:1px solid var(--line);vertical-align:top}}tbody tr:nth-child(even){{background:#f0f5f7}}td.num{{text-align:right;white-space:nowrap}}
.chart-list{{display:grid;gap:12px}}.chart-row{{display:grid;grid-template-columns:minmax(120px,190px) minmax(80px,1fr) minmax(110px,150px);gap:8px;align-items:center;font-size:12px}}.chart-row label{{color:var(--muted)}}.bar-track{{height:13px;background:#e7edf0;border-radius:3px;overflow:hidden}}.bar{{height:100%;min-width:1px;border-radius:3px}}.chart-value{{text-align:right;font-variant-numeric:tabular-nums;white-space:nowrap}}
#error-box{{display:none;background:#fff1ed;border-left:4px solid #b94b32;padding:10px;margin-bottom:10px;color:#792f22}}
@media(max-width:900px){{.layout{{grid-template-columns:1fr;padding:12px}}header{{padding:16px;align-items:flex-start;flex-direction:column}}.kpis{{grid-template-columns:repeat(2,minmax(0,1fr))}}}}
@media(max-width:520px){{.field-grid{{grid-template-columns:1fr}}.check-field{{grid-column:span 1}}.chart-row{{grid-template-columns:minmax(100px,1fr) 1fr;gap:5px}}.bar-track{{grid-column:1/-1;grid-row:2}}.chart-value{{grid-column:2;grid-row:1}}.actions{{grid-template-columns:1fr}}}}
@media print{{@page{{size:landscape;margin:12mm}}body{{background:#fff}}header{{padding:0 0 12px;background:#fff;color:var(--ink);box-shadow:none}}header p,#save-status{{display:none}}.layout{{display:block;max-width:none;padding:0}}aside,.actions,.note,.results>.panel-title{{display:none!important}}.results{{width:100%}}.output-section{{break-inside:avoid;border:0;padding:8px 0;overflow:visible}}.table-wrap{{overflow:visible}}table{{min-width:0;font-size:9px}}th,td{{padding:4px}}.chart-row{{break-inside:avoid}}}}
</style></head>
<body>
<header><div><h1>{safe_title}</h1><p>{escape(text["tagline"])}</p></div><span id="save-status" aria-live="polite"></span></header>
<div class="layout"><aside><h2 class="panel-title">{escape(text["inputs"])}</h2><form id="input-form">{"".join(sections)}</form>
<div class="actions"><button id="export-inputs" type="button">{escape(text["download_inputs"])}</button>
<label class="file-label secondary" for="import-file">{escape(text["upload_inputs"])}</label>
<input id="import-file" type="file" accept="application/json,.json">
<button class="secondary" id="print-pdf" type="button">{escape(text["print_pdf"])}</button>
<button class="secondary" id="export-results-excel" type="button">{escape(text["export_excel"])}</button>
<button class="secondary" id="reset-inputs" type="button">{escape(text["reset"])}</button></div>
<p class="note">{escape(text["assumptions"])} {escape(text["print_hint"])}</p></aside>
<main class="results"><h2 class="panel-title">{escape(text["results"])}</h2><div id="error-box" role="alert"></div>
<div id="results-content" aria-live="polite"></div></main></div>
<script id="initial-values" type="application/json">{defaults_json}</script>
<script>
"use strict";
const MODEL_ID={json.dumps(model_id)};
const LANGUAGE={json.dumps(language)};
const DEFAULTS=JSON.parse(document.getElementById("initial-values").textContent);
const VISIBILITY_RULES={visibility_rules_json};
const SAVE_KEY={json.dumps(save_key)};
const TXT={json.dumps(text, ensure_ascii=False)};
{calculation_js}
function esc(value){{return String(value??"").replace(/[&<>"']/g,char=>({{"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}}[char]));}}
function readInputs(){{const values={{}};document.querySelectorAll("[data-key]").forEach(input=>{{const key=input.dataset.key;if(input.type==="checkbox")values[key]=input.checked;else if(input.type==="number")values[key]=Number(input.value||0)/Number(input.dataset.scale||1);else values[key]=input.value;}});return values;}}
function applyInputs(values){{document.querySelectorAll("[data-key]").forEach(input=>{{const key=input.dataset.key;if(!(key in values))return;if(input.type==="checkbox")input.checked=Boolean(values[key]);else if(input.type==="number")input.value=String(Number(values[key]||0)*Number(input.dataset.scale||1));else input.value=String(values[key]??"");}});}}
function updateConditionalInputs(values){{for(const [key,condition] of Object.entries(VISIBILITY_RULES)){{const input=document.querySelector(`[data-key="${{key}}"]`);const wrapper=input?.closest("label");if(!input||!wrapper)continue;const locked=String(values[condition[0]])!==condition[1];input.disabled=locked;wrapper.classList.toggle("locked",locked);}}}}
function saveInputs(values){{try{{localStorage.setItem(SAVE_KEY,JSON.stringify(values));document.getElementById("save-status").textContent=TXT.saved;}}catch(error){{document.getElementById("save-status").textContent=TXT.saved_error;}}}}
function downloadBlob(filename,blob){{const url=URL.createObjectURL(blob);const link=document.createElement("a");link.href=url;link.download=filename;link.hidden=true;document.body.appendChild(link);link.click();link.remove();setTimeout(()=>URL.revokeObjectURL(url),1000);}}
function cell(value){{return `<td>${{esc(value)}}</td>`;}}
function renderTable(table){{return `<section class="output-section"><h2>${{esc(table.title)}}</h2><div class="table-wrap"><table><thead><tr>${{table.headers.map(header=>`<th>${{esc(header)}}</th>`).join("")}}</tr></thead><tbody>${{table.rows.map(row=>`<tr>${{row.map(cell).join("")}}</tr>`).join("")}}</tbody></table></div></section>`;}}
function renderChart(chart){{const max=Math.max(1,...chart.series.flatMap(series=>series.values.map(value=>Math.abs(Number(value)||0))));return `<section class="output-section"><h2>${{esc(chart.title)}}</h2><div class="chart-list">${{chart.series.map(series=>series.values.map((value,index)=>`<div class="chart-row"><label>${{esc(series.label)}} · ${{esc(chart.categories[index])}}</label><div class="bar-track"><div class="bar" style="width:${{Math.max(1,Math.abs(value)/max*100)}}%;background:${{esc(series.color)}}"></div></div><strong class="chart-value">${{esc(series.formatted[index])}}</strong></div>`).join("")).join("")}}</div></section>`;}}
function render(result){{const kpis=`<section class="output-section"><h2>${{esc(result.summaryTitle)}}</h2><div class="kpis">${{result.summary.map(item=>`<div class="kpi"><span>${{esc(item.label)}}</span><strong>${{esc(item.value)}}</strong></div>`).join("")}}</div></section>`;document.getElementById("results-content").innerHTML=kpis+result.charts.map(renderChart).join("")+result.tables.map(renderTable).join("");window.CURRENT_CALCULATION=result;document.getElementById("error-box").style.display="none";}}
function xmlEscape(value){{return String(value??"").replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;").replace(/\"/g,"&quot;").replace(/'/g,"&apos;");}}
function safeSheetName(value,index){{let name=String(value||`Results ${{index+1}}`);for(const invalid of [String.fromCharCode(92),"/","?","*","[","]",":"])name=name.split(invalid).join(" ");name=name.trim().slice(0,31);return name||`Results ${{index+1}}`;}}
function makeExcelWorkbook(result){{const sheets=[{{name:LANGUAGE==="pt"?"Resumo":"Summary",rows:[[result.summaryTitle],...result.summary.map(item=>[item.label,item.value])]}},...result.tables.map((table,index)=>({{name:safeSheetName(table.title,index),rows:[[table.title],table.headers,...table.rows]}}))];const used=new Set();const worksheetXml=sheets.map((sheet,index)=>{{let name=safeSheetName(sheet.name,index);let unique=name;let suffix=2;while(used.has(unique)){{unique=(name.slice(0,27)+" "+suffix++).slice(0,31);}}used.add(unique);const rows=sheet.rows.map(row=>`<Row>${{row.map(value=>`<Cell><Data ss:Type="String">${{xmlEscape(value)}}</Data></Cell>`).join("")}}</Row>`).join("");return `<Worksheet ss:Name="${{xmlEscape(unique)}}"><Table>${{rows}}</Table></Worksheet>`;}}).join("");return `<?xml version="1.0"?><Workbook xmlns="urn:schemas-microsoft-com:office:spreadsheet" xmlns:o="urn:schemas-microsoft-com:office:office" xmlns:x="urn:schemas-microsoft-com:office:excel" xmlns:ss="urn:schemas-microsoft-com:office:spreadsheet"><Styles><Style ss:ID="Default" ss:Name="Normal"><Alignment ss:Vertical="Bottom"/></Style></Styles>${{worksheetXml}}</Workbook>`;}}
function update(){{try{{const values=readInputs();updateConditionalInputs(values);saveInputs(values);render(calculate(values,LANGUAGE));}}catch(error){{const box=document.getElementById("error-box");box.textContent=error.message||String(error);box.style.display="block";}}}}
document.getElementById("input-form").addEventListener("input",update);
document.getElementById("input-form").addEventListener("change",update);
document.getElementById("reset-inputs").addEventListener("click",()=>{{try{{localStorage.removeItem(SAVE_KEY);}}catch(error){{}}applyInputs(DEFAULTS);update();}});
document.getElementById("export-inputs").addEventListener("click",()=>{{const payload={{model:MODEL_ID,version:1,values:readInputs()}};const blob=new Blob([JSON.stringify(payload,null,2)],{{type:"application/json"}});downloadBlob(MODEL_ID+"_"+TXT.export_name+".json",blob);}});
document.getElementById("print-pdf").addEventListener("click",()=>window.print());
document.getElementById("export-results-excel").addEventListener("click",()=>{{const workbook=makeExcelWorkbook(window.CURRENT_CALCULATION);const blob=new Blob([workbook],{{type:"application/vnd.ms-excel;charset=utf-8"}});downloadBlob(MODEL_ID+"_"+TXT.export_name+".xml",blob);}});
document.getElementById("import-file").addEventListener("change",async event=>{{const file=event.target.files[0];if(!file)return;try{{const payload=JSON.parse(await file.text());if(payload.model!==MODEL_ID||!payload.values)throw Error(TXT.import_error);applyInputs(payload.values);update();document.getElementById("save-status").textContent=TXT.import_ok;}}catch(error){{const box=document.getElementById("error-box");box.textContent=TXT.import_error;box.style.display="block";}}event.target.value="";}});
try{{const saved=JSON.parse(localStorage.getItem(SAVE_KEY)||"null");if(saved)applyInputs(saved);}}catch(error){{}}
update();
</script></body></html>'''


def synvitta_calculation_js() -> str:
        return r'''function calculate(v, lang) {
    const pt = lang === "pt";
    const n = key => Number(v[key] || 0);
    const label = (ptText, enText) => pt ? ptText : enText;
    const money = (value, currency = "BRL") => {
        const number = new Intl.NumberFormat(pt ? "pt-BR" : "en-US", {
            minimumFractionDigits: 2, maximumFractionDigits: 2
        }).format(Number(value) || 0);
        return (currency === "USD" ? "USD " : (pt ? "R$ " : "BRL ")) + number;
    };
    const percent = value => new Intl.NumberFormat(pt ? "pt-BR" : "en-US", {
        minimumFractionDigits: 2, maximumFractionDigits: 2
    }).format(Number(value) || 0) + "%";
    const landed_cost_ratio = (landed, revenue) => landed > 0
        ? (revenue / landed).toFixed(2).replace(".", pt ? "," : ".") + "x"
        : label("N/A", "N/A");
    const quantity = Math.max(1, n("numero_kits"));
    const exchange = Math.max(0.01, n("cambio"));
    const volumeFactor = quantity / 1000;
    const revenue = n("faturamento_base") * volumeFactor;
    const cogs = n("cogs_usd_base") * volumeFactor * exchange;
    const fob1Usd = n("fob_usd_base") * volumeFactor;
    const operatorCost = revenue * n("pct_operador_log");
    const logistics = n("pct_logistica");
    const taxBrRate = n("pct_imposto_br");
    const usTaxRate = n("pct_imposto_eua");
    const remittanceFactor = (1 - n("pct_retencao_div")) * (1 - n("pct_taxa_envio"));
    function localProfit(fobUsd) {
        const landed = fobUsd * exchange * (1 + logistics);
        const operating = revenue - landed - operatorCost - n("opex_trimestral");
        const tax = Math.max(operating, 0) * taxBrRate;
        return { landed, operating, tax, net: operating - tax };
    }
    function exportProfit(fobUsd) {
        const gross = fobUsd * exchange - cogs;
        return gross - Math.max(gross, 0) * usTaxRate;
    }
    const local1 = localProfit(fob1Usd);
    const export1 = exportProfit(fob1Usd);
    const matrix1 = local1.net * n("pct_participacao_matriz_c1");
    const branch1 = local1.net * (1 - n("pct_participacao_matriz_c1"));
    const global1 = export1 + local1.net - Math.max(matrix1, 0) * (1 - remittanceFactor);
    const fob2Usd = Math.max(0, n("fob_usd_c2"));
    const local2 = localProfit(fob2Usd);
    const export2 = exportProfit(fob2Usd);
    const kits = new Intl.NumberFormat(pt ? "pt-BR" : "en-US", {maximumFractionDigits: 0}).format(quantity);
    const scenarioNames = pt
        ? ["1. Subsidiária Controlada", "2. Distribuidor Independente"]
        : ["1. Controlled Subsidiary", "2. Independent Distributor"];
    const comparisonHeaders = [
        label("Cenário Societário / Comercial", "Business / ownership scenario"),
        label("FOB do Cenário (USD)", "Scenario FOB (USD)"),
        label("Lucro Matriz EUA - Exportação (R$)", "U.S. parent export profit (BRL)"),
        label("Margem Matriz EUA s/ FOB (%)", "U.S. parent margin on FOB (%)"),
        label("Lucro Matriz Brasil (R$)", "Brazil parent profit (BRL)"),
        label("Margem Matriz Brasil s/ Faturamento (%)", "Brazil parent margin on revenue (%)"),
        label("Lucro Total da Matriz (R$)", "Total parent company profit (BRL)"),
        label("Lucro Filial / Empresa Local Brasil (R$)", "Brazil branch / local company profit (BRL)"),
        label("Margem Filial / Local s/ Faturamento (%)", "Branch / local company margin on revenue (%)"),
        label("Lucro Global Consolidado (R$)", "Consolidated global profit (BRL)"),
        label("Lucro Global por Kit (R$)", "Global profit per kit (BRL)"),
        label("Markup s/ Landed Cost (x)", "Markup / landed cost (x)")
    ];
    const rows = [
        [scenarioNames[0], money(fob1Usd, "USD"), money(export1), percent(fob1Usd ? export1 / (fob1Usd * exchange) * 100 : 0),
            money(matrix1), percent(revenue ? matrix1 / revenue * 100 : 0), money(export1 + matrix1),
            money(branch1), percent(revenue ? branch1 / revenue * 100 : 0), money(global1), money(global1 / quantity),
            landed_cost_ratio(local1.landed, revenue, pt)],
        [scenarioNames[1], money(fob2Usd, "USD"), money(export2), percent(fob2Usd ? export2 / (fob2Usd * exchange) * 100 : 0),
            label("N/A", "N/A"), label("N/A", "N/A"), money(export2), money(local2.net),
            percent(revenue ? local2.net / revenue * 100 : 0), label("N/A", "N/A"), label("N/A", "N/A"),
            landed_cost_ratio(local2.landed, revenue, pt)]
    ];
    const summaryTitle = label("Resumo da DRE Operacional (Brasil)", "Brazil operating income statement summary");
    const summary = [
        {label: label("Faturamento Bruto (R$)", "Gross revenue (BRL)"), value: money(revenue)},
        {label: label("Acomodação / Operador (R$)", "Logistics operator (BRL)"), value: money(operatorCost)},
        {label: label("Landed Cost (R$)", "Landed cost (BRL)"), value: money(local1.landed)},
        {label: label("Lucro Operacional (R$)", "Operating profit (BRL)"), value: money(local1.operating)},
        {label: label(`Impostos BR (${percent(taxBrRate * 100)})`, `Brazil taxes (${percent(taxBrRate * 100)})`), value: money(local1.tax)},
        {label: label("Lucro Líquido BR (100%)", "Brazil net profit (100%)"), value: money(local1.net)},
        {label: label("Kits considerados", "Kits modeled"), value: kits}
    ];
    const chart = {
        title: label("Lucro por cenário e entidade", "Profit by scenario and entity"),
        categories: [label("Cenário 1", "Scenario 1"), label("Cenário 2", "Scenario 2")],
        series: [
            {label: label("Lucro líquido da exportação da matriz", "U.S. parent net export profit"), color: "#2878a0", values: [export1, export2], formatted: [money(export1), money(export2)]},
            {label: label("Lucro Matriz Brasil", "Brazil parent profit"), color: "#d78a36", values: [matrix1, 0], formatted: [money(matrix1), "N/A"]},
            {label: label("Resultado retido na filial/local", "Profit retained by branch/local company"), color: "#4e9a72", values: [branch1, local2.net], formatted: [money(branch1), money(local2.net)]}
        ]
    };
    const dreHeaders = [label("Conta", "Account"), label("Cenário 1", "Scenario 1"), label("Cenário 2", "Scenario 2")];
    const dreRows = [
        [label("Receita bruta", "Gross revenue"), money(revenue), money(revenue)],
        [label("Landed cost", "Landed cost"), money(-local1.landed), money(-local2.landed)],
        [label("Acomodação / operador", "Logistics operator"), money(-operatorCost), money(-operatorCost)],
        [label("OpEx local", "Local operating expenses"), money(-n("opex_trimestral")), money(-n("opex_trimestral"))],
        [label("Lucro operacional", "Operating profit"), money(local1.operating), money(local2.operating)],
        [label("Impostos Brasil", "Brazil taxes"), money(-local1.tax), money(-local2.tax)],
        [label("Lucro líquido Brasil", "Brazil net profit"), money(local1.net), money(local2.net)],
        [label("Lucro líquido exportação da matriz", "Parent company net export profit"), money(export1), money(export2)],
        [label("Lucro global consolidado", "Consolidated global profit"), money(global1), label("N/A", "N/A")]
    ];
    return {
        summaryTitle,
        summary,
        charts: [chart],
        tables: [
            {title: label("Comparativo Executivo - Dois Cenários", "Executive comparison - Two scenarios"), headers: comparisonHeaders, rows},
            {title: label("DRE operacional Brasil", "Brazil operating income statement"), headers: dreHeaders, rows: dreRows}
        ]
    };
}'''


def synvitta2_calculation_js() -> str:
        return r'''function calculate(v, lang) {
    const pt = lang === "pt";
    const n = key => Number(v[key] || 0);
    const s = key => String(v[key] ?? "");
    const label = (ptText, enText) => pt ? ptText : enText;
    const money = value => {
        const number = new Intl.NumberFormat(pt ? "pt-BR" : "en-US", {
            minimumFractionDigits: 2, maximumFractionDigits: 2
        }).format(Number(value) || 0);
        return (pt ? "R$ " : "BRL ") + number;
    };
    const usd = value => "USD " + new Intl.NumberFormat(pt ? "pt-BR" : "en-US", {
        minimumFractionDigits: 2, maximumFractionDigits: 2
    }).format(Number(value) || 0);
    const pct = value => new Intl.NumberFormat(pt ? "pt-BR" : "en-US", {
        minimumFractionDigits: 2, maximumFractionDigits: 2
    }).format(Number(value) || 0) + "%";
    const rate = key => n(key) / 100;
    const quantity = Math.max(1, n("quantidade"));
    const sold1 = Math.max(0, Math.min(quantity, n("quantidade_vendida")));
    const sold2 = Math.max(0, Math.min(quantity, n("quantidade_vendida_c2")));
    const exchange = Math.max(0.01, n("cambio"));
    const period = Math.max(1, n("meses_operacao"));
    const boxes = Math.ceil(quantity / Math.max(1, n("kits_por_volume")));
    const volumeM3 = boxes * n("comprimento") * n("largura") * n("altura") / 1000000;
    const volumetricWeight = boxes * n("comprimento") * n("largura") * n("altura") / Math.max(1, n("divisor_volumetrico"));
    const chargeableWeight = Math.max(n("peso_bruto_total"), volumetricWeight);
    const wm = Math.max(volumeM3, n("peso_bruto_total") / 1000);
    let freightUsd = n("frete_usd");
    if (s("calculo_frete") === "Tarifa marítima por W/M") freightUsd = n("tarifa_wm") * wm;
    else if (s("calculo_frete") === "Tarifa por kg taxável") freightUsd = n("tarifa_frete_kg") * chargeableWeight;
    else if (s("calculo_frete") === "Tarifa por m³") freightUsd = n("tarifa_m3") * volumeM3;
    const freightBrl = freightUsd * exchange;
    const detailedImport = s("modo_custos_importacao") === "Detalhado";
    const dispatchCosts = [
        ["Armazenagem", "Warehousing", "custo_armazenagem"],
        ["Capatazia / terminal", "Cargo handling / terminal", "custo_capatazia"],
        ["Despachante aduaneiro", "Customs broker", "custo_despachante"],
        ["Taxa Siscomex", "Siscomex fee", "taxa_siscomex"],
        ["Taxas portuárias / aeroportuárias", "Port / airport fees", "taxas_terminal"],
        ["Honorários / agente de carga", "Forwarder / freight agent fees", "honorarios_agente_carga"],
        ["Licenças, análise e inspeção", "Licenses, testing, and inspection", "licencas_inspecao"],
        ["Outras despesas de importação", "Other import expenses", "outras_despesas_importacao"]
    ];
    function calculateImport(fobPerKit) {
        const fobUsd = fobPerKit * quantity;
        const insuranceBrl = (fobUsd + freightUsd) * exchange * rate("seguro_pct");
        const customsValue = fobUsd * exchange + freightBrl + insuranceBrl + n("ajustes_aduaneiros_brl");
        const ii = detailedImport ? customsValue * rate("aliq_ii") : 0;
        const ipi = detailedImport ? (customsValue + ii + n("antidumping_brl")) * rate("aliq_ipi") : 0;
        const pisImport = detailedImport ? customsValue * rate("aliq_pis") : 0;
        const cofinsImport = detailedImport ? customsValue * rate("aliq_cofins") : 0;
        const cbsIbsImport = detailedImport ? customsValue * n("multiplo_base_cbs_ibs") * (rate("aliq_cbs") + rate("aliq_ibs")) : 0;
        const afrmm = detailedImport && s("modal") === "Marítimo" ? freightBrl * rate("aliq_afrmm") : 0;
        const icmsBaseBefore = customsValue + ii + ipi + pisImport + cofinsImport + afrmm + (detailedImport ? n("antidumping_brl") + n("despesas_na_base_icms") : 0);
        const icmsBase = detailedImport && rate("aliq_icms") < 1 ? icmsBaseBefore / (1 - rate("aliq_icms")) : 0;
        const icms = icmsBase * rate("aliq_icms");
        const dispatchTotal = detailedImport ? dispatchCosts.reduce((sum, row) => sum + n(row[2]), 0) : 0;
        const importTaxes = detailedImport
            ? ii + ipi + pisImport + cofinsImport + cbsIbsImport + icms + afrmm + n("antidumping_brl")
            : n("custo_importacao_consolidado_brl");
        const credits = detailedImport
            ? (v.credita_ipi ? ipi : 0) + (v.credita_pis ? pisImport : 0) + (v.credita_cofins ? cofinsImport : 0)
                + (v.credita_cbs_ibs ? cbsIbsImport : 0) + (v.credita_icms ? icms : 0)
            : 0;
        const inventoryCost = Math.max(customsValue + importTaxes + dispatchTotal + n("frete_interno_brl") - credits, 0);
        const composition = detailedImport
            ? [
                ["Valor aduaneiro", "Customs value", customsValue],
                ["II", "Import duty (II)", ii], ["IPI-importação", "Import IPI", ipi],
                ["PIS-importação", "Import PIS", pisImport], ["Cofins-importação", "Import Cofins", cofinsImport],
                ["CBS/IBS-importação estimados", "Estimated import CBS/IBS", cbsIbsImport],
                ["ICMS-importação", "Import ICMS", icms], ["AFRMM", "Merchant Marine Tax (AFRMM)", afrmm],
                ["Antidumping / medidas compensatórias", "Anti-dumping / countervailing duties", n("antidumping_brl")],
                ...dispatchCosts.map(row => [row[0], row[1], n(row[2])]),
                ["Frete interno", "Domestic freight", n("frete_interno_brl")],
                ["Créditos tributários estimados", "Estimated tax credits", -credits],
                ["Custo de aquisição do estoque", "Inventory acquisition cost", inventoryCost]
            ]
            : [
                ["Valor aduaneiro", "Customs value", customsValue],
                ["Tributos e despesas aduaneiras consolidados", "Consolidated import taxes and customs expenses", importTaxes],
                ["Frete interno", "Domestic freight", n("frete_interno_brl")],
                ["Créditos tributários estimados", "Estimated tax credits", -credits],
                ["Custo de aquisição do estoque", "Inventory acquisition cost", inventoryCost]
            ];
        const outlay = customsValue + importTaxes + dispatchTotal + n("frete_interno_brl");
        return {customsValue, importTaxes, dispatchTotal, credits, inventoryCost, outlay, composition};
    }
    const import1 = calculateImport(n("preco_fob_base"));
    const import2 = calculateImport(n("preco_fob_c2"));
    const salesTaxRate = s("modo_tributos_venda") === "Detalhado"
        ? rate("aliq_icms_venda") + rate("aliq_pis_venda") + rate("aliq_cofins_venda") + rate("aliq_outros_venda")
        : rate("aliq_venda_consolidada");
    const monthlyOpex = s("modo_opex") === "Detalhado"
        ? ["opex_pessoal", "opex_aluguel", "opex_utilidades", "opex_servicos_profissionais", "opex_comercial_marketing", "opex_sistemas", "opex_seguros", "opex_depreciacao", "opex_administrativo", "opex_outros"].reduce((sum, key) => sum + n(key), 0)
        : n("opex_consolidado_mensal");
    const isPresumedProfit = s("regime_tributario") === "Lucro Presumido";
    function calculateScenario(fobPerKit, sold, pricePerKit, opexFactor, parentShare, importData) {
        const fobUsd = fobPerKit * quantity;
        const cogs = importData.inventoryCost / quantity * sold;
        const grossRevenue = pricePerKit * sold;
        const commercialRevenue = Math.max(grossRevenue - n("devolucoes_descontos"), 0);
        const salesTaxes = commercialRevenue * salesTaxRate;
        const netRevenue = commercialRevenue - salesTaxes;
        const opex = monthlyOpex * period * opexFactor;
        const variableOperator = netRevenue * rate("operador_pct");
        const operatingProfit = netRevenue - cogs - variableOperator - opex;
        const profitBeforeTax = operatingProfit - n("juros_brl");
        let irpj = 0, additionalIrpj = 0, csll = 0, brazilTax = 0;
        if (isPresumedProfit) {
            irpj = commercialRevenue * rate("aliq_irpj_faturamento");
            additionalIrpj = Math.max(commercialRevenue * rate("base_presumida_irpj") - n("limite_adicional_irpj_mensal") * period, 0) * rate("aliq_adicional_irpj");
            csll = commercialRevenue * rate("aliq_csll_faturamento");
            brazilTax = irpj + additionalIrpj + csll;
        } else {
            brazilTax = Math.max(profitBeforeTax, 0) * rate("aliq_ir_csll");
            irpj = brazilTax;
        }
        const netBrazil = profitBeforeTax - brazilTax;
        const manufacturingCost = n("custo_fabricacao_usd") * quantity * exchange;
        const exportProfitBeforeTax = fobUsd * exchange - manufacturingCost - n("opex_matriz_usd") * exchange;
        const floridaTax = Math.max(exportProfitBeforeTax, 0) * rate("rateio_fl") * rate("aliq_fl");
        const federalTax = Math.max(exportProfitBeforeTax - floridaTax, 0) * rate("aliq_federal_eua");
        const netExportProfit = exportProfitBeforeTax - floridaTax - federalTax;
        const parentBrazilProfit = Math.max(netBrazil, 0) * parentShare;
        const dividendWithholding = parentBrazilProfit * rate("retencao_dividendos");
        const remittanceAfterTax = parentBrazilProfit - dividendWithholding;
        const remittanceCost = remittanceAfterTax * rate("custo_remessa");
        const netRemittance = remittanceAfterTax - remittanceCost;
        const branchRetained = netBrazil - parentBrazilProfit;
        const globalProfit = netExportProfit + netBrazil - parentBrazilProfit + netRemittance;
        const dre = [
            ["Receita bruta", "Gross revenue", grossRevenue],
            ["Devoluções, abatimentos e descontos", "Returns, allowances, and discounts", -Math.min(n("devolucoes_descontos"), grossRevenue)],
            ["Tributos sobre vendas", "Sales taxes", -salesTaxes],
            ["Receita líquida", "Net revenue", netRevenue],
            ["Custo das mercadorias vendidas (CMV)", "Cost of goods sold (COGS)", -cogs],
            ["Operação / armazenagem variável", "Variable operations / warehousing", -variableOperator],
            ["Opex fixo do período", "Fixed operating expenses for the period", -opex],
            ["Lucro operacional", "Operating profit", operatingProfit],
            ["Juros e despesas financeiras", "Interest and financial expenses", -n("juros_brl")],
            ["Resultado antes de IR/CSLL estimados", "Profit before estimated IR/CSLL", profitBeforeTax]
        ];
        if (isPresumedProfit) {
            dre.push(["IRPJ comercial sobre faturamento", "Commercial IRPJ on revenue", -irpj]);
            dre.push(["Adicional de IRPJ", "Additional IRPJ", -additionalIrpj]);
            dre.push(["CSLL comercial sobre faturamento", "Commercial CSLL on revenue", -csll]);
        } else dre.push(["IR/CSLL estimados", "Estimated IR/CSLL", -brazilTax]);
        dre.push(["Lucro líquido Brasil", "Brazil net profit", netBrazil]);
        return {
            fobUsd, sold, pricePerKit, grossRevenue, commercialRevenue, salesTaxes, netRevenue,
            cogs, opex, variableOperator, operatingProfit, profitBeforeTax, brazilTax, irpj,
            additionalIrpj, csll, netBrazil, netExportProfit, parentBrazilProfit, branchRetained,
            dividendWithholding, remittanceCost, netRemittance, globalProfit, dre,
            exportMargin: fobUsd ? netExportProfit / (fobUsd * exchange) : 0,
            marginBrazil: netRevenue ? netBrazil / netRevenue : null,
            markup: importData.inventoryCost > 0 ? pricePerKit / (importData.inventoryCost / quantity) : null,
            effectiveBrazilTax: commercialRevenue ? brazilTax / commercialRevenue : null
        };
    }
    const c1 = calculateScenario(n("preco_fob_base"), sold1, n("receita_por_kit"), 1, rate("participacao_matriz"), import1);
    const c2 = calculateScenario(n("preco_fob_c2"), sold2, n("receita_por_kit_c2"), n("fator_opex_c2"), rate("participacao_matriz_c2"), import2);
    const comparisonData = [
        ["Preço FOB matriz", "Parent company FOB price", "USD/kit", n("preco_fob_base"), n("preco_fob_c2")],
        ["FOB total", "Total FOB", "USD", c1.fobUsd, c2.fobUsd],
        ["Kits vendidos", "Kits sold", "kits", c1.sold, c2.sold],
        ["Preço bruto de venda Brasil", "Brazil gross selling price", "R$/kit", c1.pricePerKit, c2.pricePerKit],
        ["Fator de Opex local", "Local operating expense factor", "x", 1, n("fator_opex_c2")],
        ["Valor aduaneiro", "Customs value", "R$", import1.customsValue, import2.customsValue],
        ["Desembolso total da importação", "Total import outlay", "R$", import1.outlay, import2.outlay],
        ["Créditos tributários estimados", "Estimated tax credits", "R$", import1.credits, import2.credits],
        ["Custo líquido de aquisição do estoque", "Net inventory acquisition cost", "R$", import1.inventoryCost, import2.inventoryCost],
        ["Custo de aquisição por kit", "Acquisition cost per kit", "R$/kit", import1.inventoryCost / quantity, import2.inventoryCost / quantity],
        ["CMV do período", "Cost of goods sold for the period", "R$", c1.cogs, c2.cogs],
        ["Receita líquida Brasil", "Brazil net revenue", "R$", c1.netRevenue, c2.netRevenue],
        ["Lucro líquido Brasil", "Brazil net profit", "R$", c1.netBrazil, c2.netBrazil],
        ["Markup (preço bruto / custo de aquisição)", "Markup (gross price / acquisition cost)", "x", c1.markup, c2.markup],
        ["IRPJ + CSLL calculados", "Calculated IRPJ + CSLL", "R$", c1.brazilTax, c2.brazilTax],
        ["Alíquota efetiva IRPJ + CSLL", "Effective IRPJ + CSLL rate", "%", c1.effectiveBrazilTax === null ? null : c1.effectiveBrazilTax * 100, c2.effectiveBrazilTax === null ? null : c2.effectiveBrazilTax * 100],
        ["Margem líquida Brasil / receita líquida", "Brazil net margin / net revenue", "%", c1.marginBrazil === null ? null : c1.marginBrazil * 100, c2.marginBrazil === null ? null : c2.marginBrazil * 100],
        ["Parcela atribuída à matriz", "Share allocated to parent company", "%", n("participacao_matriz"), n("participacao_matriz_c2")],
        ["Parcela atribuída à filial/local", "Share allocated to branch/local company", "%", 100 - n("participacao_matriz"), 100 - n("participacao_matriz_c2")],
        ["Resultado da matriz no Brasil antes da remessa", "Brazil parent company profit before remittance", "R$", c1.parentBrazilProfit, c2.parentBrazilProfit],
        ["Resultado retido na filial/local", "Profit retained by branch/local company", "R$", c1.branchRetained, c2.branchRetained],
        ["Retenção sobre dividendos", "Dividend withholding tax", "R$", c1.dividendWithholding, c2.dividendWithholding],
        ["Custo cambial da remessa", "Foreign exchange cost of remittance", "R$", c1.remittanceCost, c2.remittanceCost],
        ["Remessa líquida à matriz", "Net remittance to parent company", "R$", c1.netRemittance, c2.netRemittance],
        ["Lucro líquido da exportação da matriz", "Parent company net export profit", "R$", c1.netExportProfit, c2.netExportProfit],
        ["Margem líquida exportação / FOB convertido", "Net export margin / converted FOB", "%", c1.exportMargin * 100, c2.exportMargin * 100],
        ["Lucro total da matriz (exportação + remessa)", "Total parent company profit (exports + remittance)", "R$", c1.netExportProfit + c1.netRemittance, c2.netExportProfit + c2.netRemittance],
        ["Lucro global consolidado", "Consolidated global profit", "R$", c1.globalProfit, null],
        ["Lucro global consolidado por kit", "Consolidated global profit per kit", "R$/kit", c1.globalProfit / quantity, null]
    ];
    function display(value, unit) {
        if (value === null || value === undefined || Number.isNaN(Number(value))) return "N/A";
        if (unit === "USD" || unit === "USD/kit") return usd(value) + (unit === "USD/kit" ? "/kit" : "");
        if (unit === "kits") return new Intl.NumberFormat(pt ? "pt-BR" : "en-US", {maximumFractionDigits: 0}).format(value);
        if (unit === "%") return pct(value);
        if (unit === "x") return Number(value).toFixed(2).replace(pt ? "." : "_", pt ? "," : ".") + "x";
        return money(value) + (unit === "R$/kit" ? "/kit" : "");
    }
    const tableHeaders = pt
        ? ["Indicador", "Unidade", "Cenário 1", "Cenário 2"]
        : ["Metric", "Unit", "Scenario 1", "Scenario 2"];
    const compareRows = comparisonData.map(row => [
        pt ? row[0] : row[1],
        pt ? row[2] : row[2].replace("R$", "BRL"),
        display(row[3], row[2]),
        display(row[4], row[2])
    ]);
    const dreNames = [
        ["Receita bruta", "Gross revenue"], ["Devoluções, abatimentos e descontos", "Returns, allowances, and discounts"],
        ["Tributos sobre vendas", "Sales taxes"], ["Receita líquida", "Net revenue"],
        ["Custo das mercadorias vendidas (CMV)", "Cost of goods sold (COGS)"],
        ["Operação / armazenagem variável", "Variable operations / warehousing"],
        ["Opex fixo do período", "Fixed operating expenses for the period"], ["Lucro operacional", "Operating profit"],
        ["Juros e despesas financeiras", "Interest and financial expenses"],
        ["Resultado antes de IR/CSLL estimados", "Profit before estimated IR/CSLL"],
        ...(isPresumedProfit ? [["IRPJ comercial sobre faturamento", "Commercial IRPJ on revenue"], ["Adicional de IRPJ", "Additional IRPJ"], ["CSLL comercial sobre faturamento", "Commercial CSLL on revenue"]] : [["IR/CSLL estimados", "Estimated IR/CSLL"]]),
        ["Lucro líquido Brasil", "Brazil net profit"]
    ];
    const dreRows = dreNames.map(names => {
        const row1 = c1.dre.find(item => item[0] === names[0]);
        const row2 = c2.dre.find(item => item[0] === names[0]);
        return [pt ? names[0] : names[1], row1 ? money(row1[2]) : label("N/A", "N/A"), row2 ? money(row2[2]) : label("N/A", "N/A")];
    });
    const compositionByName = new Map();
    for (const item of import1.composition) compositionByName.set(item[0], [item[1], item[2], null]);
    for (const item of import2.composition) {
        const row = compositionByName.get(item[0]) || [item[1], null, null];
        row[2] = item[2];
        compositionByName.set(item[0], row);
    }
    const importRows = Array.from(compositionByName.entries()).map(([name, row]) => [
        pt ? name : row[0],
        row[1] === null ? label("Não disponível", "Not available") : money(row[1]),
        row[2] === null ? label("Não disponível", "Not available") : money(row[2])
    ]);
    const execRows = [
        [label("1. Subsidiária controlada", "1. Controlled subsidiary"), c1, true],
        [label("2. Distribuidor Independente", "2. Independent distributor"), c2, false]
    ].map(([name, c, globalApplicable]) => [
        name, usd(c.fobUsd), money(c.netExportProfit), pct(c.exportMargin * 100),
        money(c.parentBrazilProfit), pct(c.grossRevenue ? c.parentBrazilProfit / c.grossRevenue * 100 : 0),
        money(c.netExportProfit + c.netRemittance), money(c.branchRetained),
        pct(c.grossRevenue ? c.branchRetained / c.grossRevenue * 100 : 0),
        globalApplicable ? money(c.globalProfit) : label("N/A", "N/A"),
        globalApplicable ? money(c.globalProfit / quantity) : label("N/A", "N/A"),
        c.markup === null ? label("N/A", "N/A") : c.markup.toFixed(2).replace(".", pt ? "," : ".") + "x"
    ]);
    return {
        summaryTitle: label("Resumo da DRE Operacional (Brasil)", "Brazil operating income statement summary"),
        summary: [
            {label: label("Faturamento Bruto (R$)", "Gross revenue (BRL)"), value: money(c1.grossRevenue)},
            {label: label("Acomodação / Operador (R$)", "Logistics operator (BRL)"), value: money(c1.variableOperator)},
            {label: label("Landed Cost (R$)", "Landed cost (BRL)"), value: money(import1.inventoryCost)},
            {label: label("Lucro Operacional (R$)", "Operating profit (BRL)"), value: money(c1.operatingProfit)},
            {label: label(`Impostos BR (${pct(c1.salesTaxes + c1.brazilTax && c1.grossRevenue ? (c1.salesTaxes + c1.brazilTax) / c1.grossRevenue * 100 : 0)})`, `Brazil taxes (${pct(c1.salesTaxes + c1.brazilTax && c1.grossRevenue ? (c1.salesTaxes + c1.brazilTax) / c1.grossRevenue * 100 : 0)})`), value: money(c1.salesTaxes + c1.brazilTax)},
            {label: label("Lucro Líquido BR (100%)", "Brazil net profit (100%)"), value: money(c1.netBrazil)}
        ],
        charts: [{
            title: label("Resultado por entidade e cenário", "Profit by entity and scenario"),
            categories: [label("Cenário 1", "Scenario 1"), label("Cenário 2", "Scenario 2")],
            series: [
                {label: label("Resultado retido na filial/local", "Profit retained by branch/local company"), color: "#4e9a72", values: [c1.branchRetained, c2.branchRetained], formatted: [money(c1.branchRetained), money(c2.branchRetained)]},
                {label: label("Remessa líquida à matriz", "Net remittance to parent company"), color: "#d78a36", values: [c1.netRemittance, c2.netRemittance], formatted: [money(c1.netRemittance), money(c2.netRemittance)]},
                {label: label("Lucro líquido da exportação da matriz", "Parent company net export profit"), color: "#2878a0", values: [c1.netExportProfit, c2.netExportProfit], formatted: [money(c1.netExportProfit), money(c2.netExportProfit)]},
                {label: label("Lucro global consolidado", "Consolidated global profit"), color: "#18364a", values: [c1.globalProfit, null], formatted: [money(c1.globalProfit), label("N/A", "N/A")]}
            ]
        }],
        tables: [
            {title: label("Comparativo Executivo - Dois Cenários", "Executive comparison - Two scenarios"), headers: [
                label("Cenário Societário / Comercial", "Business / ownership scenario"), label("FOB (USD)", "FOB (USD)"),
                label("Lucro exportação (R$)", "Export profit (BRL)"), label("Margem exportação (%)", "Export margin (%)"),
                label("Lucro matriz Brasil (R$)", "Brazil parent profit (BRL)"), label("Margem matriz (%)", "Parent margin (%)"),
                label("Lucro total matriz (R$)", "Total parent profit (BRL)"), label("Lucro filial/local (R$)", "Branch/local profit (BRL)"),
                label("Margem filial/local (%)", "Branch/local margin (%)"), label("Lucro global (R$)", "Global profit (BRL)"),
                label("Lucro global/kit (R$)", "Global profit/kit (BRL)"), label("Markup (x)", "Markup (x)")
            ], rows: execRows},
            {title: label("Comparação detalhada dos cenários", "Detailed scenario comparison"), headers: tableHeaders, rows: compareRows},
            {title: label("Composição da importação", "Import composition"), headers: [label("Item", "Item"), label("Cenário 1", "Scenario 1"), label("Cenário 2", "Scenario 2")], rows: importRows},
            {title: label("DRE gerencial Brasil", "Brazil management income statement"), headers: [label("Conta", "Account"), label("Cenário 1", "Scenario 1"), label("Cenário 2", "Scenario 2")], rows: dreRows}
        ]
    };
}'''
