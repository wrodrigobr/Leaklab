# -*- coding: utf-8 -*-
"""Limpar fora dos blinds nao e falta de carta, e desvio.

── O caso ─────────────────────────────────────────────────────────────────────────────────────

Observacao do usuario, e ela e de POKER antes de ser de codigo: limp so e acao legitima nos
blinds — o SB completa por meia cega, o BB tem a opcao gratis. De UTG a BTN a jogada e fold ou
RFI, nunca limp.

Conferido contra o proprio GTO Wizard, em **374 nos de primeira decisao** dos HAR em disco:

    UTG..BTN   menu = ('FOLD', 'RAISE')            <- nao existe CALL
    SB         menu = ('FOLD', 'CALL', 'RAISE')    <- o complete existe

Ou seja: nao e lacuna de captura. E acao que a arvore nao contem.

── O defeito ──────────────────────────────────────────────────────────────────────────────────

O hero limpando de ABERTURA (ninguem antes) ja era acusado — 17 decisoes do acervo, todas com
veredito. O mesmo hero limpando ATRAS de outro limp caia no desvio `limped_pot` e ficava MUDO —
41 decisoes, todas sem gabarito.

Dois vereditos diferentes para o mesmo erro, decididos por **quem agiu antes dele**.

── A regra ────────────────────────────────────────────────────────────────────────────────────

Fora dos blinds, a carta de RFI responde as duas pontas: mao no range → o certo era RAISE; fora do
range → era FOLD. Nos dois casos o limp e o desvio. Nos blinds o desvio `limped_pot` continua,
porque la limpar E jogada — e para essa nao temos carta.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from leaklab.preflop_gto_ranges import analyze_preflop


def _spot(pos, mao, stack, acao='call', limp=True, n=8):
    return analyze_preflop(position=pos, hero_hand_type=mao, stack_bb=stack, action_taken=acao,
                           facing_size=0.0, vs_position='', facing_raises=0, n_players=n,
                           facing_limp=limp)


def test_over_limp_fora_dos_blinds_e_acusado():
    """Era o buraco: 41 decisoes mudas. A carta diz o que era certo nas duas pontas."""
    no_range = _spot('CO', 'A8s', 45.0)
    assert no_range['available'] is True, no_range.get('coverage_reason')
    assert no_range['action_quality'] == 'major_leak'
    assert no_range['recommended_actions'] == ['raise'], no_range['recommended_actions']

    fora = _spot('CO', '72o', 45.0)
    assert fora['available'] is True
    assert fora['recommended_actions'] == ['fold'], fora['recommended_actions']


def test_o_mesmo_erro_tem_o_mesmo_veredito_com_ou_sem_limp_antes():
    """O que tornava o defeito absurdo: quem agiu ANTES do hero decidia se ele seria julgado.
    Limp de abertura e over-limp sao o mesmo erro do hero."""
    for pos, mao in (('CO', 'A8s'), ('HJ', 'KJo'), ('BTN', '76s'), ('UTG', 'J4o')):
        abertura = _spot(pos, mao, 40.0, limp=False)
        atras = _spot(pos, mao, 40.0, limp=True)
        assert abertura['available'] == atras['available'], (pos, mao)
        assert abertura['action_quality'] == atras['action_quality'], (
            f'{pos} {mao}: abertura={abertura["action_quality"]} over-limp={atras["action_quality"]}')
        assert abertura['recommended_actions'] == atras['recommended_actions'], (pos, mao)


def test_NOS_BLINDS_limpar_continua_sem_gabarito():
    """CONTROLE, e o que impede o conserto de virar anistia ao contrario: no SB e no BB limpar E
    jogada legitima, e para ESSA nao temos carta. Acusar ali seria inventar veredito."""
    for pos in ('SB', 'BB'):
        r = _spot(pos, 'A8s', 45.0)
        assert r['available'] is False, f'{pos}: virou acusacao — limpar no blind e legitimo'
        assert r.get('coverage_reason') == 'limped_pot'


def test_quem_NAO_limpou_num_pote_limpado_segue_sem_gabarito():
    """CONTROLE 2. A saida nova e so para a acao de LIMPAR. Iso-raisar ou foldar sobre um limp e
    outra decisao — a range de iso e mais larga que a de RFI, e nao temos essa carta. Estender
    aqui seria gradear pela carta errada, que e o defeito que este projeto passa o dia matando."""
    for acao in ('raise', 'fold'):
        r = _spot('CO', 'A8s', 45.0, acao=acao)
        assert r['available'] is False, f'{acao} sobre limp virou veredito sem carta'
        assert r.get('coverage_reason') == 'limped_pot'


def test_o_atalho_de_push_fold_continua_valendo():
    """CONTROLE 3: o ramo que ja existia (<=12bb, jam/fold com limp como dead money) nao pode ter
    sido roubado pela saida nova — ela vem DEPOIS dele no if."""
    r = _spot('CO', 'A8s', 10.0, acao='jam')
    assert r.get('limp_dead_money') is True, r.get('coverage_reason')
    assert 'limp_fora_dos_blinds' not in r


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
