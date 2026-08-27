# -*- coding: utf-8 -*-
"""O PORTÃO DE ACEITE de um torneio: o que a TELA mostra, conferido contra os nossos conceitos.

    python scripts/portao_de_aceite.py <dossie.jsonl>

Cada porta abaixo nasceu de um defeito real, e a lista é a memória viva deles. O portão responde
uma pergunta só: **este torneio pode ir para o aluno?**

── Por que sobre o DOSSIÊ e não sobre o banco ─────────────────────────────────────────────

Entre o banco e a tela moram o motor de veredito, a cadeia viva do `/replay`, o StrategyProvider
e o card. Foi lá que todos os defeitos deste projeto moraram — inclusive os de 26/08, em que o
banco estava certo e a tela discordava dele. Ler o banco responderia outra pergunta.

── Regra de leitura ───────────────────────────────────────────────────────────────────────

Toda porta imprime **denominador e violações**. Denominador zero NÃO é aprovação: é
"não testável nesta amostra", e sai marcado como tal. Zero sem denominador é o zero tranquilizador
que encerra investigação, e este projeto já pagou por ele.
"""
import json
import os
import sys
from collections import Counter

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, '/app')

_ACU = ('small_mistake', 'clear_mistake')
_BANDA = {'standard': (0.0, 0.08), 'marginal': (0.09, 0.18),
          'small_mistake': (0.19, 0.35), 'clear_mistake': (0.36, 1.0)}
# o front suprime a qualidade estática quando o solver é benigno; fora daí, o aluno VÊ
_SUPRIME_QUALIDADE = ('gto_correct', 'gto_mixed', 'gto_minor_deviation')
_FAMILIA = {'bet': 'bet', 'bet_33pct': 'bet', 'bet_50pct': 'bet', 'bet_75pct': 'bet',
            'bet_125pct': 'bet', 'allin': 'allin', 'jam': 'allin', 'shove': 'allin',
            'raise': 'raise', 'check': 'check', 'fold': 'fold', 'call': 'call'}


def _fam(a):
    a = str(a or '').lower()
    if a.startswith('raise'):
        return 'raise'
    if a.startswith('bet'):
        return 'bet'
    return _FAMILIA.get(a, a)


def _qualidade(p):
    return str(((p.get('matriz_do_spot') or {}).get('action_quality')) or '')


def carrega(caminho):
    passos, por_mao = [], {}
    with open(caminho, encoding='utf-8') as fh:
        for linha in fh:
            o = json.loads(linha)
            if o.get('tipo') != 'mao':
                continue
            lst = o.get('passos_do_hero') or []
            por_mao[str(o['hand_id'])] = lst
            passos.extend(lst)
    return passos, por_mao


# ── as portas ──────────────────────────────────────────────────────────────────────────────
# cada uma devolve (nome, denominador, violacoes, exemplos)

def porta_procedencia_coerente(passos):
    """Rótulo de solver não convive com procedência `motor` na mesma linha (26/08)."""
    alvo = [p for p in passos if p.get('gto_label')]
    maus = [p for p in alvo if p.get('verdict_source') == 'motor']
    return ('gto_label com procedencia motor', len(alvo), maus)


def porta_linguagem_exige_custo(passos):
    """`pode_falar_como_gto` sem custo medido é falsa autoridade (24/08)."""
    alvo = [p for p in passos if p.get('pode_falar_como_gto') is not None]
    maus = [p for p in alvo if p.get('pode_falar_como_gto') and not p.get('verdict_has_cost')]
    return ('fala como GTO sem custo medido', len(alvo), maus)


def porta_magnitude_exige_custo(passos):
    """O veredito mais duro exige custo medido (26/08)."""
    alvo = [p for p in passos if p.get('error_label')]
    maus = [p for p in alvo
            if p.get('error_label') == 'clear_mistake' and not p.get('verdict_has_cost')]
    return ('clear_mistake sem custo medido', len(alvo), maus)


def porta_score_na_banda(passos):
    """Score fora da banda do próprio rótulo: duas fontes para o mesmo fato (26/08)."""
    alvo = [p for p in passos if p.get('error_label') and p.get('error_score') is not None]
    maus = []
    for p in alvo:
        lo, hi = _BANDA.get(p['error_label'], (0.0, 1.0))
        if not (lo <= float(p['error_score']) <= hi):
            maus.append(p)
    return ('score fora da banda do label', len(alvo), maus)


def porta_nao_acusa_o_que_recomenda(passos):
    """Acusar com a recomendação IGUAL à jogada é dizer "errou, e o certo era o que fez"."""
    alvo = [p for p in passos if p.get('is_error')]
    maus = [p for p in alvo if p.get('best_action')
            and _fam(p['best_action']) == _fam(p.get('action'))]
    return ('acusa com best_action == jogada', len(alvo), maus)


def porta_palavra_bate_com_a_acao(passos):
    """A palavra exibida nomeia a ação do GTO — salvo a regra deliberada de best == jogada."""
    alvo = [p for p in passos if p.get('best_action') and p.get('gto_action')]
    maus = [p for p in alvo
            if _fam(p['best_action']) != _fam(p['gto_action'])
            and _fam(p['best_action']) != _fam(p.get('action'))]
    return ('palavra exibida != acao do GTO', len(alvo), maus)


def porta_qualidade_estatica_nao_contradiz_o_veredito(passos):
    """A direção que o front NÃO suprime: qualidade benigna com veredito de ERRO.

    A direção oposta (qualidade "leak" com veredito "não é erro") é suprimida por
    `cardLogic.mostraQualidadeEstatica` desde 26/08 — medi-la aqui seria medir a própria correção.
    Esta é a que fica descoberta.
    """
    alvo = [p for p in passos if _qualidade(p)]
    maus = [p for p in alvo
            if p.get('is_error') and _qualidade(p) in ('correct', 'acceptable')]
    return ('qualidade benigna com veredito de ERRO', len(alvo), maus)


def porta_a_regra_do_front_que_suprime_a_contradicao_existe(passos):
    """A contradição "major leak" x "não é erro" é suprimida no FRONT, não no payload.

    Por isso ela não se mede no dossiê: `cardLogic.mostraQualidadeEstatica` decide, e o payload
    continua carregando os dois fatos legitimamente. Medir o payload aqui acusaria 20 casos que o
    aluno não vê — foi o que a 1ª versão desta porta fez, e depois a 2ª ficou com o NOME e a
    CONDIÇÃO em desacordo (flagava concordância).

    Então esta porta confere o que dá para conferir daqui: que a regra está no lugar. Os casos
    dela têm teste unitário próprio, quebrado de propósito, em `cardLogic.test.ts`.
    """
    import os as _os
    caminho = _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '..', '..',
                            'frontend', 'src', 'lib', 'cardLogic.ts')
    if not _os.path.exists(caminho):
        return ('regra do front que suprime a contradicao', 0, [])
    with open(caminho, encoding='utf-8') as fh:
        fonte = fh.read()
    ok = 'mostraQualidadeEstatica' in fonte and 'isError === false' in fonte
    return ('regra do front que suprime a contradicao', 1, [] if ok else [{'street': '-',
            'action': 'REGRA AUSENTE', 'best_action': None, 'gto_label': None,
            'error_label': None, 'is_error': None, 'verdict_has_cost': None,
            'equity_source': None}])


def porta_multiway_nao_recebe_solver_hu(passos):
    """O solver é heads-up; em pote multiway o produto se recusa a graduar."""
    alvo = [p for p in passos
            if int(p.get('n_active_opponents') or 0) >= 2
            and (p.get('street') or '') in ('flop', 'turn', 'river')]
    maus = [p for p in alvo if p.get('gto_label') and not p.get('multiway_safe')
            and not p.get('multiway_advice')]
    return ('multiway exibindo rotulo de solver HU', len(alvo), maus)


def porta_fold_nao_condenado_por_equity_vs_random(passos):
    """Equity vs mão aleatória infla e condena quem folda (27/08).

    A direção do erro do estimador depende da CLASSE DA MÃO: com `air` ele infla (acusação falsa),
    com par+ ele SUBvaloriza e a acusação pode ser boa. A porta CHAMA a mesma função da regra
    (`verdict.estimador_infla_a_equity`) em vez de reimplementar a condição — reimplementar no
    medidor é como seis medições desta base foram contaminadas.
    """
    from leaklab.verdict import estimador_infla_a_equity
    alvo = [p for p in passos
            if (p.get('street') or '') in ('flop', 'turn', 'river')
            and str(p.get('action') or '').lower() == 'fold'
            and estimador_infla_a_equity(p.get('hero_cards'), p.get('board'), p.get('street'))]
    maus = [p for p in alvo if p.get('is_error') and p.get('equity_source') == 'vs_random'
            and not p.get('verdict_has_cost')]
    return ('fold acusado so por equity vs_random', len(alvo), maus)


def porta_ausencia_declara_motivo(passos):
    """Ausência de veredito GTO tem que dizer por quê (26/08).

    O campo que declara é `gto_coverage` (postflop) ou `ev_loss_motivo`. A 1ª versão desta porta
    lia `gto_spot_mismatch`/`gto_depth_capped` e acusou 41 casos que declaravam sim — o MESMO erro
    de leitura que fez um juiz de QA reportar "28 ausências mudas". Nenhuma era muda.
    """
    alvo = [p for p in passos
            if p.get('verdict_source') and not p.get('gto_label')
            and str(p.get('action') or '').lower() not in ('shows', 'show', 'mucks', 'muck')]
    maus = [p for p in alvo if not p.get('gto_coverage') and not p.get('ev_loss_motivo')]
    return ('ausencia de GTO sem motivo declarado', len(alvo), maus)


def porta_coverage_nao_mente(passos):
    """`gto_coverage: covered` exige rótulo de fato entregue.

    Dizer "coberto" e não entregar veredito é a contradição que o `_mw_spot` produzia: o sinal era
    calculado antes da supressão multiway. 68 spots do torneio 72.
    """
    alvo = [p for p in passos if p.get('gto_coverage')]
    maus = [p for p in alvo if p['gto_coverage'] == 'covered' and not p.get('gto_label')]
    return ('gto_coverage "covered" sem rotulo entregue', len(alvo), maus)


_PORTAS = [porta_procedencia_coerente, porta_linguagem_exige_custo, porta_magnitude_exige_custo,
           porta_score_na_banda, porta_nao_acusa_o_que_recomenda, porta_palavra_bate_com_a_acao,
           porta_a_regra_do_front_que_suprime_a_contradicao_existe, porta_multiway_nao_recebe_solver_hu,
           porta_fold_nao_condenado_por_equity_vs_random, porta_ausencia_declara_motivo,
           porta_coverage_nao_mente, porta_qualidade_estatica_nao_contradiz_o_veredito]


def main():
    if len(sys.argv) < 2:
        sys.exit('uso: portao_de_aceite.py <dossie.jsonl>')
    passos, por_mao = carrega(sys.argv[1])
    reais = [p for p in passos
             if str(p.get('action') or '').lower() not in ('shows', 'show', 'mucks', 'muck',
                                                           'posts', 'post')]
    print('passos do hero: %d  (decisoes reais: %d)' % (len(passos), len(reais)))
    print('  acusacoes na tela: %d' % sum(1 for p in reais if p.get('is_error')))
    print()
    print('%-46s %10s %10s   %s' % ('porta', 'denomin.', 'violacoes', 'veredito'))
    print('-' * 92)

    reprovou, nao_testavel = 0, 0
    detalhes = []
    for porta in _PORTAS:
        nome, denom, maus = porta(reais)
        if denom == 0:
            veredito = 'NAO TESTAVEL (denominador 0)'
            nao_testavel += 1
        elif maus:
            veredito = 'REPROVOU'
            reprovou += 1
            detalhes.append((nome, maus))
        else:
            veredito = 'ok'
        print('%-46s %10d %10d   %s' % (nome[:46], denom, len(maus), veredito))

    for nome, maus in detalhes:
        print()
        print('== %s (%d)' % (nome, len(maus)))
        for p in maus[:8]:
            print('   %-7s fez %-6s | best=%-10s gto=%-14s | %-13s erro=%-5s custo=%s eq=%s'
                  % (p.get('street'), p.get('action'), p.get('best_action'), p.get('gto_label'),
                     p.get('error_label'), p.get('is_error'), p.get('verdict_has_cost'),
                     p.get('equity_source')))

    print()
    # APROVADO exige as duas coisas: zero violacoes E zero portas sem denominador. Porta que nao
    # pode ser testada nao aprova nada -- a 1a versao imprimia "APROVADO com 12 nao testaveis"
    # para um dossie VAZIO, que e o zero tranquilizador com outro nome.
    if reprovou:
        print('PORTAO: REPROVADO — %d porta(s) com violacao' % reprovou)
    elif nao_testavel:
        print('PORTAO: INCONCLUSIVO — %d de %d portas sem denominador nesta amostra. '
              'Nao aprova: precisa de um torneio que exercite essas portas.'
              % (nao_testavel, len(_PORTAS)))
    else:
        print('PORTAO: APROVADO — todas as %d portas testadas e sem violacao' % len(_PORTAS))
    sys.exit(1 if (reprovou or nao_testavel) else 0)


if __name__ == '__main__':
    main()
