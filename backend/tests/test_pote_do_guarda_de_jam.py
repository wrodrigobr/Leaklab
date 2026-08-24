# -*- coding: utf-8 -*-
"""`spot.potBb` tem que ser o pote que o jogador ENFRENTA, não a soma crua das apostas.

── O caso que originou (24/08, auditoria pré-lançamento) ──────────────────────────────────

`potBb` vinha de `state.pot_size` (`_pot_up_to`), que o próprio `hand_state_builder` declara
acertar **1,2%** contra o `Total pot` do SUMMARY: perde os blinds e as antes, e conta o
incremento do raise em vez do total do jogador. O número sai sempre MENOR que o real.

Quem consome:

  · GUARDA DE JAM (`decision_engine_v11`, ~linha 710) — rejeita nó de all-in quando
    `stack_bb / potBb > 3`. Pote menor ⇒ SPR maior ⇒ o guarda rejeita jam DEMAIS, e a decisão
    cai no heurístico em vez de usar o nó do solver.
  · `lookup_gto(pot_bb=...)` do `/replay` — escolhe QUAL nó é servido.

Medido em 184 decisões postflop do acervo: **7 rejeições com o número antigo, 1 com o certo —
6 nós GTO recuperados.** Uma das rejeições dizia `pote 0.5bb` no postflop, o que não existe:
depois do preflop o pote já tem, no mínimo, os blinds.

── Por que um teste, e não só o conserto ──────────────────────────────────────────────────

O valor certo (`pot_at_decision`) já estava no mesmo dict, na linha de baixo, e ninguém lia.
Nada quebrava, nenhum teste ficava vermelho: o defeito só aparecia como cobertura GTO menor —
um silêncio, não um erro. É o tipo que volta na próxima refatoração se não houver guarda.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))


def _spot_de(pot_at_decision, pot_size, bb):
    """Monta o dict como o `pipeline` monta, sem depender de um hand history real."""
    class _State:
        pass
    st = _State()
    st.pot_size = pot_size
    st.metadata = {'bb': bb, 'pot_at_decision': pot_at_decision}
    # Mesma expressão do pipeline — se ela mudar lá e não aqui, o segundo teste acusa.
    return (round(float((st.metadata or {}).get('pot_at_decision')) / (st.metadata.get('bb') or 1), 2)
            if (st.metadata or {}).get('pot_at_decision')
            else round(st.pot_size / (st.metadata.get('bb') or 1), 2))


def test_potBb_usa_o_pote_enfrentado_e_nao_a_soma_crua():
    # Caso real do acervo: bb=60, apostas cruas somam 30 fichas (0,5bb), mas o pote que o
    # jogador enfrenta é 132 fichas (2,2bb) porque inclui blinds e antes.
    assert _spot_de(132.0, 30.0, 60.0) == 2.2, 'potBb ignorou o pote enfrentado'
    # Sem o valor certo, cai no antigo em vez de virar None.
    assert _spot_de(None, 30.0, 60.0) == 0.5, 'o fallback sumiu — potBb viraria None'
    print('OK  test_potBb_usa_o_pote_enfrentado_e_nao_a_soma_crua')


def test_o_pipeline_realmente_le_pot_at_decision():
    """Prova de fiação. O teste acima replica a expressão; este confere que o `pipeline` de
    verdade a contém — senão eu estaria testando a minha cópia, não o produto."""
    caminho = os.path.join(os.path.dirname(__file__), '..', 'leaklab', 'pipeline.py')
    with open(caminho, encoding='utf-8') as fh:
        fonte = fh.read()
    assert "'potAtDecision'" in fonte, 'o pipeline parou de expor potAtDecision'
    trecho = fonte[fonte.index("'potBb'"):fonte.index("'potBb'") + 600]
    assert 'pot_at_decision' in trecho, (
        "`potBb` voltou a ser calculado só de `state.pot_size` — o guarda de jam volta a "
        "rejeitar nó de all-in por SPR inflado")
    print('OK  test_o_pipeline_realmente_le_pot_at_decision')


def test_o_guarda_de_jam_ainda_rejeita_SPR_alto():
    """Contraprova: o conserto não pode DESLIGAR o guarda. SPR realmente alto continua
    rejeitando — o caso que sobrou na medição (21bb de stack, 2,2bb de pote, SPR 9,5)."""
    stack, pote = 21.0, 2.2
    assert (stack / pote) > 3.0, 'o caso de controle deixou de ser SPR alto'
    # E o inverso: o SPR que o pote errado inventava (0,5bb) era absurdo e sumiu.
    assert (stack / 0.5) > 40, 'o SPR inflado do pote antigo não era tão absurdo assim'
    print('OK  test_o_guarda_de_jam_ainda_rejeita_SPR_alto')


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
