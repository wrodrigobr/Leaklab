# -*- coding: utf-8 -*-
"""Nenhum limite de plano fica cravado no front: todos vem do backend.

-- O defeito (auditoria NLU-10, 15/09) -----------------------------------------------------

Dois numeros de plano viviam escritos no frontend, e nenhum dos dois batia com o
`PLAN_LIMITS` de `database/repositories.py`:

  * `AccountMenu.tsx` caia em `{ tournaments: 3, ai_calls: 10 }` sem `plan_limits` no payload.
    O free do backend e 30 torneios e 15 analises: a barra desenhava "2/3 usado, quase no teto"
    para quem tinha 28 de folga.
  * `AdminDashboard.tsx` cravava `PLAN_TETO = { free: 30, pro: 200, coach: 200 }`. O coach do
    backend tem `tournaments: None`, sem teto: o admin via um coach com 200+ torneios pintado de
    vermelho enquanto as duas portas de cota (`_check_upload_quota` e
    `reivindicar_com_cota_liberada`) nunca o barram.

-- O que este arquivo defende --------------------------------------------------------------

1. `/subscription/plans` serve `tournaments` e `ai_calls` de cada plano que lista, direto do
   `PLAN_LIMITS` (e a fonte que o front passou a consultar).
2. Varredura (regra 5): os arquivos do front que falam de plano nao cravam numero de limite.
   A varredura PROVA que acha: recebe os dois trechos de antes do conserto e acusa os dois.
"""
import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

try:
    import flask_cors  # noqa: F401
except ImportError:
    import unittest.mock as mock
    sys.modules['flask_cors'] = mock.MagicMock()
    sys.modules['flask_cors'].CORS = lambda app, **kw: None

RAIZ = os.path.join(os.path.dirname(__file__), '..')
FRONT = os.path.abspath(os.path.join(RAIZ, '..', 'frontend', 'src'))

# Arquivos do front que exibem limite de plano. Quem exibir um novo entra aqui.
ARQUIVOS = [
    os.path.join('components', 'hud', 'AccountMenu.tsx'),
    os.path.join('pages', 'admin', 'AdminDashboard.tsx'),
]

# Os nomes de campo de limite. Um numero literal ao lado de qualquer um deles e um teto cravado.
CAMPOS = ('tournaments', 'ai_calls', 'ai_calls_limit', 'tournaments_limit')


def tetos_cravados(fonte):
    """(linha, trecho) de cada limite de plano escrito como numero no fonte do front."""
    achados = []
    for i, linha in enumerate(fonte.splitlines(), 1):
        t = linha.strip()
        if t.startswith('//') or t.startswith('*') or t.startswith('/*'):
            continue
        for campo in CAMPOS:
            if re.search(r'\b%s\s*:\s*\d+' % re.escape(campo), t):
                achados.append((i, t[:110]))
                break
        else:
            # `PLAN_TETO = { free: 30, pro: 200 }` e a outra forma: nome de plano -> numero.
            # Sem heuristica de vizinhanca: a primeira versao deste medidor exigia a palavra
            # "PLAN" nas linhas anteriores, passou no caso FORJADO (o comentario dizia "plano")
            # e calou no arquivo de verdade. Regra 1 da casa, aprendida aqui.
            if re.search(r'\b(free|pro|coach)\s*:\s*\d+', t):
                achados.append((i, t[:110]))
    return achados


def test_a_rota_de_planos_serve_os_limites():
    """Sem estes campos o front recebe vazio e volta a precisar de numero proprio."""
    from database.repositories import PLAN_LIMITS
    import api.app as A
    A.app.config['TESTING'] = True
    r = A.app.test_client().get('/subscription/plans')
    assert r.status_code == 200, r.status_code
    planos = {p['id']: p for p in r.get_json()['plans']}
    assert planos, 'a rota nao listou plano nenhum'
    for pid, p in planos.items():
        assert 'tournaments' in p and 'ai_calls' in p, '%s sem os limites: %s' % (pid, sorted(p))
        assert p['tournaments'] == PLAN_LIMITS[pid]['tournaments'], pid
        assert p['ai_calls'] == PLAN_LIMITS[pid]['ai_calls'], pid


def test_o_coach_nao_tem_teto_de_torneios_no_backend():
    """O numero que o front cravava (coach: 200) contradizia isto."""
    from database.repositories import PLAN_LIMITS
    assert PLAN_LIMITS['coach']['tournaments'] is None, PLAN_LIMITS['coach']['tournaments']


def test_varredura_o_front_nao_crava_limite_de_plano():
    for rel in ARQUIVOS:
        caminho = os.path.join(FRONT, rel)
        with open(caminho, encoding='utf-8') as f:
            achados = tetos_cravados(f.read())
        assert not achados, '%s crava limite de plano: %s' % (rel, achados)


def test_varredura_acha_os_casos_forjados():
    """Regra 1: o medidor tem de se mexer. Os trechos sao os de antes do conserto."""
    menu = 'const limits    = user.plan_limits ?? { tournaments: 3, ai_calls: 10 };\n'
    assert len(tetos_cravados(menu)) == 1, tetos_cravados(menu)
    admin = ('/** Teto de torneios/mes de cada plano */\n'
             'const PLAN_TETO: Record<string, number> = { free: 30, pro: 200, coach: 200 };\n')
    assert len(tetos_cravados(admin)) == 1, tetos_cravados(admin)
    # e cala no consertado
    limpo = ('const limits    = user.plan_limits;\n'
             'for (const p of data?.plans ?? []) out[p.id] = p.tournaments;\n')
    assert tetos_cravados(limpo) == [], tetos_cravados(limpo)
    # comentario que CITA o numero antigo nao conta como teto cravado
    comentario = '  // O literal antigo (3 torneios e 10 analises) nao era limite de plano nenhum\n'
    assert tetos_cravados(comentario) == []


if __name__ == '__main__':
    falhas = 0
    testes = [v for k, v in sorted(globals().items()) if k.startswith('test_')]
    for t in testes:
        try:
            t()
            print('OK      %s' % t.__name__)
        except AssertionError as e:
            falhas += 1
            print('FALHOU  %s: %s' % (t.__name__, e))
        except Exception as e:
            falhas += 1
            print('ERRO    %s: %s: %s' % (t.__name__, type(e).__name__, e))
    print('\nTotal: %d | Passed: %d | Failed: %d' % (len(testes), len(testes) - falhas, falhas))
    sys.exit(1 if falhas else 0)
