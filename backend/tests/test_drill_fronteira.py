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


# ── Sondagem de range ─────────────────────────────────────────────────────────────────────────
#
# A sondagem AFIRMA um número ao jogador ("CO tem cerca de 40% das mãos"). Se o número estiver
# errado, ele é memorizado com confiança e aplicado na mesa — o pior tipo de dano deste produto.

def _spots(cenario, n=120, semente=5):
    cats = fundamentals_catalog(cenario, 50)
    rng = random.Random(semente)
    return [s for s in (generate_canonical_spot(rng.choice(cats), rng) for _ in range(n)) if s]


def test_sondagem_nunca_aparece_em_rfi():
    """Em `rfi` o herói age PRIMEIRO: não existe range de vilão para estimar. Servir a pergunta
    ali seria inventar uma sem resposta."""
    com = [s for s in _spots('rfi') if s.get('range_probe')]
    assert not com, f'{len(com)} spots de rfi vieram com sondagem'
    print('OK  test_sondagem_nunca_aparece_em_rfi')


def test_sondagem_aparece_onde_ha_vilao():
    spots = _spots('vs_rfi')
    com = [s for s in spots if s.get('range_probe')]
    assert com, 'nenhuma sondagem em vs_rfi — o recurso não está ativo'
    # É tempero, não prato: a maioria dos spots continua sendo a tela normal.
    assert len(com) < len(spots) * 0.7, 'sondagem em quase todo spot; era para ser minoria'
    print(f'OK  test_sondagem_aparece_onde_ha_vilao ({len(com)}/{len(spots)})')


def test_a_fatia_afirmada_bate_com_a_range_real():
    """O número da alternativa correta tem que ser a largura REAL da posição do vilão."""
    from leaklab.academy_questions import _larguras_por_posicao, _faixa
    larguras = _larguras_por_posicao(50.0)
    if len(larguras) < 3:
        print('OK  test_a_fatia_afirmada_bate_com_a_range_real (ranges indisponíveis, pulado)')
        return
    checados = 0
    for s in _spots('vs_rfi'):
        p = s.get('range_probe')
        if not p:
            continue
        vs = s['vs_position']
        if vs not in larguras:
            continue
        assert p['opcoes'][p['correta']] == _faixa(larguras[vs]), (
            f'{vs}: sondagem diz {p["opcoes"][p["correta"]]}, range real é {_faixa(larguras[vs])}')
        checados += 1
    assert checados > 0, 'nenhuma sondagem verificável'
    print(f'OK  test_a_fatia_afirmada_bate_com_a_range_real ({checados} conferidas)')


def test_alternativas_da_sondagem_nao_colidem():
    for s in _spots('vs_rfi'):
        p = s.get('range_probe')
        if not p:
            continue
        assert len(set(p['opcoes'])) == len(p['opcoes']), f'opções repetidas: {p["opcoes"]}'
        assert 0 <= p['correta'] < len(p['opcoes'])
    print('OK  test_alternativas_da_sondagem_nao_colidem')


def test_a_resposta_certa_nao_fica_sempre_na_mesma_posicao():
    """A sondagem embaralha por conta própria (não passa pelo sweep da Academia). Sem isto, o
    jogador aprende a clicar sempre no primeiro botão — foi exatamente o bug do quiz."""
    idx = [s['range_probe']['correta'] for s in _spots('vs_rfi', n=200, semente=3)
           if s.get('range_probe')]
    assert len(idx) >= 10, f'amostra pequena demais ({len(idx)})'
    assert len(set(idx)) > 1, f'resposta certa sempre na posição {idx[0]}'
    print(f'OK  test_a_resposta_certa_nao_fica_sempre_na_mesma_posicao ({sorted(set(idx))})')


if __name__ == '__main__':
    falhas = 0
    testes = (test_a_maioria_das_perguntas_vem_da_borda, test_ainda_serve_algumas_faceis,
              test_classificador_reconhece_mao_mista, test_todo_spot_declara_se_e_borda,
              test_nunca_devolve_None_por_falta_de_borda,
              test_sondagem_nunca_aparece_em_rfi, test_sondagem_aparece_onde_ha_vilao,
              test_a_fatia_afirmada_bate_com_a_range_real,
              test_alternativas_da_sondagem_nao_colidem,
              test_a_resposta_certa_nao_fica_sempre_na_mesma_posicao)
    for t in testes:
        try:
            t()
        except AssertionError as e:
            falhas += 1
            print(f'FALHOU  {t.__name__}: {e}')
    print(f'\nTotal: {len(testes)} | Passed: {len(testes) - falhas} | Failed: {falhas}')
    sys.exit(1 if falhas else 0)
