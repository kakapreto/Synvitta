"""Campos e notas comuns da memória de importação (valores por lote)."""

from math import isfinite

NOTA_IMPORTACAO = (
    "Referência: 02/11/2026. Valores por lote, sem repetir custos já contidos na fatura/frete. "
    "Mercadoria = preço unitário × quantidade; o Incoterm não ajusta parcelas automaticamente. "
    "VA inclui transporte, seguro e ajustes de valoração até o local de importação "
    "(Regulamento Aduaneiro, arts. 77–79; IN RFB 2.090/2022). "
    "ULD/RAP e despacho de exportação: informe o total e a parcela incluída na VA conforme documentos; "
    "a exclusão não é automática. Preservadas as premissas antigas até revisão explícita. "
    "Capatazia nacional destacada do transporte não integra a VA (Decreto 11.090/2022). "
    "ICMS-SP por dentro inclui Siscomex e outras despesas aduaneiras qualificadas; "
    "armazenagem, despachante e frete interno não entram automaticamente (RC 5.832/2015). "
    "A parcela adicional da base do ICMS é apenas uma classificação de custos já lançados, não outro desembolso. "
    "CBS/IBS na Duimp em 2026: não recolher, segundo a RFB (manual atualizado em 06/10/2026); "
    "o campo de recolhimento efetivo inicia em zero e não usa o antigo múltiplo da VA. "
    "Alíquotas/benefícios dependem de NCM, origem, regime e data: validar no Classif/DI/Duimp. "
    "Rateie despesas da declaração entre produtos; não lance o total integral em cada produto. "
    "Landed bruto = VA + custos fora da VA + tributos pagos + despesas até o hub. "
    "Créditos somente na projeção de vendas/CMV, conforme elegibilidade; não presuma créditos ordinários "
    "de PIS/COFINS-importação no lucro presumido. Não descontar o mesmo crédito novamente dos tributos de venda. "
    "Não é uma apuração fiscal automática para 2027 em diante."
)

NOTA_IMPORTACAO_EN = (
    "Reviewed 2026-11-02. Enter per-lot costs not already included in the goods invoice or freight. "
    "Goods = unit price × quantity; changing the Incoterm does not reallocate costs automatically. "
    "Customs value includes transport, insurance and valuation additions through the import location "
    "(Customs Regulations, arts. 77–79; IN RFB 2,090/2022). "
    "Enter total rental/export clearance and their documented customs-value portions; exclusion is not automatic. "
    "Legacy allocations are preserved pending explicit review. Separately identified Brazilian handling is excluded "
    "from customs value (Decree 11,090/2022). São Paulo ICMS is grossed up and includes Siscomex and qualifying "
    "customs charges, not automatically storage, brokerage or domestic freight (RC 5,832/2015). "
    "The additional ICMS base field classifies costs already entered; it is not another expense. "
    "RFB's Duimp guide, updated 2026-10-06, states CBS/IBS must not be paid in 2026. "
    "Actual CBS/IBS payable defaults to zero; the former customs-value multiplier is not used. "
    "Confirm rates, surcharges and benefits against NCM, origin, regime and declaration date in Classif/DI/Duimp. "
    "Allocate declaration-level costs across products instead of entering the full cost twice. "
    "Gross landed cost includes customs value, costs outside it, taxes paid and costs through the hub. "
    "Credits belong only to the sales/COGS projection, subject to eligibility; ordinary import PIS/COFINS credits "
    "must not be presumed under the presumed-profit regime. This is not an automatic tax determination for 2027 onward."
)
FONTES_IMPORTACAO = (
    ("Regulamento Aduaneiro, arts. 77–79", "https://www.planalto.gov.br/ccivil_03/_ato2007-2010/2009/decreto/d6759.htm"),
    ("Capatazia: Decreto 11.090/2022", "https://www.planalto.gov.br/ccivil_03/_ato2019-2022/2022/decreto/D11090.htm"),
    ("ICMS-SP: RC 5.832/2015", "https://legislacao.fazenda.sp.gov.br/Paginas/RC5832_2015.aspx"),
    ("RFB: Duimp e transição 2026", "https://www.gov.br/receitafederal/pt-br/assuntos/aduana-e-comercio-exterior/manuais/despacho-de-importacao/sistemas/duimp/rtc"),
    ("Classif: tratamento tributário", "https://portalunico.siscomex.gov.br/classif/"),
)

# chave, rótulo PT, rótulo EN, grupo, tipo, valor inicial
CAMPOS_IMPORTACAO = (
    ("frete_origem_usd", "Frete interno na origem (USD/lote)", "Origin inland freight (USD/lot)", "frete", "number", 0.0),
    ("despacho_miami_usd", "Despacho de exportação — total (USD/lote)", "Export clearance — total (USD/lot)", "frete", "number", 0.0),
    ("despacho_na_va_usd", "Despacho de exportação — parcela na VA (USD/lote)", "Export clearance — share in customs value (USD/lot)", "frete", "number", 0.0),
    ("locacao_rap_usd", "Locação ULD/RAP — total (USD/lote)", "ULD/RAP rental — total (USD/lot)", "frete", "number", 0.0),
    ("locacao_na_va_usd", "Locação ULD/RAP — parcela na VA (USD/lote)", "ULD/RAP rental — share in customs value (USD/lot)", "frete", "number", 0.0),
    ("valoracao_revisada", "Revisei documentalmente as parcelas incluídas na VA", "I reviewed the documented customs-value allocation", "frete", "checkbox", False),
    ("modo_seguro", "Como informar o seguro?", "Insurance input method", "frete", "select", "Percentual"),
    ("seguro_total_usd", "Seguro porta a porta total (USD/lote)", "Total door-to-door insurance (USD/lot)", "frete", "number", 0.0),
    ("seguro_apos_usd", "Seguro após local de importação (USD/lote)", "Insurance after import location (USD/lot)", "frete", "number", 0.0),
    ("acrescimos_va_usd", "Outros acréscimos à VA (USD/lote)", "Other customs-value additions (USD/lot)", "frete", "number", 0.0),
    ("custo_anvisa", "Taxa ANVISA/TFVS (R$/lote)", "ANVISA/TFVS fee (BRL/lot)", "importacao", "number", 0.0),
    ("custo_hub", "Armazenagem no hub de Guarulhos (R$/lote/período)", "Guarulhos hub storage (BRL/lot/period)", "importacao", "number", 0.0),
    ("outras_despesas_aduaneiras", "Outras despesas aduaneiras — total (R$/lote)", "Other customs expenses — total (BRL/lot)", "importacao", "number", 0.0),
    ("cbs_ibs_recolher", "CBS/IBS efetivamente a recolher (R$/lote; zero na Duimp/2026)", "CBS/IBS actually payable (BRL/lot; zero for Duimp/2026)", "importacao", "number", 0.0),
    ("iof_cambio", "IOF-câmbio efetivamente devido na importação (R$/lote)", "IOF on import exchange actually due (BRL/lot)", "importacao", "number", 0.0),
)

ROTULOS_ALINHADOS = {
    "preco_fob_base": ("Preço da mercadoria na fatura (USD/unidade)", "Goods invoice price (USD/unit)"),
    "frete_usd": ("Frete internacional até o Brasil (USD/lote)", "International freight to Brazil (USD/lot)"),
    "seguro_pct": ("Seguro estimado (% mercadoria + fretes)", "Estimated insurance (% goods + freight)"),
    "ajustes_aduaneiros_brl": ("Ajustes adicionais à VA (R$/lote; não repetir acréscimos USD)", "Additional customs adjustments (BRL/lot; do not repeat USD additions)"),
    "frete_interno_brl": ("Frete GRU → hub Guarulhos (R$/lote)", "GRU → Guarulhos hub freight (BRL/lot)"),
    "custo_armazenagem": ("Armazenagem no terminal até desembaraço (R$/lote)", "Terminal storage through customs clearance (BRL/lot)"),
    "custo_capatazia": ("Capatazia nacional destacada (R$/lote)", "Separately identified Brazilian handling (BRL/lot)"),
    "despesas_na_base_icms": ("Outras parcelas na base do ICMS — já lançadas nos custos (R$/lote)", "Other ICMS base additions — already recorded as costs (BRL/lot)"),
    "aliq_cofins": ("COFINS-Importação total, com adicional aplicável (%)", "Total import COFINS including applicable surcharge (%)"),
    "preco_fob_p2": ("Preço da mercadoria na fatura (USD/unidade) — produto 2", "Goods invoice price (USD/unit) — product 2"),
}

ROTULOS_ANTIGOS = {
    "Preço FOB da matriz (USD/kit)": ROTULOS_ALINHADOS["preco_fob_base"][0],
    "Preço FOB da matriz (USD por kit)": ROTULOS_ALINHADOS["preco_fob_base"][0],
    "Preço FOB (USD por unidade)": ROTULOS_ALINHADOS["preco_fob_p2"][0],
    "Frete internacional total (USD)": ROTULOS_ALINHADOS["frete_usd"][0],
    "Seguro (% sobre FOB + frete)": ROTULOS_ALINHADOS["seguro_pct"][0],
    "Ajustes ao valor aduaneiro (R$)": ROTULOS_ALINHADOS["ajustes_aduaneiros_brl"][0],
    "Frete interno até o estabelecimento (R$)": ROTULOS_ALINHADOS["frete_interno_brl"][0],
    "Frete interno (R$)": ROTULOS_ALINHADOS["frete_interno_brl"][0],
    "Armazenagem (R$)": ROTULOS_ALINHADOS["custo_armazenagem"][0],
    "Capatazia / terminal (R$)": ROTULOS_ALINHADOS["custo_capatazia"][0],
    "Outras despesas efetivamente incluídas na base do ICMS (R$)": ROTULOS_ALINHADOS["despesas_na_base_icms"][0],
    "Cofins-importação (%)": ROTULOS_ALINHADOS["aliq_cofins"][0],
}


def valorar_lote(mercadoria_usd, frete_usd, seguro_pct, ajustes_brl, cambio, componentes):
    for key, _, _, _, kind, _ in CAMPOS_IMPORTACAO:
        if kind == "number" and (not isfinite(componentes[key]) or componentes[key] < 0):
            raise ValueError(f"{key}: informe um valor finito e não negativo.")
    origem = componentes["frete_origem_usd"]
    despacho = componentes["despacho_miami_usd"]
    locacao = componentes["locacao_rap_usd"]
    despacho_va = componentes["despacho_na_va_usd"]
    locacao_va = componentes["locacao_na_va_usd"]
    seguro_total = (
        componentes["seguro_total_usd"] if componentes["modo_seguro"] == "Valor informado"
        else (mercadoria_usd + origem + frete_usd) * seguro_pct
    )
    seguro_pos = componentes["seguro_apos_usd"]
    if despacho_va > despacho or locacao_va > locacao:
        raise ValueError("A parcela incluída na VA não pode exceder o custo total de despacho/locação.")
    if seguro_pos > seguro_total:
        raise ValueError("O seguro após o local de importação não pode exceder o seguro total.")
    parcelas = [
        ("Mercadoria — valor da fatura", mercadoria_usd),
        ("Frete interno na origem", origem),
        ("Frete internacional até o Brasil", frete_usd),
        ("Seguro até o local de importação", seguro_total - seguro_pos),
        ("Despacho de exportação — parcela na VA", despacho_va),
        ("Locação ULD/RAP — parcela na VA", locacao_va),
        ("Outros acréscimos à VA", componentes["acrescimos_va_usd"] + ajustes_brl / cambio),
    ]
    va = sum(valor for _, valor in parcelas) * cambio
    fora_va = [
        ("Despacho de exportação — fora da VA", (despacho - despacho_va) * cambio),
        ("Locação ULD/RAP — fora da VA", (locacao - locacao_va) * cambio),
        ("Seguro após local de importação", seguro_pos * cambio),
    ]
    return va, [(nome, valor * cambio) for nome, valor in parcelas], fora_va


def completar_campos_importacao(fields):
    """Completa metadados antigos e atuais sem trocar valores já salvos."""
    from standalone_html3 import field

    obsolete = {"aliq_cbs", "aliq_ibs", "multiplo_base_cbs_ibs"}
    fields = [dict(item) for item in fields if item["key"].removesuffix("_p2") not in obsolete]
    by_key = {item["key"]: item for item in fields}
    for suffix in ("", "_p2"):
        for key, pt, en, group, kind, default in CAMPOS_IMPORTACAO:
            full_key = key + suffix
            if full_key not in by_key:
                group_pt, group_en = (
                    ("1. Valor aduaneiro — custos internacionais", "1. Customs value — international costs")
                    if group == "frete" else
                    ("2. Landed cost bruto — tributos e despesas até o hub", "2. Gross landed cost — taxes and expenses through the hub")
                )
                item = field(full_key, pt, en, default, group_pt, group_en, kind=kind, minimum=0 if kind == "number" else None)
                fields.append(item)
                by_key[full_key] = item
        by_key["modo_seguro" + suffix]["options"] = [
            ("Percentual", "Percentual estimado", "Estimated percentage"),
            ("Valor informado", "Valor da apólice", "Policy amount"),
        ]
    for item in fields:
        key = item["key"]
        suffix = "_p2" if key.endswith("_p2") else ""
        base = key[:-3] if suffix else key
        aligned_key = key if key in ROTULOS_ALINHADOS else base
        if aligned_key in ROTULOS_ALINHADOS:
            pt, en = ROTULOS_ALINHADOS[aligned_key]
            item["label"] = {"pt": pt, "en": en}
        if base.startswith("credita_"):
            item["group"] = {"pt": "3. Créditos — somente na projeção de vendas", "en": "3. Credits — sales projection only"}
        elif base in {row[0] for row in CAMPOS_IMPORTACAO} or item["group"]["pt"] in (
            "Embalagem e frete", "Tributos e despesas de importação",
        ):
            is_freight = base in {row[0] for row in CAMPOS_IMPORTACAO if row[3] == "frete"} or item["group"]["pt"] == "Embalagem e frete"
            item["group"] = {
                "pt": ("1. Valor aduaneiro — custos internacionais" if is_freight else "2. Landed cost bruto — tributos e despesas até o hub") + (" — produto 2" if suffix else ""),
                "en": ("1. Customs value — international costs" if is_freight else "2. Gross landed cost — taxes and expenses through the hub") + (" — product 2" if suffix else ""),
            }
    order = {
        "produto": 0, "frete": 1, "importacao": 2, "creditos": 3,
    }

    def fase(item):
        group = item["group"]["pt"]
        if group.startswith("1. "):
            return (order["frete"], group)
        if group.startswith("2. "):
            return (order["importacao"], group)
        if group.startswith("3. "):
            return (order["creditos"], group)
        if group in ("Produto, volume e câmbio", "Produto 2 (NCM diferente)"):
            return (order["produto"], group)
        return (4, "")

    return sorted(fields, key=fase)
