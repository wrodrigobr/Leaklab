# -*- coding: utf-8 -*-
"""Bot de boas-vindas dos fundadores no Telegram (21/08).

A conversa inteira é testada sem rede e sem bot de verdade, porque toda a lógica de
sequência vive numa função pura. É onde os erros deste tipo de código moram: perder uma
resposta, pular uma pergunta, tratar o `/start` como se fosse resposta, ou reiniciar a
conversa de quem já terminou.

O webhook também é testado no que importa: **ele é público**, e a única coisa entre ele e
qualquer pessoa da internet é o segredo do header. Um webhook aberto deixaria estranhos
fazendo o bot escrever no grupo dos fundadores.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

try:
    import flask_cors  # noqa: F401
except ImportError:
    import unittest.mock as mock
    sys.modules['flask_cors'] = mock.MagicMock()
    sys.modules['flask_cors'].CORS = lambda app, **kw: None

from leaklab.telegram_bot import (ETAPA_FIM, extrair_evento, proximo_passo,  # noqa: E402
                                  texto_boas_vindas_grupo)


def test_conversa_inteira_grava_as_tres_respostas():
    """O caminho feliz, ponta a ponta. Se alguma resposta se perder no meio, a entrevista
    inteira vira lixo e a pessoa respondeu à toa."""
    etapa, gravado = 0, {}
    # /start: só pergunta, não grava nada.
    p = proximo_passo(etapa, '')
    assert p['gravar'] is None and '1 de 3' in p['responder']
    assert p['nova_etapa'] == 0, 'o /start avançou a etapa e comeu a 1ª pergunta'

    for texto, campo in (('Rodrigo', 'apelido'),
                         ('turbos de 5 a 20 no GG', 'formato'),
                         ('defesa de BB contra open do BTN', 'duvida'),
                         ('eu@exemplo.com', 'email')):
        p = proximo_passo(etapa, texto)
        assert p['gravar'] == {campo: texto}, f'{campo} nao foi gravado: {p["gravar"]}'
        gravado.update(p['gravar'])
        etapa = p['nova_etapa']

    assert etapa == ETAPA_FIM and p['fim'] is True
    assert set(gravado) == {'apelido', 'formato', 'duvida', 'email'}


def test_start_nao_vira_resposta_da_primeira_pergunta():
    """Sem o caso vazio explícito, o `/start` seria gravado como se fosse o apelido da
    pessoa e a pergunta 1 nunca seria feita."""
    p = proximo_passo(0, '')
    assert p['gravar'] is None
    assert p['nova_etapa'] == 0


def test_resposta_vazia_repete_a_pergunta_em_vez_de_avancar():
    """Um toque errado não pode custar a pergunta: sem isso a pessoa avança com campo
    vazio e ninguém percebe."""
    p = proximo_passo(1, '   ')
    assert p['gravar'] is None
    assert p['nova_etapa'] == 1, 'avançou com resposta vazia'
    assert '2 de 3' in p['responder'], 'nao repetiu a pergunta pendente'


def test_fim_entrega_o_convite_do_grupo_no_momento_certo():
    """A pessoa acabou de responder três perguntas e está com o app aberto: é o instante de
    maior disposição que o programa vai ter. Mandar o convite depois, por outro canal, é
    pedir que ela se lembre — e quem chegou pelo link do e-mail pode nem estar no grupo."""
    p = proximo_passo(3, 'eu@t.com', 'https://t.me/+abc123')
    assert p['fim'] is True
    assert 'https://t.me/+abc123' in p['responder'], 'o convite nao foi entregue no fecho'


def test_sem_grupo_configurado_nao_manda_convite_quebrado():
    """Mesmo cuidado da mensagem de boas-vindas: melhor não citar o grupo do que mandar um
    link vazio. O texto degrada, não quebra."""
    p = proximo_passo(3, 'eu@t.com', '')
    assert p['fim'] is True
    assert 'https://t.me/' not in p['responder']
    assert 'me diz no grupo' in p['responder'], 'perdeu o fecho na degradacao'

    p2 = proximo_passo(3, 'eu@t.com', None)
    assert 'https://t.me/' not in p2['responder']


def test_email_pode_ser_pulado_sem_travar():
    """O e-mail é opcional de propósito. Se "pular" travasse a conversa, a pessoa ficaria
    presa na última pergunta depois de ter respondido as três que interessam."""
    p = proximo_passo(3, 'pular')
    assert p['gravar'] is None, 'gravou "pular" como se fosse e-mail'
    assert p['fim'] is True and p['nova_etapa'] == ETAPA_FIM


def test_quem_ja_terminou_nao_reinicia():
    """Mandar mensagem depois de terminar não pode zerar a entrevista e apagar o que a
    pessoa escreveu."""
    p = proximo_passo(ETAPA_FIM, 'oi, tudo bem?')
    assert p['gravar'] is None
    assert p['nova_etapa'] == ETAPA_FIM
    assert p['fim'] is True


def test_bot_nao_se_da_boas_vindas():
    """O próprio bot entrando no grupo dispara `new_chat_members`. Sem o filtro, ele se
    cumprimentaria e o primeiro post do grupo seria constrangedor."""
    so_bot = {'message': {'chat': {'id': -100, 'type': 'supergroup'},
                          'new_chat_members': [{'id': 7, 'is_bot': True,
                                                'first_name': 'GrindLabBot'}]}}
    assert extrair_evento(so_bot) is None

    com_humano = {'message': {'chat': {'id': -100, 'type': 'supergroup'},
                              'new_chat_members': [{'id': 7, 'is_bot': True},
                                                   {'id': 8, 'first_name': 'Ana'}]}}
    ev = extrair_evento(com_humano)
    assert ev['tipo'] == 'entrou_no_grupo' and ev['nome'] == 'Ana'


def test_mensagem_de_outro_bot_e_ignorada():
    upd = {'message': {'chat': {'id': 5, 'type': 'private'},
                       'from': {'id': 9, 'is_bot': True}, 'text': 'spam'}}
    assert extrair_evento(upd) is None


def test_update_sem_texto_nao_quebra():
    """Foto, sticker, entrar em canal, reação: a API manda de tudo. Nada disso pode virar
    exceção num endpoint que o Telegram reenvia quando não recebe 200."""
    for upd in ({}, {'edited_message': {'text': 'oi'}},
                {'message': {'chat': {'id': 1, 'type': 'private'},
                             'from': {'id': 2}, 'photo': [{}]}},
                {'message': {'chat': {}, 'text': 'x'}}):
        assert extrair_evento(upd) is None


def test_boas_vindas_leva_ao_direto():
    t = texto_boas_vindas_grupo('Ana', 'GrindLabFundadoresBot')
    assert 'Ana' in t
    assert 'https://t.me/GrindLabFundadoresBot?start=intro' in t


def test_boas_vindas_sem_username_configurado_nao_gera_link_quebrado():
    """Link "https://t.me/?start=intro" seria pior que nenhum link."""
    t = texto_boas_vindas_grupo('Ana', '')
    assert 'https://t.me/?start' not in t


def _cliente():
    import api.app as A
    A.app.config['TESTING'] = True
    return A, A.app.test_client()


def test_webhook_sem_segredo_configurado_recusa_tudo():
    """Fail-safe: sem o segredo no ambiente a rota não existe. Um webhook aberto deixaria
    qualquer um fazer o bot escrever no grupo dos fundadores."""
    A, cli = _cliente()
    os.environ.pop('TELEGRAM_WEBHOOK_SECRET', None)
    r = cli.post('/telegram/webhook', json={'message': {'chat': {'id': 1}}})
    assert r.status_code == 404, r.status_code


def test_webhook_recusa_segredo_errado_e_aceita_o_certo():
    A, cli = _cliente()
    os.environ['TELEGRAM_WEBHOOK_SECRET'] = 'segredo-de-teste'
    try:
        corpo = {'message': {'chat': {'id': -1, 'type': 'supergroup'},
                             'new_chat_members': [{'id': 3, 'first_name': 'Ana'}]}}
        r = cli.post('/telegram/webhook', json=corpo,
                     headers={'X-Telegram-Bot-Api-Secret-Token': 'errado'})
        assert r.status_code == 403, r.status_code

        r2 = cli.post('/telegram/webhook', json=corpo,
                      headers={'X-Telegram-Bot-Api-Secret-Token': 'segredo-de-teste'})
        assert r2.status_code == 200, r2.status_code
    finally:
        os.environ.pop('TELEGRAM_WEBHOOK_SECRET', None)


def test_webhook_sem_header_nenhum_recusa():
    """Chamada crua, sem header: é o que um varredor de porta faria."""
    A, cli = _cliente()
    os.environ['TELEGRAM_WEBHOOK_SECRET'] = 'segredo-de-teste'
    try:
        r = cli.post('/telegram/webhook', json={'message': {'chat': {'id': 1}}})
        assert r.status_code == 403
    finally:
        os.environ.pop('TELEGRAM_WEBHOOK_SECRET', None)


if __name__ == '__main__':
    falhas = 0
    testes = [v for k, v in sorted(globals().items()) if k.startswith('test_')]
    for t in testes:
        try:
            t()
        except AssertionError as e:
            falhas += 1
            print(f'FALHOU  {t.__name__}: {e}')
        except Exception as e:
            falhas += 1
            print(f'ERRO    {t.__name__}: {type(e).__name__}: {e}')
    print(f'\nTotal: {len(testes)} | Passed: {len(testes) - falhas} | Failed: {falhas}')
    sys.exit(1 if falhas else 0)
