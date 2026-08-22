# -*- coding: utf-8 -*-
"""Copy do frontend que precisa passar pelo i18n.

── O caso que originou (21/08) ────────────────────────────────────────────────────────────

Varrendo travessão na copy achei `planBuilder.ts` e `ranges.ts` com texto em português
**cravado no código**: os títulos das semanas do plano de estudo e as descrições das ranges
apareciam em português mesmo com a interface em inglês ou espanhol.

Os dois arquivos acabaram em lugares diferentes, e a diferença é o ponto:

- **`planBuilder.ts` era copy VIVA** e foi para o i18n, nos três locales.
- **`ranges.ts` era copy MORTA.** O campo `RangeSet.description` era escrito em 43 lugares e
  lido em **nenhum**: o commit `7a5db722` (25/05) o tirou da tela e deixou o campo para trás.
  Provei com o compilador — renomear o campo na interface produziu 43 erros, todos do tipo
  "propriedade desconhecida em literal", ou seja **todos escritores, zero leitores**. Traduzir
  teria sido trabalho que ninguém veria; o certo era remover.

── Os dois guardas ────────────────────────────────────────────────────────────────────────

1. **Chave sem tradução** é o defeito que chega ao jogador: o i18next mostra a chave crua
   ("planBuilder.dia.drill") na tela. Vale para os três locales, e é o mais barato de checar.
2. **Português cravado** nos arquivos já limpos, para que não volte.

O segundo é deliberadamente uma LISTA, não uma varredura do frontend inteiro: dezenas de
componentes ainda têm copy em português no código, e um teste que nasce vermelho é um teste
que alguém desliga. A lista declara a premissa e cresce quando um arquivo é limpo.
"""
import json
import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

_BACKEND = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
_FRONT = os.path.abspath(os.path.join(_BACKEND, '..', 'frontend', 'src'))
_LOCALES = os.path.join(_FRONT, 'i18n', 'locales')
_IDIOMAS = ('pt-BR', 'en', 'es')

# Arquivos cuja copy JÁ passou pelo i18n. Entrar aqui é o que fecha a dívida de um arquivo.
_SEM_PORTUGUES_CRAVADO = [
    os.path.join('components', 'study', 'planBuilder.ts'),
    os.path.join('data', 'ranges.ts'),
]

# Heurística de "isto é português": acento, ou palavra funcional que não existe em inglês nem
# aparece em identificador de código. Termo de poker em inglês (Open, Shove, 3-Bet) passa
# limpo de propósito — por regra do projeto ele NÃO é traduzido.
_PORTUGUES = re.compile(
    r'[áàâãéêíóôõúüçÁÀÂÃÉÊÍÓÔÕÚÜÇ]'
    r'|\b(de|da|do|das|dos|em|para|com|sem|não|uma|seu|sua|pelo|pela|você)\b',
    re.IGNORECASE)

_LITERAL = re.compile(r"'([^'\n]{4,})'|\"([^\"\n]{4,})\"")

# `t("chave")` / `t('chave', {…})` — o que o código PEDE ao i18n
_CHAMADA_T = re.compile(r"""\bt\(\s*['"]([a-zA-Z][\w.]*)['"]""")


def _sem_comentario(fonte):
    return re.sub(r'/\*.*?\*/|(?<![:\w])//[^\n]*',
                  lambda m: '\n' * m.group(0).count('\n'), fonte, flags=re.S)


def _ler(caminho):
    with open(caminho, encoding='utf-8') as fh:
        return fh.read()


def _tem_chave(dados, caminho_da_chave):
    no = dados
    for parte in caminho_da_chave.split('.'):
        if not isinstance(no, dict) or parte not in no:
            return False
        no = no[parte]
    return isinstance(no, str)


def test_chaves_pedidas_pelo_planBuilder_existem_nos_3_locales():
    """Chave sem tradução vaza para a tela como texto cru. Este é o defeito que o jogador vê."""
    arquivo = os.path.join(_FRONT, 'components', 'study', 'planBuilder.ts')
    assert os.path.exists(arquivo), f'{arquivo} sumiu — o teste perdeu o alvo'

    pedidas = sorted(set(_CHAMADA_T.findall(_sem_comentario(_ler(arquivo)))))
    assert len(pedidas) >= 15, (
        f'só {len(pedidas)} chaves encontradas em planBuilder.ts. Ou a copy voltou a ser '
        'cravada, ou o padrão de `t(...)` mudou e este teste parou de enxergar')

    faltando = []
    for idioma in _IDIOMAS:
        dados = json.loads(_ler(os.path.join(_LOCALES, idioma, 'study.json')))
        for chave in pedidas:
            if not _tem_chave(dados, chave):
                faltando.append(f'  {idioma}/study.json  →  {chave}')

    assert not faltando, ('chave pedida pelo código e ausente no locale (o i18next mostra a '
                          'chave crua na tela):\n' + '\n'.join(faltando))
    print(f'OK  test_chaves_pedidas_pelo_planBuilder_existem_nos_3_locales '
          f'({len(pedidas)} chaves × {len(_IDIOMAS)} idiomas)')


def test_o_varredor_ACHA_a_chave_faltando():
    """Prova de detecção. Sem ela, o teste acima passaria por não estar lendo nada."""
    dados = {'planBuilder': {'dia': {'drill': 'Drill prático'}}}
    assert _tem_chave(dados, 'planBuilder.dia.drill'), 'não achou uma chave que EXISTE'
    assert not _tem_chave(dados, 'planBuilder.dia.cronometrado'), 'achou chave inexistente'
    # um nó intermediário não é tradução: `t("planBuilder.dia")` devolveria um objeto
    assert not _tem_chave(dados, 'planBuilder.dia'), 'aceitou um nó intermediário como texto'
    print('OK  test_o_varredor_ACHA_a_chave_faltando')


def test_arquivos_ja_limpos_nao_tem_portugues_cravado():
    violacoes = []
    literais = 0
    for rel in _SEM_PORTUGUES_CRAVADO:
        caminho = os.path.join(_FRONT, rel)
        assert os.path.exists(caminho), f'{rel} sumiu — o teste perdeu o alvo'
        texto = _sem_comentario(_ler(caminho))
        for m in _LITERAL.finditer(texto):
            literais += 1
            lit = m.group(1) or m.group(2)
            if _PORTUGUES.search(lit):
                linha = texto.count('\n', 0, m.start()) + 1
                violacoes.append(f'  src/{rel}:{linha}  {lit[:80]}')

    assert literais > 50, f'só {literais} literais lidos — o varredor não está enxergando'
    assert not violacoes, ('português cravado em arquivo que já passou pelo i18n:\n'
                           + '\n'.join(violacoes))
    print(f'OK  test_arquivos_ja_limpos_nao_tem_portugues_cravado ({literais} literais)')


def test_o_varredor_de_portugues_NAO_acusa_termo_de_poker():
    """Contraprova. Termo de poker em inglês atravessa os 3 idiomas por regra do projeto, e um
    guarda que exigisse tradução deles quebraria a própria convenção da marca."""
    for bom in ("'Open BTN'", "'3-Bet (OOP)'", "'Shove SB (<=8bb)'", "'Call vs Shove BB'",
                "'planBuilder.fallback.posicaoSpr'", "'text-muted-foreground'"):
        lit = bom.strip("'")
        assert not _PORTUGUES.search(lit), f'acusou texto que deve ficar como está: {bom}'

    for ruim in ("'Drill prático'", "'Fora de posição, vs abertura'", "'~17% das mãos'"):
        lit = ruim.strip("'")
        assert _PORTUGUES.search(lit), f'deixou passar português cravado: {ruim}'
    print('OK  test_o_varredor_de_portugues_NAO_acusa_termo_de_poker')


def test_RangeSet_nao_tem_campo_morto_de_descricao():
    """`description` era escrito em 43 lugares e lido em nenhum, com texto em português que o
    jogador nunca via. Voltar a gravá-lo sem um leitor recria a dívida — e ela sobreviveu três
    meses justamente por ser invisível."""
    fonte = _ler(os.path.join(_FRONT, 'data', 'ranges.ts'))
    assert 'export interface RangeSet' in fonte, 'RangeSet sumiu — o teste perdeu o alvo'
    corpo = fonte.split('export interface RangeSet', 1)[1].split('}', 1)[0]
    assert 'description' not in corpo, (
        'RangeSet voltou a ter `description`. Se o painel passou a EXIBIR a descrição, tudo '
        'bem: traga a string do i18n e atualize este teste. Se não exibe, o campo só carrega '
        'texto que ninguém lê.')
    print('OK  test_RangeSet_nao_tem_campo_morto_de_descricao')


if __name__ == '__main__':
    falhas = 0
    testes = [v for k, v in sorted(globals().items()) if k.startswith('test_')]
    for teste in testes:
        try:
            teste()
        except AssertionError as e:
            falhas += 1
            print(f'FALHOU  {teste.__name__}: {e}')
        except Exception as e:
            falhas += 1
            print(f'ERRO    {teste.__name__}: {type(e).__name__}: {e}')
    print(f'\nTotal: {len(testes)} | Passed: {len(testes) - falhas} | Failed: {falhas}')
    sys.exit(1 if falhas else 0)
