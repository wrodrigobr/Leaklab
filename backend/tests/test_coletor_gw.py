# -*- coding: utf-8 -*-
"""O coletor do GW: descoberta de sizing, parada no limite e gravacao incremental.

── Por que este arquivo existe ────────────────────────────────────────────────────────────────

O coletor gasta um recurso ESCASSO E ALHEIO: a cota diaria da conta do usuario no GTO Wizard.
Testar "rodando pra ver" custa a propria cota que o script existe para economizar — e um bug de
loop custaria a conta. Entao tudo aqui roda contra um `buscar` falso que devolve payloads da
FORMA REAL (a mesma que o HAR trouxe: `players_info[*].simple_hand_counters` + `action_solutions`).

Cada guarda e verificado nos DOIS sentidos: com o defeito presente ele acusa, e com o defeito
ausente ele fica quieto. Guarda que so foi visto acusando nao prova que discrimina.
"""
import io
import json
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts'))

from coletor_gw import LimiteAtingido, caminha, escolhe_acao, gravador, token_da_acao  # noqa: E402
from importar_har_hu import extrai_nos, no_de_resposta                                 # noqa: E402

# ── as 169 na ordem que o GW usa ('22', '32o', '32s', '33', ...) ───────────────────────────────
_R = '23456789TJQKA'
_MAOS = sorted(
    [r + r for r in _R]
    + [_R[j] + _R[i] + s for j in range(13) for i in range(j) for s in ('o', 's')]
)
assert len(_MAOS) == 169


def _payload(acoes, ator_dealer=True, folds_puros=()):
    """Resposta `spot-solution` sintetica com a forma real.

    `acoes`: [(tipo, betsize), ...]. `folds_puros`: maos com fold 100% (para forjar corrupcao).
    """
    idx = {m: i for i, m in enumerate(_MAOS)}
    sols = []
    for tipo, bs in acoes:
        estrategia = [0.0] * 169
        for m in _MAOS:
            if tipo == 'FOLD':
                estrategia[idx[m]] = 1.0 if m in folds_puros else 0.2
            else:
                estrategia[idx[m]] = 0.0 if m in folds_puros else 0.4
        acao = {'type': tipo}
        if bs is not None:
            acao['betsize'] = bs
        sols.append({'action': acao, 'strategy': estrategia, 'evs': [1.5] * 169})
    # `position` e `seat` NAO sao enfeite: o payload real do GW os traz, e a fixture sem eles
    # escondeu o bug de `mesa` — em HU o BB e o ultimo assento (1), entao a mesa e 2.
    return {
        'players_info': [
            {'simple_hand_counters': {m: 1 for m in _MAOS},
             'player': {'is_active': ator_dealer, 'is_dealer': True,
                        'position': 'SB', 'seat': 0}},
            {'simple_hand_counters': {m: 1 for m in _MAOS},
             'player': {'is_active': not ator_dealer, 'is_dealer': False,
                        'position': 'BB', 'seat': 1}},
        ],
        'action_solutions': sols,
        'game': {'pot': 1.5, 'active_position': 'SB' if ator_dealer else 'BB'},
    }


def _arvore(stack, size_3bet):
    """Arvore HU minima de uma profundidade, com o sizing do 3-bet PARAMETRIZADO."""
    allin = f'{stack:.3f}'
    return {
        '': _payload([('FOLD', None), ('CALL', '1.000'), ('RAISE', '2'), ('RAISE', allin)]),
        'C': _payload([('CHECK', None), ('RAISE', '3'), ('RAISE', allin)], ator_dealer=False),
        'R2': _payload([('FOLD', None), ('CALL', '2'), ('RAISE', size_3bet), ('RAISE', allin)],
                       ator_dealer=False),
        'R2-RAI': _payload([('FOLD', None), ('CALL', allin)]),
        f'R2-R{size_3bet}': _payload([('FOLD', None), ('CALL', size_3bet), ('RAISE', allin)]),
        f'R2-R{size_3bet}-RAI': _payload([('FOLD', None), ('CALL', allin)], ator_dealer=False),
    }


def _buscar_de(arvores, erro_em=None, status_erro=429, log=None):
    """`buscar` falso. `erro_em`: indice da requisicao a partir do qual devolve erro."""
    estado = {'n': 0}

    def buscar(params):
        estado['n'] += 1
        if log is not None:
            log.append((params['depth'], params['preflop_actions']))
        if erro_em is not None and estado['n'] >= erro_em:
            return status_erro, {'detail': 'quota exceeded'}
        arvore = arvores[params['depth']]
        no = params['preflop_actions']
        if no not in arvore:
            return 404, None
        return 200, arvore[no]
    return buscar


_LINHAS = [[], ['raise_min'], ['raise_min', 'allin'], ['raise_min', 'raise_min'],
           ['raise_min', 'raise_min', 'allin'], ['call']]


# ── 1. porta unica de decodificacao ───────────────────────────────────────────────────────────

def test_har_e_coletor_decodificam_igual():
    """A regra que vive em N lugares e UMA funcao — e o teste varre os N caminhos.

    A ordem das 169 ja nos custou uma leitura errada (JJ lido como 'call 90,5%'). Se o coletor
    tivesse a propria copia da decodificacao, o erro poderia renascer so num dos caminhos.
    """
    corpo = _payload([('FOLD', None), ('CALL', '2'), ('RAISE', '4.5')], ator_dealer=False)
    q = {'gametype': 'MTTHUGeneralSimpleAI', 'depth': '14.125', 'preflop_actions': 'R2'}

    # caminho do coletor
    pelo_coletor = no_de_resposta(corpo, q)

    # caminho do HAR: mesmo payload embrulhado num .har de verdade
    har = {'log': {'entries': [{
        'request': {'url': 'https://api.gtowizard.com/v4/solutions/spot-solution/?x=1',
                    'queryString': [{'name': k, 'value': v} for k, v in q.items()]},
        'response': {'content': {'text': json.dumps(corpo)}},
    }]}}
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / 'x.har'
        p.write_text(json.dumps(har), encoding='utf-8')
        pelo_har = extrai_nos(p)

    assert len(pelo_har) == 1
    assert pelo_har[0] == pelo_coletor, 'os dois caminhos divergiram na decodificacao'
    assert pelo_coletor['ator'] == 'BB' and pelo_coletor['acoes'] == ['FOLD', 'CALL 2', 'RAISE 4.5']


# ── 2. o sizing vem da resposta, nao do palpite ───────────────────────────────────────────────

def test_descobre_o_sizing_do_proprio_no():
    """O GW muda o 3-bet por profundidade (R4.5 a 14bb, R5.5 a 30bb). Um plano com sizing
    escrito na mao geraria requisicao invalida — e requisicao invalida gasta cota igual."""
    arvores = {'14.125': _arvore(14.125, '4.5'), '30.125': _arvore(30.125, '5.5')}
    log = []
    buscar = _buscar_de(arvores, log=log)
    for depth in ('14.125', '30.125'):
        caminha(buscar, 'MTTHUGeneralSimpleAI', depth, _LINHAS)
    pedidos = {(d, n) for d, n in log}
    assert ('14.125', 'R2-R4.5') in pedidos, 'nao descobriu o 3-bet de 4.5 a 14bb'
    assert ('30.125', 'R2-R5.5') in pedidos, 'nao descobriu o 3-bet de 5.5 a 30bb'
    assert ('14.125', 'R2-R4.5-RAI') in pedidos
    # e o alvo desta rodada, o SB vs 3-bet JAM, foi pedido nas duas
    assert ('14.125', 'R2-RAI') in pedidos and ('30.125', 'R2-RAI') in pedidos


def test_o_code_do_payload_manda_no_token():
    """O GW declara o token em `action.code`. Derivar por tamanho era heuristica onde havia dado
    — a mesma familia do `history_spot` adivinhado. O `code` vence sempre."""
    assert token_da_acao({'type': 'RAISE', 'betsize': '4.5', 'code': 'R4.5'}, 16.125) == 'R4.5'
    assert token_da_acao({'type': 'RAISE', 'betsize': '16.000', 'code': 'RAI',
                          'allin': True}, 16.125) == 'RAI'
    assert token_da_acao({'type': 'FOLD', 'betsize': '0', 'code': 'F'}, 16.125) == 'F'
    # o `code` manda mesmo quando a heuristica discordaria (raise gigante que NAO e all-in)
    assert token_da_acao({'type': 'RAISE', 'betsize': '15.900', 'code': 'R15.9',
                          'allin': False}, 16.125) == 'R15.9'


def test_token_derivado_sobrevive_para_no_antigo():
    """Fallback para no gravado antes de guardarmos `code`. FOLD agora e 'F', nao None: em mesa
    cheia foldar PASSA A VEZ, e o token precisa entrar na linha (`F-F-F-F-R2`)."""
    assert token_da_acao({'type': 'RAISE', 'betsize': '12.500'}, 12.625) == 'RAI'
    assert token_da_acao({'type': 'RAISE', 'betsize': '4.5'}, 12.625) == 'R4.5'
    assert token_da_acao({'type': 'CALL', 'betsize': '2'}, 12.625) == 'C'
    assert token_da_acao({'type': 'FOLD'}, 12.625) == 'F'
    # CONTROLE: o mesmo 12.5 num spot FUNDO nao e all-in
    assert token_da_acao({'type': 'RAISE', 'betsize': '12.500'}, 60.125) == 'R12.5'


def test_escolhe_acao_nao_inventa_o_que_o_no_nao_oferece():
    """No sem raise normal (so fold/call/allin) nao vira requisicao chutada."""
    acoes = [{'type': 'FOLD'}, {'type': 'CALL', 'betsize': '2'}, {'type': 'RAISE', 'betsize': '20.000'}]
    assert escolhe_acao('raise_min', acoes, 20.125) is None
    assert escolhe_acao('allin', acoes, 20.125)['betsize'] == '20.000'


# ── 3. parada no limite (o guarda que protege a conta) ────────────────────────────────────────

def test_para_no_primeiro_sinal_de_limite():
    """429 na 3a requisicao: para na hora. E o CONTROLE — sem erro nenhum, NAO para."""
    arvores = {'14.125': _arvore(14.125, '4.5')}
    log = []
    try:
        caminha(_buscar_de(arvores, erro_em=3, log=log), 'g', '14.125', _LINHAS)
        assert False, 'devia ter levantado LimiteAtingido'
    except LimiteAtingido as e:
        assert '429' in str(e), e
    assert len(log) == 3, f'insistiu depois do limite: {len(log)} requisicoes'

    log_ok = []
    caminha(_buscar_de(arvores, log=log_ok), 'g', '14.125', _LINHAS)
    assert len(log_ok) > 3, 'o controle parou sem motivo — o guarda nao discrimina'


def test_no_coletado_vira_conhecido_na_mesma_execucao():
    """Blocos diferentes do plano compartilham prefixos (F-F-R2 serve a 3 pares). O `ja` so
    era lido do disco no inicio: o mesmo no foi buscado 3x na MESMA execucao (15/08, ~6
    requisicoes de cota desperdicadas). O contrato: no coletado entra no indice NA HORA, e o
    bloco seguinte o pula sem requisicao."""
    arvores = {'14.125': _arvore(14.125, '4.5')}
    ja: dict = {}

    def ao_coletar(gt, chave, no):
        ja.setdefault(gt, {})[chave] = no          # a mesma fiacao do main()

    log1: list = []
    caminha(_buscar_de(arvores, log=log1), 'g', '14.125', [[], ['raise_min']],
            ao_coletar=ao_coletar)
    assert log1, 'bloco 1 devia ter buscado'
    log2: list = []
    caminha(_buscar_de(arvores, log=log2), 'g', '14.125', [[], ['raise_min']],
            ao_coletar=ao_coletar, conhecidos=ja.get('g', {}))
    assert log2 == [], f'bloco 2 rebuscou no ja coletado nesta execucao: {log2}'


def test_403_na_primeira_requisicao_e_depth_indisponivel():
    """O caso 28.125 (15/08): 403 no ROOT abortava o plano inteiro — duas execucoes perdidas.
    O 403 e PAYWALL de tier (o app mostra "Upgrade... Premium Tournament users"), nao cota:
    403 ANTES de qualquer resposta da depth e DepthIndisponivel (quem chama pula a depth);
    403 no MEIO da caminhada continua LimiteAtingido — servidor que muda de ideia no meio e
    bloqueio de sessao, nao paywall."""
    from coletor_gw import DepthIndisponivel
    arvores = {'14.125': _arvore(14.125, '4.5')}
    # 403 logo na 1a requisicao -> DepthIndisponivel
    try:
        caminha(_buscar_de(arvores, erro_em=1, status_erro=403), 'g', '14.125', _LINHAS)
        assert False, 'devia ter levantado DepthIndisponivel'
    except DepthIndisponivel as e:
        assert '403' in str(e), e
    # 403 na 3a (ja houve resposta valida) -> LimiteAtingido, como sempre
    try:
        caminha(_buscar_de(arvores, erro_em=3, status_erro=403), 'g', '14.125', _LINHAS)
        assert False, 'devia ter levantado LimiteAtingido'
    except LimiteAtingido as e:
        assert '403' in str(e), e
    # CONTROLE: 429 na 1a NAO vira pulo de depth — so 403 fala de grade
    try:
        caminha(_buscar_de(arvores, erro_em=1, status_erro=429), 'g', '14.125', _LINHAS)
        assert False, 'devia ter levantado LimiteAtingido'
    except LimiteAtingido as e:
        assert '429' in str(e), e


def test_corpo_sem_solucao_tambem_e_limite():
    """200 com corpo vazio e o disfarce mais comum de cota estourada: seguir so gastaria mais."""
    class _Vazio(dict):
        pass
    arvores = {'14.125': {'': _Vazio()}}
    try:
        caminha(_buscar_de(arvores), 'g', '14.125', [[]])
        assert False, 'aceitou corpo sem action_solutions'
    except LimiteAtingido as e:
        assert 'sem solucao' in str(e)


# ── 4. no corrompido nao entra no acervo ──────────────────────────────────────────────────────

def test_no_com_ordem_corrompida_e_rejeitado():
    """Mesma validacao do importador: AA com fold 100% denuncia ordem trocada.
    Carta errada e pior que carta nenhuma — foi exatamente o que a carta ring provou."""
    bom = _payload([('FOLD', None), ('CALL', '2')], ator_dealer=False, folds_puros={'32o', '42o'})
    ruim = _payload([('FOLD', None), ('CALL', '2')], ator_dealer=False, folds_puros={'AA', '32o'})
    for corpo, esperado in ((bom, 1), (ruim, 0)):
        coletados = caminha(_buscar_de({'14.125': {'': corpo}}), 'g', '14.125', [[]])
        assert len(coletados) == esperado, (esperado, coletados.keys())


def test_hu_raso_aceita_fold_largo_mas_nao_par_nem_ax():
    """Rodada 4 (15/08): a 3-7bb o proprio GW folda 72s/82s/83s no ROOT (regime push/fold) —
    a lista de lixo do HU profundo rejeitou 5 nos LEGITIMOS. No raso valem so as proibicoes
    universais: par e Ax nunca sao fold puro, e as ancoras AA/KK seguem ativas. No fundo
    (>7,5bb) a regra continua a de sempre."""
    from importar_har_hu import valida_no as _valida
    lixo_raso = {'72s', '82s', '83s', '32o', '72o'}

    def _no(depth, folds):
        return no_de_resposta(_payload([('FOLD', None), ('RAISE', '5.000')],
                                       folds_puros=folds),
                              {'gametype': 'MTTHUGeneralSimpleAI', 'depth': depth,
                               'preflop_actions': ''})

    assert _valida(_no('5.125', lixo_raso)) is None, _valida(_no('5.125', lixo_raso))
    # proibicoes universais continuam valendo no raso
    assert '22' in (_valida(_no('5.125', lixo_raso | {'22'})) or '')
    assert 'A2o' in (_valida(_no('5.125', lixo_raso | {'A2o'})) or '')
    assert 'AA' in (_valida(_no('5.125', lixo_raso | {'AA'})) or '')   # ancora, camada anterior
    # CONTROLE: no fundo a mesma mao ainda denuncia — a regra rasa nao vazou para cima
    assert '72s' in (_valida(_no('14.125', {'72s', '32o'})) or '')


# ── 5. o que ja veio fica gravado ─────────────────────────────────────────────────────────────

def test_grava_a_cada_no_e_sobrevive_a_parada():
    """A licao do HAR perdido: o coletado so existe depois de escrito em disco."""
    arvores = {'14.125': _arvore(14.125, '4.5')}
    with tempfile.TemporaryDirectory() as d:
        out = Path(d) / 'acervo.json'
        grava = gravador(out)
        try:
            caminha(_buscar_de(arvores, erro_em=3), 'g', '14.125', _LINHAS,
                    ao_coletar=lambda gt, k, n: grava(gt, k, n))
        except LimiteAtingido:
            pass
        assert out.exists(), 'parou e nao gravou nada'
        salvo = json.loads(out.read_text(encoding='utf-8'))
        assert sum(len(v) for v in salvo.values()) == 2, salvo


def test_merge_preserva_o_acervo_anterior():
    """Gravar no novo nao pode apagar sessao anterior (o acumulador e a unica copia)."""
    with tempfile.TemporaryDirectory() as d:
        out = Path(d) / 'acervo.json'
        out.write_text(json.dumps({'g': {'99.125|ROOT': {'antigo': True}}}), encoding='utf-8')
        gravador(out)('g', '14.125|ROOT', {'novo': True})
        salvo = json.loads(out.read_text(encoding='utf-8'))
        assert '99.125|ROOT' in salvo['g'] and '14.125|ROOT' in salvo['g']


# ── 6. economia de cota ───────────────────────────────────────────────────────────────────────

def test_prefixo_compartilhado_gasta_uma_requisicao_so():
    """As 6 linhas do plano compartilham ROOT e R2. Sem memoizacao seriam 14 requisicoes;
    com, sao 6 nos distintos. Cada repetida seria cota queimada em dado que ja temos."""
    arvores = {'14.125': _arvore(14.125, '4.5')}
    log = []
    caminha(_buscar_de(arvores, log=log), 'g', '14.125', _LINHAS)
    assert len(log) == len(set(log)), f'pediu no repetido: {log}'
    assert len(log) == 6, f'esperava 6 nos distintos, foram {len(log)}: {log}'


# ── 7. o transporte: navegar e ESCUTAR ────────────────────────────────────────────────────────

class _RespostaFalsa:
    def __init__(self, url, corpo, status=200):
        self.url, self._corpo, self.status = url, corpo, status

    def json(self):
        return self._corpo


class _PaginaFalsa:
    """Playwright de mentira: `goto` dispara as respostas que o app 'faria' para aquela URL."""

    def __init__(self, respostas_por_no):
        self.respostas = respostas_por_no          # {preflop_actions: [(no_da_resposta, corpo)]}
        self.ouvintes = []
        self.visitadas = []

    def on(self, _evento, fn):
        self.ouvintes.append(fn)

    def remove_listener(self, _evento, fn):
        self.ouvintes.remove(fn)

    def goto(self, url, **_):
        from urllib.parse import parse_qs, urlparse
        q = parse_qs(urlparse(url).query)
        self.visitadas.append((q.get('depth', [''])[0], q.get('preflop_actions', [''])[0]))
        pedido = q.get('preflop_actions', [''])[0]
        for no_resp, corpo in self.respostas.get(pedido, []):
            u = (f"https://api.gtowizard.com/v4/solutions/spot-solution/?gametype=g"
                 f"&depth={q['depth'][0]}&preflop_actions={no_resp}")
            for fn in list(self.ouvintes):
                fn(_RespostaFalsa(u, corpo))

    def wait_for_timeout(self, _ms):
        pass

    def evaluate(self, _expr):
        return getattr(self, 'texto', '')


def test_navegando_casa_a_resposta_com_o_no_pedido():
    """A pagina emite varias respostas; so a do no PEDIDO pode ser aceita."""
    from coletor_gw import buscador_navegando
    alvo = _payload([('FOLD', None), ('CALL', '2'), ('RAISE', '4.5')], ator_dealer=False)
    outro = _payload([('FOLD', None), ('CALL', '1.000')])
    page = _PaginaFalsa({'R2': [('', outro), ('R2', alvo), ('C', outro)]})
    status, corpo = buscador_navegando(page, espera_ms=1000)(
        {'gametype': 'g', 'depth': '14.125', 'preflop_actions': 'R2'})
    assert status == 200
    assert [a['action']['type'] for a in corpo['action_solutions']] == ['FOLD', 'CALL', 'RAISE']
    assert page.visitadas == [('14.125', 'R2')]


def test_navegando_acusa_se_o_app_entregar_outro_no():
    """O pior desfecho possivel seria gravar o ROOT sob a chave de R2: carta errada nao se
    denuncia depois. Se a rota da SPA mudar, isto PARA em vez de gravar."""
    from coletor_gw import LimiteAtingido as _L, buscador_navegando
    root = _payload([('FOLD', None), ('CALL', '1.000')])
    page = _PaginaFalsa({'R2': [('', root)]})          # pedi R2, o app so entregou ROOT
    try:
        buscador_navegando(page, espera_ms=300, passo_ms=100)(
            {'gametype': 'g', 'depth': '14.125', 'preflop_actions': 'R2'})
        assert False, 'aceitou resposta de outro no'
    except _L as e:
        assert 'nao entregou' in str(e), e
    # CONTROLE: com a resposta certa, o mesmo caminho NAO acusa
    page2 = _PaginaFalsa({'R2': [('R2', root)]})
    assert buscador_navegando(page2, espera_ms=300, passo_ms=100)(
        {'gametype': 'g', 'depth': '14.125', 'preflop_actions': 'R2'})[0] == 200


def test_le_o_aviso_de_limite_da_propria_pagina():
    """Em 07/08 o coletor rodou com a cota estourada e ficou 30s no escuro por no. A pagina
    dizia, o tempo todo: "You have reached your free daily solution browsing limit." Perguntar
    a ela e mais barato que esperar o timeout e mais honesto que adivinhar a causa."""
    from coletor_gw import LimiteAtingido as _L, buscador_navegando
    page = _PaginaFalsa({'': []})                      # nenhuma resposta chega
    page.texto = '\n'.join([
        'Mtt 16bb Heads-up',
        'You have reached your free daily solution browsing limit.',
        'View Plans',
    ])
    try:
        buscador_navegando(page, espera_ms=5000, passo_ms=100)(
            {'gametype': 'g', 'depth': '16.125', 'preflop_actions': ''})
        assert False, 'nao acusou o limite'
    except _L as e:
        assert 'daily solution browsing limit' in str(e), e

    # CONTROLE: sem o aviso, a MESMA ausencia de resposta da o erro generico, nao "limite"
    page2 = _PaginaFalsa({'': []})
    page2.texto = 'Mtt 16bb Heads-up'
    try:
        buscador_navegando(page2, espera_ms=300, passo_ms=100)(
            {'gametype': 'g', 'depth': '16.125', 'preflop_actions': ''})
        assert False
    except _L as e:
        assert 'nao entregou' in str(e), f'confundiu ausencia de resposta com cota: {e}'


def test_url_do_spot_carrega_o_no():
    from coletor_gw import url_do_spot
    u = url_do_spot({'gametype': 'MTTHUGeneralSimpleAI', 'depth': '16.125',
                     'preflop_actions': 'R2-RAI'})
    assert 'preflop_actions=R2-RAI' in u and 'depth=16.125' in u
    assert u.startswith('https://app.gtowizard.com/solutions?')


def test_history_spot_acompanha_a_linha():
    """`history_spot=0` fixo fazia o app exibir a RAIZ e ignorar o `preflop_actions` — o coletor
    esperou 30s por um `R2` que nunca vinha. A URL que o GW montou ao clicar mostrou a regra:
    e o numero de acoes ja jogadas na linha."""
    from coletor_gw import url_do_spot
    casos = {'': '0', 'R2': '1', 'R2-RAI': '2', 'R2-R4.5-RAI': '3'}
    for acoes, esperado in casos.items():
        u = url_do_spot({'gametype': 'g', 'depth': '16.125', 'preflop_actions': acoes})
        assert f'history_spot={esperado}' in u, (acoes, u)


# ── 8. cota: no que ja esta no disco nao se pede de novo ──────────────────────────────────────

def test_rotulo_gravado_volta_a_acao():
    """Round-trip: a acao crua vira rotulo ao gravar e precisa voltar identica ao ser lida,
    senao o reaproveitamento escolheria o filho errado."""
    from coletor_gw import acoes_cruas_de_rotulos
    cruas = [{'type': 'FOLD'}, {'type': 'CALL', 'betsize': '2'},
             {'type': 'RAISE', 'betsize': '4.5'}, {'type': 'RAISE', 'betsize': '16.000'}]
    rotulos = ['FOLD', 'CALL 2', 'RAISE 4.5', 'RAISE 16.000']
    assert acoes_cruas_de_rotulos(rotulos) == cruas
    for original, voltou in zip(cruas, acoes_cruas_de_rotulos(rotulos)):
        assert token_da_acao(original, 16.125) == token_da_acao(voltou, 16.125)


def test_no_ja_no_acervo_nao_gasta_requisicao():
    """A cota diaria e o recurso mais escasso da operacao. Entre execucoes, ROOT e R2 ja estao
    no disco: rebusca-los seria pagar de novo por dado que ja temos — e foi o que aconteceu na
    rodada de 07/08, que gastou ROOT@16.125 duas vezes."""
    arvore = _arvore(16.125, '4.5')
    conhecidos = {}
    for no_str in ('', 'R2'):
        conhecidos[f"16.125|{no_str or 'ROOT'}"] = no_de_resposta(
            arvore[no_str], {'gametype': 'g', 'depth': '16.125', 'preflop_actions': no_str})
    log = []
    caminha(_buscar_de({'16.125': arvore}, log=log), 'g', '16.125', _LINHAS,
            conhecidos=conhecidos)
    pedidos = {n for _d, n in log}
    assert '' not in pedidos and 'R2' not in pedidos, f'refez no conhecido: {pedidos}'
    assert 'R2-RAI' in pedidos, 'nao chegou ao no inedito usando as acoes gravadas'

    # CONTROLE: sem `conhecidos`, os mesmos nos SAO pedidos (o teste nao passa por vacuidade)
    log2 = []
    caminha(_buscar_de({'16.125': arvore}, log=log2), 'g', '16.125', _LINHAS)
    assert '' in {n for _d, n in log2} and 'R2' in {n for _d, n in log2}


# ── 9. mesa cheia ─────────────────────────────────────────────────────────────────────────────

_ORDEM_8M = ['UTG', 'UTG+1', 'LJ', 'HJ', 'CO', 'BTN', 'SB', 'BB']


def _payload_ring(pos_ator, acoes, folds_puros=(), n=8):
    """Resposta de mesa cheia na forma REAL, lida de um HAR de 11/05 (`MTTGeneral_8m`):
    `player.position`, `game.active_position` e `action.code` existem e sao autoritativos."""
    base = _payload(acoes, folds_puros=folds_puros)
    base['players_info'] = [
        {'simple_hand_counters': {m: 1 for m in _MAOS},
         'player': {'position': p, 'name': p, 'seat': i, 'is_active': p == pos_ator,
                    'is_dealer': p == 'BTN', 'is_hero': p == pos_ator, 'is_folded': False}}
        for i, p in enumerate(_ORDEM_8M[:n])
    ]
    base['game'] = {'pot': '2.5', 'active_position': pos_ator, 'board': ''}
    for s, (tipo, bs) in zip(base['action_solutions'], acoes):
        s['action']['position'] = pos_ator
        s['action']['allin'] = False
        s['action']['code'] = {'FOLD': 'F', 'CALL': 'C', 'CHECK': 'X'}.get(tipo, f'R{bs}')
    return base


def test_ring_le_a_posicao_do_payload_e_nao_do_is_dealer():
    """Em HU dava para deduzir 'SB' de `is_dealer`. Em mesa cheia sao 8 posicoes e um dealer so —
    a heuristica nao teria como funcionar. O GW declara `position` e `active_position`."""
    # CO de proposito: a heuristica de `is_dealer` devolveria 'BB' para QUALQUER nao-dealer, entao
    # um teste com ator no BB passaria mesmo com a heuristica velha — foi o que a mutacao pegou.
    corpo = _payload_ring('CO', [('FOLD', None), ('CALL', '6.5'), ('RAISE', '20.000')],
                          folds_puros={'32o', '72o'})
    q = {'gametype': 'MTTGeneral_8m', 'depth': '20.125', 'preflop_actions': 'F-F-F-R2'}
    no = no_de_resposta(corpo, q)
    assert no['ator'] == 'CO', no['ator']
    assert no['mesa'] == 8
    assert no['codigos'] == ['F', 'C', 'R20.000']
    # CONTROLE: em HU o mesmo caminho continua dando SB/BB
    hu = no_de_resposta(_payload([('FOLD', None), ('CALL', '2')], ator_dealer=True),
                        {'gametype': 'MTTHUGeneralSimpleAI', 'depth': '16.125',
                         'preflop_actions': ''})
    assert hu['ator'] == 'SB' and hu['mesa'] == 2


def test_mesa_nao_e_len_players_info():
    """O defeito que eu enviei em 07/08 e so descobri ao varrer os HAR antigos.

    `players_info` traz **so quem ja agiu**: num no raiz vem UM jogador. Ler isso como "mesa de 1"
    fez o cruzamento contra 1.948 nos em disco devolver ZERO pares aproveitaveis — um zero
    tranquilizador que era artefato do meu proprio campo, nao ausencia de dado. O tamanho sai de
    duas fontes que precisam concordar: os digitos do gametype e o assento de uma posicao TARDIA
    (o BB e sempre o ultimo assento).
    """
    from importar_har_hu import mesa_do_no
    parcial = [{'player': {'position': 'UTG', 'seat': 0}},
               {'player': {'position': 'BB', 'seat': 7}}]
    assert mesa_do_no('MTTGeneral_8m', parcial) == 8
    assert mesa_do_no('MTTGeneralV2', parcial) == 8, 'sem digitos no gametype, o assento resolve'
    # so o ator, e cedo na mesa: nao da para derivar do assento — vale o gametype
    assert mesa_do_no('MTTGeneral_8m', [{'player': {'position': 'UTG', 'seat': 0}}]) == 8
    assert mesa_do_no('MTTGeneralV2', [{'player': {'position': 'UTG', 'seat': 0}}]) is None
    # 9-max: o BB e o assento 8
    assert mesa_do_no('MTTGeneralV2', [{'player': {'position': 'BB', 'seat': 8}}]) == 9
    # DISCORDANCIA entre as fontes -> None, nunca um palpite
    assert mesa_do_no('MTTGeneral_8m', [{'player': {'position': 'BB', 'seat': 8}}]) is None


def test_payload_PARCIAL_ainda_da_a_mesa_certa():
    """O cenario REAL, pelo caminho de verdade.

    Num no de mesa cheia so aparecem em `players_info` os jogadores que ja agiram: `F-F-F-R2` tras
    quatro, nao oito. As fixtures anteriores listavam a mesa inteira, entao `len(players_info)`
    acertava por acidente e a verificacao por mutacao passava cega — o defeito so apareceu contra
    os HAR de verdade, onde o campo virou "mesa de 1".
    """
    corpo = _payload_ring('CO', [('FOLD', None), ('RAISE', '2')], folds_puros={'32o', '72o'})
    # ate o ATOR: os quatro que ja agiram mais o CO, que esta decidindo. O payload real sempre
    # inclui quem age — cortar antes dele produziria uma resposta que o GW nunca manda.
    corpo['players_info'] = corpo['players_info'][:5]
    corpo['game']['active_position'] = 'CO'
    no = no_de_resposta(corpo, {'gametype': 'MTTGeneralV2', 'depth': '20.125',
                                'preflop_actions': 'F-F-F-R2'})
    assert no['mesa'] == 8, (
        'mesa saiu %r com 4 jogadores listados — voltou a contar `players_info`' % no['mesa'])
    assert no['ator'] == 'CO'


def test_ring_nao_e_validado_com_a_lista_de_lixo_de_hu():
    """A lista de lixo aceitavel e de HU, onde as ranges sao larguissimas. Um UTG de 8-max folda
    Q9o, J9o, T8s — com a regra de HU o no bom seria REJEITADO. Em mesa cheia vale a ancora do
    outro extremo: num RFI, 32o e 72o SAO fold puro."""
    from importar_har_hu import valida_no as _valida
    lixo_de_ring = {'32o', '72o', 'Q9o', 'J9o', 'T8s', 'K5o', '94o'}
    bom = no_de_resposta(_payload_ring('UTG', [('FOLD', None), ('RAISE', '2')],
                                       folds_puros=lixo_de_ring),
                         {'gametype': 'MTTGeneral_8m', 'depth': '20.125', 'preflop_actions': ''})
    assert _valida(bom) is None, _valida(bom)

    # ordem corrompida das duas maneiras que o validador tem que pegar
    com_aa = no_de_resposta(_payload_ring('UTG', [('FOLD', None), ('RAISE', '2')],
                                          folds_puros=lixo_de_ring | {'AA'}),
                            {'gametype': 'MTTGeneral_8m', 'depth': '20.125',
                             'preflop_actions': ''})
    assert 'AA' in (_valida(com_aa) or ''), _valida(com_aa)

    sem_lixo = no_de_resposta(_payload_ring('UTG', [('FOLD', None), ('RAISE', '2')],
                                            folds_puros={'Q9o', 'J9o'}),
                              {'gametype': 'MTTGeneral_8m', 'depth': '20.125',
                               'preflop_actions': ''})
    assert '32o' in (_valida(sem_lixo) or ''), _valida(sem_lixo)


def test_no_postflop_e_recusado_pelas_DUAS_pontas():
    """Achado no HAR real de 11/05: o unico no de mesa cheia que sobrou era POSTFLOP, e ali o
    `strategy` vem por COMBO (1326), nao por mao (169). Sem guarda a decodificacao estourava com
    IndexError — e um payload com 1000 valores teria "funcionado" para as 169 primeiras chaves,
    mentindo em silencio. Duas recusas independentes: o board na query e o tamanho do array."""
    corpo = _payload_ring('BB', [('FOLD', None), ('CALL', '6.5')])
    q = {'gametype': 'MTTGeneral_8m', 'depth': '20.125', 'preflop_actions': 'R2-F-C'}

    assert no_de_resposta(corpo, dict(q, board='Ad6h5d')) is None, 'aceitou no com board'

    por_combo = json.loads(json.dumps(corpo))
    for s in por_combo['action_solutions']:
        s['strategy'] = s['strategy'] + [0.1] * 1157        # 1326 combos
    assert no_de_resposta(por_combo, q) is None, 'aceitou strategy fora de 169'

    # CONTROLE: o mesmo no, preflop e com 169, entra normalmente
    assert no_de_resposta(corpo, q) is not None


def test_ring_caminha_pelos_folds_ate_o_heroi():
    """A linha de mesa cheia atravessa os folds dos outros: `F-F-F-F-R2-F-R6.5` e o BB decidindo
    contra squeeze do SB depois do open do CO. Sem a intencao `fold`, esse no e inalcancavel."""
    arvore = {
        '': _payload_ring('UTG', [('FOLD', None), ('RAISE', '2')], folds_puros={'32o', '72o'}),
        'F': _payload_ring('UTG+1', [('FOLD', None), ('RAISE', '2')], folds_puros={'32o', '72o'}),
        'F-F': _payload_ring('LJ', [('FOLD', None), ('RAISE', '2')], folds_puros={'32o', '72o'}),
        'F-F-F': _payload_ring('HJ', [('FOLD', None), ('RAISE', '2')], folds_puros={'32o', '72o'}),
        'F-F-F-F': _payload_ring('CO', [('FOLD', None), ('RAISE', '2')],
                                 folds_puros={'32o', '72o'}),
        'F-F-F-F-R2': _payload_ring('BTN', [('FOLD', None), ('CALL', '2'), ('RAISE', '6.5')]),
        'F-F-F-F-R2-F': _payload_ring('SB', [('FOLD', None), ('CALL', '2'), ('RAISE', '6.5')]),
        'F-F-F-F-R2-F-R6.5': _payload_ring('BB', [('FOLD', None), ('CALL', '6.5'),
                                                  ('RAISE', '20.000')]),
    }
    log = []
    linha = [['fold', 'fold', 'fold', 'fold', 'raise_min', 'fold', 'raise_min']]
    coletados = caminha(_buscar_de({'20.125': arvore}, log=log), 'MTTGeneral_8m', '20.125', linha)
    assert '20.125|F-F-F-F-R2-F-R6.5' in coletados, sorted(coletados)
    assert coletados['20.125|F-F-F-F-R2-F-R6.5']['ator'] == 'BB'
    assert len(log) == 8, f'gastou {len(log)} requisicoes para 8 nos: {log}'


if __name__ == '__main__':
    falhas = 0
    testes = [v for k, v in sorted(globals().items()) if k.startswith('test_')]
    for t in testes:
        buf, real = io.StringIO(), sys.stdout
        sys.stdout = buf
        try:
            t()
        except AssertionError as e:
            sys.stdout = real; falhas += 1
            print(f'FALHOU  {t.__name__}: {e}')
        except Exception as e:
            sys.stdout = real; falhas += 1
            print(f'ERRO    {t.__name__}: {type(e).__name__}: {e}')
        finally:
            sys.stdout = real
    print(f'\nTotal: {len(testes)} | Passed: {len(testes) - falhas} | Failed: {falhas}')
    sys.exit(1 if falhas else 0)
