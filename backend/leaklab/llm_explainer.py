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

_NO_DASH_RULE = (
    " Regra de estilo OBRIGATÓRIA: NUNCA use travessão (—) nem hífen como pontuação "
    "separando orações; use vírgula, dois-pontos ou ponto. Hífen apenas em palavra "
    "composta (ex.: pré-flop). Travessão soa texto de robô."
)


def _with_no_dash(payload: dict) -> dict:
    """Acrescenta a regra anti-travessão ao system do payload (copy gerada soa humana).
    Idempotente: não duplica se o system já menciona a regra."""
    try:
        sys_txt = payload.get('system')
        if sys_txt and 'travessão' not in str(sys_txt):
            p = dict(payload)
            p['system'] = str(sys_txt) + _NO_DASH_RULE
            return p
    except Exception:
        pass
    return payload


def _call_llm_api(payload: dict) -> str:
    """Chama a API do Claude com um payload já construído. Retorna texto bruto."""
    import requests as _req
    payload = _with_no_dash(payload)
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
    text = ''.join(
        block['text'] for block in data.get('content', [])
        if block.get('type') == 'text'
    ).strip()
    return _sanitize_player_out(text)


# Trava determinística de saída player-facing: troca travessão/meia-risca usados como pontuação
# (cercados por espaço) por vírgula. Não toca em hífen de palavra composta (pré-flop, check-raise)
# nem em ranges sem espaço (5–10bb), só na pontuação que "soa IA". Independe do prompt.
import re as _re_out
_OUT_DASH = _re_out.compile(r' +[—–] +')


def _sanitize_player_out(text: str) -> str:
    if not text:
        return text
    return _OUT_DASH.sub(', ', text)


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

        # Bloco INTENÇÃO da aposta (value / proteção / semi-blefe / blefe / "o meio")
        bet_intent_block = ''
        bi = d.get('bet_intent') or {}
        if bi.get('intent'):
            _intent_pt = {
                'value_showdown':   'APOSTA POR VALOR — a mão é forte; aposta pra que mãos piores paguem e o hero lucre com elas',
                'value_protection': 'VALOR + PROTEÇÃO — a mão está na frente mas o board pode dar projeto ao vilão; a aposta cobra caro pra ele continuar e protege a mão (flop/turn)',
                'semi_bluff':       'SEMI-BLEFE — ainda sem mão feita, mas com projeto (flush/sequência) que pode completar; a aposta pode levar fold agora e, se pagar, ainda há cartas pra melhorar',
                'middle':           'FORÇA MÉDIA — mão boa pra ganhar de um blefe no showdown, mas fraca demais pra apostar por valor; ao apostar, as piores foldam e só as melhores pagam (o hero só leva call quando está atrás), então quase sempre dar check é melhor',
                'bluff':            'BLEFE — a mão provavelmente está atrás; aposta pra fazer uma mão melhor foldar',
            }
            _il = ["\n── INTENÇÃO DA APOSTA (por que apostar: valor ou blefe?) ──"]
            _il.append(f"Intenção classificada: {_intent_pt.get(bi['intent'], bi['intent'])}")
            if bi.get('gto_bet_freq') is not None:
                _il.append(f"Frequência com que o GTO aposta esta mão neste spot: {round(bi['gto_bet_freq'] * 100, 1)}%")
            if bi.get('is_leak'):
                _il.append("⚠ A aposta não tem um objetivo claro: o GTO prefere dar check aqui — não é spot de valor nem de blefe lucrativo. Explique isso ao aluno em linguagem simples.")
            bet_intent_block = '\n'.join(_il) + '\n'

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
            + bet_intent_block
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
        "Tom: direto, técnico mas acessível, como um coach falando com o aluno após a sessão. "
        "Cubra obrigatoriamente estes 4 tópicos, um por parágrafo: "
        "(1) visão geral da qualidade das decisões, "
        "(2) o principal leak identificado, "
        "(3) como o jogador se comportou sob pressão de ICM, "
        "(4) um conselho concreto de foco para a próxima sessão. "
        "É obrigatório terminar o parágrafo 4 com uma frase de encerramento completa. "
        "NÃO use bullet points. Escreva em prosa fluida. "
        f"{_POKER_TERMS_EN} "
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
        f"{_POKER_TERMS_EN} "
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
    """Formata HUD stats para o prompt do LLM, usando a fonte ÚNICA STAT_REFERENCES
    (mesmas faixas do dashboard) + GATE DE AMOSTRA: stats abaixo do mínimo confiável
    são marcados como NÃO acionáveis (o LLM não deve gerar correção em cima de ruído)."""
    if not stats or stats.get('total_hands', 0) == 0:
        return ''
    from leaklab.opponent_stats import STAT_REFERENCES, classify_stat
    sample = stats.get('total_hands', 0)

    # (label, chave, unidade[, faixa inline p/ stats SEM referência])
    rows = [
        ('VPIP', 'vpip', '%'), ('PFR', 'pfr', '%'), ('AF (postflop)', 'af', 'x'),
        ('C-Bet%', 'cbet_pct', '%'), ('Fold to 3BET', 'fold_to_3bet', '%'),
        ('WTSD', 'wtsd', '%'), ('3BET%', 'three_bet', '%'), ('W$SD', 'w_at_sd', '%'),
        ('Steal%', 'steal_pct', '%'),
        ('Fold vs Flop Bet', 'fold_to_flop_bet', '%', (40, 55)),
        ('BB Defense', 'bb_defense', '%', (35, 55)),
        ('Open Limp%', 'open_limp_pct', '%', (0, 5)),
    ]
    lines = ['\n**Perfil de Jogo — HUD Stats comportamentais (com gate de amostra):**']
    for row in rows:
        label, key, unit = row[0], row[1], row[2]
        val = stats.get(key)
        if val is None:
            lines.append(f'  - {label}: sem dados'); continue
        fmt = f'{val:.1f}x' if unit == 'x' else f'{val:.1f}%'
        c = classify_stat(key, val, sample)
        if c is not None:                       # tem referência (STAT_REFERENCES)
            lo, hi = c['healthy']
            rng = f'{lo:.0f}–{hi:.0f}{unit}'
            if c['band'] == 'low_sample':
                lines.append(f"  - {label}: {fmt} — AMOSTRA INSUFICIENTE "
                             f"({sample}/{STAT_REFERENCES[key]['min']} mãos): NÃO acionável")
            elif c['band'] == 'healthy':
                lines.append(f'  - {label}: {fmt} ✓ saudável ({rng})')
            else:                               # above / below → tendência direcional
                arrow = '↑' if c['band'] == 'above' else '↓'
                lines.append(f'  - {label}: {fmt} ⚠ {arrow} {c["flag"]} (saudável {rng})')
        else:                                   # sem referência → faixa inline
            lo, hi = row[3]
            note = '✓ ok' if lo <= val <= hi else f'fora ({lo:.0f}–{hi:.0f}{unit})'
            lines.append(f'  - {label}: {fmt} {note}')

    lines.append(f'  (baseado em {sample} mãos. Stats marcados "AMOSTRA INSUFICIENTE" '
                 'NÃO são read confiável — não gere correção em cima deles.)')
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


# Refresh-por-drift do plano de estudo: o plano canônico é regenerado quando os dados "driftam"
# o suficiente — a cada _STUDY_PLAN_DRIFT_TOURNEYS torneios novos OU quando os top-3 leaks mudam.
# Flutuação pequena (mesma faixa de torneios, mesmos leaks) NÃO regenera → estabilidade do plano.
_STUDY_PLAN_DRIFT_TOURNEYS = 10

def _study_plan_drift_sig(leaks: list, evolution: list) -> str:
    import hashlib
    n_bucket = len(evolution or []) // max(1, _STUDY_PLAN_DRIFT_TOURNEYS)
    # Identidade QUALITATIVA dos top-3 leaks (sem magnitude — bb/contagem flutuam e não devem regerar).
    _QUAL = ('street', 'best_action', 'action', 'position', 'leak', 'leak_type', 'key', 'pattern', 'spot', 'category')
    parts = []
    for l in (leaks or [])[:3]:
        if isinstance(l, dict):
            parts.append('|'.join(f"{k}={l[k]}" for k in _QUAL if l.get(k) is not None))
        else:
            parts.append(str(l))
    sig = hashlib.md5('|'.join(parts).encode()).hexdigest()[:8]
    return f"t{n_bucket}_{sig}"


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
                    'source': leak_source, 'ev': ev_leaks or []}, sort_keys=True, default=str).encode()
    ).hexdigest()
    # Chave DB estável (1 linha/aluno); o fingerprint de drift fica no VALOR.
    db_key = 'study_plan_current'
    drift_sig = _study_plan_drift_sig(leaks, evolution)

    if not force_new:
        # Cache em memória
        if mem_key in _cache:
            return json.loads(_cache[mem_key])
        # Cache persistente no banco — só serve se os dados NÃO driftaram (refresh-por-drift).
        if user_id is not None:
            try:
                from database.repositories import get_llm_cache
                cached = get_llm_cache(user_id, db_key)
                if cached:
                    _obj = json.loads(cached)
                    if isinstance(_obj, dict) and 'plan' in _obj and _obj.get('_drift') == drift_sig:
                        _cache[mem_key] = json.dumps(_obj['plan'], ensure_ascii=False)
                        return _obj['plan']
                    # formato antigo (sem _drift) ou driftou → cai pra regenerar
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
    ev_txt = _format_ev_leaks_weighted(ev_leaks) if ev_leaks else ''

    # Nível (ELO) pré-computado — o LLM usa como referência, não adivinha o 'nivel'.
    level_label = None
    if user_id is not None:
        try:
            from database.repositories import get_player_level
            _lv = get_player_level(user_id) or {}
            level_label = _lv.get('label') or _lv.get('level')
        except Exception:
            level_label = None

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
- Pior fase ICM: pressão {icm_weak}{('''
- Nível estimado (ELO): ''' + level_label) if level_label else ''}
{hud_txt}
**Leaks identificados (por frequência de erro):**{source_note}
{leaks_txt}
{('''
**Vazamentos por EV PONDERADO (já ranqueado em CÓDIGO — siga ESTA ordem; "confiança baixa" = amostra pequena, possível variância, NÃO priorize):**
''' + ev_txt) if ev_txt else ''}

## Instrução de Coach

Use os HUD Stats comportamentais para enriquecer o diagnóstico: se VPIP alto + PFR baixo, o jogador é loose-passive; se AF abaixo de 2x, o postflop é passivo demais; se Open Limp% acima de 5%, há problema de fold equity pré-flop; se BB Defense baixa, o jogador está sendo exploitado no big blind. Cruze os HUD Stats com os Leaks identificados para gerar módulos muito mais específicos e personalizados.

REGRAS DE PRIORIZAÇÃO E AMOSTRA (siga à risca):
- Ordene os cards pela ordem do "EV PONDERADO" acima (já calculado em código). NÃO recalcule nem reordene por bb bruto.
- GATE: NÃO gere card de correção para HUD stats marcados "AMOSTRA INSUFICIENTE". Liste-os em "observar_mais_dados" (sample atual vs necessário + por que esperar).
- NÃO force 6 cards. Se só há N leaks acionáveis e CONFIÁVEIS, entregue N (entre 1 e 6). NÃO invente leaks que os dados não mostram.
- Leaks marcados "confiança baixa" (amostra pequena): se incluir, sinalize a incerteza no diagnóstico e rebaixe a prioridade. Itens fracos/ruidosos vão em "nao_focar_agora".
- Use o "Nível estimado (ELO)" como referência para o campo "nivel".

Cada card deve ter:
1. Título direto e específico ao leak (máx 6 palavras)
2. Diagnóstico: 2-3 frases — RAIZ do problema + impacto em EV/bb (cite o custo em bb quando houver)
3. Conceitos-chave: 2-4 conceitos teóricos a dominar
4. Recursos: descreva o TIPO de material e o conceito a buscar (ex: "vídeo sobre defesa de BB vs steal em MTT", "teoria de ICM em bolha"). NÃO invente títulos de livros, nomes de vídeos nem URLs específicos.
5. Exercício prático: rotina CONCRETA e mensurável, dimensionada pra ~2h/semana de estudo (estimativa)
6. Métrica de progresso: como saber que melhorou

ESTILO: nos textos (diagnóstico, conceitos, exercício, resumo) NUNCA use travessão (—) nem hífen como pontuação separando orações; use vírgula, dois-pontos ou ponto. Hífen só em palavra composta.

Responda APENAS com JSON válido, sem texto adicional, no formato:
{{
  "nivel": "iniciante|intermediario|avancado",
  "resumo": "2-3 frases: perfil de erros, padrões principais e caminho de evolução",
  "cards": [
    {{
      "prioridade": "p1",
      "icone": "♠|♥|♦|♣",
      "titulo": "título do tópico",
      "diagnostico": "raiz do problema + impacto em EV/bb",
      "conceitos": ["conceito 1", "conceito 2"],
      "recursos": {{
        "livros": ["TIPO de material + conceito — sem inventar título"],
        "videos": ["tipo de vídeo/conceito a buscar"],
        "curso": "tipo de treinamento ou string vazia"
      }},
      "exercicio": "rotina prática concreta e mensurável",
      "metrica": "como medir o progresso",
      "spot": "street/action do leak",
      "ev_ponderado": "−X bb (copie do EV PONDERADO acima, ou null)",
      "confianca_amostra": "alta|média|baixa"
    }}
  ],
  "observar_mais_dados": [
    {{ "indicador": "WTSD", "valor_atual": "40%", "sample_atual": 897, "sample_necessario": 1000, "por_que_esperar": "abaixo da amostra confiável — pode ser ruído" }}
  ],
  "nao_focar_agora": [
    {{ "item": "leak ou stat", "motivo": "amostra pequena / EV baixo / variância" }}
  ]
}}

(cards: entre 1 e 6, só os acionáveis. observar_mais_dados/nao_focar_agora podem ser [] se não houver.)"""

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
        # Persistir no banco (chave estável, sobrescreve) com o fingerprint de drift no valor.
        if user_id is not None:
            try:
                from database.repositories import set_llm_cache
                set_llm_cache(user_id, db_key, json.dumps({'_drift': drift_sig, 'plan': result}, ensure_ascii=False))
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


# ── Plano de estudos — loop agêntico (tool use + structured output) ─────────────
#
# Diferença de altitude vs o coach chat: aqui NÃO faz sentido buscar os dados de
# resumo sob demanda — um plano de estudos é um diagnóstico COMPLETO e sempre quer
# leaks + EV + HUD. Esses ficam pré-carregados (como no single-shot legado). O que
# o loop adiciona é INVESTIGAÇÃO DE PROFUNDIDADE VARIÁVEL: para cada leak top, o
# modelo pode puxar as MÃOS REAIS por trás dele e o detalhe de alinhamento GTO, e
# então escrever um módulo ancorado nos dados do jogador — não conselho genérico.
# A saída final é estruturada via a ferramenta terminal submit_study_plan (o schema
# é validado pela API → JSON sempre válido, sem strip de markdown nem recuperação).

# ── Pré-computação (passo 1): tira cálculo/gate de dentro do LLM ─────────────────
def _ev_confidence(n: int) -> tuple[float, str]:
    """Fator de encolhimento por nº de decisões — penaliza variância de amostra pequena.
    Um leak de 3 decisões NÃO pode superar um padrão confiável de 24."""
    if n >= 10:
        return 1.0, 'alta'
    if n >= 5:
        return 0.6, 'média'
    return 0.3, 'baixa'


def _weighted_ev_leaks(ev_leaks: list | None) -> list:
    """Ranqueia leaks por EV PONDERADO = bb total × confiança (shrink por nº de decisões).
    Calculado em CÓDIGO (determinístico) — o LLM não computa, só prioriza pela ordem dada."""
    out = []
    for l in (ev_leaks or []):
        n     = int(l.get('n', 0) or 0)
        total = float(l.get('total_ev_loss_bb', 0) or 0)
        factor, conf = _ev_confidence(n)
        out.append({**l, 'ev_ponderado': round(total * factor, 2), 'confianca_amostra': conf})
    # tiered: confiança ALTA primeiro (por EV ponderado), depois média, depois baixa —
    # assim um leak confiável de 24 decisões nunca fica atrás de variância de 3 decisões.
    _rank = {'alta': 0, 'média': 1, 'baixa': 2}
    out.sort(key=lambda x: (_rank.get(x.get('confianca_amostra'), 3), -x.get('ev_ponderado', 0)))
    return out


def _format_ev_leaks_weighted(ev_leaks: list | None) -> str:
    """Texto dos vazamentos por EV PONDERADO (já ranqueado + flag de variância)."""
    weighted = _weighted_ev_leaks(ev_leaks)
    return '\n'.join(
        f"  - {l.get('position', '?')} {l.get('street', '')} (ideal: {l.get('ideal_action', '')}): "
        f"−{l.get('total_ev_loss_bb', 0)} bb em {l.get('n', 0)} decisões → "
        f"EV ponderado −{l.get('ev_ponderado', 0)} bb (confiança {l.get('confianca_amostra', '?')}"
        f"{'; AMOSTRA PEQUENA — possível variância, não priorize' if l.get('confianca_amostra') == 'baixa' else ''})"
        for l in weighted[:6]
    )


def _build_study_diagnosis_block(leaks: list, evolution: list, icm: dict,
                                 hero: str, player_stats: dict | None,
                                 leak_source: str, ev_leaks: list | None,
                                 level_label: str | None = None) -> str:
    """Monta o bloco de diagnóstico (dados do jogador) compartilhado pelo prompt."""
    total_dec  = sum((e.get('decisions_count') or 0) for e in evolution) or 1
    avg_score  = sum((e.get('avg_score') or 0) * (e.get('decisions_count') or 0)
                     for e in evolution) / total_dec
    avg_std    = sum((e.get('standard_pct') or 0) * (e.get('decisions_count') or 0)
                     for e in evolution) / total_dec
    avg_clear  = sum((e.get('clear_pct') or 0) * (e.get('decisions_count') or 0)
                     for e in evolution) / total_dec
    n_torneios = len(evolution)
    icm_weak   = max(icm.items(),
                     key=lambda x: 1 - x[1].get('standard_rate', 1),
                     default=('—', {}))[0] if icm else '—'

    leaks_txt = '\n'.join(
        f"  - {l['spot']}: {l['n']} ocorrências, score médio {l['avg_score']:.3f} "
        f"({'crítico' if l['avg_score'] >= .36 else 'moderado' if l['avg_score'] >= .20 else 'leve'})"
        for l in leaks[:8]
    )
    ev_txt   = _format_ev_leaks_weighted(ev_leaks) if ev_leaks else ''
    hud_txt  = _format_hud_stats_for_prompt(player_stats) if player_stats else ''
    lvl_line = f"\n- Nível estimado (ELO): {level_label}" if level_label else ''
    source_note = {
        'gto':       '\n(Leaks via análise GTO — comparação direta com solver. Alta confiança.)',
        'heuristic': '\n(Leaks via análise heurística do engine — confiança moderada.)',
        'empty':     '',
    }.get(leak_source, '')

    block = f"""## Dados do Jogador ({hero})

**Métricas gerais ({n_torneios} torneios analisados):**
- Score médio de erro: {avg_score:.4f} (meta: abaixo de 0.08)
- Standard% (decisões corretas): {avg_std:.1f}% (meta: acima de 80%)
- Erros claros: {avg_clear:.1f}% (meta: abaixo de 5%)
- Pior fase ICM: pressão {icm_weak}{lvl_line}
{hud_txt}
**Leaks identificados (por frequência de erro):**{source_note}
{leaks_txt}"""
    if ev_txt:
        block += ("\n\n**Vazamentos por EV PONDERADO (já ranqueado em CÓDIGO — siga ESTA ordem; "
                  "leaks 'confiança baixa' podem ser variância de amostra pequena, NÃO priorize):**\n"
                  + ev_txt)
    return block


_STUDY_PLAN_CARD_SCHEMA = {
    'type': 'object',
    'properties': {
        'prioridade':  {'type': 'string', 'description': 'p1..p6, na ordem de prioridade de EV.'},
        'icone':       {'type': 'string', 'description': 'Um naipe: ♠ ♥ ♦ ♣'},
        'titulo':      {'type': 'string', 'description': 'Título direto e específico ao leak (máx 6 palavras).'},
        'diagnostico': {'type': 'string', 'description': 'Raiz do problema e impacto em EV/bb. Cite o custo em bb e as mãos reais investigadas quando houver.'},
        'conceitos':   {'type': 'array', 'items': {'type': 'string'}, 'description': '2-4 conceitos teóricos a dominar.'},
        'recursos': {
            'type': 'object',
            'properties': {
                'livros': {'type': 'array', 'items': {'type': 'string'}},
                'videos': {'type': 'array', 'items': {'type': 'string'}},
                'curso':  {'type': 'string', 'description': 'Nome do curso/treinamento, ou string vazia.'},
            },
        },
        'exercicio': {'type': 'string', 'description': 'Rotina prática concreta e mensurável para hoje.'},
        'metrica':   {'type': 'string', 'description': 'Como medir o progresso neste leak.'},
        'spot':      {'type': 'string', 'description': 'street/action do leak principal.'},
        'ev_ponderado':      {'type': 'string', 'description': '−X bb (copie do EV PONDERADO do diagnóstico), ou vazio.'},
        'confianca_amostra': {'type': 'string', 'enum': ['alta', 'média', 'baixa'], 'description': 'Confiança da amostra do leak.'},
    },
    'required': ['prioridade', 'titulo', 'diagnostico', 'conceitos', 'exercicio', 'metrica', 'spot'],
}

_STUDY_TOOLS = [
    {
        'name': 'get_leak_hands',
        'description': (
            'Retorna as mãos REAIS do jogador por trás de um leak: as decisões com erro '
            'GTO ou EV perdido em um street/posição específicos, da que mais sangra para a '
            'que menos. Use para ancorar o diagnóstico de um módulo em mãos concretas (cartas, '
            'board, ação tomada vs ideal, bb perdidos) em vez de conselho genérico.'
        ),
        'input_schema': {
            'type': 'object',
            'properties': {
                'street':   {'type': 'string', 'description': 'preflop|flop|turn|river (opcional).'},
                'position': {'type': 'string', 'description': 'Posição do hero, ex: BTN, SB, BB, CO (opcional).'},
            },
        },
    },
    {
        'name': 'get_gto_alignment',
        'description': (
            'Retorna o detalhamento de alinhamento GTO do jogador (% correto/mixed/desvio leve/'
            'crítico) quebrado por street ou por posição. Use para localizar ONDE exatamente o '
            'desvio se concentra antes de escrever o módulo.'
        ),
        'input_schema': {
            'type': 'object',
            'properties': {
                'by': {'type': 'string', 'enum': ['street', 'position'], 'description': 'Eixo do breakdown.'},
            },
        },
    },
    {
        'name': 'submit_study_plan',
        'description': (
            'Entrega o plano de estudos final. Chame UMA vez, no fim, depois de investigar os '
            'leaks top. Entre 1 e 6 cards ACIONÁVEIS (NÃO force 6), ordenados por EV ponderado.'
        ),
        'input_schema': {
            'type': 'object',
            'properties': {
                'nivel':  {'type': 'string', 'enum': ['iniciante', 'intermediario', 'avancado']},
                'resumo': {'type': 'string', 'description': '2-3 frases sobre o perfil de erros e o caminho de evolução.'},
                'cards':  {'type': 'array', 'items': _STUDY_PLAN_CARD_SCHEMA,
                           'description': '1 a 6 cards ACIONÁVEIS, na ordem do EV ponderado.'},
                'observar_mais_dados': {'type': 'array', 'description': 'HUD stats abaixo da amostra confiável — não acionar ainda.',
                    'items': {'type': 'object', 'properties': {
                        'indicador': {'type': 'string'}, 'valor_atual': {'type': 'string'},
                        'sample_atual': {'type': 'integer'}, 'sample_necessario': {'type': 'integer'},
                        'por_que_esperar': {'type': 'string'}}}},
                'nao_focar_agora': {'type': 'array', 'description': 'Leaks/stats de baixa prioridade (variância, EV baixo).',
                    'items': {'type': 'object', 'properties': {
                        'item': {'type': 'string'}, 'motivo': {'type': 'string'}}}},
            },
            'required': ['nivel', 'resumo', 'cards'],
        },
    },
]


def _run_study_tool(name: str, user_id: int, tool_input: dict) -> str:
    """Executa uma ferramenta investigativa do plano, escopada ao user_id."""
    from database import repositories as _repo
    if name == 'get_leak_hands':
        rows = _repo.get_decisions_for_spot(
            user_id,
            street=tool_input.get('street') or None,
            position=tool_input.get('position') or None,
            days=90, limit=8,
        )
        return json.dumps(rows, ensure_ascii=False, default=str)
    if name == 'get_gto_alignment':
        if tool_input.get('by') == 'position':
            data = _repo.get_gto_alignment_by_position(user_id)
        else:
            data = _repo.get_gto_alignment_by_street(user_id)
        return json.dumps(data, ensure_ascii=False, default=str)
    return json.dumps({'error': f'ferramenta desconhecida: {name}'})


def generate_study_plan_agentic(leaks: list, evolution: list, icm: dict,
                                hero: str = 'Jogador',
                                user_id: int | None = None,
                                force_new: bool = False,
                                player_stats: dict | None = None,
                                leak_source: str = 'gto',
                                ev_leaks: list | None = None,
                                max_iterations: int = 8) -> dict:
    """Gera o plano de estudos via loop agêntico. Mesma assinatura/retorno de
    generate_study_plan, mas o modelo investiga cada leak em profundidade antes de
    sintetizar. Cache compartilhado com o gerador legado (db_key estável por aluno).
    """
    import hashlib

    stats_fingerprint = {
        k: v for k, v in (player_stats or {}).items()
        if k != 'total_hands' and v is not None
    } if player_stats else {}
    mem_key = 'study_plan_agentic_v1:' + hashlib.md5(
        json.dumps({'leaks': leaks, 'evo_len': len(evolution), 'stats': stats_fingerprint,
                    'source': leak_source, 'ev': ev_leaks or []}, sort_keys=True, default=str).encode()
    ).hexdigest()
    db_key = 'study_plan_current'   # mesmo do legado — plano canônico único por aluno
    drift_sig = _study_plan_drift_sig(leaks, evolution)

    if not force_new:
        if mem_key in _cache:
            return json.loads(_cache[mem_key])
        if user_id is not None:
            try:
                from database.repositories import get_llm_cache
                cached = get_llm_cache(user_id, db_key)
                if cached:
                    _obj = json.loads(cached)
                    if isinstance(_obj, dict) and 'plan' in _obj and _obj.get('_drift') == drift_sig:
                        _cache[mem_key] = json.dumps(_obj['plan'], ensure_ascii=False)
                        return _obj['plan']
                    # formato antigo ou driftou → regenera
            except Exception:
                pass

    def _finalize(plan: dict) -> dict:
        plan = dict(plan)
        plan['source'] = leak_source
        result_str = json.dumps(plan, ensure_ascii=False)
        _cache[mem_key] = result_str
        if user_id is not None:
            try:
                from database.repositories import set_llm_cache
                set_llm_cache(user_id, db_key, json.dumps({'_drift': drift_sig, 'plan': plan}, ensure_ascii=False))
            except Exception:
                pass
        return plan

    level_label = None
    if user_id is not None:
        try:
            from database.repositories import get_player_level
            _lv = get_player_level(user_id) or {}
            level_label = _lv.get('label') or _lv.get('level')
        except Exception:
            level_label = None

    diagnosis = _build_study_diagnosis_block(
        leaks, evolution, icm, hero, player_stats, leak_source, ev_leaks, level_label=level_label)

    system = (
        "Você é um coach profissional de poker MTT com 15+ anos de experiência, "
        "especialista em identificar e corrigir leaks em torneios.\n\n"
        "Você tem ferramentas para INVESTIGAR a fundo cada leak do aluno antes de montar "
        "o plano: get_leak_hands (mãos reais por trás de um leak) e get_gto_alignment "
        "(onde o desvio se concentra). Investigue os 2-3 leaks de MAIOR EV PONDERADO — cite "
        "mãos e números reais no diagnóstico — e SÓ ENTÃO chame submit_study_plan.\n\n"
        "REGRAS: ordene pela ordem do EV PONDERADO (já calculado em código); NÃO force 6 cards "
        "— entregue só os 1-6 leaks ACIONÁVEIS e confiáveis; NÃO gere card de HUD stat marcado "
        "'AMOSTRA INSUFICIENTE' (liste em observar_mais_dados); leaks 'confiança baixa' (amostra "
        "pequena) vão em nao_focar_agora ou com a incerteza sinalizada; NÃO invente títulos de "
        "livros/vídeos/URLs (descreva o tipo + conceito); use o 'Nível estimado (ELO)' como "
        "'nivel'. Não invente mãos: ferramenta vazia → use os dados de resumo.\n\n"
        f"Português do Brasil. {_POKER_TERMS_EN}"
    )
    user_msg = (
        diagnosis +
        "\n\n## Tarefa\nInvestigue os leaks de maior EV ponderado e gere o plano (1-6 módulos "
        "ACIONÁVEIS, não force 6), cada um ancorado em mãos/números reais quando possível. "
        "Cruze os HUD Stats (respeitando o gate de amostra) com os leaks. Dimensione os "
        "exercícios pra ~2h/semana de estudo (estimativa). Termine chamando submit_study_plan."
    )

    messages: list[dict] = [{'role': 'user', 'content': user_msg}]

    for _ in range(max_iterations):
        data = _call_llm_api_full({
            'model':      'claude-haiku-4-5-20251001',
            'max_tokens': 6000,
            'system':     system,
            'messages':   messages,
            'tools':      _STUDY_TOOLS,
        })
        content = data.get('content', [])
        messages.append({'role': 'assistant', 'content': content})

        tool_uses = [b for b in content if b.get('type') == 'tool_use']
        # Se o modelo entregou o plano, captura e retorna.
        for b in tool_uses:
            if b.get('name') == 'submit_study_plan':
                return _finalize(b.get('input') or {})

        if data.get('stop_reason') != 'tool_use' or not tool_uses:
            break   # respondeu em texto sem submeter — força o submit abaixo

        tool_results = []
        for b in tool_uses:
            try:
                result_str = _run_study_tool(b.get('name', ''), user_id, b.get('input') or {})
            except Exception as e:
                result_str = json.dumps({'error': str(e)})
            tool_results.append({
                'type':        'tool_result',
                'tool_use_id': b.get('id'),
                'content':     result_str,
            })
        messages.append({'role': 'user', 'content': tool_results})

    # Esgotou iterações / respondeu em texto: força a entrega estruturada.
    data = _call_llm_api_full({
        'model':       'claude-haiku-4-5-20251001',
        'max_tokens':  6000,
        'system':      system,
        'messages':    messages + [{
            'role': 'user',
            'content': 'Entregue o plano agora chamando submit_study_plan.',
        }],
        'tools':       _STUDY_TOOLS,
        'tool_choice': {'type': 'tool', 'name': 'submit_study_plan'},
    })
    for b in data.get('content', []):
        if b.get('type') == 'tool_use' and b.get('name') == 'submit_study_plan':
            return _finalize(b.get('input') or {})

    # Não deveria chegar aqui (tool_choice força a tool); fallback defensivo.
    return {'nivel': 'intermediario', 'resumo': 'Plano com IA temporariamente indisponível.',
            'cards': [], 'source': leak_source, 'error': 'ai_unavailable'}


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

import re as _re

# Trava de coerência da narrativa causal: a co-ocorrência é POR TORNEIO (mãos diferentes), então o
# texto NUNCA pode afirmar "mesma mão" nem contar a correlação em "N mãos". Se o LLM violar, o texto
# é descartado e cai no template determinístico (que é sempre coerente).
_CAUSAL_INCOHERENT = _re.compile(
    r"\b\d+\s*(m[ãa]os?|hands?|manos?)\b"          # "3 mãos" / "in 3 hands" / "3 manos"
    r"|mesm[ao]s?\s+m[ãa]os?"                       # "mesma mão", "mesmas mãos/maos"
    r"|same\s+hands?"                              # "same hand(s)"
    r"|mism[ao]s?\s+manos?",                       # "misma mano", "mismas manos"
    _re.IGNORECASE,
)


def _causal_text_is_coherent(text: str) -> bool:
    return bool(text) and not _CAUSAL_INCOHERENT.search(text)


def explain_leak_causality(edges: list, hero: str = 'você', lang: str = 'pt-BR') -> str:
    """1 parágrafo curto (2-3 frases) explicando a causa raiz dos pares mais correlacionados."""
    if not edges:
        return ""
    cache_key = "causal_v4_" + lang + "_" + "_".join(
        f"{e['source']}:{e['target']}" for e in edges[:3]
    )
    if cache_key in _cache:
        return _cache[cache_key]
    try:
        text = _call_llm_causality(edges[:3], hero, lang)
    except Exception:
        text = _template_causality(edges[:3])
    # Trava: saída incoerente (afirma "mesma mão" / conta em "mãos") → template determinístico.
    if not _causal_text_is_coherent(text):
        import logging
        logging.getLogger('llm_guard').warning('narrativa causal incoerente descartada: %r', text[:160])
        text = _template_causality(edges[:3])
    _cache[cache_key] = text
    return text


_POKER_TERMS_EN = (
    "Termos técnicos de poker SEMPRE em inglês, NUNCA traduzidos: "
    "fold, call, raise, bet, check, check-raise, check-call, check-fold, c-bet, donk bet, "
    "3-bet, 4-bet, 5-bet, shove, reshove, limp, open, squeeze, barrel, float, overbet, "
    "value bet, bluff, blocker, preflop, flop, turn, river, hand, spot, equity, ICM, M-ratio, "
    "stack, pot odds, range, board, position, IP, OOP, GTO. "
    "JAMAIS traduza termos compostos: é 'check-raise' (NUNCA 'checar aumentar', 'check aumento'), "
    "'c-bet' (NUNCA 'aposta de continuação'), 'check-call' (NUNCA 'passar e pagar'), "
    "'3-bet' (NUNCA 'terceira aposta'). Também NUNCA traduza ações isoladas: é 'check' (NUNCA 'checar'/'passar'), "
    "'raise' (NUNCA 'aumentar'), 'call' (NUNCA 'igualar'), 'bet' (NUNCA 'apostar' como termo técnico), "
    "'fold' (NUNCA 'desistir'/'correr'). Para all-in agressivo use SEMPRE 'shove', NUNCA 'jam'. "
    "NUNCA use 'rua' ou 'ruas', sempre 'street' ou 'streets'. "
    "Para conjugar em português use as formas naturais do jogador brasileiro: 'deu fold', 'deu raise', "
    "'deu check', 'deu bet', 'deu check-raise', 'deu call', e os verbos consagrados 'foldou', 'apostou', 'pagou', 'shovou'. "
    "NUNCA invente aportuguesamentos como 'raisando', 'bettando', 'foldando', 'checando', 'callando'. "
    "NUNCA use travessão nem hífen como pontuação separando orações; use vírgula, "
    "dois-pontos ou ponto. Hífen só em termo composto (ex.: check-raise, pré-flop)."
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
    from leaklab.leak_causal_graph import human_spot
    pairs = "\n".join(
        f"- {human_spot(e['source'])} ↔ {human_spot(e['target'])}: {e['correlation']:.0%} correlation "
        f"({e['co_occurrences']} tournaments together)"
        for e in edges
    )
    system_prompt = (
        f"You are a friendly MTT poker coach talking directly to a student who is still learning. {lang_instr} "
        "IMPORTANT about the data: each pair of leaks CO-OCCURS ACROSS THE SAME TOURNAMENTS, in DIFFERENT hands. "
        "They are NOT the same hand and one does NOT trigger the other within a hand. It is a session-level tendency: "
        "in those tournaments the player commits BOTH types of mistake, hinting at a shared root cause (e.g. a mindset or a miscalibrated range), NOT a chain reaction inside one hand. "
        "NEVER say or imply the two leaks happen in the same hand, and NEVER say one 'triggers'/'causes'/'leads to' the other. Always frame it as appearing together across tournaments/sessions. "
        "Analyze the leak correlations and write EXACTLY 3 SHORT sentences: "
        "(1) Describe what both mistakes look like in practice at the table, use plain language about the BEHAVIOR (what the player does), not abstract concepts. "
        "(2) Name the single habit or misunderstanding that likely produces both errors, if you use a technical term, immediately explain it in simple words in parentheses. "
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
    from leaklab.leak_causal_graph import human_spot
    top = edges[0]
    a = human_spot(top['source'])
    b = human_spot(top['target'])
    corr = int(top['correlation'] * 100)
    return (
        f"Os leaks de {a} e {b} co-ocorrem em {corr}% dos torneios analisados, "
        f"sugerindo uma causa raiz comum, provavelmente relacionada a leitura de range ou "
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


# ── AI Coach — loop agêntico (tool use) ─────────────────────────────────────────
#
# Em vez de pré-carregar TODOS os dados do aluno no system prompt (como faz
# coach_chat_reply acima), aqui o modelo recebe ferramentas e busca apenas o
# dado de que precisa para responder a pergunta. O loop:
#   modelo → pede tool → executamos no DB → devolvemos resultado → modelo → ...
# até o modelo parar de pedir ferramentas (stop_reason != 'tool_use').
#
# Segurança: o user_id é injetado pelo servidor a cada execução de ferramenta.
# O modelo escolhe QUAL dado consultar, nunca DE QUEM — não há como ele acessar
# dados de outro usuário.

_COACH_TOOLS = [
    {
        'name': 'get_top_leaks',
        'description': (
            'Retorna o ranking dos principais leaks (erros recorrentes) do aluno, '
            'priorizado por análise GTO quando disponível. Use quando o aluno '
            'perguntar sobre seus maiores erros, pontos fracos, ou o que estudar.'
        ),
        'input_schema': {
            'type': 'object',
            'properties': {
                'days': {'type': 'integer', 'description': 'Janela em dias (padrão 90).'},
            },
        },
    },
    {
        'name': 'get_ev_leaks',
        'description': (
            'Retorna os spots onde o aluno mais perde EV (big blinds perdidos vs a '
            'melhor jogada), do mais caro ao mais barato. Use quando o aluno perguntar '
            'onde está perdendo mais fichas, qual erro custa mais caro, ou pedir '
            'prioridade de estudo por impacto financeiro.'
        ),
        'input_schema': {
            'type': 'object',
            'properties': {
                'days': {'type': 'integer', 'description': 'Janela em dias (padrão 90).'},
            },
        },
    },
    {
        'name': 'get_player_stats',
        'description': (
            'Retorna as estatísticas agregadas do aluno: VPIP, PFR, 3-bet%, c-bet%, '
            'aggression factor, WTSD, fold to 3-bet, etc. Use quando o aluno perguntar '
            'sobre suas tendências ou um stat específico.'
        ),
        'input_schema': {
            'type': 'object',
            'properties': {
                'days': {'type': 'integer', 'description': 'Janela em dias (padrão 90).'},
            },
        },
    },
    {
        'name': 'get_action_frequencies',
        'description': (
            'Retorna a frequência de cada ação (fold/call/raise/etc) do aluno quebrada '
            'por street e por posição. Use quando o aluno perguntar com que frequência '
            'faz uma ação em um street ou posição específica.'
        ),
        'input_schema': {
            'type': 'object',
            'properties': {
                'days': {'type': 'integer', 'description': 'Janela em dias (padrão 90).'},
            },
        },
    },
    {
        'name': 'get_recent_tournaments',
        'description': (
            'Retorna métricas de evolução por torneio recente (score médio, % de jogadas '
            'standard). Use quando o aluno perguntar sobre evolução, desempenho recente '
            'ou tendência ao longo do tempo.'
        ),
        'input_schema': {
            'type': 'object',
            'properties': {
                'days': {'type': 'integer', 'description': 'Janela em dias (padrão 90).'},
            },
        },
    },
]


def _run_coach_tool(name: str, user_id: int, tool_input: dict) -> tuple[str, str | None]:
    """Executa uma ferramenta do coach escopada ao user_id. Retorna (json_str, leak_source).

    leak_source só é preenchido por get_top_leaks (para o frontend saber a origem).
    """
    from database import repositories as _repo

    days = tool_input.get('days', 90)
    try:
        days = max(1, min(365, int(days)))
    except (TypeError, ValueError):
        days = 90

    leak_source: str | None = None
    if name == 'get_top_leaks':
        data = _repo.get_leak_ranking_gto_first(user_id, days)
        leak_source = data.get('source')
        result = {'source': leak_source, 'leaks': data.get('leaks', [])[:6]}
    elif name == 'get_ev_leaks':
        result = {'leaks': _repo.get_ev_leaks(user_id, days).get('leaks', [])[:6]}
    elif name == 'get_player_stats':
        result = _repo.get_player_stats(user_id, days)
    elif name == 'get_action_frequencies':
        result = _repo.get_player_action_frequencies(user_id, days)
    elif name == 'get_recent_tournaments':
        result = (_repo.get_evolution_metrics(user_id, days) or [])[-8:]
    else:
        return (json.dumps({'error': f'ferramenta desconhecida: {name}'}), None)

    return (json.dumps(result, ensure_ascii=False, default=str), leak_source)


def _with_prompt_cache(payload: dict) -> dict:
    """Marca breakpoints de cache_control (Anthropic prompt caching) no prefixo reutilizado.
    No loop agêntico o custo está nas MENSAGENS (tool-results reenviados a cada round-trip),
    não no system/tools (pequenos, < 2048 tokens). Então o breakpoint principal é a ÚLTIMA
    mensagem: cacheia todo o prefixo (system+tools+conversa) até ali; o round-trip seguinte lê
    a ~0.1x. Também marca o system (ajuda quando é grande, ex.: study plan). NÃO muta os objetos
    originais (a lista `messages` é reutilizada no loop — mutar acumularia breakpoints e quebraria)."""
    p = dict(payload)
    _cc = {"type": "ephemeral"}
    # system (caso seja grande o bastante sozinho)
    sys = p.get('system')
    if isinstance(sys, str) and sys.strip():
        p['system'] = [{"type": "text", "text": sys, "cache_control": _cc}]
    elif isinstance(sys, list) and sys:
        nb = [dict(b) if isinstance(b, dict) else b for b in sys]
        if isinstance(nb[-1], dict):
            nb[-1] = {**nb[-1], "cache_control": _cc}
        p['system'] = nb
    # ÚLTIMA mensagem: cacheia o prefixo todo (inclui tool-results = a parte cara)
    msgs = p.get('messages')
    if isinstance(msgs, list) and msgs:
        nm = list(msgs)
        last = dict(nm[-1])
        c = last.get('content')
        if isinstance(c, str) and c:
            last['content'] = [{"type": "text", "text": c, "cache_control": _cc}]
        elif isinstance(c, list) and c:
            nc = [dict(b) if isinstance(b, dict) else b for b in c]
            if isinstance(nc[-1], dict):
                nc[-1] = {**nc[-1], "cache_control": _cc}
                last['content'] = nc
        nm[-1] = last
        p['messages'] = nm
    return p


def _call_llm_api_full(payload: dict) -> dict:
    """Como _call_llm_api, mas devolve o JSON completo da resposta.

    Necessário para o loop de tool use, que precisa de stop_reason e dos blocos
    de conteúdo (não só do texto).
    """
    import requests as _req
    payload = _with_prompt_cache(_with_no_dash(payload))
    resp = _req.post(
        'https://api.anthropic.com/v1/messages',
        json=payload,
        headers={
            'Content-Type':      'application/json',
            'anthropic-version': '2023-06-01',
            'anthropic-beta':    'prompt-caching-2024-07-31',
            'x-api-key':         _api_key(),
        },
        timeout=90,
    )
    resp.raise_for_status()
    data = resp.json()
    # Verificação do prompt caching: loga tokens criados (1ª chamada) vs lidos do cache (0.1x).
    try:
        import logging as _lg
        _u = data.get('usage') or {}
        _cc, _cr = _u.get('cache_creation_input_tokens', 0), _u.get('cache_read_input_tokens', 0)
        if _cc or _cr:  # só loga quando o caching está ATIVO (prefixo > mínimo do modelo)
            _lg.getLogger('llm_cache').info(
                'prompt_cache created=%s read=%s input=%s output=%s',
                _cc, _cr, _u.get('input_tokens'), _u.get('output_tokens'))
    except Exception:
        pass
    return data


def coach_chat_reply_agentic(message: str, user_id: int, hero: str = 'Jogador',
                             max_iterations: int = 6) -> dict:
    """Responde a pergunta do aluno via loop agêntico com ferramentas.

    O modelo busca sob demanda apenas os dados relevantes à pergunta, em vez de
    receber tudo pré-carregado. Retorna {reply, source, tools_used}.
    """
    safe_message = sanitize_llm_input(message, max_len=1000)

    system = (
        f"Você é o Coach IA do PokerLeaks, assistente tático de poker MTT de elite. "
        f"Seu aluno é {hero}.\n\n"
        "Você tem ferramentas para consultar os dados reais de desempenho do aluno "
        "(leaks, EV perdido, estatísticas, frequências, evolução). SEMPRE que a pergunta "
        "depender desses dados, chame a ferramenta apropriada antes de responder — nunca "
        "invente números. Para perguntas conceituais gerais de estratégia, responda "
        "direto, sem ferramentas. Não chame a mesma ferramenta duas vezes para a mesma "
        "pergunta.\n\n"
        "Seja direto e técnico. Português do Brasil. "
        f"{_POKER_TERMS_EN} Máximo 350 palavras."
    )

    messages: list[dict] = [{'role': 'user', 'content': safe_message}]
    tools_used: list[str] = []
    leak_source_seen: str | None = None

    for _ in range(max_iterations):
        payload = {
            'model':      'claude-haiku-4-5-20251001',
            'max_tokens': 1024,
            'system':     system,
            'messages':   messages,
            'tools':      _COACH_TOOLS,
        }
        data    = _call_llm_api_full(payload)
        content = data.get('content', [])
        messages.append({'role': 'assistant', 'content': content})

        if data.get('stop_reason') != 'tool_use':
            reply = ''.join(
                b['text'] for b in content if b.get('type') == 'text'
            ).strip()
            return {
                'reply':       reply,
                'source':      leak_source_seen or 'agentic',
                'tools_used':  tools_used,
            }

        tool_results: list[dict] = []
        for block in content:
            if block.get('type') != 'tool_use':
                continue
            tname = block.get('name', '')
            if tname not in tools_used:
                tools_used.append(tname)
            try:
                result_str, src = _run_coach_tool(tname, user_id, block.get('input') or {})
                if src:
                    leak_source_seen = src
            except Exception as e:
                result_str = json.dumps({'error': str(e)})
            tool_results.append({
                'type':        'tool_result',
                'tool_use_id': block.get('id'),
                'content':     result_str,
            })
        messages.append({'role': 'user', 'content': tool_results})

    # Esgotou as iterações — força uma resposta final sem ferramentas.
    payload = {
        'model':      'claude-haiku-4-5-20251001',
        'max_tokens': 700,
        'system':     system,
        'messages':   messages + [{
            'role': 'user',
            'content': 'Responda agora com base no que você já consultou, sem mais ferramentas.',
        }],
    }
    reply = _call_llm_api(payload)
    return {'reply': reply, 'source': leak_source_seen or 'agentic', 'tools_used': tools_used}


# ── Deep dive de uma mão flagada — loop agêntico (tool use) ─────────────────────
#
# analyze_single_decision (single-shot) crava um nó GTO genérico no prompt e pede
# pro modelo ESTIMAR equity/pot odds. O deep-dive substitui estimativa por
# investigação: o modelo chama lookup_gto com a MÃO REAL do hero (estratégia +
# EV por ação, verdade do solver), puxa a mão INTEIRA (todos os streets) e o
# HISTÓRICO do jogador neste mesmo spot (é leak recorrente ou pontual?). Saída em
# Markdown (mesmo contrato {analysis} do single-shot → frontend inalterado).
#
# As 3 ferramentas são parametrizadas pela decisão fixa no servidor — o modelo
# escolhe O QUE investigar, nunca monta params (evita lookup_gto com args errados).

def _decision_to_gto_params(decision: dict) -> dict:
    """Deriva os parâmetros de lookup_gto a partir de uma decisão do banco."""
    street = (decision.get('street') or 'preflop').lower()
    hc     = (decision.get('hero_cards') or '').replace(' ', '')
    hero_hand = [hc[i:i+2] for i in range(0, len(hc), 2)][:2] if hc else []
    try:
        board_raw = decision.get('board', '[]')
        board = json.loads(board_raw) if isinstance(board_raw, str) else (board_raw or [])
    except Exception:
        board = []
    board = (board[:3] if street == 'flop' else board[:4] if street == 'turn'
             else board[:5] if street == 'river' else [])
    level_bb     = float(decision.get('level_bb') or 0)
    stack_bb     = float(decision.get('stack_bb') or 100)
    facing_chips = float(decision.get('facing_bet') or 0)
    pot_chips    = float(decision.get('pot_size') or 0)
    is_3bet      = bool(decision.get('is_3bet'))
    vs_position  = decision.get('vs_position') or ''
    action_seq   = 'rfi'
    if street == 'preflop':
        action_seq = 'vs_3bet' if is_3bet else ('vs_rfi' if vs_position else 'rfi')
    return {
        'street':         street,
        'position':       decision.get('position') or '',
        'board':          board,
        'hero_hand':      hero_hand,
        'hero_stack_bb':  stack_bb,
        'action_seq':     action_seq,
        'vs_position':    vs_position,
        'facing_size_bb': (facing_chips / level_bb) if level_bb else 0.0,
        'pot_bb':         (pot_chips / level_bb) if level_bb else 0.0,
        'num_players':    int(decision.get('num_players') or 9),
        'pot_type':       '3bet' if is_3bet else '',
    }


_DEEPDIVE_TOOLS = [
    {
        'name': 'get_gto_solution',
        'description': (
            'Retorna a solução GTO REAL do solver para ESTE spot exato, com a mão do hero: '
            'estratégia (ações com frequência e EV em bb) e qualidade da convergência. '
            'Use SEMPRE antes de falar de frequências/EV — é verdade objetiva, não estime. '
            'Se found=false, não há solução no banco para este spot; aí sim estime e diga isso.'
        ),
        'input_schema': {'type': 'object', 'properties': {}},
    },
    {
        'name': 'get_full_hand',
        'description': (
            'Retorna TODAS as decisões desta mesma mão (todos os streets), para você entender '
            'a história completa — não só o street isolado. Use para conectar a linha do hero '
            'através dos streets.'
        ),
        'input_schema': {'type': 'object', 'properties': {}},
    },
    {
        'name': 'get_my_history_here',
        'description': (
            'Retorna outras decisões do jogador no MESMO spot (street + posição) com erro GTO/EV. '
            'Use para dizer se este erro é RECORRENTE (padrão a corrigir) ou pontual.'
        ),
        'input_schema': {'type': 'object', 'properties': {}},
    },
]


def _run_deepdive_tool(name: str, decision: dict, user_id: int) -> str:
    """Executa uma ferramenta do deep-dive, escopada à decisão fixa e ao user_id."""
    from database import repositories as _repo
    if name == 'get_gto_solution':
        from leaklab.gto_solver import lookup_gto
        params = _decision_to_gto_params(decision)
        sol = lookup_gto(**params, block_remote=True, allow_remote_solve=False)
        return json.dumps({
            'found':              sol.get('found'),
            'source':             sol.get('source'),
            'strategy':           sol.get('strategy'),
            'exploitability_pct': sol.get('exploitability_pct'),
            'hand_strategy':      sol.get('hand_strategy'),
        }, ensure_ascii=False, default=str)
    if name == 'get_full_hand':
        rows = _repo.get_decisions_for_hand(decision.get('tournament_id'), decision.get('hand_id'))
        keep = ('street', 'position', 'hero_cards', 'board', 'action_taken',
                'best_action', 'gto_action', 'gto_label', 'score', 'ev_loss_bb')
        return json.dumps([{k: r.get(k) for k in keep} for r in rows],
                          ensure_ascii=False, default=str)
    if name == 'get_my_history_here':
        rows = _repo.get_decisions_for_spot(
            user_id, street=decision.get('street'), position=decision.get('position'),
            days=180, limit=10)
        return json.dumps(rows, ensure_ascii=False, default=str)
    return json.dumps({'error': f'ferramenta desconhecida: {name}'})


_DEEPDIVE_FORMAT = """Use EXATAMENTE este formato Markdown (texto corrido, ZERO JSON, zero chaves, zero colchetes):

### ❌ O Erro
3-4 frases: o que foi feito e por que é (ou não é) erro neste contexto específico.

### 📐 A Matemática
- **Equity estimada:** X%  •  **Pot odds exigidas:** Y%  •  **Equity ajustada (ICM/posição/draw):** Z%
- **Déficit/Superávit:** ±N pp — a ação tomada era [correta/incorreta]
- **EV:** ação tomada vs ação correta (em bb), use os números do solver quando houver

### 🧠 GTO Solver
Se get_gto_solution retornou found=true: ação recomendada, distribuição de frequências e EV por ação (dados do solver = verdade), e se o hero ALINHOU ou DIVERGIU. Se found=false, diga que não há solução no banco e que a análise é estimada. Omita a seção inteira só no preflop sem dados.

### 🧭 O Contexto
M ratio, stack em bb, ICM e posição — implicação prática de cada um para este spot.

### 🔁 Padrão
Se get_my_history_here mostrar outras ocorrências, diga se é um leak RECORRENTE e quão caro; senão, trate como pontual.

### ✅ A Ação Correta
**[AÇÃO]** — 4-5 frases: por que é superior, objetivo estratégico, o que acontece contra os ranges do oponente.

### 💡 A Lição
Uma regra prática memorável. **Negrito** no conceito-chave."""


def deep_dive_decision_agentic(decision: dict, user_id: int, max_iterations: int = 6) -> str:
    """Deep dive de uma decisão via loop agêntico. Retorna Markdown (mesmo contrato
    de analyze_single_decision). O modelo investiga GTO real + mão completa + histórico
    antes de escrever."""
    street     = (decision.get('street') or 'preflop')
    hero_cards = decision.get('hero_cards') or '—'
    try:
        board_raw  = decision.get('board', '[]')
        board_list = json.loads(board_raw) if isinstance(board_raw, str) else (board_raw or [])
        board_str  = ' '.join(board_list) if board_list else '—'
    except Exception:
        board_str = '—'
    stack_bb = decision.get('stack_bb')
    desc = (
        f"Decisão a analisar a fundo:\n"
        f"Street: {street.upper()}  |  Cartas: {hero_cards}  |  Board: {board_str}\n"
        f"Posição: {decision.get('position') or '—'}  |  "
        f"Stack: {f'{stack_bb:.0f} bb' if stack_bb else '—'}  |  "
        f"M: {decision.get('m_ratio') or '—'}  |  ICM: {decision.get('icm_pressure') or 'low'}\n"
        f"Ação tomada: {decision.get('action_taken') or '—'}  |  "
        f"Ação recomendada: {decision.get('best_action') or '—'}  |  "
        f"GTO: {decision.get('gto_label') or decision.get('gto_action') or '—'}\n"
        f"Avaliação: {decision.get('label') or 'standard'} (score {float(decision.get('score') or 0):.3f})\n\n"
        "Investigue com as ferramentas (solução GTO real, mão completa, seu histórico no spot) "
        "e então escreva a análise."
    )
    system = (
        "Você é um coach de poker MTT de elite fazendo um DEEP DIVE de uma decisão. "
        "Você tem ferramentas — use-as antes de afirmar números: get_gto_solution (estratégia/EV "
        "reais do solver para esta mão), get_full_hand (todos os streets desta mão), "
        "get_my_history_here (se o erro se repete). Não estime o que o solver pode te dizer.\n\n"
        + _DEEPDIVE_FORMAT +
        f"\n\nPortuguês do Brasil, tom técnico e direto. {_POKER_TERMS_EN} "
        "Nunca mencione 'GTO Wizard' — use sempre 'GTO Solver'."
    )

    messages: list[dict] = [{'role': 'user', 'content': desc}]
    for _ in range(max_iterations):
        data = _call_llm_api_full({
            'model':      'claude-haiku-4-5-20251001',
            'max_tokens': 1600,
            'system':     system,
            'messages':   messages,
            'tools':      _DEEPDIVE_TOOLS,
        })
        content = data.get('content', [])
        messages.append({'role': 'assistant', 'content': content})
        if data.get('stop_reason') != 'tool_use':
            return ''.join(b['text'] for b in content if b.get('type') == 'text').strip()
        tool_results = []
        for b in content:
            if b.get('type') != 'tool_use':
                continue
            try:
                result_str = _run_deepdive_tool(b.get('name', ''), decision, user_id)
            except Exception as e:
                result_str = json.dumps({'error': str(e)})
            tool_results.append({
                'type':        'tool_result',
                'tool_use_id': b.get('id'),
                'content':     result_str,
            })
        messages.append({'role': 'user', 'content': tool_results})

    # Esgotou iterações — força resposta final sem ferramentas.
    return _call_llm_api({
        'model':      'claude-haiku-4-5-20251001',
        'max_tokens': 1600,
        'system':     system,
        'messages':   messages + [{'role': 'user',
                                   'content': 'Escreva a análise agora, sem mais ferramentas.'}],
    })


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
7. Nunca mencione "GTO Wizard", use sempre "GTO Solver"
8. """ + _POKER_TERMS_EN

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

