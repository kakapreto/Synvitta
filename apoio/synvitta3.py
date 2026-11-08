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
from standalone_html3 import build_calculator_html, field
from synvitta3_calc_js import synvitta3_calculation_js
from synvitta3_i18n import translate
from synvitta3_importacao import (
    CAMPOS_IMPORTACAO, FONTES_IMPORTACAO, NOTA_IMPORTACAO, NOTA_IMPORTACAO_EN,
    ROTULOS_ANTIGOS, completar_campos_importacao, valorar_lote,
)
from openpyxl.chart import BarChart, Reference
from openpyxl.styles import Font, PatternFill
from reportlab.graphics.charts.barcharts import VerticalBarChart
from reportlab.graphics.charts.legends import Legend
from reportlab.graphics.shapes import Drawing
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


CAMINHO_CONFIGURADO = os.environ.get("SYNVITTA3_DEFAULTS_PATH")
if CAMINHO_CONFIGURADO:
    ARQUIVO_PADROES = Path(CAMINHO_CONFIGURADO)
    ARQUIVO_PADROES_LEGADO = None
else:
    LOCAL_APP_DATA = os.environ.get("LOCALAPPDATA")
    if LOCAL_APP_DATA:
        RAIZ_PADROES = Path(LOCAL_APP_DATA)
    elif os.name == "nt":
        RAIZ_PADROES = Path.home() / "AppData" / "Local"
    else:
        RAIZ_PADROES = Path.home() / ".local" / "share"
    ARQUIVO_PADROES = RAIZ_PADROES / "Synvitta3" / "defaults.json"
    # Na primeira execução, reaproveita as premissas salvas pela versão 2.
    ARQUIVO_PADROES_LEGADO = RAIZ_PADROES / "Synvitta2" / "defaults.json"

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
    page_title=(
        "Synvitta3 - Detailed simulation"
        if st.session_state.get("idioma_interface", "pt") == "en"
        else "Synvitta3 - Simulação detalhada"
    ),
    page_icon="📦",
    layout="wide",
)

MOEDA_ATUAL = {"codigo": "USD", "simbolo": "US$", "fator": 1.0}
IDIOMA_ATUAL = st.session_state.get("idioma_interface", "pt")
TEMA_ATUAL = st.session_state.get("tema_interface", "dark")
EXIBINDO_ENTRADAS = True


def L(texto: object) -> str:
    texto = ROTULOS_ANTIGOS.get(str(texto), texto)
    texto_traduzido = translate(texto, IDIOMA_ATUAL)
    if EXIBINDO_ENTRADAS:
        return texto_traduzido
    protegido = texto_traduzido.replace("R$/USD", "\0")
    return protegido.replace("R$", MOEDA_ATUAL["simbolo"]).replace("\0", "R$/USD")


def definir_moeda(codigo: str, cambio_aduaneiro: float) -> None:
    if codigo == "USD":
        MOEDA_ATUAL.update(codigo="USD", simbolo="US$", fator=1 / max(cambio_aduaneiro, 0.01))
    else:
        MOEDA_ATUAL.update(codigo="BRL", simbolo="R$", fator=1.0)


def convertido(valor: float) -> float:
    return valor * MOEDA_ATUAL["fator"]


def moeda(valor: float) -> str:
    # Recebe valor já na moeda de exibição.
    texto = f"{valor:,.2f}"
    if MOEDA_ATUAL["codigo"] == "BRL":
        texto = texto.replace(",", "_").replace(".", ",").replace("_", ".")
    return f"{MOEDA_ATUAL['simbolo']} {texto}"


def moeda_resumida(valor: float) -> str:
    simbolo = MOEDA_ATUAL["simbolo"]
    if abs(valor) >= 1_000_000:
        texto = f"{simbolo} {valor / 1_000_000:.2f} mi"
    elif abs(valor) >= 10_000:
        texto = f"{simbolo} {valor / 1_000:.1f} mil"
    else:
        return moeda(valor)
    return texto.replace(".", ",") if MOEDA_ATUAL["codigo"] == "BRL" else texto.replace(" mil", "k").replace(" mi", "M")


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
    return st.number_input(
        L(rotulo),
        min_value=0.0,
        max_value=99.0,
        value=valor_padrao(chave, valor),
        step=0.1,
        key=chave,
        disabled=disabled,
    ) / 100


def campos_importacao_widgets(sufixo: str, grupo_alvo: str, desativado: bool = False) -> dict[str, object]:
    componentes = {}
    for chave, rotulo, rotulo_en, grupo, tipo, inicial in CAMPOS_IMPORTACAO:
        if grupo != grupo_alvo:
            continue
        rotulo = rotulo_en if IDIOMA_ATUAL == "en" else rotulo
        chave_widget = chave + sufixo
        if tipo == "checkbox":
            valor = st.checkbox(rotulo, value=valor_padrao(chave_widget, inicial), key=chave_widget, disabled=desativado)
        elif tipo == "select":
            valor = st.selectbox(rotulo, ["Percentual", "Valor informado"], index=indice_padrao(chave_widget, ["Percentual", "Valor informado"], 0), key=chave_widget, disabled=desativado, format_func=L)
        else:
            sem_apolice = chave == "seguro_total_usd" and componentes.get("modo_seguro") != "Valor informado"
            valor = st.number_input(rotulo, min_value=0.0, value=float(valor_padrao(chave_widget, inicial)), key=chave_widget, disabled=desativado or sem_apolice)
        componentes[chave] = valor
    if grupo_alvo == "frete" and not desativado and not componentes["valoracao_revisada"]:
        st.warning(L("Valoração pendente de revisão documental: parcelas na VA preservam a premissa anterior."))
    return componentes


def seletor_modo_composicao(rotulo: str, chave: str) -> str:
    with st.container(border=True):
        st.markdown(L(f"**{L(rotulo)}**"))
        modo = st.segmented_control(
            L("Modo de composição"),
            ["Detalhado", "Consolidado"],
            format_func=L,
            default=valor_padrao(chave, "Detalhado"),
            key=chave,
            label_visibility="collapsed",
            width="stretch",
        )
        st.caption(L(f"Modo ativo: {modo}"))
    return modo


def salvar_padroes() -> None:
    valores_salvos = dict(PADROES_SALVOS)
    valores_salvos.pop("idioma_interface", None)
    valores_salvos.pop("tema_interface", None)
    for chave in st.session_state:
        if (
            not isinstance(chave, str)
            or chave.startswith(("$$", "_synvitta3_"))
            or chave in {"idioma_interface", "tema_interface"}
        ):
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
        st.warning(L(f"Não foi possível salvar os padrões neste computador: {erro}"))
st.title(L("📦 Synvitta3 | Simulação detalhada"))
st.caption(L(
    "Modelo gerencial configurável. As alíquotas, bases tributárias e créditos "
    "devem ser confirmados para o NCM, origem, destino, regime e período da operação."
))
st.caption(L(
    "Premissas salvas automaticamente no perfil deste host, fora da pasta do app; "
    "atualizações do código não removem esses dados. Dispositivos conectados a este host "
    "compartilham os mesmos padrões."
))

with st.sidebar:
    st.header(L("Premissas da operação"))

    st.radio(
        L("Idioma"),
        ["pt", "en"],
        format_func=lambda idioma: "Português" if idioma == "pt" else "English",
        horizontal=True,
        key="idioma_interface",
    )
    st.radio(
        L("Tema"),
        ["dark", "light"],
        format_func=lambda tema: L("Escuro" if tema == "dark" else "Claro"),
        horizontal=True,
        key="tema_interface",
    )
    cores_tema = (
        {
            "base": "#ffffff",
            "secondary": "#f0f2f6",
            "text": "#31333f",
            "primary": "#007fa3",
        }
        if TEMA_ATUAL == "light"
        else {
            "base": "#070a13",
            "secondary": "#0d1322",
            "text": "#f1f5f9",
            "primary": "#00d2ff",
        }
    )
    st.html(f"""
    <style>
      :root {{
        color-scheme: {"light" if TEMA_ATUAL == "light" else "dark"};
        --background-color: {cores_tema["base"]};
        --secondary-background-color: {cores_tema["secondary"]};
        --text-color: {cores_tema["text"]};
        --primary-color: {cores_tema["primary"]};
      }}
      html, body, main, [data-testid="stAppViewContainer"],
      [data-testid="stMainBlockContainer"] {{
        color-scheme: {"light" if TEMA_ATUAL == "light" else "dark"};
        background-color: {cores_tema["base"]} !important;
        color: {cores_tema["text"]} !important;
      }}
      [data-testid="stSidebar"] > div:first-child,
      [data-testid="stHeader"] {{
        background-color: {cores_tema["secondary"]} !important;
        color: {cores_tema["text"]} !important;
      }}
      p, h1, h2, h3, h4, h5, h6, label, button,
      [data-testid="stExpander"] summary {{
        color: {cores_tema["text"]} !important;
        background-color: {cores_tema["secondary"]} !important;
      }}
      [data-testid="stExpander"],
      [data-testid="stExpander"] details {{
        background-color: {cores_tema["secondary"]} !important;
      }}
      button[data-variant="segmented_control"] {{
        background-color: {cores_tema["secondary"]} !important;
        color: {cores_tema["text"]} !important;
      }}
      button[data-variant="segmented_control"][data-selected="true"] {{
        background-color: {cores_tema["primary"]} !important;
      }}
      input, textarea, [data-baseweb="select"] > div {{
        background-color: {cores_tema["secondary"]} !important;
        color: {cores_tema["text"]} !important;
      }}
      [data-testid="stBaseButton-primary"] {{
        background-color: {cores_tema["primary"]} !important;
      }}
    </style>
    """)

    moeda_relatorio = st.segmented_control(
        L("Moeda do relatório"),
        ["USD", "BRL"],
        default=valor_padrao("moeda_relatorio", "USD"),
        key="moeda_relatorio",
        width="stretch",
        help=L("Todos os resultados, tabelas e relatórios são exibidos na moeda escolhida, "
        "convertidos pelo câmbio gerencial. Os campos de entrada em R$ permanecem em reais.",
        ),
    ) or "USD"
    with st.expander(L("1. Produto, volume e câmbio"), expanded=True):
        ncm_codigo = st.text_input(
            L("NCM do produto"), value=valor_padrao("ncm_codigo", "3822.19.90"),
            placeholder=L("Ex.: 0000.00.00"), key="ncm_codigo"
        )
        pais_origem = st.text_input(
            L("País de origem aduaneira (confirmar fabricação)"),
            value=valor_padrao("pais_origem", "Estados Unidos"),
            help=(
                L("Preenchido com base no local informado. Se o produto for fabricado ou "
                "originário de outro país, altere este campo; local de embarque não define sozinho a origem aduaneira.")
            ),
            key="pais_origem",
        )
        local_origem = st.text_input(
            L("Local de origem / embarque"),
            value=valor_padrao("local_origem", "Alachua, Florida"),
            key="local_origem",
        )
        opcoes_uf = ["Não informado", "AC", "AL", "AM", "AP", "BA", "CE", "DF", "ES", "GO", "MA", "MG", "MS", "MT", "PA", "PB", "PE", "PI", "PR", "RJ", "RN", "RO", "RR", "RS", "SC", "SE", "SP", "TO"]
        uf_destino = st.selectbox(
            L("UF de destino / estabelecimento importador"),
            opcoes_uf,
            index=indice_padrao("uf_destino", opcoes_uf, 26),
            key="uf_destino",
            format_func=L,
        )
        opcoes_incoterm = ["FOB", "EXW", "FCA", "FAS", "CFR", "CIF", "CPT", "CIP", "DAP", "DPU", "DDP"]
        incoterm = st.selectbox(
            L("Incoterm negociado"),
            opcoes_incoterm,
            index=indice_padrao("incoterm", opcoes_incoterm, 0),
            help=(
                L("O cálculo usa o preço informado como valor FOB da mercadoria e soma "
                "frete e seguro separadamente. Este campo registra o termo do contrato; "
                "não converte automaticamente preço CIF/CFR/DAP/DDP.")
            ),
            key="incoterm",
            format_func=L,
        )
        opcoes_regime = ["Não informado", "Lucro Real", "Lucro Presumido", "Simples Nacional", "Outro"]
        regime_tributario = st.selectbox(
            L("Regime tributário da importadora"),
            opcoes_regime,
            index=indice_padrao("regime_tributario", opcoes_regime, 2),
            key="regime_tributario",
            format_func=L,
        )
        registro_sanitario = st.text_input(
            L("Registro / licença sanitária aplicável"),
            value=valor_padrao("registro_sanitario", ""),
            placeholder=L("Anvisa, AFE ou não aplicável"),
            key="registro_sanitario",
        )
        quantidade = st.number_input(L("Kits importados"), min_value=1, value=valor_padrao("quantidade", 1000), step=100, key="quantidade")
        quantidade_vendida = st.number_input(
            L("Kits vendidos no período"), min_value=0,
            value=valor_padrao("quantidade_vendida", 1000), step=100, key="quantidade_vendida"
        )
        quantidade_vendida = min(quantidade_vendida, quantidade)
        cambio = st.number_input(
            L("Câmbio aduaneiro / gerencial (R$/USD)"),
            min_value=0.01,
            value=valor_padrao("cambio", 5.60),
            step=0.05,
            format="%.4f",
            key="cambio",
        )
        preco_fob_base = st.number_input(
            L("Preço FOB da matriz (USD por kit)"), min_value=0.0,
            value=valor_padrao("preco_fob_base", 200.0), step=10.0, key="preco_fob_base"
        )
        custo_fabricacao_usd = st.number_input(
            L("Custo de fabricação da matriz (USD por kit)"),
            min_value=0.0,
            value=valor_padrao("custo_fabricacao_usd", 100.0),
            step=10.0,
            key="custo_fabricacao_usd",
        )
        receita_por_kit = st.number_input(
            L("Preço bruto de venda no Brasil (R$ por kit)"),
            min_value=0.0,
            value=valor_padrao("receita_por_kit", 9598.40),
            step=100.0,
            key="receita_por_kit",
        )
        meses_operacao = st.number_input(
            L("Duração do período da DRE (meses)"), min_value=1,
            value=valor_padrao("meses_operacao", 3), step=1, key="meses_operacao"
        )
        st.divider()
        st.markdown(L("**Produto 2 (NCM diferente)**"))
        p2_ativo = st.checkbox(
            L("Incluir segundo produto na simulação"),
            value=valor_padrao("p2_ativo", False),
            key="p2_ativo",
            help=L("Importação e tributos são calculados à parte; receita, custos, lucro e margens "
            "são consolidados com o produto 1. Opex, juros, IR/CSLL e remessas são consolidados."),
        )
        p2_off = not p2_ativo
        nome_p2 = st.text_input(L("Nome do produto 2"), value=valor_padrao("nome_p2", "Produto 2"), key="nome_p2", disabled=p2_off)
        ncm_p2 = st.text_input(L("NCM do produto 2"), value=valor_padrao("ncm_p2", ""), placeholder=L("Ex.: 0000.00.00"), key="ncm_p2", disabled=p2_off)
        quantidade_p2 = st.number_input(L("Unidades importadas (produto 2)"), min_value=1, value=valor_padrao("quantidade_p2", 1000), step=100, key="quantidade_p2", disabled=p2_off)
        quantidade_vendida_p2 = min(
            st.number_input(L("Unidades vendidas no período (produto 2)"), min_value=0, value=valor_padrao("quantidade_vendida_p2", 1000), step=100, key="quantidade_vendida_p2", disabled=p2_off),
            quantidade_p2,
        )
        preco_fob_p2 = st.number_input(L("Preço FOB (USD por unidade)"), min_value=0.0, value=valor_padrao("preco_fob_p2", 0.0), step=10.0, key="preco_fob_p2", disabled=p2_off)
        custo_fabricacao_usd_p2 = st.number_input(L("Custo de fabricação (USD por unidade)"), min_value=0.0, value=valor_padrao("custo_fabricacao_usd_p2", 0.0), step=10.0, key="custo_fabricacao_usd_p2", disabled=p2_off)
        receita_por_kit_p2 = st.number_input(L("Preço bruto de venda no Brasil (R$ por unidade)"), min_value=0.0, value=valor_padrao("receita_por_kit_p2", 0.0), step=100.0, key="receita_por_kit_p2", disabled=p2_off)

    with st.expander(L("1. Valor aduaneiro — custos internacionais")):
        st.info(NOTA_IMPORTACAO_EN if IDIOMA_ATUAL == "en" else NOTA_IMPORTACAO)
        st.markdown(" · ".join(f"[{nome}]({url})" for nome, url in FONTES_IMPORTACAO))
        if uf_destino != "SP":
            st.warning(L("A memória usa a orientação de ICMS de SP. Valide a regra da UF do importador; o hub não define sozinho o destino fiscal."))
        kits_por_volume = st.number_input(
            L("Kits por caixa/volume"), min_value=1,
            value=valor_padrao("kits_por_volume", 10), step=1, key="kits_por_volume"
        )
        comprimento = st.number_input(L("Comprimento da caixa (cm)"), min_value=0.0, value=valor_padrao("comprimento", 50.0), key="comprimento")
        largura = st.number_input(L("Largura da caixa (cm)"), min_value=0.0, value=valor_padrao("largura", 40.0), key="largura")
        altura = st.number_input(L("Altura da caixa (cm)"), min_value=0.0, value=valor_padrao("altura", 30.0), key="altura")
        peso_bruto_total = st.number_input(
            L("Peso bruto total da carga (kg)"), min_value=0.0,
            value=valor_padrao("peso_bruto_total", 500.0), step=10.0, key="peso_bruto_total"
        )
        divisor_volumetrico = st.number_input(
            L("Divisor volumétrico (cm³/kg)"), min_value=1,
            value=valor_padrao("divisor_volumetrico", 6000), step=500, key="divisor_volumetrico"
        )
        opcoes_modal = ["Marítimo", "Aéreo", "Rodoviário", "Outro"]
        modal = st.selectbox(L("Modal internacional"), opcoes_modal, index=indice_padrao("modal", opcoes_modal, 0), key="modal", format_func=L)
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
            L("Como informar o frete internacional?"),
            opcoes_frete,
            index=indice_padrao("calculo_frete", opcoes_frete, 0),
            key="calculo_frete",
            format_func=L,
        )
        if calculo_frete == "Valor total informado":
            frete_usd = st.number_input(
                L("Frete internacional total (USD)"), min_value=0.0,
                value=valor_padrao("frete_usd", 0.0), step=100.0, key="frete_usd"
            )
        elif calculo_frete == "Tarifa marítima por W/M":
            tarifa_wm = st.number_input(
                L("Tarifa (USD por unidade W/M)"), min_value=0.0,
                value=valor_padrao("tarifa_wm", 0.0), step=10.0, key="tarifa_wm"
            )
            frete_usd = tarifa_wm * unidade_wm
        elif calculo_frete == "Tarifa por kg taxável":
            tarifa_frete = st.number_input(
                L("Tarifa (USD por kg taxável)"), min_value=0.0,
                value=valor_padrao("tarifa_frete_kg", 0.0), step=0.1, key="tarifa_frete_kg"
            )
            frete_usd = tarifa_frete * peso_taxavel
        else:
            tarifa_m3 = st.number_input(
                L("Tarifa (USD por m³)"), min_value=0.0,
                value=valor_padrao("tarifa_m3", 0.0), step=10.0, key="tarifa_m3"
            )
            frete_usd = tarifa_m3 * volume_m3
        if modal == "Marítimo":
            st.caption(
                L(f"Volumes: {volumes} | Volume: {volume_m3:.3f} m³ | "
                f"W/M estimado (maior entre m³ e toneladas): {unidade_wm:.3f}")
            )
        else:
            st.caption(
                L(f"Volumes: {volumes} | Volume: {volume_m3:.3f} m³ | "
                f"Peso volumétrico: {peso_volumetrico:.1f} kg | "
                f"Peso taxável estimado: {peso_taxavel:.1f} kg")
            )
        componentes_importacao = [campos_importacao_widgets("", "frete")]
        seguro_pct = percentual("Seguro (% sobre FOB + frete)", "seguro_pct", 0.5, disabled=componentes_importacao[0]["modo_seguro"] == "Valor informado")
        ajustes_aduaneiros_brl = st.number_input(
            L("Ajustes ao valor aduaneiro (R$)"),
            min_value=0.0,
            value=valor_padrao("ajustes_aduaneiros_brl", 0.0),
            help=L("Ex.: assists, royalties ou outros ajustes exigidos pelas regras de valoração.")
            ,key="ajustes_aduaneiros_brl"
        )
        frete_interno_brl = st.number_input(
            L("Frete interno até o estabelecimento (R$)"), min_value=0.0,
            value=valor_padrao("frete_interno_brl", 0.0), step=500.0, key="frete_interno_brl"
        )
        st.divider()
        st.markdown(L("**Produto 2**"))
        kits_por_volume_p2 = st.number_input(L("Kits por caixa/volume"), min_value=1, value=valor_padrao("kits_por_volume_p2", 10), step=1, key="kits_por_volume_p2", disabled=p2_off)
        comprimento_p2 = st.number_input(L("Comprimento da caixa (cm)"), min_value=0.0, value=valor_padrao("comprimento_p2", 50.0), key="comprimento_p2", disabled=p2_off)
        largura_p2 = st.number_input(L("Largura da caixa (cm)"), min_value=0.0, value=valor_padrao("largura_p2", 40.0), key="largura_p2", disabled=p2_off)
        altura_p2 = st.number_input(L("Altura da caixa (cm)"), min_value=0.0, value=valor_padrao("altura_p2", 30.0), key="altura_p2", disabled=p2_off)
        peso_bruto_total_p2 = st.number_input(L("Peso bruto total da carga (kg)"), min_value=0.0, value=valor_padrao("peso_bruto_total_p2", 500.0), step=10.0, key="peso_bruto_total_p2", disabled=p2_off)
        divisor_volumetrico_p2 = st.number_input(L("Divisor volumétrico (cm³/kg)"), min_value=1, value=valor_padrao("divisor_volumetrico_p2", 6000), step=500, key="divisor_volumetrico_p2", disabled=p2_off)
        modal_p2 = st.selectbox(L("Modal internacional (produto 2)"), opcoes_modal, index=indice_padrao("modal_p2", opcoes_modal, 0), key="modal_p2", disabled=p2_off, format_func=L)
        volumes_p2 = ceil(quantidade_p2 / kits_por_volume_p2)
        volume_m3_p2 = volumes_p2 * comprimento_p2 * largura_p2 * altura_p2 / 1_000_000
        peso_volumetrico_p2 = volumes_p2 * comprimento_p2 * largura_p2 * altura_p2 / divisor_volumetrico_p2
        peso_taxavel_p2 = max(peso_bruto_total_p2, peso_volumetrico_p2)
        unidade_wm_p2 = max(volume_m3_p2, peso_bruto_total_p2 / 1000)
        opcoes_frete_p2 = (
            ["Valor total informado", "Tarifa marítima por W/M"]
            if modal_p2 == "Marítimo"
            else ["Valor total informado", "Tarifa por kg taxável", "Tarifa por m³"]
        )
        calculo_frete_p2 = st.selectbox(
            L("Como informar o frete internacional?"), opcoes_frete_p2,
            index=indice_padrao("calculo_frete_p2", opcoes_frete_p2, 0),
            key="calculo_frete_p2", format_func=L, disabled=p2_off,
        )
        frete_usd_p2 = st.number_input(L("Frete internacional total (USD)"), min_value=0.0, value=valor_padrao("frete_usd_p2", 0.0), step=100.0, key="frete_usd_p2", disabled=p2_off or calculo_frete_p2 != "Valor total informado")
        tarifa_wm_p2 = st.number_input(L("Tarifa (USD por unidade W/M)"), min_value=0.0, value=valor_padrao("tarifa_wm_p2", 0.0), step=10.0, key="tarifa_wm_p2", disabled=p2_off or calculo_frete_p2 != "Tarifa marítima por W/M")
        tarifa_frete_kg_p2 = st.number_input(L("Tarifa (USD por kg taxável)"), min_value=0.0, value=valor_padrao("tarifa_frete_kg_p2", 0.0), step=0.1, key="tarifa_frete_kg_p2", disabled=p2_off or calculo_frete_p2 != "Tarifa por kg taxável")
        tarifa_m3_p2 = st.number_input(L("Tarifa (USD por m³)"), min_value=0.0, value=valor_padrao("tarifa_m3_p2", 0.0), step=10.0, key="tarifa_m3_p2", disabled=p2_off or calculo_frete_p2 != "Tarifa por m³")
        if calculo_frete_p2 == "Tarifa marítima por W/M":
            frete_usd_p2 = tarifa_wm_p2 * unidade_wm_p2
        elif calculo_frete_p2 == "Tarifa por kg taxável":
            frete_usd_p2 = tarifa_frete_kg_p2 * peso_taxavel_p2
        elif calculo_frete_p2 == "Tarifa por m³":
            frete_usd_p2 = tarifa_m3_p2 * volume_m3_p2
        componentes_importacao.append(campos_importacao_widgets("_p2", "frete", p2_off))
        seguro_pct_p2 = percentual("Seguro (% sobre FOB + frete)", "seguro_pct_p2", 0.5, disabled=p2_off or componentes_importacao[1]["modo_seguro"] == "Valor informado")
        ajustes_aduaneiros_brl_p2 = st.number_input(L("Ajustes ao valor aduaneiro (R$)"), min_value=0.0, value=valor_padrao("ajustes_aduaneiros_brl_p2", 0.0), key="ajustes_aduaneiros_brl_p2", disabled=p2_off)
        frete_interno_brl_p2 = st.number_input(L("Frete interno (R$)"), min_value=0.0, value=valor_padrao("frete_interno_brl_p2", 0.0), step=500.0, key="frete_interno_brl_p2", disabled=p2_off)

    with st.expander(L("2. Landed cost bruto — tributos e despesas até o hub")):
        modo_custos_importacao = seletor_modo_composicao(
            "Nível de composição dos custos aduaneiros",
            "modo_custos_importacao",
        )
        modo_importacao_detalhado = modo_custos_importacao == "Detalhado"
        if modo_importacao_detalhado:
            st.caption(L("Informe as taxas e bases efetivamente aplicáveis à classificação e à operação."))
        else:
            st.caption(
                L("Informe um único total para tributos e despesas aduaneiras. Exclua o valor aduaneiro, "
                "frete internacional, seguro e frete interno, que são tratados separadamente. "
                "Créditos recuperáveis não são separados neste modo.")
            )
        aliq_ii = percentual("II (%)", "aliq_ii", disabled=not modo_importacao_detalhado)
        aliq_ipi = percentual("IPI-importação (%)", "aliq_ipi", disabled=not modo_importacao_detalhado)
        aliq_pis = percentual("PIS-importação (%)", "aliq_pis", disabled=not modo_importacao_detalhado)
        aliq_cofins = percentual("Cofins-importação (%)", "aliq_cofins", disabled=not modo_importacao_detalhado)
        aliq_cbs = aliq_ibs = 0.0
        multiplo_base_cbs_ibs = 1.0
        aliq_icms = percentual("ICMS-importação (%)", "aliq_icms", disabled=not modo_importacao_detalhado)
        aliq_afrmm = percentual("AFRMM (%) sobre frete marítimo", "aliq_afrmm", disabled=not modo_importacao_detalhado)
        antidumping_brl = st.number_input(
            L("Antidumping / medidas compensatórias (R$)"), min_value=0.0,
            value=valor_padrao("antidumping_brl", 0.0), step=100.0,
            key="antidumping_brl", disabled=not modo_importacao_detalhado,
        )
        despesas_na_base_icms = st.number_input(
            L("Outras despesas efetivamente incluídas na base do ICMS (R$)"),
            min_value=0.0,
            value=valor_padrao("despesas_na_base_icms", 0.0),
            step=100.0,
            key="despesas_na_base_icms",
            help=L("Informe apenas valores efetivamente devidos à repartição aduaneira e demonstrados na DI/DUIMP. Exclua a Taxa Siscomex, incluída separadamente. Armazenagem, capatazia, despachante e frete interno não são incluídos automaticamente segundo a orientação da SEFAZ-SP (RC 5.832/2015)."),
            disabled=not modo_importacao_detalhado,
        )
        custos_despacho = {
            "Armazenagem": st.number_input(L("Armazenagem (R$)"), min_value=0.0, value=valor_padrao("custo_armazenagem", 0.0), step=100.0, key="custo_armazenagem", disabled=not modo_importacao_detalhado),
            "Capatazia / terminal": st.number_input(L("Capatazia / terminal (R$)"), min_value=0.0, value=valor_padrao("custo_capatazia", 0.0), step=100.0, key="custo_capatazia", disabled=not modo_importacao_detalhado),
            "Despachante aduaneiro": st.number_input(L("Despachante aduaneiro (R$)"), min_value=0.0, value=valor_padrao("custo_despachante", 0.0), step=100.0, key="custo_despachante", disabled=not modo_importacao_detalhado),
            "Taxa Siscomex": st.number_input(L("Taxa Siscomex (R$)"), min_value=0.0, value=valor_padrao("taxa_siscomex", 0.0), step=50.0, key="taxa_siscomex", disabled=not modo_importacao_detalhado),
            "Taxas portuárias / aeroportuárias": st.number_input(L("Taxas portuárias / aeroportuárias (R$)"), min_value=0.0, value=valor_padrao("taxas_terminal", 0.0), step=100.0, key="taxas_terminal", disabled=not modo_importacao_detalhado),
            "Honorários / agente de carga": st.number_input(L("Honorários / agente de carga (R$)"), min_value=0.0, value=valor_padrao("honorarios_agente_carga", 0.0), step=100.0, key="honorarios_agente_carga", disabled=not modo_importacao_detalhado),
            "Licenças, análise e inspeção": st.number_input(L("Licenças, análise e inspeção (R$)"), min_value=0.0, value=valor_padrao("licencas_inspecao", 0.0), step=100.0, key="licencas_inspecao", disabled=not modo_importacao_detalhado),
            "Outras despesas de importação": st.number_input(L("Outras despesas de importação (R$)"), min_value=0.0, value=valor_padrao("outras_despesas_importacao", 0.0), step=100.0, key="outras_despesas_importacao", disabled=not modo_importacao_detalhado),
        }
        componentes_importacao[0].update(campos_importacao_widgets("", "importacao", not modo_importacao_detalhado))
        custo_importacao_consolidado_brl = st.number_input(
            L("Tributos e despesas aduaneiras consolidados (R$)"),
            min_value=0.0,
            value=valor_padrao("custo_importacao_consolidado_brl", 0.0),
            step=1000.0,
            key="custo_importacao_consolidado_brl",
            disabled=modo_importacao_detalhado,
        )
        st.divider()
        st.markdown(L("**Produto 2**"))
        modo_custos_importacao_p2 = st.segmented_control(
            L("Modo de composição (produto 2)"),
            ["Detalhado", "Consolidado"],
            format_func=L,
            default=valor_padrao("modo_custos_importacao_p2", "Detalhado"),
            key="modo_custos_importacao_p2",
            width="stretch",
            disabled=p2_off,
        ) or "Detalhado"
        p2_detalhado = p2_ativo and modo_custos_importacao_p2 == "Detalhado"
        p2_consolidado = p2_ativo and modo_custos_importacao_p2 == "Consolidado"
        modo_importacao_detalhado_p2 = modo_custos_importacao_p2 == "Detalhado"
        aliq_ii_p2 = percentual("II (%)", "aliq_ii_p2", disabled=not p2_detalhado)
        aliq_ipi_p2 = percentual("IPI-importação (%)", "aliq_ipi_p2", disabled=not p2_detalhado)
        aliq_pis_p2 = percentual("PIS-importação (%)", "aliq_pis_p2", disabled=not p2_detalhado)
        aliq_cofins_p2 = percentual("Cofins-importação (%)", "aliq_cofins_p2", disabled=not p2_detalhado)
        aliq_cbs_p2 = aliq_ibs_p2 = 0.0
        multiplo_base_cbs_ibs_p2 = 1.0
        aliq_icms_p2 = percentual("ICMS-importação (%)", "aliq_icms_p2", disabled=not p2_detalhado)
        aliq_afrmm_p2 = percentual("AFRMM (%) sobre frete marítimo", "aliq_afrmm_p2", disabled=not p2_detalhado)
        antidumping_brl_p2 = st.number_input(L("Antidumping / medidas compensatórias (R$)"), min_value=0.0, value=valor_padrao("antidumping_brl_p2", 0.0), step=100.0, key="antidumping_brl_p2", disabled=not p2_detalhado)
        despesas_na_base_icms_p2 = st.number_input(L("Outras despesas efetivamente incluídas na base do ICMS (R$)"), min_value=0.0, value=valor_padrao("despesas_na_base_icms_p2", 0.0), step=100.0, key="despesas_na_base_icms_p2", help=L("Informe apenas valores efetivamente devidos à repartição aduaneira e demonstrados na DI/DUIMP. Exclua a Taxa Siscomex, incluída separadamente. Armazenagem, capatazia, despachante e frete interno não são incluídos automaticamente segundo a orientação da SEFAZ-SP (RC 5.832/2015)."), disabled=not p2_detalhado)
        custos_despacho_p2 = {
            nome: st.number_input(
                L(f"{nome} (R$)"), min_value=0.0, value=valor_padrao(chave + "_p2", 0.0),
                step=passo, key=chave + "_p2", disabled=not p2_detalhado,
            )
            for nome, chave, passo in (
                ("Armazenagem", "custo_armazenagem", 100.0),
                ("Capatazia / terminal", "custo_capatazia", 100.0),
                ("Despachante aduaneiro", "custo_despachante", 100.0),
                ("Taxa Siscomex", "taxa_siscomex", 50.0),
                ("Taxas portuárias / aeroportuárias", "taxas_terminal", 100.0),
                ("Honorários / agente de carga", "honorarios_agente_carga", 100.0),
                ("Licenças, análise e inspeção", "licencas_inspecao", 100.0),
                ("Outras despesas de importação", "outras_despesas_importacao", 100.0),
            )
        }
        componentes_importacao[1].update(campos_importacao_widgets("_p2", "importacao", not p2_detalhado))
        custo_importacao_consolidado_brl_p2 = st.number_input(L("Tributos e despesas aduaneiras consolidados (R$)"), min_value=0.0, value=valor_padrao("custo_importacao_consolidado_brl_p2", 0.0), step=1000.0, key="custo_importacao_consolidado_brl_p2", disabled=not p2_consolidado)

    with st.expander(L("4. Receita e tributos sobre vendas")):
        st.caption(L("Créditos são estimativas para a projeção de vendas/CMV; não reduzem o caixa da importação. No lucro presumido, não presuma créditos ordinários de PIS/COFINS-importação. Confirme a elegibilidade de ICMS/IPI e não desconte o mesmo crédito novamente dos tributos sobre vendas."))
        creditos_widgets = {}
        for sufixo, desativado in (("", not modo_importacao_detalhado), ("_p2", not p2_detalhado)):
            st.markdown("**" + L("Créditos — produto 2" if sufixo else "Créditos — produto 1") + "**")
            for imposto, rotulo in (("ipi", "IPI recuperável"), ("pis", "PIS-importação recuperável"), ("cofins", "Cofins-importação recuperável"), ("cbs_ibs", "CBS/IBS-importação recuperáveis"), ("icms", "ICMS recuperável")):
                chave = "credita_" + imposto + sufixo
                creditos_widgets[chave] = st.checkbox(L(rotulo), value=valor_padrao(chave, False), key=chave, disabled=desativado)
        credita_ipi, credita_pis, credita_cofins, credita_cbs_ibs, credita_icms = (
            creditos_widgets["credita_" + imposto] for imposto in ("ipi", "pis", "cofins", "cbs_ibs", "icms")
        )
        credita_ipi_p2, credita_pis_p2, credita_cofins_p2, credita_cbs_ibs_p2, credita_icms_p2 = (
            creditos_widgets["credita_" + imposto + "_p2"] for imposto in ("ipi", "pis", "cofins", "cbs_ibs", "icms")
        )
        devolucoes_descontos = st.number_input(
            L("Devoluções, abatimentos e descontos (R$)"), min_value=0.0,
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
        st.divider()
        st.markdown(L("**Produto 2**"))
        modo_tributos_venda_p2 = st.segmented_control(
            L("Modo de composição dos tributos sobre vendas (produto 2)"),
            ["Detalhado", "Consolidado"],
            format_func=L,
            default=valor_padrao("modo_tributos_venda_p2", "Detalhado"),
            key="modo_tributos_venda_p2",
            width="stretch",
            disabled=p2_off,
        ) or "Detalhado"
        p2_vendas_detalhadas = p2_ativo and modo_tributos_venda_p2 == "Detalhado"
        devolucoes_descontos_p2 = st.number_input(L("Devoluções, abatimentos e descontos (R$)"), min_value=0.0, value=valor_padrao("devolucoes_descontos_p2", 0.0), step=1000.0, key="devolucoes_descontos_p2", disabled=p2_off)
        aliq_icms_venda_p2 = percentual("ICMS efetivo sobre vendas (%)", "aliq_icms_venda_p2", disabled=not p2_vendas_detalhadas)
        aliq_pis_venda_p2 = percentual("PIS efetivo sobre vendas (%)", "aliq_pis_venda_p2", disabled=not p2_vendas_detalhadas)
        aliq_cofins_venda_p2 = percentual("Cofins efetiva sobre vendas (%)", "aliq_cofins_venda_p2", disabled=not p2_vendas_detalhadas)
        aliq_outros_venda_p2 = percentual("Outros tributos sobre vendas / CBS / IBS efetivos (%)", "aliq_outros_venda_p2", disabled=not p2_vendas_detalhadas)
        aliq_venda_consolidada_p2 = percentual(
            "Alíquota efetiva consolidada sobre vendas (%)",
            "aliq_venda_consolidada_p2",
            disabled=p2_vendas_detalhadas or p2_off,
        )
        operador_pct_p2 = percentual(
            "Operação / armazenagem variável (% da receita líquida)", "operador_pct_p2", 5.0, disabled=p2_off
        )
        st.caption(
            L("O produto 2 usa os mesmos cenários, câmbio, regime tributário e premissas societárias "
            "do produto 1; frete, impostos, despesas e operação variável são próprios. O Opex fixo é único e consolidado.")
        )

    with st.expander(L("5. Opex do período")):
        modo_opex = seletor_modo_composicao(
            "Nível de composição do Opex",
            "modo_opex",
        )
        st.caption(L("Valores mensais; o total é multiplicado pela duração da DRE."))
        modo_opex_detalhado = modo_opex == "Detalhado"
        opex_detalhado = {
            "Pessoal e encargos": st.number_input(L("Pessoal e encargos / mês (R$)"), min_value=0.0, value=valor_padrao("opex_pessoal", 90000.0), step=5000.0, key="opex_pessoal", disabled=not modo_opex_detalhado),
            "Aluguel e condomínio": st.number_input(L("Aluguel e condomínio / mês (R$)"), min_value=0.0, value=valor_padrao("opex_aluguel", 25000.0), step=1000.0, key="opex_aluguel", disabled=not modo_opex_detalhado),
            "Utilidades e telecomunicações": st.number_input(L("Utilidades e telecomunicações / mês (R$)"), min_value=0.0, value=valor_padrao("opex_utilidades", 10000.0), step=1000.0, key="opex_utilidades", disabled=not modo_opex_detalhado),
            "Serviços profissionais": st.number_input(L("Serviços profissionais / mês (R$)"), min_value=0.0, value=valor_padrao("opex_servicos_profissionais", 15000.0), step=1000.0, key="opex_servicos_profissionais", disabled=not modo_opex_detalhado),
            "Comercial e marketing": st.number_input(L("Comercial e marketing / mês (R$)"), min_value=0.0, value=valor_padrao("opex_comercial_marketing", 30000.0), step=1000.0, key="opex_comercial_marketing", disabled=not modo_opex_detalhado),
            "Sistemas e comunicações": st.number_input(L("Sistemas e comunicações / mês (R$)"), min_value=0.0, value=valor_padrao("opex_sistemas", 5000.0), step=500.0, key="opex_sistemas", disabled=not modo_opex_detalhado),
            "Seguros": st.number_input(L("Seguros / mês (R$)"), min_value=0.0, value=valor_padrao("opex_seguros", 5000.0), step=500.0, key="opex_seguros", disabled=not modo_opex_detalhado),
            "Depreciação e amortização": st.number_input(L("Depreciação e amortização / mês (R$)"), min_value=0.0, value=valor_padrao("opex_depreciacao", 10000.0), step=1000.0, key="opex_depreciacao", disabled=not modo_opex_detalhado),
            "Despesas administrativas": st.number_input(L("Despesas administrativas / mês (R$)"), min_value=0.0, value=valor_padrao("opex_administrativo", 5000.0), step=500.0, key="opex_administrativo", disabled=not modo_opex_detalhado),
            "Outros Opex": st.number_input(L("Outros Opex / mês (R$)"), min_value=0.0, value=valor_padrao("opex_outros", 5000.0), step=500.0, key="opex_outros", disabled=not modo_opex_detalhado),
        }
        opex_consolidado_mensal = st.number_input(
            L("Opex total consolidado / mês (R$)"),
            min_value=0.0,
            value=valor_padrao("opex_consolidado_mensal", 200000.0),
            step=5000.0,
            key="opex_consolidado_mensal",
            disabled=modo_opex_detalhado,
        )
        opex_mensal = opex_detalhado if modo_opex_detalhado else {"Opex consolidado": opex_consolidado_mensal}
        juros_brl = st.number_input(
            L("Juros e despesas financeiras do período (R$)"), min_value=0.0,
            value=valor_padrao("juros_brl", 0.0), step=1000.0,
            key="juros_brl",
        )

    with st.expander(L("6. Tributos sobre lucro e remessas")):
        if regime_tributario == "Lucro Presumido":
            st.caption(
                L("Estimativa para comércio: 1,20% de IRPJ + 1,08% de CSLL sobre a receita tributável. "
                "O adicional de IRPJ pode elevar essa soma até perto de 3,08%. Essa faixa não inclui "
                "PIS/Cofins, que devem ser informados separadamente em tributos sobre vendas.")
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
                L("Limite mensal da base para adicional de IRPJ (R$)"),
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
                L("Estimativa gerencial sobre lucro positivo; não substitui a apuração fiscal do regime.")
            )
        aliq_federal_eua = percentual("EUA: imposto corporativo federal (%)", "aliq_federal_eua", 21.0)
        aliq_fl = percentual("Flórida: imposto corporativo estadual (%)", "aliq_fl", 5.5)
        rateio_fl = st.sidebar.number_input(
            L("Parcela do lucro tributável atribuída à Flórida (%)"),
            min_value=0.0,
            max_value=100.0,
            value=valor_padrao("rateio_fl", 100.0),
            step=1.0,
            key="rateio_fl",
        ) / 100
        opex_matriz_usd = st.number_input(
            L("Opex da matriz atribuível à exportação (USD)"), min_value=0.0,
            value=valor_padrao("opex_matriz_usd", 0.0), step=1000.0,
            key="opex_matriz_usd",
        )
        participacao_matriz = st.slider(
            L("Parcela do lucro brasileiro atribuída à matriz (%)"),
            min_value=0,
            max_value=100,
            value=valor_padrao("participacao_matriz", 75),
            step=5,
            key="participacao_matriz",
        ) / 100
        st.caption(L(f"Parcela atribuída à filial/local: {1 - participacao_matriz:.0%}."))
        retencao_dividendos = percentual(
            "Retenção sobre dividendos remetidos (%)", "retencao_dividendos", 10.0
        )
        custo_remessa = percentual("Custo cambial da remessa (%)", "custo_remessa", 1.0)

    with st.expander(L("7. Cenário 2: premissas alternativas")):
        preco_fob_c2 = st.number_input(
            L("Preço FOB alternativo da matriz (USD por kit)"),
            min_value=0.0,
            value=valor_padrao("preco_fob_c2", 220.0),
            step=10.0,
            key="preco_fob_c2",
        )
        quantidade_vendida_c2 = st.number_input(
            L("Kits vendidos no cenário 2"),
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
            L("Preço bruto de venda no Brasil no cenário 2 (R$/kit)"),
            min_value=0.0,
            value=valor_padrao("receita_por_kit_c2", float(receita_por_kit)),
            step=100.0,
            key="receita_por_kit_c2",
        )
        fator_opex_c2 = st.number_input(
            L("Fator do Opex local no cenário 2 (x)"),
            min_value=0.0,
            max_value=5.0,
            value=valor_padrao("fator_opex_c2", 1.0),
            step=0.1,
            key="fator_opex_c2",
            help=L("1,0 mantém o mesmo Opex do cenário 1; 1,2 aumenta o Opex em 20%.")
        )
        if p2_ativo:
            st.markdown(L("**Produto 2 (NCM diferente)**"))
            preco_fob_c2_p2 = st.number_input(L("Preço FOB alternativo da matriz - produto 2 (USD por unidade)"), min_value=0.0, value=valor_padrao("preco_fob_c2_p2", float(preco_fob_p2)), step=10.0, key="preco_fob_c2_p2")
            quantidade_vendida_c2_p2 = min(
                st.number_input(L("Unidades vendidas no cenário 2 (produto 2)"), min_value=0, value=valor_padrao("quantidade_vendida_c2_p2", int(quantidade_vendida_p2)), step=100, key="quantidade_vendida_c2_p2"),
                quantidade_p2,
            )
            receita_por_kit_c2_p2 = st.number_input(L("Preço bruto de venda no Brasil no cenário 2 - produto 2 (R$ por unidade)"), min_value=0.0, value=valor_padrao("receita_por_kit_c2_p2", float(receita_por_kit_p2)), step=100.0, key="receita_por_kit_c2_p2")
        else:
            preco_fob_c2_p2 = preco_fob_p2
            quantidade_vendida_c2_p2 = quantidade_vendida_p2
            receita_por_kit_c2_p2 = receita_por_kit_p2
        participacao_matriz_c2 = st.slider(
            L("Parcela do lucro brasileiro atribuída à matriz (%)"),
            min_value=0,
            max_value=100,
            value=valor_padrao("participacao_matriz_c2", 75),
            step=5,
            key="participacao_matriz_c2",
        ) / 100
        st.caption(L(f"Parcela atribuída à filial/local: {1 - participacao_matriz_c2:.0%}."))
        st.caption(
            L("FOB, volume vendido, preço de venda, fator de Opex e participação variam por cenário. "
            "Câmbio, custos de importação e alíquotas permanecem compartilhados.")
        )

definir_moeda(moeda_relatorio, cambio)
EXIBINDO_ENTRADAS = False
quantidade_total = quantidade + (quantidade_p2 if p2_ativo else 0)

if modo_tributos_venda == "Detalhado":
    aliquota_venda_p1 = aliq_icms_venda + aliq_pis_venda + aliq_cofins_venda + aliq_outros_venda
else:
    aliquota_venda_p1 = aliq_venda_consolidada

PRODUTO1 = {
    "nome": "Produto 1",
    "ncm": ncm_codigo,
    "quantidade": quantidade,
    "custo_fabricacao_usd": custo_fabricacao_usd,
    "frete_usd": frete_usd,
    "modal": modal,
    "seguro_pct": seguro_pct,
    "ajustes": ajustes_aduaneiros_brl,
    "frete_interno": frete_interno_brl,
    "detalhado": modo_custos_importacao == "Detalhado",
    "aliq_ii": aliq_ii,
    "aliq_ipi": aliq_ipi,
    "aliq_pis": aliq_pis,
    "aliq_cofins": aliq_cofins,
    "aliq_cbs": aliq_cbs,
    "aliq_ibs": aliq_ibs,
    "multiplo_base": multiplo_base_cbs_ibs,
    "aliq_icms": aliq_icms,
    "aliq_afrmm": aliq_afrmm,
    "antidumping": antidumping_brl,
    "taxa_siscomex": custos_despacho["Taxa Siscomex"],
    "despesas_base_icms": despesas_na_base_icms,
    "custos_despacho": custos_despacho,
    "credita": {
        "ipi": credita_ipi, "pis": credita_pis, "cofins": credita_cofins,
        "cbs_ibs": credita_cbs_ibs, "icms": credita_icms,
    },
    "consolidado": custo_importacao_consolidado_brl,
    "devolucoes": devolucoes_descontos,
    "aliquota_venda": aliquota_venda_p1,
    "operador_pct": operador_pct,
    "componentes": componentes_importacao[0],
}
nome_p2 = nome_p2.strip() or "Produto 2"
if modo_tributos_venda_p2 == "Detalhado":
    aliquota_venda_p2 = aliq_icms_venda_p2 + aliq_pis_venda_p2 + aliq_cofins_venda_p2 + aliq_outros_venda_p2
else:
    aliquota_venda_p2 = aliq_venda_consolidada_p2

PRODUTO2 = {
    "nome": nome_p2,
    "ncm": ncm_p2,
    "quantidade": quantidade_p2,
    "custo_fabricacao_usd": custo_fabricacao_usd_p2,
    "frete_usd": frete_usd_p2,
    "modal": modal_p2,
    "seguro_pct": seguro_pct_p2,
    "ajustes": ajustes_aduaneiros_brl_p2,
    "frete_interno": frete_interno_brl_p2,
    "detalhado": modo_importacao_detalhado_p2,
    "aliq_ii": aliq_ii_p2,
    "aliq_ipi": aliq_ipi_p2,
    "aliq_pis": aliq_pis_p2,
    "aliq_cofins": aliq_cofins_p2,
    "aliq_cbs": aliq_cbs_p2,
    "aliq_ibs": aliq_ibs_p2,
    "multiplo_base": multiplo_base_cbs_ibs_p2,
    "aliq_icms": aliq_icms_p2,
    "aliq_afrmm": aliq_afrmm_p2,
    "antidumping": antidumping_brl_p2,
    "taxa_siscomex": custos_despacho_p2["Taxa Siscomex"],
    "despesas_base_icms": despesas_na_base_icms_p2,
    "custos_despacho": custos_despacho_p2,
    "credita": {
        "ipi": credita_ipi_p2, "pis": credita_pis_p2, "cofins": credita_cofins_p2,
        "cbs_ibs": credita_cbs_ibs_p2, "icms": credita_icms_p2,
    },
    "consolidado": custo_importacao_consolidado_brl_p2,
    "devolucoes": devolucoes_descontos_p2,
    "aliquota_venda": aliquota_venda_p2,
    "operador_pct": operador_pct_p2,
    "componentes": componentes_importacao[1],
} if p2_ativo else None


def calcular_produto(
    produto: dict[str, object],
    preco_fob_usd: float,
    quantidade_vendida_produto: int,
    receita_por_unidade: float,
) -> dict[str, object]:
    qtd = produto["quantidade"]
    fob_usd = preco_fob_usd * qtd
    frete_brl = produto["frete_usd"] * cambio
    componentes = produto["componentes"]
    if produto["detalhado"] and not 0 <= produto["aliq_icms"] < 1:
        st.error(L("O ICMS deve ser de 0% a menos de 100%."))
        st.stop()
    try:
        valor_aduaneiro, composicao_va, fora_va = valorar_lote(
            fob_usd, produto["frete_usd"], produto["seguro_pct"], produto["ajustes"], cambio, componentes
        )
    except ValueError as erro:
        st.error(f"{produto['nome']}: {erro}")
        st.stop()
    despesas_despacho = 0.0
    if produto["detalhado"]:
        ii = valor_aduaneiro * produto["aliq_ii"]
        base_ipi = valor_aduaneiro + ii
        ipi = base_ipi * produto["aliq_ipi"]
        pis_importacao = valor_aduaneiro * produto["aliq_pis"]
        cofins_importacao = valor_aduaneiro * produto["aliq_cofins"]
        cbs_ibs_importacao = componentes["cbs_ibs_recolher"]
        afrmm = frete_brl * produto["aliq_afrmm"] if produto["modal"] == "Marítimo" else 0.0
        base_icms_sem_grossup = (
            valor_aduaneiro + ii + ipi + pis_importacao + cofins_importacao + afrmm
            + produto["antidumping"] + produto["taxa_siscomex"] + produto["despesas_base_icms"]
            + componentes["iof_cambio"]
        )
        base_icms = (
            base_icms_sem_grossup / (1 - produto["aliq_icms"]) if produto["aliq_icms"] < 1 else 0.0
        )
        icms = base_icms * produto["aliq_icms"]
        tributos_importacao = (
            ii + ipi + pis_importacao + cofins_importacao + cbs_ibs_importacao
            + icms + afrmm + produto["antidumping"] + componentes["iof_cambio"]
        )
        despesas_adicionais = [
            ("Taxa ANVISA/TFVS", componentes["custo_anvisa"]),
            ("Armazenagem no hub de Guarulhos", componentes["custo_hub"]),
            ("Outras despesas aduaneiras", componentes["outras_despesas_aduaneiras"]),
        ]
        despesas_despacho = sum(produto["custos_despacho"].values()) + sum(v for _, v in despesas_adicionais)
        composicao_importacao = [
            ("II", ii),
            ("IPI-importação", ipi),
            ("PIS-importação", pis_importacao),
            ("Cofins-importação", cofins_importacao),
            ("CBS/IBS efetivamente a recolher", cbs_ibs_importacao),
            ("IOF-câmbio na importação", componentes["iof_cambio"]),
            ("ICMS-importação", icms),
            ("AFRMM", afrmm),
            ("Antidumping / medidas compensatórias", produto["antidumping"]),
            *produto["custos_despacho"].items(),
            *despesas_adicionais,
        ]
        creditos_ref = produto["credita"]
        creditos = (
            (ipi if creditos_ref["ipi"] else 0.0)
            + (pis_importacao if creditos_ref["pis"] else 0.0)
            + (cofins_importacao if creditos_ref["cofins"] else 0.0)
            + (cbs_ibs_importacao if creditos_ref["cbs_ibs"] else 0.0)
            + (icms if creditos_ref["icms"] else 0.0)
        )
    else:
        ii = ipi = pis_importacao = cofins_importacao = cbs_ibs_importacao = 0.0
        afrmm = icms = base_icms = creditos = 0.0
        tributos_importacao = produto["consolidado"]
        composicao_importacao = [
            ("Tributos e despesas aduaneiras consolidados", produto["consolidado"])
        ]
    desembolso_importacao = (
        valor_aduaneiro + sum(v for _, v in fora_va) + tributos_importacao + despesas_despacho + produto["frete_interno"]
    )
    custo_estoque = max(desembolso_importacao - creditos, 0.0)
    custo_unitario = custo_estoque / qtd
    cmv = custo_unitario * quantidade_vendida_produto

    receita_bruta = receita_por_unidade * quantidade_vendida_produto
    receita_liquida_comercial = max(receita_bruta - produto["devolucoes"], 0.0)
    tributos_venda = receita_liquida_comercial * produto["aliquota_venda"]
    receita_liquida = receita_liquida_comercial - tributos_venda
    custo_operacao_variavel = receita_liquida * produto["operador_pct"]
    composicao = [
        ("Valor aduaneiro", valor_aduaneiro),
        *fora_va,
        *composicao_importacao,
        ("Frete interno", produto["frete_interno"]),
        ("Landed cost bruto até o hub", desembolso_importacao),
    ]
    return {
        "nome": produto["nome"],
        "ncm": produto["ncm"],
        "quantidade": qtd,
        "quantidade_vendida": quantidade_vendida_produto,
        "fob_usd": fob_usd,
        "custo_fabricacao": produto["custo_fabricacao_usd"] * qtd * cambio,
        "valor_aduaneiro": valor_aduaneiro,
        "ii": ii,
        "ipi": ipi,
        "pis_importacao": pis_importacao,
        "cofins_importacao": cofins_importacao,
        "icms": icms,
        "afrmm": afrmm,
        "base_icms": base_icms,
        "desembolso_importacao": desembolso_importacao,
        "landed_cost_bruto": desembolso_importacao,
        "creditos": creditos,
        "custo_estoque": custo_estoque,
        "custo_unitario": custo_unitario,
        "cmv": cmv,
        "receita_bruta": receita_bruta,
        "devolucoes": min(produto["devolucoes"], receita_bruta),
        "receita_liquida_comercial": receita_liquida_comercial,
        "tributos_venda": tributos_venda,
        "receita_liquida": receita_liquida,
        "custo_operacao_variavel": custo_operacao_variavel,
        "margem_contribuicao": receita_liquida - cmv - custo_operacao_variavel,
        "composicao": composicao,
        "composicao_va": composicao_va + [("Valor aduaneiro", valor_aduaneiro)],
    }


def calcular_cenario(
    preco_fob_usd: float,
    participacao_matriz_cenario: float,
    quantidade_vendida_cenario: int,
    receita_por_kit_cenario: float,
    fator_opex_cenario: float = 1.0,
    preco_fob_p2_cenario: float | None = None,
    quantidade_vendida_p2_cenario: int | None = None,
    receita_por_kit_p2_cenario: float | None = None,
) -> dict[str, object]:
    produtos = [
        calcular_produto(PRODUTO1, preco_fob_usd, quantidade_vendida_cenario, receita_por_kit_cenario)
    ]
    if p2_ativo:
        produtos.append(
            calcular_produto(
                PRODUTO2,
                preco_fob_p2 if preco_fob_p2_cenario is None else preco_fob_p2_cenario,
                int(quantidade_vendida_p2 if quantidade_vendida_p2_cenario is None else quantidade_vendida_p2_cenario),
                receita_por_kit_p2 if receita_por_kit_p2_cenario is None else receita_por_kit_p2_cenario,
            )
        )

    def soma(chave: str) -> float:
        return sum(float(produto[chave]) for produto in produtos)

    fob_usd = soma("fob_usd")
    valor_aduaneiro = soma("valor_aduaneiro")
    ii = soma("ii")
    ipi = soma("ipi")
    pis_importacao = soma("pis_importacao")
    cofins_importacao = soma("cofins_importacao")
    icms = soma("icms")
    afrmm = soma("afrmm")
    base_icms = soma("base_icms")
    desembolso_importacao = soma("desembolso_importacao")
    landed_cost_bruto = soma("landed_cost_bruto")
    creditos = soma("creditos")
    custo_estoque = soma("custo_estoque")
    custo_unitario = custo_estoque / sum(produto["quantidade"] for produto in produtos)
    cmv = soma("cmv")
    receita_bruta = soma("receita_bruta")
    devolucoes_efetivas = soma("devolucoes")
    receita_liquida_comercial = soma("receita_liquida_comercial")
    tributos_venda = soma("tributos_venda")
    receita_liquida = soma("receita_liquida")
    aliquota_total_venda = (
        tributos_venda / receita_liquida_comercial if receita_liquida_comercial > 0 else 0.0
    )
    custo_operacao_variavel = soma("custo_operacao_variavel")
    quantidade_vendida_total = int(soma("quantidade_vendida"))
    if len(produtos) == 1:
        composicao = produtos[0]["composicao"]
    else:
        composicao = [
            (f"{produto['nome']} · {nome}", valor)
            for produto in produtos
            for nome, valor in produto["composicao"]
            if nome != "Landed cost bruto até o hub"
        ] + [("Landed cost bruto até o hub (consolidado)", landed_cost_bruto)]
    opex_total = sum(opex_mensal.values()) * meses_operacao * fator_opex_cenario
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

    custo_fabricacao = soma("custo_fabricacao")
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

    dre = [
        ("Receita bruta", receita_bruta),
        ("Devoluções, abatimentos e descontos", -devolucoes_efetivas),
        ("Tributos sobre vendas", -tributos_venda),
        ("Receita líquida", receita_liquida),
        ("Custo das mercadorias vendidas (CMV)", -cmv),
        ("Lucro bruto", receita_liquida - cmv),
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
        "quantidade_vendida": quantidade_vendida_total,
        "receita_por_kit": receita_bruta / quantidade_vendida_total if quantidade_vendida_total else receita_por_kit_cenario,
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
        "landed_cost_bruto": landed_cost_bruto,
        "creditos": creditos,
        "custo_estoque": custo_estoque,
        "custo_unitario": custo_unitario,
        "custo_fabricacao": custo_fabricacao,
        "cmv": cmv,
        "receita_bruta": receita_bruta,
        "devolucoes": devolucoes_efetivas,
        "receita_liquida_comercial": receita_liquida_comercial,
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
        "markup": receita_bruta / cmv if cmv > 0 else None,
        "margem_operacional": lucro_operacional / receita_liquida if receita_liquida > 0 else None,
        "margem_br": lucro_liquido_br / receita_liquida if receita_liquida > 0 else None,
        "margem_exportacao": (
            lucro_exportacao_liquido / (fob_usd * cambio) if fob_usd else 0.0
        ),
        "composicao": composicao,
        "produtos": produtos,
        "dre": dre,
    }


CHAVES_MONETARIAS = (
    "valor_aduaneiro", "ii", "ipi", "pis_importacao", "cofins_importacao", "icms", "afrmm",
    "base_icms", "desembolso_importacao", "landed_cost_bruto", "creditos", "custo_estoque", "custo_unitario", "cmv",
    "receita_bruta", "receita_liquida", "tributos_venda", "custo_operacao_variavel",
    "lucro_operacional", "lucro_liquido_br", "imposto_br", "imposto_irpj",
    "imposto_irpj_adicional", "imposto_csll", "lucro_exportacao_antes_imposto", "imposto_fl",
    "imposto_federal", "lucro_exportacao_liquido", "retencao", "custo_remessa",
    "remessa_liquida", "lucro_matriz_br", "lucro_filial_retido", "lucro_total_matriz",
    "lucro_global", "receita_por_kit", "custo_fabricacao", "devolucoes",
    "receita_liquida_comercial", "margem_contribuicao",
)


def converter_para_moeda_exibida(cenario: dict[str, object]) -> dict[str, object]:
    # O cálculo permanece em reais; a conversão ocorre apenas para exibição e relatórios.
    resultado = dict(cenario)
    for chave in CHAVES_MONETARIAS:
        if chave in resultado and resultado[chave] is not None:
            resultado[chave] = convertido(float(resultado[chave]))
    resultado["composicao"] = [(nome, convertido(valor)) for nome, valor in cenario["composicao"]]
    resultado["dre"] = [(nome, convertido(valor)) for nome, valor in cenario["dre"]]
    resultado["produtos"] = [
        {
            chave: convertido(float(valor)) if chave in CHAVES_MONETARIAS else valor
            for chave, valor in produto.items()
            if chave not in ("composicao", "composicao_va")
        }
        | {
            "composicao": [(nome, convertido(valor)) for nome, valor in produto["composicao"]],
            "composicao_va": [(nome, convertido(valor)) for nome, valor in produto["composicao_va"]],
        }
        for produto in cenario["produtos"]
    ]
    return resultado


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
    preco_fob_c2_p2,
    int(quantidade_vendida_c2_p2),
    receita_por_kit_c2_p2,
)
cenario1_share = participacao_matriz
cenario2_share = c2_share
cenario1 = converter_para_moeda_exibida(cenario1)
cenario2 = converter_para_moeda_exibida(cenario2)
salvar_padroes()


def tabela_linhas(linhas: list[tuple[str, float]]) -> pd.DataFrame:
    traduzidas = [
        (" · ".join(L(parte) for parte in str(nome).split(" · ")), valor)
        for nome, valor in linhas
    ]
    return pd.DataFrame(traduzidas, columns=[L("Conta"), L("Valor (R$)")])


def tabela_importacao_brl_usd(linhas: list[tuple[str, float]]) -> pd.DataFrame:
    return pd.DataFrame(
        [(L(nome), valor / MOEDA_ATUAL["fator"], valor / MOEDA_ATUAL["fator"] / cambio) for nome, valor in linhas],
        columns=[L("Componente"), "BRL", "USD"],
    )


def tabela_por_produto(cenario: dict[str, object]) -> pd.DataFrame:
    logistica = [
        {
            "ncm": ncm_codigo, "importadas": quantidade, "volumes": volumes, "volume": volume_m3,
            "bruto": peso_bruto_total, "taxavel": peso_taxavel, "modal": modal, "frete": frete_usd,
        },
        {
            "ncm": ncm_p2, "importadas": quantidade_p2, "volumes": volumes_p2, "volume": volume_m3_p2,
            "bruto": peso_bruto_total_p2, "taxavel": peso_taxavel_p2, "modal": modal_p2, "frete": frete_usd_p2,
        },
    ]
    produtos_cenario = cenario["produtos"]
    total_produtos = len(produtos_cenario)
    colunas = [L("Item")] + [str(p["nome"]) if p["nome"] not in ("Produto 1", "Produto 2") else L(p["nome"]) for p in produtos_cenario]
    if total_produtos > 1:
        colunas.append(L("Total consolidado"))
    inteiro = lambda v: f"{int(v):,}".replace(",", "." if IDIOMA_ATUAL != "en" else ",")
    decimal = lambda v, d=2: (
        f"{v:,.{d}f}" if IDIOMA_ATUAL == "en" else f"{v:,.{d}f}".replace(",", "_").replace(".", ",").replace("_", ".")
    )
    linhas: list[list[str]] = []

    def adicionar(rotulo: str, valores: list[str], total: str = "") -> None:
        linhas.append([L(rotulo)] + valores + ([total] if total_produtos > 1 else []))

    dados = logistica[:total_produtos]
    soma = lambda chave: sum(d[chave] for d in dados)
    adicionar("NCM", [str(d["ncm"] or "-") for d in dados], "-")
    adicionar("Unidades importadas", [inteiro(d["importadas"]) for d in dados], inteiro(soma("importadas")))
    adicionar("Unidades vendidas", [inteiro(p["quantidade_vendida"]) for p in produtos_cenario], inteiro(sum(p["quantidade_vendida"] for p in produtos_cenario)))
    adicionar("Volumes (caixas)", [inteiro(d["volumes"]) for d in dados], inteiro(soma("volumes")))
    adicionar("Volume (m³)", [decimal(d["volume"], 3) for d in dados], decimal(soma("volume"), 3))
    adicionar("Peso bruto (kg)", [decimal(d["bruto"], 1) for d in dados], decimal(soma("bruto"), 1))
    adicionar("Peso taxável (kg)", [decimal(d["taxavel"], 1) for d in dados], decimal(soma("taxavel"), 1))
    adicionar("Modal internacional", [L(d["modal"]) for d in dados], "-")
    adicionar("Frete internacional (USD)", [f"USD {decimal(d['frete'])}" for d in dados], f"USD {decimal(soma('frete'))}")
    dinheiro = [
        ("FOB total (USD)", "fob_usd", True),
        ("Valor aduaneiro", "valor_aduaneiro", False),
        ("Landed cost bruto até o hub", "landed_cost_bruto", False),
        ("Créditos estimados para fase posterior à venda", "creditos", False),
        ("Custo líquido do estoque para cálculo do CMV", "custo_estoque", False),
        ("Custo de aquisição por kit", "custo_unitario", False),
        ("Receita bruta", "receita_bruta", False),
        ("Tributos sobre vendas", "tributos_venda", False),
        ("Receita líquida", "receita_liquida", False),
        ("CMV do período", "cmv", False),
        ("Operação variável", "custo_operacao_variavel", False),
        ("Margem de contribuição", "margem_contribuicao", False),
    ]
    for rotulo, chave, em_usd in dinheiro:
        formatar = (lambda v: f"USD {decimal(v)}") if em_usd else (lambda v: moeda(float(v)))
        if chave == "custo_unitario":
            total = formatar(cenario[chave])
        else:
            total = formatar(sum(float(p[chave]) for p in produtos_cenario))
        adicionar(rotulo, [formatar(float(p[chave])) for p in produtos_cenario], total)
    return pd.DataFrame(linhas, columns=colunas)


def tabela_composicao_por_produto(cenario: dict[str, object]) -> pd.DataFrame:
    produtos_cenario = cenario["produtos"]
    nomes_produtos = [
        L(p["nome"]) if p["nome"] in ("Produto 1", "Produto 2") else str(p["nome"]) for p in produtos_cenario
    ]
    contas: dict[str, list[float | None]] = {}
    for indice, produto in enumerate(produtos_cenario):
        for conta, valor in produto["composicao"]:
            contas.setdefault(conta, [None] * len(produtos_cenario))[indice] = valor
    linhas = []
    for conta, valores in contas.items():
        total = sum(v for v in valores if v is not None)
        linhas.append([L(conta)] + valores + ([total] if len(produtos_cenario) > 1 else []))
    colunas = [L("Conta")] + nomes_produtos + ([L("Total consolidado")] if len(produtos_cenario) > 1 else [])
    return pd.DataFrame(linhas, columns=colunas)


def linhas_dre_entidade(
    entidade: str,
    cenario: dict[str, object],
    participacao: float,
) -> list[tuple[str, float, str, bool]]:
    valor = lambda chave: float(cenario[chave])
    if entidade == "parent":
        receita_fob = convertido(float(cenario["fob_usd"]) * cambio)
        opex_exportacao = convertido(opex_matriz_usd * cambio)
        return [
            ("Gross Export Revenue (FOB)", receita_fob, "Kits sold × agreed FOB price per kit.", True),
            ("(-) Manufacturing Cost (COGS)", -valor("custo_fabricacao"), "Manufacturing cost per kit × kits sold.", False),
            ("Gross Profit (U.S.)", receita_fob - valor("custo_fabricacao"), "Gross export revenue less manufacturing costs.", True),
            ("(-) Assigned Export OPEX", -opex_exportacao, "U.S. parent overhead allocated to export operations.", False),
            ("Earnings Before Taxes (EBT)", valor("lucro_exportacao_antes_imposto"), "Gross profit less assigned export operating expenses.", True),
            ("(-) Florida State Income Tax", -valor("imposto_fl"), f"Positive EBT × Florida rate ({aliq_fl:.2%}) × apportionment ({rateio_fl:.2%}).", False),
            ("(-) U.S. Federal Income Tax", -valor("imposto_federal"), f"Remaining positive EBT × federal rate ({aliq_federal_eua:.2%}).", False),
            ("U.S. Net Operating Profit", valor("lucro_exportacao_liquido"), "EBT less estimated Florida and federal income taxes.", True),
            ("(+) Brazil Subsidiary Dividends (Gross)", valor("lucro_matriz_br"), f"Brazil subsidiary net income × parent ownership ({participacao:.2%}).", False),
            ("(-) U.S. Withholding Tax on Dividends", -valor("retencao"), f"Gross dividends × withholding rate ({retencao_dividendos:.2%}).", False),
            ("(-) Remittance Costs", -valor("custo_remessa"), f"Post-withholding dividends × remittance fee ({custo_remessa:.2%}).", False),
            ("Net Brazil Dividend Received", valor("remessa_liquida"), "Gross dividends less withholding tax and remittance costs.", True),
            ("Total U.S. Parent Net Income", valor("lucro_total_matriz"), "Net U.S. operating profit plus net Brazil dividends received.", True),
        ]

    if entidade == "subsidiary":
        despesas_fixas = convertido(
            sum(opex_mensal.values()) * meses_operacao * valor("fator_opex")
        )
        resultado_antes_impostos = valor("lucro_operacional") - convertido(juros_brl)
        return [
            ("Gross Revenue", valor("receita_bruta"), "Kits sold in Brazil × gross selling price per kit.", True),
            ("(-) Returns, Allowances and Discounts", -valor("devolucoes"), "Configured sales returns, allowances and discounts.", False),
            ("Taxable Commercial Revenue", valor("receita_liquida_comercial"), "Gross revenue less returns, allowances and discounts.", True),
            ("(-) Sales Taxes", -valor("tributos_venda"), "ICMS, PIS, COFINS and other configured sales taxes.", False),
            ("Net Revenue", valor("receita_liquida"), "Taxable commercial revenue less sales taxes.", True),
            ("(-) Cost of Goods Sold (COGS)", -valor("cmv"), "Landed inventory cost allocated to kits sold.", False),
            ("Gross Profit", valor("receita_liquida") - valor("cmv"), "Net revenue less cost of goods sold.", True),
            ("(-) Variable Operating Expenses", -valor("custo_operacao_variavel"), "Configured variable operating and logistics costs.", False),
            ("(-) Fixed Operating Expenses (OPEX)", -despesas_fixas, "Monthly fixed OPEX × period × scenario factor.", False),
            ("Operating Income (EBIT)", valor("lucro_operacional"), "Gross profit less variable and fixed operating expenses.", True),
            ("(-) Interest and Financial Expenses", -convertido(juros_brl), "Configured interest and financial expenses for the period.", False),
            ("Earnings Before Income Taxes", resultado_antes_impostos, "Operating income less interest and financial expenses.", True),
            ("(-) Corporate Income Taxes (IRPJ/CSLL)", -valor("imposto_br"), "Estimated Brazilian income taxes under the selected tax regime.", False),
            ("Net Income - Brazil Subsidiary", valor("lucro_liquido_br"), "Earnings before income taxes less estimated corporate taxes.", True),
            ("(-) Dividends Allocated to U.S. Parent", -valor("lucro_matriz_br"), f"Below-net-income allocation; parent ownership is {participacao:.2%}.", False),
            ("Net Income Retained Locally", valor("lucro_filial_retido"), "Brazil subsidiary net income less dividends allocated to the parent.", True),
        ]

    raise ValueError(f"Unsupported income statement entity: {entidade}")


def tabela_dre_entidade(entidade: str) -> pd.DataFrame:
    linhas_c1 = linhas_dre_entidade(entidade, cenario1, cenario1_share)
    linhas_c2 = linhas_dre_entidade(entidade, cenario2, cenario2_share)
    receita_c1 = (
        convertido(float(cenario1["fob_usd"]) * cambio)
        if entidade == "parent"
        else float(cenario1["receita_bruta"])
    )
    receita_c2 = (
        convertido(float(cenario2["fob_usd"]) * cambio)
        if entidade == "parent"
        else float(cenario2["receita_bruta"])
    )
    if [linha[0] for linha in linhas_c1] != [linha[0] for linha in linhas_c2]:
        raise ValueError(f"Inconsistent income statement rows for {entidade}.")
    demonstrativo = pd.DataFrame(
        [
            {
                "Account Line Structure": conta,
                "Scenario 1": valor_c1,
                "Scenario 1 %": valor_c1 / receita_c1 if receita_c1 > 0 else None,
                "Scenario 2": valor_c2,
                "Scenario 2 %": valor_c2 / receita_c2 if receita_c2 > 0 else None,
                "Operational / Tax Logic": logica_c1,
                "Emphasis": destaque_c1,
            }
            for (conta, valor_c1, logica_c1, destaque_c1), (_, valor_c2, _, _) in zip(
                linhas_c1, linhas_c2, strict=True
            )
        ]
    )
    demonstrativo["Account Line Structure"] = demonstrativo[
        "Account Line Structure"
    ].map(L)
    demonstrativo["Operational / Tax Logic"] = demonstrativo[
        "Operational / Tax Logic"
    ].map(L)
    return demonstrativo


def valor_dre_formatado(valor: float) -> str:
    valor_arredondado = round(valor, 2)
    if valor_arredondado == 0:
        valor_arredondado = 0.0
    return (
        f"({moeda(abs(valor_arredondado))})"
        if valor_arredondado < 0
        else moeda(valor_arredondado)
    )


def percentual_dre_formatado(valor: float | None) -> str:
    if valor is None or pd.isna(valor):
        return "N/A"
    percentual_arredondado = round(float(valor) * 100, 2)
    if percentual_arredondado == 0:
        percentual_arredondado = 0.0
    return f"{percentual_arredondado:.2f}%"


def render_income_statement(title: str, statement: pd.DataFrame) -> None:
    linhas_html = []
    for _, linha in statement.iterrows():
        classe = ' class="subtotal"' if linha["Emphasis"] else ""
        percentual_c1 = linha["Scenario 1 %"]
        percentual_c2 = linha["Scenario 2 %"]
        valores = (
            linha["Scenario 1"],
            percentual_dre_formatado(percentual_c1),
            linha["Scenario 2"],
            percentual_dre_formatado(percentual_c2),
        )
        valor_html = "".join(
            f'<td class="numeric">{html_escape(valor_dre_formatado(valor))}</td>'
            if indice in (0, 2)
            else f'<td class="numeric">{html_escape(valor)}</td>'
            for indice, valor in enumerate(valores)
        )
        linhas_html.append(
            f"<tr{classe}><th scope=\"row\">{html_escape(linha['Account Line Structure'])}</th>"
            f"{valor_html}<td>{html_escape(linha['Operational / Tax Logic'])}</td></tr>"
        )
    st.html(f"""
    <section class="synvitta-income-statement" aria-label="{html_escape(title, quote=True)}">
      <h3>{html_escape(title)}</h3>
      <div class="synvitta-income-scroll">
        <table>
          <caption>{html_escape(title)} by business scenario</caption>
          <thead><tr>
            <th scope="col">{html_escape(L("Account Line Structure"))}</th>
            <th scope="col">{html_escape(L("Scenario 1"))}</th><th scope="col">%</th>
            <th scope="col">{html_escape(L("Scenario 2"))}</th><th scope="col">%</th>
            <th scope="col">{html_escape(L("Operational / Tax Logic"))}</th>
          </tr></thead>
          <tbody>{"".join(linhas_html)}</tbody>
        </table>
      </div>
    </section>
    <style>
      .synvitta-income-statement{{margin:0 0 1.5rem;color:#212529}}
      .synvitta-income-statement h3{{color:#f1f5f9;font-size:1.15rem;margin:0 0 .55rem}}
      .synvitta-income-scroll{{overflow-x:auto}}
      .synvitta-income-statement table{{border-collapse:collapse;min-width:980px;width:100%;font-size:.82rem;line-height:1.3}}
      .synvitta-income-statement th,.synvitta-income-statement td{{border:1px solid #c8d2d8;padding:.5rem .6rem;vertical-align:middle}}
      .synvitta-income-statement thead th{{background:#1A252F;color:#fff;text-align:center;white-space:nowrap}}
      .synvitta-income-statement tbody tr:nth-child(odd){{background:#EAEDF0}}
      .synvitta-income-statement tbody tr:nth-child(even){{background:#E8ECF4}}
      .synvitta-income-statement tbody tr.subtotal th,.synvitta-income-statement tbody tr.subtotal td{{font-weight:700}}
      .synvitta-income-statement tbody th{{min-width:225px;text-align:left}}
      .synvitta-income-statement td.numeric{{font-variant-numeric:tabular-nums;text-align:right;white-space:nowrap}}
      .synvitta-income-statement td:last-child{{min-width:280px}}
      .synvitta-income-statement caption{{position:absolute;width:1px;height:1px;padding:0;margin:-1px;overflow:hidden;clip:rect(0,0,0,0);white-space:nowrap;border:0}}
    </style>
    """)


def criar_grafico_resultados() -> go.Figure:
    figura = go.Figure()
    series = [
        (L("Lucro líquido da exportação da matriz"), "lucro_exportacao_liquido", "#2878a0"),
        (L("Remessa líquida à matriz"), "remessa_liquida", "#d78a36"),
        (L("Resultado retido na filial/local"), "lucro_filial_retido", "#4e9a72"),
    ]
    for nome, chave, cor in series:
        valores = [float(cenario1[chave]), float(cenario2[chave])]
        figura.add_trace(
            go.Bar(
                name=nome,
                x=[L("Cenário 1"), L("Cenário 2")],
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
        title={"text": L("Lucro por cenário e entidade"), "x": 0.02, "font": {"size": 16}},
        legend={"orientation": "h", "yanchor": "top", "y": -0.22, "xanchor": "center", "x": 0.5},
        xaxis_title=L("Cenário"),
        yaxis_title=L("Lucro (R$)"),
        uniformtext_minsize=9,
        uniformtext_mode="hide",
    )
    figura.update_yaxes(
        tickprefix=MOEDA_ATUAL["simbolo"] + " ", tickformat="~s", gridcolor="#e5ebef",
        zerolinecolor="#82909a", rangemode="tozero"
    )
    figura.update_xaxes(
        categoryorder="array",
        categoryarray=[L("Cenário 1"), L("Cenário 2")],
        automargin=True,
    )
    return figura


st.warning(
    L("Este modelo não consulta Siscomex, Classif, TEC, regimes especiais ou legislação em tempo real. "
    "Não preenche automaticamente NCM, origem, preferências tarifárias, bases especiais, créditos "
    "ou regras da reforma tributária. Use alíquotas e bases validadas por despachante e contador."
))

abas = st.tabs([
    L("Resumo"),
    L("Composição da importação"),
    L("Income Statements"),
    L("Cenários e matriz"),
])
tab_resumo = abas[0]
tab_importacao = abas[1]
tab_dre = abas[2]
tab_cenarios = abas[3]

with tab_resumo:
    st.subheader(L("📌 Resumo da DRE Operacional (Brasil)"))
    impostos_br_resumo = cenario1["tributos_venda"] + cenario1["imposto_br"]
    aliquota_impostos_br_resumo = (
        impostos_br_resumo / cenario1["receita_bruta"]
        if cenario1["receita_bruta"] > 0
        else 0.0
    )
    indicadores_dre = [
        (L("Faturamento Bruto (R$)"), moeda(cenario1["receita_bruta"])),
        (L("Acomodação / Operador (R$)"), moeda(cenario1["custo_operacao_variavel"])),
        (L("Landed Cost bruto até o hub (R$)"), moeda(cenario1["landed_cost_bruto"])),
        (L("Lucro Operacional (R$)"), moeda(cenario1["lucro_operacional"])),
        (f"{L('Impostos BR')} ({aliquota_impostos_br_resumo:.0%})", moeda(impostos_br_resumo)),
        (L("Lucro Líquido BR"), moeda(cenario1["lucro_liquido_br"])),
        (
            L("Margem operacional"),
            f"{cenario1['margem_operacional']:.2%}" if cenario1["margem_operacional"] is not None else "N/A",
        ),
        (
            L("Margem líquida Brasil"),
            f"{cenario1['margem_br']:.2%}" if cenario1["margem_br"] is not None else "N/A",
        ),
        (L("Lucro global consolidado"), moeda(cenario1["lucro_global"])),
    ]
    colunas_dre = st.columns(len(indicadores_dre))
    for coluna, (rotulo, valor) in zip(colunas_dre, indicadores_dre):
        coluna.markdown(
            f"<div style='min-height:56px;padding:5px 4px;border-bottom:2px solid #2878a0;'>"
            f"<div style='font-size:10px;line-height:1.2;color:{'#52606d' if TEMA_ATUAL == 'light' else '#cbd5e1'};'>{html_escape(rotulo)}</div>"
            f"<div style='font-size:13px;line-height:1.2;font-weight:700;color:{'#18364a' if TEMA_ATUAL == 'light' else '#f1f5f9'};margin-top:4px;'>{html_escape(valor)}</div>"
            "</div>",
            unsafe_allow_html=True,
        )
    st.caption(
        L("Indicadores do cenário 1. Impostos BR somam tributos sobre vendas e IRPJ/CSLL estimados; "
        "tributos de importação compõem o landed cost bruto, e créditos estimados são mostrados separadamente para a fase de vendas."
    ))
    st.subheader(L("Dados por produto (cenário 1)"))
    st.dataframe(tabela_por_produto(cenario1), hide_index=True, width="stretch")
    st.subheader(L("⚖️ Comparativo Executivo - Dois Cenários"))

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
                "Lucro Global por Kit (R$)": cenario1["lucro_global"] / quantidade_total,
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
        f"<th>{html_escape(L(str(coluna)))}</th>" for coluna in comparativo_executivo.columns
    )
    linhas_executivas_html = []
    for indice, (_, linha) in enumerate(comparativo_executivo.iterrows()):
        celulas = []
        for coluna in comparativo_executivo.columns:
            valor = linha[coluna]
            if pd.isna(valor):
                texto = "N/A"
            elif coluna == "Cenário Societário / Comercial":
                texto = L(valor)
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
    st.caption(L("Os valores apresentados refletem exclusivamente as premissas preenchidas no painel lateral."))
    st.plotly_chart(
        criar_grafico_resultados(),
        width="stretch",
        alt=L("Lucro líquido exportador, matriz no Brasil e filial/local para os dois cenários"),
        config={"displayModeBar": False, "responsive": True},
    )

with tab_importacao:
    st.subheader(L("Composição do valor aduaneiro"))
    for produto in cenario1["produtos"]:
        st.markdown(f"**{produto['nome']}**")
        st.dataframe(tabela_importacao_brl_usd(produto["composicao_va"]), hide_index=True, width="stretch")
    st.subheader(L("Composição do landed cost bruto até o hub"))
    for produto in cenario1["produtos"]:
        st.markdown(f"**{produto['nome']}**")
        linhas = produto["composicao"] + [
            ("Landed cost bruto — por unidade", produto["landed_cost_bruto"] / produto["quantidade"])
        ]
        st.dataframe(tabela_importacao_brl_usd(linhas), hide_index=True, width="stretch")
    st.subheader(L("Dados por produto (cenário 1)"))
    st.dataframe(tabela_por_produto(cenario1), hide_index=True, width="stretch")
    st.subheader(L("Memória de cálculo aduaneiro, landed cost bruto e créditos para vendas"))
    st.write(
        f"{L('Valor aduaneiro')}: **{moeda(cenario1['valor_aduaneiro'])}** · "
        f"{L('Base calculada do ICMS')}: **{moeda(cenario1['base_icms'])}** · "
        f"{L('Landed cost bruto até o hub')}: **{moeda(cenario1['landed_cost_bruto'])}** · "
        f"{L('Créditos estimados para fase posterior à venda')}: **{moeda(cenario1['creditos'])}**"
    )
    if p2_ativo:
        for rotulo_cenario, cenario_atual in ((L("Cenário 1"), cenario1), (L("Cenário 2"), cenario2)):
            st.markdown(f"**{rotulo_cenario}**")
            tabela_comp = tabela_composicao_por_produto(cenario_atual)
            st.dataframe(
                tabela_comp,
                hide_index=True,
                width="stretch",
                column_config={
                    coluna: st.column_config.NumberColumn(format=f"{MOEDA_ATUAL['simbolo']} %.2f")
                    for coluna in tabela_comp.columns[1:]
                },
            )
    else:
        st.dataframe(
        tabela_linhas(cenario1["composicao"]),
        hide_index=True,
        column_config={
            L("Valor (R$)"): st.column_config.NumberColumn(
                format=f"{MOEDA_ATUAL['simbolo']} %.2f"
            )
        },
        alt=L("Composição do valor aduaneiro, tributos, despesas e créditos da importação"),
    )
    if modo_custos_importacao == "Detalhado":
        st.caption(
            L("O ICMS é estimado por gross-up sobre uma base configurável simplificada. "
              "Confirme composição da base, exclusões, reduções e créditos para a UF e operação.")
        )
    else:
        st.caption(
            L("Modo consolidado: o total informado não discrimina tributos nem créditos recuperáveis. "
            "O frete interno continua sendo somado separadamente.")
        )

with tab_dre:
    render_income_statement(
        L("US Parent Company Profitability (Florida Matrix)"),
        tabela_dre_entidade("parent"),
    )
    st.caption(L("Percentages are calculated against gross export revenue (FOB) for each scenario."))

    render_income_statement(
        L("Brazil Subsidiary P&L (Local Operation)"),
        tabela_dre_entidade("subsidiary"),
    )
    st.caption(
        L("Percentages are calculated against Brazilian gross revenue. The dividend allocation "
        "is shown below net income and is not treated as an operating expense.")
    )

with tab_cenarios:
    st.subheader(L("Comparação dos cenários"))
    linhas_comparativo = [
        ("Preço FOB matriz", "USD/kit", cenario1["fob_usd"] / quantidade_total, cenario2["fob_usd"] / quantidade_total),
        ("FOB total", "USD", cenario1["fob_usd"], cenario2["fob_usd"]),
        ("Kits vendidos", "kits", cenario1["quantidade_vendida"], cenario2["quantidade_vendida"]),
        ("Preço bruto de venda Brasil", "R$/kit", cenario1["receita_por_kit"], cenario2["receita_por_kit"]),
        ("Fator de Opex local", "x", cenario1["fator_opex"], cenario2["fator_opex"]),
        ("Valor aduaneiro", "R$", cenario1["valor_aduaneiro"], cenario2["valor_aduaneiro"]),
        ("Landed cost bruto até o hub", "R$", cenario1["landed_cost_bruto"], cenario2["landed_cost_bruto"]),
        ("Créditos estimados para fase posterior à venda", "R$", cenario1["creditos"], cenario2["creditos"]),
        ("Custo líquido do estoque para cálculo do CMV", "R$", cenario1["custo_estoque"], cenario2["custo_estoque"]),
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
        ("Lucro global consolidado por kit", "R$/kit", cenario1["lucro_global"] / quantidade_total, None),
    ]
    if p2_ativo:
        for indice_produto, produto_base in enumerate(cenario1["produtos"]):
            produto_c2 = cenario2["produtos"][indice_produto]
            nome_produto = L(produto_base["nome"]) if produto_base["nome"] in ("Produto 1", "Produto 2") else produto_base["nome"]
            for rotulo, unidade, chave in (
                ("Kits vendidos", "kits", "quantidade_vendida"),
                ("FOB total", "USD", "fob_usd"),
                ("Valor aduaneiro", "R$", "valor_aduaneiro"),
                ("Landed cost bruto até o hub", "R$", "landed_cost_bruto"),
                ("Custo líquido do estoque para cálculo do CMV", "R$", "custo_estoque"),
                ("CMV do período", "R$", "cmv"),
                ("Receita líquida", "R$", "receita_liquida"),
                ("Margem de contribuição", "R$", "margem_contribuicao"),
            ):
                linhas_comparativo.append(
                    (f"{L(rotulo)} · {nome_produto}", unidade, produto_base[chave], produto_c2[chave])
                )
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
                texto = L("Não disponível")
            elif unidade == "%":
                texto = f"{valor:.2f}%"
            elif unidade == "USD":
                texto = f"USD {valor:,.2f}"
            elif unidade == "USD/kit":
                texto = f"USD {valor:,.2f}/kit"
            elif unidade == "R$/kit":
                texto = f"{moeda(float(valor))}/kit"
            elif unidade == "kits":
                texto = f"{int(valor):,}"
                if IDIOMA_ATUAL != "en":
                    texto = texto.replace(",", ".")
            elif unidade == "x":
                texto = f"{valor:.2f}x"
            else:
                texto = moeda(float(valor))
            comparativo_apresentacao.at[indice, coluna] = texto
    linhas_resultado_global = comparativo["Indicador"].isin(
        ["Lucro global consolidado", "Lucro global consolidado por kit"]
    )
    comparativo_apresentacao.loc[linhas_resultado_global, "Cenário 2"] = "N/A"
    comparativo_apresentacao_ui = comparativo_apresentacao.copy()
    comparativo_apresentacao_ui["Indicador"] = comparativo_apresentacao_ui[
        "Indicador"
    ].map(L)
    comparativo_apresentacao_ui = comparativo_apresentacao_ui.rename(
        columns={coluna: L(coluna) for coluna in comparativo_apresentacao_ui.columns}
    )
    st.dataframe(
        comparativo_apresentacao_ui,
        hide_index=True,
        alt=L("Comparação detalhada de importação, DRE, margens e alocação societária dos dois cenários"),
    )
    st.caption(
        L("Participação da matriz no lucro líquido brasileiro: {c1} no cenário 1 e {c2} no cenário 2.")
        .format(c1=f"{cenario1_share:.0%}", c2=f"{cenario2_share:.0%}")
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
        "Lucro global por kit (R$)": cenario["lucro_global"] / quantidade_total if global_aplicavel else "N/A",
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
        *(
            [
                ("Produto 2 - FOB cenário 2 USD/unidade", preco_fob_c2_p2),
                ("Produto 2 - unidades vendidas cenário 2", quantidade_vendida_c2_p2),
                ("Produto 2 - preço venda Brasil cenário 2 R$/unidade", receita_por_kit_c2_p2),
            ]
            if p2_ativo
            else []
        ),
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
if p2_ativo:
    premissas_exportacao = pd.concat(
        [
            premissas_exportacao,
            pd.DataFrame(
                [
                    ("Produto 2 - nome", nome_p2),
                    ("Produto 2 - NCM", ncm_p2),
                    ("Produto 2 - unidades importadas", quantidade_p2),
                    ("Produto 2 - unidades vendidas", quantidade_vendida_p2),
                    ("Produto 2 - FOB USD/unidade", preco_fob_p2),
                    ("Produto 2 - custo de fabricação USD/unidade", custo_fabricacao_usd_p2),
                    ("Produto 2 - preço venda Brasil R$/unidade", receita_por_kit_p2),
                    ("Produto 2 - modal", modal_p2),
                    ("Produto 2 - frete internacional USD", frete_usd_p2),
                    ("Produto 2 - seguro percentual", seguro_pct_p2),
                    ("Produto 2 - modo de composição da importação", modo_custos_importacao_p2),
                    ("Produto 2 - II percentual", aliq_ii_p2),
                    ("Produto 2 - IPI percentual", aliq_ipi_p2),
                    ("Produto 2 - PIS-importação percentual", aliq_pis_p2),
                    ("Produto 2 - Cofins-importação percentual", aliq_cofins_p2),
                    ("Produto 2 - CBS-importação percentual", aliq_cbs_p2),
                    ("Produto 2 - IBS-importação percentual", aliq_ibs_p2),
                    ("Produto 2 - ICMS-importação percentual", aliq_icms_p2),
                    ("Produto 2 - AFRMM percentual", aliq_afrmm_p2),
                    ("Produto 2 - despesas de desembaraço R$", sum(custos_despacho_p2.values())),
                    ("Produto 2 - modo de composição dos tributos sobre vendas", modo_tributos_venda_p2),
                    ("Produto 2 - alíquota sobre vendas", aliquota_venda_p2),
                    ("Produto 2 - operação variável percentual", operador_pct_p2),
                ],
                columns=["Premissa", "Valor informado"],
            ),
        ],
        ignore_index=True,
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
    for indice, produto in enumerate(cenario1["produtos"], 1):
        tabela_importacao_brl_usd(produto["composicao_va"]).to_excel(writer, sheet_name=f"VA P{indice} C1", index=False)
        tabela_importacao_brl_usd(produto["composicao"]).to_excel(writer, sheet_name=f"Landed bruto P{indice} C1", index=False)
    for entidade, nome_aba in (
        ("parent", "US Parent DRE"),
        ("subsidiary", "Brazil Subsidiary P&L"),
    ):
        demonstrativo = tabela_dre_entidade(entidade)
        destaques = demonstrativo["Emphasis"].tolist()
        demonstrativo = demonstrativo.drop(columns="Emphasis").rename(
            columns={"Scenario 1 %": "%", "Scenario 2 %": "%"}
        )
        demonstrativo.to_excel(writer, sheet_name=nome_aba, index=False)
        planilha_dre = writer.sheets[nome_aba]
        planilha_dre.freeze_panes = "A2"
        planilha_dre.auto_filter.ref = planilha_dre.dimensions
        planilha_dre.column_dimensions["A"].width = 43
        planilha_dre.column_dimensions["B"].width = 20
        planilha_dre.column_dimensions["C"].width = 13
        planilha_dre.column_dimensions["D"].width = 20
        planilha_dre.column_dimensions["E"].width = 13
        planilha_dre.column_dimensions["F"].width = 76
        currency_format = f'"{MOEDA_ATUAL["simbolo"]}" #,##0.00;("{MOEDA_ATUAL["simbolo"]}" #,##0.00)'
        for celula in planilha_dre[1]:
            celula.fill = PatternFill("solid", fgColor="1A252F")
            celula.font = Font(color="FFFFFF", bold=True)
        for indice_linha, destaque in enumerate(destaques, start=2):
            fill_color = "EAEDF0" if indice_linha % 2 == 0 else "E8ECF4"
            for celula in planilha_dre[indice_linha]:
                celula.fill = PatternFill("solid", fgColor=fill_color)
                if destaque:
                    celula.font = Font(bold=True)
            planilha_dre.cell(indice_linha, 2).number_format = currency_format
            planilha_dre.cell(indice_linha, 3).number_format = "0.00%;(0.00%)"
            planilha_dre.cell(indice_linha, 4).number_format = currency_format
            planilha_dre.cell(indice_linha, 5).number_format = "0.00%;(0.00%)"
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
    Paragraph("Synvitta3 - Relatório de simulação", estilos_pdf["Title"]),
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

for produto in cenario1["produtos"]:
    for titulo, linhas in (
        ("Composição do valor aduaneiro", produto["composicao_va"]),
        ("Composição do landed cost bruto até o hub", produto["composicao"] + [
            ("Landed cost bruto — por unidade", produto["landed_cost_bruto"] / produto["quantidade"])
        ]),
    ):
        memoria = tabela_importacao_brl_usd(linhas)
        linhas_pdf = [list(memoria.columns)] + [
            [str(nome), f"{brl:,.2f}", f"{usd:,.2f}"] for nome, brl, usd in memoria.itertuples(index=False, name=None)
        ]
        elementos_pdf.extend([
            Paragraph(html_escape(f"{L(titulo)} — {produto['nome']} — {L('Cenário 1')}"), estilos_pdf["Heading2"]),
            tabela_pdf(linhas_pdf, [360, 175, 175]),
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

for entidade, titulo in (
    ("parent", "US Parent Company Profitability (Florida Matrix)"),
    ("subsidiary", "Brazil Subsidiary P&L (Local Operation)"),
):
    demonstrativo = tabela_dre_entidade(entidade)
    linhas_dre_pdf = [[
        "Account Line Structure", "Scenario 1", "%", "Scenario 2", "%",
        "Operational / Tax Logic",
    ]]
    for _, linha in demonstrativo.iterrows():
        valor_c1 = float(linha["Scenario 1"])
        valor_c2 = float(linha["Scenario 2"])
        percentual_c1 = linha["Scenario 1 %"]
        percentual_c2 = linha["Scenario 2 %"]
        linhas_dre_pdf.append([
            str(linha["Account Line Structure"]),
            valor_dre_formatado(valor_c1),
            percentual_dre_formatado(percentual_c1),
            valor_dre_formatado(valor_c2),
            percentual_dre_formatado(percentual_c2),
            str(linha["Operational / Tax Logic"]),
        ])
    elementos_pdf.extend([
        Paragraph(html_escape(titulo), estilos_pdf["Heading2"]),
        tabela_pdf(linhas_dre_pdf, [175, 90, 42, 90, 42, 265]),
        Spacer(1, 10),
    ])

documento_pdf = SimpleDocTemplate(
    pdf_buffer,
    pagesize=landscape(A4),
    rightMargin=32,
    leftMargin=32,
    topMargin=28,
    bottomMargin=28,
    title="Synvitta3 - Relatório de simulação",
    author="Synvitta3",
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
    "Landed cost bruto até o hub": "Gross landed cost through the hub",
    "Créditos estimados para fase posterior à venda": "Estimated credits for the sales phase",
    "Custo líquido do estoque para cálculo do CMV": "Net inventory cost for COGS calculation",
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
    "Landed cost bruto até o hub": "Gross landed cost through the hub",
    "Frete internacional": "International freight",
    "Seguro internacional": "International insurance",
    "Despacho aduaneiro": "Customs clearance",
    "Armazenagem": "Warehousing",
    "Capatazia": "Cargo handling",
    "Taxa Siscomex": "Siscomex fee",
    "Outras despesas de importação": "Other import expenses",
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


def tabelas_dre_html() -> str:
    tabelas = []
    for entidade, titulo in (
        ("parent", "US Parent Company Profitability (Florida Matrix)"),
        ("subsidiary", "Brazil Subsidiary P&L (Local Operation)"),
    ):
        demonstrativo = tabela_dre_entidade(entidade)
        demonstrativo["Scenario 1"] = demonstrativo["Scenario 1"].map(
            valor_dre_formatado
        )
        demonstrativo["Scenario 2"] = demonstrativo["Scenario 2"].map(
            valor_dre_formatado
        )
        demonstrativo["Scenario 1 %"] = demonstrativo["Scenario 1 %"].map(
            percentual_dre_formatado
        )
        demonstrativo["Scenario 2 %"] = demonstrativo["Scenario 2 %"].map(
            percentual_dre_formatado
        )
        demonstrativo = demonstrativo.drop(columns="Emphasis").rename(
            columns={"Scenario 1 %": "%", "Scenario 2 %": "%"}
        )
        tabelas.append(
            f"<h3>{html_escape(titulo)}</h3>"
            + demonstrativo.to_html(
                index=False,
                border=0,
                classes="report-table income-statement",
                escape=True,
            )
        )
    return "".join(tabelas)


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
        titulo = "Synvitta3 - Detailed Simulation Report"
        aviso = "Management estimate only. Validate tax rates, customs bases, and recoverable credits with qualified professionals."
        secao_comparativo = "Scenario comparison"
        secao_resultado = "Profit by entity and scenario"
        secao_premissas = "Assumptions"
        secao_importacao = "Import composition"
        secao_dre = "Income statements"
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
        dre_html = tabelas_dre_html()
        lang = "en"
    else:
        titulo = "Synvitta3 - Relatório de simulação detalhada"
        aviso = "Estimativa gerencial. Valide alíquotas, bases aduaneiras e créditos recuperáveis com profissionais habilitados."
        secao_comparativo = "Comparação dos cenários"
        secao_resultado = "Resultado por entidade e cenário"
        secao_premissas = "Premissas utilizadas"
        secao_importacao = "Composição da importação"
        secao_dre = "Income statements"
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
        dre_html = tabelas_dre_html()
        lang = "pt-BR"
    grafico_html = grafico_relatorio_html(ingles).to_html(full_html=False, include_plotlyjs="cdn")
    memorias_html = []
    for produto in cenario1["produtos"]:
        for titulo_memoria, linhas in (
            ("Composição do valor aduaneiro", produto["composicao_va"]),
            ("Composição do landed cost bruto até o hub", produto["composicao"] + [
                ("Landed cost bruto — por unidade", produto["landed_cost_bruto"] / produto["quantidade"])
            ]),
        ):
            idioma = "en" if ingles else "pt"
            memoria = tabela_importacao_brl_usd(linhas)
            memoria.iloc[:, 0] = [translate(nome, idioma) for nome, _ in linhas]
            memoria.columns = ["Component" if ingles else "Componente", "BRL", "USD"]
            memorias_html.append(
                f"<h2>{html_escape(translate(titulo_memoria, idioma))} — {html_escape(str(produto['nome']))}</h2>"
                + memoria.to_html(index=False, border=0, classes="report-table", escape=True)
            )
    return f"""<!doctype html>
<html lang="{lang}"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{html_escape(titulo)}</title><style>
body{{font-family:Segoe UI,Arial,sans-serif;color:#203040;background:#f5f7f8;margin:0;padding:24px}}
main{{max-width:1500px;margin:auto}}h1,h2{{color:#18364a}}h1{{font-size:26px}}h2{{font-size:19px;margin-top:30px}}
.note{{color:#52606d;font-size:12px}}.report-table{{border-collapse:collapse;width:100%;background:#fff;font-size:12px}}
.report-table th{{background:#18364a;color:#fff;text-align:left}}.report-table th,.report-table td{{padding:8px;border:1px solid #d9e1e8;vertical-align:top}}
.report-table tbody tr:nth-child(even){{background:#f0f5f7}}.scroll{{overflow-x:auto}}.chart{{background:#fff;padding:8px;border:1px solid #d9e1e8}}
table.income-statement{{min-width:1050px}}table.income-statement th{{background:#1A252F;text-align:center;white-space:nowrap}}table.income-statement tbody tr:nth-child(odd){{background:#EAEDF0}}table.income-statement tbody tr:nth-child(even){{background:#E8ECF4}}table.income-statement td:nth-child(n+2):nth-child(-n+5){{text-align:right;white-space:nowrap}}
@media print{{body{{background:#fff;padding:0}}}}
</style></head><body><main><h1>{html_escape(titulo)}</h1><p class="note">{html_escape(aviso)}</p>
<h2>{secao_comparativo}</h2><div class="scroll">{comparativo_html}</div>
<h2>{secao_resultado}</h2><div class="chart">{grafico_html}</div>
<h2>{secao_premissas}</h2><div class="scroll">{premissas_html}</div>
{''.join(memorias_html)}
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
    "moeda_relatorio": ("Moeda do relatório", "Report currency", "produto", "select"),
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
    "despesas_na_base_icms": ("Outras despesas efetivamente incluídas na base do ICMS (R$)", "Other expenses actually included in the ICMS tax base (BRL)", "importacao", "number"),
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
    "preco_fob_c2_p2": ("Preço FOB alternativo da matriz (USD/unidade) - produto 2", "Alternative parent company FOB price (USD/unit) - product 2", "cenario2", "number"),
    "quantidade_vendida_c2_p2": ("Unidades vendidas no cenário 2 - produto 2", "Units sold in scenario 2 - product 2", "cenario2", "number"),
    "receita_por_kit_c2_p2": ("Preço de venda Brasil no cenário 2 (R$/unidade) - produto 2", "Brazil selling price in scenario 2 (BRL/unit) - product 2", "cenario2", "number"),
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

grupos_campos_html.update({
    "p2_produto": ("Produto 2 (NCM diferente)", "Product 2 (different HS code)"),
    "p2_frete": ("Produto 2: embalagem e frete", "Product 2: packaging and freight"),
    "p2_importacao": ("Produto 2: tributos e despesas de importação", "Product 2: import taxes and expenses"),
    "p2_vendas": ("Produto 2: receita e tributos sobre vendas", "Product 2: revenue and sales taxes"),
})
_campos_p2 = {
    "p2_ativo": ("Incluir segundo produto na simulação", "Include a second product in the simulation", "produto", "checkbox"),
    "nome_p2": ("Nome do produto 2", "Product 2 name", "produto", "text"),
    "ncm_p2": ("NCM do produto 2", "Product 2 HS code (NCM)", "produto", "text"),
    "quantidade_p2": ("Kits importados (produto 2)", "Imported units (product 2)", "produto", "number"),
    "quantidade_vendida_p2": ("Kits vendidos no período (produto 2)", "Units sold in the period (product 2)", "produto", "number"),
    "preco_fob_p2": ("Preço FOB (USD/unidade) - produto 2", "FOB price (USD/unit) - product 2", "produto", "number"),
    "custo_fabricacao_usd_p2": ("Custo de fabricação (USD/unidade) - produto 2", "Manufacturing cost (USD/unit) - product 2", "produto", "number"),
    "receita_por_kit_p2": ("Preço bruto de venda Brasil (R$/unidade) - produto 2", "Brazil gross selling price (BRL/unit) - product 2", "produto", "number"),
}
_grupo_p2 = {"produto": "produto", "frete": "frete", "importacao": "importacao", "vendas": "vendas"}
_base_p2 = (
    "kits_por_volume comprimento largura altura peso_bruto_total divisor_volumetrico modal calculo_frete "
    "frete_usd tarifa_wm tarifa_frete_kg tarifa_m3 seguro_pct ajustes_aduaneiros_brl frete_interno_brl "
    "modo_custos_importacao aliq_ii aliq_ipi aliq_pis aliq_cofins aliq_cbs aliq_ibs multiplo_base_cbs_ibs "
    "aliq_icms aliq_afrmm antidumping_brl despesas_na_base_icms custo_armazenagem custo_capatazia "
    "custo_despachante taxa_siscomex taxas_terminal honorarios_agente_carga licencas_inspecao "
    "outras_despesas_importacao custo_importacao_consolidado_brl credita_ipi credita_pis credita_cofins "
    "credita_cbs_ibs credita_icms devolucoes_descontos modo_tributos_venda aliq_icms_venda aliq_pis_venda "
    "aliq_cofins_venda aliq_outros_venda aliq_venda_consolidada operador_pct"
).split()
for _chave_base in _base_p2:
    _pt, _en, _grupo, _tipo = rotulos_campos_html[_chave_base]
    _campos_p2[_chave_base + "_p2"] = (_pt + " - produto 2", _en + " - product 2", _grupo_p2[_grupo], _tipo)
rotulos_campos_html.update(_campos_p2)
percentuais_widget_html |= {c + "_p2" for c in percentuais_widget_html if c + "_p2" in rotulos_campos_html}
valores_percentuais_iniciais["operador_pct_p2"] = 5.0
valores_percentuais_iniciais["seguro_pct_p2"] = 0.5
valores_iniciais_ocultos.update({c + "_p2": v for c, v in list(valores_iniciais_ocultos.items()) if c in _base_p2})

campos_calculadora2 = []
for chave, (rotulo_pt, rotulo_en, grupo, tipo) in rotulos_campos_html.items():
    chave_base = chave[:-3] if chave.endswith("_p2") and chave != "p2_ativo" else chave
    valor_inicial = valores_iniciais_ocultos.get(chave, valores_percentuais_iniciais.get(chave, 0.0))
    valor_execucao = locals().get(chave, valor_inicial)
    if chave in percentuais_widget_html and isinstance(valor_execucao, (int, float)):
        valor_execucao *= 100
    valor = valores_salvos_html.get(chave, st.session_state.get(chave, valor_execucao))
    opcoes = []
    if chave_base == "uf_destino":
        opcoes = [(item, item, item) for item in opcoes_uf]
    elif chave_base == "incoterm":
        opcoes = [(item, item, item) for item in opcoes_incoterm]
    elif chave_base == "regime_tributario":
        opcoes = [
            ("Não informado", "Não informado", "Not specified"),
            ("Lucro Real", "Lucro Real", "Actual-profit regime"),
            ("Lucro Presumido", "Lucro Presumido", "Presumed-profit regime"),
            ("Simples Nacional", "Simples Nacional", "Simplified National Regime"),
            ("Outro", "Outro", "Other"),
        ]
    elif chave_base == "moeda_relatorio":
        opcoes = [("USD", "USD", "USD"), ("BRL", "BRL", "BRL")]
    elif chave_base == "modal":
        opcoes = [("Marítimo", "Marítimo", "Ocean freight"), ("Aéreo", "Aéreo", "Air freight"), ("Rodoviário", "Rodoviário", "Road freight"), ("Outro", "Outro", "Other")]
    elif chave_base in {"modo_custos_importacao", "modo_tributos_venda", "modo_opex"}:
        opcoes = [("Detalhado", "Detalhado", "Detailed"), ("Consolidado", "Consolidado", "Consolidated")]
    elif chave_base == "calculo_frete":
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

TITULOS_HTML = {"pt": "Synvitta3 - Simulação detalhada", "en": "Synvitta3 - Detailed simulation"}
campos_calculadora2 = completar_campos_importacao(campos_calculadora2)
for campo in campos_calculadora2:
    campo["value"] = st.session_state.get(campo["key"], valores_salvos_html.get(campo["key"], campo["value"]))
relatorio_html_pt = build_calculator_html(
    model_id="synvitta3",
    language="pt",
    title="Synvitta3 - Simulação detalhada",
    fields=campos_calculadora2,
    calculation_js=synvitta3_calculation_js(),
    titles=TITULOS_HTML,
)
relatorio_html_en = build_calculator_html(
    model_id="synvitta3",
    language="en",
    title="Synvitta3 - Detailed simulation",
    fields=campos_calculadora2,
    calculation_js=synvitta3_calculation_js(),
    titles=TITULOS_HTML,
)
relatorio_html_app = build_calculator_html(
    model_id="synvitta3",
    language="pt",
    title="Synvitta3",
    fields=campos_calculadora2,
    calculation_js=synvitta3_calculation_js(),
    titles=TITULOS_HTML,
    auto_language=True,
)
try:
    pasta_relatorios = Path(__file__).resolve().parent
    (pasta_relatorios / "synvitta3_relatorio.html").write_text(relatorio_html_pt, encoding="utf-8")
    (pasta_relatorios / "synvitta3_report.htm").write_text(relatorio_html_en, encoding="utf-8")
    (pasta_relatorios / "synvitta3_app.html").write_text(relatorio_html_app, encoding="utf-8")
    status_relatorio = "Arquivos HTML/HTM atualizados na pasta do Synvitta3."
except OSError as erro_gravacao:
    status_relatorio = f"Não foi possível gravar os arquivos na pasta do app: {erro_gravacao}"

with st.container(horizontal=True):
    st.download_button(
        L("Baixar resumo CSV"),
        data=resumo_exportacao.to_csv(index=False).encode("utf-8-sig"),
        file_name="synvitta3_resumo.csv",
        mime="text/csv",
        icon=":material/download:",
    )
    st.download_button(
        L("Baixar relatório Excel"),
        data=arquivo_excel.getvalue(),
        file_name="synvitta3_relatorio.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        on_click="ignore",
        icon=":material/download:",
    )
    st.download_button(
        L("Baixar relatório PDF"),
        data=arquivo_pdf,
        file_name="synvitta3_relatorio.pdf",
        mime="application/pdf",
        on_click="ignore",
        icon=":material/download:",
    )
    st.download_button(
        L("Baixar relatório HTML"),
        data=relatorio_html_pt.encode("utf-8"),
        file_name="synvitta3_relatorio.html",
        mime="text/html",
        icon=":material/download:",
    )
    st.download_button(
        L("Baixar HTML bilíngue (PC e celular)"),
        data=relatorio_html_app.encode("utf-8"),
        file_name="synvitta3_app.html",
        mime="text/html",
        icon=":material/download:",
    )
    st.download_button(
        L("Download English report"),
        data=relatorio_html_en.encode("utf-8"),
        file_name="synvitta3_report.htm",
        mime="text/html",
        icon=":material/download:",
    )
st.caption(L(status_relatorio))
