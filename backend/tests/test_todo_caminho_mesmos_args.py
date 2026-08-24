# -*- coding: utf-8 -*-
"""Todo caminho que chama a porta unica preflop passa os argumentos que decidem O NO.

── O caso ─────────────────────────────────────────────────────────────────────────────────────

Em 07/08 o `/replay` foi flagrado chamando `analyze_preflop` **sem `facing_to_bb` e sem
`facing_allin`**. Esses dois separam a carta de 3-bet PEQUENO da carta de JAM: sao nos
diferentes. Numa mao heads-up de 15bb efetivos, o jam do vilao era roteado para o no de 3-bet
pequeno — veredito da carta errada, que e exatamente o defeito que o caminho HU existe para matar.

O caminho principal (`/analyze`) ja passava os dois. So o replay ficou para tras, e **nada
acusava**: o teste de paridade que existia comparava `sync x motor` e o replay nao estava na conta.

── Por que a varredura e sobre o CODIGO-FONTE ─────────────────────────────────────────────────

Nao ha como exercitar os tres caminhos num teste de unidade sem montar torneio, banco e request.
O que se pode garantir barato e que **nenhuma chamada esqueca um argumento** — e e disso que o
defeito era feito. Se a assinatura mudar, o teste quebra e alguem le este arquivo.

`n_players` esta na lista pelo mesmo motivo: sem ele, `int(None or 0) == 2` e falso e uma mesa de
DOIS jogadores e gradeada pela carta de mesa cheia.
"""
import io
import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

_BASE = os.path.join(os.path.dirname(__file__), '..')
_APP = os.path.join(_BASE, 'api', 'app.py')

# ── A reincidencia (09/08) ─────────────────────────────────────────────────────────────────────
# A varredura acima cobria SO `api/app.py` e exigia SO dois argumentos — e passava 3/3 enquanto:
#   · o MOTOR (`decision_engine_v11._enrich_preflop_gto`), que e quem GRAVA `gto_label` e
#     `best_action`, nao passava `facing_limp` nem `caller_position`. Sem o primeiro, iso-raise
#     sobre limp era gradeado pela range de DEFESA CONTRA OPEN e saia `gto_critical` com
#     best='fold'; sem o segundo, squeeze virava defesa heads-up (36 de 108 combinacoes amostradas
#     trocam de cenario por causa dele). O card passava os dois: banco e tela discordando sobre a
#     MESMA decisao;
#   · o override de VEREDITO do `/replay` nao passava `facing_to_bb`, `facing_limp` nem
#     `caller_position`, enquanto o bloco de DISPLAY, na MESMA funcao, passava os tres — 30
#     decisoes do acervo com `display=acceptable` ao lado de `veredito=gto_critical`;
#   · o sync nao passava `facing_allin`.
# Guarda que varre um lugar so nao guarda uma regra que vive em quatro.
_ARQUIVOS = (
    os.path.join('api', 'app.py'),
    os.path.join('leaklab', 'decision_engine_v11.py'),
    os.path.join('scripts', 'sync_gto_labels_from_ranges.py'),
)

# Argumentos que mudam QUAL CARTA e consultada. Faltar qualquer um nao devolve "nao sei":
# devolve veredito de outro no.
# `is_pko` entrou em 23/08, depois de uma auditoria achar o estrago: a carta PKO e OUTRA
# carta (K7s de UTG a 71bb: raise 100% na PKO, 30/70 na Classic), e so o MOTOR passava o
# argumento -- justo quem PERSISTE gto_label. Card, matriz e sync liam a Classic, entao o
# jogador via 'Erro, devia dar raise' ao lado de uma matriz dizendo fold 70%. Esta lista
# existe exatamente para essa familia e estava VERDE com o defeito vivo.
_OBRIGATORIOS = ('n_players', 'facing_allin', 'facing_to_bb', 'facing_limp',
                 'caller_position', 'is_pko')

# Isencao NOMEADA, com motivo. Lista de isencao que cresce calada e a proxima versao do bug — so
# entra aqui com uma frase dizendo por que o dado NAO EXISTE naquele caminho.
#
# ── A chave e o CALL SITE, nao o arquivo (bloqueio do QA, 09/08) ──────────────────────────────
# A primeira versao chaveava por `('api/app.py', 'caller_position')`, e `api/app.py` tem QUATRO
# chamadas da porta unica. O QA removeu `caller_position` das TRES que o tinham e a varredura
# ficou verde: a isencao de uma chamada cobria as outras tres. Guarda com isencao larga demais e
# guarda desligado — a mesma familia do proprio defeito que este arquivo persegue.
#
# A chave e o nome QUALIFICADO da funcao que faz a chamada (`_build_replay_data._norm`), e nao o
# numero da linha: linha muda a cada edicao acima dela e uma isencao que sai do lugar volta a
# calar a chamada errada.
_ISENTOS = {
    # O override preflop do enriquecimento de no GTO le a linha de `decisions`, e nao ha coluna
    # `caller_position` no schema (conferido em 09/08: as colunas de contexto sao facing_bet,
    # vs_position, facing_to_call_bb, effective_stack_bb, facing_limp). O sync so tem o dado
    # porque o re-deriva do texto cru da mao. Quando a coluna existir, tire daqui.
    ('api/app.py', 'get_decision_gto', 'caller_position'):
        'nao ha coluna caller_position em decisions',
}


def _sem_comentarios(src: str) -> str:
    """Apaga os comentarios PRESERVANDO offsets (troca por espaco), para o numero de linha do
    achado continuar valendo.

    Nao e detalhe: a primeira versao desta varredura procurava o nome do argumento como substring
    do corpo da chamada, e o comentario que eu mesmo escrevi acima dos argumentos CITA os tres
    nomes. Removi os tres argumentos de proposito e o teste passou — comentario nao e evidencia,
    nem quando o leitor e um teste.
    """
    import io as _io
    import tokenize
    fora = list(src)
    linhas = src.splitlines(keepends=True)
    inicio = [0]
    for l in linhas:
        inicio.append(inicio[-1] + len(l))
    try:
        toks = list(tokenize.generate_tokens(_io.StringIO(src).readline))
    except (tokenize.TokenError, IndentationError, SyntaxError):
        return src                                  # arquivo nao tokenizavel: melhor cru que nada
    for tok in toks:
        if tok.type != tokenize.COMMENT:
            continue
        a = inicio[tok.start[0] - 1] + tok.start[1]
        b = inicio[tok.end[0] - 1] + tok.end[1]
        for k in range(a, b):
            if fora[k] != '\n':
                fora[k] = ' '
    return ''.join(fora)


def _funcao_qualificada(src: str, linha: int) -> str:
    """Nome qualificado da funcao que contem a linha (`_build_replay_data._norm`).

    Sobe pelo arquivo aceitando so linhas MENOS indentadas que o bloco corrente — sem isso um
    `def` irmao, declarado acima e no mesmo nivel, seria confundido com o dono da chamada.
    """
    linhas = src.splitlines()
    if not 1 <= linha <= len(linhas):
        return ''
    atual = linhas[linha - 1]
    nivel = len(atual) - len(atual.lstrip())
    cadeia = []
    for k in range(linha - 2, -1, -1):
        l = linhas[k]
        if not l.strip():
            continue
        ind = len(l) - len(l.lstrip())
        if ind >= nivel:
            continue
        m = re.match(r'\s*(?:async\s+)?def\s+(\w+)', l)
        if m:
            cadeia.append(m.group(1))
        nivel = ind
        if nivel == 0 and m:
            break
    return '.'.join(reversed(cadeia))


def _chamadas_da_porta_unica(arquivos=_ARQUIVOS):
    """Cada chamada de analise nos N arquivos: (arquivo, linha, funcao qualificada, corpo).

    `funcao` e o que a lista de isencao usa como chave — ver `_ISENTOS`.
    """
    achadas = []
    for rel in arquivos:
        src = _sem_comentarios(io.open(os.path.join(_BASE, rel), encoding='utf-8').read())
        nome = rel.replace(os.sep, '/')
        for m in re.finditer(
                r'\b(?:_analyze_preflop|analyze_preflop|_pfs\w*|preflop_strategy)\s*\(', src):
            i = m.end() - 1
            prof, j = 0, i
            while j < len(src):
                if src[j] == '(':
                    prof += 1
                elif src[j] == ')':
                    prof -= 1
                    if prof == 0:
                        break
                j += 1
            corpo = src[i:j]
            if 'hero_hand_type' not in corpo:
                continue                   # import, alias ou outra funcao de nome parecido
            linha = src[:m.start()].count('\n') + 1
            achadas.append((nome, linha, _funcao_qualificada(src, linha), corpo))
    return achadas


def test_a_varredura_encontra_os_caminhos():
    """Controle: se a busca parar de achar chamadas, o teste abaixo passa por vacuidade."""
    achadas = _chamadas_da_porta_unica()
    assert len(achadas) >= 6, f'a varredura achou so {len(achadas)} chamadas — o padrao mudou'
    arquivos = {a for a, _l, _f, _c in achadas}
    for esperado in ('api/app.py', 'leaklab/decision_engine_v11.py',
                     'scripts/sync_gto_labels_from_ranges.py'):
        assert esperado in arquivos, f'a varredura perdeu {esperado}'
    # A chave da isencao so vale se a varredura souber DE QUEM e cada chamada.
    anonimas = [f'{a}:{l}' for a, l, f, _c in achadas if not f]
    assert not anonimas, f'chamadas sem funcao identificada (a isencao viraria global): {anonimas}'
    assert len({(a, f) for a, _l, f, _c in achadas}) >= 5, (
        'as chamadas colapsaram em poucas funcoes — a chave por call site perdeu resolucao')


def test_nenhuma_chamada_esquece_o_que_decide_o_no():
    faltando = []
    for arq, linha, fn, corpo in _chamadas_da_porta_unica():
        sem = [a for a in _OBRIGATORIOS if a not in corpo and (arq, fn, a) not in _ISENTOS]
        if sem:
            faltando.append(f'{arq}:{linha} ({fn}) sem {sem}')
    assert not faltando, 'chamadas da porta unica incompletas: ' + '; '.join(faltando)


def test_a_isencao_nao_cobre_chamada_nenhuma_alem_da_sua():
    """O bloqueio, virado guarda. Cada entrada de `_ISENTOS` tem que casar com UMA chamada que
    realmente nao passa o argumento; isencao que sobra e isencao que vai cobrir a chamada errada
    no dia em que alguem quebrar outra coisa. Guarda de isencao ausente foi o que deixou o QA
    remover `caller_position` de tres chamadas sem que nada acusasse."""
    achadas = _chamadas_da_porta_unica()
    for (arq, fn, arg), motivo in _ISENTOS.items():
        assert motivo.strip(), f'isencao sem motivo: {(arq, fn, arg)}'
        alvos = [c for a, _l, f, c in achadas if a == arq and f == fn]
        assert alvos, f'isencao {(arq, fn, arg)} nao casa com chamada nenhuma — esta obsoleta'
        assert len(alvos) == 1, (
            f'isencao {(arq, fn, arg)} cobre {len(alvos)} chamadas da mesma funcao; separe-as')
        assert arg not in alvos[0], (
            f'isencao {(arq, fn, arg)} nao e mais necessaria — a chamada ja passa o argumento')


def test_o_motor_passa_os_dois_que_escolhem_a_ARVORE():
    """Redundante de proposito com o teste acima, e mais legivel no dia em que quebrar. O motor e
    o unico caminho cujo resultado e PERSISTIDO — divergencia aqui vira dado errado no banco, nao
    so pixel errado na tela."""
    src = _sem_comentarios(
        io.open(os.path.join(_BASE, 'leaklab', 'decision_engine_v11.py'), encoding='utf-8').read())
    corpo = src[src.index('def _enrich_preflop_gto'):]
    corpo = corpo[:corpo.index('\n_LABEL_SEV')]
    for arg in ('facing_limp', 'caller_position'):
        assert re.search(rf'\b{arg}\s*=', corpo), (
            f'_enrich_preflop_gto parou de passar {arg} — o motor volta a gradear pote limpado '
            f'pela carta de RFI e squeeze pela carta de defesa vs open')


def test_as_DUAS_chamadas_do_replay_tem_a_mesma_superficie():
    """`_build_replay_data` chama a porta duas vezes (display e veredito) e as duas descrevem a
    MESMA decisao. Divergir ali e o card se contradizendo sozinho."""
    src = _sem_comentarios(io.open(_APP, encoding='utf-8').read())
    ini = src.index('def _build_replay_data')
    # Fim da funcao = proximo `def`/decorador em coluna 0. Sem delimitar, `src[ini:]` engole o
    # resto do arquivo e a comparacao pega chamadas de outras funcoes — o teste acusaria
    # divergencia entre coisas que nao precisam concordar.
    fim = re.search(r'^(?:@|def |class )', src[ini + 10:], re.M)
    corpo_fn = src[ini:ini + 10 + (fim.start() if fim else len(src))]
    l0 = src[:ini].count('\n') + 1
    l1 = l0 + corpo_fn.count('\n')
    chamadas = [c for a, l, _f, c in _chamadas_da_porta_unica((os.path.join('api', 'app.py'),))
                if a == 'api/app.py' and l0 <= l <= l1]
    assert len(chamadas) >= 2, f'o /replay deixou de ter as duas chamadas ({len(chamadas)})'
    args = [{a for a in _OBRIGATORIOS if a in c} for c in chamadas]
    assert all(s == args[0] for s in args), (
        'as duas chamadas do /replay divergem na superficie de argumentos: '
        + str([sorted(s) for s in args]))


def test_o_replay_passa_o_tamanho_em_BB_e_nao_em_FICHAS():
    """`facingSize` vem em FICHAS (212.780 na mao que expos isto) e `facingToBb` em bb. Passar o
    primeiro como tamanho e a unidade errada — o bug mais recorrente deste projeto.

    (Honestidade: no provider atual `facing_size` so e usado como `> 0`, entao a troca nao muda
    veredito hoje. O teste existe para que continue certo quando alguem passar a usar o valor.)
    """
    for arq, linha, _fn, corpo in _chamadas_da_porta_unica():
        if 'facing_size' not in corpo:
            continue
        m = re.search(r'facing_size\s*=\s*([^,\n]+)', corpo)
        assert m, (arq, linha, corpo[:120])
        expr = m.group(1)
        assert 'facingSize' not in expr, (
            f"{arq}:{linha} passa `facingSize` (fichas) como facing_size; use `facingToBb`")


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
