"""Configuração do bot via variáveis de ambiente."""
from __future__ import annotations
import os
from pathlib import Path

# Carrega .env na raiz do gto_bot (ou do backend)
_here = Path(__file__).parent
for _candidate in [_here / '.env', _here.parent / '.env']:
    if _candidate.exists():
        from dotenv import load_dotenv
        load_dotenv(_candidate)
        break

LEAKLAB_URL         = os.environ.get('LEAKLAB_URL', 'http://localhost:5000')
LEAKLAB_ADMIN_TOKEN = os.environ.get('LEAKLAB_ADMIN_TOKEN', '')

GTW_EMAIL    = os.environ.get('GTW_EMAIL', '')
GTW_PASSWORD = os.environ.get('GTW_PASSWORD', '')
GTW_BASE_URL = 'https://app.gtowizard.com'

BATCH_SIZE = int(os.environ.get('BATCH_SIZE', '100'))
DELAY_MS   = int(os.environ.get('DELAY_MS',   '800'))
HEADLESS   = os.environ.get('HEADLESS', 'false').lower() == 'true'

# Arquivo onde o modo discovery salva as chamadas capturadas
DISCOVERY_LOG = str(_here / 'discovery_log.jsonl')


def validate():
    errors = []
    if not LEAKLAB_ADMIN_TOKEN:
        errors.append('LEAKLAB_ADMIN_TOKEN não configurado')
    if not GTW_EMAIL or not GTW_PASSWORD:
        errors.append('GTW_EMAIL / GTW_PASSWORD não configurados')
    return errors
