# -*- coding: utf-8 -*-
"""A carta nao acusa fold contra all-in quando o preco do pote contradiz a acusacao.

── O caso do dono (16/09), torneio 30, mao 157832100251 ──────────────────────────────────────

K7s no SB, 3-bet ALL-IN de 33,9bb, fold. A lista "Leaks por custo" acusou 1,21bb; o dono abriu o
replay e perguntou por que aquilo constava como leak se a tela nao aponta erro nenhum.

A carta usada e de `vs_3bet`, balde de **30bb**, e declara `raise_to_bb: 15.0`: ela modela um
3-bet DIMENSIONADO, que deixaria 15bb atras para jogar o flop. Com 15bb atras, seguir com K7s se
defende. Contra um shove nao ha flop: e equity pura.

E na MESMA decisao o motor mediu:

    paga 30,39bb para um pote de 38,10bb  ->  exige 44,4% de equity
    K7s contra o range                    ->  43,4%

O fold estava certo por um ponto percentual, e a carta cobrou 1,21bb. Duas fontes do nosso
proprio produto discordando, com a que acusava usando um sizing que nao era o do spot.

── O que este arquivo defende ────────────────────────────────────────────────────────────────

Que a acusacao cai SO quando o preco a contradiz, e que ela FICA quando o preco a confirma. A
regra absolve, nunca acusa: e o lado seguro da regra 7, e a mesma doutrina que ja vale para a
carta de mesa cheia do GW ("carta vizinha absolve, nao acusa"), aplicada ao sizing.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from leaklab.card_verdict import carta_nao_acusa_fold_vs_allin as absolve   # noqa: E402

#: os numeros exatos da decisao do dono
EQUITY_K7S = 0.4339
EXIGIDA    = 0.4435


def test_o_caso_do_dono_deixa_de_ser_acusado():
    q, ev = absolve('gto_minor_deviation', 1.21, facing_allin=True, acao_jogada='fold',
                    equity=EQUITY_K7S, equity_exigida=EXIGIDA)
    assert q == 'correct', q
    # o EV tambem cai, e nao so a qualidade: a lista de leaks ranqueia por CUSTO, entao deixar
    # 1,21bb de pe manteria a mao na lista depois de o card absolver -- as duas superficies
    # discordando, que e o defeito que esta semana consertou em dezenas de lugares.
    assert ev is None, ev


def test_quando_o_preco_FECHA_a_acusacao_fica():
    """O outro lado, e o que impede a regra de virar uma anistia geral: com equity acima da
    exigida, a carta e o pote concordam que era call, e o fold segue sendo leak."""
    q, ev = absolve('gto_critical', 3.0, facing_allin=True, acao_jogada='fold',
                    equity=0.62, equity_exigida=0.44)
    assert q == 'gto_critical', q
    assert ev == 3.0, ev
    # e no limite exato (equity == exigida) a acusacao tambem fica: empate nao absolve
    q2, ev2 = absolve('gto_critical', 3.0, facing_allin=True, acao_jogada='fold',
                      equity=0.4435, equity_exigida=0.4435)
    assert (q2, ev2) == ('gto_critical', 3.0), (q2, ev2)


def test_so_vale_contra_ALL_IN():
    """Num 3-bet dimensionado o no da carta corresponde ao spot, e a acusacao e legitima: a
    premissa da regra e justamente NAO haver stack atras."""
    q, ev = absolve('gto_critical', 1.21, facing_allin=False, acao_jogada='fold',
                    equity=EQUITY_K7S, equity_exigida=EXIGIDA)
    assert (q, ev) == ('gto_critical', 1.21), (q, ev)


def test_so_vale_para_FOLD():
    """Quem PAGOU o all-in nao e absolvido por preco: se o preco nao fechava, pagar e que foi o
    desvio, e `_normalize_facing_allin` ja cuida do caso em que pagar era a linha agressiva."""
    for acao in ('call', 'allin', 'raise', 'shove'):
        q, ev = absolve('gto_critical', 1.21, facing_allin=True, acao_jogada=acao,
                        equity=EQUITY_K7S, equity_exigida=EXIGIDA)
        assert (q, ev) == ('gto_critical', 1.21), (acao, q, ev)


def test_sem_os_DOIS_numeros_nao_absolve():
    """Absolver sem medida seria anistia disfarcada de conserto: sem equity ou sem exigida, a
    regra nao tem base para contradizer a carta e sai de fininho."""
    for eq, ex in ((None, EXIGIDA), (EQUITY_K7S, None), (None, None), ('x', EXIGIDA)):
        q, ev = absolve('gto_critical', 1.21, facing_allin=True, acao_jogada='fold',
                        equity=eq, equity_exigida=ex)
        assert (q, ev) == ('gto_critical', 1.21), (eq, ex, q, ev)


def test_quem_ja_estava_correto_passa_intacto():
    for q0 in ('correct', 'unknown'):
        q, ev = absolve(q0, None, facing_allin=True, acao_jogada='fold',
                        equity=EQUITY_K7S, equity_exigida=EXIGIDA)
        assert (q, ev) == (q0, None), (q0, q, ev)


def test_a_fiacao_do_motor_passa_os_numeros_certos():
    """CONTROLE da fiacao, que e onde a versao anterior de uma regra igual a esta passou verde
    com a condicao trocada (25/08, quatro guardas cegos): a funcao pura pode estar perfeita e o
    motor chamar com o argumento errado.

    Le o fonte porque montar uma decisao preflop inteira aqui exigiria carta, range e contexto;
    o que precisa ser travado e que os quatro argumentos venham das fontes certas.
    """
    import inspect

    from leaklab import decision_engine_v11 as eng
    fonte = inspect.getsource(eng)
    i = fonte.index('carta_nao_acusa_fold_vs_allin')
    trecho = fonte[i:i + 600]
    assert "facing_allin=bool(spot.get('facingAllin'))" in trecho, trecho[:300]
    assert "acao_jogada=_acao_real" in trecho, trecho[:300]
    assert "equity=math.get('estimatedHandEquity')" in trecho, trecho[:300]
    assert "equity_exigida=threshold_pack.get('adjustedRequiredEquity')" in trecho, trecho[:300]
    # e o ev_loss precisa ser zerado no dicionario, senao a lista de leaks nao muda
    assert "'ev_loss_bb': None" in trecho, trecho[:400]


if __name__ == '__main__':
    passed = failed = 0
    for nome, fn in sorted(list(globals().items())):
        if not nome.startswith('test_') or not callable(fn):
            continue
        try:
            fn()
            print('OK  %s' % nome)
            passed += 1
        except AssertionError as e:
            print('FALHOU  %s: %s' % (nome, e))
            failed += 1
        except Exception as e:
            print('ERRO    %s: %s: %s' % (nome, type(e).__name__, e))
            failed += 1
    print('\nTotal: %d | Passed: %d | Failed: %d' % (passed + failed, passed, failed))
    sys.exit(1 if failed else 0)
