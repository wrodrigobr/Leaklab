"""
email_digest.py — Digest semanal para jogadores inscritos.

Estratégia:
  - Zero LLM — conteúdo 100% determinístico baseado nos dados reais
  - SMTP via smtplib nativo (sem dependências extras)
  - Fallback gracioso: se SMTP não configurado, loga e retorna False
  - Unsubscribe via token HMAC seguro no link de rodapé

Variáveis de ambiente requeridas:
  SMTP_HOST        — ex: smtp.sendgrid.net
  SMTP_PORT        — ex: 587 (default)
  SMTP_USER        — ex: apikey (SendGrid) ou endereço SMTP
  SMTP_PASSWORD    — senha SMTP / API key
  DIGEST_FROM      — ex: noreply@leaklabs.ai
  APP_BASE_URL     — ex: https://leaklabs.ai (para links de unsubscribe)
  LEAKLAB_SECRET   — usado para assinar token de unsubscribe
"""
from __future__ import annotations
import hashlib
import hmac
import logging
import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Optional

log = logging.getLogger(__name__)

_UNSUBSCRIBE_SALT = "digest_unsub_v1"


# ── Token de unsubscribe ──────────────────────────────────────────────────────

def _unsub_token(user_id: int) -> str:
    secret = os.environ.get("LEAKLAB_SECRET", "dev-secret")
    msg = f"{_UNSUBSCRIBE_SALT}:{user_id}"
    return hmac.new(secret.encode(), msg.encode(), hashlib.sha256).hexdigest()[:32]


def verify_unsub_token(user_id: int, token: str) -> bool:
    return hmac.compare_digest(_unsub_token(user_id), token)


# ── Token de unsubscribe dos comunicados do admin (salt distinto do digest) ───

_EMAIL_UNSUB_SALT = "admin_email_unsub_v1"


def _email_unsub_token(user_id: int) -> str:
    secret = os.environ.get("LEAKLAB_SECRET", "dev-secret")
    msg = f"{_EMAIL_UNSUB_SALT}:{user_id}"
    return hmac.new(secret.encode(), msg.encode(), hashlib.sha256).hexdigest()[:32]


def verify_email_unsub_token(user_id: int, token: str) -> bool:
    return hmac.compare_digest(_email_unsub_token(user_id), token)


# ── Geração do conteúdo ───────────────────────────────────────────────────────

def _ev_bar(ev_loss: float) -> str:
    """Barra visual de EV loss: ████░░░░ (máx 8 chars, proporcional a 0–200bb)."""
    pct = min(1.0, abs(ev_loss) / 200.0)
    filled = round(pct * 8)
    return "█" * filled + "░" * (8 - filled)


def build_digest_data(user_id: int) -> Optional[dict]:
    """Monta o conjunto de dados para o digest. Retorna None se sem dados."""
    try:
        from database.repositories import (
            get_evolution_metrics, get_leak_ranking_gto_first,
            get_drill_spots, get_drill_stats,
        )
        evo = get_evolution_metrics(user_id, days=7)
        # Leak digest GTO-first: prefere ranking baseado em gto_label (critical/minor),
        # fallback heuristico apenas se sem cobertura GTO. Alinhado com /player/leak-roi.
        leak_data = get_leak_ranking_gto_first(user_id, days=30)
        leaks = leak_data['leaks']
        leak_source = leak_data['source']
        spots = get_drill_spots(user_id)
        stats = get_drill_stats(user_id)
    except Exception as e:
        log.warning("digest data error for user %s: %s", user_id, e)
        return None

    tournaments_week = len(evo.get("evolution", []))
    if tournaments_week == 0 and not leaks:
        return None  # sem dados relevantes — não enviar

    # Standard% da última semana
    last_std = None
    evo_list = evo.get("evolution", [])
    if evo_list:
        last_std = evo_list[-1].get("standard_pct")

    # Top leak por EV loss
    top_leak = None
    total_ev_loss = 0.0
    if leaks:
        top_leak = leaks[0]
        total_ev_loss = sum(abs(l.get("ev_loss_bb", 0) or 0) for l in leaks)

    # Drill mais atrasado
    overdue_spot = None
    overdue_spots = [s for s in spots if (s.get("days_overdue") or 0) > 0]
    if overdue_spots:
        overdue_spot = max(overdue_spots, key=lambda s: s.get("days_overdue", 0))

    drill_accuracy = stats.get("accuracy_pct") if stats else None

    return {
        "tournaments_week": tournaments_week,
        "last_std":         last_std,
        "top_leak":         top_leak,
        "total_ev_loss":    total_ev_loss,
        "overdue_spot":     overdue_spot,
        "overdue_count":    len(overdue_spots),
        "drill_accuracy":   drill_accuracy,
        "leak_source":      leak_source,
    }


def build_digest_html(username: str, data: dict, unsub_link: str) -> str:
    std_pct = data["last_std"]
    std_line = f"{std_pct:.1f}% standard" if std_pct is not None else "Dados insuficientes"

    n_t = data["tournaments_week"]
    s_t = "s" if n_t != 1 else ""
    tourney_line = (
        f'<p style="margin:4px 0 0 0;font-size:12px;color:#6b7280;">'
        f'{n_t} torneio{s_t} analisado{s_t} esta semana</p>'
        if n_t > 0 else ""
    )

    top_leak = data["top_leak"]
    leak_block = ""
    if top_leak:
        spot  = (top_leak.get("spot") or "").replace("_", " ")
        ev    = abs(top_leak.get("ev_loss_bb", 0) or 0)
        bar   = _ev_bar(ev)
        leak_block = f"""
      <tr>
        <td style="padding:16px 24px;border-bottom:1px solid #1e2433;">
          <p style="margin:0 0 4px 0;font-size:11px;text-transform:uppercase;letter-spacing:.08em;color:#6b7280;">
            🔴 Maior leak da semana
          </p>
          <p style="margin:0 0 8px 0;font-size:16px;font-weight:600;color:#f1f5f9;">{spot}</p>
          <p style="margin:0;font-family:monospace;font-size:13px;color:#ef4444;">
            {bar} {ev:.1f} bb de EV perdido
          </p>
        </td>
      </tr>"""

    drill_block = ""
    if data["overdue_spot"]:
        spot_name = (data["overdue_spot"].get("leak_spot") or "").replace("_", " ")
        days_late  = data["overdue_spot"].get("days_overdue", 0)
        drill_block = f"""
      <tr>
        <td style="padding:16px 24px;border-bottom:1px solid #1e2433;">
          <p style="margin:0 0 4px 0;font-size:11px;text-transform:uppercase;letter-spacing:.08em;color:#6b7280;">
            🕐 Drill atrasado
          </p>
          <p style="margin:0 0 4px 0;font-size:15px;font-weight:600;color:#f1f5f9;">{spot_name}</p>
          <p style="margin:0;font-size:12px;color:#f59e0b;">{days_late} dia{"s" if days_late != 1 else ""} de atraso — {data["overdue_count"]} spot{"s" if data["overdue_count"] != 1 else ""} pendente{"s" if data["overdue_count"] != 1 else ""}</p>
        </td>
      </tr>"""

    acc_block = ""
    if data["drill_accuracy"] is not None:
        acc = data["drill_accuracy"]
        color = "#22c55e" if acc >= 70 else "#f59e0b" if acc >= 50 else "#ef4444"
        acc_block = f"""
      <tr>
        <td style="padding:16px 24px;border-bottom:1px solid #1e2433;">
          <p style="margin:0 0 4px 0;font-size:11px;text-transform:uppercase;letter-spacing:.08em;color:#6b7280;">
            🎯 Precisão nos drills
          </p>
          <p style="margin:0;font-size:22px;font-weight:700;color:{color};">{acc:.0f}%</p>
        </td>
      </tr>"""

    return f"""<!DOCTYPE html>
<html lang="pt-BR">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>Seu resumo semanal — LeakLabs.ai</title></head>
<body style="margin:0;padding:0;background:#0f1117;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;">
  <table width="100%" cellpadding="0" cellspacing="0" style="background:#0f1117;padding:40px 16px;">
    <tr><td align="center">
      <table width="560" cellpadding="0" cellspacing="0" style="background:#161b27;border-radius:12px;overflow:hidden;border:1px solid #1e2433;">

        <!-- Header -->
        <tr>
          <td style="padding:24px;background:#1a1f2e;border-bottom:1px solid #1e2433;">
            <p style="margin:0;font-size:10px;font-family:monospace;text-transform:uppercase;letter-spacing:.12em;color:#6366f1;">LeakLabs.ai</p>
            <h1 style="margin:6px 0 0 0;font-size:20px;font-weight:700;color:#f1f5f9;">Resumo da semana, {username}</h1>
          </td>
        </tr>

        <!-- Standard% -->
        <tr>
          <td style="padding:20px 24px;border-bottom:1px solid #1e2433;">
            <p style="margin:0 0 4px 0;font-size:11px;text-transform:uppercase;letter-spacing:.08em;color:#6b7280;">Qualidade de decisão (7 dias)</p>
            <p style="margin:0;font-size:26px;font-weight:700;color:#6366f1;">{std_line}</p>
            {tourney_line}
          </td>
        </tr>

        {leak_block}
        {drill_block}
        {acc_block}

        <!-- CTA -->
        <tr>
          <td style="padding:24px;text-align:center;">
            <a href="https://leaklabs.ai/dashboard"
               style="display:inline-block;background:#6366f1;color:#fff;text-decoration:none;padding:12px 28px;border-radius:8px;font-size:13px;font-weight:600;">
              Abrir LeakLabs
            </a>
          </td>
        </tr>

        <!-- Footer -->
        <tr>
          <td style="padding:16px 24px;border-top:1px solid #1e2433;text-align:center;">
            <p style="margin:0;font-size:11px;color:#6b7280;">
              Você recebe este email porque ativou o digest semanal.<br>
              <a href="{unsub_link}" style="color:#6b7280;text-decoration:underline;">Cancelar inscrição</a>
            </p>
          </td>
        </tr>

      </table>
    </td></tr>
  </table>
</body>
</html>"""


# ── Envio SMTP ────────────────────────────────────────────────────────────────

def send_digest_email(to_email: str, username: str, data: dict, user_id: int) -> bool:
    """Envia o digest para um usuário. Retorna True se enviado com sucesso."""
    smtp_host = os.environ.get("SMTP_HOST", "")
    smtp_port = int(os.environ.get("SMTP_PORT", "587"))
    smtp_user = os.environ.get("SMTP_USER", "")
    smtp_pass = os.environ.get("SMTP_PASSWORD", "")
    from_addr = os.environ.get("DIGEST_FROM", "noreply@leaklabs.ai")
    base_url  = os.environ.get("APP_BASE_URL", "https://leaklabs.ai")

    if not smtp_host or not smtp_user or not smtp_pass:
        log.warning("SMTP não configurado — digest não enviado para %s", to_email)
        return False

    token     = _unsub_token(user_id)
    unsub_url = f"{base_url}/api/player/digest/unsubscribe?uid={user_id}&token={token}"
    html_body = build_digest_html(username, data, unsub_url)

    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"📊 Seu resumo semanal — LeakLabs.ai"
    msg["From"]    = from_addr
    msg["To"]      = to_email
    msg.attach(MIMEText(html_body, "html", "utf-8"))

    try:
        with smtplib.SMTP(smtp_host, smtp_port, timeout=15) as server:
            server.ehlo()
            server.starttls()
            server.login(smtp_user, smtp_pass)
            server.sendmail(from_addr, [to_email], msg.as_string())
        log.info("Digest enviado para %s (user %s)", to_email, user_id)
        return True
    except Exception as e:
        log.error("Erro ao enviar digest para %s: %s", to_email, e)
        return False


# ── Email transacional (aprovação/rejeição de coach) ─────────────────────────

def send_transactional_email(to_email: str, subject: str, html_body: str) -> bool:
    """Envia email transacional simples (sem unsubscribe). Retorna True se enviado."""
    smtp_host = os.environ.get("SMTP_HOST", "")
    smtp_port = int(os.environ.get("SMTP_PORT", "587"))
    smtp_user = os.environ.get("SMTP_USER", "")
    smtp_pass = os.environ.get("SMTP_PASSWORD", "")
    from_addr = os.environ.get("DIGEST_FROM", "noreply@leaklabs.ai")

    if not smtp_host or not smtp_user or not smtp_pass:
        log.warning("SMTP não configurado — email transacional não enviado para %s", to_email)
        return False

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"]    = from_addr
    msg["To"]      = to_email
    msg.attach(MIMEText(html_body, "html", "utf-8"))

    try:
        with smtplib.SMTP(smtp_host, smtp_port, timeout=15) as server:
            server.ehlo()
            server.starttls()
            server.login(smtp_user, smtp_pass)
            server.sendmail(from_addr, [to_email], msg.as_string())
        log.info("Email transacional enviado para %s", to_email)
        return True
    except Exception as e:
        log.error("Erro ao enviar email transacional para %s: %s", to_email, e)
        return False


# ── Email de comunicado do admin (espelha a mensagem in-app) ─────────────────

_CATEGORY_META = {
    "info":     ("📣", "#6366f1", "Informação"),
    "aviso":    ("⚠️", "#f59e0b", "Aviso"),
    "novidade": ("🎉", "#22c55e", "Novidade"),
}


def build_admin_email_html(username: str, title: str, body: str,
                           unsub_link: str, category: str = "info") -> str:
    """HTML do email de comunicado do admin — mesmo visual do digest, com rodapé
    de descadastro (LGPD). `body` pode ter quebras de linha (viram <br>)."""
    emoji, color, cat_label = _CATEGORY_META.get(category, _CATEGORY_META["info"])
    safe_title = (title or "").strip() or "Comunicado — LeakLabs.ai"
    body_html = (body or "").strip().replace("\n", "<br>")
    return f"""<!DOCTYPE html>
<html lang="pt-BR">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>{safe_title}</title></head>
<body style="margin:0;padding:0;background:#0f1117;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;">
  <table width="100%" cellpadding="0" cellspacing="0" style="background:#0f1117;padding:40px 16px;">
    <tr><td align="center">
      <table width="560" cellpadding="0" cellspacing="0" style="background:#161b27;border-radius:12px;overflow:hidden;border:1px solid #1e2433;">
        <tr>
          <td style="padding:24px;background:#1a1f2e;border-bottom:1px solid #1e2433;">
            <p style="margin:0;font-size:10px;font-family:monospace;text-transform:uppercase;letter-spacing:.12em;color:{color};">{emoji} {cat_label}</p>
            <h1 style="margin:6px 0 0 0;font-size:20px;font-weight:700;color:#f1f5f9;">{safe_title}</h1>
          </td>
        </tr>
        <tr>
          <td style="padding:24px;">
            <p style="margin:0 0 16px 0;font-size:14px;color:#cbd5e1;">Olá, {username}.</p>
            <p style="margin:0;font-size:15px;line-height:1.6;color:#e2e8f0;">{body_html}</p>
          </td>
        </tr>
        <tr>
          <td style="padding:0 24px 24px;text-align:center;">
            <a href="https://leaklabs.ai/dashboard"
               style="display:inline-block;background:{color};color:#fff;text-decoration:none;padding:12px 28px;border-radius:8px;font-size:13px;font-weight:600;">
              Abrir LeakLabs
            </a>
          </td>
        </tr>
        <tr>
          <td style="padding:16px 24px;border-top:1px solid #1e2433;text-align:center;">
            <p style="margin:0;font-size:11px;color:#6b7280;">
              Você recebe comunicados da LeakLabs porque tem conta na plataforma.<br>
              <a href="{unsub_link}" style="color:#6b7280;text-decoration:underline;">Não quero mais receber emails</a>
            </p>
          </td>
        </tr>
      </table>
    </td></tr>
  </table>
</body>
</html>"""


def send_admin_email(to_email: str, username: str, user_id: int,
                     title: str, body: str, category: str = "info") -> bool:
    """Envia o comunicado do admin por email (com rodapé de descadastro). True se enviado."""
    base_url = os.environ.get("APP_BASE_URL", "https://leaklabs.ai")
    token = _email_unsub_token(user_id)
    unsub_url = f"{base_url}/api/player/email/unsubscribe?uid={user_id}&token={token}"
    subject = (title or "").strip() or "Comunicado — LeakLabs.ai"
    html = build_admin_email_html(username, title, body, unsub_url, category)
    return send_transactional_email(to_email, subject, html)


def send_admin_email_bulk(recipients: list, title: str, body: str,
                          category: str = "info") -> dict:
    """Envia o comunicado para vários destinatários (já filtrados por opt-in).
    `recipients` = [{id,email,username}]. Retorna {'sent','errors'}."""
    sent = errors = 0
    for r in recipients:
        ok = send_admin_email(r.get("email", ""), r.get("username", ""),
                              int(r.get("id") or 0), title, body, category)
        if ok:
            sent += 1
        else:
            errors += 1
    log.info("Comunicado admin por email: sent=%d errors=%d", sent, errors)
    return {"sent": sent, "errors": errors}


# ── Runner (chamado pelo endpoint admin) ──────────────────────────────────────

def run_weekly_digest() -> dict:
    """
    Itera todos os usuários com digest_subscribed=1 que fizeram login
    nos últimos 30 dias e envia o email.
    Retorna {'sent': N, 'skipped': N, 'errors': N}.
    """
    from database.repositories import get_digest_subscribers
    users = get_digest_subscribers()
    sent = skipped = errors = 0
    for u in users:
        data = build_digest_data(u["id"])
        if not data:
            skipped += 1
            continue
        ok = send_digest_email(u["email"], u["username"], data, u["id"])
        if ok:
            sent += 1
        else:
            errors += 1
    log.info("Digest concluído: sent=%d skipped=%d errors=%d", sent, skipped, errors)
    return {"sent": sent, "skipped": skipped, "errors": errors}
