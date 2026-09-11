# -*- coding: utf-8 -*-
"""O nome do heroi vem da mao que TEM nome, nao da primeira (11/09).

── O que originou ─────────────────────────────────────────────────────────────────────────

Medindo por que 470 torneios do acervo estao sem colocacao, achei 21 em que o banco guardou o
literal `'Hero'` enquanto o arquivo trazia o nome real em centenas de maos. No torneio 242:
"Michel Diens" em 266 das 274 maos, e a primeira mao — a unica que o codigo olhava — nao tinha a
linha `Dealt to` (jogador sentado fora, ou export comecando no meio).

A causa era `hands[0].hero or 'Hero'`, copiado em quatro lugares do `app.py`.

O que isso arrastava: colocacao e premio saem de linhas que comecam com o NOME do jogador
(`<nome> finished the tournament in Nth place`), entao nome errado = torneio sem resultado. O HUD
de oponente e o alias do GG tambem usam o heroi. As DECISOES nao eram afetadas: ali o motor usa o
heroi POR MAO, e o nome esta certo.

── O que este arquivo defende ─────────────────────────────────────────────────────────────

1. o nome vem da mao que tem nome, e o MAIS FREQUENTE ganha (arquivo com maos de dois jogadores
   responde pelo dono, que e quem aparece mais);
2. nenhuma mao com nome devolve 'Hero', e isso NAO e falha: CoinPoker (97 torneios) e GGPoker
   (25) escrevem 'Hero' no proprio arquivo;
3. **ponta a ponta**: arquivo cuja primeira mao nao tem `Dealt to` grava o nome real E extrai a
   colocacao, que era o dano de verdade;
4. **a varredura dos N+1** (regra 5): a regra vive num lugar so, e nenhum ponto do `app.py`
   voltou a decidir o heroi de nivel de torneio por conta propria.
"""
import io
import os
import re
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
_TMPDB = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
_TMPDB.close()
os.environ['LEAKLAB_DB'] = _TMPDB.name
os.environ.pop('DATABASE_URL', None)

from leaklab.parser import heroi_das_maos, parse_hand_history                  # noqa: E402


class _Mao:
    def __init__(self, hero):
        self.hero = hero


#: Duas maos do MESMO torneio. Na primeira o heroi esta sentado fora (sem `Dealt to`), e e ela
#: que o codigo antigo olhava. Na segunda ele joga, busta, e o PokerStars escreve a colocacao.
_ARQUIVO = """PokerStars Hand #261000000001: Tournament #4099999999, $0.90+$0.10 USD Hold'em No Limit - Level I (10/20) - 2026/09/01 20:10:00 ET
Table '4099999999 3' 8-max Seat #2 is the button
Seat 1: MichelDiens (1500 in chips) out of hand (moved from another table into small blind)
Seat 2: vilao_um (1500 in chips)
Seat 3: vilao_dois (1500 in chips)
vilao_um: posts small blind 10
vilao_dois: posts big blind 20
*** HOLE CARDS ***
vilao_um: folds
Uncalled bet (10) returned to vilao_dois
vilao_dois collected 20 from pot
*** SUMMARY ***
Total pot 20 | Rake 0
Seat 2: vilao_um (button) (small blind) folded before Flop
Seat 3: vilao_dois (big blind) collected (20)

PokerStars Hand #261000000002: Tournament #4099999999, $0.90+$0.10 USD Hold'em No Limit - Level I (10/20) - 2026/09/01 20:12:00 ET
Table '4099999999 3' 8-max Seat #1 is the button
Seat 1: MichelDiens (1500 in chips)
Seat 2: vilao_um (1500 in chips)
Seat 3: vilao_dois (3000 in chips)
MichelDiens: posts small blind 10
vilao_um: posts big blind 20
*** HOLE CARDS ***
Dealt to MichelDiens [Ah Kd]
vilao_dois: raises 1480 to 1500 and is all-in
MichelDiens: calls 1490 and is all-in
vilao_um: folds
*** FLOP *** [2c 7d 9s]
*** TURN *** [2c 7d 9s] [3h]
*** RIVER *** [2c 7d 9s 3h] [4c]
*** SHOW DOWN ***
vilao_dois: shows [Qs Qh] (a pair of Queens)
MichelDiens: shows [Ah Kd] (high card Ace)
vilao_dois collected 3020 from pot
MichelDiens finished the tournament in 5th place and received $1.10.
*** SUMMARY ***
Total pot 3020 | Rake 0
Board [2c 7d 9s 3h 4c]
Seat 1: MichelDiens (button) (small blind) showed [Ah Kd] and lost with high card Ace
Seat 3: vilao_dois showed [Qs Qh] and won (3020) with a pair of Queens
"""


def test_o_nome_vem_da_mao_que_TEM_nome_e_o_mais_frequente_ganha():
    assert heroi_das_maos([_Mao(None), _Mao('Michel Diens'), _Mao('Michel Diens')]) == 'Michel Diens'
    # arquivo com maos de dois jogadores: responde pelo DONO, que aparece mais
    assert heroi_das_maos([_Mao('A'), _Mao('B'), _Mao('B')]) == 'B'
    # espaco em branco nao e nome
    assert heroi_das_maos([_Mao('  '), _Mao(None)]) == 'Hero'
    # nenhuma mao: nao explode
    assert heroi_das_maos([]) == 'Hero'
    assert heroi_das_maos(None) == 'Hero'


def test_sala_que_anonimiza_continua_Hero():
    """CoinPoker (97 torneios do acervo) e GGPoker (25) escrevem 'Hero' no arquivo. Ali 'Hero' e
    a resposta CERTA, e trocar por outra coisa seria inventar um nome que a sala nao deu."""
    assert heroi_das_maos([_Mao('Hero'), _Mao('Hero')]) == 'Hero'


def test_ponta_a_ponta_a_primeira_mao_sem_Dealt_to_nao_perde_o_nome_nem_a_colocacao():
    """O dano de verdade: nome errado = torneio sem colocacao, porque a linha do resultado comeca
    com o NOME do jogador. A primeira mao deste arquivo tem o heroi `out of hand` (sem
    `Dealt to`), que e exatamente o caso dos 21 torneios achados em 11/09."""
    maos = parse_hand_history(_ARQUIVO)
    assert len(maos) == 2, len(maos)
    assert getattr(maos[0], 'hero', None) in (None, ''), 'a 1a mao nao deveria ter heroi'
    assert maos[1].hero == 'MichelDiens', maos[1].hero
    # a regra antiga (`maos[0].hero or 'Hero'`) daria 'Hero'; a nova acha o nome
    assert heroi_das_maos(maos) == 'MichelDiens', heroi_das_maos(maos)

    # e com o nome certo a colocacao sai do proprio arquivo
    from api.app import _extract_financials
    raw = '\n'.join(m.raw_text for m in maos if hasattr(m, 'raw_text'))
    fin_certo = _extract_financials(raw, heroi_das_maos(maos), 'pokerstars', None)
    assert fin_certo['place'] == 5, fin_certo
    assert fin_certo['prize'] == 1.10, fin_certo
    # com o nome errado, o MESMO arquivo nao devolve colocacao nenhuma — era o bug
    fin_errado = _extract_financials(raw, 'Hero', 'pokerstars', None)
    assert fin_errado['place'] is None, ('com o nome errado nao ha colocacao', fin_errado)


def test_a_regra_do_heroi_do_TORNEIO_vive_num_lugar_so():
    """Regra 5 do CLAUDE.md: a regra estava copiada em quatro lugares do `app.py` e foi por isso
    que ninguem notou. A varredura tem de PROVAR que varreu — falha se nao achar nenhuma chamada,
    o que significaria que a sonda parou de medir."""
    raiz = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
    app = io.open(os.path.join(raiz, 'api', 'app.py'), encoding='utf-8').read()
    # TRES lugares de nivel de torneio (analise, re-analise e o payload do replay). O quarto
    # ponto que decide heroi no `app.py` e POR MAO e fica de fora de proposito: ali o heroi e o
    # daquela mao, nao o do arquivo.
    chamadas = len(re.findall(r'heroi_das_maos\(', app))
    assert chamadas >= 3, ('a sonda nao achou as chamadas: ou o nome mudou, ou a regra voltou a '
                           'ser copiada', chamadas)
    # nenhum lugar decide o heroi do TORNEIO por conta propria
    copias = re.findall(r'hands\[0\]\.hero', app)
    assert not copias, ('a regra voltou a ser copiada em %d lugar(es)' % len(copias))
    # o heroi POR MAO segue existindo, e e legitimo (o motor precisa do heroi daquela mao)
    assert re.search(r'hand\.hero or ', app), 'o heroi por mao desapareceu: isto nao era o bug'


if __name__ == '__main__':
    falhas = 0
    testes = [v for k, v in sorted(globals().items()) if k.startswith('test_')]
    for t in testes:
        try:
            t()
            print('OK  %s' % t.__name__)
        except AssertionError as e:
            falhas += 1
            print('FALHOU  %s: %s' % (t.__name__, e))
        except Exception as e:                                  # noqa: BLE001
            falhas += 1
            print('ERRO    %s: %s: %s' % (t.__name__, type(e).__name__, e))
    print('\nTotal: %d | Passed: %d | Failed: %d' % (len(testes), len(testes) - falhas, falhas))
    sys.exit(1 if falhas else 0)
