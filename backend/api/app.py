"""
PokerLeakLab API v2 — com persistência SQLite e autenticação JWT.
"""
from __future__ import annotations
import sys, os, re, uuid, time, json, logging, threading
import math
from pathlib import Path

_BASE = Path(__file__).resolve().parent.parent  # backend/
sys.path.insert(0, str(_BASE))

from dotenv import load_dotenv
load_dotenv(_BASE / '.env')

# ── Structured JSON logging ───────────────────────────────────────────────────

class _JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        entry: dict = {
            'ts':    self.formatTime(record, '%Y-%m-%dT%H:%M:%S'),
            'level': record.levelname,
            'mod':   record.module,
            'msg':   record.getMessage(),
        }
        for key in ('request_id', 'user_id', 'duration_ms', 'status', 'method', 'path'):
            if hasattr(record, key):
                entry[key] = getattr(record, key)
        if record.exc_info:
            entry['exc'] = self.formatException(record.exc_info)
        return json.dumps(entry, ensure_ascii=False)

_handler = logging.StreamHandler()
_handler.setFormatter(_JsonFormatter())
logging.basicConfig(handlers=[_handler], level=logging.INFO, force=True)

log = logging.getLogger(__name__)

# ── Sentry (no-op when SENTRY_DSN is absent or sdk not installed) ────────────
# Init AFTER logging.basicConfig so Sentry's LoggingIntegration appends on top
# of our handler instead of being wiped by force=True.
_SENTRY_DSN = os.environ.get('SENTRY_DSN', '')
if _SENTRY_DSN:
    try:
        import sentry_sdk
        from sentry_sdk.integrations.flask import FlaskIntegration
        from sentry_sdk.integrations.logging import LoggingIntegration
        sentry_sdk.init(
            dsn=_SENTRY_DSN,
            integrations=[
                FlaskIntegration(),
                LoggingIntegration(level=logging.WARNING, event_level=logging.ERROR),
            ],
            traces_sample_rate=0.05,
            environment=os.environ.get('ENVIRONMENT', 'development'),
            send_default_pii=False,
        )
    except ImportError:
        log.warning('sentry-sdk not installed — Sentry disabled')

from flask import Flask, request, jsonify, g
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

from leaklab.parser import parse_pokerstars_file_from_text
from leaklab.parser import raise_total_from_raw as _raise_total_from_raw
from leaklab.pipeline import build_decision_inputs_for_hand
from leaklab.decision_engine_v11 import evaluate_decision, facing_allin_row
from leaklab.pareamento_decisoes import BaldeDeDecisoes, balde_de_gto_do_banco
from leaklab.mtt_context import build_mtt_context
from leaklab.gto_utils import hand_to_type as _hand_to_type
from leaklab.preflop_gto_ranges import analyze_preflop as _analyze_preflop
from leaklab.session_metrics import build_session_metrics
from leaklab.leak_correlator import correlate_leaks
from leaklab.llm_explainer import explain_decisions, generate_tournament_summary, generate_tournament_narrative, generate_comparison_narrative, coach_chat_reply
from leaklab.report_generator import build_html_report, generate_pdf_bytes
from leaklab.email_digest import (
    run_weekly_digest, verify_unsub_token, send_transactional_email,
    verify_email_unsub_token, send_admin_email, send_admin_email_bulk,
    send_verification_email, send_welcome_email, send_password_reset_email, run_winback,
)

from database.schema import init_db
from database.repositories import (
    create_user, verify_password, get_user_by_email, get_user_by_id, get_user_by_username,
    save_tournament, save_decisions, get_tournaments,
    get_tournament, get_tournament_by_db_id, get_decisions, update_llm_summary,
    get_llm_cache, set_llm_cache,
    get_evolution_metrics, get_leak_summary, get_leak_roi_impact,
    get_pressure_profile, get_confidence_drift,
    get_drill_spots, save_drill_session, get_drill_stats, get_decision_for_drill,
    get_player_dna,
    get_icm_performance, get_breakdown, get_player_stats,
    get_player_level, get_player_action_frequencies,
    get_students,
    # Coach system
    assign_invite_key, get_coach_by_invite_key, link_student_to_coach,
    upsert_coach_profile, get_coach_profile, get_public_coaches,
    get_coach_impact_metrics, recommend_coaches_for_leaks,
    get_study_overrides, save_study_override, delete_study_override,
    get_annotations, get_annotations_for_decisions, upsert_annotation,
    delete_annotation, get_reviewed_tournament_ids,
    get_all_students_worst_decisions, get_common_leaks,
    # Sprint 6 — BACK-002
    get_coach_baseline, set_coach_baseline, delete_coach_baseline,
    get_student_activity_feed, get_baseline_comparison,
    # Sprint 7 — BACK-006
    upsert_review, delete_review, get_reviews, get_my_review,
    # Sprint 8 — BACK-006 pt.2
    get_public_coach_reviews,
    # Sprint 9 — BACK-010: quota
    get_quota_status, increment_tournament_count, increment_ai_calls, PLAN_LIMITS,
    # Sprint 11 — BACK-011: security
    decision_belongs_to_student,
    # Sprint 15 — BACK-015: payments
    save_payment, get_payments, update_user_plan,
    get_phase_analysis, get_texture_analysis, get_tournaments_comparison,
    # Sprint C — BACK-014 + BACK-017: admin panel + revenue share
    get_admin_dashboard_stats, get_all_users, get_all_users_count, update_user_admin, delete_user_admin,
    get_coach_finance_summary, get_coach_finance_students, get_coach_finance_history,
    get_admin_activity_logs,
    # Sprint D — BACK-016: WhatsApp
    get_user_by_phone, update_user_phone,
    # Sprint Q — FEAT-02 + FEAT-03: Daily Focus + XP Server-Side
    reset_drill_sessions,
    add_xp, get_xp_status, get_achievements,
    # Sprint S — FEAT-06: Leak Causal Graph
    get_leak_graph_data,
    # Sprint T — FEAT-07: Coach Effectiveness
    get_coach_effectiveness_report,
    # Sprint V — FEAT-09: Coach Plan Templates
    get_coach_templates, create_coach_template, delete_coach_template,
    # Sprint V — FEAT-10: Coach Messages
    send_coach_message, get_coach_messages, mark_messages_read, get_unread_message_count,
    get_coach_message_count,
    # Sprint W — FEAT-11: Digest
    get_digest_subscribers, update_digest_subscription,
    # Email de comunicado do admin (opt-out)
    get_email_recipients, update_email_opt_in,
    # Verificação de email no cadastro (2FA simples)
    set_verification_code, verify_email_code, mark_email_verified,
    # Atividade / win-back
    touch_activity,
    # Sprint AH — BACK-018: Coach Application Flow
    create_coach_application, get_coach_applications,
    approve_coach_application, reject_coach_application,
    # Sprint AP — Career Graph
    get_career_projection,
    # Sprint AQ — Cognitive Failure Mapper
    get_cognitive_failure_report,
    # Sprint AR — Personal Strategic Twin
    get_strategic_twin_profile,
    # Sprint AS — AI Sparring Mode
    get_sparring_hand,
    # FEAT-08 — Session Goals
    get_session_goal_for_tournament, save_session_goal_review,
    reconcile_tournament_labels,
)
from database.auth import generate_token, require_auth, require_coach, require_admin
from leaklab.content_moderation import sanitize_llm_input, moderate_text
from leaklab.stripe_gateway import (
    create_subscription, cancel_subscription, get_subscription, get_payment,
    validate_webhook, PLAN_AMOUNTS, PLAN_AMOUNTS_ANNUAL, BILLING_DAYS, plan_amount,
    create_billing_portal_session, STRIPE_WEBHOOK_SECRET,
)


def _ts_to_str(ts):
    """PAY-04: unix timestamp do Stripe (current_period_end) → string ISO p/ plan_expires_at."""
    if not ts:
        return None
    import datetime as _dt
    try:
        return _dt.datetime.utcfromtimestamp(int(ts)).strftime('%Y-%m-%d %H:%M:%S')
    except (ValueError, TypeError, OSError):
        return None


def _plan_period(billing_cycle: str):
    """PAY-02: (period_start, period_end) ISO p/ o ciclo escolhido a partir de agora."""
    import datetime as _dt
    days = BILLING_DAYS.get(billing_cycle, 30)
    now  = _dt.datetime.utcnow()
    end  = now + _dt.timedelta(days=days)
    fmt  = '%Y-%m-%d %H:%M:%S'
    return now.strftime(fmt), end.strftime(fmt)

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 5 * 1024 * 1024

# Atrás de proxy (Cloudflare/Nginx, Render): confia no X-Forwarded-For do proxy imediato
# para que get_remote_address (rate-limiter anti-abuso) veja o IP REAL do usuário, não o do
# proxy. Sem isso, /analyze/guest e /subscription/checkout limitariam por IP de proxy.
# x_for=1 = confia em 1 hop (o Nginx/Render que adiciona o IP real ao XFF).
from werkzeug.middleware.proxy_fix import ProxyFix
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)

# ── Request instrumentation ───────────────────────────────────────────────────

@app.before_request
def _before():
    g.request_id = uuid.uuid4().hex[:8]
    g.t0 = time.monotonic()

# Analytics de uso (MVP): rota → funcionalidade. Allowlist CURADO — só rotas que são
# uma feature de verdade (ignora polling/infra: /health, unread-count, /auth, OPTIONS).
# Prefixo, primeiro match vence (mais específico antes). Métrica-chave = usuários únicos.
_FEATURE_MAP = [
    ('/analyze/guest',             'analyze_guest'),
    ('/analyze',                   'import_tournament'),
    ('/player/spots/drill',        'ghost_table'),
    ('/player/sparring',           'leak_trainer'),
    ('/player/training',           'leak_trainer'),
    ('/coach/chat',                'ai_coach_chat'),
    ('/replay',                    'replayer'),
    ('/study/plan',                'study_plan'),
    ('/student/study-plan',        'study_plan'),
    ('/player/career',             'career_graph'),
    ('/player/cognitive-failures', 'cognitive_failures'),
    ('/player/strategic-twin',     'strategic_twin'),
    ('/player/leak-graph',         'leak_causal_map'),
    ('/player/leak-roi',           'leak_finder'),
    ('/player/leak-finder',        'leak_finder'),
    ('/metrics/leaderboard',       'leaderboard'),
    ('/player/elo',                'rating_elo'),
    ('/player/rating',             'rating_elo'),
    ('/history/tournaments',       'history'),
    ('/history/evolution',         'history'),
    ('/preflop-ranges',            'gto_ranges'),
    ('/gto/strategy',              'gto_ranges'),
    ('/support',                   'support'),
    ('/coach/students',            'coach_dashboard'),
    ('/coach/context',             'coach_dashboard'),
    ('/tournament',                'tournament_detail'),
    ('/metrics/player-stats',      'dashboard'),   # âncora: carrega 1x por abertura do dashboard
]

def _feature_for_path(path: str):
    for prefix, key in _FEATURE_MAP:
        if path.startswith(prefix):
            return key
    return None

@app.after_request
def _log_request(response):
    try:
        duration_ms = round((time.monotonic() - g.get('t0', time.monotonic())) * 1000)
        log.info(
            '%s %s %s',
            request.method, request.path, response.status_code,
            extra={
                'request_id': g.get('request_id', ''),
                'user_id':    g.get('user_id', ''),
                'method':     request.method,
                'path':       request.path,
                'status':     response.status_code,
                'duration_ms': duration_ms,
            },
        )
        response.headers['X-Request-Id'] = g.get('request_id', '')
    except Exception:
        pass
    # Analytics de uso: registra a funcionalidade (agregado por dia). Só request autenticado,
    # 2xx/3xx, não-OPTIONS, e rota mapeada. Silencioso — nunca afeta a resposta.
    try:
        uid = g.get('user_id')
        if uid and request.method != 'OPTIONS' and response.status_code < 400:
            fk = _feature_for_path(request.path)
            if fk:
                from database.repositories import record_feature_usage
                record_feature_usage(uid, fk)
    except Exception:
        pass
    return response

# ALLOWED_ORIGINS: comma-separated list of trusted frontend origins.
# Defaults to "*" in dev; set explicitly in production via env var.
_RAW_ORIGINS = os.environ.get('ALLOWED_ORIGINS', '*')
_ALLOWED_ORIGINS = [o.strip() for o in _RAW_ORIGINS.split(',')] if _RAW_ORIGINS != '*' else '*'
CORS(app,
     resources={r"/*": {"origins": _ALLOWED_ORIGINS}},
     supports_credentials=False,
     automatic_options=True)

limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=[],
    storage_uri="memory://",
)

@limiter.request_filter
def _exempt_in_testing():
    return app.testing

# Forçar CORS em TODA resposta incluindo erros não capturados
@app.after_request
def _cors_every_response(response):
    if _RAW_ORIGINS == '*':
        response.headers.setdefault('Access-Control-Allow-Origin', '*')
    else:
        origin = request.headers.get('Origin', '')
        if origin in _ALLOWED_ORIGINS:
            response.headers['Access-Control-Allow-Origin'] = origin
            response.headers['Vary'] = 'Origin'
    response.headers.setdefault('Access-Control-Allow-Headers', 'Content-Type, Authorization')
    response.headers.setdefault('Access-Control-Allow-Methods', 'GET, POST, PUT, PATCH, DELETE, OPTIONS')
    return response


@app.after_request
def _security_headers(response):
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['X-XSS-Protection'] = '1; mode=block'
    response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
    # `is_production()` e nao a condicao estreita: com RENDER/LEAKLAB_PROD, que nenhum arquivo
    # do repositorio escreve, o HSTS NUNCA era emitido em producao.
    from database.auth import is_production as _e_prod
    if _e_prod():
        response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
    return response

# Inicializar banco ao subir
init_db()

# ── BACK-010: Quota helpers ────────────────────────────────────────────────────

def _check_upload_quota(user_id: int):
    """Retorna resposta 402 se usuário Free atingiu o limite mensal de torneios, None caso contrário."""
    status = get_quota_status(user_id)
    limit  = status['limits'].get('tournaments')
    if limit is not None and status['tournaments_used'] >= limit:
        return jsonify({
            'error': 'Limite mensal de torneios atingido.',
            'quota_exceeded': True,
            'plan': status['plan'],
            'used': status['tournaments_used'],
            'limit': limit,
        }), 402
    return None


def _check_ai_quota(user_id: int):
    """Retorna resposta 402 se usuário Free atingiu o limite mensal de análises IA, None caso contrário."""
    status = get_quota_status(user_id)
    limit  = status['limits'].get('ai_calls')
    if limit is not None and status['ai_calls_used'] >= limit:
        return jsonify({
            'error': 'Limite mensal de análises IA atingido.',
            'quota_exceeded': True,
            'plan': status['plan'],
            'used': status['ai_calls_used'],
            'limit': limit,
        }), 402
    return None


def _check_advanced_insights(user_id: int):
    """Retorna 402 se o plano não inclui os insights de IA avançada (Strategic Twin,
    Cognitive Failures, Leak Causal Map, Career) — exclusivos do Pro. None caso contrário."""
    status = get_quota_status(user_id)
    if not status['limits'].get('advanced_insights', False):
        return jsonify({
            'error': 'Insights avançados de IA são exclusivos do plano Pro.',
            'upgrade_required': True,
            'feature': 'advanced_insights',
            'plan': status['plan'],
        }), 402
    return None

# ── Auth ──────────────────────────────────────────────────────────────────────

def _email_verification_enabled() -> bool:
    """Verificação de email por código só é exigida quando há SMTP configurado (prod).
    Em dev/testes (sem SMTP) o cadastro segue instantâneo, sem quebrar o fluxo local.
    EMAIL_VERIFICATION_DISABLED=1 força desligar mesmo com SMTP."""
    if os.environ.get('EMAIL_VERIFICATION_DISABLED', '').strip().lower() in ('1', 'true', 'yes', 'on'):
        return False
    return bool(os.environ.get('SMTP_HOST') and os.environ.get('SMTP_USER')
                and os.environ.get('SMTP_PASSWORD'))


def _gen_verification_code() -> str:
    """Código numérico de 6 dígitos (com zeros à esquerda), gerado com secrets."""
    import secrets
    return f"{secrets.randbelow(1000000):06d}"


def _verification_ttl_min() -> int:
    """Validade do código de confirmação de cadastro, em minutos (default 24h).

    Era 15 minutos, herdado de OTP de login. Confirmação de cadastro é outro caso de uso:
    a pessoa cadastra no celular, o e-mail demora ou cai em spam, e quando ela acha o código
    já morreu — recebendo "Código expirado", que parece erro dela.

    Não é infinito de propósito: `/auth/verify-email` EMITE token de sessão, então o código é
    credencial de acesso à conta. Sem expirar, viraria uma senha permanente de 6 dígitos
    guardada na caixa de e-mail de quem nunca confirmou."""
    try:
        v = int(os.environ.get('EMAIL_VERIFICATION_TTL_MIN', '1440'))
    except ValueError:
        return 1440
    return v if 5 <= v <= 43200 else 1440


# Reset de SENHA continua curto de propósito: esse código troca a senha da conta, é o alvo
# clássico de quem invade uma caixa de e-mail. A folga de 24h vale para confirmar cadastro
# (o pior caso é ativar uma conta que já era daquele e-mail), não para tomar uma conta viva.
_PASSWORD_RESET_TTL_MIN = 15


def _issue_verification(user_id: int, email: str, username: str) -> bool:
    """Gera + grava + envia o código de verificação. Retorna se o email saiu."""
    from datetime import datetime, timedelta
    ttl = _verification_ttl_min()
    code = _gen_verification_code()
    expires = (datetime.utcnow() + timedelta(minutes=ttl)).strftime("%Y-%m-%d %H:%M:%S")
    set_verification_code(user_id, code, expires)
    try:
        return send_verification_email(email, username, code, ttl)
    except Exception:
        log.exception("failed sending verification email to %s", email)
        return False


@app.route('/auth/register', methods=['POST'])
@limiter.limit("10 per minute")
def register():
    data = request.get_json(silent=True) or {}
    username = data.get('username', '').strip()
    email    = data.get('email',    '').strip().lower()
    password = data.get('password', '')
    role     = data.get('role', 'player')

    if role == 'coach':
        return jsonify({'error': 'Coaches devem se candidatar via /auth/coach-apply'}), 400
    if role not in ('player',):
        role = 'player'

    if not all([username, email, password]):
        return jsonify({'error': 'username, email e password são obrigatórios'}), 400
    if '@' in username:
        return jsonify({'error': 'Nome de usuário não pode ser um email', 'code': 'username_is_email'}), 400
    from leaklab.content_moderation import moderate_handle as _mod_handle
    if not _mod_handle(username)[0]:
        return jsonify({'error': 'Nome de usuário não permitido', 'code': 'username_offensive'}), 400
    if len(password) < 8:
        return jsonify({'error': 'Senha deve ter pelo menos 8 caracteres'}), 400
    if get_user_by_email(email):
        return jsonify({'error': 'Email já cadastrado'}), 409
    if get_user_by_username(username):
        return jsonify({'error': 'Nome de usuário já está em uso'}), 409

    # Link referral do coach: ?ref=<invite_key>. Resolve o coach e já vincula o aluno como
    # PENDENTE (entra na fila de aprovação do coach). Ref inválido/cheio → signup normal.
    ref = (data.get('ref') or '').strip().upper()
    coach_id = referral_coach_id = link_status = invited_by_key = None
    _coach = None
    if ref:
        from database.repositories import get_coach_by_invite_key
        _coach = get_coach_by_invite_key(ref)
        if _coach and _coach.get('role') == 'coach':
            coach_id          = _coach['id']
            referral_coach_id = _coach['id']
            link_status       = 'pending'
            invited_by_key    = ref

    # Origem de aquisição: utm_source capturado no front (ex.: 'instagram'). Sanitiza p/ não virar
    # lixo: minúsculo, só [a-z0-9_-], máx 40 chars. Vazio → None (orgânico/direto).
    import re as _re_acq
    _acq = (data.get('acquisition_source') or '').strip().lower()[:40]
    _acq = _re_acq.sub(r'[^a-z0-9_-]', '', _acq) or None

    verify_on = _email_verification_enabled()
    try:
        user_id = create_user(username, email, password, role,
                              coach_id=coach_id, referral_coach_id=referral_coach_id,
                              link_status=link_status, invited_by_key=invited_by_key,
                              acquisition_source=_acq,
                              email_verified=0 if verify_on else 1)
        # Candidatura ao programa de fundadores feita no próprio cadastro (veio de /fundadores).
        # Gravada em coluna PRÓPRIA, não em acquisition_source: de onde veio (instagram) e o
        # que pediu (ser fundador) são dois fatos distintos, e um não pode apagar o outro.
        if bool(data.get('founder_apply')):
            try:
                from database.repositories import apply_as_founder
                apply_as_founder(user_id)
            except Exception:
                # Não derruba o cadastro por causa da candidatura, mas também não some com
                # a falha: sem o log, o jogador ficaria fora da fila sem ninguém saber.
                log.exception("falha ao registrar candidatura de fundador para user %s", user_id)
        linked = _coach['username'] if (ref and coach_id) else None
        if verify_on:
            # Não emite token: a conta só completa depois que o código do email é validado.
            email_sent = _issue_verification(user_id, email, username)
            return jsonify({'pending_verification': True, 'email': email,
                            'email_sent': email_sent, 'linked_coach': linked}), 201
        token = generate_token(user_id, role)
        return jsonify({'token': token, 'user_id': user_id, 'role': role,
                        'linked_coach': linked}), 201
    except Exception as e:
        log.exception("register error for %s", email)
        return jsonify({'error': 'Erro interno ao criar conta'}), 500


@app.route('/auth/verify-email', methods=['POST'])
@limiter.limit("10 per minute")
def verify_email():
    """Valida o código de confirmação; ao dar certo verifica a conta, envia boas-vindas
    e emite o token (login)."""
    data  = request.get_json(silent=True) or {}
    email = data.get('email', '').strip().lower()
    code  = (data.get('code') or '').strip()
    if not email or not code:
        return jsonify({'error': 'email e código são obrigatórios'}), 400
    res = verify_email_code(email, code)
    st  = res.get('status')
    if st == 'ok':
        u = res['user']
        mark_email_verified(u['id'])
        try:
            send_welcome_email(u['email'], u['username'])
        except Exception:
            log.exception("welcome email failed for %s", email)
        linked = None
        if u.get('coach_id') and u.get('link_status') == 'pending':
            from database.repositories import get_user_by_id
            c = get_user_by_id(u['coach_id'])
            linked = c['username'] if c else None
        token = generate_token(u['id'], u['role'])
        return jsonify({'token': token, 'user_id': u['id'], 'username': u['username'],
                        'role': u['role'], 'linked_coach': linked})
    if st == 'already':
        return jsonify({'error': 'Esta conta já está confirmada. É só fazer login.', 'code': 'already'}), 400
    if st == 'expired':
        return jsonify({'error': 'Código expirado. Reenvie um novo código.', 'code': 'expired'}), 400
    if st == 'too_many':
        return jsonify({'error': 'Muitas tentativas. Reenvie um novo código.', 'code': 'too_many'}), 429
    if st == 'not_found':
        return jsonify({'error': 'Cadastro não encontrado.', 'code': 'not_found'}), 404
    return jsonify({'error': 'Código inválido.', 'code': 'invalid',
                    'remaining': res.get('remaining')}), 400


@app.route('/auth/resend-code', methods=['POST'])
@limiter.limit("5 per minute")
def resend_code():
    """Reenvia o código de confirmação. Não vaza existência de conta: sempre responde ok."""
    data  = request.get_json(silent=True) or {}
    email = data.get('email', '').strip().lower()
    if not email:
        return jsonify({'error': 'email é obrigatório'}), 400
    u = get_user_by_email(email)
    sent = False
    if u and int(u.get('email_verified') or 0) == 0:
        sent = _issue_verification(u['id'], email, u['username'])
    return jsonify({'ok': True, 'email_sent': sent})


@app.route('/auth/coach-apply', methods=['POST'])
@limiter.limit("5 per minute")
def coach_apply():
    data = request.get_json(silent=True) or {}
    username         = data.get('username', '').strip()
    email            = data.get('email', '').strip().lower()
    password         = data.get('password', '')
    instagram_handle = data.get('instagram_handle', '').strip()
    bio              = data.get('bio', '').strip()
    specialties      = data.get('specialties', '[]')
    experience_years = int(data.get('experience_years', 0) or 0)
    biggest_results  = data.get('biggest_results', '').strip()

    if not all([username, email, password]):
        return jsonify({'error': 'username, email e password são obrigatórios'}), 400
    if '@' in username:
        return jsonify({'error': 'Nome de usuário não pode ser um email', 'code': 'username_is_email'}), 400
    from leaklab.content_moderation import moderate_handle as _mod_handle
    if not _mod_handle(username)[0]:
        return jsonify({'error': 'Nome de usuário não permitido', 'code': 'username_offensive'}), 400
    if len(password) < 8:
        return jsonify({'error': 'Senha deve ter pelo menos 8 caracteres'}), 400
    if get_user_by_email(email):
        return jsonify({'error': 'Email já cadastrado'}), 409
    if get_user_by_username(username):
        return jsonify({'error': 'Nome de usuário já está em uso'}), 409
    if not bio or len(bio) < 30:
        return jsonify({'error': 'Bio deve ter pelo menos 30 caracteres'}), 400

    try:
        user_id = create_user(username, email, password, 'coach_pending')
        create_coach_application(user_id, instagram_handle, bio,
                                  specialties if isinstance(specialties, str) else str(specialties),
                                  experience_years, biggest_results)
        return jsonify({'ok': True, 'message': 'Candidatura recebida. Você será notificado por email.'}), 201
    except Exception as e:
        log.exception("coach_apply error for %s", email)
        return jsonify({'error': 'Erro interno ao criar candidatura'}), 500


@app.route('/auth/login', methods=['POST'])
@limiter.limit("15 per minute")
def login():
    data     = request.get_json(silent=True) or {}
    email    = data.get('email', '').strip().lower()
    password = data.get('password', '')

    user = verify_password(email, password)
    if not user:
        return jsonify({'error': 'Credenciais inválidas'}), 401

    if user.get('role') == 'coach_pending':
        return jsonify({
            'error': 'Candidatura em análise. Você receberá um email quando for aprovado.',
            'code': 'coach_pending'
        }), 403

    # Conta pendente de verificação por email (só quando a verificação está ligada).
    if _email_verification_enabled() and int(user.get('email_verified') or 0) == 0:
        _issue_verification(user['id'], email, user['username'])
        return jsonify({
            'error': 'Confirme seu email para entrar. Enviamos um novo código.',
            'code': 'email_unverified', 'email': email,
        }), 403

    touch_activity(user['id'])   # registra atividade + reseta o ciclo de win-back
    token = generate_token(user['id'], user['role'])
    return jsonify({
        'token':    token,
        'user_id':  user['id'],
        'username': user['username'],
        'role':     user['role'],
    })


@app.route('/auth/me', methods=['GET'])
@require_auth
def me():
    coach_id  = g.user.get('coach_id')
    coach_username = None
    if coach_id:
        coach_row = get_user_by_id(coach_id)
        if coach_row:
            coach_username = coach_row['username']
    quota = get_quota_status(g.user['id'])
    return jsonify({
        'user_id':              g.user['id'],
        'username':             g.user['username'],
        'email':                g.user['email'],
        'role':                 g.user['role'],
        'coach_id':             coach_id,
        'coach_username':       coach_username,
        'plan':                 quota['plan'],
        'tournaments_used':     quota['tournaments_used'],
        'ai_calls_used':        quota['ai_calls_used'],
        'plan_limits':          quota['limits'],
        # Stripe: current_period_end (próxima cobrança / fim do acesso se cancelado).
        # A página de assinatura mostrava "—" porque o campo nunca saía daqui.
        'plan_expires_at':      quota.get('plan_expires_at'),
        'whatsapp_phone':          g.user.get('whatsapp_phone'),
        'digest_subscribed':       bool(g.user.get('digest_subscribed', 0)),
        'profile_completed_at':    g.user.get('profile_completed_at'),
        'onboarding_completed':    bool(g.user.get('onboarding_completed', 0)),
    })


@app.route('/auth/update-email', methods=['POST'])
@require_auth
def update_email():
    from database.repositories import update_user_email
    d = request.get_json(silent=True) or {}
    new_email = (d.get('email') or '').strip().lower()
    current_pw = d.get('current_password', '')
    if not new_email or '@' not in new_email:
        return jsonify({'error': 'E-mail inválido'}), 400
    result = update_user_email(g.user_id, new_email, current_pw)
    if result == 'wrong_password':
        return jsonify({'error': 'Senha incorreta'}), 403
    if result == 'email_taken':
        return jsonify({'error': 'E-mail já cadastrado'}), 409
    return jsonify({'ok': True, 'email': new_email})


@app.route('/auth/change-password', methods=['POST'])
@require_auth
def change_password():
    from database.repositories import change_user_password
    d = request.get_json(silent=True) or {}
    current_pw = d.get('current_password', '')
    new_pw     = d.get('new_password', '')
    if len(new_pw) < 8:
        return jsonify({'error': 'A nova senha deve ter pelo menos 8 caracteres'}), 400
    if not change_user_password(g.user_id, current_pw, new_pw):
        return jsonify({'error': 'Senha atual incorreta'}), 403
    return jsonify({'ok': True})


@app.route('/auth/forgot-password', methods=['POST'])
@limiter.limit("5 per hour")
def forgot_password():
    """Dispara o código de redefinição de senha por email. Resposta SEMPRE genérica
    (200) — não vaza quais emails existem (evita enumeração). Só envia de fato se o
    email existir e houver SMTP configurado; reusa as colunas do 2FA de cadastro."""
    d = request.get_json(silent=True) or {}
    email = (d.get('email') or '').strip().lower()
    generic = jsonify({'ok': True})
    if not email or not _email_verification_enabled():
        return generic, 200
    user = get_user_by_email(email)
    if user:
        try:
            from datetime import datetime, timedelta
            code = _gen_verification_code()
            expires = (datetime.utcnow() + timedelta(minutes=_PASSWORD_RESET_TTL_MIN)).strftime("%Y-%m-%d %H:%M:%S")
            set_verification_code(user['id'], code, expires)
            send_password_reset_email(email, user.get('username', ''), code, _PASSWORD_RESET_TTL_MIN)
        except Exception:
            log.exception("forgot-password: falha ao emitir reset para %s", email)
    return generic, 200


@app.route('/auth/reset-password', methods=['POST'])
@limiter.limit("10 per hour")
def reset_password():
    """Redefine a senha com o código enviado por email. Não revela se o email existe:
    'not_found' vira o mesmo 'código inválido'."""
    from database.repositories import reset_password_with_code
    d = request.get_json(silent=True) or {}
    email  = (d.get('email') or '').strip().lower()
    code   = (d.get('code') or '').strip()
    new_pw = d.get('new_password') or ''
    if len(new_pw) < 8:
        return jsonify({'error': 'A nova senha deve ter pelo menos 8 caracteres', 'code': 'weak'}), 400
    if not email or not code:
        return jsonify({'error': 'Código inválido', 'code': 'invalid'}), 400
    res = reset_password_with_code(email, code, new_pw)
    st = res.get('status')
    if st == 'ok':
        return jsonify({'ok': True})
    errmap = {
        'expired':  ('O código expirou. Solicite um novo.', 'expired', 400),
        'too_many': ('Muitas tentativas. Solicite um novo código.', 'too_many', 429),
    }
    # not_found e invalid caem no genérico "código inválido" (não vaza inexistência do email)
    msg, ecode, http = errmap.get(st, ('Código inválido', 'invalid', 400))
    return jsonify({'error': msg, 'code': ecode}), http


@app.route('/student/coach', methods=['DELETE'])
@require_auth
def unlink_coach():
    from database.repositories import unlink_student_coach, check_password
    if g.role == 'coach':
        return jsonify({'error': 'Coaches não possuem vínculo de aluno'}), 400
    d = request.get_json(silent=True) or {}
    password = d.get('password', '')
    if not password:
        return jsonify({'error': 'Senha obrigatória para remover vínculo'}), 400
    if not check_password(g.user_id, password):
        return jsonify({'error': 'Senha incorreta'}), 403
    unlink_student_coach(g.user_id)
    return jsonify({'ok': True})


# ── Análise + persistência ────────────────────────────────────────────────────

@app.route('/analyze', methods=['POST'])
@require_auth
@limiter.limit("30 per hour")
def analyze():
    try:
        return _analyze_impl()
    except Exception as e:
        log.exception("unhandled error in /analyze for user %s", g.user_id)
        return jsonify({'error': f'Erro ao processar arquivo: {type(e).__name__}: {e}'}), 500


def _apply_tournament_summary(user_id, content, filename):
    """Aplica um Tournament Summary (ACR/WPN '.ots' JSON ou PokerStars texto) a um torneio JÁ
    IMPORTADO. Casa por Tournament #, acha o hero, e atualiza place/prize/profit/buy_in +
    field_size/prize_pool (só o summary traz o tamanho do field). Sem inventar: os números vêm do
    arquivo real. Devolve (payload, http_status); (None, None) se o conteúdo NÃO for um summary
    reconhecido (aí o chamador segue como hand history)."""
    from leaklab.parser import (parse_acr_results, parse_pokerstars_summary,
                                 parse_ggpoker_summary)
    from database.repositories import get_tournament, update_tournament_financials

    # ACR (.ots JSON) OU PokerStars (texto) OU GGPoker (texto). Cada parser devolve None se não for
    # o seu formato — a ordem importa (PS antes de GG, pq o GG casa 'Tournament #' genérico).
    res = parse_acr_results(content)
    ps  = None if res else parse_pokerstars_summary(content)
    gg  = None if (res or ps) else parse_ggpoker_summary(content)
    sm  = res or ps or gg
    if not sm:
        return None, None

    tid  = sm['tournament_id']
    tour = get_tournament(user_id, tid)
    if not tour:
        return {'kind': 'summary', 'tournament_id': tid,
                'error': f'Torneio {tid} não encontrado. Importe as mãos (hand history) desse '
                         f'torneio antes de subir o resultado.'}, 404
    hero = tour.get('hero')

    field_size = sm.get('player_count')
    prize_pool = sm.get('prize_pool')
    re_entries_out = None   # só o GG reporta re-entradas hoje

    if res:
        # ── ACR: premiação por jogador no arquivo (soma re-entradas do hero) ──
        mine = [f for f in res['finishes'] if hero and f['player'] == hero]
        if not mine:
            return {'kind': 'summary', 'tournament_id': tid,
                    'error': f'O jogador "{hero}" não aparece no arquivo de resultados.'}, 422
        prize = round(sum(f['prize'] for f in mine), 2)
        places = [f['place'] for f in mine if f['place'] is not None]
        place = min(places) if places else None
        buy_in = _summary_buyin_from_filename(filename)
        if buy_in is None:
            buy_in = tour.get('buy_in')
        if buy_in is None and prize_pool and field_size:
            try:
                buy_in = round(float(prize_pool) / float(field_size), 2)
            except Exception:
                buy_in = None
        profit = round(prize - buy_in, 2) if buy_in is not None else None
        started_at = None
    elif ps:
        # ── PokerStars: field_size + prize_pool + buy-in vêm do summary; place do "You finished
        # in Nth"; prize da linha do hero na ordem de colocação (0 se não cravou ITM) ──
        place = ps.get('hero_place')
        mine = [f for f in ps['finishes'] if hero and f['player'] == hero]
        if place is None and mine:
            place = min(f['place'] for f in mine if f['place'] is not None)
        buy_in = ps.get('buy_in') or tour.get('buy_in')
        # prize: só quando o hero aparece na lista (aí um valor $ = ITM, ausência = 0). Sem o hero
        # na lista, não sobrescreve (mantém o que o HH tiver).
        if mine:
            prize = round(sum(f['prize'] for f in mine), 2)
            profit = round(prize - buy_in, 2) if buy_in is not None else None
        else:
            prize = tour.get('prize')
            profit = tour.get('profit')
        started_at = ps.get('started_at')
    else:
        # ── GGPoker: place do "You finished the tournament in Nth"; prize do "received a total of
        # $X" (inclui re-entradas/bounties, dado autoritativo); buy-in do summary (soma do PKO) ──
        place = gg.get('hero_place')
        # custo REAL = buy-in de 1 entrada × total de entradas (1 + re-entradas). Sem coluna de
        # "total investido", grava esse total no buy_in → profit e ROI (soma de buy_in) ficam certos.
        buy_in_single = gg.get('buy_in') or tour.get('buy_in')
        re_entries_out = int(gg.get('re_entries') or 0)
        entries = 1 + re_entries_out
        buy_in = round(buy_in_single * entries, 2) if buy_in_single is not None else tour.get('buy_in')
        prize = gg.get('hero_prize')
        if prize is not None:
            profit = round(prize - buy_in, 2) if buy_in is not None else None
        else:
            prize = tour.get('prize')
            profit = tour.get('profit')
        started_at = gg.get('started_at')

    update_tournament_financials(user_id, tid, buy_in=buy_in, prize=prize, profit=profit,
                                 place=place, field_size=field_size, prize_pool=prize_pool,
                                 started_at=started_at, re_entries=re_entries_out)

    # Colocacao de CADA jogador — e o que habilita ICM real em mesa final de MTT (o gate antigo,
    # `field_size <= 9`, nunca abria ali). Ver `leaklab.mesa_final`. So vale para importacao nova:
    # o texto do resumo nao e guardado, entao torneio antigo nao da backfill.
    _finishes = (res or ps or gg or {}).get('finishes') or []
    _n_finishes = 0
    if _finishes:
        try:
            from database.repositories import get_tournament, save_tournament_finishes
            _t = get_tournament(user_id, tid)
            if _t:
                _n_finishes = save_tournament_finishes(_t['id'], _finishes)
        except Exception as _e:
            # Nao pode derrubar a importacao do resumo (o financeiro ja foi gravado). Sem
            # colocacoes o ICM real fica desligado, que e o comportamento seguro.
            app.logger.warning('colocacoes nao gravadas para %s: %s', tid, _e)
    return {'kind': 'summary', 'tournament_id': tid, 'hero': hero, 'place': place, 'prize': prize,
            'buy_in': buy_in, 'profit': profit, 'field_size': field_size,
            'prize_pool': prize_pool, 're_entries': re_entries_out,
            'finishes_gravadas': _n_finishes}, 200


@app.route('/tournament/results', methods=['POST'])
@require_auth
def tournament_results():
    """Complementa os dados de um torneio com o arquivo de RESULTADOS (Tournament Summary).
    Dois formatos: ACR/WPN '.ots' (JSON) e PokerStars (texto)."""
    content  = _extract_content(request)
    filename = _extract_upload_filename(request)
    if not content:
        return jsonify({'error': 'Conteúdo ausente'}), 400
    payload, status = _apply_tournament_summary(g.user_id, content, filename)
    if status is None:
        return jsonify({'error': 'Arquivo de resultados não reconhecido. Esperado o Tournament '
                                 'Summary do PokerStars (.txt) ou do ACR/WPN (.ots).'}), 422
    return jsonify(payload), status


def _analyze_impl():
    # A quota é checada só DEPOIS de sabermos se é torneio novo (ver `existing` abaixo):
    # re-import/merge do mesmo T# (PokerStars quebra torneio longo em arquivos por dia)
    # não deve consumir nem ser barrado pela quota.
    content = _extract_content(request)
    if not content:
        return jsonify({'error': 'Conteúdo ausente'}), 400
    upload_filename = _extract_upload_filename(request)   # ACR: buy-in vem daqui

    # A prescrição ANTES do upload: é o termo de comparação do gate anti-ruído da notificação
    # pós-análise (spec cobranca-proximo-passo.md §3 — só notifica se o diagnóstico MUDOU).
    # Lida antes do parse porque depois do processamento o currículo já é o novo.
    _missao_antes = None
    try:
        from leaklab.proximo_passo import montar_proximo_passo as _mpp
        _missao_antes = ((_mpp(g.user_id).get('passo') or {}).get('titulo'))
    except Exception:
        pass

    try:
        hands = parse_pokerstars_file_from_text(content)
    except Exception as e:
        log.exception("parse error in /analyze")
        return jsonify({'error': 'Arquivo inválido ou formato não suportado'}), 422

    if not hands:
        # Sem mãos: pode ser um Tournament Summary jogado no importador principal (fluxo natural do
        # usuário — ele não distingue os tipos de arquivo). Detecta e roteia pro complemento do
        # torneio em vez de dar "Nenhuma mão encontrada".
        payload, status = _apply_tournament_summary(g.user_id, content, upload_filename)
        if status is not None:
            return jsonify(payload), status
        return jsonify({'error': 'Nenhuma mão encontrada'}), 422

    results, hand_results, errors = _analyze_hands(
        hands, field_size=_field_size_for(g.user_id, hands[0].tournament_id),
        colocacoes=_colocacoes_for(g.user_id, hands[0].tournament_id))
    if not results:
        return jsonify({'error': 'Nenhuma decisão encontrada'}), 422

    metrics = build_session_metrics(results)
    leaks   = correlate_leaks(results)

    hero          = hands[0].hero or 'Hero'
    tournament_id = hands[0].tournament_id or ''
    # Sem identificador de torneio (ex.: cash game ou formato sem "Tournament #"):
    # não persistir — um tournament_id vazio quebra abrir/excluir no frontend
    # (URL /tournament/ sem id). A plataforma é focada em torneios (MTT/SNG).
    if not str(tournament_id).strip():
        return jsonify({'error': 'Hand history sem identificador de torneio. '
                                 'Apenas torneios (MTT/SNG) são suportados — cash games '
                                 'e formatos sem "Tournament #" não podem ser importados.'}), 422
    site          = _detect_site(hands[0].raw_text if hasattr(hands[0],'raw_text') else '')
    played_at  = _extract_date(hands[0].raw_text if hasattr(hands[0],'raw_text') else '')
    raw_full   = '\n'.join(h.raw_text for h in hands if hasattr(h,'raw_text'))
    financials = _extract_financials(raw_full, hero, site, upload_filename)
    t_name     = _extract_tournament_name(raw_full, site, financials.get('buy_in'))

    # Torneio já importado: o PokerStars QUEBRA a HH de um torneio longo em arquivos por DATA (mesmo
    # T#, nomes/dias diferentes). Em vez de rejeitar, MESCLAR: re-parseia o raw já salvo + o novo,
    # dedup por hand_id, e re-analisa a UNIÃO (save_decisions abaixo faz DELETE+insert → substitui o
    # torneio com a união consolidada). Só rejeita se o arquivo não trouxer NENHUMA mão nova.
    existing = get_tournament(g.user_id, tournament_id)
    # Quota só vale pra torneio NOVO. Re-import do mesmo T# (merge) não consome nem é barrado.
    if not existing:
        quota_err = _check_upload_quota(g.user_id)
        if quota_err:
            return quota_err
    _merged = False
    _new_hands_n = 0
    if existing:
        _existing_raw = existing.get('raw_text') or ''
        try:
            _existing_hands = parse_pokerstars_file_from_text(_existing_raw) if _existing_raw else []
        except Exception:
            _existing_hands = []
        _existing_ids = {str(getattr(h, 'hand_id', '') or '') for h in _existing_hands}
        _new_hands = [h for h in hands
                      if (str(getattr(h, 'hand_id', '') or '') and
                          str(getattr(h, 'hand_id', '') or '') not in _existing_ids)]
        if not _new_hands:
            return jsonify({
                'error': f'Torneio {tournament_id} já foi importado (este arquivo não traz mãos novas).',
                'duplicate': True,
                'tournament_id': tournament_id,
            }), 409
        # União ORDENADA por hand_id (o # global do PokerStars é monotônico no tempo) — senão a sequência
        # das mãos segue a ordem de IMPORT, não a cronológica (importar o dia 2 antes do dia 1 embaralha).
        def _hand_sort_key(h):
            _hid = str(getattr(h, 'hand_id', '') or '')
            return (0, int(_hid)) if _hid.isdigit() else (1, _hid)
        hands = sorted(_existing_hands + _new_hands, key=_hand_sort_key)
        results, hand_results, errors = _analyze_hands(hands)
        if not results:
            return jsonify({'error': 'Nenhuma decisão na união das mãos'}), 422
        metrics    = build_session_metrics(results)
        leaks      = correlate_leaks(results)
        raw_full   = '\n'.join(h.raw_text for h in hands if hasattr(h, 'raw_text'))
        financials = _extract_financials(raw_full, hero, site, upload_filename)
        t_name     = _extract_tournament_name(raw_full, site, financials.get('buy_in'))
        _merged, _new_hands_n = True, len(_new_hands)
        log.info("analyze: MESCLANDO torneio %s (+%d mãos novas, %d no total)",
                 tournament_id, _new_hands_n, len(hands))

    # Persistir
    t_db_id = save_tournament(
        user_id=g.user_id,
        tournament_id=tournament_id,
        hero=hero,
        metrics=metrics,
        site=site,
        played_at=played_at,
        result='itm' if financials.get('prize') else None,
        place=financials.get('place'),
        buy_in=financials.get('buy_in'),
        prize=financials.get('prize'),
        profit=financials.get('profit'),
        raw_text=raw_full,
        tournament_name=t_name,
        is_pko=any(getattr(h, 'is_pko', False) for h in hands) if hands else False,
    )
    save_decisions(t_db_id, results)

    # HUD: computa e persiste os perfis de comportamento dos oponentes deste torneio
    # (alimenta as Fases 2-3: perfil do vilão + exploit no card). Bônus — nunca bloqueia
    # o /analyze; try/except garante que um erro aqui não derruba o upload.
    # CoinPoker troca o hash do jogador a CADA MÃO → sem identidade entre mãos, o HUD é inútil
    # E o cálculo explode (~milhares de "jogadores" de 1 mão → 1 conexão PG cada → timeout do
    # worker → "Failed to fetch"). SystemExit do timeout nem é pego pelo except Exception abaixo.
    # Guard genérico por contagem cobre qualquer site futuro com anonimização por-mão.
    _profiles = {}
    if site != 'coinpoker':
        try:
            from leaklab.opponent_stats import build_profiles as _build_profiles
            _profiles = _build_profiles(hands)
        except Exception:
            log.exception("opponent_profiles: build falhou (não bloqueia o /analyze)")
    # Guard anti-explosão (por PROPORÇÃO, não conta absoluta): anonimização por-mão faz os nomes
    # únicos crescerem ~linear com as mãos (CoinPoker ~4,4 únicos/mão); MTT real repete oponentes
    # na mesa (~0,2). Só pula quando é claramente por-mão, pra NÃO punir run profunda de PS/GG.
    _per_hand_anon = len(_profiles) > 60 and len(_profiles) > 3 * max(1, len(hands))
    if _profiles and not _per_hand_anon:
        try:
            from database.repositories import upsert_opponent_profile as _upsert_prof
            for _pname, _prof in _profiles.items():
                if _pname and _pname != hero:
                    _upsert_prof(t_db_id, _pname, _prof)
        except Exception:
            log.exception("opponent_profiles: upsert falhou (não bloqueia o /analyze)")
    # Só conta na quota torneio NOVO; re-import/merge do mesmo T# não consome.
    if not existing:
        try:
            increment_tournament_count(g.user_id)
        except Exception:
            pass

    # Preencher gto_label preflop via ranges estáticos + reconciliar label vs gto_label
    def _preflop_sync_and_reconcile(tid: int) -> None:
        import logging as _logging
        _log = _logging.getLogger(__name__)
        try:
            import sys as _sys
            from pathlib import Path as _Path
            _scripts = str(_Path(__file__).resolve().parent.parent / 'scripts')
            if _scripts not in _sys.path:
                _sys.path.insert(0, _scripts)
            from sync_gto_labels_from_ranges import sync_tournament
            sync_tournament(tid)
        except Exception as _e:
            _log.exception("preflop_sync FAILED tournament_id=%s err=%s", tid, _e)
        try:
            # `only_ids=[]`: NÃO re-deriva label nenhum. O `sync_tournament` acima já reconciliou
            # exatamente as linhas cujo `gto_label` ele mudou; o resto acabou de sair do motor,
            # com um veredito mais completo do que o `gto_label` sozinho produz. Esta chamada
            # segue valendo pelo alinhamento de score e pelo recálculo dos percentuais, que são
            # do torneio inteiro. Ver reconcile_tournament_labels.
            n = reconcile_tournament_labels(tid, only_ids=[])
            _log.info("preflop_sync_and_reconcile done tournament_id=%s reconciled=%d", tid, n)
        except Exception as _e:
            _log.exception("reconcile FAILED tournament_id=%s err=%s", tid, _e)

    threading.Thread(
        target=_preflop_sync_and_reconcile,
        args=(t_db_id,),
        daemon=True,
        name='label-reconcile',
    ).start()

    # Enfileirar spots postflop novos para o solver GTO em background
    threading.Thread(
        target=_enqueue_postflop_spots,
        args=(results, t_db_id),
        daemon=True,
        name='gto-upload-enqueue',
    ).start()

    # Auto-enfileirar análise GTO para todas as mãos postflop do torneio
    threading.Thread(
        target=_auto_queue_gto_for_tournament,
        args=(t_db_id, results, g.user_id),
        daemon=True,
        name='gto-hand-autoqueue',
    ).start()

    # Warm-up cache GW pra spots preflop multiway (squeeze, cold-callers) —
    # spots fora do escopo HU do lookup_gto local. Antecipa a captura pra
    # que o Replayer abra com hand_freqs corretas sem cache miss.
    threading.Thread(
        target=_warmup_gw_multiway,
        args=(hands, hero),
        daemon=True,
        name='gw-multiway-warmup',
    ).start()

    # Auto-capture ON-DEMAND de spots preflop NULL cobríveis (faces_squeeze/vs_3bet/
    # vs_rfi): busca o spot CANÔNICO no GTO Solver, injeta no master de ranges e
    # re-grada as decisões — fecha os NULLs organicamente conforme spots recorrem.
    # Tracking evita re-buscar no-solution genuíno; fast-fail não trava o servidor.
    def _autocapture_preflop(tid: int):
        try:
            from leaklab.preflop_autocapture import run_autocapture
            run_autocapture(tid)
        except Exception as _e:
            _log.warning("autocapture preflop FAILED tournament_id=%s err=%s", tid, _e)

    threading.Thread(
        target=_autocapture_preflop,
        args=(t_db_id,),
        daemon=True,
        name='preflop-autocapture',
    ).start()

    # Recalcula ELO do user — processa todas as decisoes em ordem cronologica.
    # Snapshot inserido em player_elo_history. Idempotente (snapshot novo a
    # cada upload, gera serie temporal pro grafico de evolucao).
    threading.Thread(
        target=_recompute_user_elo,
        args=(g.user_id,),
        daemon=True,
        name='elo-recompute',
    ).start()

    # Explicações LLM se solicitado
    if request.args.get('explain', '').lower() == 'true':
        all_decisions = [d for h in hand_results.values() for d in h['decisions']]
        explanations  = explain_decisions(all_decisions)
        from leaklab.llm_explainer import _key
        for hand in hand_results.values():
            for d in hand['decisions']:
                d['explanation'] = explanations.get(_key(d), '')

    # ── O contrato pós-upload (spec §3): a prescrição nasce AQUI, na tela do prejuízo ──
    # O bloco vai SEMPRE (a tela de resultado mostra a dor e o remédio juntos); a NOTIFICAÇÃO
    # só quando o diagnóstico mudou — evento, não calendário. `missao_antes` foi lida no início
    # do processamento; o get_training_proof que roda dentro de missions_with_state é também o
    # detector de reabertura, então "mudou" cobre leak novo no topo E reaberto.
    _passo_pos_upload = None
    try:
        from leaklab.proximo_passo import montar_proximo_passo
        _pp = montar_proximo_passo(g.user_id, origem='pos_upload')
        _passo_pos_upload = _pp.get('passo')
        _missao_depois = (_passo_pos_upload or {}).get('titulo')
        if _passo_pos_upload and _missao_depois != _missao_antes:
            from database.repositories import create_notification
            create_notification(g.user_id, 'treino_prescrito',
                                {'passo': _passo_pos_upload},
                                _passo_pos_upload.get('cta_url'))
    except Exception:
        log.exception('proximo passo pós-upload falhou (user=%s)', g.user_id)

    import uuid
    return jsonify({
        'session_id':       str(uuid.uuid4()),
        'proximo_passo':    _passo_pos_upload,
        'tournament_db_id': t_db_id,
        'hero':             hero,
        'tournament_id':    tournament_id,
        'played_at':        played_at,
        'financials':       financials,
        'total_hands':      len(hands),
        'parse_errors':     len(errors),
        'metrics':          metrics,
        'leaks':            leaks,
        'hands':            hand_results,
        'merged':           _merged,        # torneio já existia → mesclou as mãos novas (HH dividida por dia)
        'new_hands':        _new_hands_n,
    })


@app.route('/analyze/tournament-summary', methods=['POST'])
@require_auth
@limiter.limit("20 per hour")
def tournament_summary():
    # Pro (29/08, decisão do dono): a análise IA do torneio é insight avançado. O gate mora
    # AQUI, não só no botão — cadeado de front sem porta de back é decoração.
    gate = _check_advanced_insights(g.user_id)
    if gate:
        return gate
    try:
        body = request.get_json(silent=True) or {}
        t_db_id = body.get('tournament_id')  # ID interno do banco (int)

        if t_db_id:
            # Buscar decisões já salvas no banco — não precisa do arquivo
            from database.repositories import get_tournament_by_db_id
            t = get_tournament_by_db_id(g.user_id, int(t_db_id))
            if not t:
                return jsonify({'error': 'Torneio não encontrado'}), 404

            decisions = get_decisions(int(t_db_id))
            if not decisions:
                return jsonify({'error': 'Nenhuma decisão encontrada para este torneio'}), 400

            hero = t.get('hero', 'Hero') or 'Hero'
            n_hands = t.get('hand_count', len(decisions))

            # Converter decisões do banco para o formato esperado pelo generate_tournament_summary
            results = [{
                'evaluation': {
                    'label':        d.get('label','standard'),
                    'mistakeScore': float(d.get('score', 0)),
                },
                'action_taken': d.get('action_taken',''),
                'best_action':  d.get('best_action',''),
                'street':       d.get('street','preflop'),
                'hand_id':      d.get('hand_id',''),
                'context': {
                    'icmPressure': d.get('icm_pressure','low'),
                    'mRatio':      float(d.get('m_ratio', 10) or 10),
                },
            } for d in decisions]

        else:
            # Fallback: aceitar conteúdo bruto (compatibilidade)
            raw = _extract_content(request)
            if not raw:
                return jsonify({'error': 'Envie tournament_id ou o conteúdo do arquivo'}), 400
            hands = parse_pokerstars_file_from_text(raw)
            results, _, _ = _analyze_hands(hands)
            if not results:
                return jsonify({'error': 'Nenhuma decisão encontrada'}), 400
            hero = hands[0].hero or 'Hero'
            n_hands = len(hands)
            t_db_id = None

        # Se já existe summary salvo, retornar sem chamar LLM
        if t_db_id:
            existing_summary = t.get('llm_summary')
            if existing_summary:
                return jsonify({
                    'hero':            hero,
                    'summary':         existing_summary,
                    'total_decisions': len(results),
                    'cached':          True,
                })

        ai_err = _check_ai_quota(g.user_id)
        if ai_err:
            return ai_err

        summary = generate_tournament_summary(results, n_hands, hero)
        try:
            increment_ai_calls(g.user_id)
        except Exception:
            pass

        # Persistir
        if t_db_id:
            update_llm_summary(int(t_db_id), summary)

        return jsonify({
            'hero':            hero,
            'summary':         summary,
            'total_decisions': len(results),
        })

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


# ── Histórico e evolução ──────────────────────────────────────────────────────

@app.route('/history/tournaments', methods=['GET'])
@require_auth
def history_tournaments():
    limit = int(request.args.get('limit', 50))
    tournaments = get_tournaments(g.user_id, limit)
    reviewed_ids = get_reviewed_tournament_ids(g.user_id)
    for t in tournaments:
        for field in ('played_at', 'imported_at'):
            val = t.get(field)
            if val is not None and not isinstance(val, str):
                t[field] = str(val)[:10]
        t['coach_reviewed'] = t['id'] in reviewed_ids
    return jsonify({'tournaments': tournaments})


@app.route('/history/tournament/<tournament_id>', methods=['GET'])
@require_auth
def history_tournament(tournament_id):
    t = get_tournament(g.user_id, tournament_id)
    if not t:
        return jsonify({'error': 'Torneio não encontrado'}), 404
    decisions = get_decisions(t['id'])
    annotated = {a['decision_id'] for a in get_annotations_for_decisions([d['id'] for d in decisions])}
    for d in decisions:
        d['has_annotation'] = d['id'] in annotated
        d['note'] = _enrich_note(d)
        # A lista servia o veredito sem dizer se ele tem direito a linguagem de GTO. Mesmo gate
        # do /replay, mesma funcao — a alternativa era uma terceira porta para o mesmo fato.
        d['verdict_source'] = _procedencia_da_linha(d)
        d['verdict_has_cost'] = _tem_custo_da_linha(d)
        d['pode_falar_como_gto'] = _pode_falar_como_gto_da_linha(d)
    return jsonify({'tournament': t, 'decisions': decisions})


@app.route('/history/tournament/<tournament_id>/phase_analysis', methods=['GET'])
@require_auth
def history_tournament_phase_analysis(tournament_id):
    t = get_tournament(g.user_id, tournament_id)
    if not t:
        return jsonify({'error': 'Torneio não encontrado'}), 404
    return jsonify({'phase_analysis': get_phase_analysis(t['id'])})


@app.route('/history/tournament/<tournament_id>/texture_analysis', methods=['GET'])
@require_auth
def history_tournament_texture_analysis(tournament_id):
    t = get_tournament(g.user_id, tournament_id)
    if not t:
        return jsonify({'error': 'Torneio não encontrado'}), 404
    return jsonify({'texture_analysis': get_texture_analysis(t['id'])})


@app.route('/history/tournament/<tournament_id>/narrative', methods=['GET'])
@require_auth
def history_tournament_narrative(tournament_id):
    t = get_tournament(g.user_id, tournament_id)
    if not t:
        return jsonify({'error': 'Torneio não encontrado'}), 404

    decisions  = get_decisions(t['id'])
    phases     = get_phase_analysis(t['id'])
    ctx        = _build_narrative_context(t, decisions, phases)
    narrative  = generate_tournament_narrative(t['id'], ctx)

    std = t.get('standard_pct') or 0
    quality_level = 'solid' if std >= 75 else 'regular' if std >= 60 else 'poor'

    return jsonify({'narrative': narrative, 'quality_level': quality_level})


def _build_narrative_context(tourn: dict, decisions: list, phases: list) -> dict:
    from collections import Counter, defaultdict
    if not decisions:
        return {}

    labels = Counter(d.get('label', 'standard') for d in decisions)
    total  = len(decisions)

    spot_scores = defaultdict(list)
    for d in decisions:
        key = f"{d.get('street', '?')}/{d.get('best_action', '?')}"
        spot_scores[key].append(d.get('score', 0) or 0)

    top_leaks = sorted(
        [(k, round(sum(v) / len(v), 3), len(v)) for k, v in spot_scores.items() if len(v) >= 2],
        key=lambda x: x[1], reverse=True
    )[:3]

    icm_groups = defaultdict(list)
    for d in decisions:
        icm = d.get('icm_pressure') or 'low'
        icm_groups[icm].append(d.get('score', 0) or 0)

    icm_breakdown = {
        level: {'count': len(scores), 'avg': round(sum(scores) / len(scores), 4)}
        for level, scores in icm_groups.items()
    }

    worst_phase = max(phases, key=lambda p: p.get('avg_score', 0)) if phases else None

    return {
        'standard_pct':    tourn.get('standard_pct') or 0,
        'avg_score':       tourn.get('avg_score') or 0,
        'total_decisions': total,
        'label_counts':    dict(labels),
        'top_leaks':       top_leaks,
        'icm_breakdown':   icm_breakdown,
        'worst_phase':     worst_phase,
    }


@app.route('/history/tournaments/compare', methods=['GET'])
@require_auth
def history_tournaments_compare():
    raw = request.args.get('ids', '')
    ids = [i.strip() for i in raw.split(',') if i.strip()]
    if len(ids) < 2 or len(ids) > 4:
        return jsonify({'error': 'Selecione entre 2 e 4 torneios'}), 400

    items = get_tournaments_comparison(g.user_id, ids)
    if len(items) < 2:
        return jsonify({'error': 'Torneios não encontrados'}), 404

    narrative = generate_comparison_narrative(items)
    return jsonify({'items': items, 'narrative': narrative})


@app.route('/history/tournament/<tournament_id>/report.pdf', methods=['GET'])
@require_auth
def history_tournament_report_pdf(tournament_id):
    t = get_tournament(g.user_id, tournament_id)
    if not t:
        return jsonify({'error': 'Torneio não encontrado'}), 404

    decisions = get_decisions(t['id'])
    phases    = get_phase_analysis(t['id'])
    hero      = t.get('hero', 'Hero')

    from flask import Response
    try:
        html = build_html_report(t, decisions, phases, hero)
    except Exception:
        import logging, traceback as _tb
        logging.getLogger('report').error('build_html_report falhou t=%s\n%s', tournament_id, _tb.format_exc())
        return jsonify({'error': 'Falha ao gerar o relatório'}), 500

    safe_id = tournament_id.replace(' ', '_')[:40]
    try:
        pdf_bytes = generate_pdf_bytes(html)
        return Response(
            pdf_bytes,
            mimetype='application/pdf',
            headers={
                'Content-Disposition': f'attachment; filename="grindlab-report-{safe_id}.pdf"',
                'Cache-Control': 'no-store',
            }
        )
    except Exception:
        # WeasyPrint não disponível ou falhou (ex: libs GTK ausentes no Windows dev).
        # Loga o erro REAL pra diagnosticar (pydyf incompatível, lib faltando, etc.) antes do fallback.
        import logging, traceback as _tb
        logging.getLogger('report').warning('WeasyPrint falhou, fallback HTML t=%s\n%s', tournament_id, _tb.format_exc())
        return Response(
            html,
            mimetype='text/html',
            headers={
                'Content-Disposition': f'attachment; filename="grindlab-report-{safe_id}.html"',
                'Cache-Control': 'no-store',
            }
        )


@app.route('/history/evolution', methods=['GET'])
@require_auth
def history_evolution():
    from database.repositories import get_leak_ranking_gto_first
    days   = int(request.args.get('days', 30))
    last_n = int(request.args.get('last_n')) if request.args.get('last_n') else None
    leak_data = get_leak_ranking_gto_first(g.user_id, days, last_n=last_n)
    return jsonify({
        'evolution':    get_evolution_metrics(g.user_id, days, last_n=last_n, by_played=True),
        'leaks':        leak_data['leaks'],
        'leak_source':  leak_data['source'],
        'icm':          get_icm_performance(g.user_id, days),
    })


@app.route('/history/breakdown', methods=['GET'])
@require_auth
def history_breakdown():
    days = int(request.args.get('days', 90))
    return jsonify(get_breakdown(g.user_id, days))


@app.route('/metrics/player-stats', methods=['GET'])
@require_auth
def player_stats():
    days   = int(request.args.get('days', 90))
    last_n = int(request.args.get('last_n')) if request.args.get('last_n') else None
    stats = get_player_stats(g.user_id, days, last_n=last_n)
    # Flags direcionais (banda saudável/abaixo/acima vs referências MTT, gateados por amostra).
    from leaklab.opponent_stats import player_stat_flags
    stats['flags'] = player_stat_flags(stats)
    return jsonify(stats)


@app.route('/metrics/level', methods=['GET'])
@require_auth
def player_level():
    return jsonify(get_player_level(g.user_id))


@app.route('/player/ev-summary', methods=['GET'])
@require_auth
def player_ev_summary():
    """UX-1: hero do DashboardV2 — EV/100, tendência, % sólidas e top leaks por CUSTO."""
    from database.repositories import get_ev_summary
    return jsonify(get_ev_summary(g.user_id))


@app.route('/player/leak-roi', methods=['GET'])
@require_auth
def player_leak_roi():
    """Leaks rankeados por gto_label (critical/minor_deviation). Fallback para heurístico se sem dados GTO.
    Retorna {source: 'gto'|'heuristic', leaks: [...]} para o frontend exibir a fonte explicitamente.
    """
    from database.repositories import get_gto_leak_ranking
    days   = int(request.args.get('days', 90))
    last_n = int(request.args.get('last_n')) if request.args.get('last_n') else None
    leaks = get_gto_leak_ranking(g.user_id, days, last_n=last_n)
    if leaks:
        source = 'gto'
    else:
        leaks = get_leak_roi_impact(g.user_id, days, last_n=last_n)
        source = 'heuristic'
    return jsonify({'source': source, 'leaks': leaks})


@app.route('/player/ev-leaks', methods=['GET'])
@require_auth
def player_ev_leaks():
    """#24/#25 — leaks ranqueados por EV perdido (bb), por spot. Início do Leak
    Finder: prioriza pelo total de big blinds deixados na mesa, não por contagem."""
    from database.repositories import get_ev_leaks
    days   = int(request.args.get('days', 90))
    last_n = int(request.args.get('last_n')) if request.args.get('last_n') else None
    return jsonify(get_ev_leaks(g.user_id, days, last_n=last_n))


@app.route('/player/leak-finder', methods=['GET'])
@require_auth
def player_leak_finder():
    """#25 — Leak Finder consolidado: vazamentos priorizados por EV perdido (bb),
    com severidade e o top leak em destaque. Carro-chefe da síntese 'LeakLab'."""
    from database.repositories import get_consolidated_leak_report
    days   = int(request.args.get('days', 90))
    last_n = int(request.args.get('last_n')) if request.args.get('last_n') else None
    return jsonify(get_consolidated_leak_report(g.user_id, days, last_n=last_n))


@app.route('/player/pressure-profile', methods=['GET'])
@require_auth
def player_pressure_profile():
    """PERF-004 — Perfil de colapso técnico sob pressão ICM."""
    days = int(request.args.get('days', 90))
    return jsonify(get_pressure_profile(g.user_id, days))


@app.route('/player/confidence-drift', methods=['GET'])
@require_auth
def player_confidence_drift():
    """PERF-005 — Detecta sessões com possível tilt/drift de confiança."""
    days = int(request.args.get('days', 30))
    return jsonify(get_confidence_drift(g.user_id, days))


@app.route('/player/elo', methods=['GET'])
@require_auth
def player_elo():
    """
    Retorna ELO atual + histórico do jogador.

    Resposta:
      { user_id, overall: {elo, n_decisions, band_label, band_color},
        by_street: {preflop:{...}, flop:{...}, ...},
        total_decisions, calculated_at, bands, solver_elo, initial_elo,
        history: [{calculated_at, elo_overall, total_decisions}],
        delta_7d: float | null }   ← variacao nos ultimos 7 dias
    """
    from database.repositories import (
        get_latest_elo, get_elo_history, get_decisions_for_elo, insert_elo_snapshot,
    )
    from leaklab.elo_engine import compute_player_elo_from_decisions, snapshot_to_dict, BANDS, SOLVER_ELO, INITIAL_ELO

    from database.repositories import get_peak_elo
    latest = get_latest_elo(g.user_id)
    # Se nunca calculado, computa on-demand (1ª chamada por user) — forma recente
    if not latest:
        decisions = get_decisions_for_elo(g.user_id, last_n_tournaments=ELO_WINDOW_TOURNAMENTS)
        if decisions:
            snap = compute_player_elo_from_decisions(g.user_id, decisions)
            insert_elo_snapshot(snapshot_to_dict(snap))
            latest = get_latest_elo(g.user_id)
    peak_elo = get_peak_elo(g.user_id)

    history = get_elo_history(g.user_id, limit=180)  # ~6 meses

    # Delta 7 dias (compara latest com snapshot mais próximo de 7d atrás)
    delta_7d = None
    if latest and len(history) >= 2:
        import datetime
        try:
            now_ts = datetime.datetime.fromisoformat(str(latest['calculated_at']).replace('Z',''))
            target = now_ts - datetime.timedelta(days=7)
            best = None
            for h in history:
                try:
                    hts = datetime.datetime.fromisoformat(str(h['calculated_at']).replace('Z',''))
                except Exception:
                    continue
                if hts <= target:
                    best = h
                    break
            if best:
                delta_7d = round(float(latest['elo_overall']) - float(best['elo_overall']), 1)
        except Exception:
            pass

    from leaklab.elo_engine import band_full, next_band_for

    if not latest:
        # User novo sem decisions ainda
        ic, bl, bc = band_full(INITIAL_ELO)
        return jsonify({
            'user_id':         g.user_id,
            'overall': {
                'elo':         float(INITIAL_ELO),
                'n_decisions': 0,
                'band_icon':   ic,
                'band_label':  bl,
                'band_color':  bc,
            },
            'next_band':       next_band_for(INITIAL_ELO),
            'peak_elo':        None,
            'by_street':       {},
            'total_decisions': 0,
            'calculated_at':   None,
            'bands':           [{'threshold': t, 'icon': i, 'label': l, 'color': c} for (t, i, l, c) in BANDS],
            'solver_elo':      SOLVER_ELO,
            'initial_elo':     INITIAL_ELO,
            'history':         [],
            'delta_7d':        None,
            'decay_applied':   0.0,
            'weeks_inactive':  0.0,
            'by_stake':        {},
            'no_data':         True,
        })

    def _wrap(elo: float | None, n: int) -> dict | None:
        if elo is None: return None
        ic, bl, bc = band_full(float(elo))
        return {'elo': float(elo), 'n_decisions': int(n or 0),
                'band_icon': ic, 'band_label': bl, 'band_color': bc}

    by_street = {}
    for st, n_col in (('preflop','n_preflop'), ('flop','n_flop'),
                      ('turn','n_turn'), ('river','n_river')):
        v = _wrap(latest.get(f'elo_{st}'), latest.get(n_col) or 0)
        if v: by_street[st] = v

    # ── Decay por inatividade (Sprint 2) — aplicado na leitura, só no overall ──
    from leaklab.elo_engine import apply_inactivity_decay
    from database.repositories import get_last_activity_at
    raw_overall = float(latest['elo_overall'])
    weeks_inactive = 0.0
    last_act = get_last_activity_at(g.user_id)
    if last_act:
        import datetime
        try:
            la = datetime.datetime.fromisoformat(str(last_act).replace('Z', ''))
            weeks_inactive = max(0.0, (datetime.datetime.utcnow() - la).total_seconds() / (7 * 86400))
        except Exception:
            weeks_inactive = 0.0
    display_overall, decay_applied = apply_inactivity_decay(raw_overall, weeks_inactive)

    overall = _wrap(display_overall, latest.get('total_decisions') or 0)

    # ── ELO por faixa de stake (Sprint 2 #19) — recomputado na leitura ─────────
    by_stake = {}
    try:
        from database.repositories import get_decisions_for_elo_by_stake
        from leaklab.elo_engine import compute_player_elo_by_stake
        stake_snaps = compute_player_elo_by_stake(
            g.user_id, get_decisions_for_elo_by_stake(g.user_id, last_n_tournaments=ELO_WINDOW_TOURNAMENTS))
        for b in ('micro', 'low', 'mid', 'high'):
            s = stake_snaps.get(b)
            if s:
                by_stake[b] = {'elo': s.overall.elo, 'n_decisions': s.overall.n_decisions,
                               'band_icon': s.overall.band_icon, 'band_label': s.overall.band_label,
                               'band_color': s.overall.band_color}
    except Exception:
        by_stake = {}

    return jsonify({
        'user_id':         g.user_id,
        'overall':         overall,
        'next_band':       next_band_for(display_overall),
        'decay_applied':   decay_applied,                 # pts subtraídos do overall por inatividade
        'weeks_inactive':  round(weeks_inactive, 1),
        'by_stake':        by_stake,
        'peak_elo':        round(peak_elo, 1) if peak_elo is not None else None,
        'by_street':       by_street,
        'total_decisions': int(latest.get('total_decisions') or 0),
        'calculated_at':   str(latest.get('calculated_at') or ''),
        'window_tournaments': ELO_WINDOW_TOURNAMENTS,
        'bands':           [{'threshold': t, 'icon': i, 'label': l, 'color': c} for (t, i, l, c) in BANDS],
        'solver_elo':      SOLVER_ELO,
        'initial_elo':     INITIAL_ELO,
        'history':         [
            {'calculated_at': str(h['calculated_at']),
             'elo_overall':  round(float(h['elo_overall']), 1),
             'total_decisions': int(h['total_decisions'])}
            for h in history
        ],
        'delta_7d':        delta_7d,
    })


@app.route('/player/elo-curve', methods=['GET'])
@require_auth
def player_elo_curve():
    """
    Curva de ELO torneio-a-torneio em duas janelas:
      all_time: cumulativo desde o 1º torneio (jornada completa)
      recent:   últimos ELO_WINDOW_TOURNAMENTS torneios (forma atual)
    Cada série: [{tournament_id, elo, n_decisions}].
    """
    from leaklab.elo_engine import compute_elo_curve
    from database.repositories import get_decisions_for_elo_curve

    all_dec    = get_decisions_for_elo_curve(g.user_id)
    recent_dec = get_decisions_for_elo_curve(g.user_id, last_n_tournaments=ELO_WINDOW_TOURNAMENTS)

    return jsonify({
        'all_time':           compute_elo_curve(all_dec),
        'recent':             compute_elo_curve(recent_dec),
        'window_tournaments': ELO_WINDOW_TOURNAMENTS,
    })


@app.route('/player/evolution', methods=['GET'])
@require_auth
def player_evolution():
    """Relatório de evolução: EV perdido por torneio, spots mais caros e a matriz posição ×
    profundidade. Ranqueia por CUSTO — a validação estatística (melhorou?) vem do
    `/player/training-proof`, que mede taxa de erro. São perguntas diferentes de propósito."""
    from database.repositories import get_evolution_report
    return jsonify(get_evolution_report(g.user_id))


@app.route('/player/evolution/reports', methods=['GET'])
@require_auth
def player_evolution_reports():
    """Histórico de retratos datados. O valor de congelar é poder comparar julho com agosto —
    um número que muda sozinho não serve para comparação."""
    from database.repositories import list_evolution_reports
    return jsonify({'reports': list_evolution_reports(g.user_id)})


@app.route('/player/evolution/reports/<int:report_id>', methods=['GET'])
@require_auth
def player_evolution_report(report_id):
    from database.repositories import get_evolution_report_by_id
    r = get_evolution_report_by_id(g.user_id, report_id)
    if not r:
        return jsonify({'error': 'Relatório não encontrado'}), 404
    try:
        r['snapshot'] = json.loads(r['snapshot'])
    except Exception:
        pass
    return jsonify(r)


@app.route('/player/pending-gto-count', methods=['GET'])
@require_auth
def player_pending_gto_count():
    """Retorna contagem de spots com análise GTO ainda pendente para o usuário."""
    from database.repositories import get_user_pending_gto_count
    return jsonify({'pending': get_user_pending_gto_count(g.user_id)})


@app.route('/player/gto-quality', methods=['GET'])
@require_auth
def player_gto_quality():
    """Distribuição de gto_label para o jogador nos últimos 90 dias."""
    from database.repositories import get_gto_quality_breakdown
    last_n = int(request.args.get('last_n')) if request.args.get('last_n') else None
    return jsonify(get_gto_quality_breakdown(g.user_id, last_n=last_n))


@app.route('/player/gto-alignment', methods=['GET'])
@require_auth
def player_gto_alignment():
    """GTO alignment breakdown by street — preflop/flop/turn/river."""
    from database.repositories import get_gto_alignment_by_street
    last_n = int(request.args.get('last_n')) if request.args.get('last_n') else None
    return jsonify(get_gto_alignment_by_street(g.user_id, last_n=last_n))


@app.route('/player/gto-position', methods=['GET'])
@require_auth
def player_gto_position():
    """GTO alignment breakdown by position — BTN/CO/HJ/MP/UTG/SB/BB."""
    from database.repositories import get_gto_alignment_by_position
    last_n = int(request.args.get('last_n')) if request.args.get('last_n') else None
    return jsonify(get_gto_alignment_by_position(g.user_id, last_n=last_n))


@app.route('/player/gto-alignment-matrix', methods=['GET'])
@require_auth
def player_gto_alignment_matrix():
    """GTO alignment heatmap matrix — posicao (EP/MP/CO/BTN/SB/BB) x street."""
    from database.repositories import get_gto_alignment_matrix
    last_n = int(request.args.get('last_n')) if request.args.get('last_n') else None
    return jsonify(get_gto_alignment_matrix(g.user_id, last_n=last_n))


@app.route('/player/results-vs-gto', methods=['GET'])
@require_auth
def player_results_vs_gto():
    """Insight #5 'ganhei mas joguei errado' — erros de GTO escondidos atrás de
    vitorias (resultado != processo)."""
    from database.repositories import get_results_vs_gto
    last_n = int(request.args.get('last_n')) if request.args.get('last_n') else None
    return jsonify(get_results_vs_gto(g.user_id, last_n=last_n))



def _spot_sem_veredito(row: dict) -> bool:
    """O drill serviria este spot e a correcao devolveria 'uncovered'?

    Existe porque a SELECAO usava o `gto_label` GRAVADO no import e a CORRECAO faz uma consulta
    AO VIVO — e as duas discordam. O jogador recebia um exercicio, respondia, e levava "fora da
    cobertura" sem acao recomendada. Reportado com dois exemplos, de causas diferentes: mao fora
    da range solvada e pote multiway.

    A regra e a MESMA do gradeamento (`gto_off_tree` la embaixo): postflop resolvido por range
    AGREGADA nunca e hand-aware, entao nunca crava veredito. Repetir a expressao aqui seria
    convidar as duas a divergirem de novo — por isso a definicao e uma so, e o teste cobra que
    o que passa por este filtro nao volta 'uncovered'.

    Multiway ja sai no SQL da selecao; sobra o off-tree, que exige o lookup ao vivo.
    """
    street = (row.get('street') or '').lower()
    if street == 'preflop':
        return False
    if (row.get('n_active_opponents') or 0) >= 2:
        return True
    try:
        _b, _f, fonte = _resolve_best_action_from_node(row, return_strategy=True)
    except Exception:
        return False   # falha de lookup nao vira exclusao: perder spot e pior que arriscar um
    return fonte in ('gto_range', 'gto_stored')


@app.route('/player/spots/drill', methods=['GET'])
@require_auth
def player_drill_spots():
    """Sprint K — Retorna spots de mistakes para o Ghost Table Simulator.
    Ghost (SRS das mãos reais) é Pro: o Free vê o bloqueio com upsell (não trava a página)."""
    from database.repositories import PLAN_LIMITS
    plan = (getattr(g, 'user', None) or {}).get('plan', 'free')
    gate_active, _grace = _training_gate_status()   # rampa: durante a transição, Ghost liberado
    if gate_active and not PLAN_LIMITS.get(plan, PLAN_LIMITS['free']).get('ghost', False):
        return jsonify({'spots': [], 'stats': None, 'requires_pro': True, 'feature': 'ghost'}), 200
    limit  = min(int(request.args.get('limit', 10)), 20)
    street = request.args.get('street') or None
    spot   = request.args.get('spot')   or None
    # Pede FOLGA e descarta o que voltaria sem veredito. A ordem do SRS e preservada: filtrar
    # nao reordena, so remove. Medido no acervo real: o descarte custa 8,5% do pool (3% multiway,
    # 5,5% off-tree) e deixa 183 spots — muito acima dos 10 de uma sessao.
    brutos = get_drill_spots(g.user_id, limit=limit * 3, street=street, spot=spot)
    spots  = [s for s in brutos if not _spot_sem_veredito(s)][:limit]
    stats  = get_drill_stats(g.user_id, days=30)
    return jsonify({'spots': spots, 'stats': stats})


# MVP aproximação DEEP: spot postflop fundo (alto SPR) que o solver não cobre no stack real
# (deep OOP = árvore grande, rejeitada/não resolvida). Em HU, o solve a ~30bb é tratável e a AÇÃO
# transfere bem; sizing/comprometimento podem diferir → exibido como "≈ Aproximação". Só acima do MIN
# (abaixo, o solve real já cobre). Ver scripts/enqueue_deep_approx.py.
_DEEP_APPROX_STACK_BB = 30.0
_DEEP_APPROX_MIN_BB   = 35.0


def _hashes_da_linha(street, position, board_for_hash, hero_hand, stack_bb, facing_bb,
                     is_3bet) -> list:
    """Variantes de hash de nó para uma LINHA de `decisions`, na MESMA ordem do engine.

    RC-3 da auditoria do Ghost Table (25/06, fechado 17/08): o drill e o /replay/<id>/gto
    chamavam `compute_spot_hash` SEM pot_type — um pote 3-BET resolvia o nó da árvore SRP
    (outra estrutura de ranges, veredito de outra carta). A linha carrega `is_3bet`, que
    basta para espelhar o engine no ramo 3-bet: variante '3bet' primeiro, legado como
    aproximação deliberada — a mesma ordem de `_enrich_gto`/`lookup_gto`.

    A variante 'oop_pfr' NÃO é derivável da linha: o opener preflop não é coluna, e
    `hero_was_aggressor` postflop é INICIATIVA (um check-raise a inverte) — derivar seria
    chute, e derivação já custou caro aqui. Quem protege esse caso é o guarda
    `_no_contradiz_o_gravado`."""
    from leaklab.gto_utils import compute_spot_hash
    hashes = []
    for pt in (('3bet', '') if is_3bet else ('',)):
        if hero_hand:
            hashes.append(compute_spot_hash(street, position, board_for_hash, hero_hand,
                                            stack_bb, facing_bb, pt))
        hashes.append(compute_spot_hash(street, position, board_for_hash, [],
                                        stack_bb, facing_bb, pt))
        if facing_bb == 0:
            hashes.append(compute_spot_hash(street, position, board_for_hash, [],
                                            stack_bb, 0.0, pt))
    return hashes


_FAMILIA_ACAO_NO = {
    'jam': 'allin', 'shove': 'allin', 'allin': 'allin', 'all-in': 'allin', 'all_in': 'allin',
    'bet': 'aggro', 'raise': 'aggro', 'reraise': 'aggro', '3bet': 'aggro', '4bet': 'aggro',
    'call': 'call', 'check': 'check', 'fold': 'fold',
}


def _no_contradiz_o_gravado(node, stored_gto_action) -> bool:
    """True quando a ação-topo do nó VIVO é de outra FAMÍLIA que o `gto_action` gravado —
    o cheiro de nó de variante errada (ex.: 'oop_pfr', que não dá para derivar da linha; o
    nó legado ali descreve o confronto com as ranges TROCADAS).

    O gravado veio do engine com o spot COMPLETO em mãos, e o resync o mantém fresco depois
    de re-solve — contradição aqui não é frescor, é outra árvore. Quem contradiz é
    rejeitado e o consumidor cai no gravado: coerente com o que o card mostra em toda outra
    superfície, e nunca introduz dado novo errado (regra 7: o conserto não pode causar dano
    que o buraco não causava). Sem gravado (linha sem cobertura na análise), o guarda não
    age — nó vivo é cobertura ADITIVA. Família (fold/check/call/aggro/allin), não ação
    exata: 'bet' vs 'raise' é rótulo de menu, não contradição."""
    if not node or not stored_gto_action:
        return False
    topo = ''
    sj = node.get('strategy_json')
    if sj:
        try:
            import json as _jj
            _s = _jj.loads(sj) if isinstance(sj, str) else sj
            topo = max(_s, key=lambda k: (_s[k] or {}).get('frequency', 0))
        except Exception:
            topo = ''
    if not topo:
        topo = node.get('gto_action') or ''
    fam_no = _FAMILIA_ACAO_NO.get((topo or '').lower().strip())
    fam_gravado = _FAMILIA_ACAO_NO.get((stored_gto_action or '').lower().strip())
    if not fam_no or not fam_gravado:
        return False
    return fam_no != fam_gravado


def _resolve_best_action_from_node(row: dict, return_strategy: bool = False):
    """Busca ação GTO ao vivo em gto_nodes (mesma lógica do /replay/<id>/gto).
    Fallback para decisions.gto_action → best_action se nenhum nó for encontrado.
    Com return_strategy=True retorna (top_action, {ação_normalizada: frequência})."""
    from database.repositories import get_gto_node
    from leaklab.gto_utils import compute_spot_hash
    import json as _j

    street    = row.get('street', '')
    position  = row.get('position', '')
    facing_bb = float(row.get('facing_bet') or 0.0)
    stack_bb  = float(row.get('stack_bb') or 30.0)

    try:
        board_raw = row.get('board') or '[]'
        board = _j.loads(board_raw) if isinstance(board_raw, str) else (board_raw or [])
    except Exception:
        board = []

    from leaklab.gto_utils import board_for_street
    board_for_hash = board_for_street(board, street)

    hand_raw = row.get('hero_cards') or ''
    if isinstance(hand_raw, str) and hand_raw.strip():
        _raw = hand_raw.strip()
        hero_hand = _raw.split() if ' ' in _raw else [_raw[i:i+2] for i in range(0, len(_raw), 2)]
    else:
        hero_hand = []

    def _valid_node(n):
        """Rejeita nó se street ou board não batem — captura colisões de hash SHA256[:16]."""
        if not n:
            return None
        if n.get('street', '').lower() != street.lower():
            return None
        try:
            node_board = sorted(_j.loads(n.get('board') or '[]') if isinstance(n.get('board'), str) else (n.get('board') or []))
            if board_for_hash and node_board and node_board != sorted(board_for_hash):
                return None
        except Exception:
            pass
        # Rejeita nó incompatível com o FACING do spot: se o hero enfrenta aposta (facing>0),
        # o nó não pode ser um first-to-act (menu com 'check'). Sem isto um nó OOP check/bet
        # casa num spot vs-bet e o card recomenda "check" sem botão de check (ação inalcançável).
        _acts = set()
        try:
            _sj = n.get('strategy_json')
            if _sj:
                _acts = {str(k).lower() for k in (_j.loads(_sj) if isinstance(_sj, str) else _sj).keys()}
        except Exception:
            _acts = set()
        if not _acts and n.get('gto_action'):
            _acts = {str(n['gto_action']).lower()}
        if facing_bb > 0 and 'check' in _acts:
            return None
        # O INVERSO (RC-5/6, 17/08): sem aposta a enfrentar POSTFLOP, nó com 'fold' no menu é
        # um nó vs-aposta — outra forma de spot. Servi-lo faz a janela de frequência premiar
        # fold onde fold nem existe. Preflop fica fora: open-fold é legal com facing 0.
        if facing_bb == 0 and street.lower() != 'preflop' and 'fold' in _acts:
            return None
        return n

    # RC-3: variantes de pot_type na ordem do engine ('3bet' primeiro quando a linha diz
    # is_3bet) + guarda de coerência contra o gravado (pega variante inderivável, ex. oop_pfr).
    node = None
    for _h in _hashes_da_linha(street, position, board_for_hash, hero_hand, stack_bb,
                               facing_bb, row.get('is_3bet')):
        _n = _valid_node(get_gto_node(_h))
        if _n and not _no_contradiz_o_gravado(_n, row.get('gto_action')):
            node = _n
            break
    # Fallback d (get_gto_node_by_spot) removido: usa algoritmo de hash diferente de compute_spot_hash,
    # podendo retornar nós completamente errados via colisão acidental.

    top_action = row.get('gto_action') or row.get('best_action') or 'fold'
    strat = {}
    source = 'gto_stored'   # decisions.gto_action sem nó vivo
    if node:
        # Hand-aware primeiro (gotcha das frequências agregadas): num K72r a range
        # checa 60% mas AA aposta 95% — validar pela range daria "correto" indevido.
        # Quando a árvore por mão existe (gto_tree_strategies), usa a frequência
        # DA MÃO do hero; agregado é fallback.
        hand_view = None
        if node.get('tree_hash') and hero_hand and street != 'preflop':
            try:
                from leaklab.gto_solver import hand_view_for_spot
                hand_view = hand_view_for_spot(node['tree_hash'], board_for_hash, hero_hand)
            except Exception:
                hand_view = None
        if hand_view and hand_view.get('actions'):
            strat = {a: {'frequency': v.get('frequency', 0)} for a, v in hand_view['actions'].items()}
            top_action = max(strat, key=lambda k: strat[k].get('frequency', 0))
            source = 'gto_hand'
        elif node.get('strategy_json'):
            try:
                strat = _j.loads(node['strategy_json'])
                top_action = max(strat, key=lambda k: strat[k].get('frequency', 0))
                source = 'gto_range'
            except Exception:
                strat = {}
                if node.get('gto_action'):
                    top_action = node['gto_action']
                    source = 'gto_range'
        elif node.get('gto_action'):
            top_action = node['gto_action']
            source = 'gto_range'

    def _norm_action(raw: str) -> str:
        raw = (raw or '').lower()
        if raw in ('shove', 'jam', 'allin', 'all-in', 'all_in'):
            return 'jam'
        if raw.startswith('bet'):
            # Enfrentando aposta (facing>0), a agressão legal é RAISE, não bet (não há botão
            # 'bet' vs-aposta). O solver rotula o raise-sobre-aposta como 'bet_Xbb'; normaliza
            # p/ raise. Sem aposta em frente, 'bet' é bet de verdade (postflop first-to-act).
            return 'raise' if facing_bb > 0 else 'bet'
        if raw.startswith('raise'):
            # Preflop, abrir o pote é RAISE (raisa por cima das blinds), nunca "bet".
            # Só postflop (sem blinds em frente) agredir sem aposta anterior = "bet".
            return 'bet' if (facing_bb == 0 and (street or '').lower() != 'preflop') else 'raise'
        return raw

    a = _norm_action(top_action)

    # Sanity: jam dominante com SPR > 8 e sem aposta anterior é implausível.
    # SPR alto sem facing bet significa overbet de >8x o pote — GTO nunca recomenda jam como
    # ação dominante nesse cenário. Indica hash match incorreto no gto_nodes.
    # Fallback: decisions.gto_action (computado pelo worker, geralmente correto nesses casos).
    if a == 'jam' and facing_bb == 0:
        pot_bb_val = float(row.get('pot_size') or 0)
        if pot_bb_val > 0 and stack_bb > 0 and stack_bb / pot_bb_val > 8:
            stored = _norm_action(row.get('gto_action') or '')
            a = stored if stored else 'check'

    if return_strategy:
        freqs: dict = {}
        for _raw_act, _info in (strat or {}).items():
            _na = _norm_action(_raw_act)
            try:
                freqs[_na] = freqs.get(_na, 0.0) + float((_info or {}).get('frequency', 0) or 0)
            except Exception:
                pass
        return a, freqs, source
    return a


def _norm_drill(a: str) -> str:
    """Mapeia ação GTO para os 6 botões do Ghost Table (fold/check/call/bet/raise/jam)."""
    a = (a or '').strip().lower()
    if a in ('shove', 'jam', 'allin', 'all-in', 'all_in'):
        return 'jam'
    if a.startswith('bet'):
        return 'bet'
    if a.startswith('raise'):
        return 'raise'
    return a


def grade_drill_action(row, new_action):
    """VEREDITO DO DRILL — FONTE ÚNICA. Pura: dado o spot (row) e a ação do jogador, devolve o
    veredito completo (gto_tier/is_correct/best_action/freqs/flags), SEM efeitos colaterais
    (sem save/XP/HTTP). O endpoint /submit E a validação exaustiva consomem isto. Nunca recriar
    o mapeamento em outro lugar (ver feedback_card_display_untested)."""
    best_action = row['best_action']
    gto_action  = row.get('gto_action') or ''
    gto_label   = row.get('gto_label') or ''

    # Usa live GTO node lookup quando cobertura GTO disponível (mesmo pipeline do Replayer).
    gto_freqs: dict = {}
    validation_source = 'heuristic'   # sem cobertura GTO: gradeia vs best_action do engine
    if gto_action and gto_label not in ('wizard_pending', ''):
        best_action, gto_freqs, validation_source = _resolve_best_action_from_node(row, return_strategy=True)
        # RC-4: range AGREGADA (gto_range/gto_stored) nunca é hand-aware → SEMPRE off-tree postflop.
        _street_lc = (row.get('street') or '').lower()
        gto_off_tree = (_street_lc != 'preflop' and validation_source in ('gto_range', 'gto_stored'))
    else:
        gto_off_tree = False
        best_action = _norm_drill(best_action)
        # Guard: raise sem aposta anterior é "bet" — mas SÓ postflop.
        if (float(row.get('facing_bet') or 0) == 0 and best_action == 'raise'
                and (row.get('street') or '').lower() != 'preflop'):
            best_action = 'bet'

    # Guard: BB pode check grátis — fold sem aposta é impossível.
    if float(row.get('facing_bet') or 0) == 0 and best_action == 'fold' and row.get('position') == 'BB':
        best_action = 'check'
        # RC-5/6 (17/08): quem reescreve o best_action reescreve as FREQUÊNCIAS junto — a
        # mesma regra dos campos-viajantes do veredito. Sem isto a janela de ≥30% premiava o
        # fold que este guard acabou de declarar impossível (freq do nó intacta).
        if gto_freqs and 'fold' in gto_freqs:
            gto_freqs = dict(gto_freqs)
            gto_freqs['check'] = round(gto_freqs.get('check', 0.0) + gto_freqs.pop('fold'), 4)

    # MULTIWAY: postflop com 2+ oponentes vivos → solver é HU-only, não cobre.
    # n_active_opponents NULL (legado/reimport) → 0 = NÃO multiway (alinha com o drill em ~6812).
    # NÃO usar num_players-1 de fallback: num_players é o TAMANHO DA MESA (ex.: 9), não os ativos
    # NA STREET — num pote que afunilou pra HU no turn/river isso marcava multiway falso (bug real:
    # T#4002072836, mão HU no river virava "≈ multiway"). Melhor não-flag do que marcar HU como multiway.
    _n_opp = row.get('n_active_opponents')
    _n_opp = max(0, int(_n_opp or 0))
    gto_multiway = ((row.get('street') or '').lower() != 'preflop' and _n_opp >= 2)

    original_score = row['score']
    norm_new   = _norm_drill(new_action)
    top_match  = norm_new == best_action

    # Guard: facing_bet >= stack_bb → call e jam são mecanicamente equivalentes.
    facing_bet = float(row.get('facing_bet') or 0)
    stack_bb   = float(row.get('stack_bb') or 9999)
    call_jam_equiv = False
    if not top_match and facing_bet > 0 and stack_bb > 0 and facing_bet >= stack_bb * 0.90:
        if norm_new in ('call', 'jam') and best_action in ('call', 'jam'):
            call_jam_equiv = True

    # Guard: PREFLOP curto pot-committed — shove co-ótimo p/ best_action que continua (call/raise).
    _pot_pf = float(row.get('pot_size') or 0)
    if (not top_match and not call_jam_equiv
            and (row.get('street') or '').lower() == 'preflop'
            and norm_new == 'jam' and best_action in ('call', 'raise')
            and 0 < stack_bb <= 14 and _pot_pf >= stack_bb * 0.75):
        call_jam_equiv = True

    # Guard: stack curtíssimo (≤2.5bb) — raise ≡ jam.
    raise_jam_equiv = False
    if (not top_match and stack_bb > 0 and stack_bb <= 2.5
            and norm_new in ('raise', 'jam') and best_action in ('raise', 'jam')):
        raise_jam_equiv = True
    call_jam_equiv = call_jam_equiv or raise_jam_equiv

    # ── Avaliação pela distribuição GTO (princípio da indiferença) ───────────
    CORRECT_FREQ, MIN_FREQ = 0.30, 0.10
    player_freq = float(gto_freqs.get(norm_new, 0.0)) if gto_freqs else 0.0

    # MULTIWAY (opção A): informativo. Nunca punição dura; expõe a sugestão do advisor.
    mw_advice = None
    multiway_safe = None   # Fase 2: veredito GRADEADO da cauda segura (flag MULTIWAY_GRADE_SAFE_TAIL)
    if gto_multiway:
        try:
            from leaklab.multiway_advisor import advise_multiway, is_hero_leak, norm_action as _mw_norm
            import json as _mwjson
            _b = row.get('board')
            _b = _mwjson.loads(_b) if isinstance(_b, str) else (_b or [])
            _sc = {'flop': 3, 'turn': 4, 'river': 5}.get((row.get('street') or '').lower(), len(_b))
            _adv = advise_multiway(
                row.get('hero_cards'), _b[:_sc],
                float(row.get('pot_size') or 0), float(row.get('facing_bet') or 0),
                _n_opp,
                street=(row.get('street') or 'flop').lower(),
                eff_stack_bb=(float(row.get('stack_bb') or 0) or None))
            if _adv:
                mw_advice = {
                    'action':       _norm_drill(_mw_norm(_adv.get('action'))),
                    'is_clear':     bool(_adv.get('is_clear')),
                    'rationale':    _adv.get('rationale'),
                    'suggests_leak': is_hero_leak(_adv, norm_new) if _adv.get('is_clear') else None,
                }
        except Exception:
            mw_advice = None
        # Fase 2: cauda segura tem PRECEDÊNCIA sobre o informativo (flag-gated dentro de graded_safe_verdict).
        try:
            from leaklab.multiway_safety import graded_safe_verdict as _gsv
            multiway_safe = _gsv(
                row.get('hero_cards'), _b[:_sc], _n_opp,
                float(row.get('pot_size') or 0), float(row.get('facing_bet') or 0),
                norm_new, street=(row.get('street') or 'flop').lower())
        except Exception:
            multiway_safe = None

    if multiway_safe:
        # Cauda segura: veredito REAL (garantido) em vez de 'uncovered'. is_leak → error.
        gto_tier = 'error' if multiway_safe['is_leak'] else 'correct'
    elif gto_off_tree or gto_multiway:
        gto_tier = 'uncovered'   # off-tree OU multiway: não crava veredito; nunca penaliza.
    elif top_match or call_jam_equiv:
        gto_tier = 'correct'
    elif gto_freqs and player_freq >= CORRECT_FREQ:
        gto_tier = 'correct'
    elif gto_freqs and player_freq >= MIN_FREQ:
        gto_tier = 'deviation'
    else:
        gto_tier = 'error'

    is_correct    = gto_tier != 'error'   # 'uncovered' não é erro
    is_mixed_line = gto_tier == 'correct' and not (top_match or call_jam_equiv)
    if gto_tier == 'uncovered':
        new_score = original_score   # neutro REAL (delta=0)
    elif top_match or call_jam_equiv:
        new_score = 0.02
    elif gto_tier == 'correct':
        new_score = 0.04
    elif gto_tier == 'deviation':
        new_score = 0.10
    else:
        new_score = original_score

    gto_strategy = [
        {'action': _a, 'frequency': round(_f, 4)}
        for _a, _f in sorted(gto_freqs.items(), key=lambda kv: -kv[1]) if _f > 0.005
    ] if gto_freqs else []

    return {
        'gto_tier': gto_tier, 'is_correct': is_correct, 'best_action': best_action,
        'gto_freqs': gto_freqs, 'validation_source': validation_source,
        'gto_off_tree': gto_off_tree, 'gto_multiway': gto_multiway,
        'multiway_advice': (None if multiway_safe else mw_advice),   # cauda segura SUBSTITUI o informativo
        'multiway_safe': multiway_safe,   # Fase 2: veredito gradeado da cauda segura (None = informativo)
        'new_score': new_score, 'original_score': original_score, 'is_mixed_line': is_mixed_line,
        'player_freq': player_freq, 'gto_strategy': gto_strategy, 'norm_new': norm_new,
        'top_match': top_match, 'call_jam_equiv': call_jam_equiv,
    }


@app.route('/player/spots/drill/submit', methods=['POST'])
@require_auth
def player_drill_submit():
    """Sprint K — Salva redecisão e retorna avaliação."""
    data = request.get_json() or {}
    decision_id = data.get('decision_id')
    new_action  = data.get('new_action', '').strip().lower()

    if not decision_id or not new_action:
        return jsonify({'error': 'decision_id e new_action são obrigatórios'}), 400

    row = get_decision_for_drill(g.user_id, decision_id)
    if not row:
        return jsonify({'error': 'Decisão não encontrada'}), 404

    v = grade_drill_action(row, new_action)
    gto_tier          = v['gto_tier']
    is_correct        = v['is_correct']
    best_action       = v['best_action']
    new_score         = v['new_score']
    original_score    = v['original_score']
    player_freq       = v['player_freq']
    is_mixed_line     = v['is_mixed_line']
    gto_off_tree      = v['gto_off_tree']
    gto_multiway      = v['gto_multiway']
    mw_advice         = v['multiway_advice']
    gto_strategy      = v['gto_strategy']
    validation_source = v['validation_source']

    result = save_drill_session(
        user_id=g.user_id,
        decision_id=decision_id,
        new_action=new_action,
        new_score=new_score,
        original_score=original_score,
        is_correct=is_correct,   # acerto autoritativo (tier GTO), não delta<0
    )

    # XP — drill_completed só na 1ª vez do dia por decisão (anti-farm);
    # drill_mastered quando o SRS atinge o intervalo máximo pela 1ª vez.
    xp_events = []
    if is_correct and gto_tier != 'uncovered' and result.get('first_drill_today'):
        xp_events.append('drill_completed')   # uncovered (off-tree/multiway) não é acerto cravado → sem XP
    if result.get('mastered_now'):
        xp_events.append('drill_mastered')
    xp_gained, xp_total, new_achievements = 0, None, []
    for ev in xp_events:
        xp_res = add_xp(g.user_id, ev)
        xp_gained += xp_res.get('xp_gained', 0)
        xp_total   = xp_res.get('xp_total', xp_total)
        new_achievements.extend(xp_res.get('new_achievements', []))

    return jsonify({
        'xp': {
            'events':           xp_events,
            'gained':           xp_gained,
            'total':            xp_total,
            'new_achievements': new_achievements,
        },
        'is_correct':        is_correct,
        'best_action':       best_action,
        'new_action':        new_action,
        'new_score':         new_score,
        'original_score':    original_score,
        'gto_freq':          round(player_freq, 3),
        'mixed':             is_mixed_line,
        'gto_tier':          gto_tier,
        'gto_off_tree':      gto_off_tree,   # mão fora da cobertura hand-aware → "≈ aproximação"
        'gto_multiway':      gto_multiway,   # postflop multiway (solver HU-only) → "≈ multiway"
        'multiway_advice':   mw_advice,      # opção A: sugestão heurística informativa (não pune)
        'gto_strategy':      gto_strategy,
        'validation_source': validation_source,   # gto_hand | gto_range | gto_stored | heuristic
        'delta':             result['delta'],
        'next_drill_at':     result['next_drill_at'],
        'srs_interval_days': result['srs_interval_days'],
    })


@app.route('/player/drill-stats', methods=['GET'])
@require_auth
def player_drill_stats_only():
    """Dashboard — Estatísticas de drill sem carregar os spots."""
    days = int(request.args.get('days', 30))
    return jsonify(get_drill_stats(g.user_id, days=days))


@app.route('/player/dna', methods=['GET'])
@require_auth
def player_dna():
    """Sprint L — Assinatura estratégica do jogador (Decision DNA)."""
    days = int(request.args.get('days', 90))
    return jsonify(get_player_dna(g.user_id, days=days))


@app.route('/player/leak-graph', methods=['GET'])
@require_auth
def player_leak_graph():
    gate = _check_advanced_insights(g.user_id)
    if gate:
        return gate
    days = int(request.args.get('days', 90))
    lang = request.args.get('lang', 'pt-BR')
    return jsonify(get_leak_graph_data(g.user_id, days=days, lang=lang))


@app.route('/player/career', methods=['GET'])
@require_auth
def player_career():
    gate = _check_advanced_insights(g.user_id)
    if gate:
        return gate
    from leaklab.llm_explainer import generate_career_narrative
    lang       = request.args.get('lang', 'pt-BR')
    projection = get_career_projection(g.user_id)
    if not projection.get("insufficient_data"):
        projection["narrative"] = generate_career_narrative(projection, lang=lang)
    return jsonify(projection)


@app.route('/player/cognitive-failures', methods=['GET'])
@require_auth
def player_cognitive_failures():
    gate = _check_advanced_insights(g.user_id)
    if gate:
        return gate
    from leaklab.llm_explainer import generate_cognitive_narrative
    lang   = request.args.get('lang', 'pt-BR')
    days   = int(request.args.get('days', 90))
    report = get_cognitive_failure_report(g.user_id, days=days)
    if not report.get("insufficient_data") and report.get("patterns"):
        report["narrative"] = generate_cognitive_narrative(report["patterns"], lang=lang)
    return jsonify(report)


@app.route('/player/session-context', methods=['GET'])
@require_auth
def player_session_context():
    """Contexto de sessão OBJETIVO (multi-tabling, fadiga, horário) × qualidade da decisão.
    Cruza a janela de tempo de cada torneio (started_at/ended_at) com o avg_score."""
    gate = _check_advanced_insights(g.user_id)
    if gate:
        return gate
    from leaklab.session_context import analyze_session_context
    from database.schema import get_conn as _gc
    from database.repositories import _fetchall, _adapt
    conn = _gc()
    try:
        rows = _fetchall(conn, _adapt(
            "SELECT started_at, ended_at, avg_score, decisions_count "
            "FROM tournaments WHERE user_id = ? AND started_at IS NOT NULL"), (g.user_id,))
    finally:
        conn.close()
    return jsonify(analyze_session_context([dict(r) for r in rows]))


@app.route('/metrics/leaderboard', methods=['GET'])
@require_auth
def leaderboard():
    """Ranking de alunos por APRENDIZADO (#15 — fundação: motor + endpoint).

    Pontua por aderência GTO (40%) + evolução (30%) + engajamento (20%) +
    volume (10%), com guarda de elegibilidade (mín. mãos/torneios/cobertura GTO).
    `period` em dias (default 90). UI pública, opt-in/privacidade e cron de
    snapshots ficam para um sprint futuro (precisam de escala real de usuários).

    Privacidade (#15 opt-in): a lista pública (`ranked`/`ineligible`) só inclui
    quem optou por participar, anonimizado por handle. `me` traz a posição do
    próprio usuário sempre — mesmo fora do ranking público.
    """
    from database.repositories import (
        get_leaderboard_metrics, should_take_snapshot,
        save_leaderboard_snapshot, get_rank_delta, grant_leaderboard_achievements,
    )
    from leaklab.leaderboard import (
        rank_leaderboard, public_view, W_GTO, W_EVO, W_ENG, W_VOL,
        MIN_HANDS, MIN_TOURNAMENTS, MIN_GTO_DECISIONS,
    )
    period = request.args.get('period', default=90, type=int)
    result = rank_leaderboard(get_leaderboard_metrics(period_days=period))
    # Substituto local do cron: grava um snapshot ~1/dia (best-effort, reusa o
    # ranking já computado). Cron real (scheduler/hosting) fica pendente — backlog #15.
    try:
        if should_take_snapshot(period):
            save_leaderboard_snapshot(period, result['ranked'])
    except Exception:
        pass
    view = public_view(result, viewer_id=g.user_id)
    if view['me'] is not None:
        me = view['me']
        me['rank_delta'] = get_rank_delta(g.user_id, period)
        # Badges de ranking (#15): concede com base na posição/ELO atuais (best-effort).
        try:
            rd = me['rank_delta']['delta'] if me.get('rank_delta') else None
            grant_leaderboard_achievements(
                g.user_id, rank=me.get('overall_rank'),
                rank_delta=rd, elo=me.get('player_elo'),
            )
        except Exception:
            pass
    return jsonify({
        'period_days':  period,
        'weights':      {'gto': W_GTO, 'evolution': W_EVO, 'engagement': W_ENG, 'volume': W_VOL},
        'eligibility':  {'min_hands': MIN_HANDS, 'min_tournaments': MIN_TOURNAMENTS,
                         'min_gto_decisions': MIN_GTO_DECISIONS},
        'ranked':       view['ranked'],
        'ineligible':   view['ineligible'],
        'me':           view['me'],
    })


@app.route('/metrics/training-league', methods=['GET'])
@require_auth
def training_league():
    """Liga de Treino (#32): ranking de ESFORÇO da semana corrente (seg–dom), por
    acertos no treino — NÃO por ELO/skill. Opt-in/handle reusam a vitrine do #15.
    Reset automático (a janela é a semana atual). O próprio usuário sempre vê sua
    posição (`me`), mesmo sem ter treinado ou sem opt-in."""
    from datetime import datetime, timedelta
    from database.repositories import get_training_league, get_leaderboard_prefs, get_xp_status
    from leaklab.leaderboard import rank_training_league, public_view

    today  = datetime.utcnow().date()
    monday = today - timedelta(days=today.weekday())
    sunday = monday + timedelta(days=6)
    ws, we = monday.strftime('%Y-%m-%d'), sunday.strftime('%Y-%m-%d')

    players = get_training_league(ws, we)
    # Garante que o viewer aparece (linha zero) mesmo sem treino na semana → `me` existe.
    if not any(p['user_id'] == g.user_id for p in players):
        prefs = get_leaderboard_prefs(g.user_id)
        try:
            streak = int((get_xp_status(g.user_id) or {}).get('streak') or 0)
        except Exception:
            streak = 0
        players.append({
            'user_id': g.user_id, 'username': g.user.get('username') if g.get('user') else None,
            'handle': prefs.get('handle'), 'opt_in': bool(prefs.get('opt_in')),
            'streak': streak, 'points': 0, 'spots': 0,
        })

    view = public_view(rank_training_league(players), viewer_id=g.user_id)
    return jsonify({
        'week_start': ws, 'week_end': we,
        'ranked':     view['ranked'],
        'ineligible': view['ineligible'],
        'me':         view['me'],
    })


@app.route('/metrics/hall-of-fame', methods=['GET'])
@require_auth
def hall_of_fame():
    """Campeões mensais do ranking (#15 hall of fame) — #1 de cada mês, com
    privacidade (anônimo se sem opt-in). Vazio até a série cobrir ≥1 mês."""
    from database.repositories import get_hall_of_fame
    period = request.args.get('period', default=90, type=int)
    return jsonify({'champions': get_hall_of_fame(period_days=period)})


@app.route('/player/leaderboard-prefs', methods=['GET'])
@require_auth
def leaderboard_prefs_get():
    """Preferências de privacidade do ranking do próprio usuário (#15 opt-in)."""
    from database.repositories import get_leaderboard_prefs
    return jsonify(get_leaderboard_prefs(g.user_id))


@app.route('/player/leaderboard-prefs', methods=['POST'])
@require_auth
def leaderboard_prefs_set():
    """Liga/desliga a participação no ranking público + handle (apelido). Não afeta
    a visão do coach sobre o aluno, só a vitrine pública."""
    from database.repositories import set_leaderboard_prefs
    body = request.get_json(silent=True) or {}
    handle = body.get('handle')
    if handle is not None and not isinstance(handle, str):
        return jsonify({'error': 'handle must be a string'}), 400
    try:
        prefs = set_leaderboard_prefs(g.user_id, bool(body.get('opt_in')), handle)
    except ValueError as e:
        # handle_taken → apelido já em uso por outro aluno (case-insensitive)
        return jsonify({'error': str(e)}), 409
    return jsonify(prefs)


@app.route('/player/notifications', methods=['GET'])
@require_auth
def notifications_list():
    """Notificações do usuário (mais novas primeiro). type + payload (JSON) —
    o frontend renderiza o texto localizado por tipo."""
    from database.repositories import get_notifications
    return jsonify({'notifications': get_notifications(g.user_id, limit=30)})


@app.route('/player/notifications/unread-count', methods=['GET'])
@require_auth
def notifications_unread_count():
    from database.repositories import get_unread_notification_count
    return jsonify({'unread': get_unread_notification_count(g.user_id)})


@app.route('/player/notifications/<int:notif_id>/read', methods=['POST'])
@require_auth
def notifications_mark_read(notif_id):
    from database.repositories import mark_notification_read
    mark_notification_read(g.user_id, notif_id)
    return jsonify({'ok': True})


@app.route('/player/notifications/read-all', methods=['POST'])
@require_auth
def notifications_mark_all_read():
    from database.repositories import mark_all_notifications_read
    mark_all_notifications_read(g.user_id)
    return jsonify({'ok': True})


@app.route('/player/notifications/<int:notif_id>', methods=['DELETE'])
@require_auth
def notifications_dismiss(notif_id):
    """Dispensa (remove) uma notificação — ao clicar, sai da lista."""
    from database.repositories import dismiss_notification
    ok = dismiss_notification(g.user_id, notif_id)
    return jsonify({'ok': ok})


@app.route('/player/notifications', methods=['DELETE'])
@require_auth
def notifications_dismiss_all():
    """Limpa todas as notificações do usuário."""
    from database.repositories import dismiss_all_notifications
    n = dismiss_all_notifications(g.user_id)
    return jsonify({'ok': True, 'removed': n})


@app.route('/player/sparring/hand', methods=['GET'])
@require_auth
def player_sparring_hand():
    hand_id       = request.args.get('hand_id')
    tournament_id = request.args.get('tournament_id', type=int)
    raw_excl      = request.args.get('exclude_hand_ids', '')
    exclude_hand_ids = [h.strip() for h in raw_excl.split(',') if h.strip()] if raw_excl else []
    data = get_sparring_hand(g.user_id, hand_id=hand_id, tournament_id=tournament_id,
                             exclude_hand_ids=exclude_hand_ids)
    return jsonify(data)


# ── Academia ──────────────────────────────────────────────────────────────────

@app.route('/academy/math/question', methods=['GET'])
@require_auth
def academy_math_question():
    from leaklab.academy import generate_math_question
    level = request.args.get('level', 'beginner')
    return jsonify(generate_math_question(g.user_id, level=level))


@app.route('/academy/math/submit', methods=['POST'])
@require_auth
def academy_math_submit():
    body       = request.get_json(force=True) or {}
    selected   = body.get('selected_index')
    correct    = body.get('correct_index')
    xp_value   = int(body.get('xp_value', 15))
    is_correct = selected == correct
    if is_correct:
        add_xp(g.user_id, 'academy_math_correct', xp_value)
    return jsonify({'is_correct': is_correct})


@app.route('/academy/board-strength/question', methods=['GET'])
@require_auth
def academy_board_strength_question():
    from leaklab.academy import generate_board_strength_question
    return jsonify(generate_board_strength_question(g.user_id))


@app.route('/academy/board-strength/submit', methods=['POST'])
@require_auth
def academy_board_strength_submit():
    body       = request.get_json(force=True) or {}
    selected   = body.get('selected_index')
    correct    = body.get('correct_index')
    xp_value   = int(body.get('xp_value', 20))
    is_correct = selected == correct
    if is_correct:
        add_xp(g.user_id, 'academy_board_correct', xp_value)
    return jsonify({'is_correct': is_correct})


@app.route('/academy/tournament/question', methods=['GET'])
@require_auth
def academy_tournament_question():
    from leaklab.academy import generate_tournament_question
    return jsonify(generate_tournament_question(g.user_id))


@app.route('/academy/tournament/submit', methods=['POST'])
@require_auth
def academy_tournament_submit():
    body       = request.get_json(force=True) or {}
    selected   = body.get('selected_index')
    correct    = body.get('correct_index')
    xp_value   = int(body.get('xp_value', 25))
    is_correct = selected == correct
    if is_correct:
        add_xp(g.user_id, 'academy_tournament_correct', xp_value)
    return jsonify({'is_correct': is_correct})


@app.route('/academy/exploits/question', methods=['GET'])
@require_auth
def academy_exploits_question():
    from leaklab.academy import generate_exploit_question
    return jsonify(generate_exploit_question(g.user_id))


@app.route('/academy/exploits/submit', methods=['POST'])
@require_auth
def academy_exploits_submit():
    body       = request.get_json(force=True) or {}
    selected   = body.get('selected_index')
    correct    = body.get('correct_index')
    xp_value   = int(body.get('xp_value', 20))
    is_correct = selected == correct
    if is_correct:
        add_xp(g.user_id, 'academy_exploits_correct', xp_value)
    return jsonify({'is_correct': is_correct})


@app.route('/academy/pko/question', methods=['GET'])
@require_auth
def academy_pko_question():
    from leaklab.academy import generate_pko_question
    return jsonify(generate_pko_question(g.user_id))


@app.route('/academy/pko/submit', methods=['POST'])
@require_auth
def academy_pko_submit():
    body       = request.get_json(force=True) or {}
    selected   = body.get('selected_index')
    correct    = body.get('correct_index')
    xp_value   = int(body.get('xp_value', 20))
    is_correct = selected == correct
    if is_correct:
        add_xp(g.user_id, 'academy_pko_correct', xp_value)
    return jsonify({'is_correct': is_correct})


@app.route('/academy/imbalances/question', methods=['GET'])
@require_auth
def academy_imbalances_question():
    from leaklab.academy import generate_imbalance_question
    return jsonify(generate_imbalance_question(g.user_id))


@app.route('/academy/imbalances/submit', methods=['POST'])
@require_auth
def academy_imbalances_submit():
    body       = request.get_json(force=True) or {}
    selected   = body.get('selected_index')
    correct    = body.get('correct_index')
    xp_value   = int(body.get('xp_value', 20))
    is_correct = selected == correct
    if is_correct:
        add_xp(g.user_id, 'academy_imbalances_correct', xp_value)
    return jsonify({'is_correct': is_correct})


@app.route('/academy/bvb/question', methods=['GET'])
@require_auth
def academy_bvb_question():
    from leaklab.academy import generate_bvb_question
    return jsonify(generate_bvb_question(g.user_id))


@app.route('/academy/bvb/submit', methods=['POST'])
@require_auth
def academy_bvb_submit():
    body       = request.get_json(force=True) or {}
    selected   = body.get('selected_index')
    correct    = body.get('correct_index')
    xp_value   = int(body.get('xp_value', 20))
    is_correct = selected == correct
    if is_correct:
        add_xp(g.user_id, 'academy_bvb_correct', xp_value)
    return jsonify({'is_correct': is_correct})


@app.route('/academy/bankroll/question', methods=['GET'])
@require_auth
def academy_bankroll_question():
    from leaklab.academy import generate_bankroll_question
    return jsonify(generate_bankroll_question(g.user_id))


@app.route('/academy/bankroll/submit', methods=['POST'])
@require_auth
def academy_bankroll_submit():
    body       = request.get_json(force=True) or {}
    selected   = body.get('selected_index')
    correct    = body.get('correct_index')
    xp_value   = int(body.get('xp_value', 20))
    is_correct = selected == correct
    if is_correct:
        add_xp(g.user_id, 'academy_bankroll_correct', xp_value)
    return jsonify({'is_correct': is_correct})


@app.route('/academy/terms/question', methods=['GET'])
@require_auth
def academy_terms_question():
    from leaklab.academy import generate_terms_question
    return jsonify(generate_terms_question(g.user_id))


@app.route('/academy/terms/submit', methods=['POST'])
@require_auth
def academy_terms_submit():
    body       = request.get_json(force=True) or {}
    selected   = body.get('selected_index')
    correct    = body.get('correct_index')
    xp_value   = int(body.get('xp_value', 20))
    is_correct = selected == correct
    if is_correct:
        add_xp(g.user_id, 'academy_terms_correct', xp_value)
    return jsonify({'is_correct': is_correct})


@app.route('/academy/barrels/question', methods=['GET'])
@require_auth
def academy_barrels_question():
    from leaklab.academy import generate_barrel_question
    return jsonify(generate_barrel_question(g.user_id))


@app.route('/academy/barrels/submit', methods=['POST'])
@require_auth
def academy_barrels_submit():
    body       = request.get_json(force=True) or {}
    selected   = body.get('selected_index')
    correct    = body.get('correct_index')
    xp_value   = int(body.get('xp_value', 20))
    is_correct = selected == correct
    if is_correct:
        add_xp(g.user_id, 'academy_barrels_correct', xp_value)
    return jsonify({'is_correct': is_correct})


@app.route('/academy/threebet/question', methods=['GET'])
@require_auth
def academy_threebet_question():
    from leaklab.academy import generate_3bet_question
    return jsonify(generate_3bet_question(g.user_id))


@app.route('/academy/threebet/submit', methods=['POST'])
@require_auth
def academy_threebet_submit():
    body       = request.get_json(force=True) or {}
    selected   = body.get('selected_index')
    correct    = body.get('correct_index')
    xp_value   = int(body.get('xp_value', 20))
    is_correct = selected == correct
    if is_correct:
        add_xp(g.user_id, 'academy_threebet_correct', xp_value)
    return jsonify({'is_correct': is_correct})


@app.route('/academy/draws/question', methods=['GET'])
@require_auth
def academy_draws_question():
    from leaklab.academy import generate_draws_question
    return jsonify(generate_draws_question(g.user_id))


@app.route('/academy/draws/submit', methods=['POST'])
@require_auth
def academy_draws_submit():
    body       = request.get_json(force=True) or {}
    selected   = body.get('selected_index')
    correct    = body.get('correct_index')
    xp_value   = int(body.get('xp_value', 20))
    is_correct = selected == correct
    if is_correct:
        add_xp(g.user_id, 'academy_draws_correct', xp_value)
    return jsonify({'is_correct': is_correct})


@app.route('/academy/pushfold/question', methods=['GET'])
@require_auth
def academy_pushfold_question():
    from leaklab.academy import generate_pushfold_question
    return jsonify(generate_pushfold_question(g.user_id))


@app.route('/academy/pushfold/submit', methods=['POST'])
@require_auth
def academy_pushfold_submit():
    body       = request.get_json(force=True) or {}
    selected   = body.get('selected_index')
    correct    = body.get('correct_index')
    xp_value   = int(body.get('xp_value', 20))
    is_correct = selected == correct
    if is_correct:
        add_xp(g.user_id, 'academy_pushfold_correct', xp_value)
    return jsonify({'is_correct': is_correct})


@app.route('/academy/showdown/question', methods=['GET'])
@require_auth
def academy_showdown_question():
    from leaklab.academy import generate_sdv_question
    return jsonify(generate_sdv_question(g.user_id))


@app.route('/academy/showdown/submit', methods=['POST'])
@require_auth
def academy_showdown_submit():
    body       = request.get_json(force=True) or {}
    selected   = body.get('selected_index')
    correct    = body.get('correct_index')
    xp_value   = int(body.get('xp_value', 20))
    is_correct = selected == correct
    if is_correct:
        add_xp(g.user_id, 'academy_showdown_correct', xp_value)
    return jsonify({'is_correct': is_correct})


@app.route('/academy/position/question', methods=['GET'])
@require_auth
def academy_position_question():
    from leaklab.academy import generate_position_question
    return jsonify(generate_position_question(g.user_id))


@app.route('/academy/position/submit', methods=['POST'])
@require_auth
def academy_position_submit():
    body       = request.get_json(force=True) or {}
    selected   = body.get('selected_index')
    correct    = body.get('correct_index')
    xp_value   = int(body.get('xp_value', 20))
    is_correct = selected == correct
    if is_correct:
        add_xp(g.user_id, 'academy_position_correct', xp_value)
    return jsonify({'is_correct': is_correct})


@app.route('/academy/blockers/question', methods=['GET'])
@require_auth
def academy_blockers_question():
    from leaklab.academy import generate_blocker_question
    return jsonify(generate_blocker_question(g.user_id))


@app.route('/academy/blockers/submit', methods=['POST'])
@require_auth
def academy_blockers_submit():
    body       = request.get_json(force=True) or {}
    selected   = body.get('selected_index')
    correct    = body.get('correct_index')
    xp_value   = int(body.get('xp_value', 20))
    is_correct = selected == correct
    if is_correct:
        add_xp(g.user_id, 'academy_blockers_correct', xp_value)
    return jsonify({'is_correct': is_correct})


@app.route('/academy/combos/question', methods=['GET'])
@require_auth
def academy_combos_question():
    from leaklab.academy import generate_combo_question
    return jsonify(generate_combo_question(g.user_id))


@app.route('/academy/combos/submit', methods=['POST'])
@require_auth
def academy_combos_submit():
    body       = request.get_json(force=True) or {}
    selected   = body.get('selected_index')
    correct    = body.get('correct_index')
    xp_value   = int(body.get('xp_value', 20))
    is_correct = selected == correct
    if is_correct:
        add_xp(g.user_id, 'academy_combos_correct', xp_value)
    return jsonify({'is_correct': is_correct})


@app.route('/academy/mdf/question', methods=['GET'])
@require_auth
def academy_mdf_question():
    from leaklab.academy import generate_mdf_question
    return jsonify(generate_mdf_question(g.user_id))


@app.route('/academy/mdf/submit', methods=['POST'])
@require_auth
def academy_mdf_submit():
    body       = request.get_json(force=True) or {}
    selected   = body.get('selected_index')
    correct    = body.get('correct_index')
    xp_value   = int(body.get('xp_value', 20))
    is_correct = selected == correct
    if is_correct:
        add_xp(g.user_id, 'academy_mdf_correct', xp_value)
    return jsonify({'is_correct': is_correct})


@app.route('/academy/sizing/question', methods=['GET'])
@require_auth
def academy_sizing_question():
    from leaklab.academy import generate_sizing_question
    return jsonify(generate_sizing_question(g.user_id))


@app.route('/academy/sizing/submit', methods=['POST'])
@require_auth
def academy_sizing_submit():
    body       = request.get_json(force=True) or {}
    selected   = body.get('selected_index')
    correct    = body.get('correct_index')
    xp_value   = int(body.get('xp_value', 20))
    is_correct = selected == correct
    if is_correct:
        add_xp(g.user_id, 'academy_sizing_correct', xp_value)
    return jsonify({'is_correct': is_correct})


@app.route('/academy/postflop/question', methods=['GET'])
@require_auth
def academy_postflop_question():
    from leaklab.academy import generate_postflop_question
    return jsonify(generate_postflop_question(g.user_id))


@app.route('/academy/postflop/submit', methods=['POST'])
@require_auth
def academy_postflop_submit():
    body       = request.get_json(force=True) or {}
    selected   = body.get('selected_index')
    correct    = body.get('correct_index')
    xp_value   = int(body.get('xp_value', 20))
    is_correct = selected == correct
    if is_correct:
        add_xp(g.user_id, 'academy_postflop_correct', xp_value)
    return jsonify({'is_correct': is_correct})


@app.route('/academy/icm/question', methods=['GET'])
@require_auth
def academy_icm_question():
    from leaklab.academy import generate_icm_question
    return jsonify(generate_icm_question(g.user_id))


@app.route('/academy/icm/submit', methods=['POST'])
@require_auth
def academy_icm_submit():
    body       = request.get_json(force=True) or {}
    selected   = body.get('selected_index')
    correct    = body.get('correct_index')
    xp_value   = int(body.get('xp_value', 25))
    is_correct = selected == correct
    if is_correct:
        add_xp(g.user_id, 'academy_icm_correct', xp_value)
    return jsonify({'is_correct': is_correct})


@app.route('/academy/multiway/question', methods=['GET'])
@require_auth
def academy_multiway_question():
    from leaklab.academy import generate_multiway_question
    return jsonify(generate_multiway_question(g.user_id))


@app.route('/academy/multiway/submit', methods=['POST'])
@require_auth
def academy_multiway_submit():
    body       = request.get_json(force=True) or {}
    selected   = body.get('selected_index')
    correct    = body.get('correct_index')
    xp_value   = int(body.get('xp_value', 20))
    is_correct = selected == correct
    if is_correct:
        add_xp(g.user_id, 'academy_multiway_correct', xp_value)
    return jsonify({'is_correct': is_correct})


@app.route('/academy/gto-preflop/question', methods=['GET'])
@require_auth
def academy_gto_preflop_question():
    from leaklab.academy_gto_preflop import generate_gto_preflop_question
    scenario = request.args.get('scenario', 'mixed')
    return jsonify(generate_gto_preflop_question(scenario))


@app.route('/academy/gto-preflop/submit', methods=['POST'])
@require_auth
def academy_gto_preflop_submit():
    # Avaliação SERVER-SIDE: o cliente manda o spot (echo da /question) + a ação
    # escolhida; o veredito GTO é calculado aqui — a range nunca vai pro cliente.
    from leaklab.academy_gto_preflop import grade_gto_preflop_answer
    body     = request.get_json(force=True) or {}
    spot     = body.get('spot') or {}
    action   = (body.get('action') or '').lower()
    xp_value = int(body.get('xp_value', 25))
    result   = grade_gto_preflop_answer(spot, action)
    result['xp_awarded'] = xp_value if result.get('is_correct') else 0
    if result['xp_awarded']:
        add_xp(g.user_id, 'academy_gto_preflop_correct', xp_value)
    return jsonify(result)


def _training_gate_status():
    """Rampa suave do gate freemium de treino: ANTES de TRAINING_GATE_START (ISO YYYY-MM-DD,
    override por env) o gate NÃO é aplicado (período de transição, todos treinam como Pro) e
    as respostas trazem grace_until pro aviso. A partir da data, aplica. Erro na data → aplica."""
    import os as _os
    from datetime import datetime as _dt
    start = _os.environ.get('TRAINING_GATE_START', '2026-07-20')
    try:
        active = _dt.utcnow().date() >= _dt.strptime(start, '%Y-%m-%d').date()
    except Exception:
        active = True
    return active, (None if active else start)


@app.route('/player/leaktrainer/next', methods=['POST'])
@require_auth
def leaktrainer_next():
    """Leak Trainer (Fase 1) — próximo spot canônico mirado no leak do jogador, SEM revelar a resposta.
    O currículo vem dos leaks reais (get_leak_categories); o spot é sintético/limpo; o estado da sessão
    (hits/misses por categoria) é client-side e ecoado. Adulterar o estado não falsifica acerto — o
    grading é server-side e stateless."""
    from leaklab.leak_trainer import build_curriculum, next_spot, _fundamentals_curriculum, fundamentals_catalog
    from database.repositories import PLAN_LIMITS, get_training_spots_today
    body          = request.get_json(silent=True) or {}
    session_state = body.get('session_state') or {}
    days          = int(body.get('days', 90) or 90)
    tz_offset     = int(body.get('tz_offset_min', 0) or 0)
    # foco do treino: 'adaptive' (padrão, currículo real ponderado) | 'leak:<key>' (uma categoria real)
    # | 'fund:<scenario>' (fundamentos de rfi/vs_rfi/vs_3bet, mesmo sem leak medido). O usuário ESCOLHE.
    focus         = (body.get('focus') or 'adaptive').strip()

    # ── Gate freemium (média): cap diário + treino mirado é Pro (Free treina fundamentos) ──
    plan = (getattr(g, 'user', None) or {}).get('plan', 'free')
    gate_active, grace_until = _training_gate_status()
    # rampa suave: durante o período de transição, todo mundo treina como Pro
    lim  = PLAN_LIMITS.get(plan, PLAN_LIMITS['free']) if gate_active else PLAN_LIMITS['pro']
    cap  = lim.get('training_spots_per_day')
    if cap is not None:
        used = get_training_spots_today(g.user_id, tz_offset)
        if used >= cap:
            return jsonify({'spot': None, 'session_state': session_state,
                            'limit_reached': True, 'requires_pro': True,
                            'used': used, 'cap': cap}), 200
    # Free: sem treino MIRADO (adaptive/leak reais) → cai em fundamentos genéricos (preflop),
    # que de quebra já exclui postflop. O front mostra o upsell via targeted_locked.
    targeted_locked = False
    from leaklab.leak_trainer import FREE_CATALOG_FOCUSES
    # Entradas de catálogo que SÃO fundamentos (BvB, stack curto) treinam no Free como os
    # fund:*; postflop e adaptativo seguem o gate do plano.
    if (not lim.get('leak_targeted', True) and not focus.startswith('fund:')
            and focus not in FREE_CATALOG_FOCUSES):
        focus = 'adaptive'          # normaliza; abaixo forçamos fundamentos
        targeted_locked = True
    try:
        if targeted_locked:
            spot = next_spot(_fundamentals_curriculum(), session_state)
        elif focus == 'fund:range_grid':
            # Treino de FRONTEIRA na grade: marcar uma família inteira (Áses suited, pares…).
            # Não passa por next_spot/currículo: não é um spot de decisão, é de memorização, e
            # o adaptativo por categoria de leak não se aplica.
            #
            # Quem escolhe a carta é o SRS, e não o sorteio: sorteio dá a mesma chance à carta
            # que ele domina e à que nunca viu, e nunca traz de volta o erro na hora em que ele
            # estaria esquecendo. `servidas` chega do cliente porque a carta só ganha linha no
            # banco DEPOIS de corrigida — sem isso a mesma carta poderia voltar na sequência.
            from leaklab.leak_trainer import proximo_card_de_range, sugerir_memorizacao_de_range
            _alvo = None
            try:
                _sug = sugerir_memorizacao_de_range(g.user_id, days=days)
                _alvo = (_sug or {}).get('position')
            except Exception:
                logger.exception('falha ao mirar a carta de range')
            spot = proximo_card_de_range(g.user_id,
                                         servidas=(body.get('servidas') or []),
                                         alvo=_alvo)
        elif focus.startswith('cat:'):
            # Catálogo de treinos nomeados (Fase 1, 17/08): BvB, stack curto, catálogos
            # postflop. Currículo vem da fonte única; id desconhecido → lista vazia → o
            # fallback de fundamentos abaixo segura (nunca 500).
            from leaklab.leak_trainer import curriculo_do_catalogo
            curriculum = curriculo_do_catalogo(focus.split(':', 1)[1], g.user_id)
            spot       = next_spot(curriculum, session_state) if curriculum else \
                         next_spot(_fundamentals_curriculum(), session_state)
        elif focus.startswith('fund:'):
            curriculum = fundamentals_catalog(focus.split(':', 1)[1])
            spot       = next_spot(curriculum, session_state)
        elif focus.startswith('leak:'):
            key = focus.split(':', 1)[1]
            full = build_curriculum(g.user_id, days=days)
            filtrado = [c for c in full if c.get('key') == key]
            # Regra 6: o fallback era `or full` CALADO — o deep-link prometia um leak e o
            # adaptativo servia outro sem ninguém saber (pego ao vivo na auditoria da
            # jornada). O fallback continua (tela vazia é pior), mas agora AVISA.
            _fallback = not filtrado
            curriculum = filtrado or full
            spot       = next_spot(curriculum, session_state)
            if _fallback and spot is not None:
                spot['focus_fallback'] = True
        else:
            curriculum = build_curriculum(g.user_id, days=days)
            spot       = next_spot(curriculum, session_state)
    except Exception:
        # uma categoria/query ruim não pode derrubar a página — cai em fundamentos (preflop, sem DB)
        app.logger.exception("leaktrainer_next falhou (user=%s) — fallback fundamentos", g.user_id)
        try:
            spot = next_spot(_fundamentals_curriculum(), session_state)
        except Exception:
            app.logger.exception("leaktrainer_next fallback também falhou")
            spot = None
    return jsonify({'spot': spot, 'session_state': session_state,
                    'targeted_locked': targeted_locked, 'plan': plan, 'grace_until': grace_until})


@app.route('/player/progression/missions', methods=['GET'])
@require_auth
def progression_missions():
    """PIP: os top-3 leaks como MISSÕES, por EV ponderado por confiança (amostra pequena nunca
    lidera o plano). Cada missão traz o vínculo com o jogo real — é o que dá sentido ao treino."""
    from leaklab.progression import build_missions
    days = int(request.args.get('days', 90) or 90)
    try:
        missions = build_missions(g.user_id, days=days)
    except Exception:
        app.logger.exception("progression_missions falhou (user=%s)", g.user_id)
        missions = []
    return jsonify({'missions': missions})


@app.route('/player/progression/status', methods=['GET'])
@require_auth
def progression_status():
    """Estado de cada missão nos 3 níveis: em treino → dominado no treino → comprovado no jogo.

    O gate de PROGRESSÃO é o treino (rápido, amostra infinita); o SELO é o jogo real. Nunca
    dizemos 'corrigido' antes dos uploads confirmarem — é o que separa isto de um simulador.
    Os critérios voltam com progresso porque o gate é transparente de propósito: mistério faz
    o jogador desistir.

    O foco (`ativa`) sai de `missions_with_state`, a MESMA função que o plano de sessão usa —
    se a tela e o treino resolvessem o foco por conta própria, avançar de leak no painel não
    mudaria o que é servido no drill."""
    from leaklab.progression import missions_with_state
    days = int(request.args.get('days', 90) or 90)
    try:
        est = missions_with_state(g.user_id, days=days)
    except Exception:
        app.logger.exception("progression_status falhou (user=%s)", g.user_id)
        return jsonify({'items': [], 'ativa': None, 'proximas': [], 'dominadas': [], 'restantes': 0})
    # F2 do cockpit: a aula ligada à MISSÃO (a Academia contextual — o link genérico saiu das
    # telas de treino em 19/08 e a volta dela é por vínculo real, nunca por atalho solto).
    # Mesmo matcher do plano de estudos (academy_catalog) — fonte única do leak→aula.
    try:
        from leaklab.academy_catalog import modules_for_card
        if est.get('ativa'):
            a = est['ativa']
            a['academy_modules'] = modules_for_card({
                'titulo': a.get('titulo') or '',
                'spot': f"{a.get('scenario') or ''} {a.get('position') or ''} vs {a.get('vs_position') or ''}",
            })
    except Exception:
        app.logger.exception("academy_modules da missão falhou (user=%s)", g.user_id)
    # Enxerto (20/08): o CONCEITO do spot na tela, não só o link da aula — o mesmo
    # `concept_for_spot` que o feedback do drill já usa (fonte única do gatilho/princípio).
    try:
        from leaklab.progression import concept_for_spot
        if est.get('ativa'):
            est['ativa']['concept'] = concept_for_spot(est['ativa'])
    except Exception:
        app.logger.exception("concept da missão falhou (user=%s)", g.user_id)
    return jsonify(est)


@app.route('/player/progression/session', methods=['POST'])
@require_auth
def progression_session():
    """Abre a sessão: escolhe a missão e devolve o PLANO (quantos spots de cada fatia).
    O plano é stateless — o cliente ecoa o progresso no /next e o servidor nunca confia nele
    pra nada além de compor a sessão (o gabarito segue server-side)."""
    from leaklab.progression import plan_session, SESSION_SIZES, DEFAULT_SESSION
    from database.repositories import get_training_skills
    body = request.get_json(silent=True) or {}
    size = (body.get('size') or DEFAULT_SESSION).strip().lower()
    if size not in SESSION_SIZES:
        size = DEFAULT_SESSION
    days = int(body.get('days', 90) or 90)
    # Revisão = categorias JÁ praticadas (as que têm domínio registrado). Sem histórico o
    # plano devolve o espaço pra missão em vez de inventar revisão.
    try:
        review_keys = [s['category_key'] for s in get_training_skills(g.user_id)
                       if int(s.get('attempts') or 0) > 0]
    except Exception:
        review_keys = []
    try:
        plan = plan_session(g.user_id, size=size, days=days, review_keys=review_keys)
    except Exception:
        app.logger.exception("progression_session falhou (user=%s)", g.user_id)
        return jsonify({'plan': None, 'error': 'falha ao montar a sessão'}), 200
    return jsonify({'plan': plan})


@app.route('/player/progression/next', methods=['POST'])
@require_auth
def progression_next():
    """Próximo spot da sessão, respeitando a composição já cumprida (interleaving real).
    A resposta certa NUNCA vai no /next — só no /grade, como no resto do trainer."""
    from leaklab.progression import next_spot_for_plan, contrast_note
    body = request.get_json(silent=True) or {}
    plan = body.get('plan') or {}
    done = body.get('done') or {}
    try:
        spot = next_spot_for_plan(plan, done)
    except Exception:
        app.logger.exception("progression_next falhou (user=%s)", g.user_id)
        spot = None
    nota = contrast_note(spot) if spot else None
    return jsonify({'spot': spot, 'contrast_note': nota})


@app.route('/player/proximo-passo', methods=['GET'])
@require_auth
def player_proximo_passo():
    """A prescrição única de treino (spec cobranca-proximo-passo.md §2). Dashboard, sino e
    resposta do upload consomem ISTO — recalcular precedência no cliente é proibido pela spec,
    porque superfícies que decidem sozinhas divergem."""
    from leaklab.proximo_passo import montar_proximo_passo
    origem = (request.args.get('origem') or 'api').strip()[:24]
    # tz do ALUNO: a semana da meta vira segunda 00:00 no fuso dele, não no do servidor. Sem
    # isto, quem treina 21h no Brasil conta o dia (e às vezes a semana) errado.
    try:
        tz = int(request.args.get('tz_offset_min') or 0)
    except ValueError:
        tz = 0
    return jsonify(montar_proximo_passo(g.user_id, origem=origem, tz_offset_min=tz))


@app.route('/player/meta-semanal', methods=['POST'])
@require_auth
def player_meta_semanal():
    """O aluno declara em quantos dias por semana se compromete a treinar (Fase 3).

    A pergunta é em DIAS e a medida é em dias: `progression_attempts` não tem identidade de
    sessão, então "sessões por semana" seria um número que não responde à pergunta feita.
    """
    from database.repositories import set_meta_semanal
    from leaklab.meta_semanal import OPCOES
    body = request.get_json(silent=True) or {}
    if not set_meta_semanal(g.user_id, body.get('dias')):
        return jsonify({'error': 'meta inválida', 'opcoes': list(OPCOES)}), 400
    from leaklab.proximo_passo import meta_semanal_de
    try:
        tz = int(body.get('tz_offset_min') or 0)
    except (TypeError, ValueError):
        tz = 0
    return jsonify({'ok': True, 'meta_semanal': meta_semanal_de(g.user_id, tz)})


@app.route('/player/leaktrainer/full-hand/next', methods=['POST'])
@require_auth
def leaktrainer_full_hand_next():
    """Mão INTEIRA heads-up (Fase 3): sorteia uma mão real jogável ponta a ponta do acervo
    compartilhado. Payload anonimizado POR CONSTRUÇÃO (test_mao_completa varre e falha se
    vazar identificador); `chave` de dedup é hash opaco. Pro, como o Ghost (mão real)."""
    from database.repositories import PLAN_LIMITS
    from leaklab import mao_completa as mc
    plan = (getattr(g, 'user', None) or {}).get('plan', 'free')
    gate_active, _ = _training_gate_status()
    if gate_active and not PLAN_LIMITS.get(plan, PLAN_LIMITS['free']).get('ghost', False):
        return jsonify({'hand': None, 'requires_pro': True, 'feature': 'full_hand'}), 200
    body = request.get_json(force=True) or {}
    evitar = {str(x) for x in (body.get('evitar') or [])[:300]}
    import random as _r
    linhas, chave = mc.mao_jogavel(_resolve_best_action_from_node, _r.Random(), evitar)
    if not linhas:
        return jsonify({'hand': None})
    payload = mc.montar_mao(linhas, *chave)
    if not payload:
        return jsonify({'hand': None})
    payload['chave'] = mc.chave_opaca(*chave)
    return jsonify({'hand': payload})


@app.route('/player/leaktrainer/full-hand/grade', methods=['POST'])
@require_auth
def leaktrainer_full_hand_grade():
    """Corrige UM passo da mão inteira por `grade_drill_action` (fonte única do Ghost).
    Sem SRS: o SRS é do Ghost do DONO da mão. Resposta com whitelist de campos — o veredito
    não pode virar a porta por onde a identidade vaza."""
    from leaklab import mao_completa as mc
    body = request.get_json(force=True) or {}
    try:
        ref = int(body.get('ref') or 0)
    except (TypeError, ValueError):
        ref = 0
    action = (body.get('action') or '').lower()
    if not ref or not action:
        return jsonify({'found': False}), 400
    try:
        res = mc.corrigir_passo(ref, action, grade_drill_action)
    except Exception:
        logger.exception('full-hand/grade falhou (user=%s ref=%s)', g.user_id, ref)
        res = None
    if res is None:
        return jsonify({'found': False}), 404
    # Estatística persistente do card do catálogo — mesma porta dos outros treinos.
    try:
        from database.repositories import record_training_attempt
        record_training_attempt(g.user_id, 'fh:full_hand', bool(res.get('is_correct')))
    except Exception:
        logger.exception('full-hand: record_training_attempt falhou (user=%s)', g.user_id)
    permitidos = ('is_correct', 'gto_tier', 'mixed', 'best_action', 'gto_freqs',
                  'validation_source', 'gto_off_tree', 'new_action', 'gto_freq')
    return jsonify({'found': True, **{k: res.get(k) for k in permitidos if k in res}})


@app.route('/player/leaktrainer/range-classes', methods=['POST'])
@require_auth
def leaktrainer_range_classes():
    """Painel "range por classe de mão" de um spot postflop do trainer: a hand_table da árvore
    que CORRIGE o spot, agrupada por classe (trinca+, top pair, draw...) com a estratégia média
    ponderada pelo peso. Display-only: nada daqui alimenta veredito, score ou SRS.

    O spot volta do cliente como no /grade, mas a VERDADE é lida do banco: o tree_hash do pool
    (ou o re-derivado pelo mesmo lookup da correção) escolhe a árvore, e a tabela vem de lá.
    O que o cliente poderia adulterar muda só o rótulo do painel dele mesmo."""
    from leaklab.leak_trainer import arvore_do_spot
    from leaklab.range_classes import range_por_classe
    body = request.get_json(force=True) or {}
    spot = body.get('spot') or {}
    if spot.get('kind') != 'postflop' or not spot.get('board'):
        return jsonify({'found': False})
    try:
        th = arvore_do_spot(spot)
        painel = range_por_classe(th, spot.get('board') or [],
                                  float(spot.get('facing_size_bb') or 0) > 0) if th else None
    except Exception:
        logger.exception('range-classes falhou (user=%s)', g.user_id)
        painel = None
    if not painel:
        return jsonify({'found': False})
    return jsonify({'found': True, **painel})


@app.route('/player/leaktrainer/options', methods=['GET'])
@require_auth
def leaktrainer_options():
    """Opções do seletor de treino: os LEAKS reais do jogador (com domínio, ordenados por EV) +
    os CENÁRIOS de fundamentos (rfi/vs_rfi/vs_3bet) pra explorar mesmo sem leak medido. O drill
    filtra por 'focus' (leak:<key> | fund:<scenario> | adaptive)."""
    from leaklab.leak_trainer import build_curriculum, TRAINABLE_SCENARIOS
    from database.repositories import get_training_skills
    skills = {s['category_key']: s for s in get_training_skills(g.user_id)}
    leaks = []
    try:
        for c in build_curriculum(g.user_id):
            if int(c.get('n') or 0) <= 0:                        # só leaks REAIS medidos (sem fund./piloto)
                continue
            if c.get('scenario') not in TRAINABLE_SCENARIOS:     # só o que o drill consegue servir
                continue
            s = skills.get(c['key'])
            leaks.append({
                'category_key': c['key'], 'scenario': c.get('scenario'),
                'position': c.get('position'), 'vs_position': c.get('vs_position', ''),
                'stack_bb': c.get('stack_bb'), 'ev_loss_bb': round(float(c.get('ev_loss_bb') or 0), 1),
                'mastery': (s['mastery'] if s else 0.0), 'tier': (s['tier'] if s else 'bronze'),
            })
    except Exception:
        app.logger.exception("leaktrainer_options: build_curriculum falhou (user=%s)", g.user_id)
    # Memorizacao de range: a SUGESTAO (a partir dos leaks reais) e o placar do SRS. Sem isto o
    # exercicio so aparece para quem abre "Treinar outra coisa" e ja sabe que precisa dele — que
    # e exatamente quem menos precisa. Quem erra a abertura do LJ acha que errou aquela mao.
    memorizacao = None
    try:
        from leaklab.leak_trainer import sugerir_memorizacao_de_range
        from database.repositories import resumo_das_cartas_de_range
        memorizacao = {
            'sugestao': sugerir_memorizacao_de_range(g.user_id),
            'placar':   resumo_das_cartas_de_range(g.user_id),
        }
    except Exception:
        app.logger.exception("leaktrainer_options: memorizacao falhou (user=%s)", g.user_id)
    # Catálogo de treinos NOMEADOS (Fase 1, 17/08): a porta de quem chega sabendo o que quer.
    # Nome/descrição são i18n do frontend (chaveados por `id`); o backend manda o roteável
    # (focus) e a estatística agregada da persistência que JÁ existia (training_skill_progress).
    catalogo = []
    try:
        from leaklab.leak_trainer import CATALOGO_TREINOS, stats_do_catalogo
        _stats = stats_do_catalogo(list(skills.values()))
        catalogo = [{**{k: e[k] for k in ('id', 'focus', 'grupo', 'free')},
                     'stats': _stats.get(e['id'])} for e in CATALOGO_TREINOS]
    except Exception:
        app.logger.exception("leaktrainer_options: catalogo falhou (user=%s)", g.user_id)
    return jsonify({'leaks': leaks, 'scenarios': TRAINABLE_SCENARIOS,
                    'memorizacao': memorizacao, 'catalogo': catalogo})


@app.route('/player/leaktrainer/grade', methods=['POST'])
@require_auth
def leaktrainer_grade():
    """Corrige a ação NO SERVIDOR via analyze_preflop — a range nunca sai do servidor. XP por acerto."""
    from leaklab.leak_trainer import grade_canonical_spot, grade_range_grid_spot
    body   = request.get_json(force=True) or {}
    spot   = body.get('spot') or {}
    action = (body.get('action') or '').lower()
    # Marcação de família: a resposta é um CONJUNTO de mãos, não uma ação. Corrigido aqui e não
    # dentro de grade_canonical_spot porque o formato da resposta é outro — enfiar os dois na
    # mesma função obrigaria cada chamador a saber qual dos dois contratos está em jogo.
    if spot.get('kind') == 'range_grid':
        res = grade_range_grid_spot(spot, body.get('marcadas') or [])
        # Agenda a revisao. Range e MEMORIZACAO: sem reencontro programado o exercicio vira
        # exposicao, e o jogador reencontra por sorteio o que ja sabe enquanto esquece o resto.
        try:
            from database.repositories import registrar_carta_de_range
            ck = spot.get('card_key') or spot.get('category') or ''
            if ck and not res.get('erro'):
                res['srs'] = registrar_carta_de_range(
                    g.user_id, ck, spot.get('position') or '', spot.get('familia') or '',
                    int(float(spot.get('stack_bb') or 50)), bool(res.get('acertou')))
        except Exception:
            logger.exception('falha ao agendar revisao da carta de range')
        return jsonify(res)
    result = grade_canonical_spot(spot, action)
    # Camada didática do Protocolo: o GATILHO do spot + a nota da classe de mão. Determinística
    # (sem LLM no caminho quente) e anexada aqui pra o corretor seguir sendo fonte única.
    try:
        from leaklab.progression import concept_for_spot, stratum_of, sizing_note
        result['concept'] = concept_for_spot(spot, result)
        # ENSINA o tamanho do raise (o dado tem: 'R2.1' = raise para 2,1bb). Não é uma segunda
        # pergunta: cada nó tem UM tamanho GTO, então perguntar viraria decoreba de tabela.
        _rec = (result.get('recommended') or [None])[0]
        result['sizing_note'] = sizing_note(spot, result.get('raise_to_bb'), _rec)
        # Loga a tentativa COM ESTRATO: é o que permite o gate saber se o jogador acerta na
        # fronteira ou só na parte fácil da range (acertar 90% foldando lixo não é domínio).
        # Atribui à MISSÃO quando o spot faz parte de uma sessão do protocolo: o spot de
        # contraste é de outra profundidade, mas a tentativa é evidência da missão em prova.
        _cat = spot.get('mission_key') or spot.get('category')
        if _cat:
            from database.repositories import record_progression_attempt
            # `origem` = por onde o aluno CHEGOU (dashboard/sino/email/pos_upload/espontanea).
            # É a métrica 1 da spec de cobrança: sem ela, "o trigger funciona?" vira opinião.
            record_progression_attempt(g.user_id, _cat, stratum_of(result),
                                       spot.get('block_kind'), bool(result.get('is_correct')),
                                       origem=(body.get('origem') or None))
    except Exception:
        app.logger.exception("camada de progressão falhou (user=%s)", g.user_id)
        result['concept'] = None
    xp_full = int(spot.get('xp_value', 20) or 20)
    # XP por RESULTADO (como o Ghost Table): acerto pleno = cheio; aceitável (linha co-ótima que o GTO
    # mistura) = parcial; erro = 0. add_xp atualiza XP global + streak + conquistas (sino).
    if result.get('gto_tier') == 'correct' and not result.get('mixed'):
        award = xp_full
    elif result.get('is_correct'):
        award = max(1, round(xp_full * 0.6))
    else:
        award = 0
    xp_gained, xp_total, new_achievements, events = 0, None, [], []
    if award:
        xp_res = add_xp(g.user_id, 'leaktrainer_correct', award)
        xp_gained = xp_res.get('xp_gained', award)
        xp_total = xp_res.get('xp_total')
        new_achievements = xp_res.get('new_achievements', [])
        events = ['leaktrainer_correct']
    result['xp'] = {'events': events, 'gained': xp_gained, 'total': xp_total, 'new_achievements': new_achievements}
    result['xp_awarded'] = xp_gained
    # Gamificação de treino: registra a tentativa por categoria e devolve o domínio
    # atualizado (antes→depois) pro veredito da lição. Eixo SEPARADO do ELO.
    _cat = spot.get('category')
    if _cat:
        try:
            from database.repositories import (record_training_attempt, evaluate_training_achievements,
                                               record_daily_mission_progress)
            result['training'] = record_training_attempt(g.user_id, _cat, bool(result.get('is_correct')))
            # conquistas de treino recém-desbloqueadas (pro veredito da lição comemorar).
            # `com_prova=False`: as medalhas de prova-no-jogo dependem de hand history nova, não
            # de responder um spot — e calculá-las aqui custava 2,7s POR CLIQUE. Quem as concede
            # é `/player/training/overview`, que já calcula a prova pra desenhar a tela.
            result['training_achievements'] = evaluate_training_achievements(g.user_id, com_prova=False)
            # missões diárias: incrementa contadores + auto-resgata as completas (XP).
            # tz_offset (min a leste do UTC, do frontend) → reset à meia-noite LOCAL do jogador.
            _tz = 0
            try:
                _tz = int((request.get_json(silent=True) or {}).get('tz_offset') or 0)
            except Exception:
                _tz = 0
            result['daily_missions'] = record_daily_mission_progress(
                g.user_id, bool(result.get('is_correct')), _tz)
        except Exception:
            app.logger.exception('record_training_attempt falhou (user=%s)', g.user_id)
            result['training'] = None
    return jsonify(result)


@app.route('/player/training/skills', methods=['GET'])
@require_auth
def training_skills():
    """Domínio de treino do jogador por categoria (eixo separado do ELO) — pro mapa/curso
    e pra marcar 'recomendado' (cruzando com os leaks reais)."""
    from database.repositories import get_training_skills
    return jsonify({'skills': get_training_skills(g.user_id)})


@app.route('/player/training/overview', methods=['GET'])
@require_auth
def training_overview():
    """Status do treino do jogador (eixo de gamificação, SEPARADO do ELO): XP+streak,
    domínio por habilidade e o catálogo de conquistas (com unlocked) — pro hub de Treino."""
    from database.repositories import (get_training_skills, get_training_achievements,
                                        get_daily_missions, training_readiness,
                                        get_training_proof, dominio_por_cenario)
    # A prova sai UMA vez e serve os dois consumidores: as conquistas (que contam provados,
    # reconquistados e com_amostra) e a tela. Medido antes: este endpoint fazia 115 idas ao banco,
    # 104 delas para recalcular exatamente esta prova lá dentro, e a tela ainda pedia `/proof` numa
    # segunda requisição — 219 idas para desenhar uma página. Ela vai no corpo porque quem já pagou
    # o cálculo devolvê-lo é de graça; `/player/training/proof` continua existindo.
    prova = get_training_proof(g.user_id)
    # ÚNICO ponto que concede as medalhas de prova-no-jogo. O corretor não pode fazê-lo (custaria
    # 2,7s por clique), e aqui a prova já está na mão. Antes de `get_training_achievements`, senão
    # a tela desenharia a medalha como bloqueada no mesmo instante em que ela foi conquistada.
    try:
        from database.repositories import evaluate_training_achievements
        evaluate_training_achievements(g.user_id, proof=prova)
    except Exception:
        app.logger.exception('overview: conceder conquistas de prova falhou (user=%s)', g.user_id)
    return jsonify({
        'xp':           get_xp_status(g.user_id),
        # O hub mostra DOMÍNIO, e domínio é por cenário: exibir as 54 chaves exatas (todas em
        # Bronze, ~4 tentativas cada) contradizia o veredito da lição, que fala do cenário. Duas
        # superfícies com o mesmo nome e números diferentes é a família de bug que já custou caro
        # aqui. A chave exata segue em `/player/training/skills`, para seleção e depuração.
        'skills':       sorted((dominio_por_cenario(g.user_id) or {}).values(),
                               key=lambda c: -float(c.get('mastery') or 0)),
        'achievements': get_training_achievements(g.user_id, proof=prova),  # conquistas de TREINO
        'missions':     get_daily_missions(g.user_id, _tz_offset_arg()),   # missões diárias (fuso local)
        'readiness':    training_readiness(g.user_id),          # gate 'Aplicar': todos os leaks no Diamante
        'proof':        prova,
    })


@app.route('/player/grind/hand', methods=['POST'])
@require_auth
def grind_proxima_mao():
    """Modo grind: uma MÃO REAL inteira, heads-up, para ser percorrida decisão a decisão.

    O que sai daqui é ANONIMIZADO por construção: posição e stack em BB, e nada mais. Sem nick, sem
    torneio, sem data — o identificador é um token opaco. As mãos são do acervo de todos, então
    isso é requisito de entrada e não acabamento de tela.
    """
    from leaklab.grind_mode import proxima_mao
    body = request.get_json(silent=True) or {}
    vistas = set(body.get('vistas') or [])
    try:
        mao = proxima_mao(evitar=vistas, min_decisoes=int(body.get('min_decisoes', 2) or 2))
    except Exception:
        app.logger.exception('grind: falha ao montar mão (user=%s)', g.user_id)
        mao = None
    return jsonify({'mao': mao, 'esgotou': mao is None})


@app.route('/player/grind/grade', methods=['POST'])
@require_auth
def grind_corrigir():
    """Corrige UM passo da mão. A resposta nunca sai do servidor antes disto."""
    from leaklab.grind_mode import corrigir_passo
    body = request.get_json(force=True) or {}
    passo = body.get('passo') or {}
    acao = (body.get('acao') or '').lower()
    try:
        res = corrigir_passo(passo, acao)
    except Exception:
        app.logger.exception('grind: falha ao corrigir passo (user=%s)', g.user_id)
        res = None
    if res is None:
        # Sem veredito possível: NÃO inventa. O front avança sem pontuar, e diz isso.
        return jsonify({'resultado': None, 'sem_veredito': True})
    return jsonify({'resultado': res, 'sem_veredito': False})


@app.route('/player/training/catalog', methods=['GET'])
@require_auth
def training_catalog():
    """Os treinos com NOME, para o jogador escolher o que praticar, com o histórico dele em cada um.

    Só apresentação: o foco de cada item é um valor que `/player/leaktrainer/next` já aceitava e que
    a tela já sabia abrir por `?foco=`. O que faltava era vitrine — a chave interna é
    `vs_3bet:HJ:BTN:50`, que ninguém pede em voz alta.
    """
    from leaklab.trainer_catalog import catalogo_do_jogador
    return jsonify({'drills': catalogo_do_jogador(g.user_id)})


@app.route('/player/training/daily-status', methods=['GET'])
@require_auth
def training_daily_status():
    """Nudge leve pro nav (selo "lição de hoje pendente"): a missão de lição do dia ainda não foi
    completa? Fuso LOCAL do jogador (?tz_offset=). Endpoint barato — 1 query."""
    from database.repositories import get_daily_missions
    missions = get_daily_missions(g.user_id, _tz_offset_arg())
    lesson = next((m for m in missions if m.get('key') == 'm_lesson'), None)
    return jsonify({'lesson_pending': bool(lesson and not lesson.get('completed'))})


@app.route('/player/training/proof', methods=['GET'])
@require_auth
def training_proof():
    """Fase 4 "Provar": compara a aderência GTO REAL (mãos, não drill) da categoria treinada
    ANTES × DEPOIS — o loop treino→jogo→prova. Honesto: % + amostra dos dois lados, sem crava causa."""
    from database.repositories import get_training_proof
    return jsonify({'proof': get_training_proof(g.user_id)})


@app.route('/player/strategic-twin', methods=['GET'])
@require_auth
def player_strategic_twin():
    gate = _check_advanced_insights(g.user_id)
    if gate:
        return gate
    from leaklab.llm_explainer import generate_twin_narrative
    lang    = request.args.get('lang', 'pt-BR')
    days    = int(request.args.get('days', 180))
    profile = get_strategic_twin_profile(g.user_id, days=days)
    if not profile.get("insufficient_data") and profile.get("costly_spots"):
        profile["narrative"] = generate_twin_narrative(profile, lang=lang)
    return jsonify(profile)


@app.route('/player/drill-sessions/reset', methods=['DELETE'])
@require_auth
def player_drill_sessions_reset():
    """Reseta histórico SRS do Ghost Table — todos os spots voltam para fila inicial."""
    deleted = reset_drill_sessions(g.user_id)
    return jsonify({'ok': True, 'deleted': deleted})


@app.route('/player/xp', methods=['GET'])
@require_auth
def player_get_xp():
    return jsonify(get_xp_status(g.user_id))


@app.route('/player/xp', methods=['POST'])
@require_auth
def player_add_xp():
    body = request.get_json(force=True) or {}
    result = add_xp(g.user_id, body.get('event_type', ''), body.get('amount'))
    return jsonify(result)


@app.route('/player/achievements', methods=['GET'])
@require_auth
def player_achievements():
    return jsonify({'achievements': get_achievements(g.user_id)})


# ── Coach Replay interativo — seus erros mais caros, revisados na mesa real ────
@app.route('/player/coach-replay/<tournament_id>', methods=['GET'])
@require_auth
def player_coach_replay(tournament_id):
    """Dados do Coach Replay do torneio: erros mais caros (com o que o herói fez × GTO) +
    plano. O front abre o replay real de cada mão. É a 'cura' → Pro (Free vê o upsell).
    `tournament_id` é o CÓDIGO do torneio (igual ao resto do app), não o id interno."""
    from database.repositories import PLAN_LIMITS
    from leaklab.coach_replay import build_coach_replay
    plan = (getattr(g, 'user', None) or {}).get('plan', 'free')
    if not PLAN_LIMITS.get(plan, PLAN_LIMITS['free']).get('advanced_insights', False):
        return jsonify({'requires_pro': True, 'feature': 'coach_replay'}), 200
    # resolve o código → torneio do usuário (aceita id interno como fallback, p/ compat)
    t = None
    if str(tournament_id).isdigit():
        t = get_tournament_by_db_id(g.user_id, int(tournament_id))
    if not t:
        t = get_tournament(g.user_id, tournament_id)
    if not t:
        return jsonify({'error': 'Torneio não encontrado'}), 404
    data = build_coach_replay(g.user_id, t['id'])
    if data is None:
        return jsonify({'error': 'Torneio não encontrado'}), 404
    return jsonify(data)


# ── Desafio do Dia (#42) ──────────────────────────────────────────────────────
def _challenge_day() -> str:
    from datetime import datetime
    return datetime.utcnow().strftime('%Y-%m-%d')


@app.route('/player/session/ritual', methods=['GET'])
@require_auth
def session_ritual():
    """O estado do ritual (30/08): check-in aberto (se houver) + foco sugerido do leak mais
    caro com amostra. Nunca bloqueia o dashboard: falha degrada para indisponível."""
    from leaklab.ritual_da_sessao import checkin_aberto, sugerir_foco
    try:
        return jsonify({'available': True,
                        'checkin': checkin_aberto(g.user_id),
                        'foco_sugerido': sugerir_foco(g.user_id)})
    except Exception:
        app.logger.exception('session/ritual falhou; degradando')
        return jsonify({'available': False})


@app.route('/player/session/checkin', methods=['POST'])
@require_auth
def session_checkin():
    """Abre o check-in SELANDO a linha de base do foco (o princípio do gabarito vetado:
    o debriefing compara contra a régua do momento da promessa)."""
    from leaklab.ritual_da_sessao import abrir_checkin
    body = request.get_json(silent=True) or {}
    bk = body.get('bankroll_ok')
    ck = abrir_checkin(g.user_id,
                       None if bk is None else bool(bk),
                       str(body.get('foco_spot') or '').strip() or None)
    return jsonify({'checkin': ck})


@app.route('/player/session/debrief/<int:tid>', methods=['GET'])
@require_auth
def session_debrief(tid):
    """O balanço da sessão: execução do foco vs base selada + mão gatilho + mãos caras.
    LER não fecha o check-in — fechar é ato explícito (POST abaixo)."""
    from leaklab.ritual_da_sessao import debrief
    d = debrief(g.user_id, tid)
    if d is None:
        return jsonify({'error': 'Torneio não encontrado'}), 404
    return jsonify(d)


@app.route('/player/session/checkin/<int:checkin_id>/close', methods=['POST'])
@require_auth
def session_checkin_close(checkin_id):
    from leaklab.ritual_da_sessao import fechar_checkin
    body = request.get_json(silent=True) or {}
    try:
        tid = int(body.get('tournament_id') or 0)
    except (TypeError, ValueError):
        tid = 0
    return jsonify({'ok': fechar_checkin(g.user_id, checkin_id, tid)})


@app.route('/player/daily-challenge', methods=['GET'])
@require_auth
def player_daily_challenge():
    """Spot APROVADO do dia (sem a resposta) + tentativa do usuário (se já fez) + stats.
    Serve SÓ do pool vetado; se não há spot aprovado pro dia, retorna available=False."""
    from database.repositories import (get_today_challenge, get_challenge_attempt, get_challenge_stats)
    import json as _json
    day = _challenge_day()
    # Blindagem: o desafio NUNCA pode derrubar a tela de treino. Qualquer falha (borda de
    # Postgres, spot corrompido) degrada pra "sem desafio hoje" e loga, em vez de 500.
    try:
        ch = get_today_challenge(day)
        if not ch:
            return jsonify({'available': False, 'day': day})
        spot = _json.loads(ch['spot_json'])
        attempt = get_challenge_attempt(g.user_id, day)
        stats = get_challenge_stats(day)
        out = {
            'available': True, 'day': day,
            'spot': {k: spot.get(k) for k in ('scenario', 'position', 'vs_position', 'stack_bb',
                                              'facing_size', 'hand', 'hero_cards', 'options', 'board')},
            'answered': attempt is not None,
            'stats': stats,
        }
        if attempt:
            # já respondeu: devolve o veredito (regrada pra não guardar texto), sem re-registrar
            from leaklab.daily_challenge import grade_challenge
            g_res = grade_challenge(ch['spot_json'], attempt['chosen_action'], answer=ch.get('answer'))
            out['result'] = {'chosen': attempt['chosen_action'], **g_res,
                             'teaching': ch.get('explanation') or ''}
        return jsonify(out)
    except Exception:
        app.logger.exception('daily-challenge GET falhou; degradando para available=False')
        return jsonify({'available': False, 'day': day})


@app.route('/player/daily-challenge/submit', methods=['POST'])
@require_auth
def player_daily_challenge_submit():
    """Grada a decisão do jogador (1 tentativa/dia), devolve veredito + explicação,
    e conta no dia de treino (alimenta a Liga #32)."""
    from database.repositories import (get_today_challenge, get_challenge_attempt,
                                       record_challenge_attempt, get_challenge_stats,
                                       record_daily_mission_progress)
    from leaklab.daily_challenge import grade_challenge
    day = _challenge_day()
    ch = get_today_challenge(day)
    if not ch:
        return jsonify({'error': 'Sem desafio disponível hoje'}), 404
    if get_challenge_attempt(g.user_id, day):
        return jsonify({'error': 'Você já respondeu o desafio de hoje', 'code': 'already_answered'}), 409
    action = (request.get_json(silent=True) or {}).get('action', '')
    if not action:
        return jsonify({'error': 'action obrigatória'}), 400
    res = grade_challenge(ch['spot_json'], action, answer=ch.get('answer'))
    record_challenge_attempt(g.user_id, day, res['played'], res.get('gto_tier') or '', res['is_correct'])
    try:
        record_daily_mission_progress(g.user_id, bool(res['is_correct']))   # conta no dia → Liga #32
    except Exception:
        pass
    return jsonify({'result': {'chosen': res['played'], **res, 'teaching': ch.get('explanation') or ''},
                    'stats': get_challenge_stats(day)})


@app.route('/admin/daily-challenge/generate', methods=['POST'])
@require_admin
def admin_daily_challenge_generate():
    """Gera N candidatos pro pool, status='pending' pra curadoria.

    `difficulty` (facil|medio|dificil) escolhe a faixa de frequência do GTO. O padrão é
    `dificil`: spot de resposta unânime é respondido no automático e não separa quem sabe.
    O nível fácil continua disponível, sob pedido explícito."""
    from leaklab.daily_challenge import build_candidates, DIFFICULTIES, DEFAULT_DIFFICULTY
    from database.repositories import add_challenge_candidates
    body = request.get_json(silent=True) or {}
    n = int(body.get('n', 10) or 10)
    n = max(1, min(n, 50))
    diff = str(body.get('difficulty') or DEFAULT_DIFFICULTY).lower()
    if diff not in DIFFICULTIES:
        diff = DEFAULT_DIFFICULTY
    # `verify` liga o voto adversarial (camada 4): N peritos independentes tentam derrubar o
    # gabarito antes de o candidato chegar à sua fila de aprovação. Ligado por padrão — o motivo
    # de cada descarte vai pro log do container.
    verify = bool(body.get('verify', True))
    cands = build_candidates(n, difficulty=diff, verify=verify)
    added = add_challenge_candidates(cands)
    return jsonify({'generated': added, 'difficulty': diff, 'verified': verify})


@app.route('/admin/daily-challenge/revalidate', methods=['POST'])
@require_admin
def admin_daily_challenge_revalidate():
    """Revalida o pool contra os gates de HOJE (30/08: 'certeza GTO' vale para o acervo).
    `dry_run=true` só mede. Reprovados viram 'retired_gto' e saem do sorteio."""
    from leaklab.daily_challenge import revalidar_pool
    body = request.get_json(silent=True) or {}
    return jsonify(revalidar_pool(aplicar=not bool(body.get('dry_run'))))


@app.route('/admin/daily-challenge/pool', methods=['GET'])
@require_admin
def admin_daily_challenge_pool():
    from database.repositories import list_challenge_candidates, count_approved_challenges
    from leaklab.daily_challenge import describe_challenge
    import json as _json
    status = request.args.get('status')
    rows = list_challenge_candidates(status=status)
    for r in rows:
        try:
            r['spot'] = _json.loads(r.pop('spot_json'))
            r['context'] = describe_challenge(r['spot'])   # contexto rico p/ curadoria
        except Exception:
            r['spot'] = {}
            r['context'] = None
    # os mais DESAFIADORES primeiro (contraintuitivos / com mistura), pra curar melhor
    rows.sort(key=lambda x: (x.get('context') or {}).get('challenge_score', 0), reverse=True)
    return jsonify({'pool': rows,
                    'approved_unused': count_approved_challenges(unused_only=True)})


@app.route('/admin/daily-challenge/<int:pool_id>/status', methods=['POST'])
@require_admin
def admin_daily_challenge_status(pool_id):
    from database.repositories import set_challenge_status
    status = (request.get_json(silent=True) or {}).get('status', '')
    if status not in ('approved', 'rejected', 'pending'):
        return jsonify({'error': 'status inválido'}), 400
    set_challenge_status(pool_id, status)
    return jsonify({'ok': True})


@app.route('/admin/daily-challenge/reset-my-attempt', methods=['POST'])
@require_admin
def admin_daily_challenge_reset_my_attempt():
    """Reteste: apaga a tentativa de HOJE do próprio admin, pra responder o desafio de novo.
    Admin-only (jogador comum não pode furar o 1/dia)."""
    from database.repositories import reset_challenge_attempt
    removed = reset_challenge_attempt(g.user_id, _challenge_day())
    return jsonify({'ok': True, 'removed': removed})


# ── Session Goals — FEAT-08 ───────────────────────────────────────────────────


@app.route('/player/session-review/<int:tournament_id>', methods=['GET'])
@require_auth
def player_session_review(tournament_id: int):
    """Returns the session goal linked to a tournament and an AI review (Pro only)."""
    goal_row = get_session_goal_for_tournament(g.user_id, tournament_id)

    if not goal_row:
        return jsonify({'goal': None, 'review': None, 'requires_pro': False})

    goal = {
        'goal_leak_spot':      goal_row.get('goal_leak_spot'),
        'target_standard_pct': goal_row.get('target_standard_pct'),
        'notes':               goal_row.get('notes'),
    }

    user_plan = g.user.get('plan', 'free')
    is_pro    = user_plan in ('pro', 'coach')
    review    = goal_row.get('llm_review')

    # Generate and cache review for Pro users on first access
    if is_pro and not review:
        try:
            t = get_tournament_by_db_id(g.user_id, tournament_id)
            if t:
                review = _gen_session_review(goal, dict(t))
                if review:
                    save_session_goal_review(goal_row['id'], review)
        except Exception:
            review = None

    return jsonify({'goal': goal, 'review': review, 'requires_pro': not is_pro})


def _gen_session_review(goal: dict, tournament: dict) -> str | None:
    """Calls Claude Haiku to compare session goal vs actual performance."""
    import os, requests as _req
    api_key = os.environ.get('ANTHROPIC_API_KEY', '')
    if not api_key:
        return None

    spot       = goal.get('goal_leak_spot') or 'sem foco específico'
    target_pct = goal.get('target_standard_pct')
    notes      = goal.get('notes') or ''
    actual_pct = tournament.get('standard_pct')
    avg_score  = tournament.get('avg_score')
    hands      = tournament.get('hands_count', 0)

    lines = [f"Foco de trabalho: {spot}"]
    if target_pct is not None:
        lines.append(f"Meta de standard%: {target_pct}%")
    if notes:
        lines.append(f"Anotações: {notes}")
    lines.append("")
    if actual_pct is not None:
        lines.append(f"Standard% real: {actual_pct:.1f}%")
    if avg_score is not None:
        lines.append(f"Score médio de erro: {avg_score:.3f}")
    if hands:
        lines.append(f"Mãos analisadas: {hands}")

    prompt = (
        "Você é um coach de poker MTT. O jogador definiu um objetivo antes deste torneio. "
        "Escreva um review técnico e direto (3-4 frases) comparando objetivo vs resultado real. "
        "Comece indicando se o objetivo foi atingido. Use **negrito** para os pontos-chave. "
        "Português do Brasil. Termos de poker em inglês (fold, call, raise, equity, etc.).\n\n"
        + "\n".join(lines)
    )

    try:
        resp = _req.post(
            'https://api.anthropic.com/v1/messages',
            json={
                'model':      'claude-haiku-4-5-20251001',
                'max_tokens': 300,
                'messages':   [{'role': 'user', 'content': prompt}],
            },
            headers={
                'Content-Type':      'application/json',
                'anthropic-version': '2023-06-01',
                'x-api-key':         api_key,
            },
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
        return ''.join(
            b['text'] for b in data.get('content', []) if b.get('type') == 'text'
        ).strip() or None
    except Exception:
        return None


@app.route('/player/spots/drill/<int:decision_id>/table', methods=['GET'])
@require_auth
def player_drill_table(decision_id: int):
    """Ghost Table visual: estado FIEL da mesa no ponto da decisão (parse lazy do HH).
    Devolve seats[] (stack/bet em BB, folded, hero), button, pot, board, hero_cards."""
    from database.repositories import get_decision_hand_context
    from leaklab.parser import parse_hand_history
    from leaklab.hand_state_builder import build_table_state_at_decision
    ctx = get_decision_hand_context(g.user_id, decision_id)
    if not ctx or not ctx.get('raw_text'):
        return jsonify({'error': 'Contexto da mão indisponível'}), 404
    hand_id = ctx.get('hand_id')
    street  = ctx.get('street') or 'preflop'
    try:
        hand = next((h for h in parse_hand_history(ctx['raw_text']) if h.hand_id == hand_id), None)
    except Exception as e:
        log.warning("drill table parse error dec=%s: %s", decision_id, e)
        hand = None
    if not hand:
        return jsonify({'error': 'Mão não encontrada no histórico'}), 404
    # target_facing desambigua quando o hero age 2+× na street (para no momento certo).
    _tf = ctx.get('facing_bet')
    state = build_table_state_at_decision(hand, street, target_facing=_tf)
    bb = float(state.get('bb') or ctx.get('level_bb') or 0) or 1.0
    # seats em CHIPS (stack/bet crus) — o PokerTableV3 normaliza p/ BB via betUnit + bb.
    # BUG A: o pot vem do builder (carried_pot dos streets anteriores + bets da street
    # atual). NÃO recomputar via sum(seat.bet) — isso descartava o pote de streets passados
    # (postflop first-to-act rendia pote 0). state['pot'] já inclui os bets correntes.
    pot_chips = round(float(state.get('pot') or 0.0), 1)
    _sc = {'preflop': 0, 'flop': 3, 'turn': 4, 'river': 5}
    board = (hand.board or [])[:_sc.get(street, 5)]
    return jsonify({
        'seats':      state['seats'],
        'button':     state.get('button'),
        'pot':        pot_chips,
        'bb_chips':   bb,
        'street':     street,
        'board':      board,
        'hero_cards': hand.hero_cards,
    })


@app.route('/player/spots/drill/<int:decision_id>/analysis', methods=['GET'])
@require_auth
def player_drill_analysis(decision_id: int):
    """Sprint K — Análise LLM on-demand de uma decisão do drill, com cache no banco."""
    from database.repositories import get_llm_cache, set_llm_cache

    cache_key = f'drill_analysis:{decision_id}'
    cached = get_llm_cache(g.user_id, cache_key)
    if cached:
        return jsonify({'analysis': cached, 'cached': True})

    row = get_decision_for_drill(g.user_id, decision_id)
    if not row:
        return jsonify({'error': 'Decisão não encontrada'}), 404

    try:
        from leaklab.llm_explainer import analyze_single_decision
        analysis = analyze_single_decision(dict(row))
        set_llm_cache(g.user_id, cache_key, analysis)
        return jsonify({'analysis': analysis, 'cached': False})
    except Exception as e:
        return jsonify({'error': f'Análise indisponível: {str(e)}'}), 503


# ── Coach: nível do aluno ────────────────────────────────────────────────────

@app.route('/coach/student/<int:student_id>/level', methods=['GET'])
@require_coach
def student_level(student_id: int):
    if not _verify_student(g.user_id, student_id):
        return jsonify({'error': 'Aluno não encontrado'}), 404
    return jsonify(get_player_level(student_id))


# ── AI Coach conversacional ──────────────────────────────────────────────────

@app.route('/coach/chat', methods=['POST'])
@require_auth
def coach_chat():
    data    = request.get_json(silent=True) or {}
    message = data.get('message', '').strip()
    if not message:
        return jsonify({'error': 'Mensagem obrigatória'}), 400

    # Gate: AI Coach Chat e exclusivo do plano Pro
    _plan = (g.user.get('plan') or 'free').lower()
    if not PLAN_LIMITS.get(_plan, PLAN_LIMITS['free']).get('ai_coach_chat', False):
        return jsonify({
            'error': 'AI Coach Chat exclusivo do plano Pro',
            'upgrade_required': True,
        }), 402

    # Fase 2 — teto DIÁRIO (fair-use anti-abuso/bot). 429 (não é upsell — Pro já tem acesso).
    from database.repositories import can_send_ai_chat, increment_ai_chat
    _chat_ok, _chat_rem = can_send_ai_chat(g.user_id)
    if not _chat_ok:
        return jsonify({
            'error': 'ai_chat_daily_limit',
            'message': 'Você atingiu o limite diário de mensagens do AI Coach Chat. Tente novamente amanhã.',
        }), 429

    message = sanitize_llm_input(message, max_len=1000)
    hero    = sanitize_llm_input(g.user.get('username', 'Jogador'), max_len=40)   # vai pro prompt do LLM

    # Caminho preferido: loop agêntico (o modelo busca só o dado relevante via tools).
    # Flag COACH_CHAT_AGENTIC=0 desliga; qualquer falha cai no single-shot legado.
    if os.getenv('COACH_CHAT_AGENTIC', '1') == '1':
        try:
            from leaklab.llm_explainer import coach_chat_reply_agentic
            result = coach_chat_reply_agentic(message, g.user_id, hero=hero)
            increment_ai_chat(g.user_id)   # conta a mensagem no teto diário
            return jsonify({
                'reply':      result['reply'],
                'source':     result.get('source', 'agentic'),
                'tools_used': result.get('tools_used', []),
            })
        except Exception:
            log.exception("coach_chat agentic error; fallback para single-shot")
            # cai no caminho legado abaixo

    # Single-shot legado: pré-carrega todo o contexto no prompt.
    from database.repositories import get_leak_ranking_gto_first, get_ev_leaks as _get_ev_leaks
    days        = 90
    leak_data   = get_leak_ranking_gto_first(g.user_id, days)
    leaks       = leak_data['leaks']
    leak_source = leak_data['source']
    evolution   = get_evolution_metrics(g.user_id, days) or []
    freqs       = get_player_action_frequencies(g.user_id, days)
    ev_leaks    = _get_ev_leaks(g.user_id, days).get('leaks')   # #24/#25: prioriza por bb

    try:
        reply = coach_chat_reply(message, leaks, evolution, hero=hero,
                                  frequencies=freqs, leak_source=leak_source, ev_leaks=ev_leaks)
        increment_ai_chat(g.user_id)   # conta a mensagem no teto diário
        return jsonify({'reply': reply, 'source': leak_source})
    except Exception as e:
        log.exception("coach_chat error")
        return jsonify({'error': 'Coach temporariamente indisponível'}), 500


@app.route('/coach/context', methods=['GET'])
@require_auth
def coach_context():
    from database.repositories import get_leak_ranking_gto_first
    days        = 90
    leak_data   = get_leak_ranking_gto_first(g.user_id, days)
    leaks       = leak_data['leaks']
    leak_source = leak_data['source']
    evolution   = get_evolution_metrics(g.user_id, days) or []
    tourns      = get_tournaments(g.user_id, limit=200)

    total_hands = sum(t.get('hands_count', 0) for t in tourns)

    avg_scores = [e['avg_score'] for e in evolution if e.get('avg_score') is not None]
    avg_score  = round(sum(avg_scores) / len(avg_scores), 4) if avg_scores else None

    std_pcts    = [e['standard_pct'] for e in evolution if e.get('standard_pct') is not None]
    standard_pct = round(sum(std_pcts) / len(std_pcts), 4) if std_pcts else None

    return jsonify({
        'hands_analyzed':       total_hands,
        'tournaments_analyzed': len(tourns),
        'top_leaks':            [{'spot': l['spot'], 'avg_score': l['avg_score'], 'n': l['n']} for l in leaks[:5]],
        'leak_source':          leak_source,
        'avg_score':            avg_score,
        'standard_pct':         standard_pct,
    })


# ── Coach endpoints ───────────────────────────────────────────────────────────

# NOTA: a rota /coach/students é servida por coach_students_v2 (abaixo) — que inclui
# trend + sinais de cockpit (is_active_paid, is_referred). A versão duplicada antiga
# (sem esses campos) foi removida: o Werkzeug casava a 1ª regra registrada e sombreava
# a v2, deixando o `trend` sempre vazio no front.


@app.route('/coach/students/leaderboard', methods=['GET'])
@require_coach
def coach_students_leaderboard():
    """Ranking dos PRÓPRIOS alunos do coach (#15 coach view) — nomes reais, sem
    filtro de opt-in (o coach sempre vê os números), read-only. Não compete entre
    coaches."""
    from database.repositories import get_coach_students_leaderboard
    from leaklab.leaderboard import (
        W_GTO, W_EVO, W_ENG, W_VOL, MIN_HANDS, MIN_TOURNAMENTS, MIN_GTO_DECISIONS,
    )
    period = request.args.get('period', default=90, type=int)
    result = get_coach_students_leaderboard(g.user_id, period_days=period)
    return jsonify({
        'period_days':  period,
        'weights':      {'gto': W_GTO, 'evolution': W_EVO, 'engagement': W_ENG, 'volume': W_VOL},
        'eligibility':  {'min_hands': MIN_HANDS, 'min_tournaments': MIN_TOURNAMENTS,
                         'min_gto_decisions': MIN_GTO_DECISIONS},
        'ranked':       result['ranked'],
        'ineligible':   result['ineligible'],
    })


@app.route('/coach/student/<int:student_id>/history', methods=['GET'])
@require_coach
def coach_student_history(student_id):
    # Verificar que o aluno pertence a este coach
    students = get_students(g.user_id)
    if not any(s['id'] == student_id for s in students):
        return jsonify({'error': 'Aluno não encontrado'}), 404
    from database.repositories import get_leak_ranking_gto_first
    days = int(request.args.get('days', 30))
    leak_data = get_leak_ranking_gto_first(student_id, days)
    return jsonify({
        'student_id':   student_id,
        'evolution':    get_evolution_metrics(student_id, days),
        'leaks':        leak_data['leaks'],
        'leak_source':  leak_data['source'],
        'icm':          get_icm_performance(student_id, days),
        'tournaments':  get_tournaments(student_id),
    })


# ── Util endpoints (sem auth — para o frontend offline) ──────────────────────

# Decisão de exemplo da landing / dashboard vazio.
#
# É uma análise REAL, produzida pela mesma pipeline do /replay sobre uma mão jogada de verdade,
# congelada por `scripts/gerar_decisao_exemplo.py`. O que existia antes era um card escrito à
# mão: números plausíveis e uma frase. Quem via aquilo não via o produto, via uma maquete dele.
#
# Por que congelada e não ao vivo: a landing é pública e deslogada. Servir ao vivo a mão de um
# jogador expõe dado dele a cada visita, sem que ele tenha pedido. A fixture não tem nick, id de
# mão nem id de torneio — a lista de campos que entra nela é BRANCA, no gerador.
#
# O preço, declarado: mudou o motor, o exemplo não acompanha sozinho. Rode o gerador de novo.
_FIXTURES_DEMO = _BASE / 'fixtures'
_fixtures_demo_cache: dict[str, dict] = {}


def _fixture_demo(nome: str):
    """Carrega e memoiza uma fixture de demonstração. Devolve `None` quando nao ha arquivo.

    Duas rotas publicas leem fixture do mesmo jeito (decisao e dashboard), entao a leitura vive
    aqui: a terceira nasce sem copiar o tratamento de erro, que e onde a copia costuma divergir.
    """
    if nome not in _fixtures_demo_cache:
        try:
            with open(_FIXTURES_DEMO / f'{nome}.json', encoding='utf-8') as f:
                _fixtures_demo_cache[nome] = json.load(f)
        except (OSError, ValueError) as e:
            log.warning('fixture de demonstracao "%s" indisponivel: %s', nome, e)
            return None
    return _fixtures_demo_cache[nome]


@app.route('/sample/decision', methods=['GET'])
@limiter.limit("60 per minute")
def sample_decision():
    """Uma decisão real e anonimizada, no formato que o Decision Card já consome."""
    dados = _fixture_demo('decisao_exemplo')
    if dados is None:
        # 404 e não 500: a ausência da fixture não é erro do cliente nem incidente de
        # servidor, e o frontend trata como "sem exemplo" sem quebrar a landing.
        return jsonify({'error': 'exemplo indisponível'}), 404
    return jsonify({'decision': dados})


@app.route('/sample/dashboard', methods=['GET'])
@limiter.limit("60 per minute")
def sample_dashboard():
    """Dashboard de DEMONSTRAÇÃO: os 19 payloads que a tela consome, de um jogador real.

    Existe porque o tour guiado precisa de uma tela POVOADA para apontar. Rodá-lo sobre o
    dashboard de quem acabou de se cadastrar seria apontar para cards vazios — e um tour que
    aponta para cards vazios ensina que o produto é vazio.

    Os números vêm da mesma pipeline dos endpoints reais (`scripts/gerar_dashboard_demo.py` bate
    neles via test client), o que garante duas coisas: a FORMA bate com o que o frontend espera,
    e os 13 cards são COERENTES entre si — o leak prioritário conversa com o EV perdido, que
    conversa com a cobertura GTO. Fabricar isso à mão erraria em silêncio.
    """
    dados = _fixture_demo('dashboard_demo')
    if dados is None:
        return jsonify({'error': 'demonstração indisponível'}), 404
    return jsonify(dados)


@app.route('/health', methods=['GET'])
def health():
    db_ok = False
    try:
        from database.schema import get_conn
        conn = get_conn()
        conn.execute('SELECT 1')
        conn.close()
        db_ok = True
    except Exception:
        pass
    status = 'ok' if db_ok else 'degraded'
    return jsonify({'status': status, 'version': '2.0', 'db': db_ok}), (200 if db_ok else 503)


@app.route('/gto/status', methods=['GET'])
def gto_status():
    """Retorna estado do GTO Wizard client: auth ok/falhou, idade do token, etc."""
    try:
        from leaklab.gto_wizard_client import get_status as _gw_status
        s = _gw_status()
    except Exception as e:
        s = {'enabled': False, 'error': str(e)}
    http_code = 200 if s.get('auth_ok') else (503 if s.get('enabled') else 200)
    return jsonify(s), http_code


@app.route('/analyze/guest', methods=['POST'])
@limiter.limit("10 per hour")
def analyze_guest():
    """Análise sem login — retorna dados mas não persiste."""
    content = _extract_content(request)
    if not content:
        return jsonify({'error': 'Conteúdo ausente'}), 400
    try:
        hands = parse_pokerstars_file_from_text(content)
    except Exception as e:
        return jsonify({'error': str(e)}), 422
    results, hand_results, errors = _analyze_hands(hands)
    if not results:
        return jsonify({'error': 'Nenhuma decisão encontrada'}), 422
    import uuid
    return jsonify({
        'session_id':  str(uuid.uuid4()),
        'hero':        hands[0].hero or 'Hero',
        'tournament_id': hands[0].tournament_id or '',
        'total_hands': len(hands),
        'parse_errors':len(errors),
        'metrics':     build_session_metrics(results),
        'leaks':       correlate_leaks(results),
        'hands':       hand_results,
        'note':        'Análise não salva. Faça login para manter histórico.',
    })


# ── Helpers ───────────────────────────────────────────────────────────────────

def _extract_content(req) -> str | None:
    if req.is_json:
        return (req.get_json(silent=True) or {}).get('content')
    if 'file' in req.files:
        f = req.files['file']
        filename = (f.filename or '').lower()
        if not filename.endswith('.txt'):
            return None
        try:
            return f.read().decode('utf-8', errors='replace')
        except Exception:
            return None
    return req.form.get('content')


def _tz_offset_arg() -> int:
    """Minutos a leste do UTC vindos do frontend (query ?tz_offset=). Pro reset diário das missões
    ser à meia-noite LOCAL do jogador (JS: -new Date().getTimezoneOffset(); Brasil = -180)."""
    try:
        return int(request.args.get('tz_offset') or 0)
    except Exception:
        return 0


def _extract_upload_filename(req) -> str | None:
    """Nome do arquivo enviado (o ACR guarda o buy-in só no filename). O frontend manda o
    nome no JSON; o upload multipart tem em req.files."""
    try:
        if 'file' in req.files and req.files['file'].filename:
            return req.files['file'].filename
    except Exception:
        pass
    if req.is_json:
        return (req.get_json(silent=True) or {}).get('filename')
    try:
        return req.form.get('filename')
    except Exception:
        return None


_GENERIC_NOTES = {
    "A decisão deve seguir a estrutura principal esperada para esse spot.",
    "A ação escolhida força uma linha fora da banda mais defensável do range estimado.",
    "A mão está em região de borda do range, então a decisão exige mais nuance do que um julgamento binário.",
}

def _enrich_note(row: dict) -> str:
    """Gera nota descritiva a partir dos campos da tabela decisions.
    Substitui notas genéricas antigas por texto específico usando os dados já armazenados.
    """
    note = (row.get('note') or '').strip()
    if note and note not in _GENERIC_NOTES:
        return note

    action  = row.get('action_taken', '') or ''
    best    = row.get('best_action', '')  or ''
    street  = row.get('street', 'preflop') or 'preflop'
    label   = row.get('label', 'standard') or 'standard'
    score   = row.get('score', 0) or 0
    m_ratio = row.get('m_ratio')
    icm     = (row.get('icm_pressure') or 'low').lower()
    stack   = row.get('stack_bb')
    draw    = (row.get('draw_profile') or 'none').lower()
    pos     = (row.get('position') or '').upper()
    is_3bet = row.get('is_3bet', 0)
    facing  = row.get('facing_bet')
    # O pote da nota e o pote da DECISAO (blinds + antes + o que esta na frente), nao
    # `pot_size` -- que e outra coisa e ficou assim de proposito (hand_state_builder:804).
    # A nota escrevia "pot 1.0bb" onde havia 3.7bb em 215 de 433 decisoes preflop.
    # Linha antiga (sem a coluna nova) NAO cai no valor errado: omite o pote.
    pot_sz  = row.get('pot_at_decision_bb')

    _act = {"fold": "fold", "check": "check", "call": "call",
            "bet": "bet", "raise": "raise", "jam": "all-in"}.get
    _str = {"preflop": "pré-flop", "flop": "flop",
            "turn": "turn", "river": "river"}.get

    action_pt = (_act(action, action) or action).upper()
    best_pt   = (_act(best,   best)   or best).upper()
    street_pt = (_str(street, street) or street).capitalize()

    parts = []

    # ── Contexto da situação ─────────────────────────────────────────────────
    ctx_items = []
    if pos:
        ctx_items.append(pos)
    if stack is not None:
        ctx_items.append(f"{stack:.0f}bb")
    if is_3bet:
        ctx_items.append("3-Bet pot")
    if facing and facing > 0:
        ctx_items.append(f"aposta {facing:.1f}bb")
    if pot_sz and pot_sz > 0:
        ctx_items.append(f"pot {pot_sz:.1f}bb")

    header = street_pt
    if ctx_items:
        header += " — " + " · ".join(ctx_items)
    parts.append(header + ".")

    # ── Ação ────────────────────────────────────────────────────────────────
    if label in ("small_mistake", "clear_mistake") and best and best != action:
        parts.append(f"Você deu {action_pt}, mas o esperado era {best_pt}.")

    # ── Draw ────────────────────────────────────────────────────────────────
    if draw not in ("none", "no_draw", ""):
        if "combo" in draw:
            parts.append("Board com draw combinado (flush + straight).")
        elif "flush" in draw:
            parts.append("Board com projeto de flush — equity implícita relevante.")
        elif "straight" in draw:
            parts.append("Board com projeto de straight.")
        elif "backdoor" in draw:
            parts.append("Draw backdoor presente.")

    # ── MTT context ──────────────────────────────────────────────────────────
    if m_ratio is not None:
        mr = round(m_ratio, 1)
        if mr < 6:
            parts.append(f"M-Ratio {mr}: jogo push/fold — range muito estreito.")
        elif mr < 10:
            parts.append(f"M-Ratio {mr}: zona crítica de pressão.")
        elif mr < 15:
            parts.append(f"M-Ratio {mr}: pressão moderada de stack.")

    if icm == "high":
        parts.append("ICM elevado: risco de eliminação amplifica o custo do erro.")
    elif icm == "medium":
        parts.append("ICM médio: equity de fichas subestima o risco de bust.")

    # ── Score ────────────────────────────────────────────────────────────────
    if label in ("small_mistake", "clear_mistake"):
        severity = "Erro grave" if label == "clear_mistake" else "Pequeno erro"
        parts.append(f"{severity} (score {score:.3f}).")

    return " ".join(parts) if parts else note


def _detect_showdown(raw_text: str, hero: str) -> str | None:
    """Retorna 'won', 'lost' ou None se o hero não chegou ao showdown.
    Só conta showdown se o hero mostrou cartas (participou efetivamente).

    Fonte primária: a seção SUMMARY ("Seat N: Hero showed [...] and won/lost") —
    formato comum a PokerStars e GGPoker. Fallback: a linha de AÇÃO "Hero: shows
    [...]" + "Hero collected" (variante onde o summary não traz o veredito).
    """
    from leaklab.parser import _extract_showdown_result
    res = _extract_showdown_result(raw_text, hero)
    if res is not None:
        return res
    shows_pat = re.compile(r'\b' + re.escape(hero) + r'\s*:\s*shows?\b')
    if not shows_pat.search(raw_text):
        return None
    won_pat = re.compile(r'\b' + re.escape(hero) + r'\s+collected\b')
    return 'won' if won_pat.search(raw_text) else 'lost'


def _detect_hand_won(raw_text: str, hero: str) -> bool | None:
    """True se o hero COLETOU o pote nesta mão (ganhou, com ou sem showdown);
    False caso contrário. None se não dá pra determinar. Diferente de
    `_detect_showdown` (que só conta showdown) — base do insight results×GTO
    'ganhei mas joguei errado pelo GTO' (resultado ≠ processo)."""
    if not hero:
        return None
    return bool(re.search(r'\b' + re.escape(hero) + r'\s+collected\b', raw_text))


def _field_size_for(user_id, tournament_id):
    """Inscritos no torneio, se já soubermos. Só o resumo (arquivo TS) traz esse número — o hand
    history não. Quando o resumo ainda não subiu, devolve None e o ICM contínuo fica de fora
    (ver `mtt_context._ICM_MAX_PLAYERS`): re-analisar depois do TS o habilita."""
    if not tournament_id:
        return None
    try:
        t = get_tournament(user_id, str(tournament_id))
        return (t or {}).get('field_size')
    except Exception:
        return None


def _colocacoes_for(user_id, tournament_id):
    """{nome: colocacao final} do torneio, se o resumo ja subiu. E a prova que liga ICM real numa
    MESA FINAL DE MTT — `field_size` nunca serve para isso, porque num MTT ele continua sendo o
    total de inscritos para sempre. Ver `leaklab.mesa_final`."""
    if not tournament_id:
        return None
    try:
        from database.repositories import get_tournament, get_tournament_finishes
        t = get_tournament(user_id, str(tournament_id))
        if not t:
            return None
        return get_tournament_finishes(t['id']) or None
    except Exception:
        return None


def _analyze_hands(hands, field_size=None, colocacoes=None):
    results, hand_results, errors = [], {}, []
    for hand in hands:
        try:
            mtt    = build_mtt_context(hand, field_size=field_size, colocacoes=colocacoes)
            inputs = build_decision_inputs_for_hand(hand, field_size=field_size,
                                                    colocacoes=colocacoes)
            hero   = hand.hero or 'Hero'
            sd_result = _detect_showdown(hand.raw_text or '', hero)
            hero_won  = _detect_hand_won(hand.raw_text or '', hero)
            decisions = []
            for di in inputs:
                r = evaluate_decision(di)
                interp = r.get('interpretation', {})
                enriched = {
                    **r,
                    'street':           di['street'],
                    'context':          di['context'],
                    'math':             di['math'],
                    'spot':             di['spot'],
                    'hero_cards':       hand.hero_cards,
                    'board':            hand.board or [],
                    'draw_profile':     di['math'].get('drawProfile', ''),
                    'position':         di['spot'].get('position', ''),
                    'num_players':      di['context'].get('activePlayers', 0),
                    'level_sb':         di['context'].get('levelSb', 0),
                    'level_bb':         di['context'].get('levelBb', 0),
                    'level_num':        di['context'].get('levelNum', 0),
                    'note':             interp.get('strategicExplanation', '') or interp.get('mathExplanation', ''),
                    'is_3bet':          di.get('is_3bet', False),
                    'showdown_result':  sd_result,
                    'hero_won_hand':    hero_won,
                }
                # Enriquecer decisões preflop com análise de range GTO
                if di['street'] == 'preflop':
                    try:
                        h_type = _hand_to_type(hand.hero_cards) if hand.hero_cards else None
                        if h_type:
                            _spot = di.get('spot', {})
                            _ctx  = di.get('context', {})
                            from leaklab.strategy_provider import sem_carta_nao_afirma
                            enriched['preflop_gto'] = sem_carta_nao_afirma(_analyze_preflop(
                                is_pko         = bool(_ctx.get('isPko')),
                                position       = _spot.get('position', ''),
                                hero_hand_type = h_type,
                                stack_bb       = float(_spot.get('effectiveStackBb') or _ctx.get('heroStackBb') or 20),
                                action_taken   = di.get('player_action', ''),
                                # em bb, nao em fichas: `facingSize` e o valor cru da mesa
                                facing_size    = float(_spot.get('facingToBb') or 0),
                                vs_position    = _spot.get('villainPosition', ''),
                                is_3bet_pot    = bool(_spot.get('is3betPot') or di.get('is_3bet', False)),
                                n_players      = _spot.get('nPlayers'),
                                facing_raises      = int(_spot.get('preflopRaisesFaced') or 0),
                                hero_was_aggressor = bool(_spot.get('heroWasAggressor')),
                                facing_limp        = bool(_spot.get('facingLimp')),
                                caller_position    = _spot.get('callerPosition', ''),
                                # `facingToBb` e `facingAllin` FALTAVAM aqui, e sao o que separa
                                # dois nos diferentes: sem eles um JAM era roteado para a carta de
                                # 3-bet PEQUENO — o mesmo defeito de "no errado" que o caminho HU
                                # existe para matar. `facingSize` vem em FICHAS
                                # (212.780 nesta mao) e nao serve de tamanho em bb.
                                facing_to_bb       = float(_spot.get('facingToBb') or 0),
                                facing_allin       = bool(_spot.get('facingAllin')),
                            ))
                    except Exception:
                        pass
                results.append(enriched)
                decisions.append(enriched)
            if decisions:
                hand_results[hand.hand_id] = {
                    'cards': hand.hero_cards,
                    'mtt':   {'mRatio': mtt.m_ratio, 'icm': mtt.icm_pressure,
                              'stage': mtt.tournament_stage, 'players': mtt.active_players,
                              'stackBb': mtt.hero_stack_bb},
                    'decisions': decisions,
                }
        except Exception as e:
            errors.append({'hand_id': hand.hand_id, 'error': str(e)})
    return results, hand_results, errors


def _detect_site(raw: str) -> str:
    # Delega pro detector do parser (fonte única) — evita drift: tinha uma cópia AQUI sem o branch
    # ACR, então o torneio ACR parseava certo mas era GRAVADO como site='unknown' (bug "rede unknown").
    from leaklab.parser import _detect_site as _parser_detect_site
    return _parser_detect_site(raw)


def jogadores_do_roster(raw: str) -> set:
    """Nomes distintos que APARECERAM SENTADOS, lendo so o roster do topo de cada mao.

    Delega a `leaklab.mesa_final.nomes_sentados` — a leitura de assento vive LA porque a prova de
    mesa final depende do mesmo sinal, e este projeto ja pagou caro por ter a mesma regra copiada
    em dois lugares. Este nome fica como fachada porque os testes e o nome do torneio o usam.
    """
    from leaklab.mesa_final import nomes_sentados
    return nomes_sentados(raw)


def _extract_tournament_name(raw: str, site: str, buy_in: float | None = None) -> str | None:
    """
    Extrai nome/descrição amigável do torneio para exibição na lista.
    GGPoker: captura nome explícito (ex: "Spin&Gold #14").
    PokerStars: detecta formato (SNG vs MTT) pelo número de jogadores únicos;
                SNGs têm exatamente N jogadores sem reposição, MTTs trazem novos
                jogadores de mesas quebradas (>9 únicos no arquivo completo).
    """
    import re
    if site == 'coinpoker':
        # nome entre aspas: "Tournament '₮1.10 Asia Rapid Fire PKO [Turbo]' '72561'"
        m = re.search(r"Tournament\s+'([^']+)'", raw)
        if m:
            return m.group(1).strip()
    if site == 'ggpoker':
        m = re.search(r'Tournament\s+#\d+,\s+(.+?)\s+Hold\'?em', raw, re.IGNORECASE)
        if m:
            return m.group(1).strip()
    else:
        if site == 'partypoker':
            # Nome amigável na linha de mesa: "Table Powerfest #193 - Main Event $500,000 Gtd (128730277) Table #83"
            # ou "Table $1 Sit & Go Hero (128487129) Table #1"
            m = re.search(r'^Table (.+?) \(\d+\) Table #\d+', raw, re.MULTILINE)
            if m:
                return m.group(1).strip()
            # cash (sem id de torneio na mesa) ou sem nome → cai no heurístico abaixo
        if buy_in is None or buy_in <= 0:
            return None
        # Contar jogadores únicos listados nos assentos para distinguir SNG de MTT.
        #
        # Reportado pelo usuário: "os nomes dos torneios ficam como MTT $1.00 mesmo para um Sit
        # and Go de 9 jogadores". Causa: o regex antigo (`^Seat \d+: (.+?) \(`) casava TAMBÉM as
        # linhas do SUMMARY, onde o parêntese vem depois de texto de resultado — e o nome
        # capturado virava "Alan_xavi collected", "Alan_xavi showed [Ad 8d] and won",
        # "Alan_xavi folded before Flop". O MESMO jogador contava várias vezes: num SnG de 9,
        # medido, o regex antigo devolvia 30 nomes, então TODO SnG estourava o limite de 9 e era
        # rotulado MTT.
        #
        # Agora só o ROSTER do topo conta, exigindo o stack no parêntese: "(1500 in chips)"
        # (PokerStars/GG) ou "(29150.00)" (ACR). Linha de SUMMARY não tem stack ali e não casa.
        unique_players = len(jogadores_do_roster(raw))
        # Sem roster reconhecido, não afirma formato nenhum: um nome errado é pior que nome
        # genérico, porque o usuário usa isso pra achar o torneio na lista.
        if unique_players == 0:
            return None
        fmt = 'SNG' if unique_players <= 9 else 'MTT'
        return f'{fmt} ${buy_in:.2f}'
    return None


def _acr_buyin_from_filename(filename: str | None) -> float | None:
    """Buy-in do ACR a partir do NOME DO ARQUIVO: '...TN-$0{FULLSTOP}50 NLH...' → 0.50.
    O ACR escapa o ponto decimal como '{FULLSTOP}' no filename; o corpo da HH é só em chips."""
    if not filename:
        return None
    import re
    fn = filename.replace('{FULLSTOP}', '.')
    m = re.search(r'TN-\$([0-9]+(?:\.[0-9]+)?)', fn)
    if not m:
        return None
    try:
        return round(float(m.group(1)), 2)
    except ValueError:
        return None


def _summary_buyin_from_filename(filename: str | None) -> float | None:
    """Buy-in TOTAL do filename do arquivo de RESULTADOS ACR: 'TS... $0.50 + $0.05.ots' → 0.55
    (buy-in + fee, como o PokerStars). Fallback: um único '$X'."""
    if not filename:
        return None
    import re
    m = re.search(r'\$(\d+(?:\.\d+)?)\s*\+\s*\$(\d+(?:\.\d+)?)', filename)
    if m:
        return round(float(m.group(1)) + float(m.group(2)), 2)
    m = re.search(r'\$(\d+(?:\.\d+)?)', filename)
    return round(float(m.group(1)), 2) if m else None


def _extract_financials(raw: str, hero: str, site: str | None = None, filename: str | None = None) -> dict:
    """
    Extrai buy-in e prêmio do hero do hand history.
    Suporta PokerStars, GGPoker, 888poker, PartyPoker e ACR (buy-in via filename).
    """
    import re
    result = {'buy_in': None, 'prize': None, 'profit': None, 'place': None}

    # ── ACR / WPN: corpo da HH é SÓ em chips → buy-in vem do FILENAME. prize/profit/place ficam
    # DESCONHECIDOS (None): o HH ACR não traz resultado nem payout → NÃO assumir busted (prize=0),
    # seria prejuízo falso. Só o buy-in (stake) é conhecido. Ver specs/acr-parser.md fase 5.
    if site == 'acr':
        result['buy_in'] = _acr_buyin_from_filename(filename)
        return result

    # ── CoinPoker: buy-in em ₮ (token) no header "Tournament '₮1.10 ...'". prize/place ficam
    # DESCONHECIDOS (o HH não traz resultado) — não assumir busted (prejuízo falso), igual ao ACR.
    if site == 'coinpoker':
        m = re.search(r'₮\s*(\d+(?:\.\d+)?)', raw)
        if m:
            result['buy_in'] = round(float(m.group(1)), 2)
        return result

    # ── 888poker / PartyPoker (dialeto PartyGaming) ────────────────────────────
    if site in ('888poker', 'partypoker'):
        if site == '888poker':
            # Buy-in no HH: "Tournament #83728678 $18.30 + $1.70 - Table #1 9 Max"
            # (\D*? pula o símbolo de moeda — pode ser $, £, € ou perdido no encoding)
            m = re.search(r'Tournament #\d+\s+\D*?(\d+(?:\.\d+)?)\s*\+\s*\D*?(\d+(?:\.\d+)?)', raw)
            if not m:
                # Fallback: arquivo de Tournament Summary — "Buy-In: $0.93 + $0.07"
                m = re.search(r'Buy-In:\s*\D*?(\d+(?:\.\d+)?)\s*\+\s*\D*?(\d+(?:\.\d+)?)', raw, re.IGNORECASE)
            if m:
                result['buy_in'] = round(float(m.group(1)) + float(m.group(2)), 2)

            if hero:
                # Resultado vive só no Tournament Summary (arquivo separado do HH):
                #   "Hero finished 1/3 and won $1.5"  → place 1, ganho LÍQUIDO 1.5
                #   "Hero finished 3/3 and lost $1"   → place 3, perda do buy-in
                ms = re.search(
                    re.escape(hero) +
                    r'\s+finished\s+(\d+)/\d+\s+and\s+(won|lost)\s+\D*?(\d+(?:\.\d+)?)',
                    raw, re.IGNORECASE
                )
                if ms:
                    result['place'] = int(ms.group(1))
                    net = float(ms.group(3))
                    bi = result['buy_in'] or 0.0
                    # 'won/lost X' = resultado líquido; prize derivado (bruto = buy-in + líquido)
                    result['prize'] = round(bi + net if ms.group(2).lower() == 'won'
                                            else max(bi - net, 0.0), 2)
        else:  # partypoker — "NL Texas Hold'em $215 USD Buy-in ..." / "$1 USD Buy-in"
            m = re.search(r'\$(\d+\.?\d*)\s+USD Buy-in', raw)
            if m:
                result['buy_in'] = float(m.group(1))

            if hero:
                # PartyPoker grava o resultado no próprio HH:
                #   "Player Hero finished in 1 place and received $3 USD"
                #   "Player DiggErr555 finished in 840." (bustou — sem prêmio)
                m = re.search(
                    r'Player ' + re.escape(hero) +
                    r' finished in (\d+)(?:\s+place and received \$(\d+\.?\d*))?',
                    raw, re.IGNORECASE
                )
                if m:
                    result['place'] = int(m.group(1))
                    result['prize'] = float(m.group(2)) if m.group(2) else 0.0

        if result['buy_in'] and result['prize'] is not None:
            result['profit'] = round(result['prize'] - result['buy_in'], 2)
        return result

    # ── PokerStars buy-in: '$0.98+$0.12' ou '$0.49+$0.49+$0.12' ─────────────
    # Captura 2 ou 3 componentes (prize [+bounty] + rake) e soma tudo
    m = re.search(r'\$(\d+\.?\d*)\+\$(\d+\.?\d*)(?:\+\$(\d+\.?\d*))?', raw)
    if m:
        total = float(m.group(1)) + float(m.group(2))
        if m.group(3):
            total += float(m.group(3))
        result['buy_in'] = round(total, 2)

    # ── GGPoker buy-in: não está nos hand files, tenta extrair do nome do torneio
    # Ex: "Spin&Gold #14" → tiers conhecidos; "NL Hold'em $5.25+$0.25" → montante
    if result['buy_in'] is None:
        m = re.search(r'\$(\d+\.?\d*)\+\$(\d+\.?\d*)', raw)
        if not m:
            # GGPoker MTT: "NLH $X+$Y" ou "NLHE $X"
            m = re.search(r'NLH[E]?\s+\$(\d+\.?\d*)(?:\+\$(\d+\.?\d*))?', raw, re.IGNORECASE)
            if m:
                buyin = float(m.group(1))
                rake  = float(m.group(2)) if m.group(2) else 0.0
                result['buy_in'] = round(buyin + rake, 2)
        if result['buy_in'] is None:
            # GG embute o buy-in no nome do torneio: "Bounty Hunters Big One $1.08 Hold'em No Limit"
            m = re.search(r"\$(\d+(?:\.\d+)?)\s+Hold'?em", raw, re.IGNORECASE)
            if m:
                result['buy_in'] = round(float(m.group(1)), 2)

    # ── Resultado hero PokerStars: "phpro finished the tournament in 3rd place and received $23.29"
    #    Vencedor: "phpro wins the tournament and receives $3.83 - congratulations!"
    if hero:
        m = re.search(
            re.escape(hero) + r'.*?finished.*?(\d+)[a-z]{2} place.*?received \$(\d+\.?\d*)',
            raw, re.IGNORECASE
        )
        if m:
            result['place'] = int(m.group(1))
            result['prize'] = float(m.group(2))
        else:
            # Vencedor PokerStars: "hero wins the tournament and receives $X"
            m = re.search(
                re.escape(hero) + r'.*?wins the tournament.*?receives \$(\d+\.?\d*)',
                raw, re.IGNORECASE
            )
            if m:
                result['place'] = 1
                result['prize'] = float(m.group(1))
            else:
                m = re.search(
                    re.escape(hero) + r'.*?finished.*?(\d+)[a-z]{2} place',
                    raw, re.IGNORECASE
                )
                if m:
                    result['place'] = int(m.group(1))
                    result['prize'] = 0.0

        # ── GGPoker resultado: "Hero finished in 3rd place" / "Hero wins $X"
        if result['place'] is None:
            m = re.search(
                re.escape(hero) + r'[^.]*?finished[^.]*?in (\d+)[a-z]{2}',
                raw, re.IGNORECASE
            )
            if m:
                result['place'] = int(m.group(1))

        if result['prize'] is None:
            # PokerStars: hero busted sem ITM — "hero finished the tournament" sem lugar/prêmio.
            # (NÃO somar "collected X from" — são potes normais em FICHAS, não prêmio em dinheiro.)
            if re.search(re.escape(hero) + r'\s+finished the tournament', raw, re.IGNORECASE):
                result['prize'] = 0.0

    # Sem prêmio/ITM detectado = eliminado (busted). O prejuízo é o buy-in cheio (inclui rake).
    # Cobre o GG (que não traz resultado no HH) e qualquer torneio sem cash. Se o jogador
    # tiver cashado mas o HH não registrar (caso GG), pode ser corrigido manualmente depois.
    if result['prize'] is None and result['buy_in']:
        result['prize'] = 0.0

    if result['buy_in'] and result['prize'] is not None:
        result['profit'] = round(result['prize'] - result['buy_in'], 2)

    return result


_MONTHS = {
    'january': 1, 'february': 2, 'march': 3, 'april': 4, 'may': 5, 'june': 6,
    'july': 7, 'august': 8, 'september': 9, 'october': 10, 'november': 11, 'december': 12,
}


def _extract_date(raw: str) -> str | None:
    """
    Extrai a data do jogo do hand history.
    Suporta PokerStars/GGPoker (2025/07/22), 888poker ("*** 21 06 2018", DD MM YYYY)
    e PartyPoker ("Sunday, July 24, 19:32:00 CEST 2016", mês por nome).
    """
    import re
    m = re.search(r'(\d{4})/(\d{2})/(\d{2})\s+\d{2}:\d{2}:\d{2}', raw)
    if m:
        return f'{m.group(1)}-{m.group(2)}-{m.group(3)}'
    m = re.search(r'(\d{4})/(\d{2})/(\d{2})', raw)
    if m:
        return f'{m.group(1)}-{m.group(2)}-{m.group(3)}'
    # 888poker: "$100/$200 Blinds No Limit Holdem - *** 08 08 2016 23:03:27" (DD MM YYYY)
    m = re.search(r'\*\*\*\s+(\d{2}) (\d{2}) (\d{4})\b', raw)
    if m:
        return f'{m.group(3)}-{m.group(2)}-{m.group(1)}'
    # PartyPoker: "... - Sunday, July 24, 19:32:00 CEST 2016" (Mês DD ... YYYY)
    m = re.search(
        r'\b(January|February|March|April|May|June|July|August|September|October|November|December)'
        r'\s+(\d{1,2}),.*?(\d{4})',
        raw, re.IGNORECASE
    )
    if m:
        mo = _MONTHS[m.group(1).lower()]
        return f'{m.group(3)}-{mo:02d}-{int(m.group(2)):02d}'
    return None


# ── Error handlers ────────────────────────────────────────────────────────────


# ── Coach system endpoints ────────────────────────────────────────────────────

@app.route('/coach/invite-key', methods=['GET'])
@require_coach
def coach_invite_key():
    """Retorna (ou gera) a chave de convite do coach (LEGADO — ver convites single-use)."""
    key = assign_invite_key(g.user_id)
    return jsonify({'invite_key': key})


# ── SEC-01: convites single-use do coach ──────────────────────────────────────

@app.route('/coach/invites', methods=['GET'])
@require_coach
def coach_invites_list():
    from database.repositories import list_coach_invites
    return jsonify({'invites': list_coach_invites(g.user_id)})


@app.route('/coach/invites', methods=['POST'])
@require_coach
def coach_invites_create():
    from database.repositories import create_coach_invite
    data = request.get_json(silent=True) or {}
    label = (data.get('label') or '').strip()[:120] or None
    try:
        days = int(data.get('expires_days', 30))
    except (TypeError, ValueError):
        days = 30
    inv = create_coach_invite(g.user_id, expires_days=max(0, min(days, 365)), label=label)
    return jsonify({'invite': inv}), 201


@app.route('/coach/invites/<int:invite_id>', methods=['DELETE'])
@require_coach
def coach_invites_revoke(invite_id):
    from database.repositories import revoke_coach_invite
    ok = revoke_coach_invite(g.user_id, invite_id)
    return jsonify({'ok': ok}), (200 if ok else 404)


@app.route('/student/redeem-invite', methods=['POST'])
@require_auth
def student_redeem_invite():
    """Resgata um convite single-use → vincula o aluno ao coach (substitui o link por chave)."""
    from database.repositories import redeem_coach_invite
    data = request.get_json(silent=True) or {}
    code = (data.get('code') or '').strip()
    if not code:
        return jsonify({'error': 'code obrigatório'}), 400
    res = redeem_coach_invite(g.user_id, code)
    if not res['ok']:
        return jsonify({'error': res['error']}), 400
    msg = (f'Solicitação enviada ao coach {res["coach"]["username"]} — aguardando aprovação'
           if res.get('pending') else f'Vinculado ao coach {res["coach"]["username"]}')
    return jsonify({'message': msg, 'coach': res['coach'], 'pending': bool(res.get('pending'))})


@app.route('/coach/link-requests', methods=['GET'])
@require_coach
def coach_link_requests_list():
    """SEC-01 fase 2: vínculos pendentes de aprovação do coach."""
    from database.repositories import list_pending_link_requests
    return jsonify({'requests': list_pending_link_requests(g.user_id)})


@app.route('/coach/link-requests/<int:student_id>/approve', methods=['POST'])
@require_coach
def coach_link_request_approve(student_id):
    from database.repositories import approve_link_request
    ok = approve_link_request(g.user_id, student_id)
    return jsonify({'ok': ok}), (200 if ok else 404)


@app.route('/coach/link-requests/<int:student_id>/reject', methods=['POST'])
@require_coach
def coach_link_request_reject(student_id):
    from database.repositories import reject_link_request
    ok = reject_link_request(g.user_id, student_id)
    return jsonify({'ok': ok}), (200 if ok else 404)


@app.route('/coach/trial-status', methods=['GET'])
@require_coach
def coach_trial_status():
    """COACH-02: estado do Pro de cortesia (dias restantes, indicados pagantes, meta)."""
    from database.repositories import get_coach_trial_status
    return jsonify(get_coach_trial_status(g.user_id))


@app.route('/coach/profile', methods=['GET', 'POST'])
@require_auth
def coach_profile():
    """GET: busca perfil. POST: cria/atualiza perfil do coach."""
    if request.method == 'GET':
        profile = get_coach_profile(g.user_id)
        return jsonify(profile or {})

    # POST — criar/atualizar
    data = request.get_json(silent=True) or {}
    bio_raw = data.get('bio', '')
    is_clean, reason = moderate_text(bio_raw)
    if not is_clean:
        return jsonify({'error': reason}), 422
    profile = upsert_coach_profile(
        user_id=g.user_id,
        display_name=data.get('display_name', ''),
        bio=bio_raw,
        specialties=data.get('specialties', []),
        contact_email=data.get('contact_email'),
        contact_link=data.get('contact_link'),
        is_public=data.get('is_public', True),
        # Sprint 7 — campos estendidos
        photo_url=data.get('photo_url'),
        experience_years=data.get('experience_years'),
        stakes=data.get('stakes'),
        coaching_style=data.get('coaching_style'),
        languages=data.get('languages', ['pt']),
        biggest_results=data.get('biggest_results', []),
        price_per_session=data.get('price_per_session'),
        price_monthly=data.get('price_monthly'),
        trial_available=bool(data.get('trial_available', False)),
        availability=data.get('availability'),
        social_youtube=data.get('social_youtube'),
        social_twitch=data.get('social_twitch'),
        social_twitter=data.get('social_twitter'),
        social_instagram=data.get('social_instagram'),
    )
    # Garantir que tem chave de convite
    key = assign_invite_key(g.user_id)
    profile['invite_key'] = key
    return jsonify(profile)


@app.route('/coach/effectiveness', methods=['GET'])
@require_coach
def coach_effectiveness():
    return jsonify(get_coach_effectiveness_report(g.user_id))


# ── Coach Plan Templates — FEAT-09 ───────────────────────────────────────────

@app.route('/coach/templates', methods=['GET'])
@require_coach
def coach_templates_list():
    return jsonify({'templates': get_coach_templates(g.user_id)})


@app.route('/coach/templates', methods=['POST'])
@require_coach
def coach_templates_create():
    d = request.get_json(silent=True) or {}
    name = (d.get('name') or '').strip()
    if not name:
        return jsonify({'error': 'name obrigatório'}), 400
    archetype  = (d.get('target_archetype') or '').strip() or None
    cards_json = d.get('cards_json')
    if not isinstance(cards_json, (list, str)):
        return jsonify({'error': 'cards_json obrigatório'}), 400
    import json as _json
    if isinstance(cards_json, list):
        cards_json = _json.dumps(cards_json, ensure_ascii=False)
    t = create_coach_template(g.user_id, name, archetype, cards_json)
    return jsonify(t), 201


@app.route('/coach/templates/<int:template_id>', methods=['DELETE'])
@require_coach
def coach_templates_delete(template_id: int):
    delete_coach_template(template_id, g.user_id)
    return jsonify({'ok': True})


# ── Coach Messages — FEAT-10 ─────────────────────────────────────────────────

def _resolve_coach_student(user_id: int, role: str, student_id_param: int | None = None):
    """Returns (coach_id, student_id) for the current user or 403."""
    if role == 'coach':
        return user_id, student_id_param
    else:
        # Student — look up their coach
        user = get_user_by_id(user_id)
        if not user or not user.get('coach_id'):
            return None, None
        return user['coach_id'], user_id


@app.route('/coach/messages/inbox', methods=['GET'])
@require_coach
def coach_messages_inbox():
    from database.repositories import get_coach_inbox
    threads = get_coach_inbox(g.user_id)
    return jsonify({'threads': threads})


@app.route('/coach/student/<int:student_id>/messages', methods=['GET'])
@require_coach
def coach_messages_list(student_id: int):
    if not _verify_student(g.user_id, student_id):
        return jsonify({'error': 'Aluno não vinculado'}), 403
    msgs = get_coach_messages(g.user_id, student_id, limit=100)
    mark_messages_read(g.user_id, student_id, reader_role='coach')
    return jsonify({'messages': msgs})


@app.route('/coach/student/<int:student_id>/messages', methods=['POST'])
@require_coach
def coach_messages_send(student_id: int):
    if not _verify_student(g.user_id, student_id):
        return jsonify({'error': 'Aluno não vinculado'}), 403
    d = request.get_json(silent=True) or {}
    body = sanitize_llm_input((d.get('body') or '').strip(), max_len=1000)
    if not body:
        return jsonify({'error': 'body obrigatório'}), 400
    decision_id = d.get('decision_id')
    msg = send_coach_message(g.user_id, student_id, body,
                             sender_role='coach', decision_id=decision_id)
    return jsonify(msg), 201


@app.route('/player/coach/messages', methods=['GET'])
@require_auth
def player_messages_list():
    coach_id, student_id = _resolve_coach_student(g.user_id, g.role)
    if not coach_id:
        return jsonify({'messages': []})
    msgs = get_coach_messages(coach_id, student_id, limit=100)
    mark_messages_read(coach_id, student_id, reader_role='student')
    return jsonify({'messages': msgs})


@app.route('/player/coach/messages', methods=['POST'])
@require_auth
def player_messages_send():
    d = request.get_json(silent=True) or {}
    body = sanitize_llm_input((d.get('body') or '').strip(), max_len=1000)
    if not body:
        return jsonify({'error': 'body obrigatório'}), 400
    coach_id, student_id = _resolve_coach_student(g.user_id, g.role)
    if not coach_id:
        return jsonify({'error': 'Sem coach vinculado'}), 400
    msg = send_coach_message(coach_id, student_id, body, sender_role='student')
    return jsonify(msg), 201


@app.route('/player/messages/unread', methods=['GET'])
@require_auth
def player_messages_unread():
    count = get_unread_message_count(g.user_id, g.role)
    return jsonify({'unread': count})


@app.route('/coach/<int:coach_id>/contact', methods=['POST'])
@require_auth
def coach_contact_send(coach_id: int):
    """Aluno envia mensagem inicial para um coach sem vínculo formal."""
    d = request.get_json(silent=True) or {}
    body = sanitize_llm_input((d.get('body') or '').strip(), max_len=1000)
    if not body:
        return jsonify({'error': 'body obrigatório'}), 400
    target = get_user_by_id(coach_id)
    if not target or target.get('role') != 'coach':
        return jsonify({'error': 'Coach não encontrado'}), 404
    # Anti-spam: max 20 mensagens por par quando não vinculado
    if g.user.get('coach_id') != coach_id:
        n = get_coach_message_count(coach_id, g.user_id)
        if n >= 20:
            return jsonify({'error': 'Limite de mensagens atingido'}), 429
    msg = send_coach_message(coach_id, g.user_id, body, sender_role='student')
    return jsonify(msg), 201


@app.route('/coach/<int:coach_id>/contact-thread', methods=['GET'])
@require_auth
def coach_contact_thread(coach_id: int):
    """Aluno lê a thread de mensagens com um coach específico."""
    msgs = get_coach_messages(coach_id, g.user_id, limit=100)
    if msgs:
        mark_messages_read(coach_id, g.user_id, reader_role='student')
    return jsonify({'messages': msgs})


@app.route('/coach/impact', methods=['GET'])
@require_coach
def coach_impact():
    """Métricas de impacto do coach sobre seus alunos."""
    days = int(request.args.get('days', 30))
    return jsonify(get_coach_impact_metrics(g.user_id, days))


@app.route('/coach/students', methods=['GET'])
@require_coach
def coach_students_v2():
    """Lista alunos com métricas recentes + sinais de cockpit (P1a):
    `is_active_paid` (= ativo que conta na comp: pro + import nos últimos 30d, a MESMA
    régua do payout), `is_referred` (indicado — aproximação por invited_by_key até o SEC-01),
    `plan`. O score da última sessão já vem em recent_tournament.avg_score."""
    import datetime as _dt
    from database.repositories import get_students_attention_signals
    _cutoff = (_dt.datetime.utcnow() - _dt.timedelta(days=30)).strftime('%Y-%m-%d %H:%M:%S')
    students = get_students(g.user_id)
    _attn = get_students_attention_signals(g.user_id)   # P1b: {sid: {critical_pending, unread}}
    enriched = []
    for s in students:
        tournaments = get_tournaments(s['id'], limit=5)
        recent = tournaments[0] if tournaments else None
        # Calcular tendência (último vs anterior)
        trend = None
        if len(tournaments) >= 2:
            diff = (tournaments[0]['avg_score'] or 0) - (tournaments[1]['avg_score'] or 0)
            trend = 'improving' if diff < -0.005 else 'worsening' if diff > 0.005 else 'stable'
        # ativo que conta na comp: pro + importou nos últimos 30d (imported_at em formato
        # ISO → comparação lexicográfica de string com o cutoff é válida).
        _imp = (recent or {}).get('imported_at') or ''
        # Indicado = vinculado via convite single-use OU link referral (referral_coach_id).
        is_referred = (s.get('invited_via_invite_id') is not None
                       or s.get('referral_coach_id') is not None)
        # SEC-01 fase 2: só vínculos aprovados pelo coach contam na comp. Legados = 'approved'.
        _approved = (s.get('link_status') or 'approved') == 'approved'
        # "Ativo · conta R$" = indicado + aprovado + PAGANTE EM DIA (exclui past_due/perk) +
        # importou nos últimos 30d (régua do payout). billing_standing=='paying' já garante pro.
        is_active_paid = (is_referred and _approved and s.get('billing_standing') == 'paying'
                          and bool(_imp) and _imp >= _cutoff)
        enriched.append({
            **s,
            'recent_tournament': recent,
            'total_tournaments': len(tournaments),
            'trend': trend,
            'is_active_paid': is_active_paid,
            'is_referred': is_referred,
            'link_status': s.get('link_status') or 'approved',
            'critical_pending': (_attn.get(s['id']) or {}).get('critical_pending', 0),
            'unread': (_attn.get(s['id']) or {}).get('unread', 0),
            # V2-3: últimos scores (cronológico) p/ sparkline de tendência no roster
            'score_history': [t['avg_score'] for t in reversed(tournaments) if t.get('avg_score') is not None],
        })
    # Ordenar: alunos com piores scores primeiro (mais precisam de atenção)
    enriched.sort(
        key=lambda x: x['recent_tournament']['avg_score'] if x['recent_tournament'] else 0,
        reverse=True
    )
    return jsonify({'students': enriched})


@app.route('/coach/recent-activity', methods=['GET'])
@require_coach
def coach_recent_activity():
    """P2 — feed cross-aluno: torneios recentes de todos os alunos do coach."""
    from database.repositories import get_coach_recent_activity
    limit = min(int(request.args.get('limit', 20)), 50)
    return jsonify({'activity': get_coach_recent_activity(g.user_id, limit)})


@app.route('/coach/cohort-analytics', methods=['GET'])
@require_coach
def coach_cohort_analytics():
    """V2-2 — gráficos da turma: distribuição de qualidade, receita no tempo, heatmap de leaks."""
    from database.repositories import get_coach_cohort_analytics
    return jsonify(get_coach_cohort_analytics(g.user_id))


# ── Student endpoints ─────────────────────────────────────────────────────────

@app.route('/student/link-coach', methods=['POST'])
@require_auth
def link_coach():
    """Vincula aluno a coach via chave de convite."""
    data = request.get_json(silent=True) or {}
    invite_key = data.get('invite_key', '').strip().upper()
    if not invite_key:
        return jsonify({'error': 'invite_key obrigatório'}), 400

    result = link_student_to_coach(g.user_id, invite_key)
    if not result['ok']:
        return jsonify({'error': result['error']}), 400
    return jsonify({
        'message': f'Vinculado ao coach {result["coach"]["username"]} com sucesso',
        'coach': result['coach'],
    })


@app.route('/student/recommended-coaches', methods=['GET'])
@require_auth
def recommended_coaches():
    """Coaches recomendados baseado nos leaks do aluno."""
    coaches = recommend_coaches_for_leaks(g.user_id)
    return jsonify({'coaches': coaches})


# ── Coaches públicos ──────────────────────────────────────────────────────────

@app.route('/coaches', methods=['GET'])
def public_coaches():
    """Lista coaches públicos com filtros (sem auth)."""
    coaches = get_public_coaches(
        specialty  = request.args.get('specialty'),
        language   = request.args.get('language'),
        trial_only = request.args.get('trial') == '1',
        max_price  = float(request.args['max_price']) if request.args.get('max_price') else None,
        search     = request.args.get('q'),
        sort       = request.args.get('sort', 'rating'),
        limit      = int(request.args.get('limit', 20)),
    )
    return jsonify({'coaches': coaches})


@app.route('/coaches/<int:coach_user_id>', methods=['GET'])
def public_coach_profile(coach_user_id):
    """Perfil público completo de um coach."""
    profile = get_coach_profile(coach_user_id)
    if not profile or not profile.get('is_public'):
        return jsonify({'error': 'Coach não encontrado'}), 404
    PRIVATE = {'password_hash', 'email'}
    safe = {k: v for k, v in profile.items() if k not in PRIVATE}
    safe['reviews'] = get_public_coach_reviews(coach_user_id, limit=10)
    try:
        eff = get_coach_effectiveness_report(coach_user_id)
        safe['effectiveness_badge'] = eff['summary'].get('badge')
        safe['effectiveness_median_delta'] = eff['summary'].get('median_delta')
    except Exception:
        safe['effectiveness_badge'] = None
        safe['effectiveness_median_delta'] = None
    return jsonify(safe)


@app.route('/coaches/<int:coach_user_id>/reviews', methods=['GET'])
def public_coach_reviews(coach_user_id):
    """Reviews públicas de um coach."""
    limit = int(request.args.get('limit', 10))
    return jsonify(get_public_coach_reviews(coach_user_id, limit))


# Redirecionar o endpoint antigo de coach/students para o novo
@app.route('/coach/students-legacy', methods=['GET'])
@require_coach
def coach_students_legacy():
    return coach_students_v2()


# ── Coach: acesso completo aos dados de alunos ────────────────────────────────

def _verify_student(coach_id: int, student_id: int):
    """Retorna True se student_id pertence a coach_id."""
    students = get_students(coach_id)
    return any(s['id'] == student_id for s in students)


@app.route('/coach/student/<int:student_id>/stats', methods=['GET'])
@require_coach
def coach_student_stats(student_id):
    if not _verify_student(g.user_id, student_id):
        return jsonify({'error': 'Aluno não encontrado'}), 404
    days = int(request.args.get('days', 90))
    return jsonify(get_player_stats(student_id, days))


@app.route('/coach/student/<int:student_id>/breakdown', methods=['GET'])
@require_coach
def coach_student_breakdown(student_id):
    if not _verify_student(g.user_id, student_id):
        return jsonify({'error': 'Aluno não encontrado'}), 404
    days = int(request.args.get('days', 90))
    return jsonify(get_breakdown(student_id, days))


@app.route('/coach/student/<int:student_id>/tournament/<tournament_id>', methods=['GET'])
@require_coach
def coach_student_tournament(student_id, tournament_id):
    if not _verify_student(g.user_id, student_id):
        return jsonify({'error': 'Aluno não encontrado'}), 404
    t = get_tournament(student_id, tournament_id)
    if not t:
        return jsonify({'error': 'Torneio não encontrado'}), 404
    decisions = get_decisions(t['id'])
    # Aderência coach × sistema por decisão (marca mãos não-aderentes na tela do coach).
    from leaklab.coach_adherence import classify as _adh_classify
    _ann_map = {a['decision_id']: a for a in get_annotations_for_decisions([d['id'] for d in decisions], coach_id=g.user_id)}
    for d in decisions:
        d['note'] = _enrich_note(d)
        _ann = _ann_map.get(d['id'])
        if _ann:
            _kind, _rec = _adh_classify(d, _ann)
            d['adherence'] = _kind                         # match_ok|match_erro|diverge_rigido|diverge_perdido|comentario
            d['coach_comment'] = _ann.get('comment')
            d['coach_action'] = _ann.get('coach_action')
        else:
            d['adherence'] = None
    return jsonify({'tournament': t, 'decisions': decisions})


@app.route('/coach/student/<int:student_id>/worst-decisions', methods=['GET'])
@require_coach
def coach_student_worst_decisions(student_id):
    if not _verify_student(g.user_id, student_id):
        return jsonify({'error': 'Aluno não encontrado'}), 404
    limit = int(request.args.get('n', 20))
    from database.schema import get_conn as _gc
    conn = _gc()
    try:
        rows = conn.execute("""
            SELECT d.id, d.hand_id, d.street, d.hero_cards, d.board,
                   d.action_taken, d.best_action, d.gto_action, d.label, d.score,
                   d.position, d.icm_pressure, d.m_ratio, d.stack_bb,
                   t.tournament_id, t.site,
                   COALESCE(a.coach_override_label, d.label) AS effective_label
            FROM decisions d
            JOIN tournaments t ON t.id = d.tournament_id
            LEFT JOIN coach_hand_annotations a
                   ON a.decision_id = d.id AND a.student_id = t.user_id AND a.coach_id = ?
            WHERE t.user_id = ?
              AND COALESCE(a.coach_override_label, d.label) IN ('clear_mistake', 'small_mistake')
            ORDER BY d.score DESC
            LIMIT ?
        """, (g.user_id, student_id, limit)).fetchall()
    finally:
        conn.close()
    return jsonify({'decisions': [dict(r) for r in rows]})


@app.route('/coach/all-worst-decisions', methods=['GET'])
@require_coach
def coach_all_worst_decisions():
    """Piores decisões de todos os alunos — visão multi-aluno (BACK-003)."""
    n = int(request.args.get('n', 20))
    student_id_filter = request.args.get('student_id', type=int)
    street_filter = request.args.get('street') or None
    label_filter  = request.args.get('label') or None
    decisions = get_all_students_worst_decisions(
        g.user_id, n=n,
        student_id_filter=student_id_filter,
        street_filter=street_filter,
        label_filter=label_filter,
    )
    return jsonify({'decisions': decisions})


@app.route('/coach/common-leaks', methods=['GET'])
@require_coach
def coach_common_leaks():
    """Leaks em comum entre alunos — com lista de alunos afetados por spot (BACK-004)."""
    days = int(request.args.get('days', 30))
    leaks = get_common_leaks(g.user_id, days=days)
    return jsonify({'leaks': leaks})


@app.route('/coach/student/<int:student_id>/study-plan', methods=['GET'])
@require_coach
def coach_student_study_plan(student_id):
    if not _verify_student(g.user_id, student_id):
        return jsonify({'error': 'Aluno não encontrado'}), 404
    try:
        from leaklab.llm_explainer import generate_study_plan
        from database.repositories import get_player_stats as _get_player_stats, get_leak_ranking_gto_first
        days = int(request.args.get('days', 90))
        leak_data    = get_leak_ranking_gto_first(student_id, days)
        leaks        = leak_data['leaks']
        leak_source  = leak_data['source']
        evolution    = get_evolution_metrics(student_id, days) or []
        icm          = get_icm_performance(student_id, days)  or {}
        player_stats = _get_player_stats(student_id, days)
        if not leaks and not evolution:
            return jsonify({'error': 'Aluno sem dados suficientes'}), 400
        tourns = get_tournaments(student_id, limit=1)
        hero = tourns[0]['hero'] if tourns else 'Aluno'
        force_new = request.args.get('new') == '1'
        from database.repositories import get_ev_leaks as _get_ev_leaks
        _ev = _get_ev_leaks(student_id, days).get('leaks')   # #24/#25: prioriza por bb
        plan = _gen_study_plan(leaks, evolution, icm, hero=hero, user_id=student_id,
                               force_new=force_new, player_stats=player_stats,
                               leak_source=leak_source, ev_leaks=_ev)
        return jsonify(plan)
    except Exception as e:
        import traceback; traceback.print_exc()
        return jsonify({'error': str(e)}), 500


def _attach_equity_real_vs_mostrada(replay, hand):
    """Equity REAL do herói vs a mão que o vilão mostrou, por street, nos steps de decisão.

    Item 2 da deliberação de 17/08 (após a validação com 1.082 medições): a equity estimada
    é calibrada na média mas tem cauda gorda no river — a real vs a mão revelada é o
    antídoto pedagógico na revisão ("você pagou o turn com 5% contra a mão dele"). É
    CONTEXTO, nunca veredito: julgar a decisão pela mão mostrada é resulting; o veredito
    continua vindo da range. Pareamento estrito: só com UM revelador além do herói
    (`revelador_unico`) — vs 2+ mãos o número não significa nada. Nunca bloqueia o /replay."""
    try:
        from leaklab.equity_real import equity_real_por_street, revelador_unico
        par = revelador_unico(getattr(hand, 'reveals', None) or {}, replay.get('hero') or '')
        if not par:
            return
        nome, vilao_cartas = par
        por_street = equity_real_por_street(
            getattr(hand, 'hero_cards', '') or '', vilao_cartas,
            getattr(hand, 'board', None) or [])
        if not por_street:
            return
        for _st in replay.get('timeline', []):
            if not _st.get('is_hero'):
                continue
            eq = por_street.get((_st.get('street') or '').lower())
            if eq is not None:
                _st['real_equity_vs_shown'] = {'equity': eq, 'villain': nome,
                                               'villain_cards': list(vilao_cartas)}
    except Exception:
        pass


def _attach_opponent_hud(replay, local_tid, hands=None):
    """HUD de oponente (Fases 2-3): anexa `villain_profile` (arquétipo + stats gateados) e
    `exploit` a cada step do timeline, por lookup do `villain_name` nos opponent_profiles do
    torneio. Pula nomes que são POSIÇÃO (dados anonimizados → read sem significado). Fonte
    ÚNICA do HUD — usada pela visão do aluno (get_replay) e do coach (coach_student_replay).
    Nunca bloqueia o /replay (exceção engolida).

    `hands` (as ParsedHand do torneio, 17/08): liga o CONSUMIDOR do `ParsedHand.reveals` —
    `replay['villain_reveals']` = {jogador: [{hand, cards}]}, "ele já MOSTROU X neste
    torneio". Mão revelada no SUMMARY é FATO, não read inferido, então não passa pelo gate
    de amostra do [[project_opponent_hud]] — mas é dado de terceiro e só aparece onde o HUD
    já aparece (replayer, nunca dashboard). A mão ATUAL fica de fora do mapa: o HUD
    mostraria o showdown antes de o replay chegar lá (spoiler). Mapa por JOGADOR (não por
    step) porque o HUD vive na MESA, um box por assento."""
    try:
        from database.repositories import get_opponent_profiles as _get_opp
        from leaklab.opponent_stats import compute_exploit as _exploit, is_position_name as _is_pos
        _opp_map = {p['player']: {'archetype': p['archetype'], 'confidence': p['confidence'],
                                  'hands': p['hands'], 'stats': p['stats']}
                    for p in _get_opp(local_tid)}
        # Reveals agregados do torneio — independentes do perfil (vilão de poucas mãos não
        # tem arquétipo, mas mão mostrada continua sendo evidência). Herói fica de fora: a
        # carta dele já é o centro do replay.
        _mostradas: dict = {}
        _mao_atual = str(replay.get('hand_id') or '')
        _heroi = replay.get('hero') or ''
        for _h in (hands or []):
            if str(getattr(_h, 'hand_id', '')) == _mao_atual:
                continue
            for _nome, _cartas in (getattr(_h, 'reveals', None) or {}).items():
                if _cartas and _nome != _heroi and not _is_pos(_nome):
                    _mostradas.setdefault(_nome, []).append(
                        {'hand': str(getattr(_h, 'hand_id', '') or '')[-6:],
                         'cards': list(_cartas)})
        if _mostradas:
            # As mais recentes por último no HH; teto de 8 por vilão para não virar tabela.
            replay['villain_reveals'] = {n: v[-8:] for n, v in _mostradas.items()}
        if not _opp_map:
            return
        # Mapa completo pro HUD da MESA (estilo Holdem Manager: 1 box por assento) — só
        # nomes reais (não posição). O front casa pelo nome do jogador no assento.
        replay['opponent_profiles'] = {n: pr for n, pr in _opp_map.items() if not _is_pos(n)}
        for _st in replay.get('timeline', []):
            _vn = _st.get('villain_name')
            if _vn and _vn in _opp_map and not _is_pos(_vn):   # nome=posição → anonimizado, pula
                _prof = _opp_map[_vn]
                _st['villain_profile'] = _prof
                if _st.get('is_hero'):                          # Fase 3: exploit só no step do hero
                    _ex = _exploit(action=_st.get('action'), best_action=_st.get('best_action'),
                                   bet_intent=_st.get('bet_intent'), street=_st.get('street'),
                                   profile=_prof, icm_pressure=_st.get('icm_pressure'))
                    if _ex:
                        _st['exploit'] = _ex
    except Exception:
        pass


@app.route('/coach/student/<int:student_id>/replay/<tournament_id>/<hand_id>', methods=['GET'])
@require_coach
def coach_student_replay(student_id, tournament_id, hand_id):
    if not _verify_student(g.user_id, student_id):
        return jsonify({'error': 'Aluno não encontrado'}), 404
    t = get_tournament(student_id, tournament_id)
    if not t:
        return jsonify({'error': 'Torneio não encontrado'}), 404
    raw_text = t.get('raw_text')
    if not raw_text:
        return jsonify({'error': 'Hand history não disponível'}), 404
    try:
        hands = parse_pokerstars_file_from_text(raw_text)
    except Exception as e:
        return jsonify({'error': f'Erro ao parsear: {str(e)}'}), 422
    target = next((h for h in hands if str(h.hand_id) == str(hand_id)), None)
    if not target:
        return jsonify({'error': f'Mão {hand_id} não encontrada'}), 404
    _asite = (t.get('site') or '').lower()
    if _asite in ('ggpoker', 'coinpoker'):   # CoinPoker também anonimiza (hash)
        # GG: hash estável no torneio → mapa do torneio (Vilão N consistente entre mãos).
        # CoinPoker: hash muda a cada mão → mapa DA MÃO (Vilão 1-6), senão viraria "Vilão 1547".
        _asrc = target.raw_text if _asite == 'coinpoker' else raw_text
        _apply_alias_to_hand(target, _build_gg_alias_map(_asrc, t.get('hero') or target.hero))
    _db_all_c  = get_decisions(t['id'])
    _db_hand_c = [d for d in _db_all_c if str(d.get('hand_id')) == str(hand_id)]
    # Balde consumido em ordem, não índice — a chave (street, ação) não é única, e a lista
    # vai INTEIRA (sem filtrar por gto_label). Mesma função do replay do aluno.
    _gto_idx_c = balde_de_gto_do_banco(_db_hand_c)
    try:
        from leaklab.pipeline import build_decision_inputs_for_hand
        from leaklab.decision_engine_v11 import evaluate_decision as _eval
        live_decisions = []
        for di in build_decision_inputs_for_hand(target):
            r = _eval(di)
            action_norm = (r.get('actionTaken','') or '').rstrip('s') or r.get('actionTaken','')
            gto_data = _gto_idx_c.proxima((di['street'], action_norm)) or {}
            live_decisions.append({
                'hand_id': str(target.hand_id), 'street': di['street'],
                'action_taken': r.get('actionTaken', ''), 'best_action': r.get('bestAction', ''),
                'label': r['evaluation']['label'], 'score': r['evaluation']['mistakeScore'],
                'context': di.get('context', {}), 'math': di.get('math', {}),
                'breakdown': r['evaluation'].get('scoreBreakdown', {}),
                # Procedência e insumos do custo, iguais aos da rota do ALUNO. Sem eles o coach
                # via `custo=False` na mesma decisão em que o aluno via `custo=True` — duas telas,
                # respostas opostas sobre o mesmo spot.
                'verdict_source':   r.get('verdictSource'),
                'verdict_has_cost': r.get('verdictHasCost'),
                'ev_loss_bb':     gto_data.get('ev_loss_bb'),
                'ev_loss_source': gto_data.get('ev_loss_source'),
                'gto_label':  gto_data.get('gto_label'),
                'gto_action': gto_data.get('gto_action'),
                'gto_depth_capped': 1 if (gto_data.get('depth_capped') or gto_data.get('gto_depth_capped')) else 0,
                'bet_intent': r.get('bet_intent'),
                'reco_rationale': r.get('reco_rationale'),
                'icm_zone_approx': bool(r.get('icm_zone_approx')),  # gate zona-ICM → "≈ Aproximação chipEV"
            })
        hand_decisions = live_decisions
    except Exception:
        hand_decisions = _db_hand_c
    replay = _build_replay_data(target, hand_decisions, t.get('hero', target.hero))
    # HUD de oponente na visão do COACH — mesma fonte do aluno (perfil + exploit por step).
    _attach_opponent_hud(replay, t['id'], hands=hands)
    _attach_equity_real_vs_mostrada(replay, target)
    # Attach coach annotations for decisions in this hand
    db_decisions = _db_all_c
    hand_db_decisions = [d for d in db_decisions if str(d.get('hand_id')) == str(hand_id)]
    if hand_db_decisions:
        # Visão do COACH: só as anotações DELE (g.user_id) — não de outro coach do aluno.
        ann_list = get_annotations_for_decisions([d['id'] for d in hand_db_decisions], coach_id=g.user_id)
        ann_map = {str(a['decision_id']): a for a in ann_list}
        replay['coach_annotations'] = {
            str(d['id']): {**ann_map[str(d['id'])],
                           'street': d.get('street'), 'action_taken': d.get('action_taken')}
            for d in hand_db_decisions if str(d['id']) in ann_map
        }
    else:
        replay['coach_annotations'] = {}
    return jsonify(replay)


@app.route('/coach/student/<int:student_id>/study-overrides', methods=['GET'])
@require_coach
def coach_student_study_overrides_get(student_id):
    if not _verify_student(g.user_id, student_id):
        return jsonify({'error': 'Aluno não encontrado'}), 404
    overrides = get_study_overrides(g.user_id, student_id)
    return jsonify({'overrides': overrides})


@app.route('/coach/student/<int:student_id>/study-overrides', methods=['POST'])
@require_coach
def coach_student_study_overrides_save(student_id):
    if not _verify_student(g.user_id, student_id):
        return jsonify({'error': 'Aluno não encontrado'}), 404
    data = request.get_json(silent=True) or {}
    card_spot = data.get('card_spot', '').strip()
    status    = data.get('status', 'validated')
    if not card_spot:
        return jsonify({'error': 'card_spot obrigatório'}), 400
    if status not in ('validated', 'commented', 'replaced'):
        return jsonify({'error': 'status inválido'}), 400
    import json as _json
    custom_card = data.get('custom_card')
    custom_card_str = _json.dumps(custom_card) if custom_card else None
    result = save_study_override(g.user_id, student_id, card_spot, status,
                                  note=data.get('note'), custom_card=custom_card_str)
    return jsonify(result)


@app.route('/coach/student/<int:student_id>/study-overrides/<path:card_spot>', methods=['DELETE'])
@require_coach
def coach_student_study_overrides_delete(student_id, card_spot):
    if not _verify_student(g.user_id, student_id):
        return jsonify({'error': 'Aluno não encontrado'}), 404
    delete_study_override(g.user_id, student_id, card_spot)
    return jsonify({'ok': True})


@app.route('/coach/student/<int:student_id>/hand-annotations', methods=['GET'])
@require_coach
def coach_hand_annotations_list(student_id):
    if not _verify_student(g.user_id, student_id):
        return jsonify({'error': 'Aluno não encontrado'}), 404
    annotations = get_annotations(g.user_id, student_id)
    return jsonify({'annotations': annotations})


@app.route('/coach/student/<int:student_id>/hand-annotations', methods=['POST'])
@require_coach
def coach_hand_annotations_upsert(student_id):
    if not _verify_student(g.user_id, student_id):
        return jsonify({'error': 'Aluno não encontrado'}), 404
    d = request.get_json(silent=True) or {}
    decision_id          = d.get('decision_id')
    comment              = (d.get('comment') or '').strip()
    mode                 = d.get('mode', 'complement')
    coach_action         = d.get('coach_action') or None
    coach_override_label = d.get('coach_override_label') or None
    if not decision_id or not comment:
        return jsonify({'error': 'decision_id e comment são obrigatórios'}), 400
    if mode not in ('complement', 'replace'):
        return jsonify({'error': 'mode deve ser complement ou replace'}), 400
    valid_labels = ('standard', 'marginal', 'small_mistake', 'clear_mistake', None)
    if coach_override_label not in valid_labels:
        return jsonify({'error': 'coach_override_label inválido'}), 400
    if not decision_belongs_to_student(int(decision_id), student_id):
        return jsonify({'error': 'Decisão não encontrada'}), 404
    is_clean, reason = moderate_text(comment)
    if not is_clean:
        return jsonify({'error': reason}), 422
    comment = sanitize_llm_input(comment, max_len=1000)
    annotation = upsert_annotation(
        g.user_id, student_id, decision_id, comment, mode,
        coach_action, coach_override_label,
    )
    return jsonify(annotation)


@app.route('/coach/annotations/improve', methods=['POST'])
@require_coach
def coach_annotation_improve():
    """Botão "Melhorar com IA": reescreve a anotação do coach (ortografia/clareza/didática),
    preservando o sentido. NÃO salva nada — devolve a sugestão pro coach revisar e aceitar
    no front (não-destrutivo). Persona de professor; público sem conhecimento avançado."""
    d = request.get_json(silent=True) or {}
    text = (d.get('text') or '').strip()
    lang = d.get('lang') or 'pt-BR'
    if not text:
        return jsonify({'error': 'texto vazio'}), 400
    is_clean, reason = moderate_text(text)
    if not is_clean:
        return jsonify({'error': reason}), 422
    text = sanitize_llm_input(text, max_len=1000)
    try:
        from leaklab.llm_explainer import improve_coach_text
        improved = improve_coach_text(text, lang)
    except Exception:
        app.logger.exception('coach_annotation_improve falhou (user=%s)', g.user_id)
        return jsonify({'error': 'IA indisponível no momento'}), 502
    return jsonify({'improved': improved})


@app.route('/coach/student/<int:student_id>/hand-annotations/<int:decision_id>', methods=['DELETE'])
@require_coach
def coach_hand_annotations_delete(student_id, decision_id):
    if not _verify_student(g.user_id, student_id):
        return jsonify({'error': 'Aluno não encontrado'}), 404
    delete_annotation(g.user_id, student_id, decision_id)
    return jsonify({'ok': True})


# ── Sprint 6 BACK-002: Baseline + Feed de Atividade ──────────────────────────

@app.route('/coach/student/<int:student_id>/baseline', methods=['GET'])
@require_coach
def coach_baseline_get(student_id):
    if not _verify_student(g.user_id, student_id):
        return jsonify({'error': 'Aluno não encontrado'}), 404
    row = get_coach_baseline(g.user_id, student_id)
    return jsonify(row or {})


@app.route('/coach/student/<int:student_id>/baseline', methods=['POST'])
@require_coach
def coach_baseline_set(student_id):
    if not _verify_student(g.user_id, student_id):
        return jsonify({'error': 'Aluno não encontrado'}), 404
    data = request.get_json(silent=True) or {}
    baseline_date = data.get('baseline_date', '')
    if not baseline_date:
        return jsonify({'error': 'baseline_date obrigatório (YYYY-MM-DD)'}), 400
    note = data.get('note')
    row = set_coach_baseline(g.user_id, student_id, baseline_date, note)
    return jsonify(row)


@app.route('/coach/student/<int:student_id>/baseline', methods=['DELETE'])
@require_coach
def coach_baseline_delete(student_id):
    if not _verify_student(g.user_id, student_id):
        return jsonify({'error': 'Aluno não encontrado'}), 404
    delete_coach_baseline(g.user_id, student_id)
    return jsonify({'ok': True})


@app.route('/coach/student/<int:student_id>/activity-feed', methods=['GET'])
@require_coach
def coach_student_activity_feed(student_id):
    if not _verify_student(g.user_id, student_id):
        return jsonify({'error': 'Aluno não encontrado'}), 404
    limit = int(request.args.get('limit', 30))
    events = get_student_activity_feed(student_id, limit)
    return jsonify(events)


@app.route('/coach/student/<int:student_id>/progress-report', methods=['GET'])
@require_coach
def coach_student_progress_report(student_id):
    if not _verify_student(g.user_id, student_id):
        return jsonify({'error': 'Aluno não encontrado'}), 404
    report = get_baseline_comparison(g.user_id, student_id)
    if report is None:
        return jsonify({'error': 'Baseline não definida para este aluno'}), 404
    return jsonify(report)


# ── Sprint 7 BACK-006: Reviews ────────────────────────────────────────────────

@app.route('/coach/review', methods=['POST'])
@require_auth
def submit_review():
    """Aluno avalia seu coach (atual ou anterior)."""
    data = request.get_json(silent=True) or {}
    rating = data.get('rating')
    if not rating or not isinstance(rating, int) or not (1 <= rating <= 5):
        return jsonify({'error': 'rating deve ser inteiro entre 1 e 5'}), 400
    coach_id = g.user.get('coach_id')
    if not coach_id:
        # Permite avaliar um coach anterior via coach_id explícito
        coach_id = data.get('coach_id')
    if not coach_id:
        return jsonify({'error': 'Você não está vinculado a um coach'}), 400
    review_text = data.get('review_text') or ''
    if review_text:
        is_clean, reason = moderate_text(review_text)
        if not is_clean:
            return jsonify({'error': reason}), 422
    review = upsert_review(
        coach_id=int(coach_id),
        student_id=g.user_id,
        rating=rating,
        review_text=review_text or None,
    )
    return jsonify(review)


@app.route('/coach/review', methods=['DELETE'])
@require_auth
def delete_my_review():
    coach_id = g.user.get('coach_id') or request.args.get('coach_id')
    if not coach_id:
        return jsonify({'error': 'coach_id obrigatório'}), 400
    delete_review(int(coach_id), g.user_id)
    return jsonify({'ok': True})


@app.route('/coach/my-review', methods=['GET'])
@require_auth
def get_my_review_endpoint():
    """Aluno consulta a própria review do seu coach."""
    coach_id = g.user.get('coach_id') or request.args.get('coach_id')
    if not coach_id:
        return jsonify(None)
    review = get_my_review(int(coach_id), g.user_id)
    return jsonify(review)


@app.route('/coach/reviews', methods=['GET'])
@require_coach
def coach_get_reviews():
    """Coach vê todas as suas avaliações + stats."""
    limit = int(request.args.get('limit', 20))
    return jsonify(get_reviews(g.user_id, limit))


@app.route('/analyze/decision', methods=['POST'])
@require_auth
@limiter.limit("30 per hour")
def analyze_decision():
    """Análise IA de uma decisão específica identificada pelo ID do banco."""
    data = request.get_json(silent=True) or {}
    decision_id = data.get('decision_id')
    if not decision_id:
        return jsonify({'error': 'decision_id obrigatório'}), 400

    from database.schema import get_conn as _gc
    conn = _gc()
    try:
        row = conn.execute(
            """SELECT d.*, t.user_id FROM decisions d
               JOIN tournaments t ON t.id = d.tournament_id
               WHERE d.id = ?""",
            (decision_id,)
        ).fetchone()
    finally:
        conn.close()

    if not row or dict(row).get('user_id') != g.user_id:
        return jsonify({'error': 'Decisão não encontrada'}), 404

    decision = dict(row)

    # Deep-dive agêntico (investiga GTO real + mão completa + histórico) é o caminho
    # preferido; cache em chave própria (:deep). Flag DEEP_DIVE_AGENTIC=0 desliga;
    # qualquer falha cai no single-shot legado.
    agentic = os.getenv('DEEP_DIVE_AGENTIC', '1') == '1'
    cache_key = f"decision:{decision_id}:deep" if agentic else f"decision:{decision_id}"

    cached = get_llm_cache(g.user_id, cache_key)
    if cached and not data.get('force_new'):
        return jsonify({'analysis': cached, 'cached': True})

    ai_err = _check_ai_quota(g.user_id)
    if ai_err:
        return ai_err

    analysis = None
    if agentic:
        try:
            from leaklab.llm_explainer import deep_dive_decision_agentic
            analysis = deep_dive_decision_agentic(decision, g.user_id)
        except Exception:
            log.exception("analyze_decision deep-dive error; fallback para single-shot")
            cache_key = f"decision:{decision_id}"   # cai na chave legada

    if analysis is None:
        from leaklab.llm_explainer import analyze_single_decision
        analysis = analyze_single_decision(decision)

    try:
        increment_ai_calls(g.user_id)
    except Exception:
        pass

    try:
        set_llm_cache(g.user_id, cache_key, analysis)
    except Exception:
        pass

    return jsonify({'analysis': analysis, 'cached': False})


@app.route('/analyze/hand-coach', methods=['POST'])
@require_auth
@limiter.limit("30 per hour")
def hand_coach():
    """
    Análise profunda de uma mão pelo Coach IA com cache persistente.
    Verifica cache no PostgreSQL antes de chamar o LLM.
    """
    data = request.get_json(silent=True) or {}
    hand_data = data.get('hand')
    if not hand_data:
        return jsonify({'error': 'Dados da mão ausentes'}), 400

    # Chave de cache: user_id + hand_id + decisões relevantes
    hand_id    = str(hand_data.get('id', hand_data.get('handId', '')))
    cache_key  = f"hand:{hand_id}"
    force_new  = data.get('force_new', False)

    # Verificar cache
    if not force_new and hand_id:
        cached = get_llm_cache(g.user_id, cache_key)
        if cached:
            import json as _json
            try:
                analyses = _json.loads(cached)
                return jsonify({'hand_id': hand_id, 'analyses': analyses, 'cached': True})
            except Exception:
                pass

    ai_err = _check_ai_quota(g.user_id)
    if ai_err:
        return ai_err

    try:
        from leaklab.llm_explainer import _build_payload, _call_llm_api
        import json as _json

        # Filtrar só decisões com erro para análise
        decisions = hand_data.get('decisions', hand_data.get('decs', []))
        # Normalizar formato
        norm_decs = []
        for d in decisions:
            ev    = d.get('evaluation') or {}
            label = d.get('l') or d.get('label') or ev.get('label', 'standard')
            score = d.get('sc') or d.get('score') or ev.get('mistakeScore', 0)
            norm_decs.append({
                'hero_cards':  hand_data.get('cards') or hand_data.get('hero_cards', ''),
                'board':       hand_data.get('board', []),
                'street':      d.get('s') or d.get('street', ''),
                'actionTaken': d.get('t') or d.get('actionTaken', ''),
                'bestAction':  d.get('e') or d.get('bestAction', ''),
                'evaluation': {
                    'label':         label,
                    'mistakeScore':  score,
                    'scoreBreakdown': d.get('evaluation', {}).get('scoreBreakdown', {}),
                },
                'math':    d.get('math', {}),
                'context': {
                    'mRatio':       d.get('m') or (d.get('context') or {}).get('mRatio'),
                    'icmPressure':  d.get('icm') or (d.get('context') or {}).get('icmPressure', 'low'),
                    'heroStackBb':  (d.get('context') or {}).get('heroStackBb'),
                    'tournamentStage': (d.get('context') or {}).get('tournamentStage', 'unknown'),
                    'activePlayers':   (d.get('context') or {}).get('activePlayers'),
                },
                'thresholds':    d.get('thresholds', {}),
                'interpretation':d.get('interpretation', {}),
            })

        if not norm_decs:
            return jsonify({'analysis': 'Nenhuma decisão encontrada para analisar.', 'decisions': []}), 200

        payload = _build_payload(norm_decs)
        raw     = _call_llm_api(payload)

        from leaklab.llm_explainer import _parse_llm_response
        analyses = _parse_llm_response(raw, len(norm_decs))

        # Salvar no cache
        if hand_id and analyses:
            import json as _json
            try:
                set_llm_cache(g.user_id, cache_key, _json.dumps(analyses))
            except Exception:
                pass

        try:
            increment_ai_calls(g.user_id)
        except Exception:
            pass

        return jsonify({
            'hand_id':   hand_id or hand_data.get('id', ''),
            'decisions': len(norm_decs),
            'analyses':  analyses,
            'cached':    False,
        })

    except Exception as e:
        import traceback, logging
        logging.error(f"hand-coach error: {traceback.format_exc()}")
        # Retornar erro detalhado em vez de 500 silencioso
        decisions_safe = locals().get('decisions', [])
        try:
            fallback = [_template_hand_analysis(d) for d in decisions_safe[:1]]
        except Exception:
            fallback = [f'Erro ao analisar: {str(e)}']
        return jsonify({
            'hand_id':  hand_data.get('id', '') if hand_data else '',
            'analyses': fallback,
            'error':    str(e),
            'note':     'Análise gerada via template (LLM indisponível)',
        }), 200  # 200 para o frontend conseguir ler a mensagem


def _template_hand_analysis(d) -> str:
    label = d.get('l') or d.get('label') or 'standard'
    street = d.get('s') or d.get('street', 'preflop')
    action = d.get('t') or d.get('actionTaken', '')
    best   = d.get('e') or d.get('bestAction', '')
    score  = d.get('sc') or d.get('score') or              (d.get('evaluation') or {}).get('mistakeScore', 0)
    if label == 'standard':
        return f'Decisão correta no {street}. {action} foi a jogada adequada para este spot.'
    return (
        f'No {street}, a ação {action} foi inferior ao esperado ({best}), '
        f'com score de erro {score:.3f}. '
        f'Revise os fundamentos de pot odds e equity para este tipo de spot.'
    )



def _gen_study_plan(leaks, evolution, icm, *, hero, user_id, force_new,
                    player_stats, leak_source, ev_leaks):
    """Plano de estudos: prefere o loop agêntico (investiga cada leak em profundidade),
    cai no single-shot legado em qualquer falha. Flag STUDY_PLAN_AGENTIC=0 desliga."""
    from leaklab.llm_explainer import generate_study_plan
    from leaklab.academy_catalog import attach_academy_modules
    plan = None
    if os.getenv('STUDY_PLAN_AGENTIC', '1') == '1':
        try:
            from leaklab.llm_explainer import generate_study_plan_agentic
            plan = generate_study_plan_agentic(
                leaks, evolution, icm, hero=hero, user_id=user_id,
                force_new=force_new, player_stats=player_stats,
                leak_source=leak_source, ev_leaks=ev_leaks)
        except Exception:
            log.exception("study_plan agentic error; fallback para single-shot")
    if plan is None:
        plan = generate_study_plan(
            leaks, evolution, icm, hero=hero, user_id=user_id,
            force_new=force_new, player_stats=player_stats,
            leak_source=leak_source, ev_leaks=ev_leaks)
    # Link leak→aula: anexa os módulos da Academia relevantes a cada card (determinístico).
    return attach_academy_modules(plan)


@app.route('/study/plan', methods=['GET'])
@require_auth
def study_plan():
    """Gera plano de estudos personalizado via LLM baseado nos leaks reais."""
    try:
        from leaklab.llm_explainer import generate_study_plan
        from database.repositories import get_leak_ranking_gto_first

        days = int(request.args.get('days', 90))

        leak_data    = get_leak_ranking_gto_first(g.user_id, days)
        leaks        = leak_data['leaks']
        leak_source  = leak_data['source']
        evolution    = get_evolution_metrics(g.user_id, days) or []
        icm          = get_icm_performance(g.user_id, days)   or {}
        from database.repositories import get_player_stats as _get_player_stats
        player_stats = _get_player_stats(g.user_id, days)

        if not leaks and not evolution:
            return jsonify({'error': 'Sem dados suficientes — importe torneios primeiro'}), 400

        from database.repositories import get_tournaments
        tourns = get_tournaments(g.user_id, limit=1)
        hero   = tourns[0]['hero'] if tourns else 'Jogador'

        # Verificar se o aluno tem coach
        from database.schema import get_conn as _gc
        import json as _json
        _conn = _gc()
        try:
            _row = _conn.execute("SELECT coach_id FROM users WHERE id=?", (g.user_id,)).fetchone()
            coach_id_val = dict(_row).get('coach_id') if _row else None
        finally:
            _conn.close()

        # Aluno com coach não pode forçar regerar — plano é gerenciado pelo coach
        force_new = request.args.get('new') == '1' and not coach_id_val

        from database.repositories import get_ev_leaks as _get_ev_leaks
        _ev = _get_ev_leaks(g.user_id, days).get('leaks')   # #24/#25: prioriza por bb
        plan = _gen_study_plan(leaks, evolution, icm, hero=hero, user_id=g.user_id,
                               force_new=force_new, player_stats=player_stats,
                               leak_source=leak_source, ev_leaks=_ev)

        # Aplicar overrides do coach nos cards para que o aluno veja o mesmo conteúdo
        coach_managed = False
        if coach_id_val:
            try:
                overrides = get_study_overrides(coach_id_val, g.user_id)
                coach_managed = len(overrides) > 0
                for ov in overrides:
                    for card in plan.get('cards', []):
                        if card.get('spot') != ov['card_spot']:
                            continue
                        if ov['status'] == 'replaced' and ov.get('custom_card'):
                            try:
                                custom = _json.loads(ov['custom_card'])
                                for field in ('titulo', 'diagnostico', 'exercicio'):
                                    if custom.get(field):
                                        card[field] = custom[field]
                                if custom.get('recursos'):
                                    card['recursos'] = custom['recursos']
                            except Exception:
                                pass
                        if ov['status'] == 'commented' and ov.get('note'):
                            card['coach_note'] = ov['note']
                        break
            except Exception:
                pass

        plan['coach_managed'] = coach_managed
        # Treino INTERNO sugerido a partir dos leaks reais, calculado no servidor e NUNCA pedido
        # ao LLM: é um fato sobre os torneios dele (qual posição sangra e quanto), e fato em
        # prompt volta alucinado. O plano ganha um destino clicável em vez de só um conselho.
        try:
            from leaklab.leak_trainer import sugerir_memorizacao_de_range
            plan['treino_sugerido'] = sugerir_memorizacao_de_range(g.user_id)
        except Exception:
            app.logger.exception('falha ao sugerir memorizacao de range no plano')
            plan['treino_sugerido'] = None
        # plan['source'] já é setado por generate_study_plan com leak_source
        return jsonify(plan)

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({
            'nivel': 'intermediario',
            'resumo': 'Erro ao gerar plano. Tente regerar.',
            'cards': [],
            'error': str(e)
        }), 200  # 200 para o CORS não ser bloqueado


@app.route('/analyze/replay-coach', methods=['POST'])
@require_auth
def replay_coach():
    """
    Análise Coach IA diretamente do replayer.
    Recebe os dados do erro já processados, sem precisar do formato antigo.
    """
    from leaklab.llm_explainer import coach_replay_decision
    d = request.get_json(silent=True) or {}

    # Validar mínimo necessário
    action_taken = d.get('action_taken','')
    best_action  = d.get('best_action','')
    street       = d.get('street','preflop')
    if not action_taken:
        return jsonify({'error': 'action_taken obrigatório'}), 400

    cache_key = f"replay:{d.get('hand_id','')}:{street}:{action_taken}"
    cached = get_llm_cache(g.user_id, cache_key)
    if cached:
        return jsonify({'analysis': cached, 'cached': True})

    analysis = coach_replay_decision(
        street       = street,
        action_taken = action_taken,
        best_action  = best_action,
        hero_cards   = d.get('hero_cards', []),
        board        = d.get('board', []),
        hand_equity  = d.get('hand_equity'),
        pot_odds     = d.get('pot_odds'),
        m_ratio      = d.get('m_ratio'),
        icm_pressure = d.get('icm_pressure','low'),
        error_score  = d.get('error_score'),
        error_label  = d.get('error_label',''),
        math_penalty = d.get('math_penalty',0),
        range_penalty= d.get('range_penalty',0),
    )

    if analysis and not analysis.startswith('Erro'):
        set_llm_cache(g.user_id, cache_key, analysis)

    return jsonify({'analysis': analysis, 'cached': False})


@app.route('/history/tournament/<tournament_id>', methods=['DELETE'])
@require_auth
def delete_tournament(tournament_id):
    """Deleta um torneio específico do usuário (e suas decisões via CASCADE)."""
    from database.schema import get_conn as _gc
    conn = _gc()
    try:
        row = conn.execute(
            "SELECT id FROM tournaments WHERE user_id=? AND tournament_id=?",
            (g.user_id, tournament_id)
        ).fetchone()
        if not row:
            return jsonify({'error': 'Torneio não encontrado'}), 404
        db_id = row['id']
        # Limpa o histórico SRS das decisões deste torneio ANTES de deletá-las — senão
        # as drill_sessions ficam órfãs e ainda contam no "histórico de drill" (get_drill_stats
        # conta FROM drill_sessions sem JOIN). Não há ON DELETE CASCADE em drill_sessions.
        conn.execute("DELETE FROM drill_sessions WHERE decision_id IN "
                     "(SELECT id FROM decisions WHERE tournament_id=?)", (db_id,))
        conn.execute("DELETE FROM decisions WHERE tournament_id=?", (db_id,))
        # Limpa os gto_hand_requests do torneio — senão ficam órfãos (apontando p/ torneio inexistente)
        # e erram "Torneio sem raw_text no banco" quando o worker tenta processá-los.
        try:
            conn.execute("DELETE FROM gto_hand_requests WHERE tournament_id=?", (db_id,))
        except Exception:
            pass
        conn.execute("DELETE FROM tournaments WHERE id=?", (db_id,))
        conn.commit()
        return jsonify({'ok': True, 'deleted': tournament_id})
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        conn.close()


@app.route('/debug/tournaments', methods=['GET'])
@require_auth
def debug_tournaments():
    """Endpoint temporário para diagnóstico de datas."""
    from database.schema import get_conn as _gc
    conn = _gc()
    try:
        rows = conn.execute(
            "SELECT tournament_id, played_at, imported_at FROM tournaments WHERE user_id=? LIMIT 5",
            (g.user_id,)
        ).fetchall()
        result = []
        for r in rows:
            d = dict(r)
            result.append({
                'tournament_id': d['tournament_id'],
                'played_at_raw':   str(d['played_at']),
                'played_at_type':  type(d['played_at']).__name__,
                'imported_at_raw': str(d['imported_at'])[:19],
            })
        return jsonify(result)
    finally:
        conn.close()

@app.route('/admin/reset-my-data', methods=['POST'])
@require_auth
def reset_my_data():
    """
    Deleta TODOS os dados do usuário logado (torneios, decisões, cache LLM).
    Útil para testes. NÃO deleta o usuário em si.
    """
    from database.schema import get_conn
    conn = get_conn()
    try:
        # Deletar em ordem para respeitar foreign keys
        conn.execute("""
            DELETE FROM llm_cache WHERE user_id = ?
        """, (g.user_id,))
        # SRS de todas as decisões do usuário (todas serão deletadas) — evita órfãs nas stats.
        conn.execute("DELETE FROM drill_sessions WHERE user_id = ?", (g.user_id,))
        conn.execute("""
            DELETE FROM decisions WHERE tournament_id IN (
                SELECT id FROM tournaments WHERE user_id = ?
            )
        """, (g.user_id,))
        conn.execute("""
            DELETE FROM tournaments WHERE user_id = ?
        """, (g.user_id,))
        conn.commit()
        return jsonify({'ok': True, 'message': 'Dados resetados com sucesso'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        conn.close()


# In-memory cache do replay por (tid_db, hand_id, user_id).
# `_build_replay_data` re-roda engine + preflop GTO + strategy lookup por step —
# pesado (300-1500ms). TTL curto (5min) cobre uma sessao de review sem ficar
# stale entre sessoes. Limit 256 entradas evita memory leak em prod.
_REPLAY_CACHE: dict = {}
_REPLAY_CACHE_LOCK = threading.Lock()
_REPLAY_CACHE_TTL = 300  # 5 min
_REPLAY_CACHE_MAX = 256

def _replay_cache_get(key):
    with _REPLAY_CACHE_LOCK:
        entry = _REPLAY_CACHE.get(key)
        if not entry:
            return None
        if time.time() - entry['ts'] > _REPLAY_CACHE_TTL:
            _REPLAY_CACHE.pop(key, None)
            return None
        return entry['data']

def _replay_cache_set(key, data):
    with _REPLAY_CACHE_LOCK:
        if len(_REPLAY_CACHE) >= _REPLAY_CACHE_MAX:
            # Evict mais antigo
            oldest = min(_REPLAY_CACHE.items(), key=lambda kv: kv[1]['ts'])
            _REPLAY_CACHE.pop(oldest[0], None)
        _REPLAY_CACHE[key] = {'ts': time.time(), 'data': data}



from database.repositories import _align_score_to_label   # porta unica da politica score<->label

from leaklab import verdict as _verdict_mod   # porta unica da politica de veredito


def _procedencia_da_linha(d):
    """Procedencia de uma linha JA GRAVADA. Usa a coluna quando existe; senao deriva da fonte.

    Linhas anteriores a migracao de 24/08 nao tem `verdict_source`. Derivar na leitura evita um
    backfill que reescreveria 10 mil linhas para um campo que o motor ja sabe recalcular -- e
    evita o estado "as vezes preenchida", que e pior que nao existir.
    """
    if not d:
        return None
    gravado = d.get('verdict_source')
    if gravado:
        return gravado
    fonte = (d.get('ev_loss_source') or '').lower()
    tem_gab = bool(d.get('gto_label')) or d.get('ev_loss_bb') is not None
    return _verdict_mod.procedencia(
        {'available': tem_gab, 'ev_loss_source': fonte} if tem_gab else None,
        None,
        d.get('street'))


# Teto de proporcionalidade do all-in RECOMENDADO. Um jam so e jogada quando o dinheiro ja
# esta comprometido: com stack muito maior que o pote, all-in nao e "a versao forte da aposta",
# e outra jogada. 3x e onde as recomendacoes que passam pelo solver se concentram (129 de 130
# do acervo estao abaixo disso).
_TETO_JAM_SOBRE_POTE = 3.0
_ACOES_DE_JAM = ('allin', 'shove', 'jam', 'all-in')


def _best_action_proporcional(best, pot_bb, stack_bb, street=None):
    """Troca all-in por `bet` quando o jam recomendado e desproporcional ao pote -- POSTFLOP.

    Tres juizes de poker independentes pegaram isto em 25/08: o card recomendava all-in de 9x,
    17x, 19x e ate **22x o pote** com Ts2h, Kc4d, AdKs. A origem NAO era o motor -- reprocessando
    as mesmas maos, `evaluate_decision` devolve `check`. Quem manda o jam e o NO DO SOLVER
    consultado ao vivo (`verdict_layer: live`, `gto_action: allin`), num spot de SPR ~10: e no
    de profundidade errada vazando para um spot fundo, a mesma familia ja registrada em
    [[project_degenerate_pot_nodes]].

    O teto e uma REDE, nao um substituto do conserto do no: enquanto a captura nao for revista,
    ele impede que a tela mande o aluno colocar o torneio inteiro num pote de 5bb.

    ── SO POSTFLOP, e isto foi conserto de 27/08 ─────────────────────────────────────────────

    A 1a versao nao olhava a street, e a razao do teto e SPR -- que e conceito de postflop. No
    preflop o pote e so os blinds (`pot_at_decision_bb` = 1,0), entao **todo** jam acima de 3bb
    passa do teto: um push de 11,2bb num pote de 1bb, que e a jogada mais padrao que existe em
    MTT, aparecia na tela como "aposte".

    Medido no acervo: das 149 decisoes em que o teto trocava a palavra, **146 eram preflop** e so
    3 postflop -- 98% de disparo errado, incluindo 10 acusacoes. Um juiz de poker pegou o sintoma
    ("o aluno le `aposte` onde o motor quis dizer all-in") e a origem era este guarda, escrito por
    mim no dia anterior.
    """
    if (street or '').lower() == 'preflop':
        return best
    if (best or '').lower() not in _ACOES_DE_JAM:
        return best
    # Recusar e RECUSAR: devolver `bet` nomeava uma acao que ninguem computou, sem tamanho, e
    # a tela dizia "aposte" onde o solver disse all-in. `None` diz o que de fato temos -- nenhuma
    # recomendacao que sustentemos -- e o motivo viaja em `best_action_recusado`.
    try:
        pote, stack = float(pot_bb or 0), float(stack_bb or 0)
    except (TypeError, ValueError):
        return best
    if pote > 0 and stack > _TETO_JAM_SOBRE_POTE * pote:
        return None
    return best


def _pode_falar_como_gto_da_linha(d, multiway=None, procedencia=None, motivo=None):
    """O gate COMPLETO para uma linha: procedencia + custo + a recusa em graduar multiway.

    Existe como funcao porque ele e consultado em mais de uma porta (o `/replay` e a lista do
    torneio), e a regra 5 deste projeto e explicita: regra em N lugares vira funcao. A versao
    anterior tinha a expressao inline no /replay e NADA na lista -- a lista servia o veredito
    sem dizer se ele tem direito a linguagem de GTO.

    `multiway=None` deixa a funcao inferir de `n_active_opponents` + street; o /replay passa o
    proprio `_mw_spot`, que ja considera os casos que so ele conhece.
    """
    if not d:
        return False
    if multiway is None:
        try:
            n_opp = int(d.get('n_active_opponents') or 0)
        except (TypeError, ValueError):
            n_opp = 0
        multiway = n_opp >= 2 and (d.get('street') or '').lower() != 'preflop'
    if multiway:
        # O solver e HU-only: em multiway o produto se RECUSA a graduar, e liberar a palavra
        # "leak" ali seria acusar com a autoridade de um gabarito que nao existe.
        return False
    # `procedencia` explicita existe para o /replay: la o veredito EXIBIDO pode ter vindo da
    # camada viva, e o gate precisa julgar a fonte que decidiu, nao a que esta gravada. Quem nao
    # passa (a lista do torneio) segue lendo a coluna, como sempre.
    # `motivo` viaja junto pelo mesmo motivo do `_tem_custo_da_linha`: filtrar o custo numa porta
    # e nao na outra deixou 4 decisoes dizendo "posso falar como GTO" com `verdict_has_cost: false`
    # na MESMA linha -- o portao de aceite pegou na rodada seguinte.
    return _verdict_mod.pode_falar_como_gto(
        procedencia or _procedencia_da_linha(d), _tem_custo_da_linha(d, motivo))


def _tem_custo_da_linha(d, motivo=None):
    """Existe EV em bb de fonte que vale como quantidade, nesta linha gravada?

    A COLUNA nao basta sozinha. Medido em 27/08 por um juiz de QA: 9 linhas com
    `verdict_has_cost: true` e **sem `ev_loss_bb`**, todas com `ev_loss_motivo: nao_confiavel` --
    o numero exibido passa pelo filtro de confiabilidade (`ev_loss_trustworthy`) e a coluna nao.
    Duas portas para o mesmo fato: "tem custo" dizia sim enquanto o custo nao chegava a tela.
    Em 3 delas isso liberava `pode_falar_como_gto`.

    Custo que nao sobrevive ao filtro nao e custo para efeito de autoridade.
    """
    if not d:
        return False
    if (motivo or '') == 'nao_confiavel':
        return False
    # `ev_loss_motivo` NAO existe na linha do banco -- e campo calculado no display
    # (`_ev_e_motivo`). A 1a versao deste guarda lia a chave direto do `decision` e nunca
    # disparava: 10 linhas seguiram com `verdict_has_cost: true` e `ev_loss_bb` nulo depois do
    # "conserto". Quem chama passa o motivo quando o tem.
    if (d.get('ev_loss_motivo') or '') == 'nao_confiavel':
        return False
    if d.get('verdict_has_cost') is not None:
        return bool(d.get('verdict_has_cost'))
    return _verdict_mod.tem_custo_medido(
        {'available': True, 'ev_loss_bb': d.get('ev_loss_bb'),
         'ev_loss_source': d.get('ev_loss_source')}, None)


# ── Compartilhar uma mão ───────────────────────────────────────────────────────────────────
#
# Do benchmark, e a única coisa deste produto que sai dele: alguém posta o link num grupo e quem
# clica vê o que o GrindLab disse da mão. Ver `leaklab/mao_compartilhada.py` para as três decisões
# de desenho -- em resumo: compartilhar é ATO (token aleatório, revogável), o payload sai por
# LISTA BRANCA, e nick de ninguém viaja.

@app.route('/replay/share', methods=['POST'])
@require_auth
@limiter.limit("20 per hour")
def criar_link_da_mao():
    """Cria o link público de uma mão do PRÓPRIO usuário."""
    from leaklab.mao_compartilhada import criar
    body = request.get_json(silent=True) or {}
    bruto = body.get('tournament_id')
    # Aceita o id INTERNO (int) e o id do SITE (string, que é o que o replay carrega).
    try:
        tid = int(bruto or 0)
    except (TypeError, ValueError):
        t = get_tournament(g.user_id, str(bruto or ''))
        tid = int(t['id']) if t else 0
    hid = str(body.get('hand_id') or '').strip()
    if not tid or not hid:
        return jsonify({'error': 'tournament_id e hand_id sao obrigatorios'}), 400
    step = body.get('step_idx')
    step = int(step) if isinstance(step, (int, float)) and int(step) >= 0 else None
    token = criar(g.user_id, tid, hid, step_idx=step,
                  pergunta=str(body.get('question') or '').strip() or None)
    if not token:
        # 404 e nao 403: dizer "existe mas nao e sua" ja e informacao sobre a mao de outro.
        return jsonify({'error': 'mao nao encontrada'}), 404
    return jsonify({'token': token})


@app.route('/replay/share/<token>', methods=['DELETE'])
@require_auth
def revogar_link_da_mao(token):
    """Desliga o link. Quem compartilhou tem de poder voltar atrás."""
    from leaklab.mao_compartilhada import revogar
    return jsonify({'ok': revogar(g.user_id, str(token))})


@app.route('/h/<token>/vote', methods=['POST'])
@limiter.limit("30 per hour")
def votar_mao_compartilhada(token):
    """PÚBLICO: vota na decisão marcada ANTES de ver o veredito. Agregado por ação — nenhum
    visitante identificável é gravado. 30/h por IP: mais que isso é script, não curiosidade."""
    from leaklab.mao_compartilhada import votar
    acao = (request.get_json(silent=True) or {}).get('action', '')
    placar = votar(str(token), acao)
    if placar is None:
        return jsonify({'error': 'link invalido ou acao nao votavel'}), 404
    return jsonify({'votos': placar})


@app.route('/h/<token>/comment', methods=['POST'])
@require_auth
@limiter.limit("20 per hour")
def comentar_mao_compartilhada(token):
    """Comentário exige CONTA (anônimo vota, não escreve). Free serve: o link é porta de
    entrada da comunidade, não feature paga."""
    from leaklab.mao_compartilhada import comentar
    texto = (request.get_json(silent=True) or {}).get('text', '')
    cid = comentar(str(token), g.user_id, texto)
    if cid is None:
        return jsonify({'error': 'link invalido ou texto vazio'}), 400
    return jsonify({'id': cid})


@app.route('/h/<token>/comment/<int:comment_id>', methods=['DELETE'])
@require_auth
def apagar_comentario_mao(token, comment_id):
    """Autor apaga o que escreveu; dono da mão modera a própria página."""
    from leaklab.mao_compartilhada import apagar_comentario
    return jsonify({'ok': apagar_comentario(comment_id, g.user_id)})


@app.route('/h/<token>', methods=['GET'])
@limiter.limit("60 per minute")
def ler_mao_compartilhada(token):
    """PÚBLICO, sem login. O limite existe porque endpoint aberto sem limite é convite a
    varredura -- ainda que o token de 128 bits aleatórios não seja enumerável."""
    from leaklab.mao_compartilhada import ler
    dados = ler(str(token))
    if not dados:
        return jsonify({'error': 'link invalido ou revogado'}), 404
    return jsonify(dados)


@app.route('/tournament/<int:tid>/hero-hud', methods=['GET'])
@require_auth
def tournament_hero_hud(tid):
    """HUD do HERÓI neste torneio (29/08): descritivo da sessão, com amostra declarada.
    Computado do raw_text porque o upload grava perfis SÓ de oponentes — e sem gates de
    amostra, porque descrição de sessão não é read de exploit (ver hud_do_torneio.py)."""
    from leaklab.hud_do_torneio import hud_do_heroi
    from leaklab.parser import parse_hand_history
    t = get_tournament_by_db_id(g.user_id, tid)
    if not t or not t.get('raw_text'):
        return jsonify({'error': 'Torneio não encontrado'}), 404
    try:
        hands = parse_hand_history(t['raw_text'])
        hud = hud_do_heroi(hands, t.get('hero') or '')
    except Exception:
        app.logger.exception('hero-hud falhou (t=%s)', tid)
        hud = None
    if not hud:
        return jsonify({'available': False})
    return jsonify({'available': True, **hud})


@app.route('/replay/<tournament_id>/<hand_id>', methods=['GET'])
@require_auth
def get_replay(tournament_id, hand_id):
    """Constrói dados de replay para uma mão específica."""
    import re as _re

    t = None
    if tournament_id.isdigit():
        t = get_tournament_by_db_id(g.user_id, int(tournament_id))
    if not t:
        t = get_tournament(g.user_id, tournament_id)
    if not t:
        return jsonify({'error': 'Torneio não encontrado'}), 404

    # Cache hit pelo replay pesado (sem coach_annotations — essas sao leves e por user)
    _cache_key = (t['id'], str(hand_id), g.user_id)
    cached_replay = _replay_cache_get(_cache_key)
    if cached_replay is not None:
        replay = dict(cached_replay)  # shallow copy pra adicionar anotações
        # Re-fetch coach_annotations (rapido, e podem ter sido editadas)
        db_decisions = get_decisions(t['id'])
        hand_db_decisions = [d for d in db_decisions if str(d.get('hand_id')) == str(hand_id)]
        if hand_db_decisions:
            ann_list = get_annotations_for_decisions([d['id'] for d in hand_db_decisions])
            ann_map = {str(a['decision_id']): a for a in ann_list}
            replay['coach_annotations'] = {
                str(d['id']): {**ann_map[str(d['id'])],
                               'street': d.get('street'), 'action_taken': d.get('action_taken')}
                for d in hand_db_decisions if str(d['id']) in ann_map
            }
        else:
            replay['coach_annotations'] = {}
        return jsonify(replay)

    raw_text = t.get('raw_text')
    if not raw_text:
        return jsonify({'error': 'Hand history não disponível — reimporte o torneio'}), 404

    # Re-parsear o hand history
    try:
        hands = parse_pokerstars_file_from_text(raw_text)
    except Exception as e:
        return jsonify({'error': f'Erro ao parsear: {str(e)}'}), 422

    # Encontrar a mão específica
    target = next((h for h in hands if str(h.hand_id) == str(hand_id)), None)
    if not target:
        return jsonify({'error': f'Mão {hand_id} não encontrada no torneio'}), 404

    # GG (hash estável no torneio) → mapa do torneio. CoinPoker (hash por-mão) → mapa DA MÃO
    # (Vilão 1-6), senão o índice global viraria "Vilão 1547".
    _asite = (t.get('site') or '').lower()
    if _asite in ('ggpoker', 'coinpoker'):
        _asrc = target.raw_text if _asite == 'coinpoker' else raw_text
        _apply_alias_to_hand(target, _build_gg_alias_map(_asrc, t.get('hero') or target.hero))

    # Buscar decisões do banco para enriquecer com gto_label/gto_action
    _db_all      = get_decisions(t['id'])
    _db_hand     = [d for d in _db_all if str(d.get('hand_id')) == str(hand_id)]
    # Balde (street, action_taken) → linhas do banco, consumidas EM ORDEM. Não é índice: a
    # chave NÃO é única (o hero age duas vezes na mesma street ao pagar um open e depois
    # enfrentar um 3-bet), e um dict fazia as duas decisões dividirem um veredito só.
    # Passa `_db_hand` INTEIRO de propósito — filtrar por `gto_label` aqui era a outra
    # metade do defeito. Ver leaklab/pareamento_decisoes.py.
    _gto_index   = balde_de_gto_do_banco(_db_hand)

    # Re-executar o engine ao vivo para garantir scores/labels atualizados
    # O banco pode ter dados de versões antigas do engine com bugs corrigidos
    try:
        from leaklab.pipeline import build_decision_inputs_for_hand
        from leaklab.decision_engine_v11 import evaluate_decision as _eval
        live_decisions = []
        for di in build_decision_inputs_for_hand(target):
            r = _eval(di)
            action_norm = (r.get('actionTaken','') or '').rstrip('s') or r.get('actionTaken','')
            gto_data = _gto_index.proxima((di['street'], action_norm)) or {}
            live_decisions.append({
                'hand_id':      str(target.hand_id),
                'street':       di['street'],
                'action_taken': r.get('actionTaken', ''),
                'best_action':  r.get('bestAction', ''),
                'label':        r['evaluation']['label'],
                'score':        r['evaluation']['mistakeScore'],
                'context':      di.get('context', {}),
                'math':         di.get('math', {}),
                'thresholds':   r.get('thresholds', {}),
                'breakdown':    r['evaluation'].get('scoreBreakdown', {}),
                # PROCEDÊNCIA do veredito VIVO, na mesma fonte de `label`/`score` (o dict `r`).
                # Ler da coluna aqui seria misturar instantes: o label é recomputado ao vivo e a
                # coluna guarda o de ontem. Sem estes campos, `_procedencia_da_linha` caía SEMPRE
                # no ramo de derivação e a coluna gravada virava write-only — a mesma forma do
                # clamp que ficou desligado por não receber o argumento.
                'verdict_source':   r.get('verdictSource'),
                'verdict_has_cost': r.get('verdictHasCost'),
                'gto_label':    gto_data.get('gto_label'),
                'gto_action':   gto_data.get('gto_action'),
                'gto_depth_capped': 1 if (gto_data.get('depth_capped') or gto_data.get('gto_depth_capped')) else 0,
                # Os campos-viajantes do EV, com a MESMA semantica do save_decisions: a regua
                # de confianca (ev_loss_trustworthy_row) le estas colunas, e este dict vivo
                # SUBSTITUI a linha do banco no /replay. Sem eles, o dict sintetico chegava a
                # _ev_e_motivo com ev_loss_source=None e todo EV preflop saia "sem confianca"
                # enquanto o coach (que le a LINHA) mostrava o numero (13/08, K9o -0.9BB).
                'facing_bet':   ((di.get('spot') or {}).get('facingToBb')
                                 if (di.get('spot') or {}).get('facingToBb') is not None
                                 else gto_data.get('facing_bet')),
                'ev_loss_bb':   ((r.get('gto') or {}).get('ev_loss_bb')
                                 if (r.get('gto') or {}).get('ev_loss_bb') is not None
                                 else (r.get('preflop_gto') or {}).get('ev_loss_bb')),  # #24 (live)
                'ev_loss_source': ((r.get('gto') or {}).get('ev_loss_source')
                                   or (r.get('preflop_gto') or {}).get('ev_loss_source')),
                'stack_bb':     (di.get('context') or {}).get('heroStackBb'),
                'estimated_equity': (di.get('math') or {}).get('estimatedHandEquity'),
                'pot_size':     (di.get('spot') or {}).get('potBb'),
                'bet_intent':   r.get('bet_intent'),
                'threebet_intent': r.get('threebet_intent'),  # intenção do 3-bet (valor/merge/light)
                'reco_rationale': r.get('reco_rationale'),
                'icm_zone_approx': bool(r.get('icm_zone_approx')),  # gate zona-ICM → "≈ Aproximação chipEV"
                '_di':          di,
            })
        hand_decisions = live_decisions
    except Exception:
        # Fallback para dados do banco se engine falhar
        hand_decisions = _db_hand

    # Construir replay data (parte pesada — vai pro cache)
    replay = _build_replay_data(target, hand_decisions, t.get('hero', target.hero))

    # HUD Fase 2-3: perfil do vilão + exploit por step. t['id'] = id LOCAL (chave do
    # opponent_profiles). Mesma fonte do aluno e do coach (helper compartilhado).
    _attach_opponent_hud(replay, t['id'], hands=hands)
    _attach_equity_real_vs_mostrada(replay, target)

    _replay_cache_set(_cache_key, dict(replay))

    # Incluir anotações do coach para o aluno visualizar no replay (rapido, fora do cache)
    db_decisions = get_decisions(t['id'])
    hand_db_decisions = [d for d in db_decisions if str(d.get('hand_id')) == str(hand_id)]
    if hand_db_decisions:
        ann_list = get_annotations_for_decisions([d['id'] for d in hand_db_decisions])
        ann_map = {str(a['decision_id']): a for a in ann_list}
        replay['coach_annotations'] = {
            str(d['id']): {**ann_map[str(d['id'])],
                           'street': d.get('street'), 'action_taken': d.get('action_taken')}
            for d in hand_db_decisions if str(d['id']) in ann_map
        }
    else:
        replay['coach_annotations'] = {}

    # PKO flag — frontend mostra badge no header do Replayer.
    replay['is_pko'] = bool(t.get('is_pko'))

    return jsonify(replay)


def _build_gg_alias_map(full_raw, hero):
    """GG anonimiza oponentes com um hexa ESTÁVEL por torneio. Mapeia cada hexa → 'Vilão N'
    por ordem de 1ª aparição (determinístico) p/ uma identidade consistente em todas as mãos."""
    import re as _re
    seen = []
    for m in _re.finditer(r'^Seat \d+: (.+?) \([0-9.,]+ in chips', full_raw or '', _re.MULTILINE):
        name = m.group(1).strip()
        if name and name != hero and name not in seen:
            seen.append(name)
    return {name: f'Vilão {i + 1}' for i, name in enumerate(seen)}


def _apply_alias_to_hand(hand, alias):
    """Aplica o de/para (hexa → 'Vilão N') na mão: raw_text, seats, actions, players, bounties.
    Idempotente o suficiente; só toca nomes que estão no mapa (oponentes anônimos do GG)."""
    if not alias:
        return hand
    rt = hand.raw_text or ''
    for hexname, al in alias.items():
        rt = rt.replace(hexname, al)
    hand.raw_text = rt
    for s in (hand.seats or []):
        s['name'] = alias.get(s.get('name'), s.get('name'))
    for a in (hand.actions or []):
        a.player = alias.get(a.player, a.player)
    hand.players = [alias.get(p, p) for p in (hand.players or [])]
    if getattr(hand, 'bounties', None):
        hand.bounties = {alias.get(k, k): v for k, v in hand.bounties.items()}
    return hand


def _ev_para_exibir(decision, _di, _spot):
    """O `ev_loss_bb` gravado, ou `None` quando ele nao cabe no jogo.

    Porta unica do CARD para o EV, espelhando o que o motor ja faz para severidade. Antes desta
    funcao o motor gateava e a tela nao, e a tela mostrava numero impossivel: `-3588 bb` num
    stack de 32,2bb, reportado por um usuario. Medido no acervo, 62 decisoes tinham EV maior do
    que cabe na mao, 34 delas com `clear_mistake`.

    Devolve `None` de proposito, e nao um valor "consertado": o pote com que o no foi solvado nao
    e gravado em lugar nenhum, entao nao ha como reescalar — so da para conferir e calar.
    """
    return _ev_e_motivo(decision, _di, _spot)[0]


def _ev_e_motivo(decision, _di, _spot):
    """`(valor, motivo)` — o EV a exibir e, quando ele nao vai, POR QUE nao vai.

    Sao TRES ausencias diferentes, e trata-las como uma so seria a celula em branco que este
    produto ja pagou caro para nao ter:

      · `sem_gabarito`   nao ha carta nem no: nao existe linha otima contra a qual medir custo
      · `fora_de_escala` o numero e IMPOSSIVEL (passa do pote + 2 stacks) — 62 decisoes medidas
      · `nao_confiavel`  os guardas antigos desconfiam (teto de fold, profundidade, fonte) sem
                         que o valor seja absurdo — **264 decisoes**, e chama-las de "fora de
                         escala" seria impreciso: elas cabem no jogo, so nao merecem confianca
    """
    if not decision:
        return None, None
    ev = decision.get('ev_loss_bb')
    if ev is None:
        return None, 'sem_gabarito'
    try:
        # Insumos CANONICOS: as colunas da LINHA, iguais aos do coach e dos agregadores.
        # A versao anterior passava pot/equity/facing do spot REPARSEADO e, num caso
        # limitrofe do teto de fold, o card dizia "sem confianca" enquanto o badge do
        # coach mostrava -0.9BB para o MESMO numero (13/08). Mesma regra + mesmos
        # insumos = mesma resposta em toda porta, por construcao.
        from leaklab.decision_engine_v11 import ev_loss_trustworthy_row
        ok = ev_loss_trustworthy_row(decision)
    except Exception:
        return ev, None    # sem conseguir avaliar, mantem o comportamento antigo
    if ok:
        return ev, None
    # Impossivel x apenas duvidoso: a fronteira e a mesma do teto fisico do motor —
    # com os MESMOS insumos de linha da regra acima.
    try:
        _st = float(decision.get('stack_bb') or 0)
        _pt = float(decision.get('pot_size') or 0)
        impossivel = _st > 0 and abs(float(ev)) > _pt + 2.0 * _st
    except (TypeError, ValueError):
        impossivel = False
    return None, ('fora_de_escala' if impossivel else 'nao_confiavel')


def _sem_ev_impossivel(hand_strategy, decision, _di, _spot):
    """`hand_strategy` com os EVs removidos quando eles nao cabem no jogo. Frequencias intactas.

    Mesma regra e mesma porta do `_ev_para_exibir`: as duas superficies do card (o selo de custo e
    as linhas por acao) tem de calar juntas, senao o card volta a se contradizer — foi assim que
    263 cards mostraram texto de uma fonte e veredito de outra em 05/08.
    """
    if not hand_strategy or not hand_strategy.get('actions'):
        return hand_strategy
    if _ev_para_exibir(decision, _di, _spot) is not None:
        return hand_strategy
    # Sem EV confiavel: zera SO os campos de EV, preservando o resto do bloco.
    limpo = dict(hand_strategy)
    limpo['actions'] = [{**a, 'ev_bb': None, 'ev_loss_bb': None}
                        for a in hand_strategy['actions']]
    return limpo


def _build_replay_data(hand, decisions_db, hero_override=None):
    """Constrói a timeline completa de replay a partir de uma ParsedHand.

    SOMENTE LEITURA: o veredito é derivado a cada requisição e NÃO é gravado. Havia dois blocos
    que diziam persistir o resultado da reconciliação (`update_decision_gto`), mas nenhum dos
    dois jamais executou — referenciavam `_db_hand`, local de `get_replay`, e o `except: pass`
    engolia o NameError. Removidos, porque comentário que descreve o contrário do que o código
    faz é pior que ausência de código.

    Consequência a conhecer: o `gto_label` gravado em `decisions` é o do IMPORT, não o
    reconciliado que o card mostra. Tudo que lê a coluna (cobertura, scoring de leak, plano de
    estudo) enxerga o valor do import. Ligar a persistência é decisão de produto, não de
    refactor: mudaria agregados que o usuário já vê. Enquanto não for decidido, o invariante
    é este, e `test_replay_nao_grava.py` o mantém."""
    import re as _re
    from leaklab.hand_state_builder import _normalize_action
    from leaklab.parser import SEAT_OUT_OF_HAND_RE

    def _parse_summary(raw):
        """Extrai resultado, vencedores e cartas reveladas do SUMMARY.

        Reportado pelo usuário: mãos da ACR paravam antes do fim no replay (às vezes no turn,
        às vezes no river) — a conclusão (cartas reveladas + vencedor) nunca aparecia. Causa:
        os regexes abaixo foram escritos só contra o formato PokerStars/GGPoker
        ("and won (1,110)", valor entre parênteses, sem centavos). A ACR escreve
        "and won 1110.00", sem parênteses e com centavos, e tem duas linhas de SUMMARY que
        não existiam aqui: "did not show and won X" (ganhou sem showdown) e
        "showed [...] and lost with ..." (perdedor revelado, que nenhum site tinha).
        Sem nenhuma linha reconhecida, result['winners'] e result['seats'] ficavam vazios,
        a condição que dispara o frame de conclusão nunca era verdadeira, e o replay
        terminava na última ação — que podia ser antes do river ser sequer mostrado.
        """
        start = raw.find('*** SUMMARY ***')
        if start < 0: return {}
        s = raw[start:]
        result = {'winners':[], 'seats':[], 'board':[], 'total_pot':None}
        m = _re.search(r'Total pot ([\d,]+(?:\.\d+)?)', s)
        if m: result['total_pot'] = int(float(m.group(1).replace(',', '')))
        m = _re.search(r'Board \[([^\]]+)\]', s)
        if m: result['board'] = m.group(1).split()
        # Valor com OU sem parênteses, com OU sem centavos: PokerStars/GG usam a primeira
        # forma, ACR a segunda.
        _AMT = r'\(?([\d,]+(?:\.\d+)?)\)?'
        for line in s.split('\n'):
            # A descrição da mão ("with a pair of Aces") é OPCIONAL: a GGPoker às vezes escreve
            # só "showed [2s] and won (46,800)", sem o "with ...", quando os demais já foldaram
            # e não há mão adversária pra comparar. Sem o "?", essa linha nunca casava e a
            # conclusão da mão ficava tão ausente quanto o bug original da ACR.
            m = _re.match(r'Seat (\d+): (.+?) (?:\(.*?\) )?showed \[([^\]]+)\] and won ' + _AMT + r'(?: with (.+))?', line)
            if m:
                result['seats'].append({'seat':int(m.group(1)),'player':m.group(2).strip(),
                    'cards':m.group(3).split(),'won':int(float(m.group(4).replace(',', ''))),
                    'hand_desc':(m.group(5) or '').strip(),'outcome':'won'}); continue
            # Perdedor revelado (chamou e perdeu no showdown). Sem este caso as cartas do
            # vilão perdedor nunca chegavam ao replay em NENHUM site — só o vencedor entrava.
            m = _re.match(r'Seat (\d+): (.+?) (?:\(.*?\) )?showed \[([^\]]+)\] and lost(?: with (.+))?', line)
            if m:
                result['seats'].append({'seat':int(m.group(1)),'player':m.group(2).strip(),
                    'cards':m.group(3).split(),'won':0,
                    'hand_desc':(m.group(4) or '').strip(),'outcome':'lost'}); continue
            m = _re.match(r'Seat (\d+): (.+?) (?:\(.*?\) )?mucked \[([^\]]+)\]', line)
            if m:
                result['seats'].append({'seat':int(m.group(1)),'player':m.group(2).strip(),
                    'cards':m.group(3).split(),'won':0,
                    'hand_desc':'mucked','outcome':'lost'}); continue
            m = _re.match(r'Seat (\d+): (.+?) (?:\(.*?\) )?collected ' + _AMT, line)
            if m:
                result['seats'].append({'seat':int(m.group(1)),'player':m.group(2).strip(),
                    'cards':[],'won':int(float(m.group(3).replace(',', ''))),
                    'hand_desc':'collected','outcome':'won'}); continue
            # ACR: ganhou sem disputa (todo mundo foldou) — "did not show and won X.XX".
            m = _re.match(r'Seat (\d+): (.+?) (?:\(.*?\) )?did not show and won ' + _AMT, line)
            if m:
                result['seats'].append({'seat':int(m.group(1)),'player':m.group(2).strip(),
                    'cards':[],'won':int(float(m.group(3).replace(',', ''))),
                    'hand_desc':'did not show','outcome':'won'})
        result['winners'] = [s for s in result['seats'] if s['outcome']=='won']
        return result

    hero = hero_override or hand.hero

    # Extrair seats, stacks e bounties — pela FONTE ÚNICA de leitura de assento.
    #
    # Este bloco tinha o QUARTO regex próprio de assento, inline (`_re.match`, invisível à
    # varredura de `re.compile`), exigindo o ")" logo após o número: nas mãos PKO
    # ("(12255 in chips, $15 bounty)") ele não achava assento NENHUM e o replay inteiro devolvia
    # {'error': 'Seats não encontrados'} — onze torneios sem replay em produção, descobertos ao
    # investigar por que 9 linhas da sonda ODDS não rendiam card. O corte do SUMMARY (linhas
    # "Seat N: ... won (1,110)" corrompiam o roster) mora na fonte única; o filtro de assento
    # "out of hand" fica AQUI porque é regra do replay, não da leitura.
    seats = {}
    _bounties = getattr(hand, 'bounties', {}) or {}
    from leaklab.mesa_final import assentos_numerados
    for _num, player, _fichas, _linha in assentos_numerados(hand.raw_text):
        # Assento "out of hand" (movido de outra mesa, joga só após o botão) não
        # está nesta mão: incluí-lo na mesa inflava a contagem (HU virava "multiway"
        # no fallback seats−folded do card) e deslocava as posições do replay.
        if SEAT_OUT_OF_HAND_RE.search(_linha):
            continue
        seat_d = {'player': player, 'stack': int(_fichas)}
        if player in _bounties:
            seat_d['bounty'] = _bounties[player]
        seats[_num] = seat_d
    if not seats:
        return {'error': 'Seats não encontrados'}

    # Detectar eventos de knockout na mão (PokerStars/GGPoker)
    _KO_RE = _re.compile(r'^(.+?) wins \$([0-9.]+) bounty for eliminating (.+)', _re.IGNORECASE)
    knockout_events = []
    for line in hand.raw_text.split('\n'):
        mk = _KO_RE.match(line.strip())
        if mk:
            knockout_events.append({
                'winner':    mk.group(1).strip(),
                'amount':    float(mk.group(2)),
                'eliminated': mk.group(3).strip(),
            })

    seat_nums = sorted(seats.keys())
    n         = len(seat_nums)
    btn_idx   = seat_nums.index(hand.button_seat) if hand.button_seat in seat_nums else 0
    # Posição autoritativa: delegada a `leaklab.posicoes` — ver o comentário abaixo.
    # ordena CLOCKWISE a partir do SB (assento depois do button) e nomeia por índice.
    # A antiga tabela "forward" (BTN,SB,BB,UTG,UTG+1,...) só batia em 9-max e rotulava
    # errado o miolo das mesas menores (6-max dava UTG+1/UTG+2 em vez de HJ/CO).
    # 'LJ' (não 'MP1') p/ casar com o Decision Card / GTO Solver.
    ordered = [seat_nums[(btn_idx + 1 + k) % n] for k in range(n)]  # [SB, BB, ..., BTN]
    # FONTE UNICA (leaklab.posicoes). Esta era uma COPIA, e o comentario acima afirmava ser "a
    # mesma derivacao do builder" sem ser: faltava o caso de HEADS-UP. Com n=2 o dict
    # {0:'SB', 1:'BB', n-1:'BTN'} tinha n-1 == 1, entao 'BTN' sobrescrevia 'BB' e o rotulo da big
    # blind DESAPARECIA — enquanto o SB aparecia sobre o jogador errado. Reportado pelo usuario
    # como "as blinds nao estao sendo exibidas".
    from leaklab.posicoes import nomes_de_posicao
    _pn = nomes_de_posicao(n, miolo='LJ')
    positions = {ordered[k]: _pn[k] for k in range(n)}

    # Mapear erros por (street, action_taken) — inclui dados matemáticos do engine
    # Normalizar: banco usa 'fold','call','raise'; parser usa 'folds','calls','raises'
    def _norm(a):
        if not a:
            return ''
        a = a.rstrip('s') if a.endswith('s') else a
        return 'allin' if a in ('all-in', 'allin', 'jam', 'shove') else a

    # Decisões do hero por (street, action). NÃO é um dict: a chave se repete quando o hero
    # age duas vezes na mesma street, e `all_decisions[key] = d` fazia a segunda APAGAR a
    # primeira — os dois passos da mesa acabavam mostrando o mesmo card. Cada balde é
    # consumido em ordem. Ver leaklab/pareamento_decisoes.py.
    _chave_dec = lambda d: (d.get('street', ''), _norm(d.get('action_taken', '')))
    _decisoes_por_chave = BaldeDeDecisoes(decisions_db, _chave_dec)

    # Re-rodar o engine para enriquecer TODAS as decisões hero com dados matemáticos
    # e análise de range preflop GTO
    try:
        from leaklab.pipeline import build_decision_inputs_for_hand
        from leaklab.decision_engine_v11 import evaluate_decision
        from leaklab.gto_utils import hand_to_type
        engine_inputs = build_decision_inputs_for_hand(hand)
        _balde_enriq = BaldeDeDecisoes(decisions_db, _chave_dec)
        for di in engine_inputs:
            r   = evaluate_decision(di)
            key = (di['street'], _norm(r.get('actionTaken', '')))
            _alvo = _balde_enriq.proxima(key)
            if _alvo is not None:
                _alvo['context']   = di.get('context', {})
                _alvo['math']      = di.get('math', {})
                _alvo['breakdown'] = r['evaluation'].get('scoreBreakdown', {})
                _alvo['_di']       = di  # spot params for GTO strategy lookup
                # Análise de range preflop — só para preflop hero actions
                if di['street'] == 'preflop':
                    try:
                        spot     = di.get('spot', {})
                        ctx      = di.get('context', {})
                        h_cards  = di.get('hero_cards', [])
                        h_type   = hand_to_type(h_cards) if h_cards else None
                        if h_type:
                            _pf_facing_chips = float(spot.get('facingSize') or 0)
                            _pf_level_bb     = float(ctx.get('levelBb') or 0)
                            # Convert chips to BB; facingSize from parser is in chips
                            _pf_facing_bb = (round(_pf_facing_chips / _pf_level_bb, 2)
                                             if _pf_facing_chips > 0 and _pf_level_bb > 0
                                             else _pf_facing_chips)
                            _pf_stack_bb     = float(spot.get('effectiveStackBb') or ctx.get('heroStackBb') or 20)
                            _pf_pos          = spot.get('position', '')
                            # Detectar 3-bet pot pelo HISTÓRICO da hand: se já houve >= 2
                            # raises preflop antes da ação do hero, é 3-bet pot (independente
                            # de hero ser o 3-bettor ou estar enfrentando).
                            _pf_n_raises_before = 0
                            _hand_obj = hand  # ParsedHand do escopo de _build_replay_data
                            try:
                                _act_canon = (di.get('player_action', '') or '').lower().rstrip('s')
                                _hero_seen = 0
                                # Conta quantas vezes essa player_action do hero já apareceu
                                # antes do DI atual (di_idx) — DIs preflop em ordem.
                                _hero_idx = -1
                                for _i, _a in enumerate(_hand_obj.actions or []):
                                    if (_a.street == 'preflop' and _a.player == _hand_obj.hero
                                            and (_a.action or '').lower().rstrip('s') == _act_canon):
                                        _hero_idx = _i; break
                                if _hero_idx >= 0:
                                    _pf_n_raises_before = sum(
                                        1 for _a in (_hand_obj.actions or [])[:_hero_idx]
                                        if _a.street == 'preflop' and (_a.action or '') in ('raises','all-in','raise','allin')
                                    )
                            except Exception:
                                pass
                            # `is_3bet_pot` significa "hero FEZ o 3-bet", NAO "o pote e de 3-bet"
                            # — esta escrito no proprio `analyze_preflop`. A formula antiga ligava a
                            # flag quando havia >=2 raises ANTES do hero, que e exatamente o caso
                            # OPOSTO (hero ENFRENTA um 3-bet). Com ela, o cenario virava
                            # squeeze/vs_4bet em vez de vs_3bet e o veredito saia `fold`.
                            #
                            # Reportado por um aluno: card dizendo "Call lucrativo: equity 64%
                            # supera pot odds 21%" e, no mesmo quadro, "ERRO" e "CALL -EV". O
                            # backend gravou `standard`; quem inventou o erro foi este lookup.
                            #
                            # "Quantos raises vieram antes" ja viaja em `facing_raises`, logo
                            # abaixo — este parametro nunca foi o lugar dele. Agora usa a MESMA
                            # fonte do motor (`decision_engine_v11` linha ~248).
                            _pf_is_3bet_pot = bool(di.get('is_3bet', False))
                            # Porta única de estratégia preflop (mesma do trainer/engine/replay-verdict).
                            # `raw` = dict cru do analyze_preflop (dialeto de armazenamento) → o
                            # frontend consome preflop_gto como antes, sem mudança de contrato.
                            from leaklab.strategy_provider import (preflop_strategy as _pfs_a,
                                preflop_call_vs_shove_fallback as _pf_shove_fb,
                                preflop_open_range_proxy as _pf_open_proxy)
                            _pf_result = _pfs_a(
                                # PKO muda a CARTA consultada. Sem este argumento o card
                                # lia a Classic enquanto o veredito gravado vinha da PKO.
                                is_pko         = bool((di.get('context') or {}).get('isPko')),
                                position       = _pf_pos,
                                hero_hand_type = h_type,
                                stack_bb       = _pf_stack_bb,
                                action_taken   = di.get('player_action', ''),
                                facing_size    = _pf_facing_bb,
                                vs_position    = spot.get('villainPosition', ''),
                                is_3bet_pot    = _pf_is_3bet_pot,
                                n_players      = spot.get('nPlayers'),
                                # Sem estes dois, faces_squeeze (cold/blind enfrenta open+3bet/
                                # squeeze) cai em vs_rfi e sugere call largo (bug "call 54s vs
                                # squeeze"). Alinha o display ao veredito armazenado.
                                facing_raises      = int(spot.get('preflopRaisesFaced') or 0),
                                hero_was_aggressor = bool(spot.get('heroWasAggressor')),
                                facing_limp        = bool(spot.get('facingLimp')),
                                caller_position    = spot.get('callerPosition', ''),
                                # #23: open enfrentado em bb (raise-to total) — pro card
                                # rebaixar fold de defesa marginal vs open off-tree.
                                facing_to_bb       = float(spot.get('facingToBb') or 0),
                                facing_allin       = bool(spot.get('facingAllin', False)),
                                hero_raise_to_bb   = spot.get('heroRaiseToBb'),
                            )['raw']
                            # Fallbacks preflop honestos (sem cobertura de árvore) — fonte única no
                            # strategy_provider (antes construídos INLINE aqui, em cópia do lado do
                            # veredito). O gatilho fica aqui; a construção do dict, no provider.
                            _uncov_act = di.get('player_action', '')
                            # (1) call-vs-shove: sem dados vs_shove, proxy pela pertinência ao open (RFI)
                            if (not _pf_result.get('available')
                                    and _uncov_act in ('call', 'allin')
                                    and _pf_facing_bb >= _pf_stack_bb * 0.40):
                                _fb = _pf_shove_fb(_pf_pos, h_type, _pf_stack_bb, action_taken='call')
                                if _fb:
                                    _pf_result = _fb
                            # (2) open-range proxy: spot sem cobertura (ex.: vs limp multiway) — só as
                            # 2 pontas claras (fold fora do open / iso dentro do open); resto = ambíguo.
                            if (not _pf_result.get('available')
                                    and _uncov_act in ('fold', 'raise')):
                                _op = _pf_open_proxy(_pf_pos, h_type, _pf_stack_bb, action_taken=_uncov_act)
                                if _op:
                                    _pf_result = _op
                            _alvo['preflop_gto'] = _pf_result
                    except Exception:
                        pass
    except Exception:
        pass  # fallback gracioso — continua sem dados extras

    bb     = hand.bb or 100
    stacks = {s: seats[s]['stack'] for s in seats}
    pot    = 0
    bets_r = {s: 0 for s in seats}   # apostas visíveis como fichas na rodada
    board  = []
    street = 'preflop'
    folded = []

    # Pre-scan raw_text for mid-hand "shows [cards]" so we can reveal cards
    # as soon as the action occurs (e.g. all-in before river runout)
    SHOWS_RE = _re.compile(r'^(.+): shows \[([^\]]+)\]', _re.MULTILINE)
    shows_map = {}  # player -> [card, ...]
    for _m in SHOWS_RE.finditer(hand.raw_text or ''):
        _player = _m.group(1).strip()
        if _player not in shows_map:
            shows_map[_player] = _m.group(2).split()

    # Pre-scan for "Uncalled bet (X) returned to Player" lines
    # These appear after all actions when an all-in isn't fully called
    # GG usa separador de milhar (5,000); aceita vírgula e remove antes de converter.
    UNCALLED_RE = _re.compile(r'Uncalled bet \(([\d,]+(?:\.\d+)?)\) returned to (.+)')
    uncalled_returns = []
    for line in (hand.raw_text or '').split('\n'):
        _mu = UNCALLED_RE.match(line.strip())
        if _mu:
            uncalled_returns.append({'amount': int(float(_mu.group(1).replace(',', ''))), 'player': _mu.group(2).strip()})

    current_revealed = {}  # seat_str -> [cards], accumulates as shows happen

    # Extrair antes e blinds do raw_text (parser não os captura em hand.actions)
    #
    # Reportado pelo usuário: "eu estou no BB e não apareceu; a SB só apareceu depois que o D
    # pagou". Medido numa mão 3-handed da ACR: o frame inicial vinha com pot=0, blinds_total=0 e
    # ZERO fichas em todos os assentos — nenhum ante e nenhum blind era capturado. As fichas que
    # apareciam na mesa eram só as das AÇÕES, então o pote parecia nascer do nada quando alguém
    # agia, e o blind do hero nunca era desenhado.
    #
    # Duas incompatibilidades com o dialeto ACR, ambas neste regex:
    #   · DOIS-PONTOS: PokerStars/GG escrevem "Hero: posts the ante 40"; a ACR escreve
    #     "Hero posts ante 40.00", sem ":" (é a diferença central do dialeto, já documentada no
    #     parser). `(.+): posts` nunca casava.
    #   · "the" OPCIONAL no ante: a ACR usa "posts ante", sem o artigo.
    # Os decimais (`.00`) também: `[\d,]+` parava antes do ponto e, num valor como "0.50", leria
    # zero. Agora o grupo aceita a parte decimal e a conversão passa por float.
    antes   = []
    blinds  = []
    _ANTE_ANY  = _re.compile(r'^(.+?):? posts (?:the )?ante ([\d,]+(?:\.\d+)?)')
    _BLIND_ANY = _re.compile(r'^(.+?):? posts (?:the )?(small|big) blind ([\d,]+(?:\.\d+)?)')
    for line in hand.raw_text.split('\n'):
        line = line.strip()
        m_ante  = _ANTE_ANY.match(line)
        m_blind = _BLIND_ANY.match(line)
        if m_ante:
            antes.append({'player': m_ante.group(1).strip(),
                          'amount': int(float(m_ante.group(2).replace(',', '')))})
        elif m_blind:
            blinds.append({'player': m_blind.group(1).strip(),
                           'type':   m_blind.group(2),
                           'amount': int(float(m_blind.group(3).replace(',', '')))})

    # Aplicar antes ao pot (sem ficha individual)
    for a in antes:
        pot += a['amount']
        pseat = next((s for s,d in seats.items() if d['player']==a['player']), None)
        if pseat:
            stacks[pseat] = max(0, stacks[pseat] - a['amount'])

    # Aplicar blinds ao pot E às fichas visíveis
    for b in blinds:
        pot += b['amount']
        pseat = next((s for s,d in seats.items() if d['player']==b['player']), None)
        if pseat:
            stacks[pseat]  = max(0, stacks[pseat] - b['amount'])
            bets_r[pseat]  = bets_r.get(pseat, 0) + b['amount']

    def snap(extra=None):
        base = {
            'seats':  {s: {'player': seats[s]['player'], 'stack': stacks[s],
                           'stack_bb': round(stacks[s] / bb, 1), 'pos': positions[s],
                           'bounty': seats[s].get('bounty')}   # PKO: 🎯 no replayer (snap dropava o campo)
                       for s in seats},
            'button':     hand.button_seat,
            'hero':       hero,
            'hero_cards': [hand.hero_cards[:2], hand.hero_cards[2:]]
                           if len(hand.hero_cards or '') >= 4 else [],
            'board':  board[:],
            'pot':    pot,
            'pot_bb': round(pot / bb, 1),
            'bets':   dict(bets_r),
            'street': street,
            'folded': folded[:],
            'bb':     bb,
        }
        if extra: base.update(extra)
        return base

    # Resumo dos antes para exibição
    antes_total = sum(a['amount'] for a in antes)
    antes_desc  = ''
    if antes:
        n_antes = len(antes)
        val     = antes[0]['amount']
        antes_desc = f'{n_antes}×{val} ante = {antes_total}'

    timeline = [snap({
        'type':       'deal',
        'desc':       'Início da mão',
        'antes_total': antes_total,
        'antes_desc':  antes_desc,
        'blinds_total': sum(b['amount'] for b in blinds),
    })]

    for action in hand.actions:
        if action.street != street:
            street = action.street
            bets_r = {s: 0 for s in seats}
            if street == 'flop':   board = hand.board[:3]
            elif street == 'turn':  board = hand.board[:4]
            elif street == 'river': board = hand.board[:]
            timeline.append(snap({'type': 'street', 'desc': street.upper(),
                                  'revealed_cards': dict(current_revealed) if current_revealed else None}))

        pseat = next((s for s, d in seats.items() if d['player'] == action.player), None)
        amt   = action.amount or 0
        # Total do "raises X to Y" via parser (fonte única, tolerante a separador de milhar).
        # O regex inline antigo (`raises \d+ to (\d+)`) parava na vírgula e devolvia 1 ficha em
        # "raises 798 to 1,098" (CoinPoker/GG) → RAISE aparecia como 0 BB na mesa. Ver parser.
        total_raise = (_raise_total_from_raw(action.raw)
                       if action.action in ('raises', 'all-in') else None)

        if action.action in ('calls', 'bets', 'raises', 'all-in') and (amt or total_raise):
            # Para raises: "raises X to Y" — X é o incremento, Y é o total colocado
            # O total que entra no pot é Y (não X), menos o que o jogador já tinha apostado
            # Para all-in: parser converte "bets/raises ... and is all-in" para 'all-in';
            #   se veio de raise ("raises X to Y"), Y é o total; se de bet, amt é o total.
            if action.action == 'raises':
                total_placed = total_raise if total_raise is not None else amt
                already_in   = bets_r.get(pseat, 0)
                real_addition = total_placed - already_in
                pot += real_addition
                if pseat:
                    stacks[pseat]  = max(0, stacks[pseat] - real_addition)
                    bets_r[pseat]  = total_placed
            elif action.action == 'all-in':
                if total_raise is not None:
                    # raise all-in: "raises X to Y and is all-in" — Y é o total colocado
                    total_placed  = total_raise
                    already_in    = bets_r.get(pseat, 0)
                    real_addition = total_placed - already_in
                else:
                    # bet all-in: "bets X and is all-in" — amt é o total
                    real_addition = amt
                    total_placed  = bets_r.get(pseat, 0) + amt
                pot += real_addition
                if pseat:
                    stacks[pseat]  = max(0, stacks[pseat] - real_addition)
                    bets_r[pseat]  = total_placed
            else:
                pot += amt
                if pseat:
                    stacks[pseat] = max(0, stacks[pseat] - amt)
                    bets_r[pseat] = bets_r.get(pseat, 0) + amt


        if action.action == 'folds' and action.player not in folded:
            folded.append(action.player)

        # Acumular cartas reveladas de "shows" mid-hand (all-in antes do runout, etc.)
        if action.action == 'shows' and pseat is not None:
            if action.player in shows_map:
                current_revealed[str(pseat)] = shows_map[action.player]

        # Consome o balde EM ORDEM: a 1ª ação do hero com essa chave leva a 1ª decisão, a 2ª
        # leva a 2ª. Com `dict.get` as duas levavam a mesma, e o segundo passo da mesa exibia
        # o veredito do primeiro — inclusive o selo SOLVER de uma decisão sem solver.
        err_key  = (action.street, _norm(action.action))
        decision = (_decisoes_por_chave.proxima(err_key)
                    if action.player == hero else None)

        # Dados técnicos para QUALQUER ação do hero (não só erros)
        tech = {}
        if decision:
            ctx  = decision.get('context', {})
            math = decision.get('math', {})
            thr  = decision.get('thresholds', {})
            bd   = decision.get('breakdown', {})
            tech = {
                'pot_odds_equity': math.get('potOddsEquity'),
                'adjusted_required_equity': thr.get('adjustedRequiredEquity'),
                'hand_equity':     math.get('estimatedHandEquity'),
                'equity_source':   math.get('equitySource', 'vs_random'),  # #27: vs_range | vs_random
                # Leitura de range por iniciativa (12/08): quem tinha a iniciativa quando a
                # street comecou. O front deriva 'c-bet' vs 'donk/check-raise' cruzando com o
                # facing — derivacao PURA em replayWhy, testada la.
                'street_initiative': (decision.get('_di') or {}).get('spot', {}).get('iniciativaDaStreet'),
                'draw_profile':    math.get('drawProfile', 'none'),
                'm_ratio':         ctx.get('mRatio'),
                'icm_pressure':    ctx.get('icmPressure'),
                'icm_tax_pct':     ctx.get('icmTaxPct'),   # mesa final: chip% − equity ICM% (None fora dela)
                'hero_stack_bb':   ctx.get('heroStackBb') or float((decision.get('_di') or {}).get('spot', {}).get('effectiveStackBb') or 0) or None,
                'math_penalty':    bd.get('mathPenalty', 0),
                'range_penalty':   bd.get('rangePenalty', 0),
                'context_penalty': bd.get('contextPenalty', 0),
            }

        # GTO reconciliation — solver é fonte autoritativa quando disponível
        gto_label   = decision.get('gto_label')  if decision else None
        gto_action  = decision.get('gto_action') if decision else None
        gto_depth_capped = bool(decision.get('gto_depth_capped')) if decision else False  # opção B: aprox >60bb
        engine_best = decision.get('best_action') if decision else None

        # CAMADA 1 (leaklab/card_verdict, puro e testado): veredito pelo label ARMAZENADO.
        # `_norm` local é de propósito — ver a nota sobre normalização em card_verdict.
        from leaklab.card_verdict import (
            spot_mismatch as _spot_mismatch, verdict_from_stored as _v_stored, VerdictChain,
        )
        gto_spot_mismatch = _spot_mismatch(_norm(gto_action), _norm(engine_best))
        # A cadeia carrega o veredito pelas 4 camadas e registra qual delas decidiu. A ordem é
        # declarada em card_verdict.LAYERS — aplicar fora dela levanta erro.
        _vc = VerdictChain(gto_label=gto_label, gto_action=gto_action, live_top_act=None)
        _vc.apply('stored', _v_stored(
            gto_label, gto_action, engine_best,
            decision.get('label', 'standard') if decision is not None else None,
            _norm(action.action), gto_spot_mismatch,
        ))
        is_error        = _vc['is_error']
        reconciled_best = _vc['reconciled_best']

        # Detectar conflito engine vs GTO (quando não há mismatch de spot)
        gto_engine_conflict = (
            not gto_spot_mismatch
            and gto_label is not None
            and engine_best is not None
            and _norm(engine_best) != _norm(reconciled_best or '')
        )

        # Extrai contexto da decisao (compartilhado entre lookup_gto e multiway)
        _di   = (decision or {}).get('_di', {}) if decision else {}
        _spot = _di.get('spot', {})
        _ctx  = _di.get('context', {})

        # Fetch full GTO strategy for display (all actions with freq + combos).
        # Também tenta quando NÃO há gto_label armazenado mas é decisão postflop do
        # hero: o nó pode ter nascido depois do import (re-solve / fix de board), e
        # sem isto o card ficava preso em "processando" pra sempre (o stored label
        # nunca era atualizado). Nesse caso usa lookup SÓ LOCAL (block_remote=True)
        # pra não disparar um solve remoto lento dentro do /replay.
        gto_strategy = None
        live_hand_strategy = None   # Fase 3: estratégia da mão específica (card)
        _lk_approx_stack = None     # MVP deep: nó capado a Xbb usado (spot fundo) → "≈ aproximação"
        _hero_postflop = (action.player == hero and action.street != 'preflop')
        if decision and not gto_spot_mismatch and (gto_label or _hero_postflop):
            try:
                from leaklab.gto_solver import lookup_gto as _lookup_gto
                _gto_result = _lookup_gto(
                    street         = action.street,
                    position       = _spot.get('position', _ctx.get('position', '')),
                    board          = _spot.get('board', []),
                    hero_hand      = _di.get('hero_cards', []),
                    hero_stack_bb  = float(_spot.get('effectiveStackBb', _ctx.get('heroStackBb', 20.0)) or 20.0),
                    action_seq     = _ctx.get('actionSeq', 'rfi'),
                    vs_position    = _spot.get('villainPosition', _ctx.get('vsPosition', '')),
                    # facing REAL do spot (facingToBb, em BB) — NÃO decision.get('facing_bet'),
                    # que vem do nó já casado (=0 no nó de aposta) e fazia o lookup devolver o
                    # nó de PRIMEIRA AÇÃO (bet/check) num spot que ENFRENTA aposta (call/fold/
                    # raise). Mesmo facing que o engine usa (decision_engine: facingToBb).
                    facing_size_bb = float(_spot.get('facingToBb') or 0),
                    pot_bb         = float(_spot.get('potBb', 0) or 0),     # BB, não fichas (potSize)
                    # READ-ONLY: block_remote=False faz o lookup_gto dar short-circuit (sem
                    # GW nem Texas) quando NÃO há nó local. O `(not gto_label)` antigo passava
                    # block_remote=True em spot não-coberto → caía na query GW (timeout 20s,
                    # GW 'degraded') → /replay travava 20–80s. Coberto retorna o nó cacheado antes.
                    block_remote   = False,
                    allow_remote_solve = False,   # defensivo: nunca solva na requisição
                    pot_type       = _spot.get('potType', ''),            # Fase 2: pote 3-bet
                    opener         = _spot.get('preflopOpener', ''),
                    threebettor    = _spot.get('preflop3bettor', ''),
                )
                if _gto_result.get('found') and _gto_result.get('strategy'):
                    gto_strategy = _gto_result['strategy']
                    _lk_approx_stack = _gto_result.get('approx_stack')   # nó capado deep (≈ aproximação)
                    # Fase 3 (item 4): visão da MÃO p/ o card ("Sua mão: check 100%")
                    _hv = _gto_result.get('hand_strategy')
                    if _hv and _hv.get('actions'):
                        _hc = _di.get('hero_cards') or []
                        live_hand_strategy = {
                            'hand': ''.join(_hc) if len(_hc) == 2 else '',
                            'actions': [
                                {'action': a, 'frequency': v.get('frequency'),
                                 'ev_bb': v.get('ev_bb'),
                                 'ev_loss_bb': v.get('ev_loss_bb')}
                                for a, v in _hv['actions'].items()
                            ],
                        }
            except Exception:
                pass

        # Fallback multiway: quando lookup_gto local nao tem cobertura (spot fora
        # do escopo HU — multiway / squeeze / cold-callers), tenta GTO Wizard via
        # /gw-spot. So pra preflop e decisao do hero.
        #
        # IMPORTANTE: nao bloqueia /replay no cache miss (cada GW call leva ~30s).
        # Estrategia: tenta cache local primeiro (12ms). Se HIT, usa. Se MISS,
        # dispara background task pra popular o cache pra proxima visita e segue
        # sem GTO multiway no response atual.
        if (gto_strategy is None
                and action.street == 'preflop'
                and action.player == hero
                and not gto_spot_mismatch):
            try:
                from leaklab.gto_wizard_client import (
                    lookup_for_hand_decision as _lookup_mw,
                    _enabled as _gw_enabled,
                )
                if _gw_enabled():
                    _act_idx = hand.actions.index(action)
                    _stack_bb = float(_spot.get('effectiveStackBb')
                                      or _ctx.get('heroStackBb') or 100.0)
                    # 1. Cache-only lookup (12ms; nao chama GW)
                    _mw = _lookup_mw(hand, _act_idx, depth_bb=_stack_bb,
                                     use_cache=True, cache_only=True)
                    if _mw is None:
                        # Cache miss — dispara warmup em background pra proxima visita
                        import threading
                        def _warmup_gw(h=hand, idx=_act_idx, sb=_stack_bb):
                            try:
                                _lookup_mw(h, idx, depth_bb=sb, timeout=120, use_cache=True)
                            except Exception:
                                pass
                        threading.Thread(target=_warmup_gw, daemon=True).start()
                    elif _mw.get('strategy'):
                        gto_strategy = _mw['strategy']
                        # Expose hero-specific hand_freqs no payload — Decision Card
                        # usa pra mostrar frequencia da mao especifica do hero.
                        _hero_cards = _di.get('hero_cards') or []
                        _hand_type  = None
                        if _hero_cards and len(_hero_cards) == 2:
                            try:
                                from leaklab.gto_utils import hand_to_type
                                _hand_type = hand_to_type(_hero_cards)
                            except Exception:
                                pass
                        if _hand_type:
                            _hf = (_mw.get('hand_freqs') or {}).get(_hand_type)
                            if _hf:
                                for _gs in gto_strategy:
                                    _gs['hero_freq'] = _hf.get(_gs.get('action'), 0.0)
            except Exception:
                pass

        # Re-evaluate is_error/reconciled_best using LIVE strategy (overrides stored gto_label)
        # Stored label may come from a mismatched or stale node; live frequency is ground truth.
        _pf_vivo = None      # a carta preflop que a CAMADA VIVA consultou (pode existir onde o
                             # motor nao teve nenhuma) -- ver o uso em `best_action`
        live_top_act = None
        # Veredito do hero vem da estratégia da MÃO específica (postflop solved node),
        # não do range agregado. Ex.: o range folda 63%, mas A2s levanta 93% → a
        # recomendação para ESTA mão é raise e o call é desvio de raise (não de fold).
        # Sem isto, live_top_act pegava a ação modal do range (fold) e persistia
        # gto_action=fold por cima do gto_action=raise correto.
        _recon_strat = (
            live_hand_strategy['actions']
            if live_hand_strategy and live_hand_strategy.get('actions')
            else gto_strategy
        )
        if _recon_strat and not gto_spot_mismatch:
            from leaklab.card_verdict import reconcile_verdict as _reconcile
            acted_norm = _norm(action.action)
            # Reconciliação PURA (leaklab/card_verdict, testada): a estratégia da MÃO
            # tem prioridade sobre o range agregado. Sem isto a recomendação pegava a
            # ação modal do range (ex.: fold 63%) em vez da da mão (raise 93%).
            # Colapso shove≡call ANTES da comparacao viva: no spot em que o call ja poe
            # todo mundo all-in, a estrategia do no (call/fold) nao tem 'allin' e comparar a
            # acao crua re-acusa o que o motor ja absolveu (regressao vista em 12/08).
            from leaklab.card_verdict import colapsa_shove_para_call as _colapsa_sc
            _played_live = 'call' if _colapsa_sc(_spot, action.action) else action.action
            _v = _reconcile(
                gto_strategy,
                (live_hand_strategy or {}).get('actions'),
                _played_live,
                gto_action,
            )
            if _v:
                is_error, reconciled_best, gto_label, gto_action, live_top_act = \
                    _vc.apply('live', _v).unpack()
                # (Havia aqui um bloco que dizia persistir o veredito do solver. Ele nunca
                #  executou: referenciava `_db_hand`, que é local de `get_replay` e não existe
                #  neste escopo, e o `except: pass` engolia o NameError. Removido — ver a nota
                #  sobre /replay ser somente-leitura no topo desta função.)

        # Preflop override: aggregate nodes give misleading fold recommendation for in-range hands.
        # Use analyze_preflop with the specific hero hand to get the correct recommendation.
        # This overrides both gto_action (stale DB value) and live_top_act (from aggregate node).
        preflop_override_action = None
        if action.street == 'preflop' and action.player == hero and decision:
            _di_pf  = decision.get('_di') or {}
            _spot   = _di_pf.get('spot', {})
            _hc     = _di_pf.get('hero_cards', []) or []
            _pos    = _spot.get('position', '') or decision.get('position', '')
            _sb     = float(_spot.get('effectiveStackBb') or decision.get('stack_bb') or 20.0)
            _facing = float(decision.get('facing_bet') or 0.0)
            if not _facing:
                # facing_bet not available in live_decision for decisions without gto_label —
                # try spot.facingSize (in chips) and convert to BB using level_bb
                _facing_chips = float(_spot.get('facingSize') or 0)
                _level_bb = float((_di_pf.get('context') or {}).get('levelBb') or 0)
                if _facing_chips > 0 and _level_bb > 0:
                    _facing = round(_facing_chips / _level_bb, 2)
            if not _hc and isinstance(decision.get('hero_cards'), str):
                _raw_hc = decision['hero_cards'].strip()
                _hc = _raw_hc.split() if ' ' in _raw_hc else [_raw_hc[i:i+2] for i in range(0, len(_raw_hc), 2)]
            if _hc and _pos:
                try:
                    # Porta única de estratégia preflop (mesma do trainer/engine). `raw` = dict cru
                    # (dialeto de armazenamento) — o resto da reconciliação segue sem mudança. O
                    # fallback call-vs-shove também vem do provider (era construído inline aqui).
                    from leaklab.strategy_provider import (preflop_strategy as _pfs,
                        preflop_call_vs_shove_fallback as _pf_shove_fb2)
                    from leaklab.gto_utils import hand_to_type as _h2t
                    _ht = _h2t(_hc)
                    if _ht:
                        _pf = _pfs(
                            is_pko         = bool((_di_pf.get('context') or {}).get('isPko')),
                            position       = _pos,
                            hero_hand_type = _ht,
                            stack_bb       = _sb,
                            action_taken   = _norm(action.action),
                            facing_size    = _facing,
                            vs_position    = (_spot.get('villainPosition') or _spot.get('vsPosition', '')),
                            is_3bet_pot    = bool(_spot.get('is3betPot') or _spot.get('isThreeBetPot')),
                            n_players      = _spot.get('nPlayers'),
                            facing_raises      = int(_spot.get('preflopRaisesFaced') or 0),
                            hero_was_aggressor = bool(_spot.get('heroWasAggressor')),
                            # ── A MESMA superfície do bloco de display (app.py:~6403) ────────────
                            # `_build_replay_data` chama a porta única DUAS vezes para a mesma
                            # decisão: lá para o card, aqui para o VEREDITO. Esta cópia ficou sem
                            # `facing_to_bb`, `facing_limp` e `caller_position`, e o card se
                            # contradizia sozinho: o bloco GTO dizia `acceptable` (open off-tree) e
                            # o selo dizia ERRO / `gto_critical` recomendando CALL. Trinta decisões
                            # no acervo local, todas folds, várias contra all-in — foldar 63s para
                            # 39,5bb levava carimbo de erro grave.
                            #
                            # É o defeito do commit 68347c0a vivo de novo: aquele conserto
                            # acrescentou `facing_allin` e esqueceu `facing_to_bb`. `facing_allin`
                            # só salva o 3-bet que é all-in de verdade; um 3-bet a 74% do stack
                            # rota para o nó errado.
                            facing_to_bb       = float(_spot.get('facingToBb') or 0) or _facing,
                            facing_limp        = bool(_spot.get('facingLimp')),
                            caller_position    = _spot.get('callerPosition', '') or '',
                            facing_allin       = bool(_spot.get('facingAllin', False)),
                            hero_raise_to_bb   = _spot.get('heroRaiseToBb'),
                        )['raw']
                        # Fallback call-vs-shove: sem dados vs_shove, proxy pela pertinência ao open
                        # (RFI). Fonte única no provider (antes construído inline aqui). Gatilho aqui.
                        if not _pf.get('available') and _norm(action.action) == 'call' and _facing >= _sb * 0.40:
                            _fb = _pf_shove_fb2(_pos, _ht, _sb, action_taken=_norm(action.action))
                            if _fb:
                                _pf = _fb

                        if _pf.get('available'):
                            _pf_vivo = _pf          # a carta que o /replay realmente consultou
                        # O call que ja leva o stack inteiro E o jam da carta. O conserto no
                        # MOTOR nao alcanca aqui: o /replay reconsulta a carta por conta propria,
                        # e depois do regrade a LISTA ja dizia `call`/`gto_correct` enquanto o
                        # CARD seguia com "Correto" ao lado de "recomendado: jam". Mesma funcao
                        # pura do motor, chamada tambem aqui — regra 5.
                        from leaklab.card_verdict import (
                            carta_colapsada_por_commit_total as _colapsa_carta_viva)
                        _q_viva, _rec_viva, _custo_viva = _colapsa_carta_viva(
                            _pf.get('action_quality', 'unknown'),
                            _pf.get('recommended_actions'), _spot, _norm(action.action))
                        if not _custo_viva:      # so e False quando colapsou
                            _pf = {**_pf, 'action_quality': _q_viva,
                                   'recommended_actions': _rec_viva}
                            _pf_vivo = _pf
                        if _pf.get('available') and _pf.get('recommended_actions'):
                            preflop_override_action = _pf['recommended_actions'][0]
                            # CAMADA 3 (card_verdict, puro): qualidade desconhecida devolve None
                            # e a camada anterior fica de pé.
                            from leaklab.card_verdict import verdict_from_preflop as _v_pf
                            is_error, reconciled_best, gto_label, gto_action, live_top_act = \
                                _vc.apply('preflop', _v_pf(
                                    _pf.get('action_quality', 'unknown'),
                                    preflop_override_action, _norm(action.action))).unpack()
                            # (Bloco de persistência do preflop removido pelo mesmo motivo do
                            #  postflop: `_db_hand` não existe neste escopo e o NameError era
                            #  engolido. Nunca gravou nada.)
                except Exception:
                    pass

        # Por que (não) há cobertura GTO neste step postflop do hero — sinal honesto
        # pro card mostrar a razão CERTA em vez de "Processando" eterno em spots que
        # o solver heads-up nunca cobre (multiway, deep>60bb, hero IP enfrentando
        # aposta, sem vilão). 'pending' = solvável, nó ainda não existe.
        gto_coverage = None
        # Motivo declarado pela CARTA no preflop (`limped_pot`, `pairing_uncovered`, ...). Ele ja
        # existia dentro de `analyze_preflop` e morria no caminho: o payload so entregava coverage
        # para postflop.
        # calculado UMA vez e reusado: o mesmo motivo alimenta `ev_loss_motivo` e o guarda de
        # custo, senao voltam a ser duas portas para o mesmo fato
        try:
            _motivo_do_custo = _ev_e_motivo(decision, _di, _spot)[1]
        except Exception:                                                 # noqa: BLE001
            _motivo_do_custo = None
        _pf_cobertura = None
        try:
            _pf_cobertura = ((_di.get('preflop_gto') or {}) or {}).get('coverage_reason')
        except Exception:                                                 # noqa: BLE001
            _pf_cobertura = None
        if action.player == hero and action.street != 'preflop' and action.action not in ('shows', 'mucks', 'posts'):
            if gto_label:
                gto_coverage = 'covered'
            else:
                _nopp = int(_spot.get('nActiveOpponents') or 1)
                _vsu  = (_spot.get('villainPosition') or '').upper()
                _stk  = float(_spot.get('effectiveStackBb') or 0)
                _fac  = float(_spot.get('facingSize') or 0)
                if _nopp > 1:
                    gto_coverage = 'multiway'
                elif not _vsu or _vsu == 'UNKNOWN':
                    gto_coverage = 'no_villain'
                elif _stk > 200:
                    gto_coverage = 'deep'           # >200bb: nem aproximação (Opção B vai até 200)
                else:
                    try:
                        from leaklab.gto_solver import _postflop_hero_is_ip
                        _ip = _postflop_hero_is_ip((_spot.get('position') or '').upper(), _vsu)
                    except Exception:
                        _ip = False
                    gto_coverage = 'ip_facing_bet' if (_ip and _fac > 0) else 'pending'

        # FALLBACK MULTIWAY: o solver é HU e em pote 3-way+ recomenda agressão que
        # multiway costuma ser erro (mão 5: A2c levanta 93% HU, mas 3-way é fold).
        # Substitui a recomendação HU por equity-vs-range (eval7) + pot odds + realização.
        # É ESTIMATIVA honesta (rotulada), tem prioridade sobre o nó HU neste spot.
        multiway_advice = None
        multiway_safe = None       # Fase 2: veredito GRADEADO da cauda segura (flag MULTIWAY_GRADE_SAFE_TAIL)
        multiway_safe_label = None
        _mw_spot = False        # spot multiway postflop do hero (solver HU é unreliable aqui)
        _mw_nopp = 0
        # `'all-in'` ESTAVA FALTANDO nesta lista, e o parser normaliza o shove exatamente assim
        # (`leaklab/parser.py`: `action_str = 'all-in'`). Sem ele o bloco inteiro era pulado nos
        # all-ins pos-flop: `_mw_spot` ficava False, `gto_label` nao era suprimido e
        # `pode_falar_como_gto` LIBERAVA. Medido no torneio 72 por um juiz de QA: 9 all-ins
        # postflop sem `n_active_opponents`, 5 deles multiway de verdade, 4 exibindo veredito de
        # solver heads-up COM autorizacao para falar como GTO. O all-in e justamente o spot em
        # que o conselho errado custa o torneio.
        _VERBOS_DE_DECISAO = ('bets', 'raises', 'calls', 'checks', 'folds', 'all-in',
                              'bet', 'raise', 'call', 'check', 'fold', 'shove')
        if (action.player == hero and action.street != 'preflop' and decision
                and action.action in _VERBOS_DE_DECISAO):
            _nopp_mw = int(_spot.get('nActiveOpponents') or 0)
            _mw_nopp = _nopp_mw
            if _nopp_mw >= 2:
                _mw_spot = True
                try:
                    from leaklab.multiway_advisor import advise_multiway as _amw
                    _hc_mw = ''.join(_di.get('hero_cards') or [])
                    multiway_advice = _amw(
                        _hc_mw,
                        _spot.get('board') or [],
                        float(_spot.get('potBb') or 0),
                        float(_spot.get('facingToBb') or 0),
                        _nopp_mw,
                        is_in_position=_spot.get('isInPosition'),
                        street=action.street,
                        eff_stack_bb=float(_spot.get('effectiveStackBb') or 0),
                    )
                except Exception:
                    multiway_advice = None
                # Só SOBREPÕE com ALTA confiança (is_clear). Decisão próxima → defere ao engine.
                if multiway_advice and not multiway_advice.get('is_clear'):
                    multiway_advice = None
            # CAMADA 4 (card_verdict, puro): multiway tem prioridade sobre o nó heads-up.
            from leaklab.card_verdict import (
                verdict_from_multiway_advice as _v_mw_adv,
                verdict_from_multiway_engine as _v_mw_eng,
            )
            if multiway_advice:
                from leaklab.multiway_advisor import is_hero_leak as _mw_leak
                is_error, reconciled_best, gto_label, gto_action, live_top_act = \
                    _vc.apply('multiway_advice', _v_mw_adv(
                        multiway_advice['action'], _norm(multiway_advice['action']),
                        _mw_leak(multiway_advice, action.action))).unpack()
            elif _mw_spot:
                # Advisor DEFERIU: o solver HU não é confiável aqui, então o veredito vem da
                # SEVERIDADE do engine (label EV-capado) — NÃO do gto_label de frequência HU
                # (que diria 'crítico' num spot que o coach aprova). Card = badge.
                is_error, reconciled_best, gto_label, gto_action, live_top_act = \
                    _vc.apply('multiway_engine', _v_mw_eng(
                        decision.get('label'), decision.get('best_action'),
                        reconciled_best, gto_action)).unpack()

            # Fase 2 (flag MULTIWAY_GRADE_SAFE_TAIL): a CAUDA SEGURA tem precedência sobre o
            # informativo. Veredito GARANTIDO (sobrevive ao canto adversário das premissas →
            # nunca pune jogada defensável): vira erro/correto REAL. Flag off → multiway_safe
            # None → comportamento de hoje (≈ aproximação) intacto.
            if _mw_spot:
                try:
                    from leaklab.multiway_safety import graded_safe_verdict as _gsv
                    multiway_safe = _gsv(
                        ''.join(_di.get('hero_cards') or []),
                        _spot.get('board') or [],
                        _nopp_mw,
                        float(_spot.get('potBb') or 0),
                        float(_spot.get('facingToBb') or 0),
                        action.action,
                        street=action.street,
                    )
                except Exception:
                    multiway_safe = None
                if multiway_safe:
                    from leaklab.card_verdict import verdict_from_multiway_safe as _v_mw_safe
                    _v4 = _v_mw_safe(multiway_safe['recommended'],
                                     _norm(multiway_safe['recommended']),
                                     multiway_safe['is_leak'])
                    is_error, reconciled_best, gto_label, gto_action, live_top_act = \
                        _vc.apply('multiway_safe', _v4).unpack()
                    multiway_advice     = None   # cauda segura SUBSTITUI o informativo
                    multiway_safe_label = _v4['safe_label']

        # Sizing do OPEN (Fase 1): tamanho do open preflop do hero vs o padrão de teoria
        # (~2bb; SBxBB sobe). O size sai do raw ("raises X to Y" → Y/bb), não do amount (=BY).
        # Gate: a crítica de open-sizing NÃO se aplica a jam (all-in tem size forçado) nem à zona
        # push/fold (≤12bb é jam-or-fold; "abra 2-2,5bb" ali é conselho de deep stack, sem sentido).
        _eff_stack = float(_spot.get('effectiveStackBb') or _ctx.get('heroStackBb') or 99)
        sizing_advice = None
        # `> 12` era PROXY de "zona de jam", e proxy erra: numa mao de 17bb efetivos o card dizia
        # ao mesmo tempo "GTO RECOMENDA: SHOVE" e "suba pra 3bb" — duas recomendacoes diferentes
        # na mesma tela. O sinal certo estava a duas linhas de distancia: a recomendacao
        # RECONCILIADA. Se a jogada e all-in, nao existe conselho de tamanho a dar; o tamanho e
        # forcado. Perguntar ao sistema em vez de aproximar por profundidade.
        _rec_norm = str(reconciled_best or '').lower()
        _rec_e_jam = _rec_norm in ('jam', 'shove', 'allin', 'all-in')
        if (action.player == hero and action.street == 'preflop'
                and action.action == 'raises' and decision
                and int(_spot.get('preflopRaisesFaced') or 0) == 0
                and not _rec_e_jam
                and _eff_stack > 12):
            try:
                # Total via parser (tolerante a separador de milhar). O regex antigo
                # `to\s+([\d.]+)` capturava "1" em "to 1,098" (CoinPoker/GG), então o
                # tamanho saía ~0bb e a análise de sizing sumia sem avisar nesses sites.
                _tot = _raise_total_from_raw(action.raw)
                _bbz = float(hand.bb or _ctx.get('levelBb') or 0)
                if _tot and _bbz > 0:
                    from leaklab.sizing_advisor import analyze_open_sizing as _szadv
                    sizing_advice = _szadv(to_bb=_tot / _bbz,
                                           position=(_spot.get('position') or ''),
                                           facing_limp=bool(_spot.get('facingLimp')),
                                           stack_bb=_eff_stack)
            except Exception:
                pass

        # Sizing do 3-BET (#3): tamanho do 3-bet do hero como múltiplo do open enfrentado
        # (IP ~3x, OOP ~4x; squeeze sobe). Só raise enfrentando exatamente 1 raise (não jam).
        threebet_sizing = None
        if (action.player == hero and action.street == 'preflop'
                and action.action == 'raises' and decision
                and int(_spot.get('preflopRaisesFaced') or 0) == 1):
            try:
                # mesmo bug do milhar do open: usa o parser em vez de regex local
                _tot3 = _raise_total_from_raw(action.raw)
                _bb3 = float(hand.bb or _ctx.get('levelBb') or 0)
                _open_to = _spot.get('facingToBb')
                if _tot3 and _bb3 > 0 and _open_to:
                    from leaklab.sizing_advisor import analyze_3bet_sizing as _szb
                    threebet_sizing = _szb(to_bb=_tot3 / _bb3,
                                           open_to_bb=float(_open_to),
                                           is_ip=bool(_spot.get('isInPosition')),
                                           squeeze=bool(_spot.get('callerPosition')))
            except Exception:
                pass

        # Sizing POSTFLOP (Fase 2): tamanho da aposta do hero vs o size principal do nó GTO.
        # O nó já traz os tamanhos (bet_33pct, bet_75pct…) com frequência — compara direto.
        postflop_sizing = None
        if (action.player == hero and action.street != 'preflop'
                and action.action in ('bets', 'raises') and decision and gto_strategy):
            try:
                from leaklab.sizing_advisor import (gto_main_bet_size_pct as _gms,
                                                    analyze_postflop_sizing as _pfs)
                _amt = float(amt or 0)
                _pot_before = float(pot) - _amt           # pot ANTES da aposta (pot já inclui o amt)
                if _amt > 0 and _pot_before > 0:
                    _bbv = float(hand.bb or _ctx.get('levelBb') or 0)
                    _pre_bb = (_pot_before / _bbv) if _bbv > 0 else None
                    postflop_sizing = _pfs(hero_pct=_amt / _pot_before * 100.0,
                                           gto_pct=_gms(gto_strategy, _pre_bb))
            except Exception:
                pass

        # Sizing POSTFLOP por HEURÍSTICA (Fase 3): só quando NÃO há nó GTO (multiway/deep/
        # sem cobertura). Board seco→pequeno, molhado→grande; nudge IP/OOP e SPR. Só 'bets'.
        postflop_texture_sizing = None
        if (action.player == hero and action.street != 'preflop'
                and action.action == 'bets' and decision and not gto_strategy):
            try:
                from leaklab.sizing_advisor import analyze_postflop_texture_sizing as _txs
                _amt = float(amt or 0)
                _pot_before = float(pot) - _amt
                _potbb = float(_spot.get('potBb') or 0)
                _eff   = float(_spot.get('effectiveStackBb') or 0)
                if _amt > 0 and _pot_before > 0:
                    postflop_texture_sizing = _txs(
                        hero_pct=_amt / _pot_before * 100.0,
                        board=(_spot.get('board') or []),
                        is_ip=bool(_spot.get('isInPosition')),
                        spr=(_eff / _potbb) if _potbb > 0 else None)
            except Exception:
                pass

        # O tier EFETIVO do passo, calculado UMA vez para os dois campos de display.
        #
        # A camada 1 conta 'marginal' como is_error DE PROPOSITO (e o que faz a recomendacao
        # aparecer em vez de abencoar a jogada), mas o piso do display promovia marginal
        # (Aceitavel) a small_mistake (Erro): o pill do replayer dizia ERRO onde card e lista
        # dizem Aceitavel (call do excesso, print de 14/08). A regra cirurgica usa a
        # PROVENIENCIA da cadeia: se a ULTIMA palavra foi da camada 1 ('stored') com label
        # marginal, nao ha acusacao — pill Aceitavel, anel e bolinha sem vermelho. Se qualquer
        # camada posterior opinou (override preflop major_leak, estrategia viva, multiway), o
        # piso continua valendo — e o que os goldens congelam (AJo call vs 3-bet major_leak
        # TEM de seguir ERRO; a 1a versao desta mudanca derrubou esses e o golden acusou).
        _so_marginal_camada_1 = (getattr(_vc, 'layer', None) == 'stored'
                                 and bool(decision) and decision.get('label') == 'marginal')
        # A cadeia viva NAO promove. O ramo antigo terminava em `else 'small_mistake'`: quando ela
        # dizia "erro" e o rotulo gravado nao era acusacao, a tela acusava por conta propria --
        # uma segunda politica de veredito por cima da do motor, e mais simples que ela.
        # Medido em 26/08: 24 divergencias lista x card em 486 decisoes, 22 delas do card
        # acusando mais e ZERO do card absolvendo. E em 22 das 24 o motor USOU o no do solver,
        # entao nao era falta de cobertura -- era o motor aplicando suas regras (piso por
        # direcao, teto de EV, ICM, piso de custo) e a cadeia viva ignorando todas. O regrade
        # completo do acervo devolveu `MUDAM: 0`, ou seja, banco e motor concordam: quem destoa
        # e a camada viva. Ver `verdict.label_exibido_da_camada_viva`.
        if multiway_safe_label is not None:
            _el_efetivo = multiway_safe_label
        elif multiway_advice:
            _el_efetivo = None
        else:
            _el_efetivo, is_error = _verdict_mod.label_exibido_da_camada_viva(
                decision.get('label') if decision else None, is_error)
        # PISO DE CUSTO, aplicado AQUI e uma vez so: o `_el_efetivo` alimenta `error_label`,
        # `error_score` e `is_error`, e aplicar depois (como na primeira tentativa) rebaixava o
        # rotulo e deixava `is_error: True` e o score fora da banda -- tres campos para o mesmo
        # fato, dois deles desatualizados.
        if (_el_efetivo in ('small_mistake', 'clear_mistake')
                and decision
                and _verdict_mod.custo_irrelevante_para_acusar(decision.get('ev_loss_bb'))):
            _el_efetivo = 'marginal'
            is_error = False
        # SEVERIDADE SEM CUSTO, tambem aqui e pelo mesmo motivo do piso acima: o /replay recomputa
        # o rotulo, entao o conserto feito no motor nao alcanca esta camada. Sem custo medido o
        # veredito nao afirma MAGNITUDE -- `clear_mistake` cai para `small_mistake`. Segue sendo
        # acusacao: a frequencia zero da carta e evidencia; o que nao ha e base para o tamanho.
        if _el_efetivo == 'clear_mistake' and decision:
            _el_efetivo = _verdict_mod.severidade_sem_custo(
                _el_efetivo, _tem_custo_da_linha(decision))
        # E a mesma invariante do motor, aqui: acusar com a recomendacao IGUAL a jogada e dizer
        # "voce errou, e o certo era o que voce fez". O conserto feito no motor nao alcanca este
        # rotulo, porque o /replay recomputa -- mesmo padrao que ja custou duas voltas com o
        # score e uma com o piso de custo. Se ha desvio, ele e de TAMANHO, e quem fala de tamanho
        # e o bloco de sizing.
        _best_exibido = (_best_action_proporcional(
            reconciled_best,
            (decision.get('pot_at_decision_bb') or decision.get('pot_size')) if decision else None,
            (decision.get('effective_stack_bb') or decision.get('stack_bb')) if decision else None,
            street=action.street) if decision else None)
        if (_el_efetivo in ('small_mistake', 'clear_mistake') and _best_exibido
                and str(_best_exibido).lower()
                == str(_normalize_action(action.action) or '').lower().rstrip('s')):
            _el_efetivo = 'marginal'
            is_error = False
        # O TETO DE JAM RECUSOU a recomendacao: acusar o aluno por nao ter feito aquilo que o
        # proprio produto se recusa a recomendar e incoerente. Quando `_best_action_proporcional`
        # troca o all-in por `bet`, ele esta dizendo "nao endosso este jam" -- e a partir dai o
        # que sobra na tela e uma palavra sem tamanho, que nao sustenta acusacao. Era o unico
        # `clear_mistake` do torneio 72, e um juiz de poker pediu para tira-lo da tela: all-in de
        # 3x o pote com segundo par, ENFRENTANDO uma aposta, exibido como "aposte".
        # `_best_exibido` VAZIO e o caso principal, nao o de borda: quando o teto recusa o jam ele
        # devolve None. A 1a versao exigia `_best_exibido` verdadeiro -- escrita quando a recusa
        # ainda devolvia a palavra `bet` -- e parou de disparar assim que a recusa virou None.
        # Resultado: a unica `clear_mistake` do torneio 72 seguiu acusando, agora SEM nenhuma
        # recomendacao ao lado. Um juiz de coerencia leu exatamente isso: "a acusacao mais grave
        # do acervo entregue sem resposta".
        if (_el_efetivo in ('small_mistake', 'clear_mistake') and reconciled_best
                and (not _best_exibido
                     or str(_best_exibido).lower() != str(reconciled_best).lower())):
            _el_efetivo = 'marginal'
            is_error = False
        # SEM ROTULO NAO HA ERRO. `_el_efetivo` fica None quando o advisor multiway assume, e o
        # `is_error` da cadeia seguia True: o card marcava "Erro" sem uma palavra que dissesse
        # QUAL erro. Um juiz de poker achou 4 assim no torneio 72, tres delas com custo medido
        # 0,00bb. Erro sem nome nao e veredito, e o aluno nao tem o que fazer com ele.
        if _el_efetivo is None:
            is_error = False
        timeline.append(snap({
            'type':               'action',
            'player':             action.player,
            'seat':               pseat,
            'action':             _normalize_action(action.action),
            'amount':             amt,
            'is_hero':            action.player == hero,
            # `gto_coverage` e calculado ANTES de `_mw_spot`, e usa o `gto_label` de antes da
            # supressao multiway -- entao dizia `covered` em 68 spots do torneio 72 nos quais o
            # payload NAO entrega rotulo nenhum, porque o produto se recusa a graduar multiway.
            # "Coberto" ao lado de "sem veredito" e a mesma contradicao de sempre, e foi o que
            # um juiz de QA leu como "a ausencia nao declara motivo": ela declarava, com a
            # palavra errada. O `_mw_spot` tem a ultima palavra.
            # PREFLOP tambem declara. `gto_coverage` so era calculado para postflop, entao 67
            # decisoes preflop de procedencia `motor` -- 3 delas ACUSANDO -- nao diziam uma
            # palavra sobre por que nao ha gabarito. A carta ja declara o motivo
            # (`limped_pot`, `pairing_uncovered`, `open_size_off_tree`...); faltava entrega-lo.
            'gto_coverage':       ('multiway' if _mw_spot else
                                   (gto_coverage or
                                    (_pf_cobertura if action.street == 'preflop' else None))),
            # A recusa se DECLARA. Sem isto o card so veria `best_action: null` e nao saberia
            # dizer se e ausencia de cobertura ou recusa deliberada de um jam desproporcional.
            'best_action_recusado': ('jam_desproporcional'
                                     if (reconciled_best and not _best_exibido) else None),
            'is_error':           bool(is_error and not _so_marginal_camada_1),
            # FEAT-20: severidade que dirige o veredito de 3 níveis do card. Em multiway-clear
            # o advisor é AUTORITATIVO (sobrepõe o label HU do engine, válido ou não): leak →
            # small_mistake (Erro), senão standard (Correto). Fora dele, a label do engine.
            # Mantém card = badge de aderência em todo spot.
            # B2 (opção informativa, igual Ghost Table): multiway NÃO é gradeado como erro/correto
            # (solver é HU-only, advisor é estimativa) — error_label=None → o card mostra "≈ aproximação"
            # neutro + a sugestão do advisor. B1: fora do multiway, deriva do is_error RECOMPUTADO live
            # (não do label antigo do DB); preserva clear/small; floora small_mistake quando is_error.
            # Fase 2: cauda segura graduada (multiway_safe_label) tem precedência — veredito
            # REAL (small_mistake/standard) em vez do None informativo. Senão, lógica de hoje.
            # Alinhado ao label EXIBIDO (`_el_efetivo`), nao ao gravado. O label aqui e
            # RECOMPUTADO ao vivo e costuma ser mais severo que o do banco; o score vinha da
            # coluna, entao a tela mostrava `small_mistake` com score 0. O backfill de 24/08
            # corrigiu a COLUNA e esta porta continuou servindo o numero velho -- duas portas
            # para o mesmo fato, uma consertada. Medido no torneio 7: 61 de 485 abaixo do piso.
            'error_label':        _el_efetivo,
            'error_score':        (_align_score_to_label(_el_efetivo, decision.get('score'),
                                                          decision.get('ev_loss_bb'))
                                   if decision else None),
            # PROCEDÊNCIA: de onde veio o veredito. Derivada AQUI quando a coluna ainda está
            # vazia (decisão anterior à migração), pela MESMA função do motor — reimplementar a
            # regra na API seria a segunda porta, o defeito mais recorrente deste projeto.
            # Quem teve a ULTIMA palavra na cadeia responde pela procedencia. `error_label` e
            # `gto_label` acima ja sao RECOMPUTADOS ao vivo; deixar `verdict_source` saindo da
            # coluna fazia o mesmo objeto dizer "veio do heuristico" e "o solver classificou como
            # desvio critico". Medido no torneio 72: 3 decisoes com `gto_critical` ao lado de
            # `motor`, com o banco guardando `marginal` 0,13 e `gto_label` NULO.
            # O CUSTO nao muda: a camada viva traz rotulo, nao traz EV — entao
            # `pode_falar_como_gto` segue False nesses casos, que e o certo.
            'verdict_source':     _verdict_mod.procedencia_da_camada(
                                      _vc.layer, _procedencia_da_linha(decision)),
            'verdict_has_cost':   _tem_custo_da_linha(decision, _motivo_do_custo),
            # A tela usa isto para decidir se pode escrever "leak"/"erro contra o equilíbrio" ou
            # se precisa dizer que é leitura do motor.
            # MULTIWAY: o mesmo payload suprime `gto_label` e `error_label` porque o solver é
            # HU-only e o produto se RECUSA a graduar o spot. Liberar a linguagem de GTO ali
            # seria dizer "não posso te dar o veredito" e "pode escrever leak" no mesmo objeto —
            # a falsa confiança que a procedência existe para eliminar, agora com carimbo de
            # autoridade. Medido no torneio 7: 3 de 4 spots multiway postflop faziam isso.
            'pode_falar_como_gto': _pode_falar_como_gto_da_linha(
                                       decision, multiway=_mw_spot,
                                       procedencia=_verdict_mod.procedencia_da_camada(
                                           _vc.layer, _procedencia_da_linha(decision)),
                                       motivo=_motivo_do_custo),
            # A recomendacao exibida nao nomeia acao que a carta VIVA joga 0% das vezes. A regra
            # existe no motor, mas o /replay consulta a carta por conta propria (`_pf`) e podia
            # exibir `raise` acima de `hand_freq {fold: 1.0, raise: 0.0}` -- 7 casos medidos, todos
            # `verdict_source: motor`. Mesma funcao do motor, chamada tambem aqui: regra 5.
            'best_action':        (_verdict_mod.recomendacao_coerente_com_a_carta(
                                       _best_exibido, (_pf_vivo or {}).get('hand_freq'))
                                   if (_pf_vivo or {}).get('scenario') == 'rfi'
                                   else _best_exibido),
            'engine_best':        engine_best if (gto_engine_conflict or gto_spot_mismatch) else None,
            'gto_label':          (None if _mw_spot else gto_label),
            'gto_action':         preflop_override_action or live_top_act or gto_action,
            'n_active_opponents': (_mw_nopp or None),   # >=2 = multiway (card usa severidade, não gto HU)
            # Pote LIMPADO: o card precisa saber para PARAR de esconder o preço. A supressão de
            # equity/pot odds no preflop existe porque a equity vs mão aleatória contradizia o
            # veredito — mas aqui ela é multiway de verdade (Monte Carlo), e este é justamente o
            # spot em que o preço é a única evidência que temos.
            'facing_limp':        bool(_spot.get('facingLimp')),
            'facing_to_call_bb':  _spot.get('facingToCallBb'),   # custo de entrar, em bb
            'n_can_see_flop':     _spot.get('nCanSeeFlop'),
            # Opção B: derivado AO VIVO (não da coluna armazenada, que a re-análise não
            # atualiza) — postflop coberto com stack >60bb é aproximação capada em 60bb.
            'gto_depth_capped':   (not _mw_spot and action.street != 'preflop' and bool(gto_label)
                                   and float(_spot.get('effectiveStackBb') or 0) > 60.0),
            'bet_intent':         (decision.get('bet_intent') if decision else None),  # intenção da aposta (value/blefe/meio)
            'threebet_intent':    (decision.get('threebet_intent') if decision else None),  # intenção do 3-bet (valor/merge/light)
            # Gate zona-ICM: aperto que o ChipEV reprova mas defensável sob ICM → card mostra
            # "≈ Aproximação chipEV" (não "Erro"). Só quando NÃO é multiway (lá já há badge próprio).
            'icm_zone_approx':    (bool(decision.get('icm_zone_approx')) if (decision and not _mw_spot) else False),
            'reco_rationale':     (decision.get('reco_rationale') if decision else None),  # por que a ação recomendada
            'villain_name':       (_di.get('spot', {}).get('villainName') if decision else None),  # HUD: vilão do spot
            'sizing_advice':      sizing_advice,   # Fase 1: análise do tamanho do open
            'threebet_sizing':    threebet_sizing,   # #3: tamanho do 3-bet vs open (IP 3x/OOP 4x)
            'postflop_sizing':    postflop_sizing,   # Fase 2: aposta do hero vs size do nó GTO
            'postflop_texture_sizing': postflop_texture_sizing,   # Fase 3: heurística de textura (sem nó)
            # ── O EV so vai para a tela se couber no JOGO ──────────────────────────────────
            # `ev_loss_trustworthy` e a fonte unica da regra "este numero pode ser usado como
            # quantidade", e ate 10/08 o motor a consultava para decidir SEVERIDADE enquanto o
            # card lia o valor gravado direto. Duas portas para o mesmo fato, e a do card nao
            # tinha guarda: um usuario viu **"-3588 bb" num stack de 32,2bb**.
            #
            # Medido: 62 decisoes com EV maior do que cabe na mao, 34 delas rotuladas
            # `clear_mistake`. A causa esta em `ev_loss_fold_ceiling` — o EV vem na escala do
            # POTE SOLVADO e o pote nao entra no `spot_hash`, entao nao ha como reescalar.
            #
            # `None` some com o selo e o custo de oportunidade, que e o certo: melhor o card nao
            # falar de custo do que falar um numero impossivel.
            'ev_loss_bb':         _ev_e_motivo(decision, _di, _spot)[0],  # #24
            # POR QUE o custo nao aparece. Tres motivos distintos — ver `_ev_e_motivo`.
            'ev_loss_motivo':     _motivo_do_custo,
            'multiway_advice':    multiway_advice,   # fallback multiway: equity-vs-range (estimativa, não GTO HU)
            'multiway_safe':      multiway_safe,     # Fase 2: veredito GRADEADO da cauda segura (None = informativo)
            # com estimativa multiway ativa, esconde as barras HU (o artefato que estamos
            # substituindo) — o card mostra a estimativa, não "raise 93%" do solver HU.
            # As FREQUENCIAS ficam (sao estrategia, nao dependem de escala); os EVs saem quando
            # nao cabem no jogo. Era daqui que vinham as linhas "Call 100% 3588.4bb" e o custo de
            # oportunidade do card que o usuario reportou — o selo tem guarda desde 10/08, estas
            # linhas nao tinham.
            'hand_strategy':      (None if _mw_spot
                                   else _sem_ev_impossivel(live_hand_strategy, decision, _di, _spot)),
            'gto_strategy':       (None if _mw_spot else gto_strategy),
            'gto_approx_stack':   (None if _mw_spot else _lk_approx_stack),   # MVP deep: ≈ aproximação a Xbb

            'gto_spot_mismatch':  gto_spot_mismatch if gto_label else None,
            # Qual das 4 camadas teve a última palavra neste card. Diagnóstico: até aqui, para
            # saber por que um card diz o que diz era preciso depurar o handler inteiro.
            'verdict_layer':      _vc.layer,
            'preflop_gto':        decision.get('preflop_gto') if decision else None,
            'desc':           f"{action.player}: {_normalize_action(action.action)}"
                                + (f' {int(amt)}' if amt else ''),
            'revealed_cards': dict(current_revealed) if current_revealed else None,
            **tech,
        }))

    # Ruas sem NENHUMA acao (all-in cedo: ninguem mais decide, mas o board continua sendo
    # dealt) nunca disparavam o "if action.street != street" acima, entao o replay parava no
    # ultimo street COM acao mesmo que a mao tivesse ido a showdown. Reportado pelo usuario:
    # mao parava as vezes no turn, as vezes no river, dependendo de onde o ultimo jogador foi
    # all-in. hand.board e o board FINAL, extraido das linhas "*** TURN/RIVER ***" independente
    # de acao (o parser atualiza ao ver o MARCADOR, nao uma decisao) -- fonte confiavel de
    # quantas cartas realmente sairam. Preenche os frames que faltaram, na mesma forma da
    # transicao normal (bets_r zera: ninguem tem ficha "na mesa" apos o all-in ser resolvido).
    for _rua, _n in (('flop', 3), ('turn', 4), ('river', 5)):
        if len(hand.board or []) >= _n and len(board) < _n:
            street = _rua
            board  = list(hand.board[:_n])
            bets_r = {s: 0 for s in seats}
            timeline.append(snap({'type': 'street', 'desc': _rua.upper(), 'revealed_cards': None}))

    # Apply uncalled bet returns — correct pot/stacks/bets before showdown.
    # Em maos uncontested (so o jogador do uncalled vai coletar o pot), pular
    # o frame de "return" pra evitar o efeito visual de 'aposta diminui antes
    # de virar pot'. Os dados de pot/stacks ainda sao aplicados.
    _summary_pre = _parse_summary(hand.raw_text or '')
    _uncontested_winners = set()
    if _summary_pre.get('winners') and len(_summary_pre['winners']) == 1:
        _uncontested_winners.add(_summary_pre['winners'][0]['player'])

    for ur in uncalled_returns:
        ur_player = ur['player']
        ur_amount = ur['amount']
        ur_pseat  = next((s for s, d in seats.items() if d['player'] == ur_player), None)
        pot                    = max(0, pot - ur_amount)
        if ur_pseat is not None:
            stacks[ur_pseat]   = stacks[ur_pseat] + ur_amount
            bets_r[ur_pseat]   = max(0, bets_r.get(ur_pseat, 0) - ur_amount)
        # Pula o frame visual se uncontested win — o pot displaced ja cobre.
        if ur_player in _uncontested_winners:
            continue
        timeline.append(snap({
            'type':   'return',
            'player': ur_player,
            'seat':   ur_pseat,
            'amount': ur_amount,
            'desc':   f"Uncalled bet ({ur_amount}) returned to {ur_player}",
        }))

    # Adicionar frame de conclusão com resultado da mão
    summary = _parse_summary(hand.raw_text or '')
    if summary.get('winners') or summary.get('seats'):
        # Garante que o board do showdown tem as 5 cartas (summary é fonte autoritativa,
        # cobre casos de dados importados antes da correção do parser)
        if summary.get('board'):
            board = summary['board']

        # Mapa seat_number → cartas reveladas (para mostrar cartas dos villains na mesa)
        revealed = {}
        for s_info in summary.get('seats', []):
            if s_info.get('cards'):
                pseat = next((sn for sn, sd in seats.items()
                              if sd['player'] == s_info['player']), None)
                if pseat is not None:
                    revealed[str(pseat)] = s_info['cards']

        timeline.append(snap({
            'type':           'showdown',
            'desc':           'Conclusão da mão',
            'summary':         summary,
            'revealed_cards':  revealed,   # {seat_num_str: ["Ah","Kd"]}
            'knockout_events': knockout_events if knockout_events else [],
        }))

    return {
        'hand_id':       str(hand.hand_id),
        'tournament_id': str(hand.tournament_id or ''),
        'hero':          hero,
        'hero_cards':    [hand.hero_cards[:2], hand.hero_cards[2:]]
                          if len(hand.hero_cards or '') >= 4 else [],
        'board':         hand.board,
        'button':        hand.button_seat,
        'sb':            hand.sb,
        'bb':            bb,
        'seats':         {s: {k: v for k, v in {
                              'player': seats[s]['player'],
                              'stack':  seats[s]['stack'],
                              'pos':    positions[s],
                              'bounty': seats[s].get('bounty'),
                          }.items() if v is not None} for s in seats},
        'is_bounty':     bool(_bounties),
        'timeline':      timeline,
    }


# ── BACK-010: Subscription endpoints ─────────────────────────────────────────

@app.route('/subscription/plans', methods=['GET'])
def subscription_plans():
    return jsonify({
        'plans': [
            {
                'id':          'free',
                'name':        'Freemium',
                'price':       0,
                'currency':    'BRL',
                'tournaments': PLAN_LIMITS['free']['tournaments'],
                'ai_calls':    PLAN_LIMITS['free']['ai_calls'],
                'features':    [
                    f"{PLAN_LIMITS['free']['tournaments']} torneios/mês",
                    f"{PLAN_LIMITS['free']['ai_calls']} análises LeakLabs/mês",
                    'Acesso a todas as funcionalidades de análise',
                    'Replayer, Ghost Table, plano de estudos',
                    'Heatmap GTO, leaks, evolução',
                    '✗ Sem AI Coach Chat',
                ],
            },
            {
                'id':          'pro',
                'name':        'Pro',
                'price':       9900,   # R$99,00 (mensal)
                'currency':    'BRL',
                'tournaments': PLAN_LIMITS['pro']['tournaments'],
                'ai_calls':    PLAN_LIMITS['pro']['ai_calls'],
                # PAY-02: opções de ciclo. annual = 2 meses grátis (R$990 vs R$1.188 cheio).
                'billing': {
                    'monthly': {'price': int(PLAN_AMOUNTS['pro'] * 100), 'period_days': BILLING_DAYS['monthly']},
                    'annual':  {
                        'price':            int(PLAN_AMOUNTS_ANNUAL['pro'] * 100),
                        'period_days':      BILLING_DAYS['annual'],
                        'monthly_equiv':    int(PLAN_AMOUNTS_ANNUAL['pro'] * 100 / 12),
                        'full_price':       int(PLAN_AMOUNTS['pro'] * 100 * 12),
                        'discount_pct':     round((1 - (PLAN_AMOUNTS_ANNUAL['pro'] / (PLAN_AMOUNTS['pro'] * 12))) * 100),
                        'months_free':      round(12 - PLAN_AMOUNTS_ANNUAL['pro'] / PLAN_AMOUNTS['pro']),
                    },
                },
                'features':    [
                    'Torneios ilimitados',
                    'Análises LeakLabs ilimitadas',
                    'AI Coach Chat (conversa contextual)',
                    'Plano de estudos personalizado',
                    'Acesso ao marketplace de coaches',
                    'Suporte prioritário',
                ],
            },
        ]
    })


@app.route('/subscription/status', methods=['GET'])
@require_auth
def subscription_status():
    status = get_quota_status(g.user_id)
    return jsonify(status)


@app.route('/subscription/upgrade', methods=['POST'])
@require_admin
def subscription_upgrade():
    """Upgrade MANUAL (admin) — concessão sem pagamento. Produção usa /subscription/checkout.

    PAY-03 (anti-fraude): era @require_auth → QUALQUER usuário se auto-concedia Pro de graça.
    Agora é @require_admin; aceita `user_id` opcional (default = o próprio admin)."""
    data = request.get_json(silent=True) or {}
    new_plan = data.get('plan', 'pro')
    target_id = data.get('user_id', g.user_id)
    if new_plan not in PLAN_LIMITS:
        return jsonify({'error': 'Plano inválido'}), 400
    update_user_plan(int(target_id), new_plan)
    return jsonify({'ok': True, 'plan': new_plan, 'user_id': target_id})


# ── BACK-015: Stripe Billing ──────────────────────────────────────────────────

@app.route('/subscription/checkout', methods=['POST'])
@require_auth
@limiter.limit("10 per hour")
def subscription_checkout():
    """Cria assinatura Stripe incompleta e retorna client_secret para o frontend."""
    data = request.get_json(silent=True) or {}
    plan = data.get('plan')
    billing = data.get('billing', 'monthly')
    if plan != 'pro':
        return jsonify({'error': 'Plano inválido. Use pro.'}), 400
    if billing not in ('monthly', 'annual'):
        return jsonify({'error': 'Ciclo inválido. Use monthly ou annual.'}), 400

    try:
        result = create_subscription(
            plan_name=plan,
            payer_email=g.user.get('email', ''),
            user_id=g.user_id,
            billing_cycle=billing,
        )
    except Exception as e:
        log.exception("Stripe checkout error for user %s plan %s", g.user_id, plan)
        if app.debug:
            return jsonify({'error': f'[DEBUG] Stripe: {e}'}), 502
        return jsonify({'error': 'Erro ao iniciar pagamento. Tente novamente.'}), 502

    # PAY-04: assinatura recorrente → vincula o sub_id ao usuário (sem mudar o plano)
    # para que os webhooks de ciclo de vida resolvam o usuário por mp_subscription_id.
    if result.get('recurring') and str(result['subscription_id']).startswith('sub_'):
        from database.repositories import link_subscription_id
        link_subscription_id(g.user_id, result['subscription_id'])

    return jsonify({
        'client_secret':   result['client_secret'],
        'subscription_id': result['subscription_id'],
        'billing':         result.get('billing_cycle', billing),
        'recurring':       bool(result.get('recurring')),
    })


@app.route('/subscription/activate', methods=['POST'])
@require_auth
def subscription_activate():
    """Verifica PaymentIntent e ativa o plano — chamado após confirmPayment no frontend."""
    data              = request.get_json(silent=True) or {}
    plan              = data.get('plan')
    payment_intent_id = data.get('payment_intent_id')
    subscription_id   = data.get('subscription_id')

    if plan != 'pro':
        return jsonify({'error': 'Plano inválido. Use pro.'}), 400
    if not payment_intent_id or not subscription_id:
        return jsonify({'error': 'payment_intent_id e subscription_id obrigatórios'}), 400

    # ── PAY-04: ASSINATURA RECORRENTE (sub_...) ──────────────────────────────────
    # Estado derivado da Subscription real (status + current_period_end); ownership por
    # metadata.user_id. O webhook invoice.paid é a fonte da verdade da recorrência; este
    # activate é a confirmação imediata (idempotente com o webhook via invoice id).
    if str(subscription_id).startswith('sub_'):
        sub = get_subscription(subscription_id)
        if not sub:
            return jsonify({'error': 'Assinatura não encontrada.'}), 400
        smeta = sub.get('metadata') or {}
        if str(smeta.get('user_id', '')) and str(smeta.get('user_id')) != str(g.user_id):
            log.warning("activate: sub %s pertence a %s, não a %s", subscription_id, smeta.get('user_id'), g.user_id)
            return jsonify({'error': 'Esta assinatura não pertence à sua conta.'}), 403
        status  = sub.get('status')
        expires = _ts_to_str(_fim_do_periodo(sub))
        cycle   = smeta.get('billing_cycle', 'monthly')
        cycle   = cycle if cycle in ('monthly', 'annual') else 'monthly'
        if status in ('active', 'trialing'):
            from database.repositories import apply_stripe_subscription, maybe_promote_coach_earned
            apply_stripe_subscription(g.user_id, status, expires, subscription_id)
            inv    = sub.get('latest_invoice')
            inv_id = inv if isinstance(inv, str) else (inv or {}).get('id')
            save_payment(user_id=g.user_id, plan='pro',
                         amount_cents=int(plan_amount('pro', cycle) * 100),
                         status='approved', gateway_id=str(inv_id or subscription_id),
                         gateway_sub_id=subscription_id, gateway='stripe', period_end=expires)
            _coach = g.user.get('coach_id')
            if _coach:
                try:
                    maybe_promote_coach_earned(_coach)
                except Exception:
                    log.exception("maybe_promote_coach_earned falhou (activate sub) coach=%s", _coach)
            return jsonify({'ok': True, 'plan': 'pro', 'subscription_id': subscription_id,
                            'recurring': True, 'status': status, 'expires_at': expires})
        # incomplete / past_due → ainda não pagou; o webhook invoice.paid confirmará.
        return jsonify({'ok': True, 'plan': g.user.get('plan', 'free'),
                        'subscription_id': subscription_id, 'recurring': True,
                        'status': status, 'pending': True})

    pi = get_payment(payment_intent_id)
    if not pi or pi.get('status') not in ('succeeded', 'processing'):
        status = pi.get('status') if pi else 'not_found'
        return jsonify({'error': f'Pagamento não confirmado (status: {status})'}), 400

    # PAY-03 (anti-fraude): NÃO confiar em nada que o cliente mande além do pi_id.
    # Tudo é derivado do PaymentIntent real do Stripe (metadata + amount):
    #  (A) o PI tem de PERTENCER ao usuário autenticado (metadata.user_id);
    #  (B) o ciclo vem do metadata (não do body) → não dá pra pagar mensal e reivindicar anual;
    #  (C) o valor gravado é o REALMENTE cobrado (pi.amount), conferido contra a tabela de preços.
    meta = pi.get('metadata') or {}
    pi_user = str(meta.get('user_id', ''))
    if pi_user and pi_user != str(g.user_id):
        log.warning("activate: PI %s pertence a user %s, não a %s", payment_intent_id, pi_user, g.user_id)
        return jsonify({'error': 'Este pagamento não pertence à sua conta.'}), 403
    billing = meta.get('billing_cycle', 'monthly')
    if billing not in ('monthly', 'annual'):
        billing = 'monthly'
    pi_plan = meta.get('plan_name') or plan
    if pi_plan != 'pro':
        return jsonify({'error': 'Plano do pagamento inválido.'}), 400
    expected_cents = int(plan_amount('pro', billing) * 100)
    charged_cents  = int(pi.get('amount') or expected_cents)
    if charged_cents != expected_cents:
        log.warning("activate: valor cobrado %s != esperado %s (pi=%s cycle=%s)",
                    charged_cents, expected_cents, payment_intent_id, billing)
        return jsonify({'error': 'Valor do pagamento não confere com o plano.'}), 400

    period_start, period_end = _plan_period(billing)   # PAY-02: vigência mensal/anual
    update_user_plan(g.user_id, 'pro', subscription_id, plan_expires_at=period_end)
    save_payment(
        user_id=g.user_id,
        plan='pro',
        amount_cents=charged_cents,   # valor REAL do PI, não o reivindicado pelo cliente
        status='approved',
        gateway_id=payment_intent_id,
        gateway_sub_id=subscription_id,
        gateway='stripe',
        period_start=period_start,
        period_end=period_end,
    )
    # COACH-02: aluno indicado virou pagante → pode fechar a meta de 15 do coach.
    _coach_id = g.user.get('coach_id')
    if _coach_id:
        try:
            from database.repositories import maybe_promote_coach_earned
            maybe_promote_coach_earned(_coach_id)
        except Exception:
            log.exception("maybe_promote_coach_earned falhou (activate) coach=%s", _coach_id)
    return jsonify({'ok': True, 'plan': plan, 'subscription_id': subscription_id,
                    'billing': billing, 'expires_at': period_end})


def _como_dict(x) -> dict:
    """Qualquer coisa vinda do SDK do Stripe vira dicionario de verdade.

    `StripeObject` NAO e um dict nesta versao: `.get` levanta `AttributeError` e `dict(obj)` tenta
    iterar como sequencia e levanta `KeyError: 0`. Eu tropecei nas duas formas no mesmo dia, em
    tres lugares diferentes -- por isso existe um lugar so para converter.

    `str(obj)` do SDK devolve JSON valido; e o caminho mais barato e o unico que nao depende de
    qual atributo o Stripe moveu de lugar nesta semana.
    """
    if isinstance(x, dict):
        return x
    if x is None:
        return {}
    try:
        import json as _j
        d = _j.loads(str(x))
        return d if isinstance(d, dict) else {}
    except Exception:                                          # noqa: BLE001
        return {}


def _fim_do_periodo(sub) -> int | None:
    """O `current_period_end` de uma Subscription, nas DUAS formas que o Stripe ja usou.

    Terceiro campo que mudou de lugar na reorganizacao da API (`2026-04-22.dahlia`): o periodo
    saiu do nivel da assinatura e foi para CADA ITEM dela.

    O defeito que isto conserta, medido em 28/08: o `invoice.paid` gravava a expiracao correta, e
    o `customer.subscription.updated` -- que chega DEPOIS -- lia `sub['current_period_end']`,
    recebia `None`, e **sobrescrevia a data com nulo**. O usuario virava Pro sem validade: se a
    renovacao falhasse, nao havia quando rebaixar.

    Ordem observada dos eventos: invoice.paid (8o) e customer.subscription.updated (10o). O
    ultimo a falar vence, e o ultimo estava lendo o lugar errado.
    """
    if not sub:
        return None
    direto = sub.get('current_period_end') if isinstance(sub, dict) else getattr(sub, 'current_period_end', None)
    if direto:
        return direto
    itens = (sub.get('items') if isinstance(sub, dict) else getattr(sub, 'items', None)) or {}
    dados = (itens.get('data') if isinstance(itens, dict) else getattr(itens, 'data', None)) or []
    if not dados:
        return None
    primeiro = dados[0]
    return (primeiro.get('current_period_end') if isinstance(primeiro, dict)
            else getattr(primeiro, 'current_period_end', None))


def _subscription_da_invoice(obj) -> str | None:
    """O id da assinatura de uma invoice, nas DUAS formas que o Stripe ja usou.

    ── O defeito, medido em 28/08 na jornada de pagamento completa ──────────────────────────

    O Stripe REMOVEU `invoice.subscription` na API atual (`2026-04-22.dahlia`) e mudou o campo
    para `invoice.parent.subscription_details.subscription`. Nosso handler lia so o caminho
    antigo, recebia `None`, e `get_user_by_subscription(None)` nao achava ninguem.

    O efeito exato, exercitado no modo de teste: o cartao foi aprovado, a assinatura ficou
    `active`, o Stripe cobrou R$ 39,90, os 13 tipos de webhook chegaram e todos responderam
    **200** -- e o usuario **continuou `free`**. Pagou e nao recebeu. Nada disso gera erro em
    lugar nenhum, porque um `None` que nao acha usuario e indistinguivel de um evento que nao
    era para nos.

    O `payment_intent.succeeded` falha pelo mesmo motivo por outro caminho: na assinatura
    recorrente o metadata mora na Subscription, e o PaymentIntent da fatura chega sem `user_id`.

    Le as duas formas de proposito: eventos antigos reentregues pelo Stripe (retry, replay) ainda
    chegam no formato velho, e quebrar o historico para consertar o presente trocaria um defeito
    por outro.
    """
    if not obj:
        return None
    direto = obj.get('subscription') if isinstance(obj, dict) else getattr(obj, 'subscription', None)
    if direto:
        return direto
    pai = obj.get('parent') if isinstance(obj, dict) else getattr(obj, 'parent', None)
    if not pai:
        return None
    det = pai.get('subscription_details') if isinstance(pai, dict) else getattr(pai, 'subscription_details', None)
    if not det:
        return None
    return (det.get('subscription') if isinstance(det, dict)
            else getattr(det, 'subscription', None))


def _metadata_da_invoice(obj) -> dict:
    """O metadata que viaja com a assinatura da invoice. Segunda porta para achar o usuario
    quando ele ainda nao tem `mp_subscription_id` gravado (ex.: 1a fatura chegando antes do
    nosso registro)."""
    pai = (obj.get('parent') if isinstance(obj, dict) else getattr(obj, 'parent', None)) or {}
    det = (pai.get('subscription_details') if isinstance(pai, dict)
           else getattr(pai, 'subscription_details', None)) or {}
    m = det.get('metadata') if isinstance(det, dict) else getattr(det, 'metadata', None)
    return dict(m) if m else {}


@app.route('/subscription/webhook', methods=['POST'])
def subscription_webhook():
    """Recebe eventos Stripe e atualiza planos/pagamentos."""
    import json as _json
    payload    = request.get_data()
    sig_header = request.headers.get('stripe-signature', '')

    if not STRIPE_WEBHOOK_SECRET:
        # Em produção, RECUSAR webhook não assinado: sem o secret, um atacante POSTa um evento
        # forjado (payment_intent.succeeded com metadata arbitrária) e se auto-concede Pro.
        from database.auth import is_production as _e_prod2
        if _e_prod2():
            log.error("STRIPE_WEBHOOK_SECRET ausente em produção — webhook recusado")
            return jsonify({'error': 'Webhook not configured'}), 503
        # Dev sem secret — aceita sem validar
        try:
            event = _json.loads(payload)
        except Exception:
            return jsonify({'error': 'Bad payload'}), 400
    else:
        try:
            event = validate_webhook(payload, sig_header)
        except Exception as e:
            log.warning("Stripe webhook validation error: %s", e)
            return jsonify({'error': 'Invalid signature'}), 400

    # ── O evento vira DICIONÁRIO aqui, uma vez ────────────────────────────────────────────
    #
    # `validate_webhook` devolve um `StripeObject`, que **não responde a `.get`**: o
    # `__getattr__` dele procura a chave `'get'` nos dados e levanta `AttributeError`. O resto
    # deste handler é escrito com `obj.get(...)` em dezenas de linhas.
    #
    # O efeito, medido em 28/08 percorrendo a jornada inteira no modo de teste: **todo evento de
    # assinatura estourava**, o `except` genérico abaixo engolia, e o handler devolvia **200**. O
    # Stripe considera entregue e nunca reenvia. O cartão foi aprovado, a assinatura ficou
    # `active`, R$ 39,90 cobrados, e o usuário continuou `free`.
    #
    # E o pior: só acontece com o segredo CONFIGURADO. Sem segredo, o caminho é `json.loads` e vem
    # um dict de verdade -- que é o caminho dos testes. **A suíte inteira passava por cima do
    # defeito**, porque exercitava a metade que funciona.
    #
    # Normalizar aqui e não espalhar `isinstance` é o conserto: uma porta, e o resto do handler
    # passa a falar com o mesmo tipo sempre.
    if not isinstance(event, dict):
        try:
            event = _json.loads(str(event))
        except Exception:                                      # noqa: BLE001
            event = {'type': getattr(event, 'type', ''),
                     'data': {'object': dict(getattr(event, 'data', {}).get('object', {}))}}
    event_type = event.get('type', '')
    obj        = (event.get('data') or {}).get('object') or {}
    log.info("Stripe webhook type=%s", event_type)

    # Blindagem: erro de PROCESSAMENTO (ex.: evento sem metadata) NÃO retorna 500 — o Stripe
    # re-tentaria por dias. Assinatura inválida segue 400 acima; aqui o evento foi RECEBIDO (200)
    # e o erro fica logado p/ auditoria. Eventos não tratados caem no ack final.
    try:
        if event_type == 'payment_intent.succeeded':
            # PaymentIntent concluído — ativa plano via metadata
            meta      = obj.get('metadata', {}) if isinstance(obj, dict) else obj.metadata
            user_id   = int(meta.get('user_id', 0))
            plan_name = meta.get('plan_name', '')
            billing   = meta.get('billing_cycle', 'monthly') if isinstance(meta, dict) else 'monthly'
            if billing not in ('monthly', 'annual'):
                billing = 'monthly'
            pi_id     = obj.get('id', '') if isinstance(obj, dict) else obj.id
            amount    = obj.get('amount', 0) if isinstance(obj, dict) else obj.amount
            if user_id and plan_name:
                period_start, period_end = _plan_period(billing)   # PAY-02: vigência
                update_user_plan(user_id, plan_name, str(pi_id), plan_expires_at=period_end)
                save_payment(
                    user_id=user_id, plan=plan_name,
                    amount_cents=int(amount),
                    status='approved',
                    gateway_id=str(pi_id),
                    gateway_sub_id=str(pi_id),
                    gateway='stripe',
                    period_start=period_start,
                    period_end=period_end,
                )
                # COACH-02: aluno indicado virou pagante → pode fechar a meta do coach.
                try:
                    _u = get_user_by_id(user_id)
                    if _u and _u.get('coach_id'):
                        from database.repositories import maybe_promote_coach_earned
                        maybe_promote_coach_earned(_u['coach_id'])
                except Exception:
                    log.exception("maybe_promote_coach_earned falhou (webhook) user=%s", user_id)

        elif event_type == 'payment_intent.payment_failed':
            # PAY-01: registra a falha p/ trilha de auditoria/suporte (não altera o plano).
            meta      = obj.get('metadata', {}) if isinstance(obj, dict) else obj.metadata
            user_id   = int(meta.get('user_id', 0) or 0)
            plan_name = meta.get('plan_name', '') if isinstance(meta, dict) else ''
            pi_id     = obj.get('id', '') if isinstance(obj, dict) else obj.id
            amount    = obj.get('amount', 0) if isinstance(obj, dict) else obj.amount
            if user_id:
                save_payment(
                    user_id=user_id, plan=plan_name or 'pro',
                    amount_cents=int(amount or 0),
                    status='failed',
                    gateway_id=str(pi_id),
                    gateway_sub_id=str(pi_id),
                    gateway='stripe',
                )

        # ── PAY-04: ciclo de vida da ASSINATURA RECORRENTE ──────────────────────────
        elif event_type == 'invoice.paid':
            # Renovação (ou 1ª cobrança) paga → mantém/estende o Pro. Fonte da verdade da
            # recorrência. Idempotente: save_payment dedupe por invoice id (gateway_id).
            from database.repositories import get_user_by_subscription, apply_stripe_subscription
            sub_id  = _subscription_da_invoice(obj)
            inv_id  = obj.get('id')
            amount  = obj.get('amount_paid', 0) or 0
            _lines  = (obj.get('lines') or {}).get('data') or [{}]
            per_end = _ts_to_str((_lines[0].get('period') or {}).get('end'))
            u = get_user_by_subscription(sub_id) if sub_id else None
            if not u:
                # Segunda porta: o metadata que viaja com a assinatura. A 1ª fatura pode chegar
                # antes de `mp_subscription_id` estar gravado (o Stripe entrega o webhook em
                # milissegundos, e o nosso registro acontece na resposta do checkout). Sem esta
                # porta, quem paga na primeira tentativa depende de uma corrida para virar Pro.
                _meta = _metadata_da_invoice(obj)
                try:
                    _uid = int(_meta.get('user_id') or 0)
                except (TypeError, ValueError):
                    _uid = 0
                if _uid:
                    from database.repositories import get_user_by_id as _get_u
                    u = _get_u(_uid)
            if u:
                apply_stripe_subscription(u['id'], 'active', per_end, sub_id)
                save_payment(user_id=u['id'], plan='pro', amount_cents=int(amount),
                             status='approved', gateway_id=str(inv_id or sub_id),
                             gateway_sub_id=str(sub_id), gateway='stripe', period_end=per_end)
                try:
                    if u.get('coach_id'):
                        from database.repositories import maybe_promote_coach_earned
                        maybe_promote_coach_earned(u['coach_id'])
                except Exception:
                    log.exception("promote coach (invoice.paid) user=%s", u['id'])

        elif event_type == 'invoice.payment_failed':
            # Falha de renovação → registra; NÃO faz downgrade (Stripe entra em retry/dunning).
            from database.repositories import get_user_by_subscription
            sub_id = _subscription_da_invoice(obj)
            inv_id = obj.get('id')
            amount = obj.get('amount_due', 0) or 0
            u = get_user_by_subscription(sub_id) if sub_id else None
            if u:
                save_payment(user_id=u['id'], plan='pro', amount_cents=int(amount),
                             status='failed', gateway_id=str(inv_id or sub_id),
                             gateway_sub_id=str(sub_id), gateway='stripe')

        elif event_type in ('customer.subscription.updated', 'customer.subscription.deleted'):
            # Mudança de status (active/past_due/canceled). deleted → downgrade p/ free.
            from database.repositories import get_user_by_subscription, apply_stripe_subscription
            sub_id  = obj.get('id')
            status  = 'canceled' if event_type.endswith('deleted') else obj.get('status')
            per_end = _ts_to_str(_fim_do_periodo(obj))
            smeta   = obj.get('metadata') or {}
            uid     = int(smeta.get('user_id', 0) or 0)
            if not uid and sub_id:
                u = get_user_by_subscription(sub_id)
                uid = u['id'] if u else 0
            # Motivo do churn p/ análise no admin: cancellation_details.reason (voluntário/involuntário).
            _cd = obj.get('cancellation_details') or {}
            cancel_reason = _cd.get('reason') or _cd.get('feedback') if status == 'canceled' else None
            if uid:
                apply_stripe_subscription(uid, status, per_end, sub_id, cancel_reason=cancel_reason)

        elif event_type == 'charge.refunded':
            # Estorno: marca o pagamento como refunded (sai da receita); se TOTAL e cobria o Pro,
            # rebaixa o usuário p/ free. Requer o evento 'charge.refunded' habilitado no webhook.
            # ── Grava com uma chave, procura com outra (28/08) ──────────────────────────
            #
            # Exercitado no modo de teste: o estorno de R$ 39,90 foi concluido, o
            # `charge.refunded` chegou -- e o usuario **continuou Pro**. Devolveu o dinheiro e
            # ficou com o produto.
            #
            # A causa: no caminho RECORRENTE, `invoice.paid` grava `gateway_id` = id da FATURA
            # (`in_...`), e o `charge.refunded` traz o PaymentIntent (`pi_...`). Nunca casam. E o
            # `charge['invoice']` vem `None` nesta versao da API, entao nem a ponte obvia existe.
            #
            # A ponte que EXISTE e a assinatura: do PaymentIntent chega-se a fatura, e da fatura
            # ao `sub_...` que gravamos em `gateway_sub_id`. Tres tentativas, da mais barata para
            # a mais cara, e cada uma so roda se a anterior falhou.
            from database.repositories import mark_payment_refunded
            _pi   = obj.get('payment_intent') or obj.get('id')
            _full = bool(obj.get('refunded'))   # True = estorno integral
            _uid  = mark_payment_refunded(str(_pi), full=_full) if _pi else None
            if not _uid:
                # ── A ponte que NOS controlamos ─────────────────────────────────────────
                #
                # Nenhum payload liga o estorno ao pagamento: medido em 28/08, nem o
                # `PaymentIntent`, nem o `Charge`, nem a propria `Invoice` carregam o outro lado
                # nesta versao da API. Cacar a fatura a partir do PI foi a 1a tentativa e falhou
                # nas tres pontes -- o log `ESTORNO SEM DONO` que instrumentei foi quem mostrou.
                #
                # O elo estavel e o CLIENTE: `_get_or_create_customer` grava `user_id` no metadata
                # dele, entao esse dado e nosso e nao depende de como o Stripe reorganiza os
                # objetos. Enquanto formos nos a escrever, a ponte continua de pe.
                _cli = obj.get('customer')
                if _cli:
                    try:
                        import stripe as _sdk
                        _cli_obj = _como_dict(_sdk.Customer.retrieve(str(_cli)))
                        _uid = int((_cli_obj.get('metadata') or {}).get('user_id') or 0) or None
                    except Exception:                          # noqa: BLE001
                        log.exception('estorno: nao consegui ler o cliente %s', _cli)
                    if _uid and _pi:
                        # Marca o pagamento pela ASSINATURA do usuario, para ele sair da receita.
                        try:
                            from database.repositories import mark_payment_refunded_by_user
                            mark_payment_refunded_by_user(_uid, full=_full)
                        except ImportError:
                            log.warning('estorno: pagamento de %s nao marcado como refunded '
                                        '(sem mark_payment_refunded_by_user); o plano cai, mas a '
                                        'receita do admin fica inflada ate alguem conferir', _uid)
            if _uid:
                update_user_plan(_uid, 'free', None)
                # O STATUS tambem cai. Sem isto o plano vira `free` e `subscription_status` fica
                # `active`: a tela do admin e o painel do coach continuam mostrando uma assinatura
                # viva para quem pediu o dinheiro de volta. Medido na jornada de 28/08 -- o plano
                # caiu certo e o status mentiu.
                try:
                    from database.repositories import apply_stripe_subscription
                    apply_stripe_subscription(_uid, 'canceled', None, None,
                                              cancel_reason='refunded')
                except Exception:                              # noqa: BLE001
                    log.exception('estorno: plano caiu mas o status nao (user=%s)', _uid)
                log.info('ESTORNO aplicado: user=%s rebaixado para free (charge=%s)',
                         _uid, obj.get('id'))
            else:
                # NAO fica calado: um estorno que nao acha o dono e dinheiro devolvido com o
                # produto entregue, e sem este log ninguem descobre ate a auditoria.
                log.error('ESTORNO SEM DONO: charge=%s pi=%s cliente=%s -- o usuario segue com o '
                          'plano', obj.get('id'), _pi, obj.get('customer'))
    except Exception:
        log.exception("Stripe webhook processing failed type=%s", event_type)
    return jsonify({'ok': True})


@app.route('/subscription/invoices', methods=['GET'])
@require_auth
def subscription_invoices():
    """Histórico de pagamentos do usuário autenticado."""
    payments = get_payments(g.user_id)
    return jsonify({'invoices': payments})


@app.route('/subscription/cancel', methods=['POST'])
@require_auth
def subscription_cancel_endpoint():
    """Cancela a assinatura do usuário.

    PAY-04: assinatura recorrente (`sub_`) → agenda cancelamento p/ o **fim do período**
    (mantém Pro até lá); o webhook `customer.subscription.deleted` fará o downgrade depois.
    PI legado (`pi_`) → downgrade imediato (não há recorrência a interromper)."""
    sub_id = g.user.get('mp_subscription_id')
    if not sub_id:
        return jsonify({'error': 'Nenhuma assinatura ativa encontrada'}), 400
    is_recurring = str(sub_id).startswith('sub_')
    try:
        cancel_subscription(sub_id, at_period_end=is_recurring)
    except Exception:
        log.exception("cancel falhou sub=%s", sub_id)
        return jsonify({'error': 'Erro ao cancelar assinatura no gateway'}), 502
    if is_recurring:
        return jsonify({'ok': True, 'plan': g.user.get('plan', 'pro'),
                        'cancel_at_period_end': True})
    update_user_plan(g.user_id, 'free', None)
    return jsonify({'ok': True, 'plan': 'free'})


@app.route('/subscription/portal', methods=['POST'])
@require_auth
def subscription_portal():
    """PAY-04: cria uma sessão do Billing Portal hospedado do Stripe — o cliente gerencia
    cartão, faturas e cancelamento self-service. Retorna {url} para redirecionar."""
    data    = request.get_json(silent=True) or {}
    ret_url = data.get('return_url') or (request.headers.get('Origin', '') + '/dashboard')
    try:
        sess = create_billing_portal_session(g.user_id, ret_url)
    except Exception:
        log.exception("billing portal falhou user=%s", g.user_id)
        return jsonify({'error': 'Erro ao abrir o portal de pagamento.'}), 502
    if not sess:
        return jsonify({'error': 'Nenhum cadastro de pagamento encontrado.'}), 404
    return jsonify(sess)


# ── Admin Panel — BACK-017 ────────────────────────────────────────────────────

@app.route('/admin/dashboard', methods=['GET'])
@require_admin
def admin_dashboard():
    return jsonify(get_admin_dashboard_stats())


@app.route('/admin/reconcile-tournament/<int:tournament_db_id>', methods=['POST'])
@require_admin
def admin_reconcile_tournament(tournament_db_id: int):
    """Forca reconciliacao manual de label vs gto_label para um torneio.
    Tambem roda o sync de gto_labels preflop via ranges estaticos antes
    do reconcile, garantindo que decisions sem cobertura GTO recebam
    classificacao quando possivel.
    """
    import sys as _sys
    from pathlib import Path as _Path
    _scripts = str(_Path(__file__).resolve().parent.parent / 'scripts')
    if _scripts not in _sys.path:
        _sys.path.insert(0, _scripts)

    sync_count = 0
    try:
        from sync_gto_labels_from_ranges import sync_tournament
        sync_count = sync_tournament(tournament_db_id) or 0
    except Exception as e:
        return jsonify({'error': f'sync_failed: {e}'}), 500

    try:
        # `only_ids=[]` pelo mesmo motivo do outro chamador pós-sync: o sync já reconciliou o
        # que mudou, e varrer o resto reescreveria o veredito do motor.
        reconciled = reconcile_tournament_labels(tournament_db_id, only_ids=[])
    except Exception as e:
        return jsonify({'error': f'reconcile_failed: {e}'}), 500

    # Buscar timestamp atualizado
    from database.schema import get_conn as _get_conn
    conn = _get_conn()
    try:
        row = conn.execute(
            "SELECT labels_reconciled_at FROM tournaments WHERE id=?",
            (tournament_db_id,)
        ).fetchone()
    finally:
        conn.close()
    return jsonify({
        'tournament_id': tournament_db_id,
        'preflop_synced': sync_count,
        'reconciled': reconciled,
        'labels_reconciled_at': row['labels_reconciled_at'] if row else None,
    })


@app.route('/admin/label-coherence', methods=['GET'])
@require_admin
def admin_label_coherence():
    """Auditoria de coerencia label vs gto_label. Read-only.
    Query params:
      user_id (int, opcional) — filtrar por usuario
      scan_limit (int, default 5000) — limite de decisions no audit C (live vs stored)
    """
    import sys as _sys
    from pathlib import Path as _Path
    _scripts = str(_Path(__file__).resolve().parent.parent / 'scripts')
    if _scripts not in _sys.path:
        _sys.path.insert(0, _scripts)
    from audit_label_coherence import run_audit
    user_id = request.args.get('user_id', type=int)
    scan_limit = request.args.get('scan_limit', type=int, default=5000)
    return jsonify(run_audit(user_id=user_id, scan_limit=scan_limit))


@app.route('/admin/users', methods=['GET'])
@require_admin
def admin_users():
    limit  = int(request.args.get('limit', 50))
    offset = int(request.args.get('offset', 0))
    plan   = request.args.get('plan')
    role   = request.args.get('role')
    search = request.args.get('search')
    users  = get_all_users(limit=limit, offset=offset, plan=plan, role=role, search=search)
    total  = get_all_users_count(plan=plan, role=role, search=search)
    return jsonify({'users': users, 'total': total})


@app.route('/admin/tournaments', methods=['GET'])
@require_admin
def admin_tournaments():
    """Torneios de TODOS os usuários (suporte/depuração): reproduzir na própria conta um bug
    reportado por um jogador. Não devolve o raw_text (pesado) — o download é o endpoint abaixo."""
    from database.repositories import get_all_tournaments_admin, get_all_tournaments_admin_count
    limit   = min(int(request.args.get('limit', 50)), 200)
    offset  = int(request.args.get('offset', 0))
    site    = request.args.get('site') or None
    search  = request.args.get('search') or None
    user_id = request.args.get('user_id') or None
    return jsonify({
        'tournaments': get_all_tournaments_admin(limit=limit, offset=offset, site=site,
                                                 search=search, user_id=user_id),
        'total':       get_all_tournaments_admin_count(site=site, search=search, user_id=user_id),
    })


def _tournament_raw_filename(site, tournament_id, name) -> str:
    """Padrão único de nome do .txt (espelhado em scripts/export_tournament_raw.py)."""
    import re as _re_fn
    parts = [str(site or 'site'), str(tournament_id or 'sem-id')]
    if name:
        slug = _re_fn.sub(r'[^\w\-]+', '-', str(name), flags=_re_fn.UNICODE).strip('-')[:60]
        if slug:
            parts.append(slug)
    return '_'.join(parts) + '.txt'


@app.route('/admin/tournaments/<int:tournament_db_id>/raw.txt', methods=['GET'])
@require_admin
def admin_tournament_raw(tournament_db_id):
    """Download do hand history CRU de um torneio (.txt), pra reimportar e reproduzir o bug.
    Read-only. Acesso restrito a admin (dado de jogador — não expor fora do painel)."""
    from flask import Response
    from database.repositories import get_tournament_raw_admin
    t = get_tournament_raw_admin(tournament_db_id)
    if not t:
        return jsonify({'error': 'Torneio não encontrado'}), 404
    raw = t.get('raw_text')
    if not raw:
        return jsonify({'error': 'Torneio sem raw_text (import antigo, antes do armazenamento do cru)'}), 404
    app.logger.info("admin_tournament_raw: admin=%s baixou torneio db_id=%s (user=%s)",
                    getattr(g, 'user_id', '?'), tournament_db_id, t.get('username'))
    fname = _tournament_raw_filename(t.get('site'), t.get('tournament_id'), t.get('tournament_name'))
    resp = Response(raw, content_type='text/plain; charset=utf-8')
    resp.headers['Content-Disposition'] = f'attachment; filename="{fname}"'
    return resp


# Kill switch do comunicado por email: OFF por padrão. Enquanto não ligar
# ADMIN_EMAIL_ENABLED=1 no host, nenhum email de comunicado dispara (o toggle
# no painel vira no-op e o sino segue funcionando normalmente).
def _admin_email_enabled() -> bool:
    return os.environ.get('ADMIN_EMAIL_ENABLED', '').strip().lower() in ('1', 'true', 'yes', 'on')


def _winback_enabled() -> bool:
    """Win-back automático (cron) só roda com WINBACK_ENABLED=1 e SMTP configurado.
    O disparo manual pelo admin não exige a flag (só SMTP)."""
    return (os.environ.get('WINBACK_ENABLED', '').strip().lower() in ('1', 'true', 'yes', 'on')
            and bool(os.environ.get('SMTP_HOST')))


@app.route('/admin/message', methods=['POST'])
@require_admin
def admin_send_message():
    """Admin → mensagem direta a UM jogador (cai no sino de notificações via create_notification)."""
    from database.repositories import create_notification
    data  = request.get_json(force=True) or {}
    try:
        uid = int(data.get('user_id') or 0)
    except Exception:
        uid = 0
    title = (data.get('title') or '').strip()
    body  = (data.get('body') or '').strip()
    link  = (data.get('link') or '').strip() or None
    cat   = (data.get('category') or 'info').strip() or 'info'
    if cat not in ('info', 'aviso', 'novidade'):
        cat = 'info'
    if not uid or not (title or body):
        return jsonify({'error': 'user_id e (título ou corpo) são obrigatórios'}), 400
    create_notification(uid, 'admin_message', {'title': title, 'body': body, 'category': cat}, link)
    # Espelha por email (opt-in respeitado). Gated pelo kill switch ADMIN_EMAIL_ENABLED.
    emailed = 0
    if bool(data.get('email')) and _admin_email_enabled():
        recipients = get_email_recipients([uid])
        emailed = send_admin_email_bulk(recipients, title, body, cat).get('sent', 0)
    return jsonify({'ok': True, 'emailed': emailed})


@app.route('/admin/broadcast', methods=['POST'])
@require_admin
def admin_broadcast():
    """Admin → broadcast a TODOS os jogadores (ou filtrado por role/plan). Fan-out 1 notif/usuário."""
    from database.repositories import get_all_user_ids, broadcast_notification
    data  = request.get_json(force=True) or {}
    title = (data.get('title') or '').strip()
    body  = (data.get('body') or '').strip()
    link  = (data.get('link') or '').strip() or None
    if not (title or body):
        return jsonify({'error': 'título ou corpo obrigatório'}), 400
    cat   = (data.get('category') or 'info').strip() or 'info'
    if cat not in ('info', 'aviso', 'novidade'):
        cat = 'info'
    role  = (data.get('role') or 'player').strip() or None
    plan  = (data.get('plan') or '').strip() or None
    ids   = get_all_user_ids(role=role, plan=plan)
    n     = broadcast_notification(ids, 'admin_broadcast',
                                   {'title': title, 'body': body, 'category': cat}, link)
    # Espelha por email para quem não descadastrou (LGPD via email_opt_in).
    # Gated pelo kill switch ADMIN_EMAIL_ENABLED (OFF por padrão).
    emailed = 0
    if bool(data.get('email')) and _admin_email_enabled():
        recipients = get_email_recipients(ids)
        emailed = send_admin_email_bulk(recipients, title, body, cat).get('sent', 0)
    return jsonify({'ok': True, 'count': n, 'emailed': emailed})


@app.route('/admin/coach/<int:coach_id>/students', methods=['GET'])
@require_admin
def admin_coach_students(coach_id: int):
    """Roster de alunos de um coach (admin) — com plano, standing de pagamento e link_status,
    para auditar as relações coach↔aluno e quem conta pra comissão."""
    from database.repositories import get_students
    return jsonify({'students': get_students(coach_id)})


@app.route('/admin/users/<int:uid>', methods=['PATCH'])
@require_admin
def admin_update_user(uid):
    data      = request.get_json() or {}
    plan      = data.get('plan')
    suspended = data.get('suspended')
    if plan is None and suspended is None:
        return jsonify({'error': 'Nenhum campo para atualizar'}), 400
    update_user_admin(uid, plan=plan, suspended=suspended)
    return jsonify({'ok': True})


@app.route('/admin/users/<int:uid>', methods=['DELETE'])
@require_admin
def admin_delete_user(uid):
    """Permanently delete a user. Requires admin password in request body."""
    data = request.get_json() or {}
    admin_password = data.get('admin_password', '').strip()
    if not admin_password:
        return jsonify({'error': 'Senha administrativa obrigatória'}), 400
    # verify admin credentials
    admin_row = get_user_by_id(g.user_id)
    if not admin_row:
        return jsonify({'error': 'Admin não encontrado'}), 403
    if not verify_password(admin_row['email'], admin_password):
        return jsonify({'error': 'Senha incorreta'}), 403
    # prevent deleting yourself
    if uid == g.user_id:
        return jsonify({'error': 'Não é possível excluir sua própria conta pelo painel admin'}), 400
    target = get_user_by_id(uid)
    if not target:
        return jsonify({'error': 'Usuário não encontrado'}), 404
    delete_user_admin(uid)
    return jsonify({'ok': True, 'deleted_id': uid})


@app.route('/admin/users/<int:uid>/clear-handle', methods=['POST'])
@require_admin
def admin_clear_handle(uid):
    """Limpa o apelido do usuário no ranking (contorna o lock one-time). Remedia
    apelido ofensivo que escapou da moderação — o usuário depois escolhe outro."""
    from database.repositories import admin_clear_leaderboard_handle
    if not get_user_by_id(uid):
        return jsonify({'error': 'Usuário não encontrado'}), 404
    admin_clear_leaderboard_handle(uid)
    return jsonify({'ok': True})


@app.route('/admin/finance/coaches', methods=['GET'])
@require_admin
def admin_finance_coaches():
    """Modelo %: comissão acumulada por coach (pagável / em carência / paga)."""
    from database.repositories import get_coaches_commission_status
    coaches = get_coaches_commission_status()
    total_payable = sum(int(c.get('payable_cents') or 0) for c in coaches)
    return jsonify({'coaches': coaches, 'total_payable_cents': total_payable})


@app.route('/admin/coach/<int:coach_id>/commission/pay', methods=['PATCH'])
@require_admin
def admin_pay_coach_commission(coach_id):
    """Marca como PAGAS as comissões pagáveis (carência vencida) do coach."""
    from database.repositories import mark_coach_commissions_paid
    total = mark_coach_commissions_paid(coach_id)
    return jsonify({'ok': True, 'paid_cents': total})


@app.route('/admin/coach/<int:coach_id>/commission', methods=['PATCH'])
@require_admin
def admin_set_coach_commission(coach_id):
    """Define a taxa de comissão % do coach (Parceiro Fundador) em basis points (3000=30%).
    Vazio/null = escada padrão por volume (15%/20%/25%)."""
    from database.repositories import set_coach_commission_rate
    data = request.get_json(silent=True) or {}
    bps  = data.get('rate_bps')
    if bps in (None, '', 'null'):
        bps = None
    else:
        try:
            bps = int(bps)
            if bps < 0 or bps > 10000:
                raise ValueError
        except (ValueError, TypeError):
            return jsonify({'error': 'rate_bps inválido (0-10000)'}), 400
    set_coach_commission_rate(coach_id, bps)
    return jsonify({'ok': True, 'rate_bps': bps})


@app.route('/admin/finance/export.csv', methods=['GET'])
@require_admin
def admin_finance_export():
    import datetime, io, csv
    from flask import Response
    from database.repositories import get_coaches_commission_status
    coaches = get_coaches_commission_status()
    buf = io.StringIO()
    w   = csv.writer(buf)
    w.writerow(['Coach', 'Pagavel (R$)', 'Em carencia (R$)', 'Pago (R$)'])
    for c in coaches:
        w.writerow([
            c.get('display_name') or c['username'],
            f"{int(c.get('payable_cents') or 0) / 100:.2f}",
            f"{int(c.get('held_cents') or 0) / 100:.2f}",
            f"{int(c.get('paid_cents') or 0) / 100:.2f}",
        ])
    resp = Response(buf.getvalue(), mimetype='text/csv')
    today = datetime.date.today().strftime('%Y-%m-%d')
    resp.headers['Content-Disposition'] = f'attachment; filename=comissoes-{today}.csv'
    return resp


@app.route('/admin/finance/overview', methods=['GET'])
@require_admin
def admin_finance_overview():
    """PAY-03: visão financeira consolidada — receita, gateways, MRR/ARR, repasses
    (pendentes/pagos) e detecção de pagamentos duplicados (saúde anti-fraude)."""
    from database.repositories import (
        admin_revenue_summary, admin_payout_totals, admin_detect_duplicate_payments,
    )
    return jsonify({
        'revenue':    admin_revenue_summary(),
        'payouts':    admin_payout_totals(),
        'duplicates': admin_detect_duplicate_payments(),
    })


@app.route('/admin/finance/cockpit', methods=['GET'])
@require_admin
def admin_finance_cockpit():
    """ADMIN-FIN: cockpit — entradas, saídas (coach+despesas), net, MRR real, dunning, ARPU."""
    from database.repositories import admin_cockpit_summary
    return jsonify(admin_cockpit_summary(request.args.get('month') or None))


@app.route('/admin/finance/calendar', methods=['GET'])
@require_admin
def admin_finance_calendar_route():
    """ADMIN-FIN: calendário — renovações entrando, repasses saindo, despesas com vencimento."""
    from database.repositories import admin_finance_calendar
    return jsonify(admin_finance_calendar(request.args.get('month') or None))


@app.route('/admin/finance/dunning', methods=['GET'])
@require_admin
def admin_finance_dunning():
    """ADMIN-FIN: receita em risco — atrasados, cancelados recentes, falhas, duplicatas."""
    from database.repositories import admin_dunning
    return jsonify(admin_dunning())


@app.route('/admin/finance/timeseries', methods=['GET'])
@require_admin
def admin_finance_timeseries():
    """ADMIN-FIN: série mensal (bruto + churn) p/ os gráficos de tendência."""
    from database.repositories import admin_revenue_timeseries
    try:
        months = max(1, min(int(request.args.get('months', 6)), 24))
    except (TypeError, ValueError):
        months = 6
    return jsonify({'series': admin_revenue_timeseries(months)})


@app.route('/admin/finance/expenses', methods=['GET', 'POST'])
@require_admin
def admin_finance_expenses():
    """ADMIN-FIN: despesas (saídas). GET lista; POST cria."""
    from database.repositories import list_expenses, create_expense
    if request.method == 'GET':
        return jsonify({'expenses': list_expenses(active_only=False)})
    d = request.get_json(silent=True) or {}
    if not d.get('category') or d.get('amount_cents') in (None, ''):
        return jsonify({'error': 'category e amount_cents são obrigatórios'}), 400
    eid = create_expense(
        category=d['category'], vendor=d.get('vendor'),
        amount_cents=int(d['amount_cents']), recurrence=d.get('recurrence', 'monthly'),
        due_day=d.get('due_day'), period=d.get('period'),
        status=d.get('status', 'forecast'), note=d.get('note'),
        currency=d.get('currency', 'BRL'))
    return jsonify({'id': eid}), 201


@app.route('/admin/finance/expenses/<int:expense_id>', methods=['PATCH', 'DELETE'])
@require_admin
def admin_finance_expense_item(expense_id: int):
    from database.repositories import update_expense, delete_expense
    if request.method == 'DELETE':
        delete_expense(expense_id)
        return jsonify({'ok': True})
    d = request.get_json(silent=True) or {}
    update_expense(expense_id, **d)
    return jsonify({'ok': True})


@app.route('/admin/payments', methods=['GET'])
@require_admin
def admin_payments():
    """PAY-03: lista TODOS os pagamentos (com pagante), filtros status/gateway/busca."""
    from database.repositories import admin_list_payments
    status  = request.args.get('status') or None
    gateway = request.args.get('gateway') or None
    search  = request.args.get('search') or None
    try:
        limit  = max(1, min(int(request.args.get('limit', 100)), 500))
        offset = max(0, int(request.args.get('offset', 0)))
    except (TypeError, ValueError):
        limit, offset = 100, 0
    return jsonify(admin_list_payments(status=status, gateway=gateway, search=search,
                                       limit=limit, offset=offset))


@app.route('/admin/logs', methods=['GET'])
@require_admin
def admin_logs():
    limit = int(request.args.get('limit', 50))
    logs  = get_admin_activity_logs(limit=limit)
    return jsonify({'logs': logs})


# ── Coach Finance — BACK-014 ──────────────────────────────────────────────────

@app.route('/coach/finance/summary', methods=['GET'])
@require_coach
def coach_finance_summary():
    return jsonify(get_coach_finance_summary(g.user_id))


@app.route('/coach/finance/students', methods=['GET'])
@require_coach
def coach_finance_students():
    students = get_coach_finance_students(g.user_id)
    return jsonify({'students': students})


@app.route('/coach/finance/history', methods=['GET'])
@require_coach
def coach_finance_history():
    history = get_coach_finance_history(g.user_id)
    return jsonify({'payments': history})


@app.route('/profile/phone', methods=['PATCH'])
@require_auth
def update_phone():
    """Atualiza o telefone de contato do perfil (opcional, único por usuário).

    A coluna se chama `whatsapp_phone` por herança do bot de drills (BACK-016), removido em
    v0.45.x por nunca ter saído do rascunho. O campo continua vivo como contato simples: o
    nome interno fica, o produto não promete nada de WhatsApp.
    """
    data  = request.get_json(force=True, silent=True) or {}
    # data.get('phone', '') NÃO cobre {"phone": null}: a chave existe com None e o default
    # não entra → None.strip() dava 500. `or ''` normaliza null/ausente pra string vazia.
    phone = (data.get('phone') or '').strip() or None
    if phone:
        # Normaliza: remove +, espaços e traços
        phone = phone.replace('+', '').replace(' ', '').replace('-', '')
        if not phone.isdigit() or len(phone) < 10 or len(phone) > 15:
            return jsonify({'error': 'Número inválido. Use formato DDI+DDD+número (ex: 5511999999999)'}), 400
        # Verifica se já está em uso por outro usuário
        existing = get_user_by_phone(phone)
        if existing and existing['id'] != g.user_id:
            return jsonify({'error': 'Número já vinculado a outro usuário'}), 409
    update_user_phone(g.user_id, phone)
    return jsonify({'ok': True, 'phone': phone})


# ── Sprint W — FEAT-11: Digest semanal ───────────────────────────────────────

@app.route('/player/digest/subscribe', methods=['POST'])
@require_auth
def digest_subscribe():
    update_digest_subscription(g.user_id, True)
    return jsonify({'ok': True, 'digest_subscribed': True})


@app.route('/player/digest/unsubscribe', methods=['POST'])
@require_auth
def digest_unsubscribe_auth():
    update_digest_subscription(g.user_id, False)
    return jsonify({'ok': True, 'digest_subscribed': False})


@app.route('/player/digest/unsubscribe', methods=['GET'])
def digest_unsubscribe_link():
    """Link de opt-out do email (não requer token JWT — usa token HMAC)."""
    uid   = request.args.get('uid', '')
    token = request.args.get('token', '')
    if not uid or not token:
        return jsonify({'error': 'Parâmetros inválidos'}), 400
    try:
        user_id = int(uid)
    except ValueError:
        return jsonify({'error': 'uid inválido'}), 400
    if not verify_unsub_token(user_id, token):
        return jsonify({'error': 'Token inválido'}), 403
    update_digest_subscription(user_id, False)
    return '<html><body style="font-family:sans-serif;text-align:center;padding:60px"><h2>Inscrição cancelada</h2><p>Você não receberá mais o digest semanal da GrindLab.</p></body></html>', 200


@app.route('/player/email/unsubscribe', methods=['GET'])
def email_unsubscribe_link():
    """Descadastro dos comunicados do admin por email (token HMAC, sem JWT)."""
    uid   = request.args.get('uid', '')
    token = request.args.get('token', '')
    if not uid or not token:
        return jsonify({'error': 'Parâmetros inválidos'}), 400
    try:
        user_id = int(uid)
    except ValueError:
        return jsonify({'error': 'uid inválido'}), 400
    if not verify_email_unsub_token(user_id, token):
        return jsonify({'error': 'Token inválido'}), 403
    update_email_opt_in(user_id, False)
    return '<html><body style="font-family:sans-serif;text-align:center;padding:60px"><h2>Descadastro concluído</h2><p>Você não receberá mais emails de comunicado da GrindLab.</p></body></html>', 200


@app.route('/admin/send-digest', methods=['POST'])
@require_admin
def admin_send_digest():
    result = run_weekly_digest()
    return jsonify(result)


@app.route('/admin/run-winback', methods=['POST'])
@require_admin
def admin_run_winback():
    """Dispara o win-back manualmente. dry_run=True (default) só devolve a prévia de quem
    receberia, sem enviar. Envio real exige SMTP configurado."""
    data    = request.get_json(silent=True) or {}
    dry_run = bool(data.get('dry_run', True))
    limit   = data.get('limit')
    limit   = int(limit) if limit else None
    if not dry_run and not os.environ.get('SMTP_HOST'):
        return jsonify({'error': 'SMTP não configurado — envio real indisponível'}), 400
    return jsonify(run_winback(dry_run=dry_run, limit=limit))


# ── Admin — Coach Applications (BACK-018) ─────────────────────────────────────

@app.route('/admin/coach-applications', methods=['GET'])
@require_admin
def admin_list_coach_applications():
    status = request.args.get('status', 'pending')
    apps   = get_coach_applications(status=status)
    return jsonify({'applications': apps})


@app.route('/admin/coach-applications/<int:app_id>/approve', methods=['POST'])
@require_admin
def admin_approve_coach_application(app_id):
    note = (request.get_json(silent=True) or {}).get('note', '')
    app  = approve_coach_application(app_id, note)
    if not app:
        return jsonify({'error': 'Candidatura não encontrada'}), 404
    base_url = os.environ.get('APP_BASE_URL', 'https://grindlabpoker.com')
    html = f"""<!DOCTYPE html><html><body style="font-family:sans-serif;background:#0f1117;color:#f1f5f9;padding:40px">
<h2 style="color:#2DD4BF">Candidatura aprovada · GrindLab</h2>
<p>Olá, <strong>{app['username']}</strong>!</p>
<p>Sua candidatura como coach foi <strong style="color:#22c55e">aprovada</strong>.</p>
<p>Você já pode fazer login e configurar seu perfil:</p>
<p><a href="{base_url}/login" style="color:#6366f1">{base_url}/login</a></p>
{f'<p style="color:#9ca3af">Nota do admin: {note}</p>' if note else ''}
</body></html>"""
    send_transactional_email(app['email'], 'Candidatura aprovada · GrindLab', html)
    return jsonify({'ok': True})


@app.route('/admin/coach-applications/<int:app_id>/reject', methods=['POST'])
@require_admin
def admin_reject_coach_application(app_id):
    note = (request.get_json(silent=True) or {}).get('note', '')
    app  = reject_coach_application(app_id, note)
    if not app:
        return jsonify({'error': 'Candidatura não encontrada'}), 404
    if note:
        base_url = os.environ.get('APP_BASE_URL', 'https://grindlabpoker.com')
        html = f"""<!DOCTYPE html><html><body style="font-family:sans-serif;background:#0f1117;color:#f1f5f9;padding:40px">
<h2 style="color:#2DD4BF">Atualização da candidatura · GrindLab</h2>
<p>Olá, <strong>{app['username']}</strong>.</p>
<p>Sua candidatura como coach não foi aprovada neste momento.</p>
<p style="color:#9ca3af">Motivo: {note}</p>
<p>Você pode entrar em contato pelo site para mais informações.</p>
</body></html>"""
        send_transactional_email(app['email'], 'Candidatura · GrindLab', html)
    return jsonify({'ok': True})


@app.route('/player/profile', methods=['GET'])
@require_auth
def get_player_profile():
    from database.repositories import get_user_demographics
    data = get_user_demographics(g.user_id)
    return jsonify(data or {})


@app.route('/player/profile', methods=['PATCH'])
@require_auth
def update_player_profile():
    from database.repositories import update_user_demographics
    body = request.get_json(silent=True) or {}
    allowed = {'birth_year', 'country', 'state_province', 'city',
                'poker_experience_years', 'main_game_type', 'usual_buyin_range'}
    fields = {k: v for k, v in body.items() if k in allowed}
    update_user_demographics(g.user_id, **fields)
    from database.repositories import get_user_demographics
    return jsonify(get_user_demographics(g.user_id) or {})


@app.route('/admin/demographics', methods=['GET'])
@require_admin
def admin_demographics():
    from database.repositories import get_demographics_aggregate
    return jsonify(get_demographics_aggregate())


@app.route('/admin/feature-usage', methods=['GET'])
@require_admin
def admin_feature_usage():
    """Analytics de uso (MVP): ranking de funcionalidades (usuários únicos + acessos)
    na janela + DAU/WAU/MAU. `?days=` (default 30, 1..365)."""
    from database.repositories import get_feature_usage_report
    days = request.args.get('days', 30, type=int) or 30
    days = max(1, min(days, 365))
    return jsonify(get_feature_usage_report(days))


@app.route('/admin/activation-funnel', methods=['GET'])
@require_admin
def admin_activation_funnel():
    """Funil de ativação: cadastrou → importou → treinou → voltou, com a conversão ENTRE
    degraus (onde o gargalo aparece) e a origem das sessões. É o instrumento do programa de
    fundadores: sem ele, o programa vira sensação em vez de aprendizado. `?days=` (1..365)."""
    from database.repositories import get_activation_funnel
    days = request.args.get('days', 30, type=int) or 30
    return jsonify(get_activation_funnel(max(1, min(days, 365))))


# ── Bot de boas-vindas dos fundadores (Telegram) ──────────────────────────────

def _telegram_enviar(chat_id: int, texto: str) -> bool:
    """Envia mensagem pelo bot. Sem token configurado, é no-op silencioso (dev/testes)."""
    token = os.environ.get('TELEGRAM_BOT_TOKEN', '').strip()
    if not token:
        return False
    try:
        import requests
        r = requests.post(f'https://api.telegram.org/bot{token}/sendMessage',
                          json={'chat_id': chat_id, 'text': texto,
                                'disable_web_page_preview': True}, timeout=10)
        if not r.ok:
            log.warning("telegram sendMessage falhou: %s %s", r.status_code, r.text[:200])
        return r.ok
    except Exception:
        log.exception("telegram sendMessage erro")
        return False


@app.route('/telegram/webhook', methods=['POST'])
def telegram_webhook():
    """Recebe os updates do Telegram.

    Endpoint PÚBLICO por natureza (o Telegram chama de fora), então a autenticação é o
    header secreto configurado no setWebhook. Sem `TELEGRAM_WEBHOOK_SECRET` no ambiente a
    rota recusa tudo: um webhook aberto seria uma porta para qualquer um mandar o bot
    escrever no grupo dos fundadores.

    Responde 200 mesmo quando ignora o update, de propósito: o Telegram reenvia o que não
    recebe 200, e um erro nosso viraria laço de reentrega.
    """
    segredo = os.environ.get('TELEGRAM_WEBHOOK_SECRET', '').strip()
    if not segredo:
        return jsonify({'error': 'not configured'}), 404
    enviado = request.headers.get('X-Telegram-Bot-Api-Secret-Token', '')
    import hmac as _hmac
    if not _hmac.compare_digest(enviado, segredo):
        log.warning("telegram webhook: segredo invalido")
        return jsonify({'error': 'forbidden'}), 403

    from leaklab.telegram_bot import (ETAPA_FIM, extrair_evento, primeira_pergunta,
                                      proximo_passo, texto_boas_vindas_grupo)
    from database.repositories import get_telegram_intro, save_telegram_intro

    bruto = request.get_json(silent=True) or {}
    ev = extrair_evento(bruto)
    if not ev or not ev.get('user_id'):
        # Ignorar em silêncio deixa cego quem depura: um evento legítimo descartado por
        # engano fica indistinguível de nenhum evento ter chegado. Loga só a FORMA do
        # update (as chaves e o tipo de chat), nunca o conteúdo das mensagens do grupo.
        msg = bruto.get('message') or {}
        log.info("telegram: update ignorado tipos=%s chat=%s servico=%s",
                 sorted(bruto.keys()),
                 (msg.get('chat') or {}).get('type'),
                 sorted(k for k in msg
                        if k.endswith('_chat_member') or k.endswith('_chat_members')))
        return jsonify({'ok': True, 'ignorado': True})

    try:
        if ev['tipo'] == 'entrou_no_grupo':
            usuario_bot = os.environ.get('TELEGRAM_BOT_USERNAME', '').strip().lstrip('@')
            _telegram_enviar(ev['chat_id'], texto_boas_vindas_grupo(ev['nome'], usuario_bot))
            return jsonify({'ok': True, 'acao': 'boas_vindas'})

        # As perguntas só acontecem na conversa privada. No grupo o bot fica quieto, senão
        # vira ruído em cima da conversa dos fundadores, que é o que o grupo existe para ter.
        if ev.get('chat_tipo') != 'private':
            return jsonify({'ok': True, 'ignorado': 'grupo'})

        intro = get_telegram_intro(ev['user_id'])
        etapa = int((intro or {}).get('etapa') or 0)
        texto = ev['texto'] or ''
        if texto.strip().startswith('/start'):
            # /start não é resposta de pergunta nenhuma: só abre (ou reabre) a conversa.
            if not intro:
                save_telegram_intro(ev['user_id'], ev['chat_id'], ev['nome'], 0)
            _telegram_enviar(ev['chat_id'],
                             primeira_pergunta() if etapa < ETAPA_FIM
                             else 'Você já respondeu as três. Obrigado.')
            return jsonify({'ok': True, 'acao': 'start'})

        passo = proximo_passo(etapa, texto,
                              os.environ.get('TELEGRAM_GROUP_INVITE', '').strip())
        save_telegram_intro(ev['user_id'], ev['chat_id'], ev['nome'],
                            passo['nova_etapa'], passo['gravar'], concluido=passo['fim'])
        _telegram_enviar(ev['chat_id'], passo['responder'])
        return jsonify({'ok': True, 'etapa': passo['nova_etapa']})
    except Exception:
        # 200 mesmo no erro: 5xx faz o Telegram reenviar o mesmo update sem parar.
        log.exception("telegram webhook: falha tratando update")
        return jsonify({'ok': False}), 200


@app.route('/admin/telegram/intros', methods=['GET'])
@require_admin
def admin_telegram_intros():
    """As respostas de entrada. A terceira pergunta é o insumo de roadmap mais direto que
    o programa produz: é o jogador dizendo, com as palavras dele, o que o incomoda."""
    from database.repositories import list_telegram_intros
    return jsonify({'intros': list_telegram_intros()})


@app.route('/player/founder/apply', methods=['POST'])
@require_auth
def player_founder_apply():
    """Candidatura ao programa de fundadores, para quem já tem conta.

    Idempotente: clicar de novo devolve `ja_estava: True` sem reescrever a data. Reescrever
    jogaria o jogador para o fim da fila por ter clicado duas vezes, e a ordem de chegada é
    o critério que a divulgação promete."""
    from database.repositories import apply_as_founder, get_user_by_id
    novo = apply_as_founder(g.user_id)
    u = get_user_by_id(g.user_id) or {}
    return jsonify({'ok': True, 'ja_estava': not novo,
                    'candidatado_em': u.get('founder_applied_at'),
                    'ja_e_fundador': u.get('plan_source') == 'founder'})


@app.route('/player/founder/status', methods=['GET'])
@require_auth
def player_founder_status():
    """O que a página /fundadores mostra para quem está logado: já se candidatou? já entrou?"""
    from database.repositories import get_user_by_id
    u = get_user_by_id(g.user_id) or {}
    return jsonify({
        'candidatado_em': u.get('founder_applied_at'),
        'ja_e_fundador':  u.get('plan_source') == 'founder',
        'expira_em':      u.get('plan_expires_at') if u.get('plan_source') == 'founder' else None,
    })


@app.route('/admin/founders/candidatos', methods=['GET'])
@require_admin
def admin_founder_candidates():
    """Fila de candidatos, na ordem em que chegaram — a ordem É a promessa."""
    from database.repositories import get_founder_candidates
    limit = request.args.get('limit', 200, type=int) or 200
    return jsonify({'candidatos': get_founder_candidates(max(1, min(limit, 500)))})


@app.route('/admin/founders', methods=['GET'])
@require_admin
def admin_founders():
    """Painel do programa de fundadores: o que cada um recebeu, usou e DEVOLVEU.

    As três colunas juntas é que respondem a pergunta que interessa no fim do ciclo —
    renovar ou não. Uso sozinho mede engajamento, não o trato."""
    from database.repositories import get_founder_program
    return jsonify(get_founder_program())


@app.route('/admin/founders', methods=['POST'])
@require_admin
def admin_grant_founders():
    """Concede Pro de fundador em lote. `{user_ids: [...], meses: 6}`.

    Assinante pagante é PULADO, não sobrescrito — e volta na resposta, para a concessão
    não sumir com o caso em silêncio."""
    from database.repositories import grant_founder
    data = request.get_json(silent=True) or {}
    ids = data.get('user_ids') or []
    if not isinstance(ids, list) or not ids:
        return jsonify({'error': 'user_ids (lista não vazia) é obrigatório'}), 400
    try:
        ids = [int(i) for i in ids]
    except (TypeError, ValueError):
        return jsonify({'error': 'user_ids deve conter inteiros'}), 400
    meses = data.get('meses', 6)
    try:
        meses = int(meses)
    except (TypeError, ValueError):
        meses = 6
    if not 1 <= meses <= 24:
        return jsonify({'error': 'meses deve estar entre 1 e 24'}), 400
    res = grant_founder(ids, meses)
    log.info("founders concedidos=%s pulados=%s ate=%s",
             len(res['concedidos']), len(res['pulados']), res['expira_em'])
    return jsonify({'ok': True, **res})


@app.route('/admin/founders/<int:uid>', methods=['DELETE'])
@require_admin
def admin_revoke_founder(uid: int):
    """Tira do programa (volta a free). Só afeta quem É fundador."""
    from database.repositories import revoke_founder
    if not revoke_founder(uid):
        return jsonify({'error': 'usuário não está no programa de fundadores'}), 404
    return jsonify({'ok': True})


@app.route('/player/preferences', methods=['GET'])
@require_auth
def get_player_preferences():
    from database.repositories import get_user_preferences
    return jsonify(get_user_preferences(g.user_id))


@app.route('/player/preferences', methods=['PATCH'])
@require_auth
def save_player_preferences():
    from database.repositories import save_user_preferences
    body = request.get_json(silent=True) or {}
    layout = body.get('dashboard_layout')
    if layout is None:
        return jsonify({'error': 'dashboard_layout required'}), 400
    save_user_preferences(g.user_id, layout)
    return jsonify({'ok': True})


@app.route('/player/onboarding/complete', methods=['POST'])
@require_auth
def complete_onboarding():
    from database.repositories import set_onboarding_completed
    set_onboarding_completed(g.user_id)
    return jsonify({'ok': True})


@app.route('/admin/support-tickets/count', methods=['GET'])
@require_admin
def admin_support_tickets_count():
    from database.schema import get_conn as _gc
    conn = _gc()
    try:
        row = conn.execute(
            "SELECT COUNT(*) AS n FROM support_tickets WHERE status = 'open'"
        ).fetchone()
        return jsonify({'open': row['n'] if row else 0})
    finally:
        conn.close()


@app.route('/admin/support-tickets', methods=['GET'])
@require_admin
def admin_support_tickets():
    from database.schema import get_conn as _gc
    conn = _gc()
    try:
        rows = conn.execute("""
            SELECT st.id, st.user_id, u.username, st.category, st.subject,
                   st.message, st.status, st.admin_reply, st.replied_at, st.created_at
            FROM support_tickets st
            LEFT JOIN users u ON u.id = st.user_id
            ORDER BY st.created_at DESC
            LIMIT 200
        """).fetchall()
        return jsonify({'tickets': [dict(r) for r in rows]})
    finally:
        conn.close()


@app.route('/admin/support-tickets/<int:ticket_id>/reply', methods=['POST'])
@require_admin
def admin_support_reply(ticket_id):
    from database.schema import get_conn as _gc
    data  = request.get_json(force=True) or {}
    reply = str(data.get('reply', '')).strip()
    if not reply:
        return jsonify({'error': 'Resposta obrigatória'}), 400
    conn = _gc()
    try:
        conn.execute(
            "UPDATE support_tickets SET admin_reply = ?, status = 'replied', replied_at = datetime('now') WHERE id = ?",
            (reply, ticket_id)
        )
        conn.commit()
    finally:
        conn.close()
    return jsonify({'ok': True})


# ── GTO Integration ───────────────────────────────────────────────────────────

@app.route('/replay/<int:decision_id>/gto', methods=['GET'])
@require_auth
def get_decision_gto(decision_id):
    """Retorna análise GTO completa para uma decisão: estratégia, exploitability, frequência da jogada."""
    from database.repositories import get_decision_spot, get_gto_node
    from leaklab.gto_utils import compute_spot_hash
    import json as _json

    dec = get_decision_spot(decision_id, g.user_id)   # anti-IDOR: só a própria decisão
    if not dec:
        return jsonify({'error': 'Decisão não encontrada'}), 404

    street    = dec.get('street') or ''
    position  = dec.get('position') or ''
    board_raw = dec.get('board') or '[]'
    hand_raw  = dec.get('hero_cards') or ''
    stack_bb  = float(dec.get('stack_bb') or 30.0)
    facing_bb = float(dec.get('facing_bet') or 0.0)
    # Stored GTO analysis (set by the hand worker)
    stored_gto_action = dec.get('gto_action') or ''
    stored_gto_label  = dec.get('gto_label') or ''

    if not street or not position:
        return jsonify({'found': False, 'reason': 'spot_incomplete'}), 404

    try:
        board = _json.loads(board_raw) if isinstance(board_raw, str) else (board_raw or [])
    except Exception:
        board = []

    # Parse hero cards: "Jc Th" (space-sep) or "JcTh" (concatenated 2-char pairs)
    if isinstance(hand_raw, str) and hand_raw.strip():
        _raw = hand_raw.strip()
        if ' ' in _raw:
            hero_hand = _raw.split()
        else:
            hero_hand = [_raw[i:i+2] for i in range(0, len(_raw), 2)] if len(_raw) % 2 == 0 else []
    else:
        hero_hand = []

    # O banco guarda o board COMPLETO; o hash usa a fatia da street. Fonte única em gto_utils:
    # a cópia local desta regra é o que faltou no enfileiramento e produziu hashes que nunca casavam.
    from leaklab.gto_utils import board_for_street
    board_for_hash = board_for_street(board, street)

    player_action = (dec.get('action_taken') or '').lower()

    def _valid_node_replayer(n):
        """Rejeita nó se street ou board não batem — captura colisões de hash SHA256[:16]."""
        if not n:
            return None
        if n.get('street', '').lower() != street.lower():
            return None
        try:
            node_board = sorted(_json.loads(n.get('board') or '[]') if isinstance(n.get('board'), str) else (n.get('board') or []))
            if board_for_hash and node_board and node_board != sorted(board_for_hash):
                return None
        except Exception:
            pass
        # Guardas de FORMA do menu (RC-5/6, 17/08) — os mesmos do drill: vs-aposta não pode
        # ter 'check' no menu; sem aposta postflop não pode ter 'fold'.
        _acts = set()
        try:
            _sj = n.get('strategy_json')
            if _sj:
                _acts = {str(k).lower() for k in (_json.loads(_sj) if isinstance(_sj, str) else _sj).keys()}
        except Exception:
            _acts = set()
        if not _acts and n.get('gto_action'):
            _acts = {str(n['gto_action']).lower()}
        if facing_bb > 0 and 'check' in _acts:
            return None
        if facing_bb == 0 and street.lower() != 'preflop' and 'fold' in _acts:
            return None
        return n

    # ── Node lookup: multiple fallback strategies ────────────────────────────
    # RC-3 (17/08): mesmas variantes de pot_type e mesmo guarda de coerência do drill
    # (`_hashes_da_linha` + `_no_contradiz_o_gravado`) — fonte única; a cópia sem pot_type
    # aqui resolvia nó SRP para pote 3-bet.
    node = None
    for _h in _hashes_da_linha(street, position, board_for_hash, hero_hand, stack_bb,
                               facing_bb, dec.get('is_3bet')):
        _n = _valid_node_replayer(get_gto_node(_h))
        if _n and not _no_contradiz_o_gravado(_n, stored_gto_action):
            node = _n
            break
    # fallback d (get_gto_node_by_spot) removido: hash algorithm divergente → falsos matches
    # e) APROXIMAÇÃO DEEP: postflop fundo sem nó no stack real → tenta o nó capado a 30bb (HU
    #    tratável). A AÇÃO transfere bem; sizing/comprometimento podem diferir → marca aproximação.
    _approx_stack = None
    if not node and street != 'preflop' and stack_bb > _DEEP_APPROX_MIN_BB:
        for _h in _hashes_da_linha(street, position, board_for_hash, hero_hand,
                                   _DEEP_APPROX_STACK_BB, facing_bb, dec.get('is_3bet')):
            _n = _valid_node_replayer(get_gto_node(_h))
            if _n and not _no_contradiz_o_gravado(_n, stored_gto_action):
                node = _n
                break
        if node:
            _approx_stack = _DEEP_APPROX_STACK_BB

    # ── Build strategy from node (if found) ─────────────────────────────────
    strategy = []
    exploit  = None
    top_action = stored_gto_action  # default to stored value
    spot_hash_out = _h if '_h' in dir() else ''

    if node:
        exploit = node.get('exploitability_pct')
        strategy_raw = {}
        if node.get('strategy_json'):
            try:
                strategy_raw = _json.loads(node['strategy_json'])
            except Exception:
                pass

        if strategy_raw:
            for action_key, data in strategy_raw.items():
                strategy.append({
                    'action':    action_key,
                    'label':     _gto_action_label(action_key),
                    'frequency': round(float(data.get('frequency', 0)), 4),
                    'combos':    data.get('combos'),
                })
            strategy.sort(key=lambda x: x['frequency'], reverse=True)
        elif node.get('gto_action'):
            strategy = [{
                'action':    node['gto_action'],
                'label':     _gto_action_label(node['gto_action']),
                'frequency': float(node.get('gto_freq') or 1.0),
                'combos':    None,
            }]

        if strategy:
            top_action = strategy[0]['action']
        spot_hash_out = node.get('spot_hash', '')

    # Postflop HAND-AWARE: a strategy_json do nó é a RANGE agregada (ex.: trinca exibida como
    # 'fold' porque a range folda muito). Tenta a estratégia DA MÃO; se a mão está fora da
    # cobertura (off-tree), mantém a agregada mas marca aproximação (gto_off_tree).
    hand_aware_used = False
    if node and street != 'preflop' and hero_hand and node.get('tree_hash'):
        try:
            from leaklab.gto_solver import hand_view_for_spot
            hv = hand_view_for_spot(node['tree_hash'], board_for_hash, hero_hand)
            if hv and hv.get('actions'):
                strategy = sorted([
                    {'action': _a, 'label': _gto_action_label(_a),
                     'frequency': round(float(_v.get('frequency', 0) or 0), 4), 'combos': None}
                    for _a, _v in hv['actions'].items()
                ], key=lambda x: x['frequency'], reverse=True)
                if strategy:
                    top_action = strategy[0]['action']
                hand_aware_used = True
        except Exception:
            pass

    # Preflop override: GTO nodes store aggregate range strategy (e.g. "HJ opens 28%"),
    # not hand-specific strategy. For KK, the node says "fold 72%" (72% of all HJ hands fold)
    # which is misleading. Use analyze_preflop for the hand-specific recommendation instead.
    if street == 'preflop' and hero_hand:
        try:
            from leaklab.preflop_gto_ranges import analyze_preflop
            from leaklab.gto_utils import hand_to_type
            h_type = hand_to_type(hero_hand)
            if h_type:
                pf = analyze_preflop(
                    # a decisao guarda o torneio; o torneio e que sabe se e PKO
                    is_pko       = bool(dec.get('is_pko')),
                    position     = position,
                    hero_hand_type = h_type,
                    stack_bb     = stack_bb,
                    action_taken = player_action,
                    facing_size  = facing_bb,
                    vs_position  = (dec.get('villain_position') or ''),
                    n_players    = dec.get('num_players'),
                    # faces_squeeze precisa do nº de raises enfrentados (coluna armazenada);
                    # sem isto, squeeze cai em vs_rfi e sugere call largo.
                    facing_raises = int(dec.get('preflop_raises_faced') or 0),
                    is_3bet_pot   = bool(dec.get('is_3bet')),
                    # Mesmos dois que faltavam no /replay: separam a carta de 3-bet PEQUENO da
                    # carta de JAM. Sem eles, um all-in e gradeado pelo no de raise sized.
                    facing_to_bb  = float(dec.get('facing_to_call_bb') or 0),
                    facing_allin  = facing_allin_row(dec),
                    hero_was_aggressor = bool(dec.get('hero_was_aggressor')),
                    facing_limp        = bool(dec.get('facing_limp')),
                )
                if pf.get('available') and pf.get('recommended_actions'):
                    top_action = pf['recommended_actions'][0]
        except Exception:
            pass

    # Sanity: jam dominante (>50%) com SPR > 8 e sem aposta = nó incorreto.
    # Overbet de mais de 8x o pote nunca é ação dominante no GTO — descarta nó.
    if strategy and facing_bb == 0:
        top_freq_action = (strategy[0].get('action') or '').lower()
        top_freq_val    = float(strategy[0].get('frequency') or 0)
        if top_freq_action in ('shove', 'jam', 'allin', 'all-in', 'all_in') and top_freq_val > 0.5:
            pot_bb_val = float(dec.get('pot_size') or 0)
            if pot_bb_val > 0 and stack_bb > 0 and stack_bb / pot_bb_val > 8:
                # Nó suspeito — ignorar strategy_json e usar stored_gto_action
                strategy = []
                node = None
                _approx_stack = None   # nó approx descartado pelo guard de SPR → não rotula aproximação

    # ── Fallback: use stored gto_action from decisions table (no node found) ─
    if not strategy and stored_gto_action:
        strategy = [{
            'action':    stored_gto_action,
            'label':     _gto_action_label(stored_gto_action),
            'frequency': 1.0,
            'combos':    None,
        }]
        top_action = stored_gto_action

    if not strategy:
        return jsonify({'found': False, 'spot_hash': spot_hash_out}), 404

    # ── Frequência GTO da jogada do herói ────────────────────────────────────
    player_freq = _player_action_freq(player_action, strategy)
    agreement   = player_freq >= 0.15 if player_action else None

    # OFF-TREE: postflop exibindo distribuição não hand-aware (range agregada ou stored) → a
    # recomendação não é da mão; o card mostra "≈ aproximação" em vez de veredito autoritativo.
    # SÓ quando a estratégia é MISTA: ação ~pura (top >= 90%) vale p/ toda mão (sem ambiguidade),
    # então não marca off-tree (evita "fora da cobertura" + "Call 100%" ao mesmo tempo).
    _top_freq = float(strategy[0].get('frequency') or 0) if strategy else 0.0
    gto_off_tree = (street != 'preflop' and bool(strategy) and not hand_aware_used and _top_freq < 0.90)
    # MULTIWAY: postflop com 2+ oponentes vivos → o solver é HU-only, não cobre. Marca aproximação
    # multiway p/ o card não apresentar veredito GTO autoritativo onde não há cobertura.
    gto_multiway = (street != 'preflop' and int(dec.get('n_active_opponents') or 0) >= 2)

    return jsonify({
        'found':               True,
        'spot_hash':           spot_hash_out,
        'street':              street,
        'position':            position,
        'stack_bb':            stack_bb,
        'facing_bb':           facing_bb,
        'gto_action':          top_action,
        'gto_action_label':    _gto_action_label(top_action),
        'gto_freq':            float(node['gto_freq'] if node and node.get('gto_freq') else 0.0),
        'ev_diff':             node.get('ev_diff') if node else None,
        'exploitability_pct':  exploit,
        'source':              node.get('source') if node else 'stored',
        'player_action':       player_action,
        'player_action_label': _gto_action_label(player_action) if player_action else None,
        'player_action_freq':  player_freq,
        'agreement':           agreement,
        'strategy':            strategy,
        'is_aggregate':        bool(node and node.get('is_aggregate')),
        'gto_note':            'range_distribution' if node and node.get('is_aggregate') else None,
        'gto_off_tree':        gto_off_tree,   # postflop sem hand-aware → "≈ aproximação"
        'gto_multiway':        gto_multiway,   # postflop multiway (solver HU-only) → "≈ multiway"
        'gto_approx_stack':    _approx_stack,  # nó capado p/ spot deep → "≈ aproximação (solver a Xbb)"
        'hand_aware':          hand_aware_used,
    })


def _gto_action_label(action_key: str) -> str:
    """Converte chave interna do solver para label legível."""
    if not action_key:
        return ''
    _MAP = {
        'check':       'CHECK',
        'call':        'CALL',
        'fold':        'FOLD',
        'allin':       'ALL-IN',
        'all-in':      'ALL-IN',
        'bet_33pct':   'BET 33%',
        'bet_50pct':   'BET 50%',
        'bet_66pct':   'BET 66%',
        'bet_75pct':   'BET 75%',
        'bet_100pct':  'BET POT',
        'bet_125pct':  'BET 125%',
        'raise_2x':    'RAISE 2×',
        'raise_3x':    'RAISE 3×',
        'raise_4x':    'RAISE 4×',
        'jam':         'ALL-IN',
        'bet':         'BET',
        'raise':       'RAISE',
    }
    key = action_key.lower().strip()
    if key in _MAP:
        return _MAP[key]
    # Genérico: capitaliza e substitui underscores
    return key.replace('_', ' ').upper()


def _player_action_freq(player_action: str, strategy: list) -> float:
    """Retorna a frequência GTO da ação jogada pelo herói (fuzzy match)."""
    if not player_action or not strategy:
        return 0.0
    pa = player_action.lower()
    # Match exato
    for s in strategy:
        if s['action'].lower() == pa:
            return s['frequency']
    # Fuzzy: fold/call/check direto
    for s in strategy:
        skey = s['action'].lower()
        if pa in ('fold',)  and skey == 'fold':  return s['frequency']
        if pa in ('call',)  and skey == 'call':  return s['frequency']
        if pa in ('check',) and skey == 'check': return s['frequency']
    # Fuzzy: qualquer aposta/raise quando player apostou
    if pa in ('bet', 'raise', 'jam', 'allin', 'all-in'):
        bet_freqs = [s['frequency'] for s in strategy if any(
            k in s['action'].lower() for k in ('bet', 'raise', 'allin', 'jam')
        )]
        return sum(bet_freqs) if bet_freqs else 0.0
    return 0.0


@app.route('/admin/gto/nodes', methods=['POST'])
@require_admin
def admin_gto_insert():
    """Bulk insert de nós GTO pelo bot. Requer token admin."""
    from database.repositories import insert_gto_nodes
    body  = request.get_json(force=True) or {}
    nodes = body.get('nodes', [])
    if not isinstance(nodes, list) or not nodes:
        return jsonify({'error': 'nodes deve ser uma lista não vazia'}), 400
    if len(nodes) > 500:
        return jsonify({'error': 'Máximo de 500 nós por request'}), 400
    try:
        inserted = insert_gto_nodes(nodes)
        return jsonify({'inserted': inserted})
    except Exception as e:
        log.exception('admin_gto_insert error')
        return jsonify({'error': str(e)}), 500


@app.route('/admin/gto/stats', methods=['GET'])
@require_admin
def admin_gto_stats():
    """Estatísticas da base gto_nodes."""
    from database.repositories import get_gto_stats
    return jsonify(get_gto_stats())


@app.route('/admin/gto/missing-spots', methods=['GET'])
@require_admin
def admin_gto_missing_spots():
    """Spots com maior frequência de erro que ainda não têm nó GTO."""
    from database.repositories import get_missing_gto_spots
    limit = request.args.get('limit', 100, type=int)
    limit = min(limit, 500)
    return jsonify({'spots': get_missing_gto_spots(limit)})


@app.route('/preflop-ranges', methods=['GET'])
@require_auth
# A pagina /ranges (28/08) trocou o padrao de uso: era 1 chamada por sessao de replayer, virou 1
# por clique numa barra de 14 stacks x 9 posicoes. Medido pela revisao de seguranca: 30 requisicoes
# seguidas custam 2,9s de CPU do worker e 1 MB de egress, e o conteudo e 100% deterministico.
#
# O TETO E 600, nao 120, e o numero saiu de medir o consumidor legitimo mais pesado antes de
# escolher: `capturar_torneio_para_auditoria.py` consulta a matriz por decisao preflop e faz 433
# chamadas em rajada num torneio de 600 decisoes. Com 120/min o portao de aceite -- a rede que
# roda a cada deploy -- passaria a levar 429 de si mesmo. Limite que quebra uso legitimo vira
# limite desligado na semana seguinte.
@limiter.limit("600 per minute")
def preflop_ranges():
    """
    Retorna ranges GTO de preflop por posição e stack depth.
    Query params: position (ex: BTN), stack_bb (float, default 30)

    Response:
      { position, stack_bb, stack_bucket,
        rfi: { hands: [str], pct: float } | null,
        vs_rfi: { [opener]: { call: [str], raise3bet: [str], pct_play: float } },
        vs_3bet: { hands_4bet: [str], hands_call: [str], pct_continua: float } | null }
    """
    from leaklab.preflop_gto_ranges import _load, balde_rfi, _expand_range, _norm_pos

    position = request.args.get('position', 'BTN')
    # `float()` cru devolvia 500 em `stack_bb=abc` e, pior, ACEITAVA `NaN` e `Infinity`: os dois
    # saturavam no balde de 100bb e a resposta saia 200 dizendo `stack_bucket: "100bb"` para o
    # stack que o cliente pediu, sem nenhum sinal. E `"stack_bb": NaN` nem e JSON valido (RFC
    # 8259), entao o proprio `JSON.parse` do front quebrava num 200.
    #
    # Recusar, e NAO fazer clamp para a faixa valida: clamp transformaria a ameaca em entrega
    # silenciosa da carta errada -- o conserto causando o dano que o bug so ameacava (regra 7).
    try:
        stack_bb = float(request.args.get('stack_bb', 30.0))
    except (TypeError, ValueError):
        return jsonify({'error': 'stack_bb invalido'}), 400
    if not math.isfinite(stack_bb) or stack_bb <= 0:
        return jsonify({'error': 'stack_bb precisa ser um numero finito e positivo'}), 400

    pos    = _norm_pos(position)
    bucket = balde_rfi(stack_bb)   # este endpoint mostra a RFI; ver `balde_rfi`
    data   = _load()
    bk     = data.get('ranges', {}).get(bucket, {})

    # RFI — formato v3 GW (open_pct + raise_hands + allin_hands) ou v2 (pct + hands)
    rfi_raw = bk.get('RFI', {}).get(pos)
    rfi = None
    if rfi_raw:
        if 'open_pct' in rfi_raw or 'raise_hands' in rfi_raw:
            # v3 GW master — usa hand_freqs exato quando disponível
            raise_set = _expand_range(rfi_raw.get('raise_hands', ''))
            allin_set = _expand_range(rfi_raw.get('allin_hands', ''))
            open_pct  = float(rfi_raw.get('open_pct', 0))
            raise_pct = float(rfi_raw.get('raise_pct', 0))
            allin_pct = float(rfi_raw.get('allin_pct', 0))

            all_hands_seen = raise_set | allin_set
            hand_freqs_raw = rfi_raw.get('hand_freqs', {}) or {}
            freqs = {}

            # 1. hand_freqs exato do JSON v3 (GW): mapear códigos brutos
            for hand, hf in hand_freqs_raw.items():
                mapped = {'fold': 0.0, 'call': 0.0, 'raise': 0.0, 'allin': 0.0}
                for code, f in hf.items():
                    if code == 'F':                  mapped['fold']  += float(f)
                    elif code == 'C':                mapped['call']  += float(f)
                    elif code == 'RAI':              mapped['allin'] += float(f)
                    elif code.startswith('R'):       mapped['raise'] += float(f)
                freqs[hand] = {k: round(v, 4) for k, v in mapped.items()}

            # 2. Fallback split simulado pras mãos nos sets sem hand_freqs
            for hand in sorted(all_hands_seen):
                if hand in freqs: continue
                w_raise = raise_pct if hand in raise_set else 0
                w_allin = allin_pct if hand in allin_set else 0
                total = w_raise + w_allin
                if total == 0:
                    n = sum([hand in raise_set, hand in allin_set]) or 1
                    freqs[hand] = {'raise': (1/n) if hand in raise_set else 0,
                                   'allin': (1/n) if hand in allin_set else 0,
                                   'call': 0, 'fold': 0}
                else:
                    freqs[hand] = {'raise': round(w_raise/total, 4),
                                   'allin': round(w_allin/total, 4),
                                   'call': 0, 'fold': 0}
            rfi = {
                'hands':       sorted(all_hands_seen),
                'pct':         round(open_pct, 4),
                'raise_pct':   round(raise_pct, 4),
                'allin_pct':   round(allin_pct, 4),
                'frequencies': freqs,
            }
        else:
            # v2 legacy
            hands_set = _expand_range(rfi_raw.get('hands', ''))
            rfi = {
                'hands':       sorted(hands_set),
                'pct':         float(rfi_raw.get('pct', 0)),
                'frequencies': {h: {'raise': 1.0, 'call': 0, 'allin': 0, 'fold': 0} for h in hands_set},
            }

    # vs_RFI — retorna frequencies por mão estilo GTO Wizard (multi-cor proporcional)
    vs_rfi_raw = bk.get('vs_RFI', {})
    vs_rfi = {}
    for opener_key, defenders in vs_rfi_raw.items():
        defender = defenders.get(pos)
        if not defender:
            continue
        opener_label = opener_key.replace('_open', '')

        # Formato v3 GW (preferido): pcts globais + hands separados por ação
        call_set  = _expand_range(defender.get('call_hands', ''))
        raise_set = _expand_range(defender.get('raise_hands', ''))
        allin_set = _expand_range(defender.get('allin_hands', ''))

        # Fallback formato antigo (sem separação por ação)
        if not call_set and not raise_set and not allin_set:
            all_hands = _expand_range(defender.get('hands', ''))
            acoes     = defender.get('acoes', [])
            is_3bet   = 'THREBET' in acoes or '3BET' in [a.upper() for a in acoes]
            if is_3bet: raise_set = all_hands
            else:       call_set  = all_hands

        # Pcts globais (default GW v3, fallback pra v2)
        call_pct  = float(defender.get('call_pct') or 0)
        raise_pct = float(defender.get('raise_pct') or 0)
        allin_pct = float(defender.get('allin_pct') or 0)
        if call_pct + raise_pct + allin_pct == 0:
            # v2 antigo: usa pct_play como total não-fold (heurística simples)
            pct_total = float(defender.get('pct_play', 0))
            if all(s == set() for s in [call_set, raise_set, allin_set]):
                pass
            else:
                # split proporcional por tamanho dos sets (aproximação grosseira)
                total_combos = sum(len(s) for s in [call_set, raise_set, allin_set]) or 1
                call_pct  = pct_total * len(call_set)  / total_combos
                raise_pct = pct_total * len(raise_set) / total_combos
                allin_pct = pct_total * len(allin_set) / total_combos

        pct_play = call_pct + raise_pct + allin_pct

        # Construir frequencies por mão. Prefere hand_freqs exato do JSON v3 (GW Wizard
        # — soma 1.0 com fold). Fallback: split proporcional pelos pcts globais.
        all_hands_seen = call_set | raise_set | allin_set
        hand_freqs_raw = defender.get('hand_freqs', {}) or {}
        frequencies = {}

        # 1. Mãos com hand_freqs exato (GW Wizard): mapear códigos brutos pra ações
        for hand, freqs in hand_freqs_raw.items():
            mapped = {'fold': 0.0, 'call': 0.0, 'raise': 0.0, 'allin': 0.0}
            for code, f in freqs.items():
                if code == 'F':       mapped['fold']  += float(f)
                elif code == 'C':     mapped['call']  += float(f)
                elif code == 'RAI':   mapped['allin'] += float(f)
                elif code.startswith('R'):  mapped['raise'] += float(f)
            frequencies[hand] = {k: round(v, 4) for k, v in mapped.items()}

        # 2. Mãos nos sets mas SEM hand_freqs (edge case): fallback pro split simulado
        for hand in all_hands_seen:
            if hand in frequencies:
                continue
            in_call  = hand in call_set
            in_raise = hand in raise_set
            in_allin = hand in allin_set
            w_call  = call_pct  if in_call  else 0
            w_raise = raise_pct if in_raise else 0
            w_allin = allin_pct if in_allin else 0
            total_w = w_call + w_raise + w_allin
            if total_w == 0:
                n = sum([in_call, in_raise, in_allin]) or 1
                frequencies[hand] = {
                    'call':  (1/n) if in_call  else 0,
                    'raise': (1/n) if in_raise else 0,
                    'allin': (1/n) if in_allin else 0,
                    'fold':  0,
                }
            else:
                frequencies[hand] = {
                    'call':  round(w_call  / total_w, 4),
                    'raise': round(w_raise / total_w, 4),
                    'allin': round(w_allin / total_w, 4),
                    'fold':  0,
                }

        vs_rfi[opener_label] = {
            'raise3bet':   sorted(raise_set | allin_set),  # legacy field (mantém compat)
            'call':        sorted(call_set),
            'allin':       sorted(allin_set),
            'pct_play':    round(pct_play, 4),
            'call_pct':    round(call_pct, 4),
            'raise_pct':   round(raise_pct, 4),
            'allin_pct':   round(allin_pct, 4),
            'acoes':       defender.get('acoes', []),
            'hands':       sorted(all_hands_seen),
            'frequencies': frequencies,
        }

    # Helper: monta grade de ação (frequencies por mão + sets + pcts) a partir de
    # hand_freqs (formato v3 GW). Usado por vs_3bet e squeeze, cujos *_hands strings
    # vêm vazios — a range real está em hand_freqs. O RangeGrid colore por frequencies.
    def _grid_from_freqs(d):
        freqs = {}
        for hand, hf in (d.get('hand_freqs') or {}).items():
            m = {'fold': 0.0, 'call': 0.0, 'raise': 0.0, 'allin': 0.0}
            for code, f in hf.items():
                if code == 'F':            m['fold']  += float(f)
                elif code == 'C':          m['call']  += float(f)
                elif code == 'RAI':        m['allin'] += float(f)
                elif code.startswith('R'): m['raise'] += float(f)
            freqs[hand] = {k: round(v, 4) for k, v in m.items()}
        call_set  = _expand_range(d.get('call_hands', ''))  or {h for h, f in freqs.items() if f['call']  > 0.01}
        raise_set = _expand_range(d.get('raise_hands', '')) or {h for h, f in freqs.items() if f['raise'] > 0.01}
        allin_set = _expand_range(d.get('allin_hands', '')) or {h for h, f in freqs.items() if f['allin'] > 0.01}
        n = len(freqs) or 1
        call_pct  = float(d.get('call_pct')  or 0) or sum(f['call']  for f in freqs.values()) / n
        raise_pct = float(d.get('raise_pct') or 0) or sum(f['raise'] for f in freqs.values()) / n
        allin_pct = float(d.get('allin_pct') or 0) or sum(f['allin'] for f in freqs.values()) / n
        return {
            'raise3bet':   sorted(raise_set | allin_set),
            'call':        sorted(call_set),
            'allin':       sorted(allin_set),
            'pct_play':    round(call_pct + raise_pct + allin_pct, 4),
            'call_pct':    round(call_pct, 4),
            'raise_pct':   round(raise_pct, 4),
            'allin_pct':   round(allin_pct, 4),
            'hands':       sorted(call_set | raise_set | allin_set),
            'frequencies': freqs,
        }

    # Busca a section[pos] com fallback de bucket (mesma tabela do analyze_preflop) —
    # senão spots como 17bb/14bb (sparse) davam None mesmo havendo dado adjacente.
    _vs3_fallbacks = {'14bb': ['10bb', '20bb'], '17bb': ['20bb', '14bb'],
                      '40bb': ['30bb', '50bb'], '60bb': ['50bb', '75bb'],
                      '75bb': ['100bb', '50bb']}
    # De onde CADA secao veio de fato. Ate 28/08 o fallback servia o balde vizinho e a resposta
    # seguia dizendo `stack_bucket: <o pedido>` -- no replayer isso era invisivel (o stack nao era
    # selecionavel), e a pagina /ranges transformou em contradicao de um clique: pedir squeeze a
    # 17bb e a 14bb devolvia a MESMA grade com rotulos diferentes. Medido: 6 spots de squeeze.
    #
    # Substituicao silenciosa e a mesma familia da ausencia muda: o produto responde, e o que ele
    # responde nao e o que foi perguntado.
    substituicao = {}

    def _section_for_pos(section_name):
        for bk_try in [bucket] + _vs3_fallbacks.get(bucket, []):
            sec = data.get('ranges', {}).get(bk_try, {}).get(section_name, {})
            if sec.get(pos):
                if bk_try != bucket:
                    substituicao[section_name] = bk_try
                return sec[pos]
        return {}

    # vs_3bet — keyed por 3bettor (hero=pos é o opener; estrutura vs_3bet[hero][3bettor]).
    # O formato antigo {pos}_RFI_vs_3bet não existe mais (sempre dava null).
    vs_3bet = {tbettor: _grid_from_freqs(sp) for tbettor, sp in _section_for_pos('vs_3bet').items()} or None

    # squeeze — hero squeeza; keyed por opener (estrutura squeeze[hero][opener]).
    squeeze = {opener: _grid_from_freqs(sp) for opener, sp in _section_for_pos('squeeze').items()} or None

    # Nada aqui depende do usuario: a carta e um JSON estatico em disco e a resposta e funcao
    # pura de (posicao, balde). O `stack_bb` viaja no corpo so como eco do pedido, entao o cache
    # publico e por URL e nao mistura resposta entre contas.
    resp = jsonify({
        'position':     pos,
        'stack_bb':     round(stack_bb, 1),
        'stack_bucket': bucket,
        'rfi':          rfi,
        'vs_rfi':       vs_rfi,
        'vs_3bet':      vs_3bet,
        'squeeze':      squeeze,
        # so aparece quando ALGUMA secao veio de outro balde; ausente quando tudo bateu
        'substituicao': substituicao or None,
    })
    resp.headers['Cache-Control'] = 'public, max-age=3600'
    return resp


@app.route('/gto/strategy', methods=['POST'])
@require_auth
def gto_strategy():
    """
    Lookup GTO verificado para um spot específico — **read-only por padrão**.

    BLINDAGEM AGPL: o solver postflop (postflop-solver, AGPL-3.0) só roda OFFLINE
    (workers/scripts). Este endpoint, por padrão, serve APENAS dados já no banco
    (`block_remote=False`/`allow_remote_solve=False`) e NUNCA dispara um solve ao vivo
    pela rede — evitando o gatilho da AGPL §13 (interação de usuário com o programa
    remotamente). O solve ao vivo só é permitido para ADMIN que peça explicitamente
    (`live_solve: true`), p/ ferramentas internas.

    Body: street, position, board[], hero_hand[], hero_stack_bb,
          action_seq (default 'rfi'), vs_position (default ''),
          live_solve (default false — só efetivo p/ admin)

    200 → found=True, dados verificados (do banco)
    202 → found=False, sem cobertura no banco (não enfileira nem solva)
    """
    from leaklab.gto_solver import lookup_gto
    d               = request.get_json(force=True) or {}
    street          = str(d.get('street', 'preflop')).lower()
    position        = str(d.get('position', '')).upper()
    board           = d.get('board', [])
    hero_hand       = d.get('hero_hand', [])
    hero_stack_bb   = float(d.get('hero_stack_bb', 30.0))
    action_seq      = str(d.get('action_seq', 'rfi'))
    vs_position     = str(d.get('vs_position', ''))
    facing_size_bb  = float(d.get('facing_size_bb', 0.0) or 0.0)
    num_players     = int(d.get('num_players', 9) or 9)

    if not position or not hero_hand:
        return jsonify({'error': 'position e hero_hand são obrigatórios'}), 400

    # Solve ao vivo (AGPL via rede) SÓ para admin com opt-in explícito. Demais → read-only.
    live_solve = bool(d.get('live_solve')) and (g.user.get('role') == 'admin')

    result = lookup_gto(
        street=street, position=position, board=board,
        hero_hand=hero_hand, hero_stack_bb=hero_stack_bb,
        action_seq=action_seq, vs_position=vs_position,
        facing_size_bb=facing_size_bb,
        num_players=num_players,
        block_remote=live_solve,
        allow_remote_solve=live_solve,
    )
    return jsonify(result), 200 if result.get('found') else 202


@app.route('/admin/gto/import-verified', methods=['POST'])
@require_admin
def admin_gto_import_verified():
    """
    Importa ranges verificadas de solver externo (PioSOLVER, GTO Wizard export, etc.).
    Exige exploitability_pct no payload — rejeita importações sem garantia de qualidade.

    Body:
    {
      "solver": "piosolver_3.0",
      "game_tree": "6max_100bb_2.5x_ante",
      "exploitability_pct": 0.3,
      "ranges": [
        { "position":"BTN", "vs_position":"", "action_seq":"rfi",
          "hand_type":"AKs", "action":"raise", "frequency":1.0, "ev_bb":1.63 }
      ]
    }
    """
    from database.repositories import upsert_preflop_ranges
    body = request.get_json(force=True) or {}

    global_exploit = body.get('exploitability_pct')
    if global_exploit is None:
        return jsonify({'error': 'exploitability_pct obrigatório — importação sem garantia não é permitida'}), 400
    if float(global_exploit) > 1.0:
        return jsonify({'error': f'exploitability_pct={global_exploit}% > 1.0% — solve não convergiu o suficiente'}), 400

    ranges = body.get('ranges', [])
    if not ranges:
        return jsonify({'error': 'ranges[] obrigatório e não pode ser vazio'}), 400
    if len(ranges) > 10000:
        return jsonify({'error': 'Máximo de 10.000 ranges por importação'}), 400

    solver_config = _json.dumps({
        'solver':       body.get('solver', 'unknown'),
        'game_tree':    body.get('game_tree', ''),
        'imported_at':  _json.dumps(None),  # preenchido pelo banco via default
    })

    rows = []
    for r in ranges:
        rows.append({**r,
            'exploitability_pct': float(global_exploit),
            'source':             f"import:{body.get('solver', 'external')}",
            'solver_config':      solver_config,
        })

    inserted = upsert_preflop_ranges(rows)
    return jsonify({
        'inserted':            inserted,
        'exploitability_pct':  global_exploit,
        'solver':              body.get('solver'),
    })


@app.route('/admin/gto/preflop-stats', methods=['GET'])
@require_admin
def admin_gto_preflop_stats():
    """Estatísticas da base preflop verificada."""
    from database.repositories import get_preflop_stats
    return jsonify(get_preflop_stats())


@app.route('/admin/gto/run-solver', methods=['POST'])
@require_admin
def admin_gto_run_solver():
    """
    Processa até N spots da fila do solver.
    Só armazena solves com exploitability <= 1.0%.
    Retorna {solved, rejected, failed}.
    """
    from leaklab.gto_solver import run_solver_worker
    max_jobs = min(int((request.get_json(force=True) or {}).get('max_jobs', 5)), 20)
    result   = run_solver_worker(max_jobs=max_jobs)
    return jsonify(result)


@app.route('/admin/gto/queue', methods=['GET'])
@require_admin
def admin_gto_queue():
    """Lista spots na fila do solver com status."""
    from database.schema import get_conn as _gc
    from database.repositories import _fetchall, _adapt
    conn = _gc()
    try:
        rows = _fetchall(conn, _adapt("""
            SELECT spot_hash, status, priority, requested_at, solved_at
            FROM gto_solver_queue
            ORDER BY priority DESC, requested_at ASC
            LIMIT 200
        """))
        counts = {}
        for r in rows:
            counts[r['status']] = counts.get(r['status'], 0) + 1
        return jsonify({'queue': [dict(r) for r in rows], 'counts': counts})
    finally:
        conn.close()


@app.route('/player/hands/<hand_id>/request-gto', methods=['POST'])
@require_auth
def player_request_gto(hand_id):
    """Usuário solicita análise GTO para uma mão específica."""
    from database.repositories import (request_gto_for_hand, get_decisions,
                                        can_request_solve, increment_solves, get_quota_status,
                                        can_enqueue_solve)
    user_id = g.user_id
    body = request.get_json(force=True) or {}
    tournament_id = body.get('tournament_id')
    if not tournament_id:
        return jsonify({'error': 'tournament_id obrigatório'}), 400

    # Verificar acesso
    t = get_tournament(user_id, str(tournament_id))
    if not t:
        return jsonify({'error': 'Torneio não encontrado'}), 404

    # #26 — cota de solves on-demand por tier. Bloqueia ANTES de enfileirar quando
    # o plano estourou; 402 sinaliza upsell pro front. Pro/coach = ilimitado.
    allowed, remaining = can_request_solve(user_id)
    if not allowed:
        qs = get_quota_status(user_id)
        return jsonify({
            'error':        'solve_quota_exceeded',
            'message':      'Você atingiu o limite de análises GTO sob demanda do seu plano neste mês.',
            'solves_used':  qs.get('solves_used'),
            'solves_limit': (qs.get('limits') or {}).get('solves'),
            'plan':         qs.get('plan'),
        }), 402

    # Fase 2 — limite de fila por usuário: 1 aluno não pode monopolizar a fila/VM do solver.
    _q_ok, _q_pending, _q_cap = can_enqueue_solve(user_id)
    if not _q_ok:
        return jsonify({
            'error':   'solve_queue_full',
            'message': f'Você já tem {_q_pending} análises GTO na fila (máx {_q_cap}). Aguarde concluir antes de pedir mais.',
            'pending': _q_pending,
            'cap':     _q_cap,
        }), 429

    result = request_gto_for_hand(t['id'], hand_id, user_id)
    # Consome a cota só quando um solve NOVO entra na fila (idempotente: re-pedir
    # um já existente não cobra).
    if result.get('inserted'):
        increment_solves(user_id)
        remaining = (remaining - 1) if remaining is not None else None
    status_map = {
        'pending':    'Na fila — análise será processada em breve.',
        'processing': 'Processando agora...',
        'done':       'Análise já concluída.',
        'error':      'Ocorreu um erro no processamento anterior.',
    }
    return jsonify({
        'queued':           result['inserted'],
        'status':           result['status'],
        'id':               result['id'],
        'message':          status_map.get(result['status'], 'Na fila.'),
        'solves_remaining': remaining,   # None = ilimitado
    })


@app.route('/player/hands/<hand_id>/gto-status', methods=['GET'])
@require_auth
def player_gto_status(hand_id):
    """Retorna status da solicitação GTO para uma mão."""
    from database.repositories import get_gto_hand_request_status
    user_id = g.user_id
    row = get_gto_hand_request_status(hand_id, user_id)
    if not row:
        return jsonify({'status': 'not_requested'})
    return jsonify(dict(row))


@app.route('/admin/gto/hand-queue', methods=['GET'])
@require_admin
def admin_gto_hand_queue():
    """Lista fila de solicitações GTO por mão (admin)."""
    from database.repositories import get_gto_hand_request_queue
    rows = get_gto_hand_request_queue(limit=100)
    counts = {}
    for r in rows:
        counts[r['status']] = counts.get(r['status'], 0) + 1
    return jsonify({'queue': [dict(r) for r in rows], 'counts': counts})


@app.route('/admin/gto/worker-status', methods=['GET'])
@require_admin
def admin_gto_worker_status():
    """Status do GTO Hand Worker: saúde, filas, throughput, cobertura e erros recentes."""
    from database.schema import get_conn as _gc
    from database.repositories import _fetchall, _fetchone, _adapt

    conn = _gc()
    try:
        # ── Queue counters — gto_hand_requests ───────────────────────────────
        hand_counts_rows = _fetchall(conn, "SELECT status, COUNT(*) AS n FROM gto_hand_requests GROUP BY status")
        hand_counts = {r['status']: r['n'] for r in hand_counts_rows}

        # ── Queue counters — gto_solver_queue ────────────────────────────────
        solver_counts_rows = _fetchall(conn, "SELECT status, COUNT(*) AS n FROM gto_solver_queue GROUP BY status")
        solver_counts = {r['status']: r['n'] for r in solver_counts_rows}

        # ── Worker health: last processed timestamp ───────────────────────────
        # "Último proc" = mais recente entre o hand worker (gto_hand_requests.processed_at) E o
        # solver drenado por cron (gto_solver_queue.solved_at). Antes lia só o hand worker, que em
        # prod fica parado (ninguém usa GTO de mão sob demanda) → mostrava "—" mesmo com o solver
        # drenando de 5 em 5 min: pipeline vivo parecia morto.
        # solved_at/processed_at são gravados em UTC (datetime('now')/NOW()). Emite ISO 8601 com 'Z'
        # (UTC explícito) pro front (new Date().toLocaleString) converter pro fuso local de quem vê —
        # sem o 'Z' o JS lê a string naive como hora LOCAL e mostra o UTC cru (bug do GMT-3 no Brasil).
        import datetime as _dt0

        def _utc_iso(v):
            if hasattr(v, 'isoformat'):
                if getattr(v, 'tzinfo', None) is None:
                    v = v.replace(tzinfo=_dt0.timezone.utc)
                return v.isoformat().replace('+00:00', 'Z')
            s = str(v).strip().replace(' ', 'T')
            return s if (s.endswith('Z') or '+' in s[10:]) else s + 'Z'

        _lh = []
        for _q, _col in (("gto_hand_requests", "processed_at"), ("gto_solver_queue", "solved_at")):
            _r = _fetchone(conn, _adapt(
                f"SELECT {_col} AS ts FROM {_q} WHERE {_col} IS NOT NULL ORDER BY {_col} DESC LIMIT 1"))
            if _r and _r['ts'] is not None:
                _lh.append(_utc_iso(_r['ts']))
        last_heartbeat = max(_lh) if _lh else None

        # ── Throughput por hora (24h) — AS DUAS filas. Bucketiza em PYTHON (strftime é SQLite-only).
        import datetime as _dtt
        from collections import Counter as _Counter
        _cut = (_dtt.datetime.utcnow() - _dtt.timedelta(hours=24)).strftime('%Y-%m-%d %H:%M:%S')
        _rows = _fetchall(conn, _adapt(
            "SELECT processed_at AS ts FROM gto_hand_requests "
            "WHERE status IN ('done','error') AND processed_at >= ?"), (_cut,))
        _rows += _fetchall(conn, _adapt(
            "SELECT solved_at AS ts FROM gto_solver_queue "
            "WHERE solved_at IS NOT NULL AND solved_at >= ?"), (_cut,))
        _buckets = _Counter()
        for _r in _rows:
            _pa = _r['ts']
            if _pa is None:
                continue
            _s = _pa.isoformat() if hasattr(_pa, 'isoformat') else str(_pa)
            _buckets[_s[:13].replace(' ', 'T') + ':00:00'] += 1   # 'YYYY-MM-DDTHH:00:00'
        throughput = [{'hour': h, 'count': _buckets[h]} for h in sorted(_buckets)]

        # ── gto_nodes coverage by source ─────────────────────────────────────
        coverage_rows = _fetchall(conn, "SELECT source, COUNT(*) AS n FROM gto_nodes GROUP BY source")
        coverage = {r['source']: r['n'] for r in coverage_rows}
        # Preflop decisions validated via JSON range files (no gto_nodes entry)
        pf_row = _fetchone(conn, _adapt(
            "SELECT COUNT(*) AS n FROM decisions WHERE street='preflop' AND gto_label IS NOT NULL"
        ))
        coverage['preflop_ranges'] = pf_row['n'] if pf_row else 0
        nodes_total = sum(v for k, v in coverage.items() if k != 'preflop_ranges')
        coverage['total'] = nodes_total + coverage['preflop_ranges']

        # ── Recent errors ────────────────────────────────────────────────────
        error_rows = _fetchall(conn, _adapt("""
            SELECT r.id, r.hand_id, r.tournament_id, r.error_msg, r.processed_at,
                   u.email AS user_email
            FROM gto_hand_requests r
            LEFT JOIN users u ON u.id = r.requested_by
            WHERE r.status = 'error'
            ORDER BY r.processed_at DESC
            LIMIT 10
        """))
        recent_errors = [dict(r) for r in error_rows]

        # ── Worker active heuristic: processed anything in last 2 minutes ────
        is_active = False
        if last_heartbeat:
            active_row = _fetchone(conn, _adapt("""
                SELECT 1 FROM gto_hand_requests
                WHERE status IN ('done','error')
                  AND processed_at >= datetime('now', '-2 minutes')
                LIMIT 1
            """))
            is_active = active_row is not None

        # Also check if there are running requests (worker picked them up)
        if not is_active and hand_counts.get('running', 0) > 0:
            is_active = True

        # ── Fase 1: saúde do SOLVER (tempo de resolução, vazão, backlog, taxa de erro) ──
        # Tudo derivado da gto_solver_queue (requested_at + solved_at) — sem tocar no solver.
        import datetime as _dtm

        def _to_dt(v):
            if v is None:
                return None
            if hasattr(v, 'isoformat') and not isinstance(v, str):
                return v if getattr(v, 'tzinfo', None) else v.replace(tzinfo=_dtm.timezone.utc)
            try:
                s = str(v).strip().replace(' ', 'T').replace('Z', '')
                d = _dtm.datetime.fromisoformat(s)
                return d if d.tzinfo else d.replace(tzinfo=_dtm.timezone.utc)
            except Exception:
                return None

        _now_utc = _dtm.datetime.now(_dtm.timezone.utc)
        _cut1h = (_dtm.datetime.utcnow() - _dtm.timedelta(hours=1)).strftime('%Y-%m-%d %H:%M:%S')
        _cut24 = (_dtm.datetime.utcnow() - _dtm.timedelta(hours=24)).strftime('%Y-%m-%d %H:%M:%S')

        # tempo de resolução END-TO-END (enfileirado → resolvido) das últimas 24h. Janela recente
        # de propósito: incluir backlog antigo (spot que ficou semanas na fila) distorce o número,
        # não reflete a operação atual. Inclui a espera na fila; o solve PURO vem na Fase 3.
        _res_rows = _fetchall(conn, _adapt(
            "SELECT requested_at, solved_at FROM gto_solver_queue "
            "WHERE solved_at IS NOT NULL AND solved_at >= ? ORDER BY solved_at DESC LIMIT 500"), (_cut24,))
        _durs = []
        for _r in _res_rows:
            _a = _to_dt(_r['requested_at']); _b = _to_dt(_r['solved_at'])
            if _a and _b:
                _d = (_b - _a).total_seconds()
                if _d >= 0:
                    _durs.append(_d)
        _durs.sort()

        def _pctl(p):
            if not _durs:
                return None
            _i = min(len(_durs) - 1, int(round(p / 100.0 * (len(_durs) - 1))))
            return round(_durs[_i], 1)

        # vazão (solves concluídos na janela)
        _tp1 = _fetchone(conn, _adapt("SELECT COUNT(*) AS n FROM gto_solver_queue WHERE solved_at >= ?"), (_cut1h,))
        _tp24 = _fetchone(conn, _adapt("SELECT COUNT(*) AS n FROM gto_solver_queue WHERE solved_at >= ?"), (_cut24,))
        # backlog: idade do pendente mais antigo
        _oldest = _fetchone(conn, _adapt(
            "SELECT MIN(requested_at) AS ts FROM gto_solver_queue WHERE status = 'pending'"))
        _oldest_dt = _to_dt(_oldest['ts']) if _oldest else None
        _oldest_age = round((_now_utc - _oldest_dt).total_seconds()) if _oldest_dt else None
        # taxa de erro recente (24h)
        _ef = _fetchone(conn, _adapt(
            "SELECT SUM(CASE WHEN status='failed' THEN 1 ELSE 0 END) AS f, "
            "SUM(CASE WHEN status='done' THEN 1 ELSE 0 END) AS d "
            "FROM gto_solver_queue WHERE requested_at >= ?"), (_cut24,))
        _fail = (_ef['f'] or 0) if _ef else 0
        _donec = (_ef['d'] or 0) if _ef else 0
        _err_pct = round(_fail * 100.0 / (_fail + _donec), 1) if (_fail + _donec) else 0.0

        solver_health = {
            'resolution': {
                'avg_sec': round(sum(_durs) / len(_durs), 1) if _durs else None,
                'p95_sec': _pctl(95),
                'sample':  len(_durs),
            },
            'throughput': {'last_1h': (_tp1['n'] if _tp1 else 0), 'last_24h': (_tp24['n'] if _tp24 else 0)},
            'backlog': {
                'pending': solver_counts.get('pending', 0),
                'running': solver_counts.get('running', 0),
                'oldest_pending_age_sec': _oldest_age,
            },
            'error_rate': {'failed': _fail, 'done': _donec, 'pct': _err_pct},
        }

    finally:
        conn.close()

    # ── Servidor do solver: reachability + latência (ping no /health que já existe) ──
    _server = {'url': None, 'reachable': False, 'latency_ms': None, 'status': None, 'gto_wizard': None,
               'cpu_count': None, 'load': None, 'mem': None, 'active_solves': None,
               'max_solves': None, 'rayon_threads': None}
    try:
        import os as _os3, time as _t3, json as _j3, urllib.request as _u3
        _surl = (_os3.environ.get('GTO_SOLVER_URL', '') or '').rstrip('/')
        _server['url'] = _surl or None
        if _surl:
            _t0 = _t3.time()
            with _u3.urlopen(_surl + '/health', timeout=4) as _resp:
                _body = _j3.loads(_resp.read().decode('utf-8'))
            _server['latency_ms'] = round((_t3.time() - _t0) * 1000)
            _server['reachable'] = True
            # Fase 2: vitais do box do solver (presentes só se o /health estiver enriquecido)
            for _k in ('status', 'gto_wizard', 'cpu_count', 'load', 'mem',
                       'active_solves', 'max_solves', 'rayon_threads'):
                _server[_k] = _body.get(_k)
    except Exception:
        pass
    solver_health['server'] = _server

    # ── Estado do worker (3 níveis, p/ não confundir "ocioso normal" com "caiu") ──
    # O worker é CRON (drena de ~5 em 5 min), então fica fora de um job na maior parte do tempo.
    #   working = processando agora (is_active);
    #   healthy = ocioso mas saudável (cron rodou < 15 min OU não há trabalho na fila);
    #   down    = HÁ trabalho parado E sem heartbeat há >15 min → o cron não está drenando.
    import datetime as _dtw
    _pending = (solver_counts.get('pending', 0) + solver_counts.get('running', 0)
                + hand_counts.get('pending', 0) + hand_counts.get('queued', 0))
    _hb_recent = False
    if last_heartbeat:
        try:
            _hb = _dtw.datetime.fromisoformat(str(last_heartbeat).replace('Z', '+00:00'))
            _hb_recent = (_dtw.datetime.now(_dtw.timezone.utc) - _hb).total_seconds() < 15 * 60
        except Exception:
            _hb_recent = False
    if is_active:
        worker_state = 'working'
    elif _pending > 0 and not _hb_recent:
        worker_state = 'down'
    else:
        worker_state = 'healthy'

    return jsonify({
        'worker': {
            'active':         is_active,
            'state':          worker_state,
            'last_heartbeat': last_heartbeat,
        },
        'hand_queue':   hand_counts,
        'solver_queue': solver_counts,
        'solver_health': solver_health,
        'throughput':   throughput,
        'coverage':     coverage,
        'recent_errors': recent_errors,
    })


@app.route('/admin/gto/reprocess-decisions', methods=['POST'])
@require_admin
def admin_gto_reprocess_decisions():
    """
    Reprocessa todas as decisões de todos os torneios, re-avaliando com GTO.
    Atualiza gto_label, gto_action e label (se GTO suavizar o score).
    """
    from database.repositories import get_all_tournaments_raw, save_decisions
    from leaklab.parser import parse_pokerstars_file_from_text
    parse_ggpoker_file_from_text = parse_pokerstars_file_from_text  # GGPoker usa mesmo parser
    from leaklab.pipeline import build_decision_inputs_for_hand
    from leaklab.decision_engine_v11 import evaluate_decision

    tournaments = get_all_tournaments_raw()
    processed = errors = decisions_updated = 0

    for t in tournaments:
        raw_text = t.get('raw_text')
        if not raw_text:
            continue
        try:
            site = _detect_site(raw_text)
            if site == 'ggpoker':
                hands = parse_ggpoker_file_from_text(raw_text)
            else:
                hands = parse_pokerstars_file_from_text(raw_text)

            results = []
            for hand in hands:
                hero = hand.hero or t.get('hero', 'Hero')
                sd_result = _detect_showdown(hand.raw_text or '', hero)
                for di in build_decision_inputs_for_hand(hand):
                    r = evaluate_decision(di)
                    interp = r.get('interpretation', {})
                    enriched = {
                        **r,
                        'street':          di['street'],
                        'context':         di['context'],
                        'math':            di['math'],
                        'spot':            di['spot'],
                        'hero_cards':      hand.hero_cards,
                        'board':           hand.board or [],
                        'draw_profile':    di['math'].get('drawProfile', ''),
                        'position':        di['spot'].get('position', ''),
                        'num_players':     di['context'].get('activePlayers', 0),
                        'level_sb':        di['context'].get('levelSb', 0),
                        'level_bb':        di['context'].get('levelBb', 0),
                        'level_num':       di['context'].get('levelNum', 0),
                        'note':            interp.get('strategicExplanation', '') or interp.get('mathExplanation', ''),
                        'is_3bet':         di.get('is_3bet', False),
                        'showdown_result': sd_result,
                    }
                    results.append(enriched)

            save_decisions(t['id'], results)
            decisions_updated += len(results)
            processed += 1
        except Exception as e:
            log.warning('reprocess error tournament %s: %s', t.get('id'), e)
            errors += 1

    return jsonify({
        'processed': processed,
        'errors': errors,
        'decisions_updated': decisions_updated,
    })


# ── Revalidação engine vs oracle (varredura sistemática) ────────────────────

_REVAL_RUNS: dict[int, dict] = {}        # status em memória dos runs em background
_REVAL_NEXT_FAKE_ID = [0]                # sequência local p/ marcador "started"


@app.route('/admin/revalidation/run', methods=['POST'])
@require_admin
def admin_revalidation_run():
    """
    Dispara uma varredura de revalidação engine vs oracle.

    Body JSON:
      scope: 'all' | 'user:<id>' | 'tournament:<id>'   (default 'all')
      with_llm_judge: bool                              (default false)
      llm_budget: int                                   (default 50)
      sync: bool                                        (default false — roda em thread)
      output_dir: str                                   (opcional)
      notes: str                                        (opcional)

    Quando sync=true, executa inline e retorna o run_id real.
    Quando sync=false, retorna { run_id: null, task_id, status: 'started' }
    e o resultado pode ser consultado em /admin/revalidation/runs/<id>.
    """
    body = request.get_json(silent=True) or {}
    scope = _parse_scope(body.get('scope', 'all'))
    with_llm_judge = bool(body.get('with_llm_judge', False))
    llm_budget = int(body.get('llm_budget', 50))
    output_dir = body.get('output_dir') or os.path.join('reports', 'revalidation')
    notes = body.get('notes')
    sync = bool(body.get('sync', False))

    from leaklab.revalidation.orchestrator import revalidate

    if sync:
        result = revalidate(
            scope=scope, with_llm_judge=with_llm_judge,
            llm_budget=llm_budget, output_dir=output_dir, notes=notes,
        )
        return jsonify({
            'run_id':         result.run_id,
            'scope':          result.scope,
            'status':         'done',
            'total_decisions': result.total_decisions,
            'category_counts': result.category_counts,
            'elapsed_sec':    result.elapsed_sec,
            'errors':         len(result.errors),
        })

    # Background
    _REVAL_NEXT_FAKE_ID[0] += 1
    task_id = _REVAL_NEXT_FAKE_ID[0]
    _REVAL_RUNS[task_id] = {'status': 'started', 'run_id': None}

    def _bg():
        try:
            result = revalidate(
                scope=scope, with_llm_judge=with_llm_judge,
                llm_budget=llm_budget, output_dir=output_dir, notes=notes,
            )
            _REVAL_RUNS[task_id] = {
                'status':          'done',
                'run_id':          result.run_id,
                'total_decisions': result.total_decisions,
                'category_counts': result.category_counts,
                'elapsed_sec':     result.elapsed_sec,
                'errors':          len(result.errors),
            }
        except Exception as e:
            log.exception('revalidation background failed: task_id=%s', task_id)
            _REVAL_RUNS[task_id] = {'status': 'error', 'error': str(e), 'run_id': None}

    threading.Thread(target=_bg, daemon=True, name=f'revalidate-{task_id}').start()
    return jsonify({'task_id': task_id, 'status': 'started', 'run_id': None})


@app.route('/admin/revalidation/tasks/<int:task_id>', methods=['GET'])
@require_admin
def admin_revalidation_task_status(task_id: int):
    """Status de um run iniciado em background."""
    info = _REVAL_RUNS.get(task_id)
    if not info:
        return jsonify({'error': 'task não encontrada'}), 404
    return jsonify(info)


@app.route('/admin/revalidation/runs', methods=['GET'])
@require_admin
def admin_revalidation_runs():
    """Últimos N runs persistidos em revalidation_runs."""
    from database.schema import get_conn as _gc
    limit = int(request.args.get('limit', 20))
    conn = _gc()
    try:
        rows = conn.execute(
            "SELECT id, scope, total_tournaments, total_hands, total_decisions, "
            "category_counts_json, llm_judge_used, notes, created_at "
            "FROM revalidation_runs ORDER BY id DESC LIMIT ?",
            (limit,)
        ).fetchall()
        out = []
        for r in rows:
            d = dict(r)
            try:
                d['category_counts'] = json.loads(d.pop('category_counts_json') or '{}')
            except Exception:
                d['category_counts'] = {}
            out.append(d)
        return jsonify({'runs': out})
    finally:
        conn.close()


@app.route('/admin/revalidation/runs/<int:run_id>', methods=['GET'])
@require_admin
def admin_revalidation_run_detail(run_id: int):
    """Sumário + counts de um run específico."""
    from database.schema import get_conn as _gc
    conn = _gc()
    try:
        row = conn.execute(
            "SELECT * FROM revalidation_runs WHERE id = ?", (run_id,)
        ).fetchone()
        if not row:
            return jsonify({'error': 'run não encontrado'}), 404
        d = dict(row)
        try:
            d['category_counts'] = json.loads(d.pop('category_counts_json') or '{}')
        except Exception:
            d['category_counts'] = {}
        return jsonify(d)
    finally:
        conn.close()


@app.route('/admin/revalidation/runs/<int:run_id>/findings', methods=['GET'])
@require_admin
def admin_revalidation_findings(run_id: int):
    """
    Findings paginados de um run.

    Query params:
      category (string ou 'all', default 'all')
      street, position (filtros opcionais)
      limit (default 100, máx 500), offset (default 0)
      order ('severity_desc' [default] | 'severity_asc' | 'id_asc')
    """
    from database.schema import get_conn as _gc
    cat   = request.args.get('category', 'all')
    street = request.args.get('street')
    position = request.args.get('position')
    limit  = min(int(request.args.get('limit', 100)), 500)
    offset = int(request.args.get('offset', 0))
    order  = request.args.get('order', 'severity_desc')

    where = ["run_id = ?"]
    params: list = [run_id]
    if cat and cat != 'all':
        where.append("category = ?"); params.append(cat)
    if street:
        where.append("street = ?"); params.append(street)
    if position:
        where.append("position = ?"); params.append(position)
    where_sql = ' AND '.join(where)

    if order == 'severity_asc':
        order_sql = "ORDER BY severity_score ASC, id ASC"
    elif order == 'id_asc':
        order_sql = "ORDER BY id ASC"
    else:
        order_sql = "ORDER BY severity_score DESC, id ASC"

    conn = _gc()
    try:
        rows = conn.execute(
            f"SELECT * FROM revalidation_findings WHERE {where_sql} {order_sql} LIMIT ? OFFSET ?",
            tuple(params) + (limit, offset),
        ).fetchall()
        total_row = conn.execute(
            f"SELECT COUNT(*) AS n FROM revalidation_findings WHERE {where_sql}",
            tuple(params),
        ).fetchone()
        out = []
        for r in rows:
            d = dict(r)
            try:
                d['reasons'] = json.loads(d.pop('reasons_json') or '[]')
            except Exception:
                d['reasons'] = []
            out.append(d)
        return jsonify({
            'run_id': run_id,
            'total':  dict(total_row).get('n', 0) if total_row else 0,
            'limit':  limit,
            'offset': offset,
            'findings': out,
        })
    finally:
        conn.close()


def _parse_scope(raw: str):
    """Converte string 'all'|'user:N'|'tournament:N' em Scope."""
    from leaklab.revalidation.orchestrator import Scope
    raw = (raw or 'all').strip()
    if raw == 'all':
        return Scope.all()
    if raw.startswith('user:'):
        return Scope.for_user(int(raw.split(':', 1)[1]))
    if raw.startswith('tournament:'):
        return Scope.for_tournament(int(raw.split(':', 1)[1]))
    return Scope.all()


@app.route('/admin/reanalyze-preflop-labels', methods=['POST'])
@require_admin
def admin_reanalyze_preflop_labels():
    """
    Re-analisa labels preflop usando o pipeline completo (parse → evaluate).
    Corrige decisões que receberam label errado devido aos bugs corrigidos em
    preflop_gto_ranges.py (v0.101.x). Idempotente — seguro rodar múltiplas vezes.
    """
    from database.schema import get_conn as _gc
    from leaklab.parser import parse_hand_history
    from leaklab.pipeline import build_decision_inputs_for_hand
    from leaklab.decision_engine_v11 import evaluate_decision

    conn = _gc()
    try:
        tournaments = conn.execute(
            "SELECT id FROM tournaments WHERE raw_text IS NOT NULL ORDER BY id"
        ).fetchall()

        total_checked = 0
        total_updated = 0
        skipped_tournaments = 0
        affected_ids  = set()
        changes       = []

        for row in tournaments:
            tid = row['id']
            raw_row = conn.execute(
                "SELECT raw_text FROM tournaments WHERE id = ?", (tid,)
            ).fetchone()
            # Acesso por chave: no Postgres fetchone() devolve dict (RealDictCursor),
            # raw_row[0] estoura KeyError.
            raw_text = raw_row['raw_text'] if raw_row else None
            if not raw_text:
                continue

            try:
                hands = parse_hand_history(raw_text)
            except Exception:
                continue

            def _real(v):  # posição concreta (ignora vazio/UNKNOWN)
                return v and str(v).upper() != 'UNKNOWN'
            def _diff(a, b):  # difere de fato (case-insensitive)
                return str(a or '').upper() != str(b or '').upper()

            seen: set = set()
            tour_changes = []   # mudanças DESTE torneio, só persistidas se o commit passar
            for hand in hands:
                try:
                    dis = build_decision_inputs_for_hand(hand)
                except Exception:
                    continue

                for di in dis:
                    if di.get('street') != 'preflop':
                        continue
                    hand_id = di.get('hand_id', '')
                    spot    = di.get('spot', {})
                    act     = (spot.get('actionTaken') or di.get('player_action', '')).lower()
                    pos     = (di.get('position') or spot.get('position') or '').upper()
                    if not hand_id or not act:
                        continue
                    dedup = (hand_id, pos, act)
                    if dedup in seen:
                        continue
                    seen.add(dedup)

                    # Escopar por tournament_id: hand_id NÃO é único entre torneios/usuários
                    # (dois jogadores importam o mesmo torneio = mesmo hand_id). Sem o escopo,
                    # o match colide e relabela/reposiciona a decisão de OUTRA conta.
                    db_row = conn.execute(
                        "SELECT id, label, score, ev_loss_bb, position, vs_position FROM decisions "
                        "WHERE tournament_id = ? AND hand_id = ? AND street = 'preflop' "
                        "AND action_taken = ? LIMIT 1",
                        (tid, hand_id, act)
                    ).fetchone()
                    if not db_row:
                        continue

                    did       = db_row['id']
                    old_label = db_row['label']
                    old_pos   = db_row['position']
                    old_vs    = db_row['vs_position']
                    total_checked += 1

                    try:
                        result    = evaluate_decision(di)
                        new_label = (result.get('evaluation') or {}).get('label') or old_label
                    except Exception:
                        continue

                    # Posição/vs_position frescos (o pipeline já usa o _infer_position
                    # corrigido, que exclui o assento "out of hand"). Corrige decisões
                    # gravadas antes do fix, cuja posição defasada quebrava o lookup GTO
                    # (ex.: BB defendendo virava "UTG" → caía na heurística).
                    new_pos = pos or old_pos
                    new_vs  = (result.get('preflop_gto') or {}).get('vs_position') or old_vs

                    sets, params = [], []
                    if new_label != old_label:
                        sets.append("label = ?");       params.append(new_label)
                        # O SCORE VIAJA COM O LABEL. Esta era a terceira porta a mudar o veredito
                        # sem carregar o score junto (as outras duas ja tinham sido fechadas), e
                        # ela deixava `label='standard'` com `score=0,9` -- a banda de standard e
                        # [0; 0,08]. Medido em 26/08: 14 linhas do acervo, todas de solver, com o
                        # rotulo dizendo "correto" e o numero dizendo "pior possivel". Como
                        # `priority_score = COUNT(*) * AVG(score)`, o numero orfao ainda ordenava
                        # o plano de estudo.
                        sets.append("score = ?")
                        params.append(_align_score_to_label(
                            new_label, db_row['score'], db_row['ev_loss_bb']))
                    # Só corrige posição/vs para um valor CONCRETO e realmente diferente:
                    # nunca rebaixa uma posição conhecida para UNKNOWN nem gera churn de caixa.
                    if _real(new_pos) and _diff(new_pos, old_pos):
                        sets.append("position = ?");    params.append(new_pos)
                    if _real(new_vs) and _diff(new_vs, old_vs):
                        sets.append("vs_position = ?"); params.append(new_vs)

                    if sets:
                        params.append(did)
                        conn.execute(
                            f"UPDATE decisions SET {', '.join(sets)} WHERE id = ?",
                            tuple(params)
                        )
                        tour_changes.append({
                            'tid': tid, 'hand_id': hand_id, 'action': act,
                            'old': old_label, 'new': new_label,
                            'pos': f"{old_pos}->{new_pos}" if new_pos != old_pos else old_pos,
                            'vs':  f"{old_vs}->{new_vs}" if new_vs != old_vs else old_vs,
                        })

            # Commit POR TORNEIO: transação curta evita deadlock com migrações/outros
            # workers (a versão anterior segurava locks de TODAS as decisões por ~1min
            # numa transação única → deadlock detected no UPDATE tournaments). Recalcula
            # o agregado do torneio no mesmo commit. Se der deadlock/erro, faz rollback
            # e SEGUE (só perde este torneio, não a run inteira).
            if not tour_changes:
                continue
            try:
                std_row = conn.execute(
                    "SELECT COUNT(CASE WHEN label='standard' THEN 1 END)*100.0/COUNT(*) AS s, "
                    "AVG(score) AS a FROM decisions WHERE tournament_id = ?", (tid,)
                ).fetchone()
                if std_row:
                    conn.execute(
                        "UPDATE tournaments SET standard_pct=?, avg_score=? WHERE id=?",
                        (round(std_row['s'] or 0, 2), round(std_row['a'] or 0, 4), tid)
                    )
                conn.commit()
                affected_ids.add(tid)
                changes.extend(tour_changes)
                total_updated += len(tour_changes)
            except Exception:
                try:
                    conn.rollback()
                except Exception:
                    pass
                skipped_tournaments += 1

        return jsonify({
            'checked':  total_checked,
            'updated':  total_updated,
            'affected_tournaments': len(affected_ids),
            'skipped_tournaments':  skipped_tournaments,
            'changes':  changes,
        })
    finally:
        conn.close()


@app.route('/admin/llm-cache/clear', methods=['POST'])
@require_admin
def admin_clear_llm_cache():
    """Limpa o LLM cache (banco + in-memory). Útil após re-validação GTO."""
    import leaklab.llm_explainer as _exp
    conn = get_conn()
    try:
        deleted = conn.execute("DELETE FROM llm_cache").rowcount
        conn.commit()
    finally:
        conn.close()
    _exp._cache.clear()
    return jsonify({'ok': True, 'deleted_db': deleted, 'message': 'LLM cache limpo'})


@app.route('/support/contact', methods=['POST'])
@require_auth
def support_contact():
    from database.schema import get_conn as _gc
    data     = request.get_json(force=True) or {}
    category = str(data.get('category', 'other'))[:50]
    subject  = str(data.get('subject',  ''))[:120]
    message  = str(data.get('message',  '')).strip()
    if not message:
        return jsonify({'error': 'Mensagem obrigatória'}), 400
    conn = _gc()
    try:
        conn.execute(
            "INSERT INTO support_tickets (user_id, category, subject, message) VALUES (?, ?, ?, ?)",
            (g.user_id, category, subject, message)
        )
        conn.commit()
    finally:
        conn.close()
    return jsonify({'ok': True})


@app.route('/support/my-tickets', methods=['GET'])
@require_auth
def support_my_tickets():
    from database.schema import get_conn as _gc
    conn = _gc()
    try:
        rows = conn.execute(
            "SELECT id, category, subject, message, status, admin_reply, replied_at, created_at "
            "FROM support_tickets WHERE user_id = ? ORDER BY created_at DESC LIMIT 50",
            (g.user_id,)
        ).fetchall()
        return jsonify({'tickets': [dict(r) for r in rows]})
    finally:
        conn.close()


@app.route('/support/my-tickets/unread', methods=['GET'])
@require_auth
def support_my_tickets_unread():
    """Count of replied tickets not yet read by the user."""
    from database.schema import get_conn as _gc
    conn = _gc()
    try:
        row = conn.execute(
            "SELECT COUNT(*) AS n FROM support_tickets WHERE user_id = ? AND status = 'replied' AND read_at IS NULL",
            (g.user_id,)
        ).fetchone()
        return jsonify({'replied': int(row['n']) if row else 0})
    finally:
        conn.close()


@app.route('/support/my-tickets/mark-read', methods=['POST'])
@require_auth
def support_mark_read():
    """Mark all replied tickets as read (clears the unread badge)."""
    from database.schema import get_conn as _gc
    conn = _gc()
    try:
        conn.execute(
            "UPDATE support_tickets SET read_at = datetime('now') WHERE user_id = ? AND status = 'replied' AND read_at IS NULL",
            (g.user_id,)
        )
        conn.commit()
        return jsonify({'ok': True})
    finally:
        conn.close()


@app.route('/support/my-tickets/<int:ticket_id>', methods=['DELETE'])
@require_auth
def support_delete_ticket(ticket_id):
    """Apaga UMA mensagem do próprio usuário (limpar a lista). Guard de dono (só o autor apaga)."""
    from database.schema import get_conn as _gc
    conn = _gc()
    try:
        conn.execute("DELETE FROM support_tickets WHERE id = ? AND user_id = ?", (ticket_id, g.user_id))
        conn.commit()
        return jsonify({'ok': True})
    finally:
        conn.close()


@app.route('/support/my-tickets', methods=['DELETE'])
@require_auth
def support_clear_my_tickets():
    """Limpa TODAS as mensagens do próprio usuário."""
    from database.schema import get_conn as _gc
    conn = _gc()
    try:
        conn.execute("DELETE FROM support_tickets WHERE user_id = ?", (g.user_id,))
        conn.commit()
        return jsonify({'ok': True})
    finally:
        conn.close()


@app.errorhandler(500)
def internal_error(e):
    # Não vazar a mensagem da exceção (pode conter SQL/caminhos/colunas). Loga server-side só.
    log.exception("internal_error 500: %s", e)
    return jsonify({'error': 'Erro interno do servidor'}), 500

@app.errorhandler(413)
def too_large(_): return jsonify({'error': 'Arquivo muito grande (limite: 5MB)'}), 413

@app.errorhandler(405)
def method_not_allowed(_): return jsonify({'error': 'Método não permitido'}), 405

@app.errorhandler(404)
def not_found(_): return jsonify({'error': 'Rota não encontrada'}), 404


def _enfileirar_spot_da_decisao(di: dict, facing: float, tournament_db_id=None) -> bool:
    """Enfileira o spot postflop desta decisão no solver. True se ele está de fato na fila.

    Existe porque o contador `queued` do processador de pedidos MENTIA. O ramo do mismatch
    enfileirava e contava; o ramo de "ainda sem cobertura" apenas CONTAVA, apoiado em
    `is_simple_spot` — que responde "dá para solvar em menos de 30s", e não "alguém pediu o
    solve". Resultado medido em produção: o pedido 13 do torneio 123 ficou 2h relatando
    `done=0 queued=1` com a fila do solver VAZIA, e o selo "Análise GTO em andamento" mentiu
    até o age-out de 24h. A decisão nunca ganharia veredito.

    Agora o enfileiramento é UM lugar só, e quem conta pergunta a ele se deu certo.
    """
    from leaklab.gto_solver import _priority, montar_payload_postflop
    from database.repositories import enqueue_solver_spot
    try:
        spot = di.get('spot', {}) or {}
        ctx  = di.get('context', {}) or {}
        street = di.get('street', '')
        # Gate, corte de board, ranges e parametros moram em `montar_payload_postflop` — era a
        # TERCEIRA copia da mesma montagem, e as copias ja discordaram (ranges trocadas).
        # `potSize` vem em FICHAS. Este chamador passava ele CRU como `pot_bb` enquanto os outros
        # dois pontos do arquivo dividiam pelo `level_bb` e explicavam por quê: pote ~100x inflado
        # → SPR colapsa → o solver força all-in e devolve estratégia degenerada com exploitability
        # 0.0% falsa. Medido em produção: **135 nós (2,6%) nasceram assim**, 9 deles all-in a 100%
        # e 11 com exploitability ≤ 0,05%. O treino peneira esses nós desde hoje, mas o `/replay`
        # não peneira — eles continuavam virando veredito.
        #
        # `potBb` já vem convertido do pipeline, ao lado do `potSize`. A peneira abaixo existe
        # porque o próprio `potBb` divide por `(bb or 1)`: quando o parser não extrai a BB, ele
        # sai igual ao valor em fichas. Ver [[reference_parser_bb_extraction_gate]].
        _stack = float(spot.get('effectiveStackBb') or ctx.get('heroStackBb') or 20)
        _pot_bb = spot.get('potBb')
        try:
            _pot_bb = float(_pot_bb) if _pot_bb is not None else None
        except (TypeError, ValueError):
            _pot_bb = None
        # Peneira pela FONTE UNICA (pote_implausivel) — a regra local barrava TAMBEM o pote
        # multiway legitimo com um so vilao ativo (HU com dinheiro morto), que e solvavel.
        # Nota: o limiar local antigo (pot > 2.5*stack) era ate MAIS estrito que a peneira
        # do reenqueue (2.5*2*stack); a fonte unica unifica os dois no mesmo numero.
        from leaklab.gto_solver import pote_implausivel as _pote_impl
        if _pot_bb is not None and (_pot_bb <= 0 or _pote_impl(_pot_bb, _stack, spot.get('nActiveOpponents'))):
            log.warning('spot NAO enfileirado: pote implausivel (%.1fbb com stack %.1fbb, street=%s)',
                        _pot_bb, _stack, street)
            return False
        montado = montar_payload_postflop(
            street      = street,
            position    = spot.get('position') or ctx.get('position') or '',
            vs_position = spot.get('villainPosition') or ctx.get('vsPosition') or '',
            board       = di.get('board', []) or spot.get('board', []),
            hero_cards  = di.get('hero_cards', []),
            stack_bb    = _stack,
            facing_bb   = facing,
            pot_bb      = _pot_bb,
            pot_type    = spot.get('potType', ''),
            opener      = spot.get('preflopOpener', ''),
            threebettor = spot.get('preflop3bettor', ''))
        if not montado:
            return False
        h, payload = montado
        return bool(enqueue_solver_spot(h, payload, priority=_priority(street),
                                        tournament_id=tournament_db_id))
    except Exception:
        log.exception('falha ao enfileirar spot da decisao (street=%s)', di.get('street'))
        return False


def _process_gto_hand_request(req: dict) -> tuple[str, str | None]:
    """
    Processa um item da gto_hand_requests: busca decisões da mão, roda lookup_gto
    em cada uma, salva gto_label/gto_action no banco.
    Retorna (status, error_msg).
    """
    from database.repositories import (
        get_decisions, update_decision_gto, update_gto_hand_request,
    )
    from leaklab.gto_solver import lookup_gto
    from leaklab.pipeline import build_decision_inputs_for_hand
    from leaklab.decision_engine_v11 import evaluate_decision

    request_id    = req['id']
    tournament_id = req['tournament_id']
    hand_id       = req['hand_id']

    try:
        from database.repositories import get_tournament_by_db_id as _get_t_by_id
        # tournament_id aqui é o DB int (t['id']), não o hash string
        t = _get_t_by_id(req.get('requested_by', 0), tournament_id)
        if not t:
            # fallback: buscar sem filtro de user (admin worker)
            from database.schema import get_conn as _gc
            from database.repositories import _fetchone, _adapt
            _conn = _gc()
            try:
                t = _fetchone(_conn, _adapt("SELECT * FROM tournaments WHERE id = ?"), (tournament_id,))
            finally:
                _conn.close()
        if not t or not t.get('raw_text'):
            return 'error', 'Torneio sem raw_text no banco', 0, 0

        raw_text = t['raw_text']
        site = _detect_site(raw_text)
        if site == 'ggpoker':
            from leaklab.parser import parse_pokerstars_file_from_text as _parse_gg
            hands = _parse_gg(raw_text)
        else:
            from leaklab.parser import parse_pokerstars_file_from_text as _parse_ps
            hands = _parse_ps(raw_text)

        target = next((h for h in hands if str(h.hand_id) == str(hand_id)), None)
        if not target:
            return 'error', f'Mão {hand_id} não encontrada no raw_text', 0, 0

        hero = target.hero or t.get('hero', 'Hero')
        db_decisions = [d for d in get_decisions(tournament_id)
                        if str(d.get('hand_id')) == str(hand_id)]

        # Balde (street, action_taken) → linhas do banco, consumido EM ORDEM.
        # Era um dict, e a chave NÃO é única: com duas decisões iguais na mesma street a
        # segunda sobrescrevia a primeira, e o resultado do solver era gravado no
        # `decision_id` ERRADO. Dos quatro lugares com esse defeito, este é o único que
        # ESCREVE no banco. Ver leaklab/pareamento_decisoes.py.
        def _norm(a):
            if not a: return ''
            a = a.rstrip('s') if a.endswith('s') else a
            return 'allin' if a in ('all-in', 'allin', 'jam', 'shove') else a
        db_index = BaldeDeDecisoes(
            db_decisions,
            lambda d: (_norm(d.get('street', '')), _norm(d.get('action_taken', ''))),
        )

        update_gto_hand_request(request_id, 'processing',
                                decisions_found=len(db_decisions))

        done = 0      # resolvidos agora pela primeira vez
        queued = 0    # enfileirados para o solver (não estavam na base)
        for di in build_decision_inputs_for_hand(target):
            if di['street'] not in ('flop', 'turn', 'river'):
                continue
            ctx = di.get('context', {})
            key = (_norm(di['street']), _norm(di.get('player_action', '') or ''))
            db_dec = db_index.proxima(key)
            if not db_dec:
                continue
            already_analyzed = bool(db_dec.get('gto_label'))
            # Não pula: re-analisa sempre para corrigir gto_action de nós parciais antigos

            spot = di.get('spot', {})
            # potSize vem em FICHAS → converter p/ BB pelo level_bb (senão pot 100x inflado
            # → SPR colapsa → solver degenera em all-in; mesma classe do bug do enqueue).
            _lvl_bb = float(db_dec.get('level_bb') or 1) or 1
            _pot_bb = round(float(spot.get('potSize', 0) or 0) / _lvl_bb, 2)
            gto = lookup_gto(
                street          = di['street'],
                position        = spot.get('position', ctx.get('position', '')),
                board           = spot.get('board', []),
                hero_hand       = di.get('hero_cards', []),
                hero_stack_bb   = spot.get('effectiveStackBb', ctx.get('heroStackBb', 20.0)),
                action_seq      = ctx.get('actionSeq', 'rfi'),
                vs_position     = spot.get('villainPosition', ctx.get('vsPosition', '')),
                facing_size_bb  = float(db_dec.get('facing_bet', 0) or 0),
                pot_bb          = _pot_bb,
                num_players     = int(db_dec.get('num_players', 9) or 9),
            )

            if gto.get('found') and gto.get('strategy'):
                r   = evaluate_decision(di)
                acted = _norm(r.get('player_action', '') or di.get('player_action', ''))
                played_freq = next(
                    (s['frequency'] for s in gto['strategy']
                     if _norm(str(s.get('action', ''))) == acted),
                    0.0
                )
                top_action = max(gto['strategy'], key=lambda s: s['frequency'])
                gto_action = _norm(str(top_action.get('action', '')))

                # Guarda de contexto: não salva se o nó GTO for incompatível
                # com a situação real (facing bet vs sem aposta).
                engine_best = _norm(db_dec.get('best_action', '') or '')
                _facing     = float(db_dec.get('facing_bet', 0) or 0)
                _NO_BET_ACTIONS = ('check', 'bet')
                _is_mismatch = (
                    # Qualquer facing_bet > 0 com nó de check/bet → sempre inválido
                    (_facing > 0 and gto_action in _NO_BET_ACTIONS)
                    or (engine_best != 'call' and gto_action == 'call' and _facing == 0)
                )
                if _is_mismatch:
                    log.warning(
                        "GTO mismatch descartado: dec=%s engine=%s gto=%s facing=%.1f",
                        db_dec['id'], engine_best, gto_action, _facing,
                    )
                    # Enfileira o spot correto (com facing real) pelo MESMO caminho do outro
                    # ramo: este bloco era uma segunda cópia da montagem do payload, e a cópia
                    # que ficou para trás foi justamente a que esqueceu de enfileirar.
                    _entrou = _enfileirar_spot_da_decisao(di, _facing, req.get('tournament_id'))
                    if _entrou:
                        queued += 1   # só conta o que entrou na fila de verdade
                    continue

                if played_freq >= 0.60:
                    gto_label = 'gto_correct'
                elif played_freq >= 0.30:
                    gto_label = 'gto_mixed'
                elif played_freq >= 0.10:
                    gto_label = 'gto_minor_deviation'
                else:
                    gto_label = 'gto_critical'

                # Score como opportunity cost da ação jogada vs ação ótima
                top_freq_w    = max((s['frequency'] for s in gto['strategy']), default=1.0)
                opp_cost_w    = max(0.0, top_freq_w - played_freq)
                _score_mult_w = {
                    'gto_correct': 0.10, 'gto_mixed': 0.30,
                    'gto_minor_deviation': 0.65, 'gto_critical': 0.90,
                }
                gto_score_w = round(opp_cost_w * _score_mult_w.get(gto_label, 0.5), 4)
                _lbl_thresholds = [(0.08, 'standard'), (0.18, 'marginal'),
                                   (0.36, 'small_mistake'), (1.0, 'clear_mistake')]
                engine_label_w = next(l for t, l in _lbl_thresholds if gto_score_w <= t)

                update_decision_gto(db_dec['id'], gto_label, gto_action,
                                    label=engine_label_w, score=gto_score_w)
                if not already_analyzed:
                    done += 1
            else:
                # Spot sem dado GTO. A pergunta que decide o destino do PEDIDO é: o solver local
                # vai resolver isto algum dia? `is_simple_spot` já responde — e o código antigo
                # ignorava a resposta, contando como "enfileirado" mesmo o que ele acabara de
                # classificar como fora do alcance. O pedido ficava 'solver_queued' esperando algo
                # que ninguém ia fazer (sintoma em produção: req_id=8 parado com a fila do solver
                # VAZIA — não havia nada em andamento, e não haveria).
                #
                # Sem cobertura é TERMINAL e honesto: `gto_label` fica NULL e o card mostra o
                # motivo real. Só conta como enfileirado o que o solver de fato vai pegar.
                #
                # Removido daqui o UPDATE que marcava a decisão para o fallback do GTO Wizard: ele
                # foi descontinuado, `_mark_failed_solver_jobs_as_wizard_pending` já é no-op pelo
                # mesmo motivo, e existe um script (`clear_wizard_pending.py`) para limpar as
                # linhas legadas — este caminho recriava exatamente o que ele apaga.
                _facing2  = float(db_dec.get('facing_bet', 0) or 0)
                _stack2   = float(spot.get('effectiveStackBb') or ctx.get('heroStackBb') or 20)
                _street2  = di.get('street', 'flop')
                _solvavel = True
                try:
                    from leaklab.gto_solver import is_simple_spot as _is_simple
                    _solvavel = bool(_is_simple(_street2, spot.get('board', []), _stack2, _facing2))
                except Exception:
                    # Na dúvida, conta como enfileirado: o age-out fecha depois. Melhor esperar
                    # por algo solvável do que declarar sem cobertura o que talvez tivesse.
                    log.exception("GTO hand worker: is_simple_spot falhou (dec_id=%s)", db_dec.get('id'))
                # Conta como enfileirado SÓ o que entrou na fila. `is_simple_spot` responde
                # "dá para solvar rápido", não "alguém pediu o solve" — usá-la como prova de
                # enfileiramento foi o que fez o pedido 13 esperar 24h por nada.
                if _solvavel and _enfileirar_spot_da_decisao(di, _facing2,
                                                             req.get('tournament_id')):
                    queued += 1

        # ENQUANTO HOUVER spot enfileirado (queued>0), o request NÃO está pronto — fica 'solver_queued'
        # mesmo que tenha resolvido alguns agora (done>0). O 'and done==0' antigo marcava 'done'
        # prematuramente quando 1 spot resolvia, com outros ainda solvando → a lista mostrava "Analisado"
        # com spots em andamento. 'done' só quando queued==0 (tudo resolvido). O drain re-checa a cada
        # ciclo (e força 'done' nos não-solváveis velhos > 2h).
        final_status = 'solver_queued' if queued > 0 else 'done'
        return final_status, None, done, queued

    except Exception as exc:
        log.exception("GTO hand worker error req_id=%s", request_id)
        return 'error', str(exc), 0, 0


def _mark_failed_solver_jobs_as_wizard_pending() -> int:
    """APOSENTADO. O fallback pro GTO Wizard foi descontinuado: o GW foi cancelado e
    só resolvia HU, então spots que o solver local não cobre (multiway postflop, etc.)
    não têm para onde ir — ficam como "sem cobertura" (gto_label NULL), que é o estado
    honesto. Antes, esta função re-marcava esses jobs falhos como wizard_pending a cada
    ciclo do worker, deixando o indicador "processando" preso pra sempre. No-op agora."""
    return 0


_REPORT_SWEEP_SEC = 3600   # varredura de cadência do relatório: de hora em hora basta, porque o
                           # gatilho mais rápido (veredito mudou) só muda quando o jogador importa


def _evolution_report_worker_loop():
    """Congela um retrato do relatório de evolução para quem cruzou um gatilho.

    Roda aqui, no serviço que já está de pé, e não num cron: cron pendente é o que já falhou nesta
    operação — o de `drain_hand_requests` nunca executou porque redirecionava log para /var/log,
    onde o usuário `deploy` não pode criar arquivo, e o shell do cron falhava antes do comando.
    Sem rastro, porque o rastro era justamente o arquivo.

    A decisão de gerar é `repositories.decidir_cadencia_relatorio` (pura e testada); aqui só há o
    relógio e o log."""
    from database.repositories import gerar_relatorios_pendentes
    time.sleep(60)   # deixa o app e as filas assentarem antes da primeira varredura
    while True:
        try:
            feitos = gerar_relatorios_pendentes()
            for uid, motivo, rid in feitos:
                log.info("relatório de evolução gerado: user_id=%s motivo=%s id=%s", uid, motivo, rid)
                # O relatório era gerado EM SILÊNCIO — o desperdício mais óbvio que a spec de
                # cobrança mediu: o sistema produzia a notícia e não contava a ninguém.
                try:
                    from database.repositories import create_notification
                    create_notification(uid, 'relatorio_gerado',
                                        {'motivo': motivo, 'report_id': rid}, '/evolucao')
                except Exception:
                    log.exception('sino de relatório falhou (user=%s)', uid)
        except Exception:
            log.exception("evolution report worker loop error")
        time.sleep(_REPORT_SWEEP_SEC)


_COBRANCA_SWEEP_SEC = 6 * 3600   # varredura da cobrança por e-mail: 4x/dia basta, porque o teto
                                 # é semanal — varrer de hora em hora só gastaria banco


def _cobranca_email_worker_loop():
    """E-mail de cobrança por evento (Fase 2 da spec cobranca-proximo-passo.md).

    Roda no serviço que já está de pé, e não num cron — mesma razão do worker de relatórios.

    DESLIGADO por padrão (`ENGAGEMENT_EMAIL_ENABLED`): subir código é reversível, e-mail enviado
    não é. O loop levanta mesmo desligado e apenas não envia, para que ligar a flag não dependa
    de um restart lembrado.

    A DECISÃO é da função pura `decidir_email_cobranca`; aqui só há o relógio, o SMTP e o log.
    """
    from leaklab.cobranca_email import (emails_habilitados, coletar_eventos,
                                        decidir_email_cobranca, montar_email)
    from leaklab.email_digest import send_transactional_email, _email_unsub_token
    from database.repositories import (alunos_para_varredura_de_cobranca,
                                       ultimo_email_de_cobranca, registrar_email_de_cobranca)
    from datetime import datetime
    time.sleep(90)   # deixa o app assentar; e não compete com a primeira varredura do relatório
    base_url = os.environ.get('APP_BASE_URL', 'https://grindlabpoker.com')
    while True:
        try:
            if not emails_habilitados():
                log.info('cobrança por e-mail: desligada (ENGAGEMENT_EMAIL_ENABLED)')
            else:
                agora = datetime.utcnow().isoformat()
                enviados = 0
                # A lista já vem filtrada por opt-in/verificado (o opt-out mora na origem, para
                # que nenhum caminho novo possa esquecer de checá-lo).
                for aluno in alunos_para_varredura_de_cobranca():
                    uid = int(aluno['id'])
                    try:
                        escolhido = decidir_email_cobranca(
                            agora, coletar_eventos(uid, agora), ultimo_email_de_cobranca(uid))
                        if not escolhido:
                            continue
                        token = _email_unsub_token(uid)
                        unsub = f"{base_url}/api/player/email/unsubscribe?uid={uid}&token={token}"
                        montado = montar_email(escolhido['tipo'], escolhido.get('dados') or {},
                                               aluno.get('username') or '', base_url, unsub)
                        if not montado:
                            continue
                        assunto, html = montado
                        # Registra SÓ depois do SMTP aceitar: gravar antes transformaria uma
                        # falha de envio em silêncio de uma semana inteira para aquele aluno.
                        if send_transactional_email(aluno['email'], assunto, html):
                            registrar_email_de_cobranca(uid, escolhido['tipo'])
                            enviados += 1
                            log.info('cobrança enviada: user=%s tipo=%s', uid, escolhido['tipo'])
                    except Exception:
                        log.exception('cobrança por e-mail falhou (user=%s)', uid)
                log.info('varredura de cobrança concluída: %d e-mail(s)', enviados)
        except Exception:
            log.exception('cobranca email worker loop error')
        time.sleep(_COBRANCA_SWEEP_SEC)


_HAND_RECHECK_SEC = 300   # cadência da re-checagem de 'solver_queued' — a do cron que ela substituiu


def _gto_hand_worker_loop():
    """Worker em background: drena `gto_hand_requests`.

    DUAS cadências, e a distinção não é cosmética:

      · pedido NOVO ('pending') → processa no ciclo seguinte, que é o valor de ser always-on;
      · pedido já com o solver ('solver_queued') → re-checa só a cada `_HAND_RECHECK_SEC`.

    Por que separar: a re-checagem existe para virar 'done' depois que o solver termina, e foi
    desenhada para um cron de 5 minutos. Rodando a cada ciclo de um loop always-on, o pedido volta
    na lista enquanto o solver não termina e é reprocessado a cada poucos segundos. E como
    `enqueue_solver_spot` RESSUSCITA spot 'done'/'failed' para 'pending', cada volta reenfileirava
    o mesmo spot — um spot que falha virava esteira de re-solve. Foi o que aconteceu em produção
    assim que este worker passou a rodar lá: `req_id=8` reprocessado a cada 6 segundos.

    O age-out fecha o outro lado: spot que o solver não resolve (multiway, deep, árvore rejeitada)
    manteria o pedido queued para sempre. Passado `_GTO_STALE_HOURS`, ele é encerrado — 'sem
    cobertura' é terminal, 'em andamento' há três dias não é.
    """
    from database.repositories import (
        get_pending_gto_hand_requests, update_gto_hand_request,
        expire_stale_gto_hand_requests,
    )
    time.sleep(10)  # aguardar app inicializar
    _proximo_recheck = 0.0
    while True:
        try:
            _agora = time.monotonic()
            _rechecar = _agora >= _proximo_recheck
            if _rechecar:
                _proximo_recheck = _agora + _HAND_RECHECK_SEC
                try:
                    _expirados = expire_stale_gto_hand_requests()
                    if _expirados:
                        log.info("GTO hand worker: %d pedido(s) encerrado(s) por idade "
                                 "(spots sem cobertura do solver)", _expirados)
                except Exception:
                    log.exception("GTO hand worker: falha ao expirar pedidos antigos")

            pending = get_pending_gto_hand_requests(limit=10, include_queued=_rechecar)
            for req in pending:
                log.info("GTO hand worker: processando req_id=%s hand=%s", req['id'], req['hand_id'])
                status, err, n_done, n_queued = _process_gto_hand_request(dict(req))
                update_gto_hand_request(
                    req['id'], status,
                    decisions_done=n_done,
                    error_msg=err,
                )
                log.info("GTO hand worker: req_id=%s → %s (done=%s queued=%s)", req['id'], status, n_done, n_queued)

            # Fallback pro GTO Wizard APOSENTADO: GW foi cancelado e só resolvia HU.
            # Spots que o solver local não cobre (multiway postflop, etc.) ficam como
            # "sem cobertura" (gto_label NULL) — estado honesto — em vez de wizard_pending
            # eterno (que fazia o indicador "processando" mentir pra sempre).

            # Ciclo rápido só quando havia trabalho NOVO. Medir por `pending` não-vazio faria o
            # ciclo de re-checagem (que sempre traz os queued) acelerar o loop sem ter o que fazer.
            _havia_novo = any((r.get('status') or '') == 'pending' for r in pending)
            time.sleep(5 if _havia_novo else 30)
        except Exception:
            log.exception("GTO hand worker loop error")
            time.sleep(30)


def _warmup_gw_multiway(hands: list, hero: str) -> None:
    """
    Warm-up cache GW pra spots preflop multiway de um torneio recém-importado.

    Para cada decisão preflop do hero:
      1. Encoda preflop_actions (formato GW)
      2. Classifica scenario via classify_multiway
      3. Skip se HU comum (rfi/vs_rfi/vs_3bet/vs_4bet) — esses têm cobertura
         local via analyze_preflop. So warm scenarios multiway/squeeze/vs_squeeze
         /5bet_or_higher onde lookup_gto falha.
      4. Dedup por (gametype, depth, preflop_actions) — mesma combinação só é
         resolvida 1x mesmo aparecendo em várias mãos.
      5. Chama lookup_for_hand_decision(use_cache=True) — popula gw_raw_cache.

    Rodando em daemon thread; serializado via _page_fetch_lock no server remoto.
    """
    try:
        from leaklab.gto_wizard_client import (
            lookup_for_hand_decision as _lookup, _enabled as _gw_enabled,
        )
        from leaklab.gw_action_encoder import (
            encode_preflop_actions, find_hero_preflop_decisions,
            num_seated_players, gw_gametype_for, classify_multiway,
        )
        from database.repositories import get_gw_raw_cache
        import hashlib
    except Exception as e:
        log.debug("gw-warmup: imports falharam — %s", e)
        return

    if not _gw_enabled():
        log.info("gw-warmup: GTO_WIZARD_ENABLED=false, skip")
        return
    if not hands or not hero:
        return

    # Coleta spots únicos (gametype, depth_bucket, preflop_actions) — só multiway
    WARM_SCENARIOS = {"multiway", "squeeze", "vs_squeeze", "5bet_or_higher"}
    seen_keys: set[str] = set()
    queue: list[tuple] = []  # (hand, idx, depth_bb)
    total_decisions = 0
    skipped_hu = 0

    for h in hands:
        if not getattr(h, 'hero', None) or h.hero != hero:
            continue
        try:
            n = num_seated_players(h)
            gt = gw_gametype_for(n)
            if not gt:
                continue
        except Exception:
            continue

        for idx in find_hero_preflop_decisions(h):
            total_decisions += 1
            try:
                pf = encode_preflop_actions(h, idx)
            except Exception:
                continue
            classify = classify_multiway(pf)
            if classify.get("scenario") not in WARM_SCENARIOS:
                skipped_hu += 1
                continue

            # Estima depth — tenta extrair stack do hero da linha "Seat N:"
            depth_bb = 100.0
            try:
                from leaklab.hand_state_builder import _effective_stack as _es
                depth_bb = float(_es(h, hero, [a for a in h.actions[:idx]])) or 100.0
            except Exception:
                pass

            # Dedup por chave (gametype, depth bucketed em 10bb, preflop_actions)
            dep_bucket = int(round(depth_bb / 10) * 10)
            key = f"{gt}|{dep_bucket}|{pf}"
            if key in seen_keys:
                continue
            seen_keys.add(key)
            queue.append((h, idx, depth_bb))

    if not queue:
        log.info("gw-warmup: nada pra warmar (decisions=%d hu_skipped=%d uniq=0)",
                 total_decisions, skipped_hu)
        return

    log.info("gw-warmup: iniciando torneio (decisions=%d hu_skip=%d multiway_uniq=%d)",
             total_decisions, skipped_hu, len(queue))

    warmed, hits, errors = 0, 0, 0
    import time as _time
    t0 = _time.time()
    for hand, idx, depth_bb in queue:
        try:
            # cache_only=True primeiro pra contar hits sem chamar GW
            cached = _lookup(hand, idx, depth_bb=depth_bb, cache_only=True)
            if cached:
                hits += 1
                continue
            # Cache miss — faz lookup completo (popula cache)
            r = _lookup(hand, idx, depth_bb=depth_bb, timeout=90, use_cache=True)
            if r:
                warmed += 1
            else:
                errors += 1
        except Exception:
            errors += 1

    log.info("gw-warmup: done em %.0fs (warmed=%d hit=%d err=%d uniq=%d)",
             _time.time() - t0, warmed, hits, errors, len(queue))


# Janela de "forma recente" pro ELO — últimos N torneios.
ELO_WINDOW_TOURNAMENTS = 25


def _recompute_user_elo(user_id: int) -> None:
    """
    Recalcula ELO de FORMA RECENTE do user (últimos ELO_WINDOW_TOURNAMENTS
    torneios) e insere snapshot em player_elo_history. Rodado após cada upload
    — gera série temporal. O pico histórico é derivado do MAX dos snapshots.
    """
    try:
        from leaklab.elo_engine import compute_player_elo_from_decisions, snapshot_to_dict, band_full
        from database.repositories import (get_decisions_for_elo, insert_elo_snapshot,
                                           get_latest_elo, create_notification)
        # Banda anterior (antes de inserir o novo snapshot) — base do trigger.
        prev = get_latest_elo(user_id)
        prev_band = band_full(float(prev['elo_overall']))[1] if prev else None

        decisions = get_decisions_for_elo(user_id, last_n_tournaments=ELO_WINDOW_TOURNAMENTS)
        snapshot  = compute_player_elo_from_decisions(user_id, decisions)
        payload   = snapshot_to_dict(snapshot)
        insert_elo_snapshot(payload)

        # ── Trigger de notificação: mudança de banda de ELO ────────────────────
        new_band = payload['overall']['band_label']
        if prev_band and new_band != prev_band:
            new_elo = float(payload['overall']['elo'])
            delta   = round(new_elo - float(prev['elo_overall']), 1)
            direction = 'up' if delta >= 0 else 'down'
            try:
                create_notification(
                    user_id, f'elo_band_{direction}',
                    payload={'band': new_band, 'prev_band': prev_band,
                             'elo': round(new_elo, 1), 'delta': delta},
                    link='/rating')
            except Exception:
                log.exception("notif elo_band falhou user=%s", user_id)

        log.info("elo-recompute: user=%s overall=%.1f decisions=%d (janela=%dt)",
                 user_id, payload['overall']['elo'], payload['total_decisions'],
                 ELO_WINDOW_TOURNAMENTS)
    except Exception as e:
        log.exception("elo-recompute FAILED user=%s err=%s", user_id, e)


def _auto_queue_gto_for_tournament(t_db_id: int, results: list, user_id: int) -> None:
    """
    Cria gto_hand_requests para todas as mãos com decisões postflop.
    INSERT OR IGNORE — seguro de chamar múltiplas vezes (reimport não duplica).
    Roda em background thread após import de torneio.
    """
    try:
        from database.repositories import bulk_request_gto_for_hands
        hand_ids = list({
            d['hand_id'] for d in results
            if d.get('street') in ('flop', 'turn', 'river') and d.get('hand_id')
        })
        if hand_ids:
            n = bulk_request_gto_for_hands(t_db_id, hand_ids, user_id)
            log.info("GTO auto-queue: %d mãos enfileiradas para torneio t_db=%d", n, t_db_id)
    except Exception:
        log.exception("GTO auto-queue falhou para t_db=%d", t_db_id)


def _enqueue_postflop_spots(results: list, tournament_id: int = None) -> None:
    """
    Enfileira na gto_solver_queue todos os spots postflop do upload que ainda
    não existam em gto_nodes. Roda em background — não bloqueia a resposta ao usuário.
    `tournament_id`: grava o vínculo torneio↔spot (gto_tournament_queue) pro sinal
    "Analisando" ser per-torneio (imune a upload de terceiros).
    """
    from leaklab.gto_utils import compute_spot_hash, normalize_position, board_for_street
    from database.repositories import get_gto_node, enqueue_solver_spot
    import json as _json

    enqueued = 0
    already  = 0
    for d in results:
        if d.get('street') not in ('flop', 'turn', 'river'):
            continue
        try:
            spot   = d.get('spot', {})
            ctx    = d.get('context', {})
            # FATIADO na street, igual ao lookup. Sem isto o spot de flop era gravado com as cinco
            # cartas do river: o hash nunca casava com o que o lookup procura, e o solver ainda
            # recebia `street: flop` com o board completo. Ver `board_for_street`.
            board  = board_for_street(d.get('board', []), d.get('street'))
            hero_h = d.get('hero_cards', [])
            pos    = normalize_position(spot.get('position', ctx.get('position', '')))
            stack  = float(spot.get('effectiveStackBb') or ctx.get('heroStackBb') or 20)
            _level_bb = float(d.get('level_bb') or 1) or 1
            facing = round(float(spot.get('facingSize') or 0) / _level_bb, 2)

            # A variante de pot_type entra no hash DO ENFILEIRAMENTO tambem — sem isto, o
            # solve de um spot 'oop_pfr' seria gravado sob o hash legado e o lookup (que
            # procura na chave certa, sem fallback) nunca o encontraria.
            from leaklab.gto_solver import _effective_pot_type as _epft
            _effq = _epft(spot.get('potType', ''), spot.get('preflopOpener', ''),
                          spot.get('preflop3bettor', ''), stack,
                          hero_pos=pos, vs_pos=normalize_position(
                              spot.get('villainPosition', ctx.get('vsPosition', ''))))
            spot_hash = compute_spot_hash(d['street'], pos, board, hero_h, stack, facing, _effq)
            if get_gto_node(spot_hash):
                already += 1
                continue

            from leaklab.gto_solver import (_priority, _solver_params_for_stack,
                                            resolve_solver_ranges, vale_enfileirar_postflop)
            vs_pos   = normalize_position(spot.get('villainPosition', ctx.get('vsPosition', '')))
            # Não enfileira o que o produto não vai servir. Spot de herói-IP com a flag desligada
            # produziria um nó com a estratégia do VILÃO, e o resync automático o transformaria em
            # veredito sem passar pelo portão do lookup. Ver `vale_enfileirar_postflop`.
            if not vale_enfileirar_postflop(pos, vs_pos, facing):
                continue
            # Ranges pela MESMA função que o lookup usa. Aqui havia duas linhas próprias que
            # punham a range do herói no lugar do IP e a do vilão no lugar do OOP — e o solver
            # devolve o player 0, que é o OOP, então cada jogador recebia a range do outro.
            # Também ignoravam as ranges REAIS capturadas e as genéricas de 6-max deixavam
            # UTG+1, UTG+2 e LJ na range mais larga do arquivo, justo as que deviam ser as mais
            # estreitas. Era inerte enquanto o hash do board estava errado; deixou de ser.
            _ip_range, _oop_range, _hero_ip = resolve_solver_ranges(
                pos, vs_pos, stack,
                pot_type=spot.get('potType', ''),
                opener=spot.get('preflopOpener', ''),
                threebettor=spot.get('preflop3bettor', ''))
            # pot em BB: potSize vem em FICHAS (igual facingSize) → dividir por _level_bb.
            # Sem isso o pot_bb ficava ~100x inflado → SPR colapsava → o solver forçava
            # all-in (estratégia degenerada + exploitability 0.0% fake). Mesmo /_level_bb
            # do facing acima.
            _pot_chips = float(spot.get('potSize') or 0)
            pot_bb   = round(_pot_chips / _level_bb, 2) if _pot_chips > 0 else (facing * 2 + 2 or 4.0)
            _params  = _solver_params_for_stack(stack)
            payload  = _json.dumps({
                'street':                    d['street'],
                'board':                     board,
                'position':                  pos,
                'hero_hand':                 hero_h,
                'hero_stack_bb':             stack,
                'facing_size_bb':            facing,
                'oop_range':                 _oop_range,
                'ip_range':                  _ip_range,
                'hero_is_ip':                _hero_ip,   # main.rs lê player 1 quando IP
                'pot_bb':                    pot_bb,
                'effective_stack_bb':        _params['effective_stack_bb'],  # capped for tree size
                'max_iterations':            _params['max_iterations'],
                'target_exploitability_pct': _params['target_exploitability_pct'],
                '_meta': {'position': pos, 'vs_position': vs_pos, 'hero_hand': hero_h,
                          'hero_stack_bb': stack, 'facing_size_bb': facing,
                          'street': d['street'], 'board': board},
            }, sort_keys=True)

            if enqueue_solver_spot(spot_hash, payload, priority=_priority(d['street']), tournament_id=tournament_id):
                enqueued += 1

            # AUTOMÁTICO DEEP: spot postflop FUNDO (>35bb) → ALÉM do real, enfileira a variante
            # capada a 30bb. Deep OOP de alta SPR costuma falhar/não fechar no stack real; o 30bb
            # cobre como "≈ Aproximação" (a AÇÃO transfere). Mesmo hash que o lookup procura
            # (pot_type default). O lookup prioriza o nó REAL — o 30bb só entra se o real não cobrir.
            if stack > _DEEP_APPROX_MIN_BB:
                _h30 = compute_spot_hash(d['street'], pos, board, hero_h, _DEEP_APPROX_STACK_BB, facing, _effq)
                if not get_gto_node(_h30):
                    _p30 = _solver_params_for_stack(_DEEP_APPROX_STACK_BB)
                    # Ranges do stack CAPADO, não do real: as capturadas são por faixa de stack,
                    # e este solve acontece a 30bb. Pedir a range de 60bb para um solve de 30bb
                    # descreveria um confronto que não é o que está sendo resolvido.
                    _ipr30, _oopr30, _hip30 = resolve_solver_ranges(
                        pos, vs_pos, _DEEP_APPROX_STACK_BB,
                        pot_type=spot.get('potType', ''),
                        opener=spot.get('preflopOpener', ''),
                        threebettor=spot.get('preflop3bettor', ''))
                    _pay30 = _json.dumps({
                        'street': d['street'], 'board': board, 'position': pos, 'hero_hand': hero_h,
                        'hero_stack_bb': _DEEP_APPROX_STACK_BB, 'facing_size_bb': facing,
                        'oop_range': _oopr30,
                        'ip_range':  _ipr30,
                        'hero_is_ip': _hip30,
                        'pot_bb': pot_bb,
                        'effective_stack_bb':        _p30['effective_stack_bb'],
                        'max_iterations':            _p30['max_iterations'],
                        'target_exploitability_pct': _p30['target_exploitability_pct'],
                        '_meta': {'position': pos, 'vs_position': vs_pos, 'hero_hand': hero_h,
                                  'approx_of_stack': stack, 'deep_approx': True,
                                  'street': d['street'], 'board': board},
                    }, sort_keys=True)
                    if enqueue_solver_spot(_h30, _pay30, priority=_priority(d['street']), tournament_id=tournament_id):
                        enqueued += 1
        except Exception:
            pass

    log.info("Upload GTO enqueue: %s novos spots enfileirados, %s já resolvidos", enqueued, already)


def _reconcile_drained_tournaments():
    """Re-anexa o gto_label das decisões de torneios cuja fila do solver JÁ drenou (todos os
    spots 'done') e cujo solve é mais novo que a última reconciliação. Corrige a cobertura
    artificialmente baixa pós-import: o solve termina DEPOIS do import, então as decisões ficam
    com gto_label NULL até um resync. Guarda o progresso em tournaments.labels_reconciled_at
    (não reprocessa até um novo solve). Fill-only: nunca remove/muda cobertura existente."""
    from database.schema import get_conn as _gc
    from database.repositories import _fetchall as _fa
    conn = _gc()
    try:
        cands = _fa(conn, """
            SELECT gtq.tournament_id AS tid
            FROM gto_tournament_queue gtq
            JOIN gto_solver_queue sq ON sq.spot_hash = gtq.spot_hash
            JOIN tournaments t ON t.id = gtq.tournament_id
            GROUP BY gtq.tournament_id, t.labels_reconciled_at
            HAVING SUM(CASE WHEN sq.status IN ('pending','running') THEN 1 ELSE 0 END) = 0
               AND SUM(CASE WHEN sq.status = 'done' THEN 1 ELSE 0 END) > 0
               AND (t.labels_reconciled_at IS NULL OR MAX(sq.solved_at) > t.labels_reconciled_at)
        """)
    finally:
        conn.close()
    if not cands:
        return
    from scripts.resync_postflop_gto import resync_tournament_postflop
    for r in cands:
        tid = dict(r)['tid']
        try:
            n = resync_tournament_postflop(tid, apply=True)
            _c2 = _gc()
            try:
                _c2.execute("UPDATE tournaments SET labels_reconciled_at = datetime('now') WHERE id = ?", (tid,))
                _c2.commit()
            finally:
                _c2.close()
            log.info("reconcile: torneio %s re-anexado (%s decisões preenchidas)", tid, n)
        except Exception:
            log.exception("reconcile tournament %s falhou", tid)


def _solver_queue_worker_loop():
    """Consumidor da fila do solver: EVENT-DRIVEN (acorda no instante do enqueue) + DRENA ATÉ
    ESVAZIAR, com CONCORRÊNCIA = GTO_SOLVER_CONCURRENCY (satura os MAX_SOLVES do solver, em vez
    de 1 solve por vez). Substitui o cron de 5min — sem ociosidade entre lotes. Roda como serviço
    dedicado em prod (run_solver_consumer.py); em dev, atrás de LEAKLAB_LOCAL_SOLVER."""
    from leaklab.gto_solver import run_solver_worker_pool
    import os as _os
    _conc = max(1, int(_os.environ.get('GTO_SOLVER_CONCURRENCY', '2')))
    time.sleep(15)  # aguardar app inicializar
    tick = 0
    while True:
        try:
            from database.schema import get_conn as _gc
            from database.repositories import _fetchone as _f1
            conn = _gc()
            # Reseta spots que ficaram em 'running' > 10 min (backend restart, crash, etc.)
            conn.execute("UPDATE gto_solver_queue SET status='pending' WHERE status='running' AND requested_at < datetime('now', '-10 minutes')")
            conn.commit()
            # acesso por NOME (dict) — em prod (Postgres/RealDictCursor) a linha é dict, não tupla.
            _pr = _f1(conn, "SELECT COUNT(*) AS n FROM gto_solver_queue WHERE status='pending'")
            pending = (dict(_pr).get('n', 0) if _pr else 0) or 0
            conn.close()
            if pending > 0:
                tick += 1
                log.info("Solver queue [tick %s]: pending=%s conc=%s", tick, pending, _conc)
                result = run_solver_worker_pool(max_jobs=min(pending, 50), concurrency=_conc)
                log.info("Solver queue pool resultado: %s", result)
                continue   # re-checa JÁ: drena enquanto houver fila, sem esperar os 60s
        except Exception:
            log.exception("Solver queue worker loop error")
        # Fila drenou → re-anexa labels dos torneios que acabaram de ser solvados (corrige a
        # cobertura artificialmente baixa pós-import). Guardado por labels_reconciled_at, então
        # é barato quando não há nada novo (query de candidatos volta vazia).
        try:
            _reconcile_drained_tournaments()
        except Exception:
            log.exception("reconcile drained tournaments error")
        # Fila vazia → dorme até o próximo enqueue (event-driven); o timeout de 60s é só
        # varredura de segurança (reset de 'running' preso, retries).
        try:
            from leaklab.solver_signals import solver_queue_event
            solver_queue_event.wait(timeout=60)
            solver_queue_event.clear()
        except Exception:
            time.sleep(60)


if __name__ == '__main__':
    import os as _os
    _worker = threading.Thread(target=_gto_hand_worker_loop, daemon=True, name='gto-hand-worker')
    _worker.start()
    # Worker do SOLVER LOCAL (Rust solver_cli): DESLIGADO por padrão em dev — ele drena a fila
    # e come CPU (derruba o PC). O solve de verdade roda no servidor dedicado (Hetzner). Este
    # bloco __main__ nem executa em prod (gunicorn). Pra solvar localmente de propósito:
    #   LEAKLAB_LOCAL_SOLVER=1 python api/app.py
    if _os.environ.get('LEAKLAB_LOCAL_SOLVER', '').lower() in ('1', 'true', 'yes'):
        _solver_worker = threading.Thread(target=_solver_queue_worker_loop, daemon=True, name='gto-solver-worker')
        _solver_worker.start()
        log.warning("gto-solver-worker LIGADO (LEAKLAB_LOCAL_SOLVER=1) — solve local usa CPU pesado")
    else:
        log.info("gto-solver-worker desligado (defina LEAKLAB_LOCAL_SOLVER=1 pra solvar localmente)")
    try:
        from leaklab.gto_wizard_client import start_background_refresher as _gw_start
        _gw_start()
    except Exception:
        pass
    app.run(debug=True, port=5000)
