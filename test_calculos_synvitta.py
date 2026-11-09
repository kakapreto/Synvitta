import copy
import unittest

from pydantic import ValidationError

from calculos_synvitta import Cenario, calcular_cenario, calcular_landed_cost, cenario_padrao


def cenario_simples():
    cenario = cenario_padrao()
    cenario.custos_compartilhados_usd.frete_internacional_aereo = 0
    cenario.custos_compartilhados_usd.frete_origem = 0
    cenario.custos_compartilhados_usd.seguro_internacional = 0
    cenario.custos_compartilhados_usd.despacho_miami = 0
    cenario.custos_compartilhados_usd.locacao_uld_rap = 0
    for chave in type(cenario.custos_compartilhados_brl).model_fields:
        setattr(cenario.custos_compartilhados_brl, chave, 0)
    for produto in cenario.produtos:
        produto.quantidade = 1
        produto.preco_unitario_exw_usd = 100
        produto.preco_venda_unitario_brl = 750_000
        produto.frete_interno_hub_brl = 0
        for chave in type(produto.aliquotas_importacao).model_fields:
            setattr(produto.aliquotas_importacao, chave, 0)
        for chave in type(produto.aliquotas_venda).model_fields:
            setattr(produto.aliquotas_venda, chave, 0)
        produto.pis_venda_real = produto.cofins_venda_real = 0
    cenario.estrutura_opex_e_societaria.opex_fixo_mensal_brl = 0
    return cenario


class CalculosTests(unittest.TestCase):
    def test_lc224_exemplo_oficial_q1_e_q2(self):
        cenario = cenario_simples()
        for trimestre, csll in ((1, 16_200), (2, 16_470), (4, 16_470)):
            with self.subTest(trimestre=trimestre):
                cenario.tributacao.trimestre = trimestre
                lp = calcular_cenario(cenario).lucro_presumido
                self.assertAlmostEqual(lp.base_irpj_brl, 122_000)
                self.assertAlmostEqual(lp.irpj_brl, 18_300)
                self.assertAlmostEqual(lp.adicional_irpj_brl, 6_200)
                self.assertAlmostEqual(lp.csll_brl, csll)

    def test_limites_exatos_e_2025_sem_majoracao(self):
        cenario = cenario_simples()
        cenario.produtos[0].preco_venda_unitario_brl = 625_000
        cenario.produtos[1].preco_venda_unitario_brl = 625_000
        lp = calcular_cenario(cenario).lucro_presumido
        self.assertEqual(lp.receita_excedente_majoracao_brl, 0)
        self.assertEqual(lp.base_irpj_brl, 100_000)
        cenario.tributacao.ano = 2025
        cenario.produtos[1].preco_venda_unitario_brl = 875_000
        lp = calcular_cenario(cenario).lucro_presumido
        self.assertEqual(lp.base_irpj_brl, 120_000)
        self.assertEqual(lp.csll_brl, 16_200)

    def test_adicional_irpj_usa_trimestre_nao_meses_opex(self):
        cenario = cenario_simples()
        for produto in cenario.produtos:
            produto.preco_venda_unitario_brl = 375_000
        lp = calcular_cenario(cenario).lucro_presumido
        self.assertEqual(lp.base_irpj_brl, 60_000)
        self.assertEqual(lp.adicional_irpj_brl, 0)
        cenario.estrutura_opex_e_societaria.meses_operacao = 3
        self.assertEqual(calcular_cenario(cenario).lucro_presumido.adicional_irpj_brl, 0)

    def test_rateio_e_fechamento_do_landed(self):
        cenario = cenario_simples()
        cenario.produtos[1].preco_unitario_exw_usd = 200
        cenario.parametros_globais.ptax = 5
        usd = cenario.custos_compartilhados_usd
        usd.frete_origem = 30
        usd.frete_internacional_aereo = 60
        usd.seguro_internacional = 3
        usd.despacho_miami = 6
        usd.locacao_uld_rap = 9
        cenario.custos_compartilhados_brl.taxa_siscomex = 30
        landed = calcular_landed_cost(cenario)
        self.assertAlmostEqual(landed.cif_total_lote_brl, (300 + 93) * 5)
        self.assertAlmostEqual(landed.landed_cost_bruto_lote_brl, 408 * 5 + 30)
        self.assertAlmostEqual(landed.produtos[0].cif_total_brl * 2,
                               landed.produtos[1].cif_total_brl)
        usd.despacho_na_va = 6
        usd.locacao_na_va = 9
        revisado = calcular_landed_cost(cenario)
        self.assertAlmostEqual(revisado.cif_total_lote_brl, 408 * 5)
        self.assertAlmostEqual(revisado.landed_cost_bruto_lote_brl,
                               landed.landed_cost_bruto_lote_brl)

    def test_tributos_importacao_e_icms_por_dentro(self):
        cenario = cenario_simples()
        cenario.parametros_globais.ptax = 5
        produto = cenario.produtos[0]
        taxas = produto.aliquotas_importacao
        taxas.ii, taxas.ipi, taxas.pis, taxas.cofins, taxas.icms = .10, .05, .021, .0965, .18
        custo = calcular_landed_cost(cenario).produtos[0]
        self.assertAlmostEqual(custo.ii_brl, 50)
        self.assertAlmostEqual(custo.ipi_brl, 27.5)
        self.assertAlmostEqual(custo.pis_brl, 10.5)
        self.assertAlmostEqual(custo.cofins_brl, 48.25)
        self.assertAlmostEqual(custo.base_icms_brl, 636.25 / .82)
        self.assertAlmostEqual(custo.icms_brl, 636.25 / .82 * .18)

    def test_creditos_sem_dupla_contagem_e_pis_exclui_icms(self):
        cenario = cenario_simples()
        produto = cenario.produtos[0]
        produto.aliquotas_importacao.pis = .021
        produto.aliquotas_importacao.cofins = .0965
        produto.aliquotas_venda.icms = .18
        produto.aliquotas_venda.pis = .0065
        produto.aliquotas_venda.cofins = .03
        produto.pis_venda_real = .0165
        produto.cofins_venda_real = .076
        original = calcular_cenario(cenario)
        custo = original.landed_cost.produtos[0]
        produto.credito_pis_importacao_real_brl = custo.pis_brl
        produto.credito_cofins_importacao_real_brl = custo.cofins_brl
        credito = custo.pis_brl + custo.cofins_brl
        revisado = calcular_cenario(cenario)
        self.assertAlmostEqual(
            original.lucro_real.cmv_total_brl - revisado.lucro_real.cmv_total_brl, credito
        )
        self.assertEqual(original.lucro_real.tributos_venda_total_brl,
                         revisado.lucro_real.tributos_venda_total_brl)
        self.assertEqual(original.lucro_presumido, revisado.lucro_presumido)
        item = revisado.lucro_presumido.itens_produtos[0]
        self.assertAlmostEqual(item.pis_venda_brl, 750_000 * .82 * .0065)
        produto.credito_pis_importacao_real_brl = custo.pis_brl + 1
        with self.assertRaisesRegex(ValueError, "excede"):
            calcular_cenario(cenario)

    def test_dividendos_fecham_e_prejuizo_nao_distribui(self):
        cenario = cenario_simples()
        resultado = calcular_cenario(cenario)
        for r in (resultado.lucro_real, resultado.lucro_presumido):
            self.assertAlmostEqual(r.dividendos_matriz_brutos_brl,
                                   r.lucro_liquido_brasil_brl * .75)
            self.assertAlmostEqual(
                r.remessa_matriz_eua_brl + r.retencao_dividendos_brl
                + r.custo_remessa_brl + r.parcela_socios_locais_brl,
                r.lucro_liquido_brasil_brl,
            )
        cenario.estrutura_opex_e_societaria.opex_fixo_mensal_brl = 2_000_000
        resultado = calcular_cenario(cenario)
        self.assertEqual(resultado.lucro_real.irpj_csll_brl, 0)
        self.assertGreater(resultado.lucro_presumido.irpj_csll_brl, 0)
        for r in (resultado.lucro_real, resultado.lucro_presumido):
            self.assertEqual(r.remessa_matriz_eua_brl, 0)
            self.assertEqual(r.parcela_socios_locais_brl, 0)
            self.assertLess(r.lucro_retido_filial_sp_brl, 0)

    def test_receita_zero_e_opex_nao_triplica_receita(self):
        cenario = cenario_simples()
        cenario.estrutura_opex_e_societaria.opex_fixo_mensal_brl = 100
        cenario.estrutura_opex_e_societaria.meses_operacao = 3
        resultado = calcular_cenario(cenario)
        self.assertEqual(resultado.lucro_presumido.receita_bruta_total_brl, 1_500_000)
        self.assertEqual(resultado.lucro_presumido.opex_fixo_brl, 300)
        for produto in cenario.produtos:
            produto.preco_venda_unitario_brl = 0
        resultado = calcular_cenario(cenario)
        self.assertEqual(resultado.lucro_presumido.margem_liquida_pct, 0)
        self.assertEqual(resultado.lucro_real.irpj_csll_brl, 0)

    def test_json_antigo_e_validacoes(self):
        antigo = cenario_padrao().model_dump()
        del antigo["tributacao"]
        for produto in antigo["produtos"]:
            for chave in ("pis_venda_real", "cofins_venda_real",
                          "credito_pis_importacao_real_brl", "credito_cofins_importacao_real_brl"):
                del produto[chave]
        migrado = Cenario.model_validate(antigo)
        self.assertEqual(migrado.tributacao.trimestre, 4)
        self.assertEqual(migrado.tributacao.ano, 2026)
        for valor in (0, -1, float("nan"), float("inf")):
            dados = copy.deepcopy(antigo)
            dados["parametros_globais"]["ptax"] = valor
            with self.subTest(ptax=valor), self.assertRaises(ValidationError):
                Cenario.model_validate(dados)
        dados = cenario_padrao().model_dump()
        dados["produtos"][0]["aliquotas_importacao"]["icms"] = 1
        with self.assertRaises(ValidationError):
            Cenario.model_validate(dados)
        dados = cenario_padrao().model_dump()
        dados["custos_compartilhados_usd"]["despacho_na_va"] = 99999
        with self.assertRaises(ValidationError):
            Cenario.model_validate(dados)

    def test_determinismo_e_entradas_nao_mutadas(self):
        cenario = cenario_padrao()
        antes = cenario.model_dump_json()
        self.assertEqual(calcular_cenario(cenario), calcular_cenario(cenario))
        self.assertEqual(cenario.model_dump_json(), antes)


if __name__ == "__main__":
    unittest.main()
