# -*- coding: utf-8 -*-
"""Programa de fundadores (20/08) — Pro de graça em troca de uso e feedback.

Um programa desses falha de dois jeitos, e os dois são silenciosos:

1. **O benefício nunca expira.** `get_quota_status` só derrubava plano vencido para
   `plan_source IS NULL`; um `founder` fora dessa lista ficaria Pro para sempre e
   "6 meses renovável" viraria vitalício sem ninguém decidir isso.
2. **Ninguém mede a contrapartida.** Se o painel mostrar só consumo, no fim do ciclo não há
   como separar quem honrou o trato de quem só usou — e a renovação vira chute.

Cada um desses tem teste que forja o caso e exige o número se mexer (regra 1).
"""
import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

_TMPDB = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
_TMPDB.close()
os.environ['LEAKLAB_DB'] = _TMPDB.name      # banco descartável: medir o dado de outra
os.environ.pop('DATABASE_URL', None)        # pessoa é a versão silenciosa do zero enganoso

from database.schema import get_conn, init_db                      # noqa: E402
from database.repositories import (                                # noqa: E402
    _adapt, apply_as_founder, get_founder_candidates, get_founder_program, get_quota_status,
    grant_founder, revoke_founder,
)


def _limpa():
    with get_conn() as conn:
        for t in ('support_tickets', 'progression_attempts', 'tournaments', 'users'):
            try:
                conn.execute(_adapt(f"DELETE FROM {t}"))
            except Exception:
                pass
        conn.commit()


def _user(uid: int, nome: str, plan: str = 'free', source=None):
    with get_conn() as conn:
        conn.execute(_adapt(
            "INSERT INTO users (id, email, password_hash, username, role, plan, plan_source) "
            "VALUES (?,?,?,?,'player',?,?)"),
            (uid, f'{nome}@t.com', 'x', nome, plan, source))
        conn.commit()


def _torneio(uid: int, tid: str):
    with get_conn() as conn:
        conn.execute(_adapt(
            "INSERT INTO tournaments (user_id, tournament_id, tournament_name, hero) "
            "VALUES (?,?,?,?)"), (uid, tid, 'T', 'Hero'))
        conn.commit()


def _treino(uid: int, dia: str):
    with get_conn() as conn:
        conn.execute(_adapt(
            "INSERT INTO progression_attempts (user_id, category_key, stratum, block_kind, "
            "correct, created_at) VALUES (?,?,?,?,?,?)"),
            (uid, 'rfi:BTN::40', 'core', 'mission', 1, f'{dia} 12:00:00'))
        conn.commit()


def _ticket(uid: int, assunto: str = 'achei um bug'):
    with get_conn() as conn:
        conn.execute(_adapt(
            "INSERT INTO support_tickets (user_id, subject, message) VALUES (?,?,?)"),
            (uid, assunto, 'o botao X nao responde'))
        conn.commit()


def _do(prog, uid):
    return next(f for f in prog['founders'] if f['user_id'] == uid)


def test_concessao_marca_a_coorte_e_a_validade():
    init_db(); _limpa()
    _user(1, 'ana')
    assert get_founder_program()['resumo']['total'] == 0, 'banco não estava limpo'

    res = grant_founder([1], meses=6)
    assert res['concedidos'] == [1] and not res['pulados']
    f = _do(get_founder_program(), 1)
    assert f['dias_restantes'] is not None and 170 <= f['dias_restantes'] <= 181, f
    assert f['desde'], 'founder_since não foi gravado — não dá para saber o ciclo'
    assert get_quota_status(1)['plan'] == 'pro'


def test_assinante_pagante_nao_e_sobrescrito():
    """Regra 7: o conserto não pode causar dano que a ausência dele não causava. Conceder
    cortesia por cima de uma assinatura apagaria o vínculo de quem PAGA."""
    init_db(); _limpa()
    _user(2, 'paga', plan='pro', source='stripe_sub')
    res = grant_founder([2], meses=6)
    assert res['concedidos'] == []
    assert res['pulados'] and res['pulados'][0]['motivo'] == 'assinante pagante'
    with get_conn() as conn:
        d = dict(conn.execute(_adapt(
            "SELECT plan_source FROM users WHERE id = 2")).fetchone())
    assert d['plan_source'] == 'stripe_sub', 'a assinatura foi sobrescrita'


def test_beneficio_de_fundador_EXPIRA():
    """O teste que existe por causa da falha silenciosa: sem `founder` na regra de
    expiração, 6 meses vira vitalício e ninguém percebe."""
    init_db(); _limpa()
    _user(3, 'venceu')
    grant_founder([3], meses=6)
    assert get_quota_status(3)['plan'] == 'pro', 'nem começou Pro'

    with get_conn() as conn:      # força o vencimento para ontem
        conn.execute(_adapt("UPDATE users SET plan_expires_at = '2020-01-01 00:00:00' "
                            "WHERE id = 3"))
        conn.commit()
    st = get_quota_status(3)
    assert st['plan'] == 'free', 'fundador vencido continuou Pro — benefício virou vitalício'
    assert st['expired'] is True


def test_renovacao_estende_sem_perder_o_inicio():
    """`founder_since` é o que diz "está no 2º ciclo". Se a renovação o reescrevesse, todo
    fundador pareceria novo para sempre."""
    init_db(); _limpa()
    _user(4, 'renova')
    grant_founder([4], meses=6)
    inicio = _do(get_founder_program(), 4)['desde']
    grant_founder([4], meses=6)
    f = _do(get_founder_program(), 4)
    assert f['desde'] == inicio, 'a renovação apagou a data de entrada'
    assert f['dias_restantes'] >= 170


def test_painel_separa_quem_HONRA_de_quem_so_usa():
    """O trato é uso E devolutiva. Quem usa muito e nunca fala não é o mesmo caso de quem
    usa e reporta — e o painel precisa dizer qual é qual, senão a renovação é chute."""
    init_db(); _limpa()
    _user(10, 'honra'); _user(11, 'sousa'); _user(12, 'sumiu')
    grant_founder([10, 11, 12], meses=6)

    _torneio(10, 'A'); _treino(10, '2026-08-01'); _treino(10, '2026-08-02'); _ticket(10)
    _torneio(11, 'B'); _treino(11, '2026-08-01'); _treino(11, '2026-08-02')
    # 12 não faz nada

    p = get_founder_program()
    assert _do(p, 10)['honrando'] is True
    assert _do(p, 11)['honrando'] is False, 'contou como honrando quem nunca deu retorno'
    assert _do(p, 11)['usou'] is True, 'quem usou tem que aparecer como tendo usado'
    assert _do(p, 12)['usou'] is False
    assert p['resumo'] == {'total': 3, 'honrando': 1, 'silenciosos': 1, 'vencendo_em_30d': 0}


def test_um_dia_so_de_treino_nao_conta_como_uso():
    """Mesmo critério do funil: usar é VOLTAR, não abrir uma vez."""
    init_db(); _limpa()
    _user(13, 'umdia')
    grant_founder([13], meses=6)
    _torneio(13, 'C'); _treino(13, '2026-08-01')
    assert _do(get_founder_program(), 13)['usou'] is False


def test_vencendo_em_30d_aparece_no_resumo():
    """É o gatilho da conversa de renovação — se não aparecer, o ciclo vence sozinho."""
    init_db(); _limpa()
    _user(14, 'quasela')
    grant_founder([14], meses=1)     # ~30 dias
    assert get_founder_program()['resumo']['vencendo_em_30d'] == 1


def test_revogar_so_atinge_fundador():
    init_db(); _limpa()
    _user(20, 'fund'); _user(21, 'assina', plan='pro', source='stripe_sub')
    grant_founder([20], meses=6)
    assert revoke_founder(20) is True
    assert get_quota_status(20)['plan'] == 'free'
    assert revoke_founder(21) is False, 'revogou um assinante que não era fundador'
    assert get_quota_status(21)['plan'] == 'pro'
    assert revoke_founder(999) is False, 'disse ter revogado usuário inexistente'


def test_concessao_relata_usuario_inexistente_em_vez_de_calar():
    """Regra 6: operação que pode falhar em silêncio precisa de conferência explícita."""
    init_db(); _limpa()
    res = grant_founder([777], meses=6)
    assert res['concedidos'] == []
    assert res['pulados'][0]['motivo'] == 'inexistente'


def test_fila_respeita_a_ordem_de_chegada():
    """A publicação promete "os N primeiros". Se a fila não sair na ordem em que as pessoas
    se candidataram, a promessa não é cumprível — e ninguém percebe pela tela."""
    init_db(); _limpa()
    _user(30, 'terceiro'); _user(31, 'primeiro'); _user(32, 'segundo')
    with get_conn() as conn:
        for uid, quando in ((31, '2026-08-01 10:00:00'),
                            (32, '2026-08-01 11:00:00'),
                            (30, '2026-08-02 09:00:00')):
            conn.execute(_adapt("UPDATE users SET founder_applied_at = ? WHERE id = ?"),
                         (quando, uid))
        conn.commit()
    fila = get_founder_candidates()
    assert [c['username'] for c in fila] == ['primeiro', 'segundo', 'terceiro'], fila
    assert [c['posicao'] for c in fila] == [1, 2, 3]


def test_candidatar_duas_vezes_nao_perde_o_lugar_na_fila():
    """Clicar de novo não pode jogar a pessoa para o fim da fila — seria punir quem
    interagiu mais, e a fila é justamente o critério prometido."""
    init_db(); _limpa()
    _user(40, 'clicou'); _user(41, 'depois')
    assert apply_as_founder(40) is True
    primeira = get_founder_candidates()[0]['founder_applied_at']
    apply_as_founder(41)
    assert apply_as_founder(40) is False, 'a 2ª candidatura reescreveu o registro'
    fila = get_founder_candidates()
    assert fila[0]['username'] == 'clicou', 'quem clicou 2x foi parar atrás'
    assert fila[0]['founder_applied_at'] == primeira


def test_aprovado_sai_da_fila():
    """Sem isto o admin reaprovaria a mesma pessoa a cada visita ao painel."""
    init_db(); _limpa()
    _user(50, 'aprovado'); _user(51, 'esperando')
    apply_as_founder(50); apply_as_founder(51)
    assert len(get_founder_candidates()) == 2
    grant_founder([50], meses=6)
    fila = get_founder_candidates()
    assert [c['username'] for c in fila] == ['esperando'], fila


def test_fila_traz_sinal_para_decidir():
    """Aprovar às cegas é o que enche o programa de silencioso. A fila mostra se a pessoa
    já fez alguma coisa antes de você dar 6 meses de Pro."""
    init_db(); _limpa()
    _user(60, 'jausou'); _user(61, 'sonome')
    apply_as_founder(60); apply_as_founder(61)
    _torneio(60, 'X'); _treino(60, '2026-08-01')
    fila = {c['username']: c for c in get_founder_candidates()}
    assert fila['jausou']['torneios'] == 1 and fila['jausou']['treinos'] == 1
    assert fila['sonome']['torneios'] == 0 and fila['sonome']['treinos'] == 0


def test_quem_nao_se_candidatou_nao_aparece_na_fila():
    """Contraprova: se a fila listasse todo mundo, ela não estaria medindo candidatura."""
    init_db(); _limpa()
    _user(70, 'pediu'); _user(71, 'nao_pediu')
    apply_as_founder(70)
    assert [c['username'] for c in get_founder_candidates()] == ['pediu']


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
