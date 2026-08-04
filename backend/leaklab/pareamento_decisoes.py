# -*- coding: utf-8 -*-
"""Emparelhar as decisões de uma mão vindas de DUAS fontes.

O `/replay` (e o worker de solve) reconstroem a mão do texto cru e precisam casar cada
decisão recalculada ao vivo com a linha correspondente do banco. O emparelhamento vivia
copiado em quatro lugares, todos com o mesmo defeito: um `dict` chaveado por
`(street, ação)`.

**Essa chave não é única.** O hero age duas vezes na mesma street sempre que paga um open e
depois enfrenta um 3-bet, ou aposta e depois enfrenta um raise. Quando isso acontece, um
`dict` faz a segunda linha sobrescrever a primeira, e as duas decisões passam a compartilhar
um veredito só. Medido em 2026-08-04: 74 decisões colidem (0,8% do acervo), 32 têm
`gto_label` diferente entre si e **26 exibiam selo SOLVER numa decisão que não tem solver**.

A chave continua sendo `(street, ação)` — é o que as duas fontes têm em comum, já que a
decisão recalculada não carrega `decision_id`. O que muda é que ela deixa de ser um índice
único e passa a ser um **balde consumido em ordem**: a primeira decisão da mão casa com a
primeira linha do banco daquela chave, a segunda com a segunda. As duas fontes são
cronológicas (`get_decisions` ordena por `id`, que é a ordem de gravação, e o pipeline
devolve as decisões na ordem das ações), então a ordem dentro do balde corresponde.

Quando o balde acaba — banco com menos linhas que a mão recalculada, o que acontece em
torneio analisado por uma versão anterior do parser — a decisão fica **sem** par em vez de
roubar o de outra. Perder cobertura é honesto; trocar veredito não é.

Não normaliza nada de propósito. Cada chamador já tem o seu normalizador de ação e eles
**diferem entre si** (uns fazem `lower()` e mapeiam `jam`→`allin`, outros não); unificá-los é
trabalho à parte, com um teste de equivalência sobre o vocabulário real antes — ver a nota
em `leaklab/card_verdict.py`.
"""
from __future__ import annotations

from collections import defaultdict, deque
from typing import Any, Callable, Hashable, Iterable


class BaldeDeDecisoes:
    """Linhas do banco agrupadas por chave, entregues **uma vez cada**, em ordem.

    Uso:

        balde = BaldeDeDecisoes(linhas_do_banco, lambda d: (d['street'], norm(d['action_taken'])))
        for di in decisoes_recalculadas:
            linha = balde.proxima((di['street'], norm(acao)))   # None quando não há par
    """

    def __init__(self, linhas: Iterable[Any], chave: Callable[[Any], Hashable]):
        self._baldes: dict[Hashable, deque] = defaultdict(deque)
        for linha in linhas or ():
            self._baldes[chave(linha)].append(linha)

    def proxima(self, k: Hashable):
        """Consome e devolve a próxima linha daquela chave, ou None se não houver.

        Consumir é o ponto: sem isso, duas decisões iguais levam a mesma linha."""
        balde = self._baldes.get(k)
        return balde.popleft() if balde else None

    def restantes(self) -> int:
        """Linhas do banco que nenhuma decisão reclamou. Zero é o esperado quando as duas
        fontes descrevem a mesma mão; diferente de zero indica que elas divergiram."""
        return sum(len(b) for b in self._baldes.values())


def chave_do_replay(d) -> tuple:
    """Chave `(street, ação)` no dialeto do `/replay`: o banco grava 'call', o parser devolve
    'calls'. NÃO faz `lower()` nem mapeia `jam`→`allin` — o `/replay` sempre foi assim, e
    trocar por outro normalizador seria mudança de comportamento disfarçada de refactor."""
    acao = (d.get('action_taken', '') or '')
    return (d.get('street', ''), acao.rstrip('s') or acao)


def balde_de_gto_do_banco(linhas_do_banco: Iterable[Any]) -> BaldeDeDecisoes:
    """Balde das decisões de UMA mão, do jeito que os dois `/replay` (aluno e coach) precisam.

    **Recebe as linhas TODAS, inclusive as sem `gto_label`, e isso é o ponto.** O código
    anterior filtrava `if d.get('gto_label')`, e a decisão sem gabarito então não ocupava o
    seu lugar na fila: ela cedia a vez, herdava o veredito da outra decisão da mesma chave e
    aparecia na tela com selo SOLVER sem ter solver. Filtrar aqui de novo reintroduz o
    defeito inteiro."""
    return BaldeDeDecisoes(linhas_do_banco, chave_do_replay)


def parear_por_ordem(chaves_vivas: list, chaves_banco: list) -> list:
    """Versão pura, para teste e para quem prefere índices a objetos.

    Devolve uma lista do tamanho de `chaves_vivas` com o ÍNDICE em `chaves_banco` de cada
    par (ou None). Nenhum índice aparece duas vezes."""
    balde = BaldeDeDecisoes(range(len(chaves_banco)), lambda i: chaves_banco[i])
    return [balde.proxima(k) for k in chaves_vivas]
