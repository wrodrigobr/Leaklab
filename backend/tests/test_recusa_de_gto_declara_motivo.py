# -*- coding: utf-8 -*-
"""Toda recusa de cobertura GTO diz POR QUE.

── O caso que originou (26/08) ────────────────────────────────────────────────────────────

O acervo tinha **1.300 decisões com `gto_label` NULL**, todas caindo no heurístico. Dessas, **68
tinham nó de solver hand-aware no banco, casando por `spot_hash`** — e mesmo assim o motor as
recusava. Sondei perguntando ao próprio motor e a resposta foi: `available=False`, **motivo:
"sem_motivo_declarado"**, nas 68.

`_enrich_gto` tinha ONZE saídas `{'available': False}` e apenas duas diziam alguma coisa
(`spot_mismatch`, `ungradeable_action`). Ausência calada não dá para atacar — só para conviver.

Isto NÃO muda comportamento: quem recusava segue recusando. O que muda é que agora dá para contar
POR MOTIVO, e cada motivo vira um alvo ou uma decisão consciente de não cobrir. É a regra 6 do
CLAUDE.md ("operação que pode falhar em silêncio precisa de conferência explícita") aplicada ao
coração do enriquecimento.
"""
import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

_FONTE = os.path.join(os.path.dirname(__file__), '..', 'leaklab', 'decision_engine_v11.py')


def _corpo_do_enriquecimento():
    """Só o corpo de `_enrich_gto` — as outras funções do módulo têm política própria."""
    with open(_FONTE, encoding='utf-8') as fh:
        fonte = fh.read()
    i = fonte.index('def _enrich_gto(')
    j = fonte.index('\ndef ', i + 10)
    return fonte[i:j]


def test_nenhuma_recusa_do_enriquecimento_sai_muda():
    """Varredura N+1: recusa nova que esqueça o motivo cai aqui, não em produção seis meses
    depois quando alguém for medir por que 1.300 decisões não têm veredito."""
    corpo = _corpo_do_enriquecimento()
    mudas = []
    for m in re.finditer(r"return \{['\"]available['\"]:\s*False", corpo):
        trecho = corpo[m.start():m.start() + 220]
        if 'coverage_reason' not in trecho:
            linha = corpo[:m.start()].count(chr(10)) + 1
            mudas.append('linha %d de _enrich_gto' % linha)
    assert not mudas, (
        'recusa(s) de cobertura GTO sem motivo declarado: %s — use `_sem_gto(motivo)`, senão a '
        'ausência volta a ser muda e não dá para atacar' % ', '.join(mudas))
    print('OK  test_nenhuma_recusa_do_enriquecimento_sai_muda')


def test_o_motivo_CHEGA_no_resultado():
    """Declarar no `_sem_gto` e não propagar seria cobertura sem cobertura. Ancora no valor que
    a sonda realmente lê."""
    from leaklab.decision_engine_v11 import _enrich_gto

    # street que o enriquecimento postflop não atende: recusa conhecida e estável
    r = _enrich_gto({'street': 'preflop', 'spot': {}, 'player_action': 'fold'})
    assert r.get('available') is False
    assert r.get('coverage_reason') == 'nao_e_postflop', (
        'o motivo não chegou ao resultado: veio %r' % r.get('coverage_reason'))
    print('OK  test_o_motivo_CHEGA_no_resultado')


def test_a_recusa_continua_sendo_recusa():
    """Contraprova. Um `_sem_gto` que devolvesse `available=True` faria os dois testes acima
    passarem e quebraria o produto inteiro — o motivo é um ADENDO, não uma troca de política."""
    from leaklab.decision_engine_v11 import _sem_gto

    r = _sem_gto('qualquer_motivo')
    assert r['available'] is False, 'a recusa deixou de recusar'
    assert r['coverage_reason'] == 'qualquer_motivo'
    extra = _sem_gto('outro', spot_mismatch=True)
    assert extra['spot_mismatch'] is True, 'os campos antigos pararam de viajar junto'
    print('OK  test_a_recusa_continua_sendo_recusa')


if __name__ == '__main__':
    falhas = 0
    testes = [v for k, v in sorted(globals().items()) if k.startswith('test_')]
    for teste in testes:
        try:
            teste()
        except AssertionError as e:
            falhas += 1
            print('FALHOU  %s: %s' % (teste.__name__, e))
        except Exception as e:                              # noqa: BLE001
            falhas += 1
            print('ERRO    %s: %s: %s' % (teste.__name__, type(e).__name__, e))
    print('\nTotal: %d | Passed: %d | Failed: %d' % (len(testes), len(testes) - falhas, falhas))
    sys.exit(1 if falhas else 0)
