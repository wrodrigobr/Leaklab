# -*- coding: utf-8 -*-
"""
Toda decisao gravada pelo caminho VIVO saia com `spot_hash` NULL.

── Como apareceu ──────────────────────────────────────────────────────────────────────────────────

Reprocessando o acervo local (2.306 decisoes), o `spot_hash` caiu de 1.728 preenchidos para **1**.
Nao era dano do reprocesso: era o caminho de gravacao nunca ter preenchido a chave. Os 1.728 que
existiam vinham de backfill, e os torneios analisados mais recentemente estavam com **0%**:

    t=418  n=34   com hash=0
    t=420  n=64   com hash=0
    t=426  n=136  com hash=0
    t=429  n=351  com hash=7   (2%)

── A causa ────────────────────────────────────────────────────────────────────────────────────────

`repositories._chaves` lia o stack assim:

    stack_bb = r.get('stack_bb') or spot.get('heroStackBb')

O dict de resultado da analise **nao tem nenhum dos dois**: no topo nao existe `stack_bb`, e o
`spot` carrega `effectiveStackBb` (o `heroStackBb` vive no `context`). As duas fontes davam None,
`chaves_de_decisao` devolvia `(None, None)`, e o INSERT gravava NULL nas duas colunas.

`spot_family_key` e `spot_hash` alimentam a agregacao por familia do Protocolo de Progressao;
decisao sem chave sai da conta em silencio.

── Por que `effectiveStackBb` e nao `heroStackBb` ─────────────────────────────────────────────────

E o stack que o MOTOR usa no `compute_spot_hash` (`decision_engine_v11`: `effectiveStackBb or
heroStackBb or 20`). Usar outro produziria uma chave que o lookup nunca procura.

Nota registrada de passagem: a COLUNA `decisions.stack_bb` guarda `ctx.heroStackBb`, que e outra
quantidade — nao e a que entra no hash. Nao foi mexida aqui.
"""
import os, sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from database.repositories import _chaves                     # noqa: E402


def _resultado(effective_stack=37.4, **spot_extra):
    """Formato do dict que `save_decisions` recebe — igual ao que `_analyze_hands` e o
    `reprocess_tournament` montam: sem `stack_bb` no topo, sem `heroStackBb` no spot."""
    spot = {'position': 'MP1', 'villainPosition': 'BTN', 'effectiveStackBb': effective_stack,
            'facingToBb': 2.0, 'potType': 'srp', 'preflopRaisesFaced': 1}
    spot.update(spot_extra)
    return {'street': 'preflop', 'position': 'MP1', 'board': [], 'hero_cards': 'AsKd',
            'is_3bet': False, 'spot': spot}


def test_decisao_gravada_recebe_familia_e_hash():
    familia, hash_ = _chaves(_resultado())
    assert familia, 'sem spot_family_key a decisao sai da agregacao por familia'
    assert hash_,   'sem spot_hash a decisao nao casa com no do solver'


def test_o_stack_usado_e_o_EFETIVO():
    """Dois stacks efetivos em baldes diferentes precisam gerar familias diferentes. Se a funcao
    voltar a ler `heroStackBb` (ausente), as duas caem em None e ficam IGUAIS."""
    f_curto, _ = _chaves(_resultado(effective_stack=9.0))
    f_fundo, _ = _chaves(_resultado(effective_stack=80.0))
    assert f_curto and f_fundo, (f_curto, f_fundo)
    assert f_curto != f_fundo, f'o bucket de stack nao entrou na chave: {f_curto} == {f_fundo}'


def test_a_chave_bate_com_a_que_o_MOTOR_procura():
    """A chave gravada tem que ser a mesma que o lookup do solver monta, senao o no existe e
    nunca e achado. Confronta com `familia_spot.chaves_de_decisao` alimentado pela mesma
    fonte que o `decision_engine` usa (`effectiveStackBb`)."""
    from leaklab.familia_spot import chaves_de_decisao
    r = _resultado()
    esperado = chaves_de_decisao(
        street='preflop', position='MP1', stack_bb=r['spot']['effectiveStackBb'],
        vs_position='BTN', is_3bet=False, board=[], hero_cards='AsKd',
        facing_bet=r['spot']['facingToBb'], pot_type='srp', raises_faced=1)
    assert _chaves(r) == esperado, (_chaves(r), esperado)


def test_sem_stack_nenhum_nao_inventa_chave():
    """Sem dado nao se chuta: a decisao fica sem chave em vez de receber uma errada."""
    r = _resultado()
    r['spot'].pop('effectiveStackBb')
    familia, hash_ = _chaves(r)
    assert (familia, hash_) == (None, None), (familia, hash_)


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
