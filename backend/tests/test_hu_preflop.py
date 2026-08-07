# -*- coding: utf-8 -*-
"""Mesa de 2 nunca mais consulta carta de mesa cheia.

── O caso ─────────────────────────────────────────────────────────────────────────────────────

A revisao com o coach (05-06/08) provou por ORACULO EXTERNO (GTO Wizard HU, capturado via HAR
pelo usuario) que a carta ring mentia em heads-up:

  JJ no BB vs open de SB   nossa carta ring: call 100%   GW HU: 3-BET 100% em TODA
                                                          profundidade de 10 a 60bb

O sistema acusou de erro o 3-bet OBRIGATORIO do jogador (caso 75 da revisao). E o inverso tambem
aconteceu: no caso 73 eu chamei o limp do sistema de "erro de cenario" e o GW confirmou o limp
como estrategia dominante do SB ate ~30bb — o coach ("all-in direto") e que estava errado.

── A regra ────────────────────────────────────────────────────────────────────────────────────

`n_players == 2` roteia EXCLUSIVAMENTE para as cartas HU capturadas (`docs/hu_ranges_har.json`):
ou ha no capturado, ou `hu_uncovered` — null honesto. Nunca a carta ring.

Detalhes que ja quebraram uma vez e por isso tem teste:
- o "no mais proximo" e por distancia RELATIVA (absoluta escolhia 10bb para stack de 17 e caia
  num null indevido, com o no de 25bb disponivel e valido);
- defesa vs OPEN-JAM nao e gradeada pelo no R2 de open pequeno — gradear contra o no errado e
  exatamente o defeito que este caminho substitui.
"""
import os, sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from leaklab.preflop_gto_ranges import analyze_preflop


def _hu(**kw):
    kw.setdefault('n_players', 2)
    kw.setdefault('hero_was_aggressor', False)
    kw.setdefault('facing_raises', 0)
    kw.setdefault('facing_size', 0.0)
    kw.setdefault('facing_to_bb', 0.0)
    return analyze_preflop(**kw)


def test_jj_bb_vs_open_3bet_e_correto_e_call_e_leak():
    """O caso 75. A carta ring dizia call 100%; o GW HU manda 3-bet em toda profundidade."""
    r = _hu(position='BB', hero_hand_type='JJ', stack_bb=22.0, action_taken='raise',
            facing_size=2.2, vs_position='SB', facing_raises=1, facing_to_bb=2.2)
    assert r['available'] is True and r['scenario'] == 'hu_vs_rfi'
    assert r['action_quality'] == 'correct', r['action_quality']
    assert r['recommended_actions'][0] == 'raise'
    # e o call — a resposta da carta ring — agora e leak: prova que a ring NAO foi consultada
    r2 = _hu(position='BB', hero_hand_type='JJ', stack_bb=22.0, action_taken='call',
             facing_size=2.2, vs_position='SB', facing_raises=1, facing_to_bb=2.2)
    assert r2['action_quality'] == 'major_leak', r2['action_quality']


def test_a5s_sb_first_in_limpa():
    """O caso 73, em que o COACH errou: limp e a estrategia dominante do SB ate ~30bb.
    A 27bb (janela do no de 25); os 17bb originais ficam null ate capturar ROOT de 16-18."""
    r = _hu(position='SB', hero_hand_type='A5s', stack_bb=27.0, action_taken='call')
    assert r['available'] is True and r['scenario'] == 'hu_rfi'
    assert r['recommended_actions'][0] == 'call', r['recommended_actions']
    assert r['action_quality'] == 'correct'


def test_fronteira_de_regime_e_null_ate_capturar():
    """A licao da amostragem em producao: SB a 14,8bb caiu no no de 10bb (janela de 40%) e um
    AJo foi ACUSADO por min-raisar em vez de jamar — regime errado. A janela de 25% continua
    valendo mesmo agora que a fresta de 12-20bb foi capturada (coletor, 07/08).

    ROOT hoje: {1, 10, 12.6, 14, 16, 18, 20, 25, 30, 40}. Os buracos que sobraram sao 2-9bb e
    acima de ~50 — e la o veredito tem que continuar sendo null, nao o no mais proximo a
    qualquer distancia.
    """
    for stack in (5.0, 55.0):
        r = _hu(position='SB', hero_hand_type='AJo', stack_bb=stack, action_taken='raise')
        assert r['available'] is False, (
            f'stack {stack} usou no de outro regime ({r.get("hu_depth")})')
    for stack, faixa in ((13.0, (12, 15)), (17.0, (16, 19)), (22.5, (20, 26))):
        r = _hu(position='SB', hero_hand_type='AJo', stack_bb=stack, action_taken='raise')
        assert r['available'] is True, f'stack {stack} devia estar coberto'
        assert faixa[0] < float(r['hu_depth']) < faixa[1], (stack, r['hu_depth'])


def test_hu_sem_no_e_null_honesto():
    """Nó existente na nossa base, mas NAO naquela profundidade, segue null — a janela nao
    estica. Temos `R2` a 60bb e `R2-RAI` so ate 40bb: a 60bb o jam fica sem gabarito, e o motor
    prefere calar a gradear por um regime 33% mais raso."""
    r = _hu(position='SB', hero_hand_type='A5s', stack_bb=60.0, action_taken='call',
            facing_size=60.0, vs_position='BB', facing_raises=1, hero_was_aggressor=True,
            facing_to_bb=60.0, facing_allin=True)
    assert r['available'] is False
    assert r.get('coverage_reason') == 'hu_uncovered'


def test_mao_fora_da_range_que_chega_ao_no_nao_e_erro():
    """`R2-RAI` de 16bb tem 98 das 169: o 72o nunca chega ali porque o SB nao abre 72o. Sem
    estrategia para a mao, TODA acao virava desvio — o 72o levava `major_leak` no call E no
    fold, o que so denuncia que a carta nao tem o que dizer. Sem gabarito nao e erro."""
    for acao in ('call', 'fold'):
        r = _hu(position='SB', hero_hand_type='72o', stack_bb=16.0, action_taken=acao,
                facing_size=16.0, vs_position='BB', facing_raises=1, hero_was_aggressor=True,
                facing_to_bb=16.0, facing_allin=True)
        assert r['available'] is False, f'{acao}: {r.get("action_quality")}'
        assert r.get('coverage_reason') == 'hu_hand_out_of_range'
    # CONTROLE: mao que CHEGA ao mesmo no continua sendo gradeada
    r = _hu(position='SB', hero_hand_type='AJo', stack_bb=16.0, action_taken='call',
            facing_size=16.0, vs_position='BB', facing_raises=1, hero_was_aggressor=True,
            facing_to_bb=16.0, facing_allin=True)
    assert r['available'] is True and r['action_quality'] == 'correct'


def test_defesa_vs_open_jam_nao_usa_o_no_de_open_pequeno():
    """BB contra open-JAM de 20bb: o no R2 modela open de 2x. Gradear contra o no errado e o
    defeito original com outra roupa."""
    r = _hu(position='BB', hero_hand_type='JJ', stack_bb=20.0, action_taken='call',
            facing_size=20.0, vs_position='SB', facing_raises=1, facing_to_bb=20.0,
            facing_allin=True)
    assert r['available'] is False and r.get('coverage_reason') == 'hu_uncovered'


def test_fora_da_janela_de_profundidade_e_null():
    for stack in (4.0, 300.0):
        r = _hu(position='BB', hero_hand_type='JJ', stack_bb=stack, action_taken='call',
                facing_size=2.0, vs_position='SB', facing_raises=1, facing_to_bb=2.0)
        assert r['available'] is False, f'stack {stack} deveria ser hu_uncovered'


def test_bb_vs_limp_e_gradeado():
    """No `C` (2a captura): BB contra limp do SB tem estrategia real (check/raise mix)."""
    r = _hu(position='BB', hero_hand_type='QTs', stack_bb=30.0, action_taken='check',
            facing_limp=True)
    assert r['available'] is True and r['scenario'] == 'hu_bb_vs_limp'
    assert r['action_quality'] == 'correct'
    assert (r['hand_freq'] or {}).get('raise', 0) > 0, 'o mix de iso-raise sumiu'


def test_3bet_pequeno_e_3bet_jam_sao_NOS_DIFERENTES():
    """Os dois estao capturados (o jam veio no coletor de 07/08), e o tamanho decide qual usar.
    O que este teste protege nao e a cobertura, e a SEPARACAO: gradear um jam pela carta de
    3-bet pequeno seria o defeito da carta ring com outra roupa."""
    pequeno = _hu(position='SB', hero_hand_type='AJo', stack_bb=16.0, action_taken='fold',
                  facing_size=4.5, vs_position='BB', facing_raises=1, hero_was_aggressor=True,
                  facing_to_bb=4.5)
    assert pequeno['available'] is True and pequeno['scenario'] == 'hu_vs_3bet'
    assert pequeno['action_quality'] == 'major_leak', 'foldar AJo a 3-bet pequeno a 16bb e leak'

    jam = _hu(position='SB', hero_hand_type='AJo', stack_bb=16.0, action_taken='call',
              facing_size=16.0, vs_position='BB', facing_raises=1, hero_was_aggressor=True,
              facing_to_bb=16.0, facing_allin=True)
    assert jam['available'] is True and jam['scenario'] == 'hu_vs_3bet_jam'
    assert jam['action_quality'] == 'correct', 'pagar o jam com AJo a 16bb e a jogada da carta'


def test_bb_vs_4bet_jam_e_gradeado():
    """BB 3-betou, SB jamou por cima: no R2-Rx-RAI. JJ paga (call 100% no no de 16bb)."""
    r = _hu(position='BB', hero_hand_type='JJ', stack_bb=16.0, action_taken='call',
            facing_size=16.0, vs_position='SB', facing_raises=2, hero_was_aggressor=True,
            facing_to_bb=16.0, facing_allin=True)
    assert r['available'] is True and r['scenario'] == 'hu_vs_4bet'
    assert r['action_quality'] == 'correct'


def test_mesa_cheia_nao_muda():
    """CONTROLE: o roteamento e de mesa de 2. Em 9-max nada disto se aplica."""
    r = analyze_preflop(position='BB', hero_hand_type='JJ', stack_bb=22.0, action_taken='raise',
                        facing_size=2.2, vs_position='SB', facing_raises=1,
                        hero_was_aggressor=False, facing_to_bb=2.2, n_players=9)
    assert not str(r.get('scenario', '')).startswith('hu_'), r.get('scenario')


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
