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


# ── Marcação de família (treino de fronteira na grade) ────────────────────────────────────────

def _spot_grid(semente=11):
    from leaklab.leak_trainer import generate_range_grid_spot
    rng = random.Random(semente)
    for _ in range(30):
        s = generate_range_grid_spot(rng)
        if s:
            return s
    return None


def test_familia_servida_tem_a_fronteira_dentro():
    """Família 100% dentro ou 100% fora não ensina fronteira: vira 'marque tudo' ou 'marque nada',
    e o jogador acerta sem saber. O gerador tem que descartá-las."""
    from leaklab.leak_trainer import generate_range_grid_spot, grade_range_grid_spot
    rng = random.Random(3)
    checados = 0
    for _ in range(60):
        sp = generate_range_grid_spot(rng)
        if not sp:
            continue
        g = grade_range_grid_spot(sp, [])
        n_certas, n_total = len(g['certas']), len(sp['hands'])
        assert 0 < n_certas < n_total, (
            f"{sp['position']} / {sp['familia_label']}: {n_certas} de {n_total} — "
            'família sem fronteira não deveria ser servida')
        checados += 1
    assert checados > 10, f'poucos spots gerados ({checados})'
    print(f'OK  test_familia_servida_tem_a_fronteira_dentro ({checados} spots)')


def test_correcao_reporta_o_que_faltou_e_o_que_sobrou():
    from leaklab.leak_trainer import grade_range_grid_spot
    sp = _spot_grid()
    assert sp, 'nenhum spot de grade gerado'
    certas = grade_range_grid_spot(sp, [])['certas']
    fora = [h for h in sp['hands'] if h not in certas]

    # marcação perfeita
    g = grade_range_grid_spot(sp, certas)
    assert g['acertou'] and not g['faltaram'] and not g['sobraram']
    assert g['xp'] > 0, 'acerto pleno tem que pagar XP'

    # faltando uma
    g = grade_range_grid_spot(sp, certas[:-1])
    assert not g['acertou'] and g['faltaram'] == [certas[-1]] and not g['sobraram']
    assert g['xp'] == 0

    # sobrando uma
    if fora:
        g = grade_range_grid_spot(sp, certas + [fora[0]])
        assert not g['acertou'] and g['sobraram'] == [fora[0]] and not g['faltaram']
    print('OK  test_correcao_reporta_o_que_faltou_e_o_que_sobrou')


def test_nao_marcar_nada_NAO_conta_como_acerto():
    """A armadilha do formato: numa família em que a posição abre 5 de 12, 'porcentagem de células
    certas' daria 58% para quem não responde. Por isso a correção é faltou/sobrou, e nunca um
    placar que premie o silêncio."""
    from leaklab.leak_trainer import grade_range_grid_spot
    sp = _spot_grid()
    g = grade_range_grid_spot(sp, [])
    assert not g['acertou'] and g['xp'] == 0
    assert g['faltaram'], 'não marcar nada tem que reportar tudo como faltando'
    print('OK  test_nao_marcar_nada_NAO_conta_como_acerto')


def test_a_fronteira_e_a_mao_mais_fraca_que_entra():
    """É o fato âncora que o jogador leva mesmo errando."""
    from leaklab.leak_trainer import grade_range_grid_spot
    sp = _spot_grid()
    g = grade_range_grid_spot(sp, [])
    ordem = sp['hands']
    assert g['fronteira'] in g['certas']
    mais_fraca = max((h for h in g['certas']), key=ordem.index)
    assert g['fronteira'] == mais_fraca, f"{g['fronteira']} não é a mais fraca de {g['certas']}"
    print(f"OK  test_a_fronteira_e_a_mao_mais_fraca_que_entra ({sp['familia_label']}: {g['fronteira']})")


def test_marcacao_fora_da_familia_e_ignorada():
    """O cliente não define o gabarito: mão que não pertence à família servida não conta como
    'sobrou' nem envenena a correção."""
    from leaklab.leak_trainer import grade_range_grid_spot
    sp = _spot_grid()
    certas = grade_range_grid_spot(sp, [])['certas']
    g = grade_range_grid_spot(sp, certas + ['AA', 'ZZs', ''])
    assert g['acertou'], f"marcação estranha vazou para a correção: {g['sobraram']}"
    print('OK  test_marcacao_fora_da_familia_e_ignorada')


if __name__ == '__main__':
    falhas = 0
    testes = (test_a_maioria_das_perguntas_vem_da_borda, test_ainda_serve_algumas_faceis,
              test_classificador_reconhece_mao_mista, test_todo_spot_declara_se_e_borda,
              test_nunca_devolve_None_por_falta_de_borda,
              test_sondagem_nunca_aparece_em_rfi, test_sondagem_aparece_onde_ha_vilao,
              test_a_fatia_afirmada_bate_com_a_range_real,
              test_alternativas_da_sondagem_nao_colidem,
              test_a_resposta_certa_nao_fica_sempre_na_mesma_posicao,
              test_familia_servida_tem_a_fronteira_dentro,
              test_correcao_reporta_o_que_faltou_e_o_que_sobrou,
              test_nao_marcar_nada_NAO_conta_como_acerto,
              test_a_fronteira_e_a_mao_mais_fraca_que_entra,
              test_marcacao_fora_da_familia_e_ignorada)
    for t in testes:
        try:
            t()
        except AssertionError as e:
            falhas += 1
            print(f'FALHOU  {t.__name__}: {e}')
    print(f'\nTotal: {len(testes)} | Passed: {len(testes) - falhas} | Failed: {falhas}')
    sys.exit(1 if falhas else 0)
