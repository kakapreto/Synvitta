import ast
import io
import json
import socket
import unittest
from pathlib import Path
from unittest.mock import patch

import openpyxl
import pandas as pd
from streamlit.testing.v1 import AppTest

from calculos_synvitta import Cenario, DREReportSynvitta, calcular_cenario, cenario_padrao


APP_PATH = Path(__file__).with_name("app_synvitta.py")


class AppSynvittaTests(unittest.TestCase):
    def setUp(self):
        conectar = socket.socket.connect

        def conectar_apenas_loopback(sock, endereco):
            # Asyncio no Windows usa socketpair em loopback.
            if not isinstance(endereco, tuple) or endereco[0] not in ("127.0.0.1", "::1"):
                raise AssertionError("External network forbidden")
            return conectar(sock, endereco)

        self.network_patch = patch("socket.socket.connect", new=conectar_apenas_loopback)
        self.network_patch.start()
        self.addCleanup(self.network_patch.stop)
        self.app = AppTest.from_file(str(APP_PATH), default_timeout=30).run()
        self.assertFalse(self.app.exception)

    def executar(self):
        self.app.sidebar.button[0].click().run()
        self.assertFalse(self.app.exception)

    def test_resultados_e_downloads_sem_chave_ou_rede(self):
        self.assertEqual(len(self.app.sidebar.text_input), 0)
        self.executar()
        self.assertFalse(self.app.error)
        self.assertEqual(len(self.app.metric), 10)
        self.assertEqual(len(self.app.get("download_button")), 3)
        self.assertEqual(
            self.app.session_state["resultado_dre"]["lucro_presumido"]
            ["receita_bruta_total_brl"], 58_624_000,
        )
        self.assertEqual(self.app.session_state["resultado_dre"]["ptax"], 5.6)
        self.app.run()
        self.assertFalse(self.app.exception)
        self.assertEqual(len(self.app.metric), 10)

    def test_entradas_alteradas_ocultam_resultados_antigos(self):
        self.executar()
        self.app.number_input(key="entrada:global:ptax").set_value(6.0).run()
        self.assertEqual(len(self.app.metric), 0)
        self.assertTrue(any("alteradas" in aviso.value for aviso in self.app.warning))
        self.executar()
        self.assertEqual(self.app.session_state["resultado_dre"]["ptax"], 6)

    def test_participacoes_invalidas_mostram_erro_e_podem_ser_corrigidas(self):
        self.app.number_input(
            key="entrada:soc:participacao_matriz_eua_pct"
        ).set_value(70.0).run()
        self.assertFalse(self.app.exception)
        self.executar()
        self.assertIn("somar 100%", self.app.error[0].value)
        self.app.number_input(
            key="entrada:soc:participacao_socios_locais_sp_pct"
        ).set_value(30.0).run()
        self.executar()
        self.assertFalse(self.app.error)

    def test_campos_iguais_dos_produtos_nao_colidem(self):
        self.app.number_input(key="entrada:p2:importacao:ii").set_value(0.0)
        self.app.number_input(key="entrada:p2:importacao:ipi").set_value(0.0)
        self.app.number_input(key="entrada:p2:frete_interno_hub_brl").set_value(1200.0)
        self.app.run()
        self.executar()
        self.assertFalse(self.app.error)

    def test_download_cenario_reflete_entradas_atuais(self):
        self.app.number_input(key="entrada:global:ptax").set_value(5.8).run()
        self.assertEqual(self.app.session_state["cenario"]["parametros_globais"]["ptax"], 5.8)
        self.executar()
        report = DREReportSynvitta.model_validate(self.app.session_state["resultado_dre"])
        self.assertEqual(report.premissas.parametros_globais.ptax, 5.8)
        self.assertEqual(json.loads(report.model_dump_json())["ptax"], 5.8)

    def test_importacao_valida_atualiza_entradas_e_limpa_resultados(self):
        self.executar()
        novo = cenario_padrao()
        novo.parametros_globais.ptax = 6.2
        novo.produtos[0].quantidade = 100
        self.app.session_state["arquivo_cenario"] = io.BytesIO(
            novo.model_dump_json().encode()
        )
        source = APP_PATH.read_text(encoding="utf-8")
        # Chama o mesmo callback da UI sem depender do suporte a upload do AppTest.
        source += "\nimportar_cenario()\n"
        app = AppTest.from_string(source, default_timeout=30)
        app.session_state["arquivo_cenario"] = io.BytesIO(
            novo.model_dump_json().encode()
        )
        app.run()
        self.assertFalse(app.exception)
        self.assertEqual(app.session_state["cenario"]["parametros_globais"]["ptax"], 6.2)
        self.assertNotIn("resultado_dre", app.session_state)

    def test_excel_tem_dados_premissas_e_memoria(self):
        self.executar()
        tree = ast.parse(APP_PATH.read_text(encoding="utf-8"))
        tree.body = [
            node for node in tree.body
            if isinstance(node, ast.FunctionDef)
            and node.name in ("tabela_dre", "gerar_excel_bytes")
        ]
        namespace = {"pd": pd, "io": io, "DREReportSynvitta": DREReportSynvitta}
        exec(compile(tree, str(APP_PATH), "exec"), namespace)
        relatorio = DREReportSynvitta.model_validate(self.app.session_state["resultado_dre"])
        data = namespace["gerar_excel_bytes"](relatorio)
        workbook = openpyxl.load_workbook(io.BytesIO(data), data_only=True)
        self.assertEqual(workbook["DRE_Comparativa"]["C2"].value, 58_624_000)
        self.assertIn("Landed_Cost", workbook.sheetnames)
        self.assertIn("Memoria_e_Avisos", workbook.sheetnames)
        self.assertIn("Entradas", workbook.sheetnames)
        self.assertIn("Produtos_Presumido", workbook.sheetnames)


if __name__ == "__main__":
    unittest.main()
