# -*- coding: utf-8 -*-
"""
ESPINHA DE MEDICAO DO TRILHO LENTO — Protocolo de Progressao, Fase 1.

`specs/protocolo-progressao.md` §5 e §12.1. A propria spec diz: "se isto nao funcionar, nada do
resto importa". E o que decide se o produto pode dizer "voce melhorou NO JOGO REAL".

── Metrica primaria: taxa de erro, nao media de EV ────────────────────────────────────────────────

EV perdido por decisao e zero-inflado e de cauda pesada: a maioria das decisoes custa ~0 e poucas
custam muito. Media com IC gaussiano em n=20 e fragil e sensivel a um unico outlier — inclusive aos
13 nos degenerados que ainda existem em producao. A taxa de erro e binomial, e o intervalo de
Wilson se comporta bem com amostra pequena.

── O erro e HERDADO do veredito, nao redefinido aqui ──────────────────────────────────────────────

A spec dizia "proporcao de decisoes com `ev_loss_bb > limiar`". Medido, herdar o veredito de 3
niveis (`verdict.is_error`, dirigido pela severidade `label`) e melhor por dois motivos:

  1. **Cobertura.** `label` existe nas 9216 decisoes de producao; `ev_loss_bb` existe em 5780
     (62,7%). Redefinir por limiar de EV jogaria fora um terco da evidencia — e a taxa de erro e
     justamente a metrica que precisa de amostra.
  2. **Consistencia.** O aluno ja VE aquele veredito no card. Uma segunda definicao de "erro",
     com outra regua, criaria dois numeros discordando na cara dele — que e o antipadrao que este
     projeto ja pagou caro (ver o invariante de veredito consistente).

O EV medio continua exibido porque magnitude importa, mas com `ev_loss_bb` winsorizado e com a
COBERTURA declarada ao lado: "medido em X% das suas decisoes deste tipo".

── Winner's curse: por que o baseline precisa ENCOLHER ────────────────────────────────────────────

O Top-3 de leaks e selecionado por EV extremo. Entao o baseline daquela familia esta inflado POR
CONSTRUCAO: parte da "melhora" que viria depois seria regressao a media mesmo que o aluno nao
mudasse nada. Creditar isso como progresso destroi a credibilidade no primeiro mes em que o numero
reverte.

O antidoto e empirical Bayes: encolher a taxa observada em direcao a media populacional daquela
familia, com peso proporcional ao tamanho da amostra do aluno. Com n pequeno, o baseline vira
quase a media populacional; com n grande, quase a observacao dele.

── O que NAO esta aqui, de proposito ──────────────────────────────────────────────────────────────

Nada persiste. `progression_snapshots` e materializacao (performance), nao logica — a spec e
explicita: "o coracao e uma QUERY". Materializar antes de a query estar certa e criar uma segunda
fonte de verdade que envelhece.
"""
from __future__ import annotations

import math

# z de 95%. Nao e configuravel de proposito: um z frouxo transformaria ruido em "comprovado", e a
# escolha do nivel de confianca nao deve ser um parametro que cada superficie ajusta ao seu gosto.
Z_95 = 1.959963985

# Forca do prior no encolhimento (pseudo-observacoes). Com 20 decisoes — o minimo de validacao — o
# baseline fica meio a meio entre o observado e a media populacional. E um freio deliberado: a
# familia mediana tem MUITO menos que isso, e sem freio cada usuario novo pareceria um caso extremo.
FORCA_DO_PRIOR = 20.0


def wilson(k: int, n: int, z: float = Z_95) -> tuple:
    """Intervalo de Wilson para uma proporcao. Devolve (baixo, alto), ambos em [0, 1].

    Wilson e nao a aproximacao normal porque com n pequeno (que e o caso majoritario aqui) a normal
    produz intervalos que saem de [0,1] e que colapsam para largura ZERO quando k=0 ou k=n — ou
    seja, afirmaria certeza absoluta a partir de 5 acertos. Wilson nunca faz isso.

    n = 0 devolve (0.0, 1.0): nao saber nada e um intervalo que cobre tudo, nao um zero.
    """
    if not n:
        return 0.0, 1.0
    p = k / n
    d = 1 + z * z / n
    centro = (p + z * z / (2 * n)) / d
    meia = (z / d) * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return max(0.0, centro - meia), min(1.0, centro + meia)


def encolher_taxa(k: int, n: int, taxa_populacional: float,
                  forca: float = FORCA_DO_PRIOR) -> float:
    """Taxa encolhida em direcao a media populacional (empirical Bayes).

    `(k + forca*pop) / (n + forca)`. Com n pequeno o resultado tende a `taxa_populacional`; com n
    grande tende a `k/n`.

    Existe por causa do winner's curse: o leak entrou no Top-3 porque o numero dele estava extremo,
    e comparar a melhora contra aquele extremo credita regressao a media como progresso. Sem isto,
    o Top-3 recompensa variancia por construcao.
    """
    pop = min(max(float(taxa_populacional or 0.0), 0.0), 1.0)
    if n <= 0:
        return pop
    return (k + forca * pop) / (n + forca)


def taxa_de_erro(decisoes, taxa_populacional: float | None = None) -> dict:
    """Taxa de erro de um conjunto de decisoes (uma familia, numa janela).

    Cada decisao e um dict com `gto_label`, `label`, `spot_family_key`, `ev_loss_bb`, `stack_bb` e
    opcionalmente `zona_icm_provada`. Quem decide se ela conta e `familia_spot`, nao este modulo —
    a politica de cobertura tem um dono so.

    Devolve o numero E o que ele nao sabe: intervalo de Wilson, cobertura de EV, e quantas ficaram
    de fora por qual motivo. Taxa sem denominador e sem intervalo e exatamente o "numero confiante
    e falso" que a regra 1 do CLAUDE.md proibe.
    """
    from leaklab.familia_spot import (no_universo_de_medicao, winsorizar_ev,
                                      MIN_DECISOES_VALIDACAO)
    from leaklab.verdict import is_error
    from collections import Counter

    dentro, erros, fora = [], 0, Counter()
    for d in (decisoes or []):
        ok, motivo = no_universo_de_medicao(
            gto_label=d.get('gto_label'), zona_icm_provada=d.get('zona_icm_provada'),
            spot_family_key=d.get('spot_family_key'))
        if not ok:
            fora[motivo] += 1
            continue
        dentro.append(d)
        if is_error(d.get('label')):
            erros += 1

    n = len(dentro)
    # EV so entra na MAGNITUDE, com cobertura propria — e menor que a da taxa de erro (62,7% contra
    # 85,8% em producao), e misturar as duas coberturas num numero so esconderia isso.
    com_ev = [winsorizar_ev(d.get('ev_loss_bb'), d.get('stack_bb'))
              for d in dentro if d.get('ev_loss_bb') is not None]
    baixo, alto = wilson(erros, n)

    return {
        'n': n,
        'n_erros': erros,
        'taxa': round(erros / n, 4) if n else None,
        'wilson_baixo': round(baixo, 4),
        'wilson_alto': round(alto, 4),
        'taxa_encolhida': (round(encolher_taxa(erros, n, taxa_populacional), 4)
                           if taxa_populacional is not None else None),
        'n_com_ev': len(com_ev),
        'cobertura_ev_pct': round(100.0 * len(com_ev) / n, 1) if n else None,
        'ev_medio_winsorizado': round(sum(com_ev) / len(com_ev), 3) if com_ev else None,
        'fora_por_motivo': dict(fora),
        'pode_afirmar': n >= MIN_DECISOES_VALIDACAO,
    }


def melhorou_de_verdade(baseline: dict, recente: dict,
                        taxa_populacional: float | None = None) -> tuple:
    """A familia melhorou ALEM do ruido? Devolve (veredito, motivo).

    Tres condicoes, e todas tem que valer:

      1. A janela recente tem amostra (`pode_afirmar`). Sem isso nao ha o que comparar.
      2. O baseline foi ENCOLHIDO para a media populacional antes da comparacao (winner's curse).
      3. O teto do intervalo de Wilson da janela recente fica ABAIXO do baseline encolhido. Comparar
         ponto contra ponto declararia melhora em metade dos casos por sorteio; exigir que o
         intervalo INTEIRO esteja abaixo e o que separa sinal de variancia.

    Devolve `('indefinido', motivo)` quando nao da para afirmar — nunca `False` disfarcado de
    "nao melhorou". As duas coisas sao diferentes e a tela precisa distingui-las: "ainda estou
    coletando" nao e "voce nao melhorou".

    ── QUANDO passar `taxa_populacional`, e por que isso NAO e detalhe ────────────────────────────

    Passe **somente quando a familia foi SELECIONADA por ser extrema** — o leak do Top-3, o que
    esta em validacao. E para esse caso que o encolhimento existe: o baseline dele esta inflado por
    construcao, e comparar contra o extremo credita regressao a media como progresso.

    Aplicar em TODA familia introduz vies, e ele foi medido. Varrendo as 504 familias dos dois
    usuarios com mais volume, com encolhimento em todas: **12 "piorou" contra 3 "melhorou"**. O
    mecanismo e simetrico e obvio depois de visto: o encolhimento puxa baseline BAIXO para cima
    (facilitando "piorou") e baseline ALTO para baixo (dificultando "melhorou"). Numa familia que
    nao foi escolhida por extremidade, nao ha winner's curse para corrigir, e a correcao vira
    distorcao.

    Sem `taxa_populacional`, o baseline encolhe em direcao a si mesmo, ou seja, nao encolhe — que e
    o comportamento certo para monitoramento geral.
    """
    if not recente or not recente.get('pode_afirmar'):
        return 'indefinido', 'amostra insuficiente na janela recente'
    if not baseline or not baseline.get('n'):
        return 'indefinido', 'sem baseline para comparar'

    pop = taxa_populacional if taxa_populacional is not None else baseline.get('taxa')
    base_encolhida = encolher_taxa(baseline['n_erros'], baseline['n'], pop)

    if recente['wilson_alto'] < base_encolhida:
        return 'melhorou', (f"teto do intervalo recente ({recente['wilson_alto']:.1%}) abaixo do "
                            f"baseline encolhido ({base_encolhida:.1%})")
    if recente['wilson_baixo'] > base_encolhida:
        return 'piorou', (f"piso do intervalo recente ({recente['wilson_baixo']:.1%}) acima do "
                          f"baseline encolhido ({base_encolhida:.1%})")
    return 'indefinido', 'o intervalo recente ainda cobre o baseline encolhido'


def progresso_de_coleta(n_atual: int, minimo: int | None = None) -> dict:
    """Progresso da COLETA de amostra, que e o que a tela mostra durante a espera.

    A spec (§5) e explicita sobre isto: com gate honesto, um aluno de 5 torneios por mes veria
    "validando..." por semanas e o produto pareceria morto. O que avanca toda semana e a coleta,
    entao e ela que aparece — "validacao: 14 de 20 decisoes reais coletadas". Ela nao promete
    melhora e ensina sobre variancia pelo caminho.
    """
    from leaklab.familia_spot import MIN_DECISOES_VALIDACAO
    alvo = int(minimo or MIN_DECISOES_VALIDACAO)
    n = max(0, int(n_atual or 0))
    return {
        'coletadas': n,
        'alvo': alvo,
        'faltam': max(0, alvo - n),
        'pct': round(min(100.0, 100.0 * n / alvo), 1) if alvo else None,
        'completo': n >= alvo,
    }
