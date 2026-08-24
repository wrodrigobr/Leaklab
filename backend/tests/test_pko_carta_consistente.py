# -*- coding: utf-8 -*-
"""PKO consulta OUTRA carta preflop — e todos os caminhos precisam consultar a mesma.

── O caso que originou (23/08, auditoria pré-lançamento) ──────────────────────────────────

Um jogador auditando o torneio 3980940107 viu, no MESMO card:

    veredito:  "Erro — ação esperada: RAISE"   (gto_critical, gto_played_freq 0.0)
    matriz:    K7s → fold 69,9% / raise 30,1%  (action_quality "correct", custo 0.0bb)

As duas leituras vinham de cartas DIFERENTES. `preflop_strategy(..., is_pko: bool = False)`
tem o argumento com default, e só `decision_engine_v11` o passava — justamente o caminho que
PERSISTE `gto_label` e `best_action`. Card, matriz, replay e o sync liam a carta Classic.

Prova reproduzível (K7s, UTG, 70.9bb, 8 jogadores):

    is_pko=True  → raise 100%, fold 0%
    is_pko=False → raise 30,1%, fold 69,9%

23 dos 87 torneios do acervo são PKO — 26%.

── Por que este teste existe, se `test_todo_caminho_mesmos_args` já cobre argumentos ───────

Aquele guarda é SINTÁTICO: confere que a chamada menciona o argumento. Ele ficou verde durante
todo o tempo em que o defeito rodou (porque `is_pko` não estava na lista), e depois de eu
acrescentá-lo ele voltaria a ficar verde com `is_pko=dec.get('is_pko')` — que é sempre False,
porque `decisions` NÃO TEM essa coluna. Passar o argumento com o valor errado satisfaz o
guarda sintático e não conserta nada.

Este teste é SEMÂNTICO: exige que as duas cartas sejam de fato diferentes (senão o argumento
não decide nada e o teste inteiro é decorativo) e que a flag chegue viva pela porta de dados.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))


def test_a_carta_PKO_e_diferente_da_classic():
    """Prova de detecção. Se as duas cartas fossem iguais, todo o resto seria teatro: o
    argumento não mudaria nada e um `is_pko` errado passaria despercebido para sempre."""
    from leaklab.strategy_provider import preflop_strategy

    comum = dict(position='UTG', hand='K7s', stack_bb=70.9, action_taken='fold', n_players=8)
    pko = preflop_strategy(is_pko=True, **comum).get('hand_freq') or {}
    classic = preflop_strategy(is_pko=False, **comum).get('hand_freq') or {}

    assert pko and classic, 'uma das cartas não respondeu — o teste perdeu o alvo'
    assert pko != classic, (
        'a carta PKO e a Classic devolveram a MESMA estratégia para K7s/UTG/70.9bb. Ou a carta '
        'PKO sumiu, ou o argumento parou de ser lido: nos dois casos este arquivo inteiro vira '
        'decoração, porque nada mais depende de `is_pko`.')
    print('OK  test_a_carta_PKO_e_diferente_da_classic (pko=%s classic=%s)'
          % (pko.get('raise'), classic.get('raise')))


def test_get_decision_spot_entrega_a_flag_de_PKO():
    """A flag vive em `tournaments`, não em `decisions`. `get_decision_spot` já fazia o JOIN;
    faltava trazer a coluna. Sem ela, `dec.get('is_pko')` é sempre None → sempre Classic."""
    import inspect
    from database import repositories

    fonte = inspect.getsource(repositories.get_decision_spot)
    assert 'is_pko' in fonte, (
        'get_decision_spot parou de trazer is_pko. O endpoint /replay/<id>/gto passa a consultar '
        'a carta Classic em torneio PKO, e o card volta a contradizer o veredito gravado.')
    assert 'tournaments' in fonte, 'o JOIN com tournaments sumiu — a flag não tem de onde vir'
    print('OK  test_get_decision_spot_entrega_a_flag_de_PKO')


def test_o_sync_nao_reescreve_PKO_com_a_carta_classic():
    """O sync REESCREVE `gto_label` no banco. Sem `is_pko` ele desfaz, em massa, o veredito que
    o motor gravou pela carta certa — e o mesmo torneio muda de veredito conforme o sync tenha
    rodado ou não."""
    caminho = os.path.join(os.path.dirname(__file__), '..', 'scripts',
                           'sync_gto_labels_from_ranges.py')
    with open(caminho, encoding='utf-8') as fh:
        fonte = fh.read()
    assert 'pko_by_tid' in fonte, 'o sync não carrega mais a flag de PKO por torneio'
    assert 'is_pko=pko_by_tid' in fonte, (
        'o sync voltou a chamar a porta única sem `is_pko` — vai reescrever torneio PKO com a '
        'carta Classic')
    print('OK  test_o_sync_nao_reescreve_PKO_com_a_carta_classic')


def test_nenhum_caminho_passa_is_pko_constante():
    """O conserto tem que LER a flag, não fixá-la. `is_pko=False` cravado satisfaz o guarda
    sintático e mantém o defeito — foi exatamente o risco desta correção."""
    import re
    raiz = os.path.join(os.path.dirname(__file__), '..')
    suspeitos = []
    for pasta in ('api', 'leaklab', 'scripts'):
        base = os.path.join(raiz, pasta)
        for atual, _, nomes in os.walk(base):
            for nome in nomes:
                if not nome.endswith('.py'):
                    continue
                caminho = os.path.join(atual, nome)
                with open(caminho, encoding='utf-8') as fh:
                    for n, linha in enumerate(fh, 1):
                        if re.search(r'is_pko\s*=\s*(True|False)\s*[,)]', linha) \
                                and 'def ' not in linha:
                            suspeitos.append('%s/%s:%d  %s' % (pasta, nome, n, linha.strip()))
    assert not suspeitos, ('`is_pko` passado como constante (o valor tem que vir do torneio):\n  '
                           + '\n  '.join(suspeitos))
    print('OK  test_nenhum_caminho_passa_is_pko_constante')


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
