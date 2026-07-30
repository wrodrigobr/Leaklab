"""
Jogadores do roster: a base para distinguir SNG de MTT e para detectar mesa final.

── O bug reportado ────────────────────────────────────────────────────────────────────────────

Usuario: "os nomes dos torneios ficam como MTT $1.00 mesmo para um Sit and Go de 9 jogadores".

Causa medida: a contagem de jogadores unicos usava `^Seat \\d+: (.+?) \\(` sobre o arquivo INTEIRO,
e isso casa as linhas de `*** SUMMARY ***` tambem. O PokerStars escreve

    Seat 4: phpro (small blind) collected (1500)

e um regex que aceite "(numero)" no fim casa o VALOR COLETADO, devolvendo o "nome"
"phpro (small blind) collected". O mesmo jogador era contado varias vezes: num SnG de 9 reais,
a leitura devolvia 27 a 30 nomes, entao TODO SnG estourava o limite de 9 e virava "MTT".

Medido em producao depois do conserto: roster bate exatamente com o field_size do resumo em
todos os torneios de mesa unica (9=9, 6=6, 3=3), e o MTT de 29 inscritos da 22 nomes (jogadores
que passaram pela mesa do hero).

── Por que um regex mais esperto nao resolveria ────────────────────────────────────────────────

Foi a primeira tentativa e falhou: exigir "in chips" quebra a ACR (que escreve "(29150.00)"), e
aceitar decimais casa o "collected (1500)". O corte tem que ser ESTRUTURAL — pular a secao de
summary — que e o mesmo critario que `_build_replay_data` ja usava ao ler o roster de uma mao.
"""
import os, sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from api.app import jogadores_do_roster, _extract_tournament_name


# SnG de 3 maos com 9 jogadores. As linhas de SUMMARY repetem os nomes com sufixo de resultado —
# e a armadilha que inflava a contagem.
_SNG_9 = """PokerStars Hand #1: Tournament #900, $0.98+$0.12 USD Hold'em No Limit - Level I (10/20) - 2026/07/01 0:00:00 ET
Table '900 1' 9-max Seat #1 is the button
Seat 1: alfa (1500 in chips)
Seat 2: bravo (1500 in chips)
Seat 3: charlie (1500 in chips)
Seat 4: delta (1500 in chips)
Seat 5: echo (1500 in chips)
Seat 6: foxtrot (1500 in chips)
Seat 7: golf (1500 in chips)
Seat 8: hotel (1500 in chips)
Seat 9: india (1500 in chips)
bravo: posts small blind 10
charlie: posts big blind 20
*** HOLE CARDS ***
Dealt to alfa [Ah Kh]
delta: folds
alfa: raises 40 to 60
bravo: folds
charlie: folds
Uncalled bet (40) returned to alfa
alfa collected 50 from pot
*** SUMMARY ***
Total pot 50 | Rake 0
Seat 1: alfa (button) collected (50)
Seat 2: bravo (small blind) folded before Flop
Seat 3: charlie (big blind) folded before Flop
Seat 4: delta folded before Flop and did not bet

PokerStars Hand #2: Tournament #900, $0.98+$0.12 USD Hold'em No Limit - Level I (10/20) - 2026/07/01 0:05:00 ET
Table '900 1' 9-max Seat #2 is the button
Seat 1: alfa (1550 in chips)
Seat 2: bravo (1490 in chips)
Seat 3: charlie (1480 in chips)
Seat 4: delta (1500 in chips)
Seat 5: echo (1500 in chips)
Seat 6: foxtrot (1500 in chips)
Seat 7: golf (1500 in chips)
Seat 8: hotel (1500 in chips)
Seat 9: india (1500 in chips)
charlie: posts small blind 10
delta: posts big blind 20
*** HOLE CARDS ***
Dealt to alfa [2c 7d]
alfa: folds
charlie: folds
delta collected 30 from pot
*** SUMMARY ***
Total pot 30 | Rake 0
Seat 3: charlie (small blind) folded before Flop
Seat 4: delta (big blind) collected (30)
"""

# ACR: roster sem "in chips", stack decimal.
_ACR_3 = """Game Hand #77 - Tournament #55 - Holdem (No Limit) - Level 9 (2500.00/5000.00) - 2026/07/29 21:29:23 UTC
Table '4' 9-max Seat #3 is the button
Seat 1: Chucksayer (35500.00)
Seat 2: AOTApoker410 (80920.00)
Seat 3: MusashiBR (343270.00)
Chucksayer posts ante 500.00
AOTApoker410 posts ante 500.00
MusashiBR posts ante 500.00
Chucksayer posts the small blind 2500.00
AOTApoker410 posts the big blind 5000.00
*** HOLE CARDS ***
Dealt to MusashiBR [7d 5h]
MusashiBR calls 5000.00
Chucksayer folds
AOTApoker410 checks
*** SUMMARY ***
Total pot 12500.00
Seat 1: Chucksayer (small blind) folded on the Pre-Flop
Seat 2: AOTApoker410 (big blind) did not show and won 12500.00
Seat 3: MusashiBR (button) folded on the Flop
"""


def test_conta_so_o_roster_e_nao_as_linhas_de_summary():
    """O caso exato do bug: 9 jogadores de verdade, mas o SUMMARY repete nomes com sufixo."""
    nomes = jogadores_do_roster(_SNG_9)
    assert nomes == {'alfa', 'bravo', 'charlie', 'delta', 'echo',
                     'foxtrot', 'golf', 'hotel', 'india'}, sorted(nomes)


def test_nao_inventa_jogador_a_partir_do_valor_coletado():
    """'Seat 1: alfa (button) collected (50)' nao pode virar o jogador
    'alfa (button) collected' — era exatamente o que acontecia."""
    nomes = jogadores_do_roster(_SNG_9)
    assert not any('collected' in n or 'folded' in n or 'blind)' in n for n in nomes), sorted(nomes)


def test_le_o_roster_da_ACR_sem_in_chips():
    """A ACR escreve '(29150.00)' em vez de '(1500 in chips)'. Exigir 'in chips' quebraria ela —
    foi a primeira tentativa de conserto e falhou."""
    assert jogadores_do_roster(_ACR_3) == {'Chucksayer', 'AOTApoker410', 'MusashiBR'}


def test_le_o_roster_do_888_com_espacos_e_cifrao():
    """O 888/PartyPoker escreve "Seat 1: Mr.Tatt00 ( $3,548 )": espaco interno E cifrao. A
    primeira versao deste conserto exigia digito logo apos o "(" e QUEBROU a suite do 888 (o
    unico teste que cobre esse dialeto). Fica travado aqui tambem."""
    raw_888 = """***** 888poker Hand History for Game 1 *****
$20 + $2 USD Sit and Go
Table 1 9 Max (Real Money)
Seat 5 is the button
Total number of players : 3
Seat 1: Mr.Tatt00 ( $3,548 )
Seat 5: bilguun0226 ( $1,614 )
Seat 7: DiggErr555 ( $4,886 )
"""
    assert jogadores_do_roster(raw_888) == {'Mr.Tatt00', 'bilguun0226', 'DiggErr555'}


def test_SNG_de_9_nao_e_rotulado_MTT():
    """O sintoma que o usuario viu na lista de torneios."""
    assert _extract_tournament_name(_SNG_9, 'pokerstars', 1.10) == 'SNG $1.10'


def test_MTT_continua_MTT():
    """Mais de 9 nomes distintos no roster = jogadores chegaram de outras mesas."""
    extra = _SNG_9 + """
PokerStars Hand #3: Tournament #900, $0.98+$0.12 USD Hold'em No Limit - Level II (15/30) - 2026/07/01 0:10:00 ET
Table '900 1' 9-max Seat #1 is the button
Seat 1: alfa (1550 in chips)
Seat 2: novato_um (3000 in chips)
Seat 3: novato_dois (2500 in chips)
*** HOLE CARDS ***
Dealt to alfa [Ah Kh]
alfa: folds
"""
    nomes = jogadores_do_roster(extra)
    assert 'novato_um' in nomes and len(nomes) == 11, sorted(nomes)
    assert _extract_tournament_name(extra, 'pokerstars', 1.10) == 'MTT $1.10'


def test_sem_roster_reconhecido_nao_afirma_formato():
    """Nome errado e pior que nome genérico: o usuario usa isso pra achar o torneio na lista."""
    assert _extract_tournament_name('lixo sem assentos', 'pokerstars', 1.10) is None


if __name__ == '__main__':
    falhas = 0
    testes = (test_conta_so_o_roster_e_nao_as_linhas_de_summary,
              test_nao_inventa_jogador_a_partir_do_valor_coletado,
              test_le_o_roster_da_ACR_sem_in_chips,
              test_le_o_roster_do_888_com_espacos_e_cifrao,
              test_SNG_de_9_nao_e_rotulado_MTT,
              test_MTT_continua_MTT,
              test_sem_roster_reconhecido_nao_afirma_formato)
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
