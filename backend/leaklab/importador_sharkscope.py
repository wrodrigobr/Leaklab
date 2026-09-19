# -*- coding: utf-8 -*-
"""Importa o RESULTADO de torneios a partir do JSON do SharkScope. Uso ADMIN, por enquanto.

── O pedido (19/09) ──────────────────────────────────────────────────────────────────────────

O dono: "podemos criar um importador com base no json... assim eu posso capturar manualmente os
torneios dos jogadores, e inserir na ferramenta... ela deve ser apenas para uso admin por
enquanto".

Contexto medido: no acervo, `buy_in` esta preenchido em 8,9% dos torneios e `profit` em 6,7%. O
PartyPoker nao publica summary que saibamos ler, e e justamente a sala que o SharkScope rastreia
com precisao. Este modulo fecha esse buraco sem assinatura comercial: o dono obtem o JSON pela
via normal e cola aqui.

── O que este modulo NAO faz ────────────────────────────────────────────────────────────────

Nao busca nada. Nao fala com o SharkScope. Recebe um JSON que alguem ja tinha em maos. A API
deles exige assinatura Pro (US$ 166+/mes) e automatizar o site seria contornar o licenciamento;
nenhum dos dois caminhos esta aqui.

E nao traz mao nenhuma: a base do SharkScope e de RESULTADO. Isto completa a camada financeira, e
nunca a de analise.

── As tres armadilhas do formato, achadas lendo um HAR real ─────────────────────────────────

1. **`@reEntries` NAO e do jogador.** E o total de re-entradas DO TORNEIO (16, 32, 19 nos dados
   reais). O numero do jogador e `@multientries`. Confundir os dois multiplicaria o custo dele
   por vinte.
2. **Freeroll entra com `@stake` zero.** Sem marcacao, ele entra no ROI com denominador falso.
3. **O `@id` e do SharkScope, nao da sala.** Nao serve de chave para casar com o que o jogador
   importou por hand history. O pareamento tem de ser por outro caminho -- ver `parear`.

── Por que o pareamento e por DIA + COLOCACAO ───────────────────────────────────────────────

Na primeira comparacao que eu fiz entre este JSON e producao, eu casei por dia + buy-in e **troquei
os pares** em dias com dois torneios do mesmo buy-in. Apareceram divergencias que nao existiam. A
colocacao e o campo que distingue, e o buy-in so entra como desempate.
"""
from __future__ import annotations

import datetime
import logging
from typing import List, Optional

log = logging.getLogger(__name__)

#: Procedencia gravada em `tournaments.financeiro_origem`.
ORIGEM = 'sharkscope'

#: Hierarquia de confianca. O arquivo da sala e autoritativo e NAO e sobrescrito: trocar dado real
#: por dado de terceiro seria perda, e ela seria silenciosa. O SharkScope fica acima do digitado
#: (ele bateu em 7 de 7 torneios conferidos contra producao em 19/09) e abaixo do arquivo.
MAIS_CONFIAVEL = ('arquivo',)


def _num(v) -> Optional[float]:
    try:
        return round(float(v), 2)
    except (TypeError, ValueError):
        return None


def normalizar(payload: dict) -> List[dict]:
    """JSON do SharkScope -> lista de resultados no vocabulario do produto.

    Aceita o corpo inteiro da resposta (com `Response`) ou so o `PlayerResponse`. Nao levanta por
    campo ausente: torneio sem os campos minimos e DESCARTADO com motivo, porque meia linha e pior
    que nenhuma.
    """
    resp = payload.get('Response', payload)
    try:
        jogador = resp['PlayerResponse']['PlayerView']['Player']
    except (KeyError, TypeError):
        return []

    bruto = (jogador.get('CompletedTournaments') or {}).get('Tournament') or []
    if isinstance(bruto, dict):          # um torneio so nao vem em lista
        bruto = [bruto]

    saida = []
    for t in bruto:
        en = t.get('TournamentEntry') or {}
        stake, rake = _num(t.get('@stake')), _num(t.get('@rake'))
        if stake is None or rake is None or not t.get('@date'):
            continue
        # O custo e (stake + rake) x quantas vezes ELE entrou. `@multientries`, nunca
        # `@reEntries` -- ver o cabecalho.
        try:
            entradas = max(1, int(en.get('@multientries') or 1))
        except (TypeError, ValueError):
            entradas = 1
        buy = round((stake + rake) * entradas, 2)
        premio = _num(en.get('@prize')) or 0.0
        try:
            quando = datetime.datetime.fromtimestamp(int(t['@date']), datetime.timezone.utc)
        except (TypeError, ValueError, OSError):
            continue
        saida.append({
            'jogador':    jogador.get('@name'),
            'rede':       t.get('@network') or jogador.get('@network'),
            'nome':       t.get('@name'),
            'quando':     quando,
            'dia':        quando.strftime('%Y-%m-%d'),
            'buy_in':     buy,
            'entradas':   entradas,
            'premio':     premio,
            'bounty':     _num(en.get('@prizeBountyComponent')) or 0.0,
            'lucro':      round(premio - buy, 2),
            'colocacao':  int(en.get('@position')) if (en.get('@position') or '').isdigit() else None,
            'field':      int(t['@totalEntrants']) if str(t.get('@totalEntrants', '')).isdigit() else None,
            'prize_pool': _num(t.get('@prizePool')),
            'moeda':      t.get('@currency'),
            'freeroll':   (stake + rake) == 0,
            'id_sharkscope': t.get('@id'),
        })
    return saida


def parear(resultados: List[dict], torneios: List[dict]) -> List[dict]:
    """Casa cada resultado com um torneio do jogador. Duas passadas, da chave FORTE para a fraca.

    Devolve a lista de resultados com `par` (o torneio casado ou None) e `chave` (por que casou).
    Nenhum torneio e usado duas vezes: e o mesmo cuidado do `BaldeDeDecisoes`, e pelo mesmo motivo
    -- chave que nao e unica, consumida sem controle, faz o segundo par sobrescrever o primeiro.
    """
    livres = list(range(len(torneios)))

    def mesmo_dia(t, r):
        return str(t.get('played_at') or '')[:10] == r['dia']

    for chave in ('dia+colocacao', 'dia+premio', 'dia+buy_in'):
        for r in resultados:
            if r.get('par') is not None:
                continue
            for k in list(livres):
                t = torneios[k]
                if not mesmo_dia(t, r):
                    continue
                ok = (
                    (chave == 'dia+colocacao' and r['colocacao'] is not None
                     and t.get('place') == r['colocacao'])
                    or (chave == 'dia+premio' and r['premio'] > 0
                        and _num(t.get('prize')) == r['premio'])
                    or (chave == 'dia+buy_in' and _num(t.get('buy_in')) == r['buy_in'])
                )
                if ok:
                    r['par'], r['chave'] = t, chave
                    livres.remove(k)
                    break
    for r in resultados:
        r.setdefault('par', None)
        r.setdefault('chave', None)
    return resultados


def planejar(user_id: int, payload: dict, torneios: List[dict]) -> dict:
    """O que o import FARIA. E a mesma funcao que o `aplicar` usa para decidir.

    Preview que descreve outra operacao e pior que preview nenhum: aqui os dois leem deste plano,
    e nao ha um caminho para o seco e outro para o molhado.
    """
    resultados = parear(normalizar(payload), torneios)
    plano = {'atualizar': [], 'sem_par': [], 'protegidos': [], 'iguais': []}
    for r in resultados:
        t = r['par']
        if t is None:
            plano['sem_par'].append(r)
            continue
        origem = (t.get('financeiro_origem') or '')
        if origem in MAIS_CONFIAVEL:
            r['motivo'] = 'ja tem resultado do arquivo da sala, que e mais confiavel'
            plano['protegidos'].append(r)
            continue
        ja = (_num(t.get('buy_in')) == r['buy_in'] and (_num(t.get('prize')) or 0.0) == r['premio']
              and t.get('place') == r['colocacao'])
        (plano['iguais'] if ja else plano['atualizar']).append(r)
    plano['torneios_sem_resultado'] = [
        t for t in torneios
        if not any(r['par'] is t for r in resultados)
    ]
    return plano


def aplicar(user_id: int, plano: dict) -> dict:
    """Grava o que o plano mandou. So o que esta em `atualizar`."""
    from database.repositories import update_tournament_financials
    feitos = falhos = 0
    for r in plano.get('atualizar', []):
        t = r['par']
        try:
            ok = update_tournament_financials(
                user_id, str(t.get('tournament_id')),
                buy_in=r['buy_in'], prize=r['premio'],
                # O lucro NAO vem do JSON: e calculado, como na entrada manual. Aceitar os tres
                # numeros de fora deixaria entrar um conjunto que nao fecha.
                profit=r['lucro'], place=r['colocacao'],
                field_size=r['field'], prize_pool=r['prize_pool'],
                re_entries=r['entradas'] if r['entradas'] > 1 else None,
                origem=ORIGEM)
            feitos += 1 if ok else 0
            falhos += 0 if ok else 1
        except Exception:
            log.exception("importador sharkscope: falha no torneio %s", t.get('tournament_id'))
            falhos += 1
    return {'atualizados': feitos, 'falhos': falhos}
