"""
llm_explainer.py — Ciclo 2
Gera explicações em português para decisões analisadas pelo engine.

Estratégia:
  - Decisões com erro (small_mistake / clear_mistake): 1 chamada batch ao LLM
  - Decisões standard / marginal sem math penalty: template Python (sem custo)
  - Cache por hash do input: mesma decisão analisada 2x não gera 2a chamada
  - Fallback gracioso: se LLM indisponível, retorna template
"""
from __future__ import annotations
import json
import hashlib
import os
from typing import Dict, List
from leaklab.content_moderation import sanitize_llm_input


def _api_key() -> str:
    """Retorna a chave da API Anthropic da variável de ambiente."""
    key = os.environ.get('ANTHROPIC_API_KEY', '')
    if not key:
        raise RuntimeError(
            'ANTHROPIC_API_KEY não configurada. '
            'Adicione esta variável de ambiente no Render.'
        )
    return key

# Cache em memória (por sessão)
_cache: Dict[str, str] = {}


# ── Entrypoint principal ──────────────────────────────────────────────────────

def explain_decisions(decisions: List[dict]) -> Dict[str, str]:
    """
    Recebe lista de decisões enriquecidas (output do pipeline + engine).
    Retorna dict {decision_key → explicação em português}.

    decision_key = f"{hand_id}_{street}_{index}"
    """
    errors   = [d for d in decisions if d['evaluation']['label']
                in ('small_mistake', 'clear_mistake')]
    standard = [d for d in decisions if d not in errors]

    explanations: Dict[str, str] = {}

    # Decisões sem erro: template local
    for d in standard:
        key = _key(d)
        explanations[key] = _template_standard(d)

    # Decisões com erro: verificar cache primeiro
    to_explain = []
    for d in errors:
        key = _key(d)
        if key in _cache:
            explanations[key] = _cache[key]
        else:
            to_explain.append(d)

    # Chamar LLM para os não cacheados
    if to_explain:
        try:
            llm_results = _call_llm_batch(to_explain)
            for d, explanation in zip(to_explain, llm_results):
                key = _key(d)
                _cache[key] = explanation
                explanations[key] = explanation
        except Exception as e:
            # Fallback: template para todos que não conseguimos explicar
            for d in to_explain:
                key = _key(d)
                explanations[key] = _template_error(d)

    return explanations


# ── LLM call ─────────────────────────────────────────────────────────────────

def _call_llm_api(payload: dict) -> str:
    """Chama a API do Claude com um payload já construído. Retorna texto bruto."""
    import requests as _req
    resp = _req.post(
        'https://api.anthropic.com/v1/messages',
        json=payload,
        headers={
            'Content-Type':      'application/json',
            'anthropic-version': '2023-06-01',
            'x-api-key':         _api_key(),
        },
        timeout=90,
    )
    resp.raise_for_status()
    data = resp.json()
    return ''.join(
        block['text'] for block in data.get('content', [])
        if block.get('type') == 'text'
    ).strip()


def _call_llm_batch(decisions: List[dict]) -> List[str]:
    """
    Faz uma única chamada ao Haiku com todas as decisões com erro.
    Retorna lista de explicações na mesma ordem.
    """
    import requests as _req
    payload = _build_payload(decisions)
    resp = _req.post(
        'https://api.anthropic.com/v1/messages',
        json=payload,
        headers={
            'Content-Type':      'application/json',
            'anthropic-version': '2023-06-01',
            'x-api-key':         _api_key(),
        },
        timeout=90,
    )
    resp.raise_for_status()
    data = resp.json()
    raw_text = ''.join(
        block['text'] for block in data.get('content', [])
        if block.get('type') == 'text'
    )
    return _parse_llm_response(raw_text, len(decisions))


_ICM_MULTIPLIER = {"low": 1.00, "medium": 1.15, "high": 1.30, "bubble": 1.50}
_REV_IMPL_ADJ_PP = {"low": 0.0, "medium": 3.0, "high": 6.0}


def _rev_impl_tier(pct: float) -> str:
    if pct <= 10: return "low"
    if pct <= 20: return "medium"
    return "high"


def _m_zone(m_ratio) -> str:
    try:
        m = float(m_ratio)
        if m < 6:   return "push_fold"
        if m <= 12: return "pressure"
        return "normal"
    except (TypeError, ValueError):
        return "normal"


def _action_warning(action: str, zone: str) -> str:
    act = action.lower()
    if zone == "push_fold" and any(x in act for x in ["call", "minraise", "raise"]):
        return "⚠️ AÇÃO INVÁLIDA PARA M<6 — apenas shove ou fold são válidos"
    if zone == "pressure" and "call" in act and "allin" not in act:
        return "⚠️ CALL ESPECULATIVO COM M 6-12 — risco estrutural"
    return ""


def _build_payload(decisions: List[dict]) -> dict:
    """Monta payload para análise profunda. Retorna Markdown estruturado."""

    def _board_for_street(street, board):
        if street == 'preflop': return []
        if street == 'flop':    return board[:3]
        if street == 'turn':    return board[:4]
        return board

    def _suit(c):
        return {'s':'♠','h':'♥','d':'♦','c':'♣'}.get(c[-1].lower(),'') if c and len(c)>=2 else ''

    def _fmt_card(c):
        return (c[:-1] + _suit(c)) if c and len(c) >= 2 else (c or '')

    def _fmt_cards(lst):
        return ' '.join(_fmt_card(c) for c in lst) if lst else '—'

    system_prompt = """Você é um coach de poker MTT de elite. Analise as decisões e escreva em TEXTO CORRIDO estruturado — NÃO retorne JSON, NÃO use chaves {}, NÃO use colchetes [].

════════════════════════════════════════
BLOCO 1 — FILTRO OBRIGATÓRIO DE M-RATIO
════════════════════════════════════════

ANTES de qualquer análise, aplique este filtro baseado no M-Ratio:

- M < 6  → Modo push/fold puro. Qualquer raise convencional ou call sem ser all-in é erro estrutural.
           A análise deve começar com: "⚠️ Com M=[valor], o único jogo válido é push/fold."
           Pule a seção Range GTO de RFI/vs RFI — substitua por análise de push/fold range.

- M 6–12 → Zona de pressão. Raise/fold ou shove são as únicas opções válidas. Calls especulativos
           são erros por definição. Mencione isso explicitamente no contexto.

- M > 12 → Jogo normal. Todas as ações são válidas. Análise padrão completa.

════════════════════════════════════════
BLOCO 2 — CÁLCULO DE EQUITY AJUSTADA
════════════════════════════════════════

Os dados já incluem os cálculos completos — use os números EXATOS fornecidos:

1. Equity real ajustada = equity bruta − ajuste de reverse implied odds (já calculado)
2. Equity mínima ICM = pot odds × fator ICM (já calculado)
3. Déficit final = equity mínima ICM − equity real ajustada (já calculado)
4. Se déficit > 0: continuar era matematicamente incorreto. Se déficit < 0: correto.

Mostre a sequência completa na seção 📐 A Matemática.

════════════════════════════════════════
BLOCO 3 — FORMATO DE SAÍDA POR DECISÃO
════════════════════════════════════════

Para cada decisão use EXATAMENTE este formato Markdown:

---
## [número]. [Street] — [ação tomada] era [correto/incorreto], o correto era [ação correta]

### ⚠️ Alerta de Stack (apenas se M < 12)
M-Ratio [valor] — [consequência direta para esta decisão]

### ❌ O Erro
Explique em 3-4 frases o que foi feito de errado e por que é um erro estratégico neste contexto específico. Seja cirúrgico: mencione posição, stack, contexto do torneio e o que o oponente representa.

### 📊 Range GTO (apenas preflop — pule completamente para flop/turn/river)
- **Cenário:** [RFI | vs RFI | vs 3bet | Push/Fold]
- **Mão no range GTO?** [Sim — dentro do top X% | Não — fora do top X%]
- **Ação GTO recomendada:** [raise/fold/call/shove]
- **Análise de range:** [1-2 frases sobre o que o range GTO diz sobre esta mão e posição]
(Se M < 6, substitua por: "Push/fold range: esta mão [está / não está] no range de shove")

### 🎯 GTO Postflop (apenas flop/turn/river — use quando bloco GTO SOLVER presente)
Quando o bloco "── GTO SOLVER ──" estiver presente, use OBRIGATORIAMENTE os dados exatos:
- **Ação principal GTO:** [ação] ([frequência]% do range)
- **Ação do hero:** [ação] ([frequência]% — classificação)
- **Distribuição do range:** liste as ações com frequências exatas do bloco GTO SOLVER
- **Interpretação:** o que a distribuição revela sobre o spot (polar vs merged, bluff catchers, etc.)
- **Divergência:** quantifique o custo da desvio em termos de oportunidade perdida

### 📐 A Matemática
- **Equity estimada:** X% (mão vs range do oponente)
- **Ajuste rev. implied odds:** −Ypp ([sem impacto / leve / relevante])
- **Equity real ajustada:** Z%
- **Pot odds brutas exigem:** W%
- **Fator ICM ([low/medium/high/bubble]):** ×[fator] → equity mínima real: V%
- **Déficit/Superávit:** ±Npp → [fold/call/raise] era [correto/incorreto]
- **EV estimado:** ação tomada ≈ −X BB | ação correta ≈ +Y BB por 100 mãos

### 🧭 O Contexto
- **M Ratio [valor]:** [push/fold puro M<6 | zona de pressão M6-12 | jogo normal M>12] — implicação direta
- **Stack ([valor] BB):** [como este stack afeta as opções disponíveis]
- **ICM [nível] (×[fator]):** [como o ICM inflaciona o custo de erros neste momento]
- **Posição ([posição]):** [como IP/OOP afeta equity realizada e linha correta]
- **Padrão detectado:** [se este erro se repete nesta sessão, mencione aqui]

### ✅ A Ação Correta
**[AÇÃO]** — [explicação completa em 4-5 frases: por que é superior matematicamente, qual o objetivo estratégico, o que acontece contra os diferentes sub-ranges do oponente, como o ICM afeta a escolha]

### 💡 A Lição
[Regra prática memorável e ESPECÍFICA para o padrão deste jogador nesta sessão.
NÃO use conselhos genéricos. USE o contexto real desta sessão.
Use **negrito** para o conceito-chave.]

---

════════════════════════════════════════
BLOCO 4 — SÍNTESE FINAL (após todas as decisões)
════════════════════════════════════════

---
## 📈 Relatório de Padrões — Sessão Completa

### Resumo Executivo
- **Decisões analisadas:** N (X preflop | Y postflop)
- **Erros confirmados:** N (X% das decisões)
- **Custo total estimado:** −Z BB nesta sessão

### Leak Dominante
[Tipo de erro mais frequente com nome técnico e impacto em BB]

### Stack Depth Crítico
[Em qual range de M-Ratio o jogador mais erra e por quê]

### Padrão Posicional
[Em quais posições os erros se concentram — IP vs OOP]

### ICM — Sensibilidade ao Risco
[O jogador ajusta adequadamente ao ICM ou sub/super-ajusta?]

### Top 3 Prioridades de Estudo
1. [Tema mais urgente com exemplo específico desta sessão]
2. [Segundo tema com exemplo]
3. [Terceiro tema com exemplo]

### Estimativa de EV Recuperável
Se corrigir os padrões identificados: **+X BB/torneio estimado**

---

════════════════════════════════════════
REGRAS OBRIGATÓRIAS — NÃO VIOLE
════════════════════════════════════════

1. Escreva SOMENTE texto Markdown — zero JSON, zero chaves {}, zero colchetes []
2. Use os números EXATOS dos dados fornecidos — não arredonde sem indicar
3. Aplique o filtro de M-Ratio ANTES de qualquer análise — nunca ignore
4. Mostre o cálculo ICM como multiplicador matemático — não como label qualitativo
5. Para preflop: use os dados de range GTO fornecidos
6. Para flop/turn/river: pule a seção Range GTO de range tables — use o bloco "── GTO SOLVER ──" quando presente
7. Quando o bloco GTO SOLVER estiver presente, use-o como verdade objetiva na análise — não estime o que o solver diria
8. Nunca mencione "GTO Wizard" — use sempre "GTO Solver"
7. A seção "💡 A Lição" DEVE referenciar padrão específico desta sessão — nunca genérica
8. A síntese "📈 Relatório de Padrões" é obrigatória — não omita mesmo com poucos erros
9. Português do Brasil, tom técnico e direto
10. Termos de poker SEMPRE em inglês: fold, call, raise, bet, check, shove, preflop, flop, turn, river,
    hand, spot, equity, ICM, M-ratio, stack, pot odds, range, 3-bet, c-bet, board, position, IP, OOP,
    push/fold, reverse implied odds, fold equity, EV, +EV, -EV, bluff, value bet
11. Separe cada decisão com ---
12. Seja cirúrgico: "déficit de 18.4pp com ICM high = fold obrigatório" não "equity insuficiente\""""

    decisions_data = []
    error_pattern_tracker: dict = {}

    for i, d in enumerate(decisions):
        ev    = d.get('evaluation', {})
        bd    = ev.get('scoreBreakdown', {})
        ctx   = d.get('context', {})
        mt    = d.get('math', {})
        spot  = d.get('spot', {})
        hp    = d.get('hand_profile', {})
        rng   = d.get('range_evaluation', {})
        pfgto = d.get('preflop_gto', {}) or {}

        street     = d.get('street', 'preflop')
        full_board = d.get('board', [])
        board_now  = _board_for_street(street, full_board)
        hero_cards = d.get('hero_cards', '??')
        action     = d.get('actionTaken', d.get('action_taken', '?'))
        best       = d.get('bestAction',  d.get('best_action',  '?'))

        # Equity pipeline com ICM e reverse implied odds
        eq_est    = round((mt.get('estimatedHandEquity') or 0) * 100, 1)
        pot_odds  = round((mt.get('potOddsEquity') or 0) * 100, 1)
        rev_impl  = round((mt.get('reverseImpliedOddsFactor') or 0) * 100, 1)
        icm       = ctx.get('icmPressure', ctx.get('icm_pressure', 'low'))

        icm_factor   = _ICM_MULTIPLIER.get(icm, 1.00)
        eq_min_icm   = round(pot_odds * icm_factor, 1)
        rev_tier     = _rev_impl_tier(rev_impl)
        rev_adj_pp   = _REV_IMPL_ADJ_PP[rev_tier]
        eq_real      = round(eq_est - rev_adj_pp, 1)
        deficit      = round(eq_min_icm - eq_real, 1)

        # M-Ratio e validação
        m_ratio  = ctx.get('mRatio') or ctx.get('m_ratio', '?')
        stack_bb = ctx.get('heroStackBb') or ctx.get('stack_bb', '?')
        zone     = _m_zone(m_ratio)
        warning  = _action_warning(action, zone)

        position   = spot.get('position') or ctx.get('position', '?')
        hand_class = hp.get('handClass', '?')
        range_zone = rng.get('rangeZone', '?')
        draw       = mt.get('drawProfile', 'none')

        cards_fmt = _fmt_cards([hero_cards[:2], hero_cards[2:]]) if len(hero_cards) >= 4 else hero_cards
        board_fmt = _fmt_cards(board_now) if board_now else '(preflop — sem board)'

        # Rastreamento de padrões recorrentes
        leak_type = rng.get('rangeZone', ev.get('label', 'unknown'))
        error_pattern_tracker[leak_type] = error_pattern_tracker.get(leak_type, 0) + 1
        pattern_note = ''
        if error_pattern_tracker[leak_type] > 1:
            pattern_note = (
                f"\nPadrão recorrente: {leak_type} apareceu "
                f"{error_pattern_tracker[leak_type]}x nesta sessão."
            )

        # Bloco Range GTO preflop
        pfgto_block = ''
        if street == 'preflop' and pfgto.get('available'):
            scenario_label = {
                'rfi':     'RFI (Raise First In)',
                'vs_rfi':  'vs RFI (defendendo abertura)',
                'vs_3bet': 'vs 3bet (respondendo re-raise)',
            }.get(pfgto.get('scenario', ''), pfgto.get('scenario', ''))
            in_rng    = pfgto.get('in_range', False)
            rng_pct   = pfgto.get('range_pct', 0)
            rec_acts  = '/'.join(pfgto.get('recommended_actions', []))
            pro_notes = ' | '.join(pfgto.get('pro_notes', []))
            if zone == 'push_fold':
                pfgto_block = (
                    f"\nRange GTO preflop (Push/Fold M<6):\n"
                    f"  Mão no range de shove: {'SIM' if in_rng else 'NÃO'} "
                    f"(top {rng_pct*100:.0f}% da posição)\n"
                    f"  Ação correta: {'SHOVE' if in_rng else 'FOLD'}\n"
                    f"  Notas: {pro_notes}\n"
                )
            else:
                pfgto_block = (
                    f"\nRange GTO preflop:\n"
                    f"  Cenário: {scenario_label}\n"
                    f"  Mão no range: {'SIM' if in_rng else 'NÃO'} "
                    f"(top {rng_pct*100:.0f}% das mãos)\n"
                    f"  Ação GTO recomendada: {rec_acts}\n"
                    f"  Notas profissionais: {pro_notes}\n"
                )

        # Bloco GTO Solver postflop (batch)
        # Prioridade: campo 'gto' do engine (tem strategy completo) → campos raiz do banco
        gto_solver_block = ''
        gto_dict    = d.get('gto') or {}
        gto_lbl     = gto_dict.get('gto_label')  or d.get('gto_label')
        gto_act     = gto_dict.get('gto_action')  or d.get('gto_action')
        gto_freq_v  = gto_dict.get('gto_freq')
        played_freq_v = gto_dict.get('played_freq')
        strategy_v  = gto_dict.get('strategy') or []
        exploit_v   = gto_dict.get('exploitability')
        gto_source  = gto_dict.get('source', 'postflop_db')

        if street != 'preflop' and (gto_lbl or gto_act):
            lines = ["\n── GTO SOLVER (DADOS OBJETIVOS — USE COMO VERDADE) ──"]

            # Ação principal
            if gto_freq_v is not None:
                lines.append(f"Ação principal GTO: {gto_act} ({round(gto_freq_v * 100, 1)}% de frequência)")
            else:
                lines.append(f"Ação principal GTO: {gto_act}")

            # Frequência da ação jogada
            if played_freq_v is not None:
                lines.append(
                    f"Ação do hero ({action}): {round(played_freq_v * 100, 1)}% de frequência no range GTO"
                )

            # Classificação
            _lbl_map = {
                'gto_correct':         'CORRETO (≥60% de frequência)',
                'gto_mixed':           'MISTO (30–60% — ação alternativa válida)',
                'gto_minor_deviation': 'DESVIO LEVE (10–30%)',
                'gto_critical':        'DESVIO CRÍTICO (<10%)',
            }
            if gto_lbl:
                lines.append(f"Classificação: {_lbl_map.get(gto_lbl, gto_lbl)}")

            # Distribuição completa da estratégia
            if strategy_v:
                lines.append("Distribuição completa da estratégia GTO neste spot:")
                for s in sorted(strategy_v, key=lambda x: float(x.get('frequency', 0)), reverse=True):
                    freq_pct  = round(float(s.get('frequency', 0)) * 100, 1)
                    act_name  = s.get('action', '?')
                    combos    = s.get('combos', '')
                    combo_str = f"  ({combos} combos)" if combos else ""
                    lines.append(f"  • {act_name}: {freq_pct}%{combo_str}")

            # Qualidade do solve
            if exploit_v is not None:
                lines.append(f"Exploitability: {exploit_v:.1f}% (qualidade do solve)")

            lines.append(f"Fonte: {gto_source}")
            gto_solver_block = '\n'.join(lines) + '\n'

        decisions_data.append(
            f"DECISÃO {i+1} de {len(decisions)}:\n"
            f"Cartas: {cards_fmt} | Board no momento: {board_fmt}\n"
            f"Street: {street} | Tomou: {action} | Correto: {best}\n"
            f"{warning}\n"
            f"Label: {ev.get('label','?')} | Score: {ev.get('mistakeScore',0):.3f}\n"
            f"\n── CÁLCULO DE EQUITY ──\n"
            f"Equity bruta estimada: {eq_est}%\n"
            f"Reverse implied odds: {rev_impl}% (tier: {rev_tier}, ajuste: −{rev_adj_pp:.0f}pp)\n"
            f"Equity real ajustada: {eq_real}%\n"
            f"Pot odds brutas exigem: {pot_odds}%\n"
            f"ICM: {icm} → fator ×{icm_factor:.2f} → equity mínima real: {eq_min_icm}%\n"
            f"Déficit final: {deficit:+.1f}pp "
            f"({'fold/pass correto' if deficit > 0 else 'continuar correto'})\n"
            f"\n── CONTEXTO ──\n"
            f"M ratio: {m_ratio} (zona: {zone}) | Stack: {stack_bb} BB | "
            f"ICM: {icm} | Posição: {position}\n"
            f"Draw: {draw} | Classe da mão: {hand_class} | Zona do range: {range_zone}\n"
            f"\n── PENALIDADES ──\n"
            f"gap_base: {bd.get('baseActionGap',0):.3f} | "
            f"math: {bd.get('mathPenalty',0):.3f} | "
            f"range: {bd.get('rangePenalty',0):.3f} | "
            f"contexto: {bd.get('contextPenalty',0):.3f}"
            + pattern_note
            + pfgto_block
            + gto_solver_block
        )

    user_message = (
        "Analise estas " + str(len(decisions)) + " decisão(ões) com erro no poker MTT:\n\n"
        + "\n\n".join(decisions_data)
        + "\n\nEscreva a análise completa em Markdown seguindo o formato especificado. "
        + "Inclua o Relatório de Padrões ao final. APENAS texto Markdown, NUNCA JSON."
    )

    return {
        'model':      'claude-haiku-4-5-20251001',
        'max_tokens': max(1200 * len(decisions), 3000),
        'system':     system_prompt,
        'messages':   [{'role': 'user', 'content': user_message}],
    }


def _parse_llm_response(raw: str, expected: int) -> List[str]:
    """
    Processa resposta Markdown do LLM.
    Divide por --- e retorna lista de seções, uma por decisão.
    """
    import re as _re

    # Limpar possíveis markdown fences residuais
    text = raw.strip()
    text = _re.sub(r'^```[a-z]*\n?', '', text, flags=_re.IGNORECASE)
    text = _re.sub(r'\n?```$', '', text)
    text = text.strip()

    # Tentar dividir por separadores ---
    parts = _re.split(r'\n---+\n', text)
    parts = [p.strip() for p in parts if p.strip() and len(p.strip()) > 50]

    if len(parts) >= expected:
        return parts[:expected]

    # Se não dividiu corretamente, dividir por "## N."
    parts = _re.split(r'(?=^## \d+\.)', text, flags=_re.MULTILINE)
    parts = [p.strip() for p in parts if p.strip() and len(p.strip()) > 50]

    if len(parts) >= expected:
        return parts[:expected]

    # Fallback: retornar tudo como uma única análise
    if len(text) > 50:
        result = [text]
        while len(result) < expected:
            result.append('Análise indisponível para esta decisão.')
        return result[:expected]

    return ['O Coach IA não retornou análise. Tente novamente.'] * expected

# ── Templates locais (sem custo) ──────────────────────────────────────────────

def _template_standard(d: dict) -> str:
    action  = d.get('actionTaken', d.get('action_taken', '?'))
    street  = d.get('street', '?')
    label   = d.get('evaluation', {}).get('label', 'standard')

    if label == 'standard':
        return f"Decisão correta no {_street_pt(street)}. {_action_pt(action).capitalize()} foi a jogada adequada para o spot."
    # marginal
    return f"Decisão aceitável no {_street_pt(street)}, embora exista uma alternativa ligeiramente melhor."


def _template_error(d: dict) -> str:
    """Fallback quando LLM falha."""
    action = d.get('actionTaken', d.get('action_taken', '?'))
    best   = d.get('bestAction',  d.get('best_action',  '?'))
    street = d.get('street', '?')
    score  = d.get('evaluation', {}).get('mistakeScore', 0)
    return (
        f"No {_street_pt(street)}, você optou por {_action_pt(action)} "
        f"quando a jogada esperada era {_action_pt(best)}. "
        f"Score de erro: {score:.3f}."
    )


def _street_pt(street: str) -> str:
    return {'preflop': 'pré-flop', 'flop': 'flop',
            'turn': 'turn', 'river': 'river'}.get(street, street)


def _action_pt(action: str) -> str:
    return {'fold': 'fold', 'check': 'check', 'call': 'call',
            'bet': 'bet', 'raise': 'raise', 'jam': 'shove'}.get(action, action)


def _key(d: dict) -> str:
    hand_id = d.get('handId', d.get('hand_id', d.get('hand_id_full', 'x')))
    street  = d.get('street', 'x')
    action  = d.get('actionTaken', d.get('action_taken', 'x'))
    raw     = f"{hand_id}_{street}_{action}"
    return hashlib.md5(raw.encode()).hexdigest()[:12]


# ── Tournament summary ────────────────────────────────────────────────────────

def generate_tournament_summary(results: list, total_hands: int,
                                 hero: str = 'Hero') -> str:
    """
    Gera um resumo geral do torneio em linguagem natural.
    Uma única chamada ao Haiku com o agregado da sessão.
    Retorna string com o resumo ou fallback template se LLM indisponível.
    """
    ctx = _build_tournament_context(results, total_hands)
    cache_key = _tournament_cache_key(ctx)

    if cache_key in _cache:
        return _cache[cache_key]

    try:
        summary = _call_llm_summary(ctx, hero)
        _cache[cache_key] = summary
        return summary
    except Exception:
        fallback = _template_tournament_summary(ctx, hero)
        return fallback


def _build_tournament_context(results: list, total_hands: int) -> dict:
    """Agrega métricas do torneio para o LLM."""
    from collections import Counter, defaultdict

    if not results:
        return {}

    labels = Counter(r['evaluation']['label'] for r in results)
    total  = len(results)

    # Breakdown por ICM
    icm_groups = defaultdict(list)
    for r in results:
        icm = r.get('context', {}).get('icmPressure', 'low')
        icm_groups[icm].append(r['evaluation']['mistakeScore'])

    icm_breakdown = {}
    for level, scores in icm_groups.items():
        icm_breakdown[level] = {
            'count': len(scores),
            'avg':   round(sum(scores) / len(scores), 4),
        }

    # Top leaks (street × ação, mínimo 2 ocorrências)
    spot_scores = defaultdict(list)
    for r in results:
        street = r.get('street', 'unknown')
        action = r.get('bestAction', r.get('actionTaken', 'unknown'))
        key = f"{street}/{action}"
        spot_scores[key].append(r['evaluation']['mistakeScore'])

    top_leaks = sorted(
        [(k, round(sum(v)/len(v), 3), len(v))
         for k, v in spot_scores.items() if len(v) >= 2],
        key=lambda x: x[1], reverse=True
    )[:4]

    # M ratio range
    m_vals = [r.get('context', {}).get('mRatio') for r in results
              if r.get('context', {}).get('mRatio') is not None]

    return {
        'total_hands':     total_hands,
        'total_decisions': total,
        'avg_score':       round(sum(r['evaluation']['mistakeScore'] for r in results) / total, 4),
        'standard_pct':    round(labels.get('standard', 0) / total * 100, 1),
        'clear_pct':       round(labels.get('clear_mistake', 0) / total * 100, 1),
        'icm_breakdown':   icm_breakdown,
        'top_leaks':       top_leaks,
        'm_min':           round(min(m_vals), 1) if m_vals else None,
        'm_avg':           round(sum(m_vals) / len(m_vals), 1) if m_vals else None,
    }


def _call_llm_summary(ctx: dict, hero: str) -> str:
    """Chama o Haiku para gerar o resumo do torneio."""

    system_prompt = (
        "Você é um coach de poker MTT. "
        "Analise as métricas do torneio abaixo e escreva um resumo em português "
        "de 4 parágrafos completos. "
        "Tom: direto, técnico mas acessível — como um coach falando com o aluno após a sessão. "
        "Cubra obrigatoriamente estes 4 tópicos, um por parágrafo: "
        "(1) visão geral da qualidade das decisões, "
        "(2) o principal leak identificado, "
        "(3) como o jogador se comportou sob pressão de ICM, "
        "(4) um conselho concreto de foco para a próxima sessão. "
        "É obrigatório terminar o parágrafo 4 com uma frase de encerramento completa. "
        "NÃO use bullet points. Escreva em prosa fluida. "
        "Termos técnicos de poker SEMPRE em inglês: fold, call, raise, bet, check, shove, preflop, flop, turn, river, hand, spot, equity, ICM, M-ratio, stack, pot odds, range, 3-bet, c-bet, board, position. "
        "Retorne APENAS o texto do resumo, sem título ou formatação extra."
    )

    user_msg = "Jogador: " + hero + "\nMetricas:\n" + json.dumps(ctx, ensure_ascii=False, indent=2)

    payload = {
        'model':      'claude-haiku-4-5-20251001',
        'max_tokens': 900,
        'system':     system_prompt,
        'messages':   [{'role': 'user', 'content': user_msg}],
    }

    import requests as _req
    resp = _req.post(
        'https://api.anthropic.com/v1/messages',
        json=payload,
        headers={
            'Content-Type':      'application/json',
            'anthropic-version': '2023-06-01',
            'x-api-key':         _api_key(),
        },
        timeout=60,
    )
    resp.raise_for_status()
    data = resp.json()
    return ''.join(
        block['text'] for block in data.get('content', [])
        if block.get('type') == 'text'
    ).strip()


def _template_tournament_summary(ctx: dict, hero: str) -> str:
    """Fallback quando o LLM não está disponível."""
    avg   = ctx.get('avg_score', 0)
    std   = ctx.get('standard_pct', 0)
    clear = ctx.get('clear_pct', 0)
    leaks = ctx.get('top_leaks', [])
    icm   = ctx.get('icm_breakdown', {})

    quality = 'consistente' if std >= 75 else 'irregular' if std >= 60 else 'abaixo do esperado'
    top_leak = leaks[0][0] if leaks else 'não identificado'

    icm_high = icm.get('high', {})
    icm_comment = ''
    if icm_high and icm_high.get('avg', 0) > avg * 1.3:
        icm_comment = (f" Sob pressão de ICM elevado ({icm_high['count']} decisões), "
                       f"o score médio subiu para {icm_high['avg']:.3f}, "
                       f"indicando dificuldade em situações de stack curto.")

    return (
        f"O desempenho de {hero} neste torneio foi {quality}, "
        f"com {std:.1f}% das decisões dentro do esperado e score médio de {avg:.4f}. "
        f"O principal leak identificado foi {top_leak}, "
        f"que representa o spot com maior peso de erro acumulado."
        f"{icm_comment} "
        f"Para a próxima sessão, o foco deve ser revisitar os fundamentos de pot odds "
        f"e gerenciamento de stack em situações de pressão."
    )


def _tournament_cache_key(ctx: dict) -> str:
    """Chave de cache baseada nas métricas principais."""
    import hashlib, json as _json
    raw = _json.dumps({
        'avg': ctx.get('avg_score'),
        'hands': ctx.get('total_hands'),
        'leaks': ctx.get('top_leaks', [])[:2],
    }, sort_keys=True)
    return 'summary_' + hashlib.md5(raw.encode()).hexdigest()[:10]


# ── Tournament narrative (short, inline) ─────────────────────────────────────

def generate_tournament_narrative(tournament_id: int, ctx: dict) -> str:
    """
    2-3 frases descrevendo o arco de qualidade da sessão.
    Diferente do generate_tournament_summary (4 parágrafos), esta é
    uma narrativa curta para exibição inline na página do torneio.
    Cacheia por tournament_id para evitar chamadas repetidas.
    """
    cache_key = f"narr_{tournament_id}"
    if cache_key in _cache:
        return _cache[cache_key]

    try:
        text = _call_llm_narrative(ctx)
    except Exception:
        text = _template_narrative(ctx)

    _cache[cache_key] = text
    return text


def _call_llm_narrative(ctx: dict) -> str:
    system_prompt = (
        "Você é um coach de poker MTT. "
        "Com base nas métricas abaixo, escreva EXATAMENTE 2 ou 3 frases "
        "descrevendo o arco de qualidade desta sessão. "
        "Seja específico: cite o padrão dominante de erros, a fase de maior deterioração "
        "(se houver) e o impacto de ICM se relevante. "
        "Use linguagem técnica e direta, como um coach falando ao vivo após a sessão. "
        "NÃO use títulos, bullets ou formatação Markdown. Apenas as frases, ponto final."
    )
    user_msg = json.dumps(ctx, ensure_ascii=False, indent=2)
    payload = {
        'model':      'claude-haiku-4-5-20251001',
        'max_tokens': 400,
        'system':     system_prompt,
        'messages':   [{'role': 'user', 'content': user_msg}],
    }
    import requests as _req
    resp = _req.post(
        'https://api.anthropic.com/v1/messages',
        json=payload,
        headers={
            'Content-Type':      'application/json',
            'anthropic-version': '2023-06-01',
            'x-api-key':         _api_key(),
        },
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()
    return ''.join(
        block['text'] for block in data.get('content', [])
        if block.get('type') == 'text'
    ).strip()


def _template_narrative(ctx: dict) -> str:
    """Fallback determinístico quando LLM indisponível."""
    std   = ctx.get('standard_pct', 0) or 0
    avg   = ctx.get('avg_score', 0) or 0
    leaks = ctx.get('top_leaks', [])
    icm   = ctx.get('icm_breakdown', {})
    worst = ctx.get('worst_phase')

    if std >= 75:
        quality = f"Sessão sólida: {std:.0f}% das decisões dentro do padrão esperado (score médio {avg:.3f})."
    elif std >= 60:
        quality = f"Desempenho regular com {std:.0f}% de decisões padrão e score médio {avg:.3f}."
    else:
        quality = f"Sessão abaixo do esperado: apenas {std:.0f}% de decisões padrão (score médio {avg:.3f})."

    leak_str = ""
    if leaks:
        spot, score, n = leaks[0]
        street, action = (spot.split("/") + ["?"])[:2]
        leak_str = f" Leak dominante: {street}/{action} ({n}× detectado, score {score:.3f})."

    icm_high = icm.get('high', {})
    phase_str = ""
    if worst and worst.get('avg_score', 0) > avg * 1.25:
        phase_str = f" Maior deterioração na fase {worst.get('phase', '?')} (score {worst['avg_score']:.3f})."
    elif icm_high and icm_high.get('count', 0) >= 3 and icm_high.get('avg', 0) > avg * 1.2:
        phase_str = f" Deterioração detectada sob ICM elevado ({icm_high['count']} mãos, score {icm_high['avg']:.3f})."

    return f"{quality}{leak_str}{phase_str}"


def generate_comparison_narrative(items: list) -> str:
    """2 frases comparando evolução entre 2+ torneios. Cache por IDs."""
    cache_key = "cmp_" + "_".join(str(i.get("tournament_id", "")) for i in items)
    if cache_key in _cache:
        return _cache[cache_key]

    try:
        text = _call_llm_comparison(items)
    except Exception:
        text = _template_comparison(items)

    _cache[cache_key] = text
    return text


def _call_llm_comparison(items: list) -> str:
    ctx = [
        {
            "torneio": i.get("tournament_id"),
            "data": str(i.get("played_at", ""))[:10],
            "standard_pct": f"{i.get('standard_pct', 0):.1f}%",
            "score_medio": round(i.get("avg_score") or 0, 4),
            "principal_leak": i["top_leaks"][0][0] if i.get("top_leaks") else None,
        }
        for i in items
    ]
    system_prompt = (
        "Você é um coach de poker MTT. Compare os torneios abaixo e escreva "
        "EXATAMENTE 2 frases descrevendo a evolução entre eles. "
        "Use 'Standard%' para a taxa de decisões corretas e 'score médio' para o erro médio. "
        f"Cite os números concretos. Seja direto e técnico. NÃO use títulos ou bullets. {_POKER_TERMS_EN}"
    )
    payload = {
        "model": "claude-haiku-4-5-20251001",
        "max_tokens": 350,
        "system": system_prompt,
        "messages": [{"role": "user", "content": json.dumps(ctx, ensure_ascii=False)}],
    }
    import requests as _req
    resp = _req.post(
        "https://api.anthropic.com/v1/messages",
        json=payload,
        headers={
            "Content-Type": "application/json",
            "anthropic-version": "2023-06-01",
            "x-api-key": _api_key(),
        },
        timeout=20,
    )
    resp.raise_for_status()
    data = resp.json()
    return "".join(
        block["text"] for block in data.get("content", []) if block.get("type") == "text"
    ).strip()


def _template_comparison(items: list) -> str:
    if len(items) < 2:
        return ""
    first, last = items[0], items[-1]
    std_delta = (last.get("standard_pct") or 0) - (first.get("standard_pct") or 0)
    score_delta = (last.get("avg_score") or 0) - (first.get("avg_score") or 0)
    direction = "melhora" if std_delta > 0 else "queda"
    sign = "+" if std_delta >= 0 else ""
    return (
        f"Evolução de {sign}{std_delta:.1f}pp em Standard% entre o primeiro e o último torneio "
        f"({'score médio melhorou' if score_delta < 0 else 'score médio piorou'} "
        f"{abs(score_delta):.3f}). "
        f"Tendência de {direction} técnica no período analisado."
    )


def _format_hud_stats_for_prompt(stats: dict) -> str:
    """Formata HUD stats como texto interpretado para o prompt do LLM."""
    if not stats or stats.get('total_hands', 0) == 0:
        return ''

    def _line(label: str, value, lo: float, hi: float, unit: str = '%', invert: bool = False) -> str:
        if value is None:
            return f'  - {label}: sem dados'
        margin = (hi - lo) * 0.35
        if value >= lo and value <= hi:
            status = '✓'
            note = 'dentro do range ideal'
        elif (not invert and value < lo - margin) or (invert and value > hi + margin):
            status = '⚠'
            note = f'abaixo do ideal ({lo:.0f}–{hi:.0f}{unit})' if not invert else f'acima do ideal ({lo:.0f}–{hi:.0f}{unit})'
        elif (not invert and value > hi + margin) or (invert and value < lo - margin):
            status = '⚠'
            note = f'acima do ideal ({lo:.0f}–{hi:.0f}{unit})' if not invert else f'abaixo do ideal ({lo:.0f}–{hi:.0f}{unit})'
        else:
            status = '~'
            note = f'próximo do limite (ideal: {lo:.0f}–{hi:.0f}{unit})'
        fmt = f'{value:.1f}{unit}' if unit != 'x' else f'{value:.1f}x'
        return f'  - {label}: {fmt} {status} {note}'

    lines = [
        '\n**Perfil de Jogo — HUD Stats comportamentais:**',
        _line('VPIP',            stats.get('vpip'),            12,  22),
        _line('PFR',             stats.get('pfr'),              9,  18),
        _line('AF (postflop)',   stats.get('af'),             2.0, 4.0, unit='x'),
        _line('C-Bet%',          stats.get('cbet_pct'),        50,  75),
        _line('Fold to 3BET',    stats.get('fold_to_3bet'),    55,  72),
        _line('WTSD',            stats.get('wtsd'),            25,  35),
        _line('3BET%',           stats.get('three_bet'),        4,   8),
        _line('W$SD',            stats.get('w_at_sd'),         50,  60),
        _line('Fold vs Flop Bet',stats.get('fold_to_flop_bet'),40,  55),
        _line('BB Defense',      stats.get('bb_defense'),      35,  55),
        _line('Steal%',          stats.get('steal_pct'),       25,  45),
        _line('Open Limp%',      stats.get('open_limp_pct'),    0,   5),
    ]
    lines.append(
        f'  (baseado em {stats.get("total_hands", 0)} mãos — stats comportamentais, '
        'independentes da análise GTO)'
    )
    return '\n'.join(lines) + '\n'


def _recover_truncated_plan_json(raw: str) -> str | None:
    """Tenta recuperar JSON de study plan truncado por max_tokens.

    Estrategia: localizar o ultimo '}' que esteja seguido de ',' ou ']' (= cards
    completos), recortar ate ali e fechar o array + objeto root.
    Retorna None se nao conseguir recuperar.
    """
    import re as _re
    # Encontra todos os fechamentos '}' que parecem terminar um card
    # (seguidos de ',' ou ']'). Pega o ultimo.
    last_complete = -1
    depth = 0
    in_str = False
    escape = False
    for i, ch in enumerate(raw):
        if escape:
            escape = False
            continue
        if ch == '\\' and in_str:
            escape = True
            continue
        if ch == '"':
            in_str = not in_str
            continue
        if in_str:
            continue
        if ch == '{':
            depth += 1
        elif ch == '}':
            depth -= 1
            # depth 1 = dentro do array "cards", entao esse } fechou um card
            if depth == 1:
                last_complete = i
    if last_complete < 0:
        return None
    # Recorta ate o ultimo card completo e fecha estrutura
    fixed = raw[:last_complete + 1] + "\n  ]\n}"
    try:
        json.loads(fixed)
        return fixed
    except Exception:
        return None


def generate_study_plan(leaks: list, evolution: list, icm: dict,
                        hero: str = 'Jogador',
                        user_id: int | None = None,
                        force_new: bool = False,
                        player_stats: dict | None = None,
                        leak_source: str = 'gto',
                        ev_leaks: list | None = None) -> dict:
    """
    Gera plano de estudos personalizado baseado nos leaks reais do jogador.
    Retorna dict com cards[], resumo, nível identificado e `source` (gto|heuristic|empty).
    Cache persistente no banco via llm_cache com chave estável por aluno.

    leak_source: 'gto' (default) ou 'heuristic' — origem dos leaks. Afeta o prompt
    (Claude é informado da fonte) e é retornado no payload para o frontend.
    """
    import hashlib, json, os, requests

    # Chave em memória (por snapshot de dados — evita regerar na mesma sessão)
    stats_fingerprint = {
        k: v for k, v in (player_stats or {}).items()
        if k != 'total_hands' and v is not None
    } if player_stats else {}
    mem_key = 'study_plan_v6:' + hashlib.md5(
        json.dumps({'leaks': leaks, 'evo_len': len(evolution), 'stats': stats_fingerprint,
                    'source': leak_source, 'ev': ev_leaks or []}, sort_keys=True).encode()
    ).hexdigest()
    # Chave DB estável — plano canônico único por aluno
    db_key = 'study_plan_current'

    if not force_new:
        # Cache em memória
        if mem_key in _cache:
            return json.loads(_cache[mem_key])
        # Cache persistente no banco
        if user_id is not None:
            try:
                from database.repositories import get_llm_cache
                cached = get_llm_cache(user_id, db_key)
                if cached:
                    _cache[mem_key] = cached
                    return json.loads(cached)
            except Exception:
                pass

    # --- Calcular métricas gerais ---
    total_dec  = sum((e.get('decisions_count') or 0) for e in evolution) or 1
    avg_score  = sum((e.get('avg_score') or 0) * (e.get('decisions_count') or 0)
                     for e in evolution) / total_dec
    avg_std    = sum((e.get('standard_pct') or 0) * (e.get('decisions_count') or 0)
                     for e in evolution) / total_dec
    avg_clear  = sum((e.get('clear_pct') or 0) * (e.get('decisions_count') or 0)
                     for e in evolution) / total_dec
    n_torneioa = len(evolution)

    # ICM fraco = onde mais erra
    icm_weak = max(icm.items(),
                   key=lambda x: 1 - x[1].get('standard_rate', 1),
                   default=('—', {}))[0] if icm else '—'

    # --- Montar prompt ---
    leaks_txt = '\n'.join(
        f"  - {l['spot']}: {l['n']} ocorrências, score médio {l['avg_score']:.3f} "
        f"({'crítico' if l['avg_score'] >= .36 else 'moderado' if l['avg_score'] >= .20 else 'leve'})"
        for l in leaks[:8]
    )

    # Vazamentos por EV PERDIDO (#24/#25) — quantos bb cada spot custa. PRIORIDADE
    # do plano: o leak que mais sangra EV vale mais que vários pequenos.
    ev_txt = ''
    if ev_leaks:
        ev_txt = '\n'.join(
            f"  - {l.get('position', '?')} {l.get('street', '')} (ideal: {l.get('ideal_action', '')}): "
            f"−{l.get('total_ev_loss_bb', 0)} bb em {l.get('n', 0)} decisões "
            f"(−{l.get('avg_ev_loss_bb', 0)} bb/decisão)"
            for l in ev_leaks[:6]
        )

    # --- HUD stats section (se disponível) ---
    hud_txt = _format_hud_stats_for_prompt(player_stats) if player_stats else ''

    # Indicar fonte dos leaks ao Claude para contextualizar o nível de confiança
    source_note = {
        'gto': '\n(Leaks identificados via análise GTO — comparação direta com solver. Alta confiança.)',
        'heuristic': '\n(Leaks identificados via análise heurística do engine — fallback usado quando cobertura GTO é insuficiente. Confiança moderada.)',
        'empty': '',
    }.get(leak_source, '')

    prompt = f"""Você é um coach profissional de poker MTT com mais de 15 anos de experiência, especialista em identificar e corrigir leaks em torneios.
Analise os dados de performance abaixo e gere um plano de estudos DETALHADO e PERSONALIZADO.

## Dados do Jogador ({hero})

**Métricas gerais ({n_torneioa} torneios analisados):**
- Score médio de erro: {avg_score:.4f} (meta: abaixo de 0.08)
- Standard% (decisões corretas): {avg_std:.1f}% (meta: acima de 80%)
- Erros claros: {avg_clear:.1f}% (meta: abaixo de 5%)
- Pior fase ICM: pressão {icm_weak}
{hud_txt}
**Leaks identificados (por frequência de erro):**{source_note}
{leaks_txt}
{('''
**Vazamentos por EV PERDIDO (bb deixados na mesa — PRIORIZE A ORDEM DO PLANO POR AQUI):**
Cada spot abaixo mostra quantos big blinds o jogador deixou na mesa vs a melhor jogada GTO. Um leak que custa muito EV (bb) vale mais que um leak frequente porém barato. Ordene o plano do que mais sangra EV pro que menos.
''' + ev_txt) if ev_txt else ''}

## Instrução de Coach

Use os HUD Stats comportamentais para enriquecer o diagnóstico: se VPIP alto + PFR baixo, o jogador é loose-passive; se AF abaixo de 2x, o postflop é passivo demais; se Open Limp% acima de 5%, há problema de fold equity pré-flop; se BB Defense baixa, o jogador está sendo exploitado no big blind. Cruze os HUD Stats com os Leaks identificados para gerar módulos muito mais específicos e personalizados.

Gere um plano de estudos com exatamente 6 itens, ordenados pela PRIORIDADE DE EV — comece pelos vazamentos que mais custam bb (lista "Vazamentos por EV PERDIDO" acima, quando disponível); na ausência dela, use a frequência de erro. Quando souber o custo em bb de um leak, cite-o no diagnóstico ("este leak custa ~X bb/decisão").
Cada item deve ser um módulo de estudo completo com:

1. Título direto e específico ao leak (máx 6 palavras)
2. Diagnóstico: 2-3 frases explicando a RAIZ do problema e seu impacto real em EV/fichas
3. Conceitos-chave: lista de 2-4 conceitos teóricos que o jogador PRECISA dominar para corrigir este leak
4. Recursos de estudo:
   - 1-2 livros ou capítulos específicos (ex: "The Mental Game of Poker cap. 3", "Applications of No-Limit Hold'em cap. 7")
   - 1-2 tipos de vídeos/canais (ex: "solver study sessions focados em spots-chave", "hand history reviews de spots de 3bet")
   - 1 curso ou treinamento específico se relevante
5. Exercício prático: uma rotina CONCRETA e mensurável que o jogador pode fazer HOJE (ex: "Revisar 20 mãos de fold no BB contra 3bet, marcar as que tinham +EV call e calcular os pot odds")
6. Métrica de progresso: como saber que melhorou (ex: "Taxa de erro neste spot abaixo de 15% em 50 mãos")

Responda APENAS com JSON válido, sem texto adicional, no formato:
{{
  "nivel": "iniciante|intermediario|avancado",
  "resumo": "2-3 frases descrevendo o perfil de erros, os padrões principais e o caminho de evolução deste jogador",
  "cards": [
    {{
      "prioridade": "p1",
      "icone": "♠|♥|♦|♣",
      "titulo": "título do tópico",
      "diagnostico": "explicação da raiz do problema e impacto em EV",
      "conceitos": ["conceito 1", "conceito 2", "conceito 3"],
      "recursos": {{
        "livros": ["livro/capítulo específico 1", "livro/capítulo específico 2"],
        "videos": ["tipo de vídeo/canal 1", "tipo de vídeo/canal 2"],
        "curso": "nome do curso ou treinamento (null se não aplicável)"
      }},
      "exercicio": "rotina prática concreta e mensurável",
      "metrica": "como medir o progresso neste leak",
      "spot": "street/action do leak principal"
    }}
  ]
}}"""

    try:
        resp = requests.post(
            'https://api.anthropic.com/v1/messages',
            headers={
                'x-api-key':         _api_key(),
                'anthropic-version': '2023-06-01',
                'content-type':      'application/json',
            },
            json={
                'model':      'claude-haiku-4-5-20251001',
                'max_tokens': 6000,
                'messages':   [{'role': 'user', 'content': prompt}],
            },
            timeout=90,
        )
        resp.raise_for_status()
        raw = resp.json()['content'][0]['text'].strip()

        # Limpar possível markdown
        if raw.startswith('```'):
            raw = raw.split('```')[1]
            if raw.startswith('json'):
                raw = raw[4:]
        raw = raw.strip()

        # Truncamento por max_tokens: tenta recuperar tentando fechar o JSON
        # até o último card completo (último '}' seguido de virgula ou fechamento).
        try:
            result = json.loads(raw)
        except json.JSONDecodeError:
            recovered = _recover_truncated_plan_json(raw)
            if recovered:
                result = json.loads(recovered)
            else:
                raise
        result['source'] = leak_source
        result_str = json.dumps(result, ensure_ascii=False)
        _cache[mem_key] = result_str
        # Persistir no banco com chave estável (sobrescreve plano anterior)
        if user_id is not None:
            try:
                from database.repositories import set_llm_cache
                set_llm_cache(user_id, db_key, result_str)
            except Exception:
                pass
        return result

    except Exception as e:
        # Fallback: NUNCA vazar o erro cru da API (ex.: "400 ... anthropic ...") pro
        # cliente — loga internamente e devolve um código estável. O front mostra
        # uma mensagem amigável ("IA temporariamente indisponível").
        try:
            import logging as _lg
            _lg.getLogger('leaklab.llm_explainer').warning(
                "generate_study_plan falhou (IA indisponível?): %s", str(e)[:200])
        except Exception:
            pass
        return {
            'nivel': 'intermediario',
            'resumo': 'Plano com IA temporariamente indisponível.',
            'cards': [],
            'source': leak_source,
            'error': 'ai_unavailable',
        }


def coach_replay_decision(street, action_taken, best_action,
                           hero_cards=None, board=None,
                           hand_equity=None, pot_odds=None,
                           m_ratio=None, icm_pressure='low',
                           error_score=None, error_label='',
                           math_penalty=0, range_penalty=0) -> str:
    """
    Gera explicação do Coach IA para um erro específico identificado no replayer.
    Retorna texto em português, direto, sem markdown excessivo.
    """
    import hashlib, json, os, requests

    # Cache em memória
    cache_input = json.dumps({
        'street': street, 'action': action_taken, 'best': best_action,
        'eq': round(hand_equity or 0, 2), 'po': round(pot_odds or 0, 2),
        'mr': round(m_ratio or 0, 1)
    }, sort_keys=True)
    ckey = 'rc:' + hashlib.md5(cache_input.encode()).hexdigest()
    if ckey in _cache:
        return _cache[ckey]

    # Formatar cartas
    def fmt_cards(cards):
        if not cards: return '?? ??'
        if isinstance(cards, list) and len(cards) == 2:
            suits = {'s':'♠','h':'♥','d':'♦','c':'♣'}
            result = []
            for c in cards:
                if c and len(c) >= 2:
                    rank = c[:-1].upper()
                    suit = suits.get(c[-1].lower(), c[-1])
                    result.append(rank+suit)
                else:
                    result.append(str(c))
            return ' '.join(result)
        return str(cards)

    hero_str  = fmt_cards(hero_cards)
    board_str = ' '.join([fmt_cards([c]) for c in (board or [])]) or '(sem board)'

    # Mapear label para texto
    label_map = {
        'clear_mistake': 'erro grave',
        'small_mistake': 'erro',
        'marginal':      'decisão marginal',
    }
    label_str = label_map.get(error_label, 'erro')

    # Contexto matemático
    eq_str  = f'{hand_equity*100:.0f}%' if hand_equity is not None else None
    po_str  = f'{pot_odds*100:.0f}%'    if pot_odds   is not None else None
    mr_str  = f'{m_ratio:.1f}BB'        if m_ratio    is not None else None
    icm_map = {'low':'baixa','medium':'média','high':'alta'}
    icm_str = icm_map.get(icm_pressure, icm_pressure)

    # Contexto de situação
    math_ctx = ''
    if eq_str and po_str:
        math_ctx = f'Equity estimada: {eq_str}. Pot odds necessários: {po_str}. '
    elif eq_str:
        math_ctx = f'Equity estimada: {eq_str}. '
    if mr_str:
        math_ctx += f'Stack: {mr_str}. '
    math_ctx += f'Pressão ICM: {icm_str}.'

    prompt = f"""Você é um coach profissional de poker MTT. Analise este {label_str} e explique de forma clara e direta.

Situação:
- Street: {street.upper()}
- Cartas do herói: {hero_str}
- Board: {board_str}
- Ação tomada: {action_taken.upper()}
- Ação correta: {best_action.upper()}
- {math_ctx}

Escreva uma explicação em 3-5 linhas em português brasileiro:
1. Por que {action_taken.upper()} foi o erro nesta situação específica
2. Por que {best_action.upper()} seria melhor (seja concreto com os números disponíveis)
3. O que observar em situações similares no futuro

Seja direto, use linguagem de coach (não acadêmica). Não use markdown, apenas texto corrido."""

    try:
        resp = requests.post(
            'https://api.anthropic.com/v1/messages',
            headers={
                'x-api-key':         _api_key(),
                'anthropic-version': '2023-06-01',
                'content-type':      'application/json',
            },
            json={
                'model':      'claude-haiku-4-5-20251001',
                'max_tokens': 400,
                'messages':   [{'role': 'user', 'content': prompt}],
            },
            timeout=25,
        )
        resp.raise_for_status()
        result = resp.json()['content'][0]['text'].strip()
        _cache[ckey] = result
        return result
    except Exception as e:
        return f'Erro ao conectar ao Coach IA: {str(e)}'


# ── Leak Causal Map (FEAT-06) ────────────────────────────────────────────────

def explain_leak_causality(edges: list, hero: str = 'você', lang: str = 'pt-BR') -> str:
    """1 parágrafo curto (2-3 frases) explicando a causa raiz dos pares mais correlacionados."""
    if not edges:
        return ""
    cache_key = "causal_v3_" + lang + "_" + "_".join(
        f"{e['source']}:{e['target']}" for e in edges[:3]
    )
    if cache_key in _cache:
        return _cache[cache_key]
    try:
        text = _call_llm_causality(edges[:3], hero, lang)
    except Exception:
        text = _template_causality(edges[:3])
    _cache[cache_key] = text
    return text


_POKER_TERMS_EN = (
    "Termos técnicos de poker SEMPRE em inglês: "
    "fold, call, raise, bet, check, shove, preflop, flop, turn, river, "
    "hand, spot, equity, ICM, M-ratio, stack, pot odds, range, 3-bet, c-bet, "
    "board, position, IP, OOP, shove, reshove, open, limp, squeeze. "
    "NUNCA use 'rua' ou 'ruas' — sempre 'street' ou 'streets'. "
    "Para conjugar ações em português, use a forma 'dando raise', 'dando bet', 'dando fold' — "
    "NUNCA 'raisando', 'bettando', 'foldando' ou qualquer aportuguesamento de termos ingleses."
)

_LANG_INSTRUCTIONS = {
    'pt-BR': (
        f"Responda APENAS em português do Brasil formal. {_POKER_TERMS_EN} "
        "Use 'você está', 'você precisa' — NUNCA contrações informais como 'tá', 'tô', 'pra'."
    ),
    'en':    "Respond ONLY in English. Keep poker technical terms in English.",
    'es':    f"Responde ÚNICAMENTE en español. {_POKER_TERMS_EN}",
}


def _call_llm_causality(edges: list, hero: str, lang: str = 'pt-BR') -> str:
    import requests as _req
    lang_instr = _LANG_INSTRUCTIONS.get(lang, _LANG_INSTRUCTIONS['pt-BR'])
    pairs = "\n".join(
        f"- {e['source']} ↔ {e['target']}: {e['correlation']:.0%} correlation "
        f"({e['co_occurrences']} tournaments together)"
        for e in edges
    )
    system_prompt = (
        f"You are a friendly MTT poker coach talking directly to a student who is still learning. {lang_instr} "
        "Analyze the leak correlations and write EXACTLY 3 SHORT sentences: "
        "(1) Describe what both mistakes look like in practice at the table — use plain language about the BEHAVIOR (what the player does), not abstract concepts. "
        "(2) Name the single habit or misunderstanding causing both errors — if you use a technical term, immediately explain it in simple words in parentheses. "
        "(3) Give one concrete, actionable change the player can make starting in their next session. "
        "Write as if talking face to face, not writing a report. "
        "Avoid dense jargon clusters. Keep each sentence under 40 words. "
        "Do NOT use titles, bullets, labels like '1)' or introductions."
    )
    payload = {
        "model": "claude-haiku-4-5-20251001",
        "max_tokens": 340,
        "system": system_prompt,
        "messages": [{"role": "user", "content": f"Player leaks ({hero}):\n{pairs}"}],
    }
    resp = _req.post(
        "https://api.anthropic.com/v1/messages",
        json=payload,
        headers={
            "Content-Type": "application/json",
            "anthropic-version": "2023-06-01",
            "x-api-key": _api_key(),
        },
        timeout=20,
    )
    resp.raise_for_status()
    data = resp.json()
    return "".join(
        block["text"] for block in data.get("content", []) if block.get("type") == "text"
    ).strip()


def _template_causality(edges: list) -> str:
    if not edges:
        return ""
    top = edges[0]
    a = top['source'].replace('/', ' ').replace('_', ' ')
    b = top['target'].replace('/', ' ').replace('_', ' ')
    corr = int(top['correlation'] * 100)
    return (
        f"Os leaks de {a} e {b} co-ocorrem em {corr}% dos torneios analisados, "
        f"sugerindo uma causa raiz comum — provavelmente relacionada a leitura de range ou "
        f"gestão de stack. Corrija o spot com maior frequência primeiro para reduzir "
        f"automaticamente os demais."
    )


# ── Career Projection Narrative (Sprint AP) ─────────────────────────────────

_LANG_CAREER = {
    'pt-BR': "Responda APENAS em português do Brasil.",
    'en':    "Respond ONLY in English.",
    'es':    "Responde ÚNICAMENTE en español.",
}


def generate_career_narrative(projection: dict, lang: str = 'pt-BR') -> str:
    """2-3 sentences: current trajectory, next milestone, key blocker."""
    cache_key = (
        f"career2_{lang}_{projection.get('current_level_slug','?')}_"
        f"{projection.get('current_avg', 0):.1f}_"
        + "_".join(lk['spot'] for lk in projection.get('blocking_leaks', [])[:2])
    )
    if cache_key in _cache:
        return _cache[cache_key]
    try:
        text = _call_career_narrative(projection, lang)
    except Exception:
        text = _template_career(projection)
    _cache[cache_key] = text
    return text


def _call_career_narrative(projection: dict, lang: str) -> str:
    import requests as _req
    lang_instr = _LANG_CAREER.get(lang, _LANG_CAREER['pt-BR'])
    nm = projection.get("next_milestone") or {}
    leaks = projection.get("blocking_leaks", [])
    leak_str = ", ".join(lk['spot'].replace('/', ' → ') for lk in leaks[:2]) or "—"
    if nm.get("reachable") and nm.get("months_needed", 0) > 0:
        timeline = (f"At the current rate, the next level ({nm['level_name']} / "
                    f"{nm['threshold']} ELO) is ~{nm['months_needed']} months away "
                    f"({nm['tournaments_needed']} tournaments).")
    elif projection.get("slope_per_tournament", 0) <= 0:
        timeline = "The current trajectory is flat or declining."
    else:
        timeline = f"The player is close to the next threshold already."

    system = (
        f"You are a concise MTT poker coach. {lang_instr} "
        "Write EXACTLY 2-3 sentences summarizing: (1) the player's current trajectory "
        "(improving/flat/declining), (2) when they'll reach the next level if on track, "
        "(3) the single most important leak to fix to accelerate that. "
        "CRITICAL: Use ONLY the exact level names provided in the context (e.g. Grinder, Regular, Sólido, Expert, Elite). "
        "Never invent or substitute different level names. Be direct and specific. No headers or bullets."
    )
    user_content = (
        f"Current level: {projection['current_level']} ({projection['current_avg']:.0f} ELO rating, "
        f"GTO-adherence based). "
        f"Trend: {projection['slope_per_tournament']:+.1f} ELO per tournament over "
        f"{projection['tournament_count']} tournaments. "
        f"{timeline} "
        f"Top blocking leaks: {leak_str}."
    )
    payload = {
        "model": "claude-haiku-4-5-20251001",
        "max_tokens": 220,
        "system": system,
        "messages": [{"role": "user", "content": user_content}],
    }
    resp = _req.post(
        "https://api.anthropic.com/v1/messages",
        json=payload,
        headers={
            "Content-Type": "application/json",
            "anthropic-version": "2023-06-01",
            "x-api-key": _api_key(),
        },
        timeout=20,
    )
    resp.raise_for_status()
    data = resp.json()
    return "".join(
        block["text"] for block in data.get("content", []) if block.get("type") == "text"
    ).strip()


def _template_career(projection: dict) -> str:
    slope = projection.get("slope_per_tournament", 0)
    nm    = projection.get("next_milestone") or {}
    leaks = projection.get("blocking_leaks", [])
    top   = leaks[0]["spot"].replace("/", " → ") if leaks else "leaks recorrentes"
    if slope > 0.05 and nm.get("reachable"):
        return (
            f"Sua trajetória atual mostra melhora consistente de {slope:+.1f} ELO por torneio. "
            f"Mantendo esse ritmo, você alcançará o nível {nm['level_name']} "
            f"({nm['threshold']} ELO) em aproximadamente {nm['months_needed']} meses. "
            f"O principal obstáculo é o leak em {top} — corrigi-lo acelera diretamente essa projeção."
        )
    elif slope <= 0:
        return (
            f"Seu ELO está estagnado ou em queda nos últimos torneios. "
            f"O foco imediato deve ser consistência, não volume. "
            f"O leak de {top} é o ponto de maior impacto para retomar a curva positiva."
        )
    else:
        return (
            f"Você está progredindo, mas o ritmo está abaixo do potencial. "
            f"O leak de {top} aparece com alta frequência e é o principal freio de crescimento. "
            f"Corrigi-lo pode acelerar sua chegada ao próximo nível."
        )


# ── Cognitive Failure Narrative (Sprint AQ) ──────────────────────────────────

_LANG_COGNITIVE = {
    'pt-BR': (
        "Responda APENAS em português do Brasil formal. "
        "Use 'você está', 'você precisa', 'você tende' — NUNCA use contrações informais como 'tá', 'tô', 'pra'. "
        "NUNCA use 'rua' ou 'ruas' — sempre 'street' ou 'streets'."
    ),
    'en':    "Respond ONLY in English.",
    'es':    "Responde ÚNICAMENTE en español.",
}

_PATTERN_NAMES_EN = {
    "revenge_aggression": "Revenge Aggression",
    "fear_folding":       "Fear Folding",
    "sunk_cost":          "Sunk Cost Continuation",
    "entitlement_tilt":   "Entitlement Tilt",
    "compensation_call":  "Compensation Call",
    "icm_blindness":      "ICM Blindness",
}

# Plain-language behavior descriptions used in the LLM prompt so the model
# produces concrete, accessible language instead of clinical labels.
_PATTERN_BEHAVIORS = {
    "revenge_aggression": (
        "bets and raises too much in the hands right after a bad beat or a big loss, "
        "as if trying to quickly win back what was lost"
    ),
    "fear_folding": (
        "folds too often when facing any pressure, especially after losing chips, "
        "even when the hand and odds justify continuing"
    ),
    "sunk_cost": (
        "keeps calling bets on later streets even when the hand is unlikely to win, "
        "because they already put chips in the pot and feel they can't walk away"
    ),
    "entitlement_tilt": (
        "starts playing looser and less carefully after a streak of good hands, "
        "as if convinced that winning momentum will continue regardless of hand quality"
    ),
    "compensation_call": (
        "calls bets they would normally fold immediately after correctly folding a strong hand, "
        "as if needing to 'make up' for the fold they just made"
    ),
    "icm_blindness": (
        "gambles their whole stack on thin spots at the final table, where survival and pay "
        "jumps make chips worth less than their face value, instead of tightening up under ICM pressure"
    ),
}


def generate_cognitive_narrative(patterns: list, lang: str = 'pt-BR') -> str:
    """2-3 sentences on the dominant cognitive pattern, its EV cost, and one corrective habit."""
    if not patterns:
        return ""
    cache_key = (
        f"cog_v3_{lang}_"
        + "_".join(f"{p['type']}:{p['severity']}" for p in patterns[:3])
    )
    if cache_key in _cache:
        return _cache[cache_key]
    try:
        text = _call_cognitive_narrative(patterns, lang)
    except Exception:
        text = _template_cognitive(patterns, lang)
    _cache[cache_key] = text
    return text


def _call_cognitive_narrative(patterns: list, lang: str) -> str:
    import requests as _req
    lang_instr = _LANG_COGNITIVE.get(lang, _LANG_COGNITIVE['pt-BR'])
    top = patterns[0]
    top_behavior = _PATTERN_BEHAVIORS.get(top['type'],
        f"makes suboptimal decisions under pressure ({top['type']})")
    severity_label = {"high": "strongly", "medium": "moderately", "low": "occasionally"}.get(
        top['severity'], "notably")
    pattern_str = "; ".join(
        f"{_PATTERN_BEHAVIORS.get(p['type'], p['type'])} "
        f"(seen in {p['frequency']*100:.0f}% of sessions, {p['severity']} severity)"
        for p in patterns[:2]
    )
    system = (
        f"You are a friendly poker mental-game coach talking directly to a student. {lang_instr} "
        "Write EXACTLY 3 SHORT sentences: "
        "(1) Describe what the player FEELS at the table right before this pattern activates — "
        "use simple, relatable language about the emotion or situation, not clinical labels. "
        "(2) Describe the mistake this feeling causes at the table, in concrete terms "
        "(what they do with their chips or their decisions). "
        "(3) Give one simple, physical or mental reset trick they can use in the next session "
        "to interrupt the pattern — make it specific and immediately actionable. "
        "Tone: warm and direct, like a good coach, but ALWAYS use formal language — "
        "in Portuguese use 'você está' never 'você tá', avoid slang or contractions. "
        "Keep each sentence under 40 words. "
        "Do NOT use titles, bullets, or academic labels like 'cognitive bias'."
    )
    user_content = (
        f"The player {severity_label} shows this pattern: {top_behavior}. "
        f"Additional context: {pattern_str}."
    )
    payload = {
        "model": "claude-haiku-4-5-20251001",
        "max_tokens": 320,
        "system": system,
        "messages": [{"role": "user", "content": user_content}],
    }
    resp = _req.post(
        "https://api.anthropic.com/v1/messages",
        json=payload,
        headers={
            "Content-Type": "application/json",
            "anthropic-version": "2023-06-01",
            "x-api-key": _api_key(),
        },
        timeout=20,
    )
    resp.raise_for_status()
    data = resp.json()
    return "".join(
        block["text"] for block in data.get("content", []) if block.get("type") == "text"
    ).strip()


def _template_cognitive(patterns: list, lang: str = 'pt-BR') -> str:
    top  = patterns[0]
    freq = int(top['frequency'] * 100)
    # Plain-language descriptions per pattern type and language
    _PLAIN_PT = {
        "revenge_aggression": (
            f"Em {freq}% das sessões analisadas, você tende a apostar e relançar demais logo após perder uma mão — como se quisesse recuperar rápido o que perdeu. "
            "Isso te leva a colocar fichas no pot com mãos fracas, em momentos em que o correto seria esperar. "
            "Quando sentir esse impulso, espere 30 segundos e pergunte: 'eu apostaria assim se a mão anterior tivesse sido boa?'"
        ),
        "fear_folding": (
            f"Em {freq}% das sessões, você tende a desistir de mãos com muita facilidade quando o oponente aposta, especialmente após perder fichas. "
            "Esse medo de perder mais faz você sair de pots em que as probabilidades justificariam continuar. "
            "Antes de foldar sob pressão, calcule rapidamente o que você precisa de equity (pot odds) — só então decida."
        ),
        "sunk_cost": (
            f"Em {freq}% das sessões, você tende a continuar pagando bets no turn e no river mesmo quando a mão provavelmente perdeu, "
            "porque já investiu fichas antes e sente que não pode sair. "
            "Ignore o que já está no pot — a única pergunta que importa é: 'minha mão vale esse call agora?'"
        ),
        "entitlement_tilt": (
            f"Em {freq}% das sessões, você começa a jogar de forma mais descuidada após uma sequência de boas mãos, como se a sorte fosse continuar independente do que você fizer. "
            "Isso te leva a entrar em pots fracos e a apostar sem razão clara. "
            "Após ganhar três mãos seguidas, faça uma pausa curta e redefina seu foco como se fosse a primeira mão do dia."
        ),
        "compensation_call": (
            f"Em {freq}% das sessões, você tende a pagar bets que normalmente foldaria logo após ter foldado uma mão forte corretamente — como se precisasse 'compensar' o fold anterior. "
            "Cada mão é independente: foldar bem não cria nenhuma dívida para a próxima. "
            "Quando sentir vontade de pagar 'só para fazer alguma coisa', é sinal para foldar."
        ),
        "icm_blindness": (
            f"Em {freq}% dos spots de alto ICM na mesa final, você arrisca a pilha em situações finas em vez de apertar — ignorando que, perto dos pay jumps, suas fichas valem menos do que parecem. "
            "Sobreviver tem valor real ali: um call ou shove marginal que seria certo em cash vira um erro caro sob ICM. "
            "Na mesa final, antes de arriscar a stack, pergunte: 'esse all-in ainda é +EV depois de descontar o prêmio de sobrevivência?'"
        ),
    }
    _PLAIN_EN = {
        "revenge_aggression": (
            f"In {freq}% of sessions, you tend to bet and raise too much right after losing a hand — as if trying to quickly win back what you lost. "
            "This leads you to put chips in the pot with weak hands, when the right play is to wait. "
            "When you feel that urge, pause 30 seconds and ask: 'would I play this way if my last hand had been good?'"
        ),
        "fear_folding": (
            f"In {freq}% of sessions, you tend to give up hands too easily when facing a bet, especially after losing chips. "
            "That fear of losing more makes you exit pots where the odds actually justify continuing. "
            "Before folding under pressure, quickly check if your equity beats the pot odds — then decide."
        ),
        "sunk_cost": (
            f"In {freq}% of sessions, you keep calling bets on the turn and river even when your hand has likely lost, "
            "because you already put chips in and feel you can't walk away. "
            "Ignore what's already in the pot — the only question is: 'is my hand worth this call right now?'"
        ),
        "entitlement_tilt": (
            f"In {freq}% of sessions, you start playing more carelessly after a run of good hands, as if the winning streak will continue regardless of hand quality. "
            "This leads you to enter weak pots and bet without a clear reason. "
            "After winning three hands in a row, take a short break and reset your focus as if it's the first hand of the day."
        ),
        "compensation_call": (
            f"In {freq}% of sessions, you tend to call bets you would normally fold right after correctly folding a strong hand — as if you need to 'make up' for the fold. "
            "Each hand is independent: folding well creates no debt for the next hand. "
            "When you feel like calling 'just to do something', that's your cue to fold."
        ),
        "icm_blindness": (
            f"In {freq}% of high-ICM final-table spots, you risk your stack on thin situations instead of tightening up — ignoring that near the pay jumps your chips are worth less than they look. "
            "Survival has real value there: a marginal call or shove that would be correct in a cash game becomes a costly mistake under ICM. "
            "At the final table, before risking your stack ask: 'is this all-in still +EV after subtracting the survival premium?'"
        ),
    }
    _PLAIN_ES = {
        "revenge_aggression": (
            f"En el {freq}% de las sesiones, tiendes a apostar y reraisear demasiado justo después de perder una mano — como si quisieras recuperar rápido lo perdido. "
            "Esto te lleva a meter fichas al pot con manos débiles, cuando lo correcto sería esperar. "
            "Cuando sientas ese impulso, espera 30 segundos y pregúntate: '¿jugaría así si mi última mano hubiera sido buena?'"
        ),
        "fear_folding": (
            f"En el {freq}% de las sesiones, tiendes a rendirte demasiado fácil cuando el oponente apuesta, especialmente tras perder fichas. "
            "Ese miedo a perder más te hace salir de pots donde las pot odds justificarían continuar. "
            "Antes de foldear bajo presión, calcula rápidamente si tu equity supera las pot odds — luego decide."
        ),
        "sunk_cost": (
            f"En el {freq}% de las sesiones, sigues pagando bets en el turn y river aunque tu mano probablemente perdió, "
            "porque ya pusiste fichas antes y sientes que no puedes retirarte. "
            "Ignora lo que ya está en el pot — la única pregunta es: '¿vale mi mano este call ahora?'"
        ),
        "entitlement_tilt": (
            f"En el {freq}% de las sesiones, empiezas a jugar de forma más descuidada tras una racha de buenas manos, como si la suerte fuera a continuar sin importar lo que hagas. "
            "Esto te lleva a entrar en pots débiles y apostar sin razón clara. "
            "Tras ganar tres manos seguidas, tómate una pausa corta y resetea tu enfoque como si fuera la primera mano del día."
        ),
        "compensation_call": (
            f"En el {freq}% de las sesiones, tiendes a pagar bets que normalmente foldearías justo después de haber foldeado bien una mano fuerte — como si necesitaras 'compensar' ese fold. "
            "Cada mano es independiente: foldear bien no crea ninguna deuda para la siguiente. "
            "Cuando sientas ganas de pagar 'solo para hacer algo', esa es tu señal de fold."
        ),
        "icm_blindness": (
            f"En el {freq}% de los spots de alto ICM en la mesa final, arriesgas tu pila en situaciones finas en vez de apretar — ignorando que, cerca de los pay jumps, tus fichas valen menos de lo que parecen. "
            "Sobrevivir tiene valor real allí: un call o shove marginal que sería correcto en cash se vuelve un error caro bajo ICM. "
            "En la mesa final, antes de arriesgar tu stack pregúntate: '¿este all-in sigue siendo +EV tras descontar el premio de supervivencia?'"
        ),
    }
    if lang == 'en':
        return _PLAIN_EN.get(top['type'],
            f"In {freq}% of sessions you show emotional decision-making under pressure. "
            f"This leads to mistakes at the most costly moments. "
            f"Pause 30 seconds after any triggering event before playing your next hand.")
    if lang == 'es':
        return _PLAIN_ES.get(top['type'],
            f"En el {freq}% de las sesiones muestras decisiones emocionales bajo presión. "
            f"Esto genera errores en los momentos de mayor coste. "
            f"Pausa 30 segundos tras cualquier evento desencadenante antes de jugar la siguiente mano.")
    return _PLAIN_PT.get(top['type'],
        f"Em {freq}% das sessões você toma decisões emocionais sob pressão. "
        f"Isso gera erros nos momentos de maior custo. "
        f"Faça uma pausa de 30 segundos após qualquer evento gatilho antes de jogar a próxima mão.")


# ── Strategic Twin Narrative (Sprint AR) ─────────────────────────────────────

_LANG_TWIN = {
    'pt-BR': "CRITICAL: Write the entire response in Brazilian Portuguese (pt-BR). Use 'eu', 'minha', 'meu' (first person). Do NOT use English words except for established poker terms (shove, jam, fold, call, raise, check, bet, equity, ICM, EV, range, etc.).",
    'en':    "Write the entire response in English.",
    'es':    "CRITICAL: Write the entire response in Spanish (español). Use 'yo', 'mi' (first person). Do NOT use English words except for established poker terms (shove, jam, fold, call, raise, check, bet, equity, ICM, EV, range, etc.).",
}

_ACTION_LABEL_EN = {
    "jam":   "shove",
    "fold":  "fold",
    "call":  "call",
    "raise": "raise",
    "bet":   "bet",
    "check": "check",
}

_ICM_LABEL_EN = {
    "low":      "low ICM pressure",
    "medium":   "medium ICM pressure",
    "high":     "high ICM pressure",
    "critical": "critical ICM pressure",
}


def generate_twin_narrative(profile: dict, lang: str = 'pt-BR') -> str:
    """2-3 sentences describing the player's dominant strategic tendencies and their cost."""
    costly = profile.get("costly_spots", [])
    if not costly:
        return ""
    cache_key = (
        f"twin_{lang}_"
        + "_".join(f"{s['street']}:{s['best_action']}:{s['icm_pressure']}" for s in costly[:3])
    )
    if cache_key in _cache:
        return _cache[cache_key]
    try:
        text = _call_twin_narrative(profile, lang)
    except Exception:
        text = _template_twin(profile, lang)
    _cache[cache_key] = text
    return text


def _call_twin_narrative(profile: dict, lang: str) -> str:
    import requests as _req
    lang_instr = _LANG_TWIN.get(lang, _LANG_TWIN['pt-BR'])
    avg_pct = int(profile["player_avg_error_rate"] * 100)
    costly  = profile.get("costly_spots", [])[:3]
    spot_str = "; ".join(
        f"{_ACTION_LABEL_EN.get(s['best_action'], s['best_action'])} on {s['street']} "
        f"under {_ICM_LABEL_EN.get(s['icm_pressure'], s['icm_pressure'])} "
        f"({int(s['error_rate'] * 100)}% error rate, {int(s['delta_from_avg'] * 100)}% above your avg)"
        for s in costly
    )
    system = (
        f"{lang_instr}\n\n"
        "You are a concise MTT poker coach writing a personal strategic profile. "
        "Write EXACTLY 2-3 sentences in the FIRST PERSON (e.g. 'Em situações em que...', "
        "'Meu spot mais custoso...' for pt-BR; 'In situations where...' for English): "
        "(1) name the most costly spot and the error rate, "
        "(2) explain what this tendency reveals about the player's strategy, "
        "(3) state one concrete adjustment. "
        "No headers, no bullets. Be specific and predictive in tone."
    )
    user_content = (
        f"Player average error rate: {avg_pct}%. "
        f"Costliest spots (above average): {spot_str}. "
        f"Total decisions analysed: {profile.get('total_decisions', 0)}."
    )
    payload = {
        "model": "claude-haiku-4-5-20251001",
        "max_tokens": 250,
        "system": system,
        "messages": [{"role": "user", "content": user_content}],
    }
    resp = _req.post(
        "https://api.anthropic.com/v1/messages",
        json=payload,
        headers={
            "Content-Type": "application/json",
            "anthropic-version": "2023-06-01",
            "x-api-key": _api_key(),
        },
        timeout=20,
    )
    resp.raise_for_status()
    data = resp.json()
    return "".join(
        block["text"] for block in data.get("content", []) if block.get("type") == "text"
    ).strip()


def _template_twin(profile: dict, lang: str = 'pt-BR') -> str:
    costly  = profile.get("costly_spots", [])
    if not costly:
        return ""
    top     = costly[0]
    avg_pct = int(profile["player_avg_error_rate"] * 100)
    err_pct = int(top["error_rate"] * 100)
    delta   = int(top["delta_from_avg"] * 100)
    action_pt = {"jam": "shove", "fold": "fold", "call": "call", "raise": "raise", "bet": "bet", "check": "check"}
    action_es = {"jam": "shove", "fold": "fold", "call": "call", "raise": "raise", "bet": "bet", "check": "check"}
    icm_pt    = {"low": "ICM baixo", "medium": "ICM moderado", "high": "ICM alto", "critical": "ICM crítico"}
    icm_es    = {"low": "ICM bajo", "medium": "ICM moderado", "high": "ICM alto", "critical": "ICM crítico"}
    street_pt = {"preflop": "preflop", "flop": "no flop", "turn": "no turn", "river": "no river"}
    street_es = {"preflop": "preflop", "flop": "en el flop", "turn": "en el turn", "river": "en el river"}
    if lang == 'en':
        act = _ACTION_LABEL_EN.get(top["best_action"], top["best_action"])
        icm = _ICM_LABEL_EN.get(top["icm_pressure"], top["icm_pressure"])
        return (
            f"In {top['street']} spots requiring a {act} under {icm}, I make errors {err_pct}% of the time — "
            f"{delta}% above my personal average of {avg_pct}%. "
            f"This reveals a tendency to deviate from the correct line under pressure. "
            f"Focus on pre-committing to your action range for these spots before the hand begins."
        )
    if lang == 'es':
        act = action_es.get(top["best_action"], top["best_action"])
        st  = street_es.get(top["street"], top["street"])
        icm = icm_es.get(top["icm_pressure"], top["icm_pressure"])
        return (
            f"En spots que requieren {act} {st} con {icm}, cometo errores el {err_pct}% de las veces — "
            f"{delta}% por encima de mi promedio personal del {avg_pct}%. "
            f"Esto revela una tendencia a desviarme de la línea correcta bajo presión. "
            f"Pre-comprométete con tu rango de acción para estos spots antes de que comience la mano."
        )
    act = action_pt.get(top["best_action"], top["best_action"])
    st  = street_pt.get(top["street"], top["street"])
    icm = icm_pt.get(top["icm_pressure"], top["icm_pressure"])
    return (
        f"Em spots que exigem {act} {st} com {icm}, erro {err_pct}% das vezes — "
        f"{delta}% acima da minha média pessoal de {avg_pct}%. "
        f"Isso revela uma tendência a desviar da linha correta sob pressão. "
        f"Pré-comprometimento com o range de ação para esses spots antes da mão começa pode corrigir isso."
    )



# ── AI Coach conversacional ────────────────────────────────────────────────────

def coach_chat_reply(message: str, leaks: list, evolution: list,
                     hero: str = 'Jogador', frequencies: dict | None = None,
                     leak_source: str = 'gto', ev_leaks: list | None = None) -> str:
    """Responde pergunta do usuário com contexto real de desempenho.

    leak_source: 'gto' (default) ou 'heuristic' — origem dos leaks. Informa o Claude
    sobre a confiança da fonte para contextualizar a resposta.
    """
    import requests as _req

    ctx_parts: list[str] = []

    if leaks:
        source_note = {
            'gto': ' (fonte: análise GTO, alta confiança)',
            'heuristic': ' (fonte: análise heurística, confiança moderada — cobertura GTO insuficiente)',
        }.get(leak_source, '')
        leaks_txt = '\n'.join(
            f"  - {l['spot']}: {l['n']} ocorrências, score médio {l['avg_score']:.3f} "
            f"({'crítico' if l['avg_score'] >= .36 else 'moderado' if l['avg_score'] >= .20 else 'leve'})"
            for l in leaks[:5]
        )
        ctx_parts.append(f"Top leaks detectados{source_note}:\n{leaks_txt}")

    if ev_leaks:
        evloss_txt = '\n'.join(
            f"  - {l.get('position', '?')} {l.get('street', '')} (ideal: {l.get('ideal_action', '')}): "
            f"−{l.get('total_ev_loss_bb', 0)} bb em {l.get('n', 0)} decisões"
            for l in ev_leaks[:5]
        )
        ctx_parts.append("Vazamentos que mais custam EV (bb perdidos vs a melhor jogada — "
                         "priorize estes ao orientar):\n" + evloss_txt)

    if evolution:
        recent = evolution[-5:]
        ev_txt = '\n'.join(
            f"  - {e.get('tournament_id','?')}: "
            f"score médio={e.get('avg_score',0):.3f}, "
            f"Standard%={e.get('standard_pct',0):.1f}%"
            for e in recent
        )
        ctx_parts.append(f"Últimos {len(recent)} torneios:\n{ev_txt}")

    if frequencies:
        freq_lines: list[str] = []
        by_street = frequencies.get('by_street', {})
        for street in ['preflop', 'flop', 'turn', 'river']:
            data = by_street.get(street)
            if not data:
                continue
            parts = ', '.join(
                f"{a} {pct:.0f}%"
                for a, pct in data['pcts'].items()
            )
            freq_lines.append(f"  {street} ({data['total']} decisões): {parts}")

        by_pos = frequencies.get('by_position', {})
        if by_pos:
            pos_lines: list[str] = []
            for pos, data in by_pos.items():
                parts = ', '.join(
                    f"{a} {pct:.0f}%"
                    for a, pct in list(data['pcts'].items())[:3]
                )
                pos_lines.append(f"  {pos} ({data['total']}m): {parts}")
            if pos_lines:
                freq_lines.append("Preflop por posição:\n" + '\n'.join(pos_lines))

        if freq_lines:
            ctx_parts.append("Frequências de ação:\n" + '\n'.join(freq_lines))

    context = '\n\n'.join(ctx_parts) if ctx_parts else 'Nenhum dado de desempenho disponível ainda.'

    system = (
        f"Você é o Coach IA do PokerLeaks, assistente tático de poker MTT de elite. "
        f"Seu aluno é {hero}.\n\n"
        f"Dados reais de desempenho atual:\n{context}\n\n"
        "Use esses dados para personalizar cada resposta. Quando perguntado sobre "
        "frequências (ex: 3-bet%, fold%, VPIP), use os dados de frequência acima. "
        "Seja direto e técnico. "
        f"Português do Brasil. {_POKER_TERMS_EN} Máximo 350 palavras."
    )

    safe_message = sanitize_llm_input(message, max_len=1000)
    payload = {
        'model':      'claude-haiku-4-5-20251001',
        'max_tokens': 700,
        'system':     system,
        'messages':   [{'role': 'user', 'content': safe_message}],
    }

    try:
        return _call_llm_api(payload)
    except Exception as e:
        return f'Coach temporariamente indisponível. Erro: {str(e)}'


def analyze_single_decision(decision: dict) -> str:
    """Análise focada de uma única decisão de mão pelo Coach IA.

    decision é um dict com os campos da tabela decisions:
    street, hero_cards, board, action_taken, best_action, label, score,
    m_ratio, icm_pressure, stack_bb, draw_profile, position, num_players,
    level_sb, level_bb, level_num, note, gto_label, gto_action.
    """
    import json as _json

    street      = decision.get('street', 'preflop')
    hero_cards  = decision.get('hero_cards', '')
    board_raw   = decision.get('board', '[]')
    action      = decision.get('action_taken', '')
    best        = decision.get('best_action', '')
    label       = decision.get('label', 'standard')
    score       = decision.get('score', 0)
    m_ratio     = decision.get('m_ratio')
    icm         = decision.get('icm_pressure', 'low')
    stack_bb    = decision.get('stack_bb')
    draw        = decision.get('draw_profile', 'none')
    position    = decision.get('position', '')
    num_players = decision.get('num_players')
    level_sb    = decision.get('level_sb')
    level_bb    = decision.get('level_bb')
    level_num   = decision.get('level_num')
    note        = sanitize_llm_input(decision.get('note', '') or '', max_len=500)
    gto_label   = decision.get('gto_label')
    gto_action  = decision.get('gto_action')

    try:
        board_list = _json.loads(board_raw) if isinstance(board_raw, str) else board_raw
        board_str  = ' '.join(board_list) if board_list else '—'
    except Exception:
        board_list = []
        board_str  = '—'

    level_info = ''
    if level_num:
        level_info = f'Nível {level_num}'
        if level_sb and level_bb:
            level_info += f' ({int(level_sb)}/{int(level_bb)})'
    elif level_sb and level_bb:
        level_info = f'Blinds {int(level_sb)}/{int(level_bb)}'

    vs_info = f'vs {num_players - 1}' if num_players and num_players > 1 else ''

    label_pt = {
        'standard':     'Linha sólida',
        'marginal':     'Decisão marginal',
        'small_mistake':'Pequeno erro',
        'clear_mistake':'Erro claro',
    }.get(label, label)

    hand_desc = (
        f"Street: {street.upper()}\n"
        f"Cartas do hero: {hero_cards or '—'}\n"
        f"Board: {board_str}\n"
        f"Posição: {position or '—'}  {vs_info}\n"
        f"{level_info}\n"
        f"Stack: {f'{stack_bb:.0f} BB' if stack_bb else '—'}  |  M ratio: {m_ratio or '—'}  |  ICM: {icm}\n"
        f"Draw profile: {draw}\n"
        f"Ação tomada: {action}\n"
        f"Ação recomendada: {best}\n"
        f"Avaliação: {label_pt} (score {score:.3f})\n"
    )
    if note:
        hand_desc += f"Nota do engine: {note}\n"

    # Bloco GTO Solver — apenas postflop (preflop usa range tables próprias)
    if street != 'preflop' and (gto_label or gto_action):
        strategy_dist = ''
        try:
            from leaklab.gto_utils import compute_spot_hash
            from database.repositories import get_gto_node
            board_for_hash = (board_list[:3] if street == 'flop'
                              else board_list[:4] if street == 'turn'
                              else board_list)
            facing_bb  = float(decision.get('facing_bet') or 0)
            stack_val  = float(stack_bb or 100)
            node = get_gto_node(
                compute_spot_hash(street, position or '', board_for_hash, [], stack_val, facing_bb)
            )
            if node and node.get('strategy_json'):
                strat = (_json.loads(node['strategy_json'])
                         if isinstance(node['strategy_json'], str)
                         else node['strategy_json'])
                if isinstance(strat, dict):
                    parts = [f"{act} {int(freq * 100)}%"
                             for act, freq in sorted(strat.items(), key=lambda x: -x[1])]
                    strategy_dist = '  |  '.join(parts)
        except Exception:
            pass

        hand_desc += f"\nGTO Solver:\n"
        hand_desc += f"  Ação recomendada: {gto_label or gto_action}\n"
        if strategy_dist:
            hand_desc += f"  Distribuição: {strategy_dist}\n"
        hero_norm = (action or '').lower().rstrip('s')
        gto_norm  = (gto_label or gto_action or '').lower()
        if hero_norm and gto_norm:
            aligned = hero_norm in gto_norm or gto_norm in hero_norm
            hand_desc += f"  Ação do hero: {'ALINHADA' if aligned else 'DIVERGE'} com GTO Solver\n"

    system = """Você é um coach de poker MTT de elite. Analise a decisão abaixo e escreva em TEXTO CORRIDO estruturado — NÃO retorne JSON, NÃO use chaves {}, NÃO use colchetes [].

Use EXATAMENTE este formato Markdown:

### ❌ O Erro
Explique em 3-4 frases o que foi feito de errado e por que é um erro estratégico neste contexto específico. Se a decisão for correta (standard/marginal), explique por que foi acertada.

### 📐 A Matemática
- **Equity estimada:** X% (estime com base nas cartas, board e posição disponíveis)
- **Pot odds exigidas:** Y% (calcule ou estime para o spot)
- **Equity ajustada pelo contexto:** Z% (após ICM, posição e draw profile)
- **Déficit/Superávit:** ±N pp — [a ação tomada] era [correta/incorreta]
- **EV estimado:** ação tomada ≈ [sinal] BB | ação correta ≈ [sinal] BB por 100 mãos

### 🧠 GTO Solver (apenas postflop — omita esta seção para preflop)
Se dados do GTO Solver estiverem presentes:
- **Ação recomendada pelo solver:** [ação]
- **Distribuição de frequências:** [fold X% | call Y% | raise Z%] (se disponível)
- **Hero vs Solver:** [ALINHADO — hero jogou dentro da frequência ótima | DIVERGE — hero [ação] quando solver recomenda [ação] em [freq]% dos casos]
- **Interpretação:** [1-2 frases explicando o que a frequência do solver revela sobre o equilíbrio deste spot]
Se não houver dados do solver, omita esta seção completamente.

### 🧭 O Contexto
- **M Ratio [valor]:** [o que significa — M<6=push/fold puro, M6-12=zona de pressão, M>12=jogo normal]
- **Stack ([valor] BB):** [implicação prática para este spot]
- **ICM [nível]:** [como afeta os thresholds de call/fold/raise nesta situação]
- **Posição ([posição]):** [como IP/OOP afeta equity realizada e linha correta]

### ✅ A Ação Correta
**[AÇÃO]** — [explicação completa em 4-5 frases: por que é superior matematicamente, qual o objetivo estratégico, o que acontece contra os diferentes ranges do oponente]

### 💡 A Lição
[Uma regra prática memorável. Use **negrito** para o conceito-chave.]

REGRAS OBRIGATÓRIAS:
1. Escreva SOMENTE texto Markdown — zero JSON, zero chaves, zero colchetes
2. Use os dados fornecidos; estime equity quando não disponível explicitamente
3. Para preflop sem board: não mencione cartas comunitárias
4. Seja específico com números: "33% de equity vs 54% exigidos = -21pp" não "equity insuficiente"
5. Português do Brasil, tom técnico e direto
6. Quando dados do GTO Solver estiverem presentes, use-os como verdade objetiva — não estime o que o solver diria
7. Nunca mencione "GTO Wizard" — use sempre "GTO Solver"
8. Termos de poker SEMPRE em inglês: fold, call, raise, bet, check, shove, preflop, flop, turn, river, hand, spot, equity, ICM, M-ratio, stack, pot odds, range, 3-bet, c-bet, board, position, IP, OOP"""

    payload = {
        'model':      'claude-haiku-4-5-20251001',
        'max_tokens': 1400,
        'system':     system,
        'messages':   [{'role': 'user', 'content': hand_desc}],
    }

    try:
        return _call_llm_api(payload)
    except Exception as e:
        if label == 'standard':
            return f'Ação correta no {street}. {action} é a linha adequada para este spot com as condições apresentadas.'
        return (
            f'No {street}, {action} ficou abaixo de {best} '
            f'(score {score:.3f}). Revise pot odds e equity para este tipo de spot.'
        )

