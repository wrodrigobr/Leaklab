"""
build_challenge_posts.py — cura N spots pro POST do Desafio do Dia (Instagram) e escreve
os JSONs na fila do projeto de vídeo (video/src/data/challenge_queue/).

Reusa o pipeline de certeza do Desafio do Dia do sistema (gabarito confiável), mas filtra
pra CONTEÚDO: só spots ENGAJANTES (contraintuitivos ou com mistura real) e DESCARTA os
suspeitos (ex.: foldar par forte / AQ+ vs 3-bet, que pode ser range nitty demais e viraria
"seu solver tá errado" nos comentários). Diverso por cenário/posição.

Uso:
    python scripts/build_challenge_posts.py --n 5
    python scripts/build_challenge_posts.py --n 5 --seed 42     # reproduzível
Depois, renderiza tudo:
    cd video && npm run posts
Ou o comando único (raiz do repo):  ./make-daily-posts.sh 5
"""
from __future__ import annotations
import argparse
import json
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))   # backend/ no path (roda de qualquer cwd)

from leaklab.daily_challenge import build_candidates, describe_challenge, explain_challenge

_OPTS = {'rfi': ['fold', 'raise'], 'vs_rfi': ['fold', 'call', 'raise'], 'vs_3bet': ['fold', 'call', 'raise']}
_ORDER = '23456789TJQKA'
_QUEUE = Path(__file__).resolve().parents[2] / 'video' / 'src' / 'data' / 'challenge_queue'


def _second_freq(ctx: dict) -> float:
    strat = ctx.get('gto_strategy') or []
    return float(strat[1]['freq']) if len(strat) > 1 else 0.0


def _suspicious(sp: dict, answer: str) -> bool:
    """Descarta gabaritos que parecem errados demais pra servir num post (mão forte foldando
    vs 3-bet). Melhor perder um spot do que servir um gabarito questionável em público."""
    if sp['scenario'] == 'vs_3bet' and answer == 'fold':
        hand = sp['hand']
        if len(hand) >= 2 and hand[0] == hand[1]:                 # par
            if _ORDER.index(hand[0]) >= _ORDER.index('8'):        # 88+ foldar vs 3bet = suspeito
                return True
        if hand in ('AQo', 'AQs', 'AJs', 'ATs', 'KQs', 'AKo', 'AKs'):
            return True
    return False


def curate(n: int, rng: random.Random) -> list[dict]:
    """Acumula candidatos certos de várias sementes, filtra por engajamento e confiança,
    e escolhe N diversos (cap 2/cenário, sem repetir posição no mesmo cenário)."""
    pool: dict = {}
    for k in range(60):
        sub = random.Random(rng.randint(0, 10**9))
        for c in build_candidates(30, rng=sub):
            sp = json.loads(c['spot_json'])
            sig = (sp['scenario'], sp['position'], str(sp.get('vs_position') or ''), sp['stack_bb'], sp['hand'])
            if sig in pool:
                continue
            ctx = describe_challenge(sp)
            c['_sp'] = sp; c['_ctx'] = ctx; c['_2f'] = _second_freq(ctx)
            pool[sig] = c
        if len(pool) > 400:
            break
    # engajante + confiável
    cands = [c for c in pool.values()
             if (c['_ctx'].get('counterintuitive') or c['_2f'] >= 0.10)
             and not _suspicious(c['_sp'], c['answer'])]
    # mistos primeiro (mais ricos de explicar), depois contraintuitivos puros
    cands.sort(key=lambda c: (c['_2f'], c['_ctx'].get('challenge_score', 0)), reverse=True)
    chosen, scc, seen = [], {}, set()
    for c in cands:
        sp = c['_sp']; scn = sp['scenario']; pos = sp['position']
        if scc.get(scn, 0) >= 2 or (scn, pos) in seen:
            continue
        chosen.append(c); scc[scn] = scc.get(scn, 0) + 1; seen.add((scn, pos))
        if len(chosen) >= n:
            break
    return chosen


def to_doc(c: dict) -> dict:
    sp, ctx = c['_sp'], c['_ctx']
    return {
        'scenario': sp['scenario'], 'position': sp['position'], 'vs_position': sp.get('vs_position', ''),
        'stack_bb': sp['stack_bb'], 'hand': sp['hand'], 'hero_cards': sp['hero_cards'],
        'options': _OPTS[sp['scenario']], 'answer': c['answer'],
        'hand_class': ctx.get('hand_class'), 'counterintuitive': ctx.get('counterintuitive'),
        'challenge_score': ctx.get('challenge_score'), 'gto_strategy': ctx.get('gto_strategy'),
        'best_action': ctx.get('best_action'), 'why': ctx.get('why'),
        'explanation': explain_challenge(sp, ctx),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--n', type=int, default=5)
    ap.add_argument('--seed', type=int, default=None, help='fixa a semente (reproduzível); sem isto varia a cada run')
    args = ap.parse_args()

    rng = random.Random(args.seed)   # sem --seed → entropia do sistema (varia por run)
    chosen = curate(args.n, rng)
    if not chosen:
        print('Nenhum spot passou nos filtros. Rode de novo (varia por run).')
        return

    _QUEUE.mkdir(parents=True, exist_ok=True)
    for old in _QUEUE.glob('dia*.json'):   # limpa a fila anterior
        old.unlink()
    for i, c in enumerate(chosen, 1):
        doc = to_doc(c)
        (_QUEUE / f'dia{i}.json').write_text(json.dumps(doc, ensure_ascii=False, indent=2), encoding='utf-8')
        sp, ctx = c['_sp'], c['_ctx']
        mix = ', '.join(f"{l['action']} {round(l['freq'] * 100)}%" for l in ctx.get('gto_strategy') or [])
        print(f"dia{i}: {sp['position']} {sp['stack_bb']}bb {sp['hand']} [{sp['scenario']}] -> {c['answer'].upper()} | {mix}")
    print(f"\n{len(chosen)} spots em {_QUEUE}")
    print("Renderiza com:  cd video && npm run posts")


if __name__ == '__main__':
    main()
