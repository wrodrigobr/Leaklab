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
    os.path.join('components', 'hud', 'PlayerStatsCard.tsx'),
    os.path.join('components', 'hud', 'CheckoutModal.tsx'),
    os.path.join('components', 'hud', 'ProfileCompletionCard.tsx'),
    os.path.join('components', 'replayer', 'GtoMixedBadge.tsx'),
    os.path.join('pages', 'Fundadores.tsx'),
    os.path.join('pages', 'TournamentCompare.tsx'),
    os.path.join('pages', 'Subscription.tsx'),
    os.path.join('pages', 'LeakTrainer.tsx'),
    os.path.join('components', 'hud', 'GtoAlignmentMatrixCard.tsx'),
    os.path.join('components', 'hud', 'UploadZone.tsx'),
    os.path.join('components', 'hud', 'AccountMenu.tsx'),
    os.path.join('components', 'hud', 'QuotaBanner.tsx'),
    os.path.join('components', 'hud', 'PositionMap.tsx'),
    os.path.join('components', 'study', 'ResourceList.tsx'),
]

# CONTRAPROVA do filtro de codigo. Ele ja cegou o varredor uma vez: com `(`, `)` e `"` na
# lista de "cheiro de codigo", "Você tem 3 torneios (grátis)" deixou de ser visto. Um filtro
# que silencia copy legitima e pior do que filtro nenhum, porque da a impressao de limpeza.
_AMOSTRAS_DO_FILTRO = [
    ('<p>Você tem 3 torneios (grátis) neste mês</p>', True, 'copy com parênteses'),
    ('<p>Análise "profunda" da mão</p>', True, 'copy com aspas'),
    ('<h2>O que você recebe</h2>', True, 'texto JSX solto'),
    ('const x = a >= 0 ? b[i] : c; const y = !!z && w !== "ativo";', False, 'código puro'),
    ('className={cn("flex", ativo && "on")}', False, 'className'),
]


def test_o_filtro_de_codigo_NAO_silencia_copy_legitima():
    for fonte, esperado, rotulo in _AMOSTRAS_DO_FILTRO:
        achou = any(_PORTUGUES.search(lit) for _, lit in _todo_texto_de_tela(fonte))
        assert achou == esperado, (
            f'{rotulo}: esperava {"achar" if esperado else "ignorar"} e o varredor '
            f'{"achou" if achou else "ignorou"} — {fonte[:60]!r}')
    print(f'OK  test_o_filtro_de_codigo_NAO_silencia_copy_legitima '
          f'({len(_AMOSTRAS_DO_FILTRO)} amostras)')

# Copy que E divida, e que fica em portugues POR DECISAO. Sem esta lista, quem vier depois
# lê o placar do `scripts/medir_copy_cravada.py` como "falta traduzir isto" e refaz a
# discussão do zero.
_EXCECOES_DECLARADAS = {
    os.path.join('pages', 'Privacy.tsx'):
        'política de privacidade (LGPD/GDPR): tradução imprecisa de termo legal cria '
        'exposição real, e em português o texto está correto. Traduzir exige revisão '
        'jurídica, não só i18n',
    os.path.join('pages', 'admin'):
        'o painel admin tem UM leitor, que fala português',
    os.path.join('pages', 'coach'):
        '1 coach em produção; vale quando houver coach que não fale português',
}


def test_as_excecoes_de_i18n_ainda_apontam_para_arquivos_REAIS():
    """Exceção que aponta para arquivo inexistente vira permissão silenciosa: o arquivo é
    renomeado, a exceção continua na lista, e ninguém percebe que ela parou de valer."""
    for alvo, porque in _EXCECOES_DECLARADAS.items():
        caminho = os.path.join(_FRONT, alvo)
        assert os.path.exists(caminho), (
            f'a exceção {alvo!r} não existe mais ({porque}). Se o arquivo saiu, tire a '
            'exceção; se foi renomeado, atualize o caminho')
        assert len(porque) > 30, f'exceção {alvo!r} sem motivo escrito'
    print(f'OK  test_as_excecoes_de_i18n_ainda_apontam_para_arquivos_REAIS '
          f'({len(_EXCECOES_DECLARADAS)} exceções)')

# Heurística de "isto é português": acento, ou palavra funcional que não existe em inglês nem
# aparece em identificador de código. Termo de poker em inglês (Open, Shove, 3-Bet) passa
# limpo de propósito — por regra do projeto ele NÃO é traduzido.
#
# A lista nasceu curta e ISSO ERA UM BURACO: a quebra deliberada com "Pro liberado por 6
# meses" NÃO acusou, porque a frase não tem acento nem nenhuma das palavras que eu tinha
# listado. O guarda parecia funcionar; funcionava só para o português acentuado.
_PORTUGUES = re.compile(
    r'[áàâãéêíóôõúüçÁÀÂÃÉÊÍÓÔÕÚÜÇ]'
    r'|\b(de|da|do|das|dos|em|para|com|sem|não|uma|seu|sua|pelo|pela|você'
    r'|por|que|mais|quando|como|onde|ainda|já|ou|nos|nas|aos|isso|este|esta'
    r'|entre|até|mas|foi|ser|tem|vai|cada|todo|toda|quem)\b',
    re.IGNORECASE)

_LITERAL = re.compile(r"'([^'\n]{4,})'|\"([^\"\n]{4,})\"")

# As TRÊS formas de escrever texto na tela, porque para quem LÊ elas são a mesma coisa. Medir
# só a primeira me fez errar o tamanho da dívida duas vezes seguidas (308 → 537 → 628), e um
# guarda que enxerga menos que o medidor é cobertura que não cobre.
_JSX_SOLTO = re.compile(r'>([^<>{}]*[A-Za-zÀ-ÿ]{3}[^<>{}]*)<')
_TEMPLATE = re.compile(r'`([^`]*[A-Za-zÀ-ÿ]{3}[^`]*)`')
# `pokerstars.com` casava "com" como palavra portuguesa.
_URLISH = re.compile(r'^\S+\.(com|br|io|net|org|gg|tsx?|jsx?|json|svg|png)(/\S*)?$', re.I)

# Um regex de crase-a-crase não distingue o INTERIOR de um template do INTERVALO entre dois
# templates distintos: num arquivo cheio de cn(`...`), o "conteúdo" capturado vira um pedaço
# de JSX. Estes marcadores só aparecem em código, nunca numa frase para o jogador.
#
# `(`, `)` e `"` estavam aqui e CEGARAM o detector: "Você tem 3 torneios (grátis)" e
# 'Análise "profunda"' deixaram de ser vistos. Parêntese e aspas são comuns em copy — só
# entram marcadores que praticamente NÃO aparecem numa frase para o jogador.
_CHEIRO_DE_CODIGO = ('</', '/>', 'className', '=>', '{{', "':", '??', '!==', '===',
                     '; ', 'const ', 'return ', '&&', '||')


def _parece_codigo(trecho):
    return any(marca in trecho for marca in _CHEIRO_DE_CODIGO)


# Trechos que a heurística acusa e que NÃO são copy. Sem esta lista, quem retomar o placar
# reinvestiga os mesmos catorze — e cada um custou abrir o arquivo para entender o papel.
#
# O padrão que os une: em todos, o português é um IDENTIFICADOR, não texto para o jogador.
_NAO_E_COPY = {
    'Pré-flop': 'valor do tipo `Street`, comparado com === (chave do filtro de mãos)',
    'satélite': 'termo de BUSCA em `nome.includes("satélite")`, não rótulo',
    'Sólido': 'chave de mapa pt→slug; o VALOR vem do backend nesse formato',
    'como-funciona': 'id de âncora HTML',
    '[GTO] solicitando análise': 'console.log — texto de desenvolvedor',
    '[GTO] erro na solicitação:': 'console.error — texto de desenvolvedor',
    '[GTO] handId ou tournamentId vazio': 'console.log — texto de desenvolvedor',
    'PokerStars Hand #': 'FORMATO DE ARQUIVO que o parser lê, não copy: `hhGenerator` monta '
                        'um hand history; traduzir quebraria a importação',
}


def _todo_texto_de_tela(codigo):
    """(posição, texto) de tudo que vira texto na tela: aspas, JSX solto e template."""
    for m in _LITERAL.finditer(codigo):
        yield m.start(), (m.group(1) or m.group(2))
    # O filtro vale para OS DOIS: `_JSX_SOLTO` também casa o `>` de um operador `>=` e segue
    # até o próximo `<`, devolvendo uma linha de código como se fosse texto de tela.
    for padrao in (_JSX_SOLTO, _TEMPLATE):
        for m in padrao.finditer(codigo):
            limpo = ' '.join(m.group(1).split())
            if limpo and not _parece_codigo(limpo):
                yield m.start(), limpo

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
        for pos, lit in _todo_texto_de_tela(texto):
            literais += 1
            if not _URLISH.match(lit) and _PORTUGUES.search(lit):
                linha = texto.count('\n', 0, pos) + 1
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
