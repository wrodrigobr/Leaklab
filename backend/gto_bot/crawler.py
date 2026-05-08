"""
crawler.py — Bot Playwright para captura passiva e ativa do GTO Wizard.

MODOS:
  passive  — abre o browser, usuário navega manualmente, bot captura em background
  discover — igual ao passivo mas salva todas as chamadas em discovery_log.jsonl
             para identificar o endpoint de solução correto
"""
from __future__ import annotations
import json
import logging
import time
from pathlib import Path
from .config import (
    GTW_BASE_URL, GTW_EMAIL, GTW_PASSWORD,
    HEADLESS, DELAY_MS, DISCOVERY_LOG,
)
from .models import GtoNode
from .parser import is_solution_url, parse_response
from .sender import send_batch

log = logging.getLogger(__name__)

# Buffer de nós capturados antes de enviar ao backend
_NODE_BUFFER: list[GtoNode] = []
_DISCOVERY_ENTRIES: list[dict] = []
_DISCOVERY_MODE = False


def _on_response(response) -> None:
    """Callback chamado pelo Playwright para cada resposta HTTP."""
    global _NODE_BUFFER, _DISCOVERY_ENTRIES

    url = response.url

    # Ignorar assets estáticos
    if any(ext in url for ext in ['.js', '.css', '.png', '.ico', '.woff', '.svg']):
        return

    # Ignorar calls que claramente não são API de solução
    if 'gtowizard' not in url.lower():
        return

    try:
        body = response.json()
    except Exception:
        return

    if _DISCOVERY_MODE:
        # Salvar TODA chamada JSON para análise posterior
        entry = {
            'url':      url,
            'method':   response.request.method,
            'status':   response.status,
            'keys':     list(body.keys())[:15] if isinstance(body, dict) else str(type(body)),
            'preview':  json.dumps(body)[:300],
        }
        _DISCOVERY_ENTRIES.append(entry)
        log.debug('DISCOVERY %s %s → %s', response.request.method, url[:60], entry['keys'])

        # Flush periódico para o arquivo
        if len(_DISCOVERY_ENTRIES) % 10 == 0:
            _flush_discovery()
        return

    # Modo passivo: tentar parsear se URL parece ser solução
    if not is_solution_url(url):
        return

    try:
        req_body = None
        try:
            req_body = json.loads(response.request.post_data or '{}')
        except Exception:
            pass

        nodes = parse_response(url, req_body, body)
        if nodes:
            _NODE_BUFFER.extend(nodes)
            log.info('Capturado: %d nó(s) de %s', len(nodes), url[:60])

            # Flush ao atingir 50 nós
            if len(_NODE_BUFFER) >= 50:
                sent = send_batch(_NODE_BUFFER)
                log.info('Auto-flush: %d nós enviados ao backend', sent)
                _NODE_BUFFER.clear()
    except Exception as e:
        log.debug('Erro ao processar response %s: %s', url[:60], e)


def _flush_discovery() -> None:
    """Salva as entradas de discovery no arquivo JSONL."""
    try:
        with open(DISCOVERY_LOG, 'w', encoding='utf-8') as f:
            for entry in _DISCOVERY_ENTRIES:
                f.write(json.dumps(entry, ensure_ascii=False) + '\n')
    except Exception as e:
        log.error('Erro ao salvar discovery_log: %s', e)


def run_passive(discover: bool = False) -> int:
    """
    Abre o browser, faz login no GTO Wizard e fica capturando em background.
    Usuário navega manualmente pelos spots desejados.

    Args:
        discover: Se True, loga TODAS as chamadas em vez de tentar parsear

    Returns:
        Total de nós enviados ao backend (0 em modo discovery)
    """
    global _DISCOVERY_MODE, _NODE_BUFFER

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print('\n[ERRO] Playwright não instalado.')
        print('Execute: pip install playwright && playwright install chromium')
        return 0

    _DISCOVERY_MODE = discover
    _NODE_BUFFER = []

    print(f'\n{"=" * 60}')
    if discover:
        print('  MODO DISCOVERY — capturando todas as chamadas JSON')
        print(f'  Saída: {DISCOVERY_LOG}')
    else:
        print('  MODO PASSIVO — capturando soluções GTO em background')
    print('  Browser vai abrir. Navegue pelo GTO Wizard normalmente.')
    print('  Pressione Ctrl+C quando terminar.')
    print(f'{"=" * 60}\n')

    total_sent = 0

    with sync_playwright() as pw:
        browser = pw.chromium.launch(
            headless=HEADLESS,
            args=['--no-sandbox'],
        )
        ctx  = browser.new_context(viewport={'width': 1400, 'height': 900})
        page = ctx.new_page()

        # Interceptar respostas
        page.on('response', _on_response)

        # Login automático se credenciais configuradas
        if GTW_EMAIL and GTW_PASSWORD:
            print(f'Fazendo login como {GTW_EMAIL}...')
            try:
                page.goto(f'{GTW_BASE_URL}/login', timeout=15_000)
                page.wait_for_load_state('networkidle', timeout=10_000)

                # Tentar preencher campos de email e senha
                # Seletores comuns — ajustar se necessário
                for selector in ['input[type="email"]', 'input[name="email"]', '#email']:
                    if page.locator(selector).count() > 0:
                        page.fill(selector, GTW_EMAIL)
                        break

                for selector in ['input[type="password"]', 'input[name="password"]', '#password']:
                    if page.locator(selector).count() > 0:
                        page.fill(selector, GTW_PASSWORD)
                        break

                for selector in ['button[type="submit"]', 'button:has-text("Login")',
                                  'button:has-text("Sign in")', 'button:has-text("Entrar")']:
                    if page.locator(selector).count() > 0:
                        page.click(selector)
                        break

                page.wait_for_load_state('networkidle', timeout=10_000)
                print('Login concluído.\n')
            except Exception as e:
                log.warning('Login automático falhou: %s — continue manualmente', e)
                page.goto(GTW_BASE_URL, timeout=15_000)
        else:
            print('Credenciais não configuradas — faça login manualmente no browser.')
            page.goto(GTW_BASE_URL, timeout=15_000)

        print('Browser pronto. Navegue pelo GTO Wizard...')
        print('(Ctrl+C para encerrar e enviar os nós capturados)\n')

        try:
            # Manter o browser aberto até o usuário encerrar
            while True:
                time.sleep(2)
                if _NODE_BUFFER and not discover:
                    print(f'  Buffer: {len(_NODE_BUFFER)} nós prontos para envio...')
        except KeyboardInterrupt:
            print('\nEncerrando...')

        # Flush final
        if discover:
            _flush_discovery()
            total = len(_DISCOVERY_ENTRIES)
            print(f'\n{total} chamadas salvas em: {DISCOVERY_LOG}')
            print('Execute: python -m gto_bot analyze-discovery  para ver o resumo')
        else:
            if _NODE_BUFFER:
                sent = send_batch(_NODE_BUFFER)
                total_sent += sent
                print(f'{sent} nós enviados ao backend.')
            print(f'\nTotal da sessão: {total_sent} nós enviados.')

        browser.close()

    return total_sent
