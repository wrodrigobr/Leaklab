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
6. Português do Brasil, tom técnico e direto"""

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
        "de 3 a 4 parágrafos curtos. "
        "Tom: direto, técnico mas acessível — como um coach falando com o aluno após a sessão. "
        "Cubra: visão geral da qualidade das decisões, o principal leak identificado, "
        "como o jogador se comportou sob pressão de ICM, e um conselho de foco para a próxima sessão. "
        "NÃO use bullet points. Escreva em prosa fluida. "
        "Retorne APENAS o texto do resumo, sem título ou formatação extra."
    )

    user_msg = "Jogador: " + hero + "\nMetricas:\n" + json.dumps(ctx, ensure_ascii=False, indent=2)

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


def generate_study_plan(leaks: list, evolution: list, icm: dict,
                        hero: str = 'Jogador',
                        user_id: int | None = None) -> dict:
    """
    Gera plano de estudos personalizado baseado nos leaks reais do jogador.
    Retorna dict com cards[], resumo, e nível identificado.
    Cache persistente no banco PostgreSQL via llm_cache.
    """
    import hashlib, json, os, requests

    # --- Construir fingerprint para cache ---
    cache_key = 'study_plan_v2:' + hashlib.md5(
        json.dumps({'leaks': leaks, 'evo_len': len(evolution)},
                   sort_keys=True).encode()
    ).hexdigest()

    # Cache em memória (sessão)
    if cache_key in _cache:
        return json.loads(_cache[cache_key])

    # Cache persistente no banco
    if user_id is not None:
        try:
            from database.repositories import get_llm_cache
            cached = get_llm_cache(user_id, cache_key)
            if cached:
                _cache[cache_key] = cached
                return json.loads(cached)
        except Exception:
            pass

    # --- Calcular métricas gerais ---
    total_dec  = sum(e.get('decisions_count', 0) for e in evolution) or 1
    avg_score  = sum(e.get('avg_score', 0) * e.get('decisions_count', 0)
                     for e in evolution) / total_dec
    avg_std    = sum(e.get('standard_pct', 0) * e.get('decisions_count', 0)
                     for e in evolution) / total_dec
    avg_clear  = sum(e.get('clear_pct', 0) * e.get('decisions_count', 0)
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
- Score médio de erro: {{avg_score:.4f}} (meta: abaixo de 0.08)
- Taxa de decisões corretas (standard): {{avg_std:.1f}}% (meta: acima de 80%)
- Taxa de erros graves (clear mistakes): {{avg_clear:.1f}}% (meta: abaixo de 5%)
- Pior fase ICM: pressão {{icm_weak}}

**Leaks identificados (por frequência de erro):**
{{leaks_txt}}

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
        _cache[cache_key] = result_str
        # Persistir no banco
        if user_id is not None:
            try:
                from database.repositories import set_llm_cache
                set_llm_cache(user_id, cache_key, result_str)
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

