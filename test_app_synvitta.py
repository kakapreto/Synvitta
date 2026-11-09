import ast
import copy
import io
import json
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import httpx
import httpx2
import openpyxl
import pandas as pd
from google import genai
from google.genai import errors
from pydantic import BaseModel, Field
from streamlit.testing.v1 import AppTest


APP_PATH = Path(__file__).with_name("app_synvitta.py")


def respostas_validas():
    produto = {
        "nome_produto": "Produto de teste",
        "ncm": "0000.00.00",
        "quantidade": 10,
        "valor_exw_total_usd": 50,
        "cif_total_brl": 350,
        "landed_cost_bruto_total_brl": 500,
        "creditos_tributarios_recuperaveis_brl": 100,
        "custo_estoque_liquido_cmv_brl": 400,
        "custo_unitario_cmv_brl": 40,
    }
    landed = {
        "ptax_utilizada": 5.6,
        "valor_exw_total_lote_usd": 50,
        "cif_total_lote_brl": 350,
        "landed_cost_bruto_lote_brl": 500,
        "creditos_totais_lote_brl": 100,
        "custo_estoque_liquido_lote_brl": 400,
        "produtos": [produto],
    }
    regime = {
        "regime_tributario": "Teste",
        "receita_bruta_total_brl": 1000,
        "tributos_venda_total_brl": 100,
        "receita_liquida_total_brl": 900,
        "cmv_total_brl": 400,
        "lucro_bruto_total_brl": 500,
        "opex_fixo_brl": 100,
        "operacao_variavel_brl": 0,
        "ebitda_brl": 400,
        "irpj_csll_brl": 100,
        "lucro_liquido_brasil_brl": 300,
        "margem_liquida_pct": 30,
        "remessa_matriz_eua_brl": 200,
        "lucro_retido_filial_sp_brl": 75,
        "itens_produtos": [{
            "nome_produto": "Produto de teste",
            "unidades_vendidas": 10,
            "receita_bruta_brl": 1000,
            "tributos_venda_brl": 100,
            "receita_liquida_brl": 900,
            "cmv_brl": 400,
            "lucro_bruto_brl": 500,
            "margem_contribucao_pct": 50,
        }],
    }
    relatorio = {
        "ptax": 5.6,
        "lucro_real": regime,
        "lucro_presumido": copy.deepcopy(regime),
        "regime_recomendado": "Relatorio ficticio para teste da interface.",
        "economia_tributaria_anual_estimada_brl": 0,
    }
    return [
        SimpleNamespace(text=json.dumps(landed)),
        SimpleNamespace(text=json.dumps(relatorio)),
    ]


class AppSynvittaTests(unittest.TestCase):
    def setUp(self):
        self.real_client = genai.Client
        self.client = MagicMock()
        self.client.__enter__.return_value = self.client
        self.client.models.generate_content.side_effect = respostas_validas()
        self.client_patch = patch("google.genai.Client", return_value=self.client)
        self.factory = self.client_patch.start()
        self.addCleanup(self.client_patch.stop)
        self.app = AppTest.from_file(str(APP_PATH), default_timeout=30)
        self.app.secrets["GEMINI_API_KEY"] = "test-key-not-a-real-credential"
        self.app.run()
        self.assertFalse(self.app.exception)

    def executar(self):
        self.app.sidebar.button[0].click().run()
        self.assertFalse(self.app.exception)

    def test_resultados_e_exportacoes_apos_duas_etapas(self):
        self.executar()
        self.assertFalse(self.app.error)
        self.assertEqual(len(self.app.metric), 6)
        self.assertEqual(len(self.app.get("download_button")), 3)
        self.assertEqual(self.client.models.generate_content.call_count, 2)
        self.assertEqual(self.app.session_state["resultado_dre"]["ptax"], 5.6)
        self.assertEqual(
            self.app.session_state["resultado_dre"]["lucro_presumido"]
            ["lucro_liquido_brasil_brl"], 300,
        )
        self.assertEqual(self.app.status[0].state, "complete")
        http_options = self.factory.call_args.kwargs["http_options"]
        self.assertEqual(http_options.timeout, 60_000)
        self.assertEqual(http_options.retry_options.attempts, 2)
        self.assertIn(503, http_options.retry_options.http_status_codes)
        payload_dre = json.loads(
            self.client.models.generate_content.call_args_list[1].kwargs["contents"]
        )
        self.assertEqual(payload_dre["ptax"], 5.6)
        self.assertIn("landed_cost_input", payload_dre)
        self.assertIn("empresa", payload_dre)
        self.app.run()
        self.assertFalse(self.app.exception)
        self.assertEqual(len(self.app.metric), 6)
        self.assertEqual(self.client.models.generate_content.call_count, 2)

    def test_excel_tem_dados_do_relatorio(self):
        self.executar()
        tree = ast.parse(APP_PATH.read_text(encoding="utf-8"))
        tree.body = [
            node for node in tree.body
            if isinstance(node, ast.ClassDef)
            or isinstance(node, ast.FunctionDef) and node.name == "gerar_excel_bytes"
        ]
        namespace = {"BaseModel": BaseModel, "Field": Field, "pd": pd, "io": io}
        exec(compile(tree, str(APP_PATH), "exec"), namespace)
        report_class = namespace["DREReportSynvitta"]
        report = report_class.model_validate(self.app.session_state["resultado_dre"])
        data = namespace["gerar_excel_bytes"](report)
        workbook = openpyxl.load_workbook(io.BytesIO(data), data_only=True)
        self.assertIn("DRE_Comparativa", workbook.sheetnames)
        self.assertEqual(workbook["DRE_Comparativa"]["B2"].value, 1000)
        self.assertEqual(workbook["DRE_Comparativa"]["C11"].value, 300)

    def test_excesso_de_demanda_nao_simula_sucesso(self):
        self.client.models.generate_content.side_effect = errors.ServerError(
            503, {"error": {"message": "Service overloaded"}}
        )
        self.executar()
        self.assertIn("excesso de demanda", self.app.error[0].value)
        self.assertEqual(self.app.status[0].state, "error")
        self.assertEqual(len(self.app.metric), 0)
        self.assertEqual(self.client.models.generate_content.call_count, 1)

    def test_resposta_vazia_interrompe_antes_da_dre(self):
        self.client.models.generate_content.side_effect = [
            SimpleNamespace(text=None),
        ]
        self.executar()
        self.assertIn("Landed Cost", self.app.error[0].value)
        self.assertIn("não retornou dados", self.app.error[0].value)
        self.assertEqual(self.client.models.generate_content.call_count, 1)
        self.assertEqual(len(self.app.metric), 0)

    def test_resposta_incompleta_nao_e_aceita(self):
        self.client.models.generate_content.side_effect = [
            SimpleNamespace(text="{}"),
        ]
        self.executar()
        self.assertIn("dados incompletos", self.app.error[0].value)
        self.assertEqual(self.client.models.generate_content.call_count, 1)
        self.assertEqual(len(self.app.metric), 0)

    def test_falha_na_dre_nao_exibe_resultado_antigo(self):
        self.executar()
        self.client.models.generate_content.side_effect = [
            respostas_validas()[0], SimpleNamespace(text="not json"),
        ]
        self.executar()
        self.assertIn("DRE", self.app.error[0].value)
        self.assertEqual(len(self.app.metric), 0)
        self.assertNotIn("resultado_dre", self.app.session_state)

    def test_timeout_e_mostrado_na_tela(self):
        self.client.models.generate_content.side_effect = httpx.ReadTimeout(
            "test timeout"
        )
        self.executar()
        self.assertIn("tempo limite", self.app.error[0].value)
        self.assertEqual(len(self.app.metric), 0)

    def test_timeout_do_transporte_httpx2(self):
        self.client.models.generate_content.side_effect = httpx2.ReadTimeout(
            "test timeout"
        )
        self.executar()
        self.assertIn("tempo limite", self.app.error[0].value)
        self.assertEqual(len(self.app.metric), 0)

    def test_sdk_repete_503_e_recupera_sem_rede(self):
        respostas = respostas_validas()
        chamadas = []

        def responder(request):
            chamadas.append(request)
            if len(chamadas) == 1:
                return httpx.Response(
                    503, json={"error": {"code": 503, "message": "Overloaded"}}
                )
            texto = respostas[len(chamadas) - 2].text
            return httpx.Response(200, json={
                "candidates": [{
                    "content": {"role": "model", "parts": [{"text": texto}]},
                    "finishReason": "STOP",
                }],
            })

        def criar_cliente(**kwargs):
            options = kwargs["http_options"]
            options.httpx_client = httpx.Client(
                transport=httpx.MockTransport(responder)
            )
            options.retry_options.initial_delay = 0
            options.retry_options.max_delay = 0
            options.retry_options.jitter = 0
            return self.real_client(**kwargs)

        self.factory.side_effect = criar_cliente
        self.executar()
        self.assertFalse(self.app.error)
        self.assertEqual(len(chamadas), 3)
        self.assertEqual(len(self.app.metric), 6)

    def test_chave_ausente_nao_chama_api(self):
        self.app.sidebar.text_input(key="gemini_api_key").set_value("").run()
        self.executar()
        self.assertIn("chave válida", self.app.error[0].value)
        self.factory.assert_not_called()

    def test_campos_iguais_dos_produtos_nao_colidem(self):
        self.app.number_input(key="p2_ii").set_value(0.0)
        self.app.number_input(key="p2_ipi").set_value(0.0)
        self.app.number_input(key="p2_frete_hub").set_value(1200.0)
        self.app.run()
        self.assertFalse(self.app.exception)
        self.executar()
        self.assertEqual(len(self.app.metric), 6)


if __name__ == "__main__":
    unittest.main()
