"""
build_short_spot.py — escolhe o spot mais DESAFIADOR (vetado, gabarito dominante) pra virar
um Short vertical do Desafio do Dia. Dados reais (mesmo filtro do #42), zero invenção.

Saída: ../video/src/data/short_spot.json
"""
import os, sys, json, random

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from leaklab.daily_challenge import build_candidates, describe_challenge, grade_challenge   # noqa: E402


def build(n: int = 100):
    cands = build_candidates(n, rng=random.Random(7), with_explanation=False)
    # gancho ideal do Short = FOLD de uma mão que parece forte (a maior surpresa),
    # depois qualquer contraintuitivo, depois maior score. Prioriza o "você jogaria, mas o GTO larga".
    def rank(c):
        ctx = describe_challenge(c['spot_json'])
        fold_strong = 1 if (ctx['counterintuitive'] and c['answer'] == 'fold') else 0
        return (fold_strong, ctx['challenge_score']), ctx
    scored = [(rank(c)[0], c, rank(c)[1]) for c in cands]
    scored.sort(key=lambda x: x[0], reverse=True)
    _key, best, best_ctx = scored[0]
    spot = json.loads(best['spot_json'])
    g = grade_challenge(best['spot_json'], best['answer'])   # veredito do gabarito (explicação)
    out = {
        'scenario': spot['scenario'], 'position': spot['position'],
        'vs_position': spot.get('vs_position') or '', 'stack_bb': spot['stack_bb'],
        'hand': spot['hand'], 'hero_cards': spot['hero_cards'],
        'options': spot['options'], 'answer': best['answer'],
        'hand_class': best_ctx['hand_class'], 'counterintuitive': best_ctx['counterintuitive'],
        'challenge_score': best_ctx['challenge_score'],
        'gto_strategy': best_ctx['gto_strategy'], 'best_action': best_ctx['best_action'],
        'why': best_ctx['why'], 'explanation': g['explanation'],
    }
    path = os.path.join(os.path.dirname(__file__), '..', '..', 'video', 'src', 'data', 'short_spot.json')
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print(f"score {out['challenge_score']} | {out['position']} {out['hand']} {out['stack_bb']}bb "
          f"vs {out['vs_position'] or '-'} -> GTO {out['answer']}")
    print('why:', out['why'])
    print('->', os.path.normpath(path))


if __name__ == '__main__':
    build()
