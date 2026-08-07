# -*- coding: utf-8 -*-
"""Importa estrategias HEADS-UP do GTO Wizard a partir de arquivos .har.

    python scripts/importar_har_hu.py caminho/um.har [outro.har ...] [--out saida.json]

── Por que existe ─────────────────────────────────────────────────────────────────────────────

A revisao cruzada com o coach (05/08) provou por oraculo externo que gradeavamos o trecho
HEADS-UP com carta de MESA CHEIA: JJ no BB contra open de SB era "call 100%" na nossa carta e
**3-bet 100%** no GW HU real (HAR de 06/08, depth 20.125). O sistema acusou de erro a jogada
correta do jogador.

O usuario captura os nos no GW com o DevTools (Network -> "Save all as HAR with content") e este
script extrai, de cada resposta `spot-solution`, a estrategia COMPLETA das 169 maos.

── As duas licoes de decodificacao, pagas com erro ────────────────────────────────────────────

1. **A ordem dos arrays de 169 NAO e a matriz 13x13.** O proprio `parse_gw_har.py` ja avisava
   ("ordem ... nao e trivial") e eu reincidi: li JJ como "call 90,5%" com a ordem errada. A ordem
   verdadeira vem de `players_info[*].simple_hand_counters`, um dict cuja ORDEM DE INSERCAO
   ('22', '32o', '32s', '33', ...) indexa `strategy`/`evs`/`range`. Este script a le DO PROPRIO
   ARQUIVO, nunca a assume.
2. **Todo no importado passa por validacao de lixo**: num no de defesa de BB vs open, as maos com
   fold 100% tem que ser offsuit fraco (32o, 94o...). Se aparecer par ou As entre elas, a ordem
   esta errada e o no e REJEITADO em vez de importado torto — carta errada e pior que carta
   nenhuma, como a propria carta 9-max acabou de demonstrar.
"""
from __future__ import annotations

import argparse
import base64
import json
import sys
from pathlib import Path

# Maos que PODEM ser fold puro num no de defesa HU. Qualquer coisa fora disto com fold 100%
# indica ordem corrompida. Conservador de proposito: pares e maos com As nunca entram.
_LIXO_ACEITAVEL = {
    f"{a}{b}o" for a in "23456789T" for b in "23456789" if a != b
} | {f"{a}{b}s" for a in "23456" for b in "2345" if a != b} | {
    'J2o', 'J3o', 'J4o', 'J5o', 'J6o', 'J7o', 'Q2o', 'Q3o', 'Q4o', 'Q5o', 'Q6o',
    'K2o', 'K3o', 'K4o', 'T2s', 'T3s',
}


def _texto_da_resposta(entry: dict) -> str:
    c = entry.get('response', {}).get('content', {}) or {}
    txt = c.get('text') or ''
    if c.get('encoding') == 'base64':
        txt = base64.b64decode(txt).decode('utf-8', 'replace')
    return txt


def _rotulo(acao: dict) -> str:
    t = acao.get('type', '?')
    bs = acao.get('betsize')
    return f"{t} {bs}" if bs not in (None, 0, '0') else t


def no_de_resposta(j: dict, q: dict) -> dict | None:
    """Decodifica UMA resposta `spot-solution` no nosso formato de no. None = nao aproveitavel.

    **Porta unica de decodificacao.** Existem dois caminhos que trazem essa resposta — o HAR
    salvo a mao e o `coletor_gw.py` — e a decodificacao (sobretudo a ordem das 169, que ja nos
    custou uma leitura errada) nao pode ter duas copias. `tests/test_coletor_gw.py` varre os
    dois caminhos com o MESMO payload e exige no identico.
    """
    if (q.get('board') or '').strip():
        return None                        # no postflop: este importador modela preflop
    pi = j.get('players_info') or []
    if not pi or not j.get('action_solutions'):
        return None
    ordem = list((pi[0].get('simple_hand_counters') or {}).keys())
    if len(ordem) != 169:
        return None
    ativo = next((p for p in pi if (p.get('player') or {}).get('is_active')), None)
    if not ativo:
        return None

    # A POSICAO vem do payload, nao de heuristica. A primeira versao deduzia 'SB' de `is_dealer`
    # (verdade em HU, inutil em mesa cheia); o GW declara `player.position` e
    # `game.active_position` em toda resposta. Conferido: bate com a heuristica em 21 de 21 nos
    # HU. Em mesa cheia a heuristica nao teria como funcionar — sao 8 posicoes, um dealer so.
    jogo = j.get('game') or {}
    ator = (jogo.get('active_position') or ativo['player'].get('position')
            or ('SB' if ativo['player'].get('is_dealer') else 'BB'))

    # O `strategy` TEM que ter 169 posicoes. Num no postflop ele vem por COMBO (1326) e a
    # indexacao por mao vira lixo — testado com o HAR de 11/05, onde a decodificacao estourou
    # com IndexError assim que o guarda de board foi retirado. Erro em indice e o defeito que
    # menos se anuncia: com 1326 valores e 169 chaves, metade "funcionaria" e mentiria.
    if any(len(s.get('strategy') or []) != 169 for s in j['action_solutions']):
        return None

    maos: dict = {}
    acoes, codigos = [], []
    for s in j['action_solutions']:
        acao = s.get('action') or {}
        rot = _rotulo(acao)
        acoes.append(rot)
        # `code` E o token do no ('F', 'C', 'R2', 'RAI'). Guardamos porque o coletor precisa dele
        # para montar o filho, e deriva-lo por tamanho era chute onde havia dado.
        codigos.append(acao.get('code'))
        evs = s.get('evs') or [None] * 169
        for i, freq in enumerate(s.get('strategy') or []):
            f = float(freq or 0)
            ev = evs[i] if i < len(evs) else None
            # **Guarda tambem a acao de frequencia ZERO, quando o solver publica o EV dela.**
            # Ate 07/08 so guardavamos o que a carta joga, e com isso o motor sabia COM QUE
            # FREQUENCIA cada acao aparece mas nao QUANTO CUSTA escolher outra. Resultado medido:
            # min-raise de SB a 12,6bb virava "erro" custando 0,003bb. O numero que desmente a
            # acusacao estava no payload o tempo todo, no `evs` das acoes nao jogadas.
            if f > 0.0005 or ev is not None:
                maos.setdefault(ordem[i], {})[rot] = {
                    'f': round(f, 4),
                    'ev': (round(float(ev), 4) if ev is not None else None),
                }
    return {
        'gametype': q.get('gametype', ''),
        'depth': q.get('depth', ''),
        'preflop_actions': q.get('preflop_actions', ''),
        'ator': ator,
        'mesa': len(pi),
        'pot': jogo.get('pot'),
        'acoes': acoes,
        'codigos': codigos,
        'maos': maos,
    }


def extrai_nos(har_path: Path) -> list[dict]:
    """Todos os nos `spot-solution` de um HAR, ja decodificados."""
    har = json.loads(har_path.read_text(encoding='utf-8'))
    nos = []
    for entry in har.get('log', {}).get('entries', []):
        url = entry.get('request', {}).get('url', '')
        if '/spot-solution' not in url:
            continue
        txt = _texto_da_resposta(entry)
        if not txt:
            continue                       # o GW manda a mesma chamada 2x, uma vazia
        try:
            j = json.loads(txt)
        except Exception:
            continue
        q = {p['name']: p['value'] for p in entry['request'].get('queryString', [])}
        no = no_de_resposta(j, q)
        if no:
            nos.append(no)
    return nos


def eh_hu(no: dict) -> bool:
    """Mesa de 2. Lido do payload (`mesa` = jogadores em `players_info`) e, para nos antigos que
    nao tem o campo, do gametype."""
    if no.get('mesa'):
        return int(no['mesa']) == 2
    return 'HU' in (no.get('gametype') or '').upper()


def valida_no(no: dict) -> str | None:
    """None = ok; senao, o motivo da rejeicao.

    Duas forcas de validacao, porque o range de chegada muda o que e plausivel:

    - **No de PRIMEIRA decisao** (ROOT, ou BB reagindo a open/limp): o ator chega com as 169.
      Ali fold 100% so pode ser lixo — par ou As foldando denuncia ordem corrompida.
    - **No posterior** (ex.: SB enfrentando 3-bet): o range ja e filtrado e foldar `92s` que
      abriu e LEGITIMO — a primeira versao deste validador rejeitou um no bom por isso. Resta a
      ancora universal: AA/KK nunca sao fold puro preflop HU nessas profundidades. Com ordem
      corrompida, o indice que se le como "AA" e uma mao qualquer, que plausivelmente folda —
      entao a ancora pega a corrupcao com boa probabilidade, sem falso alarme.
    """
    if not any(a.startswith('FOLD') for a in no['acoes']):
        return None
    folds_puros = {mao for mao, acs in no['maos'].items()
                   if acs.get('FOLD', {}).get('f', 0) >= 0.99}
    for ancora in ('AA', 'KK', 'QQ', 'AKs'):
        if ancora in folds_puros:
            return f"ordem corrompida: {ancora} com fold 100%"

    if not eh_hu(no):
        # MESA CHEIA: a lista de lixo aceitavel e de HU, onde as ranges sao larguissimas. Um UTG
        # de 8-max folda Q9o, J9o, T8s — nada disso e "suspeito" ali, e usar a lista de HU
        # rejeitaria no bom (foi assim que a 1a versao do validador matou um no legitimo).
        # A ancora do outro extremo funciona em qualquer mesa: num RFI, `32o` e `72o` SAO fold
        # puro. Se a ordem estiver corrompida, o indice lido como '32o' e uma mao qualquer, que
        # provavelmente nao folda 100% — entao as duas pontas juntas pegam a corrupcao.
        so_folds_antes = all(t == 'F' for t in no['preflop_actions'].split('-') if t)
        if so_folds_antes:
            faltando = [m for m in ('32o', '72o') if m not in folds_puros]
            if faltando:
                return f"ordem suspeita: {faltando} deveria(m) ser fold puro num RFI"
        return None

    primeira_decisao = no['preflop_actions'] in ('', 'R2', 'C') or (
        no['preflop_actions'].count('-') == 0)
    if primeira_decisao:
        suspeitos = [m for m in folds_puros if m not in _LIXO_ACEITAVEL]
        if suspeitos:
            return f"ordem suspeita: fold 100% em {sorted(suspeitos)[:6]}"
    return None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('hars', nargs='+')
    ap.add_argument('--out', default='docs/hu_ranges_har.json')
    args = ap.parse_args()

    # MERGE com o que ja foi importado: os HAR de captura se sobrescrevem no Downloads (os tres
    # ate agora chamavam 'sbxbb.har'), entao o JSON de saida e o unico acumulador que sobrevive.
    # Novo no com a mesma chave substitui o antigo; nos de sessoes anteriores ficam.
    out_previa = Path(args.out)
    saida: dict = {}
    if out_previa.exists():
        try:
            saida = json.loads(out_previa.read_text(encoding='utf-8'))
            print(f"mesclando com {sum(len(v) for v in saida.values())} nos ja importados")
        except Exception:
            saida = {}
    rejeitados = 0
    for caminho in args.hars:
        for no in extrai_nos(Path(caminho)):
            motivo = valida_no(no)
            chave = f"{no['depth']}|{no['preflop_actions'] or 'ROOT'}"
            if motivo:
                rejeitados += 1
                print(f"REJEITADO {chave}: {motivo}")
                continue
            # ultimo vence (recaptura do mesmo no substitui)
            saida.setdefault(no['gametype'], {})[chave] = no
            print(f"OK  {chave:24s} ator={no['ator']} acoes={no['acoes']} "
                  f"maos_no_range={len(no['maos'])}")

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(saida, ensure_ascii=False, indent=1), encoding='utf-8')
    total = sum(len(v) for v in saida.values())
    print(f"\n{total} nos importados, {rejeitados} rejeitados -> {out}")
    return 0 if total else 1


if __name__ == '__main__':
    sys.exit(main())
