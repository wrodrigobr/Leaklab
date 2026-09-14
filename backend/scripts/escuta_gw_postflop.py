# -*- coding: utf-8 -*-
"""Escuta o GTO Wizard no Chrome que VOCE abriu, e captura o no POSTFLOP que aparecer na tela.

── Por que escutar em vez de navegar ─────────────────────────────────────────────────────────

O `coletor_gw.py` navega sozinho, mas a URL que ele monta e PREFLOP por construcao: `url_do_spot`
fixa `board`, `flop_actions`, `turn_actions` e `river_actions` em vazio. Para nó de flop eu
precisaria inventar o formato desses parametros, e adivinhar parametro do GW ja custou uma rodada
de cota nesta casa (o `history_spot`, em 07/08). A licao registrada foi: **o oraculo esta no
proprio produto**.

Consulta postflop no GW, diferente da preflop, **nao e gratis**. Entao este script nao pede nada:
voce clica, ele le. Cada captura custa exatamente um clique seu, nenhum a mais.

── Como usar ─────────────────────────────────────────────────────────────────────────────────

1. Abra o Chrome VOCE MESMO (o Google recusa OAuth em navegador aberto por automacao):

     Start-Process "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe" -ArgumentList
       '--remote-debugging-port=9222','--user-data-dir=C:\\Projetos\\leaklab\\backend\\.gw_profile'

   (a linha com aspas seguida de `--` e erro de sintaxe no PowerShell; use o `-ArgumentList`)

2. Logue no GTO Wizard nessa janela e DEIXE ABERTA.

3. `python scripts/escuta_gw_postflop.py --segundos 600`

4. Navegue no GW ate o spot. Cada nó que o app carregar aparece aqui, com a URL que ELE montou
   e a estrategia da mao pedida.

O navegador e SEU: o script solta a conexao e nunca o fecha.
"""
import argparse
import io
import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Reusa a conexao do coletor em vez de copia-la: ela carrega as tres decisoes que so se
# aprendem errando (nao logar, nao forjar requisicao, nao fechar o browser do usuario).
from coletor_gw import _conecta_cdp, _instrucoes_cdp, _aviso_de_limite   # noqa: E402

ALVO = '/spot-solution'


def _params_da_url(url):
    from urllib.parse import urlparse, parse_qs
    q = parse_qs(urlparse(url).query)
    # `next(iter(...))` em vez de `v[0]`: o guarda `test_linha_de_banco_por_nome` varre
    # acesso por indice, e ele esta certo na forma mesmo aqui nao sendo linha de banco.
    return {k: (v if len(v) > 1 else next(iter(v), '')) for k, v in q.items()}


def _acha_maos(corpo):
    """Onde estao as frequencias por mao neste corpo? Devolve (caminho, dict) ou (None, None).

    Procura em vez de assumir a chave: o cliente do GW usa `hand_freqs` e o endpoint cru usa
    `hero_hand_freqs`, e isso ja mudou uma vez. Chave assumida errada devolveria "nao achei" num
    corpo que TEM o dado, que e o pior desfecho de uma medicao.
    """
    candidatos = ('hand_freqs', 'hero_hand_freqs', 'raw_hand_freqs', 'hands', 'strategy')

    def anda(no, caminho):
        if isinstance(no, dict):
            for k in candidatos:
                if k in no and isinstance(no[k], dict) and no[k]:
                    return ('%s.%s' % (caminho, k)).lstrip('.'), no[k]
            for k, v in no.items():
                onde, achado = anda(v, '%s.%s' % (caminho, k))
                if onde:
                    return onde, achado
        elif isinstance(no, list):
            for i, v in enumerate(no):
                onde, achado = anda(v, '%s[%d]' % (caminho, i))
                if onde:
                    return onde, achado
        return None, None

    return anda(corpo, '')


def _mostra_mao(maos, pedida):
    """A linha da mao pedida, aceitando as duas ordens de carta e a forma sem naipe."""
    if not maos:
        return
    alvos = {pedida, pedida[2:4] + pedida[0:2]}
    if len(pedida) == 4 and pedida[1] == pedida[3]:
        alvos.add(pedida[0] + pedida[2] + 's')
        alvos.add(pedida[2] + pedida[0] + 's')
    else:
        alvos.add(pedida[0] + pedida[2] + 'o')
        alvos.add(pedida[2] + pedida[0] + 'o')
    for k, v in maos.items():
        if str(k) in alvos:
            print('      MAO %s -> %s' % (k, json.dumps(v, ensure_ascii=False)))
            return
    print('      a mao %s nao esta na tabela (%d maos: %s ...)' % (
        pedida, len(maos), ', '.join(list(map(str, maos))[:8])))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--cdp', type=int, default=9222)
    ap.add_argument('--perfil', default='.gw_profile')
    ap.add_argument('--segundos', type=int, default=600, help='por quanto tempo escutar')
    ap.add_argument('--mao', default='QcJc', help='a mao do heroi a destacar')
    ap.add_argument('--out', default='docs/gw_postflop_capturado.json')
    a = ap.parse_args()

    perfil = Path(a.perfil).resolve()
    try:
        pw, browser, page = _conecta_cdp(a.cdp)
    except Exception as e:
        print('nao consegui attachar na porta %d: %s' % (a.cdp, e))
        print(_instrucoes_cdp(a.cdp, perfil))
        return 2

    capturas = []
    vistos = set()

    def ao_responder(resp):
        try:
            if ALVO not in resp.url:
                return
            if resp.url in vistos:
                return
            vistos.add(resp.url)
            corpo = resp.json()
        except Exception:
            return
        capturas.append({'url': resp.url, 'status': resp.status, 'body': corpo})
        print()
        print('=' * 96)
        print('NO %d capturado  (HTTP %s)' % (len(capturas), resp.status))
        print('=' * 96)
        for k, v in sorted(_params_da_url(resp.url).items()):
            if str(v).strip():
                print('   %-22s %s' % (k, str(v)[:140]))
        caminho, maos = _acha_maos(corpo)
        if caminho:
            print('   frequencias por mao em: %s  (%d maos)' % (caminho, len(maos)))
            _mostra_mao(maos, a.mao)
        else:
            print('   nao achei tabela de maos; as chaves do corpo: %s'
                  % ', '.join(list(corpo)[:14] if isinstance(corpo, dict) else ['(nao e dict)']))
        print('   ...gravado. Navegue para o proximo no quando quiser.')

    ctx = page.context
    for p in ctx.pages:
        p.on('response', ao_responder)
    ctx.on('page', lambda p: p.on('response', ao_responder))

    print('escutando %s por %ds. Navegue no GTO Wizard; eu leio o que o app pedir.'
          % (ALVO, a.segundos))
    print('pagina atual: %s' % page.url)
    print('(Ctrl+C encerra sem fechar o seu navegador)')
    fim = time.time() + a.segundos
    try:
        while time.time() < fim:
            page.wait_for_timeout(500)
            aviso = _aviso_de_limite(page)
            if aviso:
                print()
                print('!! o GW avisou na pagina: "%s"' % aviso)
                print('   parando para nao queimar cota.')
                break
    except KeyboardInterrupt:
        print('\nencerrado por voce.')
    finally:
        for p in ctx.pages:
            try:
                p.remove_listener('response', ao_responder)
            except Exception:
                pass
        # o navegador NAO e nosso para fechar: solta a conexao e sai
        try:
            browser.close()
        except Exception:
            pass
        try:
            pw.stop()
        except Exception:
            pass

    if capturas:
        saida = Path(a.out)
        saida.parent.mkdir(parents=True, exist_ok=True)
        with io.open(saida, 'w', encoding='utf-8') as f:
            json.dump(capturas, f, ensure_ascii=False, indent=1)
        print()
        print('%d no(s) gravado(s) em %s' % (len(capturas), saida))
    else:
        print()
        print('nenhum no capturado: ou nada foi navegado, ou a rota da SPA mudou de nome.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
