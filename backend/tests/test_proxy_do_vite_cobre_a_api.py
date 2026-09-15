# -*- coding: utf-8 -*-
"""Em dev, toda chamada de API tem proxy, e nenhuma delas rouba a rota de tela.

-- O defeito (auditoria NLU-11, 15/09) -----------------------------------------------------

O dev server do vite tem dois papeis no mesmo host: servir a SPA e proxiar a API. O front usa
`BASE=""` em dev (o `.env` tem `VITE_API_URL=` vazio, e `??` nao cai no default com string
vazia), entao TODA chamada de `lib/api.ts` passa pelo proxy. Medido com o dev server no ar e o
backend desligado:

  * `/coaches?limit=1`, `/coaches/62` e `/shared-hands/feed?sort=new` recebiam 404 do PROPRIO
    vite, porque nao tinham chave e o fallback da SPA so responde a `Accept: text/html`. Em dev,
    o diretorio de coaches, o perfil publico de coach e a tela `/maos` nao carregavam;
  * dar F5 em `/tournaments/5`, `/academy/3bet`, `/study`, `/subscription`, `/profile` ou
    `/admin` proxiava a PAGINA para o backend, e a tela virava JSON de erro.

A lista certa de excecoes nao era uma lista: 8 prefixos sao API e tela ao mesmo tempo, e o
caminho nao os separa. Quem separa e o `Accept`. Nada disso chega a producao (Cloudflare Pages
serve a SPA, a API mora em outro dominio); o risco e alguem "consertar" o produto por um sintoma
do proxy.

-- O que este arquivo defende --------------------------------------------------------------

1. Todo caminho que o front chama casa com uma chave do proxy.
2. Existe UM bypass por `Accept: text/html`, aplicado a todas as chaves de uma volta sobre a
   lista (nao uma copia por chave). Sem ele, chave que e prefixo de rota de tela e defeito.
3. Prefixo de API sem chave esta na lista DECLARADA de excecoes, com motivo.

Os tres leitores (proxy, `App.tsx`, chamadas do front) provam que leem com fontes forjadas.
"""
import glob
import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

RAIZ = os.path.join(os.path.dirname(__file__), '..')
FRONT = os.path.abspath(os.path.join(RAIZ, '..', 'frontend'))

#: Prefixo de API que NAO tem chave no proxy, e por que. Front que passe a chamar um deles faz
#: o teste falhar, o que e o ponto.
SEM_PROXY_DE_PROPOSITO = {
    '/debug':    'so debug de admin, por curl',
    '/gto':      'so admin e o consumer do solver',
    '/telegram':  'webhook do bot, nunca o navegador',
}


def _sem_comentario_de_linha(texto):
    """Tira a parte comentada de cada linha. As notas da lista de prefixos CITAM caminhos entre
    aspas para explicar a barra final, e sem isto a citacao entrava como chave."""
    return '\n'.join(re.sub(r'//.*$', '', l) for l in texto.splitlines())


def chaves_do_proxy(vite):
    """As chaves do proxy, nas duas formas: entrada inline com `target` (antiga) e a lista
    `PREFIXOS_DE_API` (atual)."""
    chaves = re.findall(r'^\s*"(/[^"]+)":\s*\{\s*target', vite, re.M)
    lista = re.search(r'const PREFIXOS_DE_API\s*=\s*\[(.*?)\];', vite, re.S)
    if lista:
        chaves += re.findall(r'"(/[^"]+)"', _sem_comentario_de_linha(lista.group(1)))
    return chaves


def tem_bypass_unico(vite):
    """O bypass le o `Accept` E esta LIGADO dentro da volta sobre a lista.

    Nao basta a palavra `bypass` aparecer no arquivo: a primeira versao deste teste conferia
    isso, e quando eu tirei o `bypass:` do objeto mapeado ela CALOU, porque a funcao continuava
    definida e o comentario continuava falando dela. O que vale e a fiacao, entao o teste olha
    dentro do corpo do `.map`. Comentario nao e evidencia, inclusive contra mim.
    """
    limpo = _sem_comentario_de_linha(vite)
    if not re.search(r'headers\.accept[^\r\n]*text/html', limpo):
        return False
    volta = re.search(r'PREFIXOS_DE_API\.map\((.*?)\n\s*\);', limpo, re.S)
    return bool(volta) and 'bypass:' in volta.group(1)


def rotas_de_tela(apptsx):
    return sorted(set(re.findall(r'path="(/[^"]*)"', apptsx)))


def caminhos_chamados(raiz):
    """Os caminhos de API que o front chama (`request(...)` e `fetch(`${base}...`)`)."""
    out = set()
    for f in glob.glob(os.path.join(raiz, 'src', '**', '*.ts*'), recursive=True):
        if '.test.' in f:
            continue
        with open(f, encoding='utf-8', errors='ignore') as fh:
            t = fh.read()
        for m in re.finditer(
                r"request(?:<[^(]*>)?\(\s*[`'\"](/[A-Za-z0-9_\-]+(?:/[A-Za-z0-9_\-${}.]*)*)", t):
            out.add(m.group(1))
        for m in re.finditer(r"fetch\(\s*`\$\{base\}(/[A-Za-z0-9_\-]+)", t):
            out.add(m.group(1))
    return sorted(out)


def prefixos_do_backend():
    with open(os.path.join(RAIZ, 'api', 'app.py'), encoding='utf-8') as f:
        rotas = re.findall(r"@app\.route\('(/[^']*)'", f.read())
    return sorted({'/' + r.split('/')[1] for r in rotas if len(r.split('/')) > 1 and r.split('/')[1]})


def _ler(*partes):
    with open(os.path.join(FRONT, *partes), encoding='utf-8') as f:
        return f.read()


def test_toda_chamada_do_front_casa_com_uma_chave_do_proxy():
    chaves = chaves_do_proxy(_ler('vite.config.ts'))
    chamados = caminhos_chamados(FRONT)
    assert len(chamados) > 100, 'o leitor achou %d chamadas: a forma do api.ts mudou?' % len(chamados)
    sem_proxy = [c for c in chamados if not any(c.startswith(k) for k in chaves)]
    assert not sem_proxy, 'em dev estas chamadas recebem 404 do vite: %s' % sem_proxy


def test_o_bypass_por_accept_existe_e_e_unico():
    vite = _ler('vite.config.ts')
    assert tem_bypass_unico(vite), 'sem bypass por Accept aplicado a toda a lista'
    # e ele devolve a SPA, nao um 404
    assert 'index.html' in vite


def test_chave_que_e_prefixo_de_tela_exige_o_bypass():
    vite = _ler('vite.config.ts')
    chaves = chaves_do_proxy(vite)
    telas = rotas_de_tela(_ler('src', 'App.tsx'))
    assert len(telas) > 20, 'o leitor achou %d rotas de tela: App.tsx mudou de forma?' % len(telas)
    captura = sorted({k for k in chaves for r in telas if r.startswith(k)})
    if captura:
        assert tem_bypass_unico(vite), \
            'chaves que capturam rota de tela sem bypass: %s' % captura


def test_prefixo_de_api_sem_chave_esta_declarado():
    chaves = chaves_do_proxy(_ler('vite.config.ts'))
    faltando = [p for p in prefixos_do_backend() if not any(p.startswith(k) or k.startswith(p)
                                                            for k in chaves)]
    naodeclarados = [p for p in faltando if p not in SEM_PROXY_DE_PROPOSITO]
    assert not naodeclarados, \
        'prefixo de API sem chave e sem motivo declarado: %s' % naodeclarados


def test_os_leitores_provam_que_leem():
    """Regra 1: cada leitor recebe uma fonte forjada e tem de responder o que se espera."""
    antigo = ('    proxy: {\n'
              '      "/auth":   { target: "http://127.0.0.1:5000", changeOrigin: true },\n'
              '      "/coach/": { target: "http://127.0.0.1:5000", changeOrigin: true },\n'
              '    },\n')
    assert chaves_do_proxy(antigo) == ['/auth', '/coach/']
    assert tem_bypass_unico(antigo) is False

    novo = ('const PREFIXOS_DE_API = [\n'
            '  "/auth",\n'
            '  "/coach/",   // barra final: "/coach" exato nao e rota de API\n'
            '];\n'
            'const paraASpa = (req) =>\n'
            '  (req.headers.accept ?? "").includes("text/html") ? "/index.html" : undefined;\n'
            'const p = Object.fromEntries(\n'
            '  PREFIXOS_DE_API.map((k) => [k,\n'
            '    { target: API, changeOrigin: true, bypass: paraASpa }]),\n'
            ');\n')
    # o `"/coach"` citado no COMENTARIO nao entra como chave
    assert chaves_do_proxy(novo) == ['/auth', '/coach/'], chaves_do_proxy(novo)
    assert tem_bypass_unico(novo) is True
    # sem a volta sobre a lista NAO conta como unico
    sem_volta = novo.replace('PREFIXOS_DE_API.map', 'OUTRA_COISA.map')
    assert tem_bypass_unico(sem_volta) is False
    # e a FIACAO e que vale: tirar o `bypass:` do objeto tem de acusar, mesmo com a funcao ainda
    # definida e o comentario ainda falando dela. Foi o erro da 1a versao deste teste: ela
    # conferia a palavra `bypass` no arquivo e calou quando eu desliguei a fiacao de proposito.
    sem_fiacao = novo.replace(', bypass: paraASpa', '')
    assert tem_bypass_unico(sem_fiacao) is False
    comentada = novo.replace('    { target: API, changeOrigin: true, bypass: paraASpa }]),',
                             '    { target: API, changeOrigin: true }]),   // bypass: paraASpa')
    assert tem_bypass_unico(comentada) is False

    assert rotas_de_tela('<Route path="/coaches/:id" element={<X/>} />') == ['/coaches/:id']


if __name__ == '__main__':
    falhas = 0
    testes = [v for k, v in sorted(globals().items()) if k.startswith('test_')]
    for t in testes:
        try:
            t()
            print('OK      %s' % t.__name__)
        except AssertionError as e:
            falhas += 1
            print('FALHOU  %s: %s' % (t.__name__, e))
        except Exception as e:
            falhas += 1
            print('ERRO    %s: %s: %s' % (t.__name__, type(e).__name__, e))
    print('\nTotal: %d | Passed: %d | Failed: %d' % (len(testes), len(testes) - falhas, falhas))
    sys.exit(1 if falhas else 0)
