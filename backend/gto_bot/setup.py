"""
setup.py — Configura o ambiente do bot automaticamente.

Uso:  python backend/gto_bot/setup.py

O que faz:
  1. Lê o LEAKLAB_SECRET do .env do backend
  2. Gera um token admin válido por 365 dias
  3. Cria o arquivo gto_bot/.env com os valores corretos
"""
from __future__ import annotations
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pathlib import Path
from dotenv import load_dotenv

# Carregar o .env do backend
backend_env = Path(__file__).parent.parent / '.env'
if backend_env.exists():
    load_dotenv(backend_env)

SECRET = os.environ.get('LEAKLAB_SECRET', 'dev-secret-inseguro-nao-usar-em-prod')

# Buscar o primeiro usuário admin no banco
from database.schema import get_conn

conn = get_conn()
try:
    row = conn.execute(
        "SELECT id, email FROM users WHERE role = 'admin' ORDER BY id LIMIT 1"
    ).fetchone()
finally:
    conn.close()

if not row:
    print('Nenhum usuário admin encontrado no banco.')
    print('Crie um usuário admin primeiro via API /auth/register')
    sys.exit(1)

user_id, email = row[0], row[1]

import jwt, datetime
payload = {
    'user_id': user_id,
    'email':   email,
    'role':    'admin',
    'exp':     datetime.datetime.now(datetime.UTC) + datetime.timedelta(days=365),
}
token = jwt.encode(payload, SECRET, algorithm='HS256')

# Criar o .env do bot
bot_env = Path(__file__).parent / '.env'
content = f"""# Gerado automaticamente por setup.py
LEAKLAB_URL=http://localhost:5000
LEAKLAB_ADMIN_TOKEN={token}

# GTO Wizard — preencher com suas credenciais
GTW_EMAIL=
GTW_PASSWORD=

# Config
BATCH_SIZE=100
DELAY_MS=800
HEADLESS=false
"""

bot_env.write_text(content, encoding='utf-8')
print(f'✓ {bot_env} criado com token para {email} (válido 365 dias)')
print(f'\nPróximo passo:')
print(f'  1. Edite {bot_env}')
print(f'     Adicione GTW_EMAIL e GTW_PASSWORD')
print(f'  2. Execute: python -m gto_bot discover')
