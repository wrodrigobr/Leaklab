# -*- coding: utf-8 -*-
"""
Deteccao de MESA FINAL — a prova que autoriza ICM real.

── O que o usuario reportou ───────────────────────────────────────────────────────────────────────

Numa mao com 3 sentados: "certeza que e mesa final, pois so temos 3 jogadores na mesa. Identificou
erro no meu raise, mas estou com um stack muito maior que os adversarios, eu nao deveria
explora-los?"

Medido: o gate de ICM real era `field_size <= 9`. Num MTT o `field_size` e o total de INSCRITOS e
nao muda nunca — 500 inscritos continuam 500 na mesa final. Ou seja, **o gate nunca abria numa
mesa final de MTT**, exatamente onde ICM domina a decisao. So funcionava em torneio de mesa unica.

── O que este arquivo trava ───────────────────────────────────────────────────────────────────────

1. Que a prova por COLOCACOES abra o gate numa mesa final de MTT (o caso do usuario).
2. Que ela NAO abra numa mesa qualquer de MTT em andamento — que foi o bug ANTERIOR: contar
   assentos dava "mesa final" em toda mao de um MTT 9-max, e a equity de premiacao era calculada
   tratando 8 stacks como o torneio inteiro.
3. Que a prova falhe FECHADA com dado incompleto. Ligar ICM real com equity errada e pior do que
   nao ligar, porque o bucket heuristico continua valendo e nao afirma nada falso.
4. Que a leitura de assento seja a MESMA em todos os dialetos (PS/GG/ACR/888). Ela ja existiu em
   tres copias, e a copia do `mtt_context` exigia "in chips" — que a ACR nao escreve.
"""
import os, sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from leaklab.mesa_final import mesa_e_o_torneio, nomes_sentados, MAX_NA_MESA


# ── A prova posicional ─────────────────────────────────────────────────────────────────────────

def test_mesa_final_de_MTT_com_3_sentados():
    """O caso exato do usuario: MTT grande, 3 sentados, e as colocacoes deles sao 1, 2 e 3.
    Ninguem pode ter colocacao maior que 3 porque quem tem ja saiu."""
    ok, motivo = mesa_e_o_torneio(
        {'MusashiBR', 'Chucksayer', 'AOTApoker410'},
        field_size=180,   # 180 inscritos: o gate ANTIGO recusaria
        colocacoes={'MusashiBR': 1, 'Chucksayer': 3, 'AOTApoker410': 2,
                    'quem_saiu_antes': 4, 'outro': 57})
    assert ok is True, motivo
    assert motivo == 'colocacoes'


def test_mesa_final_cheia_de_9():
    """Mesa final comecando com 9 sentados: colocacoes 1..9, ninguem acima."""
    nomes = {f'p{i}' for i in range(1, 10)}
    col = {f'p{i}': i for i in range(1, 10)}
    col.update({f'saiu{i}': i for i in range(10, 300)})
    ok, motivo = mesa_e_o_torneio(nomes, field_size=299, colocacoes=col)
    assert ok is True and motivo == 'colocacoes'


def test_mesa_qualquer_de_MTT_em_andamento_NAO_abre():
    """O bug ANTERIOR. Nivel 3 de blinds, 9 sentados, centenas vivos — alguem nesta mesa vai
    terminar em 137o lugar, e isso prova que a mesa nao e o torneio."""
    nomes = {f'p{i}' for i in range(1, 10)}
    col = {f'p{i}': i * 15 for i in range(1, 10)}     # 15, 30, ... 135
    ok, motivo = mesa_e_o_torneio(nomes, field_size=300, colocacoes=col)
    assert ok is False, motivo
    assert motivo == 'colocacoes_indicam_mtt_em_andamento'


def test_uma_colocacao_a_mais_que_o_numero_de_sentados_derruba():
    """Fronteira exata: 3 sentados com colocacoes 1, 2 e 4. O 4 significa que existe alguem em
    3o lugar que ainda esta vivo em OUTRA mesa. Um off-by-one aqui ligaria ICM na mesa errada."""
    ok, motivo = mesa_e_o_torneio({'a', 'b', 'c'}, field_size=90,
                                  colocacoes={'a': 1, 'b': 2, 'c': 4})
    assert ok is False and motivo == 'colocacoes_indicam_mtt_em_andamento'


# ── Falhar fechado ─────────────────────────────────────────────────────────────────────────────

def test_nome_sem_colocacao_conhecida_nao_prova_nada():
    """Se nao sei onde um dos sentados terminou, nao sei se alguem ficou acima de N. Cai para o
    critério de mesa unica — e aqui nem esse existe, entao recusa.

    Falhar ABERTO aqui e o padrao que este projeto ja pagou caro: no backfill de EV eu chamei o
    guarda sem o parametro de equity, o teto de plausibilidade devolveu None, e 439 decisoes
    receberam EV impossivel (a pior: perda de 41604bb num stack de 11,7bb)."""
    ok, motivo = mesa_e_o_torneio({'a', 'b', 'desconhecido'}, field_size=180,
                                  colocacoes={'a': 1, 'b': 2})
    assert ok is False, motivo
    assert motivo == 'sem_prova'


def test_sem_resumo_nao_afirma():
    """Sem nenhuma das duas provas o ICM real fica desligado. E o estado da maioria dos torneios:
    medido em producao em 2026-07-29, 19 de 76 tinham resumo enviado."""
    assert mesa_e_o_torneio({'a', 'b', 'c'}) == (False, 'sem_prova')


def test_mesa_maior_que_9_nunca_e_mesa():
    """Acima da capacidade de uma mesa nao e mesa, e sinal de leitura errada do roster."""
    nomes = {f'p{i}' for i in range(1, 12)}
    ok, motivo = mesa_e_o_torneio(nomes, colocacoes={f'p{i}': i for i in range(1, 12)})
    assert ok is False and motivo == 'mesa_grande_demais'


def test_heads_up_e_mesa_mas_um_jogador_nao():
    assert mesa_e_o_torneio({'a', 'b'}, colocacoes={'a': 1, 'b': 2})[0] is True
    assert mesa_e_o_torneio({'a'}, colocacoes={'a': 1}) == (False, 'sem_mesa')
    assert mesa_e_o_torneio(set()) == (False, 'sem_mesa')


# ── O critério antigo continua valendo ─────────────────────────────────────────────────────────

def test_mesa_unica_continua_abrindo_sem_colocacoes():
    """SnG de 9: `field_size` prova que a mesa e o torneio do comeco ao fim. Nao pode ter sido
    perdido no caminho — era o unico gate que existia."""
    assert mesa_e_o_torneio({f'p{i}' for i in range(9)}, field_size=9)[1] == 'mesa_unica'
    assert mesa_e_o_torneio({'a', 'b'}, field_size=2)[0] is True


def test_colocacoes_tem_precedencia_sobre_field_size():
    """Com as duas provas presentes, a posicional decide: ela e especifica DA MAO, o field_size
    fala do torneio. Um SnG de 9 na bolha (3 sentados de 9 inscritos, colocacoes 1-2-3) e mesa
    final tanto por um critério quanto pelo outro, mas o motivo reportado tem que ser o forte."""
    ok, motivo = mesa_e_o_torneio({'a', 'b', 'c'}, field_size=9,
                                  colocacoes={'a': 1, 'b': 2, 'c': 3})
    assert ok is True and motivo == 'colocacoes'


# ── Leitura de assento: um dialeto de cada ─────────────────────────────────────────────────────

def test_le_assento_nos_quatro_dialetos():
    """Esta funcao ja existiu em tres copias. A do `mtt_context` exigia "in chips", que a ACR nao
    escreve — a contagem de jogadores ativos so nao zerava porque caia, por coincidencia de
    formato, no fallback do dialeto 888."""
    ps = "Seat 1: alfa (1500 in chips)\nSeat 2: bravo (1500 in chips)"
    acr = "Seat 1: Chucksayer (35500.00)\nSeat 2: MusashiBR (343270.00)"
    p888 = "Seat 1: Mr.Tatt00 ( $3,548 )\nSeat 5: DiggErr555 ( $4,886 )"
    assert nomes_sentados(ps) == {'alfa', 'bravo'}
    assert nomes_sentados(acr) == {'Chucksayer', 'MusashiBR'}
    assert nomes_sentados(p888) == {'Mr.Tatt00', 'DiggErr555'}


def test_nao_conta_as_linhas_de_summary():
    """"Seat 1: alfa (button) collected (50)" nao e um jogador chamado
    "alfa (button) collected". Era exatamente o que acontecia, e inflava um SnG de 9 para 30
    nomes — entao TODO SnG virava "MTT" no nome do torneio."""
    raw = ("PokerStars Hand #1: Tournament #900\n"
           "Seat 1: alfa (1500 in chips)\n"
           "Seat 2: bravo (1500 in chips)\n"
           "*** SUMMARY ***\n"
           "Seat 1: alfa (button) collected (50)\n"
           "Seat 2: bravo (small blind) folded before Flop\n")
    assert nomes_sentados(raw) == {'alfa', 'bravo'}


# ── Integracao: o gate do mtt_context de fato liga ─────────────────────────────────────────────

_MAO_MESA_FINAL = """Game Hand #77 - Tournament #55 - Holdem (No Limit) - Level 9 (2500.00/5000.00) - 2026/07/29 21:29:23 UTC
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
MusashiBR raises 12500.00 to 12500.00
Chucksayer folds
AOTApoker410 folds
"""


def _ctx(colocacoes):
    from leaklab.parser import parse_hand_history
    from leaklab.mtt_context import build_mtt_context
    maos = parse_hand_history(_MAO_MESA_FINAL)
    assert maos, 'a mao de fixture tem que parsear'
    return build_mtt_context(maos[0], field_size=180, colocacoes=colocacoes)


def test_ICM_real_LIGA_na_mesa_final_de_MTT():
    """Ponta a ponta: 180 inscritos (o gate antigo recusaria) e ICM real sai com numero."""
    c = _ctx({'MusashiBR': 1, 'Chucksayer': 3, 'AOTApoker410': 2})
    assert c.active_players == 3, c.active_players
    assert c.icm_equity_pct is not None, 'ICM real nao ligou na mesa final'
    # O hero tem 343k de 460k em fichas (74,6%) mas ICM taxa isso: equity de premiacao MENOR que
    # a de fichas e o efeito que faz mesa final ser jogada diferente.
    assert c.icm_chip_pct > c.icm_equity_pct, (c.icm_chip_pct, c.icm_equity_pct)


def test_ICM_real_NAO_liga_sem_as_colocacoes():
    """Mesma mao, sem resumo: recusa. Prova que quem abriu o gate foram as colocacoes, e nao a
    contagem de 3 assentos — que e o bug anterior."""
    c = _ctx(None)
    assert c.active_players == 3
    assert c.icm_equity_pct is None, 'ligou ICM real sem prova nenhuma'


def test_ICM_real_NAO_liga_com_colocacoes_de_MTT_em_andamento():
    c = _ctx({'MusashiBR': 12, 'Chucksayer': 40, 'AOTApoker410': 91})
    assert c.icm_equity_pct is None, 'ligou ICM real numa mesa qualquer de MTT'


# ── Dados reais: o torneio que o usuario reportou ──────────────────────────────────────────────
#
# ACR #35598158, 29 inscritos, hero campeao, 101 maos do hero. As colocacoes vem do resumo de
# verdade (parse_acr_results). Medido em 2026-07-29: 48 das 101 maos sao mesa final, a deteccao
# liga na mao 53 com 8 assentos e NUNCA desliga (zero oscilacoes).
_COL_35598158 = {
    'MusashiBR': 1, 'JAMESHARPER': 2, 'Yachtman': 3, 'MoneyFunnel': 4, '66spade': 5,
    'AOTApoker410': 6, 'Chucksayer': 7, 'reyvinzon': 8, 'Naroko349': 9, 'Bitemee126': 10,
    'Hendo92': 11, 'TheFifthJack': 12, 'jippy': 13,
}


def test_tres_assentos_pode_ser_ou_nao_ser_mesa_final_no_MESMO_torneio():
    """O caso que derruba a intuicao "3 sentados logo e mesa final" — e ela era a do usuario, e
    tambem a do gate antigo que contava assentos.

    Duas maos REAIS do torneio 35598158, ambas com 3 sentados, uma de cada lado:

      2789054332 (mao 55 de 101): MoneyFunnel(4), Chucksayer(7), MusashiBR(1) — maior colocacao 7,
                                  entao ao menos 7 pessoas estavam vivas. Mesa curta por quebra de
                                  mesa, NAO mesa final.
      2789067545 (mao 90 de 101): MusashiBR(1), JAMESHARPER(2), Yachtman(3) — maior colocacao 3.
                                  Mesa final de verdade.

    Nenhuma contagem de assentos separa essas duas. A colocacao separa.
    """
    curta = mesa_e_o_torneio({'MoneyFunnel', 'Chucksayer', 'MusashiBR'},
                             field_size=29, colocacoes=_COL_35598158)
    final = mesa_e_o_torneio({'MusashiBR', 'JAMESHARPER', 'Yachtman'},
                             field_size=29, colocacoes=_COL_35598158)
    assert curta == (False, 'colocacoes_indicam_mtt_em_andamento'), curta
    assert final == (True, 'colocacoes'), final


def test_reentrada_usa_a_MELHOR_colocacao():
    """Bug meu, e do tipo que falha calado. Re-entrada da ao jogador DUAS colocacoes: no
    35598158 real, Yachtman aparece como 3o (a re-entrada, onde ele parou) E como 25o (a primeira
    entrada, que quebrou). A primeira versao de `save_tournament_finishes` guardava a linha que
    aparecesse primeiro — dependia da ordem do arquivo, guardou o 25o, e a mesa final de 3 era
    RECUSADA. Nenhum erro na tela, so o veredito errado.

    Aritmeticamente: a colocacao que conta e onde a PESSOA saiu, que e a menor.
    """
    from database.repositories import save_tournament_finishes, get_tournament_finishes
    from database.schema import init_db
    init_db()
    tid = 987654
    # ordem invertida de proposito: a linha do 25o vem ANTES da do 3o
    save_tournament_finishes(tid, [
        {'player': 'Yachtman', 'place': 25, 'prize': 0.0},
        {'player': 'Yachtman', 'place': 3,  'prize': 2.17},
        {'player': 'MusashiBR', 'place': 1, 'prize': 4.8},
        {'player': 'JAMESHARPER', 'place': 2, 'prize': 2.9},
    ])
    col = get_tournament_finishes(tid)
    assert col.get('Yachtman') == 3, col
    assert mesa_e_o_torneio({'MusashiBR', 'JAMESHARPER', 'Yachtman'},
                            field_size=29, colocacoes=col) == (True, 'colocacoes')


def test_linha_sem_colocacao_e_descartada_e_nao_gravada_com_place_nulo():
    """Uma linha com place NULL nao prova nada e faria a regra falhar ABERTO (o `all(...)` veria
    um valor presente que na verdade e vazio)."""
    from database.repositories import save_tournament_finishes, get_tournament_finishes
    from database.schema import init_db
    init_db()
    tid = 987655
    n = save_tournament_finishes(tid, [{'player': 'a', 'place': 1},
                                       {'player': 'sem_place', 'place': None},
                                       {'player': '', 'place': 5}])
    assert n == 1, n
    assert get_tournament_finishes(tid) == {'a': 1}


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
