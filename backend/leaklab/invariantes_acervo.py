# -*- coding: utf-8 -*-
"""Invariantes do ACERVO — o que nenhuma linha gravada pode ser, nunca.

── Por que este arquivo existe ────────────────────────────────────────────────────────────────

A suite deste projeto testa FUNÇÕES: dado este input, o motor devolve aquele veredito. Isso prova
que o conserto funciona. Não prova que o acervo está limpo. As duas coisas se separaram na
prática: em 10/08 uma auditoria de seis lentes sobre um snapshot de produção achou 48 defeitos
candidatos e nenhum deles tinha teste vermelho — a suíte inteira passava com 567 acusações no ar,
2.355 mesas de zero jogadores e um dashboard publicando 7.669 bb/100 onde o número honesto era 9,8.

O buraco não era falta de teste. Era o tipo de teste. Um teste de conserto responde "o guarda X
funciona?"; uma varredura responde "existe alguma linha que viola X?". A segunda pergunta é a que
o produto faz na tela, e ninguém estava fazendo.

── Como funciona ──────────────────────────────────────────────────────────────────────────────

Cada invariante declara o que é impossível, ONDE isso chega na tela, e quantas violações existem
hoje (`baseline`). A varredura falha quando um número CRESCE — e o baseline só desce, nunca sobe.
Um conserto que zera uma família também zera o baseline dela, no mesmo commit.

Baseline diferente de zero é dívida declarada, não invariante quebrada. A alternativa (esperar
tudo zerar antes de ligar a varredura) deixaria a rede desligada justamente durante os consertos,
que é quando ela pega mais coisa.

── A regra que este arquivo tem de obedecer ───────────────────────────────────────────────────

CLAUDE.md, item 1: diagnóstico precisa PROVAR que detecta. Toda invariante aqui traz um `forjar`,
e `tests/test_invariantes_acervo.py` insere a violação forjada num banco limpo e exige que a
sonda vá de 0 para 1 — e que NENHUMA outra sonda reaja. Sonda sem `forjar` não entra na lista.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Callable, List, Optional, Sequence

from leaklab.decision_engine_v11 import _norm_gto_action

# Rótulos que o produto exibe como erro. Fonte: CLAUDE.md e `verdict3`.
ACUSADAS = ('small_mistake', 'clear_mistake', 'critical')

# Cartas que o hero já viu quando toma a decisão daquela street.
CARTAS_VISIVEIS = {'preflop': 0, 'flop': 3, 'turn': 4, 'river': 5}


@dataclass
class Violacao:
    id_linha: object
    detalhe: str


@dataclass
class Invariante:
    id: str
    titulo: str
    """O que é impossível, em uma frase."""
    porta: str
    """Onde isso chega ao jogador. Invariante sem porta é curiosidade, não defeito."""
    baseline: int
    """Violações conhecidas hoje. A varredura falha se o medido PASSAR daqui."""
    medir: Callable[[object], List[Violacao]]
    forjar: Callable[[object], None]
    """Insere exatamente UMA violação. Sem isto a sonda não prova que enxerga."""
    origem: str = ''
    """Onde o defeito foi achado, para quem for consertar."""
    banco_isolado: bool = False
    """A sonda olha a COLUNA, não a linha: só acusa se TODAS as linhas estiverem mortas.

    Uma forja não consegue matar uma coluna que já tem linhas sãs, então o teste roda estas num
    banco só delas. Em troca elas ganham `curar`, e o teste exige o caminho de volta: com uma
    linha viva a sonda tem de calar. Sem esse segundo lado, a sonda poderia estar acusando sempre.
    """
    curar: Optional[Callable[[object], None]] = None
    """Insere a linha que faz a sonda calar. Obrigatório quando `banco_isolado`."""
    sobrepoe: Sequence[str] = ()
    """Outras sondas que a MESMA forja legitimamente aciona, e o teste aceita.

    Sobreposição declarada é diferente de sonda larga. Uma acusação de shove-contra-jam é ao
    mesmo tempo "punido pela grafia" e "acusado do que foi recomendado" — são dois defeitos com
    dois consertos diferentes que compartilham linhas. O que o teste não aceita é sobreposição
    NÃO declarada, que quase sempre significa forja quebrando mais de uma coisa por descuido.
    """


# ── utilidades de leitura ──────────────────────────────────────────────────────────────────────

def _linhas(conn, sql: str, params: Sequence = ()) -> List[dict]:
    """Lê como lista de dicts, funcionando em SQLite e no adaptador de Postgres do projeto.

    O adaptador normaliza `?` → `%s`, então o SQL aqui usa `?` e vale nos dois bancos.

    Só `fetchall()`, nunca `cursor.description`: no Postgres o `execute` devolve um `_PgResult`,
    que emula a interface do sqlite3 sem expor `description`. A primeira versão desta função usava
    `description` e passou em toda a suíte — que roda em SQLite — para estourar `AttributeError`
    na primeira execução contra produção. `_PgResult.fetchall()` já devolve dicts; o `sqlite3.Row`
    vira dict com o mesmo `dict(r)`.
    """
    cur = conn.execute(sql, tuple(params)) if params else conn.execute(sql)
    return [dict(r) for r in cur.fetchall()]


def _tid_qualquer(conn) -> object:
    """Um tournament_id existente, para as forjas respeitarem a FK."""
    r = _linhas(conn, 'SELECT id FROM tournaments LIMIT 1')
    return r[0]['id'] if r else None


#: Uma decisão SÃ: nenhuma invariante deste arquivo reage a ela. É o esqueleto sobre o qual cada
#: forja troca um campo só — assim o teste sabe que a sonda reagiu ao defeito, e não ao esqueleto.
LINHA_SA = dict(
    hand_id='SA', street='preflop', hero_cards='AsKs', board='[]',
    action_taken='call', best_action='call', label='standard', score=0.5,
    num_players=9, n_active_opponents=3, position='BTN',
    stack_bb=30.0, effective_stack_bb=30.0, pot_size=3.0, facing_bet=2.0,
    facing_to_call_bb=2.0, estimated_equity=0.62,
    ev_loss_bb=0.3, ev_loss_source='gw_har',
    gto_label='gto_correct', gto_action='call', gto_played_freq=0.8, gto_top_freq=0.8,
    hero_won_hand=1, multiway_safe_verdict='ok', hero_was_aggressor=0,
)

#: A irmã postflop da linha sã. Existe para as sondas de coluna morta que só olham o postflop:
#: sem ela, qualquer forja de flop acusaria COL-AGRESSOR de tabela.
LINHA_SA_POSTFLOP = dict(LINHA_SA, hand_id='SA-POST', street='flop',
                         board='["2h","7c","2d"]', hero_was_aggressor=1)


def _forjar_linha(conn, **campos) -> None:
    """Insere uma decisão sã com os campos dados trocados. Um defeito por forja."""
    base = LINHA_SA_POSTFLOP if campos.get('street') in ('flop', 'turn', 'river') else LINHA_SA
    d = dict(base)
    d.update(campos)
    d['hand_id'] = 'FORJA'
    d['tournament_id'] = _tid_qualquer(conn)
    cols = ', '.join(d)
    marc = ', '.join('?' for _ in d)
    conn.execute(f'INSERT INTO decisions ({cols}) VALUES ({marc})', tuple(d.values()))


# ── as invariantes ─────────────────────────────────────────────────────────────────────────────

def _ev_acima_do_teto(conn):
    """O EV perdido não pode passar do que havia em jogo: pote + os dois stacks.

    É o mesmo teto que `ev_loss_trustworthy` aplica no motor. Aqui ele vira invariante de DADO
    porque enquanto a linha existir, basta uma porta esquecer o filtro para o número chegar à
    tela — foi o que aconteceu com `-3588 bb` num stack de 32,2bb, e depois de novo em
    `get_ev_summary` e em `coach_replay`.
    """
    return [Violacao(r['id'], f"ev={r['ev_loss_bb']:.1f} teto={r['teto']:.1f} stack={r['stack_bb']}")
            for r in _linhas(conn, """
                SELECT id, ev_loss_bb, stack_bb,
                       COALESCE(pot_size,0) + 2*COALESCE(stack_bb,0) AS teto
                  FROM decisions
                 WHERE ev_loss_bb IS NOT NULL
                   AND ABS(ev_loss_bb) > COALESCE(pot_size,0) + 2*COALESCE(stack_bb,0)""")]


def _mesa_impossivel(conn):
    """Uma decisão existe porque há mesa. `num_players` nunca pode ser menor que 2.

    Com 0, `_detect_icm_pressure` cai no `if active_players <= 3: return 'high'` antes de olhar o
    M, e `_ICM_EXCLUDED='high'` some com a linha do ranking de leaks e do plano de estudo.
    """
    return [Violacao(r['id'], f"num_players={r['num_players']} position={r['position']} "
                              f"n_active_opponents={r['n_active_opponents']}")
            for r in _linhas(conn, """
                SELECT id, num_players, position, n_active_opponents FROM decisions
                 WHERE num_players IS NULL OR num_players < 2""")]


def _freq_jogada_acima_da_modal(conn):
    """A frequência da ação jogada não pode passar da frequência da ação MODAL.

    `gto_top_freq` é o máximo da estratégia do nó. `played > top` significa que os dois números
    descrevem ações diferentes, e o card imprime os dois lado a lado.
    """
    return [Violacao(r['id'], f"played={r['gto_played_freq']} top={r['gto_top_freq']} "
                              f"gto_action={r['gto_action']}")
            for r in _linhas(conn, """
                SELECT id, gto_played_freq, gto_top_freq, gto_action FROM decisions
                 WHERE gto_played_freq IS NOT NULL AND gto_top_freq IS NOT NULL
                   AND gto_played_freq > gto_top_freq""")]


def _acusa_o_que_recomenda(conn):
    """Não se acusa uma decisão quando a ação recomendada É a ação jogada.

    O gerador de texto do produto já assume isso (`api/app.py` só escreve "o esperado era Y"
    quando Y difere), mas o veredito não faz a mesma checagem: o card mostra "✗ Erro" com a
    coluna "ideal" repetindo o que o jogador fez.

    A comparação usa `_norm_gto_action` do próprio motor — shove, jam e allin são a mesma jogada.
    """
    fora = []
    for r in _linhas(conn, """
            SELECT id, action_taken, best_action, label, gto_label FROM decisions
             WHERE label IN ('small_mistake','clear_mistake','critical')
               AND best_action IS NOT NULL"""):
        if _norm_gto_action(r['best_action']) == _norm_gto_action(r['action_taken']):
            fora.append(Violacao(r['id'], f"{r['action_taken']} acusado de {r['label']} "
                                          f"com best_action={r['best_action']}"))
    return fora


def _punido_pela_grafia(conn):
    """Mesma jogada escrita de outro jeito não é desvio.

    `calc_base_action_gap` e `calc_range_penalty` comparam a string crua enquanto o
    `math_penalty`, na MESMA expressão de score, normaliza. Um 'shove' contra um 'jam' custa
    0,18 de gap e 0,08 de range_penalty por causa da palavra.
    """
    fora = []
    for r in _linhas(conn, """
            SELECT id, action_taken, best_action, label, score FROM decisions
             WHERE label <> 'standard' AND best_action IS NOT NULL
               AND action_taken <> best_action"""):
        if _norm_gto_action(r['best_action']) == _norm_gto_action(r['action_taken']):
            fora.append(Violacao(r['id'], f"{r['action_taken']} vs {r['best_action']} "
                                          f"→ {r['label']} score={r['score']}"))
    return fora


def _solver_acusa_produto_absolve(conn):
    """Quando o solver diz que a ação tem 0% de frequência, o produto não pode dar 'standard'.

    O piso é do próprio motor (`_gto_label_cap`: gto_critical → mínimo small_mistake). As linhas
    que escapam vêm do guarda `_sem_gabarito`, que é do PREFLOP e dispara em todo postflop.
    """
    return [Violacao(r['id'], f"{r['street']} gto_critical → label={r['label']} score={r['score']} "
                              f"facing={r['facing_to_call_bb']} eff={r['effective_stack_bb']}")
            for r in _linhas(conn, """
                SELECT id, street, label, score, facing_to_call_bb, effective_stack_bb
                  FROM decisions
                 WHERE gto_label = 'gto_critical' AND label = 'standard'""")]


def _selo_contradiz_veredito(conn):
    """O selo 'GTO Correto' e o veredito de erro não podem conviver na mesma linha.

    São duas respostas para a mesma pergunta, exibidas a três centímetros uma da outra.
    """
    return [Violacao(r['id'], f"gto_correct + label={r['label']} (played={r['gto_played_freq']})")
            for r in _linhas(conn, """
                SELECT id, label, gto_played_freq FROM decisions
                 WHERE gto_label = 'gto_correct'
                   AND label IN ('small_mistake','clear_mistake','critical')""")]


def _nota_perfeita_sem_gabarito(conn):
    """`score = 0.0` é a nota perfeita. Sem gabarito e discordando da ação, ela é mentira.

    Não é o "sem gabarito não é erro" que já foi decidido — ali o produto se cala. Aqui ele
    AFIRMA acerto máximo numa linha em que o próprio motor recomenda outra coisa.
    """
    fora = []
    for r in _linhas(conn, """
            SELECT id, score, best_action, action_taken, gto_label FROM decisions
             WHERE score = 0.0 AND best_action IS NOT NULL
               AND (gto_label IS NULL OR gto_label = '' OR gto_label = 'uncovered')"""):
        if _norm_gto_action(r['best_action']) != _norm_gto_action(r['action_taken']):
            fora.append(Violacao(r['id'], f"score=0.0 sem gabarito, jogou {r['action_taken']} "
                                          f"e o motor queria {r['best_action']}"))
    return fora


def _board_do_futuro(conn):
    """A decisão não pode guardar cartas que o hero ainda não tinha visto.

    O corte por street é feito na LEITURA, em mais de um ponto — e já houve três meses gravando
    com uma chave e procurando com outra por causa de um consumidor que esqueceu de cortar.
    Enquanto a coluna trouxer o runout inteiro, cada consumidor novo é uma chance de vazar o
    river num card de flop.
    """
    fora = []
    for r in _linhas(conn, 'SELECT id, street, board FROM decisions WHERE board IS NOT NULL'):
        limite = CARTAS_VISIVEIS.get((r['street'] or '').lower())
        if limite is None:
            continue
        try:
            cartas = json.loads(r['board'] or '[]')
        except (TypeError, ValueError):
            continue
        if isinstance(cartas, list) and len(cartas) > limite:
            fora.append(Violacao(r['id'], f"{r['street']} com {len(cartas)} cartas: {cartas}"))
    return fora


def _fold_acusado_com_preco_ruim(conn):
    """Não se acusa um fold quando a própria linha mostra equity abaixo do pot odds.

    Os dois números aparecem no card ao lado do veredito. Se a equity exibida não paga o preço
    exibido, chamar o fold de erro é o card se contradizendo na mesma tela.
    """
    return [Violacao(r['id'], f"{r['street']} eq={r['estimated_equity']:.3f} < "
                              f"odds={r['facing_to_call_bb']/(r['pot_size']+r['facing_to_call_bb']):.3f} "
                              f"→ {r['label']}")
            for r in _linhas(conn, """
                SELECT id, street, estimated_equity, facing_to_call_bb, pot_size, label
                  FROM decisions
                 WHERE action_taken = 'fold'
                   AND label IN ('clear_mistake','critical')
                   AND estimated_equity IS NOT NULL AND pot_size IS NOT NULL
                   AND facing_to_call_bb > 0
                   AND estimated_equity < facing_to_call_bb/(pot_size+facing_to_call_bb)""")]


def _ev_sem_procedencia(conn):
    """Número de EV sem fonte declarada não pode ser gravado — a régua depende da fonte."""
    return [Violacao(r['id'], f"ev={r['ev_loss_bb']} sem ev_loss_source")
            for r in _linhas(conn, """
                SELECT id, ev_loss_bb FROM decisions
                 WHERE ev_loss_bb IS NOT NULL
                   AND (ev_loss_source IS NULL OR ev_loss_source = '')""")]


def _coluna_morta(coluna: str, filtro: str = ''):
    """Coluna que o INSERT nunca preenche: existe no schema, está 100% nula, e alguma tela a lê.

    A violação é a COLUNA, não a linha — por isso devolve 0 ou 1. Foi assim que
    `multiway_safe_verdict` passou despercebida: nenhuma linha estava errada, o campo inteiro é
    que nunca chegou.
    """
    onde = filtro or '1=1'

    def medir(conn):
        tot = _linhas(conn, f'SELECT COUNT(*) AS n FROM decisions WHERE {onde}')[0]['n']
        if not tot:
            return []          # tabela vazia não prova coluna morta
        vivos = _linhas(conn, f'SELECT COUNT(*) AS n FROM decisions '
                              f'WHERE {onde} AND {coluna} IS NOT NULL')[0]['n']
        if vivos:
            return []
        return [Violacao(coluna, f'{coluna} nula em {tot} de {tot} linhas'
                                 + (f' onde {filtro}' if filtro else ''))]
    return medir


def _coluna_constante(coluna: str, valor_morto, filtro: str = ''):
    """Coluna que é gravada, mas sempre com o mesmo valor onde deveria variar.

    Diferente de `_coluna_morta`: aqui o INSERT preenche, então nenhum teste de nulo acusa. O
    `hero_was_aggressor` passou assim — 0 em 2.903 de 2.903 decisões postflop, com a coluna viva
    no preflop, onde ela significa menos.
    """
    onde = filtro or '1=1'

    def medir(conn):
        tot = _linhas(conn, f'SELECT COUNT(*) AS n FROM decisions WHERE {onde}')[0]['n']
        if not tot:
            return []
        outros = _linhas(conn, f'SELECT COUNT(*) AS n FROM decisions WHERE {onde} '
                               f'AND ({coluna} IS NULL OR {coluna} <> ?)',
                         (valor_morto,))[0]['n']
        if outros:
            return []
        return [Violacao(coluna, f'{coluna} = {valor_morto} em {tot} de {tot} linhas'
                                 + (f' onde {filtro}' if filtro else ''))]
    return medir


INVARIANTES: List[Invariante] = [
    Invariante(
        id='EV-TETO', baseline=60,
        titulo='EV perdido acima do que havia em jogo (pote + 2 stacks)',
        porta='DashboardV2 "−X bb/100", card "Onde você sangra", relatório de replay do coach',
        origem='auditoria 10/08, lente de escala — confirmado por 2 céticos',
        medir=_ev_acima_do_teto,
        forjar=lambda c: _forjar_linha(c, ev_loss_bb=9999.0, stack_bb=10.0, pot_size=3.0,
                                       ev_loss_source='solver_hand'),
    ),
    Invariante(
        id='MESA', baseline=2355,
        titulo='num_players menor que 2 — mesa que não existe',
        porta='icm_pressure="high" força exclusão do ranking de leaks e do plano de estudo',
        origem='auditoria 10/08, lentes de nulos e de escala — confirmado por 2 céticos',
        medir=_mesa_impossivel,
        forjar=lambda c: _forjar_linha(c, num_players=0, position='UTG+2', n_active_opponents=5),
    ),
    Invariante(
        id='FREQ', baseline=43,
        titulo='frequência da ação jogada acima da frequência da ação modal',
        porta='card do replayer imprime as duas frequências lado a lado',
        origem='auditoria 10/08, lente de contradição — confirmado por 2 céticos',
        medir=_freq_jogada_acima_da_modal,
        forjar=lambda c: _forjar_linha(c, gto_played_freq=1.0, gto_top_freq=0.0,
                                       gto_action='check', gto_label='gto_mixed'),
    ),
    Invariante(
        id='AUTO', baseline=15,
        titulo='decisão acusada em que a ação recomendada é a ação jogada',
        porta='card exibe "✗ Erro" com a coluna ideal repetindo o que o jogador fez',
        origem='auditoria 10/08, achado por duas lentes — confirmado por 2 céticos. '
               'Relabel de 11/08 levou 20 → 15: os 5 shove/jam sairam com o conserto da grafia. '
               'Os 15 restantes sao 12 fold/fold, 2 check/check e 1 call/call, e dependem de uma '
               'decisao de produto: rebaixar o veredito ou corrigir a recomendacao.',
        medir=_acusa_o_que_recomenda,
        forjar=lambda c: _forjar_linha(c, action_taken='fold', best_action='fold',
                                       label='small_mistake', score=0.19, gto_label=None),
    ),
    Invariante(
        id='GRAFIA', baseline=2,
        titulo='mesma jogada com outra palavra tratada como desvio (shove vs jam)',
        porta='score e label do card, e a nota "Ação esperada: ALL-IN" para quem deu all-in',
        origem='auditoria 10/08, lente de contradição — confirmado por 2 céticos',
        medir=_punido_pela_grafia,
        sobrepoe=('AUTO',),   # uma acusacao ortografica e, por definicao, uma auto-acusacao
        forjar=lambda c: _forjar_linha(c, action_taken='shove', best_action='jam',
                                       label='small_mistake', score=0.2565, gto_label=None),
    ),
    Invariante(
        id='MUDO', baseline=19,
        titulo='solver diz 0% de frequência e o produto devolve "standard"',
        porta='veredito do card e score exibido; o piso é do próprio _gto_label_cap',
        origem='auditoria 10/08, lente de cobertura — confirmado por 2 céticos',
        medir=_solver_acusa_produto_absolve,
        forjar=lambda c: _forjar_linha(c, gto_label='gto_critical', label='standard', score=0.0,
                                       street='flop', board='["2h","7c","2d"]'),
    ),
    Invariante(
        id='SELO', baseline=2,
        titulo='selo "GTO Correto" convivendo com veredito de erro na mesma linha',
        porta='card do replayer: selo e veredito a três centímetros um do outro',
        origem='medido em 10/08 sobre o snapshot, com controle. Relabel de 11/08 levou 12 → 2 '
               'ao unificar o piso de direcao. As 2 que sobraram sao de outra familia: postflop '
               'com frequencia ALTA (0,60 e 0,90) e perda de EV real (1,93bb e 2,56bb) — o '
               'solver toma a acao quase sempre E ela custa. Nao e contradicao de piso.',
        medir=_selo_contradiz_veredito,
        forjar=lambda c: _forjar_linha(c, gto_label='gto_correct', label='clear_mistake',
                                       score=0.7, action_taken='call', best_action='fold'),
    ),
    Invariante(
        id='NOTA', baseline=45,
        titulo='nota perfeita (score 0.0) sem gabarito e discordando da própria recomendação',
        porta='score exibido no card e usado no ELO',
        origem='medido em 10/08 sobre o snapshot, com controle',
        medir=_nota_perfeita_sem_gabarito,
        forjar=lambda c: _forjar_linha(c, score=0.0, gto_label=None, action_taken='fold',
                                       best_action='call'),
    ),
    Invariante(
        id='BOARD', baseline=6070,
        titulo='board gravado com cartas que o hero ainda não tinha visto',
        porta='mesa exibida ao lado do veredito; e cada consumidor novo que esquecer de cortar',
        origem='medido em 10/08 sobre o snapshot (4.456 preflop, 1.042 flop, 572 turn)',
        medir=_board_do_futuro,
        forjar=lambda c: _forjar_linha(c, street='flop', board='["2h","7c","2d","Qs","4h"]'),
    ),
    Invariante(
        id='ODDS', baseline=16,
        titulo='fold acusado com a equity da própria linha abaixo do pot odds da própria linha',
        porta='card mostra equity, preço e veredito juntos',
        origem='medido em 10/08 sobre o snapshot (13 no flop), com coorte de controle',
        medir=_fold_acusado_com_preco_ruim,
        forjar=lambda c: _forjar_linha(c, street='flop', board='["2h","7c","2d"]',
                                       action_taken='fold', best_action='call',
                                       label='clear_mistake', score=0.8,
                                       estimated_equity=0.10, pot_size=10.0,
                                       facing_to_call_bb=10.0, gto_label='gto_critical'),
    ),
    Invariante(
        id='PROCED', baseline=5,
        titulo='ev_loss_bb gravado sem ev_loss_source',
        porta='a régua ev_loss_trustworthy decide pela fonte; sem fonte ela chuta',
        origem='medido em 10/08 sobre o snapshot',
        medir=_ev_sem_procedencia,
        forjar=lambda c: _forjar_linha(c, ev_loss_bb=1.2, ev_loss_source=None, stack_bb=30.0),
    ),
    Invariante(
        id='COL-GANHOU', baseline=1, banco_isolado=True,
        titulo='hero_won_hand nunca é gravada',
        porta='card "Resultado vs GTO" publica 0 e 0,0% como se fosse medição',
        origem='medido em 10/08: 9.813 de 9.813 nulas',
        medir=_coluna_morta('hero_won_hand'),
        forjar=lambda c: _forjar_linha(c, hero_won_hand=None),
        curar=lambda c: _forjar_linha(c, hero_won_hand=1),
    ),
    Invariante(
        id='COL-MULTIWAY', baseline=1, banco_isolado=True,
        titulo='multiway_safe_verdict nunca é gravada',
        porta='é a coluna que decide se um erro multiway aparece; nula, o produto cala',
        origem='medido em 10/08: 9.813 de 9.813 nulas',
        medir=_coluna_morta('multiway_safe_verdict'),
        forjar=lambda c: _forjar_linha(c, multiway_safe_verdict=None),
        curar=lambda c: _forjar_linha(c, multiway_safe_verdict='ok'),
    ),
    Invariante(
        id='COL-AGRESSOR', baseline=1, banco_isolado=True,
        titulo='hero_was_aggressor é sempre 0 no postflop',
        porta='sizing, leitura de range e escolha de nó postflop dependem dela',
        origem='medido em 10/08: 2.903 de 2.903 postflop com 0 (controle: 214 preflop com 1)',
        medir=_coluna_constante('hero_was_aggressor', 0, "street <> 'preflop'"),
        forjar=lambda c: _forjar_linha(c, street='flop', board='["2h","7c","2d"]',
                                       hero_was_aggressor=0),
        curar=lambda c: _forjar_linha(c, street='turn', board='["2h","7c","2d","Qs"]',
                                      hero_was_aggressor=1),
    ),
]


def varrer(conn, invariantes: Optional[Sequence[Invariante]] = None) -> List[dict]:
    """Roda todas as sondas e devolve o resultado de cada uma, sem julgar."""
    saida = []
    for inv in (invariantes or INVARIANTES):
        vs = inv.medir(conn)
        saida.append({
            'id': inv.id, 'titulo': inv.titulo, 'porta': inv.porta,
            'baseline': inv.baseline, 'medido': len(vs),
            'delta': len(vs) - inv.baseline,
            'exemplos': [f'{v.id_linha}: {v.detalhe}' for v in vs[:3]],
        })
    return saida


def regressoes(resultado: Sequence[dict]) -> List[dict]:
    """As que PIORARAM. É só isto que derruba a varredura."""
    return [r for r in resultado if r['medido'] > r['baseline']]


def melhorias(resultado: Sequence[dict]) -> List[dict]:
    """As que melhoraram e cujo baseline precisa DESCER no mesmo commit do conserto."""
    return [r for r in resultado if r['medido'] < r['baseline']]
