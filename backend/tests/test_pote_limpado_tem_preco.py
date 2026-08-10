# -*- coding: utf-8 -*-
"""Pote limpado tinha custo ZERO gravado, e por isso nao tinha preco nenhum.

── O caso ─────────────────────────────────────────────────────────────────────────────────────

Veio de uma pergunta do usuario sobre o relatorio do coach: em tres maos o produto se calava onde
o coach dizia "erro grave, tem que completar". A explicacao que eu tinha escrito no relatorio
("falta capturar a carta de limp") estava errada por dois motivos.

**1. A carta nao existe.** Dos 239 nos capturados do GW, 10 tem limp na linha e 9 sao heads-up.
Em mesa cheia, 165 nos tem menu `(FOLD, RAISE)`: a arvore nao deixa UTG-BTN limpar. Nao e lacuna
de captura, e jogada que a solucao nao contem.

**2. Nao precisamos da carta — precisamos do PRECO, e ele estava zerado.**
`_facing_to_total_at` so olha `bets/raises/all-in`, e limp e `calls`. Medido no acervo:

    facing_to_call_bb zerado em POTE LIMPADO    743 de 743   (100%)
    facing_to_call_bb zerado em POTE COM RAISE    8 de 3.107   (0%)

Sem custo, `potOddsEquity` sai `None` e o motor fica sem preco no unico spot onde ele decide.

── E a equity que aparecia era a errada ───────────────────────────────────────────────────────

O `street_math_engine` so aplica correcao multiway POSTFLOP, com a justificativa "preflop ja usa
ranges GTO especificas por cenario" — verdade em todo lugar menos aqui, que e o unico spot
preflop sem carta. Num pote 5-way o produto exibia a equity HEADS-UP: `Q5o` no SB aparecia com
**50,2%** onde o numero multiway e **17,5%**.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from leaklab.multiway_advisor import (equity_realizada_em_pote_limpado,   # noqa: E402
                                      _MW_FOLD_MARGIN)


# ── A equity multiway preflop ──────────────────────────────────────────────────────────────────

def test_a_equity_CAI_com_mais_vilaos():
    """O sinal mais barato de que a conta e multiway de verdade. Se a curva nao cair, o que esta
    sendo medido e heads-up com outro nome."""
    eqs = [equity_realizada_em_pote_limpado('6s9s', n, False)[0] for n in (1, 2, 3, 4)]
    assert eqs == sorted(eqs, reverse=True), eqs
    assert eqs[0] - eqs[-1] > 0.15, f'a queda de {eqs[0]:.3f} para {eqs[-1]:.3f} e pequena demais'


def test_fora_de_posicao_realiza_MENOS():
    """MUTACAO: passar `bool(is_in_position)` na chave do cache.

    `_realization_tax` distingue `False` (fora de posicao, +4pp) de `None` (desconhecido, sem
    imposto). A primeira versao da chave usava `bool()`, que colapsa os dois — e ai o primeiro a
    ser calculado ficava no cache pelos DOIS. Foi achado rodando a mesma mao por dois caminhos e
    recebendo numeros diferentes.
    """
    oop = equity_realizada_em_pote_limpado('2c8c', 3, False)
    desconhecido = equity_realizada_em_pote_limpado('2c8c', 3, None)
    assert oop[0] == desconhecido[0], 'a equity CRUA nao depende de posicao'
    assert oop[1] < desconhecido[1], 'fora de posicao tem de realizar menos'


def test_e_ESTAVEL_entre_processos():
    """MUTACAO: voltar a semente para `hash(chave)`.

    `hash()` de string e randomizado por processo (PYTHONHASHSEED). Usa-lo como semente daria
    equity diferente a cada reprocesso — e aqui a equity decide VEREDITO, entao a mesma mao
    mudaria de rotulo sem nada ter mudado. `crc32` e estavel entre processos e maquinas.

    O teste roda um interpretador NOVO de proposito: dentro do mesmo processo o `hash` tambem e
    estavel, entao um teste in-process passaria com o defeito presente.
    """
    import subprocess
    codigo = ('import sys; sys.path.insert(0, %r);'
              'from leaklab.multiway_advisor import equity_realizada_em_pote_limpado as e;'
              'print(e("2c8c", 3, False))' % os.path.join(os.path.dirname(__file__), '..'))
    saidas = {subprocess.run([sys.executable, '-c', codigo], capture_output=True, text=True,
                             env={**os.environ, 'PYTHONHASHSEED': s}).stdout.strip()
              for s in ('0', '1', '12345')}
    assert len(saidas) == 1, f'resultado mudou com o PYTHONHASHSEED: {saidas}'


def test_aceita_LISTA_e_STRING():
    """O motor entrega `['2c','8c']` (o `_parse_cards` do pipeline) e o resto do modulo entrega
    `'2c8c'`. Aceitar so um dos dois e o bug do `_ranks_of`, que iterava string caractere a
    caractere e transformou naipe em rank em 140 de 470 decisoes."""
    assert (equity_realizada_em_pote_limpado('6s9s', 2, False)
            == equity_realizada_em_pote_limpado(['6s', '9s'], 2, False))


# ── O custo, que e a peca que faltava ──────────────────────────────────────────────────────────

def _spot(hero, raw):
    from leaklab.parser import parse_pokerstars_file_from_text
    from leaklab.pipeline import build_decision_inputs_for_hand
    h = parse_pokerstars_file_from_text(raw)[0]
    for e in build_decision_inputs_for_hand(h, hero):
        if e.get('street') == 'preflop':
            return e
    return None


_MAO_LIMPADA = """PokerStars Hand #999000111: Tournament #555, $0.85+$0.15 USD Hold'em No Limit - Level VIII (100/200) - 2026/08/10 12:00:00 ET
Table '555 1' 6-max Seat #6 is the button
Seat 1: HERO (6000 in chips)
Seat 2: VIL1 (6000 in chips)
Seat 3: VIL2 (6000 in chips)
Seat 4: VIL3 (6000 in chips)
Seat 5: VIL4 (6000 in chips)
Seat 6: VIL5 (6000 in chips)
HERO: posts small blind 100
VIL1: posts big blind 200
*** HOLE CARDS ***
Dealt to HERO [6s 9s]
VIL2: folds
VIL3: calls 200
VIL4: folds
VIL5: folds
HERO: folds
VIL1: checks
*** SUMMARY ***
Total pot 500
"""


def test_o_SB_completando_tem_custo_de_meia_cega():
    """O nivel a igualar num pote limpado e o BIG BLIND. O SB ja tem 0,5bb na frente, entao paga
    a diferenca; quem esta fora dos blinds paga 1bb; o BB paga zero, que e a opcao gratis dele.
    Sai do `to_total - o que o hero ja tem na frente`, sem caso especial por posicao."""
    e = _spot('HERO', _MAO_LIMPADA)
    assert e is not None, 'a mao de teste nao produziu decisao preflop'
    sp = e['spot']
    assert sp['facingLimp'] is True, 'o limp do VIL3 nao foi detectado'
    assert abs(float(sp['facingToCallBb']) - 0.5) < 0.01, sp['facingToCallBb']
    assert e['math']['potOddsEquity'], 'sem custo nao ha preco, e o preco e a peca que faltava'


def test_FIRST_IN_continua_sem_preco():
    """CONTROLE, e ele e o que impede o conserto de virar um raio de alcance que ninguem mediu.

    Se o custo fosse preenchido em todo pote sem raise, **3.060 decisoes de first-in** ganhariam
    pot odds de uma hora para a outra. Pagar nao e acao da arvore no first-in, e o efeito disso
    em veredito nao foi medido. O gatilho e limp DE VERDADE, nao ausencia de raise.
    """
    sem_limp = _MAO_LIMPADA.replace('VIL3: calls 200', 'VIL3: folds')
    e = _spot('HERO', sem_limp)
    assert e is not None
    assert not e['spot']['facingLimp']
    assert float(e['spot']['facingToCallBb'] or 0) == 0.0, 'first-in ganhou preco indevido'


def test_conta_quem_NAO_foldou_e_nao_so_quem_agiu():
    """MUTACAO: trocar `nCanSeeFlop` por `nActiveOpponents` no guarda.

    `nActiveOpponents` conta so quem JA AGIU voluntariamente — limitacao conhecida e documentada
    ("`still_in_now` mente preflop"). No pote limpado isso perde o BB, que tem opcao gratis e
    sempre ve o flop. Medido no `82s` do relatorio: o campo diz 2 vilaos e sao 3, e a diferenca
    inverte o veredito (18% de equity realizada vira 9%). **Contar a menos INFLA a equity**, que
    e a direcao que acusa a mais.
    """
    e = _spot('HERO', _MAO_LIMPADA)
    sp = e['spot']
    assert sp['nCanSeeFlop'] == 2, f"limper + BB = 2, veio {sp['nCanSeeFlop']}"
    assert int(sp['nActiveOpponents'] or 0) < sp['nCanSeeFlop'], (
        'controle quebrado: os dois campos precisam DIFERIR aqui, senao o teste nao discrimina')


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
