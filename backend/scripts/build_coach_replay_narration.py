"""
build_coach_replay_narration.py — Script Generator do Coach Replay (grounded).

Gera a narração por cena a partir do ReplaySpec REAL. Pipeline:
  1. rascunho DETERMINÍSTICO (só os fatos do spec, nunca inventa número)
  2. (opcional) LLM Haiku poliria a prosa pra soar como coach
  3. VALIDADOR anti-invenção: se a versão do LLM citar qualquer número que não está nos
     fatos, é REJEITADA e cai no rascunho determinístico.

Saída: ../video/src/data/coach_replay_narration.json (scene_id -> texto)
"""
import os, sys, json, re

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

_SPEC = os.path.join(os.path.dirname(__file__), '..', '..', 'video', 'src', 'data', 'coach_replay_spec.json')
_OUT = os.path.join(os.path.dirname(__file__), '..', '..', 'video', 'src', 'data', 'coach_replay_narration.json')

_ACT_PT = {'fold': 'fold', 'call': 'call', 'raise': 'raise', 'check': 'check', 'jam': 'shove', 'allin': 'shove'}


def _nums(text: str) -> set:
    """Todos os números citados num texto (pra validar contra os fatos)."""
    return set(re.findall(r'\d+(?:[.,]\d+)?', text or ''))


def _allowed_numbers(spec: dict) -> set:
    """Números LEGÍTIMos (dos fatos): mãos, ocorrências, EV, cards implícitos, semanas."""
    ok = set()
    ok.add(str(spec['intro']['hands_analyzed']))
    ok.add(str(spec['intro']['leaks_found']))
    for l in spec['leaks']:
        ok |= _nums(str(l.get('occurrences'))) | _nums(str(l.get('ev_lost_bb')))
        for e in l['examples']:
            ok |= _nums(str(e.get('ev_loss_bb'))) | _nums(str(e.get('hero_cards')))
    for p in spec['plan']:
        ok.add(str(p['week']))
    return ok


def _det_intro(spec: dict) -> str:
    t = spec['tournament']
    return (f"Olá. Analisamos {spec['intro']['hands_analyzed']} mãos do seu {t['name']} "
            f"e encontramos {spec['intro']['leaks_found']} padrões que estão custando EV. Vamos direto ao ponto.")


def _det_leak(l: dict) -> str:
    ex = l['examples'][0] if l['examples'] else None
    base = (f"Seu leak número {l['rank']}: {l['title']}. "
            f"Foram {l['occurrences']} spots, custando cerca de {abs(l['ev_lost_bb'])} big blinds no torneio.")
    if ex:
        base += (f" Por exemplo, no {ex['position']} o GTO manda "
                 f"{_ACT_PT.get(ex['gto_action'], ex['gto_action'])}.")
    base += " " + l['recommendation']
    return base


def _det_plan(spec: dict) -> str:
    weeks = " ".join(f"Semana {p['week']}, {p['focus']}." for p in spec['plan'])
    return f"Seu plano de estudo: {weeks} Comece agora, treine esses spots no GrindLab."


def _polish(draft: str, allowed: set) -> str:
    """LLM (Haiku) reescreve a prosa. Se citar número fora dos fatos, DESCARTA e mantém o rascunho.
    Sem API key → devolve o rascunho (já correto)."""
    try:
        from leaklab.llm_explainer import _call_llm_api, _POKER_TERMS_EN
    except Exception:
        return draft
    system = (
        "Você é um coach de poker de torneios revisando a sessão do aluno, tom caloroso e direto. "
        "Reescreva o texto pra soar natural, SEM mudar nenhum fato. "
        "NUNCA cite número, carta, posição ou EV que não esteja no texto original. Não invente nada. "
        f"{_POKER_TERMS_EN} Português do Brasil. Devolva só o parágrafo."
    )
    try:
        out = (_call_llm_api({'model': 'claude-haiku-4-5-20251001', 'max_tokens': 400,
                              'system': system, 'messages': [{'role': 'user', 'content': draft}]}) or '').strip()
    except Exception:
        return draft
    if not out:
        return draft
    # VALIDADOR anti-invenção: todo número do LLM tem que existir nos fatos
    if not _nums(out).issubset(allowed):
        return draft   # rejeita a versão do LLM, mantém o determinístico
    return out


def build():
    spec = json.load(open(_SPEC, encoding='utf-8'))
    allowed = _allowed_numbers(spec)
    scenes = {'intro': _det_intro(spec)}
    for i, l in enumerate(spec['leaks']):
        scenes[f'leak{i+1}'] = _det_leak(l)
    scenes['plan'] = _det_plan(spec)
    # polimento (com guard-rail); sem key, mantém o determinístico
    narration = {k: _polish(v, allowed) for k, v in scenes.items()}

    json.dump(narration, open(_OUT, 'w', encoding='utf-8'), ensure_ascii=False, indent=2)
    total_chars = sum(len(v) for v in narration.values())
    print(f"=== Narração Coach Replay ({len(narration)} cenas, ~{round(total_chars/14)}s de fala) ===")
    for k, v in narration.items():
        print(f"\n[{k}] {v}")
    print('\n->', os.path.normpath(_OUT))


if __name__ == '__main__':
    build()
