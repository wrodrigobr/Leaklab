"""Bateria do veredito do Decision Card (leaklab/card_verdict).

Trava a camada de reconciliação do /replay — antes inline em api/app.py, SEM teste —
onde o bug A2s/mão 5 morava (card julgava pela ação modal do RANGE em vez da MÃO).
Casos pontuais + invariantes sobre matriz determinística.
"""
import sys, os, traceback
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from leaklab.card_verdict import (
    reconcile_verdict, norm_action, label_for_freq,
    spot_mismatch, verdict_from_stored, verdict_from_preflop,
    verdict_from_multiway_advice, verdict_from_multiway_engine, verdict_from_multiway_safe,
    VerdictChain, LAYERS,
)


# ── Camadas 1/3/4, extraídas do /replay (antes inline numa função de 1000 linhas) ─────────────
#
# Cada camada sobrescreve a anterior. Testá-las isoladamente é o que permite mexer na ORDEM
# depois sabendo o que cada uma faz sozinha.

def test_mismatch_check_quando_hero_enfrenta_aposta():
    """O nó respondeu a um spot em que ninguém apostou; o hero está pagando. Nó de outro spot."""
    assert spot_mismatch('check', 'call') is True
    assert spot_mismatch('bet', 'call') is True
    print("OK  test_mismatch_check_quando_hero_enfrenta_aposta")


def test_mismatch_call_quando_nao_ha_aposta():
    assert spot_mismatch('call', 'check') is True
    assert spot_mismatch('call', 'bet') is True
    print("OK  test_mismatch_call_quando_nao_ha_aposta")


def test_mismatch_falso_quando_compativel_ou_vazio():
    assert spot_mismatch('raise', 'call') is False    # ambos enfrentando aposta
    assert spot_mismatch('check', 'bet') is False     # ambos sem aposta
    assert spot_mismatch('', 'call') is False         # sem dado não inventa incompatibilidade
    assert spot_mismatch('call', '') is False
    print("OK  test_mismatch_falso_quando_compativel_ou_vazio")


def test_stored_gto_confirma_derruba_alarme_do_engine():
    """Solver diz que a jogada é válida: o engine pode ter dado alarme falso e perde."""
    v = verdict_from_stored('gto_correct', 'raise', 'fold', 'clear_mistake', 'call', False)
    assert v['is_error'] is False
    assert v['reconciled_best'] == 'call'      # a própria jogada vira a referência
    print("OK  test_stored_gto_confirma_derruba_alarme_do_engine")


def test_stored_gto_aponta_desvio():
    v = verdict_from_stored('gto_critical', 'raise', 'fold', 'standard', 'call', False)
    assert v['is_error'] is True and v['reconciled_best'] == 'raise'
    print("OK  test_stored_gto_aponta_desvio")


def test_stored_sem_gto_o_engine_decide():
    assert verdict_from_stored(None, None, 'fold', 'small_mistake', 'call', False)['is_error'] is True
    assert verdict_from_stored(None, None, 'fold', 'standard', 'call', False)['is_error'] is False
    print("OK  test_stored_sem_gto_o_engine_decide")


def test_stored_sem_decisao_nao_e_erro():
    """Sem decisão do engine (ação sem análise), nada pode ser chamado de erro."""
    v = verdict_from_stored(None, None, None, None, 'call', False)
    assert v['is_error'] is False
    print("OK  test_stored_sem_decisao_nao_e_erro")


def test_stored_mismatch_ignora_o_gto_inteiro():
    """Com spot incompatível a recomendação do GTO não é corrigida — é descartada."""
    v = verdict_from_stored('gto_critical', 'check', 'call', 'standard', 'call', True)
    assert v['reconciled_best'] == 'call'      # engine_best, não o 'check' do nó errado
    assert v['is_error'] is False
    print("OK  test_stored_mismatch_ignora_o_gto_inteiro")


def test_preflop_qualidade_desconhecida_nao_mexe():
    """'unknown' devolve None de propósito: a camada anterior continua valendo."""
    assert verdict_from_preflop('unknown', 'raise', 'call') is None
    assert verdict_from_preflop(None, 'raise', 'call') is None
    print("OK  test_preflop_qualidade_desconhecida_nao_mexe")


def test_preflop_mapeia_as_seis_qualidades():
    esperado = {'correct': (False, 'gto_correct'), 'acceptable': (False, 'gto_mixed'),
                'gto_minor_deviation': (True, 'gto_minor_deviation'),
                'minor_mistake': (True, 'gto_minor_deviation'),
                'leak': (True, 'gto_critical'), 'major_leak': (True, 'gto_critical')}
    for q, (err, label) in esperado.items():
        v = verdict_from_preflop(q, 'raise', 'call')
        assert v['is_error'] is err and v['gto_label'] == label, (q, v)
        # acerto → a referência é a própria jogada; erro → a recomendada
        assert v['reconciled_best'] == ('raise' if err else 'call'), (q, v)
    print("OK  test_preflop_mapeia_as_seis_qualidades")


def test_multiway_advice_mantem_cru_e_normalizado_separados():
    """`reconciled_best` sai normalizado e `gto_action` cru. A diferença aparece na tela."""
    v = verdict_from_multiway_advice('folds', 'fold', True)
    assert v['reconciled_best'] == 'fold'
    assert v['gto_action'] == 'folds' and v['live_top_act'] == 'folds'
    assert v['is_error'] is True
    print("OK  test_multiway_advice_mantem_cru_e_normalizado_separados")


def test_multiway_engine_usa_DUAS_severidades_nao_tres():
    """REGRESSÃO de leitura: a camada 1 chama 'marginal' de erro, o ramo multiway NÃO.
    A diferença é deliberada — multiway já é aproximação, marginal ali não vira erro."""
    assert verdict_from_multiway_engine('marginal', 'call', 'x', 'y')['is_error'] is False
    assert verdict_from_multiway_engine('small_mistake', 'call', 'x', 'y')['is_error'] is True
    assert verdict_from_multiway_engine('clear_mistake', 'call', 'x', 'y')['is_error'] is True
    print("OK  test_multiway_engine_usa_DUAS_severidades_nao_tres")


def test_multiway_engine_preserva_valor_anterior_sem_best():
    """Sem best_action do engine, o que a camada anterior decidiu permanece."""
    v = verdict_from_multiway_engine('standard', None, 'anterior', 'gto_anterior')
    assert v['reconciled_best'] == 'anterior' and v['gto_action'] == 'gto_anterior'
    print("OK  test_multiway_engine_preserva_valor_anterior_sem_best")


def test_multiway_safe_rotula_severidade():
    assert verdict_from_multiway_safe('folds', 'fold', True)['safe_label'] == 'small_mistake'
    assert verdict_from_multiway_safe('folds', 'fold', False)['safe_label'] == 'standard'
    print("OK  test_multiway_safe_rotula_severidade")


# ── VerdictChain: a precedência virou dado ───────────────────────────────────────────────────

def test_chain_camada_posterior_vence():
    c = VerdictChain()
    c.apply('stored', {'is_error': False, 'reconciled_best': 'call'})
    c.apply('live',   {'is_error': True,  'reconciled_best': 'raise'})
    assert c['is_error'] is True and c['reconciled_best'] == 'raise'
    assert c.layer == 'live'
    print("OK  test_chain_camada_posterior_vence")


def test_chain_camada_que_nao_opina_nao_vira_dona():
    """None = a camada não teve o que dizer. Ela não pode sobrescrever NEM assinar o veredito —
    senão `verdict_layer` mentiria sobre quem decidiu."""
    c = VerdictChain()
    c.apply('stored', {'is_error': True, 'reconciled_best': 'fold'})
    c.apply('preflop', None)
    assert c['is_error'] is True and c.layer == 'stored'
    assert c.trail == ['stored']
    print("OK  test_chain_camada_que_nao_opina_nao_vira_dona")


def test_chain_preserva_campo_que_a_camada_nao_decide():
    """A camada 1 não mexe em gto_label; ele tem que atravessar intacto."""
    c = VerdictChain(gto_label='gto_correct', gto_action='raise', live_top_act=None)
    c.apply('stored', {'is_error': False, 'reconciled_best': 'call'})
    assert c.unpack() == (False, 'call', 'gto_correct', 'raise', None)
    print("OK  test_chain_preserva_campo_que_a_camada_nao_decide")


def test_chain_ignora_campo_de_diagnostico():
    """As funções devolvem também dados de diagnóstico (`source`, `played_freq`, `safe_label`).
    Nada disso pode virar campo do veredito por acidente."""
    c = VerdictChain()
    c.apply('live', {'is_error': False, 'reconciled_best': 'call',
                     'source': 'hand', 'played_freq': 0.9, 'top_freq': 0.9})
    assert 'source' not in c.data and 'played_freq' not in c.data, c.data
    print("OK  test_chain_ignora_campo_de_diagnostico")


def test_chain_fora_de_ordem_levanta():
    """O ponto da ordem declarada: aplicar ao contrário é erro de programação e tem que doer.
    Só pode acontecer por edição de código — nunca por dado —, então falhar alto é seguro."""
    c = VerdictChain()
    c.apply('preflop', {'is_error': True})
    for tarde in ('stored', 'live', 'preflop'):
        try:
            c.apply(tarde, {'is_error': False})
        except ValueError:
            continue
        raise AssertionError(f"aplicar {tarde!r} depois de 'preflop' deveria levantar")
    print("OK  test_chain_fora_de_ordem_levanta")


def test_chain_camada_desconhecida_levanta():
    try:
        VerdictChain().apply('inventada', {'is_error': True})
    except ValueError:
        print("OK  test_chain_camada_desconhecida_levanta")
        return
    raise AssertionError("camada fora de LAYERS deveria levantar")


def test_chain_ordem_declarada_bate_com_as_camadas_reais():
    """Se alguém acrescentar uma camada ao /replay sem declarar aqui, isto quebra."""
    assert LAYERS == ('stored', 'live', 'preflop',
                      'multiway_advice', 'multiway_engine', 'multiway_safe'), LAYERS
    print("OK  test_chain_ordem_declarada_bate_com_as_camadas_reais")


# ── caso-âncora: mão 5 (A2s) — range folda 63%, mas a mão LEVANTA 93% ──────────
def test_mao5_recomenda_da_mao_nao_do_range():
    rng  = [{'action': 'fold', 'frequency': 0.63}, {'action': 'raise', 'frequency': 0.34},
            {'action': 'call', 'frequency': 0.03}]
    hand = [{'action': 'raise', 'frequency': 0.93}, {'action': 'call', 'frequency': 0.06},
            {'action': 'fold', 'frequency': 0.01}]
    v = reconcile_verdict(rng, hand, 'call', 'fold')
    assert v['source'] == 'hand'
    assert v['live_top_act'] == 'raise', v          # recomenda RAISE (não fold do range)
    assert v['gto_action'] == 'raise'
    assert v['gto_label'] == 'gto_critical'         # call = 6% na MÃO (não 3% do range)
    assert v['is_error'] is True
    assert v['reconciled_best'] == 'raise'
    print("OK  test_mao5_recomenda_da_mao_nao_do_range")


def test_sem_mao_cai_no_range():
    rng = [{'action': 'fold', 'frequency': 0.70}, {'action': 'call', 'frequency': 0.30}]
    v = reconcile_verdict(rng, None, 'call')
    assert v['source'] == 'range'
    assert v['live_top_act'] == 'fold'
    assert v['played_freq'] == 0.30
    assert v['is_error'] is False                    # 0.30 está no limite (mista) → não-erro
    assert v['reconciled_best'] == 'call'
    v2 = reconcile_verdict(rng, [], 'call')          # mão vazia também cai no range
    assert v2['source'] == 'range'
    print("OK  test_sem_mao_cai_no_range")


def test_jogou_a_modal_nao_e_erro():
    hand = [{'action': 'check', 'frequency': 0.80}, {'action': 'bet', 'frequency': 0.20}]
    v = reconcile_verdict(None, hand, 'check')
    assert v['is_error'] is False
    assert v['gto_label'] == 'gto_correct'           # 80%
    assert v['reconciled_best'] == 'check'
    assert v['live_top_act'] == 'check'
    print("OK  test_jogou_a_modal_nao_e_erro")


def test_shove_jam_allin_equivalentes():
    hand = [{'action': 'allin', 'frequency': 0.95}, {'action': 'fold', 'frequency': 0.05}]
    for played in ('shove', 'jam', 'allin', 'all-in', 'shoves'):
        v = reconcile_verdict(None, hand, played)
        assert v['played_freq'] == 0.95, (played, v)
        assert v['gto_label'] == 'gto_correct', (played, v)
        assert v['is_error'] is False, (played, v)
    print("OK  test_shove_jam_allin_equivalentes")


def test_sizing_casa_por_prefixo():
    # estratégia com sizing; a ação jogada base ('bet') casa com 'bet_75pct'
    hand = [{'action': 'bet_75pct', 'frequency': 0.65}, {'action': 'check', 'frequency': 0.35}]
    v = reconcile_verdict(None, hand, 'bet')
    assert v['played_freq'] == 0.65
    assert v['live_top_act'] == 'bet_75pct'
    assert v['gto_label'] == 'gto_correct'
    print("OK  test_sizing_casa_por_prefixo")


def test_sem_estrategia_retorna_none():
    assert reconcile_verdict(None, None, 'call') is None
    assert reconcile_verdict([], [], 'call') is None
    print("OK  test_sem_estrategia_retorna_none")


def test_fallback_stored_gto_action():
    # estratégia só com a própria ação (modal = ela); gto_action vem da modal
    hand = [{'action': 'call', 'frequency': 1.0}]
    v = reconcile_verdict(None, hand, 'call', stored_gto_action='raise')
    assert v['gto_action'] == 'call'                 # modal vence o stored
    print("OK  test_fallback_stored_gto_action")


def test_label_for_freq_thresholds():
    assert label_for_freq(0.60) == 'gto_correct'
    assert label_for_freq(0.59) == 'gto_mixed'
    assert label_for_freq(0.30) == 'gto_mixed'
    assert label_for_freq(0.29) == 'gto_minor_deviation'
    assert label_for_freq(0.10) == 'gto_minor_deviation'
    assert label_for_freq(0.09) == 'gto_critical'
    assert label_for_freq(0.0)  == 'gto_critical'
    print("OK  test_label_for_freq_thresholds")


# ── INVARIANTES sobre matriz determinística (sem RNG) ─────────────────────────
def _matrix():
    """Pares (range, hand) determinísticos cobrindo divergência range×mão."""
    acts = ['fold', 'call', 'raise', 'check', 'bet', 'allin']
    out = []
    # range concentrado em fold; mão concentrada em cada ação por vez
    for top in acts:
        rng  = [{'action': 'fold', 'frequency': 0.7}, {'action': top, 'frequency': 0.3}] \
               if top != 'fold' else [{'action': 'fold', 'frequency': 1.0}]
        for f in (0.95, 0.6, 0.34, 0.2, 0.05):
            other = 'fold' if top != 'fold' else 'call'
            hand = [{'action': top, 'frequency': f}, {'action': other, 'frequency': round(1 - f, 3)}]
            for played in acts:
                out.append((rng, hand, played, top))
    return out


def test_invariante_recomendacao_vem_da_mao():
    """Havendo estratégia da MÃO, a recomendação (live_top_act) é SEMPRE a modal da
    mão — nunca a do range quando divergem. E played_freq é o da MÃO."""
    viol = 0
    for rng, hand, played, hand_top in _matrix():
        v = reconcile_verdict(rng, hand, played)
        assert v is not None
        assert v['source'] == 'hand'
        # modal da mão calculada de forma independente
        exp_top = max(hand, key=lambda s: s['frequency'])['action']
        if v['live_top_act'] != exp_top:
            viol += 1
        # played_freq deve bater com a freq da própria ação na MÃO (por prefixo/allin)
        pn = norm_action(played)
        exp_freq = 0.0
        for s in hand:
            an = norm_action(s['action'])
            if an == pn or pn.startswith(an) or an.startswith(pn):
                exp_freq = s['frequency']; break
        assert abs(v['played_freq'] - exp_freq) < 1e-9, (rng, hand, played, v)
    assert viol == 0, f'{viol} casos com recomendação fora da modal da mão'
    print(f"OK  test_invariante_recomendacao_vem_da_mao ({len(_matrix())} casos)")


def test_invariante_label_consistente_com_freq():
    """O gto_label SEMPRE corresponde ao bucket de played_freq — nunca contradiz
    (ex.: jogou ação de 93% e veio 'crítico')."""
    for rng, hand, played, _ in _matrix():
        v = reconcile_verdict(rng, hand, played)
        assert v['gto_label'] == label_for_freq(v['played_freq']), (hand, played, v)
        # coerência is_error × label: erro ⇔ played_freq < 0.30 ⇔ label pior que mixed
        assert v['is_error'] == (v['played_freq'] < 0.30)
        if not v['is_error']:
            assert v['gto_label'] in ('gto_correct', 'gto_mixed')
            assert v['reconciled_best'] == norm_action(played)
    print("OK  test_invariante_label_consistente_com_freq")


def test_invariante_nunca_recomenda_e_critica_a_mesma():
    """Anti-autocontradição: se o card NÃO marca erro (jogou ação válida), a ação
    reconciliada é a própria jogada — nunca recomenda outra coisa contra uma jogada
    aprovada."""
    for rng, hand, played, _ in _matrix():
        v = reconcile_verdict(rng, hand, played)
        if not v['is_error']:
            assert v['reconciled_best'] == norm_action(played), (hand, played, v)
    print("OK  test_invariante_nunca_recomenda_e_critica_a_mesma")


if __name__ == '__main__':
    tests = [v for k, v in sorted(globals().items()) if k.startswith('test_')]
    passed = failed = 0
    for t in tests:
        try:
            t(); passed += 1
        except Exception as e:
            print(f"FAIL {t.__name__}: {e}")
            traceback.print_exc()
            failed += 1
    print(f"\n{'='*50}")
    print(f"Total: {passed+failed} | Passed: {passed} | Failed: {failed}")
