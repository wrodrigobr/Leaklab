"""
test_grind_mode.py — a mão inteira, e as três coisas que ela não pode fazer.

O modo percorre uma mão REAL heads-up do preflop ao river, uma decisão por vez. As mãos vêm do
acervo de TODOS os jogadores, não só das do próprio — e é isso que torna a anonimização requisito
de entrada, não acabamento de tela.

O que está travado aqui:

1. **Nenhum identificador sai no payload.** Sem `tournament_id`, sem `hand_id`, sem nick, sem data.
   O que viaja é um token opaco, e o servidor é quem sabe o que ele significa. Uma vez servido, não
   dá para despublicar da cabeça de quem viu.
2. **O board é cortado por STREET.** A coluna `board` da decisão traz as 5 cartas em TODA linha,
   inclusive no preflop. Mostrar assim entregaria o river antes de o jogador decidir no flop — o
   exercício deixaria de ser um exercício.
3. **Nenhum passo chega sem veredito possível.** Medido antes do filtro: 30% dos passos postflop
   voltavam `None` porque a mão do herói não está na `hand_table` daquela árvore. Num spot solto
   isso é um spot pulado; numa mão inteira, o jogador percorre metade e trava no meio.
"""
import json
import os
import sys
import traceback

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import leaklab.grind_mode as GM


# ── dublê do banco ────────────────────────────────────────────────────────────

def _dec(id_, street, facing=0.0, pot=4.0, board='["3h","2d","6d","9d","2h"]',
         mao='JsTd', tree='t1'):
    return {'id': id_, 'street': street, 'hero_cards': mao, 'board': board,
            'position': 'BB', 'vs_position': 'BTN', 'stack_bb': 40.0,
            'pot_size': pot, 'facing_bet': facing, 'action_taken': 'call',
            'spot_hash': 'h1', 'level_bb': 100, 'tree_hash': tree, 'spot_json': '{}'}


class _Conn:
    def __init__(self, linhas):
        self.linhas = linhas

    def execute(self, sql, params=None):
        self._sql = sql
        return self

    def fetchall(self):
        if 'gto_nodes' in self._sql:          # a query de mãos disponíveis
            return [{'tournament_id': 7, 'hand_id': 'H1', 'n': 3}]
        return [dict(l) for l in self.linhas]

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def _com(linhas):
    original = GM.get_conn
    GM.get_conn = lambda: _Conn(linhas)
    return original


_MAO = [
    _dec(1, 'preflop', facing=3.0, pot=2.0),
    _dec(2, 'flop', facing=0.0, pot=4.0),
    _dec(3, 'flop', facing=1.9, pot=5.9),
    _dec(4, 'turn', facing=0.0, pot=7.8),
    _dec(5, 'river', facing=27.1, pot=46.0),
]


# ── testes ────────────────────────────────────────────────────────────────────

def test_o_preflop_herda_o_vilao_do_postflop():
    """O preflop quase nunca guarda `vs_position` (vem o sentinela `'unknown'`), mas o postflop
    guarda. Num pote heads-up, quem estava no flop estava no preflop também.

    Sem isso a mesa ficava SEM NINGUÉM na jogada: reportado com o herói no BB, onde a regra
    "quem agiu antes do herói foldou" apagava os oito outros assentos. Dobrar todo mundo é uma
    afirmação — "todos passaram" — e ela era falsa, porque a mão seguia para o flop.
    """
    linhas = [
        _dec(1, 'preflop', facing=3.0, pot=2.0),
        _dec(2, 'flop', facing=0.0, pot=4.0),
    ]
    linhas[0]['vs_position'] = 'unknown'      # como o banco realmente grava
    linhas[1]['vs_position'] = 'BTN'
    orig = _com(linhas)
    try:
        m = GM.montar_mao(7, 'H1')
    finally:
        GM.get_conn = orig
    assert m['passos'][0]['vs_position'] == 'BTN', m['passos'][0]
    assert m['passos'][1]['vs_position'] == 'BTN'
    print('OK  test_o_preflop_herda_o_vilao_do_postflop')


def test_sentinela_unknown_nunca_chega_na_tela():
    """`vs_position` não vem VAZIO quando não há vilão: vem o literal `'unknown'`, em 3.600 linhas
    de preflop. Testar por string vazia não pega sentinela, e a tela escrevia "SB vs unknown"."""
    for sentinela in ('unknown', 'UNKNOWN', 'none', '-', '', None):
        assert GM._vilao(sentinela) == '', f'{sentinela!r} passou'
    assert GM._vilao('BTN') == 'BTN'
    linhas = [_dec(1, 'preflop'), _dec(2, 'flop')]
    for l in linhas:
        l['vs_position'] = 'unknown'
    orig = _com(linhas)
    try:
        m = GM.montar_mao(7, 'H1')
    finally:
        GM.get_conn = orig
    assert all(p['vs_position'] == '' for p in m['passos']), m['passos']
    print('OK  test_sentinela_unknown_nunca_chega_na_tela')


def test_o_payload_nao_carrega_identificador_nenhum():
    """As mãos são de OUTROS jogadores. Nick, torneio, hand_id e data não podem sair daqui."""
    orig = _com(_MAO)
    try:
        m = GM.montar_mao(7, 'H1')
    finally:
        GM.get_conn = orig
    assert m, 'não montou'
    bruto = json.dumps(m).lower()
    for proibido in ('tournament', 'hand_id', 'nick', 'player', 'villain_name', "'h1'", '"h1"'):
        assert proibido not in bruto, f'vazou {proibido!r} no payload: {bruto[:200]}'
    assert m['token'] and len(m['token']) >= 16, 'token curto demais para ser opaco'
    print('OK  test_o_payload_nao_carrega_identificador_nenhum')


def test_o_token_nao_deixa_adivinhar_a_mao():
    """Token derivado só de (torneio, mão) seria enumerável: alguém pediria o acervo inteiro por id
    sequencial. O segredo é o que impede."""
    a = GM.token_da_mao(7, 'H1')
    b = GM.token_da_mao(7, 'H2')
    c = GM.token_da_mao(8, 'H1')
    assert a != b and a != c, 'tokens colidem entre mãos diferentes'
    assert GM.token_da_mao(7, 'H1') == a, 'token não é estável'

    # O SEGREDO precisa PARTICIPAR do cálculo, e é isso que a primeira versão deste teste não
    # cobria: tirar o segredo do hash mantinha tokens distintos e estáveis, e ele passava verde.
    # Sem segredo, quem souber (torneio, mão) reproduz o token e enumera o acervo inteiro — e os
    # ids de torneio são sequenciais.
    antes = GM._SEGREDO
    try:
        GM._SEGREDO = 'outro-segredo-qualquer'
        assert GM.token_da_mao(7, 'H1') != a, 'o segredo não entra no token: ele é reproduzível'
    finally:
        GM._SEGREDO = antes
    assert GM.token_da_mao(7, 'H1') == a, 'o token mudou depois de restaurar o segredo'
    print('OK  test_o_token_nao_deixa_adivinhar_a_mao')


def test_o_board_e_cortado_por_street():
    """A coluna `board` traz as 5 cartas em TODA linha, inclusive no preflop. Sem cortar, o jogador
    veria o river antes de decidir no flop — e o exercício deixaria de existir."""
    orig = _com(_MAO)
    try:
        m = GM.montar_mao(7, 'H1')
    finally:
        GM.get_conn = orig
    esperado = {'preflop': 0, 'flop': 3, 'turn': 4, 'river': 5}
    for p in m['passos']:
        assert len(p['board']) == esperado[p['street']], (p['street'], p['board'])
    # e o river do board NÃO aparece em nenhum passo anterior
    river = m['passos'][-1]['board'][-1]
    for p in m['passos'][:-1]:
        assert river not in p['board'] or p['street'] == 'river', (p['street'], p['board'])
    print('OK  test_o_board_e_cortado_por_street')


def test_os_passos_saem_na_ordem_da_mao():
    orig = _com(list(reversed(_MAO)))       # banco devolvendo fora de ordem
    try:
        m = GM.montar_mao(7, 'H1')
    finally:
        GM.get_conn = orig
    ordem = [p['street'] for p in m['passos']]
    assert ordem == ['preflop', 'flop', 'flop', 'turn', 'river'], ordem
    print('OK  test_os_passos_saem_na_ordem_da_mao')


def test_o_menu_acompanha_haver_aposta_na_mesa():
    """Sem aposta não se oferece fold nem raise; com aposta não se oferece check. São jogadas que
    não existem, e oferecê-las ensina uma regra falsa antes de ensinar estratégia."""
    orig = _com(_MAO)
    try:
        m = GM.montar_mao(7, 'H1')
    finally:
        GM.get_conn = orig
    for p in m['passos']:
        if p['street'] == 'preflop':
            continue
        if p['facing_size_bb'] > 0:
            assert p['options'] == ['fold', 'call', 'raise'], p
        else:
            assert p['options'] == ['check', 'bet'], p
    print('OK  test_o_menu_acompanha_haver_aposta_na_mesa')


def test_a_acao_do_vilao_aparece_entre_os_passos():
    """A linha do vilão não está gravada como evento; é deduzida do pote e da aposta enfrentada.
    Sem ela, o jogador vê o pote crescer sozinho entre duas decisões."""
    orig = _com(_MAO)
    try:
        m = GM.montar_mao(7, 'H1')
    finally:
        GM.get_conn = orig
    # o passo que enfrenta 1.9bb tem que anunciar a aposta do vilão antes
    p3 = m['passos'][2]
    assert p3['facing_size_bb'] == 1.9
    assert p3['vilao_antes'] and p3['vilao_antes']['tipo'] == 'aposta', p3['vilao_antes']
    assert p3['vilao_antes']['bb'] == 1.9
    assert m['passos'][0]['vilao_antes'] is None, 'inventou ação antes do primeiro passo'
    print('OK  test_a_acao_do_vilao_aparece_entre_os_passos')


def test_mao_com_passo_nao_gradeavel_NAO_e_servida():
    """Medido antes deste filtro: 30% dos passos postflop voltavam sem veredito, porque a mão do
    herói não está na `hand_table` daquela árvore. Num spot solto isso é um spot pulado; numa mão
    inteira o jogador percorre metade e trava no meio, sem entender por quê.

    Custa acervo — 336 mãos com >=2 decisões viraram 138 gradeáveis de ponta a ponta. Vale.
    """
    chamadas = {'n': 0}
    original = GM.corrigir_passo

    def falha_no_terceiro(passo, acao):
        chamadas['n'] += 1
        return None if chamadas['n'] == 3 else {'gto_tier': 'correct'}

    GM.corrigir_passo = falha_no_terceiro
    try:
        assert GM._toda_gradeavel({'passos': [{'options': ['check', 'bet']}] * 5}) is False
        chamadas['n'] = 0
        GM.corrigir_passo = lambda p, a: {'gto_tier': 'correct'}
        assert GM._toda_gradeavel({'passos': [{'options': ['check', 'bet']}] * 5}) is True
    finally:
        GM.corrigir_passo = original
    print('OK  test_mao_com_passo_nao_gradeavel_NAO_e_servida')


def test_mao_sem_cartas_ou_sem_board_nao_vira_exercicio():
    """`hero_cards` é gravado COLADO (`'JsTd'`) enquanto `board` é JSON — duas colunas vizinhas com
    formatos diferentes. Ler as duas do mesmo jeito explodia."""
    orig = _com([_dec(1, 'flop', mao='')])
    try:
        assert GM.montar_mao(7, 'H1') is None
    finally:
        GM.get_conn = orig
    orig = _com([_dec(1, 'flop', board='[]')])
    try:
        assert GM.montar_mao(7, 'H1') is None
    finally:
        GM.get_conn = orig
    # e o formato colado é lido corretamente
    assert GM._cartas('JsTd') == ['Js', 'Td']
    assert GM._cartas('["Js","Td"]') == ['Js', 'Td']
    assert GM._cartas('') == []
    print('OK  test_mao_sem_cartas_ou_sem_board_nao_vira_exercicio')


if __name__ == '__main__':
    testes = [(k, v) for k, v in sorted(globals().items()) if k.startswith('test_')]
    ok = fail = 0
    for nome, fn in testes:
        try:
            fn()
            ok += 1
        except Exception as e:
            print(f'FAIL {nome}: {e}')
            traceback.print_exc()
            fail += 1
    print(f"\n{'='*50}")
    print(f'Total: {ok+fail} | Passed: {ok} | Failed: {fail}')
    raise SystemExit(1 if fail else 0)
