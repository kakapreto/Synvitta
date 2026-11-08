"""Atualiza os HTMLs existentes sem substituir suas premissas ou lógica de vendas."""

import json
import re
import subprocess
from html.parser import HTMLParser
from pathlib import Path

from standalone_html3 import build_calculator_html, field
from synvitta3_calc_js import synvitta3_calculation_js
from synvitta3_importacao import completar_campos_importacao


class CamposHTML(HTMLParser):
    def __init__(self, values):
        super().__init__()
        self.values = values
        self.fields = []
        self.group = ("Premissas", "Assumptions")
        self.label = None
        self.current = None
        self.in_form = False

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "form" and attrs.get("id") == "input-form":
            self.in_form = True
        if not self.in_form:
            return
        if tag == "summary" and "data-pt" in attrs:
            self.group = (attrs["data-pt"], attrs["data-en"])
        if tag == "label":
            self.label = None
            self.current = None
        if tag == "span" and "data-pt" in attrs:
            self.label = (attrs["data-pt"], attrs["data-en"])
            if self.current:
                self.current["label"] = dict(zip(("pt", "en"), self.label))
        if tag in ("input", "select") and "data-key" in attrs:
            key = attrs["data-key"]
            kind = "select" if tag == "select" else attrs.get("type", "number")
            pt, en = self.label or (key, key)
            self.current = field(
                key, pt, en, self.values.get(key, False if kind == "checkbox" else 0),
                *self.group, kind=kind, scale=float(attrs.get("data-scale", 1)),
                minimum=float(attrs["min"]) if "min" in attrs else None,
                maximum=float(attrs["max"]) if "max" in attrs else None,
                step=attrs.get("step", "any"),
            )
            self.fields.append(self.current)
        if tag == "option" and self.current:
            self.current["options"].append((
                attrs["value"], attrs.get("data-pt", attrs["value"]), attrs.get("data-en", attrs["value"])
            ))

    def handle_endtag(self, tag):
        if tag == "form":
            self.in_form = False


def atualizar(path):
    original = path.read_text(encoding="utf-8")
    values = json.loads(re.search(r'<script id="initial-values"[^>]*>(.*?)</script>', original, re.S)[1])
    overrides = re.findall(r"Object.assign\(DEFAULTS,(\{.*?\})\);", original, re.S)
    if overrides:
        js = "const DEFAULTS=" + json.dumps(values) + ";\n"
        js += "\n".join(f"Object.assign(DEFAULTS,{item});" for item in overrides)
        js += "\nconsole.log(JSON.stringify(DEFAULTS));"
        result = subprocess.run(["node", "-"], input=js, capture_output=True, encoding="utf-8", check=True)
        values = json.loads(result.stdout)
    parser = CamposHTML(values)
    parser.feed(original)
    if len(parser.fields) < 100:
        raise ValueError(f"Metadados de entrada incompletos: {path}")
    fields = completar_campos_importacao(parser.fields)
    for item in fields:
        item["value"] = values.get(item["key"], item["value"])
    if "ano_calendario" in values and not any(item["key"] == "ano_calendario" for item in fields):
        for key, pt, en in (
            ("ano_calendario", "Ano-calendário da apuração", "Tax assessment year"),
            ("mes_inicio_periodo", "Mês inicial do período (1–12)", "Starting month of period (1–12)"),
            ("receita_acumulada_ano_antes_periodo", "Receita bruta acumulada antes do período (R$)", "Gross revenue accumulated before period (BRL)"),
        ):
            fields.append(field(key, pt, en, values[key], "Tributos sobre lucro e remessas", "Profit taxes and remittances", minimum=0))
    calculation = synvitta3_calculation_js()
    migration = ""
    if "function calculateLc224Surcharge" in original:
        # Este relatório possui uma revisão independente da DRE; só troca a importação.
        old_calc = original[original.index("function calculate(v, lang) {"):original.index("\nfunction esc(")]
        start = calculation.index("    const dispatchCosts =")
        end = calculation.index("    const productOneImport")
        old_start = old_calc.index("    const dispatchCosts =")
        old_end = old_calc.index("    const productOneImport")
        old_calc = old_calc[:old_start] + calculation[start:end] + old_calc[old_end:]
        if "    const brl = value =>" not in old_calc:
            old_calc = old_calc.replace('    const usd = value =>', '    const brl = value => (pt ? "R$ " : "BRL ") + numberFormat(value);\n    const usd = value =>', 1)
        va_start = calculation.index('    tables.push({\n        title: label("Composição do valor aduaneiro"')
        va_end = calculation.index('    tables.push({\n        title: label("Composição da importação"', va_start)
        if 'title: label("Composição do valor aduaneiro"' in old_calc:
            old_va = old_calc.index('    tables.push({\n        title: label("Composição do valor aduaneiro"')
            old_import = old_calc.index('    tables.push({\n        title: label("Composição da importação"', old_va)
            old_calc = old_calc[:old_va] + calculation[va_start:va_end] + old_calc[old_import:]
        else:
            anchor = old_calc.index('    tables.push({\n        title: label("Composição da importação"')
            old_calc = old_calc[:anchor] + calculation[va_start:va_end] + old_calc[anchor:]
        warnings_start = calculation.index("        importWarnings:")
        warnings_end = calculation.index("        summaryTitle:", warnings_start)
        if "        importWarnings:" in old_calc:
            old_start = old_calc.index("        importWarnings:")
            old_end = old_calc.index("        summaryTitle:", old_start)
            old_calc = old_calc[:old_start] + calculation[warnings_start:warnings_end] + old_calc[old_end:]
        else:
            old_calc = old_calc.replace("        summaryTitle:", calculation[warnings_start:warnings_end] + "        summaryTitle:", 1)
        calculation = old_calc
        if "function separateLegacyFreight" in original:
            migration_start = original.index("function separateLegacyFreight")
            migration_end = original.find("\nconst VISIBILITY_RULES", migration_start)
            if migration_end == -1:
                migration_end = original.index("\nfunction applyInputs", migration_start)
            migration = original[migration_start:migration_end]
    language = re.search(r'let LANGUAGE="(pt|en)"', original)[1]
    html = build_calculator_html(
        model_id="synvitta3", language=language, title="Synvitta3",
        fields=fields, calculation_js=calculation,
        titles={"pt": "Synvitta3 - Simulação detalhada", "en": "Synvitta3 - Detailed simulation"},
        auto_language='const AUTO_LANGUAGE=true' in original,
    )
    old_save = re.search(r'const SAVE_KEY=("[^"]+");', original)[1]
    html = re.sub(r'const SAVE_KEY="[^"]+";', lambda _: f"const SAVE_KEY={old_save};", html)
    if migration:
        html = html.replace("function applyInputs(values){", migration + "\nfunction applyInputs(values){values=separateLegacyFreight(values);")
    path.write_text(html, encoding="utf-8")
    print(f"Atualizado: {path.name} ({len(fields)} campos)")


if __name__ == "__main__":
    apoio = Path(__file__).resolve().parent
    for path in (apoio / "synvitta3_app.html", apoio / "synvitta3_relatorio.html", apoio.parent / "synvitta3_report.htm"):
        atualizar(path)
