from __future__ import annotations

import html
import json
import math
import os
from datetime import date
from pathlib import Path


def defaults_path() -> Path:
    configured = os.environ.get("SYNVITTA2_DEFAULTS_PATH")
    if configured:
        return Path(configured)
    local_app_data = Path(
        os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local")
    )
    return local_app_data / "Synvitta2" / "defaults.json"


def format_number(value: float, decimals: int = 2) -> str:
    return f"{value:,.{decimals}f}".replace(",", "_").replace(".", ",").replace("_", ".")


def format_brl(value: float) -> str:
    return f"R$ {format_number(value)}"


def format_usd(value: float) -> str:
    return f"US$ {format_number(value)}"


def format_percent(value: float) -> str:
    return f"{format_number(value)}%"


def build_report(profile: dict[str, object]) -> str:
    p = profile
    quantity = int(p["quantidade"])
    exchange = float(p["cambio"])
    period = float(p["meses_operacao"])

    def rate(key: str) -> float:
        return float(p.get(key, 0) or 0) / 100

    boxes = math.ceil(quantity / max(float(p["kits_por_volume"]), 1))
    volume_m3 = (
        boxes
        * float(p["comprimento"])
        * float(p["largura"])
        * float(p["altura"])
        / 1_000_000
    )
    volumetric_weight = (
        boxes
        * float(p["comprimento"])
        * float(p["largura"])
        * float(p["altura"])
        / max(float(p["divisor_volumetrico"]), 1)
    )
    chargeable_weight = max(float(p["peso_bruto_total"]), volumetric_weight)
    wm_units = max(volume_m3, float(p["peso_bruto_total"]) / 1000)
    freight_usd = float(p["frete_usd"])
    freight_method = str(p["calculo_frete"])
    if freight_method == "Tarifa marítima por W/M":
        freight_usd = float(p.get("tarifa_wm", 0)) * wm_units
    elif freight_method == "Tarifa por kg taxável":
        freight_usd = float(p.get("tarifa_frete_kg", 0)) * chargeable_weight
    elif freight_method == "Tarifa por m³":
        freight_usd = float(p.get("tarifa_m3", 0)) * volume_m3
    freight_brl = freight_usd * exchange
    import_is_detailed = p["modo_custos_importacao"] == "Detalhado"
    dispatch_keys = (
        "custo_armazenagem",
        "custo_capatazia",
        "custo_despachante",
        "taxa_siscomex",
        "taxas_terminal",
        "honorarios_agente_carga",
        "licencas_inspecao",
        "outras_despesas_importacao",
    )
    dispatch_total = sum(float(p.get(key, 0) or 0) for key in dispatch_keys)

    def calculate_scenario(
        fob_total_usd: float,
        sold: int,
        price_per_kit: float,
        parent_share: float,
        opex_factor: float = 1.0,
    ) -> dict[str, float]:
        insurance = (fob_total_usd + freight_usd) * exchange * rate("seguro_pct")
        customs_value = (
            fob_total_usd * exchange
            + freight_brl
            + insurance
            + float(p.get("ajustes_aduaneiros_brl", 0) or 0)
        )
        if import_is_detailed:
            ii = customs_value * rate("aliq_ii")
            ipi = (customs_value + ii + float(p.get("antidumping_brl", 0) or 0)) * rate("aliq_ipi")
            pis = customs_value * rate("aliq_pis")
            cofins = customs_value * rate("aliq_cofins")
            cbs_ibs = customs_value * float(p["multiplo_base_cbs_ibs"]) * (
                rate("aliq_cbs") + rate("aliq_ibs")
            )
            afrmm = freight_brl * rate("aliq_afrmm") if p["modal"] == "Marítimo" else 0.0
            icms_base = (
                customs_value
                + ii
                + ipi
                + pis
                + cofins
                + afrmm
                + float(p.get("antidumping_brl", 0) or 0)
                + float(p.get("despesas_na_base_icms", 0) or 0)
            )
            icms_base = icms_base / (1 - rate("aliq_icms")) if rate("aliq_icms") < 1 else 0.0
            icms = icms_base * rate("aliq_icms")
            import_taxes = (
                ii
                + ipi
                + pis
                + cofins
                + cbs_ibs
                + icms
                + afrmm
                + float(p.get("antidumping_brl", 0) or 0)
            )
            credits = (
                (ipi if p.get("credita_ipi") else 0.0)
                + (pis if p.get("credita_pis") else 0.0)
                + (cofins if p.get("credita_cofins") else 0.0)
                + (cbs_ibs if p.get("credita_cbs_ibs") else 0.0)
                + (icms if p.get("credita_icms") else 0.0)
            )
            dispatch = dispatch_total
        else:
            import_taxes = float(p.get("custo_importacao_consolidado_brl", 0) or 0)
            credits = 0.0
            dispatch = 0.0
        inventory_cost = max(
            customs_value
            + import_taxes
            + dispatch
            + float(p.get("frete_interno_brl", 0) or 0)
            - credits,
            0.0,
        )

        gross_revenue = price_per_kit * sold
        commercial_revenue = max(
            gross_revenue - float(p.get("devolucoes_descontos", 0) or 0), 0.0
        )
        if p["modo_tributos_venda"] == "Detalhado":
            sales_tax_rate = sum(
                rate(key)
                for key in (
                    "aliq_icms_venda",
                    "aliq_pis_venda",
                    "aliq_cofins_venda",
                    "aliq_outros_venda",
                )
            )
        else:
            sales_tax_rate = rate("aliq_venda_consolidada")
        net_revenue = commercial_revenue * (1 - sales_tax_rate)
        if p["modo_opex"] == "Detalhado":
            monthly_opex = sum(
                float(p.get(key, 0) or 0)
                for key in (
                    "opex_pessoal",
                    "opex_aluguel",
                    "opex_utilidades",
                    "opex_servicos_profissionais",
                    "opex_comercial_marketing",
                    "opex_sistemas",
                    "opex_seguros",
                    "opex_depreciacao",
                    "opex_administrativo",
                    "opex_outros",
                )
            )
        else:
            monthly_opex = float(p.get("opex_consolidado_mensal", 0) or 0)
        cogs = inventory_cost / quantity * sold
        operator_cost = net_revenue * rate("operador_pct")
        operating_profit = (
            net_revenue
            - cogs
            - operator_cost
            - monthly_opex * period * opex_factor
            - float(p.get("juros_brl", 0) or 0)
        )
        if p["regime_tributario"] == "Lucro Presumido":
            tax_br = (
                commercial_revenue * rate("aliq_irpj_faturamento")
                + max(
                    commercial_revenue * rate("base_presumida_irpj")
                    - float(p.get("limite_adicional_irpj_mensal", 0) or 0) * period,
                    0.0,
                )
                * rate("aliq_adicional_irpj")
                + commercial_revenue * rate("aliq_csll_faturamento")
            )
        else:
            tax_br = max(operating_profit, 0.0) * rate("aliq_ir_csll")
        net_brazil = operating_profit - tax_br
        parent_brazil = max(net_brazil, 0.0) * parent_share
        distributor = net_brazil - parent_brazil
        parent_margin = parent_brazil / gross_revenue * 100 if gross_revenue else 0.0
        distributor_margin = distributor / gross_revenue * 100 if gross_revenue else 0.0
        return {
            "customs_value": customs_value,
            "inventory_cost": inventory_cost,
            "gross_revenue": gross_revenue,
            "net_brazil": net_brazil,
            "parent_margin": parent_margin,
            "distributor_margin": distributor_margin,
        }

    fob_start = 100_000.0
    scenario1_fob = float(p["preco_fob_base"]) * quantity
    scenario1 = calculate_scenario(
        scenario1_fob,
        int(p["quantidade_vendida"]),
        float(p["receita_por_kit"]),
        rate("participacao_matriz"),
    )
    c2_sold = int(p["quantidade_vendida_c2"])
    c2_price = float(p["receita_por_kit_c2"])
    c2_share = rate("participacao_matriz_c2")
    c2_factor = float(p["fator_opex_c2"])

    def scenario2(fob_total_usd: float) -> dict[str, float]:
        return calculate_scenario(fob_total_usd, c2_sold, c2_price, c2_share, c2_factor)

    if scenario2(fob_start)["distributor_margin"] <= 0:
        raise ValueError("A margem da distribuidora já não é positiva no FOB inicial de US$ 100.000.")
    fob_high = fob_start
    while scenario2(fob_high)["distributor_margin"] > 0 and fob_high < 1e12:
        fob_high *= 2
    if scenario2(fob_high)["distributor_margin"] > 0:
        raise ValueError("Não foi possível encontrar o FOB que zera a margem da distribuidora.")

    low, high = fob_start, fob_high
    for _ in range(100):
        midpoint = (low + high) / 2
        if scenario2(midpoint)["distributor_margin"] > 0:
            low = midpoint
        else:
            high = midpoint
    fob_break_even = (low + high) / 2

    c2_start = scenario2(fob_start)
    c2_break_even = scenario2(fob_break_even)
    crossover: float | None = None
    if c2_start["distributor_margin"] >= scenario1["parent_margin"] >= c2_break_even["distributor_margin"]:
        low, high = fob_start, fob_break_even
        for _ in range(100):
            midpoint = (low + high) / 2
            if scenario2(midpoint)["distributor_margin"] > scenario1["parent_margin"]:
                low = midpoint
            else:
                high = midpoint
        crossover = (low + high) / 2

    def make_chart() -> str:
        width, height = 1120, 560
        left, right, top, bottom = 92, 36, 48, 82
        plot_width = width - left - right
        plot_height = height - top - bottom
        max_margin = max(scenario1["parent_margin"], c2_start["distributor_margin"])
        y_max = max(20.0, math.ceil(max_margin / 10) * 10)

        def x_pos(fob: float) -> float:
            return left + (fob - fob_start) / (fob_break_even - fob_start) * plot_width

        def y_pos(margin: float) -> float:
            return top + plot_height - margin / y_max * plot_height

        parts = [
            f'<svg viewBox="0 0 {width} {height}" role="img" aria-labelledby="chart-title chart-desc">',
            '<title id="chart-title">Sensibilidade da margem conforme FOB total</title>',
            '<desc id="chart-desc">Margem da matriz no cenário 1 constante e margem da distribuidora no cenário 2 decrescente até zero.</desc>',
        ]
        tick_step = 10 if y_max <= 100 else 20
        for tick in range(0, int(y_max) + 1, tick_step):
            y = y_pos(tick)
            parts.append(f'<line class="grid" x1="{left}" y1="{y:.1f}" x2="{width-right}" y2="{y:.1f}"/>')
            parts.append(f'<text class="axis-label" x="{left-14}" y="{y+5:.1f}" text-anchor="end">{tick}%</text>')
        for index in range(5):
            fob = fob_start + (fob_break_even - fob_start) * index / 4
            x = x_pos(fob)
            label = f"US$ {fob / 1_000_000:.2f} mi" if fob >= 1_000_000 else f"US$ {fob / 1_000:.0f} mil"
            parts.append(f'<line class="grid vertical" x1="{x:.1f}" y1="{top}" x2="{x:.1f}" y2="{height-bottom}"/>')
            parts.append(f'<text class="axis-label" x="{x:.1f}" y="{height-bottom+27}" text-anchor="middle">{label}</text>')
        parts.append(f'<line class="axis" x1="{left}" y1="{height-bottom}" x2="{width-right}" y2="{height-bottom}"/>')
        parts.append(f'<line class="axis" x1="{left}" y1="{top}" x2="{left}" y2="{height-bottom}"/>')
        parts.append(f'<text class="axis-title" x="{left+plot_width/2:.1f}" y="{height-18}" text-anchor="middle">FOB total da importação (USD)</text>')
        parts.append(f'<text class="axis-title" transform="translate(24 {top+plot_height/2:.1f}) rotate(-90)" text-anchor="middle">Margem líquida sobre faturamento bruto</text>')

        sample_count = 181
        sample_fobs = [fob_start + (fob_break_even - fob_start) * i / (sample_count - 1) for i in range(sample_count)]
        if crossover is not None:
            sample_fobs.append(crossover)
        sample_fobs = sorted(set(sample_fobs))
        scenario2_points = [
            f'{x_pos(fob):.1f},{y_pos(scenario2(fob)["distributor_margin"]):.1f}'
            for fob in sample_fobs
        ]
        parts.append(f'<path class="curve distributor" d="M{" L".join(scenario2_points)}"/>')
        y_matrix = y_pos(scenario1["parent_margin"])
        parts.append(f'<path class="curve parent" d="M{left},{y_matrix:.1f} L{width-right},{y_matrix:.1f}"/>')

        if crossover is not None:
            cx, cy = x_pos(crossover), y_matrix
            parts.append(f'<line class="marker-line" x1="{cx:.1f}" y1="{cy:.1f}" x2="{cx:.1f}" y2="{height-bottom}"/>')
            parts.append(f'<circle class="marker equal" cx="{cx:.1f}" cy="{cy:.1f}" r="7"><title>Margens iguais: {format_percent(scenario1["parent_margin"])} em {format_usd(crossover)}</title></circle>')
            label_x = min(cx + 15, width - right - 245)
            label_y = max(top + 18, cy - 18)
            parts.append(f'<text class="annotation equal-label" x="{label_x:.1f}" y="{label_y:.1f}">Margens iguais: {format_usd(crossover)}</text>')
        bx, by = x_pos(fob_break_even), y_pos(0)
        parts.append(f'<circle class="marker zero" cx="{bx:.1f}" cy="{by:.1f}" r="7"><title>Margem da distribuidora igual a zero: {format_usd(fob_break_even)}</title></circle>')
        parts.append(f'<text class="annotation zero-label" x="{bx-12:.1f}" y="{by-17:.1f}" text-anchor="end">Margem da distribuidora = 0</text>')
        parts.append('</svg>')
        return "".join(parts)

    c2_equal = scenario2(crossover) if crossover is not None else None
    snapshot_rows = [
        ("Kits importados", str(quantity)),
        ("Kits vendidos no cenário 2", str(c2_sold)),
        ("FOB cenário 1 salvo", f"{format_usd(scenario1_fob)} total ({format_usd(float(p['preco_fob_base']))}/kit)"),
        ("Preço de venda cenário 2", f"{format_brl(c2_price)}/kit"),
        ("Câmbio", f"R$ {format_number(exchange)}/US$"),
        ("Frete e seguro", f"{format_usd(freight_usd)}; seguro {format_number(float(p['seguro_pct']))}%"),
        ("Participação da matriz", f"C1: {format_number(float(p['participacao_matriz']))}%; C2: {format_number(float(p['participacao_matriz_c2']))}%"),
        ("Vendas / Opex", f"ICMS {format_number(float(p['aliq_icms_venda']))}% + PIS {format_number(float(p['aliq_pis_venda']))}% + Cofins {format_number(float(p['aliq_cofins_venda']))}%; Opex {format_brl(sum(float(p.get(key, 0) or 0) for key in ('opex_pessoal','opex_aluguel','opex_utilidades','opex_servicos_profissionais','opex_comercial_marketing','opex_sistemas','opex_seguros','opex_depreciacao','opex_administrativo','opex_outros')) * period)} no período"),
        ("Regime tributário Brasil", str(p["regime_tributario"])),
    ]
    snapshot_html = "".join(
        f"<tr><th>{html.escape(label)}</th><td>{html.escape(value)}</td></tr>"
        for label, value in snapshot_rows
    )
    cross_value = (
        f"{format_usd(crossover)} total / {format_usd(crossover / quantity)} por kit"
        if crossover is not None
        else "Sem cruzamento dentro do intervalo analisado"
    )
    cross_margin = format_percent(scenario1["parent_margin"])
    c2_equal_margin = format_percent(c2_equal["distributor_margin"]) if c2_equal else "N/A"
    cross_row = (
        f"<tr><td>Igualdade das margens</td><td>{cross_value}</td>"
        f"<td>{cross_margin}</td><td>{c2_equal_margin}</td></tr>"
        if crossover is not None
        else ""
    )
    comparison_rows = (
        f"<tr><td>Início da análise</td><td>{format_usd(fob_start)}</td>"
        f"<td>{format_percent(scenario1['parent_margin'])}</td><td>{format_percent(c2_start['distributor_margin'])}</td></tr>"
        f"{cross_row}"
        f"<tr><td>Margem da distribuidora igual a zero</td><td>{format_usd(fob_break_even)}</td>"
        f"<td>{format_percent(scenario1['parent_margin'])}</td><td>{format_percent(c2_break_even['distributor_margin'])}</td></tr>"
    )

    template = """<!doctype html>
<html lang="pt-BR"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="application-name" content="Synvitta2 Sensibilidade"><title>Análise de sensibilidade FOB | Synvitta2</title>
<style>
:root{color-scheme:light;--ink:#18364a;--text:#263941;--muted:#5b6d73;--line:#d4e0df;--paper:#fff;--canvas:#eef3f1;--teal:#197c78;--coral:#d0644c;--gold:#d59a3a;--mint:#dcefe9}
*{box-sizing:border-box}body{margin:0;background:var(--canvas);color:var(--text);font:15px/1.5 "Segoe UI",Arial,sans-serif}header{background:var(--ink);color:#fff;padding:26px max(22px,calc((100vw - 1240px)/2)) 24px;border-bottom:5px solid var(--gold)}header p{margin:0;color:#c9dfdf;font-size:13px}h1{margin:7px 0 5px;font-size:clamp(24px,3vw,34px);line-height:1.15}main{max-width:1280px;margin:0 auto;padding:22px}.lede{max-width:850px;color:var(--muted);margin:0 0 18px}.metrics{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:10px;margin:16px 0 20px}.metric{background:var(--paper);border-top:3px solid var(--teal);padding:13px 15px;min-width:0}.metric:nth-child(2){border-color:var(--coral)}.metric:nth-child(3){border-color:var(--gold)}.metric:nth-child(4){border-color:#688d55}.metric span{display:block;color:var(--muted);font-size:12px}.metric strong{display:block;color:var(--ink);font-size:19px;margin-top:5px;overflow-wrap:anywhere}.metric small{color:var(--muted)}.chart-panel{background:var(--paper);border:1px solid var(--line);padding:14px 18px 8px}.chart-panel h2,.section h2{font-size:18px;color:var(--ink);margin:0 0 8px}.chart{width:100%;height:auto;display:block}.grid{stroke:#dbe5e3;stroke-width:1}.grid.vertical{stroke-dasharray:2 5}.axis{stroke:#708188;stroke-width:1.2}.axis-label{fill:#53656b;font-size:12px}.axis-title{fill:#263941;font-size:13px;font-weight:600}.curve{fill:none;stroke-width:4;stroke-linecap:round;stroke-linejoin:round}.curve.parent{stroke:var(--teal)}.curve.distributor{stroke:var(--coral)}.marker-line{stroke:var(--gold);stroke-width:1.5;stroke-dasharray:5 5}.marker{stroke:#fff;stroke-width:2.5}.marker.equal{fill:var(--gold)}.marker.zero{fill:var(--coral)}.annotation{font-size:12px;font-weight:700;paint-order:stroke;stroke:#fff;stroke-width:4px;stroke-linejoin:round}.equal-label{fill:#8a5d12}.zero-label{fill:#a34634}.legend{display:flex;flex-wrap:wrap;gap:18px;padding:0 8px 8px;font-size:13px;color:var(--muted)}.legend span{display:inline-flex;align-items:center;gap:7px}.swatch{width:20px;height:4px;border-radius:4px;background:var(--teal)}.swatch.distributor{background:var(--coral)}.section{margin-top:20px;background:var(--paper);border:1px solid var(--line);padding:16px 18px}.table-wrap{overflow-x:auto}table{border-collapse:collapse;width:100%;font-size:13px}th,td{padding:9px 10px;border-bottom:1px solid var(--line);text-align:left;vertical-align:top}thead th{background:var(--ink);color:#fff}tbody th{width:29%;color:var(--ink);font-weight:600}tbody tr:nth-child(even){background:#f4f7f6}.note{font-size:13px;color:var(--muted);margin:10px 0 0}.method{display:grid;grid-template-columns:1fr 1fr;gap:16px}.method p{margin:7px 0}.pill{display:inline-block;background:var(--mint);color:#165a57;padding:3px 8px;font-size:12px;font-weight:700;border-radius:3px}.footer{color:var(--muted);font-size:12px;padding:20px 0 4px}@media(max-width:800px){main{padding:14px}.metrics{grid-template-columns:repeat(2,minmax(0,1fr))}.method{grid-template-columns:1fr}.chart-panel{padding:10px 8px}.axis-label{font-size:10px}.axis-title{font-size:11px}}@media(max-width:480px){.metrics{grid-template-columns:1fr 1fr}.metric strong{font-size:16px}header{padding:20px 16px}main{padding:10px}.chart-panel h2,.section h2{font-size:16px}}
</style></head><body>
<header><p>Synvitta2 · cenário independente · sensibilidade de preço</p><h1>Margens versus FOB total</h1><p>Perfil carregado do host em __DATE__ · análise estática e autônoma</p></header>
<main><p class="lede">Compara a margem da matriz brasileira no cenário 1 com a margem retida pela distribuidora independente no cenário 2 enquanto o FOB total importado varia de US$ 100.000 até o ponto de margem zero.</p>
<div class="metrics"><div class="metric"><span>Matriz Brasil · cenário 1</span><strong>__C1_MARGIN__</strong><small>FOB salvo: __C1_FOB__ total</small></div><div class="metric"><span>Distribuidora · FOB inicial</span><strong>__C2_START__</strong><small>Em US$ 100.000 de FOB</small></div><div class="metric"><span>Margens iguais</span><strong>__CROSS_FOB__</strong><small>Ambas em __CROSS_MARGIN__</small></div><div class="metric"><span>FOB de margem zero · cenário 2</span><strong>__BREAK_EVEN__</strong><small>__BREAK_EVEN_UNIT__ por kit</small></div></div>
<section class="chart-panel"><h2>Curvas de margem</h2><div class="legend"><span><i class="swatch"></i>Matriz Brasil · cenário 1 (constante)</span><span><i class="swatch distributor"></i>Distribuidora · cenário 2</span></div><div class="chart">__CHART__</div><p class="note">O eixo X mostra o valor FOB total em USD para a quantidade importada salva; o cenário 1 permanece fixo no FOB do perfil. O cruzamento identifica igualdade das duas margens. O limite final é o FOB em que a margem da distribuidora chega a zero.</p></section>
<section class="section"><h2>Pontos de referência</h2><div class="table-wrap"><table><thead><tr><th>Referência</th><th>FOB total</th><th>Matriz Brasil · C1</th><th>Distribuidora · C2</th></tr></thead><tbody>__COMPARISON_ROWS__</tbody></table></div></section>
<section class="section"><h2>Premissas do perfil usado</h2><div class="table-wrap"><table><tbody>__SNAPSHOT_ROWS__</tbody></table></div><p class="note">O arquivo registra uma fotografia dos padrões no momento da geração. Alterar os padrões do host não modifica este HTML; gere novamente para atualizar a análise.</p></section>
<section class="section method"><div><h2>Como ler as curvas</h2><p><span class="pill">Cenário 1</span> Margem do lucro brasileiro atribuído à matriz sobre o faturamento bruto, conforme o comparativo Synvitta2. É uma linha horizontal porque as premissas do cenário 1 permanecem fixas.</p><p><span class="pill">Cenário 2</span> Lucro líquido retido pela distribuidora local sobre o faturamento bruto. A participação da matriz permanece no valor salvo, atualmente __C2_SHARE__.</p></div><div><h2>Como a sensibilidade é calculada</h2><p>Para cada FOB, o cálculo atualiza valor aduaneiro, seguro, tributos de importação e custo de estoque; mantém as demais premissas salvas; e recalcula CMV, tributos sobre vendas, operação, Opex e IRPJ/CSLL pelo regime configurado.</p><p class="note">É uma análise gerencial baseada nas fórmulas e entradas do simulador, não uma apuração tributária ou cotação vinculante.</p></div></section>
<p class="footer">Gerado por gerar_analise_sensibilidade_synvitta2.py · __DATE__</p></main></body></html>"""
    replacements = {
        "__DATE__": date.today().isoformat(),
        "__C1_MARGIN__": format_percent(scenario1["parent_margin"]),
        "__C1_FOB__": format_usd(scenario1_fob),
        "__C2_START__": format_percent(c2_start["distributor_margin"]),
        "__CROSS_FOB__": cross_value,
        "__CROSS_MARGIN__": cross_margin,
        "__BREAK_EVEN__": format_usd(fob_break_even),
        "__BREAK_EVEN_UNIT__": format_usd(fob_break_even / quantity),
        "__CHART__": make_chart(),
        "__COMPARISON_ROWS__": comparison_rows,
        "__SNAPSHOT_ROWS__": snapshot_html,
        "__C2_SHARE__": f"{format_number(float(p['participacao_matriz_c2']))}%",
    }
    for marker, value in replacements.items():
        template = template.replace(marker, value)
    return template


def main() -> None:
    path = defaults_path()
    profile = json.loads(path.read_text(encoding="utf-8"))
    report = build_report(profile)
    output = Path(__file__).with_name("analise_sensibilidade_synvitta2.html")
    output.write_text(report, encoding="utf-8")
    print(f"HTML gerado: {output}")


if __name__ == "__main__":
    main()