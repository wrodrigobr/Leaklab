# -*- coding: utf-8 -*-
"""
Prova de que A MESA É O TORNEIO — a condição que autoriza ICM real.

── O que o usuário reportou ───────────────────────────────────────────────────────────────────────

Numa mão com 3 jogadores sentados: "certeza que é mesa final, pois só temos 3 jogadores na mesa.
As decisões aqui já não deveriam ser diferentes? Identificou erro no meu raise, mas estou com um
stack muito maior que os adversários, eu não deveria explorá-los?"

Ele está certo sobre o diagnóstico e o produto estava cego: o ICM real só ligava quando
`field_size` (inscritos, vindo do resumo) era ≤ 9. Num MTT o `field_size` é o total de inscritos
PARA SEMPRE — 500 inscritos continuam 500 na mesa final. Ou seja, o gate **nunca abria numa mesa
final de MTT**, exatamente onde ICM é o fator dominante. Ele só funcionava em torneio de mesa
única.

── Por que não bastava contar assentos ────────────────────────────────────────────────────────────

Foi o bug ANTERIOR, e o conserto dele criou este. O gate original era `assentos <= 9`, o que num
MTT 9-max é verdade em TODA mão: o card anunciava "Mesa final" no nível 3 de blinds com centenas
de jogadores vivos, e a equity de premiação era calculada tratando aqueles 8 stacks como o torneio
inteiro. Contagem de assentos não distingue "mesa final" de "uma mesa qualquer".

O hand history não informa quantos jogadores restam no torneio, e o hero só enxerga a própria
mesa. Então precisa de prova externa.

── A prova, e ela foi ideia do usuário ────────────────────────────────────────────────────────────

"No summary tem a colocação do torneio, poderíamos detectar quando os 8 ou 9 jogadores vencedores
estão na mesma mesa."

É exato, e o motivo é aritmético: as colocações de um torneio são uma permutação de 1..N, e quem
sai mais tarde tem colocação menor. Se restam S jogadores, as colocações DELES são exatamente
{1..S} — ninguém pode ter colocação > S, porque quem tem já saiu. Então:

    a mesa é o torneio  ⟺  a MAIOR colocação entre os sentados == número de sentados

Um falso positivo exigiria que todos os sentados tivessem sobrevivido a todos os jogadores das
outras mesas com a mesa ainda cheia — em campo de duas mesas isso é 1 em C(18,9) ≈ 49 mil.

── Limitação honesta ──────────────────────────────────────────────────────────────────────────────

Isto só funciona em torneio cujo arquivo de RESUMO foi enviado, porque é de lá que vêm as
colocações. Sem resumo, o gate cai no critério antigo (`field_size` de mesa única) e o ICM real
continua desligado. Medido em produção em 2026-07-29: 19 dos 76 torneios têm resumo, e nenhum
deles pode ser recuperado retroativamente — o texto do resumo não é guardado, só os campos que
ele preenche. Vale para importação nova.
"""
from __future__ import annotations

import re

# Assentos do roster (o topo da mão), por dialeto:
#   PS/GG          "Seat 1: nome (1500 in chips)"
#   ACR            "Seat 1: nome (29150.00)"
#   888/PartyPoker "Seat 1: nome ( $3,548 )"   — espaços internos E cifrão
#
# Permissivo de propósito com o número: quem exclui as linhas de `*** SUMMARY ***` (que também
# começam com "Seat N:" e trazem "(1500)" como VALOR COLETADO) é o corte ESTRUTURAL abaixo, não
# este padrão. Tentar resolver por regex mais esperto já falhou duas vezes: exigir "in chips"
# quebra a ACR, e exigir dígito logo após o "(" quebra o 888.
_ASSENTO_RE = re.compile(r'^Seat \d+: (.+?) \(\s*\$?[\d.,]+\s*(?:in chips)?\s*\)')

# Máximo de jogadores que caberia numa mesa. Acima disso não é mesa, é torneio em andamento.
MAX_NA_MESA = 9


def nomes_sentados(raw: str) -> set:
    """Nomes distintos que APARECERAM SENTADOS no raw dado (uma mão ou o arquivo inteiro).

    Fonte única deste sinal. Serve a três consumidores: distinguir SNG de MTT no nome do torneio,
    contar o roster de uma mão e provar mesa final. O corte do summary é estrutural — ver
    `_ASSENTO_RE`.
    """
    nomes = set()
    em_summary = False
    for linha in (raw or '').splitlines():
        l = linha.strip()
        if l.startswith('*** SUMMARY ***'):
            em_summary = True
            continue
        # Cabeçalho de mão nova encerra o summary anterior (cobre "PokerStars Hand #",
        # "Poker Hand #TM" do GG, "Game Hand #" da ACR, "CoinPoker Hand #").
        if 'Hand #' in l:
            em_summary = False
            continue
        if em_summary:
            continue
        m = _ASSENTO_RE.match(l)
        if m:
            nomes.add(m.group(1).strip())
    return nomes


def mesa_e_o_torneio(sentados: set | list | None,
                     *,
                     field_size: int | None = None,
                     colocacoes: dict | None = None) -> tuple[bool, str]:
    """A mesa contém TODOS os jogadores que restam no torneio? Devolve (veredito, motivo).

    Duas provas, nesta ordem de força:

    `colocacoes` — {nome: colocação_final} do torneio todo (do arquivo de resumo). Prova
    posicional: maior colocação entre os sentados == número de sentados. Funciona em MESA FINAL
    DE MTT, que é o caso que o gate antigo não cobria.

    `field_size` — inscritos no torneio. Prova de mesa única: um torneio de até 9 inscritos é uma
    mesa só do começo ao fim. É o critério antigo, mantido porque é o único disponível quando não
    há colocações.

    O motivo é devolvido para que a superfície possa dizer POR QUE ligou (ou não) o ICM real, em
    vez de o número aparecer sem explicação.
    """
    nomes = {n for n in (sentados or []) if n}
    n_sentados = len(nomes)
    if n_sentados < 2:
        return False, 'sem_mesa'
    if n_sentados > MAX_NA_MESA:
        return False, 'mesa_grande_demais'

    if colocacoes:
        # Toda pessoa sentada precisa ter colocação conhecida. Um único nome ausente derruba a
        # prova: se não sei onde ele terminou, não sei se alguém ficou acima de n_sentados.
        # Falhar FECHADO aqui é obrigatório — falhar aberto ligaria ICM real com equity errada,
        # que é pior do que não ligar (o bucket heurístico continua valendo).
        places = [colocacoes.get(n) for n in nomes]
        if all(p is not None for p in places):
            if max(places) == n_sentados:
                return True, 'colocacoes'
            return False, 'colocacoes_indicam_mtt_em_andamento'

    if field_size is not None and 2 <= int(field_size) <= MAX_NA_MESA:
        return True, 'mesa_unica'

    return False, 'sem_prova'
