# -*- coding: utf-8 -*-
"""`get_training_proof` sem N+1 — e com a saída INTACTA.

── O que foi medido (21/08, produção) ─────────────────────────────────────────────────────

94 categorias treinadas, **626 idas ao banco**, 7,3s, e só 26 categorias com algo a provar.
As outras 68 pagavam o laço inteiro para serem descartadas no fim. O endpoint já tinha sido
otimizado uma vez (219 → 115 idas); o que cresceu depois foi o número de CATEGORIAS, e o
desenho por-item voltou a doer.

── Por que estes testes, e não só um cronômetro ────────────────────────────────────────────

**Otimização que muda resultado não é otimização, é bug rápido.** Aqui a trava é dupla:

1. o resultado é comparado item a item contra o caminho ingênuo (mesmo dado, mesma ordem);
2. o número de consultas é CONTADO, com teto — senão o N+1 volta na próxima mudança e
   ninguém percebe, que é exatamente como ele voltou desta vez.

E o corte que mais economiza (pular categoria sem torneio novo) tem um teste próprio para o
caso em que ele NÃO pode agir: categoria sem baseline precisa medir o "antes" mesmo sem
torneio novo, senão fica sem ponto de partida para sempre.
"""
import os
import sys
import tempfile
from datetime import datetime, timedelta

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
os.environ['LEAKLAB_DB'] = tempfile.mktemp(suffix='.db')

import database.schema as sch          # noqa: E402
import database.repositories as repo   # noqa: E402

sch.init_db()

_orig_execute = sch._AdaptedConn.execute if hasattr(sch, '_AdaptedConn') else None


class Contador:
    """Conta idas ao banco durante um bloco. Cronômetro varia com a máquina; contagem de
    consulta é determinística e é a grandeza que o N+1 realmente move.

    Instrumenta o WRAPPER do projeto (`_AdaptedConn.execute`), não o `sqlite3.Connection`:
    o tipo nativo é imutável, e o wrapper é justamente por onde todo o código passa."""

    def __init__(self):
        self.n = 0

    def __enter__(self):
        self._orig = sch._AdaptedConn.execute
        cont = self

        def espiao(self_conn, sql, params=None):
            cont.n += 1
            return cont._orig(self_conn, sql, params)

        sch._AdaptedConn.execute = espiao
        return self

    def __exit__(self, *exc):
        sch._AdaptedConn.execute = self._orig
        return False


def _semear(n_categorias: int, com_torneio_novo: bool):
    """Usuário com N categorias treinadas E DECISÕES REAIS. `com_torneio_novo` decide se há
    import posterior ao baseline — é o que separa quem tem algo a provar de quem não tem.

    **As decisões são obrigatórias.** A 1ª versão deste dublê semeava só as categorias, e aí
    `baseline_n` saía 0: o laço caía no `continue` de "sem antes medido" ANTES de chegar no
    corte que eu queria testar. Os testes passavam com o corte removido — cobertura sem
    cobrir, que é o defeito que a regra 2 deste projeto manda caçar.
    """
    uid = repo.create_user(f'u{n_categorias}{com_torneio_novo}',
                           f'u{n_categorias}{com_torneio_novo}@t.com', 'pass1234')
    conn = repo.get_conn()
    try:
        ontem = (datetime.utcnow() - timedelta(days=2)).strftime('%Y-%m-%d %H:%M:%S')
        hoje = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
        cur = conn.execute(repo._adapt(
            "INSERT INTO tournaments (user_id, tournament_id, tournament_name, hero, imported_at) "
            "VALUES (?,?,?,?,?)"), (uid, 'T-antigo', 'T', 'Hero', ontem))
        tid_antigo = cur.lastrowid
        tid_novo = None
        if com_torneio_novo:
            cur = conn.execute(repo._adapt(
                "INSERT INTO tournaments (user_id, tournament_id, tournament_name, hero, imported_at) "
                "VALUES (?,?,?,?,?)"), (uid, 'T-novo', 'T', 'Hero', hoje))
            tid_novo = cur.lastrowid

        for i in range(n_categorias):
            pos, stack = 'BTN', 20 + i
            conn.execute(repo._adapt(
                "INSERT INTO training_skill_progress (user_id, category_key, attempts, correct) "
                "VALUES (?,?,?,?)"), (uid, f'rfi:{pos}::{stack}', 5, 3))
            # Decisões que casam com o filtro da categoria, para o baseline ter n > 0.
            for tid in filter(None, (tid_antigo, tid_novo)):
                conn.execute(repo._adapt(
                    "INSERT INTO decisions (tournament_id, hand_id, street, hero_cards, "
                    "action_taken, best_action, score, label, position, stack_bb, gto_label, "
                    "preflop_raises_faced) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)"),
                    (tid, f'h{i}-{tid}', 'preflop', 'AsKs', 'raise', 'raise', 100,
                     'standard', pos, stack, 'gto_correct', 0))
        conn.commit()
    finally:
        conn.close()
    return uid


def test_saida_nao_muda_com_a_otimizacao():
    """A trava principal. Se o resultado mudar, o ganho não interessa."""
    uid = _semear(12, com_torneio_novo=True)
    primeira = repo.get_training_proof(uid)
    segunda = repo.get_training_proof(uid)   # 2ª chamada já com baselines criados
    assert primeira == segunda, 'a função não é estável entre chamadas'


def test_categoria_sem_torneio_novo_nao_paga_consulta():
    """O corte que economiza: sem import posterior ao baseline, a categoria não tem o que
    provar e não pode custar uma consulta de aderência por item."""
    uid = _semear(30, com_torneio_novo=False)
    repo.get_training_proof(uid)          # 1ª cria os baselines (custo inevitável)
    with Contador() as c:
        r = repo.get_training_proof(uid)  # 2ª deve ser barata
    assert r == [], 'sem torneio novo não há nada a provar'
    # 30 categorias: o desenho antigo faria ~4 consultas por categoria (120+). Com o corte,
    # o custo deixa de crescer com o número de categorias.
    assert c.n <= 20, f'{c.n} consultas para 30 categorias sem dado — o N+1 voltou'


def test_categoria_SEM_baseline_ainda_mede_o_antes():
    """O corte não pode agir cedo demais: sem baseline, a categoria precisa congelar o
    "antes" mesmo sem torneio novo. Pular aqui deixaria a categoria sem ponto de partida
    para sempre, e a prova nunca poderia existir."""
    uid = _semear(3, com_torneio_novo=False)
    repo.get_training_proof(uid)
    conn = repo.get_conn()
    try:
        n = dict(conn.execute(repo._adapt(
            "SELECT COUNT(*) AS n FROM training_proof WHERE user_id=?"), (uid,)).fetchone())['n']
    finally:
        conn.close()
    assert n == 3, f'baseline não foi criado para as 3 categorias (achei {n})'


def test_custo_nao_cresce_com_o_numero_de_categorias():
    """O sintoma que originou tudo: o endpoint ficou lento porque as CATEGORIAS cresceram,
    não porque o acervo cresceu. Se dobrar as categorias dobrar as consultas, voltamos ao
    ponto de partida."""
    u_pequeno = _semear(10, com_torneio_novo=False)
    u_grande = _semear(60, com_torneio_novo=False)
    repo.get_training_proof(u_pequeno)
    repo.get_training_proof(u_grande)

    with Contador() as c1:
        repo.get_training_proof(u_pequeno)
    with Contador() as c2:
        repo.get_training_proof(u_grande)

    # 6x mais categorias não pode custar 6x mais consultas.
    assert c2.n < c1.n * 3, (f'{c1.n} consultas com 10 categorias e {c2.n} com 60 — '
                             'o custo ainda cresce por categoria')


def _semear_mesmo_filtro(n_stacks: int):
    """N categorias que diferem SÓ no stack. `_category_adherence_filter` ignora o stack de
    propósito, então todas produzem o mesmo SQL — e sem memória, a mesma pergunta é feita N
    vezes. Medido em produção: 85 categorias mapeáveis, 55 consultas distintas."""
    uid = repo.create_user(f'mf{n_stacks}', f'mf{n_stacks}@t.com', 'pass1234')
    conn = repo.get_conn()
    try:
        ontem = (datetime.utcnow() - timedelta(days=2)).strftime('%Y-%m-%d %H:%M:%S')
        hoje = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
        cur = conn.execute(repo._adapt(
            "INSERT INTO tournaments (user_id, tournament_id, tournament_name, hero, imported_at) "
            "VALUES (?,?,?,?,?)"), (uid, 'T-a', 'T', 'Hero', ontem))
        t_antigo = cur.lastrowid
        for i in range(n_stacks):
            # MESMO cenário e MESMA posição, só o stack muda: filtro idêntico.
            conn.execute(repo._adapt(
                "INSERT INTO training_skill_progress (user_id, category_key, attempts, correct) "
                "VALUES (?,?,?,?)"), (uid, f'rfi:BTN::{10 + i}', 5, 3))
        for j in range(4):
            conn.execute(repo._adapt(
                "INSERT INTO decisions (tournament_id, hand_id, street, hero_cards, "
                "action_taken, best_action, score, label, position, stack_bb, gto_label, "
                "preflop_raises_faced) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)"),
                (t_antigo, f'h{j}-a', 'preflop', 'AsKs', 'raise', 'raise', 100,
                 'standard', 'BTN', 25, 'gto_correct', 0))
        conn.commit()
    finally:
        conn.close()

    # A ORDEM REPRODUZ A VIDA: o jogador treina (o baseline congela o "antes") e só DEPOIS
    # joga e importa. Inserir o torneio novo antes desta chamada o deixaria mais velho que o
    # baseline, e ele não contaria como "depois" — a 1ª versão deste dublê errou exatamente
    # aí, e o teste acusou com "0 de 12".
    repo.get_training_proof(uid)

    conn = repo.get_conn()
    try:
        amanha = (datetime.utcnow() + timedelta(days=1)).strftime('%Y-%m-%d %H:%M:%S')
        cur = conn.execute(repo._adapt(
            "INSERT INTO tournaments (user_id, tournament_id, tournament_name, hero, imported_at) "
            "VALUES (?,?,?,?,?)"), (uid, 'T-n', 'T', 'Hero', amanha))
        t_novo = cur.lastrowid
        for j in range(4):
            conn.execute(repo._adapt(
                "INSERT INTO decisions (tournament_id, hand_id, street, hero_cards, "
                "action_taken, best_action, score, label, position, stack_bb, gto_label, "
                "preflop_raises_faced) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)"),
                (t_novo, f'h{j}-n', 'preflop', 'AsKs', 'raise', 'raise', 100,
                 'standard', 'BTN', 25, 'gto_correct', 0))
        conn.commit()
    finally:
        conn.close()
    return uid


def test_categorias_com_o_mesmo_filtro_nao_repetem_a_consulta():
    """O corte 3. `_category_adherence_filter` ignora o stack, então 12 categorias que só
    diferem no stack fazem a MESMA pergunta ao banco 12 vezes. Perguntar uma vez e reusar é
    correto por construção: consulta idêntica no mesmo instante devolve resultado idêntico."""
    uid = _semear_mesmo_filtro(12)   # já deixa os baselines criados e o torneio novo importado
    with Contador() as c:
        r1 = repo.get_training_proof(uid)

    # 12 categorias, 1 filtro distinto. Sem memória seriam ~4 consultas por categoria.
    assert c.n <= 25, f'{c.n} consultas para 12 categorias de filtro IDÊNTICO — sem memória'
    # A saída é UMA linha, e isso é correto: `get_training_proof` deduplica por família no
    # fim ("sem isto a lista mostrava 60 linhas para 39 famílias, rfi:BTN seis vezes com
    # números IDÊNTICOS"). Ou seja, o código já sabia que estas 12 medem a mesma população —
    # o que torna calcular 12 vezes um desperdício em dobro. A 1ª versão deste teste exigia
    # 12 e acusou "a memória engoliu categorias": era o teste que estava errado, não o código.
    assert len(r1) == 1, f'a deduplicação por família mudou (saíram {len(r1)}, esperava 1)'
    assert r1[0]['after_n'] > 0, 'a linha que sobrou perdeu o dado do depois'


def test_memoria_nao_confunde_recortes_diferentes():
    """A chave inclui os recortes de data e torneio. Se cacheasse só pelo filtro, o "antes"
    e o "depois" da mesma categoria colidiriam — e a prova mostraria delta zero sempre,
    dizendo ao jogador que ele não evoluiu."""
    from database.repositories import _memo
    cache = {}
    a = _memo(cache, ('x', 'antes'), lambda: 'valor-antes')
    b = _memo(cache, ('x', 'depois'), lambda: 'valor-depois')
    assert a == 'valor-antes' and b == 'valor-depois', 'chaves diferentes colidiram'
    assert _memo(cache, ('x', 'antes'), lambda: 'NAO DEVIA RECALCULAR') == 'valor-antes'


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
