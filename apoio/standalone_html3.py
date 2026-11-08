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
        "language": "Idioma",
        "theme": "Tema",
        "currency": "Moeda",
        "theme_auto": "Automático",
        "theme_light": "Claro",
        "theme_dark": "Escuro",
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
        "language": "Language",
        "theme": "Theme",
        "currency": "Currency",
        "theme_auto": "Automatic",
        "theme_light": "Light",
        "theme_dark": "Dark",
    },
}


MODE_FIELDS = {
    "modo_custos_importacao", "modo_tributos_venda", "modo_opex",
    "modo_custos_importacao_p2", "modo_tributos_venda_p2", "moeda_relatorio",
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
    label_attrs = (
        f'data-pt="{escape(field_data["label"]["pt"], quote=True)}" '
        f'data-en="{escape(field_data["label"]["en"], quote=True)}"'
    )
    kind = field_data["kind"]
    if kind == "select":
        options = []
        for value, label_pt, label_en in field_data["options"]:
            selected = " selected" if str(value) == str(field_data["value"]) else ""
            options.append(
                f'<option value="{escape(str(value), quote=True)}"{selected} '
                f'data-pt="{escape(str(label_pt), quote=True)}" data-en="{escape(str(label_en), quote=True)}">'
                f'{escape(label_pt if language == "pt" else label_en)}</option>'
            )
        class_attr = ' class="mode-choice"' if key in MODE_FIELDS else ""
        control = f'<select id="f-{key}" data-key="{key}"{class_attr}>{"".join(options)}</select>'
    elif kind == "checkbox":
        checked = " checked" if field_data["value"] else ""
        control = f'<input id="f-{key}" data-key="{key}" type="checkbox"{checked}>'
        return f'<label class="check-field" for="f-{key}">{control}<span {label_attrs}>{label}</span></label>'
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
    wrapper_class = "field mode-field" if kind == "select" and field_data["key"] in MODE_FIELDS else "field"
    return f'<label class="{wrapper_class}" for="f-{key}"><span {label_attrs}>{label}</span>{control}</label>'


def build_calculator_html(
    *,
    model_id: str,
    language: str,
    title: str,
    fields: list[dict[str, Any]],
    calculation_js: str,
    titles: dict[str, str] | None = None,
    auto_language: bool = False,
) -> str:
    import_note = ""
    if model_id == "synvitta3":
        from synvitta3_importacao import FONTES_IMPORTACAO, NOTA_IMPORTACAO, NOTA_IMPORTACAO_EN, completar_campos_importacao

        fields = completar_campos_importacao(fields)
        import_note = (
            '<details class="input-group"><summary data-pt="Base oficial e preenchimento — 02/11/2026" data-en="Official basis and input guidance — 2026-11-02">Base oficial e preenchimento — 02/11/2026</summary>'
            f'<p class="note" data-pt="{escape(NOTA_IMPORTACAO, quote=True)}" data-en="{escape(NOTA_IMPORTACAO_EN, quote=True)}">{escape(NOTA_IMPORTACAO)}</p><p class="note">'
            + " · ".join(f'<a href="{escape(url, quote=True)}" target="_blank" rel="noopener">{escape(name)}</a>' for name, url in FONTES_IMPORTACAO)
            + "</p></details>"
        )
    language = "en" if language == "en" else "pt"
    titles = titles or {"pt": title, "en": title}
    text = UI_TEXT[language]
    groups: dict[str, list[dict[str, Any]]] = {}
    group_names: dict[str, dict[str, str]] = {}
    for item in fields:
        group_key = item["group"][language]
        groups.setdefault(group_key, []).append(item)
        group_names[group_key] = item["group"]
    sections = [import_note] if import_note else []
    for index, (group, items) in enumerate(groups.items()):
        controls = "".join(_control(item, language) for item in items)
        opened = " open" if index == 0 else ""
        sections.append(
            f'<details class="input-group"{opened}><summary data-pt="{escape(group_names[group]["pt"], quote=True)}" '
            f'data-en="{escape(group_names[group]["en"], quote=True)}">{escape(group)}</summary>'
            f'<div class="field-grid">{controls}</div></details>'
        )
    if model_id == "synvitta3" and "calculateLc224Surcharge" in calculation_js:
        note_pt = "LC 224/2025: majoração de 10% dos percentuais presumidos sobre a receita que exceder R$ 5 milhões no ano; IRPJ desde janeiro de 2026 e CSLL desde abril de 2026. Períodos com mais de um mês pressupõem receita uniforme entre os meses e devem caber no mesmo ano-calendário."
        note_en = "LC 224/2025: 10% increase to presumed-profit percentages on revenue above BRL 5 million per year; IRPJ from January 2026 and CSLL from April 2026. Periods longer than one month assume revenue is uniform across months and must fit within one calendar year."
        sections.append(f'<p class="note" data-pt="{escape(note_pt, quote=True)}" data-en="{escape(note_en, quote=True)}">{escape(note_en if language == "en" else note_pt)}</p>')
    defaults = {item["key"]: item["value"] for item in fields}
    defaults_json = json.dumps(defaults, ensure_ascii=False, separators=(",", ":"))
    defaults_json = defaults_json.replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")
    save_key = f"synvitta-standalone:{model_id}:{hashlib.sha256(defaults_json.encode('utf-8')).hexdigest()[:12]}"
    visibility_rules: dict[str, list[tuple[str, str]]] = {}
    if model_id == "synvitta3":
        detailed_import_fields = [
            "aliq_ii", "aliq_ipi", "aliq_pis", "aliq_cofins", "aliq_cbs", "aliq_ibs",
            "multiplo_base_cbs_ibs", "aliq_icms", "aliq_afrmm", "antidumping_brl",
            "despesas_na_base_icms", "custo_armazenagem", "custo_capatazia", "custo_despachante",
            "taxa_siscomex", "taxas_terminal", "honorarios_agente_carga", "licencas_inspecao",
            "outras_despesas_importacao", "credita_ipi", "credita_pis", "credita_cofins",
            "credita_cbs_ibs", "credita_icms",
        ]
        for key in detailed_import_fields:
            visibility_rules[key] = [("modo_custos_importacao", "Detalhado")]
        for suffix in ("", "_p2"):
            for key in ("custo_anvisa", "custo_hub", "outras_despesas_aduaneiras", "cbs_ibs_recolher", "iof_cambio"):
                visibility_rules[key + suffix] = [("modo_custos_importacao" + suffix, "Detalhado")]
            visibility_rules["seguro_pct" + suffix] = [("modo_seguro" + suffix, "Percentual")]
            visibility_rules["seguro_total_usd" + suffix] = [("modo_seguro" + suffix, "Valor informado")]
        visibility_rules["custo_importacao_consolidado_brl"] = [("modo_custos_importacao", "Consolidado")]
        for key in ("aliq_icms_venda", "aliq_pis_venda", "aliq_cofins_venda", "aliq_outros_venda"):
            visibility_rules[key] = [("modo_tributos_venda", "Detalhado")]
        visibility_rules["aliq_venda_consolidada"] = [("modo_tributos_venda", "Consolidado")]
        for item in fields:
            key = item["key"]
            if key.endswith("_p2"):
                visibility_rules.setdefault(key, []).append(("p2_ativo", "true"))
        for key in detailed_import_fields:
            if key + "_p2" in visibility_rules:
                visibility_rules[key + "_p2"].append(("modo_custos_importacao_p2", "Detalhado"))
        if "custo_importacao_consolidado_brl_p2" in visibility_rules:
            visibility_rules["custo_importacao_consolidado_brl_p2"].append(
                ("modo_custos_importacao_p2", "Consolidado")
            )
        for key in ("aliq_icms_venda", "aliq_pis_venda", "aliq_cofins_venda", "aliq_outros_venda"):
            if key + "_p2" in visibility_rules:
                visibility_rules[key + "_p2"].append(("modo_tributos_venda_p2", "Detalhado"))
        if "aliq_venda_consolidada_p2" in visibility_rules:
            visibility_rules["aliq_venda_consolidada_p2"].append(("modo_tributos_venda_p2", "Consolidado"))
        detailed_opex_fields = [
            "opex_pessoal", "opex_aluguel", "opex_utilidades", "opex_servicos_profissionais",
            "opex_comercial_marketing", "opex_sistemas", "opex_seguros", "opex_depreciacao",
            "opex_administrativo", "opex_outros",
        ]
        for key in detailed_opex_fields:
            visibility_rules[key] = [("modo_opex", "Detalhado")]
        visibility_rules["opex_consolidado_mensal"] = [("modo_opex", "Consolidado")]
    visibility_rules_json = json.dumps(visibility_rules, ensure_ascii=False, separators=(",", ":"))
    safe_model = escape(model_id, quote=True)
    safe_title = escape(titles[language])
    light_vars = (
        "--ink:#18364a;--head-bg:#18364a;--text:#203040;--muted:#52606d;--line:#d9e1e8;--line2:#bac7cf;"
        "--paper:#fff;--canvas:#f3f6f7;--blue:#2878a0;--green:#4e9a72;--orange:#d78a36;--zebra:#f0f5f7;"
        "--zebra1:#eaedf0;--zebra2:#e8ecf4;--track:#e7edf0;--locked-bg:#e7ecef;--locked-text:#59656b;"
        "--err-bg:#fff1ed;--err-text:#792f22"
    )
    dark_vars = (
        "--ink:#e3edf3;--head-bg:#14303f;--text:#dbe5ec;--muted:#9fb0bc;--line:#2e4350;--line2:#425a69;"
        "--paper:#1a2630;--canvas:#10181e;--blue:#4aa3d0;--green:#5fb487;--orange:#e3a050;--zebra:#1f2d38;"
        "--zebra1:#1d2933;--zebra2:#22303b;--track:#2a3a46;--locked-bg:#222e37;--locked-text:#7d8d98;"
        "--err-bg:#3a1f1a;--err-text:#f2b8aa"
    )
    initial_language = json.dumps(language)
    texts_json = json.dumps(UI_TEXT, ensure_ascii=False)
    titles_json = json.dumps(titles, ensure_ascii=False)
    auto_flag = "true" if auto_language else "false"
    return f'''<!doctype html>
<html lang="{"en" if language == "en" else "pt-BR"}">
<head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="application-name" content="{safe_model}"><title>{safe_title}</title>
<style>
:root{{{light_vars};color-scheme:light}}
@media(prefers-color-scheme:dark){{:root:not([data-theme="light"]){{{dark_vars};color-scheme:dark}}}}
:root[data-theme="dark"]{{{dark_vars};color-scheme:dark}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--canvas);color:var(--text);font:15px/1.45 "Segoe UI",Arial,sans-serif}}
header{{background:var(--head-bg);color:#fff;padding:20px max(20px,calc((100vw - 1500px)/2));display:flex;align-items:center;justify-content:space-between;gap:18px}}
header h1{{font-size:22px;line-height:1.2;margin:0}}header p{{font-size:12px;color:#d5e1e7;margin:5px 0 0}}#save-status{{font-size:12px;white-space:nowrap}}
.layout{{max-width:1540px;padding:20px;margin:auto;display:grid;grid-template-columns:minmax(300px,380px) minmax(0,1fr);gap:20px;align-items:start}}
aside,.results{{min-width:0}}.panel-title{{font-size:17px;color:var(--ink);margin:0 0 12px}}
.input-group,.output-section{{background:var(--paper);border:1px solid var(--line);border-radius:6px;margin-bottom:10px}}
.input-group summary{{cursor:pointer;padding:12px 14px;color:var(--ink);font-weight:700}}.field-grid{{display:grid;grid-template-columns:1fr 1fr;gap:10px;padding:0 12px 13px}}
.field{{display:grid;gap:4px;font-size:12px;color:var(--muted);min-width:0}}.field[hidden],.check-field[hidden]{{display:none!important}}.field input,.field select{{width:100%;min-width:0;border:1px solid var(--line2);border-radius:4px;padding:8px;background:var(--paper);color:var(--text);font:inherit;font-size:14px}}
.toolbar{{display:flex;gap:10px;align-items:center;flex-wrap:wrap}}.toolbar label{{display:flex;align-items:center;gap:6px;font-size:12px;color:#d5e1e7}}.toolbar select{{background:var(--paper);color:var(--text);border:1px solid var(--line2);border-radius:4px;padding:5px 8px;font:inherit;font-size:13px}}
.field.mode-field{{grid-column:1/-1;padding:10px;border:2px solid var(--blue);border-radius:5px;background:#edf5f8;color:var(--ink);font-weight:700}}.mode-field select{{border:2px solid var(--blue);font-weight:700;color:var(--ink)}}
.field.locked,.check-field.locked{{opacity:.48;filter:grayscale(.75);cursor:not-allowed}}.field.locked input,.field.locked select{{background:var(--locked-bg);color:var(--locked-text);cursor:not-allowed}}.check-field.locked input{{cursor:not-allowed}}
.check-field{{grid-column:span 2;display:flex;align-items:center;gap:8px;color:var(--text);font-size:13px}}.check-field input{{width:17px;height:17px;accent-color:var(--blue)}}
.actions{{display:grid;grid-template-columns:1fr 1fr;gap:8px;margin:12px 0}}button,.file-label{{border:1px solid var(--blue);background:var(--blue);color:#fff;padding:9px 10px;border-radius:4px;font:inherit;font-size:13px;font-weight:700;text-align:center;cursor:pointer}}button.secondary,.file-label.secondary{{background:var(--paper);color:var(--blue)}}button:hover,.file-label:hover{{filter:brightness(.94)}}#import-file{{display:none}}.note{{color:var(--muted);font-size:12px;margin:8px 2px}}
.output-section{{padding:14px;overflow:hidden}}.output-section h2{{font-size:17px;color:var(--ink);margin:0 0 12px}}.kpis{{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:10px}}
.kpi{{border-bottom:2px solid var(--blue);padding:8px 5px;min-width:0}}.kpi span{{display:block;font-size:11px;color:var(--muted)}}.kpi strong{{display:block;color:var(--ink);font-size:15px;margin-top:4px;overflow-wrap:anywhere}}
.table-wrap{{overflow-x:auto}}table{{border-collapse:collapse;width:100%;min-width:680px;font-size:12px}}th{{background:var(--head-bg);color:#fff;text-align:left}}th,td{{padding:8px;border:1px solid var(--line);vertical-align:top}}tbody tr:nth-child(even){{background:var(--zebra)}}td.num{{text-align:right;white-space:nowrap}}
table.income-statement{{min-width:1050px}}table.income-statement th{{background:#1A252F;text-align:center;white-space:nowrap}}table.income-statement tbody tr:nth-child(odd){{background:var(--zebra1)}}table.income-statement tbody tr:nth-child(even){{background:var(--zebra2)}}table.income-statement tbody tr.subtotal{{font-weight:700}}table.income-statement td:nth-child(n+2):nth-child(-n+5){{text-align:right;white-space:nowrap}}table.income-statement td:last-child{{min-width:260px}}
.chart-list{{display:grid;gap:12px}}.chart-row{{display:grid;grid-template-columns:minmax(120px,190px) minmax(80px,1fr) minmax(110px,150px);gap:8px;align-items:center;font-size:12px}}.chart-row label{{color:var(--muted)}}.bar-track{{height:13px;background:var(--track);border-radius:3px;overflow:hidden}}.bar{{height:100%;min-width:1px;border-radius:3px}}.chart-value{{text-align:right;font-variant-numeric:tabular-nums;white-space:nowrap}}
#error-box{{display:none;background:var(--err-bg);border-left:4px solid #b94b32;padding:10px;margin-bottom:10px;color:var(--err-text)}}
@media(max-width:900px){{.layout{{grid-template-columns:1fr;padding:12px}}.toolbar{{width:100%}}header{{padding:16px;align-items:flex-start;flex-direction:column}}.kpis{{grid-template-columns:repeat(2,minmax(0,1fr))}}}}
@media(max-width:520px){{.field-grid{{grid-template-columns:1fr}}.check-field{{grid-column:span 1}}.chart-row{{grid-template-columns:minmax(100px,1fr) 1fr;gap:5px}}.bar-track{{grid-column:1/-1;grid-row:2}}.chart-value{{grid-column:2;grid-row:1}}.actions{{grid-template-columns:1fr}}}}
@media print{{html:root:root{{{light_vars};color-scheme:light}}.toolbar{{display:none}}@page{{size:landscape;margin:12mm}}body{{background:#fff}}header{{padding:0 0 12px;background:#fff;color:#18364a;box-shadow:none}}header p,#save-status{{display:none}}.layout{{display:block;max-width:none;padding:0}}aside,.actions,.note,.results>.panel-title{{display:none!important}}.results{{width:100%}}.output-section{{break-inside:avoid;border:0;padding:8px 0;overflow:visible}}.table-wrap{{overflow:visible}}table{{min-width:0;font-size:9px}}th,td{{padding:4px}}.chart-row{{break-inside:avoid}}}}
</style></head>
<body>
<header><div><h1 id="page-title">{safe_title}</h1><p data-i18n="tagline">{escape(text["tagline"])}</p></div>
<div class="toolbar"><label><span data-i18n="language">{escape(text["language"])}</span><select id="lang-select"><option value="pt">Português</option><option value="en">English</option></select></label>
<label><span data-i18n="currency">{escape(text["currency"])}</span><select id="currency-select"><option value="USD">USD</option><option value="BRL">BRL</option></select></label>
<label><span data-i18n="theme">{escape(text["theme"])}</span><select id="theme-select"><option value="auto" data-i18n="theme_auto">{escape(text["theme_auto"])}</option><option value="light" data-i18n="theme_light">{escape(text["theme_light"])}</option><option value="dark" data-i18n="theme_dark">{escape(text["theme_dark"])}</option></select></label>
<span id="save-status" aria-live="polite"></span></div></header>
<div class="layout"><aside><h2 class="panel-title" data-i18n="inputs">{escape(text["inputs"])}</h2><form id="input-form">{"".join(sections)}</form>
<div class="actions"><button id="export-inputs" type="button" data-i18n="download_inputs">{escape(text["download_inputs"])}</button>
<label class="file-label secondary" for="import-file" data-i18n="upload_inputs">{escape(text["upload_inputs"])}</label>
<input id="import-file" type="file" accept="application/json,.json">
<button class="secondary" id="print-pdf" type="button" data-i18n="print_pdf">{escape(text["print_pdf"])}</button>
<button class="secondary" id="export-results-excel" type="button" data-i18n="export_excel">{escape(text["export_excel"])}</button>
<button class="secondary" id="reset-inputs" type="button" data-i18n="reset">{escape(text["reset"])}</button></div>
<p class="note"><span data-i18n="assumptions">{escape(text["assumptions"])}</span> <span data-i18n="print_hint">{escape(text["print_hint"])}</span></p></aside>
<main class="results"><h2 class="panel-title" data-i18n="results">{escape(text["results"])}</h2><div id="error-box" role="alert"></div>
<div id="results-content" aria-live="polite"></div></main></div>
<script id="initial-values" type="application/json">{defaults_json}</script>
<script>
"use strict";
const MODEL_ID={json.dumps(model_id)};
let LANGUAGE={initial_language};
const TITLES={titles_json};
const TXT_ALL={texts_json};
const LANG_KEY="synvitta-language";
const THEME_KEY="synvitta-theme";
const DEFAULTS=JSON.parse(document.getElementById("initial-values").textContent);
const VISIBILITY_RULES={visibility_rules_json};
const SAVE_KEY={json.dumps(save_key)};
let TXT=TXT_ALL[LANGUAGE];
{calculation_js}
function esc(value){{return String(value??"").replace(/[&<>"']/g,char=>({{"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}}[char]));}}
function readInputs(){{const values={{}};document.querySelectorAll("[data-key]").forEach(input=>{{const key=input.dataset.key;if(input.type==="checkbox")values[key]=input.checked;else if(input.type==="number")values[key]=Number(input.value||0)/Number(input.dataset.scale||1);else values[key]=input.value;}});return values;}}
function applyInputs(values){{document.querySelectorAll("[data-key]").forEach(input=>{{const key=input.dataset.key;if(!(key in values))return;if(input.type==="checkbox")input.checked=Boolean(values[key]);else if(input.type==="number")input.value=String(Number(values[key]||0)*Number(input.dataset.scale||1));else input.value=String(values[key]??"");}});}}
function updateConditionalInputs(values){{for(const [key,condition] of Object.entries(VISIBILITY_RULES)){{const input=document.querySelector(`[data-key="${{key}}"]`);const wrapper=input?.closest("label");if(!input||!wrapper)continue;const locked=condition.some(rule=>String(values[rule[0]])!==rule[1]);input.disabled=locked;wrapper.classList.toggle("locked",locked);}}}}
function saveInputs(values){{try{{localStorage.setItem(SAVE_KEY,JSON.stringify(values));document.getElementById("save-status").textContent=TXT.saved;}}catch(error){{document.getElementById("save-status").textContent=TXT.saved_error;}}}}
function downloadBlob(filename,blob){{const url=URL.createObjectURL(blob);const link=document.createElement("a");link.href=url;link.download=filename;link.hidden=true;document.body.appendChild(link);link.click();link.remove();setTimeout(()=>URL.revokeObjectURL(url),1000);}}
function cell(value){{return `<td>${{esc(value)}}</td>`;}}
function renderTable(table){{const tableClass=table.style==="income-statement"?" income-statement":"";return `<section class="output-section"><h2>${{esc(table.title)}}</h2><div class="table-wrap"><table class="${{tableClass.trim()}}"><thead><tr>${{table.headers.map(header=>`<th>${{esc(header)}}</th>`).join("")}}</tr></thead><tbody>${{table.rows.map((row,index)=>`<tr class="${{table.emphasisRows?.includes(index)?"subtotal":""}}">${{row.map(cell).join("")}}</tr>`).join("")}}</tbody></table></div></section>`;}}
function renderChart(chart){{const max=Math.max(1,...chart.series.flatMap(series=>series.values.map(value=>Math.abs(Number(value)||0))));return `<section class="output-section"><h2>${{esc(chart.title)}}</h2><div class="chart-list">${{chart.series.map(series=>series.values.map((value,index)=>`<div class="chart-row"><label>${{esc(series.label)}} · ${{esc(chart.categories[index])}}</label><div class="bar-track"><div class="bar" style="width:${{Math.max(1,Math.abs(value)/max*100)}}%;background:${{esc(series.color)}}"></div></div><strong class="chart-value">${{esc(series.formatted[index])}}</strong></div>`).join("")).join("")}}</div></section>`;}}
function render(result){{const warnings=(result.importWarnings||[]).map(message=>`<section class="output-section" role="status">${{esc(message)}}</section>`).join("");const kpis=`<section class="output-section"><h2>${{esc(result.summaryTitle)}}</h2><div class="kpis">${{result.summary.map(item=>`<div class="kpi"><span>${{esc(item.label)}}</span><strong>${{esc(item.value)}}</strong></div>`).join("")}}</div></section>`;document.getElementById("results-content").innerHTML=warnings+kpis+result.charts.map(renderChart).join("")+result.tables.map(renderTable).join("");window.CURRENT_CALCULATION=result;document.getElementById("error-box").style.display="none";}}
function xmlEscape(value){{return String(value??"").replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;").replace(/\"/g,"&quot;").replace(/'/g,"&apos;");}}
function safeSheetName(value,index){{let name=String(value||`Results ${{index+1}}`);for(const invalid of [String.fromCharCode(92),"/","?","*","[","]",":"])name=name.split(invalid).join(" ");name=name.trim().slice(0,31);return name||`Results ${{index+1}}`;}}
function makeExcelWorkbook(result){{const sheets=[{{name:LANGUAGE==="pt"?"Resumo":"Summary",rows:[[result.summaryTitle],...result.summary.map(item=>[item.label,item.value])]}},...result.tables.map((table,index)=>({{name:safeSheetName(table.title,index),rows:[[table.title],table.headers,...table.rows]}}))];const used=new Set();const worksheetXml=sheets.map((sheet,index)=>{{let name=safeSheetName(sheet.name,index);let unique=name;let suffix=2;while(used.has(unique)){{unique=(name.slice(0,27)+" "+suffix++).slice(0,31);}}used.add(unique);const rows=sheet.rows.map(row=>`<Row>${{row.map(value=>`<Cell><Data ss:Type="String">${{xmlEscape(value)}}</Data></Cell>`).join("")}}</Row>`).join("");return `<Worksheet ss:Name="${{xmlEscape(unique)}}"><Table>${{rows}}</Table></Worksheet>`;}}).join("");return `<?xml version="1.0"?><Workbook xmlns="urn:schemas-microsoft-com:office:spreadsheet" xmlns:o="urn:schemas-microsoft-com:office:office" xmlns:x="urn:schemas-microsoft-com:office:excel" xmlns:ss="urn:schemas-microsoft-com:office:spreadsheet"><Styles><Style ss:ID="Default" ss:Name="Normal"><Alignment ss:Vertical="Bottom"/></Style></Styles>${{worksheetXml}}</Workbook>`;}}
function applyLanguage(lang){{LANGUAGE=lang==="en"?"en":"pt";TXT=TXT_ALL[LANGUAGE];document.documentElement.lang=LANGUAGE==="en"?"en":"pt-BR";document.querySelectorAll("[data-pt]").forEach(el=>{{el.textContent=el.dataset[LANGUAGE];}});document.querySelectorAll("[data-i18n]").forEach(el=>{{el.textContent=TXT[el.dataset.i18n];}});document.getElementById("page-title").textContent=TITLES[LANGUAGE];document.title=TITLES[LANGUAGE];document.getElementById("lang-select").value=LANGUAGE;}}
function applyTheme(theme){{const value=["light","dark"].includes(theme)?theme:"auto";if(value==="auto")document.documentElement.removeAttribute("data-theme");else document.documentElement.setAttribute("data-theme",value);document.getElementById("theme-select").value=value;}}
function readPref(key){{try{{return localStorage.getItem(key);}}catch(error){{return null;}}}}
function writePref(key,value){{try{{localStorage.setItem(key,value);}}catch(error){{}}}}
function update(){{try{{const values=readInputs();updateConditionalInputs(values);saveInputs(values);render(calculate(values,LANGUAGE));document.getElementById("export-results-excel").disabled=false;}}catch(error){{window.CURRENT_CALCULATION=null;document.getElementById("export-results-excel").disabled=true;document.getElementById("results-content").replaceChildren();const box=document.getElementById("error-box");box.textContent=error.message||String(error);box.style.display="block";}}}}
document.getElementById("input-form").addEventListener("input",update);
document.getElementById("input-form").addEventListener("change",update);
document.getElementById("reset-inputs").addEventListener("click",()=>{{try{{localStorage.removeItem(SAVE_KEY);}}catch(error){{}}applyInputs(DEFAULTS);update();}});
document.getElementById("export-inputs").addEventListener("click",()=>{{const payload={{model:MODEL_ID,version:1,values:readInputs()}};const blob=new Blob([JSON.stringify(payload,null,2)],{{type:"application/json"}});downloadBlob(MODEL_ID+"_"+TXT.export_name+".json",blob);}});
document.getElementById("print-pdf").addEventListener("click",()=>window.print());
document.getElementById("export-results-excel").addEventListener("click",()=>{{const workbook=makeExcelWorkbook(window.CURRENT_CALCULATION);const blob=new Blob([workbook],{{type:"application/vnd.ms-excel;charset=utf-8"}});downloadBlob(MODEL_ID+"_"+TXT.export_name+".xml",blob);}});
document.getElementById("import-file").addEventListener("change",async event=>{{const file=event.target.files[0];if(!file)return;try{{const payload=JSON.parse(await file.text());if(payload.model!==MODEL_ID||!payload.values)throw Error(TXT.import_error);applyInputs(payload.values);update();document.getElementById("save-status").textContent=TXT.import_ok;}}catch(error){{const box=document.getElementById("error-box");box.textContent=TXT.import_error;box.style.display="block";}}event.target.value="";}});
try{{const saved=JSON.parse(localStorage.getItem(SAVE_KEY)||"null");if(saved)applyInputs(saved);}}catch(error){{}}
const onLanguage=event=>{{applyLanguage(event.target.value);writePref(LANG_KEY,LANGUAGE);update();}};
document.getElementById("lang-select").addEventListener("change",onLanguage);
document.getElementById("lang-select").addEventListener("input",onLanguage);
const currencyField=document.getElementById("f-moeda_relatorio"),currencySelect=document.getElementById("currency-select");
function syncCurrency(){{if(currencyField)currencySelect.value=currencyField.value==="BRL"?"BRL":"USD";}}
currencySelect.addEventListener("change",()=>{{if(currencyField){{currencyField.value=currencySelect.value;}}update();}});
if(currencyField)currencyField.addEventListener("change",syncCurrency);
document.getElementById("theme-select").addEventListener("change",event=>{{applyTheme(event.target.value);writePref(THEME_KEY,event.target.value);}});
const AUTO_LANGUAGE={auto_flag};
const storedLanguage=readPref(LANG_KEY);
applyLanguage(storedLanguage||(AUTO_LANGUAGE&&String(navigator.language||"").toLowerCase().startsWith("en")?"en":LANGUAGE));
applyTheme(readPref(THEME_KEY)||"auto");
syncCurrency();
update();
</script></body></html>'''
