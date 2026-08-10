# -*- coding: utf-8 -*-
"""O EV exibido tem de caber no JOGO — o card mostrava -3588bb num stack de 32,2bb.

── O caso ─────────────────────────────────────────────────────────────────────────────────────

Print do usuario: veredito ERRO com selo **"-3588 bb"**, linhas "Call 100% 3588.4bb" e
"Custo de oportunidade: -3588,36 BB", num spot com **Stack 32.2bb**. Perder 3.588 big blinds com
32 na frente nao e exagero de estimativa: e impossivel.

Nao era um card. Medido no acervo de producao:

    decisoes com ev_loss_bb gravado ........ 6.275
    com |EV| MAIOR do que cabe na mao .........  62
      dessas, rotuladas `clear_mistake` .......  34

O veredito mais duro do produto apoiado num numero que nao pode existir.

── A causa, ja documentada ────────────────────────────────────────────────────────────────────

Esta em `ev_loss_fold_ceiling`: o EV do solver vem na escala do **POTE COM QUE O NO FOI SOLVADO**,
e `compute_spot_hash` nao inclui o tamanho do pote. Um no solvado num pote de 5bb e servido a um
spot de 31,8bb, e o numero volta numa escala que nao e a daquele spot. **O pote solvado nao e
gravado em lugar nenhum**, entao nao ha como reescalar — so da para conferir e calar.

── Por que os guardas existentes nao pegaram ──────────────────────────────────────────────────

`ev_loss_trustworthy` tinha duas perguntas, e nenhuma era esta:

  · a fonte e confiavel?              -> `solver_hand` e, passa
  · o STACK esta acima do teto?       -> 16bb esta bem abaixo de 100bb, passa
  · (so em fold) contradiz a conta?   -> devolve `None` quando falta equity/pote, e ai passa

Nenhuma pergunta se o VALOR e possivel. O teto novo e a fisica do jogo, nao um limiar: numa mao o
hero ganha no maximo o pote mais o que o vilao cobre, e perde no maximo o proprio stack.
`pote + 2 x stack` e generoso de proposito — mata o impossivel sem apertar o duvidoso, que os
outros dois guardas ja fazem.

── E a tela tinha porta propria ───────────────────────────────────────────────────────────────

O motor consultava o guarda para decidir SEVERIDADE; o card lia o valor gravado direto. Duas
portas para o mesmo fato, e so uma com fechadura. Agora as duas superficies do card (o selo de
custo e as linhas por acao) passam pela mesma funcao e calam juntas.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from leaklab.decision_engine_v11 import ev_loss_trustworthy   # noqa: E402


def _ok(ev, stack, pot, acao='call'):
    return ev_loss_trustworthy(ev, stack, 'solver_hand', action=acao,
                               equity=0.40, pot_bb=pot, facing_bb=2.0)


def test_o_caso_do_print_e_recusado():
    """MUTACAO: apagar o bloco do teto fisico.

    Os numeros exatos do card reportado: stack 32,2bb, SPR 3,0 (pote ~10,7bb), EV de -3588,36."""
    assert _ok(3588.36, 32.2, 10.7, 'fold') is False


def test_a_pior_do_acervo_e_recusada():
    """68.724bb num stack de 16,16bb com pote de 16,9 — o teto fisico ali e 49,2bb."""
    assert _ok(68724.66, 16.16, 16.9, 'fold') is False


def test_CONTROLE_o_EV_legitimo_continua_passando():
    """O guarda tem de matar o impossivel sem apertar o duvidoso. Sem estes controles, `return
    False` sempre passaria nos dois testes acima e mataria o EV do produto inteiro."""
    assert _ok(2.0, 30.0, 12.0) is True, 'perda pequena num stack normal'
    assert _ok(30.0, 30.0, 12.0) is True, 'perder o stack inteiro E possivel'
    assert _ok(71.9, 30.0, 12.0) is True, 'pote + 2 stacks ainda cabe (o teto e generoso)'


def test_a_fronteira_discrimina():
    """Um passo acima do teto ja e recusado. Sem isto o teto poderia estar em qualquer lugar."""
    assert _ok(72.0, 30.0, 12.0) is True, 'exatamente no teto ainda passa'
    assert _ok(72.1, 30.0, 12.0) is False, 'um decimo acima do teto tem de cair'


def test_vale_para_TODA_acao_e_nao_so_para_fold():
    """O teto de fold existe porque la a aritmetica e fechada. Este e outro: 61 das 62 decisoes
    impossiveis do acervo eram folds, mas uma era CALL — e o guarda antigo nao tinha nada para
    call ou raise."""
    for acao in ('call', 'raise', 'bet', 'check', 'fold'):
        assert _ok(9999.0, 20.0, 10.0, acao) is False, f'{acao} passou com EV impossivel'


def test_sem_stack_nao_inventa_teto():
    """CONTROLE: sem saber o stack nao ha teto para conferir, e chutar um apagaria EV legitimo.
    O comportamento antigo (passar) e o certo aqui — e o mesmo principio de
    `ev_loss_fold_ceiling`, que devolve None quando falta dado."""
    assert ev_loss_trustworthy(50.0, None, 'solver_hand', action='call',
                               equity=0.4, pot_bb=10.0, facing_bb=2.0) is True


# ── A porta da TELA ───────────────────────────────────────────────────────────────────────────

def test_as_duas_superficies_do_card_calam_JUNTAS():
    """MUTACAO: fazer `_sem_ev_impossivel` devolver `hand_strategy` intacto.

    O selo de custo e as linhas por acao sao superficies diferentes do mesmo card. Se so uma
    calar, o card volta a se contradizer — foi assim que 263 cards mostraram texto de uma fonte e
    veredito de outra em 05/08. As FREQUENCIAS ficam: sao estrategia, nao dependem de escala.
    """
    from api.app import _ev_para_exibir, _sem_ev_impossivel
    dec = {'ev_loss_bb': 3588.36, 'ev_loss_source': 'solver_hand',
           'action_taken': 'fold', 'estimated_equity': 0.34}
    di = {'math': {'estimatedHandEquity': 0.34}}
    spot = {'effectiveStackBb': 32.2, 'potBb': 10.7, 'facingToCallBb': 2.0}
    hs = {'actions': [{'action': 'call', 'frequency': 1.0, 'ev_bb': 3588.4, 'ev_loss_bb': 0.0},
                      {'action': 'fold', 'frequency': 0.0, 'ev_bb': -3588.4, 'ev_loss_bb': 3588.4}]}

    assert _ev_para_exibir(dec, di, spot) is None, 'o selo ainda mostraria o numero impossivel'
    limpo = _sem_ev_impossivel(hs, dec, di, spot)
    assert all(a['ev_bb'] is None for a in limpo['actions']), 'as linhas por acao mantiveram o EV'
    assert [a['frequency'] for a in limpo['actions']] == [1.0, 0.0], (
        'as frequencias sumiram junto — elas sao estrategia e nao dependem de escala')

    # CONTROLE: com EV que cabe, NADA e removido nas duas superficies.
    dec_ok = {**dec, 'ev_loss_bb': 1.8}
    hs_ok = {'actions': [{'action': 'call', 'frequency': 1.0, 'ev_bb': 4.2, 'ev_loss_bb': 0.0}]}
    assert _ev_para_exibir(dec_ok, di, spot) == 1.8
    assert _sem_ev_impossivel(hs_ok, dec_ok, di, spot)['actions'][0]['ev_bb'] == 4.2


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
