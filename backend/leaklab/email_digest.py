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
  DIGEST_FROM      — ex: noreply@grindlabpoker.com
  APP_BASE_URL     — ex: https://grindlabpoker.com (para links de unsubscribe)
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
<title>Seu resumo semanal · GrindLab</title></head>
<body style="margin:0;padding:0;background:#0f1117;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;">
  <table width="100%" cellpadding="0" cellspacing="0" style="background:#0f1117;padding:40px 16px;">
    <tr><td align="center">
      <table width="560" cellpadding="0" cellspacing="0" style="background:#161b27;border-radius:12px;overflow:hidden;border:1px solid #1e2433;">

        <!-- Header -->
        <tr>
          <td style="padding:24px;background:#1a1f2e;border-bottom:1px solid #1e2433;">
            <p style="margin:0;font-size:10px;font-family:monospace;text-transform:uppercase;letter-spacing:.12em;color:#2DD4BF;">GrindLab</p>
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
            <a href="https://grindlabpoker.com/dashboard"
               style="display:inline-block;background:#2DD4BF;color:#0A0E1A;text-decoration:none;padding:12px 28px;border-radius:8px;font-size:13px;font-weight:600;">
              Abrir GrindLab
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
    from_addr = os.environ.get("DIGEST_FROM", "noreply@grindlabpoker.com")
    base_url  = os.environ.get("APP_BASE_URL", "https://grindlabpoker.com")

    if not smtp_host or not smtp_user or not smtp_pass:
        log.warning("SMTP não configurado — digest não enviado para %s", to_email)
        return False

    token     = _unsub_token(user_id)
    unsub_url = f"{base_url}/api/player/digest/unsubscribe?uid={user_id}&token={token}"
    html_body = build_digest_html(username, data, unsub_url)

    msg = MIMEMultipart("alternative")
    msg["Subject"] = "📊 Seu resumo semanal · GrindLab"
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
    from_addr = os.environ.get("DIGEST_FROM", "noreply@grindlabpoker.com")

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

# Categoria só define uma eyebrow editorial (texto), sem ícone. Cor de destaque é
# sempre o teal da marca; a categoria muda apenas o rótulo.
_CATEGORY_LABEL = {"info": "Comunicado", "aviso": "Aviso importante", "novidade": "Novidade"}

# Paleta GrindLab
_C_BG      = "#0A0E1A"   # fundo
_C_CARD    = "#111726"   # card
_C_BORDER  = "#1F2A3A"
_C_TEAL    = "#2DD4BF"
_C_LIGHT   = "#E3E8EC"   # títulos
_C_BODY    = "#B4C0CC"   # corpo
_C_MUTED   = "#6B7A8A"   # rodapé
_FONT      = "-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif"


def _body_to_paragraphs(body: str) -> str:
    """Converte o corpo em parágrafos: linha em branco separa <p>, quebra simples vira <br>."""
    text = (body or "").strip()
    if not text:
        return ""
    blocks = [b.strip() for b in text.replace("\r\n", "\n").split("\n\n") if b.strip()]
    out = []
    for b in blocks:
        inner = b.replace("\n", "<br>")
        out.append(
            f'<p style="margin:0 0 18px 0;font-size:16px;line-height:1.7;color:{_C_BODY};">{inner}</p>'
        )
    return "\n            ".join(out)


def _cta_button(label: str, url: str) -> str:
    return (
        f'<table role="presentation" cellpadding="0" cellspacing="0" style="margin:12px 0 4px 0;">'
        f'<tr><td style="border-radius:10px;background:{_C_TEAL};">'
        f'<a href="{url}" style="display:inline-block;padding:14px 34px;font-size:15px;'
        f'font-weight:700;color:{_C_BG};text-decoration:none;white-space:nowrap;">{label}</a></td></tr></table>'
    )


def _email_document(*, title: str, inner_html: str, base_url: str,
                    footer_note: str, unsub_link: str | None = None,
                    preheader: str = "") -> str:
    """Shell visual único de todos os emails: logo GrindLab, barra teal, card escuro,
    conteúdo e rodapé. `inner_html` é o miolo já montado; `unsub_link` só nos comunicados."""
    logo_url = f"{base_url}/email-logo.png"
    from datetime import datetime
    year = datetime.utcnow().year
    unsub_html = (
        f'&nbsp;·&nbsp;<a href="{unsub_link}" style="color:{_C_MUTED};text-decoration:underline;">'
        f'Cancelar o recebimento de emails</a>' if unsub_link else ""
    )
    return f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width,initial-scale=1.0">
  <meta name="color-scheme" content="dark">
  <title>{title}</title>
</head>
<body style="margin:0;padding:0;background:{_C_BG};font-family:{_FONT};-webkit-font-smoothing:antialiased;">
  <div style="display:none;max-height:0;overflow:hidden;opacity:0;">{preheader or title}</div>
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:{_C_BG};padding:32px 16px;">
    <tr><td align="center">
      <table role="presentation" width="600" cellpadding="0" cellspacing="0" style="width:600px;max-width:600px;background:{_C_CARD};border:1px solid {_C_BORDER};border-radius:16px;overflow:hidden;">
        <tr>
          <td align="center" style="padding:36px 40px 28px 40px;background:{_C_BG};border-bottom:1px solid {_C_BORDER};">
            <img src="{logo_url}" width="196" alt="GrindLab" style="display:block;width:196px;max-width:60%;height:auto;border:0;color:{_C_LIGHT};font-size:24px;font-weight:800;letter-spacing:.02em;">
          </td>
        </tr>
        <tr><td style="height:3px;background:{_C_TEAL};line-height:3px;font-size:0;">&nbsp;</td></tr>
        <tr>
          <td style="padding:40px;">
            {inner_html}
          </td>
        </tr>
        <tr>
          <td style="padding:26px 40px;background:{_C_BG};border-top:1px solid {_C_BORDER};">
            <p style="margin:0 0 6px 0;font-size:13px;font-weight:700;letter-spacing:.02em;color:{_C_LIGHT};">GrindLab Poker</p>
            <p style="margin:0 0 14px 0;font-size:12px;line-height:1.6;color:{_C_MUTED};">{footer_note}</p>
            <p style="margin:0;font-size:12px;color:{_C_MUTED};">
              <a href="{base_url}" style="color:{_C_MUTED};text-decoration:underline;">grindlabpoker.com</a>{unsub_html}
            </p>
            <p style="margin:14px 0 0 0;font-size:11px;color:{_C_MUTED};">© {year} GrindLab. Todos os direitos reservados.</p>
          </td>
        </tr>
      </table>
    </td></tr>
  </table>
</body>
</html>"""


def _eyebrow(text: str) -> str:
    return f'<p style="margin:0 0 10px 0;font-size:12px;font-weight:700;text-transform:uppercase;letter-spacing:.14em;color:{_C_TEAL};">{text}</p>'


def _h1(text: str) -> str:
    return f'<h1 style="margin:0 0 24px 0;font-size:26px;line-height:1.25;font-weight:800;color:{_C_LIGHT};">{text}</h1>'


def _greeting(username: str) -> str:
    return f'<p style="margin:0 0 18px 0;font-size:16px;line-height:1.7;color:{_C_BODY};">Olá, {username},</p>'


def build_admin_email_html(username: str, title: str, body: str,
                           unsub_link: str, category: str = "info") -> str:
    """HTML profissional do comunicado do admin: logo GrindLab, cores da marca,
    tipografia limpa, sem ícones. Rodapé com descadastro (LGPD). O corpo aceita
    parágrafos (linha em branco) e quebras simples."""
    base_url   = os.environ.get("APP_BASE_URL", "https://grindlabpoker.com")
    eyebrow    = _CATEGORY_LABEL.get(category, _CATEGORY_LABEL["info"])
    safe_title = (title or "").strip() or "Comunicado da GrindLab"
    inner = (
        _eyebrow(eyebrow) + _h1(safe_title) + _greeting(username)
        + _body_to_paragraphs(body)
        + _cta_button("Acessar a plataforma", f"{base_url}/dashboard")
    )
    return _email_document(
        title=safe_title, inner_html=inner, base_url=base_url,
        footer_note="A plataforma de treino e evolução para jogadores de torneio. "
                    "Este comunicado foi enviado porque você tem uma conta na GrindLab.",
        unsub_link=unsub_link,
    )


def build_verification_email_html(username: str, code: str, minutes: int = 15) -> str:
    """Email de confirmação de conta com o código de verificação em destaque."""
    base_url = os.environ.get("APP_BASE_URL", "https://grindlabpoker.com")
    code_box = (
        f'<table role="presentation" cellpadding="0" cellspacing="0" style="margin:8px 0 22px 0;">'
        f'<tr><td style="background:{_C_BG};border:1px solid {_C_BORDER};border-radius:12px;padding:22px 40px;">'
        f'<span style="font-family:\'Courier New\',monospace;font-size:38px;font-weight:800;'
        f'letter-spacing:.32em;color:{_C_TEAL};">{code}</span></td></tr></table>'
    )
    inner = (
        _eyebrow("Confirmação de conta") + _h1("Confirme seu email") + _greeting(username)
        + f'<p style="margin:0 0 8px 0;font-size:16px;line-height:1.7;color:{_C_BODY};">'
          f'Use o código abaixo para concluir seu cadastro na GrindLab:</p>'
        + code_box
        + f'<p style="margin:0;font-size:14px;line-height:1.6;color:{_C_MUTED};">'
          f'O código expira em {minutes} minutos. Se você não criou esta conta, é só ignorar este email.</p>'
    )
    return _email_document(
        title="Seu código de confirmação · GrindLab", inner_html=inner, base_url=base_url,
        footer_note="Você recebeu este email porque uma conta foi criada com este endereço na GrindLab.",
        preheader=f"Seu código de confirmação: {code}",
    )


def build_password_reset_email_html(username: str, code: str, minutes: int = 15) -> str:
    """Email de redefinição de senha com o código em destaque."""
    base_url = os.environ.get("APP_BASE_URL", "https://grindlabpoker.com")
    code_box = (
        f'<table role="presentation" cellpadding="0" cellspacing="0" style="margin:8px 0 22px 0;">'
        f'<tr><td style="background:{_C_BG};border:1px solid {_C_BORDER};border-radius:12px;padding:22px 40px;">'
        f'<span style="font-family:\'Courier New\',monospace;font-size:38px;font-weight:800;'
        f'letter-spacing:.32em;color:{_C_TEAL};">{code}</span></td></tr></table>'
    )
    inner = (
        _eyebrow("Redefinição de senha") + _h1("Redefina sua senha") + _greeting(username)
        + f'<p style="margin:0 0 8px 0;font-size:16px;line-height:1.7;color:{_C_BODY};">'
          f'Recebemos um pedido para redefinir a senha da sua conta GrindLab. '
          f'Use o código abaixo para criar uma nova senha:</p>'
        + code_box
        + f'<p style="margin:0;font-size:14px;line-height:1.6;color:{_C_MUTED};">'
          f'O código expira em {minutes} minutos. Se você não pediu para redefinir a senha, '
          f'é só ignorar este email, sua senha atual continua valendo.</p>'
    )
    return _email_document(
        title="Redefinição de senha · GrindLab", inner_html=inner, base_url=base_url,
        footer_note="Você recebeu este email porque um pedido de redefinição de senha foi feito para esta conta.",
        preheader=f"Seu código de redefinição: {code}",
    )


def build_welcome_email_html(username: str) -> str:
    """Email de boas-vindas enviado após a verificação concluída."""
    base_url = os.environ.get("APP_BASE_URL", "https://grindlabpoker.com")
    inner = (
        _eyebrow("Bem-vindo à GrindLab") + _h1("Sua conta está pronta") + _greeting(username)
        + f'<p style="margin:0 0 18px 0;font-size:16px;line-height:1.7;color:{_C_BODY};">'
          f'Sua conta foi confirmada. A partir de agora você pode importar seus torneios, '
          f'treinar seus spots mais custosos e acompanhar sua evolução mão a mão.</p>'
        + f'<p style="margin:0 0 18px 0;font-size:16px;line-height:1.7;color:{_C_BODY};">'
          f'Comece importando um torneio recente. A plataforma analisa cada decisão e mostra '
          f'onde estão seus leaks e como corrigi-los.</p>'
        + _cta_button("Começar agora", f"{base_url}/dashboard")
    )
    return _email_document(
        title="Bem-vindo à GrindLab", inner_html=inner, base_url=base_url,
        footer_note="A plataforma de treino e evolução para jogadores de torneio.",
        preheader="Sua conta foi confirmada. Bom grind.",
    )


def send_admin_email(to_email: str, username: str, user_id: int,
                     title: str, body: str, category: str = "info") -> bool:
    """Envia o comunicado do admin por email (com rodapé de descadastro). True se enviado."""
    base_url = os.environ.get("APP_BASE_URL", "https://grindlabpoker.com")
    token = _email_unsub_token(user_id)
    unsub_url = f"{base_url}/api/player/email/unsubscribe?uid={user_id}&token={token}"
    subject = (title or "").strip() or "Comunicado · GrindLab"
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


# ── Verificação de conta + boas-vindas (transacionais) ───────────────────────

def send_verification_email(to_email: str, username: str, code: str, minutes: int = 15) -> bool:
    """Envia o código de confirmação de conta. True se enviado."""
    html = build_verification_email_html(username, code, minutes)
    return send_transactional_email(to_email, f"Seu código de confirmação: {code}", html)


def send_welcome_email(to_email: str, username: str) -> bool:
    """Envia o email de boas-vindas após a conta ser verificada. True se enviado."""
    html = build_welcome_email_html(username)
    return send_transactional_email(to_email, "Bem-vindo à GrindLab", html)


def send_password_reset_email(to_email: str, username: str, code: str, minutes: int = 15) -> bool:
    """Envia o código de redefinição de senha. True se enviado."""
    html = build_password_reset_email_html(username, code, minutes)
    return send_transactional_email(to_email, f"Seu código de redefinição: {code}", html)


# ── Win-back (reengajamento de inativos) ─────────────────────────────────────

# Estágios em dias de inatividade e cooldown mínimo entre envios (dias).
_WINBACK_STAGE_DAYS = [7, 21, 45]
_WINBACK_COOLDOWN_DAYS = 7


def _parse_dt(v):
    from datetime import datetime
    if not v:
        return None
    if isinstance(v, datetime):
        return v
    s = str(v)
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S.%f"):
        try:
            return datetime.strptime(s[:26], fmt)
        except Exception:
            pass
    try:
        return datetime.fromisoformat(s.replace("Z", ""))
    except Exception:
        return None


def _winback_hook_html(hook) -> str:
    """Gancho pessoal a partir de build_digest_data (top_leak). Genérico se sem dados."""
    P = f'margin:0 0 18px 0;font-size:16px;line-height:1.7;color:{_C_BODY};'
    if hook and hook.get("top_leak"):
        spot = (hook["top_leak"].get("spot") or "").replace("_", " ")
        ev = abs(hook["top_leak"].get("ev_loss_bb", 0) or 0)
        return (f'<p style="{P}">Seu leak mais custoso continua aberto: '
                f'<strong style="color:{_C_LIGHT};">{spot}</strong> '
                f'(cerca de {ev:.1f} bb perdidos). Alguns minutos de treino já começam a fechar isso.</p>')
    return (f'<p style="{P}">Importe um torneio recente e veja onde estão seus leaks. '
            f'A plataforma analisa cada decisão e mostra exatamente o que corrigir.</p>')


def build_winback_email_html(username: str, days: int, hook, unsub_link: str) -> str:
    """Email de reengajamento: gancho pessoal (maior leak) + CTA de volta. Com descadastro."""
    base_url = os.environ.get("APP_BASE_URL", "https://grindlabpoker.com")
    inner = (
        _eyebrow("Sentimos sua falta") + _h1("Seus torneios continuam esperando") + _greeting(username)
        + f'<p style="margin:0 0 18px 0;font-size:16px;line-height:1.7;color:{_C_BODY};">'
          f'Faz {days} dias desde seu último acesso à GrindLab.</p>'
        + _winback_hook_html(hook)
        + _cta_button("Voltar a treinar", f"{base_url}/dashboard")
    )
    return _email_document(
        title="Seus torneios continuam esperando · GrindLab", inner_html=inner, base_url=base_url,
        footer_note="A plataforma de treino e evolução para jogadores de torneio.",
        unsub_link=unsub_link,
        preheader="Seu maior leak continua aberto. Volte quando quiser.",
    )


def send_winback_email(to_email: str, username: str, user_id: int, days: int, hook) -> bool:
    """Envia o email de win-back (com descadastro, respeitando LGPD). True se enviado."""
    base_url = os.environ.get("APP_BASE_URL", "https://grindlabpoker.com")
    token = _email_unsub_token(user_id)
    unsub = f"{base_url}/api/player/email/unsubscribe?uid={user_id}&token={token}"
    html = build_winback_email_html(username, days, hook, unsub)
    return send_transactional_email(to_email, "Seus torneios continuam esperando", html)


def run_winback(dry_run: bool = False, limit: int | None = None) -> dict:
    """Varre inativos e envia o email do estágio devido (7/21/45 dias), respeitando
    cooldown, opt-out e verificação. dry_run=True só devolve a prévia, sem enviar.
    Retorna {'candidates','sent','skipped','errors'[, 'preview']}."""
    from database.repositories import get_winback_candidates, mark_winback_sent
    from datetime import datetime
    cands = get_winback_candidates(_WINBACK_STAGE_DAYS[0], _WINBACK_COOLDOWN_DAYS)
    now = datetime.utcnow()
    sent = skipped = errors = 0
    preview = []
    for u in cands:
        ll = _parse_dt(u.get("last_login"))
        days = (now - ll).days if ll else 999
        stage = int(u.get("winback_stage") or 0)
        if stage >= len(_WINBACK_STAGE_DAYS) or days < _WINBACK_STAGE_DAYS[stage]:
            skipped += 1
            continue
        if dry_run:
            preview.append({"email": u["email"], "username": u["username"],
                            "days": days, "next_stage": stage + 1})
            continue
        try:
            hook = build_digest_data(u["id"])
        except Exception:
            hook = None
        ok = send_winback_email(u["email"], u["username"], u["id"], days, hook)
        if ok:
            mark_winback_sent(u["id"], stage + 1)
            sent += 1
        else:
            errors += 1
        if limit and sent >= limit:
            break
    res = {"candidates": len(cands), "sent": sent, "skipped": skipped, "errors": errors}
    if dry_run:
        res["preview"] = preview[:100]
    log.info("Win-back run: %s", res)
    return res


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
