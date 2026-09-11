# -*- coding: utf-8 -*-
"""A ferramenta de desfazer o reparo das divergencias (10/09).

── O que originou ─────────────────────────────────────────────────────────────────────────

O reparo das divergencias reescreve 7 campos em milhares de decisoes de gente pagante (medido:
7.259 linhas candidatas, 768 acusacoes saindo da tela no modo conservador). O dump guarda o
ANTES de cada linha, mas arquivo sem ferramenta que o use e promessa, nao capacidade.

── O que este arquivo defende ─────────────────────────────────────────────────────────────

A guarda que decide se a reversao e segura: **so reverte a linha cujo estado ATUAL e exatamente
o que o reparo gravou.** Se o valor de hoje e outro, alguem escreveu ali depois (novo solve,
reconcile, reanalise do admin), e gravar o antigo por cima apagaria uma escrita mais nova — o
conserto causando dano que o bug nao causava. Tres decisoes semeadas de proposito:

  intacta       — esta como o reparo gravou            -> REVERTE
  mexida        — alguem gravou outra coisa depois     -> NAO TOCA, sai como `mudou_depois`
  ja_antiga     — ja esta no estado antigo             -> nada a fazer

E o caso que mais me preocupava: `Decimal`/texto contra float. O dump sai com `default=str`,
entao o `ev_loss_bb` do Postgres viaja como '1.4'. Sem normalizar, TODA linha cairia em
`mudou_depois` e a reversao nao reverteria nada, dizendo que estava tudo bem.

Quebrado de proposito (guarda do `para` removida), a linha mexida e revertida e o teste acusa.
"""
import io
import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
_TMPDB = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
_TMPDB.close()
os.environ['LEAKLAB_DB'] = _TMPDB.name
os.environ.pop('DATABASE_URL', None)

from database.schema import get_conn, init_db                                  # noqa: E402
from database.repositories import _adapt                                       # noqa: E402
import scripts.reverter_do_dump as rev                                         # noqa: E402

_ARQ = os.path.join(tempfile.gettempdir(), 'dump_de_teste.jsonl')

#: (id, estado ANTES do reparo, estado que o reparo GRAVOU, estado de HOJE no banco)
_CASOS = {
    'intacta': (9101,
                {'label': 'clear_mistake', 'best': 'check', 'gto_label': 'gto_critical',
                 'gto_action': 'check', 'played': 0.02, 'top': 0.9, 'ev': 1.4,
                 'ev_src': 'solver_hand'},
                {'label': 'standard', 'best': 'bet', 'gto_label': 'gto_correct',
                 'gto_action': 'bet', 'played': 0.71, 'top': 0.71, 'ev': 0.0,
                 'ev_src': 'solver_hand'}),
    'mexida': (9102,
               {'label': 'small_mistake', 'best': 'call', 'gto_label': 'gto_minor_deviation',
                'gto_action': 'call', 'played': 0.3, 'top': 0.5, 'ev': 0.4,
                'ev_src': 'solver_hand'},
               {'label': 'standard', 'best': 'fold', 'gto_label': 'gto_mixed',
                'gto_action': 'fold', 'played': 0.5, 'top': 0.5, 'ev': 0.1,
                'ev_src': 'solver_hand'}),
    'ja_antiga': (9103,
                  {'label': 'marginal', 'best': 'bet', 'gto_label': 'gto_mixed',
                   'gto_action': 'bet', 'played': 0.4, 'top': 0.6, 'ev': 0.2,
                   'ev_src': 'solver_hand'},
                  {'label': 'standard', 'best': 'check', 'gto_label': 'gto_correct',
                   'gto_action': 'check', 'played': 0.8, 'top': 0.8, 'ev': 0.0,
                   'ev_src': 'solver_hand'}),
}
#: o que alguem gravou DEPOIS do reparo na linha `mexida` (um solve novo, por exemplo)
_DEPOIS = {'label': 'clear_mistake', 'best': 'raise', 'gto_label': 'gto_critical',
           'gto_action': 'raise', 'played': 0.01, 'top': 0.95, 'ev': 2.2,
           'ev_src': 'solver_hand'}


def _grava(conn, did, est):
    conn.execute(_adapt(
        "UPDATE decisions SET label=?, best_action=?, gto_label=?, gto_action=?, "
        "gto_played_freq=?, gto_top_freq=?, ev_loss_bb=?, ev_loss_source=? WHERE id=?"),
        (est['label'], est['best'], est['gto_label'], est['gto_action'], est['played'],
         est['top'], est['ev'], est['ev_src'], did))


def _semeia():
    init_db()
    conn = get_conn()
    for t in ('decisions', 'tournaments', 'users'):
        conn.execute('DELETE FROM %s' % t)
    conn.execute(_adapt("INSERT INTO users (id, username, email, password_hash) "
                        "VALUES (9001,'u','u@e.st','h')"))
    conn.execute(_adapt("INSERT INTO tournaments (id, user_id, tournament_id, tournament_name, "
                        "hero) VALUES (9001, 9001, 'T1', 'Torneio 1', 'Hero')"))
    for nome, (did, de, para) in _CASOS.items():
        conn.execute(_adapt(
            "INSERT INTO decisions (id, tournament_id, hand_id, street, hero_cards, board, "
            "action_taken, best_action, label, score, position, num_players, spot_hash) "
            "VALUES (?, 9001, ?, 'flop', 'QsTs', '[\"3c\",\"Js\",\"Th\"]', 'bet', 'x', 'x', "
            "0.9, 'BB', 9, ?)"), (did, 'H-%s' % nome, 'spot-%s' % nome))
        # o estado de HOJE: o que o reparo gravou, menos o `ja_antiga` (que ja voltou) e o
        # `mexida` (que alguem sobrescreveu depois)
        _grava(conn, did, de if nome == 'ja_antiga' else
               (_DEPOIS if nome == 'mexida' else para))
    conn.commit(); conn.close()
    with io.open(_ARQ, 'w', encoding='utf-8', newline='\n') as fh:
        for nome, (did, de, para) in _CASOS.items():
            # `default=str` como no dump de verdade: e assim que Decimal chega como texto
            fh.write(json.dumps({'id': did, 'tid': 9001, 'user_id': 9001,
                                 'hand_id': 'H-%s' % nome, 'street': 'flop', 'acao': 'bet',
                                 'natureza': 'label_drift', 'diffs': ['label'],
                                 'de': de, 'para': para}, default=str) + '\n')


def _estado(did):
    conn = get_conn()
    r = dict(conn.execute(_adapt(
        "SELECT label, best_action, gto_label, gto_action, gto_played_freq, gto_top_freq, "
        "ev_loss_bb, ev_loss_source FROM decisions WHERE id=?"), (did,)).fetchone())
    conn.close()
    return r


def _roda(*extra):
    argv = sys.argv
    sys.argv = ['reverter_do_dump.py', _ARQ] + list(extra)
    try:
        rev.main()
    finally:
        sys.argv = argv


def test_reverte_a_linha_intacta_e_nao_toca_a_que_mudou_depois():
    _semeia()
    _roda('--apply')
    intacta = _estado(_CASOS['intacta'][0])
    assert intacta['gto_label'] == 'gto_critical', intacta      # voltou ao ANTES
    assert intacta['label'] == 'clear_mistake' and intacta['best_action'] == 'check', intacta
    assert float(intacta['ev_loss_bb']) == 1.4, intacta
    mexida = _estado(_CASOS['mexida'][0])
    assert mexida['gto_label'] == 'gto_critical' and mexida['best_action'] == 'raise', (
        'a escrita mais nova NAO pode ser apagada pela reversao', mexida)
    ja = _estado(_CASOS['ja_antiga'][0])
    assert ja['gto_label'] == 'gto_mixed', ja                   # segue no antigo, sem toque


def test_o_score_volta_junto_quando_a_linha_o_carrega():
    """As linhas do `reconcile` carregam `score`, porque ele e re-derivado do label.

    Devolver o rotulo antigo e deixar a nota nova e a linha-quimera de 12/08: veredito de uma
    avaliacao com o numero de outra. Quem muda veredito carrega a nota junto, na ida e na volta.
    """
    _semeia()
    did = _CASOS['intacta'][0]
    conn = get_conn()
    conn.execute(_adapt("UPDATE decisions SET score=? WHERE id=?"), (0.11, did))
    conn.commit(); conn.close()
    # a MESMA linha do dump, agora com score nos dois lados (como o reconcile grava)
    linhas = [json.loads(l) for l in io.open(_ARQ, encoding='utf-8') if l.strip()]
    with io.open(_ARQ, 'w', encoding='utf-8', newline=chr(10)) as fh:
        for x in linhas:
            if x['id'] == did:
                x['natureza'] = 'reconcile'
                x['de']['score'] = 0.93
                x['para']['score'] = 0.11
            fh.write(json.dumps(x) + chr(10))
    _roda('--apply')
    conn = get_conn()
    sc = dict(conn.execute(_adapt("SELECT score FROM decisions WHERE id=?"), (did,)).fetchone())
    conn.close()
    assert round(float(sc['score']), 2) == 0.93, ('o score tem de voltar junto', sc)


def test_dry_run_nao_escreve():
    _semeia()
    _roda()
    assert _estado(_CASOS['intacta'][0])['gto_label'] == 'gto_correct', 'dry-run gravou'


def test_numero_em_texto_e_o_mesmo_numero():
    """O caso que faria a reversao dizer "tudo bem" sem reverter nada: o dump sai com
    `default=str`, e o `ev_loss_bb` do Postgres viaja como '1.4'. Sem normalizar, o estado atual
    (float 1.4) nunca bateria com o esperado ('1.4') e TODA linha cairia em `mudou_depois`."""
    atual = {'label': 'standard', 'best_action': 'bet', 'gto_label': 'gto_correct',
             'gto_action': 'bet', 'gto_played_freq': 0.71, 'gto_top_freq': 0.71,
             'ev_loss_bb': 1.4, 'ev_loss_source': 'solver_hand'}
    esperado = {'label': 'standard', 'best': 'bet', 'gto_label': 'gto_correct',
                'gto_action': 'bet', 'played': '0.71', 'top': '0.71', 'ev': '1.4',
                'ev_src': 'solver_hand'}
    assert rev.estado_igual(atual, esperado), 'texto e float tem de comparar igual'
    # e '' e None sao a MESMA ausencia
    assert rev.estado_igual(dict(atual, gto_action=''), dict(esperado, gto_action=None))
    # mas diferenca de verdade continua sendo diferenca
    assert not rev.estado_igual(dict(atual, ev_loss_bb=2.0), esperado)


def test_o_recorte_por_usuario_e_por_torneio():
    _semeia()
    _roda('--user', '999', '--apply')                 # usuario que nao esta no dump
    assert _estado(_CASOS['intacta'][0])['gto_label'] == 'gto_correct', 'reverteu fora do recorte'
    _roda('--tid', '9001', '--apply')
    assert _estado(_CASOS['intacta'][0])['gto_label'] == 'gto_critical', 'nao reverteu no recorte'


if __name__ == '__main__':
    falhas = 0
    testes = [v for k, v in sorted(globals().items()) if k.startswith('test_')]
    for t in testes:
        try:
            t()
            print('OK  %s' % t.__name__)
        except AssertionError as e:
            falhas += 1
            print('FALHOU  %s: %s' % (t.__name__, e))
        except Exception as e:                                  # noqa: BLE001
            falhas += 1
            print('ERRO    %s: %s: %s' % (t.__name__, type(e).__name__, e))
    print('\nTotal: %d | Passed: %d | Failed: %d' % (len(testes), len(testes) - falhas, falhas))
    sys.exit(1 if falhas else 0)
