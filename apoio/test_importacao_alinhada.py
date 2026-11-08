import ast
import copy
import json
import re
import subprocess
import unittest
from pathlib import Path

from synvitta3_calc_js import synvitta3_calculation_js
from synvitta3_importacao import CAMPOS_IMPORTACAO, completar_campos_importacao, valorar_lote


APOIO = Path(__file__).resolve().parent
ROOT = APOIO.parent.parent
CALCULADORA = ROOT / "estudo_logistico" / "calculadora_landed_cost_corrigida.html"


def node_json(script):
    result = subprocess.run(["node", "-"], input=script, capture_output=True, encoding="utf-8", check=True)
    return json.loads(result.stdout)


def calculation_from_html(path):
    html = path.read_text(encoding="utf-8")
    return html[html.index("function calculate(v, lang) {"):html.index("\nfunction esc(")]


class ImportacaoAlinhadaTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        source = (APOIO / "synvitta3.py").read_text(encoding="utf-8")
        function = next(n for n in ast.parse(source).body if isinstance(n, ast.FunctionDef) and n.name == "calcular_produto")
        namespace = {"valorar_lote": valorar_lote, "cambio": 5.5}
        exec(compile(ast.Module(body=[function], type_ignores=[]), str(APOIO / "synvitta3.py"), "exec"), namespace)
        cls.python_calculate = staticmethod(namespace["calcular_produto"])
        text = CALCULADORA.read_text(encoding="utf-8")
        cls.calculator_js = text[text.index("    function importCosts("):text.index("    function estimate(")]
        cls.engines = [synvitta3_calculation_js()] + [
            calculation_from_html(path) for path in (
                APOIO / "synvitta3_app.html", APOIO / "synvitta3_relatorio.html", APOIO.parent / "synvitta3_report.htm"
            )
        ]

    def scenario(self):
        components = {key: default for key, _, _, _, _, default in CAMPOS_IMPORTACAO}
        components.update(
            frete_origem_usd=500, despacho_miami_usd=250, despacho_na_va_usd=100,
            locacao_rap_usd=5000, locacao_na_va_usd=2000, modo_seguro="Valor informado",
            seguro_total_usd=4000, seguro_apos_usd=100, acrescimos_va_usd=50,
            custo_anvisa=268, custo_hub=2000, outras_despesas_aduaneiras=300, iof_cambio=40,
        )
        product = {
            "nome": "Leitor", "ncm": "9027.50.20", "quantidade": 160,
            "frete_usd": 2500, "modal": "Aéreo", "seguro_pct": 0.005, "ajustes": 55,
            "frete_interno": 800, "detalhado": True, "aliq_ii": 0.14, "aliq_ipi": 0.0975,
            "aliq_pis": 0.021, "aliq_cofins": 0.0965, "aliq_icms": 0.18,
            "aliq_afrmm": 0, "antidumping": 25, "taxa_siscomex": 115, "despesas_base_icms": 300,
            "custos_despacho": {"Taxa Siscomex": 115, "Armazenagem": 15000},
            "credita": {k: False for k in ("ipi", "pis", "cofins", "cbs_ibs", "icms")},
            "consolidado": 10000, "devolucoes": 0, "aliquota_venda": 0,
            "operador_pct": 0, "custo_fabricacao_usd": 2000, "componentes": components,
        }
        return product

    def evaluate_all(self, product):
        c = product["componentes"]
        values = {
            **c, "cambio": 5.5, "quantidade": 160, "quantidade_vendida": 80,
            "preco_fob_base": 5000, "preco_fob_c2": 5000, "receita_por_kit": 68000,
            "calculo_frete": "Valor total informado", "frete_usd": 2500, "modal": "Aéreo",
            "modo_custos_importacao": "Detalhado" if product["detalhado"] else "Consolidado",
            "seguro_pct": product["seguro_pct"] * 100, "ajustes_aduaneiros_brl": product["ajustes"],
            "frete_interno_brl": 800, "taxa_siscomex": 115, "custo_armazenagem": 15000,
            "despesas_na_base_icms": 300, "antidumping_brl": 25,
            "custo_importacao_consolidado_brl": 10000, "meses_operacao": 1,
        }
        for tax in ("ii", "ipi", "pis", "cofins", "icms"):
            values["aliq_" + tax] = product["aliq_" + tax] * 100
        for tax, enabled in product["credita"].items():
            values["credita_" + tax] = enabled
        outputs = []
        for engine in self.engines:
            instrumented = engine.replace(
                "        summaryTitle:",
                "        debug: {importData: importA, cogs: c1.cogs},\n        summaryTitle:", 1
            )
            result = node_json(instrumented + "\nconsole.log(JSON.stringify(calculate(" + json.dumps(values) + ', "pt")));')
            outputs.append(result["debug"])
            for table in result["tables"]:
                for row in table["rows"]:
                    self.assertEqual(len(row), len(table["headers"]), table["title"])
            self.assertTrue(any("valor aduaneiro" in t["title"] for t in result["tables"]))
        python = self.python_calculate(product, 5000, 80, 68000)
        for result in outputs:
            data = result["importData"]
            for js_key, py_key in (
                ("customsValue", "valor_aduaneiro"), ("outlay", "landed_cost_bruto"),
                ("credits", "creditos"), ("inventoryCost", "custo_estoque")
            ):
                self.assertAlmostEqual(data[js_key], python[py_key], places=6)
            self.assertAlmostEqual(result["cogs"], python["cmv"], places=6)
            self.assertAlmostEqual(sum(row[2] for row in data["composition"][:-1]), data["outlay"], places=6)
            self.assertAlmostEqual(sum(row[2] for row in data["customsComposition"][:-1]), data["customsValue"], places=6)
        return python, outputs[0]["importData"]

    def test_python_and_all_standalones_match(self):
        self.evaluate_all(self.scenario())

    def test_credits_never_reduce_cash(self):
        product = self.scenario()
        gross, _ = self.evaluate_all(product)
        product["credita"].update(ipi=True, icms=True)
        credited, _ = self.evaluate_all(product)
        self.assertEqual(gross["landed_cost_bruto"], credited["landed_cost_bruto"])
        self.assertLess(credited["cmv"], gross["cmv"])

    def test_consolidated_still_includes_costs_outside_va_once(self):
        product = self.scenario()
        product["detalhado"] = False
        self.evaluate_all(product)

    def test_percentage_insurance_includes_origin_freight(self):
        product = self.scenario()
        product["componentes"].update(modo_seguro="Percentual", seguro_apos_usd=0)
        python, js = self.evaluate_all(product)
        insurance = next(row[2] for row in js["customsComposition"] if row[1] == "Insurance through import location")
        self.assertAlmostEqual(insurance, (800000 + 500 + 2500) * 0.005 * 5.5)
        self.assertEqual(python["valor_aduaneiro"], js["customsValue"])

    def test_calculator_matches_synvitta(self):
        product = self.scenario()
        python, js = self.evaluate_all(product)
        c = product["componentes"]
        data = {
            "cabecalho": {"taxa_cambio_usd_brl": 5.5},
            "financeiro_internacional_usd": {
                "preco_exw_lote_usd": 800000, "frete_interno_origem_usd": 500,
                "despacho_exportacao_eua_usd": 250, "taxa_locacao_uld_usd": 5000,
                "despacho_na_va_usd": 100, "locacao_na_va_usd": 2000,
                "seguro_porta_a_porta_usd": 4000, "seguro_apos_local_importacao_usd": 100,
                "acrescimos_valor_aduaneiro_usd": 50, "ajustes_va_brl": 55,
            },
            "tributacao": {
                "aliquota_ii_percentual": 14, "aliquota_ipi_percentual": 9.75,
                "aliquota_pis_percentual": 2.1, "aliquota_cofins_percentual": 9.65,
                "aliquota_icms_estado_destino_percentual": 18, "antidumping_brl": 25,
                "cbs_ibs_recolher_brl": 0, "iof_cambio_brl": 40,
            },
            "despesas_nacionalizacao_brl": {
                "taxa_siscomex_brl": 115, "armazenagem_aeroporto_brl": 15000,
                "taxa_anvisa_tfvs_brl": c["custo_anvisa"], "armazenagem_hub_guarulhos_brl": c["custo_hub"],
                "outras_despesas_aduaneiras_brl": 300, "parcelas_base_icms_brl": 300,
                "frete_rodoviario_interno_brl": 800,
                **{k: 0 for k in ("honorarios_despachante_brl", "capatazia_brl", "taxas_terminal_brl",
                                 "agente_carga_brl", "licencas_inspecao_brl", "outras_despesas_importacao_brl")},
            },
        }
        result = node_json(self.calculator_js + "\nconsole.log(JSON.stringify(importCosts(" + json.dumps(data) + ", 2500, 5000)));")
        self.assertAlmostEqual(result["landed"], python["landed_cost_bruto"], places=6)
        self.assertAlmostEqual(result["customsBrl"], js["customsValue"], places=6)
        self.assertAlmostEqual(result["icms"], python["icms"], places=6)

    def test_documented_allocation_does_not_duplicate_cost(self):
        product = self.scenario()
        before, _ = self.evaluate_all(product)
        product["componentes"]["despacho_na_va_usd"] += 50
        after, _ = self.evaluate_all(product)
        self.assertAlmostEqual(after["valor_aduaneiro"] - before["valor_aduaneiro"], 50 * 5.5)
        # A alteração do desembolso é só a diferença de tributos, não outra cobrança do despacho.
        self.assertAlmostEqual(
            after["landed_cost_bruto"] - before["landed_cost_bruto"],
            sum(after[k] - before[k] for k in ("ii", "ipi", "pis_importacao", "cofins_importacao", "icms")),
            places=6,
        )

    def test_invalid_allocations_are_rejected(self):
        components = self.scenario()["componentes"]
        components["locacao_na_va_usd"] = 5001
        with self.assertRaises(ValueError):
            valorar_lote(800000, 2500, 0.005, 0, 5.5, components)

    def test_legacy_cbs_rates_do_not_create_cash_payment(self):
        source = self.engines[0]
        script = source + """
const base = {quantidade:1, cambio:5.5, preco_fob_base:100, modo_custos_importacao:"Detalhado"};
const get = v => calculate(v, "pt").summary[2].value;
console.log(JSON.stringify([get(base), get({...base, aliq_cbs:0.9, aliq_ibs:0.1, multiplo_base_cbs_ibs:1})]));
"""
        before, after = node_json(script)
        self.assertEqual(before, after)

    def test_field_metadata_is_idempotent(self):
        fields = completar_campos_importacao([])
        self.assertEqual(fields, completar_campos_importacao(copy.deepcopy(fields)))
        self.assertEqual(len(fields), len({item["key"] for item in fields}))

    def test_two_product_totals_and_output_shapes(self):
        html = (APOIO.parent / "synvitta3_report.htm").read_text(encoding="utf-8")
        values = json.loads(re.search(r'<script id="initial-values"[^>]*>(.*?)</script>', html, re.S)[1])
        values["p2_ativo"] = True
        expected = None
        for engine in self.engines:
            instrumented = engine.replace(
                "        summaryTitle:",
                "        debug: [c1.outlay, importA.outlay + importP2.outlay],\n        summaryTitle:", 1
            )
            result = node_json(instrumented + "\nconsole.log(JSON.stringify(calculate(" + json.dumps(values) + ', "pt")));')
            self.assertAlmostEqual(*result["debug"], places=6)
            if expected is None:
                expected = result["debug"][0]
            self.assertAlmostEqual(result["debug"][0], expected, places=6)
            for table in result["tables"]:
                for row in table["rows"]:
                    self.assertEqual(len(row), len(table["headers"]), table["title"])

    def test_inline_javascript_syntax(self):
        for path in (CALCULADORA, APOIO / "synvitta3_app.html", APOIO / "synvitta3_relatorio.html", APOIO.parent / "synvitta3_report.htm"):
            for attrs, script in re.findall(r"<script\b([^>]*)>(.*?)</script>", path.read_text(encoding="utf-8"), re.S):
                if "application/json" not in attrs and script.strip():
                    subprocess.run(["node", "--check", "-"], input=script, capture_output=True, encoding="utf-8", check=True)


if __name__ == "__main__":
    unittest.main()
