# -*- coding: utf-8 -*-
"""Apaga os perfis de oponente de salas em que o nome do vilao nao identifica uma pessoa.

── Por que existe ─────────────────────────────────────────────────────────────────────────

O `/analyze` deixou de construir perfil para essas salas (ver
`leaklab.opponent_stats.SALAS_SEM_IDENTIDADE_DE_VILAO`), mas o que JA FOI GRAVADO continua no
banco, e o replayer mostra o bloco de perfis quando ele vem preenchido. Desligar a torneira nao
esvazia o balde: o jogador que abrir um torneio antigo do PartyPoker segue vendo read confiante
sobre um "oponente" que e a soma de todos os que ocuparam aquele assento.

Read com lastro falso e pior que read ausente, porque o jogador age nele.

── Cuidado de medicao ─────────────────────────────────────────────────────────────────────

O dry-run mostra a CONTAGEM POR SALA e uma amostra dos nomes. Se a amostra vier com nome de
gente de verdade, o filtro pegou a sala errada e nao se aplica nada — e por isso a amostra
aparece antes da pergunta, nao depois.

Uso:
    python -m scripts.limpa_perfis_sem_identidade              # dry-run
    python -m scripts.limpa_perfis_sem_identidade --apply
    python -m scripts.limpa_perfis_sem_identidade --site partypoker --apply
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))
except Exception:
    pass

from database.schema import get_conn                                          # noqa: E402
from database.repositories import _adapt                                      # noqa: E402
from leaklab.opponent_stats import SALAS_SEM_IDENTIDADE_DE_VILAO              # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--apply', action='store_true')
    ap.add_argument('--site', default=None,
                    help='limita a UMA sala (tem de estar na lista sem identidade)')
    args = ap.parse_args()

    salas = list(SALAS_SEM_IDENTIDADE_DE_VILAO)
    if args.site:
        alvo = args.site.lower()
        if alvo not in salas:
            print('ERRO: %r nao esta em SALAS_SEM_IDENTIDADE_DE_VILAO (%s). Esta lista e a '
                  'fonte unica, e apagar perfil de sala fora dela seria perda de dado bom.'
                  % (args.site, ', '.join(salas)))
            return 2
        salas = [alvo]
    print('salas sem identidade de vilao: %s' % ', '.join(salas))

    conn = get_conn()
    marcas = ', '.join(['?'] * len(salas))
    linhas = conn.execute(_adapt(
        "SELECT t.site AS site, p.player_name AS nome, p.hands_seen AS maos "
        "FROM opponent_profiles p JOIN tournaments t ON t.id = p.tournament_id "
        "WHERE lower(t.site) IN (%s) ORDER BY p.hands_seen DESC" % marcas), tuple(salas)).fetchall()

    if not linhas:
        print('\nnenhum perfil gravado para essas salas. Nada a fazer.')
        conn.close()
        return 0

    por_sala = {}
    for r in linhas:
        d = dict(r)
        por_sala.setdefault((d['site'] or '').lower(), []).append(d)
    print()
    for sala, itens in sorted(por_sala.items()):
        print('  %-12s %5d perfis | amostra: %s' % (
            sala, len(itens),
            ', '.join('%s(%s maos)' % (i['nome'], i['maos']) for i in itens[:6])))
    print('\n  TOTAL a apagar: %d perfis' % len(linhas))
    print('  Confira a amostra: se houver nome de jogador de verdade ai, o filtro pegou a sala '
          'errada e NAO se aplica.')

    if not args.apply:
        print('\nDRY-RUN. Repita com --apply para apagar.')
        conn.close()
        return 0

    cur = conn.execute(_adapt(
        "DELETE FROM opponent_profiles WHERE tournament_id IN "
        "(SELECT id FROM tournaments WHERE lower(site) IN (%s))" % marcas), tuple(salas))
    conn.commit()
    # Conferencia EXPLICITA: `DELETE` que nao casa nada nao levanta erro nenhum (regra 6).
    resta = conn.execute(_adapt(
        "SELECT COUNT(*) FROM opponent_profiles p JOIN tournaments t ON t.id = p.tournament_id "
        "WHERE lower(t.site) IN (%s)" % marcas), tuple(salas)).fetchone()[0]
    conn.close()
    print('\nAPAGADOS. Restam %d perfis dessas salas (esperado: 0).' % resta)
    return 0 if resta == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
