# -*- coding: utf-8 -*-
"""Coletor dirigido do GTO Wizard: percorre uma LISTA FECHADA de nos e grava no acervo.

    python scripts/coletor_gw.py --login                  # uma vez: abre o browser p/ voce logar
    python scripts/coletor_gw.py --plano docs/gw_plano_hu.json --max-nos 40

── Por que existe ─────────────────────────────────────────────────────────────────────────────

Ate aqui a captura era manual: DevTools aberto, dezenas de cliques, "Save all as HAR". Funcionou,
mas custou dois acidentes que este script existe para nao repetir:

- **nos perdidos por cache**: o browser respondeu do cache e o HAR nao guarda resposta cacheada,
  entao `ROOT` e `R2` de uma captura inteira vieram vazios;
- **um HAR sobrescrito antes do import** (todos se chamavam `sbxbb.har`), e o modulo de mesa
  cheia se perdeu.

── O que este script NAO e ────────────────────────────────────────────────────────────────────

**Nao e um aspirador.** A conta e do usuario e o limite e por conta — automatizar nao cria cota.
O desenho e deliberadamente do tamanho da mao humana:

- percorre **so** o plano declarado (`--plano`), nunca a arvore inteira;
- **pausa** entre requisicoes (`--pausa`, com jitter) e **teto** de nos por execucao (`--max-nos`);
- **para no primeiro sinal de limite** (HTTP 429/402/403 ou corpo sem solucao) em vez de insistir;
- **grava a cada no**, para que uma parada no meio preserve o que ja veio.

── Login: o coletor NAO loga, ele se CONECTA ──────────────────────────────────────────────────

O Google recusa OAuth em navegador iniciado por automacao ("Esse navegador ou app pode nao ser
seguro") — e isso e uma decisao deles, nao um obstaculo a contornar. Entao o fluxo padrao e o
inverso: **voce** abre o Chrome, loga como sempre, e o script ATTACHA na sessao que ja existe
(`--cdp`). Nada e automatizado no login, e o navegador e literalmente o seu.

── Como descobre o nome do no ─────────────────────────────────────────────────────────────────

O sizing do GW muda por profundidade (`R2-R4.5` a 14bb, `R2-R5.5` a 30bb). Adivinhar geraria
requisicao invalida e queimaria cota. Entao o plano fala em INTENCAO ('raise_min', 'allin',
'call') e o token sai da resposta do proprio no pai — a arvore se descobre andando.
"""
from __future__ import annotations

import argparse
import json
import random
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from importar_har_hu import no_de_resposta, valida_no        # noqa: E402  (porta unica)

API = 'https://api.gtowizard.com/v4/solutions/spot-solution/'
APP = 'https://app.gtowizard.com/'


class LimiteAtingido(Exception):
    """Sinal de parar TUDO: cota, bloqueio ou resposta que nao e solucao."""


class DepthIndisponivel(Exception):
    """HTTP 403 na PRIMEIRA requisicao de uma profundidade: a depth nao esta disponivel para
    ESTA conta — atras do paywall do tier ou fora da grade.

    Provado em 15/08 com 28.125: o 403 abortou o plano inteiro duas vezes, e o diagnostico
    inicial ("degrau fora da grade") estava ERRADO — o app mostra "Upgrade to get access to
    this solution / Premium Tournament users and higher". E paywall, e o free tier serve as
    outras depths do plano normalmente. Quem trata pula SO a depth; 403 no MEIO de uma
    caminhada (depois de resposta valida) continua sendo LimiteAtingido, porque servidor que
    muda de ideia no meio e bloqueio de sessao, nao paywall de depth."""


# ── tokens ────────────────────────────────────────────────────────────────────────────────────

def token_da_acao(acao: dict, stack: float) -> str | None:
    """Nome do no filho para uma acao, no dialeto do `preflop_actions` do GW.

    **O payload JA DIZ o token**, no campo `code` ('F', 'C', 'R2', 'RAI'). A primeira versao
    derivava por tamanho ("betsize >= stack - 0,5 e all-in") e acertava, mas era heuristica onde
    havia dado declarado — a mesma familia de erro do `history_spot` adivinhado. A derivacao
    sobrevive so como fallback para no antigo, gravado antes de guardarmos `code`.
    """
    if acao.get('code'):
        return str(acao['code'])
    tipo = (acao.get('type') or '').upper()
    if tipo == 'FOLD':
        return 'F'                           # em mesa cheia foldar PASSA a vez, nao encerra
    if tipo in ('CALL', 'CHECK'):
        return 'C'
    bs = acao.get('betsize')
    if bs in (None, '', 0):
        return None
    if acao.get('allin') or float(bs) >= float(stack) - 0.5:
        return 'RAI'
    txt = str(bs).rstrip('0').rstrip('.') if '.' in str(bs) else str(bs)
    return f'R{txt}'


def _eh_allin(a: dict, stack: float) -> bool:
    if 'allin' in a:
        return bool(a['allin'])              # o payload declara; nao precisamos inferir
    try:
        return float(a.get('betsize') or 0) >= float(stack) - 0.5
    except (TypeError, ValueError):
        return False


def escolhe_acao(desejo: str, acoes: list[dict], stack: float) -> dict | None:
    """Resolve a INTENCAO do plano contra as acoes que o no realmente oferece."""
    raises = [a for a in acoes if (a.get('type') or '').upper() == 'RAISE' and a.get('betsize')]
    allin = [a for a in raises if _eh_allin(a, stack)]
    normais = sorted((a for a in raises if a not in allin),
                     key=lambda a: float(a.get('betsize') or 0))
    if desejo == 'allin':
        return allin[0] if allin else None
    if desejo == 'raise_min':
        return normais[0] if normais else None
    if desejo == 'raise_max':
        return normais[-1] if normais else None
    if desejo in ('call', 'limp', 'check'):
        return next((a for a in acoes
                     if (a.get('type') or '').upper() in ('CALL', 'CHECK')), None)
    if desejo == 'fold':
        # So faz sentido em mesa cheia, onde o fold passa a vez ate chegar em quem queremos.
        return next((a for a in acoes if (a.get('type') or '').upper() == 'FOLD'), None)
    raise ValueError(f'desejo desconhecido no plano: {desejo!r}')


# ── caminhada ─────────────────────────────────────────────────────────────────────────────────

def caminha(buscar, gametype: str, depth: str, linhas: list[list[str]],
            ao_coletar=None, pausar=None, conhecidos=None) -> dict:
    """Percorre as `linhas` de UMA profundidade. `buscar(params) -> (status, corpo)`.

    Prefixos sao memoizados: `[raise_min]` e `[raise_min, allin]` compartilham ROOT e R2 e
    gastam UMA requisicao cada, nao duas. Cota economizada e cota que sobra para no novo.

    `conhecidos` (o acervo ja em disco) evita refazer requisicao entre EXECUCOES: a caminhada
    precisa das acoes do no pai para achar o filho, e essas acoes ja estao gravadas. Sem isso,
    cada nova execucao pagava ROOT e R2 de novo antes de chegar ao no inedito.
    """
    stack = float(depth)
    cache: dict[str, dict] = {}
    coletados: dict[str, dict] = {}
    conhecidos = conhecidos or {}

    def obter(no_str: str) -> dict:
        if no_str in cache:
            return cache[no_str]
        chave_ja = f"{depth}|{no_str or 'ROOT'}"
        if chave_ja in conhecidos:
            no = dict(conhecidos[chave_ja])
            no['_acoes_cruas'] = acoes_cruas_do_no(no)
            cache[no_str] = no
            print(f'  ja tinha {chave_ja}')
            return no
        if pausar and cache:
            pausar()
        params = {'gametype': gametype, 'depth': depth, 'stacks': '',
                  'preflop_actions': no_str, 'flop_actions': '', 'turn_actions': '',
                  'river_actions': '', 'board': ''}
        status, corpo = buscar(params)
        if status != 200:
            if status == 403 and not cache:
                # Nada foi obtido nesta depth ainda (nem conhecido, nem buscado): o 403 e da
                # depth, nao da sessao. Quem chama decide pular.
                raise DepthIndisponivel(
                    f'HTTP 403 em depth={depth} — paywall do tier (ou degrau fora da grade)')
            raise LimiteAtingido(f'HTTP {status} em depth={depth} no={no_str or "ROOT"}')
        if not isinstance(corpo, dict) or not corpo.get('action_solutions'):
            # Nao e "no vazio": e resposta que nao contem solucao — cota, bloqueio ou spot
            # invalido. Seguir adiante so gastaria requisicao contra um servidor que ja disse nao.
            raise LimiteAtingido(f'resposta sem solucao em depth={depth} no={no_str or "ROOT"}')
        no = no_de_resposta(corpo, params)
        if no is None:
            raise LimiteAtingido(f'resposta indecodificavel em depth={depth} no={no_str}')
        no['_acoes_cruas'] = [s.get('action') or {} for s in corpo['action_solutions']]
        cache[no_str] = no
        chave = f"{depth}|{no_str or 'ROOT'}"
        motivo = valida_no(no)
        if motivo:
            print(f'  REJEITADO {chave}: {motivo}')
        else:
            no_limpo = {k: v for k, v in no.items() if not k.startswith('_')}
            coletados[chave] = no_limpo
            print(f'  OK  {chave:26s} ator={no["ator"]:2s} acoes={no["acoes"]}')
            if ao_coletar:
                ao_coletar(gametype, chave, no_limpo)
        return no

    for linha in linhas:
        no_str = ''
        obter(no_str)                                   # ROOT sempre
        for desejo in linha:
            acao = escolhe_acao(desejo, cache[no_str]['_acoes_cruas'], stack)
            if acao is None:
                print(f'  (pulei {linha}: no {no_str or "ROOT"} nao oferece {desejo})')
                break
            token = token_da_acao(acao, stack)
            if token is None:
                break
            no_str = f'{no_str}-{token}' if no_str else token
            obter(no_str)
    return coletados


# ── persistencia ──────────────────────────────────────────────────────────────────────────────

def gravador(caminho: Path):
    """Grava a CADA no. Uma parada no meio (limite, ctrl-C, queda) preserva o coletado."""
    def grava(gametype: str, chave: str, no: dict):
        atual = {}
        if caminho.exists():
            try:
                atual = json.loads(caminho.read_text(encoding='utf-8'))
            except Exception:
                atual = {}
        atual.setdefault(gametype, {})[chave] = no
        caminho.parent.mkdir(parents=True, exist_ok=True)
        caminho.write_text(json.dumps(atual, ensure_ascii=False, indent=1), encoding='utf-8')
    return grava


# ── browser ───────────────────────────────────────────────────────────────────────────────────

def _contexto(perfil: Path, headless: bool, navegador: str = 'chrome'):
    """Chromium empacotado ou o Chrome/Edge instalado na maquina.

    Default e o **Chrome real**: e o navegador que voce ja usa no GW, entao user-agent e
    fingerprint sao os de sempre — um Chromium de automacao destoa do trafego normal da conta
    sem nenhum ganho. Cai para o Chromium empacotado se o canal nao estiver instalado.

    O perfil e SEPARADO do seu Chrome do dia a dia (`.gw_profile`): o Chrome recusa abrir um
    perfil ja em uso, e apontar para o seu perfil real misturaria a automacao com suas abas.
    """
    from playwright.sync_api import sync_playwright
    pw = sync_playwright().start()
    opcoes = dict(headless=headless, viewport={'width': 1280, 'height': 800})
    canal = {'chrome': 'chrome', 'edge': 'msedge'}.get(navegador)
    if canal:
        try:
            ctx = pw.chromium.launch_persistent_context(str(perfil), channel=canal, **opcoes)
            return pw, ctx
        except Exception as e:
            print(f'{navegador} nao disponivel ({type(e).__name__}); usando o Chromium empacotado')
    ctx = pw.chromium.launch_persistent_context(str(perfil), **opcoes)
    return pw, ctx


def _chrome_exe() -> str:
    for c in (r'C:\Program Files\Google\Chrome\Application\chrome.exe',
              r'C:\Program Files (x86)\Google\Chrome\Application\chrome.exe'):
        if Path(c).exists():
            return c
    return 'chrome'


def _instrucoes_cdp(porta: int, perfil: Path) -> str:
    return '\n'.join([
        '',
        'Abra o Chrome VOCE MESMO, com um perfil so para isto:',
        '',
        f'  "{_chrome_exe()}" --remote-debugging-port={porta} --user-data-dir="{perfil}"',
        '',
        'Logue no GTO Wizard nessa janela. O login e normal, feito por voce — o Google recusa',
        'OAuth em navegador aberto por automacao, e isso e decisao deles, nao obstaculo a burlar.',
        'Deixe a janela aberta e rode o coletor de novo:',
        '',
        '  python scripts/coletor_gw.py --plano docs/gw_plano_hu.json --max-nos 40',
        '',
    ])


def _conecta_cdp(porta: int):
    """Attacha no Chrome que VOCE abriu. Retorna (pw, browser, page) — o browser NAO e nosso
    para fechar."""
    from playwright.sync_api import sync_playwright
    pw = sync_playwright().start()
    browser = pw.chromium.connect_over_cdp(f'http://localhost:{porta}')
    ctx = browser.contexts[0] if browser.contexts else browser.new_context()
    page = next((p for p in ctx.pages if 'gtowizard.com' in p.url), None)
    if page is None:
        page = ctx.new_page()
        page.goto(APP)
    return pw, browser, page


def url_do_spot(params: dict) -> str:
    """URL da SPA para um no.

    **`history_spot` e o indice do spot dentro da linha, e nao e decorativo.** A primeira versao
    mandava `history_spot=0` fixo: o app entao exibia a RAIZ da linha e ignorava o
    `preflop_actions`, e o coletor esperava 30s por um `R2` que nunca vinha. Lido da URL que o
    proprio GW montou ao clicar: ROOT -> 0, `R2` -> 1, `R2-RAI` -> 2 — o numero de acoes ja
    jogadas na linha.
    """
    from urllib.parse import urlencode
    acoes = params.get('preflop_actions') or ''
    q = {
        'soltab': 'strategy', 'solution_type': 'gwiz', 'gmfs_solution_tab': 'ai_sols',
        'gametype': params['gametype'], 'depth': params['depth'],
        'preflop_actions': acoes,
        'gmfft_sort_key': '0', 'gmfft_sort_order': 'desc',
        'history_spot': str(len(acoes.split('-')) if acoes else 0),
    }
    return f'{APP}solutions?{urlencode(q)}'


def acoes_cruas_do_no(no: dict) -> list[dict]:
    """Acoes de um no JA GRAVADO, para caminhar sem repedi-lo. Usa os `codigos` quando o no foi
    capturado depois de passarmos a guarda-los; senao reconstroi do rotulo."""
    cruas = acoes_cruas_de_rotulos(no.get('acoes') or [])
    for acao, code in zip(cruas, (no.get('codigos') or [])):
        if code:
            acao['code'] = code
    return cruas


def acoes_cruas_de_rotulos(rotulos: list[str]) -> list[dict]:
    """'RAISE 4.5' -> {'type': 'RAISE', 'betsize': '4.5'}. Volta do que foi GRAVADO.

    Serve para reaproveitar no que o acervo ja tem: com a cota diaria do GW sendo o recurso mais
    escasso da operacao, refazer uma requisicao de no conhecido e cota queimada em dado que ja
    esta no disco.
    """
    cruas = []
    for r in rotulos:
        partes = r.split(' ', 1)
        acao = {'type': partes[0]}
        if len(partes) > 1:
            acao['betsize'] = partes[1]
        cruas.append(acao)
    return cruas


def _mesma_chave(url: str, params: dict) -> bool:
    from urllib.parse import parse_qs, urlparse
    q = parse_qs(urlparse(url).query)
    def v(k):
        return (q.get(k) or [''])[0]
    return (v('gametype') == params['gametype'] and v('depth') == params['depth']
            and v('preflop_actions') == (params.get('preflop_actions') or ''))


_MARCADORES_DE_LIMITE = (
    'daily solution browsing limit',        # o texto exato que o GW mostrou em 07/08
    'reached your free daily',
    'limite diario',
    'limite diário',
)


def _aviso_de_limite(page) -> str | None:
    """A propria pagina diz quando a cota acabou. Perguntar a ela e mais barato e mais honesto
    do que esperar o timeout e depois adivinhar entre cota, sessao caida e rota mudada."""
    try:
        txt = page.evaluate('document.body.innerText') or ''
    except Exception:
        return None
    baixo = str(txt).lower()
    for m in _MARCADORES_DE_LIMITE:
        if m in baixo:
            for linha in str(txt).splitlines():
                if m in linha.lower():
                    return linha.strip()[:160]
            return m
    return None


def buscador_navegando(page, espera_ms: int = 30000, passo_ms: int = 250):
    """Navega ate o no e ESCUTA a requisicao que o proprio app faz.

    Forjar a chamada nao funciona e nao deve funcionar: o app assina cada requisicao com um
    header `google-anal-id` gerado por um script proprio, e um `fetch` nosso chega sem ele
    ("Failed to fetch"). Entao nao imitamos o app — deixamos o app trabalhar e so lemos o que
    passa, que e exatamente o que o HAR fazia.

    **Casa a resposta com o no PEDIDO.** Se a rota da SPA mudar e o app entregar outro no, isto
    acusa em vez de gravar dado certo sob chave errada — que seria o pior desfecho possivel,
    porque a carta errada nao se denuncia depois.
    """
    def buscar(params: dict):
        capturado: dict = {}

        def ao_responder(resp):
            try:
                if '/spot-solution' not in resp.url or not _mesma_chave(resp.url, params):
                    return
                if 'body' not in capturado:
                    capturado['status'] = resp.status
                    capturado['body'] = resp.json()
            except Exception:
                pass                        # resposta sem corpo legivel: a proxima serve

        page.on('response', ao_responder)
        try:
            # O app do GW tem lentidao INTERMITENTE: em 15/08 tres execucoes morreram no goto
            # de 30s depois de dezenas de navegacoes rapidas, sempre em nos diferentes — nao e
            # limite (o aviso de cota aparece na pagina, e ha guarda para ele), e babar
            # reexecucao a cada soluco desperdicava a sessao aberta. Uma retentativa com
            # timeout dobrado resolve o soluco; se a SEGUNDA tambem estourar, ai sim e problema
            # de verdade e o erro sobe.
            try:
                page.goto(url_do_spot(params), wait_until='domcontentloaded')
            except Exception:
                page.wait_for_timeout(3000)
                page.goto(url_do_spot(params), wait_until='domcontentloaded',
                          timeout=60000)
            esperou = 0
            while 'body' not in capturado and esperou < espera_ms:
                page.wait_for_timeout(passo_ms)
                esperou += passo_ms
                aviso = _aviso_de_limite(page)
                if aviso:
                    raise LimiteAtingido(f'o GW respondeu: "{aviso}"')
        finally:
            page.remove_listener('response', ao_responder)

        if 'body' not in capturado:
            raise LimiteAtingido(
                f"o app nao entregou o no {params.get('preflop_actions') or 'ROOT'} "
                f"(depth={params['depth']}) em {espera_ms // 1000}s — sessao caiu, cota, "
                f"ou a rota da SPA mudou")
        return capturado['status'], capturado['body']
    return buscar


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--plano', default='docs/gw_plano_hu.json')
    ap.add_argument('--out', default='docs/hu_ranges_har.json')
    ap.add_argument('--perfil', default='.gw_profile',
                    help='diretorio do perfil do Chromium (fica fora do git)')
    ap.add_argument('--login', action='store_true', help='abre o browser para voce logar e sai')
    ap.add_argument('--pausa', type=float, default=8.0, help='segundos entre requisicoes')
    ap.add_argument('--max-nos', type=int, default=40, help='teto de nos NOVOS por execucao')
    ap.add_argument('--navegador', default='chrome', choices=('chrome', 'edge', 'chromium'),
                    help='so para --login: Chrome instalado, Edge, ou o Chromium empacotado')
    ap.add_argument('--cdp', type=int, default=9222, metavar='PORTA',
                    help='attacha no Chrome que voce abriu com --remote-debugging-port (padrao)')
    ap.add_argument('--refazer', action='store_true',
                    help='rebusca nos que o acervo ja tem (padrao: reaproveita, poupa cota)')
    ap.add_argument('--sem-cdp', action='store_true',
                    help='abre o proprio navegador em vez de attachar (o Google bloqueia o login)')
    args = ap.parse_args()

    perfil = Path(args.perfil).resolve()
    perfil.mkdir(parents=True, exist_ok=True)

    if args.login and not args.sem_cdp:
        print(_instrucoes_cdp(args.cdp, perfil))
        return 0

    if args.login:
        pw, ctx = _contexto(perfil, headless=False, navegador=args.navegador)
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        page.goto(APP)
        print('\nLogue no GTO Wizard nesta janela. Quando o estudo estiver aberto, volte aqui e')
        print('tecle ENTER — a sessao fica salva no perfil e as proximas execucoes nao pedem login.')
        input()
        ctx.close(); pw.stop()
        print('sessao salva em', perfil)
        return 0

    plano = json.loads(Path(args.plano).read_text(encoding='utf-8'))
    # O plano manda no destino: HU e mesa cheia nao dividem acervo (o motor le so o de HU, e um
    # no de 8-max entrando la seria carta de mesa cheia gradeando heads-up — o defeito original).
    out = Path(plano.get('saida') or args.out)
    ja = {}
    if out.exists():
        ja = json.loads(out.read_text(encoding='utf-8'))
    antes = sum(len(v) for v in ja.values())
    grava = gravador(out)
    novos = 0

    def ao_coletar(gt, chave, no):
        nonlocal novos
        novos += 1
        grava(gt, chave, no)
        # No coletado vira CONHECIDO na hora, nao so na proxima execucao: blocos diferentes
        # do plano compartilham prefixos (F-F-R2 serve a 3 pares), e sem isto o mesmo no era
        # buscado 3x na MESMA execucao — medido em 15/08, ~6 requisicoes de cota desperdicadas
        # numa leva de 24.
        ja.setdefault(gt, {})[chave] = no

    def pausar():
        time.sleep(args.pausa * random.uniform(0.8, 1.4))

    nosso = args.sem_cdp                       # so fechamos o navegador se fomos nos que abrimos
    if nosso:
        pw, ctx = _contexto(perfil, headless=False, navegador=args.navegador)
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        page.goto(APP)
        fechar = lambda: (ctx.close(), pw.stop())
    else:
        try:
            pw, browser, page = _conecta_cdp(args.cdp)
        except Exception as e:
            print(f'nao consegui conectar no Chrome em localhost:{args.cdp} ({type(e).__name__})')
            print(_instrucoes_cdp(args.cdp, perfil))
            return 2
        fechar = lambda: pw.stop()             # a janela e do usuario; so soltamos a conexao
    if 'login' in page.url or 'accounts.google' in page.url:
        print('a sessao do GW nao esta logada nessa janela — logue nela e rode de novo')
        fechar()
        return 2
    buscar = buscador_navegando(page)

    parada = None
    try:
        seguidas_403 = 0
        for bloco in plano['blocos']:
            gt = bloco.get('gametype', plano.get('gametype'))
            for depth in bloco['depths']:
                if novos >= args.max_nos:
                    parada = f'teto de {args.max_nos} nos atingido'
                    raise LimiteAtingido(parada)
                print(f'\ndepth {depth}')
                try:
                    caminha(buscar, gt, str(depth), bloco['linhas'],
                            ao_coletar=ao_coletar, pausar=pausar,
                            conhecidos=(None if args.refazer else ja.get(gt, {})))
                    seguidas_403 = 0
                except DepthIndisponivel as e:
                    # Depth atras do paywall (ou fora da grade): pula SO esta depth. Mas 403
                    # em serie nao e paywall pontual, e sessao/bloqueio — ai vale a regra de
                    # parar no primeiro sinal.
                    seguidas_403 += 1
                    print(f'  PULEI: {e}')
                    if seguidas_403 >= 3:
                        raise LimiteAtingido(
                            f'3 depths seguidas com 403 — cheiro de bloqueio, nao de paywall ({e})')
    except LimiteAtingido as e:
        parada = str(e)
    except KeyboardInterrupt:
        parada = 'interrompido pelo usuario'
    finally:
        fechar()

    depois = sum(len(v) for v in json.loads(out.read_text(encoding='utf-8')).values()) if out.exists() else 0
    print(f'\n{novos} nos coletados nesta execucao — acervo {antes} -> {depois} ({out})')
    if parada:
        print(f'PAROU: {parada}')
        print('O que veio ate aqui esta gravado. Rode de novo mais tarde para continuar.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
