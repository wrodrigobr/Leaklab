"""
validation.py — o trilho LENTO do Protocolo: provar no JOGO REAL que o leak foi corrigido.

Este módulo é só matemática. Não toca banco, não sabe o que é um leak: recebe contagens de
erro (antes/depois) e devolve um veredito honesto. Assim ele é testável de verdade, e a
regra estatística fica num lugar só.

Por que taxa de ERRO e não média de EV
--------------------------------------
EV perdido tem cauda pesada: uma mão de −18bb domina 30 mãos de −0,2bb e faz a média oscilar
sem que nada tenha mudado no jogo. Taxa de erro é binomial — tem intervalo de confiança
conhecido, e é a pergunta que o jogador realmente faz ("eu ainda erro isso?").

As três correções de honestidade
--------------------------------
1. **Shrinkage do baseline (winner's curse).** O leak entrou no plano por ser o PIOR de uma
   lista. Escolher o extremo de uma amostra enviesa a medida: parte do "antes" ruim é azar,
   não hábito. Sem correção, o jogador melhora no papel só por regressão à média — e a
   plataforma mente pra ele. Puxamos o baseline em direção à taxa GLOBAL do próprio jogador,
   com peso equivalente a `SHRINK_PSEUDO_N` observações (prior Beta centrado no global).

2. **Intervalo de confiança na DIFERENÇA (Newcombe).** Comparar dois percentuais soltos
   ("era 62%, agora é 71%") não diz nada com 14 e 19 mãos. O veredito só sai quando o
   intervalo da diferença não cruza o zero.

3. **ICM fora da conta.** Decidido na auditoria: o grading é chipEV puro e não temos ranges de
   ICM. Validar correção com mãos de bolha compararia o jogador contra um gabarito que não
   vale ali. O filtro é aplicado por quem consulta o banco; aqui só documentamos que o `n`
   recebido já vem limpo.

O que este módulo NUNCA faz: dizer que o treino CAUSOU a melhora. Ele compara dois períodos.
Causa exigiria grupo de controle, e inventar isso seria pior que não medir.
"""
from __future__ import annotations

import math

# ── Parâmetros ───────────────────────────────────────────────────────────────────────────────
WILSON_Z          = 1.96   # 95% — o padrão; mudar isto muda o rigor de TODO veredito
SHRINK_PSEUDO_N   = 20     # peso do prior no shrinkage: ~20 mãos de "opinião" antes do dado
VALIDATION_MIN_N  = 12     # amostra mínima do DEPOIS pra abrir o veredito (abaixo: sem amostra)
BASELINE_MIN_N    = 8      # sem um "antes" mínimo não há do que partir

# Veredito do trilho lento
V_SEM_AMOSTRA  = 'sem_amostra'    # ainda não jogou o suficiente pra dizer
V_MELHOROU     = 'melhorou'       # a queda na taxa de erro resiste ao intervalo
V_SEM_MUDANCA  = 'sem_mudanca'    # indistinguível de ruído (NÃO é "não melhorou")
V_PIOROU       = 'piorou'         # regressão real — reabre o leak

VERDICT_LABEL = {
    V_SEM_AMOSTRA: 'Ainda sem amostra no jogo',
    V_MELHOROU:    'Melhorou no jogo',
    V_SEM_MUDANCA: 'Sem diferença mensurável',
    V_PIOROU:      'Regrediu no jogo',
}


def wilson(k: int, n: int, z: float = WILSON_Z) -> tuple[float, float, float]:
    """Intervalo de Wilson para uma proporção. Devolve (baixo, centro, alto).

    Wilson e não a aproximação normal porque com n pequeno ou p perto de 0/1 a normal produz
    intervalos absurdos (inclusive negativos) — exatamente o regime em que este produto opera:
    um jogador de MTT tem 9-30 decisões por família, não 500.
    """
    if n <= 0:
        return (0.0, 0.0, 1.0)
    p = k / n
    z2 = z * z
    denom = 1 + z2 / n
    centro = (p + z2 / (2 * n)) / denom
    margem = (z * math.sqrt(p * (1 - p) / n + z2 / (4 * n * n))) / denom
    return (max(0.0, centro - margem), centro, min(1.0, centro + margem))


def shrink(k: int, n: int, p_global: float, pseudo_n: int = SHRINK_PSEUDO_N) -> tuple[float, float]:
    """Puxa a taxa observada em direção à taxa global do jogador (prior Beta).

    Devolve (k_ajustado, n_ajustado) — contagens EFETIVAS, não só a proporção, pra que o
    intervalo de confiança seja calculado sobre elas e reflita o prior.

    Efeito prático: um baseline de 8/10 (80% de erro) com global de 30% e prior de 20 vira
    (8+6)/(10+20) = 46,7%. A melhora que o jogador vai precisar mostrar é bem menor de fingir.
    """
    if n <= 0:
        return (pseudo_n * p_global, float(pseudo_n))
    return (k + pseudo_n * p_global, float(n + pseudo_n))


def newcombe_diff(k1: float, n1: float, k2: float, n2: float,
                  z: float = WILSON_Z) -> tuple[float, float]:
    """IC de 95% para a diferença p1 − p2 (método 10 de Newcombe, score/Wilson).

    Escolhido em vez do z-teste de duas proporções porque mantém cobertura decente com amostra
    pequena e nunca devolve limite fora de [-1, 1]. Aceita contagens fracionárias (o baseline
    chega aqui já ajustado pelo shrinkage).
    """
    if n1 <= 0 or n2 <= 0:
        return (-1.0, 1.0)
    l1, _, u1 = wilson(k1, n1, z)
    l2, _, u2 = wilson(k2, n2, z)
    p1, p2 = k1 / n1, k2 / n2
    lo = (p1 - p2) - math.sqrt((p1 - l1) ** 2 + (u2 - p2) ** 2)
    hi = (p1 - p2) + math.sqrt((u1 - p1) ** 2 + (p2 - l2) ** 2)
    return (max(-1.0, lo), min(1.0, hi))


def validate_leak(erros_antes: int, n_antes: int,
                  erros_depois: int, n_depois: int,
                  taxa_global: float) -> dict:
    """Veredito do trilho lento para UMA família de spot.

    `erros_*` = decisões marcadas como erro pelo gabarito; `n_*` = decisões com gabarito
    (já sem ICM). `taxa_global` = taxa de erro do jogador no geral, âncora do shrinkage.

    Devolve o veredito COM os números que o sustentam — o jogador tem direito de ver por que a
    plataforma disse o que disse, e a mesma estrutura alimenta a reabertura automática.
    """
    saida = {
        'n_antes': n_antes, 'n_depois': n_depois,
        'taxa_antes':  round((erros_antes / n_antes) * 100, 1) if n_antes else None,
        'taxa_depois': round((erros_depois / n_depois) * 100, 1) if n_depois else None,
        'taxa_global': round(taxa_global * 100, 1),
    }

    if n_antes < BASELINE_MIN_N:
        saida.update({'veredito': V_SEM_AMOSTRA, 'motivo': 'baseline_curto',
                      'label': VERDICT_LABEL[V_SEM_AMOSTRA]})
        return saida
    if n_depois < VALIDATION_MIN_N:
        saida.update({'veredito': V_SEM_AMOSTRA, 'motivo': 'depois_curto',
                      'faltam': VALIDATION_MIN_N - n_depois,
                      'label': VERDICT_LABEL[V_SEM_AMOSTRA]})
        return saida

    k_aj, n_aj = shrink(erros_antes, n_antes, taxa_global)
    saida['taxa_antes_ajustada'] = round((k_aj / n_aj) * 100, 1)

    # diferença = antes − depois. Positiva significa "errava mais antes", ou seja, melhorou.
    lo, hi = newcombe_diff(k_aj, n_aj, erros_depois, n_depois)
    saida['ic_diferenca'] = [round(lo * 100, 1), round(hi * 100, 1)]

    if lo > 0:
        v = V_MELHOROU
    elif hi < 0:
        v = V_PIOROU
    else:
        v = V_SEM_MUDANCA
    saida.update({'veredito': v, 'label': VERDICT_LABEL[v]})
    return saida


def should_reopen(validacao: dict | None) -> bool:
    """Reabrir o leak quando o JOGO REAL contradiz o domínio de treino.

    Só a regressão comprovada reabre. `sem_mudanca` NÃO reabre: ausência de prova de melhora
    não é prova de piora, e reabrir por isso puniria quem apenas ainda não jogou o bastante —
    o jogador desistiria do protocolo por um resultado que a estatística nem afirma.
    """
    return bool(validacao) and validacao.get('veredito') == V_PIOROU
