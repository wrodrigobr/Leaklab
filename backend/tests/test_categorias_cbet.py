# -*- coding: utf-8 -*-
"""Categorias de leak de C-BET: a iniciativa divide (street x posicao), e o treino mira o pool certo.

── O que estava invisivel ─────────────────────────────────────────────────────────────────────

Ate 12/08 a categoria postflop era (street x posicao): quem c-betava errado e quem defendia
errado contra c-bet caiam no MESMO balde, dominado pela defesa (76% do volume). Medido no acervo
de producao: **150 dos 524 erros postflop (29%) eram de spots COM iniciativa** e nao viravam
categoria propria — o jogador treinava defesa para consertar um leak de c-bet.

── As tres regras desta entrega ───────────────────────────────────────────────────────────────

1. A chave da DEFESA fica a ANTIGA (`pf:street:pos`). `progression_attempts` e chaveado por ela;
   mudar a chave orfanaria o historico de treino, e o historico agregado descrevia
   majoritariamente defesa. A INICIATIVA e categoria nova (`:ini`) e comeca do zero — o que
   tambem e verdade: o pool de c-bet nao existia.
2. O treino MIRA a forma do leak: categoria de iniciativa serve spots SEM aposta na frente
   (c-bet/barrel — o hero age); defesa serve ENFRENTANDO. Aproximacao declarada: o pool guarda
   `facing_size_bb`, nao quem agrediu por ultimo.
3. Linha com `hero_was_aggressor` NULL (anterior ao backfill) conta como defesa — o lado
   conservador, e o que ela sempre foi aos olhos do treino.
"""
import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import database.schema as sch


def _banco_com_leaks():
    sch.SQLITE_PATH = tempfile.mktemp(suffix='.db')
    sch.init_db()
    c = sch.get_conn()
    c.execute("INSERT OR IGNORE INTO users (id,username,email,password_hash) "
              "VALUES (1,'h','h@t.st','x')")
    c.execute("INSERT OR IGNORE INTO tournaments (id,user_id,tournament_id,tournament_name,hero,"
              "imported_at) VALUES (1,1,'T1','T1','Hero',datetime('now'))")

    def ins(i, ini, gto='gto_critical'):
        c.execute(
            "INSERT INTO decisions (tournament_id,hand_id,street,hero_cards,board,action_taken,"
            "best_action,label,score,position,gto_label,hero_was_aggressor,stack_bb,num_players) "
            "VALUES (1,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (f'H{i}', 'flop', 'AsKs', '["2h","7c","2d"]', 'check', 'bet', 'small_mistake', 0.2,
             'SB', gto, ini, 30.0, 6))

    # 12 decisoes COM iniciativa (10 erros) e 12 SEM (12 erros) — ambos acima do min_n=10.
    for i in range(12):
        ins(i, 1, 'gto_critical' if i < 10 else 'gto_correct')
    for i in range(12, 24):
        ins(i, 0, 'gto_critical')
    # E 3 com NULL (pre-backfill): contam como defesa, nao como terceira categoria.
    for i in range(24, 27):
        ins(i, None, 'gto_correct')
    c.commit(); c.close()


def test_a_iniciativa_divide_a_categoria():
    _banco_com_leaks()
    from database.repositories import get_postflop_leak_categories
    cats = get_postflop_leak_categories(1, days=3650, min_n=10)
    por_ini = {bool(x['iniciativa']): x for x in cats}
    assert set(por_ini) == {True, False}, cats
    assert por_ini[True]['erros'] == 10, por_ini[True]
    # defesa = 12 com 0 + 3 com NULL — o NULL nao vira terceira categoria
    assert por_ini[False]['n'] == 15, por_ini[False]
    assert por_ini[False]['erros'] == 12, por_ini[False]
    print('OK  test_a_iniciativa_divide_a_categoria')


def test_chave_da_defesa_e_a_ANTIGA_e_iniciativa_ganha_sufixo():
    """Quebrar isto orfana o historico de `progression_attempts` de todo jogador."""
    _banco_com_leaks()
    from leaklab.leak_trainer import postflop_leak_cats
    cats = postflop_leak_cats(1, days=3650)
    chaves = {bool(x['iniciativa']): x['key'] for x in cats}
    assert chaves[False] == 'pf:flop:SB', chaves
    assert chaves[True] == 'pf:flop:SB:ini', chaves
    print('OK  test_chave_da_defesa_e_a_ANTIGA_e_iniciativa_ganha_sufixo')


def _pool_com(nos, **kw):
    """`_com_nos` do teste vizinho troca o get_conn e DEVOLVE o original — nao e context
    manager. Restaurar no finally, senao um teste contamina o seguinte."""
    sys.path.insert(0, os.path.dirname(__file__))
    import random
    from test_trainer_pool import _com_nos, TP
    original = _com_nos(nos)
    try:
        return TP.proximo_spot(rng=random.Random(7), **kw)
    finally:
        TP.get_conn = original


def test_o_pool_respeita_o_filtro_de_iniciativa():
    from test_trainer_pool import _no
    # A tabela da mao precisa de UMA frequencia POR acao do menu — a default do `_no` tem duas,
    # e o guarda de coerencia do pool rejeita o no de 3 acoes em silencio (proximo_spot -> None).
    nos = [_no(hash_='h_agindo', facing=0.0, acao='check', acoes=['check', 'bet_50pct']),
           _no(hash_='h_enfrenta', facing=6.0, acao='call', acoes=['fold', 'call', 'raise_50pct'],
               tabela_mao=[{'hand': 'JsTd', 'weight': 10.0,
                            'freqs': [0.1, 0.7, 0.2], 'evs': [0.0, 1.5, 1.2]}])]
    agindo = _pool_com(nos, enfrentando=False)
    assert agindo and agindo['spot_hash'] == 'h_agindo', agindo and agindo.get('spot_hash')
    enfrenta = _pool_com(nos, enfrentando=True)
    assert enfrenta and enfrenta['spot_hash'] == 'h_enfrenta', enfrenta and enfrenta.get('spot_hash')
    # CONTROLE: sem filtro, os dois sao serviveis — o filtro nao pode virar recusa geral.
    livre = _pool_com(nos)
    assert livre is not None
    print('OK  test_o_pool_respeita_o_filtro_de_iniciativa')


def test_o_treino_traduz_iniciativa_para_a_forma_do_pool():
    """A categoria diz `iniciativa`; o pool fala `enfrentando`. A traducao mora no leak_trainer e
    e o INVERSO um do outro — este teste le a chamada viva com um dublê que a captura."""
    import leaklab.leak_trainer as lt
    capturas = []

    def _pool_espiao(rng=None, evitar=None, street=None, position=None, enfrentando=None):
        capturas.append({'street': street, 'position': position, 'enfrentando': enfrentando})
        return None   # forca o fallback, que nao interessa aqui

    import leaklab.trainer_pool as tp
    original = tp.proximo_spot
    tp.proximo_spot = _pool_espiao
    try:
        for cat, esperado in [({'street': 'flop', 'position': 'SB', 'iniciativa': True}, False),
                              ({'street': 'flop', 'position': 'SB', 'iniciativa': False}, True),
                              ({'street': 'flop', 'position': 'SB'}, None)]:
            capturas.clear()
            try:
                lt.generate_postflop_spot(category=cat)
            except Exception:
                pass   # o fallback pode falhar sem acervo; o que se testa e a PRIMEIRA chamada
            assert capturas, 'o treino nao consultou o pool'
            assert capturas[0]['enfrentando'] is esperado, (cat, capturas[0])
    finally:
        tp.proximo_spot = original
    print('OK  test_o_treino_traduz_iniciativa_para_a_forma_do_pool')


if __name__ == '__main__':
    import sys as _s
    _testes = [v for k, v in sorted(globals().items()) if k.startswith('test_') and callable(v)]
    _falhas = 0
    for _t in _testes:
        try:
            _t()
        except Exception as _e:
            _falhas += 1
            print('FAIL    %s: %s: %s' % (_t.__name__, type(_e).__name__, _e))
    print()
    print('Total: %d | Passed: %d | Failed: %d' % (len(_testes), len(_testes) - _falhas, _falhas))
    _s.exit(1 if _falhas else 0)
