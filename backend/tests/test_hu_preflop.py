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
    """O caso 73, em que o COACH errou: limp e a estrategia dominante do SB ate ~30bb."""
    r = _hu(position='SB', hero_hand_type='A5s', stack_bb=17.0, action_taken='call')
    assert r['available'] is True and r['scenario'] == 'hu_rfi'
    assert r['recommended_actions'][0] == 'call', r['recommended_actions']
    assert r['action_quality'] == 'correct'


def test_distancia_relativa_escolhe_o_no_certo():
    """Regressao: stack 17 com ROOT em {1,10,25,30,40}. Distancia ABSOLUTA escolhia 10 (dist 7),
    que reprova no guarda de 40%, e o spot caia em null com o no de 25bb valido ali do lado."""
    r = _hu(position='SB', hero_hand_type='A5s', stack_bb=17.0, action_taken='raise')
    assert r['available'] is True, r.get('coverage_reason')
    assert float(r.get('hu_depth') or 0) > 20, f"escolheu {r.get('hu_depth')}"


def test_hu_sem_no_e_null_honesto():
    """SB enfrentando 3-bet nao foi capturado: available=False com motivo, nunca carta ring."""
    r = _hu(position='SB', hero_hand_type='A5s', stack_bb=17.0, action_taken='call',
            facing_size=17.0, vs_position='BB', facing_raises=1, hero_was_aggressor=True,
            facing_to_bb=17.0, facing_allin=True)
    assert r['available'] is False
    assert r.get('coverage_reason') == 'hu_uncovered'


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
