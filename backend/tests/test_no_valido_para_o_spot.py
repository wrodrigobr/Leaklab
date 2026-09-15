# -*- coding: utf-8 -*-
"""O menu de um no GTO tem de caber no spot, nas TRES portas que servem menu.

-- O defeito (auditoria NLU-2, 2a metade, 15/09) -------------------------------------------

A regra de FORMA do menu (RC-5/6, 17/08) vivia copiada em dois lugares de `api/app.py`:
`_valid_node` (card/drill) e `_valid_node_replayer` (/replay). Faltava na terceira porta, a
ferramenta `get_gto_solution` do deep-dive, que entrega o menu DIRETO ao LLM.

Enquanto o hash do deep-dive estava errado (1a metade do NLU-2) a porta quase nunca achava no,
e a falta do guarda nao aparecia. Consertado o hash, ela passou a achar: um no de first-to-act
servido a um spot vs-aposta faria o texto recomendar 'check' onde nao ha botao de check. E o
risco da regra 7 da casa (o conserto causando dano que o bug nao causava), e por isso a regra
virou UMA funcao (`gto_utils.no_valido_para_o_spot`) chamada pelas tres.

-- O que este arquivo defende --------------------------------------------------------------

1. As duas impossibilidades estruturais, na funcao unica, e o que NAO pode ser rejeitado.
2. A porta do deep-dive recusa o no incoerente (found=false) e serve o coerente.
3. Varredura (regra 5): as N+1 portas chamam a funcao unica e nenhuma guarda uma copia inline.
   A varredura PROVA que acha: recebe o fonte de antes do conserto e tem de acusar.
"""
import ast
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

try:
    import flask_cors  # noqa: F401
except ImportError:
    import unittest.mock as mock
    sys.modules['flask_cors'] = mock.MagicMock()
    sys.modules['flask_cors'].CORS = lambda app, **kw: None

RAIZ = os.path.join(os.path.dirname(__file__), '..')

# As portas que servem MENU de no a alguem. Quem abrir uma quarta entra aqui.
PORTAS = [
    (('api', 'app.py'), '_valid_node'),                        # card e drill
    (('api', 'app.py'), '_valid_node_replayer'),               # /replay
    (('leaklab', 'llm_explainer.py'), '_run_deepdive_tool'),   # ferramenta do agente
]
FONTE_UNICA = ('no_valido_para_o_spot', 'menu_coerente_com_o_spot')


def _no(**kw):
    base = dict(street='flop', board=json.dumps(['Kh', '7d', '2c']), gto_action='call',
                strategy_json=json.dumps({'call': 0.6, 'fold': 0.4}))
    base.update(kw)
    return base


def test_menu_com_check_nao_serve_spot_vs_aposta():
    from leaklab.gto_utils import no_valido_para_o_spot, menu_coerente_com_o_spot
    n = _no(strategy_json=json.dumps({'check': 0.72, 'bet_50pct': 0.28}))
    assert no_valido_para_o_spot(n, 'flop', ['Kh', '7d', '2c'], 3.0) is None
    ok, motivo = menu_coerente_com_o_spot({'check', 'bet_50pct'}, 'flop', 3.0)
    assert ok is False and motivo == 'menu_de_first_to_act_em_spot_vs_aposta', motivo
    # Sem aposta, o MESMO menu e legitimo.
    assert no_valido_para_o_spot(n, 'flop', ['Kh', '7d', '2c'], 0.0) is n


def test_menu_com_fold_nao_serve_spot_postflop_sem_aposta():
    from leaklab.gto_utils import no_valido_para_o_spot, menu_coerente_com_o_spot
    n = _no(strategy_json=json.dumps({'fold': 0.55, 'call': 0.45}))
    assert no_valido_para_o_spot(n, 'flop', ['Kh', '7d', '2c'], 0.0) is None
    ok, motivo = menu_coerente_com_o_spot({'fold', 'call'}, 'flop', 0.0)
    assert ok is False and motivo == 'menu_vs_aposta_em_spot_sem_aposta', motivo
    # Preflop fica FORA: open-fold e legal com facing 0.
    ok_pre, _ = menu_coerente_com_o_spot({'fold', 'raise'}, 'preflop', 0.0)
    assert ok_pre is True


def test_street_e_board_divergentes_sao_rejeitados():
    from leaklab.gto_utils import no_valido_para_o_spot
    assert no_valido_para_o_spot(_no(street='turn'), 'flop', ['Kh', '7d', '2c'], 3.0) is None
    assert no_valido_para_o_spot(_no(board=json.dumps(['2s', '3s', '4s'])),
                                 'flop', ['Kh', '7d', '2c'], 3.0) is None
    # Ordem do board nao importa; o no coerente passa.
    assert no_valido_para_o_spot(_no(), 'flop', ['2c', 'Kh', '7d'], 3.0) is not None


def test_menu_cai_no_gto_action_quando_nao_ha_strategy_json():
    from leaklab.gto_utils import acoes_do_no, no_valido_para_o_spot
    n = _no(strategy_json=None, gto_action='CHECK')
    assert acoes_do_no(n) == {'check'}
    assert no_valido_para_o_spot(n, 'flop', ['Kh', '7d', '2c'], 3.0) is None


def _deepdive(menu, facing_bet):
    """Roda a ferramenta do agente com um lookup_gto dublado que devolve `menu`."""
    import leaklab.gto_solver as gs
    from leaklab.llm_explainer import _run_deepdive_tool
    original = gs.lookup_gto
    gs.lookup_gto = lambda **kw: {
        'found': True, 'source': 'postflop_db', 'exploitability_pct': 0.4,
        'strategy': [{'action': a, 'frequency': f} for a, f in menu.items()],
    }
    try:
        dec = {'street': 'flop', 'position': 'BTN', 'board': json.dumps(['Kh', '7d', '2c']),
               'hero_cards': 'AsQs', 'stack_bb': 30.0, 'facing_bet': facing_bet,
               'pot_size': 9.0, 'num_players': 2}
        return json.loads(_run_deepdive_tool('get_gto_solution', dec, 9601))
    finally:
        gs.lookup_gto = original


def test_deepdive_recusa_menu_que_nao_cabe_no_spot():
    fora = _deepdive({'check': 0.7, 'bet_50pct': 0.3}, 3.0)
    assert fora.get('found') is False, fora
    assert fora.get('motivo') == 'menu_de_first_to_act_em_spot_vs_aposta', fora
    sem_aposta = _deepdive({'fold': 0.5, 'call': 0.5}, 0.0)
    assert sem_aposta.get('found') is False, sem_aposta


def test_deepdive_serve_o_menu_coerente():
    dentro = _deepdive({'call': 0.6, 'fold': 0.4}, 3.0)
    assert dentro.get('found') is True, dentro
    assert {a['action'] for a in dentro['strategy']} == {'call', 'fold'}, dentro


# -- Varredura das N+1 portas (regra 5) ------------------------------------------------------

def portas_sem_fonte_unica(fonte, nomes):
    """Nomes de funcao, entre `nomes`, cujo corpo nao chama a funcao unica do guarda."""
    arvore = ast.parse(fonte)
    achadas, faltantes = set(), []
    for no in ast.walk(arvore):
        if isinstance(no, (ast.FunctionDef, ast.AsyncFunctionDef)) and no.name in nomes:
            achadas.add(no.name)
            corpo = ast.dump(no)
            if not any(f in corpo for f in FONTE_UNICA):
                faltantes.append(no.name)
    for n in nomes:
        if n not in achadas:
            faltantes.append('%s: funcao NAO ENCONTRADA' % n)
    return sorted(faltantes)


def copias_inline_do_guarda(fonte):
    """Linhas que reimplementam a regra em vez de chamar a fonte unica."""
    achados = []
    for i, linha in enumerate(fonte.splitlines(), 1):
        t = linha.strip()
        if t.startswith('#'):
            continue
        if "'check' in" in t and 'facing' in t:
            achados.append((i, t))
        if "'fold' in" in t and 'preflop' in t:
            achados.append((i, t))
    return achados


def test_varredura_as_tres_portas_chamam_a_fonte_unica():
    por_arquivo = {}
    for partes, nome in PORTAS:
        por_arquivo.setdefault(partes, []).append(nome)
    for partes, nomes in por_arquivo.items():
        with open(os.path.join(RAIZ, *partes), encoding='utf-8') as f:
            fonte = f.read()
        faltam = portas_sem_fonte_unica(fonte, nomes)
        assert not faltam, '%s: %s' % ('/'.join(partes), faltam)


def test_varredura_nenhuma_copia_inline_do_guarda_sobrou():
    arquivos = {partes for partes, _ in PORTAS} | {('leaklab', 'gto_solver.py')}
    for partes in arquivos:
        with open(os.path.join(RAIZ, *partes), encoding='utf-8') as f:
            fonte = f.read()
        achados = copias_inline_do_guarda(fonte)
        assert not achados, '%s reimplementa o guarda: %s' % ('/'.join(partes), achados)


def test_varredura_acha_o_caso_forjado():
    """Regra 1: o medidor tem de se mexer. Os trechos sao os de ANTES do conserto."""
    antigo = (
        "def _valid_node_replayer(n):\n"
        "    if not n:\n"
        "        return None\n"
        "    if facing_bb > 0 and 'check' in _acts:\n"
        "        return None\n"
        "    return n\n"
    )
    assert portas_sem_fonte_unica(antigo, ['_valid_node_replayer']) == ['_valid_node_replayer']
    assert copias_inline_do_guarda(antigo) == [(4, "if facing_bb > 0 and 'check' in _acts:")]
    ausente = "def outra(n):\n    return n\n"
    assert portas_sem_fonte_unica(ausente, ['_valid_node']) == [
        '_valid_node: funcao NAO ENCONTRADA']
    consertado = (
        "def _valid_node(n):\n"
        "    from leaklab.gto_utils import no_valido_para_o_spot\n"
        "    return no_valido_para_o_spot(n, street, board_for_hash, facing_bb)\n"
    )
    assert portas_sem_fonte_unica(consertado, ['_valid_node']) == []
    assert copias_inline_do_guarda(consertado) == []


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
