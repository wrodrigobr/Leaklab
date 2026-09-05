# -*- coding: utf-8 -*-
"""Quem pode rebaixar um usuário, e quem não pode (05/09).

── O que originou ────────────────────────────────────────────────────────────────────────

O dono avisou que o único assinante pagante tinha caído para Free "mais uma vez", e logo
depois que um FUNDADOR também. A consulta em produção mostrou o tamanho real: **10
rebaixamentos, 100% deles com `cancel_reason='incomplete_expired'`** — nenhuma cancelação
verdadeira na tabela inteira. Três dos atingidos eram fundadores; um era o pagante, cuja
assinatura seguia ACTIVE no Stripe enquanto o nosso banco o mandava para Free.

`incomplete_expired` é a assinatura CRIADA e nunca paga, que o Stripe expira ~24h depois.
Ela nunca esteve ativa, então não tem o que cancelar. Estava na mesma lista de `canceled`.

O amplificador foi o CheckoutModal criando uma assinatura por abertura do modal — um
usuário acumulou 8 em 11 segundos, e cada fantasma virava um rebaixamento no dia seguinte.

── Os quatro defeitos, e por que cada teste existe ───────────────────────────────────────

1. `incomplete_expired` tratado como cancelamento (a raiz).
2. O handler do webhook forçava `status='canceled'` em todo `deleted`, destruindo o status
   real ANTES de a política poder decidir.
3. A guarda de 03/09 (ignorar evento de assinatura que não é a atual) depende de
   `mp_subscription_id` — e o próprio downgrade APAGA esse campo. Depois do primeiro
   acidente ela ficava desarmada e todo evento seguinte derrubava de novo. Era literalmente
   o "mais uma vez".
4. `update_user_admin` escrevia só a coluna `plan`, deixando uma linha que se contradiz:
   ou desarmava a guarda (3), ou fazia `get_quota_status` devolver 'free' na leitura com o
   banco dizendo 'pro'.

O caso levou horas para ser diagnosticado porque **não havia registro nenhum** de mudança
de plano. `plan_audit` nasceu disso, e tem teste de varredura próprio aqui.
"""
import io
import os
import re
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

_TMPDB = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
_TMPDB.close()
os.environ['LEAKLAB_DB'] = _TMPDB.name
os.environ.pop('DATABASE_URL', None)

from database.schema import get_conn, init_db                          # noqa: E402
import database.repositories as repo                                   # noqa: E402
from database.repositories import (                                    # noqa: E402
    PLAN_SOURCES_SEM_RECEITA, _adapt, apply_stripe_subscription, get_quota_status,
    grant_founder, update_user_admin,
)

_RAIZ = os.path.join(os.path.dirname(__file__), '..')


def _limpa():
    conn = get_conn()
    conn.execute("DELETE FROM plan_audit")
    conn.execute("DELETE FROM users")
    conn.commit()
    conn.close()


def _user(uid, nome, **campos):
    conn = get_conn()
    conn.execute(_adapt("INSERT INTO users (id, username, email, password_hash, role) "
                        "VALUES (?, ?, ?, 'x', 'player')"),
                 (uid, nome, '%s@x.com' % nome))
    for k, v in campos.items():
        conn.execute(_adapt("UPDATE users SET %s = ? WHERE id = ?" % k), (v, uid))
    conn.commit()
    conn.close()


def _estado(uid):
    conn = get_conn()
    r = dict(conn.execute(_adapt(
        "SELECT plan, plan_source, mp_subscription_id, plan_expires_at FROM users WHERE id = ?"),
        (uid,)).fetchone())
    conn.close()
    return r


def _auditoria(uid):
    conn = get_conn()
    rows = [dict(r) for r in conn.execute(_adapt(
        "SELECT origem, detalhe, plan_antes, plan_depois FROM plan_audit "
        "WHERE user_id = ? ORDER BY id"), (uid,)).fetchall()]
    conn.close()
    return rows


# ── 1. A raiz: checkout abandonado não rebaixa ninguém ────────────────────────────────

def test_incomplete_expired_nao_rebaixa_o_pagante():
    """O caso literal do micheldienstmann25: assinatura real ACTIVE, fantasma expirando."""
    init_db(); _limpa()
    _user(1, 'pagante')
    apply_stripe_subscription(1, 'active', '2026-12-01 00:00:00', 'sub_REAL')
    assert _estado(1)['plan'] == 'pro'

    acao = apply_stripe_subscription(1, 'incomplete_expired', None, 'sub_FANTASMA')
    assert acao == 'ignored_never_active', acao
    assert _estado(1)['plan'] == 'pro', 'checkout abandonado derrubou o pagante'
    assert _estado(1)['mp_subscription_id'] == 'sub_REAL', 'perdeu o vínculo da assinatura real'


def test_cancelamento_de_verdade_continua_rebaixando():
    """Contraprova da anterior: sem ela, o teste acima passaria com o downgrade desligado."""
    init_db(); _limpa()
    _user(2, 'cancelou')
    apply_stripe_subscription(2, 'active', '2026-12-01 00:00:00', 'sub_REAL')
    acao = apply_stripe_subscription(2, 'canceled', None, 'sub_REAL')
    assert acao == 'downgraded', acao
    assert _estado(2)['plan'] == 'free'


# ── 2. Procedência: o Stripe não manda em Pro concedido por fora ──────────────────────

def test_evento_do_stripe_nao_rebaixa_fundador():
    """aguiard109 e rulliansiqueira, na prática: fundador derrubado por sub fantasma."""
    init_db(); _limpa()
    _user(3, 'fundador')
    grant_founder([3], meses=6)
    assert _estado(3)['plan_source'] == 'founder'

    acao = apply_stripe_subscription(3, 'canceled', None, 'sub_QUALQUER')
    assert acao == 'ignored_non_stripe_plan', acao
    assert _estado(3)['plan'] == 'pro', 'o Stripe rebaixou um fundador'
    assert _estado(3)['plan_source'] == 'founder'


# ── 3. A guarda que se desarmava sozinha ──────────────────────────────────────────────

def test_guarda_continua_armada_depois_do_conserto_pelo_admin():
    """O 'mais uma vez'. O downgrade apaga `mp_subscription_id`; o conserto pelo painel não
    o restaura; a guarda antiga, que só olhava esse campo, ficava cega para sempre."""
    init_db(); _limpa()
    _user(4, 'reincidente')
    apply_stripe_subscription(4, 'active', '2026-12-01 00:00:00', 'sub_REAL')
    apply_stripe_subscription(4, 'canceled', None, 'sub_REAL')          # cai (legítimo)
    assert _estado(4)['mp_subscription_id'] is None

    update_user_admin(4, plan='pro', por=99)                            # dono conserta
    assert _estado(4)['plan'] == 'pro'

    acao = apply_stripe_subscription(4, 'canceled', None, 'sub_FANTASMA')
    assert acao == 'ignored_non_stripe_plan', acao
    assert _estado(4)['plan'] == 'pro', 'rebaixado de novo depois do conserto'


# ── 4. O painel do admin grava estado coerente ────────────────────────────────────────

def test_pro_dado_pelo_admin_e_lido_como_pro_pelo_produto():
    """O banco dizia 'pro' e o produto entregava 'free': `get_quota_status` rebaixa na
    leitura quando a vigência venceu, e o painel não limpava a vigência herdada."""
    init_db(); _limpa()
    _user(5, 'concedido', plan='free', plan_expires_at='2026-01-01 00:00:00')
    update_user_admin(5, plan='pro', por=99)

    assert _estado(5)['plan_source'] == 'admin'
    q = get_quota_status(5)
    assert q['plan'] == 'pro', 'banco diz pro, produto lê %r' % q['plan']
    assert not q.get('expired')


# ── 5. A trilha de auditoria (a ausência dela foi metade do custo do diagnóstico) ──────

def test_toda_mudanca_de_plano_deixa_rastro():
    init_db(); _limpa()
    _user(6, 'rastreado')
    apply_stripe_subscription(6, 'active', '2026-12-01 00:00:00', 'sub_REAL')
    apply_stripe_subscription(6, 'canceled', None, 'sub_REAL')
    update_user_admin(6, plan='pro', por=99)

    linhas = _auditoria(6)
    assert len(linhas) == 3, 'esperava 3 mudanças registradas, veio %d' % len(linhas)
    assert [l['origem'] for l in linhas] == ['stripe_webhook', 'stripe_webhook', 'admin']
    assert [(l['plan_antes'], l['plan_depois']) for l in linhas] == [
        ('free', 'pro'), ('pro', 'free'), ('free', 'pro')]
    assert 'sub_REAL' in (linhas[1]['detalhe'] or ''), 'a trilha não diz QUAL assinatura'


def test_evento_ignorado_nao_polui_a_trilha():
    """Trilha que registra não-mudança vira ruído e para de ser lida."""
    init_db(); _limpa()
    _user(7, 'quieto')
    grant_founder([7], meses=6)
    antes = len(_auditoria(7))
    apply_stripe_subscription(7, 'incomplete_expired', None, 'sub_FANTASMA')
    apply_stripe_subscription(7, 'canceled', None, 'sub_FANTASMA')
    assert len(_auditoria(7)) == antes


# ── 6. Regra 5: a pergunta "este Pro é receita?" tem UM dono ──────────────────────────

def test_nenhuma_copia_solta_da_regra_de_pagante():
    """Varredura N+1. A cláusula vivia copiada em 5 consultas, e as procedências criadas
    depois não entraram em nenhuma: `founder` contava como assinante pagante no MRR.
    Este teste falha se alguém escrever a lista à mão de novo em vez de usar a função."""
    suspeitas = []
    for pasta in ('api', 'database', 'leaklab', 'scripts'):
        base = os.path.join(_RAIZ, pasta)
        for raiz, _, arquivos in os.walk(base):
            for nome in arquivos:
                if not nome.endswith('.py'):
                    continue
                caminho = os.path.join(raiz, nome)
                texto = io.open(caminho, encoding='utf-8', errors='ignore').read()
                for m in re.finditer(r"plan_source\s+NOT\s+IN\s*\(", texto, re.IGNORECASE):
                    linha = texto[:m.start()].count('\n') + 1
                    suspeitas.append('%s/%s:%d' % (pasta, nome, linha))
    assert not suspeitas, 'cláusula de pagante escrita à mão em: %s' % ', '.join(suspeitas)


def test_pro_concedido_fica_fora_da_receita():
    """Fundador, cortesia de coach e concessão do admin não são MRR."""
    for origem in ('founder', 'admin', 'coach_trial', 'coach_earned'):
        assert origem in PLAN_SOURCES_SEM_RECEITA, '%s entraria no MRR' % origem
    clausula = repo._sql_pro_pagante('u.')
    assert clausula.count('u.plan_source') == 2, clausula
    for origem in PLAN_SOURCES_SEM_RECEITA:
        assert "'%s'" % origem in clausula, '%s ficou fora da cláusula' % origem


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
