# -*- coding: utf-8 -*-
"""Sala que anonimiza o vilao nao gera HUD de oponente (11/09).

── O caso ─────────────────────────────────────────────────────────────────────────────────

O CoinPoker troca o hash do jogador a cada mao, e o HUD dele foi desligado em 04/09 por dois
motivos: sem identidade entre maos o read nao significa nada, e o volume de "jogadores de uma
mao" derrubava o worker. Ficou um guard por PROPORCAO (mais de 60 perfis e mais de 3x as maos)
para pegar qualquer sala futura com anonimizacao por-mao.

**O PartyPoker passa por esse guard folgado e e igualmente inutil, pelo motivo oposto.** Ele
anonimiza por ASSENTO: o nome persiste entre maos, e por isso a contagem nunca cresce. Medido no
arquivo real (3.482 maos, 34 torneios): **9 nomes de vilao**, e o nome segue o assento e nao a
pessoa (`Player1` no assento 1 em 88,6% das maos; `Player8` no assento 8 em 88,4%).

Num torneio de 322 maos, `build_profiles` devolve 9 perfis com amostra de 120 a 302 maos e VPIP
de 20% a 38%. Nenhum piso de amostra salva isso: a amostra e grande, o que falta e IDENTIDADE.
Cada perfil e a media de todos os que sentaram naquele assento, com rebalanceamento de mesa no
meio. Read com lastro falso e pior que read ausente, porque o jogador age nele.

── O que este arquivo defende ─────────────────────────────────────────────────────────────

1. A lista de salas sem identidade existe e traz as DUAS (uma so passaria com o Party de volta).
2. O `/analyze` nao constroi perfil para elas (condicao lida no fonte, no ponto de decisao).
3. Controle negativo: PokerStars e GGPoker seguem FORA da lista. Um guard que desligasse o HUD
   de todo mundo tambem passaria nos dois primeiros casos.
4. O que motiva a regra: nomes por assento produzem amostra grande com identidade nenhuma.

Quebrado de proposito (11/09): tirando `partypoker` da lista, os casos 1 e 2 acusam; pondo
`pokerstars` nela, o controle negativo acusa.
"""
import io
import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

_APP = os.path.join(os.path.dirname(__file__), '..', 'api', 'app.py')
_STATS = os.path.join(os.path.dirname(__file__), '..', 'leaklab', 'opponent_stats.py')
_FIX = os.path.join(os.path.dirname(__file__), 'fixtures')


def _lista_do_fonte():
    """A lista mora em `leaklab/opponent_stats.py`, nao no app: quem DECIDE (o `/analyze`) e quem
    LIMPA o que ja foi gravado (`scripts/limpa_perfis_sem_identidade.py`) leem a mesma lista. Com
    a constante dentro do app, o script teria de importar o Flask para saber a resposta, e a
    copia apareceria no dia seguinte."""
    src = io.open(_STATS, encoding='utf-8').read()
    src = '\n'.join(l.split('#')[0] for l in src.splitlines())   # comentario nao e evidencia
    m = re.search(r"SALAS_SEM_IDENTIDADE_DE_VILAO\s*=\s*\(([^)]*)\)", src)
    assert m, 'a lista de salas sem identidade de vilao desapareceu de opponent_stats.py'
    return [x.strip().strip("'\"") for x in m.group(1).split(',') if x.strip()]


def test_as_duas_salas_sem_identidade_estao_na_lista():
    salas = _lista_do_fonte()
    for s in ('coinpoker', 'partypoker'):
        assert s in salas, ('%s saiu da lista: o HUD volta a inventar read' % s, salas)


def test_o_analyze_decide_pela_lista_e_nao_por_uma_sala_cravada():
    """A condicao no ponto de decisao. Era `if site != 'coinpoker'`, e foi exatamente por isso
    que a sala seguinte entrou sem ninguem notar."""
    src = io.open(_APP, encoding='utf-8').read()
    assert 'if site not in SALAS_SEM_IDENTIDADE_DE_VILAO:' in src, \
        'o /analyze parou de decidir pela lista'
    assert "if site != 'coinpoker':" not in src, \
        'voltou a condicao cravada numa sala so'


def test_pokerstars_e_ggpoker_seguem_COM_hud():
    """CONTROLE NEGATIVO: sem ele, um guard que desligasse o HUD de todas as salas passaria nos
    dois testes acima. O HUD de oponente e uma feature viva para quem tem identidade."""
    salas = _lista_do_fonte()
    for s in ('pokerstars', 'ggpoker', 'acr'):
        assert s not in salas, ('%s nao anonimiza vilao e nao pode perder o HUD' % s, salas)


def test_o_nome_do_vilao_no_party_e_o_ASSENTO_nao_a_pessoa():
    """A medicao que motiva a regra, refeita na fixture: poucos nomes, muitas maos, e o nome
    colado no numero do assento. E o que nenhum piso de amostra detecta."""
    raw = io.open(os.path.join(_FIX, 'partypoker_mtt_novo.txt'), encoding='utf-8').read()
    pares = re.findall(r'^Seat (\d+): (Player\d+) \(', raw, re.M)
    assert pares, 'a fixture nao tem assento com nome de vilao'
    # Todo nome `PlayerN` aparece no assento N: o nome E o rotulo do assento.
    fora = [(s, n) for s, n in pares if n != 'Player%s' % s]
    assert len(fora) <= len(pares) * 0.35, (
        'a fixture nao exibe mais o padrao nome=assento; a medicao que justifica a regra '
        'precisa ser refeita', len(fora), len(pares))
    nomes = {n for _, n in pares}
    assert len(nomes) <= 9, ('esperado punhado de nomes, achei %d' % len(nomes), sorted(nomes))


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
