# -*- coding: utf-8 -*-
"""O sync e o motor tem que chegar na porta unica com os MESMOS argumentos.

── O caso ─────────────────────────────────────────────────────────────────────────────────────

Onze decisoes preflop tinham gabarito no banco e "nao sei" no motor. Os dois chamam a MESMA
funcao (`preflop_strategy`) — a divergencia estava nos ARGUMENTOS.

Achado por observacao, nao por leitura: interceptei a chamada nos dois caminhos e comparei os
kwargs de verdade. Reconstruir os argumentos a mao me deu campo errado tres vezes seguidas
(`facingBet` onde o pipeline grava `facingSize`, `vsPosition` onde grava `villainPosition`).

Depois, ablacao UM-A-UM sobre os 11: partindo dos args do sync, trocar UM campo pelo do motor e
ver qual sozinho reproduz o resultado. Resultado:

    hero_was_aggressor   9 de 11
    n_players            2 de 11

E so. `facing_size` diferia em 11 de 11 (18.0 bb no sync, 300.0 fichas no motor) e **nao causava
nada** — o provider so usa esse campo como `> 0`. Sem a ablacao eu teria "consertado" a unidade,
que e o bug mais recorrente deste projeto, e errado o alvo.

── Por que o motor esta certo nos dois ────────────────────────────────────────────────────────

`hero_was_aggressor`: o sync usava `is_3bet` como proxy e o proprio comentario dele admitia o
chute. O campo decide o CENARIO (`vs_3bet` x `vs_rfi` x `faces_squeeze` x `vs_4bet`) — ou seja,
QUAL RANGE e consultada. Chutar aqui nao devolve "nao sei": devolve veredito da range errada.

`n_players`: `_norm_pos` mapeia posicao por tamanho de mesa (6/7/8-max nao caem no mesmo lugar do
9-max). O sync nao passava.

Conserto: coluna `decisions.hero_was_aggressor` (gravada pelo pipeline, como `facing_limp`) e
`num_players`, que ja existia e so nao era lida.
"""
import os, re, sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

_SYNC = os.path.join(os.path.dirname(__file__), '..', 'scripts',
                     'sync_gto_labels_from_ranges.py')


def _codigo():
    """So codigo: os comentarios do arquivo CITAM o proxy antigo para explicar por que ele saiu."""
    return '\n'.join(l for l in open(_SYNC, encoding='utf-8').read().splitlines()
                     if not l.lstrip().startswith('#'))


def test_o_sync_nao_chuta_hero_was_aggressor():
    """A causa de 9 das 11. `is_3bet` significa "hero DEU 3bet", nao "hero ja agrediu"."""
    src = _codigo()
    assert 'hero_was_aggressor=is_3bet' not in src, (
        'voltou o proxy `is_3bet` — ele escolhe o cenario errado e, com ele, a range errada')
    assert 'hero_was_aggressor=was_aggressor' in src, (
        'o sync parou de passar o valor real de hero_was_aggressor')


def test_o_sync_passa_o_tamanho_da_mesa():
    """A causa das outras 2. Sem `n_players`, `_norm_pos` mapeia como se fosse 9-max."""
    src = _codigo()
    assert 'n_players=' in src, 'o sync voltou a nao passar n_players'


def test_o_sync_le_as_duas_colunas():
    """FIACAO: passar o argumento nao adianta se o SELECT nao traz a coluna — ele viraria None
    sempre, e o fallback silencioso levaria de volta ao proxy."""
    src = _codigo()
    assert src.count('hero_was_aggressor') >= 3, (
        'algum SELECT do sync parou de trazer hero_was_aggressor')
    assert src.count('num_players') >= 3, 'algum SELECT do sync parou de trazer num_players'


def test_linha_antiga_cai_no_comportamento_conhecido():
    """`hero_was_aggressor` e NULL em linha gravada antes da coluna existir. Nesse caso o sync
    tem que cair no proxy de antes — que e errado, mas e o comportamento CONHECIDO — em vez de
    assumir False, que seria um terceiro comportamento, novo e silencioso."""
    src = _codigo()
    assert re.search(r'_hwa\s+is\s+not\s+None', src), (
        'o fallback de linha antiga sumiu; NULL passaria a virar False e mudaria veredito de '
        'linha antiga sem ninguem pedir')


def test_a_coluna_e_gravada_pelo_caminho_vivo():
    """Ter a coluna no schema e nao grava-la e o defeito do `spot_hash`, que por meses era
    gravado so pelo backfill."""
    repo = open(os.path.join(os.path.dirname(__file__), '..', 'database', 'repositories.py'),
                encoding='utf-8').read()
    assert "spot_ctx.get('heroWasAggressor')" in repo, (
        'save_decisions parou de gravar hero_was_aggressor — a coluna existiria vazia')
    assert 'hero_was_aggressor,' in repo, 'a coluna sumiu da lista do INSERT'


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
