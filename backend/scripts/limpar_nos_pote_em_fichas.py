"""Remove os nós postflop que nasceram com o pote em FICHAS, e devolve as decisões deles ao
estado honesto de "sem cobertura".

## Por que eles existem

`_enfileirar_spot_da_decisao` passava `spot['potSize']` (FICHAS) como `pot_bb`, enquanto os outros
dois pontos do mesmo arquivo dividiam pelo `level_bb`. Pote ~100x inflado faz o SPR colapsar, o
solver força all-in e devolve estratégia degenerada com exploitability 0,0% falsa. **A fonte foi
corrigida em 2026-08-02**; este script trata só o que já ficou gravado.

## Por que APAGAR e não re-chavear

Nó degenerado produz veredito CONFIANTE e ERRADO. Apagar transforma isso em "sem cobertura", que é
o estado honesto — o jogador deixa de receber uma resposta em vez de receber uma errada.

Re-chavear (apontar a decisão para outro nó) está FORA de questão: é exatamente o erro que o bug do
board ensinou. Bug que some com a resposta é honesto; conserto que a TROCA não é.

## O que este script toca, e só

1. `gto_nodes` — as linhas cujo `pot_bb` do payload é implausível para o stack do próprio nó.
2. `gto_solver_queue` — as linhas correspondentes, para que o payload errado não seja reprocessado.
3. `decisions` — apaga APENAS as colunas de veredito GTO das decisões que apontavam para esses nós
   (`gto_label`, `gto_action`, `gto_played_freq`, `gto_top_freq`, `gto_depth_capped`, `spot_hash`,
   e o `ev_loss_bb` quando ele veio do GTO). O resto da decisão fica intacto.

**NUNCA** usa `cleanup --tournament`, que purga global — ver [[project_degenerate_pot_nodes]].
**NUNCA** toca preflop nem `gto_preflop_ranges`.

## O que ele NÃO faz, de propósito

Não re-enfileira. O `spot_json` guardado tem o pote errado, então re-enfileirar reproduziria o bug.
Os spots voltam para a fila naturalmente pelo caminho já corrigido, no próximo `/analyze` ou pedido
de mão que os alcance.

## Uso

    python -m scripts.limpar_nos_pote_em_fichas              # dry-run (padrão), não escreve nada
    python -m scripts.limpar_nos_pote_em_fichas --detalhe    # dry-run + lista nó a nó
    python -m scripts.limpar_nos_pote_em_fichas --executar   # aplica
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
try:
    sys.stdout.reconfigure(encoding='utf-8')
except Exception:
    pass
try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))
except Exception:
    pass

from database.schema import get_conn
from database.repositories import _adapt

# Mesma régua do filtro que passou a valer no enfileiramento e no treino: um pote maior que os dois
# stacks somados não existe em heads-up. Manter o número em UM lugar seria melhor; aqui ele está
# duplicado de propósito, porque um script de limpeza não pode mudar de comportamento se a
# constante do produto mudar depois — o que ele apaga tem que ser o que este arquivo descreve.
POTE_MAX_EM_STACKS = 2.5

_COLUNAS_VEREDITO = ('gto_label', 'gto_action', 'gto_played_freq', 'gto_top_freq')


def _carrega(v):
    return json.loads(v) if isinstance(v, (str, bytes)) else v


def levantar() -> list[dict]:
    """Os nós postflop cujo pote é implausível para o stack do próprio nó."""
    with get_conn() as conn:
        linhas = conn.execute(_adapt("""
            SELECT g.spot_hash, g.street, g.position, g.gto_action, g.gto_freq,
                   g.exploitability_pct, q.spot_json
              FROM gto_nodes g
              JOIN gto_solver_queue q ON q.spot_hash = g.spot_hash
             WHERE LOWER(g.street) IN ('flop','turn','river')
        """)).fetchall()

    fora = []
    for r in linhas:
        sj = _carrega(r['spot_json']) or {}
        pote = float(sj.get('pot_bb') or 0)
        stack = float(sj.get('effective_stack_bb') or sj.get('hero_stack_bb') or 0)
        if not stack:
            continue                     # sem stack não dá para julgar o pote: não mexe
        if pote <= 0 or pote > stack * POTE_MAX_EM_STACKS:
            fora.append({'spot_hash': r['spot_hash'], 'street': r['street'],
                         'position': r['position'], 'gto_action': r['gto_action'],
                         'gto_freq': float(r['gto_freq'] or 0),
                         'exploit': r['exploitability_pct'],
                         'pot_bb': pote, 'stack_bb': stack})
    return fora


def raio(hashes: list[str]) -> dict:
    """Quem depende desses nós hoje. É o que o usuário precisa ver ANTES de decidir."""
    if not hashes:
        return {'decisoes': 0, 'com_veredito': 0, 'criticas': 0, 'jogadores': 0, 'amostra': []}
    ph = ','.join(['?'] * len(hashes))
    with get_conn() as conn:
        d = conn.execute(_adapt(f"""
            SELECT COUNT(*) AS n,
                   SUM(CASE WHEN gto_label IS NOT NULL AND gto_label <> '' THEN 1 ELSE 0 END) AS com,
                   SUM(CASE WHEN gto_label = 'gto_critical' THEN 1 ELSE 0 END) AS crit
              FROM decisions WHERE spot_hash IN ({ph})"""), tuple(hashes)).fetchone()
        u = conn.execute(_adapt(f"""
            SELECT COUNT(DISTINCT t.user_id) AS u FROM decisions d
              JOIN tournaments t ON t.id = d.tournament_id
             WHERE d.spot_hash IN ({ph})"""), tuple(hashes)).fetchone()
        am = conn.execute(_adapt(f"""
            SELECT d.street, d.hero_cards, d.action_taken, d.gto_action, d.gto_label, d.ev_loss_bb
              FROM decisions d WHERE d.spot_hash IN ({ph})
               AND d.gto_label IS NOT NULL AND d.gto_label <> ''
             ORDER BY CASE WHEN d.gto_label='gto_critical' THEN 0 ELSE 1 END LIMIT 10"""),
            tuple(hashes)).fetchall()
    return {'decisoes': int(d['n'] or 0), 'com_veredito': int(d['com'] or 0),
            'criticas': int(d['crit'] or 0), 'jogadores': int(u['u'] or 0),
            'amostra': [dict(r) for r in am]}


def executar(hashes: list[str]) -> dict:
    """Aplica. Uma transação por etapa, com contagem conferida — em PG uma falha aborta a
    transação e os comandos seguintes falham CALADOS, então cada etapa reporta o que fez."""
    if not hashes:
        return {}
    ph = ','.join(['?'] * len(hashes))
    feito = {}
    with get_conn() as conn:
        # 1. limpa o VEREDITO das decisões (o dado da mão fica intacto)
        sets = ', '.join(f'{c} = NULL' for c in _COLUNAS_VEREDITO)
        cur = conn.execute(_adapt(
            f"UPDATE decisions SET {sets}, gto_depth_capped = 0, spot_hash = NULL, "
            f"ev_loss_bb = CASE WHEN ev_loss_source LIKE '%gto%' THEN NULL ELSE ev_loss_bb END, "
            f"ev_loss_source = CASE WHEN ev_loss_source LIKE '%gto%' THEN NULL ELSE ev_loss_source END "
            f"WHERE spot_hash IN ({ph})"), tuple(hashes))
        feito['decisoes_limpas'] = getattr(cur, 'rowcount', -1)
        # 2. some com a linha da fila, senão o payload errado volta a ser processado
        cur = conn.execute(_adapt(f"DELETE FROM gto_solver_queue WHERE spot_hash IN ({ph})"),
                           tuple(hashes))
        feito['fila_removida'] = getattr(cur, 'rowcount', -1)
        # 3. e o nó
        cur = conn.execute(_adapt(f"DELETE FROM gto_nodes WHERE spot_hash IN ({ph})"), tuple(hashes))
        feito['nos_removidos'] = getattr(cur, 'rowcount', -1)
        conn.commit()
    return feito


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--executar', action='store_true', help='aplica (padrão é dry-run)')
    ap.add_argument('--detalhe', action='store_true', help='lista nó a nó')
    args = ap.parse_args()

    nos = levantar()
    hashes = [n['spot_hash'] for n in nos]
    print(f"{'='*70}")
    print('NÓS POSTFLOP COM POTE IMPLAUSÍVEL (pote em fichas)')
    print(f"{'='*70}")
    print(f'  régua: pote <= 0 ou pote > {POTE_MAX_EM_STACKS}x o stack do próprio nó')
    print(f'  encontrados: {len(nos)}')
    if not nos:
        print('\nNada a fazer.')
        return

    degenerados = [n for n in nos if n['gto_freq'] >= 0.99
                   and str(n['gto_action']).lower() in ('allin', 'all-in', 'jam', 'shove')]
    fake = [n for n in nos if n['exploit'] is not None and float(n['exploit']) <= 0.05]
    print(f'    all-in a 100%                : {len(degenerados)}')
    print(f'    exploitability <= 0,05% (fake): {len(fake)}')

    r = raio(hashes)
    print(f"\n{'-'*70}")
    print('QUEM DEPENDE DELES HOJE')
    print(f"{'-'*70}")
    print(f"  decisões apontando           : {r['decisoes']}")
    print(f"  ... com veredito GTO na tela : {r['com_veredito']}")
    print(f"  ... rotuladas gto_critical   : {r['criticas']}   <-- 'você errou feio', sobre pote inflado")
    print(f"  jogadores afetados           : {r['jogadores']}")
    if r['amostra']:
        print('\n  o que esses jogadores veem hoje:')
        for a in r['amostra']:
            print(f"    {a['street']:6s} {str(a['hero_cards']):10s} fez={str(a['action_taken']):6s} "
                  f"gto={str(a['gto_action']):6s} ({a['gto_label']}) ev_loss={a['ev_loss_bb']}")

    if args.detalhe:
        print(f"\n{'-'*70}\n  NÓ A NÓ\n{'-'*70}")
        for n in nos:
            print(f"    {n['spot_hash']}  {n['street']:6s} {str(n['position']):6s} "
                  f"pote {n['pot_bb']:9.1f}bb  stack {n['stack_bb']:6.1f}bb  "
                  f"-> {n['gto_action']} @ {n['gto_freq']:.2f}  exploit {n['exploit']}")

    print(f"\n{'='*70}")
    if not args.executar:
        print('DRY-RUN — nada foi escrito.')
        print(f'  Aplicando, aconteceria: {len(nos)} nós removidos, {len(hashes)} linhas de fila')
        print(f'  removidas, e {r["com_veredito"]} decisões perderiam o veredito GTO')
        print('  (viram "sem cobertura", que é o estado honesto — o dado da mão fica intacto).')
        print('\n  Para aplicar:  python -m scripts.limpar_nos_pote_em_fichas --executar')
        return

    print('APLICANDO...')
    feito = executar(hashes)
    print(f"  decisões limpas : {feito.get('decisoes_limpas')}")
    print(f"  fila removida   : {feito.get('fila_removida')}")
    print(f"  nós removidos   : {feito.get('nos_removidos')}")

    # Conferência explícita: operação que pode falhar em silêncio precisa provar que fez.
    restantes = levantar()
    print(f"\n  CONFERÊNCIA — nós implausíveis restantes: {len(restantes)}  (tem que ser 0)")
    if restantes:
        print('  ATENÇÃO: sobrou coisa. Rode de novo com --detalhe e investigue antes de concluir.')
        sys.exit(1)
    print('\nFeito. Os spots voltam à fila naturalmente, pelo caminho já corrigido.')


if __name__ == '__main__':
    main()
