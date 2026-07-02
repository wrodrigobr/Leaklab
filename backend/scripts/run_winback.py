"""Win-back de inativos: envia o email de reengajamento do estágio devido (7/21/45 dias).

Entrada de CRON. Só dispara de verdade com WINBACK_ENABLED=1 e SMTP configurado no host,
para não sair email por acidente. Use --dry-run para ver a prévia sem enviar.

Uso:
  python -m scripts.run_winback            # respeita WINBACK_ENABLED (cron)
  python -m scripts.run_winback --dry-run  # só prévia, nunca envia
  python -m scripts.run_winback --force    # envia mesmo sem WINBACK_ENABLED (exige SMTP)

Cron sugerido (1x/dia):
  30 13 * * * cd /home/deploy/app && docker compose exec -T web python -m scripts.run_winback >> cron.log 2>&1
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from leaklab.email_digest import run_winback

_dry   = '--dry-run' in sys.argv
_force = '--force' in sys.argv


def _enabled() -> bool:
    return (os.environ.get('WINBACK_ENABLED', '').strip().lower() in ('1', 'true', 'yes', 'on')
            and bool(os.environ.get('SMTP_HOST')))


if __name__ == '__main__':
    if _dry:
        res = run_winback(dry_run=True)
        print(f"[dry-run] candidatos={res['candidates']} elegíveis={len(res.get('preview', []))} "
              f"skipped={res['skipped']}")
        for p in res.get('preview', []):
            print(f"  - {p['username']} <{p['email']}> inativo {p['days']}d → estágio {p['next_stage']}")
        sys.exit(0)
    if not (_enabled() or _force):
        print("Win-back desligado (WINBACK_ENABLED != 1 ou SMTP ausente). Use --dry-run ou --force.")
        sys.exit(0)
    if not os.environ.get('SMTP_HOST'):
        print("SMTP não configurado — abortando envio real.")
        sys.exit(1)
    res = run_winback(dry_run=False)
    print(f"Win-back: candidatos={res['candidates']} enviados={res['sent']} "
          f"skipped={res['skipped']} erros={res['errors']}")
