# -*- coding: utf-8 -*-
"""O recorte da carta que a landing renderiza tem que ser IGUAL à carta.

── Por que este guarda existe (28/08) ─────────────────────────────────────────────────────

`frontend/src/data/vitrineRange.ts` é um recorte do balde 20bb / CO / RFI, e o cabeçalho dele
afirmava:

    "Print raster envelhece calado quando a carta muda; isto nao."

Era falso. O arquivo é um literal colado à mão, sem gerador e sem ninguém conferindo: no dia em
que o balde de 20bb fosse reimportado, a landing seguiria mostrando a carta velha exatamente como
um `.webp` faria. Uma revisão apontou o comentário como a parte mais enganosa da entrega, e estava
certa — comentário não é evidência (regra 8 do CLAUDE.md).

Este teste é o que torna a frase verdadeira. Ele compara o recorte com a fonte e falha no dia em
que os dois divergirem, dizendo qual mão mudou.
"""
import io
import json
import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

_VITRINE = os.path.normpath(os.path.join(
    os.path.dirname(os.path.abspath(__file__)), '..', '..',
    'frontend', 'src', 'data', 'vitrineRange.ts'))

BALDE, POSICAO, SECAO = '20bb', 'CO', 'RFI'


def _do_arquivo():
    """Lê o FREQS do .ts. Sem parser de TS: o objeto é JSON puro entre `= ` e `;`."""
    fonte = io.open(_VITRINE, encoding='utf-8').read()
    m = re.search(r'const FREQS = (\{.*?\});', fonte, re.S)
    assert m, 'não achei o objeto FREQS em vitrineRange.ts'
    return json.loads(m.group(1))


def _da_carta():
    from leaklab.preflop_gto_ranges import _load
    spot = ((_load().get('ranges') or {}).get(BALDE) or {}).get(SECAO, {}).get(POSICAO) or {}
    hf = spot.get('hand_freqs') or {}
    fora = {}
    for mao, f in hf.items():
        raise_ = sum(v for k, v in f.items() if k.startswith('R') and k != 'RAI')
        d = {'raise': round(raise_, 4), 'allin': round(float(f.get('RAI', 0.0)), 4),
             'call': round(float(f.get('C', 0.0)), 4), 'fold': round(float(f.get('F', 0.0)), 4)}
        fora[mao] = {k: v for k, v in d.items() if v > 0}
    return fora


def test_a_carta_tem_o_spot_que_a_vitrine_recorta():
    """CONTROLE de base. Se o spot sumisse da carta, os testes abaixo comparariam dois vazios e
    passariam verde — o zero tranquilizador."""
    assert len(_da_carta()) > 50, (
        'o spot %s/%s/%s tem menos de 50 mãos na carta — a fonte mudou de forma'
        % (BALDE, SECAO, POSICAO))
    print('OK  test_a_carta_tem_o_spot_que_a_vitrine_recorta')


def test_o_recorte_da_landing_bate_com_a_carta():
    """O guarda que torna verdadeiro o comentário do arquivo."""
    arquivo, carta = _do_arquivo(), _da_carta()
    faltando = sorted(set(carta) - set(arquivo))
    sobrando = sorted(set(arquivo) - set(carta))
    assert not faltando, (
        'a carta ganhou mãos que a landing não mostra (%d): %s — rode '
        '`scripts/gerar_vitrine_range.py`' % (len(faltando), ', '.join(faltando[:8])))
    assert not sobrando, (
        'a landing mostra mãos que saíram da carta (%d): %s' % (len(sobrando), ', '.join(sobrando[:8])))
    difs = [m for m in carta if arquivo[m] != carta[m]]
    assert not difs, (
        'frequência divergente em %d mão(s): %s. Ex.: %s → landing %s, carta %s'
        % (len(difs), ', '.join(difs[:5]), difs[0], arquivo[difs[0]], carta[difs[0]]))
    print('OK  test_o_recorte_da_landing_bate_com_a_carta (%d mãos)' % len(carta))


def test_o_arquivo_declara_de_ONDE_veio():
    """Procedência no próprio arquivo: sem ela, quem for regerar não sabe qual spot recortar."""
    fonte = io.open(_VITRINE, encoding='utf-8').read()
    for pedaco in (BALDE, POSICAO, SECAO, 'preflop_gto_ranges'):
        assert pedaco in fonte, 'vitrineRange.ts não declara %r na procedência' % pedaco
    print('OK  test_o_arquivo_declara_de_ONDE_veio')


if __name__ == '__main__':
    falhas = 0
    testes = [v for k, v in sorted(globals().items()) if k.startswith('test_')]
    for teste in testes:
        try:
            teste()
        except AssertionError as e:
            falhas += 1
            print('FALHOU  %s: %s' % (teste.__name__, e))
        except Exception as e:                              # noqa: BLE001
            falhas += 1
            print('ERRO    %s: %s: %s' % (teste.__name__, type(e).__name__, e))
    print('\nTotal: %d | Passed: %d | Failed: %d' % (len(testes), len(testes) - falhas, falhas))
    sys.exit(1 if falhas else 0)
