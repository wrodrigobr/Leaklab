# -*- coding: utf-8 -*-
"""
Nome da posicao por assento — FONTE UNICA.

── O bug que originou ─────────────────────────────────────────────────────────────────────────────

Usuario, sobre uma mao heads-up da ACR: "no torneio acr as blinds nao estao sendo exibidas".

Medido no payload real de producao (mao 2789068082): as posicoes saiam `{seat 4: 'SB',
seat 3: 'BTN'}`. Em heads-up **o botao E o small blind**, entao o certo e `{seat 3: 'SB'/'BTN',
seat 4: 'BB'}`. O resultado na tela: o rotulo BB nao existia, e o "SB" aparecia sobre quem tinha
postado a big blind. Para quem olha a mesa, isso e exatamente "as blinds nao estao sendo
exibidas".

── Por que aconteceu ──────────────────────────────────────────────────────────────────────────────

A regra estava em DUAS copias. `hand_state_builder._position_names` tinha o caso de heads-up, com
comentario e tudo (foi consertado la porque o SB/botao virava BB e o spot ficava sem cobertura
GTO). A copia do `_build_replay_data` NAO tinha — e o comentario dela dizia
"mesma derivacao do engine (_infer_position) e do builder", afirmando uma equivalencia que nao
existia. Comentario nao e evidencia.

Com n=2 a copia montava o dict `{0:'SB', 1:'BB', n-1:'BTN'}`, e como `n-1 == 1` a ultima chave
vencia: o 'BB' era sobrescrito por 'BTN' e desaparecia.

── A divergencia de nomes, que e DE PROPOSITO ─────────────────────────────────────────────────────

As duas copias tambem discordavam no miolo da mesa: o builder chamava de `MP1` o que o replay
chama de `LJ`. Isso NAO e acidente — `LJ` e o nome que o Decision Card e o GTO Solver usam, e
mudar o do builder mexeria em lookup de range. Por isso o miolo e parametro (`miolo`), nao um
valor unico: a funcao e uma so, e cada chamador declara qual vocabulario usa.
"""
from __future__ import annotations

# Ordem de preenchimento do miolo da mesa, do UTG para o centro, nos dois vocabularios.
_MIOLO = {
    'LJ':  ['UTG', 'UTG+1', 'UTG+2', 'LJ', 'MP2', 'MP3'],    # replay / Decision Card / GTO Solver
    'MP1': ['UTG', 'UTG+1', 'UTG+2', 'MP1', 'MP2', 'MP3'],   # hand_state_builder (historico)
}


def nomes_de_posicao(n: int, miolo: str = 'LJ') -> dict:
    """Nome da posicao por INDICE na ordem de acao preflop: 0=SB, 1=BB, ..., n-1=BTN.

    O chamador ordena os assentos no sentido do jogo a partir do assento seguinte ao botao e usa
    o indice aqui. `miolo` escolhe o vocabulario das posicoes intermediarias — ver o modulo.
    """
    if n <= 0:
        return {}
    if n == 1:
        return {0: 'BTN'}
    if n == 2:
        # HEADS-UP: o botao E o small blind. Como o chamador poe o botao por ULTIMO
        # (indice n-1 == 1), o indice 1 e o SB e o indice 0 e o BB. Nao da para derivar isso da
        # regra geral, e foi justamente o caso que a copia do replay nao tinha.
        return {0: 'BB', 1: 'SB'}

    nomes = {0: 'SB', 1: 'BB', n - 1: 'BTN'}
    if n >= 4:
        nomes[n - 2] = 'CO'
    if n >= 6:
        nomes[n - 3] = 'HJ'
    seq = _MIOLO.get(miolo) or _MIOLO['LJ']
    i = 0
    for k in range(2, n):
        if k not in nomes:
            nomes[k] = seq[i] if i < len(seq) else f'P{k}'
            i += 1
    return nomes
