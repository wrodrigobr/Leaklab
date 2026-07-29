# -*- coding: utf-8 -*-
"""E-mail de cobrança por EVENTO (spec cobranca-proximo-passo.md §5).

Fase 2. A Fase 1 pôs a prescrição em toda superfície que o aluno VÊ; esta alcança o aluno que
não voltou — que é justamente quem o sistema precisa acordar.

── A régua, e por que ela é dura ─────────────────────────────────────────────────────────────

Cobrança por CALENDÁRIO treina o jogador a ignorar cobrança. É a mesma lição que o relatório de
evolução já pagou: quem joga pouco recebe "sem amostra" em tudo e para de abrir. Aqui vale
igual — e pior, porque e-mail sem fato novo custa a caixa de entrada, não só a atenção.

Então: só dispara com EVENTO, teto de 1 por semana, o de maior força vence, e opt-out sempre.

`decidir_email_cobranca` é PURA: recebe os eventos já apurados, o último envio e o relógio.
É ela que decide mandar e-mail para uma pessoa real, e essa decisão tem que ser testável sem
banco, sem SMTP e sem esperar uma semana passar.

── O interruptor ─────────────────────────────────────────────────────────────────────────────

`ENGAGEMENT_EMAIL_ENABLED` nasce DESLIGADO, no mesmo padrão do `ADMIN_EMAIL_ENABLED`. Um deploy
não pode disparar e-mail para a base inteira como efeito colateral: subir código é reversível,
e-mail enviado não é.
"""
from __future__ import annotations

import os

# Força de cada gatilho: o maior vence quando mais de um acontece na mesma varredura. A ordem
# espelha a precedência do próximo passo (spec §2.2) de propósito — o e-mail e a tela têm que
# concordar sobre o que é urgente, senão o aluno recebe uma cobrança e encontra outra coisa.
FORCA = {
    'leak_reaberto':    4,   # o jogo real desmentiu o treino
    'relatorio_gerado': 3,   # existe notícia nova, e ela é boa ou má mas é FATO
    'revisao_vencida':  2,   # a promessa do "volta em 3 dias" venceu
    'inatividade':      1,   # o mais fraco: não houve evento, houve ausência
}

# Teto: uma cobrança por semana, sempre. Vence inclusive o gatilho mais forte — quem joga muito
# mudaria de estado toda semana e o e-mail viraria ruído com cara de urgência.
TETO_DIAS = 7

# A revisão só cobra depois de 48h vencida: revisão que venceu hoje de manhã não é abandono, e
# o aluno que entra à noite resolve sozinho. Cobrar antes disso é cobrar quem ia pagar.
REVISAO_HORAS_MIN = 48

# Inatividade: 7 dias sem NENHUMA tentativa, com missão aberta. Menos que isso confunde férias
# com desistência.
INATIVIDADE_DIAS = 7


def emails_habilitados() -> bool:
    """Interruptor de produção. OFF por padrão: um deploy nunca dispara e-mail sozinho."""
    return (os.environ.get('ENGAGEMENT_EMAIL_ENABLED', '').strip().lower()
            in ('1', 'true', 'yes', 'on'))


def _dias_entre(depois: str, antes: str) -> float:
    """Diferença em dias entre dois ISO. Devolve infinito quando não há 'antes' (nunca enviado),
    que é o que faz o primeiro e-mail passar pelo teto sem caso especial."""
    if not antes:
        return float('inf')
    from datetime import datetime
    try:
        a = datetime.fromisoformat(str(antes)[:26])
        d = datetime.fromisoformat(str(depois)[:26])
    except ValueError:
        return float('inf')
    return (d - a).total_seconds() / 86400.0


def decidir_email_cobranca(agora: str, eventos: list | None,
                           ultimo_envio: str | None) -> dict | None:
    """Qual e-mail mandar agora, ou None.

    `eventos`: [{'tipo': str, 'dados': dict}] — já apurados pelo chamador.
    `ultimo_envio`: ISO do último e-mail DE COBRANÇA enviado a este aluno (qualquer tipo).

    Pura: sem banco, sem SMTP, sem relógio próprio.
    """
    if not eventos:
        return None
    # Teto primeiro: ele vence tudo, inclusive o gatilho mais forte. Checar antes de escolher
    # deixa isso explícito no código, e não uma consequência de ordem de ifs.
    if _dias_entre(agora, ultimo_envio) < TETO_DIAS:
        return None
    validos = [e for e in eventos if e.get('tipo') in FORCA]
    if not validos:
        return None
    return max(validos, key=lambda e: FORCA[e['tipo']])


def coletar_eventos(user_id: int, agora: str) -> list:
    """Apura os eventos de cobrança deste aluno. Faz I/O; a DECISÃO é da função pura acima.

    Cada gatilho corresponde a um fato verificável no banco — nenhum deles é "faz tempo que
    ele não vem" sozinho, exceto a inatividade, que é o mais fraco e exige missão aberta.
    """
    from datetime import datetime, timedelta
    from database.repositories import (contar_revisoes_vencidas, listar_reaberturas,
                                       ultimo_relatorio_de_evolucao, ultima_tentativa_de_treino,
                                       get_progression_attempts)
    eventos = []

    # 1 ── Leak reaberto sem treino depois. Mesmo corte da Fase 1: quem já voltou não é acordado.
    try:
        for r in listar_reaberturas(user_id):
            try:
                att = get_progression_attempts(user_id, r['category_key'], limit=1,
                                               since=r['reopened_at'])
            except Exception:
                att = []
            if not att:
                # O título vem resolvido AQUI, pela mesma função da Fase 1: `listar_reaberturas`
                # devolve `category_key`, e o e-mail que chegou na caixa do usuário dizia
                # "um leak que você já tinha dominado" em vez de nomear o leak. Cobrança que
                # não diz O QUE cobrar é pior que nenhuma.
                from leaklab.proximo_passo import _titulo_da_categoria
                eventos.append({'tipo': 'leak_reaberto',
                                'dados': {**r, 'titulo': _titulo_da_categoria(r['category_key'])}})
                break        # um por varredura: o e-mail cobra UMA coisa
    except Exception:
        pass

    # 2 ── Relatório de evolução novo desde o último e-mail. O worker já o gera; até a Fase 1 ele
    #      só virava sino, e quem não abre o app nunca soube que existia.
    try:
        rel = ultimo_relatorio_de_evolucao(user_id)
        if rel and _dias_entre(agora, rel.get('created_at')) <= TETO_DIAS:
            eventos.append({'tipo': 'relatorio_gerado', 'dados': rel})
    except Exception:
        pass

    # 3 ── Revisão vencida há 48h+.
    try:
        rev = contar_revisoes_vencidas(user_id)
        n = int(rev.get('drills') or 0) + int(rev.get('ranges') or 0)
        antiga = rev.get('mais_antiga')
        if n > 0 and antiga and _dias_entre(agora, antiga) >= (REVISAO_HORAS_MIN / 24.0):
            eventos.append({'tipo': 'revisao_vencida', 'dados': {**rev, 'total': n}})
    except Exception:
        pass

    # 4 ── Inatividade COM missão aberta. Sem missão aberta não há o que cobrar: o aluno em dia
    #      que parou de jogar não deve receber e-mail lembrando que parou.
    try:
        ultima = ultima_tentativa_de_treino(user_id)
        if _dias_entre(agora, ultima) >= INATIVIDADE_DIAS:
            from leaklab.progression import missions_with_state
            ativa = (missions_with_state(user_id) or {}).get('ativa')
            if ativa:
                eventos.append({'tipo': 'inatividade',
                                'dados': {'missao': ativa,
                                          'dias': int(_dias_entre(agora, ultima))
                                          if ultima else INATIVIDADE_DIAS}})
    except Exception:
        pass

    return eventos


# ── Corpo dos e-mails (só PT, regra do projeto) ───────────────────────────────────────────────
#
# A primeira linha carrega o FATO, em bb quando houver. "Você tem treinos pendentes" é ruído;
# "Você perdeu 14,4bb enfrentando aberturas do LJ" é motivo para abrir o app.

def montar_email(tipo: str, dados: dict, username: str, base_url: str,
                 unsub_url: str) -> tuple[str, str] | None:
    """(assunto, html) do e-mail, ou None se o tipo não tem corpo."""
    from leaklab.email_digest import _email_document, _eyebrow, _h1, _greeting, _cta_button

    if tipo == 'leak_reaberto':
        # Fallback CURTO de propósito. O anterior era "um leak que você já tinha dominado", que
        # encaixado na frase abaixo produzia "Você já tinha dominado um leak que você já tinha
        # dominado no treino" — reportado pelo usuário na caixa dele. Texto de reserva tem que
        # caber na frase que o hospeda, não ser uma frase inteira.
        titulo = dados.get('titulo') or 'este leak'
        assunto = 'Um leak que você dominava voltou'
        inner = (
            _eyebrow('Leak reaberto')
            + _h1('O erro voltou nos seus torneios')
            + _greeting(username)
            + _p(f'Você já tinha dominado <strong>{_esc(titulo)}</strong> no treino. Nos seus '
                 f'torneios recentes ele voltou a aparecer, então o domínio foi zerado.')
            + _p('Isso não apaga o que você aprendeu. Significa que a correção ainda não '
                 'sobreviveu à mesa, e é isso que o treino existe para provar.')
            + _cta_button('Corrigir agora', f'{base_url}/leak-trainer?origem=email')
        )
    elif tipo == 'relatorio_gerado':
        assunto = 'Seu relatório de evolução está pronto'
        inner = (
            _eyebrow('Relatório de evolução')
            + _h1('Tem número novo sobre o seu jogo')
            + _greeting(username)
            + _p('Seu volume recente já dá para comparar com o período anterior. O relatório diz '
                 'onde você melhorou, onde piorou e, quando a amostra ainda é pequena, diz isso '
                 'também em vez de fingir precisão.')
            + _cta_button('Ver o relatório', f'{base_url}/evolucao?origem=email')
        )
    elif tipo == 'revisao_vencida':
        n = int(dados.get('total') or 0)
        # O coletor só cria o evento com n > 0, então isto é estado impossível por construção.
        # Uma linha para que nunca saia "0 revisões te esperando" se alguém montar o e-mail por
        # outro caminho: e-mail absurdo custa mais caro que e-mail não enviado.
        if n <= 0:
            return None
        assunto = f'{n} revisão te esperando' if n == 1 else f'{n} revisões te esperando'
        inner = (
            _eyebrow('Revisão vencida')
            + _h1('Chegou a hora de reencontrar o que você estudou')
            + _greeting(username)
            + _p(f'Você tem <strong>{n}</strong> {"revisão" if n == 1 else "revisões"} no ponto. '
                 f'O que fixa o aprendizado é o reencontro no tempo certo, não a repetição '
                 f'seguida, e é por isso que elas voltam espaçadas.')
            + _p('São poucos minutos.')
            + _cta_button('Revisar', f'{base_url}/leak-trainer?origem=email')
        )
    elif tipo == 'inatividade':
        # Mesma família do bug do leak reaberto: o texto de reserva tem que caber na frase que o
        # hospeda. Aqui ele aparecia em DUAS posições diferentes (meio e começo), e no começo
        # saía em minúscula — "seu leak principal segue como o leak que mais te custa", que
        # ainda por cima repetia "leak" duas vezes. Duas reservas, uma para cada posição.
        missao = dados.get('missao') or {}
        ev = missao.get('ev_loss_bb')
        maos = missao.get('hands')
        titulo = missao.get('titulo')
        assunto = 'Seu leak continua custando'
        if ev and maos:
            onde = f'<strong>{_esc(titulo)}</strong>' if titulo else 'no seu leak principal'
            emest = f' em {onde}' if titulo else f' {onde}'
            custo = (f'Você perdeu <strong>{ev}bb</strong>{emest}, em {maos} mãos reais.')
        elif titulo:
            custo = f'<strong>{_esc(titulo)}</strong> segue sendo o que mais te custa.'
        else:
            custo = 'Seu leak principal segue aberto, e continua custando nas suas mãos.'
        inner = (
            _eyebrow('Sua missão continua aberta')
            + _h1('O leak não some sozinho')
            + _greeting(username)
            + _p(custo)
            + _p('A sessão que ataca exatamente isso leva uns 4 minutos e continua te esperando.')
            + _cta_button('Treinar', f'{base_url}/leak-trainer?origem=email')
        )
    else:
        return None

    html = _email_document(
        title=assunto, inner_html=inner, base_url=base_url,
        footer_note='Você recebe este email porque tem treinos em aberto na GrindLab. '
                    'No máximo um por semana.',
        unsub_link=unsub_url, preheader=assunto)
    return assunto, html


def _esc(s) -> str:
    return (str(s or '').replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;'))


def _p(html: str) -> str:
    return (f'<p style="margin:0 0 16px 0;font-size:15px;line-height:1.7;color:#B4C0CC;">'
            f'{html}</p>')
