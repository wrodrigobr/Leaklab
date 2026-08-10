"""
preflop_gto_ranges.py — Análise GTO de preflop a partir do JSON validado.

Cobre três cenários:
  RFI     — Raise First In: primeira a abrir em determinada posição
  vs_RFI  — defendendo contra abertura de outro jogador
  vs_3bet — respondendo a um re-raise após sua abertura
"""
from __future__ import annotations
import json, logging, os
from typing import Optional

log = logging.getLogger(__name__)

_RANGES_FILE = os.path.join(os.path.dirname(__file__), '..', 'docs', 'leaklab_gto_ranges.json')
_data: Optional[dict] = None


def _load() -> dict:
    global _data
    if _data is None:
        with open(_RANGES_FILE, 'r', encoding='utf-8') as f:
            _data = json.load(f)
    return _data


# ── PKO (Progressive Knockout) — ranges do GW por estágio field-remaining ──────
_PKO_RANGES_FILE = os.path.join(os.path.dirname(__file__), '..', 'docs', 'leaklab_pko_ranges.json')
_pko_data: Optional[dict] = None


def _load_pko() -> dict:
    global _pko_data
    if _pko_data is None:
        try:
            with open(_PKO_RANGES_FILE, 'r', encoding='utf-8') as f:
                _pko_data = json.load(f)
        except FileNotFoundError:
            _pko_data = {}
    return _pko_data


def _pko_ranges_for(stack_bb: float, field: str = '200p'):
    """Seleciona o estágio PKO pelo depth e devolve (ranges_do_bucket, stage_token,
    stage_label) ou (None, None, None).

    No GW o depth é acoplado ao estágio field-remaining; os depths canônicos
    capturados são START=100, PCT90=90, PCT70=70 e depois um PLATÔ em 50bb
    (PCT50/PCT37/PCT25/BUBBLEMID/T3). No platô usamos PCT50 (mid-game
    representativo) — distinguir os estágios de 50bb exige field-remaining, que a
    hand history não traz. Abaixo de ~45bb não há range PKO (o GW não resolve PKO
    raso) → devolve None p/ cair no Classic (push/fold). T2/FT são config-specific
    (stacks heterogêneos, não capturáveis uniforme)."""
    pko = _load_pko().get('pko_ranges', {}).get(field, {})
    if not pko or stack_bb < 45:
        return None, None, None
    if stack_bb >= 95:
        stage = 'START'
    elif stack_bb >= 80:
        stage = 'PCT90'
    elif stack_bb >= 60:
        stage = 'PCT70'
    else:
        stage = 'PCT50'
    node = pko.get(stage)
    if not node or not node.get('ranges'):
        return None, None, None
    ranges = node['ranges']
    bucket = next(iter(ranges))     # cada estágio tem 1 bucket (o depth canônico)
    return ranges[bucket], stage, node.get('_stage')


# ── EV-loss (#24): overlay de EV por mão/ação (bb) ────────────────────────────
_EVS_FILE = os.path.join(os.path.dirname(__file__), '..', 'docs', 'leaklab_gto_evs.json')
_evs_data: Optional[dict] = None


def _load_evs() -> dict:
    global _evs_data
    if _evs_data is None:
        try:
            with open(_EVS_FILE, 'r', encoding='utf-8') as f:
                _evs_data = json.load(f)
        except FileNotFoundError:
            _evs_data = {}
    return _evs_data


def _ev_action_code(action_taken: str, hand_ev: dict) -> Optional[str]:
    """Mapeia a ação do hero pro code do EV ({F, C, R*, RAI})."""
    at = (action_taken or '').lower()
    if at == 'fold':
        return 'F'
    if at in ('call', 'check', 'complete'):
        return 'C'
    if at in ('jam', 'shove', 'allin', 'all-in'):
        return 'RAI'
    if at in ('raise', 'bet', '3bet', '4bet', 'squeeze'):
        rs = [c for c in hand_ev if c.startswith('R') and c != 'RAI']
        return rs[0] if rs else None
    return None


def _evs_da_mao(bucket: str, scenario: str, hero: str, vs: str, hero_hand: str):
    """`{codigo de acao: EV em bb}` que `leaklab_gto_evs.json` publica para esta mão neste nó.
    `None` sem cobertura. Único leitor desse JSON — dois caminhos indexando o mesmo arquivo por
    conta própria foi como a contradição do KK chegou ao card."""
    bk = _load_evs().get('ranges', {}).get(bucket, {})
    if scenario == 'rfi':
        spot = bk.get('RFI', {}).get(hero)
    elif scenario == 'vs_rfi':
        spot = bk.get('vs_RFI', {}).get(vs, {}).get(hero)
    elif scenario in ('vs_3bet', 'squeeze', 'vs_4bet', 'faces_squeeze'):
        spot = bk.get(scenario, {}).get(hero, {}).get(vs)
    else:
        spot = None
    return (spot or {}).get(hero_hand) or None


def _margem_ev_sobre_fold(bucket: str, scenario: str, hero: str, vs: str, hero_hand: str):
    """Quanto a MELHOR ação vale a mais que o fold, em bb, pela carta de EV. `None` sem cobertura.

    É o oráculo que diz o TAMANHO da vantagem de continuar — não só que existe. Usado pelo teto de
    tamanho: uma vantagem de 11,4bb (AA) não some porque o vilão abriu 1,3bb a mais; uma de 0,14bb
    (75o) some.
    """
    ev = _evs_da_mao(bucket, scenario, hero, vs, hero_hand)
    if not ev or 'F' not in ev:
        return None
    return round(max(ev.values()) - float(ev['F']), 3)


def _ev_loss_bb(bucket: str, scenario: str, hero: str, vs: str,
                hero_hand: str, action_taken: str):
    """ev_loss_bb da mão do hero = max_ação(ev) − ev(ação escolhida), clamp ≥0.
    Devolve (ev_loss, source) ou (None, None) sem cobertura. Source 'gw_har'."""
    hand_ev = _evs_da_mao(bucket, scenario, hero, vs, hero_hand)
    if not hand_ev:
        return None, None
    code = _ev_action_code(action_taken, hand_ev)
    if code is None or code not in hand_ev:
        return None, None
    best = max(hand_ev.values())
    return round(max(0.0, best - hand_ev[code]), 3), 'gw_har'


# Hardcoded buckets — JSON v3 (GW master) não tem stack_buckets section.
# Mantém compat com v2 que tinha campo no JSON.
_DEFAULT_BUCKETS = [
    ('10bb',  0,    12),
    ('14bb',  12,   15.5),
    ('17bb',  15.5, 18.5),
    ('20bb',  18.5, 25),
    ('30bb',  25,   35),
    ('40bb',  35,   45),
    ('50bb',  45,   62.5),
    ('75bb',  62.5, 87.5),
    ('100bb', 87.5, 9999),
]

def _stack_bucket(stack_bb: float) -> str:
    data = _load()
    # Prioriza campo do JSON se existir (v2 antigo)
    for label, bounds in data.get('stack_buckets', {}).items():
        if bounds.get('min', 0) <= stack_bb <= bounds.get('max', 0):
            return label
    # Fallback hardcoded (v3 não tem stack_buckets no JSON)
    for label, lo, hi in _DEFAULT_BUCKETS:
        if lo <= stack_bb < hi:
            return label
    return '100bb'


def _profundidade_compativel(depth: float, stack_bb: float) -> bool:
    """A carta de `depth` bb pode falar de um stack de `stack_bb`? Janela RELATIVA de 25%.

    Extraída de `_hu_no_mais_proximo`, onde a regra nasceu e onde o comentário original explica o
    porquê do número: a 40% um SB de 14,8bb era gradeado pelo nó de 10bb — outro REGIME (a 10bb o
    SB é jam/limp; a 15bb existe raise normal) — e um AJo foi acusado por min-raisar "em vez de
    jamar". Fronteira de regime é onde profundidade vizinha mais mente.

    Relativa e não absoluta: 5bb de distância a 10bb é outra estratégia; 5bb a 100bb é ruído.

    **Quatro consumidores**, e os dois últimos chegaram aqui no mesmo dia por lados diferentes: o
    nó HU, o seletor de balde das ranges de open/re-raise (0,2bb recebia a carta de 10bb) e o
    consumo da range de JAM, onde a mesma saturação produziu **duas acusações falsas medidas no
    acervo** — `3hAh CO vs BTN a 3,9bb` e `KdJs BTN vs SB a 5,2bb` viravam `small_mistake`, e a
    4bb pagar um jam com A3s é obrigatório."""
    d, s = float(depth or 0), float(stack_bb or 0)
    if d <= 0 or s <= 0:
        return False
    return abs(d - s) / max(d, s) <= 0.25


def _balde_da_carta(stack_bb: float) -> Optional[str]:
    """Balde de ranges para este stack — ou None quando a profundidade do balde não cabe nele.

    `_stack_bucket` PARTICIONA a reta: o balde mais raso é `[0, 12)` e o mais fundo `[87.5, 9999)`,
    então nas duas pontas ele **satura em silêncio**. Um jogador de 0,2bb recebia a carta de 10bb
    (e um de 195bb, a de 100bb) sem nenhum sinal de que a carta era de outra profundidade.

    Este é o mesmo seletor que o caminho HU já usa via `_profundidade_compativel`, e por isso a
    resposta aqui é a mesma de lá: **null honesto**. Quem não passa cai no vs-random, que é
    exatamente o comportamento que esses spots tinham antes de existir range nenhuma — não é
    perda de veredito, é parar de fingir precisão que a carta não tem."""
    label = _stack_bucket(stack_bb)
    try:
        depth = float(str(label).replace('bb', ''))
    except ValueError:
        # Rótulo não-numérico só existe no `stack_buckets` do JSON v2 (custom). Sem depth para
        # conferir, mantém o comportamento antigo em vez de derrubar cobertura por não saber.
        return label
    return label if _profundidade_compativel(depth, stack_bb) else None


def _expand_range(notation: str) -> set[str]:
    """Expande notação de range separada por vírgula em conjunto de hand_types."""
    if not notation or 'N/A' in notation.upper():
        return set()
    from leaklab.gto_utils import expand_range_notation
    hands: set[str] = set()
    for part in notation.split(','):
        part = part.strip()
        if not part:
            continue
        for h in expand_range_notation(part):
            if len(h) == 2:
                hands.add(h)                         # par: 'AA', 'KK'
            elif len(h) >= 3 and h[-1] not in ('s', 'o'):
                hands.add(h + 's')                   # sem sufixo → ambos
                hands.add(h + 'o')
            else:
                hands.add(h)
    return hands


def _in_range(hand_type: str, notation: str) -> bool:
    if not hand_type or not notation:
        return False
    return hand_type in _expand_range(notation)


_ACT = {'ALLIN': 'jam', 'RFI': 'raise', 'THREBET': 'raise', 'CALL': 'call', 'FOLD': 'fold'}
_POS = {
    'BTN': 'Button', 'CO': 'Cutoff', 'HJ': 'HiJack', 'LJ': 'LoJack',
    'UTG': 'UTG', 'UTG1': 'UTG+1', 'SB': 'Small Blind', 'BB': 'Big Blind',
}

# Pipeline (hand_state_builder._position_names) e JSON v3 (GW MTTGeneralV2 9-max)
# usam nomenclaturas diferentes. Mapeamento depende do TAMANHO DA MESA (n_players).
#
# Pipeline naming por n_players (de hand_state_builder._position_names):
#   n=6: SB, BB, UTG, HJ, CO, BTN
#   n=7: SB, BB, UTG, UTG+1, HJ, CO, BTN
#   n=8: SB, BB, UTG, UTG+1, UTG+2, HJ, CO, BTN
#   n=9: SB, BB, UTG, UTG+1, UTG+2, MP1, HJ, CO, BTN
#  n=10: SB, BB, UTG, UTG+1, UTG+2, MP1, MP2, HJ, CO, BTN
#
# GW MTTGeneralV2 (sempre 9-max): SB, BB, UTG, UTG+1, UTG+2, LJ, HJ, CO, BTN
#
# Mapping por ordem de ação (pipeline_pos → GW pos):
# Mesa de N seats, hero na ordem K (0=SB, 1=BB, 2=UTG, ...):
#   - K ∈ {0, 1}: blinds direto (SB/BB)
#   - K = 2: UTG
#   - K = N-1: BTN
#   - K = N-2: CO
#   - K = N-3: HJ
#   - K ∈ [3, N-4]: ordem early/middle → mapear pro slot equivalente em GW 9-max
#
# Em GW 9-max (N=9): ordem early = {3:UTG+1, 4:UTG+2, 5:LJ}
# Pra mesa menor (8/7/6), comprimimos: pipeline 'UTG+2' em 8-max = LJ em GW (3ª ação).

# Mapping estático default — assume GW 9-max nativo.
# Usado quando n_players desconhecido (fallback).
_POS_NORM = {
    'UTG':   'UTG',
    'UTG+1': 'UTG+1',
    'UTG+2': 'UTG+2',
    'LJ':    'LJ',
    'HJ':    'HJ',
    'CO':    'CO',
    'BTN':   'BTN',
    'SB':    'SB',
    'BB':    'BB',
    'UTG1':  'UTG+1',   # legacy v2
    'UTG2':  'UTG+2',   # legacy v2
    'MP1':   'LJ',      # 9-max pipeline: 4ª ação = LJ no GW
    'MP2':   'HJ',      # 10-max pipeline: 5ª ação (raro)
    'MP':    'LJ',      # genérico
}

# ── Pipeline N-max → GW 9-max: parear por JOGADORES ATRÁS ─────────────────────────────────────
#
# A tabela estática que morava aqui misturava duas filosofias e por isso mentia. CO e BTN eram
# mapeados por jogadores atrás (certo), mas UTG e HJ por ÍNDICE DE AÇÃO (errado): numa mesa de 6 o
# HJ, que tem 4 jogadores atrás, recebia a carta de UTG+1 9-max — a range mais TIGHT da mesa
# grande. Medido: 17,7% de abertura contra os 29,3% que a posição pede a 40bb, e 17 tipos de mão
# que a carta equivalente abre 100% e a usada abre 0% (KTo, JTo, QTo, A8o, 33…). Abrir KTo do 2º
# assento 6-max, que todo regular faz, saía `gto_critical`. Mesas de 3/4/5 nem tinham entrada e
# caíam no default 9-max, que é ainda mais tight.
#
# O que define a range de abertura é QUANTOS AINDA PODEM AGIR depois de você, não em que ordem
# você agiu. Por isso a regra virou UMA conta, e não uma tabela por tamanho de mesa: mesa nova
# nunca mais fica sem entrada. A ordem dos nomes vem de `leaklab.posicoes` — a MESMA fonte que o
# pipeline usa para batizar o assento; re-derivá-la aqui seria a segunda cópia de sempre.
_ORDEM_GW_9MAX = ('UTG', 'UTG+1', 'UTG+2', 'LJ', 'HJ', 'CO', 'BTN', 'SB', 'BB')
# quantos agem DEPOIS na primeira órbita: UTG=8 … BTN=2, SB=1, BB=0
_GW_POR_ATRAS = {len(_ORDEM_GW_9MAX) - 1 - i: p for i, p in enumerate(_ORDEM_GW_9MAX)}
_ATRAS_MAX_GW = max(_GW_POR_ATRAS)

# Apelidos de dialeto que não são posição nova, só grafia (v2 legado / genérico).
_POS_ALIAS = {'UTG1': 'UTG+1', 'UTG2': 'UTG+2', 'MP': 'LJ'}

_mapa_mesa_cache: dict[int, dict[str, str]] = {}


def _mapa_da_mesa(n: int) -> dict[str, str]:
    """{nome do pipeline → posição GW 9-max} para uma mesa de n, pareado por jogadores atrás."""
    if n in _mapa_mesa_cache:
        return _mapa_mesa_cache[n]
    from leaklab.posicoes import nomes_de_posicao
    out: dict[str, str] = {}
    # Os dois vocabulários do projeto (`LJ` no replay/Decision Card, `MP1` no hand_state_builder)
    # nomeiam o MESMO assento — ver o cabeçalho de `leaklab/posicoes.py`. Indexar os dois evita
    # que o dialeto de quem chama decida se há cobertura.
    for vocab in ('LJ', 'MP1'):
        for i, nome in nomes_de_posicao(n, miolo=vocab).items():
            if nome in ('SB', 'BB'):
                out[nome] = nome
                continue
            # (n-1-i) ainda por agir na mesa + os dois blinds, que agem por último preflop
            atras = n + 1 - i
            out[nome] = _GW_POR_ATRAS.get(min(atras, _ATRAS_MAX_GW), 'UTG')
    _mapa_mesa_cache[n] = out
    return out

# Ordem de AÇÃO da primeira órbita preflop, no dialeto já normalizado por `_POS_NORM`.
# Blinds agem por ÚLTIMO preflop — por isso SB/BB no fim, e não no começo como no pós-flop.
_ORDEM_ACAO_PREFLOP = ('UTG', 'UTG+1', 'UTG+2', 'LJ', 'HJ', 'CO', 'BTN', 'SB', 'BB')
_IDX_ACAO_PREFLOP = {p: i for i, p in enumerate(_ORDEM_ACAO_PREFLOP)}


def _age_depois(hero_pos: str, vs_pos: str) -> bool:
    """O vilão age DEPOIS do hero na primeira órbita preflop?

    Serve para reconhecer o par estruturalmente impossível numa árvore raise-first: hero em
    UTG+1 "defendendo" um open do HJ, ou hero no SB "defendendo" um open do BB. Nenhum dos dois
    existe — em ambos hero já tinha agido, então só segue na mão por ter LIMPADO.

    Posição desconhecida responde False: na dúvida, não classifica.
    """
    i = _IDX_ACAO_PREFLOP.get(hero_pos)
    j = _IDX_ACAO_PREFLOP.get(vs_pos)
    return i is not None and j is not None and j > i


# Push/fold bucket → lista de pf_stack keys (em ordem de preferência)
_PUSHFOLD_BUCKET_STACK = {
    '10bb': ['12bb', '10bb'],   # 12bb é o máximo do bucket; fallback 10bb
    '14bb': ['15bb'],
    '20bb': ['20bb_pf'],        # só como último fallback para 20bb
}


def _norm_pos(position: str, n_players: int | None = None) -> str:
    """Normaliza nome de posição do pipeline/banco para chave do JSON v3 (9-max GW).

    Com `n_players`, pareia por JOGADORES ATRÁS (ver `_mapa_da_mesa`). Sem ele, assume que o nome
    já é do dialeto 9-max — é o único palpite honesto quando o tamanho da mesa não veio.
    """
    p = (position or '').upper()
    p = _POS_ALIAS.get(p, p)
    n = int(n_players or 0)
    if n >= 2:
        m = _mapa_da_mesa(n)
        if p in m:
            return m[p]
    return _POS_NORM.get(p, p)


def villain_open_range(position: str, stack_bb: float, n_players: int | None = None,
                       is_pko: bool = False) -> dict:
    """Range de ABERTURA (RFI) do villain numa posição, como {hand_canon: weight}
    para o cálculo de equity vs range (#27). weight = freq não-fold da mão (raise +
    allin) quando o GW traz hand_freqs; senão 1.0 por membership em raise/allin_hands.

    Usado quando o hero DEFENDE contra um open: o villain não tem mãos aleatórias,
    tem a RFI range daquela posição. Vazio ({}) se não há cobertura (cai no
    vs-random no caller). PKO usa a range PKO do estágio; senão a Classic."""
    pos = _norm_pos(position, n_players)
    bk_data = None
    if is_pko:
        _pko_bk, _stg, _lbl = _pko_ranges_for(stack_bb)
        if _pko_bk:
            bk_data = _pko_bk
    if bk_data is None:
        _bk = _balde_da_carta(stack_bb)
        if _bk is None:
            return {}
        bk_data = _load().get('ranges', {}).get(_bk, {})
    rfi = (bk_data.get('RFI') or {}).get(pos)
    if not rfi:
        return {}
    raise_hs = rfi.get('raise_hands', '') or rfi.get('hands', '')
    allin_hs = rfi.get('allin_hands', '')
    members = _expand_range(raise_hs) | _expand_range(allin_hs)
    if not members:
        return {}
    hand_freqs = rfi.get('hand_freqs', {}) or {}
    out: dict[str, float] = {}
    for h in members:
        hf = hand_freqs.get(h, {})
        if hf:
            w = sum(float(f) for code, f in hf.items()
                    if code == 'RAI' or (code.startswith('R') and code != 'F'))
            out[h] = w if w > 0 else 1.0
        else:
            out[h] = 1.0
    return out


def villain_reraise_range(villain_pos: str, hero_pos: str, stack_bb: float,
                          n_players: int | None = None, is_pko: bool = False) -> dict:
    """Range com que o villain 3-BETA contra um open do hero, como {hand_canon: weight}.

    ── Por que existe ─────────────────────────────────────────────────────────────────────────
    O `estimated_equity` do produto é medido **contra mão aleatória** sempre que o hero enfrenta
    mais de um raise: `pipeline.py` só injetava range no caso de open simples, com a justificativa
    "3bet/4bet têm ranges mais estreitas e ficam no vs-random". A consequência é o defeito que o
    coach apontou: AQo contra um 4-bet all-in exibia **64,4%** de equity — número medido contra
    outra coisa — e o card usava isso para abençoar o call.

    A range existe nas nossas cartas e é a MESMA que já usamos para gradear o villain: em
    `vs_RFI[opener][defender]`, o peso de cada mão nas famílias de aumento. Aqui ela é lida do
    ponto de vista do villain, que é quem 3-betou.

    Vazio (`{}`) quando não há cobertura — e aí o caller mantém o vs-random, que é o
    comportamento de hoje. **Nunca inventar range estreita**: equity contra range errada é pior
    que equity contra aleatória, porque parece precisa.
    """
    vil = _norm_pos(villain_pos, n_players)
    her = _norm_pos(hero_pos, n_players)
    bk_data = None
    if is_pko:
        _pko_bk, _stg, _lbl = _pko_ranges_for(stack_bb)
        if _pko_bk:
            bk_data = _pko_bk
    if bk_data is None:
        _bk = _balde_da_carta(stack_bb)
        if _bk is None:
            return {}
        bk_data = _load().get('ranges', {}).get(_bk, {})
    spot = ((bk_data.get('vs_RFI') or {}).get(her) or {}).get(vil)
    if not spot:
        return {}
    membros = _expand_range(spot.get('raise_hands', '') or '') | _expand_range(
        spot.get('allin_hands', '') or '')
    if not membros:
        return {}
    hand_freqs = spot.get('hand_freqs', {}) or {}
    out: dict[str, float] = {}
    for h in membros:
        hf = hand_freqs.get(h, {})
        if hf:
            w = sum(float(f) for code, f in hf.items()
                    if code == 'RAI' or (code.startswith('R') and code != 'F'))
            if w > 0:
                out[h] = w
        else:
            out[h] = 1.0
    return out


def _linha_do_jam(raises_faced: int, hero_was_aggressor: bool) -> Optional[str]:
    """Qual linha do preflop produziu este all-in: `open_jam`, `3bet_jam`, `4bet_jam` ou `None`.

    ── O erro que esta função existe para não deixar repetir ──────────────────────────────────
    `preflop_raises_faced` conta **raises de VILÃO** — o raise do próprio hero não entra, ele vira
    `hero_was_aggressor`. A primeira versão deste caminho leu o número sozinho e errou os dois
    lados, sempre na direção que ABSOLVE call ruim:

    | rf | hero abriu | linha real | o que eu usava | efeito |
    |---|---|---|---|---|
    | 1 | não | open-jam | `RFI[vilão]` | certo |
    | 1 | **sim** | **3-bet jam** | `RFI[vilão]` | range de ABERTURA, larga demais (83 decisões) |
    | 2 | não | open + 3-bet jam a frio | `vs_RFI[abridor][vilão]` | certo |
    | 2 | **sim** | **4-bet jam** | `vs_RFI` | range de 3-BET, larga demais (23 decisões) |

    Achado ao regerar o relatório do coach: o AQo dele (`QhAd UTG+2`, o caso #2) subiu de
    `marginal` para `standard` — nós abençoando exatamente o call que ele critica. O comentário
    dele dizia o que os dados não diziam: *"tem um 3-bet e um 4-bet. Esse 4-bet é muita força."*
    É 4-bet jam com `rf=2`, e eu gradeava pelo nó de 3-bet.

    **Não há nó de 4-bet jam em carta nenhuma**, então ali a resposta certa é `None` — vs-random,
    que é o comportamento antigo, e o G2 volta a rebaixar.
    """
    rf = int(raises_faced or 0)
    agg = bool(hero_was_aggressor)
    if rf == 1:
        return '3bet_jam' if agg else 'open_jam'
    if rf == 2:
        # A frio o hero não abriu: o vilão 3-betou por cima do open de um TERCEIRO, e o nó dele
        # continua sendo `vs_RFI[abridor][vilão]`. Com o hero tendo aberto, o que veio foi 4-bet.
        return '4bet_jam' if agg else '3bet_jam'
    return None


def _no_de_jam_do_vilao(villain_pos: str, hero_pos: str, stack_bb: float,
                        n_players: Optional[int], raises_faced: int,
                        hero_was_aggressor: bool = False):
    """`(depth, no)` do nó em que o VILÃO agiu com o jam no menu — ou `(None, None)`.

    A seleção espelha `_hu_analyze` e `_load_ring` de propósito. Um índice próprio aqui seria a
    quinta cópia de uma regra que já mora em quatro lugares, e a quinta divergiria calada.
    """
    mesa = int(n_players or 0)
    if mesa == 2:
        # `raises_faced` conta raises de VILÃO (o do hero vira `hero_was_aggressor`), então o
        # tipo do nó depende do PAR, não do número sozinho — ver `_linha_do_jam`.
        tipo = {'open_jam': 'ROOT', '3bet_jam': 'R2', '4bet_jam': 'SB_VS_3BET'}.get(
            _linha_do_jam(raises_faced, hero_was_aggressor) or '')
        # Em HU o ator do nó é fixo pela estrutura da mão: quem age primeiro é o SB, quem
        # responde ao open é o BB, quem responde ao 3-bet é o SB de novo. Se o vilão declarado
        # não é esse, a decisão não é a que o nó modela.
        if tipo is None or {'ROOT': 'SB', 'R2': 'BB', 'SB_VS_3BET': 'SB'}[tipo] != villain_pos:
            return None, None
        return _hu_no_mais_proximo(_load_hu().get(tipo) or {}, stack_bb)

    # Mesa cheia: só o nó de defesa contra UM open está indexado (`_ring_papeis` exige agressor),
    # então só o 3-bet jam tem carta. E aqui a mesa tem de ser EXATA — a política de "carta de
    # mesa vizinha absolve mas não acusa" não se transporta para uma range: uma range aproximada
    # não suaviza veredito, ela muda a equity, e move nos DOIS sentidos.
    if _linha_do_jam(raises_faced, hero_was_aggressor) != '3bet_jam':
        return None, None
    por_depth = _load_ring().get(('vs_rfi', villain_pos, hero_pos))
    if not por_depth:
        return None, None
    depth, no = _hu_no_mais_proximo(por_depth, stack_bb)
    if no is None or int(no.get('mesa') or 0) != mesa:
        return None, None
    return depth, no


def villain_jam_range(villain_pos: str, hero_pos: str, stack_bb: float,
                      n_players: Optional[int] = None, raises_faced: int = 2,
                      is_pko: bool = False, opener_pos: str = '',
                      hero_was_aggressor: bool = False) -> dict:
    """Range com que o villain vai de ALL-IN, como `{hand_canon: weight}`.

    ── Por que existe ─────────────────────────────────────────────────────────────────────────
    Enfrentando um jam, o produto media equity contra **mão aleatória**: `pipeline.py` excluía
    `facing_allin` da injeção de range de propósito, porque a carta `vs_RFI` modela um 3-bet DE
    TAMANHO e usar um nó pelo outro é precisão falsa. A saída correta nunca foi voltar ao
    aleatório — era ler o nó certo.

    ── Onde a range estava ────────────────────────────────────────────────────────────────────
    Em lugar nenhum novo. Ela é a coluna `allin` dos nós que já capturamos do GW, lida do lado de
    **quem jamou** em vez de quem responde. O fechamento das cinco famílias registrou esta metade
    como "bloqueada: exige a range de JAM, e push/fold é seção morta" — e a primeira parte estava
    certa quanto ao ARQUIVO de ranges (nenhuma chave de push/jam/shove, `_other_spots` vazia) e
    errada quanto ao DADO: 198 dos nós capturados oferecem jam, 192 têm mão jogando-o, 2.885
    pares (nó, mão) com frequência > 0. Mesmo formato da família 1 — o dado vinha no payload e
    ninguém o consumia.

    Vazio (`{}`) quando não há cobertura, e aí o caller mantém o comportamento de hoje.
    **Nunca inventar range estreita**: equity contra range errada é pior que contra aleatória,
    porque parece precisa.
    """
    if not is_pko:
        # A captura do GW é Classic. Em PKO ela não serve de substituta: com bounty a range de
        # jam ABRE, e emprestar a Classic estreitaria a range do vilão, inflaria a equity do hero
        # e absolveria call ruim — dano que o buraco de hoje não causa.
        depth, no = _no_de_jam_do_vilao(villain_pos, hero_pos, stack_bb, n_players, raises_faced,
                                        hero_was_aggressor)
        if no is not None:
            out: dict[str, float] = {}
            massa = {'allin': 0.0, 'raise': 0.0}
            for mao, acs in (no.get('maos') or {}).items():
                combos = _HU_COMBOS(mao)
                f = 0.0
                for rot, v in (acs or {}).items():
                    fam = _hu_familia_da_acao(rot, depth)
                    if fam in massa:
                        massa[fam] += combos * float(v.get('f') or 0)
                    if fam == 'allin':
                        f += float(v.get('f') or 0)
                if f > 0.005:
                    out[mao] = round(f, 4)
            # Dominância só no open-jam, pela mesma assimetria documentada em
            # `_jam_da_carta_vs_rfi`: ali recusar devolve o caller para a range de ABERTURA, uma
            # alternativa boa que exige barra alta; aqui, enfrentando 3-bet jam, a alternativa é
            # mão aleatória. Exigir dominância nos dois zerava o HU acima de 16bb — e a 25bb o
            # 3-bet jam do BB é ramo de estratégia, não cauda.
            if out and (_linha_do_jam(raises_faced, hero_was_aggressor) != 'open_jam'
                        or _jam_e_a_abertura(massa['allin'], massa['raise'])):
                if sum(_HU_COMBOS(m) for m in out) >= _MASSA_MINIMA_DE_JAM:
                    return out

    # ── A carta já publica as duas ranges de jam; faltava lê-las ───────────────────────────────
    # Em mesa cheia o nó capturado quase nunca responde: o índice do ring só tem `faces_squeeze`,
    # e first-in não é indexado por construção (`_ring_papeis` exige agressor). Mas o arquivo de
    # ranges publica `allin_hands` nos DOIS nós que interessam:
    #
    #   open-jam   → `RFI[pos]`                  — 25 das 72 entradas têm mão jamando
    #   3-bet jam  → `vs_RFI[opener][defender]`  — 183 das 324, e em 105 o jam domina
    #
    # A seção `push/fold` do arquivo está morta de fato (nenhuma chave, `_other_spots` vazia), e
    # foi por isso que esta metade da família 5 ficou registrada como bloqueada. Mas a push range
    # nunca esteve nela: estava na coluna de all-in dos nós que já consultamos todo dia.
    if int(n_players or 0) == 2:
        # **Mesa de 2 nunca consulta carta de mesa cheia.** É a regra que originou todo o caminho
        # HU: a revisão com o coach provou por oráculo externo que a carta ring mente em heads-up
        # (JJ no BB vs open é "call 100%" na 9-max e 3-BET 100% no GW HU, em toda profundidade).
        # Sem esta saída, um HU sem nó capturado cairia no `RFI[SB]` da 9-max — e só não caía por
        # acidente, porque o guarda de dominância barrava antes. Ou há nó HU, ou `{}` honesto.
        return {}
    linha = _linha_do_jam(raises_faced, hero_was_aggressor)
    if linha == 'open_jam':
        return _jam_da_carta_rfi(villain_pos, stack_bb, n_players, is_pko)
    if linha == '3bet_jam':
        # `vs_RFI[opener][defender]` — e o opener é quem ABRIU, que **nem sempre é o hero**. Com
        # o hero tendo aberto ele é o próprio abridor; num 3-bet jam pego a frio, o abridor é um
        # terceiro e vem de `preflop_opener`. Indexar pela posição do hero nos dois casos
        # descartava 57 das 80 decisões; indexar SÓ pelo `preflop_opener` sem olhar
        # `hero_was_aggressor` mandava 4-bet jam para este nó, que é largo demais.
        abridor = opener_pos or (hero_pos if hero_was_aggressor else '')
        if not abridor:
            return {}
        return _jam_da_carta_vs_rfi(villain_pos, abridor, stack_bb, n_players, is_pko)
    # `4bet_jam` e o resto caem aqui: não há nó de 4-bet jam em carta nenhuma, e servir o de
    # 3-bet no lugar infla a equity e absolve o call. Vazio devolve o vs-random, que é o
    # comportamento antigo — e com ele o rebaixamento do G2 volta a valer.
    return {}


def _jam_e_a_abertura(massa_jam: float, massa_raise: float) -> bool:
    """O jam só vira range quando ele É a agressão daquela profundidade, não a cauda dela.

    ── Por que este guarda existe ─────────────────────────────────────────────────────────────
    Sem ele o consumo da range de jam produz o pior resultado possível: uma range **estreita e
    confiante** feita do resíduo da carta. Medido no acervo: `7h7s UTG+2 vs SB a 29,8bb` saía com
    range de **10 mãos** e a equity pulava de 59,5% para 72,1% — 12,6 pontos, num fold que hoje é
    `gto_correct`. A 30bb o open-jam é fração residual da estratégia; condicionar nela é a
    precisão falsa contra a qual todo este arquivo está escrito.

    E há um motivo mais forte que o estatístico: a auditoria de 09/08 escolheu a range de
    ABERTURA de propósito, por ser "mais larga que a de jam, logo conservadora a favor do hero".
    Sem este guarda, ligar a range de jam reverteria calada uma decisão deliberada, e no sentido
    que ABSOLVE call ruim.

    O limiar não é inventado: é uma comparação dentro da própria fonte. Vale onde abrir É jamar,
    que é o regime raso — e casa com o que se vê na árvore do GW, onde abaixo de ~9bb a primeira
    decisão não oferece mais aumento dimensionado.

    **Os dois caminhos passam por aqui** (nó capturado e carta de RFI). Eram duas leituras da
    mesma regra, e regra em N lugares diverge calada no N+1.
    """
    return massa_jam >= massa_raise


def _bloco_de_ranges(stack_bb: float, is_pko: bool) -> dict:
    """O bloco de ranges da profundidade — PKO quando há, senão Classic. `{}` fora da janela.

    Fina de propósito: quem decide se o balde serve é `_balde_da_carta`, o MESMO seletor que
    `villain_open_range` e `villain_reraise_range` usam. Esta função só resolve o bloco.

    ── Nota de merge, 2026-08-10 ──────────────────────────────────────────────────────────────
    Duas frentes chegaram nesta necessidade no mesmo dia, por lados diferentes: a range de jam
    (`_stack_bucket` devolvia a carta de 10bb para 3,9bb e isso virou duas acusações falsas) e as
    ranges de open/re-raise (a mesma saturação, com 0,2bb recebendo a carta de 10bb). As duas
    escreveram um `_balde_da_carta`, com o MESMO nome e contratos diferentes — e o merge textual
    do git juntou as duas definições em silêncio, com a segunda vencendo. Os call sites da outra
    passariam um argumento só e estourariam `TypeError` em `villain_open_range`.

    Ficou um contrato só: `_balde_da_carta(stack_bb) -> rótulo | None` decide, esta resolve.
    """
    if is_pko:
        _pko_bk, _stg, _lbl = _pko_ranges_for(stack_bb)
        if _pko_bk:
            return _pko_bk
    balde = _balde_da_carta(stack_bb)
    if balde is None:
        return {}
    return _load().get('ranges', {}).get(balde, {})


# Massa mínima (em combos, de 1326) para uma range de jam valer como leitura. 60 combos são
# ~10 mãos canônicas. Ver o comentário do piso em `_jam_do_spot` para o número medido por trás.
_MASSA_MINIMA_DE_JAM = 60


def _jam_do_spot(spot: Optional[dict], exigir_dominancia: bool = True) -> dict:
    """`{hand_canon: freq_de_RAI}` de um spot da carta — `{}` se ninguém jama ali.

    Lê a MESMA estrutura que `villain_open_range` e `villain_reraise_range`, mudando só o filtro:
    lá o peso é toda ação não-fold, aqui é só `RAI`. Serve tanto o `RFI[pos]` (open-jam) quanto o
    `vs_RFI[opener][defender]` (3-bet jam) porque os dois têm o mesmo formato — e um extrator por
    nó seria a segunda cópia de uma leitura que já diverge fácil.
    """
    if not spot:
        return {}
    massa = lambda hs: sum(_HU_COMBOS(m) for m in _expand_range(hs or ''))
    mj = massa(spot.get('allin_hands'))
    mr = massa(spot.get('raise_hands') or spot.get('hands'))
    if exigir_dominancia and not _jam_e_a_abertura(mj, mr):
        return {}
    # ── Piso de suporte ────────────────────────────────────────────────────────────────────────
    # Range estreita demais não é leitura, é ruído com aparência de precisão — e a DIREÇÃO do
    # erro decide que ele importa: range estreita puxa a equity para baixo, o que absolve fold e
    # **condena call**, que é o lado onde acusação nova nasce. Medido nas 57 decisões de 3-bet
    # jam do acervo, a distribuição é limpa: 21 a 33 mãos no corpo e um único caso de **5 mãos**
    # (`AcTs UTG+2 vs SB a 27,4bb`, −24,6 pontos de equity). O piso é julgamento meu, escolhido
    # abaixo do corpo e acima do caso solto; o que ele não é é limiar de conveniência.
    if mj < _MASSA_MINIMA_DE_JAM:
        return {}
    hand_freqs = spot.get('hand_freqs', {}) or {}
    out: dict[str, float] = {}
    for h in _expand_range(spot.get('allin_hands', '') or ''):
        f = float((hand_freqs.get(h) or {}).get('RAI') or 0)
        # Sem `hand_freqs` a carta só diz "esta mão está na range de all-in", sem frequência —
        # peso 1.0, o mesmo que `villain_open_range` faz na mesma situação.
        out[h] = round(f, 4) if f > 0.005 else (1.0 if not hand_freqs.get(h) else 0.0)
    return {h: w for h, w in out.items() if w > 0}


def _jam_da_carta_rfi(pos_vilao: str, stack_bb: float, n_players: Optional[int],
                      is_pko: bool) -> dict:
    """Open-jam: o vilão abriu de all-in. O nó dele é a própria RFI da posição."""
    bk = _bloco_de_ranges(stack_bb, is_pko)
    return _jam_do_spot((bk.get('RFI') or {}).get(_norm_pos(pos_vilao, n_players)))


def _jam_da_carta_vs_rfi(pos_vilao: str, pos_opener: str, stack_bb: float,
                         n_players: Optional[int], is_pko: bool) -> dict:
    """3-bet jam: alguém abriu e o vilão respondeu de all-in.

    O nó é `vs_RFI[opener][defender]` — o abridor manda no primeiro índice, o vilão que 3-betou é
    o defender. É a MESMA entrada que `villain_reraise_range` consulta e na mesma ordem; a
    diferença é o filtro, que aqui fica só no all-in em vez de somar todas as famílias de aumento.
    """
    bk = _bloco_de_ranges(stack_bb, is_pko)
    spot = ((bk.get('vs_RFI') or {}).get(_norm_pos(pos_opener, n_players)) or {}).get(
        _norm_pos(pos_vilao, n_players))
    # ── Aqui a barra é MENOR que no open-jam, e a razão é a alternativa ────────────────────────
    # No open-jam, recusar a range de jam devolve o caller para `villain_open_range` — uma range
    # real, escolhida de propósito por ser conservadora. Trocá-la exige limpar uma barra alta.
    # Enfrentando um 3-bet jam o caller não tem para onde cair: hoje é **mão aleatória**. Uma
    # range do nó CERTO ganha do aleatório mesmo sem dominar a agressão, e exigir dominância aqui
    # descartaria 3 dos 9 nós medidos com share de 0,42 a 0,48 — 3-bet jam a 20-25bb não é cauda
    # de estratégia, é ramo inteiro. O que continua barrado é o nó sem all-in nenhum.
    return _jam_do_spot(spot, exigir_dominancia=False)


def _canonical_open_bb(bk_data: dict, opener_pos: str) -> Optional[float]:
    """Tamanho de open canônico do GTO p/ a posição do opener, em bb — lido do código
    de sizing (R{x}) modal na RFI do opener (ex.: 'R2.1' → 2.1bb). None se o opener
    abre só jam (RAI, sem R-code) ou sem cobertura. Usado p/ detectar open off-tree
    (vilão abriu maior que o GTO) e não punir o fold de defesa como crítico (#23)."""
    rfi = (bk_data.get('RFI') or {}).get(opener_pos)
    if not isinstance(rfi, dict):
        return None
    counts: dict[str, int] = {}
    for hf in (rfi.get('hand_freqs') or {}).values():
        for code in hf:
            if code.startswith('R') and code != 'RAI':
                counts[code] = counts.get(code, 0) + 1
    if not counts:
        return None
    code = max(counts, key=counts.get)   # R-code modal (ex.: 'R2.1')
    try:
        return float(code[1:])
    except (ValueError, IndexError):
        return None


def raise_to_bb_from_node(node: dict, hero_hand_type: str | None = None) -> float | None:
    """TAMANHO do raise deste nó, em bb — o código de ação já carrega o sizing ('R2.1' = raise
    para 2,1bb) e o parser o descartava (`code.startswith('R')` → só 'raise').

    Prefere o código da MÃO do hero; se ela não raiseia, cai no código modal do nó. Medição
    sobre o JSON inteiro: **0% dos 1.036 nós têm mais de um tamanho de raise**, então nó e mão
    concordam — cada spot tem UM tamanho GTO, não uma mistura de sizings. Por isso o produto
    ENSINA o tamanho no feedback em vez de perguntá-lo: com um só tamanho por nó, perguntar
    viraria decoreba de tabela.
    """
    if not isinstance(node, dict):
        return None
    hfs = node.get('hand_freqs') or {}

    def _size(code: str):
        try:
            return float(code[1:])
        except (ValueError, IndexError):
            return None

    if hero_hand_type and hero_hand_type in hfs:
        for code in hfs[hero_hand_type]:
            if code.startswith('R') and code != 'RAI':
                s = _size(code)
                if s:
                    return s
    counts: dict[str, int] = {}
    for hf in hfs.values():
        for code in hf:
            if code.startswith('R') and code != 'RAI':
                counts[code] = counts.get(code, 0) + 1
    if not counts:
        return None
    return _size(max(counts, key=counts.get))


# Open ≥ este fator do canônico = off-tree "maior que o GTO" (ex.: 2bb→2.8bb+).
_OPEN_OVERSIZE_FACTOR = 1.4

# Aposta que come esta fração do stack efetivo é JAM na prática, mesmo sem o histórico dizer
# all-in. Era `0.65` literal em dois pontos do roteador heads-up; virou constante porque o mesmo
# limiar passou a decidir cobertura em mesa cheia — três cópias divergem calado.
_FRACAO_QUE_E_JAM = 0.65


def _raise_declarado_bb(node: dict) -> Optional[float]:
    """Tamanho do ÚLTIMO aumento da linha que o nó DECLARA, em bb — None se ele fecha em all-in
    ou não declara nada.

    O nó do GW carrega a própria linha em `preflop_actions`: `R2-F-F-F-F-F-F-F` é "o opener
    aumentou para 2bb e todos foldaram", `R2-R6` é "open 2bb, 3-bet para 6bb". Isso é o sistema
    DECLARANDO o tamanho que ele modela — melhor que `_canonical_open_bb`, que deduz o tamanho
    pelo código R modal das mãos do opener e pode divergir do nó realmente servido.

    Varredura dos 324 nós `vs_RFI` do JSON: TODOS modelam open pequeno (2 a 3,5bb) e NENHUM
    modela open-jam. Por isso enfrentar all-in em mesa cheia não tem carta — tem que calar.
    """
    if not isinstance(node, dict):
        return None
    toks = [t for t in (node.get('preflop_actions') or '').split('-') if t.startswith('R')]
    if not toks or toks[-1] == 'RAI':
        return None
    try:
        return float(toks[-1][1:])
    except (ValueError, IndexError):
        return None


def _direcao_do_tamanho(node: dict, to_bb: float) -> str:
    """Como a aposta enfrentada (`to_bb`) se compara ao tamanho que o nó modela.

    Devolve `'dentro'`, `'maior'`, `'menor'` ou `'indeterminado'` (nó sem tamanho declarado ou
    `to_bb` ausente — não dá para afirmar nada sobre um nó cujo tamanho não se conhece).

    Tolerância = `_OPEN_OVERSIZE_FACTOR` para os dois lados, a mesma régua que o projeto já usa
    para chamar um open de off-tree (`open_size_mismatch`, logo abaixo). Uma régua só: dois
    limiares para o mesmo conceito divergem calados.

    Nota de escopo: o ramo `R2` do heads-up (BB vs open) guarda o teto histórico de 4,5bb em vez
    desta função. Apertá-lo para 2×1,4=2,8bb tiraria a cobertura de todo open de 3bb, que é
    comum — é uma medição a fazer, não um bug a consertar de passagem.
    """
    tam = _raise_declarado_bb(node)
    if tam is None or not to_bb or float(to_bb) <= 0:
        return 'indeterminado'
    to = float(to_bb)
    if to > tam * _OPEN_OVERSIZE_FACTOR:
        return 'maior'
    if to < tam / _OPEN_OVERSIZE_FACTOR:
        return 'menor'
    return 'dentro'


def _tamanho_cabe_no_no(node: dict, to_bb: float) -> bool:
    """Atalho booleano de `_direcao_do_tamanho` — `'indeterminado'` conta como NÃO cabe."""
    return _direcao_do_tamanho(node, to_bb) == 'dentro'


# Ações que continuam na mão. Uma recomendação DEFENSIVA (só fold) e uma AGRESSIVA reagem em
# sentidos opostos a um erro de preço — é isso que `_veredito_sobrevive_ao_tamanho` explora.
_ACOES_QUE_DEFENDEM = frozenset({'call', 'raise', 'jam', 'allin', 'shove'})
_ACOES_AGRESSIVAS = frozenset({'raise', 'jam', 'allin', 'shove'})


def _defesa_e_de_valor(hand_freq: dict | None, rec: list | None) -> bool:
    """A carta defende esta mão sobretudo AGREDINDO (3-bet/jam pesam mais que o call)?

    Regra do #23, que morava inline no bloco de `open_size_mismatch`. Serve para decidir se um
    fold é DEFENSÁVEL contra um open maior, e só para isso: ela NÃO é criterio para manter uma
    acusação viva — `22` a 23bb é jam pela frequência e a margem de EV dele sobre o fold é de
    0,38bb, ou seja, o open maior pode virar a resposta. Quem decide isso é
    `_veredito_sobrevive_ao_tamanho`, com a margem medida.

    Preferir a freq EXATA da mão; sem ela, cair na presença de raise/jam no `rec`.
    """
    if hand_freq:
        return (float(hand_freq.get('raise', 0) or 0) + float(hand_freq.get('allin', 0) or 0)
                > float(hand_freq.get('call', 0) or 0))
    return any(str(a).lower() in _ACOES_AGRESSIVAS for a in (rec or []))


def _veredito_sobrevive_ao_tamanho(direcao: str, rec: list,
                                   margem_bb: float | None = None,
                                   excesso_bb: float = 0.0) -> bool:
    """O veredito deste nó continua válido mesmo o tamanho enfrentado não sendo o modelado?

    Argumento UNILATERAL, no espírito do teto computado de equity: mantendo a range do vilão
    fixa, subir o preço só pode tornar o FOLD mais certo, e baixá-lo só pode tornar a DEFESA mais
    certa. Então:

      preço MAIOR que o do nó   → a carta que manda FOLDAR continua valendo (a resposta não pode
                                  virar defesa a um preço pior); a que manda DEFENDER pode virar
                                  fold → sem gabarito.
      preço MENOR que o do nó   → o espelho.

    Isto não prova que a carta acerta; prova só que o erro de preço não anda contra ela. Serve
    exatamente para não trocar uma resposta — trocar é o dano que o bug não causava.

    A EXCEÇÃO, com o número no lugar do palpite. Suprimir tudo apagaria acusações certas: foldar
    AA a um open de 3,3bb não é defensável por o open ter vindo maior, e essa acusação vale mais
    que a regra. Mas "é mão de value" não serve de criterio — pela frequência, `22` que o nó jama
    a 23bb entra no mesmo grupo de AA, e acusar quem folda 22 contra um open de 4,7bb seria a
    falsa condenação que este guarda existe para evitar (medido: a régua de frequência devolvia
    14 acusações, 12 delas assim).

    O critério é o oráculo de EV do próprio repositório (`leaklab_gto_evs.json`): a melhor ação
    vale `margem_bb` a mais que o fold, e defender no preço real custa no máximo `excesso_bb`
    (= quanto o open passou do que o nó modela) a mais do que defender no preço modelado. Se a
    margem cobre o excesso, o fold continua sendo pior — a resposta não pode ter virado. Medido no
    nó CO→BB a 30bb com excesso de 1,3bb: AA 11,43 · KK 8,58 · QQ 6,89 · AKs 5,75 · 99 3,18
    sobrevivem; 75o 0,14 não. É COTA INFERIOR de segurança, não estimativa: o limite ignora que um
    pote maior também paga mais quando a mão ganha, então erra para o lado de calar.
    """
    if direcao in ('dentro', 'indeterminado'):
        return True
    defende = any(str(a).lower() in _ACOES_QUE_DEFENDEM for a in (rec or []))
    if direcao == 'maior':
        if not defende:
            return True
        return margem_bb is not None and float(margem_bb) > float(excesso_bb or 0.0)
    return defende


def _attach_ev_loss(base: dict) -> None:
    """Anexa ev_loss_bb à análise preflop em QUALQUER caminho de saída (inclui o
    push/fold que retorna cedo). Só Classic (PKO terá overlay próprio); NULL
    honesto sem cobertura. Lê tudo do próprio base (pos/vs já normalizados)."""
    if not base.get('available') or base.get('pko') or base.get('ev_loss_bb') is not None:
        return
    elb, esrc = _ev_loss_bb(base.get('stack_bucket'), base.get('scenario'),
                            base.get('position'), base.get('vs_position') or '',
                            base.get('hand_type'), base.get('action_taken'))
    base['ev_loss_bb'] = elb
    if esrc:
        base['ev_loss_source'] = esrc


def _normalize_facing_allin(base: dict, action_taken: str) -> None:
    """Enfrentando um ALL-IN, não se pode AUMENTAR — a linha agressiva do GTO (jam/shove/
    raise) se executa CHAMANDO. Então: (a) a recomendação 'jam'/'raise' vira 'call'; (b) o
    CALL do hero (ou um shove redundante) é CORRETO se a mão está no range agressivo (= o
    jam). Fora do range (deveria foldar), pagar segue leak. Corrige o falso 'Desvio Crítico'
    em call vs all-in (mão 113: AKs paga o 4-bet shove = a jogada agressiva do GTO)."""
    if not base.get('available'):
        return
    rec = base.get('recommended_actions') or []
    if not any(a in ('jam', 'shove', 'allin', 'all-in', 'raise') for a in rec):
        return  # GTO não manda agredir (ex.: fold) — pagar o all-in segue leak
    base['recommended_actions'] = ['call']          # facing all-in: a agressão = call

    # Consistência do card: as FREQUÊNCIAS exibidas ("Como GTO joga X") também têm que
    # falar "call", não "allin"/"raise". Vs um all-in, jam/raise se executam CHAMANDO —
    # senão o card mostra "GTO recomenda Call" ao lado de "Allin 99.9%" (parece bug).
    # Dobra allin+raise dentro de call, tanto na freq exata da mão quanto nos agregados.
    hf = base.get('hand_freq')
    if isinstance(hf, dict):
        hf['call'] = round(hf.get('call', 0.0) + hf.get('allin', 0.0) + hf.get('raise', 0.0), 4)
        hf['allin'] = 0.0
        hf['raise'] = 0.0
    for _agg in ('allin_pct', 'raise_pct'):
        if base.get(_agg):
            base['call_pct'] = round(float(base.get('call_pct', 0.0) or 0.0) + float(base.get(_agg) or 0.0), 4)
            base[_agg] = 0.0

    if (action_taken or '').lower() in ('call', 'jam', 'shove', 'allin', 'all-in'):
        base['action_quality'] = 'correct'
        base['in_range'] = True
        base['ev_loss_bb'] = 0.0


_NEVER_FOLD_VS_3BET = {'AA', 'KK'}


def _soften_mixed_3bet_quality(base: dict, action_taken: str) -> None:
    """vs_3bet/vs_4bet/squeeze/faces_squeeze são spots MISTOS — call/raise/fold são todos
    parte do range GTO. O modelo dá UMA ação recomendada → qualquer alternativa razoável
    virava `major_leak` → gto_critical ("Desvio Crítico" indevido em decisão mista, ex.:
    foldar TJs a um 4-bet, flatar AK vs 3-bet). Rebaixa major_leak → `gto_minor_deviation`
    nesses cenários (mão no range). Mantém crítico só p/ foldar AA/KK a um 3-bet (nunca-fold)."""
    if base.get('action_quality') != 'major_leak' or not base.get('in_range'):
        return
    if base.get('scenario') not in ('vs_3bet', 'vs_4bet', 'squeeze', 'faces_squeeze'):
        return
    if ((action_taken or '').lower() == 'fold' and base.get('scenario') == 'vs_3bet'
            and base.get('hand_type') in _NEVER_FOLD_VS_3BET):
        return  # foldar AA/KK a um 3-bet segue crítico
    base['action_quality'] = 'gto_minor_deviation'


_ARGS_POSICIONAIS = ('position', 'hero_hand_type', 'stack_bb', 'action_taken')


def _preenche_buraco_com_ring(base: dict, args: tuple, kwargs: dict) -> None:
    """Carta de mesa cheia do GW, SÓ onde não há gabarito.

    O gatilho é `available=False` com `pairing_uncovered`: 149 decisões do acervo caem aí porque
    o par (hero, 3-bettor) nunca foi semeado. Onde já existe carta, este caminho não encosta —
    trocar a fonte mexeria em veredito hoje correto sem experimento que diga qual está certa.

    Mesa de 2 nunca entra aqui: HU tem porta própria, e carta de mesa cheia em heads-up é o
    defeito que originou toda esta frente.
    """
    if base.get('available') or base.get('coverage_reason') != 'pairing_uncovered':
        return
    p = dict(zip(_ARGS_POSICIONAIS, args))
    p.update(kwargs)
    mesa_decisao = int(p.get('n_players') or 0)
    if mesa_decisao == 2:
        return
    cenario = base.get('scenario')
    hero, vilao = p.get('position'), p.get('vs_position')
    if cenario not in ('faces_squeeze', 'vs_rfi') or not hero or not vilao:
        return
    por_depth = _load_ring().get((cenario, hero, vilao))
    if not por_depth:
        return
    depth, no = _hu_no_mais_proximo(por_depth, float(p.get('stack_bb') or 0))
    if no is None:
        return

    # ── mesa da carta x mesa da decisão ───────────────────────────────────────────────────────
    # No GW gratuito só existe 8-max, e o acervo real está espalhado: das 104 decisões, 41 são de
    # mesa de 8, 30 de 7, 16 de 6, 11 de 9. Carta de outra mesa é outro regime — a mesma família
    # do defeito que originou tudo isto. Mas a assimetria decide a política: hoje estas decisões
    # são NULL, então absolver com carta aproximada é aditivo, e ACUSAR CRITICAMENTE com ela
    # seria dano que o buraco não causava.
    #   distância 0 → gradua normal
    #   distância 1 → gradua, marcado, e o veredito duro é rebaixado
    #   distância 2+ → não usa (6-max com carta de 8-max muda a pressão de posição de verdade)
    dist = abs(int(no.get('mesa') or 0) - mesa_decisao) if mesa_decisao else 99
    if dist > 1:
        return

    _grade_por_no_capturado(base, no, depth, p.get('hero_hand_type') or '',
                            p.get('action_taken') or '',
                            fonte='gw_ring_har' if dist == 0 else 'gw_ring_har_aprox')
    if not base.get('available'):
        return
    base.pop('coverage_reason', None)
    if dist == 1:
        base['ring_mesa_aproximada'] = {'carta': no.get('mesa'), 'decisao': mesa_decisao}
        if base.get('action_quality') == 'major_leak':
            base['action_quality'] = 'gto_minor_deviation'


def analyze_preflop(*args, **kwargs) -> dict:
    """Análise GTO preflop + ev_loss_bb (#24). Wrapper fino sobre o _impl pra
    anexar o EV em todos os returns (RFI/push-fold/vs_rfi/3bet/etc)."""
    facing_allin = bool(kwargs.pop('facing_allin', False))
    # O pop acima alimenta o _normalize_facing_allin do wrapper, mas o caminho HU (dentro
    # do impl) tambem precisa da flag — sem ela, defesa vs open-jam seria gradeada pelo no
    # R2 de open pequeno, que e o defeito que o caminho HU existe para matar.
    kwargs['facing_allin'] = facing_allin
    base = _analyze_preflop_impl(*args, **kwargs)
    _preenche_buraco_com_ring(base, args, kwargs)
    _attach_ev_loss(base)
    _act = kwargs.get('action_taken') or (args[3] if len(args) > 3 else '')
    if facing_allin:
        _normalize_facing_allin(base, _act)
    _soften_mixed_3bet_quality(base, _act)
    return base


# ── HEADS-UP: cartas capturadas do GTO Wizard via HAR (docs/hu_ranges_har.json) ────────────────
# A revisao com o coach provou por oraculo externo que a carta RING mentia em HU: JJ no BB vs
# open era "call 100%" na 9-max e 3-BET 100% no GW HU, em TODA profundidade de 10 a 60bb. Em mesa
# de 2, a carta ring nunca e consultada: ou ha no HU capturado, ou null honesto (`hu_uncovered`).
_HU_PATH = os.path.join(os.path.dirname(__file__), '..', 'docs', 'hu_ranges_har.json')
_hu_cache = None


def _load_hu() -> dict:
    global _hu_cache
    if _hu_cache is None:
        try:
            with open(_HU_PATH, encoding='utf-8') as f:
                bruto = json.load(f)
        except Exception:
            bruto = {}
        nos: dict = {}
        for _gt, mapa in (bruto or {}).items():
            for chave, no in mapa.items():
                d_str, node = chave.split('|', 1)
                # O NOME do no carrega o sizing da sessao (R2-R4.5 num depth, R2-R5.5 noutro).
                # Quem roteia precisa do TIPO, nao do nome.
                if node == 'ROOT':
                    tipo = 'ROOT'
                elif node == 'C':
                    tipo = 'BB_VS_LIMP'
                elif '-' not in node:
                    tipo = 'R2'                       # BB vs open
                else:
                    partes = node.split('-')
                    if len(partes) == 2:
                        tipo = 'SB_VS_3BET_JAM' if partes[1] == 'RAI' else 'SB_VS_3BET'
                    elif len(partes) == 3 and partes[2] == 'RAI':
                        tipo = 'BB_VS_4BET_JAM'
                    else:
                        continue                      # linha mais funda: fora do modelo
                nos.setdefault(tipo, {})[float(d_str)] = no
        _hu_cache = nos
    return _hu_cache


# ── MESA CHEIA: cartas do GTO Wizard (docs/ring_ranges_har.json) ──────────────────────────────
#
# Preenche BURACO, não substitui carta existente. Onde já há cobertura, trocar a fonte mexeria em
# veredito hoje correto sem experimento que diga qual das duas está certa — e o dano seria de um
# tipo que o gap não causa. Promover o GW a autoritativo em ring é decisão separada e medível.

_RING_PATH = os.path.join(os.path.dirname(__file__), '..', 'docs', 'ring_ranges_har.json')
_ring_cache = None

# Ordem de ação da primeira órbita. As linhas que capturamos vivem todas nela.
_ORDEM_RING = {
    8: ['UTG', 'UTG+1', 'LJ', 'HJ', 'CO', 'BTN', 'SB', 'BB'],
    9: ['UTG', 'UTG+1', 'UTG+2', 'LJ', 'HJ', 'CO', 'BTN', 'SB', 'BB'],
    6: ['LJ', 'HJ', 'CO', 'BTN', 'SB', 'BB'],
}


def _ring_papeis(node: str, mesa: int, ator: str):
    """Do nome do nó (`F-F-F-F-R2-F-R6.5`) para os papéis: quem abriu, quem 3-betou, e o cenário.

    O i-ésimo token é o i-ésimo jogador na ordem de ação. É derivação, e derivação já nos custou
    caro — por isso o resultado é CONFERIDO contra o `ator` que o payload declara: se a posição
    que a contagem diz que age não for a que o GW diz que está agindo, o nó é descartado em vez
    de indexado torto. Duas fontes independentes precisam concordar.
    """
    ordem = _ORDEM_RING.get(int(mesa or 0))
    if not ordem or not node:
        return None
    tokens = [t for t in node.split('-') if t]
    if len(tokens) >= len(ordem):
        return None                                   # passou da primeira órbita: fora do modelo
    agressores = [ordem[i] for i, t in enumerate(tokens) if t.startswith('R')]
    if ordem[len(tokens)] != ator:
        return None                                   # a contagem e o payload discordam
    if len(agressores) == 1:
        return {'abriu': agressores[0], 'vilao': agressores[0], 'cenario': 'vs_rfi'}
    if len(agressores) == 2:
        # Hero ainda não agiu, então ele não é o abridor: é defesa contra open + 3-bet.
        return {'abriu': agressores[0], 'vilao': agressores[1], 'cenario': 'faces_squeeze'}
    return None


def _load_ring() -> dict:
    """{(cenario, hero, vilao): {depth: no}} — vazio enquanto não houver captura de mesa cheia."""
    global _ring_cache
    if _ring_cache is None:
        try:
            with open(_RING_PATH, encoding='utf-8') as f:
                bruto = json.load(f)
        except Exception:
            bruto = {}
        idx: dict = {}
        for _gt, mapa in (bruto or {}).items():
            for chave, no in (mapa or {}).items():
                try:
                    d_str, node = chave.split('|', 1)
                    papeis = _ring_papeis(node, no.get('mesa'), no.get('ator'))
                    if not papeis:
                        continue
                    k = (papeis['cenario'], no['ator'], papeis['vilao'])
                    idx.setdefault(k, {})[float(d_str)] = no
                except Exception:
                    continue
        _ring_cache = idx
    return _ring_cache


def _hu_no_mais_proximo(por_depth: dict, stack_bb: float):
    """No de profundidade mais proxima — ou None quando a distancia RELATIVA passa da janela.
    Um jogador a 5bb nao pode ser gradeado pela carta de 10bb: melhor null honesto que carta de
    outra profundidade (e o mesmo principio que derrubou a carta ring em HU)."""
    if not por_depth:
        return None, None
    # Distancia RELATIVA, nao absoluta: com nos em {10, 25} e stack 17, o absoluto escolhe 10
    # (dist 7 < 8) que REPROVA no guarda de 40%, enquanto 25 passaria — e o caso 73 (A5s SB
    # first-in a 17bb) caia em null indevido. 7bb de distancia a 10bb e outra estrategia; 8bb a
    # 25bb e a mesma familia.
    d = min(por_depth, key=lambda x: abs(x - stack_bb) / max(x, stack_bb, 1e-9))
    # Janela de 25%, nao 40%. A primeira versao usou 40% e a amostragem do acervo pegou o dano:
    # SB a 14,8bb gradeado pelo no de 10bb — outro REGIME (a 10bb o SB e jam/limp; a 15bb existe
    # raise normal), e um AJo foi acusado por min-raisar "em vez de jamar". Fronteira de regime
    # e onde profundidade vizinha mais mente; melhor null honesto ate capturar o no certo.
    #
    # A regra mora em `_profundidade_compativel` desde 09/08, porque DOIS caminhos chegaram nela
    # no mesmo dia, por lados diferentes: o seletor de BALDE das ranges de vilao (`_stack_bucket`
    # satura nas duas pontas e entregava a carta de 10bb para 0,2bb) e o consumo da range de JAM.
    # Uma janela, quatro consumidores.
    if not _profundidade_compativel(d, stack_bb):
        return None, None
    return d, por_depth[d]


def _hu_familia_da_acao(rotulo: str, depth: float) -> str:
    t = rotulo.split()[0]
    if t == 'FOLD':
        return 'fold'
    if t in ('CALL', 'CHECK'):
        # CHECK aparece no no de BB vs limp. Sem este ramo ele caia no parser de betsize e
        # virava 'raise' — check gradeado como agressao.
        return 'call'
    try:
        bs = float(rotulo.split()[1])
    except Exception:
        bs = 0.0
    return 'allin' if bs >= depth - 1.0 else 'raise'


_HU_COMBOS = lambda m: 6 if len(m) == 2 else (4 if m.endswith('s') else 12)


def _hu_analyze(base: dict, pos: str, hero_hand_type: str, stack_bb: float, action_taken: str,
                facing_raises: int, hero_was_aggressor: bool, facing_limp: bool,
                facing_to_bb: float, facing_allin: bool) -> dict:
    dados = _load_hu()
    base['scenario'] = 'hu_uncovered'

    node = None
    _to = float(facing_to_bb or 0)
    _raises = int(facing_raises or 0)
    if (pos == 'SB' and not hero_was_aggressor and _raises == 0 and not facing_limp):
        node, base['scenario'] = 'ROOT', 'hu_rfi'
    elif pos == 'BB' and not hero_was_aggressor and _raises == 0 and facing_limp:
        node, base['scenario'] = 'BB_VS_LIMP', 'hu_bb_vs_limp'
    elif pos == 'SB' and hero_was_aggressor and _raises >= 1:
        # SB abriu e levou 3-bet. Sao DOIS nos distintos e o tamanho decide qual: `R2-Rx` para
        # 3-bet pequeno, `R2-RAI` para jam (capturado em 07/08, 10-40bb). Gradear jam pelo no de
        # 3-bet pequeno seria o defeito da carta ring com outra roupa.
        if facing_allin or _to >= float(stack_bb) * _FRACAO_QUE_E_JAM:
            node, base['scenario'] = 'SB_VS_3BET_JAM', 'hu_vs_3bet_jam'
        else:
            node, base['scenario'] = 'SB_VS_3BET', 'hu_vs_3bet'
    elif pos == 'BB' and hero_was_aggressor and _raises >= 2 and (
            facing_allin or _to >= float(stack_bb) * _FRACAO_QUE_E_JAM):
        node, base['scenario'] = 'BB_VS_4BET_JAM', 'hu_vs_4bet'
    elif (pos == 'BB' and not hero_was_aggressor and _raises == 1
            and not facing_allin and _to <= 4.5):
        # R2 modela defesa vs open pequeno. Open-jam (facing_allin) e opens gigantes ficam FORA:
        # gradear vs o no errado foi exatamente o defeito que este caminho substitui.
        node, base['scenario'] = 'R2', 'hu_vs_rfi'

    if node is None:
        base['coverage_reason'] = 'hu_uncovered'
        return base

    depth, no = _hu_no_mais_proximo(dados.get(node) or {}, float(stack_bb))
    if no is None:
        base['coverage_reason'] = 'hu_uncovered'
        return base

    # ── O nó de 3-bet modela UM tamanho, e o roteador acima só separava jam de não-jam ────────
    # `SB_VS_3BET` a 40bb é `R2-R6`: a única opção de pagamento dentro dele é CALL 6. Um 3-bet real
    # de 15 ou 25bb era gradeado por essa estratégia, com pot odds de outro mundo (pagar 6 exige
    # ~33% de equity; pagar 25 exige ~42%). Foldar QTo a um 3-bet de 25bb saía `gto_critical` com
    # "GTO recomenda Call", e a 26,5bb — 1,5bb a mais, agora acima do limiar de jam — o MESMO fold
    # virava `correct`. Descontinuidade no mesmo spot.
    #
    # O guarda de tamanho já existia no ramo IRMÃO (BB vs open, `_to <= 4.5`), com o comentário
    # "gradear vs o no errado foi exatamente o defeito que este caminho substitui". Faltava aqui.
    if node == 'SB_VS_3BET' and not _tamanho_cabe_no_no(no, _to):
        base['coverage_reason'] = 'hu_uncovered'
        base['scenario'] = 'hu_uncovered'
        return base

    return _grade_por_no_capturado(base, no, depth, hero_hand_type, action_taken,
                                   fonte='gw_hu_har')


def _EV_MINOR_BB() -> float:
    """Limiar de EV desprezivel. **Fonte unica**: o mesmo `_PREFLOP_EV_MINOR_BB` (0,12bb) que o
    motor ja usa desde a recalibracao com o coach (#27). Import tardio so para nao criar ciclo."""
    try:
        from leaklab.decision_engine_v11 import _PREFLOP_EV_MINOR_BB
        return float(_PREFLOP_EV_MINOR_BB)
    except Exception:
        return 0.12


def _perda_de_ev_da_carta(acs: dict, depth: float, fam: str):
    """Quanto a acao jogada perde para a melhor da carta, em bb. None = a carta nao diz.

    Sai do `evs` que o GW publica para TODA acao, inclusive as de frequencia zero — o dado que o
    importador descartava ate 07/08. Sem ele, o motor sabia com que frequencia cada acao aparece
    e nao sabia quanto custa escolher outra.
    """
    por_fam: dict = {}
    for rot, v in (acs or {}).items():
        ev = v.get('ev')
        if ev is None:
            continue
        f = _hu_familia_da_acao(rot, depth)
        por_fam[f] = max(por_fam.get(f, float('-inf')), float(ev))
    if len(por_fam) < 2 or fam not in por_fam:
        return None
    return round(max(por_fam.values()) - por_fam[fam], 4)


def _grade_por_no_capturado(base: dict, no: dict, depth: float, hero_hand_type: str,
                            action_taken: str, fonte: str) -> dict:
    """Gradua uma acao contra um no capturado do GW. **Porta unica**: HU e mesa cheia usam esta.

    A alternativa era o caminho de ring reimplementar frequencia, adjacencia raise/jam e faixas de
    qualidade — quatro copias de regra que ja moram aqui, e a quinta divergiria calada.
    """
    acs = (no.get('maos') or {}).get(hero_hand_type) or {}
    # `any(f > 0)` e nao `if acs`: desde 07/08 o importador guarda tambem a acao de frequencia
    # ZERO (pelo EV dela), entao uma mao fora da range chega aqui com entradas — todas zeradas.
    if not any(float(v.get('f') or 0) > 0 for v in acs.values()):
        # A mão não chega a este nó: a range que o GW faz avançar até aqui não a contém (num
        # `R2-RAI` de 16bb são 98 das 169). Sem estratégia para ela, TODA ação vira desvio — o
        # 72o levava `major_leak` no call E no fold, o que só denuncia que a carta não tem o que
        # dizer. Sem gabarito não é erro, a mesma regra do [[project_sem_gabarito_nao_e_erro]].
        base['coverage_reason'] = 'hu_hand_out_of_range'
        base['hu_depth'] = depth
        return base
    freq: dict = {'fold': 0.0, 'call': 0.0, 'raise': 0.0, 'allin': 0.0}
    for rot, v in acs.items():
        freq[_hu_familia_da_acao(rot, depth)] += float(v.get('f') or 0)
    freq = {k: round(v, 4) for k, v in freq.items()}

    # range agregado (peso por combos) — so display
    total = jogadas = 0.0
    for m, macs in (no.get('maos') or {}).items():
        c = _HU_COMBOS(m)
        total += c
        jogadas += c * sum(float(v.get('f') or 0) for r, v in macs.items()
                           if _hu_familia_da_acao(r, depth) != 'fold')
    # **FRAÇÃO (0..1), não porcentagem.** Todo o resto do sistema devolve `range_pct` nessa escala
    # e os consumidores multiplicam por 100 na hora de exibir (front, `llm_explainer`). Este ramo
    # nascia em 0..100 e o card imprimia **"9880%"** — o mesmo defeito de unidade que já custou
    # caro aqui em fichas × bb, agora em fração × porcentagem. Ficou escondido enquanto o número
    # só alimentava a largura de uma barra (que satura em 100%); apareceu no dia em que virou texto.
    range_pct = round(jogadas / total, 4) if total else 0.0

    _rec_map = {'fold': 'fold', 'call': 'call', 'raise': 'raise', 'allin': 'jam'}
    rec = [_rec_map[k] for k, v in sorted(freq.items(), key=lambda kv: -kv[1]) if v >= 0.02]

    fam = {'shove': 'allin', 'jam': 'allin', 'allin': 'allin', 'all-in': 'allin',
           'raise': 'raise', 'bet': 'raise', 'call': 'call', 'check': 'call',
           'fold': 'fold'}.get((action_taken or '').lower(), (action_taken or '').lower())
    # Adjacencia raise<->jam SO quando o no nao oferece a familia jogada: a 10bb o unico
    # aumento e o jam, e um "raise" do jogador e o mesmo compromisso.
    # O `f > 0` no varredor NAO e decorativo: desde 07/08 o importador guarda tambem as acoes de
    # frequencia zero, entao "existe rotulo dessa familia" passou a ser sempre verdadeiro e a
    # adjacencia nunca mais dispararia. A pergunta certa sempre foi "alguma mao JOGA essa
    # familia", nao "o rotulo existe".
    if freq.get(fam, 0) == 0 and fam in ('raise', 'allin'):
        outra = 'allin' if fam == 'raise' else 'raise'
        if freq.get(outra, 0) > 0 and not any(
                _hu_familia_da_acao(r, depth) == fam and float(v.get('f') or 0) > 0
                for macs in (no.get('maos') or {}).values() for r, v in macs.items()):
            fam = outra

    f_jogada = freq.get(fam, 0.0)
    if f_jogada >= 0.20:
        quality = 'correct'
    elif f_jogada >= 0.05:
        quality = 'acceptable'
    elif f_jogada >= 0.005:
        quality = 'minor_mistake'
    else:
        quality = 'major_leak'

    perda = _perda_de_ev_da_carta(acs, depth, fam)
    if (perda is not None and perda < _EV_MINOR_BB()
            and quality in ('major_leak', 'minor_mistake')):
        # ── Por que isto NAO contradiz o RC-A ────────────────────────────────────────────────
        # O `_preflop_gto_label_adjust` decidiu, com razao, que `major_leak` nunca rebaixa por EV:
        # "custa pouco JUSTAMENTE porque nao devia estar no pote". Aquilo vale para mao fora do
        # range — que aqui nem chega neste ponto, sai antes como `hu_hand_out_of_range`.
        # Este caso e outro: a mao ESTA no range e joga alguma coisa; o que tem frequencia zero e
        # a ACAO escolhida. Medido no acervo, o SB a 12,6bb que min-raisa em vez de limpar perde
        # entre 0,000 e 0,014bb — mesma mao, mesmo pote, EV empatado. Chamar isso de erro e
        # severidade sem lastro, e foi o que o coach apontou em 4 casos.
        quality = 'acceptable'
        base['ev_perda_carta_bb'] = perda

    base.update({
        'available': True,
        'source': fonte,
        'hu_depth': depth,
        'in_range': (freq['call'] + freq['raise'] + freq['allin']) >= 0.05,
        'range_pct': range_pct,
        'hand_freq': freq,
        'recommended_actions': rec or ['fold'],
        'action_quality': quality,
        'pro_notes': [],
    })
    return base


def _analyze_preflop_impl(
    position: str,
    hero_hand_type: str,      # ex: 'AKo', 'AKs', 'AA'
    stack_bb: float,
    action_taken: str,        # 'fold', 'call', 'raise', 'jam'
    facing_size: float = 0.0,
    vs_position: str = '',    # posição de quem abriu (opener)
    is_3bet_pot: bool = False,
    caller_position: str = '', # posição do cold caller (se houver, ativa squeeze lookup)
    n_players: int | None = None,  # tamanho da mesa — usado pra mapping correto pipeline→GW
    facing_raises: int = 0,    # nº de raises de villains ANTES da decisão do hero (open=1, 3bet=2…)
    hero_was_aggressor: bool = False,  # hero já deu raise nesta street antes desta decisão
    facing_limp: bool = False,  # pote limpado (limp sem raise) — árvore fora da cobertura GTO
    is_pko: bool = False,  # torneio PKO/bounty — usa ranges PKO do GW (RFI) quando cobertos
    facing_to_bb: float = 0.0,  # #23: tamanho do open enfrentado (raise-to total, em bb)
    facing_allin: bool = False,   # so o caminho HU consome; o ring usa o wrapper via pop
) -> dict:
    """
    Retorna análise GTO completa de uma decisão preflop.

    Keys retornadas:
      available, scenario, hand_type, stack_bucket, stack_bb,
      position, vs_position, in_range, range_pct, range_hands,
      recommended_actions, action_quality, pro_notes,
      rfi_pct (RFI), hands_4bet/hands_call (vs_3bet)
    """
    data    = _load()
    bucket  = _stack_bucket(stack_bb)
    bk_data = data.get('ranges', {}).get(bucket, {})
    pos     = _norm_pos(position, n_players)
    vs_pos  = _norm_pos(vs_position, n_players) if vs_position else ''
    cal_pos = _norm_pos(caller_position, n_players) if caller_position else ''

    base = {
        'available': False, 'scenario': 'rfi',
        'hand_type': hero_hand_type, 'stack_bucket': bucket,
        'stack_bb': round(stack_bb, 1), 'position': pos,
        'vs_position': vs_pos or None,
        'in_range': False, 'range_pct': 0.0, 'range_hands': '',
        'recommended_actions': [], 'action_quality': 'unknown',
        'action_taken': action_taken, 'pro_notes': [],
    }

    # Squeeze: hero é squeezador (raise sobre open + cold caller). Distingue de vs_3bet HU.
    if is_3bet_pot and vs_pos and cal_pos:
        scenario = 'squeeze'
    elif hero_was_aggressor and facing_raises >= 2 and vs_pos:
        # Hero 3betou (foi agressor) e agora enfrenta um 4-BET (open + 4bet = 2 raises
        # de villain). A range vs_4bet[hero][4bettor] existe (GW v3, deep stacks). Sem
        # este branch caía em vs_3bet (range errado — resposta a 3bet, não a 4bet).
        scenario = 'vs_4bet'
    elif hero_was_aggressor and facing_size > 0 and vs_pos:
        # Hero ABRIU (RFI) e agora enfrenta um re-raise (3bet). O flag is_3bet_pot marca
        # "hero FEZ o 3bet", não "hero ENFRENTA um 3bet" — por isso vem False aqui mesmo
        # sendo pote de 3bet. Sem este branch caía em vs_rfi (defesa vs open), que não tem
        # entrada pro pareamento opener×3bettor → NULL falso. A range vs_3bet[opener][3bettor]
        # já existe (GW v3): pos=hero (opener), vs_pos=3bettor.
        scenario = 'vs_3bet'
    elif facing_raises >= 2 and not hero_was_aggressor:
        # Hero (cold caller / blind) enfrenta um pote 3-BET/SQUEEZE sem ter sido o agressor.
        # Tem range próprio (faces_squeeze[hero][3bettor], coletado via seed do GW). NUNCA
        # tratar como vs_rfi (que aplicaria a defesa larga vs open simples e recomendaria,
        # ex., call 45s vs squeeze, marcando um fold correto como gto_critical). Sem cobertura
        # no faces_squeeze → lookup retorna base (available=False) = NULL honesto.
        scenario = 'faces_squeeze'
    elif facing_size > 0:
        # vs_pos pode ser '' quando opener não foi detectado — lookup retornará None → available=False
        scenario = 'vs_rfi'
    else:
        scenario = 'rfi'
    base['scenario'] = scenario

    # HEADS-UP: rota EXCLUSIVA para as cartas capturadas do GW. A carta ring nao descreve mesa
    # de 2 (BB defende outra range, SB limpa por estrategia), e ate 06/08 ela era consultada
    # assim mesmo — acusando de erro, por exemplo, o 3-bet OBRIGATORIO de JJ no BB.
    if int(n_players or 0) == 2 and pos in ('SB', 'BB'):
        return _hu_analyze(base, pos, hero_hand_type, float(stack_bb), action_taken,
                           facing_raises, hero_was_aggressor, facing_limp,
                           float(facing_to_bb or 0.0), bool(facing_allin))

    # Hero ainda na mão contra um raise de quem age DEPOIS dele. Só existe um jeito de isso
    # acontecer: hero LIMPOU. (Se tivesse foldado estaria fora; se tivesse aberto, o cenário seria
    # vs_3bet.) Nenhuma árvore que capturamos tem esse nó — as nossas são raise-first e o GTO não
    # open-limpa de posição não-blind. O lookup abaixo ia falhar de qualquer jeito; o problema é
    # que falhava MUDO, com `available=False` e `coverage_reason=None`, indistinguível de gap de
    # captura. Medido no acervo de produção: 89 das 284 decisões preflop sem gabarito são isto,
    # e o par mais comum é SB limp + BB iso-raise (29).
    #
    # Só ANOTA — não retorna. Anotar não muda `available` nem veredito nenhum (há teste travando
    # esse invariante), e retornar aqui apagaria o fallback de reshove push/fold que vive logo
    # abaixo no ramo vs_rfi. Ele hoje é código morto (a seção `push_fold` do JSON está vazia em
    # todos os buckets), mas matá-lo de vez seria uma decisão que esta anotação não precisa tomar.
    if scenario in ('vs_rfi', 'faces_squeeze') and vs_pos and _age_depois(pos, vs_pos):
        base['coverage_reason'] = 'limp_then_raise'

    # Pote LIMPADO (limp sem raise) = árvore fora da cobertura GTO (capturamos só
    # árvores raise-first: RFI/vs_RFI/vs_3bet/squeeze/faces_squeeze). Iso-raise,
    # over-limp e BB-check de opção caem todos aqui. Rotula o motivo p/ o display
    # mostrar "{pos} vs Limp" em vez de um available=False mudo (parece falta de
    # captura, mas é gap de cenário conhecido — backlog #22).
    if facing_limp:
        # A stacks curtos (push/fold), um JAM/FOLD sobre um limp É a MESMA decisão de
        # push/fold — o limp é só dead money e não cria nó GTO novo (o GTO não
        # open-limpa de posição não-blind, então não existe árvore vs-limp pra
        # capturar). Aplica o range de RFI (push/fold) com flag de aproximação. Os
        # demais potes limpados (deep, ou call/iso-raise) seguem sem cobertura honesta.
        # ⚠️ O BB NÃO entra neste atalho, e a razão é dupla. (a) Estrutural: o BB nunca é
        # first-in — não existe range de RFI para ele em bucket nenhum (conferido: os 9 buckets
        # trazem UTG..SB e nenhum BB), então o lookup abaixo não tinha como achar nada.
        # (b) Semântica: o raciocínio do atalho é "o limp é dead money, então jamar sobre ele é a
        # mesma decisão de abrir". Para o BB isso é falso — ele já tem 1bb dentro e FECHA a ação;
        # não é abertura, é defesa da própria big blind.
        # Sem esta guarda o BB caía no lookup, não achava, e escorria para o fim da função sem
        # `coverage_reason` — o null MUDO. Eram 11 das 46 mudas do acervo de produção; as outras
        # 35 nem chegavam aqui porque o `facing_limp` não sobrevivia ao banco.
        if (pos != 'BB' and stack_bb <= 12
                and action_taken.lower() in ('shove', 'jam', 'allin', 'fold')):
            scenario = 'rfi'
            base['scenario'] = 'rfi'
            base['limp_dead_money'] = True   # display: "≈ push/fold · limp = dead money"
            # cai pro lookup de RFI abaixo (não retorna)
        elif pos not in ('SB', 'BB') and action_taken.lower() in ('call', 'limp', 'check'):
            # ── OVER-LIMP fora dos blinds: não é falta de carta, é desvio ────────────────────
            # Limpar só é ação legítima nos blinds — o SB completa por meia cega, o BB tem a
            # opção grátis. De UTG a BTN a árvore do GW oferece **só FOLD e RAISE** (conferido
            # em 374 nós de primeira decisão: nenhum tem CALL fora do SB). Não é lacuna de
            # captura: é ação que a estratégia não contém.
            #
            # Sem esta saída, o hero limpando ATRÁS de outro limp caía no `limped_pot` e ficava
            # sem veredito — 41 decisões do acervo, todas mudas. E o mesmo hero limpando de
            # ABERTURA (17 decisões) já era acusado, porque não passava por aqui: dois vereditos
            # diferentes para o mesmo erro, decididos por quem agiu antes dele.
            #
            # A carta de RFI responde as duas pontas: mão no range → o certo era RAISE; fora do
            # range → era FOLD. Nos dois casos o limp é o desvio.
            scenario = 'rfi'
            base['scenario'] = 'rfi'
            base['limp_fora_dos_blinds'] = True
            # cai pro lookup de RFI abaixo (não retorna)
        else:
            base['coverage_reason'] = 'limped_pot'
            return base  # available=False — fora de cobertura (limped pot)

    # BB checando em pot não contestado = free play. Não há range pra gradear (não dá pra
    # foldar o BB; check é o default), mas é TRIVIALMENTE correto. Marca como tal em vez de
    # "sem cobertura" pra não exibir "Spot N/A · Sem veredito".
    if scenario == 'rfi' and pos == 'BB' and action_taken.lower() == 'check':
        # BB check em pote não-aberto: NÃO é decisão gradeável (INV-3, null honesty). Não fabrica
        # veredito 'correct' (isso era veredito inventado p/ um não-spot). available=False honesto;
        # marca bb_option só p/ o display mostrar "Check de opção do BB" em vez de "Spot N/A" mudo,
        # sem cravar acerto. scenario fica 'rfi' e NÃO seta coverage_reason.
        #
        # ⚠️ Na prática este ramo quase não roda: quem chega aqui com `facing_limp` conhecido já
        # foi desviado acima para `limped_pot`, e no acervo de produção **163 de 163** desses
        # checks tinham `facing_limp = 1` — se todos foldassem até o BB, a mão acabaria sem
        # decisão dele. Isto aqui é o fallback de quem chama sem saber do limp (linha antiga, outro
        # caller). Não é o caso comum, e chamá-lo de "free play" no plural seria errado.
        base['bb_option'] = True
        base['reasoning'] = 'Check de opção do BB em pote não-aberto: sem decisão gradeável.'
        return base   # available=False (default da base) — scenario='rfi'

    # ── PKO overlay (RFI / vs_RFI) ────────────────────────────────────────────
    # Em torneio PKO o bounty muda a estratégia (abre-se/defende-se mais largo).
    # Quando é PKO e o spot tem cobertura, troca a FONTE de range pra PKO do GW
    # (capturado por estágio field-remaining) — o resto do grading v3 roda igual.
    # RFI e vs_RFI usam bk_data, então basta o swap aqui; squeeze tem hook próprio
    # (lê de data[ranges][bk_try]). Seleção do estágio pelo depth (stage↔depth
    # acoplado). Sem cobertura PKO (raso <45bb, sem captura, T2/FT config-specific)
    # → segue no range Classic chipEV abaixo. field fixo em 200p (única captura).
    if is_pko and scenario in ('rfi', 'vs_rfi'):
        _pko_bk, _pko_stage, _pko_label = _pko_ranges_for(stack_bb)
        _pko_hit = False
        if _pko_bk:
            if scenario == 'rfi':
                _pko_hit = _pko_bk.get('RFI', {}).get(pos) is not None
            else:  # vs_rfi: [opener][defender]
                _pko_hit = _pko_bk.get('vs_RFI', {}).get(vs_pos, {}).get(pos) is not None
        if _pko_hit:
            bk_data = _pko_bk
            base['pko'] = True
            base['pko_stage'] = _pko_stage
            base['pko_stage_label'] = _pko_label
            base['source'] = 'pko_gto'

    # ── RFI ──────────────────────────────────────────────────────────────────
    if scenario == 'rfi':
        rfi = bk_data.get('RFI', {}).get(pos)
        if not rfi:
            # Push/fold fallback para stacks curtos (10bb, 14bb; 20bb como último recurso)
            pf_section = bk_data.get('push_fold', {}).get(pos)
            if pf_section:
                pf_entry = None
                for pf_key in _PUSHFOLD_BUCKET_STACK.get(bucket, []):
                    pf_entry = pf_section.get(pf_key)
                    if pf_entry:
                        break
                if pf_entry:
                    shove_hands = pf_entry.get('shove_hands', '')
                    shove_pct   = float(pf_entry.get('shove_pct', 0))
                    in_shove    = _in_range(hero_hand_type, shove_hands)
                    rec         = ['jam'] if in_shove else ['fold']
                    quality     = _pushfold_quality(action_taken, in_shove)
                    base.update({
                        'available': True, 'in_range': in_shove,
                        'range_pct': shove_pct, 'range_hands': shove_hands,
                        'range_grid_pct': shove_pct,
                        'recommended_actions': rec, 'action_quality': quality,
                        'source': pf_entry.get('_source', 'pushfold_gto'),
                        'pro_notes': _pushfold_notes(pos, hero_hand_type, stack_bb,
                                                     shove_pct, in_shove, action_taken),
                    })
                    return base
            return base
        # Detecta formato v3 (GW master) vs v2 (RegLife antigo)
        is_v3 = 'open_pct' in rfi or 'raise_hands' in rfi
        in_complete = False  # SB completa/limpa esta mão (preenchido no v3 via código 'C')

        if is_v3:
            # v3: campos open_pct/raise_pct/allin_pct + raise_hands/allin_hands
            pct         = float(rfi.get('open_pct', 0))
            grid_pct    = pct
            raise_hs    = rfi.get('raise_hands', '')
            allin_hs    = rfi.get('allin_hands', '')
            # range total não-fold = raise + allin (em stacks rasos quase tudo é allin)
            all_hands_parts = [h for h in [raise_hs, allin_hs] if h]
            hands_str   = ','.join(all_hands_parts)
            acoes       = []  # v3 deriva ação por hand_in (in_raise vs in_allin)
            limp_str    = ''   # v3 não tem limp (RegLife antigo tinha SB limp)
            limp_pct    = 0.0
            in_raise    = bool(raise_hs) and _in_range(hero_hand_type, raise_hs)
            in_allin    = bool(allin_hs) and _in_range(hero_hand_type, allin_hs)
            in_rng      = in_raise or in_allin
            in_limp     = False

            # Ordem por freq da MÃO específica quando disponível (hand_freqs do GW v3)
            # Inclui FOLD quando freq fold >= 20% (mão mista que GTO frequentemente folda)
            _hf_rfi = rfi.get('hand_freqs', {}).get(hero_hand_type, {})
            _hf_raise_w = 0.0; _hf_allin_w = 0.0; _hf_fold_w = 0.0; _hf_call_w = 0.0
            for code, f in _hf_rfi.items():
                if code == 'RAI':                _hf_allin_w += float(f)
                elif code == 'F':                _hf_fold_w  += float(f)
                elif code == 'C':                _hf_call_w  += float(f)   # SB complete/limp
                elif code.startswith('R'):       _hf_raise_w += float(f)
            # SB curto joga limp-or-jam: 'C' (complete) é ação GTO VÁLIDA. O v3 antes
            # ignorava o complete (só raise/jam) → AKs SB (complete 100%) caía em
            # rec=fold + "fora do range" + jam=major_leak (card contraditório). Agora
            # o complete entra no rec e marca a mão como no range.
            in_complete = _hf_call_w > 0
            in_rng = in_rng or in_complete
            _opts = []
            if in_allin:
                _opts.append(('jam',   _hf_allin_w if _hf_allin_w > 0 else float(rfi.get('allin_pct', 0) or 0)))
            if in_raise:
                _opts.append(('raise', _hf_raise_w if _hf_raise_w > 0 else float(rfi.get('raise_pct', 0) or 0)))
            if _hf_call_w >= 0.10:
                _opts.append(('call', _hf_call_w))   # complete/limp do SB
            # Fold como opção GTO quando freq significativa (mão mista entre fold/raise)
            if _hf_fold_w >= 0.20:
                _opts.append(('fold', _hf_fold_w))
            _opts.sort(key=lambda x: -x[1])
            # Filtra freq ≥10% (igual vs_rfi/mesclada). Sem isto, jam/raise entram só
            # por membership na string do range, com freq ~0% (ex.: RFI 33 @75bb em
            # raise_hands → "Fold / Raise" com raise 0,12%). Scanner de invariantes pegou.
            rec = [a for a, w in _opts if w >= 0.10] or ['fold']
        else:
            # v2 (RegLife antigo): pct + hands + acoes
            pct         = float(rfi.get('combo_pct') or rfi.get('pct', 0))
            grid_pct    = float(rfi.get('grid_pct') or rfi.get('pct', 0))
            hands_str   = rfi.get('hands', '')
            acoes       = rfi.get('acoes', [])
            limp_str    = rfi.get('limp_hands', '')   # SB limp range (quando presente)
            limp_pct    = float(rfi.get('limp_combo_pct') or rfi.get('limp_pct', 0))
            in_rng      = _in_range(hero_hand_type, hands_str)
            in_limp     = bool(limp_str) and _in_range(hero_hand_type, limp_str)

            # Recomendação: raise se no raise range, call/limp se no limp range, fold caso contrário
            if in_rng:
                rec = [_ACT.get(a, a.lower()) for a in acoes]
            elif in_limp:
                rec = ['call']   # limp from SB
            else:
                rec = ['fold']

        # hand_freq exato pra RFI (v3 GW) — usado pelo quality classifier por freq
        # e pela barra "sua mão" do Decision Card/Replayer.
        hand_freq = None
        if is_v3:
            hand_freq_raw = rfi.get('hand_freqs', {}).get(hero_hand_type, {})
            if hand_freq_raw:
                hand_freq = {'call': 0.0, 'raise': 0.0, 'allin': 0.0, 'fold': 0.0}
                for code, f in hand_freq_raw.items():
                    if code == 'F':       hand_freq['fold']  += float(f)
                    elif code == 'C':     hand_freq['call']  += float(f)
                    elif code == 'RAI':   hand_freq['allin'] += float(f)
                    elif code.startswith('R'):  hand_freq['raise'] += float(f)
                hand_freq = {k: round(v, 4) for k, v in hand_freq.items()}
            else:
                # Mão SEM entrada no GW v3 = fold puro 100% (out of range). Devolver
                # {fold:1} explícito (não None) evita o display cair no % AGREGADO do
                # range — a análise é sobre a carta do jogador, não a posição.
                hand_freq = {'call': 0.0, 'raise': 0.0, 'allin': 0.0, 'fold': 1.0}

        quality = _rfi_quality(action_taken, in_rng, stack_bb,
                               in_limp=in_limp, is_sb=(pos == 'SB'),
                               hand_freq=hand_freq)
        # SB limp-strategy: jammar/raisear uma mão que o GTO COMPLETA (limpa) é
        # simplificação de EV próxima (ex.: AKs SB @10bb jam vs limp), não erro
        # grave. Rebaixa major_leak→leak quando a mão está no range de complete.
        if (in_complete or in_limp) and action_taken.lower() in ('shove', 'jam', 'allin', 'raise') and quality == 'major_leak':
            quality = 'leak'
        # Expõe raise/allin/call/fold pct agregados do range — usados pela
        # barra do Decision Card quando hand_freq específica não existe.
        if is_v3:
            agg_raise = float(rfi.get('raise_pct', 0) or 0)
            agg_allin = float(rfi.get('allin_pct', 0) or 0)
        else:
            # v2: deriva de acoes (R = raise, J/A = allin)
            _acoes_norm = [str(a).upper() for a in acoes]
            agg_raise = pct if any(a in ('R', 'RAISE') for a in _acoes_norm) else 0.0
            agg_allin = pct if any(a in ('J', 'A', 'JAM', 'ALLIN', 'ALL-IN') for a in _acoes_norm) else 0.0
            if not (agg_raise or agg_allin):  # fallback genérico
                agg_raise = pct
        agg_call = limp_pct  # RFI tem call só via limp (SB)
        agg_fold = max(0.0, 1.0 - (agg_raise + agg_allin + agg_call))

        base.update({
            'available': True, 'in_range': in_rng or in_limp,
            'range_pct': pct, 'range_hands': hands_str,
            # TAMANHO GTO do raise (o código 'R2.1' carrega o sizing) — ensinado no feedback
            'raise_to_bb': raise_to_bb_from_node(rfi, hero_hand_type),
            'hand_freq': hand_freq,  # freq exata da mão hero (para barra Decision Card)
            'range_grid_pct': grid_pct,
            'recommended_actions': rec, 'rfi_pct': pct,
            # Agregados do range (rendered no Decision Card quando hand_freq=null)
            'raise_pct': round(agg_raise, 4),
            'allin_pct': round(agg_allin, 4),
            'call_pct':  round(agg_call,  4),
            'fold_pct':  round(agg_fold,  4),
            'action_quality': quality,
            'in_limp_range': in_limp,
            'limp_pct': limp_pct,
            'pro_notes': _rfi_notes(pos, hero_hand_type, stack_bb, pct, in_rng, action_taken,
                                     in_limp=in_limp, hand_freq=hand_freq),
        })

    # ── vs RFI ───────────────────────────────────────────────────────────────
    elif scenario == 'vs_rfi':
        vs_rfi = bk_data.get('vs_RFI', {})
        # JSON v3 (GW master) usa 9-max nativo. vs_pos e pos já foram normalizados
        # pelo _POS_NORM (UTG+1, UTG+2, etc).
        # Tentar lookup direto; fallback p/ aliases legacy ("{opener}_open", "MP")
        opener_data = vs_rfi.get(vs_pos)
        if not isinstance(opener_data, dict):
            # Fallback v2 antigo: usava "MP" no lugar de "UTG+1"
            for alt in (f"{vs_pos}_open", 'MP' if vs_pos == 'UTG+1' else None):
                if alt and isinstance(vs_rfi.get(alt), dict):
                    opener_data = vs_rfi.get(alt)
                    break
        defender = opener_data.get(pos) if isinstance(opener_data, dict) else None
        if defender is None and isinstance(opener_data, dict):
            # Fallback: tentar 'MP' se pos for UTG+1 (legacy)
            if pos == 'UTG+1':
                defender = opener_data.get('MP')
        if not defender or not isinstance(defender, dict):
            # Push/fold reshove fallback para stacks curtos sem dados RegLife vs_RFI
            pf_section = bk_data.get('push_fold', {}).get(pos)
            if pf_section:
                pf_entry = None
                for pf_key in _PUSHFOLD_BUCKET_STACK.get(bucket, []):
                    pf_entry = pf_section.get(pf_key)
                    if pf_entry:
                        break
                if pf_entry:
                    shove_hands = pf_entry.get('shove_hands', '')
                    shove_pct   = float(pf_entry.get('shove_pct', 0))
                    in_shove    = _in_range(hero_hand_type, shove_hands)
                    # vs raise: reshove com o range de shove; fold o restante
                    rec     = ['jam'] if in_shove else ['fold']
                    quality = _pushfold_quality(action_taken, in_shove)
                    base.update({
                        'available': True, 'in_range': in_shove,
                        'range_pct': shove_pct, 'range_hands': shove_hands,
                        'recommended_actions': rec, 'action_quality': quality,
                        'source': pf_entry.get('_source', 'pushfold_gto') + '_reshove',
                        'pro_notes': _pushfold_notes(pos, hero_hand_type, stack_bb,
                                                     shove_pct, in_shove, action_taken,
                                                     is_reshove=True),
                    })
                    return base
            base.setdefault('coverage_reason', 'pairing_uncovered')
            return base

        if 'fold_pct' in defender:
            # Formato novo (RegLife v2 e v3 GW master): fold/call/raise/allin separados
            call_pct    = float(defender.get('call_pct', 0))
            raise_pct   = float(defender.get('raise_pct', 0))
            allin_pct   = float(defender.get('allin_pct', 0))
            fold_hands  = defender.get('fold_hands', '')
            call_hands  = defender.get('call_hands', '')
            raise_hands = defender.get('raise_hands', '')
            allin_hands = defender.get('allin_hands', '')

            in_call  = bool(call_hands)  and _in_range(hero_hand_type, call_hands)
            in_raise = bool(raise_hands) and _in_range(hero_hand_type, raise_hands)
            in_allin = bool(allin_hands) and _in_range(hero_hand_type, allin_hands)
            in_rng   = in_call or in_raise or in_allin

            # Recomendação preserva TODAS as ações válidas (mãos mistas). ORDEM por
            # freq da MÃO específica (hand_freqs do GW v3) quando disponível.
            # Inclui FOLD quando hand_freq.fold ≥ 20% (mão mista que GTO frequentemente folda).
            _hf_vs = defender.get('hand_freqs', {}).get(hero_hand_type, {})
            _hf_call_w = 0.0; _hf_raise_w = 0.0; _hf_allin_w = 0.0; _hf_fold_w = 0.0
            for code, f in _hf_vs.items():
                if code == 'C':                  _hf_call_w  += float(f)
                elif code == 'RAI':              _hf_allin_w += float(f)
                elif code == 'F':                _hf_fold_w  += float(f)
                elif code.startswith('R'):       _hf_raise_w += float(f)
            has_hf_vs = (_hf_call_w + _hf_raise_w + _hf_allin_w) > 0
            _options = []
            if in_allin:
                _options.append(('jam',   _hf_allin_w if has_hf_vs else float(defender.get('allin_pct', 0) or 0)))
            if in_raise:
                _options.append(('raise', _hf_raise_w if has_hf_vs else float(defender.get('raise_pct', 0) or 0)))
            if in_call:
                _options.append(('call',  _hf_call_w  if has_hf_vs else float(defender.get('call_pct',  0) or 0)))
            if _hf_fold_w >= 0.20:
                _options.append(('fold', _hf_fold_w))
            _agg_order = {'jam': 4, 'raise': 3, 'call': 2, 'fold': 1}
            _options.sort(key=lambda x: (-x[1], -_agg_order[x[0]]))
            # Filtra por freq ≥10% (igual à branch mesclada). Sem isto, uma ação de
            # peso ~0 entrava no rec só por a mão estar na STRING do range (ex.: 99 vs
            # open jama 99.9% mas estava em call_hands → "GTO recomenda Shove / Call").
            # Todos os 964 spots têm hand_freqs reais (0 string-only), então o peso é
            # sempre a freq da mão — o filtro é seguro.
            rec = [a for a, w in _options if w >= 0.10] or ['fold']

            # aggr_pct: campo v2 (RegLife) ou computado em v3 (call+raise+allin = não-fold)
            aggr_pct = float(defender.get('aggr_pct', call_pct + raise_pct + allin_pct))

            # hand_freq: frequência EXATA da mão do hero (vem do JSON v3 hand_freqs).
            # Permite mostrar 28/72 pra 88 em vez de 13/5 (% global do range).
            # Códigos brutos do GW (C, R5, R6, RAI, F) — normalizar pra call/raise/allin/fold.
            hand_freq_raw = defender.get('hand_freqs', {}).get(hero_hand_type, {})
            hand_freq = {'call': 0.0, 'raise': 0.0, 'allin': 0.0, 'fold': 0.0}
            for code, f in hand_freq_raw.items():
                if code == 'F':       hand_freq['fold']  += float(f)
                elif code == 'C':     hand_freq['call']  += float(f)
                elif code == 'RAI':   hand_freq['allin'] += float(f)
                elif code.startswith('R'):  hand_freq['raise'] += float(f)
            hand_freq = {k: round(v, 4) for k, v in hand_freq.items()}
            has_hf = sum(hand_freq.values()) > 0.001

            # Quality classifier usa hand_freq (freq EXATA) quando disponível —
            # mais preciso que verificar in/out range. Fallback pro modo rec/in_rng.
            quality = _vs_rfi_quality_new(action_taken, in_rng, rec, hand_freq if has_hf else None)

            # #23: open OFF-TREE (vilão abriu MAIOR que o GTO). A range de defesa é
            # vs o open mínimo canônico; vs um open maior a defesa correta é mais
            # tight, então foldar uma mão marginal é DEFENSÁVEL — não marcar crítico.
            # Rebaixa o fold (leak/major_leak → acceptable) e anexa flag pro card.
            open_caveat = None
            _canon_open = _canonical_open_bb(bk_data, vs_pos)
            if (_canon_open and facing_to_bb
                    and facing_to_bb >= _canon_open * _OPEN_OVERSIZE_FACTOR):
                open_caveat = {'facing_bb': round(facing_to_bb, 1),
                               'canonical_bb': _canon_open}
                # Só rebaixa a DEFESA MARGINAL (call-dominada): vs um open maior, são
                # essas mãos que viram fold. Mão de VALUE que o GTO defende sobretudo
                # com agressão (raise/jam > call) NUNCA é fold defensável, mesmo vs open
                # grande — segue crítico (ex.: AA/KK/QQ/99 que 3betam). Usa a freq EXATA
                # da mão (hand_freq) quando há; senão cai na presença de raise/jam no rec.
                _is_value = _defesa_e_de_valor(hand_freq if has_hf else None, rec)
                if (action_taken.lower() == 'fold' and not _is_value
                        and quality in ('leak', 'major_leak')):
                    quality = 'acceptable'

            base.update({
                'available': True, 'in_range': in_rng,
                'range_pct':    aggr_pct,
                'range_hands':  allin_hands or raise_hands or call_hands,
                'raise_to_bb': raise_to_bb_from_node(defender, hero_hand_type),
                'recommended_actions': rec, 'action_quality': quality,
                'fold_pct':   float(defender.get('fold_pct', 0)),
                'call_pct':   call_pct,
                'raise_pct':  raise_pct,
                'allin_pct':  allin_pct,
                'hand_freq':  hand_freq,  # freq EXATA da mão hero (use no Decision Card)
                'fold_hands': fold_hands, 'call_hands': call_hands,
                'raise_hands': raise_hands, 'allin_hands': allin_hands,
                'open_size_mismatch': open_caveat,  # #23: open off-tree (None se normal)
                'pro_notes':  _vs_rfi_notes_new(pos, vs_pos, hero_hand_type, stack_bb,
                                                 aggr_pct, in_rng, rec, action_taken),
            })
        else:
            # Old format: pct_play / hands / acoes
            pct_play  = float(defender.get('pct_play', 0))
            hands_str = defender.get('hands', '')
            acoes     = defender.get('acoes', [])
            in_rng    = _in_range(hero_hand_type, hands_str)
            rec       = [_ACT.get(a, a.lower()) for a in acoes] if in_rng else ['fold']
            quality   = _vs_rfi_quality(action_taken, in_rng, acoes)
            base.update({
                'available': True, 'in_range': in_rng,
                'range_pct': pct_play, 'range_hands': hands_str,
                'raise_to_bb': raise_to_bb_from_node(defender, hero_hand_type),
                'recommended_actions': rec, 'action_quality': quality,
                'pro_notes': _vs_rfi_notes(pos, vs_pos, hero_hand_type, stack_bb,
                                            pct_play, in_rng, action_taken, acoes),
            })

        # ── O open enfrentado não é o que o nó modela ────────────────────────────────────────
        # `vs_RFI[opener][defender]` responde a UM tamanho — e o nó o DECLARA em
        # `preflop_actions`. Varredura dos 324 nós: todos declaram open pequeno (2 a 3,5bb) e
        # NENHUM declara open-jam. Até 09/08 o motor gradeava qualquer tamanho por esse nó:
        # BB/K9o/40bb vs CO saía `correct`, com o MESMO "GTO joga Call / Raise", enfrentando
        # 2bb, 5bb ou 20bb — dez vezes o preço que a carta modela. Pior, pagar um shove de 14bb
        # com J9o também saía "Correto": medido com eval7 contra a própria range de ABERTURA do
        # vilão (mais larga que a de jam, logo conservadora a favor do hero), J9o a 14bb tem
        # 31,1% e precisa de 45,6%; 96s a 20bb tem 32,1% contra 46,9%. Calls de −2 a −3bb
        # absolvidos pelo produto.
        #
        # A rodada anterior escreveu o teto e só o consultou sob "é jam" (≥65% do stack), o que
        # criou uma descontinuidade absurda no mesmo spot: a 20bb `correct`, a 26,5bb sem
        # veredito.
        #
        # POR QUE DIRECIONAL, e não teto seco. Medido no acervo local (1.688 decisões preflop,
        # 587 chegam a um nó vs_RFI): 185 enfrentam tamanho fora da tolerância de 1,4x, 126 já
        # eram null, e 59 ainda têm veredito. Teto seco mataria os 59 — mas 55 deles são FOLDS
        # que a carta também manda foldar (72o, 85o, 93o…), e nesses o preço maior não muda a
        # resposta: só a reforça. Perder 55 vereditos certos para consertar 4 é trocar cobertura
        # por nada. Quem decide é `_veredito_sobrevive_ao_tamanho`, com a margem de EV que a
        # carta publica sobre o fold — ver a justificativa lá, inclusive por que "é mão de value"
        # NÃO serve de critério.
        #
        # Ablação no mesmo acervo (guarda ligado × desligado): 18 decisões perdem veredito, 67
        # ganham (o gate de jam anterior calava 62 folds que a carta também folda), e nenhuma
        # TROCA de veredito nem ganha acusação nova.
        #
        # Sem gabarito não é erro: null honesto, e o card diz qual foi o motivo.
        _dir_tam = _direcao_do_tamanho(defender, facing_to_bb)
        _enfrenta_jam = bool(facing_allin) or bool(
            facing_to_bb and stack_bb
            and float(facing_to_bb) >= float(stack_bb) * _FRACAO_QUE_E_JAM)
        if _dir_tam == 'indeterminado' and _enfrenta_jam:
            # All-in sem `facing_to_bb` no payload: não se sabe o número, mas se sabe que um
            # shove não é o open de 2bb que o nó declara. Tratar como 'dentro' seria o pior
            # veredito possível — o confiante e falso.
            _dir_tam = 'maior'
        _tam_no = _raise_declarado_bb(defender)
        _excesso = max(0.0, float(facing_to_bb or 0) - float(_tam_no or 0))
        _margem = _margem_ev_sobre_fold(bucket, 'vs_rfi', pos, vs_pos, hero_hand_type)
        if base.get('available') and not _veredito_sobrevive_ao_tamanho(
                _dir_tam, base.get('recommended_actions'), _margem, _excesso):
            for _k in ('available', 'in_range'):
                base[_k] = False
            base['recommended_actions'] = []
            base['action_quality'] = 'unknown'
            # O motivo do all-in só vale quando o shove foi MAIOR que o nó: um vilão que vai de
            # all-in por 1,25bb num nó de 2bb está do outro lado da régua, e dizer "abriu de
            # all-in e a carta só descreve open pequeno" seria descrever o oposto do que houve.
            base['coverage_reason'] = ('open_jam_uncovered'
                                       if (_enfrenta_jam and _dir_tam == 'maior')
                                       else 'open_size_off_tree')
            return base

    # ── vs 3bet / faces_squeeze / squeeze / vs_4bet — MESMA estrutura [hero][villain] ──
    elif scenario in ('vs_3bet', 'faces_squeeze', 'squeeze', 'vs_4bet'):
        # vs_3bet:       ranges[stack][vs_3bet][opener_hero][3bettor] — hero abriu, enfrenta 3bet
        # faces_squeeze: ranges[stack][faces_squeeze][hero][3bettor] — hero DEFENDE open+3bet/squeeze
        # squeeze:       ranges[stack][squeeze][hero][opener]        — hero SQUEEZA (raise sobre
        #                open + cold call). Os três têm a MESMA estrutura de spot e graduação
        #                (raise_hands, call_hands, allin_hands, hand_freqs). A branch antiga do
        #                squeeze usava section 'vs_squeeze' + chave flat (formato obsoleto) e nunca
        #                casava — caía em vs_rfi (range errado). Agora reusa este path.
        _section = {'vs_3bet': 'vs_3bet', 'faces_squeeze': 'faces_squeeze',
                    'squeeze': 'squeeze', 'vs_4bet': 'vs_4bet'}[scenario]
        bucket_fallbacks = {
            '14bb': ['10bb', '20bb'], '17bb': ['20bb', '14bb'],
            '40bb': ['30bb', '50bb'], '60bb': ['50bb', '75bb'],
            '75bb': ['100bb', '50bb'],
        }
        candidate_buckets = [bucket] + bucket_fallbacks.get(bucket, [])
        spot = None
        actual_vs = vs_pos
        # PKO overlay (squeeze / vs_3bet / faces_squeeze / vs_4bet): este bloco lê de
        # data[ranges][bk_try] (não bk_data), então o swap acima não alcança — injeta
        # a fonte PKO aqui. Todos os 4 cenários têm a MESMA chave [hero][villain]
        # ([pos][vs_pos]) tanto no Classic quanto no PKO, então basta usar _section.
        if is_pko:
            _pko_bk, _pko_stage, _pko_label = _pko_ranges_for(stack_bb)
            if _pko_bk:
                _pko_sp = _pko_bk.get(_section, {}).get(pos, {}).get(vs_pos)
                if _pko_sp is not None:
                    spot = _pko_sp
                    base['pko'] = True
                    base['pko_stage'] = _pko_stage
                    base['pko_stage_label'] = _pko_label
                    base['source'] = 'pko_gto'
        for bk_try in candidate_buckets if spot is None else []:
            vs3_try = data.get('ranges', {}).get(bk_try, {}).get(_section, {})
            hero_dict = vs3_try.get(pos, {})
            if not hero_dict:
                continue
            # Só pareamento EXATO opener×3bettor. SEM fallback "qualquer 3bettor":
            # com vs_pos desconhecido (ex.: 3bettor não detectado) ou pareamento sem
            # cobertura, é honesto retornar sem grade (NULL) em vez de aplicar a range
            # de um 3bettor aleatório — isso fabricaria um veredito GTO falso.
            spot = hero_dict.get(vs_pos)
            if spot:
                break
        if not spot:
            # Sem o par [hero][vilão] na captura. Distinto de `limp_then_raise`: aquele é
            # estrutural (o nó não existe em árvore nenhuma), este é lacuna da NOSSA base — o nó
            # existe, nós é que não temos. Quem lê a tela precisa saber qual dos dois é, e quem
            # for reabastecer a base precisa saber o que buscar. `setdefault` porque a anotação
            # estrutural, quando houver, é a mais informativa das duas.
            base.setdefault('coverage_reason', 'pairing_uncovered')
            return base
        hands_4bet  = spot.get('raise_hands', '')
        hands_call  = spot.get('call_hands', '')
        hands_allin = spot.get('allin_hands', '')
        hand_freqs  = spot.get('hand_freqs') or {}
        in_4b   = _in_range(hero_hand_type, hands_4bet)
        in_cl   = _in_range(hero_hand_type, hands_call)
        in_jam  = _in_range(hero_hand_type, hands_allin)
        in_rng  = in_4b or in_cl or in_jam
        hf_raw = hand_freqs.get(hero_hand_type) if hand_freqs else None

        # ── Ausente de TODAS as listas do nó = OFF-TREE, não "fold 100%" ─────────────────────
        # O comentário antigo aqui dizia que "GW só popula mãos com ação não-fold", e por isso
        # tratava a ausência como fold puro. É falso: `fold_hands` é populado à parte (neste nó,
        # 8 das 13 mãos de `fold_hands` nem aparecem em `hand_freqs`). Quem não está em lista
        # NENHUMA não chega a este nó — a range de abertura que faz o hero avançar até aqui não a
        # contém.
        #
        # O custo do erro: a 10bb o GW jama KK e AKo em vez de min-raisar, então quem min-raisou
        # KK e levou 3-bet all-in ficava fora de todas as listas → "GTO folda 100%" → o produto
        # dava `correct` a QUEM FOLDOU KK e `major_leak` a quem pagou. E o oráculo já estava no
        # repositório contradizendo isso no MESMO card: `leaklab_gto_evs.json` publica
        # KK = {'F': 0.0, 'C': 7.27}, e é esse arquivo que alimenta o selo de −7,3bb impresso ao
        # lado do "Correto". Duas fontes para o mesmo fato. Medido: 996 pares (nó, mão) off-tree
        # cujo fold o próprio GW cobra ≥1bb, 46 deles com mão premium.
        #
        # A população afetada é "o hero abriu fora da carta na rua anterior" — desvio recreativo
        # comum, não caso raro. Sem gabarito não é erro: null honesto, como o caminho HU já faz.
        _peso_hf = sum(float(v or 0) for v in (hf_raw or {}).values())
        _no_no = _peso_hf > 0.001 or in_rng or _in_range(hero_hand_type, spot.get('fold_hands', '') or '') \
            or _in_range(hero_hand_type, spot.get('check_hands', '') or '')
        if hand_freqs and not _no_no:
            # `hand_freqs` no if: nó em formato antigo (sem freq por mão) não tem como distinguir
            # off-tree de fold, e ali o comportamento conhecido continua valendo.
            base['coverage_reason'] = 'hand_out_of_node_range'
            return base

        # Freq por mão — normaliza códigos brutos GW (F/C/R{x}/RAI) → nosso modelo.
        hf = {'fold': 0.0, 'call': 0.0, 'raise': 0.0, 'allin': 0.0}
        if hf_raw:
            for code, f in hf_raw.items():
                if code == 'F':            hf['fold']  += float(f)
                elif code == 'C':          hf['call']  += float(f)
                elif code == 'RAI':        hf['allin'] += float(f)
                elif code.startswith('R'): hf['raise'] += float(f)
            hf = {k: round(v, 4) for k, v in hf.items()}
        elif hand_freqs:
            # Mão fora de todos os ranges de ação → fold puro
            hf = {'fold': 1.0, 'call': 0.0, 'raise': 0.0, 'allin': 0.0}
        # Entrada all-zero ({F:0,C:0}) = mão de peso 0 (off-tree / 0 combos no nó do
        # solver). Tratar como fold puro — igual à normalização de saída (INV-10).
        # Sem isto, _vs_3bet_quality vê 0% em TUDO → major_leak FALSO ao foldar (ex.:
        # TT faces_squeeze HJ vs SB), enquanto o display normaliza p/ fold:1.0 → card
        # contraditório ("Fold 100%" + LEAK GRAVE por ter foldado).
        if sum(hf.values()) < 0.001:
            hf = {'fold': 1.0, 'call': 0.0, 'raise': 0.0, 'allin': 0.0}
        actions_freq = [
            ('raise', float(hf.get('raise', 0)) or (1.0 if in_4b else 0)),
            ('call',  float(hf.get('call',  0)) or (1.0 if in_cl else 0)),
            ('jam',   float(hf.get('allin', 0)) or (1.0 if in_jam else 0)),
            ('fold',  float(hf.get('fold',  0))),
        ]
        rec = [a for a, f in sorted(actions_freq, key=lambda x: -x[1]) if f >= 0.10]
        if not rec:
            rec = ['fold']
        quality = _vs_3bet_quality(action_taken, in_4b, in_cl, in_jam=in_jam, hand_freq=hf)
        pct_continua = (float(spot.get('raise_pct', 0))
                        + float(spot.get('call_pct', 0))
                        + float(spot.get('allin_pct', 0)))
        # Pcts globais do spot (range agregado) — barra de freq por ação
        raise_pct_g = float(spot.get('raise_pct', 0))
        call_pct_g  = float(spot.get('call_pct',  0))
        allin_pct_g = float(spot.get('allin_pct', 0))
        fold_pct_g  = float(spot.get('fold_pct',  1.0))
        # Normaliza: alguns JSONs vêm em [0,1], outros em [0,100]
        if max(raise_pct_g, call_pct_g, allin_pct_g, fold_pct_g) > 1.5:
            raise_pct_g /= 100.0
            call_pct_g  /= 100.0
            allin_pct_g /= 100.0
            fold_pct_g  /= 100.0

        base.update({
            'available': True, 'in_range': in_rng,
            'range_pct': pct_continua / 100.0 if pct_continua > 1 else pct_continua,
            'range_hands': f"4bet: {hands_4bet} | call: {hands_call} | jam: {hands_allin}",
            'raise_to_bb': raise_to_bb_from_node(spot, hero_hand_type),
            'recommended_actions': rec, 'action_quality': quality,
            'hands_4bet': hands_4bet, 'hands_call': hands_call, 'hands_allin': hands_allin,
            # Pcts globais (frontend usa pra stacked bar quando hand_freq não está disponível)
            'raise_pct': raise_pct_g, 'call_pct': call_pct_g,
            'allin_pct': allin_pct_g, 'fold_pct': fold_pct_g,
            'hand_freq': hf,
            'vs_position': actual_vs,
            'pro_notes':   _vs_3bet_notes(pos, hero_hand_type, stack_bb,
                                          pct_continua, in_4b, in_cl, action_taken, scenario),
        })

    # INV-10 (honestidade do display): quando available=True, hand_freq DEVE ser
    # uma distribuição válida (soma ~1) da AÇÃO DA MÃO. Vários paths devolvem None
    # ou tudo-zero para mãos out-of-range — aí o frontend cai no % AGREGADO do
    # range (distribuição da posição) em vez do veredito da carta do jogador.
    # Normaliza num só ponto: sem distribuição válida = fold puro 100%.
    if base.get('available'):
        _hf = base.get('hand_freq')
        if not _hf or sum(_hf.values()) < 0.5:
            base['hand_freq'] = {'call': 0.0, 'raise': 0.0, 'allin': 0.0, 'fold': 1.0}

    # Depth MUITO aproximado: o bucket mais baixo ('10bb') cobre 0–12bb, então um
    # stack de 3–5bb usa o range de 10bb. Sub-6bb facing open é push/fold puro — o
    # range 10bb (com flats) não se aplica bem e pode marcar veredito over-harsh
    # (ex.: call A6o a 3bb pelas odds vira "major_leak"). Vale também pro RFI em zona
    # de push/fold: a <6bb o range de jam é bem mais largo que o de abertura 10bb,
    # então um shove fora do range 10bb (ex.: K7o UTG @3.8bb) não é erro grave.
    # Não ser over-harsh: rebaixa a severidade 1 nível e sinaliza depth_approx (o
    # front já mostra "≈"). Mesma filosofia do #23 (não punir desvio onde o dado não
    # cobre com precisão).
    if base.get('available') and bucket == '10bb' and stack_bb < 6:
        _soft = {'major_leak': 'leak', 'leak': 'acceptable'}
        if base.get('action_quality') in _soft:
            base['action_quality'] = _soft[base['action_quality']]
            base['depth_approx'] = True

    return base


# ── Quality classifiers ──────────────────────────────────────────────────────

def _rfi_quality(action: str, in_rng: bool, stack_bb: float, *,
                 in_limp: bool = False, is_sb: bool = False,
                 hand_freq: dict | None = None) -> str:
    """Quality classifier RFI.

    Quando hand_freq disponível (freq EXATA da mão pelo GTO Wizard), classifica
    pela frequência GTO da ação tomada:
      >= 30% → correct (ação dominante)
      10–30% → acceptable (ação válida do mix, minoritária)
      3–10%  → leak (raramente GTO — ex: QQ shove 4% quando raise é 96%)
      < 3%   → major_leak (fora do GTO)
    """
    act = action.lower()
    # Normalizar 'shove'/'allin'/'all-in' → 'jam' (forma canônica)
    if act in ('shove', 'allin', 'all-in'): act = 'jam'

    # 1. Usa hand_freq quando disponível (preciso por mão)
    if hand_freq:
        key_map = {
            'fold': 'fold', 'call': 'call', 'check': 'call',
            'raise': 'raise', 'bet': 'raise',
            'jam': 'allin',
        }
        key = key_map.get(act, act)
        freq = float(hand_freq.get(key, 0))
        # Push/fold (≤12bb = bucket 10bb): abrir = jammar. O range 10bb separa raise
        # (open/min-raise) de allin, mas em todo o bucket curto um open COMPROMETE o
        # stack — raise≈allin. Sem isso, QQ BTN @8bb (range: raise 96%) vira "leak" ao
        # dar shove, sendo que a 8bb jammar é a mesma decisão (você está committed).
        # Soma as duas freqs pra creditar o jam de qualquer mão que o GTO abre.
        if act == 'jam' and stack_bb <= 12:
            freq = float(hand_freq.get('allin', 0)) + float(hand_freq.get('raise', 0))
        # ── O espelho, que faltava ───────────────────────────────────────────────────────────
        # A adjacência era creditada em UMA direção só, apesar de o comentário acima justificá-la
        # com "raise≈allin". Consequência: min-raisar KK/QQ/AKs de CO a 10bb — jogada padrão de
        # regular de MTT — devolvia freq['raise']=0 e virava `major_leak` → `gto_critical`, que
        # pesa 0,45 no ranking de leaks e manda o aluno estudar um erro inexistente. Jammar a
        # MESMA mão no MESMO spot saía "Correto". Varredura do bucket 10bb: 326 de 449 pares
        # mão×posição cujo jam é `correct` tinham o min-raise marcado `major_leak`.
        #
        # Por que TETO em `acceptable` e não `correct`: a mão está no range, mas quem tem
        # frequência zero é o SIZING escolhido, e o custo medido pela própria carta é real ainda
        # que pequeno (mediana 0,029bb; 304 dos 326 abaixo do limiar de 0,12bb do motor). É
        # exatamente o veredito que a porta irmã já dá no mesmo caso — `_grade_por_no_capturado`
        # rebaixa para `acceptable` quando "a mao ESTA no range e joga alguma coisa; o que tem
        # frequencia zero e a ACAO escolhida". `acceptable` capeia o label em 'marginal' e o
        # gto_label em desvio leve: informa sem acusar.
        if act == 'raise' and stack_bb <= 12 and freq < 0.10:
            _vizinho = float(hand_freq.get('allin', 0)) + float(hand_freq.get('raise', 0))
            if _vizinho >= 0.30:
                return 'acceptable'
        if   freq >= 0.30: return 'correct'
        elif freq >= 0.10: return 'acceptable'
        elif freq >= 0.03: return 'leak'
        else:              return 'major_leak'

    # 2. Fallback (sem hand_freq): lógica binária original
    if in_rng and act in ('raise', 'jam'):    return 'correct'
    if in_rng and act == 'call':              return 'acceptable'
    if in_rng and act == 'fold':              return 'leak'
    if in_limp and act == 'call':             return 'correct'
    if in_limp and act in ('raise', 'jam'):   return 'acceptable'
    if in_limp and act == 'fold':             return 'leak'
    if not in_rng and not in_limp:
        if act == 'fold':                     return 'correct'
        if act in ('raise', 'jam'):
            return 'leak' if is_sb else ('major_leak' if stack_bb > 25 else 'leak')
        if act == 'call':
            return 'acceptable' if is_sb else 'leak'
    return 'acceptable'


def _vs_rfi_quality_new(action: str, in_rng: bool, rec: list, hand_freq: dict | None = None) -> str:
    """Quality classifier vs_RFI.

    Quando hand_freq disponível (freq EXATA da mão hero pelo GTO Wizard), classifica
    pela frequência GTO da ação tomada — mais preciso que verificar in/out range:
      freq >= 30%  → correct      (ação dominante ou frequente do GTO)
      10–30%       → acceptable   (ação válida do GTO mix, minoritária)
      3–10%        → leak         (ação raramente GTO)
      < 3%         → major_leak   (ação fora do GTO)

    Sem hand_freq, fallback pro classificador binário (in_rng/rec) original.
    """
    act = action.lower()
    if hand_freq:
        # Mapear action → key em hand_freq
        key_map = {
            'fold': 'fold',
            'call': 'call', 'check': 'call',
            'raise': 'raise', 'bet': 'raise',
            'jam': 'allin', 'allin': 'allin', 'shove': 'allin', 'all-in': 'allin',
        }
        key = key_map.get(act, act)
        freq = float(hand_freq.get(key, 0))
        if   freq >= 0.30: return 'correct'
        elif freq >= 0.10: return 'acceptable'
        elif freq >= 0.03: return 'leak'
        else:              return 'major_leak'

    # Fallback (sem hand_freq): lógica binária original
    if in_rng and act in rec:                     return 'correct'
    if in_rng and act == 'fold':                  return 'leak'
    if in_rng and act not in rec:                 return 'leak'
    if not in_rng and act == 'fold':              return 'correct'
    if not in_rng and act in ('raise', 'jam'):    return 'major_leak'
    if not in_rng and act == 'call':              return 'leak'
    return 'acceptable'


def _vs_rfi_quality(action: str, in_rng: bool, acoes: list) -> str:
    act  = action.lower()
    acts = {_ACT.get(a, a.lower()) for a in acoes}
    if in_rng and act in acts:                  return 'correct'
    if in_rng and act == 'fold':                return 'leak'
    if in_rng and act not in acts:              return 'leak'   # desvio dentro do range
    if not in_rng and act == 'fold':            return 'correct'
    if not in_rng and act in ('raise', 'jam'):  return 'major_leak'
    if not in_rng and act == 'call':            return 'leak'
    return 'acceptable'


def _vs_3bet_quality(action: str, in_4b: bool, in_cl: bool, *,
                     in_jam: bool = False, hand_freq: dict | None = None) -> str:
    act = action.lower()
    if act in ('shove', 'allin', 'all-in'):
        act = 'jam'
    # Classifica pela freq exata da mão quando disponível (mesma lógica do RFI)
    if hand_freq:
        key_map = {'fold': 'fold', 'call': 'call', 'check': 'call',
                   'raise': 'raise', 'bet': 'raise', 'jam': 'allin'}
        freq = float(hand_freq.get(key_map.get(act, act), 0))
        if   freq >= 0.30: return 'correct'
        elif freq >= 0.10: return 'acceptable'
        elif freq >= 0.03: return 'leak'
        else:              return 'major_leak'
    # Fallback binário (sem hand_freq)
    if in_4b and act in ('raise', 'jam'):       return 'correct'
    if in_cl and act == 'call':                  return 'correct'
    if in_jam and act == 'jam':                  return 'correct'
    if (in_4b or in_cl or in_jam) and act == 'fold': return 'leak'
    if not (in_4b or in_cl or in_jam) and act == 'fold': return 'correct'
    return 'major_leak'


# ── Professional notes ────────────────────────────────────────────────────────

def _rfi_notes(pos, hand, stack, pct, in_rng, action, *, in_limp: bool = False,
               hand_freq: dict | None = None) -> list[str]:
    notes = []
    label = _POS.get(pos, pos)
    pct_s = f"{pct*100:.0f}%"
    act   = action.lower()
    if in_rng:
        # Framing correto: se a mão é shove-dominante (hf_allin > hf_raise), é range de SHOVE,
        # não "abertura" (stack curto). A ~9bb ainda há min-raise (ex.: AA) que segue "abertura".
        _hf_r0 = float(hand_freq.get('raise', 0)) if hand_freq else 0.0
        _hf_a0 = float(hand_freq.get('allin', 0)) if hand_freq else 0.0
        if _hf_a0 > _hf_r0:
            notes.append(f"{label} dá shove com {pct_s} das mãos a {stack:.0f}bb. {hand} está no range de shove.")
        else:
            notes.append(f"{label} abre {pct_s} das mãos a {stack:.0f}bb — {hand} está no range de abertura.")
        # Pro_note baseado na freq EXATA da ação tomada (vs. dominante)
        hf_fold  = float(hand_freq.get('fold', 0))  if hand_freq else 0.0
        hf_raise = float(hand_freq.get('raise', 0)) if hand_freq else 0.0
        hf_allin = float(hand_freq.get('allin', 0)) if hand_freq else 0.0
        # Mapear ação → freq da ação tomada
        act_freq_map = {'fold': hf_fold, 'raise': hf_raise, 'bet': hf_raise,
                        'jam': hf_allin, 'shove': hf_allin, 'allin': hf_allin, 'call': 0.0}
        act_freq = act_freq_map.get(act, 0.0)
        # Ação dominante
        action_pcts = [('Fold', hf_fold), ('Raise', hf_raise), ('Shove', hf_allin)]
        action_pcts.sort(key=lambda x: -x[1])
        dom_name, dom_freq = action_pcts[0]
        act_label = {'fold': 'Fold', 'raise': 'Raise', 'bet': 'Raise',
                     'jam': 'Shove', 'shove': 'Shove', 'allin': 'Shove', 'call': 'Limp/Call'}.get(act, act.title())

        if hand_freq and (hf_raise > 0 or hf_allin > 0 or hf_fold > 0):
            if act_freq >= 0.50:
                notes.append(f"{act_label} é a ação dominante GTO pra {hand} ({act_freq*100:.0f}%).")
            elif act_freq >= 0.20:
                notes.append(f"{act_label} é GTO válido pra {hand} ({act_freq*100:.0f}%), mas {dom_name.lower()} é dominante ({dom_freq*100:.0f}%).")
            elif act_freq >= 0.03:
                notes.append(f"{act_label} é GTO raramente ({act_freq*100:.0f}%) pra {hand}. GTO prefere {dom_name.lower()} ({dom_freq*100:.0f}%).")
            else:
                notes.append(f"{act_label} com {hand} é leak — GTO sempre escolhe {dom_name.lower()} ({dom_freq*100:.0f}%) neste spot.")
        else:
            # Sem hand_freq: textos genéricos antigos
            if act == 'fold':
                notes.append(f"Foldar {hand} do {label} é um leak: GTO sempre joga essa mão neste spot.")
            elif act == 'call':
                notes.append("Limp desperdiça vantagem posicional. Raise/shove é a linha mais lucrativa aqui.")
            else:
                notes.append(f"Raise correto. {hand} é uma abertura sólida do {label} neste stack.")
    elif in_limp:
        notes.append(f"{hand} do {label} a {stack:.0f}bb — mão no range de limp (call) da small blind.")
        if act == 'call':
            notes.append(f"Limp correto. {hand} se beneficia de ver flop barato antes de agir após o BB.")
        elif act in ('raise', 'jam'):
            notes.append(f"Raise com {hand} é aceitável mas não optimal — o GTO prefere limp para explorar posição pós-flop.")
        elif act == 'fold':
            notes.append(f"Foldar {hand} do SB é um leak: a mão tem equity para limp e ver flop barato.")
    else:
        notes.append(f"{hand} está fora do range GTO do {label} a {stack:.0f}bb (range: top {pct_s}).")
        if act in ('raise', 'jam'):
            if stack <= 20:
                notes.append(f"Com {stack:.0f}bb o jogo é push/fold — {hand} não tem equity suficiente para shove aqui.")
            else:
                notes.append(f"Abrir {hand} do {label} é loose: perde EV contra os ranges de defesa dos oponentes.")
        elif act == 'fold':
            notes.append(f"Fold correto. {hand} não justifica entrada desta posição neste stack.")
    # Nota sobre stack — usa hand_freq quando disponível pra ser preciso.
    # Evita "essencialmente push/fold" quando GW indica raise sized é dominante (ex: QQ BTN 8bb).
    if hand_freq and in_rng:
        hf_r = float(hand_freq.get('raise', 0))
        hf_a = float(hand_freq.get('allin', 0))
        if hf_r > 0.7:
            # Raise sized é claramente dominante pra essa mão — não é push/fold puro
            if stack <= 15:
                notes.append(f"Mesmo com {stack:.0f}bb, GTO prefere raise sized ({hf_r*100:.0f}%) — {hand} mantém valor pós-flop.")
        elif hf_a > 0.7:
            # Allin é dominante — push/fold de fato
            notes.append(f"Com {stack:.0f}bb, GTO faz shove ({hf_a*100:.0f}%) com {hand} — maximiza fold equity.")
        elif hf_r > 0.2 and hf_a > 0.2:
            # Mix significativo entre raise e shove — zona transição
            notes.append(f"Stack {stack:.0f}bb em zona de transição: GTO mistura raise ({hf_r*100:.0f}%) e shove ({hf_a*100:.0f}%) com {hand}.")
    elif stack <= 15:
        # Fallback sem hand_freq (mão fora do range, ou v2 legacy) — genérico
        notes.append(f"Com {stack:.0f}bb a jogabilidade pós-flop é limitada — equity de mão e posição são prioridade.")
    elif stack <= 25:
        notes.append(f"Com {stack:.0f}bb a jogabilidade pós-flop é limitada — equity de mão e posição são prioridade.")
    return notes


def _vs_rfi_notes_new(pos, vs_pos, hand, stack, aggr_pct, in_rng, rec, action) -> list[str]:
    """Pro notes for RegLife vs_RFI format."""
    notes  = []
    label  = _POS.get(pos, pos)
    vs_lbl = _POS.get(vs_pos, vs_pos)
    aggr_s = f"{aggr_pct*100:.0f}%"
    act    = action.lower()
    rec_s  = '/'.join(r.title() for r in rec if r != 'fold')
    if in_rng:
        notes.append(f"{label} continua com {aggr_s} das mãos vs open do {vs_lbl} a {stack:.0f}bb — {hand} está no range de {rec_s or 'defesa'}.")
        if act == 'fold':
            notes.append(f"Foldar {hand} vs {vs_lbl} open é excessivamente tight e perde EV no longo prazo.")
        elif act in ('raise', 'jam') and rec == ['call']:
            notes.append(f"3bet com {hand} aqui não é optimal: GTO preconiza call (flat) neste spot.")
        elif act == 'call' and rec in (['raise'], ['jam']):
            notes.append(f"Call com {hand} é passivo: GTO preconiza 3bet neste spot.")
    else:
        notes.append(f"{hand} está fora do range de defesa do {label} vs {vs_lbl} open a {stack:.0f}bb (defende {aggr_s}).")
        if act == 'fold':
            notes.append(f"Fold correto. {hand} não tem equity suficiente para continuar vs range do {vs_lbl}.")
        elif act in ('raise', 'jam'):
            notes.append(f"3bet com {hand} não é sustentado pelo GTO: range de 3bet do {label} vs {vs_lbl} é mais apertado.")
        elif act == 'call':
            notes.append(f"Flat com {hand} fora do range perde EV no longo prazo.")
    return notes


def _vs_rfi_notes(pos, vs_pos, hand, stack, pct, in_rng, action, acoes) -> list[str]:
    notes  = []
    label  = _POS.get(pos, pos)
    vs_lbl = _POS.get(vs_pos, vs_pos)
    pct_s  = f"{pct*100:.0f}%"
    acts_s = '/'.join(a.title() for a in acoes if a != 'FOLD')
    act    = action.lower()
    if in_rng:
        notes.append(f"{label} continua com {pct_s} das mãos vs open do {vs_lbl} — {hand} está no range de {acts_s}.")
        if act == 'fold':
            notes.append(f"Foldar {hand} vs {vs_lbl} open é excessivamente tight e perde EV no longo prazo.")
    else:
        notes.append(f"{hand} está fora do range de defesa do {label} vs {vs_lbl} open a {stack:.0f}bb.")
        if act == 'fold':
            notes.append(f"Fold correto. {hand} não tem equity suficiente para continuar vs o range de abertura do {vs_lbl}.")
        elif act in ('raise', 'jam'):
            notes.append(f"3bet com {hand} aqui não é sustentado pelo GTO — range de 3bet do {label} vs {vs_lbl} é mais apertado.")
    return notes


def _vs_3bet_notes(pos, hand, stack, pct, in_4b, in_cl, action, scenario='vs_3bet') -> list[str]:
    notes = []
    label = _POS.get(pos, pos)
    pct_s = f"{pct*100:.0f}%"
    act   = action.lower()
    # termo do villain (o que o hero enfrenta) e verbo do hero (ação agressiva) por cenário
    term      = 'squeeze' if scenario in ('faces_squeeze', 'squeeze') else ('4bet' if scenario == 'vs_4bet' else '3bet')
    hero_verb = '5bet/jam' if scenario == 'vs_4bet' else '4bet'
    if scenario == 'squeeze':
        # Hero É o squeezador (raise/shove sobre open + cold call) — não responde a um.
        if in_4b:
            notes.append(f"{hand} do {label} squeeza (raise/shove sobre open + cold call) — mão no topo do range ({pct_s} squeezam).")
            if act == 'fold':
                notes.append(f"Foldar {hand} aqui perde EV: a mão está no range de squeeze.")
        elif in_cl:
            notes.append(f"{hand} do {label} faz over-call vs o open + cold call — {pct_s} continuam.")
            if act == 'fold':
                notes.append(f"Foldar {hand} aqui é tight demais — a mão tem força para continuar 3-way.")
        elif act in ('raise', 'jam', 'call'):
            notes.append(f"Squeeze/call com {hand} aqui perde EV: fora do range para esse spot 3-way.")
        return notes
    if in_4b:
        notes.append(f"{hand} do {label} faz {hero_verb} vs {term} — mão no topo do range de continuação ({pct_s} continuam).")
        if act == 'fold':
            notes.append(f"Foldar {hand} vs {term} é grande erro de EV: esta mão está no range de {hero_verb}.")
    elif in_cl:
        notes.append(f"{hand} do {label} faz call vs {term} — range de continuação é {pct_s} das mãos.")
        if act == 'fold':
            notes.append(f"Foldar {hand} vs {term} é tight demais — a mão tem equity para continuar.")
    else:
        # Fora do range: o "why" do card já diz "fora do range" → não duplicar. Só
        # adiciona nota quando o jogador DESVIA (continua), pra explicar o erro.
        if act in ('raise', 'jam', 'call'):
            notes.append(f"Continuar com {hand} vs {term} perde EV: a mão não tem equity vs o range de {term} do oponente.")
    return notes


def _pushfold_quality(action: str, in_shove: bool) -> str:
    act = action.lower()
    if in_shove and act in ('jam', 'raise'):     return 'correct'
    if in_shove and act == 'fold':               return 'major_leak'  # foldar mão shove = máxima perda de EV
    if in_shove and act == 'call':               return 'acceptable'
    if not in_shove and act == 'fold':           return 'correct'
    if not in_shove and act in ('jam', 'raise'): return 'major_leak'
    if not in_shove and act == 'call':           return 'leak'
    return 'acceptable'


def _pushfold_notes(pos, hand, stack, shove_pct, in_shove, action, *, is_reshove=False) -> list[str]:
    notes = []
    label  = _POS.get(pos, pos)
    pct_s  = f"{shove_pct*100:.0f}%"
    act    = action.lower()
    verb   = "reshove" if is_reshove else "shove"
    if in_shove:
        notes.append(f"{label} faz {verb} com {pct_s} das mãos a {stack:.0f}bb (GTO push/fold) — {hand} está no range.")
        if act == 'fold':
            notes.append(f"Foldar {hand} a {stack:.0f}bb é um leak: a mão tem equity suficiente para {verb}.")
        elif act == 'call':
            notes.append(f"Call a {stack:.0f}bb é passivo — {verb}/shove maximiza fold equity e EV esperado.")
    else:
        notes.append(f"{hand} está fora do range de {verb} do {label} a {stack:.0f}bb (range: top {pct_s}).")
        if act in ('jam', 'raise'):
            notes.append(f"{verb.capitalize()} com {hand} não é lucrativo neste stack — a mão não tem equity vs calls dos oponentes.")
        elif act == 'fold':
            notes.append(f"Fold correto. {hand} não justifica {verb} desta posição a {stack:.0f}bb.")
    notes.append(f"Stack de {stack:.0f}bb: jogo é essencialmente push/fold — ranges baseados em GTO sem ICM.")
    return notes


def _find_opener_key(vs_rfi: dict, opener_pos: str) -> Optional[str]:
    if not opener_pos:
        return None
    # New format: direct position key
    if opener_pos in vs_rfi and isinstance(vs_rfi[opener_pos], dict):
        return opener_pos
    # Old format: "{pos}_open"
    key = f"{opener_pos}_open"
    return key if key in vs_rfi else None
