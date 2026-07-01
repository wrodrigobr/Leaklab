"""Backfill de tournaments.site a partir do raw_text (re-detecção pelo parser). Corrige torneios
gravados com site errado — notavelmente os ACR que caíam em 'unknown' por causa de um _detect_site
duplicado no app.py sem o branch ACR (fonte única agora no parser). READ-ONLY exceto a coluna site.

Uso: python -m scripts.backfill_site_from_raw
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from database.schema import get_conn, USE_POSTGRES
from leaklab.parser import _detect_site

conn = get_conn()
if not USE_POSTGRES:                     # PRAGMA é SQLite-only; em Postgres aborta a transação
    try:
        conn.execute('PRAGMA busy_timeout=30000')
    except Exception:
        pass

rows = conn.execute("SELECT id, site, raw_text FROM tournaments WHERE raw_text IS NOT NULL").fetchall()
print(f"Verificando {len(rows)} torneios...")
checked = updated = 0
by_site = {}
for r in rows:
    raw = r['raw_text']
    if not raw:
        continue
    checked += 1
    detected = _detect_site(raw)
    if detected and detected != 'unknown' and detected != (r['site'] or ''):
        conn.execute("UPDATE tournaments SET site = ? WHERE id = ?", (detected, r['id']))
        updated += 1
        by_site[detected] = by_site.get(detected, 0) + 1
conn.commit()
conn.close()
print(f"Concluido. Verificados: {checked} | Atualizados: {updated} | por site: {by_site}")
