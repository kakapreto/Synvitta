import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from html import escape
from io import BytesIO
from pathlib import Path
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.graphics.charts.barcharts import VerticalBarChart
from reportlab.graphics.charts.legends import Legend
from reportlab.graphics.shapes import Drawing
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
from openpyxl.chart import BarChart, Reference
from openpyxl.chart.label import DataLabelList
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from standalone_html import build_calculator_html, field, synvitta_calculation_js

# Configuração da Página
st.set_page_config(
    page_title="Simulação Simplificada - Synvitta",
    page_icon="📊",
    layout="wide"
)

def formatar_reais(valor: float) -> str:
    valor_localizado = f"{valor:,.2f}".replace(",", "_").replace(".", ",").replace("_", ".")
    return f"R$ {valor_localizado}"


def formatar_reais_grafico(valor: float) -> str:
    sinal = "-" if valor < 0 else ""
    absoluto = abs(valor)
    if absoluto >= 1_000_000:
        return f"{sinal}R$ {absoluto / 1_000_000:.2f} mi".replace(".", ",")
    if absoluto >= 1_000:
        return f"{sinal}R$ {absoluto / 1_000:.0f} mil"
    return formatar_reais(valor)


st.title("📊 Simulação simplificada — Synvitta")
st.markdown("Ajuste as premissas e controles dos dois cenários na barra lateral.")

# ==========================================
# BARRA LATERAL - PARÂMETROS E PREMISSAS
# ==========================================
st.sidebar.header("⚙️ Premissas da Operação")

# Premissas Comerciais e Cambiais
cambio = st.sidebar.number_input("Taxa de Câmbio (USD/BRL)", min_value=0.01, value=5.60, step=0.10, format="%.2f")
numero_kits = st.sidebar.number_input("Número de kits", min_value=1, value=1000, step=100)
st.sidebar.caption("Faturamento, fabricação e FOB são valores-base para 1.000 kits e variam conforme a quantidade. O OpEx trimestral permanece fixo.")
faturamento_base = st.sidebar.number_input("Faturamento bruto base (R$ / 1.000 kits)", min_value=1.0, value=9598400.0, step=100000.0, format="%.2f")
cogs_usd_base = st.sidebar.number_input("Custo de produção da matriz (USD / 1.000 kits)", min_value=0.0, value=100000.0, step=10000.0, format="%.2f")

st.sidebar.markdown("---")
st.sidebar.header("📦 Custos Operacionais e Logística")

fob_usd_base = st.sidebar.slider("FOB base (USD / 1.000 kits)", min_value=0, max_value=500000, value=200000, step=10000)
pct_logistica = st.sidebar.number_input("Logística / Internalização (% s/ FOB)", min_value=0.0, value=130.0, step=5.0) / 100
pct_operador_log = st.sidebar.number_input("Acomodação / Operador Logístico (% s/ Faturamento)", min_value=0.0, max_value=100.0, value=5.0, step=0.5) / 100
opex_trimestral = st.sidebar.number_input("OpEx Local Trimestral (R$)", min_value=0.0, value=600000.0, step=50000.0)

st.sidebar.markdown("---")
st.sidebar.header("⚖️ Impostos e Remessas")

pct_imposto_br = st.sidebar.number_input("Carga Tributária Brasil (% s/ Lucro Operacional)", min_value=0.0, max_value=100.0, value=32.0, step=1.0) / 100
pct_retencao_div = st.sidebar.number_input("Imposto s/ Distribuição Dividendos BR (%)", min_value=0.0, max_value=100.0, value=10.0, step=1.0) / 100
pct_taxa_envio = st.sidebar.number_input("Taxa Cambial de Remessa (%)", min_value=0.0, max_value=100.0, value=1.0, step=0.1) / 100
pct_imposto_eua = st.sidebar.number_input("Imposto Corporativo Flórida/EUA (%)", min_value=0.0, max_value=100.0, value=25.35, step=0.5) / 100

fator_volume = numero_kits / 1000
faturamento_bruto = faturamento_base * fator_volume
cogs_usd = cogs_usd_base * fator_volume
fob_usd = fob_usd_base * fator_volume
custo_operador_log = faturamento_bruto * pct_operador_log
fob_brl_referencia_c2 = fob_usd * cambio
lucro_operacional_referencia_c2 = (
    faturamento_bruto
    - fob_brl_referencia_c2 * (1 + pct_logistica)
    - custo_operador_log
    - opex_trimestral
)
lucro_liquido_referencia_c2 = (
    lucro_operacional_referencia_c2
    - max(lucro_operacional_referencia_c2, 0) * pct_imposto_br
)

def lucro_filial_para_fob(fob_usd: float) -> float:
    fob_brl_calculado = fob_usd * cambio
    lucro_operacional = (
        faturamento_bruto
        - fob_brl_calculado * (1 + pct_logistica)
        - custo_operador_log
        - opex_trimestral
    )
    return lucro_operacional - max(lucro_operacional, 0) * pct_imposto_br


def fob_para_lucro_filial(lucro_alvo: float) -> float | None:
    if pct_imposto_br == 1 and lucro_alvo > 0:
        return None
    if lucro_alvo < 0 or pct_imposto_br == 1:
        lucro_operacional_alvo = lucro_alvo
    else:
        lucro_operacional_alvo = lucro_alvo / (1 - pct_imposto_br)
    fob_brl_alvo = (
        faturamento_bruto
        - custo_operador_log
        - opex_trimestral
        - lucro_operacional_alvo
    ) / (1 + pct_logistica)
    return fob_brl_alvo / cambio


def registrar_edicao_fob_c2() -> None:
    st.session_state["cenario2_ultima_edicao"] = "fob"


def registrar_edicao_lucro_c2() -> None:
    st.session_state["cenario2_ultima_edicao"] = "lucro"


chave_fob_c2 = "cenario2_fob_usd"
chave_lucro_c2 = "cenario2_lucro_filial_brl"
chave_referencia_c2 = "cenario2_referencia"
if chave_fob_c2 not in st.session_state:
    lucro_inicial_c2 = lucro_liquido_referencia_c2 * 0.25
    fob_inicial_c2 = fob_para_lucro_filial(lucro_inicial_c2)
    st.session_state[chave_fob_c2] = max(fob_inicial_c2 or 0, 0)
    st.session_state[chave_lucro_c2] = lucro_inicial_c2
    st.session_state[chave_referencia_c2] = "lucro"

ultima_edicao_c2 = st.session_state.pop("cenario2_ultima_edicao", None)
if ultima_edicao_c2 is not None:
    st.session_state[chave_referencia_c2] = ultima_edicao_c2

if st.session_state[chave_referencia_c2] == "fob":
    st.session_state[chave_lucro_c2] = lucro_filial_para_fob(st.session_state[chave_fob_c2])
    fob_c2_viavel = True
else:
    fob_alvo_c2 = fob_para_lucro_filial(st.session_state[chave_lucro_c2])
    fob_c2_viavel = fob_alvo_c2 is not None and fob_alvo_c2 >= -0.01
    st.session_state[chave_fob_c2] = max(fob_alvo_c2 or 0, 0)

st.sidebar.markdown("---")
st.sidebar.header("🏢 Cenário 1 - Participação societária")
pct_participacao_matriz_c1 = st.sidebar.slider(
    "Participação da matriz no resultado do Brasil (%)",
    min_value=0,
    max_value=100,
    value=75,
    step=5,
) / 100
pct_participacao_filial_c1 = 1 - pct_participacao_matriz_c1
st.sidebar.caption(f"Participação da filial no Brasil: {pct_participacao_filial_c1:.0%}")

st.sidebar.header("📈 Cenário 2 - FOB e lucro da filial")
st.sidebar.number_input(
    "FOB de venda da matriz para o Brasil (USD)",
    min_value=0.0,
    step=10000.0,
    format="%.2f",
    key=chave_fob_c2,
    on_change=registrar_edicao_fob_c2,
)
st.sidebar.number_input(
    "Lucro líquido da filial no Brasil (R$)",
    min_value=-1000000000000.0,
    max_value=1000000000000.0,
    step=50000.0,
    format="%.2f",
    key=chave_lucro_c2,
    on_change=registrar_edicao_lucro_c2,
)
st.sidebar.caption("Altere qualquer um dos campos; o outro será recalculado automaticamente.")

# ==========================================
# MOTOR DE CÁLCULO MÁTEMÁTICO (DRE BASE)
# ==========================================
fob_brl = fob_usd * cambio
landed_cost = fob_brl * (1 + pct_logistica)

lucro_operacional_br = faturamento_bruto - landed_cost - custo_operador_log - opex_trimestral
imposto_br = max(lucro_operacional_br, 0) * pct_imposto_br
lucro_liquido_br = lucro_operacional_br - imposto_br

# Margem de Exportação da Matriz EUA
cogs_brl = cogs_usd * cambio
lucro_fob_bruto_eua = fob_brl - cogs_brl
lucro_fob_liq_eua = lucro_fob_bruto_eua - max(lucro_fob_bruto_eua, 0) * pct_imposto_eua

# ==========================================
# CÁLCULO DOS 2 CENÁRIOS
# ==========================================
fator_remessa = (1 - pct_retencao_div) * (1 - pct_taxa_envio)

# Cenário 1: subsidiária com participação ajustável
lucro_matriz_br_c1 = lucro_liquido_br * pct_participacao_matriz_c1
lucro_filial_br_c1 = lucro_liquido_br * pct_participacao_filial_c1
dividendos_liquidos_c1 = max(lucro_matriz_br_c1, 0) * fator_remessa
lucro_global_c1 = lucro_fob_liq_eua + lucro_liquido_br - max(lucro_matriz_br_c1, 0) * (1 - fator_remessa)

# Cenário 2: FOB e lucro local mantidos em sincronia pelos campos da barra lateral
fob_usd_c2 = st.session_state[chave_fob_c2]
lucro_filial_alvo_c2 = st.session_state[chave_lucro_c2]
fob_brl_c2 = fob_usd_c2 * cambio
cenario_2_viavel = fob_c2_viavel
if cenario_2_viavel:
    landed_cost_c2 = fob_brl_c2 * (1 + pct_logistica)
    lucro_operacional_br_c2 = faturamento_bruto - landed_cost_c2 - custo_operador_log - opex_trimestral
    imposto_br_c2 = max(lucro_operacional_br_c2, 0) * pct_imposto_br
    lucro_filial_br_c2 = lucro_operacional_br_c2 - imposto_br_c2
    lucro_fob_bruto_eua_c2 = fob_brl_c2 - cogs_brl
    lucro_matriz_eua_c2 = lucro_fob_bruto_eua_c2 - max(lucro_fob_bruto_eua_c2, 0) * pct_imposto_eua
else:
    lucro_filial_br_c2 = None
    lucro_matriz_eua_c2 = None

st.sidebar.metric(
    "FOB de venda da matriz - Cenário 2",
    f"USD {fob_usd_c2:,.2f}" if fob_usd_c2 is not None else "Não viável",
)
st.sidebar.caption("FOB é o preço de exportação da matriz para o Brasil; o cenário 2 recalcula esse preço conforme a parcela de lucro escolhida.")

def margem_sobre_faturamento(lucro: float | None) -> float | None:
    return lucro / faturamento_bruto * 100 if lucro is not None else None

def margem_sobre_fob(lucro: float | None, fob_brl_calculado: float | None) -> float | None:
    if lucro is None or fob_brl_calculado is None or fob_brl_calculado == 0:
        return None
    return lucro / fob_brl_calculado * 100

if not cenario_2_viavel:
    st.warning(
        "A parcela escolhida para a filial no cenário 2 não é viável com o faturamento, "
        "OpEx e custos atuais: seria necessário um FOB negativo. Ajuste as premissas."
    )

lucro_matriz_total_c1 = lucro_fob_liq_eua + lucro_matriz_br_c1
lucro_matriz_total_c2 = lucro_matriz_eua_c2

# ==========================================
# PAINEL PRINCIPAL E PAINEL DE MÉTRICAS
# ==========================================
st.subheader("📌 Resumo da DRE Operacional (Brasil)")
col1, col2, col3, col4, col5, col6 = st.columns(6)

def exibir_indicador(coluna, rotulo: str, valor: str) -> None:
    coluna.markdown(
        f"<div style='min-height:56px;padding:5px 4px;border-bottom:2px solid #2878a0;'>"
        f"<div style='font-size:10px;line-height:1.2;color:#52606d;'>{escape(rotulo)}</div>"
        f"<div style='font-size:13px;line-height:1.2;font-weight:700;color:#18364a;margin-top:4px;'>{escape(valor)}</div>"
        "</div>",
        unsafe_allow_html=True,
    )

exibir_indicador(col1, "Faturamento Bruto (R$)", formatar_reais(faturamento_bruto))
exibir_indicador(col2, "Acomodação / Operador (R$)", formatar_reais(custo_operador_log))
exibir_indicador(col3, "Landed Cost (R$)", formatar_reais(landed_cost))
exibir_indicador(col4, "Lucro Operacional (R$)", formatar_reais(lucro_operacional_br))
exibir_indicador(col5, f"Impostos BR ({pct_imposto_br:.0%})", formatar_reais(imposto_br))
exibir_indicador(col6, "Lucro Líquido BR (100%)", formatar_reais(lucro_liquido_br))

st.markdown("---")
st.subheader("⚖️ Comparativo Executivo - Dois Cenários")

# Montagem da Tabela Comparativa
dados_cenarios = {
    "Cenário Societário / Comercial": [
        "1. Subsidiária Controlada",
        "2. Distribuidor Independente",
    ],
    "FOB do Cenário (USD)": [fob_usd, fob_usd_c2],
    "Lucro Matriz EUA - Exportação (R$)": [lucro_fob_liq_eua, lucro_matriz_eua_c2],
    "Margem Matriz EUA s/ FOB (%)": [
        margem_sobre_fob(lucro_fob_liq_eua, fob_brl),
        margem_sobre_fob(lucro_matriz_eua_c2, fob_brl_c2 if cenario_2_viavel else None),
    ],
    "Lucro Matriz Brasil (R$)": [lucro_matriz_br_c1, None],
    "Margem Matriz Brasil s/ Faturamento (%)": [margem_sobre_faturamento(lucro_matriz_br_c1), None],
    "Lucro Total da Matriz (R$)": [lucro_matriz_total_c1, lucro_matriz_total_c2],
    "Lucro Filial / Empresa Local Brasil (R$)": [lucro_filial_br_c1, lucro_filial_br_c2],
    "Margem Filial / Local s/ Faturamento (%)": [
        margem_sobre_faturamento(lucro_filial_br_c1),
        margem_sobre_faturamento(lucro_filial_br_c2),
    ],
    "Lucro Global Consolidado (R$)": [lucro_global_c1, None],
    "Lucro Global por Kit (R$)": [lucro_global_c1 / numero_kits, None],
    "Markup s/ Landed Cost (x)": [
        faturamento_bruto / landed_cost if landed_cost > 0 else None,
        faturamento_bruto / landed_cost_c2 if cenario_2_viavel and landed_cost_c2 > 0 else None,
    ],
}

df_cenarios = pd.DataFrame(dados_cenarios)

# Exibição da tabela executiva
def formatar_valor_tabela(coluna: str, valor) -> str:
    if pd.isna(valor):
        return "N/A"
    if coluna == "FOB do Cenário (USD)":
        return f"USD {valor:,.2f}"
    if "Markup" in coluna:
        return f"{valor:.2f}x".replace(".", ",")
    if "(%)" in coluna:
        return f"{valor:.2f}%".replace(".", ",")
    if "(R$)" in coluna:
        return formatar_reais(valor)
    return str(valor)


cabecalho_html = "".join(f"<th>{escape(str(coluna))}</th>" for coluna in df_cenarios.columns)
linhas_html = []
for indice, (_, linha) in enumerate(df_cenarios.iterrows()):
    celulas = "".join(
        f"<td>{escape(formatar_valor_tabela(coluna, linha[coluna]))}</td>"
        for coluna in df_cenarios.columns
    )
    linhas_html.append(f'<tr class="linha-{indice % 2}">{celulas}</tr>')

html_tabela = f"""
<div style="overflow-x:auto;width:100%;">
    <table class="synvitta-table" style="border-collapse:collapse;table-layout:fixed;width:100%;min-width:1180px;font-family:Segoe UI,Arial,sans-serif;">
    <thead><tr>{cabecalho_html}</tr></thead>
    <tbody>{''.join(linhas_html)}</tbody>
  </table>
</div>
<style>
    .synvitta-table, .synvitta-table * {{ box-sizing:border-box; writing-mode:horizontal-tb; transform:none; }}
    .synvitta-table th {{ background:#18364a;color:#fff;font-size:9px;font-weight:700;text-align:center;vertical-align:middle;white-space:normal;padding:8px 5px;border-right:1px solid #496174;line-height:1.25;overflow-wrap:anywhere; }}
    .synvitta-table td {{ color:#203040;font-size:10px;font-weight:700;text-align:center;vertical-align:middle;white-space:normal;padding:9px 5px;border-bottom:1px solid #d9e1e8;line-height:1.25;overflow-wrap:anywhere; }}
    .synvitta-table th:first-child, .synvitta-table td:first-child {{ width:180px;text-align:left; }}
    .synvitta-table .linha-1 {{ background:#f0f5f7; }}
</style>
"""
st.html(html_tabela)

# Gráfico executivo com valores destacados
chart_data = df_cenarios.set_index("Cenário Societário / Comercial")[[
    "Lucro Matriz EUA - Exportação (R$)",
    "Lucro Matriz Brasil (R$)",
    "Lucro Filial / Empresa Local Brasil (R$)",
]]
figura_lucros = go.Figure()
series_grafico = [
    ("Lucro Matriz EUA - Exportação (R$)", "Matriz EUA", "#2878a0"),
    ("Lucro Matriz Brasil (R$)", "Matriz Brasil", "#d78a36"),
    ("Lucro Filial / Empresa Local Brasil (R$)", "Filial Brasil", "#4e9a72"),
]
for coluna, nome, cor in series_grafico:
    valores = [float(valor) if pd.notna(valor) else None for valor in chart_data[coluna]]
    rotulos = [formatar_reais_grafico(valor) if valor is not None else "" for valor in valores]
    valores_exatos = [formatar_reais(valor) if valor is not None else "N/A" for valor in valores]
    figura_lucros.add_trace(go.Bar(
        name=nome,
        x=["Cenário 1", "Cenário 2"],
        y=valores,
        marker_color=cor,
        text=rotulos,
        textposition="outside",
        cliponaxis=False,
        customdata=valores_exatos,
        hovertemplate="<b>%{x}</b><br>%{fullData.name}: %{customdata}<extra></extra>",
    ))
figura_lucros.update_layout(
    template="plotly_white",
    barmode="group",
    height=420,
    margin={"l": 45, "r": 35, "t": 55, "b": 110},
    font={"family": "Aptos, Segoe UI, sans-serif", "size": 10, "color": "#203040"},
    title={"text": "Lucro por cenário e entidade", "x": 0.02, "font": {"size": 16}},
    legend={"orientation": "h", "yanchor": "top", "y": -0.22, "xanchor": "center", "x": 0.5},
    xaxis_title="Cenário",
    yaxis_title="Lucro (R$)",
    uniformtext_minsize=9,
    uniformtext_mode="hide",
)
figura_lucros.update_yaxes(tickprefix="R$ ", tickformat="~s", gridcolor="#e5ebef", zerolinecolor="#82909a", rangemode="tozero")
figura_lucros.update_xaxes(categoryorder="array", categoryarray=["Cenário 1", "Cenário 2"], automargin=True)
st.plotly_chart(figura_lucros, width="stretch", config={"displayModeBar": False, "responsive": True})

# Preparação das premissas para exportação
dados_premissas = pd.DataFrame([
    ["Número de kits", numero_kits, "kits"],
    ["Taxa de câmbio", cambio, "R$/USD"],
    ["Participação da matriz no cenário 1", pct_participacao_matriz_c1, "%"],
    ["Participação da filial no cenário 1", pct_participacao_filial_c1, "%"],
    ["Lucro líquido de referência para cenário 2", lucro_liquido_referencia_c2, "R$"],
    [
        "Lucro da filial como proporção do lucro de referência",
        lucro_filial_alvo_c2 / lucro_liquido_referencia_c2 if lucro_liquido_referencia_c2 else None,
        "%",
    ],
    ["Lucro-alvo da filial no cenário 2", lucro_filial_alvo_c2, "R$"],
    ["Faturamento bruto base (1.000 kits)", faturamento_base, "R$"],
    ["Faturamento bruto calculado", faturamento_bruto, "R$"],
    ["Custo de produção da matriz base (1.000 kits)", cogs_usd_base, "USD"],
    ["Custo de produção da matriz calculado", cogs_usd, "USD"],
    ["Preço FOB base (1.000 kits)", fob_usd_base, "USD"],
    ["Preço FOB calculado", fob_usd, "USD"],
    ["Preço FOB calculado para cenário 2", fob_usd_c2, "USD"],
    ["Dividendos líquidos remetidos à matriz (cenário 1)", dividendos_liquidos_c1, "R$"],
    ["Logística / internalização", pct_logistica, "%"],
    ["Operador logístico", pct_operador_log, "%"],
    ["OpEx local trimestral", opex_trimestral, "R$"],
    ["Carga tributária Brasil", pct_imposto_br, "%"],
    ["Imposto sobre dividendos", pct_retencao_div, "%"],
    ["Taxa cambial de remessa", pct_taxa_envio, "%"],
    ["Imposto corporativo EUA", pct_imposto_eua, "%"],
    ["Lucro operacional Brasil", lucro_operacional_br, "R$"],
    ["Landed cost calculado", landed_cost, "R$"],
    ["Impostos Brasil", imposto_br, "R$"],
    ["Lucro líquido Brasil", lucro_liquido_br, "R$"],
], columns=["Premissa", "Valor", "Unidade"])

# Exportação para Excel
excel_buffer = BytesIO()
with pd.ExcelWriter(excel_buffer, engine="openpyxl") as writer:
    df_cenarios.to_excel(writer, sheet_name="Cenários", index=False, na_rep="N/A")
    dados_premissas.to_excel(writer, sheet_name="Premissas", index=False)
    planilha_cenarios = writer.sheets["Cenários"]
    planilha_cenarios.freeze_panes = "A2"
    planilha_cenarios.auto_filter.ref = planilha_cenarios.dimensions
    for coluna, largura in {
        "A": 38, "B": 17, "C": 22, "D": 16, "E": 22, "F": 18,
        "G": 22, "H": 25, "I": 18, "J": 24, "K": 22, "L": 22,
    }.items():
        planilha_cenarios.column_dimensions[coluna].width = largura
    for linha in range(2, planilha_cenarios.max_row + 1):
        planilha_cenarios.cell(linha, 2).number_format = '"USD" #,##0.00'
        for coluna in (3, 5, 7, 8, 10, 11):
            planilha_cenarios.cell(linha, coluna).number_format = '"R$" #,##0.00'
        planilha_cenarios.cell(linha, 12).number_format = '0.00"x"'
        for coluna in (4, 6, 9):
            planilha_cenarios.cell(linha, coluna).number_format = '0.00"%"'
    for celula in planilha_cenarios[1]:
        celula.fill = PatternFill("solid", fgColor="18364A")
        celula.font = Font(name="Aptos", size=11, bold=True, color="FFFFFF")
        celula.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
    planilha_cenarios.row_dimensions[1].height = 42
    for linha in range(2, planilha_cenarios.max_row + 1):
        planilha_cenarios.row_dimensions[linha].height = 34
        for celula in planilha_cenarios[linha]:
            celula.font = Font(name="Aptos", size=11, bold=True, color="18364A")
            celula.fill = PatternFill("solid", fgColor="F0F5F7" if linha % 2 == 0 else "FFFFFF")
            celula.alignment = Alignment(
                horizontal="left" if celula.column == 1 else "center",
                vertical="center",
                wrap_text=True,
            )
            celula.border = Border(bottom=Side(style="thin", color="D9E1E8"))
    planilha_graficos = writer.book.create_sheet("Gráficos")
    grafico_excel = BarChart()
    grafico_excel.type = "bar"
    grafico_excel.grouping = "clustered"
    grafico_excel.style = 10
    grafico_excel.title = "Lucro por entidade e cenário"
    grafico_excel.x_axis.title = "Lucro (R$)"
    grafico_excel.x_axis.numFmt = '"R$" #,##0.00'
    grafico_excel.y_axis.title = "Cenário"
    grafico_excel.height = 9
    grafico_excel.width = 24
    for coluna in (3, 5, 8):
        dados_grafico = Reference(planilha_cenarios, min_col=coluna, min_row=1, max_row=3)
        grafico_excel.add_data(dados_grafico, titles_from_data=True)
    categorias_grafico = Reference(planilha_cenarios, min_col=1, min_row=2, max_row=3)
    grafico_excel.set_categories(categorias_grafico)
    grafico_excel.legend.position = "b"
    grafico_excel.dLbls = DataLabelList()
    grafico_excel.dLbls.showVal = True
    grafico_excel.dLbls.numFmt = '"R$" #,##0.00'
    planilha_graficos.add_chart(grafico_excel, "A1")
    planilha_premissas = writer.sheets["Premissas"]
    planilha_premissas.freeze_panes = "A2"
    planilha_premissas.auto_filter.ref = planilha_premissas.dimensions
    planilha_premissas.column_dimensions["A"].width = 34
    planilha_premissas.column_dimensions["B"].width = 22
    planilha_premissas.column_dimensions["C"].width = 14
    for linha in range(2, planilha_premissas.max_row + 1):
        unidade = planilha_premissas.cell(linha, 3).value
        if unidade == "%":
            planilha_premissas.cell(linha, 2).number_format = "0.00%"
        elif unidade in ("R$", "USD", "R$/USD"):
            planilha_premissas.cell(linha, 2).number_format = '#,##0.00'
    for celula in planilha_premissas[1]:
        celula.fill = PatternFill("solid", fgColor="18364A")
        celula.font = Font(name="Aptos", size=11, bold=True, color="FFFFFF")
        celula.alignment = Alignment(horizontal="center", vertical="center")
    planilha_premissas.row_dimensions[1].height = 28
    for linha in range(2, planilha_premissas.max_row + 1):
        for celula in planilha_premissas[linha]:
            celula.font = Font(name="Aptos", size=10, bold=True, color="18364A")
            celula.fill = PatternFill("solid", fgColor="F0F5F7" if linha % 2 == 0 else "FFFFFF")
            celula.alignment = Alignment(vertical="center", wrap_text=True)
            celula.border = Border(bottom=Side(style="thin", color="D9E1E8"))
excel_data = excel_buffer.getvalue()

# Exportação para PDF
pdf_buffer = BytesIO()
estilos = getSampleStyleSheet()
estilo_celula = estilos["BodyText"]
estilo_celula.fontSize = 8
estilo_celula.leading = 10
estilo_valor = ParagraphStyle(
    "ValorTabelaExecutiva",
    parent=estilo_celula,
    fontName="Helvetica-Bold",
    fontSize=9,
    leading=11,
    alignment=1,
)
estilo_cabecalho = ParagraphStyle(
    "CabecalhoTabela",
    parent=estilo_celula,
    textColor=colors.white,
    fontName="Helvetica-Bold",
)
elementos_pdf = [
    Paragraph("Synvitta - Relatório de Viabilidade", estilos["Title"]),
    Spacer(1, 12),
    Paragraph("Premissas da operação e resumo Brasil", estilos["Heading2"]),
]
linhas_premissas = [["Premissa", "Valor"]]
for _, premissa in dados_premissas.iterrows():
    valor = premissa["Valor"]
    unidade = premissa["Unidade"]
    if unidade == "%":
        valor_formatado = f"{valor:.2%}".replace(".", ",")
    elif unidade == "R$":
        valor_formatado = formatar_reais(valor)
    elif unidade == "USD":
        valor_formatado = f"USD {valor:,.2f}"
    elif unidade == "R$/USD":
        valor_formatado = f"R$ {valor:,.2f} / USD"
    else:
        valor_formatado = f"{valor:,} {unidade}"
    linhas_premissas.append([Paragraph(str(premissa["Premissa"]), estilo_celula), valor_formatado])

tabela_premissas = Table(linhas_premissas, colWidths=[300, 210], repeatRows=1)
tabela_premissas.setStyle(TableStyle([
    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#18364a")),
    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
    ("FONTSIZE", (0, 0), (-1, -1), 8),
    ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#eef3f5")]),
    ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#c8d2d8")),
    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ("LEFTPADDING", (0, 0), (-1, -1), 6),
    ("RIGHTPADDING", (0, 0), (-1, -1), 6),
    ("TOPPADDING", (0, 0), (-1, -1), 4),
    ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
]))
elementos_pdf.extend([
    tabela_premissas,
    Spacer(1, 14),
    Paragraph("Distribuição de lucros por cenário", estilos["Heading2"]),
])

grafico_pdf = VerticalBarChart()
grafico_pdf.x = 42
grafico_pdf.y = 46
grafico_pdf.width = 650
grafico_pdf.height = 150
grafico_pdf.data = [
    [lucro_fob_liq_eua, lucro_matriz_eua_c2 or 0],
    [lucro_matriz_br_c1, 0],
    [lucro_filial_br_c1, lucro_filial_br_c2 or 0],
]
grafico_pdf.categoryAxis.categoryNames = [
    "Cenário 1",
    "Cenário 2",
]
grafico_pdf.categoryAxis.labels.fontSize = 7
grafico_pdf.categoryAxis.labels.angle = 0
grafico_pdf.barLabelArray = [
    [formatar_reais_grafico(lucro_fob_liq_eua), formatar_reais_grafico(lucro_matriz_eua_c2 or 0)],
    [formatar_reais_grafico(lucro_matriz_br_c1), "N/A"],
    [formatar_reais_grafico(lucro_filial_br_c1), formatar_reais_grafico(lucro_filial_br_c2 or 0)],
]
grafico_pdf.barLabelFormat = "values"
grafico_pdf.barLabels.fontName = "Helvetica-Bold"
grafico_pdf.barLabels.fontSize = 6
grafico_pdf.barLabels.fillColor = colors.HexColor("#18364a")
grafico_pdf.barLabels.nudge = 3
lucros_grafico = [
    lucro_fob_liq_eua,
    lucro_matriz_eua_c2 or 0,
    lucro_matriz_br_c1,
    lucro_filial_br_c1,
    lucro_filial_br_c2 or 0,
]
grafico_pdf.valueAxis.valueMin = min(0, min(lucros_grafico))
maior_lucro = max(*lucros_grafico, 1)
grafico_pdf.valueAxis.valueMax = maior_lucro * 1.15
grafico_pdf.valueAxis.valueStep = max(maior_lucro / 5, 1)
grafico_pdf.valueAxis.labels.fontSize = 7
grafico_pdf.bars[0].fillColor = colors.HexColor("#2878a0")
grafico_pdf.bars[1].fillColor = colors.HexColor("#d78a36")
grafico_pdf.bars[2].fillColor = colors.HexColor("#4e9a72")
desenho_grafico_pdf = Drawing(740, 235)
desenho_grafico_pdf.add(grafico_pdf)
legenda_pdf = Legend()
legenda_pdf.x = 500
legenda_pdf.y = 215
legenda_pdf.colorNamePairs = [
    (colors.HexColor("#2878a0"), "Matriz EUA"),
    (colors.HexColor("#d78a36"), "Matriz Brasil"),
    (colors.HexColor("#4e9a72"), "Filial / empresa local Brasil"),
]
legenda_pdf.fontSize = 8
desenho_grafico_pdf.add(legenda_pdf)
elementos_pdf.append(desenho_grafico_pdf)
elementos_pdf.append(Paragraph("Resultado por cenário", estilos["Heading2"]))

cabecalhos_pdf = [Paragraph(str(coluna), estilo_cabecalho) for coluna in df_cenarios.columns]
linhas_cenarios_pdf = [cabecalhos_pdf]
for _, cenario in df_cenarios.iterrows():
    linhas_cenarios_pdf.append([
        Paragraph(str(cenario["Cenário Societário / Comercial"]), estilo_valor),
        Paragraph(f"USD {cenario['FOB do Cenário (USD)']:,.2f}" if pd.notna(cenario["FOB do Cenário (USD)"]) else "N/A", estilo_valor),
        Paragraph(formatar_reais(cenario["Lucro Matriz EUA - Exportação (R$)"]) if pd.notna(cenario["Lucro Matriz EUA - Exportação (R$)"]) else "N/A", estilo_valor),
        Paragraph(f"{cenario['Margem Matriz EUA s/ FOB (%)']:.2f}%".replace(".", ",") if pd.notna(cenario["Margem Matriz EUA s/ FOB (%)"]) else "N/A", estilo_valor),
        Paragraph(formatar_reais(cenario["Lucro Matriz Brasil (R$)"]) if pd.notna(cenario["Lucro Matriz Brasil (R$)"]) else "N/A", estilo_valor),
        Paragraph(f"{cenario['Margem Matriz Brasil s/ Faturamento (%)']:.2f}%".replace(".", ",") if pd.notna(cenario["Margem Matriz Brasil s/ Faturamento (%)"]) else "N/A", estilo_valor),
        Paragraph(formatar_reais(cenario["Lucro Total da Matriz (R$)"]) if pd.notna(cenario["Lucro Total da Matriz (R$)"]) else "N/A", estilo_valor),
        Paragraph(formatar_reais(cenario["Lucro Filial / Empresa Local Brasil (R$)"]) if pd.notna(cenario["Lucro Filial / Empresa Local Brasil (R$)"]) else "N/A", estilo_valor),
        Paragraph(f"{cenario['Margem Filial / Local s/ Faturamento (%)']:.2f}%".replace(".", ",") if pd.notna(cenario["Margem Filial / Local s/ Faturamento (%)"]) else "N/A", estilo_valor),
        Paragraph(formatar_reais(cenario["Lucro Global Consolidado (R$)"]) if pd.notna(cenario["Lucro Global Consolidado (R$)"]) else "N/A", estilo_valor),
        Paragraph(formatar_reais(cenario["Lucro Global por Kit (R$)"]) if pd.notna(cenario["Lucro Global por Kit (R$)"]) else "N/A", estilo_valor),
        Paragraph(f"{cenario['Markup s/ Landed Cost (x)']:.2f}x".replace(".", ",") if pd.notna(cenario["Markup s/ Landed Cost (x)"]) else "N/A", estilo_valor),
    ])

tabela_cenarios = Table(
    linhas_cenarios_pdf,
    colWidths=[118, 52, 63, 45, 63, 45, 66, 70, 45, 68, 60, 52],
    repeatRows=1,
)
tabela_cenarios.setStyle(TableStyle([
    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#18364a")),
    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
    ("FONTSIZE", (0, 0), (-1, 0), 8),
    ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#eef3f5")]),
    ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#c8d2d8")),
    ("ALIGN", (1, 1), (-1, -1), "RIGHT"),
    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ("LEFTPADDING", (0, 0), (-1, -1), 4),
    ("RIGHTPADDING", (0, 0), (-1, -1), 4),
    ("TOPPADDING", (0, 0), (-1, -1), 8),
    ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
]))
elementos_pdf.append(tabela_cenarios)
documento_pdf = SimpleDocTemplate(
    pdf_buffer,
    pagesize=landscape(A4),
    rightMargin=24,
    leftMargin=24,
    topMargin=24,
    bottomMargin=24,
)
documento_pdf.build(elementos_pdf)
pdf_data = pdf_buffer.getvalue()

# Relatórios HTML gravados ao lado deste script e disponíveis para download.
traducao_premissas = {
    "Número de kits": "Number of kits",
    "Taxa de câmbio": "Exchange rate",
    "Participação da matriz no cenário 1": "Parent company share in scenario 1",
    "Participação da filial no cenário 1": "Branch share in scenario 1",
    "Lucro líquido de referência para cenário 2": "Scenario 2 reference net profit",
    "Lucro da filial como proporção do lucro de referência": "Branch profit as a share of reference profit",
    "Lucro-alvo da filial no cenário 2": "Scenario 2 branch target profit",
    "Faturamento bruto base (1.000 kits)": "Base gross revenue (1,000 kits)",
    "Faturamento bruto calculado": "Calculated gross revenue",
    "Custo de produção da matriz base (1.000 kits)": "Parent company base production cost (1,000 kits)",
    "Custo de produção da matriz calculado": "Calculated parent company production cost",
    "Preço FOB base (1.000 kits)": "Base FOB price (1,000 kits)",
    "Preço FOB calculado": "Calculated FOB price",
    "Preço FOB calculado para cenário 2": "Calculated FOB price for scenario 2",
    "Dividendos líquidos remetidos à matriz (cenário 1)": "Net dividends remitted to parent company (scenario 1)",
    "Logística / internalização": "Logistics / import handling",
    "Operador logístico": "Logistics operator",
    "OpEx local trimestral": "Quarterly local operating expenses",
    "Carga tributária Brasil": "Brazil tax burden",
    "Imposto sobre dividendos": "Dividend tax",
    "Taxa cambial de remessa": "Remittance foreign exchange fee",
    "Imposto corporativo EUA": "U.S. corporate tax",
    "Lucro operacional Brasil": "Brazil operating profit",
    "Landed cost calculado": "Calculated landed cost",
    "Impostos Brasil": "Brazil taxes",
    "Lucro líquido Brasil": "Brazil net profit",
}
traducao_colunas_cenarios = {
    "Cenário Societário / Comercial": "Business / ownership scenario",
    "FOB do Cenário (USD)": "Scenario FOB (USD)",
    "Lucro Matriz EUA - Exportação (R$)": "U.S. parent export profit (BRL)",
    "Margem Matriz EUA s/ FOB (%)": "U.S. parent margin on FOB (%)",
    "Lucro Matriz Brasil (R$)": "Brazil parent profit (BRL)",
    "Margem Matriz Brasil s/ Faturamento (%)": "Brazil parent margin on revenue (%)",
    "Lucro Total da Matriz (R$)": "Total parent company profit (BRL)",
    "Lucro Filial / Empresa Local Brasil (R$)": "Brazil branch / local company profit (BRL)",
    "Margem Filial / Local s/ Faturamento (%)": "Branch / local company margin on revenue (%)",
    "Lucro Global Consolidado (R$)": "Consolidated global profit (BRL)",
    "Lucro Global por Kit (R$)": "Global profit per kit (BRL)",
    "Markup s/ Landed Cost (x)": "Markup / landed cost (x)",
}
cenarios_html_pt = df_cenarios.copy()
for coluna in cenarios_html_pt.columns:
    cenarios_html_pt[coluna] = cenarios_html_pt[coluna].map(
        lambda valor, nome_coluna=coluna: formatar_valor_tabela(nome_coluna, valor)
    )
cenarios_html_en = cenarios_html_pt.rename(columns=traducao_colunas_cenarios)
cenarios_html_en["Business / ownership scenario"] = cenarios_html_en[
    "Business / ownership scenario"
].replace({
    "1. Subsidiária Controlada": "1. Controlled Subsidiary",
    "2. Distribuidor Independente": "2. Independent Distributor",
})

premissas_html_pt = dados_premissas.copy()
premissas_html_pt["Valor"] = premissas_html_pt.apply(
    lambda linha: (
        f"{linha['Valor']:.2%}".replace(".", ",") if linha["Unidade"] == "%"
        else formatar_reais(linha["Valor"]) if linha["Unidade"] == "R$"
        else f"USD {linha['Valor']:,.2f}" if linha["Unidade"] == "USD"
        else f"{formatar_reais(linha['Valor'])} / USD" if linha["Unidade"] == "R$/USD"
        else f"{linha['Valor']:,} {linha['Unidade']}"
    ) if pd.notna(linha["Valor"]) else "N/A",
    axis=1,
)
premissas_html_en = premissas_html_pt.rename(columns={
    "Premissa": "Assumption", "Valor": "Value", "Unidade": "Unit"
}).copy()
premissas_html_en["Assumption"] = premissas_html_en["Assumption"].replace(traducao_premissas)
premissas_html_en["Unit"] = premissas_html_en["Unit"].replace({"kits": "kits"})

figura_lucros_en = go.Figure(figura_lucros)
nomes_series_en = {
    "Matriz EUA": "U.S. Parent Company",
    "Matriz Brasil": "Brazil Parent Company",
    "Filial Brasil": "Brazil Branch / Local Company",
}
for serie in figura_lucros_en.data:
    serie.name = nomes_series_en.get(serie.name, serie.name)
    serie.x = ["Scenario 1" if valor == "Cenário 1" else "Scenario 2" for valor in serie.x]
figura_lucros_en.update_layout(
    title_text="Profit by scenario and entity",
    xaxis_title="Scenario",
    yaxis_title="Profit (BRL)",
)

def montar_relatorio_html(titulo: str, subtitulo: str, resumo: list[tuple[str, str]], premissas: pd.DataFrame,
                          cenarios: pd.DataFrame, grafico: go.Figure, ingles: bool) -> str:
    resumo_html = "".join(
        f"<tr><th>{escape(rotulo)}</th><td>{escape(valor)}</td></tr>"
        for rotulo, valor in resumo
    )
    grafico_html = grafico.to_html(full_html=False, include_plotlyjs="cdn")
    return f"""<!doctype html>
<html lang="{'en' if ingles else 'pt-BR'}"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>{escape(titulo)}</title>
<style>
body{{font-family:Segoe UI,Arial,sans-serif;color:#203040;background:#f5f7f8;margin:0;padding:24px}}
main{{max-width:1500px;margin:auto}}h1,h2{{color:#18364a}}h1{{font-size:26px}}h2{{font-size:19px;margin-top:30px}}
.report-table{{border-collapse:collapse;width:100%;background:white;font-size:13px}}
.report-table th{{background:#18364a;color:white;text-align:left}}
.report-table th,.report-table td{{padding:9px 10px;border:1px solid #d9e1e8;vertical-align:top}}
.report-table tbody tr:nth-child(even){{background:#f0f5f7}}
.note{{color:#52606d;font-size:12px}}.chart{{background:white;padding:8px;border:1px solid #d9e1e8}}
.scroll{{overflow-x:auto}}@media print{{body{{background:white;padding:0}}}}
</style></head><body><main><h1>{escape(titulo)}</h1><p class="note">{escape(subtitulo)}</p>
<h2>{'Operating summary (Brazil)' if ingles else 'Resumo operacional (Brasil)'}</h2>
<table class="report-table"><tbody>{resumo_html}</tbody></table>
<h2>{'Profit distribution by scenario' if ingles else 'Distribuição de lucros por cenário'}</h2>
<div class="chart">{grafico_html}</div>
<h2>{'Scenario comparison' if ingles else 'Comparativo dos cenários'}</h2>
<div class="scroll">{cenarios.to_html(index=False, border=0, classes='report-table', escape=True, na_rep='N/A')}</div>
<h2>{'Assumptions' if ingles else 'Premissas'}</h2>
<div class="scroll">{premissas.to_html(index=False, border=0, classes='report-table', escape=True, na_rep='N/A')}</div>
</main></body></html>"""

resumo_html_pt = [
    ("Faturamento Bruto (R$)", formatar_reais(faturamento_bruto)),
    ("Acomodação / Operador (R$)", formatar_reais(custo_operador_log)),
    ("Landed Cost (R$)", formatar_reais(landed_cost)),
    ("Lucro Operacional (R$)", formatar_reais(lucro_operacional_br)),
    (f"Impostos BR ({pct_imposto_br:.0%})", formatar_reais(imposto_br)),
    ("Lucro Líquido BR (100%)", formatar_reais(lucro_liquido_br)),
]
resumo_html_en = [
    ("Gross revenue (BRL)", formatar_reais(faturamento_bruto)),
    ("Logistics operator (BRL)", formatar_reais(custo_operador_log)),
    ("Landed cost (BRL)", formatar_reais(landed_cost)),
    ("Operating profit (BRL)", formatar_reais(lucro_operacional_br)),
    (f"Brazil taxes ({pct_imposto_br:.0%})", formatar_reais(imposto_br)),
    ("Brazil net profit (100%)", formatar_reais(lucro_liquido_br)),
]
relatorio_html_pt = montar_relatorio_html(
    "Synvitta - Relatório de Viabilidade", "Relatório gerencial baseado nas premissas informadas.",
    resumo_html_pt, premissas_html_pt, cenarios_html_pt, figura_lucros, False,
)
relatorio_html_en = montar_relatorio_html(
    "Synvitta - Feasibility Report", "Management report based on the assumptions provided.",
    resumo_html_en, premissas_html_en, cenarios_html_en, figura_lucros_en, True,
)
campos_calculadora = [
    field("cambio", "Taxa de câmbio (USD/BRL)", "Exchange rate (USD/BRL)", cambio, "Comercial e cambial", "Commercial and exchange", step="0.01", minimum=0.01),
    field("numero_kits", "Número de kits", "Number of kits", numero_kits, "Comercial e cambial", "Commercial and exchange", step=100, minimum=1),
    field("faturamento_base", "Faturamento bruto base (R$ / 1.000 kits)", "Base gross revenue (BRL / 1,000 kits)", faturamento_base, "Comercial e cambial", "Commercial and exchange", step=100000, minimum=0),
    field("cogs_usd_base", "Custo de produção da matriz (USD / 1.000 kits)", "Parent company production cost (USD / 1,000 kits)", cogs_usd_base, "Comercial e cambial", "Commercial and exchange", step=10000, minimum=0),
    field("fob_usd_base", "FOB base (USD / 1.000 kits)", "Base FOB (USD / 1,000 kits)", fob_usd_base, "Custos operacionais e logística", "Operating costs and logistics", step=10000, minimum=0),
    field("pct_logistica", "Logística / internalização (% s/ FOB)", "Logistics / import handling (% of FOB)", pct_logistica, "Custos operacionais e logística", "Operating costs and logistics", scale=100, step=1, minimum=0, maximum=500),
    field("pct_operador_log", "Acomodação / operador logístico (% s/ faturamento)", "Logistics operator (% of revenue)", pct_operador_log, "Custos operacionais e logística", "Operating costs and logistics", scale=100, step=0.1, minimum=0, maximum=100),
    field("opex_trimestral", "OpEx local trimestral (R$)", "Quarterly local operating expenses (BRL)", opex_trimestral, "Custos operacionais e logística", "Operating costs and logistics", step=10000, minimum=0),
    field("pct_imposto_br", "Carga tributária Brasil (% s/ lucro operacional)", "Brazil tax on operating profit (%)", pct_imposto_br, "Impostos e remessas", "Taxes and remittances", scale=100, step=0.1, minimum=0, maximum=100),
    field("pct_retencao_div", "Imposto s/ distribuição de dividendos BR (%)", "Brazil dividend withholding tax (%)", pct_retencao_div, "Impostos e remessas", "Taxes and remittances", scale=100, step=0.1, minimum=0, maximum=100),
    field("pct_taxa_envio", "Taxa cambial de remessa (%)", "Remittance foreign exchange fee (%)", pct_taxa_envio, "Impostos e remessas", "Taxes and remittances", scale=100, step=0.1, minimum=0, maximum=100),
    field("pct_imposto_eua", "Imposto corporativo Flórida/EUA (%)", "Florida/U.S. corporate tax (%)", pct_imposto_eua, "Impostos e remessas", "Taxes and remittances", scale=100, step=0.1, minimum=0, maximum=100),
    field("pct_participacao_matriz_c1", "Participação da matriz no cenário 1 (%)", "Parent company share in scenario 1 (%)", pct_participacao_matriz_c1, "Cenários", "Scenarios", scale=100, step=5, minimum=0, maximum=100),
    field("fob_usd_c2", "FOB da matriz no cenário 2 (USD)", "Parent company FOB in scenario 2 (USD)", fob_usd_c2, "Cenários", "Scenarios", step=10000, minimum=0),
]
relatorio_html_pt = build_calculator_html(
    model_id="synvitta",
    language="pt",
    title="Synvitta - Simulação simplificada",
    fields=campos_calculadora,
    calculation_js=synvitta_calculation_js(),
)
relatorio_html_en = build_calculator_html(
    model_id="synvitta",
    language="en",
    title="Synvitta - Simplified Simulation",
    fields=campos_calculadora,
    calculation_js=synvitta_calculation_js(),
)
try:
    pasta_relatorios = Path(__file__).resolve().parent
    (pasta_relatorios / "relatorio_synvitta.html").write_text(relatorio_html_pt, encoding="utf-8")
    (pasta_relatorios / "synvitta_report.htm").write_text(relatorio_html_en, encoding="utf-8")
    status_relatorio = "Arquivos HTML/HTM atualizados na pasta do Synvitta."
except OSError as erro_gravacao:
    status_relatorio = f"Não foi possível gravar os arquivos na pasta do app: {erro_gravacao}"

# Downloads dos relatórios
csv = df_cenarios.to_csv(index=False, na_rep="N/A").encode("utf-8")
col_csv, col_excel, col_pdf, col_html, col_english = st.columns(5)
col_csv.download_button(
    label="📥 Baixar CSV",
    data=csv,
    file_name="simulacao_synvitta.csv",
    mime="text/csv",
    use_container_width=True,
)
col_excel.download_button(
    label="📊 Baixar relatório Excel",
    data=excel_data,
    file_name="relatorio_synvitta.xlsx",
    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    use_container_width=True,
)
col_pdf.download_button(
    label="📄 Baixar relatório PDF",
    data=pdf_data,
    file_name="relatorio_synvitta.pdf",
    mime="application/pdf",
    use_container_width=True,
)
col_html.download_button(
    label="Baixar relatório HTML",
    data=relatorio_html_pt.encode("utf-8"),
    file_name="relatorio_synvitta.html",
    mime="text/html",
    width="stretch",
)
col_english.download_button(
    label="Download English report",
    data=relatorio_html_en.encode("utf-8"),
    file_name="synvitta_report.htm",
    mime="text/html",
    width="stretch",
)
st.caption(status_relatorio)