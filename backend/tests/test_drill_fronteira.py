"""
O treino tem que servir a FRONTEIRA da range, não o miolo óbvio.

── Por que isto existe ───────────────────────────────────────────────────────────────────────

O sorteio de mãos era uniforme (`rng.shuffle(_HANDS)`), então a maior parte das perguntas era
trivial: foldar 32o de UTG não ensina nada, consome uma pergunta e ainda paga XP. Medido antes
da mudança, a amostra vinha assim: `UTG 77`, `UTG+2 ATs`, `LJ AJo` — aberturas óbvias.

O que ensina é a borda, e ela tem duas formas:

  · o GTO MISTURA na mão (ação dominante abaixo de 90%) — não existe resposta única ali;
  · a mão MUDA DE LADO entre assentos vizinhos (abre do CO, não do UTG) — é o "quase", e é
    exatamente o que precisa ser memorizado.

Isto é medido nas ranges reais capturadas: de UTG para HJ entram 16 mãos suited contra 9
offsuit; de HJ para BTN, 19 contra 17. A borda é onde o range cresce.

── O que este arquivo trava ──────────────────────────────────────────────────────────────────

Que o viés EXISTA e seja forte (a maioria das perguntas vem da borda), e que ele não vire
filtro absoluto — o jogador precisa de algumas fáceis para calibrar a régua e não desistir.
"""
import os, random, sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from leaklab.leak_trainer import (fundamentals_catalog, generate_canonical_spot,
                                  e_mao_de_fronteira, _COTA_FRONTEIRA)


def _amostra(n=150, semente=7):
    cats = fundamentals_catalog('rfi', 50)
    rng = random.Random(semente)
    spots = []
    for _ in range(n):
        s = generate_canonical_spot(rng.choice(cats), rng)
        if s:
            spots.append(s)
    return spots


def test_a_maioria_das_perguntas_vem_da_borda():
    spots = _amostra()
    assert len(spots) > 100, f'geração produziu poucos spots ({len(spots)})'
    borda = sum(1 for s in spots if s.get('fronteira'))
    frac = borda / len(spots)
    # Piso bem abaixo da cota para não quebrar por variação de amostra; o que importa é que o
    # viés EXISTA. Antes da mudança media 39% — e uma versão intermediária, com um `continue`
    # condicionado errado, media exatamente isso e parecia funcionar.
    assert frac >= 0.55, (
        f'só {frac:.0%} das perguntas vêm da borda (cota é {_COTA_FRONTEIRA:.0%}). '
        'O viés não está sendo aplicado.')
    print(f'OK  test_a_maioria_das_perguntas_vem_da_borda ({frac:.0%} de borda)')


def test_ainda_serve_algumas_faceis():
    """Cem por cento de borda seria treino brutal e sem calibragem."""
    spots = _amostra()
    faceis = sum(1 for s in spots if not s.get('fronteira'))
    assert faceis > 0, 'nenhuma pergunta fácil — o viés virou filtro absoluto'
    print(f'OK  test_ainda_serve_algumas_faceis ({faceis} de {len(spots)})')


def test_classificador_reconhece_mao_mista():
    """Estratégia mista é borda por definição: o próprio GTO não tem resposta única."""
    assert e_mao_de_fronteira('CO', 'K9o', 50.0, {'raise': 0.55, 'fold': 0.45}) is True
    assert e_mao_de_fronteira('CO', 'K9o', 50.0, {'raise': 0.5}) is True
    print('OK  test_classificador_reconhece_mao_mista')


def test_todo_spot_declara_se_e_borda():
    """`fronteira` no payload é o que permite MEDIR o viés depois. Sem ele, a mudança seria
    inverificável em produção — e este projeto já pagou caro por número que ninguém confere."""
    for s in _amostra(n=30):
        assert 'fronteira' in s, f'spot sem o campo `fronteira`: {s.get("hand")}'
        assert isinstance(s['fronteira'], bool)
    print('OK  test_todo_spot_declara_se_e_borda')


def test_nunca_devolve_None_por_falta_de_borda():
    """Se as 40 mãos sorteadas não tiverem nenhuma de borda, serve a reserva. Spot fácil é melhor
    que spot nenhum — e devolver None aqui deixaria o jogador com a tela vazia."""
    cats = fundamentals_catalog('rfi', 50)
    rng = random.Random(99)
    vazios = sum(1 for _ in range(60) if generate_canonical_spot(rng.choice(cats), rng) is None)
    assert vazios == 0, f'{vazios} categorias devolveram None'
    print('OK  test_nunca_devolve_None_por_falta_de_borda')


if __name__ == '__main__':
    falhas = 0
    testes = (test_a_maioria_das_perguntas_vem_da_borda, test_ainda_serve_algumas_faceis,
              test_classificador_reconhece_mao_mista, test_todo_spot_declara_se_e_borda,
              test_nunca_devolve_None_por_falta_de_borda)
    for t in testes:
        try:
            t()
        except AssertionError as e:
            falhas += 1
            print(f'FALHOU  {t.__name__}: {e}')
    print(f'\nTotal: {len(testes)} | Passed: {len(testes) - falhas} | Failed: {falhas}')
    sys.exit(1 if falhas else 0)
