# -*- coding: utf-8 -*-
"""Corrige `tournaments.hero` quando o nome gravado nao e um jogador do arquivo.

── O caso (medido em producao em 12/09) ───────────────────────────────────────────────────

21 torneios de duas contas (Michel e Luciper) tem `hero` gravado como o literal `'Hero'`,
enquanto o arquivo diz `MichelDiens` / `Michel Diens` / `Luciper`. As decisoes gravadas SAO
delas: o casamento das acoes com o heroi do arquivo da 89% a 100%, e com o nome gravado da
**0%** — o `'Hero'` nunca agiu, e placeholder. Logo o dano e o rotulo, e o reparo e renomear.

Duas causas, e a segunda nao era conhecida:
  1. a PRIMEIRA mao do arquivo nao tem `Dealt to`, e o import gravava `hands[0].hero or 'Hero'`
     (consertado para import novo em 11/09, com `heroi_das_maos`);
  2. o `hero` e gravado na CRIACAO do torneio e nunca revisto: no t577 a primeira mao traz
     `Luciper` e o campo ficou `'Hero'` de uma subida anterior. Arquivo partido em varias
     subidas reproduz isso sem o bug (1).

── O efeito colateral, que o reparo tem de levar junto ────────────────────────────────────

O `/analyze` grava perfil de oponente para todo jogador `!= hero`. Com o `hero` errado, **o
proprio jogador entrou como oponente de si mesmo**: medido, 21 de 21 torneios tem exatamente um
perfil com o nome do heroi de verdade. Renomear so a coluna deixaria o jogador vendo um "read"
sobre ele mesmo no replay. Por isso este script apaga esse perfil tambem.

── Por que o criterio nao e um corte no casamento ─────────────────────────────────────────

Corte em "90% das acoes casam" seria numero meu: o t208 da 89% e e o mesmo caso. O criterio e
ESTRUTURAL e nao admite grau:

  · o arquivo tem UM heroi so  — arquivo com varios e outra situacao (30 torneios de outra
    conta, arquivos de terceiros) e este script NUNCA os toca;
  · o nome gravado NAO e jogador do arquivo  — e o que prova que ele e invalido, nao uma escolha;
  · o heroi do arquivo APARECE entre os jogadores  — prova que o nome novo e real.

O casamento entra no relatorio como informacao, com um piso baixo de sanidade para recusar o
caso esquisito, nao para separar os legitimos.

Uso:
    python -m scripts.repara_heroi_do_arquivo                  # dry-run
    python -m scripts.repara_heroi_do_arquivo --apply
    python -m scripts.repara_heroi_do_arquivo --apply --dump ~/rollback/heroi.jsonl
"""
import argparse
import io
import json
import os
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))
except Exception:
    pass

from database.schema import get_conn                                          # noqa: E402
from database.repositories import _adapt                                     # noqa: E402
from database.rowutil import first_value                                     # noqa: E402
from leaklab.parser import parse_hand_history, heroi_das_maos                 # noqa: E402

#: Piso de sanidade, nao criterio de selecao: abaixo disto a linha vai para "recusado" e alguem
#: olha. Os casos legitimos medidos em producao ficam entre 89% e 100%.
PISO_CASAMENTO = 0.50


def jogadores_do_arquivo(maos):
    """Todo nome que APARECE no arquivo, como assento ou como autor de acao."""
    nomes = set()
    for m in maos:
        for a in (m.actions or []):
            if (a.player or '').strip():
                nomes.add(a.player.strip())
        for s in (m.seats or []):
            n = (s.get('name') if isinstance(s, dict) else None) or ''
            if n.strip():
                nomes.add(n.strip())
        for p in (m.players or []):
            if isinstance(p, str) and p.strip():
                nomes.add(p.strip())
    return nomes


def herois_do_arquivo(maos):
    return Counter((m.hero or '').strip() for m in maos if (m.hero or '').strip())


def casamento_com(conn, tid, maos, quem):
    """Fracao das decisoes gravadas que existe entre as acoes de `quem`."""
    gravadas = Counter()
    for d in conn.execute(_adapt(
            "SELECT hand_id, action_taken FROM decisions WHERE tournament_id = ?"),
            (tid,)).fetchall():
        dd = dict(d)
        gravadas[(str(dd['hand_id']), (dd['action_taken'] or '').lower().rstrip('s'))] += 1
    if not gravadas:
        return None
    dele = Counter()
    for m in maos:
        for a in (m.actions or []):
            if (a.player or '').strip() != quem:
                continue
            acao = (a.action or '').lower().rstrip('s') or (a.action or '').lower()
            dele[(str(m.hand_id), acao)] += 1
    achou = sum(min(n, dele.get(k, 0)) for k, n in gravadas.items())
    return round(achou / sum(gravadas.values()), 4)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--apply', action='store_true')
    ap.add_argument('--dump', default=None, help='JSONL com de/para, para desfazer')
    ap.add_argument('--user', type=int, default=None)
    args = ap.parse_args()

    conn = get_conn()
    sql = ("SELECT t.id AS id, t.hero AS hero, t.site AS site, t.user_id AS uid, "
           "u.email AS email, t.raw_text AS raw FROM tournaments t "
           "LEFT JOIN users u ON u.id = t.user_id "
           "WHERE t.raw_text IS NOT NULL AND t.raw_text != ''")
    par = []
    if args.user:
        sql += " AND t.user_id = ?"
        par.append(args.user)
    sql += " ORDER BY t.id"
    linhas = conn.execute(_adapt(sql), tuple(par)).fetchall()

    total = Counter()
    reparos, recusados = [], []
    for row in linhas:
        t = dict(row)
        try:
            maos = parse_hand_history(t['raw'])
        except Exception:
            total['ilegivel'] += 1
            continue
        if not maos:
            continue
        total['lidos'] += 1
        gravado = (t['hero'] or '').strip()
        hs = herois_do_arquivo(maos)
        if not hs:
            total['arquivo sem heroi'] += 1
            continue
        do_arquivo = heroi_das_maos(maos)
        if gravado == do_arquivo:
            total['nome OK'] += 1
            continue

        # ── CRITERIO ESTRUTURAL ──────────────────────────────────────────────────────────
        if len(hs) > 1:
            total['RECUSADO multi-heroi'] += 1
            recusados.append((t['id'], gravado, do_arquivo,
                              'arquivo tem %d herois: e o caso dos arquivos de terceiros' % len(hs)))
            continue
        presentes = jogadores_do_arquivo(maos)
        if gravado and gravado in presentes:
            total['RECUSADO nome gravado E jogador'] += 1
            recusados.append((t['id'], gravado, do_arquivo,
                              'o nome gravado joga no arquivo: renomear seria trocar de pessoa'))
            continue
        if do_arquivo not in presentes:
            total['RECUSADO nome novo ausente'] += 1
            recusados.append((t['id'], gravado, do_arquivo,
                              'o nome novo nao aparece entre os jogadores'))
            continue
        bate = casamento_com(conn, t['id'], maos, do_arquivo)
        if bate is not None and bate < PISO_CASAMENTO:
            total['RECUSADO casamento baixo'] += 1
            recusados.append((t['id'], gravado, do_arquivo,
                              'as decisoes casam so %.0f%% com o nome novo' % (100 * bate)))
            continue

        perfil_de_si = first_value(conn.execute(_adapt(
            "SELECT COUNT(*) AS n FROM opponent_profiles WHERE tournament_id = ? "
            "AND player_name = ?"), (t['id'], do_arquivo)).fetchone()) or 0
        total['A REPARAR'] += 1
        reparos.append({'id': t['id'], 'site': t['site'], 'uid': t['uid'],
                        'email': (t['email'] or '')[:26],
                        'de': gravado or '(vazio)', 'para': do_arquivo,
                        'maos': len(maos), 'bate': bate, 'perfil_de_si': perfil_de_si})

    print('== resumo ==')
    for k, v in sorted(total.items()):
        print('  %-32s %5d' % (k, v))

    if recusados:
        print('\n== RECUSADOS (e por que) ==')
        for r in recusados:
            print('  t%-6s %-16s -> %-16s %s' % r)

    if not reparos:
        print('\nnada a reparar.')
        conn.close()
        return 0

    print('\n== a reparar ==')
    print('  %-6s %-11s %-26s %-16s %-16s %5s %7s %6s' % (
        'id', 'site', 'email', 'de', 'para', 'maos', 'bate', 'perfil'))
    for r in reparos:
        print('  %-6s %-11s %-26s %-16s %-16s %5d %7s %6d' % (
            r['id'], r['site'], r['email'], r['de'][:16], r['para'][:16], r['maos'],
            '-' if r['bate'] is None else '%.0f%%' % (100 * r['bate']), r['perfil_de_si']))
    print('\n  torneios: %d | perfis do proprio jogador a apagar: %d'
          % (len(reparos), sum(r['perfil_de_si'] for r in reparos)))

    if not args.apply:
        print('\nDRY-RUN. Repita com --apply para gravar.')
        conn.close()
        return 0

    dump = io.open(args.dump, 'a', encoding='utf-8', newline='\n') if args.dump else None
    gravados = perfis = 0
    for r in sorted(reparos, key=lambda x: x['id']):      # ordem crescente de id, como sempre
        if dump is not None:
            dump.write(json.dumps({'tabela': 'tournaments', 'id': r['id'],
                                   'coluna': 'hero', 'de': r['de'], 'para': r['para'],
                                   'perfil_apagado': r['para'] if r['perfil_de_si'] else None},
                                  ensure_ascii=False) + '\n')
        conn.execute(_adapt("UPDATE tournaments SET hero = ? WHERE id = ?"),
                     (r['para'], r['id']))
        gravados += 1
        if r['perfil_de_si']:
            conn.execute(_adapt("DELETE FROM opponent_profiles WHERE tournament_id = ? "
                                "AND player_name = ?"), (r['id'], r['para']))
            perfis += 1
    conn.commit()
    if dump is not None:
        dump.close()

    # ── CONFERENCIA EXPLICITA (regra 6): UPDATE que nao casa nada nao levanta erro ────────
    ids = [r['id'] for r in reparos]
    marcas = ', '.join(['?'] * len(ids))
    errados = first_value(conn.execute(_adapt(
        "SELECT COUNT(*) AS n FROM tournaments WHERE id IN (%s) AND hero = 'Hero'" % marcas),
        tuple(ids)).fetchone()) or 0
    sobrou = 0
    for r in reparos:
        sobrou += first_value(conn.execute(_adapt(
            "SELECT COUNT(*) AS n FROM opponent_profiles WHERE tournament_id = ? "
            "AND player_name = ?"), (r['id'], r['para'])).fetchone()) or 0
    conn.close()
    print('\nGRAVADOS %d torneios | %d perfis do proprio jogador apagados' % (gravados, perfis))
    print('conferencia: torneios ainda com hero=\'Hero\': %d (esperado 0) | '
          'perfis de si mesmo restantes: %d (esperado 0)' % (errados, sobrou))
    if args.dump:
        print('registro para desfazer: %s' % args.dump)
    return 0 if (errados == 0 and sobrou == 0) else 1


if __name__ == '__main__':
    sys.exit(main())
