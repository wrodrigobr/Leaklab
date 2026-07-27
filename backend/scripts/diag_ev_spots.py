"""
Prévia do relatório de evolução: custo em bb, não acurácia.

A distinção que estrutura tudo: **bb perdidos ranqueia** (no que mexer agora) e **taxa de erro
valida** (melhorou?). Errar 29% de um spot que custa 0,08bb importa menos que errar 6% de um que
custa 4bb — um relatório ordenado por frequência manda o jogador para o lugar errado.

Zona de ICM fora dos dois lados: o gabarito é chipEV puro e o EV medido ali não descreve a
decisão. Mesmo critério da validação.

SOMENTE LEITURA. Chama `repositories.get_evolution_report`, a mesma função que o endpoint
`/player/evolution` serve — a sonda e a tela não podem discordar sobre o seu jogo.

Uso:
    cd ~/app && docker compose exec web python -m scripts.diag_ev_spots SEU_EMAIL
    cd ~/app && docker compose exec web python -m scripts.diag_ev_spots --user-id 3 --json
"""
import sys, os, json, argparse

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.schema import get_conn
from database.repositories import _adapt, _fetchone, get_evolution_report
from leaklab.gto_utils import STACK_BUCKETS

_ORDEM_POS = ['UTG', 'UTG+1', 'UTG+2', 'LJ', 'HJ', 'CO', 'BTN', 'SB', 'BB']


def _usuario(conn, alvo):
    q = "SELECT id, username FROM users WHERE " + ("id = ?" if str(alvo).isdigit() else "lower(email) = ?")
    r = _fetchone(conn, _adapt(q), (int(alvo) if str(alvo).isdigit() else str(alvo).lower(),))
    return dict(r) if r else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('alvo', nargs='?')
    ap.add_argument('--user-id', dest='uid')
    ap.add_argument('--json', action='store_true', help='despeja o payload cru')
    args = ap.parse_args()
    alvo = args.uid or args.alvo
    if not alvo:
        ap.error('informe o email ou --user-id')

    conn = get_conn()
    try:
        u = _usuario(conn, alvo)
    finally:
        conn.close()
    if not u:
        print(f"usuário não encontrado: {alvo}")
        return

    rel = get_evolution_report(u['id'])
    if args.json:
        print(json.dumps(rel, ensure_ascii=False, indent=1))
        return

    r = rel.get('resumo') or {}
    print(f"usuário: {u['username']} (id={u['id']})   torneios na janela: {r.get('n_torneios', 0)}\n")
    if r.get('bb_por_torneio') is None:
        print("sem torneios com decisões gradeadas.")
        return

    d = r.get('delta')
    seta = '' if d is None else ('▼ melhorou' if d < 0 else '▲ piorou' if d > 0 else '= igual')
    print(f"  EV perdido por torneio : {r['bb_por_torneio']}bb   (metade anterior: {r.get('anterior')}bb)")
    print(f"  variação               : {d if d is not None else '—'}bb  {seta}\n")

    print("  spots mais caros do período:")
    for i, s in enumerate(rel.get('top_spots') or [], 1):
        vs = f" vs {s['vs_position']}" if s.get('vs_position') else ''
        print(f"    {i}. -{s['ev_loss_bb']}bb  {s['street']} · {s['position']}{vs} · "
              f"{s['stack_bb']}bb · jogou {s['action']} (gabarito: {s['best_action']})")
        print(f"       t={s['ext']}&h={s['hand_id']}")
    print()

    # ── matriz posição × profundidade ────────────────────────────────────────────────────
    labels = [b[2] for b in STACK_BUCKETS]
    grade = {}
    for c in rel.get('matriz') or []:
        grade[(c['position'], c['bucket'])] = c
    print("  bb perdidos / 100 decisões — posição × profundidade (n entre parênteses):")
    print("        " + "".join(f"{l:>14s}" for l in labels))
    for pos in _ORDEM_POS:
        if not any((pos, l) in grade for l in labels):
            continue
        linha = f"  {pos:>5s} "
        for l in labels:
            c = grade.get((pos, l))
            celula = '—' if not c else f"{c['bb_100']} ({c['n']})"
            linha += f"{celula:>14s}"
        print(linha)
    print("\n(somente leitura — zona de ICM excluída, mesmo critério da validação)")


if __name__ == '__main__':
    main()
