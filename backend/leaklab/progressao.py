# -*- coding: utf-8 -*-
"""
ESPINHA DE MEDICAO DO TRILHO LENTO — Protocolo de Progressao, Fase 1.

`specs/protocolo-progressao.md` §5 e §12.1. A propria spec diz: "se isto nao funcionar, nada do
resto importa". E o que decide se o produto pode dizer "voce melhorou NO JOGO REAL".

── ESTE MODULO NAO FAZ ESTATISTICA. Ele PREPARA os numeros para `leaklab/validation.py` ───────────

A regra estatistica (Wilson, shrinkage de winner's curse, intervalo de Newcombe na diferenca,
vereditos, `should_reopen`) mora em `leaklab/validation.py` e ja estava viva antes desta fase. A
primeira versao deste arquivo reimplementou tudo aquilo — a duplicata exata que este projeto pune
mais, e pior: comparava o intervalo da janela recente contra um PONTO, ignorando a incerteza do
proprio baseline, quando `validation.newcombe_diff` compara as duas proporcoes corretamente.

A divisao ficou assim, e ela e a razao de os dois arquivos existirem:

    validation.py  — so matematica. Recebe CONTAGENS (erros/n antes e depois) e devolve veredito.
                     Nao toca banco, nao sabe o que e um leak.
    progressao.py  — a ponte. Converte DECISOES em contagens, aplicando a politica de cobertura
                     (`familia_spot`), e devolve tambem o que a contagem nao diz: cobertura de EV,
                     EV medio winsorizado, e quantas decisoes ficaram de fora por qual motivo.

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

# Wilson, shrinkage e comparacao vem de `validation.py`. Reexportados aqui por conveniencia de
# quem ja importa este modulo — mas o dono e la, e nao ha uma segunda implementacao.
from leaklab.validation import (wilson as _wilson_lcs, shrink, validate_leak,  # noqa: F401
                                should_reopen, V_MELHOROU, V_PIOROU,
                                V_SEM_AMOSTRA, V_SEM_MUDANCA, VERDICT_LABEL,
                                SHRINK_PSEUDO_N, VALIDATION_MIN_N, BASELINE_MIN_N)


def wilson(k: int, n: int) -> tuple:
    """(baixo, alto) de Wilson. Fachada sobre `validation.wilson`, que devolve (baixo, centro, alto).

    Existe so porque a serie temporal quer a banda e nao o centro. `n=0` devolve (0.0, 1.0): nao
    saber nada e o intervalo inteiro, nunca um zero — familia vazia nao pode parecer perfeita.
    """
    if not n:
        return 0.0, 1.0
    baixo, _centro, alto = _wilson_lcs(k, n)
    return baixo, alto


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
        'taxa_encolhida': (round(shrink(erros, n, taxa_populacional)[0]
                                 / shrink(erros, n, taxa_populacional)[1], 4)
                           if taxa_populacional is not None else None),
        'n_com_ev': len(com_ev),
        'cobertura_ev_pct': round(100.0 * len(com_ev) / n, 1) if n else None,
        'ev_medio_winsorizado': round(sum(com_ev) / len(com_ev), 3) if com_ev else None,
        'fora_por_motivo': dict(fora),
        'pode_afirmar': n >= MIN_DECISOES_VALIDACAO,
    }


def comparar_janelas(baseline: dict, recente: dict, taxa_global: float) -> dict:
    """Veredito do trilho lento entre duas janelas. Delega a `validation.validate_leak`.

    Nao ha regra estatistica aqui de proposito. A primeira versao desta funcao tinha a sua propria
    (comparava o intervalo de Wilson da janela recente contra o baseline encolhido como PONTO), e
    isso era duplicata E pior: ignorava a incerteza do baseline. `validate_leak` usa o intervalo de
    Newcombe sobre a DIFERENCA, que e o teste correto entre duas proporcoes, e ja governa o estado
    do leak em `progression.state_for` desde antes desta fase.

    `taxa_global` e a taxa de erro do jogador no geral — a ancora do shrinkage de winner's curse.
    """
    b = baseline or {}
    r = recente or {}
    return validate_leak(int(b.get('n_erros') or 0), int(b.get('n') or 0),
                         int(r.get('n_erros') or 0), int(r.get('n') or 0),
                         float(taxa_global or 0.0))


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
