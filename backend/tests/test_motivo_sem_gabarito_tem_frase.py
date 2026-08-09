# -*- coding: utf-8 -*-
"""Todo `coverage_reason` que o motor emite tem frase nos TRES locales.

── Por que este guarda existe ─────────────────────────────────────────────────────────────────

Em 08/08 o card passou a explicar POR QUE nao ha gabarito: `selectWhy` devolve
`card.semGabarito.{motivo}` e a view traduz. Isso amarrou o dialeto interno do motor ao arquivo de
traducao — e amarrou CALADO: motivo novo sem frase nao levanta erro nenhum, o i18n devolve a
propria chave e o jogador le `card.semGabarito.open_jam_uncovered` na tela. E o mesmo defeito do
`hu_rfi` vazando como nome de cenario, com outra roupa.

Em 09/08 nasceram DOIS motivos novos no mesmo dia (`open_jam_uncovered` e
`hand_out_of_node_range`). Sem esta varredura, cada um seria uma chance de vazar.

── Como e medido ──────────────────────────────────────────────────────────────────────────────

Os motivos sao lidos do CODIGO-FONTE do motor, nao de uma lista escrita aqui: lista paralela
envelhece e a divergencia e justamente o que se quer pegar.
"""
import io
import json
import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Fonte unica do "apague os comentarios antes de olhar" — nasceu no guarda de argumentos, quando
# a busca por substring achou os nomes dos argumentos NO COMENTARIO que os explica e passou verde
# com os tres removidos. Copiar a funcao aqui seria a segunda copia da mesma regra.
from test_todo_caminho_mesmos_args import _sem_comentarios  # noqa: E402

_MOTOR = os.path.join(os.path.dirname(__file__), '..', 'leaklab', 'preflop_gto_ranges.py')
_LOCALES = os.path.join(os.path.dirname(__file__), '..', '..', 'frontend', 'src', 'i18n', 'locales')

# `limped_pot` tem tratamento proprio no card (a heuristica assume e a frase vem de `whyLimped`),
# entao ele NAO passa por `semGabarito` — ha teste travando isso em `replayWhy.test.ts`.
_FORA_DO_SEMGABARITO = {'limped_pot'}


def _motivos_do_motor() -> set:
    """Todo literal de motivo que aparece numa atribuicao a `coverage_reason`, em QUALQUER forma.

    A primeira versao casava so `coverage_reason'] = 'literal'`. Em 09/08 a emissao virou um
    condicional (`= ('open_jam_uncovered' if ... else 'open_size_off_tree')`) e a varredura
    devolveu ZERO para os dois motivos — o guarda que existe para impedir chave crua na tela
    deixaria passar duas. Agora le a INSTRUCAO inteira (ate os parenteses fecharem) e recolhe os
    literais dela, o que cobre tambem `setdefault(..., 'x')` e o ternario.
    """
    return _motivos_em(io.open(_MOTOR, encoding='utf-8').read())


def _motivos_em(src: str) -> set:
    src = _sem_comentarios(src)
    achados = set()
    for m in re.finditer(r"coverage_reason'", src):
        # Varre ate o fim da INSTRUCAO: quebra de linha so encerra com os parenteses fechados,
        # senao um condicional de duas linhas perde o literal do `else` — foi o que aconteceu.
        prof, j = 0, m.end()
        while j < len(src):
            c = src[j]
            if c in '([{':
                prof += 1
            elif c in ')]}':
                prof = max(0, prof - 1)   # o `]` de `base['coverage_reason']` fecha o de fora
            elif c == '\n' and prof == 0:
                break
            j += 1
        trecho = src[m.end():j]
        for lit in re.finditer(r"'([a-z][a-z_]{4,})'", trecho):
            # Literal que esta sendo COMPARADO nao e um motivo emitido — a condicao que escolhe
            # entre dois motivos cita `== 'maior'`, e le-lo como motivo faria o guarda exigir uma
            # frase de i18n para uma direcao de tamanho.
            antes = trecho[:lit.start()].rstrip()
            if antes.endswith(('==', '!=', ' in', ' not in')):
                continue
            achados.add(lit.group(1))
    return achados - _FORA_DO_SEMGABARITO


def test_a_varredura_encontra_os_motivos():
    """Controle: se o padrao mudar, o teste abaixo passa por vacuidade."""
    m = _motivos_do_motor()
    assert len(m) >= 5, f'a varredura achou so {sorted(m)} — o padrao de emissao mudou'
    assert 'pairing_uncovered' in m and 'hu_uncovered' in m, sorted(m)
    assert 'open_size_off_tree' in m, (
        'o motivo emitido por condicional de duas linhas sumiu da varredura ' + str(sorted(m)))


def test_a_varredura_le_as_TRES_formas_de_emitir():
    """O guarda so vale se ler a emissao do jeito que ela existe — e ela existe de tres jeitos.
    A versao anterior lia UM (`= 'literal'`) e por isso devolveu zero para os dois motivos que
    nasceram em 09/08. Fonte sintetica de proposito: aqui o gabarito e conhecido."""
    fonte = (
        "base['coverage_reason'] = 'motivo_simples'\n"
        "base.setdefault('coverage_reason', 'motivo_setdefault')\n"
        "base['coverage_reason'] = ('motivo_ternario_a' if x\n"
        "                           else 'motivo_ternario_b')\n"
        "base['coverage_reason'] = ('motivo_comparado_a' if d == 'direcao_qualquer'\n"
        "                           else 'motivo_comparado_b')\n"
        "# base['coverage_reason'] = 'motivo_so_no_comentario'\n"
    )
    achados = _motivos_em(fonte)
    for esperado in ('motivo_simples', 'motivo_setdefault', 'motivo_ternario_a',
                     'motivo_ternario_b', 'motivo_comparado_a', 'motivo_comparado_b'):
        assert esperado in achados, f'{esperado} escapou da varredura: {sorted(achados)}'
    assert 'direcao_qualquer' not in achados, (
        'a varredura leu o lado direito de uma COMPARACAO como motivo — o guarda passaria a '
        'exigir frase de i18n para um valor interno que nunca chega ao card')
    assert 'motivo_so_no_comentario' not in achados, (
        'a varredura leu um comentario como emissao — comentario nao e evidencia, e uma emissao '
        'comentada faria a lista de frases parecer viva')


def test_todo_motivo_tem_frase_nos_tres_locales():
    motivos = _motivos_do_motor()
    faltando = []
    lidos = 0
    for loc in ('pt-BR', 'en', 'es'):
        p = os.path.join(_LOCALES, loc, 'replayer.json')
        if not os.path.exists(p):
            continue                       # backend rodando sem o checkout do front
        lidos += 1
        d = json.load(io.open(p, encoding='utf-8'))
        tem = (d.get('card') or {}).get('semGabarito') or {}
        for m in sorted(motivos - set(tem)):
            faltando.append(f'{loc}: {m}')
    assert not faltando, ('motivo sem frase — o card imprime a chave crua na tela: '
                          + '; '.join(faltando))
    # O `continue` acima existe para o backend rodar sem o checkout do front — e transformava
    # caminho errado em teste VERDE. O QA de aceitacao apontou `_LOCALES` para um diretorio
    # inexistente e este teste passou tendo lido ZERO arquivos: zero tranquilizador dentro do
    # guarda que existe justamente para impedir chave crua na tela.
    # "Verde sem ter verificado nada" e o pior resultado possivel num guarda. Mas o backend
    # PRECISA rodar sem o checkout do front, entao a distincao e entre duas coisas diferentes:
    #   · frontend ausente        -> nao se aplica, e legitimo pular
    #   · frontend presente e os locales nao -> configuracao errada, e o teste TEM que gritar
    _front = os.path.join(os.path.dirname(__file__), '..', '..', 'frontend')
    if os.path.isdir(_front):
        assert lidos == 3, (
            f'o checkout do frontend existe mas so {lidos} de 3 locales foram lidos em '
            f'{_LOCALES!r} — o guarda passaria verde sem verificar nada')
    elif lidos == 0:
        import warnings
        warnings.warn('frontend ausente: este guarda nao verificou nada nesta execucao')


def test_CONTROLE_nenhuma_frase_orfa_de_motivo_que_o_motor_nao_emite_mais():
    """O outro lado: frase que sobrou de um motivo extinto vira documentacao mentirosa do que o
    produto ainda sabe dizer. Nao e erro fatal, mas tem que aparecer."""
    motivos = _motivos_do_motor()
    p = os.path.join(_LOCALES, 'pt-BR', 'replayer.json')
    if not os.path.exists(p):
        return
    tem = set((json.load(io.open(p, encoding='utf-8')).get('card') or {}).get('semGabarito') or {})
    orfas = tem - motivos
    assert not orfas, f'frases de motivos que o motor nao emite mais: {sorted(orfas)}'


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
