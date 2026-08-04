# -*- coding: utf-8 -*-
"""
Duas decisoes iguais na mesma street nao podem dividir um veredito so.

── O caso ─────────────────────────────────────────────────────────────────────────────────────────

Mao 259091895483 (torneio 3960586609). O hero age DUAS vezes no preflop:

  1. `CSM96: calls 8000`   -- paga o open de 2bb com KJs do CO a 56bb -> gto_critical, GTO diz raise
  2. `CSM96: calls 42153`  -- paga dois all-ins                       -> best_action=fold, SEM gto

Na tela, sobre a mesa da decisao 2 (os dois vilaes com 0 BB de stack), o card mostrava
**"ERRO · SOLVER · VOCE JOGOU CALL · GTO RECOMENDA RAISE"** -- o veredito da decisao 1.

Achado pelo usuario lendo a tela, depois de eu ter afirmado que aquela mao nao tinha defeito.

── A causa ────────────────────────────────────────────────────────────────────────────────────────

`(street, acao)` era usado como chave de `dict`, e ela **nao e unica**: o hero age duas vezes na
mesma street sempre que paga um open e depois enfrenta um 3-bet, ou aposta e depois enfrenta um
raise. Num dict, a segunda linha sobrescreve a primeira.

Havia ainda uma segunda metade: o filtro `if d.get('gto_label')` deixava a decisao SEM gabarito
fora do mapa, entao ela cedia o lugar e recebia o veredito da outra -- selo SOLVER numa decisao
que nao tem solver.

Medido no acervo: 74 decisoes colidem (0,8%), 32 com `gto_label` diferente entre si, **26 com uma
tendo gto e a outra nao** -- o caso do relato.

── Onde estava ────────────────────────────────────────────────────────────────────────────────────

Quatro copias do mesmo emparelhamento, todas em `api/app.py`. A quarta (`_process_gto_hand_request`)
**escreve no banco**: gravava o resultado do solver no `decision_id` errado.
"""
import os, sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
os.environ.setdefault('LEAKLAB_SECRET', 'x' * 40)

from leaklab.models import ParsedHand, ParsedAction                   # noqa: E402
from leaklab.pareamento_decisoes import (BaldeDeDecisoes, parear_por_ordem,   # noqa: E402
                                         balde_de_gto_do_banco)


# ── a funcao ───────────────────────────────────────────────────────────────────────────────────────

def test_duas_chaves_iguais_recebem_linhas_diferentes():
    vivas  = [('preflop', 'call'), ('preflop', 'call')]
    banco  = [('preflop', 'call'), ('preflop', 'call')]
    assert parear_por_ordem(vivas, banco) == [0, 1], 'cada decisao leva a SUA linha'


def test_linha_do_banco_nunca_e_entregue_duas_vezes():
    vivas = [('preflop', 'call')] * 3
    banco = [('preflop', 'call')] * 2
    pares = parear_por_ordem(vivas, banco)
    assert pares == [0, 1, None], pares
    usados = [p for p in pares if p is not None]
    assert len(usados) == len(set(usados)), 'nenhum indice repetido'


def test_sem_par_devolve_None_em_vez_de_roubar_o_de_outra():
    """Perder cobertura e honesto; herdar o veredito de outra decisao nao e."""
    pares = parear_por_ordem([('flop', 'bet')], [('flop', 'call')])
    assert pares == [None], pares


def test_chave_diferente_nao_interfere():
    """Uma decisao a mais de OUTRA chave nao desalinha as demais."""
    vivas = [('preflop', 'call'), ('flop', 'bet'), ('preflop', 'call')]
    banco = [('preflop', 'call'), ('preflop', 'call'), ('flop', 'bet')]
    assert parear_por_ordem(vivas, banco) == [0, 2, 1]


def test_restantes_denuncia_divergencia_entre_as_fontes():
    b = BaldeDeDecisoes([{'k': 1}, {'k': 1}], lambda d: d['k'])
    assert b.restantes() == 2
    b.proxima(1)
    assert b.restantes() == 1


def test_decisao_SEM_gto_ocupa_o_lugar_dela_na_fila():
    """A outra metade do defeito. O codigo antigo filtrava `if d.get('gto_label')`, entao a
    decisao sem gabarito nao entrava no balde — cedia a vez e herdava o veredito da outra."""
    linhas = [
        {'street': 'preflop', 'action_taken': 'call', 'gto_label': 'gto_critical'},
        {'street': 'preflop', 'action_taken': 'call', 'gto_label': None},
    ]
    balde = balde_de_gto_do_banco(linhas)
    assert balde.restantes() == 2, 'a linha sem gto_label precisa estar no balde'
    primeira = balde.proxima(('preflop', 'call'))
    segunda  = balde.proxima(('preflop', 'call'))
    assert primeira['gto_label'] == 'gto_critical'
    assert segunda is not None and segunda['gto_label'] is None, \
        'a 2a decisao deve receber a SUA linha (sem gto), nao a da 1a'


def test_o_endpoint_nao_pode_filtrar_gto_label_antes_do_balde():
    """Guarda de FONTE: o filtro pode voltar no chamador sem que nenhum teste de comportamento
    acuse, porque o `_build_replay_data` recebe as decisoes ja prontas. Este teste varre o
    proprio texto do `app.py` — mesmo padrao do guarda do Leak Trainer no front."""
    caminho = os.path.join(os.path.dirname(__file__), '..', 'api', 'app.py')
    fonte   = open(caminho, encoding='utf-8').read()
    linhas  = [l for l in fonte.splitlines()
               if 'balde_de_gto_do_banco(' in l and not l.strip().startswith('#')]
    assert len(linhas) >= 2, f'esperava os dois /replay usando o balde, achei {len(linhas)}'
    for l in linhas:
        assert 'gto_label' not in l, \
            f'filtro por gto_label voltou antes do balde — o defeito inteiro volta junto: {l.strip()}'


# ── o guarda de verdade: passa pelo replay inteiro ─────────────────────────────────────────────────

def _mao_com_dois_calls_no_preflop():
    """Hero paga um open e depois paga um all-in — duas decisoes `(preflop, call)`."""
    seats = [(1, 'Vilao', 60000), (2, 'Curto', 12000), (3, 'Hero', 90000)]
    raw = ['PokerStars Hand #259091895483: Tournament #3960586609']
    raw += [f'Seat {s}: {n} ({st} in chips)' for s, n, st in seats]
    return ParsedHand(
        hand_id='259091895483', tournament_id='3960586609', hero='Hero',
        button_seat=1, sb=2000.0, bb=4000.0, hero_cards='KsJs',
        seats=[{'seat': s, 'name': n, 'stack': st} for s, n, st in seats],
        actions=[
            ParsedAction('Vilao', 'preflop', 'raises', 8000.0,  'Vilao: raises 4,000 to 8,000'),
            ParsedAction('Hero',  'preflop', 'calls',  8000.0,  'Hero: calls 8,000'),
            ParsedAction('Curto', 'preflop', 'all-in', 12000.0, 'Curto: raises 4,000 to 12,000 and is all-in'),
            ParsedAction('Hero',  'preflop', 'calls',  4000.0,  'Hero: calls 4,000'),
            ParsedAction('Vilao', 'preflop', 'folds',  None,    'Vilao: folds'),
        ],
        raw_text='\n'.join(raw),
    )


def _decisoes_do_banco():
    """A 1ª tem veredito do solver; a 2ª NAO tem — exatamente o par do relato."""
    return [
        {'hand_id': '259091895483', 'street': 'preflop', 'action_taken': 'call',
         'best_action': 'raise', 'label': 'small_mistake', 'score': 0.3,
         'gto_label': 'gto_critical', 'gto_action': 'raise', 'facing_bet': 2.0,
         'position': 'CO', 'stack_bb': 22.5, 'hero_cards': 'KsJs'},
        {'hand_id': '259091895483', 'street': 'preflop', 'action_taken': 'call',
         'best_action': 'fold', 'label': 'small_mistake', 'score': 0.2,
         'gto_label': None, 'gto_action': None, 'facing_bet': 3.0,
         'position': 'CO', 'stack_bb': 20.5, 'hero_cards': 'KsJs'},
    ]


def _passos_do_hero(replay):
    linha = replay.get('timeline') or replay.get('steps') or []
    return [p for p in linha
            if p.get('type') == 'action' and p.get('is_hero') and p.get('action') == 'call']


def test_a_segunda_decisao_nao_herda_o_veredito_da_primeira():
    """O guarda que faltava. Sem o conserto, os dois passos saem com gto_action='raise'."""
    from api.app import _build_replay_data
    replay = _build_replay_data(_mao_com_dois_calls_no_preflop(), _decisoes_do_banco(), 'Hero')
    passos = _passos_do_hero(replay)
    assert len(passos) == 2, f'a mao tem 2 calls do hero, o replay devolveu {len(passos)}'

    primeiro, segundo = passos
    assert primeiro.get('gto_label') == 'gto_critical', primeiro.get('gto_label')
    # A 2ª decisao NAO tem solver. Herdar o selo da 1ª e o defeito inteiro.
    assert segundo.get('gto_label') is None, \
        f"2a decisao herdou o veredito da 1a: gto_label={segundo.get('gto_label')!r}"


def test_cada_passo_recebe_o_seu_proprio_facing():
    """`facing_bet` saia do MESMO mapa, entao herdava o valor errado junto com o veredito."""
    from api.app import _build_replay_data
    replay = _build_replay_data(_mao_com_dois_calls_no_preflop(), _decisoes_do_banco(), 'Hero')
    passos = _passos_do_hero(replay)
    assert len(passos) == 2
    # Os dois passos precisam ser objetos distintos com conteudo distinto — se o mapa
    # colapsou as decisoes, eles saem identicos.
    assert passos[0] != passos[1], 'os dois passos do hero sairam identicos'


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
