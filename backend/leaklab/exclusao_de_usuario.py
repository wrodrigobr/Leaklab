# -*- coding: utf-8 -*-
"""Exclusão COMPLETA de um usuário: cada tabela declarada, nada apagado por acidente.

── Por que uma lista DECLARADA e não CASCADE (30/08) ────────────────────────────────────────

O CASCADE já apagou 71 anotações de coach caladas neste projeto
([[project_cascade_apagava_anotacoes]]). Exclusão de usuário é a operação onde isso vira
tragédia: o que deve sumir precisa estar ESCRITO, e o guarda
(tests/test_exclusao_de_usuario.py) varre o schema inteiro e acusa qualquer tabela nova com
user_id que não esteja aqui — some por decisão, nunca por esquecimento (regra 5).

── O que a V1 recusa, de propósito ──────────────────────────────────────────────────────────

- **Admin**: não se exclui pela tela (proteção contra o clique errado de outro admin).
- **Coach**: tem alunos, comissões e material pendurado — precisa de fluxo próprio de
  transferência antes; recusar com mensagem é mais honesto que apagar metade.
- **A si mesmo**: o admin logado não se apaga (o botão errado mais caro que existe).
"""
from __future__ import annotations

import logging

from database.repositories import _adapt
from database.schema import get_conn

_log = logging.getLogger(__name__)

#: (tabela, [colunas que apontam para o usuário]). A ORDEM importa: filhos antes de pais.
#: Tabela ausente no ambiente (preguiçosa ainda não criada) conta como 0 — mas tabela que
#: EXISTE e falha ao apagar ABORTA a exclusão inteira: usuário meio-apagado é pior que inteiro.
TABELAS_DO_USUARIO: tuple = (
    # rastros de treino e progresso
    ('drill_sessions', ['user_id']),
    ('training_achievements', ['user_id']),
    ('training_daily', ['user_id']),
    ('training_proof', ['user_id']),
    ('training_skill_progress', ['user_id']),
    ('progression_attempts', ['user_id']),
    ('range_card_srs', ['user_id']),
    ('achievements', ['user_id']),
    ('session_goals', ['user_id']),
    ('session_checkins', ['user_id']),               # preguiçosa (ritual da sessão)
    ('daily_challenge_attempts', ['user_id']),
    ('player_elo_history', ['user_id']),
    ('leaderboard_snapshots', ['user_id']),
    # comunicação e uso
    ('notifications', ['user_id']),
    ('support_tickets', ['user_id']),
    ('feature_usage', ['user_id']),
    ('engagement_emails', ['user_id']),
    ('telegram_intros', ['user_id']),
    ('llm_cache', ['user_id']),
    ('evolution_reports', ['user_id']),
    # comunidade (preguiçosas): comentários do usuário em mãos alheias; votos dos links dele
    # comentarios DELE em maos alheias (user_id) E os fios nos links DELE (token — o guarda
    # pegou a sobra: comentario de terceiro na mao excluida ficava orfao)
    ('shared_hand_comments', ['user_id']),
    ('shared_hand_votes', []),                        # via token dos links dele (especial)
    ('shared_hands', ['user_id']),
    # dinheiro (histórico fiscal fica? decisão V1: some junto — LGPD manda; extrato real vive
    # no Stripe, que é a fonte fiscal)
    ('payments', ['user_id']),
    # trilha de mudança de plano: mesma decisão do `payments` — LGPD manda, e o extrato real
    # vive no Stripe. Declarada aqui, e não deixada para o `ON DELETE CASCADE` da FK, porque
    # CASCADE apaga CALADO: o relatório que o admin lê depois da exclusão não contaria estas
    # linhas, e "sumiu sem ninguém apagar" já custou 71 anotações de coach uma vez.
    ('plan_audit', ['user_id']),
    # relação com coach QUANDO O EXCLUÍDO É O ALUNO
    ('coach_baselines', ['student_id']),
    ('coach_commissions', ['student_id']),
    ('coach_hand_annotations', ['student_id']),
    ('coach_messages', ['student_id']),
    ('coach_reviews', ['student_id']),
    ('coach_study_overrides', ['student_id']),
    # candidatura a coach (perfil de jogador pode ter uma pendente)
    ('coach_applications', ['user_id']),
    # torneios por último entre os filhos: decisions/opponent_profiles saem por eles
    ('gto_hand_requests', []),                        # fila do solver, via tournament_id
    ('decisions', []),                                # via tournament_id (especial)
    ('opponent_profiles', []),                        # via tournament_id (especial)
    ('tournaments', ['user_id']),
)

#: Tabelas com colunas de usuário que a exclusão NÃO toca, com o motivo — o guarda exige que
#: toda tabela do schema esteja numa das duas listas.
FORA_DA_EXCLUSAO: dict = {
    'coach_profiles':       'perfil de COACH — a V1 recusa excluir coach; fluxo próprio depois',
    'coach_invites':        'material do coach (dono é o coach, não o aluno excluído)',
    'coach_payments':       'repasses do coach — contabilidade dele, não do aluno',
    'coach_plan_templates': 'material do coach',
}


def excluir_usuario(user_id: int, executado_por: int) -> dict:
    """Apaga o usuário e TODOS os rastros declarados. Levanta ValueError nas recusas da V1.

    Retorna {tabela: n_apagados} para o admin VER o que saiu — exclusão silenciosa é como
    nascem os "cadê os dados?" sem resposta.
    """
    if user_id == executado_por:
        raise ValueError('você não pode excluir a própria conta por aqui')
    conn = get_conn()
    try:
        row = conn.execute(_adapt('SELECT id, username, role FROM users WHERE id = ?'),
                           (user_id,)).fetchone()
        if not row:
            raise ValueError('usuário não encontrado')
        alvo = dict(row)
        if (alvo.get('role') or 'player') == 'admin':
            raise ValueError('conta admin não pode ser excluída pela tela')
        if (alvo.get('role') or 'player') == 'coach':
            raise ValueError('coach tem alunos e material vinculados: transfira antes '
                             '(fluxo de exclusão de coach ainda não existe)')

        tids = [dict(r)['id'] for r in conn.execute(_adapt(
            'SELECT id FROM tournaments WHERE user_id = ?'), (user_id,)).fetchall()]
        tokens = [dict(r)['token'] for r in conn.execute(_adapt(
            'SELECT token FROM shared_hands WHERE user_id = ?'), (user_id,)).fetchall()] \
            if _tabela_existe(conn, 'shared_hands') else []

        placar: dict = {}
        for tabela, colunas in TABELAS_DO_USUARIO:
            if not _tabela_existe(conn, tabela):
                placar[tabela] = 'ausente'
                continue
            n = 0
            if tabela in ('decisions', 'gto_hand_requests'):
                for tid in tids:
                    cur = conn.execute(_adapt(
                        f'DELETE FROM {tabela} WHERE tournament_id = ?'), (tid,))
                    n += getattr(cur, 'rowcount', 0) or 0
            elif False:
                for tid in tids:
                    cur = conn.execute(_adapt('DELETE FROM decisions WHERE tournament_id = ?'),
                                       (tid,))
                    n += getattr(cur, 'rowcount', 0) or 0
            elif tabela == 'opponent_profiles':
                for tid in tids:
                    cur = conn.execute(_adapt(
                        'DELETE FROM opponent_profiles WHERE tournament_id = ?'), (tid,))
                    n += getattr(cur, 'rowcount', 0) or 0
            elif tabela == 'shared_hand_votes':
                for tk in tokens:
                    cur = conn.execute(_adapt(
                        'DELETE FROM shared_hand_votes WHERE token = ?'), (tk,))
                    n += getattr(cur, 'rowcount', 0) or 0
            elif tabela == 'shared_hand_comments':
                for col in colunas:
                    cur = conn.execute(_adapt(
                        f'DELETE FROM shared_hand_comments WHERE {col} = ?'), (user_id,))
                    n += getattr(cur, 'rowcount', 0) or 0
                for tk in tokens:
                    cur = conn.execute(_adapt(
                        'DELETE FROM shared_hand_comments WHERE token = ?'), (tk,))
                    n += getattr(cur, 'rowcount', 0) or 0
            else:
                for col in colunas:
                    cur = conn.execute(_adapt(
                        f'DELETE FROM {tabela} WHERE {col} = ?'), (user_id,))
                    n += getattr(cur, 'rowcount', 0) or 0
            placar[tabela] = n

        cur = conn.execute(_adapt('DELETE FROM users WHERE id = ?'), (user_id,))
        assert getattr(cur, 'rowcount', 0), 'a linha do usuário não saiu'
        conn.commit()
        _log.warning('EXCLUSAO de usuario %s (%s) executada por admin %s: %s',
                     user_id, alvo['username'], executado_por,
                     {k: v for k, v in placar.items() if v not in (0, 'ausente')})
        return placar
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def _tabela_existe(conn, nome: str) -> bool:
    try:
        conn.execute(_adapt(f'SELECT 1 FROM {nome} LIMIT 1'))
        return True
    except Exception:                                          # noqa: BLE001
        conn.rollback()
        return False
