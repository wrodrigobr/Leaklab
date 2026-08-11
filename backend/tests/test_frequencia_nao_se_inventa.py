# -*- coding: utf-8 -*-
"""Frequencia da acao jogada MAIOR que a da acao modal e impossivel — e o produto imprimia as duas.

── O que acontecia ────────────────────────────────────────────────────────────────────────────

No ramo do no PARCIAL (sem `strategy_json`), o motor fazia:

    top_freq    = float(node.get('gto_freq') or 0.0)
    played_freq = top_freq if casa else (1.0 - top_freq)

`1.0 - top_freq` supoe no BINARIO, o que ja e aproximacao. Com `gto_freq` ausente ela deixa de ser
aproximacao e vira invencao: top vira 0.0 e a acao que nao casa recebe played = 1.0.

Medido em producao: **43 decisoes** com `played=1.0 / top=0.0`, todas river, todas com
`gto_label='gto_mixed'`. O card imprime os dois numeros lado a lado — eles descrevem acoes
diferentes.

── E o segundo defeito, nas MESMAS linhas ─────────────────────────────────────────────────────

As 43 tinham `gto_action='check'` com aposta na frente. `check` nao e acao legal para quem
enfrenta aposta: aquele no foi solvado para um spot de FIRST TO ACT. O produto exibia "o GTO daria
check" a quem estava enfrentando uma aposta.

`gto_top_freq = 0` no acervo inteiro ocorria SO nessas 43 linhas, e nenhuma delas era acusada.
Recusar o no custa a cobertura de 44 linhas e nao muda acusacao nenhuma. Bug que SOME com a
resposta e honesto; conserto que a TROCA nao e — e aqui a resposta estava trocada, nao ausente.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import leaklab.decision_engine_v11 as eng


def _com_no(no, facing_bb, acao='call'):
    """Roda `_enrich_gto` com o no do banco dublado. O que se testa e a LEITURA do no."""
    entrada = {
        'street': 'river', 'player_action': acao, 'hero_cards': ['Kh', 'Td'],
        'spot': {'position': 'BTN', 'board': ['Js', 'Ks', '7c', '3h', 'Jd'],
                 'effectiveStackBb': 40.0, 'facingToBb': facing_bb, 'potSize': 20.0},
        'math': {'estimatedEquity': 0.45},
    }
    # `_enrich_gto` importa `get_gto_node` de `database.repositories` DENTRO da funcao, entao o
    # dublê tem de trocar o atributo naquele modulo, nao neste. Trocar no lugar errado devolve
    # AttributeError na hora — sorte: um patch que "nao pega" e o jeito classico de um teste
    # passar medindo o codigo de producao sem o dublê.
    import database.repositories as repo
    original = repo.get_gto_node
    repo.get_gto_node = lambda _h: dict(no)
    try:
        return eng._enrich_gto(entrada)
    finally:
        repo.get_gto_node = original


#: O no real das 43: modal 'check', sem frequencia e sem strategy_json.
NO_SEM_FREQ = {'gto_action': 'check', 'gto_freq': None, 'strategy_json': None,
               'source': 'postflop_db'}


def test_no_de_CHECK_nao_serve_spot_com_aposta_na_frente():
    r = _com_no(NO_SEM_FREQ, facing_bb=6.0)
    assert r.get('available') is False, f'o no de check foi servido mesmo assim: {r}'
    assert r.get('spot_mismatch') is True, r
    print('OK  test_no_de_CHECK_nao_serve_spot_com_aposta_na_frente')


def test_CONTROLE_o_mesmo_no_serve_quando_NAO_ha_aposta():
    """Sem isto, "recusa sempre" passaria no teste de cima. First to act e o spot do no."""
    r = _com_no(NO_SEM_FREQ, facing_bb=0.0, acao='check')
    assert r.get('available') is True, f'o no legitimo foi recusado: {r}'
    assert r.get('gto_action') == 'check'
    print('OK  test_CONTROLE_o_mesmo_no_serve_quando_NAO_ha_aposta')


def test_sem_frequencia_no_no_o_produto_NAO_afirma_frequencia():
    """O par impossivel nasce aqui. Sem numero no no, sai None — nao 1.0 e nao 0.0."""
    r = _com_no(NO_SEM_FREQ, facing_bb=0.0, acao='bet')
    assert r.get('available') is True, r
    assert r.get('played_freq') is None, f"inventou frequencia da acao jogada: {r['played_freq']}"
    assert r.get('gto_freq') is None, f"0.0 saiu como se fosse medicao: {r['gto_freq']}"
    # O VEREDITO continua: o que se descarta e o numero, nao a leitura.
    assert r.get('gto_label'), r
    print('OK  test_sem_frequencia_no_no_o_produto_NAO_afirma_frequencia')


def test_CONTROLE_com_frequencia_no_no_os_numeros_aparecem():
    """A ancora: se o conserto fosse "nunca preencher frequencia", este teste cairia.

    Sao TRES casos, e so o do meio e ausencia:
      · a acao jogada E a modal          -> a frequencia do no, tal e qual
      · no MISTO, acao que nao e a modal -> None (so se sabe que e <= top)
      · no PURO (top=1.0), idem          -> 0.0 exato, e isso se sabe

    A versao anterior deste controle esperava `1.0 - top` no caso do meio, que era justamente a
    conta errada. Controle escrito contra o comportamento antigo protege o bug.
    """
    misto = dict(NO_SEM_FREQ, gto_action='bet', gto_freq=0.7)
    casa = _com_no(misto, facing_bb=0.0, acao='bet')
    assert casa['gto_freq'] == 0.7 and casa['played_freq'] == 0.7, casa

    nao_casa = _com_no(misto, facing_bb=0.0, acao='check')
    assert nao_casa['gto_freq'] == 0.7, nao_casa
    assert nao_casa['played_freq'] is None, (
        f"inventou {nao_casa['played_freq']} para a acao nao-modal de um no misto")

    puro = dict(NO_SEM_FREQ, gto_action='bet', gto_freq=1.0)
    r = _com_no(puro, facing_bb=0.0, acao='check')
    assert r['gto_freq'] == 1.0 and r['played_freq'] == 0.0, r
    print('OK  test_CONTROLE_com_frequencia_no_no_os_numeros_aparecem')


def test_a_invariante_vale_em_TODA_combinacao_do_ramo_parcial():
    """A varredura do proprio ramo: nenhuma combinacao pode produzir played > top.

    Testar so o caso reportado provaria o conserto de hoje. O par (freq do no, acao do hero) tem
    poucas combinacoes — da para varrer todas em vez de escolher uma.
    """
    ruins = []
    for freq in (None, 0.0, 0.05, 0.5, 0.9, 1.0):
        for modal in ('bet', 'call', 'fold', 'check'):
            for acao in ('bet', 'call', 'fold', 'check', 'raise'):
                facing = 0.0 if modal == 'check' else 4.0
                r = _com_no(dict(NO_SEM_FREQ, gto_action=modal, gto_freq=freq),
                            facing_bb=facing, acao=acao)
                if not r.get('available'):
                    continue
                p, t = r.get('played_freq'), r.get('gto_freq')
                if p is not None and t is not None and p > t:
                    ruins.append(f'no(modal={modal}, freq={freq}) + hero={acao} -> played={p} top={t}')
    assert not ruins, 'played_freq maior que gto_top_freq:\n  ' + '\n  '.join(ruins)
    print('OK  test_a_invariante_vale_em_TODA_combinacao_do_ramo_parcial')


if __name__ == '__main__':
    import sys as _s
    _testes = [v for k, v in sorted(globals().items()) if k.startswith('test_') and callable(v)]
    _falhas = 0
    for _t in _testes:
        try:
            _t()
        except Exception as _e:
            _falhas += 1
            print('FAIL    %s: %s: %s' % (_t.__name__, type(_e).__name__, _e))
    print()
    print('Total: %d | Passed: %d | Failed: %d' % (len(_testes), len(_testes) - _falhas, _falhas))
    _s.exit(1 if _falhas else 0)
