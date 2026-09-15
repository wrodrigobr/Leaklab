# -*- coding: utf-8 -*-
"""`decisions.facing_bet` e `decisions.pot_size` sao gravados EM BB. Quem le nao divide de novo.

-- O defeito (auditoria NLU-1, 15/09) -----------------------------------------------------

`save_decisions` grava `facing_bet = facingToBb` (e o fallback antigo ja dividia por
`level_bb`). `_enrich_note` (card e lista) le a coluna como bb e escreve "aposta 8.0bb".
`_drill_context` (Ghost Table) dividia a MESMA coluna por `level_bb` de novo e escrevia
"Raise 0.0bb": a mesma linha `{facing_bet: 8.0, level_bb: 200}` virava 8.0 / 200 = 0.04.
Todo spot de drill com aposta na frente descrevia o tamanho como 0,0bb.

-- O que este arquivo defende -------------------------------------------------------------

1. A mesma linha, lida pelo drill e pela nota, sai com o MESMO numero.
2. Varredura estatica (regra 5): nenhum leitor dos modulos listados divide um valor que veio de
   `facing_bet`/`pot_size` por `level_bb`. A varredura PROVA que acha: recebe o trecho antigo
   do `_drill_context` e tem de acusar.
"""
import ast
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

# Modulos que LEEM a coluna. Quem acrescentar um leitor novo entra aqui.
MODULOS_LEITORES = [
    ('database', 'repositories.py'),
    ('api', 'app.py'),
    ('leaklab', 'llm_explainer.py'),      # deep-dive (auditoria NLU-2)
]

COLUNAS_EM_BB = ('facing_bet', 'pot_size')


def _numero_bb(texto, prefixo):
    """O numero que vem logo depois de `prefixo` (a nota tambem escreve o stack em bb)."""
    m = re.search(prefixo + r'\s*(\d+(?:\.\d+)?)bb', texto or '')
    return float(m.group(1)) if m else None


def test_drill_e_nota_leem_facing_bet_com_a_mesma_unidade():
    from database.repositories import _drill_context
    from api.app import _enrich_note
    casos = [
        dict(facing_bet=8.0, level_bb=200, street='preflop', position='BB', is_3bet=0,
             action_taken='fold', best_action='call', label='small_mistake', score=60,
             stack_bb=25.0, hero_cards='AhKs'),
        dict(facing_bet=22.5, level_bb=50, street='preflop', position='CO', is_3bet=1,
             action_taken='fold', best_action='jam', label='clear_mistake', score=1,
             stack_bb=30.0, hero_cards='QsQd'),
        dict(facing_bet=6.0, level_bb=1000, street='flop', position='BTN', is_3bet=0,
             action_taken='call', best_action='raise', label='small_mistake', score=50,
             stack_bb=40.0, hero_cards='AhKs', board='["Qd","7h","2c"]'),
    ]
    for linha in casos:
        drill = _drill_context(dict(linha))['facing_desc']
        nota = _enrich_note(dict(linha, note=''))
        n_drill = _numero_bb(drill, r'(?:Raise|Bet|3-Bet)')
        n_nota = _numero_bb(nota, r'aposta')
        assert n_drill is not None, 'drill sem tamanho: %r' % drill
        assert n_nota is not None, 'nota sem tamanho: %r' % nota[:120]
        assert n_drill == n_nota == round(linha['facing_bet'], 1), (
            'a mesma linha facing_bet=%.1f (level_bb=%d) sai %r no drill e %.1fbb na nota'
            % (linha['facing_bet'], linha['level_bb'], drill, n_nota))
        assert n_drill > 0.0, 'o drill voltou a dizer 0.0bb: %r' % drill


def test_deep_dive_e_bloco_gto_procuram_o_no_no_mesmo_bucket():
    """NLU-2: `_decision_to_gto_params` (ferramenta do agente) dividia `facing_bet` e `pot_size`
    por `level_bb`; o bloco GTO de `analyze_single_decision` usa a coluna crua. A mesma linha
    dava bucket 0-3bb numa porta e 3-8bb na outra, e dois hashes de no diferentes."""
    import json
    from leaklab.llm_explainer import _decision_to_gto_params
    from leaklab.gto_utils import bet_bucket, compute_spot_hash
    dec = {'street': 'flop', 'position': 'BTN', 'hero_cards': 'AhKs',
           'board': json.dumps(['Qd', '7h', '2c']), 'level_bb': 200, 'stack_bb': 40.0,
           'facing_bet': 8.0, 'pot_size': 12.0, 'is_3bet': 0, 'vs_position': 'BB', 'num_players': 6}
    p = _decision_to_gto_params(dec)
    facing_bloco_gto = float(dec['facing_bet'])          # llm_explainer, bloco GTO: coluna crua
    assert p['facing_size_bb'] == facing_bloco_gto == 8.0, p
    assert p['pot_bb'] == 12.0, p
    assert bet_bucket(p['facing_size_bb']) == bet_bucket(facing_bloco_gto)
    h_deep = compute_spot_hash('flop', 'BTN', ['Qd', '7h', '2c'], ['Ah', 'Ks'], 40.0, p['facing_size_bb'])
    h_gto = compute_spot_hash('flop', 'BTN', ['Qd', '7h', '2c'], ['Ah', 'Ks'], 40.0, facing_bloco_gto)
    assert h_deep == h_gto, (h_deep, h_gto)
    # e a linha sem aposta segue sem aposta
    assert _decision_to_gto_params(dict(dec, facing_bet=None, pot_size=None))['facing_size_bb'] == 0.0


def test_drill_preserva_os_rotulos_por_tipo_de_spot():
    from database.repositories import _drill_context
    assert _drill_context({'facing_bet': 8.0, 'street': 'preflop', 'is_3bet': 1})['facing_desc'] == '3-Bet 8.0bb'
    assert _drill_context({'facing_bet': 2.5, 'street': 'preflop'})['facing_desc'] == 'Raise 2.5bb'
    assert _drill_context({'facing_bet': 6.0, 'street': 'flop'})['facing_desc'] == 'Bet 6.0bb'
    assert _drill_context({'facing_bet': 0, 'street': 'preflop', 'position': 'BB'})['facing_desc'] == 'SB completou'
    assert _drill_context({'facing_bet': None, 'street': 'flop', 'position': 'BTN'})['facing_desc'] is None


def divisoes_por_level_bb(fonte):
    """Divisoes `X / level_bb` onde X veio de uma coluna em bb. Devolve [(linha, nome)].

    Segue o nome: `x = ...get('facing_bet')...` marca `x`; depois `x / level_bb` (ou
    `x / float(level_bb)`, `x / level_bb_val`) acusa. Uma atribuicao nova ao mesmo nome sem a
    coluna limpa a marca (o nome foi reutilizado com outro valor).
    """
    arvore = ast.parse(fonte)
    achados = []

    def _cita_coluna(no):
        for sub in ast.walk(no):
            if isinstance(sub, ast.Constant) and sub.value in COLUNAS_EM_BB:
                return True
        return False

    def _cita_level_bb(no):
        for sub in ast.walk(no):
            if isinstance(sub, ast.Name) and sub.id.startswith('level_bb'):
                return True
        return False

    for func in ast.walk(arvore):
        if not isinstance(func, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        marcados = set()
        for no in ast.walk(func):
            if isinstance(no, ast.Assign):
                nomes = [t.id for t in no.targets if isinstance(t, ast.Name)]
                if _cita_coluna(no.value):
                    marcados.update(nomes)
                else:
                    marcados.difference_update(nomes)
            elif isinstance(no, ast.BinOp) and isinstance(no.op, ast.Div):
                esq = no.left
                nome = esq.id if isinstance(esq, ast.Name) else None
                if nome in marcados and _cita_level_bb(no.right):
                    achados.append((no.lineno, nome))
    return achados


def test_varredura_nenhum_leitor_divide_a_coluna_em_bb_por_level_bb():
    for partes in MODULOS_LEITORES:
        caminho = os.path.join(RAIZ, *partes)
        with open(caminho, encoding='utf-8') as f:
            fonte = f.read()
        achados = divisoes_por_level_bb(fonte)
        assert not achados, '%s divide valor em bb por level_bb: %s' % ('/'.join(partes), achados)


def test_varredura_acha_o_caso_forjado():
    """Regra 1: o medidor tem de se mexer. O trecho e o `_drill_context` de antes do conserto."""
    antigo = (
        "def _drill_context(r):\n"
        "    facing   = float(r.get('facing_bet') or 0)\n"
        "    level_bb = float(r.get('level_bb') or 100)\n"
        "    if facing > 0 and level_bb > 0:\n"
        "        bb_size = round(facing / level_bb, 1)\n"
        "    return bb_size\n"
    )
    assert divisoes_por_level_bb(antigo) == [(5, 'facing')]
    deep = (
        "def _p(decision):\n"
        "    level_bb = float(decision.get('level_bb') or 0)\n"
        "    facing_chips = float(decision.get('facing_bet') or 0)\n"
        "    pot_chips = float(decision.get('pot_size') or 0)\n"
        "    return {'a': (facing_chips / level_bb) if level_bb else 0.0,\n"
        "            'b': (pot_chips / level_bb) if level_bb else 0.0}\n"
    )
    assert sorted(divisoes_por_level_bb(deep)) == [(5, 'facing_chips'), (6, 'pot_chips')]
    # E se cala quando o nome foi reutilizado com outro valor (fichas cruas do spot).
    limpo = (
        "def _s(r, spot):\n"
        "    raw = r.get('pot_size')\n"
        "    raw = spot.get('potSize') or 0\n"
        "    return round(raw / level_bb_val, 1)\n"
    )
    assert divisoes_por_level_bb(limpo) == []


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
