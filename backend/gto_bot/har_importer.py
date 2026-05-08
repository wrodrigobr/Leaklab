"""
har_importer.py — Importa nós GTO a partir de um arquivo HAR exportado do browser.

COMO USAR:
1. Abra o GTO Wizard no Chrome/Firefox
2. Abra DevTools → aba Network
3. Navegue pelos spots que quer coletar
4. Clique com botão direito na lista de requests → "Save all as HAR"
5. Execute:  python -m gto_bot har caminho/para/arquivo.har
"""
from __future__ import annotations
import json
import logging
from pathlib import Path
from typing import Iterator
from .models import GtoNode
from .parser import is_solution_url, parse_response
from .sender import send_batch

log = logging.getLogger(__name__)


def _iter_har_entries(har_path: str) -> Iterator[dict]:
    """Itera sobre as entradas do HAR que correspondem a endpoints GTO."""
    with open(har_path, encoding='utf-8') as f:
        har = json.load(f)

    entries = har.get('log', {}).get('entries', [])
    log.info('HAR: %d entradas totais', len(entries))

    for entry in entries:
        req  = entry.get('request', {})
        resp = entry.get('response', {})
        url  = req.get('url', '')

        if not is_solution_url(url):
            continue
        if resp.get('status', 0) != 200:
            continue

        content = resp.get('content', {})
        mime    = content.get('mimeType', '')
        if 'json' not in mime:
            continue

        body_text = content.get('text', '')
        if not body_text:
            continue

        try:
            body = json.loads(body_text)
        except json.JSONDecodeError:
            continue

        # request body (POST)
        req_body = None
        post_data = req.get('postData', {})
        if post_data:
            try:
                req_body = json.loads(post_data.get('text', '{}'))
            except Exception:
                pass

        yield {'url': url, 'request': req_body, 'response': body}


def import_har(har_path: str, dry_run: bool = False) -> int:
    """
    Processa um arquivo HAR e envia os nós encontrados ao backend.

    Args:
        har_path: Caminho para o arquivo .har
        dry_run:  Se True, apenas mostra o que seria enviado sem enviar

    Returns:
        Número de nós enviados com sucesso
    """
    path = Path(har_path)
    if not path.exists():
        log.error('Arquivo não encontrado: %s', har_path)
        return 0

    log.info('Processando HAR: %s', path.name)
    nodes: list[GtoNode] = []
    entries_processed = 0

    for entry in _iter_har_entries(har_path):
        entries_processed += 1
        parsed = parse_response(entry['url'], entry['request'], entry['response'])
        if parsed:
            nodes.extend(parsed)
            log.debug('  ✓ %d nó(s) de %s', len(parsed), entry['url'][:80])
        else:
            log.debug('  ✗ sem parse em %s', entry['url'][:80])

    log.info('HAR processado: %d entradas relevantes, %d nós parseados',
             entries_processed, len(nodes))

    if not nodes:
        print('Nenhum nó GTO encontrado no HAR.')
        print('Sugestão: rode "python -m gto_bot discover" para identificar o endpoint correto.')
        return 0

    if dry_run:
        print(f'[DRY RUN] {len(nodes)} nós encontrados — não enviados')
        for n in nodes[:5]:
            print(f'  {n.street} {n.position} {n.gto_action} {n.gto_freq:.0%}')
        return len(nodes)

    sent = send_batch(nodes)
    print(f'{sent} nós enviados ao LeakLabs com sucesso.')
    return sent


def discover_har(har_path: str) -> None:
    """
    Modo descoberta: lista todas as chamadas JSON do HAR para identificar
    o endpoint de solução correto.
    """
    with open(har_path, encoding='utf-8') as f:
        har = json.load(f)

    entries = har.get('log', {}).get('entries', [])
    json_entries = []

    for entry in entries:
        req  = entry.get('request', {})
        resp = entry.get('response', {})
        url  = req.get('url', '')
        mime = resp.get('content', {}).get('mimeType', '')
        status = resp.get('status', 0)

        if 'json' not in mime or status != 200:
            continue
        if 'gtowizard' not in url.lower():
            continue

        body_text = resp.get('content', {}).get('text', '')
        try:
            body = json.loads(body_text) if body_text else {}
        except Exception:
            body = {}

        json_entries.append({
            'url':    url,
            'method': req.get('method', 'GET'),
            'keys':   list(body.keys())[:10] if isinstance(body, dict) else type(body).__name__,
        })

    print(f'\nChamadas JSON do GTO Wizard encontradas no HAR ({len(json_entries)} total):\n')
    for e in json_entries:
        print(f'  {e["method"]:<5} {e["url"][:80]}')
        print(f'         keys: {e["keys"]}')
        print()

    if not json_entries:
        print('Nenhuma chamada JSON do GTO Wizard encontrada.')
        print('Verifique se o HAR foi capturado durante uma sessão ativa no GTO Wizard.')
