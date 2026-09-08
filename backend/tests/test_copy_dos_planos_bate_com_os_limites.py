# -*- coding: utf-8 -*-
"""A copy da landing sobre torneios por mes tem de bater com PLAN_LIMITS (08/09/2026).

O FAQ dizia "2 torneios por mes" no Free (q5/a5) enquanto o card do plano dizia 30 e o backend
dava 30 (`PLAN_LIMITS['free']['tournaments']`). A copy do card foi atualizada em 28/08 e o FAQ
nao. Achado pelo agente que comparou o produto com o concorrente, nao por ninguem olhando a tela.

Este arquivo varre `landing.json` nos 3 idiomas: todo numero seguido de "torneios/tournaments/
torneos por mes/per month" tem de ser um dos limites de plano do backend.
"""
import io
import json
import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
os.environ.pop('DATABASE_URL', None)

from database.repositories import PLAN_LIMITS                                   # noqa: E402

_LOCALES = os.path.join(os.path.dirname(__file__), '..', '..', 'frontend', 'src', 'i18n', 'locales')
_PADRAO = re.compile(r'(\d+)\s+(?:torneios?|tournaments?|torneos?)\s+(?:por\s+m[eê]s|per\s+month)', re.I)


def _textos(d, pref=''):
    for k, v in d.items():
        kk = pref + k
        if isinstance(v, dict):
            yield from _textos(v, kk + '.')
        elif isinstance(v, str):
            yield kk, v


def test_todo_numero_de_torneios_por_mes_na_landing_e_um_limite_de_plano():
    limites = {int(v['tournaments']) for v in PLAN_LIMITS.values() if v.get('tournaments')}
    assert 30 in limites, limites
    erros, vistos = [], 0
    for loc in ('pt-BR', 'en', 'es'):
        d = json.load(io.open(os.path.join(_LOCALES, loc, 'landing.json'), encoding='utf-8'))
        for chave, txt in _textos(d):
            for m in _PADRAO.finditer(txt):
                vistos += 1
                if int(m.group(1)) not in limites:
                    erros.append('%s %s: "%s" (limites do backend: %s)' % (loc, chave, m.group(0), sorted(limites)))
    assert vistos >= 6, 'o varredor nao achou a copy dos planos (%d ocorrencias)' % vistos
    assert not erros, 'copy da landing fora dos limites de plano:\n  ' + '\n  '.join(erros)


def test_o_varredor_acha_o_caso_que_originou():
    assert [m.group(1) for m in _PADRAO.finditer('Free: 2 torneios por mês, 15 análises. Pro: 200 tournaments per month; 30 torneos por mes.')] == ['2', '200', '30']


if __name__ == '__main__':
    falhas = 0
    testes = [v for k, v in sorted(globals().items()) if k.startswith('test_')]
    for t in testes:
        try:
            t()
            print('OK  %s' % t.__name__)
        except AssertionError as e:
            falhas += 1
            print('FALHOU  %s: %s' % (t.__name__, e))
        except Exception as e:                                  # noqa: BLE001
            falhas += 1
            print('ERRO    %s: %s: %s' % (t.__name__, type(e).__name__, e))
    print('\nTotal: %d | Passed: %d | Failed: %d' % (len(testes), len(testes) - falhas, falhas))
    sys.exit(1 if falhas else 0)
