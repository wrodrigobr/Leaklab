# -*- coding: utf-8 -*-
"""O reprocesso APAGAVA as anotacoes do coach. Aconteceu de verdade, com 71 delas.

── O que aconteceu ────────────────────────────────────────────────────────────────────────────

`coach_hand_annotations.decision_id` tem FK `ON DELETE CASCADE`, e `save_decisions` faz
`DELETE FROM decisions WHERE tournament_id = ?` antes de reinserir. Resultado: **todo reprocesso
destruia o trabalho do coach**, sem erro, sem log, sem aviso.

Em 05/08 isso apagou 71 comentarios de um coach em producao. Voltaram porque eu tinha exportado
o JSON por acaso, para montar um relatorio — nao porque havia backup. Sorte nao e processo.

── O conserto ─────────────────────────────────────────────────────────────────────────────────

`save_decisions` guarda as anotacoes ANTES do DELETE e as religa DEPOIS do INSERT, na MESMA
transacao (se explodir no meio, o rollback devolve tudo). O religamento usa identidade ESTAVEL —
`(hand_id, street, action_taken)` mais um ORDINAL, porque essa chave nao e unica: o hero age duas
vezes na mesma street sempre que paga e depois enfrenta um raise.

Quando a decisao anotada nao existe mais no recalculo, a anotacao NAO volta. Perder e honesto;
colar o comentario do coach na decisao errada seria pior.

── Por que este teste tem que reprocessar DE VERDADE ──────────────────────────────────────────

Um teste que so chamasse `_religa_anotacoes` provaria a funcao, nao o comportamento. O defeito
vivia no CAMINHO — o DELETE dispara o CASCADE antes de qualquer coisa. Entao aqui se grava,
anota, e chama `save_decisions` outra vez, que e exatamente o que o reprocesso faz.
"""
import os, sys, tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import database.schema as sch
import database.repositories as repo


def _setup():
    sch.SQLITE_PATH = tempfile.mktemp(suffix='.db')
    sch.init_db()
    c = sch.get_conn()
    c.execute("INSERT OR IGNORE INTO users (id, username, email, password_hash) "
              "VALUES (1, 'aluno', 'a@t.st', 'x')")
    c.execute("INSERT OR IGNORE INTO users (id, username, email, password_hash) "
              "VALUES (2, 'coach', 'c@t.st', 'x')")
    c.execute("INSERT OR IGNORE INTO tournaments (id, user_id, tournament_id, hero) "
              "VALUES (700, 1, 'T-ANOT', 'Hero')")
    c.commit()
    c.close()


def _dec(hand_id, street, acao):
    return {'handId': hand_id, 'street': street, 'hero_cards': 'AsKs', 'board': '',
            'action_taken': acao,
            'evaluation': {'label': 'standard', 'score': 1.0, 'bestAction': acao},
            'spot': {'position': 'BTN', 'heroStackBb': 30.0}}


def _decisoes():
    # A mao 'H2' tem DUAS decisoes com a MESMA chave (preflop/call) de proposito: e o caso em que
    # um religamento ingenuo colaria o comentario na decisao errada.
    return [_dec('H1', 'preflop', 'raise'),
            _dec('H2', 'preflop', 'call'),
            _dec('H2', 'preflop', 'call'),
            _dec('H3', 'flop', 'bet')]


def _anota(decision_id, texto):
    c = sch.get_conn()
    c.execute("INSERT INTO coach_hand_annotations "
              "(coach_id, student_id, decision_id, comment, mode) VALUES (?,?,?,?,?)",
              (2, 1, decision_id, texto, 'complement'))
    c.commit()
    c.close()


def _anotacoes():
    c = sch.get_conn()
    linhas = [dict(r) for r in c.execute(
        "SELECT a.comment, d.hand_id, d.street, d.action_taken, d.id AS did "
        "FROM coach_hand_annotations a JOIN decisions d ON d.id = a.decision_id "
        "ORDER BY d.id").fetchall()]
    c.close()
    return linhas


def test_anotacao_sobrevive_ao_reprocesso():
    """O caso reportado, reduzido: anotar e reprocessar."""
    _setup()
    repo.save_decisions(700, _decisoes())
    c = sch.get_conn()
    ids = [dict(r)['id'] for r in c.execute(
        "SELECT id FROM decisions WHERE tournament_id=700 ORDER BY id").fetchall()]
    c.close()
    _anota(ids[0], 'comentario do coach')
    assert len(_anotacoes()) == 1

    repo.save_decisions(700, _decisoes())          # <- o reprocesso

    depois = _anotacoes()
    assert len(depois) == 1, f'a anotacao sumiu no reprocesso: {depois}'
    assert depois[0]['comment'] == 'comentario do coach'
    assert depois[0]['hand_id'] == 'H1', 'voltou na mao errada'


def test_chave_repetida_volta_na_decisao_CERTA():
    """`(mao, street, acao)` nao e unica. Duas anotacoes na mesma chave tem que voltar cada uma
    no seu lugar — senao o coach le o comentario dele na decisao do vizinho."""
    _setup()
    repo.save_decisions(700, _decisoes())
    c = sch.get_conn()
    ids = [dict(r)['id'] for r in c.execute(
        "SELECT id FROM decisions WHERE tournament_id=700 AND hand_id='H2' ORDER BY id").fetchall()]
    c.close()
    assert len(ids) == 2, ids
    _anota(ids[0], 'primeira call')
    _anota(ids[1], 'segunda call')

    repo.save_decisions(700, _decisoes())

    depois = [a for a in _anotacoes() if a['hand_id'] == 'H2']
    assert len(depois) == 2, depois
    assert [a['comment'] for a in depois] == ['primeira call', 'segunda call'], depois


def test_decisao_que_sumiu_nao_leva_anotacao_para_outra():
    """Se o recalculo nao produz mais aquela decisao, a anotacao NAO volta. Perder e honesto;
    realocar seria inventar."""
    _setup()
    repo.save_decisions(700, _decisoes())
    c = sch.get_conn()
    did = dict(c.execute("SELECT id FROM decisions WHERE tournament_id=700 AND hand_id='H3'"
                         ).fetchone())['id']
    c.close()
    _anota(did, 'comentario do flop')

    # reprocessa SEM a mao H3
    repo.save_decisions(700, [d for d in _decisoes() if d['handId'] != 'H3'])

    depois = _anotacoes()
    assert all(a['comment'] != 'comentario do flop' for a in depois), (
        f'a anotacao de uma decisao que sumiu foi colada em outra: {depois}')


def test_reprocesso_sem_anotacao_nao_quebra():
    """CONTROLE: o caminho normal, sem anotacao nenhuma, segue funcionando."""
    _setup()
    repo.save_decisions(700, _decisoes())
    repo.save_decisions(700, _decisoes())
    c = sch.get_conn()
    n = list(dict(c.execute("SELECT COUNT(*) AS n FROM decisions WHERE tournament_id=700"
                            ).fetchone()).values())[0]
    c.close()
    assert n == 4, n


if __name__ == '__main__':
    falhas = 0
    testes = [v for k, v in sorted(globals().items()) if k.startswith('test_')]
    for t in testes:
        try:
            t()
        except AssertionError as e:
            falhas += 1
            print(f'FALHOU  {t.__name__}: {e}')
        except Exception as e:
            falhas += 1
            print(f'ERRO    {t.__name__}: {type(e).__name__}: {e}')
    print(f'\nTotal: {len(testes)} | Passed: {len(testes) - falhas} | Failed: {falhas}')
    sys.exit(1 if falhas else 0)
