import io
import json
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

    # Agente 1: Landed Cost
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

    # Agente 2: DRE Comparativa
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
# GERADOR DE ARQUIVO EXCEL COMPLETO EM MEMÓRIA
# =====================================================================
def gerar_excel_bytes(dre_data: DREReportSynvitta) -> bytes:
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        # Aba 1: Resumo Executivo
        df_resumo = pd.DataFrame([
            {"Parâmetro": "Empresa", "Valor": dre_data.empresa},
            {"Parâmetro": "Taxa de Câmbio (PTAX)", "Valor": f"R$ {dre_data.ptax:.2f}"},
            {"Parâmetro": "Regime Recomendado", "Valor": dre_data.regime_recomendado},
            {"Parâmetro": "Economia Estimada (BRL)", "Valor": dre_data.economia_tributaria_anual_estimada_brl}
        ])
        df_resumo.to_excel(writer, sheet_name="Resumo", index=False)

        # Aba 2: DRE Comparativa
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

        # Aba 3: Produtos
        if lr.itens_produtos:
            df_prod = pd.DataFrame([p.model_dump() for p in lr.itens_produtos])
            df_prod.to_excel(writer, sheet_name="Produtos_LucroReal", index=False)

    return output.getvalue()

# =====================================================================
# INTERFACE DO USUÁRIO - SIDEBAR (PARÂMETROS EDITÁVEIS)
# =====================================================================
st.sidebar.title("⚙️ Parâmetros Operacionais")

# Gestão da API Key
api_key_env = st.secrets.get("GEMINI_API_KEY", "")
user_api_key = st.sidebar.text_input("Chave da API Gemini", value=api_key_env, type="password")

st.sidebar.subheader("💵 Câmbio e Localização")
ptax = st.sidebar.number_input("Câmbio PTAX (BRL/USD)", value=5.60, step=0.05)
uf_destino = st.sidebar.selectbox("UF de Destino", ["SP", "MG", "RJ", "PR", "SC"])

st.sidebar.subheader("📦 Produto 1: Kit Reagente")
q1 = st.sidebar.number_input("Kits Importados", value=1440)
p1_exw = st.sidebar.number_input("Preço EXW (USD/kit)", value=200.0)
v1_brl = st.sidebar.number_input("Preço Venda BR (R$/kit)", value=9600.0)

st.sidebar.subheader("🔬 Produto 2: Leitor Óptico")
q2 = st.sidebar.number_input("Leitores Importados", value=160)
p2_exw = st.sidebar.number_input("Preço EXW (USD/unidade)", value=5000.0)
v2_brl = st.sidebar.number_input("Preço Venda BR (R$/unid)", value=280000.0)

st.sidebar.subheader("🏢 Estrutura & Opex")
opex_fixo = st.sidebar.number_input("Opex Fixo Mensal (R$)", value=200000.0, step=10000.0)

btn_calcular = st.sidebar.button("🚀 Executar Simulação via IA", type="primary", use_container_width=True)

# =====================================================================
# PAINEL PRINCIPAL
# =====================================================================
st.title("🧬 Synvitta L.A. — Simulador Integrado de IA & DRE")
st.caption("Automação de Landed Cost Multiproduto + Comparativo Tributário Lucro Real vs. Presumido")

if btn_calcular:
    if not user_api_key:
        st.error("⚠️ Insira uma chave válida da API do Gemini para rodar a simulação.")
    else:
        with st.spinner("Conectando aos Agentes de IA e processando memória de cálculo aduaneira e fiscal..."):
            try:
                # Montar payloads de entrada
                payload_imp = {
                    "ptax": ptax,
                    "uf_destino": uf_destino,
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
                            "quantidade": q1,
                            "preco_unitario_exw_usd": p1_exw,
                            "frete_interno_hub_brl": 1200.0,
                            "aliquotas": {"ii": 0.0, "ipi": 0.0, "pis": 0.0, "cofins": 0.0, "icms_sp": 0.0},
                            "creditos": {"credita_ipi": False, "credita_icms": False}
                        },
                        {
                            "nome_produto": "Leitor Óptico",
                            "ncm": "9027.50.20",
                            "quantidade": q2,
                            "preco_unitario_exw_usd": p2_exw,
                            "frete_interno_hub_brl": 800.0,
                            "aliquotas": {"ii": 0.14, "ipi": 0.0975, "pis": 0.021, "cofins": 0.0965, "icms_sp": 0.18},
                            "creditos": {"credita_ipi": True, "credita_icms": True}
                        }
                    ]
                }

                payload_com = {
                    "premissas_venda": [
                        {
                            "nome_produto": "Kit Reagente / Diagnóstico",
                            "unidades_vendidas": q1,
                            "preco_venda_unitario_brl": v1_brl,
                            "aliquotas_venda": {"icms": 0.04, "pis": 0.0065, "cofins": 0.03, "operador_var": 0.04}
                        },
                        {
                            "nome_produto": "Leitor Óptico",
                            "unidades_vendidas": q2,
                            "preco_venda_unitario_brl": v2_brl,
                            "aliquotas_venda": {"icms": 0.18, "pis": 0.0065, "cofins": 0.03, "operador_var": 0.0}
                        }
                    ],
                    "opex_fixo_mensal_brl": opex_fixo,
                    "meses_operacao": 1,
                    "participacao_matriz_eua_pct": 0.75,
                    "retencao_dividendos_pct": 0.10,
                    "custo_remessa_pct": 0.01
                }

                # Chamar Pipeline
                resultado = executar_pipeline_ia(user_api_key, payload_imp, payload_com)
                st.session_state["resultado_dre"] = resultado
                st.success("✅ Simulação concluída com sucesso!")
            except Exception as e:
                st.error(f"Erro no processamento da IA: {e}")

# Renderização do Resultado em Session State
if "resultado_dre" in st.session_state:
    res: DREReportSynvitta = st.session_state["resultado_dre"]
    lr, lp = res.lucro_real, res.lucro_presumido

    # Banner Recomendação
    st.info(f"💡 **Recomendação Fiscal:** {res.regime_recomendado}")

    # Cards de KPIs
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Receita Bruta Total", f"R$ {lr.receita_bruta_total_brl:,.2f}")
    c2.metric("Lucro Líquido (Lucro Real)", f"R$ {lr.lucro_liquido_brasil_brl:,.2f}", f"Margem: {lr.margem_liquida_pct:.1f}%")
    c3.metric("Lucro Líquido (Lucro Presumido)", f"R$ {lp.lucro_liquido_brasil_brl:,.2f}", f"Margem: {lp.margem_liquida_pct:.1f}%")
    diff = lr.lucro_liquido_brasil_brl - lp.lucro_liquido_brasil_brl
    c4.metric("Vantagem do Lucro Real", f"R$ {diff:,.2f}", delta=f"{diff:,.2f}")

    # Abas Principais
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

        # Download Excel
        excel_data = gerar_excel_bytes(res)
        col_ex.download_button(
            label="📊 Baixar Relatório Completo em Excel (.xlsx)",
            data=excel_data,
            file_name="synvitta3_report_executivo.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True
        )

        # Download JSON
        json_bytes = res.model_dump_json(indent=2).encode("utf-8")
        col_js.download_button(
            label="📄 Baixar Arquivo JSON Estrito",
            data=json_bytes,
            file_name="synvitta3_report_executivo.json",
            mime="application/json",
            use_container_width=True
        )