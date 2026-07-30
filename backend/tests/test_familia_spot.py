# -*- coding: utf-8 -*-
"""
Familia de spot — a chave de agregacao da validacao no jogo real (Protocolo de Progressao, Fase 0).

── O que este arquivo trava, e por que cada guarda existe ─────────────────────────────────────────

1. Que a familia use o bucket GROSSO e o cenario LARGO. As duas escolhas sao MEDIDAS, nao gosto:
   em producao (2026-07-30, 9216 decisoes), o bucket fino cortava as familias validaveis de 118 para
   90; e o cenario por posicao do vilao derrubava as familias validaveis do user 28 de 11 para 1.
   Um refactor que "simplifique" para o esquema fino desfaz uma decisao tomada com numero.

2. Que a familia falhe FECHADA com componente faltando. Familia com componente vazio agrupa
   decisoes que nao pertencem juntas, e a media de EV dela seria uma media de coisas diferentes —
   numero confiante e falso, que e o que a regra 1 do CLAUDE.md proibe.

3. Que a winsorizacao respeite os DOIS tetos. O absoluto sozinho nao basta: uma perda de 20bb num
   stack de 11,7bb e impossivel e passaria pelo teto de 25bb. Foi assim que 439 decisoes receberam
   EV impossivel no meu backfill (a pior: 41604bb num stack de 11,7bb).

4. Que familia sem amostra fique FORA em vez de virar zero. Celula sem dado virando 0 e erro
   documentado do relatorio de evolucao.

5. Que o bucket de AGREGACAO nao seja confundido com o de LOOKUP. Sao perguntas diferentes: colapsar
   o lookup nas faixas grossas faria um stack de 19bb procurar a solucao de 10bb.
"""
import os, sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from leaklab.familia_spot import (bucket_de_agregacao, cenario_largo, familia_de,
                                  winsorizar_ev, familias_validaveis,
                                  MIN_DECISOES_VALIDACAO, TETO_EV_WINSOR_BB)


# ── A eleicao do bucket ────────────────────────────────────────────────────────────────────────

def test_bucket_de_agregacao_e_o_GROSSO_de_5_faixas():
    """Se isto virar 9 faixas, alguem desfez uma decisao tomada com medicao."""
    labels = {bucket_de_agregacao(s) for s in (1, 5, 12, 19, 25, 34, 40, 59, 70, 150)}
    assert labels == {'0-10bb', '10-20bb', '20-35bb', '35-60bb', '60-100bb'}, sorted(labels)


def test_bucket_delega_e_nao_recopia_as_faixas():
    """A particao mora em `gto_utils.STACK_BUCKETS`. Copia divergente e o bug reincidente deste
    projeto — ja aconteceu com corte de board, ranges e leitura de assento."""
    from leaklab.gto_utils import STACK_BUCKETS
    for lo, hi, label in STACK_BUCKETS:
        meio = lo + 0.5 if hi == float('inf') else (lo + hi) / 2
        assert bucket_de_agregacao(meio) == label, (meio, label)


def test_bucket_de_agregacao_NAO_e_o_de_lookup():
    """Perguntas diferentes: o de lookup snapa para uma profundidade SOLVADA (10/14/17/20/...).
    Um stack de 19bb agrega em '10-20bb' e faz lookup em '20bb' — e os dois estao certos."""
    from leaklab.preflop_gto_ranges import _stack_bucket
    assert bucket_de_agregacao(19) == '10-20bb'
    assert _stack_bucket(19) == '20bb'
    assert bucket_de_agregacao(19) != _stack_bucket(19)


def test_stack_acima_do_teto_nao_perde_bucket():
    """Stack deep cai no ultimo bucket em vez de virar None (o `inf` da faixa final)."""
    assert bucket_de_agregacao(400) == '60-100bb'


# ── A eleicao do cenario ───────────────────────────────────────────────────────────────────────

def test_cenario_preflop_distingue_rfi_de_vs_rfi_de_vs_3bet():
    assert cenario_largo('preflop', None) == 'rfi'
    assert cenario_largo('preflop', 'BTN') == 'vs_rfi'
    assert cenario_largo('preflop', 'BTN', is_3bet=True) == 'vs_3bet'


def test_cenario_NAO_carrega_a_posicao_do_vilao():
    """Medido: incluir a posicao do vilao derruba as familias validaveis do user 28 de 11 para 1.
    Ela vive no spot canonico, onde a amostra do drill aguenta."""
    assert cenario_largo('preflop', 'BTN') == cenario_largo('preflop', 'CO') == 'vs_rfi'


def test_postflop_o_cenario_e_o_street():
    for st in ('flop', 'turn', 'river'):
        assert cenario_largo(st, 'BTN') == st
        assert cenario_largo(st, None) == st


# ── A chave, e o falhar fechado ────────────────────────────────────────────────────────────────

def test_familia_e_estavel_e_legivel():
    assert familia_de('preflop', 'btn', 19) == 'preflop|rfi|BTN|10-20bb'
    assert familia_de('flop', 'BB', 45, vs_position='CO') == 'flop|flop|BB|35-60bb'


def test_familia_ignora_caixa_e_espaco():
    assert familia_de('  PREFLOP ', ' btn ', 19) == familia_de('preflop', 'BTN', 19)


def test_familia_falha_FECHADA_com_componente_faltando():
    """Familia com componente vazio agruparia decisoes que nao pertencem juntas."""
    assert familia_de(None, 'BTN', 19) is None
    assert familia_de('preflop', None, 19) is None
    assert familia_de('preflop', 'BTN', None) is None
    assert familia_de('preflop', '', 19) is None


def test_decisoes_de_stacks_diferentes_nao_caem_na_mesma_familia():
    """O bucket tem que separar: 8bb e 50bb sao situacoes distintas."""
    assert familia_de('preflop', 'BTN', 8) != familia_de('preflop', 'BTN', 50)


# ── Winsorizacao ───────────────────────────────────────────────────────────────────────────────

def test_winsoriza_pelo_teto_absoluto():
    assert winsorizar_ev(41604.0) == TETO_EV_WINSOR_BB


def test_winsoriza_pelo_STACK_quando_ele_e_menor():
    """O caso real: perda de 41604bb num stack de 11,7bb. O teto absoluto de 25bb sozinho deixaria
    passar 20bb, que continua impossivel naquele stack."""
    assert winsorizar_ev(41604.0, stack_bb=11.7) == 11.7
    assert winsorizar_ev(20.0, stack_bb=11.7) == 11.7


def test_winsorizacao_nao_inventa_perda_onde_nao_havia():
    assert winsorizar_ev(0.0) == 0.0
    assert winsorizar_ev(None) is None
    assert winsorizar_ev(0.4, stack_bb=60) == 0.4   # valor plausivel passa intacto


def test_winsorizacao_normaliza_sinal_invertido():
    """O EV do solver pode chegar com SINAL INVERTIDO (a escala vem do pote solvado, e o
    `spot_hash` nao inclui o pote). Magnitude e o que a familia agrega."""
    assert winsorizar_ev(-3.2) == 3.2


def test_stack_invalido_nao_derruba_a_winsorizacao():
    assert winsorizar_ev(100.0, stack_bb='lixo') == TETO_EV_WINSOR_BB


# ── Amostra minima ─────────────────────────────────────────────────────────────────────────────

def test_familia_sem_amostra_fica_FORA_e_nao_vira_zero():
    cont = {'a': 25, 'b': 19, 'c': 3, 'd': 40}
    v = familias_validaveis(cont)
    assert v == ['d', 'a'], v
    assert 'b' not in v and 'c' not in v


def test_fronteira_exata_da_amostra_minima():
    """Um off-by-one aqui autorizaria afirmacao com amostra menor que a decidida."""
    assert familias_validaveis({'x': MIN_DECISOES_VALIDACAO}) == ['x']
    assert familias_validaveis({'x': MIN_DECISOES_VALIDACAO - 1}) == []


def test_entrada_vazia_nao_estoura():
    assert familias_validaveis({}) == [] and familias_validaveis(None) == []


# ── As chaves materializadas, e as duas armadilhas conhecidas ──────────────────────────────────

def test_hash_de_preflop_IGNORA_o_board_guardado():
    """O teste que prova o corte por street, e ele reproduz o bug de 3 meses.

    O banco guarda o board COMPLETO da mao em TODA decisao, inclusive nas de preflop. Se o corte
    nao for aplicado, a decisao de preflop e chaveada com 5 cartas na mesa e nunca casa com o no
    que o solver gravou. Foi assim que 74,6% das decisoes postflop ficaram sem cobertura: gravava
    com 5 cartas e procurava com 3.
    """
    from leaklab.familia_spot import chaves_de_decisao
    _, com_board = chaves_de_decisao(street='preflop', position='BTN', stack_bb=25,
                                     board=['Qd', 'Th', '7h', '7s', '3h'], hero_cards='AhKh')
    _, sem_board = chaves_de_decisao(street='preflop', position='BTN', stack_bb=25,
                                     board=[], hero_cards='AhKh')
    assert com_board is not None
    assert com_board == sem_board, (com_board, sem_board)


def test_hash_de_flop_usa_TRES_cartas_e_nao_cinco():
    from leaklab.familia_spot import chaves_de_decisao
    _, cinco = chaves_de_decisao(street='flop', position='BTN', stack_bb=25,
                                 board=['Qd', 'Th', '7h', '7s', '3h'], hero_cards='AhKh')
    _, tres = chaves_de_decisao(street='flop', position='BTN', stack_bb=25,
                                board=['Qd', 'Th', '7h'], hero_cards='AhKh')
    assert cinco == tres, (cinco, tres)
    # e turn (4 cartas) tem que ser um spot DIFERENTE de flop
    _, turn = chaves_de_decisao(street='turn', position='BTN', stack_bb=25,
                                board=['Qd', 'Th', '7h', '7s', '3h'], hero_cards='AhKh')
    assert turn != tres


def test_hero_cards_COLADO_nao_vira_lixo():
    """`hero_cards` aparece na base colado ('5h5d'). Um `split()` ingenuo devolve
    ['5','h','5','d'] e todo hash sai errado — foi o que fez um diagnostico reportar
    'zero perdidas', o resultado tranquilizador e falso."""
    from leaklab.familia_spot import chaves_de_decisao
    _, colado = chaves_de_decisao(street='flop', position='BTN', stack_bb=25,
                                  board=['Qd', 'Th', '7h'], hero_cards='5h5d')
    _, lista = chaves_de_decisao(street='flop', position='BTN', stack_bb=25,
                                 board=['Qd', 'Th', '7h'], hero_cards=['5h', '5d'])
    assert colado is not None and colado == lista, (colado, lista)


def test_sem_insumo_o_hash_e_None_e_nao_hash_de_vazio():
    """Hash de nada casaria com hash de nada, agrupando decisoes sem relacao nenhuma."""
    from leaklab.familia_spot import chaves_de_decisao
    fam, h = chaves_de_decisao(street='flop', position='BTN', stack_bb=25, hero_cards=None)
    assert h is None
    assert fam == 'flop|flop|BTN|20-35bb'   # a familia nao depende das cartas e continua saindo


def test_familia_sai_mesmo_quando_o_hash_nao_sai():
    """Sao chaves independentes: a familia agrega, o hash localiza o no GTO. Uma decisao sem
    cartas registradas ainda conta na serie temporal da familia."""
    from leaklab.familia_spot import chaves_de_decisao
    fam, h = chaves_de_decisao(street='preflop', position='SB', stack_bb=8, hero_cards='')
    assert fam == 'preflop|rfi|SB|0-10bb' and h is None


def test_save_decisions_GRAVA_as_duas_colunas():
    """Regra 1 do CLAUDE.md: o diagnostico precisa PROVAR que detecta. Grava de verdade e exige
    que as colunas saiam preenchidas — sem isto, uma coluna que nunca popula passaria despercebida
    exatamente como o `10 insertions` que so alterava a docstring."""
    from database.schema import init_db, get_conn
    from database.repositories import save_decisions, save_tournament, create_user
    init_db()
    # Idempotente de proposito: a suite roda repetidas vezes contra o MESMO banco de dev, e a
    # primeira versao disto estourava `UNIQUE users.email` na segunda execucao. Pior que o erro:
    # aquele estouro fazia o teste "falhar" durante uma sabotagem e eu quase li isso como o guarda
    # tendo acusado.
    from database.repositories import get_user_by_email
    u = get_user_by_email('fam@teste.local')
    uid = u['id'] if u else create_user('fam_teste', 'fam@teste.local', 'senha-de-teste-123')
    tid = save_tournament(uid, 'T-FAM-1', 'hero', {})
    save_decisions(tid, [{
        'handId': 'h1', 'street': 'flop', 'position': 'BTN', 'stack_bb': 25.0,
        'hero_cards': 'AhKh', 'board': ['Qd', 'Th', '7h', '7s', '3h'],
        'actionTaken': 'bet', 'evaluation': {'label': 'correct', 'mistakeScore': 0},
        'spot': {'facingToBb': 0.0},
    }])
    conn = get_conn()
    try:
        r = conn.execute("SELECT spot_family_key, spot_hash FROM decisions "
                         "WHERE tournament_id = ?", (tid,)).fetchone()
    finally:
        conn.close()
    assert r is not None, 'a decisao nem gravou'
    assert r['spot_family_key'] == 'flop|flop|BTN|20-35bb', r['spot_family_key']
    assert r['spot_hash'], 'spot_hash gravado vazio'


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
