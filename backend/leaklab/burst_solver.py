# -*- coding: utf-8 -*-
"""Decisão de burst do solver: quando criar um box extra, quando destruí-lo.

Lógica PURA e separada do script de host (`scripts/burst_do_solver.py`) de propósito: a regra
que decide gastar dinheiro tem teste na suíte; o script só executa o que ela mandar.

── O modelo (02/09) ────────────────────────────────────────────────────────────────────────

Hetzner cobra por hora ARREDONDADA PRA CIMA e só para de cobrar quando o server é DELETADO.
Então: subir cedo demais desperdiça, descer cedo demais desperdiça (a hora corrente já foi
paga — descer aos 20min de hora cheia joga fora 40min pagos). A histerese aqui encode isso:

- SOBE quando pending >= ALTO (backlog que a base não drena em tempo razoável).
- DESCE quando pending <= BAIXO **e** o burst completou ao menos MIN_MINUTOS de vida —
  não pela hora cheia (otimização frágil), mas para não bater create/delete em flapping.
- Nunca mais que MAX_BURST extras. Base NUNCA entra na conta de destruição.

Calibração inicial (medida 02/09): base drena ~150-300 spots/h com max_solves=2.
ALTO=400 ≈ mais de 1h de fila só na base; BAIXO=50 ≈ a base termina sozinha em minutos.
"""
from __future__ import annotations

from dataclasses import dataclass

PENDING_ALTO = 400
PENDING_BAIXO = 50
MAX_BURST = 1
MIN_MINUTOS_DE_VIDA = 20


@dataclass
class Decisao:
    acao: str          # 'subir' | 'descer' | 'manter'
    motivo: str


def decidir(pending: int, bursts_ativos: int, minutos_do_mais_novo: float = 0.0,
            alto: int = PENDING_ALTO, baixo: int = PENDING_BAIXO,
            max_burst: int = MAX_BURST,
            min_minutos: int = MIN_MINUTOS_DE_VIDA) -> Decisao:
    """Uma decisão por chamada; o chamador executa e volta a perguntar no próximo tick."""
    if pending >= alto and bursts_ativos < max_burst:
        return Decisao('subir', f'pending={pending} >= {alto} e {bursts_ativos}/{max_burst} bursts')
    if bursts_ativos > 0 and pending <= baixo:
        if minutos_do_mais_novo < min_minutos:
            return Decisao('manter', f'pending={pending} baixo, mas burst tem só '
                                     f'{minutos_do_mais_novo:.0f}min (< {min_minutos}) — anti-flapping')
        return Decisao('descer', f'pending={pending} <= {baixo} com burst de '
                                 f'{minutos_do_mais_novo:.0f}min')
    return Decisao('manter', f'pending={pending}, bursts={bursts_ativos}')
