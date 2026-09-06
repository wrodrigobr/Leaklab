# -*- coding: utf-8 -*-
"""O plano de estudos regenera quando o PERFIL muda de banda — e so entao (AY-6, 05/09).

O cache do banco tem chave estavel por aluno e a assinatura de drift ignorava o HUD. Em 05/09
o HUD foi consertado contra o PokerTracker e os 5 planos em producao ficaram com o contexto
antigo, sem nada que os regenerasse.

O sinal certo e a BANDA, nao o valor: "saiu de loose para saudavel" e o perfil mudando; "VPIP
foi de 24,3 para 24,9" e ruido, e regenerar por ruido e churn (o jogador perde o plano que
seguia e paga uma chamada de LLM por nada). O dono descartou a alternativa de comparar periodos
dentro do plano — isso ja existe no relatorio de evolucao, e o plano deve focar nos leaks.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
os.environ.pop('DATABASE_URL', None)

from leaklab.llm_explainer import _study_plan_drift_sig          # noqa: E402
from leaklab.opponent_stats import STAT_REFERENCES               # noqa: E402

_LEAKS = [{'spot': 'preflop/fold', 'n': 12}, {'spot': 'flop/check', 'n': 9}]
_EVO = [{'avg_score': 0.1}] * 10


def _stats(vpip, wtsd=27.0):
    """HUD com amostra acima de todo gate, para a banda classificar de verdade."""
    return {'total_hands': 5000, 'vpip': vpip, 'pfr': 18.0, 'af': 2.5, 'wtsd': wtsd,
            'w_at_sd': 51.0, 'cbet_pct': 65.0, 'three_bet': 7.0, 'fold_to_3bet': 55.0,
            'steal_pct': 35.0}


def test_valor_dentro_da_mesma_banda_NAO_muda_a_assinatura():
    """VPIP 20 e 23 estao ambos na banda saudavel (18-24): o plano nao pode regenerar."""
    lo, hi = STAT_REFERENCES['vpip']['healthy']
    a = _study_plan_drift_sig(_LEAKS, _EVO, _stats(vpip=lo + 1))
    b = _study_plan_drift_sig(_LEAKS, _EVO, _stats(vpip=hi - 1))
    assert a == b, 'ruido dentro da banda regeneraria o plano (churn): %s != %s' % (a, b)


def test_mudanca_de_BANDA_muda_a_assinatura():
    """VPIP 20 (saudavel) -> 33 (loose): o perfil mudou, o plano tem de regenerar."""
    a = _study_plan_drift_sig(_LEAKS, _EVO, _stats(vpip=20.0))
    b = _study_plan_drift_sig(_LEAKS, _EVO, _stats(vpip=33.0))
    assert a != b, 'saiu de saudavel para loose e o plano nao regenerou'


def test_o_caso_que_originou_wtsd_69_para_35():
    """O conserto do HUD levou o WTSD de 69 (station) para 35 (acima, mas outra banda). Os 5
    planos em producao tinham o 69 no contexto: esta mudanca TEM de invalidar o cache."""
    a = _study_plan_drift_sig(_LEAKS, _EVO, _stats(vpip=22.0, wtsd=69.0))
    b = _study_plan_drift_sig(_LEAKS, _EVO, _stats(vpip=22.0, wtsd=27.0))
    assert a != b, 'WTSD 69 -> 27 nao invalidou o plano'


def test_sem_stats_a_assinatura_e_a_de_antes():
    """Retrocompatibilidade: chamador que nao passa `player_stats` recebe a assinatura antiga.
    Sem isto, todo plano cacheado regeneraria uma vez so por causa deste commit."""
    assert _study_plan_drift_sig(_LEAKS, _EVO) == _study_plan_drift_sig(_LEAKS, _EVO, None)
    assert _study_plan_drift_sig(_LEAKS, _EVO) == _study_plan_drift_sig(_LEAKS, _EVO, {})


def test_amostra_baixa_e_banda_e_sair_dela_conta():
    """Com 50 maos tudo e `low_sample`; com 5.000 as bandas aparecem. Ganhar amostra E mudanca
    de perfil informativo — o plano feito em amostra baixa era chute."""
    pouca = dict(_stats(vpip=33.0), total_hands=50)
    a = _study_plan_drift_sig(_LEAKS, _EVO, pouca)
    b = _study_plan_drift_sig(_LEAKS, _EVO, _stats(vpip=33.0))
    assert a != b


def test_os_leaks_continuam_mandando():
    """Contraprova: a banda entrou SOMANDO ao que ja existia. Leak novo no top-3 ainda regenera."""
    outros = [{'spot': 'river/call', 'n': 12}] + _LEAKS[1:]
    a = _study_plan_drift_sig(_LEAKS, _EVO, _stats(vpip=22.0))
    b = _study_plan_drift_sig(outros, _EVO, _stats(vpip=22.0))
    assert a != b


if __name__ == '__main__':
    falhas = 0
    testes = [v for k, v in sorted(globals().items()) if k.startswith('test_')]
    for t in testes:
        try:
            t()
            print('OK  %s' % t.__name__)
        except AssertionError as e:
            falhas += 1
            print('FALHOU  %s: %s' % (t.__name__, e))
        except Exception as e:                                  # noqa: BLE001
            falhas += 1
            print('ERRO    %s: %s: %s' % (t.__name__, type(e).__name__, e))
    print('\nTotal: %d | Passed: %d | Failed: %d' % (len(testes), len(testes) - falhas, falhas))
    sys.exit(1 if falhas else 0)
