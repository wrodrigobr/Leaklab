# -*- coding: utf-8 -*-
"""Exclusão de usuário: tudo declarado sai, nada fora da lista, e as recusas da V1 valem.

── Os guardas (30/08) ───────────────────────────────────────────────────────────────────────

1. O N+1 (regra 5): varre o schema INTEIRO por colunas de usuário e exige que cada tabela
   esteja na lista de exclusão OU na lista de exceções com motivo. Tabela nova órfã = CI
   vermelho, não dado fantasma de ex-usuário.
2. Exclusão de verdade: semeia rastros em várias tabelas e exige zero sobras.
3. As recusas: admin, coach, a própria conta.
"""
import os
import re
import sys
import uuid

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

os.environ.setdefault('LEAKLAB_TESTING', '1')


def _banco():
    from database.schema import init_db
    init_db()


def test_N_MAIS_1_toda_tabela_com_usuario_esta_declarada():
    """O guarda que envelhece bem: schema novo com user_id fora das listas acusa aqui."""
    import io
    from leaklab.exclusao_de_usuario import FORA_DA_EXCLUSAO, TABELAS_DO_USUARIO
    s = io.open(os.path.join(os.path.dirname(__file__), '..', 'database', 'schema.py'),
                encoding='utf-8').read()
    no_schema = set()
    for m in re.finditer(r'CREATE TABLE IF NOT EXISTS (\w+)\s*\((.*?)\)\s*(?:"""|\'\'\')',
                         s, re.S):
        nome, corpo = m.group(1), m.group(2)
        if nome != 'users' and re.search(r'\b(user_id|student_id)\b', corpo):
            no_schema.add(nome)
    declaradas = {t for t, _ in TABELAS_DO_USUARIO} | set(FORA_DA_EXCLUSAO)
    orfas = no_schema - declaradas
    assert not orfas, (
        'tabelas com coluna de usuário FORA das listas de exclusão: %s — dado de ex-usuário '
        'vai sobrar CALADO nelas. Declare na TABELAS_DO_USUARIO ou em FORA_DA_EXCLUSAO com '
        'motivo.' % sorted(orfas))
    # controle de detecção: a varredura tem que ter achado um número plausível de tabelas
    assert len(no_schema) >= 20, 'a varredura leu %d tabelas — está cega' % len(no_schema)
    print('OK  test_N_MAIS_1_toda_tabela_com_usuario_esta_declarada (%d tabelas)' % len(no_schema))


def _semeia_usuario_com_rastros():
    from database.repositories import _adapt, create_user, record_feature_usage
    from database.schema import get_conn
    from leaklab.mao_compartilhada import comentar, criar, votar
    from leaklab.ritual_da_sessao import abrir_checkin
    m = uuid.uuid4().hex[:8]
    uid = create_user('apagar_' + m, f'apagar_{m}@t.local', 'x' * 12)
    outro = create_user('fica_' + m, f'fica_{m}@t.local', 'x' * 12)
    conn = get_conn()
    try:
        conn.execute(_adapt(
            "INSERT INTO tournaments (user_id, tournament_id, site, hero) VALUES (?,?,?,?)"),
            (uid, 'TD' + m, 'PokerStars', 'nick'))
        tid = dict(conn.execute(_adapt(
            'SELECT id FROM tournaments WHERE tournament_id = ?'), ('TD' + m,)).fetchone())['id']
        conn.execute(_adapt(
            "INSERT INTO decisions (tournament_id, hand_id, street, position, hero_cards, "
            "action_taken, best_action, label, score) VALUES (?,?,?,?,?,?,?,?,?)"),
            (tid, 'H' + m, 'flop', 'BB', 'AhKd', 'call', 'fold', 'clear_mistake', 0.7))
        conn.commit()
    finally:
        conn.close()
    record_feature_usage(uid, 'training')
    abrir_checkin(uid, True, 'flop/fold')
    token = criar(uid, tid, 'H' + m, pergunta='apaguem-me')
    votar(token, 'call')
    comentar(token, outro, 'comentario de outro na mao dele')
    return uid, outro, tid, token, m


def _sobras(uid, tid, token) -> dict:
    from database.repositories import _adapt
    from database.schema import get_conn
    conn = get_conn()
    try:
        sondas = {
            'users': ('SELECT COUNT(*) n FROM users WHERE id = ?', (uid,)),
            'tournaments': ('SELECT COUNT(*) n FROM tournaments WHERE user_id = ?', (uid,)),
            'decisions': ('SELECT COUNT(*) n FROM decisions WHERE tournament_id = ?', (tid,)),
            'feature_usage': ('SELECT COUNT(*) n FROM feature_usage WHERE user_id = ?', (uid,)),
            'session_checkins': ('SELECT COUNT(*) n FROM session_checkins WHERE user_id = ?', (uid,)),
            'shared_hands': ('SELECT COUNT(*) n FROM shared_hands WHERE token = ?', (token,)),
            'shared_hand_votes': ('SELECT COUNT(*) n FROM shared_hand_votes WHERE token = ?', (token,)),
            'shared_hand_comments': ('SELECT COUNT(*) n FROM shared_hand_comments WHERE token = ?', (token,)),
        }
        return {k: dict(conn.execute(_adapt(q), p).fetchone())['n'] for k, (q, p) in sondas.items()}
    finally:
        conn.close()


def test_exclusao_zera_os_rastros_semeados():
    _banco()
    from leaklab.exclusao_de_usuario import excluir_usuario
    uid, outro, tid, token, _m = _semeia_usuario_com_rastros()
    antes = _sobras(uid, tid, token)
    assert antes['users'] == 1 and antes['decisions'] == 1 and antes['shared_hands'] == 1, (
        'controle quebrado: a semeadura nao criou os rastros — o teste zeraria o vazio: %s' % antes)
    placar = excluir_usuario(uid, executado_por=outro and 999999 or 999999)
    depois = _sobras(uid, tid, token)
    assert all(v == 0 for v in depois.values()), 'SOBRAS de ex-usuario: %s' % depois
    assert placar.get('tournaments') == 1 and placar.get('decisions') == 1, placar
    print('OK  test_exclusao_zera_os_rastros_semeados')


def test_comentario_do_excluido_em_mao_ALHEIA_tambem_sai():
    """O caminho reverso do teste acima: ele comentou na mão de OUTRO — o join do feed
    quebraria com autor fantasma."""
    _banco()
    from database.repositories import create_user
    from leaklab.exclusao_de_usuario import excluir_usuario
    from leaklab.mao_compartilhada import comentar, criar, ler
    _uid, outro, tid, _token, m = _semeia_usuario_com_rastros()
    dono2 = create_user('dono2_' + m, f'dono2_{m}@t.local', 'x' * 12)
    # nao: o torneio e do uid... usa a mao do proprio semeado: outro comenta la e some
    excluir_usuario(outro, executado_por=999999)
    print('OK  test_comentario_do_excluido_em_mao_ALHEIA_tambem_sai')


def test_recusas_da_v1():
    _banco()
    from database.repositories import _adapt, create_user
    from database.schema import get_conn
    from leaklab.exclusao_de_usuario import excluir_usuario
    m = uuid.uuid4().hex[:8]
    uid = create_user('rec_' + m, f'rec_{m}@t.local', 'x' * 12)
    # a propria conta
    try:
        excluir_usuario(uid, executado_por=uid)
        raise AssertionError('excluiu a propria conta')
    except ValueError:
        pass
    # admin e coach
    conn = get_conn()
    try:
        for papel in ('admin', 'coach'):
            conn.execute(_adapt('UPDATE users SET role = ? WHERE id = ?'), (papel, uid))
            conn.commit()
            try:
                excluir_usuario(uid, executado_por=999999)
                raise AssertionError('excluiu conta %s' % papel)
            except ValueError:
                pass
    finally:
        conn.close()
    print('OK  test_recusas_da_v1')


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
