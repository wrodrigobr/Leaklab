# -*- coding: utf-8 -*-
"""Quando a mão foi jogada: uma função, os quatro formatos do acervo (13/09).

── O que estava acontecendo ───────────────────────────────────────────────────────────────────

A regra "quando esta mão foi jogada" vivia em DOIS lugares, cada um com uma lista PARCIAL de
formatos, e ninguém tinha visto porque cada um errava num dialeto diferente:

    `_extract_date` (api/app.py)        nao conhecia o PartyPoker NOVO
    `_HAND_TS_RE`   (leaklab/parser.py) nao conhecia nem o Party nem o 888

Medido em producao:

    played_at nulo:     5 de 5 registros do partypoker (100%)  |  0 nas outras 4 salas
    started_at nulo:    5 de 5 do partypoker                   |  0 nas outras

O `played_at` e o eixo de tempo do produto (AY-4): sem ele o torneio fica fora de todo filtro
por periodo, do relatorio de evolucao e da projecao de carreira. Achado ao reparar a conta do
dono, cujo unico registro multi-torneio era do Party — os quatro registros novos nasceriam sem
data, e eu ia culpar o meu script de reparo.

── Os quatro formatos, todos presentes nos fixtures ───────────────────────────────────────────

    2026/05/22 18:00:00                     PokerStars, GGPoker, ACR, CoinPoker
    Thu Sep 10 18:54:46 EDT 2026            PartyPoker NOVO (mes abreviado, sem virgula)
    Sunday, July 24, 19:32:00 CEST 2016     PartyPoker antigo (mes por nome, com virgula)
    *** 08 08 2016 23:03:27                 888poker (DD MM YYYY)

── Porque a tabela abaixo tem os valores de ANTES ─────────────────────────────────────────────

Porque a correcao mexe no parser, que todo upload usa, e o risco nao e "nao consertar o Party" —
e QUEBRAR as outras quatro salas. A tabela e a baseline colhida antes da mudanca, e o teste exige
que nenhuma linha PERCA o que ja tinha. A primeira versao da minha correcao fazia exatamente
isso: os tres fixtures antigos do Party perderam a data, e eu so soube porque comparei.
"""
import io
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from leaklab.parser import (timestamps_das_maos, extract_session_times,      # noqa: E402
                            _TS_PARTY_ABREV_RE)

_FIX = os.path.join(os.path.dirname(__file__), 'fixtures')

# fixture -> (data esperada, tem janela de sessao?)
# A data e a BASELINE de antes da correcao onde ja existia; onde era None, o valor novo.
ESPERADO = {
    'partypoker_cash_9max.txt':   ('2018-06-19', True),
    'partypoker_mtt_novo.txt':    ('2026-08-03', True),     # era None: o formato novo
    'partypoker_tourney_mtt.txt': ('2016-09-26', True),
    'partypoker_tourney_stt.txt': ('2016-07-24', True),
    'pp888_cash_6max.txt':        ('2018-06-21', True),
    'pp888_tourney.txt':          ('2016-08-08', True),
    'pp888_tourney_summary.txt':  ('2022-02-14', True),
    'revalidation_mini.txt':      ('2026-05-22', True),
}


def _ler(nome):
    return io.open(os.path.join(_FIX, nome), encoding='utf-8', errors='replace').read()


def _data(texto):
    from api.app import _extract_date
    return _extract_date(texto)


def test_a_tabela_cobre_TODO_fixture_de_hand_history():
    """Guarda da varredura (regra 5): fixture novo no acervo entra na tabela, ou o teste avisa.

    Sem isto, um dialeto novo chegaria sem ninguem conferir a data dele — que foi exatamente
    como o PartyPoker entrou."""
    no_disco = {n for n in os.listdir(_FIX) if n.endswith('.txt')}
    faltando = no_disco - set(ESPERADO)
    assert faltando == set(), (
        'fixture de hand history fora da tabela de datas: %s' % sorted(faltando))
    sobrando = set(ESPERADO) - no_disco
    assert sobrando == set(), ('a tabela cita fixture que nao existe: %s' % sorted(sobrando))


def test_todo_dialeto_declara_a_data_do_jogo():
    for nome, (data, _) in sorted(ESPERADO.items()):
        achada = _data(_ler(nome))
        assert achada == data, ('%s: data %r, esperada %r' % (nome, achada, data))


def test_todo_dialeto_declara_a_JANELA_da_sessao():
    """`started_at`/`ended_at` alimentam concorrencia, fadiga e horario. Antes da correcao eles
    existiam SO para o dialeto PokerStars — 7 dos 8 fixtures davam (None, None)."""
    for nome, (_, tem) in sorted(ESPERADO.items()):
        ini, fim = extract_session_times(_ler(nome))
        if not tem:
            continue
        assert ini and fim, ('%s: sem janela de sessao (%r, %r)' % (nome, ini, fim))
        assert ini <= fim, ('%s: inicio depois do fim (%r > %r)' % (nome, ini, fim))
        # e a janela tem de conter a data do torneio
        assert ini[:10] == _data(_ler(nome)), (
            '%s: a sessao comeca em %s mas a data do torneio e %s' % (nome, ini[:10],
                                                                      _data(_ler(nome))))


def test_a_data_e_a_da_mao_mais_ANTIGA_do_arquivo():
    """Um arquivo pode ter as mãos em qualquer ordem (e o do PartyPoker tem: o export e por
    intervalo de datas). A data do torneio e a da primeira mao NO TEMPO, nao a primeira que
    aparece no texto."""
    texto = _ler('partypoker_mtt_novo.txt')
    ts = timestamps_das_maos(texto)
    assert len(ts) >= 2, ts
    assert _data(texto) == min(ts)[:10], (_data(texto), sorted(ts))
    # o fixture tem mao de data DIFERENTE da primeira do texto: e o que torna o teste valido
    assert min(ts)[:10] != max(ts)[:10], (
        'o fixture nao tem datas diferentes: este teste nao prova nada', sorted(ts)[:3])


def test_os_QUATRO_formatos_sao_lidos_isoladamente():
    """Cada formato numa linha so, sem depender de fixture: se um dialeto mudar de forma, aqui
    se ve qual."""
    casos = [
        ('2026/05/22 18:00:00',                    '2026-05-22 18:00:00', 'PokerStars/GG/ACR'),
        ('- Thu Sep 10 18:54:46 EDT 2026',         '2026-09-10 18:54:46', 'PartyPoker novo'),
        ('- Sunday, July 24, 19:32:00 CEST 2016',  '2016-07-24 19:32:00', 'PartyPoker antigo'),
        ('*** 08 08 2016 23:03:27',                '2016-08-08 23:03:27', '888poker'),
    ]
    for texto, esperado, quem in casos:
        ts = timestamps_das_maos(texto)
        assert esperado in ts, ('%s: %r nao produziu %r (produziu %r)' % (
            quem, texto, esperado, ts))


def test_o_888_e_DIA_mes_e_nao_mes_dia():
    """`*** 08 08 2016` e ambiguo de proposito no fixture; este caso desempata."""
    ts = timestamps_das_maos('*** 21 06 2018 19:41:18')
    assert ts == ['2018-06-21 19:41:18'], ('leu como mes/dia em vez de dia/mes: %r' % ts)


def test_texto_sem_data_devolve_vazio_e_nao_inventa():
    """Celula sem dado nunca vira valor: data inventada contamina todo calculo por periodo."""
    for entrada in ('', '   ', 'isto nao tem data nenhuma', None):
        assert timestamps_das_maos(entrada) == [], repr(entrada)
        assert extract_session_times(entrada) == (None, None), repr(entrada)


def test_o_padrao_do_party_nao_carrega_caractere_de_controle():
    """Cicatriz: a primeira versao deste regex comecava com o byte 0x08 (BACKSPACE) em vez de
    `\\b`, porque o `\\\\b` que eu escrevi virou o caractere literal no arquivo. O padrao exigia
    um backspace no texto, que nunca existe, e NENHUM formato do Party casava — inclusive os
    tres que funcionavam antes. Invisivel no `grep`, visivel no `repr`."""
    padrao = _TS_PARTY_ABREV_RE.pattern
    controle = sorted({hex(ord(c)) for c in padrao if ord(c) < 32})
    assert controle == [], ('o padrao tem caractere(s) de controle: %s em %r' % (
        controle, padrao[:50]))


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
