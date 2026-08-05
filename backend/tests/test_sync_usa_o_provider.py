# -*- coding: utf-8 -*-
"""
O `sync` derivava `gto_label` de uma fonte propria, com o stack ERRADO.

── O que estava separado ──────────────────────────────────────────────────────────────────────────

O motor consome `strategy_provider.preflop_strategy` (a porta unica do preflop, que o trainer, a
academy e o /replay tambem usam). O `sync_gto_labels_from_ranges` chamava `analyze_preflop` cru, e
reconstruia as entradas a partir das COLUNAS do banco. Duas consequencias:

  1. **Stack errado.** `decisions.stack_bb` guarda `heroStackBb`; a range preflop precisa do
     EFETIVO. Medido no acervo: os dois diferem em **52%** das linhas, com casos de 3,0bb efetivos
     contra 15,0bb do hero — consultar a range de outra profundidade.
  2. **Sem o guarda da porta unica.** `analyze_preflop` nao valida o formato da mao: entrada que
     ele nao entende vira "fora do range, fold 100%" com confianca. O `preflop_strategy` responde
     "nao sei".

Conserto: coluna `effective_stack_bb` (o motor ja calculava, so nao gravava) + o sync passando a
consumir `preflop_strategy`.

── O que NAO foi unificado, e por que ────────────────────────────────────────────────────────────

Paridade TOTAL de entrada nao sai das colunas: o motor passa `facingSize` em FICHAS, mais
`n_players`, `facing_allin`, `is_pko` e `heroWasAggressor` vindos do spot; o sync tem proxies ou
nao tem. Sobram 35 decisoes preflop (1,5% do acervo) em que o sync acha cobertura que o motor nao
acha. Nenhuma delas CONTRADIZ o motor — sao todas "motor nao tem, banco tem".
"""
import os, sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts'))


def test_o_sync_consome_a_porta_unica():
    """Guarda de FONTE: o modulo nao pode voltar a importar o analisador cru."""
    import sync_gto_labels_from_ranges as sync
    assert hasattr(sync, 'preflop_strategy'), 'o sync tem que consumir o strategy_provider'
    fonte = open(os.path.join(os.path.dirname(__file__), '..', 'scripts',
                              'sync_gto_labels_from_ranges.py'), encoding='utf-8').read()
    linhas = [l for l in fonte.splitlines()
              if 'analyze_preflop' in l and not l.strip().startswith('#')]
    assert not linhas, f'voltou a usar analyze_preflop direto: {linhas}'


def test_o_sync_le_o_stack_EFETIVO():
    """O stack do hero e o efetivo diferem em 52% das linhas — usar o errado consulta a range
    de outra profundidade. A coluna e NULL em linha antiga, e ai cai no comportamento de antes."""
    fonte = open(os.path.join(os.path.dirname(__file__), '..', 'scripts',
                              'sync_gto_labels_from_ranges.py'), encoding='utf-8').read()
    assert 'effective_stack_bb' in fonte, 'o sync precisa ler a coluna do stack efetivo'
    assert 'r.get("effective_stack_bb") or r["stack_bb"]' in fonte, \
        'precisa preferir o efetivo e cair no antigo so quando NULL'
    for consulta in ('SELECT id, hand_id, tournament_id',):
        assert consulta in fonte
    # as duas consultas do modulo precisam trazer a coluna, senao o `r.get` acima devolve None
    assert fonte.count('effective_stack_bb') >= 3, \
        'a coluna precisa estar nos SELECTs E na leitura'


def test_a_coluna_do_stack_efetivo_e_gravada():
    """`save_decisions` tem que persistir o efetivo — sem isso o sync nunca o ve."""
    fonte = open(os.path.join(os.path.dirname(__file__), '..', 'database', 'repositories.py'),
                 encoding='utf-8').read()
    assert "spot_ctx.get('effectiveStackBb')" in fonte
    assert 'effective_stack_bb' in fonte, 'a coluna precisa estar no INSERT'


def test_o_provider_recusa_mao_que_nao_entende():
    """O ganho concreto da porta unica: o analisador cru responderia com confianca."""
    from leaklab.strategy_provider import preflop_strategy
    r = preflop_strategy(position='BTN', hero_hand_type='lixo', stack_bb=30.0,
                         action_taken='raise')
    assert r['available'] is False, 'mao em formato desconhecido tem que virar "nao sei"'


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
