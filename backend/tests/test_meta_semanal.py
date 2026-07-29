"""
Meta semanal: a contagem bate com as tentativas, em datas conhecidas e no fuso do aluno.

── Por que este arquivo existe ───────────────────────────────────────────────────────────────

Spec cobranca-proximo-passo.md §6. A cobrança passa a ser contra o compromisso DO ALUNO ("você
prometeu 3, treinou em 1"), então o número tem que estar certo: cobrar alguém por não cumprir
uma meta que ele cumpriu é a maneira mais rápida de perder a credibilidade de toda a cobrança.

Dois riscos concretos, e os dois têm teste:

  · **Fuso.** Os carimbos são UTC. Quem treina 21h no Brasil está em outro DIA no UTC, e na
    virada de domingo para segunda está em outra SEMANA. Contar no fuso do servidor erraria
    justamente o jogador que treina à noite, que é a maioria.
  · **Fronteira da semana.** Segunda 00:00 entra; domingo 23:59 da semana anterior não.

── Desvio consciente da spec, registrado ─────────────────────────────────────────────────────

A spec dizia "sessões por semana". `progression_attempts` não tem identidade de sessão, só
carimbos — perguntar em sessões e contar dias seria um número que não responde à pergunta feita.
Pergunta e medida são ambas em DIAS.
"""
import os, sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from leaklab.meta_semanal import (inicio_da_semana, dias_treinados_na_semana,
                                  progresso_semanal, normalizar_meta, OPCOES)

# Quarta-feira, 29/07/2026, 12:00 UTC. A segunda desta semana é 27/07.
QUARTA = '2026-07-29T12:00:00'


def test_a_semana_comeca_na_segunda():
    assert inicio_da_semana(QUARTA).startswith('2026-07-27T00:00:00')
    # e numa segunda-feira, a semana começa nela mesma
    assert inicio_da_semana('2026-07-27T08:00:00').startswith('2026-07-27T00:00:00')
    # domingo pertence à semana que começou na segunda anterior
    assert inicio_da_semana('2026-08-02T23:00:00').startswith('2026-07-27T00:00:00')


def test_conta_DIAS_distintos_e_nao_tentativas():
    """40 spots numa terça contam 1, igual a 12 spots numa terça. A meta é sobre frequência, e
    frequência é o que o espaçamento exige."""
    mesma_terca = ['2026-07-28T09:00:00', '2026-07-28T09:05:00', '2026-07-28T21:40:00']
    assert dias_treinados_na_semana(mesma_terca, QUARTA) == 1
    tres_dias = ['2026-07-27T10:00:00', '2026-07-28T10:00:00', '2026-07-29T10:00:00']
    assert dias_treinados_na_semana(tres_dias, QUARTA) == 3


def test_semana_anterior_NAO_conta():
    """Sem reset a meta não é compromisso, é saldo acumulado."""
    anterior = ['2026-07-26T23:59:00', '2026-07-20T10:00:00']   # domingo e segunda anteriores
    assert dias_treinados_na_semana(anterior, QUARTA) == 0
    # a fronteira exata: segunda 00:00 entra
    assert dias_treinados_na_semana(['2026-07-27T00:00:00'], QUARTA) == 1


def test_o_FUSO_do_aluno_decide_o_dia():
    """Quem treina 21h no Brasil (BRT = -180) aparece no UTC já no dia seguinte. Contar no fuso
    do servidor erraria justamente quem treina à noite, que é a maioria."""
    # 30/07 00:30 UTC = 29/07 21:30 no Brasil → ainda é quarta para o aluno
    carimbos = ['2026-07-29T14:00:00', '2026-07-30T00:30:00']
    assert dias_treinados_na_semana(carimbos, QUARTA, tz_offset_min=0) == 2, 'em UTC são 2 dias'
    assert dias_treinados_na_semana(carimbos, QUARTA, tz_offset_min=-180) == 1, \
        'no fuso do aluno é o MESMO dia'


def test_o_fuso_tambem_move_a_fronteira_da_SEMANA():
    """Segunda 01:00 UTC é domingo 22:00 no Brasil: semana passada para o aluno, semana nova
    para o servidor."""
    seg_madrugada = ['2026-07-27T01:00:00']
    assert dias_treinados_na_semana(seg_madrugada, QUARTA, tz_offset_min=0) == 1
    assert dias_treinados_na_semana(seg_madrugada, QUARTA, tz_offset_min=-180) == 0


def test_progresso_e_None_quando_nao_ha_meta():
    """None é 'ainda não perguntamos', e é ele que dispara a pergunta na tela. Zero diria
    'meta zero', que é outra coisa."""
    assert progresso_semanal(None, 3) is None
    assert progresso_semanal(0, 3) is None


def test_progresso_reporta_cumprida():
    assert progresso_semanal(3, 1) == {'prometidas': 3, 'feitas': 1, 'cumprida': False}
    assert progresso_semanal(3, 3) == {'prometidas': 3, 'feitas': 3, 'cumprida': True}
    assert progresso_semanal(3, 5)['cumprida'] is True, 'passar da meta não desconta'


def test_so_aceita_as_opcoes_oferecidas():
    """Meta fora da lista viraria número que a tela não sabe renderizar e que o e-mail cobraria
    como promessa."""
    for v in OPCOES:
        assert normalizar_meta(v) == v
        assert normalizar_meta(str(v)) == v
    for mau in (0, 1, 4, 7, 99, -3, None, '', 'tres', 3.7):
        assert normalizar_meta(mau) is None, mau


def test_carimbo_ilegivel_e_ignorado_sem_derrubar_a_contagem():
    misto = ['2026-07-28T10:00:00', 'lixo', None, '', '2026-07-29T10:00:00']
    assert dias_treinados_na_semana(misto, QUARTA) == 2


def test_ponta_a_ponta_com_datas_conhecidas():
    """O 'pronto quando' da Fase 3: a contagem bate com `progression_attempts` num caso forjado
    com datas que eu escolhi."""
    os.environ.pop('DATABASE_URL', None)
    from database.schema import init_db, get_conn
    from database.repositories import (_adapt, set_meta_semanal, get_meta_semanal,
                                       carimbos_de_treino_recentes)
    from leaklab.proximo_passo import meta_semanal_de
    from datetime import datetime, timedelta
    init_db()
    u = 990040
    c = get_conn()
    try:
        c.execute(_adapt('INSERT INTO users (id, email, username, password_hash) VALUES (?,?,?,?)'),
                  (u, 'meta@t.local', 'meta', 'x'))
    except Exception:
        pass
    c.execute(_adapt('DELETE FROM progression_attempts WHERE user_id = ?'), (u,))
    # Zera a meta: o arquivo do SQLite sobrevive entre execuções, e sem isto a meta gravada na
    # rodada anterior vira o estado inicial da próxima. Já me pegou uma vez nesta mesma suíte —
    # o teste passa sozinho e falha na segunda execução, sem ninguém tocar no código.
    c.execute(_adapt('UPDATE users SET weekly_training_goal = NULL WHERE id = ?'), (u,))
    # Datas relativas a AGORA, para cair dentro da semana corrente independente de quando o
    # teste roda: hoje e ontem (2 dias), mais duas tentativas no mesmo dia de hoje (não contam
    # de novo).
    agora = datetime.utcnow()
    for quando in (agora, agora - timedelta(minutes=5), agora - timedelta(days=1)):
        c.execute(_adapt('INSERT INTO progression_attempts (user_id, category_key, stratum, '
                         'correct, created_at) VALUES (?,?,?,?,?)'),
                  (u, 'rfi:UTG::50', 'nucleo', 1, quando.isoformat()))
    c.commit(); c.close()

    assert meta_semanal_de(u) is None, 'sem meta declarada, o payload traz None'
    assert set_meta_semanal(u, 3) is True
    assert get_meta_semanal(u) == 3
    assert not set_meta_semanal(u, 4), 'meta fora das opções é recusada'
    assert get_meta_semanal(u) == 3, 'a recusa não pode sobrescrever a meta válida'

    carimbos = carimbos_de_treino_recentes(u)
    assert len(carimbos) == 3, carimbos
    m = meta_semanal_de(u)
    assert m['prometidas'] == 3, m
    # hoje + ontem = 2 dias, a menos que a virada de semana caia entre eles (segunda de manhã)
    assert m['feitas'] in (1, 2), m
    assert m['cumprida'] is False


if __name__ == '__main__':
    falhas = 0
    testes = (test_a_semana_comeca_na_segunda,
              test_conta_DIAS_distintos_e_nao_tentativas,
              test_semana_anterior_NAO_conta,
              test_o_FUSO_do_aluno_decide_o_dia,
              test_o_fuso_tambem_move_a_fronteira_da_SEMANA,
              test_progresso_e_None_quando_nao_ha_meta,
              test_progresso_reporta_cumprida,
              test_so_aceita_as_opcoes_oferecidas,
              test_carimbo_ilegivel_e_ignorado_sem_derrubar_a_contagem,
              test_ponta_a_ponta_com_datas_conhecidas)
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
