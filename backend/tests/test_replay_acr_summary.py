"""
Replay da ACR: a mao vai ate o fim, com as duas maos reveladas no showdown.

── O bug reportado ────────────────────────────────────────────────────────────────────────────

Usuario: "a mao nao esta indo ate o final, esta sendo interrompida, as vezes no turn, outras
no river". Medido em producao (torneio ACR, mao com all-in no turn): o replay tinha 23 frames,
o ultimo board mostrava so 4 cartas (o rio NUNCA aparecia) e nao existia frame de conclusao.

Duas causas, as duas do mesmo formato: os regexes de `_parse_summary` foram escritos so contra
o dialeto PokerStars/GGPoker ("and won (1,110)", valor entre parenteses, sem centavos). A ACR
escreve "and won 1110.00" — sem parenteses, com centavos — e tem duas linhas de SUMMARY que nao
existiam em nenhum site: "did not show and won X" (ganhou sem showdown) e "showed [...] and
lost com ..." (perdedor revelado). Sem nenhuma linha reconhecida, o frame de conclusao nunca
disparava.

A segunda causa: quando o all-in acontece cedo (turn), NENHUMA acao existe nas ruas seguintes
(ninguem mais decide) — e o frame de rua (com o board revelado) so era criado ao encontrar uma
ACAO naquela rua. Sem acao, sem frame, mesmo que o board tenha sido dealt de verdade.

── O que este arquivo trava ──────────────────────────────────────────────────────────────────

Que o board final do replay tenha SEMPRE o mesmo tamanho do board que o parser extraiu
(nunca menos), que o frame de conclusao apareca quando ha showdown, que ele revele as
cartas de QUEM GANHOU e de QUEM PERDEU (nao so o vencedor), e que os formatos antigos
(PokerStars com parenteses e virgula) continuem funcionando.
"""
import os, sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from leaklab.parser import parse_pokerstars_file_from_text
from api.app import _build_replay_data


# A mao real que expos o bug (torneio 125, hand 2789040312): all-in no turn, ninguem age no
# river, showdown com dois jogadores revelando.
_MAO_ACR_ALLIN_TURN = """Game Hand #2789040312 - Tournament #35598158 - Holdem (No Limit) - Level 4 (750.00/1500.00) - 2026/07/29 21:04:21 UTC
Table '2' 8-max Seat #1 is the button
Seat 1: MusashiBR (29920.00)
Seat 2: elvin6161 (31050.00)
Seat 3: JAMESHARPER (50197.00)
Seat 4: MoneyFunnel (72578.00)
Seat 5: Simplysim (26100.00)
Seat 6: Bitemee126 (70400.00)
Seat 7: Rushgar (30000.00)
Seat 8: Thisbitch86 (30000.00)
MusashiBR posts ante 150.00
elvin6161 posts ante 150.00
JAMESHARPER posts ante 150.00
MoneyFunnel posts ante 150.00
Simplysim posts ante 150.00
Bitemee126 posts ante 150.00
Rushgar posts ante 150.00
Thisbitch86 posts ante 150.00
elvin6161 posts the small blind 750.00
JAMESHARPER posts the big blind 1500.00
*** HOLE CARDS ***
Main pot 1200.00
Dealt to MusashiBR [9d Ac]
MoneyFunnel folds
Simplysim folds
Bitemee126 raises 3000.00 to 3000.00
Rushgar calls 3000.00
Thisbitch86 folds
MusashiBR calls 3000.00
elvin6161 folds
JAMESHARPER calls 1500.00
*** FLOP *** [5h 2h 3c]
Main pot 13950.00
JAMESHARPER checks
Bitemee126 checks
Rushgar bets 3000.00
MusashiBR calls 3000.00
JAMESHARPER calls 3000.00
Bitemee126 folds
*** TURN *** [5h 2h 3c] [Ad]
Main pot 22950.00
JAMESHARPER checks
Rushgar bets 7988.00
MusashiBR raises 15976.00 to 15976.00
JAMESHARPER folds
Rushgar raises 15862.00 to 23850.00 and is all-in
MusashiBR calls 7794.00 and is all-in
Uncalled bet (80.00) returned to Rushgar
*** RIVER *** [5h 2h 3c Ad] [Ks]
Main pot 70490.00
*** SHOW DOWN ***
Main pot 70490.00
MusashiBR shows [9d Ac] (a pair of Aces [Ad Ac Ks 9d 5h])
Rushgar shows [8c As] (a pair of Aces [As Ad Ks 8c 5h])
MusashiBR collected 70490.00 from main pot
*** SUMMARY ***
Total pot 70490.00
Board [5h 2h 3c Ad Ks]
Seat 1: MusashiBR (button) showed [9d Ac] and won 70490.00 with a pair of Aces [Ad Ac Ks 9d 5h] with the kicker Nine
Seat 2: elvin6161 (small blind) folded on the Pre-Flop
Seat 3: JAMESHARPER (big blind) folded on the Turn
Seat 4: MoneyFunnel folded on the Pre-Flop and did not bet
Seat 5: Simplysim folded on the Pre-Flop and did not bet
Seat 6: Bitemee126 folded on the Flop
Seat 7: Rushgar showed [8c As] and lost with a pair of Aces [As Ad Ks 8c 5h]
Seat 8: Thisbitch86 folded on the Pre-Flop and did not bet
"""

# Uma mao ACR com vitoria SEM showdown ("did not show and won"), o terceiro formato que
# faltava em _parse_summary.
_MAO_ACR_SEM_SHOWDOWN = """Game Hand #1111111111 - Tournament #99999999 - Holdem (No Limit) - Level 1 (10.00/20.00) - 2026/07/29 20:00:00 UTC
Table '1' 6-max Seat #1 is the button
Seat 1: PlayerA (2000.00)
Seat 2: PlayerB (2000.00)
PlayerA posts the small blind 10.00
PlayerB posts the big blind 20.00
*** HOLE CARDS ***
Dealt to PlayerA [Ah Kh]
PlayerA raises 40.00 to 40.00
PlayerB folds
Uncalled bet (20.00) returned to PlayerA
PlayerA collected 40.00 from main pot
*** SUMMARY ***
Total pot 40.00
Seat 1: PlayerA (button) did not show and won 40.00
Seat 2: PlayerB (big blind) folded on the Pre-Flop
"""


def _replay_de(raw_text, hero):
    hands = parse_pokerstars_file_from_text(raw_text)
    assert hands, 'a mao de teste nao parseou nenhuma ParsedHand'
    return _build_replay_data(hands[0], [], hero)


def test_o_board_final_tem_as_5_cartas():
    """O bug relatado: o board parava em 4 cartas (turn), o rio nunca aparecia."""
    replay = _replay_de(_MAO_ACR_ALLIN_TURN, 'MusashiBR')
    tl = replay['timeline']
    assert len(tl[-1]['board']) == 5, tl[-1]['board']


def test_a_rua_sem_acao_ganha_o_proprio_frame():
    """All-in no turn: ninguem age no river, mas o board continua sendo dealt. Antes, sem
    acao na rua, o frame de 'street' nunca era criado."""
    replay = _replay_de(_MAO_ACR_ALLIN_TURN, 'MusashiBR')
    tipos = [f['type'] for f in replay['timeline']]
    rios = [f for f in replay['timeline'] if f['type'] == 'street' and f.get('desc') == 'RIVER']
    assert rios, f'nenhum frame RIVER na timeline: {tipos}'


def test_o_frame_de_conclusao_existe_e_revela_as_DUAS_maos():
    """Antes: o vencedor era capturado (quando o formato batia), o PERDEDOR revelado nunca.
    Este e o caso que faltava em qualquer site, nao so ACR."""
    replay = _replay_de(_MAO_ACR_ALLIN_TURN, 'MusashiBR')
    sd = next((f for f in replay['timeline'] if f['type'] == 'showdown'), None)
    assert sd, 'sem frame de conclusao'
    revelado = sd['revealed_cards']
    assert set(revelado.get('1', [])) == {'9d', 'Ac'}, revelado   # MusashiBR, venceu
    assert set(revelado.get('7', [])) == {'8c', 'As'}, revelado   # Rushgar, perdeu
    vencedores = [w['player'] for w in sd['summary']['winners']]
    assert vencedores == ['MusashiBR'], vencedores


def test_vitoria_sem_showdown_tambem_conclui():
    """Terceiro formato da ACR: 'did not show and won X' (ganhou sem ninguem ver as cartas)."""
    replay = _replay_de(_MAO_ACR_SEM_SHOWDOWN, 'PlayerA')
    sd = next((f for f in replay['timeline'] if f['type'] == 'showdown'), None)
    assert sd, 'sem frame de conclusao numa vitoria sem showdown'
    vencedores = [w['player'] for w in sd['summary']['winners']]
    assert vencedores == ['PlayerA'], vencedores


def test_ggpoker_showed_e_won_SEM_a_descricao_da_mao():
    """Achado varrendo produção depois do fix da ACR: a GGPoker às vezes escreve so 'showed [2s]
    and won (46,800)', sem o 'with a description' — mesma familia de bug, outro site. Sem o "?"
    no final do regex essa linha nunca casava e a conclusao ficava tao ausente quanto na ACR."""
    raw_gg = """Poker Hand #TM1: Tournament #1, Test - Level1(100/200) - 2026/07/01 00:00:00 ET
Table '1' 6-max Seat #1 is the button
Seat 1: Hero (10000 in chips)
Seat 2: Vilao (10000 in chips)
Hero: posts small blind 100
Vilao: posts big blind 200
*** HOLE CARDS ***
Dealt to Hero [Ah Kh]
Vilao: folds
Uncalled bet (0) returned to Hero
*** SHOW DOWN ***
Hero: shows [Ah Kh]
Hero collected 400 from pot
*** SUMMARY ***
Total pot 400
Seat 1: Hero showed [Ah Kh] and won (400)
Seat 2: Vilao folded before Flop
"""
    replay = _replay_de(raw_gg, 'Hero')
    sd = next((f for f in replay['timeline'] if f['type'] == 'showdown'), None)
    assert sd, 'GGPoker sem "with" nao gerou conclusao'
    assert sd['summary']['winners'][0]['player'] == 'Hero'
    assert sd['summary']['winners'][0]['won'] == 400


def test_coinpoker_ganhou_preflop_sem_board_e_sem_descricao():
    """Achado no mesmo sweep: 'Board [  ]' (preflop, sem carta nenhuma) + 'showed [...] and won
    (X)' sem descricao. As duas ausencias juntas nao podem derrubar a conclusao."""
    raw_coin = """CoinPoker Hand #1: NLH (10/20) 2026/07/01
Tournament '1' '1' 6-max Seat #1 is the button
Seat 1: Hero (2000 in chips)
Seat 2: Vilao (2000 in chips)
Hero: posts small blind 10
Vilao: posts big blind 20
*** HOLE CARDS ***
Dealt to Hero [Ac 6s]
Vilao: folds
Uncalled bet (10) returned to Hero
Hero collected 40 from pot
*** SUMMARY ***
Total pot 40
Board [  ]
Seat 1: Hero showed [Ac 6s] and won (40)
Seat 2: Vilao folded before Flop
"""
    replay = _replay_de(raw_coin, 'Hero')
    sd = next((f for f in replay['timeline'] if f['type'] == 'showdown'), None)
    assert sd, 'CoinPoker sem board + sem descricao nao gerou conclusao'
    assert sd['summary']['winners'][0]['player'] == 'Hero'


def test_antes_e_blinds_da_ACR_aparecem_no_frame_inicial():
    """Reportado pelo usuario: "eu estou no BB e nao apareceu; a SB so apareceu depois que o D
    pagou". Medido numa mao 3-handed da ACR: o frame inicial vinha com pot=0, blinds_total=0 e
    ZERO fichas em todos os assentos. As unicas fichas na mesa eram das ACOES, entao o pote
    parecia nascer do nada e o blind do hero nunca era desenhado.

    Causa: os regexes exigiam DOIS-PONTOS ("Hero: posts the ante 40"), e a ACR escreve sem ":"
    e sem o "the" no ante ("Hero posts ante 40.00"). Nada era capturado.
    """
    replay = _replay_de(_MAO_ACR_ALLIN_TURN, 'MusashiBR')
    f0 = replay['timeline'][0]
    assert f0['antes_total'] == 1200, f0.get('antes_total')      # 8 x 150
    assert f0['blinds_total'] == 2250, f0.get('blinds_total')    # 750 + 1500
    assert f0['pot'] == 3450, f0['pot']
    # A ficha do blind fica no assento CERTO: 2 = SB (750), 3 = BB (1500).
    posicoes = {s: v['pos'] for s, v in f0['seats'].items()}
    sb = next(s for s, p in posicoes.items() if p == 'SB')
    bb = next(s for s, p in posicoes.items() if p == 'BB')
    assert f0['bets'][sb] == 750, (sb, f0['bets'])
    assert f0['bets'][bb] == 1500, (bb, f0['bets'])
    # e ninguem mais tem ficha na mesa antes de qualquer acao
    assert sum(v for k, v in f0['bets'].items() if k not in (sb, bb)) == 0, f0['bets']


def test_o_dialeto_com_dois_pontos_continua_funcionando():
    """Regressao: PokerStars/GG usam "Hero: posts the ante 40" (com dois-pontos, sem centavos)."""
    raw_ps = """PokerStars Hand #1: Tournament #1, $1.00+$0.10 USD Hold'em No Limit - Level I (10/20) - 2026/07/01 0:00:00 ET
Table '1' 6-max Seat #1 is the button
Seat 1: Botao (2000 in chips)
Seat 2: Peq (2000 in chips)
Seat 3: Grande (2000 in chips)
Botao: posts the ante 5
Peq: posts the ante 5
Grande: posts the ante 5
Peq: posts small blind 10
Grande: posts big blind 20
*** HOLE CARDS ***
Dealt to Grande [Ah Kh]
Botao: folds
Peq: folds
Uncalled bet (10) returned to Grande
Grande collected 45 from pot
*** SUMMARY ***
Total pot 45
Seat 1: Botao (button) folded before Flop
Seat 2: Peq (small blind) folded before Flop
Seat 3: Grande (big blind) collected (45)
"""
    f0 = _replay_de(raw_ps, 'Grande')['timeline'][0]
    assert f0['antes_total'] == 15, f0.get('antes_total')
    assert f0['blinds_total'] == 30, f0.get('blinds_total')
    posicoes = {s: v['pos'] for s, v in f0['seats'].items()}
    sb = next(s for s, p in posicoes.items() if p == 'SB')
    bb = next(s for s, p in posicoes.items() if p == 'BB')
    assert f0['bets'][sb] == 10 and f0['bets'][bb] == 20, f0['bets']


def test_formato_pokerstars_com_parenteses_continua_funcionando():
    """Regressao: o formato antigo (valor entre parenteses, sem centavos) nao pode quebrar."""
    from api.app import _build_replay_data as _brd
    # Reusa a mesma funcao _parse_summary indiretamente: monta uma mini SUMMARY no estilo PS.
    raw_ps = _MAO_ACR_ALLIN_TURN.replace(
        'Seat 1: MusashiBR (button) showed [9d Ac] and won 70490.00 with a pair of Aces [Ad Ac Ks 9d 5h] with the kicker Nine',
        'Seat 1: MusashiBR (button) showed [9d Ac] and won (70,490) with a pair of Aces')
    replay = _replay_de(raw_ps, 'MusashiBR')
    sd = next((f for f in replay['timeline'] if f['type'] == 'showdown'), None)
    assert sd, 'formato PokerStars (parenteses) parou de funcionar'
    assert sd['summary']['winners'][0]['won'] == 70490, sd['summary']['winners']


if __name__ == '__main__':
    falhas = 0
    testes = (test_o_board_final_tem_as_5_cartas,
              test_a_rua_sem_acao_ganha_o_proprio_frame,
              test_o_frame_de_conclusao_existe_e_revela_as_DUAS_maos,
              test_vitoria_sem_showdown_tambem_conclui,
              test_ggpoker_showed_e_won_SEM_a_descricao_da_mao,
              test_coinpoker_ganhou_preflop_sem_board_e_sem_descricao,
              test_antes_e_blinds_da_ACR_aparecem_no_frame_inicial,
              test_o_dialeto_com_dois_pontos_continua_funcionando,
              test_formato_pokerstars_com_parenteses_continua_funcionando)
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
