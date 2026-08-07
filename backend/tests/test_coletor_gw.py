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
    return {
        'players_info': [
            {'simple_hand_counters': {m: 1 for m in _MAOS},
             'player': {'is_active': True, 'is_dealer': ator_dealer}},
            {'simple_hand_counters': {m: 1 for m in _MAOS},
             'player': {'is_active': False, 'is_dealer': not ator_dealer}},
        ],
        'action_solutions': sols,
        'game': {'pot': 1.5},
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


def test_token_do_allin_nao_confunde_com_raise_grande():
    """'RAISE 12.500' num spot de 12,625 e all-in ('RAI'); 'RAISE 4.5' e raise normal."""
    assert token_da_acao({'type': 'RAISE', 'betsize': '12.500'}, 12.625) == 'RAI'
    assert token_da_acao({'type': 'RAISE', 'betsize': '4.5'}, 12.625) == 'R4.5'
    assert token_da_acao({'type': 'CALL', 'betsize': '2'}, 12.625) == 'C'
    assert token_da_acao({'type': 'FOLD'}, 12.625) is None
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
