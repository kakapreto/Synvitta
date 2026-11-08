import unittest

from synvitta3_i18n import translate


class Synvitta3TranslationTests(unittest.TestCase):
    def test_english_income_statement_text_stays_in_english(self):
        statements = (
            "US Parent Company Profitability (Florida Matrix)",
            "Account Line Structure",
            "Gross Revenue",
            "Net Revenue",
            "Gross export revenue less manufacturing costs.",
            "Percentages are calculated against gross export revenue (FOB) for each scenario.",
        )

        for statement in statements:
            with self.subTest(statement=statement):
                self.assertEqual(translate(statement, "en"), statement)

    def test_income_statement_text_can_still_be_translated_to_portuguese(self):
        self.assertEqual(translate("Gross Revenue", "pt"), "Receita bruta")
        self.assertEqual(
            translate("Gross export revenue less manufacturing costs.", "pt"),
            "Receita bruta de exportação menos custos de fabricação.",
        )

    def test_tab_and_scenario_table_labels_are_translated_to_english(self):
        expected = {
            "Resumo": "Summary",
            "Cenários e matriz": "Scenarios and matrix",
            "Preço FOB matriz": "Parent company FOB price",
            "Kits vendidos": "Kits sold",
            "Landed cost bruto até o hub": "Gross landed cost through the hub",
            "Custo líquido do estoque para cálculo do CMV": "Net inventory cost for COGS calculation",
            "Valor aduaneiro": "Customs value",
            "Frete interno": "Domestic freight",
            "Lucro bruto": "Gross profit",
        }
        for portuguese, english in expected.items():
            with self.subTest(text=portuguese):
                self.assertEqual(translate(portuguese, "en"), english)


if __name__ == "__main__":
    unittest.main()
