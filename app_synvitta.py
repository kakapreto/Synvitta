import base64
import io
import json
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st
from pydantic import ValidationError

from calculos_synvitta import Cenario, DREReportSynvitta, calcular_cenario, cenario_padrao


st.set_page_config(
    page_title="Synvitta L.A. - Landed Cost & DRE",
    page_icon="🧬", layout="wide", initial_sidebar_state="expanded",
)

st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');
    html, body, [class*="css"] { font-family: 'Inter', sans-serif !important; }
    .stApp { background-color: #F8FAFC !important; }
    .header-container {
        background: linear-gradient(135deg, #0F172A 0%, #1E293B 100%);
        padding: 24px 32px; border-radius: 12px; color: #FFFFFF;
        margin-bottom: 24px; box-shadow: 0 4px 12px rgba(15,23,42,.12);
        display: flex; align-items: center; justify-content: space-between;
    }
    .header-title { font-size: 1.8rem; font-weight: 700; color: #F8FAFC; }
    .header-subtitle { font-size: .95rem; color: #94A3B8; margin-top: 4px; }
    .header-logo { max-height: 55px; background: #FFFFFF; padding: 8px 12px; border-radius: 8px; }
    div[data-testid="stMetric"] {
        background: #FFFFFF; border: 1px solid #CBD5E1; padding: 16px 20px; border-radius: 10px;
    }
    div[data-testid="stMetricLabel"] p { color: #475569; font-weight: 600; }
    div[data-testid="stMetricValue"] { color: #0F172A; }
    .stButton > button { background: #0284C7; color: #FFFFFF; border-radius: 8px; }
    section[data-testid="stSidebar"] { background-color: #0F172A; }
    section[data-testid="stSidebar"] :is(p,label,h1,h2,h3) { color: #F8FAFC; }
</style>
""", unsafe_allow_html=True)

APP_DIR = Path(__file__).resolve().parent
DEFAULT_JSON_PATH = APP_DIR / "dados_entrada.json"


def moeda(valor: float) -> str:
    return "R$ " + f"{valor:,.2f}".replace(",", "_").replace(".", ",").replace("_", ".")


def assinatura(cenario: dict) -> str:
    return json.dumps(cenario, sort_keys=True, ensure_ascii=False, allow_nan=False)


def carregar_dados_iniciais() -> dict:
    if DEFAULT_JSON_PATH.exists():
        return Cenario.model_validate_json(
            DEFAULT_JSON_PATH.read_text(encoding="utf-8")
        ).model_dump()
    return cenario_padrao().model_dump()


def importar_cenario() -> None:
    arquivo = st.session_state["arquivo_cenario"]
    if arquivo is None:
        return
    try:
        novo = Cenario.model_validate_json(arquivo.getvalue())
    except (ValueError, ValidationError) as erro:
        st.session_state["erro_importacao"] = f"Cenário não importado: {erro}"
        return
    for chave in list(st.session_state):
        if chave.startswith("entrada:"):
            del st.session_state[chave]
    st.session_state["cenario"] = novo.model_dump()
    st.session_state.pop("resultado_dre", None)
    st.session_state.pop("assinatura_resultado", None)
    st.session_state.pop("erro_importacao", None)


def campo(
    dados: dict, chave: str, rotulo: str, prefixo: str, *,
    percentual: bool = False, minimo: float = 0.0, maximo: float | None = None,
) -> None:
    atual = dados[chave]
    inteiro = isinstance(atual, int) and not isinstance(atual, bool)
    fator = 100 if percentual else 1
    valor = atual if inteiro else float(atual) * fator
    minimo_widget = int(minimo) if inteiro else float(minimo)
    maximo_widget = int(maximo) if inteiro and maximo is not None else maximo
    novo = st.number_input(
        rotulo, value=valor, min_value=minimo_widget,
        max_value=maximo_widget, step=1 if inteiro else 0.01,
        key=f"entrada:{prefixo}:{chave}",
    )
    dados[chave] = novo / fator if percentual else novo


def checkbox(dados: dict, chave: str, rotulo: str, prefixo: str) -> None:
    dados[chave] = st.checkbox(
        rotulo, value=dados[chave], key=f"entrada:{prefixo}:{chave}"
    )


def tabela_dre(relatorio: DREReportSynvitta) -> pd.DataFrame:
    linhas = {
        "Receita Bruta Total": "receita_bruta_total_brl",
        "(-) Tributos sobre Vendas": "tributos_venda_total_brl",
        "(=) Receita Líquida": "receita_liquida_total_brl",
        "(-) CMV Nacionalizado": "cmv_total_brl",
        "(=) Lucro Bruto": "lucro_bruto_total_brl",
        "(-) Opex Fixo": "opex_fixo_brl",
        "(-) Operação Variável": "operacao_variavel_brl",
        "(=) EBITDA estimado": "ebitda_brl",
        "Base de IRPJ": "base_irpj_brl",
        "Base de CSLL": "base_csll_brl",
        "IRPJ (15%)": "irpj_brl",
        "Adicional de IRPJ": "adicional_irpj_brl",
        "CSLL (9%)": "csll_brl",
        "(-) Total IRPJ / CSLL": "irpj_csll_brl",
        "(=) Lucro Líquido Brasil": "lucro_liquido_brasil_brl",
        "Dividendos brutos da matriz": "dividendos_matriz_brutos_brl",
        "Retenção sobre dividendos": "retencao_dividendos_brl",
        "Custo da remessa": "custo_remessa_brl",
        "Remessa líquida à matriz": "remessa_matriz_eua_brl",
        "Parcela do lucro dos sócios locais": "parcela_socios_locais_brl",
    }
    return pd.DataFrame({
        "Etapa DRE": list(linhas),
        "Lucro Real estimado": [getattr(relatorio.lucro_real, k) for k in linhas.values()],
        "Lucro Presumido": [getattr(relatorio.lucro_presumido, k) for k in linhas.values()],
    })


def gerar_excel_bytes(relatorio: DREReportSynvitta) -> bytes:
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        pd.DataFrame([
            {"Parâmetro": "Empresa", "Valor": relatorio.empresa},
            {"Parâmetro": "PTAX (BRL/USD)", "Valor": relatorio.ptax},
            {"Parâmetro": "Ano", "Valor": relatorio.premissas.tributacao.ano},
            {"Parâmetro": "Trimestre", "Valor": relatorio.premissas.tributacao.trimestre},
            {"Parâmetro": "Comparação condicional", "Valor": relatorio.regime_recomendado},
            {"Parâmetro": "Diferença no trimestre (BRL)",
             "Valor": relatorio.economia_tributaria_periodo_brl},
        ]).to_excel(writer, sheet_name="Resumo", index=False)
        tabela_dre(relatorio).to_excel(writer, sheet_name="DRE_Comparativa", index=False)
        for nome, regime in (
            ("Produtos_LucroReal", relatorio.lucro_real),
            ("Produtos_Presumido", relatorio.lucro_presumido),
        ):
            pd.DataFrame([p.model_dump() for p in regime.itens_produtos]).to_excel(
                writer, sheet_name=nome, index=False
            )
        pd.DataFrame([
            p.model_dump() for p in relatorio.landed_cost.produtos
        ]).to_excel(writer, sheet_name="Landed_Cost", index=False)
        pd.DataFrame({"Premissas e limitações": relatorio.avisos}).to_excel(
            writer, sheet_name="Memoria_e_Avisos", index=False
        )
        pd.json_normalize(relatorio.premissas.model_dump()).astype(str).to_excel(
            writer, sheet_name="Entradas", index=False
        )
    return output.getvalue()


if not st.session_state.get("motor_local_v1"):
    try:
        st.session_state["cenario"] = (
            Cenario.model_validate(st.session_state["cenario"]).model_dump()
            if "cenario" in st.session_state else carregar_dados_iniciais()
        )
    except (OSError, ValueError) as erro:
        st.error(f"Não foi possível carregar as entradas: {erro}")
        st.stop()
    st.session_state.pop("resultado_dre", None)
    st.session_state.pop("assinatura_resultado", None)
    st.session_state["motor_local_v1"] = True

st.sidebar.markdown("### 🧬 Synvitta L.A.")
st.sidebar.markdown("**Painel de Controle**")
st.sidebar.info("Cálculos locais em Python. Não requer chave nem API de IA.")
st.sidebar.file_uploader(
    "Importar Cenário JSON", type=["json"], key="arquivo_cenario",
    on_change=importar_cenario,
)
if "erro_importacao" in st.session_state:
    st.sidebar.error(st.session_state["erro_importacao"])

logo = APP_DIR / "logo_synvitta.png"
logo_html = ""
if logo.exists():
    imagem = base64.b64encode(logo.read_bytes()).decode("ascii")
    logo_html = f'<img src="data:image/png;base64,{imagem}" class="header-logo" alt="Synvitta">'
st.markdown(f"""
<div class="header-container"><div>
    <div class="header-title">Synvitta L.A. — Landed Cost &amp; DRE</div>
    <div class="header-subtitle">Cálculo local multiproduto e comparação tributária estimada</div>
</div>{logo_html}</div>
""", unsafe_allow_html=True)
st.warning(
    "Estimativa gerencial, não apuração fiscal. Os valores do lote são o total "
    "do trimestre, sem multiplicar por três. Alíquotas e créditos exigem validação contábil."
)

cen = st.session_state["cenario"]
abas = st.tabs([
    "🌐 1. Câmbio & Localização", "✈️ 2. Fretes & Aduana",
    "📦 3. Kit Reagente", "🔬 4. Leitor Óptico",
    "🏢 5. Opex & Societário", "6. Período & Tributos",
])
with abas[0]:
    globais = cen["parametros_globais"]
    globais["empresa"] = st.text_input(
        "Empresa", value=globais["empresa"], key="entrada:global:empresa"
    )
    campo(globais, "ptax", "Câmbio PTAX (BRL/USD)", "global", minimo=0.01)
    globais["uf_destino"] = st.text_input(
        "UF de Destino", value=globais["uf_destino"], key="entrada:global:uf"
    )

with abas[1]:
    st.caption("Rateio dos custos comuns proporcional ao valor EXW de cada produto.")
    for chave, rotulo in (
        ("frete_internacional_aereo", "Frete Internacional Aéreo (USD/lote)"),
        ("frete_origem", "Frete de Origem (USD/lote)"),
        ("seguro_internacional", "Seguro até a importação (USD/lote)"),
        ("despacho_miami", "Despacho Miami total (USD/lote)"),
        ("locacao_uld_rap", "Locação ULD/RAP total (USD/lote)"),
        ("despacho_na_va", "Despacho incluído na VA (USD/lote)"),
        ("locacao_na_va", "Locação incluída na VA (USD/lote)"),
    ):
        campo(cen["custos_compartilhados_usd"], chave, rotulo, "usd")
    st.caption("Revise documentalmente as parcelas de despacho e ULD incluídas na VA.")
    for chave, rotulo in (
        ("armazenagem_terminal", "Armazenagem Terminal (R$/lote)"),
        ("despachante_aduaneiro", "Despachante Aduaneiro (R$/lote)"),
        ("taxa_siscomex", "Taxa Siscomex (R$/lote)"),
        ("taxa_anvisa", "Taxa ANVISA (R$/lote)"),
        ("outras_parcelas_base_icms", "Outras parcelas na base ICMS, já nos custos (R$/lote)"),
    ):
        campo(cen["custos_compartilhados_brl"], chave, rotulo, "brl")

for indice, aba in enumerate(abas[2:4]):
    with aba:
        produto = cen["produtos"][indice]
        prefixo = f"p{indice + 1}"
        st.subheader(produto["nome_produto"])
        produto["ncm"] = st.text_input(
            "NCM", value=produto["ncm"], key=f"entrada:{prefixo}:ncm"
        )
        for chave, rotulo, minimo in (
            ("quantidade", "Quantidade importada e vendida no trimestre", 1),
            ("preco_unitario_exw_usd", "Preço Unitário EXW (USD)", 0.01),
            ("preco_venda_unitario_brl", "Preço de Venda BR, sem IPI de saída (R$/unid)", 0),
            ("frete_interno_hub_brl", "Frete Interno Hub/SP (R$/produto no lote)", 0),
        ):
            campo(produto, chave, rotulo, prefixo, minimo=minimo)
        st.markdown("**Alíquotas de importação**")
        for tributo in ("ii", "ipi", "pis", "cofins", "icms"):
            campo(
                produto["aliquotas_importacao"], tributo,
                f"{tributo.upper()} Importação (%)", prefixo + ":importacao",
                percentual=True, maximo=99.99 if tributo == "icms" else 100.0,
            )
        checkbox(produto["creditos_importacao"], "credita_ipi",
                 "IPI-importação recuperável (confirmar elegibilidade)", prefixo + ":credito")
        checkbox(produto["creditos_importacao"], "credita_icms",
                 "ICMS-importação recuperável", prefixo + ":credito")
        st.markdown("**Alíquotas de venda — Lucro Presumido**")
        for tributo in ("icms", "pis", "cofins", "operador_var"):
            campo(
                produto["aliquotas_venda"], tributo, f"{tributo.upper()} Venda (%)",
                prefixo + ":venda", percentual=True, maximo=100.0,
            )
        st.markdown("**Lucro Real estimado — PIS/Cofins**")
        st.caption(
            "ICMS e comissão são os mesmos nos dois regimes. Informe apenas "
            "créditos de importação comprovadamente recuperáveis; zero significa "
            "nenhum crédito considerado. Créditos saem do CMV, não são abatidos novamente na DRE."
        )
        for chave, rotulo in (
            ("pis_venda_real", "PIS Venda — Real (%)"),
            ("cofins_venda_real", "COFINS Venda — Real (%)"),
        ):
            campo(produto, chave, rotulo, prefixo, percentual=True, maximo=100.0)
        for chave, rotulo in (
            ("credito_pis_importacao_real_brl", "Crédito PIS-importação — Real (R$/produto)"),
            ("credito_cofins_importacao_real_brl", "Crédito COFINS-importação — Real (R$/produto)"),
        ):
            campo(produto, chave, rotulo, prefixo)

with abas[4]:
    soc = cen["estrutura_opex_e_societaria"]
    campo(soc, "opex_fixo_mensal_brl", "Opex Fixo Mensal (R$)", "soc")
    campo(soc, "meses_operacao", "Meses de opex no trimestre", "soc", minimo=1, maximo=3)
    for chave, rotulo in (
        ("participacao_matriz_eua_pct", "Participação Matriz EUA (%)"),
        ("participacao_socios_locais_sp_pct", "Participação Sócios SP (%)"),
        ("retencao_dividendos_pct", "Retenção sobre dividendos (%)"),
        ("custo_remessa_pct", "Custo da remessa, após retenção (%)"),
    ):
        campo(soc, chave, rotulo, "soc", percentual=True, maximo=100.0)

with abas[5]:
    fiscal = cen["tributacao"]
    fiscal["ano"] = st.selectbox(
        "Ano-calendário", [2025, 2026], index=[2025, 2026].index(fiscal["ano"]),
        key="entrada:fiscal:ano",
    )
    campo(fiscal, "trimestre", "Trimestre completo de apuração", "fiscal", minimo=1, maximo=4)
    st.caption(
        "Modelo de comércio. Presunção padrão: IRPJ 8% e CSLL 12%. LC 224/2025: "
        "acréscimo de 10% dos coeficientes sobre a receita acima de R$ 1.250.000 "
        "no trimestre. Em 2026, IRPJ desde Q1 e CSLL desde Q2. Não inclui ajuste anual "
        "de limites entre trimestres nem início/encerramento em trimestre incompleto."
    )
    for chave, rotulo in (
        ("base_presumida_irpj", "Base presumida IRPJ (%)"),
        ("base_presumida_csll", "Base presumida CSLL (%)"),
    ):
        campo(fiscal, chave, rotulo, "fiscal", percentual=True, maximo=100.0)
    checkbox(fiscal, "excluir_icms_base_pis_cofins",
             "Excluir ICMS destacado da base de PIS/Cofins sobre vendas", "fiscal")
    campo(fiscal, "adicoes_real_brl", "Adições à base do Lucro Real/CSLL (R$)", "fiscal")
    campo(fiscal, "exclusoes_real_brl", "Exclusões da base do Lucro Real/CSLL (R$)", "fiscal")
    st.caption(
        "Adições/exclusões aplicadas igualmente ao IRPJ e à CSLL nesta estimativa. "
        "IRPJ: 15% + adicional de 10% acima de R$ 60 mil/trimestre; CSLL: 9%."
    )
    st.markdown(
        "[IRPJ — Receita Federal](https://www.gov.br/receitafederal/pt-br/assuntos/orientacao-tributaria/tributos/IRPJ) · "
        "[LC 224/2025](https://www.planalto.gov.br/ccivil_03/leis/lcp/lcp224.htm) · "
        "[Classif](https://portalunico.siscomex.gov.br/classif/)"
    )

st.sidebar.download_button(
    "💾 Baixar Cenário (JSON)", data=json.dumps(cen, indent=2, ensure_ascii=False),
    file_name="cenario_synvitta.json", mime="application/json", width="stretch",
)
if st.sidebar.button("Executar simulação local", type="primary", width="stretch"):
    st.session_state.pop("resultado_dre", None)
    try:
        resultado = calcular_cenario(Cenario.model_validate(cen))
    except ValueError as erro:
        st.error(f"Não foi possível calcular: {erro}")
    else:
        st.session_state["resultado_dre"] = resultado.model_dump()
        st.session_state["assinatura_resultado"] = assinatura(cen)
        st.success("Simulação local concluída — resultados abaixo.")

if "resultado_dre" in st.session_state:
    if st.session_state.get("assinatura_resultado") != assinatura(cen):
        st.warning("As entradas foram alteradas. Execute novamente para atualizar os resultados.")
    else:
        res = DREReportSynvitta.model_validate(st.session_state["resultado_dre"])
        lr, lp = res.lucro_real, res.lucro_presumido
        st.info(res.regime_recomendado)
        colunas = st.columns(4)
        colunas[0].metric("Receita Bruta Total", moeda(lp.receita_bruta_total_brl))
        colunas[1].metric("Lucro Líquido (Lucro Real estimado)", moeda(lr.lucro_liquido_brasil_brl))
        colunas[2].metric("Lucro Líquido (Lucro Presumido)", moeda(lp.lucro_liquido_brasil_brl))
        colunas[3].metric(
            "Diferença a favor do Real", moeda(lr.lucro_liquido_brasil_brl - lp.lucro_liquido_brasil_brl)
        )
        t1, t2, t3, t4, t5 = st.tabs([
            "📊 Comparativo DRE", "📦 Análise por Produto", "🇺🇸 Fluxo EUA",
            "📥 Exportação & Downloads", "Memória de cálculo",
        ])
        with t1:
            st.subheader("DRE trimestral estimada (BRL)")
            st.dataframe(
                tabela_dre(res).style.format({
                    "Lucro Real estimado": moeda, "Lucro Presumido": moeda,
                }), width="stretch",
            )
            st.plotly_chart(px.bar(
                pd.DataFrame([
                    {"Regime": r.regime_tributario, "Lucro Líquido (BRL)": r.lucro_liquido_brasil_brl}
                    for r in (lr, lp)
                ]),
                x="Regime", y="Lucro Líquido (BRL)", color="Regime",
            ), width="stretch")
        with t2:
            regime = st.radio("Regime", ["Lucro Presumido", "Lucro Real estimado"], horizontal=True)
            dados = lp if regime == "Lucro Presumido" else lr
            st.dataframe(pd.DataFrame([
                p.model_dump() for p in dados.itens_produtos
            ]), width="stretch")
        with t3:
            st.caption("Remessa do lucro brasileiro; não inclui fabricação, lucro ou tributos nos EUA.")
            for dados in (lp, lr):
                st.subheader(dados.regime_tributario)
                cols = st.columns(3)
                cols[0].metric("Remessa líquida à matriz", moeda(dados.remessa_matriz_eua_brl))
                cols[1].metric("Lucro atribuído aos sócios locais", moeda(dados.parcela_socios_locais_brl))
                cols[2].metric(
                    "Parcela local / receita bruta", f"{dados.margem_socios_locais_pct:.2f}%"
                )
        with t4:
            st.download_button(
                "📊 Baixar Relatório em Excel (.xlsx)", gerar_excel_bytes(res),
                "synvitta3_report_executivo.xlsx",
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                width="stretch",
            )
            st.download_button(
                "📄 Baixar JSON do Relatório", res.model_dump_json(indent=2),
                "synvitta3_report_executivo.json", "application/json", width="stretch",
            )
        with t5:
            st.dataframe(pd.DataFrame([
                p.model_dump() for p in res.landed_cost.produtos
            ]), width="stretch")
            for aviso in res.avisos:
                st.write("- " + aviso)
            st.caption(
                "VA = mercadoria + fretes + seguro + parcelas documentadas; II = VA × alíquota; "
                "IPI = (VA + II) × alíquota; PIS/Cofins-importação = VA × alíquota. "
                "ICMS por dentro = base antes do ICMS / (1 − alíquota). "
                "CMV = custo bruto − créditos recuperáveis; receita líquida = bruta − tributos de venda; "
                "lucro líquido = receita líquida − CMV − despesas − IRPJ/CSLL."
            )
