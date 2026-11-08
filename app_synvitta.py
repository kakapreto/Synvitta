import io
import json
import os
import pandas as pd
import plotly.express as px
import streamlit as st
from google import genai
from google.genai import types
from pydantic import BaseModel, Field

# =====================================================================
# CONFIGURAÇÃO DA PÁGINA STREAMLIT
# =====================================================================
st.set_page_config(
    page_title="Synvitta L.A. - Landed Cost & DRE IA",
    page_icon="🧬",
    layout="wide",
    initial_sidebar_state="expanded"
)

# =====================================================================
# GERENCIAMENTO DE ESTADO E CENÁRIOS PADRÃO
# =====================================================================
DEFAULT_JSON_PATH = "dados_entrada.json"

def carregar_dados_iniciais():
    if os.path.exists(DEFAULT_JSON_PATH):
        try:
            with open(DEFAULT_JSON_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {
        "parametros_globais": {
            "empresa": "Synvitta L.A. Ltda.",
            "ptax": 5.60,
            "uf_destino": "SP",
            "incoterm": "EXW",
            "hub_nacionalizacao": "Guarulhos/SP"
        },
        "custos_compartilhados_usd": {
            "frete_internacional_aereo": 9000.00,
            "frete_origem": 1500.00,
            "seguro_internacional": 500.00,
            "despacho_miami": 500.00,
            "locacao_uld_rap": 5000.00
        },
        "custos_compartilhados_brl": {
            "armazenagem_terminal": 21000.00,
            "despachante_aduaneiro": 7000.00,
            "taxa_siscomex": 230.00,
            "taxa_anvisa": 536.00
        },
        "produtos": [
            {
                "nome_produto": "Kit Reagente / Diagnóstico",
                "ncm": "3822.19.90",
                "quantidade": 1440,
                "preco_unitario_exw_usd": 200.00,
                "preco_venda_unitario_brl": 9600.00,
                "frete_interno_hub_brl": 1200.00,
                "aliquotas_importacao": {"ii": 0.0, "ipi": 0.0, "pis": 0.0, "cofins": 0.0, "icms": 0.0},
                "creditos_importacao": {"credita_ipi": False, "credita_icms": False},
                "aliquotas_venda": {"icms": 0.04, "pis": 0.0065, "cofins": 0.03, "operador_var": 0.04}
            },
            {
                "nome_produto": "Leitor Óptico",
                "ncm": "9027.50.20",
                "quantidade": 160,
                "preco_unitario_exw_usd": 5000.00,
                "preco_venda_unitario_brl": 280000.00,
                "frete_interno_hub_brl": 800.00,
                "aliquotas_importacao": {"ii": 0.14, "ipi": 0.0975, "pis": 0.021, "cofins": 0.0965, "icms": 0.18},
                "creditos_importacao": {"credita_ipi": True, "credita_icms": True},
                "aliquotas_venda": {"icms": 0.18, "pis": 0.0065, "cofins": 0.03, "operador_var": 0.0}
            }
        ],
        "estrutura_opex_e_societaria": {
            "opex_fixo_mensal_brl": 200000.00,
            "meses_operacao": 1,
            "participacao_matriz_eua_pct": 0.75,
            "participacao_socios_locais_sp_pct": 0.25,
            "retencao_dividendos_pct": 0.10,
            "custo_remessa_pct": 0.01
        }
    }

if "cenario" not in st.session_state:
    st.session_state["cenario"] = carregar_dados_iniciais()

# =====================================================================
# SCHEMAS PYDANTIC (ESTRUTURAS ESTREITAS)
# =====================================================================
class LandedCostProduto(BaseModel):
    nome_produto: str
    ncm: str
    quantidade: float
    valor_exw_total_usd: float
    cif_total_brl: float
    landed_cost_bruto_total_brl: float
    creditos_tributarios_recuperaveis_brl: float
    custo_estoque_liquido_cmv_brl: float
    custo_unitario_cmv_brl: float

class LandedCostLoteConsolidado(BaseModel):
    ptax_utilizada: float
    valor_exw_total_lote_usd: float
    cif_total_lote_brl: float
    landed_cost_bruto_lote_brl: float
    creditos_totais_lote_brl: float
    custo_estoque_liquido_lote_brl: float
    produtos: list[LandedCostProduto]

class DREItemProduto(BaseModel):
    nome_produto: str
    unidades_vendidas: float
    receita_bruta_brl: float
    tributos_venda_brl: float
    receita_liquida_brl: float
    cmv_brl: float
    lucro_bruto_brl: float
    margem_contribucao_pct: float

class DREDetalhadaRegime(BaseModel):
    regime_tributario: str
    receita_bruta_total_brl: float
    tributos_venda_total_brl: float
    receita_liquida_total_brl: float
    cmv_total_brl: float
    lucro_bruto_total_brl: float
    opex_fixo_brl: float
    operacao_variavel_brl: float
    ebitda_brl: float
    irpj_csll_brl: float
    lucro_liquido_brasil_brl: float
    margem_liquida_pct: float
    remessa_matriz_eua_brl: float
    lucro_retido_filial_sp_brl: float
    itens_produtos: list[DREItemProduto]

class DREReportSynvitta(BaseModel):
    projeto: str = "synvitta3_report"
    empresa: str = "Synvitta L.A. Ltda."
    ptax: float
    lucro_real: DREDetalhadaRegime
    lucro_presumido: DREDetalhadaRegime
    regime_recomendado: str = Field(description="Recomendação tributária fundamentada em 1 frase.")
    economia_tributaria_anual_estimada_brl: float

# =====================================================================
# FUNÇÃO DO PIPELINE DE IA (2 AGENTES GEMINI)
# =====================================================================
def executar_pipeline_ia(api_key: str, payload_importacao: dict, payload_comercial: dict) -> DREReportSynvitta:
    client = genai.Client(api_key=api_key)

    prompt_agente1 = """
    Você é o Engenheiro Financeiro Aduaneiro da Synvitta L.A.
    Calcule o rateio aduaneiro por NCM e o Landed Cost (EXW -> Hub Guarulhos/SP).
    Responda EXCLUSIVAMENTE com o JSON do schema LandedCostLoteConsolidado.
    """
    res_landed = client.models.generate_content(
        model='gemini-3.8-flash',
        contents=json.dumps(payload_importacao),
        config=types.GenerateContentConfig(
            system_instruction=prompt_agente1,
            response_mime_type="application/json",
            response_schema=LandedCostLoteConsolidado,
            temperature=0.0
        )
    )
    landed_json = json.loads(res_landed.text)

    payload_comercial["landed_cost_input"] = landed_json
    prompt_agente2 = """
    Você é o Controller Financeiro e Tributarista da Synvitta L.A.
    Gere a DRE comparativa (Lucro Real vs. Presumido) utilizando o CMV calculado no Landed Cost.
    Considere créditos na importação (Lucro Real) e regras de presunção (Lucro Presumido).
    Responda EXCLUSIVAMENTE com o JSON do schema DREReportSynvitta.
    """
    res_dre = client.models.generate_content(
        model='gemini-3.8-flash',
        contents=json.dumps(payload_comercial),
        config=types.GenerateContentConfig(
            system_instruction=prompt_agente2,
            response_mime_type="application/json",
            response_schema=DREReportSynvitta,
            temperature=0.0
        )
    )
    return DREReportSynvitta.model_validate_json(res_dre.text)

# =====================================================================
# GERADOR DE EXCEL EM MEMÓRIA
# =====================================================================
def gerar_excel_bytes(dre_data: DREReportSynvitta) -> bytes:
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df_resumo = pd.DataFrame([
            {"Parâmetro": "Empresa", "Valor": dre_data.empresa},
            {"Parâmetro": "Taxa de Câmbio (PTAX)", "Valor": f"R$ {dre_data.ptax:.2f}"},
            {"Parâmetro": "Regime Recomendado", "Valor": dre_data.regime_recomendado},
            {"Parâmetro": "Economia Estimada (BRL)", "Valor": dre_data.economia_tributaria_anual_estimada_brl}
        ])
        df_resumo.to_excel(writer, sheet_name="Resumo", index=False)

        lr, lp = dre_data.lucro_real, dre_data.lucro_presumido
        df_dre = pd.DataFrame({
            "Linha DRE": [
                "Receita Bruta", "(-) Impostos sobre Vendas", "(=) Receita Líquida",
                "(-) CMV Nacionalizado", "(=) Lucro Bruto", "(-) Opex Fixo",
                "(-) Operação Variável", "(=) EBITDA", "(-) IRPJ / CSLL", "(=) Lucro Líquido Brasil",
                "Remessa Matriz EUA (75%)", "Retido Filial SP (25%)"
            ],
            "Lucro Real (R$)": [
                lr.receita_bruta_total_brl, lr.tributos_venda_total_brl, lr.receita_liquida_total_brl,
                lr.cmv_total_brl, lr.lucro_bruto_total_brl, lr.opex_fixo_brl,
                lr.operacao_variavel_brl, lr.ebitda_brl, lr.irpj_csll_brl, lr.lucro_liquido_brasil_brl,
                lr.remessa_matriz_eua_brl, lr.lucro_retido_filial_sp_brl
            ],
            "Lucro Presumido (R$)": [
                lp.receita_bruta_total_brl, lp.tributos_venda_total_brl, lp.receita_liquida_total_brl,
                lp.cmv_total_brl, lp.lucro_bruto_total_brl, lp.opex_fixo_brl,
                lp.operacao_variavel_brl, lp.ebitda_brl, lp.irpj_csll_brl, lp.lucro_liquido_brasil_brl,
                lp.remessa_matriz_eua_brl, lp.lucro_retido_filial_sp_brl
            ]
        })
        df_dre.to_excel(writer, sheet_name="DRE_Comparativa", index=False)

        if lr.itens_produtos:
            df_prod = pd.DataFrame([p.model_dump() for p in lr.itens_produtos])
            df_prod.to_excel(writer, sheet_name="Produtos_LucroReal", index=False)

    return output.getvalue()

# =====================================================================
# SIDEBAR - AUTENTICAÇÃO E GESTÃO DE CENÁRIOS JSON
# =====================================================================
st.sidebar.title("🧬 Synvitta L.A. - Painel")

api_key_env = st.secrets.get("GEMINI_API_KEY", "")
user_api_key = st.sidebar.text_input("Chave da API Gemini", value=api_key_env, type="password")

st.sidebar.subheader("📂 Gestão de Cenários (JSON)")

# Upload de Cenário
uploaded_file = st.sidebar.file_uploader("Importar Cenário JSON", type=["json"])
if uploaded_file is not None:
    try:
        cenario_carregado = json.load(uploaded_file)
        st.session_state["cenario"] = cenario_carregado
        st.sidebar.success("✅ Cenário importado com sucesso!")
    except Exception as e:
        st.sidebar.error(f"Erro ao ler JSON: {e}")

# Exportação de Cenário
cenario_json_bytes = json.dumps(st.session_state["cenario"], indent=2, ensure_ascii=False).encode("utf-8")
st.sidebar.download_button(
    label="💾 Baixar Cenário Atual (JSON)",
    data=cenario_json_bytes,
    file_name="cenario_synvitta.json",
    mime="application/json",
    use_container_width=True
)

btn_calcular = st.sidebar.button("🚀 Executar Simulação via IA", type="primary", use_container_width=True)

# =====================================================================
# PAINEL PRINCIPAL - ABAS VISUAIS DE ENTRADA DE DADOS
# =====================================================================
st.title("🧬 Synvitta L.A. — Simulador Integrado de IA & DRE")
st.caption("Automação de Landed Cost Multiproduto + Comparativo Tributário Lucro Real vs. Presumido")

# Atalho rápido do cenário em memória
cen = st.session_state["cenario"]

tab_globais, tab_fretes, tab_prod1, tab_prod2, tab_opex = st.tabs([
    "🌐 1. Câmbio & Localização",
    "✈️ 2. Fretes & Despesas Aduaneiras",
    "📦 3. Kit Reagente",
    "🔬 4. Leitor Óptico",
    "🏢 5. Opex & Regras Societárias"
])

# ---------------------------------------------------------------------
# Aba 1: Parâmetros Globais
# ---------------------------------------------------------------------
with tab_globais:
    st.subheader("Parâmetros Gerais do Lote")
    col1, col2, col3 = st.columns(3)
    cen["parametros_globais"]["empresa"] = col1.text_input("Empresa", value=cen["parametros_globais"].get("empresa", "Synvitta L.A. Ltda."))
    cen["parametros_globais"]["ptax"] = col2.number_input("Câmbio PTAX (BRL/USD)", value=float(cen["parametros_globais"].get("ptax", 5.60)), step=0.05)
    cen["parametros_globais"]["uf_destino"] = col3.selectbox("UF de Destino", ["SP", "MG", "RJ", "PR", "SC"], index=0)

# ---------------------------------------------------------------------
# Aba 2: Fretes e Custos Compartilhados
# ---------------------------------------------------------------------
with tab_fretes:
    st.subheader("Custos Compartilhados da Operação")
    col_usd, col_brl = st.columns(2)

    with col_usd:
        st.markdown("**Custos em USD (Origem / Trecho Internacional)**")
        c_usd = cen["custos_compartilhados_usd"]
        c_usd["frete_internacional_aereo"] = st.number_input("Frete Internacional Aéreo (USD)", value=float(c_usd.get("frete_internacional_aereo", 9000.0)))
        c_usd["frete_origem"] = st.number_input("Frete de Origem (USD)", value=float(c_usd.get("frete_origem", 1500.0)))
        c_usd["seguro_internacional"] = st.number_input("Seguro Internacional (USD)", value=float(c_usd.get("seguro_internacional", 500.0)))
        c_usd["despacho_miami"] = st.number_input("Despacho Miami (USD)", value=float(c_usd.get("despacho_miami", 500.0)))
        c_usd["locacao_uld_rap"] = st.number_input("Locação ULD/RAP (USD)", value=float(c_usd.get("locacao_uld_rap", 5000.0)))

    with col_brl:
        st.markdown("**Custos em BRL (Despesas Locais Terminal / Despacho)**")
        c_brl = cen["custos_compartilhados_brl"]
        c_brl["armazenagem_terminal"] = st.number_input("Armazenagem Terminal (R$)", value=float(c_brl.get("armazenagem_terminal", 21000.0)))
        c_brl["despachante_aduaneiro"] = st.number_input("Despachante Aduaneiro (R$)", value=float(c_brl.get("despachante_aduaneiro", 7000.0)))
        c_brl["taxa_siscomex"] = st.number_input("Taxa Siscomex (R$)", value=float(c_brl.get("taxa_siscomex", 230.0)))
        c_brl["taxa_anvisa"] = st.number_input("Taxa ANVISA (R$)", value=float(c_brl.get("taxa_anvisa", 536.0)))

# ---------------------------------------------------------------------
# Aba 3: Produto 1 (Kit Reagente)
# ---------------------------------------------------------------------
with tab_prod1:
    st.subheader("Produto 1: Kit Reagente / Diagnóstico")
    p1 = cen["produtos"][0]
    
    c1, c2, c3 = st.columns(3)
    p1["ncm"] = c1.text_input("NCM (Prod 1)", value=p1.get("ncm", "3822.19.90"))
    p1["quantidade"] = c2.number_input("Quantidade Importada (Kits)", value=int(p1.get("quantidade", 1440)))
    p1["frete_interno_hub_brl"] = c3.number_input("Frete Interno Hub/SP (R$)", value=float(p1.get("frete_interno_hub_brl", 1200.0)))

    c4, c5 = st.columns(2)
    p1["preco_unitario_exw_usd"] = c4.number_input("Preço Unitário EXW (USD)", value=float(p1.get("preco_unitario_exw_usd", 200.0)))
    p1["preco_venda_unitario_brl"] = c5.number_input("Preço de Venda BR (R$/kit)", value=float(p1.get("preco_venda_unitario_brl", 9600.0)))

    st.markdown("---")
    st.markdown("**Alíquotas de Importação & Vendas (Kit Reagente)**")
    ca1, ca2, ca3, ca4 = st.columns(4)
    p1["aliquotas_importacao"]["ii"] = ca1.number_input("II Importação (%)", value=float(p1["aliquotas_importacao"].get("ii", 0.0)) * 100) / 100
    p1["aliquotas_importacao"]["ipi"] = ca2.number_input("IPI Importação (%)", value=float(p1["aliquotas_importacao"].get("ipi", 0.0)) * 100) / 100
    p1["aliquotas_venda"]["icms"] = ca3.number_input("ICMS Saída (%)", value=float(p1["aliquotas_venda"].get("icms", 0.04)) * 100) / 100
    p1["aliquotas_venda"]["operador_var"] = ca4.number_input("Comissão Operador Var (%)", value=float(p1["aliquotas_venda"].get("operador_var", 0.04)) * 100) / 100

# ---------------------------------------------------------------------
# Aba 4: Produto 2 (Leitor Óptico)
# ---------------------------------------------------------------------
with tab_prod2:
    st.subheader("Produto 2: Leitor Óptico")
    p2 = cen["produtos"][1]
    
    c1, c2, c3 = st.columns(3)
    p2["ncm"] = c1.text_input("NCM (Prod 2)", value=p2.get("ncm", "9027.50.20"))
    p2["quantidade"] = c2.number_input("Quantidade Importada (Unidades)", value=int(p2.get("quantidade", 160)))
    p2["frete_interno_hub_brl"] = c3.number_input("Frete Interno Hub/SP (R$)", value=float(p2.get("frete_interno_hub_brl", 800.0)))

    c4, c5 = st.columns(2)
    p2["preco_unitario_exw_usd"] = c4.number_input("Preço Unitário EXW (USD/unid)", value=float(p2.get("preco_unitario_exw_usd", 5000.0)))
    p2["preco_venda_unitario_brl"] = c5.number_input("Preço de Venda BR (R$/unid)", value=float(p2.get("preco_venda_unitario_brl", 280000.0)))

    st.markdown("---")
    st.markdown("**Alíquotas de Importação (Leitor Óptico)**")
    ca1, ca2, ca3, ca4, ca5 = st.columns(5)
    p2["aliquotas_importacao"]["ii"] = ca1.number_input("II Importação (%)", value=float(p2["aliquotas_importacao"].get("ii", 0.14)) * 100) / 100
    p2["aliquotas_importacao"]["ipi"] = ca2.number_input("IPI Importação (%)", value=float(p2["aliquotas_importacao"].get("ipi", 0.0975)) * 100) / 100
    p2["aliquotas_importacao"]["pis"] = ca3.number_input("PIS Importação (%)", value=float(p2["aliquotas_importacao"].get("pis", 0.021)) * 100) / 100
    p2["aliquotas_importacao"]["cofins"] = ca4.number_input("COFINS Importação (%)", value=float(p2["aliquotas_importacao"].get("cofins", 0.0965)) * 100) / 100
    p2["aliquotas_importacao"]["icms"] = ca5.number_input("ICMS Importação SP (%)", value=float(p2["aliquotas_importacao"].get("icms", 0.18)) * 100) / 100

# ---------------------------------------------------------------------
# Aba 5: Opex e Estrutura Societária
# ---------------------------------------------------------------------
with tab_opex:
    st.subheader("Estrutura Fixa Operacional e Regras de Dividendos")
    soc = cen["estrutura_opex_e_societaria"]
    
    c1, c2, c3 = st.columns(3)
    soc["opex_fixo_mensal_brl"] = c1.number_input("Opex Fixo Mensal (R$)", value=float(soc.get("opex_fixo_mensal_brl", 200000.0)), step=10000.0)
    soc["participacao_matriz_eua_pct"] = c2.number_input("Participação Matriz EUA (%)", value=float(soc.get("participacao_matriz_eua_pct", 0.75)) * 100) / 100
    soc["participacao_socios_locais_sp_pct"] = c3.number_input("Participação Sócios SP (%)", value=float(soc.get("participacao_socios_locais_sp_pct", 0.25)) * 100) / 100

st.markdown("---")

# =====================================================================
# PROCESSAMENTO DA SIMULAÇÃO
# =====================================================================
if btn_calcular:
    if not user_api_key:
        st.error("⚠️ Insira uma chave válida da API do Gemini na barra lateral para rodar a simulação.")
    else:
        with st.spinner("Conectando aos Agentes de IA e processando memória de cálculo aduaneira e fiscal..."):
            try:
                # Montagem automática dos Payloads atualizados a partir do Session State
                payload_imp = {
                    "ptax": cen["parametros_globais"]["ptax"],
                    "uf_destino": cen["parametros_globais"]["uf_destino"],
                    "custos_compartilhados_usd": cen["custos_compartilhados_usd"],
                    "custos_compartilhados_brl": cen["custos_compartilhados_brl"],
                    "produtos": [
                        {
                            "nome_produto": cen["produtos"][0]["nome_produto"],
                            "ncm": cen["produtos"][0]["ncm"],
                            "quantidade": cen["produtos"][0]["quantidade"],
                            "preco_unitario_exw_usd": cen["produtos"][0]["preco_unitario_exw_usd"],
                            "frete_interno_hub_brl": cen["produtos"][0]["frete_interno_hub_brl"],
                            "aliquotas": cen["produtos"][0]["aliquotas_importacao"],
                            "creditos": cen["produtos"][0]["creditos_importacao"]
                        },
                        {
                            "nome_produto": cen["produtos"][1]["nome_produto"],
                            "ncm": cen["produtos"][1]["ncm"],
                            "quantidade": cen["produtos"][1]["quantidade"],
                            "preco_unitario_exw_usd": cen["produtos"][1]["preco_unitario_exw_usd"],
                            "frete_interno_hub_brl": cen["produtos"][1]["frete_interno_hub_brl"],
                            "aliquotas": cen["produtos"][1]["aliquotas_importacao"],
                            "creditos": cen["produtos"][1]["creditos_importacao"]
                        }
                    ]
                }

                payload_com = {
                    "premissas_venda": [
                        {
                            "nome_produto": cen["produtos"][0]["nome_produto"],
                            "unidades_vendidas": cen["produtos"][0]["quantidade"],
                            "preco_venda_unitario_brl": cen["produtos"][0]["preco_venda_unitario_brl"],
                            "aliquotas_venda": cen["produtos"][0]["aliquotas_venda"]
                        },
                        {
                            "nome_produto": cen["produtos"][1]["nome_produto"],
                            "unidades_vendidas": cen["produtos"][1]["quantidade"],
                            "preco_venda_unitario_brl": cen["produtos"][1]["preco_venda_unitario_brl"],
                            "aliquotas_venda": cen["produtos"][1]["aliquotas_venda"]
                        }
                    ],
                    "opex_fixo_mensal_brl": cen["estrutura_opex_e_societaria"]["opex_fixo_mensal_brl"],
                    "meses_operacao": cen["estrutura_opex_e_societaria"].get("meses_operacao", 1),
                    "participacao_matriz_eua_pct": cen["estrutura_opex_e_societaria"]["participacao_matriz_eua_pct"],
                    "retencao_dividendos_pct": cen["estrutura_opex_e_societaria"].get("retencao_dividendos_pct", 0.10),
                    "custo_remessa_pct": cen["estrutura_opex_e_societaria"].get("custo_remessa_pct", 0.01)
                }

                resultado = executar_pipeline_ia(user_api_key, payload_imp, payload_com)
                st.session_state["resultado_dre"] = resultado
                st.success("✅ Simulação concluída com sucesso!")
            except Exception as e:
                st.error(f"Erro no processamento da IA: {e}")

# =====================================================================
# RENDERIZAÇÃO DOS RESULTADOS (DRE & RELATÓRIOS)
# =====================================================================
if "resultado_dre" in st.session_state:
    res: DREReportSynvitta = st.session_state["resultado_dre"]
    lr, lp = res.lucro_real, res.lucro_presumido

    st.info(f"💡 **Recomendação Fiscal:** {res.regime_recomendado}")

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Receita Bruta Total", f"R$ {lr.receita_bruta_total_brl:,.2f}")
    c2.metric("Lucro Líquido (Lucro Real)", f"R$ {lr.lucro_liquido_brasil_brl:,.2f}", f"Margem: {lr.margem_liquida_pct:.1f}%")
    c3.metric("Lucro Líquido (Lucro Presumido)", f"R$ {lp.lucro_liquido_brasil_brl:,.2f}", f"Margem: {lp.margem_liquida_pct:.1f}%")
    diff = lr.lucro_liquido_brasil_brl - lp.lucro_liquido_brasil_brl
    c4.metric("Vantagem do Lucro Real", f"R$ {diff:,.2f}", delta=f"{diff:,.2f}")

    t1, t2, t3, t4 = st.tabs(["📊 Comparativo DRE", "📦 Análise por Produto", "🇺🇸 Fluxo EUA", "📥 Exportação & Downloads"])

    with t1:
        st.subheader("DRE Detalhada Comparativa (BRL)")
        df_comp = pd.DataFrame({
            "Etapa DRE": [
                "Receita Bruta Total", "(-) Impostos sobre Vendas", "(=) Receita Líquida",
                "(-) CMV (Ajustado)", "(=) Lucro Bruto", "(-) Opex Fixo",
                "(-) Operação Variável", "(=) EBITDA", "(-) IRPJ / CSLL", "(=) Lucro Líquido Brasil"
            ],
            "Lucro Real": [
                lr.receita_bruta_total_brl, lr.tributos_venda_total_brl, lr.receita_liquida_total_brl,
                lr.cmv_total_brl, lr.lucro_bruto_total_brl, lr.opex_fixo_brl,
                lr.operacao_variavel_brl, lr.ebitda_brl, lr.irpj_csll_brl, lr.lucro_liquido_brasil_brl
            ],
            "Lucro Presumido": [
                lp.receita_bruta_total_brl, lp.tributos_venda_total_brl, lp.receita_liquida_total_brl,
                lp.cmv_total_brl, lp.lucro_bruto_total_brl, lp.opex_fixo_brl,
                lp.operacao_variavel_brl, lp.ebitda_brl, lp.irpj_csll_brl, lp.lucro_liquido_brasil_brl
            ]
        })
        st.dataframe(df_comp.style.format({"Lucro Real": "R$ {:,.2f}", "Lucro Presumido": "R$ {:,.2f}"}), use_container_width=True)

        fig_bar = px.bar(
            pd.DataFrame([
                {"Métrica": "Lucro Bruto", "Valor": lr.lucro_bruto_total_brl, "Regime": "Lucro Real"},
                {"Métrica": "Lucro Bruto", "Valor": lp.lucro_bruto_total_brl, "Regime": "Lucro Presumido"},
                {"Métrica": "Lucro Líquido", "Valor": lr.lucro_liquido_brasil_brl, "Regime": "Lucro Real"},
                {"Métrica": "Lucro Líquido", "Valor": lp.lucro_liquido_brasil_brl, "Regime": "Lucro Presumido"},
            ]),
            x="Métrica", y="Valor", color="Regime", barmode="group", title="Comparativo Visual de Lucro (BRL)"
        )
        st.plotly_chart(fig_bar, use_container_width=True)

    with t2:
        st.subheader("Margem de Contribuição por Produto (Lucro Real)")
        if lr.itens_produtos:
            df_p = pd.DataFrame([p.model_dump() for p in lr.itens_produtos])
            st.dataframe(df_p.style.format({
                "receita_bruta_brl": "R$ {:,.2f}",
                "tributos_venda_brl": "R$ {:,.2f}",
                "receita_liquida_brl": "R$ {:,.2f}",
                "cmv_brl": "R$ {:,.2f}",
                "lucro_bruto_brl": "R$ {:,.2f}",
                "margem_contribucao_pct": "{:.2f}%"
            }), use_container_width=True)

    with t3:
        st.subheader("Distribuição de Resultados: Matriz EUA vs. Filial SP")
        c_eua, c_sp = st.columns(2)
        c_eua.metric("Remessa Líquida à Matriz (75%)", f"R$ {lr.remessa_matriz_eua_brl:,.2f}")
        c_sp.metric("Lucro Retido Filial SP (25%)", f"R$ {lr.lucro_retido_filial_sp_brl:,.2f}")

    with t4:
        st.subheader("📥 Exportação dos Resultados")
        col_ex, col_js = st.columns(2)

        excel_data = gerar_excel_bytes(res)
        col_ex.download_button(
            label="📊 Baixar Relatório Completo em Excel (.xlsx)",
            data=excel_data,
            file_name="synvitta3_report_executivo.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True
        )

        json_bytes = res.model_dump_json(indent=2).encode("utf-8")
        col_js.download_button(
            label="📄 Baixar Arquivo JSON Estrito",
            data=json_bytes,
            file_name="synvitta3_report_executivo.json",
            mime="application/json",
            use_container_width=True
        )