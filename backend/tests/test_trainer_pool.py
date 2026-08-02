"""
test_trainer_pool.py — o acervo de nós solvados vira exercício sem ensinar errado.

Backlog #41. O Leak Trainer postflop servia UM catálogo estático de 31 spots, todos com os mesmos
parâmetros. `gto_nodes` tem 5.139 nós servíveis em produção. Este módulo faz a ponte.

Os testes usam nós SINTÉTICOS de propósito: o acervo real muda a cada torneio importado, e teste
que depende dele passa a medir o banco em vez de medir o código. Os números reais de produção
estão no CHANGELOG e na docstring do módulo.

O que está travado aqui, e por quê:

1. **A resposta certa não pode ter uma constante vencedora.** No acervo cru, "check" é a resposta
   de 56% dos nós — servindo ao acaso, o jogador acerta 56% sem olhar o board. É a cicatriz do
   quiz vencível sem ler que está no CLAUDE.md. A seleção sorteia a AÇÃO antes do nó.
2. **O veredito nunca cita ação fora do menu.** Aconteceu no desenvolvimento: uma tentativa de
   gradear por `lookup_gto` resolveu OUTRO nó e respondeu "o certo era fold" numa tela que
   oferecia check/bet. Veredito sobre outro nó é pior que veredito nenhum.
3. **Sem aposta na mesa não se oferece raise.** O normalizador do trainer manda todo `bet_50pct`
   para 'raise' porque o catálogo antigo só tinha spots enfrentando aposta.
4. **Board na ordem original.** O de `gto_nodes` vem ordenado; num river isso troca qual carta foi
   o turn e qual foi o river.
5. **Nó não gradeável não chega ao jogador.** 34% dos nós têm a mão do herói fora da `hand_table`
   (uma tabela por árvore, do range de um jogador só) — filtro na SELEÇÃO, não na correção.
"""
import json
import os
import random
import sys
import traceback

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import leaklab.trainer_pool as TP


# ── nós sintéticos ────────────────────────────────────────────────────────────

def _no(street='flop', pos='BB', board=None, mao='JsTd', acao='check', freq=0.8,
        facing=0.0, acoes=None, tabela_mao=None, exploit=1.2, hash_='h1'):
    board = board or ['Ks', '6c', '7d']
    acoes = acoes or ['check', 'bet_50pct']
    mao_l = [mao[0:2], mao[2:4]]
    tab = tabela_mao if tabela_mao is not None else [
        {'hand': mao, 'weight': 10.0, 'freqs': [freq, round(1 - freq, 3)], 'evs': [2.0, 1.0]}]
    return {
        'spot_hash': hash_, 'street': street, 'position': pos,
        'board': json.dumps(sorted(board)), 'hero_hand': json.dumps(mao_l),
        'stack_bucket': '35-60bb', 'gto_action': acao, 'gto_freq': freq,
        'exploitability_pct': exploit, 'tree_hash': 't_' + hash_,
        'actions': json.dumps(acoes),
        'spot_json': json.dumps({'board': board, 'hero_hand': mao_l, 'effective_stack_bb': 40.0,
                                 'hero_stack_bb': 40.0, 'facing_size_bb': facing, 'pot_bb': 5.0,
                                 'position': pos, 'street': street,
                                 '_meta': {'vs_position': 'BTN'}}),
        '_tabela': tab,
    }


class _ConnFalsa:
    """Dublê do banco: devolve os nós dados e a árvore de cada um."""
    def __init__(self, nos):
        self.nos = nos
        self.por_tree = {n['tree_hash']: n for n in nos}

    def execute(self, sql, params=None):
        self._ultimo = (sql, params)
        return self

    def fetchall(self):
        sql = self._ultimo[0]
        if 'gto_tree_strategies WHERE' in sql:
            return []
        return [dict(n) for n in self.nos]

    def fetchone(self):
        sql, params = self._ultimo
        if 'hand_table' in sql:
            n = self.por_tree.get((params or (None,))[0])
            if not n:
                return None
            return {'actions': n['actions'], 'hand_table': json.dumps(n['_tabela'])}
        return None

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def _com_nos(nos):
    original = TP.get_conn
    TP.get_conn = lambda: _ConnFalsa(nos)
    return original


# ── testes ────────────────────────────────────────────────────────────────────

def test_board_sai_na_ordem_original_nao_na_ordenada():
    """`gto_nodes.board` vem ORDENADO. Num river isso troca qual carta foi o turn e qual foi o
    river, e a mão que o jogador lê deixa de ser a que o solver resolveu."""
    ordem_real = ['5d', 'Jd', '9h', '6c', 'Jc']
    n = _no(street='river', board=ordem_real, mao='AsQd',
            acoes=['check', 'bet_75pct'],
            tabela_mao=[{'hand': 'AsQd', 'weight': 9, 'freqs': [0.8, 0.2], 'evs': [1, 0]}])
    orig = _com_nos([n])
    try:
        s = TP.proximo_spot(rng=random.Random(1))
        assert s is not None, 'nao montou o spot'
        assert s['board'] == ordem_real, f"board reordenado: {s['board']}"
        assert s['board'] != sorted(ordem_real), 'saiu ordenado'
    finally:
        TP.get_conn = orig
    print('OK  test_board_sai_na_ordem_original_nao_na_ordenada')


def test_board_e_cortado_pela_street():
    n = _no(street='flop', board=['Ks', '6c', '7d', '2h', '9s'])
    orig = _com_nos([n])
    try:
        s = TP.proximo_spot(rng=random.Random(1))
        assert len(s['board']) == 3, s['board']
    finally:
        TP.get_conn = orig
    print('OK  test_board_e_cortado_pela_street')


def test_sem_aposta_na_mesa_o_menu_diz_bet_e_nao_raise():
    """Oferecer 'raise' onde ninguém apostou é pedir que o jogador aumente uma aposta que não
    existe. O normalizador do trainer sozinho não sabe disso."""
    orig = _com_nos([_no(facing=0.0, acoes=['check', 'bet_50pct'])])
    try:
        s = TP.proximo_spot(rng=random.Random(1))
        assert s['options'] == ['check', 'bet'], s['options']
        g = TP.corrigir(s, 'bet')
        assert g['best_action'] in ('check', 'bet'), g['best_action']
        nomeadas = {d['action'] for d in g['gto_strategy']}
        assert nomeadas <= set(s['options']), (nomeadas, s['options'])
    finally:
        TP.get_conn = orig
    print('OK  test_sem_aposta_na_mesa_o_menu_diz_bet_e_nao_raise')


def test_enfrentando_aposta_o_menu_mantem_raise():
    orig = _com_nos([_no(facing=1.65, acao='call', acoes=['fold', 'call', 'raise_50pct'],
                         tabela_mao=[{'hand': 'JsTd', 'weight': 9,
                                      'freqs': [0.2, 0.6, 0.2], 'evs': [0, 2, 1]}])])
    try:
        s = TP.proximo_spot(rng=random.Random(1))
        assert 'raise' in s['options'] and 'bet' not in s['options'], s['options']
    finally:
        TP.get_conn = orig
    print('OK  test_enfrentando_aposta_o_menu_mantem_raise')


def test_veredito_nunca_cita_acao_fora_do_menu():
    """O invariante que nasceu de um erro real: gradear por outro caminho resolveu OUTRO nó e
    respondeu 'o certo era fold' numa tela que oferecia check/bet."""
    nos = [_no(hash_=f'h{i}', facing=(1.65 if i % 2 else 0.0),
               acao=('call' if i % 2 else 'check'),
               acoes=(['fold', 'call', 'raise_50pct'] if i % 2 else ['check', 'bet_50pct']),
               tabela_mao=[{'hand': 'JsTd', 'weight': 9,
                            'freqs': ([0.2, 0.5, 0.3] if i % 2 else [0.7, 0.3]),
                            'evs': ([0, 2, 1] if i % 2 else [2, 1])}])
           for i in range(8)]
    orig = _com_nos(nos)
    try:
        rng = random.Random(5)
        for _ in range(40):
            s = TP.proximo_spot(rng=rng)
            assert s is not None
            for a in s['options']:
                g = TP.corrigir(s, a)
                assert g is not None, 'servido sem veredito'
                nomeadas = ({g['best_action']} | set(g['recommended'])
                            | {d['action'] for d in g['gto_strategy']})
                fora = {x for x in nomeadas if x} - set(s['options'])
                assert not fora, f'veredito cita {sorted(fora)} fora do menu {s["options"]}'
    finally:
        TP.get_conn = orig
    print('OK  test_veredito_nunca_cita_acao_fora_do_menu')


def test_menu_impossivel_na_mesa_nao_e_servido():
    """Nó cuja lista de ações não bate com o `facing_size_bb` gravado.

    Este teste nasceu de uma quebra deliberada que NÃO acusou: eu tinha uma checagem de coerência
    que nenhum nó sintético conseguia violar, porque menu e estratégia saíam da mesma lista. Ou
    seja, cobertura sem cobrir. Os casos abaixo são incoerências que existem de verdade no acervo:
    oferecer FOLD sem ninguém ter apostado, e oferecer CHECK com aposta na mesa. Nenhuma das duas
    é jogada possível, e servir uma delas é ensinar uma regra falsa antes de ensinar estratégia.
    """
    sem_aposta_com_fold = _no(
        hash_='ff', facing=0.0, acoes=['fold', 'check', 'bet_50pct'],
        tabela_mao=[{'hand': 'JsTd', 'weight': 9, 'freqs': [0.1, 0.6, 0.3], 'evs': [0, 2, 1]}])
    orig = _com_nos([sem_aposta_com_fold])
    try:
        assert TP.proximo_spot(rng=random.Random(1)) is None, 'serviu fold sem aposta na mesa'
    finally:
        TP.get_conn = orig

    com_aposta_com_check = _no(
        hash_='cc', facing=1.65, acoes=['check', 'call', 'raise_50pct'],
        tabela_mao=[{'hand': 'JsTd', 'weight': 9, 'freqs': [0.2, 0.5, 0.3], 'evs': [0, 2, 1]}])
    orig = _com_nos([com_aposta_com_check])
    try:
        assert TP.proximo_spot(rng=random.Random(1)) is None, 'serviu check com aposta na mesa'
    finally:
        TP.get_conn = orig
    print('OK  test_menu_impossivel_na_mesa_nao_e_servido')


def test_no_sem_a_mao_na_tabela_nao_e_servido():
    """34% do acervo real tem a mão do herói fora da `hand_table` — uma tabela por árvore, do
    range de UM jogador. O lugar de descobrir isso é a seleção, não a correção."""
    ruim = _no(hash_='ruim', tabela_mao=[{'hand': '2c2d', 'weight': 9,
                                          'freqs': [1.0, 0.0], 'evs': [1, 0]}])
    orig = _com_nos([ruim])
    try:
        assert TP.proximo_spot(rng=random.Random(1)) is None, 'serviu no nao-gradeavel'
    finally:
        TP.get_conn = orig
    # e com um bom junto, serve o bom
    orig = _com_nos([ruim, _no(hash_='bom')])
    try:
        s = TP.proximo_spot(rng=random.Random(1))
        assert s is not None and s['spot_hash'] == 'bom', s
    finally:
        TP.get_conn = orig
    print('OK  test_no_sem_a_mao_na_tabela_nao_e_servido')


def test_a_acao_certa_e_sorteada_antes_do_no():
    """No acervo real 'check' é a resposta de 56% dos nós. Sorteando nó ao acaso, responder
    sempre 'check' acertaria 56% sem olhar o board. A seleção achata isso."""
    nos = ([_no(hash_=f'c{i}', acao='check') for i in range(90)]
           + [_no(hash_=f'f{i}', acao='fold', facing=1.65,
                  acoes=['fold', 'call', 'raise_50pct'],
                  tabela_mao=[{'hand': 'JsTd', 'weight': 9,
                               'freqs': [0.7, 0.2, 0.1], 'evs': [2, 1, 0]}]) for i in range(10)])
    orig = _com_nos(nos)
    try:
        rng = random.Random(3)
        familias = {}
        for _ in range(200):
            s = TP.proximo_spot(rng=rng)
            fam = 'check' if s['facing_size_bb'] == 0 else 'fold'
            familias[fam] = familias.get(fam, 0) + 1
        # o acervo é 90% check; servido tem que ficar MUITO abaixo disso
        share = familias.get('check', 0) / sum(familias.values())
        assert share < 0.65, f'check saiu em {share:.0%} dos servidos (acervo tem 90%)'
        assert familias.get('fold', 0) > 0, 'a familia minoritaria nunca apareceu'
    finally:
        TP.get_conn = orig
    print(f'OK  test_a_acao_certa_e_sorteada_antes_do_no ({familias})')


def test_no_degenerado_e_no_com_exploitability_fora_da_faixa_ficam_de_fora():
    """Nó degenerado ENSINA ERRADO, que é pior do que repetir. `exploit <= 0,05%` é a assinatura
    do bug do pot (all-in a 100% com exploitability fake), não um solve excelente."""
    sql = TP._sql_base()
    assert 'exploitability_pct > 0.05' in sql, 'sumiu o piso de exploitability'
    assert 'exploitability_pct <= 3.0' in sql, 'sumiu o teto de exploitability'
    assert "gto_freq >= 0.99" in sql and "LIKE '%all%'" in sql, 'sumiu o filtro anti-degenerado'
    print('OK  test_no_degenerado_e_no_com_exploitability_fora_da_faixa_ficam_de_fora')


def test_spot_ja_servido_nao_volta_na_mesma_sessao():
    nos = [_no(hash_=f'n{i}') for i in range(5)]
    orig = _com_nos(nos)
    try:
        rng = random.Random(2)
        vistos = set()
        for _ in range(5):
            s = TP.proximo_spot(rng=rng, evitar=vistos)
            assert s is not None and s['spot_hash'] not in vistos, 'repetiu na sessao'
            vistos.add(s['spot_hash'])
        assert TP.proximo_spot(rng=rng, evitar=vistos) is None, 'serviu depois de esgotar'
    finally:
        TP.get_conn = orig
    print('OK  test_spot_ja_servido_nao_volta_na_mesma_sessao')


def test_selecao_honra_o_leak_pedido():
    """O filtro de street/posição tem que CHEGAR na consulta.

    A primeira versão aceitava os parâmetros e servia o acervo inteiro do mesmo jeito: o treino
    dizia mirar o leak do jogador e sorteava de qualquer recorte. Vazamento silencioso, do tipo que
    só aparece quando alguém compara o que foi servido com o que foi pedido.
    """
    capturado = {}
    nos = [_no(hash_='x1', street='turn', pos='CO')]

    class _Espia(_ConnFalsa):
        def execute(self, sql, params=None):
            if 'gto_nodes' in sql:
                capturado['sql'] = sql
                capturado['params'] = params
            return super().execute(sql, params)

    original = TP.get_conn
    TP.get_conn = lambda: _Espia(nos)
    try:
        TP.proximo_spot(rng=random.Random(1), street='turn', position='CO')
        assert 'LOWER(g.street) = ' in capturado['sql'], 'street não foi para a consulta'
        assert 'g.position = ' in capturado['sql'], 'posição não foi para a consulta'
        assert capturado['params'] == ('turn', 'CO'), capturado['params']
    finally:
        TP.get_conn = original
    print('OK  test_selecao_honra_o_leak_pedido')


def test_menu_de_uma_opcao_so_nao_vira_exercicio():
    orig = _com_nos([_no(acoes=['check'],
                         tabela_mao=[{'hand': 'JsTd', 'weight': 9, 'freqs': [1.0], 'evs': [1]}])])
    try:
        assert TP.proximo_spot(rng=random.Random(1)) is None
    finally:
        TP.get_conn = orig
    print('OK  test_menu_de_uma_opcao_so_nao_vira_exercicio')


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
