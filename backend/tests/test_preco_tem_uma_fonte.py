# -*- coding: utf-8 -*-
"""O preço do Pro tem UMA fonte, e ninguém volta a escrevê-lo à mão.

── O que originou (28/08) ──────────────────────────────────────────────────────────────────

O dono decidiu baixar o Pro de R$ 99 para R$ 39,90. Puxando o fio de "como garantimos isto", o
mesmo valor apareceu escrito à mão em **seis lugares**:

1. `PLAN_AMOUNTS` no `stripe_gateway` — a fonte legítima
2. `"R$ 99"` cravado no `Landing.tsx`
3. As chaves `checkout.preco.*` nas três traduções, mais `-17%` literal no JSX do modal
4. `"Upgrade para Pro · R$ 99"` em seis chaves de tradução
5. `9900` / `99000` em oito asserções da suíte de cobrança
6. **`paying_pro * 9900` em TRÊS cálculos financeiros do admin** (`mrr`, `past_due_risk`,
   `overview`)

O grupo 6 é o pior: são números que a tela do dono usa para decidir. Depois da mudança de preço
eles continuariam contando R$ 99 por assinante, sem erro em lugar nenhum. E nenhum deles foi achado
por auditoria — apareceram porque um teste **que não era sobre preço** quebrou.

── O que este guarda protege ───────────────────────────────────────────────────────────────

A sétima cópia. Ela vai parecer inofensiva quando alguém a escrever, exatamente como as seis.
"""
import io
import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

_RAIZ = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))


def test_o_preco_vem_de_plan_amount_e_nao_de_literal():
    """Nenhum cálculo multiplica por um preço escrito à mão."""
    suspeitas, varridos = [], 0
    # Valores em centavos que já foram (ou podem vir a ser) o preço: qualquer múltiplo redondo de
    # 10 entre 1.000 e 200.000 centavos usado numa MULTIPLICAÇÃO é candidato a preço cravado.
    padrao = re.compile(r'\*\s*(\d{4,6})\b')
    for base, _d, arqs in os.walk(_RAIZ):
        if any(x in base for x in ('.git', '__pycache__', 'node_modules', 'tests', 'scripts')):
            continue
        for a in arqs:
            if not a.endswith('.py'):
                continue
            caminho = os.path.join(base, a)
            varridos += 1
            corpo = io.open(caminho, encoding='utf-8', errors='replace').read()
            for i, linha in enumerate(corpo.split('\n'), 1):
                nu = linha.split('#')[0]
                if 'cents' not in nu.lower() and 'mrr' not in nu.lower() and 'preco' not in nu.lower():
                    continue
                m = padrao.search(nu)
                if m and int(m.group(1)) >= 1000:
                    suspeitas.append('%s:%d  %s' % (a, i, linha.strip()[:80]))
    assert varridos >= 50, 'a varredura olhou %d arquivos: não varreu nada' % varridos
    assert not suspeitas, (
        'preço em centavos escrito à mão num cálculo de dinheiro: %s. Use '
        '`_preco_mensal_cents()` / `plan_amount()`, senão o número mente depois de a próxima '
        'mudança de preço.' % suspeitas)
    print('OK  test_o_preco_vem_de_plan_amount_e_nao_de_literal (%d arquivos)' % varridos)


def test_a_varredura_ACHA_um_literal_plantado():
    """CONTRAPROVA: sem ela um regex quebrado deixa o guarda verde para sempre."""
    padrao = re.compile(r'\*\s*(\d{4,6})\b')
    assert padrao.search('        mrr_cents = paying_pro * 9900'), 'não acha o caso real'
    assert padrao.search("            'past_due_risk_cents': past_due * 9900,"), 'não acha o 2º'
    assert not padrao.search('    total = n * 12'), 'acusaria multiplicação inocente'
    print('OK  test_a_varredura_ACHA_um_literal_plantado')


def test_os_tres_calculos_do_admin_usam_a_fonte_unica():
    """Ancora na CONDIÇÃO: os três chamam a função, e não num valor que por acaso bate hoje."""
    corpo = io.open(os.path.join(_RAIZ, 'database', 'repositories.py'),
                    encoding='utf-8', errors='replace').read()
    usos = corpo.count('_preco_mensal_cents()')
    assert usos >= 4, (
        'esperava a fonte única na definição e nos três cálculos (mrr, past_due_risk, overview), '
        'achei %d usos' % usos)
    print('OK  test_os_tres_calculos_do_admin_usam_a_fonte_unica (%d usos)' % usos)


def test_a_fonte_unica_devolve_o_preco_de_verdade():
    from database.repositories import _preco_mensal_cents
    from leaklab.stripe_gateway import PLAN_AMOUNTS
    assert _preco_mensal_cents() == int(round(PLAN_AMOUNTS['pro'] * 100)), (
        'a função divergiu de PLAN_AMOUNTS')
    assert _preco_mensal_cents() > 0, 'preço zero faria o MRR sumir sem ninguém notar'
    print('OK  test_a_fonte_unica_devolve_o_preco_de_verdade (R$ %.2f)'
          % (_preco_mensal_cents() / 100))


if __name__ == '__main__':
    falhas = 0
    testes = [v for k, v in sorted(globals().items()) if k.startswith('test_')]
    for teste in testes:
        try:
            teste()
        except AssertionError as e:
            falhas += 1
            print('FALHOU  %s: %s' % (teste.__name__, e))
        except Exception as e:                              # noqa: BLE001
            falhas += 1
            print('ERRO    %s: %s: %s' % (teste.__name__, type(e).__name__, e))
    print('\nTotal: %d | Passed: %d | Failed: %d' % (len(testes), len(testes) - falhas, falhas))
    sys.exit(1 if falhas else 0)
