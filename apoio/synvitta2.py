from __future__ import annotations

import json
import os
from html import escape as html_escape
from io import BytesIO
from pathlib import Path
from math import ceil
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from standalone_html import build_calculator_html, field, synvitta2_calculation_js
from openpyxl.chart import BarChart, Reference
from reportlab.graphics.charts.barcharts import VerticalBarChart
from reportlab.graphics.charts.legends import Legend
from reportlab.graphics.shapes import Drawing
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


CAMINHO_CONFIGURADO = os.environ.get("SYNVITTA2_DEFAULTS_PATH")
if CAMINHO_CONFIGURADO:
    ARQUIVO_PADROES = Path(CAMINHO_CONFIGURADO)
    ARQUIVO_PADROES_LEGADO = None
else:
    LOCAL_APP_DATA = os.environ.get("LOCALAPPDATA")
    if LOCAL_APP_DATA:
        DIRETORIO_PADROES = Path(LOCAL_APP_DATA) / "Synvitta2"
    elif os.name == "nt":
        DIRETORIO_PADROES = Path.home() / "AppData" / "Local" / "Synvitta2"
    else:
        DIRETORIO_PADROES = Path.home() / ".local" / "share" / "Synvitta2"
    ARQUIVO_PADROES = DIRETORIO_PADROES / "defaults.json"
    ARQUIVO_PADROES_LEGADO = Path(__file__).with_name("synvitta2_defaults.json")

try:
    caminho_leitura = ARQUIVO_PADROES
    if not caminho_leitura.exists() and ARQUIVO_PADROES_LEGADO and ARQUIVO_PADROES_LEGADO.exists():
        caminho_leitura = ARQUIVO_PADROES_LEGADO
    with caminho_leitura.open("r", encoding="utf-8") as arquivo_padroes:
        PADROES_SALVOS = json.load(arquivo_padroes)
    if not isinstance(PADROES_SALVOS, dict):
        PADROES_SALVOS = {}
except (OSError, json.JSONDecodeError):
    PADROES_SALVOS = {}


st.set_page_config(
    page_title="Synvitta2 - Simulação detalhada",
    page_icon="📦",
    layout="wide",
)

def moeda(valor: float) -> str:
    texto = f"{valor:,.2f}".replace(",", "_").replace(".", ",").replace("_", ".")
    return f"R$ {texto}"


def moeda_resumida(valor: float) -> str:
    if abs(valor) >= 1_000_000:
        return f"R$ {valor / 1_000_000:.2f} mi".replace(".", ",")
    if abs(valor) >= 10_000:
        return f"R$ {valor / 1_000:.1f} mil".replace(".", ",")
    return moeda(valor)


def valor_padrao(chave: str, valor_inicial: object) -> object:
    return PADROES_SALVOS.get(chave, valor_inicial)


def indice_padrao(chave: str, opcoes: list[str], indice_inicial: int) -> int:
    valor_salvo = valor_padrao(chave, opcoes[indice_inicial])
    return opcoes.index(valor_salvo) if valor_salvo in opcoes else indice_inicial


def percentual(
    rotulo: str,
    chave: str,
    valor: float = 0.0,
    *,
    disabled: bool = False,
) -> float:
    return st.sidebar.number_input(
        rotulo,
        min_value=0.0,
        max_value=99.0,
        value=valor_padrao(chave, valor),
        step=0.1,
        key=chave,
        disabled=disabled,
    ) / 100


def seletor_modo_composicao(rotulo: str, chave: str) -> str:
    with st.container(border=True):
        st.markdown(f"**{rotulo}**")
        modo = st.segmented_control(
            "Modo de composição",
            ["Detalhado", "Consolidado"],
            default=valor_padrao(chave, "Detalhado"),
            key=chave,
            label_visibility="collapsed",
            width="stretch",
        )
        st.caption(f"Modo ativo: {modo}")
    return modo


def salvar_padroes() -> None:
    valores_salvos = dict(PADROES_SALVOS)
    for chave in st.session_state:
        if not isinstance(chave, str) or chave.startswith(("$$", "_synvitta2_")):
            continue
        valor = st.session_state[chave]
        if isinstance(valor, (str, int, float, bool)) or valor is None:
            valores_salvos[chave] = valor
    try:
        ARQUIVO_PADROES.parent.mkdir(parents=True, exist_ok=True)
        arquivo_temporario = ARQUIVO_PADROES.with_suffix(".tmp")
        arquivo_temporario.write_text(
            json.dumps(valores_salvos, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        os.replace(arquivo_temporario, ARQUIVO_PADROES)
    except OSError as erro:
        st.warning(f"Não foi possível salvar os padrões neste computador: {erro}")


st.title("📦 Synvitta2 | Simulação detalhada")
st.caption(
    "Modelo gerencial configurável. As alíquotas, bases tributárias e créditos "
    "devem ser confirmados para o NCM, origem, destino, regime e período da operação."
)
st.caption(
    "Premissas salvas automaticamente no perfil deste host, fora da pasta do app; "
    "atualizações do código não removem esses dados. Dispositivos conectados a este host "
    "compartilham os mesmos padrões."
)

with st.sidebar:
    st.header("Premissas da operação")

    with st.expander("1. Produto, volume e câmbio", expanded=True):
        ncm_codigo = st.text_input(
            "NCM do produto", value=valor_padrao("ncm_codigo", "3822.19.90"),
            placeholder="Ex.: 0000.00.00", key="ncm_codigo"
        )
        pais_origem = st.text_input(
            "País de origem aduaneira (confirmar fabricação)",
            value=valor_padrao("pais_origem", "Estados Unidos"),
            help=(
                "Preenchido com base no local informado. Se o produto for fabricado ou "
                "originário de outro país, altere este campo; local de embarque não define sozinho a origem aduaneira."
            ),
            key="pais_origem",
        )
        local_origem = st.text_input(
            "Local de origem / embarque",
            value=valor_padrao("local_origem", "Alachua, Florida"),
            key="local_origem",
        )
        opcoes_uf = ["Não informado", "AC", "AL", "AM", "AP", "BA", "CE", "DF", "ES", "GO", "MA", "MG", "MS", "MT", "PA", "PB", "PE", "PI", "PR", "RJ", "RN", "RO", "RR", "RS", "SC", "SE", "SP", "TO"]
        uf_destino = st.selectbox(
            "UF de destino / estabelecimento importador",
            opcoes_uf,
            index=indice_padrao("uf_destino", opcoes_uf, 26),
            key="uf_destino",
        )
        opcoes_incoterm = ["FOB", "EXW", "FCA", "FAS", "CFR", "CIF", "CPT", "CIP", "DAP", "DPU", "DDP"]
        incoterm = st.selectbox(
            "Incoterm negociado",
            opcoes_incoterm,
            index=indice_padrao("incoterm", opcoes_incoterm, 0),
            help=(
                "O cálculo usa o preço informado como valor FOB da mercadoria e soma "
                "frete e seguro separadamente. Este campo registra o termo do contrato; "
                "não converte automaticamente preço CIF/CFR/DAP/DDP."
            ),
            key="incoterm",
        )
        opcoes_regime = ["Não informado", "Lucro Real", "Lucro Presumido", "Simples Nacional", "Outro"]
        regime_tributario = st.selectbox(
            "Regime tributário da importadora",
            opcoes_regime,
            index=indice_padrao("regime_tributario", opcoes_regime, 2),
            key="regime_tributario",
        )
        registro_sanitario = st.text_input(
            "Registro / licença sanitária aplicável",
            value=valor_padrao("registro_sanitario", ""),
            placeholder="Anvisa, AFE ou não aplicável",
            key="registro_sanitario",
        )
        quantidade = st.number_input("Kits importados", min_value=1, value=valor_padrao("quantidade", 1000), step=100, key="quantidade")
        quantidade_vendida = st.number_input(
            "Kits vendidos no período", min_value=0,
            value=valor_padrao("quantidade_vendida", 1000), step=100, key="quantidade_vendida"
        )
        quantidade_vendida = min(quantidade_vendida, quantidade)
        cambio = st.number_input(
            "Câmbio aduaneiro / gerencial (R$/USD)",
            min_value=0.01,
            value=valor_padrao("cambio", 5.60),
            step=0.05,
            format="%.4f",
            key="cambio",
        )
        preco_fob_base = st.number_input(
            "Preço FOB da matriz (USD por kit)", min_value=0.0,
            value=valor_padrao("preco_fob_base", 200.0), step=10.0, key="preco_fob_base"
        )
        custo_fabricacao_usd = st.number_input(
            "Custo de fabricação da matriz (USD por kit)",
            min_value=0.0,
            value=valor_padrao("custo_fabricacao_usd", 100.0),
            step=10.0,
            key="custo_fabricacao_usd",
        )
        receita_por_kit = st.number_input(
            "Preço bruto de venda no Brasil (R$ por kit)",
            min_value=0.0,
            value=valor_padrao("receita_por_kit", 9598.40),
            step=100.0,
            key="receita_por_kit",
        )
        meses_operacao = st.number_input(
            "Duração do período da DRE (meses)", min_value=1,
            value=valor_padrao("meses_operacao", 3), step=1, key="meses_operacao"
        )

    with st.expander("2. Embalagem, peso e frete internacional"):
        kits_por_volume = st.number_input(
            "Kits por caixa/volume", min_value=1,
            value=valor_padrao("kits_por_volume", 10), step=1, key="kits_por_volume"
        )
        comprimento = st.number_input("Comprimento da caixa (cm)", min_value=0.0, value=valor_padrao("comprimento", 50.0), key="comprimento")
        largura = st.number_input("Largura da caixa (cm)", min_value=0.0, value=valor_padrao("largura", 40.0), key="largura")
        altura = st.number_input("Altura da caixa (cm)", min_value=0.0, value=valor_padrao("altura", 30.0), key="altura")
        peso_bruto_total = st.number_input(
            "Peso bruto total da carga (kg)", min_value=0.0,
            value=valor_padrao("peso_bruto_total", 500.0), step=10.0, key="peso_bruto_total"
        )
        divisor_volumetrico = st.number_input(
            "Divisor volumétrico (cm³/kg)", min_value=1,
            value=valor_padrao("divisor_volumetrico", 6000), step=500, key="divisor_volumetrico"
        )
        opcoes_modal = ["Marítimo", "Aéreo", "Rodoviário", "Outro"]
        modal = st.selectbox("Modal internacional", opcoes_modal, index=indice_padrao("modal", opcoes_modal, 0), key="modal")
        volumes = ceil(quantidade / kits_por_volume)
        volume_m3 = volumes * comprimento * largura * altura / 1_000_000
        peso_volumetrico = volumes * comprimento * largura * altura / divisor_volumetrico
        peso_taxavel = max(peso_bruto_total, peso_volumetrico)
        unidade_wm = max(volume_m3, peso_bruto_total / 1000)
        opcoes_frete = (
            ["Valor total informado", "Tarifa marítima por W/M"]
            if modal == "Marítimo"
            else ["Valor total informado", "Tarifa por kg taxável", "Tarifa por m³"]
        )
        calculo_frete = st.selectbox(
            "Como informar o frete internacional?",
            opcoes_frete,
            index=indice_padrao("calculo_frete", opcoes_frete, 0),
            key="calculo_frete",
        )
        if calculo_frete == "Valor total informado":
            frete_usd = st.number_input(
                "Frete internacional total (USD)", min_value=0.0,
                value=valor_padrao("frete_usd", 0.0), step=100.0, key="frete_usd"
            )
        elif calculo_frete == "Tarifa marítima por W/M":
            tarifa_wm = st.number_input(
                "Tarifa (USD por unidade W/M)", min_value=0.0,
                value=valor_padrao("tarifa_wm", 0.0), step=10.0, key="tarifa_wm"
            )
            frete_usd = tarifa_wm * unidade_wm
        elif calculo_frete == "Tarifa por kg taxável":
            tarifa_frete = st.number_input(
                "Tarifa (USD por kg taxável)", min_value=0.0,
                value=valor_padrao("tarifa_frete_kg", 0.0), step=0.1, key="tarifa_frete_kg"
            )
            frete_usd = tarifa_frete * peso_taxavel
        else:
            tarifa_m3 = st.number_input(
                "Tarifa (USD por m³)", min_value=0.0,
                value=valor_padrao("tarifa_m3", 0.0), step=10.0, key="tarifa_m3"
            )
            frete_usd = tarifa_m3 * volume_m3
        if modal == "Marítimo":
            st.caption(
                f"Volumes: {volumes} | Volume: {volume_m3:.3f} m³ | "
                f"W/M estimado (maior entre m³ e toneladas): {unidade_wm:.3f}"
            )
        else:
            st.caption(
                f"Volumes: {volumes} | Volume: {volume_m3:.3f} m³ | "
                f"Peso volumétrico: {peso_volumetrico:.1f} kg | "
                f"Peso taxável estimado: {peso_taxavel:.1f} kg"
            )
        seguro_pct = percentual("Seguro (% sobre FOB + frete)", "seguro_pct", 0.5)
        ajustes_aduaneiros_brl = st.number_input(
            "Ajustes ao valor aduaneiro (R$)",
            min_value=0.0,
            value=valor_padrao("ajustes_aduaneiros_brl", 0.0),
            help="Ex.: assists, royalties ou outros ajustes exigidos pelas regras de valoração."
            ,key="ajustes_aduaneiros_brl"
        )
        frete_interno_brl = st.number_input(
            "Frete interno até o estabelecimento (R$)", min_value=0.0,
            value=valor_padrao("frete_interno_brl", 0.0), step=500.0, key="frete_interno_brl"
        )

    with st.expander("3. Tributos e despesas do desembaraço"):
        modo_custos_importacao = seletor_modo_composicao(
            "Nível de composição dos custos aduaneiros",
            "modo_custos_importacao",
        )
        modo_importacao_detalhado = modo_custos_importacao == "Detalhado"
        if modo_importacao_detalhado:
            st.caption("Informe as taxas e bases efetivamente aplicáveis à classificação e à operação.")
        else:
            st.caption(
                "Informe um único total para tributos e despesas aduaneiras. Exclua o valor aduaneiro, "
                "frete internacional, seguro e frete interno, que são tratados separadamente. "
                "Créditos recuperáveis não são separados neste modo."
            )
        aliq_ii = percentual("II (%)", "aliq_ii", disabled=not modo_importacao_detalhado)
        aliq_ipi = percentual("IPI-importação (%)", "aliq_ipi", disabled=not modo_importacao_detalhado)
        aliq_pis = percentual("PIS-importação (%)", "aliq_pis", disabled=not modo_importacao_detalhado)
        aliq_cofins = percentual("Cofins-importação (%)", "aliq_cofins", disabled=not modo_importacao_detalhado)
        aliq_cbs = percentual("CBS-importação / transição (%)", "aliq_cbs", disabled=not modo_importacao_detalhado)
        aliq_ibs = percentual("IBS-importação / transição (%)", "aliq_ibs", disabled=not modo_importacao_detalhado)
        multiplo_base_cbs_ibs = st.number_input(
            "Base configurável CBS/IBS (múltiplo do valor aduaneiro)",
            min_value=0.0,
            value=valor_padrao("multiplo_base_cbs_ibs", 1.0),
            step=0.1,
            key="multiplo_base_cbs_ibs",
            disabled=not modo_importacao_detalhado,
        )
        aliq_icms = percentual("ICMS-importação (%)", "aliq_icms", disabled=not modo_importacao_detalhado)
        aliq_afrmm = percentual("AFRMM (%) sobre frete marítimo", "aliq_afrmm", disabled=not modo_importacao_detalhado)
        antidumping_brl = st.number_input(
            "Antidumping / medidas compensatórias (R$)", min_value=0.0,
            value=valor_padrao("antidumping_brl", 0.0), step=100.0,
            key="antidumping_brl", disabled=not modo_importacao_detalhado,
        )
        despesas_na_base_icms = st.number_input(
            "Despesas tributáveis incluídas na base do ICMS (R$)",
            min_value=0.0,
            value=valor_padrao("despesas_na_base_icms", 0.0),
            step=100.0,
            key="despesas_na_base_icms",
            disabled=not modo_importacao_detalhado,
        )
        custos_despacho = {
            "Armazenagem": st.number_input("Armazenagem (R$)", min_value=0.0, value=valor_padrao("custo_armazenagem", 0.0), step=100.0, key="custo_armazenagem", disabled=not modo_importacao_detalhado),
            "Capatazia / terminal": st.number_input("Capatazia / terminal (R$)", min_value=0.0, value=valor_padrao("custo_capatazia", 0.0), step=100.0, key="custo_capatazia", disabled=not modo_importacao_detalhado),
            "Despachante aduaneiro": st.number_input("Despachante aduaneiro (R$)", min_value=0.0, value=valor_padrao("custo_despachante", 0.0), step=100.0, key="custo_despachante", disabled=not modo_importacao_detalhado),
            "Taxa Siscomex": st.number_input("Taxa Siscomex (R$)", min_value=0.0, value=valor_padrao("taxa_siscomex", 0.0), step=50.0, key="taxa_siscomex", disabled=not modo_importacao_detalhado),
            "Taxas portuárias / aeroportuárias": st.number_input("Taxas portuárias / aeroportuárias (R$)", min_value=0.0, value=valor_padrao("taxas_terminal", 0.0), step=100.0, key="taxas_terminal", disabled=not modo_importacao_detalhado),
            "Honorários / agente de carga": st.number_input("Honorários / agente de carga (R$)", min_value=0.0, value=valor_padrao("honorarios_agente_carga", 0.0), step=100.0, key="honorarios_agente_carga", disabled=not modo_importacao_detalhado),
            "Licenças, análise e inspeção": st.number_input("Licenças, análise e inspeção (R$)", min_value=0.0, value=valor_padrao("licencas_inspecao", 0.0), step=100.0, key="licencas_inspecao", disabled=not modo_importacao_detalhado),
            "Outras despesas de importação": st.number_input("Outras despesas de importação (R$)", min_value=0.0, value=valor_padrao("outras_despesas_importacao", 0.0), step=100.0, key="outras_despesas_importacao", disabled=not modo_importacao_detalhado),
        }
        st.markdown("**Créditos tributários**")
        credita_ipi = st.checkbox("IPI recuperável", value=valor_padrao("credita_ipi", False), key="credita_ipi", disabled=not modo_importacao_detalhado)
        credita_pis = st.checkbox("PIS-importação recuperável", value=valor_padrao("credita_pis", False), key="credita_pis", disabled=not modo_importacao_detalhado)
        credita_cofins = st.checkbox("Cofins-importação recuperável", value=valor_padrao("credita_cofins", False), key="credita_cofins", disabled=not modo_importacao_detalhado)
        credita_cbs_ibs = st.checkbox("CBS/IBS-importação recuperáveis", value=valor_padrao("credita_cbs_ibs", False), key="credita_cbs_ibs", disabled=not modo_importacao_detalhado)
        credita_icms = st.checkbox("ICMS recuperável", value=valor_padrao("credita_icms", False), key="credita_icms", disabled=not modo_importacao_detalhado)
        custo_importacao_consolidado_brl = st.number_input(
            "Tributos e despesas aduaneiras consolidados (R$)",
            min_value=0.0,
            value=valor_padrao("custo_importacao_consolidado_brl", 0.0),
            step=1000.0,
            key="custo_importacao_consolidado_brl",
            disabled=modo_importacao_detalhado,
        )

    with st.expander("4. Receita e tributos sobre vendas"):
        devolucoes_descontos = st.number_input(
            "Devoluções, abatimentos e descontos (R$)", min_value=0.0,
            value=valor_padrao("devolucoes_descontos", 0.0), step=1000.0,
            key="devolucoes_descontos",
        )
        modo_tributos_venda = seletor_modo_composicao(
            "Nível de composição dos tributos sobre vendas",
            "modo_tributos_venda",
        )
        modo_vendas_detalhado = modo_tributos_venda == "Detalhado"
        aliq_icms_venda = percentual("ICMS efetivo sobre vendas (%)", "aliq_icms_venda", disabled=not modo_vendas_detalhado)
        aliq_pis_venda = percentual("PIS efetivo sobre vendas (%)", "aliq_pis_venda", disabled=not modo_vendas_detalhado)
        aliq_cofins_venda = percentual("Cofins efetiva sobre vendas (%)", "aliq_cofins_venda", disabled=not modo_vendas_detalhado)
        aliq_outros_venda = percentual(
            "Outros tributos sobre vendas / CBS / IBS efetivos (%)",
            "aliq_outros_venda",
            disabled=not modo_vendas_detalhado,
        )
        aliq_venda_consolidada = percentual(
            "Alíquota efetiva consolidada sobre vendas (%)",
            "aliq_venda_consolidada",
            disabled=modo_vendas_detalhado,
        )
        operador_pct = percentual(
            "Operação / armazenagem variável (% da receita líquida)", "operador_pct", 5.0
        )

    with st.expander("5. Opex do período"):
        modo_opex = seletor_modo_composicao(
            "Nível de composição do Opex",
            "modo_opex",
        )
        st.caption("Valores mensais; o total é multiplicado pela duração da DRE.")
        modo_opex_detalhado = modo_opex == "Detalhado"
        opex_detalhado = {
            "Pessoal e encargos": st.number_input("Pessoal e encargos / mês (R$)", min_value=0.0, value=valor_padrao("opex_pessoal", 90000.0), step=5000.0, key="opex_pessoal", disabled=not modo_opex_detalhado),
            "Aluguel e condomínio": st.number_input("Aluguel e condomínio / mês (R$)", min_value=0.0, value=valor_padrao("opex_aluguel", 25000.0), step=1000.0, key="opex_aluguel", disabled=not modo_opex_detalhado),
            "Utilidades e telecomunicações": st.number_input("Utilidades e telecomunicações / mês (R$)", min_value=0.0, value=valor_padrao("opex_utilidades", 10000.0), step=1000.0, key="opex_utilidades", disabled=not modo_opex_detalhado),
            "Serviços profissionais": st.number_input("Serviços profissionais / mês (R$)", min_value=0.0, value=valor_padrao("opex_servicos_profissionais", 15000.0), step=1000.0, key="opex_servicos_profissionais", disabled=not modo_opex_detalhado),
            "Comercial e marketing": st.number_input("Comercial e marketing / mês (R$)", min_value=0.0, value=valor_padrao("opex_comercial_marketing", 30000.0), step=1000.0, key="opex_comercial_marketing", disabled=not modo_opex_detalhado),
            "Sistemas e comunicações": st.number_input("Sistemas e comunicações / mês (R$)", min_value=0.0, value=valor_padrao("opex_sistemas", 5000.0), step=500.0, key="opex_sistemas", disabled=not modo_opex_detalhado),
            "Seguros": st.number_input("Seguros / mês (R$)", min_value=0.0, value=valor_padrao("opex_seguros", 5000.0), step=500.0, key="opex_seguros", disabled=not modo_opex_detalhado),
            "Depreciação e amortização": st.number_input("Depreciação e amortização / mês (R$)", min_value=0.0, value=valor_padrao("opex_depreciacao", 10000.0), step=1000.0, key="opex_depreciacao", disabled=not modo_opex_detalhado),
            "Despesas administrativas": st.number_input("Despesas administrativas / mês (R$)", min_value=0.0, value=valor_padrao("opex_administrativo", 5000.0), step=500.0, key="opex_administrativo", disabled=not modo_opex_detalhado),
            "Outros Opex": st.number_input("Outros Opex / mês (R$)", min_value=0.0, value=valor_padrao("opex_outros", 5000.0), step=500.0, key="opex_outros", disabled=not modo_opex_detalhado),
        }
        opex_consolidado_mensal = st.number_input(
            "Opex total consolidado / mês (R$)",
            min_value=0.0,
            value=valor_padrao("opex_consolidado_mensal", 200000.0),
            step=5000.0,
            key="opex_consolidado_mensal",
            disabled=modo_opex_detalhado,
        )
        opex_mensal = opex_detalhado if modo_opex_detalhado else {"Opex consolidado": opex_consolidado_mensal}
        juros_brl = st.number_input(
            "Juros e despesas financeiras do período (R$)", min_value=0.0,
            value=valor_padrao("juros_brl", 0.0), step=1000.0,
            key="juros_brl",
        )

    with st.expander("6. Tributos sobre lucro e remessas"):
        if regime_tributario == "Lucro Presumido":
            st.caption(
                "Estimativa para comércio: 1,20% de IRPJ + 1,08% de CSLL sobre a receita tributável. "
                "O adicional de IRPJ pode elevar essa soma até perto de 3,08%. Essa faixa não inclui "
                "PIS/Cofins, que devem ser informados separadamente em tributos sobre vendas."
            )
            aliq_irpj_faturamento = percentual(
                "IRPJ comercial efetivo sobre faturamento (%)", "aliq_irpj_faturamento", 1.20
            )
            aliq_csll_faturamento = percentual(
                "CSLL comercial efetiva sobre faturamento (%)", "aliq_csll_faturamento", 1.08
            )
            base_presumida_irpj = percentual(
                "Base presumida usada no adicional de IRPJ (%)", "base_presumida_irpj", 8.0
            )
            aliq_adicional_irpj = percentual(
                "Adicional de IRPJ sobre a base excedente (%)", "aliq_adicional_irpj", 10.0
            )
            limite_adicional_irpj_mensal = st.number_input(
                "Limite mensal da base para adicional de IRPJ (R$)",
                min_value=0.0,
                value=valor_padrao("limite_adicional_irpj_mensal", 20000.0),
                step=1000.0,
                key="limite_adicional_irpj_mensal",
            )
            aliq_ir_csll = 0.0
        else:
            aliq_ir_csll = percentual(
                "Brasil: carga efetiva estimada sobre lucro positivo (%)", "aliq_ir_csll", 32.0
            )
            aliq_irpj_faturamento = 0.0
            aliq_csll_faturamento = 0.0
            base_presumida_irpj = 0.0
            aliq_adicional_irpj = 0.0
            limite_adicional_irpj_mensal = 0.0
            st.caption(
                "Estimativa gerencial sobre lucro positivo; não substitui a apuração fiscal do regime."
            )
        aliq_federal_eua = percentual("EUA: imposto corporativo federal (%)", "aliq_federal_eua", 21.0)
        aliq_fl = percentual("Flórida: imposto corporativo estadual (%)", "aliq_fl", 5.5)
        rateio_fl = st.sidebar.number_input(
            "Parcela do lucro tributável atribuída à Flórida (%)",
            min_value=0.0,
            max_value=100.0,
            value=valor_padrao("rateio_fl", 100.0),
            step=1.0,
            key="rateio_fl",
        ) / 100
        opex_matriz_usd = st.number_input(
            "Opex da matriz atribuível à exportação (USD)", min_value=0.0,
            value=valor_padrao("opex_matriz_usd", 0.0), step=1000.0,
            key="opex_matriz_usd",
        )
        participacao_matriz = st.slider(
            "Parcela do lucro brasileiro atribuída à matriz (%)",
            min_value=0,
            max_value=100,
            value=valor_padrao("participacao_matriz", 75),
            step=5,
            key="participacao_matriz",
        ) / 100
        st.caption(f"Parcela atribuída à filial/local: {1 - participacao_matriz:.0%}.")
        retencao_dividendos = percentual(
            "Retenção sobre dividendos remetidos (%)", "retencao_dividendos", 10.0
        )
        custo_remessa = percentual("Custo cambial da remessa (%)", "custo_remessa", 1.0)

    with st.expander("7. Cenário 2: premissas alternativas"):
        preco_fob_c2 = st.number_input(
            "Preço FOB alternativo da matriz (USD por kit)",
            min_value=0.0,
            value=valor_padrao("preco_fob_c2", 220.0),
            step=10.0,
            key="preco_fob_c2",
        )
        quantidade_vendida_c2 = st.number_input(
            "Kits vendidos no cenário 2",
            min_value=0,
            max_value=int(quantidade),
            value=valor_padrao(
                "quantidade_vendida_c2",
                min(int(quantidade_vendida), int(quantidade)),
            ),
            step=100,
            key="quantidade_vendida_c2",
        )
        receita_por_kit_c2 = st.number_input(
            "Preço bruto de venda no Brasil no cenário 2 (R$/kit)",
            min_value=0.0,
            value=valor_padrao("receita_por_kit_c2", float(receita_por_kit)),
            step=100.0,
            key="receita_por_kit_c2",
        )
        fator_opex_c2 = st.number_input(
            "Fator do Opex local no cenário 2 (x)",
            min_value=0.0,
            max_value=5.0,
            value=valor_padrao("fator_opex_c2", 1.0),
            step=0.1,
            key="fator_opex_c2",
            help="1,0 mantém o mesmo Opex do cenário 1; 1,2 aumenta o Opex em 20%."
        )
        participacao_matriz_c2 = st.slider(
            "Parcela do lucro brasileiro atribuída à matriz (%)",
            min_value=0,
            max_value=100,
            value=valor_padrao("participacao_matriz_c2", 75),
            step=5,
            key="participacao_matriz_c2",
        ) / 100
        st.caption(f"Parcela atribuída à filial/local: {1 - participacao_matriz_c2:.0%}.")
        st.caption(
            "FOB, volume vendido, preço de venda, fator de Opex e participação variam por cenário. "
            "Câmbio, custos de importação e alíquotas permanecem compartilhados."
        )


def calcular_cenario(
    preco_fob_usd: float,
    participacao_matriz_cenario: float,
    quantidade_vendida_cenario: int,
    receita_por_kit_cenario: float,
    fator_opex_cenario: float = 1.0,
) -> dict[str, object]:
    fob_usd = preco_fob_usd * quantidade
    frete_brl = frete_usd * cambio
    seguro_brl = (fob_usd + frete_usd) * cambio * seguro_pct
    valor_aduaneiro = fob_usd * cambio + frete_brl + seguro_brl + ajustes_aduaneiros_brl
    if modo_custos_importacao == "Detalhado":
        ii = valor_aduaneiro * aliq_ii
        base_ipi = valor_aduaneiro + ii + antidumping_brl
        ipi = base_ipi * aliq_ipi
        pis_importacao = valor_aduaneiro * aliq_pis
        cofins_importacao = valor_aduaneiro * aliq_cofins
        cbs_ibs_importacao = (
            valor_aduaneiro * multiplo_base_cbs_ibs * (aliq_cbs + aliq_ibs)
        )
        afrmm = frete_brl * aliq_afrmm if modal == "Marítimo" else 0.0
        base_icms_sem_grossup = (
            valor_aduaneiro
            + ii
            + ipi
            + pis_importacao
            + cofins_importacao
            + afrmm
            + antidumping_brl
            + despesas_na_base_icms
        )
        base_icms = base_icms_sem_grossup / (1 - aliq_icms) if aliq_icms < 1 else 0.0
        icms = base_icms * aliq_icms
        tributos_importacao = (
            ii + ipi + pis_importacao + cofins_importacao + cbs_ibs_importacao
            + icms + afrmm + antidumping_brl
        )
        despesas_despacho = sum(custos_despacho.values())
        composicao_importacao = [
            ("II", ii),
            ("IPI-importação", ipi),
            ("PIS-importação", pis_importacao),
            ("Cofins-importação", cofins_importacao),
            ("CBS/IBS-importação estimados", cbs_ibs_importacao),
            ("ICMS-importação", icms),
            ("AFRMM", afrmm),
            ("Antidumping / medidas compensatórias", antidumping_brl),
            *custos_despacho.items(),
        ]
    else:
        ii = ipi = pis_importacao = cofins_importacao = cbs_ibs_importacao = 0.0
        afrmm = icms = base_icms = 0.0
        tributos_importacao = custo_importacao_consolidado_brl
        despesas_despacho = 0.0
        composicao_importacao = [
            ("Tributos e despesas aduaneiras consolidados", custo_importacao_consolidado_brl)
        ]
    despesas_locais = despesas_despacho + frete_interno_brl
    desembolso_importacao = valor_aduaneiro + tributos_importacao + despesas_locais
    if modo_custos_importacao == "Detalhado":
        creditos = (
            (ipi if credita_ipi else 0.0)
            + (pis_importacao if credita_pis else 0.0)
            + (cofins_importacao if credita_cofins else 0.0)
            + (cbs_ibs_importacao if credita_cbs_ibs else 0.0)
            + (icms if credita_icms else 0.0)
        )
    else:
        creditos = 0.0
    custo_estoque = max(desembolso_importacao - creditos, 0.0)
    custo_unitario = custo_estoque / quantidade
    cmv = custo_unitario * quantidade_vendida_cenario

    receita_bruta = receita_por_kit_cenario * quantidade_vendida_cenario
    receita_liquida_comercial = max(receita_bruta - devolucoes_descontos, 0.0)
    if modo_tributos_venda == "Detalhado":
        aliquota_total_venda = (
            aliq_icms_venda + aliq_pis_venda + aliq_cofins_venda + aliq_outros_venda
        )
    else:
        aliquota_total_venda = aliq_venda_consolidada
    tributos_venda = receita_liquida_comercial * aliquota_total_venda
    receita_liquida = receita_liquida_comercial - tributos_venda
    opex_total = sum(opex_mensal.values()) * meses_operacao * fator_opex_cenario
    custo_operacao_variavel = receita_liquida * operador_pct
    lucro_operacional = receita_liquida - cmv - custo_operacao_variavel - opex_total
    lucro_antes_ir = lucro_operacional - juros_brl
    if regime_tributario == "Lucro Presumido":
        imposto_irpj = receita_liquida_comercial * aliq_irpj_faturamento
        base_irpj_adicional = receita_liquida_comercial * base_presumida_irpj
        limite_irpj_adicional = limite_adicional_irpj_mensal * meses_operacao
        imposto_irpj_adicional = (
            max(base_irpj_adicional - limite_irpj_adicional, 0.0)
            * aliq_adicional_irpj
        )
        imposto_csll = receita_liquida_comercial * aliq_csll_faturamento
        imposto_br = imposto_irpj + imposto_irpj_adicional + imposto_csll
        aliquota_efetiva_irpj_csll = (
            imposto_br / receita_liquida_comercial
            if receita_liquida_comercial > 0
            else None
        )
    else:
        imposto_br = max(lucro_antes_ir, 0.0) * aliq_ir_csll
        imposto_irpj = imposto_br
        imposto_irpj_adicional = 0.0
        imposto_csll = 0.0
        aliquota_efetiva_irpj_csll = (
            imposto_br / receita_liquida_comercial
            if receita_liquida_comercial > 0
            else None
        )
    lucro_liquido_br = lucro_antes_ir - imposto_br

    custo_fabricacao = custo_fabricacao_usd * quantidade * cambio
    lucro_exportacao_antes_imposto = fob_usd * cambio - custo_fabricacao - opex_matriz_usd * cambio
    imposto_fl = max(lucro_exportacao_antes_imposto, 0.0) * rateio_fl * aliq_fl
    base_federal = max(lucro_exportacao_antes_imposto - imposto_fl, 0.0)
    imposto_federal = base_federal * aliq_federal_eua
    lucro_exportacao_liquido = lucro_exportacao_antes_imposto - imposto_fl - imposto_federal

    matriz_lucro_br = max(lucro_liquido_br, 0.0) * participacao_matriz_cenario
    retencao = matriz_lucro_br * retencao_dividendos
    remessa_apos_retencao = matriz_lucro_br - retencao
    custo_remessa_brl = remessa_apos_retencao * custo_remessa
    remessa_liquida = remessa_apos_retencao - custo_remessa_brl
    lucro_global = lucro_exportacao_liquido + lucro_liquido_br - matriz_lucro_br + remessa_liquida

    composicao = [
        ("Valor aduaneiro", valor_aduaneiro),
        *composicao_importacao,
        ("Frete interno", frete_interno_brl),
        ("Créditos tributários estimados", -creditos),
        ("Custo de aquisição do estoque", custo_estoque),
    ]
    dre = [
        ("Receita bruta", receita_bruta),
        ("Devoluções, abatimentos e descontos", -min(devolucoes_descontos, receita_bruta)),
        ("Tributos sobre vendas", -tributos_venda),
        ("Receita líquida", receita_liquida),
        ("Custo das mercadorias vendidas (CMV)", -cmv),
        ("Operação / armazenagem variável", -custo_operacao_variavel),
        ("Opex fixo do período", -opex_total),
        ("Lucro operacional", lucro_operacional),
        ("Juros e despesas financeiras", -juros_brl),
        ("Resultado antes de IR/CSLL estimados", lucro_antes_ir),
    ]
    if regime_tributario == "Lucro Presumido":
        dre.extend([
            ("IRPJ comercial sobre faturamento", -imposto_irpj),
            ("Adicional de IRPJ", -imposto_irpj_adicional),
            ("CSLL comercial sobre faturamento", -imposto_csll),
        ])
    else:
        dre.append(("IR/CSLL estimados", -imposto_br))
    dre.append(("Lucro líquido Brasil", lucro_liquido_br))
    return {
        "fob_usd": fob_usd,
        "quantidade_vendida": quantidade_vendida_cenario,
        "receita_por_kit": receita_por_kit_cenario,
        "fator_opex": fator_opex_cenario,
        "valor_aduaneiro": valor_aduaneiro,
        "ii": ii,
        "ipi": ipi,
        "pis_importacao": pis_importacao,
        "cofins_importacao": cofins_importacao,
        "icms": icms,
        "afrmm": afrmm,
        "base_icms": base_icms,
        "desembolso_importacao": desembolso_importacao,
        "creditos": creditos,
        "custo_estoque": custo_estoque,
        "custo_unitario": custo_unitario,
        "cmv": cmv,
        "receita_bruta": receita_bruta,
        "receita_liquida": receita_liquida,
        "tributos_venda": tributos_venda,
        "aliquota_total_venda": aliquota_total_venda,
        "custo_operacao_variavel": custo_operacao_variavel,
        "lucro_operacional": lucro_operacional,
        "lucro_liquido_br": lucro_liquido_br,
        "imposto_br": imposto_br,
        "imposto_irpj": imposto_irpj,
        "imposto_irpj_adicional": imposto_irpj_adicional,
        "imposto_csll": imposto_csll,
        "aliquota_efetiva_irpj_csll": aliquota_efetiva_irpj_csll,
        "lucro_exportacao_antes_imposto": lucro_exportacao_antes_imposto,
        "imposto_fl": imposto_fl,
        "imposto_federal": imposto_federal,
        "lucro_exportacao_liquido": lucro_exportacao_liquido,
        "retencao": retencao,
        "custo_remessa": custo_remessa_brl,
        "remessa_liquida": remessa_liquida,
        "lucro_matriz_br": matriz_lucro_br,
        "lucro_filial_retido": lucro_liquido_br - matriz_lucro_br,
        "lucro_total_matriz": lucro_exportacao_liquido + remessa_liquida,
        "lucro_global": lucro_global,
        "markup": receita_por_kit_cenario / custo_unitario if custo_unitario > 0 else None,
        "margem_br": lucro_liquido_br / receita_liquida if receita_liquida > 0 else None,
        "margem_exportacao": (
            lucro_exportacao_liquido / (fob_usd * cambio) if fob_usd else 0.0
        ),
        "composicao": composicao,
        "dre": dre,
    }


c2_share = participacao_matriz_c2
cenario1 = calcular_cenario(
    preco_fob_base,
    participacao_matriz,
    int(quantidade_vendida),
    receita_por_kit,
)
cenario2 = calcular_cenario(
    preco_fob_c2,
    c2_share,
    int(quantidade_vendida_c2),
    receita_por_kit_c2,
    fator_opex_c2,
)
cenario1_share = participacao_matriz
cenario2_share = c2_share
salvar_padroes()


def tabela_linhas(linhas: list[tuple[str, float]]) -> pd.DataFrame:
    return pd.DataFrame(linhas, columns=["Conta", "Valor (R$)"])


def criar_grafico_resultados() -> go.Figure:
    figura = go.Figure()
    series = [
        ("Lucro líquido da exportação da matriz", "lucro_exportacao_liquido", "#2878a0"),
        ("Remessa líquida à matriz", "remessa_liquida", "#d78a36"),
        ("Resultado retido na filial/local", "lucro_filial_retido", "#4e9a72"),
    ]
    for nome, chave, cor in series:
        valores = [float(cenario1[chave]), float(cenario2[chave])]
        figura.add_trace(
            go.Bar(
                name=nome,
                x=["Cenário 1", "Cenário 2"],
                y=valores,
                marker_color=cor,
                text=[moeda_resumida(valor) for valor in valores],
                textposition="auto",
                customdata=[moeda(valor) for valor in valores],
                hovertemplate="<b>%{x}</b><br>%{fullData.name}: %{customdata}<extra></extra>",
            )
        )
    figura.update_layout(
        template="plotly_white",
        barmode="group",
        height=420,
        margin={"l": 45, "r": 35, "t": 45, "b": 100},
        font={"family": "Aptos, Segoe UI, sans-serif", "size": 10, "color": "#203040"},
        title={"text": "Lucro por cenário e entidade", "x": 0.02, "font": {"size": 16}},
        legend={"orientation": "h", "yanchor": "top", "y": -0.22, "xanchor": "center", "x": 0.5},
        xaxis_title="Cenário",
        yaxis_title="Lucro (R$)",
        uniformtext_minsize=9,
        uniformtext_mode="hide",
    )
    figura.update_yaxes(
        tickprefix="R$ ", tickformat="~s", gridcolor="#e5ebef",
        zerolinecolor="#82909a", rangemode="tozero"
    )
    figura.update_xaxes(categoryorder="array", categoryarray=["Cenário 1", "Cenário 2"], automargin=True)
    return figura


st.warning(
    "Este modelo não consulta Siscomex, Classif, TEC, regimes especiais ou legislação em tempo real. "
    "Não preenche automaticamente NCM, origem, preferências tarifárias, bases especiais, créditos "
    "ou regras da reforma tributária. Use alíquotas e bases validadas por despachante e contador."
)

abas = st.tabs(["Resumo", "Composição da importação", "DRE Brasil", "Cenários e matriz"])
tab_resumo = abas[0]
tab_importacao = abas[1]
tab_dre = abas[2]
tab_cenarios = abas[3]

with tab_resumo:
    st.subheader("📌 Resumo da DRE Operacional (Brasil)")
    impostos_br_resumo = cenario1["tributos_venda"] + cenario1["imposto_br"]
    aliquota_impostos_br_resumo = (
        impostos_br_resumo / cenario1["receita_bruta"]
        if cenario1["receita_bruta"] > 0
        else 0.0
    )
    indicadores_dre = [
        ("Faturamento Bruto (R$)", moeda(cenario1["receita_bruta"])),
        ("Acomodação / Operador (R$)", moeda(cenario1["custo_operacao_variavel"])),
        ("Landed Cost (R$)", moeda(cenario1["custo_estoque"])),
        ("Lucro Operacional (R$)", moeda(cenario1["lucro_operacional"])),
        (f"Impostos BR ({aliquota_impostos_br_resumo:.0%})", moeda(impostos_br_resumo)),
        ("Lucro Líquido BR (100%)", moeda(cenario1["lucro_liquido_br"])),
    ]
    colunas_dre = st.columns(6)
    for coluna, (rotulo, valor) in zip(colunas_dre, indicadores_dre):
        coluna.markdown(
            f"<div style='min-height:56px;padding:5px 4px;border-bottom:2px solid #2878a0;'>"
            f"<div style='font-size:10px;line-height:1.2;color:#52606d;'>{html_escape(rotulo)}</div>"
            f"<div style='font-size:13px;line-height:1.2;font-weight:700;color:#18364a;margin-top:4px;'>{html_escape(valor)}</div>"
            "</div>",
            unsafe_allow_html=True,
        )
    st.caption(
        "Indicadores do cenário 1. Impostos BR somam tributos sobre vendas e IRPJ/CSLL estimados; "
        "tributos de importação compõem o landed cost, enquanto créditos estimados reduzem o custo de aquisição do estoque."
    )
    st.subheader("⚖️ Comparativo Executivo - Dois Cenários")

    def margem_resumo(lucro: float, receita: float) -> str:
        return f"{lucro / receita:.2%}".replace(".", ",") if receita > 0 else "Não disponível"

    comparativo_executivo = pd.DataFrame(
        [
            {
                "Cenário Societário / Comercial": "1. Subsidiária controlada",
                "FOB do Cenário (USD)": cenario1["fob_usd"],
                "Lucro Matriz EUA - Exportação (R$)": cenario1["lucro_exportacao_liquido"],
                "Margem Matriz EUA s/ FOB (%)": cenario1["margem_exportacao"] * 100,
                "Lucro Matriz Brasil (R$)": cenario1["lucro_matriz_br"],
                "Margem Matriz Brasil s/ Faturamento (%)": cenario1["lucro_matriz_br"] / cenario1["receita_bruta"] * 100 if cenario1["receita_bruta"] else None,
                "Lucro Total da Matriz (R$)": cenario1["lucro_total_matriz"],
                "Lucro Filial / Empresa Local Brasil (R$)": cenario1["lucro_filial_retido"],
                "Margem Filial / Local s/ Faturamento (%)": cenario1["lucro_filial_retido"] / cenario1["receita_bruta"] * 100 if cenario1["receita_bruta"] else None,
                "Lucro Global Consolidado (R$)": cenario1["lucro_global"],
                "Lucro Global por Kit (R$)": cenario1["lucro_global"] / quantidade,
                "Markup s/ custo de aquisição (x)": cenario1["markup"],
            },
            {
                "Cenário Societário / Comercial": "2. Distribuidor Independente",
                "FOB do Cenário (USD)": cenario2["fob_usd"],
                "Lucro Matriz EUA - Exportação (R$)": cenario2["lucro_exportacao_liquido"],
                "Margem Matriz EUA s/ FOB (%)": cenario2["margem_exportacao"] * 100,
                "Lucro Matriz Brasil (R$)": cenario2["lucro_matriz_br"],
                "Margem Matriz Brasil s/ Faturamento (%)": cenario2["lucro_matriz_br"] / cenario2["receita_bruta"] * 100 if cenario2["receita_bruta"] else None,
                "Lucro Total da Matriz (R$)": cenario2["lucro_total_matriz"],
                "Lucro Filial / Empresa Local Brasil (R$)": cenario2["lucro_filial_retido"],
                "Margem Filial / Local s/ Faturamento (%)": cenario2["lucro_filial_retido"] / cenario2["receita_bruta"] * 100 if cenario2["receita_bruta"] else None,
                "Lucro Global Consolidado (R$)": None,
                "Lucro Global por Kit (R$)": None,
                "Markup s/ custo de aquisição (x)": cenario2["markup"],
            },
        ],
    )
    colunas_moeda_executiva = [
        "Lucro Matriz EUA - Exportação (R$)",
        "Lucro Matriz Brasil (R$)",
        "Lucro Total da Matriz (R$)",
        "Lucro Filial / Empresa Local Brasil (R$)",
        "Lucro Global Consolidado (R$)",
        "Lucro Global por Kit (R$)",
    ]
    cabecalho_executivo = "".join(
        f"<th>{html_escape(str(coluna))}</th>" for coluna in comparativo_executivo.columns
    )
    linhas_executivas_html = []
    for indice, (_, linha) in enumerate(comparativo_executivo.iterrows()):
        celulas = []
        for coluna in comparativo_executivo.columns:
            valor = linha[coluna]
            if pd.isna(valor):
                texto = "N/A"
            elif coluna == "Cenário Societário / Comercial":
                texto = str(valor)
            elif coluna == "FOB do Cenário (USD)":
                texto = f"USD {valor:,.2f}"
            elif "Markup" in coluna:
                texto = f"{valor:.2f}x".replace(".", ",")
            elif "(%)" in coluna:
                texto = f"{valor:.2f}%".replace(".", ",")
            elif coluna in colunas_moeda_executiva:
                texto = moeda(float(valor))
            else:
                texto = str(valor)
            celulas.append(f"<td>{html_escape(texto)}</td>")
        linhas_executivas_html.append(
            f'<tr class="linha-{indice % 2}">{"".join(celulas)}</tr>'
        )
    st.html(f"""
    <div style="overflow-x:auto;width:100%;">
      <table class="synvitta-table" style="border-collapse:collapse;table-layout:fixed;width:100%;min-width:1500px;font-family:Segoe UI,Arial,sans-serif;">
        <thead><tr>{cabecalho_executivo}</tr></thead>
        <tbody>{''.join(linhas_executivas_html)}</tbody>
      </table>
    </div>
    <style>
      .synvitta-table, .synvitta-table * {{ box-sizing:border-box; writing-mode:horizontal-tb; transform:none; }}
      .synvitta-table th {{ background:#18364a;color:#fff;font-size:9px;font-weight:700;text-align:center;vertical-align:middle;white-space:normal;padding:8px 5px;border-right:1px solid #496174;line-height:1.25;overflow-wrap:anywhere; }}
      .synvitta-table td {{ color:#203040;font-size:10px;font-weight:700;text-align:center;vertical-align:middle;white-space:normal;padding:9px 5px;border-bottom:1px solid #d9e1e8;line-height:1.25;overflow-wrap:anywhere; }}
      .synvitta-table th:first-child, .synvitta-table td:first-child {{ width:180px;text-align:left; }}
      .synvitta-table .linha-1 {{ background:#f0f5f7; }}
    </style>
    """)
    st.caption("Os valores apresentados refletem exclusivamente as premissas preenchidas no painel lateral.")
    st.plotly_chart(
        criar_grafico_resultados(),
        width="stretch",
        alt="Lucro líquido exportador, matriz no Brasil e filial/local para os dois cenários",
        config={"displayModeBar": False, "responsive": True},
    )

with tab_importacao:
    st.subheader("Memória de cálculo aduaneiro e custo do estoque")
    st.write(
        f"Valor aduaneiro: **{moeda(cenario1['valor_aduaneiro'])}** · "
        f"Base calculada do ICMS: **{moeda(cenario1['base_icms'])}** · "
        f"Desembolso de importação: **{moeda(cenario1['desembolso_importacao'])}** · "
        f"Créditos informados: **{moeda(cenario1['creditos'])}**"
    )
    st.dataframe(
        tabela_linhas(cenario1["composicao"]),
        hide_index=True,
        column_config={"Valor (R$)": st.column_config.NumberColumn(format="R$ %.2f")},
        alt="Composição do valor aduaneiro, tributos, despesas e créditos da importação",
    )
    if modo_custos_importacao == "Detalhado":
        st.caption(
            "O ICMS é estimado por gross-up sobre uma base configurável simplificada. "
            "Confirme composição da base, exclusões, reduções e créditos para a UF e operação."
        )
    else:
        st.caption(
            "Modo consolidado: o total informado não discrimina tributos nem créditos recuperáveis. "
            "O frete interno continua sendo somado separadamente."
        )

with tab_dre:
    st.subheader("DRE gerencial brasileira")
    st.write(
        f"CMV do período: **{moeda(cenario1['cmv'])}** · "
        f"Estoque final estimado: **{moeda(cenario1['custo_estoque'] - cenario1['cmv'])}** · "
        f"Lucro operacional: **{moeda(cenario1['lucro_operacional'])}**"
    )
    st.dataframe(
        tabela_linhas(cenario1["dre"]),
        hide_index=True,
        column_config={"Valor (R$)": st.column_config.NumberColumn(format="R$ %.2f")},
        alt="DRE gerencial brasileira com receita líquida, CMV, despesas e lucro",
    )
    if regime_tributario == "Lucro Presumido":
        carga_efetiva_texto = (
            f"{cenario1['aliquota_efetiva_irpj_csll']:.2%}".replace(".", ",")
            if cenario1["aliquota_efetiva_irpj_csll"] is not None
            else "Não disponível"
        )
        st.caption(
            f"IRPJ + CSLL efetivos estimados: {carga_efetiva_texto} da receita comercial tributável. "
            "PIS/Cofins ficam na seção de tributos sobre vendas e não entram nessa taxa."
        )
    opex_df = pd.DataFrame(
        [(nome, valor, valor * meses_operacao) for nome, valor in opex_mensal.items()],
        columns=["Despesa operacional", "Mensal (R$)", "Período (R$)"],
    )
    with st.expander("Abrir composição do Opex"):
        st.dataframe(
            opex_df,
            hide_index=True,
            column_config={
                "Mensal (R$)": st.column_config.NumberColumn(format="R$ %.2f"),
                "Período (R$)": st.column_config.NumberColumn(format="R$ %.2f"),
            },
            alt="Detalhamento das despesas operacionais mensais e do período",
        )

with tab_cenarios:
    st.subheader("Comparação dos cenários")
    linhas_comparativo = [
        ("Preço FOB matriz", "USD/kit", preco_fob_base, preco_fob_c2),
        ("FOB total", "USD", cenario1["fob_usd"], cenario2["fob_usd"]),
        ("Kits vendidos", "kits", cenario1["quantidade_vendida"], cenario2["quantidade_vendida"]),
        ("Preço bruto de venda Brasil", "R$/kit", cenario1["receita_por_kit"], cenario2["receita_por_kit"]),
        ("Fator de Opex local", "x", cenario1["fator_opex"], cenario2["fator_opex"]),
        ("Valor aduaneiro", "R$", cenario1["valor_aduaneiro"], cenario2["valor_aduaneiro"]),
        ("Desembolso total da importação", "R$", cenario1["desembolso_importacao"], cenario2["desembolso_importacao"]),
        ("Créditos tributários estimados", "R$", cenario1["creditos"], cenario2["creditos"]),
        ("Custo líquido de aquisição do estoque", "R$", cenario1["custo_estoque"], cenario2["custo_estoque"]),
        ("Custo de aquisição por kit", "R$/kit", cenario1["custo_unitario"], cenario2["custo_unitario"]),
        ("CMV do período", "R$", cenario1["cmv"], cenario2["cmv"]),
        ("Receita líquida Brasil", "R$", cenario1["receita_liquida"], cenario2["receita_liquida"]),
        ("Lucro líquido Brasil", "R$", cenario1["lucro_liquido_br"], cenario2["lucro_liquido_br"]),
        (
            "Markup (preço bruto / custo de aquisição)",
            "x",
            cenario1["markup"],
            cenario2["markup"],
        ),
        ("IRPJ + CSLL calculados", "R$", cenario1["imposto_br"], cenario2["imposto_br"]),
        (
            "Alíquota efetiva IRPJ + CSLL",
            "%",
            cenario1["aliquota_efetiva_irpj_csll"] * 100 if cenario1["aliquota_efetiva_irpj_csll"] is not None else None,
            cenario2["aliquota_efetiva_irpj_csll"] * 100 if cenario2["aliquota_efetiva_irpj_csll"] is not None else None,
        ),
        (
            "Margem líquida Brasil / receita líquida",
            "%",
            cenario1["margem_br"] * 100 if cenario1["margem_br"] is not None else None,
            cenario2["margem_br"] * 100 if cenario2["margem_br"] is not None else None,
        ),
        ("Parcela atribuída à matriz", "%", cenario1_share * 100, cenario2_share * 100),
        ("Parcela atribuída à filial/local", "%", (1 - cenario1_share) * 100, (1 - cenario2_share) * 100),
        ("Resultado da matriz no Brasil antes da remessa", "R$", cenario1["lucro_matriz_br"], cenario2["lucro_matriz_br"]),
        ("Resultado retido na filial/local", "R$", cenario1["lucro_filial_retido"], cenario2["lucro_filial_retido"]),
        ("Retenção sobre dividendos", "R$", cenario1["retencao"], cenario2["retencao"]),
        ("Custo cambial da remessa", "R$", cenario1["custo_remessa"], cenario2["custo_remessa"]),
        ("Remessa líquida à matriz", "R$", cenario1["remessa_liquida"], cenario2["remessa_liquida"]),
        ("Lucro líquido da exportação da matriz", "R$", cenario1["lucro_exportacao_liquido"], cenario2["lucro_exportacao_liquido"]),
        (
            "Margem líquida exportação / FOB convertido",
            "%",
            cenario1["margem_exportacao"] * 100,
            cenario2["margem_exportacao"] * 100,
        ),
        ("Lucro total da matriz (exportação + remessa)", "R$", cenario1["lucro_total_matriz"], cenario2["lucro_total_matriz"]),
        ("Lucro global consolidado", "R$", cenario1["lucro_global"], None),
        ("Lucro global consolidado por kit", "R$/kit", cenario1["lucro_global"] / quantidade, None),
    ]
    comparativo = pd.DataFrame(
        linhas_comparativo,
        columns=["Indicador", "Unidade", "Cenário 1", "Cenário 2"],
    )
    comparativo_apresentacao = comparativo.copy()
    comparativo_apresentacao[["Cenário 1", "Cenário 2"]] = comparativo_apresentacao[
        ["Cenário 1", "Cenário 2"]
    ].astype(object)
    for indice, linha in comparativo.iterrows():
        unidade = linha["Unidade"]
        for coluna in ["Cenário 1", "Cenário 2"]:
            valor = linha[coluna]
            if pd.isna(valor):
                texto = "Não disponível"
            elif unidade == "%":
                texto = f"{valor:.2f}%"
            elif unidade == "USD":
                texto = f"USD {valor:,.2f}"
            elif unidade == "USD/kit":
                texto = f"USD {valor:,.2f}/kit"
            elif unidade == "R$/kit":
                texto = f"{moeda(float(valor))}/kit"
            elif unidade == "kits":
                texto = f"{int(valor):,}".replace(",", ".")
            elif unidade == "x":
                texto = f"{valor:.2f}x"
            else:
                texto = moeda(float(valor))
            comparativo_apresentacao.at[indice, coluna] = texto
    linhas_resultado_global = comparativo["Indicador"].isin(
        ["Lucro global consolidado", "Lucro global consolidado por kit"]
    )
    comparativo_apresentacao.loc[linhas_resultado_global, "Cenário 2"] = "N/A"
    st.dataframe(
        comparativo_apresentacao,
        hide_index=True,
        alt="Comparação detalhada de importação, DRE, margens e alocação societária dos dois cenários",
    )
    st.caption(
        f"Participação da matriz no lucro líquido brasileiro: "
        f"{cenario1_share:.0%} no cenário 1 e {cenario2_share:.0%} no cenário 2."
    )
def linha_resumo_cenario(
    nome: str,
    cenario: dict[str, object],
    preco_fob_kit: float,
    participacao_matriz_cenario: float,
    global_aplicavel: bool = True,
) -> dict[str, object]:
    return {
        "Cenário": nome,
        "Preço FOB matriz (USD/kit)": preco_fob_kit,
        "FOB total (USD)": cenario["fob_usd"],
        "Kits vendidos": cenario["quantidade_vendida"],
        "Preço venda Brasil (R$/kit)": cenario["receita_por_kit"],
        "Fator Opex local": cenario["fator_opex"],
        "Custo importação (R$)": cenario["desembolso_importacao"],
        "Estoque (R$)": cenario["custo_estoque"],
        "Lucro líquido Brasil (R$)": cenario["lucro_liquido_br"],
        "IRPJ estimado (R$)": cenario["imposto_irpj"],
        "Adicional IRPJ (R$)": cenario["imposto_irpj_adicional"],
        "CSLL estimada (R$)": cenario["imposto_csll"],
        "IRPJ+CSLL efetivos (%)": cenario["aliquota_efetiva_irpj_csll"] * 100 if cenario["aliquota_efetiva_irpj_csll"] is not None else None,
        "Markup multiplicador (x)": cenario["markup"],
        "Margem líquida Brasil (%)": cenario["margem_br"] * 100 if cenario["margem_br"] is not None else None,
        "Parcela matriz (%)": participacao_matriz_cenario * 100,
        "Parcela filial/local (%)": (1 - participacao_matriz_cenario) * 100,
        "Resultado matriz Brasil (R$)": cenario["lucro_matriz_br"],
        "Resultado retido filial/local (R$)": cenario["lucro_filial_retido"],
        "Retenção dividendos (R$)": cenario["retencao"],
        "Custo cambial remessa (R$)": cenario["custo_remessa"],
        "Remessa líquida à matriz (R$)": cenario["remessa_liquida"],
        "Lucro líquido exportação (R$)": cenario["lucro_exportacao_liquido"],
        "Margem exportação (%)": cenario["margem_exportacao"] * 100,
        "Lucro total da matriz (R$)": cenario["lucro_total_matriz"],
        "Lucro global consolidado (R$)": cenario["lucro_global"] if global_aplicavel else "N/A",
        "Lucro global por kit (R$)": cenario["lucro_global"] / quantidade if global_aplicavel else "N/A",
    }


resumo_exportacao = pd.DataFrame(
    [
        linha_resumo_cenario("Cenário 1", cenario1, preco_fob_base, cenario1_share),
        linha_resumo_cenario("Cenário 2", cenario2, preco_fob_c2, cenario2_share, global_aplicavel=False),
    ]
)
premissas_exportacao = pd.DataFrame(
    [
        ("NCM", ncm_codigo),
        ("País de origem", pais_origem),
        ("Local de origem / embarque", local_origem),
        ("UF de destino", uf_destino),
        ("Incoterm negociado", incoterm),
        ("Regime tributário", regime_tributario),
        ("Registro / licença sanitária", registro_sanitario),
        ("Kits importados", quantidade),
        ("Kits vendidos", quantidade_vendida),
        ("Câmbio R$/USD", cambio),
        ("FOB base USD/kit", preco_fob_base),
        ("FOB cenário 2 USD/kit", preco_fob_c2),
        ("Kits vendidos cenário 2", quantidade_vendida_c2),
        ("Preço venda Brasil cenário 2 R$/kit", receita_por_kit_c2),
        ("Fator Opex local cenário 2", fator_opex_c2),
        ("IRPJ comercial sobre faturamento (%)", aliq_irpj_faturamento),
        ("CSLL comercial sobre faturamento (%)", aliq_csll_faturamento),
        ("Base presumida do adicional IRPJ (%)", base_presumida_irpj),
        ("Alíquota adicional IRPJ (%)", aliq_adicional_irpj),
        ("Limite mensal adicional IRPJ (R$)", limite_adicional_irpj_mensal),
        ("Modo de composição da importação", modo_custos_importacao),
        ("Tributos e despesas aduaneiras consolidados R$", custo_importacao_consolidado_brl),
        ("Modo de composição dos tributos sobre vendas", modo_tributos_venda),
        ("Alíquota efetiva sobre vendas", cenario1["aliquota_total_venda"]),
        ("Modo de composição do Opex", modo_opex),
        ("Opex consolidado mensal R$", opex_consolidado_mensal),
        ("Parcela matriz cenário 1", cenario1_share),
        ("Parcela filial/local cenário 1", 1 - cenario1_share),
        ("Parcela matriz cenário 2", cenario2_share),
        ("Parcela filial/local cenário 2", 1 - cenario2_share),
        ("Frete internacional USD", frete_usd),
        ("Seguro percentual", seguro_pct),
        ("II percentual", aliq_ii),
        ("IPI percentual", aliq_ipi),
        ("PIS-importação percentual", aliq_pis),
        ("Cofins-importação percentual", aliq_cofins),
        ("CBS-importação percentual", aliq_cbs),
        ("IBS-importação percentual", aliq_ibs),
        ("Base CBS/IBS múltiplo do VA", multiplo_base_cbs_ibs),
        ("ICMS-importação percentual", aliq_icms),
        ("AFRMM percentual", aliq_afrmm),
        ("Período da DRE em meses", meses_operacao),
        ("Opex mensal (R$)", sum(opex_mensal.values())),
        ("Alíquota IR/CSLL sobre lucro (outros regimes)", aliq_ir_csll),
        ("Alíquota federal EUA", aliq_federal_eua),
        ("Alíquota estadual Flórida", aliq_fl),
    ],
    columns=["Premissa", "Valor informado"],
)
arquivo_excel = BytesIO()
dados_grafico_excel = pd.DataFrame(
    [
        {
            "Cenário": "Cenário 1",
            "Resultado retido filial/local (R$)": cenario1["lucro_filial_retido"],
            "Remessa líquida à matriz (R$)": cenario1["remessa_liquida"],
            "Lucro líquido exportação (R$)": cenario1["lucro_exportacao_liquido"],
            "Lucro global consolidado (R$)": cenario1["lucro_global"],
        },
        {
            "Cenário": "Cenário 2",
            "Resultado retido filial/local (R$)": cenario2["lucro_filial_retido"],
            "Remessa líquida à matriz (R$)": cenario2["remessa_liquida"],
            "Lucro líquido exportação (R$)": cenario2["lucro_exportacao_liquido"],
            "Lucro global consolidado (R$)": "N/A",
        },
    ]
)
comparativo_excel = comparativo.copy()
comparativo_excel["Cenário 2"] = comparativo_excel["Cenário 2"].astype(object)
comparativo_excel.loc[linhas_resultado_global, "Cenário 2"] = "N/A"
with pd.ExcelWriter(arquivo_excel, engine="openpyxl") as writer:
    resumo_exportacao.to_excel(writer, sheet_name="Resumo", index=False)
    premissas_exportacao.to_excel(writer, sheet_name="Premissas", index=False)
    comparativo_excel.to_excel(writer, sheet_name="Comparativo", index=False)
    dados_grafico_excel.to_excel(writer, sheet_name="Dados do gráfico", index=False)
    tabela_linhas(cenario1["composicao"]).to_excel(writer, sheet_name="Importacao C1", index=False)
    tabela_linhas(cenario2["composicao"]).to_excel(writer, sheet_name="Importacao C2", index=False)
    tabela_linhas(cenario1["dre"]).to_excel(writer, sheet_name="DRE Cenario 1", index=False)
    tabela_linhas(cenario2["dre"]).to_excel(writer, sheet_name="DRE Cenario 2", index=False)
    grafico_excel = BarChart()
    grafico_excel.type = "col"
    grafico_excel.style = 10
    grafico_excel.title = "Resultado por entidade e cenário"
    grafico_excel.y_axis.title = "Resultado (R$)"
    grafico_excel.x_axis.title = "Cenário"
    dados_grafico = Reference(
        writer.sheets["Dados do gráfico"],
        min_col=2,
        max_col=4,
        min_row=1,
        max_row=3,
    )
    categorias_grafico = Reference(writer.sheets["Dados do gráfico"], min_col=1, min_row=2, max_row=3)
    grafico_excel.add_data(dados_grafico, titles_from_data=True)
    grafico_excel.set_categories(categorias_grafico)
    grafico_excel.height = 9
    grafico_excel.width = 22
    writer.sheets["Resumo"].add_chart(grafico_excel, "A5")

def tabela_pdf(linhas: list[list[str]], larguras: list[float]) -> Table:
    estilos = getSampleStyleSheet()
    estilo_celula = ParagraphStyle(
        "SynvittaCelulaPDF",
        parent=estilos["BodyText"],
        fontName="Helvetica",
        fontSize=7,
        leading=9,
    )
    estilo_cabecalho = ParagraphStyle(
        "SynvittaCabecalhoPDF",
        parent=estilo_celula,
        fontName="Helvetica-Bold",
        textColor=colors.white,
    )
    dados = [
        [
            Paragraph(
                html_escape(str(valor)),
                estilo_cabecalho if indice_linha == 0 else estilo_celula,
            )
            for valor in linha
        ]
        for indice_linha, linha in enumerate(linhas)
    ]
    tabela = Table(dados, colWidths=larguras, repeatRows=1, hAlign="LEFT")
    tabela.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#18364a")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#eef3f5")]),
        ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#c8d2d8")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    return tabela


def formatar_premissa_pdf(nome: str, valor: object) -> str:
    if isinstance(valor, (int, float)) and not isinstance(valor, bool):
        nome_normalizado = nome.casefold()
        if "r$/usd" in nome_normalizado:
            return f"{moeda(float(valor))} / USD"
        if any(chave in nome_normalizado for chave in ("parcela", "percentual", "alíquota", "seguro")):
            return f"{float(valor):.2%}".replace(".", ",")
        if "r$" in nome_normalizado:
            return moeda(float(valor))
        if "usd" in nome_normalizado:
            return f"USD {float(valor):,.2f}"
        return f"{valor:,.2f}".replace(",", "_").replace(".", ",").replace("_", ".")
    return str(valor) if valor not in (None, "") else "Não informado"


pdf_buffer = BytesIO()
estilos_pdf = getSampleStyleSheet()
estilo_nota_pdf = ParagraphStyle(
    "SynvittaNotaPDF",
    parent=estilos_pdf["BodyText"],
    fontSize=8,
    leading=10,
    textColor=colors.HexColor("#52606d"),
)
elementos_pdf = [
    Paragraph("Synvitta2 - Relatório de simulação", estilos_pdf["Title"]),
    Spacer(1, 6),
    Paragraph(
        "Relatório gerencial configurável. Alíquotas, bases e créditos devem ser validados para a operação.",
        estilo_nota_pdf,
    ),
    Spacer(1, 12),
    Paragraph("Resumo comparativo dos cenários", estilos_pdf["Heading2"]),
]
linhas_comparativo_pdf = [["Indicador", "Unidade", "Cenário 1", "Cenário 2"]]
linhas_comparativo_pdf.extend([
    [str(linha["Indicador"]), str(linha["Unidade"]), str(linha["Cenário 1"]), str(linha["Cenário 2"])]
    for _, linha in comparativo_apresentacao.iterrows()
])
elementos_pdf.append(tabela_pdf(linhas_comparativo_pdf, [245, 62, 210, 210]))
elementos_pdf.extend([
    Spacer(1, 12),
    Paragraph("Resultado por entidade e cenário", estilos_pdf["Heading2"]),
])

dados_grafico_pdf = [
    [cenario1["lucro_filial_retido"], cenario2["lucro_filial_retido"]],
    [cenario1["remessa_liquida"], cenario2["remessa_liquida"]],
    [cenario1["lucro_exportacao_liquido"], cenario2["lucro_exportacao_liquido"]],
]
grafico_pdf = VerticalBarChart()
grafico_pdf.x = 36
grafico_pdf.y = 34
grafico_pdf.width = 650
grafico_pdf.height = 170
grafico_pdf.data = dados_grafico_pdf
grafico_pdf.categoryAxis.categoryNames = ["Cenário 1", "Cenário 2"]
grafico_pdf.categoryAxis.labels.fontSize = 8
valores_grafico_pdf = [valor for serie in dados_grafico_pdf for valor in serie]
limite_inferior_pdf = min(0.0, min(valores_grafico_pdf))
limite_superior_pdf = max(1.0, max(valores_grafico_pdf))
grafico_pdf.valueAxis.valueMin = limite_inferior_pdf
grafico_pdf.valueAxis.valueMax = limite_superior_pdf * 1.15
grafico_pdf.valueAxis.valueStep = max(
    (grafico_pdf.valueAxis.valueMax - limite_inferior_pdf) / 5,
    1,
)
grafico_pdf.valueAxis.labels.fontSize = 7
cores_grafico_pdf = ["#4e9a72", "#d78a36", "#2878a0"]
for indice, cor in enumerate(cores_grafico_pdf):
    grafico_pdf.bars[indice].fillColor = colors.HexColor(cor)
desenho_grafico_pdf = Drawing(730, 255)
desenho_grafico_pdf.add(grafico_pdf)
legenda_pdf = Legend()
legenda_pdf.x = 430
legenda_pdf.y = 228
legenda_pdf.fontSize = 7
legenda_pdf.colorNamePairs = [
    (colors.HexColor("#4e9a72"), "Resultado retido filial/local"),
    (colors.HexColor("#d78a36"), "Remessa líquida à matriz"),
    (colors.HexColor("#2878a0"), "Lucro líquido exportação"),
]
desenho_grafico_pdf.add(legenda_pdf)
elementos_pdf.append(desenho_grafico_pdf)

linhas_premissas_pdf = [["Premissa", "Valor informado"]]
for _, premissa in premissas_exportacao.iterrows():
    linhas_premissas_pdf.append([
        str(premissa["Premissa"]),
        formatar_premissa_pdf(str(premissa["Premissa"]), premissa["Valor informado"]),
    ])
elementos_pdf.extend([
    Spacer(1, 8),
    Paragraph("Premissas utilizadas", estilos_pdf["Heading2"]),
    tabela_pdf(linhas_premissas_pdf, [370, 350]),
    Spacer(1, 10),
])

nomes_importacao_pdf = list(dict.fromkeys(
    [nome for nome, _ in cenario1["composicao"]]
    + [nome for nome, _ in cenario2["composicao"]]
))
valores_importacao_c1 = dict(cenario1["composicao"])
valores_importacao_c2 = dict(cenario2["composicao"])
linhas_importacao_pdf = [["Composição da importação", "Unidade", "Cenário 1", "Cenário 2"]]
linhas_importacao_pdf.extend([
    [
        nome,
        "R$",
        moeda(float(valores_importacao_c1[nome])) if nome in valores_importacao_c1 else "Não disponível",
        moeda(float(valores_importacao_c2[nome])) if nome in valores_importacao_c2 else "Não disponível",
    ]
    for nome in nomes_importacao_pdf
])
elementos_pdf.extend([
    Paragraph("Composição da importação", estilos_pdf["Heading2"]),
    tabela_pdf(linhas_importacao_pdf, [300, 55, 180, 180]),
    Spacer(1, 10),
])

nomes_dre_pdf = list(dict.fromkeys(
    [nome for nome, _ in cenario1["dre"]] + [nome for nome, _ in cenario2["dre"]]
))
valores_dre_c1 = dict(cenario1["dre"])
valores_dre_c2 = dict(cenario2["dre"])
linhas_dre_pdf = [["DRE gerencial Brasil", "Cenário 1", "Cenário 2"]]
linhas_dre_pdf.extend([
    [
        nome,
        moeda(float(valores_dre_c1[nome])) if nome in valores_dre_c1 else "Não disponível",
        moeda(float(valores_dre_c2[nome])) if nome in valores_dre_c2 else "Não disponível",
    ]
    for nome in nomes_dre_pdf
])
elementos_pdf.extend([
    Paragraph("DRE gerencial Brasil", estilos_pdf["Heading2"]),
    tabela_pdf(linhas_dre_pdf, [370, 170, 170]),
])

documento_pdf = SimpleDocTemplate(
    pdf_buffer,
    pagesize=landscape(A4),
    rightMargin=32,
    leftMargin=32,
    topMargin=28,
    bottomMargin=28,
    title="Synvitta2 - Relatório de simulação",
    author="Synvitta2",
)
documento_pdf.build(elementos_pdf)
arquivo_pdf = pdf_buffer.getvalue()

# Relatórios HTML em português e inglês, gravados junto a este script.
traducao_indicadores = {
    "Preço FOB matriz": "Parent company FOB price",
    "FOB total": "Total FOB",
    "Kits vendidos": "Kits sold",
    "Preço bruto de venda Brasil": "Brazil gross selling price",
    "Fator de Opex local": "Local operating expense factor",
    "Valor aduaneiro": "Customs value",
    "Desembolso total da importação": "Total import outlay",
    "Créditos tributários estimados": "Estimated tax credits",
    "Custo líquido de aquisição do estoque": "Net inventory acquisition cost",
    "Custo de aquisição por kit": "Acquisition cost per kit",
    "CMV do período": "Cost of goods sold for the period",
    "Receita líquida Brasil": "Brazil net revenue",
    "Lucro líquido Brasil": "Brazil net profit",
    "Markup (preço bruto / custo de aquisição)": "Markup (gross price / acquisition cost)",
    "IRPJ + CSLL calculados": "Calculated IRPJ + CSLL",
    "Alíquota efetiva IRPJ + CSLL": "Effective IRPJ + CSLL rate",
    "Margem líquida Brasil / receita líquida": "Brazil net margin / net revenue",
    "Parcela atribuída à matriz": "Share allocated to parent company",
    "Parcela atribuída à filial/local": "Share allocated to branch/local company",
    "Resultado da matriz no Brasil antes da remessa": "Brazil parent company profit before remittance",
    "Resultado retido na filial/local": "Profit retained by branch/local company",
    "Retenção sobre dividendos": "Dividend withholding tax",
    "Custo cambial da remessa": "Foreign exchange cost of remittance",
    "Remessa líquida à matriz": "Net remittance to parent company",
    "Lucro líquido da exportação da matriz": "Parent company net export profit",
    "Margem líquida exportação / FOB convertido": "Net export margin / converted FOB",
    "Lucro total da matriz (exportação + remessa)": "Total parent company profit (exports + remittance)",
    "Lucro global consolidado": "Consolidated global profit",
    "Lucro global consolidado por kit": "Consolidated global profit per kit",
}
traducao_premissas = {
    "NCM": "HS code (NCM)",
    "País de origem": "Country of origin",
    "Local de origem / embarque": "Origin / shipping location",
    "UF de destino": "Destination state",
    "Incoterm negociado": "Agreed Incoterm",
    "Regime tributário": "Tax regime",
    "Registro / licença sanitária": "Health registration / license",
    "Kits importados": "Imported kits",
    "Kits vendidos": "Kits sold",
    "Câmbio R$/USD": "Exchange rate BRL/USD",
    "FOB base USD/kit": "Base FOB USD/kit",
    "FOB cenário 2 USD/kit": "Scenario 2 FOB USD/kit",
    "Kits vendidos cenário 2": "Kits sold in scenario 2",
    "Preço venda Brasil cenário 2 R$/kit": "Scenario 2 Brazil selling price BRL/kit",
    "Fator Opex local cenário 2": "Scenario 2 local operating expense factor",
    "IRPJ comercial sobre faturamento (%)": "Commercial IRPJ on revenue (%)",
    "CSLL comercial sobre faturamento (%)": "Commercial CSLL on revenue (%)",
    "Base presumida do adicional IRPJ (%)": "Presumed base for additional IRPJ (%)",
    "Alíquota adicional IRPJ (%)": "Additional IRPJ rate (%)",
    "Limite mensal adicional IRPJ (R$)": "Monthly additional IRPJ threshold (BRL)",
    "Modo de composição da importação": "Import cost composition mode",
    "Tributos e despesas aduaneiras consolidados R$": "Consolidated import taxes and customs expenses (BRL)",
    "Modo de composição dos tributos sobre vendas": "Sales tax composition mode",
    "Alíquota efetiva sobre vendas": "Effective sales tax rate",
    "Modo de composição do Opex": "Operating expense composition mode",
    "Opex consolidado mensal R$": "Consolidated monthly operating expenses (BRL)",
    "Parcela matriz cenário 1": "Parent company share, scenario 1",
    "Parcela filial/local cenário 1": "Branch/local share, scenario 1",
    "Parcela matriz cenário 2": "Parent company share, scenario 2",
    "Parcela filial/local cenário 2": "Branch/local share, scenario 2",
    "Frete internacional USD": "International freight (USD)",
    "Seguro percentual": "Insurance rate",
    "II percentual": "Import duty rate",
    "IPI percentual": "IPI rate",
    "PIS-importação percentual": "Import PIS rate",
    "Cofins-importação percentual": "Import Cofins rate",
    "CBS-importação percentual": "Import CBS rate",
    "IBS-importação percentual": "Import IBS rate",
    "Base CBS/IBS múltiplo do VA": "CBS/IBS base as multiple of customs value",
    "ICMS-importação percentual": "Import ICMS rate",
    "AFRMM percentual": "AFRMM rate",
    "Período da DRE em meses": "Income statement period (months)",
    "Opex mensal (R$)": "Monthly operating expenses (BRL)",
    "Alíquota IR/CSLL sobre lucro (outros regimes)": "IR/CSLL rate on profit (other regimes)",
    "Alíquota federal EUA": "U.S. federal tax rate",
    "Alíquota estadual Flórida": "Florida state tax rate",
}
traducao_importacao = {
    "Valor aduaneiro": "Customs value",
    "II": "Import duty (II)",
    "IPI-importação": "Import IPI",
    "PIS-importação": "Import PIS",
    "Cofins-importação": "Import Cofins",
    "CBS/IBS-importação estimados": "Estimated import CBS/IBS",
    "ICMS-importação": "Import ICMS",
    "AFRMM": "Merchant Marine Tax (AFRMM)",
    "Antidumping / medidas compensatórias": "Anti-dumping / countervailing duties",
    "Tributos e despesas aduaneiras consolidados": "Consolidated import taxes and customs expenses",
    "Frete interno": "Domestic freight",
    "Créditos tributários estimados": "Estimated tax credits",
    "Custo de aquisição do estoque": "Inventory acquisition cost",
    "Frete internacional": "International freight",
    "Seguro internacional": "International insurance",
    "Despacho aduaneiro": "Customs clearance",
    "Armazenagem": "Warehousing",
    "Capatazia": "Cargo handling",
    "Taxa Siscomex": "Siscomex fee",
    "Outras despesas de importação": "Other import expenses",
}
traducao_dre = {
    "Receita bruta": "Gross revenue",
    "Devoluções, abatimentos e descontos": "Returns, allowances, and discounts",
    "Tributos sobre vendas": "Sales taxes",
    "Receita líquida": "Net revenue",
    "Custo das mercadorias vendidas (CMV)": "Cost of goods sold (COGS)",
    "Operação / armazenagem variável": "Variable operations / warehousing",
    "Opex fixo do período": "Fixed operating expenses for the period",
    "Lucro operacional": "Operating profit",
    "Juros e despesas financeiras": "Interest and financial expenses",
    "Resultado antes de IR/CSLL estimados": "Profit before estimated IR/CSLL",
    "IRPJ comercial sobre faturamento": "Commercial IRPJ on revenue",
    "Adicional de IRPJ": "Additional IRPJ",
    "CSLL comercial sobre faturamento": "Commercial CSLL on revenue",
    "IR/CSLL estimados": "Estimated IR/CSLL",
    "Lucro líquido Brasil": "Brazil net profit",
}
traducao_valores = {
    "Não disponível": "Not available",
    "Não informado": "Not provided",
    "Detalhado": "Detailed",
    "Consolidado": "Consolidated",
    "Lucro Presumido": "Presumed-profit regime",
    "Lucro Real": "Actual-profit regime",
    "Simples Nacional": "Simplified National Regime",
    "Estados Unidos": "United States",
    "Estados Unidos da América": "United States",
    "Brasil": "Brazil",
}

def formatar_valor_html_en(valor: object, unidade: str) -> str:
    if pd.isna(valor):
        return "Not available"
    if unidade == "%":
        return f"{float(valor):.2f}%"
    if unidade == "USD":
        return f"USD {float(valor):,.2f}"
    if unidade == "USD/kit":
        return f"USD {float(valor):,.2f}/kit"
    if unidade == "R$/kit":
        return f"BRL {float(valor):,.2f}/kit"
    if unidade == "kits":
        return f"{int(valor):,}"
    if unidade == "x":
        return f"{float(valor):.2f}x"
    return f"BRL {float(valor):,.2f}"


comparativo_html_en = comparativo.copy()
comparativo_html_en["Indicador"] = comparativo_html_en["Indicador"].replace(traducao_indicadores)
comparativo_html_en["Unidade"] = comparativo_html_en["Unidade"].replace({"R$": "BRL", "R$/kit": "BRL/kit"})
comparativo_html_en["Cenário 1"] = [
    formatar_valor_html_en(valor, unidade)
    for valor, unidade in zip(comparativo["Cenário 1"], comparativo["Unidade"])
]
comparativo_html_en["Cenário 2"] = [
    formatar_valor_html_en(valor, unidade)
    for valor, unidade in zip(comparativo["Cenário 2"], comparativo["Unidade"])
]
comparativo_html_en = comparativo_html_en.rename(columns={
    "Indicador": "Metric", "Unidade": "Unit", "Cenário 1": "Scenario 1", "Cenário 2": "Scenario 2"
})

premissas_html_pt = premissas_exportacao.copy()
premissas_html_pt["Valor informado"] = premissas_html_pt.apply(
    lambda linha: formatar_premissa_pdf(str(linha["Premissa"]), linha["Valor informado"]), axis=1
)
premissas_html_en = premissas_html_pt.rename(columns={
    "Premissa": "Assumption", "Valor informado": "Value"
}).copy()
premissas_html_en["Assumption"] = premissas_html_en["Assumption"].replace(traducao_premissas)
premissas_html_en["Value"] = premissas_html_en["Value"].replace(traducao_valores)

def tabela_composicao_html(cenario: dict[str, object], mapa: dict[str, str], ingles: bool) -> pd.DataFrame:
    composicao = pd.DataFrame(cenario["composicao"], columns=["Item", "Valor (R$)"])
    if ingles:
        composicao["Item"] = composicao["Item"].replace(mapa)
        composicao["Valor (R$)"] = composicao["Valor (R$)"].map(lambda valor: f"BRL {float(valor):,.2f}")
        return composicao.rename(columns={"Item": "Import item", "Valor (R$)": "Amount (BRL)"})
    composicao["Valor (R$)"] = composicao["Valor (R$)"].map(moeda)
    return composicao


def tabela_dre_html(ingles: bool) -> pd.DataFrame:
    valores_c1 = dict(cenario1["dre"])
    valores_c2 = dict(cenario2["dre"])
    nomes = list(dict.fromkeys([*valores_c1, *valores_c2]))
    linhas = [
        {
            "Conta": (traducao_dre.get(nome, nome) if ingles else nome),
            "Cenário 1": (
                f"BRL {float(valores_c1[nome]):,.2f}" if ingles else moeda(float(valores_c1[nome]))
            ) if nome in valores_c1 else ("Not available" if ingles else "Não disponível"),
            "Cenário 2": (
                f"BRL {float(valores_c2[nome]):,.2f}" if ingles else moeda(float(valores_c2[nome]))
            ) if nome in valores_c2 else ("Not available" if ingles else "Não disponível"),
        }
        for nome in nomes
    ]
    tabela = pd.DataFrame(linhas)
    if ingles:
        tabela = tabela.rename(columns={"Conta": "Account", "Cenário 1": "Scenario 1", "Cenário 2": "Scenario 2"})
    return tabela


def grafico_relatorio_html(ingles: bool) -> go.Figure:
    figura = go.Figure()
    series = [
        ("Resultado retido na filial/local", "Profit retained by branch/local company", "lucro_filial_retido", "#4e9a72"),
        ("Remessa líquida à matriz", "Net remittance to parent company", "remessa_liquida", "#d78a36"),
        ("Lucro líquido da exportação da matriz", "Parent company net export profit", "lucro_exportacao_liquido", "#2878a0"),
        ("Lucro global consolidado", "Consolidated global profit", "lucro_global", "#18364a"),
    ]
    for nome_pt, nome_en, chave, cor in series:
        figura.add_trace(go.Bar(
            name=nome_en if ingles else nome_pt,
            x=["Scenario 1", "Scenario 2"] if ingles else ["Cenário 1", "Cenário 2"],
            y=[float(cenario1[chave]), float(cenario2[chave])],
            marker_color=cor,
            hovertemplate="<b>%{x}</b><br>%{fullData.name}: BRL %{y:,.2f}<extra></extra>" if ingles
            else "<b>%{x}</b><br>%{fullData.name}: R$ %{y:,.2f}<extra></extra>",
        ))
    figura.update_layout(
        template="plotly_white", barmode="group", height=440,
        title="Profit by entity and scenario" if ingles else "Resultado por entidade e cenário",
        xaxis_title="Scenario" if ingles else "Cenário",
        yaxis_title="Result (BRL)" if ingles else "Resultado (R$)",
        font={"family": "Aptos, Segoe UI, sans-serif", "size": 11, "color": "#203040"},
        legend={"orientation": "h", "yanchor": "top", "y": -0.25, "xanchor": "center", "x": 0.5},
        margin={"l": 50, "r": 30, "t": 55, "b": 110},
    )
    figura.update_yaxes(tickprefix="BRL " if ingles else "R$ ", tickformat="~s", rangemode="tozero", gridcolor="#e5ebef")
    return figura


def montar_documento_html(ingles: bool) -> str:
    if ingles:
        titulo = "Synvitta2 - Detailed Simulation Report"
        aviso = "Management estimate only. Validate tax rates, customs bases, and recoverable credits with qualified professionals."
        secao_comparativo = "Scenario comparison"
        secao_resultado = "Profit by entity and scenario"
        secao_premissas = "Assumptions"
        secao_importacao = "Import composition"
        secao_dre = "Brazil management income statement"
        comparativo_html = comparativo_html_en.to_html(index=False, border=0, classes="report-table", escape=True)
        premissas_html = premissas_html_en.to_html(index=False, border=0, classes="report-table", escape=True)
        importacao_html = pd.merge(
            tabela_composicao_html(cenario1, traducao_importacao, True),
            tabela_composicao_html(cenario2, traducao_importacao, True),
            on="Import item", how="outer", suffixes=(" - Scenario 1", " - Scenario 2"),
        ).fillna("Not available")
        importacao_html = importacao_html.rename(columns={
            "Amount (BRL) - Scenario 1": "Scenario 1 (BRL)",
            "Amount (BRL) - Scenario 2": "Scenario 2 (BRL)",
        }).to_html(index=False, border=0, classes="report-table", escape=True)
        dre_html = tabela_dre_html(True).to_html(index=False, border=0, classes="report-table", escape=True)
        lang = "en"
    else:
        titulo = "Synvitta2 - Relatório de simulação detalhada"
        aviso = "Estimativa gerencial. Valide alíquotas, bases aduaneiras e créditos recuperáveis com profissionais habilitados."
        secao_comparativo = "Comparação dos cenários"
        secao_resultado = "Resultado por entidade e cenário"
        secao_premissas = "Premissas utilizadas"
        secao_importacao = "Composição da importação"
        secao_dre = "DRE gerencial Brasil"
        comparativo_html = comparativo_apresentacao.to_html(index=False, border=0, classes="report-table", escape=True)
        premissas_html = premissas_html_pt.to_html(index=False, border=0, classes="report-table", escape=True)
        importacao_html = pd.merge(
            tabela_composicao_html(cenario1, traducao_importacao, False),
            tabela_composicao_html(cenario2, traducao_importacao, False),
            on="Item", how="outer", suffixes=(" - Cenário 1", " - Cenário 2"),
        ).fillna("Não disponível")
        importacao_html = importacao_html.rename(columns={
            "Valor (R$) - Cenário 1": "Cenário 1 (R$)",
            "Valor (R$) - Cenário 2": "Cenário 2 (R$)",
        }).to_html(index=False, border=0, classes="report-table", escape=True)
        dre_html = tabela_dre_html(False).to_html(index=False, border=0, classes="report-table", escape=True)
        lang = "pt-BR"
    grafico_html = grafico_relatorio_html(ingles).to_html(full_html=False, include_plotlyjs="cdn")
    return f"""<!doctype html>
<html lang="{lang}"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{html_escape(titulo)}</title><style>
body{{font-family:Segoe UI,Arial,sans-serif;color:#203040;background:#f5f7f8;margin:0;padding:24px}}
main{{max-width:1500px;margin:auto}}h1,h2{{color:#18364a}}h1{{font-size:26px}}h2{{font-size:19px;margin-top:30px}}
.note{{color:#52606d;font-size:12px}}.report-table{{border-collapse:collapse;width:100%;background:#fff;font-size:12px}}
.report-table th{{background:#18364a;color:#fff;text-align:left}}.report-table th,.report-table td{{padding:8px;border:1px solid #d9e1e8;vertical-align:top}}
.report-table tbody tr:nth-child(even){{background:#f0f5f7}}.scroll{{overflow-x:auto}}.chart{{background:#fff;padding:8px;border:1px solid #d9e1e8}}
@media print{{body{{background:#fff;padding:0}}}}
</style></head><body><main><h1>{html_escape(titulo)}</h1><p class="note">{html_escape(aviso)}</p>
<h2>{secao_comparativo}</h2><div class="scroll">{comparativo_html}</div>
<h2>{secao_resultado}</h2><div class="chart">{grafico_html}</div>
<h2>{secao_premissas}</h2><div class="scroll">{premissas_html}</div>
<h2>{secao_importacao}</h2><div class="scroll">{importacao_html}</div>
<h2>{secao_dre}</h2><div class="scroll">{dre_html}</div>
</main></body></html>"""

grupos_campos_html = {
    "produto": ("Produto, volume e câmbio", "Product, volume, and exchange"),
    "frete": ("Embalagem e frete", "Packaging and freight"),
    "importacao": ("Tributos e despesas de importação", "Import taxes and expenses"),
    "vendas": ("Receita e tributos sobre vendas", "Revenue and sales taxes"),
    "opex": ("Opex e despesas financeiras", "Operating expenses and finance"),
    "tributos": ("Tributos sobre lucro e remessas", "Profit taxes and remittances"),
    "cenario2": ("Cenário 2", "Scenario 2"),
}
rotulos_campos_html = {
    "ncm_codigo": ("NCM do produto", "Product HS code (NCM)", "produto", "text"),
    "pais_origem": ("País de origem aduaneira", "Country of customs origin", "produto", "text"),
    "local_origem": ("Local de origem / embarque", "Origin / shipping location", "produto", "text"),
    "uf_destino": ("UF de destino", "Destination state", "produto", "select"),
    "incoterm": ("Incoterm negociado", "Agreed Incoterm", "produto", "select"),
    "regime_tributario": ("Regime tributário", "Tax regime", "produto", "select"),
    "registro_sanitario": ("Registro / licença sanitária", "Health registration / license", "produto", "text"),
    "quantidade": ("Kits importados", "Imported kits", "produto", "number"),
    "quantidade_vendida": ("Kits vendidos no período", "Kits sold in the period", "produto", "number"),
    "cambio": ("Câmbio (R$/USD)", "Exchange rate (BRL/USD)", "produto", "number"),
    "preco_fob_base": ("Preço FOB da matriz (USD/kit)", "Parent company FOB price (USD/kit)", "produto", "number"),
    "custo_fabricacao_usd": ("Custo de fabricação da matriz (USD/kit)", "Parent company manufacturing cost (USD/kit)", "produto", "number"),
    "receita_por_kit": ("Preço bruto de venda Brasil (R$/kit)", "Brazil gross selling price (BRL/kit)", "produto", "number"),
    "meses_operacao": ("Período da DRE (meses)", "Income statement period (months)", "produto", "number"),
    "kits_por_volume": ("Kits por caixa/volume", "Kits per carton/shipping unit", "frete", "number"),
    "comprimento": ("Comprimento da caixa (cm)", "Carton length (cm)", "frete", "number"),
    "largura": ("Largura da caixa (cm)", "Carton width (cm)", "frete", "number"),
    "altura": ("Altura da caixa (cm)", "Carton height (cm)", "frete", "number"),
    "peso_bruto_total": ("Peso bruto total (kg)", "Total gross weight (kg)", "frete", "number"),
    "divisor_volumetrico": ("Divisor volumétrico (cm³/kg)", "Volumetric divisor (cm³/kg)", "frete", "number"),
    "modal": ("Modal internacional", "International shipping mode", "frete", "select"),
    "calculo_frete": ("Cálculo do frete", "Freight calculation", "frete", "select"),
    "frete_usd": ("Frete total informado (USD)", "Entered total freight (USD)", "frete", "number"),
    "tarifa_wm": ("Tarifa marítima por W/M (USD)", "Ocean rate per W/M (USD)", "frete", "number"),
    "tarifa_frete_kg": ("Tarifa por kg taxável (USD)", "Rate per chargeable kg (USD)", "frete", "number"),
    "tarifa_m3": ("Tarifa por m³ (USD)", "Rate per m³ (USD)", "frete", "number"),
    "seguro_pct": ("Seguro (% sobre FOB + frete)", "Insurance (% of FOB + freight)", "frete", "number"),
    "ajustes_aduaneiros_brl": ("Ajustes ao valor aduaneiro (R$)", "Customs value adjustments (BRL)", "frete", "number"),
    "frete_interno_brl": ("Frete interno (R$)", "Domestic freight (BRL)", "frete", "number"),
    "modo_custos_importacao": ("Composição dos custos aduaneiros", "Import cost composition", "importacao", "select"),
    "aliq_ii": ("II (%)", "Import duty (II) (%)", "importacao", "number"),
    "aliq_ipi": ("IPI-importação (%)", "Import IPI (%)", "importacao", "number"),
    "aliq_pis": ("PIS-importação (%)", "Import PIS (%)", "importacao", "number"),
    "aliq_cofins": ("Cofins-importação (%)", "Import Cofins (%)", "importacao", "number"),
    "aliq_cbs": ("CBS-importação (%)", "Import CBS (%)", "importacao", "number"),
    "aliq_ibs": ("IBS-importação (%)", "Import IBS (%)", "importacao", "number"),
    "multiplo_base_cbs_ibs": ("Base CBS/IBS (múltiplo do VA)", "CBS/IBS base (multiple of customs value)", "importacao", "number"),
    "aliq_icms": ("ICMS-importação (%)", "Import ICMS (%)", "importacao", "number"),
    "aliq_afrmm": ("AFRMM (% sobre frete marítimo)", "AFRMM (% of ocean freight)", "importacao", "number"),
    "antidumping_brl": ("Antidumping / medidas compensatórias (R$)", "Anti-dumping / countervailing duties (BRL)", "importacao", "number"),
    "despesas_na_base_icms": ("Despesas incluídas na base ICMS (R$)", "Expenses included in ICMS base (BRL)", "importacao", "number"),
    "custo_armazenagem": ("Armazenagem (R$)", "Warehousing (BRL)", "importacao", "number"),
    "custo_capatazia": ("Capatazia / terminal (R$)", "Cargo handling / terminal (BRL)", "importacao", "number"),
    "custo_despachante": ("Despachante aduaneiro (R$)", "Customs broker (BRL)", "importacao", "number"),
    "taxa_siscomex": ("Taxa Siscomex (R$)", "Siscomex fee (BRL)", "importacao", "number"),
    "taxas_terminal": ("Taxas portuárias / aeroportuárias (R$)", "Port / airport fees (BRL)", "importacao", "number"),
    "honorarios_agente_carga": ("Honorários / agente de carga (R$)", "Forwarder / freight agent fees (BRL)", "importacao", "number"),
    "licencas_inspecao": ("Licenças, análise e inspeção (R$)", "Licenses, testing, and inspection (BRL)", "importacao", "number"),
    "outras_despesas_importacao": ("Outras despesas de importação (R$)", "Other import expenses (BRL)", "importacao", "number"),
    "custo_importacao_consolidado_brl": ("Tributos/despesas consolidados (R$)", "Consolidated import taxes/expenses (BRL)", "importacao", "number"),
    "credita_ipi": ("IPI recuperável", "Recoverable IPI", "importacao", "checkbox"),
    "credita_pis": ("PIS-importação recuperável", "Recoverable import PIS", "importacao", "checkbox"),
    "credita_cofins": ("Cofins-importação recuperável", "Recoverable import Cofins", "importacao", "checkbox"),
    "credita_cbs_ibs": ("CBS/IBS-importação recuperáveis", "Recoverable import CBS/IBS", "importacao", "checkbox"),
    "credita_icms": ("ICMS recuperável", "Recoverable ICMS", "importacao", "checkbox"),
    "devolucoes_descontos": ("Devoluções, abatimentos e descontos (R$)", "Returns, allowances, and discounts (BRL)", "vendas", "number"),
    "modo_tributos_venda": ("Composição dos tributos sobre vendas", "Sales tax composition", "vendas", "select"),
    "aliq_icms_venda": ("ICMS efetivo sobre vendas (%)", "Effective sales ICMS (%)", "vendas", "number"),
    "aliq_pis_venda": ("PIS efetivo sobre vendas (%)", "Effective sales PIS (%)", "vendas", "number"),
    "aliq_cofins_venda": ("Cofins efetiva sobre vendas (%)", "Effective sales Cofins (%)", "vendas", "number"),
    "aliq_outros_venda": ("Outros tributos sobre vendas (%)", "Other sales taxes (%)", "vendas", "number"),
    "aliq_venda_consolidada": ("Alíquota consolidada sobre vendas (%)", "Consolidated sales tax rate (%)", "vendas", "number"),
    "operador_pct": ("Operação / armazenagem variável (% receita líquida)", "Variable operations / warehousing (% net revenue)", "vendas", "number"),
    "modo_opex": ("Composição do Opex", "Operating expense composition", "opex", "select"),
    "opex_pessoal": ("Pessoal e encargos / mês (R$)", "Personnel and payroll / month (BRL)", "opex", "number"),
    "opex_aluguel": ("Aluguel e condomínio / mês (R$)", "Rent and condominium / month (BRL)", "opex", "number"),
    "opex_utilidades": ("Utilidades e telecomunicações / mês (R$)", "Utilities and telecom / month (BRL)", "opex", "number"),
    "opex_servicos_profissionais": ("Serviços profissionais / mês (R$)", "Professional services / month (BRL)", "opex", "number"),
    "opex_comercial_marketing": ("Comercial e marketing / mês (R$)", "Sales and marketing / month (BRL)", "opex", "number"),
    "opex_sistemas": ("Sistemas e comunicações / mês (R$)", "Systems and communications / month (BRL)", "opex", "number"),
    "opex_seguros": ("Seguros / mês (R$)", "Insurance / month (BRL)", "opex", "number"),
    "opex_depreciacao": ("Depreciação e amortização / mês (R$)", "Depreciation and amortization / month (BRL)", "opex", "number"),
    "opex_administrativo": ("Despesas administrativas / mês (R$)", "Administrative expenses / month (BRL)", "opex", "number"),
    "opex_outros": ("Outros Opex / mês (R$)", "Other operating expenses / month (BRL)", "opex", "number"),
    "opex_consolidado_mensal": ("Opex consolidado / mês (R$)", "Consolidated operating expenses / month (BRL)", "opex", "number"),
    "juros_brl": ("Juros e despesas financeiras (R$)", "Interest and financial expenses (BRL)", "opex", "number"),
    "aliq_irpj_faturamento": ("IRPJ efetivo sobre faturamento (%)", "Effective IRPJ on revenue (%)", "tributos", "number"),
    "aliq_csll_faturamento": ("CSLL efetiva sobre faturamento (%)", "Effective CSLL on revenue (%)", "tributos", "number"),
    "base_presumida_irpj": ("Base presumida para adicional IRPJ (%)", "Presumed base for additional IRPJ (%)", "tributos", "number"),
    "aliq_adicional_irpj": ("Adicional de IRPJ (%)", "Additional IRPJ rate (%)", "tributos", "number"),
    "limite_adicional_irpj_mensal": ("Limite mensal adicional IRPJ (R$)", "Monthly additional IRPJ threshold (BRL)", "tributos", "number"),
    "aliq_ir_csll": ("IR/CSLL sobre lucro (outros regimes) (%)", "IR/CSLL on profit (other regimes) (%)", "tributos", "number"),
    "aliq_federal_eua": ("Imposto federal EUA (%)", "U.S. federal tax (%)", "tributos", "number"),
    "aliq_fl": ("Imposto estadual Flórida (%)", "Florida state tax (%)", "tributos", "number"),
    "rateio_fl": ("Parcela atribuída à Flórida (%)", "Profit allocated to Florida (%)", "tributos", "number"),
    "opex_matriz_usd": ("Opex da matriz atribuído à exportação (USD)", "Parent company operating expenses assigned to exports (USD)", "tributos", "number"),
    "participacao_matriz": ("Parcela da matriz no lucro Brasil (%)", "Parent company share of Brazil profit (%)", "tributos", "number"),
    "retencao_dividendos": ("Retenção sobre dividendos (%)", "Dividend withholding tax (%)", "tributos", "number"),
    "custo_remessa": ("Custo cambial da remessa (%)", "Remittance foreign exchange cost (%)", "tributos", "number"),
    "preco_fob_c2": ("Preço FOB alternativo da matriz (USD/kit)", "Alternative parent company FOB price (USD/kit)", "cenario2", "number"),
    "quantidade_vendida_c2": ("Kits vendidos no cenário 2", "Kits sold in scenario 2", "cenario2", "number"),
    "receita_por_kit_c2": ("Preço de venda Brasil no cenário 2 (R$/kit)", "Brazil selling price in scenario 2 (BRL/kit)", "cenario2", "number"),
    "fator_opex_c2": ("Fator do Opex local no cenário 2 (x)", "Scenario 2 local operating expense factor (x)", "cenario2", "number"),
    "participacao_matriz_c2": ("Parcela da matriz no cenário 2 (%)", "Parent company share in scenario 2 (%)", "cenario2", "number"),
}
percentuais_widget_html = {
    "seguro_pct", "aliq_ii", "aliq_ipi", "aliq_pis", "aliq_cofins", "aliq_cbs", "aliq_ibs",
    "aliq_icms", "aliq_afrmm", "aliq_icms_venda", "aliq_pis_venda", "aliq_cofins_venda",
    "aliq_outros_venda", "aliq_venda_consolidada", "operador_pct", "aliq_irpj_faturamento",
    "aliq_csll_faturamento", "base_presumida_irpj", "aliq_adicional_irpj", "aliq_ir_csll",
    "aliq_federal_eua", "aliq_fl", "rateio_fl", "participacao_matriz", "retencao_dividendos",
    "custo_remessa", "participacao_matriz_c2",
}
valores_iniciais_ocultos = {
    "custo_armazenagem": 0.0, "custo_capatazia": 0.0, "custo_despachante": 0.0,
    "taxa_siscomex": 0.0, "taxas_terminal": 0.0, "honorarios_agente_carga": 0.0,
    "licencas_inspecao": 0.0, "outras_despesas_importacao": 0.0,
    "opex_pessoal": 90000.0, "opex_aluguel": 25000.0, "opex_utilidades": 10000.0,
    "opex_servicos_profissionais": 15000.0, "opex_comercial_marketing": 30000.0,
    "opex_sistemas": 5000.0, "opex_seguros": 5000.0, "opex_depreciacao": 10000.0,
    "opex_administrativo": 5000.0, "opex_outros": 5000.0, "opex_consolidado_mensal": 200000.0,
    "tarifa_wm": 0.0, "tarifa_frete_kg": 0.0, "tarifa_m3": 0.0,
}
valores_percentuais_iniciais = {
    "aliq_ii": 0.0, "aliq_ipi": 0.0, "aliq_pis": 0.0, "aliq_cofins": 0.0,
    "aliq_cbs": 0.0, "aliq_ibs": 0.0, "aliq_icms": 0.0, "aliq_afrmm": 0.0,
    "aliq_icms_venda": 0.0, "aliq_pis_venda": 0.0, "aliq_cofins_venda": 0.0,
    "aliq_outros_venda": 0.0, "aliq_venda_consolidada": 0.0,
    "aliq_irpj_faturamento": 1.2, "aliq_csll_faturamento": 1.08,
    "base_presumida_irpj": 8.0, "aliq_adicional_irpj": 10.0, "aliq_ir_csll": 32.0,
    "aliq_federal_eua": 21.0, "aliq_fl": 5.5, "rateio_fl": 100.0,
    "participacao_matriz": 75.0, "participacao_matriz_c2": 75.0,
    "retencao_dividendos": 10.0, "custo_remessa": 1.0, "seguro_pct": 0.5,
    "operador_pct": 5.0,
}
try:
    valores_salvos_html = json.loads(ARQUIVO_PADROES.read_text(encoding="utf-8"))
except (OSError, json.JSONDecodeError):
    valores_salvos_html = dict(PADROES_SALVOS)

campos_calculadora2 = []
for chave, (rotulo_pt, rotulo_en, grupo, tipo) in rotulos_campos_html.items():
    valor_inicial = valores_iniciais_ocultos.get(chave, valores_percentuais_iniciais.get(chave, 0.0))
    valor_execucao = locals().get(chave, valor_inicial)
    if chave in percentuais_widget_html and isinstance(valor_execucao, (int, float)):
        valor_execucao *= 100
    valor = valores_salvos_html.get(chave, st.session_state.get(chave, valor_execucao))
    opcoes = []
    if chave == "uf_destino":
        opcoes = [(item, item, item) for item in opcoes_uf]
    elif chave == "incoterm":
        opcoes = [(item, item, item) for item in opcoes_incoterm]
    elif chave == "regime_tributario":
        opcoes = [
            ("Não informado", "Não informado", "Not specified"),
            ("Lucro Real", "Lucro Real", "Actual-profit regime"),
            ("Lucro Presumido", "Lucro Presumido", "Presumed-profit regime"),
            ("Simples Nacional", "Simples Nacional", "Simplified National Regime"),
            ("Outro", "Outro", "Other"),
        ]
    elif chave == "modal":
        opcoes = [("Marítimo", "Marítimo", "Ocean freight"), ("Aéreo", "Aéreo", "Air freight"), ("Rodoviário", "Rodoviário", "Road freight"), ("Outro", "Outro", "Other")]
    elif chave in {"modo_custos_importacao", "modo_tributos_venda", "modo_opex"}:
        opcoes = [("Detalhado", "Detalhado", "Detailed"), ("Consolidado", "Consolidado", "Consolidated")]
    elif chave == "calculo_frete":
        opcoes = [
            ("Valor total informado", "Valor total informado", "Total amount entered"),
            ("Tarifa marítima por W/M", "Tarifa marítima por W/M", "Ocean rate per W/M"),
            ("Tarifa por kg taxável", "Tarifa por kg taxável", "Rate per chargeable kg"),
            ("Tarifa por m³", "Tarifa por m³", "Rate per cubic meter"),
        ]
    campos_calculadora2.append(field(
        chave,
        rotulo_pt,
        rotulo_en,
        valor,
        grupos_campos_html[grupo][0],
        grupos_campos_html[grupo][1],
        kind=tipo,
        options=opcoes,
        step="any",
    ))

relatorio_html_pt = build_calculator_html(
    model_id="synvitta2",
    language="pt",
    title="Synvitta2 - Simulação detalhada",
    fields=campos_calculadora2,
    calculation_js=synvitta2_calculation_js(),
)
relatorio_html_en = build_calculator_html(
    model_id="synvitta2",
    language="en",
    title="Synvitta2 - Detailed simulation",
    fields=campos_calculadora2,
    calculation_js=synvitta2_calculation_js(),
)
try:
    pasta_relatorios = Path(__file__).resolve().parent
    (pasta_relatorios / "synvitta2_relatorio.html").write_text(relatorio_html_pt, encoding="utf-8")
    (pasta_relatorios / "synvitta2_report.htm").write_text(relatorio_html_en, encoding="utf-8")
    status_relatorio = "Arquivos HTML/HTM atualizados na pasta do Synvitta2."
except OSError as erro_gravacao:
    status_relatorio = f"Não foi possível gravar os arquivos na pasta do app: {erro_gravacao}"

with st.container(horizontal=True):
    st.download_button(
        "Baixar resumo CSV",
        data=resumo_exportacao.to_csv(index=False).encode("utf-8-sig"),
        file_name="synvitta2_resumo.csv",
        mime="text/csv",
        icon=":material/download:",
    )
    st.download_button(
        "Baixar relatório Excel",
        data=arquivo_excel.getvalue(),
        file_name="synvitta2_relatorio.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        on_click="ignore",
        icon=":material/download:",
    )
    st.download_button(
        "Baixar relatório PDF",
        data=arquivo_pdf,
        file_name="synvitta2_relatorio.pdf",
        mime="application/pdf",
        on_click="ignore",
        icon=":material/download:",
    )
    st.download_button(
        "Baixar relatório HTML",
        data=relatorio_html_pt.encode("utf-8"),
        file_name="synvitta2_relatorio.html",
        mime="text/html",
        icon=":material/download:",
    )
    st.download_button(
        "Download English report",
        data=relatorio_html_en.encode("utf-8"),
        file_name="synvitta2_report.htm",
        mime="text/html",
        icon=":material/download:",
    )
st.caption(status_relatorio)