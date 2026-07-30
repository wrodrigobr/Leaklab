# -*- coding: utf-8 -*-
"""
FAMILIA DE SPOT — a chave de agregacao da validacao no jogo real (Protocolo de Progressao, Fase 0).

Fonte unica. `spec/protocolo-progressao.md` §3 e §12.0.

── Por que familia e nao spot canonico ────────────────────────────────────────────────────────────

O spot canonico (posicao × bucket × prev_action × sizing × board) e otimo para o DRILL, onde a
amostra e infinita. Para validar no jogo real ele e inutilizavel: a spec mediu 190 familias com
mediana de 6 decisoes numa granularidade JA mais grossa que a canonica. Validar no canonico levaria
de muitos meses a nunca.

── A eleicao de bucket, e por que "unificar num so" seria errado ──────────────────────────────────

A Fase 0 da spec pede "eleger e unificar UM esquema de stack bucket". Medido, os dois esquemas que
coexistem NAO sao versoes rivais da mesma coisa — respondem a perguntas diferentes:

  `preflop_gto_ranges._DEFAULT_BUCKETS` (10/14/17/20/30/40/50/75/100bb) e **chave de LOOKUP**: cada
  label e uma profundidade para a qual EXISTE solucao no arquivo de ranges. Nao e particao
  arbitraria. Colapsa-la nas 5 faixas grossas faria um stack de 19bb procurar a solucao de 10bb.

  `gto_utils.STACK_BUCKETS` (0-10/10-20/20-35/35-60/60+) e **particao de AGREGACAO**, para relatorio
  e serie temporal.

Entao o que se elege nao e "um esquema para tudo", e sim **qual esquema serve a chave de familia** —
e a resposta e o GROSSO, por medicao. Medido em producao em 2026-07-30 (9216 decisoes):

    GROSSO (5 faixas):  910 familias | mediana 3 dec/familia | 118 (13,0%) com >=20 decisoes
    FINO   (9 faixas): 1391 familias | mediana 2 dec/familia |  90 ( 6,5%) com >=20 decisoes

O fino cortaria as familias validaveis em 24%. O lookup continua usando o fino, e isso agora e
declaracao, nao acidente.

── A descoberta que a spec nao previu: o CENARIO pesa mais que o bucket ───────────────────────────

A validacao e POR USUARIO, e nesse denominador a granularidade do cenario domina. Medido em
producao, familias com >=20 decisoes por usuario:

    cenario por POSICAO do vilao:  user 3 -> 48 | user 43 -> 28 | user 28 ->  1 | user 26 -> 0
    cenario LARGO (rfi/vs_rfi):    user 3 -> 59 | user 43 -> 47 | user 28 -> 11 | user 26 -> 5

Trocar o cenario de fino para largo levou o user 28 de 1 para 11 familias validaveis, e o numero de
usuarios com ALGUMA familia validavel de 3 para 4 de 8. A troca de bucket, comparada, mexe pouco.
Por isso a familia usa cenario LARGO, e a posicao do vilao fica fora dela (vive no spot canonico,
onde a amostra aguenta).

── Limite honesto, para o produto dizer em vez de esconder ────────────────────────────────────────

Mesmo com as duas escolhas grossas, quem tem 258 decisoes tem ZERO familia validavel. O selo
"comprovado no jogo" nao e alcancavel para a maior parte da base hoje. `familias_validaveis` existe
para a superficie poder dizer "ainda nao da para afirmar", que e o mesmo criterio de honestidade do
card de tendencia de EV.
"""
from __future__ import annotations

# Amostra minima para uma familia sustentar afirmacao estatistica no jogo real (spec §5).
MIN_DECISOES_VALIDACAO = 20

# Teto de plausibilidade do EV perdido por decisao, em bb, aplicado ANTES de qualquer media.
#
# Winsorizacao, nao descarte: um no GTO degenerado (bug do pot em fichas, `ev_bb` na casa de
# milhares) dentro de uma familia destroi a serie inteira, e ainda existem residuais em producao.
# Descartar o outlier esconderia a decisao; capar mantem ela contando como erro grande sem deixar
# um unico valor absurdo definir a media da familia.
#
# 25bb e o limite: uma decisao preflop nao perde mais que o stack, e stack efetivo acima disso
# raramente esta todo em jogo numa decisao. Ver [[reference_ev_scale_trust]] — a escala do EV do
# solver vem do pote solvado e pode chegar com sinal invertido, entao teto aqui e obrigatorio.
TETO_EV_WINSOR_BB = 25.0


def bucket_de_agregacao(stack_bb: float | None) -> str | None:
    """Faixa GROSSA de stack, para a chave de familia e para a serie temporal.

    Delega a `gto_utils.STACK_BUCKETS` — a particao mora la e ter uma segunda copia aqui e o erro
    que este projeto ja pagou varias vezes. NAO usar para lookup de solucao: para isso a chave e
    `preflop_gto_ranges._stack_bucket`, que snapa para uma profundidade SOLVADA.
    """
    if stack_bb is None:
        return None
    from leaklab.gto_utils import STACK_BUCKETS
    s = float(stack_bb)
    for lo, hi, label in STACK_BUCKETS:
        if lo <= s < hi:
            return label
    return STACK_BUCKETS[-1][2]


def cenario_largo(street: str | None, vs_position: str | None,
                  is_3bet: bool | None = None) -> str:
    """Cenario da decisao, na granularidade LARGA que a medicao elegeu.

    Preflop: `rfi` (ninguem abriu antes) / `vs_rfi` (respondendo a uma abertura) / `vs_3bet`.
    Postflop: o proprio street, que ja e a distincao que importa numa familia larga.

    A posicao do vilao NAO entra: medido, incluir ela derruba as familias validaveis do user 28 de
    11 para 1. Ela vive no spot canonico, onde a amostra do drill aguenta a granularidade.
    """
    st = (street or '').strip().lower()
    if st and st != 'preflop':
        return st
    if is_3bet:
        return 'vs_3bet'
    return 'vs_rfi' if vs_position else 'rfi'


def familia_de(street: str | None, position: str | None, stack_bb: float | None,
               vs_position: str | None = None, is_3bet: bool | None = None) -> str | None:
    """Chave canonica da familia: `street|cenario|posicao|bucket`.

    Devolve None quando falta qualquer componente. Falhar FECHADO e obrigatorio: uma familia com
    componente vazio agruparia decisoes que nao pertencem juntas, e a serie de EV dela seria uma
    media de coisas diferentes — do tipo de numero confiante e falso que a regra 1 do CLAUDE.md
    proibe.
    """
    st = (street or '').strip().lower()
    pos = (position or '').strip().upper()
    bucket = bucket_de_agregacao(stack_bb)
    if not st or not pos or not bucket:
        return None
    return f'{st}|{cenario_largo(street, vs_position, is_3bet)}|{pos}|{bucket}'


def winsorizar_ev(ev_loss_bb: float | None,
                  stack_bb: float | None = None) -> float | None:
    """EV perdido capado, para entrar em media/soma de familia.

    Dois tetos, e o mais apertado vence: o absoluto (`TETO_EV_WINSOR_BB`) e o stack do heroi
    quando conhecido, porque nao se perde mais fichas do que se tem. Sem o segundo, um `ev_loss_bb`
    de 41604bb num stack de 11,7bb passava — foi exatamente o que meu backfill de EV escreveu 439
    vezes ao chamar o guarda sem o parametro de equity, e o teto de fold devolveu None em silencio.
    """
    if ev_loss_bb is None:
        return None
    v = abs(float(ev_loss_bb))
    teto = TETO_EV_WINSOR_BB
    if stack_bb is not None:
        try:
            teto = min(teto, float(stack_bb))
        except (TypeError, ValueError):
            pass
    return round(min(v, teto), 3)


def familias_validaveis(contagem_por_familia: dict) -> list:
    """Familias com amostra suficiente para afirmar algo, ordenadas pela maior amostra.

    O que NAO esta aqui e tao importante quanto o que esta: familia abaixo do minimo nao vira 0 nem
    vira "sem leak" — ela fica FORA, e a superficie diz "ainda nao da para afirmar". Celula sem dado
    virando zero e o erro que o relatorio de evolucao ja documenta.
    """
    return sorted([f for f, n in (contagem_por_familia or {}).items()
                   if (n or 0) >= MIN_DECISOES_VALIDACAO],
                  key=lambda f: -contagem_por_familia[f])
