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


# ── tokens ────────────────────────────────────────────────────────────────────────────────────

def token_da_acao(acao: dict, stack: float) -> str | None:
    """Nome do no filho para uma acao, no dialeto do `preflop_actions` do GW.

    Regra lida dos 36 nos ja capturados: CALL -> 'C'; raise de tamanho ~stack -> 'RAI';
    demais raises -> 'R' + betsize como o GW escreve ('R2', 'R4.5'). FOLD encerra a mao.
    """
    tipo = (acao.get('type') or '').upper()
    if tipo == 'FOLD':
        return None
    if tipo in ('CALL', 'CHECK'):
        return 'C'
    bs = acao.get('betsize')
    if bs in (None, '', 0):
        return None
    valor = float(bs)
    if valor >= float(stack) - 0.5:          # all-in: 'RAISE 12.500' num spot de 12,625
        return 'RAI'
    txt = str(bs).rstrip('0').rstrip('.') if '.' in str(bs) else str(bs)
    return f'R{txt}'


def escolhe_acao(desejo: str, acoes: list[dict], stack: float) -> dict | None:
    """Resolve a INTENCAO do plano contra as acoes que o no realmente oferece."""
    raises = [a for a in acoes if (a.get('type') or '').upper() == 'RAISE' and a.get('betsize')]
    allin = [a for a in raises if float(a['betsize']) >= float(stack) - 0.5]
    normais = sorted((a for a in raises if a not in allin), key=lambda a: float(a['betsize']))
    if desejo == 'allin':
        return allin[0] if allin else None
    if desejo == 'raise_min':
        return normais[0] if normais else None
    if desejo == 'raise_max':
        return normais[-1] if normais else None
    if desejo in ('call', 'limp', 'check'):
        return next((a for a in acoes
                     if (a.get('type') or '').upper() in ('CALL', 'CHECK')), None)
    raise ValueError(f'desejo desconhecido no plano: {desejo!r}')


# ── caminhada ─────────────────────────────────────────────────────────────────────────────────

def caminha(buscar, gametype: str, depth: str, linhas: list[list[str]],
            ao_coletar=None, pausar=None) -> dict:
    """Percorre as `linhas` de UMA profundidade. `buscar(params) -> (status, corpo)`.

    Prefixos sao memoizados: `[raise_min]` e `[raise_min, allin]` compartilham ROOT e R2 e
    gastam UMA requisicao cada, nao duas. Cota economizada e cota que sobra para no novo.
    """
    stack = float(depth)
    cache: dict[str, dict] = {}
    coletados: dict[str, dict] = {}

    def obter(no_str: str) -> dict:
        if no_str in cache:
            return cache[no_str]
        if pausar and cache:
            pausar()
        params = {'gametype': gametype, 'depth': depth, 'stacks': '',
                  'preflop_actions': no_str, 'flop_actions': '', 'turn_actions': '',
                  'river_actions': '', 'board': ''}
        status, corpo = buscar(params)
        if status != 200:
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


def buscador_playwright(page):
    """Faz a requisicao DE DENTRO da pagina logada — mesma origem, mesma sessao, sem token."""
    def buscar(params: dict):
        r = page.evaluate(
            """async ({api, params}) => {
                 const u = new URL(api);
                 Object.entries(params).forEach(([k, v]) => u.searchParams.set(k, v));
                 const resp = await fetch(u.toString(), {credentials: 'include'});
                 let body = null;
                 try { body = await resp.json(); } catch (e) {}
                 return {status: resp.status, body};
               }""",
            {'api': API, 'params': params})
        return r['status'], r['body']
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
                    help='Chrome instalado (default), Edge, ou o Chromium empacotado')
    args = ap.parse_args()

    perfil = Path(args.perfil).resolve()
    perfil.mkdir(parents=True, exist_ok=True)

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
    out = Path(args.out)
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

    def pausar():
        time.sleep(args.pausa * random.uniform(0.8, 1.4))

    pw, ctx = _contexto(perfil, headless=False, navegador=args.navegador)
    page = ctx.pages[0] if ctx.pages else ctx.new_page()
    page.goto(APP)
    if 'login' in page.url:
        print('sessao expirada — rode com --login primeiro')
        ctx.close(); pw.stop()
        return 2
    buscar = buscador_playwright(page)

    parada = None
    try:
        for bloco in plano['blocos']:
            gt = bloco.get('gametype', plano.get('gametype'))
            for depth in bloco['depths']:
                if novos >= args.max_nos:
                    parada = f'teto de {args.max_nos} nos atingido'
                    raise LimiteAtingido(parada)
                print(f'\ndepth {depth}')
                caminha(buscar, gt, str(depth), bloco['linhas'],
                        ao_coletar=ao_coletar, pausar=pausar)
    except LimiteAtingido as e:
        parada = str(e)
    except KeyboardInterrupt:
        parada = 'interrompido pelo usuario'
    finally:
        ctx.close(); pw.stop()

    depois = sum(len(v) for v in json.loads(out.read_text(encoding='utf-8')).values()) if out.exists() else 0
    print(f'\n{novos} nos coletados nesta execucao — acervo {antes} -> {depois} ({out})')
    if parada:
        print(f'PAROU: {parada}')
        print('O que veio ate aqui esta gravado. Rode de novo mais tarde para continuar.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
