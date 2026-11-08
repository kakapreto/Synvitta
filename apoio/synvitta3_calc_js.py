from __future__ import annotations

import json

from synvitta3_i18n import _REVERSE_TRANSLATIONS


def _statement_pt_map() -> dict[str, str]:
    extra = {
        "Below-net-income allocation; not an operating expense.": "Alocação abaixo do lucro líquido; não é despesa operacional.",
        "Brazil subsidiary net income × scenario-specific parent ownership share.": "Lucro líquido da subsidiária brasileira × participação da matriz específica do cenário.",
    }
    return {**_REVERSE_TRANSLATIONS, **extra}


def synvitta3_calculation_js() -> str:
    return r'''function calculate(v, lang) {
    const pt = lang === "pt";
    const n = key => Number(v[key] || 0);
    const s = key => String(v[key] ?? "");
    const label = (ptText, enText) => pt ? ptText : enText;
    const statementPt = __STATEMENT_PT__;
    const tr = text => {
        if (!pt) return text;
        if (statementPt[text] !== undefined) return statementPt[text];
        let result = text;
        Object.keys(statementPt).filter(k => k.length >= 16).sort((a, b) => b.length - a.length)
            .forEach(k => { result = result.split(k).join(statementPt[k]); });
        return result;
    };
    const exchange = Math.max(0.01, n("cambio"));
    const currency = s("moeda_relatorio") === "BRL" ? "BRL" : "USD";
    const fx = currency === "USD" ? 1 / exchange : 1;
    const symbol = currency === "USD" ? "US$" : (pt ? "R$" : "BRL");
    const unitSymbol = currency === "USD" ? "USD" : (pt ? "R$" : "BRL");
    const numberFormat = (value, digits = 2) => new Intl.NumberFormat(pt ? "pt-BR" : "en-US", {
        minimumFractionDigits: digits, maximumFractionDigits: digits
    }).format(Number(value) || 0);
    const money = value => symbol + " " + numberFormat((Number(value) || 0) * fx);
    const brl = value => (pt ? "R$ " : "BRL ") + numberFormat(value);
    const usd = value => "USD " + numberFormat(value);
    const pct = value => numberFormat(value) + "%";
    const rate = key => n(key) / 100;
    const quantity = Math.max(1, n("quantidade"));
    const productTwoOn = Boolean(v.p2_ativo);
    const quantityP2 = productTwoOn ? Math.max(1, n("quantidade_p2")) : 0;
    const totalQuantity = quantity + quantityP2;
    const sold1 = Math.max(0, Math.min(quantity, n("quantidade_vendida")));
    const sold2 = Math.max(0, Math.min(quantity, n("quantidade_vendida_c2")));
    const soldP2B = productTwoOn ? Math.max(0, Math.min(quantityP2, n("quantidade_vendida_c2_p2"))) : 0;
    const soldP2 = productTwoOn ? Math.max(0, Math.min(quantityP2, n("quantidade_vendida_p2"))) : 0;
    const period = Math.max(1, n("meses_operacao"));
    function logisticsFor(sfx, qty) {
        const k = key => key + sfx;
        const boxes = Math.ceil(qty / Math.max(1, n(k("kits_por_volume"))));
        const cube = boxes * n(k("comprimento")) * n(k("largura")) * n(k("altura"));
        const volumeM3 = cube / 1000000;
        const gross = n(k("peso_bruto_total"));
        const chargeableWeight = Math.max(gross, cube / Math.max(1, n(k("divisor_volumetrico"))));
        const wm = Math.max(volumeM3, gross / 1000);
        const mode = s(k("calculo_frete"));
        let freight = n(k("frete_usd"));
        if (mode === "Tarifa marítima por W/M") freight = n(k("tarifa_wm")) * wm;
        else if (mode === "Tarifa por kg taxável") freight = n(k("tarifa_frete_kg")) * chargeableWeight;
        else if (mode === "Tarifa por m³") freight = n(k("tarifa_m3")) * volumeM3;
        return {qty, boxes, volumeM3, gross, chargeableWeight, freight, modal: s(k("modal"))};
    }
    const logisticsP1 = logisticsFor("", quantity);
    const logisticsP2 = productTwoOn ? logisticsFor("_p2", quantityP2) : null;
    const freightUsd = logisticsP1.freight;
    const freightUsdP2 = logisticsP2 ? logisticsP2.freight : 0;
    const dispatchCosts = [
        ["Armazenagem", "Warehousing", "custo_armazenagem"],
        ["Capatazia / terminal", "Cargo handling / terminal", "custo_capatazia"],
        ["Despachante aduaneiro", "Customs broker", "custo_despachante"],
        ["Taxa Siscomex", "Siscomex fee", "taxa_siscomex"],
        ["Taxas portuárias / aeroportuárias", "Port / airport fees", "taxas_terminal"],
        ["Honorários / agente de carga", "Forwarder / freight agent fees", "honorarios_agente_carga"],
        ["Licenças, análise e inspeção", "Licenses, testing, and inspection", "licencas_inspecao"],
        ["Outras despesas de importação", "Other import expenses", "outras_despesas_importacao"],
        ["Taxa ANVISA/TFVS", "ANVISA/TFVS fee", "custo_anvisa"],
        ["Armazenagem no hub de Guarulhos", "Guarulhos hub storage", "custo_hub"],
        ["Outras despesas aduaneiras", "Other customs expenses", "outras_despesas_aduaneiras"]
    ];
    const dispatchCostsP2 = dispatchCosts.map(row => [row[0], row[1], row[2] + "_p2"]);
    function calculateImport(fobPerKit, o) {
        const k = key => key + o.sfx;
        const rt = key => rate(k(key));
        for (const key of ["frete_origem_usd", "despacho_miami_usd", "despacho_na_va_usd",
            "locacao_rap_usd", "locacao_na_va_usd", "seguro_total_usd", "seguro_apos_usd",
            "acrescimos_va_usd", "iof_cambio", "cbs_ibs_recolher", "custo_anvisa",
            "custo_hub", "outras_despesas_aduaneiras"]) {
            if (!Number.isFinite(n(k(key))) || n(k(key)) < 0) {
                throw new Error(label("Informe valores finitos e não negativos: ", "Enter finite nonnegative values: ") + k(key));
            }
        }
        const fobUsd = fobPerKit * o.qty;
        const freightBrl = o.freightUsd * exchange;
        const originFreight = n(k("frete_origem_usd"));
        const clearance = n(k("despacho_miami_usd"));
        const rental = n(k("locacao_rap_usd"));
        const clearanceInVa = n(k("despacho_na_va_usd"));
        const rentalInVa = n(k("locacao_na_va_usd"));
        const insuranceTotal = s(k("modo_seguro")) === "Valor informado"
            ? n(k("seguro_total_usd")) : (fobUsd + originFreight + o.freightUsd) * rt("seguro_pct");
        const insuranceAfter = n(k("seguro_apos_usd"));
        if (clearanceInVa > clearance || rentalInVa > rental) {
            throw new Error(label("A parcela na VA excede o custo total de despacho/locação.", "The customs-value allocation exceeds total clearance/rental cost."));
        }
        if (insuranceAfter > insuranceTotal) {
            throw new Error(label("O seguro após a importação excede o seguro total.", "Post-import insurance exceeds total insurance."));
        }
        const customsComposition = [
            ["Mercadoria — valor da fatura", "Goods — invoice value", fobUsd * exchange],
            ["Frete interno na origem", "Origin inland freight", originFreight * exchange],
            ["Frete internacional até o Brasil", "International freight to Brazil", freightBrl],
            ["Seguro até o local de importação", "Insurance through import location", (insuranceTotal - insuranceAfter) * exchange],
            ["Despacho de exportação — parcela na VA", "Export clearance — share in customs value", clearanceInVa * exchange],
            ["Locação ULD/RAP — parcela na VA", "ULD/RAP rental — share in customs value", rentalInVa * exchange],
            ["Outros acréscimos à VA", "Other customs-value additions", n(k("acrescimos_va_usd")) * exchange + n(k("ajustes_aduaneiros_brl"))]
        ];
        const customsValue = customsComposition.reduce((sum, row) => sum + row[2], 0);
        customsComposition.push(["Valor aduaneiro", "Customs value", customsValue]);
        const excludedComposition = [
            ["Despacho de exportação — fora da VA", "Export clearance — outside customs value", (clearance - clearanceInVa) * exchange],
            ["Locação ULD/RAP — fora da VA", "ULD/RAP rental — outside customs value", (rental - rentalInVa) * exchange],
            ["Seguro após local de importação", "Insurance after import location", insuranceAfter * exchange]
        ];
        const excludedCosts = excludedComposition.reduce((sum, row) => sum + row[2], 0);
        const det = o.detailed;
        if (det && (rt("aliq_icms") < 0 || rt("aliq_icms") >= 1)) {
            throw new Error(label("O ICMS deve ser de 0% a menos de 100%.", "ICMS must be at least 0% and below 100%."));
        }
        const ii = det ? customsValue * rt("aliq_ii") : 0;
        const ipi = det ? (customsValue + ii) * rt("aliq_ipi") : 0;
        const pisImport = det ? customsValue * rt("aliq_pis") : 0;
        const cofinsImport = det ? customsValue * rt("aliq_cofins") : 0;
        const cbsIbsImport = det ? n(k("cbs_ibs_recolher")) : 0;
        const afrmm = det && o.modal === "Marítimo" ? freightBrl * rt("aliq_afrmm") : 0;
        const icmsBaseBefore = customsValue + ii + ipi + pisImport + cofinsImport + afrmm + (det ? n(k("antidumping_brl")) + n(k("taxa_siscomex")) + n(k("despesas_na_base_icms")) + n(k("iof_cambio")) : 0);
        const icmsBase = det && rt("aliq_icms") < 1 ? icmsBaseBefore / (1 - rt("aliq_icms")) : 0;
        const icms = icmsBase * rt("aliq_icms");
        const dispatchTotal = det ? o.dispatch.reduce((sum, row) => sum + n(row[2]), 0) : 0;
        const importTaxes = det
            ? ii + ipi + pisImport + cofinsImport + cbsIbsImport + icms + afrmm + n(k("antidumping_brl")) + n(k("iof_cambio"))
            : n(k("custo_importacao_consolidado_brl"));
        const credits = det
            ? (v[k("credita_ipi")] ? ipi : 0) + (v[k("credita_pis")] ? pisImport : 0) + (v[k("credita_cofins")] ? cofinsImport : 0)
                + (v[k("credita_cbs_ibs")] ? cbsIbsImport : 0) + (v[k("credita_icms")] ? icms : 0)
            : 0;
        const domesticFreight = n(k("frete_interno_brl"));
        const outlay = customsValue + excludedCosts + importTaxes + dispatchTotal + domesticFreight;
        const inventoryCost = Math.max(outlay - credits, 0);
        const composition = det
            ? [
                ["Valor aduaneiro", "Customs value", customsValue],
                ...excludedComposition,
                ["II", "Import duty (II)", ii], ["IPI-importação", "Import IPI", ipi],
                ["PIS-importação", "Import PIS", pisImport], ["Cofins-importação", "Import Cofins", cofinsImport],
                ["CBS/IBS efetivamente a recolher", "CBS/IBS actually payable", cbsIbsImport],
                ["IOF-câmbio na importação", "IOF on import exchange", n(k("iof_cambio"))],
                ["ICMS-importação", "Import ICMS", icms], ["AFRMM", "Merchant Marine Tax (AFRMM)", afrmm],
                ["Antidumping / medidas compensatórias", "Anti-dumping / countervailing duties", n(k("antidumping_brl"))],
                ...o.dispatch.map(row => [row[0], row[1], n(row[2])]),
                ["Frete interno", "Domestic freight", domesticFreight],
                ["Landed cost bruto até o hub", "Gross landed cost through the hub", outlay]
            ]
            : [
                ["Valor aduaneiro", "Customs value", customsValue],
                ...excludedComposition,
                ["Tributos e despesas aduaneiras consolidados", "Consolidated import taxes and customs expenses", importTaxes],
                ["Frete interno", "Domestic freight", domesticFreight],
                ["Landed cost bruto até o hub", "Gross landed cost through the hub", outlay]
            ];
        return {customsValue, importTaxes, dispatchTotal, credits, inventoryCost, outlay, composition, customsComposition};
    }
    const productOneImport = {
        sfx: "", qty: quantity, freightUsd, detailed: s("modo_custos_importacao") === "Detalhado",
        modal: s("modal"), dispatch: dispatchCosts
    };
    const productTwoImport = {
        sfx: "_p2", qty: quantityP2, freightUsd: freightUsdP2,
        detailed: s("modo_custos_importacao_p2") === "Detalhado", modal: s("modal_p2"), dispatch: dispatchCostsP2
    };
    const importA = calculateImport(n("preco_fob_base"), productOneImport);
    const importB = calculateImport(n("preco_fob_c2"), productOneImport);
    const importP2 = productTwoOn ? calculateImport(n("preco_fob_p2"), productTwoImport) : null;
    const importP2B = productTwoOn ? calculateImport(n("preco_fob_c2_p2"), productTwoImport) : null;
    const salesTaxRate = s("modo_tributos_venda") === "Detalhado"
        ? rate("aliq_icms_venda") + rate("aliq_pis_venda") + rate("aliq_cofins_venda") + rate("aliq_outros_venda")
        : rate("aliq_venda_consolidada");
    const salesTaxRateP2 = s("modo_tributos_venda_p2") === "Consolidado"
        ? rate("aliq_venda_consolidada_p2")
        : rate("aliq_icms_venda_p2") + rate("aliq_pis_venda_p2") + rate("aliq_cofins_venda_p2") + rate("aliq_outros_venda_p2");
    const monthlyOpex = s("modo_opex") === "Detalhado"
        ? ["opex_pessoal", "opex_aluguel", "opex_utilidades", "opex_servicos_profissionais", "opex_comercial_marketing", "opex_sistemas", "opex_seguros", "opex_depreciacao", "opex_administrativo", "opex_outros"].reduce((sum, key) => sum + n(key), 0)
        : n("opex_consolidado_mensal");
    const isPresumedProfit = s("regime_tributario") === "Lucro Presumido";
    const productOneName = label("Produto 1", "Product 1");
    const productTwoName = (s("nome_p2").trim() === "Produto 2" ? "" : s("nome_p2").trim()) || label("Produto 2", "Product 2");
    function productResult(name, ncm, qty, sold, price, fobPerKit, manufacturingPerKit, importData, discount, taxRate, operatorKey) {
        const cogs = importData.inventoryCost / qty * sold;
        const grossRevenue = price * sold;
        const commercialRevenue = Math.max(grossRevenue - discount, 0);
        const salesTaxes = commercialRevenue * taxRate;
        const netRevenue = commercialRevenue - salesTaxes;
        const variableOperator = netRevenue * rate(operatorKey);
        return {
            name, ncm, qty, sold, price, importData, cogs, grossRevenue, commercialRevenue, salesTaxes, netRevenue,
            variableOperator, discount: Math.min(discount, grossRevenue),
            fobUsd: fobPerKit * qty,
            manufacturingCost: manufacturingPerKit * qty * exchange,
            contribution: netRevenue - cogs - variableOperator
        };
    }
    const sum = (items, key) => items.reduce((total, item) => total + item[key], 0);
    function calculateScenario(fobPerKit, sold, pricePerKit, opexFactor, parentShare, importData, p2) {
        const products = [productResult(
            productOneName, s("ncm_codigo"), quantity, sold, pricePerKit, fobPerKit, n("custo_fabricacao_usd"),
            importData,             n("devolucoes_descontos"), salesTaxRate, "operador_pct"        )];
        if (productTwoOn) {
            products.push(productResult(
                productTwoName, s("ncm_p2"), quantityP2, p2.sold, p2.price, p2.fob,
                n("custo_fabricacao_usd_p2"), p2.importData,                 n("devolucoes_descontos_p2"), salesTaxRateP2, "operador_pct_p2"            ));
        }
        const fobUsd = sum(products, "fobUsd");
        const soldTotal = sum(products, "sold");
        const cogs = sum(products, "cogs");
        const grossRevenue = sum(products, "grossRevenue");
        const commercialRevenue = sum(products, "commercialRevenue");
        const salesTaxes = sum(products, "salesTaxes");
        const netRevenue = sum(products, "netRevenue");
        const discounts = sum(products, "discount");
        const grossProfit = netRevenue - cogs;
        const opex = monthlyOpex * period * opexFactor;
        const variableOperator = sum(products, "variableOperator");
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
        const manufacturingCost = sum(products, "manufacturingCost");
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
        
        // DRE detalhada com seções
        const dreReceita = [
            ["Receita Bruta", "Gross Revenue", grossRevenue],
            ["(-) Devoluções e Descontos", "(-) Returns and Discounts", -discounts],
            ["(=) Receita Comercial Tributável", "(=) Taxable Commercial Revenue", commercialRevenue],
            ["(-) Tributos sobre Vendas", "(-) Sales Taxes", -salesTaxes],
            ["(=) Receita Líquida", "(=) Net Revenue", netRevenue]
        ];
        
        // Detalhamento dos tributos sobre vendas
        const salesTaxesDetail = s("modo_tributos_venda") === "Detalhado" ? [
            ["ICMS sobre vendas", "ICMS on sales", netRevenue * rate("aliq_icms_venda")],
            ["PIS sobre vendas", "PIS on sales", netRevenue * rate("aliq_pis_venda")],
            ["Cofins sobre vendas", "Cofins on sales", netRevenue * rate("aliq_cofins_venda")],
            ["Outros tributos/CBS/IBS", "Other taxes/CBS/IBS", netRevenue * rate("aliq_outros_venda")]
        ] : [];
        
        const dreCmv = [
            ["Custo de Aquisição do Estoque", "Inventory Acquisition Cost", cogs],
            ["(-) Estoque Final", "(-) Ending Inventory", 0],
            ["(=) CMV do Período", "(=) COGS for the Period", cogs]
        ];
        
        const dreDespesas = [
            ["Operação Variável", "Variable Operations", variableOperator],
            ["Opex Fixo do Período", "Fixed Opex for the Period", opex],
            ["Juros e Despesas Financeiras", "Interest and Financial Expenses", n("juros_brl")],
            ["(=) Total Despesas Operacionais", "(=) Total Operating Expenses", variableOperator + opex + n("juros_brl")]
        ];
        
        const dreOperacional = [
            ["Receita Líquida", "Net Revenue", netRevenue],
            ["(-) CMV", "(-) COGS", -cogs],
            ["(-) Despesas Operacionais", "(-) Operating Expenses", -(variableOperator + opex + n("juros_brl"))],
            ["(=) Lucro Operacional", "(=) Operating Profit", operatingProfit]
        ];
        
        const dreImpostos = isPresumedProfit ? [
            ["Resultado Antes de IR/CSLL", "Profit Before IR/CSLL", profitBeforeTax],
            ["(-) IRPJ Comercial (1,20%)", "(-) Commercial IRPJ (1.20%)", -irpj],
            ["(-) Adicional de IRPJ", "(-) Additional IRPJ", -additionalIrpj],
            ["(-) CSLL Comercial (1,08%)", "(-) Commercial CSLL (1.08%)", -csll],
            ["(=) Total IRPJ + CSLL", "(=) Total IRPJ + CSLL", -brazilTax]
        ] : [
            ["Resultado Antes de IR/CSLL", "Profit Before IR/CSLL", profitBeforeTax],
            ["(-) IR/CSLL sobre Lucro (32%)", "(-) IR/CSLL on Profit (32%)", -brazilTax],
            ["(=) Total IR/CSLL", "(=) Total IR/CSLL", -brazilTax]
        ];
        
        const dreLiquido = [
            ["Lucro Operacional", "Operating Profit", operatingProfit],
            ["(-) IRPJ + CSLL", "(-) IRPJ + CSLL", -brazilTax],
            ["(=) Lucro Líquido Brasil", "(=) Brazil Net Profit", netBrazil]
        ];
        
        const dre = [
            ["Receita bruta", "Gross revenue", grossRevenue],
            ["Devoluções, abatimentos e descontos", "Returns, allowances, and discounts", -discounts],
            ["Tributos sobre vendas", "Sales taxes", -salesTaxes],
            ["Receita líquida", "Net revenue", netRevenue],
            ["Custo das mercadorias vendidas (CMV)", "Cost of goods sold (COGS)", -cogs],
            ["Lucro bruto", "Gross profit", grossProfit],
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
        const imports = products.map(product => product.importData);
        return {
            products, fobUsd, sold: soldTotal, pricePerKit: soldTotal ? grossRevenue / soldTotal : pricePerKit,
            grossRevenue, commercialRevenue, salesTaxes, netRevenue, grossProfit,
            cogs, opex, variableOperator, operatingProfit, profitBeforeTax, brazilTax, irpj,
            manufacturingCost, exportProfitBeforeTax, floridaTax, federalTax,
            additionalIrpj, csll, netBrazil, netExportProfit, parentBrazilProfit, branchRetained,
            dividendWithholding, remittanceCost, netRemittance, globalProfit, dre,
            dreReceita, salesTaxesDetail, dreCmv, dreDespesas, dreOperacional, dreImpostos, dreLiquido,
            customsValue: sum(imports, "customsValue"), outlay: sum(imports, "outlay"),
            credits: sum(imports, "credits"), inventoryCost: sum(imports, "inventoryCost"),
            exportMargin: fobUsd ? netExportProfit / (fobUsd * exchange) : 0,
            marginBrazil: netRevenue ? netBrazil / netRevenue : null,
            operatingMargin: netRevenue ? operatingProfit / netRevenue : null,
            markup: cogs > 0 ? grossRevenue / cogs : null,
            effectiveBrazilTax: commercialRevenue ? brazilTax / commercialRevenue : null
        };
    }
    const c1 = calculateScenario(n("preco_fob_base"), sold1, n("receita_por_kit"), 1, rate("participacao_matriz"), importA,
        {fob: n("preco_fob_p2"), sold: soldP2, price: n("receita_por_kit_p2"), importData: importP2});
    const c2 = calculateScenario(n("preco_fob_c2"), sold2, n("receita_por_kit_c2"), n("fator_opex_c2"), rate("participacao_matriz_c2"), importB,
        {fob: n("preco_fob_c2_p2"), sold: soldP2B, price: n("receita_por_kit_c2_p2"), importData: importP2B});
    const nullable = value => value === null ? null : value * 100;
    const comparisonData = [
        ["Preço FOB matriz", "Parent company FOB price", "USD/kit", c1.fobUsd / totalQuantity, c2.fobUsd / totalQuantity],
        ["FOB total", "Total FOB", "USD", c1.fobUsd, c2.fobUsd],
        ["Kits vendidos", "Kits sold", "kits", c1.sold, c2.sold],
        ["Preço bruto de venda Brasil", "Brazil gross selling price", "R$/kit", c1.pricePerKit, c2.pricePerKit],
        ["Fator de Opex local", "Local operating expense factor", "x", 1, n("fator_opex_c2")],
        ["Valor aduaneiro", "Customs value", "R$", c1.customsValue, c2.customsValue],
        ["Landed cost bruto até o hub", "Gross landed cost through the hub", "R$", c1.outlay, c2.outlay],
        ["Créditos estimados para fase posterior à venda", "Estimated credits for the sales phase", "R$", c1.credits, c2.credits],
        ["Custo líquido do estoque para cálculo do CMV", "Net inventory cost for COGS calculation", "R$", c1.inventoryCost, c2.inventoryCost],
        ["Custo líquido por kit para cálculo do CMV", "Net cost per kit for COGS calculation", "R$/kit", c1.inventoryCost / totalQuantity, c2.inventoryCost / totalQuantity],
        ["CMV do período", "Cost of goods sold for the period", "R$", c1.cogs, c2.cogs],
        ["Receita líquida Brasil", "Brazil net revenue", "R$", c1.netRevenue, c2.netRevenue],
        ["Lucro operacional", "Operating profit", "R$", c1.operatingProfit, c2.operatingProfit],
        ["Margem operacional / receita líquida", "Operating margin / net revenue", "%", nullable(c1.operatingMargin), nullable(c2.operatingMargin)],
        ["Lucro líquido Brasil", "Brazil net profit", "R$", c1.netBrazil, c2.netBrazil],
        ["Markup (receita bruta / CMV)", "Markup (gross revenue / COGS)", "x", c1.markup, c2.markup],
        ["IRPJ + CSLL calculados", "Calculated IRPJ + CSLL", "R$", c1.brazilTax, c2.brazilTax],
        ["Alíquota efetiva IRPJ + CSLL", "Effective IRPJ + CSLL rate", "%", nullable(c1.effectiveBrazilTax), nullable(c2.effectiveBrazilTax)],
        ["Margem líquida Brasil / receita líquida", "Brazil net margin / net revenue", "%", nullable(c1.marginBrazil), nullable(c2.marginBrazil)],
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
        ["Lucro global consolidado por kit", "Consolidated global profit per kit", "R$/kit", c1.globalProfit / totalQuantity, null]
    ];
    function display(value, unit) {
        if (value === null || value === undefined || Number.isNaN(Number(value))) return "N/A";
        if (unit === "USD" || unit === "USD/kit") return usd(value) + (unit === "USD/kit" ? "/kit" : "");
        if (unit === "kits") return numberFormat(value, 0);
        if (unit === "%") return pct(value);
        if (unit === "x") return numberFormat(value) + "x";
        return money(value) + (unit === "R$/kit" ? "/kit" : "");
    }
    const tableHeaders = pt
        ? ["Indicador", "Unidade", "Cenário 1", "Cenário 2"]
        : ["Metric", "Unit", "Scenario 1", "Scenario 2"];
    const compareRows = comparisonData.map(row => [
        pt ? row[0] : row[1],
        row[2].replace("R$", unitSymbol),
        display(row[3], row[2]),
        display(row[4], row[2])
    ]);
    const statementMoney = value => value < 0 ? `(${money(Math.abs(value))})` : money(value);
    const statementRows = (entries, base1, base2) => entries.map(
        ([account, value1, value2, logic, emphasis]) => [
            tr(account), statementMoney(value1), base1 ? pct(value1 / base1 * 100) : "N/A",
            statementMoney(value2), base2 ? pct(value2 / base2 * 100) : "N/A", tr(logic), emphasis
        ]
    );
    const parentStatementRows = statementRows([
        ["Gross Export Revenue (FOB)", c1.fobUsd * exchange, c2.fobUsd * exchange, "Kits sold × agreed FOB price per kit.", true],
        ["(-) Manufacturing Cost (COGS)", -c1.manufacturingCost, -c2.manufacturingCost, "Manufacturing cost per kit × kits sold.", false],
        ["Gross Profit (U.S.)", c1.fobUsd * exchange - c1.manufacturingCost, c2.fobUsd * exchange - c2.manufacturingCost, "Gross export revenue less manufacturing costs.", true],
        ["(-) Assigned Export OPEX", -n("opex_matriz_usd") * exchange, -n("opex_matriz_usd") * exchange, "U.S. parent overhead allocated to export operations.", false],
        ["Earnings Before Taxes (EBT)", c1.exportProfitBeforeTax, c2.exportProfitBeforeTax, "Gross profit less assigned export operating expenses.", true],
        ["(-) Florida State Income Tax", -c1.floridaTax, -c2.floridaTax, `Positive EBT × Florida rate (${pct(rate("aliq_fl") * 100)}) × apportionment (${pct(rate("rateio_fl") * 100)}).`, false],
        ["(-) U.S. Federal Income Tax", -c1.federalTax, -c2.federalTax, `Remaining positive EBT × federal rate (${pct(rate("aliq_federal_eua") * 100)}).`, false],
        ["U.S. Net Operating Profit", c1.netExportProfit, c2.netExportProfit, "EBT less estimated Florida and federal income taxes.", true],
        ["(+) Brazil Subsidiary Dividends (Gross)", c1.parentBrazilProfit, c2.parentBrazilProfit, "Brazil subsidiary net income × scenario-specific parent ownership share.", false],
        ["(-) U.S. Withholding Tax on Dividends", -c1.dividendWithholding, -c2.dividendWithholding, `Gross dividends × withholding rate (${pct(rate("retencao_dividendos") * 100)}).`, false],
        ["(-) Remittance Costs", -c1.remittanceCost, -c2.remittanceCost, `Post-withholding dividends × remittance fee (${pct(rate("custo_remessa") * 100)}).`, false],
        ["Net Brazil Dividend Received", c1.netRemittance, c2.netRemittance, "Gross dividends less withholding tax and remittance costs.", true],
        ["Total U.S. Parent Net Income", c1.netExportProfit + c1.netRemittance, c2.netExportProfit + c2.netRemittance, "Net U.S. operating profit plus net Brazil dividends received.", true]
    ], c1.fobUsd * exchange, c2.fobUsd * exchange);
    const subsidiaryStatementRows = statementRows([
        ["Gross Revenue", c1.grossRevenue, c2.grossRevenue, "Kits sold in Brazil × gross selling price per kit.", true],
        ["(-) Returns, Allowances and Discounts", -sum(c1.products, "discount"), -sum(c2.products, "discount"), "Configured sales returns, allowances and discounts.", false],
        ["Taxable Commercial Revenue", c1.commercialRevenue, c2.commercialRevenue, "Gross revenue less returns, allowances and discounts.", true],
        ["(-) Sales Taxes", -c1.salesTaxes, -c2.salesTaxes, "ICMS, PIS, COFINS and other configured sales taxes.", false],
        ["Net Revenue", c1.netRevenue, c2.netRevenue, "Taxable commercial revenue less sales taxes.", true],
        ["(-) Cost of Goods Sold (COGS)", -c1.cogs, -c2.cogs, "Gross landed cost less estimated credits allocated to the sales phase, for kits sold.", false],
        ["Gross Profit", c1.grossProfit, c2.grossProfit, "Net revenue less cost of goods sold.", true],
        ["(-) Variable Operating Expenses", -c1.variableOperator, -c2.variableOperator, "Configured variable operating and logistics costs.", false],
        ["(-) Fixed Operating Expenses (OPEX)", -c1.opex, -c2.opex, "Monthly fixed OPEX × period × scenario factor.", false],
        ["Operating Income (EBIT)", c1.operatingProfit, c2.operatingProfit, "Gross profit less variable and fixed operating expenses.", true],
        ["(-) Interest and Financial Expenses", -n("juros_brl"), -n("juros_brl"), "Configured interest and financial expenses for the period.", false],
        ["Earnings Before Income Taxes", c1.profitBeforeTax, c2.profitBeforeTax, "Operating income less interest and financial expenses.", true],
        ["(-) Corporate Income Taxes (IRPJ/CSLL)", -c1.brazilTax, -c2.brazilTax, "Estimated Brazilian income taxes under the selected tax regime.", false],
        ["Net Income - Brazil Subsidiary", c1.netBrazil, c2.netBrazil, "Earnings before income taxes less estimated corporate taxes.", true],
        ["(-) Dividends Allocated to U.S. Parent", -c1.parentBrazilProfit, -c2.parentBrazilProfit, "Below-net-income allocation; not an operating expense.", false],
        ["Net Income Retained Locally", c1.branchRetained, c2.branchRetained, "Brazil subsidiary net income less dividends allocated to the parent.", true]
    ], c1.grossRevenue, c2.grossRevenue);
    const compositionByName = new Map();
    for (const item of importA.composition) compositionByName.set(item[0], [item[1], item[2], null]);
    for (const item of importB.composition) {
        const row = compositionByName.get(item[0]) || [item[1], null, null];
        row[2] = item[2];
        compositionByName.set(item[0], row);
    }
    const importRows = Array.from(compositionByName.entries()).map(([name, row]) => [
        pt ? name : row[0],
        row[1] === null ? label("Não disponível", "Not available") : money(row[1]),
        row[2] === null ? label("Não disponível", "Not available") : money(row[2])
    ]);
    const marginText = value => value === null ? "N/A" : pct(value * 100);
    const productRows = [];
    [[label("Cenário 1", "Scenario 1"), c1], [label("Cenário 2", "Scenario 2"), c2]].forEach(([scenarioName, c]) => {
        c.products.forEach(p => productRows.push([
            scenarioName, p.name, p.ncm || "-", numberFormat(p.sold, 0), money(p.grossRevenue), money(p.netRevenue),
            money(p.importData.customsValue), money(p.importData.outlay), money(p.importData.inventoryCost), money(p.cogs),
            money(p.variableOperator), money(p.contribution), marginText(p.netRevenue ? p.contribution / p.netRevenue : null)
        ]));
        productRows.push([
            scenarioName, label("Consolidado", "Consolidated"), "-", numberFormat(c.sold, 0), money(c.grossRevenue), money(c.netRevenue),
            money(c.customsValue), money(c.outlay), money(c.inventoryCost), money(c.cogs), money(c.variableOperator),
            money(c.netRevenue - c.cogs - c.variableOperator),
            marginText(c.netRevenue ? (c.netRevenue - c.cogs - c.variableOperator) / c.netRevenue : null)
        ]);
    });
    const productTwoImportRows = productTwoOn
        ? importP2.composition.map((item, i) => [pt ? item[0] : item[1], money(item[2]), money(importP2B.composition[i][2])])
        : [];
    const execRows = [
        [label("1. Subsidiária controlada", "1. Controlled subsidiary"), c1, true],
        [label("2. Distribuidor Independente", "2. Independent distributor"), c2, false]
    ].map(([name, c, globalApplicable]) => [
        name, usd(c.fobUsd), money(c.netExportProfit), pct(c.exportMargin * 100),
        money(c.parentBrazilProfit), pct(c.grossRevenue ? c.parentBrazilProfit / c.grossRevenue * 100 : 0),
        money(c.netExportProfit + c.netRemittance), money(c.branchRetained),
        pct(c.grossRevenue ? c.branchRetained / c.grossRevenue * 100 : 0),
        globalApplicable ? money(c.globalProfit) : "N/A",
        globalApplicable ? money(c.globalProfit / totalQuantity) : "N/A",
        c.markup === null ? "N/A" : numberFormat(c.markup) + "x"
    ]);
    const brazilTaxPct = pct(c1.grossRevenue ? (c1.salesTaxes + c1.brazilTax) / c1.grossRevenue * 100 : 0);
    const productSuffix = productTwoOn ? label(" - consolidado", " - consolidated") : "";
    const tables = [
        {title: label("Comparativo Executivo - Dois Cenários", "Executive comparison - Two scenarios"), headers: [
            label("Cenário Societário / Comercial", "Business / ownership scenario"), label("FOB (USD)", "FOB (USD)"),
            label(`Lucro exportação (${symbol})`, `Export profit (${symbol})`), label("Margem exportação (%)", "Export margin (%)"),
            label(`Lucro matriz Brasil (${symbol})`, `Brazil parent profit (${symbol})`), label("Margem matriz (%)", "Parent margin (%)"),
            label(`Lucro total matriz (${symbol})`, `Total parent profit (${symbol})`), label(`Lucro filial/local (${symbol})`, `Branch/local profit (${symbol})`),
            label("Margem filial/local (%)", "Branch/local margin (%)"), label(`Lucro global (${symbol})`, `Global profit (${symbol})`),
            label(`Lucro global/kit (${symbol})`, `Global profit/kit (${symbol})`), label("Markup (x)", "Markup (x)")
        ], rows: execRows},
        {title: label("Comparação detalhada dos cenários", "Detailed scenario comparison") + productSuffix, headers: tableHeaders, rows: compareRows}
    ];
    const logisticsList = productTwoOn ? [logisticsP1, logisticsP2] : [logisticsP1];
    const logisticsSum = key => logisticsList.reduce((total, item) => total + item[key], 0);
    const modalName = value => pt ? value : ({"Marítimo": "Ocean freight", "Aéreo": "Air freight", "Rodoviário": "Road freight", "Outro": "Other"}[value] || value);
    const logisticsHeaders = [label("Item", "Item"), productOneName + " (NCM " + (s("ncm_codigo") || "-") + ")"];
    if (productTwoOn) logisticsHeaders.push(productTwoName + " (NCM " + (s("ncm_p2") || "-") + ")", label("Total consolidado", "Consolidated total"));
    const logisticsRow = (name, get, total) => [name, ...logisticsList.map(get), ...(productTwoOn ? [total] : [])];
    tables.push({
        title: label("Dados por produto: quantidade, peso e volume", "Data by product: quantity, weight, and volume"),
        headers: logisticsHeaders,
        rows: [
            logisticsRow(label("Unidades importadas", "Units imported"), x => numberFormat(x.qty, 0), numberFormat(logisticsSum("qty"), 0)),
            logisticsRow(label("Unidades vendidas (cenário 1)", "Units sold (scenario 1)"), (x, i) => numberFormat(c1.products[i].sold, 0), numberFormat(c1.sold, 0)),
            logisticsRow(label("Unidades vendidas (cenário 2)", "Units sold (scenario 2)"), (x, i) => numberFormat(c2.products[i].sold, 0), numberFormat(c2.sold, 0)),
            logisticsRow(label("Volumes (caixas)", "Volumes (cartons)"), x => numberFormat(x.boxes, 0), numberFormat(logisticsSum("boxes"), 0)),
            logisticsRow(label("Volume (m³)", "Volume (m³)"), x => numberFormat(x.volumeM3, 3), numberFormat(logisticsSum("volumeM3"), 3)),
            logisticsRow(label("Peso bruto (kg)", "Gross weight (kg)"), x => numberFormat(x.gross, 1), numberFormat(logisticsSum("gross"), 1)),
            logisticsRow(label("Peso taxável (kg)", "Chargeable weight (kg)"), x => numberFormat(x.chargeableWeight, 1), numberFormat(logisticsSum("chargeableWeight"), 1)),
            logisticsRow(label("Modal internacional", "International shipping mode"), x => modalName(x.modal), "-"),
            logisticsRow(label("Frete internacional (USD)", "International freight (USD)"), x => usd(x.freight), usd(logisticsSum("freight"))),
            logisticsRow(label(`Valor aduaneiro (${symbol})`, `Customs value (${symbol})`), (x, i) => money(c1.products[i].importData.customsValue), money(c1.customsValue)),
            logisticsRow(label(`Landed cost bruto até o hub (${symbol})`, `Gross landed cost through the hub (${symbol})`), (x, i) => money(c1.products[i].importData.outlay), money(c1.outlay)),
            logisticsRow(label(`Créditos estimados para fase posterior à venda (${symbol})`, `Estimated credits for the sales phase (${symbol})`), (x, i) => money(c1.products[i].importData.credits), money(c1.credits)),
            logisticsRow(label(`Custo líquido do estoque para CMV (${symbol})`, `Net inventory cost for COGS (${symbol})`), (x, i) => money(c1.products[i].importData.inventoryCost), money(c1.inventoryCost))
        ]
    });
    if (productTwoOn) {
        tables.push({
            title: label("Resultado por produto e consolidado", "Results by product and consolidated"),
            headers: [
                label("Cenário", "Scenario"), label("Produto", "Product"), "NCM", label("Kits vendidos", "Kits sold"),
                label(`Receita bruta (${symbol})`, `Gross revenue (${symbol})`), label(`Receita líquida (${symbol})`, `Net revenue (${symbol})`),
                label(`Valor aduaneiro (${symbol})`, `Customs value (${symbol})`), label(`Landed cost bruto (${symbol})`, `Gross landed cost (${symbol})`),
                label(`Custo líquido para CMV (${symbol})`, `Net cost for COGS (${symbol})`),
                label(`CMV (${symbol})`, `COGS (${symbol})`), label(`Operação variável (${symbol})`, `Variable operations (${symbol})`),
                label(`Margem de contribuição (${symbol})`, `Contribution margin (${symbol})`), label("Margem de contribuição (%)", "Contribution margin (%)")
            ],
            rows: productRows
        });
    }
    tables.push({
        title: label("Composição do valor aduaneiro", "Customs value breakdown") + ` - ${productOneName}`,
        headers: [label("Componente", "Component"), "BRL", "USD"],
        rows: importA.customsComposition.map(row => [pt ? row[0] : row[1], brl(row[2]), usd(row[2] / exchange)])
    });
    if (productTwoOn) tables.push({
        title: label("Composição do valor aduaneiro", "Customs value breakdown") + ` - ${productTwoName}`,
        headers: [label("Componente", "Component"), "BRL", "USD"],
        rows: importP2.customsComposition.map(row => [pt ? row[0] : row[1], brl(row[2]), usd(row[2] / exchange)])
    });
    for (const [name, data, qty] of [[productOneName, importA, quantity], ...(productTwoOn ? [[productTwoName, importP2, quantityP2]] : [])]) {
        tables.push({
            title: label("Composição do landed cost bruto até o hub", "Gross landed cost breakdown through the hub") + ` - ${name}`,
            headers: [label("Componente", "Component"), "BRL", "USD"],
            rows: [
                ...data.composition.map(row => [pt ? row[0] : row[1], brl(row[2]), usd(row[2] / exchange)]),
                [label("Landed cost bruto — por unidade", "Gross landed cost — per unit"), brl(data.outlay / qty), usd(data.outlay / qty / exchange)]
            ]
        });
    }
    tables.push({
        title: label("Composição da importação", "Import composition") + (productTwoOn ? ` - ${productOneName} (NCM ${s("ncm_codigo")})` : ""),
        headers: [label("Item", "Item"), label("Cenário 1", "Scenario 1"), label("Cenário 2", "Scenario 2")], rows: importRows
    });
    if (productTwoOn) {
        tables.push({
            title: label("Composição da importação", "Import composition") + ` - ${productTwoName} (NCM ${s("ncm_p2")})`,
            headers: [label("Item", "Item"), label("Cenário 1", "Scenario 1"), label("Cenário 2", "Scenario 2")], rows: productTwoImportRows
        });
    }
    const statementHeaders = [
        tr("Account Line Structure"), label("Cenário 1", "Scenario 1"), "%", label("Cenário 2", "Scenario 2"), "%",
        tr("Operational / Tax Logic")
    ];
    tables.push({
        title: tr("US Parent Company Profitability (Florida Matrix)"),
        headers: statementHeaders,
        rows: parentStatementRows.map(row => row.slice(0, 6)),
        style: "income-statement",
        emphasisRows: parentStatementRows.flatMap((row, index) => row[6] ? [index] : [])
    });
    tables.push({
        title: tr("Brazil Subsidiary P&L (Local Operation)"),
        headers: statementHeaders,
        rows: subsidiaryStatementRows.map(row => row.slice(0, 6)),
        style: "income-statement",
        emphasisRows: subsidiaryStatementRows.flatMap((row, index) => row[6] ? [index] : [])
    });
    return {
        importWarnings: [
            !v.valoracao_revisada ? label("Produto 1: valoração pendente de revisão documental; exclusão de ULD/despacho não é automática.", "Product 1: customs valuation pending documentary review; rental/clearance exclusion is not automatic.") : null,
            productTwoOn && !v.valoracao_revisada_p2 ? label("Produto 2: valoração pendente de revisão documental; exclusão de ULD/despacho não é automática.", "Product 2: customs valuation pending documentary review; rental/clearance exclusion is not automatic.") : null,
            s("uf_destino") !== "SP" ? label("ICMS: esta memória usa a orientação de SP. Valide a regra da UF do importador; o hub não define sozinho o destino fiscal.", "ICMS: this calculation uses São Paulo guidance. Check the importer's state rules; the hub alone does not determine tax jurisdiction.") : null,
            s("regime_tributario") === "Lucro Presumido" && (v.credita_pis || v.credita_cofins || (productTwoOn && (v.credita_pis_p2 || v.credita_cofins_p2))) ? label("Lucro presumido: créditos ordinários de PIS/COFINS-importação não devem ser presumidos. Revise as seleções.", "Presumed-profit regime: ordinary import PIS/COFINS credits must not be presumed. Review the selected credits.") : null
        ].filter(Boolean),
        summaryTitle: label("Resumo da DRE Operacional (Brasil)", "Brazil operating income statement summary") + productSuffix,
        summary: [
            {label: label(`Faturamento Bruto (${symbol})`, `Gross revenue (${symbol})`), value: money(c1.grossRevenue)},
            {label: label(`Acomodação / Operador (${symbol})`, `Logistics operator (${symbol})`), value: money(c1.variableOperator)},
            {label: label(`Landed Cost bruto até o hub (${symbol})`, `Gross landed cost through the hub (${symbol})`), value: money(c1.outlay)},
            {label: label(`Lucro Operacional (${symbol})`, `Operating profit (${symbol})`), value: money(c1.operatingProfit)},
            {label: label(`Impostos BR (${brazilTaxPct})`, `Brazil taxes (${brazilTaxPct})`), value: money(c1.salesTaxes + c1.brazilTax)},
            {label: label("Lucro Líquido BR", "Brazil net profit"), value: money(c1.netBrazil)},
            {label: label("Margem operacional", "Operating margin"), value: marginText(c1.operatingMargin)},
            {label: label("Margem líquida Brasil", "Brazil net margin"), value: marginText(c1.marginBrazil)},
            {label: label("Lucro global consolidado", "Consolidated global profit"), value: money(c1.globalProfit)}
        ],
        charts: [{
            title: label("Resultado por entidade e cenário", "Profit by entity and scenario"),
            categories: [label("Cenário 1", "Scenario 1"), label("Cenário 2", "Scenario 2")],
            series: [
                {label: label("Resultado retido na filial/local", "Profit retained by branch/local company"), color: "#4e9a72", values: [c1.branchRetained, c2.branchRetained], formatted: [money(c1.branchRetained), money(c2.branchRetained)]},
                {label: label("Remessa líquida à matriz", "Net remittance to parent company"), color: "#d78a36", values: [c1.netRemittance, c2.netRemittance], formatted: [money(c1.netRemittance), money(c2.netRemittance)]},
                {label: label("Lucro líquido da exportação da matriz", "Parent company net export profit"), color: "#2878a0", values: [c1.netExportProfit, c2.netExportProfit], formatted: [money(c1.netExportProfit), money(c2.netExportProfit)]},
                {label: label("Lucro global consolidado", "Consolidated global profit"), color: "#3b6f8f", values: [c1.globalProfit, null], formatted: [money(c1.globalProfit), "N/A"]}
            ]
        }],
        tables
    };
}'''.replace("__STATEMENT_PT__", json.dumps(_statement_pt_map(), ensure_ascii=False))
