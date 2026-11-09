"""Estimativas gerenciais locais; nenhuma consulta externa ou inferencia por IA."""

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from apoio.synvitta3_importacao import CAMPOS_IMPORTACAO, valorar_lote


Valor = Annotated[float, Field(ge=0)]
Taxa = Annotated[float, Field(ge=0, le=1)]


class Modelo(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False, extra="forbid")


class Globais(Modelo):
    empresa: str = "Synvitta L.A. Ltda."
    ptax: float = Field(default=5.6, gt=0)
    uf_destino: str = "SP"
    incoterm: str = "EXW"
    hub_nacionalizacao: str = "Guarulhos/SP"


class CustosUSD(Modelo):
    frete_internacional_aereo: Valor = 9000
    frete_origem: Valor = 1500
    seguro_internacional: Valor = 500
    despacho_miami: Valor = 500
    locacao_uld_rap: Valor = 5000
    despacho_na_va: Valor = 0
    locacao_na_va: Valor = 0

    @model_validator(mode="after")
    def conferir_valoracao(self):
        if self.despacho_na_va > self.despacho_miami:
            raise ValueError("Despacho na VA excede o despacho total.")
        if self.locacao_na_va > self.locacao_uld_rap:
            raise ValueError("Locacao na VA excede a locacao total.")
        return self


class CustosBRL(Modelo):
    armazenagem_terminal: Valor = 21000
    despachante_aduaneiro: Valor = 7000
    taxa_siscomex: Valor = 230
    taxa_anvisa: Valor = 536
    outras_parcelas_base_icms: Valor = 0

    @model_validator(mode="after")
    def conferir_base(self):
        if self.outras_parcelas_base_icms > (
            self.armazenagem_terminal + self.despachante_aduaneiro + self.taxa_anvisa
        ):
            raise ValueError("Parcelas da base ICMS devem estar nos custos ja lancados.")
        return self


class AliquotasImportacao(Modelo):
    ii: Taxa = 0
    ipi: Taxa = 0
    pis: Taxa = 0
    cofins: Taxa = 0
    icms: float = Field(default=0, ge=0, lt=1)


class CreditosImportacao(Modelo):
    credita_ipi: bool = False
    credita_icms: bool = False


class AliquotasVenda(Modelo):
    icms: Taxa = 0.18
    pis: Taxa = 0.0065
    cofins: Taxa = 0.03
    operador_var: Taxa = 0


class Produto(Modelo):
    nome_produto: str = Field(min_length=1)
    ncm: str = Field(min_length=1)
    quantidade: int = Field(gt=0)
    preco_unitario_exw_usd: float = Field(gt=0)
    preco_venda_unitario_brl: Valor
    frete_interno_hub_brl: Valor = 0
    aliquotas_importacao: AliquotasImportacao = Field(default_factory=AliquotasImportacao)
    creditos_importacao: CreditosImportacao = Field(default_factory=CreditosImportacao)
    aliquotas_venda: AliquotasVenda = Field(default_factory=AliquotasVenda)
    pis_venda_real: Taxa = 0.0165
    cofins_venda_real: Taxa = 0.076
    credito_pis_importacao_real_brl: Valor = 0
    credito_cofins_importacao_real_brl: Valor = 0


class Estrutura(Modelo):
    opex_fixo_mensal_brl: Valor = 200000
    meses_operacao: int = Field(default=1, ge=1, le=3)
    participacao_matriz_eua_pct: Taxa = 0.75
    participacao_socios_locais_sp_pct: Taxa = 0.25
    retencao_dividendos_pct: Taxa = 0.10
    custo_remessa_pct: Taxa = 0.01

    @model_validator(mode="after")
    def conferir_participacoes(self):
        if abs(
            self.participacao_matriz_eua_pct
            + self.participacao_socios_locais_sp_pct - 1
        ) > 1e-8:
            raise ValueError("As participacoes da matriz e dos socios devem somar 100%.")
        return self


class Tributacao(Modelo):
    ano: Literal[2025, 2026] = 2026
    trimestre: int = Field(default=4, ge=1, le=4)
    base_presumida_irpj: Taxa = 0.08
    base_presumida_csll: Taxa = 0.12
    excluir_icms_base_pis_cofins: bool = True
    adicoes_real_brl: Valor = 0
    exclusoes_real_brl: Valor = 0


class Cenario(Modelo):
    parametros_globais: Globais = Field(default_factory=Globais)
    custos_compartilhados_usd: CustosUSD = Field(default_factory=CustosUSD)
    custos_compartilhados_brl: CustosBRL = Field(default_factory=CustosBRL)
    produtos: list[Produto] = Field(min_length=2, max_length=2)
    estrutura_opex_e_societaria: Estrutura = Field(default_factory=Estrutura)
    tributacao: Tributacao = Field(default_factory=Tributacao)


def cenario_padrao() -> Cenario:
    return Cenario(produtos=[
        Produto(
            nome_produto="Kit Reagente / Diagnostico", ncm="3822.19.90",
            quantidade=1440, preco_unitario_exw_usd=200,
            preco_venda_unitario_brl=9600, frete_interno_hub_brl=1200,
            aliquotas_venda=AliquotasVenda(icms=0.04, operador_var=0.04),
        ),
        Produto(
            nome_produto="Leitor Optico", ncm="9027.50.20", quantidade=160,
            preco_unitario_exw_usd=5000, preco_venda_unitario_brl=280000,
            frete_interno_hub_brl=800,
            aliquotas_importacao=AliquotasImportacao(
                ii=0.14, ipi=0.0975, pis=0.021, cofins=0.0965, icms=0.18,
            ),
            creditos_importacao=CreditosImportacao(credita_ipi=True, credita_icms=True),
        ),
    ])


class LandedCostProduto(Modelo):
    nome_produto: str
    ncm: str
    quantidade: int
    valor_exw_total_usd: float
    rateio_pct: float
    cif_total_brl: float
    custos_fora_va_brl: float
    despesas_locais_brl: float
    ii_brl: float
    ipi_brl: float
    pis_brl: float
    cofins_brl: float
    base_icms_brl: float
    icms_brl: float
    landed_cost_bruto_total_brl: float
    creditos_tributarios_recuperaveis_brl: float
    custo_estoque_liquido_cmv_brl: float
    custo_unitario_cmv_brl: float


class LandedCostLoteConsolidado(Modelo):
    ptax_utilizada: float
    valor_exw_total_lote_usd: float
    cif_total_lote_brl: float
    landed_cost_bruto_lote_brl: float
    creditos_totais_lote_brl: float
    custo_estoque_liquido_lote_brl: float
    produtos: list[LandedCostProduto]


class DREItemProduto(Modelo):
    nome_produto: str
    unidades_vendidas: int
    receita_bruta_brl: float
    icms_venda_brl: float
    base_pis_cofins_brl: float
    pis_venda_brl: float
    cofins_venda_brl: float
    tributos_venda_brl: float
    receita_liquida_brl: float
    cmv_brl: float
    lucro_bruto_brl: float
    operacao_variavel_brl: float
    margem_contribucao_pct: float


class DREDetalhadaRegime(Modelo):
    regime_tributario: str
    receita_bruta_total_brl: float
    tributos_venda_total_brl: float
    receita_liquida_total_brl: float
    cmv_total_brl: float
    lucro_bruto_total_brl: float
    opex_fixo_brl: float
    operacao_variavel_brl: float
    ebitda_brl: float
    base_irpj_brl: float
    base_csll_brl: float
    receita_excedente_majoracao_brl: float
    irpj_brl: float
    adicional_irpj_brl: float
    csll_brl: float
    irpj_csll_brl: float
    lucro_liquido_brasil_brl: float
    margem_liquida_pct: float
    dividendos_matriz_brutos_brl: float
    retencao_dividendos_brl: float
    custo_remessa_brl: float
    remessa_matriz_eua_brl: float
    lucro_retido_filial_sp_brl: float
    parcela_socios_locais_brl: float
    margem_socios_locais_pct: float
    itens_produtos: list[DREItemProduto]


class DREReportSynvitta(Modelo):
    projeto: str = "synvitta3_report"
    empresa: str
    ptax: float
    lucro_real: DREDetalhadaRegime
    lucro_presumido: DREDetalhadaRegime
    regime_recomendado: str
    economia_tributaria_periodo_brl: float
    economia_tributaria_anual_estimada_brl: float
    landed_cost: LandedCostLoteConsolidado
    premissas: Cenario
    avisos: list[str]


def calcular_landed_cost(cenario: Cenario) -> LandedCostLoteConsolidado:
    usd = cenario.custos_compartilhados_usd
    brl = cenario.custos_compartilhados_brl
    cambio = cenario.parametros_globais.ptax
    exw_total = sum(p.quantidade * p.preco_unitario_exw_usd for p in cenario.produtos)
    produtos = []
    for produto in cenario.produtos:
        exw = produto.quantidade * produto.preco_unitario_exw_usd
        peso = exw / exw_total
        componentes = {chave: inicial for chave, _, _, _, _, inicial in CAMPOS_IMPORTACAO}
        componentes.update({
            "frete_origem_usd": usd.frete_origem * peso,
            "despacho_miami_usd": usd.despacho_miami * peso,
            "despacho_na_va_usd": usd.despacho_na_va * peso,
            "locacao_rap_usd": usd.locacao_uld_rap * peso,
            "locacao_na_va_usd": usd.locacao_na_va * peso,
            "modo_seguro": "Valor informado",
            "seguro_total_usd": usd.seguro_internacional * peso,
        })
        va, _, parcelas_fora = valorar_lote(
            exw, usd.frete_internacional_aereo * peso, 0, 0, cambio, componentes
        )
        fora_va = sum(valor for _, valor in parcelas_fora)
        taxas = produto.aliquotas_importacao
        ii = va * taxas.ii
        ipi = (va + ii) * taxas.ipi
        pis = va * taxas.pis
        cofins = va * taxas.cofins
        base_icms = (
            va + ii + ipi + pis + cofins
            + (brl.taxa_siscomex + brl.outras_parcelas_base_icms) * peso
        ) / (1 - taxas.icms)
        icms = base_icms * taxas.icms
        despesas = (
            brl.armazenagem_terminal + brl.despachante_aduaneiro
            + brl.taxa_siscomex + brl.taxa_anvisa
        ) * peso + produto.frete_interno_hub_brl
        bruto = va + fora_va + ii + ipi + pis + cofins + icms + despesas
        creditos = (
            (ipi if produto.creditos_importacao.credita_ipi else 0)
            + (icms if produto.creditos_importacao.credita_icms else 0)
        )
        if produto.credito_pis_importacao_real_brl > pis + 1e-8:
            raise ValueError(f"{produto.nome_produto}: credito PIS excede o PIS importado.")
        if produto.credito_cofins_importacao_real_brl > cofins + 1e-8:
            raise ValueError(f"{produto.nome_produto}: credito Cofins excede a Cofins importada.")
        produtos.append(LandedCostProduto(
            nome_produto=produto.nome_produto, ncm=produto.ncm,
            quantidade=produto.quantidade, valor_exw_total_usd=exw,
            rateio_pct=peso * 100, cif_total_brl=va,
            custos_fora_va_brl=fora_va, despesas_locais_brl=despesas,
            ii_brl=ii, ipi_brl=ipi, pis_brl=pis, cofins_brl=cofins,
            base_icms_brl=base_icms, icms_brl=icms,
            landed_cost_bruto_total_brl=bruto,
            creditos_tributarios_recuperaveis_brl=creditos,
            custo_estoque_liquido_cmv_brl=bruto - creditos,
            custo_unitario_cmv_brl=(bruto - creditos) / produto.quantidade,
        ))
    return LandedCostLoteConsolidado(
        ptax_utilizada=cambio, valor_exw_total_lote_usd=exw_total,
        cif_total_lote_brl=sum(p.cif_total_brl for p in produtos),
        landed_cost_bruto_lote_brl=sum(p.landed_cost_bruto_total_brl for p in produtos),
        creditos_totais_lote_brl=sum(p.creditos_tributarios_recuperaveis_brl for p in produtos),
        custo_estoque_liquido_lote_brl=sum(p.custo_estoque_liquido_cmv_brl for p in produtos),
        produtos=produtos,
    )


def calcular_dre(
    cenario: Cenario, landed: LandedCostLoteConsolidado, *, real: bool
) -> DREDetalhadaRegime:
    fiscal = cenario.tributacao
    estrutura = cenario.estrutura_opex_e_societaria
    itens = []
    for produto, custo in zip(cenario.produtos, landed.produtos, strict=True):
        receita = produto.quantidade * produto.preco_venda_unitario_brl
        venda = produto.aliquotas_venda
        icms = receita * venda.icms
        base_pis = receita - icms if fiscal.excluir_icms_base_pis_cofins else receita
        pis = base_pis * (produto.pis_venda_real if real else venda.pis)
        cofins = base_pis * (produto.cofins_venda_real if real else venda.cofins)
        tributos = icms + pis + cofins
        if tributos > receita + 1e-8:
            raise ValueError(f"{produto.nome_produto}: tributos de venda excedem a receita.")
        liquida = receita - tributos
        cmv = custo.custo_estoque_liquido_cmv_brl
        if real:
            # Creditos recuperaveis saem do CMV, nunca dos tributos de venda novamente.
            cmv -= (
                produto.credito_pis_importacao_real_brl
                + produto.credito_cofins_importacao_real_brl
            )
        operador = liquida * venda.operador_var
        bruto = liquida - cmv
        itens.append(DREItemProduto(
            nome_produto=produto.nome_produto, unidades_vendidas=produto.quantidade,
            receita_bruta_brl=receita, icms_venda_brl=icms,
            base_pis_cofins_brl=base_pis, pis_venda_brl=pis, cofins_venda_brl=cofins,
            tributos_venda_brl=tributos, receita_liquida_brl=liquida,
            cmv_brl=cmv, lucro_bruto_brl=bruto, operacao_variavel_brl=operador,
            margem_contribucao_pct=(bruto - operador) / receita * 100 if receita else 0,
        ))
    receita = sum(p.receita_bruta_brl for p in itens)
    liquida = sum(p.receita_liquida_brl for p in itens)
    cmv = sum(p.cmv_brl for p in itens)
    operador = sum(p.operacao_variavel_brl for p in itens)
    opex = estrutura.opex_fixo_mensal_brl * estrutura.meses_operacao
    ebitda = liquida - cmv - opex - operador
    excedente = max(receita - 1_250_000, 0) if fiscal.ano == 2026 else 0
    if real:
        base_irpj = base_csll = max(
            ebitda + fiscal.adicoes_real_brl - fiscal.exclusoes_real_brl, 0
        )
    else:
        base_irpj = fiscal.base_presumida_irpj * (receita + excedente * 0.10)
        excedente_csll = excedente if fiscal.trimestre >= 2 else 0
        base_csll = fiscal.base_presumida_csll * (receita + excedente_csll * 0.10)
    irpj = base_irpj * 0.15
    adicional = max(base_irpj - 60_000, 0) * 0.10
    csll = base_csll * 0.09
    imposto = irpj + adicional + csll
    lucro = ebitda - imposto
    distribuivel = max(lucro, 0)
    dividendos = distribuivel * estrutura.participacao_matriz_eua_pct
    retencao = dividendos * estrutura.retencao_dividendos_pct
    custo_remessa = (dividendos - retencao) * estrutura.custo_remessa_pct
    locais = distribuivel * estrutura.participacao_socios_locais_sp_pct
    return DREDetalhadaRegime(
        regime_tributario="Lucro Real (estimado)" if real else "Lucro Presumido",
        receita_bruta_total_brl=receita,
        tributos_venda_total_brl=sum(p.tributos_venda_brl for p in itens),
        receita_liquida_total_brl=liquida, cmv_total_brl=cmv,
        lucro_bruto_total_brl=liquida - cmv, opex_fixo_brl=opex,
        operacao_variavel_brl=operador, ebitda_brl=ebitda,
        base_irpj_brl=base_irpj, base_csll_brl=base_csll,
        receita_excedente_majoracao_brl=0 if real else excedente,
        irpj_brl=irpj, adicional_irpj_brl=adicional, csll_brl=csll,
        irpj_csll_brl=imposto, lucro_liquido_brasil_brl=lucro,
        margem_liquida_pct=lucro / receita * 100 if receita else 0,
        dividendos_matriz_brutos_brl=dividendos, retencao_dividendos_brl=retencao,
        custo_remessa_brl=custo_remessa,
        remessa_matriz_eua_brl=dividendos - retencao - custo_remessa,
        lucro_retido_filial_sp_brl=lucro - dividendos,
        parcela_socios_locais_brl=locais,
        margem_socios_locais_pct=locais / receita * 100 if receita else 0,
        itens_produtos=itens,
    )


def calcular_cenario(cenario: Cenario) -> DREReportSynvitta:
    landed = calcular_landed_cost(cenario)
    real = calcular_dre(cenario, landed, real=True)
    presumido = calcular_dre(cenario, landed, real=False)
    diferenca = abs(real.lucro_liquido_brasil_brl - presumido.lucro_liquido_brasil_brl)
    melhor = "Lucro Real estimado" if (
        real.lucro_liquido_brasil_brl > presumido.lucro_liquido_brasil_brl
    ) else "Lucro Presumido"
    avisos = [
        "Estimativa gerencial, nao apuracao fiscal. Aliquotas e beneficios por NCM, "
        "elegibilidade ao Presumido, creditos e documentacao precisam de validacao contabil.",
        "Venda integral do lote no trimestre informado, sem triplicar a receita. "
        "Opex mensal multiplicado apenas pelos meses de operacao informados.",
        "Custos comuns rateados pelo valor EXW. VA inclui mercadoria, fretes, seguro "
        "e parcelas informadas de despacho/ULD. Despesas da base ICMS nao sao novo custo.",
        "Limite do adicional IRPJ: R$ 60.000 por trimestre completo. LC 224/2025: "
        "limite isolado R$ 1.250.000 por trimestre, sem ajustes de trimestres anteriores; "
        "majoracao de presuncao IRPJ desde Q1/2026 e CSLL desde Q2/2026.",
        "Comparacao do Lucro Real condicionada aos creditos PIS/Cofins informados "
        "manualmente; nao inclui creditos domesticos, prejuizos fiscais anteriores "
        "ou outros ajustes alem das adicoes/exclusoes informadas.",
        "Sem depreciacao, juros, receitas financeiras, IPI de saida, ST/DIFAL, "
        "CBS/IBS ou outros tributos nao informados. CBS/IBS zero em 2026 pressupoe "
        "dispensa aplicavel e cumprimento das obrigacoes acessorias.",
        "Retencao de dividendos e custo da remessa sao premissas editaveis, "
        "nao despesas operacionais. Nao inclui lucro ou tributacao da matriz nos EUA.",
        "Valores calculados com precisao integral e exibidos com duas casas; "
        "arredondamentos de documentos fiscais podem gerar diferencas.",
    ]
    for produto in cenario.produtos:
        if not any(produto.aliquotas_importacao.model_dump().values()):
            avisos.append(
                f"{produto.nome_produto}: todas as aliquotas de importacao estao "
                "zeradas. Beneficio/isencao nao foi comprovado pelo programa."
            )
        if produto.creditos_importacao.credita_ipi:
            avisos.append(
                f"{produto.nome_produto}: credito de IPI selecionado; "
                "confirme recuperabilidade e tratamento do IPI de saida."
            )
    return DREReportSynvitta(
        empresa=cenario.parametros_globais.empresa,
        ptax=cenario.parametros_globais.ptax,
        lucro_real=real, lucro_presumido=presumido,
        regime_recomendado=(
            f"{melhor} apresenta maior lucro nesta simulacao; nao constitui "
            "recomendacao fiscal nem confirma elegibilidade ao regime."
        ),
        economia_tributaria_periodo_brl=diferenca,
        economia_tributaria_anual_estimada_brl=diferenca * 4,
        landed_cost=landed, premissas=cenario,
        avisos=avisos + [
            "Economia anual, quando exportada, e apenas a diferenca trimestral "
            "multiplicada por quatro, nao previsao ou apuracao anual."
        ],
    )
