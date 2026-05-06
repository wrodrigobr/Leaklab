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

Para cada decisão use EXATAMENTE este formato Markdown:

---
## [número]. [Street] — [ação tomada] era errado, o correto era [ação correta]

### ❌ O Erro
Explique em 3-4 frases o que foi feito de errado e por que é um erro estratégico neste contexto específico.

### 📐 A Matemática
- **Equity estimada:** X% (o que sua mão vale contra o range do oponente)
- **Pot odds exigidas:** Y% (equity mínima para breakeven)
- **Equity ajustada pelo contexto:** Z% (após ICM, posição e implied odds)
- **Déficit/Superávit:** ±N pontos percentuais — [call/raise/fold] era [correto/incorreto]
- **EV estimado:** ação tomada ≈ -X BB | ação correta ≈ +Y BB por 100 mãos

### 🧭 O Contexto
- **M Ratio [valor]:** [o que significa — M<6=push/fold puro, M6-12=zona de pressão, M>12=jogo normal]
- **Stack ([valor] BB):** [implicação prática para este spot]
- **ICM [nível]:** [como afeta os thresholds de call/fold/raise nesta situação]
- **Posição ([posição]):** [como IP/OOP afeta equity realizada e linha correta]

### ✅ A Ação Correta
**[AÇÃO]** — [explicação completa em 4-5 frases: por que é superior matematicamente, qual o objetivo estratégico, o que acontece contra os diferentes ranges do oponente]

### 💡 A Lição
[Uma regra prática memorável. Use **negrito** para o conceito-chave.]

---

REGRAS OBRIGATÓRIAS:
1. Escreva SOMENTE texto Markdown — zero JSON, zero chaves, zero colchetes
2. Use os números exatos dos dados fornecidos
3. Para preflop sem board: não mencione cartas comunitárias
4. Separe cada decisão com ---
5. Seja específico: "33% de equity vs 54% exigidos = -21pp" não "equity insuficiente"
6. Português do Brasil, tom técnico e direto
7. Termos de poker SEMPRE em inglês: fold, call, raise, bet, check, jam, preflop, flop, turn, river, hand, spot, equity, ICM, M-ratio, stack, pot odds, range, 3-bet, c-bet, board, position, IP, OOP"""

    decisions_data = []
    for i, d in enumerate(decisions):
        ev   = d.get('evaluation', {})
        bd   = ev.get('scoreBreakdown', {})
        ctx  = d.get('context', {})
        mt   = d.get('math', {})
        th   = d.get('thresholds', {})
        spot = d.get('spot', {})
        hp   = d.get('hand_profile', {})
        rng  = d.get('range_evaluation', {})

        street     = d.get('street', 'preflop')
        full_board = d.get('board', [])
        board_now  = _board_for_street(street, full_board)
        hero_cards = d.get('hero_cards', '??')
        action     = d.get('actionTaken', d.get('action_taken', '?'))
        best       = d.get('bestAction',  d.get('best_action',  '?'))
        eq_est     = round((mt.get('estimatedHandEquity') or 0) * 100, 1)
        pot_odds   = round((mt.get('potOddsEquity') or 0) * 100, 1)
        eq_min     = round((th.get('adjustedRequiredEquity') or mt.get('potOddsEquity') or 0) * 100, 1)
        deficit    = round(eq_min - eq_est, 1)
        m_ratio    = ctx.get('mRatio') or ctx.get('m_ratio', '?')
        stack_bb   = ctx.get('heroStackBb') or ctx.get('stack_bb', '?')
        icm        = ctx.get('icmPressure', ctx.get('icm_pressure', 'low'))
        position   = spot.get('position') or ctx.get('position', '?')
        hand_class = hp.get('handClass', '?')
        range_zone = rng.get('rangeZone', '?')
        rev_impl   = round((mt.get('reverseImpliedOddsFactor') or 0) * 100, 1)
        draw       = mt.get('drawProfile', 'none')

        cards_fmt  = _fmt_cards([hero_cards[:2], hero_cards[2:]]) if len(hero_cards) >= 4 else hero_cards
        board_fmt  = _fmt_cards(board_now) if board_now else '(preflop — sem board)'

        decisions_data.append(
            f"DECISÃO {i+1} de {len(decisions)}:\n"
            f"Cartas: {cards_fmt} | Board no momento: {board_fmt}\n"
            f"Street: {street} | Tomou: {action} | Correto: {best}\n"
            f"Label: {ev.get('label','?')} | Score: {ev.get('mistakeScore',0):.3f}\n"
            f"Equity estimada: {eq_est}% | Pot odds exigidas: {pot_odds}% | "
            f"Equity mínima ajustada: {eq_min}% | Déficit: {deficit:+.1f}pp\n"
            f"Draw: {draw} | Reverse implied odds: {rev_impl}%\n"
            f"M ratio: {m_ratio} | Stack: {stack_bb} BB | ICM: {icm} | Posição: {position}\n"
            f"Classe da mão: {hand_class} | Zona do range: {range_zone}\n"
            f"Penalidades — gap_base: {bd.get('baseActionGap',0):.3f} | "
            f"math: {bd.get('mathPenalty',0):.3f} | "
            f"range: {bd.get('rangePenalty',0):.3f} | "
            f"contexto: {bd.get('contextPenalty',0):.3f}"
        )

    user_message = (
        "Analise estas " + str(len(decisions)) + " decisão(ões) com erro no poker MTT:\n\n"
        + "\n\n".join(decisions_data)
        + "\n\nEscreva a análise completa em Markdown seguindo o formato especificado. "
        + "Lembre: APENAS texto Markdown, NUNCA JSON."
    )

    return {
        'model':      'claude-haiku-4-5-20251001',
        'max_tokens': max(900 * len(decisions), 2500),
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
            'bet': 'bet', 'raise': 'raise', 'jam': 'all-in'}.get(action, action)


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
        "Termos técnicos de poker SEMPRE em inglês: fold, call, raise, bet, check, jam, preflop, flop, turn, river, hand, spot, equity, ICM, M-ratio, stack, pot odds, range, 3-bet, c-bet, board, position. "
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
        'max_tokens': 130,
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


def generate_study_plan(leaks: list, evolution: list, icm: dict,
                        hero: str = 'Jogador',
                        user_id: int | None = None,
                        force_new: bool = False) -> dict:
    """
    Gera plano de estudos personalizado baseado nos leaks reais do jogador.
    Retorna dict com cards[], resumo, e nível identificado.
    Cache persistente no banco via llm_cache com chave estável por aluno.
    """
    import hashlib, json, os, requests

    # Chave em memória (por snapshot de dados — evita regerar na mesma sessão)
    mem_key = 'study_plan_v2:' + hashlib.md5(
        json.dumps({'leaks': leaks, 'evo_len': len(evolution)},
                   sort_keys=True).encode()
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

    prompt = f"""Você é um coach profissional de poker MTT com mais de 15 anos de experiência, especialista em identificar e corrigir leaks em torneios.
Analise os dados de performance abaixo e gere um plano de estudos DETALHADO e PERSONALIZADO.

## Dados do Jogador ({hero})

**Métricas gerais ({n_torneioa} torneios analisados):**
- Score médio de erro: {avg_score:.4f} (meta: abaixo de 0.08)
- Standard% (decisões corretas): {avg_std:.1f}% (meta: acima de 80%)
- Erros claros: {avg_clear:.1f}% (meta: abaixo de 5%)
- Pior fase ICM: pressão {icm_weak}

**Leaks identificados (por frequência de erro):**
{leaks_txt}

## Instrução de Coach

Gere um plano de estudos com exatamente 6 itens, do leak mais crítico ao menos crítico.
Cada item deve ser um módulo de estudo completo com:

1. Título direto e específico ao leak (máx 6 palavras)
2. Diagnóstico: 2-3 frases explicando a RAIZ do problema e seu impacto real em EV/fichas
3. Conceitos-chave: lista de 2-4 conceitos teóricos que o jogador PRECISA dominar para corrigir este leak
4. Recursos de estudo:
   - 1-2 livros ou capítulos específicos (ex: "The Mental Game of Poker cap. 3", "Applications of No-Limit Hold'em cap. 7")
   - 1-2 tipos de vídeos/canais (ex: "solver study sessions no GTO Wizard", "hand history reviews de spots de 3bet")
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
                'max_tokens': 3500,
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

        result = json.loads(raw)
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
        # Fallback: retornar estrutura vazia com erro
        return {
            'nivel': 'intermediario',
            'resumo': 'Análise indisponível no momento.',
            'cards': [],
            'error': str(e),
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
    cache_key = "causal_v2_" + lang + "_" + "_".join(
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
    "fold, call, raise, bet, check, jam, preflop, flop, turn, river, "
    "hand, spot, equity, ICM, M-ratio, stack, pot odds, range, 3-bet, c-bet, "
    "board, position, IP, OOP, shove, reshove, open, limp, squeeze."
)

_LANG_INSTRUCTIONS = {
    'pt-BR': f"Responda APENAS em português do Brasil. {_POKER_TERMS_EN}",
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
        f"career_{lang}_{projection.get('current_level_slug','?')}_"
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
                    f"{nm['threshold']}%) is ~{nm['months_needed']} months away "
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
        "Be direct and specific. No headers or bullets."
    )
    user_content = (
        f"Current level: {projection['current_level']} ({projection['current_avg']:.1f}% standard). "
        f"Trend: {projection['slope_per_tournament']:+.3f}% per tournament over "
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
            f"Sua trajetória atual mostra melhora consistente de {slope:+.2f}% por torneio. "
            f"Mantendo esse ritmo, você alcançará o nível {nm['level_name']} "
            f"({nm['threshold']}%) em aproximadamente {nm['months_needed']} meses. "
            f"O principal obstáculo é o leak em {top} — corrigi-lo acelera diretamente essa projeção."
        )
    elif slope <= 0:
        return (
            f"Seu Standard% está estagnado ou em queda nos últimos torneios. "
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
    'pt-BR': "Responda APENAS em português do Brasil.",
    'en':    "Respond ONLY in English.",
    'es':    "Responde ÚNICAMENTE en español.",
}

_PATTERN_NAMES_EN = {
    "revenge_aggression": "Revenge Aggression",
    "fear_folding":       "Fear Folding",
    "sunk_cost":          "Sunk Cost Continuation",
    "entitlement_tilt":   "Entitlement Tilt",
    "compensation_call":  "Compensation Call",
}


def generate_cognitive_narrative(patterns: list, lang: str = 'pt-BR') -> str:
    """2-3 sentences on the dominant cognitive pattern, its EV cost, and one corrective habit."""
    if not patterns:
        return ""
    cache_key = (
        f"cog_{lang}_"
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
    pattern_str = "; ".join(
        f"{_PATTERN_NAMES_EN.get(p['type'], p['type'])} ({p['frequency']*100:.0f}% frequency, {p['severity']} severity)"
        for p in patterns[:3]
    )
    system = (
        f"You are a concise MTT poker coach specialising in mental game. {lang_instr} "
        "Write EXACTLY 2-3 sentences: (1) name the most damaging cognitive pattern and its trigger, "
        "(2) explain briefly why it costs EV, "
        "(3) give one concrete corrective habit the player can apply immediately. "
        "Be direct and specific. No headers or bullets."
    )
    user_content = (
        f"Detected cognitive failure patterns: {pattern_str}. "
        f"Most frequent: {patterns[0]['type']} at {patterns[0]['frequency']*100:.0f}% of opportunities."
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


def _template_cognitive(patterns: list, lang: str = 'pt-BR') -> str:
    top  = patterns[0]
    freq = int(top['frequency'] * 100)
    names_pt = {
        "revenge_aggression": "Agressividade Reativa",
        "fear_folding":       "Fold por Medo",
        "sunk_cost":          "Custo Afundado",
        "entitlement_tilt":   "Tilt por Relaxamento",
        "compensation_call":  "Call Compensatório",
    }
    names_es = {
        "revenge_aggression": "Agresividad Reactiva",
        "fear_folding":       "Fold por Miedo",
        "sunk_cost":          "Costo Hundido",
        "entitlement_tilt":   "Tilt por Complacencia",
        "compensation_call":  "Call de Compensación",
    }
    if lang == 'en':
        pname = _PATTERN_NAMES_EN.get(top['type'], top['type'])
        return (
            f"Your most frequent cognitive pattern is {pname} ({freq}% of opportunities). "
            f"This breaks decision discipline at the moments of highest strategic cost. "
            f"Take a deliberate 30-second pause after triggering events before acting on your next hand."
        )
    if lang == 'es':
        pname = names_es.get(top['type'], top['type'])
        return (
            f"Tu patrón cognitivo más frecuente es {pname} ({freq}% de las oportunidades). "
            f"Esto rompe la disciplina decisional en los momentos de mayor coste estratégico. "
            f"Haz una pausa consciente de 30 segundos tras los eventos desencadenantes antes de actuar."
        )
    pname = names_pt.get(top['type'], top['type'])
    return (
        f"Seu padrão cognitivo mais frequente é {pname} ({freq}% das oportunidades). "
        f"Isso quebra a disciplina decisional nos momentos de maior custo estratégico. "
        f"Faça uma pausa consciente de 30 segundos após eventos gatilho antes de agir na próxima mão."
    )


# ── Strategic Twin Narrative (Sprint AR) ─────────────────────────────────────

_LANG_TWIN = {
    'pt-BR': "Responda APENAS em português do Brasil.",
    'en':    "Respond ONLY in English.",
    'es':    "Responde ÚNICAMENTE en español.",
}

_ACTION_LABEL_EN = {
    "jam":   "jam/all-in",
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
        f"You are a concise MTT poker coach writing a personal strategic profile. {lang_instr} "
        "Write EXACTLY 2-3 sentences in the FIRST PERSON ('In situations where...', 'My most costly spot...'): "
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
    action_pt = {"jam": "reshove", "fold": "fold", "call": "call", "raise": "raise", "bet": "bet", "check": "check"}
    action_es = {"jam": "reshove", "fold": "fold", "call": "call", "raise": "raise", "bet": "bet", "check": "check"}
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
                     hero: str = 'Jogador') -> str:
    """Responde pergunta do usuário com contexto real de desempenho."""
    import requests as _req

    ctx_parts: list[str] = []

    if leaks:
        leaks_txt = '\n'.join(
            f"  - {l['spot']}: {l['n']} ocorrências, score médio {l['avg_score']:.3f} "
            f"({'crítico' if l['avg_score'] >= .36 else 'moderado' if l['avg_score'] >= .20 else 'leve'})"
            for l in leaks[:5]
        )
        ctx_parts.append(f"Top leaks detectados:\n{leaks_txt}")

    if evolution:
        recent = evolution[-5:]
        ev_txt = '\n'.join(
            f"  - {e.get('tournament_id','?')}: "
            f"score médio={e.get('avg_score',0):.3f}, "
            f"Standard%={e.get('standard_pct',0)*100:.0f}%"
            for e in recent
        )
        ctx_parts.append(f"Últimos {len(recent)} torneios:\n{ev_txt}")

    context = '\n\n'.join(ctx_parts) if ctx_parts else 'Nenhum dado de desempenho disponível ainda.'

    system = (
        f"Você é o Coach IA do PokerLeaks, assistente tático de poker MTT de elite. "
        f"Seu aluno é {hero}.\n\n"
        f"Dados reais de desempenho atual:\n{context}\n\n"
        "Use esses dados para personalizar cada resposta. Seja direto e técnico. "
        f"Português do Brasil. {_POKER_TERMS_EN} Máximo 300 palavras."
    )

    safe_message = sanitize_llm_input(message, max_len=1000)
    payload = {
        'model':      'claude-haiku-4-5-20251001',
        'max_tokens': 600,
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
    level_sb, level_bb, level_num, note.
    """
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

    try:
        import json as _json
        board_list = _json.loads(board_raw) if isinstance(board_raw, str) else board_raw
        board_str  = ' '.join(board_list) if board_list else '—'
    except Exception:
        board_str = '—'

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
6. Termos de poker SEMPRE em inglês: fold, call, raise, bet, check, jam, preflop, flop, turn, river, hand, spot, equity, ICM, M-ratio, stack, pot odds, range, 3-bet, c-bet, board, position, IP, OOP"""

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

