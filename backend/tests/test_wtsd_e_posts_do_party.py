# -*- coding: utf-8 -*-
"""Os dois defeitos que o dono viu na TELA depois do primeiro torneio do Party (11/09).

Nenhum dos dois apareceu na minha validacao, e a razao e a mesma: eu provei parser, pipeline e
motor, e paramos ali. **Compatibilizar uma sala nao termina no motor** — termina nas stats e no
replayer, que e onde o jogador olha.

── 1. "meu wtsd esta zerado, achei estranho" ──────────────────────────────────────────────

`wtsd` e `w_at_sd` saem os dois de `decisions.showdown_result`. O construtor de `ParsedHand` do
caminho PokerStars sempre preencheu esse campo; **o construtor do caminho PartyGaming nunca
passou por ele.** Campo que existe num caminho e nao no outro: a mesma forma da cicatriz do
`reveals=` (ver `test_reveals_do_summary`), e a razao de haver um guarda de fiacao aqui.

Alem disso, o Party nao tem a secao `Seat N: ... showed [..]` que o extrator conhecia. O
resultado mora na linha de balance do summary:

    Player1 balance 1187071, bet 448615, collected 937230, net +488615[ As, Kh ] [ a pair ... ]
    Hero balance 0, lost 448615[ Qh, Ad ] [ a pair of tens -- ... ]
    Player3 balance 658443, lost 28000 (folded)          <- nao foi ao showdown

A CARTA REVELADA e o sinal de showdown, e isso foi medido, nao suposto: no arquivo real, 1.024
maos tem linha de revelacao e **todas as 1.024 tem duas ou mais**. Zero maos com uma revelacao
so. Se a sala revelasse o heroi em pote levado sem oposicao (como o CoinPoker faz, a cicatriz do
`_SD_COM_MAO_RE`), existiriam maos com exatamente uma. Nao existe nenhuma.

Depois do conserto, no arquivo real do dono: 266 showdowns do heroi (163 ganhos, 103 perdidos),
**batendo na unidade** com as 266 linhas de revelacao do Hero contadas no texto cru. WTSD 39,8%,
W$SD 61,3%.

── 2. "no replayer nao existe o post das blinds, as antes tambem nao aparecem" ────────────

O endpoint de replay nao usava o parser: ele RECONSTRUIA antes e blinds do `raw_text` com duas
regexes proprias, que esperavam o valor cru (`posts ante 40.00`) ou entre colchetes. O dialeto
novo do Party escreve `posts ante (3000)`, entre PARENTESES — nenhuma linha casava, e a mesa
aparecia sem ante, sem blind e com o pote comecando em zero.

Regra 5 pela terceira vez no mesmo dia: a mesma pergunta lida em dois lugares, e so um aprendeu
o dialeto. Agora ha uma funcao (`posts_da_mao`) e este arquivo varre OS SEIS formatos que
existem no acervo, um por fixture.

Quebrados de proposito (11/09): sem o `showdown_result=` no construtor do Party, o guarda de
fiacao e o de showdown acusam; trocando `[^\\d]*` por um espaco em `_POSTS_RE`, a varredura dos
dialetos acusa nomeando o arquivo.
"""
import io
import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from leaklab.parser import (_extract_showdown_result, parse_hand_history,   # noqa: E402
                            posts_da_mao)

_FIX = os.path.join(os.path.dirname(__file__), 'fixtures')


def _load(nome):
    return io.open(os.path.join(_FIX, nome), encoding='utf-8').read()


# ── 1. showdown ────────────────────────────────────────────────────────────────────────────

def test_o_showdown_do_dialeto_novo_sai_da_linha_de_balance():
    """Os dois resultados, e o None de quem nao foi. So 'won' passaria com um bug que
    devolvesse 'won' sempre — por isso a 5a mao da fixture existe."""
    maos = parse_hand_history(_load('partypoker_mtt_novo.txt'))
    assert [m.showdown_result for m in maos] == [None, None, 'won', None, 'lost'], \
        [m.showdown_result for m in maos]


def test_quem_foldou_no_summary_do_party_NAO_conta_showdown():
    """`Player3 balance 658443, lost 28000 (folded)` tem "lost" e NAO e showdown: sem carta
    revelada ninguem chegou la. Contar isso encheria o denominador do W$SD com fold."""
    corpo = ('** Summary **\n'
             'Main Pot: 300 \n'
             'Hero balance 350, lost 150 (folded)\n'
             'Player2 balance 650, bet 150, collected 300, net +150[ Ts, 4c ] [ a flush ... ]\n')
    assert _extract_showdown_result(corpo, 'Hero') is None


def test_o_vencedor_do_party_e_lido_pelo_collected():
    """Controle: a MESMA linha, trocando quem e o heroi, tem de dar os dois resultados."""
    corpo = ('** Summary **\n'
             'Hero balance 0, lost 448615[ Qh, Ad ] [ a pair of tens -- ... ]\n'
             'Player1 balance 1187071, bet 448615, collected 937230, net +488615[ As, Kh ] [ ... ]\n')
    assert _extract_showdown_result(corpo, 'Hero') == 'lost'
    assert _extract_showdown_result(corpo, 'Player1') == 'won'


def test_todo_construtor_de_ParsedHand_preenche_showdown_result():
    """FIACAO, ancorada na CONDICAO. O campo existia no construtor do PokerStars e faltava no do
    PartyGaming, e foi assim que o WTSD do dono zerou. O guarda nao conta ocorrencias de texto:
    exige que TODA chamada a `ParsedHand(` no parser traga `showdown_result=`."""
    caminho = os.path.join(os.path.dirname(__file__), '..', 'leaklab', 'parser.py')
    src = io.open(caminho, encoding='utf-8').read()
    blocos = src.split('ParsedHand(')[1:]
    assert len(blocos) >= 2, ('menos de 2 construtores de ParsedHand: a varredura nao varre '
                              'o que deveria (%d)' % len(blocos))
    sem = [i for i, b in enumerate(blocos) if 'showdown_result=' not in b.split('\n    )')[0]]
    assert not sem, ('construtor(es) de ParsedHand sem showdown_result (indice a partir de 0)',
                     sem)


def test_o_wtsd_do_party_nao_e_zero_no_arquivo_real_do_dono():
    """O numero na TELA e o que estava errado, entao o guarda mede o numero. Roda so quando o
    arquivo do dono esta no disco; a fixture cobre o caso em qualquer maquina."""
    caminho = r'C:\HH Testes\20260803-20260910_ddamataa.txt'
    if not os.path.exists(caminho):
        print('SKIP test_o_wtsd_do_party_nao_e_zero_no_arquivo_real_do_dono (arquivo ausente)')
        return
    raw = io.open(caminho, encoding='utf-8', errors='replace').read()
    maos = parse_hand_history(raw)
    sd = [m.showdown_result for m in maos if m.showdown_result]
    # CONTROLE: o numero tem de bater com a contagem crua de revelacoes do Hero no texto. Sem
    # este par, um extrator que inventasse showdown passaria com qualquer numero > 0.
    cru = len(re.findall(r'^Hero balance .*?\[\s*[2-9TJQKA][cdhs]', raw, re.M))
    assert len(sd) == cru == 266, (len(sd), cru)
    assert sd.count('won') == 163 and sd.count('lost') == 103, (sd.count('won'), sd.count('lost'))


# ── 2. antes e blinds postados ─────────────────────────────────────────────────────────────

#: Um por FORMATO de valor que existe no acervo. A varredura dos N+1 do `posts`: a regex do
#: replay conhecia quatro destes seis, e as duas que faltavam eram as do Party novo.
_DIALETOS = [
    ('revalidation_mini.txt',       'PokerStars/GG, com ":" e valor cru'),
    ('partypoker_tourney_mtt.txt',  'Party/888 antigo, colchetes'),
    ('pp888_cash_6max.txt',         '888 cash, colchetes com $'),
    ('partypoker_cash_9max.txt',    'Party cash, colchetes com $ e USD, ponto final'),
    ('partypoker_tourney_stt.txt',  'Party STT, parenteses'),
    ('partypoker_mtt_novo.txt',     'Party novo, parenteses (o que quebrou o replayer)'),
]


def test_os_seis_dialetos_de_post_sao_lidos():
    """Todo arquivo do acervo produz blind postado com valor > 0. Blind com valor zero e pior
    que blind ausente: o pote do replay comeca errado e ninguem ve o defeito."""
    ruins = []
    for nome, apelido in _DIALETOS:
        p = posts_da_mao(_load(nome))
        if not p['blinds'] or any(not b['amount'] for b in p['blinds']):
            ruins.append((nome, apelido, len(p['blinds'])))
    assert not ruins, ('dialeto de post sem blind lido', ruins)


def test_o_ante_do_party_novo_entra_com_o_valor_entre_parenteses():
    """`Hero posts ante (3000)`. O dono mandou o trecho do historico dele: seis antes de 440 e
    small/big de 1750/3500. A forma e esta, e era a que nao casava."""
    trecho = ('Seat 6: Hero (77660)\n'
              'Player1 posts ante (440)\n'
              'Hero posts ante (440)\n'
              'Hero posts small blind (1750)\n'
              'Player1 posts big blind (3500)\n')
    p = posts_da_mao(trecho)
    assert [a['amount'] for a in p['antes']] == [440.0, 440.0], p['antes']
    assert p['blinds'] == [{'player': 'Hero', 'amount': 1750.0, 'type': 'small'},
                           {'player': 'Player1', 'amount': 3500.0, 'type': 'big'}], p['blinds']


def test_o_centavo_do_cash_nao_e_zerado():
    """O replay fazia `int(float(...))` e um blind de 0,10 virava 0. Nao era o bug do dono, mas
    estava no mesmo bloco e sai junto."""
    p = posts_da_mao(_load('partypoker_cash_9max.txt'))
    assert any(0 < b['amount'] < 1 for b in p['blinds']), \
        ('nenhum blind fracionario lido no cash', [b['amount'] for b in p['blinds']][:5])


def test_o_replay_usa_a_funcao_unica_e_nao_a_sua_propria_regex():
    """FIACAO. O defeito nao era o parser: era o replay ter regex propria. Se alguem reescrever
    uma ali, o dialeto seguinte quebra do mesmo jeito e o guarda de cima nem sente."""
    caminho = os.path.join(os.path.dirname(__file__), '..', 'api', 'app.py')
    src = io.open(caminho, encoding='utf-8').read()
    assert 'posts_da_mao(' in src, 'o replay parou de usar a funcao unica de posts'
    propria = re.findall(r"re\.compile\([^)]*posts[^)]*\)", src, re.IGNORECASE)
    assert not propria, ('regex de `posts` propria em app.py: use `posts_da_mao`', propria)


if __name__ == '__main__':
    falhas = 0
    testes = [v for k, v in sorted(globals().items()) if k.startswith('test_')]
    for t in testes:
        try:
            t()
            print('OK      %s' % t.__name__)
        except AssertionError as e:
            falhas += 1
            print('FALHOU  %s: %s' % (t.__name__, e))
        except Exception as e:
            falhas += 1
            print('ERRO    %s: %s: %s' % (t.__name__, type(e).__name__, e))
    print('\nTotal: %d | Passed: %d | Failed: %d' % (len(testes), len(testes) - falhas, falhas))
    sys.exit(1 if falhas else 0)
