"""
sender.py — Envia GtoNodes para o backend LeakLabs em lotes.
"""
from __future__ import annotations
import logging
import httpx
from .config import LEAKLAB_URL, LEAKLAB_ADMIN_TOKEN, BATCH_SIZE
from .models import GtoNode

log = logging.getLogger(__name__)

_HEADERS = {
    'Authorization': f'Bearer {LEAKLAB_ADMIN_TOKEN}',
    'Content-Type':  'application/json',
}


def send_batch(nodes: list[GtoNode]) -> int:
    """Envia uma lista de GtoNodes para o backend. Retorna quantos foram aceitos."""
    if not nodes:
        return 0

    total_sent = 0
    for i in range(0, len(nodes), BATCH_SIZE):
        chunk = nodes[i:i + BATCH_SIZE]
        payload = {'nodes': [n.to_dict() for n in chunk]}
        try:
            with httpx.Client(timeout=30.0) as client:
                resp = client.post(
                    f'{LEAKLAB_URL}/admin/gto/nodes',
                    json=payload,
                    headers=_HEADERS,
                )
            if resp.status_code == 200:
                inserted = resp.json().get('inserted', 0)
                total_sent += inserted
                log.info('Batch enviado: %d nós aceitos', inserted)
            else:
                log.warning('Batch rejeitado: HTTP %d — %s', resp.status_code, resp.text[:200])
        except Exception as e:
            log.error('Falha ao enviar batch: %s', e)

    return total_sent


def get_missing_spots(limit: int = 200) -> list[dict]:
    """Busca a lista de spots sem GTO data do backend (para o crawler priorizar)."""
    try:
        with httpx.Client(timeout=30.0) as client:
            resp = client.get(
                f'{LEAKLAB_URL}/admin/gto/missing-spots',
                params={'limit': limit},
                headers=_HEADERS,
            )
        if resp.status_code == 200:
            return resp.json().get('spots', [])
        log.warning('get_missing_spots: HTTP %d', resp.status_code)
        return []
    except Exception as e:
        log.error('get_missing_spots error: %s', e)
        return []


def get_stats() -> dict:
    """Retorna stats da base GTO do backend."""
    try:
        with httpx.Client(timeout=10.0) as client:
            resp = client.get(
                f'{LEAKLAB_URL}/admin/gto/stats',
                headers=_HEADERS,
            )
        return resp.json() if resp.status_code == 200 else {}
    except Exception:
        return {}
