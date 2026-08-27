# -*- coding: utf-8 -*-
"""Transforma a captura bruta em DOSSIES legiveis, um por decisao do hero.

    python3 scripts/dossies_para_auditoria.py /tmp/t72.jsonl /tmp/dossies.jsonl

Cada dossie carrega o que um jogador precisa para julgar a decisao E o que o produto DISSE
sobre ela. Quem audita responde tres perguntas:

  1. o VEREDITO esta certo? (correto / aceitavel / erro)
  2. a RECOMENDACAO faz sentido no spot?
  3. a MATRIZ (range daquela posicao e profundidade) bate com o veredito?

Nomes de vilao viram V1, V2... e o hero vira HERO: a auditoria julga decisao, nao pessoa, e
o dossie sai da maquina de producao.
"""
import json
import re
import sys


def _anonimiza(texto, mapa):
    if not isinstance(texto, str):
        return texto
    for real, falso in mapa.items():
        if real:
            texto = re.sub(re.escape(real), falso, texto)
    return texto


def _mapa_de_nomes(replay):
    mapa = {}
    hero = replay.get('hero')
    if hero:
        mapa[hero] = 'HERO'
    i = 0
    for assento in (replay.get('seats') or {}).values():
        nome = assento.get('player') if isinstance(assento, dict) else None
        if nome and nome not in mapa:
            i += 1
            mapa[nome] = 'V%d' % i
    for passo in replay.get('timeline') or []:
        for assento in (passo.get('seats') or {}).values():
            nome = assento.get('player') if isinstance(assento, dict) else None
            if nome and nome not in mapa:
                i += 1
                mapa[nome] = 'V%d' % i
    return mapa


_CAMPOS_DO_PASSO = (
    'street', 'action', 'amount', 'desc', 'pot', 'pot_bb', 'board', 'hero_cards',
    'hero_stack_bb', 'm_ratio', 'icm_pressure', 'icm_tax_pct', 'n_can_see_flop',
    'n_active_opponents', 'facing_to_call_bb', 'facing_limp', 'draw_profile',
    'hand_equity', 'equity_source', 'pot_odds_equity', 'adjusted_required_equity',
    # o VEREDITO e a recomendacao, que e o que se audita
    # `best_action_recusado`: sem ele o auditor ve `best_action` ausente e nao consegue
    # distinguir falta de cobertura de RECUSA declarada -- um juiz leu a ausencia como
    # "acusacao entregue sem resposta" porque o campo do motivo nao vinha no dossie.
    'best_action', 'best_action_recusado', 'engine_best', 'error_label', 'error_score',
    'is_error',
    'gto_action', 'gto_label', 'gto_coverage', 'gto_spot_mismatch', 'gto_depth_capped',
    'ev_loss_bb', 'ev_loss_motivo', 'multiway_safe', 'multiway_advice',
    # PROCEDENCIA (25/08): de onde veio o veredito e se ele pode falar como GTO. Sem estes
    # campos a auditoria nao consegue julgar a pergunta mais importante -- "esta acusacao tem
    # direito a se chamar GTO?" -- e a sonda de invariante acusava 411/411 "sem procedencia"
    # medindo o proprio dossie, nao o produto.
    'verdict_source', 'verdict_has_cost', 'pode_falar_como_gto',
    'postflop_sizing', 'postflop_texture_sizing', 'bet_intent',
    'math_penalty', 'context_penalty',
)


def main():
    bruto, saida = sys.argv[1], sys.argv[2]
    matrizes = {}
    dossies = {}
    torneio = None

    with open(bruto, encoding='utf-8') as fh:
        for linha in fh:
            reg = json.loads(linha)
            if reg['tipo'] == 'torneio':
                torneio = {'tournament_id': reg['tournament_id'],
                           'n_decisoes': reg['n_maos'],
                           'torneio': reg['detalhe'].get('tournament')}
            elif reg['tipo'] == 'matriz':
                matrizes['%s|%s' % (reg['position'], reg['stack_bb'])] = reg['grade']
            elif reg['tipo'] == 'replay':
                hid = reg['hand_id']
                if hid in dossies:
                    continue
                replay = reg['replay']
                mapa = _mapa_de_nomes(replay)
                passos = []
                for p in replay.get('timeline') or []:
                    if not p.get('is_hero'):
                        continue
                    d = {k: p.get(k) for k in _CAMPOS_DO_PASSO if p.get(k) is not None}
                    d['desc'] = _anonimiza(d.get('desc'), mapa)
                    pg = p.get('preflop_gto')
                    if pg:
                        d['matriz_do_spot'] = {
                            'position': pg.get('position'), 'stack_bb': pg.get('stack_bb'),
                            'vs_position': _anonimiza(pg.get('vs_position'), mapa),
                            'scenario': pg.get('scenario'), 'available': pg.get('available'),
                            'hand_type': pg.get('hand_type'),
                            'hand_freq': pg.get('hand_freq'),
                            'action_quality': pg.get('action_quality'),
                            'ev_loss_bb': pg.get('ev_loss_bb'),
                            'ev_loss_source': pg.get('ev_loss_source'),
                            'fold_pct': pg.get('fold_pct'), 'call_pct': pg.get('call_pct'),
                            'allin_pct': pg.get('allin_pct'),
                        }
                    passos.append(d)
                if not passos:
                    continue
                dossies[hid] = {
                    'hand_id': hid,
                    'hero_cards': replay.get('hero_cards'),
                    'board_final': replay.get('board'),
                    'sb': replay.get('sb'), 'bb': replay.get('bb'),
                    'is_pko': replay.get('is_pko'),
                    'lista': {k: reg['lista'].get(k) for k in (
                        'street', 'action_taken', 'best_action', 'label', 'score',
                        'gto_label', 'gto_action', 'ev_loss_bb', 'ev_loss_source',
                        'position', 'vs_position', 'stack_bb', 'effective_stack_bb',
                        'note', 'estimated_equity', 'multiway_safe_verdict',
                        'gto_played_freq', 'gto_top_freq', 'num_players',
                        'n_active_opponents', 'm_ratio', 'is_3bet', 'facing_bet',
                        'pot_size', 'draw_profile', 'level_bb', 'hero_won_hand')},
                    'passos_do_hero': passos,
                }

    with open(saida, 'w', encoding='utf-8') as fh:
        fh.write(json.dumps({'tipo': 'contexto', 'torneio': torneio,
                             'n_maos': len(dossies), 'matrizes': matrizes},
                            ensure_ascii=False) + '\n')
        for hid in sorted(dossies):
            fh.write(json.dumps({'tipo': 'mao', **dossies[hid]}, ensure_ascii=False) + '\n')

    print('maos com decisao do hero: %d' % len(dossies))
    print('matrizes capturadas: %d' % len(matrizes))
    print('passos do hero no total: %d'
          % sum(len(d['passos_do_hero']) for d in dossies.values()))


if __name__ == '__main__':
    main()
