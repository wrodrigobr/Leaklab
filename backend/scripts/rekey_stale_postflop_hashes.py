"""Re-chaveia nós postflop cujo spot_hash foi computado com a normalização de posição ANTIGA
(MP1/MP2 crus, antes do fix MP1→LJ no compute_spot_hash). Sintoma: o nó foi solvado e existe,
mas sob o hash errado, e o lookup da decisão (compute_spot_hash NOVO = LJ) não o encontra →
o spot fica 'Pendente'/heurística pra sempre mesmo com nó solvado.

Recomputa o hash correto a partir do spot_json da fila (código atual) e:
  - se NÃO existe nó sob o hash correto → renomeia (UPDATE gto_nodes.spot_hash).
  - se JÁ existe → o antigo é órfão duplicado, remove.
Mexe SÓ em gto_nodes de spots POSTFLOP. Nunca toca preflop/GW.

Uso:
    python -m scripts.rekey_stale_postflop_hashes            # dry-run (conta)
    python -m scripts.rekey_stale_postflop_hashes --apply
"""
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from database.schema import get_conn
from leaklab.gto_utils import compute_spot_hash

_POSTFLOP = ('flop', 'turn', 'river')
_APPLY = '--apply' in sys.argv


def main():
    conn = get_conn()
    node_hashes = {dict(r)['spot_hash'] for r in conn.execute('SELECT spot_hash FROM gto_nodes').fetchall()}
    rows = conn.execute('SELECT spot_hash, spot_json FROM gto_solver_queue').fetchall()

    renamed = removed = ok = 0
    for r in rows:
        d = dict(r)
        old = d['spot_hash']
        sj_raw = d.get('spot_json')
        try:
            sj = json.loads(sj_raw) if isinstance(sj_raw, str) else (sj_raw or {})
        except Exception:
            continue
        if (sj.get('street') or '').lower() not in _POSTFLOP:
            continue
        # CIRÚRGICO: só os spots cuja posição é da família full-ring que ESTE fix normaliza
        # (MP1→LJ, MP2→HJ, MP→LJ). Não re-chaveia drift histórico não relacionado.
        if (sj.get('position') or '').upper().strip() not in ('MP1', 'MP2', 'MP'):
            continue
        try:
            new = compute_spot_hash(
                sj.get('street', ''), sj.get('position', ''), sj.get('board', []),
                sj.get('hero_hand', []), float(sj.get('hero_stack_bb') or 20),
                float(sj.get('facing_size_bb') or 0),
            )
        except Exception:
            continue
        if new == old:
            continue                              # hash já correto (posição canônica)
        if old not in node_hashes:
            continue                              # sem nó sob o hash antigo → nada a re-chavear
        if new in node_hashes:
            if _APPLY:
                conn.execute('DELETE FROM gto_nodes WHERE spot_hash = ?', (old,))
            node_hashes.discard(old)
            removed += 1
            action = 'DEDUP'
        else:
            if _APPLY:
                conn.execute('UPDATE gto_nodes SET spot_hash = ? WHERE spot_hash = ?', (new, old))
            node_hashes.discard(old); node_hashes.add(new)
            renamed += 1
            action = 'REKEY'
        print(f"  {action} {sj.get('position')}/{sj.get('street')} {old[:10]} -> {new[:10]}")

    if _APPLY:
        conn.commit()
    conn.close()
    print(f"\n{'APLICADO' if _APPLY else 'DRY-RUN (use --apply)'}: "
          f"re-chaveados={renamed}, duplicados removidos={removed}")


if __name__ == '__main__':
    main()
