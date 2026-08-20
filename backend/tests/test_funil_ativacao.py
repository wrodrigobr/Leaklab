# -*- coding: utf-8 -*-
"""Funil de ativação (20/08) — o instrumento do programa de fundadores.

Regra 1: o diagnóstico PROVA que detecta. Cada degrau é forjado em banco descartável e o
número TEM que se mexer; zero tranquilizador num painel de ativação encerraria a pergunta
"onde estou perdendo gente?".

Contratos:
- cada degrau conta USUÁRIO DISTINTO que atravessou (não evento cru, que infla o gargalo);
- "voltou" = treinou em 2+ DIAS distintos (retenção é voltar, não permanecer);
- a conversão ENTRE degraus é o que revela o gargalo (o % sobre o topo esconde).
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

# Banco DESCARTÁVEL (a suíte do projeto usa SQLite em memória): sem isto o teste media o
# banco de desenvolvimento e a 1ª rodada falhou com "banco não estava limpo" — medir o dado
# de outra pessoa é a versão silenciosa do zero tranquilizador.
import tempfile                                        # noqa: E402
_TMPDB = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
_TMPDB.close()
os.environ['LEAKLAB_DB'] = _TMPDB.name                 # arquivo temp, não ':memory:':
os.environ.pop('DATABASE_URL', None)                   # em memória, cada conexão é um banco novo
from database.schema import get_conn, init_db          # noqa: E402
from database.repositories import _adapt, get_activation_funnel  # noqa: E402


def _limpa():
    with get_conn() as conn:
        for t in ('progression_attempts', 'tournaments', 'users'):
            try:
                conn.execute(_adapt(f"DELETE FROM {t}"))
            except Exception:
                pass
        conn.commit()


def _user(uid: int, email: str) -> int:
    with get_conn() as conn:
        conn.execute(_adapt(
            "INSERT INTO users (id, email, password_hash, username, role) VALUES (?,?,?,?,'player')"),
            (uid, email, 'x', email.split('@')[0]))
        conn.commit()
    return uid


def _torneio(uid: int, tid: str):
    with get_conn() as conn:
        # `hero` é NOT NULL — dublê incompleto acusa a coisa errada (a 1ª versão quebrou aqui)
        conn.execute(_adapt(
            "INSERT INTO tournaments (user_id, tournament_id, tournament_name, hero) "
            "VALUES (?,?,?,?)"), (uid, tid, 'T', 'Hero'))
        conn.commit()


def _treino(uid: int, dia: str, origem: str = 'trilha'):
    with get_conn() as conn:
        conn.execute(_adapt(
            "INSERT INTO progression_attempts (user_id, category_key, stratum, block_kind, "
            "correct, origem, created_at) VALUES (?,?,?,?,?,?,?)"),
            (uid, 'rfi:BTN::40', 'core', 'mission', 1, origem, f'{dia} 12:00:00'))
        conn.commit()


def _preso(uid: int, email: str, tentativas: int = 0):
    """Conta parada na confirmação de e-mail. `tentativas` separa as duas causas:
    0 = nunca digitou código nenhum (o e-mail não chegou); >0 = digitou e falhou."""
    with get_conn() as conn:
        conn.execute(_adapt(
            "INSERT INTO users (id, email, password_hash, username, role, email_verified, "
            "verification_attempts) VALUES (?,?,?,?,'player',0,?)"),
            (uid, email, 'x', email.split('@')[0], tentativas))
        conn.commit()


def _degrau(f: dict, key: str) -> int:
    return next(d['n'] for d in f['degraus'] if d['key'] == key)


def test_cada_degrau_prova_que_detecta():
    init_db()
    _limpa()
    base = get_activation_funnel(3650)
    assert _degrau(base, 'cadastrou') == 0, 'banco não estava limpo'

    _user(9001, 'so_cadastrou@t.com')
    f = get_activation_funnel(3650)
    assert _degrau(f, 'cadastrou') == 1 and _degrau(f, 'importou') == 0

    _user(9002, 'importou@t.com'); _torneio(9002, 'T1')
    f = get_activation_funnel(3650)
    assert _degrau(f, 'importou') == 1 and _degrau(f, 'treinou') == 0

    _treino(9002, '2026-08-01')
    f = get_activation_funnel(3650)
    assert _degrau(f, 'treinou') == 1, 'treino não moveu o degrau'
    assert _degrau(f, 'voltou') == 0, 'um dia só não é "voltou"'

    _treino(9002, '2026-08-02')
    f = get_activation_funnel(3650)
    assert _degrau(f, 'voltou') == 1, 'segundo DIA não contou como volta'


def test_degrau_conta_usuario_e_nao_evento():
    init_db(); _limpa()
    _user(9003, 'muitos_treinos@t.com'); _torneio(9003, 'T2')
    for i in range(1, 6):
        _treino(9003, f'2026-08-0{i}')
    f = get_activation_funnel(3650)
    assert _degrau(f, 'treinou') == 1, 'contou evento em vez de usuário (gargalo inflado)'


def test_conversao_entre_degraus_expoe_o_gargalo():
    init_db(); _limpa()
    for i in range(10):
        _user(9100 + i, f'u{i}@t.com')
    _torneio(9100, 'T3'); _treino(9100, '2026-08-01')
    f = get_activation_funnel(3650)
    assert f['entre']['cadastro_para_import'] == 10.0     # 1 de 10
    assert f['entre']['import_para_treino'] == 100.0      # 1 de 1 — o gargalo é ANTES
    assert f['entre']['treino_para_volta'] == 0.0


def test_porta_de_entrada_conta_quem_nunca_confirmou():
    """O degrau que faltava: sem confirmar o e-mail a conta não emite token e SOME — não
    aparece em nenhum outro degrau. Antes de 20/08 esses 7 jogadores eram invisíveis aqui."""
    init_db(); _limpa()
    _user(9300, 'entrou@t.com'); _torneio(9300, 'T5')
    _preso(9301, 'preso1@t.com'); _preso(9302, 'preso2@t.com')
    f = get_activation_funnel(3650)
    assert _degrau(f, 'cadastrou') == 3
    assert _degrau(f, 'confirmou') == 1, 'contou como confirmado quem está preso na porta'
    assert f['porta_de_entrada']['presos'] == 2
    assert f['entre']['cadastro_para_confirmacao'] == round(100 / 3, 1)


def test_separa_nao_recebeu_de_errou_o_codigo():
    """Os dois presos têm consertos OPOSTOS: entrega de e-mail vs janela do código.
    Somados num número só, o painel não diria qual consertar."""
    init_db(); _limpa()
    _preso(9310, 'nunca_recebeu@t.com', tentativas=0)
    _preso(9311, 'errou@t.com', tentativas=3)
    p = get_activation_funnel(3650)['porta_de_entrada']
    assert p['presos'] == 2
    assert p['sem_nenhuma_tentativa'] == 1, 'não separou quem nunca digitou nada'
    assert p['suspeita_de_entrega'] is False, 'metade tentou: não é falha de entrega'

    # Agora o cenário REAL de 20/08 — 7 de 7 sem nenhuma tentativa. Tem que acusar entrega.
    init_db(); _limpa()
    for i in range(7):
        _preso(9320 + i, f'p{i}@t.com', tentativas=0)
    p = get_activation_funnel(3650)['porta_de_entrada']
    assert p['sem_nenhuma_tentativa'] == 7 and p['suspeita_de_entrega'] is True


def test_banco_sem_ninguem_preso_nao_levanta_suspeita():
    """Contraprova: se a suspeita ligasse sozinha, o alarme não valeria nada."""
    init_db(); _limpa()
    _user(9330, 'ok@t.com')
    p = get_activation_funnel(3650)['porta_de_entrada']
    assert p['presos'] == 0 and p['suspeita_de_entrega'] is False


def test_origem_das_sessoes_aparece():
    init_db(); _limpa()
    _user(9200, 'origem@t.com'); _torneio(9200, 'T4')
    _treino(9200, '2026-08-01', origem='trilha')
    _treino(9200, '2026-08-02', origem='dashboard')
    ors = {o['origem']: o['tentativas'] for o in get_activation_funnel(3650)['origens']}
    assert ors.get('trilha') == 1 and ors.get('dashboard') == 1


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
