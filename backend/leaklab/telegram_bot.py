# -*- coding: utf-8 -*-
"""Bot de boas-vindas dos Parceiros Fundadores no Telegram.

O que ele faz, e só isso: recebe quem entra no grupo, convida a responder três perguntas
por mensagem direta, e guarda as respostas ligadas à conta do GrindLab.

**Por que a conversa acontece na DM e não no grupo.** Três perguntas respondidas por vinte
pessoas no mesmo grupo viram uma pilha ilegível, e quem chega depois não sabe mais o que
está sendo perguntado. Na DM cada um responde no seu ritmo, e o grupo fica livre para o que
ele existe: conversa entre os fundadores.

**Por que a máquina de estado é uma função pura.** Toda a lógica de "em que pergunta essa
pessoa está e o que respondo agora" vive em `proximo_passo`, sem tocar em rede nem em banco.
É o que permite testar a conversa inteira sem um bot de verdade, e é onde os erros de
sequência apareceriam.

O token do bot NUNCA aparece aqui: vem de `TELEGRAM_BOT_TOKEN` no ambiente.
"""
from __future__ import annotations

# ── As perguntas ─────────────────────────────────────────────────────────────
#
# Três, e na ordem em que ficam mais fáceis de responder. A última é a que mais interessa
# (é dela que sai o que construir), e por isso vem depois de duas fáceis, quando a pessoa
# já está conversando.
PERGUNTAS = [
    {
        'campo': 'apelido',
        'texto': ('Boas-vindas aos Parceiros Fundadores.\n\n'
                  'São três perguntas rápidas, e a última é a que mais me interessa.\n\n'
                  '1 de 3 — Como te chamam?'),
    },
    {
        'campo': 'formato',
        'texto': ('2 de 3 — Que formato de MTT você mais joga?\n\n'
                  'Pode ser solto: "turbos de 5 a 20 reais no GG", "PKO à noite", '
                  '"freezeout de domingo". Quanto mais específico, melhor.'),
    },
    {
        'campo': 'duvida',
        'texto': ('3 de 3 — Qual decisão do seu jogo ainda te incomoda?\n\n'
                  'Aquela situação que você joga e fica na cabeça depois. É dela que sai '
                  'o que eu vou construir primeiro.'),
    },
    {
        'campo': 'email',
        'texto': ('Por último, e é opcional: qual o e-mail da sua conta no GrindLab?\n\n'
                  'É só para ligar suas respostas ao seu acesso. Se preferir não dizer, '
                  'responde "pular".'),
    },
]

ETAPA_FIM = len(PERGUNTAS)

FIM_TEXTO = ('Pronto, é isso. Obrigado.\n\n'
             'Seu Pro já está ativo. O melhor primeiro passo é subir o hand history de um '
             'torneio recente e ver o que aparece.\n\n'
             'Quando algo travar ou parecer errado, me diz no grupo. Crítica direta vale '
             'mais que elogio.')

JA_RESPONDEU = ('Você já respondeu as três. Se quiser mudar alguma coisa, é só falar no '
                'grupo que eu ajusto.')

BOAS_VINDAS_GRUPO = ('Chegou mais um fundador: {nome}.\n\n'
                     'Me chama no direto para as três perguntas de entrada, leva um minuto: '
                     '{link}')


def _pular(texto: str) -> bool:
    return (texto or '').strip().lower() in ('pular', 'skip', 'nao', 'não', '-')


def proximo_passo(etapa: int, texto: str) -> dict:
    """Dado em que etapa a pessoa está e o que ela acabou de escrever, diz o que gravar e
    o que responder.

    Função PURA: nada de rede, nada de banco. Devolve
    `{'gravar': {campo: valor} | None, 'responder': str, 'nova_etapa': int, 'fim': bool}`.

    `etapa` é o índice da pergunta que está PENDENTE. Etapa 0 significa que nada foi
    perguntado ainda, então a primeira chamada só faz a pergunta 1 sem gravar nada — é o
    que impede o `/start` de virar resposta da pergunta que ainda não foi feita.
    """
    if etapa >= ETAPA_FIM:
        return {'gravar': None, 'responder': JA_RESPONDEU, 'nova_etapa': etapa, 'fim': True}

    pergunta = PERGUNTAS[etapa]
    valor = (texto or '').strip()

    # Texto vazio nunca avança, e isso cobre DOIS casos com a mesma regra: o `/start`, que
    # chega sem resposta nenhuma e portanto só faz a pergunta 1; e o toque errado no meio da
    # conversa, que repetiria a pergunta pendente em vez de gravar campo vazio.
    # (Havia aqui um `if etapa == 0 and not texto` separado. A mutação de teste mostrou que
    # ele era código morto: nenhum teste mudava de resultado com ele removido, porque este
    # guarda já fazia o trabalho inteiro.)
    if not valor:
        return {'gravar': None, 'responder': pergunta['texto'], 'nova_etapa': etapa,
                'fim': False}

    gravar = None
    if pergunta['campo'] == 'email' and _pular(valor):
        gravar = None                      # pular é uma resposta válida, não um erro
    else:
        gravar = {pergunta['campo']: valor[:500]}

    nova = etapa + 1
    if nova >= ETAPA_FIM:
        return {'gravar': gravar, 'responder': FIM_TEXTO, 'nova_etapa': nova, 'fim': True}
    return {'gravar': gravar, 'responder': PERGUNTAS[nova]['texto'], 'nova_etapa': nova,
            'fim': False}


def primeira_pergunta() -> str:
    """O texto que abre a conversa (resposta ao /start)."""
    return PERGUNTAS[0]['texto']


def texto_boas_vindas_grupo(nome: str, usuario_bot: str) -> str:
    """Mensagem postada no grupo quando alguém entra. Leva ao direto, onde a conversa cabe."""
    link = f'https://t.me/{usuario_bot}?start=intro' if usuario_bot else 'no meu direto'
    return BOAS_VINDAS_GRUPO.format(nome=nome or 'um novo fundador', link=link)


def extrair_evento(update: dict) -> dict | None:
    """Traduz o update cru do Telegram para o que nos interessa, ou None se for coisa que
    não tratamos (edição, canal, reação e o resto do zoológico da API).

    Devolve `{'tipo': 'entrou_no_grupo'|'mensagem', 'chat_id', 'chat_tipo', 'user_id',
    'nome', 'texto'}`.
    """
    msg = (update or {}).get('message') or {}
    chat = msg.get('chat') or {}
    if not chat.get('id'):
        return None

    novos = msg.get('new_chat_members') or []
    if novos:
        # Ignora o próprio bot entrando no grupo — senão ele se daria boas-vindas.
        humanos = [m for m in novos if not m.get('is_bot')]
        if not humanos:
            return None
        m = humanos[0]
        return {'tipo': 'entrou_no_grupo', 'chat_id': chat['id'],
                'chat_tipo': chat.get('type'), 'user_id': m.get('id'),
                'nome': m.get('first_name') or m.get('username') or '', 'texto': ''}

    de = msg.get('from') or {}
    if de.get('is_bot'):
        return None
    texto = msg.get('text')
    if texto is None:
        return None
    return {'tipo': 'mensagem', 'chat_id': chat['id'], 'chat_tipo': chat.get('type'),
            'user_id': de.get('id'),
            'nome': de.get('first_name') or de.get('username') or '',
            'texto': texto}
