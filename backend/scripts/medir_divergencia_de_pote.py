# -*- coding: utf-8 -*-
"""DUAS reconstrucoes de pote no produto, e elas nao concordam.

    python scripts/medir_divergencia_de_pote.py <tournament_id_do_site> [n_maos]

── O que se descobriu (24/08, auditoria pre-lancamento) ───────────────────────────────────

O produto tem TRES numeros chamados "pote":

  1. `state.pot_size` -> `decisions.pot_size`
     `_pot_up_to`, que soma `amount` cru. O proprio codigo diz que acerta **1,2%** contra o
     `Total pot` do SUMMARY: perde os blinds e conta o incremento do raise em vez do total.
     Mantido assim DE PROPOSITO (hand_state_builder:804) porque SPR, display e a coluna do
     banco ja dependiam dele.

  2. `_pot_at_decision` -> alimenta as POT ODDS (e o veredito)
     Reconstrucao completa: blinds, antes, o que cada um tem na frente. Declarada em 99,6%
     contra o SUMMARY, medida em 1.682 maos.

  3. `pot_bb` da timeline do `/replay` -> o que o CARD mostra

Auditando 68 decisoes de um torneio real, (2) e (3) divergiram em **19 delas (28%)**, sempre
com (2) MENOR: 4.6 x 5.6, 4.8 x 5.3, 5.3 x 7.3, 11.3 x 14.3.

── Por que isso ficou sem conserto ────────────────────────────────────────────────────────

O oraculo que decidiria (`Total pot` do SUMMARY) NAO EXISTE nos hand histories deste acervo --
`scripts/medir_pote_reconstruido.py` responde "sem oraculo, sem medicao". Sem ele, escolher
entre (2) e (3) para gravar seria trocar um numero possivelmente errado por outro. O backfill
de `pot_at_decision_bb` esta escrito (`scripts/backfill_pot_at_decision.py`) e NAO foi
aplicado por isso.

O que JA melhorou: a nota do card parou de escrever `pot {pot_size}bb` -- ela usa
`pot_at_decision_bb` e, quando a coluna esta vazia (linha antiga), OMITE o pote em vez de
mostrar o numero de (1). Deixar de mentir nao depende de resolver a divergencia.

Este script mede a divergencia a qualquer momento. Quando aparecer um acervo com `Total pot`
no SUMMARY, ele diz qual das duas reconstrucoes seguir.
"""
import json
import sys
import urllib.request

sys.path.insert(0, '/app')

from database.schema import get_conn                            # noqa: E402
from database import auth                                       # noqa: E402
from leaklab.parser import parse_hand_history                   # noqa: E402
from leaklab import hand_state_builder as hsb                   # noqa: E402


def main():
    tid_site = sys.argv[1]
    limite = int(sys.argv[2]) if len(sys.argv) > 2 else 40

    conn = get_conn()
    t = conn.execute('SELECT id, user_id, raw_text FROM tournaments WHERE tournament_id=?',
                     (tid_site,)).fetchone()
    if not t:
        sys.exit('torneio %s nao encontrado' % tid_site)
    t = dict(t)

    cab = {'Authorization': 'Bearer %s' % auth.generate_token(t['user_id'], 'player')}

    def pega(caminho):
        req = urllib.request.Request('http://127.0.0.1:5000' + caminho, headers=cab)
        with urllib.request.urlopen(req, timeout=90) as r:
            return json.loads(r.read().decode('utf-8'))

    batem = 0
    divergem = 0
    exemplos = []
    for hand in parse_hand_history(t['raw_text'])[:limite]:
        hid = str(getattr(hand, 'hand_id', '') or '')
        try:
            rep = pega('/replay/%s/%s' % (tid_site, hid))
        except Exception:                                       # noqa: BLE001
            continue
        acoes = getattr(hand, 'actions', []) or []
        hero = getattr(hand, 'hero', None)
        idx = [i for i, a in enumerate(acoes) if getattr(a, 'player', None) == hero]
        passos = [p for p in rep.get('timeline', [])
                  if p.get('is_hero') and p.get('action') != 'shows']
        bb = float(rep.get('bb') or 0) or 1.0
        for k, p in enumerate(passos):
            if k >= len(idx):
                break
            try:
                pote = hsb._pot_at_decision(hand, acoes, idx[k], p.get('street') or 'preflop')
            except Exception:                                   # noqa: BLE001
                continue
            tela = p.get('pot_bb')
            if tela is None or not pote:
                continue
            meu = round(float(pote) / bb, 1)
            if abs(meu - float(tela)) <= 0.15:
                batem += 1
            else:
                divergem += 1
                if len(exemplos) < 8:
                    exemplos.append('%s %-7s pot_at_decision=%.1f  replay=%.1f  (dif %.1f)'
                                    % (hid, p.get('street'), meu, float(tela),
                                       float(tela) - meu))

    total = batem + divergem
    print('decisoes comparadas: %d' % total)
    print('  as duas reconstrucoes BATEM:   %d  (%.1f%%)'
          % (batem, 100.0 * batem / max(1, total)))
    print('  DIVERGEM:                      %d  (%.1f%%)'
          % (divergem, 100.0 * divergem / max(1, total)))
    if exemplos:
        print('\nexemplos (o do replay e o que o jogador ve no card):')
        for e in exemplos:
            print('  ' + e)


if __name__ == '__main__':
    main()
