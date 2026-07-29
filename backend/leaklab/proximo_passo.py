# -*- coding: utf-8 -*-
"""O PRÓXIMO PASSO do aluno — a fonte única da prescrição de treino.

Spec: specs/cobranca-proximo-passo.md (§2). O motor pedagógico inteiro era pull: missão, gate,
reabertura e SRS só agiam quando o aluno aparecia. Este módulo decide, no servidor, qual é A
próxima ação — uma, não um menu — e todas as superfícies (dashboard, sino, resposta do upload,
e-mails) consomem a MESMA decisão. Superfícies que decidem sozinhas divergem; é a lição do
StrategyProvider e do veredito de 3 níveis.

A decisão é uma função PURA (`decidir_proximo_passo`): recebe os fatos já carregados e o
relógio por parâmetro, não faz I/O. É o que permite forjar cada precedência em teste e
falsificar a ordem — o molde é `decidir_cadencia_relatorio`, que provou o desenho.

Precedência (spec §2.2), da mais urgente para a menos:
  1. Leak REABERTO sem sessão posterior — o jogo real desmentiu o treino.
  2. Revisão SRS vencida (drills e ranges, unificados POR DATA, não por tipo).
  3. Missão em curso do protocolo.
  4. Carta nova de memorização do alvo; sem ela, o desafio diário não feito.
  5. Nada — e nada é resposta válida: a UI mostra descanso, nunca inventa urgência.
"""
from __future__ import annotations


def _passo(tipo: str, titulo: str, porque: str, custo_min: int, cta_url: str,
           ev_loss_bb: float | None = None, n_maos: int | None = None) -> dict:
    """O shape ÚNICO do passo (spec §2.1). Toda superfície renderiza isto, nada além disto."""
    return {'tipo': tipo, 'titulo': titulo, 'porque': porque, 'custo_min': custo_min,
            'cta_url': cta_url, 'ev_loss_bb': ev_loss_bb, 'n_maos': n_maos}


def decidir_proximo_passo(agora: str, *,
                          reabertos: list | None = None,
                          revisoes: dict | None = None,
                          missao: dict | None = None,
                          carta_nova: dict | None = None,
                          desafio_pendente: bool = False) -> list[dict]:
    """Devolve a FILA de passos, do mais urgente para o menos. Vazia = aluno em dia.

    Pura de propósito: sem banco, sem relógio próprio (`agora` chega como parâmetro ISO).
    O chamador serve `fila[0]` como o passo e `fila[1:3]` como contexto.

    Entradas:
      reabertos:  [{'category_key','titulo','ev_loss_bb','n','reopened_at','treinou_depois'}]
                  Só entra na precedência 1 quem NÃO treinou depois da reabertura — quem já
                  voltou ao treino não precisa ser acordado para isso.
      revisoes:   {'drills': int, 'ranges': int, 'mais_antiga': iso|None}
      missao:     a missão ATIVA de missions_with_state (ou None)
      carta_nova: sugestão de sugerir_memorizacao_de_range (ou None)
      desafio_pendente: o desafio diário de hoje ainda não foi feito
    """
    fila: list[dict] = []

    # 1 ── Reaberto: a única situação em que o sistema SABE que o aluno regrediu no jogo real.
    pendentes = [r for r in (reabertos or []) if not r.get('treinou_depois')]
    # Empate dentro do nível: maior EV perdido primeiro (mesma régua do PIP).
    for r in sorted(pendentes, key=lambda x: -(x.get('ev_loss_bb') or 0)):
        # O CTA leva ao treino DESTA categoria (?foco=leak:<key>), nunca à intro genérica:
        # a intro lidera com a missão ativa, que é ordenada por EV e pode ser OUTRO leak —
        # reportado na tela: a faixa prometia "HJ · 50bb" e o clique entregava "SB · 20bb".
        # Prometer um treino e entregar outro é o jeito mais rápido de o aluno parar de
        # clicar na faixa.
        fila.append(_passo(
            'leak_reaberto', r.get('titulo') or r.get('category_key', ''),
            # O porquê nomeia o FATO, não a bronca: o jogo desmentiu o domínio.
            f"Seus torneios recentes mostraram o erro de volta. O domínio foi zerado; "
            f"vale o que você provar daqui pra frente.",
            4, f"/leak-trainer?foco=leak:{r.get('category_key', '')}" + '&origem={origem}',
            r.get('ev_loss_bb'), r.get('n')))

    # 2 ── Revisão vencida: é o único jeito de o SRS cumprir a promessa do "Volta em 3 dias".
    rev = revisoes or {}
    n_rev = int(rev.get('drills') or 0) + int(rev.get('ranges') or 0)
    if n_rev > 0 and (rev.get('mais_antiga') or '') <= agora:
        alvo = ('/leak-trainer?foco=fund:range_grid&origem={origem}'
                if int(rev.get('ranges') or 0) >= int(rev.get('drills') or 0)
                else '/training?origem={origem}')
        fila.append(_passo(
            'revisao_vencida',
            f"{n_rev} revis{'ões' if n_rev > 1 else 'ão'} te esperando",
            "O reencontro no tempo certo é o que fixa. Adiar é agendar o esquecimento.",
            max(2, min(8, 1 + n_rev // 3)), alvo))

    # 3 ── Missão em curso: o gate já diz o que falta; o passo só aponta para ele.
    if missao:
        ev = missao.get('ev_loss_bb')
        n  = missao.get('hands') or missao.get('n')
        fila.append(_passo(
            'missao', missao.get('titulo') or missao.get('key', ''),
            (f"Você perdeu {ev}bb aqui, em {n} mãos reais." if ev and n
             else "É o leak que mais te custa agora."),
            4, '/leak-trainer?origem={origem}', ev, n))

    # 4 ── Carta nova do alvo; sem ela, o desafio diário. Nunca os dois: um passo por vez.
    if carta_nova:
        de_quem = carta_nova.get('de_quem')
        pos     = carta_nova.get('position', '')
        fila.append(_passo(
            'carta_nova', f"Memorizar a range do {pos}",
            (f"Você perdeu {carta_nova.get('ev_loss_bb')}bb enfrentando aberturas do {pos}."
             if de_quem == 'vilao'
             else f"Você perdeu {carta_nova.get('ev_loss_bb')}bb abrindo do {pos}."),
            3, '/leak-trainer?foco=fund:range_grid&origem={origem}',
            carta_nova.get('ev_loss_bb'), carta_nova.get('hands')))
    elif desafio_pendente:
        fila.append(_passo(
            'desafio_diario', "Desafio do dia",
            "Uma decisão difícil de verdade, contra o solver.",
            2, '/training?origem={origem}'))

    return fila


def _titulo_da_categoria(key: str) -> str:
    """Título legível a partir da chave 'cenario:pos:vs:stack' — fallback para reabertura de
    categoria que saiu do pool de missões (o passo não pode mostrar a chave crua na tela)."""
    try:
        cen, pos, vs, stack = (key.split(':') + ['', '', '', ''])[:4]
        from leaklab.progression import mission_title
        return mission_title({'scenario': cen, 'position': pos, 'vs_position': vs,
                              'stack_bb': float(stack or 0)})
    except Exception:
        return key


def montar_proximo_passo(user_id: int, origem: str = 'api',
                         tz_offset_min: int = 0) -> dict:
    """Carrega os fatos do banco e decide. É o ÚNICO lugar que junta as fontes — endpoint,
    resposta do /analyze e e-mails chamam isto, nunca remontam a precedência.

    `origem` preenche o placeholder do CTA: é o que permite a métrica 1 da spec (% de sessões
    iniciadas por trigger) sem adivinhação.
    """
    from datetime import datetime
    from database.repositories import contar_revisoes_vencidas, get_progression_attempts
    from leaklab.progression import missions_with_state
    from leaklab.leak_trainer import sugerir_memorizacao_de_range

    agora = datetime.utcnow().isoformat()

    # Missões (o estado carrega reabertura e proof — reusa a fonte única do protocolo)
    try:
        ms = missions_with_state(user_id)
    except Exception:
        ms = {'ativa': None, 'items': []}

    # Reaberturas vêm da tabela CRUA, não do proof filtrado de missions_with_state: aquele
    # caminho só enxerga categoria com torneio novo pós-baseline, e a reabertura move o
    # baseline — o leak recém-reaberto ficava invisível até o upload seguinte. Pego forjando
    # o caso num banco descartável (o endpoint devolvia 'missao' com a reabertura na mesa).
    from database.repositories import listar_reaberturas
    por_key = {i.get('key'): i for i in (ms.get('items') or [])}
    reabertos = []
    try:
        cruas = listar_reaberturas(user_id)
    except Exception:
        cruas = []
    for r in cruas:
        key, ra = r['category_key'], r['reopened_at']
        it = por_key.get(key) or {}
        # Missão que o estado já diz dominada de novo não cobra: o gate re-provou depois.
        if it and it.get('estado') and it.get('estado') != 'em_treino':
            continue
        try:
            att = get_progression_attempts(user_id, key, limit=1, since=ra)
        except Exception:
            att = []
        reabertos.append({'category_key': key,
                          'titulo': it.get('titulo') or _titulo_da_categoria(key),
                          'ev_loss_bb': it.get('ev_loss_bb'), 'n': it.get('hands'),
                          'reopened_at': ra, 'treinou_depois': bool(att)})

    try:
        revisoes = contar_revisoes_vencidas(user_id)
    except Exception:
        revisoes = {'drills': 0, 'ranges': 0, 'mais_antiga': None}

    try:
        carta = sugerir_memorizacao_de_range(user_id)
    except Exception:
        carta = None

    desafio_pendente = False
    try:
        from database.repositories import get_challenge_attempt
        hoje = datetime.utcnow().date().isoformat()
        desafio_pendente = get_challenge_attempt(user_id, hoje) is None
    except Exception:
        pass

    fila = decidir_proximo_passo(agora, reabertos=reabertos, revisoes=revisoes,
                                 missao=ms.get('ativa'), carta_nova=carta,
                                 desafio_pendente=desafio_pendente)
    # O placeholder vira a origem REAL aqui, no único ponto de saída.
    for p in fila:
        p['cta_url'] = p['cta_url'].replace('{origem}', origem)

    return {'passo': (fila[0] if fila else None), 'fila': fila[1:3],
            'meta_semanal': meta_semanal_de(user_id, tz_offset_min)}


def meta_semanal_de(user_id: int, tz_offset_min: int = 0) -> dict | None:
    """O compromisso do aluno e o quanto dele já foi cumprido esta semana.

    None quando ele nunca declarou meta — e é esse None que a tela usa para saber que ainda
    precisa perguntar. Um zero aqui diria "meta zero", que é outra coisa.
    """
    from database.repositories import get_meta_semanal, carimbos_de_treino_recentes
    from leaklab.meta_semanal import dias_treinados_na_semana, progresso_semanal
    from datetime import datetime
    try:
        meta = get_meta_semanal(user_id)
        if not meta:
            return None
        dias = dias_treinados_na_semana(carimbos_de_treino_recentes(user_id),
                                        datetime.utcnow().isoformat(), tz_offset_min)
        return progresso_semanal(meta, dias)
    except Exception:
        return None
