"""
O próximo passo: a precedência é a da spec, e cada nível foi forjado e falsificado.

── Por que este arquivo existe ───────────────────────────────────────────────────────────────

Spec cobranca-proximo-passo.md §2.2: a decisão do que o aluno faz agora é UMA função pura,
consumida por todas as superfícies. Se a ordem regredir (uma missão passando na frente de um
leak reaberto, uma revisão vencida ignorada), o sistema volta a ser o que era: cinco portas de
entrada e nenhuma mandando.

Cada teste forja UM nível e prova que ele vence os de baixo — e os negativos provam que os
gatilhos não disparam sem o fato (reaberto que já treinou não acorda ninguém; fila vazia é
resposta válida, nunca urgência inventada).
"""
import os, sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from leaklab.proximo_passo import decidir_proximo_passo

AGORA = '2026-07-29T12:00:00'

_REABERTO = {'category_key': 'rfi:UTG::50', 'titulo': 'Abertura (RFI) de UTG · 50bb',
             'ev_loss_bb': 9.0, 'n': 14, 'reopened_at': '2026-07-28T00:00:00',
             'treinou_depois': False}
_REVISOES = {'drills': 2, 'ranges': 3, 'mais_antiga': '2026-07-27T00:00:00'}
_MISSAO   = {'key': 'vs_rfi:BB:LJ:30', 'titulo': 'BB vs open do LJ · 30bb',
             'ev_loss_bb': 14.4, 'hands': 21}
_CARTA    = {'position': 'LJ', 'scenario': 'vs_rfi', 'ev_loss_bb': 14.4,
             'hands': 21, 'stack_bb': 30, 'de_quem': 'vilao'}


def test_reaberto_vence_tudo():
    fila = decidir_proximo_passo(AGORA, reabertos=[_REABERTO], revisoes=_REVISOES,
                                 missao=_MISSAO, carta_nova=_CARTA, desafio_pendente=True)
    assert fila[0]['tipo'] == 'leak_reaberto', fila[0]
    tipos = [p['tipo'] for p in fila]
    assert tipos.index('leak_reaberto') < tipos.index('revisao_vencida') < tipos.index('missao')


def test_reaberto_que_JA_treinou_nao_acorda_ninguem():
    """Quem voltou ao treino depois da reabertura não precisa ser acordado para isso. Sem este
    corte, o passo cobraria eternamente algo que o aluno já está fazendo."""
    r = dict(_REABERTO, treinou_depois=True)
    fila = decidir_proximo_passo(AGORA, reabertos=[r], revisoes=None, missao=_MISSAO)
    assert fila[0]['tipo'] == 'missao', fila[0]


def test_revisao_vencida_vence_missao():
    fila = decidir_proximo_passo(AGORA, revisoes=_REVISOES, missao=_MISSAO)
    assert [p['tipo'] for p in fila][:2] == ['revisao_vencida', 'missao']


def test_revisao_no_futuro_nao_dispara():
    """O gatilho é o vencimento, não a existência de agenda. Revisão de amanhã não é cobrança
    de hoje — disparar aqui seria notificação sem fato novo (anti-requisito 3 da spec)."""
    rev = {'drills': 0, 'ranges': 2, 'mais_antiga': '2026-08-15T00:00:00'}
    fila = decidir_proximo_passo(AGORA, revisoes=rev, missao=_MISSAO)
    assert fila[0]['tipo'] == 'missao'
    assert all(p['tipo'] != 'revisao_vencida' for p in fila)


def test_missao_sozinha_e_o_passo():
    fila = decidir_proximo_passo(AGORA, missao=_MISSAO)
    p = fila[0]
    assert p['tipo'] == 'missao'
    assert '14.4' in p['porque'] and '21' in p['porque'], \
        'o porquê tem que carregar o custo em bb e as mãos reais'
    assert p['ev_loss_bb'] == 14.4 and p['n_maos'] == 21


def test_carta_nova_apos_missao_e_desafio_como_ultimo_recurso():
    com_carta = decidir_proximo_passo(AGORA, missao=_MISSAO, carta_nova=_CARTA,
                                      desafio_pendente=True)
    tipos = [p['tipo'] for p in com_carta]
    assert 'carta_nova' in tipos and 'desafio_diario' not in tipos, \
        'um passo por vez: a carta do alvo engole o desafio'
    so_desafio = decidir_proximo_passo(AGORA, desafio_pendente=True)
    assert so_desafio[0]['tipo'] == 'desafio_diario'


def test_fila_vazia_e_resposta_valida():
    """Aluno em dia. A UI mostra descanso — urgência inventada é o que gasta a credibilidade
    de toda cobrança real (anti-requisito 3)."""
    assert decidir_proximo_passo(AGORA) == []


def test_empate_de_reabertos_decide_por_EV():
    a = dict(_REABERTO, category_key='a', ev_loss_bb=3.0)
    b = dict(_REABERTO, category_key='b', ev_loss_bb=19.0)
    fila = decidir_proximo_passo(AGORA, reabertos=[a, b])
    assert fila[0]['n_maos'] == b['n'] and fila[0]['ev_loss_bb'] == 19.0


def test_cta_aponta_para_a_superficie_do_tipo():
    """Revisão majoritária de RANGE vai para a grade; majoritária de DRILL vai para o Ghost
    Table. Mandar o aluno para a superfície errada é cobrar e não deixar pagar."""
    so_ranges = decidir_proximo_passo(AGORA, revisoes={'drills': 0, 'ranges': 3,
                                                       'mais_antiga': '2026-07-01T00:00:00'})
    assert 'fund:range_grid' in so_ranges[0]['cta_url']
    so_drills = decidir_proximo_passo(AGORA, revisoes={'drills': 4, 'ranges': 1,
                                                       'mais_antiga': '2026-07-01T00:00:00'})
    assert '/training' in so_drills[0]['cta_url']


def test_todo_passo_tem_o_shape_do_contrato():
    """Spec §2.1: toda superfície renderiza este shape, nada além dele. Campo faltando quebra
    o dashboard E o e-mail ao mesmo tempo — é o custo de fonte única, e este teste o paga."""
    fila = decidir_proximo_passo(AGORA, reabertos=[_REABERTO], revisoes=_REVISOES,
                                 missao=_MISSAO, carta_nova=_CARTA, desafio_pendente=True)
    chaves = {'tipo', 'titulo', 'porque', 'custo_min', 'cta_url', 'ev_loss_bb', 'n_maos'}
    for p in fila:
        assert set(p.keys()) == chaves, p
        assert p['titulo'] and p['porque'] and p['custo_min'] >= 1
        assert '{origem}' in p['cta_url'], 'o CTA nasce com placeholder; a origem entra na saída'


def test_reabertura_recem_criada_e_visivel_no_banco_real():
    """O bug que o forjamento pegou: o loader lia a reabertura via get_training_proof, que só
    lista categoria com torneio novo pós-baseline — e a reabertura MOVE o baseline, então o
    leak recém-reaberto era invisível até o upload seguinte. O endpoint devolvia 'missao' com
    a reabertura na mesa. Este teste forja a linha crua e exige que o passo a veja JÁ."""
    os.environ.pop('DATABASE_URL', None)
    from database.schema import init_db, get_conn
    from database.repositories import _adapt
    from leaklab.proximo_passo import montar_proximo_passo
    init_db()
    u, key = 990010, 'rfi:UTG::50'
    c = get_conn()
    # o usuário do teste precisa existir: training_proof tem FK para users
    try:
        c.execute(_adapt('INSERT INTO users (id, email, username, password_hash) VALUES (?,?,?,?)'),
                  (u, 'pp_teste@t.local', 'pp_teste', 'x'))
    except Exception:
        pass
    c.execute(_adapt('DELETE FROM training_proof WHERE user_id = ?'), (u,))
    c.execute(_adapt('DELETE FROM progression_attempts WHERE user_id = ?'), (u,))
    c.execute(_adapt(
        'INSERT INTO training_proof (user_id, category_key, baseline_pct, baseline_n, '
        'baseline_at, reopened_at, reopen_count) VALUES (?,?,80.0,30,?,?,1)'),
        (u, key, '2026-07-28T00:00:00', '2026-07-28T00:00:00'))
    c.commit(); c.close()
    out = montar_proximo_passo(u, origem='teste')
    assert out['passo'] and out['passo']['tipo'] == 'leak_reaberto', out['passo']
    assert 'UTG' in out['passo']['titulo'], 'título legível, nunca a chave crua'


def test_montar_resolve_a_origem_e_fatia_a_fila():
    """A camada de I/O: passo = fila[0], contexto = fila[1:3], origem substituída no CTA."""
    import leaklab.proximo_passo as pp
    orig_decidir = pp.decidir_proximo_passo
    try:
        # injeta uma fila conhecida para testar SÓ a montagem (o resto do banco não importa)
        pp.decidir_proximo_passo = lambda agora, **kw: [
            pp._passo('missao', 'M1', 'p', 4, '/leak-trainer?origem={origem}'),
            pp._passo('carta_nova', 'M2', 'p', 3, '/x?origem={origem}'),
            pp._passo('desafio_diario', 'M3', 'p', 2, '/y?origem={origem}'),
            pp._passo('desafio_diario', 'M4', 'p', 2, '/z?origem={origem}'),
        ]
        out = pp.montar_proximo_passo(999999, origem='dashboard')
    finally:
        pp.decidir_proximo_passo = orig_decidir
    assert out['passo']['titulo'] == 'M1'
    assert out['passo']['cta_url'].endswith('origem=dashboard')
    assert [f['titulo'] for f in out['fila']] == ['M2', 'M3'], 'fila é o contexto: 2, não o backlog'
    assert out['meta_semanal'] is None   # Fase 3


if __name__ == '__main__':
    falhas = 0
    testes = (test_reaberto_vence_tudo,
              test_reaberto_que_JA_treinou_nao_acorda_ninguem,
              test_revisao_vencida_vence_missao,
              test_revisao_no_futuro_nao_dispara,
              test_missao_sozinha_e_o_passo,
              test_carta_nova_apos_missao_e_desafio_como_ultimo_recurso,
              test_fila_vazia_e_resposta_valida,
              test_empate_de_reabertos_decide_por_EV,
              test_cta_aponta_para_a_superficie_do_tipo,
              test_todo_passo_tem_o_shape_do_contrato,
              test_reabertura_recem_criada_e_visivel_no_banco_real,
              test_montar_resolve_a_origem_e_fatia_a_fila)
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
