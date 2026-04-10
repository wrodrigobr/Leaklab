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
    import urllib.request, json as _json
    req = urllib.request.Request(
        'https://api.anthropic.com/v1/messages',
        data=_json.dumps(payload).encode('utf-8'),
        headers={
            'Content-Type':      'application/json',
            'anthropic-version': '2023-06-01',
            'x-api-key':         _api_key(),
        },
        method='POST',
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        data = _json.loads(resp.read())
    return ''.join(
        block['text'] for block in data.get('content', [])
        if block.get('type') == 'text'
    ).strip()


def _call_llm_batch(decisions: List[dict]) -> List[str]:
    """
    Faz uma única chamada ao Haiku com todas as decisões com erro.
    Retorna lista de explicações na mesma ordem.
    """
    import urllib.request

    payload = _build_payload(decisions)
    body    = json.dumps(payload).encode('utf-8')

    req = urllib.request.Request(
        'https://api.anthropic.com/v1/messages',
        data=body,
        headers={
            'Content-Type':      'application/json',
            'anthropic-version': '2023-06-01',
            'x-api-key':         _api_key(),
        },
        method='POST',
    )

    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.loads(resp.read())

    raw_text = ''.join(
        block['text'] for block in data.get('content', [])
        if block.get('type') == 'text'
    )

    return _parse_llm_response(raw_text, len(decisions))


def _build_payload(decisions: List[dict]) -> dict:
    system_prompt = """Você é um coach profissional de poker MTT com mais de 20 anos de experiência.
Analise cada decisão abaixo e retorne APENAS um JSON array com uma análise profunda por decisão.

IMPORTANTE: A decisão ocorreu na street indicada. O "board_na_decisão" mostra apenas as cartas comunitárias DISPONÍVEIS naquele momento (vazio no preflop, 3 cartas no flop, 4 no turn, 5 no river).

Para cada decisão, estruture sua análise com estas seções:

**1. O ERRO**
Explique o que foi feito de errado e por que é errado neste contexto específico.
Se a ação foi fold quando devia call: explique que estava com equity suficiente e pot odds favoráveis.
Se a ação foi call quando devia fold: explique que estava sem equity suficiente para o preço pago.
Se a ação foi call quando devia raise: explique a perda de valor e proteção.
Seja específico com os números.

**2. A MATEMÁTICA**
- Equity estimada da mão: {equity_estimada} ({equity_estimada*100:.0f}%)
- Pot odds exigidas: {pot_odds} ({pot_odds*100:.0f}%) — o que você precisa para breakeven
- Equity mínima ajustada pelo contexto: {equity_minima_req} ({equity_minima_req*100:.0f}%)
- Veredicto matemático: equity {acima/abaixo} do necessário em {diferença} pontos percentuais
- Se houver draw: calcule outs × 2 (turn) ou × 4 (flop) para probabilidade de completar
- EV estimado: compare EV da ação tomada vs ação correta

**3. O CONTEXTO**
- M ratio {m_ratio}: explique o que significa para a estratégia (M<6=push/fold, M6-12=pressão, M>12=jogo normal)
- Stack em BBs ({stack_bb} BB): explique as implicações
- ICM pressure {icm}: se high/medium, explique como afeta os thresholds de call
- Posição ({position}): como afeta a equity realizada e a decisão

**4. A AÇÃO CORRETA**
Explique passo a passo por que {best_action} era a jogada superior, com raciocínio completo.
Inclua: qual o EV esperado, por que o range se beneficia desta linha, qual o objetivo estratégico.

**5. A LIÇÃO**
Uma regra memorável que o aluno pode aplicar em situações similares.
Exemplo: "Com M<6 e stack<15BB, sua decisão deve ser push/fold. Call passivo desperdiça equity de fold."

Tom: direto, técnico, educativo. Use os números concretos fornecidos.
Formato: ["análise decisão 1", "análise decisão 2", ...]
Retorne SOMENTE o JSON array, sem texto adicional, sem markdown."""

    def _board_for_street(street: str, board: list) -> list:
        """Retorna apenas as cartas do board disponíveis na street."""
        if street == 'preflop': return []
        if street == 'flop':    return board[:3]
        if street == 'turn':    return board[:4]
        return board  # river ou unknown

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
        interp = d.get('interpretation', {})

        street    = d.get('street', 'preflop')
        full_board = d.get('board', [])
        board_now  = _board_for_street(street, full_board)

        equity_est = mt.get('estimatedHandEquity') or mt.get('equity') or 0
        pot_odds   = mt.get('potOddsEquity') or mt.get('pot_odds') or 0
        eq_min     = th.get('adjustedRequiredEquity') or pot_odds
        action     = d.get('actionTaken', d.get('action_taken', '?'))
        best       = d.get('bestAction',  d.get('best_action',  '?'))
        m_ratio    = ctx.get('mRatio') or ctx.get('m_ratio')
        stack_bb   = ctx.get('heroStackBb') or ctx.get('stack_bb')
        icm        = ctx.get('icmPressure', ctx.get('icm_pressure', 'low'))
        position   = spot.get('position') or ctx.get('position', 'unknown')

        decisions_data.append({
            'índice':              i,
            'hero_cards':          d.get('hero_cards', '??'),
            'board_na_decisão':    board_now,
            'street':              street,
            'ação_tomada':         action,
            'ação_correta':        best,
            'classificação':       ev.get('label', '?'),
            'score_erro':          round(ev.get('mistakeScore', 0), 3),
            'matemática': {
                'equity_estimada_pct':     round(equity_est * 100, 1),
                'pot_odds_pct':            round(pot_odds  * 100, 1),
                'equity_minima_exigida_pct':round(eq_min   * 100, 1),
                'deficit_equity_pct':      round((eq_min - equity_est) * 100, 1),
                'draw_profile':            mt.get('drawProfile', 'none'),
                'equity_adjustment':       mt.get('equityAdjustment', 0),
                'implied_odds_factor':     mt.get('impliedOddsFactor', 0),
                'rev_implied_odds':        mt.get('reverseImpliedOddsFactor', 0),
            },
            'contexto': {
                'm_ratio':            m_ratio,
                'stack_bb':           stack_bb,
                'icm_pressure':       icm,
                'posição':            position,
                'estágio_torneio':    ctx.get('tournamentStage', ctx.get('stage', '?')),
                'jogadores_na_mesa':  ctx.get('activePlayers', ctx.get('players')),
                'pot_size':           spot.get('potSize'),
                'facing_bet_bb':      spot.get('facingSize'),
            },
            'avaliação_range': {
                'zona_do_range':      rng.get('rangeZone', hp.get('handClass', '?')),
                'ação_recomendada':   rng.get('recommendedPrimaryAction', best),
                'confiança':          rng.get('confidence'),
                'hand_class':         hp.get('handClass'),
                'showdown_value':     hp.get('showdownValueTier'),
                'draw_tier':          hp.get('drawTier'),
            },
            'penalidades_do_score': {
                'gap_base':           round(bd.get('baseActionGap', 0), 3),
                'penalidade_math':    round(bd.get('mathPenalty', 0), 3),
                'penalidade_range':   round(bd.get('rangePenalty', 0), 3),
                'penalidade_contexto':round(bd.get('contextPenalty', 0), 3),
            },
            'resumo_engine': interp.get('summary', ''),
        })

    user_message = (
        "Analise " + str(len(decisions)) + " decisão(ões) com erro no poker MTT:\n\n"
        + json.dumps(decisions_data, ensure_ascii=False, indent=2)
    )

    return {
        'model':      'claude-haiku-4-5-20251001',
        'max_tokens': max(800 * len(decisions), 2000),
        'system':     system_prompt,
        'messages':   [{'role': 'user', 'content': user_message}],
    }


def _parse_llm_response(raw: str, expected: int) -> List[str]:
    """Extrai o JSON array da resposta do LLM."""
    # Limpar possíveis markdown fences
    clean = raw.strip()
    if clean.startswith('```'):
        lines = clean.splitlines()
        clean = '\n'.join(lines[1:-1] if lines[-1] == '```' else lines[1:])

    try:
        result = json.loads(clean)
        if isinstance(result, list):
            # Garantir que temos o número correto de explicações
            while len(result) < expected:
                result.append('Decisão analisada pelo engine.')
            return result[:expected]
    except json.JSONDecodeError:
        pass

    # Fallback: retornar texto bruto dividido por quebras
    parts = [p.strip() for p in raw.split('\n') if p.strip()]
    while len(parts) < expected:
        parts.append('Decisão analisada pelo engine.')
    return parts[:expected]


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
    import urllib.request, json as _json

    system_prompt = (
        "Você é um coach de poker MTT. "
        "Analise as métricas do torneio abaixo e escreva um resumo em português "
        "de 3 a 4 parágrafos curtos. "
        "Tom: direto, técnico mas acessível — como um coach falando com o aluno após a sessão. "
        "Cubra: visão geral da qualidade das decisões, o principal leak identificado, "
        "como o jogador se comportou sob pressão de ICM, e um conselho de foco para a próxima sessão. "
        "NÃO use bullet points. Escreva em prosa fluida. "
        "Retorne APENAS o texto do resumo, sem título ou formatação extra."
    )

    user_msg = "Jogador: " + hero + "\nMetricas:\n" + _json.dumps(ctx, ensure_ascii=False, indent=2)

    payload = {
        'model':      'claude-haiku-4-5-20251001',
        'max_tokens': 400,
        'system':     system_prompt,
        'messages':   [{'role': 'user', 'content': user_msg}],
    }

    req = urllib.request.Request(
        'https://api.anthropic.com/v1/messages',
        data=_json.dumps(payload).encode('utf-8'),
        headers={
            'Content-Type':      'application/json',
            'anthropic-version': '2023-06-01',
            'x-api-key':         _api_key(),
        },
        method='POST',
    )

    with urllib.request.urlopen(req, timeout=30) as resp:
        data = _json.loads(resp.read())

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
