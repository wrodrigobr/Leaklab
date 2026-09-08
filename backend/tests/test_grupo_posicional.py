# -*- coding: utf-8 -*-
"""Um assento, um grupo — por qualquer rotulo que o parser use para ele (AY-13, 06/09).

A auditoria (P3) achou dois mapas de posicao a mais, cada um com o proprio conjunto de rotulos
crus. O `pos_bucket` da matriz de alinhamento punha `MP1` em "MP" e `LJ` em "EP" — o MESMO
assento em baldes diferentes (`MP1` e como o 9-max grava o LJ). O DNA tinha um conjunto EP com
`MP3`, que ninguem emite, e sem `LJ`. Um dia antes, esse mesmo defeito na grade por posicao
escondia 114 maos do pagante.

Agora ha um lugar so, `grupo_posicional`, que normaliza pelo mapa do motor e agrupa pela ordem
canonica. Os testes exigem a INVARIANTE (alias e canonico caem no mesmo grupo), nao o caso.
"""
import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
_TMPDB = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
_TMPDB.close()
os.environ['LEAKLAB_DB'] = _TMPDB.name
os.environ.pop('DATABASE_URL', None)

from database.schema import get_conn, init_db                              # noqa: E402
import database.repositories as repo                                       # noqa: E402
from database.repositories import (GRUPOS_CEDO, GRUPOS_TARDE, POSICOES_NA_ORDEM,   # noqa: E402
                                   _adapt, grupo_posicional, rotulos_do_assento)
from leaklab.gto_utils import _POSITION_NORM                               # noqa: E402


def test_alias_e_canonico_caem_no_MESMO_grupo():
    """A invariante. Para todo alias do mapa do motor, o grupo e o do canonico."""
    divergem = [(cru, canon, grupo_posicional(cru), grupo_posicional(canon))
                for cru, canon in _POSITION_NORM.items()
                if grupo_posicional(cru) != grupo_posicional(canon)]
    assert not divergem, 'mesmo assento em grupos diferentes: %s' % divergem


def test_o_caso_que_originou_MP1_e_LJ():
    assert grupo_posicional('MP1') == grupo_posicional('LJ') == 'MP'
    assert grupo_posicional('MP2') == grupo_posicional('HJ') == 'MP'


def test_toda_posicao_canonica_tem_grupo():
    """Nenhum assento da ordem canonica pode cair em OTHER — seria mao sumindo calada."""
    sem = [p for p in POSICOES_NA_ORDEM if grupo_posicional(p) == 'OTHER']
    assert not sem, 'posicao canonica sem grupo: %s' % sem
    for p in POSICOES_NA_ORDEM:
        for cru in rotulos_do_assento(p):
            assert grupo_posicional(cru) == grupo_posicional(p), (cru, p)


def test_cedo_e_tarde_cobrem_tudo_antes_dos_blinds_sem_sobrepor():
    assert not set(GRUPOS_CEDO) & set(GRUPOS_TARDE)
    antes_dos_blinds = [p for p in POSICOES_NA_ORDEM if p not in ('SB', 'BB')]
    for p in antes_dos_blinds:
        assert grupo_posicional(p) in GRUPOS_CEDO + GRUPOS_TARDE, p


def _semeia(rotulo):
    init_db()
    conn = get_conn()
    for t in ('decisions', 'tournaments', 'users'):
        conn.execute('DELETE FROM %s' % t)
    conn.commit(); conn.close()
    uid = repo.create_user('gp', 'gp@t.local', 'senha12345', 'player')
    conn = get_conn()
    conn.execute(_adapt("INSERT INTO tournaments (id,user_id,tournament_id,site,hero,played_at,imported_at) "
                        "VALUES (1,?,'T1','pokerstars','Hero','2026-09-01','2026-09-01')"), (uid,))
    for i in range(100):
        # A 1a versao punha 100% raise no assento e 0% no BTN: o indice de consciencia
        # posicional SATURA em 0 dos dois lados e cru x canonico davam o mesmo numero — a
        # mutacao "conjunto cru sem LJ" passou em silencio. Proporcoes moderadas caem DENTRO
        # da escala: assento 20% raise, BTN 30% raise -> ~70; com LJ fora do conjunto cru o
        # fallback usa a agressao global (~25%) -> ~60. Distinguivel.
        if i % 2:
            pos, acao = rotulo, ('raise' if i % 20 in (1, 3) else 'call')        # 2 de 10 impares: 20%
        else:
            pos, acao = 'BTN', ('raise' if i % 20 in (0, 2, 4) else 'call')      # 3 de 10 pares: 30%
        conn.execute(_adapt("INSERT INTO decisions (tournament_id,hand_id,street,position,action_taken,"
                            "best_action,score,label,is_3bet) VALUES (1,?,'preflop',?,?,'raise',0.1,'standard',FALSE)"),
                     ('H%d' % i, pos, acao))
    conn.commit(); conn.close()
    return uid


def test_o_DNA_le_MP1_e_LJ_do_mesmo_jeito():
    """Prova pelo CONSUMIDOR, nao so pelo helper: a mesma sequencia de acoes gravada como MP1
    e como LJ tem de produzir a mesma consciencia posicional."""
    a = repo.get_player_dna(_semeia('MP1'), days=3650, last_n=0)
    b = repo.get_player_dna(_semeia('LJ'), days=3650, last_n=0)
    assert a.get('dna') and b.get('dna'), (a, b)
    assert a['dna'] == b['dna'], 'DNA diverge entre MP1 e LJ: %s x %s' % (a['dna'], b['dna'])
    # Ancora no VALOR: 50 + (30 - 20) * 2. Se o assento cair fora do grupo cedo, o fallback
    # e a agressao global (25%) e o indice vira 60 — a igualdade acima ainda pode passar por
    # saturacao, o valor nao.
    assert a['dna']['positional_awareness'] == 70.0, a['dna']['positional_awareness']


def test_a_matriz_de_alinhamento_poe_MP1_e_LJ_na_MESMA_celula():
    """O caso que originou: o mapa cru da matriz punha MP1 em MP e LJ em EP. Agora as maos
    gravadas como MP1 e como LJ tem de cair na mesma celula (MP), e nenhuma em EP."""
    uid = _semeia('MP1')
    conn = get_conn()
    # metade das maos do assento reescrita como LJ: mesmo assento, outro rotulo
    conn.execute(_adapt("UPDATE decisions SET position='LJ', gto_label='gto_correct' "
                        "WHERE position='MP1' AND CAST(SUBSTR(hand_id, 2) AS INTEGER) % 4 = 1"))
    conn.execute(_adapt("UPDATE decisions SET gto_label='gto_correct' WHERE position='MP1'"))
    conn.commit(); conn.close()
    m = repo.get_gto_alignment_matrix(uid, since_days=3650, last_n=0)
    por_pos = {}
    for c in m['cells']:
        por_pos[c['position']] = por_pos.get(c['position'], 0) + c['n']
    assert por_pos.get('MP') == 50, por_pos     # 25 MP1 + 25 LJ
    assert por_pos.get('EP', 0) == 0, por_pos
    assert por_pos.get('BTN') == 50, por_pos


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
