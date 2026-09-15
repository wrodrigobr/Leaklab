# -*- coding: utf-8 -*-
"""A copy que lista salas lista as salas que o parser reconhece, nem uma menos nem uma mais.

-- O defeito (auditoria FLU-8, 15/09) ------------------------------------------------------

`faq.a1` (landing) e `steps.upload.desc` (onboarding) diziam "PokerStars, GGPoker, ACR (WPN) e
CoinPoker" nas tres locales, enquanto `subtitle`, `howItWorks.step1Desc` e o `empty.desc` do
dashboard ja citavam PartyPoker, que esta LIGADO no parser desde a validacao contra o export
real de um fundador (3.482 maos, 36 torneios). Quem joga PartyPoker, que e o caso do fundador,
lia no FAQ que a sala dele nao e suportada.

-- O que este arquivo defende --------------------------------------------------------------

A lista de salas nao e DECLARADA em lugar nenhum: este teste pergunta ao `_detect_site` do
parser, sala por sala, com o cabecalho de cada dialeto. Depois varre TODA string de i18n que
cita duas ou mais salas (e portanto e uma lista de salas) e exige que ela cite exatamente as
reconhecidas. Duas direcoes:

  * faltar sala LIGADA e o defeito do FLU-8 (a copy nega uma sala que funciona);
  * sobrar sala DESLIGADA e pior, porque promete o que nao entrega. O 888poker esta desligado
    de proposito (falta arquivo real de export) e por isso nao pode aparecer na copy.

O criterio "2+ salas = lista de salas" acha a chave nova sozinho, sem lista de arquivos para
manter: hoje sao 18 strings (6 chaves x 3 locales). Cada chave declara de QUE capacidade ela
fala, porque as duas nao tem a mesma lista: hand history sao 5 salas, e Tournament Summary sao
2 (so existem `parse_pokerstars_summary` e `parse_ggpoker_summary`). Chave nova que a varredura
ache e que nao esteja declarada FALHA o teste, para que a escolha seja consciente. Foi assim que
o `summary.hint` apareceu no meio deste conserto, e ele estava certo.
"""
import json
import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

RAIZ = os.path.join(os.path.dirname(__file__), '..')
LOCALES_DIR = os.path.abspath(os.path.join(RAIZ, '..', 'frontend', 'src', 'i18n', 'locales'))

# Cabecalho minimo de cada dialeto e o nome pelo qual a copy chama a sala.
CABECALHOS = {
    'pokerstars': ('PokerStars Hand #1: Tournament #1', 'PokerStars'),
    'ggpoker':    ('Poker Hand #TM1: Tournament #1', 'GGPoker'),
    'acr':        ('Game Hand #1 - Tournament #1', 'ACR'),
    'coinpoker':  ('CoinPoker Hand #1 - Tournament', 'CoinPoker'),
    'partypoker': ('***** Hand History For Game 1 *****', 'PartyPoker'),
    '888poker':   ('***** 888poker Hand History for Game 1 *****', '888poker'),
}
TODOS_OS_NOMES = {nome for _h, nome in CABECALHOS.values()}

#: De que capacidade cada chave de copy fala. `hand_history` = o arquivo de maos, que o
#: `_detect_site` reconhece; `tournament_summary` = o resumo do torneio, que tem parser proprio
#: e so para duas salas. Chave nova sem declaracao falha o teste, de proposito.
CAPACIDADE_POR_CHAVE = {
    'dashboard.json:empty.desc':            'hand_history',
    'landing.json:networks.subtitle':       'hand_history',
    'landing.json:howItWorks.step1Desc':    'hand_history',
    'landing.json:faq.a1':                  'hand_history',
    'onboarding.json:steps.upload.desc':    'hand_history',
    'tournaments.json:summary.hint':        'tournament_summary',
}


def salas_reconhecidas():
    """{nome_na_copy: o parser reconhece?} — perguntado ao `_detect_site`, nao declarado."""
    from leaklab.parser import _detect_site
    return {nome: _detect_site(cab) == site for site, (cab, nome) in CABECALHOS.items()}


def salas_com_parser_de_summary():
    """As salas com parser de Tournament Summary — pela EXISTENCIA da funcao, nao por lista."""
    import leaklab.parser as P
    return {nome for site, (_cab, nome) in CABECALHOS.items()
            if hasattr(P, 'parse_%s_summary' % site)}


def _achatar(d, prefixo=''):
    for k, v in (d or {}).items():
        chave = '%s.%s' % (prefixo, k) if prefixo else k
        if isinstance(v, dict):
            for par in _achatar(v, chave):
                yield par
        elif isinstance(v, str):
            yield chave, v


def listas_de_sala(raiz, nomes=TODOS_OS_NOMES):
    """[(locale, arquivo, chave, salas_citadas)] de toda copy que cita 2+ salas."""
    out = []
    if not os.path.isdir(raiz):
        return out
    for loc in sorted(os.listdir(raiz)):
        pasta = os.path.join(raiz, loc)
        if not os.path.isdir(pasta):
            continue
        for arq in sorted(os.listdir(pasta)):
            if not arq.endswith('.json'):
                continue
            with open(os.path.join(pasta, arq), encoding='utf-8') as f:
                d = json.load(f)
            for chave, texto in _achatar(d):
                citadas = {n for n in nomes if re.search(re.escape(n), texto, re.IGNORECASE)}
                if len(citadas) >= 2:
                    out.append((loc, arq, chave, citadas))
    return out


def test_o_parser_reconhece_as_cinco_salas_e_nao_o_888():
    """O que a copy pode prometer. 888 fica de fora ate existir um export real."""
    r = salas_reconhecidas()
    assert r == {'PokerStars': True, 'GGPoker': True, 'ACR': True, 'CoinPoker': True,
                 'PartyPoker': True, '888poker': False}, r


def test_so_pokerstars_e_ggpoker_tem_parser_de_tournament_summary():
    assert salas_com_parser_de_summary() == {'PokerStars', 'GGPoker'},         salas_com_parser_de_summary()


def test_toda_copy_que_lista_sala_lista_as_reconhecidas():
    esperado = {
        'hand_history':       {n for n, ok in salas_reconhecidas().items() if ok},
        'tournament_summary': salas_com_parser_de_summary(),
    }
    listas = listas_de_sala(LOCALES_DIR)
    assert len(listas) >= 15, 'a varredura achou %d listas de sala: o criterio mudou?' % len(listas)
    problemas = []
    for loc, arq, chave, citadas in listas:
        cap = CAPACIDADE_POR_CHAVE.get('%s:%s' % (arq, chave))
        if cap is None:
            problemas.append((loc, arq, chave, 'chave NAO DECLARADA em CAPACIDADE_POR_CHAVE'))
            continue
        falta = sorted(esperado[cap] - citadas)
        sobra = sorted(citadas - esperado[cap])
        if falta or sobra:
            problemas.append((loc, arq, chave, cap, 'falta=%s' % falta, 'sobra=%s' % sobra))
    assert not problemas, 'copy em desacordo com o parser: %s' % problemas


def test_a_varredura_acha_os_casos_forjados(tmp=None):
    """Regra 1: o medidor tem de se mexer nos dois sentidos."""
    import tempfile
    base = tempfile.mkdtemp()
    loc = os.path.join(base, 'pt-BR')
    os.makedirs(loc)

    def _escreve(conteudo):
        with open(os.path.join(loc, 'landing.json'), 'w', encoding='utf-8') as f:
            json.dump(conteudo, f)

    # a copy de ANTES do conserto: sem PartyPoker
    _escreve({'faq': {'a1': 'PokerStars, GGPoker, ACR (WPN) e CoinPoker, pelo arquivo .txt'}})
    achadas = listas_de_sala(base)
    assert len(achadas) == 1 and achadas[0][2] == 'faq.a1', achadas
    assert 'PartyPoker' not in achadas[0][3]

    # a copy consertada
    _escreve({'faq': {'a1': 'PokerStars, GGPoker, ACR (WPN), CoinPoker e PartyPoker, pelo .txt'}})
    assert listas_de_sala(base)[0][3] == {'PokerStars', 'GGPoker', 'ACR', 'CoinPoker',
                                          'PartyPoker'}

    # promessa a mais: sala DESLIGADA na copy
    _escreve({'faq': {'a1': 'PokerStars, GGPoker, ACR, CoinPoker, PartyPoker e 888poker'}})
    assert '888poker' in listas_de_sala(base)[0][3]

    # uma sala sozinha nao e lista de salas
    _escreve({'faq': {'a1': 'Exporte do PokerStars o arquivo .txt'}})
    assert listas_de_sala(base) == []


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
