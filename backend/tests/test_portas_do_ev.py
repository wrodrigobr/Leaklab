# -*- coding: utf-8 -*-
"""Toda porta que soma EV passa pela regua. E o teste conta as PORTAS, nao so as consertadas.

── O historico ────────────────────────────────────────────────────────────────────────────────

`ev_loss_trustworthy` diz na propria docstring: "fonte unica desta regra: quem for somar,
ranquear ou pesar EV precisa passar por aqui". Em 09/08 o card do replayer foi corrigido por
exibir `-3588 bb` num stack de 32,2bb, e a licao registrada foi "guarda existir nao basta, conte
quantas portas levam a tela".

Um dia depois, uma auditoria sobre o snapshot de producao achou TRES portas ainda cruas:

    get_ev_summary       DashboardV2 publicava  7.669,3 bb/100   (honesto: 9,8)
    coach_replay         um torneio exibia     78.738,0 bb        (honesto:  5,9)
    get_leak_categories  a fila do Leak Trainer, ranqueada sem regua

A primeira tinha CINCO agregacoes cruas dentro dela — EV/100, top_leaks, share, serie por
torneio e sangria por street. Consertar "a funcao" nao teria bastado.

── Por que a varredura do fonte no fim ────────────────────────────────────────────────────────

Os testes de comportamento provam as portas de HOJE. A quarta porta e a que ainda nao existe:
alguem escreve `SUM(ev_loss_bb)` numa funcao nova e o numero volta a mentir sem nenhum teste
vermelho. O ultimo teste le o fonte e reprova a soma em SQL — a regra tem de ser aplicada em
Python, onde a regua alcanca.
"""
import os
import re
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import database.schema as sch

RAIZ = os.path.join(os.path.dirname(__file__), '..')

#: Uma linha impossivel de verdade: 9.999bb perdidos num stack de 10bb, pote de 3bb.
EV_IMPOSSIVEL = 9999.0
#: E uma que a regua aceita, para o teste nao passar com tudo zerado.
EV_HONESTO = 1.0


def _banco(com_impossivel=True, n_sadias=12):
    sch.SQLITE_PATH = tempfile.mktemp(suffix='.db')
    sch.init_db()
    c = sch.get_conn()
    c.execute("INSERT OR IGNORE INTO users (id,username,email,password_hash) "
              "VALUES (1,'h','h@t.st','x')")
    c.execute("INSERT OR IGNORE INTO tournaments (id,user_id,tournament_id,tournament_name,hero) "
              "VALUES (1,1,'T1','Torneio 1','Hero')")

    def ins(**kw):
        d = dict(tournament_id=1, hand_id='H', street='preflop', hero_cards='AsKs', board='[]',
                 action_taken='fold', best_action='raise', label='small_mistake', score=0.3,
                 position='BTN', vs_position='CO', stack_bb=10.0, pot_size=3.0, facing_bet=2.0,
                 estimated_equity=0.40, ev_loss_source='gw_har', num_players=9)
        d.update(kw)
        cols = ', '.join(d)
        c.execute(f"INSERT INTO decisions ({cols}) VALUES ({', '.join('?' for _ in d)})",
                  tuple(d.values()))

    for i in range(n_sadias):
        ins(hand_id=f'H{i}', ev_loss_bb=EV_HONESTO)
    if com_impossivel:
        ins(hand_id='H-IMPOSSIVEL', ev_loss_bb=EV_IMPOSSIVEL)
    c.commit()
    c.close()


def _portas(user_id=1):
    """Chama as funcoes VIVAS. Reimplementar a agregacao aqui mediria o meu codigo, nao o deles."""
    import database.repositories as repo
    from leaklab.coach_replay import build_coach_replay
    resumo = repo.get_ev_summary(user_id)
    replay = build_coach_replay(user_id, 1) or {}
    return {
        'ev_per_100':   resumo.get('ev_per_100'),
        'top_leak_bb':  (resumo.get('top_leaks') or [{}])[0].get('loss_bb'),
        'street_bb':    sum(x['loss_bb'] for x in resumo.get('by_street') or []),
        'ev_leaks_bb':  repo.get_ev_leaks(user_id, days=3650).get('total_ev_loss_bb'),
        'categorias':   [c['total_ev_loss_bb'] for c in repo.get_leak_categories(user_id, days=3650)],
        'replay_bb':    (replay.get('intro') or {}).get('ev_lost_bb'),
    }


def test_nenhuma_porta_deixa_o_numero_impossivel_passar():
    _banco(com_impossivel=True)
    p = _portas()
    # 12 linhas de 1bb: qualquer soma honesta fica na casa das dezenas. Com a linha impossivel
    # dentro, qualquer numero passaria de mil.
    assert p['ev_per_100'] == 100.0, f"EV/100 contaminado: {p['ev_per_100']}"
    assert p['top_leak_bb'] == 12.0, f"top_leak contaminado: {p['top_leak_bb']}"
    assert p['street_bb'] == 12.0, f"sangria por street contaminada: {p['street_bb']}"
    assert p['ev_leaks_bb'] == 12.0, f"get_ev_leaks contaminado: {p['ev_leaks_bb']}"
    assert p['categorias'] == [12.0], f"leak_categories contaminado: {p['categorias']}"
    assert p['replay_bb'] == 12.0, f"coach_replay contaminado: {p['replay_bb']}"
    print('OK  test_nenhuma_porta_deixa_o_numero_impossivel_passar')


def test_CONTROLE_as_portas_nao_estao_simplesmente_zeradas():
    """Sem esta ancora, um filtro que descartasse TUDO passaria no teste de cima.

    Zero tranquilizador e o pior resultado possivel numa medicao — ja encerrou investigacao
    neste projeto (CLAUDE.md, item 1).
    """
    _banco(com_impossivel=False)
    p = _portas()
    for nome, v in p.items():
        if nome == 'categorias':
            assert v and v[0] > 0, 'leak_categories devolveu vazio sem a linha impossivel'
        else:
            assert v, f'{nome} zerou mesmo sem a linha impossivel: {v}'
    print('OK  test_CONTROLE_as_portas_nao_estao_simplesmente_zeradas')


def test_a_linha_impossivel_nao_deixa_de_ser_ERRO():
    """O que se descarta e o NUMERO, nao a acusacao. Rebaixar o veredito junto seria trocar um
    defeito por outro — o fold continua errado, so nao se sabe quanto custou."""
    _banco(com_impossivel=True)
    conn = sch.get_conn()
    r = conn.execute("SELECT label FROM decisions WHERE hand_id='H-IMPOSSIVEL'").fetchone()
    conn.close()
    assert r['label'] == 'small_mistake', r['label']
    print('OK  test_a_linha_impossivel_nao_deixa_de_ser_ERRO')


def test_nenhuma_soma_de_ev_em_SQL_no_backend():
    """A varredura dos N+1. A regua nao alcanca dentro do SQL, entao a soma nao pode morar la."""
    achados = []
    for pasta in ('database', 'leaklab', 'api'):
        base = os.path.join(RAIZ, pasta)
        for dirpath, _, arquivos in os.walk(base):
            for nome in arquivos:
                if not nome.endswith('.py'):
                    continue
                caminho = os.path.join(dirpath, nome)
                for i, linha in enumerate(open(caminho, encoding='utf-8').read().splitlines(), 1):
                    nu = linha.split('--')[0].split('#')[0]
                    if re.search(r'\b(SUM|AVG)\s*\(\s*(?:\w+\.)?ev_loss_bb\s*\)', nu, re.I):
                        achados.append(f'{pasta}/{nome}:{i}: {linha.strip()}')
    assert not achados, ('soma de ev_loss_bb em SQL — agregue em Python passando por '
                         'ev_loss_trustworthy:\n  ' + '\n  '.join(achados))
    print('OK  test_nenhuma_soma_de_ev_em_SQL_no_backend')

if __name__ == '__main__':
    import sys as _s
    _testes = [v for k, v in sorted(globals().items()) if k.startswith('test_') and callable(v)]
    _falhas = 0
    for _t in _testes:
        try:
            _t()
        except Exception as _e:
            _falhas += 1
            print(f'FAIL    {_t.__name__}: {type(_e).__name__}: {_e}')
    print()
    print('Total: %d | Passed: %d | Failed: %d' % (len(_testes), len(_testes) - _falhas, _falhas))
    _s.exit(1 if _falhas else 0)
