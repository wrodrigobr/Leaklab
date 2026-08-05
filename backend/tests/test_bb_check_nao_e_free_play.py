# -*- coding: utf-8 -*-
"""O check do BB sobre limpers nao e "sempre correto" — e uma decisao que nao sabemos gradear.

── A politica, e por que ela mudou ────────────────────────────────────────────────────────────

Havia DUAS politicas para o mesmo spot:

  `sync_gto_labels_from_ranges`  BB com facing_bet=0 e check -> `gto_correct`
                                 (comentario: "BB free play: always correct")
  `analyze_preflop`              mesmo spot -> `available=False`, sem gabarito

O dado desempatou. Medido no acervo de producao em 05/08: das **163** decisoes preflop de BB com
`facing_bet = 0` e check, **163 tinham `facing_limp = 1`**. NENHUMA era free play.

E faz sentido: se todos foldassem ate o BB, a mao acabaria sem decisao dele. Havendo acao, ha
limper (ou complete do SB) — e ai o BB escolhe entre dar check e ISO-RAISAR sobre os limpers, que
e decisao de verdade. Nao iso-raisar sobre limp e leak classico de MTT, entao carimbar
`gto_correct` no check **ensinava o leak**.

Politica escolhida: **a do motor**. Sem gabarito, com motivo `limped_pot` — a mesma das outras 89
decisoes de pote limpado do acervo. Uma politica so.

── O custo, medido ANTES de decidir ───────────────────────────────────────────────────────────

163 decisoes perdem `gto_correct` (2,5% de todo `gto_correct` do acervo). O ELO cai um pouco para
quem da muito check de BB, porque o rating conta so spot com gabarito (1,5% a 2,7% da amostra por
usuario). E o lado certo do trade: o rating existe para refletir aderencia real, nao para dar
credito por nao-decisao.

O `label` nao muda — segue vindo do motor de matematica. O que sai e o selo de solver.
"""
import os, sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from leaklab.preflop_gto_ranges import analyze_preflop

_SYNC = os.path.join(os.path.dirname(__file__), '..', 'scripts',
                     'sync_gto_labels_from_ranges.py')


def _bb_check(limp=True, eff=25.0, mao='72o'):
    return analyze_preflop(position='BB', hero_hand_type=mao, stack_bb=eff,
                           action_taken='check', facing_size=0.0, vs_position='',
                           is_3bet_pot=False, facing_raises=0, hero_was_aggressor=False,
                           facing_to_bb=0.0, facing_limp=limp)


def test_check_do_bb_sobre_limp_nao_ganha_gabarito():
    """O caso real: 163 de 163 do acervo."""
    r = _bb_check(limp=True)
    assert r.get('available') is False, 'check do BB sobre limp voltou a ter gabarito'
    assert r.get('action_quality') == 'unknown'
    assert r.get('coverage_reason') == 'limped_pot', (
        f'esperava limped_pot, veio {r.get("coverage_reason")!r}')


def test_o_sync_nao_carimba_correct_no_check_do_bb():
    """FIAÇÃO: o motor pode estar certo e o sync sobrescrever antes de perguntar a ele.

    Era exatamente o que acontecia: o atalho gravava `gto_correct` sem nunca chamar o provider.
    """
    src = open(_SYNC, encoding='utf-8').read()
    # so codigo — o comentario que explica a remocao CITA o atalho antigo
    codigo = '\n'.join(l for l in src.splitlines() if not l.lstrip().startswith('#'))
    assert 'updates.append(("gto_correct", "check"' not in codigo, (
        'voltou o atalho que carimba gto_correct no check do BB — ele ensina o leak de nao '
        'iso-raisar sobre limpers, e passa por cima do provider')


def test_a_politica_e_UMA_so():
    """O mesmo spot, pelas duas portas, tem que responder a mesma coisa.

    A divergencia entre sync e motor durou meses e so apareceu quando rodei o resync no escopo
    preflop por acaso, como CONTROLE de outra coisa.
    """
    from leaklab.strategy_provider import preflop_strategy
    r = preflop_strategy(position='BB', hero_hand_type='72o', stack_bb=25.0,
                         action_taken='check', facing_size=0.0, vs_position='',
                         facing_raises=0, hero_was_aggressor=False, facing_to_bb=0.0,
                         facing_limp=True)
    assert r.get('available') is False
    assert (r.get('raw') or {}).get('coverage_reason') == 'limped_pot'


def test_o_bb_ainda_e_gradeado_quando_ENFRENTA_raise():
    """Controle negativo: a mudanca e do pote limpado, nao do BB inteiro. Se o BB parar de ser
    gradeado defendendo contra um open, o conserto vazou."""
    r = analyze_preflop(position='BB', hero_hand_type='AQs', stack_bb=25.0,
                        action_taken='call', facing_size=2.5, vs_position='BTN',
                        is_3bet_pot=False, facing_raises=1, hero_was_aggressor=False,
                        facing_to_bb=2.5, facing_limp=False)
    assert r.get('available') is True, 'BB defendendo open de BTN perdeu o gabarito'


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
