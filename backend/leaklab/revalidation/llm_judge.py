"""
llm_judge.py — Claude Haiku como tiebreaker independente.

Quando ativado (--with-llm-judge), itera sobre os top-N findings disputados
(major_mismatch e no_oracle_data) e pede a Claude um veredicto independente.
Não modifica a categoria do finding — apenas anota llm_verdict + llm_reasoning.

Cache: chave SHA256 do (street, position, action_taken, engine_best,
oracle_action, board, hero_cards). Reusa a tabela `llm_cache` (user_id=0
reservado para uso da revalidação).
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import re
from typing import Optional

log = logging.getLogger(__name__)

_LLM_USER_ID = 0   # user_id reservado para cache da revalidação
_MODEL = 'claude-haiku-4-5-20251001'
_MAX_TOKENS = 600
_VALID_VERDICTS = {'engine_correct', 'oracle_correct', 'both_acceptable', 'neither'}


def judge_findings(findings: list[dict], budget: int = 50) -> int:
    """
    Roda LLM judge nos top-`budget` findings disputados.
    Modifica `findings` in-place adicionando `llm_verdict` e `llm_reasoning`.
    Retorna número de chamadas LLM realmente feitas (cache hits não contam).
    """
    if budget <= 0 or not findings:
        return 0

    disputed = [f for f in findings
                if f.get('category') in ('major_mismatch', 'no_oracle_data')]
    disputed.sort(key=lambda f: f.get('severity_score') or 0.0, reverse=True)
    targets = disputed[:budget]

    calls_made = 0
    for f in targets:
        try:
            res = judge_spot(f)
        except Exception as exc:
            log.warning('llm_judge: falha em finding tid=%s hand=%s: %s',
                        f.get('tournament_db_id'), f.get('hand_id'), exc)
            continue
        f['llm_verdict']   = res.get('verdict')
        f['llm_reasoning'] = res.get('reasoning')
        if not res.get('cached'):
            calls_made += 1
    return calls_made


def judge_spot(finding: dict) -> dict:
    """
    Pede ao Claude que escolha entre engine_correct, oracle_correct,
    both_acceptable, neither — para um único finding.

    Retorna {'verdict': str, 'reasoning': str, 'cached': bool}.

    Lança RuntimeError quando ANTHROPIC_API_KEY ausente e não há cache.
    """
    cache_key = _cache_key(finding)
    cached = _cache_get(cache_key)
    if cached:
        parsed = _parse_response(cached)
        parsed['cached'] = True
        return parsed

    payload = _build_payload(finding)
    raw = _call_api(payload)
    parsed = _parse_response(raw)
    parsed['cached'] = False
    try:
        _cache_set(cache_key, raw)
    except Exception as e:
        log.debug('llm_judge cache set falhou: %s', e)
    return parsed


# ── Payload / parse ──────────────────────────────────────────────────────────

_SYSTEM_PROMPT = (
    "Você é um juiz de poker MTT. Recebe um spot com a recomendação de duas "
    "fontes (engine heurístico e oráculo GTO/heurística independente) e julga "
    "qual é a ação correta. Responda APENAS um JSON estrito no formato:\n"
    "{\"verdict\": \"engine_correct|oracle_correct|both_acceptable|neither\", "
    "\"reasoning\": \"2-3 frases\"}\n"
    "Sem texto fora do JSON."
)


def _build_payload(f: dict) -> dict:
    spot_text = _format_spot(f)
    return {
        'model':      _MODEL,
        'max_tokens': _MAX_TOKENS,
        'system':     _SYSTEM_PROMPT,
        'messages': [{
            'role': 'user',
            'content': (
                f"{spot_text}\n\n"
                f"engine recomenda: {f.get('engine_best')}\n"
                f"oracle recomenda: {f.get('oracle_action')}\n"
                f"ação tomada pelo herói: {f.get('action_taken')}\n"
                f"categoria atual: {f.get('category')} "
                f"(severity={f.get('severity_score')})\n\n"
                "Decida quem está certo e responda no JSON especificado."
            ),
        }],
    }


def _format_spot(f: dict) -> str:
    parts = [
        f"street={f.get('street')}",
        f"position={f.get('position')}",
    ]
    if f.get('opp_cost_bb') is not None:
        parts.append(f"opp_cost={f['opp_cost_bb']:.2f}bb")
    if f.get('gto_action'):
        parts.append(f"gto_action={f['gto_action']}")
    if f.get('oracle_source'):
        parts.append(f"oracle_source={f['oracle_source']}")
    return ' | '.join(parts)


def _parse_response(raw: str) -> dict:
    """
    Extrai {verdict, reasoning} do JSON. Tolerante a texto extra antes/depois.
    """
    if not raw:
        return {'verdict': 'neither', 'reasoning': '(resposta vazia)'}

    # Acha o primeiro { ... } no texto
    m = re.search(r'\{.*?\}', raw, re.DOTALL)
    if not m:
        return {'verdict': 'neither', 'reasoning': raw.strip()[:200]}
    try:
        parsed = json.loads(m.group(0))
    except json.JSONDecodeError:
        return {'verdict': 'neither', 'reasoning': raw.strip()[:200]}

    verdict = (parsed.get('verdict') or '').strip()
    if verdict not in _VALID_VERDICTS:
        verdict = 'neither'
    reasoning = (parsed.get('reasoning') or '').strip()[:500]
    return {'verdict': verdict, 'reasoning': reasoning}


# ── HTTP + cache ─────────────────────────────────────────────────────────────

def _call_api(payload: dict) -> str:
    import requests as _req
    key = os.environ.get('ANTHROPIC_API_KEY', '')
    if not key:
        raise RuntimeError('ANTHROPIC_API_KEY não configurada — llm_judge indisponível.')
    resp = _req.post(
        'https://api.anthropic.com/v1/messages',
        json=payload,
        headers={
            'Content-Type':      'application/json',
            'anthropic-version': '2023-06-01',
            'x-api-key':         key,
        },
        timeout=60,
    )
    resp.raise_for_status()
    data = resp.json()
    return ''.join(
        block['text'] for block in data.get('content', [])
        if block.get('type') == 'text'
    ).strip()


def _cache_key(f: dict) -> str:
    canon = {
        'street':        f.get('street'),
        'position':      f.get('position'),
        'action_taken':  f.get('action_taken'),
        'engine_best':   f.get('engine_best'),
        'oracle_action': f.get('oracle_action'),
        'gto_action':    f.get('gto_action'),
    }
    digest = hashlib.sha256(json.dumps(canon, sort_keys=True).encode()).hexdigest()[:16]
    return f'reval_judge:{digest}'


def _cache_get(key: str) -> Optional[str]:
    try:
        from database.schema import get_conn
        conn = get_conn()
        try:
            row = conn.execute(
                "SELECT response FROM revalidation_llm_cache WHERE cache_key = ?",
                (key,),
            ).fetchone()
            if not row:
                return None
            d = dict(row)
            return d.get('response')
        finally:
            conn.close()
    except Exception:
        return None


def _cache_set(key: str, value: str) -> None:
    from database.schema import USE_POSTGRES, get_conn
    conn = get_conn()
    try:
        if USE_POSTGRES:
            conn.execute(
                "INSERT INTO revalidation_llm_cache (cache_key, response) VALUES (?, ?) "
                "ON CONFLICT (cache_key) DO UPDATE SET response = excluded.response",
                (key, value),
            )
        else:
            conn.execute(
                "INSERT OR REPLACE INTO revalidation_llm_cache (cache_key, response) "
                "VALUES (?, ?)",
                (key, value),
            )
        conn.commit()
    finally:
        conn.close()
