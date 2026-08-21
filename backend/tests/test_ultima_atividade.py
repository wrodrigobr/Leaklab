# -*- coding: utf-8 -*-
"""`last_login` reflete USO, não só o momento em que a pessoa digitou a senha.

── O que estava errado ────────────────────────────────────────────────────────────────────

`touch_activity` só era chamado no `/auth/login`, e o token dura dias. Resultado medido em
produção (21/08): quem entrou uma vez e continuou usando ficava com a data congelada, e
quem recebeu o token direto do cadastro ficava com NULL para sempre — 12 de 13 contas
paradas apareciam como "nunca logou" mesmo tendo usado.

A docstring de `touch_activity` já prometia "chamado de forma throttled pelo require_auth";
só que ninguém chamava. Pendência que envelheceu calada.

Isso importa porque o painel de admin passou a mostrar a coluna "Última atividade", e é
por ela que se decide quem sumiu do programa de fundadores. **Coluna que mente é pior que
coluna ausente**: mandaria mensagem de reativação para quem está usando todo dia.

── O que estes testes travam ──────────────────────────────────────────────────────────────

1. usar a API (não só logar) registra atividade;
2. o registro é throttled por DIA — sem isso, cada chamada viraria um UPDATE, e uma sessão
   de treino faz centenas;
3. falha ao registrar NÃO derruba a requisição do jogador.
"""
import os
import sys
import tempfile
from datetime import datetime, timedelta

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
os.environ['LEAKLAB_DB'] = tempfile.mktemp(suffix='.db')

import database.schema as sch          # noqa: E402
import database.repositories as repo   # noqa: E402
from database.auth import _marcar_atividade  # noqa: E402

sch.init_db()


def _last_login(uid):
    conn = repo.get_conn()
    try:
        r = conn.execute(repo._adapt("SELECT last_login FROM users WHERE id = ?"),
                         (uid,)).fetchone()
        return dict(r)['last_login'] if r else None
    finally:
        conn.close()


def _set_last_login(uid, valor):
    conn = repo.get_conn()
    try:
        conn.execute(repo._adapt("UPDATE users SET last_login = ? WHERE id = ?"), (valor, uid))
        conn.commit()
    finally:
        conn.close()


def test_usar_a_api_registra_atividade_mesmo_sem_logar_de_novo():
    """O caso que originou tudo: token válido, pessoa usando, e a data congelada."""
    uid = repo.create_user('ativo', 'ativo@t.com', 'pass1234')
    _set_last_login(uid, None)
    assert _last_login(uid) is None

    _marcar_atividade({'id': uid, 'last_login': None})
    depois = _last_login(uid)
    assert depois, 'usar a API não registrou atividade nenhuma'
    assert str(depois)[:10] == datetime.utcnow().strftime('%Y-%m-%d')


def test_registro_e_throttled_por_dia():
    """Sem o throttle, uma sessão de treino faria centenas de UPDATEs no mesmo usuário."""
    uid = repo.create_user('throttle', 'throttle@t.com', 'pass1234')
    agora = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
    _set_last_login(uid, agora)

    # Marca um valor reconhecível: se o throttle funcionar, ele NÃO é sobrescrito.
    marca = datetime.utcnow().strftime('%Y-%m-%d') + ' 03:33:33'
    _set_last_login(uid, marca)
    _marcar_atividade({'id': uid, 'last_login': marca})
    assert _last_login(uid) == marca, 'gravou de novo no mesmo dia — throttle não funciona'


def test_dia_novo_atualiza():
    """Contraprova do teste acima: se nunca atualizasse, o throttle estaria bom demais."""
    uid = repo.create_user('ontem', 'ontem@t.com', 'pass1234')
    ontem = (datetime.utcnow() - timedelta(days=1)).strftime('%Y-%m-%d %H:%M:%S')
    _set_last_login(uid, ontem)

    _marcar_atividade({'id': uid, 'last_login': ontem})
    depois = _last_login(uid)
    assert str(depois)[:10] == datetime.utcnow().strftime('%Y-%m-%d'), \
        'dia novo não atualizou — a coluna ficaria congelada para sempre'


def test_falha_ao_registrar_nao_derruba_a_requisicao():
    """Registrar atividade é acessório. Se quebrar, o jogador não pode ver erro por isso."""
    _marcar_atividade({'id': None, 'last_login': None})       # user_id inválido
    _marcar_atividade({})                                      # dict sem nada
    _marcar_atividade({'id': 999999, 'last_login': 'lixo'})    # usuário inexistente
    # Chegar aqui sem exceção É o teste.


def test_require_auth_chama_o_registro():
    """Regra 5: a chamada tem que existir NO decorator. A versão anterior tinha a função
    pronta e nenhum chamador — e ninguém percebeu por meses."""
    import inspect
    from database import auth
    fonte = inspect.getsource(auth.require_auth)
    assert '_marcar_atividade' in fonte, \
        'require_auth não registra atividade — a coluna volta a mentir'


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
