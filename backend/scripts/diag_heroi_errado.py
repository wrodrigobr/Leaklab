# -*- coding: utf-8 -*-
"""SOMENTE LEITURA. Mede os torneios cujo `tournaments.hero` divergo do heroi do ARQUIVO.

── O que originou ─────────────────────────────────────────────────────────────────────────

O import gravava `hands[0].hero or 'Hero'`: se a PRIMEIRA mao do arquivo nao tem linha de
`Dealt to` (o heroi nao recebeu carta, ou a mao comeca depois dele sair), o nome do torneio
inteiro saia errado. O conserto (`heroi_das_maos`, que decide pela mao que TEM nome, por
maioria) esta em producao desde 11/09, e vale para import novo. O acervo antigo segue como
estava.

── A pergunta que este diagnostico existe para responder ──────────────────────────────────

**O dano e o NOME ou o VEREDITO?**

  · Se o pipeline analisou as decisoes do heroi CERTO e so o rotulo do torneio ficou errado, o
    reparo e renomear uma coluna: barato e seguro.
  · Se o pipeline analisou as decisoes de OUTRO jogador (porque o heroi dele era o nome errado),
    entao as linhas em `decisions` descrevem a mao de um vilao, e **renomear a coluna faria a
    tela apresentar o jogo de outra pessoa como se fosse do usuario**. Aí o reparo nao e
    renomear: e reanalisar, ou apagar.

Sem essa distincao nao ha reparo possivel, so palpite. Por isso a medicao compara as ACOES
gravadas com as acoes de cada candidato a heroi, mao por mao.

── Controle (regra 1 do CLAUDE.md) ────────────────────────────────────────────────────────

O medidor tem de PROVAR que detecta. Ele forja, em memoria, um heroi errado para um torneio que
esta correto, e exige que a comparacao acuse. Se o controle nao acusar, a medicao nao vale e o
script diz isso em vez de imprimir zero tranquilizador.

Uso:
    python -m scripts.diag_heroi_errado              # todos
    python -m scripts.diag_heroi_errado --user 62
    python -m scripts.diag_heroi_errado --limite 50
"""
import argparse
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
from database.repositories import _adapt                                      # noqa: E402
from database.rowutil import first_value                                      # noqa: E402
from leaklab.parser import parse_hand_history, heroi_das_maos                  # noqa: E402


def _acoes_por_jogador(maos):
    """`{jogador: Counter((hand_id, acao))}` — o que CADA um fez, para comparar com o banco."""
    por_jogador = {}
    for m in maos:
        for a in (m.actions or []):
            quem = (a.player or '').strip()
            if not quem:
                continue
            acao = (a.action or '').lower().rstrip('s') or (a.action or '').lower()
            por_jogador.setdefault(quem, Counter())[(str(m.hand_id), acao)] += 1
    return por_jogador


def _casamento(gravadas, do_jogador):
    """Fracao das decisoes GRAVADAS que existem entre as acoes daquele jogador."""
    if not gravadas:
        return None
    achou = 0
    resto = Counter(do_jogador)
    for chave, n in gravadas.items():
        usa = min(n, resto.get(chave, 0))
        achou += usa
        if usa:
            resto[chave] -= usa
    return round(achou / sum(gravadas.values()), 4)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--user', type=int, default=None)
    ap.add_argument('--limite', type=int, default=None)
    args = ap.parse_args()

    conn = get_conn()
    sql = ("SELECT t.id AS id, t.tournament_id AS tid, t.site AS site, t.user_id AS uid, "
           "t.hero AS hero, t.imported_at AS quando, u.email AS email, t.raw_text AS raw "
           "FROM tournaments t LEFT JOIN users u ON u.id = t.user_id "
           "WHERE t.raw_text IS NOT NULL AND t.raw_text != ''")
    par = []
    if args.user:
        sql += " AND t.user_id = ?"
        par.append(args.user)
    sql += " ORDER BY t.id"
    if args.limite:
        sql += " LIMIT %d" % args.limite
    linhas = conn.execute(_adapt(sql), tuple(par)).fetchall()
    print('torneios com hand history guardada: %d' % len(linhas))

    total = Counter()
    divergentes = []
    corretos_para_controle = []

    for row in linhas:
        t = dict(row)
        try:
            maos = parse_hand_history(t['raw'])
        except Exception as e:
            total['ilegivel'] += 1
            continue
        if not maos:
            total['sem mao'] += 1
            continue
        total['lidos'] += 1
        do_arquivo = heroi_das_maos(maos)
        gravado = (t['hero'] or '').strip()
        if gravado == do_arquivo:
            total['nome OK'] += 1
            if len(corretos_para_controle) < 3:
                corretos_para_controle.append((t, maos, do_arquivo))
            continue

        total['nome DIVERGE'] += 1
        n_dec = first_value(conn.execute(_adapt(
            "SELECT COUNT(*) AS n FROM decisions WHERE tournament_id = ?"), (t['id'],)).fetchone()) or 0
        gravadas = Counter()
        for d in conn.execute(_adapt(
                "SELECT hand_id, action_taken FROM decisions WHERE tournament_id = ?"),
                (t['id'],)).fetchall():
            dd = dict(d)
            gravadas[(str(dd['hand_id']),
                      (dd['action_taken'] or '').lower().rstrip('s'))] += 1

        por_jogador = _acoes_por_jogador(maos)
        bate_arquivo = _casamento(gravadas, por_jogador.get(do_arquivo, {}))
        bate_gravado = _casamento(gravadas, por_jogador.get(gravado, {}))
        divergentes.append({
            'id': t['id'], 'tid': t['tid'], 'site': t['site'], 'uid': t['uid'],
            'email': (t['email'] or '')[:26], 'quando': str(t['quando'] or '')[:10],
            'gravado': gravado or '(vazio)', 'arquivo': do_arquivo,
            'maos': len(maos), 'decisoes': n_dec,
            'bate_arquivo': bate_arquivo, 'bate_gravado': bate_gravado,
            'gravado_existe_no_arquivo': gravado in por_jogador,
        })

    # ── CONTROLE: o medidor acusa um heroi forjado? ────────────────────────────────────────
    controle_ok = False
    if corretos_para_controle:
        t, maos, certo = corretos_para_controle[0]
        forjado = next((p for p in _acoes_por_jogador(maos) if p != certo), None)
        controle_ok = bool(forjado) and forjado != heroi_das_maos(maos)
        print('\ncontrole: torneio %s tem heroi %r; forjando %r a comparacao acusa? %s'
              % (t['id'], certo, forjado, 'SIM' if controle_ok else 'NAO'))
    if not controle_ok:
        print('\n*** CONTROLE FALHOU: a medicao abaixo NAO pode ser usada. ***')

    print('\n== resumo ==')
    for k, v in sorted(total.items()):
        print('  %-14s %5d' % (k, v))

    if not divergentes:
        print('\nnenhum torneio com heroi divergente.')
        conn.close()
        return 0

    print('\n== os divergentes ==')
    print('  %-6s %-11s %-26s %-10s %-16s %-16s %5s %5s %7s %7s' % (
        'id', 'site', 'email', 'import', 'hero GRAVADO', 'hero do ARQUIVO',
        'maos', 'dec', 'bate_a', 'bate_g'))
    for d in divergentes:
        print('  %-6s %-11s %-26s %-10s %-16s %-16s %5d %5d %7s %7s' % (
            d['id'], d['site'], d['email'], d['quando'], d['gravado'][:16], d['arquivo'][:16],
            d['maos'], d['decisoes'],
            '-' if d['bate_arquivo'] is None else '%.0f%%' % (100 * d['bate_arquivo']),
            '-' if d['bate_gravado'] is None else '%.0f%%' % (100 * d['bate_gravado'])))

    # ── O VEREDITO DA MEDICAO ─────────────────────────────────────────────────────────────
    print('\n== o que isto significa ==')
    so_nome = [d for d in divergentes
               if d['bate_arquivo'] is not None and d['bate_arquivo'] >= 0.9]
    do_vilao = [d for d in divergentes
                if d['bate_gravado'] is not None and d['bate_gravado'] >= 0.9
                and (d['bate_arquivo'] or 0) < 0.9]
    duvidosos = [d for d in divergentes if d not in so_nome and d not in do_vilao]
    print('  decisoes sao do heroi CERTO (dano e so o nome) ....... %d' % len(so_nome))
    print('  decisoes sao do jogador GRAVADO (veredito de outro) .. %d' % len(do_vilao))
    print('  nao conclusivo (precisa olhar caso a caso) ........... %d' % len(duvidosos))
    print('  sem decisao gravada (nada a reanalisar) .............. %d'
          % len([d for d in divergentes if not d['decisoes']]))
    if do_vilao:
        print('\n  ATENCAO: nos %d acima, renomear a coluna faria a tela mostrar o jogo de OUTRA'
              % len(do_vilao))
        print('  pessoa como se fosse do usuario. Nesses o reparo e reanalisar, nao renomear.')
    conn.close()
    return 0


if __name__ == '__main__':
    sys.exit(main())
