# -*- coding: utf-8 -*-
"""O plano de captura de mesa cheia leva ao herói que promete.

── Por que isto e teste, e nao conferencia no olho ────────────────────────────────────────────

Cada linha do plano e uma sequencia de intencoes que atravessa os outros jogadores
(`fold, fold, fold, fold, raise_min, fold, raise_min` = CO abre, SB da squeeze, BB decide). Um
fold a mais ou a menos captura o no do VIZINHO — e o no viria valido, so que do jogador errado.
Carta certa sob rotulo errado nao se denuncia depois: ela gradua, e gradua mal.

O custo de errar aqui e alto e assimetrico: cada no-alvo consome ate 8 requisicoes de uma cota
diaria que nao se recupera. Descobrir o engano depois da captura significa perder o dia.
"""
import io
import json
import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from leaklab.preflop_gto_ranges import _ORDEM_RING

_PLANO = os.path.join(os.path.dirname(__file__), '..', 'docs', 'gw_plano_ring.json')


def _aonde_leva(linha, mesa=8):
    """(heroi, agressores) da linha — ou (None, ...) se ela passar da primeira orbita."""
    ordem = _ORDEM_RING[mesa]
    agressores = [ordem[i] for i, d in enumerate(linha) if i < len(ordem) and d.startswith('raise')]
    heroi = ordem[len(linha)] if len(linha) < len(ordem) else None
    return heroi, agressores


def _conferencia(blocos, mesa=8):
    """Lista de (rotulo, problema). Vazia = plano consistente."""
    problemas = []
    for b in blocos:
        rot = b.get('_alvo', '?')
        m = re.match(r'^(\S+) vs (?:squeeze do |3-bet do )(\S+)', rot)
        if not m:
            problemas.append((rot, 'rotulo nao diz hero e vilao'))
            continue
        for linha in b['linhas']:
            heroi, agressores = _aonde_leva(linha, mesa)
            if heroi is None:
                problemas.append((rot, f'linha de {len(linha)} acoes passa da primeira orbita'))
            elif len(agressores) != 2:
                problemas.append((rot, f'{len(agressores)} agressores, esperado 2'))
            elif heroi != m.group(1) or agressores[-1] != m.group(2):
                problemas.append((rot, f'leva a {heroi} vs {agressores[-1]}'))
    return problemas


def test_toda_linha_leva_ao_heroi_prometido():
    plano = json.load(io.open(_PLANO, encoding='utf-8'))
    problemas = _conferencia(plano['blocos'])
    assert not problemas, problemas


def test_a_conferencia_pega_linha_torta():
    """CONTROLE do proprio verificador. Um teste que so viu plano correto nao prova que
    discrimina — foi assim que dois testes meus passaram cegos hoje."""
    bom = [{'_alvo': 'BB vs squeeze do SB (CO abre)',
            'linhas': [['fold', 'fold', 'fold', 'fold', 'raise_min', 'fold', 'raise_min']]}]
    assert _conferencia(bom) == []

    # um fold A MAIS: a linha passa do BB e sai da primeira orbita
    demais = [{'_alvo': 'BB vs squeeze do SB (CO abre)',
               'linhas': [['fold'] * 5 + ['raise_min', 'fold', 'raise_min']]}]
    assert _conferencia(demais), 'aceitou linha longa demais'

    # um fold A MENOS: quem decide passa a ser o SB, nao o BB
    demenos = [{'_alvo': 'BB vs squeeze do SB (CO abre)',
                'linhas': [['fold', 'fold', 'fold', 'raise_min', 'fold', 'raise_min']]}]
    p = _conferencia(demenos)
    assert p and 'leva a SB' in p[0][1], p

    # so um agressor: nao e squeeze nenhum
    um_so = [{'_alvo': 'BB vs squeeze do SB (CO abre)',
              'linhas': [['fold'] * 6 + ['raise_min']]}]
    assert _conferencia(um_so), 'aceitou linha com um agressor so'


def test_profundidades_sao_do_menu_do_estudo():
    """Depth que o estudo nao oferece vira requisicao invalida — e requisicao invalida gasta cota
    igual. O menu foi lido do HAR de mesa cheia de 06/08."""
    menu = {12.125, 14.125, 19.125, 20.125, 22.125, 28.125, 30.125, 40.125, 50.125, 60.125,
            80.125, 100.125}
    plano = json.load(io.open(_PLANO, encoding='utf-8'))
    fora = [(b['_alvo'][:30], d) for b in plano['blocos'] for d in b['depths'] if d not in menu]
    assert not fora, fora


def test_o_plano_declara_saida_separada_do_hu():
    """No de 8-max no acervo de HU seria a carta de mesa cheia gradeando heads-up — o defeito que
    originou toda esta frente."""
    plano = json.load(io.open(_PLANO, encoding='utf-8'))
    assert plano['saida'] == 'docs/ring_ranges_har.json', plano.get('saida')
    assert 'hu_ranges' not in plano['saida']


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
