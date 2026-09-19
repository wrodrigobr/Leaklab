# -*- coding: utf-8 -*-
"""A cota do modo Pratica: teto de mesas simultaneas e teto de spots por mes.

── O pedido (18/09) ──────────────────────────────────────────────────────────────────────────

O dono: "o modo pratica pode ser liberado para plano free, mas eu quero que eles tenham uma
limitacao de apenas 2 mesas simultaneas e no maximo 30 spots por mes... e isto precisa ficar
explicito pra eles na tela".

Duas observacoes que mudaram o trabalho:

1. **O Pratica nunca esteve fechado.** A rota exigia apenas estar logado, e nenhum dos dois
   endpoints olhava o plano. Entao isto nao libera nada: isto coloca o limite que faltava.
2. **Balde proprio.** O Free ja tem `training_spots_per_day: 20` para o treino avulso, decidido
   em 28/08. O Pratica e multimesa (ate 4 spots por rodada), e misturar os baldes faria uma
   rodada de 4 mesas comer 4 dos 20 spots diarios do Ghost Table, que e outro produto.

── Por que este modulo existe, em vez de a conta ficar nos endpoints ────────────────────────

A regra vale em TRES lugares: no `/practice/tables` (que clampa as mesas), no `/practice/grade`
(que e o unico que realmente gasta cota, e que um cliente poderia chamar sem pedir mesa) e no
`/auth/me` (que alimenta o contador da tela). Regra aplicada em N lugares vira funcao, com teste
que varre os N+1 -- a regra 5 da casa. Se o teto morasse em cada endpoint, o dia em que um deles
mudasse criaria dois produtos com a mesma tela.
"""
from __future__ import annotations

from datetime import date

#: Teto absoluto de mesas do modo, independente de plano. Fonte: `pratica_preflop.MAX_MESAS`.
#: Importado tarde (dentro da funcao) porque aquele modulo carrega o gerador de spot.


def inicio_do_mes(hoje: date = None) -> str:
    """O primeiro instante do mes corrente, no formato em que `criado_em` e comparavel.

    String, e nao objeto de data, porque o filtro roda cru nos dois bancos (ver
    `historico_de_pratica.contagem_desde`).
    """
    hoje = hoje or date.today()
    return '%04d-%02d-01 00:00:00' % (hoje.year, hoje.month)


def renovacao(hoje: date = None) -> str:
    """O dia em que a cota volta: primeiro dia do mes seguinte. E o que a tela promete ao jogador,
    e precisa bater com o corte de `inicio_do_mes`, senao a mensagem mente por um dia."""
    hoje = hoje or date.today()
    ano, mes = (hoje.year + 1, 1) if hoje.month == 12 else (hoje.year, hoje.month + 1)
    return '%04d-%02d-01' % (ano, mes)


def teto_de_mesas(limite) -> int:
    """Quantas mesas o plano deixa abrir ao mesmo tempo. `None` no plano = o teto do modo."""
    from leaklab.pratica_preflop import MAX_MESAS
    if limite is None:
        return MAX_MESAS
    return max(1, min(int(limite), MAX_MESAS))


def mesas_permitidas(pedidas, limite) -> int:
    """O clamp do servidor. Existe porque o teto de mesas precisa valer mesmo quando o cliente
    mente: sem isto um POST com `n=4` passa direto e a tela nem fica sabendo."""
    try:
        n = int(pedidas or 1)
    except (TypeError, ValueError):
        n = 1
    return max(1, min(n, teto_de_mesas(limite)))


def cota(user_id: int, hoje: date = None) -> dict:
    """O estado da cota DELE, em uma chamada, no formato que a tela consome.

    `spots_limite` e `spots_restantes` saem `None` quando o plano nao tem teto -- e nao um numero
    grande, que a tela desenharia como barra quase cheia.
    """
    from database.repositories import get_quota_status
    from leaklab.historico_de_pratica import contagem_desde

    status  = get_quota_status(user_id) or {}
    limites = status.get('limits') or {}
    teto_spots = limites.get('practice_spots_per_month')
    mesas = teto_de_mesas(limites.get('practice_tables'))

    usados = contagem_desde(user_id, inicio_do_mes(hoje))
    if teto_spots is None:
        restantes, esgotado = None, False
    else:
        teto_spots = int(teto_spots)
        restantes  = max(0, teto_spots - usados)
        esgotado   = usados >= teto_spots

    return {
        'plano':           status.get('plan') or 'free',
        'mesas':           mesas,
        'spots_limite':    teto_spots,
        'spots_usados':    usados,
        'spots_restantes': restantes,
        'esgotado':        esgotado,
        'renova_em':       renovacao(hoje),
    }
