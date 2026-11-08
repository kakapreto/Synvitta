import json, re

with open('simulador_synvitta/synvitta2_report.htm', 'r', encoding='utf-8') as f:
    content = f.read()
m = re.search(r'id="initial-values"[^>]*>(.*?)</script>', content)
p = json.loads(m.group(1))

def calc_c1(fob):
    exchange = 5.6
    quantity = 1000
    freight_usd = 6400
    fob_usd = fob * quantity
    insurance = (fob_usd + freight_usd) * exchange * 0.0025
    customs = fob_usd * exchange + freight_usd * exchange + insurance
    import_tax = customs * (0.0021 + 0.00965)
    dispatch = 11299.62 + 2500 + 4500 + 136.53 + 600 + 1100 + 1637.7 + 1500
    inv = customs + import_tax + dispatch
    
    price = 9598.40
    gross = price * quantity
    sales_tax = gross * 0.0765
    net_rev = gross - sales_tax
    cogs = inv
    opex = 200000 * 3
    var_op = net_rev * 0.03
    op_profit = net_rev - cogs - var_op - opex
    
    irpj = gross * 0.012
    add_irpj = max(gross * 0.08 - 20000 * 3, 0) * 0.10
    csll = gross * 0.0108
    br_tax = irpj + add_irpj + csll
    net_br = op_profit - br_tax
    
    mfg = 100 * quantity * exchange
    export_before_tax = fob_usd * exchange - mfg - 350 * exchange
    fl_tax = max(export_before_tax, 0) * 0.055
    fed_tax = max(export_before_tax - fl_tax, 0) * 0.21
    net_export = export_before_tax - fl_tax - fed_tax
    
    parent_br = max(net_br, 0) * 0.75
    div_wht = parent_br * 0.10
    remit_after_tax = parent_br - div_wht
    remit_cost = remit_after_tax * 0.01
    net_remit = remit_after_tax - remit_cost
    
    branch_retained = net_br - parent_br # 25% for local partner / subsidiary retained
    total_parent = net_export + net_remit
    
    m_matriz = total_parent / gross * 100
    m_sub_br = net_br / gross * 100
    m_socio_25 = branch_retained / gross * 100
    
    return {
        'fob': fob,
        'total_parent': total_parent,
        'm_matriz': m_matriz,
        'net_br': net_br,
        'm_sub_br': m_sub_br,
        'socio_retido': branch_retained,
        'm_socio_25': m_socio_25,
        'net_export': net_export,
        'net_remit': net_remit
    }

print("FOB | Total Matriz (Margem) | Lucro BR Sub (Margem BR) | Socio 25% (Margem Socio)")
for f in range(100, 1400, 50):
    r = calc_c1(f)
    print(f"{f:4d} | R${r['total_parent']:9.0f} ({r['m_matriz']:5.2f}%) | R${r['net_br']:9.0f} ({r['m_sub_br']:5.2f}%) | R${r['socio_retido']:9.0f} ({r['m_socio_25']:5.2f}%)")
