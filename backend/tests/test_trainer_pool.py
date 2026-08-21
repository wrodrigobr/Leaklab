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


def test_no_de_flop_solvado_com_CINCO_cartas_nao_e_servido():
    """**Este teste mudou de significado em 2026-08-03, e o antigo era o problema.**

    Ele afirmava `len(s['board']) == 3` para um nó de flop cujo SOLVE tinha visto as cinco cartas
    — ou seja, travava a aparência correta por cima de um veredito de river. Medido em produção:
    1.977 dos 5.030 nós servíveis nasceram assim (todos antes do conserto do enfileiramento em
    28/07). A mesa desenhava 3 cartas, o jogador decidia um flop, e era corrigido por uma
    estratégia que já conhecia o river.

    Cortar a exibição não conserta o solve: só esconde o descompasso. O nó não é servível.
    Detalhes e a varredura completa em `test_board_da_street_no_pool.py`.
    """
    n = _no(street='flop', board=['Ks', '6c', '7d', '2h', '9s'])
    orig = _com_nos([n])
    try:
        assert TP.proximo_spot(rng=random.Random(1)) is None, \
            'no de flop solvado com o board do river virou exercicio'
    finally:
        TP.get_conn = orig
    print('OK  test_no_de_flop_solvado_com_CINCO_cartas_nao_e_servido')


def test_board_da_street_certa_continua_sendo_servido():
    """O contraponto: sem ele, rejeitar TUDO faria o teste acima passar com o acervo em zero."""
    orig = _com_nos([_no(street='flop', board=['Ks', '6c', '7d'])])
    try:
        s = TP.proximo_spot(rng=random.Random(1))
        assert s is not None, 'flop com 3 cartas foi rejeitado'
        assert s['board'] == ['Ks', '6c', '7d'], s['board']
    finally:
        TP.get_conn = orig
    print('OK  test_board_da_street_certa_continua_sendo_servido')


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


def test_no_sem_adversario_nao_e_servido():
    """Sem saber QUEM é o vilão não dá para desenhar a mesa nem escrever o enunciado.

    Reportado com print: "não tem mais ninguém na mão", rótulo saindo como
    "SB defende vs c-bet de (flop)" e TODOS os assentos foldados. A causa: o nó não trazia
    `vs_position`, e `indexOf('')` é -1 — o vilão nunca entrava na mão e nenhuma ficha de aposta
    era desenhada. Medido: 20% do acervo não guarda essa informação.
    """
    n = _no()
    sj = json.loads(n['spot_json']); sj['_meta'] = {}
    n['spot_json'] = json.dumps(sj)
    orig = _com_nos([n])
    try:
        assert TP.proximo_spot(rng=random.Random(1)) is None, 'serviu no sem vs_position'
    finally:
        TP.get_conn = orig
    print('OK  test_no_sem_adversario_nao_e_servido')


def test_posicao_fora_do_vocabulario_da_mesa_nao_e_servida():
    """A mesa desenha 9 assentos NOMEADOS. `MP1` (de captura antiga) vira `indexOf() == -1` e o
    assento do herói some da tela."""
    for campo, valor in (('position', 'MP1'), ('vs', 'MP1')):
        n = _no(pos=('MP1' if campo == 'position' else 'BB'))
        if campo == 'vs':
            sj = json.loads(n['spot_json']); sj['_meta'] = {'vs_position': 'MP1'}
            n['spot_json'] = json.dumps(sj)
        orig = _com_nos([n])
        try:
            assert TP.proximo_spot(rng=random.Random(1)) is None, f'serviu {campo}=MP1'
        finally:
            TP.get_conn = orig
    print('OK  test_posicao_fora_do_vocabulario_da_mesa_nao_e_servida')


def test_pote_em_fichas_nao_e_servido():
    """Parte do acervo guarda o pote em FICHAS (medido: `pot_bb` de 3500 com stack de 40) — resíduo
    do bug de fichas→BB do postflop. Um pote maior que os dois stacks somados não existe em
    heads-up, e serve de peneira sem precisar adivinhar a origem do número."""
    n = _no()
    sj = json.loads(n['spot_json']); sj['pot_bb'] = 3500.0   # stack do fixture e 40
    n['spot_json'] = json.dumps(sj)
    orig = _com_nos([n])
    try:
        assert TP.proximo_spot(rng=random.Random(1)) is None, 'serviu pote em fichas'
    finally:
        TP.get_conn = orig
    # e o pote zero tambem nao passa: postflop sem pote nao existe
    n2 = _no()
    sj2 = json.loads(n2['spot_json']); sj2['pot_bb'] = 0
    n2['spot_json'] = json.dumps(sj2)
    orig = _com_nos([n2])
    try:
        assert TP.proximo_spot(rng=random.Random(1)) is None, 'serviu pote zero'
    finally:
        TP.get_conn = orig
    print('OK  test_pote_em_fichas_nao_e_servido')


def test_a_mao_servida_ESTA_sempre_na_tabela():
    """A mão entregue ao jogador tem que ter linha na `hand_table` — é dela que sai o gabarito.

    ── O que mudou, e por que este teste foi reescrito (triado em 21/08) ───────────────────

    A versão anterior exigia `proximo_spot() is None` quando a mão do HERÓI estava fora da
    tabela ("34% do acervo real"). Isso era o contrato até a **Fase 2 (17/08)**, quando o
    pool passou a sortear uma mão DA PRÓPRIA TABELA e servir o spot com ela — destravando
    justamente esses 34%, já que a tabela tem mediana de 462 mãos por board.

    O teste ficou vermelho por cobrar o comportamento antigo depois da mudança, e o vermelho
    passou despercebido porque o CI está bloqueado. **O invariante de verdade nunca foi "não
    sirva o nó", era "não sirva mão sem gabarito"** — e é esse que fica travado aqui.
    """
    ruim = _no(hash_='ruim', tabela_mao=[{'hand': '2c2d', 'weight': 9,
                                          'freqs': [1.0, 0.0], 'evs': [1, 0]}])
    orig = _com_nos([ruim])
    try:
        s = TP.proximo_spot(rng=random.Random(1))
        assert s is not None, 'a Fase 2 devia destravar este nó servindo a mão da tabela'
        assert s['hand'] == '2c2d', (
            f"serviu {s['hand']!r}, que não tem linha na hand_table — sem gabarito da mão, "
            'a correção compara com a ação de topo e ensina o errado')
    finally:
        TP.get_conn = orig

    # CONTROLE: tabela VAZIA não tem mão nenhuma para sortear, e aí não há o que servir.
    # Sem este caso, o teste acima passaria mesmo que o pool ignorasse a tabela por completo.
    sem_tabela = _no(hash_='sem_tabela', tabela_mao=[])
    orig = _com_nos([sem_tabela])
    try:
        assert TP.proximo_spot(rng=random.Random(1)) is None, \
            'serviu spot de árvore SEM hand_table — não há gabarito por mão nenhum'
    finally:
        TP.get_conn = orig
    print('OK  test_a_mao_servida_ESTA_sempre_na_tabela')


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
    assert 'gto_freq >= 0.99' in sql, 'sumiu o filtro anti-degenerado'
    assert all(f"'{a}'" in sql for a in TP._ALLIN), 'a lista de all-in nao esta na consulta'
    print('OK  test_no_degenerado_e_no_com_exploitability_fora_da_faixa_ficam_de_fora')


def test_a_consulta_nao_tem_porcentagem_solta():
    """`%` na SQL quebra no Postgres QUANDO ha parametros, e so entao.

    Foi assim que a selecao por leak nasceu quebrada em producao: a consulta usava
    `LIKE '%all%'`, e no Postgres o `%` e placeholder. Sem parametro a consulta passava; com
    parametro — ou seja, exatamente no caminho do treino mirado, que filtra street e posicao — ela
    explodia. O `except` do chamador engolia e caia no catalogo estatico, entao a feature ficava
    desligada em silencio com a tela funcionando normalmente.

    Os testes deste arquivo usam conexao falsa e nunca veriam um problema de dialeto. Este guarda
    e sobre o TEXTO da consulta, que e o que atravessa o driver.
    """
    sql = TP._sql_base() + " AND LOWER(g.street) = ? AND g.position = ?"
    assert '%' not in sql, f'a consulta tem % solto e vai quebrar no Postgres com parametros: {sql}'
    print('OK  test_a_consulta_nao_tem_porcentagem_solta')


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
    raise SystemExit(1 if fail else 0)
